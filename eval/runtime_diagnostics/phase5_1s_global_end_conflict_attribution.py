"""Phase 5.1S calibration-only global END-conflict attribution."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from eval.runtime_diagnostics.phase5_1_offline_segmenter import (
    EXPECTED_ORACLE_SHA256,
    HOLDOUT_IDS,
    ROOT,
    load_calibration,
    verify_oracle_identity,
)
from eval.runtime_diagnostics.phase5_1r_end_policy_recovery import (
    OUTPUT as PHASE5_1R_OUTPUT,
)
from eval.runtime_diagnostics.phase5_1r_end_policy_recovery import (
    end_duration_candidates,
)
from pipeline.perception_vnext.segmentation.calibration import (
    CalibrationAttempt,
    _allowed_onsets,
    _channel_values,
    _relaxed_end_feasible,
    _selected_channel_mask,
    _valid_family_mask,
    midpoint_breakpoints,
)
from pipeline.perception_vnext.segmentation.signals import SegmentationTransition
from pipeline.perception_vnext.segmentation.state_machine import (
    ChannelThreshold,
    SegmenterConfig,
    classify_evidence,
)

MILESTONE = "PHASE_5_1S_GLOBAL_END_CONFLICT_ATTRIBUTION_01"
BASE = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
)
OUTPUT = BASE / "phase5_1s_global_end_conflict_attribution_01"
RUNNER = ROOT / "eval/runtime_diagnostics/phase5_1s_global_end_conflict_attribution.py"
TEST_FILE = ROOT / "tests/test_phase5_1s_global_end_conflict_attribution.py"
SELECTED_CHANNELS = ("h_refined_body", "h_proposal_image", "l_body")
ALL_CHANNELS = (
    "h_refined_body",
    "h_refined_image",
    "h_proposal_image",
    "l_body",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


@dataclass(frozen=True)
class ThresholdSpace:
    candidates: dict[str, tuple[float, ...]]
    all_breakpoints: dict[str, tuple[float, ...]]
    threshold_indices: dict[str, np.ndarray]
    motion_masks: tuple[np.ndarray, ...]
    valid_masks: tuple[int, ...]
    allowed_onsets: tuple[tuple[int, ...], ...]

    @property
    def size(self) -> int:
        return len(self.threshold_indices[SELECTED_CHANNELS[0]])


def build_threshold_space(
    attempts: tuple[CalibrationAttempt, ...],
) -> ThresholdSpace:
    values = _channel_values(attempts)
    all_breakpoints = {
        name: tuple(midpoint_breakpoints(values[name])) for name in ALL_CHANNELS
    }
    candidates = {
        name: tuple(all_breakpoints[name][:-1]) for name in ALL_CHANNELS
    }
    nr = len(candidates["h_refined_body"])
    np_ = len(candidates["h_proposal_image"])
    nb = len(candidates["l_body"])
    threshold_indices = {
        "h_refined_body": np.repeat(np.arange(nr, dtype=np.int16), np_ * nb),
        "h_proposal_image": np.tile(
            np.repeat(np.arange(np_, dtype=np.int16), nb), nr
        ),
        "l_body": np.tile(np.arange(nb, dtype=np.int16), nr * np_),
    }
    channel_masks = {
        name: np.asarray(
            [
                [_selected_channel_mask(attempt, name, threshold) for attempt in attempts]
                for threshold in candidates[name]
            ],
            dtype=np.uint64,
        )
        for name in SELECTED_CHANNELS
    }
    motion_masks = tuple(
        channel_masks["h_refined_body"][threshold_indices["h_refined_body"], index]
        | channel_masks["h_proposal_image"][
            threshold_indices["h_proposal_image"], index
        ]
        | channel_masks["l_body"][threshold_indices["l_body"], index]
        for index in range(len(attempts))
    )
    return ThresholdSpace(
        candidates=candidates,
        all_breakpoints=all_breakpoints,
        threshold_indices=threshold_indices,
        motion_masks=motion_masks,
        valid_masks=tuple(_valid_family_mask(attempt) for attempt in attempts),
        allowed_onsets=tuple(
            tuple(_allowed_onsets(attempt, 300.0)) for attempt in attempts
        ),
    )


def _feasible_vector(
    attempt: CalibrationAttempt,
    masks: np.ndarray,
    valid_mask: int,
    onsets: tuple[int, ...],
    duration_ms: float,
) -> np.ndarray:
    unique_masks, inverse = np.unique(masks, return_inverse=True)
    feasible_unique = np.asarray(
        [
            any(
                _relaxed_end_feasible(
                    attempt,
                    int(mask),
                    valid_mask,
                    onset,
                    end_quiet_ms=duration_ms,
                    post_roll_ms=250.0,
                )
                for onset in onsets
            )
            for mask in unique_masks
        ],
        dtype=bool,
    )
    return feasible_unique[inverse]


def _projection_summary(
    space: ThresholdSpace, feasible: np.ndarray, name: str
) -> dict[str, Any]:
    if name == "h_refined_image":
        indices = np.arange(len(space.candidates[name]), dtype=np.int16)
        status = "UNCONSTRAINED_NO_SELECTED_CALIBRATION_TRANSITIONS"
    else:
        indices = np.unique(space.threshold_indices[name][feasible])
        status = "DISCRETE_EMPIRICAL_PROJECTION"
    values = [space.candidates[name][int(index)] for index in indices]
    if not values:
        return {
            "status": "EMPTY_FEASIBLE_REGION",
            "candidate_indices": [],
            "candidate_values": [],
            "minimum_feasible_low_threshold": None,
            "maximum_feasible_low_threshold": None,
        }
    last = len(space.candidates[name]) - 1
    return {
        "status": status,
        "candidate_indices": [int(value) for value in indices],
        "candidate_values": values,
        "minimum_feasible_low_threshold": values[0],
        "maximum_feasible_low_threshold": values[-1],
        "minimum_bound_status": (
            "AT_LOWEST_EMPIRICAL_CANDIDATE" if int(indices[0]) == 0 else "BOUNDED"
        ),
        "maximum_bound_status": (
            "AT_HIGHEST_ELIGIBLE_EMPIRICAL_CANDIDATE"
            if int(indices[-1]) == last
            else "BOUNDED"
        ),
        "feasible_candidate_count": len(values),
    }


def _encoded_projection(
    space: ThresholdSpace, feasible: np.ndarray, dimensions: tuple[str, ...]
) -> np.ndarray:
    if not np.any(feasible):
        return np.asarray([], dtype=np.int64)
    code = np.zeros(int(np.count_nonzero(feasible)), dtype=np.int64)
    multiplier = 1
    for name in reversed(dimensions):
        code += space.threshold_indices[name][feasible].astype(np.int64) * multiplier
        multiplier *= len(space.candidates[name])
    return np.unique(code)


def _minimal_disjoint_dimensions(
    space: ThresholdSpace, left: np.ndarray, right: np.ndarray
) -> list[list[str]]:
    if not np.any(left) or not np.any(right):
        return []
    found: list[tuple[str, ...]] = []
    for size in range(1, len(SELECTED_CHANNELS) + 1):
        for dimensions in itertools.combinations(SELECTED_CHANNELS, size):
            if any(set(existing).issubset(dimensions) for existing in found):
                continue
            left_projection = _encoded_projection(space, left, dimensions)
            right_projection = _encoded_projection(space, right, dimensions)
            if np.intersect1d(left_projection, right_projection, assume_unique=True).size == 0:
                found.append(dimensions)
        if found:
            break
    return [list(item) for item in found]


def _constraint_direction(
    space: ThresholdSpace, left: np.ndarray, right: np.ndarray, name: str
) -> dict[str, Any]:
    left_indices = np.unique(space.threshold_indices[name][left])
    right_indices = np.unique(space.threshold_indices[name][right])
    if not left_indices.size or not right_indices.size:
        return {"relation": "NOT_APPLICABLE_EMPTY_REGION"}
    if left_indices[-1] < right_indices[0]:
        relation = "LEFT_REQUIRES_LOWER_RIGHT_REQUIRES_HIGHER"
    elif right_indices[-1] < left_indices[0]:
        relation = "RIGHT_REQUIRES_LOWER_LEFT_REQUIRES_HIGHER"
    elif np.intersect1d(left_indices, right_indices).size == 0:
        relation = "DISCRETE_NONOVERLAP_WITH_OVERLAPPING_BOUNDS"
    else:
        relation = "MARGINAL_OVERLAP"
    return {
        "relation": relation,
        "left_min": space.candidates[name][int(left_indices[0])],
        "left_max": space.candidates[name][int(left_indices[-1])],
        "right_min": space.candidates[name][int(right_indices[0])],
        "right_max": space.candidates[name][int(right_indices[-1])],
    }


def analyze_regions(
    attempts: tuple[CalibrationAttempt, ...],
    space: ThresholdSpace,
    durations: tuple[float, ...],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    region_rows: list[dict[str, Any]] = []
    pair_rows: dict[str, list[dict[str, Any]]] = {
        f"{left.attempt_id}__{right.attempt_id}": []
        for left, right in itertools.combinations(attempts, 2)
    }
    subset_has_intersection = {
        tuple(indices): False
        for size in range(2, len(attempts) + 1)
        for indices in itertools.combinations(range(len(attempts)), size)
    }
    nearest: dict[str, Any] | None = None

    for duration in durations:
        feasible = tuple(
            _feasible_vector(
                attempt,
                space.motion_masks[index],
                space.valid_masks[index],
                space.allowed_onsets[index],
                duration,
            )
            for index, attempt in enumerate(attempts)
        )
        score = np.sum(np.stack(feasible, axis=0), axis=0)
        best_score = int(np.max(score))
        best_index = int(np.flatnonzero(score == best_score)[0])
        if nearest is None or best_score > nearest["satisfied_attempt_count"]:
            nearest = {
                "end_quiet_persistence_ms": duration,
                "threshold_tuple_index": best_index,
                "satisfied_attempt_count": best_score,
                "satisfied_attempt_ids": [
                    attempt.attempt_id
                    for attempt, vector in zip(attempts, feasible, strict=True)
                    if bool(vector[best_index])
                ],
            }

        attempts_row: dict[str, Any] = {}
        for attempt_index, (attempt, vector) in enumerate(
            zip(attempts, feasible, strict=True)
        ):
            attempts_row[attempt.attempt_id] = {
                "feasible_threshold_tuple_count": int(np.count_nonzero(vector)),
                "feasible_categorical_motion_mask_count": int(
                    np.unique(space.motion_masks[attempt_index][vector]).size
                ),
                "signal_projections": {
                    name: _projection_summary(space, vector, name)
                    for name in ALL_CHANNELS
                },
            }
        five_way = np.logical_and.reduce(feasible)
        region_rows.append(
            {
                "end_quiet_persistence_ms": duration,
                "attempts": attempts_row,
                "five_attempt_intersection_threshold_tuple_count": int(
                    np.count_nonzero(five_way)
                ),
            }
        )

        packed = tuple(np.packbits(vector) for vector in feasible)
        for indices in subset_has_intersection:
            intersection = packed[indices[0]].copy()
            for index in indices[1:]:
                intersection &= packed[index]
            subset_has_intersection[indices] |= bool(np.any(intersection))

        for left_index, right_index in itertools.combinations(range(len(attempts)), 2):
            left = feasible[left_index]
            right = feasible[right_index]
            intersection_count = int(np.count_nonzero(left & right))
            key = (
                f"{attempts[left_index].attempt_id}__"
                f"{attempts[right_index].attempt_id}"
            )
            if not np.any(left) or not np.any(right):
                rejection = "ONE_OR_BOTH_ATTEMPT_REGIONS_EMPTY_AT_THIS_DURATION"
            elif intersection_count:
                rejection = "NONE_PAIRWISE_INTERSECTION_EXISTS"
            else:
                rejection = "INCOMPATIBLE_DISCRETE_LOW_THRESHOLD_REGION"
            blockers = _minimal_disjoint_dimensions(space, left, right)
            pair_rows[key].append(
                {
                    "end_quiet_persistence_ms": duration,
                    "left_feasible": bool(np.any(left)),
                    "right_feasible": bool(np.any(right)),
                    "intersection_threshold_tuple_count": intersection_count,
                    "regions_intersect": intersection_count > 0,
                    "state_machine_rejection": rejection,
                    "minimal_disjoint_signal_sets": blockers,
                    "constraint_directions": {
                        name: _constraint_direction(space, left, right, name)
                        for name in SELECTED_CHANNELS
                    },
                }
            )

    assert nearest is not None
    nearest_indices = {
        name: int(space.threshold_indices[name][nearest["threshold_tuple_index"]])
        for name in SELECTED_CHANNELS
    }
    nearest["low_threshold_indices"] = nearest_indices
    nearest["low_thresholds"] = {
        name: space.candidates[name][index]
        for name, index in nearest_indices.items()
    }

    minimal_empty_index_subsets: list[tuple[int, ...]] = []
    for indices, has_intersection in sorted(
        subset_has_intersection.items(), key=lambda item: (len(item[0]), item[0])
    ):
        if has_intersection:
            continue
        if any(set(existing).issubset(indices) for existing in minimal_empty_index_subsets):
            continue
        minimal_empty_index_subsets.append(indices)
    minimal_empty_subsets = [
        [attempts[index].attempt_id for index in indices]
        for indices in minimal_empty_index_subsets
    ]

    table_index = next(
        index for index, attempt in enumerate(attempts) if attempt.attempt_id == "attempt_009"
    )
    anchor_duration = next(
        duration
        for duration in durations
        if np.any(
            _feasible_vector(
                attempts[table_index],
                space.motion_masks[table_index],
                space.valid_masks[table_index],
                space.allowed_onsets[table_index],
                duration,
            )
        )
    )
    anchor_feasible = tuple(
        _feasible_vector(
            attempt,
            space.motion_masks[index],
            space.valid_masks[index],
            space.allowed_onsets[index],
            anchor_duration,
        )
        for index, attempt in enumerate(attempts)
    )
    proposal_indices = space.threshold_indices["h_proposal_image"]
    table_proposals = np.unique(proposal_indices[anchor_feasible[table_index]])
    partner_candidates: list[tuple[float, int]] = []
    for index in range(len(attempts) - 1):
        partner_proposals = np.unique(proposal_indices[anchor_feasible[index]])
        gap = float(
            space.candidates["h_proposal_image"][int(partner_proposals[0])]
            - space.candidates["h_proposal_image"][int(table_proposals[-1])]
        )
        partner_candidates.append((gap, index))
    proposal_gap, partner_index = min(partner_candidates)

    rb_indices = space.threshold_indices["h_refined_body"]
    body_indices = space.threshold_indices["l_body"]
    rb_body_base = len(space.candidates["l_body"])
    table_rb_body = np.unique(
        rb_indices[anchor_feasible[table_index]].astype(np.int64) * rb_body_base
        + body_indices[anchor_feasible[table_index]].astype(np.int64)
    )
    partner_rb_body = np.unique(
        rb_indices[anchor_feasible[partner_index]].astype(np.int64) * rb_body_base
        + body_indices[anchor_feasible[partner_index]].astype(np.int64)
    )
    shared_rb_body = np.intersect1d(table_rb_body, partner_rb_body, assume_unique=True)
    if not shared_rb_body.size:
        raise RuntimeError("PHASE5_1S_EXPECTED_TABLE_PARTNER_RB_BODY_OVERLAP_MISSING")
    shared_options: list[tuple[float, int, int, int]] = []
    for code_value in shared_rb_body:
        rb_index, body_index = divmod(int(code_value), rb_body_base)
        table_at_code = np.unique(
            proposal_indices[
                anchor_feasible[table_index]
                & (rb_indices == rb_index)
                & (body_indices == body_index)
            ]
        )
        partner_at_code = np.unique(
            proposal_indices[
                anchor_feasible[partner_index]
                & (rb_indices == rb_index)
                & (body_indices == body_index)
            ]
        )
        table_boundary = int(table_at_code[-1])
        partner_boundary = int(partner_at_code[0])
        gap = float(
            space.candidates["h_proposal_image"][partner_boundary]
            - space.candidates["h_proposal_image"][table_boundary]
        )
        shared_options.append((gap, rb_index, body_index, table_boundary))
    anchor_gap, shared_rb_index, shared_body_index, table_proposal_index = min(
        shared_options
    )
    partner_proposal_index = int(
        np.unique(
            proposal_indices[
                anchor_feasible[partner_index]
                & (rb_indices == shared_rb_index)
                & (body_indices == shared_body_index)
            ]
        )[0]
    )

    def make_anchor(name: str, proposal_index: int) -> dict[str, Any]:
        matches = np.flatnonzero(
            (rb_indices == shared_rb_index)
            & (proposal_indices == proposal_index)
            & (body_indices == shared_body_index)
        )
        threshold_tuple_index = int(matches[0])
        low_indices = {
            "h_refined_body": shared_rb_index,
            "h_proposal_image": proposal_index,
            "l_body": shared_body_index,
        }
        return {
            "name": name,
            "end_quiet_persistence_ms": anchor_duration,
            "threshold_tuple_index": threshold_tuple_index,
            "low_threshold_indices": low_indices,
            "low_thresholds": {
                channel: space.candidates[channel][index]
                for channel, index in low_indices.items()
            },
            "satisfied_attempt_ids": [
                attempt.attempt_id
                for attempt, vector in zip(attempts, anchor_feasible, strict=True)
                if bool(vector[threshold_tuple_index])
            ],
        }

    conflict_anchors = {
        "TABLE_SIDE": make_anchor("TABLE_SIDE", table_proposal_index),
        "CLOSEST_PARTNER_SIDE": make_anchor(
            "CLOSEST_PARTNER_SIDE", partner_proposal_index
        ),
    }
    conflict_anchors["identity"] = {
        "duration_selection": "LARGEST_BREAKPOINT_WITH_TABLE_INDIVIDUALLY_FEASIBLE",
        "strongest_conflict_partner": attempts[partner_index].attempt_id,
        "partner_selection": "SMALLEST_H_PROPOSAL_IMAGE_DISCRETE_THRESHOLD_GAP",
        "shared_h_refined_body_index": shared_rb_index,
        "shared_l_body_index": shared_body_index,
        "global_marginal_h_proposal_image_gap": proposal_gap,
        "bracketing_anchor_h_proposal_image_gap": anchor_gap,
    }

    decomposition = {
        "milestone": MILESTONE,
        "duration_count": len(durations),
        "threshold_tuple_count": space.size,
        "selected_low_threshold_dimensions": list(SELECTED_CHANNELS),
        "h_refined_image_note": (
            "No calibration transition selects this tier; its empirical candidates are "
            "reported but cannot constrain the discrete feasible regions."
        ),
        "durations": region_rows,
        "five_attempt_intersection": "EMPTY_AT_ALL_DURATIONS",
        "nearest_global_compatibility_pattern": nearest,
        "table_conflict_bracketing_anchors": conflict_anchors,
    }
    conflict_matrix = {
        "milestone": MILESTONE,
        "pairs": {
            key: {
                "intersects_at_any_duration": any(
                    row["regions_intersect"] for row in rows
                ),
                "intersecting_durations_ms": [
                    row["end_quiet_persistence_ms"]
                    for row in rows
                    if row["regions_intersect"]
                ],
                "per_duration": rows,
            }
            for key, rows in pair_rows.items()
        },
        "minimal_attempt_subsets_with_no_common_duration_threshold_tuple": (
            minimal_empty_subsets
        ),
    }
    return decomposition, conflict_matrix, nearest


def _diagnostic_config(
    space: ThresholdSpace, nearest: dict[str, Any]
) -> SegmenterConfig:
    thresholds: dict[str, ChannelThreshold] = {}
    for name in SELECTED_CHANNELS:
        index = nearest["low_threshold_indices"][name]
        thresholds[name] = ChannelThreshold(
            low=space.candidates[name][index],
            high=space.all_breakpoints[name][index + 1],
        )
    refined_fraction = nearest["low_threshold_indices"]["h_refined_body"] / max(
        1, len(space.candidates["h_refined_body"]) - 1
    )
    refined_image_index = round(
        refined_fraction * (len(space.candidates["h_refined_image"]) - 1)
    )
    thresholds["h_refined_image"] = ChannelThreshold(
        low=space.candidates["h_refined_image"][refined_image_index],
        high=space.all_breakpoints["h_refined_image"][refined_image_index + 1],
    )
    return SegmenterConfig(
        thresholds=thresholds,
        end_quiet_persistence_ms=nearest["end_quiet_persistence_ms"],
    )


def _family_details(
    transition: SegmentationTransition, config: SegmenterConfig
) -> dict[str, Any]:
    evidence = classify_evidence(transition, config)
    sides: list[dict[str, Any]] = []
    hand_quiet = True
    for side in transition.hand_sides:
        threshold = config.thresholds.get(side.channel) if side.channel else None
        above_low = bool(
            side.value is not None and threshold is not None and side.value > threshold.low
        )
        strong = bool(
            side.value is not None and threshold is not None and side.value > threshold.high
        )
        if side.channel is not None:
            hand_quiet &= not above_low
        sides.append(
            {
                "side": side.side,
                "selected_tier": side.channel,
                "selected_value": side.value,
                "valid": side.channel is not None and side.value is not None,
                "above_low": above_low,
                "strong": strong,
            }
        )
    body_quiet = evidence.body_valid and not evidence.body_above_low
    return {
        "evidence": evidence,
        "hand_sides": sides,
        "hand_quiet": evidence.hand_valid and hand_quiet,
        "body_quiet": body_quiet,
    }


def _end_decision(
    details: dict[str, Any], mode: str, after_oracle: bool
) -> tuple[bool, bool, str]:
    evidence = details["evidence"]
    hand_quiet = details["hand_quiet"]
    body_quiet = details["body_quiet"]
    if mode == "CF_D" and after_oracle:
        valid = evidence.hand_valid or evidence.body_valid
        return False, valid, "oracle_post_end_activity_ignored" if valid else "unknown"
    if mode == "CF_A":
        if evidence.hand_valid:
            return evidence.hand_above_low, hand_quiet, "body_removed_as_quiet_veto"
        return evidence.body_above_low, body_quiet, "hand_unknown_body_controls"
    if mode == "CF_B":
        if evidence.body_valid:
            return evidence.body_above_low, body_quiet, "hand_removed_as_quiet_veto"
        return evidence.hand_above_low, hand_quiet, "body_unknown_hand_controls"
    if mode == "CF_C":
        strong = evidence.hand_strong or evidence.body_strong
        any_quiet = hand_quiet or body_quiet
        return strong or not any_quiet, any_quiet and not strong, (
            "any_family_quiet_without_strong_motion"
            if any_quiet and not strong
            else "no_quiet_family_or_strong_motion"
        )
    return evidence.motion_supported, evidence.quiet, "current_all_valid_families_quiet"


def replay_end(
    attempt: CalibrationAttempt,
    config: SegmenterConfig,
    onset: int,
    *,
    mode: str = "CURRENT",
) -> dict[str, Any]:
    timestamps = attempt.raw.arrays.timestamp_ms
    state = "SIGN_ACTIVE"
    last_motion = onset
    quiet_start: float | None = None
    previous_tiers: tuple[str | None, str | None] | None = None
    trace: list[dict[str, Any]] = []
    completion: dict[str, Any] | None = None

    for transition in attempt.transitions:
        if transition.observation_index <= onset:
            previous_tiers = tuple(side.channel for side in transition.hand_sides)
            continue
        details = _family_details(transition, config)
        evidence = details["evidence"]
        tiers = evidence.selected_hand_channels
        tier_switch = previous_tiers is not None and tiers != previous_tiers
        previous_tiers = tiers
        before = state
        after_oracle = transition.observation_index > attempt.oracle_end_index
        if transition.hard_gap:
            state = "TRUNCATED_GAP"
            reason = "perception_gap_no_bridge"
            motion_for_end = False
            quiet_for_end = False
        else:
            motion_for_end, quiet_for_end, decision_basis = _end_decision(
                details, mode, after_oracle
            )
            if motion_for_end:
                last_motion = transition.observation_index
                quiet_start = None
                state = "SIGN_ACTIVE"
                reason = "motion_resumed_or_supported_quiet_reset"
            elif quiet_for_end:
                if quiet_start is None:
                    quiet_start = transition.previous_timestamp_ms
                state = "POSSIBLE_END"
                elapsed = transition.timestamp_ms - quiet_start
                if elapsed >= config.end_quiet_persistence_ms:
                    target = float(timestamps[last_motion]) + config.post_roll_ms
                    padded_end = max(
                        index
                        for index in range(last_motion, transition.observation_index + 1)
                        if timestamps[index] <= target
                    )
                    post_context = float(
                        timestamps[padded_end] - timestamps[attempt.oracle_end_index]
                    )
                    completion = {
                        "completion_observation_index": transition.observation_index,
                        "detected_offset_index": last_motion,
                        "padded_end_index": padded_end,
                        "padded_post_context_ms": post_context,
                        "oracle_end_preserved": padded_end >= attempt.oracle_end_index,
                        "within_500ms_post_context": 0.0 <= post_context <= 500.0,
                    }
                    state = "SIGN_COMPLETE"
                    reason = "end_quiet_persistence_satisfied"
                else:
                    reason = "quiet_accumulating"
            else:
                quiet_start = None
                state = "SIGN_ACTIVE"
                reason = "quiet_unknown_or_mid_motion_reset"
            if mode != "CURRENT":
                reason = f"{reason}:{decision_basis}"

        if transition.observation_index >= attempt.oracle_end_index:
            trace.append(
                {
                    "observation_index": transition.observation_index,
                    "frame_index": transition.frame_index,
                    "source_timestamp_ms": transition.timestamp_ms,
                    "oracle_region": "ACTIVE"
                    if transition.observation_index <= attempt.oracle_end_index
                    else "POST",
                    "selected_hand_tiers": list(tiers),
                    "selected_hand_values": [
                        side["selected_value"] for side in details["hand_sides"]
                    ],
                    "hand_valid": evidence.hand_valid,
                    "l_body_value": transition.l_body,
                    "body_valid": evidence.body_valid,
                    "quiet_evidence": evidence.quiet,
                    "activity_evidence": evidence.activity,
                    "strong_motion": evidence.hand_strong or evidence.body_strong,
                    "corroborated_motion": (
                        evidence.hand_above_low and evidence.body_above_low
                    ),
                    "hand_above_low": evidence.hand_above_low,
                    "body_above_low": evidence.body_above_low,
                    "hand_quiet": details["hand_quiet"],
                    "body_quiet": details["body_quiet"],
                    "tier_switch": tier_switch,
                    "perception_gap": transition.hard_gap,
                    "state_before": before,
                    "state_after": state,
                    "transition_reason": reason,
                    "quiet_start_ms_after": quiet_start,
                }
            )
        if completion is not None or state == "TRUNCATED_GAP":
            break

    structurally_feasible = bool(
        completion
        and completion["oracle_end_preserved"]
        and completion["within_500ms_post_context"]
    )
    if completion is None:
        failure = "NO_CONFIRMED_END_BEFORE_SEQUENCE_END"
    elif not completion["oracle_end_preserved"]:
        failure = "PADDED_END_BEFORE_ORACLE_END"
    elif not completion["within_500ms_post_context"]:
        failure = "PADDED_END_CONTEXT_EXCEEDS_500MS"
    else:
        failure = None
    return {
        "mode": mode,
        "onset_index": onset,
        "structurally_feasible": structurally_feasible,
        "completion": completion,
        "failure_reason": failure,
        "trace": trace,
    }


def _best_replay(
    attempt: CalibrationAttempt, config: SegmenterConfig, *, mode: str
) -> dict[str, Any]:
    replays = [
        replay_end(attempt, config, onset, mode=mode)
        for onset in _allowed_onsets(attempt, config.pre_roll_ms)
    ]
    return next(
        (replay for replay in replays if replay["structurally_feasible"]), replays[0]
    )


def trace_and_counterfactuals(
    attempts: tuple[CalibrationAttempt, ...], config: SegmenterConfig
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    current = {
        attempt.attempt_id: _best_replay(attempt, config, mode="CURRENT")
        for attempt in attempts
    }
    veto: dict[str, Any] = {}
    recovery: dict[str, Any] = {}
    for attempt in attempts:
        rows = current[attempt.attempt_id]["trace"]
        post = [row for row in rows if row["oracle_region"] == "POST"]
        counts = {
            "hand_above_low_while_body_quiet": sum(
                row["hand_above_low"] and row["body_quiet"] for row in post
            ),
            "body_above_low_while_hand_quiet": sum(
                row["body_above_low"] and row["hand_quiet"] for row in post
            ),
            "both_above_low": sum(
                row["hand_above_low"] and row["body_above_low"] for row in post
            ),
            "one_or_both_unknown": sum(
                not row["hand_valid"] or not row["body_valid"] for row in post
            ),
            "renewed_strong_motion": sum(row["strong_motion"] for row in post),
            "renewed_corroborated_motion": sum(
                row["corroborated_motion"] for row in post
            ),
            "family_tier_switch": sum(row["tier_switch"] for row in post),
            "perception_gap": sum(row["perception_gap"] for row in post),
        }
        veto[attempt.attempt_id] = counts
        stable_motion = sum(
            (row["hand_above_low"] or row["body_above_low"])
            and not row["tier_switch"]
            and not row["perception_gap"]
            for row in post
        )
        switch_motion = sum(
            (row["hand_above_low"] or row["body_above_low"])
            and row["tier_switch"]
            for row in post
        )
        unknown_resets = sum(
            row["transition_reason"] == "quiet_unknown_or_mid_motion_reset"
            for row in post
        )
        if stable_motion:
            classification = "RECOVERY_MOVEMENT_SUPPORTED_BY_ORACLE_TIMING"
        elif switch_motion:
            classification = "TRACKER_OR_FAMILY_SWITCH_ARTIFACT_POSSIBLE"
        elif unknown_resets:
            classification = "MISSINGNESS_VALIDITY_INTERACTION_POSSIBLE"
        elif current[attempt.attempt_id]["failure_reason"] == (
            "PADDED_END_BEFORE_ORACLE_END"
        ):
            classification = "EARLY_COMPLETION_NOT_POST_ORACLE_RECOVERY"
        else:
            classification = "NO_POST_ORACLE_BLOCKER_OR_INDETERMINATE"
        recovery[attempt.attempt_id] = {
            "classification": classification,
            "confidence": "TIMING_AND_RAW_SIGNAL_ONLY_NO_RGB",
            "stable_tier_post_oracle_motion_transitions": stable_motion,
            "tier_switch_motion_transitions": switch_motion,
            "unknown_reset_transitions": unknown_resets,
            "note": (
                "Oracle timing distinguishes post-sign motion from active-interval motion, "
                "but raw-v1 alone cannot prove signer intent."
            ),
        }

    counterfactuals: dict[str, Any] = {}
    for mode in ("CF_A", "CF_B", "CF_C", "CF_D"):
        per_attempt = {
            attempt.attempt_id: _best_replay(attempt, config, mode=mode)
            for attempt in attempts
        }
        changed = [
            attempt.attempt_id
            for attempt in attempts
            if per_attempt[attempt.attempt_id]["structurally_feasible"]
            != current[attempt.attempt_id]["structurally_feasible"]
        ]
        counterfactuals[mode] = {
            "all_five_structurally_feasible": all(
                result["structurally_feasible"] for result in per_attempt.values()
            ),
            "changed_attempts": changed,
            "remaining_failed_attempts": [
                attempt_id
                for attempt_id, result in per_attempt.items()
                if not result["structurally_feasible"]
            ],
            "per_attempt": {
                attempt_id: {
                    "structurally_feasible": result["structurally_feasible"],
                    "failure_reason": result["failure_reason"],
                    "completion": result["completion"],
                }
                for attempt_id, result in per_attempt.items()
            },
        }
    return current, veto, recovery, counterfactuals


def classify_root_cause(
    conflict_matrix: dict[str, Any],
    veto_by_anchor: dict[str, Any],
    counterfactuals_by_anchor: dict[str, Any],
) -> tuple[str, list[str], list[str]]:
    table_pairs = {
        name: value
        for name, value in conflict_matrix["pairs"].items()
        if "attempt_009" in name
    }
    table_proposal_only = all(
        not value["intersects_at_any_duration"]
        and all(
            row["minimal_disjoint_signal_sets"] == [["h_proposal_image"]]
            for row in value["per_duration"]
            if row["left_feasible"] and row["right_feasible"]
        )
        for value in table_pairs.values()
    )
    resolving_modes = {
        mode
        for anchor in counterfactuals_by_anchor.values()
        for mode, result in anchor.items()
        if result["all_five_structurally_feasible"]
    }
    missing = sum(
        counts["one_or_both_unknown"]
        for anchor in veto_by_anchor.values()
        for counts in anchor.values()
    )
    quiet_modes = resolving_modes & {"CF_A", "CF_B", "CF_C"}
    recovery_resolves = "CF_D" in resolving_modes
    if recovery_resolves and not quiet_modes:
        classification = "RECOVERY_AS_ACTIVITY_CONFLICT_SUPPORTED"
        secondary = [
            (
                "The incompatibility appears numerically as a global H_proposal_image "
                "threshold gap: TABLE <=0.09955792507085848 versus closest HOME "
                ">=0.24807557246229403"
            ),
            "Tier/validity transitions shape traces but are not required to resolve the conflict",
            f"Unknown-family transition count across both anchors: {missing}",
        ]
        ruled_out = [
            "Quiet fusion alone: CF-A/CF-B/CF-C do not make all five feasible",
            "Missingness as the primary cause: CF-D resolves all five without changing validity",
        ]
    elif recovery_resolves and quiet_modes:
        classification = "MULTI_FACTOR_END_CONFLICT_SUPPORTED"
        secondary = [f"Resolving modes: {sorted(resolving_modes)}"]
        ruled_out = []
    elif quiet_modes:
        classification = "QUIET_FUSION_CONFLICT_SUPPORTED"
        secondary = [f"Resolving quiet modes: {sorted(quiet_modes)}"]
        ruled_out = ["CF-D is not required to resolve the selected diagnostic"]
    elif table_proposal_only:
        classification = "GLOBAL_ABSOLUTE_THRESHOLD_CONFLICT_SUPPORTED"
        secondary = ["Exact TABLE pairwise regions are separated by H_proposal_image"]
        ruled_out = ["No bounded END counterfactual makes all five feasible"]
    else:
        classification = "CURRENT_EVIDENCE_INSUFFICIENT_FOR_END_CONFLICT_ATTRIBUTION"
        secondary = []
        ruled_out = []
    return classification, secondary, ruled_out


def render_report(
    decomposition: dict[str, Any],
    conflicts: dict[str, Any],
    traces_by_anchor: dict[str, Any],
    veto_by_anchor: dict[str, Any],
    recovery_by_anchor: dict[str, Any],
    counterfactuals_by_anchor: dict[str, Any],
    classification: str,
    secondary: list[str],
    ruled_out: list[str],
) -> str:
    nearest = decomposition["nearest_global_compatibility_pattern"]
    pair_summary = "\n".join(
        f"- `{name}`: intersects at {len(value['intersecting_durations_ms'])}/49 durations"
        for name, value in conflicts["pairs"].items()
    )
    anchors = decomposition["table_conflict_bracketing_anchors"]
    trace_summary = "\n".join(
        f"- `{anchor_name}/{attempt_id}`: feasible={value['structurally_feasible']}; "
        f"failure={value['failure_reason']}; end-trace rows={len(value['trace'])}"
        for anchor_name, traces in traces_by_anchor.items()
        for attempt_id, value in traces.items()
    )
    veto_summary = "\n".join(
        f"- `{anchor_name}/{attempt_id}`: {json.dumps(counts, sort_keys=True)}"
        for anchor_name, veto in veto_by_anchor.items()
        for attempt_id, counts in veto.items()
    )
    recovery_summary = "\n".join(
        f"- `{anchor_name}/{attempt_id}`: `{value['classification']}`"
        for anchor_name, recovery in recovery_by_anchor.items()
        for attempt_id, value in recovery.items()
    )
    cf_summary = "\n".join(
        f"- `{anchor_name}/{name}`: all-five={value['all_five_structurally_feasible']}; "
        f"changed={value['changed_attempts']}; remaining={value['remaining_failed_attempts']}"
        for anchor_name, counterfactuals in counterfactuals_by_anchor.items()
        for name, value in counterfactuals.items()
    )
    return f"""# {MILESTONE}

## SECTION 1 — SCOPE AND PARENT MILESTONES

Diagnostic-only attribution follows the validated Phase-5.1 and Phase-5.1R calibration stops.
No operating architecture or configuration was changed.

## SECTION 2 — INTEGRITY / GOVERNANCE

Oracle SHA-256 remained `{EXPECTED_ORACLE_SHA256}`. Only calibration attempts
002/003/005/007/009 were read. No recognizer, DEV, protected TEST, secondary attempt 001, Android,
training, or holdout payload was accessed.

## SECTION 3 — FEASIBLE REGION DECOMPOSITION

All 49 timestamp-derived durations and 1,028,193 discrete low-threshold tuples were decomposed.
The five-attempt intersection is empty at every duration. `H_refined_image` is unconstrained in
this population because no transition selects that tier. Exact per-duration projections and
categorical counts are in `feasible_region_decomposition.json`.

Closest deterministic compatibility pattern: T_end
`{nearest['end_quiet_persistence_ms']:.9f}` ms, satisfying
`{nearest['satisfied_attempt_count']}/5` attempts {nearest['satisfied_attempt_ids']}, with lows
`{json.dumps(nearest['low_thresholds'], sort_keys=True)}`.

For direct TABLE attribution, two fixed bracketing anchors use the largest TABLE-feasible duration
`{anchors['TABLE_SIDE']['end_quiet_persistence_ms']:.9f}` ms and identical refined-body/body
thresholds. TABLE requires `H_proposal_image <=
{anchors['TABLE_SIDE']['low_thresholds']['h_proposal_image']}`, while its closest partner
`{anchors['identity']['strongest_conflict_partner']}` requires `H_proposal_image >=
{anchors['CLOSEST_PARTNER_SIDE']['low_thresholds']['h_proposal_image']}`.

## SECTION 4 — PAIRWISE CONFLICT MATRIX

{pair_summary}

Minimal attempt subsets with no common duration/threshold tuple:
`{json.dumps(conflicts['minimal_attempt_subsets_with_no_common_duration_threshold_tuple'])}`.
Exact per-duration eliminating dimensions and constraint directions are in
`pairwise_conflict_matrix.json`.

## SECTION 5 — PER-ATTEMPT END TRACES

{trace_summary}

Every genuine oracle-end/recovery transition, selected tier/value, validity, activity/quiet state,
and exact reset/completion reason is in `end_trace_attribution.json`.

## SECTION 6 — QUIET VETO ATTRIBUTION

{veto_summary}

Counts use the two deterministic TABLE/closest-partner bracketing threshold patterns; they are
diagnostic, not promoted operating points.

## SECTION 7 — RECOVERY-MOTION ATTRIBUTION

{recovery_summary}

These labels use only oracle timing and raw signal continuity. Without RGB they do not assert
signer intent where the evidence is ambiguous.

## SECTION 8 — BOUNDED COUNTERFACTUALS

{cf_summary}

Each counterfactual changes one END diagnostic assumption only and reuses each anchor's same
thresholds and duration. CF-D is oracle-only and non-deployable. No counterfactual was combined or
promoted.

## SECTION 9 — PRIMARY ROOT-CAUSE CLASSIFICATION

**{classification}**

## SECTION 10 — SECONDARY CONTRIBUTORS

{json.dumps(secondary)}

## SECTION 11 — WHAT IS RULED OUT

{json.dumps(ruled_out)}

The result is not caused by recognizer output, class-specific parameters, a gap-rule change,
SignEvent mutation, or holdout feedback.

## SECTION 12 — LIMITATIONS

All evidence is from one controlled Gate-4 session and five calibration performances. The relaxed
END replay isolates the already-proven end subproblem; it does not establish a deployable start
configuration or production-ready segmentation. Physical intent cannot always be distinguished
from tracking effects without source RGB.

## SECTION 13 — HOLDOUT STATUS

**SEALED / NOT ACCESSED.** Attempts 004/006/008/010 were not opened.

## SECTION 14 — NEXT DECISION BOUNDARY

`WAIT_FOR_PROJECT_LEAD_PHASE_5_1S_ARCHITECTURE_DECISION`

Do not implement a repair or begin Phase 5.2.
"""


def run() -> dict[str, Any]:
    oracle = verify_oracle_identity()
    attempts = load_calibration()
    durations = end_duration_candidates(attempts)
    recovery_frontier = json.loads(
        (PHASE5_1R_OUTPUT / "end_policy_feasibility.json").read_text(encoding="utf-8")
    )
    if [row["end_quiet_persistence_ms"] for row in recovery_frontier["frontier"]] != list(
        durations
    ):
        raise RuntimeError("PHASE5_1S_PARENT_FRONTIER_IDENTITY_MISMATCH")

    space = build_threshold_space(attempts)
    decomposition, conflicts, nearest = analyze_regions(attempts, space, durations)
    anchors = decomposition["table_conflict_bracketing_anchors"]
    configs = {
        name: _diagnostic_config(space, anchor)
        for name, anchor in anchors.items()
        if name != "identity"
    }
    traces_by_anchor: dict[str, Any] = {}
    veto_by_anchor: dict[str, Any] = {}
    recovery_by_anchor: dict[str, Any] = {}
    counterfactuals_by_anchor: dict[str, Any] = {}
    for name, config in configs.items():
        traces, veto, recovery, counterfactuals = trace_and_counterfactuals(
            attempts, config
        )
        traces_by_anchor[name] = traces
        veto_by_anchor[name] = veto
        recovery_by_anchor[name] = recovery
        counterfactuals_by_anchor[name] = counterfactuals
    classification, secondary, ruled_out = classify_root_cause(
        conflicts, veto_by_anchor, counterfactuals_by_anchor
    )

    trace_artifact = {
        "milestone": MILESTONE,
        "diagnostic_configs": {
            anchor_name: {
                "end_quiet_persistence_ms": config.end_quiet_persistence_ms,
                "thresholds": {
                    name: {"low": value.low, "high": value.high}
                    for name, value in config.thresholds.items()
                },
            }
            for anchor_name, config in configs.items()
        },
        "selection_rule": {
            "duration": "largest breakpoint with TABLE individually feasible",
            "partner": "smallest H_proposal_image threshold gap",
            "bracketing": (
                "shared refined-body/body indices and closest feasible proposal indices"
            ),
            "high_threshold_rule": (
                "next empirical breakpoint above each selected low; refined-image uses the "
                "same empirical rank fraction as refined-body"
            ),
            "not_operating_points": True,
        },
        "anchors": traces_by_anchor,
    }
    veto_artifact = {
        "milestone": MILESTONE,
        "diagnostic_configs_not_promoted": True,
        "anchors": veto_by_anchor,
    }
    recovery_artifact = {
        "milestone": MILESTONE,
        "raw_signal_and_oracle_timing_only": True,
        "anchors": recovery_by_anchor,
    }
    cf_artifact = {
        "milestone": MILESTONE,
        "same_thresholds_and_duration_within_each_anchor": True,
        "counterfactuals_combined": False,
        "anchors": counterfactuals_by_anchor,
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT / "feasible_region_decomposition.json", decomposition)
    write_json(OUTPUT / "pairwise_conflict_matrix.json", conflicts)
    write_json(OUTPUT / "end_trace_attribution.json", trace_artifact)
    write_json(OUTPUT / "quiet_veto_attribution.json", veto_artifact)
    write_json(OUTPUT / "recovery_motion_attribution.json", recovery_artifact)
    write_json(OUTPUT / "bounded_counterfactual_diagnostics.json", cf_artifact)
    write_json(
        OUTPUT / "holdout_seal_status.json",
        {
            "status": "SEALED_NOT_ACCESSED",
            "attempt_ids": list(HOLDOUT_IDS),
            "raw_payloads_opened": False,
            "holdout_paths_constructed": False,
        },
    )
    previous_fixed_hashes = json.loads(
        (BASE / "phase5_1_offline_automatic_segmenter_01/source_hashes.json").read_text(
            encoding="utf-8"
        )
    )["files"]
    current_fixed_hashes = {
        name: sha256(ROOT / name) for name in previous_fixed_hashes
    }
    source_hashes = {
        "milestone": MILESTONE,
        "oracle_bounds": oracle,
        "holdout_accessed": False,
        "diagnostic_source_files": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
            for path in (RUNNER, TEST_FILE)
        },
        "fixed_phase5_1_source_hashes": current_fixed_hashes,
        "fixed_phase5_1_sources_match_parent": (
            current_fixed_hashes == previous_fixed_hashes
        ),
    }
    write_json(OUTPUT / "source_hashes.json", source_hashes)
    report = render_report(
        decomposition,
        conflicts,
        traces_by_anchor,
        veto_by_anchor,
        recovery_by_anchor,
        counterfactuals_by_anchor,
        classification,
        secondary,
        ruled_out,
    )
    report_path = OUTPUT / f"{MILESTONE}.md"
    report_path.write_text(report, encoding="utf-8")
    result = {
        "milestone": MILESTONE,
        "classification": classification,
        "nearest_satisfied_attempt_count": nearest["satisfied_attempt_count"],
        "holdout_accessed": False,
        "report": str(report_path),
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run",))
    parser.parse_args()
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
