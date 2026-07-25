"""Typed loader for quality.yaml + deterministic params hashing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class QualityConfig:
    n4_resample: bool
    resample_T: int
    resample_method: str
    q_enabled: bool
    min_coverage: float
    min_confidence: float
    min_fps: float
    min_span_frames: int
    input_root: Path
    spans_root: Path
    output_root: Path

    @property
    def params_hash(self) -> str:
        payload = {
            "n4_resample": self.n4_resample,
            "resample_T": self.resample_T,
            "resample_method": self.resample_method,
            "q_enabled": self.q_enabled,
            "min_coverage": self.min_coverage,
            "min_confidence": self.min_confidence,
            "min_fps": self.min_fps,
            "min_span_frames": self.min_span_frames,
        }
        blob = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:12]


def load_config(path: str | Path) -> QualityConfig:
    with Path(path).open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)
    return QualityConfig(
        n4_resample=bool(raw["n4_resample"]),
        resample_T=int(raw["resample_T"]),
        resample_method=str(raw["resample_method"]),
        q_enabled=bool(raw["q_enabled"]),
        min_coverage=float(raw["min_coverage"]),
        min_confidence=float(raw["min_confidence"]),
        min_fps=float(raw["min_fps"]),
        min_span_frames=int(raw["min_span_frames"]),
        input_root=Path(raw["input_root"]),
        spans_root=Path(raw["spans_root"]),
        output_root=Path(raw["output_root"]),
    )
