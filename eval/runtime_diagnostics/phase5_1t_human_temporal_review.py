"""Local blinded reviewer for Phase 5.1T-1 human temporal semantics validation.

The utility is hard-bound to the frozen 24-sample Phase-5.1T-0 inspection manifest. It serves
videos only from that manifest, never exposes an ASL_CITIZEN D1 span before the human annotation
is committed, and never reads recognition features, predictions, DEV, TEST, or phone holdouts.
"""

# The embedded single-file local review UI intentionally keeps HTML/CSS/JS lines intact.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
import threading
import webbrowser
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import cv2

ROOT = Path(__file__).resolve().parents[2]
MILESTONE = "PHASE_5_1T_1_HUMAN_TEMPORAL_SEMANTICS_VALIDATION_01"
SCHEMA = "apphear.phase5_1t.human_temporal_annotations.v1"
TOOL_VERSION = "phase5.1t-1-local-review-v1"
EXPECTED_MANIFEST_SHA256 = "73b4e5c320ef36ca8c9dc27c86a23aff66c272bad712c85d9b719087b6600658"
EXPECTED_SAMPLE_COUNT = 24
MAJOR_DISAGREEMENT_MS = 500.0
BIAS_TOLERANCE_MS = 50.0
REUSE_MIN_SUBSTANTIAL_MAJORITY = 16

INPUT_MANIFEST = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
    / "phase5_1t_0_segmentation_data_readiness_audit_01/visual_inspection_manifest.json"
)
OUTPUT_ROOT = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
    / "phase5_1t_1_human_temporal_semantics_validation_01"
)


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_manifest(
    payload: Any,
    *,
    expected_count: int = EXPECTED_SAMPLE_COUNT,
    check_files: bool = True,
) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or len(payload) != expected_count:
        raise ValueError(
            f"MANIFEST_COUNT_MISMATCH:{len(payload) if isinstance(payload, list) else 'not-list'}"
        )
    required = {
        "sample_id",
        "source",
        "signer_id",
        "gloss",
        "resolved_raw_video_path",
        "resolved_span_path",
    }
    sample_ids: set[str] = set()
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict) or not required.issubset(item):
            raise ValueError(f"MANIFEST_SCHEMA_INVALID:{index}")
        sample_id = str(item["sample_id"])
        if sample_id in sample_ids:
            raise ValueError(f"DUPLICATE_SAMPLE_ID:{sample_id}")
        sample_ids.add(sample_id)
        video = Path(str(item["resolved_raw_video_path"]))
        if check_files and not video.is_file():
            raise FileNotFoundError(f"MISSING_VIDEO:{sample_id}:{video}")
        if item["source"] == "ASL_CITIZEN":
            span = Path(str(item["resolved_span_path"]))
            if check_files and not span.is_file():
                raise FileNotFoundError(f"MISSING_D1_SPAN:{sample_id}:{span}")
        elif item["resolved_span_path"]:
            raise ValueError(f"UNEXPECTED_NON_ASL_D1_SPAN:{sample_id}")
        rows.append(dict(item))
    expected_order = sorted(rows, key=lambda row: (str(row["source"]), str(row["sample_id"])))
    if [row["sample_id"] for row in rows] != [row["sample_id"] for row in expected_order]:
        raise ValueError("MANIFEST_ORDER_NOT_DETERMINISTIC")
    return rows


def load_frozen_manifest(
    path: Path = INPUT_MANIFEST,
    *,
    expected_sha256: str = EXPECTED_MANIFEST_SHA256,
    check_files: bool = True,
) -> list[dict[str, Any]]:
    actual_hash = sha256_file(path)
    if actual_hash != expected_sha256:
        raise RuntimeError(f"INPUT_MANIFEST_SHA256_MISMATCH:{actual_hash}")
    return validate_manifest(
        json.loads(path.read_text(encoding="utf-8-sig")), check_files=check_files
    )


def probe_video(path: Path) -> dict[str, float | int]:
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise OSError(f"VIDEO_OPEN_FAILED:{path}")
        frame_count = int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        if frame_count <= 0 or not math.isfinite(fps) or fps <= 0.0:
            raise ValueError(f"INVALID_VIDEO_TIMEBASE:{path}:{frame_count}:{fps}")
        return {
            "frame_count": frame_count,
            "fps": fps,
            "duration_ms": 1000.0 * frame_count / fps,
        }
    finally:
        capture.release()


def frame_index_to_ms(frame_index: int, fps: float, *, end_exclusive: bool = False) -> float:
    if frame_index < 0 or not math.isfinite(fps) or fps <= 0.0:
        raise ValueError("INVALID_FRAME_TIMESTAMP_CONVERSION")
    return 1000.0 * (frame_index + int(end_exclusive)) / fps


def load_d1_diagnostic(row: dict[str, Any]) -> dict[str, float]:
    if row["source"] != "ASL_CITIZEN":
        raise ValueError("D1_DIAGNOSTIC_ONLY_FOR_ASL_CITIZEN")
    payload = json.loads(Path(str(row["resolved_span_path"])).read_text(encoding="utf-8-sig"))
    onset = int(payload["onset"])
    release = int(payload["release"])
    fps = float(payload["native_fps"])
    if not bool(payload["valid"]) or onset < 0 or release < onset:
        raise ValueError(f"INVALID_D1_SPAN:{row['sample_id']}")
    return {
        "d1_onset_ms": frame_index_to_ms(onset, fps),
        "d1_release_ms": frame_index_to_ms(release, fps, end_exclusive=True),
    }


def empty_annotation_document() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "tool_version": TOOL_VERSION,
        "milestone": MILESTONE,
        "input_manifest_path": str(INPUT_MANIFEST.resolve()),
        "input_manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "expected_sample_count": EXPECTED_SAMPLE_COUNT,
        "status": "AWAITING_HUMAN_REVIEW",
        "annotations": [],
    }


def load_annotation_document(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return empty_annotation_document()
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload.get("schema") != SCHEMA:
        raise ValueError("ANNOTATION_SCHEMA_MISMATCH")
    if payload.get("input_manifest_sha256") != EXPECTED_MANIFEST_SHA256:
        raise ValueError("ANNOTATION_MANIFEST_IDENTITY_MISMATCH")
    annotations = payload.get("annotations")
    if not isinstance(annotations, list):
        raise ValueError("ANNOTATIONS_NOT_LIST")
    ids = [item.get("sample_id") for item in annotations]
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_SAVED_ANNOTATION")
    return payload


def _atomic_json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def validate_annotation_input(payload: dict[str, Any], duration_ms: float) -> dict[str, Any]:
    judgments = (
        "clear_pre_context",
        "clear_active_sign",
        "clear_post_recovery_context",
        "ambiguous_or_unusable",
    )
    for field in judgments:
        if not isinstance(payload.get(field), bool):
            raise ValueError(f"BOOLEAN_JUDGMENT_REQUIRED:{field}")
    start = payload.get("human_sign_start_ms")
    end = payload.get("human_sign_end_ms")
    if start is None or end is None:
        if not payload["ambiguous_or_unusable"]:
            raise ValueError("BOUNDARIES_REQUIRED_UNLESS_AMBIGUOUS")
        start_ms = end_ms = None
    else:
        start_ms = float(start)
        end_ms = float(end)
        if not all(math.isfinite(value) for value in (start_ms, end_ms)):
            raise ValueError("NONFINITE_BOUNDARY")
        if start_ms < 0.0 or end_ms > duration_ms + 1.0 or start_ms >= end_ms:
            raise ValueError("INVALID_BOUNDARY_START_MUST_PRECEDE_END")
    return {
        "human_sign_start_ms": start_ms,
        "human_sign_end_ms": end_ms,
        **{field: payload[field] for field in judgments},
        "reviewer_note": str(payload.get("reviewer_note", "")).strip()[:500],
    }


def commit_annotation(
    *,
    manifest: Sequence[dict[str, Any]],
    annotation_path: Path,
    sample_index: int,
    payload: dict[str, Any],
    video_metadata: Sequence[dict[str, float | int]],
    now: datetime | None = None,
) -> dict[str, Any]:
    if sample_index < 0 or sample_index >= len(manifest):
        raise IndexError("SAMPLE_INDEX_OUT_OF_RANGE")
    row = manifest[sample_index]
    document = load_annotation_document(annotation_path)
    if any(item["sample_id"] == row["sample_id"] for item in document["annotations"]):
        raise ValueError("ANNOTATION_ALREADY_COMMITTED_IMMUTABLE")
    duration_ms = float(video_metadata[sample_index]["duration_ms"])
    validated = validate_annotation_input(payload, duration_ms)
    annotation: dict[str, Any] = {
        "sample_id": row["sample_id"],
        "source": row["source"],
        "signer_id": row["signer_id"],
        "gloss": row["gloss"],
        "video_path": row["resolved_raw_video_path"],
        "duration_ms": duration_ms,
        **validated,
        "review_timestamp": (now or datetime.now(UTC)).isoformat(),
        "tool_version": TOOL_VERSION,
        "schema": SCHEMA,
    }
    if row["source"] == "ASL_CITIZEN":
        diagnostic = load_d1_diagnostic(row)
        annotation.update(diagnostic)
        if validated["human_sign_start_ms"] is None:
            annotation["human_minus_d1_start_ms"] = None
            annotation["human_minus_d1_end_ms"] = None
        else:
            annotation["human_minus_d1_start_ms"] = (
                validated["human_sign_start_ms"] - diagnostic["d1_onset_ms"]
            )
            annotation["human_minus_d1_end_ms"] = (
                validated["human_sign_end_ms"] - diagnostic["d1_release_ms"]
            )
    document["annotations"].append(annotation)
    order = {row["sample_id"]: index for index, row in enumerate(manifest)}
    document["annotations"].sort(key=lambda item: order[item["sample_id"]])
    document["status"] = (
        "COMPLETE_PENDING_FINALIZE"
        if len(document["annotations"]) == len(manifest)
        else "IN_PROGRESS"
    )
    _atomic_json_write(annotation_path, document)
    return annotation


def public_state(
    manifest: Sequence[dict[str, Any]],
    annotations: dict[str, Any],
    video_metadata: Sequence[dict[str, float | int]],
) -> dict[str, Any]:
    """Return browser state with no uncommitted D1 values or span-derived context fields."""

    saved = {item["sample_id"]: item for item in annotations["annotations"]}
    samples: list[dict[str, Any]] = []
    for index, row in enumerate(manifest):
        item = {
            "index": index,
            "sample_id": row["sample_id"],
            "source": row["source"],
            "signer_id": row["signer_id"],
            "gloss": row["gloss"],
            "duration_ms": video_metadata[index]["duration_ms"],
            "fps": video_metadata[index]["fps"],
            "video_url": f"/video/{index}",
            "committed": row["sample_id"] in saved,
        }
        if item["committed"]:
            item["annotation"] = saved[row["sample_id"]]
        samples.append(item)
    return {
        "schema": SCHEMA,
        "tool_version": TOOL_VERSION,
        "progress": {"committed": len(saved), "total": len(manifest)},
        "samples": samples,
    }


def summarize_annotations(
    manifest: Sequence[dict[str, Any]], document: dict[str, Any]
) -> dict[str, Any]:
    annotations = document["annotations"]
    if len(annotations) != len(manifest):
        raise RuntimeError(f"HUMAN_REVIEW_INCOMPLETE:{len(annotations)}/{len(manifest)}")
    expected_ids = [row["sample_id"] for row in manifest]
    if [item["sample_id"] for item in annotations] != expected_ids:
        raise RuntimeError("ANNOTATION_ORDER_OR_MEMBERSHIP_MISMATCH")

    def source_counts(items: Sequence[dict[str, Any]]) -> dict[str, Any]:
        usable = [
            item
            for item in items
            if item["clear_pre_context"]
            and item["clear_active_sign"]
            and item["clear_post_recovery_context"]
            and not item["ambiguous_or_unusable"]
        ]
        active_plus_context = [
            item
            for item in items
            if item["clear_active_sign"]
            and (item["clear_pre_context"] or item["clear_post_recovery_context"])
            and not item["ambiguous_or_unusable"]
        ]
        return {
            "total_clips_reviewed": len(items),
            "clear_pre_count": sum(item["clear_pre_context"] for item in items),
            "clear_active_count": sum(item["clear_active_sign"] for item in items),
            "clear_post_recovery_count": sum(item["clear_post_recovery_context"] for item in items),
            "usable_for_pre_active_post_supervision": len(usable),
            "recognizable_active_plus_some_context": len(active_plus_context),
            "ambiguous_or_unusable_count": sum(item["ambiguous_or_unusable"] for item in items),
        }

    by_source = {
        source: source_counts([item for item in annotations if item["source"] == source])
        for source in sorted({item["source"] for item in annotations})
    }
    overall = source_counts(annotations)
    asl = [
        item
        for item in annotations
        if item["source"] == "ASL_CITIZEN" and item["human_minus_d1_start_ms"] is not None
    ]
    start_differences = [float(item["human_minus_d1_start_ms"]) for item in asl]
    end_differences = [float(item["human_minus_d1_end_ms"]) for item in asl]

    def direction(values: Sequence[float], *, boundary: str) -> dict[str, int]:
        return {
            f"d1_{boundary}_earlier_than_human": sum(value > BIAS_TOLERANCE_MS for value in values),
            f"d1_{boundary}_later_than_human": sum(value < -BIAS_TOLERANCE_MS for value in values),
            f"within_{int(BIAS_TOLERANCE_MS)}ms": sum(
                abs(value) <= BIAS_TOLERANCE_MS for value in values
            ),
        }

    d1 = {
        "compared_clips": len(asl),
        "release_semantics": "exclusive temporal endpoint: (inclusive release frame + 1) / fps",
        "median_absolute_start_difference_ms": (
            statistics.median(abs(value) for value in start_differences)
            if start_differences
            else None
        ),
        "median_absolute_end_difference_ms": (
            statistics.median(abs(value) for value in end_differences) if end_differences else None
        ),
        "median_signed_human_minus_d1_start_ms": (
            statistics.median(start_differences) if start_differences else None
        ),
        "median_signed_human_minus_d1_end_ms": (
            statistics.median(end_differences) if end_differences else None
        ),
        "start_direction": direction(start_differences, boundary="start"),
        "end_direction": direction(end_differences, boundary="end"),
        "major_disagreement_definition_ms": MAJOR_DISAGREEMENT_MS,
        "major_disagreement_count": sum(
            abs(start) > MAJOR_DISAGREEMENT_MS or abs(end) > MAJOR_DISAGREEMENT_MS
            for start, end in zip(start_differences, end_differences, strict=True)
        ),
    }
    reuse = (
        overall["clear_active_count"] >= REUSE_MIN_SUBSTANTIAL_MAJORITY
        and overall["recognizable_active_plus_some_context"] >= REUSE_MIN_SUBSTANTIAL_MAJORITY
    )
    decision = (
        "REUSE_EXISTING_SOURCE_POOL" if reuse else "PURPOSE_BUILT_SEGMENTATION_CAPTURE_REQUIRED"
    )
    return {
        "schema": "apphear.phase5_1t.human_temporal_summary.v1",
        "milestone": MILESTONE,
        "by_source": by_source,
        "overall": overall,
        "d1_vs_human_asl_citizen": d1,
        "decision_rule": {
            "minimum_clear_active": REUSE_MIN_SUBSTANTIAL_MAJORITY,
            "minimum_active_plus_pre_or_post_context": REUSE_MIN_SUBSTANTIAL_MAJORITY,
            "denominator": EXPECTED_SAMPLE_COUNT,
            "frozen_before_human_review": True,
        },
        "final_decision": decision,
        "next": "WAIT_FOR_PROJECT_LEAD_PHASE_5_1T_2_SEGMENTATION_DATASET_CONSTRUCTION_DECISION",
    }


def _final_report(summary: dict[str, Any]) -> str:
    lines = [
        "# HUMAN_TEMPORAL_SEMANTICS_VALIDATION_REPORT",
        "",
        f"**Milestone:** `{MILESTONE}`  ",
        f"**Decision:** `{summary['final_decision']}`  ",
        "**Next:** `WAIT_FOR_PROJECT_LEAD_PHASE_5_1T_2_SEGMENTATION_DATASET_CONSTRUCTION_DECISION`",
        "",
        "## Scope and integrity",
        "",
        f"The frozen 24-sample manifest SHA-256 is `{EXPECTED_MANIFEST_SHA256}`. Exactly 24 human annotations were committed. ASL_CITIZEN D1 values remained server-side until each corresponding human boundary was committed.",
        "",
        "## Human semantic results",
        "",
        "| Source | Reviewed | Clear PRE | Clear ACTIVE | Clear POST | Full PRE/ACTIVE/POST usable | Active + some context | Ambiguous/unusable |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for source, item in summary["by_source"].items():
        lines.append(
            f"| {source} | {item['total_clips_reviewed']} | {item['clear_pre_count']} | "
            f"{item['clear_active_count']} | {item['clear_post_recovery_count']} | "
            f"{item['usable_for_pre_active_post_supervision']} | "
            f"{item['recognizable_active_plus_some_context']} | "
            f"{item['ambiguous_or_unusable_count']} |"
        )
    overall = summary["overall"]
    lines.append(
        f"| **OVERALL** | **{overall['total_clips_reviewed']}** | "
        f"**{overall['clear_pre_count']}** | **{overall['clear_active_count']}** | "
        f"**{overall['clear_post_recovery_count']}** | "
        f"**{overall['usable_for_pre_active_post_supervision']}** | "
        f"**{overall['recognizable_active_plus_some_context']}** | "
        f"**{overall['ambiguous_or_unusable_count']}** |"
    )
    d1 = summary["d1_vs_human_asl_citizen"]
    lines.extend(
        [
            "",
            "## ASL_CITIZEN D1 diagnostic comparison",
            "",
            f"Compared clips: `{d1['compared_clips']}`. Median absolute START difference: `{d1['median_absolute_start_difference_ms']}` ms. Median absolute END difference: `{d1['median_absolute_end_difference_ms']}` ms. Major disagreements over {MAJOR_DISAGREEMENT_MS:.0f} ms on either side: `{d1['major_disagreement_count']}`.",
            "",
            f"START direction: `{d1['start_direction']}`. END direction: `{d1['end_direction']}`. These values are descriptive only; no D1 threshold or span was changed.",
            "",
            "## Binary decision",
            "",
            f"`{summary['final_decision']}`",
            "",
            f"The preregistered practical rule requires at least {REUSE_MIN_SUBSTANTIAL_MAJORITY}/24 clear active signs and at least {REUSE_MIN_SUBSTANTIAL_MAJORITY}/24 non-ambiguous clips with a clear active sign plus clear PRE or POST context. No model, feature, threshold, source video, or D1 span was changed.",
            "",
            "## Stop boundary",
            "",
            "`WAIT_FOR_PROJECT_LEAD_PHASE_5_1T_2_SEGMENTATION_DATASET_CONSTRUCTION_DECISION`",
            "",
            "No large-scale annotation, dataset construction, model training, feature engineering, threshold tuning, or phone deployment was started.",
        ]
    )
    return "\n".join(lines) + "\n"


def awaiting_report(committed: int = 0) -> str:
    return f"""# HUMAN_TEMPORAL_SEMANTICS_VALIDATION_REPORT

**Milestone:** `{MILESTONE}`  
**Status:** `AWAITING_HUMAN_REVIEW`  
**Progress:** `{committed}/{EXPECTED_SAMPLE_COUNT}`

The technical gate is prepared, but no final binary decision is permitted until all 24 human
annotations have been committed. No annotations are fabricated by this utility.

Run:

```powershell
.\\.venv\\Scripts\\python.exe -m eval.runtime_diagnostics.phase5_1t_human_temporal_review serve
```

After completing all clips, run:

```powershell
.\\.venv\\Scripts\\python.exe -m eval.runtime_diagnostics.phase5_1t_human_temporal_review finalize
```
"""


def _hash_manifest(paths: Sequence[Path]) -> dict[str, Any]:
    return {
        "schema": "APPHEAR_PHASE5_1T_1_SOURCE_HASHES_V1",
        "files": [
            {"path": str(path.resolve()), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in sorted(paths, key=lambda item: str(item).casefold())
        ],
    }


def prepare(output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    manifest = load_frozen_manifest()
    metadata = [probe_video(Path(str(row["resolved_raw_video_path"]))) for row in manifest]
    output_root.mkdir(parents=True, exist_ok=True)
    frozen_copy = output_root / "frozen_visual_inspection_manifest.json"
    shutil.copyfile(INPUT_MANIFEST, frozen_copy)
    if sha256_file(frozen_copy) != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError("FROZEN_MANIFEST_COPY_MISMATCH")
    freeze = {
        "schema": "apphear.phase5_1t.review_input_freeze.v1",
        "milestone": MILESTONE,
        "source_manifest_path": str(INPUT_MANIFEST.resolve()),
        "source_manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "frozen_copy_path": str(frozen_copy.resolve()),
        "frozen_copy_sha256": sha256_file(frozen_copy),
        "sample_count": len(manifest),
        "source_counts": dict(sorted(Counter(row["source"] for row in manifest).items())),
        "sample_order": [row["sample_id"] for row in manifest],
        "d1_blinding": "D1 values are absent from public state until per-sample commit",
        "major_disagreement_ms": MAJOR_DISAGREEMENT_MS,
        "decision_minimum": REUSE_MIN_SUBSTANTIAL_MAJORITY,
    }
    _atomic_json_write(output_root / "input_manifest_freeze.json", freeze)
    annotation_path = output_root / "human_annotations.json"
    if not annotation_path.exists():
        _atomic_json_write(annotation_path, empty_annotation_document())
    document = load_annotation_document(annotation_path)
    (output_root / "HUMAN_TEMPORAL_SEMANTICS_VALIDATION_REPORT.md").write_text(
        awaiting_report(len(document["annotations"])), encoding="utf-8"
    )
    tool_snapshot = output_root / "review_tool_source.py"
    shutil.copyfile(Path(__file__).resolve(), tool_snapshot)
    test_path = ROOT / "tests/test_phase5_1t_human_temporal_review.py"
    sources = [Path(__file__).resolve(), tool_snapshot, test_path, INPUT_MANIFEST, frozen_copy]
    _atomic_json_write(output_root / "source_hashes.json", _hash_manifest(sources))
    return {"manifest": manifest, "metadata": metadata, "freeze": freeze}


HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>AppHear Phase 5.1T Human Temporal Review</title>
<style>
body{font:15px system-ui;margin:0;background:#111827;color:#e5e7eb}main{max-width:1050px;margin:auto;padding:20px}
.top,.panel{background:#1f2937;border:1px solid #374151;border-radius:10px;padding:14px;margin-bottom:14px}
video{width:100%;max-height:58vh;background:#000}.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
button{padding:9px 13px;border:0;border-radius:7px;background:#2563eb;color:white;cursor:pointer}button:disabled{opacity:.45}
.secondary{background:#4b5563}.commit{background:#059669}.danger{color:#fca5a5}.good{color:#86efac}
fieldset{border:1px solid #4b5563;border-radius:8px;margin:10px 0}label{margin-right:14px}
input[type=number],textarea{background:#111827;color:#fff;border:1px solid #4b5563;border-radius:6px;padding:7px}
textarea{width:98%;height:55px}.time{font:18px ui-monospace,monospace}.hint{color:#cbd5e1;font-size:13px}
</style></head><body><main>
<div class="top"><b>Phase 5.1T-1 — approximate temporal semantics review</b><div id="progress"></div>
<div class="hint">Mark one practical sign interval. Exclude obvious preparation/recovery where possible; do not micro-adjust for linguistic perfection. D1 is hidden until commit.</div></div>
<div class="panel"><div id="identity"></div><video id="video" controls preload="metadata"></video>
<div class="row"><button class="secondary" onclick="step(-1)">◀ 1 frame</button><button class="secondary" onclick="step(1)">1 frame ▶</button><span class="time" id="clock">0.000 s</span></div>
<div class="row"><button onclick="mark('start')">Mark SIGN START</button><input id="start" type="number" step="1" readonly> ms
<button onclick="mark('end')">Mark SIGN END</button><input id="end" type="number" step="1" readonly> ms</div></div>
<div class="panel" id="form">
<fieldset><legend>clear_pre_context</legend><label><input type="radio" name="pre" value="yes">YES</label><label><input type="radio" name="pre" value="no">NO</label></fieldset>
<fieldset><legend>clear_active_sign</legend><label><input type="radio" name="active" value="yes">YES</label><label><input type="radio" name="active" value="no">NO</label></fieldset>
<fieldset><legend>clear_post_recovery_context</legend><label><input type="radio" name="post" value="yes">YES</label><label><input type="radio" name="post" value="no">NO</label></fieldset>
<fieldset><legend>ambiguous_or_unusable</legend><label><input type="radio" name="ambiguous" value="yes">YES</label><label><input type="radio" name="ambiguous" value="no">NO</label></fieldset>
<label>Optional note</label><br><textarea id="note" maxlength="500"></textarea>
<div id="d1" class="hint"></div><div id="message"></div>
<div class="row"><button class="secondary" onclick="move(-1)">Previous</button><button class="commit" id="save" onclick="save()">Commit human annotation</button><button class="secondary" onclick="move(1)">Next</button></div></div>
</main><script>
let state, index=0; const video=document.getElementById('video');
const val=n=>{const x=document.querySelector(`input[name=${n}]:checked`);return x?x.value==='yes':null};
async function boot(){state=await (await fetch('/api/state')).json(); const first=state.samples.findIndex(x=>!x.committed); index=first<0?0:first; render()}
function render(){const s=state.samples[index];document.getElementById('progress').textContent=`${state.progress.committed}/${state.progress.total} committed · sample ${index+1}/${state.samples.length}`;
document.getElementById('identity').textContent=`${s.sample_id} · ${s.source} · signer ${s.signer_id} · gloss ${s.gloss}`;video.src=s.video_url;
for(const n of ['pre','active','post','ambiguous'])document.querySelectorAll(`input[name=${n}]`).forEach(x=>{x.checked=false;x.disabled=s.committed});
document.getElementById('start').value='';document.getElementById('end').value='';document.getElementById('note').value='';document.getElementById('note').disabled=s.committed;document.getElementById('save').disabled=s.committed;document.getElementById('d1').textContent='D1 diagnostic hidden until human commit.';document.getElementById('message').textContent='';
if(s.committed){const a=s.annotation;document.getElementById('start').value=a.human_sign_start_ms??'';document.getElementById('end').value=a.human_sign_end_ms??'';document.getElementById('note').value=a.reviewer_note;for(const [n,k] of Object.entries({pre:'clear_pre_context',active:'clear_active_sign',post:'clear_post_recovery_context',ambiguous:'ambiguous_or_unusable'})){document.querySelector(`input[name=${n}][value=${a[k]?'yes':'no'}]`).checked=true}document.getElementById('d1').textContent=a.source==='ASL_CITIZEN'?`Committed. D1 diagnostic: ${a.d1_onset_ms.toFixed(1)}–${a.d1_release_ms.toFixed(1)} ms; human−D1 ${a.human_minus_d1_start_ms?.toFixed(1)??'n/a'} / ${a.human_minus_d1_end_ms?.toFixed(1)??'n/a'} ms.`:'Committed. No D1 span for this source.'}}
video.ontimeupdate=()=>document.getElementById('clock').textContent=`${video.currentTime.toFixed(3)} s`;
function mark(which){if(state.samples[index].committed)return;document.getElementById(which).value=Math.round(video.currentTime*1000)}
function step(direction){const fps=state.samples[index].fps;video.pause();video.currentTime=Math.max(0,Math.min(video.duration||1e9,video.currentTime+direction/fps))}
function move(delta){index=Math.max(0,Math.min(state.samples.length-1,index+delta));render()}
async function save(){const s=state.samples[index], fields={pre:val('pre'),active:val('active'),post:val('post'),ambiguous:val('ambiguous')};if(Object.values(fields).some(x=>x===null)){msg('All four judgments are required.',true);return}const start=document.getElementById('start').value,end=document.getElementById('end').value;if((!start||!end)&&!fields.ambiguous){msg('Mark START and END, or mark ambiguous/unusable YES.',true);return}if(start&&end&&Number(start)>=Number(end)){msg('START must be before END.',true);return}if(!confirm('Commit this approximate annotation? D1 will be revealed afterward and the committed human annotation will remain immutable.'))return;
const body={human_sign_start_ms:start?Number(start):null,human_sign_end_ms:end?Number(end):null,clear_pre_context:fields.pre,clear_active_sign:fields.active,clear_post_recovery_context:fields.post,ambiguous_or_unusable:fields.ambiguous,reviewer_note:document.getElementById('note').value};const response=await fetch(`/api/annotations/${index}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const result=await response.json();if(!response.ok){msg(result.error||'Save failed',true);return}state=await (await fetch('/api/state')).json();render();msg('Committed and saved.',false)}
function msg(text,bad){const el=document.getElementById('message');el.textContent=text;el.className=bad?'danger':'good'}boot();
</script></body></html>"""


class ReviewApplication:
    def __init__(self, output_root: Path) -> None:
        prepared = prepare(output_root)
        self.manifest: list[dict[str, Any]] = prepared["manifest"]
        self.metadata: list[dict[str, float | int]] = prepared["metadata"]
        self.annotation_path = output_root / "human_annotations.json"
        self.lock = threading.Lock()

    def state(self) -> dict[str, Any]:
        return public_state(
            self.manifest, load_annotation_document(self.annotation_path), self.metadata
        )

    def commit(self, index: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return commit_annotation(
                manifest=self.manifest,
                annotation_path=self.annotation_path,
                sample_index=index,
                payload=payload,
                video_metadata=self.metadata,
            )


def make_handler(application: ReviewApplication) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "AppHearPhase5_1TReview/1"

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
                    row = application.manifest[index]
                except (ValueError, IndexError):
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self._video(Path(str(row["resolved_raw_video_path"])))
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


def finalize(output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    prepared = prepare(output_root)
    document = load_annotation_document(output_root / "human_annotations.json")
    summary = summarize_annotations(prepared["manifest"], document)
    _atomic_json_write(output_root / "human_semantic_summary.json", summary)
    (output_root / "HUMAN_TEMPORAL_SEMANTICS_VALIDATION_REPORT.md").write_text(
        _final_report(summary), encoding="utf-8"
    )
    document["status"] = "FINALIZED"
    document["final_decision"] = summary["final_decision"]
    _atomic_json_write(output_root / "human_annotations.json", document)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "serve", "finalize"))
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.output_root)
        print(json.dumps(result["freeze"], indent=2))
        return 0
    if args.command == "serve":
        return serve(args.output_root, args.host, args.port, not args.no_browser)
    summary = finalize(args.output_root)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
