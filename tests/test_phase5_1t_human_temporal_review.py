from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from eval.runtime_diagnostics.phase5_1t_human_temporal_review import (
    EXPECTED_SAMPLE_COUNT,
    SCHEMA,
    commit_annotation,
    empty_annotation_document,
    frame_index_to_ms,
    load_annotation_document,
    public_state,
    validate_annotation_input,
    validate_manifest,
)


def rows(tmp_path: Path, count: int = EXPECTED_SAMPLE_COUNT) -> list[dict[str, object]]:
    result = []
    for index in range(count):
        video = tmp_path / f"{index:02d}.mp4"
        video.write_bytes(b"video")
        source = "ASL_CITIZEN" if index < 8 else "LOCAL"
        span = tmp_path / f"{index:02d}.span.json"
        if source == "ASL_CITIZEN":
            span.write_text(
                json.dumps(
                    {
                        "onset": 10,
                        "release": 19,
                        "native_fps": 10.0,
                        "valid": True,
                    }
                ),
                encoding="utf-8",
            )
        result.append(
            {
                "sample_id": f"sample-{index:02d}",
                "source": source,
                "signer_id": f"signer-{index:02d}",
                "gloss": f"GLOSS-{index:02d}",
                "resolved_raw_video_path": str(video),
                "resolved_span_path": str(span) if source == "ASL_CITIZEN" else "",
            }
        )
    return sorted(result, key=lambda item: (str(item["source"]), str(item["sample_id"])))


def annotation_payload() -> dict[str, object]:
    return {
        "human_sign_start_ms": 1200.0,
        "human_sign_end_ms": 2200.0,
        "clear_pre_context": True,
        "clear_active_sign": True,
        "clear_post_recovery_context": True,
        "ambiguous_or_unusable": False,
        "reviewer_note": "approximate",
    }


def test_manifest_count_is_exactly_24(tmp_path: Path) -> None:
    assert len(validate_manifest(rows(tmp_path))) == 24
    with pytest.raises(ValueError, match="MANIFEST_COUNT_MISMATCH"):
        validate_manifest(rows(tmp_path, 23))


def test_duplicate_sample_rejected(tmp_path: Path) -> None:
    payload = rows(tmp_path)
    payload[1]["sample_id"] = payload[0]["sample_id"]
    with pytest.raises(ValueError, match="DUPLICATE_SAMPLE_ID"):
        validate_manifest(payload)


def test_missing_file_handling(tmp_path: Path) -> None:
    payload = rows(tmp_path)
    Path(str(payload[0]["resolved_raw_video_path"])).unlink()
    with pytest.raises(FileNotFoundError, match="MISSING_VIDEO"):
        validate_manifest(payload)


def test_timestamp_conversion() -> None:
    assert frame_index_to_ms(10, 25.0) == pytest.approx(400.0)
    assert frame_index_to_ms(10, 25.0, end_exclusive=True) == pytest.approx(440.0)


def test_start_must_precede_end() -> None:
    payload = annotation_payload()
    payload["human_sign_start_ms"] = 2200.0
    with pytest.raises(ValueError, match="START_MUST_PRECEDE_END"):
        validate_annotation_input(payload, 3000.0)


def test_annotation_save_and_resume(tmp_path: Path) -> None:
    manifest = rows(tmp_path)
    path = tmp_path / "annotations.json"
    metadata = [{"duration_ms": 3000.0, "fps": 30.0, "frame_count": 90}] * 24
    annotation = commit_annotation(
        manifest=manifest,
        annotation_path=path,
        sample_index=0,
        payload=annotation_payload(),
        video_metadata=metadata,
        now=datetime(2026, 9, 16, tzinfo=UTC),
    )
    assert annotation["sample_id"] == manifest[0]["sample_id"]
    resumed = load_annotation_document(path)
    assert resumed["status"] == "IN_PROGRESS"
    assert len(resumed["annotations"]) == 1
    with pytest.raises(ValueError, match="ALREADY_COMMITTED"):
        commit_annotation(
            manifest=manifest,
            annotation_path=path,
            sample_index=0,
            payload=annotation_payload(),
            video_metadata=metadata,
        )


def test_deterministic_sample_ordering(tmp_path: Path) -> None:
    payload = rows(tmp_path)
    payload[0], payload[1] = payload[1], payload[0]
    with pytest.raises(ValueError, match="MANIFEST_ORDER_NOT_DETERMINISTIC"):
        validate_manifest(payload)


def test_d1_hidden_before_human_commit(tmp_path: Path) -> None:
    manifest = rows(tmp_path)
    document = empty_annotation_document()
    metadata = [{"duration_ms": 3000.0, "fps": 30.0, "frame_count": 90}] * 24
    state = public_state(manifest, document, metadata)
    first = next(item for item in state["samples"] if item["source"] == "ASL_CITIZEN")
    serialized = json.dumps(first)
    assert "d1_onset_ms" not in serialized
    assert "resolved_span_path" not in serialized
    assert "active_span_duration_ms" not in serialized


def test_d1_comparison_only_after_commit(tmp_path: Path) -> None:
    manifest = rows(tmp_path)
    path = tmp_path / "annotations.json"
    metadata = [{"duration_ms": 3000.0, "fps": 30.0, "frame_count": 90}] * 24
    asl_index = next(i for i, item in enumerate(manifest) if item["source"] == "ASL_CITIZEN")
    committed = commit_annotation(
        manifest=manifest,
        annotation_path=path,
        sample_index=asl_index,
        payload=annotation_payload(),
        video_metadata=metadata,
    )
    assert committed["d1_onset_ms"] == pytest.approx(1000.0)
    assert committed["d1_release_ms"] == pytest.approx(2000.0)
    assert committed["human_minus_d1_start_ms"] == pytest.approx(200.0)
    assert committed["human_minus_d1_end_ms"] == pytest.approx(200.0)
    state = public_state(manifest, load_annotation_document(path), metadata)
    assert state["samples"][asl_index]["annotation"]["d1_onset_ms"] == pytest.approx(1000.0)


def test_ambiguous_clip_may_commit_null_boundaries() -> None:
    payload = annotation_payload()
    payload.update(
        {
            "human_sign_start_ms": None,
            "human_sign_end_ms": None,
            "ambiguous_or_unusable": True,
        }
    )
    result = validate_annotation_input(payload, 3000.0)
    assert result["human_sign_start_ms"] is None
    assert result["human_sign_end_ms"] is None


def test_empty_document_schema() -> None:
    assert empty_annotation_document()["schema"] == SCHEMA
