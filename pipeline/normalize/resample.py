"""N4 duration normalization: resample a span's landmark trajectories to a fixed length T by
per-channel LINEAR interpolation over normalized time [0, 1].

Isolated-path / training-only (OFF in streaming/CTC — the model then handles real timing).
Linear is chosen for robustness (no overshoot) and easy exact porting. NaN gaps are
interpolated across when endpoints exist, else left NaN."""

from __future__ import annotations

import numpy as np


def resample_block(arr: np.ndarray, target_len: int) -> np.ndarray:
    """(n, K, C) -> (target_len, K, C). Per-channel NaN-safe linear interpolation."""
    n, k, c = arr.shape
    if target_len <= 0:
        raise ValueError(f"target_len must be positive, got {target_len}")
    if n == 0:
        return np.full((target_len, k, c), np.nan, dtype=np.float32)
    if n == 1:
        return np.repeat(arr.astype(np.float32), target_len, axis=0)

    src = np.linspace(0.0, 1.0, n)
    dst = np.linspace(0.0, 1.0, target_len)
    flat = arr.reshape(n, k * c).astype(np.float64)
    out = np.empty((target_len, k * c), dtype=np.float32)
    for col in range(k * c):
        series = flat[:, col]
        mask = ~np.isnan(series)
        valid = int(mask.sum())
        if valid >= 2:
            out[:, col] = np.interp(dst, src[mask], series[mask])
        elif valid == 1:
            out[:, col] = series[mask][0]
        else:
            out[:, col] = np.nan
    return out.reshape(target_len, k, c)


def resample_clip(
    hands_norm: np.ndarray,
    pose_norm: np.ndarray,
    onset: int,
    release: int,
    target_len: int,
    method: str = "linear",
) -> tuple[np.ndarray, np.ndarray]:
    """Resample the span [onset, release] to (target_len, ...). A -1 onset means whole clip."""
    if method != "linear":
        raise ValueError(f"unsupported resample method: {method!r} (only 'linear')")
    t = pose_norm.shape[0]
    if onset < 0:
        onset, release = 0, t - 1
    span_h = hands_norm[onset : release + 1].reshape(release - onset + 1, -1, 3)  # (n,42,3)
    span_p = pose_norm[onset : release + 1]  # (n,33,4)
    hands_t = resample_block(span_h, target_len).reshape(target_len, 2, 21, 3)
    pose_t = resample_block(span_p, target_len)
    return hands_t, pose_t
