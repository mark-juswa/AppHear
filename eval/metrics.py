"""Pure-numpy classification metrics for the cross-signer eval. No TF dependency so these are
fast to unit-test. All accuracy is reported per-signer AND aggregated (eval-protocol.md)."""

from __future__ import annotations

import numpy as np


def topk_accuracy(probs: np.ndarray, y: np.ndarray, k: int) -> float:
    """Fraction of samples whose true label is in the model's top-k predictions."""
    if len(y) == 0:
        return float("nan")
    k = min(k, probs.shape[1])
    topk = np.argpartition(-probs, kth=k - 1, axis=1)[:, :k]
    correct = (topk == y[:, None]).any(axis=1)
    return float(np.mean(correct))


def per_signer_metrics(
    probs: np.ndarray, y: np.ndarray, participant_ids: np.ndarray
) -> dict[str, dict[str, float]]:
    """{participant_id: {n, top1, top5}} — the headline cross-signer breakdown."""
    out: dict[str, dict[str, float]] = {}
    for pid in sorted(set(participant_ids.tolist())):
        m = participant_ids == pid
        out[str(pid)] = {
            "n": int(m.sum()),
            "top1": topk_accuracy(probs[m], y[m], 1),
            "top5": topk_accuracy(probs[m], y[m], 5),
        }
    return out


def most_confused(probs: np.ndarray, y: np.ndarray, top: int = 8) -> list[tuple[int, int, int]]:
    """Top (true, predicted, count) confusion pairs among misclassified samples."""
    pred = probs.argmax(axis=1)
    wrong = pred != y
    pairs: dict[tuple[int, int], int] = {}
    for t, p in zip(y[wrong].tolist(), pred[wrong].tolist(), strict=True):
        pairs[(t, p)] = pairs.get((t, p), 0) + 1
    ranked = sorted(pairs.items(), key=lambda kv: kv[1], reverse=True)[:top]
    return [(t, p, c) for (t, p), c in ranked]


def expected_calibration_error(
    probs: np.ndarray, y: np.ndarray, n_bins: int = 15
) -> tuple[float, list[dict[str, float]]]:
    """ECE + per-bin reliability (confidence vs accuracy). Lower ECE = better calibrated."""
    if len(y) == 0:
        return float("nan"), []
    conf = probs.max(axis=1)
    correct = probs.argmax(axis=1) == y
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    n = len(y)
    ece = 0.0
    bins: list[dict[str, float]] = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        m = (conf > lo) & (conf <= hi) if i > 0 else (conf >= lo) & (conf <= hi)
        count = int(m.sum())
        if count == 0:
            continue
        acc = float(correct[m].mean())
        avg_conf = float(conf[m].mean())
        ece += count / n * abs(acc - avg_conf)
        bins.append({"lo": float(lo), "hi": float(hi), "n": count, "acc": acc, "conf": avg_conf})
    return float(ece), bins
