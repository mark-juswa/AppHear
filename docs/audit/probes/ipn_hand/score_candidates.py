"""Score selected S2 candidates on IPN subjects by role (held-out first; never used for selection).

Candidates: S2-R2 (production), Arm A e10 (reference), Arm A IPN-selected epoch (selection-only
control), Arm B and Arm I at their pre-registered selected epochs (selection_<run>.json).
Per role (HELD_OUT_EVAL, CAL, FIT): NOG events/min, hand-visible NOG chunk fire rate, gesture
canary. Writes ipn_scores.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).parent))

import select_and_score as ss  # noqa: E402

from eval.runtime_diagnostics import event_reliability as er  # noqa: E402

HERE = Path(__file__).parent


def candidates() -> dict[str, str]:
    out = {"PRODUCTION_S2_R2": "S2_R2", "ARM_A_E10": "ARM_A_E10"}
    for run in ("ARM_A", "ARM_B", "ARM_I"):
        path = HERE / f"selection_{run}.json"
        if path.exists():
            sel = json.loads(path.read_text())
            if sel["selected_epoch"]:
                out[f"{run}_SELECTED"] = f"{run}_E{sel['selected_epoch']}"
            else:  # post-hoc diagnostic: the CAL-only part of the rule, canary dropped
                floor = sel["reference_arm_a_e10"]["cal"]["later_sign_acquisition"] - 0.03
                ok = [r for r in sel["epochs"] if r["cal"]["later_sign_acquisition"] >= floor]
                best = min(
                    ok,
                    key=lambda r: (
                        r["ipn_cal"]["nog_events_per_min"],
                        r["cal"]["nonsign_active_rate"],
                    ),
                )
                out[f"{run}_DIAGNOSTIC_NO_CANARY"] = f"{run}_E{best['epoch']}"
    return out


def main() -> None:
    cands = candidates()
    roles = {r: ss.ipn_videos(r) for r in ("HELD_OUT_EVAL", "CAL", "FIT")}
    out: dict = {"candidates": cands, "scores": {}}
    for label, name in cands.items():
        pkg = er.load_s2(ss.E, name)
        out["scores"][label] = {r: ss.ipn_metrics(pkg, v) for r, v in roles.items()}
        h = out["scores"][label]["HELD_OUT_EVAL"]
        print(
            f"{label:20s} {name:14s} held-out: nog/min={h['nog_events_per_min']:.2f} "
            f"chunk_fire={h['nog_chunk_fire']:.2f} canary={h['gesture_canary']:.2f}",
            flush=True,
        )
    (HERE / "ipn_scores.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
