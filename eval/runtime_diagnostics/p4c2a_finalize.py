"""Finalize the frozen P4-C2A blinded crop audit without changing its evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4c2a_dwpose_rgb_crop_separability_01"
TRUTH = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4a2_fresh_evidence_repair_v2_01/frozen_truth/P4A2_FRESH_HUMAN_TRUTH_V1.csv"
SAMPLE = OUT / "p4c2a_audit_sample_manifest.csv"
QUEUE = OUT / "p4c2a_blinded_review_queue.csv"
REVIEW = OUT / "p4c2a_human_crop_review.csv"
TRUE_FAILURES = OUT / "p4c2a_true_crop_failures.csv"
FALSE_VISUAL_POSITIVES = OUT / "p4c2a_false_proposal_visual_positive_cases.csv"
TRUTH_DISCREPANCIES = OUT / "p4c2a_governed_truth_discrepancies.csv"
RESULT_JSON = OUT / "p4c2a_result.json"
REPORT = OUT / "P4C2A_DWPOSE_RGB_CROP_SEPARABILITY_RESULT.md"
HASHES = OUT / "p4c2a_artifact_hash_manifest.json"
EXPECTED_DATASET = "7819c59123b4dacdafac190c81754deb766d6ed6087a2b58535490d45a6a3edd"
EXPECTED_ANNOTATION = "1b9f34412ba885e397019742bf29027987ce58668d099fd3914e48ab3206774b"
EXPECTED_QUEUE = "e29161f0a8378e008c8d8f0e2da062ec4654765d1e91ea4c6e6f006034bb2bba"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else ["crop_id"]
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def dataset_hash(rows: list[dict[str, str]]) -> str:
    label_fields = [
        "any_hand_visible", "visible_left", "visible_right", "zero_hand", "rest", "entering",
        "leaving", "blur", "occlusion", "edge_clipped", "partial_visibility", "crossing",
        "hand_hand_contact", "hand_body_contact", "left_visibility_quality",
        "right_visibility_quality", "reviewer_note",
    ]
    fields = ["annotation_row_id", "sequence_id", "frame_index", "image_sha256", *label_fields, "reviewer_status"]
    payload = [{field: row[field] for field in fields} for row in sorted(rows, key=lambda row: row["annotation_row_id"])]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def percent(numerator: int, denominator: int) -> float:
    return 100.0 * numerator / denominator if denominator else 0.0


def main() -> None:
    truth = read_csv(TRUTH)
    if sha256(TRUTH) != EXPECTED_ANNOTATION or dataset_hash(truth) != EXPECTED_DATASET:
        raise RuntimeError("P4C2A_FROZEN_EVIDENCE_MISMATCH")
    if sha256(QUEUE) != EXPECTED_QUEUE:
        raise RuntimeError("P4C2A_QUEUE_IDENTITY_MISMATCH")

    sample = read_csv(SAMPLE)
    queue = read_csv(QUEUE)
    reviews = read_csv(REVIEW)
    if len(sample) != 200 or len(queue) != 200 or len(reviews) != 200:
        raise RuntimeError("P4C2A_REVIEW_INCOMPLETE")
    sample_by_id = {row["crop_id"]: row for row in sample}
    queue_by_id = {row["crop_id"]: row for row in queue}
    review_by_id = {row["crop_id"]: row for row in reviews}
    if len(sample_by_id) != 200 or set(sample_by_id) != set(queue_by_id) or set(sample_by_id) != set(review_by_id):
        raise RuntimeError("P4C2A_CROP_IDENTITY_MISMATCH")
    allowed = {"YES_CLEAR", "YES_PARTIAL", "NO", "UNCERTAIN"}
    for crop_id, review in review_by_id.items():
        queue_row = queue_by_id[crop_id]
        if review["reviewer_status"] != "COMPLETE" or review["reviewer_label"] not in allowed:
            raise RuntimeError("P4C2A_REVIEW_INCOMPLETE")
        if review["crop_sha256"] != queue_row["crop_sha256"]:
            raise RuntimeError("P4C2A_CROP_IDENTITY_MISMATCH")
        crop_path = Path(queue_row["crop_path"])
        frame_path = Path(queue_row["full_frame_path"])
        if sha256(crop_path) != queue_row["crop_sha256"] or sha256(frame_path) != queue_row["full_frame_sha256"]:
            raise RuntimeError("P4C2A_SOURCE_MISMATCH")

    joined: list[dict[str, str]] = []
    for row in sample:
        review = review_by_id[row["crop_id"]]
        joined.append({**row, **{f"review_{key}": value for key, value in review.items() if key != "crop_id"}})

    by_truth = {
        category: Counter(row["review_reviewer_label"] for row in joined if row["truth_category"] == category)
        for category in ("REAL_VISIBLE_HAND", "FALSE_DWPOSE_PROPOSAL")
    }
    review_counts = Counter(row["review_reviewer_label"] for row in joined)
    positive_identified = by_truth["REAL_VISIBLE_HAND"]["YES_CLEAR"] + by_truth["REAL_VISIBLE_HAND"]["YES_PARTIAL"]
    false_rejected = by_truth["FALSE_DWPOSE_PROPOSAL"]["NO"]
    uncertain = review_counts["UNCERTAIN"]
    gate_a = positive_identified >= 95
    gate_b = false_rejected >= 80
    gate_c = uncertain <= 20

    true_failures = [row for row in joined if row["truth_category"] == "REAL_VISIBLE_HAND" and row["review_reviewer_label"] in {"NO", "UNCERTAIN"}]
    false_visual = [row for row in joined if row["truth_category"] == "FALSE_DWPOSE_PROPOSAL" and row["review_reviewer_label"] in {"YES_CLEAR", "YES_PARTIAL"}]
    for row in true_failures:
        row["diagnostic_interpretation"] = "GOVERNED_VISIBLE_HAND_NOT_IDENTIFIABLE_IN_FROZEN_PROPOSAL_CROP"
    for row in false_visual:
        if row["one_hand_opposite_slot_absent"] == "YES":
            diagnosis = "ABSENT_SLOT_CROP_MAY_CONTAIN_THE_OTHER_VISIBLE_HAND"
        elif row["zero_hand"] == "YES":
            diagnosis = "GOVERNED_ZERO_HAND_CONTRADICTED_BY_CROP_REVIEW"
        else:
            diagnosis = "GOVERNED_ABSENT_SLOT_CROP_VISUALLY_CONTAINS_A_HAND"
        row["diagnostic_interpretation"] = diagnosis
    atomic_csv(TRUE_FAILURES, true_failures)
    atomic_csv(FALSE_VISUAL_POSITIVES, false_visual)

    # These rows are preserved, not relabeled. A bounded post-unblinding full-frame inspection
    # confirmed conspicuous real hands in all governed ZERO_HAND source frames listed here.
    truth_discrepancies = [
        {**row, "post_unblinding_full_frame_check": "CLEAR_REAL_HUMAN_HAND_VISIBLE", "truth_action": "PRESERVED_UNCHANGED_FLAGGED_FOR_GOVERNANCE_REVIEW"}
        for row in false_visual if row["zero_hand"] == "YES"
    ]
    atomic_csv(TRUTH_DISCREPANCIES, truth_discrepancies)

    invalid_reason = (
        "Frozen governed ZERO_HAND truth is contradicted by clear real hands in 10 sampled slot-crops "
        "from 8 source frames; additionally, 23 absent-slot crops occur in one-hand frames and are "
        "visually consistent with capturing the opposite real hand."
    )
    result = {
        "status": "P4C2A_COMPLETE",
        "final_classification": "EXPERIMENT_INVALID",
        "classification_reason": invalid_reason,
        "frozen_evidence_verified": True,
        "review_integrity_passed": True,
        "review_rows": 200,
        "review_counts": dict(sorted(review_counts.items())),
        "proposal_inventory": {
            "true_visible_hand_proposals": 429,
            "false_dwpose_proposals": 159,
            "visible_hand_proposal_misses": 19,
            "visible_hand_truth_total": 448,
            "proposal_generation_recall": 429 / 448,
        },
        "unblinded_counts": {key: dict(sorted(value.items())) for key, value in by_truth.items()},
        "metrics": {
            "positive_crop_human_identifiability": positive_identified / 100,
            "false_proposal_human_rejection": false_rejected / 100,
            "overall_uncertainty": uncertain / 200,
        },
        "gates": {
            "A_positive_identifiability_ge_95pct": gate_a,
            "B_false_proposal_rejection_ge_80pct": gate_b,
            "C_uncertainty_le_10pct": gate_c,
        },
        "failure_counts": {
            "true_crops_no_or_uncertain": len(true_failures),
            "false_proposals_visually_hand_positive": len(false_visual),
            "false_visual_positive_opposite_slot_context": sum(row["one_hand_opposite_slot_absent"] == "YES" for row in false_visual),
            "false_visual_positive_governed_zero_hand": len(truth_discrepancies),
            "unique_governed_zero_hand_discrepancy_frames": len({row["annotation_row_id"] for row in truth_discrepancies}),
        },
        "review_sha256": sha256(REVIEW),
        "dataset_sha256": EXPECTED_DATASET,
        "annotation_sha256": EXPECTED_ANNOTATION,
        "no_training_or_model_work": True,
        "next_step": "STOP_FOR_PROJECT_LEAD_GOVERNANCE_REVIEW; DO_NOT_TRAIN_P4_C2B",
    }
    atomic_json(RESULT_JSON, result)

    report = f"""# P4-C2A DWPose RGB Crop Separability Result

## Executive decision

**P4C2A_COMPLETE — EXPERIMENT_INVALID.**

The blinded review itself completed with intact crop identities and provenance. After unblinding,
the frozen comparison evidence was found to contain material semantic contradictions. The original
governed labels are preserved unchanged; this report does not retroactively repair or reinterpret them.

Because the benchmark truth is not reliable for this sampled comparison, P4-C2B classifier training is
**not justified** from this result. No MobileNet/CNN or other classifier was trained.

## Frozen evidence and proposal ceiling

- Frozen dataset hash verified: `{EXPECTED_DATASET}`
- Frozen annotation hash verified: `{EXPECTED_ANNOTATION}`
- True visible-hand proposals: **429**
- False DWPose proposals: **159**
- Visible observations without a qualified proposal: **19**
- Proposal-generation recall: **429/448 = {percent(429, 448):.2f}%**
- DWPose inference rerun: **none**

## Blinded review

- Reviewed: **200/200** crops
- YES_CLEAR: **{review_counts['YES_CLEAR']}**
- YES_PARTIAL: **{review_counts['YES_PARTIAL']}**
- NO: **{review_counts['NO']}**
- UNCERTAIN: **{review_counts['UNCERTAIN']}**
- Review file SHA-256: `{sha256(REVIEW)}`

### Unblinded table

| Frozen class | YES_CLEAR | YES_PARTIAL | NO | UNCERTAIN |
|---|---:|---:|---:|---:|
| REAL_VISIBLE_HAND | {by_truth['REAL_VISIBLE_HAND']['YES_CLEAR']} | {by_truth['REAL_VISIBLE_HAND']['YES_PARTIAL']} | {by_truth['REAL_VISIBLE_HAND']['NO']} | {by_truth['REAL_VISIBLE_HAND']['UNCERTAIN']} |
| FALSE_DWPOSE_PROPOSAL | {by_truth['FALSE_DWPOSE_PROPOSAL']['YES_CLEAR']} | {by_truth['FALSE_DWPOSE_PROPOSAL']['YES_PARTIAL']} | {by_truth['FALSE_DWPOSE_PROPOSAL']['NO']} | {by_truth['FALSE_DWPOSE_PROPOSAL']['UNCERTAIN']} |

## Preregistered feasibility gates

| Gate | Frozen requirement | Observed | Result |
|---|---:|---:|---|
| A: true crop identifiable | >=95% | **{percent(positive_identified, 100):.2f}% (82/100)** | **{'PASS' if gate_a else 'FAIL'}** |
| B: false proposal rejected | >=80% | **{percent(false_rejected, 100):.2f}% (59/100)** | **{'PASS' if gate_b else 'FAIL'}** |
| C: overall uncertain | <=10% | **{percent(uncertain, 200):.2f}% (16/200)** | **{'PASS' if gate_c else 'FAIL'}** |

These frozen arithmetic results are retained, but Gates A/B cannot be treated as a valid clean
separability measurement because of the evidence defects below.

## Failure and evidence-integrity analysis

### Governed true-hand crops not visually identifiable

**18/100** governed true proposal crops were reviewed as NO (10) or UNCERTAIN (8). This shows that
the frozen 1.5x point-envelope crop does not consistently expose enough recognizable hand pixels,
even when the corresponding anatomical hand is governed as visible. The rule may be centered on a
mislocalized proposal, truncated by the frame, or dominated by non-hand pixels; it was not changed
after review.

### Governed false proposals that visibly contain a hand

**33/100** governed false proposals were reviewed as YES_CLEAR/YES_PARTIAL.

- **23/33** are absent anatomical slots in one-hand frames. The frame truth says the other hand is
  visible, so this pattern is consistent with the false slot proposal landing on the real opposite
  hand. A binary crop verifier answering “is any hand visible?” cannot establish slot association.
- **10/33**, spanning **8 source frames**, are labeled governed ZERO_HAND yet the saved crops and
  bounded full-frame inspection show conspicuous real human hands. These original truth labels are
  preserved but flagged in `p4c2a_governed_truth_discrepancies.csv`.

This is not a narrow gate miss. It exposes two different blockers: the crop rule sometimes fails to
show a governed real hand, while the proposed binary target cannot distinguish an absent slot whose
crop captures the other real hand. The sampled ZERO_HAND contradictions also prevent treating the
current percentages as clean benchmark evidence.

## Classification and next action

**EXPERIMENT_INVALID** under the preregistered invalidity condition for corrupted labels/evidence.
The completed blinded review is still useful diagnostic evidence, but it does not justify training a
lightweight RGB verifier. Stop for project-lead benchmark/target-definition review. Do not silently
relabel these rows, change crop padding, or launch another audit/training loop automatically.

No MobileNet, CNN, transfer learning, HVD, logistic regression, augmentation, threshold tuning,
WiLoR fusion, DWPose rerun/modification, Android, recognition, P4-C2B, P4-D, or P4-B work occurred.
"""
    atomic_text(REPORT, report)

    tracked = [
        SAMPLE, QUEUE, REVIEW, TRUE_FAILURES, FALSE_VISUAL_POSITIVES,
        TRUTH_DISCREPANCIES, RESULT_JSON, REPORT,
        OUT / "p4c2a_crop_generation_manifest.csv", OUT / "p4c2a_proposal_misses.csv",
        OUT / "p4c2a_crop_rule.json", OUT / "p4c2a_blinding_manifest.json",
        OUT / "p4c2a_provenance.json",
    ]
    atomic_json(HASHES, {
        "status": "P4C2A_COMPLETE_EXPERIMENT_INVALID",
        "artifacts": {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in tracked},
    })
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
