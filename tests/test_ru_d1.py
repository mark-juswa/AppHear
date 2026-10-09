from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from eval.runtime_diagnostics.ru_d1 import (
    Annotation,
    ConfirmationResult,
    TFLiteRunner,
    classify_failure,
    confirm,
    read_json,
    reconstruct_window,
    window_sha256,
)

ROOT = Path(__file__).resolve().parents[1]


def test_read_json_accepts_android_utf8_bom(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_bytes(b'\xef\xbb\xbf{"enabled": false}')

    assert read_json(path) == {"enabled": False}


def test_reconstruct_window_preserves_order_and_zero_padding() -> None:
    features = {
        10: np.full(258, 1.5, dtype=np.float32),
        11: np.full(258, -2.0, dtype=np.float32),
    }
    sources = [10, 11, -1, -1]

    window = reconstruct_window(sources, features, time_window=4)

    assert window.shape == (4, 258)
    assert np.array_equal(window[0], features[10])
    assert np.array_equal(window[1], features[11])
    assert np.count_nonzero(window[2:]) == 0


def test_window_hash_is_little_endian_float32() -> None:
    window = np.arange(2 * 258, dtype=np.float32).reshape(2, 258)
    expected = hashlib.sha256(np.asarray(window, dtype="<f4").tobytes(order="C")).hexdigest()

    assert window_sha256(window) == expected


def test_failed_oracle_classification_stays_generic_s6() -> None:
    annotation = Annotation("a", 1, 4, True, "false")
    oracle = ConfirmationResult(
        commit_class=7,
        commit_frame=3,
        final_top1=7,
        final_evidence=-0.2,
        final_margin=1.0,
    )

    result = classify_failure(
        annotation=annotation,
        hand_miss_observed=False,
        s4_mismatch_frames=0,
        ground_truth_id=5,
        actual_commit=7,
        oracle_confirmation=oracle,
    )

    assert result == "S6_RECOGNITION_FAILURE"


def test_oracle_success_attributes_failure_to_s5() -> None:
    annotation = Annotation("a", 1, 4, True, "false")
    oracle = ConfirmationResult(5, 3, 5, -0.2, 1.0)

    result = classify_failure(annotation, False, 0, 5, -1, oracle)

    assert result == "S5_FAILURE"


def test_correct_commit_remains_correct_when_a_hand_miss_was_observed() -> None:
    annotation = Annotation("a", 1, 4, True, "true")
    oracle = ConfirmationResult(5, 3, 5, -0.2, 1.0)

    result = classify_failure(annotation, True, 0, 5, 5, oracle)

    assert result == "CORRECT"


def test_checked_in_tflite_accepts_reconstructed_contract_window() -> None:
    runner = TFLiteRunner(ROOT / "android/app/src/main/assets/streaming.tflite")
    features = {3: np.linspace(-1.0, 1.0, 258, dtype=np.float32)}
    window = reconstruct_window([3] + [-1] * 95, features, time_window=96)

    probabilities = runner.infer(window, 0)

    assert probabilities.shape == (236,)
    assert np.isfinite(probabilities).all()
    # The deployed INT8 model's float output is dequantized in 1/128 increments.
    assert np.isclose(probabilities.sum(), 1.0, atol=1e-2)


def test_confirmation_replay_resets_between_s5_bouts() -> None:
    config = {
        "temperature": 1.0,
        "theta_conf": -5.0,
        "theta_margin": 0.0,
        "k_stability": 2,
        "low_fps_confirmation": {"enabled": False},
    }
    class_zero = np.asarray([0.9, 0.1], dtype=np.float32)
    class_one = np.asarray([0.1, 0.9], dtype=np.float32)

    result = confirm(
        [class_zero, class_one, class_one],
        [False, False, False],
        config,
        reset_before=[True, True, False],
    )

    assert result.commit_class == 1
    assert result.commit_frame == 1
