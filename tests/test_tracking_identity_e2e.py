"""Focused tests for E2e-A coordinate and anatomical-hand identity logic."""

from __future__ import annotations

from dataclasses import asdict
from math import isclose
from pathlib import Path

from pipeline.tracking.e2e import run_smoke
from pipeline.tracking.identity import (
    AssociationConfig,
    Box,
    HandCandidate,
    Point,
    TemporalState,
    canonicalize_pose_points,
    direct_label_assignment,
    mirror_box,
    pose_assignment,
    temporal_pose_assignment,
)


def _config() -> AssociationConfig:
    return AssociationConfig(
        pose_weight=1.0,
        temporal_weight=0.65,
        confidence_weight=0.05,
        max_cost=0.60,
        max_track_age_ms=250,
    )


def _hand(candidate_id: str, center_x: float, label: str) -> HandCandidate:
    return HandCandidate(
        candidate_id,
        Box(center_x - 0.05, 0.4, center_x + 0.05, 0.6),
        label,
        0.9,
    )


def test_mirror_box_is_an_involution() -> None:
    box = Box(0.10, 0.20, 0.35, 0.60)
    mirrored_twice = mirror_box(mirror_box(box))
    assert all(
        isclose(actual, expected, abs_tol=1e-12)
        for actual, expected in zip(
            asdict(mirrored_twice).values(), asdict(box).values(), strict=True
        )
    )


def test_mirrored_pose_coordinates_and_sides_are_canonicalized() -> None:
    source = {
        "right": Point(0.20, 0.50),
        "left": Point(0.80, 0.50),
    }
    expected = {
        "left": Point(0.80, 0.50),
        "right": Point(0.20, 0.50),
    }
    actual = canonicalize_pose_points(source, True)
    assert actual.keys() == expected.keys()
    for side in expected:
        assert isclose(actual[side].x, expected[side].x, abs_tol=1e-12)
        assert isclose(actual[side].y, expected[side].y, abs_tol=1e-12)


def test_direct_and_swapped_labels_are_explicit() -> None:
    candidate = _hand("anatomical-left", 0.75, "Left")
    assert direct_label_assignment([candidate], False)["left"] == candidate
    assert direct_label_assignment([candidate], True)["right"] == candidate


def test_pose_assignment_ignores_unreliable_handedness_label() -> None:
    left = _hand("left", 0.75, "Right")
    right = _hand("right", 0.25, "Left")
    assigned = pose_assignment(
        [right, left],
        {"left": Point(0.75, 0.5), "right": Point(0.25, 0.5)},
        _config(),
    )
    assert assigned == {"left": left, "right": right}


def test_temporal_assignment_survives_short_pose_dropout() -> None:
    state = TemporalState()
    first_left = _hand("left-0", 0.70, "Right")
    first_right = _hand("right-0", 0.30, "Left")
    temporal_pose_assignment(
        [first_left, first_right],
        {"left": Point(0.70, 0.5), "right": Point(0.30, 0.5)},
        0,
        state,
        _config(),
    )
    next_left = _hand("left-1", 0.68, "Right")
    next_right = _hand("right-1", 0.32, "Left")
    assigned = temporal_pose_assignment(
        [next_right, next_left], {}, 67, state, _config()
    )
    assert assigned == {"left": next_left, "right": next_right}


def test_smoke_writes_only_bounded_fixture_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "smoke"
    report = run_smoke(Path("pipeline/config/identity_e2e.yaml"), output)
    assert report["smoke_passed"]
    assert report["fixture_frames"] == 6
    assert report["metrics"]["pose_temporal"]["identity_accuracy"] == 1.0
    assert (output / "fixture_summary.json").is_file()
    assert (output / "run_config.json").is_file()
    assert (output / "annotation_template.csv").is_file()
