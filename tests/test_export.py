"""Phase 3 bridge tests — TFLite export parity metrics + manifest structure. Pure numpy (the
actual conversion is exercised by `python -m deploy.export_tflite --smoke`)."""

from __future__ import annotations

import numpy as np
import pytest

from deploy.export_tflite import build_manifest, parity_metrics

FLOOR = 0.05  # commit_margin_floor used in these tests


def _probs(argmaxes: list[list[int]], c: int, peak: float = 0.9) -> np.ndarray:
    """(N,T,C) probs whose per-frame argmax follows `argmaxes`; `peak` sets the winner's mass so
    the clip top1-top2 margin is peak-(1-peak)/(c-1) (above/below the commit floor)."""
    n, t = len(argmaxes), len(argmaxes[0])
    p = np.full((n, t, c), (1 - peak) / (c - 1), np.float32)
    for i in range(n):
        for j in range(t):
            p[i, j] = (1 - peak) / (c - 1)
            p[i, j, argmaxes[i][j]] = peak
    return p


def test_parity_identical_is_perfect() -> None:
    p = _probs([[1, 1, 2], [0, 0, 0]], c=3)
    fm = np.ones((2, 3), bool)
    y = np.array([1, 0])
    m = parity_metrics(p, p.copy(), fm, y, FLOOR)
    assert m["committable_agreement"] == pytest.approx(1.0)
    assert m["correct_clip_retention_all"] == pytest.approx(1.0)
    assert m["clip_argmax_agreement_all"] == pytest.approx(1.0)
    assert m["per_frame_argmax_agreement"] == pytest.approx(1.0)
    assert m["max_abs_prob_diff"] == pytest.approx(0.0)
    assert m["clip_top1_delta"] == pytest.approx(0.0)


def test_gate_ignores_flips_below_the_commit_margin() -> None:
    # A confident clip (peak 0.9 -> margin ~0.85, committable) that TFLite KEEPS, plus a near-tie
    # clip (peak ~0.34 over 3 classes -> tiny margin, NOT committable) that TFLite flips. The gate
    # metric (committable_agreement) must stay perfect; only the all-clips diagnostic dips.
    pk = np.array([[[0.90, 0.05, 0.05]], [[0.34, 0.33, 0.33]]], np.float32)
    pt = np.array([[[0.90, 0.05, 0.05]], [[0.33, 0.34, 0.33]]], np.float32)  # 2nd clip flips 0->1
    y = np.array([0, 0])
    fm = np.ones((2, 1), bool)
    m = parity_metrics(pk, pt, fm, y, FLOOR)
    assert m["committable_frac"] == pytest.approx(0.5)  # only the confident clip is committable
    assert m["committable_agreement"] == pytest.approx(1.0)  # and INT8 kept it
    assert m["clip_argmax_agreement_all"] == pytest.approx(0.5)  # near-tie flip shows only here


def test_gate_catches_a_committable_flip() -> None:
    # If TFLite flips a CONFIDENT (committable) prediction, the gate must catch it.
    pk = np.array([[[0.90, 0.05, 0.05]]], np.float32)
    pt = np.array([[[0.05, 0.90, 0.05]]], np.float32)  # confident clip flips 0->1
    y = np.array([0])
    fm = np.ones((1, 1), bool)
    m = parity_metrics(pk, pt, fm, y, FLOOR)
    assert m["committable_frac"] == pytest.approx(1.0)
    assert m["committable_agreement"] == pytest.approx(0.0)  # gate fails, as it should


def test_parity_counts_only_real_frames() -> None:
    pk = _probs([[1, 1, 1]], c=3)
    pt = _probs([[1, 1, 2]], c=3)  # differs only on frame 2
    y = np.array([1])
    fm_all = np.ones((1, 3), bool)
    fm_real = np.array([[True, True, False]])  # frame 2 is padding
    all_m = parity_metrics(pk, pt, fm_all, y, FLOOR)["per_frame_argmax_agreement"]
    real_m = parity_metrics(pk, pt, fm_real, y, FLOOR)["per_frame_argmax_agreement"]
    assert all_m == pytest.approx(2 / 3)
    assert real_m == pytest.approx(1.0)  # masking the differing padded frame -> perfect


def test_manifest_has_contract_fields() -> None:
    parity = {"committable_agreement": 1.0, "clip_top1_delta": 0.003}
    op = {"theta_conf": -1.2, "theta_margin": 0.3, "k_stability": 3}
    man = build_manifest("3.0", (96, 258), 2731, 0.715, op, "abc123", "def456", parity)
    assert man["schema_version"] == "3.0"
    assert man["feature_dim"] == 258 and man["time_window"] == 96
    assert man["num_classes"] == 2731
    assert man["landmarker_mode"] == "IMAGE"  # must match offline extraction
    assert man["calibration_temperature"] == 0.715
    assert man["operating_point"] == op
    assert man["keras_sha256"] == "abc123" and man["tflite_sha256"] == "def456"
    assert man["parity"]["committable_agreement"] == 1.0
