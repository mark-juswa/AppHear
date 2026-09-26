from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.perception_vnext.recognition_schema import (
    FEATURE_WIDTH,
    RAW_SCHEMA,
    RawSequence,
    body_point_valid,
    derive_frame_features,
    load_raw_sequence,
    save_raw_sequence,
    temporal_view,
)


def _raw() -> RawSequence:
    t = 3
    hand_xy = np.full((t, 2, 21, 2), np.nan, np.float32)
    hand_xy[:, 0] = np.asarray([120.0, 180.0], np.float32)
    hand_valid = np.zeros((t, 2, 21), bool)
    hand_valid[:, 0] = True
    body_xy = np.zeros((t, 8, 2), np.float32)
    body_xy[:, 0] = [100.0, 100.0]
    body_xy[:, 1] = [200.0, 100.0]
    body_valid = np.zeros((t, 8), bool)
    body_valid[:, :2] = True
    return RawSequence(
        metadata={
            "schema": RAW_SCHEMA,
            "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB",
            "sample_id": "unit",
        },
        frame_index=np.arange(t, dtype=np.int32),
        timestamp_ms=np.asarray([0.0, 100.0, 300.0], np.float64),
        source_size=np.tile(np.asarray([480, 640], np.int32), (t, 1)),
        hand_xy=hand_xy,
        hand_proposal_support=np.ones((t, 2, 21), np.float32),
        hand_joint_valid=hand_valid,
        hand_presence=np.asarray([[0.9, np.nan]] * t, np.float32),
        hand_observed=np.asarray([[True, False]] * t, bool),
        hand_proposal_present=np.asarray([[True, False]] * t, bool),
        hand_roi_center_side=np.full((t, 2, 3), np.nan, np.float32),
        hand_handedness_diagnostic=np.full((t, 2), np.nan, np.float32),
        body_xy=body_xy,
        body_support=np.ones((t, 8), np.float32),
        body_valid=body_valid,
        body_available=np.zeros((t,), bool),
    )


def test_body_validity_requires_support_finite_and_in_source() -> None:
    xy = np.asarray([[1, 2], [3, 4], [-1, 2], [2, np.nan]], np.float32)
    support = np.asarray([0.3, 0.2999, 0.9, 0.9], np.float32)
    assert body_point_valid(xy, support, 10, 10).tolist() == [True, False, False, False]


def test_raw_save_reload_and_derived_missingness(tmp_path: Path) -> None:
    raw = _raw()
    destination = tmp_path / "raw.npz"
    save_raw_sequence(destination, raw)
    reloaded = load_raw_sequence(destination)
    features = derive_frame_features(reloaded)
    assert features.shape == (3, FEATURE_WIDTH)
    assert np.all(np.isfinite(features))
    # The unobserved RH position block is zero even though raw missingness remains NaN.
    assert np.all(features[:, 84:168].reshape(3, 21, 4)[:, :, :2] == 0)
    np.testing.assert_allclose(features[:, 204:206], [[0, 1]] * 3)
    np.testing.assert_allclose(features[:, 206], [0.0, 0.1, 0.2])
    np.testing.assert_allclose(features[:, 207], [0.0, 1 / 3, 1.0])


def test_temporal_views_never_copy_padding_as_evidence() -> None:
    raw = _raw()
    features = derive_frame_features(raw)
    dense = temporal_view(features, raw.timestamp_ms, condition="dense", phone_completed_fps=5.0)
    sparse = temporal_view(
        features,
        raw.timestamp_ms,
        condition="phone_01_sparse",
        phone_completed_fps=5.0,
    )
    assert dense["source_indices"].tolist() == [0, 1, 2]
    # The 200 ms grid target is equidistant from 100 and 300; the stable tie picks earlier.
    assert sparse["source_indices"].tolist() == [0, 1]
    assert dense["mask"].sum() == 3
    assert sparse["mask"].sum() == 2
    assert np.all(dense["features"][~dense["mask"]] == 0)
    assert np.all(sparse["features"][~sparse["mask"]] == 0)
