"""Fixed landmark topology constants. These are properties of the MediaPipe models and the
AppHear feature contract — never make them configurable."""

from __future__ import annotations

import numpy as np

NUM_POSE_LANDMARKS: int = 33
NUM_HAND_LANDMARKS: int = 21
NUM_HANDS: int = 2  # two canonical slots: index 0 = Left, index 1 = Right

# Missing landmarks are stored as NaN (never a bare 0, which looks like the origin).
# See context/feature-schema.md § Missing-Data Convention.
MISSING: float = np.nan

# Canonical hand slot order by MediaPipe handedness label.
HAND_SLOTS: tuple[str, str] = ("Left", "Right")

# Extraction runs MediaPipe in IMAGE mode: stateless per-frame detection, no internal temporal
# tracking. Rationale: per-clip isolation + determinism, and it keeps tracking/smoothing an
# explicit stage (S3) that can be replicated identically offline and on-device (train/serve
# parity) rather than baked into MediaPipe's hidden VIDEO state. Part of the config hash.
RUNNING_MODE: str = "IMAGE"
