import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from model.experiments.phase1_full_vocab_baseline import (
    _hand_dropout_proxy,
    _stride_proxy,
    classification_metrics,
    expected_calibration_error,
    freeze_selection,
    temporal_subsample_batch,
)


def test_temporal_subsample_preserves_contract_and_compacts() -> None:
    x = np.zeros((1, 96, 258), dtype=np.float32)
    x[0, :12, 0] = np.arange(1, 13)
    mask = np.zeros((1, 96), dtype=bool)
    mask[0, :12] = True
    out, out_mask = temporal_subsample_batch(
        x, mask, np.random.default_rng(7), 1.0, 3, 4
    )
    assert out.shape == (1, 96, 258)
    assert out_mask.shape == (1, 96)
    assert 4 <= int(out_mask.sum()) <= 6
    assert np.all(out[~out_mask] == 0.0)
    assert np.all(np.diff(out[0, out_mask[0], 0]) > 0)


def test_temporal_subsample_probability_zero_is_identity() -> None:
    rng = np.random.default_rng(1)
    x = rng.normal(size=(2, 96, 258)).astype(np.float32)
    mask = np.zeros((2, 96), dtype=bool)
    mask[:, :8] = True
    x[~mask] = 0.0
    out, out_mask = temporal_subsample_batch(x, mask, rng, 0.0, 5, 4)
    np.testing.assert_array_equal(out, x)
    np.testing.assert_array_equal(out_mask, mask)


def test_classification_metrics_reports_macro_and_signers() -> None:
    probabilities = np.asarray(
        [[0.9, 0.1], [0.2, 0.8], [0.6, 0.4]], dtype=np.float32
    )
    labels = np.asarray([0, 1, 1], dtype=np.int32)
    signers = np.asarray(["A", "A", "B"])
    metrics = classification_metrics(probabilities, labels, signers)
    assert metrics["top1"] == 2 / 3
    assert metrics["top5"] == 1.0
    assert metrics["per_signer"]["A"]["top1"] == 1.0
    assert metrics["per_signer"]["B"]["top1"] == 0.0


def test_calibration_error_is_zero_for_correct_certain_predictions() -> None:
    probabilities = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    labels = np.asarray([0, 1], dtype=np.int32)
    assert expected_calibration_error(probabilities, labels) == pytest.approx(0.0)


def test_stride_proxy_compacts_only_real_frames() -> None:
    x = np.zeros((1, 6, 258), dtype=np.float32)
    x[0, :5, 0] = np.arange(1, 6)
    mask = np.asarray([[True, True, True, True, True, False]])
    output, output_mask = _stride_proxy(x, mask, 2)
    np.testing.assert_array_equal(output[0, :3, 0], [1, 3, 5])
    np.testing.assert_array_equal(output_mask, [[True, True, True, False, False, False]])


def test_hand_dropout_proxy_retains_pose_and_padding() -> None:
    x = np.ones((1, 6, 258), dtype=np.float32)
    x[0, 5] = 0.0
    mask = np.asarray([[True, True, True, True, True, False]])
    output = _hand_dropout_proxy(x, mask, every=2)
    assert np.all(output[0, [0, 2, 4], :126] == 0.0)
    assert np.all(output[0, [0, 2, 4], 126:] == 1.0)
    assert np.all(output[0, 5] == 0.0)


def test_freeze_selection_locks_validation_dataset_and_checkpoints(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    dataset_dir = tmp_path / "dataset"
    (run_dir / "config").mkdir(parents=True)
    (run_dir / "metrics").mkdir()
    test_path = dataset_dir / "test.npz"
    dataset_dir.mkdir()
    test_path.write_bytes(b"sealed test")
    digest = hashlib.sha256(test_path.read_bytes()).hexdigest().upper()
    config = {
        "dataset_dir": str(dataset_dir),
        "dataset_hashes": {"test": digest},
    }
    validation = {
        "passed": True,
        "provisional_winner": "production_streaming_tcn",
        "selection_metric": "mean validation clip top-1; macro-F1 tie-break",
        "summary_by_branch": {"production_streaming_tcn": {"mean_val_top1": 0.7}},
    }
    (run_dir / "config" / "experiment.json").write_text(json.dumps(config))
    (run_dir / "metrics" / "validation_metrics.json").write_text(
        json.dumps(validation)
    )
    for seed in (101, 202, 303):
        checkpoint = (
            run_dir
            / "models"
            / "production_streaming_tcn"
            / f"seed_{seed}"
            / "best.keras"
        )
        checkpoint.parent.mkdir(parents=True)
        checkpoint.write_bytes(f"checkpoint-{seed}".encode())
    result = freeze_selection(argparse.Namespace(run_dir=run_dir))
    assert result["frozen_branch"] == "production_streaming_tcn"
    assert result["protected_test"]["sha256"] == digest
    assert len(result["checkpoints"]) == 3
    with pytest.raises(FileExistsError):
        freeze_selection(argparse.Namespace(run_dir=run_dir))
