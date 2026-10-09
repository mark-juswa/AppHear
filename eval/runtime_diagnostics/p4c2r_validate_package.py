"""Independent pre-review validation for the frozen P4-C2R R1 package."""

from __future__ import annotations

import json
import subprocess
import sys
import tkinter as tk
from collections import Counter
from pathlib import Path

from eval.runtime_diagnostics.p4c2r_truth_review import (
    ALL_FIELDS,
    BLINDING,
    HASH_MANIFEST,
    OUT,
    QUEUE,
    REVIEW,
    ROOT,
    SELECTION,
    ReviewApp,
    ReviewStore,
    atomic_json,
    read_csv,
    sha256,
    verify_r0,
)


def main() -> None:
    verify_r0()
    queue = read_csv(QUEUE)
    review = read_csv(REVIEW)
    selection = read_csv(SELECTION)
    queue_fields = list(queue[0])
    expected_queue_fields = [
        "review_row_id",
        "source_annotation_row_id",
        "sequence_id",
        "frame_index",
        "image_sha256",
        "image_path",
        "queue_order",
    ]
    categories = Counter(row["selection_category"] for row in selection)
    conditions = {
        "rows_148": len(queue) == len(review) == len(selection) == 148,
        "unique_ids": len({row["review_row_id"] for row in queue}) == 148,
        "queue_columns_blinded": queue_fields == expected_queue_fields,
        "all_unreviewed": all(row["reviewer_status"] == "UNREVIEWED" for row in review),
        "review_schema_exact": list(review[0]) == ALL_FIELDS,
        "selection_counts": categories
        == {
            "KNOWN_ZERO_HAND_DISCREPANCY": 8,
            "OPPOSITE_SLOT_CASE": 23,
            "VISIBLE_PROPOSAL_MISS": 17,
            "QA_ZERO_HAND": 40,
            "QA_ONE_HAND": 40,
            "QA_TWO_HAND": 20,
        },
        "id_sets_match": {row["review_row_id"] for row in queue}
        == {row["review_row_id"] for row in review}
        == {row["review_row_id"] for row in selection},
        "source_images_valid": True,
        "review_store_valid": True,
        "blinding_frozen": json.loads(BLINDING.read_text(encoding="utf-8"))["status"]
        == "FROZEN_BEFORE_REVIEW",
    }
    ReviewStore()
    tests = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_p4c2r_truth_review.py", "-q"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    test_file = ROOT / "tests/test_p4c2r_truth_review.py"
    test_count = sum(
        line.startswith("def test_") for line in test_file.read_text(encoding="utf-8").splitlines()
    )
    conditions["focused_tests_10"] = tests.returncode == 0 and test_count == 10
    root = tk.Tk()
    root.withdraw()
    app = ReviewApp(root, ReviewStore())
    app.root.destroy()
    conditions["gui_construction_smoke"] = True
    if not all(conditions.values()):
        raise RuntimeError(f"P4C2R_PACKAGE_INVALID: {conditions}")
    result = {
        "status": "P4C2R_R1_PACKAGE_VALID",
        "conditions": conditions,
        "queue_sha256": sha256(QUEUE),
        "review_sha256": sha256(REVIEW),
        "selection_sha256": sha256(SELECTION),
        "test_output": tests.stdout.strip(),
    }
    validation_path = OUT / "p4c2r_pre_review_validation.json"
    atomic_json(validation_path, result)
    tracked = [
        QUEUE,
        REVIEW,
        SELECTION,
        OUT / "p4c2r_r0_source_evidence_manifest.json",
        BLINDING,
        OUT / "p4c2r_truth_review_protocol.json",
        OUT / "p4c2r_prepare_result.json",
        OUT / "P4C2R_PROPOSAL_OWNERSHIP_TRUTH_REPAIR_RESULT.md",
        validation_path,
        ROOT / "eval/runtime_diagnostics/p4c2r_truth_review.py",
        Path(__file__),
        test_file,
        ROOT / "model/config/recognition_upgrade/run_p4c2r_truth_review.ps1",
    ]
    atomic_json(
        HASH_MANIFEST,
        {
            "status": "FROZEN_AND_VALIDATED_BEFORE_HUMAN_REVIEW",
            "artifacts": {
                str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in tracked
            },
        },
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
