from __future__ import annotations

import numpy as np

from eval.runtime_diagnostics.a2_identity_experiment import _annotation_error
from eval.runtime_diagnostics.a2_identity_tracker import (
    AnatomicalIdentityTracker,
    AnatomicalSide,
    DirectObservation,
    MediaPipeSlot,
    observations_from_feature,
)


def _hand(x: float, y: float = 0.0) -> np.ndarray:
    landmarks = np.zeros((21, 3), dtype=np.float64)
    landmarks[:, 0] = x + np.linspace(0.0, 0.05, 21)
    landmarks[:, 1] = y + np.linspace(0.0, 0.03, 21)
    return landmarks


def test_tracker_preserves_identity_when_mediapipe_labels_swap() -> None:
    tracker = AnatomicalIdentityTracker()
    first = tracker.update(
        1_000_000_000,
        (
            DirectObservation(MediaPipeSlot.RIGHT, 1_000_000_000, _hand(-0.5)),
            DirectObservation(MediaPipeSlot.LEFT, 1_000_000_000, _hand(0.5)),
        ),
    )
    assert first.left is not None and first.left.slot == MediaPipeSlot.RIGHT
    assert first.right is not None and first.right.slot == MediaPipeSlot.LEFT

    swapped = tracker.update(
        1_100_000_000,
        (
            DirectObservation(MediaPipeSlot.LEFT, 1_100_000_000, _hand(-0.48)),
            DirectObservation(MediaPipeSlot.RIGHT, 1_100_000_000, _hand(0.48)),
        ),
    )
    assert swapped.left is not None and swapped.left.slot == MediaPipeSlot.LEFT
    assert swapped.right is not None and swapped.right.slot == MediaPipeSlot.RIGHT
    assert swapped.ambiguous_slots == ()


def test_unmirrored_front_camera_prior_inverts_mediapipe_handedness() -> None:
    tracker = AnatomicalIdentityTracker()
    assignment = tracker.update(
        1_000_000_000,
        (DirectObservation(MediaPipeSlot.LEFT, 1_000_000_000, _hand(0.4)),),
        {
            AnatomicalSide.LEFT: np.asarray([-0.4, 0.0]),
            AnatomicalSide.RIGHT: np.asarray([0.4, 0.0]),
        },
    )
    assert assignment.left is None
    assert assignment.right is not None
    assert assignment.right.slot == MediaPipeSlot.LEFT


def test_tracker_marks_contact_assignment_ambiguous_without_updating() -> None:
    tracker = AnatomicalIdentityTracker()
    tracker.update(
        1_000_000_000,
        (
            DirectObservation(MediaPipeSlot.LEFT, 1_000_000_000, _hand(-0.4)),
            DirectObservation(MediaPipeSlot.RIGHT, 1_000_000_000, _hand(0.4)),
        ),
    )
    contact = tracker.update(
        1_100_000_000,
        (
            DirectObservation(MediaPipeSlot.LEFT, 1_100_000_000, _hand(0.0)),
            DirectObservation(MediaPipeSlot.RIGHT, 1_100_000_000, _hand(0.0)),
        ),
    )
    assert contact.left is None
    assert contact.right is None
    assert set(contact.ambiguous_slots) == {MediaPipeSlot.LEFT, MediaPipeSlot.RIGHT}


def test_identity_only_tracker_never_carries_a_missing_hand() -> None:
    tracker = AnatomicalIdentityTracker()
    tracker.update(
        1_000_000_000,
        (DirectObservation(MediaPipeSlot.LEFT, 1_000_000_000, _hand(-0.2)),),
    )
    missing = tracker.update(1_100_000_000, ())
    assert missing.left is None
    assert missing.right is None
    assert missing.ambiguous_slots == ()


def test_decode_observations_uses_nonzero_hand_blocks_only() -> None:
    feature = np.zeros(258, dtype=np.float64)
    feature[63:126] = _hand(0.2).reshape(-1)
    observations = observations_from_feature(feature, 10)
    assert len(observations) == 1
    assert observations[0].slot == MediaPipeSlot.RIGHT


def _annotation() -> dict[str, str]:
    return {
        "sample_id": "frame",
        "review_status": "accepted",
        "visible_left": "no",
        "visible_right": "yes",
        "mp_left_identity": "none",
        "mp_right_identity": "right",
        "recoverable_left": "not_applicable",
        "recoverable_right": "not_applicable",
        "hand_hand_contact": "no",
        "hand_body_contact": "no",
        "crossing_or_midline": "no",
        "leaving_frame": "no",
        "no_hand_rest": "no",
        "notes": "",
    }


def test_detected_anatomical_hand_makes_recovery_not_applicable() -> None:
    index = {"direct_mp_left": "false", "direct_mp_right": "true"}
    assert _annotation_error(_annotation(), index) is None


def test_ambiguous_detection_requires_visible_missing_hand_review() -> None:
    index = {"direct_mp_left": "false", "direct_mp_right": "true"}
    annotation = _annotation()
    annotation["mp_right_identity"] = "ambiguous"
    annotation["recoverable_right"] = "uncertain"
    assert _annotation_error(annotation, index) is None
