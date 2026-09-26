"""Current-frame hand ROI construction for Perception vNext.

The ROI is derived only from the same frame's DWPose-t hand points.  It does
not use temporal carry, optical flow, or pose-wrist recovery.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class HandRoi:
    """Axis-aligned square in upright, unmirrored source coordinates."""

    center_x: float
    center_y: float
    side: float
    source_width: int
    source_height: int
    support_count: int

    @property
    def xyxy(self) -> tuple[float, float, float, float]:
        half = self.side * 0.5
        return (
            self.center_x - half,
            self.center_y - half,
            self.center_x + half,
            self.center_y + half,
        )

    @property
    def normalized_xyxy(self) -> tuple[float, float, float, float]:
        left, top, right, bottom = self.xyxy
        return (
            left / self.source_width,
            top / self.source_height,
            right / self.source_width,
            bottom / self.source_height,
        )


def build_hand_roi(
    points_xy: np.ndarray,
    support: np.ndarray,
    source_width: int,
    source_height: int,
    *,
    minimum_support: float = 0.10,
    minimum_points: int = 5,
    expansion: float = 1.8,
    minimum_side_fraction: float = 0.12,
    maximum_side_fraction: float = 0.50,
) -> HandRoi | None:
    """Build a high-recall robust square proposal from one anatomical slot."""

    points = np.asarray(points_xy, np.float32)
    scores = np.asarray(support, np.float32)
    if points.shape != (21, 2) or scores.shape != (21,):
        raise ValueError("hand ROI expects [21,2] points and [21] support")
    in_source = (
        np.all(np.isfinite(points), axis=1)
        & np.isfinite(scores)
        & (points[:, 0] >= 0)
        & (points[:, 0] < source_width)
        & (points[:, 1] >= 0)
        & (points[:, 1] < source_height)
    )
    selected = in_source & (scores >= minimum_support)
    if np.count_nonzero(selected) < minimum_points:
        return None
    selected_points = points[selected]
    low = np.quantile(selected_points, 0.05, axis=0)
    high = np.quantile(selected_points, 0.95, axis=0)
    center = np.median(selected_points, axis=0)
    minimum_side = min(source_width, source_height) * minimum_side_fraction
    maximum_side = min(source_width, source_height) * maximum_side_fraction
    side = float(np.clip(np.max(high - low) * expansion, minimum_side, maximum_side))
    return HandRoi(
        center_x=float(center[0]),
        center_y=float(center[1]),
        side=side,
        source_width=source_width,
        source_height=source_height,
        support_count=int(np.count_nonzero(selected)),
    )


def crop_transform(roi: HandRoi, destination_size: int = 224) -> np.ndarray:
    """Return the source-to-crop affine used by Python and Android parity."""

    half = roi.side * 0.5
    source = np.asarray(
        [
            [roi.center_x - half, roi.center_y - half],
            [roi.center_x + half, roi.center_y - half],
            [roi.center_x - half, roi.center_y + half],
        ],
        np.float32,
    )
    last = float(destination_size - 1)
    destination = np.asarray([[0.0, 0.0], [last, 0.0], [0.0, last]], np.float32)
    return cv2.getAffineTransform(source, destination)


def crop_hand(image_bgr: np.ndarray, roi: HandRoi, destination_size: int = 224) -> np.ndarray:
    return cv2.warpAffine(
        image_bgr,
        crop_transform(roi, destination_size),
        (destination_size, destination_size),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )


def restore_crop_xy(points_xy: np.ndarray, roi: HandRoi, destination_size: int = 224) -> np.ndarray:
    points = np.asarray(points_xy, np.float32)
    if points.shape != (21, 2):
        raise ValueError("hand restore expects [21,2] points")
    inverse = cv2.invertAffineTransform(crop_transform(roi, destination_size))
    homogeneous = np.concatenate(
        [points, np.ones((points.shape[0], 1), np.float32)], axis=1
    )
    return (homogeneous @ inverse.T).astype(np.float32)

