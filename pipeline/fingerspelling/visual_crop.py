"""Pure current-frame ROI crop; no detector, handedness or temporal carry."""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.perception_vnext.offline_candidate01 import _sample_rgb

CONFIG_PATH = REPO / "pipeline/config/fingerspelling_visual_v1.json"


def config() -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads(CONFIG_PATH.read_text())
    if (
        cfg["schema_version"] != "FingerspellingVisualEvidence.v1"
        or cfg["geometry_width"] != 405
        or cfg["embedding_width"] != 576
        or cfg["reflection_policy"] != "USE_RELEASED_PIXELS_AS_IS"
    ):
        raise ValueError("[visual/config] Contract mismatch")
    return cfg


def crop_geometry(
    roi: np.ndarray, proposal_present: bool, width: int, height: int, cfg: dict[str, Any]
) -> tuple[np.ndarray, bool, float]:
    value = np.asarray(roi, np.float32)
    if value.shape != (3,):
        raise ValueError("[visual/crop] ROI must have center-x/center-y/side")
    if (
        not proposal_present
        or not np.isfinite(value).all()
        or value[2] < cfg["minimum_roi_side_pixels"]
        or width <= 0
        or height <= 0
    ):
        return np.zeros(3, np.float32), False, 0.0
    expanded = value.copy()
    expanded[2] *= np.float32(cfg["roi_expansion"])
    half = expanded[2] * np.float32(0.5)
    left, top = expanded[:2] - half
    right, bottom = expanded[:2] + half
    area = max(0.0, min(float(right), width) - max(float(left), 0.0)) * max(
        0.0, min(float(bottom), height) - max(float(top), 0.0)
    )
    fraction = area / float(expanded[2] ** 2)
    valid = fraction >= cfg["minimum_source_intersection_fraction"]
    return expanded if valid else np.zeros(3, np.float32), valid, fraction


def hand_crop(
    image_rgb: np.ndarray,
    roi: np.ndarray,
    proposal_present: bool,
    cfg: dict[str, Any] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    cfg = config() if cfg is None else cfg
    if image_rgb.dtype != np.uint8 or image_rgb.ndim != 3 or image_rgb.shape[-1] != 3:
        raise ValueError("[visual/crop] Upright uint8 RGB required")
    height, width = image_rgb.shape[:2]
    expanded, valid, fraction = crop_geometry(roi, proposal_present, width, height, cfg)
    size = cfg["crop_size"]
    if not valid:
        return np.zeros((size, size, 3), np.float32), {
            "valid": False,
            "roi": expanded.tolist(),
            "source_intersection_fraction": fraction,
        }
    dx, dy = np.meshgrid(np.arange(size, dtype=np.float32), np.arange(size, dtype=np.float32))
    x = (
        np.float32(expanded[0] - expanded[2] * np.float32(0.5))
        + dx / np.float32(size - 1) * expanded[2]
    )
    y = (
        np.float32(expanded[1] - expanded[2] * np.float32(0.5))
        + dy / np.float32(size - 1) * expanded[2]
    )
    normalized = _sample_rgb(image_rgb, x, y) / np.float32(127.5) - np.float32(1.0)
    return np.ascontiguousarray(normalized, np.float32), {
        "valid": True,
        "roi": expanded.tolist(),
        "source_intersection_fraction": fraction,
    }


def crop_identity() -> dict[str, Any]:
    return {
        "schema_version": "HandCropExtractor.v1",
        "config_sha256": sha256(CONFIG_PATH),
        "implementation_sha256": sha256(REPO / "pipeline/fingerspelling/visual_crop.py"),
        "sampler_sha256": sha256(REPO / "pipeline/perception_vnext/offline_candidate01.py"),
    }
