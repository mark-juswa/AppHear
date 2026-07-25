"""Assemble the cross-signer eval report from precomputed probabilities (pure numpy).

Kept model-free so the whole report logic is unit-testable without TF. Accuracy is invariant
to temperature (monotone), so top-k is reported on raw probs; temperature only affects
calibration (ECE)."""

from __future__ import annotations

from typing import Any

import numpy as np

from .calibration import apply_temperature, fit_temperature, probs_to_logits
from .metrics import expected_calibration_error, most_confused, per_signer_metrics, topk_accuracy


def evaluate(
    val_probs: np.ndarray,
    val_y: np.ndarray,
    test_probs: np.ndarray,
    test_y: np.ndarray,
    test_pids: np.ndarray,
) -> dict[str, Any]:
    """Fit temperature on val, report top-1/top-5 (overall + per-signer), calibration, and
    top confusions on the test split."""
    temperature = fit_temperature(probs_to_logits(val_probs), val_y)
    test_cal = apply_temperature(probs_to_logits(test_probs), temperature)
    ece_pre, _ = expected_calibration_error(test_probs, test_y)
    ece_post, _ = expected_calibration_error(test_cal, test_y)

    per_signer = per_signer_metrics(test_probs, test_y, test_pids)
    macro_top1 = (
        float(np.mean([m["top1"] for m in per_signer.values()])) if per_signer else float("nan")
    )

    return {
        "n_test": int(len(test_y)),
        "n_signers": len(per_signer),
        "overall": {
            "top1": topk_accuracy(test_probs, test_y, 1),
            "top5": topk_accuracy(test_probs, test_y, 5),
            "macro_top1_per_signer": macro_top1,  # unweighted signer mean (fairness view)
        },
        "calibration": {
            "temperature": temperature,
            "ece_pre": ece_pre,
            "ece_post": ece_post,
        },
        "per_signer": per_signer,
        "most_confused": most_confused(test_probs, test_y),
    }
