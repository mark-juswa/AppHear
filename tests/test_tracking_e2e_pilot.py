"""Selection tests for the bounded ASL Citizen E2e-A pilot."""

from __future__ import annotations

from pipeline.tracking.e2e_pilot import select_pilot


def test_select_pilot_covers_every_cadence_hand_and_diagnostic_group() -> None:
    rows = []
    for cadence in (1, 4, 8):
        for hand in ("left", "right"):
            for category, target, raw in (
                ("target_miss_other_detected", 0, 1),
                ("no_hand_detected", 0, 0),
                ("control_detected", 1, 1),
            ):
                rows.append(
                    {
                        "item_id": f"{cadence}-{hand}-{category}",
                        "label": "positive",
                        "candidate_id": "image_d50_p50",
                        "cadence": str(cadence),
                        "hand": hand,
                        "target_detected": str(target),
                        "raw_detected_hands": str(raw),
                        "clip_id": f"clip-{cadence}-{hand}-{category}",
                        "frame_index": str(cadence),
                    }
                )
    selected = select_pilot(rows)
    assert len(selected) == 18
    assert {
        (int(row["cadence"]), row["hand"], row["diagnostic_group"])
        for row in selected
    } == {
        (cadence, hand, category)
        for cadence in (1, 4, 8)
        for hand in ("left", "right")
        for category in (
            "target_miss_other_detected",
            "no_hand_detected",
            "control_detected",
        )
    }
    assert len(
        {(row["clip_id"], row["frame_index"]) for row in selected}
    ) == len(selected)
