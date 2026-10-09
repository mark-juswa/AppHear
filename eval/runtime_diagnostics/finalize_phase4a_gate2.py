"""Consolidate the frozen Keras/host-TFLite/Android-TFLite Gate-2 evidence."""
# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import tensorflow as tf

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "phase4a_gate2_recognizer_runtime_parity_01"
)
ANDROID_ASSETS = ROOT / "android/app/src/debug/assets"
GATE2_ASSETS = ANDROID_ASSETS / "phase4a_gate2_recognizer_parity"
CONTRACT = ARTIFACTS / "parity_contract.json"
CONVERSION = ARTIFACTS / "conversion_identity.json"
HOST = ARTIFACTS / "host_parity.json"
ANDROID = ARTIFACTS / "android_tflite_parity.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_floats(path: Path) -> np.ndarray:
    return np.fromfile(path, dtype="<f4")


def topk(values: np.ndarray) -> list[int]:
    return np.argsort(-values, kind="stable")[:5].astype(int).tolist()


def summarize(values: list[np.ndarray]) -> dict[str, float | int]:
    flat = np.concatenate(values).astype(np.float64) if values else np.zeros(0)
    return {
        "count": int(flat.size),
        "max_abs": float(flat.max()) if flat.size else 0.0,
        "p95_abs": float(np.percentile(flat, 95)) if flat.size else 0.0,
        "mean_abs": float(flat.mean()) if flat.size else 0.0,
    }


def invoke(interpreter: Any, x: np.ndarray, mask: np.ndarray) -> np.ndarray:
    inputs = interpreter.get_input_details()
    feature = next(item for item in inputs if list(item["shape"])[-2:] == [96, 350])
    mask_input = next(item for item in inputs if list(item["shape"])[-1:] == [96])
    output = next(
        item for item in interpreter.get_output_details() if list(item["shape"])[-1:] == [236]
    )
    interpreter.set_tensor(feature["index"], x.reshape(1, 96, 350).astype(np.float32))
    interpreter.set_tensor(mask_input["index"], mask.reshape(1, 96).astype(np.bool_))
    interpreter.invoke()
    return interpreter.get_tensor(output["index"])[0].astype(np.float32)


def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    conversion = json.loads(CONVERSION.read_text(encoding="utf-8"))
    host_report = json.loads(HOST.read_text(encoding="utf-8"))
    android_report = json.loads(ANDROID.read_text(encoding="utf-8"))
    manifest_path = Path(conversion["android_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    model_path = Path(conversion["tflite_model"]["path"])
    if sha256(model_path) != conversion["tflite_model"]["sha256"]:
        raise RuntimeError("GATE2_FINAL_MODEL_HASH_FAILURE")
    if sha256(manifest_path) != conversion["android_manifest_sha256"]:
        raise RuntimeError("GATE2_FINAL_MANIFEST_HASH_FAILURE")

    android_outputs = {
        (item["fixture_id"], item["condition"]): np.asarray(
            item["android_tflite_output"], dtype=np.float32
        )
        for item in android_report["full_output_vectors"]
    }
    interpreter = tf.lite.Interpreter(model_path=str(model_path), num_threads=4)
    interpreter.allocate_tensors()
    errors: dict[str, dict[str, list[np.ndarray]]] = {
        "keras_vs_host": {"dense": [], "phone_01_sparse": []},
        "keras_vs_android": {"dense": [], "phone_01_sparse": []},
        "host_vs_android": {"dense": [], "phone_01_sparse": []},
    }
    mismatch = {key: {"top1": 0, "top5_membership": 0, "top5_order": 0} for key in errors}
    worst: dict[str, dict[str, Any]] = {key: {"absolute_error": -1.0} for key in errors}
    for item in manifest["views"]:
        key = (item["fixture_id"], item["condition"])
        x = read_floats(ANDROID_ASSETS / item["feature_asset"])
        mask = np.asarray(item["mask"], dtype=np.bool_)
        keras_output = read_floats(ANDROID_ASSETS / item["keras_output_asset"])
        host_output = invoke(interpreter, x, mask)
        android_output = android_outputs[key]
        vectors = {
            "keras_vs_host": (keras_output, host_output),
            "keras_vs_android": (keras_output, android_output),
            "host_vs_android": (host_output, android_output),
        }
        for comparison, (reference, candidate) in vectors.items():
            difference = np.abs(reference.astype(np.float64) - candidate.astype(np.float64))
            errors[comparison][item["condition"]].append(difference)
            index = int(np.argmax(difference))
            if float(difference[index]) > worst[comparison]["absolute_error"]:
                worst[comparison] = {
                    "fixture_id": item["fixture_id"],
                    "sample_id": item["sample_id"],
                    "condition": item["condition"],
                    "output_index": index,
                    "gloss": manifest["class_index_to_gloss"][index],
                    "reference_value": float(reference[index]),
                    "candidate_value": float(candidate[index]),
                    "absolute_error": float(difference[index]),
                }
            reference_top = topk(reference)
            candidate_top = topk(candidate)
            mismatch[comparison]["top1"] += int(reference_top[0] != candidate_top[0])
            mismatch[comparison]["top5_membership"] += int(set(reference_top) != set(candidate_top))
            mismatch[comparison]["top5_order"] += int(reference_top != candidate_top)

    three_way: dict[str, Any] = {}
    for comparison in errors:
        all_values = errors[comparison]["dense"] + errors[comparison]["phone_01_sparse"]
        three_way[comparison] = {
            "global": summarize(all_values),
            "dense": summarize(errors[comparison]["dense"]),
            "phone_01_sparse": summarize(errors[comparison]["phone_01_sparse"]),
            "worst": worst[comparison],
            **mismatch[comparison],
        }

    tolerance = contract["preregistered_tolerances"]
    identity = conversion["identity"]
    source_pins = {
        **identity["gate1_source_sha256"],
        "gate1_manifest.json": identity["gate1_manifest_sha256"],
        "export_v2_tcn_gate2.py": conversion["conversion_script_sha256"],
        "RecognitionV2TfliteParityVerifier.kt": sha256(
            ROOT
            / "android/app/src/debug/java/com/example/apphear/perceptionvnext/RecognitionV2TfliteParityVerifier.kt"
        ),
        "RecognitionV2TfliteParityInstrumentedTest.kt": sha256(
            ROOT
            / "android/app/src/androidTest/java/com/example/apphear/perceptionvnext/RecognitionV2TfliteParityInstrumentedTest.kt"
        ),
        "gate2_android_manifest.json": conversion["android_manifest_sha256"],
        "android_tflite_parity.json": sha256(ANDROID),
    }
    pass_items = {
        "source_checkpoint_identity": identity["checkpoint_sha256"]
        == contract["source_checkpoint_sha256"],
        "conversion_identity_recorded": bool(conversion["tflite_model"]["sha256"]),
        "output_dimensions_236": conversion["tflite_model"]["outputs"][0]["shape"] == [1, 236],
        "vocabulary_identity": identity["vocabulary_sha256"] == contract["vocabulary_sha256"],
        "host_numerical_parity": host_report["status"] == "PASS"
        and three_way["keras_vs_host"]["global"]["max_abs"]
        <= tolerance["keras_vs_host_tflite_max_abs"],
        "android_numerical_parity": android_report["status"] == "PASS"
        and three_way["keras_vs_android"]["global"]["max_abs"]
        <= tolerance["keras_vs_android_tflite_max_abs"],
        "top1_exact": three_way["keras_vs_host"]["top1"] == 0
        and three_way["keras_vs_android"]["top1"] == 0,
        "top5_membership_exact": three_way["keras_vs_host"]["top5_membership"] == 0
        and three_way["keras_vs_android"]["top5_membership"] == 0,
        "mask_padding_invariance": host_report["mask_padding_invariance"]["status"] == "PASS"
        and android_report["mask_padding_invariance"]["status"] == "PASS",
        "dev_not_accessed": not host_report["dev_accessed"] and not android_report["dev_accessed"],
        "protected_test_not_accessed": not host_report["protected_test_accessed"]
        and not android_report["protected_test_accessed"],
        "training_not_executed": not android_report["training_executed"],
    }
    passed = all(pass_items.values())
    decision = {
        "milestone": "PHASE_4A_GATE_2_RECOGNIZER_RUNTIME_PARITY_01",
        "status": "PASS" if passed else "FAIL",
        "classification": "RECOGNIZER_RUNTIME_PARITY_PASS"
        if passed
        else "RECOGNIZER_RUNTIME_PARITY_FAIL",
        "gate_criteria": pass_items,
        "source_pins": source_pins,
        "repository_identity_before_gate2": contract["repository_identity_before_gate2"],
        "source_model": conversion["source_model"],
        "tflite_model": conversion["tflite_model"],
        "parity_population": contract["parity_population"],
        "preregistered_tolerances": tolerance,
        "three_way_parity": three_way,
        "host_mask_padding_invariance": host_report["mask_padding_invariance"],
        "android_mask_padding_invariance": android_report["mask_padding_invariance"],
        "android_device": {
            key: android_report[key]
            for key in [
                "device_manufacturer",
                "device_model",
                "android_version",
                "tflite_runtime_version",
                "runtime_configuration",
                "latency",
            ]
        },
        "full_training_executed": False,
        "live_phone_recognition_executed": False,
        "dev_accessed": False,
        "protected_test_accessed": False,
        "next_authorized_boundary": (
            "PHASE_4A_GATE_3_KNOWN_TRAIN_END_TO_END_REPLAY" if passed else None
        ),
    }
    (ARTIFACTS / "gate2_decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    md = f"""# PHASE_4A_GATE_2_RECOGNIZER_RUNTIME_PARITY_01

## Decision

**{decision["classification"]}**

The frozen ordinary Recognition-V2 TCN converted to a standard-builtins-only FP32 TFLite model and reproduced the frozen Keras probabilities on host and on the physical Xiaomi phone within the preregistered tolerances. No training, live-camera inference, DEV access, or protected-TEST access occurred.

## Identities

- source checkpoint SHA-256: `{identity["checkpoint_sha256"]}`
- vocabulary SHA-256: `{identity["vocabulary_sha256"]}`
- TFLite SHA-256: `{conversion["tflite_model"]["sha256"]}`
- TFLite bytes: `{conversion["tflite_model"]["bytes"]}`
- conversion script SHA-256: `{conversion["conversion_script_sha256"]}`
- Gate-1 `RecognitionV2.kt` SHA-256: `{identity["gate1_source_sha256"]["RecognitionV2.kt"]}`
- Gate-1 manifest SHA-256: `{identity["gate1_manifest_sha256"]}`
- repository HEAD before Gate 2: `{contract["repository_identity_before_gate2"]["head"]}`
- repository branch: `{contract["repository_identity_before_gate2"]["branch"]}`
- pre-Gate-2 working tree clean: `{str(contract["repository_identity_before_gate2"]["working_tree_clean"]).lower()}`

## Source model contract

- inputs: `features [None,96,350] float32`; `frame_mask [None,96] bool`
- output: `gloss_probabilities [None,236] float32` softmax probabilities
- parameters: `{conversion["source_model"]["parameter_count"]}`
- architecture: four-block, 64-channel causal TCN; dilations `[1,2,4,8]`; kernel `3`; dropout `0.3`; mask-aware global-average pooling

## TFLite contract

- inputs: `features [1,96,350] float32`; `frame_mask [1,96] bool`
- output: `[1,236] float32` probabilities
- quantization: none
- operator requirement: standard TFLite builtins only; Select TF Ops: no

## Three-way parity

| Comparison | Max abs | P95 abs | Mean abs | Top-1 mismatch | Top-5 membership mismatch | Top-5 order mismatch |
|---|---:|---:|---:|---:|---:|---:|
| Keras vs host TFLite | {three_way["keras_vs_host"]["global"]["max_abs"]:.9g} | {three_way["keras_vs_host"]["global"]["p95_abs"]:.9g} | {three_way["keras_vs_host"]["global"]["mean_abs"]:.9g} | {three_way["keras_vs_host"]["top1"]} | {three_way["keras_vs_host"]["top5_membership"]} | {three_way["keras_vs_host"]["top5_order"]} |
| Keras vs Android TFLite | {three_way["keras_vs_android"]["global"]["max_abs"]:.9g} | {three_way["keras_vs_android"]["global"]["p95_abs"]:.9g} | {three_way["keras_vs_android"]["global"]["mean_abs"]:.9g} | {three_way["keras_vs_android"]["top1"]} | {three_way["keras_vs_android"]["top5_membership"]} | {three_way["keras_vs_android"]["top5_order"]} |
| Host vs Android TFLite | {three_way["host_vs_android"]["global"]["max_abs"]:.9g} | {three_way["host_vs_android"]["global"]["p95_abs"]:.9g} | {three_way["host_vs_android"]["global"]["mean_abs"]:.9g} | {three_way["host_vs_android"]["top1"]} | {three_way["host_vs_android"]["top5_membership"]} | {three_way["host_vs_android"]["top5_order"]} |

Preregistered limits were `1e-5` for Keras-vs-host and `1e-4` for Keras-vs-Android. The population was the exact Gate-1 TRAIN-only corpus: 10 dense and 10 PHONE_01-sparse tensors.

## Mask and padding

Keras, host TFLite, and Android TFLite all passed the preregistered `1e-6` padded-garbage invariance check. All four cases produced zero output change and unchanged Top-5 ordering.

## Physical Android runtime

- device: `{android_report["device_manufacturer"]} {android_report["device_model"]}`, Android `{android_report["android_version"]}`
- TFLite runtime: `{android_report["tflite_runtime_version"]}`
- CPU threads: `{android_report["runtime_configuration"]["cpu_threads"]}`
- XNNPACK requested: yes
- GPU/NNAPI: no/no
- latency after `{android_report["latency"]["warmups"]}` warmups over `{android_report["latency"]["measurements"]}` invocations: p50 `{android_report["latency"]["p50_ms"]:.3f} ms`, p95 `{android_report["latency"]["p95_ms"]:.3f} ms`, max `{android_report["latency"]["max_ms"]:.3f} ms`

## Boundary

- full training executed: NO
- live phone recognition executed: NO
- DEV accessed: NO
- protected TEST accessed: NO
- next authorized boundary: `{decision["next_authorized_boundary"]}`
"""
    (ARTIFACTS / "PHASE_4A_GATE_2_RECOGNIZER_RUNTIME_PARITY_REPORT.md").write_text(
        md, encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": decision["status"],
                "classification": decision["classification"],
                "three_way_parity": three_way,
                "decision_sha256": sha256(ARTIFACTS / "gate2_decision.json"),
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
