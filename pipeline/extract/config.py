"""Typed loader for extract.yaml + deterministic config hashing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class HandConfig:
    num_hands: int
    min_hand_detection_confidence: float
    min_hand_presence_confidence: float
    min_tracking_confidence: float


@dataclass(frozen=True)
class PoseConfig:
    num_poses: int
    min_pose_detection_confidence: float
    min_pose_presence_confidence: float
    min_tracking_confidence: float


@dataclass(frozen=True)
class ExtractConfig:
    extraction_version: str
    dataset_root: Path
    videos_subdir: str
    splits_subdir: str
    source: str
    output_root: Path
    hand_task: Path
    pose_task: Path
    hand: HandConfig
    pose: PoseConfig
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def videos_dir(self) -> Path:
        return self.dataset_root / self.videos_subdir

    @property
    def splits_dir(self) -> Path:
        return self.dataset_root / self.splits_subdir

    @property
    def model_config_hash(self) -> str:
        """Stable short hash of everything that changes the landmark output. Model variant is
        keyed by file *name* (pose_landmarker_lite vs _full), not path, so moving the repo
        doesn't change the hash."""
        from .constants import RUNNING_MODE

        payload = {
            "extraction_version": self.extraction_version,
            "running_mode": RUNNING_MODE,
            "hand_model": self.hand_task.name,
            "pose_model": self.pose_task.name,
            "hand": self.hand.__dict__,
            "pose": self.pose.__dict__,
        }
        blob = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:12]


def load_config(path: str | Path) -> ExtractConfig:
    """Load and validate extract.yaml. Paths are resolved relative to the repo root (the
    parent of the ``pipeline`` package) so the config works regardless of CWD."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)

    repo_root = Path(__file__).resolve().parents[2]

    def _resolve(p: str) -> Path:
        candidate = Path(p)
        return candidate if candidate.is_absolute() else (repo_root / candidate)

    return ExtractConfig(
        extraction_version=str(raw["extraction_version"]),
        dataset_root=Path(raw["dataset"]["root"]),
        videos_subdir=str(raw["dataset"]["videos_subdir"]),
        splits_subdir=str(raw["dataset"]["splits_subdir"]),
        source=str(raw["dataset"]["source"]),
        output_root=Path(raw["output"]["root"]),
        hand_task=_resolve(raw["models"]["hand_task"]),
        pose_task=_resolve(raw["models"]["pose_task"]),
        hand=HandConfig(**raw["hand"]),
        pose=PoseConfig(**raw["pose"]),
        raw=raw,
    )
