"""Q quality gate — pure per-clip accept/reject with itemized reasons. Advisory: the decision
is recorded, never destructive. Each failed gate contributes a reason string so the
dataset-health report can attribute rejections."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import QualityConfig


@dataclass
class QualityResult:
    accept: bool
    reasons: list[str] = field(default_factory=list)  # empty when accepted
    coverage: float = float("nan")
    confidence: float = float("nan")
    n_span: int = 0


def evaluate_quality(
    hand_score: np.ndarray,
    pose_score: np.ndarray,
    onset: int,
    release: int,
    valid_span: bool,
    native_fps: float,
    cfg: QualityConfig,
) -> QualityResult:
    """hand_score (T,2), pose_score (T,). Gates evaluated over the span [onset, release]."""
    reasons: list[str] = []

    if not valid_span or onset < 0:
        # No usable span — report the span reasons and skip the frame-based gates.
        return QualityResult(accept=False, reasons=["invalid_span"], n_span=0)

    span_hand = hand_score[onset : release + 1]
    span_pose = pose_score[onset : release + 1]
    n_span = release - onset + 1
    coverage = float(np.mean(np.any(span_hand > 0.0, axis=1))) if n_span else 0.0
    confidence = float(np.nanmean(span_pose)) if n_span else 0.0

    if n_span < cfg.min_span_frames:
        reasons.append(f"span_too_short({n_span}<{cfg.min_span_frames})")
    if coverage < cfg.min_coverage:
        reasons.append(f"low_coverage({coverage:.2f}<{cfg.min_coverage})")
    if confidence < cfg.min_confidence:
        reasons.append(f"low_confidence({confidence:.2f}<{cfg.min_confidence})")
    if native_fps < cfg.min_fps:
        reasons.append(f"low_fps({native_fps:.1f}<{cfg.min_fps})")

    return QualityResult(
        accept=not reasons,
        reasons=reasons,
        coverage=coverage,
        confidence=confidence,
        n_span=n_span,
    )
