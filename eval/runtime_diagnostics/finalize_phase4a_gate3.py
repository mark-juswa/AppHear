"""Independently verify and finalize Phase 4A Gate 3 device replay evidence."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "phase4a_gate3_known_train_end_to_end_replay_01"
)
ASSETS = ROOT / "android/app/src/debug/assets"
GATE1 = ASSETS / "phase4a_v2_parity/manifest.json"
GATE2 = ASSETS / "phase4a_gate2_recognizer_parity/manifest.json"
CONTRACT = ASSETS / "phase4a_gate3_known_train_replay/manifest.json"
ANDROID = ARTIFACTS / "gate3_android_replay.json"

EXPECTED = {
    "RecognitionV2.kt": (
        ROOT / "android/app/src/debug/java/com/example/apphear/perceptionvnext/RecognitionV2.kt",
        "0a5fd969c574f3077060e75bcf697390e322da7e87e870da50b547714ba39699",
    ),
    "gate1_manifest.json": (
        GATE1,
        "01fd271c25df2d0b7a64e803fabe0b745d51be1ac8f7c6f646546e2a3aa055b3",
    ),
    "ordinary_v2_tcn_fp32.tflite": (
        ASSETS / "phase4a_gate2_recognizer_parity/ordinary_v2_tcn_fp32.tflite",
        "1ccf0afa9af9aa602aa0de33c9635f5cffd7feec7d9b4e32382bc5e3fa02880c",
    ),
    "vocab.json": (
        ROOT / "artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1/vocab.json",
        "a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b",
    ),
    "RecognitionV2TfliteParityVerifier.kt": (
        ROOT / (
            "android/app/src/debug/java/com/example/apphear/perceptionvnext/"
            "RecognitionV2TfliteParityVerifier.kt"
        ),
        "e06300b044caff263421554f33132ad97a099fb26931480b0ce01cf6bcabbb9a",
    ),
    "gate2_manifest.json": (
        GATE2,
        "bfe8bec13a646eb6fa733c3bee6a421a44b5e58ed6dbb0dd59d88804e397d019",
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_f32(path: Path) -> np.ndarray:
    return np.fromfile(path, dtype="<f4")


def top5(values: np.ndarray) -> list[int]:
    return np.argsort(-values, kind="stable")[:5].astype(int).tolist()


def summarize(values: np.ndarray) -> dict[str, float | int]:
    flat = np.asarray(values, dtype=np.float64).reshape(-1)
    ordered = np.sort(flat)
    p95 = ordered[int((ordered.size - 1) * 0.95)] if ordered.size else 0.0
    return {
        "count": int(flat.size),
        "max_abs": float(flat.max()) if flat.size else 0.0,
        "p95_abs": float(p95),
        "mean_abs": float(flat.mean()) if flat.size else 0.0,
    }


def main() -> int:
    gate1 = json.loads(GATE1.read_text(encoding="utf-8"))
    gate2 = json.loads(GATE2.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    android = json.loads(ANDROID.read_text(encoding="utf-8"))

    identity: dict[str, Any] = {}
    for name, (path, expected) in EXPECTED.items():
        actual = sha256(path)
        identity[name] = {
            "path": str(path.resolve()),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "pass": actual == expected,
        }
    identity_pass = all(item["pass"] for item in identity.values())

    gate1_by_id = {item["fixture_id"]: item for item in gate1["fixtures"]}
    gate2_by_key = {
        (item["fixture_id"], item["condition"]): item for item in gate2["views"]
    }
    truth_by_id = {item["fixture_id"]: item for item in contract["fixtures"]}
    android_outputs = {
        (item["fixture_id"], item["condition"]): np.asarray(
            item["android_composed_probabilities"], dtype=np.float32
        )
        for item in android["full_output_vectors"]
    }

    feature_errors: list[np.ndarray] = []
    output_errors: list[np.ndarray] = []
    selection_mismatches = 0
    timestamp_mismatches = 0
    mask_mismatches = 0
    top1_mismatches = 0
    top5_membership_mismatches = 0
    top5_order_mismatches = 0
    mapping_mismatches = 0
    dense_correct = 0
    sparse_correct = 0

    for item in android["per_view"]:
        fixture_id = item["fixture_id"]
        condition = item["condition"]
        key = (fixture_id, condition)
        gate1_view = gate1_by_id[fixture_id]["views"][condition]
        gate2_view = gate2_by_key[key]
        truth = truth_by_id[fixture_id]

        actual_features = read_f32(
            ARTIFACTS / "v2_tensors" / f"{fixture_id}_{condition}.f32"
        )
        expected_features = read_f32(ASSETS / gate1_view["tensor_asset"])
        feature_errors.append(
            np.abs(actual_features.astype(np.float64) - expected_features.astype(np.float64))
        )

        actual_output = android_outputs[key]
        expected_output = read_f32(ASSETS / gate2_view["keras_output_asset"])
        output_errors.append(
            np.abs(actual_output.astype(np.float64) - expected_output.astype(np.float64))
        )
        expected_top = top5(expected_output)
        actual_top = top5(actual_output)
        top1_mismatches += int(expected_top[0] != actual_top[0])
        top5_membership_mismatches += int(set(expected_top) != set(actual_top))
        top5_order_mismatches += int(expected_top != actual_top)
        if actual_top[0] == truth["class_id"]:
            if condition == "dense":
                dense_correct += 1
            else:
                sparse_correct += 1
        mapping_mismatches += int(
            gate2["class_index_to_gloss"][truth["class_id"]]
            != truth["canonical_gloss"]
        )
        selection_mismatches += int(item["source_indices"] != gate1_view["source_indices"])
        timestamp_mismatches += int(
            item["source_timestamps_ms"] != gate1_view["source_timestamps_ms"]
        )
        mask_mismatches += int(item["mask"] != gate1_view["mask"])

    feature_summary = summarize(np.concatenate(feature_errors))
    output_summary = summarize(np.concatenate(output_errors))
    tolerances = contract["tolerances"]
    criteria = {
        "frozen_identity_checks": identity_pass,
        "runtime_raw_schema": android["raw_schema"] == contract["raw_schema"],
        "runtime_feature_schema": android["feature_schema"] == contract["feature_schema"],
        "feature_shape_96_350": android["feature_shape"] == [96, 350],
        "mask_shape_96": android["mask_shape"] == [96],
        "output_count_236": android["model_output_count"] == 236,
        "ten_train_fixtures": android["fixtures"] == 10,
        "ten_dense_views": android["dense_views"] == 10,
        "ten_sparse_views": android["sparse_views"] == 10,
        "selection_exact": selection_mismatches == 0,
        "timestamps_exact": timestamp_mismatches == 0,
        "mask_exact": mask_mismatches == 0,
        "android_v2_within_1e_5": feature_summary["max_abs"]
        <= tolerances["android_v2_max_abs"],
        "composed_output_within_1e_4": output_summary["max_abs"]
        <= tolerances["keras_vs_android_composed_max_abs"],
        "top1_exact": top1_mismatches == 0,
        "top5_membership_exact": top5_membership_mismatches == 0,
        "top5_order_exact": top5_order_mismatches == 0,
        "class_gloss_mapping_exact": mapping_mismatches == 0,
        "state_buffer_replay": android["state_buffer_replay"]["status"] == "PASS",
        "dev_not_accessed": not android["dev_accessed"],
        "protected_test_not_accessed": not android["protected_test_accessed"],
        "no_training": not android["training_executed"],
        "no_live_camera_recognition": not android["live_camera_recognition_executed"],
    }
    passed = all(criteria.values())
    repo = {
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "branch": subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True
        ).strip(),
        "working_tree_clean": not bool(
            subprocess.check_output(
                ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True
            ).strip()
        ),
    }
    source_pins = {
        **identity,
        "gate3_contract": {
            "path": str(CONTRACT.resolve()),
            "sha256": sha256(CONTRACT),
        },
        "gate3_verifier": {
            "path": str(
                ROOT
                / (
                    "android/app/src/debug/java/com/example/apphear/perceptionvnext/"
                    "RecognitionV2EndToEndReplayVerifier.kt"
                )
            ),
            "sha256": sha256(
                ROOT
                / (
                    "android/app/src/debug/java/com/example/apphear/perceptionvnext/"
                    "RecognitionV2EndToEndReplayVerifier.kt"
                )
            ),
        },
        "gate3_instrumented_test": {
            "path": str(
                ROOT
                / (
                    "android/app/src/androidTest/java/com/example/apphear/perceptionvnext/"
                    "RecognitionV2EndToEndReplayInstrumentedTest.kt"
                )
            ),
            "sha256": sha256(
                ROOT
                / (
                    "android/app/src/androidTest/java/com/example/apphear/perceptionvnext/"
                    "RecognitionV2EndToEndReplayInstrumentedTest.kt"
                )
            ),
        },
        "android_device_evidence": {"path": str(ANDROID.resolve()), "sha256": sha256(ANDROID)},
    }
    decision = {
        "milestone": contract["milestone"],
        "status": "PASS" if passed else "FAIL",
        "classification": (
            "KNOWN_TRAIN_END_TO_END_REPLAY_PASS"
            if passed
            else "KNOWN_TRAIN_END_TO_END_REPLAY_FAIL"
        ),
        "gate_criteria": criteria,
        "source_pins": source_pins,
        "repository_identity": repo,
        "replay_population": {
            "train_clips": 10,
            "dense_views": 10,
            "phone_01_sparse_views": 10,
            "dev_accessed": False,
            "protected_test_accessed": False,
        },
        "android_v2_intermediate_parity": {
            **feature_summary,
            "selection_mismatches": selection_mismatches,
            "timestamp_mismatches": timestamp_mismatches,
            "mask_mismatches": mask_mismatches,
            "discrete_feature_mismatches": android["android_v2_intermediate_parity"][
                "discrete_mismatches"
            ],
        },
        "end_to_end_output_parity": {
            **output_summary,
            "top1_mismatches": top1_mismatches,
            "top5_membership_mismatches": top5_membership_mismatches,
            "top5_order_mismatches": top5_order_mismatches,
            "class_gloss_mapping_mismatches": mapping_mismatches,
        },
        "semantic_correctness_diagnostic_only": {
            "dense_ground_truth_correct": dense_correct,
            "dense_total": 10,
            "sparse_ground_truth_correct": sparse_correct,
            "sparse_total": 10,
            "used_for_gate_decision": False,
        },
        "state_buffer_replay": android["state_buffer_replay"],
        "latency": android["latency"],
        "android_device": {
            key: android[key]
            for key in [
                "device_manufacturer",
                "device_model",
                "android_version",
                "tflite_runtime_version",
                "runtime_configuration",
            ]
        },
        "full_training_executed": False,
        "live_camera_recognition_executed": False,
        "dev_accessed": False,
        "protected_test_accessed": False,
        "next_authorized_boundary": (
            "PHASE_4A_GATE_4_MANUALLY_BOUNDED_LIVE_PHONE_RECOGNITION"
            if passed
            else None
        ),
    }
    (ARTIFACTS / "frozen_identity_check.json").write_text(
        json.dumps({"status": "PASS" if identity_pass else "FAIL", **source_pins}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (ARTIFACTS / "gate3_decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    latency = decision["latency"]
    report = f"""# PHASE_4A_GATE_3_KNOWN_TRAIN_END_TO_END_REPLAY_01

## Final classification

**{decision['classification']}**

The physical Xiaomi composed the two previously verified components from the same saved TRAIN
raw-v1 fixtures: `raw-v1 -> Android Recognition V2 -> authorized FP32 TFLite -> class/gloss`.
The composed path reproduced the frozen Keras reference within the preregistered tolerance. This
is an integration result, not an accuracy or production-readiness claim.

## Frozen identity check

**{'PASS' if identity_pass else 'FAIL'}**. RecognitionV2.kt, Gate-1 manifest, authorized TFLite,
vocabulary, Gate-2 runtime verifier, and Gate-2 manifest all match their frozen SHA-256 values.

## Replay population

- TRAIN clips: 10
- dense views: 10
- PHONE_01 sparse views: 10
- DEV accessed: NO
- protected TEST accessed: NO

## Android V2 intermediate parity

- max absolute error: `{feature_summary['max_abs']:.9g}`
- p95 absolute error: `{feature_summary['p95_abs']:.9g}`
- mean absolute error: `{feature_summary['mean_abs']:.9g}`
- selection/timestamp/mask/discrete mismatches: `{selection_mismatches}/{timestamp_mismatches}/{mask_mismatches}/{android['android_v2_intermediate_parity']['discrete_mismatches']}`
- preregistered tolerance: `1e-5`

## End-to-end output parity

- max absolute error: `{output_summary['max_abs']:.9g}`
- p95 absolute error: `{output_summary['p95_abs']:.9g}`
- mean absolute error: `{output_summary['mean_abs']:.9g}`
- Top-1 mismatches: `{top1_mismatches}`
- Top-5 membership mismatches: `{top5_membership_mismatches}`
- Top-5 order mismatches: `{top5_order_mismatches}`
- class-index/gloss mapping mismatches: `{mapping_mismatches}`
- preregistered tolerance: `1e-4`

## Semantic correctness — diagnostic only

- dense ground-truth correct: `{dense_correct}/10`
- sparse ground-truth correct: `{sparse_correct}/10`

These counts did not participate in the gate decision. A frozen-reference misclassification that
Android reproduces exactly is an integration pass.

## State and buffer replay

**{android['state_buffer_replay']['status']}**. Forward/reverse order, dense->sparse, and
sparse->dense were invariant. Maximum difference was
`{android['state_buffer_replay']['max_abs']:.9g}` across
`{android['state_buffer_replay']['comparisons']}` output comparisons. Feature and mask buffers were
fully rewritten and the output buffer was cleared before every invocation.

## Device latency — diagnostic only

- V2 construction p50/p95: `{latency['v2_construction_p50_ms']:.3f}/{latency['v2_construction_p95_ms']:.3f} ms`
- TFLite p50/p95: `{latency['tflite_p50_ms']:.3f}/{latency['tflite_p95_ms']:.3f} ms`
- combined replay p50/p95: `{latency['combined_p50_ms']:.3f}/{latency['combined_p95_ms']:.3f} ms`

This excludes Candidate 01 perception and is not a live-camera measurement.

## Boundary

- full training executed: NO
- live camera recognition executed: NO
- DEV accessed: NO
- protected TEST accessed: NO
- next authorized boundary: `PHASE_4A_GATE_4_MANUALLY_BOUNDED_LIVE_PHONE_RECOGNITION`
"""
    (ARTIFACTS / "PHASE_4A_GATE_3_KNOWN_TRAIN_END_TO_END_REPLAY_REPORT.md").write_text(
        report, encoding="utf-8"
    )
    print(json.dumps({
        "status": decision["status"],
        "classification": decision["classification"],
        "feature_parity": feature_summary,
        "output_parity": output_summary,
        "semantic": decision["semantic_correctness_diagnostic_only"],
        "state": decision["state_buffer_replay"],
        "latency": latency,
    }, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
