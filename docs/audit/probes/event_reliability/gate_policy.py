"""Previous-milestone confidence gate (output_policy/calibrate.py rule) applied per configuration.

Threshold: maximise Youden J = correct kept/correct - wrong kept/wrong over every held-out DEV event
of calibration signers P5/P12/P21 (correct = credited event with the right gloss; wrong = anything
else, incl. fragments), grid 0.00-0.95. Applied unchanged to validation signers P26/P39, the
reviewed phone sessions and 022535Z. A precision policy, not a reliability fix.
Writes gate_policy.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics.event_reliability import protocol_words  # noqa: E402

HERE = Path(__file__).parent
CAL = {"asl_citizen:P5", "asl_citizen:P12", "asl_citizen:P21"}
GRID = np.round(np.arange(0.0, 0.96, 0.05), 2)


def ok(r):
    return r["category"] == "GENUINE" and bool(r.get("frozen_correct"))


def main() -> None:
    out = {}
    for cfg in ("S2_R2__BASELINE", "ARM_A_E10__CONFIRM_BOUNDARY_70"):
        dev = json.loads((HERE / f"stream_ledger_{cfg}.json").read_text())["dev"]
        cal = [r for r in dev if r["signer"] in CAL]
        val = [r for r in dev if r["signer"] not in CAL]
        c, w = sum(map(ok, cal)), sum(not ok(r) for r in cal)

        def j(t, c=c, w=w, cal=cal):
            return (
                sum(ok(r) and r["word_p1"] >= t for r in cal) / c
                - sum((not ok(r)) and r["word_p1"] >= t for r in cal) / w
            )

        th = float(max(GRID, key=lambda t: (j(t), -t)))
        phone = json.loads((HERE / f"ledger_{cfg}.json").read_text())["sessions"]
        rows = [
            e for v in phone.values() if v["kind"] != "SHADOW_PROTOCOL_ONLY" for e in v["events"]
        ]

        def tally(rs, t):
            keep = [r for r in rs if r["word_p1"] >= t]
            return {
                "correct": sum(map(ok, keep)),
                "wrong_on_genuine": sum(r["category"] == "GENUINE" and not ok(r) for r in keep),
                "confirmed_nonsign": sum(r["category"] == "CONFIRMED_NONSIGN" for r in keep),
                "unreviewed_uncertain_partial": sum(
                    r["category"] in ("UNREVIEWED", "UNCERTAIN", "PARTIAL_NONSIGN") for r in keep
                ),
            }

        proto = phone["SHADOW_022535Z"]["events"]
        out[cfg] = {
            "threshold": th,
            "dev_validation": {
                "ungated": {"correct": sum(map(ok, val)), "wrong": sum(not ok(r) for r in val)},
                "gated": {
                    "correct": sum(ok(r) and r["word_p1"] >= th for r in val),
                    "wrong": sum((not ok(r)) and r["word_p1"] >= th for r in val),
                },
            },
            "phone_reviewed": {"ungated": tally(rows, 0.0), "gated": tally(rows, th)},
            "protocol_022535Z": {
                "ungated": protocol_words(proto, "frozen_top1", lambda r: True),
                "gated": protocol_words(proto, "frozen_top1", lambda r, th=th: r["word_p1"] >= th),
            },
        }
        print(cfg, json.dumps(out[cfg]))
    (HERE / "gate_policy.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
