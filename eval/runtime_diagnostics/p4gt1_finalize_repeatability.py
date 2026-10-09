"""Finalize the P4-GT1 repeatability stop without adjudication or V2 creation."""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from eval.runtime_diagnostics.p4c2r_truth_review import atomic_json, read_csv, sha256
from eval.runtime_diagnostics.p4gt1_pass1_review import OUT, REPORT, ROOT, STANDARD
from eval.runtime_diagnostics.p4gt1_repeatability_review import (
    PASS1_FULL,
    QUEUE,
    REVIEW,
    SAMPLE,
    verify_completed_pass1,
)

DISAGREEMENTS = OUT / "p4gt1_repeatability_disagreements.csv"
RESULT = OUT / "p4gt1_result.json"
FINAL_HASHES = OUT / "p4gt1_repeatability_stop_artifact_hash_manifest.json"


def atomic_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def finalize() -> dict[str, Any]:
    verify_completed_pass1()
    full = read_csv(PASS1_FULL)
    sample = read_csv(SAMPLE)
    queue = read_csv(QUEUE)
    review = read_csv(REVIEW)
    if (
        len(full) != 458
        or len(sample) != len(queue)
        or len(queue) != len(review)
        or len(review) != 100
    ):
        raise RuntimeError("P4GT1_SOURCE_INTEGRITY_FAILURE")
    if any(row["reviewer_status"] != "COMPLETE" for row in review):
        raise RuntimeError("P4GT1_INCOMPLETE_HUMAN_REVIEW")
    if any(row["revision_count"] != "0" for row in review):
        raise RuntimeError("P4GT1_SOURCE_INTEGRITY_FAILURE")
    sample_by_id = {row["frame_id"]: row for row in sample}
    queue_by_id = {row["review_row_id"]: row for row in queue}
    if len(sample_by_id) != 100 or len(queue_by_id) != 100:
        raise RuntimeError("P4GT1_SOURCE_INTEGRITY_FAILURE")

    disagreements: list[dict[str, str]] = []
    material_frames: set[str] = set()
    uncertainty_transitions = 0
    for pass2 in review:
        queued = queue_by_id.get(pass2["review_row_id"])
        if queued is None:
            raise RuntimeError("P4GT1_SOURCE_INTEGRITY_FAILURE")
        for field in (
            "source_annotation_row_id",
            "sequence_id",
            "frame_index",
            "image_sha256",
            "image_path",
        ):
            if queued[field] != pass2[field]:
                raise RuntimeError("P4GT1_SOURCE_INTEGRITY_FAILURE")
        image = Path(pass2["image_path"])
        if not image.is_file() or sha256(image) != pass2["image_sha256"]:
            raise RuntimeError("P4GT1_SOURCE_INTEGRITY_FAILURE")
        pass1 = sample_by_id.get(pass2["source_annotation_row_id"])
        if pass1 is None or pass1["source_sha256"] != pass2["image_sha256"]:
            raise RuntimeError("P4GT1_SOURCE_INTEGRITY_FAILURE")
        for side in ("left", "right"):
            first = pass1[f"visible_{side}"]
            second = pass2[f"visible_{side}"]
            if {first, second} == {"YES", "NO"}:
                kind = "MATERIAL_YES_NO"
                material_frames.add(pass1["frame_id"])
            elif first != second and "UNCERTAIN" in (first, second):
                kind = "UNCERTAINTY_TRANSITION"
                uncertainty_transitions += 1
            else:
                continue
            disagreements.append(
                {
                    "frame_id": pass1["frame_id"],
                    "source_sha256": pass1["source_sha256"],
                    "signer_id": pass1["signer_id"],
                    "sequence_id": pass1["sequence_id"],
                    "frame_index": pass1["frame_index"],
                    "anatomical_side": side.upper(),
                    "pass1_label": first,
                    "pass2_label": second,
                    "disagreement_type": kind,
                    "pass1_stratum": pass1["pass1_stratum"],
                    "pass1_source": pass1["pass1_source"],
                    "pass1_reviewed_utc": pass1["pass1_reviewed_utc"],
                    "pass2_reviewed_utc": pass2["reviewed_utc"],
                    "adjudication_status": "NOT_STARTED_REPEATABILITY_INSUFFICIENT",
                }
            )
    fields = list(disagreements[0]) if disagreements else ["frame_id"]
    atomic_csv(DISAGREEMENTS, disagreements, fields)
    material_sides = sum(row["disagreement_type"] == "MATERIAL_YES_NO" for row in disagreements)
    stratum_counts = Counter(
        row["pass1_stratum"]
        for row in disagreements
        if row["disagreement_type"] == "MATERIAL_YES_NO"
    )
    source_counts = Counter(
        row["pass1_source"]
        for row in disagreements
        if row["disagreement_type"] == "MATERIAL_YES_NO"
    )
    side_gate = material_sides <= 2
    frame_gate = len(material_frames) <= 2
    if side_gate and frame_gate:
        raise RuntimeError(
            "P4GT1_FINALIZER_SCOPE_ERROR: repeatability passed; adjudication required"
        )
    result = {
        "status": "P4GT1_REPEATABILITY_INSUFFICIENT",
        "classification": "P4GT1_REPEATABILITY_INSUFFICIENT",
        "v1_hashes_verified": True,
        "p4c2r_148_reusable": True,
        "new_pass1_frames_reviewed": 310,
        "complete_pass1_count": 458,
        "pass2_repeatability_count": 100,
        "material_side_disagreements": material_sides,
        "material_side_denominator": 200,
        "material_side_direct_agreement_rate": (200 - material_sides) / 200,
        "material_frame_disagreements": len(material_frames),
        "material_frame_denominator": 100,
        "material_frame_agreement_rate": (100 - len(material_frames)) / 100,
        "uncertainty_transitions": uncertainty_transitions,
        "material_disagreements_by_pass1_stratum": dict(sorted(stratum_counts.items())),
        "material_disagreements_by_pass1_source": dict(sorted(source_counts.items())),
        "side_gate_max_2_of_200_passed": side_gate,
        "frame_gate_max_2_of_100_passed": frame_gate,
        "adjudication_started": False,
        "v2_created": False,
        "model_or_rescore_work_started": False,
        "pass1_full_sha256": sha256(PASS1_FULL),
        "pass2_review_sha256": sha256(REVIEW),
        "disagreements_sha256": sha256(DISAGREEMENTS),
    }
    atomic_json(RESULT, result)
    atomic_text(
        REPORT,
        f"""# P4-GT1 Eligibility Ground-Truth Rebuild Result

## Final status

**STOP — `P4GT1_REPEATABILITY_INSUFFICIENT`.**

Pass 1 is complete for all **458/458** governed frames. The independent blinded Pass-2 review is
complete for **100/100 frames / 200 anatomical sides**, with unchanged identities, hashes, and no
completed-label edits.

The repeatability comparison found **{material_sides}/200 YES↔NO anatomical-side disagreements**
across **{len(material_frames)}/100 frames**. Direct binary agreement was
**{(200 - material_sides) / 200:.2%} by side** and
**{(100 - len(material_frames)) / 100:.2%} by frame**. Both frozen gates required at most 2
disagreements. There were **{uncertainty_transitions} uncertainty transitions**.

Material disagreements by Pass-1 stratum: {dict(sorted(stratum_counts.items()))}. By evidence
source: {dict(sorted(source_counts.items()))}.

## Mandatory consequences

- No adjudication queue was created.
- `P4_ELIGIBILITY_TRUTH_V2` was not created.
- No DWPose proposal, P4-C2A, E2/R1, or WiLoR rescore was performed.
- Model development remains stopped pending project-lead review of the exact disagreement cases in
  `p4gt1_repeatability_disagreements.csv`.

No classifier training, detector, model inference, threshold tuning, Android, recognition,
S4-S7, P4-C2B, P4-D, or P4-B work occurred.
""",
    )
    tracked = [
        PASS1_FULL,
        SAMPLE,
        QUEUE,
        REVIEW,
        DISAGREEMENTS,
        RESULT,
        REPORT,
        STANDARD,
        Path(__file__),
    ]
    atomic_json(
        FINAL_HASHES,
        {
            "status": "FROZEN_STOP_P4GT1_REPEATABILITY_INSUFFICIENT",
            "artifacts": {
                str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in tracked
            },
        },
    )
    return result


if __name__ == "__main__":
    print(json.dumps(finalize(), indent=2, sort_keys=True))
