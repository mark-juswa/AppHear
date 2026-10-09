from __future__ import annotations

import numpy as np

from pipeline.perception_vnext.recognition_schema import RAW_SCHEMA, RawSequence
from pipeline.perception_vnext.recognition_schema_v2 import (
    FEATURE_WIDTH_V2,
    derive_selected_features_v2,
    temporal_view_v2,
)


def _hand(wrist: np.ndarray, side: float) -> np.ndarray:
    points = np.zeros((21, 2), np.float32)
    points[0] = wrist
    bases = ((1, -0.55), (5, -0.28), (9, 0.0), (13, 0.26), (17, 0.50))
    for start, lateral in bases:
        chain = 4 if start == 1 else 4
        for offset in range(chain):
            points[start + offset] = wrist + np.asarray(
                [side * (lateral + 0.03 * offset), -(0.35 + 0.28 * offset)],
                np.float32,
            ) * 70.0
    return points


def _raw(transform: tuple[float, float, float, float] | None = None) -> RawSequence:
    timestamps = np.asarray([0.0, 80.0, 190.0, 320.0], np.float64)
    body_base = np.asarray(
        [
            [190, 190],
            [290, 190],
            [170, 250],
            [310, 250],
            [155, 315],
            [325, 315],
            [205, 360],
            [275, 360],
        ],
        np.float32,
    )
    body = np.repeat(body_base[None], len(timestamps), axis=0)
    hands = np.zeros((len(timestamps), 2, 21, 2), np.float32)
    for frame in range(len(timestamps)):
        hands[frame, 0] = _hand(np.asarray([185 + 8 * frame, 265 - 3 * frame]), 1.0)
        hands[frame, 1] = _hand(np.asarray([295 - 5 * frame, 270 + 2 * frame]), -1.0)

    if transform is not None:
        scale, radians, translate_x, translate_y = transform
        rotation = np.asarray(
            [
                [np.cos(radians), -np.sin(radians)],
                [np.sin(radians), np.cos(radians)],
            ],
            np.float32,
        )
        body = body @ rotation.T * scale + np.asarray([translate_x, translate_y])
        hands = hands @ rotation.T * scale + np.asarray([translate_x, translate_y])

    return RawSequence(
        metadata={
            "schema": RAW_SCHEMA,
            "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB",
            "sample_id": "v2_unit",
        },
        frame_index=np.arange(len(timestamps), dtype=np.int32),
        timestamp_ms=timestamps,
        source_size=np.tile(np.asarray([720, 960], np.int32), (len(timestamps), 1)),
        hand_xy=hands,
        hand_proposal_support=np.full((len(timestamps), 2, 21), 0.8, np.float32),
        hand_joint_valid=np.ones((len(timestamps), 2, 21), bool),
        hand_presence=np.full((len(timestamps), 2), 0.9, np.float32),
        hand_observed=np.ones((len(timestamps), 2), bool),
        hand_proposal_present=np.ones((len(timestamps), 2), bool),
        hand_roi_center_side=np.zeros((len(timestamps), 2, 3), np.float32),
        hand_handedness_diagnostic=np.zeros((len(timestamps), 2), np.float32),
        body_xy=body,
        body_support=np.full((len(timestamps), 8), 0.85, np.float32),
        body_valid=np.ones((len(timestamps), 8), bool),
        body_available=np.ones(len(timestamps), bool),
    )


def test_v2_is_invariant_to_global_similarity_transform() -> None:
    original = _raw()
    transformed = _raw((1.7, 0.43, 110.0, -45.0))
    indices = np.arange(len(original.timestamp_ms), dtype=np.int32)
    before = derive_selected_features_v2(original, indices)
    after = derive_selected_features_v2(transformed, indices)
    assert before.shape == (4, FEATURE_WIDTH_V2)
    np.testing.assert_allclose(before, after, atol=2.0e-5, rtol=2.0e-5)


def test_v2_missing_joint_is_zero_with_explicit_invalidity() -> None:
    raw = _raw()
    raw.hand_joint_valid[:, 0, 13] = False
    raw.hand_xy[:, 0, 13] = np.nan
    features = derive_selected_features_v2(raw, np.arange(4, dtype=np.int32))
    assert np.all(np.isfinite(features))
    # Ring-finger MCP invalidates its three adjacent angle/bone relations, while
    # the four-point palm reference and the rest of the hand remain usable.
    assert np.all(features[:, 129] == 1.0)
    assert np.any(features[:, :40] != 0.0)


def test_v2_temporal_views_use_real_selected_timestamps_and_zero_padding() -> None:
    raw = _raw()
    dense = temporal_view_v2(
        raw, condition="dense", phone_completed_fps=5.0
    )
    sparse = temporal_view_v2(
        raw, condition="phone_01_sparse", phone_completed_fps=5.0
    )
    assert dense["source_indices"].tolist() == [0, 1, 2, 3]
    assert sparse["source_indices"].tolist() == [0, 2]
    np.testing.assert_allclose(sparse["source_timestamps_ms"], [0.0, 190.0])
    assert sparse["features"][1, 348] == np.float32(0.19)
    assert dense["mask"].sum() == 4
    assert sparse["mask"].sum() == 2
    assert np.all(dense["features"][~dense["mask"]] == 0.0)
    assert np.all(sparse["features"][~sparse["mask"]] == 0.0)
