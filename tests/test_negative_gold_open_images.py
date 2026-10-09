from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from pipeline.tracking.negative_gold_open_images import (
    SEMANTIC_CLASSES,
    _interleave,
    _review_order,
    _rotate_for_display,
    _scene_bucket,
    load_config,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "model/config/recognition_upgrade/negative_gold_open_images_v7.json"
PACKAGE = (
    ROOT
    / "artifacts/recognition_upgrade/perception_backend_replacement"
    / "negative_gold_open_images_v7_01"
)


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_config_freezes_bounded_candidate_and_qc_counts() -> None:
    config = load_config(CONFIG)

    assert config["canonical_candidate_count"] == 220
    assert config["person_free_target"] == 143
    assert config["people_present_target"] == 77
    assert config["qc_repeat_count"] == 20
    assert config["dhash_hamming_max"] == 4
    assert tuple(config["semantic_classes"]) == SEMANTIC_CLASSES


def test_scene_bucket_uses_metadata_names_only() -> None:
    assert _scene_bucket({"Tree", "Mountain"}) == "NATURE"
    assert _scene_bucket({"Kitchen & dining room table", "Chair"}) == "INDOOR"
    assert _scene_bucket({"Bus", "Vehicle"}) == "TRANSPORT"
    assert _scene_bucket({"Unmapped label"}) == "MIXED"


def test_interleave_preserves_category_plan() -> None:
    free = [
        {"ImageID": f"f{index}", "discovery_category": "PERSON_FREE_DISCOVERY"}
        for index in range(20)
    ]
    present = [
        {"ImageID": f"p{index}", "discovery_category": "PEOPLE_PRESENT_DISCOVERY"}
        for index in range(20)
    ]

    rows = _interleave(free, present, 20, 13, 7)

    assert sum(row["discovery_category"] == "PERSON_FREE_DISCOVERY" for row in rows) == 13
    assert sum(row["discovery_category"] == "PEOPLE_PRESENT_DISCOVERY" for row in rows) == 7


def test_review_order_has_concealed_exact_repeat_mapping_distance() -> None:
    selected = [{"ImageID": f"{index:016x}"} for index in range(220)]

    order = _review_order(selected, repeat_count=20, seed=17)
    positions: dict[str, list[int]] = {}
    repeats = 0
    for index, (row, is_repeat) in enumerate(order):
        positions.setdefault(row["ImageID"], []).append(index)
        repeats += int(is_repeat)

    assert len(order) == 240
    assert repeats == 20
    assert sum(len(values) == 2 for values in positions.values()) == 20
    assert all(
        len(values) == 1 or abs(values[0] - values[1]) >= 20 for values in positions.values()
    )


def test_display_rotation_corrects_dimensions_without_writing() -> None:
    image = np.zeros((2, 3, 3), dtype=np.uint8)

    assert _rotate_for_display(image, "").shape == (2, 3, 3)
    assert _rotate_for_display(image, "0.0").shape == (2, 3, 3)
    assert _rotate_for_display(image, "90.0").shape == (3, 2, 3)
    assert _rotate_for_display(image, "270.0").shape == (3, 2, 3)


def test_frozen_package_has_complete_licensed_provenance() -> None:
    summary = json.loads((PACKAGE / "prepare_summary.json").read_text(encoding="utf-8"))
    manifest = _csv_rows(PACKAGE / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.csv")

    assert summary["status"] == "OPEN_IMAGES_EXTERNAL_CANDIDATE_PACKAGE_FROZEN_UNREVIEWED"
    assert summary["canonical_candidates"] == len(manifest) == 220
    assert summary["hidden_repeats"] == 20
    assert summary["discovery_category_counts"] == {
        "PEOPLE_PRESENT_DISCOVERY": 77,
        "PERSON_FREE_DISCOVERY": 143,
    }
    assert len({row["ImageID"] for row in manifest}) == 220
    assert len({row["source_image_sha256"] for row in manifest}) == 220
    assert all(row["License"] == "https://creativecommons.org/licenses/by/2.0/" for row in manifest)
    assert all(
        row[field].strip()
        for row in manifest
        for field in ("OriginalURL", "OriginalLandingURL", "Author", "download_timestamp_utc")
    )
    assert all(
        Path(row["source_image_path"]).is_file()
        and _sha256(Path(row["source_image_path"])) == row["source_image_sha256"]
        for row in manifest
    )


def test_frozen_review_queue_is_neutral_and_exact_repeat_bytes_match() -> None:
    queue = _csv_rows(PACKAGE / "review_package/review_queue.csv")
    mapping = _csv_rows(PACKAGE / "review_package/internal_repeat_map.csv")
    queue_by_id = {row["review_id"]: row for row in queue}
    map_by_id = {row["review_id"]: row for row in mapping}
    repeats = [row for row in mapping if row["is_qc_repeat"] == "true"]

    assert len(queue) == len(mapping) == 240
    assert len(repeats) == 20
    assert set(queue[0]) == {
        "review_id",
        "image_path",
        "review_status",
        "semantic_class",
        "notes",
    }
    assert all(row["review_status"] in {"unreviewed", "accepted"} for row in queue)
    assert all(
        (row["review_status"] == "unreviewed" and not row["semantic_class"])
        or (row["review_status"] == "accepted" and row["semantic_class"] in SEMANTIC_CLASSES)
        for row in queue
    )
    assert all(Path(row["image_path"]).name == f"{row['review_id']}.jpg" for row in queue)
    assert all(
        _sha256(Path(queue_by_id[row["review_id"]]["image_path"]))
        == _sha256(Path(queue_by_id[row["canonical_review_id"]]["image_path"]))
        == map_by_id[row["canonical_review_id"]]["source_image_sha256"]
        for row in repeats
    )


def test_frozen_candidates_are_not_near_seed_or_each_other() -> None:
    manifest = _csv_rows(PACKAGE / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.csv")
    seed = _csv_rows(
        ROOT
        / "artifacts/recognition_upgrade/perception_backend_replacement"
        / "negative_gold_v1_topup_01/NEGATIVE_GOLD_V1_SEED_MANIFEST.csv"
    )
    fingerprints = [int(row["dhash64"], 16) for row in seed]
    for row in manifest:
        current = int(row["dhash64"], 16)
        assert all((current ^ prior).bit_count() > 4 for prior in fingerprints)
        fingerprints.append(current)


def test_completed_review_is_formally_blocked_by_hard_repeat_qc() -> None:
    result = json.loads((PACKAGE / "finalize_result.json").read_text(encoding="utf-8"))

    assert result["decision"] == "OPEN_IMAGES_REVIEW_COMPLETE_QC_FAILED_REPAIR_REQUIRED"
    assert result["canonical_counts"] == {
        "HAND_VISIBLE": 38,
        "UNCERTAIN": 1,
        "ZERO_HAND": 181,
    }
    assert result["zero_hand_excluding_repeat_disagreements"] == 180
    assert result["trusted_negative_gold_after"] == 76
    assert result["remaining_trusted_deficit"] == 124
    assert result["benchmark_frozen"] is False
    assert result["qc"] == {
        "repeat_pairs": 20,
        "exact_agreements": 18,
        "exact_agreement_fraction": 0.9,
        "three_class_disagreements": 2,
        "zero_vs_nonzero_disagreements": 2,
        "critical_zero_hand_vs_hand_visible_disagreements": 1,
        "all_repeat_source_bytes_identical": True,
        "hard_qc_passed": False,
    }
