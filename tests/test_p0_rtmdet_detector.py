from __future__ import annotations

import numpy as np

from pipeline.tracking.p0_rtmdet_detector import (
    _availability,
    _duplicate_prediction,
    _exact_matches,
    _merged_prediction,
    _preprocess,
    _wilson,
)


def _box(x1: float, y1: float, x2: float, y2: float) -> dict[str, float]:
    return {"x_min": x1, "y_min": y1, "x_max": x2, "y_max": y2}


def test_availability_requires_center_and_half_prediction_containment() -> None:
    gold = _box(0.2, 0.2, 0.6, 0.6)
    assert _availability(gold, _box(0.3, 0.3, 0.5, 0.5))
    assert not _availability(gold, _box(0.55, 0.3, 0.95, 0.5))
    assert not _availability(gold, _box(0.0, 0.0, 0.1, 0.1))


def test_exact_matching_is_one_to_one_and_maximum_cardinality() -> None:
    gold = [_box(0.0, 0.0, 0.4, 1.0), _box(0.6, 0.0, 1.0, 1.0)]
    predictions = [_box(0.1, 0.1, 0.3, 0.9), _box(0.7, 0.1, 0.9, 0.9)]
    matches = _exact_matches(gold, predictions, _availability)
    assert {(gold_index, pred_index) for gold_index, pred_index, _ in matches} == {
        (0, 0),
        (1, 1),
    }


def test_duplicate_and_merged_diagnostics_are_separate() -> None:
    gold = [_box(0.1, 0.2, 0.4, 0.8), _box(0.6, 0.2, 0.9, 0.8)]
    predictions = [
        _box(0.12, 0.25, 0.38, 0.75),
        _box(0.14, 0.28, 0.36, 0.72),
        _box(0.05, 0.1, 0.95, 0.9),
    ]
    matches = [(0, 0, 0.5)]
    assert _duplicate_prediction(gold, predictions, matches, 1)
    assert _merged_prediction(gold, predictions[2])


def test_preprocess_is_top_left_letterbox_nchw() -> None:
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    tensor, ratio = _preprocess(image)
    assert tensor.shape == (1, 3, 320, 320)
    assert ratio == 1.6


def test_wilson_is_bounded() -> None:
    interval = _wilson(122, 184)
    assert interval["rate"] == 122 / 184
    assert 0.59 < float(interval["low"]) < float(interval["rate"])
    assert float(interval["rate"]) < float(interval["high"]) < 0.74
