"""CAL selection of re-arm variants (Arm A e10), original rule and label-contract-corrected count.

Rule (event_separation/select_on_cal.py, unchanged): among variants with split rate <= BASELINE
+ 0.02 and non-sign events <= 1.10 x BASELINE, choose the highest distinct-sign rate.
Non-sign events are counted two ways:
  neg_ev            logical span only on negative-kind rows (original count)
  neg_ev_scored     logical span only on negative rows labelled PRE, i.e. excluding the
                    join_ignore rows after every raw-level splice, which the training label
                    contract already leaves unscored (correction made 2026-10-17 after 8 of 14
                    re-entry non-sign events were found on splice rows; applied to every variant)
Writes cal_rearm_selection.json.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics import event_reliability as er  # noqa: E402
from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics import s2_r3_train  # noqa: E402
from eval.runtime_diagnostics.event_separation import VARIANTS, use_variant  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
HERE = Path(__file__).parent
NAMES = ("BASELINE", "CONFIRM_BOUNDARY_70", "REENTRY_1", "REENTRY_2", "R1_CB70", "R2_CB70")
EXTRA = (
    "PRE_EXIT_POST",
    "CB70_PRE_EXIT_POST",
    "R2_PRE_EXIT_POST",
    "R2_CB70_PRE_EXIT_POST",
    "R1_CBN70",
    "R1_CBN70_PRE_EXIT_POST",
)


def score(streams: list[dict], probs: list[np.ndarray]) -> dict[str, float]:
    t = defaultdict(float)
    for stream, p in zip(streams, probs, strict=True):
        ts = stream["timestamps_ms"]
        states = np.argmax(p, axis=1)
        events = suite.replay(
            [
                {
                    "source_index": i,
                    "source_timestamp_ms": float(ts[i]),
                    "argmax_state": int(states[i]),
                    "pre_probability": float(p[i, 0]),
                    "active_probability": float(p[i, 1]),
                    "post_probability": float(p[i, 2]),
                }
                for i in range(len(ts))
            ],
            allow_post_rearm=True,
            exact_android_commit_recovery=True,
        )["events"]
        spans = {}
        for o in sorted(set(stream["ordinals"].tolist()) - {-1}):
            rows = np.flatnonzero((stream["ordinals"] == o) & (stream["labels"] == 1))
            if len(rows):
                spans[o] = (int(rows[0]), int(rows[-1]))
        credited: set[int] = set()
        per_event: dict[int, int] = defaultdict(int)
        for a, b in spans.values():
            hits = [
                j
                for j, e in enumerate(events)
                if max(a, e["logical_active_start_index"]) <= min(b, e["logical_active_end_index"])
            ]
            for j in hits:
                per_event[j] += 1
            t["signs"] += 1
            t["split"] += float(len(hits) > 1)
            d = next((j for j in hits if j not in credited), None)
            if d is not None:
                credited.add(d)
                t["distinct"] += 1
        t["merged"] += sum(1 for c in per_event.values() if c > 1)
        neg = stream["kinds"] == s2_r3_train.NEGATIVE_KIND
        scored = neg & (stream["labels"] == 0)
        for e in events:
            a, b = int(e["logical_active_start_index"]), int(e["logical_active_end_index"])
            t["neg_ev"] += float(bool(np.all(neg[a : b + 1])))
            t["neg_ev_scored"] += float(bool(np.all(scored[a : b + 1])))
        t["events"] += len(events)
    return {**t, "distinct_rate": t["distinct"] / t["signs"], "split_rate": t["split"] / t["signs"]}


def select(results: dict, key: str) -> dict:
    base = results["BASELINE"]
    eligible = [
        n
        for n in results
        if results[n]["split_rate"] <= base["split_rate"] + 0.02
        and results[n][key] <= 1.10 * base[key]
    ]
    return {
        "eligible": eligible,
        "selected": max(eligible, key=lambda n: results[n]["distinct_rate"]),
    }


def main() -> None:
    cal = s2_r3_train.build_dataset(E, suite.read_json(s2_r3_train.CONFIG_PATH))["cal_streams"]
    s2 = sys.argv[1] if len(sys.argv) > 1 else "ARM_A_E10"
    names = NAMES + (EXTRA if s2 != "ARM_A_E10" else ())
    pkg = er.load_s2(E, s2)
    probs = [pkg.probabilities(s["features"]) for s in cal]
    results = {}
    for name in names:
        with use_variant(next(v for v in VARIANTS if v.name == name)):
            results[name] = score(cal, probs)
        r = results[name]
        print(
            f"{name:20s} distinct={r['distinct_rate']:.3f} split={r['split_rate']:.4f} "
            f"neg_ev={r['neg_ev']:.0f} neg_ev_scored={r['neg_ev_scored']:.0f} "
            f"merged={r['merged']:.0f} events={r['events']:.0f}",
            flush=True,
        )
    out = {
        "s2": "ARM_A_E10",
        "results": results,
        "original_rule": select(results, "neg_ev"),
        "label_contract_rule": select(results, "neg_ev_scored"),
    }
    print("original rule:", out["original_rule"])
    print("label-contract rule:", out["label_contract_rule"])
    suffix = "" if s2 == "ARM_A_E10" else f"_{s2}"
    (HERE / f"cal_rearm_selection{suffix}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
