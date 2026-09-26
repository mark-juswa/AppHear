from __future__ import annotations

import numpy as np

from pipeline.features.dwpose_representation_v2 import (
    BODY_OFFSET,
    FEATURE_WIDTH,
    LEFT_OBSERVED_OFFSET,
    RIGHT_HAND_OFFSET,
    RIGHT_OBSERVED_OFFSET,
    build_frame_features,
    build_padded_sequence,
    feature_index_rows,
)


def native_fixture() -> tuple[np.ndarray, np.ndarray]:
    points = np.zeros((133, 2), dtype=np.float32)
    scores = np.linspace(0.1, 0.99, 133, dtype=np.float32)
    points[:, 0] = np.arange(133, dtype=np.float32) + 100
    points[:, 1] = np.arange(133, dtype=np.float32) * 0.5 + 50
    points[5] = [100, 100]
    points[6] = [200, 100]
    points[11] = [110, 200]
    points[12] = [190, 200]
    return points, scores


def test_contract_width_and_index_map() -> None:
    assert FEATURE_WIDTH == 238
    assert [row["feature_index"] for row in feature_index_rows()] == list(range(238))


def test_shoulder_normalization_and_score_preservation() -> None:
    points, scores = native_fixture()
    feature, diagnostic = build_frame_features(points, scores, np.array([True, True]))
    assert diagnostic.success
    assert diagnostic.center_method == "SHOULDER_PRIMARY"
    assert diagnostic.scale_method == "SHOULDER_DISTANCE_PRIMARY"
    assert diagnostic.center_x == 150
    assert diagnostic.center_y == 100
    assert diagnostic.scale == 100
    assert feature.shape == (238,)
    assert feature.dtype == np.float32
    assert feature[LEFT_OBSERVED_OFFSET] == 1
    assert feature[RIGHT_OBSERVED_OFFSET] == 1
    assert feature[2] == scores[91]
    assert feature[BODY_OFFSET + 5 * 4] == -0.5


def test_unobserved_hand_is_fully_zero_without_stale_geometry() -> None:
    points, scores = native_fixture()
    feature, _ = build_frame_features(points, scores, np.array([False, True]))
    assert np.all(feature[:RIGHT_HAND_OFFSET] == 0)
    assert feature[LEFT_OBSERVED_OFFSET] == 0
    assert feature[RIGHT_OBSERVED_OFFSET] == 1
    assert np.any(feature[RIGHT_HAND_OFFSET:BODY_OFFSET] != 0)


def test_invalid_point_is_zero_masked() -> None:
    points, scores = native_fixture()
    points[91] = np.nan
    feature, _ = build_frame_features(points, scores, np.array([True, True]))
    assert np.all(feature[:4] == 0)
    assert feature[7] == 1


def test_hip_fallback_is_current_frame_only() -> None:
    points, scores = native_fixture()
    points[5:7] = np.nan
    feature, diagnostic = build_frame_features(points, scores, np.array([True, True]))
    assert diagnostic.success
    assert diagnostic.center_method == "HIP_FALLBACK"
    assert diagnostic.scale_method == "VALID_BODY_ENVELOPE_FALLBACK"
    assert np.all(np.isfinite(feature))


def test_sequence_padding_and_determinism() -> None:
    points, scores = native_fixture()
    feature_a, _ = build_frame_features(points, scores, np.array([True, False]))
    feature_b, _ = build_frame_features(points, scores, np.array([True, False]))
    assert feature_a.tobytes() == feature_b.tobytes()
    sequence, mask, length = build_padded_sequence([feature_a, feature_b])
    assert sequence.shape == (96, 238)
    assert sequence.dtype == np.float32
    assert length == 2
    assert mask[:2].all() and not mask[2:].any()
    assert np.all(sequence[2:] == 0)
