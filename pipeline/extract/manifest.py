"""Resumable extraction manifest — one CSV row per clip, so a run can skip already-done work
and produce a dataset-health report. Never silently drop a clip: failures are recorded with
status='failed' and a reason."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Literal

MANIFEST_FIELDS = (
    "clip_id",
    "split",
    "participant_id",
    "gloss",
    "asl_lex_code",
    "video_file",
    "status",  # ok | failed
    "reason",
    "n_frames",
    "native_fps",
    "hand_hit_rate",
    "two_hand_hit_rate",
    "pose_hit_rate",
    "npz_path",
    "sidecar_path",
    "model_config_hash",
)

Status = Literal["ok", "failed"]


def clip_id(video_file: str) -> str:
    """Stable id from the video filename (unique within ASL Citizen)."""
    return Path(video_file).stem


def load_done(manifest_path: Path) -> set[str]:
    """clip_ids already successfully extracted (for resumability)."""
    if not manifest_path.exists():
        return set()
    done: set[str] = set()
    with manifest_path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("status") == "ok":
                done.add(row["clip_id"])
    return done


class ManifestWriter:
    """Append-only manifest writer. Writes the header once if the file is new."""

    def __init__(self, manifest_path: Path) -> None:
        self._path = manifest_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self._path.exists()
        self._fh = self._path.open("a", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(self._fh, fieldnames=MANIFEST_FIELDS)
        if write_header:
            self._writer.writeheader()
            self._fh.flush()

    def append(self, row: dict[str, object]) -> None:
        self._writer.writerow({k: row.get(k, "") for k in MANIFEST_FIELDS})
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> ManifestWriter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
