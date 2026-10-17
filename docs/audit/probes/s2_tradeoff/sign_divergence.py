"""Where does Arm I lose the genuine signs Arm A gets? (diagnosis; no training)

Same inputs, frozen WORD, BASELINE and CONFIRM_BOUNDARY_70 decoders. Models: production S2-R2,
Arm A e10 (reference), Arm A e21, Arm B e9 (body dropout), Arm I e28 (body dropout + IPN).
Per genuine sign and model, the first failing stage:
  NOT_ACQUIRED      no observation of the sign has argmax ACTIVE
  NO_EVENT          ACTIVE inside the sign but no event overlaps it (lifecycle: too short, re-arm)
  MERGED            only a shared event overlaps it (credited to another sign)
  WRONG_WORD        its own event, wrong WORD top-1
  CORRECT
plus the S2 trace inside the sign (peak / mean P(ACTIVE), ACTIVE rows, first ACTIVE offset) and
the sign's perception evidence (accepted hands, both hands, body, wrist travel, handshape change).
PHONE  reviewed genuine signs of the 4 Tier-2 sessions + shadow 023004Z (development-exposed).
DEV    held-out ASL signers, CONTINUOUS stitched streams (heldout_dev_e2e; independent signers).
Writes sign_divergence.json.
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
MODELS = ("S2_R2", "ARM_A_E10", "ARM_A_E21", "ARM_B_E9", "ARM_I_E28")
DECODERS = ("BASELINE", "CONFIRM_BOUNDARY_70")


def evidence(raw: Any, a: int, b: int) -> dict[str, float]:
    hands = np.asarray(raw.hand_observed, bool)[a : b + 1]
    return {
        "hand_fraction": float(hands.any(axis=1).mean()),
        "both_hands_fraction": float(hands.all(axis=1).mean()),
        "body_fraction": float(np.asarray(raw.body_available, bool)[a : b + 1].mean()),
        **er.motion(raw, a, b),
    }


def stage(
    states: np.ndarray,
    sign: dict,
    events: list[tuple[int, int]],
    credited: dict,
    k: int,
    correct: bool | None,
) -> str:
    rows = slice(sign["first"], sign["last"] + 1)
    if not np.any(states[rows] == 1):
        return "NOT_ACQUIRED"
    hits = [j for j, (s, f) in enumerate(events) if max(s, sign["first"]) <= min(f, sign["last"])]
    if not hits:
        return "NO_EVENT"
    if credited.get(k) is None:
        return "MERGED"
    return "CORRECT" if correct else "WRONG_WORD"


def score_stream(
    raw: Any, probs: np.ndarray, signs: list[dict], decoder: str, word: er.Word, gloss_of: Any
) -> list[dict[str, Any]]:
    t = np.asarray(raw.timestamp_ms, np.float64)
    states = np.argmax(probs, axis=1)
    events = er.replay_events(probs, t, decoder)
    spans = [
        (int(e["logical_active_start_index"]), int(e["logical_active_end_index"])) for e in events
    ]
    credited: dict[int, int] = {}
    used: set[int] = set()
    for k, sign in enumerate(signs):
        hits = [
            j for j, (s, f) in enumerate(spans) if max(s, sign["first"]) <= min(f, sign["last"])
        ]
        d = next((j for j in hits if j not in used), None)
        if d is not None:
            used.add(d)
            credited[k] = d
    windows = [er.window_of(t, e) for e in events]
    top = {}
    if credited:
        idx = sorted(set(credited.values()))
        probs_w = word.probabilities([suite.slice_raw(raw, *windows[j]) for j in idx])
        top = {j: word.glosses[int(np.argmax(p))] for j, p in zip(idx, probs_w, strict=True)}
    out = []
    for k, sign in enumerate(signs):
        rows = np.arange(sign["first"], sign["last"] + 1)
        active = np.flatnonzero(states[rows] == 1)
        j = credited.get(k)
        correct = None if j is None else top[j] == gloss_of(sign)
        out.append(
            {
                "stage": stage(states, sign, spans, credited, k, correct),
                "peak_active": float(np.clip(probs[rows, 1], 0, 1).max()),
                "mean_active": float(np.clip(probs[rows, 1], 0, 1).mean()),
                "active_rows": int(len(active)),
                "first_active_offset": int(active[0]) if len(active) else None,
                "event_span": list(spans[j]) if j is not None else None,
            }
        )
    return out


def run_phone(word: er.Word, packages: dict[str, suite.Package]) -> list[dict[str, Any]]:
    sessions = {
        k: v for k, v in er.phone_sessions(E).items() if v["kind"] != "SHADOW_PROTOCOL_ONLY"
    }
    rows = []
    for name, s in sessions.items():
        raw = s["capture"].raw
        signs = sorted(s["positives"], key=lambda x: x["first"])
        base = [
            {
                "session": name,
                "sign": x["name"],
                "gloss": x["name"].split("#")[0].split(":")[-1],
                "rows": x["last"] - x["first"] + 1,
                **evidence(raw, x["first"], x["last"]),
            }
            for x in signs
        ]
        for m, pkg in packages.items():
            probs = pkg.probabilities(s["features"])
            for dec in DECODERS:
                res = score_stream(
                    raw, probs, signs, dec, word, lambda x: x["name"].split("#")[0].split(":")[-1]
                )
                for b, r in zip(base, res, strict=True):
                    b[f"{m}:{dec}"] = r
        rows += base
    return rows


def run_dev(word: er.Word, packages: dict[str, suite.Package]) -> list[dict[str, Any]]:
    rows = []
    for k, stream in enumerate(bench.build_streams(E, 266.616)):
        if stream["mode"] != "CONTINUOUS":
            continue
        raw = stream["raw"]
        feats = suite.features_for_raw(raw, "v1")
        base = [
            {
                "stream": k,
                "signer": stream["signer"],
                "gloss": x["gloss"],
                "rows": x["last"] - x["first"] + 1,
                **evidence(raw, x["first"], x["last"]),
            }
            for x in stream["signs"]
        ]
        for m, pkg in packages.items():
            probs = pkg.probabilities(feats)
            for dec in DECODERS:
                res = score_stream(raw, probs, stream["signs"], dec, word, lambda x: x["gloss"])
                for b, r in zip(base, res, strict=True):
                    b[f"{m}:{dec}"] = r
        rows += base
    return rows


def summarize(rows: list[dict[str, Any]], dec: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for m in MODELS:
        out[m] = dict(Counter(r[f"{m}:{dec}"]["stage"] for r in rows))
    lost = [
        r
        for r in rows
        if r[f"ARM_A_E10:{dec}"]["stage"] == "CORRECT"
        and r[f"ARM_I_E28:{dec}"]["stage"] != "CORRECT"
    ]
    kept = [
        r
        for r in rows
        if r[f"ARM_A_E10:{dec}"]["stage"] == "CORRECT"
        and r[f"ARM_I_E28:{dec}"]["stage"] == "CORRECT"
    ]
    out["A_correct_I_lost_by_I_stage"] = dict(Counter(r[f"ARM_I_E28:{dec}"]["stage"] for r in lost))
    out["A_correct_I_lost_by_B_stage"] = dict(Counter(r[f"ARM_B_E9:{dec}"]["stage"] for r in lost))
    out["I_correct_A_lost"] = sum(
        1
        for r in rows
        if r[f"ARM_I_E28:{dec}"]["stage"] == "CORRECT"
        and r[f"ARM_A_E10:{dec}"]["stage"] != "CORRECT"
    )
    keys = (
        "hand_fraction",
        "both_hands_fraction",
        "body_fraction",
        "motion_wrist_travel_per_s",
        "motion_shape_change",
        "rows",
    )
    for name, group in (("lost", lost), ("kept", kept)):
        out[f"evidence_{name}"] = {
            k: float(np.mean([r[k] for r in group])) if group else None for k in keys
        }
        out[f"evidence_{name}"]["n"] = len(group)
        for m in ("ARM_A_E10", "ARM_B_E9", "ARM_I_E28"):
            out[f"evidence_{name}"][f"{m}_peak_median"] = (
                float(np.median([r[f"{m}:{dec}"]["peak_active"] for r in group])) if group else None
            )
    return out


def main() -> None:
    word = er.Word(E, er.FROZEN_WORD, er.FROZEN_WORD_SHA)
    packages = {m: er.load_s2(E, m) for m in MODELS}
    phone = run_phone(word, packages)
    dev = run_dev(word, packages)
    out = {
        "phone": {"signs": phone, "summary": {d: summarize(phone, d) for d in DECODERS}},
        "dev_continuous": {
            "n_signs": len(dev),
            "summary": {d: summarize(dev, d) for d in DECODERS},
        },
        "dev_signs": dev,
    }
    (HERE / "sign_divergence.json").write_text(json.dumps(out, indent=1, default=float))
    for part in ("phone", "dev_continuous"):
        for d in DECODERS:
            print(part, d, json.dumps(out[part]["summary"][d], default=float), flush=True)
    print("phone A-correct / I-lost signs:")
    for r in phone:
        a, i = r["ARM_A_E10:CONFIRM_BOUNDARY_70"], r["ARM_I_E28:CONFIRM_BOUNDARY_70"]
        if a["stage"] == "CORRECT" and i["stage"] != "CORRECT":
            b = r["ARM_B_E9:CONFIRM_BOUNDARY_70"]
            print(
                f"  {r['session'][:12]:12s} {r['sign'][:26]:26s} rows={r['rows']:2d} "
                f"hand={r['hand_fraction']:.2f} body={r['body_fraction']:.2f} | "
                f"A peak={a['peak_active']:.2f} act={a['active_rows']} | "
                f"B {b['stage']} peak={b['peak_active']:.2f} | "
                f"I {i['stage']} peak={i['peak_active']:.2f} act={i['active_rows']}"
            )


if __name__ == "__main__":
    main()
