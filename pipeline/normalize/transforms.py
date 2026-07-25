"""N1/N2/N3 geometric transforms → canonical space.

Order: center (per-frame, to torso) -> scale (per-clip shoulder width) -> roll (per-clip
shoulder angle) -> mirror (handedness). Operates on image-space x,y,z; pose visibility and
hand z-origin caveats are documented inline. PURE + deterministic — this is the exact math
Android S4 will port (train/serve parity), so no hidden state, no data-dependent branches
beyond the recorded params."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..topology import LEFT_SHOULDER, RIGHT_SHOULDER, pose_mirror_perm
from .config import NormalizeConfig
from .handedness import decide_handedness
from .scale import clip_scale

_MIRROR_PERM = pose_mirror_perm()


@dataclass(frozen=True)
class NormParams:
    scale: float
    roll_angle: float  # radians (shoulder-line angle removed)
    dominant: str
    mirrored: bool


def _torso_center_xy(pose_image: np.ndarray) -> np.ndarray:
    """(T, 2) per-frame torso center = shoulder midpoint, with span-median fallback for frames
    where a shoulder is missing."""
    center = np.nanmean(pose_image[:, [LEFT_SHOULDER, RIGHT_SHOULDER], :2], axis=1)  # (T, 2)
    if np.isnan(center).any():
        med = np.nanmedian(center, axis=0)
        med = np.where(np.isnan(med), 0.0, med)
        center[np.isnan(center).any(axis=1)] = med
    out: np.ndarray = center.astype(np.float32)
    return out


def _shoulder_angle(pose_span: np.ndarray) -> float:
    """Shoulder-LINE tilt in radians, folded to (-pi/2, pi/2]. We want how far the line is from
    horizontal, NOT the L->R vector direction: the camera mirrors the view, so a front-facing
    signer's right shoulder sits at smaller x (vector ~180 deg) while the line is still level.
    Median is taken over the vector components (wrap-around safe), then folded."""
    ls = pose_span[:, LEFT_SHOULDER, :2]
    rs = pose_span[:, RIGHT_SHOULDER, :2]
    d = rs - ls
    mdx = np.nanmedian(d[:, 0])
    mdy = np.nanmedian(d[:, 1])
    if np.isnan(mdx) or np.isnan(mdy):
        return 0.0
    ang = math.atan2(mdy, mdx)
    if ang > math.pi / 2:
        ang -= math.pi
    elif ang <= -math.pi / 2:
        ang += math.pi
    return ang


def _transform_block(
    coords: np.ndarray,
    center: np.ndarray,
    s: float,
    theta: float,
    do_center: bool,
    do_scale: bool,
    do_roll: bool,
) -> np.ndarray:
    """coords: (T, K, C>=3) with xy=cols 0:2, z=col 2, rest passthrough. center: (T, 2)."""
    out = coords.astype(np.float32).copy()
    if do_center:
        out[..., :2] -= center[:, None, :]
    if do_scale and s > 0:
        out[..., :3] /= s
    if do_roll:
        c, sn = math.cos(-theta), math.sin(-theta)
        x = out[..., 0].copy()
        y = out[..., 1].copy()
        out[..., 0] = c * x - sn * y
        out[..., 1] = sn * x + c * y
    return out


def normalize_clip(
    hands_image: np.ndarray,
    pose_image: np.ndarray,
    onset: int,
    release: int,
    cfg: NormalizeConfig,
) -> tuple[np.ndarray, np.ndarray, NormParams]:
    """Return (hands_norm (T,2,21,3), pose_norm (T,33,4), params). Params derived from the span
    [onset, release]; transforms applied to all frames. A -1 onset means 'use whole clip'."""
    t = pose_image.shape[0]
    if onset < 0:
        onset, release = 0, t - 1
    span_pose = pose_image[onset : release + 1]

    do_center = cfg.n1_scale or cfg.n2_roll or cfg.n3_handedness
    s = clip_scale(span_pose) if cfg.n1_scale else 1.0
    theta = _shoulder_angle(span_pose) if cfg.n2_roll else 0.0
    hd = (
        decide_handedness(pose_image, onset, release, cfg.handedness_epsilon)
        if cfg.n3_handedness
        else None
    )
    mirrored = bool(hd.mirrored) if hd else False
    center = _torso_center_xy(pose_image) if do_center else np.zeros((t, 2), np.float32)

    pose_out = _transform_block(pose_image, center, s, theta, do_center, cfg.n1_scale, cfg.n2_roll)
    hands_flat = hands_image.reshape(t, -1, 3)  # (T, 42, 3)
    hands_out = _transform_block(
        hands_flat, center, s, theta, do_center, cfg.n1_scale, cfg.n2_roll
    ).reshape(t, 2, 21, 3)

    if mirrored:
        pose_out[..., 0] *= -1.0
        hands_out[..., 0] *= -1.0
        pose_out = pose_out[:, _MIRROR_PERM, :]
        hands_out = hands_out[:, ::-1, :, :]

    params = NormParams(
        scale=s,
        roll_angle=theta,
        dominant=hd.dominant if hd else "Right",
        mirrored=mirrored,
    )
    return hands_out.astype(np.float32), pose_out.astype(np.float32), params
