import numpy as np

from eval.runtime_diagnostics.p3_dwpose_temporal import (
    BONES,
    COLLAPSE_MEDIAN_BONE_TORSO,
    body_scale,
    hand_geometry,
)


def test_body_scale_has_image_fallback() -> None:
    keypoints = np.zeros((133, 2), dtype=np.float64)
    assert body_scale(keypoints, 640, 480) == 80.0


def test_hand_geometry_uses_frozen_twenty_bones() -> None:
    points = np.stack([np.arange(21), np.zeros(21)], axis=1).astype(np.float64)
    result = hand_geometry(points, 10.0)
    assert BONES.shape == (20, 2)
    assert result["bone_lengths"].shape == (20,)
    assert not result["collapse"]


def test_collapsed_hand_is_diagnostic_only() -> None:
    points = np.zeros((21, 2), dtype=np.float64)
    result = hand_geometry(points, 100.0)
    assert result["median_bone"] < COLLAPSE_MEDIAN_BONE_TORSO
    assert result["collapse"]
