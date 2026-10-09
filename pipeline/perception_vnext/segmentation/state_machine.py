"""Timestamp-driven deterministic isolated-sign boundary state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .schema import STATE_MACHINE_VERSION, RawV1Document
from .signals import BODY_CHANNEL, HAND_CHANNELS, SegmentationTransition


class State(StrEnum):
    IDLE = "IDLE"
    POSSIBLE_START = "POSSIBLE_START"
    SIGN_ACTIVE = "SIGN_ACTIVE"
    POSSIBLE_END = "POSSIBLE_END"
    SIGN_COMPLETE = "SIGN_COMPLETE"
    REARM = "REARM"


@dataclass(frozen=True)
class ChannelThreshold:
    low: float
    high: float

    def __post_init__(self) -> None:
        if not 0 <= self.low < self.high:
            raise ValueError("each segmentation channel requires 0 <= low < high")


@dataclass(frozen=True)
class SegmenterConfig:
    thresholds: dict[str, ChannelThreshold]
    start_persistence_ms: float = 250.0
    end_quiet_persistence_ms: float = 500.0
    rearm_stable_quiet_ms: float = 700.0
    pre_roll_ms: float = 300.0
    post_roll_ms: float = 250.0
    gap_absolute_ms: float = 500.0
    gap_median_multiplier: float = 3.0
    gap_window_ms: float = 2000.0
    long_duration_diagnostic_ms: float = 4000.0
    state_machine_version: str = STATE_MACHINE_VERSION

    def __post_init__(self) -> None:
        expected = {*HAND_CHANNELS, BODY_CHANNEL}
        if set(self.thresholds) != expected:
            raise ValueError(f"segmentation thresholds must be exactly {sorted(expected)}")
        for name in (
            "start_persistence_ms",
            "end_quiet_persistence_ms",
            "rearm_stable_quiet_ms",
            "pre_roll_ms",
            "post_roll_ms",
            "gap_absolute_ms",
            "gap_median_multiplier",
            "gap_window_ms",
            "long_duration_diagnostic_ms",
        ):
            if float(getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive")

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> SegmenterConfig:
        temporal = value["temporal_policy"]
        gap = value["gap_rule"]
        return cls(
            thresholds={
                name: ChannelThreshold(float(item["low"]), float(item["high"]))
                for name, item in value["thresholds"].items()
            },
            start_persistence_ms=float(temporal["start_persistence_ms"]),
            end_quiet_persistence_ms=float(temporal["end_quiet_persistence_ms"]),
            rearm_stable_quiet_ms=float(temporal["rearm_stable_quiet_ms"]),
            pre_roll_ms=float(temporal["pre_roll_ms"]),
            post_roll_ms=float(temporal["post_roll_ms"]),
            long_duration_diagnostic_ms=float(temporal["long_duration_diagnostic_ms"]),
            gap_absolute_ms=float(gap["absolute_ms"]),
            gap_median_multiplier=float(gap["rolling_median_multiplier"]),
            gap_window_ms=float(gap["rolling_window_ms"]),
            state_machine_version=str(value["state_machine_version"]),
        )


@dataclass(frozen=True)
class Evidence:
    activity: bool
    quiet: bool
    motion_supported: bool
    hand_valid: bool
    hand_above_low: bool
    hand_strong: bool
    body_valid: bool
    body_above_low: bool
    body_strong: bool
    selected_hand_channels: tuple[str | None, str | None]


@dataclass
class BoundaryDetection:
    event_ordinal: int
    detected_onset_index: int
    detected_offset_index: int
    padded_start_index: int
    padded_end_index: int
    completion_index: int
    quality_flags: list[str] = field(default_factory=list)
    gap_summary: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SegmentationResult:
    events: tuple[BoundaryDetection, ...]
    state_transition_trace: tuple[dict[str, Any], ...]
    final_state: str
    rearm_outcome: str
    incomplete_candidate: dict[str, Any] | None
    signal_validity_summary: dict[str, Any]


def classify_evidence(
    transition: SegmentationTransition, config: SegmenterConfig
) -> Evidence:
    hand_valid = False
    hand_above_low = False
    hand_strong = False
    selected: list[str | None] = []
    all_hand_quiet = True
    for side in transition.hand_sides:
        selected.append(side.channel)
        if side.channel is None or side.value is None:
            continue
        hand_valid = True
        threshold = config.thresholds[side.channel]
        hand_above_low = hand_above_low or side.value > threshold.low
        hand_strong = hand_strong or side.value > threshold.high
        all_hand_quiet = all_hand_quiet and side.value <= threshold.low

    body_valid = transition.l_body is not None
    body_above_low = False
    body_strong = False
    body_quiet = True
    if transition.l_body is not None:
        threshold = config.thresholds[BODY_CHANNEL]
        body_above_low = transition.l_body > threshold.low
        body_strong = transition.l_body > threshold.high
        body_quiet = transition.l_body <= threshold.low

    motion_supported = hand_above_low or body_above_low
    activity = hand_strong or body_strong or (hand_above_low and body_above_low)
    any_valid = hand_valid or body_valid
    quiet = any_valid and (not hand_valid or all_hand_quiet) and (not body_valid or body_quiet)
    return Evidence(
        activity=activity,
        quiet=quiet,
        motion_supported=motion_supported,
        hand_valid=hand_valid,
        hand_above_low=hand_above_low,
        hand_strong=hand_strong,
        body_valid=body_valid,
        body_above_low=body_above_low,
        body_strong=body_strong,
        selected_hand_channels=(selected[0], selected[1]),
    )


def _padded_indices(
    raw: RawV1Document,
    onset: int,
    offset: int,
    available_end: int,
    config: SegmenterConfig,
) -> tuple[int, int, list[str]]:
    timestamps = raw.arrays.timestamp_ms
    start_target = float(timestamps[onset]) - config.pre_roll_ms
    candidates = [index for index in range(0, onset + 1) if timestamps[index] >= start_target]
    padded_start = candidates[0] if candidates else onset
    flags: list[str] = []
    if float(timestamps[0]) > start_target:
        flags.append("PRE_ROLL_INCOMPLETE")

    end_target = float(timestamps[offset]) + config.post_roll_ms
    padded_end_candidates = [
        index
        for index in range(offset, available_end + 1)
        if timestamps[index] <= end_target
    ]
    padded_end = padded_end_candidates[-1] if padded_end_candidates else offset
    horizon_observed = any(
        timestamps[index] >= end_target for index in range(offset, available_end + 1)
    )
    if not horizon_observed:
        flags.append("POST_ROLL_INCOMPLETE")
    return padded_start, padded_end, flags


def _validity_summary(transitions: list[SegmentationTransition]) -> dict[str, Any]:
    count = len(transitions)
    channel_counts = {name: 0 for name in HAND_CHANNELS}
    hand_family_valid = 0
    body_valid = 0
    body_frame_valid = 0
    complete_body = 0
    proposal_transitions = 0
    observed_transitions = 0
    hard_gaps = 0
    for transition in transitions:
        selected = [side.channel for side in transition.hand_sides if side.channel is not None]
        if selected:
            hand_family_valid += 1
        for channel in selected:
            channel_counts[channel] += 1
        body_valid += int(transition.l_body is not None)
        body_frame_valid += int(transition.body_frame_valid)
        complete_body += int(transition.body_available)
        proposal_transitions += int(transition.proposal_transition)
        observed_transitions += int(transition.observed_transition)
        hard_gaps += int(transition.hard_gap)

    def rate(value: int) -> float:
        return float(value / count) if count else 0.0

    return {
        "transition_count": count,
        "hand_family_valid_count": hand_family_valid,
        "hand_family_valid_rate": rate(hand_family_valid),
        "selected_hand_channel_counts": channel_counts,
        "selected_hand_channel_rates": {
            name: rate(value) for name, value in channel_counts.items()
        },
        "body_family_valid_count": body_valid,
        "body_family_valid_rate": rate(body_valid),
        "body_frame_valid_count": body_frame_valid,
        "body_frame_valid_rate": rate(body_frame_valid),
        "complete_body_available_count": complete_body,
        "complete_body_available_rate": rate(complete_body),
        "proposal_transition_count": proposal_transitions,
        "observed_transition_count": observed_transitions,
        "hard_gap_count": hard_gaps,
    }


def segment_raw_sequence(
    raw: RawV1Document,
    transitions: list[SegmentationTransition],
    config: SegmenterConfig,
) -> SegmentationResult:
    """Run the complete state machine over chronological source-timestamp transitions."""

    state = State.IDLE
    events: list[BoundaryDetection] = []
    trace: list[dict[str, Any]] = []
    current_ordinal: int | None = None
    next_ordinal = 1
    possible_onset: int | None = None
    possible_start_last_timestamp: float | None = None
    onset: int | None = None
    last_activity: int | None = None
    quiet_start_ms: float | None = None
    pending_flags: set[str] = set()
    rearm_completed = False

    def change(
        new_state: State,
        transition: SegmentationTransition,
        reason: str,
        *,
        event_ordinal: int | None = None,
    ) -> None:
        nonlocal state
        trace.append(
            {
                "event_ordinal": event_ordinal,
                "from_state": state.value,
                "to_state": new_state.value,
                "reason": reason,
                "observation_index": transition.observation_index,
                "frame_index": transition.frame_index,
                "source_timestamp_ms": transition.timestamp_ms,
            }
        )
        state = new_state

    def complete_event(
        transition: SegmentationTransition,
        *,
        available_end: int,
        reason: str,
        gap_summary: dict[str, Any] | None = None,
    ) -> None:
        nonlocal state
        assert current_ordinal is not None and onset is not None and last_activity is not None
        padded_start, padded_end, flags = _padded_indices(
            raw, onset, last_activity, available_end, config
        )
        flags.extend(sorted(pending_flags))
        if gap_summary:
            flags.extend(["PERCEPTION_GAP_TRUNCATED", "POST_ROLL_INCOMPLETE"])
        flags = sorted(set(flags))
        change(State.SIGN_COMPLETE, transition, reason, event_ordinal=current_ordinal)
        events.append(
            BoundaryDetection(
                event_ordinal=current_ordinal,
                detected_onset_index=onset,
                detected_offset_index=last_activity,
                padded_start_index=padded_start,
                padded_end_index=padded_end,
                completion_index=transition.observation_index,
                quality_flags=flags,
                gap_summary=gap_summary or {},
            )
        )
        change(
            State.REARM,
            transition,
            "event_emitted_from_genuine_observations",
            event_ordinal=current_ordinal,
        )

    for transition in transitions:
        evidence = classify_evidence(transition, config)

        if transition.hard_gap:
            gap = {
                "previous_observation_index": transition.previous_index,
                "next_observation_index": transition.observation_index,
                "dt_ms": transition.dt_ms,
                "rolling_median_dt_ms": transition.rolling_median_dt_ms,
            }
            if state in (State.SIGN_ACTIVE, State.POSSIBLE_END):
                complete_event(
                    transition,
                    available_end=transition.previous_index,
                    reason="hard_gap_truncated_active_event",
                    gap_summary=gap,
                )
                quiet_start_ms = None
            elif state is State.POSSIBLE_START:
                change(
                    State.IDLE,
                    transition,
                    "hard_gap_reset_possible_start",
                    event_ordinal=current_ordinal,
                )
                current_ordinal = None
                possible_onset = None
                possible_start_last_timestamp = None
            elif state is State.REARM:
                trace.append(
                    {
                        "event_ordinal": current_ordinal,
                        "from_state": state.value,
                        "to_state": state.value,
                        "reason": "hard_gap_reset_rearm_quiet",
                        "observation_index": transition.observation_index,
                        "frame_index": transition.frame_index,
                        "source_timestamp_ms": transition.timestamp_ms,
                    }
                )
                quiet_start_ms = None
            elif state is State.IDLE:
                trace.append(
                    {
                        "event_ordinal": None,
                        "from_state": state.value,
                        "to_state": state.value,
                        "reason": "hard_gap_reset_idle_continuity",
                        "observation_index": transition.observation_index,
                        "frame_index": transition.frame_index,
                        "source_timestamp_ms": transition.timestamp_ms,
                    }
                )
            continue

        if state is State.IDLE:
            if evidence.activity:
                current_ordinal = next_ordinal
                next_ordinal += 1
                possible_onset = transition.observation_index
                possible_start_last_timestamp = transition.timestamp_ms
                change(
                    State.POSSIBLE_START,
                    transition,
                    "first_activity_evidence",
                    event_ordinal=current_ordinal,
                )
            continue

        if state is State.POSSIBLE_START:
            if evidence.activity:
                assert possible_onset is not None and possible_start_last_timestamp is not None
                possible_start_last_timestamp = transition.timestamp_ms
                elapsed = transition.timestamp_ms - float(
                    raw.arrays.timestamp_ms[possible_onset]
                )
                if elapsed >= config.start_persistence_ms:
                    onset = possible_onset
                    last_activity = transition.observation_index
                    pending_flags = set()
                    change(
                        State.SIGN_ACTIVE,
                        transition,
                        "start_persistence_satisfied",
                        event_ordinal=current_ordinal,
                    )
            else:
                change(
                    State.IDLE,
                    transition,
                    "start_continuity_lost",
                    event_ordinal=current_ordinal,
                )
                current_ordinal = None
                possible_onset = None
                possible_start_last_timestamp = None
            continue

        if state is State.SIGN_ACTIVE:
            assert onset is not None and last_activity is not None
            active_duration = transition.timestamp_ms - float(
                raw.arrays.timestamp_ms[onset]
            )
            if active_duration > config.long_duration_diagnostic_ms:
                pending_flags.add("LONG_DURATION_DIAGNOSTIC")
            if evidence.motion_supported:
                last_activity = transition.observation_index
            elif evidence.quiet:
                quiet_start_ms = transition.previous_timestamp_ms
                change(
                    State.POSSIBLE_END,
                    transition,
                    "first_continuous_quiet_interval",
                    event_ordinal=current_ordinal,
                )
            continue

        if state is State.POSSIBLE_END:
            assert last_activity is not None
            if evidence.motion_supported:
                last_activity = transition.observation_index
                quiet_start_ms = None
                change(
                    State.SIGN_ACTIVE,
                    transition,
                    "motion_resumed_before_end_confirmation",
                    event_ordinal=current_ordinal,
                )
            elif evidence.quiet:
                assert quiet_start_ms is not None
                if transition.timestamp_ms - quiet_start_ms >= config.end_quiet_persistence_ms:
                    complete_event(
                        transition,
                        available_end=transition.observation_index,
                        reason="end_quiet_persistence_satisfied",
                    )
                    if transition.timestamp_ms - quiet_start_ms >= config.rearm_stable_quiet_ms:
                        change(
                            State.IDLE,
                            transition,
                            "rearm_quiet_already_satisfied",
                            event_ordinal=current_ordinal,
                        )
                        rearm_completed = True
                        current_ordinal = None
                        onset = None
                        last_activity = None
                        quiet_start_ms = None
            else:
                quiet_start_ms = None
                change(
                    State.SIGN_ACTIVE,
                    transition,
                    "quiet_continuity_lost_to_unknown_or_mid_motion",
                    event_ordinal=current_ordinal,
                )
            continue

        if state is State.REARM:
            if evidence.motion_supported:
                last_activity = transition.observation_index
                quiet_start_ms = None
            elif evidence.quiet:
                if quiet_start_ms is None:
                    quiet_start_ms = transition.previous_timestamp_ms
                if transition.timestamp_ms - quiet_start_ms >= config.rearm_stable_quiet_ms:
                    change(
                        State.IDLE,
                        transition,
                        "rearm_stable_quiet_satisfied",
                        event_ordinal=current_ordinal,
                    )
                    rearm_completed = True
                    current_ordinal = None
                    onset = None
                    last_activity = None
                    quiet_start_ms = None
            else:
                quiet_start_ms = None

    incomplete: dict[str, Any] | None = None
    if state in (State.POSSIBLE_START, State.SIGN_ACTIVE, State.POSSIBLE_END):
        incomplete = {
            "state": state.value,
            "event_ordinal": current_ordinal,
            "detected_onset_index": onset if onset is not None else possible_onset,
            "reason": "FINITE_SEQUENCE_ENDED_BEFORE_CONFIRMED_SIGN_END",
        }
    rearm_outcome = "COMPLETED" if rearm_completed else (
        "NOT_REACHED" if not events else "INCOMPLETE_AT_SEQUENCE_END"
    )
    return SegmentationResult(
        events=tuple(events),
        state_transition_trace=tuple(trace),
        final_state=state.value,
        rearm_outcome=rearm_outcome,
        incomplete_candidate=incomplete,
        signal_validity_summary=_validity_summary(transitions),
    )
