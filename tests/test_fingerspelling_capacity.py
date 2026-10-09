"""Capacity experiment guards and causal/padding checks; no full training."""

from __future__ import annotations

import copy

import numpy as np
import pytest

from model import fingerspelling_capacity as capacity
from model import fingerspelling_ctc as reference
from model.fingerspelling_capacity_gate import decision


def view(cer: float, correct: int) -> dict:
    return {
        "metrics": {"cer": cer},
        "characters": {"per_character": {"A": {"correct": correct, "reference_count": 100}}},
    }


def test_fit_rule_requires_consistent_dual_view_character_improvement() -> None:
    cfg, _, _ = capacity.policy()
    reports = {
        a: {
            e: {
                "train": {
                    v: view(0.7 if a == "control" else 0.6, 30 if a == "control" else 40)
                    for v in ["native", "phone"]
                }
            }
            for e in [45, 60]
        }
        for a in ["control", "candidate"]
    }
    assert decision(reports, cfg)["full_training_authorized"]
    bad = copy.deepcopy(reports)
    bad["candidate"][45]["train"]["phone"] = view(0.72, 28)
    assert not decision(bad, cfg)["full_training_authorized"]
    bad = copy.deepcopy(reports)
    bad["candidate"][60]["train"]["phone"]["characters"] = view(0.6, 30)["characters"]
    assert not decision(bad, cfg)["full_training_authorized"]


def test_frozen_candidate_preserves_receptive_field_and_training_policy() -> None:
    cfg, p, base = capacity.policy()
    assert (
        1 + 2 * (base["kernel_size"] - 1) * sum(base["dilations"])
        == cfg["receptive_field_observations"]
        == 61
    )
    assert base["channels"] == 64 and cfg["candidate_channels"] == 128
    assert p["temporal_views"] == ["native", "intermediate", "phone"]
    assert base["feature_width"] == 405 and base["temporal_stride"] == 1
    with pytest.raises(ValueError):
        capacity.safe_gate(capacity.REPO / "runs/fingerspelling_ctc_baseline_02")


def test_candidate_causality_padding_gradients_and_shape() -> None:
    _, _, base = capacity.policy()
    tf = reference.tensorflow(base)
    tf.keras.utils.set_random_seed(base["seed"])
    model = capacity.build_model(tf)
    assert model.count_params() == 558236
    x = np.random.default_rng(2).normal(size=(2, 24, 405)).astype(np.float32)
    mask = np.ones((2, 24, 1), np.float32)
    a = model([x, mask], training=False).numpy()
    assert a.shape == (2, 24, 28) and np.isfinite(a).all()
    changed = x.copy()
    changed[:, 12:] += 7
    b = model([changed, mask], training=False).numpy()
    np.testing.assert_allclose(a[:, :12], b[:, :12], rtol=0, atol=0)
    padded = np.pad(x, ((0, 0), (0, 5), (0, 0)))
    padded_mask = np.pad(mask, ((0, 0), (0, 5), (0, 0)))
    c = model([padded, padded_mask], training=False).numpy()
    np.testing.assert_allclose(a, c[:, :24], rtol=1e-5, atol=1e-5)
    assert np.count_nonzero(c[:, 24:]) == 0
    with tf.GradientTape() as tape:
        logits = model([x, mask], training=True)
        loss = reference.ctc_loss(
            tf,
            logits,
            np.array([[0, 1], [12, 12]], np.int32),
            np.array([24, 24], np.int32),
            np.array([2, 2], np.int32),
        )
    gradients = tape.gradient(loss, model.trainable_variables)
    assert np.isfinite(loss.numpy())
    assert all(g is not None and np.isfinite(g.numpy()).all() for g in gradients)


def test_full_runner_is_separate_and_gate_bound() -> None:
    from model import fingerspelling_baseline2 as b2
    from model import fingerspelling_baseline4 as b4

    for run in [
        b2.DEFAULT_RUN,
        capacity.GATE_RUN,
        capacity.REPO / "runs/fingerspelling_ctc_baseline_03",
        b4.DEFAULT_RUN / "nested",
    ]:
        with pytest.raises(ValueError):
            b4.safe_run(run)
    b4.safe_run(b4.DEFAULT_RUN)
    rows = b2.dataset(b2.DEFAULT_DATA)
    assert b4.admission(rows)["full_training_authorized"]
    rid = b4.run_identity(b4.DEFAULT_DATA, rows, False)
    assert rid["base_config"]["channels"] == 128
    assert rid["adapter"]["feature_width"] == 405 and not rid["test_accessed"]
    assert rid["policy"] == b2.policy()[0]
    assert rid["initialization"] == "FRESH_NOT_FIT_GATE_FINETUNING"
