"""Offline-only DWPose-native missingness-aware representation for P5-A.

This module implements the frozen ``DWPOSE_REPRESENTATION_V2_238`` contract. It does not replace
production schema v3.0 or Android S4. Human eligibility truth is deliberately absent from every
builder interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


SCHEMA_ID = "DWPOSE_REPRESENTATION_V2_238"
SEQUENCE_LENGTH = 96
FEATURE_WIDTH = 238
BODY_INDICES = np.arange(0, 17, dtype=np.int64)
LEFT_HAND_INDICES = np.arange(91, 112, dtype=np.int64)
RIGHT_HAND_INDICES = np.arange(112, 133, dtype=np.int64)
LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_HIP = 11
RIGHT_HIP = 12
LEFT_HAND_OFFSET = 0
RIGHT_HAND_OFFSET = 84
BODY_OFFSET = 168
LEFT_OBSERVED_OFFSET = 236
RIGHT_OBSERVED_OFFSET = 237
MIN_SCALE = 1e-6
_F32_MAX = float(np.finfo(np.float32).max)


@dataclass(frozen=True)
class NormalizationDiagnostic:
    success: bool
    center_method: str
    scale_method: str
    center_x: float
    center_y: float
    scale: float
    structurally_valid_body_points: int


def _structural_validity(keypoints: np.ndarray, scores: np.ndarray) -> np.ndarray:
    values = np.column_stack([keypoints, scores])
    return np.all(np.isfinite(values) & (np.abs(values) <= _F32_MAX), axis=1)


def _pair_midpoint(points: np.ndarray, valid: np.ndarray, left: int, right: int) -> np.ndarray | None:
    if valid[left] and valid[right]:
        return (points[left] + points[right]) / 2.0
    return None


def _positive_distance(a: np.ndarray, b: np.ndarray) -> float | None:
    distance = float(np.linalg.norm(np.asarray(a, np.float64) - np.asarray(b, np.float64)))
    return distance if np.isfinite(distance) and distance > MIN_SCALE else None


def normalization_from_body(keypoints_133: np.ndarray, scores_133: np.ndarray) -> NormalizationDiagnostic:
    """Select the frozen current-frame body center and scale without temporal information."""
    keypoints = np.asarray(keypoints_133, dtype=np.float64)
    scores = np.asarray(scores_133, dtype=np.float64)
    if keypoints.shape != (133, 2) or scores.shape != (133,):
        raise ValueError(f"expected DWPose [(133,2),(133,)], got {keypoints.shape}/{scores.shape}")
    body_points = keypoints[BODY_INDICES]
    body_scores = scores[BODY_INDICES]
    valid = _structural_validity(body_points, body_scores)
    shoulders = _pair_midpoint(body_points, valid, LEFT_SHOULDER, RIGHT_SHOULDER)
    hips = _pair_midpoint(body_points, valid, LEFT_HIP, RIGHT_HIP)

    if shoulders is not None:
        center = shoulders
        center_method = "SHOULDER_PRIMARY"
    elif hips is not None:
        center = hips
        center_method = "HIP_FALLBACK"
    elif np.any(valid):
        center = np.mean(body_points[valid], axis=0)
        center_method = "VALID_BODY_MEAN_FALLBACK"
    else:
        return NormalizationDiagnostic(False, "UNAVAILABLE", "UNAVAILABLE", 0.0, 0.0, 0.0, 0)

    shoulder_scale = (
        _positive_distance(body_points[LEFT_SHOULDER], body_points[RIGHT_SHOULDER])
        if valid[LEFT_SHOULDER] and valid[RIGHT_SHOULDER]
        else None
    )
    torso_scale = _positive_distance(shoulders, hips) if shoulders is not None and hips is not None else None
    if shoulder_scale is not None:
        scale = shoulder_scale
        scale_method = "SHOULDER_DISTANCE_PRIMARY"
    elif torso_scale is not None:
        scale = torso_scale
        scale_method = "TORSO_DISTANCE_FALLBACK"
    elif np.count_nonzero(valid) >= 2:
        extent = np.max(body_points[valid], axis=0) - np.min(body_points[valid], axis=0)
        envelope = float(np.linalg.norm(extent))
        if not np.isfinite(envelope) or envelope <= MIN_SCALE:
            return NormalizationDiagnostic(
                False, center_method, "UNAVAILABLE", float(center[0]), float(center[1]), 0.0, int(np.count_nonzero(valid))
            )
        scale = envelope
        scale_method = "VALID_BODY_ENVELOPE_FALLBACK"
    else:
        return NormalizationDiagnostic(
            False, center_method, "UNAVAILABLE", float(center[0]), float(center[1]), 0.0, int(np.count_nonzero(valid))
        )

    return NormalizationDiagnostic(
        True,
        center_method,
        scale_method,
        float(center[0]),
        float(center[1]),
        max(float(scale), MIN_SCALE),
        int(np.count_nonzero(valid)),
    )


def _encode_block(
    keypoints: np.ndarray,
    scores: np.ndarray,
    indices: np.ndarray,
    normalization: NormalizationDiagnostic,
    enabled: bool,
) -> np.ndarray:
    output = np.zeros((len(indices), 4), dtype=np.float32)
    if not enabled or not normalization.success:
        return output
    points = np.asarray(keypoints[indices], dtype=np.float64)
    point_scores = np.asarray(scores[indices], dtype=np.float64)
    valid = _structural_validity(points, point_scores)
    if np.any(valid):
        center = np.array([normalization.center_x, normalization.center_y], dtype=np.float64)
        output[valid, :2] = ((points[valid] - center) / normalization.scale).astype(np.float32)
        output[valid, 2] = point_scores[valid].astype(np.float32)
        output[valid, 3] = 1.0
    return output


def build_frame_features(
    keypoints_133: np.ndarray,
    scores_133: np.ndarray,
    gated_presence: np.ndarray,
) -> tuple[np.ndarray, NormalizationDiagnostic]:
    """Build one `[238]` frame using only native DWPose output and frozen presence state."""
    keypoints = np.asarray(keypoints_133)
    scores = np.asarray(scores_133)
    observed = np.asarray(gated_presence, dtype=bool)
    if keypoints.shape != (133, 2) or scores.shape != (133,) or observed.shape != (2,):
        raise ValueError(
            f"expected keypoints (133,2), scores (133,), presence (2,), got "
            f"{keypoints.shape}/{scores.shape}/{observed.shape}"
        )
    normalization = normalization_from_body(keypoints, scores)
    feature = np.zeros((FEATURE_WIDTH,), dtype=np.float32)
    feature[LEFT_HAND_OFFSET:RIGHT_HAND_OFFSET] = _encode_block(
        keypoints, scores, LEFT_HAND_INDICES, normalization, bool(observed[0])
    ).reshape(-1)
    feature[RIGHT_HAND_OFFSET:BODY_OFFSET] = _encode_block(
        keypoints, scores, RIGHT_HAND_INDICES, normalization, bool(observed[1])
    ).reshape(-1)
    feature[BODY_OFFSET:LEFT_OBSERVED_OFFSET] = _encode_block(
        keypoints, scores, BODY_INDICES, normalization, True
    ).reshape(-1)
    feature[LEFT_OBSERVED_OFFSET] = float(observed[0] and normalization.success)
    feature[RIGHT_OBSERVED_OFFSET] = float(observed[1] and normalization.success)
    if not np.all(np.isfinite(feature)):
        raise RuntimeError("DWPOSE_REPRESENTATION_V2_NONFINITE_OUTPUT")
    return feature, normalization


def build_padded_sequence(frames: Iterable[np.ndarray]) -> tuple[np.ndarray, np.ndarray, int]:
    """Post-pad real-timed frame features to `[96,238]`; no resampling or interpolation."""
    values = [np.asarray(frame, dtype=np.float32) for frame in frames]
    if any(value.shape != (FEATURE_WIDTH,) for value in values):
        raise ValueError("every frame must have shape [238]")
    length = min(len(values), SEQUENCE_LENGTH)
    output = np.zeros((SEQUENCE_LENGTH, FEATURE_WIDTH), dtype=np.float32)
    if length:
        output[:length] = np.stack(values[:length])
    frame_mask = np.zeros((SEQUENCE_LENGTH,), dtype=bool)
    frame_mask[:length] = True
    return output, frame_mask, length


def feature_index_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    blocks = [
        ("LEFT_HAND", LEFT_HAND_OFFSET, LEFT_HAND_INDICES),
        ("RIGHT_HAND", RIGHT_HAND_OFFSET, RIGHT_HAND_INDICES),
        ("BODY", BODY_OFFSET, BODY_INDICES),
    ]
    channels = ("x_normalized", "y_normalized", "score", "valid_mask")
    for block, offset, indices in blocks:
        for local_index, source_index in enumerate(indices.tolist()):
            for channel_index, channel in enumerate(channels):
                rows.append(
                    {
                        "feature_index": offset + local_index * 4 + channel_index,
                        "block": block,
                        "local_landmark_index": local_index,
                        "dwpose_source_index": source_index,
                        "channel": channel,
                    }
                )
    rows.extend(
        [
            {"feature_index": LEFT_OBSERVED_OFFSET, "block": "LEFT_HAND_OBSERVED", "local_landmark_index": "", "dwpose_source_index": "", "channel": "observed_mask"},
            {"feature_index": RIGHT_OBSERVED_OFFSET, "block": "RIGHT_HAND_OBSERVED", "local_landmark_index": "", "dwpose_source_index": "", "channel": "observed_mask"},
        ]
    )
    if [row["feature_index"] for row in rows] != list(range(FEATURE_WIDTH)):
        raise RuntimeError("DWPOSE_REPRESENTATION_V2_INDEX_MAP_INVALID")
    return rows
