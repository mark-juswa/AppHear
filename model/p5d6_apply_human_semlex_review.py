"""Apply a completed P5-D6 human decision sheet to frozen metadata.

This calculator performs no download, dataset mutation, DWPose extraction,
V2 generation, merge, or training. It is prepared in P5-D6 but not executed.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path


ALLOWED = {"ACCEPT_EXACT_FORM", "ACCEPT_COMPATIBLE_VARIANT", "REJECT_FORM_MISMATCH", "UNRESOLVED"}


def read(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("decision_sheet", type=Path)
    parser.add_argument("--d5-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    decisions = read(args.decision_sheet)
    if len(decisions) != 68 or len({row["class_id"] for row in decisions}) != 68:
        raise SystemExit("Expected 68 unique human-review rows")
    invalid = [row for row in decisions if row["human_decision"] not in ALLOWED]
    if invalid:
        raise SystemExit("Every row must contain exactly one allowed human decision")
    qualified = read(args.d5_dir / "semlex_target_class_qualification.csv")
    fallback = read(args.d5_dir / "msasl_fallback_candidates.csv")
    pre_exact = [row for row in qualified if row["qualification_state"] == "ACCEPT_METADATA_EXACT"]
    decision_by_id = {row["class_id"]: row for row in decisions}
    accepted_human = [row for row in decisions if row["human_decision"] in ("ACCEPT_EXACT_FORM", "ACCEPT_COMPATIBLE_VARIANT")]
    accepted_ids = {row["class_id"] for row in accepted_human} | {row["apphear_class_id"] for row in pre_exact}
    accepted_exact = len(pre_exact) + sum(row["human_decision"] == "ACCEPT_EXACT_FORM" for row in decisions)
    accepted_variant = sum(row["human_decision"] == "ACCEPT_COMPATIBLE_VARIANT" for row in decisions)
    accepted_clips = sum(int(row["historically_reviewed_exact_clips"]) for row in pre_exact) + sum(int(row["semlex_candidate_train_clips"]) for row in accepted_human)
    accepted_slots = sum(int(row["historically_reviewed_exact_signers"]) for row in pre_exact) + sum(int(row["semlex_candidate_signers"]) for row in accepted_human)
    gains = [int(row["historically_reviewed_exact_signers"]) for row in pre_exact] + [int(row["semlex_candidate_signers"]) for row in accepted_human]
    accepted_critical = len([row for row in accepted_human if row["coverage_deficit_level"] == "CRITICAL_COVERAGE_DEFICIT"]) + len([row for row in pre_exact if row["coverage_deficit_level"] == "CRITICAL_COVERAGE_DEFICIT"])
    accepted_high = len([row for row in accepted_human if row["coverage_deficit_level"] == "HIGH_COVERAGE_DEFICIT"])
    unresolved = [row for row in decisions if row["human_decision"] == "UNRESOLVED"]
    unresolved_critical = sum(row["coverage_deficit_level"] == "CRITICAL_COVERAGE_DEFICIT" for row in unresolved)
    accepted_total = len(accepted_ids)
    median_gain = statistics.median(gains) if gains else 0
    if len(unresolved) >= 14 or unresolved_critical >= 8:
        classification = "SEMLEX_REVIEW_INCOMPLETE"
    elif accepted_total >= 47 and accepted_critical >= 27 and accepted_high >= 20 and median_gain >= 11:
        classification = "SEMLEX_RAW_ACQUISITION_JUSTIFIED"
    elif accepted_total >= 7 and accepted_critical >= 1:
        classification = "SEMLEX_RAW_ACQUISITION_TARGETED_ONLY"
    else:
        classification = "SEMLEX_RAW_ACQUISITION_NOT_JUSTIFIED"
    result = {
        "classification": classification, "accepted_exact_classes": accepted_exact,
        "accepted_compatible_variant_classes": accepted_variant,
        "rejected_classes": sum(row["human_decision"] == "REJECT_FORM_MISMATCH" for row in decisions),
        "unresolved_classes": len(unresolved), "accepted_candidate_clips": accepted_clips,
        "accepted_signer_class_slots": accepted_slots, "median_accepted_signer_gain": median_gain,
        "critical_classes_covered": accepted_critical, "high_classes_covered": accepted_high,
        "msasl_fallback_classes_remaining": sum(row["apphear_class_id"] not in accepted_ids for row in fallback),
        "raw_video_downloaded": False, "dwpose": "NONE", "external_merge": False, "training": False,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
