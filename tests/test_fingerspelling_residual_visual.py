"""Reliability rules, frozen B2 fallback, trainable boundary and causality."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from pipeline.fingerspelling.visual_quality import quality
from pipeline.perception_vnext.recognition_schema import RAW_SCHEMA, RawSequence


def raw_fixture() -> RawSequence:
    n = 4
    xy = np.zeros((n, 2, 21, 2), np.float32)
    xy[:] = [100, 100]
    return RawSequence(
        metadata={
            "schema": RAW_SCHEMA,
            "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB",
        },
        frame_index=np.arange(n),
        timestamp_ms=np.arange(n) * 100.0,
        source_size=np.tile([400, 400], (n, 1)),
        hand_xy=xy,
        hand_proposal_support=np.ones((n, 2, 21), np.float32),
        hand_joint_valid=np.ones((n, 2, 21), bool),
        hand_presence=np.full((n, 2), 0.99, np.float32),
        hand_observed=np.ones((n, 2), bool),
        hand_proposal_present=np.ones((n, 2), bool),
        hand_roi_center_side=np.tile([100, 100, 80], (n, 2, 1)).astype(np.float32),
        hand_handedness_diagnostic=np.zeros((n, 2)),
        body_xy=np.zeros((n, 8, 2)),
        body_support=np.zeros((n, 8)),
        body_valid=np.zeros((n, 8), bool),
        body_available=np.zeros(n, bool),
    )


def test_duplicate_stronger_and_geometry_not_mutated() -> None:
    r = raw_fixture()
    original = r.hand_xy.copy()
    r.hand_presence[0, 0] = 0.95
    q = quality(r)
    assert q["suppressed"][0, 0] and q["quality"][0, 1] > 0
    assert np.all(q["duplicate"])
    np.testing.assert_array_equal(original, r.hand_xy)
    r.hand_xy[:, 1] += 150
    r.hand_roi_center_side[:, 1, :2] += 150
    q = quality(r)
    assert not q["duplicate"].any() and (q["quality"] > 0).all()


def test_refiner_failure_partial_joints_border_and_causality() -> None:
    r = raw_fixture()
    r.hand_observed[0] = False
    r.hand_joint_valid[1, :, 0:4] = False
    r.hand_roi_center_side[2, :, :2] = 0
    q = quality(r)
    assert not q["quality"][:3].any()
    assert q["quality"][3].max() > 0
    r.hand_xy[3] += 1000
    newer = quality(r)
    for key in q:
        np.testing.assert_array_equal(q[key][:3], newer[key][:3])
    r = raw_fixture()
    r.hand_presence[:] = 0.89
    assert not quality(r)["quality"].any()
    bad = r.hand_proposal_support.copy()
    bad[:, :, :7] = 0
    assert not quality(replace(raw_fixture(), hand_proposal_support=bad))[
        "quality"
    ].any()


def test_actual_b2_zero_fallback_gradients_causality_serialization(tmp_path) -> None:
    from model import fingerspelling_baseline2 as b2
    from model import fingerspelling_ctc as reference
    from model.fingerspelling_residual_execution import (
        ResidualSteps,
        base_model,
        build_model,
        frozen_digest,
    )

    tf = reference.tensorflow(b2.policy()[1])
    tf.keras.utils.set_random_seed(20261002)
    model = build_model(tf)
    baseline = base_model(tf)
    rng = np.random.default_rng(12)
    x = rng.normal(size=(2, 12, 1559)).astype(np.float32)
    x[:, :, -2:] = 0.8
    mask = np.ones((2, 12, 1), np.float32)
    expected = baseline([x[:, :, :405], mask], training=False).numpy()
    np.testing.assert_allclose(
        expected, model([x, mask], training=True).numpy(), atol=1e-6, rtol=0
    )
    frozen = frozen_digest(model)
    names = [v.path for v in model.trainable_variables]
    assert len(names) == 6 and all(
        any(
            k in v for k in ["visual_projection", "visual_delta", "learned_visual_gate"]
        )
        for v in names
    )
    opt = tf.keras.optimizers.Adam(0.001, clipnorm=5)
    steps = ResidualSteps(tf, model, opt)
    assert steps.update is not None
    loss = steps.update(
        x,
        mask,
        np.array([[0, 1], [12, 12]], np.int32),
        np.array([12, 12], np.int32),
        np.array([2, 2], np.int32),
    )
    assert np.isfinite(loss.numpy()) and frozen_digest(model) == frozen
    assert np.any(model.get_layer("visual_delta").get_weights()[0])
    without = x.copy()
    without[:, :, -2:] = 0
    np.testing.assert_array_equal(
        expected, model([without, mask], training=True).numpy()
    )
    altered = x.copy()
    altered[:, 6:] += 10
    altered[:, 6:, -2:] = 0.9
    np.testing.assert_array_equal(
        model([x, mask], training=False).numpy()[:, :6],
        model([altered, mask], training=False).numpy()[:, :6],
    )
    path = tmp_path / "residual.keras"
    model.save(path)
    restored = tf.keras.models.load_model(path, compile=False)
    np.testing.assert_array_equal(
        model([x, mask], training=False).numpy(),
        restored([x, mask], training=False).numpy(),
    )


def test_retained_real_temporal_alignment() -> None:
    from model import fingerspelling_baseline2 as b2
    from model.fingerspelling_residual_execution import ResidualCache
    from tools.fingerspelling.residual_visual import smoke_rows

    rec = smoke_rows(b2.dataset(b2.DEFAULT_DATA))[0]
    cache = ResidualCache()
    for view in ["native", "intermediate", "phone"]:
        packed, y = cache.load(rec, view)
        g, t = cache.geometry.load(rec, view)
        np.testing.assert_array_equal(g, packed[:, :405])
        np.testing.assert_array_equal(t, y)
        emb, q = cache.visual[rec["sample_id"]]
        indices = cache.positions[(rec["sample_id"], view)]
        np.testing.assert_array_equal(
            packed[:, 405:-2], emb[indices].reshape(len(indices), -1)
        )
        np.testing.assert_array_equal(packed[:, -2:], q[indices])


def test_residual_decision_rejects_emission_only_tradeoff() -> None:
    import json

    from model.fingerspelling_residual_visual import outcome

    def report(cer, correct, substitutions, precision):
        view = {
            "metrics": {
                "cer": cer,
                "substitutions": substitutions,
                "signers": {str(i): {"cer": cer} for i in range(15)},
            },
            "discrimination": {
                "correctly_aligned_characters": correct,
                "correct_predicted_precision": precision,
            },
        }
        return {"fixed_b2_decoder": {"native": view, "phone": view}}

    base = report(0.6, 100, 80, 0.5)
    tradeoff = report(0.55, 100, 100, 0.4)
    decision = outcome(base, tradeoff, False)
    assert decision["status"] == "RESIDUAL_VISUAL_NOT_SUPPORTED_STOP_VISUAL_PATH"
    assert not decision["checks"]["phone_correct_characters_higher"]
    assert not decision["checks"]["mean_precision_not_lower"]
    json.dumps(decision)  # NumPy comparison results must be JSON-safe Python booleans.
    assert outcome(base, report(0.5, 150, 60, 0.6), False)["status"] == (
        "RESIDUAL_VISUAL_DISCRIMINATION_SUPPORTED"
    )


def test_writer_exclusion_and_release(tmp_path) -> None:
    import subprocess
    import sys

    from tools.fingerspelling.residual_lock import single_writer

    scope = tmp_path / "one_run"
    script = (
        "import sys\nfrom pathlib import Path\n"
        "from tools.fingerspelling.residual_lock import single_writer\n"
        "try:\n with single_writer(Path(sys.argv[1])): pass\n"
        "except RuntimeError: sys.exit(7)\n"
    )
    with single_writer(scope):
        blocked = subprocess.run(
            [sys.executable, "-c", script, str(scope)], check=False
        )
        assert blocked.returncode == 7
    released = subprocess.run([sys.executable, "-c", script, str(scope)], check=False)
    assert released.returncode == 0
