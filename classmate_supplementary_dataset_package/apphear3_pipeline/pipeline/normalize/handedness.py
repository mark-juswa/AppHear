"""N3 dominant-hand decision. Dominant hand = the one whose POSE WRIST moves more over the
span (pose is present ~100% of frames, so this is robust even when hand landmarks drop).
Canonical convention: the dominant hand ends up on the RIGHT, so LEFT-dominant signers are
mirrored. Near-symmetric two-handed signs (motion within handedness_epsilon) are not mirrored."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..topology import LEFT_WRIST, RIGHT_WRIST


@dataclass(frozen=True)
class HandednessDecision:
    dominant: str  # "Left" | "Right"
    mirrored: bool  # True if the clip must be mirrored to canonicalize


def _wrist_motion(pose_span_xy: np.ndarray) -> float:
    """Total frame-to-frame wrist displacement over the span (NaN-safe)."""
    if pose_span_xy.shape[0] < 2:
        return 0.0
    d = np.linalg.norm(pose_span_xy[1:] - pose_span_xy[:-1], axis=1)
    return float(np.nansum(d))


def decide_handedness(
    pose_image: np.ndarray, onset: int, release: int, epsilon: float
) -> HandednessDecision:
    span = pose_image[onset : release + 1]
    left = _wrist_motion(span[:, LEFT_WRIST, :2])
    right = _wrist_motion(span[:, RIGHT_WRIST, :2])
    total = left + right
    if total <= 0.0 or abs(left - right) / total < epsilon:
        # symmetric or no motion — canonical default, no mirror
        return HandednessDecision(dominant="Right", mirrored=False)
    dominant = "Left" if left > right else "Right"
    return HandednessDecision(dominant=dominant, mirrored=(dominant == "Left"))
