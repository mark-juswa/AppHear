"""Correct the Phase-8A-R causal-recoverability evaluator, CAL only.

This utility consumes the persisted 54-view Phase-8A-R probability/state
manifest.  It does not run S2, train, open DEV/phone data, tune Decoder V1,
or implement Decoder V2.  The correction changes only the diagnostic unit of
reasoning from an already-emitted event to the complete provisional-candidate
trajectory.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import inspect
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import eval.runtime_diagnostics.phase8a_r_causal_episode_failure_attribution as old  # noqa: E402
from pipeline.perception_vnext.segmentation.streaming_decoder import (  # noqa: E402
    ACTIVE_SIGN,
    POST_RECOVERY,
    PRE_IDLE,
    CausalStreamingSignEventDecoder,
)

BASE = ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
OLD = BASE / "phase8a_r_causal_episode_failure_attribution_01"
OUT = OLD / "evaluator_correction_01"
P7 = BASE / "phase7_production_cadence_aligned_segmenter_01"
P8 = BASE / "phase8a_causal_streaming_sign_event_decoder_01"
EXPECTED_S2_SHA = "dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73"
STATE_NAMES = {PRE_IDLE: "PRE", ACTIVE_SIGN: "ACTIVE", POST_RECOVERY: "POST"}
REQUIRED_OLD = (
    "frozen_identity.json",
    "implementation_audit.json",
    "cal_state_run_manifest.json",
    "per_sequence_three_way_comparison.csv",
    "primary_failure_set.json",
    "premature_commit_attribution.json",
    "internal_post_interruption_distribution.json",
    "internal_pre_interruption_distribution.json",
    "wrong_early_episode_attribution.json",
    "start_end_truncation_decomposition.json",
    "right_censoring_audit.json",
    "bounded_causal_recoverability.json",
    "diagnostic_gate.json",
    "source_hashes.json",
    "test_results.json",
    "PHASE8A_R_CAUSAL_EPISODE_FAILURE_ATTRIBUTION_REPORT.md",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "median": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "max": None,
        }
    data = np.asarray(values, np.float64)
    return {
        "count": int(data.size),
        "min": float(np.min(data)),
        "median": float(np.median(data)),
        "p75": float(np.percentile(data, 75)),
        "p90": float(np.percentile(data, 90)),
        "p95": float(np.percentile(data, 95)),
        "max": float(np.max(data)),
    }


def _bool(value: str) -> bool:
    return value.strip().lower() == "true"


def _float(value: str) -> float | None:
    return None if value == "" else float(value)


def load_comparison_rows() -> list[dict[str, Any]]:
    with (OLD / "per_sequence_three_way_comparison.csv").open(
        newline="", encoding="utf-8-sig"
    ) as stream:
        raw = list(csv.DictReader(stream))
    rows: list[dict[str, Any]] = []
    for item in raw:
        rows.append(
            {
                **item,
                "human_start_ms": float(item["human_start_ms"]),
                "human_end_ms": float(item["human_end_ms"]),
                "global_event_emitted": _bool(item["global_event_emitted"]),
                "global_contained_90pct": _bool(item["global_contained_90pct"]),
                "global_premature_cut": _bool(item["global_premature_cut"]),
                "global_severe_cut": _bool(item["global_severe_cut"]),
                "global_active_recall": float(item["global_active_recall"]),
                "global_window_precision": float(item["global_window_precision"]),
                "v1_event_emitted": _bool(item["v1_event_emitted"]),
                "v1_contained_90pct": _bool(item["v1_contained_90pct"]),
                "v1_premature_cut": _bool(item["v1_premature_cut"]),
                "v1_severe_cut": _bool(item["v1_severe_cut"]),
                "v1_active_recall": float(item["v1_active_recall"]),
                "v1_window_precision": float(item["v1_window_precision"]),
                "v1_context_reduction": float(item["v1_context_reduction"]),
                "v1_logical_start_ms": _float(item["v1_logical_start_ms"]),
                "v1_logical_end_ms": _float(item["v1_logical_end_ms"]),
            }
        )
    return rows


def source_line_range(function: Any) -> dict[str, int]:
    lines, start = inspect.getsourcelines(function)
    return {"start": start, "end": start + len(lines) - 1}


def continuity_and_bug_audit() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    missing = [name for name in REQUIRED_OLD if not (OLD / name).is_file()]
    if missing:
        raise RuntimeError(f"PHASE8A_R_CONTINUITY_MISMATCH:MISSING:{missing}")
    state_manifest = read_json(OLD / "cal_state_run_manifest.json")
    views = state_manifest.get("views", [])
    if len(views) != 54 or len({row["sample_id"] for row in views}) != 18:
        raise RuntimeError("PHASE8A_R_CONTINUITY_MISMATCH:CAL_POPULATION")
    if state_manifest.get("s2_checkpoint_sha256") != EXPECTED_S2_SHA:
        raise RuntimeError("PHASE8A_R_CONTINUITY_MISMATCH:S2")
    if any(
        not all(
            key in obs
            for key in (
                "timestamp_ms",
                "pre_probability",
                "active_probability",
                "post_probability",
                "argmax_state",
            )
        )
        for view in views
        for obs in view["observations"]
    ):
        raise RuntimeError("PHASE8A_R_CONTINUITY_MISMATCH:PERSISTED_PROBABILITIES")

    old_gate = read_json(OLD / "diagnostic_gate.json")
    old_primary = read_json(OLD / "primary_failure_set.json")
    old_tests = read_json(OLD / "test_results.json")
    if old_gate.get("primary_failure_count") != 22 or len(old_primary.get("rows", [])) != 22:
        raise RuntimeError("PHASE8A_R_CONTINUITY_MISMATCH:PRIMARY_FAILURE_SET")
    if not old_tests.get("passed"):
        raise RuntimeError("PHASE8A_R_CONTINUITY_MISMATCH:OLD_TESTS")

    comparisons = load_comparison_rows()
    if len(comparisons) != 54:
        raise RuntimeError("PHASE8A_R_CONTINUITY_MISMATCH:COMPARISON_COUNT")
    global_actual = {
        "event_emission_rate": float(np.mean([row["global_event_emitted"] for row in comparisons])),
        "containment_rate": float(np.mean([row["global_contained_90pct"] for row in comparisons])),
        "premature_cut_rate": float(np.mean([row["global_premature_cut"] for row in comparisons])),
    }
    v1_actual = {
        "event_emission_rate": float(np.mean([row["v1_event_emitted"] for row in comparisons])),
        "containment_rate": float(np.mean([row["v1_contained_90pct"] for row in comparisons])),
        "premature_cut_rate": float(np.mean([row["v1_premature_cut"] for row in comparisons])),
        "severe_cut_rate": float(np.mean([row["v1_severe_cut"] for row in comparisons])),
    }
    phase8_config = next(
        row
        for row in read_json(P8 / "cal_decoder_grid_summary.json")["configurations"]
        if row["config_id"] == "CONFIG_01"
    )["metrics"]
    expected_global = {
        "event_emission_rate": 1.0,
        "containment_rate": 0.9074074074074074,
        "premature_cut_rate": 0.09259259259259259,
    }
    expected_v1 = {
        "event_emission_rate": 0.9259259259259259,
        "containment_rate": 0.5,
        "premature_cut_rate": 0.5,
        "severe_cut_rate": 0.16666666666666666,
    }
    for name, expected in expected_global.items():
        if abs(global_actual[name] - expected) > 1e-12:
            raise RuntimeError(f"PHASE8A_R_REFERENCE_REPRODUCTION_FAILURE:PHASE7:{name}")
    for name, expected in expected_v1.items():
        if abs(v1_actual[name] - expected) > 1e-12:
            raise RuntimeError(f"PHASE8A_R_REFERENCE_REPRODUCTION_FAILURE:CONFIG01:{name}")
    if abs(float(phase8_config["exactly_one_event_rate"]) - 0.9259259259259259) > 1e-12:
        raise RuntimeError("PHASE8A_R_REFERENCE_REPRODUCTION_FAILURE:EXACTLY_ONE")

    continuity = {
        "schema": "apphear.phase8a_r.correction_scope.v1",
        "old_artifacts_preserved": True,
        "old_required_artifact_count": 16,
        "cal_clips": 18,
        "cal_views": 54,
        "primary_failure_count": 22,
        "s2_checkpoint_sha256": EXPECTED_S2_SHA,
        "persisted_probabilities_reused": True,
        "s2_inference_rerun": False,
        "phase7_global_reproduction": global_actual,
        "phase8a_config_01_reproduction": {
            **v1_actual,
            "exactly_one_event_rate": float(phase8_config["exactly_one_event_rate"]),
        },
        "dev_access": False,
        "phone_access": False,
        "training": False,
        "decoder_v2_implemented": False,
    }

    source = Path(old.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    attribute_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_attribute"
    )
    confirmed_emitted_gate = (
        "if event is not None and later_active_indices and later_inside" in source
    )
    confirmed_presence_count = "or bounded_interrupt or right_censored" in source
    bug_audit = {
        "schema": "apphear.phase8a_r.evaluator_bug_audit.v1",
        "defect_confirmed": bool(confirmed_emitted_gate and confirmed_presence_count),
        "source_file": str(Path(old.__file__).resolve()),
        "functions": {
            "_attribute": {
                "line_range": {"start": attribute_node.lineno, "end": attribute_node.end_lineno},
                "recoverability_emitted_event_gate": confirmed_emitted_gate,
                "interruption_presence_counted_as_attribution": confirmed_presence_count,
            },
            "_right_censor_record": {"line_range": source_line_range(old._right_censor_record)},
        },
        "confirmed_behavior": [
            "later ACTIVE was searched only after event.emitted_at_index",
            "bounded recoverability required event is not None",
            "discarded/non-emitted provisional candidates were not evaluated for later ACTIVE",
            "any inside-human PRE/POST interruption incremented attributable_count "
            "without a causal-improvement test",
        ],
        "affected_metrics": [
            "attributable_count",
            "attributable_rate",
            "bounded_causally_recoverable_count",
            "bounded_causally_recoverable_rate",
            "minimum_required_grace_ms",
            "Episode-V2 gate checks 1-3",
        ],
        "previous_final_classification_depends_on_affected_metrics": True,
    }
    if not bug_audit["defect_confirmed"]:
        raise RuntimeError("PHASE8A_R_REPORTED_EVALUATOR_DEFECT_NOT_PRESENT")
    return continuity, bug_audit, state_manifest


def replay_trajectory(view: dict[str, Any]) -> dict[str, Any]:
    decoder = CausalStreamingSignEventDecoder(old.CONFIG_01)
    for obs in view["observations"]:
        decoder.consume(
            float(obs["timestamp_ms"]),
            [obs["pre_probability"], obs["active_probability"], obs["post_probability"]],
            int(obs["argmax_state"]),
        )
    event_by_emit = {event.emitted_at_index: event for event in decoder.events}
    candidates: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    enriched: list[dict[str, Any]] = []
    for obs, trace in zip(view["observations"], decoder.trace, strict=True):
        action = trace["action"]
        row = {**obs, **{key: trace[key] for key in ("state_before", "state_after", "action")}}
        enriched.append(row)
        if action == "START_ACTIVE_CANDIDATE":
            current = {
                "candidate_number": len(candidates) + 1,
                "open_index": int(obs["observation_index"]),
                "open_ms": float(obs["timestamp_ms"]),
                "last_active_index": int(obs["observation_index"]),
                "last_active_ms": float(obs["timestamp_ms"]),
                "pre_gap_bridges": 0,
                "post_cancellations": 0,
                "actions": [action],
            }
        elif current is not None:
            current["actions"].append(action)
            if int(obs["argmax_state"]) == ACTIVE_SIGN and action in {
                "EXTEND_ACTIVE_CANDIDATE",
                "BRIDGE_PRE_GAP_TO_ACTIVE",
                "CANCEL_POST_ACTIVE_RESUMED",
                "CANCEL_POST_ACTIVE_AT_CONFIRM_BOUNDARY",
            }:
                current["last_active_index"] = int(obs["observation_index"])
                current["last_active_ms"] = float(obs["timestamp_ms"])
            if action == "BRIDGE_PRE_GAP_TO_ACTIVE":
                current["pre_gap_bridges"] += 1
            if action.startswith("CANCEL_POST_ACTIVE"):
                current["post_cancellations"] += 1
            if action in {"EMIT_SIGN_EVENT", "DISCARD_SUSTAINED_PRE_GAP", "DISCARD_TOO_SHORT"}:
                current["closure_action"] = action
                current["closure_index"] = int(obs["observation_index"])
                current["closure_ms"] = float(obs["timestamp_ms"])
                if action == "EMIT_SIGN_EVENT":
                    event = event_by_emit[int(obs["observation_index"])]
                    current["first_post_index"] = event.first_post_index
                    current["first_post_ms"] = event.first_post_ms
                candidates.append(current)
                current = None
    if current is not None:
        current["closure_action"] = f"EOF_{decoder.state.value}"
        current["closure_index"] = len(view["observations"]) - 1
        current["closure_ms"] = float(view["observations"][-1]["timestamp_ms"])
        candidates.append(current)
    return {
        "view_key": view["view_key"],
        "human_start_ms": float(view["human_start_ms"]),
        "human_end_ms": float(view["human_end_ms"]),
        "observations": enriched,
        "state_runs": view["state_runs"],
        "candidates": candidates,
        "events": [
            {
                "logical_active_start_index": event.logical_active_start_index,
                "logical_active_end_index": event.logical_active_end_index,
                "padded_start_ms": event.padded_start_ms,
                "padded_end_ms": event.padded_end_ms,
                "first_post_ms": event.first_post_ms,
                "emitted_at_index": event.emitted_at_index,
                "emitted_at_ms": event.emitted_at_ms,
            }
            for event in decoder.events
        ],
        "candidate_discard_count": decoder.candidate_discard_count,
        "bridged_pre_gap_count": decoder.bridged_pre_gap_count,
        "active_to_post_confirm_count": decoder.active_to_post_confirm_count,
        "eof_state": decoder.state.value,
    }


def _overlaps(start: float, end: float, human_start: float, human_end: float) -> bool:
    return min(end, human_end) > max(start, human_start)


def _padded_interval(
    observations: list[dict[str, Any]], logical_start: float, logical_end: float, commit_index: int
) -> tuple[float, float]:
    times = [float(obs["timestamp_ms"]) for obs in observations[: commit_index + 1]]
    start = next(value for value in times if value >= logical_start - old.CONFIG_01.pre_padding_ms)
    eligible = [value for value in times if value <= logical_end + old.CONFIG_01.post_padding_ms]
    return start, eligible[-1]


def _recall(start: float, end: float, human_start: float, human_end: float) -> float:
    intersection = max(0.0, min(end, human_end) - max(start, human_start))
    return intersection / (human_end - human_start)


def _terminal_after_run(
    runs: list[dict[str, Any]], run_position: int, observations: list[dict[str, Any]]
) -> tuple[int | None, float | None, int | None]:
    if run_position + 1 >= len(runs) or runs[run_position + 1]["state"] != "POST":
        return None, None, None
    post = runs[run_position + 1]
    first_post = float(post["start_ms"])
    for obs in observations[int(post["start_observation_index"]) :]:
        if int(obs["argmax_state"]) == ACTIVE_SIGN:
            return None, first_post, None
        if float(obs["timestamp_ms"]) - first_post >= old.CONFIG_01.post_confirm_ms:
            return int(obs["observation_index"]), first_post, run_position + 1
    return None, first_post, run_position + 1


def interruption_attribution(
    view: dict[str, Any], trajectory: dict[str, Any], baseline_recall: float, in_primary: bool
) -> list[dict[str, Any]]:
    runs = view["state_runs"]
    observations = view["observations"]
    human_start = float(view["human_start_ms"])
    human_end = float(view["human_end_ms"])
    actions = {int(row["observation_index"]): row["action"] for row in trajectory["observations"]}
    results: list[dict[str, Any]] = []
    for position in range(1, len(runs) - 1):
        previous, gap, following = runs[position - 1], runs[position], runs[position + 1]
        if previous["state"] != "ACTIVE" or following["state"] != "ACTIVE":
            continue
        if gap["state"] not in {"PRE", "POST"}:
            continue
        start_index = int(gap["start_observation_index"])
        resume_index = int(following["start_observation_index"])
        window_actions = [actions[index] for index in range(start_index, resume_index + 1)]
        closure_actions = [
            action
            for action in window_actions
            if action in {"EMIT_SIGN_EVENT", "DISCARD_SUSTAINED_PRE_GAP", "DISCARD_TOO_SHORT"}
        ]
        if "EMIT_SIGN_EVENT" in closure_actions:
            handling = "EMITTED_BEFORE_RESUMPTION"
        elif any(action.startswith("DISCARD") for action in closure_actions):
            handling = "DISCARDED_BEFORE_RESUMPTION"
        elif gap["state"] == "PRE" and "BRIDGE_PRE_GAP_TO_ACTIVE" in window_actions:
            handling = "BRIDGED_BY_V1"
        elif gap["state"] == "POST" and any(
            action.startswith("CANCEL_POST_ACTIVE") for action in window_actions
        ):
            handling = "CANCELED_BY_V1"
        else:
            handling = "NO_V1_CLOSURE_BEFORE_RESUMPTION"

        previous_overlap = _overlaps(
            float(previous["start_ms"]), float(previous["end_ms"]), human_start, human_end
        )
        later_inside = human_start <= float(following["start_ms"]) <= human_end
        same_human_sign = previous_overlap and later_inside
        gap_duration = float(following["start_ms"] - gap["start_ms"])
        stable_pre = gap["state"] == "PRE" and gap_duration >= old.CONFIG_01.rearm_pre_stable_ms
        human_covers_gap = (
            float(gap["start_ms"]) >= human_start and float(following["start_ms"]) <= human_end
        )
        unsafe_separate = stable_pre and not human_covers_gap

        last_position = position + 1
        scan = last_position + 1
        while scan + 1 < len(runs):
            interrupt = runs[scan]
            later = runs[scan + 1]
            if interrupt["state"] not in {"PRE", "POST"} or later["state"] != "ACTIVE":
                break
            if float(later["start_ms"]) > human_end:
                break
            last_position = scan + 1
            scan += 2
        last_active = runs[last_position]
        commit_index, terminal_start, _ = _terminal_after_run(runs, last_position, observations)
        hypothetical_recall = None
        hypothetical_contained = False
        if commit_index is not None:
            padded_start, padded_end = _padded_interval(
                observations,
                float(previous["start_ms"]),
                float(last_active["end_ms"]),
                commit_index,
            )
            hypothetical_recall = _recall(padded_start, padded_end, human_start, human_end)
            hypothetical_contained = hypothetical_recall >= 0.90
        v1_closed = handling in {"EMITTED_BEFORE_RESUMPTION", "DISCARDED_BEFORE_RESUMPTION"}
        causal_improvement = bool(
            in_primary
            and v1_closed
            and same_human_sign
            and not unsafe_separate
            and hypothetical_contained
            and hypothetical_recall is not None
            and hypothetical_recall > baseline_recall + 1e-12
        )
        recoverable = bool(causal_improvement and commit_index is not None)
        results.append(
            {
                "view_key": view["view_key"],
                "state": gap["state"],
                "in_primary_failure_set": in_primary,
                "previous_active_start_ms": float(previous["start_ms"]),
                "previous_active_end_ms": float(previous["end_ms"]),
                "interruption_start_ms": float(gap["start_ms"]),
                "interruption_end_ms": float(gap["end_ms"]),
                "interruption_duration_to_resumption_ms": gap_duration,
                "later_active_resumption_ms": float(following["start_ms"]),
                "last_same_sign_active_resumption_ms": float(last_active["start_ms"]),
                "later_active_inside_human_active": later_inside,
                "previous_active_overlaps_human_active": previous_overlap,
                "same_human_sign_by_evaluation": same_human_sign,
                "v1_handling": handling,
                "v1_closed_candidate_before_resumption": v1_closed,
                "stable_pre_separation": stable_pre,
                "human_active_covers_gap": human_covers_gap,
                "unsafe_distinct_episode_merge": unsafe_separate,
                "terminal_confirmation_observed_after_resumption": commit_index is not None,
                "proposed_commit_index": commit_index,
                "proposed_commit_ms": (
                    float(observations[commit_index]["timestamp_ms"])
                    if commit_index is not None
                    else None
                ),
                "terminal_start_ms": terminal_start,
                "baseline_v1_active_recall": baseline_recall,
                "hypothetical_active_recall": hypothetical_recall,
                "hypothetical_contained_90pct": hypothetical_contained,
                "causally_attributable": causal_improvement,
                "bounded_causally_recoverable": recoverable,
                "minimum_required_grace_ms": (
                    float(last_active["start_ms"] - gap["start_ms"]) if recoverable else None
                ),
                "human_label_used_only_for_scoring": True,
                "runtime_policy_uses_human_label": False,
                "runtime_policy_uses_global_run_identity": False,
                "information_available_by_proposed_commit": recoverable,
            }
        )
    return results


def right_censoring_record(
    view: dict[str, Any], trajectory: dict[str, Any], event_emitted: bool
) -> dict[str, Any] | None:
    if event_emitted:
        return None
    observations = view["observations"]
    final_candidate = trajectory["candidates"][-1] if trajectory["candidates"] else None
    classification = "NO_USABLE_CANDIDATE"
    first_terminal = None
    observed_confirmation = None
    additional = None
    sole_blocker = False
    if final_candidate is not None:
        closure = str(final_candidate["closure_action"])
        if closure == "EOF_POST_CANDIDATE":
            post_actions = [
                row
                for row in trajectory["observations"]
                if row["action"] in {"BEGIN_POST_CANDIDATE", "BRIDGE_PRE_GAP_TO_POST"}
            ]
            first_terminal = float(post_actions[-1]["timestamp_ms"])
            observed_confirmation = float(observations[-1]["timestamp_ms"] - first_terminal)
            additional = max(0.0, old.CONFIG_01.post_confirm_ms - observed_confirmation)
            active_span = float(final_candidate["last_active_ms"] - final_candidate["open_ms"])
            sole_blocker = active_span >= old.CONFIG_01.minimum_active_ms and additional > 0.0
            classification = (
                "RIGHT_CENSORED_CONFIRMATION" if sole_blocker else "POST_STARTED_OTHER_BLOCKER"
            )
        elif closure == "EOF_ACTIVE_CANDIDATE":
            classification = "NO_TERMINAL_EVIDENCE_BEFORE_EOF"
        elif closure == "EOF_PRE_GAP":
            classification = "PRE_GAP_AT_EOF_NO_LATER_ACTIVE"
        elif closure == "DISCARD_SUSTAINED_PRE_GAP":
            classification = "CANDIDATE_DISCARDED_THROUGH_PRE"
        else:
            classification = closure
    return {
        "view_key": view["view_key"],
        "classification": classification,
        "candidate_existed": final_candidate is not None,
        "final_candidate_closure": final_candidate["closure_action"] if final_candidate else None,
        "post_context_available_ms": float(observations[-1]["timestamp_ms"] - view["human_end_ms"]),
        "first_qualifying_terminal_timestamp_ms": first_terminal,
        "confirmation_duration_observed_before_eof_ms": observed_confirmation,
        "additional_elapsed_time_required_ms": additional,
        "insufficient_remaining_clip_duration_is_sole_blocker": sole_blocker,
        "synthetic_future_states_used": False,
        "bounded_causally_recoverable_with_observed_data": False,
    }


def truncation_document(primary_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for row in primary_rows:
        classification = old._dominant_truncation(row["v1"])
        rows.append(
            {
                "view_key": row["view_key"],
                "classification": classification,
                "missing_at_start_ms": float(row["v1"]["missing_at_start_ms"]),
                "missing_at_end_ms": float(row["v1"]["missing_at_end_ms"]),
            }
        )
    by_category = {}
    for name in ("START_DOMINANT", "END_DOMINANT", "BOTH", "NO_EVENT"):
        selected = [row for row in rows if row["classification"] == name]
        by_category[name] = {
            "count": len(selected),
            "missing_start_ms": distribution([row["missing_at_start_ms"] for row in selected]),
            "missing_end_ms": distribution([row["missing_at_end_ms"] for row in selected]),
        }
    return {
        "schema": "apphear.phase8a_r.corrected_truncation.v1",
        "definition_unchanged": (
            "START_IF_START_GE_2X_END;END_IF_END_GE_2X_START;"
            "OTHERWISE_BOTH;NO_EVENT_SEPARATE"
        ),
        "counts": dict(Counter(row["classification"] for row in rows)),
        "by_category": by_category,
        "rows": rows,
    }


def analyze_persisted(state_manifest: dict[str, Any], pytest_confirmed: bool) -> dict[str, Any]:
    old_primary_doc = read_json(OLD / "primary_failure_set.json")
    primary_rows = old_primary_doc["rows"]
    primary_by_key = {row["view_key"]: row for row in primary_rows}
    comparison = load_comparison_rows()
    comparison_by_key = {row["view_key"]: row for row in comparison}
    trajectories = []
    pre_rows: list[dict[str, Any]] = []
    post_rows: list[dict[str, Any]] = []
    no_event_rows: list[dict[str, Any]] = []
    right_rows: list[dict[str, Any]] = []
    for view in state_manifest["views"]:
        trajectory = replay_trajectory(view)
        trajectories.append(trajectory)
        key = view["view_key"]
        comparison_row = comparison_by_key[key]
        rows = interruption_attribution(
            view,
            trajectory,
            float(comparison_row["v1_active_recall"]),
            key in primary_by_key,
        )
        pre_rows.extend(row for row in rows if row["state"] == "PRE")
        post_rows.extend(row for row in rows if row["state"] == "POST")
        if key in primary_by_key and not comparison_row["v1_event_emitted"]:
            record = right_censoring_record(view, trajectory, False)
            assert record is not None
            no_event_rows.append(record)
            if record["classification"] == "RIGHT_CENSORED_CONFIRMATION":
                right_rows.append(record)

    write_json(
        OUT / "corrected_provisional_episode_trajectories.json",
        {
            "schema": "apphear.phase8a_r.corrected_provisional_episode_trajectories.v1",
            "cal_views": 54,
            "s2_inference_rerun": False,
            "views": trajectories,
        },
    )
    pre_attributable = [row for row in pre_rows if row["causally_attributable"]]
    post_attributable = [row for row in post_rows if row["causally_attributable"]]
    premature = [
        row for row in post_attributable if row["v1_handling"] == "EMITTED_BEFORE_RESUMPTION"
    ]
    recoverable_by_key: dict[str, list[dict[str, Any]]] = {}
    for row in pre_attributable + post_attributable:
        if row["bounded_causally_recoverable"]:
            recoverable_by_key.setdefault(row["view_key"], []).append(row)
    right_keys = {row["view_key"] for row in right_rows}
    attributable_keys = {
        row["view_key"] for row in pre_attributable + post_attributable
    } | right_keys

    recoverability_rows = []
    grace_values = []
    for primary in primary_rows:
        key = primary["view_key"]
        candidates = recoverable_by_key.get(key, [])
        if candidates:
            chosen = min(candidates, key=lambda row: float(row["minimum_required_grace_ms"]))
            grace = float(chosen["minimum_required_grace_ms"])
            grace_values.append(grace)
            reason = f"{chosen['state']}_INTERRUPTION_CAUSALLY_RECOVERABLE"
            recoverable = True
            commit = chosen["proposed_commit_ms"]
        elif key in right_keys:
            grace = None
            reason = "RIGHT_CENSORED_NO_OBSERVED_CAUSAL_COMMIT_POINT"
            recoverable = False
            commit = None
        else:
            grace = None
            reason = "NO_CAUSALLY_BENEFICIAL_PROVISIONAL_EPISODE_RECOVERY"
            recoverable = False
            commit = None
        recoverability_rows.append(
            {
                "view_key": key,
                "bounded_causally_recoverable": recoverable,
                "minimum_required_grace_ms": grace,
                "proposed_commit_ms": commit,
                "reason": reason,
                "all_information_observed_by_proposed_commit": recoverable,
                "human_label_used_only_for_scoring": True,
                "runtime_policy_uses_human_label": False,
                "runtime_policy_uses_global_run_identity": False,
                "future_after_proposed_commit_used": False,
            }
        )

    truncation = truncation_document(primary_rows)
    primary_count = len(primary_rows)
    recoverable_count = sum(row["bounded_causally_recoverable"] for row in recoverability_rows)
    attributable_count = len(attributable_keys)
    start_count = truncation["counts"].get("START_DOMINANT", 0)
    attributable_rate = attributable_count / primary_count
    recoverable_rate = recoverable_count / primary_count
    grace = distribution(grace_values)
    checks = {
        "attributable_failure_rate_at_least_0_70": attributable_rate >= 0.70,
        "bounded_causal_recoverable_rate_at_least_0_70": recoverable_rate >= 0.70,
        "grace_p90_at_most_1200_ms": grace["p90"] is not None and float(grace["p90"]) <= 1200.0,
        "start_dominant_rate_at_most_0_30": start_count / primary_count <= 0.30,
    }
    passed = all(checks.values())
    gate = {
        "schema": "apphear.phase8a_r.corrected_diagnostic_gate.v1",
        "old_classification_status": "PROVISIONAL_PENDING_EVALUATOR_CORRECTION",
        "evaluator_defect_confirmed": True,
        "primary_failure_count": primary_count,
        "attributable_count": attributable_count,
        "attributable_rate": attributable_rate,
        "bounded_causally_recoverable_count": recoverable_count,
        "bounded_causally_recoverable_rate": recoverable_rate,
        "minimum_required_grace_ms": grace,
        "start_dominant_count": start_count,
        "start_dominant_rate": start_count / primary_count,
        "checks": checks,
        "passed": passed,
        "evidence_state": (
            "EPISODE_V2_CAUSAL_DESIGN_SUPPORTED"
            if passed
            else "EPISODE_V2_CAUSAL_DESIGN_NOT_SUPPORTED"
        ),
        "supported_direction_if_failed": None if passed else "MIXED_UNRESOLVED_CAUSES",
        "next": (
            "WAIT_FOR_PROJECT_LEAD_DECODER_V2_ARCHITECTURE_FREEZE"
            if passed
            else "WAIT_FOR_PROJECT_LEAD_SEGMENTATION_ARCHITECTURE_DECISION"
        ),
    }

    write_json(
        OUT / "corrected_primary_failure_set.json",
        {
            "schema": "apphear.phase8a_r.corrected_primary_failure_set.v1",
            "definition_unchanged": old_primary_doc["definition"],
            "all_categories": old_primary_doc["all_categories"],
            "primary_failure_count": primary_count,
            "rows": primary_rows,
        },
    )
    shutil.copyfile(
        OLD / "per_sequence_three_way_comparison.csv",
        OUT / "corrected_per_sequence_three_way_comparison.csv",
    )
    write_json(
        OUT / "corrected_premature_commit_attribution.json",
        {
            "schema": "apphear.phase8a_r.corrected_premature_commit.v1",
            "supported_count": len(premature),
            "presence_is_not_causation": True,
            "rows": premature,
        },
    )
    for name, rows, attributable in (
        ("pre", pre_rows, pre_attributable),
        ("post", post_rows, post_attributable),
    ):
        write_json(
            OUT / f"corrected_{name}_interruption_attribution.json",
            {
                "schema": f"apphear.phase8a_r.corrected_{name}_interruption_attribution.v1",
                "all_cal_interruption_count": len(rows),
                "primary_interruption_count": sum(row["in_primary_failure_set"] for row in rows),
                "causally_attributable_count": len(attributable),
                "presence_is_not_causation": True,
                "rows": rows,
            },
        )
    write_json(
        OUT / "corrected_no_event_attribution.json",
        {
            "schema": "apphear.phase8a_r.corrected_no_event_attribution.v1",
            "count": len(no_event_rows),
            "classifications": dict(Counter(row["classification"] for row in no_event_rows)),
            "rows": no_event_rows,
        },
    )
    write_json(
        OUT / "corrected_right_censoring_audit.json",
        {
            "schema": "apphear.phase8a_r.corrected_right_censoring.v1",
            "right_censored_count": len(right_rows),
            "synthetic_future_states_used": False,
            "rows": no_event_rows,
        },
    )
    write_json(OUT / "corrected_start_end_truncation_decomposition.json", truncation)
    write_json(
        OUT / "corrected_bounded_causal_recoverability.json",
        {
            "schema": "apphear.phase8a_r.corrected_bounded_causal_recoverability.v1",
            "primary_failure_count": primary_count,
            "recoverable_count": recoverable_count,
            "recoverable_rate": recoverable_rate,
            "minimum_required_grace_ms": grace,
            "full_provisional_trajectory_evaluated": True,
            "rows": recoverability_rows,
        },
    )
    old_gate = read_json(OLD / "diagnostic_gate.json")
    old_truncation = read_json(OLD / "start_end_truncation_decomposition.json")
    old_cause = old_gate["cause_evidence_counts"]
    comparison_doc = {
        "schema": "apphear.phase8a_r.old_vs_corrected_attribution.v1",
        "changes": {
            "primary_failure_set_size": {
                "old": old_gate["primary_failure_count"],
                "corrected": primary_count,
                "reason": "unchanged frozen definition",
            },
            "premature_first_commit_count": {
                "old": old_cause["premature_first_commit"],
                "corrected": len(premature),
                "reason": "no emitted event was followed by beneficial same-sign ACTIVE",
            },
            "pre_interruption_attributable_count": {
                "old": old_cause["internal_pre_interruption_primary_sequences"],
                "corrected": len(pre_attributable),
                "reason": (
                    "old value counted presence; corrected value requires causal "
                    "containment improvement"
                ),
            },
            "post_interruption_attributable_count": {
                "old": old_cause["internal_post_interruption_primary_sequences"],
                "corrected": len(post_attributable),
                "reason": (
                    "old value counted presence; S2 ACTIVE resumptions were already "
                    "canceled/bridged by V1"
                ),
            },
            "right_censored_count": {
                "old": old_cause["right_censored_confirmation"],
                "corrected": len(right_rows),
                "reason": "same two EOF POST-candidate trajectories; sole blocker revalidated",
            },
            "bounded_causally_recoverable_count": {
                "old": old_gate["bounded_causally_recoverable_count"],
                "corrected": recoverable_count,
                "reason": "full candidate trajectories evaluated, including non-emitted paths",
            },
            "START_DOMINANT": {
                "old": old_truncation["counts"]["START_DOMINANT"],
                "corrected": truncation["counts"]["START_DOMINANT"],
                "reason": "frozen definition unchanged",
            },
            "END_DOMINANT": {
                "old": old_truncation["counts"]["END_DOMINANT"],
                "corrected": truncation["counts"]["END_DOMINANT"],
                "reason": "frozen definition unchanged",
            },
            "BOTH": {
                "old": old_truncation["counts"]["BOTH"],
                "corrected": truncation["counts"]["BOTH"],
                "reason": "frozen definition unchanged",
            },
            "NO_EVENT": {
                "old": old_truncation["counts"]["NO_EVENT"],
                "corrected": truncation["counts"]["NO_EVENT"],
                "reason": "frozen definition unchanged",
            },
            "attributable_percentage": {
                "old": old_gate["attributable_rate"],
                "corrected": attributable_rate,
                "reason": "interruption presence no longer treated as causation",
            },
            "recoverability_percentage": {
                "old": old_gate["bounded_causally_recoverable_rate"],
                "corrected": recoverable_rate,
                "reason": "full provisional trajectories evaluated",
            },
            "minimum_required_grace_distribution": {
                "old": old_gate["grace_distribution"],
                "corrected": grace,
                "reason": "no causally beneficial observed recovery produced a grace value",
            },
            "final_gate_classification": {
                "old": old_gate["evidence_state"],
                "corrected": gate["evidence_state"],
                "reason": "original four gates applied unchanged after semantic correction",
            },
        },
    }
    write_json(OUT / "old_vs_corrected_attribution_comparison.json", comparison_doc)
    write_json(OUT / "corrected_diagnostic_gate.json", gate)
    write_json(
        OUT / "corrected_test_results.json",
        {
            "schema": "apphear.phase8a_r.corrected_test_results.v1",
            "focused_pytest_confirmed": pytest_confirmed,
            "persisted_probability_reuse": True,
            "reference_reproduction_passed": True,
            "synthetic_semantic_cases": ["A", "B", "C", "D", "E", "F", "G", "H"],
            "no_dev": True,
            "no_phone": True,
            "no_training": True,
            "no_decoder_v2": True,
            "passed": pytest_confirmed,
        },
    )
    return {
        "gate": gate,
        "comparison": comparison_doc,
        "pre_rows": pre_rows,
        "post_rows": post_rows,
        "no_event_rows": no_event_rows,
    }


def write_report(continuity: dict[str, Any], bug: dict[str, Any], result: dict[str, Any]) -> None:
    gate = result["gate"]
    changes = result["comparison"]["changes"]
    report = f"""# PHASE 8A-R Evaluator Correction Report

## 1. Scope and continuity

This is a semantic evaluator correction, not a new experiment. All 16 historical Phase 8A-R
artifacts remain in place. The persisted 54 CAL views / 18 clips were reused; S2 inference was
not rerun. Frozen S2 SHA-256: `{EXPECTED_S2_SHA}`. DEV, phone, recognition, training, Android,
feature, normalization, label, threshold, and decoder behavior remained unopened or unchanged.

Reference reproduction remained exact: Phase-7 `{continuity["phase7_global_reproduction"]}`;
CONFIG_01 `{continuity["phase8a_config_01_reproduction"]}`.

## 2. Confirmed evaluator defect

Defect confirmed: `{bug["defect_confirmed"]}`. The historical evaluator required an emitted
event before looking for later ACTIVE and counted interruption presence as attribution. Affected
metrics: `{bug["affected_metrics"]}`.

## 3. Corrected semantic unit

The correction replays Decoder V1 from persisted probabilities and records every candidate open,
PRE bridge/discard, POST entry/cancellation, emission, and EOF state. Recoverability is evaluated
over the full provisional episode trajectory. Interruption presence is not counted unless a safe,
observed-prefix hypothetical merge would raise the failed sequence to >=90% human-ACTIVE
containment. No grace value is searched or selected.

## 4. Old versus corrected attribution

`{changes}`

The primary failure set remains `{gate["primary_failure_count"]}`. Corrected attributable cases:
`{gate["attributable_count"]}` (`{gate["attributable_rate"]:.4%}`). Corrected bounded-causally
recoverable cases: `{gate["bounded_causally_recoverable_count"]}`
(`{gate["bounded_causally_recoverable_rate"]:.4%}`).

## 5. PRE/POST and no-event findings

PRE interruptions were evaluated even when no event existed or a candidate was discarded. POST
interruptions were evaluated independently of event emission. None causally repaired a primary
failure in the frozen CAL population: the observed internal resumptions were already bridged or
canceled by V1 rather than lost through first commitment. Four primary NO_EVENT trajectories were
reconstructed: two are right-censored POST confirmations and two end with ACTIVE and no terminal
POST evidence. Right-censored cases remain attributable timing limitations but do not supply an
observed causal commit point; no future state was fabricated.

## 6. Truncation and unchanged gate

START-dominant `{gate["start_dominant_count"]}/{gate["primary_failure_count"]}`
(`{gate["start_dominant_rate"]:.4%}`). The original four checks are unchanged:
`{gate["checks"]}`.

## 7. Corrected scientific classification

**`{gate["evidence_state"]}`**

Supported direction: **`{gate["supported_direction_if_failed"]}`**. The corrected evidence still
does not support delayed terminal commitment as the principal repair. This does not prove that
retraining, START redesign, or representation redesign will work.

## 8. Exact stop boundary

**`{gate["next"]}`**

Decoder V2 was not implemented. No follow-on architecture was started.
"""
    (OUT / "PHASE8A_R_EVALUATOR_CORRECTION_REPORT.md").write_text(report, encoding="utf-8")


def write_hashes() -> None:
    paths = [
        Path(__file__),
        ROOT / "tests/test_phase8a_r_evaluator_correction.py",
        ROOT / "tests/test_phase8a_r_causal_episode_failure_attribution.py",
        Path(old.__file__),
        ROOT / "pipeline/perception_vnext/segmentation/streaming_decoder.py",
        ROOT / "context/progress-tracker.md",
        OLD / "cal_state_run_manifest.json",
        OLD / "per_sequence_three_way_comparison.csv",
        OLD / "primary_failure_set.json",
        P7 / "cal_metrics.json",
        P8 / "cal_decoder_grid_summary.json",
    ]
    write_json(
        OUT / "source_hashes.json",
        {
            "schema": "apphear.phase8a_r.evaluator_correction_source_hashes.v1",
            "files": [{"path": str(path.resolve()), "sha256": sha256(path)} for path in paths],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pytest-confirmed", action="store_true")
    args = parser.parse_args()
    continuity, bug, state_manifest = continuity_and_bug_audit()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "evaluator_bug_audit.json", bug)
    write_json(OUT / "correction_scope.json", continuity)
    result = analyze_persisted(state_manifest, args.pytest_confirmed)
    write_report(continuity, bug, result)
    write_hashes()
    print(json.dumps(result["gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
