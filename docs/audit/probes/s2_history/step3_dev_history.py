"""Step 3: controlled history conditions on held-out (signer-disjoint) segmentation DEV signs.

Each of the 69 DEV sparse views (23 clips, 7 signers, never used to fit S2-R2 or Phase-7) is
evaluated with the frozen model after prepending a history. Only S2 states are scored here
(no decoder), so the lifecycle cannot confound the result.

History conditions (all real feature rows; no interpolation of the scored sign itself):
  NONE            the training/eval condition (implicit zero padding)
  STILL_SELF_L    L copies of the clip's first observation, made 'still' (deltas 0, delta-valid
                  flags set where the current point is valid, dt = view interval). Same signer,
                  same scene, no motion: isolates history LENGTH from content.
  P1_NEG_L        last L rows of an untouched P1 negative row (INTERNAL_DEVELOPMENT role):
                  real non-sign phone movement, other signer.
  REST_PHONE_L    L rows of PRE-dominated rest from the untouched SEP23_REPRESENTATIVE session.
  POST_PHONE_L    L rows of the OCT15 hold / rest where frozen S2 sits in POST.
  PREV_SIGN       the full sequence of another DEV clip of the SAME signer (sign -> rest -> sign).
"""
import json
import sys
from collections import defaultdict

import numpy as np

from common import ACTIVE, IGNORE, load_models, load_session, phase7_dev_views, s2r2_rows

DT = 215
JOINT_VALID = slice(84, 126)
DELTA_VALID = slice(300, 342)
OBSERVED = [172, 173]
PROPOSAL = [174, 175]
ROI_DELTA_VALID = [348, 349]
BODY_VALID = slice(206, 214)
BODY_DELTA_VALID = slice(366, 374)
DELTAS = [slice(216, 300), slice(342, 348), slice(350, 366), slice(374, 378)]


def still_rows(first, n, dt_s):
    row = first.copy()
    for sl in DELTAS:
        row[sl] = 0.0
    jv = first[JOINT_VALID].reshape(2, 21) * first[OBSERVED].reshape(2, 1)
    row[DELTA_VALID] = jv.reshape(-1)
    row[ROI_DELTA_VALID] = first[PROPOSAL]
    row[BODY_DELTA_VALID] = first[BODY_VALID]
    row[DT] = dt_s
    return np.repeat(row[None], n, axis=0)


def score(model, history, view):
    x = np.concatenate([history, view["features"]]) if len(history) else view["features"]
    p = model.probs(model.normalize(x))[len(history):]
    lab = view["labels"]
    act = lab == ACTIVE
    pred = p.argmax(1)
    non_act = (lab != ACTIVE) & (lab != IGNORE)
    return {"acquired": bool((pred[act] == ACTIVE).any()),
            "active_recall": float((pred[act] == ACTIVE).mean()),
            "false_active_in_clip_pre_post": float((pred[non_act] == ACTIVE).mean()) if non_act.any() else 0.0,
            "max_p_active": float(p[act, 1].max())}


def main(out_path):
    models = load_models()
    views = phase7_dev_views()
    p1 = [r for r in s2r2_rows("P1_NEGATIVE", "INTERNAL_DEVELOPMENT") if len(r["features"]) >= 60]
    rep = load_session("SEP23_REPRESENTATIVE")
    rep_states = rep.android_probs.argmax(1)
    # longest PRE-dominated stretch outside attempts/negatives
    pre_runs = [i for i in range(60, len(rep_states)) if (rep_states[i - 60:i] == 0).mean() > 0.9]
    rest_end = pre_runs[0] if pre_runs else 60
    rest_rows = rep.features[rest_end - 60:rest_end]
    oct15 = load_session("OCT15_COMPACT")
    d = [p for p in oct15.positives if p["name"].startswith("D_")][0]
    post_rows = oct15.features[d["b"] - 59:d["b"] + 1]      # last 60 rows of the hold block
    by_signer = defaultdict(list)
    for v in views:
        by_signer[v["signer"]].append(v)

    lengths = [5, 15, 30, 60]
    results = defaultdict(lambda: defaultdict(list))
    for mname, model in models.items():
        for k, v in enumerate(views):
            dt_s = float(np.median(np.diff(v["timestamps_ms"]))) / 1000.0
            conds = {"NONE": np.zeros((0, 378), np.float32)}
            for L in lengths:
                conds[f"STILL_SELF_{L}"] = still_rows(v["features"][0], L, dt_s)
                conds[f"P1_NEG_{L}"] = p1[k % len(p1)]["features"][-L:]
                conds[f"REST_PHONE_{L}"] = rest_rows[-L:]
                conds[f"POST_PHONE_{L}"] = post_rows[-L:]
            others = [o for o in by_signer[v["signer"]] if o["key"].split("::")[0] != v["key"].split("::")[0]
                      and o["view"] == v["view"]]
            if others:
                conds["PREV_SIGN_SAME_SIGNER"] = others[0]["features"]
            for cname, hist in conds.items():
                results[mname][cname].append(score(model, hist, v))
    summary = {}
    for mname, conds in results.items():
        print(f"\n== {mname} on held-out DEV views (n={len(views)})")
        print(f"  {'condition':24s} {'n':>3s} {'acquired':>9s} {'ACTIVE recall':>14s} {'false ACTIVE in clip PRE/POST':>30s}")
        summary[mname] = {}
        for cname, lst in conds.items():
            acq = np.mean([r["acquired"] for r in lst])
            rec = np.mean([r["active_recall"] for r in lst])
            fa = np.mean([r["false_active_in_clip_pre_post"] for r in lst])
            summary[mname][cname] = {"n": len(lst), "acquired": acq, "active_recall": rec, "false_active": fa}
            print(f"  {cname:24s} {len(lst):3d} {acq:9.3f} {rec:14.3f} {fa:30.3f}")
    json.dump(summary, open(out_path, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
