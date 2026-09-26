"""Bounded Candidate 01 full-vocabulary recognition-utility pipeline.

Heavy TRAIN/DEV extraction and training are user-run only. The smoke and parity
commands are deliberately bounded and never discover or open protected test data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.perception_vnext.governance import (  # noqa: E402
    DEV_MANIFEST,
    TRAIN_MANIFEST,
    VOCAB_MANIFEST,
    audit_governed_dataset,
    governed_rows,
)
from pipeline.perception_vnext.hierarchical_sampler import (  # noqa: E402
    SAMPLER_SCHEMA,
    SAMPLER_TYPE,
    draw_identity,
    hierarchical_clip_draws,
)
from pipeline.perception_vnext.offline_candidate01 import (  # noqa: E402
    Candidate01Offline,
    extract_video,
    sha256,
)
from pipeline.perception_vnext.recognition_schema import (  # noqa: E402
    BODY_INDICES,
    FEATURE_SCHEMA,
    FEATURE_WIDTH,
    MAX_SEQUENCE_LENGTH,
    RAW_SCHEMA,
    RawSequence,
    derive_frame_features,
    load_raw_sequence,
    save_raw_sequence,
    temporal_view,
)

MILESTONE = "PERCEPTION_VNEXT_RECOGNITION_UTILITY_236_01"
SAMPLING_MILESTONE = "PERCEPTION_VNEXT_SAMPLING_GENERALIZATION_236_01"
B1_ROOT = ROOT / (
    "artifacts/recognition_upgrade/p8c3b1_controlled_live_student_geometry_capture_01"
)
B1_ROWS = B1_ROOT / "student_live_frames.jsonl"
PHONE_RUNTIME = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/phone_01/device/"
    "session_20260913T061444Z/native_runtime_audit.json"
)
DEFAULT_OUTPUT = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
)
DEFAULT_DATASET = DEFAULT_OUTPUT / "dataset"
DEFAULT_RUN = DEFAULT_OUTPUT / "tcn_run_01"
DEFAULT_CONFIG = ROOT / (
    "model/config/recognition_upgrade/perception_vnext_recognition_utility_236_01.json"
)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def stable_name(sample_id: str) -> str:
    return hashlib.sha256(sample_id.encode("utf-8")).hexdigest()[:24]


def phone_completed_fps() -> tuple[float, str]:
    evidence = json.loads(PHONE_RUNTIME.read_text(encoding="utf-8-sig"))
    candidates = [
        evidence.get("analyzer_completed_fps"),
        evidence.get("native", {}).get("analyzer_completed_fps"),
        evidence.get("native_live", {}).get("analyzer_completed_fps"),
        evidence.get("final_live_snapshot", {}).get("analyzer_completed_fps"),
    ]
    value = next((float(item) for item in candidates if item is not None), math.nan)
    if not np.isfinite(value) or value <= 0:
        raise RuntimeError("VNEXT_PHONE_FPS_EVIDENCE_INVALID")
    return value, sha256(PHONE_RUNTIME)


def audit_data(output: Path) -> dict[str, Any]:
    result = audit_governed_dataset(check_video_exists=True)
    result.update(
        {
            "milestone": MILESTONE,
            "train_manifest": str(TRAIN_MANIFEST),
            "dev_manifest": str(DEV_MANIFEST),
            "vocab_manifest": str(VOCAB_MANIFEST),
        }
    )
    write_json(output, result)
    return result


def prepare_parity(output: Path) -> dict[str, Any]:
    rows = load_jsonl(B1_ROWS)
    grouped: defaultdict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                str(row["condition_id"]),
                str(row.get("operator_note", "")),
                str(row.get("movement", "")),
            )
        ].append(row)
    required = [
        ("C0_EMPTY_FRAME_NO_PERSON", "", "stationary"),
        ("C1_PERSON_HANDS_DOWN", "", "stationary"),
        ("C2_LEFT_HAND_ONLY", "", "slow"),
        ("C3_RIGHT_HAND_ONLY", "", "slow"),
        ("C4_BOTH_WIDELY_SEPARATED", "", "slow_symmetric"),
        ("C5_BOTH_HANDS_CROSSING", "separated_start", "crossing"),
        ("C5_BOTH_HANDS_CROSSING", "crossed_hold", "crossing"),
        ("C5_BOTH_HANDS_CROSSING", "uncrossing", "crossing"),
        ("C6L_HAND_NEAR_FACE_LEFT", "", "stationary"),
        ("C6R_HAND_NEAR_FACE_RIGHT", "", "stationary"),
        ("C7L_HAND_NEAR_TORSO_LEFT", "", "stationary"),
        ("C7R_HAND_NEAR_TORSO_RIGHT", "", "stationary"),
        ("C8_FINGER_ARTICULATION", "open_palm", "stationary"),
        ("C8_FINGER_ARTICULATION", "closed_fist", "stationary"),
        ("C8_FINGER_ARTICULATION", "index_extended", "stationary"),
        ("C8_FINGER_ARTICULATION", "two_fingers_extended", "stationary"),
    ]
    if any(key not in grouped for key in required):
        raise RuntimeError("VNEXT_PARITY_REQUIRED_CONDITION_MISSING")
    chosen = [grouped[key][len(grouped[key]) // 2] for key in required]
    if len(chosen) != 16:
        raise RuntimeError(f"VNEXT_PARITY_FIXTURE_GROUP_COUNT:{len(chosen)}")
    output.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    for index, row in enumerate(chosen):
        source = B1_ROOT / row["image_filename"]
        if not source.is_file() or sha256(source) != row["image_sha256"]:
            raise RuntimeError(f"VNEXT_PARITY_SOURCE_IDENTITY:{row['retained_sequence_id']}")
        filename = f"frame_{index:02d}.png"
        destination = output / filename
        shutil.copyfile(source, destination)
        manifest_rows.append(
            {
                "frame_id": f"b1_{int(row['retained_sequence_id']):04d}",
                "frame_index": int(row["retained_sequence_id"]),
                "timestamp_ms": float(row["sensor_timestamp_ns"]) / 1_000_000.0,
                "timestamp_source": "P8C3B1_SENSOR_TIMESTAMP",
                "filename": filename,
                "sha256": row["image_sha256"],
                "condition_id": row["condition_id"],
                "operator_note": row.get("operator_note", ""),
                "source_width": int(row["source_width"]),
                "source_height": int(row["source_height"]),
            }
        )
    manifest = {
        "schema": "APPHEAR_VNEXT_PARITY_FIXTURE_V1",
        "milestone": MILESTONE,
        "raw_schema": RAW_SCHEMA,
        "source": str(B1_ROWS),
        "source_sha256": sha256(B1_ROWS),
        "frames": manifest_rows,
        "protected_test_accessed": False,
    }
    write_json(output / "fixture_manifest.json", manifest)
    return manifest


def _json_float_array(value: Any, shape: tuple[int, ...]) -> np.ndarray:
    def flatten(item: Any) -> Iterable[float]:
        if isinstance(item, list):
            for child in item:
                yield from flatten(child)
        else:
            yield np.nan if item is None else float(item)

    return np.asarray(list(flatten(value)), np.float32).reshape(shape)


def _offline_fixture_frame(
    runtime: Candidate01Offline,
    spec: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    image = cv2.imread(str(root / spec["filename"]), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"VNEXT_PARITY_OFFLINE_DECODE:{spec['frame_id']}")
    result = runtime.process_rgb(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    def hand_json(side: int) -> dict[str, Any]:
        hand = result["hands"][side]
        return {
            "anatomical_slot": "LEFT" if side == 0 else "RIGHT",
            "proposal_present": hand["proposal_present"],
            "roi_center_side_source": hand["roi"].tolist(),
            "proposal_support": hand["proposal_support"].tolist(),
            "xy_source": hand["xy"].tolist(),
            "joint_valid": hand["valid"].tolist(),
            "presence": float(hand["presence"]),
            "handedness_diagnostic": float(hand["handedness"]),
            "observed": hand["observed"],
        }

    return {
        "schema": RAW_SCHEMA,
        "frame_id": spec["frame_id"],
        "source_frame_identity": spec["sha256"],
        "frame_index": spec["frame_index"],
        "timestamp_ms": spec["timestamp_ms"],
        "timestamp_source": spec["timestamp_source"],
        "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB",
        "source_width": int(result["source_size"][0]),
        "source_height": int(result["source_size"][1]),
        "left_hand": hand_json(0),
        "right_hand": hand_json(1),
        "body": {
            "indices": BODY_INDICES.tolist(),
            "xy_source": result["body_xy"].reshape(-1).tolist(),
            "support": result["body_support"].tolist(),
            "valid": result["body_valid"].tolist(),
            "available": result["body_available"],
        },
        "current_frame_only": True,
        "synthetic_depth": False,
    }


def offline_parity(fixture_root: Path, android_jsonl: Path, output: Path) -> dict[str, Any]:
    manifest = json.loads((fixture_root / "fixture_manifest.json").read_text(encoding="utf-8"))
    android_rows = load_jsonl(android_jsonl)
    android = {row["frame_id"]: row for row in android_rows}
    specs = manifest["frames"]
    if set(android) != {row["frame_id"] for row in specs}:
        raise RuntimeError("VNEXT_PARITY_ANDROID_FRAME_SET")
    offline_rows = []
    with Candidate01Offline() as runtime:
        for spec in specs:
            offline_rows.append(_offline_fixture_frame(runtime, spec, fixture_root))
    errors: dict[str, list[float]] = {
        "body_xy_px": [],
        "body_support_abs": [],
        "hand_xy_px": [],
        "hand_roi_abs_px": [],
        "proposal_support_abs": [],
        "presence_abs": [],
        "handedness_abs": [],
    }
    structural_failures: list[str] = []
    for expected in offline_rows:
        actual = android[expected["frame_id"]]
        for key in (
            "schema",
            "source_frame_identity",
            "frame_index",
            "timestamp_ms",
            "timestamp_source",
            "image_semantics",
            "source_width",
            "source_height",
        ):
            if actual[key] != expected[key]:
                structural_failures.append(f"{expected['frame_id']}:{key}")
        eb = expected["body"]
        ab = actual["body"]
        for key in ("indices", "valid", "available"):
            if ab[key] != eb[key]:
                structural_failures.append(f"{expected['frame_id']}:body:{key}")
        body_mask = np.asarray(eb["valid"], bool) & np.asarray(ab["valid"], bool)
        e_body = _json_float_array(eb["xy_source"], (8, 2))
        a_body = _json_float_array(ab["xy_source"], (8, 2))
        errors["body_xy_px"].extend(np.linalg.norm(e_body[body_mask] - a_body[body_mask], axis=1))
        errors["body_support_abs"].extend(
            np.abs(_json_float_array(eb["support"], (8,)) - _json_float_array(ab["support"], (8,)))
        )
        for side in ("left_hand", "right_hand"):
            eh = expected[side]
            ah = actual[side]
            for key in ("anatomical_slot", "proposal_present", "joint_valid", "observed"):
                if ah[key] != eh[key]:
                    structural_failures.append(f"{expected['frame_id']}:{side}:{key}")
            e_support = _json_float_array(eh["proposal_support"], (21,))
            a_support = _json_float_array(ah["proposal_support"], (21,))
            errors["proposal_support_abs"].extend(np.abs(e_support - a_support))
            if eh["proposal_present"] and ah["proposal_present"]:
                errors["hand_roi_abs_px"].extend(
                    np.abs(
                        _json_float_array(eh["roi_center_side_source"], (3,))
                        - _json_float_array(ah["roi_center_side_source"], (3,))
                    )
                )
                e_presence = float(eh["presence"])
                a_presence = float(ah["presence"])
                errors["presence_abs"].append(abs(e_presence - a_presence))
                errors["handedness_abs"].append(
                    abs(float(eh["handedness_diagnostic"]) - float(ah["handedness_diagnostic"]))
                )
                mask = np.asarray(eh["joint_valid"], bool) & np.asarray(ah["joint_valid"], bool)
                e_xy = _json_float_array(eh["xy_source"], (21, 2))
                a_xy = _json_float_array(ah["xy_source"], (21, 2))
                errors["hand_xy_px"].extend(np.linalg.norm(e_xy[mask] - a_xy[mask], axis=1))

    def stats(values: list[float]) -> dict[str, float | int | None]:
        clean = np.asarray(values, np.float64)
        return {
            "count": len(clean),
            "p50": float(np.quantile(clean, 0.5)) if len(clean) else None,
            "p95": float(np.quantile(clean, 0.95)) if len(clean) else None,
            "max": float(np.max(clean)) if len(clean) else None,
        }

    numeric = {name: stats(values) for name, values in errors.items()}
    thresholds = {
        "body_xy_px": {"p95": 2.0, "max": 5.0},
        "body_support_abs": {"p95": 0.02, "max": 0.05},
        "hand_xy_px": {"p95": 3.0, "max": 8.0},
        "hand_roi_abs_px": {"p95": 2.0, "max": 5.0},
        "proposal_support_abs": {"p95": 0.02, "max": 0.05},
        "presence_abs": {"p95": 0.02, "max": 0.05},
        "handedness_abs": {"p95": 0.02, "max": 0.05},
    }
    numeric_failures = []
    for name, gate in thresholds.items():
        measured = numeric[name]
        if measured["count"] and (measured["p95"] > gate["p95"] or measured["max"] > gate["max"]):
            numeric_failures.append(name)
    result = {
        "schema": "APPHEAR_VNEXT_ANDROID_OFFLINE_PARITY_RESULT_V1",
        "milestone": MILESTONE,
        "status": "PASS" if not structural_failures and not numeric_failures else "FAIL",
        "frames": len(specs),
        "structural_failures": structural_failures,
        "numeric_failures": numeric_failures,
        "numeric": numeric,
        "thresholds": thresholds,
        "android_output_sha256": sha256(android_jsonl),
        "protected_test_accessed": False,
    }
    write_json(output, result)
    if result["status"] != "PASS":
        raise RuntimeError(f"VNEXT_PARITY_FAILURE:{result}")
    return result


def save_feature_package(
    path: Path,
    raw: RawSequence,
    phone_fps: float,
    phone_fps_evidence_sha256: str,
) -> None:
    derived = derive_frame_features(raw)
    dense = temporal_view(
        derived,
        raw.timestamp_ms,
        condition="dense",
        phone_completed_fps=phone_fps,
    )
    sparse = temporal_view(
        derived,
        raw.timestamp_ms,
        condition="phone_01_sparse",
        phone_completed_fps=phone_fps,
    )
    metadata = {
        "schema": FEATURE_SCHEMA,
        "raw_schema": RAW_SCHEMA,
        "feature_width": FEATURE_WIDTH,
        "max_sequence_length": MAX_SEQUENCE_LENGTH,
        "sample_id": raw.metadata["sample_id"],
        "split": raw.metadata["split"],
        "class_id": raw.metadata["class_id"],
        "canonical_gloss": raw.metadata["canonical_gloss"],
        "signer_id": raw.metadata["signer_id"],
        "source_id": raw.metadata["source_id"],
        "phone_completed_fps": phone_fps,
        "phone_fps_evidence_sha256": phone_fps_evidence_sha256,
        "dense_semantics": "chronological actual observations; unique timestamp reduction only",
        "sparse_semantics": (
            "nearest unique actual observations on measured PHONE_01 timestamp grid"
        ),
        "padding_semantics": "post-zero-padding with false sequence mask; no copied observations",
        "duration_ms": float(raw.timestamp_ms[-1] - raw.timestamp_ms[0]),
        "duration_scope": raw.metadata["duration_scope"],
        "timestamp_sources": raw.metadata["timestamp_sources"],
        "dense_frames": int(dense["mask"].sum()),
        "sparse_frames": int(sparse["mask"].sum()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        metadata_json=np.asarray(json.dumps(metadata, sort_keys=True)),
        dense_features=dense["features"],
        dense_mask=dense["mask"],
        dense_source_indices=dense["source_indices"],
        dense_source_timestamps_ms=dense["source_timestamps_ms"],
        sparse_features=sparse["features"],
        sparse_mask=sparse["mask"],
        sparse_source_indices=sparse["source_indices"],
        sparse_source_timestamps_ms=sparse["source_timestamps_ms"],
    )


def verify_feature_package(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as data:
        metadata = json.loads(str(data["metadata_json"].item()))
        if metadata["schema"] != FEATURE_SCHEMA:
            raise RuntimeError("VNEXT_FEATURE_SCHEMA_IDENTITY")
        for condition in ("dense", "sparse"):
            features = np.asarray(data[f"{condition}_features"], np.float32)
            mask = np.asarray(data[f"{condition}_mask"], bool)
            if features.shape != (MAX_SEQUENCE_LENGTH, FEATURE_WIDTH):
                raise RuntimeError("VNEXT_FEATURE_SHAPE")
            if mask.shape != (MAX_SEQUENCE_LENGTH,) or not np.any(mask):
                raise RuntimeError("VNEXT_MASK_SHAPE")
            if not np.all(np.isfinite(features)):
                raise RuntimeError("VNEXT_FEATURE_NONFINITE")
            if np.any(features[~mask] != 0):
                raise RuntimeError("VNEXT_PADDING_NONZERO")
        return metadata


def extract_dataset(
    output: Path,
    splits: list[str],
    *,
    resume: bool,
    limit_per_split: int | None,
) -> dict[str, Any]:
    governance = audit_governed_dataset(check_video_exists=True)
    if governance["status"] != "PASS" and limit_per_split is None:
        write_json(output / "governance_audit.json", governance)
        raise RuntimeError(
            f"VNEXT_EXTRACTION_GOVERNANCE_BLOCKED:{governance['status']}:"
            f"missing={governance['missing_raw_video_count']}"
        )
    phone_fps, phone_hash = phone_completed_fps()
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "governance_audit.json", governance)
    write_json(
        output / "contract.json",
        {
            "milestone": MILESTONE,
            "raw_schema": RAW_SCHEMA,
            "feature_schema": FEATURE_SCHEMA,
            "feature_width": FEATURE_WIDTH,
            "max_sequence_length": MAX_SEQUENCE_LENGTH,
            "phone_completed_fps": phone_fps,
            "phone_fps_evidence": str(PHONE_RUNTIME),
            "phone_fps_evidence_sha256": phone_hash,
            "protected_test_accessed": False,
        },
    )
    completed = []
    with Candidate01Offline() as runtime:
        for split in splits:
            rows = governed_rows(split)
            if limit_per_split is not None:
                # Deterministic breadth-first smoke: distinct classes before repeated classes.
                selected = []
                seen: set[int] = set()
                for row in rows:
                    class_id = int(row["class_id"])
                    if class_id not in seen and Path(row["raw_video_path"]).is_file():
                        selected.append(row)
                        seen.add(class_id)
                    if len(selected) >= limit_per_split:
                        break
                rows = selected
            for position, row in enumerate(rows, start=1):
                stem = stable_name(row["sample_id"])
                raw_path = output / "raw" / split / f"{stem}.npz"
                feature_path = output / "features" / split / f"{stem}.npz"
                if raw_path.exists() != feature_path.exists():
                    raise RuntimeError(
                        f"VNEXT_PARTIAL_SAMPLE_OUTPUT:{row['sample_id']}:manual_review_required"
                    )
                if resume and raw_path.is_file() and feature_path.is_file():
                    raw = load_raw_sequence(raw_path)
                    metadata = verify_feature_package(feature_path)
                    if (
                        raw.metadata["sample_id"] != row["sample_id"]
                        or metadata["sample_id"] != row["sample_id"]
                    ):
                        raise RuntimeError(f"VNEXT_RESUME_IDENTITY:{row['sample_id']}")
                    status = "REUSED"
                else:
                    if raw_path.exists() or feature_path.exists():
                        raise RuntimeError(
                            f"VNEXT_SAMPLE_OUTPUT_EXISTS_USE_RESUME:{row['sample_id']}"
                        )
                    raw = extract_video(runtime, row)
                    save_raw_sequence(raw_path, raw)
                    reloaded = load_raw_sequence(raw_path)
                    if reloaded.metadata["sample_id"] != row["sample_id"]:
                        raise RuntimeError("VNEXT_RAW_RELOAD_IDENTITY")
                    save_feature_package(feature_path, raw, phone_fps, phone_hash)
                    metadata = verify_feature_package(feature_path)
                    status = "EXTRACTED"
                with np.load(feature_path, allow_pickle=False) as feature_data:
                    dense_frames = int(np.asarray(feature_data["dense_mask"], bool).sum())
                    sparse_frames = int(np.asarray(feature_data["sparse_mask"], bool).sum())
                completed.append(
                    {
                        "sample_id": row["sample_id"],
                        "split": split,
                        "class_id": int(row["class_id"]),
                        "canonical_gloss": row["canonical_gloss"],
                        "signer_id": row["signer_group_id"],
                        "source_id": row["source_dataset"],
                        "raw_path": str(raw_path.resolve()),
                        "feature_path": str(feature_path.resolve()),
                        "raw_frames": len(raw.frame_index),
                        "dense_frames": dense_frames,
                        "sparse_frames": sparse_frames,
                        "status": status,
                    }
                )
                print(
                    f"[{split} {position}/{len(rows)}] {status} {row['sample_id']} "
                    f"raw={len(raw.frame_index)}",
                    flush=True,
                )
    index = output / "index.jsonl"
    with index.open("w", encoding="utf-8", newline="\n") as stream:
        for row in completed:
            stream.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")
    result = {
        "schema": "APPHEAR_VNEXT_EXTRACTION_RESULT_V1",
        "status": (
            "PASS"
            if all(any(row["split"] == split for row in completed) for split in splits)
            else "FAIL_GOVERNED_SPLIT_RAW_UNAVAILABLE"
        ),
        "smoke": limit_per_split is not None,
        "splits": dict(Counter(row["split"] for row in completed)),
        "classes": len({row["class_id"] for row in completed}),
        "samples": len(completed),
        "raw_schema": RAW_SCHEMA,
        "feature_schema": FEATURE_SCHEMA,
        "index": str(index.resolve()),
        "protected_test_accessed": False,
        "governance_status": governance["status"],
    }
    write_json(output / "extraction_result.json", result)
    return result


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        config.get("milestone") not in {MILESTONE, SAMPLING_MILESTONE}
        or config.get("raw_schema") != RAW_SCHEMA
        or config.get("feature_schema") != FEATURE_SCHEMA
        or config.get("input_shape") != [MAX_SEQUENCE_LENGTH, FEATURE_WIDTH]
        or config.get("classes") != 236
        or config.get("governance", {}).get("protected_test_access") is not False
    ):
        raise RuntimeError("VNEXT_TRAINING_CONFIG_CONTRACT")
    return config


def load_index(dataset: Path) -> list[dict[str, Any]]:
    index = dataset / "index.jsonl"
    if not index.is_file():
        raise RuntimeError("VNEXT_DATASET_INDEX_MISSING")
    rows = load_jsonl(index)
    if not rows:
        raise RuntimeError("VNEXT_DATASET_INDEX_EMPTY")
    return rows


def _examples(
    rows: list[dict[str, Any]], conditions: tuple[str, ...]
) -> Iterable[tuple[tuple[np.ndarray, np.ndarray], np.int32]]:
    for row in rows:
        with np.load(Path(row["feature_path"]), allow_pickle=False) as data:
            metadata = json.loads(str(data["metadata_json"].item()))
            if metadata["schema"] != FEATURE_SCHEMA or int(metadata["class_id"]) != int(
                row["class_id"]
            ):
                raise RuntimeError(f"VNEXT_TRAIN_EXAMPLE_IDENTITY:{row['sample_id']}")
            for condition in conditions:
                prefix = "dense" if condition == "dense" else "sparse"
                features = np.asarray(data[f"{prefix}_features"], np.float32)
                mask = np.asarray(data[f"{prefix}_mask"], bool)
                if features.shape != (MAX_SEQUENCE_LENGTH, FEATURE_WIDTH) or not np.all(
                    np.isfinite(features)
                ):
                    raise RuntimeError(f"VNEXT_TRAIN_EXAMPLE_SHAPE:{row['sample_id']}")
                yield (features, mask), np.int32(row["class_id"])


def make_dataset(
    rows: list[dict[str, Any]],
    conditions: tuple[str, ...],
    batch_size: int,
    seed: int,
    training: bool,
) -> Any:
    import tensorflow as tf

    def generator() -> Iterable[tuple[tuple[np.ndarray, np.ndarray], np.int32]]:
        yield from _examples(rows, conditions)

    dataset = tf.data.Dataset.from_generator(
        generator,
        output_signature=(
            (
                tf.TensorSpec((MAX_SEQUENCE_LENGTH, FEATURE_WIDTH), tf.float32),
                tf.TensorSpec((MAX_SEQUENCE_LENGTH,), tf.bool),
            ),
            tf.TensorSpec((), tf.int32),
        ),
    )
    if training:
        dataset = dataset.shuffle(
            min(len(rows) * len(conditions), 4096),
            seed=seed,
            reshuffle_each_iteration=True,
        )
    batches = math.ceil(len(rows) * len(conditions) / batch_size)
    return (
        dataset.batch(batch_size)
        .apply(tf.data.experimental.assert_cardinality(batches))
        .prefetch(1)
    )


def build_tcn(config: dict[str, Any]) -> Any:
    import tensorflow as tf

    from model.model import build_encoder

    model_config = config["model"]
    features = tf.keras.Input(
        (MAX_SEQUENCE_LENGTH, FEATURE_WIDTH), dtype="float32", name="features"
    )
    frame_mask = tf.keras.Input((MAX_SEQUENCE_LENGTH,), dtype="bool", name="frame_mask")
    encoder = build_encoder(
        MAX_SEQUENCE_LENGTH,
        FEATURE_WIDTH,
        int(model_config["blocks"]),
        int(model_config["channels"]),
        tuple(int(value) for value in model_config["dilations"]),
        int(model_config["kernel"]),
        float(model_config["dropout"]),
    )
    encoded = encoder(features)
    pooled = tf.keras.layers.GlobalAveragePooling1D(name="masked_pool")(encoded, mask=frame_mask)
    probabilities = tf.keras.layers.Dense(236, activation="softmax", name="gloss_probabilities")(
        pooled
    )
    model = tf.keras.Model(
        [features, frame_mask], probabilities, name="vnext_236_mask_aware_causal_tcn"
    )
    model.compile(
        optimizer=tf.keras.optimizers.AdamW(
            learning_rate=float(config["training"]["learning_rate"]),
            weight_decay=float(config["training"]["weight_decay"]),
        ),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(),
        metrics=[
            tf.keras.metrics.SparseCategoricalAccuracy(name="top1"),
            tf.keras.metrics.SparseTopKCategoricalAccuracy(k=5, name="top5"),
        ],
    )
    return model


def _atomic_write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    write_json(temporary, value)
    os.replace(temporary, path)


def _atomic_copy(source: Path, destination: Path) -> None:
    temporary = destination.with_name(f"{destination.name}.tmp")
    shutil.copyfile(source, temporary)
    os.replace(temporary, destination)


def _write_balanced_history(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = ["epoch", "loss", "top1", "top5", "val_loss", "val_top1", "val_top5"]
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _validate_sampling_only_delta(config: dict[str, Any]) -> None:
    baseline = load_config(DEFAULT_CONFIG)
    keys = (
        "seed",
        "raw_schema",
        "feature_schema",
        "input_shape",
        "classes",
        "model",
        "training",
        "governance",
        "runtime_scope",
    )
    changed = [key for key in keys if config.get(key) != baseline.get(key)]
    if changed:
        raise RuntimeError(f"VNEXT_SAMPLING_SCIENTIFIC_DELTA_VIOLATION:{changed}")
    sampler = config.get("training_sampler", {})
    if sampler.get("schema") != SAMPLER_SCHEMA or sampler.get("type") != SAMPLER_TYPE:
        raise RuntimeError("VNEXT_SAMPLING_CONTRACT_IDENTITY")
    if int(sampler.get("draws_per_epoch", -1)) != 3926:
        raise RuntimeError("VNEXT_SAMPLING_DRAW_BUDGET")
    if sampler.get("views_per_draw") != ["dense", "sparse"]:
        raise RuntimeError("VNEXT_SAMPLING_VIEW_POLICY")


def _train_hierarchical(
    dataset: Path,
    output: Path,
    config_path: Path,
    config: dict[str, Any],
    train_rows: list[dict[str, Any]],
    dev_rows: list[dict[str, Any]],
    *,
    resume: bool,
    smoke: bool,
) -> dict[str, Any]:
    import tensorflow as tf

    _validate_sampling_only_delta(config)
    if output.resolve() == DEFAULT_RUN.resolve():
        raise RuntimeError("VNEXT_SAMPLING_BASELINE_OVERWRITE_REFUSED")
    baseline_identity = json.loads((DEFAULT_RUN / "run_identity.json").read_text(encoding="utf-8"))
    baseline_best = DEFAULT_RUN / "best.keras"
    if not baseline_best.is_file():
        raise RuntimeError("VNEXT_SAMPLING_BASELINE_CONTROL_MISSING")
    dataset_hash = sha256(dataset / "contract.json")
    if dataset_hash != baseline_identity.get("dataset_contract_sha256"):
        raise RuntimeError("VNEXT_SAMPLING_DATASET_DRIFT")

    seed = int(config["seed"])
    epochs = 1 if smoke else int(config["training"]["epochs"])
    batch_size = int(config["training"]["batch_size"])
    declared_draws_per_epoch = int(config["training_sampler"]["draws_per_epoch"])
    draws_per_epoch = 236 if smoke else declared_draws_per_epoch
    patience = int(config["training"]["early_stop_patience"])
    config_hash = sha256(config_path)
    output.mkdir(parents=True, exist_ok=True)
    reproducibility = output / "reproducibility_config.json"
    if reproducibility.is_file() and sha256(reproducibility) != config_hash:
        raise RuntimeError("VNEXT_RESUME_CONFIG_DRIFT")
    if not reproducibility.is_file():
        shutil.copyfile(config_path, reproducibility)
    identity = {
        "milestone": config["milestone"],
        "seed": seed,
        "raw_schema": RAW_SCHEMA,
        "feature_schema": FEATURE_SCHEMA,
        "vocabulary_manifest": str(VOCAB_MANIFEST.resolve()),
        "vocabulary_sha256": sha256(VOCAB_MANIFEST),
        "config_sha256": config_hash,
        "dataset_contract_sha256": dataset_hash,
        "train_manifest_sha256": sha256(TRAIN_MANIFEST),
        "dev_manifest_sha256": sha256(DEV_MANIFEST),
        "sampler_schema": SAMPLER_SCHEMA,
        "sampler_type": SAMPLER_TYPE,
        "draws_per_epoch": draws_per_epoch,
        "declared_draws_per_epoch": declared_draws_per_epoch,
        "views_per_draw": ["dense", "sparse"],
        "baseline_run": str(DEFAULT_RUN.resolve()),
        "baseline_best_sha256": sha256(baseline_best),
        "scientific_delta": "TRAIN sample selection policy only",
        "smoke": smoke,
        "protected_test_accessed": False,
    }
    run_identity = output / "run_identity.json"
    if run_identity.is_file() and json.loads(run_identity.read_text(encoding="utf-8")) != identity:
        raise RuntimeError("VNEXT_SAMPLING_RUN_IDENTITY_DRIFT")
    write_json(run_identity, identity)

    state_path = output / "resume_state.json"
    history_path = output / "history.csv"
    latest = output / "latest.keras"
    best = output / "best.keras"
    final = output / "final.keras"
    resume_dir = output / "resume_checkpoints"
    resume_dir.mkdir(exist_ok=True)
    history_rows: list[dict[str, Any]] = []
    best_loss = math.inf
    best_epoch = -1
    best_checkpoint: Path | None = None
    wait = 0
    stopped_early = False
    initial_epoch = 0
    tf.keras.utils.set_random_seed(seed)
    if state_path.is_file():
        if not resume:
            raise RuntimeError("VNEXT_RUN_EXISTS_USE_RESUME")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        required_state = {
            "config_sha256": config_hash,
            "dataset_contract_sha256": dataset_hash,
            "sampler_schema": SAMPLER_SCHEMA,
            "sampler_type": SAMPLER_TYPE,
            "smoke": smoke,
            "effective_draws_per_epoch": draws_per_epoch,
        }
        if any(state.get(key) != value for key, value in required_state.items()):
            raise RuntimeError("VNEXT_SAMPLING_RESUME_STATE_DRIFT")
        current_checkpoint = Path(state["current_checkpoint"])
        if not current_checkpoint.is_file() or sha256(current_checkpoint) != state[
            "current_checkpoint_sha256"
        ]:
            raise RuntimeError("VNEXT_SAMPLING_RESUME_CHECKPOINT_INVALID")
        model = tf.keras.models.load_model(current_checkpoint, safe_mode=True)
        history_rows = list(state["history"])
        initial_epoch = int(state["completed_epochs"])
        best_loss = float(state["best_val_loss"])
        best_epoch = int(state["best_epoch"])
        best_checkpoint = Path(state["best_checkpoint"])
        wait = int(state["early_stop_wait"])
        stopped_early = bool(state["stopped_early"])
        if not best_checkpoint.is_file() or sha256(best_checkpoint) != state[
            "best_checkpoint_sha256"
        ]:
            raise RuntimeError("VNEXT_SAMPLING_BEST_CHECKPOINT_INVALID")
        _atomic_copy(current_checkpoint, latest)
        _atomic_copy(best_checkpoint, best)
        _write_balanced_history(history_path, history_rows)
    else:
        disallowed = [
            path
            for path in (history_path, latest, best, final)
            if path.exists()
        ]
        if disallowed:
            raise RuntimeError(f"VNEXT_SAMPLING_PARTIAL_RUN_WITHOUT_STATE:{disallowed}")
        model = build_tcn(config)

    effective_dev_rows = dev_rows[:16] if smoke else dev_rows
    dev_ds = make_dataset(effective_dev_rows, ("dense", "sparse"), batch_size, seed, False)
    fit_skipped_existing_complete_run = bool(initial_epoch >= epochs or stopped_early)
    for epoch in range(initial_epoch, epochs):
        if stopped_early:
            break
        selected = hierarchical_clip_draws(
            train_rows,
            draws=draws_per_epoch,
            seed=seed,
            epoch=epoch,
        )
        train_ds = make_dataset(selected, ("dense", "sparse"), batch_size, seed, False)
        fit = model.fit(
            train_ds,
            validation_data=dev_ds,
            initial_epoch=epoch,
            epochs=epoch + 1,
            verbose=2,
            shuffle=False,
        )
        record = {"epoch": epoch}
        for key in ("loss", "top1", "top5", "val_loss", "val_top1", "val_top5"):
            values = fit.history.get(key)
            if not values or not np.isfinite(float(values[-1])):
                raise RuntimeError(f"VNEXT_SAMPLING_NONFINITE_METRIC:{epoch}:{key}")
            record[key] = float(values[-1])
        epoch_checkpoint = resume_dir / f"epoch_{epoch + 1:03d}.keras"
        model.save(epoch_checkpoint)
        history_rows.append(record)
        if record["val_loss"] < best_loss:
            best_loss = record["val_loss"]
            best_epoch = epoch
            best_checkpoint = epoch_checkpoint
            wait = 0
        else:
            wait += 1
        stopped_early = wait >= patience
        if best_checkpoint is None:
            raise AssertionError("best checkpoint was not initialized")
        state = {
            "schema": "APPHEAR_VNEXT_BALANCED_RESUME_STATE_V1",
            "config_sha256": config_hash,
            "dataset_contract_sha256": dataset_hash,
            "sampler_schema": SAMPLER_SCHEMA,
            "sampler_type": SAMPLER_TYPE,
            "smoke": smoke,
            "effective_draws_per_epoch": draws_per_epoch,
            "completed_epochs": epoch + 1,
            "current_checkpoint": str(epoch_checkpoint.resolve()),
            "current_checkpoint_sha256": sha256(epoch_checkpoint),
            "best_epoch": best_epoch,
            "best_val_loss": best_loss,
            "best_checkpoint": str(best_checkpoint.resolve()),
            "best_checkpoint_sha256": sha256(best_checkpoint),
            "early_stop_wait": wait,
            "early_stop_patience": patience,
            "stopped_early": stopped_early,
            "epoch_draw_sha256": draw_identity(selected),
            "history": history_rows,
            "protected_test_accessed": False,
        }
        _atomic_write_json(state_path, state)
        _atomic_copy(epoch_checkpoint, latest)
        _atomic_copy(best_checkpoint, best)
        _write_balanced_history(history_path, history_rows)
        if stopped_early:
            break

    if best_checkpoint is None:
        raise RuntimeError("VNEXT_SAMPLING_NO_COMPLETED_EPOCH")
    best_model = tf.keras.models.load_model(best_checkpoint, safe_mode=True)
    model.set_weights(best_model.get_weights())
    model.save(final)
    reloaded = tf.keras.models.load_model(final, safe_mode=True)
    sample_inputs, _ = next(
        iter(make_dataset(effective_dev_rows[:1], ("dense",), 1, seed, False))
    )
    before = np.asarray(model(sample_inputs, training=False))
    after = np.asarray(reloaded(sample_inputs, training=False))
    reload_max_abs = float(np.max(np.abs(before - after)))
    metric_values = [
        float(value)
        for row in history_rows
        for key, value in row.items()
        if key != "epoch"
    ]
    finite_losses = bool(history_rows) and bool(
        np.all(np.isfinite(np.asarray(metric_values, np.float64)))
    )
    if not finite_losses or reload_max_abs > 1e-6:
        raise RuntimeError(
            f"VNEXT_SAMPLING_TRAIN_SANITY:finite={finite_losses}:reload={reload_max_abs}"
        )
    result = {
        "schema": "APPHEAR_VNEXT_BALANCED_TRAIN_RESULT_V1",
        "milestone": config["milestone"],
        "status": "PASS",
        "smoke": smoke,
        "architecture": "one established 4x64 mask-aware causal TCN",
        "classes": 236,
        "train_clips": len(train_rows),
        "dev_clips": len(dev_rows),
        "sampler_schema": SAMPLER_SCHEMA,
        "sampler_type": SAMPLER_TYPE,
        "clip_draws_per_epoch": draws_per_epoch,
        "train_examples_per_epoch": draws_per_epoch * 2,
        "steps_per_epoch": math.ceil(draws_per_epoch * 2 / batch_size),
        "dev_examples": len(effective_dev_rows) * 2,
        "epochs_completed": len(history_rows),
        "stopped_early": stopped_early,
        "best_epoch_zero_based": best_epoch,
        "best_val_loss": best_loss,
        "parameter_count": model.count_params(),
        "finite_loss_and_metrics": finite_losses,
        "checkpoint_reload_max_abs": reload_max_abs,
        "checkpoint_reload_target": "final.keras",
        "fit_skipped_existing_complete_run": fit_skipped_existing_complete_run,
        "config_sha256": config_hash,
        "dataset_contract_sha256": dataset_hash,
        "best_checkpoint": str(best.resolve()),
        "latest_checkpoint": str(latest.resolve()),
        "final_checkpoint": str(final.resolve()),
        "resume_state": str(state_path.resolve()),
        "baseline_best_sha256": sha256(baseline_best),
        "protected_test_accessed": False,
        "recognition_accuracy_claim": False if smoke else "DEV_EVALUATION_REQUIRED",
    }
    write_json(output / ("smoke_training_result.json" if smoke else "training_result.json"), result)
    return result


def train_model(
    dataset: Path,
    output: Path,
    config_path: Path,
    *,
    resume: bool,
    smoke: bool,
) -> dict[str, Any]:
    import tensorflow as tf

    config = load_config(config_path)
    rows = load_index(dataset)
    train_rows = [row for row in rows if row["split"] == "train"]
    dev_rows = [row for row in rows if row["split"] == "dev"]
    if not train_rows or not dev_rows:
        raise RuntimeError("VNEXT_TRAIN_SPLITS_MISSING")
    if set(row["signer_id"] for row in train_rows) & set(row["signer_id"] for row in dev_rows):
        raise RuntimeError("VNEXT_TRAIN_SIGNER_LEAKAGE")
    if len({row["sample_id"] for row in rows}) != len(rows):
        raise RuntimeError("VNEXT_TRAIN_DUPLICATE_SAMPLE")
    if not smoke:
        audit = audit_governed_dataset(check_video_exists=False)
        if len(train_rows) != audit["train"]["clips"] or len(dev_rows) != audit["dev"]["clips"]:
            raise RuntimeError("VNEXT_FULL_TRAIN_DATASET_INCOMPLETE")
        if {int(row["class_id"]) for row in train_rows} != set(range(236)) or {
            int(row["class_id"]) for row in dev_rows
        } != set(range(236)):
            raise RuntimeError("VNEXT_FULL_TRAIN_CLASS_COVERAGE")
    if config.get("training_sampler"):
        return _train_hierarchical(
            dataset,
            output,
            config_path,
            config,
            train_rows,
            dev_rows,
            resume=resume,
            smoke=smoke,
        )
    seed = int(config["seed"])
    tf.keras.utils.set_random_seed(seed)
    output.mkdir(parents=True, exist_ok=True)
    reproducibility = output / "reproducibility_config.json"
    if reproducibility.is_file() and sha256(reproducibility) != sha256(config_path):
        raise RuntimeError("VNEXT_RESUME_CONFIG_DRIFT")
    if not reproducibility.is_file():
        shutil.copyfile(config_path, reproducibility)
    write_json(
        output / "run_identity.json",
        {
            "milestone": MILESTONE,
            "seed": seed,
            "raw_schema": RAW_SCHEMA,
            "feature_schema": FEATURE_SCHEMA,
            "vocabulary_manifest": str(VOCAB_MANIFEST.resolve()),
            "vocabulary_sha256": sha256(VOCAB_MANIFEST),
            "config_sha256": sha256(config_path),
            "dataset_contract_sha256": sha256(dataset / "contract.json"),
            "train_manifest_sha256": sha256(TRAIN_MANIFEST),
            "dev_manifest_sha256": sha256(DEV_MANIFEST),
            "protected_test_accessed": False,
        },
    )
    latest = output / "latest.keras"
    best = output / "best.keras"
    history = output / "history.csv"
    initial_epoch = 0
    if resume:
        if latest.is_file():
            model = tf.keras.models.load_model(latest, safe_mode=True)
            if history.is_file():
                with history.open("r", encoding="utf-8", newline="") as stream:
                    initial_epoch = (
                        max((int(row["epoch"]) for row in csv.DictReader(stream)), default=-1) + 1
                    )
        elif any(path.exists() for path in (best, history)):
            raise RuntimeError("VNEXT_RESUME_PARTIAL_RUN_WITHOUT_LATEST_CHECKPOINT")
        else:
            # The user-facing heavy command is intentionally one-shot: it starts a
            # pristine run and resumes the same directory after interruption.
            model = build_tcn(config)
    else:
        if any(path.exists() for path in (latest, best, history)):
            raise RuntimeError("VNEXT_RUN_EXISTS_USE_RESUME")
        model = build_tcn(config)
    epochs = 1 if smoke else int(config["training"]["epochs"])
    batch_size = min(4, len(train_rows) * 2) if smoke else int(config["training"]["batch_size"])
    train_ds = make_dataset(train_rows, ("dense", "sparse"), batch_size, seed, True)
    dev_ds = make_dataset(dev_rows, ("dense", "sparse"), batch_size, seed, False)
    final = output / "final.keras"
    fit_skipped_existing_complete_run = bool(resume and initial_epoch >= epochs)
    if fit_skipped_existing_complete_run:
        if not final.is_file() or not best.is_file():
            raise RuntimeError("VNEXT_RESUME_COMPLETE_RUN_MISSING_FINAL_OR_BEST")
        # A prior invocation can finish model.fit() and save final.keras before a
        # post-fit validation error. Preserve that restored-best final model and
        # finish only the validation/result-writing steps; do not train again.
        model = tf.keras.models.load_model(final, safe_mode=True)
    else:
        callbacks = [
            tf.keras.callbacks.ModelCheckpoint(
                str(best), monitor="val_loss", mode="min", save_best_only=True
            ),
            tf.keras.callbacks.ModelCheckpoint(str(latest)),
            tf.keras.callbacks.CSVLogger(str(history), append=resume),
        ]
        if not smoke:
            callbacks.append(
                tf.keras.callbacks.EarlyStopping(
                    monitor="val_loss",
                    mode="min",
                    patience=int(config["training"]["early_stop_patience"]),
                    restore_best_weights=True,
                )
            )
        model.fit(
            train_ds,
            validation_data=dev_ds,
            initial_epoch=initial_epoch,
            epochs=max(epochs, initial_epoch + (1 if smoke else 0)),
            callbacks=callbacks,
            verbose=2,
            shuffle=False,
        )
        model.save(final)
    # EarlyStopping(restore_best_weights=True) intentionally makes the in-memory
    # model differ from latest.keras whenever the final epoch is not the best
    # epoch. final.keras is the serialization of this exact post-fit model and is
    # therefore the correct save/reload round-trip target.
    reloaded = tf.keras.models.load_model(final, safe_mode=True)
    (sample_inputs, _) = next(iter(make_dataset(dev_rows[:1], ("dense",), 1, seed, False)))
    before = np.asarray(model(sample_inputs, training=False))
    after = np.asarray(reloaded(sample_inputs, training=False))
    reload_max_abs = float(np.max(np.abs(before - after)))
    with history.open("r", encoding="utf-8", newline="") as stream:
        history_rows = list(csv.DictReader(stream))
    metric_values = [
        float(value)
        for row in history_rows
        for key, value in row.items()
        if key != "epoch" and value not in (None, "")
    ]
    finite_losses = bool(history_rows) and bool(metric_values) and bool(
        np.all(np.isfinite(np.asarray(metric_values, np.float64)))
    )
    if not finite_losses or reload_max_abs > 1e-6:
        raise RuntimeError(
            f"VNEXT_TRAIN_SANITY_FAILURE:finite={finite_losses}:reload={reload_max_abs}"
        )
    result = {
        "schema": "APPHEAR_VNEXT_TRAIN_RESULT_V1",
        "milestone": MILESTONE,
        "status": "PASS",
        "smoke": smoke,
        "architecture": "one established 4x64 mask-aware causal TCN",
        "classes": 236,
        "train_clips": len(train_rows),
        "dev_clips": len(dev_rows),
        "train_examples_per_epoch": len(train_rows) * 2,
        "dev_examples": len(dev_rows) * 2,
        "parameter_count": model.count_params(),
        "finite_loss_and_metrics": finite_losses,
        "checkpoint_reload_max_abs": reload_max_abs,
        "checkpoint_reload_target": "final.keras",
        "fit_skipped_existing_complete_run": fit_skipped_existing_complete_run,
        "config_sha256": sha256(config_path),
        "dataset_contract_sha256": sha256(dataset / "contract.json"),
        "best_checkpoint": str(best.resolve()),
        "latest_checkpoint": str(latest.resolve()),
        "final_checkpoint": str(final.resolve()),
        "protected_test_accessed": False,
        "recognition_accuracy_claim": False if smoke else "DEV_EVALUATION_REQUIRED",
    }
    write_json(output / ("tiny_training_sanity.json" if smoke else "training_result.json"), result)
    return result


def create_synthetic_training_smoke_dataset(output: Path, seed: int = 101) -> dict[str, Any]:
    """Create shape-only fixtures; these are never eligible recognition evidence."""

    rng = np.random.default_rng(seed)
    output.mkdir(parents=True, exist_ok=True)
    write_json(
        output / "contract.json",
        {
            "milestone": MILESTONE,
            "raw_schema": RAW_SCHEMA,
            "feature_schema": FEATURE_SCHEMA,
            "feature_width": FEATURE_WIDTH,
            "max_sequence_length": MAX_SEQUENCE_LENGTH,
            "synthetic_contract_smoke": True,
            "recognition_accuracy_claim": False,
            "protected_test_accessed": False,
        },
    )
    index_rows = []
    for split in ("train", "dev"):
        for sample in range(4):
            class_id = sample
            sample_id = f"synthetic:{split}:{sample}"
            path = output / "features" / split / f"sample_{sample}.npz"
            path.parent.mkdir(parents=True, exist_ok=True)
            real_length = 12 + sample
            dense = np.zeros((MAX_SEQUENCE_LENGTH, FEATURE_WIDTH), np.float32)
            sparse = np.zeros_like(dense)
            dense[:real_length] = rng.normal(0, 0.2, (real_length, FEATURE_WIDTH))
            sparse_length = max(3, real_length // 3)
            sparse[:sparse_length] = dense[
                np.linspace(0, real_length - 1, sparse_length).astype(int)
            ]
            dense_mask = np.arange(MAX_SEQUENCE_LENGTH) < real_length
            sparse_mask = np.arange(MAX_SEQUENCE_LENGTH) < sparse_length
            metadata = {
                "schema": FEATURE_SCHEMA,
                "sample_id": sample_id,
                "split": split,
                "class_id": class_id,
                "canonical_gloss": f"SYNTHETIC_{class_id}",
                "signer_id": f"synthetic_{split}_{sample}",
                "source_id": "SYNTHETIC_CONTRACT_SMOKE",
                "duration_ms": 500.0 + sample * 50.0,
                "duration_scope": "synthetic",
                "timestamp_sources": ["SYNTHETIC"],
            }
            np.savez_compressed(
                path,
                metadata_json=np.asarray(json.dumps(metadata, sort_keys=True)),
                dense_features=dense,
                dense_mask=dense_mask,
                sparse_features=sparse,
                sparse_mask=sparse_mask,
            )
            index_rows.append(
                {
                    "sample_id": sample_id,
                    "split": split,
                    "class_id": class_id,
                    "canonical_gloss": metadata["canonical_gloss"],
                    "signer_id": metadata["signer_id"],
                    "source_id": metadata["source_id"],
                    "feature_path": str(path.resolve()),
                }
            )
    with (output / "index.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for row in index_rows:
            stream.write(json.dumps(row, separators=(",", ":")) + "\n")
    return {
        "status": "PASS",
        "synthetic_contract_smoke": True,
        "samples": len(index_rows),
        "recognition_accuracy_claim": False,
    }


def run_training_smoke(output: Path, config: Path) -> dict[str, Any]:
    dataset = output / "synthetic_dataset"
    run = output / "run"
    fixture = create_synthetic_training_smoke_dataset(dataset)
    training = train_model(dataset, run, config, resume=False, smoke=True)
    evaluation = evaluate_model(
        dataset,
        run / "best.keras",
        run / "synthetic_metrics_smoke.json",
        batch_size=4,
    )
    result = {
        "schema": "APPHEAR_VNEXT_TINY_TRAINING_SANITY_V1",
        "status": "PASS",
        "fixture": fixture,
        "training": training,
        "evaluation_pipeline_status": evaluation["status"],
        "checkpoint_reload_max_abs": training["checkpoint_reload_max_abs"],
        "synthetic_contract_smoke": True,
        "recognition_accuracy_claim": False,
        "protected_test_accessed": False,
    }
    write_json(output / "tiny_training_sanity.json", result)
    return result


def _predict_condition(
    model: Any,
    rows: list[dict[str, Any]],
    condition: str,
    batch_size: int,
) -> dict[str, Any]:
    labels: list[int] = []
    predictions: list[int] = []
    top5_correct: list[bool] = []
    records: list[dict[str, Any]] = []
    for start in range(0, len(rows), batch_size):
        batch_rows = rows[start : start + batch_size]
        features = []
        masks = []
        metadata_rows = []
        for row in batch_rows:
            with np.load(Path(row["feature_path"]), allow_pickle=False) as data:
                prefix = "dense" if condition == "dense" else "sparse"
                features.append(np.asarray(data[f"{prefix}_features"], np.float32))
                masks.append(np.asarray(data[f"{prefix}_mask"], bool))
                metadata_rows.append(json.loads(str(data["metadata_json"].item())))
        probabilities = np.asarray(
            model([np.stack(features), np.stack(masks)], training=False), np.float32
        )
        for row, metadata, probability in zip(
            batch_rows, metadata_rows, probabilities, strict=True
        ):
            label = int(row["class_id"])
            prediction = int(np.argmax(probability))
            top5 = np.argpartition(probability, -5)[-5:]
            labels.append(label)
            predictions.append(prediction)
            top5_correct.append(label in top5)
            records.append(
                {
                    "sample_id": row["sample_id"],
                    "label": label,
                    "prediction": prediction,
                    "correct": prediction == label,
                    "top5_correct": label in top5,
                    "signer_id": row["signer_id"],
                    "source_id": row["source_id"],
                    "duration_ms": metadata["duration_ms"],
                    "duration_scope": metadata["duration_scope"],
                    "timestamp_sources": metadata["timestamp_sources"],
                }
            )
    return {
        "labels": np.asarray(labels, np.int32),
        "predictions": np.asarray(predictions, np.int32),
        "top5_correct": np.asarray(top5_correct, bool),
        "records": records,
    }


def _classification_metrics(result: dict[str, Any]) -> dict[str, Any]:
    vocabulary = json.loads(VOCAB_MANIFEST.read_text(encoding="utf-8-sig"))
    gloss_by_id = {int(class_id): gloss for gloss, class_id in vocabulary.items()}
    labels = result["labels"]
    predictions = result["predictions"]
    matrix = np.zeros((236, 236), np.int64)
    np.add.at(matrix, (labels, predictions), 1)
    support = matrix.sum(axis=1)
    predicted = matrix.sum(axis=0)
    tp = np.diag(matrix)
    recall = np.divide(tp, support, out=np.zeros(236), where=support > 0)
    precision = np.divide(tp, predicted, out=np.zeros(236), where=predicted > 0)
    f1 = np.divide(
        2 * precision * recall,
        precision + recall,
        out=np.zeros(236),
        where=(precision + recall) > 0,
    )
    off_diagonal = matrix.copy()
    np.fill_diagonal(off_diagonal, 0)
    pairs = []
    for flat in np.argsort(off_diagonal, axis=None)[::-1][:30]:
        actual, predicted_class = np.unravel_index(flat, off_diagonal.shape)
        count = int(off_diagonal[actual, predicted_class])
        if count == 0:
            break
        pairs.append(
            {
                "actual": int(actual),
                "actual_gloss": gloss_by_id[int(actual)],
                "predicted": int(predicted_class),
                "predicted_gloss": gloss_by_id[int(predicted_class)],
                "count": count,
            }
        )

    def grouped(key: str) -> dict[str, Any]:
        groups: defaultdict[str, list[bool]] = defaultdict(list)
        for record in result["records"]:
            groups[str(record[key])].append(bool(record["correct"]))
        return {
            name: {"clips": len(values), "top1": float(np.mean(values))}
            for name, values in sorted(groups.items())
        }

    return {
        "clips": len(labels),
        "top1": float(np.mean(labels == predictions)),
        "top5": float(np.mean(result["top5_correct"])),
        "macro_f1": float(np.mean(f1)),
        "per_class": [
            {
                "class_id": class_id,
                "canonical_gloss": gloss_by_id[class_id],
                "support": int(support[class_id]),
                "precision": float(precision[class_id]),
                "recall": float(recall[class_id]),
                "f1": float(f1[class_id]),
            }
            for class_id in range(236)
        ],
        "zero_recall_classes": [
            {"class_id": int(value), "canonical_gloss": gloss_by_id[int(value)]}
            for value in np.flatnonzero(recall == 0)
        ],
        "confusion_matrix": matrix.tolist(),
        "largest_confusion_pairs": pairs,
        "by_signer": grouped("signer_id"),
        "by_source": grouped("source_id"),
    }


def evaluate_model(
    dataset: Path,
    checkpoint: Path,
    output: Path,
    batch_size: int,
) -> dict[str, Any]:
    import tensorflow as tf

    rows = load_index(dataset)
    split_rows = {
        split: [row for row in rows if row["split"] == split] for split in ("train", "dev")
    }
    if not all(split_rows.values()):
        raise RuntimeError("VNEXT_EVAL_SPLITS_MISSING")
    model = tf.keras.models.load_model(checkpoint, safe_mode=True)
    details: dict[str, Any] = {}
    raw_results: dict[tuple[str, str], dict[str, Any]] = {}
    for split, values in split_rows.items():
        details[split] = {}
        for condition in ("dense", "phone_01_sparse"):
            raw = _predict_condition(model, values, condition, batch_size)
            raw_results[(split, condition)] = raw
            details[split][condition] = _classification_metrics(raw)
    comparisons = {}
    for split in ("train", "dev"):
        dense = raw_results[(split, "dense")]
        sparse = raw_results[(split, "phone_01_sparse")]
        if not np.array_equal(dense["labels"], sparse["labels"]):
            raise RuntimeError("VNEXT_EVAL_PAIRED_IDENTITY")
        dense_correct = dense["labels"] == dense["predictions"]
        sparse_correct = sparse["labels"] == sparse["predictions"]
        comparisons[split] = {
            "dense_minus_sparse_top1": float(dense_correct.mean() - sparse_correct.mean()),
            "dense_correct_sparse_wrong": int(np.count_nonzero(dense_correct & ~sparse_correct)),
            "sparse_correct_dense_wrong": int(np.count_nonzero(~dense_correct & sparse_correct)),
            "paired_clips": len(dense_correct),
        }
    gaps = {
        condition: float(details["train"][condition]["top1"] - details["dev"][condition]["top1"])
        for condition in ("dense", "phone_01_sparse")
    }
    duration_analysis: dict[str, Any] = {}
    for condition in ("dense", "phone_01_sparse"):
        records = [
            row
            for row in raw_results[("dev", condition)]["records"]
            if row["duration_scope"] == "governed_span"
            and np.isfinite(float(row["duration_ms"]))
            and float(row["duration_ms"]) > 0
        ]
        if len(records) < 100:
            duration_analysis[condition] = {
                "status": "UNAVAILABLE",
                "reason": "fewer than 100 DEV clips have governed-span duration metadata",
                "clips": len(records),
            }
            continue
        durations = np.asarray([row["duration_ms"] for row in records], np.float64)
        edges = np.quantile(durations, [0.0, 0.25, 0.5, 0.75, 1.0])
        bins = []
        for index in range(4):
            lower, upper = edges[index], edges[index + 1]
            selected = [
                row
                for row in records
                if float(row["duration_ms"]) >= lower
                and (
                    float(row["duration_ms"]) <= upper
                    if index == 3
                    else float(row["duration_ms"]) < upper
                )
            ]
            bins.append(
                {
                    "lower_ms": float(lower),
                    "upper_ms": float(upper),
                    "clips": len(selected),
                    "top1": float(np.mean([row["correct"] for row in selected]))
                    if selected
                    else None,
                }
            )
        duration_analysis[condition] = {
            "status": "AVAILABLE_GOVERNED_SPANS_ONLY",
            "clips": len(records),
            "quartile_bins": bins,
        }
    dataset_contract = json.loads((dataset / "contract.json").read_text(encoding="utf-8"))
    synthetic_smoke = bool(dataset_contract.get("synthetic_contract_smoke", False))
    result = {
        "schema": "APPHEAR_VNEXT_236_EVALUATION_V1",
        "milestone": MILESTONE,
        "status": "PASS",
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": sha256(checkpoint),
        "feature_schema": FEATURE_SCHEMA,
        "details": details,
        "dense_sparse_paired_comparison": comparisons,
        "train_minus_dev_top1_gap": gaps,
        "duration_analysis": duration_analysis,
        "milestone_interpretation": (
            "NOT_APPLICABLE_SYNTHETIC_SMOKE"
            if synthetic_smoke
            else "WAIT_FOR_PROJECT_LEAD_EVIDENCE_CLASSIFICATION"
        ),
        "interpretation_note": (
            "No arbitrary utility threshold is encoded. Use matched dense/sparse and TRAIN/DEV "
            "evidence to classify UTILITY_SUPPORTED, UTILITY_CADENCE_LIMITED, "
            "UTILITY_REPRESENTATION_LIMITED, or GENERALIZATION_LIMITED."
        ),
        "protected_test_accessed": False,
        "synthetic_contract_smoke": synthetic_smoke,
        "recognition_accuracy_claim": not synthetic_smoke,
    }
    write_json(output, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit-data")
    audit.add_argument("--output", type=Path, default=DEFAULT_OUTPUT / "governance_audit.json")
    parity_prepare = commands.add_parser("prepare-parity")
    parity_prepare.add_argument("--output", type=Path, default=DEFAULT_OUTPUT / "parity_fixture")
    parity = commands.add_parser("offline-parity")
    parity.add_argument("--fixture-root", type=Path, default=DEFAULT_OUTPUT / "parity_fixture")
    parity.add_argument(
        "--android-jsonl",
        type=Path,
        default=DEFAULT_OUTPUT / "parity_fixture/android_raw_frames.jsonl",
    )
    parity.add_argument("--output", type=Path, default=DEFAULT_OUTPUT / "parity_result.json")
    extract = commands.add_parser("extract")
    extract.add_argument("--output", type=Path, default=DEFAULT_DATASET)
    extract.add_argument("--splits", nargs="+", choices=("train", "dev"), default=["train", "dev"])
    extract.add_argument("--resume", action="store_true")
    extract.add_argument("--limit-per-split", type=int)
    train = commands.add_parser("train")
    train.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    train.add_argument("--output", type=Path, default=DEFAULT_RUN)
    train.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    train.add_argument("--resume", action="store_true")
    train.add_argument("--smoke", action="store_true")
    training_smoke = commands.add_parser("training-smoke")
    training_smoke.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT / "tiny_training_sanity"
    )
    training_smoke.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    evaluate.add_argument("--checkpoint", type=Path, default=DEFAULT_RUN / "best.keras")
    evaluate.add_argument("--output", type=Path, default=DEFAULT_RUN / "evaluation.json")
    evaluate.add_argument("--batch-size", type=int, default=32)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "audit-data":
        result = audit_data(args.output)
    elif args.command == "prepare-parity":
        result = prepare_parity(args.output)
    elif args.command == "offline-parity":
        result = offline_parity(args.fixture_root, args.android_jsonl, args.output)
    elif args.command == "extract":
        if args.limit_per_split is not None and args.limit_per_split not in range(1, 17):
            raise RuntimeError("VNEXT_SMOKE_LIMIT_MUST_BE_1_TO_16")
        result = extract_dataset(
            args.output,
            args.splits,
            resume=args.resume,
            limit_per_split=args.limit_per_split,
        )
    elif args.command == "train":
        result = train_model(
            args.dataset,
            args.output,
            args.config,
            resume=args.resume,
            smoke=args.smoke,
        )
    elif args.command == "training-smoke":
        result = run_training_smoke(args.output, args.config)
    elif args.command == "evaluate":
        result = evaluate_model(args.dataset, args.checkpoint, args.output, args.batch_size)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
