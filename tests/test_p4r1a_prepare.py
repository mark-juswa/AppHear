from __future__ import annotations

import numpy as np

from eval.runtime_diagnostics.p4r1a_prepare import diversity_sample, interaction_roi


def test_interaction_roi_is_bounded_and_deterministic() -> None:
    points = np.zeros((133, 2), dtype=np.float32)
    points[:] = np.nan
    points[5:11] = np.array(
        [[80, 100], [160, 100], [60, 160], [180, 160], [40, 220], [200, 220]],
        dtype=np.float32,
    )
    points[91:112] = np.array([[60 + index, 180 + index / 2] for index in range(21)])
    points[112:133] = np.array([[160 + index, 180 + index / 2] for index in range(21)])
    first = interaction_roi(points, np.array([True, True]), 240, 320)
    second = interaction_roi(points, np.array([True, True]), 240, 320)
    assert first == second
    assert 0 <= first["roi_x1"] < first["roi_x2"] <= 240
    assert 0 <= first["roi_y1"] < first["roi_y2"] <= 320
    assert first["roi_rule"] == "PRIMARY_CURRENT_FRAME_DWPOSE_INTERACTION_ENVELOPE"


def test_interaction_roi_falls_back_only_without_body_geometry() -> None:
    points = np.full((133, 2), np.nan, dtype=np.float32)
    result = interaction_roi(points, np.array([False, False]), 240, 320)
    assert (result["roi_x1"], result["roi_y1"], result["roi_x2"], result["roi_y2"]) == (0, 0, 240, 320)
    assert result["roi_rule"].startswith("FALLBACK_WHOLE_FRAME")


def test_diversity_sample_is_reproducible_and_unique() -> None:
    rows = [
        {"frame_id": f"f{i}", "signer_id": f"s{i % 3}", "sequence_id": f"q{i % 7}"}
        for i in range(30)
    ]
    first = diversity_sample(rows, 20, "TEST")
    second = diversity_sample(rows, 20, "TEST")
    assert [row["frame_id"] for row in first] == [row["frame_id"] for row in second]
    assert len({row["frame_id"] for row in first}) == 20
