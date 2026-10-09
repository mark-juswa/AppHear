from __future__ import annotations

import pytest

from pipeline.perception_vnext.recognition_window_materializer import (
    LogicalSignEvent,
    MaterializerConfig,
    ObservationRingBuffer,
    materialize_recognition_window,
    select_observations,
)


def event() -> LogicalSignEvent:
    return LogicalSignEvent(
        logical_active_start_index=3,
        logical_active_end_index=5,
        logical_active_start_ms=600.0,
        logical_active_end_ms=1000.0,
        terminal_post_index=6,
        terminal_post_ms=1200.0,
        commit_index=8,
        commit_ms=1600.0,
    )


def test_sparse_context_brackets_outward() -> None:
    timestamps = [0, 200, 400, 600, 800, 1000, 1200, 1400, 1600]
    window = materialize_recognition_window(timestamps, event())
    assert window.requested_start_ms == 350.0
    assert window.selected_start_ms == 200.0
    assert window.actual_pre_context_ms == 400.0
    assert window.requested_end_ms == 1450.0
    assert window.selected_end_ms == 1600.0
    assert window.actual_post_context_ms == 400.0


def test_never_reads_beyond_commit() -> None:
    timestamps = [0, 200, 400, 600, 800, 1000, 1200, 1400, 1600, 1800]
    window = materialize_recognition_window(timestamps, event())
    assert window.selected_end_index <= event().commit_index
    assert 1800.0 not in [timestamps[index] for index in window.selected_observation_indices]


def test_left_censoring_is_explicit() -> None:
    timestamps = [500, 600, 800, 1000, 1200, 1400, 1600]
    shifted = LogicalSignEvent(1, 3, 600, 1000, 4, 1200, 6, 1600)
    window = materialize_recognition_window(timestamps, shifted)
    assert window.left_censored
    assert window.selected_start_index == 0
    assert window.actual_pre_context_ms == 100.0


def test_right_censoring_is_explicit_when_commit_prefix_is_short() -> None:
    timestamps = [0, 200, 400, 600, 800, 1000, 1200, 1400]
    short = LogicalSignEvent(3, 4, 600, 800, 5, 1000, 7, 1400)
    config = MaterializerConfig(requested_pre_context_ms=250, requested_post_context_ms=500)
    window = materialize_recognition_window(timestamps, short, config)
    assert window.right_censored
    assert window.selected_end_index == short.commit_index


def test_selected_observations_are_original_ordered_objects() -> None:
    timestamps = [0, 200, 400, 600, 800, 1000, 1200, 1400, 1600]
    observations = [{"identity": index} for index in range(len(timestamps))]
    window = materialize_recognition_window(timestamps, event())
    selected = select_observations(observations, window)
    assert [row["identity"] for row in selected] == list(window.selected_observation_indices)
    assert len({id(row) for row in selected}) == len(selected)


def test_non_chronological_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="NON_CHRONOLOGICAL"):
        materialize_recognition_window([0, 200, 200, 600, 800, 1000, 1200, 1400, 1600], event())


def test_ring_buffer_is_bounded_and_chronological() -> None:
    buffer: ObservationRingBuffer[str] = ObservationRingBuffer(max_observations=3)
    for index in range(5):
        buffer.append(index, index * 100.0, f"obs-{index}")
    assert len(buffer) == 3
    assert [row.source_index for row in buffer.snapshot()] == [2, 3, 4]
    assert buffer.evicted_count == 2
    with pytest.raises(ValueError, match="NON_CHRONOLOGICAL"):
        buffer.append(5, 300.0, "bad")


def test_ring_buffer_age_limit_is_explicit() -> None:
    buffer: ObservationRingBuffer[int] = ObservationRingBuffer(
        max_observations=10, max_age_ms=250.0
    )
    for index, timestamp in enumerate([0.0, 100.0, 200.0, 400.0]):
        buffer.append(index, timestamp, index)
    assert [row.timestamp_ms for row in buffer.snapshot()] == [200.0, 400.0]
