"""Deployment regression for the debug-only S2-R3 Arm A e10 phone package.

Re-checks the committed package against its own hash-pinned contract on the same
669-observation prior-phone fixture the S2-R2 export used. No new evaluation data.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from deploy.export_s2_r2_phone import sha256
from deploy.export_s2_r3_arm_a_phone import (
    ASSETS,
    FIXTURE_PATH,
    FIXTURE_SHA,
    MODEL_SHA,
    NORMALIZATION_SHA,
    PACKAGE_ID,
)

ROOT = Path(__file__).resolve().parents[1]
FROZEN_MAIN = ROOT / "android/app/src/main/assets/phone_causal_recognition_01"


def test_arm_a_package_is_debug_only_and_hash_pinned() -> None:
    contract = json.loads((ASSETS / "contract.json").read_text(encoding="utf-8"))
    assert "src/debug/assets" in ASSETS.as_posix()
    assert not (FROZEN_MAIN / "s2_r3_arm_a_e10_candidate").exists()
    assert contract["package_id"] == PACKAGE_ID
    assert contract["research_only"] is True
    assert contract["training_executed"] is False
    assert contract["source_checkpoint_sha256"] == MODEL_SHA
    assert contract["source_normalization_sha256"] == NORMALIZATION_SHA
    assert sha256(ASSETS / "s2_r3_arm_a_e10_fp32.tflite") == contract["tflite_sha256"]
    assert sha256(ASSETS / "normalization.json") == contract["normalization_asset_sha256"]
    fixture = contract["fixture"]
    assert fixture["raw_features_sha256"] == FIXTURE_SHA == sha256(FIXTURE_PATH)
    assert fixture["argmax_state_mismatches"] == 0
    assert fixture["maximum_abs_probability_difference_keras_vs_tflite"] <= 1e-4


def test_arm_a_tflite_reproduces_exported_fixture_probabilities() -> None:
    import tensorflow as tf

    contract = json.loads((ASSETS / "contract.json").read_text(encoding="utf-8"))
    normalization = json.loads((ASSETS / "normalization.json").read_text(encoding="utf-8"))
    assert normalization["source_sha256"] == NORMALIZATION_SHA
    raw = np.fromfile(FIXTURE_PATH, dtype="<f4").reshape(-1, 378)
    features_path = ASSETS / contract["fixture"]["features_asset"]
    probabilities_path = ASSETS / contract["fixture"]["probabilities_asset"]
    assert sha256(features_path) == contract["fixture"]["features_sha256"]
    assert sha256(probabilities_path) == contract["fixture"]["probabilities_sha256"]
    expected_features = np.fromfile(features_path, dtype="<f4").reshape(-1, 378)
    expected = np.fromfile(probabilities_path, dtype="<f4").reshape(-1, 3)
    normalized = (raw - np.asarray(normalization["mean"], np.float32)) / np.asarray(
        normalization["std"], np.float32
    )
    assert np.array_equal(normalized, expected_features)
    runner = tf.lite.Interpreter(
        model_path=str(ASSETS / "s2_r3_arm_a_e10_fp32.tflite"), num_threads=1
    )
    outputs = []
    previous_length = None
    for i in range(len(normalized)):
        sequence = normalized[max(0, i - 60) : i + 1]
        if previous_length != len(sequence):
            runner.resize_tensor_input(
                runner.get_input_details()[0]["index"], [1, len(sequence), 378], strict=True
            )
            runner.allocate_tensors()
            previous_length = len(sequence)
        runner.set_tensor(runner.get_input_details()[0]["index"], sequence[None])
        runner.invoke()
        logits = runner.get_tensor(runner.get_output_details()[0]["index"])[0]
        exponential = np.exp(logits - np.max(logits))
        outputs.append(exponential / exponential.sum())
    probabilities = np.asarray(outputs)
    assert len(probabilities) == 669
    assert np.max(np.abs(probabilities - expected)) <= 1e-4
    assert np.array_equal(np.argmax(probabilities, axis=1), np.argmax(expected, axis=1))
