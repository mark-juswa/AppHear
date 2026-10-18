"""Stage attribution order for the paired phone replay (pure logic; no models or captures)."""

from __future__ import annotations

from eval.runtime_diagnostics.phone_replay_compare import classify

BASE = dict(
    adequate=True,
    acquired=True,
    credited_word=None,
    overlapped=False,
    all_active_in_rearm=False,
    gloss="HOME",
    oracle_correct=True,
)


def stage(**changes: object) -> str:
    return classify(**{**BASE, **changes})  # type: ignore[arg-type]


def test_correct_word_wins_even_with_weak_perception() -> None:
    assert stage(credited_word="HOME", adequate=False) == "CORRECT"


def test_wrong_word_splits_window_from_classifier_by_the_ideal_window() -> None:
    assert stage(credited_word="LUNCH1") == "WINDOW"
    assert stage(credited_word="LUNCH1", oracle_correct=False) == "CLASSIFIER"


def test_no_event_stages_follow_the_pipeline_order() -> None:
    assert stage(acquired=False) == "S2_NOT_ACQUIRED"
    assert stage(overlapped=True) == "MERGED"
    assert stage(all_active_in_rearm=True) == "LIFECYCLE_SWALLOWED"
    assert stage() == "LIFECYCLE_DISCARDED"


def test_inadequate_perception_is_reported_first_for_any_failure() -> None:
    assert stage(acquired=False, adequate=False) == "PERCEPTION"
    assert stage(credited_word="NICE", oracle_correct=False, adequate=False) == "PERCEPTION"
