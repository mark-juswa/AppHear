from pipeline.rgb.e6_negative_upload_review import (
    PROPOSED_SPLIT,
    _canonical_category,
    _sample_indexes,
    _session_decisions,
    _spot_review_queue,
)


def test_category_mapping_preserves_oov_label() -> None:
    assert _canonical_category("Idle_Hands") == ("P1_IDLE_HANDS", "")
    assert _canonical_category("Transition_or_Partial") == ("TRANSITION_PARTIAL", "")
    assert _canonical_category("morning") == ("OOV_SIGN", "MORNING")


def test_three_deterministic_samples_per_session() -> None:
    rows = [
        {
            "session_id": "S1",
            "raw_video_path": f"clip_{index:02d}.mp4",
        }
        for index in range(20)
    ]
    queue = _spot_review_queue(rows)
    assert [row["raw_video_path"] for row in queue] == [
        "clip_00.mp4",
        "clip_10.mp4",
        "clip_19.mp4",
    ]
    assert _sample_indexes(1) == [0]


def test_batch_requires_three_completed_accepts() -> None:
    accepted = [
        {"session_id": "S1", "review_status": "done", "review_decision": "accept"}
        for _ in range(3)
    ]
    blocked = accepted[:2] + [
        {"session_id": "S1", "review_status": "done", "review_decision": "reject"}
    ]
    assert _session_decisions(accepted) == {"S1": "accepted_batch"}
    assert _session_decisions(blocked) == {"S1": "full_session_review_required"}


def test_proposed_split_is_fresh_negative_only() -> None:
    assert PROPOSED_SPLIT == "test_fresh_negative_provisional"
