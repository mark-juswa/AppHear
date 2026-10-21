"""Replay measured per-frame stage timings through the three Candidate01 schedules (host model).

Pre-device diagnostic for the emit-on-hands candidate. CameraX delivers a frame every
--frame-ms; with STRATEGY_KEEP_ONLY_LATEST the analyzer always receives the newest frame that is
available when it becomes free (or the next one to arrive). Each frame i uses the measured
preprocess / DWPose / hands times of trace row i, so a trace recorded under a given amount of
CPU contention replays that contention. The camera-to-analyzer delay is estimated from the
serial trace (min of analysis start - capture).

Schedules:
  serial     preprocess -> pose -> hands -> deliver, all on the camera thread
  pipelined  pose(t) on a worker overlapping hands(t-1) on the camera thread; frame t emitted
             when frame t+1 arrives (the first schedule, 06e40b2f)
  emit       pose(t) on a pose worker, hands(t) on a hand worker, delivery posted back to the
             camera thread as soon as hands(t) end; analyze waits for pose(t-1) and for the
             hand stage of the frame that last used its slot (t-2) (this candidate)

The model is first checked against the live runs it was fitted on (serial A/C, pipelined B);
it is a model, not a measurement, and makes no accuracy claim.
Usage: python simulate_schedules.py --serial A.log [C.log] --pipelined B.log [--out x.json]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "tools/recognition_v3"))
from summarize_trace import parse_trace, partition_bindings  # noqa: E402

FRAME_MS = 66.654


def rows_of(path: Path, skip: int = 40) -> list[dict]:
    groups = partition_bindings(parse_trace(path.read_text(encoding="utf-8-sig").splitlines()))
    return max(groups, key=len)[skip:]


def stages(rows: list[dict]) -> list[tuple[float, float, float]]:
    """(preprocess, pose incl. decode, hands wall) per frame, ms."""
    return [(r["preprocess_ms"], r["pose_inference_and_output_ms"] + r["pose_decode_ms"],
             r["hands_wall_ms"]) for r in rows]


def camera_delay_ms(serial_rows: list[dict]) -> float:
    starts = [(r["completed_timestamp_ns"] - r["analyzer_ms"] * 1e6 - r["capture_timestamp_ns"]) / 1e6
              for r in serial_rows]
    return float(sorted(starts)[len(starts) // 50])  # 2nd percentile: robust minimum


def deliver_ms(serial_rows: list[dict]) -> float:
    return statistics.median(r["analyzer_ms"] - r["perception_ms"] for r in serial_rows)


class Camera:
    """
    Frame k is captured at k*F and available to the analyzer delay ms later. CameraX
    KEEP_ONLY_LATEST (ImageAnalysisNonBlockingAnalyzer) picks the next frame when the current
    one is CLOSED: the newest cached frame is dispatched at once, or else the next arrival. The
    dispatched frame then waits in the executor queue until analyze returns.
    """

    def __init__(self, delay: float):
        self.delay = delay
        self.last = -1

    def take(self, closed_at: float, free_at: float | None = None) -> tuple[int, float]:
        newest = int((closed_at - self.delay) // FRAME_MS)
        k = max(newest, self.last + 1)
        self.last = k
        return k, max(closed_at if free_at is None else free_at, k * FRAME_MS + self.delay)


def summarize(events: list[tuple[int, float]], name: str) -> dict:
    """events: (frame index, delivery time) in emission order."""
    events = events[20:]
    gaps = [b[0] - a[0] for a, b in zip(events, events[1:])]
    latency = sorted(t - k * FRAME_MS for k, t in events)
    span_s = (events[-1][0] - events[0][0]) * FRAME_MS / 1000.0
    mix: dict[str, float] = {}
    for g in gaps:
        mix[str(g)] = mix.get(str(g), 0) + 1 / len(gaps)
    pick = lambda p: latency[int((len(latency) - 1) * p)]  # noqa: E731
    return {"schedule": name, "observations_per_second": (len(events) - 1) / span_s,
            "mean_gap_frames": sum(gaps) / len(gaps),
            "gap_mix": dict(sorted(mix.items(), key=lambda kv: int(kv[0]))),
            "latency_p50_ms": pick(0.5), "latency_p95_ms": pick(0.95)}


def serial(timing, delay, deliver):
    cam, free, out = Camera(delay), 0.0, []
    for pre, pose, hands in timing:
        k, start = cam.take(free)
        free = start + pre + pose + hands + deliver
        out.append((k, free))
    return out


def pipelined(timing, delay, deliver):
    cam, free, closed, pose_free, out, prev = Camera(delay), 0.0, 0.0, 0.0, [], None
    for pre, pose, hands in timing:
        k, start = cam.take(closed, free)
        submit = start + pre
        pose_end = max(submit, pose_free) + pose
        pose_free = pose_end
        free = closed = submit
        if prev is not None:
            prev_k, prev_pose_end, prev_hands = prev
            free = max(submit, prev_pose_end) + prev_hands + deliver
            out.append((prev_k, free))
        prev = (k, pose_end, hands)
    return out


def emit(timing, delay, deliver, drop_when_busy: bool = False):
    """drop_when_busy: close a frame at once (no work) while DWPose or its slot is still busy."""
    cam, free, out = Camera(delay), 0.0, []
    pose_free = hand_free = 0.0
    hand_end_by_slot = [0.0, 0.0]
    camera_busy_until = 0.0  # deliveries serialize on the camera thread
    i = 0
    timing = list(timing)
    while i < len(timing):
        pre, pose, hands = timing[i]
        k, start = cam.take(free)
        if drop_when_busy and max(pose_free, hand_end_by_slot[i % 2]) > start:
            free = start + 0.5  # close and return; CameraX dispatches the next arrival
            continue
        i += 1
        ready = max(start, pose_free, hand_end_by_slot[(i - 1) % 2])
        submit = ready + pre
        pose_end = submit + pose
        pose_free = pose_end
        hand_end = max(pose_end, hand_free) + hands
        hand_free = hand_end
        hand_end_by_slot[(i - 1) % 2] = hand_end
        delivered = max(hand_end, camera_busy_until) + deliver
        camera_busy_until = delivered
        out.append((k, delivered))
        free = submit
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", type=Path, nargs="+", required=True)
    parser.add_argument("--pipelined", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    serial_rows = [rows_of(p) for p in args.serial]
    pipe_rows = rows_of(args.pipelined)
    delay = statistics.median(camera_delay_ms(r) for r in serial_rows)
    deliver = statistics.median(deliver_ms(r) for r in serial_rows)
    result = {"schema": "apphear.v3_schedule_model.v1", "accuracy_claim": "NONE",
              "frame_ms": FRAME_MS, "camera_delay_ms": delay, "deliver_ms": deliver,
              "calibration": {}, "prediction": {}}
    for path, rows in zip(args.serial, serial_rows):
        result["calibration"][f"serial_replay_{path.stem}"] = summarize(serial(stages(rows), delay, deliver), "serial")
    result["calibration"]["pipelined_replay_B"] = summarize(pipelined(stages(pipe_rows), delay, deliver), "pipelined")
    # Contended: stage times as overlapped in the first pipeline (pose 2 thr spin, hands 2 thr).
    result["prediction"]["emit_with_pipelined_B_contention"] = summarize(
        emit(stages(pipe_rows), delay, deliver), "emit")
    result["prediction"]["emit_drop_with_pipelined_B_contention"] = summarize(
        emit(stages(pipe_rows), delay, deliver, drop_when_busy=True), "emit_drop")
    # Optimistic bound: overlapped stages as fast as when run alone (no contention at all).
    for path, rows in zip(args.serial, serial_rows):
        result["prediction"][f"emit_without_contention_{path.stem}"] = summarize(
            emit(stages(rows), delay, deliver), "emit")
        result["prediction"][f"emit_drop_without_contention_{path.stem}"] = summarize(
            emit(stages(rows), delay, deliver, drop_when_busy=True), "emit_drop")
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
