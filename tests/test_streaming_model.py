"""Feature 11 tests — streaming model shape, per-frame dataset, warm-start, aggregation.
Pure-numpy parts run without TF; model/warm-start parts skip if TF is absent."""

from __future__ import annotations

import numpy as np
import pytest

from eval.streaming import last_frame_accuracy, mean_over_real, per_frame_accuracy

# --- pure-numpy aggregation (no TF) -------------------------------------------------------


def test_mean_over_real_ignores_padding() -> None:
    pf = np.zeros((1, 4, 3), np.float32)
    pf[0, 0] = [0.8, 0.1, 0.1]
    pf[0, 1] = [0.6, 0.3, 0.1]
    pf[0, 2] = [9, 9, 9]  # padded frame — must be ignored
    mask = np.array([[1, 1, 0, 0]], bool)
    clip = mean_over_real(pf, mask)
    assert np.allclose(clip[0], [0.7, 0.2, 0.1])  # mean of first two frames only


def test_per_frame_accuracy_masked() -> None:
    pf = np.zeros((1, 4, 3), np.float32)
    pf[0, 0, 1] = 1.0  # correct (y=1)
    pf[0, 1, 0] = 1.0  # wrong
    pf[0, 2, 1] = 1.0  # correct but PADDED -> ignored
    mask = np.array([[1, 1, 0, 0]], bool)
    assert per_frame_accuracy(pf, np.array([1]), mask) == pytest.approx(0.5)  # 1 of 2 real frames


def test_last_frame_accuracy_uses_length() -> None:
    pf = np.zeros((1, 4, 3), np.float32)
    pf[0, 1, 2] = 1.0  # frame at length-1 (length=2) predicts class 2
    assert last_frame_accuracy(pf, np.array([2]), np.array([2])) == 1.0
    assert last_frame_accuracy(pf, np.array([0]), np.array([2])) == 0.0


# --- TF model + data + warm-start ---------------------------------------------------------

tf = pytest.importorskip("tensorflow")


def test_streaming_model_is_per_frame() -> None:
    from model.model import build_streaming_classifier
    from pipeline.features.contract import FEATURE_DIM

    m = build_streaming_classifier(96, FEATURE_DIM, num_classes=10)
    assert m.output_shape == (None, 96, 10)  # per-frame softmax, not pooled
    p = m.predict(np.zeros((2, 96, FEATURE_DIM), np.float32), verbose=0)
    assert p.shape == (2, 96, 10) and np.allclose(p.sum(-1), 1.0, atol=1e-4)


def test_stream_dataset_shapes() -> None:
    from model.data import make_stream_dataset

    x = np.zeros((8, 96, 258), np.float32)
    y = np.arange(8, dtype=np.int32)
    fm = np.ones((8, 96), bool)
    fm[:, 50:] = False
    ds = make_stream_dataset(x, y, fm, batch_size=4, shuffle=False, seed=0)
    xb, yb, swb = next(iter(ds))
    assert xb.shape == (4, 96, 258) and yb.shape == (4, 96) and swb.shape == (4, 96)
    assert np.all(yb.numpy()[:, 0] == yb.numpy()[:, 10])  # every frame targets the same gloss
    assert swb.numpy()[0, 50] == 0.0  # padded frame weight 0


def test_warm_start_copies_encoder() -> None:
    from model.model import build_classifier, build_streaming_classifier
    from model.train_streaming import warm_start_encoder
    from pipeline.features.contract import FEATURE_DIM

    iso = build_classifier(96, FEATURE_DIM, num_classes=10)
    stream = build_streaming_classifier(96, FEATURE_DIM, num_classes=10)
    n = warm_start_encoder(stream, _save_tmp(iso))
    assert n > 0  # encoder layers transferred (head skipped)


def _save_tmp(model: object) -> object:
    import tempfile
    from pathlib import Path

    p = Path(tempfile.mkdtemp()) / "m.keras"
    model.save(p)  # type: ignore[attr-defined]
    return p
