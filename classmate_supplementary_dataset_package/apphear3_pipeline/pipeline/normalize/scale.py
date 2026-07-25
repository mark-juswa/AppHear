"""Body-scale reference — shoulder width in image-normalized units.

Shared by D1 signing detection (feature 02, for distance-invariant motion thresholds) and by
N1 scale normalization (feature 03). Kept in one place so the two can never drift apart
(train/serve parity starts here). See context/docs/02-data-pipeline.md § N1."""

from __future__ import annotations

import numpy as np

from ..topology import LEFT_HIP, LEFT_SHOULDER, RIGHT_HIP, RIGHT_SHOULDER


def shoulder_width_frame(pose_xy: np.ndarray) -> float:
    """Shoulder width for a single frame. ``pose_xy`` is (33, >=2) image coords. Returns NaN
    if either shoulder is missing."""
    ls = pose_xy[LEFT_SHOULDER, :2]
    rs = pose_xy[RIGHT_SHOULDER, :2]
    if np.isnan(ls).any() or np.isnan(rs).any():
        return float("nan")
    return float(np.linalg.norm(ls - rs))


def _torso_length_frame(pose_xy: np.ndarray) -> float:
    """Shoulder-centre → hip-centre distance (fallback scale when a shoulder is occluded)."""
    ls, rs = pose_xy[LEFT_SHOULDER, :2], pose_xy[RIGHT_SHOULDER, :2]
    lh, rh = pose_xy[LEFT_HIP, :2], pose_xy[RIGHT_HIP, :2]
    if np.isnan(np.stack([ls, rs, lh, rh])).any():
        return float("nan")
    return float(np.linalg.norm((ls + rs) / 2.0 - (lh + rh) / 2.0))


def clip_scale(pose_image: np.ndarray) -> float:
    """Robust per-clip body scale = median shoulder width over frames, falling back to median
    torso length, then to 1.0 (no-op) if the pose is unusable. ``pose_image`` is (T, 33, >=2).

    A single scalar per clip is used (not per-frame) because the signer's size doesn't change
    within a clip and a jittery per-frame divisor would inject noise (docs/02 § N1)."""
    if pose_image.shape[0] == 0:
        return 1.0
    widths = np.array([shoulder_width_frame(pose_image[t]) for t in range(pose_image.shape[0])])
    w = float(np.nanmedian(widths)) if not np.all(np.isnan(widths)) else float("nan")
    if np.isnan(w) or w <= 0.0:
        torsos = np.array([_torso_length_frame(pose_image[t]) for t in range(pose_image.shape[0])])
        w = float(np.nanmedian(torsos)) if not np.all(np.isnan(torsos)) else float("nan")
    if np.isnan(w) or w <= 0.0:
        return 1.0
    return w
