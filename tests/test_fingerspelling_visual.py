"""Crop math, missingness and causal fusion guards; no full training."""

from __future__ import annotations

import numpy as np

from model import fingerspelling_baseline2 as b2
from model import fingerspelling_ctc as reference
from model.fingerspelling_visual_execution import PACKED_WIDTH, FusionSteps, build_fusion_model
from pipeline.fingerspelling.visual_crop import config, crop_geometry, hand_crop


def test_gate_rejects_more_output_without_discrimination() -> None:
    from model.fingerspelling_visual_gate import decision

    def report(cer, correct, predicted):
        view = {
            "metrics": {"cer": cer, "predicted_characters": predicted},
            "characters": {
                "per_character": {"A": {"correct": correct, "reference_count": 100}}
            },
        }
        return {
            "train": {"native": view, "phone": view},
            "dev": {"native": view, "phone": view},
        }

    control = report(0.7, 30, 40)
    emitted_more = report(0.5, 30, 75)
    result = decision(
        {"geometry": control, "appearance": emitted_more, "combined": emitted_more}, config()
    )
    assert not result["full_fusion_training_authorized"]
    assert not result["checks"]["dev_correct_reference_gain"]
    assert not result["checks"]["dev_mean_precision_not_lower"]
    improved = report(0.4, 60, 75)
    assert decision(
        {"geometry": control, "appearance": improved, "combined": improved}, config()
    )["full_fusion_training_authorized"]


def test_real_crop_temporal_indices_and_adapter_equivalence() -> None:
    from model.fingerspelling_visual_execution import FusionCache
    from pipeline.fingerspelling.visual_package import load_visual
    from tools.fingerspelling.visual_fusion import diagnostic_rows

    rec = diagnostic_rows(b2.dataset(b2.DEFAULT_DATA))[0][0]
    cache = FusionCache()
    visual, crop_valid = load_visual(rec)
    for view in ["native", "intermediate", "phone"]:
        packed, y = cache.load(rec, view)
        geometry, targets = cache.geometry.load(rec, view)
        selected = cache.positions[(rec["sample_id"], view)]
        np.testing.assert_array_equal(packed[:, :405], geometry)
        np.testing.assert_array_equal(
            packed[:, 405:-2], visual[selected].reshape(len(selected), -1)
        )
        np.testing.assert_array_equal(packed[:, -2:], crop_valid[selected])
        np.testing.assert_array_equal(y, targets)
        np.testing.assert_array_equal(cache.load(rec, view)[0], packed)


def test_historical_orientation_probe_identity_guard() -> None:
    import json

    import pytest

    from pipeline.fingerspelling.sequence_manifest import REPO
    from pipeline.fingerspelling.visual_package import verified_orientation
    from tools.fingerspelling.visual_fusion import diagnostic_rows

    rows = diagnostic_rows(b2.dataset(b2.DEFAULT_DATA))[0]
    rec = next(r for r in rows if r["sample_id"] == "fsboard-v13-train-5480a01c45123004b9fa")
    receipt = json.loads((REPO / rec["raw_receipt_path"]).read_text())
    assert "orientation_degrees_clockwise" not in receipt
    assert verified_orientation(receipt, rec) == 270
    with pytest.raises(ValueError, match="verified historical orientation"):
        verified_orientation({**receipt, "source_probe_sha256": "corrupt"}, rec)


def test_crop_matches_known_rgb_no_reflection_and_missingness() -> None:
    cfg = {**config(), "crop_size": 3, "roi_expansion": 1.0, "minimum_roi_side_pixels": 1.0}
    image = np.zeros((8, 8, 3), np.uint8)
    image[:, :, 0] = np.arange(8, dtype=np.uint8) * 30
    pixels, info = hand_crop(image, np.array([3, 3, 4], np.float32), True, cfg)
    assert info["valid"]
    np.testing.assert_allclose(
        pixels[0, :, 0], np.array([30, 90, 150], np.float32) / 127.5 - 1, atol=1e-6
    )
    np.testing.assert_array_equal(
        pixels, hand_crop(image, np.array([3, 3, 4], np.float32), True, cfg)[0]
    )
    missing, meta = hand_crop(image, np.array([3, 3, 4], np.float32), False, cfg)
    assert not meta["valid"] and not missing.any()
    for roi in [[np.nan, 3, 4], [3, 3, 0], [100, 100, 10]]:
        _, valid, _ = crop_geometry(np.array(roi, np.float32), True, 8, 8, cfg)
        assert not valid


def test_zero_border_and_source_intersection() -> None:
    cfg = {**config(), "crop_size": 3, "roi_expansion": 1.0, "minimum_roi_side_pixels": 1.0}
    image = np.full((8, 8, 3), 255, np.uint8)
    pixels, info = hand_crop(image, np.array([0, 4, 4], np.float32), True, cfg)
    assert info["valid"] and info["source_intersection_fraction"] == 0.5
    np.testing.assert_array_equal(pixels[:, 0], -1)
    np.testing.assert_array_equal(pixels[:, -1], 1)


def test_fusion_masks_causality_gradients_and_serialization(tmp_path) -> None:
    _, base = b2.policy()
    tf = reference.tensorflow(base)
    tf.keras.utils.set_random_seed(base["seed"])
    model = build_fusion_model(tf)
    x = np.random.default_rng(3).normal(size=(2, 12, PACKED_WIDTH)).astype(np.float32)
    x[:, :, -2:] = 0
    mask = np.ones((2, 12, 1), np.float32)
    before = model([x, mask], training=False).numpy()
    altered = x.copy()
    altered[:, :, 405:-2] *= 100
    np.testing.assert_array_equal(before, model([altered, mask], training=False).numpy())
    altered = x.copy()
    altered[:, 6:, :405] += 9
    np.testing.assert_array_equal(
        before[:, :6], model([altered, mask], training=False).numpy()[:, :6]
    )
    opt = tf.keras.optimizers.Adam(base["learning_rate"], clipnorm=base["gradient_clip_norm"])
    steps = FusionSteps(tf, model, opt)
    assert steps.update is not None
    loss = steps.update(
        x,
        mask,
        np.array([[0, 1], [12, 12]], np.int32),
        np.array([12, 12], np.int32),
        np.array([2, 2], np.int32),
    )
    assert np.isfinite(loss.numpy())
    path = tmp_path / "fusion.keras"
    model.save(path)
    restored = tf.keras.models.load_model(path)
    np.testing.assert_array_equal(
        model([x, mask], training=False).numpy(), restored([x, mask], training=False).numpy()
    )
