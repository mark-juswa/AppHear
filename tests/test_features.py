"""Feature 05 tests — v3.0 contract composition, NaN imputation, presence mask, determinism.
The determinism test is the seed of the future Android S4 skew test."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pipeline.extract.constants import NUM_HAND_LANDMARKS, NUM_HANDS, NUM_POSE_LANDMARKS
from pipeline.features.contract import (
    FEATURE_DIM,
    HANDS_DIM,
    POSE_DIM,
    SCHEMA_VERSION,
    build_feature_vector,
    clip_features,
)
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


def _clip(t: int, hands_present: bool = True) -> tuple[np.ndarray, np.ndarray]:
    pose = np.full((t, NUM_POSE_LANDMARKS, 4), np.nan, np.float32)
    pose[:, LEFT_SHOULDER, :2] = (0.4, 0.3)
    pose[:, RIGHT_SHOULDER, :2] = (0.7, 0.3)
    pose[:, LEFT_HIP, :2] = (0.45, 0.7)
    pose[:, RIGHT_HIP, :2] = (0.55, 0.7)
    pose[:, :, 3] = 1.0  # visibility present everywhere we set; NaN elsewhere
    for i in range(t):
        pose[i, LEFT_WRIST, :2] = (0.45 + 0.02 * (i % 2), 0.5)
        pose[i, RIGHT_WRIST, :2] = (0.65 + 0.02 * (i % 2), 0.5)
    hands = np.full((t, NUM_HANDS, NUM_HAND_LANDMARKS, 3), np.nan, np.float32)
    if hands_present:
        hands[:] = 0.5  # arbitrary present hand landmarks
    return hands, pose


# --- contract constants -------------------------------------------------------------------


def test_contract_dims() -> None:
    assert HANDS_DIM == 126 and POSE_DIM == 132 and FEATURE_DIM == 258
    assert SCHEMA_VERSION == "3.0"


# --- build_feature_vector -----------------------------------------------------------------


def test_vector_shape_and_no_nan() -> None:
    hands = np.full((8, 2, 21, 3), np.nan, np.float32)  # both hands absent
    pose = np.zeros((8, 33, 4), np.float32)
    vec, mask = build_feature_vector(hands, pose)
    assert vec.shape == (8, FEATURE_DIM)
    assert not np.isnan(vec).any()  # NaN -> 0 imputation
    assert np.all(vec[:, :HANDS_DIM] == 0.0)  # absent hands imputed to 0
    assert mask.shape == (8, 2) and np.all(mask == 0.0)  # both slots absent


def test_mask_reflects_present_slots() -> None:
    hands = np.full((4, 2, 21, 3), np.nan, np.float32)
    hands[:, 1] = 0.3  # only right slot present
    vec, mask = build_feature_vector(hands, np.zeros((4, 33, 4), np.float32))
    assert np.all(mask[:, 0] == 0.0) and np.all(mask[:, 1] == 1.0)
    assert not np.isnan(vec).any()


def test_pose_visibility_lands_in_vector() -> None:
    hands = np.zeros((3, 2, 21, 3), np.float32)
    pose = np.zeros((3, 33, 4), np.float32)
    pose[:, :, 3] = 1.0  # visibility channel
    vec, _ = build_feature_vector(hands, pose)
    pose_block = vec[:, HANDS_DIM:].reshape(3, 33, 4)
    assert np.all(pose_block[:, :, 3] == 1.0)  # visibility preserved in the 258


# --- full composition ---------------------------------------------------------------------


def test_clip_features_composes_to_contract() -> None:
    ncfg = load_config(NCONFIG)
    hands, pose = _clip(20)
    vec, mask, params = clip_features(hands, pose, 0, 19, ncfg, resample_t=64)
    assert vec.shape == (64, FEATURE_DIM)  # N4 resampled to T=64
    assert mask.shape == (64, 2)
    assert not np.isnan(vec).any()
    assert params.scale == pytest.approx(0.3, abs=1e-5)  # shoulder width normalized


def test_clip_features_deterministic() -> None:
    # Byte-identical output for identical input -> the property Android S4 must match.
    ncfg = load_config(NCONFIG)
    hands, pose = _clip(18)
    a, am, _ = clip_features(hands, pose, 0, 17, ncfg, 64)
    b, bm, _ = clip_features(hands, pose, 0, 17, ncfg, 64)
    assert np.array_equal(a, b) and np.array_equal(am, bm)


def test_absent_hands_still_produce_valid_features() -> None:
    ncfg = load_config(NCONFIG)
    hands, pose = _clip(16, hands_present=False)  # hands never detected
    vec, mask, _ = clip_features(hands, pose, 0, 15, ncfg, 64)
    assert not np.isnan(vec).any()  # pose-only clip still yields a usable vector
    assert np.all(mask == 0.0)
