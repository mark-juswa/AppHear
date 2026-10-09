from __future__ import annotations

import numpy as np

from pipeline.perception_vnext.hand_roi import (
    build_hand_roi,
    crop_transform,
    restore_crop_xy,
)


def test_roi_rejects_insufficient_current_frame_support() -> None:
    points = np.zeros((21, 2), np.float32)
    support = np.zeros((21,), np.float32)
    assert build_hand_roi(points, support, 480, 640) is None


def test_roi_and_restore_are_inverse() -> None:
    points = np.stack(
        [np.linspace(120, 180, 21), np.linspace(200, 260, 21)], axis=1
    ).astype(np.float32)
    support = np.ones((21,), np.float32)
    roi = build_hand_roi(points, support, 480, 640)
    assert roi is not None
    transform = crop_transform(roi)
    homogeneous = np.concatenate([points, np.ones((21, 1), np.float32)], axis=1)
    crop_points = homogeneous @ transform.T
    restored = restore_crop_xy(crop_points.astype(np.float32), roi)
    np.testing.assert_allclose(restored, points, atol=1e-4)
