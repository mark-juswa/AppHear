"""Conversation-flow timeline parsing and metric definitions (Phase 0 tooling)."""

from __future__ import annotations

import json
from typing import Any

from tools.conversation_flow.summarize_timeline import parse_events, percentile, summarize


def line(event: str, t: int, **fields: Any) -> str:
    payload = {"e": event, "t": t, "w": 1_000_000 + t, **fields}
    return f"1729267200.123  1234  1234 I AppHearTurn: {json.dumps(payload)}"


def test_parse_skips_noise_and_sorts_by_elapsed_time() -> None:
    lines = [
        "--------- beginning of main",
        line("b", 20),
        "1729267200.1 1 1 I AppHearTurn: {not json",
        line("a", 10),
        '1729267200.1 1 1 I OtherTag: {"e":"x","t":1}',
    ]
    assert [event["e"] for event in parse_events(lines)] == ["a", "b"]


def test_percentile_nearest_rank() -> None:
    assert percentile([], 0.5) is None
    assert percentile([5.0], 0.95) == 5.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 4.0


def test_round_trip_taps_and_latencies() -> None:
    events = parse_events(
        [
            line("screen_created", 0, screen="text_to_asl", live=1),
            line("avatar_ready", 900),
            line("tap", 1000, screen="text_to_asl", control="talk_mode"),
            line("tap", 1100, screen="text_to_asl", control="mic"),
            line("speech_result", 3000, screen="text_to_asl", ok=True, chars=12),
            line("plan_ready", 3010, source="SPEECH", signs=2, unsupported=0),
            line("signing_started", 3200, signs=2),
            line("signing_complete", 6200, signs=2),
            line("tap", 7000, screen="text_to_asl", control="reply"),
            line("screen_created", 7050, screen="recognition", live=1),
            line("recognition_started", 7100),
            line("recognition_ready", 8100),
            line("recognition_fps", 9000, fps=7.5),
            line("tap", 12000, screen="recognition", control="hear"),
            line("tap", 13000, screen="recognition", control="speak"),
            line("speech_result", 15000, screen="recognition", ok=True, chars=9),
            line("screen_created", 15100, screen="text_to_asl", live=2),
            line("plan_ready", 28000, source="SPEECH", signs=1, unsupported=0),
            line("signing_started", 28100, signs=1),
        ]
    )
    summary = summarize(events)
    trips = summary["round_trips"]
    assert trips["hearing_messages"] == 2
    assert trips["taps_per_round_trip"] == [3]
    assert trips["setup_taps"] == ["text_to_asl:talk_mode", "text_to_asl:mic"]
    latency = summary["latency"]
    assert latency["talk_to_first_sign_ms"]["p50"] == 200.0
    assert latency["relay_to_first_sign_ms"]["p50"] == 13100.0
    assert latency["reply_tap_to_recognition_ready_ms"]["p50"] == 1100.0
    assert latency["recognition_start_to_ready_ms"]["p50"] == 1000.0
    assert latency["avatar_load_ms"] == {"n": 1, "p50": 900.0, "p95": 900.0}
    assert summary["screens"]["created"] == {"recognition": 1, "text_to_asl": 2}
    assert summary["screens"]["max_live"]["text_to_asl"] == 2
    assert summary["recognition_fps"]["p50"] == 7.5


def test_memory_growth_aligned_to_hearing_messages() -> None:
    events = parse_events(
        [
            line("plan_ready", 0, source="SPEECH", signs=1, unsupported=0),
            line("plan_ready", 10_000, source="SPEECH", signs=1, unsupported=0),
        ]
    )
    samples = [
        {"w": 1_000_000, "processes": [], "total_pss_kb": 512_000},
        {"w": 1_010_000, "processes": [], "total_pss_kb": 819_200},
    ]
    memory = summarize(events, samples)["memory"]
    assert memory is not None
    assert memory["pss_growth_mb_per_round_trip"] == 300.0
