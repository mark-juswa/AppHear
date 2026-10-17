"""IPN HandS timeline mapping and subject handling (no video, no models)."""

from __future__ import annotations

import numpy as np

from eval.runtime_diagnostics import ipn_hand_feasibility as ipn


def test_rows_map_to_one_based_inclusive_hands_frames_by_time() -> None:
    # 30 fps timeline: frame k covers t = (k - 1) / 30 s. Segments are inclusive on both ends.
    segments = [(0, 1, 30), (5, 31, 60), (0, 61, 300)]
    t = np.asarray([0.0, 966.7, 1000.0, 1966.7, 2000.0, 9000.0]) + 12345.0  # arbitrary origin
    cls = ipn.row_classes(t, segments, margin_ms=0.0)
    assert cls.tolist() == [0, 0, 5, 5, 0, 0]


def test_nog_rows_near_a_gesture_become_transition() -> None:
    segments = [(0, 1, 30), (5, 31, 60), (0, 61, 300)]
    t = np.asarray([0.0, 400.0, 2400.0, 3000.0, 9000.0])
    cls = ipn.row_classes(t, segments, margin_ms=500.0)
    # 400 ms -> frame 13, 18 frames (600 ms) before the gesture starts: inside the 15-frame pad? no.
    assert cls[0] == ipn.NOG
    assert cls[1] == ipn.NOG
    assert cls[2] == ipn.TRANSITION  # 2400 ms -> frame 73, 12 frames after the gesture ends
    assert cls[3] == ipn.NOG and cls[4] == ipn.NOG


def test_subject_is_group_plus_number_and_one_video_per_subject() -> None:
    videos = ["4CM11_19_R_#17", "4CM11_19_R_#18", "4CM11_1_R_#13", "4CM11_1_R_#14"]
    assert ipn.subject_of("4CM11_19_R_#17") == "4CM11_19"
    assert ipn.select_videos(None, videos) == ["4CM11_1_R_#13", "4CM11_19_R_#17"]
