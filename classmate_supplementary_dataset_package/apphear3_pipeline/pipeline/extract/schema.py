"""On-disk schema for stage E: per-clip landmark arrays (.npz) + metadata sidecar (.json).

Stage E stores RAW MediaPipe landmarks only — no trimming, no normalization. Downstream
stages (D1/D2, N1-N4, Q, F) consume these. See context/feature-schema.md."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .constants import NUM_HAND_LANDMARKS, NUM_HANDS, NUM_POSE_LANDMARKS

ARRAY_KEYS = (
    "hands_image",  # (T, 2, 21, 3) float32  — normalized image coords (x,y,z), NaN if absent
    "hands_world",  # (T, 2, 21, 3) float32  — metric world coords (x,y,z), NaN if absent
    "hand_score",  # (T, 2)        float32  — detection score per slot (0 if absent)
    "pose_image",  # (T, 33, 4)    float32  — image coords + visibility (x,y,z,vis)
    "pose_world",  # (T, 33, 3)    float32  — metric world coords (x,y,z)
    "pose_score",  # (T,)          float32  — pose presence (0 if absent)
    "timestamps_ms",  # (T,)       int64
)


@dataclass
class ClipLandmarks:
    """Raw per-frame landmark arrays for one clip. Index 0 = Left hand, 1 = Right hand."""

    hands_image: np.ndarray
    hands_world: np.ndarray
    hand_score: np.ndarray
    pose_image: np.ndarray
    pose_world: np.ndarray
    pose_score: np.ndarray
    timestamps_ms: np.ndarray

    def validate(self) -> None:
        t = self.timestamps_ms.shape[0]
        expected = {
            "hands_image": (t, NUM_HANDS, NUM_HAND_LANDMARKS, 3),
            "hands_world": (t, NUM_HANDS, NUM_HAND_LANDMARKS, 3),
            "hand_score": (t, NUM_HANDS),
            "pose_image": (t, NUM_POSE_LANDMARKS, 4),
            "pose_world": (t, NUM_POSE_LANDMARKS, 3),
            "pose_score": (t,),
            "timestamps_ms": (t,),
        }
        for key, shape in expected.items():
            arr = getattr(self, key)
            if arr.shape != shape:
                raise ValueError(f"{key}: expected shape {shape}, got {arr.shape}")

    def save(self, path: Path) -> None:
        self.validate()
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **{k: getattr(self, k) for k in ARRAY_KEYS})

    @classmethod
    def load(cls, path: Path) -> ClipLandmarks:
        with np.load(path) as data:
            return cls(**{k: data[k] for k in ARRAY_KEYS})


@dataclass
class ClipSidecar:
    """Per-clip metadata. Field lineage documented in context/feature-schema.md § sidecar."""

    schema_stage: str  # "E" — raw landmarks (not yet a feature-vector schema_version)
    extraction_version: str
    model_config_hash: str
    mediapipe_version: str

    source: str  # "asl_citizen"
    split: str  # "train" | "val" | "test"
    participant_id: str  # == signer_id (required for signer-level splits)
    gloss: str
    asl_lex_code: str
    video_file: str

    native_fps: float
    n_frames: int
    frame_width: int
    frame_height: int

    hand_hit_rate: float  # frac frames with >=1 hand detected
    two_hand_hit_rate: float  # frac frames with both hands detected
    pose_hit_rate: float  # frac frames with a pose detected

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2)

    @classmethod
    def load(cls, path: Path) -> ClipSidecar:
        with path.open("r", encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)
        return cls(**data)
