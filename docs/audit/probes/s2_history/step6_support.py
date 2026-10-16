import numpy as np
from common import SESSIONS, load_session, s2r2_rows
def sup(f, side):  # mean DWPose hand-keypoint support for that slot
    return f[:, 126 + 21 * side:147 + 21 * side].mean(1)
print("Mean DWPose hand-proposal support, by refiner outcome (proposal present)")
for name in list(SESSIONS) + ["S2R2_FIT_ALL"]:
    F = np.concatenate([r["features"] for r in s2r2_rows(role="FIT")]) if name == "S2R2_FIT_ALL" else load_session(name).features
    acc, rej = [], []
    for side in (0, 1):
        prop = F[:, 174 + side] > 0.5
        obs = F[:, 172 + side] > 0.5
        acc.append(sup(F, side)[prop & obs]); rej.append(sup(F, side)[prop & ~obs])
    acc, rej = np.concatenate(acc), np.concatenate(rej)
    q = lambda v: "n=%5d p10/p50/p90=%.2f/%.2f/%.2f" % (len(v), *np.percentile(v, [10, 50, 90])) if len(v) else "n=0"
    print(f"  {name:22s} accepted hand: {q(acc)}   rejected proposal: {q(rej)}")
