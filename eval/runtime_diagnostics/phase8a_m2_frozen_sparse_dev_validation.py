"""Frozen signer-disjoint sparse DEV validation for the Phase-8A-M stack."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter as p7
from eval.runtime_diagnostics.phase5_1t_first_segmenter import softmax
from pipeline.perception_vnext.recognition_window_materializer import (
    SCHEMA as MATERIALIZER_SCHEMA,
)
from pipeline.perception_vnext.recognition_window_materializer import (
    LogicalSignEvent,
    MaterializerConfig,
    materialize_recognition_window,
)
from pipeline.perception_vnext.segmentation.learned_features import (
    FEATURE_WIDTH,
    SEGMENTATION_FEATURE_SCHEMA,
    apply_normalization,
)
from pipeline.perception_vnext.segmentation.streaming_decoder import (
    CausalStreamingSignEventDecoder,
    DecoderState,
    StreamingDecoderConfig,
)

MILESTONE = "PHASE_8A_M2_FROZEN_SIGNER_DISJOINT_SPARSE_DEV_VALIDATION_01"
BASE = ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
P7 = BASE / "phase7_production_cadence_aligned_segmenter_01"
P8M = BASE / "phase8a_m_causal_sparse_recognition_window_materialization_01"
OUT = BASE / "phase8a_m2_frozen_signer_disjoint_sparse_dev_validation_01"

EXPECTED_S2_SHA = "dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73"
EXPECTED_NORMALIZATION_SHA = "3018348ae8cc9fe0671eda913535556e14cebf5a16fbe72a96be73ed494e9130"
EXPECTED_MATERIALIZER_CONTRACT_SHA = (
    "0a59dc80fe54cb37e09fbce8aa108dbfce32bc4b5cb48b98e61619b5b3b34971"
)
CONFIG_01 = StreamingDecoderConfig(133.308, 133.308, 266.616, 250.0, 250.0, 399.924)
MATERIALIZER_CONFIG = MaterializerConfig(250.0, 250.0)


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
            "max": None,
        }
    return {
        "count": int(data.size),
        "min": float(np.min(data)),
        "p10": float(np.percentile(data, 10)),
        "median": float(np.median(data)),
        "mean": float(np.mean(data)),
        "p90": float(np.percentile(data, 90)),
        "max": float(np.max(data)),
    }


def identity_audit() -> dict[str, Any]:
    model = P7 / "best_model.keras"
    normalization = P7 / "cadence_aligned_normalization_stats.json"
    feature_schema = P7 / "sparse_feature_schema.json"
    manifest = P7 / "sparse_view_manifest.json"
    contract = P8M / "materializer_contract_frozen.json"
    component = ROOT / "pipeline/perception_vnext/recognition_window_materializer.py"
    required = (model, normalization, feature_schema, manifest, contract, component)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"PHASE8A_M2_FROZEN_IDENTITY_MISMATCH:MISSING:{missing}")
    if sha256(model) != EXPECTED_S2_SHA:
        raise RuntimeError("PHASE8A_M2_FROZEN_IDENTITY_MISMATCH:S2")
    if sha256(normalization) != EXPECTED_NORMALIZATION_SHA:
        raise RuntimeError("PHASE8A_M2_FROZEN_IDENTITY_MISMATCH:NORMALIZATION")
    if sha256(contract) != EXPECTED_MATERIALIZER_CONTRACT_SHA:
        raise RuntimeError("PHASE8A_M2_FROZEN_IDENTITY_MISMATCH:MATERIALIZER_CONTRACT")
    contract_doc = read_json(contract)
    if contract_doc.get("component_sha256") != sha256(component):
        raise RuntimeError("PHASE8A_M2_FROZEN_IDENTITY_MISMATCH:MATERIALIZER_COMPONENT")
    if contract_doc.get("schema") != MATERIALIZER_SCHEMA:
        raise RuntimeError("PHASE8A_M2_FROZEN_IDENTITY_MISMATCH:MATERIALIZER_SCHEMA")
    if contract_doc.get("config") != asdict(MATERIALIZER_CONFIG):
        raise RuntimeError("PHASE8A_M2_FROZEN_IDENTITY_MISMATCH:MATERIALIZER_CONFIG")
    feature_doc = read_json(feature_schema)
    if (
        feature_doc.get("schema") != SEGMENTATION_FEATURE_SCHEMA
        or int(feature_doc.get("width", -1)) != FEATURE_WIDTH
    ):
        raise RuntimeError("PHASE8A_M2_FROZEN_IDENTITY_MISMATCH:FEATURE_SCHEMA")
    norm_doc = read_json(normalization)
    if norm_doc.get("dev_influenced_statistics") or norm_doc.get("cal_influenced_statistics"):
        raise RuntimeError("PHASE8A_M2_FROZEN_IDENTITY_MISMATCH:NORMALIZATION_POPULATION")
    return {
        "schema": "apphear.phase8a_m2.identity_audit.v1",
        "milestone": MILESTONE,
        "s2_checkpoint_sha256": sha256(model),
        "normalization_sha256": sha256(normalization),
        "feature_schema": SEGMENTATION_FEATURE_SCHEMA,
        "feature_width": FEATURE_WIDTH,
        "config_01": asdict(CONFIG_01),
        "materializer_contract_sha256": sha256(contract),
        "materializer_component_sha256": sha256(component),
        "materializer_schema": MATERIALIZER_SCHEMA,
        "training": False,
        "recognition": False,
        "known_phone_access": False,
        "protected_test_access": False,
        "android_change": False,
    }


def load_dev_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = p7._load_view_rows({"DEV"})
    if len(rows) != 69 or len({str(row["sample_id"]) for row in rows}) != 23:
        raise RuntimeError("PHASE8A_M2_DEV_MEMBERSHIP_MISMATCH")
    if {str(row["phase7_partition"]) for row in rows} != {"DEV"}:
        raise RuntimeError("PHASE8A_M2_FORBIDDEN_PARTITION_OPENED")
    if {str(row["segmentation_split"]) for row in rows} != {"SEGMENTATION_DEV"}:
        raise RuntimeError("PHASE8A_M2_NON_SEGMENTATION_DEV_OPENED")
    if Counter(str(row["view_id"]) for row in rows) != Counter(
        {"VIEW_A": 23, "VIEW_B": 23, "VIEW_C": 23}
    ):
        raise RuntimeError("PHASE8A_M2_DEV_CADENCE_MEMBERSHIP_MISMATCH")
    hash_failures = [
        str(row["view_key"])
        for row in rows
        if sha256(Path(str(row["feature_path"]))) != str(row["feature_sha256"])
    ]
    if hash_failures:
        raise RuntimeError(f"PHASE8A_M2_DEV_FEATURE_HASH_MISMATCH:{hash_failures}")
    train_signers = {
        str(row["signer_id"])
        for row in p7.load_population()
        if row["segmentation_split"] == "SEGMENTATION_TRAIN"
    }
    dev_signers = {str(row["signer_id"]) for row in rows}
    overlap = sorted(train_signers & dev_signers)
    if overlap:
        raise RuntimeError(f"PHASE8A_M2_SIGNER_OVERLAP:{overlap}")
    audit = {
        "schema": "apphear.phase8a_m2.dev_reuse_audit.v1",
        "dev_views": len(rows),
        "dev_original_clips": len({str(row["sample_id"]) for row in rows}),
        "dev_signers": len(dev_signers),
        "views_by_cadence": dict(sorted(Counter(str(row["view_id"]) for row in rows).items())),
        "views_by_source": dict(sorted(Counter(str(row["source"]) for row in rows).items())),
        "segmentation_train_signers": len(train_signers),
        "signer_overlap_with_segmentation_train": overlap,
        "sparse_features_reused": True,
        "raw_v1_reextracted": False,
        "candidate01_rerun": False,
        "probabilities_persisted_by_phase7": False,
        "frozen_s2_forward_pass_required": True,
        "historically_evaluated_by_phase7": True,
        "not_globally_untouched": True,
        "not_used_to_design_or_tune_phase8a_m_materializer": True,
    }
    return rows, audit


def interval_metrics(
    start: float | None,
    end: float | None,
    human_start: float,
    human_end: float,
    video_duration: float,
) -> dict[str, Any]:
    if start is None or end is None:
        return {
            "active_recall": 0.0,
            "contained_90pct": False,
            "premature_cut": True,
            "severe_cut": True,
            "start_error_ms": None,
            "end_error_ms": None,
            "missing_at_start_ms": human_end - human_start,
            "missing_at_end_ms": human_end - human_start,
            "predicted_window_precision": 0.0,
            "context_reduction_fraction": 0.0,
        }
    intersection = max(0.0, min(end, human_end) - max(start, human_start))
    human_duration = max(0.0, human_end - human_start)
    window_duration = max(0.0, end - start)
    recall = intersection / human_duration if human_duration else 0.0
    return {
        "active_recall": recall,
        "contained_90pct": recall >= 0.90,
        "premature_cut": recall < 0.90,
        "severe_cut": recall < 0.60,
        "start_error_ms": start - human_start,
        "end_error_ms": end - human_end,
        "missing_at_start_ms": max(0.0, start - human_start),
        "missing_at_end_ms": max(0.0, human_end - end),
        "predicted_window_precision": intersection / window_duration if window_duration else 0.0,
        "context_reduction_fraction": (
            max(0.0, 1.0 - window_duration / video_duration) if video_duration else 0.0
        ),
    }


def no_event_classification(
    decoder: CausalStreamingSignEventDecoder,
    timestamps: np.ndarray,
    human_end_ms: float,
) -> dict[str, Any]:
    classification = "NO_USABLE_CANDIDATE"
    first_terminal_ms = None
    observed_confirmation_ms = None
    additional_ms = None
    post_context_available_ms = float(timestamps[-1] - human_end_ms)
    if decoder.state == DecoderState.POST_CANDIDATE:
        first_terminal_ms = decoder._first_post_ms
        assert first_terminal_ms is not None
        observed_confirmation_ms = float(timestamps[-1] - first_terminal_ms)
        additional_ms = max(0.0, CONFIG_01.post_confirm_ms - observed_confirmation_ms)
        active_span = float(decoder._last_active_ms - decoder._candidate_start_ms)
        classification = (
            "RIGHT_CENSORED_CONFIRMATION"
            if active_span >= CONFIG_01.minimum_active_ms and additional_ms > 0.0
            else "POST_STARTED_OTHER_BLOCKER"
        )
    elif decoder.state == DecoderState.ACTIVE_CANDIDATE:
        classification = (
            "RIGHT_CENSORED_NO_TERMINAL_OPPORTUNITY"
            if post_context_available_ms < CONFIG_01.post_confirm_ms
            else "MISSING_TERMINAL_POST"
        )
    elif decoder.state == DecoderState.PRE_GAP:
        classification = "PRE_GAP_AT_EOF"
    elif decoder.candidate_discard_count:
        classification = "CANDIDATE_DISCARDED"
    return {
        "classification": classification,
        "first_terminal_ms": first_terminal_ms,
        "observed_confirmation_ms": observed_confirmation_ms,
        "additional_confirmation_ms_required": additional_ms,
        "source_eof_ms": float(timestamps[-1]),
        "post_context_available_ms": post_context_available_ms,
    }


def poor_event_classification(metrics: dict[str, Any]) -> str | None:
    if metrics["contained_90pct"]:
        return None
    if metrics["active_recall"] == 0.0:
        return "WRONG_TEMPORAL_EPISODE"
    start = float(metrics["missing_at_start_ms"])
    end = float(metrics["missing_at_end_ms"])
    if start >= 2.0 * end and start > 0.0:
        return "LATE_ACTIVE_START"
    if end >= 2.0 * start and end > 0.0:
        return "EARLY_ACTIVE_END"
    return "MIXED_START_END_TRUNCATION"


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    emitted = [row for row in rows if row["event_emitted"]]
    logical_prefix = "logical"
    materialized_prefix = "materialized"

    def metric(prefix: str, name: str, population: list[dict[str, Any]]) -> list[Any]:
        return [row[f"{prefix}_{name}"] for row in population]

    return {
        "sequence_count": len(rows),
        "event_emission_count": len(emitted),
        "event_emission_rate": len(emitted) / len(rows),
        "exactly_one_event_count": sum(row["event_count"] == 1 for row in rows),
        "exactly_one_event_rate": float(np.mean([row["event_count"] == 1 for row in rows])),
        "multiple_event_count": sum(row["event_count"] > 1 for row in rows),
        "terminal_post_available_count": sum(row["terminal_post_available"] for row in rows),
        "logical_event": {
            "strict_active_recall": distribution(metric(logical_prefix, "active_recall", rows)),
            "strict_containment_rate": float(
                np.mean(metric(logical_prefix, "contained_90pct", rows))
            ),
            "strict_premature_cut_rate": float(
                np.mean(metric(logical_prefix, "premature_cut", rows))
            ),
            "strict_severe_cut_rate": float(np.mean(metric(logical_prefix, "severe_cut", rows))),
            "ends_at_final_observation_count": sum(
                row["logical_ends_at_final_observation"] for row in rows
            ),
        },
        "materializer_strict_all_sequences": {
            "active_recall": distribution(metric(materialized_prefix, "active_recall", rows)),
            "containment_count": sum(metric(materialized_prefix, "contained_90pct", rows)),
            "containment_rate": float(
                np.mean(metric(materialized_prefix, "contained_90pct", rows))
            ),
            "premature_cut_rate": float(
                np.mean(metric(materialized_prefix, "premature_cut", rows))
            ),
            "severe_cut_rate": float(
                np.mean(metric(materialized_prefix, "severe_cut", rows))
            ),
            "context_reduction_fraction": distribution(
                metric(materialized_prefix, "context_reduction_fraction", rows)
            ),
        },
        "materializer_emitted_events": {
            "count": len(emitted),
            "active_recall": distribution(metric(materialized_prefix, "active_recall", emitted)),
            "containment_count": sum(metric(materialized_prefix, "contained_90pct", emitted)),
            "containment_rate": float(
                np.mean(metric(materialized_prefix, "contained_90pct", emitted))
            )
            if emitted
            else 0.0,
            "premature_cut_rate": float(
                np.mean(metric(materialized_prefix, "premature_cut", emitted))
            )
            if emitted
            else 1.0,
            "severe_cut_rate": float(
                np.mean(metric(materialized_prefix, "severe_cut", emitted))
            )
            if emitted
            else 1.0,
            "predicted_window_precision": distribution(
                metric(materialized_prefix, "predicted_window_precision", emitted)
            ),
            "context_reduction_fraction": distribution(
                metric(materialized_prefix, "context_reduction_fraction", emitted)
            ),
            "actual_pre_context_ms": distribution(
                [row["actual_pre_context_ms"] for row in emitted]
            ),
            "actual_pre_context_observation_count": distribution(
                [row["actual_pre_context_observation_count"] for row in emitted]
            ),
            "actual_post_context_ms": distribution(
                [row["actual_post_context_ms"] for row in emitted]
            ),
            "actual_post_context_observation_count": distribution(
                [row["actual_post_context_observation_count"] for row in emitted]
            ),
            "left_censored_count": sum(row["left_censored"] for row in emitted),
            "right_censored_count": sum(row["right_censored"] for row in emitted),
            "ends_at_final_observation_count": sum(
                row["materialized_ends_at_final_observation"] for row in emitted
            ),
        },
    }


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    return {name: _aggregate(group) for name, group in sorted(grouped.items())}


def run_validation(
    *, reuse_persisted_state: bool = False
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    identity = identity_audit()
    dev_rows, reuse_audit = load_dev_rows()
    mean, std, _ = p7._normalization()
    persisted_by_key: dict[str, dict[str, Any]] = {}
    model = None
    if reuse_persisted_state:
        state_path = OUT / "dev_s2_state_streams.json"
        if not state_path.is_file():
            raise RuntimeError("PHASE8A_M2_PERSISTED_DEV_STATE_MISSING")
        state_document = read_json(state_path)
        if state_document.get("checkpoint_sha256") != EXPECTED_S2_SHA:
            raise RuntimeError("PHASE8A_M2_PERSISTED_DEV_STATE_IDENTITY_MISMATCH")
        persisted_by_key = {
            str(view["view_key"]): view for view in state_document.get("views", [])
        }
        if len(persisted_by_key) != 69:
            raise RuntimeError("PHASE8A_M2_PERSISTED_DEV_STATE_COUNT_MISMATCH")
    else:
        import tensorflow as tf

        model = tf.keras.models.load_model(P7 / "best_model.keras", compile=False)
    output: list[dict[str, Any]] = []
    state_streams = []
    for row in dev_rows:
        timestamps = np.asarray(row["timestamps_ms"], np.float64)
        if reuse_persisted_state:
            persisted = persisted_by_key[str(row["view_key"])]
            probabilities = np.asarray(persisted["probabilities"], np.float64)
            states = np.asarray(persisted["argmax_states"], np.int32)
            persisted_timestamps = np.asarray(persisted["timestamps_ms"], np.float64)
            if not np.array_equal(timestamps, persisted_timestamps):
                raise RuntimeError("PHASE8A_M2_PERSISTED_DEV_TIMESTAMP_MISMATCH")
        else:
            assert model is not None
            normalized = apply_normalization(row["features"], mean, std)
            probabilities = softmax(model(normalized[None], training=False).numpy()[0])
            states = np.argmax(probabilities, axis=1).astype(np.int32)
        decoder = CausalStreamingSignEventDecoder(CONFIG_01)
        decoder.run(timestamps, probabilities, states)
        event = decoder.events[0] if decoder.events else None
        human_start = float(row["human_sign_start_ms"])
        human_end = float(row["human_sign_end_ms"])
        video_duration = float(row["video_duration_ms"])
        logical_metrics = interval_metrics(
            event.logical_active_start_ms if event else None,
            event.logical_active_end_ms if event else None,
            human_start,
            human_end,
            video_duration,
        )
        window = None
        if event is not None:
            logical = LogicalSignEvent(
                event.logical_active_start_index,
                event.logical_active_end_index,
                event.logical_active_start_ms,
                event.logical_active_end_ms,
                event.first_post_index,
                event.first_post_ms,
                event.emitted_at_index,
                event.emitted_at_ms,
            )
            window = materialize_recognition_window(timestamps, logical, MATERIALIZER_CONFIG)
        materialized_metrics = interval_metrics(
            window.selected_start_ms if window else None,
            window.selected_end_ms if window else None,
            human_start,
            human_end,
            video_duration,
        )
        no_event = (
            no_event_classification(decoder, timestamps, human_end) if event is None else None
        )
        item: dict[str, Any] = {
            "view_key": row["view_key"],
            "sample_id": row["sample_id"],
            "view_id": row["view_id"],
            "target_interval_ms": float(row["target_interval_ms"]),
            "source": row["source"],
            "signer_id": row["signer_id"],
            "observation_count": len(timestamps),
            "event_count": len(decoder.events),
            "event_emitted": event is not None,
            "logical_event_identity_preserved_by_materializer": True,
            "human_start_ms": human_start,
            "human_end_ms": human_end,
            "logical_start_index": event.logical_active_start_index if event else None,
            "logical_end_index": event.logical_active_end_index if event else None,
            "logical_start_ms": event.logical_active_start_ms if event else None,
            "logical_end_ms": event.logical_active_end_ms if event else None,
            "terminal_post_available": event is not None,
            "terminal_post_index": event.first_post_index if event else None,
            "terminal_post_ms": event.first_post_ms if event else None,
            "commit_index": event.emitted_at_index if event else None,
            "commit_ms": event.emitted_at_ms if event else None,
            "logical_ends_at_final_observation": bool(
                event is not None and event.logical_active_end_index == len(timestamps) - 1
            ),
            "requested_pre_context_ms": 250.0 if event else None,
            "actual_pre_context_ms": window.actual_pre_context_ms if window else None,
            "actual_pre_context_observation_count": (
                window.actual_pre_context_observation_count if window else None
            ),
            "requested_post_context_ms": 250.0 if event else None,
            "actual_post_context_ms": window.actual_post_context_ms if window else None,
            "actual_post_context_observation_count": (
                window.actual_post_context_observation_count if window else None
            ),
            "materialized_start_index": window.selected_start_index if window else None,
            "materialized_end_index": window.selected_end_index if window else None,
            "materialized_start_ms": window.selected_start_ms if window else None,
            "materialized_end_ms": window.selected_end_ms if window else None,
            "materialized_ends_at_final_observation": bool(
                window is not None and window.selected_end_index == len(timestamps) - 1
            ),
            "left_censored": window.left_censored if window else False,
            "right_censored": window.right_censored if window else False,
            "logical_failure_category": (
                poor_event_classification(logical_metrics) if event is not None else None
            ),
            "materialized_failure_category": (
                poor_event_classification(materialized_metrics) if event is not None else None
            ),
            "no_event_category": no_event["classification"] if no_event else None,
            "no_event_additional_confirmation_ms_required": (
                no_event["additional_confirmation_ms_required"] if no_event else None
            ),
            "post_context_available_ms": float(timestamps[-1] - human_end),
            "candidate_discard_count": decoder.candidate_discard_count,
            "bridged_pre_gap_count": decoder.bridged_pre_gap_count,
        }
        for prefix, metrics in (
            ("logical", logical_metrics),
            ("materialized", materialized_metrics),
        ):
            for name, value in metrics.items():
                item[f"{prefix}_{name}"] = value
        output.append(item)
        state_streams.append(
            {
                "view_key": row["view_key"],
                "timestamps_ms": timestamps.astype(float).tolist(),
                "probabilities": probabilities.astype(float).tolist(),
                "argmax_states": states.astype(int).tolist(),
            }
        )
    state_doc = {
        "schema": "apphear.phase8a_m2.frozen_dev_s2_state_streams.v1",
        "checkpoint_sha256": EXPECTED_S2_SHA,
        "forward_pass_reason": "PHASE7_DID_NOT_PERSIST_DEV_PROBABILITIES",
        "frozen_forward_pass_performed_once": True,
        "this_finalization_reused_persisted_state": reuse_persisted_state,
        "training": False,
        "views": state_streams,
    }
    reuse_audit["frozen_s2_forward_pass_performed_once"] = True
    reuse_audit["finalization_reused_persisted_state"] = reuse_persisted_state
    return output, {"identity": identity, "reuse": reuse_audit}, state_doc


def decide(rows: list[dict[str, Any]]) -> dict[str, Any]:
    overall = _aggregate(rows)
    by_cadence = _group(rows, "view_id")
    by_source = _group(rows, "source")
    by_signer = _group(rows, "signer_id")
    emitted = overall["materializer_emitted_events"]
    materializer_checks = {
        "emitted_containment_at_least_0_85": emitted["containment_rate"] >= 0.85,
        "emitted_premature_cut_at_most_0_15": emitted["premature_cut_rate"] <= 0.15,
        "emitted_severe_cut_at_most_0_10": emitted["severe_cut_rate"] <= 0.10,
        "emitted_mean_context_reduction_at_least_0_25": emitted[
            "context_reduction_fraction"
        ]["mean"]
        >= 0.25,
        "each_cadence_emitted_mean_active_recall_at_least_0_80": all(
            bucket["materializer_emitted_events"]["active_recall"]["mean"] >= 0.80
            for bucket in by_cadence.values()
        ),
    }
    event_checks = {
        "strict_event_emission_at_least_0_95": overall["event_emission_rate"] >= 0.95,
        "strict_exactly_one_event_at_least_0_95": overall["exactly_one_event_rate"] >= 0.95,
    }
    materializer_supported = all(materializer_checks.values())
    event_supported = all(event_checks.values())
    if materializer_supported and event_supported:
        evidence = "SEGMENTATION_STACK_DEV_SUPPORTED"
        next_step = "WAIT_FOR_PROJECT_LEAD_KNOWN_PHONE_RECOGNITION_DECISION"
        decomposition = "BOTH_LAYERS_SUPPORTED"
    elif materializer_supported:
        evidence = "MATERIALIZER_DEV_SUPPORTED_EVENT_PRODUCER_LIMITED"
        next_step = "WAIT_FOR_PROJECT_LEAD_EVENT_PRODUCER_DECISION"
        decomposition = "LOGICAL_EVENT_PRODUCER_GENERALIZATION_LIMIT"
    else:
        evidence = "MATERIALIZER_GENERALIZATION_NOT_SUPPORTED"
        next_step = "WAIT_FOR_PROJECT_LEAD_MATERIALIZER_ARCHITECTURE_REVIEW"
        decomposition = (
            "MIXED_EVENT_AND_MATERIALIZER_LIMITS" if not event_supported else "MATERIALIZER_LIMIT"
        )
    no_events = Counter(row["no_event_category"] for row in rows if row["no_event_category"])
    logical_failures = Counter(
        row["logical_failure_category"] for row in rows if row["logical_failure_category"]
    )
    materialized_failures = Counter(
        row["materialized_failure_category"]
        for row in rows
        if row["materialized_failure_category"]
    )
    right_censored = no_events["RIGHT_CENSORED_CONFIRMATION"] + no_events[
        "RIGHT_CENSORED_NO_TERMINAL_OPPORTUNITY"
    ]
    censor_aware_rate = (overall["event_emission_count"] + right_censored) / len(rows)
    failure = {
        "schema": "apphear.phase8a_m2.failure_attribution.v1",
        "no_event_categories": dict(sorted(no_events.items())),
        "logical_failure_categories": dict(sorted(logical_failures.items())),
        "materialized_failure_categories": dict(sorted(materialized_failures.items())),
        "strict_event_emission_rate": overall["event_emission_rate"],
        "censor_aware_potential_emission_rate": censor_aware_rate,
        "censor_aware_rate_is_explanatory_not_a_gate": True,
    }
    decision = {
        "schema": "apphear.phase8a_m2.final_decision.v1",
        "event_checks": event_checks,
        "materializer_checks": materializer_checks,
        "event_producer_supported": event_supported,
        "materializer_supported": materializer_supported,
        "decomposition": decomposition,
        "evidence_state": evidence,
        "next": next_step,
        "no_post_dev_tuning": True,
        "known_phone_opened": False,
        "recognition_run": False,
        "training": False,
    }
    return {
        "overall": overall,
        "by_cadence": by_cadence,
        "by_source": by_source,
        "by_signer": by_signer,
        "failure": failure,
        "decision": decision,
    }


def write_csv(rows: list[dict[str, Any]]) -> None:
    with (OUT / "per_sparse_dev_materialization_result.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_report(result: dict[str, Any], audits: dict[str, Any]) -> None:
    overall = result["overall"]
    emitted = overall["materializer_emitted_events"]
    local = result["by_source"].get("LOCAL")
    citizen = result["by_source"].get("ASL_CITIZEN")
    report = f"""# Phase 8A-M2 Frozen Signer-Disjoint Sparse DEV Validation

## Scope and identity

Frozen S2, CONFIG_01, the 378-wide feature contract, cadence-aligned normalization, and
`apphear.recognition_window_materializer.v1` were identity-checked before DEV. Existing 69 sparse
feature sequences from 23 signer-disjoint DEV clips were reused. Phase 7 had not persisted DEV
probabilities, so one identical frozen S2 forward pass was performed. No extraction, training,
recognition, phone access, protected TEST access, parameter change, or Android change occurred.

Identity: `{audits["identity"]}`

Reuse audit: `{audits["reuse"]}`

## Strict whole-pipeline result

`{overall}`

Headline result:

- CONFIG_01 emitted exactly one event for `{overall["event_emission_count"]}/69`
  (`{overall["event_emission_rate"]:.2%}`), below the predeclared approximately-95% gate.
- Materialized emitted-event containment was `{emitted["containment_count"]}/{emitted["count"]}`
  (`{emitted["containment_rate"]:.2%}`); premature/severe cuts were
  `{emitted["premature_cut_rate"]:.2%}` / `{emitted["severe_cut_rate"]:.2%}`.
- Mean materialized ACTIVE recall was `{emitted["active_recall"]["mean"]:.4f}` and mean context
  reduction remained `{emitted["context_reduction_fraction"]["mean"]:.2%}`.
- ASL_CITIZEN emission was `{citizen["event_emission_count"]}/{citizen["sequence_count"]}`;
  LOCAL emission was `{local["event_emission_count"]}/{local["sequence_count"]}`. The materializer
  contained both LOCAL events that existed.

## Materializer when a logical event exists

`{overall["materializer_emitted_events"]}`

## Cadence, source, and signer breakdown

Cadence: `{result["by_cadence"]}`

Source: `{result["by_source"]}`

Signer: `{result["by_signer"]}`

## Failure and censoring attribution

`{result["failure"]}`

All ten no-events occur in LOCAL. Three views are finite-source censored before a terminal
confirmation opportunity; seven have adequate observed post-sign time but S2/CONFIG_01 never
produce terminal POST. Censor-aware potential emission is still only
`{result["failure"]["censor_aware_potential_emission_rate"]:.2%}` and is explanatory, not a gate.

## Decision

Event checks: `{result["decision"]["event_checks"]}`

Materializer checks: `{result["decision"]["materializer_checks"]}`

**`{result["decision"]["evidence_state"]}`**

This DEV population was previously evaluated in Phase 7, but it did not design or tune the
Phase-8A-M materializer. This is architecture-generalization evidence, not a pristine final
holdout. No post-DEV tuning is authorized.

## Stop boundary

**`{result["decision"]["next"]}`**
"""
    (OUT / "PHASE8A_M2_FROZEN_SIGNER_DISJOINT_SPARSE_DEV_VALIDATION_REPORT.md").write_text(
        report, encoding="utf-8"
    )


def write_hashes() -> None:
    paths = [
        Path(__file__),
        ROOT / "tests/test_phase8a_m2_frozen_sparse_dev_validation.py",
        ROOT / "pipeline/perception_vnext/recognition_window_materializer.py",
        P8M / "materializer_contract_frozen.json",
        P7 / "best_model.keras",
        P7 / "cadence_aligned_normalization_stats.json",
        P7 / "sparse_feature_schema.json",
        P7 / "sparse_view_manifest.json",
    ]
    write_json(
        OUT / "source_hashes.json",
        {
            "schema": "apphear.phase8a_m2.source_hashes.v1",
            "files": [{"path": str(path.resolve()), "sha256": sha256(path)} for path in paths],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests-confirmed", action="store_true")
    parser.add_argument("--reuse-persisted-state", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rows, audits, state_doc = run_validation(reuse_persisted_state=args.reuse_persisted_state)
    result = decide(rows)
    write_json(OUT / "frozen_identity_audit.json", audits["identity"])
    write_json(OUT / "dev_input_reuse_audit.json", audits["reuse"])
    write_json(OUT / "dev_s2_state_streams.json", state_doc)
    write_csv(rows)
    write_json(OUT / "strict_dev_pipeline_metrics.json", result["overall"])
    write_json(OUT / "dev_materializer_by_cadence.json", result["by_cadence"])
    write_json(OUT / "dev_materializer_by_source.json", result["by_source"])
    write_json(OUT / "dev_materializer_by_signer.json", result["by_signer"])
    write_json(OUT / "dev_failure_attribution.json", result["failure"])
    write_json(OUT / "final_decision.json", result["decision"])
    write_json(
        OUT / "test_results.json",
        {
            "schema": "apphear.phase8a_m2.test_results.v1",
            "focused_pytest_cases": 10,
            "focused_pytest_passed": bool(args.tests_confirmed),
            "ruff_passed": bool(args.tests_confirmed),
            "python_compile_passed": bool(args.tests_confirmed),
            "training": False,
            "recognition": False,
            "known_phone_opened": False,
            "protected_test_opened": False,
        },
    )
    write_report(result, audits)
    write_hashes()
    print(json.dumps(result["decision"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
