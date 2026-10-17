"""Re-arm swallowing: what is lost; what separates a real next sign from a re-entry fragment.

S2 = Arm A e10 (reference). WORD not needed (decoder-only).
Part 1  SWALLOWED  Under CONFIRM_BOUNDARY_70, every genuine sign whose ACTIVE rows all arrive in
        EVENT_EMITTED_WAIT_REARM: time from the previous commit to its first ACTIVE row, and the
        state mix in between.
Part 2  RE-ENTRY   Under REENTRY_1 + CONFIRM_BOUNDARY_70, every event started by a re-entry, with
        its outcome (GENUINE new sign, DUPLICATE of a credited sign, NONSIGN = negative rows only,
        OTHER) and causal features known when it starts or when it is emitted:
          gap_obs / gap_ms         non-ACTIVE observations / time since the previous commit
          post_peak / pre_peak     max P(POST) / P(PRE) in that gap
          prev_span_ms             logical ACTIVE span of the previous event
          span_ms                  logical ACTIVE span of the re-entered event (known at emission)
          entry_active             P(ACTIVE) at the re-entry observation
Populations: CAL streams (sign ordinals vs negative blocks; P1/N0) and held-out DEV CONTINUOUS
(spans; rest = fragments). Writes rearm_probe.json.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics import event_reliability as er  # noqa: E402
from eval.runtime_diagnostics import heldout_dev_e2e as bench  # noqa: E402
from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics import s2_r3_train  # noqa: E402
from eval.runtime_diagnostics.event_separation import SplitConfig, use_variant  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
HERE = Path(__file__).parent
REENTRY_CB = SplitConfig(
    "R1_CB70", reentry=True, reentry_gap=1, confirm_boundary=True, post_peak=0.7
)
CB = SplitConfig("CB70", confirm_boundary=True, post_peak=0.7)


def run(probs: np.ndarray, t: np.ndarray, variant: SplitConfig) -> dict[str, Any]:
    states = np.argmax(probs, axis=1)
    rows = [
        {
            "source_index": i,
            "source_timestamp_ms": float(t[i]),
            "argmax_state": int(states[i]),
            "pre_probability": float(probs[i, 0]),
            "active_probability": float(probs[i, 1]),
            "post_probability": float(probs[i, 2]),
        }
        for i in range(len(t))
    ]
    with use_variant(variant):
        return suite.replay(rows, allow_post_rearm=True, exact_android_commit_recovery=True)


def categorize(
    span: tuple[int, int],
    signs: list[tuple[int, int]],
    credited_by: dict,
    j: int,
    negative: np.ndarray,
) -> str:
    s, f = span
    if j in credited_by:
        return "GENUINE"
    if any(max(a, s) <= min(b, f) for a, b in signs):
        return "DUPLICATE"
    if bool(np.all(negative[s : f + 1])):
        return "NONSIGN"
    return "OTHER"


def analyse(
    probs: np.ndarray,
    t: np.ndarray,
    signs: list[tuple[int, int]],
    negative: np.ndarray,
    family: np.ndarray | None,
) -> tuple[list[dict], list[dict]]:
    states = np.argmax(probs, axis=1)
    # Part 1: swallowed under CB70
    rep = run(probs, t, CB)
    trace = rep["trace"]
    commits = [int(e["emitted_at_index"]) for e in rep["events"]]
    spans = [
        (int(e["logical_active_start_index"]), int(e["logical_active_end_index"]))
        for e in rep["events"]
    ]
    swallowed = []
    for a, b in signs:
        act = [i for i in range(a, b + 1) if states[i] == 1]
        if not act or any(max(s, a) <= min(f, b) for s, f in spans):
            continue
        if all(trace[i]["state_before"] == "EVENT_EMITTED_WAIT_REARM" for i in act):
            c = max(x for x in commits if x <= act[0])
            gap = range(c + 1, act[0])
            swallowed.append(
                {
                    "ms_since_commit": float(t[act[0]] - t[c]),
                    "obs_since_commit": int(act[0] - c),
                    "post_rows": int(sum(states[i] == 2 for i in gap)),
                    "pre_rows": int(sum(states[i] == 0 for i in gap)),
                    "active_rows_in_gap": int(sum(states[i] == 1 for i in gap)),
                }
            )
    # Part 2: re-entry events under R1 + CB70
    rep = run(probs, t, REENTRY_CB)
    events = rep["events"]
    spans = [
        (int(e["logical_active_start_index"]), int(e["logical_active_end_index"])) for e in events
    ]
    credited_by: dict[int, int] = {}
    used: set[int] = set()
    for k, (a, b) in enumerate(signs):
        hits = [j for j, (s, f) in enumerate(spans) if max(s, a) <= min(f, b)]
        d = next((j for j in hits if j not in used), None)
        if d is not None:
            used.add(d)
            credited_by[d] = k
    starts = {i for i, r in enumerate(rep["trace"]) if r["action"] == "SPLIT_REENTRY_ACTIVE"}
    reentries = []
    for j, e in enumerate(events):
        s, f = spans[j]
        if s not in starts or j == 0:
            continue
        prev = events[j - 1]
        c = int(prev["emitted_at_index"])
        gap = np.arange(c + 1, s)
        cat = categorize((s, f), signs, credited_by, j, negative)
        reentries.append(
            {
                "category": cat,
                "family": str(family[s]) if family is not None and cat == "NONSIGN" else "",
                "gap_obs": int(len(gap)),
                "gap_ms": float(t[s] - t[c]),
                "post_peak": float(probs[gap, 2].max()) if len(gap) else 0.0,
                "pre_peak": float(probs[gap, 0].max()) if len(gap) else 0.0,
                "prev_span_ms": float(prev["active_span_ms"]),
                "span_ms": float(e["active_span_ms"]),
                "entry_active": float(probs[s, 1]),
                "prev_category": categorize(spans[j - 1], signs, credited_by, j - 1, negative),
            }
        )
    return swallowed, reentries


def summarize(rows: list[dict], key: str) -> dict:
    return {
        k: float(np.median([r[key] for r in rows if r["category"] == k]))
        for k in sorted({r["category"] for r in rows})
    }


def main() -> None:
    pkg = er.load_s2(E, "ARM_A_E10")
    out: dict[str, Any] = {}
    cal = s2_r3_train.build_dataset(E, suite.read_json(s2_r3_train.CONFIG_PATH))["cal_streams"]
    sw, re_ = [], []
    for s in cal:
        signs = []
        for o in sorted(set(s["ordinals"].tolist()) - {-1}):
            rows = np.flatnonzero((s["ordinals"] == o) & (s["labels"] == 1))
            if len(rows):
                signs.append((int(rows[0]), int(rows[-1])))
        a, b = analyse(
            pkg.probabilities(s["features"]),
            s["timestamps_ms"],
            signs,
            s["kinds"] == s2_r3_train.NEGATIVE_KIND,
            s["negative_family"],
        )
        sw += a
        re_ += b
    out["cal"] = {"swallowed": sw, "reentries": re_}
    sw, re_ = [], []
    for s in bench.build_streams(E, 266.616):
        if s["mode"] != "CONTINUOUS":
            continue
        raw = s["raw"]
        t = np.asarray(raw.timestamp_ms, np.float64)
        neg = np.ones(len(t), bool)
        for x in s["signs"]:
            neg[x["first"] : x["last"] + 1] = False
        a, b = analyse(
            pkg.probabilities(suite.features_for_raw(raw, "v1")),
            t,
            [(x["first"], x["last"]) for x in s["signs"]],
            neg,
            None,
        )
        sw += a
        re_ += b
    out["dev_continuous"] = {"swallowed": sw, "reentries": re_}
    for part, d in out.items():
        sw, re_ = d["swallowed"], d["reentries"]
        print(
            part,
            "swallowed",
            len(sw),
            "median ms since commit",
            np.median([x["ms_since_commit"] for x in sw]) if sw else None,
            "obs dist",
            dict(sorted(Counter(x["obs_since_commit"] for x in sw).items())),
        )
        print(
            "   reentry outcomes",
            dict(Counter(r["category"] + (":" + r["family"] if r["family"] else "") for r in re_)),
        )
        for key in ("gap_obs", "post_peak", "pre_peak", "prev_span_ms", "span_ms", "entry_active"):
            print(f"   median {key:13s}", {k: round(v, 3) for k, v in summarize(re_, key).items()})
        print(
            "   prev_category of NONSIGN re-entries",
            dict(Counter(r["prev_category"] for r in re_ if r["category"] == "NONSIGN")),
        )
        print(
            "   prev_category of GENUINE re-entries",
            dict(Counter(r["prev_category"] for r in re_ if r["category"] == "GENUINE")),
        )
    (HERE / "rearm_probe.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
