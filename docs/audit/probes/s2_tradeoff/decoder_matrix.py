"""S2 x decoder matrix on the non-phone criteria fixed before results (and phone as diagnostic).

Criteria for "improves on Arm A e10 + CB70" (fixed 2026-10-17 before any PRE_EXIT result):
  held-out ASL continuous correct >= 145 and natural >= 226 (within 5% of Arm A + CB);
  suite v04 IPN tier NOG events/min <= 1.0; CAL P1 non-sign events < 80; duplicates not worse.
Inputs: stream_ledger_*.json / ledger_*.json (event_reliability probes); IPN tier recomputed here
through suite v04 tier-1c code under each decoder variant. Writes decoder_matrix.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics import event_reliability as er  # noqa: E402
from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics.event_separation import VARIANTS, use_variant  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
LEDGERS = REPO / "docs/audit/probes/event_reliability"
HERE = Path(__file__).parent
CONFIGS = (
    ("S2_R2", "BASELINE"),
    ("ARM_A_E10", "CONFIRM_BOUNDARY_70"),
    ("ARM_A_E10", "CB70_PRE_EXIT_POST"),
    ("ARM_I_E28", "CONFIRM_BOUNDARY_70"),
    ("ARM_I_E28", "PRE_EXIT_POST"),
    ("ARM_I_E28", "CB70_PRE_EXIT_POST"),
    ("ARM_A_E10_T09", "CONFIRM_BOUNDARY_70"),
    ("ARM_K_E23", "CONFIRM_BOUNDARY_70"),
    ("ARM_K_E23", "CB70_PRE_EXIT_POST"),
    ("ARM_A_E10", "BASELINE"),
    ("ARM_A_E10", "REENTRY_2"),
    ("ARM_A_E10", "R2_CB70"),
    ("ARM_A_E10", "R1_CB70"),
    ("ARM_I_E28", "R1_CB70"),
    ("ARM_I_E28", "R2_CB70_PRE_EXIT_POST"),
    ("ARM_I_E28", "R1_CBN70"),
    ("ARM_I_E28", "R1_CBN70_PRE_EXIT_POST"),
    ("ARM_A_E10", "R1_CBN70"),
)


def stream_metrics(path: Path) -> dict:
    d = json.loads(path.read_text())
    out = {}
    for mode in ("NATURAL", "CONTINUOUS"):
        rows = [r for r in d["dev"] if r["mode"] == mode]
        out[f"dev_{mode.lower()}_correct"] = sum(
            1 for r in rows if r["category"] == "GENUINE" and r.get("frozen_correct")
        )
        out[f"dev_{mode.lower()}_fragments"] = sum(1 for r in rows if r["category"] == "NONSIGN")
        out[f"dev_{mode.lower()}_duplicates"] = sum(1 for r in rows if r["category"] == "DUPLICATE")
    out["cal_p1_nonsign"] = sum(
        1 for r in d["cal"] if r["category"] == "NONSIGN" and r["family"] == "P1"
    )
    out["cal_duplicates"] = sum(1 for r in d["cal"] if r["category"] == "DUPLICATE")
    out["cal_distinct"] = sum(1 for r in d["cal"] if r["category"] == "GENUINE")
    return out


def phone_metrics(path: Path) -> dict:
    s = json.loads(path.read_text())["summary_frozen"]
    t2, sh = s["tier2"], s["shadow_023004Z"]
    return {
        "phone_correct": t2["correct_words"] + sh["correct_words"],
        "phone_nonsign": t2.get("all_confirmed_nonsign", 0) + sh.get("all_confirmed_nonsign", 0),
        "phone_unreviewed": sum(
            v.get(f"all_{k}", 0)
            for v in (t2, sh)
            for k in ("unreviewed", "uncertain", "partial_nonsign")
        ),
        "protocol_022535Z": s["protocol"]["SHADOW_022535Z"],
    }


def main() -> None:
    config = suite.read_json(suite.SUITES["04"][0])
    spec = config["tier1c_ipn_hands_visible"]
    ipn = suite.load_ipn_streams(E, config, "v1")
    out = {}
    for s2, dec in CONFIGS:
        key = f"{s2}__{dec}"
        row: dict = {}
        sl = LEDGERS / f"stream_ledger_{key}.json"
        if sl.exists():
            row.update(stream_metrics(sl))
        pl = LEDGERS / f"ledger_{key}.json"
        if pl.exists():
            row.update(phone_metrics(pl))
        with use_variant(next(v for v in VARIANTS if v.name == dec)):
            t = suite.evaluate_ipn(er.load_s2(E, s2), ipn, spec)["total"]
        row["ipn_nog_events_per_min"] = t["nog_events_per_minute"]
        row["ipn_nog_events"] = t["nog_events"]
        out[key] = row
        print(key, json.dumps(row), flush=True)
    (HERE / "decoder_matrix.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
