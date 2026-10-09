from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.runtime_diagnostics.s2_r2_phone_positive_temporal_review import (
    ANNOTATION_SCHEMA,
    commit_annotation,
    derive_observation_labels,
    empty_annotations,
    load_annotations,
    validate_annotation,
)


def _attempt() -> dict[str, object]:
    return {
        "attempt_id": "attempt_001",
        "attempt_ordinal": 1,
        "expected_gloss": "HELLO",
        "supervision_role": "POSITIVE_ANCHOR",
        "frame_count": 5,
        "frames": [
            {
                "observation_ordinal": index + 1,
                "source_timestamp_ns": index * 200_000_000,
                "relative_timestamp_ms": index * 200.0,
                "original_path": f"frame_{index + 1}.jpg",
                "original_sha256": "a" * 64,
            }
            for index in range(5)
        ],
    }


def _payload() -> dict[str, object]:
    return {
        "full_attempt_reviewed": True,
        "sign_start_ordinal": 2,
        "sign_end_ordinal": 4,
        "clear_pre_context": True,
        "clear_active_sign": True,
        "clear_post_recovery": True,
        "ambiguous": False,
        "reviewer_note": "clear",
    }


def test_valid_non_ambiguous_review_requires_boundaries() -> None:
    payload = _payload()
    payload["sign_start_ordinal"] = None
    with pytest.raises(ValueError, match="SIGN_BOUNDARY_ORDINALS_REQUIRED"):
        validate_annotation(payload, 5)


def test_ambiguous_review_forbids_boundaries() -> None:
    payload = _payload()
    payload["ambiguous"] = True
    with pytest.raises(ValueError, match="AMBIGUOUS_ATTEMPT_MUST_NOT_DEFINE_BOUNDARIES"):
        validate_annotation(payload, 5)


def test_frozen_ignore_band_derives_pre_active_post() -> None:
    attempt = _attempt()
    annotation = {
        "ambiguous": False,
        "clear_pre_context": True,
        "clear_active_sign": True,
        "clear_post_recovery": True,
        "sign_start_relative_ms": 200.0,
        "sign_end_relative_ms": 600.0,
    }
    rows = derive_observation_labels(attempt, annotation)
    assert [row["state_name"] for row in rows] == [
        "PRE_IDLE",
        "IGNORED",
        "ACTIVE_SIGN",
        "IGNORED",
        "POST_RECOVERY",
    ]


def test_commit_is_immutable(tmp_path: Path) -> None:
    annotation_path = tmp_path / "annotations.json"
    annotation_path.write_text(
        json.dumps(empty_annotations("manifest-hash")), encoding="utf-8"
    )
    commit_annotation(
        attempts=[_attempt()],
        annotation_path=annotation_path,
        manifest_hash="manifest-hash",
        index=0,
        payload=_payload(),
    )
    with pytest.raises(ValueError, match="ANNOTATION_ALREADY_COMMITTED_IMMUTABLE"):
        commit_annotation(
            attempts=[_attempt()],
            annotation_path=annotation_path,
            manifest_hash="manifest-hash",
            index=0,
            payload=_payload(),
        )
    assert load_annotations(annotation_path, "manifest-hash")["schema"] == ANNOTATION_SCHEMA
