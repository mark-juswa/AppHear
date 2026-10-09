from __future__ import annotations

from pathlib import Path

import pytest

from eval.runtime_diagnostics.phase5_1t_segmentation_data_readiness import (
    VideoMetadata,
    calculate_span_timing,
    duplicate_summary,
    validate_train_population,
)
from pipeline.perception_vnext.governance import EXPECTED, resolve_governed_path


def _span(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "detect_version": "d1",
        "params_hash": "abc",
        "n_frames": 100,
        "native_fps": 25.0,
        "onset": 10,
        "release": 59,
        "valid": True,
    }
    payload.update(overrides)
    return payload


def _video(frames: int = 100, fps: float = 25.0) -> VideoMetadata:
    return VideoMetadata(True, frames, fps, 1000.0 * frames / fps, "test", "")


def test_span_unit_interpretation_and_context_duration() -> None:
    result = calculate_span_timing(_span(), _video())
    assert result.valid_for_context
    assert result.unit == "inclusive_frame_indices"
    assert result.span_start_ms == pytest.approx(400.0)
    assert result.span_end_ms_exclusive == pytest.approx(2400.0)
    assert result.active_duration_ms == pytest.approx(2000.0)
    assert result.pre_context_ms == pytest.approx(400.0)
    assert result.post_context_ms == pytest.approx(1600.0)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (_span(release=100), "SPAN_OUTSIDE_SIDECAR_BOUNDS"),
        (_span(onset=-1), "SPAN_OUTSIDE_SIDECAR_BOUNDS"),
        (_span(native_fps=0), "INVALID_SPAN_TIMEBASE"),
        ({"onset": 1}, "AMBIGUOUS_SPAN_UNITS_OR_SCHEMA"),
    ],
)
def test_invalid_or_out_of_bounds_detection(payload: dict[str, object], expected: str) -> None:
    result = calculate_span_timing(payload, _video())
    assert not result.valid_for_context
    assert expected in result.errors


def test_video_bound_and_frame_count_mismatch_detection() -> None:
    result = calculate_span_timing(_span(), _video(frames=50))
    assert "SPAN_OUTSIDE_VIDEO_BOUNDS" in result.errors
    assert "SPAN_VIDEO_FRAME_COUNT_MISMATCH" in result.errors


def test_duplicate_source_handling_is_explicit() -> None:
    rows = [
        {
            "sample_id": "a",
            "resolved_raw_video_path": "X:/same.mp4",
            "resolved_span_path": "a.json",
        },
        {
            "sample_id": "b",
            "resolved_raw_video_path": "x:/same.mp4",
            "resolved_span_path": "b.json",
        },
    ]
    result = duplicate_summary(rows)
    assert result["duplicate_source_file_count"] == 1
    assert result["multiple_governed_spans_same_source_count"] == 1


def test_path_resolution_preserves_existing_file(tmp_path: Path) -> None:
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video")
    assert resolve_governed_path(str(source), "LOCAL") == source


def test_population_rejects_protected_rows() -> None:
    rows = [
        {
            "sample_id": f"train-{index}",
            "split": "train",
            "training_eligible": "true",
            "role": "primary_train",
        }
        for index in range(EXPECTED["train_clips"])
    ]
    rows[0] = {
        "sample_id": "replay:forbidden",
        "split": "protected_replay",
        "training_eligible": "false",
        "role": "protected_clean_replay",
    }
    with pytest.raises(RuntimeError, match="PROTECTED_OR_NONTRAIN_POPULATION_REJECTED|TRAIN_COUNT"):
        validate_train_population(rows)


def test_population_accepts_only_exact_train_size() -> None:
    rows = [
        {
            "sample_id": f"train-{index:04d}",
            "split": "train",
            "training_eligible": "true",
            "role": "primary_train",
        }
        for index in range(EXPECTED["train_clips"])
    ]
    validate_train_population(rows)
    with pytest.raises(RuntimeError, match="TRAIN_COUNT_MISMATCH"):
        validate_train_population(rows[:-1])


def test_deterministic_order_key() -> None:
    rows = [{"sample_id": "b"}, {"sample_id": "a"}]
    assert [row["sample_id"] for row in sorted(rows, key=lambda row: row["sample_id"])] == [
        "a",
        "b",
    ]
