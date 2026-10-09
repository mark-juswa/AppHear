"""Gate-2 FP32 export and TRAIN-only host parity for the frozen V2 TCN."""
# ruff: noqa: E501

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MILESTONE = "PHASE_4A_GATE_2_RECOGNIZER_RUNTIME_PARITY_01"
ARTIFACTS = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "phase4a_gate2_recognizer_runtime_parity_01"
)
CONTRACT = ARTIFACTS / "parity_contract.json"
GATE1_ASSETS = ROOT / "android/app/src/debug/assets"
GATE1_MANIFEST = GATE1_ASSETS / "phase4a_v2_parity/manifest.json"
ANDROID_ASSETS = ROOT / "android/app/src/debug/assets/phase4a_gate2_recognizer_parity"
CHECKPOINT = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "tcn_v2_run_01/best.keras"
)
VOCAB = ROOT / "artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1/vocab.json"
MODEL_NAME = "ordinary_v2_tcn_fp32.tflite"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def topk(values: np.ndarray, count: int = 5) -> list[int]:
    return np.argsort(-values, kind="stable")[:count].astype(int).tolist()


def stats(errors: np.ndarray) -> dict[str, float | int]:
    flat = np.asarray(errors, dtype=np.float64).reshape(-1)
    return {
        "count": int(flat.size),
        "max_abs": float(np.max(flat)) if flat.size else 0.0,
        "p95_abs": float(np.percentile(flat, 95)) if flat.size else 0.0,
        "mean_abs": float(np.mean(flat)) if flat.size else 0.0,
    }


def model_contract(model: Any, tf: Any, keras: Any) -> dict[str, Any]:
    return {
        "name": model.name,
        "tensorflow_version": tf.__version__,
        "keras_version": keras.__version__,
        "parameter_count": int(model.count_params()),
        "inputs": [
            {
                "name": tensor.name,
                "shape": [int(v) if v is not None else None for v in tensor.shape],
                "dtype": str(tensor.dtype),
            }
            for tensor in model.inputs
        ],
        "outputs": [
            {
                "name": name,
                "tensor_name": tensor.name,
                "shape": [int(v) if v is not None else None for v in tensor.shape],
                "dtype": str(tensor.dtype),
                "semantics": "probabilities_softmax",
            }
            for name, tensor in zip(model.output_names, model.outputs, strict=True)
        ],
        "architecture": {
            "encoder": "mask-aware causal TCN",
            "blocks": 4,
            "channels": 64,
            "dilations": [1, 2, 4, 8],
            "kernel": 3,
            "dropout": 0.3,
            "pooling": "GlobalAveragePooling1D with frame_mask",
            "classes": 236,
        },
    }


def validate_identity(contract: dict[str, Any], gate1: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {
        "checkpoint_sha256": sha256(CHECKPOINT),
        "vocabulary_sha256": sha256(VOCAB),
        "gate1_manifest_sha256": sha256(GATE1_MANIFEST),
    }
    source_paths = {
        "RecognitionV2.kt": ROOT
        / "android/app/src/debug/java/com/example/apphear/perceptionvnext/RecognitionV2.kt",
        "RecognitionV2ParityVerifier.kt": ROOT
        / "android/app/src/debug/java/com/example/apphear/perceptionvnext/RecognitionV2ParityVerifier.kt",
        "RecognitionV2ParityInstrumentedTest.kt": ROOT
        / "android/app/src/androidTest/java/com/example/apphear/perceptionvnext/RecognitionV2ParityInstrumentedTest.kt",
        "RecognitionV2JvmParityTest.kt": ROOT
        / "android/app/src/test/java/com/example/apphear/perceptionvnext/RecognitionV2JvmParityTest.kt",
    }
    checks["gate1_source_sha256"] = {name: sha256(path) for name, path in source_paths.items()}
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    ordered = sorted(vocab.items(), key=lambda item: item[1])
    failures: list[str] = []
    if checks["checkpoint_sha256"] != contract["source_checkpoint_sha256"]:
        failures.append("source_checkpoint")
    if checks["vocabulary_sha256"] != contract["vocabulary_sha256"]:
        failures.append("vocabulary")
    if checks["gate1_manifest_sha256"] != contract["gate1_manifest_sha256"]:
        failures.append("gate1_manifest")
    for name, expected in contract["gate1_source_pins"].items():
        if checks["gate1_source_sha256"].get(name) != expected:
            failures.append(f"gate1_source:{name}")
    if gate1.get("feature_schema") != "apphear.perception_vnext.recognition.v2":
        failures.append("gate1_feature_schema")
    if gate1.get("shape") != [96, 350]:
        failures.append("gate1_shape")
    if len(ordered) != 236 or [value for _, value in ordered] != list(range(236)):
        failures.append("vocabulary_indices")
    checks["vocabulary_size"] = len(ordered)
    checks["class_index_to_gloss"] = [key for key, _ in ordered]
    checks["failures"] = failures
    if failures:
        raise RuntimeError("GATE2_IDENTITY_FAILURE:" + ",".join(failures))
    return checks


def load_view(view: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    tensor_path = GATE1_ASSETS / view["tensor_asset"]
    if sha256(tensor_path) != view["tensor_sha256"]:
        raise RuntimeError(f"GATE2_TENSOR_HASH_FAILURE:{tensor_path}")
    features = np.fromfile(tensor_path, dtype="<f4").reshape(96, 350)
    mask = np.asarray(view["mask"], dtype=np.bool_)
    return features, mask


def tflite_io(interpreter: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    inputs = interpreter.get_input_details()
    outputs = interpreter.get_output_details()
    feature = next(item for item in inputs if list(item["shape"])[-2:] == [96, 350])
    mask = next(item for item in inputs if list(item["shape"])[-1:] == [96])
    output = next(item for item in outputs if list(item["shape"])[-1:] == [236])
    return feature, mask, output


def tensor_detail(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": item["name"],
        "shape": [int(value) for value in item["shape"]],
        "shape_signature": [int(value) for value in item["shape_signature"]],
        "dtype": np.dtype(item["dtype"]).name,
        "index": int(item["index"]),
    }


def invoke(
    interpreter: Any,
    feature: dict[str, Any],
    mask: dict[str, Any],
    output: dict[str, Any],
    x: np.ndarray,
    m: np.ndarray,
) -> np.ndarray:
    interpreter.set_tensor(feature["index"], x[np.newaxis].astype(feature["dtype"], copy=False))
    interpreter.set_tensor(mask["index"], m[np.newaxis].astype(mask["dtype"], copy=False))
    interpreter.invoke()
    return interpreter.get_tensor(output["index"])[0].astype(np.float32, copy=True)


def garbage_padding(features: np.ndarray, mask: np.ndarray) -> np.ndarray:
    result = features.copy()
    for row in np.flatnonzero(~mask):
        channel = np.arange(350, dtype=np.float32)
        result[row] = (
            np.sin(np.float32(row + 1) * (channel + np.float32(3.0))) * np.float32(3.25)
            + (np.mod(channel, np.float32(7.0)) - np.float32(3.0))
        ).astype(np.float32)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true", help="Convert and run host parity")
    args = parser.parse_args()
    if not args.prepare:
        parser.error("--prepare is required")

    # Import from the checkpoint-compatible, repository-recorded environment only.
    import keras
    import tensorflow as tf

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    gate1 = json.loads(GATE1_MANIFEST.read_text(encoding="utf-8"))
    identity = validate_identity(contract, gate1)
    model = tf.keras.models.load_model(CHECKPOINT, compile=False, safe_mode=True)
    source_contract = model_contract(model, tf, keras)
    if source_contract["parameter_count"] != 192556:
        raise RuntimeError("GATE2_PARAMETER_COUNT_FAILURE")
    if source_contract["inputs"] != [
        {"name": "features", "shape": [None, 96, 350], "dtype": "float32"},
        {"name": "frame_mask", "shape": [None, 96], "dtype": "bool"},
    ]:
        raise RuntimeError("GATE2_SOURCE_INPUT_CONTRACT_FAILURE")
    if source_contract["outputs"][0]["shape"] != [None, 236]:
        raise RuntimeError("GATE2_SOURCE_OUTPUT_CONTRACT_FAILURE")

    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = []
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
    model_bytes = converter.convert()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    ANDROID_ASSETS.mkdir(parents=True, exist_ok=True)
    artifact_model = ARTIFACTS / MODEL_NAME
    android_model = ANDROID_ASSETS / MODEL_NAME
    artifact_model.write_bytes(model_bytes)
    shutil.copyfile(artifact_model, android_model)

    interpreter = tf.lite.Interpreter(model_content=model_bytes, num_threads=4)
    interpreter.allocate_tensors()
    feature_input, mask_input, output_tensor = tflite_io(interpreter)
    if np.dtype(feature_input["dtype"]) != np.dtype(np.float32):
        raise RuntimeError("GATE2_TFLITE_FEATURE_DTYPE_FAILURE")
    if np.dtype(mask_input["dtype"]) != np.dtype(np.bool_):
        raise RuntimeError("GATE2_TFLITE_MASK_DTYPE_FAILURE")
    if np.dtype(output_tensor["dtype"]) != np.dtype(np.float32):
        raise RuntimeError("GATE2_TFLITE_OUTPUT_DTYPE_FAILURE")

    operators = sorted({item["op_name"] for item in interpreter._get_ops_details()})
    if any(name.upper().startswith("FLEX") for name in operators):
        raise RuntimeError("GATE2_SELECT_TF_OPS_FAILURE")

    expected_fixture_ids = contract["parity_population"]["fixture_ids"]
    fixture_by_id = {item["fixture_id"]: item for item in gate1["fixtures"]}
    if list(fixture_by_id) != expected_fixture_ids:
        raise RuntimeError("GATE2_FIXTURE_SET_FAILURE")
    glosses = identity["class_index_to_gloss"]
    all_errors: list[np.ndarray] = []
    per_view: list[dict[str, Any]] = []
    output_entries: list[dict[str, Any]] = []
    top1_mismatches = 0
    top5_membership_mismatches = 0
    top5_order_mismatches = 0
    worst: dict[str, Any] = {"absolute_error": -1.0}

    for fixture_id in expected_fixture_ids:
        fixture = fixture_by_id[fixture_id]
        for condition in contract["parity_population"]["conditions"]:
            view = fixture["views"][condition]
            features, mask = load_view(view)
            keras_output = (
                model([features[np.newaxis], mask[np.newaxis]], training=False)
                .numpy()[0]
                .astype(np.float32)
            )
            lite_output = invoke(
                interpreter, feature_input, mask_input, output_tensor, features, mask
            )
            if keras_output.shape != (236,) or lite_output.shape != (236,):
                raise RuntimeError("GATE2_OUTPUT_SHAPE_FAILURE")
            error = np.abs(keras_output.astype(np.float64) - lite_output.astype(np.float64))
            all_errors.append(error)
            local_worst = int(np.argmax(error))
            if float(error[local_worst]) > worst["absolute_error"]:
                worst = {
                    "fixture_id": fixture_id,
                    "sample_id": fixture["sample_id"],
                    "condition": condition,
                    "output_index": local_worst,
                    "gloss": glosses[local_worst],
                    "reference_value": float(keras_output[local_worst]),
                    "tflite_value": float(lite_output[local_worst]),
                    "absolute_error": float(error[local_worst]),
                }
            keras_top = topk(keras_output)
            lite_top = topk(lite_output)
            top1_mismatches += int(keras_top[0] != lite_top[0])
            top5_membership_mismatches += int(set(keras_top) != set(lite_top))
            top5_order_mismatches += int(keras_top != lite_top)
            expected_name = f"{fixture_id}_{condition}_keras_output.f32"
            expected_path = ANDROID_ASSETS / expected_name
            keras_output.astype("<f4").tofile(expected_path)
            per_view.append(
                {
                    "fixture_id": fixture_id,
                    "sample_id": fixture["sample_id"],
                    "condition": condition,
                    "statistics": stats(error),
                    "keras_top5_indices": keras_top,
                    "keras_top5_glosses": [glosses[index] for index in keras_top],
                    "host_tflite_top5_indices": lite_top,
                    "host_tflite_top5_glosses": [glosses[index] for index in lite_top],
                    "top1_match": keras_top[0] == lite_top[0],
                    "top5_membership_match": set(keras_top) == set(lite_top),
                    "top5_order_match": keras_top == lite_top,
                }
            )
            output_entries.append(
                {
                    "fixture_id": fixture_id,
                    "sample_id": fixture["sample_id"],
                    "condition": condition,
                    "feature_asset": view["tensor_asset"],
                    "feature_sha256": view["tensor_sha256"],
                    "mask": view["mask"],
                    "real_length": view["real_length"],
                    "keras_output_asset": f"phase4a_gate2_recognizer_parity/{expected_name}",
                    "keras_output_sha256": sha256(expected_path),
                    "keras_top5_indices": keras_top,
                    "keras_top5_glosses": [glosses[index] for index in keras_top],
                }
            )

    mask_entries: list[dict[str, Any]] = []
    mask_results: list[dict[str, Any]] = []
    mask_failures = 0
    for item in contract["mask_padding_fixtures"]:
        fixture = fixture_by_id[item["fixture_id"]]
        view = fixture["views"][item["condition"]]
        features, mask = load_view(view)
        if bool(np.all(mask)):
            raise RuntimeError("GATE2_MASK_FIXTURE_HAS_NO_PADDING")
        garbage = garbage_padding(features, mask)
        valid_rows = np.flatnonzero(mask)
        if not np.array_equal(features[valid_rows], garbage[valid_rows]):
            raise RuntimeError("GATE2_GARBAGE_CHANGED_VALID_ROWS")
        keras_base = (
            model([features[np.newaxis], mask[np.newaxis]], training=False)
            .numpy()[0]
            .astype(np.float32)
        )
        keras_garbage = (
            model([garbage[np.newaxis], mask[np.newaxis]], training=False)
            .numpy()[0]
            .astype(np.float32)
        )
        lite_base = invoke(interpreter, feature_input, mask_input, output_tensor, features, mask)
        lite_garbage = invoke(interpreter, feature_input, mask_input, output_tensor, garbage, mask)
        keras_error = np.abs(keras_base.astype(np.float64) - keras_garbage.astype(np.float64))
        lite_error = np.abs(lite_base.astype(np.float64) - lite_garbage.astype(np.float64))
        tolerance = float(contract["preregistered_tolerances"]["mask_padding_invariance_max_abs"])
        passed = float(keras_error.max()) <= tolerance and float(lite_error.max()) <= tolerance
        mask_failures += int(not passed)
        asset_name = f"{item['fixture_id']}_{item['condition']}_padded_garbage.f32"
        asset_path = ANDROID_ASSETS / asset_name
        garbage.astype("<f4").tofile(asset_path)
        mask_entries.append(
            {
                "fixture_id": item["fixture_id"],
                "sample_id": fixture["sample_id"],
                "condition": item["condition"],
                "feature_asset": view["tensor_asset"],
                "feature_sha256": view["tensor_sha256"],
                "garbage_feature_asset": f"phase4a_gate2_recognizer_parity/{asset_name}",
                "garbage_feature_sha256": sha256(asset_path),
                "mask": view["mask"],
                "keras_baseline_output": keras_base.astype(float).tolist(),
                "keras_garbage_output": keras_garbage.astype(float).tolist(),
            }
        )
        mask_results.append(
            {
                "fixture_id": item["fixture_id"],
                "condition": item["condition"],
                "keras": stats(keras_error),
                "host_tflite": stats(lite_error),
                "pass": passed,
            }
        )

    global_error = np.concatenate(all_errors)
    host_tolerance = float(contract["preregistered_tolerances"]["keras_vs_host_tflite_max_abs"])
    host_pass = (
        float(global_error.max()) <= host_tolerance
        and top1_mismatches == 0
        and top5_membership_mismatches == 0
        and mask_failures == 0
    )
    model_sha = sha256(artifact_model)
    gate2_manifest = {
        "milestone": MILESTONE,
        "contract_sha256": sha256(CONTRACT),
        "feature_schema": gate1["feature_schema"],
        "source_checkpoint_sha256": identity["checkpoint_sha256"],
        "model_asset": f"phase4a_gate2_recognizer_parity/{MODEL_NAME}",
        "model_sha256": model_sha,
        "vocabulary_sha256": identity["vocabulary_sha256"],
        "class_index_to_gloss": glosses,
        "input_shape": [1, 96, 350],
        "mask_shape": [1, 96],
        "output_shape": [1, 236],
        "output_semantics": "probabilities_softmax",
        "runtime": contract["android_runtime"],
        "tolerances": contract["preregistered_tolerances"],
        "views": output_entries,
        "mask_padding_views": mask_entries,
        "dev_accessed": False,
        "protected_test_accessed": False,
    }
    gate2_manifest_path = ANDROID_ASSETS / "manifest.json"
    write_json(gate2_manifest_path, gate2_manifest)

    conversion = {
        "milestone": MILESTONE,
        "source_checkpoint": str(CHECKPOINT),
        "source_checkpoint_sha256": identity["checkpoint_sha256"],
        "conversion_script": str(Path(__file__).resolve()),
        "conversion_script_sha256": sha256(Path(__file__)),
        "source_model": source_contract,
        "tflite_model": {
            "path": str(artifact_model),
            "android_asset": str(android_model),
            "sha256": model_sha,
            "bytes": artifact_model.stat().st_size,
            "precision": "FP32",
            "quantization": "NONE",
            "supported_ops_policy": ["TFLITE_BUILTINS"],
            "select_tf_ops": False,
            "operators": operators,
            "inputs": [tensor_detail(item) for item in interpreter.get_input_details()],
            "outputs": [tensor_detail(item) for item in interpreter.get_output_details()],
            "signatures": interpreter.get_signature_list(),
        },
        "identity": identity,
        "android_manifest": str(gate2_manifest_path),
        "android_manifest_sha256": sha256(gate2_manifest_path),
        "dev_accessed": False,
        "protected_test_accessed": False,
        "training_executed": False,
    }
    host_report = {
        "milestone": MILESTONE,
        "status": "PASS" if host_pass else "FAIL",
        "preregistered_tolerance": host_tolerance,
        "global": stats(global_error),
        "worst": worst,
        "top1_mismatches": top1_mismatches,
        "top5_membership_mismatches": top5_membership_mismatches,
        "top5_order_mismatches": top5_order_mismatches,
        "mask_padding_invariance": {
            "status": "PASS" if mask_failures == 0 else "FAIL",
            "tolerance": contract["preregistered_tolerances"]["mask_padding_invariance_max_abs"],
            "views": mask_results,
        },
        "per_view": per_view,
        "dev_accessed": False,
        "protected_test_accessed": False,
    }
    write_json(ARTIFACTS / "conversion_identity.json", conversion)
    write_json(ARTIFACTS / "host_parity.json", host_report)
    print(json.dumps({"conversion": conversion, "host_parity": host_report}, indent=2))
    return 0 if host_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
