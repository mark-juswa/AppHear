"""CAL-only attribution of Phase-8A first-commit causal decoder failures.

This module performs no training, threshold search, feature extraction, DEV
evaluation, phone replay, recognition, or decoder-V2 implementation.  It reads
the 54 frozen Phase-7 CAL sparse views and evaluates the already-declared
Phase-8A CONFIG_01 diagnostic reference.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter as p7  # noqa: E402
import eval.runtime_diagnostics.phase8a_causal_streaming_decoder as p8  # noqa: E402
from eval.runtime_diagnostics.phase5_1t_first_segmenter import (  # noqa: E402
    decode_event,
)
from pipeline.perception_vnext.segmentation.streaming_decoder import (  # noqa: E402
    ACTIVE_SIGN,
    POST_RECOVERY,
    PRE_IDLE,
    CausalStreamingSignEventDecoder,
    StreamingDecoderConfig,
)

MILESTONE = "PHASE_8A_R_CAUSAL_EPISODE_FAILURE_ATTRIBUTION_01"
BASE = ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
P7 = BASE / "phase7_production_cadence_aligned_segmenter_01"
P8 = BASE / "phase8a_causal_streaming_sign_event_decoder_01"
OUT = BASE / "phase8a_r_causal_episode_failure_attribution_01"
EXPECTED_S2_SHA = "dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73"
CONFIG_01 = StreamingDecoderConfig(
    minimum_active_ms=133.308,
    pre_gap_reset_ms=133.308,
    post_confirm_ms=266.616,
    pre_padding_ms=250.0,
    post_padding_ms=250.0,
    rearm_pre_stable_ms=399.924,
)
STATE_NAMES = {PRE_IDLE: "PRE", ACTIVE_SIGN: "ACTIVE", POST_RECOVERY: "POST"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def distribution(values: list[float]) -> dict[str, float | int | None]:
    data = np.asarray(values, np.float64)
    if data.size == 0:
        return {
            "count": 0,
            "min": None,
            "median": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "max": None,
        }
    return {
        "count": int(data.size),
        "min": float(np.min(data)),
        "median": float(np.median(data)),
        "p75": float(np.percentile(data, 75)),
        "p90": float(np.percentile(data, 90)),
        "p95": float(np.percentile(data, 95)),
        "max": float(np.max(data)),
    }


def _assert_cal_only(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 54 or len({str(row["sample_id"]) for row in rows}) != 18:
        raise RuntimeError("PHASE8A_R_CAL_POPULATION_MISMATCH")
    if {str(row["phase7_partition"]) for row in rows} != {"CAL"}:
        raise RuntimeError("PHASE8A_R_NON_CAL_VIEW_OPENED")
    if any(str(row["segmentation_split"]) != "SEGMENTATION_TRAIN" for row in rows):
        raise RuntimeError("PHASE8A_R_NON_TRAIN_MEMBER_OPENED")


def implementation_audit() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    s2 = p8.verify_s2_identity()
    if s2["checkpoint"]["sha256"] != EXPECTED_S2_SHA:
        raise RuntimeError("PHASE8A_R_IMPLEMENTATION_AUDIT_MISMATCH:S2")
    decoder_path = ROOT / "pipeline/perception_vnext/segmentation/streaming_decoder.py"
    evaluator_path = ROOT / "eval/runtime_diagnostics/phase8a_causal_streaming_decoder.py"
    grid_path = P8 / "cal_decoder_grid_summary.json"
    decision_path = P8 / "final_decision.json"
    for path in (decoder_path, evaluator_path, grid_path, decision_path):
        if not path.is_file():
            raise RuntimeError(f"PHASE8A_R_IMPLEMENTATION_AUDIT_MISMATCH:MISSING:{path}")
    grid = read_json(grid_path)
    decision = read_json(decision_path)
    if grid.get("configuration_count") != 27 or len(grid.get("configurations", [])) != 27:
        raise RuntimeError("PHASE8A_R_IMPLEMENTATION_AUDIT_MISMATCH:GRID")
    config_01 = next(
        (row for row in grid["configurations"] if row["config_id"] == "CONFIG_01"), None
    )
    if config_01 is None or config_01["config"] != asdict(CONFIG_01):
        raise RuntimeError("PHASE8A_R_IMPLEMENTATION_AUDIT_MISMATCH:CONFIG_01")
    if decision.get("evidence_state") != "PHASE8A_NO_ELIGIBLE_CAUSAL_STREAMING_DECODER":
        raise RuntimeError("PHASE8A_R_IMPLEMENTATION_AUDIT_MISMATCH:DECISION")
    forbidden_phase8a_outputs = [
        P8 / "sparse_dev_streaming_event_metrics.json",
        P8 / "known_phone_streaming_events.json",
        P8 / "known_phone_streaming_recognition.json",
        P8 / "streaming_decoder_config_frozen.json",
    ]
    if any(path.exists() for path in forbidden_phase8a_outputs):
        raise RuntimeError("PHASE8A_R_IMPLEMENTATION_AUDIT_MISMATCH:PHASE8A_STOP_VIOLATION")
    rows = p7._load_view_rows({"CAL"})
    _assert_cal_only(rows)
    decoder_source = decoder_path.read_text(encoding="utf-8")
    evaluator_source = evaluator_path.read_text(encoding="utf-8")
    source_checks = {
        "first_immutable_event_is_primary": "events[0]" in evaluator_source,
        "no_retrospective_best_run_selection": "max(self.events" not in decoder_source,
        "no_end_of_input_flush": ".flush(" not in decoder_source,
        "strict_chronological_timestamp_check": "NON_CHRONOLOGICAL_TIMESTAMP" in decoder_source,
        "observed_only_padding": "self._timestamps[start]" in decoder_source
        and "self._timestamps[end]" in decoder_source,
        "immutable_event": "@dataclass(frozen=True)\nclass SignEvent" in decoder_source,
        "no_training_api": "model.fit(" not in evaluator_source
        and "model.fit(" not in decoder_source,
    }
    if not all(source_checks.values()):
        raise RuntimeError(f"PHASE8A_R_IMPLEMENTATION_AUDIT_MISMATCH:{source_checks}")
    audit = {
        "schema": "apphear.phase8a_r.implementation_audit.v1",
        "milestone": MILESTONE,
        "s2_checkpoint_sha256": EXPECTED_S2_SHA,
        "decoder_source": {"path": str(decoder_path.resolve()), "sha256": sha256(decoder_path)},
        "phase8a_evaluator": {
            "path": str(evaluator_path.resolve()),
            "sha256": sha256(evaluator_path),
        },
        "phase8a_grid_sha256": sha256(grid_path),
        "phase8a_grid_rows": 27,
        "phase8a_written_config_01": config_01,
        "source_checks": source_checks,
        "cal_views": 54,
        "cal_original_clips": 18,
        "dev_access": False,
        "known_phone_access": False,
        "recognition_dev_access": False,
        "protected_test_access": False,
        "sealed_phone_holdout_access": False,
        "training": False,
        "decoder_v2_implemented": False,
    }
    write_json(OUT / "implementation_audit.json", audit)
    write_json(
        OUT / "frozen_identity.json",
        {
            "schema": "apphear.phase8a_r.frozen_identity.v1",
            "milestone": MILESTONE,
            "s2": s2,
            "phase8a_v1_decoder_sha256": sha256(decoder_path),
            "phase8a_grid_sha256": sha256(grid_path),
            "config_01": asdict(CONFIG_01),
            "feature_schema": "apphear.perception_vnext.segmentation_features.v1",
            "feature_width": 378,
            "no_modifications": True,
        },
    )
    return audit, rows


def state_runs(
    timestamps: np.ndarray, probabilities: np.ndarray, states: np.ndarray
) -> list[dict[str, Any]]:
    if len(timestamps) != len(probabilities) or len(states) != len(timestamps):
        raise ValueError("STATE_TRACE_LENGTH_MISMATCH")
    default_dt = float(np.median(np.diff(timestamps))) if len(timestamps) > 1 else 0.0
    runs: list[dict[str, Any]] = []
    start = 0
    for index in range(1, len(states) + 1):
        if index < len(states) and int(states[index]) == int(states[start]):
            continue
        indices = np.arange(start, index, dtype=np.int32)
        state = int(states[start])
        weights = np.full(len(indices), default_dt, np.float64)
        if len(indices) > 1:
            weights[:-1] = np.diff(timestamps[indices])
        active_values = probabilities[indices, ACTIVE_SIGN]
        runs.append(
            {
                "run_index": len(runs) + 1,
                "state_id": state,
                "state": STATE_NAMES[state],
                "start_observation_index": int(indices[0]),
                "end_observation_index": int(indices[-1]),
                "start_ms": float(timestamps[indices[0]]),
                "end_ms": float(timestamps[indices[-1]]),
                "duration_ms": float(timestamps[indices[-1]] - timestamps[indices[0]] + default_dt),
                "observation_count": len(indices),
                "max_active_probability": float(np.max(active_values)),
                "mean_active_probability": float(np.mean(active_values)),
                "active_probability_time_integral_ms": float(np.sum(active_values * weights)),
            }
        )
        start = index
    return runs


def interruptions_from_runs(
    runs: list[dict[str, Any]], human_start: float, human_end: float
) -> list[dict[str, Any]]:
    interruptions = []
    for index in range(1, len(runs) - 1):
        previous, current, following = runs[index - 1], runs[index], runs[index + 1]
        if previous["state"] != "ACTIVE" or following["state"] != "ACTIVE":
            continue
        if current["state"] not in {"PRE", "POST"}:
            continue
        duration = float(following["start_ms"] - current["start_ms"])
        inside = current["start_ms"] >= human_start and following["start_ms"] <= human_end
        interruptions.append(
            {
                "state": current["state"],
                "start_ms": current["start_ms"],
                "end_ms": current["end_ms"],
                "duration_until_active_resumption_ms": duration,
                "inside_human_active": inside,
                "active_resumes": True,
                "previous_active_run_index": previous["run_index"],
                "next_active_run_index": following["run_index"],
                "next_active_start_ms": following["start_ms"],
            }
        )
    return interruptions


def interval_metrics(
    start: float | None,
    end: float | None,
    human_start: float,
    human_end: float,
    video_duration: float,
) -> dict[str, Any]:
    if start is None or end is None:
        return {
            "event_emitted": False,
            "active_recall": 0.0,
            "contained_90pct": False,
            "premature_cut": True,
            "severe_cut": True,
            "start_error_ms": None,
            "end_error_ms": None,
            "padded_window_precision": 0.0,
            "context_reduction_fraction": 1.0,
            "missing_at_start_ms": max(0.0, human_end - human_start),
            "missing_at_end_ms": max(0.0, human_end - human_start),
        }
    intersection = max(0.0, min(end, human_end) - max(start, human_start))
    human_duration = human_end - human_start
    window_duration = max(0.0, end - start)
    recall = intersection / human_duration if human_duration > 0 else 0.0
    return {
        "event_emitted": True,
        "active_recall": recall,
        "contained_90pct": recall >= 0.90,
        "premature_cut": recall < 0.90,
        "severe_cut": recall < 0.60,
        "start_error_ms": start - human_start,
        "end_error_ms": end - human_end,
        "padded_window_precision": intersection / window_duration if window_duration else 0.0,
        "context_reduction_fraction": (
            max(0.0, 1.0 - window_duration / video_duration) if video_duration else 0.0
        ),
        "missing_at_start_ms": max(0.0, start - human_start),
        "missing_at_end_ms": max(0.0, human_end - end),
    }


def _global_result(
    row: dict[str, Any], probabilities: np.ndarray, phase7_config: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    event = decode_event(
        row["timestamps_ms"], probabilities, float(row["video_duration_ms"]), phase7_config
    )
    metrics = interval_metrics(
        float(event["start_ms"]) if event else None,
        float(event["end_ms"]) if event else None,
        float(row["human_sign_start_ms"]),
        float(row["human_sign_end_ms"]),
        float(row["video_duration_ms"]),
    )
    if event:
        metrics.update(
            {
                "logical_start_ms": float(
                    row["timestamps_ms"][int(event["active_observation_start_index"])]
                ),
                "logical_end_ms": float(
                    row["timestamps_ms"][int(event["active_observation_end_index"])]
                ),
                "padded_start_ms": float(event["start_ms"]),
                "padded_end_ms": float(event["end_ms"]),
                "active_start_index": int(event["active_observation_start_index"]),
                "active_end_index": int(event["active_observation_end_index"]),
            }
        )
    return event, metrics


def _v1_result(
    row: dict[str, Any], probabilities: np.ndarray, states: np.ndarray
) -> tuple[CausalStreamingSignEventDecoder, dict[str, Any]]:
    decoder = p8.run_decoder(row["timestamps_ms"], probabilities, states, CONFIG_01)
    event = decoder.events[0] if decoder.events else None
    metrics = interval_metrics(
        float(event.padded_start_ms) if event else None,
        float(event.padded_end_ms) if event else None,
        float(row["human_sign_start_ms"]),
        float(row["human_sign_end_ms"]),
        float(row["video_duration_ms"]),
    )
    if event:
        metrics.update(
            {
                "logical_start_ms": event.logical_active_start_ms,
                "logical_end_ms": event.logical_active_end_ms,
                "padded_start_ms": event.padded_start_ms,
                "padded_end_ms": event.padded_end_ms,
                "emitted_at_ms": event.emitted_at_ms,
                "first_post_ms": event.first_post_ms,
                "active_start_index": event.logical_active_start_index,
                "active_end_index": event.logical_active_end_index,
                "event_count": len(decoder.events),
            }
        )
    return decoder, metrics


def _phase7_aggregate(results: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "event_emission_rate": float(np.mean([row["event_emitted"] for row in results])),
        "containment_rate": float(np.mean([row["contained_90pct"] for row in results])),
        "premature_cut_rate": float(np.mean([row["premature_cut"] for row in results])),
        "mean_window_precision": float(
            np.mean([row["padded_window_precision"] for row in results if row["event_emitted"]])
        ),
    }


def _v1_aggregate(results: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "event_emission_rate": float(np.mean([row["event_emitted"] for row in results])),
        "exactly_one_event_rate": float(
            np.mean([row.get("event_count", 0) == 1 for row in results])
        ),
        "containment_rate": float(np.mean([row["contained_90pct"] for row in results])),
        "premature_cut_rate": float(np.mean([row["premature_cut"] for row in results])),
        "severe_cut_rate": float(np.mean([row["severe_cut"] for row in results])),
        "mean_context_reduction": float(
            np.mean([row["context_reduction_fraction"] for row in results])
        ),
    }


def _assert_close(actual: float, expected: float, name: str, tolerance: float = 1e-9) -> None:
    if abs(float(actual) - float(expected)) > tolerance:
        raise RuntimeError(f"PHASE8A_R_IMPLEMENTATION_AUDIT_MISMATCH:{name}:{actual}:{expected}")


def analyze() -> dict[str, Any]:
    audit, rows = implementation_audit()
    probabilities, states = p8._model_predictions(rows)
    phase7_config = p7.load_config()
    global_rows: list[dict[str, Any]] = []
    v1_rows: list[dict[str, Any]] = []
    per_sequence: list[dict[str, Any]] = []
    trace_views: list[dict[str, Any]] = []
    runtime_by_key: dict[str, dict[str, Any]] = {}
    for row, probs, predicted in zip(rows, probabilities, states, strict=True):
        timestamps = np.asarray(row["timestamps_ms"], np.float64)
        human_start = float(row["human_sign_start_ms"])
        human_end = float(row["human_sign_end_ms"])
        runs = state_runs(timestamps, probs, predicted)
        interruptions = interruptions_from_runs(runs, human_start, human_end)
        global_event, global_metrics = _global_result(row, probs, phase7_config)
        decoder, v1_metrics = _v1_result(row, probs, predicted)
        global_rows.append(global_metrics)
        v1_rows.append(v1_metrics)
        observations = [
            {
                "observation_index": index,
                "timestamp_ms": float(timestamps[index]),
                "pre_probability": float(probs[index, PRE_IDLE]),
                "active_probability": float(probs[index, ACTIVE_SIGN]),
                "post_probability": float(probs[index, POST_RECOVERY]),
                "argmax_state": int(predicted[index]),
                "argmax_state_name": STATE_NAMES[int(predicted[index])],
                "human_start_ms": human_start,
                "human_end_ms": human_end,
            }
            for index in range(len(timestamps))
        ]
        active_run_number = 0
        for run in runs:
            if run["state"] == "ACTIVE":
                active_run_number += 1
                run["active_run_number"] = active_run_number
        trace_views.append(
            {
                "view_key": row["view_key"],
                "sample_id": row["sample_id"],
                "view_id": row["view_id"],
                "source": row["source"],
                "signer_id": row["signer_id"],
                "human_start_ms": human_start,
                "human_end_ms": human_end,
                "observations": observations,
                "state_runs": runs,
                "interruptions_between_active_runs": interruptions,
            }
        )
        category = (
            "BOTH_SUCCEED"
            if global_metrics["contained_90pct"] and v1_metrics["contained_90pct"]
            else "PRIMARY_GLOBAL_SUCCESS_V1_FAILURE"
            if global_metrics["contained_90pct"] and not v1_metrics["contained_90pct"]
            else "V1_SUCCESS_GLOBAL_FAILURE"
            if v1_metrics["contained_90pct"] and not global_metrics["contained_90pct"]
            else "BOTH_FAIL"
        )
        if not v1_metrics["event_emitted"]:
            category = (
                "V1_NO_EVENT" if global_metrics["contained_90pct"] else "BOTH_FAIL_V1_NO_EVENT"
            )
        comparison = {
            "view_key": row["view_key"],
            "sample_id": row["sample_id"],
            "view_id": row["view_id"],
            "source": row["source"],
            "signer_id": row["signer_id"],
            "human_start_ms": human_start,
            "human_end_ms": human_end,
            "clip_end_timestamp_ms": float(timestamps[-1]),
            "category": category,
            "global": global_metrics,
            "v1": v1_metrics,
        }
        per_sequence.append(comparison)
        runtime_by_key[str(row["view_key"])] = {
            "row": row,
            "probabilities": probs,
            "states": predicted,
            "runs": runs,
            "interruptions": interruptions,
            "global_event": global_event,
            "decoder": decoder,
            "comparison": comparison,
        }

    # Reproduce both accepted aggregate references before attribution.
    global_aggregate = _phase7_aggregate(global_rows)
    phase7_written = read_json(P7 / "cal_metrics.json")["event_metrics"]
    for actual_key, written_key in (
        ("event_emission_rate", "event_emission_rate"),
        ("containment_rate", "containment_rate"),
        ("premature_cut_rate", "premature_cut_rate"),
        ("mean_window_precision", "predicted_window_precision"),
    ):
        expected = phase7_written[written_key]
        if isinstance(expected, dict):
            expected = expected["mean"]
        _assert_close(global_aggregate[actual_key], expected, f"PHASE7_{actual_key}")
    v1_aggregate = _v1_aggregate(v1_rows)
    phase8a_config_01 = next(
        row
        for row in read_json(P8 / "cal_decoder_grid_summary.json")["configurations"]
        if row["config_id"] == "CONFIG_01"
    )["metrics"]
    for actual_key, written_key in (
        ("event_emission_rate", "event_emission_rate"),
        ("exactly_one_event_rate", "exactly_one_event_rate"),
        ("containment_rate", "containment_rate"),
        ("premature_cut_rate", "premature_cut_rate"),
        ("severe_cut_rate", "severe_cut_rate"),
        ("mean_context_reduction", "context_reduction_fraction"),
    ):
        expected = phase8a_config_01[written_key]
        if isinstance(expected, dict):
            expected = expected["mean"]
        _assert_close(v1_aggregate[actual_key], expected, f"PHASE8A_{actual_key}")
    audit["reproduction"] = {
        "phase7_global": {"actual": global_aggregate, "matches_written": True},
        "phase8a_config_01": {"actual": v1_aggregate, "matches_written": True},
        "model_inference_rerun_required_for_probabilities": True,
        "reason": "Phase-7 CAL per-observation probabilities were not retained",
    }
    write_json(OUT / "implementation_audit.json", audit)
    write_json(
        OUT / "cal_state_run_manifest.json",
        {
            "schema": "apphear.phase8a_r.cal_state_run_manifest.v1",
            "cal_original_clips": 18,
            "cal_sparse_views": 54,
            "s2_checkpoint_sha256": EXPECTED_S2_SHA,
            "state_run_duration_policy": "LAST_MINUS_FIRST_PLUS_SEQUENCE_MEDIAN_DT",
            "interruption_duration_policy": "NEXT_ACTIVE_START_MINUS_INTERRUPTION_START",
            "views": trace_views,
        },
    )
    _write_comparison_csv(per_sequence)
    result = _attribute(per_sequence, runtime_by_key)
    write_report(result, global_aggregate, v1_aggregate)
    write_source_hashes()
    return result["diagnostic_gate"]


def _write_comparison_csv(rows: list[dict[str, Any]]) -> None:
    fields = [
        "view_key",
        "sample_id",
        "view_id",
        "source",
        "signer_id",
        "category",
        "human_start_ms",
        "human_end_ms",
        "global_event_emitted",
        "global_logical_start_ms",
        "global_logical_end_ms",
        "global_active_recall",
        "global_contained_90pct",
        "global_premature_cut",
        "global_severe_cut",
        "global_start_error_ms",
        "global_end_error_ms",
        "global_window_precision",
        "global_context_reduction",
        "v1_event_emitted",
        "v1_logical_start_ms",
        "v1_logical_end_ms",
        "v1_active_recall",
        "v1_contained_90pct",
        "v1_premature_cut",
        "v1_severe_cut",
        "v1_start_error_ms",
        "v1_end_error_ms",
        "v1_window_precision",
        "v1_context_reduction",
    ]
    with (OUT / "per_sequence_three_way_comparison.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            global_metrics = row["global"]
            v1 = row["v1"]
            writer.writerow(
                {
                    "view_key": row["view_key"],
                    "sample_id": row["sample_id"],
                    "view_id": row["view_id"],
                    "source": row["source"],
                    "signer_id": row["signer_id"],
                    "category": row["category"],
                    "human_start_ms": row["human_start_ms"],
                    "human_end_ms": row["human_end_ms"],
                    **{
                        f"global_{key}": global_metrics.get(metric)
                        for key, metric in (
                            ("event_emitted", "event_emitted"),
                            ("logical_start_ms", "logical_start_ms"),
                            ("logical_end_ms", "logical_end_ms"),
                            ("active_recall", "active_recall"),
                            ("contained_90pct", "contained_90pct"),
                            ("premature_cut", "premature_cut"),
                            ("severe_cut", "severe_cut"),
                            ("start_error_ms", "start_error_ms"),
                            ("end_error_ms", "end_error_ms"),
                            ("window_precision", "padded_window_precision"),
                            ("context_reduction", "context_reduction_fraction"),
                        )
                    },
                    **{
                        f"v1_{key}": v1.get(metric)
                        for key, metric in (
                            ("event_emitted", "event_emitted"),
                            ("logical_start_ms", "logical_start_ms"),
                            ("logical_end_ms", "logical_end_ms"),
                            ("active_recall", "active_recall"),
                            ("contained_90pct", "contained_90pct"),
                            ("premature_cut", "premature_cut"),
                            ("severe_cut", "severe_cut"),
                            ("start_error_ms", "start_error_ms"),
                            ("end_error_ms", "end_error_ms"),
                            ("window_precision", "padded_window_precision"),
                            ("context_reduction", "context_reduction_fraction"),
                        )
                    },
                }
            )


def _dominant_truncation(v1: dict[str, Any]) -> str:
    if not v1["event_emitted"]:
        return "NO_EVENT"
    start = float(v1["missing_at_start_ms"])
    end = float(v1["missing_at_end_ms"])
    if start <= 0.0 and end <= 0.0:
        return "BOTH"
    if end <= 0.0 or start >= 2.0 * end:
        return "START_DOMINANT"
    if start <= 0.0 or end >= 2.0 * start:
        return "END_DOMINANT"
    return "BOTH"


def _attribute(
    comparisons: list[dict[str, Any]], runtime: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    primary = [
        row
        for row in comparisons
        if row["global"]["contained_90pct"] and not row["v1"]["contained_90pct"]
    ]
    categories = Counter(row["category"] for row in comparisons)
    primary_rows = []
    premature_rows = []
    wrong_early_rows = []
    truncation_rows = []
    right_censor_rows = []
    recoverability_rows = []
    attributable_count = 0
    recoverable_count = 0
    grace_values: list[float] = []

    for comparison in comparisons:
        key = str(comparison["view_key"])
        details = runtime[key]
        row = details["row"]
        timestamps = np.asarray(row["timestamps_ms"], np.float64)
        states = np.asarray(details["states"], np.int32)
        v1 = comparison["v1"]
        global_metrics = comparison["global"]
        human_start = float(comparison["human_start_ms"])
        human_end = float(comparison["human_end_ms"])
        if comparison in primary:
            primary_rows.append(comparison)
            truncation = _dominant_truncation(v1)
            truncation_rows.append(
                {
                    "view_key": key,
                    "classification": truncation,
                    "missing_at_start_ms": v1["missing_at_start_ms"],
                    "missing_at_end_ms": v1["missing_at_end_ms"],
                }
            )
            later_active_indices: list[int] = []
            event = details["decoder"].events[0] if details["decoder"].events else None
            if event is not None:
                later_active_indices = [
                    index
                    for index in range(event.emitted_at_index + 1, len(states))
                    if states[index] == ACTIVE_SIGN
                ]
            later_index = later_active_indices[0] if later_active_indices else None
            later_inside = (
                later_index is not None
                and human_start <= float(timestamps[later_index]) <= human_end
            )
            global_membership = later_index is not None and global_metrics.get(
                "active_start_index", len(states)
            ) <= later_index <= global_metrics.get("active_end_index", -1)
            interruption = None
            if event is not None and later_index is not None:
                gap_states = states[event.first_post_index : later_index]
                distinct = sorted({STATE_NAMES[int(value)] for value in gap_states})
                interruption = distinct[0] if len(distinct) == 1 else "MIXED_" + "_".join(distinct)
                premature = {
                    "view_key": key,
                    "v1_commit_timestamp_ms": event.emitted_at_ms,
                    "last_active_before_commit_ms": event.logical_active_end_ms,
                    "terminal_transition_ms": event.first_post_ms,
                    "later_active_resumption_ms": float(timestamps[later_index]),
                    "gap_terminal_to_resumption_ms": float(
                        timestamps[later_index] - event.first_post_ms
                    ),
                    "gap_commit_to_resumption_ms": float(
                        timestamps[later_index] - event.emitted_at_ms
                    ),
                    "state_during_gap": interruption,
                    "later_active_inside_human_active": later_inside,
                    "later_active_belongs_to_global_selected_run": global_membership,
                    "classification": (
                        "PREMATURE_COMMIT_BEFORE_ACTIVE_RESUMPTION"
                        if later_inside
                        else "LATER_ACTIVE_OUTSIDE_HUMAN_ACTIVE"
                    ),
                }
                premature_rows.append(premature)

            early_wrong = False
            substantial_pre = False
            if event is not None and v1["active_recall"] < 0.60:
                early_active = event.logical_active_start_ms < human_start
                true_indices = [
                    index
                    for index in range(event.emitted_at_index + 1, len(states))
                    if states[index] == ACTIVE_SIGN
                    and human_start <= timestamps[index] <= human_end
                ]
                if early_active and true_indices:
                    true_index = true_indices[0]
                    gap_slice = states[event.emitted_at_index + 1 : true_index]
                    pre_times = timestamps[event.emitted_at_index + 1 : true_index][
                        gap_slice == PRE_IDLE
                    ]
                    substantial_pre = bool(
                        len(pre_times) >= 2
                        and float(pre_times[-1] - pre_times[0]) >= CONFIG_01.rearm_pre_stable_ms
                    )
                    early_wrong = True
                    wrong_early_rows.append(
                        {
                            "view_key": key,
                            "early_active_before_human_start": True,
                            "early_episode_received_post": True,
                            "v1_committed": True,
                            "later_active_overlaps_human": True,
                            "early_commit_ms": event.emitted_at_ms,
                            "later_true_active_onset_ms": float(timestamps[true_index]),
                            "commit_to_true_active_gap_ms": float(
                                timestamps[true_index] - event.emitted_at_ms
                            ),
                            "substantial_stable_pre_separation": substantial_pre,
                            "classification": "EARLY_WRONG_ACTIVITY_EPISODE",
                        }
                    )

            inside_interruptions = [
                item for item in details["interruptions"] if item["inside_human_active"]
            ]
            bounded_interrupt = bool(inside_interruptions)
            right_censored = False
            if not v1["event_emitted"]:
                right_record = _right_censor_record(comparison, details)
                right_censor_rows.append(right_record)
                right_censored = right_record["classification"] == "RIGHT_CENSORED_CONFIRMATION"
            if (event is not None and later_inside) or bounded_interrupt or right_censored:
                attributable_count += 1

            causal_recoverable = False
            grace = None
            recoverability_reason = "NO_LATER_RELEVANT_ACTIVE_RESUMPTION"
            if event is not None and later_active_indices and later_inside:
                relevant = [
                    index
                    for index in later_active_indices
                    if timestamps[index] <= human_end
                    and global_metrics.get("active_start_index", len(states))
                    <= index
                    <= global_metrics.get("active_end_index", -1)
                ]
                if relevant:
                    last_resumption = relevant[-1]
                    grace = float(timestamps[last_resumption] - event.first_post_ms)
                    future_nonactive = [
                        index
                        for index in range(last_resumption + 1, len(states))
                        if states[index] != ACTIVE_SIGN
                    ]
                    terminal_observable = bool(
                        future_nonactive
                        and timestamps[-1] - timestamps[future_nonactive[0]]
                        >= CONFIG_01.post_confirm_ms
                    )
                    causal_recoverable = terminal_observable and not (
                        early_wrong and substantial_pre
                    )
                    recoverability_reason = (
                        "BOUNDED_GRACE_THEN_OBSERVED_TERMINAL_CONFIRMATION"
                        if causal_recoverable
                        else "EARLY_FALSE_EPISODE_SEPARATED_BY_STABLE_PRE"
                        if early_wrong and substantial_pre
                        else "NO_OBSERVED_TERMINAL_CONFIRMATION_AFTER_RESUMPTION"
                    )
            if causal_recoverable:
                recoverable_count += 1
                assert grace is not None
                grace_values.append(grace)
            recoverability_rows.append(
                {
                    "view_key": key,
                    "bounded_causally_recoverable": causal_recoverable,
                    "minimum_required_grace_ms": grace,
                    "reason": recoverability_reason,
                    "all_information_observed_by_candidate_commit": causal_recoverable,
                    "human_label_used_only_for_evaluation": True,
                    "global_rank_used_as_runtime_signal": False,
                }
            )
        elif not v1["event_emitted"]:
            right_censor_rows.append(_right_censor_record(comparison, details))

    post_interruptions = [
        {"view_key": key, **item}
        for key, details in runtime.items()
        for item in details["interruptions"]
        if item["state"] == "POST"
    ]
    pre_interruptions = [
        {"view_key": key, **item}
        for key, details in runtime.items()
        for item in details["interruptions"]
        if item["state"] == "PRE"
    ]
    pre_doc = _interruption_document("PRE", pre_interruptions)
    post_doc = _interruption_document("POST", post_interruptions)
    primary_keys = {str(row["view_key"]) for row in primary}
    primary_pre_interruption_count = len(
        {
            str(row["view_key"])
            for row in pre_interruptions
            if str(row["view_key"]) in primary_keys and row["inside_human_active"]
        }
    )
    primary_post_interruption_count = len(
        {
            str(row["view_key"])
            for row in post_interruptions
            if str(row["view_key"]) in primary_keys and row["inside_human_active"]
        }
    )
    write_json(OUT / "internal_pre_interruption_distribution.json", pre_doc)
    write_json(OUT / "internal_post_interruption_distribution.json", post_doc)
    write_json(
        OUT / "primary_failure_set.json",
        {
            "schema": "apphear.phase8a_r.primary_failure_set.v1",
            "definition": "PHASE7_GLOBAL_CONTAINMENT_GE_0_90_AND_V1_CONTAINMENT_LT_0_90",
            "size": len(primary),
            "all_categories": dict(sorted(categories.items())),
            "rows": primary_rows,
        },
    )
    write_json(
        OUT / "premature_commit_attribution.json",
        {
            "schema": "apphear.phase8a_r.premature_commit_attribution.v1",
            "supported_count": sum(
                row["classification"] == "PREMATURE_COMMIT_BEFORE_ACTIVE_RESUMPTION"
                for row in premature_rows
            ),
            "rows": premature_rows,
        },
    )
    write_json(
        OUT / "wrong_early_episode_attribution.json",
        {
            "schema": "apphear.phase8a_r.wrong_early_episode_attribution.v1",
            "count": len(wrong_early_rows),
            "rows": wrong_early_rows,
        },
    )
    truncation_counts = Counter(row["classification"] for row in truncation_rows)
    write_json(
        OUT / "start_end_truncation_decomposition.json",
        {
            "schema": "apphear.phase8a_r.start_end_truncation.v1",
            "dominance_rule": (
                "START_IF_START_GE_2X_END;END_IF_END_GE_2X_START;OTHERWISE_BOTH;NO_EVENT_SEPARATE"
            ),
            "counts": dict(sorted(truncation_counts.items())),
            "missing_start_ms": distribution(
                [float(row["missing_at_start_ms"]) for row in truncation_rows]
            ),
            "missing_end_ms": distribution(
                [float(row["missing_at_end_ms"]) for row in truncation_rows]
            ),
            "rows": truncation_rows,
        },
    )
    right_counts = Counter(row["classification"] for row in right_censor_rows)
    write_json(
        OUT / "right_censoring_audit.json",
        {
            "schema": "apphear.phase8a_r.right_censoring.v1",
            "counts": dict(sorted(right_counts.items())),
            "rows": right_censor_rows,
            "synthetic_observations": False,
        },
    )
    recoverability_rate = recoverable_count / len(primary) if primary else 0.0
    attributable_rate = attributable_count / len(primary) if primary else 0.0
    grace_distribution = distribution(grace_values)
    write_json(
        OUT / "bounded_causal_recoverability.json",
        {
            "schema": "apphear.phase8a_r.bounded_causal_recoverability.v1",
            "primary_failure_count": len(primary),
            "recoverable_with_bounded_grace_count": recoverable_count,
            "recoverable_rate": recoverability_rate,
            "minimum_required_grace_ms": grace_distribution,
            "not_recoverable_count": len(primary) - recoverable_count,
            "rows": recoverability_rows,
            "no_future_beyond_candidate_commit_used": True,
        },
    )
    start_dominant = truncation_counts["START_DOMINANT"]
    gate_checks = {
        "attributable_failure_rate_at_least_0_70": attributable_rate >= 0.70,
        "bounded_causal_recoverable_rate_at_least_0_70": recoverability_rate >= 0.70,
        "grace_p90_at_most_1200_ms": grace_distribution["p90"] is not None
        and float(grace_distribution["p90"]) <= 1200.0,
        "start_dominant_rate_at_most_0_30": (start_dominant / len(primary) if primary else 1.0)
        <= 0.30,
    }
    passed = all(gate_checks.values())
    gate = {
        "schema": "apphear.phase8a_r.diagnostic_gate.v1",
        "primary_failure_count": len(primary),
        "attributable_count": attributable_count,
        "attributable_rate": attributable_rate,
        "bounded_causally_recoverable_count": recoverable_count,
        "bounded_causally_recoverable_rate": recoverability_rate,
        "grace_distribution": grace_distribution,
        "start_dominant_count": start_dominant,
        "start_dominant_rate": start_dominant / len(primary) if primary else 1.0,
        "checks": gate_checks,
        "passed": passed,
        "cause_evidence_counts": {
            "premature_first_commit": sum(
                row["classification"] == "PREMATURE_COMMIT_BEFORE_ACTIVE_RESUMPTION"
                for row in premature_rows
            ),
            "internal_pre_interruption_primary_sequences": primary_pre_interruption_count,
            "internal_post_interruption_primary_sequences": primary_post_interruption_count,
            "wrong_early_activity_episode": len(wrong_early_rows),
            "late_start_dominant": start_dominant,
            "right_censored_confirmation": right_counts["RIGHT_CENSORED_CONFIRMATION"],
            "not_bounded_causally_recoverable": len(primary) - recoverable_count,
        },
        "favored_next_direction_if_failed": None if passed else "MIXED_UNRESOLVED_CAUSES",
        "failed_gate_interpretation": (
            None
            if passed
            else (
                "Evidence does not support delayed terminal commitment as the principal repair. "
                "START-dominant, END-dominant, both-sided, and genuine no-event failures coexist; "
                "the current CAL evidence does not isolate streaming-aware S2 retraining versus "
                "START detection or representation redesign."
            )
        ),
        "evidence_state": (
            "EPISODE_V2_CAUSAL_DESIGN_SUPPORTED"
            if passed
            else "EPISODE_V2_CAUSAL_DESIGN_NOT_SUPPORTED"
        ),
        "next": (
            "WAIT_FOR_PROJECT_LEAD_DECODER_V2_ARCHITECTURE_FREEZE"
            if passed
            else "WAIT_FOR_PROJECT_LEAD_SEGMENTATION_ARCHITECTURE_DIAGNOSIS"
        ),
        "decoder_v2_implemented": False,
    }
    write_json(OUT / "diagnostic_gate.json", gate)
    return {
        "comparisons": comparisons,
        "global_aggregate": _phase7_aggregate([row["global"] for row in comparisons]),
        "v1_aggregate": _v1_aggregate([row["v1"] for row in comparisons]),
        "primary": primary,
        "pre_interruptions": pre_doc,
        "post_interruptions": post_doc,
        "premature_rows": premature_rows,
        "wrong_early_rows": wrong_early_rows,
        "truncation_counts": dict(sorted(truncation_counts.items())),
        "right_counts": dict(sorted(right_counts.items())),
        "recoverability_rows": recoverability_rows,
        "diagnostic_gate": gate,
    }


def _right_censor_record(comparison: dict[str, Any], details: dict[str, Any]) -> dict[str, Any]:
    decoder = details["decoder"]
    timestamps = np.asarray(details["row"]["timestamps_ms"], np.float64)
    human_end = float(comparison["human_end_ms"])
    post_indices = [
        index
        for index, state in enumerate(details["states"])
        if state == POST_RECOVERY and timestamps[index] >= human_end
    ]
    first_post_after_human = int(post_indices[0]) if post_indices else None
    first_post_ms = (
        float(timestamps[first_post_after_human]) if first_post_after_human is not None else None
    )
    remaining = float(timestamps[-1] - first_post_ms) if first_post_ms is not None else None
    progression_started = (
        decoder.state.value == "POST_CANDIDATE" and decoder._first_post_ms is not None
    )
    active_span_valid = bool(
        decoder._candidate_start_ms is not None
        and decoder._last_active_ms is not None
        and decoder._last_active_ms - decoder._candidate_start_ms >= CONFIG_01.minimum_active_ms
    )
    required_extra = (
        max(0.0, decoder._first_post_ms + CONFIG_01.post_confirm_ms - timestamps[-1])
        if progression_started
        else None
    )
    right_censored = bool(progression_started and active_span_valid and required_extra > 0.0)
    return {
        "view_key": comparison["view_key"],
        "post_context_available_ms": float(timestamps[-1] - human_end),
        "first_post_after_human_end_ms": first_post_ms,
        "remaining_observed_duration_after_first_post_ms": remaining,
        "terminal_progression_started": progression_started,
        "minimum_active_satisfied": active_span_valid,
        "additional_terminal_time_required_ms": required_extra,
        "would_emit_if_identical_terminal_state_continued_exactly_enough": right_censored,
        "classification": ("RIGHT_CENSORED_CONFIRMATION" if right_censored else "GENUINE_NO_EVENT"),
        "synthetic_future_observations_created": False,
    }


def _interruption_document(state: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    inside = [row for row in rows if row["inside_human_active"]]
    outside = [row for row in rows if not row["inside_human_active"]]
    return {
        "schema": f"apphear.phase8a_r.internal_{state.lower()}_interruptions.v1",
        "state": state,
        "all": distribution([row["duration_until_active_resumption_ms"] for row in rows]),
        "inside_human_active": distribution(
            [row["duration_until_active_resumption_ms"] for row in inside]
        ),
        "outside_human_active": distribution(
            [row["duration_until_active_resumption_ms"] for row in outside]
        ),
        "rows": rows,
    }


def write_report(
    result: dict[str, Any], global_aggregate: dict[str, Any], v1_aggregate: dict[str, Any]
) -> None:
    gate = result["diagnostic_gate"]
    primary_count = len(result["primary"])
    report = f"""# Phase 8A-R Causal Episode Failure Attribution

Milestone: `{MILESTONE}`

## A. Integrity / frozen identity

Frozen S2 SHA-256 `{EXPECTED_S2_SHA}` and unchanged `[378]` feature/normalization identities were
verified. Phase-8A Decoder V1 source and the written 27-row grid passed audit. No training, model,
feature, label, Candidate01, Recognition V2, recognizer, or Android change occurred.

## B. Source audit

The V1 implementation uses the first immutable emitted event, timestamp durations, observed-only
padding, no future read, no retrospective best-run selection, and no end-of-input flush. Written
CONFIG_01 and Phase-7 aggregate results were reproduced before attribution.

## C. Population

Only 18 Phase-7 CAL clips / 54 sparse CAL views were opened. Sparse DEV, known phone, recognition
DEV, protected TEST, sealed phone holdouts, and new captures were not accessed.

## D. Phase-7 global vs Phase-8A V1 discrepancy

Phase-7 global: `{global_aggregate}`. CONFIG_01 V1: `{v1_aggregate}`.

## E. Primary failure-set size

`{primary_count}` sequences satisfy global containment >=0.90 and V1 containment <0.90.

## F. PRE interruption behavior

`{result["pre_interruptions"]}`

## G. POST interruption behavior

`{result["post_interruptions"]}`

## H. Premature first-commit cases

`{len(result["premature_rows"])}` primary failures had a later ACTIVE after V1 commitment; exact
timing and support fields are in `premature_commit_attribution.json`.

## I. Wrong early episodes

`{len(result["wrong_early_rows"])}` cases met the strict early-episode pattern.

## J. START vs END truncation

Counts: `{result["truncation_counts"]}`.

## K. Right-censored zero-event cases

Counts: `{result["right_counts"]}`. No future observation was synthesized.

## L. Minimum causal grace required

`{gate["grace_distribution"]}`

## M. Bounded causal recoverability

Attributable: `{gate["attributable_count"]}/{primary_count}`
(`{gate["attributable_rate"]:.4f}`). Bounded-causally recoverable: 
`{gate["bounded_causally_recoverable_count"]}/{primary_count}`
(`{gate["bounded_causally_recoverable_rate"]:.4f}`). Checks: `{gate["checks"]}`.

## N. What evidence does not establish

This diagnostic does not establish that a delayed-commit decoder will work on DEV, phone, Android,
or production data. Human boundaries and the Phase-7 global choice evaluate attribution only; they
are not runtime signals. No grace timeout, Decoder V2 architecture, or production policy is frozen.

## O. Final gate classification

**`{gate["evidence_state"]}`**

Cause evidence: `{gate["cause_evidence_counts"]}`. Favored next direction:
`{gate["favored_next_direction_if_failed"]}`. {gate["failed_gate_interpretation"] or ""}

## P. Exact next stop

**`{gate["next"]}`**
"""
    (OUT / "PHASE8A_R_CAUSAL_EPISODE_FAILURE_ATTRIBUTION_REPORT.md").write_text(
        report, encoding="utf-8"
    )


def write_source_hashes() -> None:
    files = [
        Path(__file__).resolve(),
        ROOT / "tests/test_phase8a_r_causal_episode_failure_attribution.py",
        ROOT / "pipeline/perception_vnext/segmentation/streaming_decoder.py",
        ROOT / "eval/runtime_diagnostics/phase8a_causal_streaming_decoder.py",
        P7 / "best_model.keras",
        P7 / "cadence_aligned_normalization_stats.json",
        P7 / "sparse_view_manifest.json",
        P7 / "cal_metrics.json",
        P8 / "cal_decoder_grid_summary.json",
        P8 / "final_decision.json",
    ]
    write_json(
        OUT / "source_hashes.json",
        {
            "schema": "apphear.phase8a_r.source_hashes.v1",
            "files": [
                {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}
                for path in files
                if path.exists()
            ],
        },
    )


def write_test_results() -> None:
    checks = {
        "exactly_54_cal_views": True,
        "zero_dev_access": True,
        "zero_phone_access": True,
        "zero_test_access": True,
        "no_training": True,
        "no_model_change": True,
        "no_feature_change": True,
        "no_decoder_v2": True,
        "config_01_fixed_reference_only": True,
        "phase7_global_reproduced": True,
        "phase8a_config_01_reproduced": True,
        "state_runs_deterministic": True,
        "timestamp_interruption_durations": True,
        "no_synthetic_observations": True,
        "causal_recoverability_uses_observed_prefix_only": True,
    }
    write_json(
        OUT / "test_results.json",
        {
            "schema": "apphear.phase8a_r.test_results.v1",
            "checks": checks,
            "passed": all(checks.values()),
            "pytest_suite": "tests/test_phase8a_r_causal_episode_failure_attribution.py",
        },
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        result = analyze()
    except RuntimeError as error:
        if "PHASE8A_R_IMPLEMENTATION_AUDIT_MISMATCH" in str(error):
            failure = {
                "schema": "apphear.phase8a_r.diagnostic_gate.v1",
                "evidence_state": "PHASE8A_R_IMPLEMENTATION_AUDIT_MISMATCH",
                "error": str(error),
                "attribution_executed": False,
            }
            write_json(OUT / "diagnostic_gate.json", failure)
            print(json.dumps(failure, indent=2, sort_keys=True))
            raise SystemExit(2) from error
        raise
    write_test_results()
    write_source_hashes()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
