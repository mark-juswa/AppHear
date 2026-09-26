"""Bounded human review for recovered S2-R2 phone temporal supervision.

This module does not run perception, model inference, or training.  It freezes the historical
P1 raw-video inventory and records immutable, bounded semantic intervals.  Unmarked time is
excluded by construction; capture instructions and old frame labels never become blanket PRE
labels.
"""

# The single-file local review UI intentionally keeps embedded HTML/JS lines intact.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import csv
import json
import math
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

import cv2

ROOT = Path(__file__).resolve().parents[2]
MILESTONE = "S2_R2_PHONE_TEMPORAL_SUPERVISION_01"
TOOL_VERSION = "s2-r2-p1-temporal-review-v1"
ANNOTATION_SCHEMA = "apphear.s2_r2.p1_temporal_annotations.v1"
MANIFEST_SCHEMA = "apphear.s2_r2.p1_review_manifest.v1"

P1_CAPTURE_MANIFEST = (
    ROOT / "artifacts/recognition_upgrade/e2e_c0/p1_capture_03/capture_manifest.csv"
)
OUTPUT_ROOT = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
    / "s2_r2_phone_temporal_supervision_01/p1_temporal_review_01"
)
REVIEW_MANIFEST = OUTPUT_ROOT / "p1_review_manifest.json"
ANNOTATIONS = OUTPUT_ROOT / "p1_temporal_annotations.json"

CATEGORIES = {
    "CONFIRMED_NON_SIGN",
    "AMBIGUOUS_EXCLUDE",
    "POSSIBLE_LEXICAL_OR_SIGN_PREPARATION",
}
BEHAVIOR_TAGS = {
    "NEUTRAL_STILLNESS",
    "VISIBLE_HAND_MOVEMENT",
    "OBJECT_OR_PHONE_INTERACTION",
    "GROOMING_OR_ADJUSTMENT",
    "CASUAL_POINTING",
    "HAND_CROSSING_OR_OCCLUSION",
    "HANDS_ENTERING_OR_LEAVING_FRAME",
    "BODY_REPOSITIONING",
    "OTHER_NON_SIGN_MOTION",
}


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


def probe_video(path: Path) -> dict[str, int | float]:
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise OSError(f"VIDEO_OPEN_FAILED:{path}")
        frame_count = int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        if frame_count <= 0 or not math.isfinite(fps) or fps <= 0:
            raise ValueError(f"INVALID_VIDEO_TIMEBASE:{path}:{frame_count}:{fps}")
        return {
            "frame_count": frame_count,
            "fps": fps,
            "duration_ms": 1000.0 * frame_count / fps,
        }
    finally:
        capture.release()


def load_source_manifest(path: Path = P1_CAPTURE_MANIFEST) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        raw_rows = list(csv.DictReader(stream))
    if len(raw_rows) != 30:
        raise RuntimeError(f"P1_SOURCE_COUNT_MISMATCH:{len(raw_rows)}")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_rows:
        clip_id = str(raw["clip_id"])
        if clip_id in seen:
            raise RuntimeError(f"DUPLICATE_CLIP_ID:{clip_id}")
        seen.add(clip_id)
        video = Path(str(raw["video_path"]))
        if not video.is_file():
            raise FileNotFoundError(f"MISSING_P1_VIDEO:{clip_id}:{video}")
        expected_hash = str(raw["sha256"]).lower()
        actual_hash = sha256_file(video)
        if actual_hash != expected_hash:
            raise RuntimeError(f"P1_VIDEO_HASH_MISMATCH:{clip_id}:{actual_hash}")
        metadata = probe_video(video)
        rows.append(
            {
                "clip_id": clip_id,
                "participant_id": str(raw["participant_id"]),
                "device_id": str(raw["device_id"]),
                "environment_id": str(raw["environment_id"]),
                "camera_facing": str(raw["camera_facing"]),
                "video_path": str(video.resolve()),
                "video_sha256": actual_hash,
                **metadata,
            }
        )
    rows.sort(key=lambda row: (str(row["participant_id"]), str(row["clip_id"])))
    return rows


def build_review_manifest(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "milestone": MILESTONE,
        "tool_version": TOOL_VERSION,
        "source_manifest_path": str(P1_CAPTURE_MANIFEST.resolve()),
        "source_manifest_sha256": sha256_file(P1_CAPTURE_MANIFEST),
        "clip_count": len(rows),
        "rows": list(rows),
        "governance": {
            "historical_experiment_rerun": False,
            "model_inference": False,
            "training": False,
            "protected_test_accessed": False,
            "unmarked_time_disposition": "EXCLUDED",
            "whole_clip_auto_pre_label": False,
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
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if document.get("schema") != ANNOTATION_SCHEMA:
        raise ValueError("ANNOTATION_SCHEMA_MISMATCH")
    if document.get("review_manifest_sha256") != manifest_hash:
        raise ValueError("ANNOTATION_MANIFEST_IDENTITY_MISMATCH")
    annotations = document.get("annotations")
    if not isinstance(annotations, list):
        raise ValueError("ANNOTATIONS_NOT_LIST")
    ids = [item.get("clip_id") for item in annotations]
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_CLIP_ANNOTATION")
    return document


def validate_intervals(payload: dict[str, Any], duration_ms: float) -> list[dict[str, Any]]:
    if payload.get("full_video_reviewed") is not True:
        raise ValueError("FULL_VIDEO_REVIEW_CONFIRMATION_REQUIRED")
    raw_intervals = payload.get("intervals")
    if not isinstance(raw_intervals, list) or not raw_intervals:
        raise ValueError("AT_LEAST_ONE_EXPLICIT_INTERVAL_REQUIRED")
    intervals: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_intervals):
        if not isinstance(raw, dict):
            raise ValueError(f"INTERVAL_NOT_OBJECT:{index}")
        category = str(raw.get("category", ""))
        if category not in CATEGORIES:
            raise ValueError(f"INVALID_INTERVAL_CATEGORY:{index}:{category}")
        start_ms = float(raw.get("start_ms"))
        end_ms = float(raw.get("end_ms"))
        if not math.isfinite(start_ms) or not math.isfinite(end_ms):
            raise ValueError(f"NONFINITE_INTERVAL:{index}")
        if start_ms < 0 or start_ms >= end_ms or end_ms > duration_ms + 1.0:
            raise ValueError(f"INVALID_INTERVAL_BOUNDS:{index}:{start_ms}:{end_ms}")
        tags = sorted({str(tag) for tag in raw.get("behavior_tags", [])})
        invalid_tags = set(tags) - BEHAVIOR_TAGS
        if invalid_tags:
            raise ValueError(f"INVALID_BEHAVIOR_TAG:{index}:{sorted(invalid_tags)}")
        if category == "CONFIRMED_NON_SIGN" and not tags:
            raise ValueError(f"NON_SIGN_BEHAVIOR_TAG_REQUIRED:{index}")
        intervals.append(
            {
                "start_ms": start_ms,
                "end_ms": end_ms,
                "category": category,
                "behavior_tags": tags,
                "note": str(raw.get("note", "")).strip()[:300],
            }
        )
    intervals.sort(key=lambda item: (item["start_ms"], item["end_ms"]))
    for previous, current in zip(intervals, intervals[1:], strict=False):
        if current["start_ms"] < previous["end_ms"]:
            raise ValueError(
                f"OVERLAPPING_INTERVALS:{previous['end_ms']}:{current['start_ms']}"
            )
    return intervals


def commit_annotation(
    *,
    rows: Sequence[dict[str, Any]],
    annotation_path: Path,
    manifest_hash: str,
    index: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if index < 0 or index >= len(rows):
        raise IndexError("CLIP_INDEX_OUT_OF_RANGE")
    row = rows[index]
    document = load_annotations(annotation_path, manifest_hash)
    if any(item["clip_id"] == row["clip_id"] for item in document["annotations"]):
        raise ValueError("ANNOTATION_ALREADY_COMMITTED_IMMUTABLE")
    intervals = validate_intervals(payload, float(row["duration_ms"]))
    annotation = {
        "schema": ANNOTATION_SCHEMA,
        "clip_id": row["clip_id"],
        "participant_id": row["participant_id"],
        "device_id": row["device_id"],
        "environment_id": row["environment_id"],
        "video_path": row["video_path"],
        "video_sha256": row["video_sha256"],
        "duration_ms": row["duration_ms"],
        "full_video_reviewed": True,
        "intervals": intervals,
        "reviewer_note": str(payload.get("reviewer_note", "")).strip()[:500],
        "review_timestamp": datetime.now(UTC).isoformat(),
        "tool_version": TOOL_VERSION,
    }
    document["annotations"].append(annotation)
    order = {row["clip_id"]: idx for idx, row in enumerate(rows)}
    document["annotations"].sort(key=lambda item: order[item["clip_id"]])
    document["status"] = (
        "COMPLETE_PENDING_FINALIZE"
        if len(document["annotations"]) == len(rows)
        else "IN_PROGRESS"
    )
    _atomic_json_write(annotation_path, document)
    return annotation


def prepare(output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    rows = load_source_manifest()
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / REVIEW_MANIFEST.name
    manifest = build_review_manifest(rows)
    if manifest_path.is_file():
        existing = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if existing != manifest:
            raise RuntimeError("FROZEN_REVIEW_MANIFEST_DRIFT")
    else:
        _atomic_json_write(manifest_path, manifest)
    manifest_hash = sha256_file(manifest_path)
    annotation_path = output_root / ANNOTATIONS.name
    if not annotation_path.is_file():
        _atomic_json_write(annotation_path, empty_annotations(manifest_hash))
    load_annotations(annotation_path, manifest_hash)
    shutil.copyfile(Path(__file__).resolve(), output_root / "review_tool_source.py")
    return {
        "rows": rows,
        "manifest_path": manifest_path,
        "manifest_sha256": manifest_hash,
        "annotation_path": annotation_path,
    }


def summarize(rows: Sequence[dict[str, Any]], document: dict[str, Any]) -> dict[str, Any]:
    if len(document["annotations"]) != len(rows):
        raise RuntimeError(
            f"P1_HUMAN_REVIEW_INCOMPLETE:{len(document['annotations'])}/{len(rows)}"
        )
    interval_counts: Counter[str] = Counter()
    duration_by_category: Counter[str] = Counter()
    behavior_duration: Counter[str] = Counter()
    usable_by_participant: Counter[str] = Counter()
    rows_out: list[dict[str, Any]] = []
    for annotation in document["annotations"]:
        for ordinal, interval in enumerate(annotation["intervals"], start=1):
            duration = float(interval["end_ms"]) - float(interval["start_ms"])
            interval_counts[interval["category"]] += 1
            duration_by_category[interval["category"]] += duration
            if interval["category"] == "CONFIRMED_NON_SIGN":
                usable_by_participant[annotation["participant_id"]] += 1
                for tag in interval["behavior_tags"]:
                    behavior_duration[tag] += duration
            rows_out.append(
                {
                    "interval_id": f"{annotation['clip_id']}::{ordinal:03d}",
                    "clip_id": annotation["clip_id"],
                    "participant_id": annotation["participant_id"],
                    "device_id": annotation["device_id"],
                    "environment_id": annotation["environment_id"],
                    "video_path": annotation["video_path"],
                    "video_sha256": annotation["video_sha256"],
                    **interval,
                    "duration_ms": duration,
                    "eligible_for_s2_r2_negative": interval["category"]
                    == "CONFIRMED_NON_SIGN",
                }
            )
    return {
        "schema": "apphear.s2_r2.p1_temporal_review_summary.v1",
        "milestone": MILESTONE,
        "clips_reviewed": len(document["annotations"]),
        "interval_counts": dict(sorted(interval_counts.items())),
        "duration_ms_by_category": dict(sorted(duration_by_category.items())),
        "confirmed_non_sign_behavior_duration_ms": dict(sorted(behavior_duration.items())),
        "confirmed_non_sign_interval_count_by_participant": dict(
            sorted(usable_by_participant.items())
        ),
        "eligible_intervals": sum(
            item["eligible_for_s2_r2_negative"] for item in rows_out
        ),
        "interval_rows": rows_out,
        "decision_pending_signer_governance": True,
        "training_authorized": False,
    }


def _write_interval_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    fieldnames = [
        "interval_id",
        "clip_id",
        "participant_id",
        "device_id",
        "environment_id",
        "video_path",
        "video_sha256",
        "start_ms",
        "end_ms",
        "duration_ms",
        "category",
        "behavior_tags",
        "note",
        "eligible_for_s2_r2_negative",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            encoded = dict(row)
            encoded["behavior_tags"] = ";".join(row["behavior_tags"])
            writer.writerow(encoded)


def finalize(output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    prepared = prepare(output_root)
    document = load_annotations(
        prepared["annotation_path"], prepared["manifest_sha256"]
    )
    summary = summarize(prepared["rows"], document)
    _atomic_json_write(output_root / "p1_temporal_review_summary.json", summary)
    _write_interval_csv(output_root / "p1_reviewed_intervals.csv", summary["interval_rows"])
    document["status"] = "FINALIZED"
    _atomic_json_write(prepared["annotation_path"], document)
    compact = dict(summary)
    compact.pop("interval_rows")
    return compact


def public_state(
    rows: Sequence[dict[str, Any]], document: dict[str, Any]
) -> dict[str, Any]:
    saved = {item["clip_id"]: item for item in document["annotations"]}
    samples = []
    for index, row in enumerate(rows):
        item = {
            **row,
            "index": index,
            "video_url": f"/video/{index}",
            "committed": row["clip_id"] in saved,
        }
        if item["committed"]:
            item["annotation"] = saved[row["clip_id"]]
        samples.append(item)
    return {
        "schema": ANNOTATION_SCHEMA,
        "tool_version": TOOL_VERSION,
        "categories": sorted(CATEGORIES),
        "behavior_tags": sorted(BEHAVIOR_TAGS),
        "progress": {"committed": len(saved), "total": len(rows)},
        "samples": samples,
    }


HTML = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>AppHear P1 Temporal Review</title><style>body{font:15px system-ui;background:#111827;color:#e5e7eb;margin:0}main{max-width:1100px;margin:auto;padding:18px}.panel{background:#1f2937;border:1px solid #374151;border-radius:10px;padding:14px;margin-bottom:12px}video{width:100%;max-height:55vh;background:#000}.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0}button{padding:8px 12px;border:0;border-radius:6px;background:#2563eb;color:white}.secondary{background:#4b5563}.commit{background:#059669}input,select,textarea{background:#111827;color:white;border:1px solid #4b5563;border-radius:5px;padding:6px}textarea{width:98%}.bad{color:#fca5a5}.good{color:#86efac}.hint{color:#cbd5e1;font-size:13px}table{width:100%;border-collapse:collapse}th,td{border-bottom:1px solid #374151;padding:5px;text-align:left}.tags label{display:inline-block;margin-right:10px}</style></head><body><main><div class="panel"><b>S2-R2 P1 temporal review</b><div id="progress"></div><div class="hint">Watch the complete clip. Add only defensible bounded intervals. Unmarked time is excluded. Genuine sign preparation, possible lexical signing, and ambiguity must not be labeled non-sign.</div></div><div class="panel"><div id="identity"></div><video id="video" controls preload="metadata"></video><div class="row"><button class="secondary" onclick="step(-1)">◀ frame</button><button class="secondary" onclick="step(1)">frame ▶</button><span id="clock"></span><button onclick="mark('start')">Mark START</button><input id="start" readonly size="8"><button onclick="mark('end')">Mark END</button><input id="end" readonly size="8"></div><div class="row"><select id="category"><option>CONFIRMED_NON_SIGN</option><option>AMBIGUOUS_EXCLUDE</option><option>POSSIBLE_LEXICAL_OR_SIGN_PREPARATION</option></select><input id="intervalNote" placeholder="interval note" size="38"><button onclick="addInterval()">Add interval</button></div><div class="tags" id="tags"></div><table><thead><tr><th>ms</th><th>category</th><th>tags</th><th></th></tr></thead><tbody id="intervals"></tbody></table></div><div class="panel"><label><input id="full" type="checkbox"> I watched the complete video</label><br><textarea id="reviewerNote" placeholder="optional clip note"></textarea><div id="message"></div><div class="row"><button class="secondary" onclick="move(-1)">Previous</button><button class="commit" id="commit" onclick="commit()">Commit immutable clip review</button><button class="secondary" onclick="move(1)">Next</button></div></div></main><script>let state,index=0,draft=[];const video=document.getElementById('video');async function boot(){state=await(await fetch('/api/state')).json();const first=state.samples.findIndex(x=>!x.committed);index=first<0?0:first;document.getElementById('tags').innerHTML=state.behavior_tags.map(x=>`<label><input type="checkbox" name="tag" value="${x}">${x}</label>`).join('');render()}function render(){const s=state.samples[index];draft=[];document.getElementById('progress').textContent=`${state.progress.committed}/${state.progress.total} committed · clip ${index+1}/${state.samples.length}`;document.getElementById('identity').textContent=`${s.clip_id} · ${s.participant_id} · ${s.device_id} · ${s.environment_id} · ${(s.duration_ms/1000).toFixed(1)} s`;video.src=s.video_url;for(const id of ['start','end','intervalNote','reviewerNote'])document.getElementById(id).value='';document.getElementById('full').checked=false;document.getElementById('message').textContent='';document.querySelectorAll('input[name=tag]').forEach(x=>x.checked=false);document.getElementById('commit').disabled=s.committed;if(s.committed){draft=s.annotation.intervals;document.getElementById('full').checked=true;document.getElementById('reviewerNote').value=s.annotation.reviewer_note}draw()}video.ontimeupdate=()=>document.getElementById('clock').textContent=`${video.currentTime.toFixed(3)} s`;function mark(id){if(!state.samples[index].committed)document.getElementById(id).value=Math.round(video.currentTime*1000)}function step(d){video.pause();video.currentTime=Math.max(0,Math.min(video.duration||1e9,video.currentTime+d/state.samples[index].fps))}function addInterval(){const start=Number(document.getElementById('start').value),end=Number(document.getElementById('end').value),category=document.getElementById('category').value,tags=[...document.querySelectorAll('input[name=tag]:checked')].map(x=>x.value);if(!(end>start)){msg('Mark a valid START and END.',true);return}if(category==='CONFIRMED_NON_SIGN'&&!tags.length){msg('Choose at least one behavior tag for confirmed non-sign.',true);return}draft.push({start_ms:start,end_ms:end,category,behavior_tags:tags,note:document.getElementById('intervalNote').value});draft.sort((a,b)=>a.start_ms-b.start_ms);draw();msg('Interval added to draft.',false)}function draw(){document.getElementById('intervals').innerHTML=draft.map((x,i)=>`<tr><td>${x.start_ms}–${x.end_ms}</td><td>${x.category}</td><td>${x.behavior_tags.join(', ')}</td><td>${state.samples[index].committed?'':`<button class="secondary" onclick="removeInterval(${i})">remove</button>`}</td></tr>`).join('')}function removeInterval(i){draft.splice(i,1);draw()}function move(d){index=Math.max(0,Math.min(state.samples.length-1,index+d));render()}function msg(t,b){const e=document.getElementById('message');e.textContent=t;e.className=b?'bad':'good'}async function commit(){if(!document.getElementById('full').checked){msg('Confirm that the complete video was watched.',true);return}if(!draft.length){msg('Add at least one explicit interval. Use AMBIGUOUS_EXCLUDE if nothing is safely reusable.',true);return}if(!confirm('Commit this clip review? It is immutable after commit.'))return;const response=await fetch(`/api/annotations/${index}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({full_video_reviewed:true,intervals:draft,reviewer_note:document.getElementById('reviewerNote').value})});const result=await response.json();if(!response.ok){msg(result.error||'Save failed',true);return}state=await(await fetch('/api/state')).json();render();msg('Committed.',false)}boot();</script></body></html>"""


class ReviewApplication:
    def __init__(self, output_root: Path) -> None:
        prepared = prepare(output_root)
        self.rows = prepared["rows"]
        self.annotation_path = prepared["annotation_path"]
        self.manifest_hash = prepared["manifest_sha256"]
        self.lock = threading.Lock()

    def state(self) -> dict[str, Any]:
        document = load_annotations(self.annotation_path, self.manifest_hash)
        return public_state(self.rows, document)

    def commit(self, index: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return commit_annotation(
                rows=self.rows,
                annotation_path=self.annotation_path,
                manifest_hash=self.manifest_hash,
                index=index,
                payload=payload,
            )


def make_handler(application: ReviewApplication) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "AppHearS2R2P1Review/1"

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
            if parsed.path.startswith("/video/"):
                try:
                    index = int(parsed.path.rsplit("/", 1)[1])
                    path = Path(str(application.rows[index]["video_path"]))
                except (ValueError, IndexError):
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self._video(path)
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
                    end = min(int(right) if right else size - 1, size - 1)
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
                if length <= 0 or length > 500_000:
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
    print(f"P1 temporal review: {url}")
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
    parser.add_argument("command", choices=("prepare-p1", "serve-p1", "finalize-p1"))
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare-p1":
        prepared = prepare(args.output_root)
        print(
            json.dumps(
                {
                    "clips": len(prepared["rows"]),
                    "manifest": str(prepared["manifest_path"]),
                    "manifest_sha256": prepared["manifest_sha256"],
                    "annotations": str(prepared["annotation_path"]),
                },
                indent=2,
            )
        )
        return 0
    if args.command == "serve-p1":
        return serve(args.output_root, args.host, args.port, not args.no_browser)
    print(json.dumps(finalize(args.output_root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
