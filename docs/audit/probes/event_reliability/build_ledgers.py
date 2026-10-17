"""Build phone event ledgers for every compared configuration (frozen WORD displayed, v2 shadow).

Writes ledger_<S2>__<DECODER>.json next to this file and prints the reproduction check against
the numbers recorded in earlier milestones (event_separation/armA_e10_confirm_boundary.json,
output_policy/phone_false_words.json).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics import event_reliability as er  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
HERE = Path(__file__).parent
CONFIGS = (
    ("S2_R2", "BASELINE"),
    ("S2_R2", "CONFIRM_BOUNDARY_70"),
    ("ARM_A_E10", "BASELINE"),
    ("ARM_A_E10", "CONFIRM_BOUNDARY_70"),
    ("ARM_A_E21_T08", "BASELINE"),
    ("ARM_A_E21_T08", "CONFIRM_BOUNDARY_70"),
)
RECORDED = {  # tier-2 correct words (frozen) / events inside confirmed non-sign / all events
    ("S2_R2", "BASELINE"): (8, 5, None),
    ("ARM_A_E10", "BASELINE"): (13, 9, 33),
    ("ARM_A_E10", "CONFIRM_BOUNDARY_70"): (14, 9, 34),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configs", nargs="*", help="S2:DECODER pairs (default: all)")
    args = parser.parse_args()
    configs = [tuple(c.split(":")) for c in args.configs] if args.configs else CONFIGS
    sessions = er.phone_sessions(E)
    frozen = er.Word(E, er.FROZEN_WORD, er.FROZEN_WORD_SHA)
    shadow = er.Word(E, er.V2_WORD)
    for s2_name, variant in configs:
        s2 = er.load_s2(E, s2_name)
        ledger = er.phone_ledger(E, sessions, s2, variant, frozen, shadow)
        summary = er.summarize_phone(ledger)
        out = {
            "s2": s2.identity,
            "s2_name": s2_name,
            "decoder": variant,
            "frozen_word_sha256": frozen.sha256,
            "v2_word_sha256": shadow.sha256,
            "summary_frozen": summary,
            "summary_v2": er.summarize_phone(ledger, key="v2"),
            "sessions": ledger,
        }
        (HERE / f"ledger_{s2_name}__{variant}.json").write_text(
            json.dumps(out, indent=1, default=float), encoding="utf-8"
        )
        t2 = summary["tier2"]
        line = (
            f"{s2_name:14s} {variant:20s} tier2 correct={t2['correct_words']:2d}/23 "
            f"nonsign={t2.get('all_confirmed_nonsign', 0)} events={t2['events']} "
            f"dup={t2.get('all_duplicate', 0)} merged={t2['merged_events']} "
            f"unreviewed={t2.get('all_unreviewed', 0)} partial={t2.get('all_partial_nonsign', 0)} "
            f"uncertain={t2.get('all_uncertain', 0)}"
        )
        rec = RECORDED.get((s2_name, variant))
        if rec:
            got = (t2["correct_words"], t2.get("all_confirmed_nonsign", 0), t2["events"])
            same = all(r is None or r == g for r, g in zip(rec, got, strict=True))
            line += f" | recorded {rec} -> {'REPRODUCED' if same else 'MISMATCH'}"
        print(line, flush=True)
        sh = summary["shadow_023004Z"]
        print(
            f"{'':35s} shadow023004Z correct={sh['correct_words']}/{sh['genuine_signs']} "
            f"nonsign={sh.get('all_confirmed_nonsign', 0)} events={sh['events']} | 022535Z "
            f"{summary['protocol']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
