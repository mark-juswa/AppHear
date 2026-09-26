"""Reusable diagnostics for causal PRE/ACTIVE/POST terminal evidence.

This module summarizes an already-frozen probability stream. It does not decode,
train, select thresholds, or alter any runtime component.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np

SCHEMA = "apphear.diagnostics.terminal_evidence.v1"
COMPARISON_FEATURES = (
    "max_post_probability",
    "mean_post_probability",
    "mean_post_minus_active_margin",
    "post_dominant_fraction",
    "final_post_probability",
)


def distribution(values: Iterable[float]) -> dict[str, float | int | None]:
    data = np.asarray(list(values), np.float64)
    if not data.size:
        return {
            "count": 0,
            "min": None,
            "p10": None,
            "median": None,
            "mean": None,
            "p90": None,
            "p95": None,
            "max": None,
        }
    return {
        "count": int(data.size),
        "min": float(np.min(data)),
        "p10": float(np.percentile(data, 10)),
        "median": float(np.median(data)),
        "mean": float(np.mean(data)),
        "p90": float(np.percentile(data, 90)),
        "p95": float(np.percentile(data, 95)),
        "max": float(np.max(data)),
    }


def _runs(mask: np.ndarray, timestamps: np.ndarray) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    start: int | None = None
    for index, value in enumerate(mask.tolist() + [False]):
        if value and start is None:
            start = index
        elif not value and start is not None:
            end = index - 1
            runs.append(
                {
                    "start_local_index": start,
                    "end_local_index": end,
                    "start_ms": float(timestamps[start]),
                    "end_ms": float(timestamps[end]),
                    "observation_count": end - start + 1,
                    "span_ms": float(timestamps[end] - timestamps[start]),
                }
            )
            start = None
    return runs


def summarize_interval(
    timestamps_ms: Sequence[float] | np.ndarray,
    probabilities: Sequence[Sequence[float]] | np.ndarray,
    *,
    start_ms: float,
    end_ms: float,
    anchor_ms: float,
) -> dict[str, Any]:
    """Summarize genuine observations inside one inclusive causal interval."""

    timestamps = np.asarray(timestamps_ms, np.float64)
    probs = np.asarray(probabilities, np.float64)
    if timestamps.ndim != 1 or probs.shape != (len(timestamps), 3):
        raise ValueError("TERMINAL_EVIDENCE_SHAPE_MISMATCH")
    if len(timestamps) and np.any(np.diff(timestamps) <= 0.0):
        raise ValueError("TERMINAL_EVIDENCE_NON_CHRONOLOGICAL")
    indices = np.flatnonzero((timestamps >= float(start_ms)) & (timestamps <= float(end_ms)))
    if not len(indices):
        return {
            "schema": SCHEMA,
            "observation_count": 0,
            "first_observation_ms": None,
            "last_observation_ms": None,
            "observed_span_ms": 0.0,
            "max_post_probability": None,
            "mean_post_probability": None,
            "median_post_probability": None,
            "mean_active_probability": None,
            "max_post_minus_active_margin": None,
            "mean_post_minus_active_margin": None,
            "post_dominant_fraction": None,
            "post_dominant_observation_count": 0,
            "post_dominant_run_count": 0,
            "longest_post_dominant_span_ms": 0.0,
            "first_post_dominant_delay_from_anchor_ms": None,
            "active_return_after_post_dominance": False,
            "post_probability_time_integral_ms": 0.0,
            "positive_post_margin_time_integral_ms": 0.0,
            "final_pre_probability": None,
            "final_active_probability": None,
            "final_post_probability": None,
        }
    local_timestamps = timestamps[indices]
    local = probs[indices]
    pre = local[:, 0]
    active = local[:, 1]
    post = local[:, 2]
    margin = post - active
    dominant = np.argmax(local, axis=1) == 2
    runs = _runs(dominant, local_timestamps)
    first_dominant = int(np.flatnonzero(dominant)[0]) if np.any(dominant) else None
    active_return = bool(
        first_dominant is not None and np.any(np.argmax(local[first_dominant + 1 :], axis=1) == 1)
    )
    post_integral = float(np.trapezoid(post, local_timestamps)) if len(indices) > 1 else 0.0
    positive_margin_integral = (
        float(np.trapezoid(np.maximum(margin, 0.0), local_timestamps))
        if len(indices) > 1
        else 0.0
    )
    return {
        "schema": SCHEMA,
        "observation_count": int(len(indices)),
        "first_observation_ms": float(local_timestamps[0]),
        "last_observation_ms": float(local_timestamps[-1]),
        "observed_span_ms": float(local_timestamps[-1] - local_timestamps[0]),
        "max_post_probability": float(np.max(post)),
        "mean_post_probability": float(np.mean(post)),
        "median_post_probability": float(np.median(post)),
        "mean_active_probability": float(np.mean(active)),
        "max_post_minus_active_margin": float(np.max(margin)),
        "mean_post_minus_active_margin": float(np.mean(margin)),
        "post_dominant_fraction": float(np.mean(dominant)),
        "post_dominant_observation_count": int(np.count_nonzero(dominant)),
        "post_dominant_run_count": len(runs),
        "post_dominant_runs": runs,
        "longest_post_dominant_span_ms": max(
            (float(run["span_ms"]) for run in runs), default=0.0
        ),
        "first_post_dominant_delay_from_anchor_ms": (
            float(local_timestamps[first_dominant] - anchor_ms)
            if first_dominant is not None
            else None
        ),
        "active_return_after_post_dominance": active_return,
        "post_probability_time_integral_ms": post_integral,
        "positive_post_margin_time_integral_ms": positive_margin_integral,
        "final_pre_probability": float(pre[-1]),
        "final_active_probability": float(active[-1]),
        "final_post_probability": float(post[-1]),
    }


def build_control_envelope(
    successful_terminal: Sequence[dict[str, Any]],
    successful_intra_active: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    if not successful_terminal or not successful_intra_active:
        raise ValueError("TERMINAL_EVIDENCE_CONTROLS_REQUIRED")
    return {
        "schema": "apphear.diagnostics.terminal_evidence.control_envelope.v1",
        "comparison_features": list(COMPARISON_FEATURES),
        "successful_terminal_lower_p10": {
            feature: float(np.percentile([row[feature] for row in successful_terminal], 10))
            for feature in COMPARISON_FEATURES
        },
        "intra_active_upper_p95": {
            feature: float(np.percentile([row[feature] for row in successful_intra_active], 95))
            for feature in COMPARISON_FEATURES
        },
        "successful_terminal_distributions": {
            feature: distribution(row[feature] for row in successful_terminal)
            for feature in COMPARISON_FEATURES
        },
        "intra_active_distributions": {
            feature: distribution(row[feature] for row in successful_intra_active)
            for feature in COMPARISON_FEATURES
        },
        "classification_rule": {
            "signal_present": (
                "at least 3/5 metrics reach successful-terminal p10 and at least 4/5 "
                "exceed intra-ACTIVE p95"
            ),
            "signal_absent": (
                "at most 1/5 metrics reach successful-terminal p10 and at most 1/5 "
                "exceed intra-ACTIVE p95"
            ),
            "otherwise": "MIXED_OR_AMBIGUOUS",
            "threshold_search": False,
        },
    }


def classify_against_controls(
    summary: dict[str, Any], envelope: dict[str, Any]
) -> dict[str, Any]:
    if not summary.get("observation_count"):
        return {
            "classification": "MIXED_OR_AMBIGUOUS",
            "successful_floor_votes": 0,
            "intra_active_exceedance_votes": 0,
            "feature_comparisons": {},
        }
    comparisons = {}
    successful_votes = 0
    active_votes = 0
    for feature in COMPARISON_FEATURES:
        value = float(summary[feature])
        successful_floor = float(envelope["successful_terminal_lower_p10"][feature])
        active_ceiling = float(envelope["intra_active_upper_p95"][feature])
        reaches_success = value >= successful_floor
        exceeds_active = value > active_ceiling
        successful_votes += int(reaches_success)
        active_votes += int(exceeds_active)
        comparisons[feature] = {
            "value": value,
            "successful_terminal_p10": successful_floor,
            "intra_active_p95": active_ceiling,
            "reaches_successful_terminal_floor": reaches_success,
            "exceeds_intra_active_ceiling": exceeds_active,
        }
    if successful_votes >= 3 and active_votes >= 4:
        classification = "MODEL_TERMINAL_SIGNAL_PRESENT_DECODER_NOT_USING_IT"
    elif successful_votes <= 1 and active_votes <= 1:
        classification = "MODEL_TERMINAL_SIGNAL_ABSENT"
    else:
        classification = "MIXED_OR_AMBIGUOUS"
    return {
        "classification": classification,
        "successful_floor_votes": successful_votes,
        "intra_active_exceedance_votes": active_votes,
        "feature_comparisons": comparisons,
    }
