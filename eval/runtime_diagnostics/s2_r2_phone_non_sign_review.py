"""Blind visual review of bounded non-sign intervals in one phone validation stream."""

# ruff: noqa: E501 -- embedded single-page reviewer is deliberately self-contained.

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics.s2_r2_independent_phone_validation import (  # noqa: E402
    OUT,
    _attempts,
    read_json,
)


def review_path(session: Path) -> Path:
    return OUT / session.name / "blinded_human_review" / "non_sign_visual_review.json"


def prepare(session: Path) -> dict:
    attempts = _attempts(session)
    originals = session / "continuous_visual/originals"
    count = len(list(originals.glob("frame_*_original.jpg")))
    expected = [originals / f"frame_{index + 1:06d}_original.jpg" for index in range(count)]
    if count == 0 or not all(path.is_file() for path in expected):
        raise ValueError("S2_R2_NON_SIGN_ORIGINAL_SEQUENCE_INCOMPLETE")
    if int(read_json(session / "continuous_visual/evidence_summary.json")["verified_original_files"]) != count:
        raise ValueError("S2_R2_NON_SIGN_VISUAL_COUNT_MISMATCH")
    path = review_path(session)
    path.parent.mkdir(parents=True, exist_ok=True)
    initial = {
        "schema": "apphear.s2_r2.independent_phone_non_sign_visual_review.v1",
        "session_id": session.name,
        "visual_observation_count": count,
        "reviewer_blinded_to_s2_output": True,
        "confirmed_non_sign_intervals": [],
        "full_session_visual_reviewed": False,
    }
    if path.exists():
        document = read_json(path)
        if any(document.get(key) != value for key, value in initial.items() if key not in {"confirmed_non_sign_intervals", "full_session_visual_reviewed"}):
            raise ValueError("S2_R2_NON_SIGN_REVIEW_IDENTITY_DRIFT")
    else:
        path.write_text(json.dumps(initial, indent=2) + "\n", encoding="utf-8")
        document = initial
    return {"path": path, "document": document, "attempts": attempts, "originals": originals}


def _save(path: Path, document: dict) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def add_interval(prepared: dict, start: int, end: int, note: str) -> dict:
    document = prepared["document"]
    if document["full_session_visual_reviewed"]:
        raise ValueError("S2_R2_NON_SIGN_REVIEW_ALREADY_COMPLETED")
    if not 0 <= start <= end < document["visual_observation_count"]:
        raise ValueError("S2_R2_NON_SIGN_INTERVAL_OUT_OF_RANGE")
    if not note.strip():
        raise ValueError("S2_R2_NON_SIGN_BEHAVIOR_NOTE_REQUIRED")
    for attempt in prepared["attempts"]:
        if start <= attempt["end_index"] and end >= attempt["start_index"]:
            raise ValueError("S2_R2_NON_SIGN_INTERVAL_OVERLAPS_SIGN_ATTEMPT")
    for interval in document["confirmed_non_sign_intervals"]:
        if start <= interval["end_index"] and end >= interval["start_index"]:
            raise ValueError("S2_R2_NON_SIGN_INTERVAL_OVERLAP")
    interval = {"start_index": start, "end_index": end, "behavior_note": note.strip()}
    document["confirmed_non_sign_intervals"].append(interval)
    document["confirmed_non_sign_intervals"].sort(key=lambda item: item["start_index"])
    _save(prepared["path"], document)
    return interval


def finalize(session: Path) -> Path:
    prepared = prepare(session)
    document = prepared["document"]
    if not document["full_session_visual_reviewed"]:
        raise ValueError("S2_R2_NON_SIGN_FULL_VISUAL_REVIEW_REQUIRED")
    positive = review_path(session).parent / "validation_human_review.json"
    labels = read_json(positive)
    if labels.get("session_id") != session.name or len(labels.get("attempts", [])) != 6:
        raise ValueError("S2_R2_TEMPORAL_REVIEW_REQUIRED_FIRST")
    if labels.get("non_sign_review_pending") is False:
        raise ValueError("S2_R2_NON_SIGN_REVIEW_ALREADY_LINKED")
    labels["confirmed_non_sign_intervals"] = document["confirmed_non_sign_intervals"]
    labels["non_sign_review_pending"] = False
    labels["non_sign_review_source"] = str(prepared["path"])
    _save(positive, labels)
    return positive


HTML = r"""<!doctype html><html><head><meta charset="utf-8"><title>AppHear blind non-sign review</title><style>body{font:15px system-ui;background:#111827;color:#eee;margin:0}main{max-width:970px;margin:auto;padding:14px}.box{background:#1f2937;padding:14px;margin:8px;border-radius:8px}img{display:block;max-width:100%;max-height:63vh;margin:auto}button,input{padding:7px;margin:4px}input[type=range]{width:95%}.warn{color:#fca5a5}</style></head><body><main><div class="box"><b>Blind full-session non-sign review</b><p>Scrub all frames. Do not view S2 outputs. Mark only bounded intervals with clearly ordinary/non-lexical behavior outside sign attempts. Exclude sign preparation and uncertain motion. Empty intervals are allowed, but cannot support a non-sign suppression claim.</p><p id="attempts"></p></div><div class="box"><img id="image"><input id="slider" type="range" min="0" value="0"><div><button onclick="step(-1)">◀ frame</button><button onclick="step(1)">frame ▶</button><span id="position"></span></div><div><button onclick="mark('start')">Mark START</button><span id="start"></span><button onclick="mark('end')">Mark END</button><span id="end"></span></div><input id="note" placeholder="Observed behavior (required)" size="55"><button onclick="save()">Add confirmed non-sign interval</button><p id="message" class="warn"></p></div><div class="box"><b>Saved bounded intervals</b><pre id="intervals"></pre><label><input id="full" type="checkbox">I inspected the complete visual session, including inter-attempt periods</label><button onclick="complete()">Complete visual review</button></div></main><script>let state,frame=0,start=null,end=null;async function boot(){state=await(await fetch('/api/state')).json();document.getElementById('slider').max=state.visual_observation_count-1;document.getElementById('attempts').textContent='Sign attempts (do not mark non-sign inside): '+state.attempts.map(x=>`${x.gloss} ${x.start_index}-${x.end_index}`).join(' · ');render()}function render(){document.getElementById('slider').value=frame;document.getElementById('image').src='/image/'+frame;document.getElementById('position').textContent=`observation index ${frame} / ${state.visual_observation_count-1}`;document.getElementById('intervals').textContent=JSON.stringify(state.confirmed_non_sign_intervals,null,2);document.getElementById('full').checked=state.full_session_visual_reviewed}function step(d){frame=Math.max(0,Math.min(state.visual_observation_count-1,frame+d));render()}document.getElementById('slider').oninput=e=>{frame=Number(e.target.value);render()};function mark(which){if(state.full_session_visual_reviewed)return;if(which==='start')start=frame;else end=frame;document.getElementById(which).textContent=frame}async function post(path,payload){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const v=await r.json();if(!r.ok)throw Error(v.error);return v}async function save(){try{if(start===null||end===null)throw Error('Mark START and END first');state=await post('/api/intervals',{start_index:start,end_index:end,behavior_note:document.getElementById('note').value});start=end=null;document.getElementById('start').textContent=document.getElementById('end').textContent='';document.getElementById('note').value='';render();document.getElementById('message').textContent='Interval saved'}catch(e){document.getElementById('message').textContent=e.message}}async function complete(){try{if(!document.getElementById('full').checked)throw Error('Confirm complete visual review first');if(!confirm('Complete this blind non-sign review? No further intervals can be added.'))return;state=await post('/api/complete',{full_session_visual_reviewed:true});render();document.getElementById('message').textContent='Visual review complete; tell Codex.'}catch(e){document.getElementById('message').textContent=e.message}}window.onkeydown=e=>{if(e.key==='ArrowLeft')step(-1);if(e.key==='ArrowRight')step(1)};boot()</script></body></html>"""


def serve(session: Path, port: int) -> None:
    prepared = prepare(session)

    class Handler(BaseHTTPRequestHandler):
        def respond(self, body: bytes, mime: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/":
                return self.respond(HTML.encode(), "text/html; charset=utf-8")
            if path == "/api/state":
                value = {**prepared["document"], "attempts": prepared["attempts"]}
                return self.respond(json.dumps(value).encode(), "application/json")
            if path.startswith("/image/"):
                try:
                    index = int(path.rsplit("/", 1)[1])
                    if not 0 <= index < prepared["document"]["visual_observation_count"]:
                        raise ValueError("IMAGE_INDEX_OUT_OF_RANGE")
                    image = prepared["originals"] / f"frame_{index + 1:06d}_original.jpg"
                    return self.respond(image.read_bytes(), "image/jpeg")
                except ValueError:
                    return self.send_error(HTTPStatus.NOT_FOUND)
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size < 10_000:
                    raise ValueError("INVALID_REQUEST_SIZE")
                payload = json.loads(self.rfile.read(size))
                if self.path == "/api/intervals":
                    add_interval(
                        prepared,
                        int(payload["start_index"]),
                        int(payload["end_index"]),
                        str(payload["behavior_note"]),
                    )
                elif self.path == "/api/complete":
                    if payload != {"full_session_visual_reviewed": True}:
                        raise ValueError("EXPLICIT_FULL_REVIEW_CONFIRMATION_REQUIRED")
                    prepared["document"]["full_session_visual_reviewed"] = True
                    _save(prepared["path"], prepared["document"])
                else:
                    raise ValueError("UNKNOWN_ENDPOINT")
                self.respond(json.dumps(prepared["document"]).encode(), "application/json")
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                self.respond(json.dumps({"error": str(error)}).encode(), "application/json", 400)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(url, flush=True)
    webbrowser.open(url)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "serve", "finalize"))
    parser.add_argument("session", type=Path)
    parser.add_argument("--port", type=int, default=8772)
    args = parser.parse_args()
    if args.command == "prepare":
        print(prepare(args.session)["path"])
    elif args.command == "serve":
        serve(args.session, args.port)
    else:
        print(finalize(args.session))


if __name__ == "__main__":
    main()
