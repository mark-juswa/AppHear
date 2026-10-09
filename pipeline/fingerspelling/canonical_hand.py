"""Causal heuristic primary-hand identity using only common current/past raw-v1 evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.perception_vnext.recognition_schema import RawSequence

VERSION = "SigningHandCanonicalizer.v1"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config/fingerspelling_features_v2.json"
CONFIG: dict[str, Any] = json.loads(CONFIG_PATH.read_text())


@dataclass(frozen=True)
class CanonicalSequence:
    primary_slot: np.ndarray
    secondary_slot: np.ndarray
    states: np.ndarray
    motion_valid: np.ndarray


def overlap(roi: np.ndarray) -> float:
    if not np.isfinite(roi).all() or (roi[:, 2] <= 0).any():
        return 0.0
    low, high = roi[:, :2] - roi[:, 2:3] / 2, roi[:, :2] + roi[:, 2:3] / 2
    size = np.maximum(0, np.minimum(high[0], high[1]) - np.maximum(low[0], low[1]))
    area = size[0] * size[1]
    return float(area / (roi[0, 2] ** 2 + roi[1, 2] ** 2 - area))


def evidence_key(raw: RawSequence, i: int, s: int) -> tuple[float, ...]:
    """Resolve exact association/quality/wrist ties by evidence, never slot naming."""
    result = []
    for j in range(21):
        valid = bool(raw.hand_joint_valid[i, s, j] and raw.hand_observed[i, s])
        support = raw.hand_proposal_support[i, s, j]
        result.extend(
            [
                float(valid),
                float(raw.hand_xy[i, s, j, 0]) if valid else 0.0,
                float(raw.hand_xy[i, s, j, 1]) if valid else 0.0,
                float(np.isfinite(support)),
                float(support) if np.isfinite(support) else 0.0,
            ]
        )
    result.append(float(raw.hand_proposal_present[i, s]))
    for value in [raw.hand_presence[i, s], *raw.hand_roi_center_side[i, s]]:
        result.extend([float(np.isfinite(value)), float(value) if np.isfinite(value) else 0.0])
    return tuple(result)


def canonicalize(raw: RawSequence) -> CanonicalSequence:
    raw.validate()
    n = len(raw.frame_index)
    slots: np.ndarray = np.full(n, -1, np.int32)
    secondary: np.ndarray = np.full(n, -1, np.int32)
    states: np.ndarray = np.zeros((n, 8), np.float32)
    motion: np.ndarray = np.zeros(n, bool)
    previous: tuple[int, int] | None = None
    weights = CONFIG["quality_weights"]
    for i in range(n):
        valid = raw.hand_joint_valid[i] & raw.hand_observed[i, :, None]
        candidates = [
            s
            for s in range(2)
            if valid[s, 0] and int(valid[s].sum()) >= CONFIG["minimum_valid_joints"]
        ]
        if not candidates:
            continue
        quality = []
        for s in range(2):
            support = raw.hand_proposal_support[i, s]
            finite = support[np.isfinite(support)]
            q = np.float32(weights[0]) * np.float32(valid[s].sum() / 21)
            presence = raw.hand_presence[i, s]
            q += np.float32(weights[1]) * np.float32(
                np.clip(presence, 0, 1) if np.isfinite(presence) else 0
            )
            total = np.float32(0)
            for value in finite:
                total += np.float32(np.clip(value, 0, 1))
            q += np.float32(weights[2]) * (
                total / np.float32(len(finite)) if len(finite) else np.float32(0)
            )
            quality.append(q)
        short = np.float32(raw.source_size[i].min())
        duplicate = (
            len(candidates) == 2
            and raw.hand_proposal_present[i].all()
            and overlap(raw.hand_roi_center_side[i]) >= CONFIG["duplicate_roi_iou"]
        )
        if duplicate:
            delta = raw.hand_xy[i, 0, 0] - raw.hand_xy[i, 1, 0]
            distance = np.sqrt(delta[0] * delta[0] + delta[1] * delta[1]) / short
            duplicate = bool(distance <= CONFIG["duplicate_wrist_distance_short_side"])
        distinct = len(candidates) == 2 and not duplicate
        distances: dict[int, float] = {}
        if previous is not None:
            j, old_slot = previous
            elapsed = (raw.timestamp_ms[i] - raw.timestamp_ms[j]) / 1000
            if (
                elapsed <= CONFIG["maximum_association_gap_seconds"]
                and (raw.source_size[i] == raw.source_size[j]).all()
            ):
                for s in candidates:
                    delta = raw.hand_xy[i, s, 0] - raw.hand_xy[j, old_slot, 0]
                    d = float(np.sqrt(delta[0] * delta[0] + delta[1] * delta[1]) / short)
                    if d <= CONFIG["maximum_association_distance_short_side"]:
                        distances[s] = d

        ranks = {
            s: (
                distances.get(s, float("inf")),
                -float(quality[s]),
                float(raw.hand_xy[i, s, 0, 0]),
                float(raw.hand_xy[i, s, 0, 1]),
            )
            for s in candidates
        }
        chosen = min(candidates, key=ranks.__getitem__)
        tied = [s for s in candidates if ranks[s] == ranks[chosen]]
        if len(tied) > 1:
            keys = {s: (evidence_key(raw, i, s), s) for s in tied}
            chosen = min(tied, key=keys.__getitem__)
        continuous = chosen in distances
        ambiguous = distinct and (
            not distances
            or (
                len(distances) == 2
                and abs(distances[0] - distances[1]) < CONFIG["association_margin_short_side"]
            )
        )
        slots[i] = chosen
        if distinct:
            secondary[i] = 1 - chosen
        states[i] = [
            1,
            quality[chosen],
            continuous,
            ambiguous,
            duplicate,
            distinct,
            not continuous,
            len(candidates) / 2,
        ]
        motion[i] = continuous and previous is not None and previous[0] == i - 1
        previous = (i, chosen)
    return CanonicalSequence(slots, secondary, states, motion)
