"""Augmentation tests — shape, no-NaN, visibility preserved, absent hands stay zero, determinism."""

from __future__ import annotations

import numpy as np

from model.augment import AugmentConfig, augment_batch
from pipeline.features.contract import HANDS_DIM

CFG = AugmentConfig(rotation_deg=10.0, scale=0.1, noise_std=0.01, frame_mask_frac=0.1)


def _batch(b: int = 4, t: int = 64) -> np.ndarray:
    rng = np.random.default_rng(0)
    x = rng.standard_normal((b, t, 258)).astype(np.float32)
    x[:, :, HANDS_DIM + 3 :: 4] = 1.0  # pose visibility channels = 1
    return x


def test_shape_and_no_nan() -> None:
    out = augment_batch(_batch(), CFG, np.random.default_rng(1))
    assert out.shape == (4, 64, 258)
    assert not np.isnan(out).any()
    assert out.dtype == np.float32


def test_visibility_channel_untouched() -> None:
    x = _batch()
    out = augment_batch(x, CFG, np.random.default_rng(1))
    vis_in = x[:, :, HANDS_DIM + 3 :: 4]
    vis_out = out[:, :, HANDS_DIM + 3 :: 4]
    # visibility only changes where a whole frame was temporally masked to 0
    changed = vis_out != vis_in
    assert np.all(vis_out[changed] == 0.0)  # any change is a full-frame mask, never geometry


def test_absent_hands_stay_zero() -> None:
    x = _batch()
    x[:, :, 0:63] = 0.0  # left hand absent for all frames
    out = augment_batch(x, AugmentConfig(10.0, 0.1, 0.01, 0.0), np.random.default_rng(1))
    assert np.all(out[:, :, 0:63] == 0.0)  # augmentation never invents an absent hand


def test_deterministic_with_seed() -> None:
    x = _batch()
    a = augment_batch(x, CFG, np.random.default_rng(7))
    b = augment_batch(x, CFG, np.random.default_rng(7))
    assert np.array_equal(a, b)


def test_zero_config_is_near_identity() -> None:
    x = _batch()
    out = augment_batch(x, AugmentConfig(0.0, 0.0, 0.0, 0.0), np.random.default_rng(1))
    assert np.allclose(out, x, atol=1e-5)  # no rotation/scale/noise/mask => unchanged
