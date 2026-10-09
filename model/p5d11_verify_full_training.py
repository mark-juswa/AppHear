"""Verify P5-D11 EC_P3 full-run completion without scientific evaluation."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from model import p5d11_exposure_controlled_p3 as d11


def main() -> int:
    rows: list[dict[str, Any]] = []
    contract_sha = d11.sha256(d11.OUT / "p5d11_preregistered_outcome_contract.json")
    for seed in d11.SEEDS:
        directory = d11.run_directory(seed)
        state_path = directory / "run_state.json"
        run_contract_path = directory / "run_contract.json"
        checkpoint = directory / "best.keras"
        history_path = directory / "history.csv"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
        contract = json.loads(run_contract_path.read_text(encoding="utf-8")) if run_contract_path.is_file() else {}
        history = []
        if history_path.is_file():
            with history_path.open("r", encoding="utf-8-sig", newline="") as handle:
                history = list(csv.DictReader(handle))
        expected_schedule = json.loads((d11.OUT / f"p5d11_seed{seed}_schedule_hash.json").read_text(encoding="utf-8"))
        nlls = [float(row["validation_clip_nll"]) for row in history]
        minimum = min(nlls) if nlls else float("inf")
        earliest = int(next(row["optimizer_updates"] for row in history if float(row["validation_clip_nll"]) == minimum)) if history else -1
        checks = {
            "state_complete": state.get("status") == "COMPLETE",
            "updates_exact": int(state.get("completed_updates", -1)) == d11.UPDATES,
            "optimizer_iterations_exact": int(state.get("optimizer_iterations", -1)) == d11.UPDATES,
            "validation_opportunities_exact": int(state.get("validation_opportunities", -1)) == 100 and len(history) == 100,
            "schedule_hash_exact": contract.get("schedule_sha256") == expected_schedule["schedule_file_sha256"] == d11.sha256(d11.OUT / "schedules" / f"seed_{seed}_schedule.npz"),
            "initialization_exact": contract.get("initialization_tensor_sha256") == d11.EXPECTED_INITIALIZATIONS[seed],
            "model_objective_exact": contract.get("objective") == "PFCE_MATCHED" and contract.get("intervention") == "EC_P3",
            "outcome_contract_exact": contract.get("outcome_contract_sha256") == contract_sha,
            "checkpoint_present": checkpoint.is_file(),
            "checkpoint_hash_exact": checkpoint.is_file() and state.get("checkpoint_sha256") == d11.sha256(checkpoint),
            "best_nll_exact": bool(history) and abs(float(state.get("best_validation_clip_nll", float("nan"))) - minimum) <= 1e-12,
            "earliest_best_retained": int(state.get("selected_optimizer_update", -1)) == earliest,
            "test_access_prohibited": contract.get("test_access") == "PROHIBITED",
        }
        rows.append({"seed": seed, **checks, "passed": all(checks.values())})
    passed = len(rows) == 3 and all(row["passed"] for row in rows)
    result = {
        "passed": passed, "expected_runs": 3, "verified_runs": sum(row["passed"] for row in rows),
        "rows": rows, "scientific_conclusion_calculated": False, "test_accessed": False,
        "next_gate": "P5D11B_EXPOSURE_CONTROLLED_RESULT_AUDIT" if passed else "COMPLETE_OR_REPAIR_RUNS_ONLY",
    }
    d11.write_json(d11.OUT / "p5d11_full_training_verification.json", result)
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
