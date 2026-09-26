"""Bounded Phase 5.1T-3 first class-agnostic causal segmenter experiment.

This utility is intentionally narrow: it accepts only the frozen Phase 5.1T-2
population, extracts full source videos through frozen Candidate01, creates one
fixed label policy, trains one small causal TCN, and evaluates the frozen
signer-disjoint DEV split.  It never imports recognition-v2 or a recognizer.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.perception_vnext.offline_candidate01 import (  # noqa: E402
    Candidate01Offline,
    extract_video,
)
from pipeline.perception_vnext.recognition_schema import (  # noqa: E402
    RAW_SCHEMA,
    RawSequence,
    load_raw_sequence,
    save_raw_sequence,
)
from pipeline.perception_vnext.segmentation.learned_features import (  # noqa: E402
    FEATURE_BLOCKS,
    FEATURE_WIDTH,
    SEGMENTATION_FEATURE_SCHEMA,
    apply_normalization,
    derive_causal_segmentation_features,
    feature_names,
    normalization_from_train,
)

MILESTONE = "PHASE_5_1T_3_FIRST_CLASS_AGNOSTIC_SEGMENTER_01"
T2 = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "phase5_1t_2_bounded_segmentation_seed_dataset_01"
)
OUT = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "phase5_1t_3_first_class_agnostic_segmenter_01"
)
SELECTED = T2 / "selected_120_manifest.json"
SPLIT = T2 / "frozen_segmentation_split.json"
ANNOTATIONS = T2 / "segmentation_human_annotations.json"
CONFIG = OUT / "training_config.json"
LEGACY_RAW_TRAIN = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/dataset/raw/train"
)
EXPECTED_SELECTED_SHA = "832ba25420bef80acda3b40e7a44414654c3227222e4336d66174b8cca7ea15e"
EXPECTED_SPLIT_SHA = "b4a2dbaf9c3810a86f8407068ea50dfc3f2079fc951932ff3a76bbe411b599c6"
LABEL_NAMES = ("PRE_IDLE", "ACTIVE_SIGN", "POST_RECOVERY")
IGNORE_LABEL = -1


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def stable_name(sample_id: str) -> str:
    return hashlib.sha256(sample_id.encode("utf-8")).hexdigest()[:24]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def load_config() -> dict[str, Any]:
    config = read_json(CONFIG)
    if config.get("milestone") != MILESTONE:
        raise RuntimeError("TRAINING_CONFIG_MILESTONE_MISMATCH")
    if config["features"]["schema"] != SEGMENTATION_FEATURE_SCHEMA:
        raise RuntimeError("TRAINING_CONFIG_FEATURE_SCHEMA_MISMATCH")
    if int(config["features"]["width"]) != FEATURE_WIDTH:
        raise RuntimeError("TRAINING_CONFIG_FEATURE_WIDTH_MISMATCH")
    return config


def load_population() -> list[dict[str, Any]]:
    if sha256(SELECTED) != EXPECTED_SELECTED_SHA:
        raise RuntimeError("FROZEN_SELECTED_MANIFEST_IDENTITY_MISMATCH")
    if sha256(SPLIT) != EXPECTED_SPLIT_SHA:
        raise RuntimeError("FROZEN_SEGMENTATION_SPLIT_IDENTITY_MISMATCH")
    selected = read_json(SELECTED)
    split = read_json(SPLIT)
    annotations = read_json(ANNOTATIONS)
    rows = list(selected["rows"])
    if len(rows) != 120 or int(selected["sample_count"]) != 120:
        raise RuntimeError("FROZEN_SELECTED_COUNT_MISMATCH")
    if len({str(row["sample_id"]) for row in rows}) != len(rows):
        raise RuntimeError("DUPLICATE_FROZEN_SAMPLE")
    annotation_by_id = {str(row["sample_id"]): row for row in annotations["annotations"]}
    if len(annotation_by_id) != 120 or annotations.get("status") != "FINALIZED":
        raise RuntimeError("FROZEN_ANNOTATION_PACKAGE_INCOMPLETE")
    train_ids = set(map(str, split["train_sample_ids"]))
    dev_ids = set(map(str, split["dev_sample_ids"]))
    if train_ids & dev_ids or len(train_ids) != 96 or len(dev_ids) != 24:
        raise RuntimeError("FROZEN_SPLIT_INVALID")
    merged: list[dict[str, Any]] = []
    for row in rows:
        sample_id = str(row["sample_id"])
        annotation = annotation_by_id[sample_id]
        expected_split = "SEGMENTATION_TRAIN" if sample_id in train_ids else "SEGMENTATION_DEV"
        if sample_id not in train_ids | dev_ids or row["segmentation_split"] != expected_split:
            raise RuntimeError(f"FROZEN_SPLIT_ROW_MISMATCH:{sample_id}")
        if annotation["segmentation_split"] != expected_split:
            raise RuntimeError(f"FROZEN_ANNOTATION_SPLIT_MISMATCH:{sample_id}")
        value = dict(row)
        value.update(
            {
                "human_sign_start_ms": annotation.get("human_sign_start_ms"),
                "human_sign_end_ms": annotation.get("human_sign_end_ms"),
                "ambiguous_or_unusable": bool(annotation["ambiguous_or_unusable"]),
                "annotation_reused_from_phase5_1t_1": bool(
                    annotation["annotation_reused_from_phase5_1t_1"]
                ),
            }
        )
        merged.append(value)
    usable = [row for row in merged if not row["ambiguous_or_unusable"]]
    counts = Counter(row["segmentation_split"] for row in usable)
    if counts != {"SEGMENTATION_TRAIN": 89, "SEGMENTATION_DEV": 23}:
        raise RuntimeError(f"FROZEN_USABLE_COUNTS_MISMATCH:{dict(counts)}")
    train_signers = {
        row["signer_id"] for row in usable if row["segmentation_split"] == "SEGMENTATION_TRAIN"
    }
    dev_signers = {
        row["signer_id"] for row in usable if row["segmentation_split"] == "SEGMENTATION_DEV"
    }
    if train_signers & dev_signers:
        raise RuntimeError("SEGMENTATION_SIGNER_LEAKAGE")
    return usable


def video_metadata(path: Path) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"FULL_VIDEO_OPEN_FAILED:{path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
    capture.release()
    if not np.isfinite(fps) or fps <= 0 or frame_count <= 0:
        raise RuntimeError(f"FULL_VIDEO_METADATA_INVALID:{path}")
    return {
        "fps": fps,
        "frame_count": frame_count,
        "duration_from_frames_ms": frame_count * 1000.0 / fps,
    }


def verify_full_video(
    raw: RawSequence, metadata: dict[str, Any], expected_sha: str
) -> dict[str, Any]:
    raw.validate()
    meta = raw.metadata
    if meta.get("schema") != RAW_SCHEMA:
        raise RuntimeError("FULL_VIDEO_RAW_SCHEMA_MISMATCH")
    if meta.get("duration_scope") != "whole_isolated_clip":
        raise RuntimeError("FULL_VIDEO_SCOPE_IS_CROPPED")
    if meta.get("span_start_inclusive") != 0 or meta.get("span_end_inclusive") is not None:
        raise RuntimeError("FULL_VIDEO_SPAN_CONTAMINATION")
    if str(meta.get("source_video_sha256", "")).lower() != expected_sha.lower():
        raise RuntimeError("FULL_VIDEO_SOURCE_HASH_MISMATCH")
    expected_frames = int(metadata["frame_count"])
    if len(raw.frame_index) != expected_frames or int(raw.frame_index[0]) != 0:
        raise RuntimeError(
            f"FULL_VIDEO_FRAME_COVERAGE_MISMATCH:{len(raw.frame_index)}:{expected_frames}"
        )
    frame_ms = 1000.0 / float(metadata["fps"])
    start_ok = float(raw.timestamp_ms[0]) <= max(80.0, 1.5 * frame_ms)
    end_covered_ms = float(raw.timestamp_ms[-1]) + frame_ms
    required_end_ms = float(metadata["duration_from_frames_ms"]) - max(80.0, frame_ms)
    if not start_ok or end_covered_ms < required_end_ms:
        raise RuntimeError("FULL_VIDEO_TIMESTAMP_COVERAGE_MISMATCH")
    return {
        "raw_observations": len(raw.timestamp_ms),
        "first_frame_index": int(raw.frame_index[0]),
        "last_frame_index": int(raw.frame_index[-1]),
        "first_timestamp_ms": float(raw.timestamp_ms[0]),
        "last_timestamp_ms": float(raw.timestamp_ms[-1]),
        "expected_video_frames": expected_frames,
        "native_fps": float(metadata["fps"]),
        "duration_from_frames_ms": float(metadata["duration_from_frames_ms"]),
        "scope": "FULL_SOURCE_VIDEO",
        "span_used": False,
    }


def _candidate_row(row: dict[str, Any], video_sha: str) -> dict[str, str]:
    return {
        "raw_video_path": str(row["source_video_path"]),
        "raw_video_sha256": video_sha,
        "span_path": "",
        "sample_id": str(row["sample_id"]),
        "split": str(row["segmentation_split"]),
        "class_id": str(row["class_id"]),
        "canonical_gloss": str(row["gloss"]),
        "signer_group_id": str(row["signer_id"]),
        "source_dataset": str(row["source"]),
    }


def extract_full_video_features() -> dict[str, Any]:
    rows = load_population()
    config = load_config()
    raw_dir = OUT / "raw_full_video"
    feature_dir = OUT / "features"
    raw_dir.mkdir(parents=True, exist_ok=True)
    feature_dir.mkdir(parents=True, exist_ok=True)
    pending: list[tuple[dict[str, Any], str, dict[str, Any], Path]] = []
    completed: list[dict[str, Any]] = []

    def finalize_raw(
        row: dict[str, Any],
        raw: RawSequence,
        source_sha: str,
        metadata: dict[str, Any],
        raw_path: Path,
        origin: str,
    ) -> None:
        proof = verify_full_video(raw, metadata, source_sha)
        features = derive_causal_segmentation_features(raw)
        feature_path = feature_dir / f"{stable_name(str(row['sample_id']))}.npz"
        np.savez_compressed(
            feature_path,
            schema=np.asarray(SEGMENTATION_FEATURE_SCHEMA),
            sample_id=np.asarray(str(row["sample_id"])),
            timestamps_ms=raw.timestamp_ms.astype(np.float64),
            features=features,
            raw_sha256=np.asarray(sha256(raw_path)),
        )
        completed.append(
            {
                "sample_id": row["sample_id"],
                "source": row["source"],
                "signer_id": row["signer_id"],
                "gloss": row["gloss"],
                "segmentation_split": row["segmentation_split"],
                "source_video_path": str(Path(row["source_video_path"]).resolve()),
                "source_video_sha256": source_sha,
                "source_video_duration_ms": float(row["video_duration_ms"]),
                "raw_path": str(raw_path.resolve()),
                "raw_sha256": sha256(raw_path),
                "feature_path": str(feature_path.resolve()),
                "feature_sha256": sha256(feature_path),
                "feature_schema": SEGMENTATION_FEATURE_SCHEMA,
                "feature_width": FEATURE_WIDTH,
                "raw_origin": origin,
                "full_video_verification": proof,
                "human_timestamps_used_for_extraction": False,
            }
        )

    for index, row in enumerate(rows, start=1):
        video = Path(row["source_video_path"])
        if not video.is_file():
            raise RuntimeError(f"USABLE_SOURCE_VIDEO_MISSING:{row['sample_id']}")
        source_sha = sha256(video)
        metadata = video_metadata(video)
        output_raw = raw_dir / f"{stable_name(str(row['sample_id']))}.npz"
        candidates = [output_raw, LEGACY_RAW_TRAIN / output_raw.name]
        reused = False
        for candidate in candidates:
            if not candidate.is_file():
                continue
            try:
                raw = load_raw_sequence(candidate)
                verify_full_video(raw, metadata, source_sha)
            except (ValueError, RuntimeError, KeyError):
                continue
            if candidate != output_raw:
                shutil.copyfile(candidate, output_raw)
                raw = load_raw_sequence(output_raw)
                origin = "VERIFIED_EXISTING_CANDIDATE01_WHOLE_CLIP_COPY"
            else:
                origin = "PHASE5_1T_3_RESUME_FULL_VIDEO"
            finalize_raw(row, raw, source_sha, metadata, output_raw, origin)
            reused = True
            print(
                f"[{index:03d}/{len(rows)}] full-video verified/reused {row['sample_id']}",
                flush=True,
            )
            break
        if not reused:
            pending.append((row, source_sha, metadata, output_raw))

    if pending:
        print(f"Candidate01 full-video extraction required for {len(pending)} clips", flush=True)
        with Candidate01Offline() as runtime:
            for offset, (row, source_sha, metadata, output_raw) in enumerate(pending, start=1):
                raw = extract_video(runtime, _candidate_row(row, source_sha))
                save_raw_sequence(output_raw, raw)
                finalize_raw(
                    row,
                    raw,
                    source_sha,
                    metadata,
                    output_raw,
                    "NEW_FROZEN_CANDIDATE01_FULL_VIDEO_EXTRACTION",
                )
                print(
                    f"[new {offset:03d}/{len(pending)}] extracted {row['sample_id']} "
                    f"({len(raw.timestamp_ms)} observations)",
                    flush=True,
                )
    order = {str(row["sample_id"]): index for index, row in enumerate(rows)}
    completed.sort(key=lambda row: order[str(row["sample_id"])])
    result = {
        "schema": "apphear.phase5_1t.extracted_feature_manifest.v1",
        "milestone": MILESTONE,
        "generated_at_utc": utc_now(),
        "selected_manifest_sha256": EXPECTED_SELECTED_SHA,
        "segmentation_split_sha256": EXPECTED_SPLIT_SHA,
        "raw_schema": RAW_SCHEMA,
        "feature_schema": SEGMENTATION_FEATURE_SCHEMA,
        "feature_width": FEATURE_WIDTH,
        "sample_count": len(completed),
        "train_count": sum(row["segmentation_split"] == "SEGMENTATION_TRAIN" for row in completed),
        "dev_count": sum(row["segmentation_split"] == "SEGMENTATION_DEV" for row in completed),
        "full_source_video_count": sum(
            row["full_video_verification"]["scope"] == "FULL_SOURCE_VIDEO" for row in completed
        ),
        "governed_or_human_span_used_for_extraction": False,
        "rows": completed,
    }
    if result["sample_count"] != 112 or result["full_source_video_count"] != 112:
        raise RuntimeError("FULL_VIDEO_EXTRACTION_POPULATION_INCOMPLETE")
    write_json(OUT / "extracted_feature_manifest.json", result)
    write_feature_schema(config)
    generate_labels(rows, completed, config)
    return result


def write_feature_schema(config: dict[str, Any]) -> None:
    value = {
        "schema": SEGMENTATION_FEATURE_SCHEMA,
        "raw_schema": RAW_SCHEMA,
        "width": FEATURE_WIDTH,
        "dtype": "float32",
        "time_axis": "strictly chronological actual Candidate01 source timestamps",
        "causality": "current observation plus one backward transition only",
        "missingness": "zero numeric value plus explicit validity; no interpolation or carry",
        "coordinate_space": "source-image normalized XY; deltas in the same space",
        "normalization": "per-dimension z-score computed from usable SEGMENTATION_TRAIN only",
        "forbidden_inputs": [
            "RGB",
            "Recognition V2",
            "recognizer outputs",
            "gloss",
            "class_id",
            "future observations",
            "D1 boundaries",
            "human boundaries as features or extraction controls",
        ],
        "blocks": [block.__dict__ for block in FEATURE_BLOCKS],
        "feature_names": feature_names(),
        "config_identity_sha256": sha256(CONFIG),
        "model_contract": config["model"],
    }
    write_json(OUT / "feature_schema.json", value)


def temporal_labels(
    timestamps_ms: np.ndarray,
    start_ms: float,
    end_ms: float,
    ignore_band_ms: float,
) -> np.ndarray:
    timestamps = np.asarray(timestamps_ms, np.float64)
    if not (0.0 <= start_ms < end_ms) or ignore_band_ms < 0:
        raise ValueError("INVALID_HUMAN_BOUNDARY_OR_IGNORE_BAND")
    labels = np.full(len(timestamps), IGNORE_LABEL, np.int8)
    labels[timestamps < start_ms - ignore_band_ms] = 0
    labels[(timestamps > start_ms + ignore_band_ms) & (timestamps < end_ms - ignore_band_ms)] = 1
    labels[timestamps > end_ms + ignore_band_ms] = 2
    return labels


def generate_labels(
    population: list[dict[str, Any]],
    extracted: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    by_id = {str(row["sample_id"]): row for row in extracted}
    band = float(config["labels"]["ignore_band_ms"])
    samples: list[dict[str, Any]] = []
    totals: defaultdict[str, Counter[int]] = defaultdict(Counter)
    for row in population:
        manifest_row = by_id[str(row["sample_id"])]
        with np.load(manifest_row["feature_path"], allow_pickle=False) as data:
            timestamps = np.asarray(data["timestamps_ms"], np.float64)
        labels = temporal_labels(
            timestamps,
            float(row["human_sign_start_ms"]),
            float(row["human_sign_end_ms"]),
            band,
        )
        counts = Counter(map(int, labels))
        totals[str(row["segmentation_split"])].update(counts)
        samples.append(
            {
                "sample_id": row["sample_id"],
                "segmentation_split": row["segmentation_split"],
                "human_sign_start_ms": float(row["human_sign_start_ms"]),
                "human_sign_end_ms": float(row["human_sign_end_ms"]),
                "timestamps_ms": timestamps.tolist(),
                "labels": labels.astype(int).tolist(),
                "counts": {
                    LABEL_NAMES[key] if key >= 0 else "IGNORED": counts[key]
                    for key in (-1, 0, 1, 2)
                },
            }
        )
    result = {
        "schema": "apphear.phase5_1t.temporal_labels.v1",
        "milestone": MILESTONE,
        "ignore_band_ms": band,
        "human_timestamps_are_labels_only": True,
        "class_map": {str(index): name for index, name in enumerate(LABEL_NAMES)},
        "ignore_label": IGNORE_LABEL,
        "totals": {
            split: {
                LABEL_NAMES[key] if key >= 0 else "IGNORED": counter[key] for key in (-1, 0, 1, 2)
            }
            for split, counter in totals.items()
        },
        "samples": samples,
    }
    if any(sample["counts"]["ACTIVE_SIGN"] == 0 for sample in samples):
        raise RuntimeError("USABLE_SAMPLE_HAS_NO_ACTIVE_SUPERVISION")
    write_json(OUT / "generated_temporal_labels.json", result)
    return result


def load_training_arrays() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    population = load_population()
    manifest = read_json(OUT / "extracted_feature_manifest.json")
    labels = read_json(OUT / "generated_temporal_labels.json")
    manifest_by_id = {str(row["sample_id"]): row for row in manifest["rows"]}
    labels_by_id = {str(row["sample_id"]): row for row in labels["samples"]}
    result: list[dict[str, Any]] = []
    for row in population:
        sample_id = str(row["sample_id"])
        feature_row = manifest_by_id[sample_id]
        with np.load(feature_row["feature_path"], allow_pickle=False) as data:
            if str(data["schema"].item()) != SEGMENTATION_FEATURE_SCHEMA:
                raise RuntimeError("SAVED_FEATURE_SCHEMA_MISMATCH")
            timestamps = np.asarray(data["timestamps_ms"], np.float64)
            features = np.asarray(data["features"], np.float32)
        target = np.asarray(labels_by_id[sample_id]["labels"], np.int32)
        if len(target) != len(timestamps) or features.shape != (len(timestamps), FEATURE_WIDTH):
            raise RuntimeError(f"FEATURE_LABEL_ALIGNMENT_MISMATCH:{sample_id}")
        value = dict(row)
        value.update({"timestamps_ms": timestamps, "features": features, "labels": target})
        result.append(value)
    return result, manifest, labels


def build_model(config: dict[str, Any]) -> Any:
    import tensorflow as tf

    model_config = config["model"]
    inputs = tf.keras.Input(shape=(None, FEATURE_WIDTH), dtype=tf.float32, name="raw_v1_features")
    x = tf.keras.layers.Dense(
        int(model_config["input_projection_channels"]), name="input_projection"
    )(inputs)
    for index, dilation in enumerate(model_config["dilations"]):
        residual = x
        y = tf.keras.layers.LayerNormalization(name=f"block_{index}_norm")(x)
        y = tf.keras.layers.Conv1D(
            int(model_config["channels"]),
            int(model_config["kernel_size"]),
            padding="causal",
            dilation_rate=int(dilation),
            activation=tf.nn.gelu,
            name=f"block_{index}_conv_1",
        )(y)
        y = tf.keras.layers.Dropout(float(model_config["dropout"]), name=f"block_{index}_drop_1")(y)
        y = tf.keras.layers.Conv1D(
            int(model_config["channels"]),
            int(model_config["kernel_size"]),
            padding="causal",
            dilation_rate=int(dilation),
            name=f"block_{index}_conv_2",
        )(y)
        y = tf.keras.layers.Dropout(float(model_config["dropout"]), name=f"block_{index}_drop_2")(y)
        x = tf.keras.layers.Activation(tf.nn.gelu, name=f"block_{index}_residual_gelu")(
            residual + y
        )
    logits = tf.keras.layers.Dense(3, name="state_logits")(x)
    model = tf.keras.Model(inputs=inputs, outputs=logits, name="phase5_1t_causal_tcn")
    if model.count_params() >= int(model_config["parameter_limit"]):
        raise RuntimeError(f"MODEL_PARAMETER_LIMIT_EXCEEDED:{model.count_params()}")
    return model


def softmax(logits: np.ndarray) -> np.ndarray:
    value = np.asarray(logits, np.float64)
    value -= np.max(value, axis=-1, keepdims=True)
    exp = np.exp(value)
    return exp / np.sum(exp, axis=-1, keepdims=True)


def decode_event(
    timestamps_ms: np.ndarray,
    probabilities: np.ndarray,
    duration_ms: float,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    timestamps = np.asarray(timestamps_ms, np.float64)
    probs = np.asarray(probabilities, np.float64)
    active = np.argmax(probs, axis=1) == 1
    indices = np.flatnonzero(active)
    if len(indices) == 0:
        return None
    if len(timestamps) > 1:
        default_dt = float(np.median(np.diff(timestamps)))
    else:
        default_dt = 0.0
    gap_ms = float(config["decoding"]["short_gap_merge_ms"])
    runs: list[list[int]] = [[int(indices[0])]]
    for index in indices[1:]:
        inactive_gap_ms = max(0.0, float(timestamps[index] - timestamps[runs[-1][-1]]) - default_dt)
        if inactive_gap_ms <= gap_ms:
            runs[-1].append(int(index))
        else:
            runs.append([int(index)])

    def run_key(run: list[int]) -> tuple[float, float, float]:
        dts = np.full(len(run), default_dt, np.float64)
        if len(run) > 1:
            dts[:-1] = np.diff(timestamps[run])
        integral = float(np.sum(probs[run, 1] * np.maximum(dts, 0.0)))
        duration = float(timestamps[run[-1]] - timestamps[run[0]] + default_dt)
        return (integral, duration, -float(timestamps[run[0]]))

    chosen = max(runs, key=run_key)
    start = max(0.0, float(timestamps[chosen[0]]) - float(config["decoding"]["pre_padding_ms"]))
    end = min(
        float(duration_ms),
        float(timestamps[chosen[-1]]) + default_dt + float(config["decoding"]["post_padding_ms"]),
    )
    if end <= start:
        return None
    return {
        "start_ms": start,
        "end_ms": end,
        "active_observation_start_index": chosen[0],
        "active_observation_end_index": chosen[-1],
        "merged_active_run_count": len(runs),
        "selection_key": list(run_key(chosen)),
    }


def event_result(
    row: dict[str, Any], event: dict[str, Any] | None, containment_threshold: float
) -> dict[str, Any]:
    human_start = float(row["human_sign_start_ms"])
    human_end = float(row["human_sign_end_ms"])
    human_duration = human_end - human_start
    base = {
        "sample_id": row["sample_id"],
        "source": row["source"],
        "signer_id": row["signer_id"],
        "gloss": row["gloss"],
        "segmentation_split": row["segmentation_split"],
        "human_start_ms": human_start,
        "human_end_ms": human_end,
        "video_duration_ms": float(row["video_duration_ms"]),
        "event_emitted": event is not None,
    }
    if event is None:
        return {
            **base,
            "predicted_start_ms": None,
            "predicted_end_ms": None,
            "active_recall": 0.0,
            "window_precision": 0.0,
            "contained_90pct": False,
            "premature_cut": True,
            "start_error_ms": None,
            "end_error_ms": None,
            "start_absolute_error_ms": None,
            "end_absolute_error_ms": None,
            "excess_pre_ms": 0.0,
            "excess_post_ms": 0.0,
            "retained_context_ms": 0.0,
        }
    predicted_start = float(event["start_ms"])
    predicted_end = float(event["end_ms"])
    intersection = max(0.0, min(predicted_end, human_end) - max(predicted_start, human_start))
    predicted_duration = max(predicted_end - predicted_start, 1e-9)
    recall = intersection / human_duration
    precision = intersection / predicted_duration
    return {
        **base,
        "predicted_start_ms": predicted_start,
        "predicted_end_ms": predicted_end,
        "active_recall": recall,
        "window_precision": precision,
        "contained_90pct": recall >= containment_threshold,
        "premature_cut": recall < containment_threshold,
        "start_error_ms": predicted_start - human_start,
        "end_error_ms": predicted_end - human_end,
        "start_absolute_error_ms": abs(predicted_start - human_start),
        "end_absolute_error_ms": abs(predicted_end - human_end),
        "excess_pre_ms": max(0.0, human_start - predicted_start),
        "excess_post_ms": max(0.0, predicted_end - human_end),
        "retained_context_ms": max(0.0, human_start - predicted_start)
        + max(0.0, predicted_end - human_end),
    }


def state_metrics(truth: list[np.ndarray], predictions: list[np.ndarray]) -> dict[str, Any]:
    y_true = np.concatenate(truth).astype(np.int32)
    y_pred = np.concatenate(predictions).astype(np.int32)
    keep = y_true != IGNORE_LABEL
    y_true = y_true[keep]
    y_pred = y_pred[keep]
    confusion = np.zeros((3, 3), np.int64)
    for actual, predicted in zip(y_true, y_pred, strict=True):
        confusion[actual, predicted] += 1
    per_class: dict[str, Any] = {}
    f1_values = []
    for index, name in enumerate(LABEL_NAMES):
        tp = int(confusion[index, index])
        fp = int(confusion[:, index].sum() - tp)
        fn = int(confusion[index, :].sum() - tp)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1_values.append(f1)
        per_class[name] = {
            "support": int(confusion[index, :].sum()),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return {
        "observation_count": int(len(y_true)),
        "accuracy": float(np.mean(y_true == y_pred)),
        "macro_f1": float(np.mean(f1_values)),
        "per_class": per_class,
        "confusion_matrix_rows_actual_columns_predicted": confusion.tolist(),
    }


def distribution(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0}
    array = np.asarray(values, np.float64)
    return {
        "count": len(values),
        "min": float(array.min()),
        "p10": float(np.percentile(array, 10)),
        "p25": float(np.percentile(array, 25)),
        "median": float(np.median(array)),
        "p75": float(np.percentile(array, 75)),
        "p90": float(np.percentile(array, 90)),
        "max": float(array.max()),
        "mean": float(array.mean()),
    }


def aggregate_events(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    emitted = [row for row in results if row["event_emitted"]]
    return {
        "clip_count": total,
        "events_emitted": len(emitted),
        "event_emission_rate": len(emitted) / total,
        "containment_count": sum(row["contained_90pct"] for row in results),
        "containment_rate": sum(row["contained_90pct"] for row in results) / total,
        "premature_cut_count": sum(row["premature_cut"] for row in results),
        "premature_cut_rate": sum(row["premature_cut"] for row in results) / total,
        "active_recall": distribution([float(row["active_recall"]) for row in results]),
        "predicted_window_precision": distribution(
            [float(row["window_precision"]) for row in results]
        ),
        "start_signed_error_ms": distribution([float(row["start_error_ms"]) for row in emitted]),
        "start_absolute_error_ms": distribution(
            [float(row["start_absolute_error_ms"]) for row in emitted]
        ),
        "end_signed_error_ms": distribution([float(row["end_error_ms"]) for row in emitted]),
        "end_absolute_error_ms": distribution(
            [float(row["end_absolute_error_ms"]) for row in emitted]
        ),
        "excess_pre_ms": distribution([float(row["excess_pre_ms"]) for row in results]),
        "excess_post_ms": distribution([float(row["excess_post_ms"]) for row in results]),
        "retained_context_ms": distribution([float(row["retained_context_ms"]) for row in results]),
    }


def predict_rows(
    model: Any, rows: list[dict[str, Any]], config: dict[str, Any]
) -> tuple[list[np.ndarray], list[dict[str, Any]]]:
    import tensorflow as tf

    predictions: list[np.ndarray] = []
    events: list[dict[str, Any]] = []
    threshold = float(config["evaluation"]["containment_active_recall_threshold"])
    for row in rows:
        logits = model(tf.convert_to_tensor(row["normalized_features"][None]), training=False)
        probabilities = softmax(logits.numpy()[0])
        predicted = np.argmax(probabilities, axis=1).astype(np.int32)
        event = decode_event(
            row["timestamps_ms"], probabilities, float(row["video_duration_ms"]), config
        )
        predictions.append(predicted)
        result = event_result(row, event, threshold)
        result["predicted_state_counts"] = {
            LABEL_NAMES[index]: int(np.count_nonzero(predicted == index)) for index in range(3)
        }
        if event is not None:
            result["decoder"] = event
        events.append(result)
    return predictions, events


def _checkpoint_key(events: list[dict[str, Any]], state: dict[str, Any]) -> tuple[float, ...]:
    aggregate = aggregate_events(events)
    return (
        float(aggregate["containment_rate"]),
        -float(aggregate["premature_cut_rate"]),
        float(aggregate["event_emission_rate"]),
        float(aggregate["predicted_window_precision"].get("mean", 0.0)),
        float(state["macro_f1"]),
    )


def train_once() -> dict[str, Any]:
    import tensorflow as tf

    config = load_config()
    rows, manifest, labels_document = load_training_arrays()
    train_rows = [row for row in rows if row["segmentation_split"] == "SEGMENTATION_TRAIN"]
    dev_rows = [row for row in rows if row["segmentation_split"] == "SEGMENTATION_DEV"]
    if len(train_rows) != 89 or len(dev_rows) != 23:
        raise RuntimeError("TRAIN_DEV_COUNT_CHANGED")
    seed = int(config["training"]["seed"])
    tf.keras.utils.set_random_seed(seed)
    tf.config.experimental.enable_op_determinism()

    stats = normalization_from_train([row["features"] for row in train_rows])
    normalization = {
        "schema": "apphear.phase5_1t.train_only_normalization.v1",
        "feature_schema": SEGMENTATION_FEATURE_SCHEMA,
        "population": "89_USABLE_SEGMENTATION_TRAIN_CLIPS_ONLY",
        "train_sample_ids": [row["sample_id"] for row in train_rows],
        "observation_count": int(sum(len(row["features"]) for row in train_rows)),
        "mean": stats["mean"].astype(float).tolist(),
        "std": stats["std"].astype(float).tolist(),
        "dev_influenced_statistics": False,
    }
    write_json(OUT / "normalization_stats.json", normalization)
    for row in rows:
        row["normalized_features"] = apply_normalization(
            row["features"], stats["mean"], stats["std"]
        )

    train_counts = Counter(
        int(label) for row in train_rows for label in row["labels"] if int(label) != IGNORE_LABEL
    )
    if set(train_counts) != {0, 1, 2}:
        raise RuntimeError(f"TRAIN_LABEL_CLASS_MISSING:{dict(train_counts)}")
    total_labels = sum(train_counts.values())
    class_weights = {index: total_labels / (3.0 * train_counts[index]) for index in range(3)}
    max_length = max(len(row["labels"]) for row in train_rows)
    x = np.zeros((len(train_rows), max_length, FEATURE_WIDTH), np.float32)
    y = np.zeros((len(train_rows), max_length), np.int32)
    weights = np.zeros((len(train_rows), max_length), np.float32)
    for sample_index, row in enumerate(train_rows):
        length = len(row["labels"])
        x[sample_index, :length] = row["normalized_features"]
        valid = row["labels"] != IGNORE_LABEL
        y[sample_index, :length] = np.where(valid, row["labels"], 0)
        weights[sample_index, :length] = np.asarray(
            [
                class_weights[int(label)] if keep else 0.0
                for label, keep in zip(row["labels"], valid, strict=True)
            ],
            np.float32,
        )

    model = build_model(config)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(
            learning_rate=float(config["training"]["learning_rate"])
        ),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        weighted_metrics=[tf.keras.metrics.SparseCategoricalAccuracy(name="state_accuracy")],
    )
    summary_lines: list[str] = []
    model.summary(print_fn=summary_lines.append)
    model_summary = {
        "schema": "apphear.phase5_1t.model_summary.v1",
        "architecture": config["model"],
        "parameter_count": int(model.count_params()),
        "under_parameter_limit": model.count_params() < int(config["model"]["parameter_limit"]),
        "causal": True,
        "input_shape": [None, None, FEATURE_WIDTH],
        "output_shape": [None, None, 3],
        "keras_summary": summary_lines,
    }
    write_json(OUT / "model_summary.json", model_summary)

    class BoundaryCheckpoint(tf.keras.callbacks.Callback):
        def __init__(self) -> None:
            super().__init__()
            self.best_key: tuple[float, ...] | None = None
            self.best_epoch: int | None = None
            self.records: list[dict[str, Any]] = []

        def on_epoch_end(self, epoch: int, logs: dict[str, float] | None = None) -> None:
            predictions, events = predict_rows(self.model, dev_rows, config)
            state = state_metrics([row["labels"] for row in dev_rows], predictions)
            event_metrics = aggregate_events(events)
            key = _checkpoint_key(events, state)
            improved = self.best_key is None or key > self.best_key
            if improved:
                self.best_key = key
                self.best_epoch = epoch + 1
                self.model.save(OUT / "best_model.keras", overwrite=True)
            record = {
                "epoch": epoch + 1,
                "train_logs": {name: float(value) for name, value in (logs or {}).items()},
                "dev_checkpoint_key": list(key),
                "dev_containment_rate": event_metrics["containment_rate"],
                "dev_premature_cut_rate": event_metrics["premature_cut_rate"],
                "dev_event_emission_rate": event_metrics["event_emission_rate"],
                "dev_mean_window_precision": event_metrics["predicted_window_precision"].get(
                    "mean", 0.0
                ),
                "dev_macro_f1": state["macro_f1"],
                "saved_as_best": improved,
            }
            self.records.append(record)
            print(
                f"boundary-check epoch={epoch + 1} key={key} best={improved}",
                flush=True,
            )

    checkpoint = BoundaryCheckpoint()
    history = model.fit(
        x,
        y,
        sample_weight=weights,
        batch_size=int(config["training"]["batch_size"]),
        epochs=int(config["training"]["epochs"]),
        shuffle=True,
        verbose=2,
        callbacks=[checkpoint],
    )
    if checkpoint.best_epoch is None or not (OUT / "best_model.keras").is_file():
        raise RuntimeError("BEST_CHECKPOINT_NOT_CREATED")
    training_history = {
        "schema": "apphear.phase5_1t.training_history.v1",
        "training_run_identity": "MAIN_RUN_01",
        "started_from_random_initialization": True,
        "seed": seed,
        "epochs_completed": len(history.history["loss"]),
        "best_epoch": checkpoint.best_epoch,
        "best_checkpoint_key": list(checkpoint.best_key or ()),
        "class_label_counts_train_only": {LABEL_NAMES[key]: train_counts[key] for key in range(3)},
        "class_weights_train_only": {LABEL_NAMES[key]: class_weights[key] for key in range(3)},
        "padded_train_length": max_length,
        "keras_history": {
            name: [float(value) for value in values] for name, values in history.history.items()
        },
        "epoch_boundary_metrics": checkpoint.records,
        "dev_used_only_by_predeclared_checkpoint_rule": True,
        "model_sweep": False,
        "bug_rerun": False,
        "input_manifest_sha256": sha256(OUT / "extracted_feature_manifest.json"),
        "label_artifact_sha256": sha256(OUT / "generated_temporal_labels.json"),
        "normalization_sha256": sha256(OUT / "normalization_stats.json"),
    }
    write_json(OUT / "training_history.json", training_history)
    final = evaluate_and_report(
        rows, config, model_summary, training_history, manifest, labels_document
    )
    return final


def _write_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = [
        "sample_id",
        "source",
        "signer_id",
        "gloss",
        "human_start_ms",
        "human_end_ms",
        "video_duration_ms",
        "event_emitted",
        "predicted_start_ms",
        "predicted_end_ms",
        "active_recall",
        "window_precision",
        "contained_90pct",
        "premature_cut",
        "start_error_ms",
        "end_error_ms",
        "start_absolute_error_ms",
        "end_absolute_error_ms",
        "excess_pre_ms",
        "excess_post_ms",
        "retained_context_ms",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _group_event_metrics(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    return {name: aggregate_events(values) for name, values in sorted(grouped.items())}


def full_video_baseline(
    rows: list[dict[str, Any]], config: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    threshold = float(config["evaluation"]["containment_active_recall_threshold"])
    results = [
        event_result(
            row,
            {"start_ms": 0.0, "end_ms": float(row["video_duration_ms"])},
            threshold,
        )
        for row in rows
    ]
    return results, aggregate_events(results)


def promotion_decision(
    learned: dict[str, Any],
    baseline: dict[str, Any],
    per_signer: dict[str, Any],
    diagnostic: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    policy = config["evaluation"]["promotion"]
    baseline_context = float(baseline["retained_context_ms"].get("mean", 0.0))
    learned_context = float(learned["retained_context_ms"].get("mean", 0.0))
    reduction = 1.0 - learned_context / baseline_context if baseline_context > 0 else 0.0
    multi_clip = [
        float(value["active_recall"]["mean"])
        for value in per_signer.values()
        if int(value["clip_count"]) >= 2
    ]
    all_signer = [float(value["active_recall"]["mean"]) for value in per_signer.values()]
    unseen = diagnostic["unseen_in_segmentation_train"]
    seen = diagnostic["seen_in_segmentation_train"]
    recall_drop = float(seen["active_recall"]["mean"] - unseen["active_recall"]["mean"])
    checks = {
        "event_emission_rate": learned["event_emission_rate"]
        >= policy["minimum_event_emission_rate"],
        "containment_rate": learned["containment_rate"] >= policy["minimum_containment_rate"],
        "premature_cut_rate": learned["premature_cut_rate"] <= policy["maximum_premature_cut_rate"],
        "median_active_recall": learned["active_recall"]["median"]
        >= policy["minimum_median_active_recall"],
        "excess_context_reduction": reduction
        >= policy["minimum_excess_context_reduction_vs_full_video"],
        "unseen_gloss_recall": unseen["active_recall"]["mean"]
        >= policy["minimum_unseen_gloss_mean_active_recall"],
        "seen_unseen_recall_drop": recall_drop <= policy["maximum_seen_to_unseen_recall_drop"],
        "multi_clip_signer_floor": not multi_clip
        or min(multi_clip) >= policy["minimum_multi_clip_signer_mean_active_recall"],
        "all_signer_floor": min(all_signer) >= policy["minimum_any_signer_mean_active_recall"],
    }
    promoted = all(checks.values())
    return {
        "checks": checks,
        "excess_context_reduction_vs_full_video": reduction,
        "seen_to_unseen_mean_active_recall_drop": recall_drop,
        "minimum_multi_clip_signer_mean_active_recall": min(multi_clip) if multi_clip else None,
        "minimum_any_signer_mean_active_recall": min(all_signer),
        "all_checks_pass": promoted,
        "evidence_state": (
            "LEARNED_SEGMENTER_PROMOTED_FOR_LIVE_INTEGRATION"
            if promoted
            else "RAW_V1_SEGMENTER_NOT_YET_JUSTIFIED"
        ),
        "production_readiness_claimed": False,
    }


def failure_diagnosis(
    train_state: dict[str, Any],
    dev_state: dict[str, Any],
    dev_events: dict[str, Any],
    per_signer: dict[str, Any],
    by_source: dict[str, Any],
) -> list[dict[str, str]]:
    diagnoses: list[dict[str, str]] = []
    if train_state["macro_f1"] < 0.75:
        diagnoses.append(
            {
                "category": "UNDERFIT_SMALL_DATA",
                "evidence": f"TRAIN macro-F1 was {train_state['macro_f1']:.4f} (<0.75).",
            }
        )
    train_active = train_state["per_class"]["ACTIVE_SIGN"]["recall"]
    dev_active = dev_state["per_class"]["ACTIVE_SIGN"]["recall"]
    if train_active - dev_active >= 0.20:
        diagnoses.append(
            {
                "category": "SIGNER_GENERALIZATION_FAILURE",
                "evidence": (
                    f"ACTIVE recall dropped {train_active - dev_active:.4f} "
                    "from TRAIN to unseen-signer DEV."
                ),
            }
        )
    confusion = np.asarray(dev_state["confusion_matrix_rows_actual_columns_predicted"], np.int64)
    active_total = max(int(confusion[1].sum()), 1)
    if confusion[1, 2] / active_total >= 0.20:
        diagnoses.append(
            {
                "category": "STATE_CONFUSION_ACTIVE_POST",
                "evidence": (
                    f"{confusion[1, 2] / active_total:.4f} of supervised ACTIVE "
                    "observations were predicted POST."
                ),
            }
        )
    if confusion[1, 0] / active_total >= 0.20:
        diagnoses.append(
            {
                "category": "STATE_CONFUSION_PRE_ACTIVE",
                "evidence": (
                    f"{confusion[1, 0] / active_total:.4f} of supervised ACTIVE "
                    "observations were predicted PRE."
                ),
            }
        )
    signer_recall = [value["active_recall"]["mean"] for value in per_signer.values()]
    if max(signer_recall) - min(signer_recall) >= 0.35:
        diagnoses.append(
            {
                "category": "SIGNER_GENERALIZATION_FAILURE",
                "evidence": (
                    "Per-signer mean event recall range was "
                    f"{min(signer_recall):.4f}–{max(signer_recall):.4f}."
                ),
            }
        )
    if len(by_source) > 1:
        source_recall = [value["active_recall"]["mean"] for value in by_source.values()]
        if max(source_recall) - min(source_recall) >= 0.35:
            diagnoses.append(
                {
                    "category": "SOURCE_DOMAIN_FAILURE",
                    "evidence": (
                        "Per-source mean event recall range was "
                        f"{min(source_recall):.4f}–{max(source_recall):.4f}."
                    ),
                }
            )
    if dev_events["event_emission_rate"] < 0.95 and dev_active >= 0.75:
        diagnoses.append(
            {
                "category": "DECODING_UNSTABLE",
                "evidence": (
                    "DEV state ACTIVE recall was substantial while fixed decoding failed "
                    "to emit nearly all events."
                ),
            }
        )
    unique = {(item["category"], item["evidence"]): item for item in diagnoses}
    return list(unique.values())


def evaluate_and_report(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
    model_summary: dict[str, Any],
    training_history: dict[str, Any],
    manifest: dict[str, Any],
    labels_document: dict[str, Any],
) -> dict[str, Any]:
    import tensorflow as tf

    model = tf.keras.models.load_model(OUT / "best_model.keras")
    train_rows = [row for row in rows if row["segmentation_split"] == "SEGMENTATION_TRAIN"]
    dev_rows = [row for row in rows if row["segmentation_split"] == "SEGMENTATION_DEV"]
    train_predictions, train_event_rows = predict_rows(model, train_rows, config)
    dev_predictions, dev_event_rows = predict_rows(model, dev_rows, config)
    train_state = state_metrics([row["labels"] for row in train_rows], train_predictions)
    dev_state = state_metrics([row["labels"] for row in dev_rows], dev_predictions)
    train_events = aggregate_events(train_event_rows)
    dev_events = aggregate_events(dev_event_rows)
    write_json(OUT / "dev_state_metrics.json", dev_state)
    write_json(OUT / "dev_event_metrics.json", dev_events)
    _write_results_csv(OUT / "per_dev_sample_results.csv", dev_event_rows)

    per_signer = _group_event_metrics(dev_event_rows, "signer_id")
    per_signer_document = {
        "schema": "apphear.phase5_1t.per_signer_results.v1",
        "held_out_signer_count": len(per_signer),
        "results": per_signer,
    }
    write_json(OUT / "per_signer_results.json", per_signer_document)
    train_glosses = {str(row["gloss"]) for row in train_rows}
    seen_rows = [row for row in dev_event_rows if str(row["gloss"]) in train_glosses]
    unseen_rows = [row for row in dev_event_rows if str(row["gloss"]) not in train_glosses]
    diagnostic = {
        "schema": "apphear.phase5_1t.seen_unseen_gloss_diagnostic.v1",
        "diagnostic_only": True,
        "seen_in_segmentation_train": aggregate_events(seen_rows),
        "unseen_in_segmentation_train": aggregate_events(unseen_rows),
        "unseen_glosses": sorted({str(row["gloss"]) for row in unseen_rows}),
        "training_or_selection_influence": False,
    }
    write_json(OUT / "seen_unseen_gloss_diagnostic.json", diagnostic)

    baseline_rows, baseline_metrics = full_video_baseline(dev_rows, config)
    baseline = {
        "schema": "apphear.phase5_1t.baseline_comparison.v1",
        "full_video_window": baseline_metrics,
        "learned_segmenter": dev_events,
        "deterministic_phase5_1_policy": {
            "evaluated": False,
            "reason": "NO_RUNNABLE_FROZEN_GLOBAL_CONFIGURATION_AFTER_PHASE5_1R",
            "retuning_performed": False,
        },
        "d1_reference": {
            "evaluated": False,
            "reason": "DIAGNOSTIC_NOT_REQUIRED_AND_EXCLUDED_FROM_TRAINING_PROMOTION",
        },
        "per_sample_full_video": baseline_rows,
    }
    write_json(OUT / "baseline_comparison.json", baseline)

    by_source = _group_event_metrics(dev_event_rows, "source")
    promotion = promotion_decision(dev_events, baseline_metrics, per_signer, diagnostic, config)
    diagnoses = (
        []
        if promotion["all_checks_pass"]
        else failure_diagnosis(train_state, dev_state, dev_events, per_signer, by_source)
    )
    final = {
        "schema": "apphear.phase5_1t.first_segmenter_result.v1",
        "milestone": MILESTONE,
        "generated_at_utc": utc_now(),
        "best_epoch": training_history["best_epoch"],
        "train_state_metrics": train_state,
        "train_event_metrics": train_events,
        "dev_state_metrics": dev_state,
        "dev_event_metrics": dev_events,
        "dev_by_source": by_source,
        "promotion": promotion,
        "failure_diagnoses": diagnoses,
        "representation_insufficiency": (
            "NOT_ESTABLISHED_BY_ONE_SMALL_MODEL_RUN"
            if not any(item["category"] == "REPRESENTATION_INSUFFICIENT" for item in diagnoses)
            else "SUPPORTED"
        ),
        "next_stop_boundary": (
            "WAIT_FOR_PROJECT_LEAD_PHASE_5_1T_4_LIVE_INTEGRATION_DECISION"
            if promotion["all_checks_pass"]
            else "WAIT_FOR_PROJECT_LEAD_PHASE_5_1T_3_FAILURE_DIAGNOSIS"
        ),
        "governance": {
            "selected_manifest_unchanged": sha256(SELECTED) == EXPECTED_SELECTED_SHA,
            "segmentation_split_unchanged": sha256(SPLIT) == EXPECTED_SPLIT_SHA,
            "usable_train": 89,
            "usable_dev": 23,
            "zero_signer_overlap": True,
            "full_video_extraction_count": manifest["full_source_video_count"],
            "human_timestamps_used_only_as_labels": True,
            "d1_target_usage": False,
            "recognition_v2_accessed": False,
            "recognizer_inference": False,
            "recognition_dev_accessed": False,
            "protected_test_accessed": False,
            "sealed_phone_holdout_accessed": False,
            "model_sweep": False,
            "new_annotation": False,
            "android_modified": False,
        },
    }
    write_json(OUT / "final_result.json", final)
    write_report(
        final, config, model_summary, training_history, labels_document, diagnostic, baseline
    )
    write_source_hashes()
    return final


def write_report(
    result: dict[str, Any],
    config: dict[str, Any],
    model_summary: dict[str, Any],
    history: dict[str, Any],
    labels: dict[str, Any],
    diagnostic: dict[str, Any],
    baseline: dict[str, Any],
) -> None:
    dev_state = result["dev_state_metrics"]
    dev_event = result["dev_event_metrics"]
    train_state = result["train_state_metrics"]
    promotion = result["promotion"]
    full = baseline["full_video_window"]
    report = f"""# Phase 5.1T-3 First Class-Agnostic Segmenter

Milestone: `{MILESTONE}`

## A–B. Input representation and full-video extraction

The model consumes `{SEGMENTATION_FEATURE_SCHEMA}` `[T,{FEATURE_WIDTH}]` FP32 sequences derived
only from chronological `apphear.perception_vnext.raw.v1` observations. The contract contains
current refined-hand, proposal, ROI and body geometry/support/validity, actual `dt`, and only
backward one-transition deltas. Missing geometry is zero plus explicit validity. No interpolation,
stale carry, RGB, gloss/class input, Recognition V2, recognizer output, or future observation is
present.

All `112/112` usable samples were verified as complete source-video Candidate01 sequences:
frame zero through the decoded final frame, `duration_scope=whole_isolated_clip`, and no D1,
recognition, or human span supplied to extraction. Human boundaries controlled labels only.

## C–D. Labels and ignored transitions

The fixed class map is `0=PRE_IDLE`, `1=ACTIVE_SIGN`, `2=POST_RECOVERY`. The frozen ignore band is
`{config["labels"]["ignore_band_ms"]:.0f} ms` inclusively around both human START and END.

- TRAIN counts: `{labels["totals"]["SEGMENTATION_TRAIN"]}`
- DEV counts: `{labels["totals"]["SEGMENTATION_DEV"]}`

## E–F. Model and training configuration

One causal TCN was run: 64-channel input projection, four residual blocks, kernel 3, dilations
`[1,2,4,8]`, two causal convolutions per block, GELU, dropout 0.2, and three per-observation logits.
Parameter count: `{model_summary["parameter_count"]:,}` (<200k). Seed `{history["seed"]}`, Adam
`lr=0.001`, TRAIN-only weighted cross-entropy, 50 fixed epochs, batch size 8. The checkpoint rule
was frozen before training and selected epoch `{history["best_epoch"]}` lexicographically by DEV
containment, premature cuts, emission, precision, macro-F1, then earliest epoch. This was one main
run; no sweep or rerun occurred.

## G. TRAIN learning behavior

- Final logged loss: `{history["keras_history"]["loss"][-1]:.6f}`
- TRAIN observation accuracy / macro-F1 at selected checkpoint:
  `{train_state["accuracy"]:.4f}` / `{train_state["macro_f1"]:.4f}`
- TRAIN per-class metrics: `{train_state["per_class"]}`

## H. Frozen DEV temporal-state metrics

- Observation accuracy: `{dev_state["accuracy"]:.4f}`
- Macro-F1: `{dev_state["macro_f1"]:.4f}`
- Per-class metrics: `{dev_state["per_class"]}`
- Confusion matrix (actual rows, predicted columns):
  `{dev_state["confusion_matrix_rows_actual_columns_predicted"]}`

## I–K. DEV events, premature cuts, and retained context

- Events emitted: `{dev_event["events_emitted"]}/{dev_event["clip_count"]}`
- >=90% ACTIVE containment: `{dev_event["containment_count"]}/{dev_event["clip_count"]}`
  (`{dev_event["containment_rate"]:.4f}`)
- Premature cuts: `{dev_event["premature_cut_count"]}/{dev_event["clip_count"]}`
  (`{dev_event["premature_cut_rate"]:.4f}`)
- ACTIVE recall distribution: `{dev_event["active_recall"]}`
- Predicted-window precision: `{dev_event["predicted_window_precision"]}`
- START signed / absolute error (ms): `{dev_event["start_signed_error_ms"]}` /
  `{dev_event["start_absolute_error_ms"]}`
- END signed / absolute error (ms): `{dev_event["end_signed_error_ms"]}` /
  `{dev_event["end_absolute_error_ms"]}`
- Excess PRE / POST (ms): `{dev_event["excess_pre_ms"]}` / `{dev_event["excess_post_ms"]}`

## L. Held-out signer results

`{json.dumps(read_json(OUT / "per_signer_results.json")["results"], sort_keys=True)}`

## M. Seen-vs-unseen-gloss diagnostic

- Seen-gloss DEV: `{diagnostic["seen_in_segmentation_train"]}`
- Unseen-gloss DEV: `{diagnostic["unseen_in_segmentation_train"]}`
- Unseen glosses (`{len(diagnostic["unseen_glosses"])}`): `{diagnostic["unseen_glosses"]}`

This comparison is diagnostic only and did not alter training, decoding, or selection.

## N. Baseline comparison

The full-video baseline retained every human ACTIVE interval but retained mean context
`{full["retained_context_ms"]["mean"]:.2f} ms`. The learned event retained mean context
`{dev_event["retained_context_ms"]["mean"]:.2f} ms`, a frozen reduction of
`{promotion["excess_context_reduction_vs_full_video"]:.4f}`. Phase 5.1 deterministic segmentation
was not evaluated because no runnable global configuration survived Phase 5.1R; no threshold
search was reopened. D1 was not used.

## O–P. Failure cases and representation sufficiency

Evidence-based failure diagnoses: `{result["failure_diagnoses"]}`

Representation conclusion: `{result["representation_insufficiency"]}`. A failure of this single,
small, bounded model does not by itself prove raw-v1 representation insufficiency.

## Q–R. Final evidence state and stop boundary

Promotion checks: `{promotion["checks"]}`

**`{promotion["evidence_state"]}`**

No production-readiness claim is made.

**`{result["next_stop_boundary"]}`**
"""
    (OUT / "PHASE5_1T_3_SEGMENTER_REPORT.md").write_text(report, encoding="utf-8")


def write_source_hashes() -> None:
    files = [
        SELECTED,
        SPLIT,
        ANNOTATIONS,
        CONFIG,
        ROOT / "pipeline/perception_vnext/offline_candidate01.py",
        ROOT / "pipeline/perception_vnext/recognition_schema.py",
        ROOT / "pipeline/perception_vnext/segmentation/learned_features.py",
        Path(__file__).resolve(),
        ROOT / "tests/test_phase5_1t_first_segmenter.py",
        ROOT
        / (
            "artifacts/recognition_upgrade/perception_vnext/phone_01/"
            "candidate_01_dwpose_t_mp_hand/export/dwpose_t_singlepass.onnx"
        ),
        ROOT
        / (
            "artifacts/recognition_upgrade/perception_vnext/phone_01/"
            "candidate_01_dwpose_t_mp_hand/refiner/hand_landmarks_detector.tflite"
        ),
        OUT / "extracted_feature_manifest.json",
        OUT / "feature_schema.json",
        OUT / "normalization_stats.json",
        OUT / "generated_temporal_labels.json",
        OUT / "best_model.keras",
        OUT / "test_results.json",
    ]
    write_json(
        OUT / "source_hashes.json",
        {
            "schema": "APPHEAR_PHASE5_1T_3_SOURCE_HASHES_V1",
            "generated_at_utc": utc_now(),
            "files": [
                {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}
                for path in files
            ],
        },
    )


def prepare() -> dict[str, Any]:
    rows = load_population()
    config = load_config()
    result = {
        "milestone": MILESTONE,
        "selected_manifest_sha256": sha256(SELECTED),
        "segmentation_split_sha256": sha256(SPLIT),
        "training_config_sha256": sha256(CONFIG),
        "usable_train": sum(row["segmentation_split"] == "SEGMENTATION_TRAIN" for row in rows),
        "usable_dev": sum(row["segmentation_split"] == "SEGMENTATION_DEV" for row in rows),
        "train_signers": sorted(
            {row["signer_id"] for row in rows if row["segmentation_split"] == "SEGMENTATION_TRAIN"}
        ),
        "dev_signers": sorted(
            {row["signer_id"] for row in rows if row["segmentation_split"] == "SEGMENTATION_DEV"}
        ),
        "feature_schema": config["features"]["schema"],
        "training_runs_authorized": config["experiment_policy"]["main_training_runs"],
        "status": "PREDECLARED_AND_INTEGRITY_VERIFIED",
    }
    if set(result["train_signers"]) & set(result["dev_signers"]):
        raise RuntimeError("SIGNER_OVERLAP")
    write_json(OUT / "pretraining_integrity.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "extract", "train", "all"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command in {"prepare", "all"}:
        print(json.dumps(prepare(), indent=2), flush=True)
    if args.command in {"extract", "all"}:
        value = extract_full_video_features()
        print(
            json.dumps(
                {
                    key: value[key]
                    for key in (
                        "sample_count",
                        "train_count",
                        "dev_count",
                        "full_source_video_count",
                    )
                },
                indent=2,
            ),
            flush=True,
        )
    if args.command in {"train", "all"}:
        value = train_once()
        print(
            json.dumps(
                {
                    "evidence_state": value["promotion"]["evidence_state"],
                    "next": value["next_stop_boundary"],
                },
                indent=2,
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
