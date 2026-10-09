from eval.runtime_diagnostics.p4a2_fresh_evidence_review import semantic_counts, validate_label


def complete(**updates):
    row = {
        "any_hand_visible": "NO", "visible_left": "NO", "visible_right": "NO",
        "zero_hand": "YES", "rest": "YES", "entering": "NO", "leaving": "NO",
        "left_visibility_quality": "NOT_APPLICABLE", "right_visibility_quality": "NOT_APPLICABLE",
        "blur": "NO", "occlusion": "NO", "edge_clipped": "NO", "partial_visibility": "NO",
        "crossing": "NO", "hand_hand_contact": "NO", "hand_body_contact": "NO",
        "reviewer_status": "COMPLETE",
    }
    row.update(updates)
    return row


def test_zero_hand_consistency():
    assert not validate_label(complete())
    assert validate_label(complete(visible_left="YES"))


def test_semantic_counts_observations_and_frames():
    rows = [
        complete(),
        complete(any_hand_visible="YES", visible_left="YES", zero_hand="NO", rest="NO", left_visibility_quality="WEAK"),
        complete(any_hand_visible="YES", visible_left="YES", visible_right="YES", zero_hand="NO", rest="NO", left_visibility_quality="CLEAR", right_visibility_quality="CLEAR"),
    ]
    counts = semantic_counts(rows)
    assert counts["visible_hand_observations"] == 3
    assert counts["one_hand_visible_observations"] == 1
    assert counts["weak_one_hand_observations"] == 1
    assert counts["complete_two_hand_frames"] == 1
    assert counts["zero_hand_frames"] == 1
