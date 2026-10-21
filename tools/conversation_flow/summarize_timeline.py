"""Summarize an AppHear conversation-flow capture (Phase 0 baseline / Phase 1 comparison).

Input: a logcat file containing `AppHearTurn` JSON events (see `ConversationTimeline.kt`) and,
optionally, the `meminfo.jsonl` written by `capture_session.py`. Timing uses each event's `t`
(device elapsed-realtime ms); memory samples are aligned by wall-clock ms (`w`).

Metric definitions (identical for every build so runs are comparable):
- Round trip i: from the i-th `plan_ready` (a hearing message reaching the avatar) to the next.
  `taps_per_round_trip` counts `tap` events inside each complete round trip; taps before the
  first `plan_ready` are reported separately as `setup_taps`.
- talk_to_first_sign_ms: Text-to-ASL `speech_result` (ok) -> next `signing_started`.
- relay_to_first_sign_ms: Recognition `speech_result` (ok) -> next `signing_started`.
- reply_tap_to_recognition_ready_ms: Text-to-ASL `reply` tap -> next `recognition_ready`.
- recognition_start_to_ready_ms: `recognition_started` -> next `recognition_ready`.
- avatar_load_ms: Text-to-ASL `screen_created` -> next `avatar_ready`.
- signing_ms: `signing_started` -> next `signing_complete`.
Percentiles use the nearest-rank method and always report n.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

TAG = "AppHearTurn"
Event = dict[str, Any]


def parse_events(lines: Iterable[str]) -> list[Event]:
    """Extract timeline events from logcat lines; other lines and malformed JSON are skipped."""
    events: list[Event] = []
    for line in lines:
        tag_at = line.find(TAG)
        if tag_at < 0:
            continue
        brace = line.find("{", tag_at)
        if brace < 0:
            continue
        try:
            event = json.loads(line[brace:].strip())
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and "e" in event and "t" in event:
            events.append(event)
    events.sort(key=lambda event: event["t"])
    return events


def percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return float(ordered[rank - 1])


def describe(values: Sequence[float]) -> dict[str, float | int | None]:
    return {"n": len(values), "p50": percentile(values, 0.5), "p95": percentile(values, 0.95)}


def _matches(event: Event, name: str, **fields: Any) -> bool:
    return event["e"] == name and all(event.get(key) == value for key, value in fields.items())


def paired_latencies(
    events: Sequence[Event], start: dict[str, Any], end: dict[str, Any]
) -> list[float]:
    """Time from each start event to the first following end event (unpaired starts dropped)."""
    start_fields = dict(start)
    end_fields = dict(end)
    start_name = start_fields.pop("e")
    end_name = end_fields.pop("e")
    results: list[float] = []
    for index, event in enumerate(events):
        if not _matches(event, start_name, **start_fields):
            continue
        for later in events[index + 1 :]:
            if _matches(later, end_name, **end_fields):
                results.append(float(later["t"] - event["t"]))
                break
            if _matches(later, start_name, **start_fields):
                break
    return results


def round_trips(events: Sequence[Event]) -> dict[str, Any]:
    plan_times = [event["t"] for event in events if event["e"] == "plan_ready"]
    taps = [event for event in events if event["e"] == "tap"]
    setup = [tap for tap in taps if not plan_times or tap["t"] < plan_times[0]]
    per_trip: list[int] = []
    controls: Counter[str] = Counter()
    for begin, end in zip(plan_times, plan_times[1:], strict=False):
        inside = [tap for tap in taps if begin <= tap["t"] < end]
        per_trip.append(len(inside))
        controls.update(f"{tap.get('screen')}:{tap.get('control')}" for tap in inside)
    return {
        "hearing_messages": len(plan_times),
        "complete_round_trips": len(per_trip),
        "taps_per_round_trip": per_trip,
        "taps_per_round_trip_mean": (sum(per_trip) / len(per_trip)) if per_trip else None,
        "tap_controls_in_round_trips": dict(sorted(controls.items())),
        "setup_taps": [f"{tap.get('screen')}:{tap.get('control')}" for tap in setup],
    }


def screens(events: Sequence[Event]) -> dict[str, Any]:
    created: Counter[str] = Counter()
    max_live: dict[str, int] = {}
    for event in events:
        if event["e"] not in ("screen_created", "screen_destroyed"):
            continue
        screen = str(event.get("screen"))
        if event["e"] == "screen_created":
            created[screen] += 1
        live = event.get("live")
        if isinstance(live, int):
            max_live[screen] = max(max_live.get(screen, 0), live)
    return {"created": dict(sorted(created.items())), "max_live": dict(sorted(max_live.items()))}


def memory(samples: Sequence[dict[str, Any]], events: Sequence[Event]) -> dict[str, Any] | None:
    if not samples:
        return None
    totals = [float(sample["total_pss_kb"]) for sample in samples]
    plan_walls = [event["w"] for event in events if event["e"] == "plan_ready"]
    at_turns: list[float] = []
    for wall in plan_walls:
        nearest = min(samples, key=lambda sample: abs(sample["w"] - wall))
        at_turns.append(float(nearest["total_pss_kb"]))
    growth = (at_turns[-1] - at_turns[0]) / (len(at_turns) - 1) if len(at_turns) > 1 else None
    return {
        "samples": len(samples),
        "start_total_pss_mb": totals[0] / 1024,
        "max_total_pss_mb": max(totals) / 1024,
        "end_total_pss_mb": totals[-1] / 1024,
        "pss_mb_at_each_hearing_message": [value / 1024 for value in at_turns],
        "pss_growth_mb_per_round_trip": growth / 1024 if growth is not None else None,
    }


def summarize(events: Sequence[Event], samples: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
    fps = [
        float(e["fps"]) for e in events if e["e"] == "recognition_fps" and e.get("fps") is not None
    ]
    catalog = [float(e["ms"]) for e in events if e["e"] == "catalog_ready" and "ms" in e]
    latencies = {
        "talk_to_first_sign_ms": paired_latencies(
            events,
            {"e": "speech_result", "screen": "text_to_asl", "ok": True},
            {"e": "signing_started"},
        ),
        "relay_to_first_sign_ms": paired_latencies(
            events,
            {"e": "speech_result", "screen": "recognition", "ok": True},
            {"e": "signing_started"},
        ),
        "reply_tap_to_recognition_ready_ms": paired_latencies(
            events,
            {"e": "tap", "screen": "text_to_asl", "control": "reply"},
            {"e": "recognition_ready"},
        ),
        "recognition_start_to_ready_ms": paired_latencies(
            events, {"e": "recognition_started"}, {"e": "recognition_ready"}
        ),
        "avatar_load_ms": paired_latencies(
            events, {"e": "screen_created", "screen": "text_to_asl"}, {"e": "avatar_ready"}
        ),
        "signing_ms": paired_latencies(events, {"e": "signing_started"}, {"e": "signing_complete"}),
    }
    return {
        "events": len(events),
        "round_trips": round_trips(events),
        "latency": {name: describe(values) for name, values in latencies.items()},
        "catalog_ms": describe(catalog),
        "recognition_fps": describe(fps),
        "screens": screens(events),
        "memory": memory(samples, events),
        "signing_failures": sum(1 for event in events if event["e"] == "signing_failed"),
    }


def render_markdown(summary: dict[str, Any]) -> str:
    def fmt(value: Any) -> str:
        return (
            "-" if value is None else (f"{value:.1f}" if isinstance(value, float) else str(value))
        )

    trips = summary["round_trips"]
    rows = [
        "| Metric | n | p50 | p95 |",
        "|---|---|---|---|",
    ]
    for name, stats in {
        **summary["latency"],
        "catalog_ms": summary["catalog_ms"],
        "recognition_fps": summary["recognition_fps"],
    }.items():
        rows.append(f"| {name} | {stats['n']} | {fmt(stats['p50'])} | {fmt(stats['p95'])} |")
    lines = [
        "# Conversation-flow capture summary",
        "",
        f"- Hearing messages: {trips['hearing_messages']}; complete round trips: "
        f"{trips['complete_round_trips']}",
        f"- Taps per round trip: {trips['taps_per_round_trip']} "
        f"(mean {fmt(trips['taps_per_round_trip_mean'])})",
        f"- Tap controls in round trips: {trips['tap_controls_in_round_trips']}",
        f"- Setup taps before first message: {trips['setup_taps']}",
        f"- Screens created: {summary['screens']['created']}; max live: "
        f"{summary['screens']['max_live']}",
        f"- Signing failures: {summary['signing_failures']}",
        "",
        *rows,
    ]
    mem = summary["memory"]
    if mem:
        lines += [
            "",
            f"- Total PSS MB start/max/end: {fmt(mem['start_total_pss_mb'])} / "
            f"{fmt(mem['max_total_pss_mb'])} / {fmt(mem['end_total_pss_mb'])}",
            f"- PSS growth per round trip (MB): {fmt(mem['pss_growth_mb_per_round_trip'])}",
        ]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("capture_dir", type=Path, help="Directory written by capture_session.py")
    args = parser.parse_args(argv)
    directory: Path = args.capture_dir
    events = parse_events(
        (directory / "timeline.log").read_text(encoding="utf-8", errors="replace").splitlines()
    )
    meminfo_path = directory / "meminfo.jsonl"
    samples = (
        [json.loads(line) for line in meminfo_path.read_text(encoding="utf-8").splitlines() if line]
        if meminfo_path.exists()
        else []
    )
    summary = summarize(events, samples)
    (directory / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (directory / "summary.md").write_text(render_markdown(summary), encoding="utf-8")
    print(render_markdown(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
