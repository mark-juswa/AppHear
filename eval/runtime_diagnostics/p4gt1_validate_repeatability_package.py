"""Independent validation of the frozen P4-GT1 repeatability package."""

from __future__ import annotations

import json
import subprocess
import sys
import tkinter as tk
from collections import Counter

from eval.runtime_diagnostics.p4c2r_truth_review import atomic_json, read_csv, sha256
from eval.runtime_diagnostics.p4gt1_pass1_review import C2R_REVIEW, ROOT, STANDARD
from eval.runtime_diagnostics.p4gt1_repeatability_review import (
    BLINDING,
    HASH_MANIFEST,
    OUT,
    PASS1_FULL,
    PASS1_REPORT_SNAPSHOT,
    PASS1_REVIEW,
    PREPARE_RESULT,
    PROVENANCE,
    QUEUE,
    REPORT,
    REVIEW,
    SAMPLE,
    RepeatabilityApp,
    RepeatabilityStore,
    verify_completed_pass1,
)


def main() -> None:
    truth, c2r = verify_completed_pass1()
    full = read_csv(PASS1_FULL)
    sample = read_csv(SAMPLE)
    queue = read_csv(QUEUE)
    review = read_csv(REVIEW)
    sample_states = Counter(row["pass1_stratum"] for row in sample)
    sample_sources = Counter(row["pass1_source"] for row in sample)
    conditions = {
        "completed_pass1_inputs_verified": len(truth) == 458 and len(c2r) == 148,
        "pass1_full_458_unique": len(full) == 458 and len({row["frame_id"] for row in full}) == 458,
        "sample_100_unique": len(sample) == 100 and len({row["frame_id"] for row in sample}) == 100,
        "sample_strata": sample_states == {"ZERO": 40, "ONE": 40, "TWO": 20},
        "sample_sources": sample_sources == {"REUSED_P4C2R_148": 34, "NEW_P4GT1_310": 66},
        "sample_excludes_uncertain": all(row["pass1_stratum"] != "UNCERTAIN" for row in sample),
        "queue_review_100": len(queue) == len(review) == 100,
        "queue_ids_unique": len({row["review_row_id"] for row in queue}) == 100,
        "queue_review_ids_match": {row["review_row_id"] for row in queue}
        == {row["review_row_id"] for row in review},
        "all_repeat_rows_unreviewed": all(row["reviewer_status"] == "UNREVIEWED" for row in review),
        "blinding_frozen": json.loads(BLINDING.read_text(encoding="utf-8"))["status"]
        == "FROZEN_BEFORE_REPEATABILITY_REVIEW",
        "standard_preserved": STANDARD.is_file(),
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
    app = RepeatabilityApp(root, RepeatabilityStore())
    app.root.destroy()
    conditions["gui_construction_smoke"] = True
    if not all(conditions.values()):
        raise RuntimeError(f"P4GT1_REPEATABILITY_PACKAGE_INVALID: {conditions}")
    result = {
        "status": "P4GT1_REPEATABILITY_PACKAGE_VALID",
        "conditions": conditions,
        "pass1_full_sha256": sha256(PASS1_FULL),
        "sample_sha256": sha256(SAMPLE),
        "queue_sha256": sha256(QUEUE),
        "review_sha256": sha256(REVIEW),
        "test_output": tests.stdout.strip(),
    }
    validation = OUT / "p4gt1_repeatability_pre_review_validation.json"
    atomic_json(validation, result)
    tracked = [
        STANDARD,
        C2R_REVIEW,
        PASS1_REVIEW,
        PASS1_FULL,
        SAMPLE,
        QUEUE,
        REVIEW,
        BLINDING,
        PROVENANCE,
        PREPARE_RESULT,
        REPORT,
        PASS1_REPORT_SNAPSHOT,
        validation,
        ROOT / "eval/runtime_diagnostics/p4gt1_repeatability_review.py",
        ROOT / "eval/runtime_diagnostics/p4gt1_validate_repeatability_package.py",
        ROOT / "tests/test_p4c2r_truth_review.py",
        ROOT / "tests/test_p4gt1_pass1_review.py",
        ROOT / "model/config/recognition_upgrade/run_p4gt1_repeatability_review.ps1",
    ]
    atomic_json(
        HASH_MANIFEST,
        {
            "status": "FROZEN_AND_VALIDATED_BEFORE_REPEATABILITY_REVIEW",
            "artifacts": {
                str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in tracked
            },
        },
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
