from pipeline.rgb.e6_existing_negative_source_search import (
    _normalize_gloss,
    _round_robin_unique_glosses,
)


def test_round_robin_selection_balances_signers_and_uses_unique_glosses() -> None:
    rows = [
        {"participant_id": "P1", "video_file": "a.mp4", "canonical_gloss": "A"},
        {"participant_id": "P1", "video_file": "b.mp4", "canonical_gloss": "B"},
        {"participant_id": "P2", "video_file": "c.mp4", "canonical_gloss": "C"},
        {"participant_id": "P2", "video_file": "d.mp4", "canonical_gloss": "D"},
    ]

    selected = _round_robin_unique_glosses(rows, 4)

    assert [row["participant_id"] for row in selected] == ["P1", "P2", "P1", "P2"]
    assert len({row["canonical_gloss"] for row in selected}) == 4


def test_gloss_normalization_matches_product_core_contract() -> None:
    assert _normalize_gloss("WASH 2") == "WASH2"
    assert _normalize_gloss("thank-you") == "THANKYOU"
