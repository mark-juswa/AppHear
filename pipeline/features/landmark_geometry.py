"""Experiment-only E6-2 landmark geometry derived from schema v3.0.

The first 258 channels are preserved exactly. This module does not change the
production feature contract or Android runtime.
"""

from __future__ import annotations

import numpy as np

from pipeline.features.contract import FEATURE_DIM

SCHEMA_ID = "apphear.landmark_geometry.v0"
HAND_LOCAL_DIM = 120
JOINT_COSINE_DIM = 28
PALM_NORMAL_DIM = 6
BODY_HEAD_RELATION_DIM = 28
QUALITY_MASK_DIM = 4
GEOMETRY_DIM = (
    FEATURE_DIM
    + HAND_LOCAL_DIM
    + JOINT_COSINE_DIM
    + PALM_NORMAL_DIM
    + BODY_HEAD_RELATION_DIM
    + QUALITY_MASK_DIM
)

_EPS = np.float32(1e-6)
_JOINT_TRIPLES = (
    (1, 2, 3),
    (2, 3, 4),
    (0, 5, 6),
    (5, 6, 7),
    (6, 7, 8),
    (0, 9, 10),
    (9, 10, 11),
    (10, 11, 12),
    (0, 13, 14),
    (13, 14, 15),
    (14, 15, 16),
    (0, 17, 18),
    (17, 18, 19),
    (18, 19, 20),
)
_POSE_ANCHORS = (
    # eye, ear, shoulder for canonical left/right hand slots.
    (2, 7, 11),
    (5, 8, 12),
)


def _safe_unit(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    norm = np.linalg.norm(values, axis=-1, keepdims=True)
    valid = norm[..., 0] >= _EPS
    unit = np.divide(values, norm, out=np.zeros_like(values), where=norm >= _EPS)
    return unit.astype(np.float32), valid


def _joint_cosines(hand: np.ndarray, valid: np.ndarray) -> np.ndarray:
    result = []
    for first, center, last in _JOINT_TRIPLES:
        left, left_valid = _safe_unit(hand[..., first, :] - hand[..., center, :])
        right, right_valid = _safe_unit(hand[..., last, :] - hand[..., center, :])
        cosine = np.sum(left * right, axis=-1)
        cosine = np.where(valid & left_valid & right_valid, np.clip(cosine, -1.0, 1.0), 0.0)
        result.append(cosine.astype(np.float32))
    return np.stack(result, axis=-1).astype(np.float32)


def build_landmark_geometry(
    base_features: np.ndarray, frame_mask: np.ndarray
) -> tuple[np.ndarray, dict[str, object]]:
    """Append E6-2 geometry to `(N,T,258)` or `(T,258)` v3.0 features."""
    source = np.asarray(base_features, dtype=np.float32)
    squeeze = source.ndim == 2
    if squeeze:
        source = source[None, ...]
    if source.ndim != 3 or source.shape[-1] != FEATURE_DIM:
        raise ValueError(f"expected [N,T,{FEATURE_DIM}], got {source.shape}")
    mask = np.asarray(frame_mask, dtype=bool)
    if mask.ndim == 1:
        mask = mask[None, ...]
    if mask.shape != source.shape[:2]:
        raise ValueError(f"frame_mask must have shape {source.shape[:2]}, got {mask.shape}")

    n, t, _ = source.shape
    hands = source[..., :126].reshape(n, t, 2, 21, 3)
    pose = source[..., 126:].reshape(n, t, 33, 4)
    pose_xyz = pose[..., :3]
    pose_vis = pose[..., 3]
    hand_present = np.any(hands != 0.0, axis=(-2, -1)) & mask[..., None]

    wrist = hands[..., 0, :]
    index_mcp = hands[..., 5, :]
    pinky_mcp = hands[..., 17, :]
    palm_scale = 0.5 * (
        np.linalg.norm(index_mcp - wrist, axis=-1)
        + np.linalg.norm(pinky_mcp - wrist, axis=-1)
    )
    hand_valid = hand_present & (palm_scale >= _EPS)

    local = hands[..., 1:, :] - wrist[..., None, :]
    local = np.divide(
        local,
        palm_scale[..., None, None],
        out=np.zeros_like(local),
        where=palm_scale[..., None, None] >= _EPS,
    )
    local = np.where(hand_valid[..., None, None], np.clip(local, -4.0, 4.0), 0.0)
    hand_local = local.reshape(n, t, HAND_LOCAL_DIM).astype(np.float32)

    angle_parts = [_joint_cosines(hands[..., side, :, :], hand_valid[..., side]) for side in range(2)]
    joint_cosines = np.concatenate(angle_parts, axis=-1).astype(np.float32)

    palm_cross = np.cross(index_mcp - wrist, pinky_mcp - wrist)
    palm_unit, palm_unit_valid = _safe_unit(palm_cross)
    palm_unit = np.where((hand_valid & palm_unit_valid)[..., None], palm_unit, 0.0)
    palm_normals = palm_unit.reshape(n, t, PALM_NORMAL_DIM).astype(np.float32)

    nose = pose_xyz[..., 0, :]
    nose_valid = (pose_vis[..., 0] > 0.0) & mask
    centroids = np.mean(hands, axis=-2)
    relation_parts = []
    for side, (eye_index, ear_index, shoulder_index) in enumerate(_POSE_ANCHORS):
        present = hand_present[..., side]

        def relation(point: np.ndarray, anchor_index: int) -> np.ndarray:
            anchor_valid = (pose_vis[..., anchor_index] > 0.0) & mask
            valid = present & anchor_valid
            values = point - pose_xyz[..., anchor_index, :]
            return np.where(valid[..., None], np.clip(values, -4.0, 4.0), 0.0)

        centroid_to_nose = np.where(
            (present & nose_valid)[..., None],
            np.clip(centroids[..., side, :] - nose, -4.0, 4.0),
            0.0,
        )
        relation_parts.extend(
            [
                centroid_to_nose,
                relation(hands[..., side, 8, :], eye_index),
                relation(hands[..., side, 8, :], ear_index),
                relation(wrist[..., side, :], shoulder_index),
            ]
        )
    both = hand_present[..., 0] & hand_present[..., 1]
    hand_vector = centroids[..., 0, :] - centroids[..., 1, :]
    hand_vector = np.where(both[..., None], np.clip(hand_vector, -4.0, 4.0), 0.0)
    hand_distance = np.where(both, np.linalg.norm(hand_vector, axis=-1), 0.0)[..., None]
    relations = np.concatenate([*relation_parts, hand_vector, hand_distance], axis=-1).astype(np.float32)

    pose_visibility_mean = (np.mean(pose_vis, axis=-1) * mask)[..., None]
    quality_masks = np.concatenate(
        [
            pose_visibility_mean,
            hand_present[..., 0, None].astype(np.float32),
            hand_present[..., 1, None].astype(np.float32),
            mask[..., None].astype(np.float32),
        ],
        axis=-1,
    )
    output = np.concatenate(
        [source, hand_local, joint_cosines, palm_normals, relations, quality_masks], axis=-1
    ).astype(np.float32)
    output[~mask] = 0.0
    if output.shape[-1] != GEOMETRY_DIM:
        raise AssertionError(f"geometry width mismatch: {output.shape[-1]}")
    if not np.isfinite(output).all():
        raise ValueError("geometry tensor contains NaN or Inf")
    schema = {
        "schema_id": SCHEMA_ID,
        "shape": [int(source.shape[1]), GEOMETRY_DIM],
        "layout": [
            {"name": "base_v30", "start": 0, "end_exclusive": 258},
            {"name": "hand_local_xyz", "start": 258, "end_exclusive": 378},
            {"name": "joint_cosines", "start": 378, "end_exclusive": 406},
            {"name": "palm_normals", "start": 406, "end_exclusive": 412},
            {"name": "body_head_relations", "start": 412, "end_exclusive": 440},
            {"name": "quality_and_masks", "start": 440, "end_exclusive": 444},
        ],
        "base_channels_preserved": bool(np.array_equal(output[..., :FEATURE_DIM], source)),
    }
    return (output[0] if squeeze else output), schema


def augment_landmark_geometry_batch(
    values: np.ndarray,
    config: object,
    rng: np.random.Generator,
    valid_frame_mask: np.ndarray,
) -> np.ndarray:
    """Augment v3.0 channels, then deterministically rebuild all derived channels."""
    from model.augment import augment_batch

    base = np.asarray(values, dtype=np.float32)[..., :FEATURE_DIM]
    augmented_base = augment_batch(base, config, rng, valid_frame_mask=valid_frame_mask)
    rebuilt, _ = build_landmark_geometry(augmented_base, valid_frame_mask)
    return rebuilt
