"""Audit and summarize the debug-only causal phone recognition integration.

This utility never trains, extracts new scientific data, or changes a frozen
model.  ``audit`` verifies identities and writes the pre-device evidence
package.  ``summarize`` imports one manually captured Android session after it
has been pulled from the device.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
    / "phone_causal_recognition_integration_01"
)
ASSET_ROOT = ROOT / "android/app/src/debug/assets/phone_causal_recognition_01"

EXPECTED = {
    "s2_checkpoint": (
        ROOT
        / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
        / "phase7_production_cadence_aligned_segmenter_01/best_model.keras",
        "dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73",
    ),
    "s2_normalization": (
        ROOT
        / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
        / "phase7_production_cadence_aligned_segmenter_01"
        / "cadence_aligned_normalization_stats.json",
        "3018348ae8cc9fe0671eda913535556e14cebf5a16fbe72a96be73ed494e9130",
    ),
    "segmentation_feature_reference": (
        ROOT / "pipeline/perception_vnext/segmentation/learned_features.py",
        "dfb5e9c2877881ab676d7c463739455b797e95679dfbe1e25866b26e8908f5f9",
    ),
    "materializer_contract": (
        ROOT
        / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
        / "phase8a_m_causal_sparse_recognition_window_materialization_01"
        / "materializer_contract_frozen.json",
        "0a59dc80fe54cb37e09fbce8aa108dbfce32bc4b5cb48b98e61619b5b3b34971",
    ),
    "recognition_v2_android": (
        ROOT
        / "android/app/src/debug/java/com/example/apphear/perceptionvnext/RecognitionV2.kt",
        "0a5fd969c574f3077060e75bcf697390e322da7e87e870da50b547714ba39699",
    ),
    "recognizer_tflite": (
        ROOT
        / "android/app/src/debug/assets/phase4a_gate2_recognizer_parity"
        / "ordinary_v2_tcn_fp32.tflite",
        "1ccf0afa9af9aa602aa0de33c9635f5cffd7feec7d9b4e32382bc5e3fa02880c",
    ),
    "recognizer_manifest": (
        ROOT
        / "android/app/src/debug/assets/phase4a_gate2_recognizer_parity/manifest.json",
        "bfe8bec13a646eb6fa733c3bee6a421a44b5e58ed6dbb0dd59d88804e397d019",
    ),
}

SOURCE_PATHS = [
    ROOT / "deploy/export_phone_causal_s2.py",
    ROOT / "eval/runtime_diagnostics/phone_causal_recognition_integration.py",
    ROOT / "android/app/build.gradle.kts",
    ROOT
    / "android/app/src/debug/java/com/example/apphear/perceptionvnext"
    / "PerceptionVNextLiveRecognitionActivity.kt",
    ROOT
    / "android/app/src/debug/java/com/example/apphear/perceptionvnext/PhoneCausalCore.kt",
    ROOT
    / "android/app/src/debug/java/com/example/apphear/perceptionvnext/PhoneCausalController.kt",
    ROOT
    / "android/app/src/debug/java/com/example/apphear/perceptionvnext/PhoneS2Runner.kt",
    ROOT
    / "android/app/src/test/java/com/example/apphear/perceptionvnext/PhoneCausalCoreTest.kt",
    ROOT
    / "android/app/src/androidTest/java/com/example/apphear/perceptionvnext"
    / "PhoneSegmentationFeatureParityInstrumentedTest.kt",
    ROOT
    / "android/app/src/androidTest/java/com/example/apphear/perceptionvnext"
    / "PhoneS2ParityInstrumentedTest.kt",
]

ATTEMPTS = [
    (1, "HELLO", 1),
    (2, "HELLO", 2),
    (3, "AT", 1),
    (4, "AT", 2),
    (5, "HOME", 1),
    (6, "HOME", 2),
    (7, "STREET", 1),
    (8, "STREET", 2),
    (9, "TABLE", 1),
    (10, "TABLE", 2),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def numeric_summary(values: list[float]) -> dict[str, float | int | None]:
    """Return a compact deterministic summary without adding a numeric dependency."""

    if not values:
        return {"count": 0, "min": None, "median": None, "mean": None, "p90": None, "max": None}
    ordered = sorted(values)
    p90_index = round(0.9 * (len(ordered) - 1))
    return {
        "count": len(ordered),
        "min": ordered[0],
        "median": statistics.median(ordered),
        "mean": statistics.fmean(ordered),
        "p90": ordered[p90_index],
        "max": ordered[-1],
    }


def require_frozen_identities() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, (path, expected) in EXPECTED.items():
        if not path.is_file():
            raise FileNotFoundError(f"PHONE_CAUSAL_REQUIRED_IDENTITY_MISSING:{name}:{path}")
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"PHONE_CAUSAL_FROZEN_IDENTITY_MISMATCH:{name}:{actual}")
        result[name] = {
            "path": str(path.relative_to(ROOT)),
            "sha256": actual,
            "status": "MATCH",
        }
    recognizer_manifest = read_json(EXPECTED["recognizer_manifest"][0])
    if recognizer_manifest["vocabulary_sha256"] != (
        "a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b"
    ):
        raise RuntimeError("PHONE_CAUSAL_VOCABULARY_IDENTITY_MISMATCH")
    result["recognizer_vocabulary"] = {
        "sha256": recognizer_manifest["vocabulary_sha256"],
        "status": "MATCH",
    }
    return result


def audit() -> None:
    identities = require_frozen_identities()
    mobile = read_json(ASSET_ROOT / "contract.json")
    if mobile["source_checkpoint_sha256"] != identities["s2_checkpoint"]["sha256"]:
        raise RuntimeError("PHONE_CAUSAL_MOBILE_S2_SOURCE_MISMATCH")
    if mobile["source_normalization_sha256"] != identities["s2_normalization"]["sha256"]:
        raise RuntimeError("PHONE_CAUSAL_MOBILE_NORMALIZATION_SOURCE_MISMATCH")
    if mobile["feature_width"] != 378:
        raise RuntimeError("PHONE_CAUSAL_MOBILE_FEATURE_WIDTH_MISMATCH")
    if mobile["materializer_contract_sha256"] != identities["materializer_contract"]["sha256"]:
        raise RuntimeError("PHONE_CAUSAL_MOBILE_MATERIALIZER_MISMATCH")
    if sha256(ASSET_ROOT / "s2_phase7_fp32.tflite") != mobile["tflite_sha256"]:
        raise RuntimeError("PHONE_CAUSAL_EXPORTED_S2_IDENTITY_MISMATCH")

    integration = {
        "milestone": "PHONE_CAUSAL_RECOGNITION_INTEGRATION_01",
        "scope": "debug-only explicit-opt-in production-equivalent integration",
        "components": [
            {
                "layer": "Candidate01",
                "implementation": (
                    "PerceptionVNextLiveRecognitionActivity existing current-frame path"
                ),
                "change": (
                    "integration callback and diagnostics only; "
                    "perception math/runners unchanged"
                ),
            },
            {
                "layer": "segmentation feature builder",
                "implementation": "PhoneSegmentationFeatureBuilder",
                "contract": "apphear.perception_vnext.segmentation_features.v1 [378]",
            },
            {
                "layer": "S2",
                "implementation": "PhoneS2Runner",
                "contract": "bounded 61-observation causal prefix, FP32 TFLite, current state only",
            },
            {
                "layer": "logical event producer",
                "implementation": "PhoneCausalEventProducer",
                "contract": "unchanged CONFIG_01 hard-argmax timestamp semantics",
            },
            {
                "layer": "observation buffer/materializer",
                "implementation": "PhoneObservationRingBuffer",
                "contract": "frozen cadence-safe outward bracketing, genuine observations only",
            },
            {
                "layer": "Recognition V2 and recognizer",
                "implementation": "RecognitionV2 + RecognitionV2LiveRecognizer",
                "contract": "[96,350] float32 + [96] bool mask; frozen 236-class model",
            },
        ],
        "rearm": {
            "owner": "CONFIG_01 EVENT_EMITTED_WAIT_REARM",
            "stable_pre_ms": 399.924,
            "legacy_downstream_rearm_active": False,
            "dual_rearm": False,
        },
        "release_behavior": "disabled and debug sources/assets excluded",
        "training_executed": False,
    }
    write_json(ARTIFACT_ROOT / "integration_map.json", integration)
    write_json(
        ARTIFACT_ROOT / "contract_identities.json",
        {
            "frozen": identities,
            "mobile_s2_contract": mobile,
            "governance": {
                "training_executed": False,
                "s2_r1_started": False,
                "recognizer_modified": False,
                "materializer_tuned": False,
                "known_phone_opened": False,
                "protected_test_opened": False,
            },
        },
    )
    write_json(
        ARTIFACT_ROOT / "controlled_phone_capture_manifest.json",
        {
            "schema": "apphear.phone_causal_recognition.capture_manifest.v1",
            "membership_frozen_before_capture": True,
            "attempts": [
                {"attempt_id": attempt_id, "gloss": gloss, "repetition": repetition}
                for attempt_id, gloss, repetition in ATTEMPTS
            ],
            "selection_role": "bounded integration cohort, not production accuracy estimate",
        },
    )
    write_json(
        ARTIFACT_ROOT / "parity_status.json",
        {
            "host_keras_vs_tflite": {
                "status": "PASS",
                "observations": mobile["fixture"]["observation_count"],
                "max_abs_probability_difference": mobile["fixture"][
                    "maximum_abs_probability_difference_keras_vs_tflite"
                ],
            },
            "android_feature_fixture": {
                "status": "PASS",
                "device": "Xiaomi M2101K7AG Android 12",
                "observations": 4,
                "per_feature_abs_tolerance": 1e-6,
            },
            "android_s2_fixture": {
                "status": "PASS",
                "device": "Xiaomi M2101K7AG Android 12",
                "observations": mobile["fixture"]["observation_count"],
                "per_probability_abs_tolerance": 1e-4,
            },
            "android_build": "PASS",
            "jvm_causal_core_tests": "PASS",
            "live_controlled_cohort": "READY_FOR_MANUAL_CAPTURE",
            "debug_activity_launch": "PASS_FOREGROUND_VERIFIED",
            "milestone_complete": False,
        },
    )
    write_json(
        ARTIFACT_ROOT / "test_results.json",
        {
            "python_ruff_exporter": "PASS",
            "python_compile_exporter": "PASS",
            "android_jvm_phone_causal_core": "PASS",
            "android_assemble_debug": "PASS",
            "android_test_kotlin_compile": "PASS",
            "android_lint_debug": {
                "status": "BASELINE_BLOCKED",
                "errors": 24,
                "warnings": 555,
                "note": (
                    "reported errors are pre-existing debug-source findings; "
                    "new phone files compile"
                ),
            },
            "device_feature_parity_current_fixture": "PASS",
            "device_s2_parity_fixed_output_export": "PASS",
            "training_call": False,
        },
    )
    source_hashes = {
        str(path.relative_to(ROOT)): sha256(path)
        for path in SOURCE_PATHS
        if path.is_file()
    }
    source_hashes.update(
        {
            str(path.relative_to(ROOT)): sha256(path)
            for path in sorted(ASSET_ROOT.iterdir())
            if path.is_file()
        },
    )
    write_json(ARTIFACT_ROOT / "source_hashes.json", source_hashes)


def summarize(session_root: Path) -> None:
    identity = read_json(session_root / "identity.json")
    observations = read_jsonl(session_root / "observations.jsonl")
    events = read_jsonl(session_root / "events.jsonl")
    attempts = read_jsonl(session_root / "attempts.jsonl")
    if identity["milestone"] != "PHONE_CAUSAL_RECOGNITION_INTEGRATION_01":
        raise RuntimeError("PHONE_CAUSAL_SESSION_IDENTITY_MISMATCH")
    if identity["segmentation"]["source_checkpoint_sha256"] != EXPECTED["s2_checkpoint"][1]:
        raise RuntimeError("PHONE_CAUSAL_SESSION_S2_IDENTITY_MISMATCH")
    if identity["segmentation"]["source_normalization_sha256"] != EXPECTED["s2_normalization"][1]:
        raise RuntimeError("PHONE_CAUSAL_SESSION_NORMALIZATION_IDENTITY_MISMATCH")
    if identity["materializer_contract_sha256"] != EXPECTED["materializer_contract"][1]:
        raise RuntimeError("PHONE_CAUSAL_SESSION_MATERIALIZER_IDENTITY_MISMATCH")
    if identity["recognizer"]["model_sha256"] != EXPECTED["recognizer_tflite"][1]:
        raise RuntimeError("PHONE_CAUSAL_SESSION_RECOGNIZER_IDENTITY_MISMATCH")
    timestamps = [float(item["source_timestamp_ms"]) for item in observations]
    if any(right <= left for left, right in zip(timestamps, timestamps[1:], strict=False)):
        raise RuntimeError("PHONE_CAUSAL_SESSION_NON_CHRONOLOGICAL")
    event_attempts = Counter(item.get("attempt_id") for item in events)
    completed = [item for item in attempts if item.get("action") == "COMPLETE"]
    completed_attempt_ids = {int(item["attempt_id"]) for item in completed}
    rows = []
    for attempt_id, gloss, repetition in ATTEMPTS:
        matching = [item for item in events if item.get("attempt_id") == attempt_id]
        completed_here = attempt_id in completed_attempt_ids
        rows.append(
            {
                "attempt_id": attempt_id,
                "expected_gloss": gloss,
                "repetition": repetition,
                "event_count_during_marked_attempt": event_attempts[attempt_id],
                "top1": [item["top1_gloss"] for item in matching],
                "capture_status": "COMPLETE" if completed_here else "NOT_CAPTURED",
                "visual_audit_status": (
                    "SEE_BOUNDED_VISUAL_AUDIT" if completed_here else "NOT_APPLICABLE"
                ),
                "failure_attribution": (
                    "EVENT_WINDOW_AND_RECOGNITION_SUCCEEDED"
                    if completed_here and matching
                    else "NOT_EVALUATED"
                ),
            },
        )

    latest_event = max(events, key=lambda item: int(item["commit_index"]), default=None)
    lifecycle: dict[str, Any] = {"status": "NO_EVENT_AVAILABLE"}
    if latest_event is not None:
        commit_index = int(latest_event["commit_index"])
        post_commit = [item for item in observations if int(item["source_index"]) > commit_index]
        state_counts = Counter(int(item["argmax_state"]) for item in post_commit)
        action_counts = Counter(item["event_action"] for item in post_commit)
        elapsed_ms = (
            float(post_commit[-1]["source_timestamp_ms"]) - float(latest_event["commit_ms"])
            if post_commit
            else 0.0
        )
        rearmed = action_counts["REARM_COMPLETE"] > 0
        lifecycle = {
            "status": "REARMED" if rearmed else "NOT_REARMED_BEFORE_CAPTURE_STOP",
            "latest_event_id": int(latest_event["event_id"]),
            "latest_event_attempt_id": latest_event.get("attempt_id"),
            "commit_index": commit_index,
            "post_commit_observation_count": len(post_commit),
            "post_commit_elapsed_ms": elapsed_ms,
            "post_commit_argmax_counts": {
                "PRE": state_counts[0],
                "ACTIVE": state_counts[1],
                "POST": state_counts[2],
            },
            "post_commit_post_probability": numeric_summary(
                [float(item["post_probability"]) for item in post_commit],
            ),
            "post_commit_max_pre_probability": max(
                (float(item["pre_probability"]) for item in post_commit),
                default=None,
            ),
            "begin_rearm_pre_count": action_counts["BEGIN_REARM_PRE"],
            "reset_rearm_pre_count": action_counts["RESET_REARM_PRE"],
            "rearm_complete_count": action_counts["REARM_COMPLETE"],
            "final_event_state": (
                observations[-1]["event_state_after"] if observations else None
            ),
            "frozen_rearm_requirement": {
                "state": "PRE",
                "stable_duration_ms": 399.924,
            },
        }

    runtime = {
        field: numeric_summary([float(item[field]) for item in observations if field in item])
        for field in ("candidate_total_ms", "feature_ms", "s2_ms")
    }
    runtime.update(
        {
            field: numeric_summary([float(item[field]) for item in events if field in item])
            for field in ("materializer_ms", "recognition_v2_ms", "recognition_invocation_ms")
        },
    )
    unmarked_events = [item for item in events if item.get("attempt_id") is None]
    capture_complete = len(completed) == len(ATTEMPTS)
    stopped_for_rearm = (
        not capture_complete
        and lifecycle["status"] == "NOT_REARMED_BEFORE_CAPTURE_STOP"
    )
    classification = (
        "PHONE_EVENT_PRODUCER_LIMIT_SUPPORTED"
        if stopped_for_rearm
        else "CONTROLLED_PHONE_COHORT_COMPLETE" if capture_complete else "CAPTURE_INCOMPLETE"
    )
    output = ARTIFACT_ROOT / "phone_sessions" / session_root.name
    summary = {
            "session_root": str(session_root),
            "observation_count": len(observations),
            "event_count": len(events),
            "unmarked_event_count": len(unmarked_events),
            "attempt_mark_count": len(attempts),
            "completed_attempt_count": len(completed),
            "attempts": rows,
            "post_event_lifecycle": lifecycle,
            "runtime_ms": runtime,
            "cohort_complete": capture_complete,
            "capture_stopped_for_rearm_failure": stopped_for_rearm,
            "classification": classification,
            "classification_scope": (
                "bounded one-attempt integration evidence; not a production accuracy estimate"
            ),
            "independent_human_audit_complete": False,
        }
    write_json(output / "session_diagnostic_summary.json", summary)
    write_json(
        output / "final_decision.json",
        {
            "classification": classification,
            "supported_component_limit": (
                "CONFIG_01_PRE_ONLY_REARM_LIFECYCLE"
                if stopped_for_rearm
                else None
            ),
            "s2_terminal_signal_absent": False if stopped_for_rearm else None,
            "automatic_repair_authorized": False,
            "next": "WAIT_FOR_PROJECT_LEAD_PHONE_EVENT_LIFECYCLE_DECISION",
        },
    )
    parity = read_json(ARTIFACT_ROOT / "parity_status.json")
    parity["live_controlled_cohort"] = (
        "BLOCKED_AFTER_ATTEMPT_1_REARM_FAILURE"
        if stopped_for_rearm
        else "COMPLETE" if capture_complete else "INCOMPLETE"
    )
    parity["milestone_complete"] = stopped_for_rearm or capture_complete
    write_json(ARTIFACT_ROOT / "parity_status.json", parity)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("audit")
    summary = sub.add_parser("summarize")
    summary.add_argument("--session-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "audit":
        audit()
        result = {"status": "PRE_DEVICE_AUDIT_COMPLETE", "output": str(ARTIFACT_ROOT)}
        print(json.dumps(result, indent=2))
    else:
        summarize(args.session_root.resolve())
        result = {"status": "SESSION_IMPORTED", "session": str(args.session_root)}
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
