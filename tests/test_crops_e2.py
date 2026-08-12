"""Focused tests for the experiment-only E2 RGB crop stage."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from pipeline.crops.audit import summarize
from pipeline.crops.config import RoiConfig
from pipeline.crops.roi import causal_roi_sequence, direct_square_box, extract_square_crop
from pipeline.crops.sampling import select_frame_indices


def _roi_config() -> RoiConfig:
    return RoiConfig(
        crop_sizes=(80, 96, 112),
        expansion_factors=(1.5, 1.75, 2.0),
        min_valid_landmarks=15,
        min_side_fraction=0.12,
        max_side_fraction=0.75,
        max_hold_ms=100,
        pad_value_rgb=(0, 0, 0),
    )


def test_direct_box_is_square_and_centered() -> None:
    landmarks = np.full((21, 3), np.nan, dtype=np.float32)
    landmarks[:, 0] = np.linspace(0.4, 0.6, 21)
    landmarks[:, 1] = np.linspace(0.3, 0.5, 21)
    landmarks[:, 2] = 0.0
    box = direct_square_box(landmarks, 200, 100, 1.5, _roi_config())
    assert box is not None
    x1, y1, x2, y2 = box
    assert x2 - x1 == pytest.approx(y2 - y1)
    assert (x1 + x2) / 2 == pytest.approx(100.0)
    assert (y1 + y2) / 2 == pytest.approx(40.0)


def test_causal_hold_expires_by_timestamp() -> None:
    hands = np.full((4, 2, 21, 3), np.nan, dtype=np.float32)
    hands[0, 0, :, :2] = 0.5
    hands[0, 0, :, 2] = 0.0
    scores = np.zeros((4, 2), dtype=np.float32)
    scores[0, 0] = 1.0
    rois = causal_roi_sequence(
        hands, scores, np.array([0, 50, 100, 150]), 200, 100, 1.5, _roi_config()
    )
    assert [frame[0].source for frame in rois] == ["direct", "held", "held", "missing"]
    assert all(frame[1].source == "missing" for frame in rois)


def test_unsampled_native_detection_does_not_refresh_low_fps_roi() -> None:
    hands = np.full((5, 2, 21, 3), np.nan, dtype=np.float32)
    hands[1, 0, :, :2] = 0.5
    hands[1, 0, :, 2] = 0.0
    scores = np.zeros((5, 2), dtype=np.float32)
    scores[1, 0] = 1.0
    mask = np.array([True, False, False, False, True])
    rois = causal_roi_sequence(
        hands,
        scores,
        np.array([0, 33, 67, 100, 133]),
        200,
        100,
        1.5,
        _roi_config(),
        mask,
    )
    assert rois[1][0].source == "missing"
    assert rois[4][0].source == "missing"


def test_observation_mask_shape_is_validated() -> None:
    hands = np.full((2, 2, 21, 3), np.nan, dtype=np.float32)
    scores = np.zeros((2, 2), dtype=np.float32)
    with pytest.raises(ValueError, match="observation_mask shape"):
        causal_roi_sequence(
            hands,
            scores,
            np.array([0, 33]),
            200,
            100,
            1.5,
            _roi_config(),
            np.array([True]),
        )


def test_crop_padding_and_shape() -> None:
    frame = np.full((50, 100, 3), 255, dtype=np.uint8)
    crop, padding = extract_square_crop(frame, (-10.0, 5.0, 30.0, 45.0), 80, (0, 0, 0))
    assert crop.shape == (80, 80, 3)
    assert padding == pytest.approx(0.25)
    assert np.any(crop == 0)
    assert np.any(crop == 255)


def test_frame_selection_is_deterministic_and_bounded() -> None:
    selected = select_frame_indices(10, 50, cadence=4, frames_per_clip=5)
    assert selected == select_frame_indices(10, 50, cadence=4, frames_per_clip=5)
    assert len(selected) == 5
    assert all(10 <= value <= 50 and value % 4 == 0 for value in selected)


def test_audit_summary_uses_visible_hand_denominator(tmp_path: Path) -> None:
    index_path = tmp_path / "index.csv"
    audit_path = tmp_path / "audit.csv"
    output_path = tmp_path / "summary.json"
    with index_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["crop_id", "crop_size", "expansion", "cadence", "roi_source"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "crop_id": "a",
                "crop_size": 96,
                "expansion": 1.75,
                "cadence": 1,
                "roi_source": "direct",
            }
        )
        writer.writerow(
            {
                "crop_id": "b",
                "crop_size": 96,
                "expansion": 1.75,
                "cadence": 1,
                "roi_source": "missing",
            }
        )
    with audit_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["crop_id", "visible_hand", "usable"])
        writer.writeheader()
        writer.writerow({"crop_id": "a", "visible_hand": "yes", "usable": "yes"})
        writer.writerow({"crop_id": "b", "visible_hand": "no", "usable": ""})
    report = summarize(audit_path, index_path, output_path, gate=0.98)
    assert report["groups"]["overall"]["visible"] == 1
    assert report["groups"]["overall"]["usable_visible_rate"] == 1.0
    assert report["incomplete_rows"] == 0
