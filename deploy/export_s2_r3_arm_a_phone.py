"""Export S2-R3 Arm A epoch 10 as a debug-only, hash-pinned phone S2 package.

Conversion and parity only: this module never fits or changes the Keras model. The parity
fixture is the exact prior-phone observation stream the S2-R2 export used (the committed,
hash-pinned S2-R2 debug asset), so both research packages are compared on identical input.

Arm A ended with status NO_ELIGIBLE_EPOCH; epoch 10 is its recorded diagnostic fallback.
This package is a research candidate for debug capture only, never a production default.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import tensorflow as tf

from deploy.export_s2_r2_phone import (
    FEATURE_SCHEMA,
    RECEPTIVE_FIELD,
    TOLERANCE,
    WIDTH,
    sha256,
    softmax,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_RELATIVE = Path(
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/s2_r3_arm_a_01"
)
MODEL_NAME = "epoch_10.keras"
SELECTED_EPOCH = 10
MODEL_SHA = "17915b023694cec1c85f10f96b44608c95f06ef655c49b7d1453c3a4a47b1c7c"
NORMALIZATION_SHA = "754e5e0e05e012333cd96170ba63602c26d7ab2a8b87ae8e3af99d76ed1268dc"
PACKAGE_ID = "ARM_A_E10_CANDIDATE"
ASSET_ROOT = "phone_causal_recognition_01/s2_r3_arm_a_e10_candidate"
ASSETS = ROOT / "android/app/src/debug/assets" / ASSET_ROOT
# Prior-phone fixture: committed alongside the frozen S2-R2 package (session_20260921T153138Z).
S2_R2_CONTRACT = (
    ROOT / "android/app/src/main/assets/phone_causal_recognition_01/s2_r2_candidate/contract.json"
)
FIXTURE_ASSET = "phone_causal_recognition_01/s2_r2_candidate/phone_parity_raw_features.f32"
FIXTURE_PATH = ROOT / "android/app/src/debug/assets" / FIXTURE_ASSET
FIXTURE_SHA = "17ed546b61bdb3750dcdc130166211484b8fe45ae210df88325fa972079f7618"
FIXTURE_SESSION = "session_20260921T153138Z"
FIXTURE_OBSERVATIONS = 669


def verify_sources(source_root: Path) -> tuple[Path, dict, dict, np.ndarray]:
    source = source_root / SOURCE_RELATIVE
    model = source / MODEL_NAME
    normalization_path = source / "normalization.json"
    if sha256(model) != MODEL_SHA or sha256(normalization_path) != NORMALIZATION_SHA:
        raise RuntimeError("ARM_A_E10_SOURCE_IDENTITY_MISMATCH")
    training = json.loads((source / "training_result.json").read_text(encoding="utf-8"))
    if (
        training["milestone"] != "S2_R3_ARM_A_01"
        or training["normalization_sha256"] != NORMALIZATION_SHA
        or training["diagnostic_fallback_epoch"] != SELECTED_EPOCH
        or training["protected_test_accessed"]
        or training["gate_inputs_used_for_training_or_selection"]
    ):
        raise RuntimeError("ARM_A_E10_TRAINING_RECORD_MISMATCH")
    normalization = json.loads(normalization_path.read_text(encoding="utf-8"))
    if (
        normalization["feature_schema"] != FEATURE_SCHEMA
        or len(normalization["mean"]) != WIDTH
        or len(normalization["std"]) != WIDTH
        or normalization["cal_or_gate_influenced_statistics"]
    ):
        raise RuntimeError("ARM_A_E10_NORMALIZATION_CONTRACT_MISMATCH")
    s2_r2 = json.loads(S2_R2_CONTRACT.read_text(encoding="utf-8"))["fixture"]
    if (
        s2_r2["raw_features_sha256"] != FIXTURE_SHA
        or s2_r2["source_session"] != FIXTURE_SESSION
        or sha256(FIXTURE_PATH) != FIXTURE_SHA
    ):
        raise RuntimeError("ARM_A_E10_PHONE_FIXTURE_HASH_MISMATCH")
    features = np.fromfile(FIXTURE_PATH, dtype="<f4").reshape(-1, WIDTH)
    if len(features) != FIXTURE_OBSERVATIONS or not np.isfinite(features).all():
        raise RuntimeError("ARM_A_E10_PHONE_FIXTURE_SHAPE_MISMATCH")
    return model, training, normalization, features


def export(source_root: Path) -> dict:
    model_path_source, training, normalization, features = verify_sources(source_root)
    model = tf.keras.models.load_model(model_path_source, compile=False)
    if (
        model.input_shape != (None, None, WIDTH)
        or model.output_shape != (None, None, 3)
        or model.count_params() != 123_779
    ):
        raise RuntimeError("ARM_A_E10_MODEL_CONTRACT_MISMATCH")
    mean = np.asarray(normalization["mean"], dtype=np.float32)
    std = np.asarray(normalization["std"], dtype=np.float32)
    if not np.isfinite(std).all() or np.any(std <= 0):
        raise RuntimeError("ARM_A_E10_INVALID_NORMALIZATION_STD")
    normalized = ((features - mean) / std).astype(np.float32)
    keras_logits = np.asarray(model(normalized[None], training=False), np.float32)[0]
    keras_prob = softmax(keras_logits)

    mobile = tf.keras.Model(model.input, model.output[:, -1, :], name="s2_r3_arm_a_mobile_last")
    converter = tf.lite.TFLiteConverter.from_keras_model(mobile)
    converter.optimizations = []
    converter.target_spec.supported_types = [tf.float32]
    model_bytes = converter.convert()
    ASSETS.mkdir(parents=True, exist_ok=True)
    model_path = ASSETS / "s2_r3_arm_a_e10_fp32.tflite"
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
        raise RuntimeError(f"ARM_A_E10_HOST_TFLITE_PARITY_FAILED:{maximum}:{state_mismatches}")

    feature_path = ASSETS / "phone_parity_normalized_features.f32"
    probability_path = ASSETS / "phone_parity_probabilities.f32"
    feature_path.write_bytes(normalized.astype("<f4", copy=False).tobytes())
    probability_path.write_bytes(result.astype("<f4", copy=False).tobytes())
    argmax = np.argmax(result, axis=1)
    contract = {
        "schema": "apphear.phone_causal_recognition.s2_mobile_contract.v1",
        "milestone": "S2_R3_ARM_A_E10_PHONE_DEBUG_PACKAGE_01",
        "package_id": PACKAGE_ID,
        "research_only": True,
        "source_training_milestone": training["milestone"],
        "source_training_status": training["status"],
        "source_selected_epoch": SELECTED_EPOCH,
        "source_selection_basis": "diagnostic_fallback_epoch",
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
            "source_session": FIXTURE_SESSION,
            "source_feature_sha256": FIXTURE_SHA,
            "observation_count": len(normalized),
            "raw_features_asset_path": FIXTURE_ASSET,
            "raw_features_sha256": FIXTURE_SHA,
            "features_asset": feature_path.name,
            "features_sha256": sha256(feature_path),
            "probabilities_asset": probability_path.name,
            "probabilities_sha256": sha256(probability_path),
            "maximum_abs_probability_difference_keras_vs_tflite": maximum,
            "argmax_state_mismatches": state_mismatches,
            "tflite_argmax_state_counts": [int(np.count_nonzero(argmax == s)) for s in range(3)],
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
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT,
        help="checkout holding the git-ignored artifacts/ tree (default: this checkout)",
    )
    args = parser.parse_args()
    if args.command == "verify-sources":
        _, training, _, features = verify_sources(args.source_root)
        print(
            json.dumps(
                {
                    "status": "ARM_A_E10_SOURCES_VERIFIED",
                    "observations": len(features),
                    "training_status": training["status"],
                },
                indent=2,
            )
        )
    else:
        print(json.dumps(export(args.source_root), indent=2, sort_keys=True))
