"""Feature 10 tests — real-timed (N4 off) composition: padding, truncation, mask, no-NaN."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.extract.constants import NUM_HAND_LANDMARKS, NUM_HANDS, NUM_POSE_LANDMARKS
from pipeline.features.contract import FEATURE_DIM, clip_features_realtimed
from pipeline.normalize.config import load_config
from pipeline.topology import (
    LEFT_HIP,
    LEFT_SHOULDER,
    LEFT_WRIST,
    RIGHT_HIP,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
)

NCONFIG = Path(__file__).resolve().parents[1] / "pipeline" / "config" / "normalize.yaml"


def _clip(t: int) -> tuple[np.ndarray, np.ndarray]:
    pose = np.full((t, NUM_POSE_LANDMARKS, 4), np.nan, np.float32)
    pose[:, LEFT_SHOULDER, :2] = (0.4, 0.3)
    pose[:, RIGHT_SHOULDER, :2] = (0.7, 0.3)
    pose[:, LEFT_HIP, :2] = (0.45, 0.7)
    pose[:, RIGHT_HIP, :2] = (0.55, 0.7)
    pose[:, :, 3] = 1.0
    for i in range(t):
        pose[i, LEFT_WRIST, :2] = (0.45 + 0.02 * (i % 2), 0.5)
        pose[i, RIGHT_WRIST, :2] = (0.65 + 0.02 * (i % 2), 0.5)
    hands = np.full((t, NUM_HANDS, NUM_HAND_LANDMARKS, 3), 0.5, np.float32)
    return hands, pose


def test_realtimed_preserves_length_and_pads() -> None:
    ncfg = load_config(NCONFIG)
    hands, pose = _clip(40)  # 40-frame clip, span 0..29 => 30 real frames
    feat, fmask, length, _ = clip_features_realtimed(hands, pose, 0, 29, ncfg, t_max=96)
    assert feat.shape == (96, FEATURE_DIM)
    assert length == 30  # real timing kept (NOT resampled to 96)
    assert fmask.sum() == 30 and fmask[:30].all() and not fmask[30:].any()
    assert np.all(feat[30:] == 0.0)  # padded region is exactly zero
    assert not np.isnan(feat).any()


def test_realtimed_truncates_overlength() -> None:
    ncfg = load_config(NCONFIG)
    hands, pose = _clip(140)
    feat, fmask, length, _ = clip_features_realtimed(hands, pose, 0, 139, ncfg, t_max=96)
    assert length == 96 and fmask.all()  # 140-frame span tail-truncated to t_max
    assert feat.shape == (96, FEATURE_DIM)


def test_realtimed_differs_from_resampled() -> None:
    # real-timed keeps native frames; a short span stays short (not stretched to 96)
    ncfg = load_config(NCONFIG)
    hands, pose = _clip(20)
    _, fmask, length, _ = clip_features_realtimed(hands, pose, 0, 11, ncfg, t_max=96)
    assert length == 12  # a 12-frame sign occupies 12 frames, rest padded


def test_realtimed_deterministic() -> None:
    ncfg = load_config(NCONFIG)
    hands, pose = _clip(30)
    a = clip_features_realtimed(hands, pose, 0, 25, ncfg, 96)[0]
    b = clip_features_realtimed(hands, pose, 0, 25, ncfg, 96)[0]
    assert np.array_equal(a, b)


def test_realtimed_pose_only_no_nan() -> None:
    ncfg = load_config(NCONFIG)
    hands, pose = _clip(24)
    hands[:] = np.nan  # hands never detected
    feat, _, _, _ = clip_features_realtimed(hands, pose, 0, 17, ncfg, 96)
    assert not np.isnan(feat).any()  # NaN->0 imputation holds in the streaming path too


def test_config_streaming_defaults() -> None:
    from pipeline.features.config import load_config as load_fcfg

    fcfg = load_fcfg(Path(__file__).resolve().parents[1] / "pipeline" / "config" / "features.yaml")
    assert fcfg.streaming_t_max == 96
    assert "streaming" in str(fcfg.streaming_output_root)
