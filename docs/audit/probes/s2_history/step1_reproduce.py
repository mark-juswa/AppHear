"""Step 1: reproduce the runtime exactly, then re-run the audit's oracle-context probe
on all four labelled phone sessions (two of them untouched distinct-signer validation)."""
import json
import sys

import numpy as np

from common import ACTIVE, SESSIONS, decode, load_models, load_session

models = load_models()
s2 = models["S2_R2"]
out = {}
for name in SESSIONS:
    s = load_session(name)
    n = len(s.timestamps_ms)
    # (a) rolling prefix exactly as recorded by Android (history_length per row)
    rolling = np.zeros((n, 3))
    for i in range(n):
        h = int(s.history_length[i])
        rolling[i] = s2.probs(s.normalized_s2r2[i - h + 1:i + 1])[-1]
    full = s2.probs(s.normalized_s2r2)
    resets = int(np.sum((s.history_length[1:] <= s.history_length[:-1]) & (s.history_length[1:] < 61)))
    # (b) decoder port on Android argmax reproduces recorded events
    events_file = SESSIONS[name][0] / "events.jsonl"
    recorded = [json.loads(line) for line in open(events_file, encoding="utf-8")]
    src = np.fromfile(SESSIONS[name][0] / "s2_exact_parity/source_index.i32", dtype=np.int32)
    ported = decode(s.timestamps_ms, s.android_probs.argmax(1))
    rec = [(e["logical_active_start_index"], e["logical_active_end_index"], e["commit_index"]) for e in recorded]
    por = [(int(src[e["start"]]), int(src[e["end"]]), int(src[e["commit"]])) for e in ported]
    print(f"\n== {name} ({s.role}) n={n}")
    print(f"  keras rolling vs android max|dp|={np.abs(rolling - s.android_probs).max():.2e} "
          f"argmax mismatches={int((rolling.argmax(1) != s.android_probs.argmax(1)).sum())}; "
          f"history resets in session={resets}; full-pass vs rolling max|dp|={np.abs(full - rolling).max():.2e}")
    print(f"  decoder port events == recorded: {por == rec} ({len(por)} vs {len(rec)})")
    rows = []
    for p in s.positives:
        a, b = p["a"], p["b"]
        act_rows = p["active_rows"]
        res = {"name": p["name"], "judgment": p["judgment"], "n_active_labelled": len(act_rows),
               "history_len_at_onset": int(s.history_length[a]),
               "android_active": int(sum(s.android_probs[i].argmax() == ACTIVE for i in act_rows))}
        for k in (8, 4, 0):
            start = max(0, a - k)
            pr = s2.probs(s.normalized_s2r2[start:b + 1])
            res[f"fresh_onset-{k}"] = int(sum(pr[i - start].argmax() == ACTIVE for i in act_rows))
        rows.append(res)
        print(f"  {p['name']:32s} {p['judgment'][:9]:9s} hist@onset={res['history_len_at_onset']:2d} "
              f"ACTIVE rolling={res['android_active']:2d}/{len(act_rows):2d} fresh-8={res['fresh_onset-8']:2d} "
              f"fresh-4={res['fresh_onset-4']:2d} fresh-0={res['fresh_onset-0']:2d}")
    out[name] = rows
json.dump(out, open(sys.argv[1], "w"), indent=1)
