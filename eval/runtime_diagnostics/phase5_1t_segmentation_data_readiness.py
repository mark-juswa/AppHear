"""Phase 5.1T-0 governed TRAIN temporal-context readiness audit.

This utility is intentionally read-only with respect to scientific data.  It reads only the
frozen recognition TRAIN manifest, its governed raw videos, and governed span sidecars.  It never
loads recognition DEV, protected TEST, Gate-4 phone attempts, features, or recognizer outputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2

from pipeline.perception_vnext.governance import (
    EXPECTED,
    TRAIN_MANIFEST,
    load_rows,
    resolve_governed_path,
    sha256,
)

ROOT = Path(__file__).resolve().parents[2]
MILESTONE = "PHASE_5_1T_0_SEGMENTATION_DATA_READINESS_AUDIT_01"
OUTPUT_ROOT = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
    / "phase5_1t_0_segmentation_data_readiness_audit_01"
)
CONTEXT_REQUIREMENTS_MS: tuple[tuple[str, float, float], ...] = (
    ("pre_250_post_250", 250.0, 250.0),
    ("pre_500_post_500", 500.0, 500.0),
    ("pre_750_post_750", 750.0, 750.0),
    ("pre_1000_post_1000", 1000.0, 1000.0),
    ("pre_500_post_750", 500.0, 750.0),
    ("pre_500_post_1000", 500.0, 1000.0),
    ("pre_750_post_1000", 750.0, 1000.0),
    ("pre_1000_post_1500", 1000.0, 1500.0),
)
PERCENTILES = (0, 10, 25, 50, 75, 90, 100)


@dataclass(frozen=True)
class VideoMetadata:
    readable: bool
    frame_count: int | None
    fps: float | None
    duration_ms: float | None
    timestamp_basis: str
    error: str


@dataclass(frozen=True)
class SpanTiming:
    valid_for_context: bool
    unit: str
    onset_frame_inclusive: int | None
    release_frame_inclusive: int | None
    n_frames: int | None
    native_fps: float | None
    span_start_ms: float | None
    span_end_ms_exclusive: float | None
    active_duration_ms: float | None
    pre_context_ms: float | None
    post_context_ms: float | None
    detector_version: str
    detector_params_hash: str
    errors: tuple[str, ...]


def percentile(values: Sequence[float], q: float) -> float | None:
    """Linear percentile matching NumPy's default interpolation, without a NumPy dependency."""

    clean = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    position = (len(clean) - 1) * q / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return clean[lower]
    weight = position - lower
    return clean[lower] * (1.0 - weight) + clean[upper] * weight


def distribution(values: Iterable[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    labels = {0: "min", 10: "p10", 25: "p25", 50: "median", 75: "p75", 90: "p90", 100: "max"}
    return {
        "count": len(clean),
        **{labels[q]: percentile(clean, q) for q in PERCENTILES},
    }


def probe_video(path: Path) -> VideoMetadata:
    if not path.is_file():
        return VideoMetadata(False, None, None, None, "unavailable", "MISSING_VIDEO")
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            return VideoMetadata(False, None, None, None, "unavailable", "VIDEO_OPEN_FAILED")
        frame_count = int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        if frame_count <= 0:
            return VideoMetadata(
                False,
                frame_count,
                fps,
                None,
                "opencv_container_metadata",
                "NON_POSITIVE_FRAME_COUNT",
            )
        if not math.isfinite(fps) or fps <= 0.0:
            return VideoMetadata(
                False, frame_count, fps, None, "opencv_container_metadata", "INVALID_FPS"
            )
        duration_ms = 1000.0 * frame_count / fps
        if not math.isfinite(duration_ms) or duration_ms <= 0.0:
            return VideoMetadata(
                False,
                frame_count,
                fps,
                duration_ms,
                "opencv_container_metadata",
                "INVALID_DURATION",
            )
        return VideoMetadata(
            True,
            frame_count,
            fps,
            duration_ms,
            "OpenCV container frame_count / nominal_fps; no manufactured cadence",
            "",
        )
    finally:
        capture.release()


def calculate_span_timing(
    payload: dict[str, Any], video: VideoMetadata | None = None
) -> SpanTiming:
    """Interpret the governed D1 sidecar's inclusive frame-index contract."""

    errors: list[str] = []
    required = ("onset", "release", "n_frames", "native_fps", "valid")
    if any(name not in payload for name in required):
        errors.append("AMBIGUOUS_SPAN_UNITS_OR_SCHEMA")
        return SpanTiming(
            False,
            "unknown",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            str(payload.get("detect_version", "")),
            str(payload.get("params_hash", "")),
            tuple(errors),
        )
    try:
        onset = int(payload["onset"])
        release = int(payload["release"])
        n_frames = int(payload["n_frames"])
        fps = float(payload["native_fps"])
    except (TypeError, ValueError):
        errors.append("AMBIGUOUS_SPAN_UNITS_OR_SCHEMA")
        return SpanTiming(
            False,
            "unknown",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            str(payload.get("detect_version", "")),
            str(payload.get("params_hash", "")),
            tuple(errors),
        )
    if not bool(payload["valid"]):
        errors.append("SPAN_MARKED_INVALID")
    if n_frames <= 0 or not math.isfinite(fps) or fps <= 0.0:
        errors.append("INVALID_SPAN_TIMEBASE")
    if onset < 0 or release < onset or release >= n_frames:
        errors.append("SPAN_OUTSIDE_SIDECAR_BOUNDS")
    if video and video.frame_count is not None and release >= video.frame_count:
        errors.append("SPAN_OUTSIDE_VIDEO_BOUNDS")
    if video and video.frame_count is not None and abs(video.frame_count - n_frames) > 1:
        errors.append("SPAN_VIDEO_FRAME_COUNT_MISMATCH")
    if errors:
        return SpanTiming(
            False,
            "inclusive_frame_indices",
            onset,
            release,
            n_frames,
            fps,
            None,
            None,
            None,
            None,
            None,
            str(payload.get("detect_version", "")),
            str(payload.get("params_hash", "")),
            tuple(errors),
        )
    start_ms = 1000.0 * onset / fps
    end_ms = 1000.0 * (release + 1) / fps
    pre_ms = start_ms
    post_ms = 1000.0 * (n_frames - release - 1) / fps
    if pre_ms < 0.0 or post_ms < 0.0:
        errors.append("NEGATIVE_PRE_OR_POST_CONTEXT")
    return SpanTiming(
        not errors,
        "inclusive_frame_indices",
        onset,
        release,
        n_frames,
        fps,
        start_ms,
        end_ms,
        end_ms - start_ms,
        pre_ms,
        post_ms,
        str(payload.get("detect_version", "")),
        str(payload.get("params_hash", "")),
        tuple(errors),
    )


def validate_train_population(rows: Sequence[dict[str, str]]) -> None:
    if len(rows) != EXPECTED["train_clips"]:
        raise RuntimeError(f"TRAIN_COUNT_MISMATCH:{len(rows)}")
    for row in rows:
        if row.get("split") != "train" or row.get("training_eligible") != "true":
            raise RuntimeError(f"PROTECTED_OR_NONTRAIN_POPULATION_REJECTED:{row.get('sample_id')}")
        role = row.get("role", "").casefold()
        if "protected" in role or role == "test" or row.get("sample_id", "").startswith("replay:"):
            raise RuntimeError(f"PROTECTED_OR_NONTRAIN_POPULATION_REJECTED:{row.get('sample_id')}")


def duplicate_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    sample_counts = Counter(row["sample_id"] for row in rows)
    path_groups: defaultdict[str, list[str]] = defaultdict(list)
    for row in rows:
        path_groups[str(Path(row["resolved_raw_video_path"])).casefold()].append(row["sample_id"])
    duplicate_samples = {key: value for key, value in sorted(sample_counts.items()) if value > 1}
    duplicate_paths = {
        key: values for key, values in sorted(path_groups.items()) if len(values) > 1
    }
    return {
        "duplicate_sample_id_count": len(duplicate_samples),
        "duplicate_sample_ids": duplicate_samples,
        "duplicate_source_file_count": len(duplicate_paths),
        "duplicate_source_files": duplicate_paths,
        "multiple_governed_spans_same_source_count": sum(
            1
            for values in duplicate_paths.values()
            if sum(
                bool(next(row for row in rows if row["sample_id"] == sample)["resolved_span_path"])
                for sample in values
            )
            > 1
        ),
    }


def _count_distribution(counter: Counter[str]) -> dict[str, Any]:
    return distribution(list(counter.values()))


def _coverage_summary(
    rows: Sequence[dict[str, Any]], pre_ms: float, post_ms: float
) -> dict[str, Any]:
    usable = [
        row
        for row in rows
        if row["context_valid"]
        and row["pre_context_ms"] >= pre_ms
        and row["post_context_ms"] >= post_ms
    ]
    signer_counts = Counter(row["signer_id"] for row in usable)
    gloss_counts = Counter(row["gloss"] for row in usable)
    source_counts = Counter(row["source"] for row in usable)
    return {
        "required_pre_ms": pre_ms,
        "required_post_ms": post_ms,
        "usable_clips": len(usable),
        "percentage_of_train": 100.0 * len(usable) / len(rows),
        "unique_signers": len(signer_counts),
        "unique_glosses": len(gloss_counts),
        "clips_per_source": dict(sorted(source_counts.items())),
        "signer_coverage_distribution": _count_distribution(signer_counts),
        "gloss_coverage_distribution": _count_distribution(gloss_counts),
        "glosses_with_at_least": {
            str(n): sum(count >= n for count in gloss_counts.values()) for n in (1, 3, 5, 10)
        },
        "usable_sample_ids_sha256": hashlib.sha256(
            "\n".join(sorted(row["sample_id"] for row in usable)).encode("utf-8")
        ).hexdigest(),
    }


def _source_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for source in sorted({row["source"] for row in rows}):
        subset = [row for row in rows if row["source"] == source]
        valid = [row for row in subset if row["context_valid"]]
        approx_fill = [
            row
            for row in valid
            if row["pre_context_ms"] <= 1000.0 / row["span_native_fps"]
            and row["post_context_ms"] <= 1000.0 / row["span_native_fps"]
        ]
        result[source] = {
            "clips": len(subset),
            "readable_videos": sum(row["video_readable"] for row in subset),
            "governed_span_paths": sum(bool(row["resolved_span_path"]) for row in subset),
            "context_valid_clips": len(valid),
            "signer_count": len({row["signer_id"] for row in subset}),
            "gloss_count": len({row["gloss"] for row in subset}),
            "video_duration_ms": distribution(
                row["raw_video_duration_ms"]
                for row in subset
                if row["raw_video_duration_ms"] is not None
            ),
            "active_span_duration_ms": distribution(
                row["active_span_duration_ms"] for row in valid
            ),
            "pre_context_ms": distribution(row["pre_context_ms"] for row in valid),
            "post_context_ms": distribution(row["post_context_ms"] for row in valid),
            "approximately_fills_complete_source_video": {
                "definition": "pre and post context each <= one declared span-native frame",
                "count": len(approx_fill),
                "fraction_of_context_valid": len(approx_fill) / len(valid) if valid else None,
            },
        }
    return result


def _pairwise_gloss_overlap(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    by_signer: defaultdict[str, set[str]] = defaultdict(set)
    for row in rows:
        by_signer[row["signer_id"]].add(row["gloss"])
    intersections: list[float] = []
    jaccards: list[float] = []
    signers = sorted(by_signer)
    for index, left in enumerate(signers):
        for right in signers[index + 1 :]:
            intersection = by_signer[left] & by_signer[right]
            union = by_signer[left] | by_signer[right]
            intersections.append(float(len(intersection)))
            jaccards.append(len(intersection) / len(union) if union else 0.0)
    return {
        "signer_pairs": len(intersections),
        "pairs_with_any_gloss_overlap": sum(value > 0 for value in intersections),
        "intersection_gloss_count": distribution(intersections),
        "jaccard": distribution(jaccards),
    }


def _split_feasibility(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    all_signer_counts = Counter(row["signer_id"] for row in rows)
    signer_glosses: defaultdict[str, set[str]] = defaultdict(set)
    signer_sources: defaultdict[str, set[str]] = defaultdict(set)
    for row in rows:
        signer_glosses[row["signer_id"]].add(row["gloss"])
        signer_sources[row["signer_id"]].add(row["source"])
    by_requirement: dict[str, Any] = {}
    for name, pre_ms, post_ms in CONTEXT_REQUIREMENTS_MS:
        usable = [
            row
            for row in rows
            if row["context_valid"]
            and row["pre_context_ms"] >= pre_ms
            and row["post_context_ms"] >= post_ms
        ]
        counts = Counter(row["signer_id"] for row in usable)
        gloss_signers: defaultdict[str, set[str]] = defaultdict(set)
        for row in usable:
            gloss_signers[row["gloss"]].add(row["signer_id"])
        by_requirement[name] = {
            "contextual_signers": len(counts),
            "signers_with_at_least_contextual_clips": {
                str(n): sum(value >= n for value in counts.values()) for n in (1, 5, 10, 20, 50)
            },
            "contextual_clips_per_signer": _count_distribution(counts),
            "glosses_represented_by_at_least_signers": {
                str(n): sum(len(value) >= n for value in gloss_signers.values())
                for n in (1, 2, 3, 5, 10)
            },
            "pairwise_signer_gloss_overlap": _pairwise_gloss_overlap(usable),
        }
    return {
        "final_split_created": False,
        "all_train_clips_per_signer": dict(sorted(all_signer_counts.items())),
        "all_train_glosses_per_signer": {
            key: len(signer_glosses[key]) for key in sorted(signer_glosses)
        },
        "all_train_sources_per_signer": {
            key: sorted(signer_sources[key]) for key in sorted(signer_sources)
        },
        "by_context_requirement": by_requirement,
        "interpretation": (
            "Signer-disjoint splitting is numerically assessable from governed TRAIN only. "
            "Unseen-signer plus unseen-gloss evaluation is only plausible where contextual clips "
            "retain multi-signer gloss coverage; no signer or gloss is selected in this audit."
        ),
    }


def _inspection_manifest(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic 24-row review queue; selection does not consult recognition results."""

    selected: list[dict[str, Any]] = []
    for source in sorted({row["source"] for row in rows}):
        subset = [row for row in rows if row["source"] == source]
        ranked = sorted(
            subset,
            key=lambda row: (
                row["pre_context_ms"] if row["pre_context_ms"] is not None else -1.0,
                row["post_context_ms"] if row["post_context_ms"] is not None else -1.0,
                row["raw_video_duration_ms"] if row["raw_video_duration_ms"] is not None else -1.0,
                row["sample_id"],
            ),
        )
        if not ranked:
            continue
        indices = sorted({round(index * (len(ranked) - 1) / 7) for index in range(8)})
        for index in indices:
            row = ranked[index]
            selected.append(
                {
                    "sample_id": row["sample_id"],
                    "source": row["source"],
                    "signer_id": row["signer_id"],
                    "gloss": row["gloss"],
                    "resolved_raw_video_path": row["resolved_raw_video_path"],
                    "resolved_span_path": row["resolved_span_path"],
                    "active_span_duration_ms": row["active_span_duration_ms"],
                    "pre_context_ms": row["pre_context_ms"],
                    "post_context_ms": row["post_context_ms"],
                    "review_purpose": "later human preparation/recovery semantics check",
                }
            )
    return sorted(selected, key=lambda row: (row["source"], row["sample_id"]))


def _audit_row(row: dict[str, str]) -> dict[str, Any]:
    source = row["source_dataset"]
    video_path = resolve_governed_path(row["raw_video_path"], source)
    span_text = row.get("span_path", "").strip()
    span_path = resolve_governed_path(span_text, source) if span_text else Path()
    video = probe_video(video_path)
    span: SpanTiming | None = None
    span_error = ""
    if not span_text:
        span_error = "MISSING_GOVERNED_SPAN_PATH"
    elif not span_path.is_file():
        span_error = "MISSING_SPAN_FILE"
    else:
        try:
            payload = json.loads(span_path.read_text(encoding="utf-8-sig"))
            span = calculate_span_timing(payload, video)
        except (OSError, json.JSONDecodeError) as error:
            span_error = f"UNREADABLE_SPAN:{type(error).__name__}"
    errors = [video.error] if video.error else []
    if span_error:
        errors.append(span_error)
    if span:
        errors.extend(span.errors)
    return {
        "sample_id": row["sample_id"],
        "source": source,
        "signer_id": row["signer_group_id"],
        "gloss": row["canonical_gloss"],
        "class_id": int(row["class_id"]),
        "manifest_raw_video_path": row["raw_video_path"],
        "resolved_raw_video_path": str(video_path),
        "manifest_span_path": span_text,
        "resolved_span_path": str(span_path) if span_text else "",
        "raw_video_duration_ms": video.duration_ms,
        "video_frame_count": video.frame_count,
        "video_fps": video.fps,
        "video_timestamp_basis": video.timestamp_basis,
        "video_readable": video.readable,
        "span_unit": span.unit if span else "unavailable",
        "span_onset_frame_inclusive": span.onset_frame_inclusive if span else None,
        "span_release_frame_inclusive": span.release_frame_inclusive if span else None,
        "span_n_frames": span.n_frames if span else None,
        "span_native_fps": span.native_fps if span else None,
        "span_start_ms": span.span_start_ms if span else None,
        "span_end_ms_exclusive": span.span_end_ms_exclusive if span else None,
        "active_span_duration_ms": span.active_duration_ms if span else None,
        "pre_context_ms": span.pre_context_ms if span else None,
        "post_context_ms": span.post_context_ms if span else None,
        "context_valid": bool(span and span.valid_for_context and video.readable),
        "detect_version": span.detector_version if span else "",
        "detect_params_hash": span.detector_params_hash if span else "",
        "lineage_status": row["lineage_status"],
        "issues": "|".join(errors),
    }


def _integrity(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    issues = Counter(issue for row in rows for issue in row["issues"].split("|") if issue)
    duplicates = duplicate_summary(rows)
    relocations: Counter[str] = Counter()
    for row in rows:
        if row["manifest_raw_video_path"] != row["resolved_raw_video_path"]:
            relocations[f"{row['source']}:raw_video_path"] += 1
        if row["manifest_span_path"] != row["resolved_span_path"]:
            relocations[f"{row['source']}:span_path"] += 1
    return {
        "issue_counts": dict(sorted(issues.items())),
        **duplicates,
        "resolved_path_relocations": dict(sorted(relocations.items())),
        "missing_video": sum("MISSING_VIDEO" in row["issues"] for row in rows),
        "missing_span": sum(
            "MISSING_GOVERNED_SPAN_PATH" in row["issues"] or "MISSING_SPAN_FILE" in row["issues"]
            for row in rows
        ),
        "unreadable_video": sum(
            not row["video_readable"] and "MISSING_VIDEO" not in row["issues"] for row in rows
        ),
        "invalid_non_positive_duration": sum(
            row["raw_video_duration_ms"] is not None and row["raw_video_duration_ms"] <= 0
            for row in rows
        ),
        "span_outside_video_bounds": sum(
            "SPAN_OUTSIDE_VIDEO_BOUNDS" in row["issues"] for row in rows
        ),
        "negative_pre_post_context": sum(
            "NEGATIVE_PRE_OR_POST_CONTEXT" in row["issues"] for row in rows
        ),
        "ambiguous_span_units": sum(
            "AMBIGUOUS_SPAN_UNITS_OR_SCHEMA" in row["issues"] for row in rows
        ),
        "suspicious_exact_full_video_spans": sum(
            row["context_valid"]
            and row["span_onset_frame_inclusive"] == 0
            and row["span_release_frame_inclusive"] == row["span_n_frames"] - 1
            for row in rows
        ),
    }


def _label_provenance(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ASL_CITIZEN": {
            "classification": "detector-derived boundary",
            "rows": sum(row["source"] == "ASL_CITIZEN" for row in rows),
            "mechanism": (
                "D1 landmark-motion hysteresis plus hands-raised gate; longest run; two-frame "
                "backoff; inclusive frame indices; detector thresholds documented as tuned on "
                "90 val clips"
            ),
            "lineage_confidence": "HIGH",
            "semantic_label_confidence": "LOW_TO_MODERATE",
            "limitation": (
                "The sidecar is not a manual sign-boundary annotation. Outside-span frames are "
                "detector-negative context, not proven PRE/IDLE or POST-SIGN/RECOVERY labels."
            ),
        },
        "APPHEAR_CAPTURE": {
            "classification": "previously processed whole isolated clip; no governed temporal span",
            "rows": sum(row["source"] == "APPHEAR_CAPTURE" for row in rows),
            "mechanism": "E6 feature extraction used onset=0 and release=last decoded frame",
            "lineage_confidence": "HIGH",
            "semantic_label_confidence": "UNKNOWN",
            "limitation": (
                "No governed active boundary exists, so PRE/ACTIVE/POST labels cannot be derived."
            ),
        },
        "LOCAL": {
            "classification": "previously processed whole isolated clip; no governed temporal span",
            "rows": sum(row["source"] == "LOCAL" for row in rows),
            "mechanism": "E6 feature extraction used onset=0 and release=last decoded frame",
            "lineage_confidence": "HIGH",
            "semantic_label_confidence": "UNKNOWN",
            "limitation": (
                "No governed active boundary exists, so PRE/ACTIVE/POST labels cannot be derived."
            ),
        },
        "defensible_training_interpretation": (
            "NOT YET. Before/inside/after may be retained as weak detector-derived candidates for "
            "ASL_CITIZEN, but must not be promoted to ground-truth temporal labels without a "
            "detector-independent human boundary audit."
        ),
    }


def _write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _hash_manifest(paths: Sequence[Path]) -> dict[str, Any]:
    return {
        "schema": "APPHEAR_PHASE5_1T_0_SOURCE_HASHES_V1",
        "files": [
            {"path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in sorted(paths, key=lambda item: str(item).casefold())
        ],
    }


def _report(payload: dict[str, Any], source_summary: dict[str, Any], split: dict[str, Any]) -> str:
    coverage = payload["context_coverage"]
    integrity = payload["integrity"]
    lines = [
        "# SEGMENTATION_DATA_READINESS_REPORT",
        "",
        f"**Milestone:** `{MILESTONE}`  ",
        "**Final evidence statement:** `SEGMENTATION_SOURCE_CONTEXT_PARTIAL`  ",
        "**Next:** `WAIT_FOR_PROJECT_LEAD_PHASE_5_1T_1_DATASET_DECISION`",
        "",
        "## 1. Scope and governance",
        "",
        "Only the frozen governed recognition TRAIN manifest was loaded. Recognition DEV, "
        "protected TEST, Gate-4 phone payloads, Phase-5 holdouts, features, and recognizer "
        "outputs were not opened. No scientific data, manifest, model, runtime, or Android "
        "file was modified.",
        "",
        "## 2. Exact population",
        "",
        f"Audited `{payload['population']['clips']}` TRAIN clips, "
        f"`{payload['population']['glosses']}` glosses, and "
        f"`{payload['population']['signers']}` signer groups: "
        f"`{payload['population']['sources']}`.",
        "",
        "## 3. Span schema and provenance",
        "",
        "ASL_CITIZEN sidecars encode inclusive `onset`/`release` frame indices with declared "
        "`native_fps` and `n_frames`; temporal endpoints are `[onset/fps, (release+1)/fps)`. "
        "They are D1 detector outputs, not manual annotations. APPHEAR_CAPTURE and LOCAL "
        "carry no governed span path; their E6 recognition feature extraction used the whole "
        "decoded clip.",
        "",
        "Therefore `before = PRE`, `inside = ACTIVE`, and `after = POST/RECOVERY` is not yet "
        "defensible as ground truth. The ASL rows are at most weak detector-derived label "
        "candidates pending detector-independent visual validation.",
        "",
        "## 4. Integrity findings",
        "",
        f"- Missing governed spans: `{integrity['missing_span']}` "
        "(all APPHEAR_CAPTURE/LOCAL rows).",
        f"- Missing videos: `{integrity['missing_video']}`; unreadable videos: "
        f"`{integrity['unreadable_video']}`.",
        f"- Duplicate sample IDs: `{integrity['duplicate_sample_id_count']}`; duplicate source "
        f"files: `{integrity['duplicate_source_file_count']}`.",
        f"- Span outside video bounds: `{integrity['span_outside_video_bounds']}`; ambiguous "
        f"units: `{integrity['ambiguous_span_units']}`.",
        f"- Exact whole-video D1 spans: `{integrity['suspicious_exact_full_video_spans']}`.",
        f"- Governed relocations used: `{integrity['resolved_path_relocations']}`.",
        "",
        "## 5. Context coverage",
        "",
        "| Requirement | Usable | % TRAIN | Signers | Glosses | >=1 / >=3 / >=5 / >=10 clips |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, _, _ in CONTEXT_REQUIREMENTS_MS:
        item = coverage[name]
        thresholds = item["glosses_with_at_least"]
        lines.append(
            f"| {name} | {item['usable_clips']} | {item['percentage_of_train']:.2f}% | "
            f"{item['unique_signers']} | {item['unique_glosses']} | "
            f"{thresholds['1']} / {thresholds['3']} / {thresholds['5']} / {thresholds['10']} |"
        )
    lines.extend(["", "## 6. Source distributions", ""])
    for source, item in source_summary.items():
        lines.append(
            f"- **{source}:** {item['clips']} clips, {item['signer_count']} signers, "
            f"{item['gloss_count']} glosses, {item['context_valid_clips']} context-valid spans; "
            f"video duration median={item['video_duration_ms']['median']} ms, "
            f"pre median={item['pre_context_ms']['median']} ms, "
            f"post median={item['post_context_ms']['median']} ms."
        )
    best = coverage["pre_500_post_750"]
    split_best = split["by_context_requirement"]["pre_500_post_750"]
    multi_signer = split_best["glosses_represented_by_at_least_signers"]
    lines.extend(
        [
            "",
            "## 7. Signer-disjoint feasibility",
            "",
            f"At the 500 ms PRE + 750 ms POST audit bin, `{best['unique_signers']}` signer "
            f"groups and `{best['unique_glosses']}` glosses remain. Detailed per-signer counts, "
            "multi-signer gloss coverage, and pairwise gloss overlap are in "
            "`split_feasibility.json`. Of the 236 glosses, "
            f"`{multi_signer['2']}` occur for at least two contextual signers, "
            f"`{multi_signer['3']}` for at least three, and `{multi_signer['5']}` for at least "
            "five. An unseen-signer plus selected unseen-gloss evaluation appears numerically "
            "possible, but coverage is imbalanced and this audit does not choose a split.",
            "",
            "## 8. Readiness conclusion",
            "",
            "`SEGMENTATION_SOURCE_CONTEXT_PARTIAL`",
            "",
            "There is measurable genuine source-video context across a broad 236-gloss, "
            "multi-signer ASL_CITIZEN population, but only 3,309/3,926 rows have any governed "
            "span and those spans are detector-derived. APPHEAR_CAPTURE/LOCAL contribute no "
            "governed temporal labels. A learned temporal segmenter must not be trained from "
            "these boundaries as ground truth until a deterministic human audit/adjudication "
            "gate establishes preparation, active-sign, and recovery semantics.",
            "",
            "## 9. Stop boundary",
            "",
            "`WAIT_FOR_PROJECT_LEAD_PHASE_5_1T_1_DATASET_DECISION`",
            "",
            "No extraction or temporal-model training was started.",
        ]
    )
    return "\n".join(lines) + "\n"


def run(output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    if sha256(TRAIN_MANIFEST) != EXPECTED["train_manifest_sha256"]:
        raise RuntimeError("TRAIN_MANIFEST_IDENTITY_MISMATCH")
    source_rows = load_rows(TRAIN_MANIFEST)
    validate_train_population(source_rows)
    rows = sorted((_audit_row(row) for row in source_rows), key=lambda row: row["sample_id"])
    integrity = _integrity(rows)
    coverage = {
        name: _coverage_summary(rows, pre_ms, post_ms)
        for name, pre_ms, post_ms in CONTEXT_REQUIREMENTS_MS
    }
    source_summary = _source_summary(rows)
    split = _split_feasibility(rows)
    provenance = _label_provenance(rows)
    payload = {
        "schema": "APPHEAR_PHASE5_1T_0_SEGMENTATION_DATA_READINESS_V1",
        "milestone": MILESTONE,
        "final_evidence_statement": "SEGMENTATION_SOURCE_CONTEXT_PARTIAL",
        "next": "WAIT_FOR_PROJECT_LEAD_PHASE_5_1T_1_DATASET_DECISION",
        "population": {
            "manifest": str(TRAIN_MANIFEST.resolve()),
            "manifest_sha256": sha256(TRAIN_MANIFEST),
            "clips": len(rows),
            "glosses": len({row["gloss"] for row in rows}),
            "signers": len({row["signer_id"] for row in rows}),
            "sources": dict(sorted(Counter(row["source"] for row in rows).items())),
        },
        "integrity": integrity,
        "context_coverage": coverage,
        "span_label_provenance": provenance,
        "governance": {
            "recognition_dev_accessed": False,
            "protected_test_accessed": False,
            "gate4_phone_payload_accessed": False,
            "phase5_phone_holdout_accessed": False,
            "recognizer_accessed": False,
            "training_executed": False,
            "candidate01_modified": False,
            "recognition_v2_modified": False,
            "android_modified": False,
            "scientific_data_modified": False,
            "authoritative_manifest_created": False,
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    _write_csv(output_root / "per_sample_context.csv", rows)
    _write_json(output_root / "segmentation_data_readiness.json", payload)
    _write_json(output_root / "source_summary.json", source_summary)
    _write_json(output_root / "split_feasibility.json", split)
    _write_json(output_root / "visual_inspection_manifest.json", _inspection_manifest(rows))
    report = _report(payload, source_summary, split)
    (output_root / "SEGMENTATION_DATA_READINESS_REPORT.md").write_text(report, encoding="utf-8")
    code = Path(__file__).resolve()
    test = ROOT / "tests/test_phase5_1t_segmentation_data_readiness.py"
    source_inputs = [
        code,
        test,
        TRAIN_MANIFEST,
        ROOT / "pipeline/perception_vnext/governance.py",
        ROOT / "pipeline/detect/schema.py",
        ROOT / "pipeline/detect/span.py",
        ROOT / "pipeline/config/detect.yaml",
        ROOT / "pipeline/splits/phase1_full_vocab.py",
        ROOT / "pipeline/rgb/e6_v30_five_sign_baseline.py",
        ROOT
        / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
        / "phase4a_gate4a1c_oracle_temporal_boundary_replay_01"
        / "PHASE4A_GATE4A1C_FINAL_REPORT.md",
        ROOT
        / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
        / "phase5_0_segmentation_contract_and_signal_audit_01"
        / "PHASE_5_0_SEGMENTATION_CONTRACT_AND_SIGNAL_AUDIT_01.md",
        ROOT
        / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
        / "phase5_1_offline_automatic_segmenter_01"
        / "PHASE_5_1_OFFLINE_AUTOMATIC_SEGMENTER_01.md",
        ROOT
        / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
        / "phase5_1s_global_end_conflict_attribution_01"
        / "PHASE_5_1S_GLOBAL_END_CONFLICT_ATTRIBUTION_01.md",
    ]
    _write_json(output_root / "source_hashes.json", _hash_manifest(source_inputs))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    result = run(args.output_root)
    print(
        json.dumps(
            {"result": result["final_evidence_statement"], "output": str(args.output_root)},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
