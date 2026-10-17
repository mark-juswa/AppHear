"""WORD v3 (neighbour context) vs v2 vs frozen: clean DEV, neighbour contamination, phone.

A  Signer-disjoint DEV (816 span-cut clips), PHONE_01 sparse at 5.6 and 3.75 fps.
B  Contamination test on the same DEV signers from FULL-LENGTH video (independent of the TRAIN-side
   augmentation construction): window = sign span +/-250 ms; optionally followed by the lead-in and
   first 30% / 50% of the signer's next clip's span (NEXT_30 / NEXT_50 -- the merged-window failure
   seen on the phone) or preceded by the last 30% of the previous clip's span (PREV_30). Views at
   3.75 fps; paired exact McNemar between recognizers.
C  Phone: the 32 recorded device windows (human-reviewed labels from device_window_pairing.json),
   the two Stage-2 shadow sessions' device windows and human-boundary windows (session 023004Z
   human labels are UNBLINDED; session 022535Z uses protocol expectations only). Scored only;
   nothing here selects or tunes anything.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from math import comb
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "docs/audit/probes/pipeline_v3"))

import stage_attribution as sa  # noqa: E402

from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter import (  # noqa: E402
    subset_raw,
)
from eval.runtime_diagnostics.phone_s2_exact_parity_and_r2_decision import (  # noqa: E402
    load_capture,
)
from pipeline.perception_vnext.recognition_schema import (  # noqa: E402
    load_raw_sequence,
    select_nearest_unique,
)

E = Path("F:/ASL DATASET/5. Apphear3")
RU = E / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
DEVICE = E / "artifacts/recognition_v3_stage2_compact_device"
MODELS = {
    "frozen": None,
    "v2": RU / "word_track_robust_aug_02/best.keras",
    "v3": RU / "word_track_robust_aug_03/best.keras",
}
PHONE_STEP = 1000.0 / 3.75


def mcnemar(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    n01, n10 = int(np.sum(~a & b)), int(np.sum(a & ~b))
    n = n01 + n10
    p = min(1.0, 2 * sum(comb(n, k) for k in range(min(n01, n10) + 1)) / 2**n) if n else 1.0
    return {"fixed": n01, "broken": n10, "p": p}


def sparse(raw: Any, rng: np.random.Generator) -> Any:
    t = np.asarray(raw.timestamp_ms, np.float64)
    idx = select_nearest_unique(
        t, np.arange(t[0] + rng.uniform(0, PHONE_STEP), t[-1] + 1e-6, PHONE_STEP)
    )
    return subset_raw(raw, np.asarray(idx if len(idx) else [0], np.int32))


def contamination_windows(
    rng: np.random.Generator,
) -> tuple[dict[str, list[Any]], list[str], list[str]]:
    clips = suite.read_json(RU / "heldout_dev_fullvideo_raw_01/manifest.json")["clips"]
    clips = [c for c in clips if c["span_valid"]]
    by_signer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in clips:
        by_signer[c["signer"]].append(c)
    cache: dict[str, Any] = {}

    def raw_of(c: dict[str, Any]) -> Any:
        if c["sample_id"] not in cache:
            cache[c["sample_id"]] = load_raw_sequence(E / c["raw_path"])
        return cache[c["sample_id"]]

    def segment(c: dict[str, Any], kind: str, frac: float = 0.0) -> Any:
        raw = raw_of(c)
        t = np.asarray(raw.timestamp_ms, np.float64)
        on, off = c["span_onset_index"], c["span_release_index"]
        if kind == "core":
            lo = int(np.searchsorted(t, t[on] - 250.0))
            hi = int(np.searchsorted(t, t[off] + 250.0, side="right")) - 1
        elif kind == "next":  # the next sign's lead-in (250 ms) and its first `frac` of the span
            lo = int(np.searchsorted(t, t[on] - 250.0))
            hi = on + max(1, int(frac * (off - on + 1)))
        else:  # prev: the last `frac` of the previous sign's span
            lo = off - max(1, int(frac * (off - on + 1))) + 1
            hi = off
        return subset_raw(raw, np.arange(max(0, lo), min(len(t) - 1, hi) + 1, dtype=np.int32))

    windows: dict[str, list[Any]] = defaultdict(list)
    glosses, signers = [], []
    for signer in sorted(by_signer):
        group = by_signer[signer]
        order = rng.permutation(len(group))
        for k, i in enumerate(order):
            c = group[i]
            nxt = group[order[(k + 1) % len(order)]]
            prv = group[order[(k - 1) % len(order)]]
            core = segment(c, "core")
            windows["CLEAN"].append(sparse(core, rng))
            windows["NEXT_30"].append(
                sparse(suite.concat_raw([core, segment(nxt, "next", 0.3)], 33.3), rng)
            )
            windows["NEXT_50"].append(
                sparse(suite.concat_raw([core, segment(nxt, "next", 0.5)], 33.3), rng)
            )
            windows["PREV_30"].append(
                sparse(suite.concat_raw([segment(prv, "prev", 0.3), core], 33.3), rng)
            )
            glosses.append(c["gloss"])
            signers.append(signer)
    return windows, glosses, signers


def phone_windows() -> list[dict[str, Any]]:
    """(window, gloss or None, source) for every labelled phone window available."""
    out = []
    pairing = json.loads(
        (REPO / "docs/audit/probes/word_track/device_window_pairing.json").read_text()
    )
    by_session = defaultdict(list)
    for e in pairing["events"]:
        if e["label"] == "GENUINE":
            by_session[e["session"]].append(e)
    config = suite.read_json(suite.SUITES["03"][0])
    paths = {
        n: E / s["capture"]
        for n, s in config["tier2_sessions"].items()
        if isinstance(s, dict) and "capture" in s
    }
    paths["SEP21_S2FIT_EXACT"] = E / "phone_pull_s2_exact_parity/session_20260921T153138Z"
    for name, events in by_session.items():
        raw = load_capture(paths[name], require_full_session=False).raw
        t = np.asarray(raw.timestamp_ms, np.float64)
        logged = {
            json.loads(line)["event_id"]: json.loads(line)
            for line in (paths[name] / "events.jsonl").open()
        }
        for e in events:
            d = logged[e["event_id"]]
            idx = d.get("recognition_v2_source_indices") or list(
                range(d["materialized_start_index"], d["materialized_end_index"] + 1)
            )
            out.append(
                {
                    "window": suite._take(raw, np.asarray(idx), t[np.asarray(idx)]),
                    "gloss": e["gloss"],
                    "source": "RECORDED_DEVICE_WINDOW",
                }
            )
    session = DEVICE / "session_20261017T023004Z"
    labels = json.loads((session / "transition_review/human_boundaries.json").read_text())
    raw = load_capture(session, require_full_session=False).raw
    t = np.asarray(raw.timestamp_ms, np.float64)
    signs = [s for s in labels["signs"] if s["judgment"] == "GENUINE_SIGN"]
    for line in (session / "events.jsonl").open():
        d = json.loads(line)
        a, b = d["logical_active_start_index"], d["logical_active_end_index"]
        hit = next((s for s in signs if max(a, s["start_index"]) <= min(b, s["end_index"])), None)
        if hit:
            idx = np.asarray(d["recognition_v2_source_indices"])
            out.append(
                {
                    "window": suite._take(raw, idx, t[idx]),
                    "gloss": hit["gloss"],
                    "source": "SHADOW_023004Z_DEVICE_WINDOW (unblinded labels)",
                }
            )
    for s in signs:
        a, b = sa.oracle_ctx_window(t, s["start_index"], s["end_index"])
        out.append(
            {
                "window": suite.slice_raw(raw, a, b),
                "gloss": s["gloss"],
                "source": "SHADOW_023004Z_HUMAN_BOUNDARY (unblinded labels)",
            }
        )
    return out


def main() -> None:
    recs = {k: sa.Recognizer(E, v) for k, v in MODELS.items()}
    result: dict[str, Any] = {"identities": {k: r.sha256 for k, r in recs.items()}}
    dev = [json.loads(line) for line in open(E / sa.DATASET_INDEX) if '"split":"dev"' in line]
    raws = [load_raw_sequence(Path(r["raw_path"])) for r in dev]
    gl = [r["canonical_gloss"] for r in dev]
    result["A_dev"] = {}
    for fps in (5.606840672873506, 3.75):
        sa.PHONE_COMPLETED_FPS = fps
        c = {
            k: np.asarray(
                [
                    r.score(p, g)["correct"]
                    for p, g in zip(r.probabilities(raws, "phone_01_sparse"), gl, strict=True)
                ]
            )
            for k, r in recs.items()
        }
        result["A_dev"][f"{fps:.2f}fps"] = {
            **{k: float(v.mean()) for k, v in c.items()},
            "v3_vs_v2": mcnemar(c["v2"], c["v3"]),
            "v3_vs_frozen": mcnemar(c["frozen"], c["v3"]),
        }
    windows, glosses, signers = contamination_windows(np.random.default_rng(31))
    result["B_contamination"] = {}
    for cond, wins in windows.items():
        c = {
            k: np.asarray(
                [
                    r.score(p, g)["correct"]
                    for p, g in zip(r.probabilities(wins, "dense"), glosses, strict=True)
                ]
            )
            for k, r in recs.items()
        }
        result["B_contamination"][cond] = {
            **{k: float(v.mean()) for k, v in c.items()},
            "v3_vs_v2": mcnemar(c["v2"], c["v3"]),
            "v3_vs_frozen": mcnemar(c["frozen"], c["v3"]),
        }
    phone = phone_windows()
    result["C_phone"] = {}
    for source in sorted({p["source"] for p in phone}):
        sub = [p for p in phone if p["source"] == source]
        result["C_phone"][source] = {
            "n": len(sub),
            **{
                k: int(
                    sum(
                        r.score(pr, p["gloss"])["correct"]
                        for pr, p in zip(
                            r.probabilities([q["window"] for q in sub], "dense"), sub, strict=True
                        )
                    )
                )
                for k, r in recs.items()
            },
            "per_window": [
                [p["gloss"]]
                + [
                    recs[k].glosses[int(np.argmax(pr))]
                    for k, pr in (
                        (k, recs[k].probabilities([p["window"]], "dense")[0]) for k in recs
                    )
                ]
                for p in sub
            ],
        }
    out = REPO / "docs/audit/probes/word_track/word_v3_eval.json"
    out.write_text(json.dumps(result, indent=2, default=float))
    print(json.dumps({k: v for k, v in result.items() if k != "C_phone"}, indent=1, default=float))
    for source, v in result["C_phone"].items():
        print(source, {k: v[k] for k in ("n", "frozen", "v2", "v3")})


if __name__ == "__main__":
    main()
