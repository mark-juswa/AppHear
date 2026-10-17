"""NON_ACTIVE training target (Arm K): equals standard CE without it; -log(pPRE + pPOST) with it."""

from __future__ import annotations

import numpy as np
import pytest

tf = pytest.importorskip("tensorflow")

from eval.runtime_diagnostics import s2_r3_train as tr  # noqa: E402


def test_loss_equals_sparse_categorical_crossentropy_without_non_active() -> None:
    logits = tf.constant(np.random.default_rng(0).normal(size=(3, 7, 3)), tf.float32)
    y = tf.constant(np.random.default_rng(1).integers(0, 3, size=(3, 7)))
    reference = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True, reduction="none")
    assert np.allclose(
        tr.non_active_aware_loss(tf)(y, logits).numpy(), reference(y, logits).numpy(), atol=1e-6
    )


def test_non_active_rows_accept_pre_or_post_but_not_active() -> None:
    loss = tr.non_active_aware_loss(tf)
    y = tf.constant([[tr.NON_ACTIVE, tr.NON_ACTIVE, tr.NON_ACTIVE]])
    logits = tf.constant([[[8.0, 0.0, 0.0], [0.0, 0.0, 8.0], [0.0, 8.0, 0.0]]])
    values = loss(y, logits).numpy()[0]
    assert values[0] < 0.01 and values[1] < 0.01  # confident PRE or POST: no penalty
    assert values[2] > 7.0  # confident ACTIVE: penalised
    p = tf.nn.softmax(logits).numpy()[0, 2]
    assert np.isclose(values[2], -np.log(p[0] + p[2]), atol=1e-5)
