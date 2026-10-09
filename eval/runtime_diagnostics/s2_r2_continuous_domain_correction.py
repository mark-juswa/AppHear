"""Governed preparation and bounded learnability check for S2-R2.

This module deliberately separates the cheap, preregistered learnability check from the
full Candidate01 reprocessing and the single main training run.  It never reads protected
TEST and never changes the 378-dimensional feature contract.
"""

from __future__ import annotations

# The project entrypoints add the repository root before importing sibling modules.
# ruff: noqa: E402, I001

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics.phase5_1t_first_segmenter import (  # noqa: E402
    IGNORE_LABEL,
    LABEL_NAMES,
    build_model,
    softmax,
    state_metrics,
    temporal_labels,
)
import eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter as p7  # noqa: E402
from eval.runtime_diagnostics.phase8a_causal_streaming_decoder import (  # noqa: E402
    aggregate_event_metrics,
    event_metrics_for_row,
    run_decoder,
)
from eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter import (  # noqa: E402
    deterministic_offset_ms,
)
from pipeline.perception_vnext.offline_candidate01 import (  # noqa: E402
    EXPECTED_ONNX_SHA256,
    EXPECTED_REFINER_SHA256,
    Candidate01Offline,
    _rotate_upright,
    sha256 as candidate_sha256,
)
from pipeline.perception_vnext.recognition_schema import RAW_SCHEMA, RawSequence  # noqa: E402
from pipeline.perception_vnext.segmentation.learned_features import (  # noqa: E402
    FEATURE_WIDTH,
    SEGMENTATION_FEATURE_SCHEMA,
    apply_normalization,
    derive_causal_segmentation_features,
    normalization_from_train,
)
from pipeline.perception_vnext.segmentation.streaming_decoder import (  # noqa: E402
    StreamingDecoderConfig,
)

MILESTONE = "S2_R2_CONTINUOUS_DOMAIN_CORRECTION_01"
BASE = ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
SUPERVISION = BASE / "s2_r2_phone_temporal_supervision_01"
OUT = BASE / "s2_r2_continuous_domain_correction_01"
CONFIG = ROOT / "model/config/recognition_upgrade/s2_r2_continuous_domain_correction_01.json"
MAIN_CONFIG = ROOT / "model/config/recognition_upgrade/s2_r2_main_candidate_01.json"
CORRECTED_MAIN_CONFIG = (
    ROOT / "model/config/recognition_upgrade/s2_r2_main_candidate_01_enrichment_correction.json"
)
PHASE7 = BASE / "phase7_production_cadence_aligned_segmenter_01"
PHASE7_CONFIG = PHASE7 / "phase7_config.json"
PHASE7_SPLIT = PHASE7 / "frozen_fit_cal_split.json"
PHASE7_MANIFEST = PHASE7 / "sparse_view_manifest.json"
PHASE7_LABELS = PHASE7 / "generated_sparse_temporal_labels.json"
PHASE7_NORM = PHASE7 / "cadence_aligned_normalization_stats.json"
PHASE7_MODEL = PHASE7 / "best_model.keras"
P1_INTERVALS = SUPERVISION / "p1_temporal_review_01/p1_reviewed_intervals.csv"
PHONE_LABELS = (
    SUPERVISION
    / "phone_positive_temporal_review_01/phone_positive_observation_labels.csv"
)
EXACT_PHONE_REVIEW = OUT / "exact_phone_temporal_review_01"
EXACT_PHONE_LABELS = EXACT_PHONE_REVIEW / "exact_phone_observation_labels.csv"
EXACT_PHONE_FEATURES = EXACT_PHONE_REVIEW / "exact_phone_labeled_features.npz"
EXACT_PHONE_LINKAGE = EXACT_PHONE_REVIEW / "exact_phone_tensor_linkage.json"
HUMAN_ANNOTATIONS = (
    BASE
    / "phase5_1t_1_human_temporal_semantics_validation_01/human_annotations.json"
)
PER_SAMPLE_CONTEXT = (
    BASE / "phase5_1t_0_segmentation_data_readiness_audit_01/per_sample_context.csv"
)
UNUSED_AUDIT = (
    BASE
    / "phase8a_u_s2_training_exposure_and_terminal_diversity_audit_01"
    / "unused_governed_data_audit.json"
)
S2_SHA256 = "dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73"
PHASE7_NORM_SHA256 = "3018348ae8cc9fe0671eda913535556e14cebf5a16fbe72a96be73ed494e9130"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def freeze_json(path: Path, value: Any) -> None:
    payload = canonical_json(value)
    if path.exists() and path.read_bytes() != payload:
        raise RuntimeError(f"FROZEN_ARTIFACT_MUTATION_REFUSED:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(payload)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(value))


def load_config() -> dict[str, Any]:
    config = read_json(CONFIG)
    if config.get("milestone") != MILESTONE:
        raise RuntimeError("S2_R2_CONFIG_MILESTONE_MISMATCH")
    if config["feature_contract"] != {
        "schema": SEGMENTATION_FEATURE_SCHEMA,
        "width": FEATURE_WIDTH,
        "semantics_changed": False,
    }:
        raise RuntimeError("S2_R2_FEATURE_CONTRACT_MISMATCH")
    return config


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _stable_rank(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}|{value}".encode()).hexdigest()


def freeze_governance() -> dict[str, Any]:
    config = load_config()
    split = read_json(PHASE7_SPLIT)
    p1_rows = [
        row
        for row in _read_csv(P1_INTERVALS)
        if row["eligible_for_s2_r2_negative"].lower() == "true"
    ]
    by_participant: defaultdict[str, set[str]] = defaultdict(set)
    for row in p1_rows:
        by_participant[row["participant_id"]].add(row["clip_id"])
    development_clips: set[str] = set()
    for _participant, clips in sorted(by_participant.items()):
        ranked = sorted(clips, key=lambda value: _stable_rank(config["seed"], value))
        count = max(1, round(len(ranked) * 0.2))
        development_clips.update(ranked[:count])
    p1_assignments = [
        {
            "interval_id": row["interval_id"],
            "clip_id": row["clip_id"],
            "participant_id": row["participant_id"],
            "role": "INTERNAL_DEVELOPMENT" if row["clip_id"] in development_clips else "FIT",
        }
        for row in p1_rows
    ]

    phone_assignments = {
        "attempt_001": "INTERNAL_DEVELOPMENT_POSITIVE_ANCHOR",
        "attempt_002": "FIT_HARD_POSITIVE",
        "attempt_003": "FIT_HARD_POSITIVE",
        "attempt_004": "FIT_HARD_POSITIVE",
        "attempt_005": "FIT_POSITIVE_ANCHOR",
    }
    unused = read_json(UNUSED_AUDIT)
    enrichment = [
        row
        for row in unused["phase5_1t_1_human_labels_outside_selected_120"]["rows"]
        if row["usable"] and not row["reserved_dev_signer"]
    ]
    if len(enrichment) != 17:
        raise RuntimeError(f"S2_R2_ENRICHMENT_COUNT_CHANGED:{len(enrichment)}")

    governance = {
        "schema": "apphear.s2_r2.governance_freeze.v1",
        "milestone": MILESTONE,
        "decision": "CONSERVATIVE_FIT_DEVELOPMENT_ROLES_FROZEN",
        "identity_mapping_search": {
            "P01": "NO_AUTHORITATIVE_MAPPING_FOUND",
            "P02": "NO_AUTHORITATIVE_MAPPING_FOUND",
            "phone_design_signer": "NO_AUTHORITATIVE_MAPPING_FOUND",
            "bounded_search_conclusion": (
                "Participant aliases are not promoted to governed signer identities. "
                "They are conservatively consumed only as development enrichment."
            ),
        },
        "roles": {
            "P01": "FIT_DEVELOPMENT_ONLY_NO_INDEPENDENCE_CLAIM",
            "P02": "FIT_DEVELOPMENT_ONLY_NO_INDEPENDENCE_CLAIM",
            "phone_design:session_20260921T102840Z:S001": (
                "FIT_DEVELOPMENT_ONLY_HARD_POSITIVE_NO_INDEPENDENCE_CLAIM"
            ),
            "P03_P06": "UNUSED_N0_NOT_SELECTED",
            "0F747C-S001": "UNTOUCHED_NEGATIVE_AND_ACQUISITION_VALIDATION",
            "future_distinct_phone_signer_session": (
                "UNTOUCHED_POST_FREEZE_POSITIVE_CONTINUOUS_VALIDATION"
            ),
        },
        "retired_claims": [
            "P01/P02 cannot support an independent-signer S2-R2 claim.",
            "The current phone design signer cannot validate S2-R2.",
            "Historical opened DEV remains regression evidence, not post-R2 promotion evidence.",
        ],
        "protected_test_accessed": False,
    }
    manifest = {
        "schema": "apphear.s2_r2.dataset_manifest_design.v1",
        "milestone": MILESTONE,
        "status": "FROZEN_FOR_EXTRACTION",
        "feature_contract": {
            "schema": SEGMENTATION_FEATURE_SCHEMA,
            "width": FEATURE_WIDTH,
        },
        "normalization": "RECOMPUTE_FROM_S2_R2_FIT_ROWS_ONLY",
        "components": {
            "existing_governed_fit_71": {
                "role": "FIT",
                "clip_count": len(split["fit_sample_ids"]),
                "sparse_view_count": len(split["fit_sample_ids"]) * 3,
                "sample_ids": split["fit_sample_ids"],
            },
            "existing_governed_cal_18": {
                "role": "CHECKPOINT_SELECTION_AND_REGRESSION",
                "clip_count": len(split["cal_sample_ids"]),
                "sparse_view_count": len(split["cal_sample_ids"]) * 3,
                "sample_ids": split["cal_sample_ids"],
            },
            "prior_human_labeled_enrichment_17": {
                "role": "FIT_AFTER_CURRENT_CONTRACT_REEXTRACTION",
                "clip_count": 17,
                "rows": enrichment,
            },
            "reviewed_phone_positive_5": {
                "signer_id": "phone_design:session_20260921T102840Z:S001",
                "assignments": phone_assignments,
                "independent_validation": False,
            },
            "reviewed_p1_negative_45": {
                "participants": ["P01", "P02"],
                "assignments": p1_assignments,
                "fit_interval_count": sum(row["role"] == "FIT" for row in p1_assignments),
                "internal_development_interval_count": sum(
                    row["role"] == "INTERNAL_DEVELOPMENT" for row in p1_assignments
                ),
            },
            "n0": {"role": "UNUSED", "selected_intervals": 0},
            "e6_0F747C_S001": {"role": "UNTOUCHED_VALIDATION", "consumed": False},
            "historical_dev_23": {
                "role": "OPENED_REGRESSION_ONLY",
                "consumed_for_fit_or_selection": False,
            },
            "future_positive_phone": {
                "role": "UNTOUCHED_POST_FREEZE_VALIDATION",
                "required_scope": (
                    "one distinct signer/session; about six attempts across at least three "
                    "temporal behaviors with genuine PRE/ACTIVE/POST context"
                ),
            },
        },
        "protected_test_accessed": False,
    }
    freeze_json(OUT / "governance_freeze.json", governance)
    freeze_json(OUT / "s2_r2_dataset_manifest_design.json", manifest)
    freeze_json(
        OUT / "source_identities.json",
        {
            "schema": "apphear.s2_r2.source_identities.v1",
            "config_sha256": sha256_file(CONFIG),
            "phase7_model_sha256": sha256_file(PHASE7_MODEL),
            "expected_phase7_model_sha256": S2_SHA256,
            "phase7_normalization_sha256": sha256_file(PHASE7_NORM),
            "expected_phase7_normalization_sha256": PHASE7_NORM_SHA256,
            "candidate01_onnx_sha256": candidate_sha256(
                ROOT
                / "artifacts/recognition_upgrade/perception_vnext/phone_01/"
                "candidate_01_dwpose_t_mp_hand/export/dwpose_t_singlepass.onnx"
            ),
            "candidate01_expected_onnx_sha256": EXPECTED_ONNX_SHA256,
            "candidate01_refiner_sha256": candidate_sha256(
                ROOT
                / "artifacts/recognition_upgrade/perception_vnext/phone_01/"
                "candidate_01_dwpose_t_mp_hand/refiner/hand_landmarks_detector.tflite"
            ),
            "candidate01_expected_refiner_sha256": EXPECTED_REFINER_SHA256,
            "protected_test_accessed": False,
        },
    )
    return {"status": "S2_R2_GOVERNANCE_AND_DATASET_DESIGN_FROZEN", **governance}


def _raw_from_records(
    sample_id: str,
    source_id: str,
    signer_id: str,
    records: list[tuple[int, float, dict[str, Any]]],
) -> RawSequence:
    if not records:
        raise RuntimeError(f"S2_R2_NO_RAW_RECORDS:{sample_id}")
    value = RawSequence(
        metadata={
            "schema": RAW_SCHEMA,
            "candidate_id": "dwpose_t_256x192_plus_mp_hand_224",
            "sample_id": sample_id,
            "source_id": source_id,
            "signer_id": signer_id,
            "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB",
            "current_frame_only": True,
            "synthetic_depth": False,
            "carry_forward": False,
        },
        frame_index=np.asarray([row[0] for row in records], np.int32),
        timestamp_ms=np.asarray([row[1] for row in records], np.float64),
        source_size=np.stack([row[2]["source_size"] for row in records]),
        hand_xy=np.stack([[hand["xy"] for hand in row[2]["hands"]] for row in records]),
        hand_proposal_support=np.stack(
            [[hand["proposal_support"] for hand in row[2]["hands"]] for row in records]
        ),
        hand_joint_valid=np.stack(
            [[hand["valid"] for hand in row[2]["hands"]] for row in records]
        ),
        hand_presence=np.asarray(
            [[hand["presence"] for hand in row[2]["hands"]] for row in records], np.float32
        ),
        hand_observed=np.asarray(
            [[hand["observed"] for hand in row[2]["hands"]] for row in records], bool
        ),
        hand_proposal_present=np.asarray(
            [[hand["proposal_present"] for hand in row[2]["hands"]] for row in records], bool
        ),
        hand_roi_center_side=np.stack(
            [[hand["roi"] for hand in row[2]["hands"]] for row in records]
        ),
        hand_handedness_diagnostic=np.asarray(
            [[hand["handedness"] for hand in row[2]["hands"]] for row in records], np.float32
        ),
        body_xy=np.stack([row[2]["body_xy"] for row in records]),
        body_support=np.stack([row[2]["body_support"] for row in records]),
        body_valid=np.stack([row[2]["body_valid"] for row in records]),
        body_available=np.asarray([row[2]["body_available"] for row in records], bool),
    )
    value.validate()
    return value


def _extract_phone_rows(runtime: Candidate01Offline, attempt_ids: set[str]) -> list[dict[str, Any]]:
    grouped: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in _read_csv(PHONE_LABELS):
        if row["attempt_id"] in attempt_ids:
            grouped[row["attempt_id"]].append(row)
    result: list[dict[str, Any]] = []
    for attempt_id in sorted(grouped):
        source_rows = sorted(grouped[attempt_id], key=lambda row: int(row["observation_ordinal"]))
        records = []
        labels = []
        for row in source_rows:
            path = Path(row["original_path"])
            if sha256_file(path) != row["original_sha256"]:
                raise RuntimeError(f"S2_R2_PHONE_IMAGE_IDENTITY:{path}")
            bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if bgr is None:
                raise RuntimeError(f"S2_R2_PHONE_IMAGE_DECODE:{path}")
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            records.append(
                (
                    int(row["observation_ordinal"]) - 1,
                    int(row["source_timestamp_ns"]) / 1_000_000.0,
                    runtime.process_rgb(rgb),
                )
            )
            labels.append(int(row["state_id"]))
        raw = _raw_from_records(
            f"phone:{attempt_id}",
            "PHONE_DESIGN",
            "phone_design:session_20260921T102840Z:S001",
            records,
        )
        result.append(
            {
                "row_id": f"phone::{attempt_id}",
                "domain": "PHONE_POSITIVE",
                "source": "PHONE_DESIGN",
                "signer_id": "phone_design:session_20260921T102840Z:S001",
                "features": derive_causal_segmentation_features(raw),
                "labels": np.asarray(labels, np.int32),
                "timestamps_ms": raw.timestamp_ms,
                "provenance": "SYNCED_JPEG_REPROCESSED_CURRENT_CANDIDATE01",
            }
        )
    return result


def _video_timestamps(path: Path) -> tuple[np.ndarray, float, int]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"S2_R2_VIDEO_OPEN:{path}")
    if hasattr(cv2, "CAP_PROP_ORIENTATION_AUTO"):
        capture.set(cv2.CAP_PROP_ORIENTATION_AUTO, 0)
    orientation = 0
    if hasattr(cv2, "CAP_PROP_ORIENTATION_META"):
        orientation = int(round(capture.get(cv2.CAP_PROP_ORIENTATION_META))) % 360
    if orientation not in (0, 90, 180, 270):
        orientation = 0
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    if not math.isfinite(fps) or fps <= 0:
        capture.release()
        raise RuntimeError(f"S2_R2_VIDEO_FPS:{path}")
    values = []
    previous = -math.inf
    index = -1
    try:
        while True:
            ok, _ = capture.read()
            if not ok:
                break
            index += 1
            container_ms = float(capture.get(cv2.CAP_PROP_POS_MSEC))
            fallback_ms = index * 1000.0 / fps
            timestamp_ms = (
                container_ms
                if math.isfinite(container_ms) and container_ms > previous
                else fallback_ms
            )
            if timestamp_ms <= previous:
                timestamp_ms = previous + 1000.0 / fps
            previous = timestamp_ms
            values.append(timestamp_ms)
    finally:
        capture.release()
    return np.asarray(values, np.float64), fps, orientation


def _selected_interval_indices(
    timestamps: np.ndarray,
    interval_id: str,
    start_ms: float,
    end_ms: float,
    target_interval_ms: float,
) -> np.ndarray:
    offset = deterministic_offset_ms(interval_id, "VIEW_B", target_interval_ms)
    target = start_ms + offset
    selected = []
    previous = -1
    while target <= end_ms:
        insertion = int(np.searchsorted(timestamps, target, side="left"))
        candidates = [
            index
            for index in (insertion - 1, insertion)
            if previous < index < len(timestamps)
            and start_ms <= float(timestamps[index]) <= end_ms
        ]
        if not candidates:
            target += target_interval_ms
            continue
        chosen = min(candidates, key=lambda index: (abs(float(timestamps[index]) - target), index))
        selected.append(chosen)
        previous = chosen
        target += target_interval_ms
    if len(selected) < 2:
        raise RuntimeError(f"S2_R2_INTERVAL_TOO_SHORT:{interval_id}:{len(selected)}")
    return np.asarray(selected, np.int32)


def _process_video_indices(
    runtime: Candidate01Offline,
    path: Path,
    selected: np.ndarray,
    timestamps: np.ndarray,
    orientation: int,
) -> list[tuple[int, float, dict[str, Any]]]:
    wanted = set(map(int, selected))
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"S2_R2_VIDEO_OPEN:{path}")
    if hasattr(cv2, "CAP_PROP_ORIENTATION_AUTO"):
        capture.set(cv2.CAP_PROP_ORIENTATION_AUTO, 0)
    records = []
    index = -1
    try:
        while wanted:
            ok, frame = capture.read()
            if not ok:
                break
            index += 1
            if index not in wanted:
                continue
            upright = _rotate_upright(frame, orientation)
            rgb = cv2.cvtColor(upright, cv2.COLOR_BGR2RGB)
            records.append((index, float(timestamps[index]), runtime.process_rgb(rgb)))
            wanted.remove(index)
    finally:
        capture.release()
    if wanted:
        raise RuntimeError(f"S2_R2_SELECTED_FRAME_MISSING:{path}:{sorted(wanted)}")
    return records


def _extract_p1_rows(runtime: Candidate01Offline, interval_ids: set[str]) -> list[dict[str, Any]]:
    config = load_config()
    interval_ms = float(config["learnability"]["p1_view"]["target_interval_ms"])
    source_rows = {row["interval_id"]: row for row in _read_csv(P1_INTERVALS)}
    result = []
    for interval_id in sorted(interval_ids):
        row = source_rows.get(interval_id)
        if row is None or row["eligible_for_s2_r2_negative"].lower() != "true":
            raise RuntimeError(f"S2_R2_P1_INTERVAL_NOT_ELIGIBLE:{interval_id}")
        path = Path(row["video_path"])
        if sha256_file(path) != row["video_sha256"]:
            raise RuntimeError(f"S2_R2_P1_VIDEO_IDENTITY:{path}")
        timestamps, _, orientation = _video_timestamps(path)
        selected = _selected_interval_indices(
            timestamps,
            interval_id,
            float(row["start_ms"]),
            float(row["end_ms"]),
            interval_ms,
        )
        records = _process_video_indices(runtime, path, selected, timestamps, orientation)
        raw = _raw_from_records(
            f"p1:{interval_id}", "P1_CAPTURE_03", row["participant_id"], records
        )
        result.append(
            {
                "row_id": f"p1::{interval_id}",
                "domain": "P1_NEGATIVE",
                "source": "P1_CAPTURE_03",
                "signer_id": row["participant_id"],
                "features": derive_causal_segmentation_features(raw),
                "labels": np.zeros(len(records), np.int32),
                "timestamps_ms": raw.timestamp_ms,
                "provenance": "ORIGINAL_MP4_REPROCESSED_CURRENT_CANDIDATE01",
            }
        )
    return result


def _baseline_sanity_rows(clips_per_source: int) -> list[dict[str, Any]]:
    manifest = read_json(PHASE7_MANIFEST)
    labels_document = read_json(PHASE7_LABELS)
    labels = {row["view_key"]: row for row in labels_document["views"]}
    fit = [row for row in manifest["rows"] if row["phase7_partition"] == "FIT"]
    grouped: defaultdict[str, set[str]] = defaultdict(set)
    for row in fit:
        grouped[row["source"]].add(row["sample_id"])
    selected_ids = set()
    for _source, sample_ids in sorted(grouped.items()):
        ranked = sorted(sample_ids, key=lambda value: _stable_rank(5103, value))
        selected_ids.update(ranked[:clips_per_source])
    result = []
    for row in fit:
        if row["sample_id"] not in selected_ids:
            continue
        with np.load(row["feature_path"], allow_pickle=False) as data:
            features = np.asarray(data["features"], np.float32)
            timestamps = np.asarray(data["timestamps_ms"], np.float64)
        target = np.asarray(labels[row["view_key"]]["labels"], np.int32)
        result.append(
            {
                "row_id": f"baseline::{row['view_key']}",
                "domain": "BASELINE_SIGN",
                "source": row["source"],
                "signer_id": row["signer_id"],
                "features": features,
                "labels": target,
                "timestamps_ms": timestamps,
                "provenance": "PHASE7_FROZEN_SPARSE_FEATURE",
            }
        )
    if not result:
        raise RuntimeError("S2_R2_BASELINE_SANITY_EMPTY")
    return result


def _save_rows(rows: list[dict[str, Any]], destination: Path) -> list[dict[str, Any]]:
    destination.mkdir(parents=True, exist_ok=True)
    manifest = []
    for row in rows:
        name = hashlib.sha256(row["row_id"].encode()).hexdigest()[:24] + ".npz"
        path = destination / name
        np.savez_compressed(
            path,
            schema=np.asarray(SEGMENTATION_FEATURE_SCHEMA),
            row_id=np.asarray(row["row_id"]),
            domain=np.asarray(row["domain"]),
            source=np.asarray(row["source"]),
            signer_id=np.asarray(row["signer_id"]),
            features=np.asarray(row["features"], np.float32),
            labels=np.asarray(row["labels"], np.int32),
            timestamps_ms=np.asarray(row["timestamps_ms"], np.float64),
        )
        manifest.append(
            {
                "row_id": row["row_id"],
                "domain": row["domain"],
                "source": row["source"],
                "signer_id": row["signer_id"],
                "observation_count": len(row["labels"]),
                "label_counts": {
                    LABEL_NAMES[index]: int(np.count_nonzero(row["labels"] == index))
                    for index in range(3)
                },
                "ignored_count": int(np.count_nonzero(row["labels"] == IGNORE_LABEL)),
                "provenance": row["provenance"],
                "feature_path": str(path.resolve()),
                "feature_sha256": sha256_file(path),
            }
        )
    return manifest


def prepare_sanity() -> dict[str, Any]:
    config = load_config()
    freeze_governance()
    destination = OUT / "learnability_sanity/features"
    if destination.exists() and any(destination.glob("*.npz")):
        raise RuntimeError("S2_R2_SANITY_FEATURES_ALREADY_EXIST")
    baseline = _baseline_sanity_rows(
        int(config["learnability"]["baseline_fit_clips_per_source"])
    )
    with Candidate01Offline() as runtime:
        phone = _extract_phone_rows(runtime, set(config["learnability"]["phone_attempt_ids"]))
        p1 = _extract_p1_rows(runtime, set(config["learnability"]["p1_interval_ids"]))
    rows = baseline + phone + p1
    manifest = _save_rows(rows, destination)
    summary = {
        "schema": "apphear.s2_r2.learnability_sanity_dataset.v1",
        "milestone": MILESTONE,
        "purpose": "BOUNDED_TRAINING_FIT_SANITY_NOT_GENERALIZATION",
        "feature_contract": {"schema": SEGMENTATION_FEATURE_SCHEMA, "width": FEATURE_WIDTH},
        "row_count": len(manifest),
        "domain_row_counts": dict(sorted(Counter(row["domain"] for row in manifest).items())),
        "domain_observation_counts": dict(
            sorted(
                {
                    domain: sum(
                        row["observation_count"] for row in manifest if row["domain"] == domain
                    )
                    for domain in {row["domain"] for row in manifest}
                }.items()
            )
        ),
        "rows": manifest,
        "phone_jpeg_limitation": (
            "The rested session did not retain raw-v1. Synchronized source JPEGs are "
            "reprocessed with the current governed Candidate01 for fitting evidence; this is "
            "not represented as exact Android raw-v1 parity."
        ),
        "protected_test_accessed": False,
    }
    freeze_json(OUT / "learnability_sanity/dataset_manifest.json", summary)
    return {"status": "S2_R2_LEARNABILITY_SANITY_DATA_PREPARED", **summary}


def _load_sanity_rows() -> list[dict[str, Any]]:
    manifest = read_json(OUT / "learnability_sanity/dataset_manifest.json")
    result = []
    for row in manifest["rows"]:
        path = Path(row["feature_path"])
        if sha256_file(path) != row["feature_sha256"]:
            raise RuntimeError(f"S2_R2_SANITY_FEATURE_IDENTITY:{path}")
        with np.load(path, allow_pickle=False) as data:
            result.append(
                {
                    **row,
                    "features": np.asarray(data["features"], np.float32),
                    "labels": np.asarray(data["labels"], np.int32),
                }
            )
    return result


def _pack_rows(
    rows: list[dict[str, Any]], mean: np.ndarray, std: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    max_length = max(len(row["labels"]) for row in rows)
    x = np.zeros((len(rows), max_length, FEATURE_WIDTH), np.float32)
    y = np.zeros((len(rows), max_length), np.int32)
    weights = np.zeros((len(rows), max_length), np.float32)
    counts: Counter[tuple[str, int]] = Counter(
        (row["domain"], int(label))
        for row in rows
        for label in row["labels"]
        if int(label) != IGNORE_LABEL
    )
    domains = sorted({row["domain"] for row in rows})
    for row_index, row in enumerate(rows):
        length = len(row["labels"])
        x[row_index, :length] = apply_normalization(row["features"], mean, std)
        valid = row["labels"] != IGNORE_LABEL
        y[row_index, :length] = np.where(valid, row["labels"], 0)
        for index, (label, keep) in enumerate(zip(row["labels"], valid, strict=True)):
            if keep:
                weights[row_index, index] = 1.0 / (
                    len(domains) * counts[(row["domain"], int(label))]
                )
    positive = weights[weights > 0]
    weights[weights > 0] /= float(np.mean(positive))
    return x, y, weights


def _predict_model(
    model: Any,
    rows: list[dict[str, Any]],
    mean: np.ndarray,
    std: np.ndarray,
) -> dict[str, Any]:
    truth_by_domain: defaultdict[str, list[np.ndarray]] = defaultdict(list)
    pred_by_domain: defaultdict[str, list[np.ndarray]] = defaultdict(list)
    for row in rows:
        normalized = apply_normalization(row["features"], mean, std)
        logits = np.asarray(model(normalized[None], training=False))[0]
        predicted = np.argmax(logits, axis=1).astype(np.int32)
        truth_by_domain[row["domain"]].append(row["labels"])
        pred_by_domain[row["domain"]].append(predicted)
    return {
        domain: state_metrics(truth_by_domain[domain], pred_by_domain[domain])
        for domain in sorted(truth_by_domain)
    }


def run_sanity() -> dict[str, Any]:
    config = load_config()
    rows = _load_sanity_rows()
    stats = normalization_from_train([row["features"] for row in rows])
    normalization = {
        "schema": "apphear.s2_r2.learnability_fit_normalization.v1",
        "purpose": "SANITY_ONLY_NOT_DEPLOYMENT",
        "feature_schema": SEGMENTATION_FEATURE_SCHEMA,
        "row_ids": [row["row_id"] for row in rows],
        "observation_count": sum(len(row["labels"]) for row in rows),
        "mean": stats["mean"].astype(float).tolist(),
        "std": stats["std"].astype(float).tolist(),
        "cal_dev_validation_influenced_statistics": False,
    }
    freeze_json(OUT / "learnability_sanity/normalization.json", normalization)
    x, y, sample_weight = _pack_rows(rows, stats["mean"], stats["std"])

    import tensorflow as tf

    seed = int(config["seed"])
    tf.keras.utils.set_random_seed(seed)
    tf.config.experimental.enable_op_determinism()
    model = build_model(read_json(PHASE7_CONFIG))
    if model.count_params() != 123_779:
        raise RuntimeError(f"S2_R2_MODEL_PARAMETER_MISMATCH:{model.count_params()}")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(
            float(config["learnability"]["learning_rate"])
        ),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        weighted_metrics=[tf.keras.metrics.SparseCategoricalAccuracy(name="state_accuracy")],
    )
    history = model.fit(
        x,
        y,
        sample_weight=sample_weight,
        batch_size=int(config["learnability"]["batch_size"]),
        epochs=int(config["learnability"]["epochs"]),
        shuffle=True,
        verbose=2,
    )
    model.save(OUT / "learnability_sanity/sanity_model.keras", overwrite=True)
    candidate = _predict_model(model, rows, stats["mean"], stats["std"])

    baseline_norm = read_json(PHASE7_NORM)
    baseline_model = tf.keras.models.load_model(PHASE7_MODEL, compile=False)
    baseline = _predict_model(
        baseline_model,
        rows,
        np.asarray(baseline_norm["mean"], np.float32),
        np.asarray(baseline_norm["std"], np.float32),
    )
    gates = config["learnability"]["gates"]
    p1_confusion = candidate["P1_NEGATIVE"][
        "confusion_matrix_rows_actual_columns_predicted"
    ]
    p1_pre_support = sum(p1_confusion[0])
    p1_active_false_rate = p1_confusion[0][1] / p1_pre_support
    checks = {
        "phone_active_recall": candidate["PHONE_POSITIVE"]["per_class"]["ACTIVE_SIGN"][
            "recall"
        ]
        >= float(gates["minimum_phone_active_recall"]),
        "p1_active_false_rate": p1_active_false_rate
        <= float(gates["maximum_p1_active_false_rate"]),
        "baseline_active_recall": candidate["BASELINE_SIGN"]["per_class"]["ACTIVE_SIGN"][
            "recall"
        ]
        >= float(gates["minimum_baseline_active_recall"]),
        "baseline_post_recall": candidate["BASELINE_SIGN"]["per_class"]["POST_RECOVERY"][
            "recall"
        ]
        >= float(gates["minimum_baseline_post_recall"]),
        "finite_decreasing_loss": bool(
            np.all(np.isfinite(history.history["loss"]))
            and history.history["loss"][-1] < history.history["loss"][0]
        ),
    }
    decision = "LEARNABILITY_SUPPORTED" if all(checks.values()) else "LEARNABILITY_NOT_SUPPORTED"
    result = {
        "schema": "apphear.s2_r2.learnability_sanity_result.v1",
        "milestone": MILESTONE,
        "decision": decision,
        "purpose": "BOUNDED_TRAINING_FIT_SANITY_NOT_GENERALIZATION",
        "checks": checks,
        "measured_gate_values": {
            "phone_active_recall": candidate["PHONE_POSITIVE"]["per_class"][
                "ACTIVE_SIGN"
            ]["recall"],
            "p1_active_false_rate": p1_active_false_rate,
            "baseline_active_recall": candidate["BASELINE_SIGN"]["per_class"][
                "ACTIVE_SIGN"
            ]["recall"],
            "baseline_post_recall": candidate["BASELINE_SIGN"]["per_class"][
                "POST_RECOVERY"
            ]["recall"],
        },
        "gates": gates,
        "baseline_frozen_s2": baseline,
        "sanity_candidate": candidate,
        "training": {
            "seed": seed,
            "epochs": len(history.history["loss"]),
            "batch_size": int(config["learnability"]["batch_size"]),
            "learning_rate": float(config["learnability"]["learning_rate"]),
            "initial_loss": float(history.history["loss"][0]),
            "final_loss": float(history.history["loss"][-1]),
            "model_sha256": sha256_file(OUT / "learnability_sanity/sanity_model.keras"),
            "normalization_sha256": sha256_file(
                OUT / "learnability_sanity/normalization.json"
            ),
            "main_candidate_training_run": False,
            "bug_rerun": True,
            "bug_rerun_reason": "reporting label key ACTIVE versus governed ACTIVE_SIGN",
        },
        "claim_limit": (
            "The same bounded rows were used for optimization and measurement. A PASS only "
            "shows that the representation and unchanged causal TCN can fit the reviewed "
            "distinction; it is not signer-independent or production evidence."
        ),
        "protected_test_accessed": False,
    }
    freeze_json(OUT / "learnability_sanity/result.json", result)
    return result


def load_main_config(path: Path = CORRECTED_MAIN_CONFIG) -> dict[str, Any]:
    config = read_json(path)
    if config.get("milestone") != MILESTONE:
        raise RuntimeError("S2_R2_MAIN_CONFIG_MILESTONE_MISMATCH")
    expected = {
        "schema": SEGMENTATION_FEATURE_SCHEMA,
        "width": FEATURE_WIDTH,
        "semantics_changed": False,
    }
    if config.get("feature_contract") != expected:
        raise RuntimeError("S2_R2_MAIN_FEATURE_CONTRACT_MISMATCH")
    if config["training"]["main_training_runs"] != 1:
        raise RuntimeError("S2_R2_MAIN_RUN_COUNT_MISMATCH")
    return config


def freeze_main_design() -> dict[str, Any]:
    # Historical first freeze remains immutable. The effective main run uses the
    # separately versioned sparse-label-viability correction below.
    config = load_main_config(MAIN_CONFIG)
    linkage = read_json(EXACT_PHONE_LINKAGE)
    if linkage.get("linked_exact_tensor_observations") != 232:
        raise RuntimeError("S2_R2_EXACT_PHONE_LINKAGE_COUNT_MISMATCH")
    if linkage.get("jpeg_reprocessing_used_for_training_features") is not False:
        raise RuntimeError("S2_R2_EXACT_PHONE_JPEG_CONTAMINATION")
    design = read_json(OUT / "s2_r2_dataset_manifest_design.json")
    p1 = design["components"]["reviewed_p1_negative_45"]
    enrichment = design["components"]["prior_human_labeled_enrichment_17"]
    phone_fit = [int(value) for value in config["fit"]["phone_attempts"]]
    phone_dev = [int(value) for value in config["internal_development"]["phone_attempts"]]
    if set(phone_fit) & set(phone_dev) or sorted(phone_fit + phone_dev) != list(range(1, 7)):
        raise RuntimeError("S2_R2_EXACT_PHONE_ROLE_PARTITION_INVALID")
    result = {
        "schema": "apphear.s2_r2.main_dataset_freeze.v1",
        "milestone": MILESTONE,
        "status": "FROZEN_FOR_ONE_CANDIDATE_EXTRACTION",
        "config_path": str(MAIN_CONFIG.resolve()),
        "config_sha256": sha256_file(MAIN_CONFIG),
        "feature_contract": config["feature_contract"],
        "fit": {
            "phase7_fit_views": 213,
            "enrichment_clips": 17,
            "enrichment_views": 51,
            "phone_exact_attempts": phone_fit,
            "p1_interval_count": int(p1["fit_interval_count"]),
        },
        "internal_development": {
            "phase7_cal_views": 54,
            "phone_exact_attempts": phone_dev,
            "p1_interval_count": int(p1["internal_development_interval_count"]),
        },
        "phone": {
            "session_id": "session_20260921T153138Z",
            "signer_id": "phone_design:session_20260921T153138Z:S001",
            "role": "FIT_DEVELOPMENT_ONLY_NO_INDEPENDENCE_CLAIM",
            "reviewed_attempts": 6,
            "supervised_observations": int(linkage["eligible_supervised_observations"]),
            "ignored_transition_observations": int(
                linkage["ignored_transition_observations"]
            ),
            "exact_android_features_sha256": linkage["android_features_sha256"],
            "exact_labeled_npz_sha256": linkage["exact_labeled_npz_sha256"],
            "rested_jpeg_rows_retired_from_main_candidate": True,
        },
        "p1_assignments": p1["assignments"],
        "enrichment_rows": enrichment["rows"],
        "normalization": "ALL_AND_ONLY_ROWS_WITH_ROLE_FIT",
        "untouched": {
            "e6_0F747C_S001": True,
            "future_distinct_phone_signer_session": True,
            "protected_test": True,
        },
        "claim_limits": [
            "Internal phone/P1 development is opened same-source evidence, not validation.",
            "Historical DEV is regression-only and is not used for checkpoint selection.",
            "Promotion requires the reserved distinct positive phone signer/session.",
        ],
    }
    freeze_json(OUT / "main_dataset_freeze.json", result)
    return result


def freeze_corrected_main_design() -> dict[str, Any]:
    original = freeze_main_design()
    config = load_main_config()
    excluded = set(config["fit"]["excluded_enrichment_sample_ids"])
    if excluded != {"asl:train:27973404455034934-DRINK 2"}:
        raise RuntimeError("S2_R2_UNEXPECTED_ENRICHMENT_EXCLUSION")
    annotations = {
        row["sample_id"]: row for row in read_json(HUMAN_ANNOTATIONS)["annotations"]
    }
    context = {row["sample_id"]: row for row in _read_csv(PER_SAMPLE_CONTEXT)}
    viability = []
    for source in original["enrichment_rows"]:
        sample_id = source["sample_id"]
        annotation = annotations[sample_id]
        timestamps, _, _ = _video_timestamps(_resolve_source_video(context[sample_id]))
        counts = {}
        for view in config["cadence_views"]:
            indices, _ = p7.sparse_observation_indices(
                timestamps,
                sample_id,
                str(view["view_id"]),
                float(view["target_interval_ms"]),
            )
            labels = temporal_labels(
                timestamps[indices],
                float(annotation["human_sign_start_ms"]),
                float(annotation["human_sign_end_ms"]),
                100.0,
            )
            counts[str(view["view_id"])] = int(np.count_nonzero(labels == 1))
        viability.append({"sample_id": sample_id, "active_count_by_view": counts})
    unviable = {
        row["sample_id"]
        for row in viability
        if any(count == 0 for count in row["active_count_by_view"].values())
    }
    if unviable != excluded:
        raise RuntimeError(f"S2_R2_ENRICHMENT_VIABILITY_DRIFT:{sorted(unviable)}")
    selected = [row for row in original["enrichment_rows"] if row["sample_id"] not in excluded]
    if len(selected) != int(config["fit"]["enrichment_clips"]):
        raise RuntimeError("S2_R2_CORRECTED_ENRICHMENT_COUNT_MISMATCH")
    corrected = {
        **original,
        "schema": "apphear.s2_r2.main_dataset_freeze.v2",
        "status": "CORRECTED_FROZEN_FOR_ONE_CANDIDATE_EXTRACTION",
        "supersedes_sha256": sha256_file(OUT / "main_dataset_freeze.json"),
        "config_path": str(CORRECTED_MAIN_CONFIG.resolve()),
        "config_sha256": sha256_file(CORRECTED_MAIN_CONFIG),
        "fit": {
            **original["fit"],
            "enrichment_clips": len(selected),
            "enrichment_views": len(selected) * len(config["cadence_views"]),
        },
        "enrichment_rows": selected,
        "sparse_label_viability": viability,
        "exclusion": {
            "sample_ids": sorted(excluded),
            "reason": (
                "The human ACTIVE interval is 239 ms; the frozen 100 ms exclusion band "
                "leaves 39 ms eligible, with zero ACTIVE observations in all three "
                "genuine sparse cadence views. Do not relabel sign movement as PRE/POST."
            ),
            "scope": "ONE_HISTORICAL_ENRICHMENT_CLIP_ONLY",
        },
    }
    freeze_json(OUT / "main_dataset_freeze_correction_01.json", corrected)
    return corrected


def _phase7_rows(partitions: set[str]) -> list[dict[str, Any]]:
    result = []
    for row in p7._load_view_rows(partitions):
        role = "FIT" if row["phase7_partition"] == "FIT" else "INTERNAL_DEVELOPMENT"
        result.append(
            {
                **row,
                "row_id": f"phase7::{row['view_key']}",
                "domain": "BASELINE_SIGN",
                "role": role,
                "provenance": "PHASE7_FROZEN_CURRENT_CONTRACT_SPARSE_FEATURE",
            }
        )
    return result


def _exact_phone_rows() -> list[dict[str, Any]]:
    config = load_main_config()
    fit_attempts = set(map(int, config["fit"]["phone_attempts"]))
    dev_attempts = set(map(int, config["internal_development"]["phone_attempts"]))
    rows = _read_csv(EXACT_PHONE_LABELS)
    with np.load(EXACT_PHONE_FEATURES, allow_pickle=False) as data:
        features = np.asarray(data["features"], np.float32)
        labels = np.asarray(data["state_ids"], np.int32)
        timestamps_ns = np.asarray(data["source_timestamps_ns"], np.int64)
        attempts = np.asarray(data["attempt_ordinals"], np.int32)
    if len(rows) != len(features) or len(rows) != 232:
        raise RuntimeError("S2_R2_EXACT_PHONE_ARRAY_ALIGNMENT")
    result = []
    annotations = read_json(EXACT_PHONE_REVIEW / "phone_positive_temporal_annotations.json")
    annotation_by_ordinal = {
        int(item["attempt_ordinal"]): item for item in annotations["annotations"]
    }
    for attempt in range(1, 7):
        selected = np.flatnonzero(attempts == attempt)
        annotation = annotation_by_ordinal[attempt]
        role = "FIT" if attempt in fit_attempts else "INTERNAL_DEVELOPMENT"
        if attempt not in fit_attempts | dev_attempts:
            raise RuntimeError(f"S2_R2_EXACT_PHONE_ROLE_MISSING:{attempt}")
        timestamp_ms = timestamps_ns[selected].astype(np.float64) / 1_000_000.0
        result.append(
            {
                "row_id": f"exact_phone::attempt_{attempt:03d}",
                "sample_id": f"exact_phone:session_20260921T153138Z:attempt_{attempt:03d}",
                "view_key": f"exact_phone::attempt_{attempt:03d}",
                "view_id": "NATIVE_PHONE_CADENCE",
                "domain": "PHONE_POSITIVE",
                "source": "PHONE_EXACT_PARITY_CAPTURE",
                "signer_id": "phone_design:session_20260921T153138Z:S001",
                "role": role,
                "features": features[selected],
                "labels": labels[selected],
                "timestamps_ms": timestamp_ms,
                "human_sign_start_ms": float(
                    annotation["sign_start_source_timestamp_ns"]
                )
                / 1_000_000.0,
                "human_sign_end_ms": float(annotation["sign_end_source_timestamp_ns"])
                / 1_000_000.0,
                "video_duration_ms": float(timestamp_ms[-1] - timestamp_ms[0]),
                "provenance": "EXACT_ANDROID_378_VECTOR_LINKED_TO_HUMAN_REVIEW",
            }
        )
    return result


def _resolve_source_video(row: dict[str, str]) -> Path:
    for key in ("manifest_raw_video_path", "resolved_raw_video_path"):
        path = Path(row[key])
        if path.is_file():
            return path
    raise FileNotFoundError(f"S2_R2_ENRICHMENT_SOURCE_MISSING:{row['sample_id']}")


def _extract_enrichment_rows(
    runtime: Candidate01Offline, selected_sample_ids: set[str]
) -> list[dict[str, Any]]:
    config = load_main_config()
    annotations_doc = read_json(HUMAN_ANNOTATIONS)
    annotations = {
        row["sample_id"]: row
        for row in annotations_doc["annotations"]
        if row["sample_id"] in selected_sample_ids
    }
    context = {
        row["sample_id"]: row
        for row in _read_csv(PER_SAMPLE_CONTEXT)
        if row["sample_id"] in selected_sample_ids
    }
    if set(annotations) != selected_sample_ids or set(context) != selected_sample_ids:
        raise RuntimeError("S2_R2_ENRICHMENT_METADATA_INCOMPLETE")
    result = []
    for sample_id in sorted(selected_sample_ids):
        annotation = annotations[sample_id]
        context_row = context[sample_id]
        path = _resolve_source_video(context_row)
        timestamps, _, orientation = _video_timestamps(path)
        indices_by_view: dict[str, np.ndarray] = {}
        union: set[int] = set()
        for view in config["cadence_views"]:
            indices, _ = p7.sparse_observation_indices(
                timestamps,
                sample_id,
                str(view["view_id"]),
                float(view["target_interval_ms"]),
            )
            indices_by_view[str(view["view_id"])] = indices
            union.update(map(int, indices))
        selected_union = np.asarray(sorted(union), np.int32)
        records = _process_video_indices(
            runtime, path, selected_union, timestamps, orientation
        )
        raw_union = _raw_from_records(
            sample_id,
            str(annotation["source"]),
            str(annotation["signer_id"]),
            records,
        )
        position = {int(original): index for index, original in enumerate(selected_union)}
        for view in config["cadence_views"]:
            view_id = str(view["view_id"])
            local_indices = np.asarray(
                [position[int(original)] for original in indices_by_view[view_id]], np.int32
            )
            sparse = p7.subset_raw(raw_union, local_indices)
            target = temporal_labels(
                sparse.timestamp_ms,
                float(annotation["human_sign_start_ms"]),
                float(annotation["human_sign_end_ms"]),
                100.0,
            )
            if not np.any(target == 1):
                raise RuntimeError(f"S2_R2_ENRICHMENT_VIEW_NO_ACTIVE:{sample_id}:{view_id}")
            result.append(
                {
                    "row_id": f"enrichment::{sample_id}::{view_id}",
                    "sample_id": sample_id,
                    "view_key": f"{sample_id}::{view_id}",
                    "view_id": view_id,
                    "domain": "ENRICHMENT_SIGN",
                    "source": str(annotation["source"]),
                    "signer_id": str(annotation["signer_id"]),
                    "role": "FIT",
                    "features": derive_causal_segmentation_features(sparse),
                    "labels": target,
                    "timestamps_ms": sparse.timestamp_ms,
                    "human_sign_start_ms": float(annotation["human_sign_start_ms"]),
                    "human_sign_end_ms": float(annotation["human_sign_end_ms"]),
                    "video_duration_ms": float(timestamps[-1] - timestamps[0]),
                    "source_video_path": str(path.resolve()),
                    "source_video_sha256": sha256_file(path),
                    "provenance": "ORIGINAL_MP4_REPROCESSED_CURRENT_CANDIDATE01",
                }
            )
    return result


def _decorate_p1_roles(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    design = freeze_main_design()
    role_by_interval = {
        row["interval_id"]: (
            "FIT" if row["role"] == "FIT" else "INTERNAL_DEVELOPMENT"
        )
        for row in design["p1_assignments"]
    }
    for row in rows:
        interval_id = row["row_id"].removeprefix("p1::")
        row["role"] = role_by_interval[interval_id]
        row["sample_id"] = row["row_id"]
        row["view_key"] = row["row_id"]
        row["view_id"] = "VIEW_B"
        row["video_duration_ms"] = float(row["timestamps_ms"][-1] - row["timestamps_ms"][0])
    return rows


def _save_main_rows(rows: list[dict[str, Any]], destination: Path) -> list[dict[str, Any]]:
    saved = _save_rows(rows, destination)
    by_id = {row["row_id"]: row for row in rows}
    for item in saved:
        source = by_id[item["row_id"]]
        for key in (
            "role",
            "sample_id",
            "view_key",
            "view_id",
            "human_sign_start_ms",
            "human_sign_end_ms",
            "video_duration_ms",
            "source_video_path",
            "source_video_sha256",
        ):
            if key in source:
                item[key] = source[key]
    return saved


def prepare_main(smoke: bool = False) -> dict[str, Any]:
    design = freeze_corrected_main_design()
    output = OUT / ("main_smoke" if smoke else "main_candidate")
    destination = output / "features"
    if destination.exists() and any(destination.glob("*.npz")):
        raise RuntimeError(f"S2_R2_MAIN_FEATURES_ALREADY_EXIST:{destination}")

    baseline = _phase7_rows({"FIT", "CAL"})
    enrichment_ids = {row["sample_id"] for row in design["enrichment_rows"]}
    p1_ids = {row["interval_id"] for row in design["p1_assignments"]}
    if smoke:
        fit_rows = [row for row in baseline if row["role"] == "FIT"][:6]
        dev_rows = [row for row in baseline if row["role"] == "INTERNAL_DEVELOPMENT"][:6]
        baseline = fit_rows + dev_rows
        enrichment_ids = {sorted(enrichment_ids)[0]}
        fit_p1 = [
            row["interval_id"] for row in design["p1_assignments"] if row["role"] == "FIT"
        ][:1]
        dev_p1 = [
            row["interval_id"]
            for row in design["p1_assignments"]
            if row["role"] == "INTERNAL_DEVELOPMENT"
        ][:1]
        p1_ids = set(fit_p1 + dev_p1)

    with Candidate01Offline() as runtime:
        enrichment = _extract_enrichment_rows(runtime, enrichment_ids)
        p1_rows = _decorate_p1_roles(_extract_p1_rows(runtime, p1_ids))
    exact_phone = _exact_phone_rows()
    rows = baseline + enrichment + p1_rows + exact_phone
    manifest_rows = _save_main_rows(rows, destination)
    if not smoke:
        expected = {
            "total": 366,
            "FIT": 302,
            "INTERNAL_DEVELOPMENT": 64,
        }
        measured = {
            "total": len(manifest_rows),
            "FIT": sum(row["role"] == "FIT" for row in manifest_rows),
            "INTERNAL_DEVELOPMENT": sum(
                row["role"] == "INTERNAL_DEVELOPMENT" for row in manifest_rows
            ),
        }
        if measured != expected:
            raise RuntimeError(f"S2_R2_CORRECTED_POPULATION_MISMATCH:{measured}")
    summary = {
        "schema": "apphear.s2_r2.main_prepared_dataset.v1",
        "milestone": MILESTONE,
        "purpose": "SMOKE_ONLY" if smoke else "ONE_MAIN_CANDIDATE",
        "feature_contract": {"schema": SEGMENTATION_FEATURE_SCHEMA, "width": FEATURE_WIDTH},
        "config_sha256": sha256_file(CORRECTED_MAIN_CONFIG),
        "dataset_freeze_sha256": sha256_file(OUT / "main_dataset_freeze_correction_01.json"),
        "row_count": len(manifest_rows),
        "fit_row_count": sum(row["role"] == "FIT" for row in manifest_rows),
        "internal_development_row_count": sum(
            row["role"] == "INTERNAL_DEVELOPMENT" for row in manifest_rows
        ),
        "domain_row_counts": dict(
            sorted(Counter(row["domain"] for row in manifest_rows).items())
        ),
        "role_domain_row_counts": {
            f"{role}:{domain}": count
            for (role, domain), count in sorted(
                Counter((row["role"], row["domain"]) for row in manifest_rows).items()
            )
        },
        "rows": manifest_rows,
        "exact_phone_features_used": True,
        "jpeg_phone_features_used": False,
        "protected_test_accessed": False,
    }
    freeze_json(output / "dataset_manifest.json", summary)
    return {"status": "S2_R2_MAIN_DATA_PREPARED", **summary}


def _load_main_rows(smoke: bool) -> list[dict[str, Any]]:
    output = OUT / ("main_smoke" if smoke else "main_candidate")
    manifest_path = output / "dataset_manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(
            "S2_R2_PREPARE_MAIN_REQUIRED: dataset preparation has not completed; "
            "do not start train-main until prepare-main succeeds"
        )
    manifest = read_json(manifest_path)
    if not smoke and manifest.get("config_sha256") != sha256_file(CORRECTED_MAIN_CONFIG):
        raise RuntimeError("S2_R2_MAIN_PREPARATION_CONFIG_MISMATCH")
    result = []
    for row in manifest["rows"]:
        path = Path(row["feature_path"])
        if sha256_file(path) != row["feature_sha256"]:
            raise RuntimeError(f"S2_R2_MAIN_FEATURE_IDENTITY:{path}")
        with np.load(path, allow_pickle=False) as data:
            result.append(
                {
                    **row,
                    "features": np.asarray(data["features"], np.float32),
                    "labels": np.asarray(data["labels"], np.int32),
                    "timestamps_ms": np.asarray(data["timestamps_ms"], np.float64),
                }
            )
    return result


def _pack_main_rows(
    rows: list[dict[str, Any]], mean: np.ndarray, std: np.ndarray, config: dict[str, Any]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    max_length = max(len(row["labels"]) for row in rows)
    x = np.zeros((len(rows), max_length, FEATURE_WIDTH), np.float32)
    y = np.zeros((len(rows), max_length), np.int32)
    weights = np.zeros((len(rows), max_length), np.float32)
    counts = Counter(
        (row["domain"], int(label))
        for row in rows
        for label in row["labels"]
        if int(label) != IGNORE_LABEL
    )
    domain_classes = {
        domain: sorted(label for candidate, label in counts if candidate == domain)
        for domain in {row["domain"] for row in rows}
    }
    domain_weight = config["training"]["source_family_weight"]
    if set(domain_classes) != set(domain_weight):
        raise RuntimeError("S2_R2_MAIN_DOMAIN_WEIGHT_COVERAGE")
    for row_index, row in enumerate(rows):
        length = len(row["labels"])
        x[row_index, :length] = apply_normalization(row["features"], mean, std)
        valid = row["labels"] != IGNORE_LABEL
        y[row_index, :length] = np.where(valid, row["labels"], 0)
        for index, (label, keep) in enumerate(zip(row["labels"], valid, strict=True)):
            if keep:
                domain = row["domain"]
                weights[row_index, index] = float(domain_weight[domain]) / (
                    len(domain_classes[domain]) * counts[(domain, int(label))]
                )
    positive = weights[weights > 0]
    weights[weights > 0] /= float(np.mean(positive))
    audit = {
        "domain_classes": {
            domain: [LABEL_NAMES[index] for index in classes]
            for domain, classes in sorted(domain_classes.items())
        },
        "domain_class_counts": {
            f"{domain}:{LABEL_NAMES[label]}": count
            for (domain, label), count in sorted(counts.items())
        },
        "configured_source_family_weight": domain_weight,
    }
    return x, y, weights, audit


def _decoder_config(config: dict[str, Any]) -> StreamingDecoderConfig:
    values = config["decoder"]
    return StreamingDecoderConfig(
        minimum_active_ms=float(values["minimum_active_ms"]),
        pre_gap_reset_ms=float(values["pre_gap_reset_ms"]),
        post_confirm_ms=float(values["post_confirm_ms"]),
        pre_padding_ms=float(values["pre_padding_ms"]),
        post_padding_ms=float(values["post_padding_ms"]),
        rearm_pre_stable_ms=float(values["rearm_pre_stable_ms"]),
    )


def _evaluate_main_model(
    model: Any,
    rows: list[dict[str, Any]],
    mean: np.ndarray,
    std: np.ndarray,
    config: dict[str, Any],
) -> dict[str, Any]:
    predictions: dict[str, np.ndarray] = {}
    probabilities: dict[str, np.ndarray] = {}
    for row in rows:
        normalized = apply_normalization(row["features"], mean, std)
        probability = softmax(np.asarray(model(normalized[None], training=False))[0])
        probabilities[row["row_id"]] = probability
        predictions[row["row_id"]] = np.argmax(probability, axis=1).astype(np.int32)
    phone = [row for row in rows if row["domain"] == "PHONE_POSITIVE"]
    p1_rows = [row for row in rows if row["domain"] == "P1_NEGATIVE"]
    cal = [row for row in rows if row["domain"] == "BASELINE_SIGN"]
    phone_state = state_metrics(
        [row["labels"] for row in phone], [predictions[row["row_id"]] for row in phone]
    )
    p1_state = state_metrics(
        [row["labels"] for row in p1_rows],
        [predictions[row["row_id"]] for row in p1_rows],
    )
    decoder_config = _decoder_config(config)
    cal_events = []
    for row in cal:
        decoder = run_decoder(
            row["timestamps_ms"],
            probabilities[row["row_id"]],
            predictions[row["row_id"]],
            decoder_config,
        )
        cal_events.append(event_metrics_for_row(row, decoder))
    p1_event_count = 0
    for row in p1_rows:
        decoder = run_decoder(
            row["timestamps_ms"],
            probabilities[row["row_id"]],
            predictions[row["row_id"]],
            decoder_config,
        )
        p1_event_count += len(decoder.events)
    p1_matrix = p1_state["confusion_matrix_rows_actual_columns_predicted"]
    p1_support = sum(p1_matrix[0])
    return {
        "phone_state": phone_state,
        "p1_state": p1_state,
        "p1_active_false_rate": p1_matrix[0][1] / p1_support if p1_support else 0.0,
        "p1_event_count": p1_event_count,
        "p1_event_rate": p1_event_count / len(p1_rows) if p1_rows else 0.0,
        "cal_state": state_metrics(
            [row["labels"] for row in cal],
            [predictions[row["row_id"]] for row in cal],
        ),
        "cal_events": aggregate_event_metrics(cal_events),
    }


def _main_gate_checks(metrics: dict[str, Any], config: dict[str, Any]) -> dict[str, bool]:
    gates = config["checkpoint_gates"]
    phone_active = metrics["phone_state"]["per_class"]["ACTIVE_SIGN"]["recall"]
    cal = metrics["cal_events"]
    return {
        "phone_internal_active_recall": phone_active
        >= float(gates["minimum_phone_internal_active_recall"]),
        "p1_internal_active_false_rate": metrics["p1_active_false_rate"]
        <= float(gates["maximum_p1_internal_active_false_rate"]),
        "p1_internal_event_rate": metrics["p1_event_rate"]
        <= float(gates["maximum_p1_internal_event_rate"]),
        "cal_event_emission_rate": cal["event_emission_rate"]
        >= float(gates["minimum_cal_event_emission_rate"]),
        "cal_exactly_one_event_rate": cal["exactly_one_event_rate"]
        >= float(gates["minimum_cal_exactly_one_event_rate"]),
        "cal_severe_cut_rate": cal["severe_cut_rate"]
        <= float(gates["maximum_cal_severe_cut_rate"]),
    }


def _main_checkpoint_key(metrics: dict[str, Any]) -> tuple[float, ...]:
    cal = metrics["cal_events"]
    phone_active = metrics["phone_state"]["per_class"]["ACTIVE_SIGN"]["recall"]
    return (
        float(phone_active),
        -float(metrics["p1_event_rate"]),
        -float(metrics["p1_active_false_rate"]),
        float(cal["event_emission_rate"]),
        float(cal["exactly_one_event_rate"]),
        float(cal["containment_rate"]),
        -float(cal["severe_cut_rate"]),
    )


def train_main(smoke: bool = False) -> dict[str, Any]:
    config = load_main_config()
    output = OUT / ("main_smoke" if smoke else "main_candidate")
    model_path = output / ("smoke_model.keras" if smoke else "best_model.keras")
    history_path = output / ("smoke_result.json" if smoke else "training_result.json")
    if model_path.exists() or history_path.exists():
        raise RuntimeError(f"S2_R2_SINGLE_RUN_ALREADY_EXECUTED:{output}")
    rows = _load_main_rows(smoke)
    fit_rows = [row for row in rows if row["role"] == "FIT"]
    development_rows = [row for row in rows if row["role"] == "INTERNAL_DEVELOPMENT"]
    if not fit_rows or not development_rows:
        raise RuntimeError("S2_R2_MAIN_ROLE_EMPTY")
    stats = normalization_from_train([row["features"] for row in fit_rows])
    normalization = {
        "schema": "apphear.s2_r2.fit_normalization.v1",
        "purpose": "SMOKE_ONLY" if smoke else "S2_R2_DEPLOYMENT_PACKAGE",
        "feature_schema": SEGMENTATION_FEATURE_SCHEMA,
        "fit_row_ids": [row["row_id"] for row in fit_rows],
        "fit_observation_count": sum(len(row["labels"]) for row in fit_rows),
        "mean": stats["mean"].astype(float).tolist(),
        "std": stats["std"].astype(float).tolist(),
        "cal_dev_validation_influenced_statistics": False,
    }
    freeze_json(output / "normalization.json", normalization)
    x, y, sample_weight, weighting_audit = _pack_main_rows(
        fit_rows, stats["mean"], stats["std"], config
    )

    import tensorflow as tf

    seed = int(config["seed"])
    tf.keras.utils.set_random_seed(seed)
    tf.config.experimental.enable_op_determinism()
    model = build_model(read_json(PHASE7_CONFIG))
    if model.count_params() != 123_779:
        raise RuntimeError(f"S2_R2_MAIN_PARAMETER_MISMATCH:{model.count_params()}")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(float(config["training"]["learning_rate"])),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        weighted_metrics=[tf.keras.metrics.SparseCategoricalAccuracy(name="state_accuracy")],
    )

    class MainCheckpoint(tf.keras.callbacks.Callback):
        def __init__(self) -> None:
            super().__init__()
            self.best_key: tuple[float, ...] | None = None
            self.best_epoch: int | None = None
            self.records: list[dict[str, Any]] = []

        def on_epoch_end(self, epoch: int, logs: dict[str, float] | None = None) -> None:
            metrics = _evaluate_main_model(
                self.model, development_rows, stats["mean"], stats["std"], config
            )
            checks = _main_gate_checks(metrics, config)
            eligible = all(checks.values())
            key = _main_checkpoint_key(metrics)
            improved = eligible and (self.best_key is None or key > self.best_key)
            if improved:
                self.best_key = key
                self.best_epoch = epoch + 1
                self.model.save(model_path, overwrite=True)
            self.records.append(
                {
                    "epoch": epoch + 1,
                    "fit_logs": {
                        name: float(value) for name, value in (logs or {}).items()
                    },
                    "eligible": eligible,
                    "gate_checks": checks,
                    "checkpoint_key": list(key),
                    "development_metrics": metrics,
                    "saved_as_best": improved,
                }
            )
            print(
                f"s2-r2-check epoch={epoch + 1} eligible={eligible} key={key} best={improved}",
                flush=True,
            )

    callback = MainCheckpoint()
    epochs = 2 if smoke else int(config["training"]["epochs"])
    history = model.fit(
        x,
        y,
        sample_weight=sample_weight,
        batch_size=int(config["training"]["batch_size"]),
        epochs=epochs,
        shuffle=True,
        verbose=2,
        callbacks=[callback],
    )
    if smoke and not model_path.exists():
        model.save(model_path, overwrite=True)
    if not smoke and callback.best_epoch is None:
        diagnostic_path = output / "final_ineligible_model.keras"
        model.save(diagnostic_path, overwrite=True)
    selected_model = (
        tf.keras.models.load_model(model_path, compile=False)
        if model_path.exists()
        else model
    )
    candidate = _evaluate_main_model(
        selected_model, development_rows, stats["mean"], stats["std"], config
    )
    baseline_norm = read_json(PHASE7_NORM)
    baseline_model = tf.keras.models.load_model(PHASE7_MODEL, compile=False)
    baseline = _evaluate_main_model(
        baseline_model,
        development_rows,
        np.asarray(baseline_norm["mean"], np.float32),
        np.asarray(baseline_norm["std"], np.float32),
        config,
    )
    result = {
        "schema": "apphear.s2_r2.training_result.v1",
        "milestone": MILESTONE,
        "status": (
            "S2_R2_SMOKE_PASS"
            if smoke and np.all(np.isfinite(history.history["loss"]))
            else "S2_R2_CANDIDATE_SUPPORTED"
            if callback.best_epoch is not None
            else "S2_R2_CANDIDATE_NOT_SUPPORTED"
        ),
        "smoke": smoke,
        "main_training_run_consumed": not smoke,
        "seed": seed,
        "epochs_completed": len(history.history["loss"]),
        "best_epoch": callback.best_epoch,
        "best_checkpoint_key": list(callback.best_key or ()),
        "normalization_sha256": sha256_file(output / "normalization.json"),
        "model_sha256": sha256_file(model_path) if model_path.exists() else None,
        "weighting_audit": weighting_audit,
        "baseline_frozen_s2": baseline,
        "candidate": candidate,
        "candidate_gate_checks": _main_gate_checks(candidate, config),
        "epoch_records": callback.records,
        "keras_history": {
            name: [float(value) for value in values]
            for name, values in history.history.items()
        },
        "protected_test_accessed": False,
        "untouched_validation_consumed": False,
    }
    freeze_json(history_path, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "freeze-governance",
            "prepare-sanity",
            "run-sanity",
            "freeze-main",
            "prepare-main-smoke",
            "train-main-smoke",
            "prepare-main",
            "train-main",
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "freeze-governance":
        result = freeze_governance()
    elif args.command == "prepare-sanity":
        result = prepare_sanity()
    elif args.command == "run-sanity":
        result = run_sanity()
    elif args.command == "freeze-main":
        result = freeze_main_design()
    elif args.command == "prepare-main-smoke":
        result = prepare_main(smoke=True)
    elif args.command == "train-main-smoke":
        result = train_main(smoke=True)
    elif args.command == "prepare-main":
        result = prepare_main(smoke=False)
    else:
        result = train_main(smoke=False)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
