"""Held-out end-to-end benchmark: S2 + decoder + materializer + WORD on signer-disjoint DEV.

Population: the 816 ASL Citizen recognizer-DEV clips (5 signers absent from every S2 FIT/CAL source
and from recognizer TRAIN), full-length raw from heldout_dev_fullvideo_extraction.py. Per signer,
clips are grouped (seeded) into streams of 4 and joined at the raw level, then sampled at a phone
cadence before features are computed:
  NATURAL     each full clip (its own rest lead-in/out) -> sign, rest, sign ...
  CONTINUOUS  each clip cut to [onset-1, release+1] observations of the governed automatic span
              (first clip keeps its lead-in, last its tail) -> direct sign-to-sign signing
Ground-truth sign intervals are the governed automatic spans (NOT human boundaries) and the gloss.
Scoring per sign: detected (a distinct event overlaps its interval), correct word (that event's
WORD top-1 equals the gloss). Per stream: extra events (overlap no sign), word precision.
Reference: the ORACLE window (span +/-250 ms through the runtime materializer) gives the
boundary-given WORD ceiling at the same cadence. Stitching is semi-synthetic: joins are real
observations but cross-clip discontinuities exist; this is a comparative benchmark, not product
accuracy. The recognizer DEV set is selection-exposed for the recognizer (both recognizers alike).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter import (  # noqa: E402
    subset_raw,
)
from pipeline.perception_vnext.recognition_schema import (  # noqa: E402
    RawSequence,
    load_raw_sequence,
    select_nearest_unique,
)
from pipeline.perception_vnext.recognition_schema_v2 import temporal_view_v2  # noqa: E402
from pipeline.perception_vnext.recognition_window_materializer import (  # noqa: E402
    LogicalSignEvent,
    materialize_recognition_window,
)

MANIFEST = Path(
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "heldout_dev_fullvideo_raw_01/manifest.json"
)
RU = Path("artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01")
DEFAULT_RECOGNIZER = RU / "tcn_v2_run_01/best.keras"
VOCAB = Path("artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1/vocab.json")
STREAM_CLIPS = 4
SEED = 6203


class Word:
    def __init__(self, path: Path, vocab: Path) -> None:
        import tensorflow as tf

        self.model = tf.keras.models.load_model(path, compile=False, safe_mode=True)
        self.sha256 = suite.sha256(path)
        mapping = suite.read_json(vocab)
        self.glosses = [g for g, _ in sorted(mapping.items(), key=lambda item: item[1])]

    def top1(self, raws: list[RawSequence]) -> list[tuple[str, float]]:
        if not raws:
            return []
        views = [temporal_view_v2(r, condition="dense", phone_completed_fps=5.6068) for r in raws]
        x = np.stack([v["features"] for v in views]).astype(np.float32)
        m = np.stack([v["mask"] for v in views])
        out = np.concatenate(
            [
                np.asarray(self.model([x[i : i + 256], m[i : i + 256]], training=False))
                for i in range(0, len(x), 256)
            ]
        )
        return [(self.glosses[int(np.argmax(p))], float(np.max(p))) for p in out]


def sparse(raw: RawSequence, interval: float, phase: float) -> np.ndarray:
    t = np.asarray(raw.timestamp_ms, np.float64)
    return select_nearest_unique(t, np.arange(t[0] + phase, t[-1] + 1e-6, interval))


def build_streams(root: Path, interval: float) -> list[dict[str, Any]]:
    clips = suite.read_json(root / MANIFEST)["clips"]
    by_signer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for clip in clips:
        if clip["span_valid"]:
            by_signer[clip["signer"]].append(clip)
    rng = np.random.default_rng(SEED)
    streams = []
    for signer in sorted(by_signer):
        order = rng.permutation(len(by_signer[signer]))
        group = [by_signer[signer][i] for i in order]
        for start in range(0, len(group) - STREAM_CLIPS + 1, STREAM_CLIPS):
            members = group[start : start + STREAM_CLIPS]
            for mode in ("NATURAL", "CONTINUOUS"):
                parts, signs, offset = [], [], 0
                for k, clip in enumerate(members):
                    raw = load_raw_sequence(root / clip["raw_path"])
                    idx = sparse(raw, interval, float(rng.uniform(0, interval)))
                    on = int(np.searchsorted(idx, clip["span_onset_index"]))
                    off = int(np.searchsorted(idx, clip["span_release_index"], side="right")) - 1
                    if off < on:  # span shorter than one sparse step: keep nearest observation
                        off = on = min(on, len(idx) - 1)
                    lo, hi = 0, len(idx) - 1
                    if mode == "CONTINUOUS":
                        lo = 0 if k == 0 else max(0, on - 1)
                        hi = len(idx) - 1 if k == len(members) - 1 else min(len(idx) - 1, off + 1)
                    keep = idx[lo : hi + 1]
                    parts.append(subset_raw(raw, keep))
                    signs.append(
                        {
                            "gloss": clip["gloss"],
                            "first": offset + on - lo,
                            "last": offset + off - lo,
                            "sample_id": clip["sample_id"],
                        }
                    )
                    offset += len(keep)
                streams.append(
                    {
                        "signer": signer,
                        "mode": mode,
                        "raw": suite.concat_raw(parts, interval),
                        "signs": signs,
                    }
                )
    return streams


def evaluate(package: suite.Package, word: Word, streams: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    per_signer: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    records: list[list[Any]] = []  # [mode, signer, top1 probability, correct word]
    for stream in streams:
        raw, signs = stream["raw"], stream["signs"]
        t = np.asarray(raw.timestamp_ms, np.float64)
        probs = package.probabilities(suite.features_for_raw(raw, package.contract))
        states = np.argmax(probs, axis=1)
        events = suite.replay(
            [
                {
                    "source_index": i,
                    "source_timestamp_ms": float(t[i]),
                    "argmax_state": int(states[i]),
                    "pre_probability": float(probs[i, 0]),
                    "active_probability": float(probs[i, 1]),
                    "post_probability": float(probs[i, 2]),
                }
                for i in range(len(t))
            ],
            allow_post_rearm=True,
            exact_android_commit_recovery=True,
        )["events"]
        windows = []
        for e in events:
            w = materialize_recognition_window(
                t,
                LogicalSignEvent(
                    int(e["logical_active_start_index"]),
                    int(e["logical_active_end_index"]),
                    float(e["logical_active_start_ms"]),
                    float(e["logical_active_end_ms"]),
                    int(e["first_post_index"]),
                    float(e["first_post_ms"]),
                    int(e["emitted_at_index"]),
                    float(e["emitted_at_ms"]),
                ),
                suite.MATERIALIZER_CONFIG,
            )
            windows.append((w.selected_start_index, w.selected_end_index))
        predictions = word.top1([suite.slice_raw(raw, a, b) for a, b in windows])
        oracle_windows = []
        for s in signs:
            before = np.flatnonzero(t <= t[s["first"]] - 250.0)
            after = np.flatnonzero(t >= t[s["last"]] + 250.0)
            oracle_windows.append(
                (int(before[-1]) if len(before) else 0, int(after[0]) if len(after) else len(t) - 1)
            )
        oracle = word.top1([suite.slice_raw(raw, a, b) for a, b in oracle_windows])
        credited: set[int] = set()
        used: set[int] = set()
        signs_per_event: dict[int, int] = defaultdict(int)
        correct_events: set[int] = set()
        events_per_sign: list[int] = []
        duplicate_words = 0
        key = stream["mode"]
        for s, (ogloss, _) in zip(signs, oracle, strict=True):
            hits = [
                j
                for j, e in enumerate(events)
                if max(s["first"], e["logical_active_start_index"])
                <= min(s["last"], e["logical_active_end_index"])
            ]
            used.update(hits)
            for j in hits:
                signs_per_event[j] += 1
            events_per_sign.append(len(hits))
            correct_hits = [j for j in hits if predictions[j][0] == s["gloss"]]
            duplicate_words += max(0, len(correct_hits) - 1)
            acquired = bool(np.any(states[s["first"] : s["last"] + 1] == 1))
            distinct = next((j for j in hits if j not in credited), None)
            if acquired and distinct is None:
                totals[key]["acquired_no_distinct_event"] += 1
                totals[key]["acquired_inside_shared_event"] += float(bool(hits))
            totals[key]["signs"] += 1
            totals[key]["acquired"] += float(np.any(states[s["first"] : s["last"] + 1] == 1))
            totals[key]["oracle_correct"] += float(ogloss == s["gloss"])
            per_signer[f"{key}:{stream['signer']}"]["signs"] += 1
            if distinct is not None:
                credited.add(distinct)
                totals[key]["detected"] += 1
                correct = predictions[distinct][0] == s["gloss"]
                if correct:
                    correct_events.add(distinct)
                totals[key]["correct_words"] += float(correct)
                per_signer[f"{key}:{stream['signer']}"]["correct_words"] += float(correct)
        totals[key]["events"] += len(events)
        records.extend(
            [key, stream["signer"], predictions[j][1], j in correct_events]
            for j in range(len(events))
        )
        totals[key]["merged_events"] += sum(1 for c in signs_per_event.values() if c > 1)
        totals[key]["split_signs"] += sum(1 for c in events_per_sign if c > 1)
        totals[key]["duplicate_words"] += duplicate_words
        totals[key]["extra_events"] += len([j for j in range(len(events)) if j not in used])
        totals[key]["observations"] += len(t)
        totals[key]["minutes"] += float(t[-1] - t[0]) / 60000.0
    summary = {}
    for key, v in totals.items():
        summary[key] = {
            **{k: float(x) for k, x in v.items()},
            "detection_rate": v["detected"] / v["signs"],
            "correct_word_rate": v["correct_words"] / v["signs"],
            "oracle_word_rate": v["oracle_correct"] / v["signs"],
            "word_precision": v["correct_words"] / max(1.0, v["events"]),
            "extra_events_per_minute": v["extra_events"] / max(1e-9, v["minutes"]),
        }
    summary["per_signer_correct_word_rate"] = {
        k: v["correct_words"] / v["signs"] for k, v in sorted(per_signer.items())
    }
    summary["event_records"] = records
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--s2-keras", type=Path, required=True)
    parser.add_argument("--s2-normalization", type=Path, required=True)
    parser.add_argument("--recognizer", type=Path)
    parser.add_argument("--interval-ms", type=float, default=266.616)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--decoder-variant", default="BASELINE", help="event_separation variant")
    parser.add_argument(
        "--diagnostic-rearm-ms",
        type=float,
        help="DIAGNOSTIC ONLY: counterfactual re-arm stability (production CONFIG_01 is 399.924)",
    )
    args = parser.parse_args()
    if args.diagnostic_rearm_ms is not None:
        import dataclasses

        from eval.runtime_diagnostics import phone_repeated_recognition_integration as lifecycle

        lifecycle.CONFIG_01 = dataclasses.replace(
            lifecycle.CONFIG_01, rearm_pre_stable_ms=args.diagnostic_rearm_ms
        )
    root = args.evidence_root
    package = suite.load_package("EVAL", "v1", args.s2_keras, args.s2_normalization)
    word = Word(args.recognizer or root / DEFAULT_RECOGNIZER, root / VOCAB)
    streams = build_streams(root, args.interval_ms)
    from eval.runtime_diagnostics.event_separation import VARIANTS, use_variant

    variant = next(v for v in VARIANTS if v.name == args.decoder_variant)
    with use_variant(variant):
        summary = evaluate(package, word, streams)
    result = {
        "decoder_variant": variant.name,
        "schema": "apphear.heldout_dev_e2e.v1",
        "s2_package": package.identity,
        "recognizer_sha256": word.sha256,
        "interval_ms": args.interval_ms,
        "diagnostic_rearm_ms": args.diagnostic_rearm_ms,
        "streams": len(streams),
        "summary": summary,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=1), flush=True)


if __name__ == "__main__":
    main()
