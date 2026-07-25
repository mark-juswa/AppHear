"""Feature 08 tests — metrics + temperature calibration + report assembly. Pure numpy."""

from __future__ import annotations

import numpy as np
import pytest

from eval.calibration import apply_temperature, fit_temperature, nll, probs_to_logits
from eval.harness import evaluate
from eval.metrics import (
    expected_calibration_error,
    most_confused,
    per_signer_metrics,
    topk_accuracy,
)


def _onehotish(y: np.ndarray, num_classes: int, conf: float) -> np.ndarray:
    """Probabilities that put `conf` on the true class, rest spread evenly."""
    p = np.full((len(y), num_classes), (1 - conf) / (num_classes - 1), np.float64)
    p[np.arange(len(y)), y] = conf
    return p


# --- metrics ------------------------------------------------------------------------------


def test_topk_accuracy_perfect_and_top5() -> None:
    y = np.array([0, 1, 2])
    probs = _onehotish(y, 5, 0.9)
    assert topk_accuracy(probs, y, 1) == pytest.approx(1.0)
    # true class ranked 2nd -> top1 miss, top5 hit
    p = np.array([[0.4, 0.6, 0.0, 0.0, 0.0]])
    assert topk_accuracy(p, np.array([0]), 1) == 0.0
    assert topk_accuracy(p, np.array([0]), 5) == 1.0


def test_per_signer_metrics() -> None:
    y = np.array([0, 1, 0, 1])
    probs = _onehotish(y, 3, 0.8)
    probs[3] = [0.8, 0.1, 0.1]  # P2's 2nd sample wrong
    pids = np.array(["P1", "P1", "P2", "P2"])
    m = per_signer_metrics(probs, y, pids)
    assert m["P1"]["top1"] == pytest.approx(1.0) and m["P1"]["n"] == 2
    assert m["P2"]["top1"] == pytest.approx(0.5)


def test_most_confused() -> None:
    y = np.array([0, 0, 1])
    probs = np.array([[0.1, 0.9, 0.0], [0.1, 0.9, 0.0], [0.2, 0.7, 0.1]])  # 0->1 twice
    assert most_confused(probs, y)[0] == (0, 1, 2)


def test_ece_perfectly_calibrated_is_low() -> None:
    # confidence 1.0 and always correct -> ECE ~ 0
    y = np.array([0, 1, 2, 3])
    probs = _onehotish(y, 4, 0.999)
    ece, bins = expected_calibration_error(probs, y, n_bins=10)
    assert ece < 0.05 and len(bins) >= 1


# --- calibration --------------------------------------------------------------------------


def test_temperature_reduces_nll_when_overconfident() -> None:
    rng = np.random.default_rng(0)
    y = rng.integers(0, 5, 200)
    # overconfident-but-often-wrong probs -> T>1 should help
    logits = np.zeros((200, 5))
    logits[np.arange(200), rng.integers(0, 5, 200)] = 6.0  # confident on random class
    t = fit_temperature(logits, y)
    assert nll(logits, y, t) <= nll(logits, y, 1.0) + 1e-9


def test_apply_temperature_is_softmax_normalized() -> None:
    logits = probs_to_logits(np.array([[0.7, 0.2, 0.1]]))
    p = apply_temperature(logits, 2.0)
    assert p.sum() == pytest.approx(1.0)


# --- harness ------------------------------------------------------------------------------


def test_evaluate_report_structure() -> None:
    rng = np.random.default_rng(1)
    yv, yt = rng.integers(0, 6, 60), rng.integers(0, 6, 90)
    val_probs = _onehotish(yv, 6, 0.7)
    test_probs = _onehotish(yt, 6, 0.7)
    pids = rng.choice(["P1", "P2", "P3"], size=90)
    r = evaluate(val_probs, yv, test_probs, yt, pids)
    assert r["n_test"] == 90 and r["n_signers"] == 3
    assert r["overall"]["top1"] == pytest.approx(1.0)  # true class most probable
    assert set(r["per_signer"]) == {"P1", "P2", "P3"}
    assert r["calibration"]["temperature"] > 0
    assert "ece_pre" in r["calibration"] and "ece_post" in r["calibration"]
