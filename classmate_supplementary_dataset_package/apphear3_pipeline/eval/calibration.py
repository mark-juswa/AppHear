"""Temperature scaling — one scalar T fit on val to make confidences match correctness.

Our model outputs softmax probabilities, not logits, so we use pseudo-logits z = log(p): the
softmax constant cancels, so softmax(log(p)/T) is exactly temperature scaling. Fitting is a 1-D
NLL minimization (golden-section) — no extra dependency. Seeds the S7 confirmation policy
(feature 12), which must commit on CALIBRATED posteriors (v2 lesson e)."""

from __future__ import annotations

import math

import numpy as np

_EPS = 1e-8


def probs_to_logits(probs: np.ndarray) -> np.ndarray:
    logits: np.ndarray = np.log(np.clip(probs, _EPS, 1.0))
    return logits


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    out: np.ndarray = e / e.sum(axis=1, keepdims=True)
    return out


def apply_temperature(logits: np.ndarray, temperature: float) -> np.ndarray:
    return _softmax(logits / temperature)


def nll(logits: np.ndarray, y: np.ndarray, temperature: float) -> float:
    p = apply_temperature(logits, temperature)
    return float(-np.mean(np.log(p[np.arange(len(y)), y] + _EPS)))


def fit_temperature(
    logits: np.ndarray, y: np.ndarray, lo: float = 0.05, hi: float = 10.0, iters: int = 60
) -> float:
    """Golden-section minimization of NLL over T in [lo, hi]."""
    gr = (math.sqrt(5) - 1) / 2
    a, b = lo, hi
    c = b - gr * (b - a)
    d = a + gr * (b - a)
    fc, fd = nll(logits, y, c), nll(logits, y, d)
    for _ in range(iters):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - gr * (b - a)
            fc = nll(logits, y, c)
        else:
            a, c, fc = c, d, fd
            d = a + gr * (b - a)
            fd = nll(logits, y, d)
    return float((a + b) / 2)
