"""Independent validation for the frozen P4-GT1R six-frame adjudication package."""

from __future__ import annotations

import json
import subprocess
import sys
import tkinter as tk
from collections import Counter
from pathlib import Path

from eval.runtime_diagnostics.p4c2r_truth_review import atomic_json, read_csv, sha256
from eval.runtime_diagnostics.p4gt1_pass1_review import ROOT
from eval.runtime_diagnostics.p4gt1r_adjudication_review import (
    ANALYSIS,
    BLINDING,
    DISAGREEMENTS,
    HASH_MANIFEST,
    OUT,
    PREPARE_RESULT,
    PROVENANCE,
    QUEUE,
    REPORT,
    REVIEW,
    SCHEMA,
    AdjudicationApp,
    AdjudicationStore,
    verify_sources,
)


def main() -> None:
    verify_sources()
    analysis = read_csv(ANALYSIS)
    queue = read_csv(QUEUE)
    review = read_csv(REVIEW)
    historical = read_csv(DISAGREEMENTS)
    conflict_ids = {
        row["frame_id"] for row in historical if row["disagreement_type"] == "MATERIAL_YES_NO"
    }
    queue_ids = {row["frame_id"] for row in queue}
    classifications = Counter(row["repeatability_classification"] for row in analysis)
    conditions = {
        "analysis_100": len(analysis) == 100,
        "count_agreement_94": classifications["AGREEMENT"] == 94,
        "count_disagreements_6": classifications["COUNT_DISAGREEMENT"] == 6,
        "ownership_only_0": classifications["OWNERSHIP_ONLY_DISAGREEMENT"] == 0,
        "exact_six_historical_conflicts": len(conflict_ids) == 6 and queue_ids == conflict_ids,
        "queue_review_6": len(queue) == len(review) == 6,
        "unique_ids": len({row["adjudication_row_id"] for row in queue}) == 6,
        "all_unreviewed": all(row["reviewer_status"] == "UNREVIEWED" for row in review),
        "queue_review_match": {row["adjudication_row_id"] for row in queue}
        == {row["adjudication_row_id"] for row in review},
        "context_hashes_valid": True,
        "blinding_frozen": json.loads(BLINDING.read_text(encoding="utf-8"))["status"]
        == "FROZEN_BEFORE_SIX_FRAME_ADJUDICATION",
        "explicit_confirm_required": json.loads(BLINDING.read_text(encoding="utf-8"))[
            "explicit_confirm_required"
        ],
    }
    for row in queue:
        if not Path(row["current_image_path"]).is_file():
            conditions["context_hashes_valid"] = False
        if sha256(Path(row["current_image_path"])) != row["source_sha256"]:
            conditions["context_hashes_valid"] = False
        for prefix in ("previous", "next"):
            path = row[f"{prefix}_image_path"]
            if path and sha256(Path(path)) != row[f"{prefix}_image_sha256"]:
                conditions["context_hashes_valid"] = False
    test_paths = (
        ROOT / "tests/test_p4c2r_truth_review.py",
        ROOT / "tests/test_p4gt1_pass1_review.py",
        ROOT / "tests/test_p4gt1r_adjudication_review.py",
    )
    tests = subprocess.run(
        [sys.executable, "-m", "pytest", *[str(path) for path in test_paths], "-q"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    test_count = sum(
        line.startswith("def test_")
        for path in test_paths
        for line in path.read_text(encoding="utf-8").splitlines()
    )
    conditions["regression_tests_23"] = tests.returncode == 0 and test_count == 23
    root = tk.Tk()
    root.withdraw()
    app = AdjudicationApp(root, AdjudicationStore())
    app.root.destroy()
    conditions["gui_construction_smoke"] = True
    if not all(conditions.values()):
        raise RuntimeError(f"P4GT1R_ADJUDICATION_PACKAGE_INVALID: {conditions}")
    result = {
        "status": "P4GT1R_ADJUDICATION_PACKAGE_VALID",
        "conditions": conditions,
        "analysis_sha256": sha256(ANALYSIS),
        "queue_sha256": sha256(QUEUE),
        "review_sha256": sha256(REVIEW),
        "test_output": tests.stdout.strip(),
    }
    validation = OUT / "p4gt1r_adjudication_pre_review_validation.json"
    atomic_json(validation, result)
    tracked = [
        ANALYSIS,
        QUEUE,
        REVIEW,
        SCHEMA,
        BLINDING,
        PROVENANCE,
        PREPARE_RESULT,
        REPORT,
        validation,
        ROOT / "eval/runtime_diagnostics/p4gt1r_adjudication_review.py",
        ROOT / "eval/runtime_diagnostics/p4gt1r_validate_adjudication_package.py",
        *test_paths,
        ROOT / "model/config/recognition_upgrade/run_p4gt1r_adjudication.ps1",
    ]
    atomic_json(
        HASH_MANIFEST,
        {
            "status": "FROZEN_AND_VALIDATED_BEFORE_SIX_FRAME_ADJUDICATION",
            "artifacts": {
                str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in tracked
            },
        },
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
