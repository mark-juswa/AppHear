"""Tests for the side-independent E2e gold-audit workflow."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from pipeline.tracking.e2e_gold import (
    INDEX_FIELDS,
    REVIEW_FIELDS,
    select_gold_samples,
    span_frame,
)
from pipeline.tracking.e2e_gold_audit import (
    analyze,
    association_score,
    iou,
    landmark_matches,
    palm_center,
)
from pipeline.tracking.e2e_gold_review import completion_error, validate_run


def _candidate(index: int, cadence: int, detected: int) -> dict[str, str]:
    return {
        "item_id": str(index),
        "label": "positive",
        "candidate_id": "image_d50_p50",
        "cadence": str(cadence),
        "hand": "left",
        "target_detected": str(detected),
        "raw_detected_hands": str(detected),
        "clip_id": f"clip-{index}",
        "frame_index": str(index),
    }


def _write(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _prediction(center_x: float, center_y: float, label: str = "right") -> dict[str, object]:
    landmarks = []
    for index in range(21):
        offset_x = ((index % 5) - 2) * 0.006
        offset_y = ((index // 5) - 2) * 0.006
        landmarks.append({"x": center_x + offset_x, "y": center_y + offset_y, "z": 0.0})
    return {
        "box": [center_x - 0.03, center_y - 0.03, center_x + 0.03, center_y + 0.03],
        "label": label,
        "score": 0.9,
        "landmarks": landmarks,
    }


def _gold(
    x_min: float, y_min: float, x_max: float, y_max: float, side: str = "unknown"
) -> dict[str, object]:
    return {
        "x_min": x_min,
        "y_min": y_min,
        "x_max": x_max,
        "y_max": y_max,
        "anatomical_side": side,
    }


def test_span_frame_uses_registered_fraction_and_validates_bounds() -> None:
    assert span_frame(10, 30, 0.25) == 15
    assert span_frame(10, 30, 0.50) == 20
    assert span_frame(10, 30, 0.75) == 25
    with pytest.raises(ValueError):
        span_frame(30, 10, 0.50)
    with pytest.raises(ValueError):
        span_frame(10, 30, 1.50)


def test_selection_balances_cadence_without_conditioning_on_detection() -> None:
    rows = [_candidate(index, cadence, index % 2) for index, cadence in enumerate((1, 4, 8) * 4)]
    selected = select_gold_samples(rows, count=6, seed=7)
    assert len(selected) == 6
    assert {int(row["cadence"]) for row in selected} == {1, 4, 8}
    assert len({(row["clip_id"], row["frame_index"]) for row in selected}) == 6


def test_completion_requires_all_boxes_and_quality_flags() -> None:
    row = {field: "" for field in REVIEW_FIELDS}
    row.update(
        {
            "sample_id": "g001",
            "review_status": "accepted",
            "source_mirrored": "unknown",
            "visible_hand_count": "1",
            "gold_hands_json": json.dumps([_gold(0.1, 0.2, 0.3, 0.5)]),
            "motion_blur": "no",
            "occlusion": "no",
            "near_face": "yes",
            "edge_clipped": "no",
            "partial_visibility": "no",
        }
    )
    assert completion_error(row) is None
    row["visible_hand_count"] = "2"
    assert "1 boxes" in str(completion_error(row))


def test_landmark_association_requires_palm_and_coverage_inside_gold() -> None:
    gold = _gold(0.2, 0.2, 0.5, 0.6)
    inside = _prediction(0.35, 0.4)
    outside = _prediction(0.65, 0.4)
    assert palm_center(inside) == pytest.approx((0.3488, 0.3964))
    assert association_score(gold, inside) is not None
    assert association_score(gold, outside) is None


def test_landmark_matching_is_one_to_one_for_two_hands_and_false_instance() -> None:
    gold = [_gold(0.05, 0.2, 0.35, 0.7), _gold(0.65, 0.2, 0.95, 0.7)]
    predictions = [_prediction(0.2, 0.4), _prediction(0.8, 0.4), _prediction(0.5, 0.1)]
    matches = landmark_matches(gold, predictions)
    assert {(gold_index, prediction_index) for gold_index, prediction_index, _ in matches} == {
        (0, 0),
        (1, 1),
    }


def test_overlapping_gold_boxes_maximize_match_count() -> None:
    gold = [_gold(0.1, 0.2, 0.55, 0.7), _gold(0.45, 0.2, 0.9, 0.7)]
    predictions = [_prediction(0.3, 0.4), _prediction(0.7, 0.4)]
    matches = landmark_matches(gold, predictions)
    assert len(matches) == 2
    assert {gold_index for gold_index, _prediction_index, _score in matches} == {0, 1}


def test_iou_is_retained_only_as_localization_diagnostic() -> None:
    gold_box = _gold(0.1, 0.2, 0.3, 0.5)
    prediction = {"box": [0.1, 0.2, 0.3, 0.5]}
    assert iou(gold_box, prediction) == 1.0


def test_audit_uses_landmark_association_and_keeps_identity_separate(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    image = tmp_path / "image.png"
    panel = tmp_path / "panel.jpg"
    image.write_bytes(b"x")
    panel.write_bytes(b"x")
    gold_box = _gold(0.1, 0.2, 0.4, 0.6, side="left")
    prediction = _prediction(0.25, 0.4, label="right")

    index = {field: "" for field in INDEX_FIELDS}
    index.update(
        {
            "sample_id": "g001",
            "video_file": "clip.mp4",
            "sampling_cadence": "1",
            "center_image_path": str(image),
            "context_panel_path": str(panel),
            "detected_hands_json": json.dumps([prediction]),
        }
    )
    review = {field: "" for field in REVIEW_FIELDS}
    review.update(
        {
            "sample_id": "g001",
            "review_status": "accepted",
            "source_mirrored": "mirrored",
            "mirror_evidence": "controlled fixture",
            "visible_hand_count": "1",
            "gold_hands_json": json.dumps([gold_box]),
            "motion_blur": "no",
            "occlusion": "no",
            "near_face": "no",
            "edge_clipped": "no",
            "partial_visibility": "no",
        }
    )
    _write(run_dir / "internal_index.csv", INDEX_FIELDS, [index])
    _write(run_dir / "gold_review.csv", REVIEW_FIELDS, [review])
    report = analyze(run_dir, run_dir / "summary.json")
    assert report["primary"]["visible_hand_instance_recall"] == 1.0
    assert report["primary"]["unmatched_prediction_rate"] == 0.0
    assert report["identity"]["accuracy"] == 1.0
    assert report["valid_for_gate_decision"] is False


def test_invalid_partial_acceptance_does_not_block_reopening(tmp_path: Path) -> None:
    image = tmp_path / "image.png"
    panel = tmp_path / "panel.jpg"
    image.write_bytes(b"x")
    panel.write_bytes(b"x")
    index = {
        "g001": {
            "sample_id": "g001",
            "video_file": "clip.mp4",
            "center_image_path": str(image),
            "context_panel_path": str(panel),
        }
    }
    row = {field: "" for field in REVIEW_FIELDS}
    row.update(
        {
            "sample_id": "g001",
            "review_status": "accepted",
            "source_mirrored": "unmirrored",
            "visible_hand_count": "0",
            "gold_hands_json": "[]",
            "motion_blur": "no",
            "occlusion": "no",
            "near_face": "no",
            "edge_clipped": "no",
            "partial_visibility": "no",
        }
    )
    assert completion_error(row) == "known mirror status requires evidence"
    assert validate_run([row], index) == []


def test_zero_hand_rows_reject_hand_quality_flags() -> None:
    row = {field: "" for field in REVIEW_FIELDS}
    row.update(
        {
            "sample_id": "g000",
            "review_status": "accepted",
            "source_mirrored": "unknown",
            "visible_hand_count": "0",
            "gold_hands_json": "[]",
            "motion_blur": "no",
            "occlusion": "no",
            "near_face": "no",
            "edge_clipped": "no",
            "partial_visibility": "yes",
        }
    )
    assert completion_error(row) == "zero-hand rows cannot have hand-quality flags"
