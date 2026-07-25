"""Typed loader for normalize.yaml + deterministic params hashing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class NormalizeConfig:
    normalize_version: str
    n1_scale: bool
    n2_roll: bool
    n2_yaw: bool
    n3_handedness: bool
    handedness_epsilon: float
    input_root: Path
    spans_root: Path
    output_root: Path

    @property
    def params_hash(self) -> str:
        payload = {
            "normalize_version": self.normalize_version,
            "n1_scale": self.n1_scale,
            "n2_roll": self.n2_roll,
            "n2_yaw": self.n2_yaw,
            "n3_handedness": self.n3_handedness,
            "handedness_epsilon": self.handedness_epsilon,
        }
        blob = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:12]


def load_config(path: str | Path) -> NormalizeConfig:
    with Path(path).open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)
    return NormalizeConfig(
        normalize_version=str(raw["normalize_version"]),
        n1_scale=bool(raw["n1_scale"]),
        n2_roll=bool(raw["n2_roll"]),
        n2_yaw=bool(raw["n2_yaw"]),
        n3_handedness=bool(raw["n3_handedness"]),
        handedness_epsilon=float(raw["handedness_epsilon"]),
        input_root=Path(raw["input_root"]),
        spans_root=Path(raw["spans_root"]),
        output_root=Path(raw["output_root"]),
    )
