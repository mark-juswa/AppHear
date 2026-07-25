"""D1 signals: per-frame motion energy + a "hands raised" signing-space gate.

Primary signal is pose-derived (wrists/elbows — present in ~100% of frames, robust across
signers). Hand-landmark motion is an ADDITIVE auxiliary that sharpens the signal when hands
are detected but is never required (NaN hands contribute 0). All motion is in shoulder-width
units per frame so thresholds are signer/distance invariant."""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np

from ..extract.schema import ClipLandmarks
from ..normalize.scale import clip_scale
from ..topology import HIPS, LEFT_WRIST, POSE_NAME_TO_INDEX, RIGHT_WRIST

HAND_WRIST_LANDMARK = 0  # index 0 of the 21 hand landmarks is the wrist


@dataclass
class Signals:
    motion: np.ndarray  # (T,) float64 — smoothed, shoulder-width units per frame
    gate: np.ndarray  # (T,) bool — at least one wrist raised into signing space
    scale: float  # per-clip shoulder width used for normalization


def _pose_motion(pose_xy: np.ndarray, scale: float) -> np.ndarray:
    """pose_xy: (T, K, 2) selected pose landmarks. Mean per-frame displacement / scale."""
    t = pose_xy.shape[0]
    motion = np.zeros(t, dtype=np.float64)
    if t < 2:
        return motion
    dist = np.linalg.norm(pose_xy[1:] - pose_xy[:-1], axis=2)  # (T-1, K), NaN where missing
    per = np.nan_to_num(np.nanmean(_nan_rows_ok(dist), axis=1), nan=0.0)
    motion[1:] = per / scale
    return motion


def _hand_motion(hand_wrist_xy: np.ndarray, scale: float) -> np.ndarray:
    """hand_wrist_xy: (T, 2, 2) wrist xy per hand slot. 0 where hands absent."""
    t = hand_wrist_xy.shape[0]
    motion = np.zeros(t, dtype=np.float64)
    if t < 2:
        return motion
    dist = np.linalg.norm(hand_wrist_xy[1:] - hand_wrist_xy[:-1], axis=2)  # (T-1, 2)
    per = np.nan_to_num(np.nanmean(_nan_rows_ok(dist), axis=1), nan=0.0)
    motion[1:] = per / scale
    return motion


def _nan_rows_ok(x: np.ndarray) -> np.ndarray:
    """Replace all-NaN rows with NaN-safe zeros so nanmean doesn't warn on empty slices."""
    all_nan = np.all(np.isnan(x), axis=1)
    out = x.copy()
    out[all_nan] = 0.0
    return out


def _smooth(x: np.ndarray, window: int) -> np.ndarray:
    if window <= 1 or x.shape[0] == 0:
        return x
    kernel = np.ones(window, dtype=np.float64) / window
    return np.convolve(x, kernel, mode="same")


def _raised_gate(pose_image: np.ndarray, scale: float, raise_margin: float) -> np.ndarray:
    """A wrist is 'raised' when its y is above the hip line by raise_margin shoulder-widths
    (image y grows downward, so raised = smaller y). Gate = either wrist raised. If hips are
    missing the gate defaults open (never blocks detection)."""
    t = pose_image.shape[0]
    if t == 0:
        return np.zeros(0, dtype=bool)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN hips -> NaN threshold (handled)
        hip_y = np.nanmean(pose_image[:, HIPS, 1], axis=1)  # (T,)
    threshold = hip_y - raise_margin * scale
    lw_y = pose_image[:, LEFT_WRIST, 1]
    rw_y = pose_image[:, RIGHT_WRIST, 1]
    raised = (lw_y < threshold) | (rw_y < threshold)
    return np.where(np.isnan(threshold), True, raised).astype(bool)


def compute_signals(
    clip: ClipLandmarks,
    pose_landmark_names: tuple[str, ...],
    hand_aux_weight: float,
    raise_margin: float,
    smoothing_window: int,
) -> Signals:
    scale = clip_scale(clip.pose_image)
    idx = [POSE_NAME_TO_INDEX[name] for name in pose_landmark_names]
    pose_xy = clip.pose_image[:, idx, :2]
    hand_wrist_xy = clip.hands_image[:, :, HAND_WRIST_LANDMARK, :2]  # (T, 2, 2)

    motion = _pose_motion(pose_xy, scale) + hand_aux_weight * _hand_motion(hand_wrist_xy, scale)
    motion = _smooth(motion, smoothing_window)
    gate = _raised_gate(clip.pose_image, scale, raise_margin)
    return Signals(motion=motion, gate=gate, scale=scale)
