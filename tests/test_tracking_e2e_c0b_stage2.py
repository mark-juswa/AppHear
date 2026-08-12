"""Tests for the C0-B0 Stage 2 research manifest."""

from __future__ import annotations

from pipeline.tracking.e2e_c0b_stage2 import _assign_splits, _stats, _verify


def _rows() -> list[dict[str, object]]:
    rows = []
    for source, signers in (("ASL", ("A1", "A2", "A3")), ("LOCAL", ("L1", "L2", "L3"))):
        for signer in signers:
            for index in range(5):
                rows.append(
                    {
                        "sample_id": f"{source}-{signer}-{index}",
                        "source_dataset": source,
                        "participant_id": signer,
                        "raw_video_path": f"/{source}/{signer}/{index}.mp4",
                        "raw_video_sha256": f"{source}-{signer}-{index}",
                        "hand_count": 0 if index == 0 else 2 if index == 1 else 1,
                        "motion_blur": "yes" if index == 2 else "no",
                        "occlusion": "yes" if index == 3 else "no",
                        "near_face": "yes" if index == 4 else "no",
                        "edge_clipped": "no",
                        "partial_visibility": "no",
                        "dataset_split": "",
                    }
                )
    return rows


def test_assign_splits_is_source_specific_and_signer_disjoint() -> None:
    rows = _rows()
    chosen = _assign_splits(rows, target=0.25, seed=7)

    assert set(chosen) == {"ASL", "LOCAL"}
    assert _verify(rows, set(), set()) == []
    for source in ("ASL", "LOCAL"):
        train = {
            row["participant_id"]
            for row in rows
            if row["source_dataset"] == source and row["dataset_split"] == "train"
        }
        development = {
            row["participant_id"]
            for row in rows
            if row["source_dataset"] == source and row["dataset_split"] == "development"
        }
        assert train.isdisjoint(development)


def test_stats_counts_negative_and_condition_rows() -> None:
    stats = _stats(_rows())

    assert stats["rows"] == 30
    assert stats["no_hand"] == 6
    assert stats["two_hand"] == 6
    assert stats["motion_blur"] == 6


def test_verify_rejects_protected_hash() -> None:
    rows = _rows()
    _assign_splits(rows, target=0.25, seed=7)

    errors = _verify(rows, set(), {str(rows[0]["raw_video_sha256"]).upper()})

    assert "protected hash overlap" in errors
