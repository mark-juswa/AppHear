"""Deterministic, causal ROI construction and RGB crop extraction for E2."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .config import RoiConfig


@dataclass(frozen=True)
class RoiObservation:
    box_xyxy: tuple[float, float, float, float] | None
    source: str
    age_ms: int


def direct_square_box(
    landmarks_xyz: np.ndarray,
    frame_width: int,
    frame_height: int,
    expansion: float,
    config: RoiConfig,
) -> tuple[float, float, float, float] | None:
    """Return an expanded square pixel box from finite normalized image landmarks."""
    valid = np.all(np.isfinite(landmarks_xyz[:, :2]), axis=1)
    if int(np.sum(valid)) < config.min_valid_landmarks:
        return None

    xy = landmarks_xyz[valid, :2]
    x_px = xy[:, 0] * frame_width
    y_px = xy[:, 1] * frame_height
    center_x = float((np.min(x_px) + np.max(x_px)) * 0.5)
    center_y = float((np.min(y_px) + np.max(y_px)) * 0.5)
    raw_side = float(max(np.ptp(x_px), np.ptp(y_px))) * expansion
    floor = config.min_side_fraction * min(frame_width, frame_height)
    ceiling = config.max_side_fraction * max(frame_width, frame_height)
    side = float(np.clip(raw_side, floor, ceiling))
    half = side * 0.5
    return center_x - half, center_y - half, center_x + half, center_y + half


def causal_roi_sequence(
    hands_image: np.ndarray,
    hand_score: np.ndarray,
    timestamps_ms: np.ndarray,
    frame_width: int,
    frame_height: int,
    expansion: float,
    config: RoiConfig,
    observation_mask: np.ndarray | None = None,
) -> list[list[RoiObservation]]:
    """Build direct ROIs and timestamp-bounded causal holds for both canonical hand slots."""
    if observation_mask is None:
        observation_mask = np.ones(timestamps_ms.shape, dtype=bool)
    if observation_mask.shape != timestamps_ms.shape:
        raise ValueError(
            f"observation_mask shape {observation_mask.shape} does not match "
            f"timestamps {timestamps_ms.shape}"
        )

    output: list[list[RoiObservation]] = []
    last_box: list[tuple[float, float, float, float] | None] = [None, None]
    last_timestamp: list[int | None] = [None, None]

    for frame_idx, timestamp in enumerate(timestamps_ms):
        frame_rois: list[RoiObservation] = []
        for hand_idx in range(2):
            box = None
            if observation_mask[frame_idx] and hand_score[frame_idx, hand_idx] > 0.0:
                box = direct_square_box(
                    hands_image[frame_idx, hand_idx],
                    frame_width,
                    frame_height,
                    expansion,
                    config,
                )
            if box is not None:
                last_box[hand_idx] = box
                last_timestamp[hand_idx] = int(timestamp)
                frame_rois.append(RoiObservation(box, "direct", 0))
                continue

            previous_time = last_timestamp[hand_idx]
            age_ms = int(timestamp) - previous_time if previous_time is not None else -1
            if (
                last_box[hand_idx] is not None
                and previous_time is not None
                and 0 <= age_ms <= config.max_hold_ms
            ):
                frame_rois.append(RoiObservation(last_box[hand_idx], "held", age_ms))
            else:
                frame_rois.append(RoiObservation(None, "missing", max(age_ms, 0)))
        output.append(frame_rois)
    return output


def extract_square_crop(
    frame_bgr: np.ndarray,
    box_xyxy: tuple[float, float, float, float],
    output_size: int,
    pad_value_rgb: tuple[int, int, int],
) -> tuple[np.ndarray, float]:
    """Crop a square ROI with constant padding. Returns BGR crop and padded-area fraction."""
    height, width = frame_bgr.shape[:2]
    x1, y1, x2, y2 = box_xyxy
    left, top = int(np.floor(x1)), int(np.floor(y1))
    right, bottom = int(np.ceil(x2)), int(np.ceil(y2))
    side = max(right - left, bottom - top, 1)
    right, bottom = left + side, top + side

    source_left = max(left, 0)
    source_top = max(top, 0)
    source_right = min(right, width)
    source_bottom = min(bottom, height)
    crop = frame_bgr[source_top:source_bottom, source_left:source_right]

    pad_left = source_left - left
    pad_top = source_top - top
    pad_right = right - source_right
    pad_bottom = bottom - source_bottom
    bgr_value = tuple(reversed(pad_value_rgb))
    crop = cv2.copyMakeBorder(
        crop,
        pad_top,
        pad_bottom,
        pad_left,
        pad_right,
        cv2.BORDER_CONSTANT,
        value=bgr_value,
    )
    interpolation = cv2.INTER_AREA if side > output_size else cv2.INTER_LINEAR
    resized = cv2.resize(crop, (output_size, output_size), interpolation=interpolation)
    visible_area = max(source_right - source_left, 0) * max(source_bottom - source_top, 0)
    padding_fraction = 1.0 - (visible_area / float(side * side))
    return resized, float(np.clip(padding_fraction, 0.0, 1.0))


def sharpness_variance(crop_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())
