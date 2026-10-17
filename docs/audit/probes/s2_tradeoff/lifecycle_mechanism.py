"""Why are acquired signs given no event? Decoder-trace attribution (diagnosis; no training).

For every genuine sign that a model acquires (argmax ACTIVE on >= 1 sign row) but that gets no
overlapping event, the reference lifecycle trace (production decoder) names the mechanism:
  SWALLOWED_IN_REARM     all ACTIVE rows of the sign arrive in EVENT_EMITTED_WAIT_REARM
  DISCARD_TOO_SHORT      a candidate starts in the sign but emits with span < minimum_active_ms
  DISCARD_PRE_GAP        a candidate starts in the sign and is dropped by a sustained PRE gap
  OTHER                  anything else (e.g. still open at stream end)
Also, per model, the exit state after every ACTIVE run inside genuine signs (next non-ACTIVE
argmax: PRE or POST) and the run-length distribution, on held-out DEV continuous streams and phone.
Writes lifecycle_mechanism.json.
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

E = Path("F:/ASL DATASET/5. Apphear3")
HERE = Path(__file__).parent
MODELS = tuple(sys.argv[1:]) or ("ARM_A_E10", "ARM_A_E21", "ARM_B_E9", "ARM_I_E28")


def trace_of(probs: np.ndarray, t: np.ndarray) -> dict[str, Any]:
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
    return suite.replay(rows, allow_post_rearm=True, exact_android_commit_recovery=True)


def mechanisms(
    probs: np.ndarray, t: np.ndarray, signs: list[dict]
) -> tuple[Counter, Counter, Counter]:
    rep = trace_of(probs, t)
    trace, events = rep["trace"], rep["events"]
    states = np.argmax(probs, axis=1)
    spans = [
        (int(e["logical_active_start_index"]), int(e["logical_active_end_index"])) for e in events
    ]
    mech: Counter = Counter()
    exits: Counter = Counter()
    runs: Counter = Counter()
    for sign in signs:
        a, b = sign["first"], sign["last"]
        act = [i for i in range(a, b + 1) if states[i] == 1]
        # exit state and run lengths of ACTIVE runs that start inside the sign
        i = a
        while i <= b:
            if states[i] == 1:
                j = i
                while j + 1 < len(states) and states[j + 1] == 1:
                    j += 1
                runs[min(j - i + 1, 5)] += 1
                nxt = j + 1
                exits[
                    (
                        "PRE"
                        if nxt < len(states) and states[nxt] == 0
                        else "POST" if nxt < len(states) else "END"
                    )
                ] += 1
                i = j + 1
            else:
                i += 1
        if not act or any(max(s, a) <= min(f, b) for s, f in spans):
            continue
        before = [trace[i]["state_before"] if "state_before" in trace[i] else None for i in act]
        actions = [trace[i]["action"] for i in act]
        if (
            all(str(x).endswith("EVENT_EMITTED_WAIT_REARM") for x in before if x is not None)
            and before[0] is not None
        ):
            mech["SWALLOWED_IN_REARM"] += 1
            continue
        start = next(
            (i for i, x in zip(act, actions, strict=True) if x == "START_ACTIVE_CANDIDATE"), None
        )
        if start is None:
            mech["OTHER"] += 1
            continue
        fate = next(
            (
                trace[k]["action"]
                for k in range(start + 1, len(trace))
                if trace[k]["action"]
                in ("EMIT_SIGN_EVENT", "DISCARD_TOO_SHORT", "DISCARD_SUSTAINED_PRE_GAP")
            ),
            "OPEN_AT_END",
        )
        mech[
            {
                "DISCARD_TOO_SHORT": "DISCARD_TOO_SHORT",
                "DISCARD_SUSTAINED_PRE_GAP": "DISCARD_PRE_GAP",
            }.get(fate, "OTHER")
        ] += 1
    return mech, exits, runs


def main() -> None:
    packages = {m: er.load_s2(E, m) for m in MODELS}
    out: dict[str, Any] = {}
    sessions = {
        k: v for k, v in er.phone_sessions(E).items() if v["kind"] != "SHADOW_PROTOCOL_ONLY"
    }
    dev = [s for s in bench.build_streams(E, 266.616) if s["mode"] == "CONTINUOUS"]
    for m, pkg in packages.items():
        agg = {
            "phone": [Counter(), Counter(), Counter()],
            "dev_continuous": [Counter(), Counter(), Counter()],
        }
        for s in sessions.values():
            res = mechanisms(pkg.probabilities(s["features"]), s["timestamps_ms"], s["positives"])
            for c, r in zip(agg["phone"], res, strict=True):
                c.update(r)
        for s in dev:
            raw = s["raw"]
            res = mechanisms(
                pkg.probabilities(suite.features_for_raw(raw, "v1")),
                np.asarray(raw.timestamp_ms, np.float64),
                s["signs"],
            )
            for c, r in zip(agg["dev_continuous"], res, strict=True):
                c.update(r)
        out[m] = {
            part: {
                "no_event_mechanism": dict(c[0]),
                "exit_after_active_run": dict(c[1]),
                "active_run_length": dict(sorted(c[2].items())),
            }
            for part, c in agg.items()
        }
        print(m, json.dumps(out[m]), flush=True)
    (HERE / "lifecycle_mechanism.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
