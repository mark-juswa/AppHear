from __future__ import annotations

from typing import Any

from eval.runtime_diagnostics.p4a_dwpose_eligibility import (
    fit_logistic,
    metric_bundle,
    predict_model,
    truth_value,
)


def test_truth_value_preserves_unknown() -> None:
    assert truth_value("yes") == "VISIBLE"
    assert truth_value("no") == "NOT_VISIBLE"
    assert truth_value("uncertain") == "UNKNOWN"


def test_fixed_logistic_separates_simple_training_rows() -> None:
    rows: list[dict[str, Any]] = [
        {"truth": "NOT_VISIBLE", "x": -2.0},
        {"truth": "NOT_VISIBLE", "x": -1.0},
        {"truth": "VISIBLE", "x": 1.0},
        {"truth": "VISIBLE", "x": 2.0},
    ]
    model = fit_logistic(rows, ["x"])
    predictions, _ = predict_model(model, rows)
    assert predictions == [False, False, True, True]


def test_metric_bundle_uses_frame_level_zero_and_two_hand_denominators() -> None:
    rows = [
        {
            "truth": "NOT_VISIBLE",
            "manifest_row_id": "zero",
            "no_hand_rest": "yes",
            "leaving_frame": "no",
            "historical_blur_or_occlusion": "False",
            "expected_hands": "one",
            "crossing": "no",
            "hand_hand_contact": "no",
            "hand_body_contact": "no",
        },
        {
            "truth": "NOT_VISIBLE",
            "manifest_row_id": "zero",
            "no_hand_rest": "yes",
            "leaving_frame": "no",
            "historical_blur_or_occlusion": "False",
            "expected_hands": "one",
            "crossing": "no",
            "hand_hand_contact": "no",
            "hand_body_contact": "no",
        },
        {
            "truth": "VISIBLE",
            "manifest_row_id": "two",
            "no_hand_rest": "no",
            "leaving_frame": "no",
            "historical_blur_or_occlusion": "False",
            "expected_hands": "two",
            "crossing": "no",
            "hand_hand_contact": "no",
            "hand_body_contact": "no",
        },
        {
            "truth": "VISIBLE",
            "manifest_row_id": "two",
            "no_hand_rest": "no",
            "leaving_frame": "no",
            "historical_blur_or_occlusion": "False",
            "expected_hands": "two",
            "crossing": "no",
            "hand_hand_contact": "no",
            "hand_body_contact": "no",
        },
    ]
    result = metric_bundle(rows, [False, True, True, False])
    assert result["zero_hand_frame_false_presence"] == {
        "numerator": 1,
        "denominator": 1,
        "rate": 1.0,
    }
    assert result["complete_two_hand_retention"] == {
        "numerator": 0,
        "denominator": 1,
        "rate": 0.0,
    }
