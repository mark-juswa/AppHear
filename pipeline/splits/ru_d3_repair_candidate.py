"""Build the isolated RU-D3 repaired-data candidate without training a model.

The frozen Phase-1 train tensor/manifest are read-only parents.  Target rows are
re-extracted from their hashed raw videos into the RU-D3 run directory, bounded
with the existing D1/D2 contract, and rebuilt with schema-v3.0 Stage-F math.
Final assembly preserves every non-target row byte-for-byte and records all
keep/re-extract/exclude/cap decisions.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import multiprocessing as mp_process
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.detect.config import load_config as load_detect_config
from pipeline.detect.signals import compute_signals
from pipeline.detect.span import detect_span
from pipeline.extract.config import load_config as load_extract_config
from pipeline.extract.landmarks import LandmarkExtractor
from pipeline.features.config import load_config as load_feature_config
from pipeline.features.contract import SCHEMA_VERSION, clip_features_realtimed
from pipeline.normalize.config import load_config as load_normalize_config

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT = (
    ROOT / "artifacts/recognition_upgrade/four_class_foundation_audit_01/review_manifest.csv"
)
DEFAULT_BASELINE = ROOT / "artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1"
DEFAULT_OUTPUT = ROOT / "artifacts/recognition_upgrade/ru_d3/repair_candidate_01"
TARGETS = {"KNOW", "WHO", "WE", "LEAVE"}
REEXTRACT_CLASSES = {"LANDMARK_FAILURE", "INCOMPLETE_OR_BAD_SIGN"}
EXTRACT_CONFIG = ROOT / "pipeline/config/extract.yaml"
DETECT_CONFIG = ROOT / "pipeline/config/detect.yaml"
FEATURE_CONFIG = ROOT / "pipeline/config/features.yaml"
NORMALIZE_CONFIG = ROOT / "pipeline/config/normalize.yaml"

_WORKER: dict[str, Any] = {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _array_sha256(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(value.dtype).encode("ascii"))
    digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
    digest.update(value.tobytes())
    return digest.hexdigest().upper()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def _safe_id(sample_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", sample_id).strip("_")


def _initial_action(row: dict[str, str]) -> tuple[str, str]:
    gloss = row["canonical_gloss"]
    review_index = int(row["review_index"])
    source = row["source_dataset"]
    classification = row["manual_classification"]
    if gloss == "KNOW" and review_index == 37:
        return "EXCLUDE", "reviewed span does not contain a complete KNOW"
    if gloss == "LEAVE" and review_index == 14:
        return "EXCLUDE", "one-handed LEAVE variant conflicts with frozen two-hand target"
    if classification == "LANDMARK_FAILURE":
        return "REEXTRACT", "target variant is visible but existing landmark tensor failed"
    if gloss == "KNOW" and source in {"APPHEAR_CAPTURE", "LOCAL"}:
        return "REEXTRACT", "unbounded full clip labels rest/preparation/release as KNOW"
    return "KEEP", "reviewed target-consistent tensor is usable"


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output: {args.output}")
    args.output.mkdir(parents=True)
    audit_rows = [row for row in _read_csv(args.audit) if row["canonical_gloss"] in TARGETS]
    baseline_rows = _read_csv(args.baseline / "manifests/train.csv")
    baseline_by_id = {row["sample_id"]: row for row in baseline_rows}
    if len(audit_rows) != 158:
        raise ValueError(f"expected 158 target audit rows, found {len(audit_rows)}")
    decisions: list[dict[str, Any]] = []
    errors: list[str] = []
    for row in audit_rows:
        base = baseline_by_id.get(row["sample_id"])
        if base is None:
            errors.append(f"audit row missing from frozen train manifest: {row['sample_id']}")
            continue
        action, reason = _initial_action(row)
        decisions.append(
            {
                "sample_id": row["sample_id"],
                "canonical_gloss": row["canonical_gloss"],
                "review_index": row["review_index"],
                "source_dataset": row["source_dataset"],
                "signer_group_id": row["signer_group_id"],
                "raw_video_path": row["raw_video_path"],
                "raw_video_sha256": row["raw_video_sha256"],
                "manual_classification": row["manual_classification"],
                "manual_variant": row["manual_variant"],
                "initial_action": action,
                "decision_reason": reason,
            }
        )
    baseline_train = args.baseline / "train.npz"
    baseline_manifest = args.baseline / "manifests/train.csv"
    baseline_hashes = {
        "train_npz": _sha256(baseline_train),
        "train_manifest": _sha256(baseline_manifest),
        "audit_manifest": _sha256(args.audit),
    }
    _write_csv(args.output / "decisions_initial.csv", decisions)
    variant_registry = {
        "version": "ru_d3_apphear_target_variants_v1",
        "scope": "dataset candidate metadata only; no feature-contract or vocabulary change",
        "variants": {
            "KNOW": {
                "variant_id": "KNOW_ONE_HAND_TEMPLE_V1",
                "required_hands": "one",
                "description": (
                    "one hand approaches/touches the temple or upper forehead; not a HELLO wave"
                ),
            },
            "WHO": {
                "variant_id": "WHO_ONE_HAND_FACE_CHIN_V1",
                "required_hands": "one",
                "description": "short one-hand movement at the lower face/chin",
            },
            "WE": {
                "variant_id": "WE_ONE_HAND_CROSS_UPPER_TORSO_V1",
                "required_hands": "one",
                "description": (
                    "one-hand path traverses the upper torso/shoulder region; short "
                    "center-chest executions remain adjudication-sensitive against COME"
                ),
            },
            "COME": {
                "variant_id": "COME_INWARD_TO_TORSO_V1",
                "required_hands": "one_or_two_dataset_variant",
                "description": (
                    "inward/toward-signer torso-directed movement represented by current "
                    "AppHear COME examples; frozen comparison class, not modified in RU-D3"
                ),
            },
            "LEAVE": {
                "variant_id": "LEAVE_TWO_HAND_OPEN_CLOSE_WITHDRAW_V1",
                "required_hands": "two",
                "description": (
                    "two-hand open-to-close/withdrawal family; one-hand lexical variants "
                    "are excluded from this target"
                ),
            },
        },
    }
    (args.output / "variant_registry.json").write_text(
        json.dumps(variant_registry, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "phase": "RU-D3",
        "scope": (
            "repair candidate construction only; no training, collection, external "
            "ingestion, or production mutation"
        ),
        "schema_version": SCHEMA_VERSION,
        "feature_contract": [96, 258],
        "baseline_rows": len(baseline_rows),
        "target_rows": len(decisions),
        "initial_action_counts": dict(Counter(row["initial_action"] for row in decisions)),
        "baseline_hashes": baseline_hashes,
        "errors": errors,
        "passed": not errors,
    }
    (args.output / "prepare_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def _init_worker() -> None:
    extract_cfg = load_extract_config(EXTRACT_CONFIG)
    _WORKER["extractor"] = LandmarkExtractor(extract_cfg)
    _WORKER["extract_cfg"] = extract_cfg
    _WORKER["detect_cfg"] = load_detect_config(DETECT_CONFIG)
    _WORKER["feature_cfg"] = load_feature_config(FEATURE_CONFIG)
    _WORKER["normalize_cfg"] = load_normalize_config(NORMALIZE_CONFIG)


def _coverage(
    hand_score: np.ndarray, onset: int, release: int
) -> tuple[float, float, float, float]:
    score = hand_score[onset : release + 1] > 0.0
    any_rate = float(np.mean(np.any(score, axis=1)))
    two_rate = float(np.mean(np.all(score, axis=1)))
    left_rate = float(np.mean(score[:, 0]))
    right_rate = float(np.mean(score[:, 1]))
    return any_rate, two_rate, left_rate, right_rate


def _recoverable(
    gloss: str, valid: bool, length: int, any_rate: float, two_rate: float
) -> tuple[bool, str]:
    reasons: list[str] = []
    if not valid:
        reasons.append("invalid_span")
    if length < 6 or length > 96:
        reasons.append(f"span_length_{length}_outside_6_96")
    if gloss == "LEAVE":
        if any_rate < 0.50:
            reasons.append(f"any_hand_{any_rate:.3f}_below_0.50")
        if two_rate < 0.20:
            reasons.append(f"two_hand_{two_rate:.3f}_below_0.20")
    elif any_rate < 0.45:
        reasons.append(f"any_hand_{any_rate:.3f}_below_0.45")
    return not reasons, ";".join(reasons)


def _extract_one(payload: dict[str, str]) -> dict[str, Any]:
    extractor: LandmarkExtractor = _WORKER["extractor"]
    detect_cfg = _WORKER["detect_cfg"]
    feature_cfg = _WORKER["feature_cfg"]
    normalize_cfg = _WORKER["normalize_cfg"]
    output = Path(payload["output"])
    raw_path = Path(payload["raw_video_path"])
    base = _safe_id(payload["sample_id"])
    stage_path = output / "stage_e" / f"{base}.npz"
    span_path = output / "spans" / f"{base}.span.json"
    feature_path = output / "per_clip" / f"{base}.npz"
    try:
        observed_raw_hash = _sha256(raw_path)
        if observed_raw_hash != payload["raw_video_sha256"].upper():
            raise ValueError("raw video hash differs from frozen lineage")
        clip, meta = extractor.extract(raw_path)
        signals = compute_signals(
            clip,
            detect_cfg.pose_landmarks,
            detect_cfg.hand_aux_weight,
            detect_cfg.raise_margin,
            detect_cfg.smoothing_window,
        )
        span = detect_span(signals, detect_cfg)
        length = span.release - span.onset + 1 if span.onset >= 0 else 0
        any_rate = two_rate = left_rate = right_rate = 0.0
        feature_hash = ""
        if span.onset >= 0:
            any_rate, two_rate, left_rate, right_rate = _coverage(
                clip.hand_score, span.onset, span.release
            )
        accepted, rejection = _recoverable(
            payload["canonical_gloss"], span.valid, length, any_rate, two_rate
        )
        stage_path.parent.mkdir(parents=True, exist_ok=True)
        clip.save(stage_path)
        span_record = {
            "detect_version": detect_cfg.detect_version,
            "params_hash": detect_cfg.params_hash,
            "sample_id": payload["sample_id"],
            "canonical_gloss": payload["canonical_gloss"],
            "signer_group_id": payload["signer_group_id"],
            "raw_video_sha256": observed_raw_hash,
            "n_frames": int(meta["n_frames"]),
            "native_fps": float(meta["native_fps"]),
            "onset": span.onset,
            "release": span.release,
            "valid": span.valid,
            "reason": span.reason,
            "n_signing_frames": span.n_signing_frames,
            "span_length": length,
            "any_hand_coverage": any_rate,
            "two_hand_coverage": two_rate,
            "left_hand_coverage": left_rate,
            "right_hand_coverage": right_rate,
            "automatic_recovery_accepted": accepted,
            "automatic_rejection_reason": rejection,
        }
        span_path.parent.mkdir(parents=True, exist_ok=True)
        span_path.write_text(json.dumps(span_record, indent=2) + "\n", encoding="utf-8")
        if accepted:
            feature, frame_mask, feature_length, _ = clip_features_realtimed(
                clip.hands_image,
                clip.pose_image,
                span.onset,
                span.release,
                normalize_cfg,
                feature_cfg.streaming_t_max,
            )
            feature_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                feature_path,
                feature=feature,
                frame_mask=frame_mask,
                length=np.asarray(feature_length, dtype=np.int32),
                schema_version=np.asarray(SCHEMA_VERSION),
            )
            feature_hash = _sha256(feature_path)
        return {
            **{
                key: payload[key]
                for key in (
                    "sample_id",
                    "canonical_gloss",
                    "review_index",
                    "source_dataset",
                    "signer_group_id",
                    "raw_video_path",
                    "raw_video_sha256",
                )
            },
            "status": "ok",
            "error": "",
            "n_frames": int(meta["n_frames"]),
            "native_fps": float(meta["native_fps"]),
            "onset": span.onset,
            "release": span.release,
            "span_length": length,
            "span_valid": span.valid,
            "any_hand_coverage": f"{any_rate:.6f}",
            "two_hand_coverage": f"{two_rate:.6f}",
            "left_hand_coverage": f"{left_rate:.6f}",
            "right_hand_coverage": f"{right_rate:.6f}",
            "automatic_recovery_accepted": str(accepted).lower(),
            "automatic_rejection_reason": rejection,
            "stage_e_path": str(stage_path.resolve()),
            "stage_e_sha256": _sha256(stage_path),
            "span_path": str(span_path.resolve()),
            "span_sha256": _sha256(span_path),
            "feature_path": str(feature_path.resolve()) if accepted else "",
            "feature_sha256": feature_hash,
        }
    except Exception as error:  # noqa: BLE001 - one clip must not kill the repair run
        return {
            **{
                key: payload[key]
                for key in (
                    "sample_id",
                    "canonical_gloss",
                    "review_index",
                    "source_dataset",
                    "signer_group_id",
                    "raw_video_path",
                    "raw_video_sha256",
                )
            },
            "status": "failed",
            "error": str(error)[:500],
            "automatic_recovery_accepted": "false",
        }


def extract(args: argparse.Namespace) -> dict[str, Any]:
    decisions = _read_csv(args.output / "decisions_initial.csv")
    selected = [
        dict(row, output=str(args.output.resolve()))
        for row in decisions
        if row["initial_action"] == "REEXTRACT"
    ]
    existing_path = args.output / "extraction_manifest.csv"
    existing = (
        {row["sample_id"]: row for row in _read_csv(existing_path)}
        if existing_path.is_file()
        else {}
    )
    todo = [row for row in selected if row["sample_id"] not in existing]
    results = list(existing.values())
    if todo:
        if args.workers <= 1:
            _init_worker()
            iterator = map(_extract_one, todo)
        else:
            context = mp_process.get_context("spawn")
            pool = context.Pool(processes=args.workers, initializer=_init_worker)
            iterator = pool.imap_unordered(_extract_one, todo, chunksize=2)
        try:
            for index, result in enumerate(iterator, start=1):
                results.append(result)
                if index % 10 == 0:
                    print(f"[ru-d3] extracted {index}/{len(todo)}")
        finally:
            if args.workers > 1:
                pool.close()
                pool.join()
    results.sort(key=lambda row: int(row["review_index"]))
    fields = sorted({key for row in results for key in row})
    _write_csv(existing_path, results, fields)
    summary = {
        "selected": len(selected),
        "previously_complete": len(existing),
        "processed_now": len(todo),
        "status_counts": dict(Counter(row.get("status", "") for row in results)),
        "automatic_recovery_counts": dict(
            Counter(row.get("automatic_recovery_accepted", "") for row in results)
        ),
        "passed": len(results) == len(selected)
        and all(row.get("status") == "ok" for row in results),
    }
    (args.output / "extraction_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def _know_rebound_span(stage_path: Path) -> tuple[int, int, str]:
    """Bound a low-motion KNOW clip from rest through temple contact back to rest."""
    from pipeline.extract.schema import ClipLandmarks
    from pipeline.normalize.scale import clip_scale

    clip = ClipLandmarks.load(stage_path)
    scale = clip_scale(clip.pose_image)
    wrists = clip.pose_image[:, [15, 16], :2]
    ears = clip.pose_image[:, [7, 8], :2]
    distance = (
        np.linalg.norm(wrists[:, :, None, :] - ears[:, None, :, :], axis=3).min(axis=(1, 2)) / scale
    )
    if len(distance) < 6 or not np.isfinite(distance).all():
        return -1, -1, "invalid_pose_distance"
    if float(np.mean(distance[:3])) <= 0.80:
        return -1, -1, "missing_pre_sign_rest"
    if float(np.mean(distance[-3:])) <= 0.80:
        return -1, -1, "missing_post_sign_rest"
    contact = np.flatnonzero(distance < 0.65)
    if not len(contact) or float(np.min(distance)) >= 0.60:
        return -1, -1, "no_clear_temple_contact"
    first_contact, last_contact = int(contact[0]), int(contact[-1])
    pre_rest = np.flatnonzero(distance[:first_contact] >= 0.90)
    post_rest = np.flatnonzero(distance[last_contact + 1 :] >= 0.90)
    if not len(pre_rest):
        return -1, -1, "no_preparation_boundary"
    if not len(post_rest):
        return -1, -1, "no_release_boundary"
    onset = max(0, int(pre_rest[-1]) - 2)
    release = min(len(distance) - 1, last_contact + 1 + int(post_rest[0]) + 2)
    if not 6 <= release - onset + 1 <= 96:
        return -1, -1, "manual_span_outside_6_96"
    return onset, release, ""


def _write_rebound_panel(
    raw_path: Path, output_path: Path, label: str, onset: int, release: int
) -> None:
    import cv2

    capture = cv2.VideoCapture(str(raw_path))
    if not capture.isOpened():
        raise OSError(f"cannot open review video: {raw_path}")
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if onset >= 0:
        indices = [
            0,
            max(0, onset - 2),
            onset,
            (onset + release) // 2,
            release,
            min(count - 1, release + 2),
            count - 1,
        ]
    else:
        indices = np.linspace(0, max(0, count - 1), 7).astype(int).tolist()
    frames: list[np.ndarray] = []
    try:
        for frame_index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok:
                continue
            frame = cv2.resize(frame, (180, 240))
            cv2.putText(
                frame,
                f"f{frame_index}",
                (5, 232),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )
            frames.append(frame)
    finally:
        capture.release()
    if not frames:
        raise OSError(f"no review frames decoded: {raw_path}")
    strip = np.concatenate(frames, axis=1)
    header = np.zeros((48, strip.shape[1], 3), dtype=np.uint8)
    cv2.putText(
        header,
        label[:150],
        (8, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), np.concatenate([header, strip], axis=0))


def _write_contact_sheets(panel_paths: list[Path], output_dir: Path) -> None:
    import cv2

    output_dir.mkdir(parents=True, exist_ok=True)
    for page, offset in enumerate(range(0, len(panel_paths), 10), start=1):
        images: list[np.ndarray] = []
        for path in panel_paths[offset : offset + 10]:
            image = cv2.imread(str(path))
            if image is None:
                raise OSError(f"cannot read generated panel: {path}")
            images.append(cv2.resize(image, (840, 192)))
        sheet = np.concatenate(images, axis=0)
        cv2.imwrite(str(output_dir / f"know_rebound_{page:02d}.jpg"), sheet)


def rebound_know(args: argparse.Namespace) -> dict[str, Any]:
    from pipeline.extract.schema import ClipLandmarks

    extraction = _read_csv(args.output / "extraction_manifest.csv")
    selected = [
        row
        for row in extraction
        if row["canonical_gloss"] == "KNOW"
        and row["source_dataset"] in {"APPHEAR_CAPTURE", "LOCAL"}
    ]
    normalize_cfg = load_normalize_config(NORMALIZE_CONFIG)
    feature_cfg = load_feature_config(FEATURE_CONFIG)
    results: list[dict[str, Any]] = []
    for row in selected:
        stage_path = Path(row["stage_e_path"])
        onset, release, reason = _know_rebound_span(stage_path)
        accepted = not reason
        any_rate = two_rate = 0.0
        feature_path = args.output / "per_clip_rebounded" / (f"{_safe_id(row['sample_id'])}.npz")
        span_path = args.output / "spans_rebounded" / (f"{_safe_id(row['sample_id'])}.span.json")
        if accepted:
            clip = ClipLandmarks.load(stage_path)
            any_rate, two_rate, _, _ = _coverage(clip.hand_score, onset, release)
            if any_rate < 0.45:
                accepted = False
                reason = f"rebounded_any_hand_{any_rate:.3f}_below_0.45"
            else:
                feature, frame_mask, length, _ = clip_features_realtimed(
                    clip.hands_image,
                    clip.pose_image,
                    onset,
                    release,
                    normalize_cfg,
                    feature_cfg.streaming_t_max,
                )
                feature_path.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(
                    feature_path,
                    feature=feature,
                    frame_mask=frame_mask,
                    length=np.asarray(length, dtype=np.int32),
                    schema_version=np.asarray(SCHEMA_VERSION),
                )
        span_record = {
            "method": "ru_d3_know_rest_temple_rest_v1",
            "sample_id": row["sample_id"],
            "raw_video_sha256": row["raw_video_sha256"],
            "onset": onset,
            "release": release,
            "span_length": release - onset + 1 if accepted else 0,
            "any_hand_coverage": any_rate,
            "two_hand_coverage": two_rate,
            "accepted": accepted,
            "rejection_reason": reason,
        }
        span_path.parent.mkdir(parents=True, exist_ok=True)
        span_path.write_text(json.dumps(span_record, indent=2) + "\n", encoding="utf-8")
        panel_path = (
            args.output
            / "know_rebound_panels"
            / (f"{int(row['review_index']):03d}_{_safe_id(row['sample_id'])}.jpg")
        )
        status = "ACCEPT" if accepted else "REJECT"
        _write_rebound_panel(
            Path(row["raw_video_path"]),
            panel_path,
            (
                f"{row['review_index']} KNOW {row['source_dataset']} "
                f"{status} {reason} span={onset}-{release}"
            ),
            onset if accepted else -1,
            release if accepted else -1,
        )
        results.append(
            {
                **row,
                "automatic_recovery_accepted": str(accepted).lower(),
                "automatic_rejection_reason": reason,
                "onset": onset,
                "release": release,
                "span_length": release - onset + 1 if accepted else 0,
                "any_hand_coverage": f"{any_rate:.6f}",
                "two_hand_coverage": f"{two_rate:.6f}",
                "span_path": str(span_path.resolve()),
                "span_sha256": _sha256(span_path),
                "feature_path": str(feature_path.resolve()) if accepted else "",
                "feature_sha256": _sha256(feature_path) if accepted else "",
                "panel_path": str(panel_path.resolve()),
                "rebound_method": "ru_d3_know_rest_temple_rest_v1",
            }
        )
    fields = sorted({key for row in results for key in row})
    _write_csv(args.output / "know_rebound_manifest.csv", results, fields)
    _write_contact_sheets(
        [Path(row["panel_path"]) for row in results],
        args.output / "know_rebound_contact_sheets",
    )
    summary = {
        "selected": len(selected),
        "accepted": sum(row["automatic_recovery_accepted"] == "true" for row in results),
        "rejected": sum(row["automatic_recovery_accepted"] != "true" for row in results),
        "rejection_reasons": dict(
            Counter(
                row["automatic_rejection_reason"]
                for row in results
                if row["automatic_recovery_accepted"] != "true"
            )
        ),
        "passed": len(results) == 110,
    }
    (args.output / "know_rebound_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def _load_repair_feature(path: Path) -> tuple[np.ndarray, np.ndarray, int]:
    with np.load(path, allow_pickle=False) as data:
        if str(np.asarray(data["schema_version"]).item()) != SCHEMA_VERSION:
            raise ValueError(f"schema mismatch: {path}")
        return (
            np.asarray(data["feature"], np.float32),
            np.asarray(data["frame_mask"], bool),
            int(np.asarray(data["length"]).item()),
        )


def _variant_id(gloss: str) -> str:
    return {
        "KNOW": "KNOW_ONE_HAND_TEMPLE_V1",
        "WHO": "WHO_ONE_HAND_FACE_CHIN_V1",
        "WE": "WE_ONE_HAND_CROSS_UPPER_TORSO_V1",
        "LEAVE": "LEAVE_TWO_HAND_OPEN_CLOSE_WITHDRAW_V1",
    }.get(gloss, "BASELINE_UNCHANGED")


def build(args: argparse.Namespace) -> dict[str, Any]:
    decisions = {row["sample_id"]: row for row in _read_csv(args.output / "decisions_initial.csv")}
    extracted = {
        row["sample_id"]: row for row in _read_csv(args.output / "extraction_manifest.csv")
    }
    rebound_path = args.output / "know_rebound_manifest.csv"
    if rebound_path.is_file():
        extracted.update({row["sample_id"]: row for row in _read_csv(rebound_path)})
    baseline_rows = _read_csv(args.baseline / "manifests/train.csv")
    with np.load(args.baseline / "train.npz", allow_pickle=True) as data:
        baseline = {key: np.asarray(data[key]) for key in data.files}
    baseline_ids = baseline["sample_ids"].astype(str).tolist()
    if baseline_ids != [row["sample_id"] for row in baseline_rows]:
        raise ValueError("frozen baseline manifest/tensor row order mismatch")

    final_actions: dict[str, tuple[str, str]] = {}
    for sample_id, decision in decisions.items():
        action = decision["initial_action"]
        reason = decision["decision_reason"]
        if action == "REEXTRACT":
            result = extracted.get(sample_id)
            if (
                result is None
                or result.get("status") != "ok"
                or result.get("automatic_recovery_accepted") != "true"
            ):
                action = "EXCLUDE_UNRECOVERABLE"
                reason = (
                    result.get("automatic_rejection_reason", "extraction failed")
                    if result
                    else "missing extraction result"
                )
            else:
                action = "REEXTRACT_KEEP"
                reason = (
                    "isolated Stage-E + D1/D2 span + schema-v3.0 feature passed "
                    "class-specific landmark gate"
                )
        final_actions[sample_id] = (action, reason)

    know_by_signer: dict[str, list[tuple[str, float]]] = defaultdict(list)
    row_by_id = {row["sample_id"]: row for row in baseline_rows}
    for sample_id, (action, _) in final_actions.items():
        row = row_by_id[sample_id]
        if row["canonical_gloss"] != "KNOW" or action not in {"KEEP", "REEXTRACT_KEEP"}:
            continue
        result = extracted.get(sample_id, {})
        score = float(result.get("any_hand_coverage") or 1.0)
        know_by_signer[row["signer_group_id"]].append((sample_id, score))
    for _signer, candidates in know_by_signer.items():
        ranked = sorted(candidates, key=lambda item: (-item[1], item[0]))
        for sample_id, _ in ranked[args.know_signer_cap :]:
            final_actions[sample_id] = (
                "EXCLUDE_SIGNER_CAP",
                f"deterministic KNOW cap of {args.know_signer_cap} rows per signer "
                "prevents source/signer dominance",
            )

    candidate_rows: list[dict[str, Any]] = []
    x_rows: list[np.ndarray] = []
    y_rows: list[int] = []
    masks: list[np.ndarray] = []
    lengths: list[int] = []
    decisions_final: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    for index, row in enumerate(baseline_rows):
        sample_id = row["sample_id"]
        action, reason = final_actions.get(sample_id, ("UNCHANGED", "outside RU-D3 target classes"))
        decision_record = {
            **row,
            "ru_d3_action": action,
            "decision_reason": reason,
            "variant_id": _variant_id(row["canonical_gloss"]),
        }
        if action.startswith("EXCLUDE"):
            excluded_rows.append(decision_record)
            decisions_final.append(decision_record)
            continue
        if action == "REEXTRACT_KEEP":
            result = extracted[sample_id]
            feature, frame_mask, length = _load_repair_feature(Path(result["feature_path"]))
            stage_hash = result["stage_e_sha256"]
            span_hash = result["span_sha256"]
            source_feature = result["feature_path"]
            lineage_status = "ru_d3_reextracted_raw_span_feature"
        else:
            feature = np.asarray(baseline["X"][index], np.float32)
            frame_mask = np.asarray(baseline["frame_mask"][index], bool)
            length = int(baseline["lengths"][index])
            stage_hash = ""
            span_hash = ""
            source_feature = row["feature_artifact_path"]
            lineage_status = (
                row["lineage_status"] if action == "UNCHANGED" else "ru_d3_reviewed_baseline_keep"
            )
        candidate_index = len(candidate_rows)
        candidate = {
            **row,
            "feature_artifact_path": str((args.output / "candidate_train.npz").resolve()),
            "feature_row_index": candidate_index,
            "feature_length": length,
            "lineage_status": lineage_status,
            "ru_d3_action": action,
            "decision_reason": reason,
            "variant_id": _variant_id(row["canonical_gloss"]),
            "baseline_feature_artifact_path": row["feature_artifact_path"],
            "baseline_feature_row_index": row["feature_row_index"],
            "candidate_feature_source_path": source_feature,
            "candidate_feature_sha256": _array_sha256(feature),
            "candidate_stage_e_sha256": stage_hash,
            "candidate_span_sha256": span_hash,
        }
        candidate_rows.append(candidate)
        x_rows.append(feature)
        y_rows.append(int(row["class_id"]))
        masks.append(frame_mask)
        lengths.append(length)
        decisions_final.append(decision_record)

    candidate_npz = args.output / "candidate_train.npz"
    np.savez_compressed(
        candidate_npz,
        X=np.stack(x_rows).astype(np.float32),
        y=np.asarray(y_rows, dtype=np.int32),
        frame_mask=np.stack(masks).astype(bool),
        lengths=np.asarray(lengths, dtype=np.int32),
        participant_ids=np.asarray([row["signer_group_id"] for row in candidate_rows]),
        sample_ids=np.asarray([row["sample_id"] for row in candidate_rows]),
        source_datasets=np.asarray([row["source_dataset"] for row in candidate_rows]),
        raw_video_sha256=np.asarray([row["raw_video_sha256"] for row in candidate_rows]),
        roles=np.asarray([row["role"] for row in candidate_rows]),
        schema_version=np.asarray(SCHEMA_VERSION),
    )
    _write_csv(args.output / "candidate_manifest.csv", candidate_rows)
    _write_csv(args.output / "decisions_final.csv", decisions_final)
    _write_csv(args.output / "excluded_rows.csv", excluded_rows)

    dataset_dir = args.output / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate_npz, dataset_dir / "train.npz")
    shutil.copy2(args.baseline / "val.npz", dataset_dir / "val.npz")
    shutil.copy2(args.baseline / "vocab.json", dataset_dir / "vocab.json")
    _write_csv(dataset_dir / "manifests/train.csv", candidate_rows)
    shutil.copy2(args.baseline / "manifests/val.csv", dataset_dir / "manifests/val.csv")
    dataset_contract = {
        "phase": "RU-D3",
        "schema_version": SCHEMA_VERSION,
        "feature_contract": [96, 258],
        "train": {
            "path": str((dataset_dir / "train.npz").resolve()),
            "sha256": _sha256(dataset_dir / "train.npz"),
            "rows": len(candidate_rows),
        },
        "validation": {
            "path": str((dataset_dir / "val.npz").resolve()),
            "sha256": _sha256(dataset_dir / "val.npz"),
            "source_sha256": _sha256(args.baseline / "val.npz"),
            "unchanged_from_baseline": True,
        },
        "vocabulary": {
            "path": str((dataset_dir / "vocab.json").resolve()),
            "sha256": _sha256(dataset_dir / "vocab.json"),
            "source_sha256": _sha256(args.baseline / "vocab.json"),
            "classes": 236,
        },
        "protected_test_materialized": False,
        "training_authorized": False,
    }
    (dataset_dir / "dataset_contract.json").write_text(
        json.dumps(dataset_contract, indent=2) + "\n", encoding="utf-8"
    )

    before: dict[str, dict[str, Any]] = {}
    after: dict[str, dict[str, Any]] = {}
    for gloss in sorted(TARGETS | {"COME"}):
        original = [row for row in baseline_rows if row["canonical_gloss"] == gloss]
        repaired = [row for row in candidate_rows if row["canonical_gloss"] == gloss]
        before[gloss] = {
            "clips": len(original),
            "signers": len({row["signer_group_id"] for row in original}),
            "sources": dict(Counter(row["source_dataset"] for row in original)),
        }
        after[gloss] = {
            "clips": len(repaired),
            "signers": len({row["signer_group_id"] for row in repaired}),
            "sources": dict(Counter(row["source_dataset"] for row in repaired)),
        }

    candidate_id_to_index = {row["sample_id"]: i for i, row in enumerate(candidate_rows)}
    unchanged_errors: list[str] = []
    for index, row in enumerate(baseline_rows):
        if row["canonical_gloss"] in TARGETS:
            continue
        candidate_index = candidate_id_to_index.get(row["sample_id"])
        if candidate_index is None:
            unchanged_errors.append(f"non-target row removed: {row['sample_id']}")
            continue
        if not np.array_equal(baseline["X"][index], x_rows[candidate_index]):
            unchanged_errors.append(f"non-target feature changed: {row['sample_id']}")
        if int(baseline["lengths"][index]) != lengths[candidate_index]:
            unchanged_errors.append(f"non-target length changed: {row['sample_id']}")
    baseline_hashes_now = {
        "train_npz": _sha256(args.baseline / "train.npz"),
        "train_manifest": _sha256(args.baseline / "manifests/train.csv"),
    }
    prepared_hashes = json.loads(
        (args.output / "prepare_summary.json").read_text(encoding="utf-8")
    )["baseline_hashes"]
    if (
        baseline_hashes_now["train_npz"] != prepared_hashes["train_npz"]
        or baseline_hashes_now["train_manifest"] != prepared_hashes["train_manifest"]
    ):
        unchanged_errors.append("frozen baseline hash changed during RU-D3")
    summary = {
        "phase": "RU-D3",
        "schema_version": SCHEMA_VERSION,
        "feature_contract": [96, 258],
        "baseline_rows": len(baseline_rows),
        "candidate_rows": len(candidate_rows),
        "excluded_rows": len(excluded_rows),
        "before": before,
        "after": after,
        "action_counts": dict(Counter(record["ru_d3_action"] for record in decisions_final)),
        "baseline_hashes_before": {
            key: prepared_hashes[key] for key in ("train_npz", "train_manifest")
        },
        "baseline_hashes_after": baseline_hashes_now,
        "candidate_manifest_sha256": _sha256(args.output / "candidate_manifest.csv"),
        "candidate_train_sha256": _sha256(candidate_npz),
        "runner_ready_dataset": str(dataset_dir.resolve()),
        "validation_unchanged": (
            _sha256(dataset_dir / "val.npz") == _sha256(args.baseline / "val.npz")
        ),
        "protected_test_materialized": False,
        "all_other_vocabulary_classes_unchanged": not unchanged_errors,
        "unchanged_validation_errors": unchanged_errors,
        "passed": not unchanged_errors,
    }
    (args.output / "build_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    manifest = _read_csv(args.output / "candidate_manifest.csv")
    dataset_dir = args.output / "dataset"
    with np.load(dataset_dir / "train.npz", allow_pickle=True) as data:
        n = len(data["y"])
        if data["X"].shape != (n, 96, 258):
            errors.append(f"bad X shape: {data['X'].shape}")
        if data["frame_mask"].shape != (n, 96):
            errors.append("bad frame_mask shape")
        if not np.array_equal(
            data["frame_mask"].sum(axis=1).astype(np.int32), data["lengths"].astype(np.int32)
        ):
            errors.append("frame mask/length mismatch")
        if str(np.asarray(data["schema_version"]).item()) != SCHEMA_VERSION:
            errors.append("schema version mismatch")
        if data["sample_ids"].astype(str).tolist() != [row["sample_id"] for row in manifest]:
            errors.append("manifest/tensor sample order mismatch")
        if len(set(data["y"].astype(int).tolist())) != 236:
            errors.append("candidate no longer covers all 236 classes")
    summary = json.loads((args.output / "build_summary.json").read_text(encoding="utf-8"))
    errors.extend(summary.get("unchanged_validation_errors", []))
    if _sha256(dataset_dir / "val.npz") != _sha256(args.baseline / "val.npz"):
        errors.append("candidate validation tensor differs from frozen baseline")
    if (dataset_dir / "test.npz").exists():
        errors.append("protected test was materialized in the RU-D3 candidate")
    result = {
        "run_dir": str(args.output.resolve()),
        "rows": len(manifest),
        "errors": errors,
        "passed": not errors,
    }
    (args.output / "check_report.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    for command in ("prepare", "extract", "rebound-know", "build", "check"):
        child = sub.add_parser(command)
        child.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
        child.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
        child.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
        child.add_argument(
            "--workers", type=int, default=max(1, min(4, (mp_process.cpu_count() or 2) - 1))
        )
        child.add_argument("--know-signer-cap", type=int, default=10)
    return root


def main() -> int:
    args = parser().parse_args()
    result = {
        "prepare": prepare,
        "extract": extract,
        "rebound-know": rebound_know,
        "build": build,
        "check": check,
    }[args.command](args)
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
