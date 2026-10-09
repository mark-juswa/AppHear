"""Read-only integrity and paired S2 replay for one frozen phone validation session."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics.phone_repeated_recognition_integration import (  # noqa: E402
    identity as event_identity,
)
from eval.runtime_diagnostics.phone_repeated_recognition_integration import (  # noqa: E402
    replay,
)
from eval.runtime_diagnostics.phone_s2_exact_parity_and_r2_decision import (  # noqa: E402
    comparison,
    load_capture,
    read_json,
    sha256,
)
from pipeline.perception_vnext.recognition_window_materializer import (  # noqa: E402
    LogicalSignEvent,
    materialize_recognition_window,
)
from pipeline.perception_vnext.segmentation.learned_features import (  # noqa: E402
    apply_normalization,
    derive_causal_segmentation_features,
)

BASE = ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
PHASE7 = BASE / "phase7_production_cadence_aligned_segmenter_01"
R2 = BASE / "s2_r2_continuous_domain_correction_01/main_candidate"
PACKAGE = ROOT / "android/app/src/debug/assets/phone_causal_recognition_01/s2_r2_candidate"
OUT = BASE / "s2_r2_phone_deployment_and_independent_validation_01"
EXPECTED_GLOSSES = ("HELLO", "HELLO", "HOME", "HOME", "TABLE", "TABLE")
FEATURE_TOLERANCE = 1.0e-6
NORMALIZATION_TOLERANCE = 1.0e-6
PROBABILITY_TOLERANCE = 1.0e-4


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _attempts(session: Path) -> list[dict[str, Any]]:
    markers = _jsonl(session / "attempts.jsonl")
    begun = {int(item["attempt_id"]): item for item in markers if item["action"] == "BEGIN"}
    completed = {int(item["attempt_id"]): item for item in markers if item["action"] == "COMPLETE"}
    if sorted(begun) != list(range(1, 7)) or sorted(completed) != list(range(1, 7)):
        raise ValueError("S2_R2_VALIDATION_ATTEMPT_MARKER_MISMATCH")
    rows = []
    for attempt_id, gloss in enumerate(EXPECTED_GLOSSES, 1):
        first = begun[attempt_id]
        last = completed[attempt_id]
        if first["expected_gloss"] != gloss or last["expected_gloss"] != gloss:
            raise ValueError("S2_R2_VALIDATION_GLOSS_ORDER_MISMATCH")
        start = int(first["observation_count_before_mark"])
        end = int(last["observation_count_after_drain"]) - 1
        if start > end:
            raise ValueError("S2_R2_VALIDATION_EMPTY_ATTEMPT")
        rows.append(
            {"attempt_id": attempt_id, "gloss": gloss, "start_index": start, "end_index": end}
        )
    return rows


def _predict(
    model_path: Path, norm_path: Path, features: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    import tensorflow as tf

    normalization = read_json(norm_path)
    mean = np.asarray(normalization["mean"], np.float32)
    std = np.asarray(normalization["std"], np.float32)
    normalized = apply_normalization(features, mean, std)
    model = tf.keras.models.load_model(model_path, compile=False)
    logits = np.asarray(model(normalized[None], training=False), np.float32)[0]
    shifted = logits - np.max(logits, axis=-1, keepdims=True)
    exponent = np.exp(shifted)
    return normalized, exponent / exponent.sum(axis=-1, keepdims=True)


def audit(session: Path) -> dict[str, Any]:
    capture = load_capture(session, require_full_session=False)
    identity = read_json(session / "identity.json")
    session_identity = read_json(session / "session_identity.json")
    package = read_json(PACKAGE / "contract.json")
    selected = identity["segmentation"]
    if (
        selected.get("package_id") != "S2_R2_CANDIDATE"
        or session_identity.get("s2_package_id") != "S2_R2_CANDIDATE"
    ):
        raise ValueError("S2_R2_VALIDATION_WRONG_LIVE_PACKAGE")
    if session_identity["phone_target_cohort"] != "S2_R2_VALIDATION_6":
        raise ValueError("S2_R2_VALIDATION_WRONG_COHORT")
    signer = session_identity.get("declared_validation_signer_id")
    if not isinstance(signer, str) or not signer.strip():
        raise ValueError("S2_R2_VALIDATION_SIGNER_ID_MISSING")
    if selected["source_checkpoint_sha256"] != sha256(R2 / "best_model.keras") or selected[
        "source_normalization_sha256"
    ] != sha256(R2 / "normalization.json"):
        raise ValueError("S2_R2_VALIDATION_FROZEN_SOURCE_MISMATCH")
    if selected["tflite_sha256"] != sha256(PACKAGE / "s2_r2_fp32.tflite") or selected[
        "contract_sha256"
    ] != sha256(PACKAGE / "contract.json"):
        raise ValueError("S2_R2_VALIDATION_PACKAGE_MISMATCH")
    if (
        package["source_checkpoint_sha256"] != selected["source_checkpoint_sha256"]
        or package["source_normalization_sha256"] != selected["source_normalization_sha256"]
    ):
        raise ValueError("S2_R2_VALIDATION_MODEL_NORMALIZATION_PAIR_MISMATCH")
    if (
        not identity["exact_s2_parity_capture_enabled"]
        or not session_identity["s2_exact_parity_capture_enabled"]
    ):
        raise ValueError("S2_R2_VALIDATION_EXACT_CAPTURE_DISABLED")
    attempts = _attempts(session)
    observations = _jsonl(session / "observations.jsonl")
    if len(observations) != capture.count:
        raise ValueError("S2_R2_VALIDATION_OBSERVATION_COUNT_MISMATCH")
    visual = read_json(session / "continuous_visual/evidence_summary.json")
    originals = len(list((session / "continuous_visual/originals").glob("frame_*_original.jpg")))
    if (
        visual.get("finalized_after_capture_stop") is not True
        or int(visual["verified_original_files"]) != capture.count
        or originals != capture.count
    ):
        raise ValueError("S2_R2_VALIDATION_VISUAL_EVIDENCE_INCOMPLETE")
    features = derive_causal_segmentation_features(capture.raw)
    feature_parity = comparison(features, capture.android_features, FEATURE_TOLERANCE)
    normalized, probabilities = _predict(
        R2 / "best_model.keras", R2 / "normalization.json", features
    )
    norm_parity = comparison(normalized, capture.android_normalized, NORMALIZATION_TOLERANCE)
    probability_parity = comparison(
        probabilities, capture.android_probabilities, PROBABILITY_TOLERANCE
    )
    state_mismatches = int(
        np.count_nonzero(np.argmax(probabilities, axis=1) != capture.android_argmax)
    )
    passed = all(
        [
            feature_parity["pass"],
            norm_parity["pass"],
            probability_parity["pass"],
            state_mismatches == 0,
        ]
    )
    result = {
        "schema": "apphear.s2_r2.independent_phone_integrity.v1",
        "status": "S2_R2_PHONE_CAPTURE_AND_RUNTIME_PARITY_PASS"
        if passed
        else "S2_R2_PHONE_DEPLOYMENT_PARITY_FAIL",
        "session_id": session.name,
        "declared_signer_id": signer,
        "independence_attestation_required": True,
        "observation_count": capture.count,
        "visual_original_count": originals,
        "attempts": attempts,
        "package_contract_sha256": sha256(PACKAGE / "contract.json"),
        "source_model_sha256": sha256(R2 / "best_model.keras"),
        "source_normalization_sha256": sha256(R2 / "normalization.json"),
        "feature_parity": feature_parity,
        "normalization_parity": norm_parity,
        "probability_parity": probability_parity,
        "state_mismatches": state_mismatches,
    }
    _write(OUT / session.name / "capture_integrity_and_runtime_parity.json", result)
    return result


def _materialized(timestamps: np.ndarray, event: dict[str, Any]) -> dict[str, Any]:
    logical = LogicalSignEvent(
        logical_active_start_index=int(event["logical_active_start_index"]),
        logical_active_end_index=int(event["logical_active_end_index"]),
        logical_active_start_ms=float(event["logical_active_start_ms"]),
        logical_active_end_ms=float(event["logical_active_end_ms"]),
        terminal_post_index=int(event["first_post_index"]),
        terminal_post_ms=float(event["first_post_ms"]),
        commit_index=int(event["emitted_at_index"]),
        commit_ms=float(event["emitted_at_ms"]),
    )
    window = materialize_recognition_window(timestamps, logical)
    return {
        "event": event_identity(event),
        "selected_start_index": window.selected_start_index,
        "selected_end_index": window.selected_end_index,
        "observation_count": window.selected_observation_count,
        "left_censored": window.left_censored,
        "right_censored": window.right_censored,
        "actual_pre_context_ms": window.actual_pre_context_ms,
        "actual_post_context_ms": window.actual_post_context_ms,
    }


def paired_replay(session: Path, labels_path: Path) -> dict[str, Any]:
    integrity = audit(session)
    if integrity["status"] != "S2_R2_PHONE_CAPTURE_AND_RUNTIME_PARITY_PASS":
        raise RuntimeError("S2_R2_PHONE_PARITY_REQUIRED_BEFORE_INTERPRETATION")
    labels = read_json(labels_path)
    if (
        labels.get("schema") != "apphear.s2_r2.independent_phone_human_review.v1"
        or labels.get("session_id") != session.name
        or labels.get("reviewer_blinded_to_s2_output") is not True
    ):
        raise ValueError("S2_R2_HUMAN_REVIEW_CONTRACT_MISMATCH")
    if labels.get("distinct_signer_attested_from_fit_and_checkpoint_selection") is not True:
        raise ValueError("S2_R2_SIGNER_INDEPENDENCE_NOT_ATTESTED")
    if labels.get("non_sign_review_pending") is not False:
        raise ValueError("S2_R2_NON_SIGN_VISUAL_REVIEW_PENDING")
    attempts = integrity["attempts"]
    if [item.get("attempt_id") for item in labels.get("attempts", [])] != list(range(1, 7)):
        raise ValueError("S2_R2_HUMAN_REVIEW_ATTEMPT_COUNT_MISMATCH")
    capture = load_capture(session, require_full_session=False)
    features = capture.android_features
    _, baseline_prob = _predict(
        PHASE7 / "best_model.keras", PHASE7 / "cadence_aligned_normalization_stats.json", features
    )
    _, candidate_prob = _predict(R2 / "best_model.keras", R2 / "normalization.json", features)
    timestamps = np.asarray(capture.raw.timestamp_ms, np.float64)
    branches = {}
    actual_events = _jsonl(session / "events.jsonl")
    for name, probabilities in (
        ("PHASE7_CONTROL", baseline_prob),
        ("S2_R2_CANDIDATE", candidate_prob),
    ):
        states = np.argmax(probabilities, axis=1)
        rows = [
            {
                "source_timestamp_ms": float(timestamp),
                "argmax_state": int(states[index]),
                "pre_probability": float(probabilities[index, 0]),
                "active_probability": float(probabilities[index, 1]),
                "post_probability": float(probabilities[index, 2]),
            }
            for index, timestamp in enumerate(timestamps)
        ]
        decoded = replay(rows, allow_post_rearm=True)
        events = decoded["events"]
        windows = [_materialized(timestamps, event) for event in events]
        if name == "S2_R2_CANDIDATE":
            observed = [event_identity(event) for event in actual_events]
            replayed = [event_identity(event) for event in events]
            if observed != replayed:
                raise RuntimeError("S2_R2_PHONE_REPLAY_ANDROID_EVENT_IDENTITY_MISMATCH")
            for actual, replay_window in zip(actual_events, windows, strict=True):
                if (
                    actual["materialized_start_index"] != replay_window["selected_start_index"]
                    or actual["materialized_end_index"] != replay_window["selected_end_index"]
                ):
                    raise RuntimeError("S2_R2_PHONE_MATERIALIZER_ANDROID_REPLAY_MISMATCH")
        per_attempt = []
        for marker, review in zip(attempts, labels["attempts"], strict=True):
            if review.get("gloss") != marker["gloss"]:
                raise ValueError("S2_R2_HUMAN_REVIEW_GLOSS_MISMATCH")
            active = []
            labeled_indices: set[int] = set()
            for segment in review.get("segments", []):
                start, end = int(segment["start_index"]), int(segment["end_index"])
                if not marker["start_index"] <= start <= end <= marker["end_index"]:
                    raise ValueError("S2_R2_HUMAN_SEGMENT_OUTSIDE_ATTEMPT")
                overlap = labeled_indices.intersection(range(start, end + 1))
                if overlap:
                    raise ValueError("S2_R2_HUMAN_SEGMENT_OVERLAP")
                labeled_indices.update(range(start, end + 1))
                if segment["label"] == "ACTIVE":
                    active.extend(range(start, end + 1))
                elif segment["label"] not in {"PRE", "POST", "UNCERTAIN_EXCLUDE"}:
                    raise ValueError("S2_R2_HUMAN_SEGMENT_LABEL_INVALID")
            active = sorted(set(active))
            if not active and not review.get("ambiguous", False):
                raise ValueError("S2_R2_HUMAN_ACTIVE_LABEL_MISSING")
            selected = [
                window
                for window in windows
                if marker["start_index"]
                <= window["event"]["logical_active_start_index"]
                <= marker["end_index"]
            ]
            recalls = (
                [
                    sum(
                        window["selected_start_index"] <= index <= window["selected_end_index"]
                        for index in active
                    )
                    / len(active)
                    for window in selected
                ]
                if active
                else []
            )
            recognition = []
            if name == "S2_R2_CANDIDATE" and active:
                for actual in actual_events:
                    if (
                        marker["start_index"]
                        <= actual["logical_active_start_index"]
                        <= marker["end_index"]
                    ):
                        containment = sum(
                            actual["materialized_start_index"]
                            <= index
                            <= actual["materialized_end_index"]
                            for index in active
                        ) / len(active)
                        if containment >= 0.90:
                            recognition.append(
                                {
                                    "event_id": actual["event_id"],
                                    "top1_gloss": actual["top1_gloss"],
                                    "expected_rank": actual.get("expected_rank"),
                                    "top1_probability": actual["top1_probability"],
                                }
                            )
            per_attempt.append(
                {
                    "attempt_id": marker["attempt_id"],
                    "gloss": marker["gloss"],
                    "human_label_status": "UNCERTAIN_EXCLUDE" if not active else "SCORABLE",
                    "human_active_observations": len(active),
                    "s2_active_observations": int(np.count_nonzero(states[active] == 1))
                    if active
                    else None,
                    "s2_active_recall": float(np.mean(states[active] == 1)) if active else None,
                    "acquired_active": bool(np.any(states[active] == 1)) if active else None,
                    "event_count": len(selected),
                    "windows": selected,
                    "best_human_active_containment": max(recalls, default=0.0) if active else None,
                    "premature_cut": (not recalls or max(recalls) < 0.90) if active else None,
                    "severe_cut": (not recalls or max(recalls) < 0.60) if active else None,
                    "recognition_for_usable_windows": recognition,
                }
            )
        non_sign = []
        for interval in labels.get("confirmed_non_sign_intervals", []):
            start, end = int(interval["start_index"]), int(interval["end_index"])
            if not 0 <= start <= end < capture.count:
                raise ValueError("S2_R2_NON_SIGN_INTERVAL_OUT_OF_BOUNDS")
            non_sign.append(
                {
                    "start_index": start,
                    "end_index": end,
                    "active_observations": int(np.count_nonzero(states[start : end + 1] == 1)),
                    "observation_count": end - start + 1,
                    "events_starting_in_interval": sum(
                        start <= event["logical_active_start_index"] <= end for event in events
                    ),
                }
            )
        branches[name] = {
            "per_attempt": per_attempt,
            "confirmed_non_sign_intervals": non_sign,
            "event_count": len(events),
            "rearm_complete_count": decoded["rearm_complete_count"],
            "gap_reset_count": decoded["gap_reset_count"],
            "final_state": decoded["final_state"],
        }
    result = {
        "schema": "apphear.s2_r2.independent_phone_paired_replay.v1",
        "session_id": session.name,
        "same_observation_count": capture.count,
        "human_review_sha256": sha256(labels_path),
        "branches": branches,
        "training_executed": False,
        "threshold_tuning": False,
        "production_promotion": False,
    }
    _write(OUT / session.name / "paired_temporal_result.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("audit", "paired-replay"))
    parser.add_argument("session", type=Path)
    parser.add_argument("--human-review", type=Path)
    args = parser.parse_args()
    if args.command == "paired-replay":
        if args.human_review is None:
            parser.error("--human-review is required for paired-replay")
        result = paired_replay(args.session, args.human_review)
    else:
        result = audit(args.session)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
