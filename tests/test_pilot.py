"""Pilot selection tests — gloss-restricted, common-across-splits, capped, deterministic."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pipeline.pilot import select_pilot


def _write(splits_dir: Path, split: str, rows: list[tuple[str, str, str]]) -> None:
    with (splits_dir / f"{split}.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Participant ID", "Video file", "Gloss", "ASL-LEX Code"])
        for pid, vf, gloss in rows:
            w.writerow([pid, vf, gloss, "A_00_000"])


def _dir(tmp_path: Path) -> Path:
    d = tmp_path / "splits"
    d.mkdir()
    # APPLE + BOOK common to all splits; CAR only in train (must be excluded)
    _write(
        d,
        "train",
        [("P1", f"t{i}.mp4", g) for i, g in enumerate(["APPLE", "APPLE", "BOOK", "BOOK", "CAR"])],
    )
    _write(d, "val", [("P2", "v0.mp4", "APPLE"), ("P2", "v1.mp4", "BOOK")])
    _write(d, "test", [("P3", "te0.mp4", "APPLE"), ("P3", "te1.mp4", "BOOK")])
    return d


def test_select_only_common_glosses(tmp_path: Path) -> None:
    chosen, allow = select_pilot(_dir(tmp_path), glosses_k=10, max_per_split=100, seed=0)
    assert set(chosen) == {"APPLE", "BOOK"}  # CAR excluded (train-only)
    assert len(allow["train"]) == 4  # 2 APPLE + 2 BOOK, CAR dropped
    assert allow["val"] == {"v0.mp4", "v1.mp4"}


def test_glosses_k_limits_classes(tmp_path: Path) -> None:
    chosen, _ = select_pilot(_dir(tmp_path), glosses_k=1, max_per_split=100, seed=0)
    assert len(chosen) == 1 and chosen[0] in {"APPLE", "BOOK"}  # most frequent in train


def test_max_per_split_caps_and_deterministic(tmp_path: Path) -> None:
    d = _dir(tmp_path)
    a1 = select_pilot(d, glosses_k=10, max_per_split=2, seed=0)[1]
    a2 = select_pilot(d, glosses_k=10, max_per_split=2, seed=0)[1]
    assert len(a1["train"]) == 2 and a1 == a2  # capped + deterministic


def test_raises_without_common_glosses(tmp_path: Path) -> None:
    d = tmp_path / "splits"
    d.mkdir()
    _write(d, "train", [("P1", "a.mp4", "APPLE")])
    _write(d, "val", [("P2", "b.mp4", "BOOK")])
    _write(d, "test", [("P3", "c.mp4", "CAR")])
    with pytest.raises(ValueError, match="common"):
        select_pilot(d, glosses_k=5, max_per_split=10, seed=0)
