"""Tests for C0-B0 development matching and threshold selection."""

from __future__ import annotations

from pipeline.tracking.e2e_c0b_stage2_eval import (
    _availability,
    _exact_matches,
    _select_threshold,
    _wilson,
)


def _box(x1: float, y1: float, x2: float, y2: float) -> dict[str, float]:
    return {"x_min": x1, "y_min": y1, "x_max": x2, "y_max": y2}


def _metric(
    threshold: float, recall: float, two_hand: float, iou50: float, false_rate: float
) -> dict:
    return {
        "threshold": threshold,
        "availability": {"rate": recall},
        "complete_two_hand_recall": {"rate": two_hand},
        "iou50_recall": {"rate": iou50},
        "negative_frame_false_positive_rate": {"rate": false_rate},
    }


def test_availability_requires_center_and_predicted_area_coverage() -> None:
    gold = _box(0.2, 0.2, 0.6, 0.6)

    assert _availability(gold, _box(0.25, 0.25, 0.55, 0.55))
    assert not _availability(gold, _box(0.0, 0.0, 1.0, 1.0))
    assert not _availability(gold, _box(0.61, 0.2, 0.8, 0.4))


def test_exact_matching_maximizes_cardinality_before_iou() -> None:
    gold = [_box(0.0, 0.0, 0.5, 1.0), _box(0.5, 0.0, 1.0, 1.0)]
    predictions = [_box(0.1, 0.1, 0.4, 0.9), _box(0.6, 0.1, 0.9, 0.9)]

    matches = _exact_matches(gold, predictions, _availability)

    assert len(matches) == 2
    assert {(gold_index, prediction_index) for gold_index, prediction_index, _ in matches} == {
        (0, 0),
        (1, 1),
    }


def test_threshold_selection_enforces_false_positive_gate_and_ties() -> None:
    curve = [
        _metric(0.2, 0.95, 0.90, 0.80, 0.10),
        _metric(0.4, 0.90, 0.80, 0.75, 0.00),
        _metric(0.6, 0.90, 0.80, 0.75, 0.00),
    ]

    selected = _select_threshold(curve)

    assert selected is not None
    assert selected["threshold"] == 0.6


def test_wilson_preserves_counts() -> None:
    interval = _wilson(9, 10)

    assert interval["numerator"] == 9
    assert interval["denominator"] == 10
    assert interval["rate"] == 0.9
