"""Causal raw-v1 feature contract for the first learned sign segmenter.

The contract deliberately keeps current-frame evidence and backward-only
transitions separate.  Missing geometry is encoded as zero together with an
explicit validity channel; it is never carried forward or interpolated.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pipeline.perception_vnext.recognition_schema import HAND_POINTS, RawSequence

SEGMENTATION_FEATURE_SCHEMA = "apphear.perception_vnext.segmentation_features.v1"
FEATURE_WIDTH = 378


@dataclass(frozen=True)
class FeatureBlock:
    name: str
    start: int
    width: int
    semantics: str


FEATURE_BLOCKS = (
    FeatureBlock(
        "hand_xy_image", 0, 84, "current refined XY / source width,height; zero when invalid"
    ),
    FeatureBlock(
        "hand_joint_valid", 84, 42, "current refined joint validity including observed state"
    ),
    FeatureBlock("hand_proposal_support", 126, 42, "current DWPose proposal support"),
    FeatureBlock(
        "hand_presence", 168, 2, "current finite MediaPipe group-presence value, else zero"
    ),
    FeatureBlock("hand_presence_valid", 170, 2, "presence value is finite"),
    FeatureBlock("hand_observed", 172, 2, "current refined-hand observed state"),
    FeatureBlock("hand_proposal_present", 174, 2, "current proposal/ROI state"),
    FeatureBlock(
        "hand_roi_image", 176, 6, "current ROI center x/y and side normalized to source geometry"
    ),
    FeatureBlock(
        "body_xy_image", 182, 16, "current body XY / source width,height; zero when invalid"
    ),
    FeatureBlock("body_support", 198, 8, "current DWPose body support"),
    FeatureBlock("body_valid", 206, 8, "current body-point validity"),
    FeatureBlock("body_available", 214, 1, "current complete-body-group availability"),
    FeatureBlock(
        "dt_seconds", 215, 1, "actual backward source-timestamp delta, clipped to one second"
    ),
    FeatureBlock(
        "hand_xy_delta", 216, 84, "current minus previous normalized refined XY when both valid"
    ),
    FeatureBlock("hand_delta_valid", 300, 42, "both current and previous refined joints valid"),
    FeatureBlock(
        "hand_roi_delta", 342, 6, "current minus previous normalized ROI when both proposals exist"
    ),
    FeatureBlock("hand_roi_delta_valid", 348, 2, "both current and previous hand proposals exist"),
    FeatureBlock(
        "body_xy_delta", 350, 16, "current minus previous normalized body XY when both valid"
    ),
    FeatureBlock("body_delta_valid", 366, 8, "both current and previous body points valid"),
    FeatureBlock("hand_observed_transition", 374, 2, "current minus previous observed state"),
    FeatureBlock("hand_proposal_transition", 376, 2, "current minus previous proposal state"),
)


def feature_names() -> list[str]:
    names: list[str] = []
    for side in ("left", "right"):
        for joint in range(HAND_POINTS):
            for axis in ("x", "y"):
                names.append(f"hand_xy_image.{side}.{joint}.{axis}")
    for side in ("left", "right"):
        for joint in range(HAND_POINTS):
            names.append(f"hand_joint_valid.{side}.{joint}")
    for side in ("left", "right"):
        for joint in range(HAND_POINTS):
            names.append(f"hand_proposal_support.{side}.{joint}")
    names.extend(f"hand_presence.{side}" for side in ("left", "right"))
    names.extend(f"hand_presence_valid.{side}" for side in ("left", "right"))
    names.extend(f"hand_observed.{side}" for side in ("left", "right"))
    names.extend(f"hand_proposal_present.{side}" for side in ("left", "right"))
    for side in ("left", "right"):
        names.extend(f"hand_roi_image.{side}.{value}" for value in ("x", "y", "side"))
    for point in range(8):
        names.extend(f"body_xy_image.{point}.{axis}" for axis in ("x", "y"))
    names.extend(f"body_support.{point}" for point in range(8))
    names.extend(f"body_valid.{point}" for point in range(8))
    names.extend(("body_available", "dt_seconds"))
    for side in ("left", "right"):
        for joint in range(HAND_POINTS):
            for axis in ("x", "y"):
                names.append(f"hand_xy_delta.{side}.{joint}.{axis}")
    for side in ("left", "right"):
        for joint in range(HAND_POINTS):
            names.append(f"hand_delta_valid.{side}.{joint}")
    for side in ("left", "right"):
        names.extend(f"hand_roi_delta.{side}.{value}" for value in ("x", "y", "side"))
    names.extend(f"hand_roi_delta_valid.{side}" for side in ("left", "right"))
    for point in range(8):
        names.extend(f"body_xy_delta.{point}.{axis}" for axis in ("x", "y"))
    names.extend(f"body_delta_valid.{point}" for point in range(8))
    names.extend(f"hand_observed_transition.{side}" for side in ("left", "right"))
    names.extend(f"hand_proposal_transition.{side}" for side in ("left", "right"))
    if len(names) != FEATURE_WIDTH:
        raise AssertionError(f"feature name width mismatch: {len(names)}")
    return names


def _current_geometry(raw: RawSequence) -> tuple[np.ndarray, ...]:
    size = raw.source_size.astype(np.float32)
    widths = np.maximum(size[:, 0], 1.0)
    heights = np.maximum(size[:, 1], 1.0)
    short_sides = np.maximum(np.minimum(widths, heights), 1.0)

    hand_scale = np.stack([widths, heights], axis=-1)[:, None, None, :]
    hand_valid = raw.hand_joint_valid.astype(bool) & raw.hand_observed[:, :, None]
    hand_xy = raw.hand_xy.astype(np.float32) / hand_scale
    hand_xy[~hand_valid] = 0.0

    proposal_support = np.nan_to_num(
        raw.hand_proposal_support.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0
    )
    presence_valid = np.isfinite(raw.hand_presence)
    presence = np.where(presence_valid, raw.hand_presence, 0.0).astype(np.float32)

    roi = raw.hand_roi_center_side.astype(np.float32).copy()
    roi[:, :, 0] /= widths[:, None]
    roi[:, :, 1] /= heights[:, None]
    roi[:, :, 2] /= short_sides[:, None]
    proposal = raw.hand_proposal_present.astype(bool)
    roi[~proposal] = 0.0

    body_scale = np.stack([widths, heights], axis=-1)[:, None, :]
    body_valid = raw.body_valid.astype(bool)
    body_xy = raw.body_xy.astype(np.float32) / body_scale
    body_xy[~body_valid] = 0.0
    body_support = np.nan_to_num(
        raw.body_support.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0
    )
    return (
        hand_xy,
        hand_valid,
        proposal_support,
        presence,
        presence_valid,
        roi,
        proposal,
        body_xy,
        body_valid,
        body_support,
    )


def derive_causal_segmentation_features(raw: RawSequence) -> np.ndarray:
    """Return finite `[T,378]` features using only current and prior observations."""

    raw.validate()
    (
        hand_xy,
        hand_valid,
        proposal_support,
        presence,
        presence_valid,
        roi,
        proposal,
        body_xy,
        body_valid,
        body_support,
    ) = _current_geometry(raw)
    t = len(raw.timestamp_ms)
    result = np.zeros((t, FEATURE_WIDTH), np.float32)
    cursor = 0

    def put(value: np.ndarray) -> None:
        nonlocal cursor
        flat = np.asarray(value, np.float32).reshape(t, -1)
        result[:, cursor : cursor + flat.shape[1]] = flat
        cursor += flat.shape[1]

    put(hand_xy)
    put(hand_valid)
    put(proposal_support)
    put(presence)
    put(presence_valid)
    put(raw.hand_observed)
    put(proposal)
    put(roi)
    put(body_xy)
    put(body_support)
    put(body_valid)
    put(raw.body_available)
    dt = np.zeros((t,), np.float32)
    if t > 1:
        dt[1:] = np.clip(np.diff(raw.timestamp_ms) / 1000.0, 0.0, 1.0).astype(np.float32)
    put(dt)

    hand_delta_valid = np.zeros_like(hand_valid)
    hand_delta = np.zeros_like(hand_xy)
    roi_delta_valid = np.zeros_like(proposal)
    roi_delta = np.zeros_like(roi)
    body_delta_valid = np.zeros_like(body_valid)
    body_delta = np.zeros_like(body_xy)
    observed_transition = np.zeros_like(raw.hand_observed, np.float32)
    proposal_transition = np.zeros_like(proposal, np.float32)
    if t > 1:
        hand_delta_valid[1:] = hand_valid[1:] & hand_valid[:-1]
        candidate = hand_xy[1:] - hand_xy[:-1]
        hand_delta[1:] = np.where(hand_delta_valid[1:, :, :, None], candidate, 0.0)
        roi_delta_valid[1:] = proposal[1:] & proposal[:-1]
        roi_delta[1:] = np.where(roi_delta_valid[1:, :, None], roi[1:] - roi[:-1], 0.0)
        body_delta_valid[1:] = body_valid[1:] & body_valid[:-1]
        body_delta[1:] = np.where(body_delta_valid[1:, :, None], body_xy[1:] - body_xy[:-1], 0.0)
        observed_transition[1:] = raw.hand_observed[1:].astype(np.float32) - raw.hand_observed[
            :-1
        ].astype(np.float32)
        proposal_transition[1:] = proposal[1:].astype(np.float32) - proposal[:-1].astype(np.float32)
    put(hand_delta)
    put(hand_delta_valid)
    put(roi_delta)
    put(roi_delta_valid)
    put(body_delta)
    put(body_delta_valid)
    put(observed_transition)
    put(proposal_transition)

    if cursor != FEATURE_WIDTH:
        raise AssertionError(f"segmentation feature width mismatch: {cursor}")
    if not np.all(np.isfinite(result)):
        raise ValueError("segmentation features contain NaN/Inf")
    return result


def normalization_from_train(feature_sequences: list[np.ndarray]) -> dict[str, np.ndarray]:
    if not feature_sequences:
        raise ValueError("no TRAIN feature sequences")
    values = np.concatenate([np.asarray(value, np.float64) for value in feature_sequences], axis=0)
    if values.ndim != 2 or values.shape[1] != FEATURE_WIDTH:
        raise ValueError("TRAIN feature width mismatch")
    mean = values.mean(axis=0)
    std = values.std(axis=0)
    std = np.where(std >= 1e-6, std, 1.0)
    return {"mean": mean.astype(np.float32), "std": std.astype(np.float32)}


def apply_normalization(features: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    value = (np.asarray(features, np.float32) - np.asarray(mean, np.float32)) / np.asarray(
        std, np.float32
    )
    if value.shape[-1] != FEATURE_WIDTH or not np.all(np.isfinite(value)):
        raise ValueError("normalized segmentation feature tensor is invalid")
    return value.astype(np.float32)
