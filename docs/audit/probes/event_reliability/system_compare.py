"""Complete-system comparison on the same recordings (frozen WORD displayed; v2 shadow reported).

Phone (5 reviewed sessions, development-exposed; Arm P scored leave-one-session-out) and the
protocol-only shadow session 022535Z (never trained on by any model). Held-out DEV (signer-
disjoint; stitched) and CAL streams from the stream ledgers. Writes system_compare.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
CONTINUOUS = {"SEP27_TRANSITION", "OCT15_COMPACT"}  # Tier-2 sessions without capture pauses
PHONE_CONFIGS = {
    "PRODUCTION (S2-R2, production decoder)": "S2_R2__BASELINE",
    "ARM_A_E10, production decoder": "ARM_A_E10__BASELINE",
    "ARM_A_E10 + confirm-boundary": "ARM_A_E10__CONFIRM_BOUNDARY_70",
    "ARM_A_E21 @0.8, production decoder": "ARM_A_E21_T08__BASELINE",
    # 2026-10-17 external-data milestone (selection on CAL + IPN-CAL only)
    "ARM_A_E21 (IPN-selected) + confirm-boundary": "ARM_A_E21__CONFIRM_BOUNDARY_70",
    "ARM_B_E9 (body dropout) + confirm-boundary": "ARM_B_E9__CONFIRM_BOUNDARY_70",
    "ARM_I_E28 (IPN negatives; canary failed) production decoder": "ARM_I_E28__BASELINE",
    "ARM_I_E28 (IPN negatives; canary failed) + confirm-boundary": "ARM_I_E28__CONFIRM_BOUNDARY_70",
}


def phone_row(sessions: dict[str, Any]) -> dict[str, Any]:
    r: dict[str, Any] = {
        k: 0
        for k in (
            "tier2_correct",
            "tier2_wrong",
            "tier2_missed",
            "tier2_merged_away",
            "tier2_continuous_distinct",
            "tier2_nonsign",
            "tier2_unreviewed_or_uncertain",
            "tier2_duplicates",
            "tier2_events",
            "tier2_v2_correct",
            "shadow_correct",
            "shadow_wrong",
            "shadow_nonsign",
            "shadow_unreviewed",
            "shadow_events",
            "shadow_v2_correct",
        )
    }
    for name, v in sessions.items():
        if v["kind"] == "SHADOW_PROTOCOL_ONLY":
            continue
        p = "tier2" if v["kind"] == "TIER2" else "shadow"
        for s in v["signs"]:
            if s["event"] is not None:
                r[f"{p}_correct"] += bool(s.get("frozen_correct"))
                r[f"{p}_wrong"] += not s.get("frozen_correct")
                r[f"{p}_v2_correct"] += bool(s.get("v2_correct"))
                if p == "tier2" and name in CONTINUOUS:
                    r["tier2_continuous_distinct"] += 1
            if p == "tier2":
                r["tier2_missed"] += s["events_overlapping"] == 0
                r["tier2_merged_away"] += s["merged_into_shared_event"]
        for e in v["events"]:
            r[f"{p}_events"] += 1
            r[f"{p}_nonsign"] += e["category"] == "CONFIRMED_NONSIGN"
            other = e["category"] in ("UNREVIEWED", "UNCERTAIN", "PARTIAL_NONSIGN")
            r[f"{p}_unreviewed" if p == "shadow" else "tier2_unreviewed_or_uncertain"] += other
            if p == "tier2":
                r["tier2_duplicates"] += e["category"] == "DUPLICATE"
    return r


def protocol_row(events: list[dict[str, Any]]) -> dict[str, int]:
    from eval.runtime_diagnostics.event_reliability import protocol_words

    f = protocol_words(events, "frozen_top1", lambda e: True)
    v = protocol_words(events, "v2_top1", lambda e: True)
    return {
        "expected_words": f["expected_words"],
        "ordinary_movement_words": f["ordinary_movement"],
        "other_words": f["other_in_sign_blocks"] + f["outside"],
        "v2_expected_words": v["expected_words"],
    }


def stream_row(path: Path) -> dict[str, Any]:
    d = json.loads(path.read_text())
    out: dict[str, Any] = {}
    for mode in ("NATURAL", "CONTINUOUS"):
        rows = [r for r in d["dev"] if r["mode"] == mode]
        signs = sum(v for k, v in d["dev_signs"].items() if k.startswith(mode))
        out[f"dev_{mode.lower()}"] = {
            "signs": signs,
            "correct_words": sum(
                1 for r in rows if r["category"] == "GENUINE" and r.get("frozen_correct")
            ),
            "detected": sum(1 for r in rows if r["category"] == "GENUINE"),
            "fragments_outside_spans": sum(1 for r in rows if r["category"] == "NONSIGN"),
            "duplicates": sum(1 for r in rows if r["category"] == "DUPLICATE"),
            "merged_events": sum(
                1 for r in rows if r["category"] == "GENUINE" and r["genuine_overlaps"] > 1
            ),
        }
    out["cal"] = {
        "signs": d["cal_signs"],
        "distinct": sum(1 for r in d["cal"] if r["category"] == "GENUINE"),
        "nonsign_events_p1": sum(
            1 for r in d["cal"] if r["category"] == "NONSIGN" and r["family"] == "P1"
        ),
        "nonsign_events_n0": sum(
            1 for r in d["cal"] if r["category"] == "NONSIGN" and r["family"] == "N0"
        ),
        "duplicates": sum(1 for r in d["cal"] if r["category"] == "DUPLICATE"),
    }
    return out


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    out: dict[str, Any] = {"phone": {}, "protocol_022535Z": {}, "heldout_and_cal": {}}
    for label, cfg in PHONE_CONFIGS.items():
        led = json.loads((HERE / f"ledger_{cfg}.json").read_text())
        out["phone"][label] = phone_row(led["sessions"])
        out["protocol_022535Z"][label] = protocol_row(led["sessions"]["SHADOW_022535Z"]["events"])
        sl = HERE / f"stream_ledger_{cfg}.json"
        if sl.exists():
            out["heldout_and_cal"][label] = stream_row(sl)
    loso_path = HERE / "arm_p_loso.json"
    if loso_path.exists():
        loso = json.loads(loso_path.read_text())
        for dec, name in (
            ("BASELINE", "production decoder"),
            ("CONFIRM_BOUNDARY_70", "confirm-boundary"),
        ):
            sessions = {
                fold: v[f"ARM_P_SELECTED:{dec}"]["ledger"] for fold, v in loso["folds"].items()
            }
            out["phone"][f"ARM_P (leave-one-session-out), {name}"] = phone_row(sessions)
        allm = loso.get("all_sessions_model", {})
        for dec, name in (
            ("BASELINE", "production decoder"),
            ("CONFIRM_BOUNDARY_70", "confirm-boundary"),
        ):
            key = f"ARM_P_ALL:{dec}"
            if key in allm:
                out["protocol_022535Z"][f"ARM_P (all sessions), {name}"] = protocol_row(
                    allm[key]["events"]
                )
        for p in sorted(HERE.glob("stream_ledger_ARM_P_ALL_E*__*.json")):
            dec = "confirm-boundary" if "CONFIRM" in p.name else "production decoder"
            out["heldout_and_cal"][f"ARM_P (all sessions), {dec}"] = stream_row(p)
    (HERE / "system_compare.json").write_text(json.dumps(out, indent=1))
    keys = (
        "tier2_correct",
        "tier2_wrong",
        "tier2_missed",
        "tier2_merged_away",
        "tier2_continuous_distinct",
        "tier2_nonsign",
        "tier2_unreviewed_or_uncertain",
        "tier2_duplicates",
        "tier2_v2_correct",
        "shadow_correct",
        "shadow_nonsign",
        "shadow_unreviewed",
    )
    print("phone:", " ".join(k.replace("tier2_", "t2.").replace("shadow_", "sh.") for k in keys))
    for label, r in out["phone"].items():
        print(f"  {label:52s}", " ".join(str(r[k]) for k in keys))
    print("022535Z protocol:")
    for label, r in out["protocol_022535Z"].items():
        print(f"  {label:52s}", r)
    print("held-out DEV / CAL:")
    for label, r in out["heldout_and_cal"].items():
        print(f"  {label:52s}", json.dumps(r))


if __name__ == "__main__":
    main()
