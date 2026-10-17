"""Event-level contribution of CONFIRM_BOUNDARY_70 vs BASELINE (same S2 and WORD), CAL/DEV/phone.

Each CB70 event is matched to the BASELINE event(s) it overlaps in the same stream/session:
  UNCHANGED       identical logical span
  SPLIT_PIECE     overlaps a baseline event that CB70 cut into >= 2 events
  NEW             overlaps no baseline event
Reports, per category, what the extra events are (GENUINE gained, DUPLICATE, NONSIGN) and whether
the extra NONSIGN events are pieces of an already-false baseline event (no new false activation,
one extra false word) or new activations. Writes cb_contribution.json.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
CFG = "ARM_A_E10__{}"


def overl(a, b):
    return max(a[0], b[0]) <= min(a[1], b[1])


def compare(base_rows, cb_rows, key):
    groups_b, groups_c = defaultdict(list), defaultdict(list)
    for r in base_rows:
        groups_b[key(r)].append(r)
    for r in cb_rows:
        groups_c[key(r)].append(r)
    out = Counter()
    for k, rows in groups_c.items():
        brows = groups_b.get(k, [])
        bspans = {tuple(r["logical"]) for r in brows}
        for r in rows:
            if tuple(r["logical"]) in bspans:
                continue
            parents = [b for b in brows if overl(b["logical"], r["logical"])]
            kind = "SPLIT_PIECE" if parents else "NEW"
            parent = "/".join(sorted({p["category"] for p in parents})) or "-"
            out[f"{kind}:{r['category']}:parent={parent}"] += 1
        for b in brows:
            if tuple(b["logical"]) not in {tuple(r["logical"]) for r in rows}:
                out[f"REPLACED_BASELINE:{b['category']}"] += 1
    return dict(sorted(out.items()))


def counts(rows):
    c = Counter(r["category"] for r in rows)
    c["correct_words"] = sum(
        1 for r in rows if r["category"] == "GENUINE" and r.get("frozen_correct")
    )
    return dict(c)


def main():
    out = {}
    sb = json.loads((HERE / f"stream_ledger_{CFG.format('BASELINE')}.json").read_text())
    sc = json.loads((HERE / f"stream_ledger_{CFG.format('CONFIRM_BOUNDARY_70')}.json").read_text())
    for part, key in (("cal", lambda r: r["stream"]), ("dev", lambda r: r["stream"])):
        out[part] = {
            "baseline": counts(sb[part]),
            "confirm_boundary_70": counts(sc[part]),
            "changes": compare(sb[part], sc[part], key),
        }
    for mode in ("NATURAL", "CONTINUOUS"):
        b = [r for r in sb["dev"] if r["mode"] == mode]
        c = [r for r in sc["dev"] if r["mode"] == mode]
        out[f"dev_{mode.lower()}"] = {"baseline": counts(b), "confirm_boundary_70": counts(c)}
    pb = json.loads((HERE / f"ledger_{CFG.format('BASELINE')}.json").read_text())
    pc = json.loads((HERE / f"ledger_{CFG.format('CONFIRM_BOUNDARY_70')}.json").read_text())
    rows_b = [r for v in pb["sessions"].values() for r in v["events"]]
    rows_c = [r for v in pc["sessions"].values() for r in v["events"]]
    out["phone"] = {
        "baseline": counts(rows_b),
        "confirm_boundary_70": counts(rows_c),
        "changes": compare(rows_b, rows_c, lambda r: r["session"]),
    }
    (HERE / "cb_contribution.json").write_text(json.dumps(out, indent=1))
    for k, v in out.items():
        print(k)
        for kk, vv in v.items():
            print("  ", kk, vv)


if __name__ == "__main__":
    main()
