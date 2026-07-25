"""Typed loader for features.yaml (thin — most params come from the sibling normalize/quality
configs it references)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class FeaturesConfig:
    schema_version: str
    accepted_only: bool
    normalize_config: Path
    quality_config: Path
    output_root: Path
    streaming_t_max: int
    streaming_output_root: Path


def load_config(path: str | Path) -> FeaturesConfig:
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)
    repo_root = Path(__file__).resolve().parents[2]

    def _resolve(p: str) -> Path:
        c = Path(p)
        return c if c.is_absolute() else (repo_root / c)

    streaming = raw.get("streaming", {})
    return FeaturesConfig(
        schema_version=str(raw["schema_version"]),
        accepted_only=bool(raw["accepted_only"]),
        normalize_config=_resolve(str(raw["normalize_config"])),
        quality_config=_resolve(str(raw["quality_config"])),
        output_root=Path(raw["output_root"]),
        streaming_t_max=int(streaming.get("t_max", 96)),
        streaming_output_root=Path(
            streaming.get("output_root", str(raw["output_root"]) + "_streaming")
        ),
    )
