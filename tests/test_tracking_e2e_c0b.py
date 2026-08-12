"""Tests for the isolated C0-B0 detector-readiness package."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from pipeline.tracking.e2e_c0b import (
    _balanced_select,
    _coco_split,
    _proposal_boxes,
    _resolve_annotation_asset,
    check,
    inventory,
    prepare,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _video(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (96, 72))
    assert writer.isOpened()
    for index in range(20):
        writer.write(np.full((72, 96, 3), value + index, dtype=np.uint8))
    writer.release()


def _fixtures(tmp_path: Path) -> argparse.Namespace:
    asl = tmp_path / "asl"
    protected_video = asl / "videos" / "protected.mp4"
    candidate_video = asl / "videos" / "candidate.mp4"
    _video(protected_video, 1)
    _video(candidate_video, 30)
    _write_csv(
        asl / "splits" / "train.csv",
        [
            {
                "Participant ID": "P1",
                "Video file": "protected.mp4",
                "Gloss": "GOOD",
                "ASL-LEX Code": "a",
            },
            {
                "Participant ID": "P2",
                "Video file": "candidate.mp4",
                "Gloss": "HELLO",
                "ASL-LEX Code": "b",
            },
        ],
    )
    p0 = tmp_path / "p0"
    _write_csv(
        p0 / "internal_index.csv",
        [{"video_file": "protected.mp4", "participant_id": "P1"}],
    )
    n0 = tmp_path / "n0"
    p1 = tmp_path / "p1"
    for run in (n0, p1):
        other = tmp_path / f"{run.name}.mp4"
        _video(other, 60)
        _write_csv(
            run / "capture_manifest.csv",
            [{"video_path": str(other), "sha256": "A" * 64, "participant_id": "PX"}],
        )
    local = tmp_path / "local"
    local_video = local / "1" / "signs" / "good" / "local.mp4"
    _video(local_video, 90)
    sidecar = local_video.with_suffix(".json")
    sidecar.write_text(
        json.dumps(
            {
                "video_file": local_video.name,
                "signer_id": "LOCAL1",
                "gloss": "GOOD",
                "accepted": True,
            }
        ),
        encoding="utf-8",
    )
    return argparse.Namespace(
        asl_root=asl,
        local_root=local,
        p0_run=p0,
        n0_run=n0,
        p1_run=p1,
        e6_assignment=tmp_path / "missing.csv",
        output=tmp_path / "inventory",
    )


def test_inventory_excludes_frozen_source_and_keeps_independent_candidates(tmp_path: Path) -> None:
    args = _fixtures(tmp_path)
    result = inventory(args)
    rows = list(csv.DictReader((args.output / "source_inventory.csv").open(encoding="utf-8")))

    assert result["passed"] is True
    protected = next(
        row for row in rows if row["raw_video_path"].endswith("protected.mp4")
    )
    assert protected["eligibility"] == "excluded"
    assert sum(row["eligibility"] == "candidate" for row in rows) == 2
    assert result["training_authorized"] is False


def test_prepare_hashes_sources_and_writes_review_compatible_package(tmp_path: Path) -> None:
    inventory_args = _fixtures(tmp_path)
    inventory(inventory_args)
    run = tmp_path / "annotation"
    result = prepare(
        argparse.Namespace(inventory=inventory_args.output, output=run, count=2, seed=7)
    )
    checked = check(argparse.Namespace(run_dir=run, require_reviewed=False))

    assert result["rows"] == 2
    assert result["source_hashes_recorded"] is True
    assert result["source_counts"] == {"ASL_CITIZEN": 1, "LOCAL_SUPPLEMENTARY": 1}
    assert checked["passed"] is True
    assert (run / "center_images" / "c0b_0001.png").is_file()
    assert (run / "gold_review.csv").is_file()


def test_check_requires_completed_review_when_requested(tmp_path: Path) -> None:
    inventory_args = _fixtures(tmp_path)
    inventory(inventory_args)
    run = tmp_path / "annotation"
    prepare(argparse.Namespace(inventory=inventory_args.output, output=run, count=2, seed=7))

    result = check(argparse.Namespace(run_dir=run, require_reviewed=True))

    assert result["passed"] is False
    assert any("review incomplete" in error for error in result["errors"])


def test_balanced_select_rotates_sources_and_signers() -> None:
    rows = []
    for source, signers in (("ASL", ("A1", "A2", "A3")), ("LOCAL", ("L1", "L2", "L3"))):
        for signer in signers:
            for index in range(4):
                rows.append(
                    {
                        "candidate_id": f"{source}-{signer}-{index}",
                        "source_dataset": source,
                        "participant_id": signer,
                        "eligibility": "candidate",
                    }
                )

    selected = _balanced_select(rows, count=12, seed=5)

    assert Counter(row["source_dataset"] for row in selected) == {"ASL": 6, "LOCAL": 6}
    assert {row["participant_id"] for row in selected} == {"A1", "A2", "A3", "L1", "L2", "L3"}


def test_annotation_asset_falls_back_from_windows_path_to_run_copy(tmp_path: Path) -> None:
    run = tmp_path / "annotation"
    expected = run / "center_images" / "c0b_0002.png"
    expected.parent.mkdir(parents=True)
    expected.write_bytes(b"image")

    resolved = _resolve_annotation_asset(
        r"F:\ASL DATASET\5. Apphear3\old_run\center_images\c0b_0002.png",
        run,
        "center_images",
    )

    assert resolved == expected


def test_coco_split_uses_model_maker_images_directory(tmp_path: Path) -> None:
    run = tmp_path / "annotation"
    manifest = []
    reviews = []
    for index in range(6):
        sample_id = f"c0b_{index + 1:04d}"
        image_path = run / "center_images" / f"{sample_id}.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        assert cv2.imwrite(str(image_path), np.zeros((24, 32, 3), dtype=np.uint8))
        manifest.append({"sample_id": sample_id, "center_image_path": str(image_path)})
        reviews.append(
            {
                "sample_id": sample_id,
                "review_status": "accepted",
                "gold_hands_json": json.dumps(
                    [{"x_min": 0.1, "y_min": 0.1, "x_max": 0.8, "y_max": 0.8}]
                ),
            }
        )
    _write_csv(run / "annotation_manifest.csv", manifest)
    _write_csv(run / "gold_review.csv", reviews)

    train_root, validation_root, _ = _coco_split(run, tmp_path / "output")

    assert len(list((train_root / "images").glob("*.png"))) == 4
    assert len(list((validation_root / "images").glob("*.png"))) == 2
    assert (train_root / "labels.json").is_file()


def test_proposal_boxes_are_padded_clipped_and_side_unknown() -> None:
    boxes = _proposal_boxes(
        [
            {"box": [0.0, 0.1, 0.2, 0.5]},
            {"box": [0.7, 0.8, 1.0, 1.0]},
        ]
    )

    assert boxes == [
        {
            "x_min": 0.0,
            "y_min": 0.052,
            "x_max": 0.224,
            "y_max": 0.548,
            "anatomical_side": "unknown",
        },
        {
            "x_min": 0.664,
            "y_min": 0.776,
            "x_max": 1.0,
            "y_max": 1.0,
            "anatomical_side": "unknown",
        },
    ]
