"""Compact capture/review integrity tests, not recorded signing or ASL accuracy."""

from __future__ import annotations

import copy

import pytest

from eval.runtime_diagnostics import continuous_transition_diagnostics as diag
from eval.runtime_diagnostics import transition_protocols as profiles


def labels_and_integrity() -> tuple[dict, dict]:
    profile = profiles.compact_protocol()
    ranges = [
        {"block": block, "start_index": i * 20, "end_index": i * 20 + 19}
        for i, block in enumerate(profile.blocks)
    ]
    integrity = {**profile.metadata(), "observations_sha256": "source", "blocks": ranges}
    offsets = {block: i * 20 for i, block in enumerate(profile.blocks)}
    labels = {
        **profile.metadata(),
        "schema": profile.label_schema,
        "session_id": "session",
        "evidence_sha256": "source",
        "reviewer": "reviewer",
        "blinded_to_predictions": True,
        "reviewed_blocks": list(profile.blocks),
        "signs": [
            {
                "condition": block,
                "ordinal": ordinal,
                "gloss": gloss,
                "start_index": offsets[block] + 1 + (ordinal - 1) * 5,
                "end_index": offsets[block] + 3 + (ordinal - 1) * 5,
                "judgment": "GENUINE_SIGN",
            }
            for block, glosses in profile.positive_sequences
            for ordinal, gloss in enumerate(glosses, 1)
        ],
        "negative_intervals": [
            {
                "block": "D_SIGN_THEN_HOLD",
                "start_index": 70,
                "end_index": 75,
                "judgment": "CONFIRMED_NON_SIGN",
            },
            {
                "block": "E_ORDINARY_MOVEMENT",
                "start_index": 82,
                "end_index": 89,
                "judgment": "CONFIRMED_NON_SIGN",
            },
        ],
    }
    return labels, integrity


def test_canonical_profile_has_seven_signs_including_adjacent_repeat() -> None:
    profile = profiles.compact_protocol()
    assert len(profile.blocks) == 5
    assert sum(len(glosses) for _, glosses in profile.positive_sequences) == 7
    assert dict(profile.positive_sequences)["C_REPEAT_HANDS_UP"] == ("HELLO", "HELLO")
    assert profiles.from_identity({}) == profiles.LEGACY
    assert len(profiles.LEGACY.blocks) == 7
    assert profiles.LEGACY.label_schema != profile.label_schema


@pytest.mark.parametrize("defect", ["id", "hash", "parallel", "baseline", "proficiency"])
def test_compact_capture_identity_is_bound_to_serial_integrated_baseline(defect: str) -> None:
    profile = profiles.compact_protocol()
    declared = {
        **profile.metadata(),
        "comparison_baseline_sha": "e196a8d501386091eae52f59df0fa349e26b43e2",
        "transition_label_schema": profile.label_schema,
        "stage1_parallel_hands_enabled": False,
        "declared_signer_proficiency": "UNKNOWN",
    }
    assert profiles.from_identity(declared) == profile
    changes = {
        "id": ("transition_protocol_id", "OTHER"),
        "hash": ("transition_protocol_sha256", "bad"),
        "parallel": ("stage1_parallel_hands_enabled", True),
        "baseline": ("comparison_baseline_sha", "old"),
        "proficiency": ("declared_signer_proficiency", "ACCURATE"),
    }
    key, value = changes[defect]
    declared[key] = value
    with pytest.raises(ValueError, match="COMPACT_CAPTURE_IDENTITY_MISMATCH"):
        profiles.from_identity(declared)


def test_compact_review_accepts_explicit_uncertainty_without_fabricated_bounds() -> None:
    labels, integrity = labels_and_integrity()
    diag.validate_labels(labels, integrity, 100, "session")
    labels["signs"][4].update(start_index=None, end_index=None, judgment="UNCERTAIN")
    diag.validate_labels(labels, integrity, 100, "session")


@pytest.mark.parametrize(
    "defect",
    [
        "schema",
        "profile",
        "repeat",
        "missing_block",
        "unblinded",
        "hold_overlap",
        "hold_before",
        "duplicate_negative",
    ],
)
def test_invalid_reviews_are_rejected(defect: str) -> None:
    labels, integrity = labels_and_integrity()
    if defect == "schema":
        labels["schema"] = diag.LABEL_SCHEMA
    elif defect == "profile":
        labels["transition_protocol_sha256"] = "wrong"
    elif defect == "repeat":
        labels["signs"][5]["gloss"] = "HOME"
    elif defect == "missing_block":
        labels["reviewed_blocks"].pop()
    elif defect == "unblinded":
        labels["blinded_to_predictions"] = False
    elif defect == "hold_overlap":
        labels["negative_intervals"][0]["start_index"] = 62
    elif defect == "hold_before":
        labels["negative_intervals"][0].update(start_index=60, end_index=60)
    elif defect == "duplicate_negative":
        labels["negative_intervals"].append(copy.deepcopy(labels["negative_intervals"][-1]))
    with pytest.raises(ValueError):
        diag.validate_labels(labels, integrity, 100, "session")


def test_two_repeat_events_are_not_collapsed_into_one_evaluation_result() -> None:
    attempts = [
        {
            "condition": "C_REPEAT_HANDS_UP",
            "ordinal": ordinal,
            "gloss": "HELLO",
            "judgment": "GENUINE_SIGN",
            "events": [
                {"event_id": ordinal, "top1_gloss": "HELLO", "shared_between_physical_signs": False}
            ],
        }
        for ordinal in (1, 2)
    ]
    result = diag.compact_outcomes(
        attempts, [{"event_id": i, "top1_gloss": "HELLO"} for i in (1, 2)]
    )
    assert result["adjacent_repeat_has_two_distinct_events"] is True
    assert result["repeat_event_glosses"] == ["HELLO", "HELLO"]
    assert result["normal_app_sentence_delivery"] == "NOT_MEASURED_DIAGNOSTIC_ACTIVITY"
    assert result["accuracy_claim"] == "NONE_SINGLE_DESIGN_COHORT"


def test_shared_event_is_merged_not_two_recognitions() -> None:
    attempts = [
        {
            "condition": "C_REPEAT_HANDS_UP",
            "ordinal": i,
            "gloss": "HELLO",
            "judgment": "GENUINE_SIGN",
            "events": [
                {"event_id": 1, "top1_gloss": "HELLO", "shared_between_physical_signs": True}
            ],
        }
        for i in (1, 2)
    ]
    result = diag.compact_outcomes(attempts, [{"event_id": 1, "top1_gloss": "HELLO"}])
    assert result["adjacent_repeat_has_two_distinct_events"] is False
    assert [x["outcome"] for x in result["physical_signs"]] == ["MERGED_EVENT", "MERGED_EVENT"]


def test_classifier_error_is_separate_from_missing_event() -> None:
    attempts = [
        {
            "condition": "A_HANDS_DOWN",
            "ordinal": 1,
            "gloss": "HELLO",
            "judgment": "GENUINE_SIGN",
            "events": [
                {"event_id": 1, "top1_gloss": "HOME", "shared_between_physical_signs": False}
            ],
        },
        {
            "condition": "A_HANDS_DOWN",
            "ordinal": 2,
            "gloss": "HOME",
            "judgment": "GENUINE_SIGN",
            "events": [],
        },
    ]
    result = diag.compact_outcomes(attempts, [{"event_id": 1, "top1_gloss": "HOME"}])
    assert [x["outcome"] for x in result["physical_signs"]] == [
        "DISTINCT_EVENT_CLASSIFICATION_MISMATCH",
        "NO_COMPLETED_EVENT",
    ]


def test_early_episode_is_not_credited_as_a_correct_distinct_sign() -> None:
    attempts = [
        {
            "condition": "B_HANDS_UP",
            "ordinal": 1,
            "gloss": "HELLO",
            "judgment": "GENUINE_SIGN",
            "classification": ["EARLY_OR_WRONG_EPISODE"],
            "events": [
                {"event_id": 1, "top1_gloss": "HELLO", "shared_between_physical_signs": False}
            ],
        },
    ]
    result = diag.compact_outcomes(attempts, [{"event_id": 1, "top1_gloss": "HELLO"}])
    assert result["physical_signs"][0]["outcome"] == "OVERLAPPING_EARLY_EPISODE_REVIEW_REQUIRED"


def test_compact_evaluator_includes_adjacent_repeat_transition_and_hold_sign() -> None:
    labels, integrity = labels_and_integrity()
    diag.validate_labels(labels, integrity, 100, "session")
    rows = [
        {
            "source_index": i,
            "source_timestamp_ms": i * 200.0,
            "argmax_state": 0,
            "pre_probability": 0.98,
            "active_probability": 0.01,
            "post_probability": 0.01,
            "event_state_before": "IDLE",
            "event_state_after": "IDLE",
            "event_action": "NO_CHANGE",
            "candidate_open_index": None,
            "candidate_active_span_ms": None,
            "rearm_reason": None,
        }
        for i in range(100)
    ]
    result = diag.evaluate(
        rows, [], labels, [], 133.308, 533.232, protocol=profiles.compact_protocol()
    )
    assert [t["condition"] for t in result["transitions"]] == [
        "A_HANDS_DOWN",
        "B_HANDS_UP",
        "C_REPEAT_HANDS_UP",
    ]
    assert len(result["compact_outcomes"]["physical_signs"]) == 7
    assert len(result["reviewed_negatives"]) == 2
    assert result["compact_outcomes"]["adjacent_repeat_has_two_distinct_events"] is False
