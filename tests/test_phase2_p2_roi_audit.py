from __future__ import annotations

import json

from pipeline.rgb.phase2_p2_roi_audit import (
    _resolve_gold_sides,
    _side_convention_counterfactuals,
    _strict_route_selector_oracle,
    assign_detector_boxes,
    score_route_boxes,
    select_pilot_rows,
)


def test_select_pilot_rows_is_signer_diverse_and_split_safe() -> None:
    rows = []
    for label in ("A", "B"):
        for index in range(4):
            rows.append(
                {
                    "canonical_gloss": label,
                    "split": "train" if index < 3 else "val",
                    "hybrid_metadata_eligible": "True",
                    "signer_group_id": f"P{index}",
                    "any_direct_rate": str(index / 4),
                    "near_face_rate": "0.1",
                    "both_direct_rate": "0.2",
                    "edge_risk_rate": "0.0",
                    "sample_id": f"{label}{index}",
                }
            )
    selected = select_pilot_rows(rows, ["A", "B"], 3, 7)
    assert len(selected) == 6
    assert len({row["signer_group_id"] for row in selected if row["canonical_gloss"] == "A"}) == 3


def test_detector_boxes_are_assigned_to_nearest_anatomical_anchor() -> None:
    boxes = [(0.0, 0.0, 10.0, 10.0), (90.0, 0.0, 100.0, 10.0)]
    assigned = assign_detector_boxes(boxes, [(95.0, 5.0), (5.0, 5.0)])
    assert assigned[0] == boxes[1]
    assert assigned[1] == boxes[0]


def test_route_box_scoring_detects_complete_two_hand_coverage() -> None:
    gold = [
        {"anatomical_side": "left", "x_min": 10, "y_min": 10, "x_max": 20, "y_max": 20},
        {"anatomical_side": "right", "x_min": 70, "y_min": 10, "x_max": 80, "y_max": 20},
    ]
    covered, complete, side_errors = score_route_boxes(gold, [(5, 5, 25, 25), (65, 5, 85, 25)])
    assert covered == 2
    assert complete
    assert side_errors == 0


def test_route_box_scoring_detects_side_swap() -> None:
    gold = [
        {"anatomical_side": "left", "x_min": 10, "y_min": 10, "x_max": 20, "y_max": 20},
        {"anatomical_side": "right", "x_min": 70, "y_min": 10, "x_max": 80, "y_max": 20},
    ]
    covered, complete, side_errors = score_route_boxes(gold, [(65, 5, 85, 25), (5, 5, 25, 25)])
    assert covered == 0
    assert not complete
    assert side_errors == 2


def test_unknown_two_hand_scoring_cannot_reuse_one_box() -> None:
    gold = [
        {"anatomical_side": "unknown", "x_min": 10, "y_min": 10, "x_max": 20, "y_max": 20},
        {"anatomical_side": "unknown", "x_min": 12, "y_min": 12, "x_max": 18, "y_max": 18},
    ]
    covered, complete, side_errors = score_route_boxes(gold, [(5, 5, 25, 25), None])
    assert covered == 1
    assert not complete
    assert side_errors == 0


def test_side_adjudication_resolves_existing_box_order() -> None:
    gold = [
        {"anatomical_side": "unknown", "x_min": 0.1},
        {"anatomical_side": "unknown", "x_min": 0.7},
    ]
    resolved = _resolve_gold_sides(
        "sample",
        gold,
        {"sample": "box1_right_box2_left"},
    )
    assert [hand["anatomical_side"] for hand in resolved] == ["right", "left"]
    assert [hand["anatomical_side"] for hand in gold] == ["unknown", "unknown"]


def test_strict_selector_oracle_cannot_combine_routes() -> None:
    gold = [
        {"x_min": 0.1, "y_min": 0.1, "x_max": 0.2, "y_max": 0.2, "anatomical_side": "left"},
        {"x_min": 0.8, "y_min": 0.1, "x_max": 0.9, "y_max": 0.2, "anatomical_side": "right"},
    ]
    rows = []
    reviews = {}
    for route, boxes in (
        ("R1", [[0.1, 0.1, 0.2, 0.2], None]),
        ("R2", [None, [0.8, 0.1, 0.9, 0.2]]),
    ):
        audit_id = f"sample-{route}"
        rows.append(
            {
                "sample_id": "sample",
                "route": route,
                "audit_id": audit_id,
                "gold_hands_json": json.dumps(gold),
                "route_boxes_json": json.dumps(boxes),
                "triplet_available_rate": "1.0",
                "synchronization_error_ms": "0.0",
            }
        )
        reviews[audit_id] = {"verdict": "incomplete_two_hand"}

    result = _strict_route_selector_oracle(
        rows, reviews, {"sample": "box1_left_box2_right"}
    )

    assert result["known_visible_roi_coverage"] == 0.5
    assert result["complete_two_hand_coverage"] == 0.0
    assert result["geometry_gates_crossed"] is False


def test_side_convention_counterfactual_detects_global_swap() -> None:
    gold = [
        {"x_min": 0.1, "y_min": 0.1, "x_max": 0.2, "y_max": 0.2, "anatomical_side": "left"},
        {"x_min": 0.8, "y_min": 0.1, "x_max": 0.9, "y_max": 0.2, "anatomical_side": "right"},
    ]
    rows = []
    for route in ("R0", "R1", "R2"):
        rows.append(
            {
                "sample_id": "sample",
                "route": route,
                "gold_hands_json": json.dumps(gold),
                "route_boxes_json": json.dumps(
                    [[0.8, 0.1, 0.9, 0.2], [0.1, 0.1, 0.2, 0.2]]
                ),
            }
        )

    result = _side_convention_counterfactuals(
        rows, {"sample": "box1_left_box2_right"}
    )

    assert result["R1"]["as_recorded"]["anatomical_side_accuracy"] == 0.0
    assert result["R1"]["globally_swapped"]["anatomical_side_accuracy"] == 1.0
    assert result["R1"]["preferred_convention"] == "globally_swapped"
