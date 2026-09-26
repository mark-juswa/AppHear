"""Freeze and review the bounded Phase 5.1T-2 segmentation seed dataset.

This utility consumes only the governed recognition TRAIN audit produced by Phase 5.1T-0.
It freezes selection and a signer-disjoint segmentation split before intersecting immutable
Phase 5.1T-1 human annotations.  The browser receives no D1 timing before a new human
annotation is committed.  No recognition feature, prediction, DEV, TEST, phone holdout, or
model-training path is opened by this module.
"""

# The embedded single-file local review UI intentionally keeps HTML/CSS/JS lines intact.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import statistics
import threading
import webbrowser
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from eval.runtime_diagnostics.phase5_1t_human_temporal_review import (
    frame_index_to_ms,
    probe_video,
    sha256_file,
)
from pipeline.perception_vnext.governance import EXPECTED, TRAIN_MANIFEST, load_rows

ROOT = Path(__file__).resolve().parents[2]
MILESTONE = "PHASE_5_1T_2_BOUNDED_SEGMENTATION_SEED_DATASET_01"
MANIFEST_SCHEMA = "apphear.phase5_1t.seed_selection.v1"
SPLIT_SCHEMA = "apphear.phase5_1t.segmentation_split.v1"
ANNOTATION_SCHEMA = "apphear.phase5_1t.seed_human_annotations.v1"
TOOL_VERSION = "phase5.1t-2-bounded-seed-v1"
SELECTION_SEED = "PHASE_5_1T_2_BOUNDED_SEGMENTATION_SEED_DATASET_01"
EXPECTED_TOTAL = 120
MINIMUM_USABLE = 100
TARGET_SOURCE_COUNTS = {"ASL_CITIZEN": 90, "APPHEAR_CAPTURE": 12, "LOCAL": 18}
ASL_MIN_PRE_MS = 500.0
ASL_MIN_POST_MS = 750.0
CONTEXT_AVAILABLE_MS = 250.0
TARGET_DEV_CLIPS = 24
MAX_ASL_PER_SIGNER = 6
MAX_ASL_PER_GLOSS = 2
BANNED_PHONE_ATTEMPTS = ("attempt_004", "attempt_006", "attempt_008", "attempt_010")

ARTIFACT_BASE = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
)
READINESS_ROOT = ARTIFACT_BASE / "phase5_1t_0_segmentation_data_readiness_audit_01"
READINESS_TABLE = READINESS_ROOT / "per_sample_context.csv"
PHASE5_1T_1_ROOT = ARTIFACT_BASE / "phase5_1t_1_human_temporal_semantics_validation_01"
PHASE5_1T_1_ANNOTATIONS = PHASE5_1T_1_ROOT / "human_annotations.json"
OUTPUT_ROOT = ARTIFACT_BASE / "phase5_1t_2_bounded_segmentation_seed_dataset_01"

SELECTED_NAME = "selected_120_manifest.json"
SPLIT_NAME = "frozen_segmentation_split.json"
ANNOTATIONS_NAME = "segmentation_human_annotations.json"
DERIVED_NAME = "derived_temporal_metadata.csv"
SUMMARY_NAME = "selection_summary.json"
REPORT_NAME = "SEGMENTATION_SEED_DATASET_REPORT.md"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _atomic_json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _freeze_json(path: Path, payload: Any) -> None:
    """Create a frozen JSON artifact once, or prove an existing artifact is identical."""

    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8-sig"))
        if existing != payload:
            raise RuntimeError(f"FROZEN_ARTIFACT_MISMATCH:{path}")
        return
    _atomic_json_write(path, payload)


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _stable_digest(value: str) -> str:
    return hashlib.sha256(f"{SELECTION_SEED}|{value}".encode()).hexdigest()


def _truth(value: object) -> bool:
    return str(value).strip().casefold() == "true"


def _number(row: dict[str, Any], field: str) -> float:
    value = row.get(field)
    if value in (None, ""):
        raise ValueError(f"MISSING_NUMERIC_FIELD:{field}:{row.get('sample_id')}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"NONFINITE_NUMERIC_FIELD:{field}:{row.get('sample_id')}")
    return result


def validate_governed_train_population(
    audit_rows: Sequence[dict[str, str]], train_rows: Sequence[dict[str, str]]
) -> None:
    if len(audit_rows) != EXPECTED["train_clips"] or len(train_rows) != EXPECTED["train_clips"]:
        raise RuntimeError(
            f"TRAIN_COUNT_MISMATCH:{len(audit_rows)}:{len(train_rows)}:{EXPECTED['train_clips']}"
        )
    audit_ids = [row["sample_id"] for row in audit_rows]
    train_ids = [row["sample_id"] for row in train_rows]
    if len(audit_ids) != len(set(audit_ids)) or len(train_ids) != len(set(train_ids)):
        raise RuntimeError("DUPLICATE_TRAIN_SAMPLE_ID")
    if set(audit_ids) != set(train_ids):
        raise RuntimeError("READINESS_TRAIN_MEMBERSHIP_MISMATCH")
    if any(
        row.get("split") != "train"
        or row.get("role") not in {"primary_train", "supplement_train"}
        or not _truth(row.get("training_eligible"))
        for row in train_rows
    ):
        raise RuntimeError("PROTECTED_OR_NONTRAIN_POPULATION_REJECTED")
    if any(
        token in (row["sample_id"] + " " + row.get("resolved_raw_video_path", "")).casefold()
        for row in audit_rows
        for token in BANNED_PHONE_ATTEMPTS
    ):
        raise RuntimeError("SEALED_PHONE_HOLDOUT_PRESENT")


def _duration_bucket(duration_ms: float) -> str:
    for ceiling in (500.0, 750.0, 1000.0, 1500.0):
        if duration_ms < ceiling:
            return f"lt_{int(ceiling)}"
    return "ge_1500"


def _candidate_key(
    row: dict[str, Any],
    *,
    gloss_counts: Counter[str],
    duration_counts: Counter[str],
    enforce_gloss_cap: bool,
) -> tuple[Any, ...]:
    gloss = str(row["gloss"])
    active_duration = (
        _number(row, "active_span_duration_ms")
        if row.get("active_span_duration_ms") not in (None, "")
        else _number(row, "raw_video_duration_ms")
    )
    bucket = _duration_bucket(active_duration)
    if row["source"] == "ASL_CITIZEN":
        temporal_room = min(
            _number(row, "pre_context_ms") - ASL_MIN_PRE_MS,
            _number(row, "post_context_ms") - ASL_MIN_POST_MS,
        )
    else:
        temporal_room = _number(row, "raw_video_duration_ms")
    return (
        gloss_counts[gloss] > 0,
        enforce_gloss_cap and gloss_counts[gloss] >= MAX_ASL_PER_GLOSS,
        duration_counts[bucket],
        -temporal_room,
        _stable_digest(str(row["sample_id"])),
        str(row["sample_id"]),
    )


def select_diverse_rows(
    rows: Sequence[dict[str, Any]],
    *,
    count: int,
    max_per_signer: int | None,
    enforce_gloss_cap: bool,
) -> list[dict[str, Any]]:
    """Select by least-used signer, then unseen gloss, room, and duration diversity."""

    by_signer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_signer[str(row["signer_id"])].append(dict(row))
    signer_counts: Counter[str] = Counter()
    gloss_counts: Counter[str] = Counter()
    duration_counts: Counter[str] = Counter()
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    while len(selected) < count:
        eligible_signers = [
            signer
            for signer, candidates in by_signer.items()
            if any(str(row["sample_id"]) not in selected_ids for row in candidates)
            and (max_per_signer is None or signer_counts[signer] < max_per_signer)
        ]
        if not eligible_signers:
            raise RuntimeError(f"INSUFFICIENT_DIVERSE_CANDIDATES:{len(selected)}/{count}")
        signer = min(
            eligible_signers,
            key=lambda value: (signer_counts[value], _stable_digest(value), value),
        )
        candidates = [
            row
            for row in by_signer[signer]
            if str(row["sample_id"]) not in selected_ids
        ]
        row = min(
            candidates,
            key=lambda item: _candidate_key(
                item,
                gloss_counts=gloss_counts,
                duration_counts=duration_counts,
                enforce_gloss_cap=enforce_gloss_cap,
            ),
        )
        selected.append(row)
        selected_ids.add(str(row["sample_id"]))
        signer_counts[signer] += 1
        gloss = str(row["gloss"])
        gloss_counts[gloss] += 1
        active_duration = (
            _number(row, "active_span_duration_ms")
            if row.get("active_span_duration_ms") not in (None, "")
            else _number(row, "raw_video_duration_ms")
        )
        duration_counts[_duration_bucket(active_duration)] += 1
    return selected


def deterministic_selection(audit_rows: Sequence[dict[str, str]]) -> list[dict[str, Any]]:
    readable = [row for row in audit_rows if _truth(row.get("video_readable"))]
    asl = [
        row
        for row in readable
        if row["source"] == "ASL_CITIZEN"
        and _truth(row.get("context_valid"))
        and _number(row, "pre_context_ms") >= ASL_MIN_PRE_MS
        and _number(row, "post_context_ms") >= ASL_MIN_POST_MS
    ]
    apphear = [row for row in readable if row["source"] == "APPHEAR_CAPTURE"]
    local = [row for row in readable if row["source"] == "LOCAL"]
    selected = (
        select_diverse_rows(
            asl,
            count=TARGET_SOURCE_COUNTS["ASL_CITIZEN"],
            max_per_signer=MAX_ASL_PER_SIGNER,
            enforce_gloss_cap=True,
        )
        + select_diverse_rows(
            apphear,
            count=TARGET_SOURCE_COUNTS["APPHEAR_CAPTURE"],
            max_per_signer=None,
            enforce_gloss_cap=False,
        )
        + select_diverse_rows(
            local,
            count=TARGET_SOURCE_COUNTS["LOCAL"],
            max_per_signer=None,
            enforce_gloss_cap=False,
        )
    )
    source_rank = {source: index for index, source in enumerate(TARGET_SOURCE_COUNTS)}
    selected.sort(
        key=lambda row: (
            source_rank[str(row["source"])],
            _stable_digest(str(row["signer_id"])),
            str(row["signer_id"]),
            _stable_digest(str(row["sample_id"])),
            str(row["sample_id"]),
        )
    )
    if len(selected) != EXPECTED_TOTAL or len({row["sample_id"] for row in selected}) != len(
        selected
    ):
        raise RuntimeError("SELECTED_TOTAL_OR_DUPLICATE_FAILURE")
    return selected


def choose_dev_signers(selected: Sequence[dict[str, Any]]) -> tuple[set[str], dict[str, Any]]:
    source_signers: dict[str, Counter[str]] = defaultdict(Counter)
    for row in selected:
        source_signers[str(row["source"])][str(row["signer_id"])] += 1
    apphear_signers = set(source_signers["APPHEAR_CAPTURE"])
    if len(apphear_signers) != 1:
        raise RuntimeError(f"APPHEAR_SINGLE_SIGNER_CONTRACT:{sorted(apphear_signers)}")
    local_signers = sorted(
        source_signers["LOCAL"], key=lambda signer: (_stable_digest(signer), signer)
    )
    if not local_signers:
        raise RuntimeError("LOCAL_DEV_SIGNER_UNAVAILABLE")
    local_dev = local_signers[0]
    local_dev_count = source_signers["LOCAL"][local_dev]
    asl_signers = sorted(
        source_signers["ASL_CITIZEN"], key=lambda signer: (_stable_digest(signer), signer)
    )
    # Dynamic programming retains one deterministic subset for each (clip sum, signer count).
    states: dict[tuple[int, int], tuple[str, ...]] = {(0, 0): ()}
    for signer in asl_signers:
        additions: dict[tuple[int, int], tuple[str, ...]] = {}
        for (clip_sum, count), subset in states.items():
            key = (clip_sum + source_signers["ASL_CITIZEN"][signer], count + 1)
            candidate = subset + (signer,)
            if key not in states and (key not in additions or candidate < additions[key]):
                additions[key] = candidate
        states.update(additions)
    candidates = [
        (clip_sum, signer_count, subset)
        for (clip_sum, signer_count), subset in states.items()
        if signer_count >= 3 and signer_count < len(asl_signers)
    ]
    if not candidates:
        raise RuntimeError("ASL_DEV_SIGNER_SUBSET_UNAVAILABLE")
    asl_dev_clips, _, asl_dev = min(
        candidates,
        key=lambda item: (
            abs(local_dev_count + item[0] - TARGET_DEV_CLIPS),
            abs(item[1] - 6),
            item[1],
            tuple((_stable_digest(signer), signer) for signer in item[2]),
        ),
    )
    dev_signers = set(asl_dev) | {local_dev}
    if dev_signers & apphear_signers:
        raise RuntimeError("APPHEAR_SIGNER_MUST_REMAIN_TRAIN")
    return dev_signers, {
        "target_dev_clips": TARGET_DEV_CLIPS,
        "actual_dev_clips": local_dev_count + asl_dev_clips,
        "held_out_asl_signers": list(asl_dev),
        "held_out_local_signers": [local_dev],
        "apphear_capture_signers_forced_train": sorted(apphear_signers),
    }


def _selection_row(row: dict[str, Any], rank: int, split: str) -> dict[str, Any]:
    return {
        "sample_id": row["sample_id"],
        "source": row["source"],
        "signer_id": row["signer_id"],
        "gloss": row["gloss"],
        "class_id": int(row["class_id"]),
        "source_video_path": row["resolved_raw_video_path"],
        "video_duration_ms": _number(row, "raw_video_duration_ms"),
        "segmentation_split": split,
        "selection_rank": rank,
        "selection_basis": (
            "D1_ROOM_SELECTION_ONLY_HUMAN_BOUNDARY_REQUIRED"
            if row["source"] == "ASL_CITIZEN"
            else "FULL_VIDEO_HUMAN_BOUNDARY_REQUIRED"
        ),
        "candidate_pre_context_ms": (
            _number(row, "pre_context_ms") if row["source"] == "ASL_CITIZEN" else None
        ),
        "candidate_post_context_ms": (
            _number(row, "post_context_ms") if row["source"] == "ASL_CITIZEN" else None
        ),
        "candidate_active_duration_ms": (
            _number(row, "active_span_duration_ms")
            if row["source"] == "ASL_CITIZEN"
            else None
        ),
        "governed_d1_span_path": (
            row["resolved_span_path"] if row["source"] == "ASL_CITIZEN" else None
        ),
    }


def validate_selected_rows(rows: Sequence[dict[str, Any]], train_ids: set[str]) -> None:
    if len(rows) != EXPECTED_TOTAL or len(rows) > 120:
        raise RuntimeError(f"SELECTED_TOTAL_INVALID:{len(rows)}")
    ids = [str(row["sample_id"]) for row in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("DUPLICATE_SELECTED_SAMPLE")
    if not set(ids).issubset(train_ids):
        raise RuntimeError("SELECTED_SAMPLE_OUTSIDE_GOVERNED_TRAIN")
    if Counter(str(row["source"]) for row in rows) != Counter(TARGET_SOURCE_COUNTS):
        raise RuntimeError("SELECTED_SOURCE_COMPOSITION_MISMATCH")
    split_signers: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        split = str(row["segmentation_split"])
        if split not in {"SEGMENTATION_TRAIN", "SEGMENTATION_DEV"}:
            raise RuntimeError(f"INVALID_SEGMENTATION_SPLIT:{split}")
        split_signers[split].add(str(row["signer_id"]))
        if any(token in str(row["sample_id"]).casefold() for token in BANNED_PHONE_ATTEMPTS):
            raise RuntimeError("SEALED_PHONE_HOLDOUT_SELECTED")
    overlap = split_signers["SEGMENTATION_TRAIN"] & split_signers["SEGMENTATION_DEV"]
    if overlap:
        raise RuntimeError(f"SEGMENTATION_SIGNER_OVERLAP:{sorted(overlap)}")
    apphear_splits = {
        row["segmentation_split"] for row in rows if row["source"] == "APPHEAR_CAPTURE"
    }
    if apphear_splits != {"SEGMENTATION_TRAIN"}:
        raise RuntimeError("APPHEAR_CAPTURE_NOT_ENTIRELY_TRAIN")


def _manifest_document(rows: Sequence[dict[str, Any]], frozen_at: str) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "milestone": MILESTONE,
        "tool_version": TOOL_VERSION,
        "selection_seed": SELECTION_SEED,
        "frozen_at_utc": frozen_at,
        "sample_count": len(rows),
        "selection_is_recognition_train_only": True,
        "d1_role": "ASL_CITIZEN candidate temporal-room filter only; never a human target",
        "rows": list(rows),
    }


def _split_document(rows: Sequence[dict[str, Any]], split_meta: dict[str, Any], frozen_at: str) -> dict[str, Any]:
    train_signers = sorted(
        {row["signer_id"] for row in rows if row["segmentation_split"] == "SEGMENTATION_TRAIN"}
    )
    dev_signers = sorted(
        {row["signer_id"] for row in rows if row["segmentation_split"] == "SEGMENTATION_DEV"}
    )
    train_glosses = {
        row["gloss"] for row in rows if row["segmentation_split"] == "SEGMENTATION_TRAIN"
    }
    dev_glosses = {
        row["gloss"] for row in rows if row["segmentation_split"] == "SEGMENTATION_DEV"
    }
    return {
        "schema": SPLIT_SCHEMA,
        "milestone": MILESTONE,
        "frozen_at_utc": frozen_at,
        "split_frozen_before_annotation_intersection": True,
        "train_sample_ids": [
            row["sample_id"] for row in rows if row["segmentation_split"] == "SEGMENTATION_TRAIN"
        ],
        "dev_sample_ids": [
            row["sample_id"] for row in rows if row["segmentation_split"] == "SEGMENTATION_DEV"
        ],
        "train_signers": train_signers,
        "dev_signers": dev_signers,
        "signer_overlap": sorted(set(train_signers) & set(dev_signers)),
        "train_clip_count": sum(row["segmentation_split"] == "SEGMENTATION_TRAIN" for row in rows),
        "dev_clip_count": sum(row["segmentation_split"] == "SEGMENTATION_DEV" for row in rows),
        "dev_glosses_absent_from_train": sorted(dev_glosses - train_glosses),
        **split_meta,
    }


def _load_prior_annotations() -> tuple[dict[str, dict[str, Any]], str]:
    payload = json.loads(PHASE5_1T_1_ANNOTATIONS.read_text(encoding="utf-8-sig"))
    if payload.get("status") != "FINALIZED" or payload.get("expected_sample_count") != 24:
        raise RuntimeError("PHASE5_1T_1_ANNOTATIONS_NOT_FINALIZED")
    annotations = payload.get("annotations")
    if not isinstance(annotations, list) or len(annotations) != 24:
        raise RuntimeError("PHASE5_1T_1_ANNOTATION_COUNT_MISMATCH")
    by_id = {str(item["sample_id"]): item for item in annotations}
    if len(by_id) != len(annotations):
        raise RuntimeError("PHASE5_1T_1_DUPLICATE_ANNOTATION")
    return by_id, sha256_file(PHASE5_1T_1_ANNOTATIONS)


def _reused_annotation(row: dict[str, Any], prior: dict[str, Any]) -> dict[str, Any]:
    if (
        prior["source"] != row["source"]
        or prior["signer_id"] != row["signer_id"]
        or prior["gloss"] != row["gloss"]
    ):
        raise RuntimeError(f"PHASE5_1T_1_REUSE_IDENTITY_MISMATCH:{row['sample_id']}")
    annotation: dict[str, Any] = {
        "sample_id": row["sample_id"],
        "source": row["source"],
        "signer_id": row["signer_id"],
        "gloss": row["gloss"],
        "source_video_path": row["source_video_path"],
        "video_duration_ms": row["video_duration_ms"],
        "segmentation_split": row["segmentation_split"],
        "human_sign_start_ms": prior.get("human_sign_start_ms"),
        "human_sign_end_ms": prior.get("human_sign_end_ms"),
        "ambiguous_or_unusable": bool(prior["ambiguous_or_unusable"]),
        "annotation_reused_from_phase5_1t_1": True,
        "reviewer_note": str(prior.get("reviewer_note", "")),
        "review_timestamp": prior["review_timestamp"],
        "reuse_source_schema": prior["schema"],
        "reuse_source_tool_version": prior["tool_version"],
        "tool_version": TOOL_VERSION,
        "schema": ANNOTATION_SCHEMA,
    }
    for field in (
        "d1_onset_ms",
        "d1_release_ms",
        "human_minus_d1_start_ms",
        "human_minus_d1_end_ms",
    ):
        if field in prior:
            annotation[field] = prior[field]
    return annotation


def _empty_annotation_document(
    *, manifest_sha256: str, split_sha256: str, rows: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    prior, prior_sha = _load_prior_annotations()
    reused = [_reused_annotation(row, prior[row["sample_id"]]) for row in rows if row["sample_id"] in prior]
    order = {row["sample_id"]: index for index, row in enumerate(rows)}
    reused.sort(key=lambda item: order[item["sample_id"]])
    return {
        "schema": ANNOTATION_SCHEMA,
        "milestone": MILESTONE,
        "tool_version": TOOL_VERSION,
        "selected_manifest_sha256": manifest_sha256,
        "frozen_split_sha256": split_sha256,
        "expected_sample_count": EXPECTED_TOTAL,
        "created_after_selection_and_split_freeze_utc": _utc_now(),
        "phase5_1t_1_annotations_sha256": prior_sha,
        "status": "IN_PROGRESS" if len(reused) < EXPECTED_TOTAL else "COMPLETE_PENDING_FINALIZE",
        "annotations": reused,
    }


def load_annotation_document(
    path: Path, *, manifest_sha256: str, split_sha256: str
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload.get("schema") != ANNOTATION_SCHEMA:
        raise ValueError("ANNOTATION_SCHEMA_MISMATCH")
    if payload.get("selected_manifest_sha256") != manifest_sha256:
        raise ValueError("ANNOTATION_MANIFEST_IDENTITY_MISMATCH")
    if payload.get("frozen_split_sha256") != split_sha256:
        raise ValueError("ANNOTATION_SPLIT_IDENTITY_MISMATCH")
    annotations = payload.get("annotations")
    if not isinstance(annotations, list):
        raise ValueError("ANNOTATIONS_NOT_LIST")
    ids = [item.get("sample_id") for item in annotations]
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_SAVED_ANNOTATION")
    return payload


def _load_d1_diagnostic(row: dict[str, Any]) -> dict[str, float]:
    if row["source"] != "ASL_CITIZEN":
        raise ValueError("D1_DIAGNOSTIC_ONLY_FOR_ASL_CITIZEN")
    span_path = Path(str(row["governed_d1_span_path"]))
    payload = json.loads(span_path.read_text(encoding="utf-8-sig"))
    onset = int(payload["onset"])
    release = int(payload["release"])
    fps = float(payload["native_fps"])
    if not bool(payload["valid"]) or onset < 0 or release < onset:
        raise ValueError(f"INVALID_D1_SPAN:{row['sample_id']}")
    return {
        "d1_onset_ms": frame_index_to_ms(onset, fps),
        "d1_release_ms": frame_index_to_ms(release, fps, end_exclusive=True),
    }


def validate_annotation_input(payload: dict[str, Any], duration_ms: float) -> dict[str, Any]:
    ambiguous = payload.get("ambiguous_or_unusable")
    if not isinstance(ambiguous, bool):
        raise ValueError("BOOLEAN_JUDGMENT_REQUIRED:ambiguous_or_unusable")
    start = payload.get("human_sign_start_ms")
    end = payload.get("human_sign_end_ms")
    if start is None or end is None:
        if not ambiguous:
            raise ValueError("BOUNDARIES_REQUIRED_UNLESS_AMBIGUOUS")
        start_ms = end_ms = None
    else:
        start_ms, end_ms = float(start), float(end)
        if not math.isfinite(start_ms) or not math.isfinite(end_ms):
            raise ValueError("NONFINITE_BOUNDARY")
        if start_ms < 0.0 or start_ms >= end_ms or end_ms > duration_ms:
            raise ValueError("INVALID_BOUNDARY_START_MUST_PRECEDE_END")
    return {
        "human_sign_start_ms": start_ms,
        "human_sign_end_ms": end_ms,
        "ambiguous_or_unusable": ambiguous,
        "reviewer_note": str(payload.get("reviewer_note", "")).strip()[:500],
    }


def commit_annotation(
    *,
    rows: Sequence[dict[str, Any]],
    annotation_path: Path,
    manifest_sha256: str,
    split_sha256: str,
    sample_index: int,
    payload: dict[str, Any],
    video_metadata: Sequence[dict[str, float | int]],
    now: datetime | None = None,
) -> dict[str, Any]:
    if sample_index < 0 or sample_index >= len(rows):
        raise IndexError("SAMPLE_INDEX_OUT_OF_RANGE")
    row = rows[sample_index]
    document = load_annotation_document(
        annotation_path, manifest_sha256=manifest_sha256, split_sha256=split_sha256
    )
    if any(item["sample_id"] == row["sample_id"] for item in document["annotations"]):
        raise ValueError("ANNOTATION_ALREADY_COMMITTED_IMMUTABLE")
    validated = validate_annotation_input(payload, float(video_metadata[sample_index]["duration_ms"]))
    annotation: dict[str, Any] = {
        "sample_id": row["sample_id"],
        "source": row["source"],
        "signer_id": row["signer_id"],
        "gloss": row["gloss"],
        "source_video_path": row["source_video_path"],
        "video_duration_ms": row["video_duration_ms"],
        "segmentation_split": row["segmentation_split"],
        **validated,
        "annotation_reused_from_phase5_1t_1": False,
        "review_timestamp": (now or datetime.now(UTC)).isoformat(),
        "tool_version": TOOL_VERSION,
        "schema": ANNOTATION_SCHEMA,
    }
    if row["source"] == "ASL_CITIZEN":
        diagnostic = _load_d1_diagnostic(row)
        annotation.update(diagnostic)
        if validated["human_sign_start_ms"] is None:
            annotation["human_minus_d1_start_ms"] = None
            annotation["human_minus_d1_end_ms"] = None
        else:
            annotation["human_minus_d1_start_ms"] = validated["human_sign_start_ms"] - diagnostic["d1_onset_ms"]
            annotation["human_minus_d1_end_ms"] = validated["human_sign_end_ms"] - diagnostic["d1_release_ms"]
    document["annotations"].append(annotation)
    order = {item["sample_id"]: index for index, item in enumerate(rows)}
    document["annotations"].sort(key=lambda item: order[item["sample_id"]])
    document["status"] = (
        "COMPLETE_PENDING_FINALIZE"
        if len(document["annotations"]) == len(rows)
        else "IN_PROGRESS"
    )
    _atomic_json_write(annotation_path, document)
    return annotation


def public_state(
    rows: Sequence[dict[str, Any]],
    document: dict[str, Any],
    video_metadata: Sequence[dict[str, float | int]],
) -> dict[str, Any]:
    """Return browser state without any uncommitted D1 or D1-derived field."""

    saved = {item["sample_id"]: item for item in document["annotations"]}
    samples: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        item: dict[str, Any] = {
            "index": index,
            "sample_id": row["sample_id"],
            "source": row["source"],
            "signer_id": row["signer_id"],
            "gloss": row["gloss"],
            "segmentation_split": row["segmentation_split"],
            "duration_ms": video_metadata[index]["duration_ms"],
            "fps": video_metadata[index]["fps"],
            "video_url": f"/video/{index}",
            "committed": row["sample_id"] in saved,
        }
        if item["committed"]:
            item["annotation"] = saved[row["sample_id"]]
        samples.append(item)
    return {
        "schema": ANNOTATION_SCHEMA,
        "tool_version": TOOL_VERSION,
        "progress": {
            "committed": len(saved),
            "remaining": len(rows) - len(saved),
            "total": len(rows),
        },
        "samples": samples,
    }


def _distribution(values: Iterable[float]) -> dict[str, float | int | None]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {"count": 0, "min": None, "median": None, "max": None}
    return {
        "count": len(ordered),
        "min": ordered[0],
        "median": statistics.median(ordered),
        "max": ordered[-1],
    }


def derive_temporal_rows(
    rows: Sequence[dict[str, Any]], document: dict[str, Any]
) -> list[dict[str, Any]]:
    saved = {item["sample_id"]: item for item in document["annotations"]}
    derived: list[dict[str, Any]] = []
    for row in rows:
        annotation = saved.get(row["sample_id"])
        ambiguous = None if annotation is None else bool(annotation["ambiguous_or_unusable"])
        usable = bool(
            annotation is not None
            and not ambiguous
            and annotation.get("human_sign_start_ms") is not None
            and annotation.get("human_sign_end_ms") is not None
        )
        if usable:
            start = float(annotation["human_sign_start_ms"])
            end = float(annotation["human_sign_end_ms"])
            pre = start
            post = float(row["video_duration_ms"]) - end
        else:
            start = end = pre = post = None
        derived.append(
            {
                "sample_id": row["sample_id"],
                "source": row["source"],
                "signer_id": row["signer_id"],
                "gloss": row["gloss"],
                "source_video_path": row["source_video_path"],
                "video_duration_ms": row["video_duration_ms"],
                "segmentation_split": row["segmentation_split"],
                "human_sign_start_ms": start,
                "human_sign_end_ms": end,
                "actual_pre_margin_ms": pre,
                "actual_post_margin_ms": post,
                "pre_context_available": None if pre is None else pre >= CONTEXT_AVAILABLE_MS,
                "post_context_available": None if post is None else post >= CONTEXT_AVAILABLE_MS,
                "ambiguous_or_unusable": ambiguous,
                "usable_for_supervision": usable,
                "annotation_reused_from_phase5_1t_1": (
                    None if annotation is None else annotation["annotation_reused_from_phase5_1t_1"]
                ),
                "reviewer_note": None if annotation is None else annotation.get("reviewer_note", ""),
                "d1_onset_ms": None if annotation is None else annotation.get("d1_onset_ms"),
                "d1_release_ms": None if annotation is None else annotation.get("d1_release_ms"),
                "annotation_status": "PENDING" if annotation is None else "COMMITTED",
            }
        )
    return derived


def _write_derived_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("DERIVED_ROWS_EMPTY")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _awaiting_report(summary: dict[str, Any]) -> str:
    return f"""# Phase 5.1T-2 Bounded Segmentation Seed Dataset

Milestone: `{MILESTONE}`

Status: **AWAITING HUMAN REVIEW**

The deterministic `{summary['selected_total']}`-sample manifest and signer-disjoint segmentation
split are frozen. `{summary['reused_annotations']}` immutable Phase-5.1T-1 annotations were
naturally reused; `{summary['new_annotations_required']}` selected samples require a new blinded
human annotation. No sample will be replaced because it is difficult or unusable.

## Frozen population

- Sources: `{summary['source_counts']}`
- Segmentation TRAIN/DEV: `{summary['split_counts']}`
- TRAIN/DEV signer overlap: `0`
- Unique glosses: `{summary['unique_glosses']}`
- DEV glosses absent from segmentation TRAIN: `{summary['dev_glosses_absent_from_train']}`

## Governance

Recognition TRAIN only: YES. Recognition DEV accessed: NO. Protected TEST accessed: NO.
Phase-5 phone holdout accessed: NO. Recognizer accessed: NO. Model training executed: NO.
Candidate01, Recognition V2, the 236-class recognizer, source videos, and D1 span files are
unchanged. D1 remains hidden before each new ASL_CITIZEN human commit.

The guarded finalizer refuses to classify the seed until all 120 selected samples are committed.
"""


def _final_report(summary: dict[str, Any]) -> str:
    return f"""# Phase 5.1T-2 Bounded Segmentation Seed Dataset

Milestone: `{MILESTONE}`

## A. Deterministic selection

Selection used only the Phase-5.1T-0 recognition-TRAIN audit. It applied signer-round-robin
selection first, unseen-gloss preference second, minimum ASL candidate room (500 ms PRE / 750 ms
POST) third, source composition fourth, and broad duration buckets as a final diversity term.
D1 was selection-only metadata and never a human target.

## B–F. Frozen population and split

- Selected: `{summary['selected_total']}`; sources `{summary['source_counts']}`
- Split counts: `{summary['split_counts']}`
- Segmentation TRAIN signers: `{summary['train_signers']}`
- Segmentation DEV signers: `{summary['dev_signers']}`
- Signer overlap: `0`
- Unique glosses: `{summary['unique_glosses']}`
- DEV glosses absent from segmentation TRAIN: `{summary['dev_glosses_absent_from_train']}`

## G–K. Human labels and temporal geometry

- Phase-5.1T-1 annotations reused immutably: `{summary['reused_annotations']}`
- New annotations completed: `{summary['new_annotations_completed']}`
- Usable / unusable: `{summary['usable_total']}` / `{summary['unusable_total']}`
- Usable by split: `{summary['usable_by_split']}`
- Source supervision summary: `{summary['context_by_source']}`
- Usable with >=250 ms PRE: `{summary['pre_context_available']}`
- Usable with >=250 ms POST: `{summary['post_context_available']}`
- PRE margin distribution (ms): `{summary['pre_margin_distribution_ms']}`
- POST margin distribution (ms): `{summary['post_margin_distribution_ms']}`
- Unusable selected rows: `{summary['unusable_samples']}`

## L. Integrity and governance

All selected samples are exact governed recognition TRAIN members. The segmentation split was
frozen before historical-label intersection and has zero signer overlap. Recognition DEV,
protected TEST, and phone attempts 004/006/008/010 were not accessed. D1 remained hidden until
human commit. Ambiguous rows are excluded from supervision. No recognizer was accessed and no
model was trained. Candidate01, Recognition V2, the recognizer, Android, source videos, and span
files are unchanged.

## M–N. Evidence state and stop boundary

**`{summary['final_evidence_state']}`**

**`{summary['next_stop_boundary']}`**
"""


def _source_hashes(paths: Sequence[Path]) -> dict[str, Any]:
    return {
        "schema": "APPHEAR_PHASE5_1T_2_SOURCE_HASHES_V1",
        "generated_at_utc": _utc_now(),
        "files": [
            {"path": str(path.resolve()), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in sorted(paths, key=lambda item: str(item).casefold())
            if path.is_file()
        ],
    }


def prepare(output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    """Freeze selection/split, then and only then intersect historical annotations."""

    audit_rows = _load_csv(READINESS_TABLE)
    train_rows = load_rows(TRAIN_MANIFEST)
    validate_governed_train_population(audit_rows, train_rows)
    selected_raw = deterministic_selection(audit_rows)
    dev_signers, split_meta = choose_dev_signers(selected_raw)
    rows = [
        _selection_row(
            row,
            rank=index,
            split=(
                "SEGMENTATION_DEV"
                if str(row["signer_id"]) in dev_signers
                else "SEGMENTATION_TRAIN"
            ),
        )
        for index, row in enumerate(selected_raw)
    ]
    validate_selected_rows(rows, {row["sample_id"] for row in train_rows})
    output_root.mkdir(parents=True, exist_ok=True)
    selected_path = output_root / SELECTED_NAME
    split_path = output_root / SPLIT_NAME
    frozen_at = (
        str(json.loads(selected_path.read_text(encoding="utf-8-sig"))["frozen_at_utc"])
        if selected_path.exists()
        else _utc_now()
    )
    _freeze_json(selected_path, _manifest_document(rows, frozen_at))
    _freeze_json(split_path, _split_document(rows, split_meta, frozen_at))
    manifest_sha = sha256_file(selected_path)
    split_sha = sha256_file(split_path)
    annotation_path = output_root / ANNOTATIONS_NAME
    if not annotation_path.exists():
        # Historical annotations are read only after both freeze artifacts exist and are hashed.
        _atomic_json_write(
            annotation_path,
            _empty_annotation_document(
                manifest_sha256=manifest_sha,
                split_sha256=split_sha,
                rows=rows,
            ),
        )
    document = load_annotation_document(
        annotation_path, manifest_sha256=manifest_sha, split_sha256=split_sha
    )
    metadata = [probe_video(Path(str(row["source_video_path"]))) for row in rows]
    for row, video in zip(rows, metadata, strict=True):
        if abs(float(row["video_duration_ms"]) - float(video["duration_ms"])) > 80.0:
            raise RuntimeError(f"VIDEO_DURATION_DRIFT:{row['sample_id']}")
    derived = derive_temporal_rows(rows, document)
    _write_derived_csv(output_root / DERIVED_NAME, derived)
    split_doc = json.loads(split_path.read_text(encoding="utf-8-sig"))
    summary = {
        "schema": "apphear.phase5_1t.seed_selection_summary.v1",
        "milestone": MILESTONE,
        "status": "AWAITING_HUMAN_REVIEW",
        "selected_manifest_sha256": manifest_sha,
        "frozen_split_sha256": split_sha,
        "selected_total": len(rows),
        "source_counts": dict(sorted(Counter(row["source"] for row in rows).items())),
        "split_counts": dict(sorted(Counter(row["segmentation_split"] for row in rows).items())),
        "source_signer_counts": {
            source: len({row["signer_id"] for row in rows if row["source"] == source})
            for source in TARGET_SOURCE_COUNTS
        },
        "unique_glosses": len({row["gloss"] for row in rows}),
        "train_signers": split_doc["train_signers"],
        "dev_signers": split_doc["dev_signers"],
        "signer_overlap": [],
        "dev_glosses_absent_from_train": split_doc["dev_glosses_absent_from_train"],
        "reused_annotations": sum(
            bool(item["annotation_reused_from_phase5_1t_1"])
            for item in document["annotations"]
        ),
        "new_annotations_required": len(rows)
        - sum(
            bool(item["annotation_reused_from_phase5_1t_1"])
            for item in document["annotations"]
        ),
        "committed_annotations": len(document["annotations"]),
        "remaining_annotations": len(rows) - len(document["annotations"]),
        "freeze_order": [
            SELECTED_NAME,
            SPLIT_NAME,
            "historical_annotation_intersection",
        ],
        "governance": {
            "recognition_train_only": True,
            "recognition_dev_accessed": False,
            "protected_test_accessed": False,
            "phase5_phone_holdout_accessed": False,
            "recognizer_accessed": False,
            "model_training_executed": False,
            "candidate01_modified": False,
            "recognition_v2_modified": False,
            "recognizer_modified": False,
            "android_modified": False,
        },
    }
    summary_path = output_root / SUMMARY_NAME
    report_path = output_root / REPORT_NAME
    if document.get("status") == "FINALIZED":
        if not summary_path.is_file() or not report_path.is_file():
            raise RuntimeError("FINALIZED_REPORT_ARTIFACT_MISSING")
        finalized_summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
        if finalized_summary.get("status") != "FINALIZED":
            raise RuntimeError("FINALIZED_ANNOTATIONS_SUMMARY_STATE_MISMATCH")
        summary = finalized_summary
    else:
        _atomic_json_write(summary_path, summary)
        report_path.write_text(_awaiting_report(summary), encoding="utf-8")
    tool_snapshot = output_root / "human_review_tool_source.py"
    shutil.copyfile(Path(__file__).resolve(), tool_snapshot)
    sources = [
        Path(__file__).resolve(),
        tool_snapshot,
        ROOT / "tests/test_phase5_1t_bounded_seed_dataset.py",
        READINESS_TABLE,
        TRAIN_MANIFEST,
        PHASE5_1T_1_ANNOTATIONS,
        selected_path,
        split_path,
    ]
    _atomic_json_write(output_root / "source_hashes.json", _source_hashes(sources))
    test_results_path = output_root / "test_results.json"
    if not test_results_path.exists():
        _atomic_json_write(
            test_results_path,
            {
                "schema": "apphear.phase5_1t.seed_test_results.v1",
                "status": "STRUCTURAL_VALIDATION_PASS_PYTEST_PENDING",
                "checks": {
                    "selected_total_le_120": len(rows) <= 120,
                    "recognition_train_membership_only": True,
                    "zero_signer_overlap": True,
                    "split_frozen_before_annotation_intersection": True,
                    "d1_blinding_enabled": True,
                    "recognizer_accessed": False,
                    "model_training_executed": False,
                },
            },
        )
    return {
        "rows": rows,
        "metadata": metadata,
        "document": document,
        "summary": summary,
        "manifest_sha256": manifest_sha,
        "split_sha256": split_sha,
    }


def finalize(output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    prepared = prepare(output_root)
    rows = prepared["rows"]
    document = load_annotation_document(
        output_root / ANNOTATIONS_NAME,
        manifest_sha256=prepared["manifest_sha256"],
        split_sha256=prepared["split_sha256"],
    )
    if len(document["annotations"]) != EXPECTED_TOTAL:
        raise RuntimeError(f"HUMAN_REVIEW_INCOMPLETE:{len(document['annotations'])}/{EXPECTED_TOTAL}")
    expected_order = [row["sample_id"] for row in rows]
    actual_order = [item["sample_id"] for item in document["annotations"]]
    if actual_order != expected_order:
        raise RuntimeError("ANNOTATION_ORDER_OR_MEMBERSHIP_MISMATCH")
    derived = derive_temporal_rows(rows, document)
    _write_derived_csv(output_root / DERIVED_NAME, derived)
    usable = [row for row in derived if row["usable_for_supervision"]]
    unusable = [row for row in derived if not row["usable_for_supervision"]]
    evidence = (
        "SEGMENTATION_SEED_READY"
        if len(usable) >= MINIMUM_USABLE
        else "SEGMENTATION_SEED_BELOW_MINIMUM_USABLE"
    )
    next_boundary = (
        "WAIT_FOR_PROJECT_LEAD_PHASE_5_1T_3_FIRST_SEGMENTER_TRAINING_DECISION"
        if evidence == "SEGMENTATION_SEED_READY"
        else "WAIT_FOR_PROJECT_LEAD_DIAGNOSIS"
    )
    summary = dict(prepared["summary"])
    context_by_source: dict[str, Any] = {}
    for source in TARGET_SOURCE_COUNTS:
        source_rows = [row for row in derived if row["source"] == source]
        source_usable = [row for row in source_rows if row["usable_for_supervision"]]
        context_by_source[source] = {
            "selected": len(source_rows),
            "usable": len(source_usable),
            "unusable": len(source_rows) - len(source_usable),
            "pre_context_available": sum(
                bool(row["pre_context_available"]) for row in source_usable
            ),
            "post_context_available": sum(
                bool(row["post_context_available"]) for row in source_usable
            ),
        }
    summary.update(
        {
            "status": "FINALIZED",
            "new_annotations_completed": sum(
                not bool(item["annotation_reused_from_phase5_1t_1"])
                for item in document["annotations"]
            ),
            "usable_total": len(usable),
            "unusable_total": len(unusable),
            "usable_by_source": dict(sorted(Counter(row["source"] for row in usable).items())),
            "unusable_by_source": dict(sorted(Counter(row["source"] for row in unusable).items())),
            "usable_by_split": dict(
                sorted(Counter(row["segmentation_split"] for row in usable).items())
            ),
            "context_by_source": context_by_source,
            "unusable_samples": [
                {
                    "sample_id": row["sample_id"],
                    "source": row["source"],
                    "signer_id": row["signer_id"],
                    "gloss": row["gloss"],
                    "segmentation_split": row["segmentation_split"],
                    "reviewer_note": row["reviewer_note"],
                }
                for row in unusable
            ],
            "pre_context_available": sum(bool(row["pre_context_available"]) for row in usable),
            "post_context_available": sum(bool(row["post_context_available"]) for row in usable),
            "pre_margin_distribution_ms": _distribution(
                float(row["actual_pre_margin_ms"]) for row in usable
            ),
            "post_margin_distribution_ms": _distribution(
                float(row["actual_post_margin_ms"]) for row in usable
            ),
            "final_evidence_state": evidence,
            "next_stop_boundary": next_boundary,
        }
    )
    _atomic_json_write(output_root / SUMMARY_NAME, summary)
    (output_root / REPORT_NAME).write_text(_final_report(summary), encoding="utf-8")
    document["status"] = "FINALIZED"
    document["final_evidence_state"] = evidence
    document["next_stop_boundary"] = next_boundary
    _atomic_json_write(output_root / ANNOTATIONS_NAME, document)
    return summary


HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>AppHear Phase 5.1T-2 Seed Review</title><style>
body{font:15px system-ui;margin:0;background:#111827;color:#e5e7eb}main{max-width:1050px;margin:auto;padding:20px}.top,.panel{background:#1f2937;border:1px solid #374151;border-radius:10px;padding:14px;margin-bottom:14px}video{width:100%;max-height:60vh;background:#000}.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}button{padding:9px 13px;border:0;border-radius:7px;background:#2563eb;color:white;cursor:pointer}button:disabled{opacity:.45}.secondary{background:#4b5563}.commit{background:#059669}.danger{color:#fca5a5}.good{color:#86efac}fieldset{border:1px solid #4b5563;border-radius:8px;margin:10px 0}label{margin-right:14px}input[type=number],textarea{background:#111827;color:#fff;border:1px solid #4b5563;border-radius:6px;padding:7px}textarea{width:98%;height:55px}.time{font:18px ui-monospace,monospace}.hint{color:#cbd5e1;font-size:13px}</style></head><body><main>
<div class="top"><b>Phase 5.1T-2 — bounded segmentation seed review</b><div id="progress"></div><div class="hint">Mark a practical interval containing the meaningful sign while excluding obvious preparation/recovery where reasonably possible. Do not repeatedly micro-adjust. D1 is hidden until each ASL_CITIZEN commit.</div></div>
<div class="panel"><div id="identity"></div><video id="video" controls preload="metadata"></video><div class="row"><button class="secondary" onclick="step(-1)">◀ 1 frame</button><button class="secondary" onclick="step(1)">1 frame ▶</button><span class="time" id="clock">0.000 s</span></div><div class="row"><button onclick="mark('start')">Mark SIGN START</button><input id="start" type="number" step="1" readonly> ms <button onclick="mark('end')">Mark SIGN END</button><input id="end" type="number" step="1" readonly> ms</div></div>
<div class="panel"><fieldset><legend>ambiguous_or_unusable</legend><label><input type="radio" name="ambiguous" value="yes">YES</label><label><input type="radio" name="ambiguous" value="no">NO</label></fieldset><label>Optional note</label><br><textarea id="note" maxlength="500"></textarea><div id="d1" class="hint"></div><div id="message"></div><div class="row"><button class="secondary" onclick="move(-1)">Previous</button><button class="commit" id="save" onclick="save()">Commit immutable annotation</button><button class="secondary" onclick="move(1)">Next</button></div></div>
</main><script>
let state,index=0;const video=document.getElementById('video');const val=()=>{const x=document.querySelector('input[name=ambiguous]:checked');return x?x.value==='yes':null};async function boot(){state=await(await fetch('/api/state')).json();const first=state.samples.findIndex(x=>!x.committed);index=first<0?0:first;render()}function render(){const s=state.samples[index];document.getElementById('progress').textContent=`${state.progress.committed}/${state.progress.total} committed · ${state.progress.remaining} remaining · sample ${index+1}/${state.samples.length}`;document.getElementById('identity').textContent=`${s.sample_id} · ${s.source} · ${s.segmentation_split} · signer ${s.signer_id} · gloss ${s.gloss}`;video.src=s.video_url;document.querySelectorAll('input[name=ambiguous]').forEach(x=>{x.checked=false;x.disabled=s.committed});for(const id of ['start','end','note']){document.getElementById(id).value='';document.getElementById(id).disabled=s.committed}document.getElementById('save').disabled=s.committed;document.getElementById('d1').textContent='D1 diagnostic hidden until human commit.';document.getElementById('message').textContent='';if(s.committed){const a=s.annotation;document.getElementById('start').value=a.human_sign_start_ms??'';document.getElementById('end').value=a.human_sign_end_ms??'';document.getElementById('note').value=a.reviewer_note;document.querySelector(`input[name=ambiguous][value=${a.ambiguous_or_unusable?'yes':'no'}]`).checked=true;document.getElementById('d1').textContent=a.source==='ASL_CITIZEN'?`Committed. D1 diagnostic: ${a.d1_onset_ms.toFixed(1)}–${a.d1_release_ms.toFixed(1)} ms.`:'Committed. No D1 span for this source.'}}video.ontimeupdate=()=>document.getElementById('clock').textContent=`${video.currentTime.toFixed(3)} s`;function mark(which){if(!state.samples[index].committed)document.getElementById(which).value=Math.round(video.currentTime*1000)}function step(direction){const fps=state.samples[index].fps;video.pause();video.currentTime=Math.max(0,Math.min(video.duration||1e9,video.currentTime+direction/fps))}function move(delta){index=Math.max(0,Math.min(state.samples.length-1,index+delta));render()}function msg(text,bad){const el=document.getElementById('message');el.textContent=text;el.className=bad?'danger':'good'}async function save(){const ambiguous=val();if(ambiguous===null){msg('Choose YES or NO for ambiguous/unusable.',true);return}const start=document.getElementById('start').value,end=document.getElementById('end').value;if((!start||!end)&&!ambiguous){msg('Mark START and END, or mark ambiguous/unusable YES.',true);return}if(start&&end&&Number(start)>=Number(end)){msg('START must be before END.',true);return}if(!confirm('Commit this approximate annotation? The human annotation is immutable after commit.'))return;const body={human_sign_start_ms:start?Number(start):null,human_sign_end_ms:end?Number(end):null,ambiguous_or_unusable:ambiguous,reviewer_note:document.getElementById('note').value};const response=await fetch(`/api/annotations/${index}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const result=await response.json();if(!response.ok){msg(result.error||'Save failed',true);return}state=await(await fetch('/api/state')).json();render();msg('Committed and saved.',false)}boot();
</script></body></html>"""


class ReviewApplication:
    def __init__(self, output_root: Path) -> None:
        prepared = prepare(output_root)
        self.rows: list[dict[str, Any]] = prepared["rows"]
        self.metadata: list[dict[str, float | int]] = prepared["metadata"]
        self.annotation_path = output_root / ANNOTATIONS_NAME
        self.manifest_sha256 = prepared["manifest_sha256"]
        self.split_sha256 = prepared["split_sha256"]
        self.lock = threading.Lock()

    def state(self) -> dict[str, Any]:
        document = load_annotation_document(
            self.annotation_path,
            manifest_sha256=self.manifest_sha256,
            split_sha256=self.split_sha256,
        )
        return public_state(self.rows, document, self.metadata)

    def commit(self, index: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return commit_annotation(
                rows=self.rows,
                annotation_path=self.annotation_path,
                manifest_sha256=self.manifest_sha256,
                split_sha256=self.split_sha256,
                sample_index=index,
                payload=payload,
                video_metadata=self.metadata,
            )


def make_handler(application: ReviewApplication) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "AppHearPhase5_1T2SeedReview/1"

        def _json(self, payload: Any, status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/":
                body = HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/api/state":
                self._json(application.state())
                return
            if parsed.path.startswith("/video/"):
                try:
                    index = int(parsed.path.rsplit("/", 1)[1])
                    row = application.rows[index]
                except (ValueError, IndexError):
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self._video(Path(str(row["source_video_path"])))
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def _video(self, path: Path) -> None:
            size = path.stat().st_size
            start, end = 0, size - 1
            range_header = self.headers.get("Range")
            if range_header:
                try:
                    unit, spec = range_header.split("=", 1)
                    if unit != "bytes":
                        raise ValueError
                    left, right = spec.split("-", 1)
                    start = int(left) if left else 0
                    end = int(right) if right else size - 1
                    end = min(end, size - 1)
                    if start < 0 or start > end:
                        raise ValueError
                except ValueError:
                    self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    return
            length = end - start + 1
            self.send_response(HTTPStatus.PARTIAL_CONTENT if range_header else HTTPStatus.OK)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            if range_header:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            with path.open("rb") as stream:
                stream.seek(start)
                remaining = length
                while remaining:
                    block = stream.read(min(1024 * 1024, remaining))
                    if not block:
                        break
                    self.wfile.write(block)
                    remaining -= len(block)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if not parsed.path.startswith("/api/annotations/"):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                index = int(parsed.path.rsplit("/", 1)[1])
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 100_000:
                    raise ValueError("INVALID_REQUEST_LENGTH")
                payload = json.loads(self.rfile.read(length))
                annotation = application.commit(index, payload)
                self._json({"status": "COMMITTED", "annotation": annotation})
            except (IndexError, ValueError, json.JSONDecodeError) as error:
                self._json({"error": str(error)}, status=400)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def serve(output_root: Path, host: str, port: int, open_browser: bool) -> int:
    application = ReviewApplication(output_root)
    server = ThreadingHTTPServer((host, port), make_handler(application))
    url = f"http://{host}:{port}/"
    print(f"Review interface: {url}")
    print(f"Annotations: {application.annotation_path}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "serve", "finalize"))
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        prepared = prepare(args.output_root)
        print(json.dumps(prepared["summary"], indent=2))
        return 0
    if args.command == "serve":
        return serve(args.output_root, args.host, args.port, not args.no_browser)
    summary = finalize(args.output_root)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
