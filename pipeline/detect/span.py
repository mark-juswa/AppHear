"""D2: turn per-frame signals into a signing span [onset, release] via hysteresis.

Enter 'signing' when motion exceeds theta_on AND the gate is open, sustained k_on frames.
Leave when motion drops below theta_off for k_off frames. The longest contiguous signing run
is taken as the span (robust for isolated citation-form clips), then extended by `backoff`
frames on each side to catch the movement onset that precedes the threshold crossing. Runs
shorter than min_span_frames are flagged invalid (quality-gate candidates, feature 04)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import DetectConfig
from .signals import Signals


@dataclass
class Span:
    onset: int  # first frame (inclusive); -1 if none
    release: int  # last frame (inclusive); -1 if none
    valid: bool
    reason: str
    n_signing_frames: int  # frames in the detected run (before backoff)


def _hysteresis(motion: np.ndarray, gate: np.ndarray, cfg: DetectConfig) -> np.ndarray:
    """Boolean per-frame signing mask."""
    t = motion.shape[0]
    signing = np.zeros(t, dtype=bool)
    state_signing = False
    on_count = 0
    off_count = 0
    for i in range(t):
        if not state_signing:
            if motion[i] > cfg.theta_on and gate[i]:
                on_count += 1
                if on_count >= cfg.k_on:
                    state_signing = True
                    signing[i - cfg.k_on + 1 : i + 1] = True
                    off_count = 0
            else:
                on_count = 0
        else:
            signing[i] = True
            if motion[i] < cfg.theta_off:
                off_count += 1
                if off_count >= cfg.k_off:
                    state_signing = False
                    signing[i - cfg.k_off + 1 : i + 1] = False  # trailing low-motion frames
                    on_count = 0
            else:
                off_count = 0
    return signing


def _longest_run(mask: np.ndarray) -> tuple[int, int, int]:
    """(start, end_inclusive, length) of the longest True run; (-1, -1, 0) if none."""
    best_start = best_end = -1
    best_len = 0
    run_start = -1
    for i, on in enumerate(mask):
        if on and run_start == -1:
            run_start = i
        if (not on or i == len(mask) - 1) and run_start != -1:
            run_end = i if on else i - 1
            length = run_end - run_start + 1
            if length > best_len:
                best_start, best_end, best_len = run_start, run_end, length
            run_start = -1
    return best_start, best_end, best_len


def detect_span(signals: Signals, cfg: DetectConfig) -> Span:
    t = signals.motion.shape[0]
    if t == 0:
        return Span(-1, -1, False, "empty_clip", 0)

    mask = _hysteresis(signals.motion, signals.gate, cfg)
    start, end, length = _longest_run(mask)
    if length == 0:
        return Span(-1, -1, False, "no_signing_detected", 0)

    onset = max(0, start - cfg.backoff)
    release = min(t - 1, end + cfg.backoff)
    valid = length >= cfg.min_span_frames
    reason = "" if valid else f"span_too_short({length}<{cfg.min_span_frames})"
    return Span(onset=onset, release=release, valid=valid, reason=reason, n_signing_frames=length)
