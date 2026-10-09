"""The independent negative reviewer must exclude intended sign attempts."""

from __future__ import annotations

import pytest

from eval.runtime_diagnostics.s2_r2_phone_non_sign_review import add_interval


def test_non_sign_review_rejects_attempt_overlap_and_uncertain_notes(tmp_path):
    prepared = {
        "path": tmp_path / "review.json",
        "document": {
            "visual_observation_count": 20,
            "confirmed_non_sign_intervals": [],
            "full_session_visual_reviewed": False,
        },
        "attempts": [{"start_index": 5, "end_index": 10}],
    }
    with pytest.raises(ValueError, match="OVERLAPS_SIGN_ATTEMPT"):
        add_interval(prepared, 4, 6, "ordinary motion")
    with pytest.raises(ValueError, match="BEHAVIOR_NOTE_REQUIRED"):
        add_interval(prepared, 0, 2, " ")
    result = add_interval(prepared, 0, 2, "neutral waiting")
    assert result == {"start_index": 0, "end_index": 2, "behavior_note": "neutral waiting"}
    with pytest.raises(ValueError, match="INTERVAL_OVERLAP"):
        add_interval(prepared, 2, 3, "hand adjustment")
