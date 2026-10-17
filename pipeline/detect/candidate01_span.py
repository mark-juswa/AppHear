"""D1 signing span on Candidate01 raw-v1 (port of signals.py for the current perception contract).

The governed recognizer population was cut with d1 spans computed from Stage-E MediaPipe
landmarks. New sources (e.g. Sem-Lex) only have Candidate01 raw-v1, so this computes the same d1
signals from it -- wrist/elbow motion in shoulder-width units, an additive accepted-hand wrist term,
a "wrist raised above the hip line" gate -- and reuses the unchanged hysteresis/longest-run rule
(`span.detect_span`). Coordinates are Candidate01 pixel coordinates (aspect-consistent), so a
single dimensionless `theta_scale` may be needed to align with the MediaPipe-normalized originals;
it is fitted on recognizer-TRAIN clips and validated on signer-disjoint DEV, never on test data.
"""

from __future__ import annotations

import warnings
from dataclasses import replace

import numpy as np

from pipeline.perception_vnext.recognition_schema import RawSequence

from .config import DetectConfig
from .signals import Signals, _hand_motion, _pose_motion, _smooth
from .span import Span, detect_span

# Candidate01 body slots: COCO 5..12 = L/R shoulder, L/R elbow, L/R wrist, L/R hip
L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST, L_HIP, R_HIP = range(8)
MOTION_POINTS = (L_WRIST, R_WRIST, L_ELBOW, R_ELBOW)


def candidate01_signals(raw: RawSequence, cfg: DetectConfig) -> Signals:
    body = np.asarray(raw.body_xy, np.float64).copy()
    body[~np.asarray(raw.body_valid, bool)] = np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        widths = np.linalg.norm(body[:, L_SHOULDER] - body[:, R_SHOULDER], axis=-1)
        scale = float(np.nanmedian(widths)) if np.any(np.isfinite(widths)) else float("nan")
    if not np.isfinite(scale) or scale <= 0.0:
        scale = float(np.max(raw.source_size[0])) * 0.25  # same order as a shoulder width
    wrists = np.asarray(raw.hand_xy, np.float64)[:, :, 0, :].copy()
    wrists[~np.asarray(raw.hand_observed, bool)] = np.nan
    motion = _pose_motion(body[:, list(MOTION_POINTS)], scale) + cfg.hand_aux_weight * _hand_motion(
        wrists, scale
    )
    motion = _smooth(motion, cfg.smoothing_window)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        hip_y = np.nanmean(body[:, [L_HIP, R_HIP], 1], axis=1)
    threshold = hip_y - cfg.raise_margin * scale
    raised = (body[:, L_WRIST, 1] < threshold) | (body[:, R_WRIST, 1] < threshold)
    gate = np.where(np.isnan(threshold), True, raised).astype(bool)
    return Signals(motion=motion, gate=gate, scale=scale)


def candidate01_span(raw: RawSequence, cfg: DetectConfig, theta_scale: float = 1.0) -> Span:
    scaled = replace(
        cfg, theta_on=cfg.theta_on * theta_scale, theta_off=cfg.theta_off * theta_scale
    )
    return detect_span(candidate01_signals(raw, scaled), scaled)
