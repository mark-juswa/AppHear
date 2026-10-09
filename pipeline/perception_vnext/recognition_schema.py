"""Versioned raw and recognizer contracts for Candidate 01 utility testing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

RAW_SCHEMA = "apphear.perception_vnext.raw.v1"
FEATURE_SCHEMA = "apphear.perception_vnext.recognition.v1"
FEATURE_WIDTH = 208
MAX_SEQUENCE_LENGTH = 96
BODY_INDICES = np.asarray([5, 6, 7, 8, 9, 10, 11, 12], np.int32)
LEFT_HAND_START = 91
RIGHT_HAND_START = 112
HAND_POINTS = 21
BODY_POINTS = 8
BODY_SUPPORT_THRESHOLD = np.float32(0.30)
HAND_PROPOSAL_SUPPORT_THRESHOLD = np.float32(0.10)
HAND_PRESENCE_THRESHOLD = np.float32(0.50)
MINIMUM_HAND_PROPOSAL_POINTS = 5
MINIMUM_REFINED_VALID_POINTS = 18


@dataclass(frozen=True)
class RawSequence:
    """One clip of unmodified current-frame Candidate 01 evidence."""

    metadata: dict[str, Any]
    frame_index: np.ndarray
    timestamp_ms: np.ndarray
    source_size: np.ndarray
    hand_xy: np.ndarray
    hand_proposal_support: np.ndarray
    hand_joint_valid: np.ndarray
    hand_presence: np.ndarray
    hand_observed: np.ndarray
    hand_proposal_present: np.ndarray
    hand_roi_center_side: np.ndarray
    hand_handedness_diagnostic: np.ndarray
    body_xy: np.ndarray
    body_support: np.ndarray
    body_valid: np.ndarray
    body_available: np.ndarray

    def validate(self) -> None:
        t = len(self.frame_index)
        expected = {
            "timestamp_ms": (t,),
            "source_size": (t, 2),
            "hand_xy": (t, 2, HAND_POINTS, 2),
            "hand_proposal_support": (t, 2, HAND_POINTS),
            "hand_joint_valid": (t, 2, HAND_POINTS),
            "hand_presence": (t, 2),
            "hand_observed": (t, 2),
            "hand_proposal_present": (t, 2),
            "hand_roi_center_side": (t, 2, 3),
            "hand_handedness_diagnostic": (t, 2),
            "body_xy": (t, BODY_POINTS, 2),
            "body_support": (t, BODY_POINTS),
            "body_valid": (t, BODY_POINTS),
            "body_available": (t,),
        }
        for name, shape in expected.items():
            if tuple(np.asarray(getattr(self, name)).shape) != shape:
                raise ValueError(f"{name} shape mismatch: {getattr(self, name).shape} != {shape}")
        if t == 0 or not np.all(np.diff(self.frame_index.astype(np.int64)) > 0):
            raise ValueError("raw sequence frame indices must be non-empty and strictly increasing")
        if not np.all(np.diff(self.timestamp_ms.astype(np.float64)) > 0):
            raise ValueError("raw sequence timestamps must be strictly increasing")
        if self.metadata.get("schema") != RAW_SCHEMA:
            raise ValueError("raw schema identity mismatch")
        if self.metadata.get("image_semantics") != "UPRIGHT_UNMIRRORED_SOURCE_RGB":
            raise ValueError("raw image semantics mismatch")
        valid_finite = np.all(np.isfinite(self.hand_xy), axis=-1) | ~self.hand_joint_valid.astype(
            bool
        )
        if not np.all(valid_finite):
            raise ValueError("valid hand joints must contain finite XY")
        body_finite = np.all(np.isfinite(self.body_xy), axis=-1) | ~self.body_valid.astype(bool)
        if not np.all(body_finite):
            raise ValueError("valid body points must contain finite XY")


def save_raw_sequence(path: Path, raw: RawSequence) -> None:
    raw.validate()
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {
        name: np.asarray(getattr(raw, name))
        for name in RawSequence.__dataclass_fields__
        if name != "metadata"
    }
    np.savez_compressed(
        path,
        metadata_json=np.asarray(json.dumps(raw.metadata, sort_keys=True)),
        **arrays,
    )


def load_raw_sequence(path: Path) -> RawSequence:
    with np.load(path, allow_pickle=False) as data:
        value = RawSequence(
            metadata=json.loads(str(data["metadata_json"].item())),
            **{
                name: np.asarray(data[name])
                for name in RawSequence.__dataclass_fields__
                if name != "metadata"
            },
        )
    value.validate()
    return value


def body_point_valid(
    xy: np.ndarray,
    support: np.ndarray,
    source_width: int,
    source_height: int,
) -> np.ndarray:
    """Exact point rule behind PHONE_01's existing >=6/8 availability decision."""

    points = np.asarray(xy, np.float32)
    scores = np.asarray(support, np.float32)
    return (
        np.all(np.isfinite(points), axis=-1)
        & np.isfinite(scores)
        & (scores >= BODY_SUPPORT_THRESHOLD)
        & (points[..., 0] >= 0)
        & (points[..., 0] < source_width)
        & (points[..., 1] >= 0)
        & (points[..., 1] < source_height)
    )


def _normalization(
    body_xy: np.ndarray,
    body_valid: np.ndarray,
    source_width: float,
    source_height: float,
) -> tuple[np.ndarray, float, bool]:
    """Return center, isotropic scale, and whether current body evidence defines them."""

    points = np.asarray(body_xy, np.float32)
    valid = np.asarray(body_valid, bool)
    # BODY indices are L/R shoulder, L/R elbow, L/R wrist, L/R hip.
    if valid[0] and valid[1]:
        center = (points[0] + points[1]) * np.float32(0.5)
        scale = float(np.linalg.norm(points[0] - points[1]))
        if np.isfinite(scale) and scale >= 8.0:
            return center, scale, True
    if valid[6] and valid[7]:
        center = (points[6] + points[7]) * np.float32(0.5)
        scale = float(np.linalg.norm(points[6] - points[7]))
        if np.isfinite(scale) and scale >= 8.0:
            return center, scale, True
    if np.count_nonzero(valid) >= 2:
        visible = points[valid]
        center = visible.mean(axis=0, dtype=np.float32)
        extent = np.ptp(visible, axis=0)
        scale = float(np.max(extent))
        if np.isfinite(scale) and scale >= 8.0:
            return center, scale, True
    return (
        np.asarray([source_width * 0.5, source_height * 0.5], np.float32),
        max(min(source_width, source_height), 1.0),
        False,
    )


def derive_frame_features(raw: RawSequence) -> np.ndarray:
    """Build finite 208-wide features without mutating or fabricating raw evidence."""

    raw.validate()
    t = len(raw.frame_index)
    output = np.zeros((t, FEATURE_WIDTH), np.float32)
    duration = max(float(raw.timestamp_ms[-1] - raw.timestamp_ms[0]), 0.0)
    for frame in range(t):
        width, height = raw.source_size[frame]
        center, scale, body_norm_valid = _normalization(
            raw.body_xy[frame], raw.body_valid[frame], float(width), float(height)
        )
        offset = 0
        for side in range(2):
            effective_valid = raw.hand_joint_valid[frame, side] & raw.hand_observed[frame, side]
            normalized = (raw.hand_xy[frame, side] - center) / np.float32(scale)
            normalized[~effective_valid] = 0.0
            support = np.nan_to_num(
                raw.hand_proposal_support[frame, side], nan=0.0, posinf=0.0, neginf=0.0
            )
            block = np.column_stack(
                [normalized, support, effective_valid.astype(np.float32)]
            ).astype(np.float32)
            output[frame, offset : offset + 84] = block.reshape(-1)
            offset += 84
        body_normalized = (raw.body_xy[frame] - center) / np.float32(scale)
        body_normalized[~raw.body_valid[frame]] = 0.0
        body_support = np.nan_to_num(raw.body_support[frame], nan=0.0, posinf=0.0, neginf=0.0)
        body_block = np.column_stack(
            [body_normalized, body_support, raw.body_valid[frame].astype(np.float32)]
        ).astype(np.float32)
        output[frame, offset : offset + 32] = body_block.reshape(-1)
        offset += 32
        output[frame, offset : offset + 6] = np.asarray(
            [
                np.nan_to_num(raw.hand_presence[frame, 0], nan=0.0),
                float(raw.hand_observed[frame, 0]),
                np.nan_to_num(raw.hand_presence[frame, 1], nan=0.0),
                float(raw.hand_observed[frame, 1]),
                float(raw.body_available[frame]),
                float(body_norm_valid),
            ],
            np.float32,
        )
        offset += 6
        delta_ms = (
            0.0 if frame == 0 else float(raw.timestamp_ms[frame] - raw.timestamp_ms[frame - 1])
        )
        output[frame, offset] = np.float32(np.clip(delta_ms / 1000.0, 0.0, 1.0))
        output[frame, offset + 1] = np.float32(
            float(raw.timestamp_ms[frame] - raw.timestamp_ms[0]) / duration if duration > 0 else 0.0
        )
    if not np.all(np.isfinite(output)):
        raise ValueError("derived feature tensor contains NaN/Inf")
    return output


def select_nearest_unique(timestamps_ms: np.ndarray, target_ms: np.ndarray) -> np.ndarray:
    """Select chronological unique source observations nearest to ordered targets."""

    timestamps = np.asarray(timestamps_ms, np.float64)
    targets = np.asarray(target_ms, np.float64)
    candidates = np.searchsorted(timestamps, targets)
    selected: list[int] = []
    for candidate, target in zip(candidates, targets, strict=True):
        options = [index for index in (candidate - 1, candidate) if 0 <= index < len(timestamps)]
        best = min(options, key=lambda index: (abs(timestamps[index] - target), index))
        if not selected or best > selected[-1]:
            selected.append(best)
    return np.asarray(selected, np.int32)


def temporal_view(
    features: np.ndarray,
    timestamps_ms: np.ndarray,
    *,
    condition: str,
    phone_completed_fps: float,
    max_length: int = MAX_SEQUENCE_LENGTH,
) -> dict[str, np.ndarray]:
    """Create dense or measured-phone-density input with zero padding and a mask."""

    value = np.asarray(features, np.float32)
    timestamps = np.asarray(timestamps_ms, np.float64)
    if value.ndim != 2 or value.shape[1] != FEATURE_WIDTH or len(value) != len(timestamps):
        raise ValueError("temporal input shape mismatch")
    if condition == "dense":
        indices = np.arange(len(value), dtype=np.int32)
    elif condition == "phone_01_sparse":
        if not np.isfinite(phone_completed_fps) or phone_completed_fps <= 0:
            raise ValueError("phone completed FPS evidence is invalid")
        step_ms = 1000.0 / phone_completed_fps
        targets = np.arange(timestamps[0], timestamps[-1] + step_ms * 0.25, step_ms)
        indices = select_nearest_unique(timestamps, targets)
        if len(indices) == 0:
            indices = np.asarray([0], np.int32)
    else:
        raise ValueError(f"unknown temporal condition: {condition}")
    if len(indices) > max_length:
        targets = np.linspace(timestamps[indices[0]], timestamps[indices[-1]], max_length)
        local = select_nearest_unique(timestamps[indices], targets)
        indices = indices[local]
    count = len(indices)
    tensor = np.zeros((max_length, FEATURE_WIDTH), np.float32)
    mask = np.zeros((max_length,), bool)
    tensor[:count] = value[indices]
    mask[:count] = True
    return {
        "features": tensor,
        "mask": mask,
        "source_indices": indices,
        "source_timestamps_ms": timestamps[indices],
        "real_length": np.asarray(count, np.int32),
    }
