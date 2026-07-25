"""Frozen signer-level split manifest.

Builds a pinned participant->split mapping from ASL Citizen's official split CSVs, with a
content hash so the split can't silently drift. A signer must appear in exactly one split;
`verify_disjoint` is the leakage guard (context/eval-protocol.md § Split Discipline)."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

SPLITS = ("train", "val", "test")
SOURCE = "asl_citizen_official"


@dataclass
class SplitManifest:
    participant_split: dict[str, str]  # participant_id -> "train" | "val" | "test"
    counts: dict[str, dict[str, int]]  # split -> {"signers": n, "clips": n}
    content_hash: str
    source: str = SOURCE

    def split_of(self, participant_id: str) -> str | None:
        return self.participant_split.get(participant_id)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2, sort_keys=True)

    @classmethod
    def load(cls, path: Path) -> SplitManifest:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return cls(**data)


def _hash_mapping(participant_split: dict[str, str]) -> str:
    canonical = json.dumps(sorted(participant_split.items())).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:16]


def _read_participants(splits_dir: Path, split: str) -> tuple[set[str], int]:
    """(distinct participant ids, clip count) for one split CSV."""
    participants: set[str] = set()
    clips = 0
    with (splits_dir / f"{split}.csv").open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            participants.add(row["Participant ID"])
            clips += 1
    return participants, clips


def verify_disjoint(splits_dir: Path) -> dict[str, list[str]]:
    """Return {participant_id: [splits it appears in]} for any signer in >1 split. Empty = OK."""
    seen: dict[str, list[str]] = {}
    for split in SPLITS:
        participants, _ = _read_participants(splits_dir, split)
        for pid in participants:
            seen.setdefault(pid, []).append(split)
    return {pid: s for pid, s in seen.items() if len(s) > 1}


def build_manifest(splits_dir: Path) -> SplitManifest:
    """Build the frozen manifest from the official CSVs. Raises if signers are not disjoint."""
    overlap = verify_disjoint(splits_dir)
    if overlap:
        raise ValueError(f"splits are NOT signer-disjoint: {overlap}")

    participant_split: dict[str, str] = {}
    counts: dict[str, dict[str, int]] = {}
    for split in SPLITS:
        participants, clips = _read_participants(splits_dir, split)
        for pid in participants:
            participant_split[pid] = split
        counts[split] = {"signers": len(participants), "clips": clips}

    return SplitManifest(
        participant_split=participant_split,
        counts=counts,
        content_hash=_hash_mapping(participant_split),
    )
