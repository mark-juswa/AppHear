"""Causal pose-wrist ROI recovery for the E2b experiment."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import RoiConfig
from .roi import RoiObservation, direct_square_box


@dataclass(frozen=True)
class PoseRecoveryConfig:
    min_pose_visibility: float
    fallback_side_ratio: float
    max_track_age_ms: int


def _pose_point(
    pose_image: np.ndarray,
    landmark_index: int,
    frame_width: int,
    frame_height: int,
    min_visibility: float,
) -> tuple[float, float] | None:
    point = pose_image[landmark_index]
    if not np.all(np.isfinite(point[[0, 1, 3]])) or float(point[3]) < min_visibility:
        return None
    return float(point[0] * frame_width), float(point[1] * frame_height)


def _pose_hand_anchor(
    pose_image: np.ndarray,
    hand_index: int,
    frame_width: int,
    frame_height: int,
    min_visibility: float,
) -> tuple[float, float] | None:
    indices = (15, 17, 19, 21) if hand_index == 0 else (16, 18, 20, 22)
    points = [
        point
        for index in indices
        if (
            point := _pose_point(
                pose_image, index, frame_width, frame_height, min_visibility
            )
        )
        is not None
    ]
    wrist = _pose_point(
        pose_image, indices[0], frame_width, frame_height, min_visibility
    )
    if not points or wrist is None:
        return None
    return (
        float(np.mean([point[0] for point in points])),
        float(np.mean([point[1] for point in points])),
    )

def _fallback_box(
    pose_image: np.ndarray,
    hand_index: int,
    frame_width: int,
    frame_height: int,
    expansion: float,
    roi: RoiConfig,
    recovery: PoseRecoveryConfig,
) -> tuple[float, float, float, float] | None:
    anchor = _pose_hand_anchor(
        pose_image,
        hand_index,
        frame_width,
        frame_height,
        recovery.min_pose_visibility,
    )
    left_shoulder = _pose_point(
        pose_image, 11, frame_width, frame_height, recovery.min_pose_visibility
    )
    right_shoulder = _pose_point(
        pose_image, 12, frame_width, frame_height, recovery.min_pose_visibility
    )
    if anchor is None or left_shoulder is None or right_shoulder is None:
        return None
    shoulder_width = float(
        np.hypot(
            right_shoulder[0] - left_shoulder[0],
            right_shoulder[1] - left_shoulder[1],
        )
    )
    side = shoulder_width * recovery.fallback_side_ratio * expansion
    floor = roi.min_side_fraction * min(frame_width, frame_height)
    ceiling = roi.max_side_fraction * max(frame_width, frame_height)
    side = float(np.clip(side, floor, ceiling))
    half = side * 0.5
    return anchor[0] - half, anchor[1] - half, anchor[0] + half, anchor[1] + half


def causal_pose_recovery_sequence(
    hands_image: np.ndarray,
    hand_score: np.ndarray,
    pose_image: np.ndarray,
    timestamps_ms: np.ndarray,
    frame_width: int,
    frame_height: int,
    expansion: float,
    roi: RoiConfig,
    recovery: PoseRecoveryConfig,
    observation_mask: np.ndarray | None = None,
) -> list[list[RoiObservation]]:
    """Recover missing hand boxes from current causal pose hand anchors.

    Direct hand boxes remain authoritative. While a direct box is fresh, its center follows
    sampled pose-hand motion. After expiry, a body-scaled box uses the current pose anchor.
    Unsampled frames cannot refresh either hand or pose state.
    """
    if observation_mask is None:
        observation_mask = np.ones(timestamps_ms.shape, dtype=bool)
    if observation_mask.shape != timestamps_ms.shape:
        raise ValueError(
            f"observation_mask shape {observation_mask.shape} does not match "
            f"timestamps {timestamps_ms.shape}"
        )

    output: list[list[RoiObservation]] = []
    tracked_box: list[tuple[float, float, float, float] | None] = [None, None]
    tracked_anchor: list[tuple[float, float] | None] = [None, None]
    last_direct_timestamp: list[int | None] = [None, None]

    for frame_idx, timestamp_value in enumerate(timestamps_ms):
        timestamp = int(timestamp_value)
        frame_rois: list[RoiObservation] = []
        for hand_idx in range(2):
            if not observation_mask[frame_idx]:
                previous = last_direct_timestamp[hand_idx]
                age = timestamp - previous if previous is not None else 0
                frame_rois.append(RoiObservation(None, "unsampled", max(age, 0)))
                continue

            direct = None
            if hand_score[frame_idx, hand_idx] > 0.0:
                direct = direct_square_box(
                    hands_image[frame_idx, hand_idx],
                    frame_width,
                    frame_height,
                    expansion,
                    roi,
                )
            current_anchor = _pose_hand_anchor(
                pose_image[frame_idx],
                hand_idx,
                frame_width,
                frame_height,
                recovery.min_pose_visibility,
            )
            if direct is not None:
                tracked_box[hand_idx] = direct
                tracked_anchor[hand_idx] = current_anchor
                last_direct_timestamp[hand_idx] = timestamp
                frame_rois.append(RoiObservation(direct, "direct", 0))
                continue

            previous_timestamp = last_direct_timestamp[hand_idx]
            age = timestamp - previous_timestamp if previous_timestamp is not None else -1
            previous_box = tracked_box[hand_idx]
            previous_anchor = tracked_anchor[hand_idx]
            if (
                previous_box is not None
                and previous_anchor is not None
                and current_anchor is not None
                and 0 <= age <= recovery.max_track_age_ms
            ):
                dx = current_anchor[0] - previous_anchor[0]
                dy = current_anchor[1] - previous_anchor[1]
                x1, y1, x2, y2 = previous_box
                shifted = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)
                tracked_box[hand_idx] = shifted
                tracked_anchor[hand_idx] = current_anchor
                frame_rois.append(RoiObservation(shifted, "pose_tracked", age))
                continue

            fallback = _fallback_box(
                pose_image[frame_idx],
                hand_idx,
                frame_width,
                frame_height,
                expansion,
                roi,
                recovery,
            )
            if fallback is not None:
                frame_rois.append(RoiObservation(fallback, "pose_fallback", max(age, 0)))
            else:
                frame_rois.append(RoiObservation(None, "missing", max(age, 0)))
        output.append(frame_rois)
    return output


def hand_to_shoulder_ratios(
    hands_image: np.ndarray,
    hand_score: np.ndarray,
    pose_image: np.ndarray,
    frame_width: int,
    frame_height: int,
    min_valid_landmarks: int,
    min_pose_visibility: float,
) -> list[float]:
    """Measure raw hand-box side divided by pose shoulder width."""
    ratios: list[float] = []
    for frame_idx in range(hands_image.shape[0]):
        left_shoulder = _pose_point(
            pose_image[frame_idx], 11, frame_width, frame_height, min_pose_visibility
        )
        right_shoulder = _pose_point(
            pose_image[frame_idx], 12, frame_width, frame_height, min_pose_visibility
        )
        if left_shoulder is None or right_shoulder is None:
            continue
        shoulder_width = float(
            np.hypot(
                right_shoulder[0] - left_shoulder[0],
                right_shoulder[1] - left_shoulder[1],
            )
        )
        if shoulder_width <= 1.0:
            continue
        for hand_idx in range(2):
            if hand_score[frame_idx, hand_idx] <= 0.0:
                continue
            landmarks = hands_image[frame_idx, hand_idx]
            valid = np.all(np.isfinite(landmarks[:, :2]), axis=1)
            if int(np.sum(valid)) < min_valid_landmarks:
                continue
            xy = landmarks[valid, :2]
            raw_side = float(
                max(
                    np.ptp(xy[:, 0] * frame_width),
                    np.ptp(xy[:, 1] * frame_height),
                )
            )
            if raw_side > 0.0:
                ratios.append(raw_side / shoulder_width)
    return ratios
