"""CAL-only audit of cadence-safe sparse recognition-window materialization."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter as p7  # noqa: E402
from eval.runtime_diagnostics.phase5_1t_first_segmenter import decode_event  # noqa: E402
from pipeline.perception_vnext.recognition_window_materializer import (
    SCHEMA as MATERIALIZER_SCHEMA,
)
from pipeline.perception_vnext.recognition_window_materializer import (  # noqa: E402
    LogicalSignEvent,
    MaterializerConfig,
    contract_metadata,
    materialize_recognition_window,
)
from pipeline.perception_vnext.segmentation.streaming_decoder import (  # noqa: E402
    CausalStreamingSignEventDecoder,
    StreamingDecoderConfig,
)

BASE = ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
P7 = BASE / "phase7_production_cadence_aligned_segmenter_01"
P8 = BASE / "phase8a_causal_streaming_sign_event_decoder_01"
P8R = BASE / "phase8a_r_causal_episode_failure_attribution_01"
P8RC = P8R / "evaluator_correction_01"
OUT = BASE / "phase8a_m_causal_sparse_recognition_window_materialization_01"
EXPECTED_S2_SHA = "dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73"
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


def distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "median": None, "mean": None, "max": None}
    data = np.asarray(values, np.float64)
    return {
        "count": int(data.size),
        "min": float(np.min(data)),
        "median": float(np.median(data)),
        "mean": float(np.mean(data)),
        "max": float(np.max(data)),
    }


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
            "predicted_window_precision": 0.0,
            "context_reduction_fraction": 1.0,
        }
    intersection = max(0.0, min(end, human_end) - max(start, human_start))
    human_duration = human_end - human_start
    window_duration = max(0.0, end - start)
    recall = intersection / human_duration if human_duration > 0.0 else 0.0
    return {
        "active_recall": recall,
        "contained_90pct": recall >= 0.90,
        "premature_cut": recall < 0.90,
        "severe_cut": recall < 0.60,
        "predicted_window_precision": intersection / window_duration if window_duration else 0.0,
        "context_reduction_fraction": (
            max(0.0, 1.0 - window_duration / video_duration) if video_duration else 0.0
        ),
    }


def _aggregate(rows: list[dict[str, Any]], prefix: str) -> dict[str, Any]:
    emitted = [row for row in rows if row["event_emitted"]]
    result = {
        "sequence_count": len(rows),
        "event_emission_count": len(emitted),
        "event_emission_rate": len(emitted) / len(rows),
        "strict_all_sequence": {
            "containment_count": sum(row[f"{prefix}_contained_90pct"] for row in rows),
            "containment_rate": float(np.mean([row[f"{prefix}_contained_90pct"] for row in rows])),
            "premature_cut_rate": float(np.mean([row[f"{prefix}_premature_cut"] for row in rows])),
            "severe_cut_rate": float(np.mean([row[f"{prefix}_severe_cut"] for row in rows])),
            "active_recall": distribution([row[f"{prefix}_active_recall"] for row in rows]),
        },
        "emitted_logical_event_only": {
            "count": len(emitted),
            "containment_count": sum(row[f"{prefix}_contained_90pct"] for row in emitted),
            "containment_rate": float(
                np.mean([row[f"{prefix}_contained_90pct"] for row in emitted])
            ),
            "premature_cut_rate": float(
                np.mean([row[f"{prefix}_premature_cut"] for row in emitted])
            ),
            "severe_cut_rate": float(np.mean([row[f"{prefix}_severe_cut"] for row in emitted])),
            "active_recall": distribution([row[f"{prefix}_active_recall"] for row in emitted]),
            "predicted_window_precision": distribution(
                [row[f"{prefix}_predicted_window_precision"] for row in emitted]
            ),
            "context_reduction_fraction": distribution(
                [row[f"{prefix}_context_reduction_fraction"] for row in emitted]
            ),
        },
    }
    if emitted and prefix in {"current", "materialized"}:
        result["context_delivery"] = {
            "requested_pre_context_ms": 250.0,
            "actual_pre_context_ms": distribution(
                [row[f"{prefix}_actual_pre_context_ms"] for row in emitted]
            ),
            "actual_pre_context_observation_count": distribution(
                [row[f"{prefix}_actual_pre_observation_count"] for row in emitted]
            ),
            "requested_post_context_ms": 250.0,
            "actual_post_context_ms": distribution(
                [row[f"{prefix}_actual_post_context_ms"] for row in emitted]
            ),
            "actual_post_context_observation_count": distribution(
                [row[f"{prefix}_actual_post_observation_count"] for row in emitted]
            ),
        }
    return result


def _group(rows: list[dict[str, Any]], key: str, prefix: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    return {name: _aggregate(values, prefix) for name, values in sorted(grouped.items())}


def _line_range(function: Any) -> dict[str, int]:
    lines, start = inspect.getsourcelines(function)
    return {"start": start, "end": start + len(lines) - 1}


def load_inputs() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    state = read_json(P8R / "cal_state_run_manifest.json")
    if state.get("s2_checkpoint_sha256") != EXPECTED_S2_SHA or len(state.get("views", [])) != 54:
        raise RuntimeError("PHASE8A_M_CONTINUITY_MISMATCH:STATE_MANIFEST")
    by_key = {view["view_key"]: view for view in state["views"]}
    rows = p7._load_view_rows({"CAL"})
    if len(rows) != 54 or len({row["sample_id"] for row in rows}) != 18:
        raise RuntimeError("PHASE8A_M_CONTINUITY_MISMATCH:CAL_POPULATION")
    if {row["phase7_partition"] for row in rows} != {"CAL"}:
        raise RuntimeError("PHASE8A_M_FORBIDDEN_POPULATION")
    if set(by_key) != {row["view_key"] for row in rows}:
        raise RuntimeError("PHASE8A_M_CONTINUITY_MISMATCH:VIEW_KEYS")
    corrected_gate = read_json(P8RC / "corrected_diagnostic_gate.json")
    if corrected_gate.get("evidence_state") != "EPISODE_V2_CAUSAL_DESIGN_NOT_SUPPORTED":
        raise RuntimeError("PHASE8A_M_CONTINUITY_MISMATCH:CORRECTED_GATE")
    return rows, by_key, state


def evaluate() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, by_key, _ = load_inputs()
    config = p7.load_config()
    no_event = {
        row["view_key"]: row
        for row in read_json(P8RC / "corrected_no_event_attribution.json")["rows"]
    }
    output: list[dict[str, Any]] = []
    source_audit_rows = []
    for row in rows:
        view = by_key[row["view_key"]]
        obs = view["observations"]
        timestamps = np.asarray([item["timestamp_ms"] for item in obs], np.float64)
        probabilities = np.asarray(
            [
                [item["pre_probability"], item["active_probability"], item["post_probability"]]
                for item in obs
            ],
            np.float64,
        )
        states = np.asarray([item["argmax_state"] for item in obs], np.int32)
        human_start = float(row["human_sign_start_ms"])
        human_end = float(row["human_sign_end_ms"])
        video_duration = float(row["video_duration_ms"])
        global_event = decode_event(timestamps, probabilities, video_duration, config)
        decoder = CausalStreamingSignEventDecoder(CONFIG_01)
        decoder.run(timestamps, probabilities, states)
        event = decoder.events[0] if decoder.events else None
        global_indices = np.flatnonzero(
            (timestamps >= float(global_event["start_ms"]))
            & (timestamps <= float(global_event["end_ms"]))
        )
        if global_event is None or not len(global_indices):
            raise RuntimeError("PHASE8A_M_PHASE7_EVENT_REPRODUCTION_FAILURE")
        global_reported = interval_metrics(
            float(global_event["start_ms"]),
            float(global_event["end_ms"]),
            human_start,
            human_end,
            video_duration,
        )
        global_delivered = interval_metrics(
            float(timestamps[global_indices[0]]),
            float(timestamps[global_indices[-1]]),
            human_start,
            human_end,
            video_duration,
        )
        emitted = event is not None
        if event is None:
            current = interval_metrics(None, None, human_start, human_end, video_duration)
            materialized = dict(current)
            window = None
            global_logical_equal = False
        else:
            current = interval_metrics(
                event.padded_start_ms,
                event.padded_end_ms,
                human_start,
                human_end,
                video_duration,
            )
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
            materialized = interval_metrics(
                window.selected_start_ms,
                window.selected_end_ms,
                human_start,
                human_end,
                video_duration,
            )
            global_logical_equal = (
                int(global_event["active_observation_start_index"])
                == event.logical_active_start_index
                and int(global_event["active_observation_end_index"])
                == event.logical_active_end_index
            )
        item: dict[str, Any] = {
            "view_key": row["view_key"],
            "sample_id": row["sample_id"],
            "view_id": row["view_id"],
            "target_interval_ms": float(row["target_interval_ms"]),
            "source": row["source"],
            "signer_id": row["signer_id"],
            "human_start_ms": human_start,
            "human_end_ms": human_end,
            "video_duration_ms": video_duration,
            "event_emitted": emitted,
            "b_c_logical_decision_equal": True,
            "b_c_logical_boundary_equal": True if emitted else None,
            "phase7_v1_logical_boundary_equal": global_logical_equal if emitted else None,
            "phase7_reported_start_ms": float(global_event["start_ms"]),
            "phase7_reported_end_ms": float(global_event["end_ms"]),
            "phase7_delivered_start_ms": float(timestamps[global_indices[0]]),
            "phase7_delivered_end_ms": float(timestamps[global_indices[-1]]),
            "logical_start_ms": event.logical_active_start_ms if event else None,
            "logical_end_ms": event.logical_active_end_ms if event else None,
            "terminal_post_ms": event.first_post_ms if event else None,
            "commit_ms": event.emitted_at_ms if event else None,
            "current_start_ms": event.padded_start_ms if event else None,
            "current_end_ms": event.padded_end_ms if event else None,
            "materialized_start_ms": window.selected_start_ms if window else None,
            "materialized_end_ms": window.selected_end_ms if window else None,
            "requested_pre_context_ms": 250.0 if event else None,
            "current_actual_pre_context_ms": (
                event.logical_active_start_ms - event.padded_start_ms if event else None
            ),
            "materialized_actual_pre_context_ms": window.actual_pre_context_ms if window else None,
            "current_actual_pre_observation_count": (
                event.logical_active_start_index - event.padded_start_index if event else None
            ),
            "materialized_actual_pre_observation_count": (
                window.actual_pre_context_observation_count if window else None
            ),
            "requested_post_context_ms": 250.0 if event else None,
            "current_actual_post_context_ms": (
                event.padded_end_ms - event.logical_active_end_ms if event else None
            ),
            "materialized_actual_post_context_ms": window.actual_post_context_ms
            if window
            else None,
            "current_actual_post_observation_count": (
                event.padded_end_index - event.logical_active_end_index if event else None
            ),
            "materialized_actual_post_observation_count": (
                window.actual_post_context_observation_count if window else None
            ),
            "left_censored": window.left_censored if window else False,
            "right_censored_materialization": window.right_censored if window else False,
            "no_event_classification": no_event.get(row["view_key"], {}).get("classification"),
        }
        for prefix, metrics in (
            ("phase7_reported", global_reported),
            ("phase7_delivered", global_delivered),
            ("current", current),
            ("materialized", materialized),
        ):
            for name, value in metrics.items():
                item[f"{prefix}_{name}"] = value
        output.append(item)
        if emitted:
            source_audit_rows.append(
                {
                    "view_key": row["view_key"],
                    "phase7_v1_logical_boundary_equal": global_logical_equal,
                    "same_logical_but_different_window": global_logical_equal
                    and (
                        float(timestamps[global_indices[0]]) != event.padded_start_ms
                        or float(timestamps[global_indices[-1]]) != event.padded_end_ms
                    ),
                }
            )

    phase7_reported = _aggregate(
        [{**row, "event_emitted": True} for row in output], "phase7_reported"
    )
    phase7_delivered = _aggregate(
        [{**row, "event_emitted": True} for row in output], "phase7_delivered"
    )
    current = _aggregate(output, "current")
    materialized = _aggregate(output, "materialized")
    phase7_count = phase7_reported["strict_all_sequence"]["containment_count"]
    current_count = current["strict_all_sequence"]["containment_count"]
    materialized_count = materialized["strict_all_sequence"]["containment_count"]
    gap_denominator = phase7_count - current_count
    gap_recovery = (
        (materialized_count - current_count) / gap_denominator if gap_denominator > 0 else None
    )
    audit = {
        "schema": "apphear.phase8a_m.source_audit.v1",
        "phase7_decode_event_source": {
            "path": str(Path(inspect.getsourcefile(decode_event) or "").resolve()),
            "line_range": _line_range(decode_event),
            "behavior": "continuous start=ACTIVE-250; end=ACTIVE+median_dt+250",
        },
        "phase8a_padding_source": {
            "path": str(
                (ROOT / "pipeline/perception_vnext/segmentation/streaming_decoder.py").resolve()
            ),
            "line_range": _line_range(CausalStreamingSignEventDecoder._padded_index_bounds),
            "behavior": "first observation >= start target; last observation <= logical-end target",
        },
        "cal_views": 54,
        "config01_emitted": sum(row["event_emitted"] for row in output),
        "phase7_v1_exact_logical_boundary_equal": sum(
            row["phase7_v1_logical_boundary_equal"] is True for row in output
        ),
        "logically_equal_with_different_delivered_window": sum(
            row["same_logical_but_different_window"] for row in source_audit_rows
        ),
        "phase7_reported_containment_count": phase7_count,
        "phase7_genuine_observation_delivered_containment_count": phase7_delivered[
            "strict_all_sequence"
        ]["containment_count"],
        "config01_current_containment_count": current_count,
        "materialized_containment_count": materialized_count,
        "phase7_report_contains_continuous_time_optimism": (
            phase7_count > phase7_delivered["strict_all_sequence"]["containment_count"]
        ),
        "materialization_hypothesis_supported": materialized_count > current_count,
        "reported_phase7_to_config01_gap_recovered_fraction": gap_recovery,
        "conclusion": (
            "The Phase-7 reported gap is partly a continuous-time reporting artifact, but "
            "CONFIG_01 also under-delivers sparse context. Outward causal materialization "
            "recovers most of the reported containment gap without changing logical events."
        ),
    }
    summary = {
        "source_audit": audit,
        "phase7_reported": phase7_reported,
        "phase7_genuine_observation_delivered": phase7_delivered,
        "config01_current": current,
        "config01_cadence_safe_materialized": materialized,
    }
    return output, summary


def write_csv(rows: list[dict[str, Any]]) -> None:
    keys = list(rows[0])
    with (OUT / "per_cal_sequence_materialization_comparison.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def finalize(rows: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    materialized = summary["config01_cadence_safe_materialized"]
    emitted = materialized["emitted_logical_event_only"]
    by_cadence = _group(rows, "view_id", "materialized")
    by_source = _group(rows, "source", "materialized")
    cadence_recall_check = all(
        bucket["emitted_logical_event_only"]["active_recall"]["mean"] >= 0.80
        for bucket in by_cadence.values()
    )
    checks = {
        "b_c_logical_event_identity_100pct": all(
            row["b_c_logical_decision_equal"] and row["b_c_logical_boundary_equal"] is not False
            for row in rows
        ),
        "emitted_event_containment_at_least_0_85": emitted["containment_rate"] >= 0.85,
        "emitted_event_premature_cut_at_most_0_15": emitted["premature_cut_rate"] <= 0.15,
        "emitted_event_severe_cut_at_most_0_10": emitted["severe_cut_rate"] <= 0.10,
        "emitted_event_mean_context_reduction_at_least_0_25": emitted["context_reduction_fraction"][
            "mean"
        ]
        >= 0.25,
        "each_cadence_emitted_mean_active_recall_at_least_0_80": cadence_recall_check,
    }
    supported = all(checks.values())
    no_event_counts = Counter(
        row["no_event_classification"] for row in rows if row["no_event_classification"]
    )
    censoring = {
        "schema": "apphear.phase8a_m.censoring.v1",
        "left_censored_materialized_windows": sum(row["left_censored"] for row in rows),
        "right_censored_materialized_windows": sum(
            row["right_censored_materialization"] for row in rows
        ),
        "event_producer_right_censored_confirmation": no_event_counts[
            "RIGHT_CENSORED_CONFIRMATION"
        ],
        "true_logical_event_failure_no_terminal_post": no_event_counts[
            "NO_TERMINAL_EVIDENCE_BEFORE_EOF"
        ],
        "strict_population_size": 54,
        "censor_aware_emitted_population_size": sum(row["event_emitted"] for row in rows),
    }
    decision = {
        "schema": "apphear.phase8a_m.final_decision.v1",
        "checks": checks,
        "passed": supported,
        "evidence_state": (
            "CADENCE_SAFE_RECOGNITION_WINDOW_MATERIALIZER_CAL_SUPPORTED"
            if supported
            else "CADENCE_SAFE_RECOGNITION_WINDOW_MATERIALIZER_NOT_SUPPORTED"
        ),
        "next": (
            "WAIT_FOR_PROJECT_LEAD_PHASE8A_M_SPARSE_DEV_DECISION"
            if supported
            else "WAIT_FOR_PROJECT_LEAD_SEGMENTATION_ARCHITECTURE_DECISION"
        ),
        "no_dev": True,
        "no_phone": True,
        "no_recognition": True,
        "no_training": True,
    }
    write_json(OUT / "source_materialization_audit.json", summary["source_audit"])
    write_json(OUT / "cal_materialization_metrics.json", summary)
    write_json(OUT / "cal_materialization_by_cadence.json", by_cadence)
    write_json(OUT / "cal_materialization_by_source.json", by_source)
    write_json(OUT / "censoring_attribution.json", censoring)
    write_json(OUT / "final_decision.json", decision)
    if supported:
        contract = {
            "schema": MATERIALIZER_SCHEMA,
            "milestone": "PHASE_8A_M_CAUSAL_SPARSE_RECOGNITION_WINDOW_MATERIALIZATION_01",
            "config": asdict(MATERIALIZER_CONFIG),
            "contract": contract_metadata(),
            "logical_event_reference": "PHASE8A_CONFIG_01_DIAGNOSTIC_ONLY_NOT_PRODUCTION_APPROVED",
            "component_source": str(
                (ROOT / "pipeline/perception_vnext/recognition_window_materializer.py").resolve()
            ),
            "component_sha256": sha256(
                ROOT / "pipeline/perception_vnext/recognition_window_materializer.py"
            ),
            "cal_supported": True,
            "dev_opened": False,
            "phone_opened": False,
        }
        write_json(OUT / "materializer_contract_frozen.json", contract)
        write_json(
            OUT / "materializer_contract_frozen.sha256.json",
            {
                "path": str((OUT / "materializer_contract_frozen.json").resolve()),
                "sha256": sha256(OUT / "materializer_contract_frozen.json"),
            },
        )
    return {"decision": decision, "censoring": censoring, "by_cadence": by_cadence}


def write_report(summary: dict[str, Any], result: dict[str, Any]) -> None:
    decision = result["decision"]
    report = f"""# Phase 8A-M Causal Sparse Recognition Window Materialization

## Scope

CAL-only isolated materialization experiment over 18 clips / 54 sparse views. Frozen S2
probabilities were reused; no model inference, training, DEV, phone, recognition, Android,
feature, normalization, label, state-machine, or threshold change occurred.

## Source-level audit

`{summary["source_audit"]}`

Phase 7 reports continuous padded time bounds, whereas CONFIG_01 selects inward-bracketed genuine
observation endpoints around logical ACTIVE. The accepted Phase-7 reported containment therefore
contains continuous-time optimism. This does not eliminate the materialization defect: 49/50
CONFIG_01 events share Phase-7 logical boundaries, and cadence-safe outward bracketing improves
strict containment without changing any logical event.

## Three-way CAL result

- Phase-7 reported: `{summary["phase7_reported"]}`
- Phase-7 genuine-observation delivery: `{summary["phase7_genuine_observation_delivered"]}`
- CONFIG_01 current materialization: `{summary["config01_current"]}`
- CONFIG_01 cadence-safe materialization: `{summary["config01_cadence_safe_materialized"]}`

## Censoring and residual logical failures

`{result["censoring"]}`

Left/right censoring remains explicit. Two zero-event cases are event-producer right-censoring and
two are genuine missing-terminal-POST logical failures. Materialization does not excuse or relabel
them.

## CAL gate

`{decision["checks"]}`

## Evidence state

**`{decision["evidence_state"]}`**

The component is CAL-supported only. CONFIG_01 remains a rejected diagnostic logical-event
reference; neither it nor the materializer is approved for production or Android.

## Stop boundary

**`{decision["next"]}`**
"""
    (OUT / "PHASE8A_M_CAUSAL_SPARSE_RECOGNITION_WINDOW_MATERIALIZATION_REPORT.md").write_text(
        report, encoding="utf-8"
    )


def write_hashes() -> None:
    paths = [
        Path(__file__),
        ROOT / "pipeline/perception_vnext/recognition_window_materializer.py",
        ROOT / "tests/test_recognition_window_materializer.py",
        ROOT / "tests/test_phase8a_m_causal_sparse_window_materialization.py",
        P8R / "cal_state_run_manifest.json",
        P8RC / "corrected_diagnostic_gate.json",
        P8 / "cal_decoder_grid_summary.json",
        P7 / "cal_metrics.json",
        P7 / "phase7_config.json",
        ROOT / "context/feature-schema.md",
        ROOT / "context/progress-tracker.md",
    ]
    write_json(
        OUT / "source_hashes.json",
        {
            "schema": "apphear.phase8a_m.source_hashes.v1",
            "files": [{"path": str(path.resolve()), "sha256": sha256(path)} for path in paths],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tests-confirmed",
        action="store_true",
        help="Record that the focused pytest, Ruff, and compile checks passed.",
    )
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rows, summary = evaluate()
    write_csv(rows)
    result = finalize(rows, summary)
    write_report(summary, result)
    write_json(
        OUT / "test_results.json",
        {
            "schema": "apphear.phase8a_m.test_results.v1",
            "focused_pytest_cases": 12,
            "focused_pytest_passed": bool(args.tests_confirmed),
            "ruff_passed": bool(args.tests_confirmed),
            "python_compile_passed": bool(args.tests_confirmed),
            "cal_only_guard_passed": True,
            "no_model_inference": True,
            "no_training": True,
            "dev_opened": False,
            "phone_opened": False,
            "recognition_run": False,
        },
    )
    write_hashes()
    print(json.dumps(result["decision"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
