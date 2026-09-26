"""Parse A1 device traces and apply the frozen Baseline-vs-A1 runtime gates."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

EVENT_RE = re.compile(r"\bevent=([A-Z0-9_]+)\b(.*)$")
CRASH_MARKERS = ("FATAL EXCEPTION", "Fatal signal", "SIGSEGV", "ANR in com.example.apphear")


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = int((len(ordered) - 1) * quantile)
    return ordered[index]


def _stats(values: list[float]) -> dict[str, float | None]:
    return {
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "max": max(values) if values else None,
    }


def _number(value: str) -> int | float | str:
    if value == "null":
        return value
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def parse_events(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        if "AppHearA1" not in line:
            continue
        match = EVENT_RE.search(line)
        if not match:
            continue
        event: dict[str, Any] = {"event": match.group(1), "raw": line}
        for token in match.group(2).strip().split():
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            event[key] = _number(value)
        events.append(event)
    return events


def _rate(event_times: list[int], duration_s: float) -> float:
    return len(event_times) / duration_s if duration_s > 0 else 0.0


def _overlap_ms(hand: list[tuple[int, int]], pose: list[tuple[int, int]]) -> tuple[float, float]:
    total = 0
    hand_overlapped = 0
    for hs, he in hand:
        overlap_for_hand = 0
        for ps, pe in pose:
            overlap_for_hand += max(0, min(he, pe) - max(hs, ps))
        total += overlap_for_hand
        hand_overlapped += min(overlap_for_hand, he - hs)
    hand_duration = sum(end - start for start, end in hand)
    fraction = hand_overlapped / hand_duration if hand_duration else 0.0
    return total / 1_000_000.0, fraction


def _memory_summary(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"peak_pss_kb": None, "thermal_status_max": None}
    pss: list[int] = []
    thermal: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        fields = line.split(",")
        if len(fields) >= 2 and fields[1].isdigit():
            pss.append(int(fields[1]))
        if len(fields) >= 3 and fields[2].lstrip("-").isdigit():
            thermal.append(int(fields[2]))
    return {
        "peak_pss_kb": max(pss) if pss else None,
        "thermal_status_max": max(thermal) if thermal else None,
    }


def summarize(
    log_path: Path,
    memory_path: Path | None,
    warmup_seconds: int,
    expected_seconds: int | None = None,
) -> dict[str, Any]:
    text = log_path.read_text(encoding="utf-8", errors="replace")
    events = parse_events(text)
    camera = [e for e in events if e["event"] == "CAMERA_DELIVERED"]
    if not camera:
        raise ValueError(f"No AppHearA1 CAMERA_DELIVERED events in {log_path}")
    start_ns = int(camera[0]["event_ns"]) + warmup_seconds * 1_000_000_000
    events = [e for e in events if int(e.get("event_ns", 0)) >= start_ns]
    end_ns = max(int(e.get("event_ns", start_ns)) for e in events)
    duration_s = max((end_ns - start_ns) / 1_000_000_000.0, 0.001)

    by_name: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        by_name.setdefault(str(event["event"]), []).append(event)

    publication_times = [int(e["publish_ns"]) for e in by_name.get("HAND_PUBLICATION", [])]
    publication_gaps_ms = [
        (right - left) / 1_000_000.0
        for left, right in zip(publication_times, publication_times[1:], strict=False)
    ]
    hand_latency_ms = [
        float(e["duration_ns"]) / 1_000_000.0 for e in by_name.get("HAND_INFERENCE_END", [])
    ]
    consumer_age_ms = [
        float(e["hand_result_age_ns"]) / 1_000_000.0 for e in by_name.get("CONSUMER_START", [])
    ]
    source_to_s4_ms = [
        float(e["source_to_s4_ns"]) / 1_000_000.0 for e in by_name.get("CONSUMER_START", [])
    ]
    valid_joins = [e for e in by_name.get("SYNCHRONIZER_JOIN", []) if e.get("status") == "VALID"]
    pose_age_ms = [float(e["pose_age_ns"]) / 1_000_000.0 for e in valid_joins]
    future_pose_violations = sum(
        int(e["pose_source_ns"]) > int(e["hand_source_ns"])
        for e in valid_joins
        if e.get("pose_source_ns") not in (None, "null")
    )
    join_reasons = Counter(str(e.get("reason", "OTHER")) for e in by_name.get("JOIN_REJECTION", []))

    hand_intervals = [
        (int(e["start_ns"]), int(e["end_ns"])) for e in by_name.get("HAND_INFERENCE_END", [])
    ]
    pose_intervals = [
        (int(e["start_ns"]), int(e["end_ns"])) for e in by_name.get("POSE_INFERENCE_END", [])
    ]
    overlap_ms, overlap_fraction = _overlap_ms(hand_intervals, pose_intervals)

    source_order = [int(e["source_ns"]) for e in by_name.get("HAND_PUBLICATION", [])]
    ordering_violations = sum(
        right <= left for left, right in zip(source_order, source_order[1:], strict=False)
    )
    midpoint = start_ns + (end_ns - start_ns) // 2
    first_half = [t for t in publication_times if t < midpoint]
    second_half = [t for t in publication_times if t >= midpoint]
    half_duration = duration_s / 2.0
    first_rate = _rate(first_half, half_duration)
    second_rate = _rate(second_half, half_duration)
    thermal_decay = (second_rate / first_rate - 1.0) if first_rate else None

    result: dict[str, Any] = {
        "log": str(log_path),
        "mode": events[0].get("mode", "UNKNOWN") if events else "UNKNOWN",
        "duration_s": duration_s,
        "trace_coverage_fraction": (
            min(1.0, duration_s / expected_seconds) if expected_seconds else None
        ),
        "counts": {name: len(rows) for name, rows in sorted(by_name.items())},
        "rates_per_s": {
            "camera_delivered": _rate(
                [int(e["event_ns"]) for e in by_name.get("CAMERA_DELIVERED", [])], duration_s
            ),
            "analyzer_accepted": _rate(
                [int(e["event_ns"]) for e in by_name.get("ANALYZER_ACCEPT", [])], duration_s
            ),
            "hand_offered": _rate(
                [int(e["event_ns"]) for e in by_name.get("HAND_MAILBOX_ENQUEUE", [])], duration_s
            ),
            "hand_inference_completed": _rate(
                [int(e["event_ns"]) for e in by_name.get("HAND_INFERENCE_END", [])], duration_s
            ),
            "fresh_hand_publications": _rate(publication_times, duration_s),
            "pose_publications": _rate(
                [int(e["event_ns"]) for e in by_name.get("POSE_PUBLICATION", [])], duration_s
            ),
            "valid_joins": _rate([int(e["event_ns"]) for e in valid_joins], duration_s),
            "s4_observations": _rate(
                [int(e["event_ns"]) for e in by_name.get("CONSUMER_END", [])], duration_s
            ),
        },
        "inter_hand_publication_gap_ms": _stats(publication_gaps_ms),
        "hand_inference_latency_ms": _stats(hand_latency_ms),
        "hand_end_to_s4_ms": _stats(consumer_age_ms),
        "analyzer_arrival_to_s4_ms": _stats(source_to_s4_ms),
        "source_to_s4_clock_basis": "ANALYZER_ARRIVAL_MONOTONIC_PROXY",
        "pose_age_ms": _stats(pose_age_ms),
        "synchronizer_yield": len(valid_joins) / len(publication_times)
        if publication_times
        else 0.0,
        "join_rejections": dict(join_reasons),
        "ordering_violations": ordering_violations,
        "future_pose_violations": future_pose_violations,
        "inference_overlap": {
            "total_ms": overlap_ms,
            "hand_interval_fraction": overlap_fraction,
            "api_execution_interpretation": "OVERLAPPING"
            if overlap_fraction >= 0.05
            else "EFFECTIVELY_SERIALIZED",
            "gpu_internal_visibility": "NOT_DIRECTLY_OBSERVABLE",
        },
        "fresh_hand_rate_first_half": first_rate,
        "fresh_hand_rate_second_half": second_rate,
        "thermal_throughput_decay_fraction": thermal_decay,
        "crash_markers": [marker for marker in CRASH_MARKERS if marker in text],
        "no_sign_onsets": text.count("S5 ONSET"),
        "no_sign_commits": len(re.findall(r"\bCOMMIT '\w", text)),
    }
    result.update(_memory_summary(memory_path))
    return result


def _aggregate(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    def mean_path(*path: str) -> float | None:
        values: list[float] = []
        for summary in summaries:
            value: Any = summary
            for key in path:
                value = value.get(key) if isinstance(value, dict) else None
            if isinstance(value, (int, float)):
                values.append(float(value))
        return sum(values) / len(values) if values else None

    return {
        "fresh_hand_rate": mean_path("rates_per_s", "fresh_hand_publications"),
        "s4_rate": mean_path("rates_per_s", "s4_observations"),
        "p95_hand_gap_ms": mean_path("inter_hand_publication_gap_ms", "p95"),
        "p95_hand_end_to_s4_ms": mean_path("hand_end_to_s4_ms", "p95"),
        "p95_pose_age_ms": mean_path("pose_age_ms", "p95"),
        "synchronizer_yield": mean_path("synchronizer_yield"),
        "peak_pss_kb": max((s.get("peak_pss_kb") or 0 for s in summaries), default=0),
        "thermal_decay": mean_path("thermal_throughput_decay_fraction"),
        "trace_coverage": mean_path("trace_coverage_fraction"),
        "crash_markers": sorted({m for s in summaries for m in s.get("crash_markers", [])}),
        "no_sign_onsets": sum(s.get("no_sign_onsets", 0) for s in summaries),
        "no_sign_commits": sum(s.get("no_sign_commits", 0) for s in summaries),
        "ordering_violations": sum(s.get("ordering_violations", 0) for s in summaries),
        "future_pose_violations": sum(s.get("future_pose_violations", 0) for s in summaries),
        "join_rejections": dict(
            sum((Counter(s.get("join_rejections", {})) for s in summaries), Counter())
        ),
    }


def compare(run_dir: Path) -> dict[str, Any]:
    summaries = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(run_dir.glob("*_summary.json"))
        if path.name != "a1_device_benchmark_summary.json"
    }
    baseline_rows = [value for key, value in summaries.items() if key.startswith("BASELINE_")]
    a1_rows = [value for key, value in summaries.items() if key.startswith("A1_")]
    if len(baseline_rows) != 2 or len(a1_rows) != 2:
        raise ValueError("Expected two BASELINE and two A1 summaries for order-balanced comparison")
    baseline = _aggregate(baseline_rows)
    a1 = _aggregate(a1_rows)

    first_baseline = baseline_rows[0]
    pose_p95 = first_baseline["pose_age_ms"]["p95"]
    gap_p95 = first_baseline["inter_hand_publication_gap_ms"]["p95"]
    max_pose_age_ms = math.ceil(float(pose_p95) + float(gap_p95))

    freshness = bool(
        a1["fresh_hand_rate"] >= 1.15 * baseline["fresh_hand_rate"]
        or a1["p95_hand_gap_ms"] <= 0.80 * baseline["p95_hand_gap_ms"]
    )
    gates = {
        "freshness_or_tail": freshness,
        "hand_end_to_s4": a1["p95_hand_end_to_s4_ms"] <= 0.75 * baseline["p95_hand_end_to_s4_ms"],
        "s4_rate": a1["s4_rate"] >= 0.95 * baseline["s4_rate"],
        "synchronizer_yield": a1["synchronizer_yield"]
        >= max(0.90, baseline["synchronizer_yield"] - 0.05),
        "pose_age": a1["p95_pose_age_ms"] <= max_pose_age_ms,
        "ordering": a1["ordering_violations"] == 0 and a1["future_pose_violations"] == 0,
        "stability": not a1["crash_markers"],
        "no_sign_behavior": a1["no_sign_onsets"] == 0 and a1["no_sign_commits"] == 0,
        "peak_pss": not baseline["peak_pss_kb"]
        or a1["peak_pss_kb"] <= 1.15 * baseline["peak_pss_kb"],
        "thermal_decay": (
            a1["thermal_decay"] is None
            or baseline["thermal_decay"] is None
            or a1["thermal_decay"] >= baseline["thermal_decay"] - 0.05
        ),
        "trace_coverage": (
            (baseline["trace_coverage"] is None or baseline["trace_coverage"] >= 0.90)
            and (a1["trace_coverage"] is None or a1["trace_coverage"] >= 0.90)
        ),
    }
    hard_stop = not all(gates.values())
    return {
        "preregistered_pose_age_formula": "ceil(BASELINE_1 pose_age_p95 + inter_hand_gap_p95)",
        "max_pose_age_ms": max_pose_age_ms,
        "baseline": baseline,
        "a1": a1,
        "gates": gates,
        "passed": not hard_stop,
        "decision": "PROCEED_TO_SMALL_SIGNING_SENTINEL" if not hard_stop else "REJECT_A1_HARD_STOP",
        "boundary_note": (
            "Inspect the complete metric profile; thresholds are preregistered, not a claim "
            "that 14.9% and 15.0% differ scientifically."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("summarize")
    one.add_argument("--log", type=Path, required=True)
    one.add_argument("--memory", type=Path)
    one.add_argument("--warmup-seconds", type=int, default=20)
    one.add_argument("--expected-seconds", type=int)
    one.add_argument("--output", type=Path, required=True)
    comparison = sub.add_parser("compare")
    comparison.add_argument("--run-dir", type=Path, required=True)
    comparison.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "summarize":
        payload = summarize(args.log, args.memory, args.warmup_seconds, args.expected_seconds)
    else:
        payload = compare(args.run_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
