"""Train-time data augmentation for v3.0 feature tensors (T, 258).

Fights the thin-per-class overfitting (train 0.77 / val 0.33) by perturbing each clip with
small geometric + temporal noise the model must become invariant to. Layout-aware: geometry is
applied to landmark x,y,z only; pose visibility (every 4th pose channel) is left alone, and
absent hands (imputed to 0) are re-zeroed so augmentation never invents a hand where there was
none. Applied to TRAIN ONLY."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pipeline.features.contract import HANDS_DIM  # 126

_HAND_L = slice(0, 63)
_HAND_R = slice(63, 126)
_POSE = slice(HANDS_DIM, 258)


@dataclass(frozen=True)
class AugmentConfig:
    rotation_deg: float
    scale: float
    noise_std: float
    frame_mask_frac: float


def _geo(
    a: np.ndarray, cos: np.ndarray, sin: np.ndarray, s: np.ndarray, noise: np.ndarray
) -> np.ndarray:
    """a: (B,T,K,3). Scale xyz, rotate xy about origin, add Gaussian noise. cos/sin/s: (B,1,1)."""
    xy = a[..., :2] * s[..., None]  # (B,1,1,1) broadcasts over (B,T,K,2)
    z = a[..., 2:3] * s[..., None]
    x0, y0 = xy[..., 0], xy[..., 1]  # (B,T,K)
    xr = cos * x0 - sin * y0  # (B,1,1) broadcasts over (B,T,K)
    yr = sin * x0 + cos * y0
    out = np.concatenate([np.stack([xr, yr], axis=-1), z], axis=-1)
    result: np.ndarray = (out + noise).astype(np.float32)
    return result


def augment_batch(
    x: np.ndarray,
    cfg: AugmentConfig,
    rng: np.random.Generator,
    valid_frame_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Augment `(B,T,258)` while preserving explicitly padded streaming frames."""
    b, t, _ = x.shape
    if valid_frame_mask is not None and valid_frame_mask.shape != (b, t):
        raise ValueError(f"valid_frame_mask must have shape {(b, t)}, got {valid_frame_mask.shape}")
    out = x.copy()
    hl = out[:, :, _HAND_L].reshape(b, t, 21, 3)
    hr = out[:, :, _HAND_R].reshape(b, t, 21, 3)
    po = out[:, :, _POSE].reshape(b, t, 33, 4)

    absent_l = np.all(hl == 0.0, axis=(2, 3))  # (B,T) — hand slot was imputed-absent
    absent_r = np.all(hr == 0.0, axis=(2, 3))

    theta = np.radians(np.asarray(rng.uniform(-cfg.rotation_deg, cfg.rotation_deg, b), np.float32))
    cos = np.cos(theta).reshape(b, 1, 1)
    sin = np.sin(theta).reshape(b, 1, 1)
    s = np.asarray(rng.uniform(1 - cfg.scale, 1 + cfg.scale, b), np.float32).reshape(b, 1, 1)

    def noise(shape: tuple[int, ...]) -> np.ndarray:
        return rng.normal(0.0, cfg.noise_std, shape).astype(np.float32)

    hl = _geo(hl, cos, sin, s, noise(hl.shape))
    hr = _geo(hr, cos, sin, s, noise(hr.shape))
    pose_xyz = _geo(po[..., :3], cos, sin, s, noise((b, t, 33, 3)))
    po = np.concatenate([pose_xyz, po[..., 3:4]], axis=-1)  # visibility untouched

    hl[absent_l] = 0.0  # never invent an absent hand
    hr[absent_r] = 0.0

    out[:, :, _HAND_L] = hl.reshape(b, t, 63)
    out[:, :, _HAND_R] = hr.reshape(b, t, 63)
    out[:, :, _POSE] = po.reshape(b, t, 132)

    if cfg.frame_mask_frac > 0.0:  # temporal dropout: zero a fraction of frames per clip
        mask = rng.random((b, t)) < cfg.frame_mask_frac
        out[mask] = 0.0
    if valid_frame_mask is not None:
        out[~valid_frame_mask.astype(bool)] = 0.0
    return out
