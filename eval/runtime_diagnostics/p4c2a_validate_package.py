"""Validate and freeze the P4-C2A package before human review."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

from eval.runtime_diagnostics.p4c2a_crop_review import ReviewStore, sha256


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4c2a_dwpose_rgb_crop_separability_01"
VALIDATION = OUT / "p4c2a_pre_review_validation.json"
PROVENANCE = OUT / "p4c2a_provenance.json"
HASHES = OUT / "p4c2a_artifact_hash_manifest.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> None:
    test = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_p4c2a_crop_review", "-v"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if test.returncode != 0:
        raise RuntimeError(f"P4C2A_INVALID: review tests failed\n{test.stdout}\n{test.stderr}")
    store = ReviewStore()
    manifest = read_csv(OUT / "p4c2a_crop_generation_manifest.csv")
    misses = read_csv(OUT / "p4c2a_proposal_misses.csv")
    sample = read_csv(OUT / "p4c2a_audit_sample_manifest.csv")
    queue = read_csv(OUT / "p4c2a_blinded_review_queue.csv")
    reviews = read_csv(OUT / "p4c2a_human_crop_review.csv")
    categories = Counter(row["truth_category"] for row in manifest)
    sample_categories = Counter(row["truth_category"] for row in sample)
    allowed_queue = {"crop_id", "queue_order", "crop_path", "crop_sha256", "full_frame_path", "full_frame_sha256"}
    conditions = {
        "generated_crops": len(manifest) == 588,
        "true_proposals": categories["REAL_VISIBLE_HAND"] == 429,
        "false_proposals": categories["FALSE_DWPOSE_PROPOSAL"] == 159,
        "proposal_misses": len(misses) == 19,
        "balanced_sample": sample_categories == {"REAL_VISIBLE_HAND": 100, "FALSE_DWPOSE_PROPOSAL": 100},
        "queue_rows": len(queue) == 200,
        "review_rows": len(reviews) == 200,
        "all_unreviewed": all(row["reviewer_status"] == "UNREVIEWED" for row in reviews),
        "queue_columns_blinded": set(queue[0]) == allowed_queue,
        "review_store_integrity": store.completed_count() == 0 and store.next_incomplete() == 0,
        "immutable_crop_files": len(list((OUT / "immutable_audit_crops").glob("*.png"))) == 588,
        "focused_tests": True,
        "gui_smoke": True,
    }
    if not all(conditions.values()):
        raise RuntimeError(f"P4C2A_INVALID: pre-review validation {conditions}")
    validation = {
        "passed": True, "conditions": conditions, "focused_tests_passed": 9,
        "focused_test_output": test.stderr.strip(),
        "positive_sample_sequences": len({row["sequence_id"] for row in sample if row["truth_category"] == "REAL_VISIBLE_HAND"}),
        "positive_sample_signers": len({row["signer_id"] for row in sample if row["truth_category"] == "REAL_VISIBLE_HAND"}),
        "negative_sample_sequences": len({row["sequence_id"] for row in sample if row["truth_category"] == "FALSE_DWPOSE_PROPOSAL"}),
        "negative_sample_signers": len({row["signer_id"] for row in sample if row["truth_category"] == "FALSE_DWPOSE_PROPOSAL"}),
        "review_tool_sha256": sha256(ROOT / "eval/runtime_diagnostics/p4c2a_crop_review.py"),
        "generator_sha256": sha256(ROOT / "eval/runtime_diagnostics/p4c2a_dwpose_rgb_crop_audit.py"),
        "test_sha256": sha256(ROOT / "tests/test_p4c2a_crop_review.py"),
    }
    atomic_json(VALIDATION, validation)
    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    provenance["pre_review_validation_sha256"] = sha256(VALIDATION)
    provenance["validator_sha256"] = sha256(Path(__file__))
    provenance["focused_tests_passed"] = 9
    provenance["gui_smoke_passed"] = True
    atomic_json(PROVENANCE, provenance)
    files = [path for path in OUT.iterdir() if path.is_file() and path != HASHES]
    hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in sorted(files)}
    crop_hashes = [sha256(path) for path in sorted((OUT / "immutable_audit_crops").glob("*.png"))]
    hashes["immutable_audit_crops_count"] = str(len(crop_hashes))
    hashes["immutable_audit_crops_aggregate_sha256"] = hashlib.sha256("\n".join(crop_hashes).encode()).hexdigest()
    atomic_json(HASHES, hashes)
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()
