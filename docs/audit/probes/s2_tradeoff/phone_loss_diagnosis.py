"""Why does Arm I + R1 + CB recognise fewer phone words than Arm A + CB? Sign by sign.

Reviewed genuine phone signs (4 Tier-2 sessions + shadow 023004Z; development-exposed, diagnostic).
Configurations (frozen WORD): ARM_A_E10 + CONFIRM_BOUNDARY_70 (reference), ARM_I_E28 + R1_CB70
(CAL-selected decoder for Arm I), ARM_I_E28 + R2_CB70_PRE_EXIT_POST (diagnostic).
For every sign one configuration gets right and another does not: first failing stage, the argmax
state string over the sign (+/-3 observations; P=PRE A=ACTIVE O=POST, '|' marks the sign span),
P(ACTIVE) peak, the reference decoder actions on the sign rows, the event window, WORD top-1 for
its own event, and the sign's perception evidence. Writes phone_loss_diagnosis.json.
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
sys.path.insert(0, str(Path(__file__).parent))

import sign_divergence as sd  # noqa: E402

from eval.runtime_diagnostics import event_reliability as er  # noqa: E402
from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics.event_separation import VARIANTS, use_variant  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
HERE = Path(__file__).parent
CONFIGS = (
    ("ARM_A_E10", "CONFIRM_BOUNDARY_70"),
    ("ARM_I_E28", "R1_CB70"),
    ("ARM_I_E28", "R2_CB70_PRE_EXIT_POST"),
)
CHARS = "PAO"


def actions(probs: np.ndarray, t: np.ndarray, decoder: str) -> list[str]:
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
        trace = suite.replay(rows, allow_post_rearm=True, exact_android_commit_recovery=True)[
            "trace"
        ]
    return [str(r["action"]) for r in trace]


def main() -> None:
    word = er.Word(E, er.FROZEN_WORD, er.FROZEN_WORD_SHA)
    sessions = {
        k: v for k, v in er.phone_sessions(E).items() if v["kind"] != "SHADOW_PROTOCOL_ONLY"
    }
    pk = {m: er.load_s2(E, m) for m in {c[0] for c in CONFIGS}}
    signs_out: list[dict[str, Any]] = []
    for name, s in sessions.items():
        raw, t = s["capture"].raw, s["timestamps_ms"]
        signs = sorted(s["positives"], key=lambda x: x["first"])
        probs = {m: p.probabilities(s["features"]) for m, p in pk.items()}
        per_cfg = {}
        acts = {}
        for m, dec in CONFIGS:
            res = sd.score_stream(
                raw, probs[m], signs, dec, word, lambda x: x["name"].split("#")[0].split(":")[-1]
            )
            per_cfg[f"{m}:{dec}"] = res
            acts[f"{m}:{dec}"] = actions(probs[m], t, dec)
        for k, sign in enumerate(signs):
            a, b = sign["first"], sign["last"]
            lo, hi = max(0, a - 3), min(len(t) - 1, b + 3)
            row = {
                "session": name,
                "sign": sign["name"],
                "gloss": sign["name"].split("#")[0].split(":")[-1],
                "rows": b - a + 1,
                **sd.evidence(raw, a, b),
            }
            for key, res in per_cfg.items():
                m = key.split(":")[0]
                states = np.argmax(probs[m], axis=1)
                text = "".join(CHARS[int(states[i])] for i in range(lo, hi + 1))
                cut_a, cut_b = a - lo, b - lo + 1
                r = res[k]
                row[key] = {
                    **r,
                    "states": text[:cut_a] + "|" + text[cut_a:cut_b] + "|" + text[cut_b:],
                    "actions": [x for x in acts[key][a : b + 4] if x != "NO_CHANGE"],
                }
                if r["event_span"]:
                    s0, s1 = r["event_span"]
                    w = er.window_of(
                        t,
                        {
                            "logical_active_start_index": s0,
                            "logical_active_end_index": s1,
                            "first_post_index": min(s1 + 1, len(t) - 1),
                            "emitted_at_index": min(s1 + 1, len(t) - 1),
                        },
                    )
                    p = word.probabilities([suite.slice_raw(raw, *w)])[0]
                    row[key]["word_top1"] = word.glosses[int(np.argmax(p))]
                    row[key]["word_p1"] = float(np.max(p))
            signs_out.append(row)
    ref, cand, diag = (f"{m}:{d}" for m, d in CONFIGS)
    lost = [r for r in signs_out if r[ref]["stage"] == "CORRECT" and r[cand]["stage"] != "CORRECT"]
    gained = [
        r for r in signs_out if r[cand]["stage"] == "CORRECT" and r[ref]["stage"] != "CORRECT"
    ]
    out = {
        "configs": [f"{m}:{d}" for m, d in CONFIGS],
        "stage_counts": {
            key: dict(Counter(r[key]["stage"] for r in signs_out)) for key in (ref, cand, diag)
        },
        "lost_by_candidate_stage": dict(Counter(r[cand]["stage"] for r in lost)),
        "lost_recovered_by_diagnostic": sum(1 for r in lost if r[diag]["stage"] == "CORRECT"),
        "gained": len(gained),
        "signs": signs_out,
    }
    (HERE / "phone_loss_diagnosis.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: v for k, v in out.items() if k != "signs"}, indent=1))
    for label, group in (
        ("LOST (Arm A + CB correct, Arm I + R1 + CB not)", lost),
        ("GAINED", gained),
    ):
        print("\n" + label)
        for r in group:
            print(
                f"  {r['session'][:12]:12s} {r['sign'][:28]:28s} rows={r['rows']:2d} "
                f"hand={r['hand_fraction']:.2f} both={r['both_hands_fraction']:.2f} "
                f"body={r['body_fraction']:.2f}"
            )
            for key in (ref, cand, diag):
                x = r[key]
                print(
                    f"      {key:34s} {x['stage']:12s} peak={x['peak_active']:.2f} "
                    f"states={x['states']:22s} word={x.get('word_top1', '-')} "
                    f"{x.get('word_p1', 0):.2f} acts={x['actions'][:5]}"
                )


if __name__ == "__main__":
    main()
