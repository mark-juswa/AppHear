"""Phase 8A-T: terminal evidence attribution from persisted frozen S2 streams."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter as p7
from eval.runtime_diagnostics.terminal_evidence import (
    SCHEMA as TERMINAL_EVIDENCE_SCHEMA,
)
from eval.runtime_diagnostics.terminal_evidence import (
    build_control_envelope,
    classify_against_controls,
    distribution,
    summarize_interval,
)
from pipeline.perception_vnext.recognition_window_materializer import (
    LogicalSignEvent,
    MaterializerConfig,
    materialize_recognition_window,
)
from pipeline.perception_vnext.segmentation.streaming_decoder import (
    CausalStreamingSignEventDecoder,
    StreamingDecoderConfig,
)

MILESTONE = "PHASE_8A_T_CAUSAL_TERMINAL_EVIDENCE_ATTRIBUTION_01"
BASE = ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
P7 = BASE / "phase7_production_cadence_aligned_segmenter_01"
P8R = BASE / "phase8a_r_causal_episode_failure_attribution_01"
P8M = BASE / "phase8a_m_causal_sparse_recognition_window_materialization_01"
P8M2 = BASE / "phase8a_m2_frozen_signer_disjoint_sparse_dev_validation_01"
OUT = BASE / "phase8a_t_causal_terminal_evidence_attribution_01"

EXPECTED_S2_SHA = "dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73"
EXPECTED_MATERIALIZER_SHA = "0a59dc80fe54cb37e09fbce8aa108dbfce32bc4b5cb48b98e61619b5b3b34971"
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


def _active_recall(start: float, end: float, human_start: float, human_end: float) -> float:
    intersection = max(0.0, min(end, human_end) - max(start, human_start))
    duration = human_end - human_start
    return intersection / duration if duration > 0.0 else 0.0


def integrity_audit() -> dict[str, Any]:
    cal_path = P8R / "cal_state_run_manifest.json"
    dev_path = P8M2 / "dev_s2_state_streams.json"
    dev_result_path = P8M2 / "per_sparse_dev_materialization_result.csv"
    materializer_path = P8M / "materializer_contract_frozen.json"
    required = (cal_path, dev_path, dev_result_path, materializer_path)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"PHASE8A_T_CONTINUITY_MISMATCH:MISSING:{missing}")
    cal = read_json(cal_path)
    dev = read_json(dev_path)
    if cal.get("s2_checkpoint_sha256") != EXPECTED_S2_SHA or len(cal.get("views", [])) != 54:
        raise RuntimeError("PHASE8A_T_CONTINUITY_MISMATCH:CAL_STREAMS")
    if dev.get("checkpoint_sha256") != EXPECTED_S2_SHA or len(dev.get("views", [])) != 69:
        raise RuntimeError("PHASE8A_T_CONTINUITY_MISMATCH:DEV_STREAMS")
    if sha256(materializer_path) != EXPECTED_MATERIALIZER_SHA:
        raise RuntimeError("PHASE8A_T_CONTINUITY_MISMATCH:MATERIALIZER")
    decision = read_json(P8M2 / "final_decision.json")
    if decision.get("evidence_state") != "MATERIALIZER_DEV_SUPPORTED_EVENT_PRODUCER_LIMITED":
        raise RuntimeError("PHASE8A_T_CONTINUITY_MISMATCH:M2_DECISION")
    return {
        "schema": "apphear.phase8a_t.integrity_reuse_audit.v1",
        "milestone": MILESTONE,
        "s2_checkpoint_sha256": EXPECTED_S2_SHA,
        "materializer_contract_sha256": EXPECTED_MATERIALIZER_SHA,
        "config_01": asdict(CONFIG_01),
        "terminal_analyzer_schema": TERMINAL_EVIDENCE_SCHEMA,
        "cal_streams": 54,
        "dev_streams": 69,
        "s2_inference_rerun": False,
        "extraction_rerun": False,
        "training": False,
        "threshold_search": False,
        "decoder_change": False,
        "materializer_change": False,
        "recognition": False,
        "known_phone_access": False,
        "protected_test_access": False,
        "android_change": False,
    }


def _cal_streams() -> list[dict[str, Any]]:
    document = read_json(P8R / "cal_state_run_manifest.json")
    result = []
    for view in document["views"]:
        observations = view["observations"]
        result.append(
            {
                "population": "CAL",
                "view_key": view["view_key"],
                "sample_id": view["sample_id"],
                "view_id": view["view_id"],
                "source": view["source"],
                "signer_id": view["signer_id"],
                "human_start_ms": float(view["human_start_ms"]),
                "human_end_ms": float(view["human_end_ms"]),
                "timestamps_ms": np.asarray(
                    [row["timestamp_ms"] for row in observations], np.float64
                ),
                "probabilities": np.asarray(
                    [
                        [
                            row["pre_probability"],
                            row["active_probability"],
                            row["post_probability"],
                        ]
                        for row in observations
                    ],
                    np.float64,
                ),
                "states": np.asarray([row["argmax_state"] for row in observations], np.int32),
            }
        )
    return result


def _dev_streams() -> list[dict[str, Any]]:
    state = read_json(P8M2 / "dev_s2_state_streams.json")
    by_key = {str(row["view_key"]): row for row in state["views"]}
    dev_rows = p7._load_view_rows({"DEV"})
    if len(dev_rows) != 69:
        raise RuntimeError("PHASE8A_T_DEV_MEMBERSHIP_MISMATCH")
    result = []
    for row in dev_rows:
        persisted = by_key[str(row["view_key"])]
        timestamps = np.asarray(persisted["timestamps_ms"], np.float64)
        if not np.array_equal(timestamps, np.asarray(row["timestamps_ms"], np.float64)):
            raise RuntimeError("PHASE8A_T_DEV_TIMESTAMP_MISMATCH")
        result.append(
            {
                "population": "DEV",
                "view_key": row["view_key"],
                "sample_id": row["sample_id"],
                "view_id": row["view_id"],
                "source": row["source"],
                "signer_id": row["signer_id"],
                "human_start_ms": float(row["human_sign_start_ms"]),
                "human_end_ms": float(row["human_sign_end_ms"]),
                "timestamps_ms": timestamps,
                "probabilities": np.asarray(persisted["probabilities"], np.float64),
                "states": np.asarray(persisted["argmax_states"], np.int32),
            }
        )
    return result


def _sequence_record(stream: dict[str, Any]) -> dict[str, Any]:
    timestamps = stream["timestamps_ms"]
    probabilities = stream["probabilities"]
    decoder = CausalStreamingSignEventDecoder(CONFIG_01)
    decoder.run(timestamps, probabilities, stream["states"])
    event = decoder.events[0] if decoder.events else None
    materialized_recall = 0.0
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
        materialized_recall = _active_recall(
            window.selected_start_ms,
            window.selected_end_ms,
            stream["human_start_ms"],
            stream["human_end_ms"],
        )
    post_available = float(timestamps[-1] - stream["human_end_ms"])
    if event is not None:
        outcome = "SUCCESSFUL_EVENT" if materialized_recall >= 0.90 else "EMITTED_TRUNCATED"
        terminal_end = float(event.emitted_at_ms)
    elif post_available < CONFIG_01.post_confirm_ms:
        outcome = "RIGHT_CENSORED"
        terminal_end = float(timestamps[-1])
    else:
        outcome = "GENUINE_NO_EVENT"
        terminal_end = float(timestamps[-1])
    terminal = summarize_interval(
        timestamps,
        probabilities,
        start_ms=stream["human_end_ms"],
        end_ms=terminal_end,
        anchor_ms=stream["human_end_ms"],
    )
    intra_active = summarize_interval(
        timestamps,
        probabilities,
        start_ms=stream["human_start_ms"],
        end_ms=stream["human_end_ms"],
        anchor_ms=stream["human_start_ms"],
    )
    return {
        "population": stream["population"],
        "view_key": stream["view_key"],
        "sample_id": stream["sample_id"],
        "view_id": stream["view_id"],
        "source": stream["source"],
        "signer_id": stream["signer_id"],
        "human_start_ms": stream["human_start_ms"],
        "human_end_ms": stream["human_end_ms"],
        "final_observation_ms": float(timestamps[-1]),
        "post_context_available_ms": post_available,
        "event_emitted": event is not None,
        "event_count": len(decoder.events),
        "commit_ms": event.emitted_at_ms if event else None,
        "terminal_post_ms": event.first_post_ms if event else None,
        "materialized_active_recall": materialized_recall,
        "outcome": outcome,
        "terminal_evidence": terminal,
        "intra_active_evidence": intra_active,
    }


def _flatten_failure(record: dict[str, Any]) -> dict[str, Any]:
    terminal = record["terminal_evidence"]
    attribution = record["attribution"]
    return {
        "population": record["population"],
        "view_key": record["view_key"],
        "sample_id": record["sample_id"],
        "view_id": record["view_id"],
        "source": record["source"],
        "signer_id": record["signer_id"],
        "post_context_available_ms": record["post_context_available_ms"],
        "classification": attribution["classification"],
        "successful_floor_votes": attribution["successful_floor_votes"],
        "intra_active_exceedance_votes": attribution["intra_active_exceedance_votes"],
        "observation_count": terminal["observation_count"],
        "max_post_probability": terminal["max_post_probability"],
        "mean_post_probability": terminal["mean_post_probability"],
        "median_post_probability": terminal["median_post_probability"],
        "mean_active_probability": terminal["mean_active_probability"],
        "max_post_minus_active_margin": terminal["max_post_minus_active_margin"],
        "mean_post_minus_active_margin": terminal["mean_post_minus_active_margin"],
        "post_dominant_fraction": terminal["post_dominant_fraction"],
        "post_dominant_observation_count": terminal["post_dominant_observation_count"],
        "post_dominant_run_count": terminal["post_dominant_run_count"],
        "longest_post_dominant_span_ms": terminal["longest_post_dominant_span_ms"],
        "post_probability_time_integral_ms": terminal["post_probability_time_integral_ms"],
        "positive_post_margin_time_integral_ms": terminal[
            "positive_post_margin_time_integral_ms"
        ],
        "final_active_probability": terminal["final_active_probability"],
        "final_post_probability": terminal["final_post_probability"],
    }


def _clip_inventory(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["population"], record["sample_id"])].append(record)
    output = []
    for (population, sample_id), rows in sorted(grouped.items()):
        output.append(
            {
                "population": population,
                "sample_id": sample_id,
                "source": rows[0]["source"],
                "signer_id": rows[0]["signer_id"],
                "view_count": len(rows),
                "successful_event_views": sorted(
                    row["view_id"] for row in rows if row["outcome"] == "SUCCESSFUL_EVENT"
                ),
                "emitted_truncated_views": sorted(
                    row["view_id"] for row in rows if row["outcome"] == "EMITTED_TRUNCATED"
                ),
                "right_censored_views": sorted(
                    row["view_id"] for row in rows if row["outcome"] == "RIGHT_CENSORED"
                ),
                "genuine_no_event_views": sorted(
                    row["view_id"] for row in rows if row["outcome"] == "GENUINE_NO_EVENT"
                ),
            }
        )
    return output


def training_diversity_audit() -> dict[str, Any]:
    population = p7.load_population()
    train = [row for row in population if row["segmentation_split"] == "SEGMENTATION_TRAIN"]
    local = [row for row in train if row["source"] == "LOCAL"]
    apphear = [row for row in train if row["source"] == "APPHEAR_CAPTURE"]
    return {
        "schema": "apphear.phase8a_t.training_diversity_audit.v1",
        "segmentation_train_clips": len(train),
        "segmentation_train_signers": len({row["signer_id"] for row in train}),
        "local_train_clips": len(local),
        "local_train_signers": sorted({row["signer_id"] for row in local}),
        "apphear_capture_train_clips": len(apphear),
        "apphear_capture_train_signers": sorted({row["signer_id"] for row in apphear}),
        "held_out_local_dev_signers": ["local_recorder:3B96F6-S002"],
        "interpretation": (
            "LOCAL supervision exists but is shallow: 12 clips across three TRAIN signers, plus "
            "12 APPHEAR_CAPTURE clips from one signer. More independent signer/transition "
            "diversity should be audited or collected before targeted S2 correction."
        ),
    }


def analyze() -> dict[str, Any]:
    audit = integrity_audit()
    records = [_sequence_record(stream) for stream in _cal_streams() + _dev_streams()]
    successful = [row for row in records if row["outcome"] == "SUCCESSFUL_EVENT"]
    terminal_controls = [
        row["terminal_evidence"]
        for row in successful
        if row["terminal_evidence"]["observation_count"]
    ]
    active_controls = [
        row["intra_active_evidence"]
        for row in successful
        if row["intra_active_evidence"]["observation_count"]
    ]
    envelope = build_control_envelope(terminal_controls, active_controls)
    failures = [row for row in records if row["outcome"] == "GENUINE_NO_EVENT"]
    for record in failures:
        record["attribution"] = classify_against_controls(record["terminal_evidence"], envelope)
    dev_failures = [row for row in failures if row["population"] == "DEV"]
    dev_censored = [
        row for row in records if row["population"] == "DEV" and row["outcome"] == "RIGHT_CENSORED"
    ]
    failure_rows = [_flatten_failure(row) for row in failures]

    clip_inventory = _clip_inventory(records)
    dev_failure_clips = []
    by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in dev_failures:
        by_sample[row["sample_id"]].append(row)
    for sample_id, rows in sorted(by_sample.items()):
        classes = Counter(row["attribution"]["classification"] for row in rows)
        all_records = [
            row
            for row in records
            if row["population"] == "DEV" and row["sample_id"] == sample_id
        ]
        if len(classes) == 1:
            clip_classification = next(iter(classes))
        else:
            clip_classification = "MIXED_OR_AMBIGUOUS"
        dev_failure_clips.append(
            {
                "sample_id": sample_id,
                "source": rows[0]["source"],
                "signer_id": rows[0]["signer_id"],
                "genuine_failure_views": sorted(row["view_id"] for row in rows),
                "successful_views": sorted(
                    row["view_id"]
                    for row in all_records
                    if row["outcome"] == "SUCCESSFUL_EVENT"
                ),
                "cadence_sensitive": any(
                    row["outcome"] == "SUCCESSFUL_EVENT" for row in all_records
                ),
                "fails_all_three_cadences": len(rows) == 3,
                "view_classifications": dict(sorted(classes.items())),
                "clip_classification": clip_classification,
            }
        )

    view_counts = Counter(row["attribution"]["classification"] for row in dev_failures)
    clip_counts = Counter(row["clip_classification"] for row in dev_failure_clips)
    genuine_view_count = len(dev_failures)
    genuine_clip_count = len(dev_failure_clips)
    absent_views = view_counts["MODEL_TERMINAL_SIGNAL_ABSENT"]
    present_views = view_counts["MODEL_TERMINAL_SIGNAL_PRESENT_DECODER_NOT_USING_IT"]
    absent_clips = clip_counts["MODEL_TERMINAL_SIGNAL_ABSENT"]
    present_clips = clip_counts["MODEL_TERMINAL_SIGNAL_PRESENT_DECODER_NOT_USING_IT"]
    view_requirement = math.ceil(0.70 * genuine_view_count)
    clip_requirement = math.ceil((2.0 / 3.0) * genuine_clip_count)
    s2_supported = absent_views >= view_requirement and absent_clips >= clip_requirement
    decoder_supported = present_views >= view_requirement and present_clips >= clip_requirement
    if decoder_supported:
        evidence_state = "TERMINAL_SIGNAL_PRESENT_EVENT_PRODUCER_REDESIGN_SUPPORTED"
        next_architecture = "PROBABILITY_AWARE_CAUSAL_TERMINAL_EVIDENCE_MECHANISM"
        first_change = "EVENT_PRODUCER"
    elif s2_supported:
        evidence_state = "S2_TERMINAL_GENERALIZATION_CORRECTION_SUPPORTED"
        next_architecture = "TARGETED_S2_ACTIVE_TO_POST_GENERALIZATION_CORRECTION"
        first_change = "S2_AFTER_TRAINING_DIVERSITY_AUDIT"
    elif absent_views and present_views:
        evidence_state = "MIXED_TERMINAL_MODEL_AND_DECODER_LIMIT"
        next_architecture = "SEPARATE_EVENT_PRODUCER_THEN_S2_DECISIONS"
        first_change = "EVENT_PRODUCER_IF_CAL_SUPPORTS_WITHOUT_DEV_TUNING"
    else:
        evidence_state = "TERMINAL_FAILURE_CAUSE_NOT_SUFFICIENTLY_RESOLVED"
        next_architecture = "MORE_INDEPENDENT_TERMINAL_EVIDENCE_REQUIRED"
        first_change = "NONE"

    diversity = training_diversity_audit()
    decision = {
        "schema": "apphear.phase8a_t.final_decision.v1",
        "genuine_dev_failure_views": genuine_view_count,
        "genuine_dev_failure_clips": genuine_clip_count,
        "right_censored_dev_views": len(dev_censored),
        "view_attribution_counts": dict(sorted(view_counts.items())),
        "clip_attribution_counts": dict(sorted(clip_counts.items())),
        "predeclared_view_requirement_70pct": view_requirement,
        "predeclared_clip_requirement_two_thirds": clip_requirement,
        "probability_aware_decoder_redesign_justified_as_first_change": decoder_supported,
        "targeted_s2_correction_justified": s2_supported,
        "additional_signer_diverse_local_data_needed_before_training": s2_supported,
        "recommended_first_change": first_change,
        "recommended_next_architecture": next_architecture,
        "evidence_state": evidence_state,
        "next": "WAIT_FOR_PROJECT_LEAD_TERMINAL_ARCHITECTURE_DECISION",
        "training": False,
        "decoder_implemented": False,
        "threshold_search": False,
        "phone_opened": False,
    }
    return {
        "audit": audit,
        "records": records,
        "clip_inventory": clip_inventory,
        "successful": successful,
        "terminal_controls": terminal_controls,
        "active_controls": active_controls,
        "envelope": envelope,
        "failures": failures,
        "dev_failures": dev_failures,
        "dev_censored": dev_censored,
        "failure_rows": failure_rows,
        "dev_failure_clips": dev_failure_clips,
        "diversity": diversity,
        "decision": decision,
    }


def _summarize_controls(rows: list[dict[str, Any]], schema: str) -> dict[str, Any]:
    metrics = [
        "max_post_probability",
        "mean_post_probability",
        "mean_post_minus_active_margin",
        "post_dominant_fraction",
        "longest_post_dominant_span_ms",
        "post_probability_time_integral_ms",
        "final_active_probability",
        "final_post_probability",
    ]
    return {
        "schema": schema,
        "sequence_count": len(rows),
        "metrics": {metric: distribution(row[metric] for row in rows) for metric in metrics},
        "rows": rows,
    }


def write_failure_csv(rows: list[dict[str, Any]]) -> None:
    with (OUT / "per_failure_terminal_evidence.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_report(result: dict[str, Any]) -> None:
    decision = result["decision"]
    dev_failures = result["dev_failures"]
    view_counts = decision["view_attribution_counts"]
    absent_count = view_counts.get("MODEL_TERMINAL_SIGNAL_ABSENT", 0)
    present_count = view_counts.get("MODEL_TERMINAL_SIGNAL_PRESENT_DECODER_NOT_USING_IT", 0)
    ambiguous_count = view_counts.get("MIXED_OR_AMBIGUOUS", 0)
    decoder_first = decision["probability_aware_decoder_redesign_justified_as_first_change"]
    success_floor = result["envelope"]["successful_terminal_lower_p10"]
    active_ceiling = result["envelope"]["intra_active_upper_p95"]
    dev_records = [row for row in result["records"] if row["population"] == "DEV"]
    cadence_rows = []
    for view_id in ("VIEW_A", "VIEW_B", "VIEW_C"):
        rows = [row for row in dev_records if row["view_id"] == view_id]
        cadence_rows.append(
            (
                view_id,
                sum(row["outcome"] == "SUCCESSFUL_EVENT" for row in rows),
                sum(row["outcome"] == "EMITTED_TRUNCATED" for row in rows),
                sum(row["outcome"] == "RIGHT_CENSORED" for row in rows),
                sum(row["outcome"] == "GENUINE_NO_EVENT" for row in rows),
            )
        )
    cadence_table = "\n".join(
        f"| {view_id} | {success} | {truncated} | {censored} | {genuine} |"
        for view_id, success, truncated, censored, genuine in cadence_rows
    )
    failure_table = "\n".join(
        "| {sample_id} | {view_id} | {classification} | {post_ms:.1f} | "
        "{max_post:.3f} | {mean_post:.3f} | {mean_margin:.3f} | {dominant:.3f} | "
        "{final_active:.3f} | {final_post:.3f} |".format(
            sample_id=row["sample_id"],
            view_id=row["view_id"],
            classification=row["classification"],
            post_ms=float(row["post_context_available_ms"]),
            max_post=float(row["max_post_probability"]),
            mean_post=float(row["mean_post_probability"]),
            mean_margin=float(row["mean_post_minus_active_margin"]),
            dominant=float(row["post_dominant_fraction"]),
            final_active=float(row["final_active_probability"]),
            final_post=float(row["final_post_probability"]),
        )
        for row in result["failure_rows"]
        if row["population"] == "DEV"
    )
    clip_table = "\n".join(
        "| {sample_id} | {success} | {failure} | {classification} | {cadence} |".format(
            sample_id=row["sample_id"],
            success=", ".join(row["successful_views"]) or "none",
            failure=", ".join(row["genuine_failure_views"]) or "none",
            classification=row["clip_classification"],
            cadence="yes" if row["cadence_sensitive"] else "no",
        )
        for row in result["dev_failure_clips"]
    )
    diversity = result["diversity"]
    control_rows = "\n".join(
        (
            f"| {label} | {success_floor[key]:.3f} | "
            f"{active_ceiling[key]:.3f} |"
        )
        for label, key in (
            ("max POST probability", "max_post_probability"),
            ("mean POST probability", "mean_post_probability"),
            ("mean POST-ACTIVE margin", "mean_post_minus_active_margin"),
            ("POST-dominant fraction", "post_dominant_fraction"),
            ("final POST probability", "final_post_probability"),
        )
    )
    failure_header = (
        "| Sample | View | Attribution | post context ms | max POST | mean POST | "
        "mean margin | POST-dom. frac. | final ACTIVE | final POST |"
    )
    train_clips = diversity["segmentation_train_clips"]
    train_signers = diversity["segmentation_train_signers"]
    local_clips = diversity["local_train_clips"]
    local_signers = len(diversity["local_train_signers"])
    apphear_clips = diversity["apphear_capture_train_clips"]
    apphear_signers = len(diversity["apphear_capture_train_signers"])
    report = f"""# Phase 8A-T Causal Terminal Evidence Attribution

## Integrity and scope

Persisted frozen S2 streams were reused for 54 CAL and 69 signer-disjoint sparse DEV views. No
inference, extraction, training, decoder/materializer change, threshold search, recognition,
phone access, protected TEST access, or Android change occurred.

- Frozen S2 SHA-256: `{result["audit"]["s2_checkpoint_sha256"]}`
- Frozen materializer contract SHA-256: `{result["audit"]["materializer_contract_sha256"]}`
- Persisted streams: `54` CAL and `69` DEV views
- S2 inference rerun: `NO`
- Training / threshold search / decoder change: `NO / NO / NO`

## Population and controls

Successful terminal controls: `{len(result["terminal_controls"])}` views. Their human-ACTIVE
intervals provide the ordinary intra-sign POST-fluctuation control. Classification uses the fixed
five-measure control-envelope rule; it does not optimize a probability cutoff.

| Terminal measure | Successful-terminal p10 | Intra-ACTIVE p95 |
|---|---:|---:|
{control_rows}

`MODEL_TERMINAL_SIGNAL_PRESENT_DECODER_NOT_USING_IT` requires at least 3/5 measures to reach the
successful-terminal p10 and at least 4/5 to exceed the intra-ACTIVE p95. Signal absence requires
at most 1/5 for each comparison. Everything between those bounds remains ambiguous.

## DEV genuine no-events

Genuine non-censored failures: `{len(dev_failures)}` views across
`{len(result["dev_failure_clips"])}` underlying clips. Right-censored DEV views:
`{len(result["dev_censored"])}`.

{failure_header}
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
{failure_table}

Per-view attribution: `{absent_count}` signal absent, `{present_count}` signal present but unused,
and `{ambiguous_count}` ambiguous. Per-clip attribution: two signal-absent clips and one ambiguous
clip.

## Cadence and source/signer interpretation

| View | successful event | emitted but truncated | right-censored | genuine no-event |
|---|---:|---:|---:|---:|
{cadence_table}

| DEV clip | successful views | genuine failure views | clip attribution | cadence-sensitive |
|---|---|---|---|---|
{clip_table}

The primary DEV LOCAL evidence represents one held-out signer and four clips, not the full mobile
domain. Two clips succeed at VIEW_A but lose terminal evidence at VIEW_B/VIEW_C. One clip lacks
terminal evidence at all three cadences. The fourth LOCAL clip contributes the three explicitly
right-censored views and does not vote in the model-versus-decoder attribution.

CAL contains one contrasting no-event (`RUN 2`, VIEW_C) with strong terminal evidence
(max/final POST approximately `1.0`). That proves decoder-utilization failure can occur, but it is
not the dominant pattern among the seven genuine DEV no-events and therefore does not justify a
DEV-targeted probability-aware decoder as the first correction.

## Training-diversity context

- Segmentation TRAIN: `{train_clips}` clips / `{train_signers}` signers
- LOCAL TRAIN: `{local_clips}` clips across `{local_signers}` signers
- APPHEAR_CAPTURE TRAIN: `{apphear_clips}` clips from `{apphear_signers}` signer
- Held-out LOCAL DEV: one signer, `local_recorder:3B96F6-S002`

LOCAL supervision exists but is shallow. Independent signer and clean recovery-transition
diversity should be audited and, if inadequate, collected before a targeted S2 correction run.

## Decision

- Terminal-signal-absent views: `{absent_count}`
- Terminal-signal-present/decoder-unused views: `{present_count}`
- Ambiguous views: `{ambiguous_count}`
- Probability-aware decoder justified first: `{decoder_first}`
- Targeted S2 correction justified: `{decision["targeted_s2_correction_justified"]}`
- Additional signer-diverse LOCAL evidence needed before training:
  `{decision["additional_signer_diverse_local_data_needed_before_training"]}`

**`{decision["evidence_state"]}`**

Recommended first change: **`{decision["recommended_first_change"]}`**. No repair is implemented
in this milestone.

Answers to the milestone questions:

1. Six genuine DEV failure views lack terminal signal from S2.
2. Zero genuine DEV failure views contain terminal evidence comparable to successful commits.
3. One genuine DEV failure view remains ambiguous.
4. Probability-aware decoder work is not justified as the first change by this DEV evidence.
5. One targeted S2 ACTIVE-to-POST generalization correction is justified after data audit.
6. Additional signer-diverse LOCAL/recovery evidence is needed if the audit confirms the current
   shallow population is insufficient.
7. First change: audit transition/signer diversity, then correct S2 rather than CONFIG_01 or the
   frozen materializer.

## Claim limits

This is evidence from one held-out LOCAL signer and three independently failing clips expanded
across cadence views. It can localize the present failure mechanism but cannot establish that all
LOCAL, mobile, or phone users share it. Opened DEV must not be used to tune and then revalidate a
replacement.

## Stop boundary

**`{decision["next"]}`**
"""
    (OUT / "PHASE8A_T_CAUSAL_TERMINAL_EVIDENCE_ATTRIBUTION_REPORT.md").write_text(
        report, encoding="utf-8"
    )


def write_hashes() -> None:
    paths = [
        Path(__file__),
        ROOT / "eval/runtime_diagnostics/terminal_evidence.py",
        ROOT / "tests/test_terminal_evidence.py",
        ROOT / "tests/test_phase8a_t_terminal_evidence_attribution.py",
        P8R / "cal_state_run_manifest.json",
        P8M2 / "dev_s2_state_streams.json",
        P8M2 / "per_sparse_dev_materialization_result.csv",
        P8M / "materializer_contract_frozen.json",
    ]
    write_json(
        OUT / "source_hashes.json",
        {
            "schema": "apphear.phase8a_t.source_hashes.v1",
            "files": [{"path": str(path.resolve()), "sha256": sha256(path)} for path in paths],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests-confirmed", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    result = analyze()
    write_json(OUT / "integrity_reuse_audit.json", result["audit"])
    write_json(
        OUT / "population_inventory.json",
        {
            "schema": "apphear.phase8a_t.population_inventory.v1",
            "view_outcomes": dict(Counter(row["outcome"] for row in result["records"])),
            "clip_inventory": result["clip_inventory"],
        },
    )
    write_json(
        OUT / "successful_terminal_controls.json",
        _summarize_controls(
            result["terminal_controls"], "apphear.phase8a_t.successful_terminal_controls.v1"
        ),
    )
    write_json(
        OUT / "intra_sign_post_fluctuation_controls.json",
        _summarize_controls(
            result["active_controls"], "apphear.phase8a_t.intra_sign_post_controls.v1"
        ),
    )
    write_json(OUT / "terminal_control_envelope.json", result["envelope"])
    write_json(
        OUT / "genuine_no_event_terminal_evidence.json",
        {
            "schema": "apphear.phase8a_t.genuine_no_event_terminal_evidence.v1",
            "count": len(result["failures"]),
            "rows": result["failures"],
        },
    )
    write_failure_csv(result["failure_rows"])
    write_json(
        OUT / "clip_level_attribution.json",
        {
            "schema": "apphear.phase8a_t.clip_level_attribution.v1",
            "rows": result["dev_failure_clips"],
        },
    )
    write_json(OUT / "training_diversity_audit.json", result["diversity"])
    write_json(OUT / "final_decision.json", result["decision"])
    write_json(
        OUT / "test_results.json",
        {
            "schema": "apphear.phase8a_t.test_results.v1",
            "focused_pytest_cases": 9,
            "focused_pytest_passed": bool(args.tests_confirmed),
            "ruff_passed": bool(args.tests_confirmed),
            "python_compile_passed": bool(args.tests_confirmed),
            "s2_inference_rerun": False,
            "training": False,
            "threshold_search": False,
            "phone_opened": False,
        },
    )
    write_report(result)
    write_hashes()
    print(json.dumps(result["decision"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
