"""Read-only decomposition of hand-acceptance failures and body-frame validity
inside human-reviewed intervals of saved AppHear phone captures."""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np


def hand_status(o, side):
    if o[f"{side}_observed"]:
        return "ACCEPTED"
    if not o[f"{side}_proposal"]:
        return "NO_ROI_PROPOSAL"
    p = o[f"{side}_presence"]
    if p is None or p < 0.5:
        return "PRESENCE_LT_0.5"
    return "VALID_JOINTS_LT_18"


def main(session):
    s = Path(session)
    obs = [json.loads(line) for line in open(s / "observations.jsonl", encoding="utf-8")]
    n = len(obs)
    body_valid = np.fromfile(s / "s2_exact_parity" / "raw_body_valid.u8", dtype=np.uint8).reshape(n, 8)
    labels = json.load(open(s / "transition_review" / "human_boundaries.json", encoding="utf-8"))
    intervals = []
    for x in labels["signs"]:
        if x["start_index"] is not None:
            intervals.append((f"{x['condition']}:{x['gloss']}#{x['ordinal']}:{x['judgment']}", x["start_index"], x["end_index"]))
    for x in labels.get("negative_intervals", []):
        if x["start_index"] is not None:
            intervals.append((f"NEG:{x['block']}", x["start_index"], x["end_index"]))
    by_index = {o["source_index"]: i for i, o in enumerate(obs)}
    print(f"session={s.name} observations={n}")
    tot = Counter()
    for name, a, b in intervals:
        rows = [by_index[k] for k in range(a, b + 1) if k in by_index]
        c = Counter()
        shoulders = hips = v2frame = 0
        active = 0
        maxact = 0.0
        for r in rows:
            o = obs[r]
            for side in ("left", "right"):
                c[hand_status(o, side)] += 1
            sh = bool(body_valid[r, 0] and body_valid[r, 1])
            hp = bool(body_valid[r, 6] and body_valid[r, 7])
            shoulders += sh
            hips += hp
            v2frame += sh or hp
            active += o["argmax_state"] == 1
            maxact = max(maxact, o["active_probability"])
        if not name.startswith("NEG"):
            tot.update(c)
        print(f"  {name:55s} rows={len(rows):3d} ACTIVE={active:2d} maxP(ACTIVE)={maxact:.3f} "
              f"shoulders_valid={shoulders}/{len(rows)} hips_valid={hips}/{len(rows)} "
              f"V2_body_frame_valid={v2frame}/{len(rows)} hand_slots={dict(c)}")
    print("  POSITIVE-interval hand-slot totals:", dict(tot))
    all_c = Counter()
    for o in obs:
        for side in ("left", "right"):
            all_c[hand_status(o, side)] += 1
    print("  whole-session hand-slot totals:", dict(all_c))
    sh_all = int(np.sum(body_valid[:, 0] & body_valid[:, 1]))
    print(f"  whole-session shoulders-valid rows: {sh_all}/{n}")


if __name__ == "__main__":
    for path in sys.argv[1:]:
        main(path)
