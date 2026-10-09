"""Finalize the bounded P4-C2R R1 QA gate without creating V2 on failure."""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from eval.runtime_diagnostics.p4c2r_truth_review import (
    OUT,
    QUEUE,
    REVIEW,
    ROOT,
    SELECTION,
    V1,
    dataset_hash,
    read_csv,
    sha256,
    verify_r0,
)

EXPECTED_DATASET = "7819c59123b4dacdafac190c81754deb766d6ed6087a2b58535490d45a6a3edd"
EXPECTED_ANNOTATION = "1b9f34412ba885e397019742bf29027987ce58668d099fd3914e48ab3206774b"
REPORT = OUT / "P4C2R_PROPOSAL_OWNERSHIP_TRUTH_REPAIR_RESULT.md"
QA_OUT = OUT / "p4c2r_qa_disagreements.csv"
CHANGE_OUT = OUT / "p4c2r_truth_change_log.csv"
RESULT_OUT = OUT / "p4c2r_result.json"
STOP_HASHES = OUT / "p4c2r_stop_artifact_hash_manifest.json"


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def finalize() -> dict[str, Any]:
    if sha256(V1) != EXPECTED_ANNOTATION or dataset_hash(read_csv(V1)) != EXPECTED_DATASET:
        raise RuntimeError("P4C2R_SOURCE_EVIDENCE_MISMATCH")
    verify_r0()
    queue = read_csv(QUEUE)
    review = read_csv(REVIEW)
    selection = read_csv(SELECTION)
    if len(queue) != 148 or len(review) != 148 or len(selection) != 148:
        raise RuntimeError("P4C2R_REVIEW_INTEGRITY_FAILURE")
    if any(row["reviewer_status"] != "COMPLETE" for row in review):
        raise RuntimeError("P4C2R_REVIEW_INCOMPLETE")
    for rows in (queue, review, selection):
        if len({row["review_row_id"] for row in rows}) != 148:
            raise RuntimeError("P4C2R_REVIEW_INTEGRITY_FAILURE")
    queue_by_id = {row["review_row_id"]: row for row in queue}
    review_by_id = {row["review_row_id"]: row for row in review}
    selection_by_id = {row["review_row_id"]: row for row in selection}
    if set(queue_by_id) != set(review_by_id) or set(queue_by_id) != set(selection_by_id):
        raise RuntimeError("P4C2R_REVIEW_INTEGRITY_FAILURE")

    qa_rows: list[dict[str, str]] = []
    change_rows: list[dict[str, str]] = []
    material_qa_frames: set[str] = set()
    material_qa_by_category: Counter[str] = Counter()
    material_qa_sides = 0
    uncertain_qa_sides = 0
    qa_counts: Counter[str] = Counter()
    all_changed_frames: set[str] = set()
    for identifier, selected in selection_by_id.items():
        queued = queue_by_id[identifier]
        reviewed = review_by_id[identifier]
        identity_fields = (
            "source_annotation_row_id",
            "sequence_id",
            "frame_index",
            "image_sha256",
            "image_path",
        )
        if any(queued[field] != reviewed[field] for field in identity_fields):
            raise RuntimeError("ANNOTATION_ROW_IDENTITY_MISMATCH")
        if any(selected[field] != reviewed[field] for field in identity_fields):
            raise RuntimeError("ANNOTATION_ROW_IDENTITY_MISMATCH")
        image = Path(reviewed["image_path"])
        if not image.is_file() or sha256(image) != reviewed["image_sha256"]:
            raise RuntimeError("ANNOTATION_ROW_IDENTITY_MISMATCH")
        category = selected["selection_category"]
        is_qa = category.startswith("QA_")
        if is_qa:
            qa_counts[category] += 1
        frame_changed = False
        for side in ("left", "right"):
            old = selected[f"v1_visible_{side}"]
            new = reviewed[f"visible_{side}"]
            if is_qa and new == "UNCERTAIN":
                uncertain_qa_sides += 1
            material = old in {"YES", "NO"} and new in {"YES", "NO"} and old != new
            if material:
                frame_changed = True
                all_changed_frames.add(selected["source_annotation_row_id"])
                if is_qa:
                    material_qa_frames.add(selected["source_annotation_row_id"])
                    material_qa_sides += 1
                change_rows.append(
                    {
                        "frame_id": selected["source_annotation_row_id"],
                        "source_sha256": selected["image_sha256"],
                        "anatomical_side": side.upper(),
                        "old_label": old,
                        "new_label": new,
                        "reviewer_decision": new,
                        "reason": "INDEPENDENT_R1_VISIBILITY_ADJUDICATION",
                        "reviewed_utc": reviewed["reviewed_utc"],
                        "originating_discrepancy_category": category,
                        "application_status": "NOT_APPLIED_BROADER_REAUDIT_REQUIRED",
                    }
                )
        if is_qa:
            qa_rows.append(
                {
                    "frame_id": selected["source_annotation_row_id"],
                    "source_sha256": selected["image_sha256"],
                    "qa_category": category,
                    "v1_visible_left": selected["v1_visible_left"],
                    "v1_visible_right": selected["v1_visible_right"],
                    "review_visible_left": reviewed["visible_left"],
                    "review_visible_right": reviewed["visible_right"],
                    "review_frame_state": reviewed["frame_state"],
                    "material_visibility_disagreement": "YES" if frame_changed else "NO",
                    "reviewed_utc": reviewed["reviewed_utc"],
                }
            )
            if frame_changed:
                material_qa_by_category[category] += 1

    if qa_counts != {"QA_ZERO_HAND": 40, "QA_ONE_HAND": 40, "QA_TWO_HAND": 20}:
        raise RuntimeError("P4C2R_REVIEW_INTEGRITY_FAILURE")
    qa_fields = list(qa_rows[0])
    change_fields = [
        "frame_id",
        "source_sha256",
        "anatomical_side",
        "old_label",
        "new_label",
        "reviewer_decision",
        "reason",
        "reviewed_utc",
        "originating_discrepancy_category",
        "application_status",
    ]
    atomic_csv(QA_OUT, qa_rows, qa_fields)
    atomic_csv(CHANGE_OUT, change_rows, change_fields)
    disagreement_count = len(material_qa_frames)
    if disagreement_count < 3:
        raise RuntimeError("P4C2R_FINALIZER_SCOPE_ERROR: QA passed; R2-R5 processor required")
    result = {
        "status": "TRUTH_V1_BROADER_REAUDIT_REQUIRED",
        "p4c2r_complete": False,
        "v1_hashes_verified": True,
        "frames_human_adjudicated": 148,
        "qa_frames": 100,
        "qa_material_disagreement_frames": disagreement_count,
        "qa_material_disagreement_frames_by_category": dict(
            sorted(material_qa_by_category.items())
        ),
        "qa_material_disagreement_sides": material_qa_sides,
        "qa_uncertain_sides": uncertain_qa_sides,
        "qa_gate_passed": False,
        "all_reviewed_material_change_frames": len(all_changed_frames),
        "all_reviewed_material_change_sides": len(change_rows),
        "v1_to_v2_visibility_corrections_applied": 0,
        "v2_created": False,
        "r2_r5_started": False,
        "final_classification": "TRUTH_V1_BROADER_REAUDIT_REQUIRED",
        "review_sha256": sha256(REVIEW),
        "qa_disagreements_sha256": sha256(QA_OUT),
        "unapplied_change_log_sha256": sha256(CHANGE_OUT),
    }
    atomic_json(RESULT_OUT, result)
    atomic_text(
        REPORT,
        f"""# P4-C2R Proposal Coverage, Slot Ownership, and Truth Repair

## Final status

**STOP — `TRUTH_V1_BROADER_REAUDIT_REQUIRED`.**

R0 source evidence and the immutable V1 hashes were verified. The independent R1 review completed
all **148/148** full frames. The bounded random QA subset contained **{disagreement_count}/100**
material visibility disagreements ({material_qa_sides} anatomical-side changes), exceeding the
frozen stop boundary of at least 3. The QA composition remained exactly 40 V1 zero-hand, 40 V1
one-hand, and 20 V1 two-hand frames.

Disagreement frames by QA stratum: **{material_qa_by_category["QA_ZERO_HAND"]} zero-hand**,
**{material_qa_by_category["QA_ONE_HAND"]} one-hand**, and
**{material_qa_by_category["QA_TWO_HAND"]} two-hand**.

The known flagged frames were excluded from this QA rate as preregistered. Across all 148 reviewed
frames, {len(all_changed_frames)} frames / {len(change_rows)} anatomical-side labels differed
materially from V1. These decisions are preserved in `p4c2r_truth_change_log.csv` but explicitly
marked `NOT_APPLIED_BROADER_REAUDIT_REQUIRED`.

## Mandatory consequences

- V1 remains immutable.
- `P4_ELIGIBILITY_TRUTH_V2` was **not** created.
- Zero V1-to-V2 corrections were applied.
- R2 proposal coverage, R3 fallback, R4 ownership, and R5 crop rescore were **not started**.
- Proposal and ownership metrics are intentionally not reported because their truth basis failed
  bounded QA.

No classifier training, MobileNet, HVD, WiLoR, DWPose inference, threshold tuning, Android,
recognition, S4-S7, P4-C2B, P4-D, or P4-B work occurred.
""",
    )
    tracked = [
        REVIEW,
        QUEUE,
        SELECTION,
        QA_OUT,
        CHANGE_OUT,
        RESULT_OUT,
        REPORT,
        Path(__file__),
    ]
    atomic_json(
        STOP_HASHES,
        {
            "status": "FROZEN_STOP_TRUTH_V1_BROADER_REAUDIT_REQUIRED",
            "artifacts": {
                str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in tracked
            },
        },
    )
    return result


if __name__ == "__main__":
    print(json.dumps(finalize(), indent=2, sort_keys=True))
