"""Focused tests for E2d detector operating-point sweep."""

from __future__ import annotations

from pipeline.tracking.e2d import (
    Candidate,
    _balanced_negative_selection,
    _load_candidates,
    _smoke_items,
    _summary,
)


def _items(label: str) -> list[dict[str, object]]:
    rows = []
    for cadence in (1, 4, 8):
        for hand in ("left", "right"):
            for number in range(2):
                rows.append(
                    {
                        "item_id": f"{label}-{cadence}-{hand}-{number}",
                        "label": label,
                        "cadence": cadence,
                        "hand": hand,
                        "roi_source": "missing",
                    }
                )
    return rows


def test_balanced_negative_selection_and_smoke_cover_strata() -> None:
    negatives = _items("negative")
    selected = _balanced_negative_selection(negatives, count=12, seed=3)
    assert len(selected) == 12
    assert {
        (int(row["cadence"]), str(row["hand"])) for row in selected
    } == {
        (1, "left"),
        (1, "right"),
        (4, "left"),
        (4, "right"),
        (8, "left"),
        (8, "right"),
    }
    smoke = _smoke_items(negatives, "negative", seed=3)
    assert len(smoke) == 6


def test_candidate_loader_validates_control() -> None:
    raw = {
        "candidates": [
            {
                "id": "image_d50_p50",
                "mode": "image",
                "detection": 0.5,
                "presence": 0.5,
            }
        ],
        "gates": {"control_candidate": "image_d50_p50"},
    }
    candidates = _load_candidates(raw)
    assert candidates == [Candidate("image_d50_p50", "image", 0.5, 0.5)]


def test_summary_promotes_recall_gain_without_false_roi() -> None:
    candidates = [
        Candidate("image_d50_p50", "image", 0.5, 0.5),
        Candidate("image_d30_p30", "image", 0.3, 0.3),
    ]
    index = []
    latency = []
    for cadence in (1, 4, 8):
        for hand in ("left", "right"):
            for candidate in candidates:
                index.append(
                    {
                        "item_id": f"p-{cadence}-{hand}",
                        "label": "positive",
                        "candidate_id": candidate.candidate_id,
                        "cadence": cadence,
                        "hand": hand,
                        "target_detected": int(candidate.detection == 0.3),
                    }
                )
                index.append(
                    {
                        "item_id": f"n-{cadence}-{hand}",
                        "label": "negative",
                        "candidate_id": candidate.candidate_id,
                        "cadence": cadence,
                        "hand": hand,
                        "target_detected": 0,
                    }
                )
        for candidate in candidates:
            latency.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "cadence": cadence,
                    "latency_ms": 10.0,
                    "left_present": 0,
                    "right_present": 0,
                }
            )
    raw = {
        "sampling": {"cadences": [1, 4, 8]},
        "gates": {
            "control_candidate": "image_d50_p50",
            "min_positive_recall_gain": 0.2,
            "max_negative_false_roi_rate": 0.05,
            "max_negative_false_roi_increase": 0.02,
            "max_candidate_to_control_p95_latency_ratio": 1.2,
        },
    }
    report = _summary(index, latency, candidates, raw)
    assert report["promoted_candidates"] == ["image_d30_p30"]
