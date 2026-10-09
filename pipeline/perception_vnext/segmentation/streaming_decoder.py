"""Causal, timestamp-based decoder for immutable learned SignEvents.

The decoder consumes only the current observation's timestamp, three state
probabilities, and argmax state.  It never flushes a candidate at end of input:
an event exists only after observed POST evidence has persisted long enough.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class DecoderState(StrEnum):
    IDLE = "IDLE"
    ACTIVE_CANDIDATE = "ACTIVE_CANDIDATE"
    PRE_GAP = "PRE_GAP"
    POST_CANDIDATE = "POST_CANDIDATE"
    EVENT_EMITTED_WAIT_REARM = "EVENT_EMITTED_WAIT_REARM"


PRE_IDLE = 0
ACTIVE_SIGN = 1
POST_RECOVERY = 2


@dataclass(frozen=True)
class StreamingDecoderConfig:
    minimum_active_ms: float
    pre_gap_reset_ms: float
    post_confirm_ms: float
    pre_padding_ms: float = 250.0
    post_padding_ms: float = 250.0
    rearm_pre_stable_ms: float = 399.924

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if float(value) < 0.0:
                raise ValueError(f"NEGATIVE_DECODER_DURATION:{name}")
        if self.post_confirm_ms < self.post_padding_ms:
            raise ValueError("POST_CONFIRM_MUST_COVER_POST_PADDING")


@dataclass(frozen=True)
class SignEvent:
    event_id: int
    logical_active_start_index: int
    logical_active_end_index: int
    logical_active_start_ms: float
    logical_active_end_ms: float
    padded_start_index: int
    padded_end_index: int
    padded_start_ms: float
    padded_end_ms: float
    emitted_at_index: int
    emitted_at_ms: float
    first_post_index: int
    first_post_ms: float
    active_span_ms: float
    post_confirmation_elapsed_ms: float


class CausalStreamingSignEventDecoder:
    """Incremental five-state decoder with immutable event emission."""

    def __init__(self, config: StreamingDecoderConfig) -> None:
        self.config = config
        self.state = DecoderState.IDLE
        self.events: list[SignEvent] = []
        self.trace: list[dict[str, Any]] = []
        self.candidate_discard_count = 0
        self.bridged_pre_gap_count = 0
        self.active_to_post_confirm_count = 0
        self._timestamps: list[float] = []
        self._candidate_start_index: int | None = None
        self._candidate_start_ms: float | None = None
        self._last_active_index: int | None = None
        self._last_active_ms: float | None = None
        self._pre_gap_start_ms: float | None = None
        self._first_post_index: int | None = None
        self._first_post_ms: float | None = None
        self._rearm_pre_start_ms: float | None = None

    def _record(
        self,
        index: int,
        timestamp_ms: float,
        state_value: int,
        action: str,
        previous: DecoderState,
    ) -> None:
        self.trace.append(
            {
                "observation_index": index,
                "timestamp_ms": timestamp_ms,
                "argmax_state": state_value,
                "state_before": previous.value,
                "state_after": self.state.value,
                "action": action,
            }
        )

    def _clear_candidate(self) -> None:
        self._candidate_start_index = None
        self._candidate_start_ms = None
        self._last_active_index = None
        self._last_active_ms = None
        self._pre_gap_start_ms = None
        self._first_post_index = None
        self._first_post_ms = None

    def _start_candidate(self, index: int, timestamp_ms: float) -> None:
        self._candidate_start_index = index
        self._candidate_start_ms = timestamp_ms
        self._last_active_index = index
        self._last_active_ms = timestamp_ms
        self._pre_gap_start_ms = None
        self._first_post_index = None
        self._first_post_ms = None
        self.state = DecoderState.ACTIVE_CANDIDATE

    def _enter_post(self, index: int, timestamp_ms: float) -> None:
        self._first_post_index = index
        self._first_post_ms = timestamp_ms
        self._pre_gap_start_ms = None
        self.state = DecoderState.POST_CANDIDATE

    def _discard(self) -> None:
        self.candidate_discard_count += 1
        self._clear_candidate()
        self.state = DecoderState.IDLE

    def _padded_index_bounds(self) -> tuple[int, int]:
        assert self._candidate_start_ms is not None
        assert self._last_active_ms is not None
        lower = self._candidate_start_ms - self.config.pre_padding_ms
        upper = self._last_active_ms + self.config.post_padding_ms
        start = next(
            (index for index, value in enumerate(self._timestamps) if value >= lower),
            0,
        )
        eligible = [index for index, value in enumerate(self._timestamps) if value <= upper]
        end = eligible[-1] if eligible else int(self._last_active_index or 0)
        return start, end

    def _emit(self, index: int, timestamp_ms: float, state_value: int) -> SignEvent | None:
        assert self._candidate_start_index is not None
        assert self._candidate_start_ms is not None
        assert self._last_active_index is not None
        assert self._last_active_ms is not None
        assert self._first_post_index is not None
        assert self._first_post_ms is not None
        active_span = self._last_active_ms - self._candidate_start_ms
        if active_span < self.config.minimum_active_ms:
            self._discard()
            return None
        start, end = self._padded_index_bounds()
        event = SignEvent(
            event_id=len(self.events) + 1,
            logical_active_start_index=self._candidate_start_index,
            logical_active_end_index=self._last_active_index,
            logical_active_start_ms=self._candidate_start_ms,
            logical_active_end_ms=self._last_active_ms,
            padded_start_index=start,
            padded_end_index=end,
            padded_start_ms=self._timestamps[start],
            padded_end_ms=self._timestamps[end],
            emitted_at_index=index,
            emitted_at_ms=timestamp_ms,
            first_post_index=self._first_post_index,
            first_post_ms=self._first_post_ms,
            active_span_ms=active_span,
            post_confirmation_elapsed_ms=timestamp_ms - self._first_post_ms,
        )
        self.events.append(event)
        self.active_to_post_confirm_count += 1
        self._clear_candidate()
        self.state = DecoderState.EVENT_EMITTED_WAIT_REARM
        self._rearm_pre_start_ms = timestamp_ms if state_value == PRE_IDLE else None
        return event

    def consume(
        self,
        timestamp_ms: float,
        probabilities: Iterable[float],
        argmax_state: int,
    ) -> SignEvent | None:
        """Consume one chronological observation and maybe emit one immutable event."""

        timestamp = float(timestamp_ms)
        state_value = int(argmax_state)
        probs = tuple(float(value) for value in probabilities)
        if len(probs) != 3 or state_value not in (PRE_IDLE, ACTIVE_SIGN, POST_RECOVERY):
            raise ValueError("INVALID_SEGMENTER_OBSERVATION")
        if self._timestamps and timestamp <= self._timestamps[-1]:
            raise ValueError("NON_CHRONOLOGICAL_TIMESTAMP")
        index = len(self._timestamps)
        self._timestamps.append(timestamp)
        previous = self.state
        action = "NO_CHANGE"
        emitted: SignEvent | None = None

        if self.state == DecoderState.IDLE:
            if state_value == ACTIVE_SIGN:
                self._start_candidate(index, timestamp)
                action = "START_ACTIVE_CANDIDATE"

        elif self.state == DecoderState.ACTIVE_CANDIDATE:
            if state_value == ACTIVE_SIGN:
                self._last_active_index = index
                self._last_active_ms = timestamp
                action = "EXTEND_ACTIVE_CANDIDATE"
            elif state_value == POST_RECOVERY:
                self._enter_post(index, timestamp)
                action = "BEGIN_POST_CANDIDATE"
            else:
                self._pre_gap_start_ms = timestamp
                self.state = DecoderState.PRE_GAP
                action = "BEGIN_PRE_GAP"

        elif self.state == DecoderState.PRE_GAP:
            assert self._pre_gap_start_ms is not None
            elapsed = timestamp - self._pre_gap_start_ms
            if state_value == ACTIVE_SIGN and elapsed < self.config.pre_gap_reset_ms:
                self._last_active_index = index
                self._last_active_ms = timestamp
                self._pre_gap_start_ms = None
                self.bridged_pre_gap_count += 1
                self.state = DecoderState.ACTIVE_CANDIDATE
                action = "BRIDGE_PRE_GAP_TO_ACTIVE"
            elif state_value == POST_RECOVERY and elapsed < self.config.pre_gap_reset_ms:
                self.bridged_pre_gap_count += 1
                self._enter_post(index, timestamp)
                action = "BRIDGE_PRE_GAP_TO_POST"
            elif elapsed >= self.config.pre_gap_reset_ms:
                self._discard()
                action = "DISCARD_SUSTAINED_PRE_GAP"

        elif self.state == DecoderState.POST_CANDIDATE:
            assert self._first_post_ms is not None
            elapsed = timestamp - self._first_post_ms
            if state_value == ACTIVE_SIGN and elapsed < self.config.post_confirm_ms:
                self._last_active_index = index
                self._last_active_ms = timestamp
                self._first_post_index = None
                self._first_post_ms = None
                self.state = DecoderState.ACTIVE_CANDIDATE
                action = "CANCEL_POST_ACTIVE_RESUMED"
            elif state_value == ACTIVE_SIGN:
                # At the exact confirmation boundary, the current ACTIVE is not
                # terminal evidence; keep the candidate and wait for a new POST.
                self._last_active_index = index
                self._last_active_ms = timestamp
                self._first_post_index = None
                self._first_post_ms = None
                self.state = DecoderState.ACTIVE_CANDIDATE
                action = "CANCEL_POST_ACTIVE_AT_CONFIRM_BOUNDARY"
            elif elapsed >= self.config.post_confirm_ms:
                emitted = self._emit(index, timestamp, state_value)
                action = "EMIT_SIGN_EVENT" if emitted is not None else "DISCARD_TOO_SHORT"

        elif self.state == DecoderState.EVENT_EMITTED_WAIT_REARM:
            if state_value == PRE_IDLE:
                if self._rearm_pre_start_ms is None:
                    self._rearm_pre_start_ms = timestamp
                    action = "BEGIN_REARM_PRE"
                elif timestamp - self._rearm_pre_start_ms >= self.config.rearm_pre_stable_ms:
                    self._rearm_pre_start_ms = None
                    self.state = DecoderState.IDLE
                    action = "REARM_COMPLETE"
            else:
                if self._rearm_pre_start_ms is not None:
                    action = "RESET_REARM_PRE"
                self._rearm_pre_start_ms = None

        self._record(index, timestamp, state_value, action, previous)
        return emitted

    def run(
        self,
        timestamps_ms: Iterable[float],
        probabilities: Iterable[Iterable[float]],
        argmax_states: Iterable[int],
    ) -> list[SignEvent]:
        for timestamp, probs, state in zip(
            timestamps_ms, probabilities, argmax_states, strict=True
        ):
            self.consume(float(timestamp), probs, int(state))
        return list(self.events)
