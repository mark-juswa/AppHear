"""Tests for paired E2b causal pose-wrist ROI recovery."""

from __future__ import annotations

import numpy as np
import pytest

from pipeline.crops.config import RoiConfig
from pipeline.crops.pose_roi import (
    PoseRecoveryConfig,
    causal_pose_recovery_sequence,
    hand_to_shoulder_ratios,
)


def _roi() -> RoiConfig:
    return RoiConfig(
        crop_sizes=(112,),
        expansion_factors=(1.75,),
        min_valid_landmarks=15,
        min_side_fraction=0.12,
        max_side_fraction=0.75,
        max_hold_ms=100,
        pad_value_rgb=(0, 0, 0),
    )


def _pose(frames: int) -> np.ndarray:
    pose = np.full((frames, 33, 4), np.nan, dtype=np.float32)
    pose[:, 11] = [0.4, 0.4, 0.0, 1.0]
    pose[:, 12] = [0.6, 0.4, 0.0, 1.0]
    pose[:, 15] = [0.3, 0.5, 0.0, 1.0]
    pose[:, 16] = [0.7, 0.5, 0.0, 1.0]
    return pose


def _recovery(max_age: int = 150) -> PoseRecoveryConfig:
    return PoseRecoveryConfig(
        min_pose_visibility=0.5,
        fallback_side_ratio=0.7,
        max_track_age_ms=max_age,
    )


def test_pose_motion_translates_fresh_direct_box() -> None:
    hands = np.full((3, 2, 21, 3), np.nan, dtype=np.float32)
    hands[0, 0, :, 0] = np.linspace(0.2, 0.4, 21)
    hands[0, 0, :, 1] = np.linspace(0.4, 0.6, 21)
    hands[0, 0, :, 2] = 0.0
    scores = np.zeros((3, 2), dtype=np.float32)
    scores[0, 0] = 1.0
    pose = _pose(3)
    pose[1, 15, 0] += 0.1
    rois = causal_pose_recovery_sequence(
        hands,
        scores,
        pose,
        np.array([0, 50, 200]),
        200,
        100,
        1.75,
        _roi(),
        _recovery(150),
    )
    assert rois[0][0].source == "direct"
    assert rois[1][0].source == "pose_tracked"
    assert rois[2][0].source == "pose_fallback"
    assert rois[1][0].box_xyxy is not None
    assert rois[0][0].box_xyxy is not None
    assert rois[1][0].box_xyxy[0] - rois[0][0].box_xyxy[0] == pytest.approx(20.0)


def test_current_pose_fallback_works_without_hand_history() -> None:
    hands = np.full((1, 2, 21, 3), np.nan, dtype=np.float32)
    scores = np.zeros((1, 2), dtype=np.float32)
    rois = causal_pose_recovery_sequence(
        hands,
        scores,
        _pose(1),
        np.array([0]),
        200,
        100,
        1.75,
        _roi(),
        _recovery(),
    )
    assert all(item.source == "pose_fallback" for item in rois[0])
    assert all(item.box_xyxy is not None for item in rois[0])


def test_unsampled_frames_do_not_emit_or_refresh_pose_roi() -> None:
    hands = np.full((3, 2, 21, 3), np.nan, dtype=np.float32)
    scores = np.zeros((3, 2), dtype=np.float32)
    mask = np.array([True, False, True])
    rois = causal_pose_recovery_sequence(
        hands,
        scores,
        _pose(3),
        np.array([0, 33, 67]),
        200,
        100,
        1.75,
        _roi(),
        _recovery(),
        mask,
    )
    assert rois[0][0].source == "pose_fallback"
    assert rois[1][0].source == "unsampled"
    assert rois[2][0].source == "pose_fallback"


def test_ratio_measurement_uses_raw_hand_side() -> None:
    hands = np.full((1, 2, 21, 3), np.nan, dtype=np.float32)
    hands[0, 0, :, 0] = np.linspace(0.2, 0.3, 21)
    hands[0, 0, :, 1] = np.linspace(0.4, 0.5, 21)
    hands[0, 0, :, 2] = 0.0
    scores = np.array([[1.0, 0.0]], dtype=np.float32)
    ratios = hand_to_shoulder_ratios(
        hands, scores, _pose(1), 200, 100, min_valid_landmarks=15, min_pose_visibility=0.5
    )
    assert ratios == pytest.approx([0.5])
