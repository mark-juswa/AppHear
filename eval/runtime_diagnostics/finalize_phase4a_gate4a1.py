"""Finalize Gate 4A-1 from host-retained live Android evidence.

The script reads only the pulled live session, the frozen ordinary V2 checkpoint, and the
frozen vocabulary. It never opens TRAIN/DEV/TEST data and never trains or writes weights.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.perception_vnext.recognition_schema import RAW_SCHEMA, RawSequence
from pipeline.perception_vnext.recognition_schema_v2 import (
    FEATURE_SCHEMA_V2,
    FEATURE_WIDTH_V2,
    temporal_view_v2,
)

ROOT = Path(__file__).resolve().parents[2]
MILESTONE = "PHASE_4A_GATE_4A1_LIVE_PLUMBING_VALIDATION_01"
CHECKPOINT = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "tcn_v2_run_01/best.keras"
)
VOCAB = ROOT / "artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1/vocab.json"
EXPECTED_CHECKPOINT_SHA = "8107accbc621ae5652766fec80d314fe8dc9f94ba0d0548a6aef80ed91729340"
EXPECTED_VOCAB_SHA = "a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b"
V2_TOLERANCE = 1.0e-5
OUTPUT_TOLERANCE = 1.0e-4
PHONE_COMPLETED_FPS = 5.606840672873506


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_float32(path: Path, count: int) -> np.ndarray:
    values = np.fromfile(path, dtype="<f4")
    if len(values) != count:
        raise RuntimeError(f"GATE4A1_BINARY_SHAPE_FAILURE:{path}:{len(values)}:{count}")
    return values


def floats(values: list[Any]) -> np.ndarray:
    return np.asarray([np.nan if value is None else value for value in values], np.float32)


def load_raw(path: Path) -> tuple[RawSequence, dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    frames = len(value["frame_index"])
    raw = RawSequence(
        metadata={"schema": value["schema"], "image_semantics": value["image_semantics"]},
        frame_index=np.asarray(value["frame_index"], np.int32),
        timestamp_ms=np.asarray(value["timestamp_ms"], np.float64),
        source_size=np.asarray(value["source_size"], np.int32).reshape(frames, 2),
        hand_xy=floats(value["hand_xy"]).reshape(frames, 2, 21, 2),
        hand_proposal_support=floats(value["hand_proposal_support"]).reshape(frames, 2, 21),
        hand_joint_valid=np.asarray(value["hand_joint_valid"], bool).reshape(frames, 2, 21),
        hand_presence=floats(value["hand_presence"]).reshape(frames, 2),
        hand_observed=np.asarray(value["hand_observed"], bool).reshape(frames, 2),
        hand_proposal_present=np.asarray(value["hand_proposal_present"], bool).reshape(frames, 2),
        hand_roi_center_side=floats(value["hand_roi_center_side"]).reshape(frames, 2, 3),
        hand_handedness_diagnostic=floats(value["hand_handedness_diagnostic"]).reshape(frames, 2),
        body_xy=floats(value["body_xy"]).reshape(frames, 8, 2),
        body_support=floats(value["body_support"]).reshape(frames, 8),
        body_valid=np.asarray(value["body_valid"], bool).reshape(frames, 8),
        body_available=np.asarray(value["body_available"], bool),
    )
    raw.validate()
    return raw, value


def topk(values: np.ndarray) -> list[int]:
    return np.argsort(-values, kind="stable")[:5].astype(int).tolist()


def summarize(values: list[np.ndarray]) -> dict[str, Any]:
    flat = np.concatenate([np.asarray(value).reshape(-1) for value in values]).astype(np.float64)
    return {
        "count": int(flat.size),
        "max_abs": float(np.max(flat)),
        "p95_abs": float(np.percentile(flat, 95)),
        "mean_abs": float(np.mean(flat)),
    }


def percentile(values: list[float], q: float) -> float | None:
    return float(np.percentile(values, q)) if values else None


def verify_capture_semantics(summary: dict[str, Any], raw_value: dict[str, Any]) -> dict[str, Any]:
    start = int(summary["t_start_ns"])
    stop = int(summary["t_stop_ns"])
    source = [int(value) for value in summary["accepted_source_timestamps_ns"]]
    completion = [int(value) for value in summary["completion_timestamps_ns"]]
    raw_ms = np.asarray(raw_value["timestamp_ms"], np.float64)
    checks = {
        "candidate01_warm_before_start": summary["candidate01_warm_before_start"] is True,
        "all_source_timestamps_within_bounds": all(start <= value <= stop for value in source),
        "no_source_newer_than_stop": all(value <= stop for value in source),
        "chronological": all(right > left for left, right in zip(source, source[1:])),
        "no_duplicates": len(source) == len(set(source)),
        "completion_time_not_membership": summary["callback_completion_time_used_for_membership"] is False,
        "eligible_post_stop_completions_retained": int(summary["in_flight_completions_after_stop"])
        == sum(int(s <= stop and c > stop) for s, c in zip(source, completion)),
        "no_phone_sparse_simulator": summary["live_temporal_policy"]
        == "DENSE_ACTUAL_LIVE_OBSERVATIONS_NO_PHONE_01_RESAMPLING",
        "raw_timestamp_matches_source": bool(
            np.array_equal(raw_ms, np.asarray(source, np.float64) / 1_000_000.0)
        ),
        "observation_count_consistent": len(source) == int(summary["observation_count"]),
    }
    checks["status"] = "PASS" if all(checks.values()) else "FAIL"
    return checks


def run(session: Path, output: Path) -> dict[str, Any]:
    if sha256(CHECKPOINT) != EXPECTED_CHECKPOINT_SHA:
        raise RuntimeError("GATE4A1_CHECKPOINT_IDENTITY_FAILURE")
    if sha256(VOCAB) != EXPECTED_VOCAB_SHA:
        raise RuntimeError("GATE4A1_VOCAB_IDENTITY_FAILURE")
    identity = json.loads((session / "session_identity.json").read_text(encoding="utf-8"))
    session_summary = json.loads((session / "session_summary.json").read_text(encoding="utf-8"))
    if identity["milestone"] != MILESTONE or session_summary["valid_attempts"] != 5:
        raise RuntimeError("GATE4A1_SESSION_INCOMPLETE")
    if identity["tester_signer_status"] not in {
        "FAMILIAR_TRAIN_SIGNER", "UNSEEN_TO_TRAIN", "UNKNOWN"
    }:
        raise RuntimeError("GATE4A1_TESTER_STATUS_INVALID")

    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    glosses = [gloss for gloss, index in sorted(vocab.items(), key=lambda pair: pair[1])]
    import tensorflow as tf

    model = tf.keras.models.load_model(CHECKPOINT, compile=False, safe_mode=True)
    if model.count_params() != 192556:
        raise RuntimeError("GATE4A1_MODEL_PARAMETER_IDENTITY_FAILURE")

    attempt_dirs = sorted(path for path in session.glob("attempt_*") if path.is_dir())
    valid_dirs = []
    invalid_attempts: list[dict[str, Any]] = []
    for directory in attempt_dirs:
        summary = json.loads((directory / "attempt.json").read_text(encoding="utf-8"))
        if summary["classification"] == "VALID":
            valid_dirs.append(directory)
        else:
            invalid_attempts.append(summary)
    if len(valid_dirs) != 5:
        raise RuntimeError(f"GATE4A1_VALID_ATTEMPT_COUNT_FAILURE:{len(valid_dirs)}")

    feature_errors: list[np.ndarray] = []
    output_errors: list[np.ndarray] = []
    attempts: list[dict[str, Any]] = []
    worst_feature: dict[str, Any] = {"absolute_error": -1.0}
    worst_output: dict[str, Any] = {"absolute_error": -1.0}
    top1_mismatches = top5_membership_mismatches = top5_order_mismatches = 0
    semantic_top1 = semantic_top5 = 0
    for directory in valid_dirs:
        phone = json.loads((directory / "attempt.json").read_text(encoding="utf-8"))
        raw, raw_value = load_raw(directory / "raw_v1.json")
        reference_view = temporal_view_v2(
            raw,
            condition="dense",
            phone_completed_fps=PHONE_COMPLETED_FPS,
        )
        phone_features = read_float32(directory / "recognition_v2.f32", 96 * FEATURE_WIDTH_V2).reshape(96, FEATURE_WIDTH_V2)
        phone_mask = np.fromfile(directory / "frame_mask.u8", dtype=np.uint8).astype(bool)
        phone_output = read_float32(directory / "probabilities.f32", 236)
        if not np.array_equal(phone_mask, reference_view["mask"]):
            raise RuntimeError(f"GATE4A1_MASK_MISMATCH:{directory.name}")
        if list(phone["selected_source_indices"]) != reference_view["source_indices"].astype(int).tolist():
            raise RuntimeError(f"GATE4A1_SELECTION_MISMATCH:{directory.name}")
        if not np.array_equal(
            np.asarray(phone["selected_source_timestamps_ms"], np.float64),
            reference_view["source_timestamps_ms"].astype(np.float64),
        ):
            raise RuntimeError(f"GATE4A1_SELECTED_TIMESTAMP_MISMATCH:{directory.name}")
        feature_error = np.abs(reference_view["features"].astype(np.float64) - phone_features.astype(np.float64))
        feature_errors.append(feature_error)
        local_feature = int(np.argmax(feature_error))
        if float(feature_error.reshape(-1)[local_feature]) > worst_feature["absolute_error"]:
            worst_feature = {
                "attempt": directory.name,
                "timestep": local_feature // FEATURE_WIDTH_V2,
                "channel": local_feature % FEATURE_WIDTH_V2,
                "reference_value": float(reference_view["features"].reshape(-1)[local_feature]),
                "android_value": float(phone_features.reshape(-1)[local_feature]),
                "absolute_error": float(feature_error.reshape(-1)[local_feature]),
            }
        reference_output = model(
            [reference_view["features"][None].astype(np.float32), reference_view["mask"][None]],
            training=False,
        ).numpy()[0].astype(np.float32)
        output_error = np.abs(reference_output.astype(np.float64) - phone_output.astype(np.float64))
        output_errors.append(output_error)
        local_output = int(np.argmax(output_error))
        if float(output_error[local_output]) > worst_output["absolute_error"]:
            worst_output = {
                "attempt": directory.name,
                "output_class": local_output,
                "gloss": glosses[local_output],
                "reference_value": float(reference_output[local_output]),
                "android_value": float(phone_output[local_output]),
                "absolute_error": float(output_error[local_output]),
            }
        reference_top = topk(reference_output)
        phone_top = topk(phone_output)
        top1_mismatches += int(reference_top[0] != phone_top[0])
        top5_membership_mismatches += int(set(reference_top) != set(phone_top))
        top5_order_mismatches += int(reference_top != phone_top)
        expected = int(phone["expected_class_id"])
        semantic_top1 += int(phone_top[0] == expected)
        semantic_top5 += int(expected in phone_top)
        capture = verify_capture_semantics(phone, raw_value)
        first_dt = float(reference_view["features"][0, 348])
        selected = reference_view["source_timestamps_ms"]
        expected_dt = np.minimum(np.diff(selected) / 1000.0, 1.0).astype(np.float32)
        actual_dt = reference_view["features"][1 : len(selected), 348]
        dt_pass = first_dt == 0.0 and np.array_equal(actual_dt, expected_dt)
        capture["selected_timestamp_dt"] = "PASS" if dt_pass else "FAIL"
        if not dt_pass:
            capture["status"] = "FAIL"
        attempts.append({
            "attempt": directory.name,
            "expected_class_id": expected,
            "expected_gloss": phone["expected_gloss"],
            "valid": True,
            "duration_ms": phone["capture_duration_ms"],
            "observation_count": phone["observation_count"],
            "android_top1": glosses[phone_top[0]],
            "android_top1_probability": float(phone_output[phone_top[0]]),
            "expected_in_top5": expected in phone_top,
            "semantic_top1_correct": phone_top[0] == expected,
            "offline_top1": glosses[reference_top[0]],
            "feature_max_abs": float(feature_error.max()),
            "output_max_abs": float(output_error.max()),
            "capture_semantics": capture,
            "latency_ms": phone["latency_ms"],
        })

    feature_stats = summarize(feature_errors)
    output_stats = summarize(output_errors)
    capture_pass = all(item["capture_semantics"]["status"] == "PASS" for item in attempts)
    parity_pass = (
        feature_stats["max_abs"] <= V2_TOLERANCE
        and output_stats["max_abs"] <= OUTPUT_TOLERANCE
        and top1_mismatches == 0
        and top5_membership_mismatches == 0
        and top5_order_mismatches == 0
    )
    artifacts = {
        str(path.relative_to(session)): sha256(path)
        for path in sorted(session.rglob("*")) if path.is_file()
    }
    observations = [int(item["observation_count"]) for item in attempts]
    durations = [float(item["duration_ms"]) for item in attempts]
    rates = [count / (duration / 1000.0) for count, duration in zip(observations, durations)]
    body_rates = []
    left_rates = []
    right_rates = []
    candidate_latencies = []
    v2_latencies = []
    tflite_latencies = []
    stop_latencies = []
    for directory, item in zip(valid_dirs, attempts):
        raw_value = json.loads((directory / "raw_v1.json").read_text(encoding="utf-8"))
        body_rates.append(float(np.mean(raw_value["body_available"])))
        observed = np.asarray(raw_value["hand_observed"], bool).reshape(-1, 2)
        left_rates.append(float(np.mean(observed[:, 0])))
        right_rates.append(float(np.mean(observed[:, 1])))
        candidate_latencies.extend(float(row["total_perception_ms"]) for row in raw_value["frame_runtime"])
        v2_latencies.append(float(item["latency_ms"]["v2_construction"]))
        tflite_latencies.append(float(item["latency_ms"]["tflite_invocation"]))
        stop_latencies.append(float(item["latency_ms"]["stop_to_result"]))

    pass_items = {
        "frozen_identity": True,
        "tester_status_recorded": bool(identity["tester_signer_status"]),
        "candidate_warm_before_start": all(
            item["capture_semantics"]["candidate01_warm_before_start"]
            for item in attempts
        ),
        "source_timestamp_capture": capture_pass,
        "deterministic_inflight_drain": capture_pass,
        "no_double_sparsification": capture_pass,
        "five_valid_attempts": len(attempts) == 5,
        "host_evidence_retained": session.resolve().is_relative_to(output.parent.resolve()),
        "offline_replay": parity_pass,
        "no_crash_anr": not (session / "failure.txt").exists(),
        "no_training": True,
        "dev_not_accessed": True,
        "protected_test_not_accessed": True,
    }
    passed = all(pass_items.values())
    result = {
        "milestone": MILESTONE,
        "status": "PASS" if passed else "FAIL",
        "classification": "LIVE_PLUMBING_VALIDATED" if passed else "LIVE_PLUMBING_FAILURE",
        "tester_signer_status": identity["tester_signer_status"],
        "session": str(session.resolve()),
        "valid_attempts": len(attempts),
        "invalid_attempts": invalid_attempts,
        "attempts": attempts,
        "live_capture_summary": {
            "observation_count_min_median_max": [min(observations), percentile(observations, 50), max(observations)],
            "duration_ms_min_median_max": [min(durations), percentile(durations, 50), max(durations)],
            "observation_rate_hz_min_median_max": [min(rates), percentile(rates, 50), max(rates)],
            "body_available_rate_mean": float(np.mean(body_rates)),
            "left_observed_rate_mean": float(np.mean(left_rates)),
            "right_observed_rate_mean": float(np.mean(right_rates)),
        },
        "v2_parity": {**feature_stats, "tolerance": V2_TOLERANCE, "worst": worst_feature,
                      "mismatches": int(sum(np.count_nonzero(value > V2_TOLERANCE) for value in feature_errors))},
        "output_parity": {**output_stats, "tolerance": OUTPUT_TOLERANCE, "worst": worst_output,
                          "top1_mismatches": top1_mismatches,
                          "top5_membership_mismatches": top5_membership_mismatches,
                          "top5_order_mismatches": top5_order_mismatches},
        "semantic_diagnostic_only": {"top1_correct": semantic_top1, "top5_contains_expected": semantic_top5, "total": 5},
        "latency_ms": {
            "candidate01_p50": percentile(candidate_latencies, 50), "candidate01_p95": percentile(candidate_latencies, 95),
            "v2_p50": percentile(v2_latencies, 50), "v2_p95": percentile(v2_latencies, 95),
            "tflite_p50": percentile(tflite_latencies, 50), "tflite_p95": percentile(tflite_latencies, 95),
            "stop_to_result_p50": percentile(stop_latencies, 50), "stop_to_result_p95": percentile(stop_latencies, 95),
        },
        "artifact_sha256": artifacts,
        "pass_items": pass_items,
        "dev_accessed": False,
        "protected_test_accessed": False,
        "full_training_executed": False,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "gate4a1_live_replay_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# {MILESTONE}", "", f"**{result['classification']}**", "",
        f"Tester signer status: **{identity['tester_signer_status']}**", "",
        "## Attempts", "", "| Attempt | Expected | Observations | Android Top-1 | Expected Top-5 | V2 max abs | Output max abs |",
        "|---|---|---:|---|---|---:|---:|",
    ]
    for item in attempts:
        lines.append(
            f"| {item['attempt']} | {item['expected_gloss']} | {item['observation_count']} | "
            f"{item['android_top1']} | {item['expected_in_top5']} | {item['feature_max_abs']:.3g} | {item['output_max_abs']:.3g} |"
        )
    lines += [
        "", "## Technical parity", "",
        f"- V2 max/p95/mean abs: `{feature_stats['max_abs']:.9g}` / `{feature_stats['p95_abs']:.9g}` / `{feature_stats['mean_abs']:.9g}`",
        f"- Output max/p95/mean abs: `{output_stats['max_abs']:.9g}` / `{output_stats['p95_abs']:.9g}` / `{output_stats['mean_abs']:.9g}`",
        f"- Top-1 / Top-5 membership / Top-5 order mismatches: `{top1_mismatches}` / `{top5_membership_mismatches}` / `{top5_order_mismatches}`",
        "", "## Semantic results (diagnostic only)", "",
        f"- Top-1 correct: `{semantic_top1}/5`", f"- Expected in Top-5: `{semantic_top5}/5`", "",
        "DEV accessed: **NO**  ", "Protected TEST accessed: **NO**  ", "Full training executed: **NO**", "",
    ]
    (output / "PHASE4A_GATE4A1_LIVE_PLUMBING_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.session.resolve(), args.output.resolve())
    print(json.dumps({"status": result["status"], "classification": result["classification"]}, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
