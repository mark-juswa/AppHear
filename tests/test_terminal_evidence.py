from __future__ import annotations

import numpy as np
import pytest

from eval.runtime_diagnostics.terminal_evidence import (
    build_control_envelope,
    classify_against_controls,
    summarize_interval,
)


def test_interval_summary_uses_only_requested_observations() -> None:
    timestamps = np.asarray([0.0, 100.0, 200.0, 300.0])
    probabilities = np.asarray(
        [[0.9, 0.1, 0.0], [0.0, 0.9, 0.1], [0.0, 0.3, 0.7], [0.0, 0.1, 0.9]]
    )
    result = summarize_interval(
        timestamps, probabilities, start_ms=100.0, end_ms=300.0, anchor_ms=150.0
    )
    assert result["observation_count"] == 3
    assert result["post_dominant_observation_count"] == 2
    assert result["first_post_dominant_delay_from_anchor_ms"] == 50.0
    assert not result["active_return_after_post_dominance"]


def test_fragmented_post_and_active_return_are_explicit() -> None:
    timestamps = np.asarray([0.0, 100.0, 200.0, 300.0])
    probabilities = np.asarray(
        [[0.0, 0.8, 0.2], [0.0, 0.2, 0.8], [0.0, 0.9, 0.1], [0.0, 0.1, 0.9]]
    )
    result = summarize_interval(
        timestamps, probabilities, start_ms=0.0, end_ms=300.0, anchor_ms=0.0
    )
    assert result["post_dominant_run_count"] == 2
    assert result["active_return_after_post_dominance"]


def test_nonchronological_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="NON_CHRONOLOGICAL"):
        summarize_interval(
            [0.0, 100.0, 50.0],
            [[0.0, 1.0, 0.0]] * 3,
            start_ms=0.0,
            end_ms=100.0,
            anchor_ms=0.0,
        )


def _row(value: float) -> dict[str, float]:
    return {
        "max_post_probability": value,
        "mean_post_probability": value,
        "mean_post_minus_active_margin": value,
        "post_dominant_fraction": value,
        "final_post_probability": value,
    }


def test_control_calibrated_classification_has_no_sweep() -> None:
    envelope = build_control_envelope([_row(0.8), _row(1.0)], [_row(0.0), _row(0.1)])
    present = classify_against_controls({"observation_count": 2, **_row(0.9)}, envelope)
    absent = classify_against_controls({"observation_count": 2, **_row(0.01)}, envelope)
    ambiguous = classify_against_controls({"observation_count": 2, **_row(0.5)}, envelope)
    assert present["classification"] == "MODEL_TERMINAL_SIGNAL_PRESENT_DECODER_NOT_USING_IT"
    assert absent["classification"] == "MODEL_TERMINAL_SIGNAL_ABSENT"
    assert ambiguous["classification"] == "MIXED_OR_AMBIGUOUS"
    assert not envelope["classification_rule"]["threshold_search"]
