"""Tests for the bounded C0-B0 Stage 2 training package."""

from __future__ import annotations

from pipeline.tracking.e2e_c0b_stage2_train import _condition_counts, _nested_order


def _rows() -> list[dict[str, str]]:
    rows = []
    for source in ("ASL", "LOCAL"):
        for signer in ("S1", "S2"):
            for index in range(6):
                rows.append(
                    {
                        "sample_id": f"{source}-{signer}-{index}",
                        "source_dataset": source,
                        "participant_id": signer,
                        "hand_count": str(index % 3),
                        "motion_blur": "yes" if index == 1 else "no",
                        "occlusion": "yes" if index == 2 else "no",
                        "near_face": "no",
                        "edge_clipped": "no",
                        "partial_visibility": "no",
                    }
                )
    return rows


def test_nested_order_is_deterministic_and_complete() -> None:
    rows = _rows()

    first = _nested_order(rows, seed=9)
    second = _nested_order(rows, seed=9)

    assert [row["sample_id"] for row in first] == [row["sample_id"] for row in second]
    assert {row["sample_id"] for row in first} == {row["sample_id"] for row in rows}


def test_early_nested_subset_covers_sources_signers_and_hand_counts() -> None:
    subset = _nested_order(_rows(), seed=9)[:12]

    assert {row["source_dataset"] for row in subset} == {"ASL", "LOCAL"}
    assert {row["participant_id"] for row in subset} == {"S1", "S2"}
    assert {row["hand_count"] for row in subset} == {"0", "1", "2"}


def test_condition_counts() -> None:
    counts = _condition_counts(_rows())

    assert counts["rows"] == 24
    assert counts["no_hand"] == 8
    assert counts["one_hand"] == 8
    assert counts["two_hand"] == 8
