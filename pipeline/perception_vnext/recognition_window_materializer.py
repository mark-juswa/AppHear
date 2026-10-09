"""Causal, cadence-safe materialization of logical SignEvents.

The component does not infer sign state.  It converts an already-committed
logical event into a slice of genuine chronological observations, bracketing
requested temporal context outward whenever the observed causal prefix permits.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

import numpy as np

SCHEMA = "apphear.recognition_window_materializer.v1"


@dataclass(frozen=True)
class LogicalSignEvent:
    logical_active_start_index: int
    logical_active_end_index: int
    logical_active_start_ms: float
    logical_active_end_ms: float
    terminal_post_index: int
    terminal_post_ms: float
    commit_index: int
    commit_ms: float


@dataclass(frozen=True)
class MaterializerConfig:
    requested_pre_context_ms: float = 250.0
    requested_post_context_ms: float = 250.0

    def __post_init__(self) -> None:
        if self.requested_pre_context_ms < 0.0 or self.requested_post_context_ms < 0.0:
            raise ValueError("NEGATIVE_MATERIALIZER_CONTEXT")


@dataclass(frozen=True)
class MaterializedRecognitionWindow:
    schema: str
    selected_start_index: int
    selected_end_index: int
    selected_start_ms: float
    selected_end_ms: float
    selected_observation_indices: tuple[int, ...]
    selected_observation_count: int
    requested_start_ms: float
    requested_end_ms: float
    requested_pre_context_ms: float
    requested_post_context_ms: float
    actual_pre_context_ms: float
    actual_post_context_ms: float
    actual_pre_context_observation_count: int
    actual_post_context_observation_count: int
    logical_active_start_ms: float
    logical_active_end_ms: float
    terminal_post_ms: float
    commit_ms: float
    left_censored: bool
    right_censored: bool
    genuine_observations_only: bool
    chronological: bool
    synthetic_observations: bool


def _validate_event(timestamps: np.ndarray, event: LogicalSignEvent) -> None:
    if timestamps.ndim != 1 or len(timestamps) == 0:
        raise ValueError("EMPTY_OR_NON_VECTOR_TIMESTAMPS")
    if np.any(np.diff(timestamps) <= 0.0):
        raise ValueError("NON_CHRONOLOGICAL_TIMESTAMPS")
    indices = (
        event.logical_active_start_index,
        event.logical_active_end_index,
        event.terminal_post_index,
        event.commit_index,
    )
    if any(index < 0 or index >= len(timestamps) for index in indices):
        raise ValueError("EVENT_INDEX_OUT_OF_BOUNDS")
    if not (
        event.logical_active_start_index
        <= event.logical_active_end_index
        < event.terminal_post_index
        <= event.commit_index
    ):
        raise ValueError("INVALID_EVENT_INDEX_ORDER")
    expected = (
        event.logical_active_start_ms,
        event.logical_active_end_ms,
        event.terminal_post_ms,
        event.commit_ms,
    )
    actual = tuple(float(timestamps[index]) for index in indices)
    if any(abs(left - right) > 1e-6 for left, right in zip(expected, actual, strict=True)):
        raise ValueError("EVENT_TIMESTAMP_INDEX_MISMATCH")


def materialize_recognition_window(
    timestamps_ms: Sequence[float] | np.ndarray,
    event: LogicalSignEvent,
    config: MaterializerConfig | None = None,
) -> MaterializedRecognitionWindow:
    """Materialize one immutable observed-only window from the causal prefix."""

    if config is None:
        config = MaterializerConfig()
    timestamps = np.asarray(timestamps_ms, np.float64)
    _validate_event(timestamps, event)
    causal_indices = np.arange(event.commit_index + 1, dtype=np.int32)

    requested_start = event.logical_active_start_ms - config.requested_pre_context_ms
    start_candidates = causal_indices[timestamps[: event.commit_index + 1] <= requested_start]
    left_censored = len(start_candidates) == 0
    start_index = int(start_candidates[-1]) if len(start_candidates) else 0

    requested_end = event.terminal_post_ms + config.requested_post_context_ms
    end_candidates = causal_indices[timestamps[: event.commit_index + 1] >= requested_end]
    right_censored = len(end_candidates) == 0
    end_index = int(end_candidates[0]) if len(end_candidates) else event.commit_index
    if end_index < event.logical_active_end_index:
        raise ValueError("MATERIALIZED_WINDOW_TRUNCATES_LOGICAL_EVENT")

    selected = tuple(range(start_index, end_index + 1))
    return MaterializedRecognitionWindow(
        schema=SCHEMA,
        selected_start_index=start_index,
        selected_end_index=end_index,
        selected_start_ms=float(timestamps[start_index]),
        selected_end_ms=float(timestamps[end_index]),
        selected_observation_indices=selected,
        selected_observation_count=len(selected),
        requested_start_ms=requested_start,
        requested_end_ms=requested_end,
        requested_pre_context_ms=config.requested_pre_context_ms,
        requested_post_context_ms=config.requested_post_context_ms,
        actual_pre_context_ms=event.logical_active_start_ms - float(timestamps[start_index]),
        actual_post_context_ms=float(timestamps[end_index]) - event.terminal_post_ms,
        actual_pre_context_observation_count=event.logical_active_start_index - start_index,
        actual_post_context_observation_count=end_index - event.terminal_post_index,
        logical_active_start_ms=event.logical_active_start_ms,
        logical_active_end_ms=event.logical_active_end_ms,
        terminal_post_ms=event.terminal_post_ms,
        commit_ms=event.commit_ms,
        left_censored=left_censored,
        right_censored=right_censored,
        genuine_observations_only=True,
        chronological=True,
        synthetic_observations=False,
    )


T = TypeVar("T")


def select_observations(
    observations: Sequence[T], window: MaterializedRecognitionWindow
) -> tuple[T, ...]:
    if window.selected_end_index >= len(observations):
        raise ValueError("OBSERVATION_SEQUENCE_TOO_SHORT")
    return tuple(observations[index] for index in window.selected_observation_indices)


@dataclass(frozen=True)
class BufferedObservation(Generic[T]):
    source_index: int
    timestamp_ms: float
    payload: T


class ObservationRingBuffer(Generic[T]):
    """Bounded chronological storage for genuine non-RGB observations."""

    def __init__(self, *, max_observations: int, max_age_ms: float | None = None) -> None:
        if max_observations <= 0:
            raise ValueError("INVALID_RING_BUFFER_CAPACITY")
        if max_age_ms is not None and max_age_ms < 0.0:
            raise ValueError("INVALID_RING_BUFFER_AGE")
        self.max_observations = int(max_observations)
        self.max_age_ms = float(max_age_ms) if max_age_ms is not None else None
        self._items: deque[BufferedObservation[T]] = deque()
        self.evicted_count = 0

    def append(self, source_index: int, timestamp_ms: float, payload: T) -> None:
        timestamp = float(timestamp_ms)
        if self._items and timestamp <= self._items[-1].timestamp_ms:
            raise ValueError("NON_CHRONOLOGICAL_RING_BUFFER_APPEND")
        self._items.append(BufferedObservation(int(source_index), timestamp, payload))
        while len(self._items) > self.max_observations:
            self._items.popleft()
            self.evicted_count += 1
        if self.max_age_ms is not None:
            while self._items and timestamp - self._items[0].timestamp_ms > self.max_age_ms:
                self._items.popleft()
                self.evicted_count += 1

    def snapshot(self) -> tuple[BufferedObservation[T], ...]:
        return tuple(self._items)

    def __len__(self) -> int:
        return len(self._items)


def contract_metadata() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "input": {
            "timestamps": "strictly increasing genuine source observations",
            "logical_event": [
                "logical ACTIVE start/end",
                "terminal POST anchor",
                "causal commit index/time",
            ],
        },
        "policy": {
            "start": "last observed timestamp <= logical_start - requested_pre_context",
            "end": "first observed timestamp >= terminal_post + requested_post_context",
            "causal_cap": "selected_end_index <= commit_index",
        },
        "output": "inclusive genuine-observation index interval plus censoring diagnostics",
        "interpolation": False,
        "duplication": False,
        "stale_carry": False,
        "rgb_retention_required": False,
    }
