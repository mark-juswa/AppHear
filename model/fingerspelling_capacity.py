"""One opt-in wider TCN; frozen B2 feature, convolution and training math reused."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from model import fingerspelling_baseline2 as b2
from model import fingerspelling_ctc as reference
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.sequence_manifest import REPO

CONFIG = REPO / "model/config/fingerspelling_ctc_baseline_04.json"
EVIDENCE = REPO / "artifacts/fingerspelling_baseline4"
GATE_RUN = REPO / "runs/fingerspelling_ctc_baseline_04_fit_gate"


def policy() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    cfg = json.loads(CONFIG.read_text())
    p, base = b2.policy()
    if (
        cfg["schema_version"] != "apphear.fingerspelling.baseline4.v1"
        or cfg["baseline2_policy_sha256"] != sha256(b2.POLICY_PATH)
        or cfg["adapter_version"] != base["adapter_version"]
        or cfg["feature_width"] != 405
        or cfg["candidate_channels"] != 128
        or cfg["control_channels"] != base["channels"]
        or cfg["fit_epochs"] != 60
        or cfg["fit_decision_epochs"] != [45, 60]
        or cfg["fit_evaluate_every"] != 15
        or cfg["fit_minimum_combined_cer_improvement"] != 0.05
        or sha256(REPO / cfg["diagnostic_manifest"]) != cfg["diagnostic_manifest_sha256"]
    ):
        raise ValueError("[baseline4/config] Frozen design identity mismatch")
    return cfg, p, base


def diagnostic_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cfg, _, _ = policy()
    ids = json.loads((REPO / cfg["diagnostic_manifest"]).read_text())["sample_ids"]
    by_id = {r["sample_id"]: r for r in rows}
    chosen = [by_id[sid] for sid in ids]
    if len(chosen) != 64 or len(set(ids)) != 64 or any(r["split_role"] != "TRAIN" for r in chosen):
        raise ValueError("[baseline4/data] Fixed governed TRAIN64 required")
    return chosen


def build_model(tf: Any, arm: str = "candidate") -> Any:
    cfg, _, base = policy()
    if arm not in {"candidate", "control"}:
        raise ValueError("[baseline4/model] Unknown arm")
    base = {**base, "channels": cfg[f"{arm}_channels"]}
    model = reference.build_model(tf, base)
    if model.count_params() != cfg[f"{arm}_parameters"]:
        raise ValueError("[baseline4/model] Parameter identity mismatch")
    return model


def code_identity() -> dict[str, str]:
    paths = [
        "model/fingerspelling_capacity.py",
        "model/fingerspelling_capacity_gate.py",
        "tools/fingerspelling/baseline3_analysis.py",
        "pipeline/fingerspelling/adapter.py",
    ]
    return {**b2.code_identity(), **{p: sha256(REPO / p) for p in paths}}


def safe_gate(run: Path) -> None:
    if run.resolve() != GATE_RUN.resolve():
        raise ValueError("[baseline4/gate] Only dedicated gate directory is permitted")
