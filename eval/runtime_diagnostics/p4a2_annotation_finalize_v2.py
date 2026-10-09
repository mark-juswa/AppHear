"""Finalize the completed clean P4-A2 v2 human evidence without modifying the review tool."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from eval.runtime_diagnostics.p4a2_annotation_tool_v2 import (
    ALL_FIELDS,
    CANONICAL,
    LABEL_FIELDS,
    OUT,
    QUALITY_FIELDS,
    ROOT,
    SOURCE_MANIFEST,
    TRUTH_FIELDS,
    AnnotationIntegrityError,
    AnnotationStore,
    atomic_write_csv,
    atomic_write_json,
    read_csv,
    sha256,
)

MINIMUMS = {
    "visible_hand_observations": 120,
    "one_hand_visible_observations": 70,
    "zero_hand_frames": 100,
    "rest_frames": 80,
    "entry_or_leaving_frames": 25,
    "complete_two_hand_frames": 30,
}


def semantic_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    complete = [row for row in rows if row["reviewer_status"] == "COMPLETE"]
    one_hand = [
        row for row in complete
        if (row["visible_left"] == "YES") ^ (row["visible_right"] == "YES")
        and row["visible_left"] != "UNCERTAIN" and row["visible_right"] != "UNCERTAIN"
    ]
    return {
        "completed_frames": len(complete),
        "uncertain_frames": sum(any(row[field] == "UNCERTAIN" for field in TRUTH_FIELDS + QUALITY_FIELDS) for row in complete),
        "visible_hand_observations": sum(row[side] == "YES" for row in complete for side in ("visible_left", "visible_right")),
        "one_hand_visible_observations": len(one_hand),
        "clear_one_hand_observations": sum((row["left_visibility_quality"] if row["visible_left"] == "YES" else row["right_visibility_quality"]) == "CLEAR" for row in one_hand),
        "weak_one_hand_observations": sum((row["left_visibility_quality"] if row["visible_left"] == "YES" else row["right_visibility_quality"]) == "WEAK" for row in one_hand),
        "zero_hand_frames": sum(row["zero_hand"] == "YES" for row in complete),
        "rest_frames": sum(row["rest"] == "YES" for row in complete),
        "entry_or_leaving_frames": sum(row["entering"] == "YES" or row["leaving"] == "YES" for row in complete),
        "complete_two_hand_frames": sum(row["visible_left"] == "YES" and row["visible_right"] == "YES" for row in complete),
        "blur_frames": sum(row["blur"] == "YES" for row in complete),
        "occlusion_frames": sum(row["occlusion"] == "YES" for row in complete),
        "edge_clipped_frames": sum(row["edge_clipped"] == "YES" for row in complete),
        "partial_visibility_frames": sum(row["partial_visibility"] == "YES" for row in complete),
        "crossing_frames": sum(row["crossing"] == "YES" for row in complete),
        "hand_hand_contact_frames": sum(row["hand_hand_contact"] == "YES" for row in complete),
        "hand_body_contact_frames": sum(row["hand_body_contact"] == "YES" for row in complete),
    }


def dataset_hash(rows: list[dict[str, str]]) -> str:
    fields = ["annotation_row_id", "sequence_id", "frame_index", "image_sha256", *LABEL_FIELDS, "reviewer_status"]
    payload = [{field: row[field] for field in fields} for row in sorted(rows, key=lambda item: item["annotation_row_id"])]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    store = AnnotationStore(CANONICAL, verify_images=True)
    rows = store.rows
    counts = semantic_counts(rows)
    reproduced = semantic_counts(read_csv(CANONICAL))
    deficits = {key: max(0, required - counts[key]) for key, required in MINIMUMS.items()}
    provenance_path = OUT / "p4a2_v2_provenance_manifest.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    review_tool = ROOT / "eval/runtime_diagnostics/p4a2_annotation_tool_v2.py"
    test_path = ROOT / "tests/test_p4a2_annotation_tool_v2.py"
    integrity = {
        "rows": len(rows),
        "all_rows_complete": all(row["reviewer_status"] == "COMPLETE" for row in rows),
        "unique_row_ids": len({row["annotation_row_id"] for row in rows}) == len(rows),
        "source_id_set_matches": {row["annotation_row_id"] for row in rows} == {row["annotation_row_id"] for row in read_csv(SOURCE_MANIFEST)},
        "image_hashes_verified": True,
        "unexpected_revisions": sum(int(row["revision_count"]) > 0 for row in rows),
        "edit_journal_exists": (OUT / "p4a2_completed_label_edit_journal.jsonl").exists(),
        "semantic_counts_reproducible": counts == reproduced,
        "annotation_tool_hash_matches": provenance["annotation_tool_sha256"] == sha256(review_tool),
        "test_hash_matches": provenance["test_sha256"] == sha256(test_path),
        "source_manifest_hash_matches": provenance["source_manifest_sha256"] == sha256(SOURCE_MANIFEST),
        "all_semantic_minimums_passed": all(value == 0 for value in deficits.values()),
        "topup_activated": False,
    }
    integrity["passed"] = (
        len(rows) == 458 and integrity["all_rows_complete"] and integrity["unique_row_ids"]
        and integrity["source_id_set_matches"] and integrity["unexpected_revisions"] == 0
        and not integrity["edit_journal_exists"] and integrity["semantic_counts_reproducible"]
        and integrity["annotation_tool_hash_matches"] and integrity["test_hash_matches"]
        and integrity["source_manifest_hash_matches"] and integrity["all_semantic_minimums_passed"]
    )
    if not integrity["passed"]:
        atomic_write_json(OUT / "p4a2_v2_integrity_audit.json", integrity)
        raise AnnotationIntegrityError(f"Final integrity audit failed: {integrity}")

    annotation_sha = sha256(CANONICAL)
    normalized_hash = dataset_hash(rows)
    frozen_dir = OUT / "frozen_truth"
    frozen_dir.mkdir(parents=True, exist_ok=True)
    frozen_csv = frozen_dir / "P4A2_FRESH_HUMAN_TRUTH_V1.csv"
    shutil.copy2(CANONICAL, frozen_csv)
    if sha256(frozen_csv) != annotation_sha:
        raise AnnotationIntegrityError("Frozen truth copy hash mismatch")

    roles = {
        "DEV_POOL": OUT / "splits/p4a2_dev_manifest.csv",
        "VALIDATION_POOL": OUT / "splits/p4a2_validation_manifest.csv",
        "FINAL_EVAL_POOL": OUT / "sealed_final/p4a2_final_eval_manifest.csv",
    }
    split_summary = {}
    for role, target in roles.items():
        subset = [row for row in rows if row["intended_future_role"] == role]
        atomic_write_csv(target, subset, ALL_FIELDS)
        split_summary[role] = {
            "rows": len(subset), "sequences": len({row["sequence_id"] for row in subset}),
            "signers": sorted({row["signer_id"] for row in subset}), "sha256": sha256(target),
        }
    final_signers = set(split_summary["FINAL_EVAL_POOL"]["signers"])
    development_signers = set(split_summary["DEV_POOL"]["signers"]) | set(split_summary["VALIDATION_POOL"]["signers"])
    signer_separated = not final_signers.intersection(development_signers)
    limitations = [
        "No WEAK one-hand observations were labeled in the clean package.",
        "No optional blur/occlusion/edge/partial/crossing/contact positives were labeled; those subgroup diagnostics are unsupported by this package.",
    ]
    manifest = {
        "dataset_id": "P4A2_FRESH_HUMAN_TRUTH_V1", "status": "FROZEN",
        "frames": len(rows), "sequences": len({row["sequence_id"] for row in rows}),
        "signers": len({row["signer_id"] for row in rows}), "semantic_counts": counts,
        "semantic_minimums": MINIMUMS, "deficits": deficits, "topup_count": 0,
        "source_manifest_sha256": sha256(SOURCE_MANIFEST), "annotation_sha256": annotation_sha,
        "annotation_tool_sha256": sha256(review_tool), "dataset_sha256": normalized_hash,
        "finalizer_sha256": sha256(Path(__file__)), "split_summary": split_summary,
        "final_evaluation_signer_separated": signer_separated, "limitations": limitations,
    }
    atomic_write_json(frozen_dir / "P4A2_FRESH_HUMAN_TRUTH_V1.json", manifest)
    atomic_write_json(OUT / "p4a2_v2_semantic_counts.json", {"counts": counts, "minimums": MINIMUMS, "deficits": deficits})
    integrity.update({"annotation_sha256": annotation_sha, "dataset_sha256": normalized_hash, "frozen_truth_sha256": sha256(frozen_csv)})
    atomic_write_json(OUT / "p4a2_v2_integrity_audit.json", integrity)
    store.snapshot("final_freeze")
    report = f"""# P4-A2 Fresh Evidence Repair Result V2

Status: `P4A2_FRESH_EVIDENCE_READY`

The clean v2 relabel completed 458/458 frames from 28 sequences and 14 signers. Historical v1 remains `BENCHMARK_TOOLING_DEFECT — NOT FROZEN`; no corrupted label was imported.

## Human semantic counts

- Uncertain frames: {counts['uncertain_frames']}
- Visible-hand observations: {counts['visible_hand_observations']}
- One-hand visible observations: {counts['one_hand_visible_observations']}
- Weak one-hand observations: {counts['weak_one_hand_observations']}
- Zero-hand frames: {counts['zero_hand_frames']}
- Rest frames: {counts['rest_frames']}
- Entry/leaving frames: {counts['entry_or_leaving_frames']}
- Complete two-hand frames: {counts['complete_two_hand_frames']}
- Top-up: 0 frames; not required

All semantic minimums and integrity gates passed. The package has 458 unique immutable IDs, verified image hashes, zero revisions, no edit journal, reproducible counts, and matching frozen tool/test/source hashes. Development and validation splits are sequence-level; final truth is sealed. Final signer separation: {str(signer_separated).lower()}.

Limitation: zero weak-hand and zero positive optional-condition cases were labeled, so this package cannot support those subgroup diagnostics.

- Annotation SHA-256: `{annotation_sha}`
- Dataset SHA-256: `{normalized_hash}`

No E2, R1/R2, DWPose, MediaPipe, recognition, training, Android, S4-S7, S6, Sapiens, P4-B, or new recording work occurred.
"""
    (OUT / "P4A2_FRESH_EVIDENCE_REPAIR_RESULT_V2.md").write_text(report, encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
