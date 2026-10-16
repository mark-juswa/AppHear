"""Step 4: stream-level comparison of runtime history policies on all four labelled phone
sessions, with the exact decoder port. Scores genuine-sign acquisition AND false activations.

Policies (all causal; none uses labels):
  ROLLING_61        current runtime
  CAP_k             S2 sees only the last k observations (k = 8, 12, 16, 24, 32)
  RESET_AFTER_REARM earlier rejected Stage-2 probe (clear history at REARM_COMPLETE), closed loop
"""
import json
import sys

import numpy as np

from common import ACTIVE, Decoder, SESSIONS, load_models, load_session


def states_for(model, x, policy, timestamps):
    n = len(x)
    if policy == "ROLLING_61":
        p = model.probs(x)
        return p.argmax(1), p, None
    if policy.startswith("CAP_"):
        k = int(policy.split("_")[1])
        p = np.zeros((n, 3))
        for i in range(n):
            p[i] = model.probs(x[max(0, i - k + 1):i + 1])[-1]
        return p.argmax(1), p, None
    if policy == "RESET_AFTER_REARM":
        d = Decoder()
        start = 0
        p = np.zeros((n, 3))
        prev_state = "IDLE"
        for i in range(n):
            p[i] = model.probs(x[max(start, i - 60):i + 1])[-1]
            new_state = d.consume(float(timestamps[i]), int(p[i].argmax()))
            if prev_state == "WAIT" and new_state == "IDLE":
                start = i + 1          # clear history on the observation after REARM_COMPLETE
            prev_state = new_state
        return p.argmax(1), p, d.events
    raise ValueError(policy)


def evaluate(s, states, events):
    if events is None:
        d = Decoder()
        for t, st in zip(s.timestamps_ms, states):
            d.consume(float(t), int(st))
        events = d.events
    genuine = [p for p in s.positives if p["judgment"] == "GENUINE_SIGN"]
    acquired = sum(any(states[i] == ACTIVE for i in p["active_rows"]) for p in genuine)
    with_event = 0
    used = set()
    for p in genuine:
        lo, hi = p["a"], p["b"]
        hit = [k for k, e in enumerate(events) if max(lo, e["start"]) <= min(hi, e["end"])]
        with_event += bool(hit)
        used.update(hit)
    neg_obs = sum(n["b"] - n["a"] + 1 for n in s.negatives)
    neg_active = sum(int((states[n["a"]:n["b"] + 1] == ACTIVE).sum()) for n in s.negatives)
    neg_events = sum(1 for e in events for n in s.negatives if n["a"] <= e["start"] and e["end"] <= n["b"])
    return {"genuine": len(genuine), "acquired": acquired, "sign_with_event": with_event,
            "events": len(events), "events_inside_confirmed_nonsign": neg_events,
            "nonsign_active_rate": neg_active / neg_obs if neg_obs else 0.0,
            "nonsign_obs": neg_obs, "other_events": len(events) - len(used) - neg_events}


def main(out_path):
    models = load_models()
    policies = ["ROLLING_61", "CAP_8", "CAP_12", "CAP_16", "CAP_24", "CAP_32", "RESET_AFTER_REARM"]
    out = {}
    for mname in ("S2_R2",):
        model = models[mname]
        totals = {p: {} for p in policies}
        for sname in SESSIONS:
            s = load_session(sname)
            x = model.normalize(s.features)
            print(f"\n== {mname} / {sname} ({s.role})")
            for pol in policies:
                st, _, ev = states_for(model, x, pol, s.timestamps_ms)
                r = evaluate(s, st, ev)
                out[f"{mname}/{sname}/{pol}"] = r
                for k, v in r.items():
                    if k != "nonsign_active_rate":
                        totals[pol][k] = totals[pol].get(k, 0) + v
                totals[pol]["neg_active_obs"] = totals[pol].get("neg_active_obs", 0) + r["nonsign_active_rate"] * r["nonsign_obs"]
                print(f"  {pol:18s} acquired {r['acquired']}/{r['genuine']}  sign-with-event {r['sign_with_event']}/{r['genuine']}  "
                      f"events {r['events']:2d}  in-nonsign {r['events_inside_confirmed_nonsign']}  other {r['other_events']:2d}  "
                      f"nonsign ACTIVE rate {r['nonsign_active_rate']:.3f}")
        print(f"\n== {mname} TOTAL over 4 sessions")
        for pol, t in totals.items():
            print(f"  {pol:18s} acquired {t['acquired']}/{t['genuine']}  sign-with-event {t['sign_with_event']}/{t['genuine']}  "
                  f"events {t['events']}  in-nonsign {t['events_inside_confirmed_nonsign']}  other {t['other_events']}  "
                  f"nonsign ACTIVE obs {int(round(t['neg_active_obs']))}/{t['nonsign_obs']}")
    json.dump(out, open(out_path, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
