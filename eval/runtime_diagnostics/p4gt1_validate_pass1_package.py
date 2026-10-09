"""Independent validation for the frozen P4-GT1 remaining Pass-1 package."""

from __future__ import annotations

import json
import subprocess
import sys
import tkinter as tk

from eval.runtime_diagnostics.p4c2r_truth_review import atomic_json, read_csv, sha256
from eval.runtime_diagnostics.p4gt1_pass1_review import (
    BLINDING,
    C2R_REVIEW,
    HASH_MANIFEST,
    OUT,
    PREPARE_RESULT,
    PROVENANCE,
    QUEUE,
    REPORT,
    REUSED,
    REVIEW,
    ROOT,
    STANDARD,
    GT1Store,
    ReviewApp,
    verify_sources,
)


def main() -> None:
    truth, prior = verify_sources()
    queue = read_csv(QUEUE)
    review = read_csv(REVIEW)
    reused = read_csv(REUSED)
    source_ids = {row["annotation_row_id"] for row in truth}
    reused_ids = {row["annotation_row_id"] for row in reused}
    queue_ids = {row["source_annotation_row_id"] for row in queue}
    conditions = {
        "v1_and_c2r_sources_verified": len(truth) == 458 and len(prior) == 148,
        "reused_148": len(reused) == len(reused_ids) == 148,
        "remaining_310": len(queue) == len(review) == len(queue_ids) == 310,
        "complete_458_exactly_once": reused_ids.isdisjoint(queue_ids)
        and reused_ids | queue_ids == source_ids,
        "queue_unique_review_ids": len({row["review_row_id"] for row in queue}) == 310,
        "all_new_rows_unreviewed": all(row["reviewer_status"] == "UNREVIEWED" for row in review),
        "queue_review_identity_match": {row["review_row_id"] for row in queue}
        == {row["review_row_id"] for row in review},
        "standard_frozen": STANDARD.is_file(),
        "blinding_frozen": json.loads(BLINDING.read_text(encoding="utf-8"))["status"]
        == "FROZEN_BEFORE_REMAINING_PASS1_REVIEW",
        "c2r_review_preserved": sha256(C2R_REVIEW)
        == "e1c9ade5f165aa929e37813deb2c80b95405448b0583774a5d7a5ac5efc128b2",
    }
    tests = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_p4c2r_truth_review.py",
            "tests/test_p4gt1_pass1_review.py",
            "-q",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    test_count = sum(
        line.startswith("def test_")
        for path in (
            ROOT / "tests/test_p4c2r_truth_review.py",
            ROOT / "tests/test_p4gt1_pass1_review.py",
        )
        for line in path.read_text(encoding="utf-8").splitlines()
    )
    conditions["regression_tests_15"] = tests.returncode == 0 and test_count == 15
    root = tk.Tk()
    root.withdraw()
    app = ReviewApp(root, GT1Store())
    app.root.destroy()
    conditions["gui_construction_smoke"] = True
    if not all(conditions.values()):
        raise RuntimeError(f"P4GT1_PASS1_PACKAGE_INVALID: {conditions}")
    result = {
        "status": "P4GT1_PASS1_PACKAGE_VALID",
        "conditions": conditions,
        "queue_sha256": sha256(QUEUE),
        "review_sha256": sha256(REVIEW),
        "standard_sha256": sha256(STANDARD),
        "test_output": tests.stdout.strip(),
    }
    validation = OUT / "p4gt1_pass1_pre_review_validation.json"
    atomic_json(validation, result)
    tracked = [
        STANDARD,
        QUEUE,
        REVIEW,
        REUSED,
        BLINDING,
        PROVENANCE,
        PREPARE_RESULT,
        REPORT,
        validation,
        ROOT / "eval/runtime_diagnostics/p4gt1_pass1_review.py",
        ROOT / "eval/runtime_diagnostics/p4gt1_validate_pass1_package.py",
        ROOT / "tests/test_p4c2r_truth_review.py",
        ROOT / "tests/test_p4gt1_pass1_review.py",
        ROOT / "model/config/recognition_upgrade/run_p4gt1_pass1_review.ps1",
    ]
    atomic_json(
        HASH_MANIFEST,
        {
            "status": "FROZEN_AND_VALIDATED_BEFORE_REMAINING_PASS1_REVIEW",
            "artifacts": {
                str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in tracked
            },
        },
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
