"""Tests for the separate E2e gold adjudication workflow."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from pipeline.tracking.e2e_gold import INDEX_FIELDS, REVIEW_FIELDS
from pipeline.tracking.e2e_gold_adjudicate import merge, prepare, sha256


def _write(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _review(sample_id: str, count: int) -> dict[str, str]:
    row = {field: "" for field in REVIEW_FIELDS}
    boxes = [
        {
            "x_min": 0.1 + index * 0.4,
            "y_min": 0.2,
            "x_max": 0.3 + index * 0.4,
            "y_max": 0.6,
            "anatomical_side": "unknown",
        }
        for index in range(count)
    ]
    row.update(
        {
            "sample_id": sample_id,
            "review_status": "accepted",
            "source_mirrored": "unknown",
            "visible_hand_count": str(count),
            "gold_hands_json": json.dumps(boxes),
            "motion_blur": "no",
            "occlusion": "no",
            "near_face": "no",
            "edge_clipped": "no",
            "partial_visibility": "no",
        }
    )
    return row


def _index(sample_id: str, image: Path, panel: Path) -> dict[str, str]:
    row = {field: "" for field in INDEX_FIELDS}
    row.update(
        {
            "sample_id": sample_id,
            "video_file": f"{sample_id}.mp4",
            "center_image_path": str(image),
            "context_panel_path": str(panel),
            "detected_hands_json": "[]",
        }
    )
    return row


def _source_run(tmp_path: Path) -> Path:
    run = tmp_path / "source"
    run.mkdir()
    image = tmp_path / "image.png"
    panel = tmp_path / "panel.jpg"
    image.write_bytes(b"image")
    panel.write_bytes(b"panel")
    reviews = [_review("g001", 0), _review("g002", 1), _review("g003", 2)]
    indexes = [_index(row["sample_id"], image, panel) for row in reviews]
    _write(run / "gold_review.csv", REVIEW_FIELDS, reviews)
    _write(run / "internal_index.csv", INDEX_FIELDS, indexes)
    return run


def test_prepare_preserves_source_and_resets_only_sub_two_hand_rows(tmp_path: Path) -> None:
    source = _source_run(tmp_path)
    original_sha = sha256(source / "gold_review.csv")
    adjudication = tmp_path / "adjudication"

    provenance = prepare(source, adjudication)

    assert provenance["selected_sample_ids"] == ["g001", "g002"]
    assert sha256(source / "gold_review.csv") == original_sha
    with (adjudication / "gold_review.csv").open(encoding="utf-8-sig", newline="") as handle:
        corrections = list(csv.DictReader(handle))
    assert [row["sample_id"] for row in corrections] == ["g001", "g002"]
    assert all(row["review_status"] == "" for row in corrections)
    assert all(row["visible_hand_count"] == "" for row in corrections)
    assert all(row["gold_hands_json"] == "" for row in corrections)


def test_merge_requires_complete_corrections_and_keeps_two_hand_row(tmp_path: Path) -> None:
    source = _source_run(tmp_path)
    adjudication = tmp_path / "adjudication"
    prepare(source, adjudication)

    with pytest.raises(ValueError, match="incomplete"):
        merge(source, adjudication)

    corrected = [_review("g001", 1), _review("g002", 2)]
    _write(adjudication / "gold_review.csv", REVIEW_FIELDS, corrected)
    receipt = merge(source, adjudication)

    assert receipt["merge_status"] == "merged"
    assert Path(receipt["backup_path"]).is_file()
    with (source / "gold_review.csv").open(encoding="utf-8-sig", newline="") as handle:
        merged = list(csv.DictReader(handle))
    assert [row["visible_hand_count"] for row in merged] == ["1", "2", "2"]


def test_merge_rejects_source_drift(tmp_path: Path) -> None:
    source = _source_run(tmp_path)
    adjudication = tmp_path / "adjudication"
    prepare(source, adjudication)
    (source / "gold_review.csv").write_text("changed", encoding="utf-8")

    with pytest.raises(ValueError, match="changed after adjudication"):
        merge(source, adjudication)


def test_prepare_accepts_explicit_sample_ids(tmp_path: Path) -> None:
    source = _source_run(tmp_path)
    adjudication = tmp_path / "explicit"

    provenance = prepare(source, adjudication, ["g002"])

    assert provenance["selector"] == "explicit_sample_ids"
    assert provenance["selected_sample_ids"] == ["g002"]
    with (adjudication / "gold_review.csv").open(encoding="utf-8-sig", newline="") as handle:
        corrections = list(csv.DictReader(handle))
    assert [row["sample_id"] for row in corrections] == ["g002"]
