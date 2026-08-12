"""Tests for E2e-C0 capture-set preparation and validation."""

from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np

from pipeline.tracking.e2e_c0_capture import (
    capture_diversity,
    check_run,
    discover_clips,
    prepare_run,
    select_requests,
)
from pipeline.tracking.e2e_gold import REVIEW_FIELDS


def _video(path: Path, frames: int = 60, fps: float = 10.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (96, 72),
    )
    assert writer.isOpened()
    for index in range(frames):
        frame = np.full((72, 96, 3), index % 255, dtype=np.uint8)
        writer.write(frame)
    writer.release()


def _complete_review(path: Path, visible_counts: list[int]) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row, count in zip(rows, visible_counts, strict=True):
        row.update(
            {
                "review_status": "accepted",
                "source_mirrored": "unknown",
                "visible_hand_count": str(count),
                "gold_hands_json": (
                    "[]"
                    if count == 0
                    else (
                        '[{"x_min":0.1,"y_min":0.2,"x_max":0.4,'
                        '"y_max":0.7,"anatomical_side":"unknown"}]'
                    )
                ),
                "motion_blur": "no",
                "occlusion": "no",
                "near_face": "no",
                "edge_clipped": "no",
                "partial_visibility": "no",
            }
        )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_discovery_uses_folder_metadata_and_round_robin_sampling(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _video(raw / "n0" / "P01" / "phoneA" / "home" / "front" / "clip_a.mp4")
    _video(raw / "n0" / "P02" / "phoneB" / "school" / "back" / "clip_b.mp4")

    clips = discover_clips(raw, "n0", hash_videos=False)
    diversity = capture_diversity(clips)
    selected = select_requests(clips, sample_fps=1.0, max_total=6, seed=9)

    assert diversity["participants"] == ["P01", "P02"]
    assert diversity["devices"] == ["phoneA", "phoneB"]
    assert {request.clip.clip_id for request in selected} == {"clip_a", "clip_b"}
    assert len(selected) == 6


def test_prepare_writes_review_compatible_run_and_detects_n0_contamination(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    _video(raw / "n0" / "P01" / "phoneA" / "home" / "front" / "clip_a.mp4")
    output = tmp_path / "run"

    report = prepare_run(
        raw,
        "n0",
        output,
        max_total=4,
        sample_fps=1.0,
        seed=3,
        hash_videos=False,
    )
    _complete_review(output / "gold_review.csv", [0, 1, 0, 0])
    summary, errors = check_run(output)

    assert report["kind"] == "n0"
    assert (output / "center_images" / "n0_0001.png").is_file()
    assert summary["counts"]["eligible"] == 3
    assert summary["counts"]["contaminated"] == 1
    assert any("eligible frames 3 below required 600" in error for error in errors)
    assert (output / "reviewed_manifest.csv").is_file()


def test_p1_requires_visible_hands_for_eligibility(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _video(raw / "p1" / "P01" / "phoneA" / "home" / "front" / "clip_p1.mp4")
    output = tmp_path / "run"

    prepare_run(
        raw,
        "p1",
        output,
        max_total=3,
        sample_fps=1.0,
        seed=4,
        hash_videos=False,
    )
    _complete_review(output / "gold_review.csv", [1, 0, 1])
    summary, errors = check_run(output)

    assert summary["counts"]["eligible"] == 2
    assert summary["counts"]["gold_hands"] == 2
    assert summary["counts"]["no_visible_hand"] == 1
    assert any("eligible frames 2 below required 100" in error for error in errors)
