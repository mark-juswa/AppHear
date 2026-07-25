"""Feature 06 tests — signer-split manifest build, disjointness guard, hash stability."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pipeline.splits.registry import SplitManifest, build_manifest, verify_disjoint


def _write_split(splits_dir: Path, split: str, rows: list[tuple[str, str]]) -> None:
    with (splits_dir / f"{split}.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Participant ID", "Video file", "Gloss", "ASL-LEX Code"])
        for pid, vf in rows:
            w.writerow([pid, vf, "X", "A_00_000"])


def _disjoint_dir(tmp_path: Path) -> Path:
    d = tmp_path / "splits"
    d.mkdir()
    _write_split(d, "train", [("P1", "a.mp4"), ("P1", "b.mp4"), ("P2", "c.mp4")])
    _write_split(d, "val", [("P3", "d.mp4")])
    _write_split(d, "test", [("P4", "e.mp4"), ("P5", "f.mp4")])
    return d


def test_build_manifest_counts_and_mapping(tmp_path: Path) -> None:
    m = build_manifest(_disjoint_dir(tmp_path))
    assert m.split_of("P1") == "train" and m.split_of("P3") == "val" and m.split_of("P4") == "test"
    assert m.counts["train"] == {"signers": 2, "clips": 3}
    assert m.counts["val"] == {"signers": 1, "clips": 1}
    assert m.split_of("P999") is None


def test_verify_disjoint_clean(tmp_path: Path) -> None:
    assert verify_disjoint(_disjoint_dir(tmp_path)) == {}


def test_verify_disjoint_detects_leakage(tmp_path: Path) -> None:
    d = tmp_path / "splits"
    d.mkdir()
    _write_split(d, "train", [("P1", "a.mp4")])
    _write_split(d, "val", [("P1", "b.mp4")])  # P1 leaks into val
    _write_split(d, "test", [("P2", "c.mp4")])
    overlap = verify_disjoint(d)
    assert "P1" in overlap and set(overlap["P1"]) == {"train", "val"}


def test_build_rejects_leakage(tmp_path: Path) -> None:
    d = tmp_path / "splits"
    d.mkdir()
    _write_split(d, "train", [("P1", "a.mp4")])
    _write_split(d, "val", [("P1", "b.mp4")])
    _write_split(d, "test", [("P2", "c.mp4")])
    with pytest.raises(ValueError, match="signer-disjoint"):
        build_manifest(d)


def test_hash_stable_and_sensitive(tmp_path: Path) -> None:
    d = _disjoint_dir(tmp_path)
    a = build_manifest(d)
    assert a.content_hash == build_manifest(d).content_hash  # deterministic
    # moving a signer to another split changes the hash
    d2 = tmp_path / "splits2"
    d2.mkdir()
    _write_split(d2, "train", [("P1", "a.mp4"), ("P2", "c.mp4")])
    _write_split(d2, "val", [("P3", "d.mp4")])
    _write_split(d2, "test", [("P4", "e.mp4"), ("P5", "f.mp4"), ("P6", "g.mp4")])
    assert build_manifest(d2).content_hash != a.content_hash


def test_manifest_roundtrip(tmp_path: Path) -> None:
    m = build_manifest(_disjoint_dir(tmp_path))
    path = tmp_path / "splits.json"
    m.save(path)
    loaded = SplitManifest.load(path)
    assert loaded.participant_split == m.participant_split
    assert loaded.content_hash == m.content_hash
