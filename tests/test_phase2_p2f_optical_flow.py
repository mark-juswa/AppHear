from __future__ import annotations

import cv2
import numpy as np

from pipeline.rgb.phase2_p2f_optical_flow import FlowState, _features_in_box, _flow_box


def test_flow_box_tracks_translated_texture() -> None:
    previous = np.zeros((120, 160), dtype=np.uint8)
    for x in range(45, 76, 10):
        for y in range(35, 66, 10):
            cv2.circle(previous, (x, y), 2, 255, -1)
    transform = np.float32([[1, 0, 7], [0, 1, 4]])
    current = cv2.warpAffine(previous, transform, (160, 120))
    box = (35.0, 25.0, 85.0, 75.0)
    points = _features_in_box(previous, box)

    result = _flow_box(previous, current, FlowState(box, points, 0))

    assert result is not None
    tracked, _ = result
    assert np.allclose(tracked, (42.0, 29.0, 92.0, 79.0), atol=0.75)


def test_flow_box_rejects_insufficient_texture() -> None:
    frame = np.zeros((80, 80), dtype=np.uint8)
    result = _flow_box(
        frame,
        frame,
        FlowState((10.0, 10.0, 30.0, 30.0), np.empty((0, 1, 2), dtype=np.float32), 0),
    )
    assert result is None
