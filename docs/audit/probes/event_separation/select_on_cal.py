"""Select an event-separation variant on S2-R3 CAL streams only (pre-registered rule).

CAL streams: 240 seeded stitched streams from the 6 CAL signers and CAL negatives (P1, N0),
built exactly as in s2_r3_train.py; S2 = Arm A epoch 10 (diagnostic candidate). Per variant:
  distinct  sign ordinal with an event credited to it alone (one-to-one overlap matching)
  split     sign ordinal overlapped by >= 2 events (duplicate risk)
  merged    events overlapping >= 2 sign ordinals
  neg_ev    events whose logical ACTIVE span lies only on negative-block rows
Rule (fixed before any variant result was seen): among variants with split rate <= baseline + 0.02
and neg_ev <= 1.10 x baseline, choose the highest distinct rate; ties -> fewer rules.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics import s2_r3_train  # noqa: E402
from eval.runtime_diagnostics.event_separation import VARIANTS, use_variant  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
ARM_A = (
    E / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/s2_r3_arm_a_01"
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
        ordinals = sorted(set(stream["ordinals"].tolist()) - {-1})
        spans = {}
        for o in ordinals:
            rows = np.flatnonzero((stream["ordinals"] == o) & (stream["labels"] == 1))
            if len(rows):
                spans[o] = (int(rows[0]), int(rows[-1]))
        credited: set[int] = set()
        per_event = defaultdict(int)
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
        for e in events:
            a, b = int(e["logical_active_start_index"]), int(e["logical_active_end_index"])
            t["neg_ev"] += float(bool(np.all(neg[a : b + 1])))
        t["events"] += len(events)
    return {**t, "distinct_rate": t["distinct"] / t["signs"], "split_rate": t["split"] / t["signs"]}


def main() -> None:
    config = suite.read_json(s2_r3_train.CONFIG_PATH)
    data = s2_r3_train.build_dataset(E, config)
    streams = data["cal_streams"]
    package = suite.load_package(
        "ARM_A_E10", "v1", ARM_A / "epoch_10.keras", ARM_A / "normalization.json"
    )
    probs = [package.probabilities(s["features"]) for s in streams]
    results = {}
    for v in VARIANTS:
        with use_variant(v):
            results[v.name] = score(streams, probs)
        print(v.name, {k: round(x, 4) for k, x in results[v.name].items()}, flush=True)
    base = results["BASELINE"]
    eligible = [
        v
        for v in VARIANTS
        if results[v.name]["split_rate"] <= base["split_rate"] + 0.02
        and results[v.name]["neg_ev"] <= 1.10 * base["neg_ev"]
    ]
    rules = {
        v.name: int(v.reentry) + int(v.short_post) + int(v.max_active_ms is not None)
        for v in VARIANTS
    }
    chosen = max(eligible, key=lambda v: (results[v.name]["distinct_rate"], -rules[v.name]))
    out = {
        "s2": "ARM_A_E10",
        "cal_streams": len(streams),
        "results": results,
        "eligible": [v.name for v in eligible],
        "selected": chosen.name,
    }
    Path(__file__).with_name("cal_selection.json").write_text(json.dumps(out, indent=2))
    print("SELECTED", chosen.name, "eligible", out["eligible"])


if __name__ == "__main__":
    main()
