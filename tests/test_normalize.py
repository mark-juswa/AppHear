"""Feature 03 tests — N1/N2/N3 transforms + handedness + invariance properties.
Exact/synthetic, no models or dataset needed."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from pipeline.extract.constants import NUM_HAND_LANDMARKS, NUM_HANDS, NUM_POSE_LANDMARKS
from pipeline.normalize.config import load_config
from pipeline.normalize.handedness import decide_handedness
from pipeline.normalize.scale import clip_scale
from pipeline.normalize.transforms import _shoulder_angle, normalize_clip
from pipeline.topology import (
    LEFT_SHOULDER,
    LEFT_WRIST,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
    pose_mirror_perm,
)

CONFIG_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "config" / "normalize.yaml"


def _clip(t: int, shoulders: tuple, left_active: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Build (hands_image, pose_image). Shoulder positions set the tilt directly; one wrist is
    made more active to set the dominant hand."""
    (lsx, lsy), (rsx, rsy) = shoulders
    pose = np.full((t, NUM_POSE_LANDMARKS, 4), np.nan, np.float32)
    hands = np.full((t, NUM_HANDS, NUM_HAND_LANDMARKS, 3), np.nan, np.float32)
    ctr = ((lsx + rsx) / 2, (lsy + rsy) / 2)
    for i in range(t):
        pose[i, LEFT_SHOULDER, :2] = (lsx, lsy)
        pose[i, RIGHT_SHOULDER, :2] = (rsx, rsy)
        # wrists: active one oscillates, other still
        la = 0.05 * (i % 2) if left_active else 0.0
        ra = 0.0 if left_active else 0.05 * (i % 2)
        pose[i, LEFT_WRIST, :2] = (ctr[0] - 0.1 + la, ctr[1] + 0.2)
        pose[i, RIGHT_WRIST, :2] = (ctr[0] + 0.1 + ra, ctr[1] + 0.2)
    pose[:, :, 2] = 0.0  # z
    pose[:, :, 3] = 1.0  # visibility
    return hands, pose


# --- N1 scale + centering -----------------------------------------------------------------


def test_n1_scale_normalizes_shoulder_width_to_one() -> None:
    cfg = load_config(CONFIG_PATH)
    hands, pose = _clip(6, ((0.4, 0.3), (0.7, 0.3)))  # width 0.3
    _, pose_n, params = normalize_clip(hands, pose, 0, 5, cfg)
    assert params.scale == pytest.approx(0.3, abs=1e-5)
    assert clip_scale(pose_n) == pytest.approx(1.0, abs=1e-5)  # width -> 1
    # torso center mapped to origin
    mid = (pose_n[:, LEFT_SHOULDER, :2] + pose_n[:, RIGHT_SHOULDER, :2]) / 2
    assert np.allclose(mid, 0.0, atol=1e-5)


# --- N2 roll ------------------------------------------------------------------------------


def test_n2_roll_removes_shoulder_tilt() -> None:
    cfg = load_config(CONFIG_PATH)
    hands, pose = _clip(6, ((0.4, 0.35), (0.7, 0.25)))  # tilted shoulder line
    raw_angle = abs(math.degrees(_shoulder_angle(pose)))
    assert raw_angle > 5  # genuinely tilted
    _, pose_n, _ = normalize_clip(hands, pose, 0, 5, cfg)
    assert abs(math.degrees(_shoulder_angle(pose_n))) < 1e-3  # flattened


# --- N3 handedness ------------------------------------------------------------------------


def test_decide_handedness_left_dominant_mirrors() -> None:
    _, pose = _clip(8, ((0.4, 0.3), (0.7, 0.3)), left_active=True)
    hd = decide_handedness(pose, 0, 7, epsilon=0.15)
    assert hd.dominant == "Left" and hd.mirrored


def test_decide_handedness_symmetric_no_mirror() -> None:
    _, pose = _clip(8, ((0.4, 0.3), (0.7, 0.3)))  # neither wrist active -> symmetric
    hd = decide_handedness(pose, 0, 7, epsilon=0.15)
    assert not hd.mirrored


def test_n3_canonicalizes_left_dominant_to_right() -> None:
    cfg = load_config(CONFIG_PATH)
    hands, pose = _clip(8, ((0.4, 0.3), (0.7, 0.3)), left_active=True)
    _, pose_n, params = normalize_clip(hands, pose, 0, 7, cfg)
    assert params.mirrored
    # after mirroring, the dominant side is now RIGHT (canonical) -> no further mirror
    assert not decide_handedness(pose_n, 0, 7, cfg.handedness_epsilon).mirrored


def test_pose_mirror_perm_is_an_involution() -> None:
    perm = pose_mirror_perm()
    assert [perm[perm[i]] for i in range(33)] == list(range(33))  # swapping twice = identity
    assert perm[LEFT_SHOULDER] == RIGHT_SHOULDER and perm[0] == 0  # nose stays


# --- flags / shapes -----------------------------------------------------------------------


def test_all_flags_off_is_identity() -> None:
    import dataclasses

    cfg = dataclasses.replace(
        load_config(CONFIG_PATH), n1_scale=False, n2_roll=False, n3_handedness=False
    )
    hands, pose = _clip(5, ((0.4, 0.3), (0.7, 0.3)))
    hands_n, pose_n, _ = normalize_clip(hands, pose, 0, 4, cfg)
    assert np.allclose(np.nan_to_num(pose_n), np.nan_to_num(pose))
    assert pose_n.shape == pose.shape and hands_n.shape == hands.shape


def test_visibility_channel_preserved() -> None:
    cfg = load_config(CONFIG_PATH)
    hands, pose = _clip(5, ((0.4, 0.3), (0.7, 0.3)))
    _, pose_n, _ = normalize_clip(hands, pose, 0, 4, cfg)
    assert np.allclose(pose_n[:, :, 3], 1.0)  # visibility untouched by geometry


def test_params_hash_changes_with_flags() -> None:
    import dataclasses

    cfg = load_config(CONFIG_PATH)
    assert dataclasses.replace(cfg, n2_roll=not cfg.n2_roll).params_hash != cfg.params_hash
