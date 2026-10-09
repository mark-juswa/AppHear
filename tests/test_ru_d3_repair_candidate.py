from __future__ import annotations

from pipeline.splits.ru_d3_repair_candidate import _initial_action, _recoverable


def test_ru_d3_initial_decisions_preserve_known_exclusions() -> None:
    know_bad = {
        "canonical_gloss": "KNOW",
        "review_index": "37",
        "source_dataset": "ASL_CITIZEN",
        "manual_classification": "INCOMPLETE_OR_BAD_SIGN",
    }
    leave_wrong = {
        "canonical_gloss": "LEAVE",
        "review_index": "14",
        "source_dataset": "ASL_CITIZEN",
        "manual_classification": "WRONG_VARIANT",
    }
    assert _initial_action(know_bad)[0] == "EXCLUDE"
    assert _initial_action(leave_wrong)[0] == "EXCLUDE"


def test_ru_d3_unbounded_know_requires_reextraction() -> None:
    row = {
        "canonical_gloss": "KNOW",
        "review_index": "60",
        "source_dataset": "APPHEAR_CAPTURE",
        "manual_classification": "INCOMPLETE_OR_BAD_SIGN",
    }
    assert _initial_action(row)[0] == "REEXTRACT"


def test_ru_d3_landmark_recovery_gates_are_class_specific() -> None:
    assert _recoverable("WHO", True, 20, 0.45, 0.0) == (True, "")
    assert not _recoverable("WHO", True, 20, 0.44, 0.0)[0]
    assert _recoverable("LEAVE", True, 20, 0.50, 0.20) == (True, "")
    assert not _recoverable("LEAVE", True, 20, 0.80, 0.19)[0]


def test_ru_d3_rejects_invalid_or_truncated_spans() -> None:
    assert not _recoverable("KNOW", False, 20, 1.0, 0.0)[0]
    assert not _recoverable("KNOW", True, 97, 1.0, 0.0)[0]
