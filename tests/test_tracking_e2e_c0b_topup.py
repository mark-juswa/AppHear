"""Tests for the bounded C0-B0 hard-condition top-up."""

from __future__ import annotations

import csv
from pathlib import Path

from pipeline.tracking.e2e_c0b_topup import (
    _audit_negative_manifest,
    _balanced_pool,
    _candidate_strata,
    _select_topup,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _row(index: int, **changes: str) -> dict[str, str]:
    row = {
        "candidate_id": f"candidate-{index}",
        "source_dataset": "ASL_CITIZEN" if index % 2 else "LOCAL_SUPPLEMENTARY",
        "participant_id": f"P{index % 5}",
        "proposal_count": "1",
        "blur_score": str(10 + index),
        "max_box_area": str(0.01 + index / 1000),
        "min_edge_margin": "0.2",
        "near_face_proxy": "false",
        "possible_missed_second_hand": "false",
    }
    row.update(changes)
    return row


def test_negative_manifest_rejects_protected_development_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "negative.csv"
    _write_csv(
        manifest,
        [
            {
                "role": "development_negative",
                "negative_subtype": "N0_NO_HAND",
                "raw_video_path": str(tmp_path / "protected.mp4"),
                "raw_video_sha256": "A" * 64,
            },
            {
                "role": "test_negative_fresh_provisional",
                "negative_subtype": "P1_IDLE_HANDS",
                "raw_video_path": str(tmp_path / "fresh.mp4"),
                "raw_video_sha256": "B" * 64,
            },
        ],
    )

    result = _audit_negative_manifest(
        manifest, {str(tmp_path / "protected.mp4").casefold()}, {"A" * 64}
    )

    assert result["development_rows"] == 1
    assert result["independent_rows"] == 0
    assert result["excluded_overlap_rows"] == 1


def test_candidate_strata_are_explicit_proxies() -> None:
    row = _row(
        1,
        proposal_count="1",
        blur_score="4",
        max_box_area="0.01",
        min_edge_margin="0.01",
        near_face_proxy="true",
        possible_missed_second_hand="true",
    )

    assert _candidate_strata(row, blur_cutoff=5.0, small_cutoff=0.02) == [
        "blur_or_zero_detection",
        "possible_missed_second_hand",
        "edge_or_partial_proxy",
        "near_face_proxy",
        "small_hand_proxy",
    ]


def test_balanced_pool_alternates_sources_before_signers() -> None:
    rows = []
    for index in range(20):
        rows.append(_row(index))

    selected = _balanced_pool(rows, count=10, seed=7)

    counts = {source: 0 for source in ("ASL_CITIZEN", "LOCAL_SUPPLEMENTARY")}
    for row in selected:
        counts[row["source_dataset"]] += 1
    assert counts == {"ASL_CITIZEN": 5, "LOCAL_SUPPLEMENTARY": 5}


def test_select_topup_returns_unique_bounded_rows() -> None:
    rows = []
    for index in range(80):
        changes = {}
        if index % 5 == 0:
            changes["proposal_count"] = "0"
        if index % 5 == 1:
            changes["possible_missed_second_hand"] = "true"
        if index % 5 == 2:
            changes["min_edge_margin"] = "0.01"
        if index % 5 == 3:
            changes["near_face_proxy"] = "true"
        rows.append(_row(index, **changes))

    selected, diagnostics = _select_topup(rows, count=40, seed=7)

    assert len(selected) == 40
    assert len({row["candidate_id"] for _, row in selected}) == 40
    assert sum(diagnostics["selected_by_stratum"].values()) == 40
