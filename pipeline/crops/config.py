"""Typed configuration for the E2 RGB hand-crop quality experiment."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SamplingConfig:
    split_fraction: dict[str, float]
    engineering_clips: int
    audit_clips: int
    smoke_clips: int
    smoke_candidate_pool: int
    frames_per_clip: int
    smoke_frames_per_clip: int
    coverage_bins: tuple[float, float]
    cadences: tuple[int, ...]
    audit_max_items: int


@dataclass(frozen=True)
class RoiConfig:
    crop_sizes: tuple[int, ...]
    expansion_factors: tuple[float, ...]
    min_valid_landmarks: int
    min_side_fraction: float
    max_side_fraction: float
    max_hold_ms: int
    pad_value_rgb: tuple[int, int, int]


@dataclass(frozen=True)
class AuditConfig:
    usable_gate: float
    jpeg_quality: int
    panel_full_frame_width: int


@dataclass(frozen=True)
class CropConfig:
    experiment_version: str
    seed: int
    dataset_root: Path
    videos_subdir: str
    splits_subdir: str
    landmarks_root: Path
    spans_root: Path
    output_root: Path
    sampling: SamplingConfig
    roi: RoiConfig
    audit: AuditConfig
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def videos_dir(self) -> Path:
        return self.dataset_root / self.videos_subdir

    @property
    def splits_dir(self) -> Path:
        return self.dataset_root / self.splits_subdir

    @property
    def config_hash(self) -> str:
        payload = json.dumps(self.raw, sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:12]


def load_config(path: str | Path) -> CropConfig:
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)

    sampling = raw["sampling"]
    roi = raw["roi"]
    audit = raw["audit"]
    coverage_bins = tuple(float(v) for v in sampling["coverage_bins"])
    pad_value_rgb = tuple(int(v) for v in roi["pad_value_rgb"])
    if len(coverage_bins) != 2:
        raise ValueError("sampling.coverage_bins must contain exactly two thresholds")
    if len(pad_value_rgb) != 3:
        raise ValueError("roi.pad_value_rgb must contain exactly three RGB values")
    return CropConfig(
        experiment_version=str(raw["experiment_version"]),
        seed=int(raw["seed"]),
        dataset_root=Path(raw["dataset"]["root"]),
        videos_subdir=str(raw["dataset"]["videos_subdir"]),
        splits_subdir=str(raw["dataset"]["splits_subdir"]),
        landmarks_root=Path(raw["dataset"]["landmarks_root"]),
        spans_root=Path(raw["dataset"]["spans_root"]),
        output_root=Path(raw["output"]["root"]),
        sampling=SamplingConfig(
            split_fraction={str(k): float(v) for k, v in sampling["split_fraction"].items()},
            engineering_clips=int(sampling["engineering_clips"]),
            audit_clips=int(sampling["audit_clips"]),
            smoke_clips=int(sampling["smoke_clips"]),
            smoke_candidate_pool=int(sampling["smoke_candidate_pool"]),
            frames_per_clip=int(sampling["frames_per_clip"]),
            smoke_frames_per_clip=int(sampling["smoke_frames_per_clip"]),
            coverage_bins=(coverage_bins[0], coverage_bins[1]),
            cadences=tuple(int(v) for v in sampling["cadences"]),
            audit_max_items=int(sampling["audit_max_items"]),
        ),
        roi=RoiConfig(
            crop_sizes=tuple(int(v) for v in roi["crop_sizes"]),
            expansion_factors=tuple(float(v) for v in roi["expansion_factors"]),
            min_valid_landmarks=int(roi["min_valid_landmarks"]),
            min_side_fraction=float(roi["min_side_fraction"]),
            max_side_fraction=float(roi["max_side_fraction"]),
            max_hold_ms=int(roi["max_hold_ms"]),
            pad_value_rgb=(pad_value_rgb[0], pad_value_rgb[1], pad_value_rgb[2]),
        ),
        audit=AuditConfig(
            usable_gate=float(audit["usable_gate"]),
            jpeg_quality=int(audit["jpeg_quality"]),
            panel_full_frame_width=int(audit["panel_full_frame_width"]),
        ),
        raw=raw,
    )
