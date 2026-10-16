"""Step 8: label grammar and ACTIVE position in S2 training data (FIT rows of both models)."""
import json
import numpy as np
from collections import Counter
from common import P7_DIR, s2r2_rows

def grammar(rows, tag):
    trans = Counter(); multi = 0; pos = []; post_to_active = 0; seq_len_active = []
    for r in rows:
        lab = [int(x) for x in r["labels"] if int(x) != -1]
        segs = [k for k in range(len(lab)) if lab[k] == 1 and (k == 0 or lab[k - 1] != 1)]
        multi += len(segs) > 1
        for a, b in zip(lab, lab[1:]):
            if a != b: trans[(a, b)] += 1
        full = np.asarray(r["labels"])
        pos += list(np.where(full == 1)[0])
    names = {0: "PRE", 1: "ACT", 2: "POST"}
    pos = np.asarray(pos)
    print(f"{tag}: rows={len(rows)} rows with >1 ACTIVE segment={multi}")
    print("   label transitions:", {f"{names[a]}->{names[b]}": c for (a, b), c in sorted(trans.items())})
    if len(pos):
        print(f"   ACTIVE label positions (index from sequence start): p50={np.median(pos):.0f} p90={np.percentile(pos,90):.0f} "
              f"max={pos.max()}  share at index>=30: {np.mean(pos>=30):.3f}  at >=60: {np.mean(pos>=60):.3f}")

grammar(s2r2_rows(role="FIT"), "S2-R2 FIT (all domains)")
m = json.load(open(P7_DIR / "sparse_view_manifest.json", encoding="utf-8"))
fit = json.load(open(P7_DIR / "frozen_fit_cal_split.json", encoding="utf-8"))
fit_ids = set(fit.get("fit_sample_ids") or fit.get("fit") or [])
rows = []
for r in m["rows"]:
    if r["phase7_partition"] in ("FIT",) or (fit_ids and r["sample_id"] in fit_ids and r["phase7_partition"] != "DEV"):
        z = np.load(r["feature_path"], allow_pickle=False); rows.append({"labels": z["labels"]})
grammar(rows, "Phase-7 FIT")
