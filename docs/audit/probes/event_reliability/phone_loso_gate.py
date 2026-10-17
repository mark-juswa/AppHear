"""Phone-domain check of a WORD-confidence gate, leave-one-session-out (development-exposed).

For each reviewed phone session S: choose the frozen top-1 threshold on the OTHER sessions
(maximise correct words kept minus confirmed non-sign events kept; ties -> lower threshold), then
apply it to S. Sums over sessions. Tests whether the phone-only confidence separation (AUC 0.90 on
10 non-sign events) holds across sessions. Writes phone_loso_gate.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
GRID = np.round(np.arange(0.0, 1.0001, 0.05), 2)


def main(config: str = "ARM_A_E10__CONFIRM_BOUNDARY_70") -> None:
    led = json.loads((HERE / f"ledger_{config}.json").read_text())
    sessions = {
        n: v["events"] for n, v in led["sessions"].items() if v["kind"] != "SHADOW_PROTOCOL_ONLY"
    }

    def counts(rows, th):
        c = sum(
            1
            for r in rows
            if r["category"] == "GENUINE" and r.get("frozen_correct") and r["word_p1"] >= th
        )
        w = sum(
            1
            for r in rows
            if r["category"] == "GENUINE" and not r.get("frozen_correct") and r["word_p1"] >= th
        )
        n = sum(1 for r in rows if r["category"] == "CONFIRMED_NONSIGN" and r["word_p1"] >= th)
        u = sum(
            1
            for r in rows
            if r["category"] in ("UNREVIEWED", "UNCERTAIN", "PARTIAL_NONSIGN", "DUPLICATE")
            and r["word_p1"] >= th
        )
        return c, w, n, u

    out = {"folds": {}, "total_gated": [0, 0, 0, 0], "total_ungated": [0, 0, 0, 0]}
    for held in sessions:
        train = [r for n, rows in sessions.items() if n != held for r in rows]
        th = max(GRID, key=lambda t: (counts(train, t)[0] - counts(train, t)[2], -t))
        g, u = counts(sessions[held], th), counts(sessions[held], 0.0)
        out["folds"][held] = {"threshold": float(th), "gated": g, "ungated": u}
        out["total_gated"] = [a + b for a, b in zip(out["total_gated"], g, strict=True)]
        out["total_ungated"] = [a + b for a, b in zip(out["total_ungated"], u, strict=True)]
        print(f"{held:22s} th={th:.2f} (correct, wrong, nonsign, other) ungated={u} gated={g}")
    print("TOTAL ungated", out["total_ungated"], "gated", out["total_gated"])
    (HERE / "phone_loso_gate.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
