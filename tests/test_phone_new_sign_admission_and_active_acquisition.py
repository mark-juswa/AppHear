from __future__ import annotations

import pytest

from eval.runtime_diagnostics.phone_new_sign_admission_and_active_acquisition_validation import (
    CONFIRMED_NON_SIGN,
    EARLY_SIGN_FRAGMENT_OR_WRONG_EPISODE,
    GENUINE_SIGN_ONSET,
    UNCERTAIN,
    event_evidence,
    refined_label,
)


def observation(index: int, state: int, *, hand: bool, body: bool) -> dict[str, object]:
    return {
        "source_index": index,
        "argmax_state": state,
        "active_probability": 0.8 if state == 1 else 0.1,
        "left_observed": hand,
        "right_observed": False,
        "body_available": body,
        "left_proposal": True,
        "right_proposal": False,
    }


def test_refined_labels_cover_all_22_events_without_using_early_fragment_as_negative() -> None:
    covered = (
        CONFIRMED_NON_SIGN | GENUINE_SIGN_ONSET | EARLY_SIGN_FRAGMENT_OR_WRONG_EPISODE | UNCERTAIN
    )
    assert covered == set(range(1, 23))
    assert refined_label(20) == "EARLY_SIGN_FRAGMENT_OR_WRONG_EPISODE"
    assert 20 not in CONFIRMED_NON_SIGN
    with pytest.raises(ValueError, match="UNREVIEWED_EVENT_ID"):
        refined_label(23)


def test_support_can_arrive_on_second_active_without_rewriting_first_onset() -> None:
    observations = {
        10: observation(10, 1, hand=False, body=False),
        11: observation(11, 1, hand=False, body=True),
    }
    event = {
        "event_id": 3,
        "logical_active_start_index": 10,
        "logical_active_end_index": 11,
        "logical_active_start_ms": 100.0,
        "logical_active_end_ms": 300.0,
    }
    result = event_evidence(event, observations)
    assert result["first_observation_direct_support"] is False
    assert result["direct_support_within_first_two_active_observations"] is True
    assert result["logical_active_start_index"] == 10


def test_post_after_one_active_is_not_misrepresented_as_active_persistence() -> None:
    observations = {
        20: observation(20, 1, hand=True, body=False),
        21: observation(21, 2, hand=True, body=False),
    }
    event = {
        "event_id": 18,
        "logical_active_start_index": 20,
        "logical_active_end_index": 20,
        "logical_active_start_ms": 100.0,
        "logical_active_end_ms": 100.0,
    }
    result = event_evidence(event, observations)
    assert result["first_observation_direct_support"] is True
    assert result["two_consecutive_active_observations"] is False
