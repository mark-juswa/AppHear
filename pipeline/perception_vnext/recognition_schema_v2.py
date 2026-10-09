"""Signer-invariant recognition features derived from Candidate 01 raw-v1.

The contract is intentionally independent of recognition-v1. It removes absolute
body/hand scale and in-plane roll while retaining anatomical handshape, sign
location relative to the body, two-hand relations, current evidence quality,
and real-timestamp motion.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pipeline.perception_vnext.recognition_schema import (
    MAX_SEQUENCE_LENGTH,
    RawSequence,
    select_nearest_unique,
)

FEATURE_SCHEMA_V2 = "apphear.perception_vnext.recognition.v2"
FEATURE_WIDTH_V2 = 350
HAND_FEATURE_WIDTH = 130
BODY_FEATURE_WIDTH = 36
INTER_HAND_WIDTH = 7
HAND_MOTION_WIDTH = 21
INTER_HAND_MOTION_WIDTH = 3
TIME_WIDTH = 2
MOTION_SQUASH_SCALE = np.float32(4.0)

# MediaPipe anatomical hand topology, directed from wrist toward fingertips.
HAND_EDGES: tuple[tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
)
ANGLE_TRIPLETS: tuple[tuple[int, int, int], ...] = (
    (0, 1, 2), (1, 2, 3), (2, 3, 4),
    (0, 5, 6), (5, 6, 7), (6, 7, 8),
    (0, 9, 10), (9, 10, 11), (10, 11, 12),
    (0, 13, 14), (13, 14, 15), (14, 15, 16),
    (0, 17, 18), (17, 18, 19), (18, 19, 20),
)
FINGERTIPS = np.asarray([4, 8, 12, 16, 20], np.int32)
PALM_POINTS = np.asarray([0, 5, 9, 13, 17], np.int32)

# Candidate 01 BODY order: L/R shoulder, L/R elbow, L/R wrist, L/R hip.
BODY_EDGES: tuple[tuple[int, int], ...] = (
    (0, 2), (2, 4), (1, 3), (3, 5), (0, 6), (1, 7)
)

FEATURE_LAYOUT_V2: tuple[tuple[str, int, int], ...] = (
    ("left_hand", 0, 130),
    ("right_hand", 130, 260),
    ("body", 260, 296),
    ("inter_hand", 296, 303),
    ("left_hand_motion", 303, 324),
    ("right_hand_motion", 324, 345),
    ("inter_hand_motion", 345, 348),
    ("time", 348, 350),
)


@dataclass(frozen=True)
class _HandState:
    bone_unit: np.ndarray
    bone_valid: np.ndarray
    angle_sincos: np.ndarray
    angle_valid: np.ndarray
    fingertip_local: np.ndarray
    fingertip_valid: np.ndarray
    wrist_body: np.ndarray
    center_body: np.ndarray
    palm_axis_body: np.ndarray
    observed: bool
    reference_valid: bool
    wrist_body_valid: bool
    center_body_valid: bool


def _unit(vector: np.ndarray, minimum: float = 1.0e-6) -> tuple[np.ndarray, bool]:
    value = np.asarray(vector, np.float32)
    length = float(np.linalg.norm(value))
    if not np.isfinite(length) or length < minimum:
        return np.zeros(2, np.float32), False
    return value / np.float32(length), True


def _body_frame(
    body_xy: np.ndarray,
    body_valid: np.ndarray,
    source_width: float,
    source_height: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, bool]:
    """Return center, anatomical lateral/down axes, scale and validity."""

    points = np.asarray(body_xy, np.float32)
    valid = np.asarray(body_valid, bool)
    for left, right in ((0, 1), (6, 7)):
        if not (valid[left] and valid[right]):
            continue
        axis_x, ok = _unit(points[left] - points[right], minimum=8.0)
        if ok:
            center = (points[left] + points[right]) * np.float32(0.5)
            axis_y = np.asarray([-axis_x[1], axis_x[0]], np.float32)
            return center, axis_x, axis_y, float(np.linalg.norm(points[left] - points[right])), True
    return (
        np.asarray([source_width * 0.5, source_height * 0.5], np.float32),
        np.asarray([1.0, 0.0], np.float32),
        np.asarray([0.0, 1.0], np.float32),
        max(min(source_width, source_height), 1.0),
        False,
    )


def _to_body(
    points: np.ndarray,
    center: np.ndarray,
    axis_x: np.ndarray,
    axis_y: np.ndarray,
    scale: float,
) -> np.ndarray:
    delta = np.asarray(points, np.float32) - center
    return np.stack([delta @ axis_x, delta @ axis_y], axis=-1) / np.float32(scale)


def _hand_state(
    xy: np.ndarray,
    valid: np.ndarray,
    observed: bool,
    body_center: np.ndarray,
    body_axis_x: np.ndarray,
    body_axis_y: np.ndarray,
    body_scale: float,
    body_frame_valid: bool,
) -> _HandState:
    points = np.asarray(xy, np.float32)
    usable = np.asarray(valid, bool) & bool(observed)
    required = usable[0] and usable[5] and usable[9] and usable[17]
    axis_y, y_ok = _unit(points[9] - points[0]) if required else (np.zeros(2, np.float32), False)
    axis_x = np.zeros(2, np.float32)
    x_ok = False
    if y_ok:
        candidate = points[5] - points[17]
        candidate = candidate - axis_y * np.dot(candidate, axis_y)
        axis_x, x_ok = _unit(candidate)
    palm_length = float(np.linalg.norm(points[9] - points[0])) if required else 0.0
    palm_width = float(np.linalg.norm(points[5] - points[17])) if required else 0.0
    palm_scale = (palm_length + palm_width) * 0.5
    reference_valid = bool(required and x_ok and np.isfinite(palm_scale) and palm_scale >= 4.0)

    local = np.zeros((21, 2), np.float32)
    if reference_valid:
        delta = points - points[0]
        local = np.stack([delta @ axis_x, delta @ axis_y], axis=-1) / np.float32(palm_scale)
        local[~usable] = 0.0

    bone_unit = np.zeros((len(HAND_EDGES), 2), np.float32)
    bone_valid = np.zeros(len(HAND_EDGES), bool)
    if reference_valid:
        for index, (start, end) in enumerate(HAND_EDGES):
            if not (usable[start] and usable[end]):
                continue
            unit, ok = _unit(local[end] - local[start])
            if ok:
                bone_unit[index] = unit
                bone_valid[index] = True

    angle_sincos = np.zeros((len(ANGLE_TRIPLETS), 2), np.float32)
    angle_valid = np.zeros(len(ANGLE_TRIPLETS), bool)
    for index, (before, joint, after) in enumerate(ANGLE_TRIPLETS):
        if not (reference_valid and usable[before] and usable[joint] and usable[after]):
            continue
        first, first_ok = _unit(local[before] - local[joint])
        second, second_ok = _unit(local[after] - local[joint])
        if first_ok and second_ok:
            sine = first[0] * second[1] - first[1] * second[0]
            cosine = float(np.dot(first, second))
            angle_sincos[index] = np.asarray([sine, cosine], np.float32)
            angle_valid[index] = True

    fingertip_valid = usable[FINGERTIPS] & reference_valid
    fingertip_local = local[FINGERTIPS].copy()
    fingertip_local[~fingertip_valid] = 0.0
    wrist_body = np.zeros(2, np.float32)
    center_body = np.zeros(2, np.float32)
    wrist_body_valid = bool(observed and usable[0] and body_frame_valid)
    center_body_valid = bool(reference_valid and body_frame_valid)
    if wrist_body_valid:
        wrist_body = _to_body(
            points[0], body_center, body_axis_x, body_axis_y, body_scale
        ).astype(np.float32)
    valid_palm_points = points[PALM_POINTS][usable[PALM_POINTS]]
    palm_center = (
        valid_palm_points.mean(axis=0, dtype=np.float32)
        if reference_valid and len(valid_palm_points) >= 4
        else np.zeros(2, np.float32)
    )
    if center_body_valid:
        center_body = _to_body(
            palm_center, body_center, body_axis_x, body_axis_y, body_scale
        ).astype(np.float32)
    palm_axis_body = np.zeros(2, np.float32)
    if reference_valid and body_frame_valid:
        palm_axis_body = np.asarray(
            [np.dot(axis_y, body_axis_x), np.dot(axis_y, body_axis_y)], np.float32
        )
    return _HandState(
        bone_unit=bone_unit,
        bone_valid=bone_valid,
        angle_sincos=angle_sincos,
        angle_valid=angle_valid,
        fingertip_local=fingertip_local,
        fingertip_valid=fingertip_valid,
        wrist_body=wrist_body,
        center_body=center_body,
        palm_axis_body=palm_axis_body,
        observed=bool(observed),
        reference_valid=reference_valid,
        wrist_body_valid=wrist_body_valid,
        center_body_valid=center_body_valid,
    )


def _hand_static_block(
    state: _HandState,
    presence: float,
    proposal_support: np.ndarray,
    effective_joint_valid: np.ndarray,
) -> np.ndarray:
    support = np.asarray(proposal_support, np.float32)
    support_valid = np.asarray(effective_joint_valid, bool) & np.isfinite(support)
    mean_support = float(np.mean(support[support_valid])) if np.any(support_valid) else 0.0
    return np.concatenate(
        [
            state.bone_unit.reshape(-1),
            state.bone_valid.astype(np.float32),
            state.angle_sincos.reshape(-1),
            state.angle_valid.astype(np.float32),
            state.fingertip_local.reshape(-1),
            state.fingertip_valid.astype(np.float32),
            state.wrist_body,
            state.center_body,
            state.palm_axis_body,
            np.asarray(
                [
                    np.nan_to_num(presence, nan=0.0, posinf=0.0, neginf=0.0),
                    float(state.observed),
                    mean_support,
                    float(state.reference_valid),
                ],
                np.float32,
            ),
        ]
    ).astype(np.float32)


def _motion(
    current: _HandState,
    previous: _HandState | None,
    dt_seconds: float,
) -> np.ndarray:
    values = np.zeros(14, np.float32)
    validity = np.zeros(7, np.float32)
    if previous is None or not np.isfinite(dt_seconds) or dt_seconds <= 0.0:
        return np.concatenate([values, validity])

    def add_pair(offset: int, valid_index: int, now: np.ndarray, old: np.ndarray, ok: bool) -> None:
        if ok:
            values[offset : offset + 2] = np.tanh(
                ((now - old) / np.float32(dt_seconds)) / MOTION_SQUASH_SCALE
            )
            validity[valid_index] = 1.0

    add_pair(
        0,
        0,
        current.wrist_body,
        previous.wrist_body,
        current.wrist_body_valid and previous.wrist_body_valid,
    )
    add_pair(
        2,
        1,
        current.center_body,
        previous.center_body,
        current.center_body_valid and previous.center_body_valid,
    )
    for tip in range(5):
        add_pair(
            4 + tip * 2,
            2 + tip,
            current.fingertip_local[tip],
            previous.fingertip_local[tip],
            bool(current.fingertip_valid[tip] and previous.fingertip_valid[tip]),
        )
    return np.concatenate([values, validity]).astype(np.float32)


def derive_selected_features_v2(raw: RawSequence, indices: np.ndarray) -> np.ndarray:
    """Derive V2 after temporal selection so motion matches real observations."""

    raw.validate()
    selected = np.asarray(indices, np.int32)
    if selected.ndim != 1 or len(selected) == 0 or np.any(np.diff(selected) <= 0):
        raise ValueError("V2 source indices must be non-empty and strictly increasing")
    output = np.zeros((len(selected), FEATURE_WIDTH_V2), np.float32)
    previous_states: list[_HandState | None] = [None, None]
    previous_inter = np.zeros(2, np.float32)
    previous_inter_valid = False
    clip_start = float(raw.timestamp_ms[0])
    clip_duration = max(float(raw.timestamp_ms[-1] - raw.timestamp_ms[0]), 0.0)
    previous_timestamp: float | None = None

    for row_index, frame in enumerate(selected):
        width, height = raw.source_size[frame]
        body_center, body_x, body_y, body_scale, body_frame_valid = _body_frame(
            raw.body_xy[frame], raw.body_valid[frame], float(width), float(height)
        )
        states: list[_HandState] = []
        offset = 0
        for side in range(2):
            effective_valid = raw.hand_joint_valid[frame, side].astype(bool) & bool(
                raw.hand_observed[frame, side]
            )
            state = _hand_state(
                raw.hand_xy[frame, side],
                effective_valid,
                bool(raw.hand_observed[frame, side]),
                body_center,
                body_x,
                body_y,
                body_scale,
                body_frame_valid,
            )
            states.append(state)
            block = _hand_static_block(
                state,
                float(raw.hand_presence[frame, side]),
                raw.hand_proposal_support[frame, side],
                effective_valid,
            )
            output[row_index, offset : offset + HAND_FEATURE_WIDTH] = block
            offset += HAND_FEATURE_WIDTH

        body_vectors = np.zeros((len(BODY_EDGES), 2), np.float32)
        body_edge_valid = np.zeros(len(BODY_EDGES), bool)
        for edge_index, (start, end) in enumerate(BODY_EDGES):
            if not (raw.body_valid[frame, start] and raw.body_valid[frame, end]):
                continue
            source_unit, ok = _unit(raw.body_xy[frame, end] - raw.body_xy[frame, start])
            if ok:
                body_vectors[edge_index] = np.asarray(
                    [np.dot(source_unit, body_x), np.dot(source_unit, body_y)], np.float32
                )
                body_edge_valid[edge_index] = True
        body_support = np.nan_to_num(
            raw.body_support[frame], nan=0.0, posinf=0.0, neginf=0.0
        ).astype(np.float32)
        body_block = np.concatenate(
            [
                body_vectors.reshape(-1),
                body_edge_valid.astype(np.float32),
                body_support,
                raw.body_valid[frame].astype(np.float32),
                np.asarray(
                    [float(raw.body_available[frame]), float(body_frame_valid)], np.float32
                ),
            ]
        )
        output[row_index, offset : offset + BODY_FEATURE_WIDTH] = body_block
        offset += BODY_FEATURE_WIDTH

        both_wrist = states[0].wrist_body_valid and states[1].wrist_body_valid
        both_center = states[0].center_body_valid and states[1].center_body_valid
        wrist_delta = (
            states[1].wrist_body - states[0].wrist_body
            if both_wrist
            else np.zeros(2, np.float32)
        )
        center_delta = (
            states[1].center_body - states[0].center_body
            if both_center
            else np.zeros(2, np.float32)
        )
        inter = np.concatenate(
            [
                wrist_delta,
                center_delta,
                np.asarray(
                    [
                        float(np.linalg.norm(wrist_delta)) if both_wrist else 0.0,
                        float(np.linalg.norm(center_delta)) if both_center else 0.0,
                        float(states[0].observed and states[1].observed),
                    ],
                    np.float32,
                ),
            ]
        )
        output[row_index, offset : offset + INTER_HAND_WIDTH] = inter
        offset += INTER_HAND_WIDTH

        timestamp = float(raw.timestamp_ms[frame])
        dt_seconds = (
            0.0
            if previous_timestamp is None
            else (timestamp - previous_timestamp) / 1000.0
        )
        for side in range(2):
            hand_motion = _motion(states[side], previous_states[side], dt_seconds)
            output[row_index, offset : offset + HAND_MOTION_WIDTH] = hand_motion
            offset += HAND_MOTION_WIDTH

        inter_motion_valid = bool(
            previous_timestamp is not None
            and both_center
            and previous_inter_valid
            and dt_seconds > 0
        )
        if inter_motion_valid:
            inter_velocity = np.tanh(
                ((center_delta - previous_inter) / np.float32(dt_seconds))
                / MOTION_SQUASH_SCALE
            )
        else:
            inter_velocity = np.zeros(2, np.float32)
        output[row_index, offset : offset + INTER_HAND_MOTION_WIDTH] = np.concatenate(
            [inter_velocity, np.asarray([float(inter_motion_valid)], np.float32)]
        )
        offset += INTER_HAND_MOTION_WIDTH
        output[row_index, offset : offset + TIME_WIDTH] = np.asarray(
            [
                np.clip(dt_seconds, 0.0, 1.0),
                (timestamp - clip_start) / clip_duration if clip_duration > 0 else 0.0,
            ],
            np.float32,
        )
        offset += TIME_WIDTH
        if offset != FEATURE_WIDTH_V2:
            raise AssertionError(f"V2 feature width construction mismatch: {offset}")
        previous_states = states
        previous_inter = center_delta
        previous_inter_valid = both_center
        previous_timestamp = timestamp

    if not np.all(np.isfinite(output)):
        raise ValueError("V2 feature tensor contains NaN/Inf")
    return output


def temporal_view_v2(
    raw: RawSequence,
    *,
    condition: str,
    phone_completed_fps: float,
    max_length: int = MAX_SEQUENCE_LENGTH,
) -> dict[str, np.ndarray]:
    """Build dense/sparse V2 with motion based on the selected real timestamps."""

    raw.validate()
    timestamps = raw.timestamp_ms.astype(np.float64)
    if condition == "dense":
        indices = np.arange(len(timestamps), dtype=np.int32)
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
    features = derive_selected_features_v2(raw, indices)
    tensor = np.zeros((max_length, FEATURE_WIDTH_V2), np.float32)
    mask = np.zeros(max_length, bool)
    tensor[: len(indices)] = features
    mask[: len(indices)] = True
    return {
        "features": tensor,
        "mask": mask,
        "source_indices": indices,
        "source_timestamps_ms": timestamps[indices],
        "real_length": np.asarray(len(indices), np.int32),
    }
