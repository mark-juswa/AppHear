"""Vocabulary-wide WORD evaluation on identical, frozen recognition windows (research only).

``bank`` builds every recognition window once and stores its Recognition V2 features (valid rows
only), so the frozen recognizer and any candidate are scored on byte-identical inputs. ``score``
runs one Keras recognizer over the whole bank and writes its probabilities plus per-view metrics.

Populations (the protected TEST split, E6 and Tier 3 are never read):
  DEV      816 ASL Citizen recognizer-DEV clips, 5 signers disjoint from recognizer TRAIN.
           Selection-exposed (every WORD run selects its checkpoint on DEV val_loss).
  SEMLEX   Sem-Lex clips whose AppHear class was human-accepted (65 classes, 32 signers; spans
           from the Candidate01 d1 port). Never in the frozen recognizer's TRAIN or selection,
           so independent for it. Signers are split by a fixed hash into ENRICH (may be used to
           train candidates) and EVAL (never trained on) so candidates stay comparable.
  PHONE    human-reviewed genuine phone signs (suite v03 Tier-2 + the unblinded shadow session);
           development-exposed, labels carry their provenance.
  TRAIN    recognizer TRAIN (in-sample; for fit / label-consistency diagnosis only).

Views (cadence 266.616 ms = the measured 3.75 fps phone cadence unless named otherwise):
  span_dense            governed span, every frame (the training view)
  span_c375_p{0..3}     governed span at phone cadence, four sampling phases
  ctx_c375_p{0..3}      span +/-250 ms through the runtime materializer (full-length video),
                        four phases: the well-bounded runtime window
  ctx_c200_p{0,1}       the same at the 200 ms median device interval
  rt_natural, rt_continuous
                        the window of the sign's own event from S2-R3 Arm A e10 +
                        CONFIRM_BOUNDARY_70 on the held-out stitched streams (heldout_dev_e2e);
                        signs without their own event have no row (meta: detected=False)
  rob_*                 ctx_c375_p0 with boundary jitter (start late / end early, observations)
                        or simulated refiner rejection (random / fastest-motion-first)
  phone_oracle, phone_runtime
                        phone human-boundary window, and the Arm A + CB70 event window
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics import event_reliability as er  # noqa: E402
from eval.runtime_diagnostics import heldout_dev_e2e as e2e  # noqa: E402
from eval.runtime_diagnostics import phone_replay_compare as prc  # noqa: E402
from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter import (  # noqa: E402
    subset_raw,
)
from pipeline.perception_vnext.recognition_schema import (  # noqa: E402
    MAX_SEQUENCE_LENGTH,
    RawSequence,
    load_raw_sequence,
)
from pipeline.perception_vnext.recognition_schema_v2 import (  # noqa: E402
    FEATURE_WIDTH_V2,
    temporal_view_v2,
)

RU = Path("artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01")
OUT = RU / "word_vocabulary_eval_01"
INDEX = RU / "dataset/index.jsonl"
SEMLEX = RU / "semlex_candidate_raw_01/manifest.json"
SEMLEX2 = RU / "semlex_candidate_raw_02/manifest.json"
FROZEN = RU / "tcn_v2_run_01/best.keras"
FROZEN_SHA = "8107accbc621ae5652766fec80d314fe8dc9f94ba0d0548a6aef80ed91729340"
PHONE_MS = 266.616
DEVICE_MS = 200.0
PHASES = 4
SEMLEX_EVAL_FRACTION = 0.34  # of Sem-Lex signers, by fixed hash; never used to train candidates
RUNTIME = ("ARM_A_E10", "CONFIRM_BOUNDARY_70")
JITTER = {"late1": (1, 0), "late2": (2, 0), "early1": (0, -1), "early2": (0, -2), "both1": (1, -1)}
HAND_DROP = {"hand25": (0.25, "random"), "hand50": (0.5, "random"), "motion50": (0.5, "motion")}


# ----------------------------------------------------------------------------- views
class Bank:
    """Valid feature rows of many views, plus one metadata dict per view row."""

    def __init__(self) -> None:
        self.rows: dict[str, list[np.ndarray]] = defaultdict(list)
        self.meta: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def add(self, view: str, raw: RawSequence, meta: dict[str, Any]) -> None:
        v = temporal_view_v2(raw, condition="dense", phone_completed_fps=5.606840672873506)
        self.rows[view].append(v["features"][v["mask"]].astype(np.float32))
        self.meta[view].append({**meta, "observations": int(v["mask"].sum())})

    def save(self, path: Path) -> dict[str, Any]:
        arrays: dict[str, np.ndarray] = {}
        for view, rows in self.rows.items():
            arrays[f"{view}/features"] = (
                np.concatenate(rows) if rows else np.zeros((0, FEATURE_WIDTH_V2), np.float32)
            )
            arrays[f"{view}/offsets"] = np.cumsum([0] + [len(r) for r in rows]).astype(np.int64)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **arrays)
        meta_path = path.with_suffix(".meta.json")
        meta_path.write_text(json.dumps(self.meta, separators=(",", ":")) + "\n", encoding="utf-8")
        return {
            "bank": path.name,
            "sha256": suite.sha256(path),
            "meta_sha256": suite.sha256(meta_path),
            "views": {k: len(v) for k, v in self.meta.items()},
        }


def _sparse(t: np.ndarray, interval: float, phase: float) -> np.ndarray:
    from pipeline.perception_vnext.recognition_schema import select_nearest_unique

    return select_nearest_unique(t, np.arange(t[0] + phase, t[-1] + 1e-6, interval))


def at_cadence(raw: RawSequence, interval: float, phase: float) -> tuple[RawSequence, np.ndarray]:
    idx = _sparse(np.asarray(raw.timestamp_ms, np.float64), interval, phase)
    return subset_raw(raw, idx), idx


def span_in(idx: np.ndarray, onset: int, release: int) -> tuple[int, int]:
    """Span (source frame indices) mapped onto the selected observations (nearest kept)."""
    on = int(np.searchsorted(idx, onset))
    off = int(np.searchsorted(idx, release, side="right")) - 1
    if off < on:
        off = on = min(on, len(idx) - 1)
    return min(on, len(idx) - 1), off


def ctx_window(raw: RawSequence, first: int, last: int) -> RawSequence:
    t = np.asarray(raw.timestamp_ms, np.float64)
    a, b = prc.oracle_window(t, first, last)
    return suite.slice_raw(raw, a, b)


def drop_hands(raw: RawSequence, fraction: float, mode: str, seed: int) -> RawSequence:
    observed = np.asarray(raw.hand_observed, bool).copy()
    entries = np.argwhere(observed)
    count = int(round(fraction * len(entries)))
    if count == 0:
        return raw
    if mode == "random":
        chosen = np.random.default_rng(seed).choice(len(entries), size=count, replace=False)
    else:
        wrist = np.asarray(raw.hand_xy, np.float64)[:, :, 0, :]
        speed = np.zeros(observed.shape)
        speed[1:] = np.linalg.norm(np.diff(wrist, axis=0), axis=-1)
        speed[~np.isfinite(speed)] = 0.0
        chosen = np.argsort(-speed[entries[:, 0], entries[:, 1]], kind="stable")[:count]
    for frame, side in entries[chosen]:
        observed[frame, side] = False
    values = {f.name: getattr(raw, f.name) for f in dataclass_fields(RawSequence)}
    values["hand_observed"] = observed
    return RawSequence(**values)


def hand_fraction(raw: RawSequence) -> float:
    return (
        float(np.mean(np.asarray(raw.hand_observed, bool).any(axis=1)))
        if len(raw.timestamp_ms)
        else 0.0
    )


def semlex_role(signer: str) -> str:
    h = int(hashlib.sha256(signer.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "EVAL" if h < SEMLEX_EVAL_FRACTION else "ENRICH"


def add_bounded_views(
    bank: Bank,
    prefix: str,
    full: RawSequence,
    onset: int,
    release: int,
    meta: dict[str, Any],
    robust: bool,
) -> None:
    """ctx_* and rob_* views of one clip whose governed span is [onset, release] (frames)."""
    for name, interval, phases in (("c375", PHONE_MS, PHASES), ("c200", DEVICE_MS, 2)):
        for k in range(phases):
            sub, idx = at_cadence(full, interval, k * interval / PHASES)
            a, b = span_in(idx, onset, release)
            window = ctx_window(sub, a, b)
            bank.add(
                f"{prefix}ctx_{name}_p{k}",
                window,
                {**meta, "hand_fraction": hand_fraction(suite.slice_raw(sub, a, b))},
            )
            if robust and name == "c375" and k == 0:
                n = len(sub.timestamp_ms)
                for label, (d0, d1) in JITTER.items():
                    a2 = min(max(0, a + d0), b)
                    b2 = max(min(n - 1, b + d1), a2)
                    bank.add(f"{prefix}rob_{label}", ctx_window(sub, a2, b2), meta)
                for label, (fraction, mode) in HAND_DROP.items():
                    bank.add(f"{prefix}rob_{label}", drop_hands(window, fraction, mode, 7301), meta)


# ----------------------------------------------------------------------------- populations
def build_dev(root: Path) -> Bank:
    bank = Bank()
    index = [json.loads(line) for line in (root / INDEX).open(encoding="utf-8")]
    dev = {r["sample_id"]: r for r in index if r["split"] == "dev"}
    for r in dev.values():
        raw = load_raw_sequence(Path(r["raw_path"]))
        meta = {
            "sample_id": r["sample_id"],
            "gloss": r["canonical_gloss"],
            "signer": r["signer_id"],
        }
        bank.add("span_dense", raw, {**meta, "hand_fraction": hand_fraction(raw)})
        for k in range(PHASES):
            bank.add(f"span_c375_p{k}", at_cadence(raw, PHONE_MS, k * PHONE_MS / PHASES)[0], meta)
    full = suite.read_json(root / e2e.MANIFEST)["clips"]
    for clip in full:
        if not clip["span_valid"]:
            continue
        meta = {"sample_id": clip["sample_id"], "gloss": clip["gloss"], "signer": clip["signer"]}
        raw = load_raw_sequence(root / clip["raw_path"])
        add_bounded_views(
            bank, "", raw, clip["span_onset_index"], clip["span_release_index"], meta, True
        )
    print("[bank] DEV bounded views done", flush=True)
    package = er.load_s2(root, RUNTIME[0])
    streams = e2e.build_streams(root, PHONE_MS)
    from eval.runtime_diagnostics.event_separation import VARIANTS, use_variant

    with use_variant(next(v for v in VARIANTS if v.name == RUNTIME[1])):
        for stream in streams:
            add_runtime_views(bank, package, stream)
    return bank


def add_runtime_views(bank: Bank, package: suite.Package, stream: dict[str, Any]) -> None:
    raw, signs = stream["raw"], stream["signs"]
    t = np.asarray(raw.timestamp_ms, np.float64)
    probs = package.probabilities(suite.features_for_raw(raw, package.contract))
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
    events = suite.replay(rows, allow_post_rearm=True, exact_android_commit_recovery=True)["events"]
    credited: set[int] = set()
    view = f"rt_{stream['mode'].lower()}"
    for s in signs:
        hits = [
            j
            for j, e in enumerate(events)
            if max(s["first"], e["logical_active_start_index"])
            <= min(s["last"], e["logical_active_end_index"])
        ]
        j = next((h for h in hits if h not in credited), None)
        meta = {"sample_id": s["sample_id"], "gloss": s["gloss"], "signer": stream["signer"]}
        if j is None:
            bank.meta[f"{view}_missed"].append(
                {
                    **meta,
                    "acquired": bool(np.any(states[s["first"] : s["last"] + 1] == 1)),
                    "overlapped": bool(hits),
                }
            )
            continue
        credited.add(j)
        a, b = er.window_of(t, events[j])
        others = [o for o in signs if o is not s and max(a, o["first"]) <= min(b, o["last"])]
        cover = max(0, min(b, s["last"]) - max(a, s["first"]) + 1) / (s["last"] - s["first"] + 1)
        bank.add(
            view,
            suite.slice_raw(raw, a, b),
            {**meta, "contaminated": bool(others), "coverage": round(float(cover), 3)},
        )


def build_semlex(root: Path, manifest: Path = SEMLEX) -> Bank:
    from pipeline.detect.candidate01_span import candidate01_span
    from pipeline.detect.config import load_config

    cfg = load_config(ROOT / "pipeline/config/detect.yaml")
    bank = Bank()
    for clip in suite.read_json(root / manifest)["clips"]:
        raw = load_raw_sequence(root / clip["raw_path"])
        span = candidate01_span(raw, cfg, 0.4)
        if not span.valid:
            continue
        meta = {
            "sample_id": f"semlex:{clip['semlex_sample_id']}",
            "gloss": clip["gloss"],
            "signer": clip["signer"],
            "role": semlex_role(clip["signer"]),
            "human_decision": clip["human_decision"],
        }
        cut = subset_raw(raw, np.arange(span.onset, span.release + 1, dtype=np.int32))
        bank.add("span_dense", cut, {**meta, "hand_fraction": hand_fraction(cut)})
        for k in range(2):
            bank.add(f"span_c375_p{k}", at_cadence(cut, PHONE_MS, k * PHONE_MS / PHASES)[0], meta)
        add_bounded_views(bank, "", raw, span.onset, span.release, meta, False)
    return bank


def build_phone(root: Path) -> Bank:
    bank = Bank()
    package = er.load_s2(root, RUNTIME[0])
    sessions = {
        k: v for k, v in er.phone_sessions(root).items() if v["kind"] != "SHADOW_PROTOCOL_ONLY"
    }
    for name, session in sessions.items():
        raw, t = session["capture"].raw, session["timestamps_ms"]
        signs = sorted(session["positives"], key=lambda x: x["first"])
        provenance = {"TIER2": "TIER2_REVIEW_DEVELOPMENT_EXPOSED"}.get(session["kind"], "UNBLINDED")
        probs = package.probabilities(session["features"])
        events = prc.replay(probs, t, RUNTIME[1])["events"]
        used: set[int] = set()
        for s in signs:
            a, b = s["first"], s["last"]
            meta = {
                "sample_id": f"phone:{name}:{s['name']}",
                "gloss": prc.gloss_of(s["name"]),
                "signer": f"phone:{name}",
                "provenance": provenance,
                "hand_fraction": hand_fraction(suite.slice_raw(raw, a, b)),
            }
            bank.add("phone_oracle", suite.slice_raw(raw, *prc.oracle_window(t, a, b)), meta)
            hits = [
                j
                for j, e in enumerate(events)
                if max(a, e["logical_active_start_index"]) <= min(b, e["logical_active_end_index"])
            ]
            j = next((h for h in hits if h not in used), None)
            if j is None:
                bank.meta["phone_runtime_missed"].append(meta)
                continue
            used.add(j)
            bank.add("phone_runtime", suite.slice_raw(raw, *er.window_of(t, events[j])), meta)
    return bank


def build_train(root: Path) -> Bank:
    bank = Bank()
    for line in (root / INDEX).open(encoding="utf-8"):
        r = json.loads(line)
        if r["split"] != "train":
            continue
        raw = load_raw_sequence(Path(r["raw_path"]))
        meta = {
            "sample_id": r["sample_id"],
            "gloss": r["canonical_gloss"],
            "signer": r["signer_id"],
            "source": r["source_id"],
            "hand_fraction": hand_fraction(raw),
        }
        bank.add("span_dense", raw, meta)
        bank.add("span_c375_p0", at_cadence(raw, PHONE_MS, 0.0)[0], meta)
    return bank


BUILDERS = {
    "DEV": build_dev,
    "SEMLEX": build_semlex,
    # 40 further classes accepted in human review package 02 (2026-10-18)
    "SEMLEX2": lambda root: build_semlex(root, SEMLEX2),
    "PHONE": build_phone,
    "TRAIN": build_train,
}


# ----------------------------------------------------------------------------- scoring
def load_bank(path: Path) -> tuple[dict[str, list[np.ndarray]], dict[str, list[dict[str, Any]]]]:
    data = np.load(path)
    meta = json.loads(path.with_suffix(".meta.json").read_text(encoding="utf-8"))
    views: dict[str, list[np.ndarray]] = {}
    for key in data.files:
        if key.endswith("/features"):
            view = key[: -len("/features")]
            f, off = data[key], data[f"{view}/offsets"]
            views[view] = [f[off[i] : off[i + 1]] for i in range(len(off) - 1)]
    return views, meta


def predict(model: Any, rows: list[np.ndarray]) -> np.ndarray:
    out = []
    for start in range(0, len(rows), 256):
        chunk = rows[start : start + 256]
        x = np.zeros((len(chunk), MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2), np.float32)
        m = np.zeros((len(chunk), MAX_SEQUENCE_LENGTH), bool)
        for i, r in enumerate(chunk):
            x[i, : len(r)] = r
            m[i, : len(r)] = True
        out.append(np.asarray(model([x, m], training=False), np.float32))
    return np.concatenate(out) if out else np.zeros((0, 236), np.float32)


def glosses(root: Path) -> list[str]:
    vocab = suite.read_json(root / er.VOCAB)
    return [g for g, _ in sorted(vocab.items(), key=lambda item: item[1])]


def metrics(prob: np.ndarray, meta: list[dict[str, Any]], names: list[str]) -> dict[str, Any]:
    index = {g: i for i, g in enumerate(names)}
    y = np.asarray([index[m["gloss"]] for m in meta])
    order = np.argsort(-prob, axis=1, kind="stable")
    rank = np.argmax(order == y[:, None], axis=1) + 1
    top1 = rank == 1
    per_class: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for g, c, r in zip((m["gloss"] for m in meta), top1, rank, strict=True):
        per_class[g][0] += 1
        per_class[g][1] += int(c)
        per_class[g][2] += int(r <= 5)
    signer: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for m, c in zip(meta, top1, strict=True):
        signer[m["signer"]][0] += 1
        signer[m["signer"]][1] += int(c)
    recall = [v[1] / v[0] for v in per_class.values()]
    return {
        "n": int(len(y)),
        "classes": len(per_class),
        "top1": float(top1.mean()),
        "top5": float((rank <= 5).mean()),
        "macro_recall": float(np.mean(recall)),
        "zero_recall_classes": int(sum(r == 0 for r in recall)),
        "median_rank": float(np.median(rank)),
        "per_signer_top1": {k: round(v[1] / v[0], 4) for k, v in sorted(signer.items())},
        "per_class": {k: v for k, v in sorted(per_class.items())},
    }


def score(root: Path, model_path: Path, name: str, populations: list[str]) -> None:
    import tensorflow as tf

    sha = suite.sha256(model_path)
    if name == "frozen" and sha != FROZEN_SHA:
        raise ValueError("FROZEN_HASH_MISMATCH")
    model = tf.keras.models.load_model(model_path, compile=False, safe_mode=True)
    names = glosses(root)
    out_dir = root / OUT / "scores" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"model": str(model_path), "sha256": sha, "populations": {}}
    for population in populations:
        views, meta = load_bank(root / OUT / f"bank_{population}.npz")
        probs = {view: predict(model, rows) for view, rows in views.items()}
        np.savez_compressed(out_dir / f"{population}.npz", **probs)
        summary["populations"][population] = {
            view: {k: v for k, v in metrics(p, meta[view], names).items() if k != "per_class"}
            for view, p in probs.items()
        }
        for view, m in summary["populations"][population].items():
            print(
                f"[score] {name} {population} {view}: n={m['n']} "
                f"top1={m['top1']:.4f} top5={m['top5']:.4f}",
                flush=True,
            )
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--evidence-root", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("bank")
    b.add_argument("--population", choices=sorted(BUILDERS), action="append", required=True)
    s = sub.add_parser("score")
    s.add_argument("--model", type=Path, help="Keras recognizer (default: the frozen Gate-2 model)")
    s.add_argument("--name", required=True)
    s.add_argument("--population", choices=sorted(BUILDERS), action="append", required=True)
    args = parser.parse_args()
    root = args.evidence_root
    if args.command == "bank":
        for population in args.population:
            bank = BUILDERS[population](root)
            info = bank.save(root / OUT / f"bank_{population}.npz")
            (root / OUT / f"bank_{population}.json").write_text(
                json.dumps(info, indent=1) + "\n", encoding="utf-8"
            )
            print(population, json.dumps(info["views"]), flush=True)
    else:
        score(root, args.model or root / FROZEN, args.name, args.population)


if __name__ == "__main__":
    main()
