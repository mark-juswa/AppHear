from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np

from pipeline.tracking.n0_blinded_readjudication import (
    SEMANTIC_CLASSES,
    _balanced_pick,
    _make_review_order,
    _select_candidates,
    check,
)


def _rows(count: int = 60) -> list[dict[str, str]]:
    return [
        {
            "sample_id": f"n0_{index:04d}",
            "clip_id": f"clip_{index % 12:02d}",
            "participant_id": f"P{index % 6 + 1:02d}",
            "device_id": f"phone{index % 5}",
            "environment_id": f"env{index % 5}",
            "camera_facing": "front",
            "timestamp_ms": str((index // 12) * 1000 + 500),
            "frame_index": str(index),
            "center_image_path": "center.png",
            "context_panel_path": "context.jpg",
            "source_image_sha256": f"{index:064x}",
        }
        for index in range(count)
    ]


def test_candidate_selection_and_hidden_repeats_are_deterministic() -> None:
    config = {
        "selection_seed": 20260821,
        "qc_seed": 20260822,
        "minimum_timestamp_spacing_ms": 1000,
        "candidate_max_per_clip": 5,
        "candidate_count": 48,
        "qc_repeat_count": 4,
    }
    first = _select_candidates(_rows(), config)
    second = _select_candidates(_rows(), config)
    assert [row["sample_id"] for row in first] == [row["sample_id"] for row in second]
    order = _make_review_order(first, config)
    assert len(order) == 52
    assert sum(is_repeat for _, is_repeat in order) == 4


def test_balanced_pick_respects_clip_cap() -> None:
    selected = _balanced_pick(_rows(), target=36, cap=3)
    counts: dict[str, int] = {}
    for row in selected:
        counts[row["clip_id"]] = counts.get(row["clip_id"], 0) + 1
    assert len(selected) == 36
    assert max(counts.values()) == 3


def test_check_rejects_incomplete_and_accepts_complete_package(tmp_path: Path) -> None:
    output = tmp_path / "run"
    output.mkdir()
    center = output / "center.png"
    context = output / "context.jpg"
    image = np.zeros((12, 12, 3), dtype=np.uint8)
    assert cv2.imwrite(str(center), image)
    assert cv2.imwrite(str(context), image)
    queue_fields = (
        "review_id",
        "center_image_path",
        "context_panel_path",
        "review_status",
        "semantic_class",
        "notes",
    )
    with (output / "review_queue.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=queue_fields)
        writer.writeheader()
        writer.writerow(
            {
                "review_id": "review_0001",
                "center_image_path": center,
                "context_panel_path": context,
                "review_status": "unreviewed",
                "semantic_class": "",
                "notes": "",
            }
        )
    candidate_fields = (
        "review_id",
        "candidate_id",
        "source_sample_id",
        "canonical_review_id",
        "is_qc_repeat",
        "clip_id",
        "participant_id",
        "device_id",
        "environment_id",
        "camera_facing",
        "timestamp_ms",
        "frame_index",
        "source_center_image_path",
        "source_context_panel_path",
        "source_image_sha256",
    )
    with (output / "candidate_manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=candidate_fields)
        writer.writeheader()
        writer.writerow({field: "" for field in candidate_fields} | {"review_id": "review_0001"})
    config = {
        "semantic_classes": list(SEMANTIC_CLASSES),
        "output_run": str(output),
        "candidate_count": 1,
        "qc_repeat_count": 0,
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    assert not check(config_path)["passed"]
    rows = list(csv.DictReader((output / "review_queue.csv").open(encoding="utf-8")))
    rows[0]["review_status"] = "accepted"
    rows[0]["semantic_class"] = "ZERO_HAND"
    with (output / "review_queue.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=queue_fields)
        writer.writeheader()
        writer.writerows(rows)
    assert check(config_path)["passed"]
