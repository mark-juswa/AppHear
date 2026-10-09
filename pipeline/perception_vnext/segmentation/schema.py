"""Canonical raw-v1 loading and non-mutating slicing for segmentation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

RAW_SCHEMA = "apphear.perception_vnext.raw.v1"
EVENT_SCHEMA = "apphear.segmentation.sign_event.v1"
STATE_MACHINE_VERSION = "apphear.segmentation.state_machine.v1"
IMAGE_SEMANTICS = "UPRIGHT_UNMIRRORED_SOURCE_RGB"

# Width per observation in the retained live raw-v1 JSON representation. Values are flat arrays.
PER_OBSERVATION_WIDTHS = {
    "frame_index": 1,
    "timestamp_ms": 1,
    "source_size": 2,
    "hand_xy": 2 * 21 * 2,
    "hand_proposal_support": 2 * 21,
    "hand_joint_valid": 2 * 21,
    "hand_presence": 2,
    "hand_observed": 2,
    "hand_proposal_present": 2,
    "hand_roi_center_side": 2 * 3,
    "hand_handedness_diagnostic": 2,
    "body_xy": 8 * 2,
    "body_support": 8,
    "body_valid": 8,
    "body_available": 1,
    "frame_runtime": 1,
}


@dataclass(frozen=True)
class RawV1Arrays:
    """Typed array view used only for derived segmentation signals."""

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


@dataclass(frozen=True)
class RawV1Document:
    """Original JSON values plus a validated typed view.

    ``source`` is never normalized or rewritten. SignEvent serialization slices it directly.
    """

    source: dict[str, Any]
    arrays: RawV1Arrays

    @property
    def observation_count(self) -> int:
        return int(self.arrays.frame_index.size)

    def slice_source(self, start_index: int, end_index: int) -> dict[str, Any]:
        """Return an inclusive canonical raw-v1 slice without fabricating values."""

        if not 0 <= start_index <= end_index < self.observation_count:
            raise ValueError("raw-v1 slice is outside the source observation range")
        result: dict[str, Any] = {}
        for name, value in self.source.items():
            width = PER_OBSERVATION_WIDTHS.get(name)
            if width is None:
                result[name] = value
                continue
            first = start_index * width
            last = (end_index + 1) * width
            result[name] = value[first:last]
        validate_raw_v1_mapping(result)
        return result


def _reshape(source: dict[str, Any], name: str, shape: tuple[int, ...], dtype: Any) -> np.ndarray:
    return np.asarray(source[name], dtype=dtype).reshape(shape)


def validate_raw_v1_mapping(source: dict[str, Any]) -> int:
    """Fail closed on raw identity, chronology, and retained live-array structure."""

    if source.get("schema") != RAW_SCHEMA:
        raise ValueError("raw-v1 schema identity mismatch")
    if source.get("image_semantics") != IMAGE_SEMANTICS:
        raise ValueError("raw-v1 image semantics mismatch")
    if not isinstance(source.get("frame_index"), list) or not source["frame_index"]:
        raise ValueError("raw-v1 frame_index must be a non-empty list")
    count = len(source["frame_index"])
    for name, width in PER_OBSERVATION_WIDTHS.items():
        value = source.get(name)
        if not isinstance(value, list) or len(value) != count * width:
            raise ValueError(
                f"raw-v1 {name} length mismatch: {len(value) if isinstance(value, list) else None} "
                f"!= {count * width}"
            )
    frame_index = np.asarray(source["frame_index"], np.int64)
    timestamp_ms = np.asarray(source["timestamp_ms"], np.float64)
    if not np.all(np.diff(frame_index) > 0):
        raise ValueError("raw-v1 frame indices must be strictly increasing")
    if not np.all(np.isfinite(timestamp_ms)) or not np.all(np.diff(timestamp_ms) > 0):
        raise ValueError("raw-v1 source timestamps must be finite and strictly increasing")
    source_size = _reshape(source, "source_size", (count, 2), np.float64)
    if not np.all(np.isfinite(source_size)) or not np.all(source_size > 0):
        raise ValueError("raw-v1 source dimensions must be finite and positive")
    return count


def raw_v1_arrays(source: dict[str, Any]) -> RawV1Arrays:
    count = validate_raw_v1_mapping(source)
    arrays = RawV1Arrays(
        frame_index=_reshape(source, "frame_index", (count,), np.int64),
        timestamp_ms=_reshape(source, "timestamp_ms", (count,), np.float64),
        source_size=_reshape(source, "source_size", (count, 2), np.float64),
        hand_xy=_reshape(source, "hand_xy", (count, 2, 21, 2), np.float64),
        hand_proposal_support=_reshape(
            source, "hand_proposal_support", (count, 2, 21), np.float64
        ),
        hand_joint_valid=_reshape(source, "hand_joint_valid", (count, 2, 21), bool),
        hand_presence=_reshape(source, "hand_presence", (count, 2), np.float64),
        hand_observed=_reshape(source, "hand_observed", (count, 2), bool),
        hand_proposal_present=_reshape(source, "hand_proposal_present", (count, 2), bool),
        hand_roi_center_side=_reshape(
            source, "hand_roi_center_side", (count, 2, 3), np.float64
        ),
        hand_handedness_diagnostic=_reshape(
            source, "hand_handedness_diagnostic", (count, 2), np.float64
        ),
        body_xy=_reshape(source, "body_xy", (count, 8, 2), np.float64),
        body_support=_reshape(source, "body_support", (count, 8), np.float64),
        body_valid=_reshape(source, "body_valid", (count, 8), bool),
        body_available=_reshape(source, "body_available", (count,), bool),
    )
    valid_hand_finite = np.all(np.isfinite(arrays.hand_xy), axis=-1) | ~arrays.hand_joint_valid
    if not np.all(valid_hand_finite):
        raise ValueError("valid raw-v1 hand joints must contain finite XY")
    valid_body_finite = np.all(np.isfinite(arrays.body_xy), axis=-1) | ~arrays.body_valid
    if not np.all(valid_body_finite):
        raise ValueError("valid raw-v1 body points must contain finite XY")
    return arrays


def load_raw_v1_json(path: Path) -> RawV1Document:
    source = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise ValueError("raw-v1 JSON root must be an object")
    return RawV1Document(source=source, arrays=raw_v1_arrays(source))
