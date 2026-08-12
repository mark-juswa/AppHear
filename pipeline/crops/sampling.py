"""Deterministic, signer-aware clip and frame sampling for E2."""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from pipeline.detect.schema import SpanSidecar

from .config import CropConfig


@dataclass(frozen=True)
class ClipSample:
    clip_id: str
    split: str
    participant_id: str
    gloss: str
    video_file: str
    onset: int
    release: int
    hand_coverage: float
    coverage_bin: str


def _coverage_bin(value: float, thresholds: tuple[float, float]) -> str:
    if value < thresholds[0]:
        return "low"
    if value < thresholds[1]:
        return "medium"
    return "high"


def _eligible(config: CropConfig, split: str) -> list[ClipSample]:
    rows: list[ClipSample] = []
    split_path = config.splits_dir / f"{split}.csv"
    with split_path.open("r", encoding="utf-8", newline="") as fh:
        for source in csv.DictReader(fh):
            clip_id = Path(source["Video file"]).stem
            span_path = config.spans_root / split / f"{clip_id}.span.json"
            landmark_path = config.landmarks_root / split / f"{clip_id}.npz"
            video_path = config.videos_dir / source["Video file"]
            if not (span_path.exists() and landmark_path.exists() and video_path.exists()):
                continue
            span = SpanSidecar.load(span_path)
            if not span.valid or span.onset < 0 or span.release < span.onset:
                continue
            rows.append(
                ClipSample(
                    clip_id=clip_id,
                    split=split,
                    participant_id=source["Participant ID"],
                    gloss=source["Gloss"],
                    video_file=source["Video file"],
                    onset=span.onset,
                    release=span.release,
                    hand_coverage=span.in_span_hand_rate,
                    coverage_bin=_coverage_bin(
                        span.in_span_hand_rate, config.sampling.coverage_bins
                    ),
                )
            )
    return rows


def _balanced_pick(rows: list[ClipSample], count: int, rng: random.Random) -> list[ClipSample]:
    groups: dict[tuple[str, str], list[ClipSample]] = defaultdict(list)
    for row in rows:
        groups[(row.coverage_bin, row.participant_id)].append(row)
    for values in groups.values():
        rng.shuffle(values)

    keys = sorted(groups)
    rng.shuffle(keys)
    selected: list[ClipSample] = []
    while keys and len(selected) < count:
        next_keys: list[tuple[str, str]] = []
        for key in keys:
            values = groups[key]
            if values and len(selected) < count:
                selected.append(values.pop())
            if values:
                next_keys.append(key)
        keys = next_keys
        rng.shuffle(keys)
    return selected


def select_clips(config: CropConfig, count: int, seed: int) -> list[ClipSample]:
    rng = random.Random(seed)
    split_items = list(config.sampling.split_fraction.items())
    allocations: dict[str, int] = {}
    assigned = 0
    for index, (split, fraction) in enumerate(split_items):
        allocation = count - assigned if index == len(split_items) - 1 else round(count * fraction)
        allocations[split] = allocation
        assigned += allocation

    selected: list[ClipSample] = []
    for split, allocation in allocations.items():
        selected.extend(_balanced_pick(_eligible(config, split), allocation, rng))
    if len(selected) != count:
        raise ValueError(f"requested {count} eligible clips, selected {len(selected)}")
    rng.shuffle(selected)
    return selected


def select_frame_indices(
    onset: int,
    release: int,
    cadence: int,
    frames_per_clip: int,
) -> list[int]:
    first = onset + ((-onset) % cadence)
    candidates = np.arange(first, release + 1, cadence, dtype=np.int64)
    if candidates.size <= frames_per_clip:
        return [int(v) for v in candidates]
    positions = np.linspace(0, candidates.size - 1, frames_per_clip)
    return sorted({int(candidates[int(round(position))]) for position in positions})
