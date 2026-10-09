"""Versioned canonical primary-hand features, reusing frozen common v1 geometry math."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.fingerspelling import adapter as v1
from pipeline.fingerspelling.canonical_hand import (
    CONFIG,
    CONFIG_PATH,
    canonicalize,
)
from pipeline.fingerspelling.canonical_hand import (
    VERSION as HAND_VERSION,
)
from pipeline.perception_vnext.recognition_schema import RawSequence

VERSION = "FingerspellingFeatureAdapter.v2"
WIDTH = 255


def column_names() -> list[str]:
    old = v1.column_names()
    return [
        *old[:2],
        *[x.replace("slot0.", "primary.") for x in old[2:183]],
        *old[364:],
        *[
            "canonical." + x
            for x in [
                "valid",
                "quality",
                "continuous",
                "ambiguous",
                "duplicate",
                "potentially_distinct",
                "reset",
                "candidate_fraction",
            ]
        ],
        *[
            "secondary." + x
            for x in [
                "observed",
                "presence",
                "presence_valid",
                "roi_x",
                "roi_y",
                "roi_side",
                "roi_valid",
                "context_valid",
            ]
        ],
        *[f"tip{j}.{x}" for j in CONFIG["tip_indices"] for x in ["dx", "dy", "motion_valid"]],
    ]


def identity() -> dict[str, Any]:
    if (
        CONFIG["schema_version"] != VERSION
        or CONFIG["feature_width"] != WIDTH
        or CONFIG["canonicalizer_version"] != HAND_VERSION
        or CONFIG["horizontal_flip"]
        or CONFIG["target_order"] != v1.CONFIG["target_order"]
    ):
        raise ValueError("[fingerspelling/v2] Contract mismatch")
    names = column_names()
    if len(names) != WIDTH:
        raise ValueError("[fingerspelling/v2] Column mismatch")
    return {
        "schema_version": VERSION,
        "feature_width": WIDTH,
        "config_sha256": v1.sha256(CONFIG_PATH),
        "implementation_sha256": v1.sha256(Path(__file__)),
        "canonicalizer_sha256": v1.sha256(Path(__file__).with_name("canonical_hand.py")),
        "v1_geometry_identity": v1.identity(),
        "columns_sha256": hashlib.sha256("\n".join(names).encode()).hexdigest(),
    }


def derive(raw: RawSequence) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    identity()
    c = canonicalize(raw)
    remap = v1.subset(raw, np.arange(len(raw.frame_index), dtype=np.int32))
    fields = [
        "hand_xy",
        "hand_proposal_support",
        "hand_joint_valid",
        "hand_presence",
        "hand_observed",
        "hand_proposal_present",
        "hand_roi_center_side",
    ]
    for field in fields:
        a = getattr(remap, field)
        a[:] = False if a.dtype == bool else np.nan
        for i, s in enumerate(c.primary_slot):
            if s >= 0:
                a[i, 0] = getattr(raw, field)[i, s]
    dense = v1.derive(remap)
    dense[~c.motion_valid, 180:183] = 0
    out: np.ndarray = np.zeros((len(c.primary_slot), WIDTH), np.float32)
    out[:, :183], out[:, 183:224], out[:, 224:232] = dense[:, :183], dense[:, 364:], c.states
    for i, s in enumerate(c.secondary_slot):
        if s < 0:
            continue
        out[i, 232] = raw.hand_observed[i, s]
        presence = raw.hand_presence[i, s]
        if np.isfinite(presence):
            out[i, 233:235] = presence, 1
        roi = raw.hand_roi_center_side[i, s]
        if raw.hand_proposal_present[i, s] and np.isfinite(roi).all() and roi[2] > 0:
            out[i, 235:238] = roi / np.asarray(
                [*raw.source_size[i], raw.source_size[i].min()], np.float32
            )
            out[i, 238] = 1
        out[i, 239] = 1
    for i in range(1, len(c.primary_slot)):
        s, old = c.primary_slot[i], c.primary_slot[i - 1]
        if not c.motion_valid[i] or c.states[i, 3]:
            out[i, 180:183] = 0
            continue
        for k, j in enumerate(CONFIG["tip_indices"]):
            if raw.hand_joint_valid[i, s, j] and raw.hand_joint_valid[i - 1, old, j]:
                out[i, 240 + k * 3 : 242 + k * 3] = (
                    raw.hand_xy[i, s, j] - raw.hand_xy[i - 1, old, j]
                ) / np.float32(raw.source_size[i].min())
                out[i, 242 + k * 3] = 1
    if not np.isfinite(out).all():
        raise ValueError("[fingerspelling/v2] Non-finite features")
    return out, {
        "primary_slot": c.primary_slot,
        "secondary_slot": c.secondary_slot,
        "canonical_states": c.states,
        "canonical_motion_valid": c.motion_valid,
    }
