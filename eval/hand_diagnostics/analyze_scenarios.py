"""Analysis of controlled hand-diagnostic captures (standard library only). Reads the logs written by capture_scenario.sh.

Inputs per scenario: <dir>/<name>.log containing the tags AppHearDetect (30 s summaries) and AppHearV3 (per-frame JSON, capped at 240
frames per analyzer start). Nothing here changes the app; it only summarises what the app logged.

What the per-frame JSON can and cannot say (stated so the report does not over-claim):
  * has: hands_observed, hand_presence[L,R], hand_handedness[L,R], hand_roi_iou (DWPose ROIs, BEFORE the refiner),
         hand_skeleton_iou (refined skeletons, only when both slots observed), stage timings, frame age.
  * does NOT have: per-frame DWPose group support (only a mean over 'same' frames in the 30 s summary), landmark coordinates.
  * which slot was observed on a one-hand frame is inferred from presence >= 0.5 (observed also needs >= 18 valid joints).
Usage: python -m eval.hand_diagnostics.analyze_scenarios <dir> <name> [<name> ...] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

from eval.recognition_experiments.error_analysis import spearman

STAGE_RE = re.compile(r"\b([a-z_0-9]+)=(\d+(?:\.\d+)?|na)/(\d+(?:\.\d+)?|na)\b")
HANDS_RE = re.compile(r"hands\[([^\]]*)\]")
RENDER_RE = re.compile(r"render\[([^\]]*)\]")
SCALARS = ("in", "ok", "camDropEst", "faults", "fpsIn", "fpsOk")


def _num(x: str):
    return None if x == "na" else float(x)


def parse_detect_line(line: str) -> dict | None:
    """One 30 s summary. Returns None if the line is not a summary."""
    if "AppHearDetect" not in line or " in=" not in line:
        return None
    out: dict = {"stages": {}, "hands": {}, "render": {}}
    for key in SCALARS:
        m = re.search(rf"\b{re.escape(key)}=(\d+(?:\.\d+)?|na)\b", line)
        if m:
            out[key] = _num(m.group(1))
    m = re.search(r"busy=(\d+(?:\.\d+)?)%", line)
    if m:
        out["busy_pct"] = float(m.group(1))
    for k, a, b in STAGE_RE.findall(line.split("hands[")[0]):
        if k not in ("recov", "fatal"):
            out["stages"][k] = {"p50": _num(a), "p95": _num(b)}
    h = HANDS_RE.search(line)
    if h:
        for tok in h.group(1).split():
            k, _, v = tok.partition("=")
            out["hands"][k] = v
    r = RENDER_RE.search(line)
    if r:
        for tok in r.group(1).split():
            k, _, v = tok.partition("=")
            out["render"][k] = int(v)
    return out


def parse_v3(lines) -> list[dict]:
    frames = []
    for ln in lines:
        if "AppHearV3" not in ln:
            continue
        i = ln.find("{")
        if i < 0:
            continue
        try:
            d = json.loads(ln[i:])
        except json.JSONDecodeError:
            continue
        if d.get("schema_version") == "apphear.perception_v3_timing.v1":
            frames.append(d)
    return frames


def pct(vals, q):
    v = sorted(vals)
    return v[min(len(v) - 1, max(0, -(-int(q * len(v) * 1000) // 1000) - 1))] if v else None


def dist(vals):
    vals = [x for x in vals if x is not None]
    if not vals:
        return None
    return {"n": len(vals), "mean": round(statistics.fmean(vals), 3), "p50": round(statistics.median(vals), 3),
            "p95": round(pct(vals, 0.95), 3), "min": round(min(vals), 3), "max": round(max(vals), 3)}


def _mean(xs):
    xs = [x for x in xs if x is not None and x >= 0]
    return round(statistics.fmean(xs), 3) if xs else None


def analyse_frames(frames: list[dict], warmup: int = 3) -> dict:
    use = [f for f in frames if f["source_index"] >= warmup]
    obs = {0: 0, 1: 0, 2: 0}
    for f in use:
        obs[min(2, f["hands_observed"])] += 1
    two = [f for f in use if f["hands_observed"] == 2]
    one = [f for f in use if f["hands_observed"] == 1]
    skel = [f["hand_skeleton_iou"] for f in two if f["hand_skeleton_iou"] >= 0]
    roi = [f["hand_roi_iou"] for f in two if f["hand_roi_iou"] >= 0]
    paired = [(f["hand_roi_iou"], f["hand_skeleton_iou"]) for f in two if f["hand_roi_iou"] >= 0 and f["hand_skeleton_iou"] >= 0]

    def bins(v):
        return {"lt0.1": sum(1 for x in v if x < 0.1), "0.1to0.5": sum(1 for x in v if 0.1 <= x < 0.5), "ge0.5": sum(1 for x in v if x >= 0.5)}

    cross = {"roi>=0.5&skel>=0.5": 0, "roi<0.5&skel>=0.5": 0, "roi>=0.5&skel<0.5": 0, "roi<0.5&skel<0.5": 0}
    for r, s in paired:
        cross[f"roi{'>=' if r >= 0.5 else '<'}0.5&skel{'>=' if s >= 0.5 else '<'}0.5"] += 1
    slot = {"L": 0, "R": 0, "ambiguous": 0}
    hand_of_one = {"L": [], "R": []}
    for f in one:
        p, h = f["hand_presence"], f["hand_handedness"]
        s = [i for i in (0, 1) if p[i] >= 0.5]
        if len(s) == 1:
            k = "LR"[s[0]]
            slot[k] += 1
            hand_of_one[k].append(h[s[0]])
        else:
            slot["ambiguous"] += 1
    # Camera capture interval of the frames the analyzer actually received (gaps = frames dropped by latest-frame-wins), and
    # capture -> analyzer-completed (before the UI hop). Consecutive source_index only; clocks are the app's own.
    gaps, to_done = [], []
    for a, b in zip(use, use[1:]):
        ca, cb = a.get("capture_timestamp_ns"), b.get("capture_timestamp_ns")
        if ca is not None and cb is not None and b["source_index"] == a["source_index"] + 1 and cb > ca:
            gaps.append((cb - ca) / 1e6)
    for f in use:
        c, d_ = f.get("capture_timestamp_ns"), f.get("completed_timestamp_ns")
        if c is not None and d_ is not None and 0 <= (d_ - c) / 1e6 <= 10_000:
            to_done.append((d_ - c) / 1e6)
    stage_keys = ["frame_age_ms", "preprocess_ms", "pose_inference_and_output_ms", "pose_decode_ms", "hand_crop_ms",
                  "hand_inference_ms", "hands_wall_ms", "perception_ms", "analyzer_ms"]
    lat = {k: dist([f[k] for f in use]) for k in stage_keys}
    lat["capture_interval_ms(delivered frames)"] = dist(gaps)
    lat["capture_to_completed_ms"] = dist(to_done)
    lat["session_ms(analyzer-perception)"] = dist([f["analyzer_ms"] - f["perception_ms"] for f in use])
    med = {k: (v["p50"] if v else None) for k, v in lat.items()}
    return {
        "frames_total": len(frames), "frames_used_after_warmup": len(use), "warmup_frames_skipped": warmup,
        "hands_observed_frames": obs,
        "two_hand_frames": {
            "n": len(two), "skeleton_iou_bins": bins(skel), "roi_iou_bins": bins(roi), "roi_vs_skeleton_crosstab": cross,
            "spearman_roi_iou_vs_skeleton_iou": spearman([p[0] for p in paired], [p[1] for p in paired]) if len(paired) >= 3 else None,
            "mean_presence_L_R": [_mean([f["hand_presence"][0] for f in two]), _mean([f["hand_presence"][1] for f in two])],
            "mean_handedness_L_R": [_mean([f["hand_handedness"][0] for f in two]), _mean([f["hand_handedness"][1] for f in two])],
        },
        "one_hand_frames": {"n": len(one), "observed_slot": slot,
                            "mean_handedness_when_slot_L": _mean(hand_of_one["L"]), "mean_handedness_when_slot_R": _mean(hand_of_one["R"])},
        "latency_ms": lat,
        "median_share_of_analyzer_pct": {k: (round(100 * v / med["analyzer_ms"], 1) if v is not None and med["analyzer_ms"] else None)
                                         for k, v in med.items() if k not in ("frame_age_ms", "analyzer_ms")},
    }


def analyse(dirpath: Path, name: str) -> dict:
    text = (dirpath / f"{name}.log").read_text(errors="replace").splitlines()
    summaries = [d for d in (parse_detect_line(t) for t in text) if d]
    frames = parse_v3(text)
    commits = [t for t in text if "AppHearPhone" in t and " commit " in t]
    return {"scenario": name, "summaries_30s": summaries, "per_frame": analyse_frames(frames),
            "phone_commit_lines": len(commits), "crash_lines": _crash(dirpath, name)}


def _crash(dirpath: Path, name: str) -> int:
    p = dirpath / f"{name}.crash.log"
    return sum(1 for ln in p.read_text(errors="replace").splitlines() if ln.strip() and "beginning of" not in ln) if p.exists() else -1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", type=Path)
    ap.add_argument("names", nargs="+")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    res = [analyse(a.dir, n) for n in a.names]
    print(json.dumps(res, indent=1))
    if a.json:
        a.json.write_text(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
