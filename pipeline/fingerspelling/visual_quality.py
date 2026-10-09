"""Current-frame visual-only reliability and obvious duplicate suppression."""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.visual_crop import config as crop_config
from pipeline.fingerspelling.visual_crop import crop_geometry
from pipeline.perception_vnext.recognition_schema import RawSequence

CONFIG = REPO / "model/config/fingerspelling_residual_visual_01.json"


def config() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(CONFIG.read_text())
    if (
        value["schema_version"] != "apphear.fingerspelling.residual_visual.v1"
        or value["geometry_width"] != 405
        or value["embedding_width"] != 576
        or value["packed_width"] != 1559
        or value["blank_penalty"] != 0.5
        or value["test_access"] != "SEALED"
    ):
        raise ValueError("[residual/config] Contract mismatch")
    return value


def identity() -> dict[str, Any]:
    return {
        "schema_version": "apphear.fingerspelling.visual_quality.v1",
        "config_sha256": sha256(CONFIG),
        "implementation_sha256": sha256(
            REPO / "pipeline/fingerspelling/visual_quality.py"
        ),
    }


def quality(raw: RawSequence) -> dict[str, np.ndarray]:
    raw.validate()
    cfg, crop = config(), crop_config()
    n = len(raw.frame_index)
    scores = np.zeros((n, 2), np.float32)
    rois = np.zeros((n, 2, 3), np.float32)
    reasons = np.zeros((n, 2), np.uint16)
    intersection = np.zeros((n, 2), np.float32)
    containment = np.zeros((n, 2), np.float32)
    for i in range(n):
        for s in range(2):
            roi, valid, border = crop_geometry(
                raw.hand_roi_center_side[i, s],
                bool(raw.hand_proposal_present[i, s]),
                int(raw.source_size[i, 0]),
                int(raw.source_size[i, 1]),
                crop,
            )
            intersection[i, s] = border
            joints = raw.hand_joint_valid[i, s].astype(bool)
            support = int(
                np.sum(
                    raw.hand_proposal_support[i, s] >= cfg["proposal_support_threshold"]
                )
            )
            pts = raw.hand_xy[i, s][joints]
            inside = (
                float(np.mean(np.all(np.abs(pts - roi[:2]) <= roi[2] / 2, axis=1)))
                if valid and len(pts)
                else 0.0
            )
            containment[i, s] = inside
            presence = float(raw.hand_presence[i, s])
            failures = [
                not valid,
                not bool(raw.hand_observed[i, s]),
                not np.isfinite(presence) or presence < cfg["minimum_presence"],
                joints.sum() < cfg["minimum_valid_joints"],
                support < cfg["minimum_supported_joints"],
                border < cfg["minimum_source_intersection"],
                inside < cfg["minimum_joint_containment"],
            ]
            reasons[i, s] = sum((1 << k) for k, bad in enumerate(failures) if bad)
            if not any(failures):
                scores[i, s] = np.float32(
                    min(1.0, presence)
                    * joints.mean()
                    * (support / 21)
                    * border
                    * inside
                )
                rois[i, s] = roi
    before = scores.copy()
    suppressed = np.zeros((n, 2), bool)
    duplicate = np.zeros(n, bool)
    for i in range(n):
        if np.all(scores[i] > 0):
            a, b = rois[i]
            low = np.maximum(a[:2] - a[2] / 2, b[:2] - b[2] / 2)
            high = np.minimum(a[:2] + a[2] / 2, b[:2] + b[2] / 2)
            overlap = float(np.prod(np.maximum(0.0, high - low)))
            iou = overlap / float(a[2] ** 2 + b[2] ** 2 - overlap)
            common = raw.hand_joint_valid[i, 0] & raw.hand_joint_valid[i, 1]
            side = float(min(a[2], b[2]))
            distance = (
                float(
                    np.median(
                        np.linalg.norm(
                            raw.hand_xy[i, 0][common] - raw.hand_xy[i, 1][common],
                            axis=1,
                        )
                    )
                    / side
                )
                if common.any()
                else float("inf")
            )
            if (
                iou >= cfg["duplicate_min_iou"]
                and np.linalg.norm(a[:2] - b[:2]) / side
                <= cfg["duplicate_max_center_distance"]
                and distance <= cfg["duplicate_max_landmark_distance"]
                and common.sum() >= cfg["duplicate_min_common_joints"]
                and max(a[2], b[2]) / side <= cfg["duplicate_max_side_ratio"]
            ):
                weaker = 1 if scores[i, 0] >= scores[i, 1] else 0
                duplicate[i] = suppressed[i, weaker] = True
                scores[i, weaker] = 0
    return {
        "quality": scores,
        "quality_before_dedup": before,
        "rejection_bits": reasons,
        "duplicate": duplicate,
        "suppressed": suppressed,
        "expanded_rois": rois,
        "source_intersection": intersection,
        "joint_containment": containment,
    }
