"""Non-destructive span sidecar (D2 output). The raw stage-E .npz is never modified — the
span is stored as metadata that downstream stages read alongside the raw landmarks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class SpanSidecar:
    detect_version: str
    params_hash: str

    clip_id: str
    split: str
    participant_id: str
    gloss: str
    asl_lex_code: str

    n_frames: int
    native_fps: float

    onset: int  # inclusive frame index; -1 if none
    release: int  # inclusive frame index; -1 if none
    valid: bool
    reason: str
    n_signing_frames: int
    span_duration_s: float

    shoulder_scale: float
    in_span_hand_rate: float
    out_span_hand_rate: float

    # diagnostics for threshold tuning (motion in shoulder-width units per frame)
    motion_p50: float
    motion_p90: float

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2)

    @classmethod
    def load(cls, path: Path) -> SpanSidecar:
        with path.open("r", encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)
        return cls(**data)
