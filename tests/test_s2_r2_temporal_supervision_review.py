from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.runtime_diagnostics.s2_r2_temporal_supervision_review import (
    ANNOTATION_SCHEMA,
    commit_annotation,
    empty_annotations,
    load_annotations,
    validate_intervals,
)


def _row() -> dict[str, object]:
    return {
        "clip_id": "p1_1",
        "participant_id": "P01",
        "device_id": "phoneA",
        "environment_id": "indoor",
        "video_path": "p1_1.mp4",
        "video_sha256": "a" * 64,
        "duration_ms": 10_000.0,
    }


def test_confirmed_non_sign_requires_behavior_tag() -> None:
    with pytest.raises(ValueError, match="NON_SIGN_BEHAVIOR_TAG_REQUIRED"):
        validate_intervals(
            {
                "full_video_reviewed": True,
                "intervals": [
                    {
                        "start_ms": 100,
                        "end_ms": 500,
                        "category": "CONFIRMED_NON_SIGN",
                        "behavior_tags": [],
                    }
                ],
            },
            1000,
        )


def test_overlapping_intervals_fail_closed() -> None:
    with pytest.raises(ValueError, match="OVERLAPPING_INTERVALS"):
        validate_intervals(
            {
                "full_video_reviewed": True,
                "intervals": [
                    {
                        "start_ms": 100,
                        "end_ms": 600,
                        "category": "CONFIRMED_NON_SIGN",
                        "behavior_tags": ["VISIBLE_HAND_MOVEMENT"],
                    },
                    {
                        "start_ms": 500,
                        "end_ms": 900,
                        "category": "AMBIGUOUS_EXCLUDE",
                        "behavior_tags": [],
                    },
                ],
            },
            1000,
        )


def test_unmarked_gaps_are_allowed_and_excluded() -> None:
    intervals = validate_intervals(
        {
            "full_video_reviewed": True,
            "intervals": [
                {
                    "start_ms": 100,
                    "end_ms": 500,
                    "category": "CONFIRMED_NON_SIGN",
                    "behavior_tags": ["OBJECT_OR_PHONE_INTERACTION"],
                },
                {
                    "start_ms": 800,
                    "end_ms": 900,
                    "category": "POSSIBLE_LEXICAL_OR_SIGN_PREPARATION",
                    "behavior_tags": [],
                },
            ],
        },
        1000,
    )
    assert intervals[0]["start_ms"] == 100.0
    assert intervals[1]["category"] == "POSSIBLE_LEXICAL_OR_SIGN_PREPARATION"


def test_commit_is_immutable(tmp_path: Path) -> None:
    annotation_path = tmp_path / "annotations.json"
    annotation_path.write_text(
        json.dumps(empty_annotations("manifest-hash")), encoding="utf-8"
    )
    payload = {
        "full_video_reviewed": True,
        "intervals": [
            {
                "start_ms": 100,
                "end_ms": 900,
                "category": "CONFIRMED_NON_SIGN",
                "behavior_tags": ["VISIBLE_HAND_MOVEMENT"],
            }
        ],
        "reviewer_note": "reviewed",
    }
    commit_annotation(
        rows=[_row()],
        annotation_path=annotation_path,
        manifest_hash="manifest-hash",
        index=0,
        payload=payload,
    )
    with pytest.raises(ValueError, match="ANNOTATION_ALREADY_COMMITTED_IMMUTABLE"):
        commit_annotation(
            rows=[_row()],
            annotation_path=annotation_path,
            manifest_hash="manifest-hash",
            index=0,
            payload=payload,
        )
    document = load_annotations(annotation_path, "manifest-hash")
    assert document["schema"] == ANNOTATION_SCHEMA
    assert document["status"] == "COMPLETE_PENDING_FINALIZE"
