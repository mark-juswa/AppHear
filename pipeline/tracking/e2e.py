"""E2e-A coordinate and anatomical-hand identity fixture smoke."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict
from math import isclose
from pathlib import Path
from typing import Any

import yaml

from .identity import (
    AssociationConfig,
    Box,
    HandCandidate,
    Point,
    TemporalState,
    canonicalize_box,
    canonicalize_pose_points,
    direct_label_assignment,
    mirror_box,
    pose_assignment,
    temporal_pose_assignment,
)

ANNOTATION_FIELDS = (
    "sample_id",
    "sequence_id",
    "frame_index",
    "timestamp_ms",
    "video_file",
    "participant_id",
    "split",
    "cadence",
    "camera_facing",
    "inference_mirrored",
    "display_mirrored",
    "rotation_degrees",
    "image_width",
    "image_height",
    "anatomical_side",
    "visible",
    "x_min",
    "y_min",
    "x_max",
    "y_max",
    "occlusion",
    "motion_blur",
    "notes",
)


def _config(raw: dict[str, Any]) -> AssociationConfig:
    association = raw["association"]
    return AssociationConfig(
        pose_weight=float(association["pose_weight"]),
        temporal_weight=float(association["temporal_weight"]),
        confidence_weight=float(association["confidence_weight"]),
        max_cost=float(association["max_cost"]),
        max_track_age_ms=int(association["max_track_age_ms"]),
    )


def _candidate(
    candidate_id: str,
    side: str,
    center_x: float,
    label: str,
    mirrored: bool,
) -> HandCandidate:
    half = 0.08
    canonical = Box(center_x - half, 0.38, center_x + half, 0.62)
    source = mirror_box(canonical) if mirrored else canonical
    return HandCandidate(candidate_id, source, label, 0.9)


def _fixture_frames() -> list[dict[str, Any]]:
    """Known-answer fixtures spanning unmirrored, mirrored, two-hand, and dropout cases."""

    return [
        {
            "sample_id": "unmirrored-left",
            "sequence_id": "single",
            "timestamp_ms": 0,
            "inference_mirrored": False,
            "truth": {"left": "left-0"},
            "candidates": [_candidate("left-0", "left", 0.76, "Left", False)],
            "pose": {"left": Point(0.76, 0.50), "right": Point(0.24, 0.50)},
        },
        {
            "sample_id": "unmirrored-right",
            "sequence_id": "single",
            "timestamp_ms": 0,
            "inference_mirrored": False,
            "truth": {"right": "right-0"},
            "candidates": [_candidate("right-0", "right", 0.24, "Right", False)],
            "pose": {"left": Point(0.76, 0.50), "right": Point(0.24, 0.50)},
        },
        {
            "sample_id": "unmirrored-two",
            "sequence_id": "two-hand",
            "timestamp_ms": 0,
            "inference_mirrored": False,
            "truth": {"left": "left-1", "right": "right-1"},
            "candidates": [
                _candidate("right-1", "right", 0.25, "Right", False),
                _candidate("left-1", "left", 0.75, "Left", False),
            ],
            "pose": {"left": Point(0.75, 0.50), "right": Point(0.25, 0.50)},
        },
        {
            "sample_id": "mirrored-two",
            "sequence_id": "mirrored",
            "timestamp_ms": 0,
            "inference_mirrored": True,
            "truth": {"left": "left-2", "right": "right-2"},
            "candidates": [
                _candidate("left-2", "left", 0.74, "Right", True),
                _candidate("right-2", "right", 0.26, "Left", True),
            ],
            "pose": {
                "right": mirror_box(Box(0.73, 0.49, 0.75, 0.51)).center,
                "left": mirror_box(Box(0.25, 0.49, 0.27, 0.51)).center,
            },
        },
        {
            "sample_id": "track-start",
            "sequence_id": "dropout",
            "timestamp_ms": 0,
            "inference_mirrored": False,
            "truth": {"left": "left-3", "right": "right-3"},
            "candidates": [
                _candidate("left-3", "left", 0.68, "Left", False),
                _candidate("right-3", "right", 0.32, "Right", False),
            ],
            "pose": {"left": Point(0.68, 0.50), "right": Point(0.32, 0.50)},
        },
        {
            "sample_id": "track-pose-dropout",
            "sequence_id": "dropout",
            "timestamp_ms": 67,
            "inference_mirrored": False,
            "truth": {"left": "left-4", "right": "right-4"},
            "candidates": [
                _candidate("right-4", "right", 0.34, "Right", False),
                _candidate("left-4", "left", 0.66, "Left", False),
            ],
            "pose": {},
        },
    ]


def _canonical_frame(frame: dict[str, Any]) -> tuple[list[HandCandidate], dict[str, Point]]:
    mirrored = bool(frame["inference_mirrored"])
    candidates = [
        HandCandidate(
            candidate.candidate_id,
            canonicalize_box(candidate.box, mirrored),
            candidate.mediapipe_label,
            candidate.score,
        )
        for candidate in frame["candidates"]
    ]
    pose = canonicalize_pose_points(frame["pose"], mirrored)
    return candidates, pose


def _correct(assignments: dict[str, HandCandidate], truth: dict[str, str]) -> tuple[int, int]:
    correct = sum(
        assignments.get(side) is not None
        and assignments[side].candidate_id == candidate_id
        for side, candidate_id in truth.items()
    )
    return correct, len(truth)


def run_smoke(config_path: Path, output_dir: Path) -> dict[str, Any]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config = _config(raw)
    frames = _fixture_frames()
    strategies = {
        "current_direct": [0, 0],
        "swap_mirrored": [0, 0],
        "pose": [0, 0],
        "pose_temporal": [0, 0],
    }
    states: dict[str, TemporalState] = {}
    frame_results = []
    for frame in frames:
        candidates, pose = _canonical_frame(frame)
        direct = direct_label_assignment(candidates, swap_labels=False)
        camera_aware = direct_label_assignment(
            candidates, swap_labels=bool(frame["inference_mirrored"])
        )
        pose_only = pose_assignment(candidates, pose, config)
        state = states.setdefault(str(frame["sequence_id"]), TemporalState())
        temporal = temporal_pose_assignment(
            candidates, pose, int(frame["timestamp_ms"]), state, config
        )
        assignments = {
            "current_direct": direct,
            "swap_mirrored": camera_aware,
            "pose": pose_only,
            "pose_temporal": temporal,
        }
        result = {"sample_id": frame["sample_id"]}
        for name, assigned in assignments.items():
            correct, total = _correct(assigned, frame["truth"])
            strategies[name][0] += correct
            strategies[name][1] += total
            result[name] = {side: value.candidate_id for side, value in assigned.items()}
        frame_results.append(result)

    twice = mirror_box(mirror_box(Box(0.10, 0.20, 0.30, 0.40)))
    original = Box(0.10, 0.20, 0.30, 0.40)
    mirror_involution = all(
        isclose(actual, expected, abs_tol=1e-12)
        for actual, expected in zip(
            asdict(twice).values(), asdict(original).values(), strict=True
        )
    )
    metrics = {
        name: {
            "correct_assignments": values[0],
            "gold_assignments": values[1],
            "identity_accuracy": values[0] / values[1],
        }
        for name, values in strategies.items()
    }
    passed = (
        mirror_involution
        and metrics["swap_mirrored"]["identity_accuracy"] == 1.0
        and metrics["pose_temporal"]["identity_accuracy"] == 1.0
        and metrics["current_direct"]["identity_accuracy"] < 1.0
    )
    report = {
        "experiment_version": raw["experiment_version"],
        "fixture_frames": len(frames),
        "mirror_involution_passed": mirror_involution,
        "metrics": metrics,
        "frames": frame_results,
        "smoke_passed": passed,
        "interpretation": (
            "Synthetic plumbing validation only; this is not MediaPipe accuracy evidence."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "fixture_summary.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    config_bytes = config_path.read_bytes()
    run_config = {
        "config_path": str(config_path.resolve()),
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "association": asdict(config),
        "annotation_fields": list(ANNOTATION_FIELDS),
    }
    (output_dir / "run_config.json").write_text(
        json.dumps(run_config, indent=2), encoding="utf-8"
    )
    with (output_dir / "annotation_template.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        csv.DictWriter(handle, fieldnames=ANNOTATION_FIELDS).writeheader()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run E2e-A coordinate/identity fixture smoke")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("pipeline/config/identity_e2e.yaml"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if not args.smoke:
        print("[tracking/e2e] ERROR: only the bounded --smoke phase is implemented")
        return 2
    try:
        report = run_smoke(args.config, args.output)
    except (FileExistsError, KeyError, OSError, TypeError, ValueError) as error:
        print(f"[tracking/e2e] ERROR: {error}")
        return 2
    print(json.dumps(report, indent=2))
    return 0 if report["smoke_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
