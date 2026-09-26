"""Verify P5-D9 run completion without training or model inference."""
from __future__ import annotations

import json
from pathlib import Path

from model import p5d2_temporal_objective_ablation as d2


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5d9_semlex_supplementation_01"
OBJECTIVES = ("PFCE_MATCHED", "CLIPCE_AGGREGATION_ALIGNED")
SEEDS = (101, 202, 303)
MEMBERSHIP_SHA = "142a04b3b7954ea7a8c3d0f1e8036c5f5332c5f45a8ebca2676b9a2a029edde5"


def main() -> int:
    rows = []
    for seed in SEEDS:
        for objective in OBJECTIVES:
            directory = OUT / "runs" / objective / f"seed_{seed}"
            state_path = directory / "run_state.json"
            contract_path = directory / "run_contract.json"
            checkpoint = directory / "best.keras"
            row = {"objective": objective, "seed": seed, "run_directory": str(directory.resolve())}
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                contract = json.loads(contract_path.read_text(encoding="utf-8"))
                checkpoint_hash = d2.sha256(checkpoint)
                checks = {
                    "status_complete": state.get("status") == "COMPLETE",
                    "updates_exact": int(state.get("completed_updates", -1)) == 12300,
                    "optimizer_iterations_exact": int(state.get("optimizer_iterations", -1)) == 12300,
                    "validation_opportunities_exact": int(state.get("validation_opportunities", -1)) == 100,
                    "identity_exact": state.get("objective") == objective and int(state.get("seed", -1)) == seed,
                    "checkpoint_hash_exact": state.get("checkpoint_sha256") == checkpoint_hash,
                    "membership_hash_exact": contract.get("membership_sha256") == MEMBERSHIP_SHA,
                    "checkpoint_exists": checkpoint.is_file(),
                }
                row.update(checks)
                row["checkpoint_sha256"] = checkpoint_hash
                row["passed"] = all(checks.values())
            except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as error:
                row["passed"] = False
                row["error"] = f"{type(error).__name__}: {error}"
            rows.append(row)
    passed = all(row["passed"] for row in rows)
    result = {"expected_runs": 6, "verified_runs": sum(bool(row["passed"]) for row in rows), "passed": passed, "rows": rows, "training_executed_by_verifier": False, "model_inference_executed": False, "protected_test_accessed": False}
    d2.atomic_json(OUT / "p5d9_full_training_verification.json", result)
    print(json.dumps(result, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
