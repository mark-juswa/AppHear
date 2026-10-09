"""Versioned real-observation temporal views upstream of the frozen 405-column adapter."""

from __future__ import annotations

import hashlib
from typing import Any, cast

import numpy as np

from pipeline.fingerspelling.adapter import phone_indices
from pipeline.perception_vnext.recognition_schema import RawSequence

VERSION = "apphear.fingerspelling.temporal_views.v1"


def selected_indices(raw: RawSequence, view: str, config: dict[str, Any]) -> np.ndarray:
    if view == "native":
        return np.arange(len(raw.frame_index), dtype=np.int32)
    if view not in {"intermediate", "phone"}:
        raise ValueError("[fingerspelling/temporal] Unknown view")
    return cast(np.ndarray, phone_indices(raw.timestamp_ms, config[f"{view}_hz"]))


def requested_view(sample_id: str, epoch_index: int, config: dict[str, Any]) -> str:
    if epoch_index < 0:
        raise ValueError("[fingerspelling/temporal] Negative epoch")
    offset = int(hashlib.sha256(f"{config['seed']}:{sample_id}".encode()).hexdigest()[:16], 16)
    views = config["temporal_views"]
    return str(views[(offset + epoch_index) % len(views)])
