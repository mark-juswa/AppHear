"""Deterministic calibration-only threshold feasibility analysis."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np

from .schema import RawV1Document
from .signals import SegmentationTransition


@dataclass(frozen=True)
class CalibrationAttempt:
    attempt_id: str
    expected_gloss: str
    raw: RawV1Document
    transitions: tuple[SegmentationTransition, ...]
    oracle_start_index: int
    oracle_end_index: int


def midpoint_breakpoints(values: list[float]) -> list[float]:
    """Every exact midpoint between sorted unique finite calibration values."""

    unique = sorted({float(value) for value in values if np.isfinite(value)})
    return [
        (left + right) * 0.5
        for left, right in zip(unique, unique[1:], strict=False)
    ]


def _channel_values(attempts: tuple[CalibrationAttempt, ...]) -> dict[str, list[float]]:
    values = {
        "h_refined_body": [],
        "h_refined_image": [],
        "h_proposal_image": [],
        "l_body": [],
    }
    for attempt in attempts:
        for transition in attempt.transitions:
            for side in transition.hand_sides:
                if side.refined_body is not None:
                    values["h_refined_body"].append(side.refined_body)
                if side.refined_image is not None:
                    values["h_refined_image"].append(side.refined_image)
                if side.proposal_image is not None:
                    values["h_proposal_image"].append(side.proposal_image)
            if transition.l_body is not None:
                values["l_body"].append(transition.l_body)
    return values


def _selected_channel_mask(
    attempt: CalibrationAttempt, channel: str, threshold: float
) -> int:
    mask = 0
    for bit, transition in enumerate(attempt.transitions):
        if channel == "l_body":
            hit = transition.l_body is not None and transition.l_body > threshold
        else:
            hit = any(
                side.channel == channel
                and side.value is not None
                and side.value > threshold
                for side in transition.hand_sides
            )
        if hit:
            mask |= 1 << bit
    return mask


def _valid_family_mask(attempt: CalibrationAttempt) -> int:
    mask = 0
    for bit, transition in enumerate(attempt.transitions):
        if (
            any(side.channel is not None for side in transition.hand_sides)
            or transition.l_body is not None
        ):
            mask |= 1 << bit
    return mask


def _allowed_onsets(attempt: CalibrationAttempt, pre_roll_ms: float) -> list[int]:
    timestamps = attempt.raw.arrays.timestamp_ms
    allowed: list[int] = []
    for onset in range(1, attempt.raw.observation_count):
        target = float(timestamps[onset]) - pre_roll_ms
        padded_start = next(
            (index for index in range(onset + 1) if timestamps[index] >= target), onset
        )
        pre_context = float(timestamps[attempt.oracle_start_index] - timestamps[padded_start])
        if (
            padded_start <= attempt.oracle_start_index
            and 0.0 <= pre_context <= 500.0
        ):
            allowed.append(onset)
    return allowed


def _relaxed_end_feasible(
    attempt: CalibrationAttempt,
    motion_mask: int,
    valid_mask: int,
    onset_index: int,
    *,
    end_quiet_ms: float,
    post_roll_ms: float,
) -> bool:
    """Test the end policy assuming the sign was already active at an allowed onset.

    This is deliberately a relaxation of the full state machine: it removes every high-threshold
    start constraint. Failure here therefore proves that no high-threshold choice can rescue the
    same low-threshold motion/quiet pattern.
    """

    timestamps = attempt.raw.arrays.timestamp_ms
    last_motion = onset_index
    quiet_start: float | None = None
    for transition in attempt.transitions:
        current = transition.observation_index
        if current <= onset_index:
            continue
        bit = 1 << (current - 1)
        if motion_mask & bit:
            last_motion = current
            quiet_start = None
            continue
        if not valid_mask & bit:
            quiet_start = None
            continue
        if quiet_start is None:
            quiet_start = transition.previous_timestamp_ms
        if transition.timestamp_ms - quiet_start < end_quiet_ms:
            continue
        target = float(timestamps[last_motion]) + post_roll_ms
        padded_end = max(
            index
            for index in range(last_motion, current + 1)
            if timestamps[index] <= target
        )
        post_context = float(timestamps[padded_end] - timestamps[attempt.oracle_end_index])
        return (
            padded_end >= attempt.oracle_end_index
            and 0.0 <= post_context <= 500.0
        )
    return False


def exact_low_threshold_feasibility(
    attempts: tuple[CalibrationAttempt, ...],
    *,
    pre_roll_ms: float = 300.0,
    end_quiet_ms: float = 500.0,
    post_roll_ms: float = 250.0,
) -> dict[str, Any]:
    """Exhaust every distinct low-threshold motion pattern before any high search.

    The hand hierarchy selects body-relative refined motion whenever it is valid and proposal
    motion otherwise. Refined-image values are retained for the future body-reference fallback,
    but no calibration transition selects that tier. It therefore cannot affect this feasibility
    proof. At least one later breakpoint must remain available for each channel's high threshold.
    """

    if not attempts:
        raise ValueError("at least one calibration attempt is required")
    values = _channel_values(attempts)
    breakpoints = {name: midpoint_breakpoints(channel) for name, channel in values.items()}
    searched_channels = ("h_refined_body", "h_proposal_image", "l_body")
    low_candidates = {name: breakpoints[name][:-1] for name in searched_channels}
    if any(not low_candidates[name] for name in searched_channels):
        raise ValueError(
            "calibration does not provide enough unique values for low/high thresholds"
        )

    channel_masks: dict[str, list[tuple[int, ...]]] = {}
    for name in searched_channels:
        channel_masks[name] = [
            tuple(_selected_channel_mask(attempt, name, threshold) for attempt in attempts)
            for threshold in low_candidates[name]
        ]
    valid_masks = tuple(_valid_family_mask(attempt) for attempt in attempts)
    allowed_onsets = tuple(_allowed_onsets(attempt, pre_roll_ms) for attempt in attempts)

    individual_counts = Counter({attempt.attempt_id: 0 for attempt in attempts})
    joint_feasible_patterns = 0
    distinct_patterns: set[tuple[int, ...]] = set()
    representative: dict[tuple[int, ...], dict[str, float]] = {}
    feasible_attempt_masks = Counter()
    for refined_index, refined_masks in enumerate(channel_masks["h_refined_body"]):
        for proposal_index, proposal_masks in enumerate(channel_masks["h_proposal_image"]):
            hand_masks = tuple(
                refined | proposal
                for refined, proposal in zip(refined_masks, proposal_masks, strict=True)
            )
            for body_index, body_masks in enumerate(channel_masks["l_body"]):
                motion_masks = tuple(
                    hand | body for hand, body in zip(hand_masks, body_masks, strict=True)
                )
                if motion_masks in distinct_patterns:
                    continue
                distinct_patterns.add(motion_masks)
                representative[motion_masks] = {
                    "h_refined_body_low": low_candidates["h_refined_body"][refined_index],
                    "h_proposal_image_low": low_candidates["h_proposal_image"][proposal_index],
                    "l_body_low": low_candidates["l_body"][body_index],
                }
                feasible_mask = 0
                for attempt_index, attempt in enumerate(attempts):
                    feasible = any(
                        _relaxed_end_feasible(
                            attempt,
                            motion_masks[attempt_index],
                            valid_masks[attempt_index],
                            onset,
                            end_quiet_ms=end_quiet_ms,
                            post_roll_ms=post_roll_ms,
                        )
                        for onset in allowed_onsets[attempt_index]
                    )
                    if feasible:
                        feasible_mask |= 1 << attempt_index
                        individual_counts[attempt.attempt_id] += 1
                feasible_attempt_masks[feasible_mask] += 1
                if feasible_mask == (1 << len(attempts)) - 1:
                    joint_feasible_patterns += 1

    status = (
        "LOW_THRESHOLD_END_POLICY_FEASIBLE"
        if joint_feasible_patterns
        else "CALIBRATION_INSUFFICIENT_FOR_CURRENT_TEMPORAL_POLICY"
    )
    return {
        "status": status,
        "proof_type": "EXACT_PRUNED_LOW_THRESHOLD_END_FEASIBILITY",
        "proof_explanation": (
            "All distinct low-threshold motion/quiet patterns induced by every empirical "
            "midpoint were evaluated. Start activation was relaxed to every onset compatible "
            "with pre-roll and the 500 ms context bound. High thresholds only restrict starts; "
            "they cannot repair a failed relaxed end."
        ),
        "temporal_policy": {
            "pre_roll_ms": pre_roll_ms,
            "end_quiet_persistence_ms": end_quiet_ms,
            "post_roll_ms": post_roll_ms,
        },
        "candidate_breakpoint_counts": {
            name: len(points) for name, points in breakpoints.items()
        },
        "eligible_low_candidate_counts": {
            name: len(points) for name, points in low_candidates.items()
        },
        "refined_image_selected_transition_count": sum(
            side.channel == "h_refined_image"
            for attempt in attempts
            for transition in attempt.transitions
            for side in transition.hand_sides
        ),
        "raw_low_threshold_tuples": int(
            np.prod([len(low_candidates[name]) for name in searched_channels])
        ),
        "distinct_motion_patterns_evaluated": len(distinct_patterns),
        "joint_feasible_motion_patterns": joint_feasible_patterns,
        "individual_feasible_pattern_counts": dict(individual_counts),
        "feasible_attempt_mask_counts": {
            format(mask, f"0{len(attempts)}b"): count
            for mask, count in sorted(feasible_attempt_masks.items())
        },
        "attempt_order_for_masks": [attempt.attempt_id for attempt in attempts],
        "allowed_onset_counts": {
            attempt.attempt_id: len(onsets)
            for attempt, onsets in zip(attempts, allowed_onsets, strict=True)
        },
        "high_threshold_search": (
            "NOT_RUN_SOUNDLY_PRUNED_BY_ZERO_JOINT_LOW_THRESHOLD_END_FEASIBILITY"
            if not joint_feasible_patterns
            else "REQUIRED"
        ),
    }
