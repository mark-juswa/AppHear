from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from eval.runtime_diagnostics.p4c3b_finalize import pair_features


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4c3b_physical_instance_validation_01"


def read_csv(name: str) -> list[dict[str, str]]:
    with (OUT / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_independent_truth_counts() -> None:
    result = json.loads((OUT / "p4c3b_result.json").read_text(encoding="utf-8"))
    assert sum(result["raw_A_labels"].values()) == 21
    assert sum(result["independent_pair_truth"].values()) == 100
    assert result["raw_A_labels"]["MISSING_REAL_HAND"] == 7


def test_actual_capacity_uses_only_confirmed_missing_hands() -> None:
    result = json.loads((OUT / "p4c3b_actual_recovery_capacity.json").read_text(encoding="utf-8"))
    assert result["actual_raw_recovery_capacity"]["numerator"] == 419 + 7
    assert result["reaches_98_percent_gate"] is False


def test_split_is_signer_and_sequence_separated() -> None:
    rows = read_csv("p4c3b_pair_features.csv")
    development_signers = {row["signer_id"] for row in rows if row["split"] == "DEVELOPMENT"}
    validation_signers = {row["signer_id"] for row in rows if row["split"] == "VALIDATION"}
    development_sequences = {row["sequence_id"] for row in rows if row["split"] == "DEVELOPMENT"}
    validation_sequences = {row["sequence_id"] for row in rows if row["split"] == "VALIDATION"}
    assert development_signers.isdisjoint(validation_signers)
    assert development_sequences.isdisjoint(validation_sequences)


def test_pair_features_are_candidate_order_symmetric() -> None:
    source = read_csv("p4c3b_pair_truth_manifest.csv")[0]
    forward = pair_features(source)
    swapped = dict(source)
    swapped["candidate_a_points_json"], swapped["candidate_b_points_json"] = source["candidate_b_points_json"], source["candidate_a_points_json"]
    reverse = pair_features(swapped)
    for feature in (
        "box_iou", "intersection_smaller_box_ratio", "normalized_center_distance",
        "normalized_wrist_distance", "mean_corresponding_distance_normalized",
        "median_corresponding_distance_normalized", "relative_proposal_scale",
        "translation_scale_normalized_shape_distance",
    ):
        assert float(forward[feature]) == pytest.approx(float(reverse[feature]), abs=1e-12)


def test_validation_confusion_is_complete() -> None:
    result = json.loads((OUT / "p4c3b_result.json").read_text(encoding="utf-8"))
    confusion = result["deduplication_validation"]["confusion"]
    assert sum(confusion.values()) == result["deduplication_validation"]["rows"]
    assert result["decision"]["path"] == "PATH_2"

