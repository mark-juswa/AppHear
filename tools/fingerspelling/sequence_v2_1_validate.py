"""Finalize engineering gate: same TRAIN subset, four-regime loop and exact resume."""

from __future__ import annotations

import json
import math

from model import fingerspelling_ctc as reference
from model.fingerspelling_sequence_v2_1 import (
    GATE,
    RUN,
    code_identity,
    engine,
    gate_check,
    run_identity,
)
from model.fingerspelling_sequence_v2_1_encoder import configuration
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO


def main() -> None:
    p = configuration()
    gate = json.loads((GATE / "architecture_gate.json").read_text())
    if gate["status"] != "V2_1_ENGINEERING_SMOKE_PASS":
        raise ValueError("[sequence-v2.1/validate] Passed dual-objective smoke required")
    rows = json.loads((GATE / "tiny_subset.json").read_text())["samples"]
    if len(rows) != 6 or any(r["split_role"] != "TRAIN" for r in rows):
        raise ValueError("[sequence-v2.1/validate] Frozen TRAIN-only tiny subset required")
    tf = reference.tensorflow(p)
    root = RUN.with_name(RUN.name + "_smoke_execution")
    if (root / 'completion.json').exists():
        saved_identity = json.loads((root / 'run_identity.json').read_text())
        if saved_identity != run_identity(rows, True):
            raise ValueError('[sequence-v2.1/validate] Engineering identity changed')
        second = json.loads((root / 'completion.json').read_text())
    else:
        if root.exists() and any(root.iterdir()):
            raise ValueError('[sequence-v2.1/validate] Incomplete engineering run retained')
        first = engine(root, rows, tf, smoke=True, stop_after=2)
        assert first['status'] == 'ENGINEERING_PAUSE'
        second = engine(root, rows, tf, smoke=True)
    restored = json.loads((root / "resume_verification.json").read_text())
    assert restored["restored_epoch"] == 2 and restored["optimizer_iterations"] == 2
    assert restored["model_optimizer_exactly_restored"]
    assert second["status"] == "V2_1_ENGINEERING_SMOKE_COMPLETE" and second["epoch"] == 4
    assert second["optimizer_iterations"] == 4
    history = [
        json.loads((root / "epochs" / f"epoch_{i:03d}.json").read_text()) for i in range(1, 5)
    ]
    for row in history:
        assert row["evaluation_cohort"] == "TRAIN_ENGINEERING_PROXY"
        assert len(row["temporal_choices"]) == 6 and not row["dev_b_inference"]
        expected = (
            row["views"]["native"]["metrics"]["cer"]
            + row["views"]["phone"]["metrics"]["cer"]
            + row["views"]["native"]["no_space_metrics"]["cer"]
            + row["views"]["phone"]["no_space_metrics"]["cer"]
        ) / 4
        assert math.isclose(expected, row['combined_raw_greedy_selection_cer'], abs_tol=1e-15)
    inventory = json.loads((GATE / "preservation_before.json").read_text())
    changed = [name for name, info in inventory.items() if sha256(REPO / name) != info["sha256"]]
    assert not changed, changed
    verification = dict(
        status="V2_1_EXECUTION_RESUME_PASS",
        pause_epoch=2,
        final_epoch=4,
        optimizer_restore_exact=True,
        all_four_regimes=True,
        dev_accessed=False,
        test_accessed=False,
        protected_files=len(inventory),
        protected_changed=[],
        code_sha256=code_identity(),
    )
    write_json_atomic(GATE / "execution_validation.json", verification)
    gate["code_sha256_at_original_overfit_smoke"] = gate["code_sha256"]
    gate["code_sha256"] = code_identity()
    gate["finalized_code_execution_resume_validated"] = True
    write_json_atomic(GATE / "architecture_gate.json", gate)
    gate_check()
    print(json.dumps(verification, indent=2), flush=True)


if __name__ == "__main__":
    main()
