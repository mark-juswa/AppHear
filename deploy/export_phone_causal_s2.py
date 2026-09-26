"""Export the frozen Phase-7 S2 checkpoint for Android causal inference.

This is an identity-preserving deployment conversion.  It never compiles,
fits, fine-tunes, or otherwise changes the frozen Keras checkpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import tensorflow as tf

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PHASE7 = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
    / "phase7_production_cadence_aligned_segmenter_01"
)
CHECKPOINT = PHASE7 / "best_model.keras"
NORMALIZATION = PHASE7 / "cadence_aligned_normalization_stats.json"
SPARSE_MANIFEST = PHASE7 / "sparse_view_manifest.json"
MATERIALIZER_CONTRACT = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
    / "phase8a_m_causal_sparse_recognition_window_materialization_01"
    / "materializer_contract_frozen.json"
)
ASSET_DIR = ROOT / "android/app/src/debug/assets/phone_causal_recognition_01"
EXPECTED_CHECKPOINT_SHA = "dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73"
EXPECTED_NORMALIZATION_SHA = "3018348ae8cc9fe0671eda913535556e14cebf5a16fbe72a96be73ed494e9130"
EXPECTED_MATERIALIZER_CONTRACT_SHA = (
    "0a59dc80fe54cb37e09fbce8aa108dbfce32bc4b5cb48b98e61619b5b3b34971"
)
FEATURE_SCHEMA = "apphear.perception_vnext.segmentation_features.v1"
FEATURE_WIDTH = 378
STATE_COUNT = 3
RECEPTIVE_FIELD = 61


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def select_cal_fixture() -> tuple[dict[str, object], np.ndarray]:
    manifest = json.loads(SPARSE_MANIFEST.read_text(encoding="utf-8"))
    row = max(
        (item for item in manifest["rows"] if item["phase7_partition"] == "CAL"),
        key=lambda item: int(item["selected_observation_count"]),
    )
    feature_path = Path(str(row["feature_path"]))
    with np.load(feature_path, allow_pickle=False) as payload:
        features = np.asarray(payload["features"], np.float32)
    if features.ndim != 2 or features.shape[1] != FEATURE_WIDTH:
        raise ValueError("FROZEN_CAL_FIXTURE_FEATURE_SHAPE_MISMATCH")
    return row, features


def export_feature_builder_fixture(row: dict[str, object]) -> dict[str, object]:
    from pipeline.perception_vnext.recognition_schema import RawSequence, load_raw_sequence
    from pipeline.perception_vnext.segmentation.learned_features import (
        derive_causal_segmentation_features,
    )

    raw = load_raw_sequence(Path(str(row["source_raw_path"])))
    indices = np.asarray(row["selected_indices"][:4], np.int32)
    subset = RawSequence(
        metadata=dict(raw.metadata),
        **{
            name: np.asarray(getattr(raw, name))[indices]
            for name in RawSequence.__dataclass_fields__
            if name != "metadata"
        },
    )
    subset.validate()
    expected = derive_causal_segmentation_features(subset)
    expected_path = ASSET_DIR / "segmentation_feature_parity_expected.f32"
    expected_path.write_bytes(expected.astype("<f4", copy=False).tobytes())

    def finite_json(values: np.ndarray) -> object:
        data = np.asarray(values)
        if data.dtype.kind == "f":
            return np.where(np.isfinite(data), data, 0.0).tolist()
        return data.tolist()

    observations = []
    for local in range(len(indices)):
        observations.append(
            {
                "source_index": local,
                "timestamp_ms": float(subset.timestamp_ms[local]),
                "source_size": finite_json(subset.source_size[local]),
                "hand_xy": finite_json(subset.hand_xy[local]),
                "hand_joint_valid": finite_json(subset.hand_joint_valid[local]),
                "hand_proposal_support": finite_json(subset.hand_proposal_support[local]),
                "hand_presence": finite_json(subset.hand_presence[local]),
                "hand_presence_finite": np.isfinite(subset.hand_presence[local]).tolist(),
                "hand_observed": finite_json(subset.hand_observed[local]),
                "hand_proposal_present": finite_json(subset.hand_proposal_present[local]),
                "hand_roi_center_side": finite_json(subset.hand_roi_center_side[local]),
                "body_xy": finite_json(subset.body_xy[local]),
                "body_support": finite_json(subset.body_support[local]),
                "body_valid": finite_json(subset.body_valid[local]),
                "body_available": bool(subset.body_available[local]),
            }
        )
    fixture_path = ASSET_DIR / "segmentation_feature_parity_raw.json"
    json_dump(
        fixture_path,
        {
            "schema": "apphear.phone_causal_recognition.segmentation_feature_parity.v1",
            "feature_schema": FEATURE_SCHEMA,
            "observations": observations,
        },
    )
    return {
        "raw_asset": fixture_path.name,
        "raw_sha256": sha256(fixture_path),
        "expected_asset": expected_path.name,
        "expected_sha256": sha256(expected_path),
        "observation_count": len(indices),
    }


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits, axis=-1, keepdims=True)
    values = np.exp(shifted)
    return values / np.sum(values, axis=-1, keepdims=True)


def export() -> dict[str, object]:
    if sha256(CHECKPOINT) != EXPECTED_CHECKPOINT_SHA:
        raise RuntimeError("FROZEN_S2_CHECKPOINT_IDENTITY_MISMATCH")
    if sha256(NORMALIZATION) != EXPECTED_NORMALIZATION_SHA:
        raise RuntimeError("FROZEN_S2_NORMALIZATION_IDENTITY_MISMATCH")
    if sha256(MATERIALIZER_CONTRACT) != EXPECTED_MATERIALIZER_CONTRACT_SHA:
        raise RuntimeError("FROZEN_MATERIALIZER_CONTRACT_IDENTITY_MISMATCH")

    tf.keras.utils.set_random_seed(5103)
    model = tf.keras.models.load_model(CHECKPOINT, compile=False)
    if model.input_shape != (None, None, FEATURE_WIDTH):
        raise RuntimeError(f"UNEXPECTED_S2_INPUT_SHAPE:{model.input_shape}")
    if model.output_shape != (None, None, STATE_COUNT) or model.count_params() != 123_779:
        raise RuntimeError("UNEXPECTED_S2_MODEL_CONTRACT")

    # The frozen model emits one logit row per causal prefix position.  Android
    # needs only the current row; fixing the output rank also avoids relying on
    # platform-specific dynamic-output shape propagation.
    mobile_model = tf.keras.Model(model.input, model.output[:, -1, :], name="phase7_s2_mobile_last")
    converter = tf.lite.TFLiteConverter.from_keras_model(mobile_model)
    converter.optimizations = []
    converter.target_spec.supported_types = [tf.float32]
    tflite = converter.convert()
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    model_path = ASSET_DIR / "s2_phase7_fp32.tflite"
    model_path.write_bytes(tflite)

    normalization = json.loads(NORMALIZATION.read_text(encoding="utf-8"))
    normalization_asset = {
        "schema": normalization["schema"],
        "feature_schema": normalization["feature_schema"],
        "population": normalization["population"],
        "mean": normalization["mean"],
        "std": normalization["std"],
        "source_sha256": EXPECTED_NORMALIZATION_SHA,
    }
    normalization_path = ASSET_DIR / "cadence_aligned_normalization_stats.json"
    json_dump(normalization_path, normalization_asset)
    materializer_path = ASSET_DIR / "materializer_contract_frozen.json"
    materializer_path.write_bytes(MATERIALIZER_CONTRACT.read_bytes())

    row, features = select_cal_fixture()
    feature_builder_fixture = export_feature_builder_fixture(row)
    mean = np.asarray(normalization["mean"], np.float32)
    std = np.asarray(normalization["std"], np.float32)
    normalized = ((features - mean) / std).astype(np.float32)
    keras_logits = np.asarray(model(normalized[None, ...], training=False), np.float32)[0]
    keras_probabilities = softmax(keras_logits).astype(np.float32)

    interpreter = tf.lite.Interpreter(model_path=str(model_path), num_threads=1)
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    tflite_probabilities = np.empty_like(keras_probabilities)
    prefix_differences: list[dict[str, object]] = []
    for length in range(1, len(normalized) + 1):
        start = max(0, length - RECEPTIVE_FIELD)
        causal_prefix = normalized[start:length]
        runtime_length = len(causal_prefix)
        interpreter.resize_tensor_input(
            input_detail["index"], [1, runtime_length, FEATURE_WIDTH], strict=False
        )
        interpreter.allocate_tensors()
        input_detail = interpreter.get_input_details()[0]
        output_detail = interpreter.get_output_details()[0]
        interpreter.set_tensor(input_detail["index"], causal_prefix[None, ...])
        interpreter.invoke()
        logits = np.asarray(interpreter.get_tensor(output_detail["index"]), np.float32)
        probability = softmax(logits)[0].astype(np.float32)
        tflite_probabilities[length - 1] = probability
        difference = float(np.max(np.abs(probability - keras_probabilities[length - 1])))
        prefix_differences.append(
            {
                "full_prefix_length": length,
                "runtime_history_length": runtime_length,
                "max_abs_probability_difference": difference,
            }
        )

    max_abs = max(item["max_abs_probability_difference"] for item in prefix_differences)
    if max_abs > 1.0e-4:
        raise RuntimeError(f"S2_TFLITE_PARITY_FAILED:{max_abs}")

    feature_path = ASSET_DIR / "s2_parity_normalized_features.f32"
    probability_path = ASSET_DIR / "s2_parity_probabilities.f32"
    feature_path.write_bytes(normalized.astype("<f4", copy=False).tobytes())
    probability_path.write_bytes(tflite_probabilities.astype("<f4", copy=False).tobytes())
    contract = {
        "schema": "apphear.phone_causal_recognition.s2_mobile_contract.v1",
        "milestone": "PHONE_CAUSAL_RECOGNITION_INTEGRATION_01",
        "source_checkpoint_sha256": EXPECTED_CHECKPOINT_SHA,
        "source_normalization_sha256": EXPECTED_NORMALIZATION_SHA,
        "tflite_sha256": sha256(model_path),
        "normalization_asset_sha256": sha256(normalization_path),
        "materializer_contract_sha256": sha256(materializer_path),
        "feature_schema": FEATURE_SCHEMA,
        "feature_width": FEATURE_WIDTH,
        "state_order": ["PRE_IDLE", "ACTIVE_SIGN", "POST_RECOVERY"],
        "input_dtype": "FLOAT32",
        "input_shape_signature": [1, -1, FEATURE_WIDTH],
        "output_dtype": "FLOAT32",
        "output_shape_signature": [1, STATE_COUNT],
        "receptive_field_observations": RECEPTIVE_FIELD,
        "causal_runtime": "bounded rolling prefix; last output only",
        "training_executed": False,
        "quantization": "NONE_FP32",
        "fixture": {
            "view_key": row["view_key"],
            "partition": "CAL",
            "observation_count": len(normalized),
            "features_asset": feature_path.name,
            "features_sha256": sha256(feature_path),
            "probabilities_asset": probability_path.name,
            "probabilities_sha256": sha256(probability_path),
            "maximum_abs_probability_difference_keras_vs_tflite": max_abs,
        },
        "segmentation_feature_builder_fixture": feature_builder_fixture,
    }
    contract_path = ASSET_DIR / "contract.json"
    json_dump(contract_path, contract)
    return contract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("export",))
    args = parser.parse_args()
    if args.command == "export":
        print(json.dumps(export(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
