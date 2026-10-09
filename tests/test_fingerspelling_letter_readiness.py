"""Focused tests for unused host assessment and human-label admission boundaries."""

from __future__ import annotations

import copy
from typing import Any

import numpy as np
import pytest

from pipeline.fingerspelling.input_evidence import assess
from pipeline.perception_vnext.recognition_schema import RAW_SCHEMA, RawSequence
from tools.fingerspelling.letter_evidence_review import (
    LABEL_SCHEMA,
    REQUEST_SCHEMA,
    select,
    validate_labels,
)


def raw(observed: list[list[bool]]) -> RawSequence:
    hands = np.asarray(observed, bool)
    n = len(hands)
    valid = np.repeat(hands[:, :, None], 21, axis=2)
    xy = np.where(valid[:, :, :, None], np.ones((n, 2, 21, 2), np.float32), np.nan)
    return RawSequence(
        metadata={"schema": RAW_SCHEMA, "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB"},
        frame_index=np.arange(n),
        timestamp_ms=np.arange(n, dtype=np.float64) * 160,
        source_size=np.tile([640, 480], (n, 1)),
        hand_xy=xy,
        hand_proposal_support=np.zeros((n, 2, 21)),
        hand_joint_valid=valid,
        hand_presence=np.zeros((n, 2)),
        hand_observed=hands,
        hand_proposal_present=hands,
        hand_roi_center_side=np.full((n, 2, 3), np.nan),
        hand_handedness_diagnostic=np.full((n, 2), np.nan),
        body_xy=np.full((n, 8, 2), np.nan),
        body_support=np.zeros((n, 8)),
        body_valid=np.zeros((n, 8), bool),
        body_available=np.zeros(n, bool),
    )


def test_absence_is_reported_without_modifying_observations() -> None:
    value = raw([[False, False]] * 4)
    original = value.hand_xy.copy()
    result = assess(value)
    assert result["refusal_reason"] == "NO_ACCEPTED_HAND_OBSERVATIONS"
    assert result["longest_missing_usable_hand_run"] == 4
    assert result["observations"] == 4
    assert np.array_equal(value.hand_xy, original, equal_nan=True)


def test_partial_missingness_is_not_a_guessed_rejection_threshold() -> None:
    value = raw([[True, False]] * 21 + [[False, False]] * 30)
    result = assess(value)
    assert not result["refusal_recommended"]
    assert result["any_usable_hand_observations"] == 21
    assert result["observations"] == 51
    assert result["recognition_quality"] == "NOT_ESTIMATED"


def test_observed_slots_are_not_counted_as_distinct_physical_hands() -> None:
    result = assess(raw([[True, True], [False, False], [True, False]]))
    assert result["any_usable_hand_observations"] == 2
    assert result["longest_missing_usable_hand_run"] == 1


def test_no_valid_geometry_is_distinct_from_no_accepted_hand() -> None:
    value = raw([[True, False]])
    value.hand_joint_valid[:] = False
    assert assess(value)["refusal_reason"] == "NO_VALID_HAND_GEOMETRY"


def test_single_nonfinite_timestamp_is_rejected() -> None:
    value = raw([[True, False]])
    value.timestamp_ms[:] = np.nan
    with pytest.raises(ValueError, match="Non-finite"):
        assess(value)


def request_and_review() -> tuple[dict[str, Any], dict[str, Any]]:
    request = dict(
        schema_version=REQUEST_SCHEMA,
        samples=[
            dict(
                sample_id="train01",
                split_role="TRAIN",
                normalized_transcript="JAZZ",
                frame_indices=[0, 2, 4, 6],
                timestamps_ms=[0, 80, 160, 240],
            )
        ],
    )
    reviews = dict(
        schema_version=LABEL_SCHEMA,
        request_sha256="frozen",
        reviews=[
            dict(
                sample_id="train01",
                reviewer_id="qualified-reviewer",
                review_status="REVIEWED",
                labels=[
                    dict(
                        letter="J",
                        start_frame_index=0,
                        end_frame_index=2,
                        candidate_slot=0,
                        crop_semantic_review="TRUSTED_HAND_WITH_REQUIRED_FINGERS",
                        label_source="HUMAN_RGB_REVIEW",
                        qualified_fingerspelling_review=True,
                    )
                ],
            )
        ],
    )
    return request, reviews


def test_human_review_is_valid_but_not_automatically_training_admitted() -> None:
    request, reviews = request_and_review()
    result = validate_labels(request, reviews, "frozen")
    assert result["verified_letter_labels"] == {"J": 1}
    assert result["training_admitted"] is False


@pytest.mark.parametrize("change", ["dev", "pseudo", "frame", "static_j", "untrusted", "duplicate"])
def test_invalid_supervision_is_rejected(change: str) -> None:
    request, reviews = request_and_review()
    label = reviews["reviews"][0]["labels"][0]
    if change == "dev":
        request["samples"][0]["split_role"] = "DEV"
    elif change == "pseudo":
        label["label_source"] = "CTC_PEAK"
    elif change == "frame":
        label["end_frame_index"] = 1
    elif change == "static_j":
        label["end_frame_index"] = 0
    elif change == "untrusted":
        label["crop_semantic_review"] = "FACE_OR_BACKGROUND"
    else:
        reviews["reviews"][0]["labels"].append(copy.deepcopy(label))
    with pytest.raises(ValueError):
        validate_labels(request, reviews, "frozen")


def test_selection_is_metadata_only_and_order_independent() -> None:
    policy = dict(
        maximum_transcript_length=20,
        stratum_quota={"DAUN": 1, "MacKenzie": 1},
        review_sequence_count=2,
        metadata_coverage_occurrences=3,
        selection_salt="test",
    )
    rows = [
        dict(
            sample_id="a",
            official_signer_id="one",
            source_stratum="DAUN",
            split_role="TRAIN",
            normalized_transcript="ABCDEFGHIJKLM",
        ),
        dict(
            sample_id="b",
            official_signer_id="two",
            source_stratum="MacKenzie",
            split_role="TRAIN",
            normalized_transcript="NOPQRSTUVWXYZ",
        ),
        dict(
            sample_id="sealed",
            official_signer_id="three",
            source_stratum="DAUN",
            split_role="TEST",
            normalized_transcript="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        ),
    ]
    assert select(rows, policy) == select(list(reversed(rows)), policy) == rows[:2]
