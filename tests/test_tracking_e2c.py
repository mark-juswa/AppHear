"""Focused tests for the isolated E2c temporal-tracking experiment."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from pipeline.tracking.audit import analyze
from pipeline.tracking.e2c import _canonical_hands, _generation_summary, _select_smoke
from pipeline.tracking.review import (
    audit_status,
    current_stage,
    is_complete,
    load_rows,
    save_rows_atomic,
)


def test_canonical_hands_matches_existing_slot_contract() -> None:
    points = [SimpleNamespace(x=0.1, y=0.2, z=0.3) for _ in range(21)]
    result = SimpleNamespace(
        handedness=[
            [SimpleNamespace(category_name="Right", score=0.8)],
            [SimpleNamespace(category_name="Left", score=0.9)],
        ],
        hand_landmarks=[points, points],
    )
    hands, scores = _canonical_hands(result)
    assert hands.shape == (2, 21, 3)
    np.testing.assert_allclose(scores, [0.9, 0.8])


def test_smoke_selects_every_cadence_and_hand() -> None:
    rows = []
    for cadence in (1, 4, 8):
        for hand in ("left", "right"):
            rows.append(
                {
                    "base_id": f"{cadence}-{hand}",
                    "cadence": str(cadence),
                    "hand": hand,
                    "roi_source": "missing",
                }
            )
    selected = _select_smoke(rows, seed=3)
    assert {(int(row["cadence"]), row["hand"]) for row in selected} == {
        (1, "left"),
        (1, "right"),
        (4, "left"),
        (4, "right"),
        (8, "left"),
        (8, "right"),
    }


def test_generation_summary_applies_automatic_gates() -> None:
    index = []
    latency = []
    for cadence in (1, 4, 8):
        for mode, available in (("image", 0), ("video", 1)):
            index.append({"mode": mode, "cadence": cadence, "roi_available": available})
            latency.append({"mode": mode, "cadence": cadence, "latency_ms": 10.0})
    raw = {
        "sampling": {"cadences": [1, 4, 8]},
        "audit": {
            "diagnostic_min_availability_gain": 0.2,
            "diagnostic_max_video_to_image_p95_latency_ratio": 1.2,
        },
    }
    report = _generation_summary(index, latency, raw)
    assert report["automatic_gate_passed"]


def test_review_roundtrip_and_stages(tmp_path: Path) -> None:
    panel = tmp_path / "panel.jpg"
    panel.write_bytes(b"panel")
    row = {
        "base_id": "a",
        "panel_path": str(panel),
        "source_blur": "",
        "a_quality": "",
        "b_quality": "",
        "notes": "",
    }
    assert current_stage(row) == "source"
    row["source_blur"] = "clear"
    assert current_stage(row) == "a"
    row["a_quality"] = "usable"
    assert current_stage(row) == "b"
    row["b_quality"] = "missing"
    assert is_complete(row)
    path = tmp_path / "audit_template.csv"
    save_rows_atomic(path, [row])
    assert audit_status(load_rows(path))["completed"] == 1


def test_audit_unblinds_a_and_b(tmp_path: Path) -> None:
    fields = [
        "base_id",
        "mode",
        "cadence",
        "roi_available",
    ]
    with (tmp_path / "internal_index.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for cadence in (1, 4, 8):
            writer.writerow(
                {
                    "base_id": f"b{cadence}",
                    "mode": "image",
                    "cadence": cadence,
                    "roi_available": 0,
                }
            )
            writer.writerow(
                {
                    "base_id": f"b{cadence}",
                    "mode": "video",
                    "cadence": cadence,
                    "roi_available": 1,
                }
            )
    with (tmp_path / "blind_map.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["base_id", "mode_a", "mode_b"])
        writer.writeheader()
        for cadence in (1, 4, 8):
            writer.writerow(
                {"base_id": f"b{cadence}", "mode_a": "video", "mode_b": "image"}
            )
    with (tmp_path / "audit_template.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "base_id",
                "source_blur",
                "a_quality",
                "b_quality",
            ],
        )
        writer.writeheader()
        for cadence in (1, 4, 8):
            writer.writerow(
                {
                    "base_id": f"b{cadence}",
                    "source_blur": "clear",
                    "a_quality": "usable",
                    "b_quality": "missing",
                }
            )
    generation = {
        "paired_comparisons": {
            str(cadence): {"video_to_image_p95_latency_ratio": 1.0}
            for cadence in (1, 4, 8)
        }
    }
    (tmp_path / "generation_summary.json").write_text(
        json.dumps(generation), encoding="utf-8"
    )
    report = analyze(tmp_path, tmp_path / "result.json")
    assert report["promotion_passed"]
    assert report["metrics"]["video|cadence=1"]["usable_rate"] == 1.0

