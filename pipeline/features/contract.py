"""The versioned feature contract (v3.0 "normalized 258") and the exact composition that
produces it. `clip_features` is THE math Android S4 must replicate byte-for-byte (train/serve
parity), so it is pure and deterministic. See context/feature-schema.md.

Layout per frame (258 floats): [hand_L 21x3, hand_R 21x3, pose 33x4(x,y,z,visibility)]
                                = 126 + 132 = 258.
Missing hands are imputed NaN->0 inside the vector; a separate (T,2) presence mask records
which hand slots were actually present (aux, NOT part of the 258 contract)."""

from __future__ import annotations

import numpy as np

from ..normalize.causal import CausalConfig, mirror_flip_summary, normalize_clip_causal
from ..normalize.config import NormalizeConfig
from ..normalize.resample import resample_clip
from ..normalize.transforms import NormParams, normalize_clip

SCHEMA_VERSION = "3.0"
HANDS_DIM = 2 * 21 * 3  # 126
POSE_DIM = 33 * 4  # 132
FEATURE_DIM = HANDS_DIM + POSE_DIM  # 258


def build_feature_vector(hands_t: np.ndarray, pose_t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(T,2,21,3)+(T,33,4) -> (feature (T,258) f32, presence mask (T,2) f32).

    Mask is computed BEFORE NaN->0 imputation: a hand slot is 'present' in a frame when its
    block is not entirely NaN."""
    t = hands_t.shape[0]
    hands_flat = hands_t.reshape(t, HANDS_DIM)
    pose_flat = pose_t.reshape(t, POSE_DIM)
    feature = np.concatenate([hands_flat, pose_flat], axis=1)  # (T, 258)

    mask_l = ~np.all(np.isnan(hands_t[:, 0]), axis=(1, 2))
    mask_r = ~np.all(np.isnan(hands_t[:, 1]), axis=(1, 2))
    mask = np.stack([mask_l, mask_r], axis=1).astype(np.float32)

    feature = np.nan_to_num(feature, nan=0.0).astype(np.float32)
    return feature, mask


def clip_features(
    hands_image: np.ndarray,
    pose_image: np.ndarray,
    onset: int,
    release: int,
    ncfg: NormalizeConfig,
    resample_t: int,
) -> tuple[np.ndarray, np.ndarray, NormParams]:
    """Full stage-F composition: N1-N3 (normalize) -> N4 (resample) -> 258 vector + mask.
    Returns (feature (resample_t,258), mask (resample_t,2), NormParams). This is the S4 parity
    target."""
    hands_n, pose_n, params = normalize_clip(hands_image, pose_image, onset, release, ncfg)
    hands_t, pose_t = resample_clip(hands_n, pose_n, onset, release, resample_t, "linear")
    feature, mask = build_feature_vector(hands_t, pose_t)
    return feature, mask, params


def clip_features_realtimed(
    hands_image: np.ndarray,
    pose_image: np.ndarray,
    onset: int,
    release: int,
    ncfg: NormalizeConfig,
    t_max: int,
) -> tuple[np.ndarray, np.ndarray, int, NormParams]:
    """Phase-1 streaming regime: N1-N3 normalize -> keep REAL timing (N4 OFF) -> 258 vector per
    real frame, post-padded to t_max. Returns (feature (t_max,258), frame_mask (t_max,) bool,
    length int, NormParams). Longer spans are tail-truncated (~0.7% at t_max=96)."""
    hands_n, pose_n, params = normalize_clip(hands_image, pose_image, onset, release, ncfg)
    if onset < 0:
        onset, release = 0, pose_n.shape[0] - 1
    hands_span = hands_n[onset : release + 1]
    pose_span = pose_n[onset : release + 1]
    feat, _ = build_feature_vector(hands_span, pose_span)  # (L, 258)

    length = min(feat.shape[0], t_max)
    out = np.zeros((t_max, FEATURE_DIM), dtype=np.float32)
    out[:length] = feat[:length]
    frame_mask = np.zeros((t_max,), dtype=bool)
    frame_mask[:length] = True
    return out, frame_mask, length, params


def clip_features_causal(
    hands_image: np.ndarray,
    pose_image: np.ndarray,
    onset: int,
    release: int,
    ncfg: NormalizeConfig,
    ccfg: CausalConfig,
    t_max: int,
) -> tuple[np.ndarray, np.ndarray, int, tuple[int, int]]:
    """Streaming/causal regime: same 258 layout as `clip_features_realtimed`, but each frame's
    scale/roll/mirror are estimated from PAST frames only (see normalize.causal). Returns
    (feature (t_max,258), frame_mask (t_max,) bool, length int, (mirror_flips, last_flip_frame)).
    Used to MEASURE causal skew vs the full-span reference before on-device recognition (F19)."""
    hands_n, pose_n, per_frame = normalize_clip_causal(
        hands_image, pose_image, onset, release, ncfg, ccfg
    )
    feat, _ = build_feature_vector(hands_n, pose_n)  # (L, 258)
    length = min(feat.shape[0], t_max)
    out = np.zeros((t_max, FEATURE_DIM), dtype=np.float32)
    out[:length] = feat[:length]
    frame_mask = np.zeros((t_max,), dtype=bool)
    frame_mask[:length] = True
    return out, frame_mask, length, mirror_flip_summary(per_frame)
