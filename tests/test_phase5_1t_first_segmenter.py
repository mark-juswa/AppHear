from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest

from eval.runtime_diagnostics.phase5_1t_first_segmenter import (
    FEATURE_WIDTH,
    build_model,
    decode_event,
    load_config,
    temporal_labels,
    verify_full_video,
)
from pipeline.perception_vnext.recognition_schema import RAW_SCHEMA, RawSequence
from pipeline.perception_vnext.segmentation.learned_features import (
    apply_normalization,
    derive_causal_segmentation_features,
    feature_names,
    normalization_from_train,
)


def raw_fixture(t: int = 6) -> RawSequence:
    hand_xy = np.zeros((t, 2, 21, 2), np.float32)
    hand_xy[:, :, :, 0] = np.arange(t, dtype=np.float32)[:, None, None] + 10.0
    hand_xy[:, :, :, 1] = 20.0
    body_xy = np.zeros((t, 8, 2), np.float32)
    body_xy[:, :, 0] = 30.0
    body_xy[:, :, 1] = np.arange(t, dtype=np.float32)[:, None] + 40.0
    return RawSequence(
        metadata={
            "schema": RAW_SCHEMA,
            "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB",
            "duration_scope": "whole_isolated_clip",
            "span_start_inclusive": 0,
            "span_end_inclusive": None,
            "source_video_sha256": "a" * 64,
        },
        frame_index=np.arange(t, dtype=np.int32),
        timestamp_ms=np.arange(t, dtype=np.float64) * 100.0,
        source_size=np.tile(np.asarray([[100, 200]], np.int32), (t, 1)),
        hand_xy=hand_xy,
        hand_proposal_support=np.ones((t, 2, 21), np.float32),
        hand_joint_valid=np.ones((t, 2, 21), bool),
        hand_presence=np.full((t, 2), 0.9, np.float32),
        hand_observed=np.ones((t, 2), bool),
        hand_proposal_present=np.ones((t, 2), bool),
        hand_roi_center_side=np.tile(
            np.asarray([[[50.0, 100.0, 25.0], [50.0, 100.0, 25.0]]], np.float32),
            (t, 1, 1),
        ),
        hand_handedness_diagnostic=np.zeros((t, 2), np.float32),
        body_xy=body_xy,
        body_support=np.ones((t, 8), np.float32),
        body_valid=np.ones((t, 8), bool),
        body_available=np.ones((t,), bool),
    )


def test_feature_contract_is_exact_finite_and_causal() -> None:
    raw = raw_fixture()
    first = derive_causal_segmentation_features(raw)
    changed = copy.deepcopy(raw)
    changed.hand_xy[-1] += 500.0
    second = derive_causal_segmentation_features(changed)
    assert first.shape == (6, FEATURE_WIDTH)
    assert len(feature_names()) == FEATURE_WIDTH
    assert np.all(np.isfinite(first))
    np.testing.assert_array_equal(first[:-1], second[:-1])
    assert not np.array_equal(first[-1], second[-1])


def test_missing_geometry_is_zero_with_validity_not_stale_carried() -> None:
    raw = raw_fixture()
    raw.hand_observed[3, 0] = False
    features = derive_causal_segmentation_features(raw)
    assert np.all(features[3, :42] == 0.0)
    assert np.all(features[3, 84:105] == 0.0)
    assert np.all(features[3, 216:258] == 0.0)
    assert np.all(features[3, 300:321] == 0.0)


def test_train_only_normalization_round_trip_is_finite() -> None:
    one = derive_causal_segmentation_features(raw_fixture())
    two = one + np.float32(0.25)
    stats = normalization_from_train([one, two])
    normalized = apply_normalization(one, stats["mean"], stats["std"])
    assert normalized.shape == one.shape
    assert np.all(np.isfinite(normalized))


def test_fixed_ignore_band_label_mapping() -> None:
    timestamps = np.asarray([0, 899, 900, 1000, 1100, 1101, 1899, 1900, 2000, 2100, 2101])
    labels = temporal_labels(timestamps, 1000.0, 2000.0, 100.0)
    assert labels.tolist() == [0, 0, -1, -1, -1, 1, 1, -1, -1, -1, 2]


def test_full_video_verification_rejects_span_scope() -> None:
    raw = raw_fixture()
    proof = verify_full_video(
        raw,
        {"fps": 10.0, "frame_count": 6, "duration_from_frames_ms": 600.0},
        "a" * 64,
    )
    assert proof["scope"] == "FULL_SOURCE_VIDEO"
    raw.metadata["duration_scope"] = "governed_span"
    raw.metadata["span_end_inclusive"] = 5
    with pytest.raises(RuntimeError, match="FULL_VIDEO_SCOPE_IS_CROPPED"):
        verify_full_video(
            raw,
            {"fps": 10.0, "frame_count": 6, "duration_from_frames_ms": 600.0},
            "a" * 64,
        )


def test_decoder_merges_only_fixed_short_gap_and_pads_once() -> None:
    config = load_config()
    timestamps = np.arange(8, dtype=np.float64) * 100.0
    probabilities = np.asarray(
        [
            [0.8, 0.1, 0.1],
            [0.1, 0.8, 0.1],
            [0.1, 0.8, 0.1],
            [0.8, 0.1, 0.1],
            [0.1, 0.8, 0.1],
            [0.1, 0.1, 0.8],
            [0.1, 0.1, 0.8],
            [0.1, 0.1, 0.8],
        ],
        np.float32,
    )
    event = decode_event(timestamps, probabilities, 800.0, config)
    assert event is not None
    assert event["start_ms"] == 0.0
    assert event["end_ms"] == pytest.approx(750.0)


def test_model_is_small_and_future_perturbation_cannot_change_past_logits() -> None:
    import tensorflow as tf

    config = load_config()
    tf.keras.utils.set_random_seed(5103)
    model = build_model(config)
    assert model.count_params() < 200_000
    first = np.zeros((1, 12, FEATURE_WIDTH), np.float32)
    second = first.copy()
    second[:, 8:, :] = 3.0
    a = model(first, training=False).numpy()
    b = model(second, training=False).numpy()
    np.testing.assert_allclose(a[:, :8], b[:, :8], atol=1e-7, rtol=0.0)


def test_utility_does_not_import_recognition_v2_or_recognizer() -> None:
    source = Path("eval/runtime_diagnostics/phase5_1t_first_segmenter.py").read_text(
        encoding="utf-8"
    )
    assert "recognition_schema_v2" not in source
    assert "Recognizer(" not in source
    assert 'class_id"]' not in source.split("def build_model", maxsplit=1)[1]
    assert "SEGMENTATION_FEATURE_SCHEMA" in source
