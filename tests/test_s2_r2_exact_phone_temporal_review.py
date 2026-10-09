from __future__ import annotations

from pathlib import Path

from eval.runtime_diagnostics import s2_r2_exact_phone_temporal_review as exact_review


def test_exact_profile_uses_all_six_governed_attempts() -> None:
    assert exact_review.SESSION_ID == "session_20260921T153138Z"
    assert [item[:2] for item in exact_review.SELECTED_ATTEMPTS] == [
        (1, "HELLO"),
        (2, "HELLO"),
        (3, "HOME"),
        (4, "HOME"),
        (5, "TABLE"),
        (6, "TABLE"),
    ]


def test_exact_linkage_covers_every_review_visual_observation() -> None:
    exact_review._configure_review_profile(exact_review.OUTPUT_ROOT)
    attempts = exact_review.review.load_selected_attempts(exact_review.SESSION_ROOT)
    _, by_timestamp_ns = exact_review._load_linkage()
    reviewed_timestamps = {
        int(frame["source_timestamp_ns"])
        for attempt in attempts
        for frame in attempt["frames"]
    }
    assert len(reviewed_timestamps) == 232
    assert reviewed_timestamps <= set(by_timestamp_ns)


def test_configure_profile_keeps_output_isolated(tmp_path: Path) -> None:
    exact_review._configure_review_profile(tmp_path)
    assert exact_review.review.SESSION_ROOT == exact_review.SESSION_ROOT
    assert exact_review.review.OUTPUT_ROOT == tmp_path
    assert exact_review.review.SELECTED_ATTEMPTS == exact_review.SELECTED_ATTEMPTS
