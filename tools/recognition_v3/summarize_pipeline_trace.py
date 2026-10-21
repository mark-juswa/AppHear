"""Summarize one live AppHearV3 trace for the pipelined-pose throughput comparison.

Builds on summarize_trace.py (same integrity checks) and adds what the pipeline question needs:
the observation-interval distribution in camera frames, capture-to-completion latency, the time
the hand stage waited for DWPose, and per-thread CPU from /proc snapshots when given.
Camera drops stay NOT_MEASURED; gaps are reported as gaps.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from summarize_trace import parse_trace, partition_bindings, summarize  # noqa: E402


def percentiles(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    pick = lambda p: float(ordered[int((len(ordered) - 1) * p)])  # noqa: E731
    return {"p05": pick(0.05), "p50": pick(0.5), "p95": pick(0.95), "max": float(ordered[-1]),
            "mean": float(sum(ordered) / len(ordered))}


def camera_frame_ms(gaps: list[float]) -> float:
    """The smallest common gap is one or two camera frames; estimate the frame from the gaps."""
    one_frame = [g for g in gaps if g < 90.0]
    if one_frame:
        return sum(one_frame) / len(one_frame)
    two = [g / 2 for g in gaps if 110.0 < g < 160.0]
    return sum(two) / len(two) if two else 66.654


def summarize_pipeline(rows: list[dict], frame_ms: float | None) -> dict:
    base = summarize(rows)
    gaps = [(b["capture_timestamp_ns"] - a["capture_timestamp_ns"]) / 1e6 for a, b in zip(rows, rows[1:])]
    frame = frame_ms or camera_frame_ms(gaps)
    frames = Counter(round(g / frame) for g in gaps)
    latency = [(r["completed_timestamp_ns"] - r["capture_timestamp_ns"]) / 1e6 for r in rows]
    result = {
        "schema_version": "apphear.v3.pipeline_trace_summary.v1",
        "pipelined_pose": bool(rows[0].get("v3_pipelined_pose", False)),
        "emit_on_hands": bool(rows[0].get("v3_emit_on_hands", False)),
        "budget": {k: rows[0].get(k) for k in ("pose_threads", "pose_spinning", "hand_threads")},
        "observations": len(rows),
        "observations_per_second_capture_span": base["capture_span_observation_fps"],
        "observations_per_second_completion_span": base["delivered_observation_fps"],
        "interval_ms": percentiles(gaps),
        "camera_frame_ms": frame,
        "interval_camera_frames": {str(k): v / len(gaps) for k, v in sorted(frames.items())},
        "capture_to_completed_ms": percentiles(latency),
        "capture_clock_note": "capture and completion clocks may differ by a constant offset; "
        "compare arms within one boot, never absolute values across devices",
        "timing": {k: base[k] for k in ("preprocess_ms", "pose_inference_and_output_ms",
                                         "hands_wall_ms", "analyzer_ms")},
        "heap": {k: base[k] for k in ("java_heap_bytes", "native_heap_bytes")},
        "frame_drops": base["frame_drops"],
        "accuracy_claim": "NONE",
    }
    if result["pipelined_pose"]:
        result["pose_wait_ms"] = percentiles([r["pose_wait_ms"] for r in rows])
    if result["emit_on_hands"]:
        # Hands finished -> the camera thread picked the frame up (queue + posted-runnable delay).
        result["delivery_wait_ms"] = percentiles([r["delivery_wait_ms"] for r in rows])
        # Frames the analyzer released unprocessed because DWPose was busy (not camera drops).
        released = rows[-1]["busy_drops_total"] - rows[0]["busy_drops_total"]
        result["released_while_busy"] = {"frames": released,
                                         "per_observation": released / max(1, len(rows) - 1)}
    return result


def cpu_from_proc(before: Path, after: Path, wall_s: float, ticks: int = 100) -> dict:
    """Each file: raw /proc/<pid>/task/*/stat lines (`tid (comm) state ... utime stime ...`)."""
    def read(path: Path) -> dict[str, tuple[str, int]]:
        out = {}
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            open_at, close_at = line.find("("), line.rfind(")")
            if open_at < 0 or close_at < open_at:
                continue
            rest = line[close_at + 1:].split()
            out[line[:open_at].strip()] = (line[open_at + 1:close_at], int(rest[11]) + int(rest[12]))
        return out

    start, end = read(before), read(after)
    per_thread: Counter[str] = Counter()
    for tid, (name, used) in end.items():
        per_thread[name] += used - start.get(tid, (name, 0))[1]
    total = sum(per_thread.values())
    return {
        "process_cpu_percent_of_one_core": 100.0 * total / ticks / wall_s,
        "top_threads_percent_of_one_core": {
            name: 100.0 * used / ticks / wall_s for name, used in per_thread.most_common(8)
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--skip-warmup", type=int, default=20)
    parser.add_argument("--segment", type=int)
    parser.add_argument("--longest-segment", action="store_true",
                        help="use the longest contiguous binding (a live run may start with a short one)")
    parser.add_argument("--camera-frame-ms", type=float)
    parser.add_argument("--proc-before", type=Path)
    parser.add_argument("--proc-after", type=Path)
    parser.add_argument("--wall-seconds", type=float)
    args = parser.parse_args()
    groups = partition_bindings(parse_trace(args.trace.read_text(encoding="utf-8-sig").splitlines()))
    if args.longest_segment:
        args.segment = max(range(len(groups)), key=lambda i: len(groups[i]))
    if args.segment is None and len(groups) != 1:
        raise ValueError(f"{len(groups)} segments: pass --segment")
    rows = groups[args.segment or 0]
    summarize(rows)  # whole binding first: trimming must not hide a reset or lost rows
    result = summarize_pipeline(rows[args.skip_warmup:], args.camera_frame_ms)
    result["warmup_rows_excluded"] = args.skip_warmup
    result["segment"] = {"selected": args.segment or 0, "of": len(groups),
                         "rows_per_segment": [len(g) for g in groups]}
    if args.proc_before and args.proc_after and args.wall_seconds:
        result["cpu"] = cpu_from_proc(args.proc_before, args.proc_after, args.wall_seconds)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
