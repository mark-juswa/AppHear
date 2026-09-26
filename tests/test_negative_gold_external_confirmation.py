from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from pipeline.tracking.negative_gold_external_confirmation import load_config
from pipeline.tracking.negative_gold_open_images import SEMANTIC_CLASSES

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "model/config/recognition_upgrade/negative_gold_external_confirmation.json"
PACKAGE = (
    ROOT
    / "artifacts/recognition_upgrade/perception_backend_replacement"
    / "negative_gold_external_confirmation_01"
)
FIRST_PASS = (
    ROOT
    / "artifacts/recognition_upgrade/perception_backend_replacement"
    / "negative_gold_open_images_v7_01"
)
SEED = (
    ROOT
    / "artifacts/recognition_upgrade/perception_backend_replacement"
    / "negative_gold_v1_topup_01/NEGATIVE_GOLD_V1_SEED_MANIFEST.csv"
)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_confirmation_config_freezes_requested_protocol() -> None:
    config = load_config(CONFIG)

    assert config["canonical_candidate_count"] == 160
    assert config["qc_repeat_count"] == 20
    assert config["dhash_hamming_max"] == 4
    assert config["minimum_repeat_exact_agreement"] == 0.92
    assert tuple(config["semantic_classes"]) == SEMANTIC_CLASSES


def test_selection_uses_only_non_discordant_first_pass_zeros() -> None:
    selection = _rows(PACKAGE / "internal_confirmation_selection.csv")
    first_labels = {
        row["review_id"]: row for row in _rows(FIRST_PASS / "canonical_human_labels_220.csv")
    }
    discordant = {
        row["canonical_review_id"]
        for row in _rows(FIRST_PASS / "hidden_repeat_qc.csv")
        if row["zero_vs_nonzero_disagreement"].lower() == "true"
    }

    assert len(selection) == 160
    assert len({row["open_images_id"] for row in selection}) == 160
    assert all(row["first_pass_semantic_class"] == "ZERO_HAND" for row in selection)
    assert all(row["first_pass_review_id"] not in discordant for row in selection)
    assert all(
        first_labels[row["first_pass_review_id"]]["semantic_class"] == "ZERO_HAND"
        for row in selection
    )


def test_package_is_diverse_and_fully_licensed() -> None:
    summary = json.loads((PACKAGE / "prepare_summary.json").read_text(encoding="utf-8"))
    manifest = _rows(PACKAGE / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.csv")

    assert summary["eligible_non_discordant_provisional_zero_hand"] == 180
    assert summary["canonical_confirmation_candidates"] == len(manifest) == 160
    assert summary["hidden_repeats"] == 20
    assert summary["discovery_category_counts"] == {
        "PEOPLE_PRESENT_DISCOVERY": 38,
        "PERSON_FREE_DISCOVERY": 122,
    }
    assert len(summary["scene_bucket_counts"]) == 10
    assert summary["unique_authors"] == 159
    assert summary["minimum_internal_dhash_distance"] > 4
    assert summary["minimum_seed_dhash_distance"] > 4
    assert all(row["License"] == "https://creativecommons.org/licenses/by/2.0/" for row in manifest)
    assert all(
        Path(row["source_image_path"]).is_file()
        and _sha256(Path(row["source_image_path"])) == row["source_image_sha256"]
        for row in manifest
    )


def test_queue_is_blind_resumable_and_repeats_preserve_exact_bytes() -> None:
    queue = _rows(PACKAGE / "review_package/review_queue.csv")
    mapping = _rows(PACKAGE / "review_package/internal_repeat_map.csv")
    queue_by_id = {row["review_id"]: row for row in queue}
    map_by_id = {row["review_id"]: row for row in mapping}
    repeats = [row for row in mapping if row["is_qc_repeat"] == "true"]

    assert len(queue) == len(mapping) == 180
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
    assert set(Counter(row["open_images_id"] for row in mapping).values()) <= {1, 2}
    assert all(
        _sha256(Path(queue_by_id[row["review_id"]]["image_path"]))
        == _sha256(Path(queue_by_id[row["canonical_review_id"]]["image_path"]))
        == map_by_id[row["canonical_review_id"]]["source_image_sha256"]
        for row in repeats
    )


def test_frozen_dhash_rule_holds_against_seed_and_within_selection() -> None:
    manifest = _rows(PACKAGE / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.csv")
    fingerprints = [int(row["dhash64"], 16) for row in _rows(SEED)]
    hashes = {row["image_sha256"] for row in _rows(SEED)}
    for row in manifest:
        current = int(row["dhash64"], 16)
        assert row["source_image_sha256"] not in hashes
        assert all((current ^ prior).bit_count() > 4 for prior in fingerprints)
        hashes.add(row["source_image_sha256"])
        fingerprints.append(current)


def test_provenance_confirms_no_models_or_downloads() -> None:
    provenance = json.loads((PACKAGE / "provenance.json").read_text(encoding="utf-8"))

    assert provenance["model_outputs_used"] is False
    assert provenance["new_downloads_performed"] is False
    assert provenance["first_pass_labels_exposed_to_reviewer"] is False
    assert provenance["source_artifact_hashes"]


def test_failed_repeat_qc_blocks_all_promotion() -> None:
    finalization = PACKAGE / "finalization"
    result = json.loads(
        (finalization / "negative_gold_external_confirmation_result.json").read_text(
            encoding="utf-8"
        )
    )
    qc = _rows(finalization / "hidden_repeat_qc.csv")
    canonical = _rows(finalization / "second_pass_canonical_labels.csv")
    dual = _rows(finalization / "dual_pass_comparison.csv")

    assert len(canonical) == len(dual) == 160
    assert Counter(row["semantic_class"] for row in canonical) == {"ZERO_HAND": 160}
    assert sum(row["exact_agreement"] == "True" for row in qc) == 18
    assert sum(row["critical_binary_disagreement"] == "True" for row in qc) == 2
    assert result["decision"] == "NEGATIVE_GOLD_V1_STILL_INCOMPLETE"
    assert result["dual_confirmed_zero_hand_diagnostic"] == 160
    assert result["diversity_clean_confirmed_diagnostic"] == 160
    assert result["confirmed_new_zero_hand"] == 0
    assert result["selected_benchmark_additions"] == 0
    assert result["reserve_count"] == 0
    assert result["final_negative_gold_v1_total"] == 76
    assert result["exact_remaining_deficit"] == 124
    assert result["benchmark_frozen"] is False
    assert not (finalization / "NEGATIVE_GOLD_V1_MANIFEST.csv").exists()
    assert not (finalization / "NEGATIVE_GOLD_RESERVE_MANIFEST.csv").exists()


def test_finalization_hash_manifest_matches_result_artifacts() -> None:
    finalization = PACKAGE / "finalization"
    manifest = json.loads(
        (finalization / "provenance_hash_manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["model_outputs_used"] is False
    assert manifest["human_labels_overridden"] is False
    assert all(
        _sha256(finalization / name) == expected
        for name, expected in manifest["result_artifact_hashes"].items()
    )
