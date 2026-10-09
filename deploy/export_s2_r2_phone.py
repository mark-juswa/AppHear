"""Export the single frozen S2-R2 checkpoint as a debug-only phone package.

Conversion and parity only: this module never fits or changes the Keras model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import tensorflow as tf

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
CANDIDATE = BASE / "s2_r2_continuous_domain_correction_01/main_candidate"
MODEL = CANDIDATE / "best_model.keras"
NORMALIZATION = CANDIDATE / "normalization.json"
FREEZE = CANDIDATE / "candidate_freeze.json"
PHONE_FEATURES = (
    ROOT
    / "phone_pull_s2_exact_parity/session_20260921T153138Z"
    / "s2_exact_parity/android_features.f32"
)
PHONE_MANIFEST = PHONE_FEATURES.parent / "manifest.json"
ASSETS = ROOT / "android/app/src/debug/assets/phone_causal_recognition_01/s2_r2_candidate"
MODEL_SHA = "b6f8b52cece72f0b6f5b802a4ea583060d923e90a6b951059e7013114c8fc151"
NORMALIZATION_SHA = "65d885f62eaca6f11a596302d304f63149795ddaf01e702f1e6a36dd7da5c005"
FEATURE_SCHEMA = "apphear.perception_vnext.segmentation_features.v1"
WIDTH = 378
RECEPTIVE_FIELD = 61
TOLERANCE = 1.0e-4


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_sources() -> tuple[dict, dict, np.ndarray]:
    if sha256(MODEL) != MODEL_SHA or sha256(NORMALIZATION) != NORMALIZATION_SHA:
        raise RuntimeError("S2_R2_FROZEN_SOURCE_IDENTITY_MISMATCH")
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    if (
        freeze["identities"]["model_sha256"] != MODEL_SHA
        or freeze["identities"]["fit_normalization_sha256"] != NORMALIZATION_SHA
        or freeze["selected_epoch"] != 7
        or freeze["training_runs"] != 1
    ):
        raise RuntimeError("S2_R2_FREEZE_MISMATCH")
    normalization = json.loads(NORMALIZATION.read_text(encoding="utf-8"))
    if (
        normalization["feature_schema"] != FEATURE_SCHEMA
        or len(normalization["mean"]) != WIDTH
        or len(normalization["std"]) != WIDTH
        or normalization["cal_dev_validation_influenced_statistics"]
    ):
        raise RuntimeError("S2_R2_NORMALIZATION_CONTRACT_MISMATCH")
    capture = json.loads(PHONE_MANIFEST.read_text(encoding="utf-8"))
    if capture["feature_schema"] != FEATURE_SCHEMA or capture["feature_width"] != WIDTH:
        raise RuntimeError("S2_R2_PHONE_FIXTURE_SCHEMA_MISMATCH")
    if sha256(PHONE_FEATURES) != capture["files"]["android_features.f32"]["sha256"]:
        raise RuntimeError("S2_R2_PHONE_FIXTURE_HASH_MISMATCH")
    features = np.fromfile(PHONE_FEATURES, dtype="<f4").reshape(-1, WIDTH)
    if len(features) != capture["observation_count"] or not np.isfinite(features).all():
        raise RuntimeError("S2_R2_PHONE_FIXTURE_SHAPE_MISMATCH")
    return normalization, capture, features


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits, axis=-1, keepdims=True)
    values = np.exp(shifted)
    return values / np.sum(values, axis=-1, keepdims=True)


def export() -> dict:
    normalization, capture, features = verify_sources()
    model = tf.keras.models.load_model(MODEL, compile=False)
    if (
        model.input_shape != (None, None, WIDTH)
        or model.output_shape != (None, None, 3)
        or model.count_params() != 123_779
    ):
        raise RuntimeError("S2_R2_MODEL_CONTRACT_MISMATCH")
    mean = np.asarray(normalization["mean"], dtype=np.float32)
    std = np.asarray(normalization["std"], dtype=np.float32)
    if not np.isfinite(std).all() or np.any(std <= 0):
        raise RuntimeError("S2_R2_INVALID_NORMALIZATION_STD")
    normalized = ((features - mean) / std).astype(np.float32)
    keras_logits = np.asarray(model(normalized[None], training=False), np.float32)[0]
    keras_prob = softmax(keras_logits)

    mobile = tf.keras.Model(model.input, model.output[:, -1, :], name="s2_r2_mobile_last")
    converter = tf.lite.TFLiteConverter.from_keras_model(mobile)
    converter.optimizations = []
    converter.target_spec.supported_types = [tf.float32]
    model_bytes = converter.convert()
    ASSETS.mkdir(parents=True, exist_ok=True)
    model_path = ASSETS / "s2_r2_fp32.tflite"
    model_path.write_bytes(model_bytes)
    norm_path = ASSETS / "normalization.json"
    norm_path.write_text(
        json.dumps(
            {
                "schema": normalization["schema"],
                "feature_schema": FEATURE_SCHEMA,
                "mean": normalization["mean"],
                "std": normalization["std"],
                "source_sha256": NORMALIZATION_SHA,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    interpreter = tf.lite.Interpreter(model_path=str(model_path), num_threads=1)
    result = np.empty_like(keras_prob)
    for end in range(1, len(normalized) + 1):
        prefix = normalized[max(0, end - RECEPTIVE_FIELD) : end]
        input_index = interpreter.get_input_details()[0]["index"]
        interpreter.resize_tensor_input(input_index, [1, len(prefix), WIDTH], strict=False)
        interpreter.allocate_tensors()
        input_index = interpreter.get_input_details()[0]["index"]
        output_index = interpreter.get_output_details()[0]["index"]
        interpreter.set_tensor(input_index, prefix[None])
        interpreter.invoke()
        result[end - 1] = softmax(np.asarray(interpreter.get_tensor(output_index), np.float32))[0]
    differences = np.max(np.abs(result - keras_prob), axis=1)
    state_mismatches = int(
        np.count_nonzero(np.argmax(result, axis=1) != np.argmax(keras_prob, axis=1))
    )
    maximum = float(np.max(differences))
    if maximum > TOLERANCE or state_mismatches:
        raise RuntimeError(f"S2_R2_HOST_TFLITE_PARITY_FAILED:{maximum}:{state_mismatches}")

    raw_feature_path = ASSETS / "phone_parity_raw_features.f32"
    feature_path = ASSETS / "phone_parity_normalized_features.f32"
    probability_path = ASSETS / "phone_parity_probabilities.f32"
    raw_feature_path.write_bytes(features.astype("<f4", copy=False).tobytes())
    feature_path.write_bytes(normalized.astype("<f4", copy=False).tobytes())
    probability_path.write_bytes(result.astype("<f4", copy=False).tobytes())
    contract = {
        "schema": "apphear.phone_causal_recognition.s2_mobile_contract.v1",
        "milestone": "S2_R2_PHONE_DEPLOYMENT_AND_INDEPENDENT_VALIDATION_01",
        "package_id": "S2_R2_CANDIDATE",
        "source_checkpoint_sha256": MODEL_SHA,
        "source_normalization_sha256": NORMALIZATION_SHA,
        "tflite_sha256": sha256(model_path),
        "normalization_asset_sha256": sha256(norm_path),
        "feature_schema": FEATURE_SCHEMA,
        "feature_width": WIDTH,
        "state_order": ["PRE_IDLE", "ACTIVE_SIGN", "POST_RECOVERY"],
        "input_dtype": "FLOAT32",
        "input_shape_signature": [1, -1, WIDTH],
        "output_dtype": "FLOAT32",
        "output_shape_signature": [1, 3],
        "receptive_field_observations": RECEPTIVE_FIELD,
        "causal_runtime": "bounded rolling prefix; last output only",
        "training_executed": False,
        "quantization": "NONE_FP32",
        "fixture": {
            "source_session": "session_20260921T153138Z",
            "source_feature_sha256": capture["files"]["android_features.f32"]["sha256"],
            "observation_count": len(normalized),
            "raw_features_asset": raw_feature_path.name,
            "raw_features_sha256": sha256(raw_feature_path),
            "features_asset": feature_path.name,
            "features_sha256": sha256(feature_path),
            "probabilities_asset": probability_path.name,
            "probabilities_sha256": sha256(probability_path),
            "maximum_abs_probability_difference_keras_vs_tflite": maximum,
            "argmax_state_mismatches": state_mismatches,
        },
    }
    contract_path = ASSETS / "contract.json"
    contract_path.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"contract_sha256": sha256(contract_path), **contract}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("verify-sources", "export"))
    args = parser.parse_args()
    if args.command == "verify-sources":
        _, capture, features = verify_sources()
        print(
            json.dumps(
                {
                    "status": "S2_R2_FROZEN_SOURCES_VERIFIED",
                    "observations": len(features),
                    "capture_schema": capture["schema"],
                },
                indent=2,
            )
        )
    else:
        print(json.dumps(export(), indent=2, sort_keys=True))
