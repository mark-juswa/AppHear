"""Causal, common PhoneRawObservation-only fingerspelling features. No inference."""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.perception_vnext.recognition_schema import RAW_SCHEMA, RawSequence

VERSION = "FingerspellingFeatureAdapter.v1"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config/fingerspelling_features_v1.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
WIDTH = 405


def validate_config() -> None:
    expected_targets = [chr(c) for c in range(ord("A"), ord("Z") + 1)] + ["SPACE"]
    if (
        CONFIG["schema_version"] != VERSION
        or CONFIG["feature_width"] != WIDTH
        or CONFIG["raw_schema"] != RAW_SCHEMA
        or CONFIG["target_order"] != expected_targets
        or CONFIG["ctc_blank_index"] != 27
        or CONFIG["scale_mcp_indices"] != [5, 9, 13, 17]
        or CONFIG["body_indices"] != [5, 6, 7, 8, 9, 10, 11, 12]
        or CONFIG["horizontal_augmentation"] is not False
        or CONFIG["reflection_policy"] != "USE_RELEASED_PIXELS_AS_IS"
    ):
        raise ValueError("[fingerspelling/config] Frozen schema/class order/policy mismatch")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def column_names() -> list[str]:
    names = ["dt_seconds", "dt_valid"]
    joint_fields = [
        "source_x",
        "source_y",
        "local_x",
        "local_y",
        "source_valid",
        "local_valid",
        "proposal_support",
        "support_valid",
    ]
    extra = [
        "presence",
        "presence_valid",
        "observed",
        "proposal_present",
        "roi_x",
        "roi_y",
        "roi_side",
        "roi_valid",
        "palm_scale",
        "scale_valid",
        "wrist_dx",
        "wrist_dy",
        "motion_valid",
    ]
    for slot in range(2):
        names.extend(f"slot{slot}.joint{j}.{f}" for j in range(21) for f in joint_fields)
        names.extend(f"slot{slot}.{f}" for f in extra)
    names.extend(
        f"body{p}.{f}"
        for p in CONFIG["body_indices"]
        for f in ["source_x", "source_y", "support", "xy_valid", "support_valid"]
    )
    names.append("body_available")
    assert len(names) == WIDTH
    return names


def identity() -> dict[str, Any]:
    validate_config()
    return {
        "schema_version": VERSION,
        "feature_width": WIDTH,
        "config_sha256": sha256(CONFIG_PATH),
        "implementation_sha256": sha256(Path(__file__)),
        "columns_sha256": hashlib.sha256("\n".join(column_names()).encode()).hexdigest(),
    }


def subset(raw: RawSequence, indices: np.ndarray) -> RawSequence:
    """A view selects genuine observations; motion is recomputed from selected neighbors."""
    return RawSequence(
        metadata=dict(raw.metadata),
        **{
            f.name: np.asarray(getattr(raw, f.name))[indices]
            for f in fields(raw)
            if f.name != "metadata"
        },
    )


def phone_indices(timestamps_ms: np.ndarray, rate: float | None = None) -> np.ndarray:
    """Greedy causal gate: first frame, then first real frame >= last selected + period."""
    rate = CONFIG["phone_observations_per_second"] if rate is None else rate
    if not np.isfinite(rate) or rate <= 0 or not len(timestamps_ms):
        raise ValueError("[fingerspelling/cadence] Invalid rate or empty sequence")
    if not np.isfinite(timestamps_ms).all() or not (np.diff(timestamps_ms) > 0).all():
        raise ValueError("[fingerspelling/cadence] Non-chronological timestamps")
    selected = [0]
    period = 1000.0 / rate
    for i in range(1, len(timestamps_ms)):
        if timestamps_ms[i] - timestamps_ms[selected[-1]] >= period:
            selected.append(i)
    return np.asarray(selected, np.int32)


def derive(raw: RawSequence) -> np.ndarray:
    """Float32 geometry; float64 timestamps. No future normalization or hidden fill."""
    validate_config()
    raw.validate()
    if raw.metadata.get("schema") != RAW_SCHEMA or CONFIG["schema_version"] != VERSION:
        raise ValueError("[fingerspelling/adapter] Schema mismatch")
    if CONFIG["feature_width"] != WIDTH:
        raise ValueError("[fingerspelling/adapter] Width mismatch")
    t = len(raw.frame_index)
    if not np.isfinite(raw.timestamp_ms).all() or (raw.source_size <= 0).any():
        raise ValueError("[fingerspelling/adapter] Invalid timestamp/source size")
    out = np.zeros((t, WIDTH), np.float32)
    out[1:, 0] = np.diff(raw.timestamp_ms) / 1000.0
    out[1:, 1] = 1
    wh = raw.source_size.astype(np.float32)
    short = wh.min(axis=1)
    xy = raw.hand_xy.astype(np.float32)
    valid = raw.hand_joint_valid.astype(bool) & raw.hand_observed[:, :, None].astype(bool)
    scale_joints = CONFIG["scale_mcp_indices"]
    # Explicit summation order shared with Kotlin, not a reduction with platform-dependent order.
    distances = []
    for j in scale_joints:
        delta = xy[:, :, j] - xy[:, :, 0]
        distances.append(
            np.sqrt(delta[:, :, 0] * delta[:, :, 0] + delta[:, :, 1] * delta[:, :, 1]).astype(
                np.float32
            )
        )
    scale = ((distances[0] + distances[1]) + distances[2]) + distances[3]
    scale = scale / np.float32(len(scale_joints))
    scale_valid = valid[:, :, 0] & valid[:, :, scale_joints].all(axis=2)
    scale_valid &= np.isfinite(scale) & (
        scale > short[:, None] * np.float32(CONFIG["minimum_scale_short_side_ratio"])
    )
    for slot in range(2):
        start = 2 + slot * 181
        joint = out[:, start : start + 168].reshape(t, 21, 8)
        joint[:, :, :2] = np.where(valid[:, slot, :, None], xy[:, slot] / wh[:, None], 0)
        local_valid = valid[:, slot] & scale_valid[:, slot, None]
        denominator = np.where(scale_valid[:, slot], scale[:, slot], np.float32(1))
        joint[:, :, 2:4] = np.where(
            local_valid[:, :, None],
            (xy[:, slot] - xy[:, slot, 0, None]) / denominator[:, None, None],
            0,
        )
        joint[:, :, 4] = valid[:, slot]
        joint[:, :, 5] = local_valid
        support = raw.hand_proposal_support[:, slot]
        support_valid = np.isfinite(support)
        joint[:, :, 6] = np.where(support_valid, support, 0)
        joint[:, :, 7] = support_valid
        extra = out[:, start + 168 : start + 181]
        presence = raw.hand_presence[:, slot]
        extra[:, 0] = np.where(np.isfinite(presence), presence, 0)
        extra[:, 1] = np.isfinite(presence)
        extra[:, 2] = raw.hand_observed[:, slot]
        extra[:, 3] = raw.hand_proposal_present[:, slot]
        roi = raw.hand_roi_center_side[:, slot]
        roi_valid = (
            raw.hand_proposal_present[:, slot] & np.isfinite(roi).all(axis=1) & (roi[:, 2] > 0)
        )
        extra[:, 4:7] = np.where(roi_valid[:, None], roi / np.column_stack((wh, short)), 0)
        extra[:, 7] = roi_valid
        extra[:, 8] = np.where(scale_valid[:, slot], scale[:, slot] / short, 0)
        extra[:, 9] = scale_valid[:, slot]
        motion = valid[1:, slot, 0] & valid[:-1, slot, 0]
        motion &= (raw.source_size[1:] == raw.source_size[:-1]).all(axis=1)
        motion &= out[1:, 0] <= CONFIG["maximum_motion_gap_seconds"]
        extra[1:, 10:12] = np.where(
            motion[:, None], (xy[1:, slot, 0] - xy[:-1, slot, 0]) / short[1:, None], 0
        )
        extra[1:, 12] = motion
    body = out[:, 364:404].reshape(t, 8, 5)
    body[:, :, :2] = np.where(
        raw.body_valid[:, :, None], raw.body_xy.astype(np.float32) / wh[:, None], 0
    )
    finite = np.isfinite(raw.body_support)
    body[:, :, 2] = np.where(finite, raw.body_support, 0)
    body[:, :, 3] = raw.body_valid
    body[:, :, 4] = finite
    out[:, 404] = raw.body_available
    if not np.isfinite(out).all():
        raise ValueError("[fingerspelling/adapter] Non-finite model input")
    return out
