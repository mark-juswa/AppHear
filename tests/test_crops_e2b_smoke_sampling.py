"""Smoke-stratum coverage test for E2b."""

from __future__ import annotations

from pipeline.crops.e2b import _select_smoke_items


def test_smoke_selects_both_hands_at_every_cadence() -> None:
    rows = []
    for cadence in (1, 4, 8):
        for hand in ("left", "right"):
            rows.append(
                {
                    "clip_id": f"{cadence}-{hand}",
                    "frame_index": "0",
                    "hand": hand,
                    "cadence": str(cadence),
                    "roi_source": "missing",
                }
            )
    selected = _select_smoke_items(rows, seed=11)
    assert {(int(row["cadence"]), row["hand"]) for row in selected} == {
        (1, "left"),
        (1, "right"),
        (4, "left"),
        (4, "right"),
        (8, "left"),
        (8, "right"),
    }
