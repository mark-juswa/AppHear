from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "artifacts/recognition_upgrade/perception_backend_replacement"
    / "negative_gold_v1_topup_01"
)


def _csv_rows(name: str) -> list[dict[str, str]]:
    with (PACKAGE / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _hamming_hex(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def test_seed_is_frozen_incomplete_and_independent() -> None:
    result = json.loads(
        (PACKAGE / "NEGATIVE_GOLD_V1_SEED_MANIFEST.json").read_text(encoding="utf-8")
    )
    rows = _csv_rows("NEGATIVE_GOLD_V1_SEED_MANIFEST.csv")

    assert result["status"] == "NEGATIVE_GOLD_V1_SEED_NOT_COMPLETE"
    assert result["rows"] == len(rows) == 76
    assert result["remaining"] == 124
    assert result["source_composition"] == {
        "CORRECTED_GOLD": 33,
        "N0_READJUDICATED": 43,
    }
    assert all(row["semantic_class"] == "ZERO_HAND" for row in rows)
    assert len({row["image_sha256"] for row in rows}) == 76
    assert all(Path(row["image_path"]).is_file() for row in rows)
    assert all(
        _hamming_hex(left["dhash64"], right["dhash64"]) > 4
        for index, left in enumerate(rows)
        for right in rows[index + 1 :]
    )
    assert all(
        result[key]
        for key in (
            "no_exact_duplicates",
            "no_dhash_distance_le_4",
            "no_positive_p0_overlap",
            "no_protected_test_rows",
            "all_images_available",
        )
    )


def test_review_queue_is_blinded_randomized_and_qc_mapped() -> None:
    rows = _csv_rows("NEGATIVE_DIVERSITY_TOPUP_REVIEW_QUEUE.csv")
    primary = [row for row in rows if row["is_qc_repeat"] == "false"]
    repeats = [row for row in rows if row["is_qc_repeat"] == "true"]
    primary_ids = {row["review_id"] for row in primary}

    assert len(rows) == 352
    assert len(primary) == 320
    assert len(repeats) == 32
    assert len({row["source_image_sha256"] for row in primary}) == 320
    assert all(row["canonical_review_id"] in primary_ids for row in repeats)
    assert all(row["canonical_review_id"] == row["review_id"] for row in primary)

    forbidden_fragments = ("semantic", "label", "prediction", "confidence", "detected")
    assert not any(
        fragment in column.lower() for column in rows[0] for fragment in forbidden_fragments
    )


def test_frozen_dhash_sanity_examples_cover_requested_buckets() -> None:
    rows = _csv_rows("dhash_threshold_sanity_index.csv")
    observed = {row["bucket"]: int(row["dhash_distance"]) for row in rows}

    assert observed.keys() == {"d0", "d1_2", "d3_4", "d5_6"}
    assert observed["d0"] == 0
    assert 1 <= observed["d1_2"] <= 2
    assert 3 <= observed["d3_4"] <= 4
    assert 5 <= observed["d5_6"] <= 6
    assert all(Path(row["panel_path"]).is_file() for row in rows)
