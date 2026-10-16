"""Step 7 (mechanism diagnostic, NOT a deployable change): remove hand-proposal evidence for
slots the refiner rejected (phantom DWPose proposals), recompute the dependent ROI deltas and
proposal transitions, and re-run the frozen S2-R2 with its normal rolling 61 history.

The model was trained WITH phantom proposals, so this introduces its own input shift; it only
asks whether phantom-proposal content is what holds S2 in POST.
"""
import numpy as np

from common import ACTIVE, IGNORE, SESSIONS, load_models, load_session, phase7_dev_views
from step4_policies import evaluate


def sanitize(F):
    F = F.copy()
    orig = F.copy()
    n = len(F)
    for s in (0, 1):
        rej = F[:, 172 + s] < 0.5
        F[rej, 126 + 21 * s:147 + 21 * s] = 0
        F[rej, 168 + s] = 0
        F[rej, 170 + s] = 0
        F[rej, 174 + s] = 0
        F[rej, 176 + 3 * s:179 + 3 * s] = 0
        prop = F[:, 174 + s] > 0.5
        for i in range(n):
            first = i == 0 or orig[i, 215] == 0  # dt==0 marks a row without a previous observation
            valid = (not first) and prop[i] and prop[i - 1]
            F[i, 348 + s] = 1.0 if valid else 0.0
            if not valid:
                F[i, 342 + 3 * s:345 + 3 * s] = 0
            F[i, 376 + s] = 0.0 if first else float(prop[i]) - float(prop[i - 1])
    return F


models = load_models()
m = models["S2_R2"]
tot = {"base": {}, "sanitized": {}}
for name in SESSIONS:
    s = load_session(name)
    for arm, F in (("base", s.features), ("sanitized", sanitize(s.features))):
        st = m.probs(m.normalize(F)).argmax(1)
        r = evaluate(s, st, None)
        whole = np.bincount(st, minlength=3) / len(st)
        print(f"{name:22s} {arm:9s} acquired {r['acquired']}/{r['genuine']} sign-with-event {r['sign_with_event']}/{r['genuine']} "
              f"events {r['events']:2d} in-nonsign {r['events_inside_confirmed_nonsign']} other {r['other_events']:2d} "
              f"nonsign ACTIVE {r['nonsign_active_rate']:.3f}  PRE/ACT/POST share {whole[0]:.2f}/{whole[1]:.2f}/{whole[2]:.2f}")
        for k, v in r.items():
            tot[arm][k] = tot[arm].get(k, 0) + (v * r["nonsign_obs"] if k == "nonsign_active_rate" else v)
for arm, t in tot.items():
    print(f"TOTAL {arm:9s} acquired {t['acquired']}/{t['genuine']} sign-with-event {t['sign_with_event']}/{t['genuine']} "
          f"events {t['events']} in-nonsign {t['events_inside_confirmed_nonsign']} other {t['other_events']} "
          f"nonsign ACTIVE obs {int(round(t['nonsign_active_rate']))}/{t['nonsign_obs']}")

views = phase7_dev_views()
for arm in ("base", "sanitized"):
    acq, rec, fa = [], [], []
    for v in views:
        F = v["features"] if arm == "base" else sanitize(v["features"])
        p = m.probs(m.normalize(F)).argmax(1)
        act = v["labels"] == ACTIVE
        non = (v["labels"] != ACTIVE) & (v["labels"] != IGNORE)
        acq.append((p[act] == ACTIVE).any()); rec.append((p[act] == ACTIVE).mean()); fa.append((p[non] == ACTIVE).mean())
    print(f"DEV(69 views) {arm:9s} acquired {np.mean(acq):.3f} ACTIVE recall {np.mean(rec):.3f} false ACTIVE in PRE/POST {np.mean(fa):.3f}")
