from __future__ import annotations

import json
from pathlib import Path

from eval.runtime_diagnostics.a1_phone_benchmark import compare, summarize


def _line(event: str, ns: int, **fields: object) -> str:
    suffix = " ".join(f"{key}={value}" for key, value in fields.items())
    return f"I/AppHearA1: event={event} mode=BASELINE run_id=test seq=1 event_ns={ns} {suffix}"


def test_summarize_keeps_rates_yield_latency_and_overlap_separate(tmp_path: Path) -> None:
    rows = [
        _line("CAMERA_DELIVERED", 1_000_000_000, source_ns=100, arrival_ns=1_000_000_000),
        _line("ANALYZER_ACCEPT", 1_010_000_000, source_ns=100),
        _line("HAND_MAILBOX_ENQUEUE", 1_020_000_000, source_ns=100),
        _line(
            "HAND_INFERENCE_END",
            1_100_000_000,
            source_ns=100,
            start_ns=1_030_000_000,
            end_ns=1_100_000_000,
            duration_ns=70_000_000,
        ),
        _line(
            "POSE_INFERENCE_END",
            1_090_000_000,
            source_ns=100,
            start_ns=1_040_000_000,
            end_ns=1_090_000_000,
            duration_ns=50_000_000,
        ),
        _line("HAND_PUBLICATION", 1_110_000_000, source_ns=100, publish_ns=1_110_000_000),
        _line("POSE_PUBLICATION", 1_115_000_000, source_ns=100, publish_ns=1_115_000_000),
        _line(
            "SYNCHRONIZER_JOIN",
            1_120_000_000,
            hand_source_ns=100,
            pose_source_ns=100,
            pose_age_ns=0,
            status="VALID",
        ),
        _line(
            "CONSUMER_START",
            1_125_000_000,
            source_ns=100,
            hand_result_age_ns=25_000_000,
            source_to_s4_ns=125_000_000,
        ),
        _line("CONSUMER_END", 1_130_000_000, source_ns=100, duration_ns=5_000_000),
        _line("CAMERA_DELIVERED", 2_000_000_000, source_ns=200, arrival_ns=2_000_000_000),
        _line("HAND_PUBLICATION", 2_100_000_000, source_ns=200, publish_ns=2_100_000_000),
        _line(
            "SYNCHRONIZER_JOIN",
            2_110_000_000,
            hand_source_ns=200,
            pose_source_ns=100,
            pose_age_ns=100,
            status="VALID",
        ),
        _line("CONSUMER_END", 2_120_000_000, source_ns=200, duration_ns=5_000_000),
    ]
    log = tmp_path / "run.log"
    log.write_text("\n".join(rows), encoding="utf-8")

    result = summarize(log, None, warmup_seconds=0)

    assert result["synchronizer_yield"] == 1.0
    assert result["inter_hand_publication_gap_ms"]["p95"] == 990.0
    assert result["hand_inference_latency_ms"]["p95"] == 70.0
    assert result["hand_end_to_s4_ms"]["p95"] == 25.0
    assert result["inference_overlap"]["total_ms"] == 50.0
    assert result["inference_overlap"]["api_execution_interpretation"] == "OVERLAPPING"


def test_compare_uses_frozen_pose_formula_and_hard_stop(tmp_path: Path) -> None:
    base = {
        "rates_per_s": {"fresh_hand_publications": 5.0, "s4_observations": 5.0},
        "inter_hand_publication_gap_ms": {"p95": 300.0},
        "hand_end_to_s4_ms": {"p95": 100.0},
        "pose_age_ms": {"p95": 200.0},
        "synchronizer_yield": 1.0,
        "peak_pss_kb": 100_000,
        "thermal_throughput_decay_fraction": -0.02,
        "crash_markers": [],
        "no_sign_onsets": 0,
        "no_sign_commits": 0,
        "ordering_violations": 0,
        "join_rejections": {},
    }
    candidate = json.loads(json.dumps(base))
    candidate["rates_per_s"]["fresh_hand_publications"] = 6.0
    candidate["rates_per_s"]["s4_observations"] = 5.0
    candidate["inter_hand_publication_gap_ms"]["p95"] = 230.0
    candidate["hand_end_to_s4_ms"]["p95"] = 70.0
    candidate["pose_age_ms"]["p95"] = 400.0
    candidate["synchronizer_yield"] = 0.96
    for name, payload in {
        "BASELINE_1_summary.json": base,
        "BASELINE_2_summary.json": base,
        "A1_1_summary.json": candidate,
        "A1_2_summary.json": candidate,
    }.items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")

    result = compare(tmp_path)

    assert result["max_pose_age_ms"] == 500
    assert result["passed"] is True
