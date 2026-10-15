"""Read-only Stage2 diagnosis of the existing reviewed continuous WORD capture.

No labels, perception samples, missing frames, or counterfactual model outputs are invented.
The old evaluator and frozen TFLite package remain the sources of truth.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from eval.runtime_diagnostics import continuous_transition_diagnostics as legacy
from eval.runtime_diagnostics.phone_s2_exact_parity_and_r2_decision import load_capture
from pipeline.perception_vnext.segmentation.learned_features import (
    apply_normalization,
    derive_causal_segmentation_features,
)

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "android/app/src/main/assets/phone_causal_recognition_01/s2_r2_candidate"


def span_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Internal evidence availability, never a landmark-accuracy score."""
    if not rows:
        raise ValueError("EMPTY_REVIEWED_SPAN")
    active = [r for r in rows if r["argmax_state"] == 1]
    return {
        "observations": len(rows),
        "state_counts": dict(Counter(str(r["argmax_state"]) for r in rows)),
        "lifecycle_counts": dict(Counter(r["event_state_before"] for r in rows)),
        "ready_observations": sum(r["event_state_before"] == "IDLE" for r in rows),
        "active_observations": len(active),
        "blocked_active_indices": [
            r["source_index"] for r in active if r["event_state_before"] == legacy.WAIT
        ],
        "maximum_active_probability": max(r["active_probability"] for r in rows),
        "any_accepted_hand_observations": sum(
            r["left_observed"] or r["right_observed"] for r in rows
        ),
        "both_accepted_hand_observations": sum(
            r["left_observed"] and r["right_observed"] for r in rows
        ),
        "any_proposed_hand_observations": sum(
            r["left_proposal"] or r["right_proposal"] for r in rows
        ),
        "hand_motion_available_observations": sum(r["hand_delta_valid_count"] > 0 for r in rows),
        "mean_valid_body_points": sum(r["body_valid_point_count"] for r in rows) / len(rows),
        "admission_rejections": sum(r["admission_decision"] == "REJECT" for r in rows),
        "zero_active_cannot_be_repaired_by_rearm_alone": len(active) == 0,
    }


def sampling_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    gaps = np.diff([r["source_timestamp_ms"] for r in rows])
    return {
        "spacing_p50_ms": float(np.median(gaps)) if len(gaps) else None,
        "spacing_p95_ms": float(np.percentile(gaps, 95)) if len(gaps) else None,
        "gaps_over_533_232_ms": int(np.sum(gaps > 533.232)),
        "shorter_transition_could_fall_between_samples": True,
        "sensor_frame_drops": "NOT_MEASURED",
        "dense_counterfactual": "UNAVAILABLE_NO_UNPROCESSED_SENSOR_FRAMES",
    }


def compare(actual: np.ndarray, expected: np.ndarray, tolerance: float) -> dict[str, Any]:
    if actual.shape != expected.shape or not np.isfinite(actual).all():
        raise ValueError("INVALID_PARITY_TENSORS")
    maximum = float(np.max(np.abs(actual - expected)))
    return {"max_absolute_error": maximum, "tolerance": tolerance, "pass": maximum <= tolerance}


def verify_s2(session: Path) -> dict[str, Any]:
    """Same raw observations and bounded-prefix frozen S2; never rerun pixels from JPEGs."""
    import tensorflow as tf

    capture = load_capture(session, require_full_session=False)
    contract = legacy.read_json(PACKAGE / "contract.json")
    if legacy.sha256(PACKAGE / "s2_r2_fp32.tflite") != legacy.TFLITE_SHA:
        raise ValueError("FROZEN_S2_MODEL_HASH_MISMATCH")
    if legacy.sha256(PACKAGE / "normalization.json") != contract["normalization_asset_sha256"]:
        raise ValueError("FROZEN_S2_NORMALIZATION_HASH_MISMATCH")
    normalization = legacy.read_json(PACKAGE / "normalization.json")
    features = derive_causal_segmentation_features(capture.raw)
    normalized = apply_normalization(
        features,
        np.asarray(normalization["mean"], np.float32),
        np.asarray(normalization["std"], np.float32),
    )
    feature_result = compare(features, capture.android_features, 1e-6)
    normalization_result = compare(normalized, capture.android_normalized, 1e-6)
    if not feature_result["pass"] or not normalization_result["pass"]:
        raise ValueError("TRAIN_SERVE_SKEW_REQUIRES_INVESTIGATION")
    interpreter = tf.lite.Interpreter(model_path=str(PACKAGE / "s2_r2_fp32.tflite"), num_threads=1)
    probabilities = []
    allocated = 0
    for index in range(capture.count):
        prefix = normalized[max(0, index - 60) : index + 1][None]
        if prefix.shape[1] != allocated:
            interpreter.resize_tensor_input(
                interpreter.get_input_details()[0]["index"], prefix.shape
            )
            interpreter.allocate_tensors()
            allocated = prefix.shape[1]
        interpreter.set_tensor(interpreter.get_input_details()[0]["index"], prefix)
        interpreter.invoke()
        logits = interpreter.get_tensor(interpreter.get_output_details()[0]["index"])[0]
        shifted = logits - np.max(logits)
        probabilities.append(np.exp(shifted) / np.sum(np.exp(shifted)))
    predicted = np.asarray(probabilities, np.float32)
    probability_result = compare(predicted, capture.android_probabilities, 1e-4)
    mismatches = np.flatnonzero(np.argmax(predicted, axis=1) != capture.android_argmax)
    return {
        "observations": capture.count,
        "model_sha256": legacy.TFLITE_SHA,
        "feature_parity": feature_result,
        "normalization_parity": normalization_result,
        "tflite_probability_parity": probability_result,
        "argmax_mismatches": int(len(mismatches)),
        "pass": probability_result["pass"] and len(mismatches) == 0,
        "scope": (
            "same observations, host TFLite; "
            "not fresh Android performance or new recognition accuracy"
        ),
    }


def audit(session: Path, *, run_s2: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows, events, integrity = legacy.audit(session)
    labels_path = session / "transition_review/human_boundaries.json"
    labels = legacy.read_json(labels_path)
    legacy.validate_labels(labels, integrity, len(rows), session.name)
    evaluated = legacy.evaluate(
        rows,
        events,
        labels,
        legacy.jsonl(session / "ui_delivery.jsonl"),
        integrity["minimum_active_ms"],
        integrity["maximum_observation_gap_ms"],
    )
    historical = legacy.read_json(session / "transition_analysis/result.json")
    if not all(historical.get(key) == value for key, value in evaluated.items()):
        raise ValueError("HISTORICAL_ANALYSIS_NOT_REPRODUCED")
    signs = []
    for label, diagnosis in zip(labels["signs"], evaluated["attempts"], strict=True):
        entry = {**label, "legacy_classification": diagnosis["classification"]}
        if label["judgment"] == "GENUINE_SIGN":
            span = rows[label["start_index"] : label["end_index"] + 1]
            entry.update(span_summary(span), sampling=sampling_summary(span))
        signs.append(entry)
    transition_sampling = []
    for condition in legacy.BLOCKS[:2]:
        ordered = [s for s in labels["signs"] if s["condition"] == condition]
        for a, b in zip(ordered, ordered[1:], strict=False):
            if a["judgment"] != "GENUINE_SIGN" or b["judgment"] != "GENUINE_SIGN":
                continue
            between = rows[a["end_index"] + 1 : b["start_index"]]
            transition_sampling.append(
                {
                    "condition": condition,
                    "from": a["ordinal"],
                    "to": b["ordinal"],
                    "end_to_next_start_ms": rows[b["start_index"]]["source_timestamp_ms"]
                    - rows[a["end_index"]]["source_timestamp_ms"],
                    "between_observations": len(between),
                    "between_state_counts": dict(Counter(str(r["argmax_state"]) for r in between)),
                }
            )
    genuine = [s for s in signs if s["judgment"] == "GENUINE_SIGN"]
    fully_negative = sorted(
        {
            event_id
            for n in evaluated["reviewed_negatives"]
            for event_id in n.get("fully_contained_event_ids", [])
        }
    )
    result = {
        "schema_version": "apphear.recognition_v3.stage2_audit.v1",
        "integrated_comparison_commit": "e196a8d501386091eae52f59df0fa349e26b43e2",
        "historical_session": session.name,
        "integrity": integrity,
        "human_labels_sha256": legacy.sha256(labels_path),
        "historical_analysis_reproduced_exactly": True,
        "signer_status": "UNKNOWN_PROFICIENCY_DESIGN_SESSION_NOT_ACCURACY_VALIDATION",
        "reviewed_genuine_signs": len(genuine),
        "signs_with_zero_active": sum(s["active_observations"] == 0 for s in genuine),
        "signs_with_zero_accepted_hands": sum(
            s["any_accepted_hand_observations"] == 0 for s in genuine
        ),
        "signs": signs,
        "transition_sampling": transition_sampling,
        "transitions": evaluated["transitions"],
        "reviewed_negatives": evaluated["reviewed_negatives"],
        "fully_contained_negative_event_ids": fully_negative,
        "events": [
            {
                k: e[k]
                for k in (
                    "event_id",
                    "logical_active_start_index",
                    "logical_active_end_index",
                    "terminal_post_index",
                    "commit_index",
                    "top1_gloss",
                    "top1_probability",
                    "materialized_source_indices",
                    "recognition_v2_source_indices",
                )
            }
            for e in events
        ],
        "rearm_only_solution_supported": False,
        "continuous_s2_versus_perception_cause": "NOT_ISOLATED",
        "same_sign_repeat_phone_evidence": "MISSING",
        "sentence_repeat_limitation": (
            "SentenceBuilder.add ignores equal adjacent glosses " "even for distinct events"
        ),
        "stage1_android": legacy.read_json(
            ROOT / "evidence/recognition_v3_validation_20261015/phone_results.json"
        )["front_comparisons"],
        "stage1_live_lifecycle_truth": "NOT_RECORDED_NO_RETROSPECTIVE_CAUSE_ASSIGNMENT",
        "accuracy_claim": "NONE",
        "runtime_policy_changed": False,
    }
    if run_s2:
        result["same_observation_s2_parity"] = verify_s2(session)
    return result, rows


def export_kotlin_fixture(
    rows: list[dict[str, Any]], events: list[dict[str, Any]], path: Path
) -> None:
    """Real recorded inputs plus recorded Android decisions, not synthetic signs."""
    commits = {event["commit_index"]: event["event_id"] for event in events}
    fields = (
        "source_index",
        "source_timestamp_ms",
        "argmax_state",
        "event_state_before",
        "event_state_after",
        "event_action",
    )
    lines = ["# recorded Android states/actions; session_20260927T162103Z; no sign accuracy claim"]
    for row in rows:
        lines.append(
            "\t".join(
                [*(str(row[key]) for key in fields), str(commits.get(row["source_index"], 0))]
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def context_reset_probe(session: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """One closed-loop causal ablation; unchanged features/timers and no lexical claims."""
    import tensorflow as tf

    from eval.runtime_diagnostics.phone_repeated_recognition_integration import replay

    # Verify all frozen input/output identities before introducing the single ablation.
    parity = verify_s2(session)
    if not parity["pass"]:
        raise ValueError("BASELINE_PARITY_REQUIRED_BEFORE_PROBE")
    capture = load_capture(session, require_full_session=False)
    labels = legacy.read_json(session / "transition_review/human_boundaries.json")

    def run_arm(reset: bool) -> dict[str, Any]:
        runner = tf.lite.Interpreter(model_path=str(PACKAGE / "s2_r2_fp32.tflite"), num_threads=1)
        history_start, allocated = 0, 0
        predicted_rows: list[dict[str, Any]] = []
        reset_indices: list[int] = []

        def predict(row: dict[str, Any], previous_action: str | None) -> dict[str, Any]:
            nonlocal history_start, allocated
            index = row["source_index"]
            if reset and previous_action == "REARM_COMPLETE":
                history_start = index
                reset_indices.append(index)
            prefix = capture.android_normalized[max(history_start, index - 60) : index + 1][None]
            if prefix.shape[1] != allocated:
                runner.resize_tensor_input(runner.get_input_details()[0]["index"], prefix.shape)
                runner.allocate_tensors()
                allocated = prefix.shape[1]
            runner.set_tensor(runner.get_input_details()[0]["index"], prefix)
            runner.invoke()
            logits = runner.get_tensor(runner.get_output_details()[0]["index"])[0]
            exponential = np.exp(logits - np.max(logits))
            probabilities = exponential / np.sum(exponential)
            predicted = {
                **row,
                **dict(
                    zip(
                        ("pre_probability", "active_probability", "post_probability"),
                        map(float, probabilities),
                        strict=True,
                    )
                ),
                "argmax_state": int(np.argmax(probabilities)),
            }
            predicted_rows.append(predicted)
            return predicted

        replayed = replay(
            rows, allow_post_rearm=True, exact_android_commit_recovery=True, prediction_hook=predict
        )
        for row, trace in zip(predicted_rows, replayed["trace"], strict=True):
            row.update(
                event_state_before=trace["state_before"],
                event_state_after=trace["state_after"],
                event_action=trace["action"],
            )
        event_ids = [legacy.event_identity(e) for e in replayed["events"]]
        if not reset:
            historical = legacy.jsonl(session / "events.jsonl")
            if event_ids != [legacy.event_identity(e) for e in historical]:
                raise ValueError("CLOSED_LOOP_BASELINE_EVENTS_MISMATCH")
            if any(
                a["argmax_state"] != b["argmax_state"]
                or a["event_state_after"] != b["event_state_after"]
                for a, b in zip(predicted_rows, rows, strict=True)
            ):
                raise ValueError("CLOSED_LOOP_BASELINE_STATES_MISMATCH")
        signs = []
        for sign in labels["signs"]:
            if sign["judgment"] != "GENUINE_SIGN":
                continue
            start, end = sign["start_index"], sign["end_index"]
            overlaps = [
                e
                for e in replayed["events"]
                if max(start, e["logical_active_start_index"])
                <= min(end, e["logical_active_end_index"])
            ]
            signs.append(
                {
                    **sign,
                    **span_summary(predicted_rows[start : end + 1]),
                    "overlapping_logical_events": [e["event_id"] for e in overlaps],
                    "event_opened_within_reviewed_sign": [
                        e["event_id"]
                        for e in overlaps
                        if start <= e["logical_active_start_index"] <= end
                    ],
                    "overlap_is_not_correct_recognition": True,
                }
            )
        negatives = []
        for interval in labels["negative_intervals"]:
            if interval["judgment"] != "CONFIRMED_NON_SIGN":
                continue
            a, b = interval["start_index"], interval["end_index"]
            negatives.append(
                {
                    **interval,
                    "fully_contained_event_ids": [
                        e["event_id"]
                        for e in replayed["events"]
                        if a
                        <= e["logical_active_start_index"]
                        <= e["logical_active_end_index"]
                        <= b
                    ],
                    "active_observations": sum(
                        r["argmax_state"] == 1 for r in predicted_rows[a : b + 1]
                    ),
                }
            )
        return {
            "event_count": replayed["event_count"],
            "events": replayed["events"],
            "reset_indices": reset_indices,
            "signs": signs,
            "reviewed_negatives": negatives,
            "fully_contained_negative_events": sum(
                len(n["fully_contained_event_ids"]) for n in negatives
            ),
        }

    by_arm = {"unchanged_history": run_arm(False), "reset_after_rearm": run_arm(True)}
    return {
        "schema_version": "apphear.recognition_v3.stage2_context_reset_probe.v1",
        "hypothesis": "S2 POST history carry-over contributes to missed subsequent signs",
        "single_change": (
            "clear only S2 normalized model-prefix history " "after causal REARM_COMPLETE"
        ),
        "unchanged": [
            "capture inputs",
            "378 features and deltas",
            "normalization",
            "model weights",
            "decoder timers",
            "admission",
            "materializer contract",
        ],
        "baseline_same_observation_parity": parity,
        "arms": by_arm,
        "classification_and_ui": "NOT_RUN_FOR_COUNTERFACTUAL_WINDOWS",
        "deployment": "OFFLINE_ONLY_NOT_AN_ANDROID_RUNTIME_POLICY",
        "accuracy_claim": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify-s2", action="store_true")
    parser.add_argument("--context-reset-probe", type=Path)
    parser.add_argument("--kotlin-fixture", type=Path)
    args = parser.parse_args()
    result, rows = audit(args.session, run_s2=args.verify_s2)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if args.context_reset_probe:
        probe = context_reset_probe(args.session, rows)
        args.context_reset_probe.parent.mkdir(parents=True, exist_ok=True)
        args.context_reset_probe.write_text(
            json.dumps(probe, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    if args.kotlin_fixture:
        export_kotlin_fixture(rows, result["events"], args.kotlin_fixture)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "historical_analysis_reproduced_exactly",
                    "reviewed_genuine_signs",
                    "signs_with_zero_active",
                    "fully_contained_negative_event_ids",
                    "rearm_only_solution_supported",
                )
            },
            indent=2,
        )
    )
    if args.verify_s2 and not result["same_observation_s2_parity"]["pass"]:
        raise SystemExit("FROZEN_S2_REPLAY_PARITY_FAILED")


if __name__ == "__main__":
    main()
