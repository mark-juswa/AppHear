"""Arm P (Arm A recipe + reviewed phone sessions) scored leave-one-session-out on the phone.

For each fold the model trained WITHOUT session S is replayed on S only (BASELINE and
CONFIRM_BOUNDARY_70 decoders, frozen WORD displayed, v2 shadow); the folds are summed so every
reviewed phone session is scored by a model that never saw it. Arm A e10 (trained on none of
them) is scored on the same sessions for the paired comparison. Epoch per fold: the same
pre-registered CAL-only diagnostic fallback rule that selected Arm A e10 (lowest CAL non-sign
ACTIVE rate with CAL later-sign acquisition >= 0.8); epoch 10 is reported alongside.
The all-session model (no hold-out) is scored only on SHADOW_022535Z (protocol labels), which no
model trained on. Writes arm_p_loso.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics import event_reliability as er  # noqa: E402
from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
HERE = Path(__file__).parent
CONFIG = REPO / "model/config/recognition_upgrade/s2_r3_train_03.json"
DECODERS = ("BASELINE", "CONFIRM_BOUNDARY_70")


def package(run: Path, epoch: int, name: str) -> suite.Package:
    return suite.load_package(
        name, "v1", run / f"epoch_{epoch:02d}.keras", run / "normalization.json"
    )


def score(ledger: dict[str, Any]) -> dict[str, Any]:
    tier2 = er.summarize_phone(ledger)
    v2 = er.summarize_phone(ledger, key="v2")
    out = {}
    for part in ("tier2", "shadow_023004Z"):
        if part in tier2:
            out[part] = {**tier2[part], "v2_correct_words": v2[part]["correct_words"]}
    out["protocol"] = tier2["protocol"]
    return out


def add(total: dict[str, Any], part: dict[str, Any]) -> None:
    for k, v in part.items():
        if isinstance(v, dict):
            add(total.setdefault(k, {}), v)
        else:
            total[k] = total.get(k, 0) + v


def main() -> None:
    config = suite.read_json(CONFIG)
    base = E / config["output"]
    folds = config["phone_reviewed_fit"]["sessions"]
    sessions = er.phone_sessions(E)
    frozen = er.Word(E, er.FROZEN_WORD, er.FROZEN_WORD_SHA)
    shadow = er.Word(E, er.V2_WORD)
    arm_a = er.load_s2(E, "ARM_A_E10")
    result: dict[str, Any] = {"folds": {}, "totals": {}}
    for fold in folds:
        run = base / f"holdout_{fold}"
        if not (run / "training_result.json").exists():
            print(fold, "not trained yet; skipped", flush=True)
            continue
        training = suite.read_json(run / "training_result.json")
        chosen = training["diagnostic_fallback_epoch"] or training["best_epoch"] or 10
        held = {fold: sessions[fold]}
        fold_out: dict[str, Any] = {
            "selected_epoch": chosen,
            "cal": training["epochs"][chosen - 1]["cal"],
        }
        for label, pkg in (
            ("ARM_A_E10", arm_a),
            ("ARM_P_SELECTED", package(run, chosen, f"ARM_P_{fold}_E{chosen}")),
            ("ARM_P_E10", package(run, 10, f"ARM_P_{fold}_E10")),
        ):
            for dec in DECODERS:
                ledger = er.phone_ledger(E, held, pkg, dec, frozen, shadow)
                s = score(ledger)
                fold_out[f"{label}:{dec}"] = {"summary": s, "ledger": ledger[fold]}
                add(
                    result["totals"].setdefault(f"{label}:{dec}", {}),
                    {k: v for k, v in s.items() if k != "protocol"},
                )
        result["folds"][fold] = fold_out
        print(fold, "epoch", chosen, flush=True)
    full = base
    if (full / "training_result.json").exists():
        training = suite.read_json(full / "training_result.json")
        chosen = training["diagnostic_fallback_epoch"] or training["best_epoch"] or 10
        held = {er.SHADOW_PROTOCOL: sessions[er.SHADOW_PROTOCOL]}
        result["all_sessions_model"] = {"selected_epoch": chosen}
        for label, pkg in (("ARM_A_E10", arm_a), ("ARM_P_ALL", package(full, chosen, "ARM_P_ALL"))):
            for dec in DECODERS:
                ledger = er.phone_ledger(E, held, pkg, dec, frozen, shadow)
                result["all_sessions_model"][f"{label}:{dec}"] = {
                    "protocol": er.summarize_phone(ledger)["protocol"],
                    "protocol_v2": er.summarize_phone(ledger, key="v2")["protocol"],
                    "events": ledger[er.SHADOW_PROTOCOL]["events"],
                }
    (HERE / "arm_p_loso.json").write_text(
        json.dumps(result, indent=1, default=float), encoding="utf-8"
    )
    for key, t in result["totals"].items():
        for part in ("tier2", "shadow_023004Z"):
            if part in t:
                v = t[part]
                print(
                    f"{key:32s} {part:15s} correct={v['correct_words']}/{v['genuine_signs']} "
                    f"v2={v['v2_correct_words']} nonsign={v.get('all_confirmed_nonsign', 0)} "
                    f"events={v['events']} unreviewed={v.get('all_unreviewed', 0)} "
                    f"dup={v.get('all_duplicate', 0)} merged={v['merged_events']} "
                    f"missed={v['missed_no_event']}"
                )
    for key, v in result.get("all_sessions_model", {}).items():
        if isinstance(v, dict):
            print("022535Z", key, v["protocol"], "v2", v["protocol_v2"])


if __name__ == "__main__":
    main()
