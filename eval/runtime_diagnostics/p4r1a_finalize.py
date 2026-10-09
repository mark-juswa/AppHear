"""Finalize P4-R1A after the bounded 18-case human recovery review."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4r1a_rtmpose_hand5_targeted_recovery_01"


def read_csv(name: str) -> list[dict[str, str]]:
    with (OUT / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_csv(name: str, rows: list[dict[str, Any]]) -> None:
    path = OUT / name
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(name: str, value: dict[str, Any]) -> None:
    path = OUT / name
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    reviews = read_csv("p4r1a_recovery_review.csv")
    residual = read_csv("p4r1a_residual_18_manifest.csv")
    queue = read_csv("p4r1a_recovery_review_queue.csv")
    controls = read_csv("p4r1a_control_manifest.csv")
    runtime = read_csv("p4r1a_runtime_results.csv")
    if len(reviews) != 18 or len(residual) != 18 or len(queue) != 18:
        raise RuntimeError("P4R1A_FINALIZATION_ROW_COUNT_MISMATCH")
    if any(row["reviewer_status"] != "COMPLETE" for row in reviews):
        raise RuntimeError("P4R1A_HUMAN_REVIEW_INCOMPLETE")
    allowed = {"MISSING_HAND_RECOVERED", "DUPLICATE_EXISTING_HAND", "FALSE_REGION_OR_NO_OUTPUT", "AMBIGUOUS"}
    if any(row["review_label"] not in allowed for row in reviews):
        raise RuntimeError("P4R1A_INVALID_HUMAN_REVIEW_LABEL")

    review_by_id = {row["residual_id"]: row for row in reviews}
    queue_by_id = {row["residual_id"]: row for row in queue}
    result_rows: list[dict[str, Any]] = []
    for item in residual:
        result_rows.append(
            {
                **item,
                "accepted_recovery_outputs": int(queue_by_id[item["residual_id"]]["accepted_recovery_outputs"]),
                "human_recovery_label": review_by_id[item["residual_id"]]["review_label"],
                "reviewed_utc": review_by_id[item["residual_id"]]["reviewed_utc"],
                "reviewer_note": review_by_id[item["residual_id"]]["reviewer_note"],
            }
        )
    atomic_csv("p4r1a_residual_recovery_results.csv", result_rows)

    runtime_by_frame = {row["frame_id"]: row for row in runtime}
    control_rows: dict[str, list[dict[str, Any]]] = {"ZERO_CONTROL": [], "ONE_CONTROL": [], "TWO_CONTROL": []}
    for item in controls:
        accepted = int(runtime_by_frame[item["frame_id"]]["accepted_detections"])
        control_rows[item["control_type"]].append(
            {
                **item,
                "accepted_recovery_outputs": accepted,
                "any_recovery_output": accepted >= 1,
                "two_or_more_recovery_outputs": accepted >= 2,
                "physical_instance_interpretation": "RAW_OUTPUT_COUNT_BOUND_ONLY",
            }
        )
    atomic_csv("p4r1a_zero_control_results.csv", control_rows["ZERO_CONTROL"])
    atomic_csv("p4r1a_one_control_results.csv", control_rows["ONE_CONTROL"])
    atomic_csv("p4r1a_two_control_results.csv", control_rows["TWO_CONTROL"])

    counts = {label: sum(row["review_label"] == label for row in reviews) for label in sorted(allowed)}
    recovered = counts["MISSING_HAND_RECOVERED"]
    combined_numerator = 426 + recovered
    zero_any = sum(row["any_recovery_output"] for row in control_rows["ZERO_CONTROL"])
    one_any = sum(row["any_recovery_output"] for row in control_rows["ONE_CONTROL"])
    one_extra = sum(row["two_or_more_recovery_outputs"] for row in control_rows["ONE_CONTROL"])
    two_two_or_more = sum(row["two_or_more_recovery_outputs"] for row in control_rows["TWO_CONTROL"])
    result = {
        "status": "P4R1A_COMPLETE",
        "classification": "RECOVERY_CANDIDATE_INSUFFICIENT",
        "v2_verified_sha256": "24f5d8d442702e3a27424ff7f55cc24f1338f5683e5988a6a4916557e1d4252d",
        "residual_cases": 18,
        "human_review_counts": counts,
        "genuinely_recovered": recovered,
        "duplicate_existing": counts["DUPLICATE_EXISTING_HAND"],
        "false_region_or_no_output": counts["FALSE_REGION_OR_NO_OUTPUT"],
        "ambiguous": counts["AMBIGUOUS"],
        "residual_recovery_rate": {"numerator": recovered, "denominator": 18, "rate": recovered / 18},
        "combined_physical_coverage": {
            "numerator": combined_numerator,
            "denominator": 444,
            "rate": combined_numerator / 444,
            "required_numerator": 436,
            "passes": combined_numerator >= 436,
        },
        "control_diagnostics": {
            "zero_false_activation": {"numerator": zero_any, "denominator": 40, "rate": zero_any / 40, "gate_max": 0.10, "passes": zero_any / 40 <= 0.10},
            "one_existence": {"numerator": one_any, "denominator": 40, "rate": one_any / 40, "gate_min": 0.97, "passes": one_any / 40 >= 0.97},
            "one_extra_output_upper_bound": {"numerator": one_extra, "denominator": 40, "rate": one_extra / 40, "gate_max": 0.10, "passes_raw_bound": one_extra / 40 <= 0.10},
            "two_complete_upper_bound": {"numerator": two_two_or_more, "denominator": 40, "rate": two_two_or_more / 40, "gate_min": 0.95, "passes": two_two_or_more / 40 >= 0.95},
            "physical_instance_caveat": "ONE extra-hand and TWO completeness use raw accepted-output counts only. TWO can be at most the reported two-output rate, so its 95% gate fails without requiring further physical-instance adjudication.",
        },
        "gates": {
            "residual_recovery_at_least_10_of_18": recovered >= 10,
            "combined_coverage_at_least_436_of_444": combined_numerator >= 436,
            "zero_false_activation_at_most_10_percent": zero_any / 40 <= 0.10,
            "one_existence_at_least_97_percent": one_any / 40 >= 0.97,
            "one_extra_output_upper_bound_at_most_10_percent": one_extra / 40 <= 0.10,
            "two_complete_possible_at_least_95_percent": two_two_or_more / 40 >= 0.95,
        },
        "review_sha256": sha256(OUT / "p4r1a_recovery_review.csv"),
        "human_labels_invented": False,
        "no_additional_model_inference_during_finalization": True,
    }
    atomic_json("p4r1a_final_result.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
