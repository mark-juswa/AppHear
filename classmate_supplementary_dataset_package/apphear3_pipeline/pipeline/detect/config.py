"""Typed loader for detect.yaml + deterministic params hashing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DetectConfig:
    detect_version: str
    enabled: bool
    input_root: Path
    output_root: Path
    smoothing_window: int
    pose_landmarks: tuple[str, ...]
    hand_aux_weight: float
    raise_margin: float
    theta_on: float
    theta_off: float
    k_on: int
    k_off: int
    backoff: int
    min_span_frames: int

    def __post_init__(self) -> None:
        if not self.theta_off < self.theta_on:
            raise ValueError(f"theta_off ({self.theta_off}) must be < theta_on ({self.theta_on})")

    @property
    def params_hash(self) -> str:
        payload = {
            "detect_version": self.detect_version,
            "smoothing_window": self.smoothing_window,
            "pose_landmarks": list(self.pose_landmarks),
            "hand_aux_weight": self.hand_aux_weight,
            "raise_margin": self.raise_margin,
            "theta_on": self.theta_on,
            "theta_off": self.theta_off,
            "k_on": self.k_on,
            "k_off": self.k_off,
            "backoff": self.backoff,
            "min_span_frames": self.min_span_frames,
        }
        blob = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:12]


def load_config(path: str | Path) -> DetectConfig:
    with Path(path).open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)
    return DetectConfig(
        detect_version=str(raw["detect_version"]),
        enabled=bool(raw["enabled"]),
        input_root=Path(raw["input_root"]),
        output_root=Path(raw["output_root"]),
        smoothing_window=int(raw["smoothing_window"]),
        pose_landmarks=tuple(raw["motion"]["pose_landmarks"]),
        hand_aux_weight=float(raw["motion"]["hand_aux_weight"]),
        raise_margin=float(raw["gate"]["raise_margin"]),
        theta_on=float(raw["hysteresis"]["theta_on"]),
        theta_off=float(raw["hysteresis"]["theta_off"]),
        k_on=int(raw["hysteresis"]["k_on"]),
        k_off=int(raw["hysteresis"]["k_off"]),
        backoff=int(raw["span"]["backoff"]),
        min_span_frames=int(raw["span"]["min_span_frames"]),
    )
