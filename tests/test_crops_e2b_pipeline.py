"""Tests for E2b paired sampling and audit analysis."""

from __future__ import annotations

import csv
from pathlib import Path

from pipeline.crops.e2b import _select_paired_items
from pipeline.crops.e2b_audit import analyze


def test_paired_selection_balances_control_availability() -> None:
    rows = []
    for cadence in (1, 4, 8):
        for hand in ("left", "right"):
            for source in ("direct", "missing"):
                for item in range(2):
                    rows.append(
                        {
                            "clip_id": f"{cadence}-{hand}-{source}-{item}",
                            "frame_index": "0",
                            "hand": hand,
                            "cadence": str(cadence),
                            "roi_source": source,
                        }
                    )
    selected = _select_paired_items(rows, 12, seed=7)
    strata = {
        (int(row["cadence"]), row["hand"], row["roi_source"] != "missing")
        for row in selected
    }
    assert len(strata) == 12


def test_e2b_analysis_uses_paired_availability_gain(tmp_path: Path) -> None:
    index_path = tmp_path / "index.csv"
    audit_path = tmp_path / "audit.csv"
    with index_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["crop_id", "base_id", "strategy", "cadence", "roi_source"]
        )
        writer.writeheader()
        for cadence in (1, 4, 8):
            writer.writerow(
                {
                    "crop_id": f"control-{cadence}",
                    "base_id": f"base-{cadence}",
                    "strategy": "control_hold_100",
                    "cadence": cadence,
                    "roi_source": "missing",
                }
            )
            writer.writerow(
                {
                    "crop_id": f"candidate-{cadence}",
                    "base_id": f"base-{cadence}",
                    "strategy": "pose_track_150",
                    "cadence": cadence,
                    "roi_source": "pose_fallback",
                }
            )
    with audit_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["crop_id", "visible_hand", "usable", "failure_reason"]
        )
        writer.writeheader()
        for cadence in (1, 4, 8):
            writer.writerow(
                {
                    "crop_id": f"control-{cadence}",
                    "visible_hand": "yes",
                    "usable": "no",
                    "failure_reason": "missing_roi",
                }
            )
            writer.writerow(
                {
                    "crop_id": f"candidate-{cadence}",
                    "visible_hand": "yes",
                    "usable": "yes",
                    "failure_reason": "",
                }
            )
    report = analyze(audit_path, index_path, tmp_path / "result.json")
    assert report["paired_comparisons"]["pose_track_150"][
        "diagnostic_promotion_passed"
    ]
