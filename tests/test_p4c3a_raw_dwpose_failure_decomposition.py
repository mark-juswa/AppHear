from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4c3a_raw_dwpose_failure_decomposition_01"


def read_csv(name: str) -> list[dict[str, str]]:
    with (OUT / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_frozen_case_counts() -> None:
    assert len(read_csv("p4c3a_missing_hand_classification.csv")) == 25
    assert len(read_csv("p4c3a_collision_classification.csv")) == 60


def test_missing_categories_partition_all_misses() -> None:
    result = json.loads((OUT / "p4c3a_result.json").read_text(encoding="utf-8"))
    assert sum(result["missing_categories"].values()) == 25
    assert result["one_hand_misses"] + result["two_hand_misses"] == 25


def test_collision_categories_partition_all_collisions() -> None:
    result = json.loads((OUT / "p4c3a_result.json").read_text(encoding="utf-8"))
    assert sum(result["collision_categories"].values()) == 60
    arm = result["arm_association_on_duplicates"]
    assert arm["true_slot_preferred"] + arm["false_slot_preferred"] + arm["tie_ambiguous"] == result["collision_categories"]["SAME_PHYSICAL_HAND_DUPLICATE"]


def test_decision_is_diagnostic_only() -> None:
    decision = json.loads((OUT / "p4c3a_architecture_decision.json").read_text(encoding="utf-8"))
    assert decision["final_path"] in {
        "A_RAW_CANDIDATE_RGB_VERIFY",
        "B_ARM_WRIST_ROI_RGB_VERIFY",
        "C_TARGETED_SECOND_STAGE_LANDMARK_RECOVERY_REQUIRED",
    }
    assert decision["no_implementation_authorized"] is True

