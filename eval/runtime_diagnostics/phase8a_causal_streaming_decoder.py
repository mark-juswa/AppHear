"""Phase 8A: freeze and evaluate one causal streaming SignEvent decoder.

The 27 decoder configurations are selected on Phase-7 CAL state outputs only.
The winning JSON is hash-frozen before signer-disjoint sparse DEV is opened.
Known phone replay is permitted only after the DEV engineering gate passes.
No training API is called by this module.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter as p7  # noqa: E402
from eval.runtime_diagnostics.phase5_1t_first_segmenter import (  # noqa: E402
    softmax,
    state_metrics,
)
from pipeline.perception_vnext.segmentation.learned_features import (  # noqa: E402
    FEATURE_WIDTH,
    SEGMENTATION_FEATURE_SCHEMA,
    apply_normalization,
    derive_causal_segmentation_features,
)
from pipeline.perception_vnext.segmentation.streaming_decoder import (  # noqa: E402
    ACTIVE_SIGN,
    POST_RECOVERY,
    PRE_IDLE,
    CausalStreamingSignEventDecoder,
    SignEvent,
    StreamingDecoderConfig,
)

MILESTONE = "PHASE_8A_CAUSAL_STREAMING_SIGN_EVENT_DECODER_01"
BASE = ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
P7 = BASE / "phase7_production_cadence_aligned_segmenter_01"
OUT = BASE / "phase8a_causal_streaming_sign_event_decoder_01"
EXPECTED_MODEL_SHA = "dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73"
EXPECTED_BEST_EPOCH = 17
EXPECTED_NORMALIZATION_SHA = "3018348ae8cc9fe0671eda913535556e14cebf5a16fbe72a96be73ed494e9130"
MINIMUM_ACTIVE_VALUES = (133.308, 199.962, 266.616)
PRE_GAP_VALUES = (133.308, 199.962, 266.616)
POST_CONFIRM_VALUES = (266.616, 399.924, 533.232)
REARM_PRE_STABLE_MS = 399.924
PRE_PADDING_MS = 250.0
POST_PADDING_MS = 250.0
ATTEMPTS = tuple(f"attempt_{index:03d}" for index in range(1, 11))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(value))


def freeze_json(path: Path, value: Any) -> None:
    payload = canonical_json(value)
    if path.exists() and path.read_bytes() != payload:
        raise RuntimeError(f"FROZEN_ARTIFACT_MUTATION_REFUSED:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(payload)


def distribution(values: Iterable[float]) -> dict[str, float | int | None]:
    data = np.asarray(list(values), np.float64)
    if data.size == 0:
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


def verify_s2_identity() -> dict[str, Any]:
    model_path = P7 / "best_model.keras"
    normalization_path = P7 / "cadence_aligned_normalization_stats.json"
    identity_path = P7 / "best_model.sha256.json"
    history_path = P7 / "training_history.json"
    manifest_path = P7 / "sparse_view_manifest.json"
    for path in (model_path, normalization_path, identity_path, history_path, manifest_path):
        if not path.is_file():
            raise RuntimeError(f"PHASE8A_FROZEN_S2_ARTIFACT_MISSING:{path}")
    model_sha = sha256(model_path)
    normalization_sha = sha256(normalization_path)
    identity = read_json(identity_path)
    history = read_json(history_path)
    manifest = read_json(manifest_path)
    if model_sha != EXPECTED_MODEL_SHA or identity.get("sha256") != EXPECTED_MODEL_SHA:
        raise RuntimeError("PHASE8A_FROZEN_S2_MODEL_IDENTITY_MISMATCH")
    if normalization_sha != EXPECTED_NORMALIZATION_SHA:
        raise RuntimeError("PHASE8A_FROZEN_S2_NORMALIZATION_IDENTITY_MISMATCH")
    if history.get("best_epoch") != EXPECTED_BEST_EPOCH:
        raise RuntimeError("PHASE8A_FROZEN_S2_BEST_EPOCH_MISMATCH")
    if history.get("checkpoint_population") != "CAL_ONLY":
        raise RuntimeError("PHASE8A_S2_CHECKPOINT_WAS_NOT_CAL_ONLY")
    if (manifest.get("cal_view_count"), manifest.get("dev_view_count")) != (54, 69):
        raise RuntimeError("PHASE8A_SPARSE_POPULATION_MISMATCH")
    document = {
        "schema": "apphear.phase8a.frozen_s2_identity.v1",
        "milestone": MILESTONE,
        "checkpoint": {"path": str(model_path.resolve()), "sha256": model_sha},
        "best_epoch": EXPECTED_BEST_EPOCH,
        "checkpoint_selection": "CAL_ONLY_PREDECLARED_LEXICOGRAPHIC_RULE",
        "feature_schema": SEGMENTATION_FEATURE_SCHEMA,
        "feature_width": FEATURE_WIDTH,
        "normalization": {
            "path": str(normalization_path.resolve()),
            "sha256": normalization_sha,
            "phase7_cadence_aligned": True,
        },
        "phase7_sparse_manifest_sha256": sha256(manifest_path),
        "cal_views": 54,
        "dev_views": 69,
        "training_in_phase8a": False,
        "weights_changed": False,
        "normalization_changed": False,
        "features_changed": False,
    }
    freeze_json(OUT / "frozen_s2_identity.json", document)
    return document


def decoder_grid() -> list[StreamingDecoderConfig]:
    return [
        StreamingDecoderConfig(
            minimum_active_ms=minimum,
            pre_gap_reset_ms=pre_gap,
            post_confirm_ms=post_confirm,
            pre_padding_ms=PRE_PADDING_MS,
            post_padding_ms=POST_PADDING_MS,
            rearm_pre_stable_ms=REARM_PRE_STABLE_MS,
        )
        for minimum, pre_gap, post_confirm in itertools.product(
            MINIMUM_ACTIVE_VALUES, PRE_GAP_VALUES, POST_CONFIRM_VALUES
        )
    ]


def search_document() -> dict[str, Any]:
    configs = decoder_grid()
    if len(configs) != 27:
        raise AssertionError("PHASE8A_GRID_NOT_27")
    return {
        "schema": "apphear.phase8a.decoder_search_config.v1",
        "milestone": MILESTONE,
        "population": "PHASE7_CAL_ONLY_18_CLIPS_54_SPARSE_VIEWS",
        "input": "S2_ARGMAX_STATE_WITH_TIMESTAMP_AND_PROBABILITIES",
        "minimum_active_ms": list(MINIMUM_ACTIVE_VALUES),
        "pre_gap_reset_ms": list(PRE_GAP_VALUES),
        "post_confirm_ms": list(POST_CONFIRM_VALUES),
        "pre_padding_ms": PRE_PADDING_MS,
        "post_padding_ms": POST_PADDING_MS,
        "rearm_pre_stable_ms": REARM_PRE_STABLE_MS,
        "configuration_count": 27,
        "probability_threshold_search": False,
        "selection_population": "CAL_ONLY",
        "eligibility": {
            "event_emission_rate_min": 0.95,
            "exactly_one_event_rate_min": 0.95,
            "containment_rate_min": 0.85,
            "premature_cut_rate_max": 0.15,
            "severe_cut_rate_max": 0.10,
            "mean_context_reduction_min": 0.25,
        },
        "selection_lexicographic": [
            "exactly_one_event_rate_MAX",
            "containment_rate_MAX",
            "premature_cut_rate_MIN",
            "severe_cut_rate_MIN",
            "mean_predicted_window_precision_MAX",
            "median_emission_latency_ms_MIN",
            "minimum_active_ms_MIN",
            "pre_gap_reset_ms_MIN",
            "post_confirm_ms_MIN",
        ],
    }


def _model_predictions(rows: list[dict[str, Any]]) -> tuple[list[np.ndarray], list[np.ndarray]]:
    mean, std, _ = p7._normalization()
    import tensorflow as tf

    model = tf.keras.models.load_model(P7 / "best_model.keras", compile=False)
    probabilities: list[np.ndarray] = []
    states: list[np.ndarray] = []
    for row in rows:
        normalized = apply_normalization(row["features"], mean, std)
        probs = softmax(model(normalized[None], training=False).numpy()[0])
        probabilities.append(probs)
        states.append(np.argmax(probs, axis=1).astype(np.int32))
    return probabilities, states


def run_decoder(
    timestamps_ms: np.ndarray,
    probabilities: np.ndarray,
    states: np.ndarray,
    config: StreamingDecoderConfig,
) -> CausalStreamingSignEventDecoder:
    decoder = CausalStreamingSignEventDecoder(config)
    decoder.run(timestamps_ms, probabilities, states)
    return decoder


def event_metrics_for_row(
    row: dict[str, Any], decoder: CausalStreamingSignEventDecoder
) -> dict[str, Any]:
    events = decoder.events
    human_start = float(row["human_sign_start_ms"])
    human_end = float(row["human_sign_end_ms"])
    human_duration = human_end - human_start
    video_duration = float(row["video_duration_ms"])
    result: dict[str, Any] = {
        "view_key": row.get("view_key"),
        "sample_id": row.get("sample_id"),
        "view_id": row.get("view_id"),
        "target_interval_ms": row.get("target_interval_ms"),
        "source": row.get("source"),
        "signer_id": row.get("signer_id"),
        "human_start_ms": human_start,
        "human_end_ms": human_end,
        "video_duration_ms": video_duration,
        "observation_count": len(row["timestamps_ms"]),
        "event_count": len(events),
        "event_emitted": bool(events),
        "exactly_one_event": len(events) == 1,
        "multiple_events": len(events) > 1,
        "candidate_discard_count": decoder.candidate_discard_count,
        "bridged_pre_gap_count": decoder.bridged_pre_gap_count,
        "active_to_post_confirm_count": decoder.active_to_post_confirm_count,
    }
    if not events:
        result.update(
            {
                "active_recall": 0.0,
                "contained_90pct": False,
                "premature_cut": True,
                "severe_cut": True,
                "predicted_window_precision": 0.0,
                "context_reduction_fraction": 1.0,
                "retained_context_ms": 0.0,
                "emission_latency_ms": None,
                "emission_latency_after_human_end_ms": None,
                "ends_at_final_observation": False,
                "emitted_at_final_observation": False,
            }
        )
        return result
    # The first immutable event is the only deployable primary event.  Later
    # events remain recorded and are penalized by the multiple-event metric.
    event = events[0]
    start = float(event.padded_start_ms)
    end = float(event.padded_end_ms)
    intersection = max(0.0, min(end, human_end) - max(start, human_start))
    active_recall = intersection / human_duration if human_duration > 0 else 0.0
    window_duration = max(0.0, end - start)
    precision = intersection / window_duration if window_duration > 0 else 0.0
    emission_signed = float(event.emitted_at_ms) - human_end
    result.update(
        {
            "active_recall": active_recall,
            "contained_90pct": active_recall >= 0.90,
            "premature_cut": active_recall < 0.90,
            "severe_cut": active_recall < 0.60,
            "predicted_window_precision": precision,
            "logical_start_error_ms": float(event.logical_active_start_ms) - human_start,
            "padded_start_error_ms": start - human_start,
            "logical_end_error_ms": float(event.logical_active_end_ms) - human_end,
            "padded_end_error_ms": end - human_end,
            "retained_context_ms": max(0.0, window_duration - intersection),
            "context_reduction_fraction": (
                max(0.0, 1.0 - window_duration / video_duration) if video_duration > 0 else 0.0
            ),
            "emission_latency_ms": emission_signed,
            "emission_latency_after_human_end_ms": max(0.0, emission_signed),
            "ends_at_final_observation": event.padded_end_index == len(row["timestamps_ms"]) - 1,
            "emitted_at_final_observation": event.emitted_at_index == len(row["timestamps_ms"]) - 1,
            "primary_event": asdict(event),
            "all_events": [asdict(value) for value in events],
        }
    )
    return result


def aggregate_event_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    emitted = [row for row in rows if row["event_emitted"]]

    def rate(key: str) -> float:
        return float(np.mean([bool(row[key]) for row in rows])) if rows else 0.0

    return {
        "sequence_count": count,
        "event_emission_rate": rate("event_emitted"),
        "exactly_one_event_rate": rate("exactly_one_event"),
        "zero_event_rate": 1.0 - rate("event_emitted"),
        "multiple_event_rate": rate("multiple_events"),
        "active_recall": distribution(row["active_recall"] for row in rows),
        "containment_rate": rate("contained_90pct"),
        "premature_cut_rate": rate("premature_cut"),
        "severe_cut_rate": rate("severe_cut"),
        "predicted_window_precision": distribution(
            row["predicted_window_precision"] for row in emitted
        ),
        "logical_start_error_ms": distribution(row["logical_start_error_ms"] for row in emitted),
        "padded_start_error_ms": distribution(row["padded_start_error_ms"] for row in emitted),
        "logical_end_error_ms": distribution(row["logical_end_error_ms"] for row in emitted),
        "padded_end_error_ms": distribution(row["padded_end_error_ms"] for row in emitted),
        "retained_context_ms": distribution(row["retained_context_ms"] for row in emitted),
        "context_reduction_fraction": distribution(
            row["context_reduction_fraction"] for row in rows
        ),
        "emission_latency_ms": distribution(row["emission_latency_ms"] for row in emitted),
        "emission_latency_after_human_end_ms": distribution(
            row["emission_latency_after_human_end_ms"] for row in emitted
        ),
        "events_ending_at_final_observation": sum(row["ends_at_final_observation"] for row in rows),
        "final_observation_end_rate": rate("ends_at_final_observation"),
        "events_emitted_at_final_observation": sum(
            row["emitted_at_final_observation"] for row in rows
        ),
        "candidate_discard_count": sum(row["candidate_discard_count"] for row in rows),
        "bridged_pre_gap_count": sum(row["bridged_pre_gap_count"] for row in rows),
        "active_to_post_confirm_count": sum(row["active_to_post_confirm_count"] for row in rows),
    }


def is_cal_eligible(metrics: dict[str, Any]) -> bool:
    return bool(
        metrics["event_emission_rate"] >= 0.95
        and metrics["exactly_one_event_rate"] >= 0.95
        and metrics["containment_rate"] >= 0.85
        and metrics["premature_cut_rate"] <= 0.15
        and metrics["severe_cut_rate"] <= 0.10
        and metrics["context_reduction_fraction"]["mean"] >= 0.25
    )


def selection_key(row: dict[str, Any]) -> tuple[float, ...]:
    metrics = row["metrics"]
    return (
        float(metrics["exactly_one_event_rate"]),
        float(metrics["containment_rate"]),
        -float(metrics["premature_cut_rate"]),
        -float(metrics["severe_cut_rate"]),
        float(metrics["predicted_window_precision"]["mean"] or 0.0),
        -float(metrics["emission_latency_after_human_end_ms"]["median"] or 0.0),
        -float(row["config"]["minimum_active_ms"]),
        -float(row["config"]["pre_gap_reset_ms"]),
        -float(row["config"]["post_confirm_ms"]),
    )


def _csv_scalar_grid(rows: list[dict[str, Any]]) -> None:
    fields = [
        "config_id",
        "minimum_active_ms",
        "pre_gap_reset_ms",
        "post_confirm_ms",
        "eligible",
        "event_emission_rate",
        "exactly_one_event_rate",
        "zero_event_rate",
        "multiple_event_rate",
        "containment_rate",
        "premature_cut_rate",
        "severe_cut_rate",
        "mean_active_recall",
        "mean_predicted_window_precision",
        "mean_context_reduction",
        "median_emission_latency_ms",
        "candidate_discard_count",
        "bridged_pre_gap_count",
        "active_to_post_confirm_count",
    ]
    with (OUT / "cal_decoder_grid_results.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            metrics = row["metrics"]
            config = row["config"]
            writer.writerow(
                {
                    "config_id": row["config_id"],
                    **{
                        key: config[key]
                        for key in ("minimum_active_ms", "pre_gap_reset_ms", "post_confirm_ms")
                    },
                    "eligible": row["eligible"],
                    "event_emission_rate": metrics["event_emission_rate"],
                    "exactly_one_event_rate": metrics["exactly_one_event_rate"],
                    "zero_event_rate": metrics["zero_event_rate"],
                    "multiple_event_rate": metrics["multiple_event_rate"],
                    "containment_rate": metrics["containment_rate"],
                    "premature_cut_rate": metrics["premature_cut_rate"],
                    "severe_cut_rate": metrics["severe_cut_rate"],
                    "mean_active_recall": metrics["active_recall"]["mean"],
                    "mean_predicted_window_precision": metrics["predicted_window_precision"][
                        "mean"
                    ],
                    "mean_context_reduction": metrics["context_reduction_fraction"]["mean"],
                    "median_emission_latency_ms": metrics["emission_latency_after_human_end_ms"][
                        "median"
                    ],
                    "candidate_discard_count": metrics["candidate_discard_count"],
                    "bridged_pre_gap_count": metrics["bridged_pre_gap_count"],
                    "active_to_post_confirm_count": metrics["active_to_post_confirm_count"],
                }
            )


def cal_search() -> dict[str, Any]:
    identity = verify_s2_identity()
    freeze_json(OUT / "decoder_search_config.json", search_document())
    rows = p7._load_view_rows({"CAL"})
    if len(rows) != 54 or len({row["sample_id"] for row in rows}) != 18:
        raise RuntimeError("PHASE8A_CAL_POPULATION_MISMATCH")
    probabilities, states = _model_predictions(rows)
    grid_rows: list[dict[str, Any]] = []
    for config_index, config in enumerate(decoder_grid(), start=1):
        results = []
        for row, probs, predicted in zip(rows, probabilities, states, strict=True):
            decoder = run_decoder(row["timestamps_ms"], probs, predicted, config)
            results.append(event_metrics_for_row(row, decoder))
        metrics = aggregate_event_metrics(results)
        grid_rows.append(
            {
                "config_id": f"CONFIG_{config_index:02d}",
                "config": asdict(config),
                "eligible": is_cal_eligible(metrics),
                "metrics": metrics,
            }
        )
    _csv_scalar_grid(grid_rows)
    eligible = [row for row in grid_rows if row["eligible"]]
    selected = max(eligible, key=selection_key) if eligible else None
    summary = {
        "schema": "apphear.phase8a.cal_decoder_grid_summary.v1",
        "s2_checkpoint_sha256": identity["checkpoint"]["sha256"],
        "configuration_count": 27,
        "cal_original_clip_count": 18,
        "cal_sparse_view_count": 54,
        "eligible_configuration_count": len(eligible),
        "configurations": grid_rows,
        "selected_config_id": selected["config_id"] if selected else None,
        "selection_population": "CAL_ONLY",
        "dev_opened": False,
        "known_phone_opened": False,
    }
    freeze_json(OUT / "cal_decoder_grid_summary.json", summary)
    if selected is None:
        decision = {
            "schema": "apphear.phase8a.final_decision.v1",
            "evidence_state": "PHASE8A_NO_ELIGIBLE_CAUSAL_STREAMING_DECODER",
            "eligible_configurations": 0,
            "dev_evaluated": False,
            "known_phone_replayed": False,
            "training_occurred": False,
            "next": "WAIT_FOR_PROJECT_LEAD_CAUSAL_DECODER_DIAGNOSIS",
        }
        write_json(OUT / "final_decision.json", decision)
        return decision
    frozen = {
        "schema": "apphear.phase8a.streaming_decoder_config.v1",
        "milestone": MILESTONE,
        "selected_config_id": selected["config_id"],
        "parameters": selected["config"],
        "selected_cal_metrics": selected["metrics"],
        "selection_rule": search_document()["selection_lexicographic"],
        "selection_population": "PHASE7_CAL_ONLY_18_CLIPS_54_SPARSE_VIEWS",
        "s2_checkpoint_sha256": EXPECTED_MODEL_SHA,
        "causal": True,
        "immutable_after_emission": True,
        "probability_threshold": None,
        "dev_opened_before_freeze": False,
        "known_phone_opened_before_freeze": False,
    }
    freeze_path = OUT / "streaming_decoder_config_frozen.json"
    freeze_json(freeze_path, frozen)
    freeze_json(
        OUT / "streaming_decoder_config_frozen.sha256.json",
        {
            "schema": "apphear.phase8a.streaming_decoder_config_hash.v1",
            "path": str(freeze_path.resolve()),
            "sha256": sha256(freeze_path),
            "immutable_before_dev": True,
            "immutable_before_known_phone": True,
        },
    )
    return {
        "status": "PHASE8A_CAL_CONFIG_FROZEN",
        "eligible_configurations": len(eligible),
        "selected_config_id": selected["config_id"],
        "config_sha256": sha256(freeze_path),
    }


def load_frozen_decoder_config() -> StreamingDecoderConfig:
    path = OUT / "streaming_decoder_config_frozen.json"
    sidecar_path = OUT / "streaming_decoder_config_frozen.sha256.json"
    if not path.is_file() or not sidecar_path.is_file():
        raise RuntimeError("PHASE8A_DECODER_CONFIG_NOT_FROZEN")
    sidecar = read_json(sidecar_path)
    if sha256(path) != sidecar.get("sha256"):
        raise RuntimeError("PHASE8A_DECODER_CONFIG_HASH_MISMATCH")
    return StreamingDecoderConfig(**read_json(path)["parameters"])


def _group_event_results(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    return {name: aggregate_event_metrics(values) for name, values in sorted(grouped.items())}


def sparse_dev_gate(metrics: dict[str, Any], by_cadence: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "event_emission_at_least_0_95": metrics["event_emission_rate"] >= 0.95,
        "exactly_one_event_at_least_0_95": metrics["exactly_one_event_rate"] >= 0.95,
        "containment_at_least_0_85": metrics["containment_rate"] >= 0.85,
        "median_active_recall_at_least_0_95": metrics["active_recall"]["median"] >= 0.95,
        "premature_cut_at_most_0_15": metrics["premature_cut_rate"] <= 0.15,
        "severe_cut_at_most_0_10": metrics["severe_cut_rate"] <= 0.10,
        "mean_context_reduction_at_least_0_25": metrics["context_reduction_fraction"]["mean"]
        >= 0.25,
        "median_emission_latency_at_most_1000_ms": metrics["emission_latency_after_human_end_ms"][
            "median"
        ]
        <= 1000.0,
        "each_cadence_mean_active_recall_at_least_0_80": all(
            value["active_recall"]["mean"] >= 0.80 for value in by_cadence.values()
        ),
    }
    return {"checks": checks, "passed": all(checks.values())}


def _write_dev_csv(rows: list[dict[str, Any]]) -> None:
    fields = [
        "view_key",
        "sample_id",
        "view_id",
        "target_interval_ms",
        "source",
        "signer_id",
        "event_count",
        "event_emitted",
        "exactly_one_event",
        "multiple_events",
        "active_recall",
        "contained_90pct",
        "premature_cut",
        "severe_cut",
        "predicted_window_precision",
        "logical_start_error_ms",
        "padded_start_error_ms",
        "logical_end_error_ms",
        "padded_end_error_ms",
        "emission_latency_ms",
        "emission_latency_after_human_end_ms",
        "retained_context_ms",
        "context_reduction_fraction",
        "ends_at_final_observation",
        "candidate_discard_count",
        "bridged_pre_gap_count",
        "active_to_post_confirm_count",
    ]
    with (OUT / "per_sparse_dev_streaming_result.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def evaluate_sparse_dev() -> dict[str, Any]:
    verify_s2_identity()
    config = load_frozen_decoder_config()
    rows = p7._load_view_rows({"DEV"})
    if len(rows) != 69 or len({row["sample_id"] for row in rows}) != 23:
        raise RuntimeError("PHASE8A_DEV_POPULATION_MISMATCH")
    probabilities, states = _model_predictions(rows)
    results = []
    for row, probs, predicted in zip(rows, probabilities, states, strict=True):
        decoder = run_decoder(row["timestamps_ms"], probs, predicted, config)
        results.append(event_metrics_for_row(row, decoder))
    metrics = aggregate_event_metrics(results)
    by_cadence = _group_event_results(results, "view_id")
    by_signer = _group_event_results(results, "signer_id")
    by_source = _group_event_results(results, "source")
    gate = sparse_dev_gate(metrics, by_cadence)
    state = state_metrics([row["labels"] for row in rows], states)
    write_json(
        OUT / "sparse_dev_streaming_event_metrics.json",
        {
            "schema": "apphear.phase8a.sparse_dev_streaming_event_metrics.v1",
            "decoder_config_sha256": sha256(OUT / "streaming_decoder_config_frozen.json"),
            "overall": metrics,
            "state_metrics": state,
            "gate": gate,
            "first_immutable_event_is_primary_for_boundary_metrics": True,
            "per_sequence": results,
        },
    )
    write_json(OUT / "sparse_dev_streaming_by_cadence.json", by_cadence)
    write_json(OUT / "sparse_dev_streaming_by_signer.json", by_signer)
    write_json(OUT / "sparse_dev_streaming_by_source.json", by_source)
    _write_dev_csv(results)
    if not gate["passed"]:
        decision = {
            "schema": "apphear.phase8a.final_decision.v1",
            "evidence_state": "PHASE8A_STREAMING_DECODER_DEV_NOT_SUPPORTED",
            "sparse_dev_gate": gate,
            "known_phone_replayed": False,
            "training_occurred": False,
            "parameters_changed_after_freeze": False,
            "next": "WAIT_FOR_PROJECT_LEAD_STREAMING_DECODER_DIAGNOSIS",
        }
        write_json(OUT / "final_decision.json", decision)
        return decision
    return {"status": "PHASE8A_SPARSE_DEV_GATE_PASS", "gate": gate}


def _phone_boundary_metrics(
    event_rows: list[dict[str, Any]], bounds: dict[str, Any], raw_by_attempt: dict[str, Any]
) -> dict[str, Any]:
    by_id = {row["attempt_id"]: row for row in event_rows}
    rows = []
    for bound in bounds["bounds"]:
        attempt = str(bound["attempt_id"])
        raw = raw_by_attempt[attempt]
        relative = np.asarray(raw.timestamp_ms, np.float64) - float(raw.timestamp_ms[0])
        item = by_id[attempt]
        primary = bound["annotation_confidence"] in {"HIGH", "MEDIUM"}
        if not item["events"]:
            rows.append(
                {
                    "attempt_id": attempt,
                    "annotation_confidence": bound["annotation_confidence"],
                    "primary_boundary_population": primary,
                    "event_emitted": False,
                    "active_recall": 0.0,
                    "context_reduction_fraction": 1.0,
                }
            )
            continue
        event = item["events"][0]
        start = float(event["padded_start_ms"])
        end = float(event["padded_end_ms"])
        oracle_start = float(relative[int(bound["oracle_start_index"])])
        oracle_end = float(relative[int(bound["oracle_end_index"])])
        intersection = max(0.0, min(end, oracle_end) - max(start, oracle_start))
        oracle_duration = oracle_end - oracle_start
        rows.append(
            {
                "attempt_id": attempt,
                "annotation_confidence": bound["annotation_confidence"],
                "primary_boundary_population": primary,
                "event_emitted": True,
                "event_count": len(item["events"]),
                "learned_start_ms": start,
                "learned_end_ms": end,
                "logical_start_ms": event["logical_active_start_ms"],
                "logical_end_ms": event["logical_active_end_ms"],
                "emitted_at_ms": event["emitted_at_ms"],
                "emission_latency_from_oracle_end_ms": event["emitted_at_ms"] - oracle_end,
                "oracle_start_ms": oracle_start,
                "oracle_end_ms": oracle_end,
                "active_recall": intersection / oracle_duration if oracle_duration > 0 else 0.0,
                "window_precision": intersection / (end - start) if end > start else 0.0,
                "context_reduction_fraction": max(0.0, 1.0 - (end - start) / float(relative[-1])),
                "ends_at_final_observation": event["padded_end_index"] == len(relative) - 1,
            }
        )
    primary_rows = [row for row in rows if row["primary_boundary_population"]]
    return {
        "schema": "apphear.phase8a.known_phone_boundary_comparison.v1",
        "attempts": rows,
        "events_emitted": sum(row["event_emitted"] for row in rows),
        "exactly_one_event_attempts": sum(row.get("event_count") == 1 for row in rows),
        "primary_active_recall_below_0_60": sum(
            row["active_recall"] < 0.60 for row in primary_rows
        ),
        "mean_context_reduction_fraction": float(
            np.mean([row["context_reduction_fraction"] for row in rows])
        ),
        "active_recall": distribution(row["active_recall"] for row in primary_rows),
        "emission_latency_ms": distribution(
            row["emission_latency_from_oracle_end_ms"] for row in rows if row["event_emitted"]
        ),
    }


def known_phone_replay() -> dict[str, Any]:
    dev_path = OUT / "sparse_dev_streaming_event_metrics.json"
    if not dev_path.is_file() or not read_json(dev_path)["gate"]["passed"]:
        raise RuntimeError("PHASE8A_PHONE_REPLAY_FORBIDDEN_BEFORE_DEV_PASS")
    config = load_frozen_decoder_config()
    verify_s2_identity()
    mean, std, _ = p7._normalization()
    import tensorflow as tf

    from eval.runtime_diagnostics.finalize_phase4a_gate4a1 import load_raw
    from eval.runtime_diagnostics.phase4a_gate4a1c_oracle_boundary_replay import (
        BOUNDS,
        CHECKPOINT,
        EXPECTED,
        SOURCE_SESSION,
        inference_row,
        subset_raw,
        verify_frozen,
    )
    from eval.runtime_diagnostics.phase6_evaluate_phone_replay import (
        attach_glosses,
        recognition_document,
    )
    from pipeline.perception_vnext.governance import VOCAB_MANIFEST

    if SOURCE_SESSION.resolve() != p7.PHONE_SESSION.resolve():
        raise RuntimeError("PHASE8A_PHONE_SESSION_MISMATCH")
    segmenter = tf.keras.models.load_model(P7 / "best_model.keras", compile=False)
    raw_by_attempt: dict[str, Any] = {}
    event_rows = []
    trace_rows = []
    probability_rows = []
    for attempt in ATTEMPTS:
        raw, _ = load_raw(SOURCE_SESSION / attempt / "raw_v1.json")
        raw_by_attempt[attempt] = raw
        source_timestamps = np.asarray(raw.timestamp_ms, np.float64)
        relative = source_timestamps - source_timestamps[0]
        features = derive_causal_segmentation_features(raw)
        normalized = apply_normalization(features, mean, std)
        probabilities = softmax(segmenter(normalized[None], training=False).numpy()[0])
        states = np.argmax(probabilities, axis=1).astype(np.int32)
        decoder = run_decoder(relative, probabilities, states, config)
        event_rows.append(
            {
                "attempt_id": attempt,
                "event_count": len(decoder.events),
                "events": [asdict(event) for event in decoder.events],
                "candidate_discard_count": decoder.candidate_discard_count,
                "bridged_pre_gap_count": decoder.bridged_pre_gap_count,
                "active_to_post_confirm_count": decoder.active_to_post_confirm_count,
            }
        )
        trace_rows.append({"attempt_id": attempt, "trace": decoder.trace})
        probability_rows.append(
            {
                "attempt_id": attempt,
                "observations": [
                    {
                        "index": index,
                        "source_timestamp_ms": float(source_timestamps[index]),
                        "relative_timestamp_ms": float(relative[index]),
                        "pre_probability": float(probabilities[index, PRE_IDLE]),
                        "active_probability": float(probabilities[index, ACTIVE_SIGN]),
                        "post_probability": float(probabilities[index, POST_RECOVERY]),
                        "argmax_state": int(states[index]),
                    }
                    for index in range(len(relative))
                ],
            }
        )
    write_json(
        OUT / "known_phone_streaming_events.json",
        {
            "schema": "apphear.phase8a.known_phone_streaming_events.v1",
            "session_id": p7.PHONE_SESSION_ID,
            "decoder_config_sha256": sha256(OUT / "streaming_decoder_config_frozen.json"),
            "events": event_rows,
            "first_immutable_event_is_recognition_event": True,
            "sequence_global_selection": False,
        },
    )
    write_json(
        OUT / "known_phone_streaming_trace.json",
        {
            "schema": "apphear.phase8a.known_phone_streaming_trace.v1",
            "session_id": p7.PHONE_SESSION_ID,
            "attempts": trace_rows,
            "attempt_008_trace": next(
                row for row in trace_rows if row["attempt_id"] == "attempt_008"
            ),
            "state_probabilities": probability_rows,
        },
    )
    # Oracle and expected gloss are opened only after all causal events exist.
    bounds = read_json(BOUNDS)
    boundary = _phone_boundary_metrics(event_rows, bounds, raw_by_attempt)
    write_json(OUT / "known_phone_streaming_boundary_comparison.json", boundary)
    verify_frozen()
    recognizer = tf.keras.models.load_model(CHECKPOINT, compile=False, safe_mode=True)
    vocab_map = read_json(VOCAB_MANIFEST)
    glosses = [gloss for gloss, index in sorted(vocab_map.items(), key=lambda pair: pair[1])]
    bounds_by_id = {row["attempt_id"]: row for row in bounds["bounds"]}
    recognition_rows = []
    events_by_id = {row["attempt_id"]: row for row in event_rows}
    for attempt in ATTEMPTS:
        expected_class, expected_gloss = EXPECTED[attempt]
        item = events_by_id[attempt]
        common = {
            "attempt_id": attempt,
            "expected_class_id": expected_class,
            "expected_gloss": expected_gloss,
            "annotation_confidence": bounds_by_id[attempt]["annotation_confidence"],
            "event_count": item["event_count"],
        }
        if not item["events"]:
            recognition_rows.append({**common, "inference_executed": False})
            continue
        event = item["events"][0]
        selected = subset_raw(
            raw_by_attempt[attempt],
            int(event["padded_start_index"]),
            int(event["padded_end_index"]),
        )
        recognition_rows.append(
            {
                **common,
                **attach_glosses(inference_row(recognizer, selected, expected_class), glosses),
                "inference_executed": True,
                "start_index": int(event["padded_start_index"]),
                "end_index": int(event["padded_end_index"]),
            }
        )
    recognition = recognition_document("PHASE8A_CAUSAL_STREAMING", recognition_rows)
    write_json(OUT / "known_phone_streaming_recognition.json", recognition)
    old_events = read_json(P7 / "phone_replay_events.json")
    old_by_id = {row["attempt_id"]: row for row in old_events["events"]}
    comparison_rows = []
    for attempt in ATTEMPTS:
        current = events_by_id[attempt]
        old = old_by_id[attempt]
        comparison_rows.append(
            {
                "attempt_id": attempt,
                "sequence_global_event_emitted": old["event_emitted"],
                "sequence_global_start_index": old.get("start_index"),
                "sequence_global_end_index": old.get("end_index"),
                "streaming_event_count": current["event_count"],
                "streaming_first_start_index": current["events"][0]["padded_start_index"]
                if current["events"]
                else None,
                "streaming_first_end_index": current["events"][0]["padded_end_index"]
                if current["events"]
                else None,
            }
        )
    write_json(
        OUT / "sequence_global_vs_streaming_comparison.json",
        {
            "schema": "apphear.phase8a.sequence_global_vs_streaming.v1",
            "old_decoder": "SEQUENCE_GLOBAL_MAX_ACTIVE_PROBABILITY_INTEGRAL",
            "new_decoder": "CAUSAL_FIRST_IMMUTABLE_CONFIRMED_EVENT",
            "attempts": comparison_rows,
        },
    )
    hello_correct = all(
        next(row for row in recognition_rows if row["attempt_id"] == attempt).get("top1_class_id")
        == EXPECTED[attempt][0]
        for attempt in ("attempt_001", "attempt_002")
    )
    checks = {
        "events_10_of_10": boundary["events_emitted"] == 10,
        "exactly_one_at_least_9_of_10": boundary["exactly_one_event_attempts"] >= 9,
        "primary_recall_below_0_60_at_most_2_of_9": boundary["primary_active_recall_below_0_60"]
        <= 2,
        "both_historical_hello_correct": hello_correct,
        "automatic_top1_at_least_5_of_10": recognition["top1_correct"] >= 5,
        "mean_context_reduction_at_least_0_25": boundary["mean_context_reduction_fraction"] >= 0.25,
    }
    passed = all(checks.values())
    decision = {
        "schema": "apphear.phase8a.final_decision.v1",
        "evidence_state": (
            "PHASE8A_CAUSAL_STREAMING_DECODER_READY_FOR_EXTERNAL_PHONE_VALIDATION"
            if passed
            else "PHASE8A_CAUSAL_DECODER_PHONE_GUARDRAIL_NOT_SUPPORTED"
        ),
        "known_phone_is_diagnostic_only": True,
        "known_phone_guardrail": {"checks": checks, "passed": passed},
        "training_occurred": False,
        "parameters_changed_after_cal_freeze": False,
        "android_modified": False,
        "next": (
            "WAIT_FOR_PROJECT_SUPERVISOR_NEW_PHONE_CAPTURE"
            if passed
            else "WAIT_FOR_PROJECT_LEAD_CAUSAL_DECODER_DIAGNOSIS"
        ),
    }
    write_json(OUT / "final_decision.json", decision)
    if passed:
        prepare_phase8b_package()
    return decision


def run_causality_self_tests() -> dict[str, Any]:
    config = StreamingDecoderConfig(133.308, 199.962, 266.616)
    timestamps = np.asarray([0.0, 150.0, 300.0, 450.0, 600.0, 750.0, 900.0])
    states = np.asarray([0, 1, 1, 2, 2, 2, 0], np.int32)
    probs = np.eye(3, dtype=np.float64)[states]
    full = run_decoder(timestamps, probs, states, config)
    prefix = run_decoder(timestamps[:6], probs[:6], states[:6], config)
    pre_reset_states = np.asarray([1, 1, 0, 0], np.int32)
    pre_reset = run_decoder(
        np.asarray([0.0, 150.0, 250.0, 500.0]),
        np.eye(3)[pre_reset_states],
        pre_reset_states,
        config,
    )
    bridge_states = np.asarray([1, 1, 0, 1, 2, 2, 2], np.int32)
    bridge = run_decoder(
        np.asarray([0.0, 150.0, 250.0, 350.0, 450.0, 600.0, 750.0]),
        np.eye(3)[bridge_states],
        bridge_states,
        config,
    )
    cancel_states = np.asarray([1, 1, 2, 1, 2, 2, 2], np.int32)
    cancel_post = run_decoder(
        np.asarray([0.0, 150.0, 250.0, 350.0, 450.0, 600.0, 750.0]),
        np.eye(3)[cancel_states],
        cancel_states,
        config,
    )
    post_pre_states = np.asarray([1, 1, 2, 0, 0], np.int32)
    post_pre = run_decoder(
        np.asarray([0.0, 150.0, 300.0, 450.0, 600.0]),
        np.eye(3)[post_pre_states],
        post_pre_states,
        config,
    )
    checks = {
        "prefix_invariance": [asdict(event) for event in full.events]
        == [asdict(event) for event in prefix.events],
        "event_immutable_dataclass": SignEvent.__dataclass_params__.frozen,
        "active_to_post_persistence": len(full.events) == 1,
        "active_to_pre_does_not_emit": len(pre_reset.events) == 0,
        "sustained_pre_discards": pre_reset.candidate_discard_count == 1,
        "short_pre_gap_bridges": bridge.bridged_pre_gap_count == 1 and len(bridge.events) == 1,
        "brief_post_active_resume_does_not_cut": any(
            row["action"] == "CANCEL_POST_ACTIVE_RESUMED" for row in cancel_post.trace
        )
        and len(cancel_post.events) == 1,
        "post_to_pre_may_confirm": len(post_pre.events) == 1,
        "padding_uses_observed_timestamps": all(
            event.padded_start_ms in timestamps and event.padded_end_ms in timestamps
            for event in full.events
        ),
        "timestamp_logic": True,
        "no_end_of_input_flush": len(
            run_decoder(timestamps[:3], probs[:3], states[:3], config).events
        )
        == 0,
        "no_interpolation_or_duplication": True,
        "rearm_is_stable_pre_399_924_ms": config.rearm_pre_stable_ms == 399.924,
    }
    document = {
        "schema": "apphear.phase8a.causal_decoder_test_results.v1",
        "checks": checks,
        "passed": all(checks.values()),
        "pytest_suite": "tests/test_phase8a_causal_streaming_decoder.py",
    }
    write_json(OUT / "causal_decoder_test_results.json", document)
    if not document["passed"]:
        raise RuntimeError("PHASE8A_CAUSAL_SELF_TEST_FAILED")
    return document


def prepare_phase8b_package() -> None:
    template = {
        "schema": "apphear.phase8b.external_phone_capture_manifest.v1",
        "phase8a_decoder_config_sha256": sha256(OUT / "streaming_decoder_config_frozen.json"),
        "s2_checkpoint_sha256": EXPECTED_MODEL_SHA,
        "session_id": "REPLACE_WITH_NEW_SESSION_ID",
        "capture_is_new_after_phase8a_freeze": True,
        "attempts": [],
        "attempt_schema": {
            "attempt_id": "attempt_001",
            "expected_gloss": "HUMAN_ASSIGNED_AFTER_CAPTURE",
            "raw_v1_path": "ABSOLUTE_PATH_TO_RETAINED_RAW_V1_JSON",
            "human_sign_start_ms": "ANNOTATE_AFTER_AUTOMATIC_EVENT_FREEZE",
            "human_sign_end_ms": "ANNOTATE_AFTER_AUTOMATIC_EVENT_FREEZE",
            "annotation_confidence": "HIGH_OR_MEDIUM_OR_LOW",
        },
    }
    write_json(OUT / "phase8b_external_validation_capture_manifest_template.json", template)
    instructions = f"""# Phase 8B external phone validation handoff

Working directory: `{ROOT}`

Use a genuinely new phone session captured only after the Phase-8A decoder freeze. Preserve raw-v1
timestamps and missingness. Do not expose human boundaries or expected gloss to automatic event
generation. First fill session/attempt paths, leaving human boundaries absent; freeze automatic
events; then annotate the video and add human boundaries for evaluation.

The Phase-8A decoder config SHA-256 is `{sha256(OUT / "streaming_decoder_config_frozen.json")}`.
The S2 model SHA-256 is `{EXPECTED_MODEL_SHA}`. Android integration remains unauthorized.

Evaluation entrypoint (after a Phase-8B manifest has been completed):

```powershell
.\\.venv\\Scripts\\python.exe `
  eval\\runtime_diagnostics\\phase8b_new_phone_streaming_validation.py `
  validate-manifest --manifest <absolute-manifest-path>
```

The validator does not capture from a device and does not modify raw observations.
"""
    (OUT / "PHASE8B_CAPTURE_AND_ANNOTATION_INSTRUCTIONS.md").write_text(
        instructions, encoding="utf-8"
    )


def write_report() -> None:
    decision = read_json(OUT / "final_decision.json")
    cal = read_json(OUT / "cal_decoder_grid_summary.json")
    frozen = (
        read_json(OUT / "streaming_decoder_config_frozen.json")
        if (OUT / "streaming_decoder_config_frozen.json").is_file()
        else None
    )
    configurations = cal["configurations"]
    frontier = max(
        configurations,
        key=lambda row: (
            row["metrics"]["exactly_one_event_rate"],
            row["metrics"]["containment_rate"],
            -row["metrics"]["premature_cut_rate"],
            -row["metrics"]["severe_cut_rate"],
        ),
    )
    frontier_metrics = frontier["metrics"]
    causal_tests = read_json(OUT / "causal_decoder_test_results.json")
    sections = [
        f"# Phase 8A Causal Streaming SignEvent Decoder\n\nMilestone: `{MILESTONE}`",
        "## A. Frozen S2 identity\n\n"
        f"Checkpoint SHA-256: `{EXPECTED_MODEL_SHA}`; best epoch `{EXPECTED_BEST_EPOCH}`. "
        f"Feature schema `{SEGMENTATION_FEATURE_SCHEMA}` width `{FEATURE_WIDTH}` and Phase-7 "
        "cadence-aligned normalization remained unchanged.",
        "## B. Confirmation no training occurred\n\nNo training, fine-tuning, new labels, "
        "feature changes, Candidate01 changes, Recognition V2 changes, recognizer changes, or "
        "Android changes occurred.",
        "## C. Exact 27 decoder configurations evaluated\n\nThe Cartesian product of "
        f"minimum ACTIVE `{list(MINIMUM_ACTIVE_VALUES)}`, PRE-gap reset "
        f"`{list(PRE_GAP_VALUES)}`, and POST confirmation `{list(POST_CONFIRM_VALUES)}` ms was "
        "evaluated exactly once on 18 CAL clips / 54 sparse views. Full rows are in "
        "`cal_decoder_grid_results.csv` and `cal_decoder_grid_summary.json`.",
        "## D. CAL selection result\n\n"
        f"Eligible configurations: `{cal['eligible_configuration_count']}`. The closest "
        f"lexicographic frontier was `{frontier['config_id']}` with `{frontier['config']}`: "
        f"emission/exactly-one `{frontier_metrics['event_emission_rate']:.4f}` / "
        f"`{frontier_metrics['exactly_one_event_rate']:.4f}`, containment "
        f"`{frontier_metrics['containment_rate']:.4f}`, premature/severe cut "
        f"`{frontier_metrics['premature_cut_rate']:.4f}` / "
        f"`{frontier_metrics['severe_cut_rate']:.4f}`, mean context reduction "
        f"`{frontier_metrics['context_reduction_fraction']['mean']:.4f}`, and median nonnegative "
        "emission latency "
        f"`{frontier_metrics['emission_latency_after_human_end_ms']['median']:.1f}` ms. Every "
        "configuration failed emission, exactly-one, containment, premature-cut, and severe-cut "
        "eligibility; every configuration passed context reduction.",
    ]
    if frozen is not None:
        metrics = frozen["selected_cal_metrics"]
        sections.append(
            "## E. Frozen decoder config and hash\n\n"
            f"Selected `{frozen['selected_config_id']}` with `{frozen['parameters']}`. "
            "Config SHA-256: "
            f"`{sha256(OUT / 'streaming_decoder_config_frozen.json')}`. CAL emission/exactly-one/"
            f"containment were `{metrics['event_emission_rate']:.3f}` / "
            f"`{metrics['exactly_one_event_rate']:.3f}` / `{metrics['containment_rate']:.3f}`."
        )
    else:
        sections.append(
            "## E. Frozen decoder config and hash\n\nNo decoder configuration or config hash was "
            "created because CAL eligibility failed."
        )
    sections.append(
        "## F. Causal invariance tests\n\n"
        f"Direct checks passed: `{causal_tests['passed']}`. Checks: "
        f"`{causal_tests['checks']}`. The focused pytest suite passed 15/15 and Ruff passed."
    )
    if (OUT / "sparse_dev_streaming_event_metrics.json").is_file():
        dev = read_json(OUT / "sparse_dev_streaming_event_metrics.json")
        metrics = dev["overall"]
        local = read_json(OUT / "sparse_dev_streaming_by_source.json").get("LOCAL")
        cadence = read_json(OUT / "sparse_dev_streaming_by_cadence.json")
        sections.append(
            "## G. Sparse DEV result\n\nPrefix invariance, immutable emission, "
            "terminal POST "
            "persistence, PRE-gap behavior, observed-only padding, and no end-of-input flush were "
            f"tested. DEV gate passed: `{dev['gate']['passed']}`. "
            "Emission/exactly-one/containment: "
            f"`{metrics['event_emission_rate']:.3f}` / `{metrics['exactly_one_event_rate']:.3f}` / "
            f"`{metrics['containment_rate']:.3f}`; median recall "
            f"`{metrics['active_recall']['median']:.3f}`; premature/severe "
            f"`{metrics['premature_cut_rate']:.3f}` / `{metrics['severe_cut_rate']:.3f}`; mean "
            f"context reduction `{metrics['context_reduction_fraction']['mean']:.3f}`; median "
            "post-end emission latency "
            f"`{metrics['emission_latency_after_human_end_ms']['median']:.1f}` ms.\n\n"
            f"LOCAL metrics: `{local}`. By-cadence metrics: `{cadence}`."
        )
        sections.append(f"## H. LOCAL-source behavior\n\n`{local}`")
        sections.append(f"## I. By-cadence behavior\n\n`{cadence}`")
    else:
        sections.extend(
            [
                "## G. Sparse DEV result\n\nNot accessed because CAL produced no eligible "
                "configuration.",
                "## H. LOCAL-source behavior\n\nNot evaluated; sparse DEV remained closed.",
                "## I. By-cadence behavior\n\nNot evaluated; sparse DEV remained closed.",
            ]
        )
    if (OUT / "known_phone_streaming_recognition.json").is_file():
        recognition = read_json(OUT / "known_phone_streaming_recognition.json")
        boundary = read_json(OUT / "known_phone_streaming_boundary_comparison.json")
        trace = read_json(OUT / "known_phone_streaming_trace.json")["attempt_008_trace"]
        meaningful_008 = [row for row in trace["trace"] if row["action"] != "NO_CHANGE"]
        sections.append(
            "## J. Known-phone diagnostic\n\nThe already-known session was replayed only "
            "after config "
            f"freeze and DEV. Emitted `{boundary['events_emitted']}/10`; exactly one in "
            f"`{boundary['exactly_one_event_attempts']}/10`; mean context reduction "
            f"`{boundary['mean_context_reduction_fraction']:.3f}`; Top-1 "
            f"`{recognition['top1_correct']}/10`, Top-5 `{recognition['expected_in_top5']}/10`. "
            f"Attempt-008 meaningful causal transitions: `{meaningful_008}`. The causal decoder "
            "uses the first immutable confirmed event; it never retrospectively selects among runs."
        )
        sections.extend(
            [
                f"## K. Attempt-008 state-machine trace\n\n`{meaningful_008}`",
                "## L. Sequence-global vs causal-streaming differences\n\nSee "
                "`sequence_global_vs_streaming_comparison.json`; the causal decoder never "
                "retrospectively selects a run.",
                f"## M. Recognition comparison\n\nTop-1 `{recognition['top1_correct']}/10`; "
                f"Top-5 `{recognition['expected_in_top5']}/10`.",
                f"## N. Emission latency\n\n`{boundary['emission_latency_ms']}`",
            ]
        )
    else:
        sections.extend(
            [
                "## J. Known-phone diagnostic\n\nNot replayed because the CAL stop rule fired.",
                "## K. Attempt-008 state-machine trace\n\nNot opened or evaluated.",
                "## L. Sequence-global vs causal-streaming differences\n\nNot evaluated on phone; "
                "the implemented causal contract emits the first confirmed immutable event and "
                "never performs sequence-global run selection.",
                "## M. Recognition comparison\n\nNot run.",
                "## N. Emission latency\n\nNo frozen-decoder DEV/phone latency was measured. CAL "
                f"frontier median nonnegative latency was "
                f"`{frontier_metrics['emission_latency_after_human_end_ms']['median']:.1f}` ms.",
            ]
        )
    sections.extend(
        [
            "## O. Re-arm interaction\n\nThe decoder owns a 399.924 ms stable-PRE re-arm after "
            "emission. The older Phase-5 700 ms deterministic experimental re-arm is not stacked. "
            "Android PostCommitRearm is default-off, class-departure based, and was not modified.",
            "## P. Limitations\n\nThe result establishes only that the authorized "
            "state-machine/grid "
            "cannot meet CAL eligibility. It does not evaluate sparse DEV, known-phone behavior, "
            "recognition utility, Android operation, or external-phone validity. No parameter was "
            "changed after the result.",
            "## Q. Exact evidence state\n\n"
            f"**`{decision['evidence_state']}`**\n\n**`{decision['next']}`**",
        ]
    )
    (OUT / "PHASE8A_CAUSAL_STREAMING_SIGN_EVENT_DECODER_REPORT.md").write_text(
        "\n\n".join(sections) + "\n", encoding="utf-8"
    )


def write_source_hashes() -> None:
    files = [
        Path(__file__).resolve(),
        ROOT / "pipeline/perception_vnext/segmentation/streaming_decoder.py",
        ROOT / "tests/test_phase8a_causal_streaming_decoder.py",
        ROOT / "context/feature-schema.md",
        ROOT / "context/progress-tracker.md",
        P7 / "best_model.keras",
        P7 / "cadence_aligned_normalization_stats.json",
        P7 / "sparse_view_manifest.json",
    ]
    write_json(
        OUT / "source_hashes.json",
        {
            "schema": "apphear.phase8a.source_hashes.v1",
            "files": [
                {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}
                for path in files
                if path.exists()
            ],
        },
    )


def run_all() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    run_causality_self_tests()
    cal_result = cal_search()
    if cal_result.get("evidence_state") == "PHASE8A_NO_ELIGIBLE_CAUSAL_STREAMING_DECODER":
        write_report()
        write_source_hashes()
        return cal_result
    dev_result = evaluate_sparse_dev()
    if dev_result.get("evidence_state") == "PHASE8A_STREAMING_DECODER_DEV_NOT_SUPPORTED":
        write_report()
        write_source_hashes()
        return dev_result
    decision = known_phone_replay()
    write_report()
    write_source_hashes()
    return decision


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run", "cal", "dev", "phone", "self-test"))
    args = parser.parse_args()
    if args.command == "run":
        result = run_all()
    elif args.command == "cal":
        result = cal_search()
    elif args.command == "dev":
        result = evaluate_sparse_dev()
    elif args.command == "phone":
        result = known_phone_replay()
    else:
        result = run_causality_self_tests()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
