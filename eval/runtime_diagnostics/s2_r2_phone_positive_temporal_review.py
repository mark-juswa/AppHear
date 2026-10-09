"""Human temporal review for bounded S2-R2 phone-positive supervision.

This diagnostic is deliberately blinded to S2 predictions.  It freezes selected attempts from
the governed rested phone session, shows only their synchronized source observations, and records
one practical sign interval per attempt.  START/STOP attempt markers are never converted into
PRE/ACTIVE/POST labels.  Finalization applies the already-governed 100 ms transition ignore band.
"""

# The local single-file review UI intentionally keeps embedded HTML/JS lines intact.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import csv
import json
import shutil
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

ROOT = Path(__file__).resolve().parents[2]
MILESTONE = "S2_R2_PHONE_TEMPORAL_SUPERVISION_01"
SESSION_ID = "session_20260921T102840Z"
TOOL_VERSION = "s2-r2-phone-positive-temporal-review-v1"
MANIFEST_SCHEMA = "apphear.s2_r2.phone_positive_review_manifest.v1"
ANNOTATION_SCHEMA = "apphear.s2_r2.phone_positive_temporal_annotations.v1"
LABEL_SCHEMA = "apphear.s2_r2.phone_positive_observation_labels.v1"
IGNORE_BAND_MS = 100.0

SESSION_ROOT = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
    / "phone_new_sign_admission_and_active_acquisition_validation_01/device_capture_final"
    / SESSION_ID
)
OUTPUT_ROOT = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
    / "s2_r2_phone_temporal_supervision_01/phone_positive_temporal_review_01"
)
REVIEW_MANIFEST = OUTPUT_ROOT / "phone_positive_review_manifest.json"
ANNOTATIONS = OUTPUT_ROOT / "phone_positive_temporal_annotations.json"

# TABLE attempt 6 remains excluded because the accepted diagnosis found materially weaker
# perception support.  It must not be promoted merely to increase sample count.
SELECTED_ATTEMPTS = (
    (1, "HELLO", "POSITIVE_ANCHOR"),
    (2, "HELLO", "HARD_POSITIVE_MISS"),
    (3, "HOME", "HARD_POSITIVE_MISS"),
    (4, "HOME", "HARD_POSITIVE_MISS"),
    (5, "TABLE", "POSITIVE_ANCHOR"),
)
TABLE_006_EXCLUDED_FOR_WEAK_PERCEPTION_SUPPORT = True


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_selected_attempts(session_root: Path = SESSION_ROOT) -> list[dict[str, Any]]:
    if not session_root.is_dir():
        raise FileNotFoundError(f"MISSING_GOVERNED_PHONE_SESSION:{session_root}")
    attempts: list[dict[str, Any]] = []
    for ordinal, expected_gloss, role in SELECTED_ATTEMPTS:
        attempt_id = f"attempt_{ordinal:03d}"
        attempt_root = session_root / attempt_id
        attempt_path = attempt_root / "phone_attempt.json"
        if not attempt_path.is_file():
            raise FileNotFoundError(f"MISSING_PHONE_ATTEMPT:{attempt_id}")
        payload = json.loads(attempt_path.read_text(encoding="utf-8-sig"))
        if payload.get("attempt_id") != attempt_id:
            raise ValueError(f"ATTEMPT_ID_MISMATCH:{attempt_id}")
        if payload.get("expected_gloss") != expected_gloss:
            raise ValueError(f"EXPECTED_GLOSS_MISMATCH:{attempt_id}")
        raw_frames = payload.get("visual_audit_frames")
        if not isinstance(raw_frames, list) or not raw_frames:
            raise ValueError(f"NO_VISUAL_AUDIT_FRAMES:{attempt_id}")
        frames: list[dict[str, Any]] = []
        seen_ordinals: set[int] = set()
        seen_timestamps: set[int] = set()
        for raw in raw_frames:
            observation_ordinal = int(raw["accepted_ordinal"])
            source_timestamp_ns = int(raw["source_timestamp_ns"])
            if observation_ordinal in seen_ordinals or source_timestamp_ns in seen_timestamps:
                raise ValueError(f"DUPLICATE_PHONE_OBSERVATION:{attempt_id}")
            seen_ordinals.add(observation_ordinal)
            seen_timestamps.add(source_timestamp_ns)
            original_path = attempt_root / str(raw["original_file"])
            if not original_path.is_file():
                raise FileNotFoundError(
                    f"MISSING_PHONE_ORIGINAL:{attempt_id}:{observation_ordinal}"
                )
            expected_hash = str(raw["original_sha256"]).lower()
            actual_hash = sha256_file(original_path)
            if actual_hash != expected_hash:
                raise RuntimeError(
                    f"PHONE_ORIGINAL_HASH_MISMATCH:{attempt_id}:{observation_ordinal}"
                )
            frames.append(
                {
                    "observation_ordinal": observation_ordinal,
                    "source_timestamp_ns": source_timestamp_ns,
                    "original_path": str(original_path.resolve()),
                    "original_sha256": actual_hash,
                }
            )
        frames.sort(key=lambda item: item["source_timestamp_ns"])
        if [item["observation_ordinal"] for item in frames] != list(range(1, len(frames) + 1)):
            raise ValueError(f"NONCONTIGUOUS_VISUAL_ORDINALS:{attempt_id}")
        first_ns = frames[0]["source_timestamp_ns"]
        for frame in frames:
            frame["relative_timestamp_ms"] = (frame["source_timestamp_ns"] - first_ns) / 1_000_000.0
        attempts.append(
            {
                "attempt_id": attempt_id,
                "attempt_ordinal": ordinal,
                "expected_gloss": expected_gloss,
                "supervision_role": role,
                "attempt_path": str(attempt_path.resolve()),
                "attempt_sha256": sha256_file(attempt_path),
                "frame_count": len(frames),
                "frames": frames,
            }
        )
    return attempts


def build_manifest(attempts: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "milestone": MILESTONE,
        "tool_version": TOOL_VERSION,
        "session_id": SESSION_ID,
        "session_root": str(SESSION_ROOT.resolve()),
        "selected_attempt_count": len(attempts),
        "ignore_band_ms": IGNORE_BAND_MS,
        "attempts": list(attempts),
        "governance": {
            "s2_predictions_exposed_to_reviewer": False,
            "attempt_markers_used_as_temporal_labels": False,
            "training": False,
            "protected_test_accessed": False,
            "table_attempt_006_excluded_for_weak_perception_support": (
                TABLE_006_EXCLUDED_FOR_WEAK_PERCEPTION_SUPPORT
            ),
        },
    }


def empty_annotations(manifest_hash: str) -> dict[str, Any]:
    return {
        "schema": ANNOTATION_SCHEMA,
        "milestone": MILESTONE,
        "tool_version": TOOL_VERSION,
        "review_manifest_sha256": manifest_hash,
        "status": "AWAITING_HUMAN_REVIEW",
        "annotations": [],
    }


def load_annotations(path: Path, manifest_hash: str) -> dict[str, Any]:
    if not path.is_file():
        return empty_annotations(manifest_hash)
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload.get("schema") != ANNOTATION_SCHEMA:
        raise ValueError("ANNOTATION_SCHEMA_MISMATCH")
    if payload.get("review_manifest_sha256") != manifest_hash:
        raise ValueError("ANNOTATION_MANIFEST_IDENTITY_MISMATCH")
    annotations = payload.get("annotations")
    if not isinstance(annotations, list):
        raise ValueError("ANNOTATIONS_NOT_LIST")
    ids = [str(item.get("attempt_id")) for item in annotations]
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_ATTEMPT_ANNOTATION")
    return payload


def validate_annotation(payload: dict[str, Any], frame_count: int) -> dict[str, Any]:
    if payload.get("full_attempt_reviewed") is not True:
        raise ValueError("FULL_ATTEMPT_REVIEW_CONFIRMATION_REQUIRED")
    judgments: dict[str, bool] = {}
    for key in ("clear_pre_context", "clear_active_sign", "clear_post_recovery", "ambiguous"):
        value = payload.get(key)
        if not isinstance(value, bool):
            raise ValueError(f"BOOLEAN_JUDGMENT_REQUIRED:{key}")
        judgments[key] = value
    start = payload.get("sign_start_ordinal")
    end = payload.get("sign_end_ordinal")
    if judgments["ambiguous"]:
        if start is not None or end is not None:
            raise ValueError("AMBIGUOUS_ATTEMPT_MUST_NOT_DEFINE_BOUNDARIES")
    else:
        if not judgments["clear_active_sign"]:
            raise ValueError("NON_AMBIGUOUS_ATTEMPT_REQUIRES_CLEAR_ACTIVE_SIGN")
        if not isinstance(start, int) or not isinstance(end, int):
            raise ValueError("SIGN_BOUNDARY_ORDINALS_REQUIRED")
        if start < 1 or end < start or end > frame_count:
            raise ValueError(f"INVALID_SIGN_BOUNDARY_ORDINALS:{start}:{end}")
    return {
        "sign_start_ordinal": start,
        "sign_end_ordinal": end,
        **judgments,
        "reviewer_note": str(payload.get("reviewer_note", "")).strip()[:500],
    }


def commit_annotation(
    *,
    attempts: Sequence[dict[str, Any]],
    annotation_path: Path,
    manifest_hash: str,
    index: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if index < 0 or index >= len(attempts):
        raise IndexError("ATTEMPT_INDEX_OUT_OF_RANGE")
    attempt = attempts[index]
    document = load_annotations(annotation_path, manifest_hash)
    if any(item["attempt_id"] == attempt["attempt_id"] for item in document["annotations"]):
        raise ValueError("ANNOTATION_ALREADY_COMMITTED_IMMUTABLE")
    validated = validate_annotation(payload, int(attempt["frame_count"]))
    if validated["sign_start_ordinal"] is not None:
        frames = attempt["frames"]
        start_frame = frames[int(validated["sign_start_ordinal"]) - 1]
        end_frame = frames[int(validated["sign_end_ordinal"]) - 1]
        validated["sign_start_source_timestamp_ns"] = start_frame["source_timestamp_ns"]
        validated["sign_end_source_timestamp_ns"] = end_frame["source_timestamp_ns"]
        validated["sign_start_relative_ms"] = start_frame["relative_timestamp_ms"]
        validated["sign_end_relative_ms"] = end_frame["relative_timestamp_ms"]
    else:
        validated["sign_start_source_timestamp_ns"] = None
        validated["sign_end_source_timestamp_ns"] = None
        validated["sign_start_relative_ms"] = None
        validated["sign_end_relative_ms"] = None
    annotation = {
        "schema": ANNOTATION_SCHEMA,
        "attempt_id": attempt["attempt_id"],
        "attempt_ordinal": attempt["attempt_ordinal"],
        "expected_gloss": attempt["expected_gloss"],
        "supervision_role": attempt["supervision_role"],
        "frame_count": attempt["frame_count"],
        "full_attempt_reviewed": True,
        **validated,
        "review_timestamp": datetime.now(UTC).isoformat(),
        "tool_version": TOOL_VERSION,
    }
    document["annotations"].append(annotation)
    order = {item["attempt_id"]: idx for idx, item in enumerate(attempts)}
    document["annotations"].sort(key=lambda item: order[item["attempt_id"]])
    document["status"] = (
        "COMPLETE_PENDING_FINALIZE"
        if len(document["annotations"]) == len(attempts)
        else "IN_PROGRESS"
    )
    _atomic_json_write(annotation_path, document)
    return annotation


def prepare(output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    # Resolve SESSION_ROOT at call time so governed review profiles can reuse this
    # implementation without duplicating the review server or silently falling
    # back to the rested-session default captured in the function signature.
    attempts = load_selected_attempts(SESSION_ROOT)
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / REVIEW_MANIFEST.name
    manifest = build_manifest(attempts)
    if manifest_path.is_file():
        existing = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if existing != manifest:
            raise RuntimeError("FROZEN_PHONE_REVIEW_MANIFEST_DRIFT")
    else:
        _atomic_json_write(manifest_path, manifest)
    manifest_hash = sha256_file(manifest_path)
    annotation_path = output_root / ANNOTATIONS.name
    if not annotation_path.is_file():
        _atomic_json_write(annotation_path, empty_annotations(manifest_hash))
    load_annotations(annotation_path, manifest_hash)
    shutil.copyfile(Path(__file__).resolve(), output_root / "review_tool_source.py")
    return {
        "attempts": attempts,
        "manifest_path": manifest_path,
        "manifest_sha256": manifest_hash,
        "annotation_path": annotation_path,
    }


def derive_observation_labels(
    attempt: dict[str, Any], annotation: dict[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if annotation["ambiguous"]:
        for frame in attempt["frames"]:
            rows.append({**frame, "state_id": -1, "state_name": "IGNORED"})
        return rows
    start_ms = float(annotation["sign_start_relative_ms"])
    end_ms = float(annotation["sign_end_relative_ms"])
    for frame in attempt["frames"]:
        timestamp_ms = float(frame["relative_timestamp_ms"])
        state_id = -1
        state_name = "IGNORED"
        if annotation["clear_pre_context"] and timestamp_ms < start_ms - IGNORE_BAND_MS:
            state_id, state_name = 0, "PRE_IDLE"
        elif (
            annotation["clear_active_sign"]
            and timestamp_ms > start_ms + IGNORE_BAND_MS
            and timestamp_ms < end_ms - IGNORE_BAND_MS
        ):
            state_id, state_name = 1, "ACTIVE_SIGN"
        elif annotation["clear_post_recovery"] and timestamp_ms > end_ms + IGNORE_BAND_MS:
            state_id, state_name = 2, "POST_RECOVERY"
        rows.append({**frame, "state_id": state_id, "state_name": state_name})
    return rows


def _write_labels_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    fieldnames = [
        "session_id",
        "attempt_id",
        "attempt_ordinal",
        "expected_gloss",
        "supervision_role",
        "observation_ordinal",
        "source_timestamp_ns",
        "relative_timestamp_ms",
        "original_path",
        "original_sha256",
        "state_id",
        "state_name",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def finalize(output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    prepared = prepare(output_root)
    document = load_annotations(prepared["annotation_path"], prepared["manifest_sha256"])
    if len(document["annotations"]) != len(prepared["attempts"]):
        raise RuntimeError(
            f"PHONE_POSITIVE_HUMAN_REVIEW_INCOMPLETE:{len(document['annotations'])}/{len(prepared['attempts'])}"
        )
    by_id = {item["attempt_id"]: item for item in document["annotations"]}
    label_rows: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()
    attempt_summaries: list[dict[str, Any]] = []
    for attempt in prepared["attempts"]:
        annotation = by_id[attempt["attempt_id"]]
        derived = derive_observation_labels(attempt, annotation)
        for row in derived:
            output_row = {
                "session_id": SESSION_ID,
                "attempt_id": attempt["attempt_id"],
                "attempt_ordinal": attempt["attempt_ordinal"],
                "expected_gloss": attempt["expected_gloss"],
                "supervision_role": attempt["supervision_role"],
                **row,
            }
            label_counts[output_row["state_name"]] += 1
            label_rows.append(output_row)
        attempt_summaries.append(
            {
                "attempt_id": attempt["attempt_id"],
                "expected_gloss": attempt["expected_gloss"],
                "supervision_role": attempt["supervision_role"],
                "ambiguous": annotation["ambiguous"],
                "clear_pre_context": annotation["clear_pre_context"],
                "clear_active_sign": annotation["clear_active_sign"],
                "clear_post_recovery": annotation["clear_post_recovery"],
                "sign_start_ordinal": annotation["sign_start_ordinal"],
                "sign_end_ordinal": annotation["sign_end_ordinal"],
                "observation_label_counts": dict(Counter(row["state_name"] for row in derived)),
                "eligible_for_s2_r2_positive": bool(
                    not annotation["ambiguous"] and annotation["clear_active_sign"]
                ),
            }
        )
    summary = {
        "schema": LABEL_SCHEMA,
        "milestone": MILESTONE,
        "session_id": SESSION_ID,
        "review_manifest_sha256": prepared["manifest_sha256"],
        "ignore_band_ms": IGNORE_BAND_MS,
        "attempts_reviewed": len(prepared["attempts"]),
        "attempt_summaries": attempt_summaries,
        "observation_label_counts": dict(sorted(label_counts.items())),
        "training_authorized": False,
        "independent_validation_claim": False,
    }
    _write_labels_csv(output_root / "phone_positive_observation_labels.csv", label_rows)
    _atomic_json_write(output_root / "phone_positive_temporal_review_summary.json", summary)
    document["status"] = "FINALIZED"
    _atomic_json_write(prepared["annotation_path"], document)
    return summary


def public_state(attempts: Sequence[dict[str, Any]], document: dict[str, Any]) -> dict[str, Any]:
    saved = {item["attempt_id"]: item for item in document["annotations"]}
    samples = []
    for index, attempt in enumerate(attempts):
        frames = [
            {
                "observation_ordinal": frame["observation_ordinal"],
                "source_timestamp_ns": frame["source_timestamp_ns"],
                "relative_timestamp_ms": frame["relative_timestamp_ms"],
                "image_url": f"/image/{index}/{frame_index}",
            }
            for frame_index, frame in enumerate(attempt["frames"])
        ]
        sample = {
            "index": index,
            "attempt_id": attempt["attempt_id"],
            "expected_gloss": attempt["expected_gloss"],
            "supervision_role": attempt["supervision_role"],
            "frame_count": attempt["frame_count"],
            "frames": frames,
            "committed": attempt["attempt_id"] in saved,
        }
        if sample["committed"]:
            sample["annotation"] = saved[attempt["attempt_id"]]
        samples.append(sample)
    return {
        "schema": ANNOTATION_SCHEMA,
        "tool_version": TOOL_VERSION,
        "progress": {"committed": len(saved), "total": len(attempts)},
        "samples": samples,
    }


HTML = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>AppHear phone positive temporal review</title><style>body{font:15px system-ui;background:#111827;color:#e5e7eb;margin:0}main{max-width:1000px;margin:auto;padding:18px}.panel{background:#1f2937;border:1px solid #374151;border-radius:10px;padding:14px;margin-bottom:12px}img{display:block;max-width:100%;max-height:62vh;margin:auto;background:#000}button{padding:8px 12px;border:0;border-radius:6px;background:#2563eb;color:white;margin:3px}.secondary{background:#4b5563}.commit{background:#059669}.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0}input,textarea{background:#111827;color:#fff;border:1px solid #4b5563;border-radius:5px;padding:6px}input[type=range]{width:100%}.hint{color:#cbd5e1;font-size:13px}.bad{color:#fca5a5}.good{color:#86efac}fieldset{display:inline-block;border:1px solid #4b5563;margin:4px}textarea{width:98%}</style></head><body><main><div class="panel"><b>S2-R2 phone-positive temporal review</b><div id="progress"></div><div class="hint">S2 predictions are hidden. Review the full attempt and mark one practical visible sign interval. Exclude obvious preparation and recovery; do not use the attempt START/STOP as sign boundaries.</div></div><div class="panel"><div id="identity"></div><img id="image"><input id="slider" type="range" min="0" step="1"><div class="row"><button class="secondary" onclick="step(-1)">◀ observation</button><button class="secondary" onclick="step(1)">observation ▶</button><span id="position"></span><button onclick="mark('start')">Mark SIGN START</button><input id="start" readonly size="5"><button onclick="mark('end')">Mark SIGN END</button><input id="end" readonly size="5"></div></div><div class="panel"><div id="judgments"></div><label><input id="full" type="checkbox"> I reviewed the complete attempt</label><br><textarea id="note" placeholder="optional review note"></textarea><div id="message"></div><div class="row"><button class="secondary" onclick="move(-1)">Previous</button><button class="commit" id="commit" onclick="commitReview()">Commit immutable attempt review</button><button class="secondary" onclick="move(1)">Next</button></div></div></main><script>let state,index=0,frame=0;const image=document.getElementById('image'),slider=document.getElementById('slider');const questions=[['pre','clear PRE context'],['active','clear ACTIVE sign'],['post','clear POST/recovery context'],['ambiguous','ambiguous/unusable']];async function boot(){state=await(await fetch('/api/state')).json();document.getElementById('judgments').innerHTML=questions.map(([n,l])=>`<fieldset><legend>${l}</legend><label><input type="radio" name="${n}" value="yes">YES</label><label><input type="radio" name="${n}" value="no">NO</label></fieldset>`).join('');const first=state.samples.findIndex(x=>!x.committed);index=first<0?0:first;render()}function render(){const s=state.samples[index];frame=0;slider.max=s.frames.length-1;slider.value=0;document.getElementById('progress').textContent=`${state.progress.committed}/${state.progress.total} committed · attempt ${index+1}/${state.samples.length}`;document.getElementById('identity').textContent=`${s.attempt_id} · ${s.expected_gloss} · ${s.supervision_role} · ${s.frame_count} observations`;for(const id of ['start','end','note'])document.getElementById(id).value='';document.getElementById('full').checked=false;questions.forEach(([n])=>document.querySelectorAll(`input[name=${n}]`).forEach(x=>{x.checked=false;x.disabled=s.committed}));document.getElementById('commit').disabled=s.committed;if(s.committed){const a=s.annotation;document.getElementById('start').value=a.sign_start_ordinal??'';document.getElementById('end').value=a.sign_end_ordinal??'';document.getElementById('note').value=a.reviewer_note;document.getElementById('full').checked=true;for(const [n,k] of Object.entries({pre:'clear_pre_context',active:'clear_active_sign',post:'clear_post_recovery',ambiguous:'ambiguous'}))document.querySelector(`input[name=${n}][value=${a[k]?'yes':'no'}]`).checked=true}show()}function show(){const s=state.samples[index],f=s.frames[frame];slider.value=frame;image.src=f.image_url;document.getElementById('position').textContent=`${f.observation_ordinal}/${s.frame_count} · ${f.relative_timestamp_ms.toFixed(1)} ms`}slider.oninput=()=>{frame=Number(slider.value);show()};function step(d){frame=Math.max(0,Math.min(state.samples[index].frames.length-1,frame+d));show()}function mark(which){if(!state.samples[index].committed)document.getElementById(which).value=state.samples[index].frames[frame].observation_ordinal}function move(d){index=Math.max(0,Math.min(state.samples.length-1,index+d));render()}function val(n){const x=document.querySelector(`input[name=${n}]:checked`);return x?x.value==='yes':null}function msg(t,b){const e=document.getElementById('message');e.textContent=t;e.className=b?'bad':'good'}async function commitReview(){if(!document.getElementById('full').checked){msg('Confirm that the complete attempt was reviewed.',true);return}const fields={clear_pre_context:val('pre'),clear_active_sign:val('active'),clear_post_recovery:val('post'),ambiguous:val('ambiguous')};if(Object.values(fields).some(x=>x===null)){msg('All four judgments are required.',true);return}const start=document.getElementById('start').value,end=document.getElementById('end').value;if(fields.ambiguous&&(start||end)){msg('Clear START/END when marking the attempt ambiguous.',true);return}if(!fields.ambiguous&&(!start||!end)){msg('Mark SIGN START and SIGN END.',true);return}if(!fields.ambiguous&&Number(start)>Number(end)){msg('START must not follow END.',true);return}if(!confirm('Commit this human temporal review? It is immutable.'))return;const body={full_attempt_reviewed:true,sign_start_ordinal:start?Number(start):null,sign_end_ordinal:end?Number(end):null,...fields,reviewer_note:document.getElementById('note').value};const response=await fetch(`/api/annotations/${index}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const result=await response.json();if(!response.ok){msg(result.error||'Save failed',true);return}state=await(await fetch('/api/state')).json();render();msg('Committed.',false)}boot();</script></body></html>"""


class ReviewApplication:
    def __init__(self, output_root: Path) -> None:
        prepared = prepare(output_root)
        self.attempts = prepared["attempts"]
        self.annotation_path = prepared["annotation_path"]
        self.manifest_hash = prepared["manifest_sha256"]
        self.lock = threading.Lock()

    def state(self) -> dict[str, Any]:
        return public_state(
            self.attempts, load_annotations(self.annotation_path, self.manifest_hash)
        )

    def commit(self, index: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return commit_annotation(
                attempts=self.attempts,
                annotation_path=self.annotation_path,
                manifest_hash=self.manifest_hash,
                index=index,
                payload=payload,
            )


def make_handler(application: ReviewApplication) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "AppHearS2R2PhonePositiveReview/1"

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
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/api/state":
                self._json(application.state())
                return
            if parsed.path.startswith("/image/"):
                try:
                    _, _, attempt_index_raw, frame_index_raw = parsed.path.split("/")
                    attempt_index = int(attempt_index_raw)
                    frame_index = int(frame_index_raw)
                    path = Path(
                        application.attempts[attempt_index]["frames"][frame_index]["original_path"]
                    )
                except (ValueError, IndexError):
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                body = path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(HTTPStatus.NOT_FOUND)

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
                self._json(
                    {"status": "COMMITTED", "annotation": application.commit(index, payload)}
                )
            except (IndexError, ValueError, json.JSONDecodeError) as error:
                self._json({"error": str(error)}, status=400)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def serve(output_root: Path, host: str, port: int, open_browser: bool) -> int:
    application = ReviewApplication(output_root)
    server = ThreadingHTTPServer((host, port), make_handler(application))
    url = f"http://{host}:{port}/"
    print(f"Phone-positive temporal review: {url}")
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
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        prepared = prepare(args.output_root)
        print(
            json.dumps(
                {
                    "attempts": len(prepared["attempts"]),
                    "manifest": str(prepared["manifest_path"]),
                    "manifest_sha256": prepared["manifest_sha256"],
                    "annotations": str(prepared["annotation_path"]),
                },
                indent=2,
            )
        )
        return 0
    if args.command == "serve":
        return serve(args.output_root, args.host, args.port, not args.no_browser)
    print(json.dumps(finalize(args.output_root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
