"""Paired phone replay: where each recognition configuration fails, sign by sign (research only).

Replays one or more exact-parity phone captures (raw-v1 observations recorded on the device)
through several S2 package + decoder configurations, the runtime materializer and the frozen WORD
recognizer (WORD v2 reported as shadow), and attributes every human-reviewed genuine sign to the
earliest failing stage:

  PERCEPTION            < 4 observations or accepted-hand fraction < 0.5, and not recognised
  S2_NOT_ACQUIRED       no ACTIVE observation inside the sign
  LIFECYCLE_SWALLOWED   ACTIVE only while waiting to re-arm
  LIFECYCLE_DISCARDED   a candidate started but was discarded (too short / sustained PRE gap)
  MERGED                only an event credited to another sign overlaps it
  WINDOW                own event, wrong word, but the human-boundary window (+/-250 ms through
                        the runtime materializer) is classified correctly
  CLASSIFIER            own event, wrong word, and the human-boundary window is also wrong
  CORRECT

It also counts events inside confirmed non-sign intervals, events in unreviewed or uncertain
intervals, duplicates, and the commit latency after the reviewed sign end. Label provenance is
carried into the output (BLINDED / UNBLINDED / PROTOCOL_ONLY) so prediction-exposed labels are
never reported as independent evidence. Offline replay establishes recognition behaviour on the
captured observations; it does not establish live latency, stability or UI behaviour.

Usage:
  python -m eval.runtime_diagnostics.phone_replay_compare --evidence-root ROOT \
      --capture REL/PATH/session_X [--capture ...] [--registry] [--configs S2:DECODER ...] --out F
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics import event_reliability as er  # noqa: E402
from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics.event_separation import VARIANTS, use_variant  # noqa: E402

REFERENCE_CONFIGS = {
    "PRODUCTION": ("S2_R2", "BASELINE"),
    "ARM_A_CB": ("ARM_A_E10", "CONFIRM_BOUNDARY_70"),
    "ARM_A_R1_CB": ("ARM_A_E10", "R1_CB70"),
    "ARM_I_R1_CB": ("ARM_I_E28", "R1_CB70"),
}
ADEQUATE_MIN_OBSERVATIONS = 4
ADEQUATE_MIN_HAND_FRACTION = 0.5
CONTEXT_MS = 250.0


def gloss_of(name: str) -> str:
    return name.split("#")[0].split(":")[-1]


def oracle_window(t: np.ndarray, first: int, last: int) -> tuple[int, int]:
    """Human-boundary window through the runtime materializer (stage_attribution.oracle_ctx)."""
    n = len(t)
    if last + 1 < n:
        return er.window_of(
            t,
            {
                "logical_active_start_index": first,
                "logical_active_end_index": last,
                "first_post_index": last + 1,
                "emitted_at_index": n - 1,
            },
        )
    before = np.flatnonzero(t <= t[first] - CONTEXT_MS)
    return (int(before[-1]) if len(before) else 0, n - 1)


def classify(
    *,
    adequate: bool,
    acquired: bool,
    credited_word: str | None,
    overlapped: bool,
    all_active_in_rearm: bool,
    gloss: str,
    oracle_correct: bool,
) -> str:
    """Earliest failing stage for one reviewed genuine sign under one configuration."""
    if credited_word is not None and credited_word == gloss:
        return "CORRECT"
    if credited_word is not None:
        stage = "WINDOW" if oracle_correct else "CLASSIFIER"
    elif not acquired:
        stage = "S2_NOT_ACQUIRED"
    elif overlapped:
        stage = "MERGED"
    elif all_active_in_rearm:
        stage = "LIFECYCLE_SWALLOWED"
    else:
        stage = "LIFECYCLE_DISCARDED"
    return stage if adequate else "PERCEPTION"


def label_provenance(capture: Path) -> str:
    path = capture / "transition_review/human_boundaries.json"
    if not path.exists():
        return "ATTEMPT_REVIEW"
    labels = json.loads(path.read_text(encoding="utf-8"))
    return "BLINDED" if labels.get("blinded_to_predictions") else "UNBLINDED"


def session_from_capture(root: Path, capture: str, name: str) -> dict[str, Any]:
    spec = {"capture": capture, "labels": "boundaries", "continuous_no_capture_pauses": True}
    return {
        **suite.load_tier2_session(root, name, spec, "v1", 2000),
        "kind": "CAPTURE",
        "provenance": label_provenance(root / capture),
    }


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


def compare_session(
    session: dict[str, Any],
    configs: dict[str, tuple[str, str]],
    packages: dict[str, suite.Package],
    word: er.Word,
    shadow: er.Word | None,
) -> dict[str, Any]:
    raw, t = session["capture"].raw, session["timestamps_ms"]
    signs = sorted(session["positives"], key=lambda x: x["first"])
    spans = [(x["first"], x["last"]) for x in signs]
    hands = np.asarray(raw.hand_observed, bool).any(axis=1)
    oracle = [oracle_window(t, a, b) for a, b in spans]
    oracle_p = word.probabilities([suite.slice_raw(raw, *w) for w in oracle])
    rows = []
    for k, sign in enumerate(signs):
        a, b = spans[k]
        rows.append(
            {
                "sign": sign["name"],
                "gloss": gloss_of(sign["name"]),
                "observations": b - a + 1,
                "hand_fraction": float(hands[a : b + 1].mean()),
                "proposal_fraction": float(
                    np.asarray(raw.hand_proposal_present, bool)[a : b + 1].any(axis=1).mean()
                ),
                "adequate": bool(
                    b - a + 1 >= ADEQUATE_MIN_OBSERVATIONS
                    and hands[a : b + 1].mean() >= ADEQUATE_MIN_HAND_FRACTION
                ),
                "oracle_word": word.glosses[int(np.argmax(oracle_p[k]))],
            }
        )
        rows[-1]["oracle_correct"] = rows[-1]["oracle_word"] == rows[-1]["gloss"]
    events_out: dict[str, Any] = {}
    for label, (s2_name, decoder) in configs.items():
        probs = packages[s2_name].probabilities(session["features"])
        states = np.argmax(probs, axis=1)
        rep = replay(probs, t, decoder)
        events, trace = rep["events"], rep["trace"]
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
        words: dict[int, str] = {}
        shadow_words: dict[int, str] = {}
        if events:
            batch = [suite.slice_raw(raw, *w) for w in windows]
            words = {
                j: word.glosses[int(np.argmax(p))] for j, p in enumerate(word.probabilities(batch))
            }
            if shadow is not None:
                shadow_words = {
                    j: shadow.glosses[int(np.argmax(p))]
                    for j, p in enumerate(shadow.probabilities(batch))
                }
        for k, (a, b) in enumerate(spans):
            act = [i for i in range(a, b + 1) if states[i] == 1]
            j = credited.get(k)
            r = rows[k]
            stage = classify(
                adequate=r["adequate"],
                acquired=bool(act),
                credited_word=words.get(j) if j is not None else None,
                overlapped=any(max(x, a) <= min(y, b) for x, y in ev_spans),
                all_active_in_rearm=bool(act)
                and all(trace[i]["state_before"] == "EVENT_EMITTED_WAIT_REARM" for i in act),
                gloss=r["gloss"],
                oracle_correct=r["oracle_correct"],
            )
            r[label] = {
                "stage": stage,
                "peak_active": float(np.clip(probs[a : b + 1, 1], 0, 1).max()),
                "word": words.get(j) if j is not None else None,
                "shadow_word": shadow_words.get(j) if j is not None else None,
                "commit_latency_ms": (
                    float(t[int(events[j]["emitted_at_index"])] - t[b]) if j is not None else None
                ),
            }
        categories: Counter[str] = Counter()
        for j, (x, y) in enumerate(ev_spans):
            if j in used:
                continue
            if any(max(x, a) <= min(y, b) for a, b in spans):
                categories["DUPLICATE_OR_SHARED"] += 1
            elif any(n["first"] <= x and y <= n["last"] for n in session["negatives"]):
                categories["CONFIRMED_NONSIGN"] += 1
            else:
                categories["UNREVIEWED_OR_UNCERTAIN"] += 1
        events_out[label] = {"events": len(events), **categories}
    provenance = session.get("provenance") or {
        "TIER2": "TIER2_REVIEW_DEVELOPMENT_EXPOSED",
        "SHADOW_HUMAN_UNBLINDED": "UNBLINDED",
    }.get(session.get("kind", ""), "UNKNOWN")
    return {"provenance": provenance, "signs": rows, "events": events_out}


def summarize(results: dict[str, Any], configs: dict[str, tuple[str, str]]) -> dict[str, Any]:
    signs = [r for v in results.values() for r in v["signs"]]
    out: dict[str, Any] = {
        "genuine_signs": len(signs),
        "oracle_correct": sum(r["oracle_correct"] for r in signs),
    }
    for label in configs:
        lat = [
            r[label]["commit_latency_ms"]
            for r in signs
            if r[label]["commit_latency_ms"] is not None
        ]
        out[label] = {
            "stages": dict(Counter(r[label]["stage"] for r in signs)),
            "correct": sum(1 for r in signs if r[label]["stage"] == "CORRECT"),
            "shadow_correct": sum(1 for r in signs if r[label]["shadow_word"] == r["gloss"]),
            "confirmed_nonsign_events": sum(
                v["events"][label].get("CONFIRMED_NONSIGN", 0) for v in results.values()
            ),
            "unreviewed_or_uncertain_events": sum(
                v["events"][label].get("UNREVIEWED_OR_UNCERTAIN", 0) for v in results.values()
            ),
            "duplicate_or_shared_events": sum(
                v["events"][label].get("DUPLICATE_OR_SHARED", 0) for v in results.values()
            ),
            "commit_latency_ms_median": float(np.median(lat)) if lat else None,
        }
    out["provenance"] = dict(Counter(v["provenance"] for v in results.values()))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument(
        "--capture", action="append", default=[], help="capture dir relative to root"
    )
    parser.add_argument(
        "--registry", action="store_true", help="include the reviewed phone registry"
    )
    parser.add_argument("--configs", nargs="*", help="LABEL=S2:DECODER (default: the 4 references)")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.evidence_root
    configs = (
        {c.split("=")[0]: tuple(c.split("=")[1].split(":")) for c in args.configs}
        if args.configs
        else REFERENCE_CONFIGS
    )
    sessions: dict[str, dict[str, Any]] = {}
    if args.registry:
        sessions.update(
            {
                k: v
                for k, v in er.phone_sessions(root).items()
                if v["kind"] != "SHADOW_PROTOCOL_ONLY"
            }
        )
    for capture in args.capture:
        sessions[Path(capture).name] = session_from_capture(root, capture, Path(capture).name)
    if not sessions:
        parser.error("give --capture and/or --registry")
    packages = {m: er.load_s2(root, m) for m in {c[0] for c in configs.values()}}
    word = er.Word(root, er.FROZEN_WORD, er.FROZEN_WORD_SHA)
    shadow = er.Word(root, er.V2_WORD)
    results = {n: compare_session(s, configs, packages, word, shadow) for n, s in sessions.items()}
    summary = summarize(results, configs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "configs": {k: list(v) for k, v in configs.items()},
                "summary": summary,
                "sessions": results,
            },
            indent=1,
            default=float,
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=1, default=float))


if __name__ == "__main__":
    main()
