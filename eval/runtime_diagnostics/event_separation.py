"""Offline event-separation variants of the frozen causal decoder (research only).

The production lifecycle (CausalStreamingSignEventDecoder + PRE_OR_POST re-arm) loses consecutive
signs in three measured ways:
  M1 ACTIVE runs that span two signs with no POST between them are one candidate (merge);
  M2 a POST shorter than post_confirm followed by ACTIVE is cancelled and merged;
  M3 after an emission, ACTIVE during the 400 ms re-arm wait is ignored (next sign gets no event).
Each variant below is causal (decides from the current and past observations only), keeps every
production threshold, and only adds a split/re-entry rule:
  REENTRY        in EVENT_EMITTED_WAIT_REARM, ACTIVE after >= `reentry_gap` non-ACTIVE observations
                 since the commit starts a new candidate (addresses M3)
  SHORT_POST     in POST_CANDIDATE, ACTIVE resuming before confirmation commits the open candidate
                 at that point when its POST probability peaked >= `post_peak` (addresses M2)
  MAX_ACTIVE     an ACTIVE candidate longer than `max_active_ms` is committed at its weakest ACTIVE
                 observation (after the minimum span), continuing as a new candidate (M1)
Nothing here replaces the Android lifecycle; `use_variant` swaps the decoder class used by the
offline reference replay so every benchmark sees identical streams and S2 outputs.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from eval.runtime_diagnostics import phone_repeated_recognition_integration as lifecycle
from pipeline.perception_vnext.segmentation.streaming_decoder import (
    CausalStreamingSignEventDecoder,
    DecoderState,
    StreamingDecoderConfig,
)

PRE_IDLE, ACTIVE_SIGN, POST_RECOVERY = 0, 1, 2


@dataclass(frozen=True)
class SplitConfig:
    name: str
    reentry: bool = False
    reentry_gap: int = 1
    short_post: bool = False
    post_peak: float = 0.5
    max_active_ms: float | None = None
    # Added 2026-10-17 from the shadow-session trace: at phone cadence (200-267 ms) a one- or
    # two-observation POST between consecutive signs lands exactly on the post_confirm boundary,
    # where production treats the next ACTIVE as a continuation. Split there instead.
    confirm_boundary: bool = False
    # Added 2026-10-17 from the Arm I lifecycle trace: a valid ACTIVE run (span >= minimum_active)
    # that exits into PRE instead of POST is discarded by the 133 ms PRE-gap reset, i.e. at the
    # very next phone observation. With pre_exit_post the PRE exit enters the same post_confirm
    # end-of-sign confirmation as a POST exit. Shorter ACTIVE runs keep the production behaviour.
    pre_exit_post: bool = False
    # Added 2026-10-17 from the Arm I phone traces: when an S2 moves post-sign probability from
    # POST to PRE, P(POST) stops reaching the split threshold. With nonactive_peak the split
    # rules are gated on 1 - P(ACTIVE) (any end-of-sign evidence) instead of P(POST).
    nonactive_peak: bool = False


BASELINE = SplitConfig("BASELINE")


class SplitDecoder(CausalStreamingSignEventDecoder):
    def __init__(self, config: StreamingDecoderConfig, split: SplitConfig) -> None:
        super().__init__(config)
        self.split = split
        self._active_probs: dict[int, float] = {}
        self._post_peak = 0.0
        self._nonactive_since_emit = 0
        self.split_counts = {
            "REENTRY": 0,
            "SHORT_POST": 0,
            "MAX_ACTIVE": 0,
            "CONFIRM_BOUNDARY": 0,
            "PRE_EXIT_POST": 0,
        }

    def _end_evidence(self, probs: tuple[float, ...]) -> float:
        return 1.0 - probs[1] if self.split.nonactive_peak else probs[2]

    def _commit_open_candidate(self, index: int, timestamp: float, terminal: int) -> bool:
        """Emit the open candidate with `terminal` as its terminal observation; True if emitted."""
        self._first_post_index = terminal
        self._first_post_ms = self._timestamps[terminal]
        event = self._emit(index, timestamp, ACTIVE_SIGN)
        return event is not None

    def consume(self, timestamp_ms: float, probabilities: Any, argmax_state: int) -> Any:
        probs = tuple(float(v) for v in probabilities)
        state = int(argmax_state)
        index = len(self._timestamps)
        s = self.split
        if self.state == DecoderState.EVENT_EMITTED_WAIT_REARM:
            if state == ACTIVE_SIGN and s.reentry and self._nonactive_since_emit >= s.reentry_gap:
                self._timestamps.append(float(timestamp_ms))
                self._rearm_pre_start_ms = None
                self._start_candidate(index, float(timestamp_ms))
                self._active_probs = {index: probs[1]}
                self.split_counts["REENTRY"] += 1
                self._record(
                    index,
                    float(timestamp_ms),
                    state,
                    "SPLIT_REENTRY_ACTIVE",
                    DecoderState.EVENT_EMITTED_WAIT_REARM,
                )
                return None
            self._nonactive_since_emit = (
                0 if state == ACTIVE_SIGN else self._nonactive_since_emit + 1
            )
        if self.state == DecoderState.POST_CANDIDATE:
            self._post_peak = max(self._post_peak, self._end_evidence(probs))
            elapsed = float(timestamp_ms) - float(self._first_post_ms or timestamp_ms)
            short = s.short_post and elapsed < self.config.post_confirm_ms
            boundary = s.confirm_boundary and elapsed >= self.config.post_confirm_ms
            if state == ACTIVE_SIGN and (short or boundary) and self._post_peak >= s.post_peak:
                terminal = int(self._first_post_index)  # type: ignore[arg-type]
                self._timestamps.append(float(timestamp_ms))
                previous = self.state
                emitted = self._commit_open_candidate(index, float(timestamp_ms), terminal)
                if emitted:
                    self.split_counts["CONFIRM_BOUNDARY" if boundary else "SHORT_POST"] += 1
                self._start_candidate(index, float(timestamp_ms))
                self._active_probs = {index: probs[1]}
                self._post_peak = 0.0
                self._record(index, float(timestamp_ms), state, "SPLIT_SHORT_POST", previous)
                return self.events[-1] if emitted else None
        if self.state == DecoderState.ACTIVE_CANDIDATE and state == ACTIVE_SIGN and s.max_active_ms:
            start_ms = float(self._candidate_start_ms)  # type: ignore[arg-type]
            if float(timestamp_ms) - start_ms > s.max_active_ms:
                floor = start_ms + self.config.minimum_active_ms
                options = [
                    i
                    for i in self._active_probs
                    if self._timestamps[i] >= floor
                    and float(timestamp_ms) - self._timestamps[i] >= self.config.minimum_active_ms
                ]
                if options:
                    dip = min(options, key=lambda i: (self._active_probs[i], -i))
                    self._timestamps.append(float(timestamp_ms))
                    previous = self.state
                    start = int(self._candidate_start_index)  # type: ignore[arg-type]
                    self._last_active_index = dip - 1 if dip - 1 >= start else dip
                    self._last_active_ms = self._timestamps[self._last_active_index]
                    emitted = self._commit_open_candidate(index, float(timestamp_ms), dip)
                    if emitted:
                        self.split_counts["MAX_ACTIVE"] += 1
                    self._start_candidate(
                        dip + 1 if dip + 1 <= index else index,
                        self._timestamps[dip + 1 if dip + 1 <= index else index],
                    )
                    self._last_active_index = index
                    self._last_active_ms = float(timestamp_ms)
                    self._active_probs = {i: p for i, p in self._active_probs.items() if i > dip}
                    self._active_probs[index] = probs[1]
                    self._record(index, float(timestamp_ms), state, "SPLIT_MAX_ACTIVE", previous)
                    return self.events[-1] if emitted else None
        if (
            s.pre_exit_post
            and self.state == DecoderState.ACTIVE_CANDIDATE
            and state == PRE_IDLE
            and float(self._last_active_ms) - float(self._candidate_start_ms)  # type: ignore[arg-type]
            >= self.config.minimum_active_ms
        ):
            self.split_counts["PRE_EXIT_POST"] += 1
            state = POST_RECOVERY  # same confirmation path as a POST exit
        before = len(self.events)
        result = super().consume(timestamp_ms, probs, state)
        if self.state == DecoderState.ACTIVE_CANDIDATE and state == ACTIVE_SIGN:
            if self.trace[-1]["action"] == "START_ACTIVE_CANDIDATE":
                self._active_probs = {}
            self._active_probs[index] = probs[1]
        if (
            self.state == DecoderState.POST_CANDIDATE
            and self.trace[-1]["action"] == "BEGIN_POST_CANDIDATE"
        ):
            self._post_peak = self._end_evidence(probs)
        if len(self.events) > before:
            self._nonactive_since_emit = 0 if state == ACTIVE_SIGN else 1
        return result


@contextlib.contextmanager
def use_variant(split: SplitConfig) -> Iterator[None]:
    """Swap the decoder used by the reference replay (and so by every suite/benchmark)."""
    original = lifecycle.CausalStreamingSignEventDecoder
    lifecycle.CausalStreamingSignEventDecoder = lambda config: SplitDecoder(config, split)  # type: ignore[assignment,misc]
    try:
        yield
    finally:
        lifecycle.CausalStreamingSignEventDecoder = original  # type: ignore[misc]


VARIANTS = (
    BASELINE,
    SplitConfig("REENTRY_1", reentry=True, reentry_gap=1),
    SplitConfig("REENTRY_2", reentry=True, reentry_gap=2),
    SplitConfig("SHORT_POST_50", short_post=True, post_peak=0.5),
    SplitConfig("SHORT_POST_70", short_post=True, post_peak=0.7),
    SplitConfig("MAX_ACTIVE_1600", max_active_ms=1600.0),
    SplitConfig("MAX_ACTIVE_2000", max_active_ms=2000.0),
    SplitConfig("R1_SP50", reentry=True, reentry_gap=1, short_post=True, post_peak=0.5),
    SplitConfig(
        "R1_SP50_MA2000",
        reentry=True,
        reentry_gap=1,
        short_post=True,
        post_peak=0.5,
        max_active_ms=2000.0,
    ),
    SplitConfig(
        "R2_SP70_MA2000",
        reentry=True,
        reentry_gap=2,
        short_post=True,
        post_peak=0.7,
        max_active_ms=2000.0,
    ),
    SplitConfig("CONFIRM_BOUNDARY_50", confirm_boundary=True, post_peak=0.5),
    SplitConfig("CONFIRM_BOUNDARY_70", confirm_boundary=True, post_peak=0.7),
    SplitConfig("PRE_EXIT_POST", pre_exit_post=True),
    SplitConfig("CB70_PRE_EXIT_POST", confirm_boundary=True, post_peak=0.7, pre_exit_post=True),
    # 2026-10-17 re-arm study: re-entry combined with the confirm-boundary candidate.
    SplitConfig("R1_CB70", reentry=True, reentry_gap=1, confirm_boundary=True, post_peak=0.7),
    SplitConfig("R2_CB70", reentry=True, reentry_gap=2, confirm_boundary=True, post_peak=0.7),
    # For S2 models whose post-sign output drifts to PRE (Arm I): re-entry with PRE_EXIT_POST.
    SplitConfig("R2_PRE_EXIT_POST", reentry=True, reentry_gap=2, pre_exit_post=True),
    SplitConfig(
        "R1_CBN70",
        reentry=True,
        reentry_gap=1,
        confirm_boundary=True,
        post_peak=0.7,
        nonactive_peak=True,
    ),
    SplitConfig(
        "R1_CBN70_PRE_EXIT_POST",
        reentry=True,
        reentry_gap=1,
        confirm_boundary=True,
        post_peak=0.7,
        nonactive_peak=True,
        pre_exit_post=True,
    ),
    SplitConfig(
        "R2_CB70_PRE_EXIT_POST",
        reentry=True,
        reentry_gap=2,
        confirm_boundary=True,
        post_peak=0.7,
        pre_exit_post=True,
    ),
)
