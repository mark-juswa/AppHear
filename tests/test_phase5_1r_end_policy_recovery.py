from __future__ import annotations

from eval.runtime_diagnostics.phase5_1_offline_segmenter import load_calibration
from eval.runtime_diagnostics.phase5_1r_end_policy_recovery import (
    FINAL_STATUS,
    end_duration_candidates,
    non_runnable_config,
)


def test_end_duration_candidates_are_exact_calibration_breakpoints() -> None:
    attempts = load_calibration()
    candidates = end_duration_candidates(attempts)

    expected = {
        round(float(timestamps[end] - timestamps[start]), 9)
        for attempt in attempts
        for timestamps in (attempt.raw.arrays.timestamp_ms,)
        for start in range(len(timestamps))
        for end in range(start + 1, len(timestamps))
        if 0.0 < float(timestamps[end] - timestamps[start]) < 500.0
    }
    assert candidates == tuple(sorted(expected, reverse=True))
    assert len(candidates) == 49
    assert all(0.0 < value < 500.0 for value in candidates)


def test_no_feasible_duration_config_is_not_holdout_eligible() -> None:
    config = non_runnable_config({"status": FINAL_STATUS})

    assert config["freeze_status"] == "NOT_FROZEN_NO_GLOBAL_FEASIBLE_DURATION"
    assert config["holdout_eligible"] is False
    assert config["thresholds"] is None
    assert config["temporal_policy"]["end_quiet_persistence_ms"] is None
    assert config["missingness_rules"]["missing_evidence"] == (
        "UNKNOWN_NOT_ZERO_NOT_QUIET"
    )
