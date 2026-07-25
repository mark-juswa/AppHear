"""Feature 07 tests — causal-TCN model shape/forward + data loader. Requires TensorFlow;
skipped automatically if TF isn't installed."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("tensorflow")

from model.data import load_split, make_dataset  # noqa: E402
from model.model import build_classifier, build_encoder  # noqa: E402
from pipeline.features.contract import FEATURE_DIM  # noqa: E402

T = 64


def test_encoder_output_shape() -> None:
    enc = build_encoder(
        T, FEATURE_DIM, blocks=4, channels=64, dilations=(1, 2, 4, 8), kernel=3, dropout=0.1
    )
    assert enc.output_shape == (None, T, 64)  # per-frame embeddings, causal (same length)


def test_classifier_shapes_and_softmax() -> None:
    model = build_classifier(T, FEATURE_DIM, num_classes=10)
    assert model.input_shape == (None, T, FEATURE_DIM)
    assert model.output_shape == (None, 10)
    x = np.random.default_rng(0).standard_normal((3, T, FEATURE_DIM)).astype(np.float32)
    p = model.predict(x, verbose=0)
    assert p.shape == (3, 10)
    assert np.allclose(p.sum(axis=1), 1.0, atol=1e-4)  # softmax normalized
    assert model.count_params() > 0


def test_make_dataset_batches() -> None:
    x = np.zeros((10, T, FEATURE_DIM), np.float32)
    y = np.arange(10, dtype=np.int32)
    ds = make_dataset(x, y, batch_size=4, shuffle=True, seed=0)
    bx, by = next(iter(ds))
    assert bx.shape[1:] == (T, FEATURE_DIM) and bx.shape[0] == 4 and by.shape[0] == 4


def test_load_split_roundtrip(tmp_path: Path) -> None:
    x = np.zeros((5, T, FEATURE_DIM), np.float32)
    y = np.arange(5, dtype=np.int32)
    pids = np.array(["P1"] * 5)
    np.savez_compressed(tmp_path / "train.npz", X=x, y=y, participant_ids=pids, mask=x[..., :2])
    xr, yr, pr = load_split(tmp_path, "train")
    assert xr.shape == (5, T, FEATURE_DIM) and yr.tolist() == list(range(5)) and pr[0] == "P1"
