from __future__ import annotations

from eval.runtime_diagnostics.phase5_1_offline_segmenter import load_calibration
from eval.runtime_diagnostics.phase5_1s_global_end_conflict_attribution import (
    _minimal_disjoint_dimensions,
    build_threshold_space,
)


def test_threshold_space_is_the_frozen_phase5_1_empirical_domain() -> None:
    attempts = load_calibration()
    space = build_threshold_space(attempts)

    assert len(space.candidates["h_refined_body"]) == 37
    assert len(space.candidates["h_refined_image"]) == 37
    assert len(space.candidates["h_proposal_image"]) == 177
    assert len(space.candidates["l_body"]) == 157
    assert space.size == 1_028_193
    assert len(space.motion_masks) == 5


def test_disjoint_projection_reports_exact_signal_dimension() -> None:
    attempts = load_calibration()
    space = build_threshold_space(attempts)
    left = space.threshold_indices["h_refined_body"] == 0
    right = space.threshold_indices["h_refined_body"] == 1

    assert _minimal_disjoint_dimensions(space, left, right) == [
        ["h_refined_body"]
    ]
