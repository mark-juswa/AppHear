"""Paired phone failure matrix: earliest responsible stage per genuine sign, per configuration.

Reviewed genuine phone signs (4 Tier-2 sessions + shadow 023004Z; development-exposed,
diagnostic). Frozen WORD throughout. Configurations:
  PRODUCTION            S2-R2 + production decoder
  ARM_A_CB              Arm A e10 + CONFIRM_BOUNDARY_70
  ARM_A_R1_CB           Arm A e10 + R1_CB70 (re-entry + confirm-boundary)
  ARM_I_R1_CB           Arm I e28 + R1_CB70 (CAL-selected decoder for Arm I)
Per sign (configuration-independent):
  perception_adequate   >= 4 observations and accepted-hand fraction >= 0.5 (stage_attribution)
  oracle_correct        frozen WORD top-1 on the human-boundary window through the runtime
                        materializer (+/-250 ms) - what the classifier can do on an ideal window
Per sign and configuration, the earliest failing stage:
  PERCEPTION            evidence inadequate and the sign is not recognised
  S2_NOT_ACQUIRED       no ACTIVE observation inside the sign
  LIFECYCLE_SWALLOWED   ACTIVE only while waiting to re-arm
  LIFECYCLE_DISCARDED   a candidate started but was discarded (too short / sustained PRE gap)
  MERGED                only a shared event (credited to another sign)
  WINDOW                own event, wrong word, but the ideal window is correct
  CLASSIFIER            own event, wrong word, and the ideal window is also wrong
  CORRECT
plus commit latency (emission time - last reviewed sign observation) and window contamination
(the event window covers >= 50% of another reviewed sign). Writes phone_failure_matrix.json.
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
sys.path.insert(0, str(REPO / "docs/audit/probes/pipeline_v3"))

import stage_attribution as sa  # noqa: E402

from eval.runtime_diagnostics import event_reliability as er  # noqa: E402
from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics.event_separation import VARIANTS, use_variant  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
HERE = Path(__file__).parent
CONFIGS = {
    "PRODUCTION": ("S2_R2", "BASELINE"),
    "ARM_A_CB": ("ARM_A_E10", "CONFIRM_BOUNDARY_70"),
    "ARM_A_R1_CB": ("ARM_A_E10", "R1_CB70"),
    "ARM_I_R1_CB": ("ARM_I_E28", "R1_CB70"),
}


def gloss_of(name: str) -> str:
    return name.split("#")[0].split(":")[-1]


def replay(probs: np.ndarray, t: np.ndarray, decoder: str) -> dict[str, Any]:
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
    with use_variant(next(v for v in VARIANTS if v.name == decoder)):
        return suite.replay(rows, allow_post_rearm=True, exact_android_commit_recovery=True)


def main() -> None:
    word = er.Word(E, er.FROZEN_WORD, er.FROZEN_WORD_SHA)
    sessions = {
        k: v for k, v in er.phone_sessions(E).items() if v["kind"] != "SHADOW_PROTOCOL_ONLY"
    }
    pk = {m: er.load_s2(E, m) for m in {c[0] for c in CONFIGS.values()}}
    rows: list[dict[str, Any]] = []
    for name, s in sessions.items():
        raw, t = s["capture"].raw, s["timestamps_ms"]
        signs = sorted(s["positives"], key=lambda x: x["first"])
        spans = [(x["first"], x["last"]) for x in signs]
        oracle_windows = [sa.oracle_ctx_window(t, a, b) for a, b in spans]
        oracle_p = word.probabilities([suite.slice_raw(raw, *w) for w in oracle_windows])
        base = []
        for k, sign in enumerate(signs):
            a, b = spans[k]
            hands = np.asarray(raw.hand_observed, bool)[a : b + 1]
            proposals = np.asarray(raw.hand_proposal_present, bool)[a : b + 1]
            base.append(
                {
                    "session": name,
                    "sign": sign["name"],
                    "gloss": gloss_of(sign["name"]),
                    "observations": b - a + 1,
                    "hand_fraction": float(hands.any(axis=1).mean()),
                    "proposal_fraction": float(proposals.any(axis=1).mean()),
                    "body_fraction": float(np.asarray(raw.body_available, bool)[a : b + 1].mean()),
                    "cadence_ms": float(np.median(np.diff(t[max(0, a - 1) : b + 2]))),
                    "perception_adequate": bool(b - a + 1 >= 4 and hands.any(axis=1).mean() >= 0.5),
                    "oracle_top1": word.glosses[int(np.argmax(oracle_p[k]))],
                    "oracle_correct": word.glosses[int(np.argmax(oracle_p[k]))]
                    == gloss_of(sign["name"]),
                }
            )
        for label, (m, dec) in CONFIGS.items():
            probs = pk[m].probabilities(s["features"])
            states = np.argmax(probs, axis=1)
            rep = replay(probs, t, dec)
            events = rep["events"]
            trace = rep["trace"]
            ev_spans = [
                (int(e["logical_active_start_index"]), int(e["logical_active_end_index"]))
                for e in events
            ]
            windows = [er.window_of(t, e) for e in events]
            credited: dict[int, int] = {}
            used: set[int] = set()
            for k, (a, b) in enumerate(spans):
                hits = [j for j, (x, y) in enumerate(ev_spans) if max(x, a) <= min(y, b)]
                d = next((j for j in hits if j not in used), None)
                if d is not None:
                    used.add(d)
                    credited[k] = d
            tops = {}
            if credited:
                idx = sorted(set(credited.values()))
                p = word.probabilities([suite.slice_raw(raw, *windows[j]) for j in idx])
                tops = {
                    j: (word.glosses[int(np.argmax(q))], float(np.max(q)))
                    for j, q in zip(idx, p, strict=True)
                }
            for k, (a, b) in enumerate(spans):
                r = base[k]
                act = [i for i in range(a, b + 1) if states[i] == 1]
                j = credited.get(k)
                info: dict[str, Any] = {
                    "peak_active": float(np.clip(probs[a : b + 1, 1], 0, 1).max())
                }
                if j is not None:
                    top, p1 = tops[j]
                    w = windows[j]
                    others = [(x, y) for i2, (x, y) in enumerate(spans) if i2 != k]
                    contaminated = any(
                        (min(w[1], y) - max(w[0], x) + 1) >= 0.5 * (y - x + 1)
                        for x, y in others
                        if max(w[0], x) <= min(w[1], y)
                    )
                    info.update(
                        {
                            "word": top,
                            "word_p1": p1,
                            "window": list(w),
                            "window_contaminated": contaminated,
                            "commit_latency_ms": float(
                                t[int(events[j]["emitted_at_index"])] - t[b]
                            ),
                        }
                    )
                    if top == r["gloss"]:
                        stage = "CORRECT"
                    elif r["oracle_correct"]:
                        stage = "WINDOW"
                    else:
                        stage = "CLASSIFIER"
                elif not act:
                    stage = "S2_NOT_ACQUIRED"
                elif any(max(x, a) <= min(y, b) for x, y in ev_spans):
                    stage = "MERGED"
                elif all(trace[i]["state_before"] == "EVENT_EMITTED_WAIT_REARM" for i in act):
                    stage = "LIFECYCLE_SWALLOWED"
                else:
                    stage = "LIFECYCLE_DISCARDED"
                if stage != "CORRECT" and not r["perception_adequate"]:
                    stage = "PERCEPTION"
                info["stage"] = stage
                r[label] = info
        rows += base
    labels = list(CONFIGS)
    out: dict[str, Any] = {
        "configs": {k: list(v) for k, v in CONFIGS.items()},
        "signs": rows,
        "stage_counts": {lab: dict(Counter(r[lab]["stage"] for r in rows)) for lab in labels},
        "perception_inadequate": [
            r["sign"] + "@" + r["session"] for r in rows if not r["perception_adequate"]
        ],
        "oracle_correct": sum(r["oracle_correct"] for r in rows),
        "commit_latency_ms_median": {
            lab: float(
                np.median(
                    [r[lab]["commit_latency_ms"] for r in rows if "commit_latency_ms" in r[lab]]
                )
            )
            for lab in labels
        },
        "contaminated_windows": {
            lab: sum(1 for r in rows if r[lab].get("window_contaminated")) for lab in labels
        },
        "cadence_ms_median_by_session": {
            n: float(np.median([r["cadence_ms"] for r in rows if r["session"] == n]))
            for n in sessions
        },
    }
    (HERE / "phone_failure_matrix.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: v for k, v in out.items() if k != "signs"}, indent=1, default=float))
    print(
        f"\n{'session':12s} {'sign':26s} obs hand prop ora | "
        + " | ".join(f"{lab:>18s}" for lab in labels)
    )
    for r in rows:
        print(
            f"{r['session'][:12]:12s} {r['sign'][:26]:26s} {r['observations']:3d} "
            f"{r['hand_fraction']:.2f} {r['proposal_fraction']:.2f} "
            f"{'Y' if r['oracle_correct'] else 'n'}   | "
            + " | ".join(f"{r[lab]['stage'][:18]:>18s}" for lab in labels)
        )


if __name__ == "__main__":
    main()
