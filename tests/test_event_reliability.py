"""Event-ledger categorisation and admission bookkeeping (no models, no evidence root)."""

from __future__ import annotations

from eval.runtime_diagnostics import event_reliability as er


def _row(first: int, last: int, top1: str = "HELLO") -> dict:
    return {"logical": [first, last], "frozen_top1": top1, "v2_top1": top1}


def _session(kind: str = "TIER2") -> dict:
    return {
        "kind": kind,
        "positives": [
            {"name": "B:HELLO#1", "first": 10, "last": 14},
            {"name": "B:HOME#2", "first": 16, "last": 19},
        ],
        "uncertain": [{"name": "C:HELLO#2", "first": 40, "last": 44}],
        "negatives": [{"name": "E", "first": 60, "last": 80}],
    }


def test_categories_follow_review_labels_only() -> None:
    rows = [
        _row(10, 19),  # spans both signs: credited to HELLO, HOME left without its own event
        _row(41, 43),
        _row(62, 70, "SICK"),
        _row(78, 84, "AND"),
        _row(90, 95, "YOUNG"),
    ]
    out = er.label_session(_session(), rows)
    cats = [r["category"] for r in out["events"]]
    assert cats == ["GENUINE", "UNCERTAIN", "CONFIRMED_NONSIGN", "PARTIAL_NONSIGN", "UNREVIEWED"]
    hello, home = out["signs"]
    assert hello["event"] == 0 and hello["frozen_correct"]
    assert home["event"] is None and home["merged_into_shared_event"]
    assert out["events"][0]["genuine_overlaps"] == 2


def test_second_event_on_a_credited_sign_is_a_duplicate() -> None:
    out = er.label_session(_session(), [_row(10, 12), _row(13, 14), _row(16, 19, "HOME")])
    assert [r["category"] for r in out["events"]] == ["GENUINE", "DUPLICATE", "GENUINE"]
    assert [s["event"] for s in out["signs"]] == [0, 2]


def test_summary_counts_rejections_against_correct_words() -> None:
    session = _session()
    rows = [_row(10, 14), _row(16, 19, "HOME"), _row(62, 70, "SICK")]
    for r, p in zip(rows, (0.9, 0.3, 0.8), strict=True):
        r["word_p1"] = p
    ledger = {"S": {"kind": "TIER2", **er.label_session(session, rows)}}
    all_kept = er.summarize_phone(ledger)["tier2"]
    gated = er.summarize_phone(ledger, lambda r: r["word_p1"] >= 0.5)["tier2"]
    assert all_kept["correct_words"] == 2 and all_kept["admitted_confirmed_nonsign"] == 1
    assert gated["correct_words"] == 1 and gated["rejected_correct_words"] == 1
    assert gated["admitted_confirmed_nonsign"] == 1


def test_protocol_scoring_claims_each_expected_gloss_once() -> None:
    rows = [
        {"block": "C_REPEAT_HANDS_UP", "frozen_top1": "HELLO"},
        {"block": "C_REPEAT_HANDS_UP", "frozen_top1": "HELLO"},
        {"block": "C_REPEAT_HANDS_UP", "frozen_top1": "HELLO"},
        {"block": "E_ORDINARY_MOVEMENT", "frozen_top1": "SICK"},
        {"block": None, "frozen_top1": "CAR"},
    ]
    score = er.protocol_words(rows, "frozen_top1", lambda r: True)
    assert score == {
        "expected_words": 2,
        "other_in_sign_blocks": 1,
        "ordinary_movement": 1,
        "outside": 1,
    }
