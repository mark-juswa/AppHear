"""Step 10: direct sign->sign transitions without rest, from held-out DEV clips of the same signer
and cadence view. Prefix = previous clip up to its first POST observation after ACTIVE
(+0/+3/+6 POST rows = hand held briefly). Target = next clip starting 1 row before its ACTIVE.
Control = the same cropped target with no prefix. Per-view breakdown included."""
import numpy as np
from collections import defaultdict
from common import ACTIVE, POST, load_models, phase7_dev_views
models = load_models(); views = phase7_dev_views()
by = defaultdict(list)
for v in views: by[(v["signer"], v["view"])].append(v)
for mname, m in models.items():
    res = defaultdict(list)
    for (sig, view), vs in by.items():
        for k, tgt in enumerate(vs):
            prev = vs[k - 1] if len(vs) > 1 else None
            ta = int(np.where(tgt["labels"] == ACTIVE)[0][0])
            target = tgt["features"][max(0, ta - 1):]; lab = tgt["labels"][max(0, ta - 1):]
            act = lab == ACTIVE
            def acq(hist):
                x = np.concatenate([hist, target]) if len(hist) else target
                p = m.probs(m.normalize(x))[len(hist):].argmax(1)
                return (p[act] == ACTIVE).any(), (p[act] == ACTIVE).mean()
            res[("NO_PREFIX(cropped)", view)].append(acq(np.zeros((0, 378), np.float32)))
            if prev is None: continue
            pl = prev["labels"]; pa = np.where(pl == ACTIVE)[0]
            after = [i for i in range(pa[-1] + 1, len(pl)) if pl[i] == POST]
            if not after: continue
            for extra in (0, 3, 6):
                end = min(after[0] + extra, len(pl) - 1)
                res[(f"PREV_SIGN_then_+{extra}POST", view)].append(acq(prev["features"][:end + 1]))
    print(f"== {mname}")
    conds = sorted({c for c, _ in res})
    for c in conds:
        allv = [x for (cc, _), lst in res.items() if cc == c for x in lst]
        per = "  ".join(f"{v}:{np.mean([a for a,_ in res[(c,v)]]):.2f}" for v in ("VIEW_A","VIEW_B","VIEW_C") if (c,v) in res)
        print(f"  {c:26s} n={len(allv):2d} acquired={np.mean([a for a,_ in allv]):.3f} recall={np.mean([r for _,r in allv]):.3f}   by view {per}")
