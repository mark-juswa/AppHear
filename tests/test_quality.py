"""Feature 04 tests — N4 resample exactness + Q quality-gate logic. Pure/synthetic."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pipeline.normalize.resample import resample_block, resample_clip
from pipeline.quality.config import load_config
from pipeline.quality.gate import evaluate_quality

CONFIG_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "config" / "quality.yaml"


# --- N4 resample --------------------------------------------------------------------------


def test_resample_length_and_endpoints() -> None:
    # a single channel ramp 0..9 over 10 frames -> resampled to 64 keeps endpoints, monotone
    arr = np.arange(10, dtype=np.float32).reshape(10, 1, 1)
    out = resample_block(arr, 64)
    assert out.shape == (64, 1, 1)
    assert out[0, 0, 0] == pytest.approx(0.0)
    assert out[-1, 0, 0] == pytest.approx(9.0)
    assert np.all(np.diff(out[:, 0, 0]) >= -1e-6)  # monotone non-decreasing


def test_resample_linear_midpoint() -> None:
    arr = np.array([0.0, 10.0], dtype=np.float32).reshape(2, 1, 1)  # linear 0->10
    out = resample_block(arr, 3)  # t = 0, 0.5, 1
    assert out[:, 0, 0] == pytest.approx([0.0, 5.0, 10.0])


def test_resample_single_frame_replicates() -> None:
    arr = np.full((1, 2, 3), 4.0, np.float32)
    out = resample_block(arr, 5)
    assert out.shape == (5, 2, 3) and np.all(out == 4.0)


def test_resample_empty_is_nan() -> None:
    out = resample_block(np.empty((0, 2, 3), np.float32), 5)
    assert out.shape == (5, 2, 3) and np.all(np.isnan(out))


def test_resample_nan_gap_interpolated() -> None:
    # channel present at ends, NaN in middle -> linear fill across the gap
    arr = np.array([0.0, np.nan, np.nan, 3.0], np.float32).reshape(4, 1, 1)
    out = resample_block(arr, 4)
    assert not np.isnan(out).any()
    assert out[0, 0, 0] == pytest.approx(0.0) and out[-1, 0, 0] == pytest.approx(3.0)


def test_resample_all_nan_channel_stays_nan() -> None:
    arr = np.full((4, 1, 1), np.nan, np.float32)
    assert np.all(np.isnan(resample_block(arr, 8)))


def test_resample_clip_shapes() -> None:
    cfg = load_config(CONFIG_PATH)
    hands = np.zeros((40, 2, 21, 3), np.float32)
    pose = np.zeros((40, 33, 4), np.float32)
    h, p = resample_clip(hands, pose, 5, 30, cfg.resample_T, cfg.resample_method)
    assert h.shape == (cfg.resample_T, 2, 21, 3) and p.shape == (cfg.resample_T, 33, 4)


def test_resample_rejects_unknown_method() -> None:
    with pytest.raises(ValueError, match="linear"):
        resample_clip(np.zeros((3, 2, 21, 3)), np.zeros((3, 33, 4)), 0, 2, 8, "cubic")


# --- Q quality gate -----------------------------------------------------------------------


def _scores(t: int, hand_frac: float, vis: float) -> tuple[np.ndarray, np.ndarray]:
    hand = np.zeros((t, 2), np.float32)
    hand[: int(t * hand_frac), 0] = 1.0  # left hand present in a fraction of frames
    pose = np.full((t,), vis, np.float32)
    return hand, pose


def test_gate_accepts_good_clip() -> None:
    cfg = load_config(CONFIG_PATH)
    hand, pose = _scores(40, hand_frac=0.5, vis=0.9)
    res = evaluate_quality(hand, pose, 0, 39, True, 30.0, cfg)
    assert res.accept and not res.reasons
    assert res.coverage == pytest.approx(0.5)


def test_gate_rejects_invalid_span() -> None:
    cfg = load_config(CONFIG_PATH)
    hand, pose = _scores(40, 0.5, 0.9)
    res = evaluate_quality(hand, pose, -1, -1, False, 30.0, cfg)
    assert not res.accept and res.reasons == ["invalid_span"]


def test_gate_rejects_low_coverage_and_fps() -> None:
    cfg = load_config(CONFIG_PATH)
    hand, pose = _scores(40, hand_frac=0.05, vis=0.9)  # coverage 0.05 < 0.15
    res = evaluate_quality(hand, pose, 0, 39, True, 10.0, cfg)  # fps 10 < 15
    assert not res.accept
    joined = " ".join(res.reasons)
    assert "low_coverage" in joined and "low_fps" in joined


def test_gate_rejects_low_confidence() -> None:
    cfg = load_config(CONFIG_PATH)
    hand, pose = _scores(40, 0.5, vis=0.2)  # visibility 0.2 < 0.5
    res = evaluate_quality(hand, pose, 0, 39, True, 30.0, cfg)
    assert not res.accept and any("low_confidence" in r for r in res.reasons)


def test_params_hash_changes_with_threshold() -> None:
    import dataclasses

    cfg = load_config(CONFIG_PATH)
    assert dataclasses.replace(cfg, min_coverage=0.9).params_hash != cfg.params_hash
