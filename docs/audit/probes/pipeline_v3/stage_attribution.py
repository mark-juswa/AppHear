"""Full-pipeline stage attribution and oracle-boundary WORD evaluation (read-only diagnostic).

Frozen components only: Candidate01 raw-v1 evidence as recorded, S2-R2 (suite v03 reference
package), CONFIG_01 decoder with PRE_OR_POST re-arm and exact Android commit recovery, the
v1 materializer (+/-250 ms), Recognition V2 DENSE view (as PhoneCausalController.kt) and the
frozen 236-class recognizer checkpoint (tcn_v2_run_01/best.keras, the source of the Android
ordinary_v2_tcn_fp32.tflite). Nothing is trained, tuned or written outside --out.

Part A  PHONE: every human-reviewed genuine phone sign (suite Tier-2 sessions plus the S2-FIT
        exact-parity session, which is valid for the WORD question only). Per sign: perception
        evidence, S2 acquisition, event/merge, runtime window coverage, WORD result on the runtime
        window, and WORD result on oracle windows built from the human boundaries:
          ORACLE_TIGHT  first..last human ACTIVE observation
          ORACLE_CTX    the same interval passed through the runtime materializer (+/-250 ms)
        Oracle windows are an offline upper reference, not deployable performance.
Part B  DEV: the 816 signer-disjoint recognizer DEV clips (held out from the recognizer AND from
        every S2 FIT/CAL signer). Their raw is already cut to the governed automatic onset/release
        span, so the baseline is itself a boundary-given number. Boundary error sensitivity is
        measured by removing the first/last fraction of the span (late onset / early commit),
        in the dense view and the phone-cadence sparse view.
Part C  SEG-DEV windowing: the 23 human-annotated full-video clips (69 phone-cadence views). They
        are signer-disjoint for S2 but are recognizer TRAIN clips, so absolute WORD accuracy is
        inflated; only the relative effect of window construction is interpreted.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter import (  # noqa: E402
    subset_raw,
)
from eval.runtime_diagnostics.phone_s2_exact_parity_and_r2_decision import (  # noqa: E402
    load_capture,
)
from pipeline.perception_vnext.recognition_schema import (  # noqa: E402
    RawSequence,
    load_raw_sequence,
)
from pipeline.perception_vnext.recognition_schema_v2 import temporal_view_v2  # noqa: E402
from pipeline.perception_vnext.recognition_window_materializer import (  # noqa: E402
    LogicalSignEvent,
    materialize_recognition_window,
)
from pipeline.perception_vnext.segmentation.streaming_decoder import (  # noqa: E402
    CausalStreamingSignEventDecoder,
)

PHONE_COMPLETED_FPS = 5.606840672873506
RU = "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
RECOGNIZER = f"{RU}/tcn_v2_run_01/best.keras"
RECOGNIZER_SHA = "8107accbc621ae5652766fec80d314fe8dc9f94ba0d0548a6aef80ed91729340"
VOCAB = "artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1/vocab.json"
DATASET_INDEX = (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/dataset/index.jsonl"
)
EXTRA_PHONE = {
    "SEP21_S2FIT_EXACT": {
        "capture": "phone_pull_s2_exact_parity/session_20260921T153138Z",
        "labels": "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
        "s2_r2_continuous_domain_correction_01/exact_phone_temporal_review_01/"
        "phone_positive_observation_labels.csv",
        "s2_valid": False,
    }
}
ADEQUATE_MIN_OBS = 4
ADEQUATE_MIN_HAND_FRACTION = 0.5
CONTAINMENT = 0.9


class Recognizer:
    def __init__(self, root: Path, path: Path | None = None) -> None:
        import tensorflow as tf

        if path is None:
            path = root / RECOGNIZER
            if suite.sha256(path) != RECOGNIZER_SHA:
                raise ValueError("RECOGNIZER_HASH_MISMATCH")
        self.sha256 = suite.sha256(path)
        self.model = tf.keras.models.load_model(path, compile=False, safe_mode=True)
        vocab = suite.read_json(root / VOCAB)
        self.glosses = [g for g, _ in sorted(vocab.items(), key=lambda item: item[1])]
        self.index = {g: i for i, g in enumerate(self.glosses)}

    def probabilities(self, raws: list[RawSequence], condition: str = "dense") -> np.ndarray:
        if not raws:
            return np.zeros((0, len(self.glosses)), np.float32)
        views = [
            temporal_view_v2(raw, condition=condition, phone_completed_fps=PHONE_COMPLETED_FPS)
            for raw in raws
        ]
        features = np.stack([v["features"] for v in views]).astype(np.float32)
        mask = np.stack([v["mask"] for v in views])
        out = []
        for start in range(0, len(views), 128):
            out.append(
                np.asarray(
                    self.model(
                        [features[start : start + 128], mask[start : start + 128]], training=False
                    )
                )
            )
        return np.concatenate(out).astype(np.float64)

    def score(self, probability: np.ndarray, expected: str) -> dict[str, Any]:
        order = np.argsort(-probability, kind="stable")
        target = self.index[expected]
        return {
            "top1": self.glosses[int(order[0])],
            "top1_probability": float(probability[order[0]]),
            "correct": bool(order[0] == target),
            "top5": bool(target in order[:5]),
            "expected_rank": int(np.flatnonzero(order == target)[0]) + 1,
            "expected_probability": float(probability[target]),
        }


def window_for(
    timestamps: np.ndarray, first: int, last: int, post: int, commit: int
) -> tuple[int, int]:
    window = materialize_recognition_window(
        timestamps,
        LogicalSignEvent(
            first,
            last,
            float(timestamps[first]),
            float(timestamps[last]),
            post,
            float(timestamps[post]),
            commit,
            float(timestamps[commit]),
        ),
        suite.MATERIALIZER_CONFIG,
    )
    return window.selected_start_index, window.selected_end_index


def oracle_ctx_window(timestamps: np.ndarray, first: int, last: int) -> tuple[int, int]:
    n = len(timestamps)
    if last + 1 < n:
        return window_for(timestamps, first, last, last + 1, n - 1)
    # sign runs to the end of the clip: same pre-context rule, right-censored at the last row
    before = np.flatnonzero(
        timestamps <= timestamps[first] - suite.MATERIALIZER_CONFIG.requested_pre_context_ms
    )
    return (int(before[-1]) if len(before) else 0, n - 1)


def coverage(window: tuple[int, int], timestamps: np.ndarray, first: int, last: int) -> float:
    lo = max(timestamps[window[0]], timestamps[first])
    hi = min(timestamps[window[1]], timestamps[last])
    span = timestamps[last] - timestamps[first]
    if span <= 0:
        return float(window[0] <= first <= window[1])
    return float(max(0.0, hi - lo) / span)


# ----------------------------------------------------------------------------- part A
def extra_session(root: Path, spec: dict[str, Any], tolerance_ns: int) -> dict[str, Any]:
    capture = load_capture(root / spec["capture"], require_full_session=False)
    timestamps = np.asarray(capture.raw.timestamp_ms, np.float64)
    stamp_ns = np.round(timestamps * 1e6).astype(np.int64)
    attempts: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    with (root / spec["labels"]).open(encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            target = int(row["source_timestamp_ns"])
            index = int(np.argmin(np.abs(stamp_ns - target)))
            if abs(int(stamp_ns[index]) - target) > tolerance_ns:
                raise ValueError("UNMATCHED_LABEL_TIMESTAMP")
            attempts[row["attempt_id"]].append((index, int(row["state_id"]), row["expected_gloss"]))
    positives = []
    for attempt_id, rows in sorted(attempts.items()):
        active = sorted(i for i, s, _ in rows if s == suite.ACTIVE)
        if active:
            positives.append(
                {
                    "name": f"{attempt_id}:{rows[0][2]}",
                    "first": active[0],
                    "last": active[-1],
                    "active_rows": active,
                }
            )
    return {
        "capture": capture,
        "features": suite.features_for_raw(capture.raw, "v1"),
        "timestamps_ms": timestamps,
        "positives": positives,
        "uncertain": [],
        "negatives": [],
        "continuous": False,
    }


def gloss_of(name: str) -> str:
    head = name.split("#")[0]
    return head.split(":")[-1]


def phone_part(root: Path, rec: Recognizer, package: suite.Package) -> dict[str, Any]:
    config = suite.read_json(suite.SUITES["03"][0])
    tier = config["tier2_sessions"]
    tolerance = int(tier["timestamp_match_tolerance_ns"])
    sessions: dict[str, tuple[dict[str, Any], bool, str]] = {}
    for name, spec in tier.items():
        if isinstance(spec, dict) and "capture" in spec:
            sessions[name] = (
                suite.load_tier2_session(root, name, spec, "v1", tolerance),
                True,
                spec["signer_role"],
            )
    for name, spec in EXTRA_PHONE.items():
        sessions[name] = (
            extra_session(root, spec, tolerance),
            spec["s2_valid"],
            "DESIGN_SIGNER_S2_FIT (WORD-only; S2 trained on these attempts)",
        )
    signs: list[dict[str, Any]] = []
    false_events: list[dict[str, Any]] = []
    fresh_controls: list[dict[str, Any]] = []
    for name, (session, s2_valid, role) in sessions.items():
        raw = session["capture"].raw
        t = session["timestamps_ms"]
        probs = package.probabilities(session["features"])
        states = np.argmax(probs, axis=1)
        replayed = suite.replay(
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
        )
        events = replayed["events"]
        windows = [
            window_for(
                t,
                int(e["logical_active_start_index"]),
                int(e["logical_active_end_index"]),
                int(e["first_post_index"]),
                int(e["emitted_at_index"]),
            )
            for e in events
        ]
        positives = sorted(session["positives"], key=lambda s: s["first"])
        per_sign, used, merged = suite.match_signs(positives, events, states)
        credited: set[int] = set()
        genuine_rows = [(s["first"], s["last"]) for s in positives]
        batch: list[RawSequence] = []
        keys: list[tuple[int, str]] = []
        for k, (sign, match) in enumerate(zip(positives, per_sign, strict=False)):
            first, last = sign["first"], sign["last"]
            hits = [
                j
                for j, e in enumerate(events)
                if max(first, e["logical_active_start_index"])
                <= min(last, e["logical_active_end_index"])
            ]
            distinct = next((j for j in hits if j not in credited), None)
            if distinct is not None:
                credited.add(distinct)
            rows = np.arange(first, last + 1)
            hand = np.any(raw.hand_observed[rows], axis=1)
            row: dict[str, Any] = {
                "session": name,
                "signer_role": role,
                "s2_valid": s2_valid,
                "continuous": session["continuous"],
                "sign": sign["name"],
                "gloss": gloss_of(sign["name"]),
                "first": first,
                "last": last,
                "observations": int(len(rows)),
                "duration_ms": float(t[last] - t[first]),
                "median_interval_ms": float(np.median(np.diff(t[max(0, first - 1) : last + 2]))),
                "hand_fraction": float(np.mean(hand)),
                "both_hands_fraction": float(np.mean(np.all(raw.hand_observed[rows], axis=1))),
                "proposal_fraction": float(
                    np.mean(np.any(raw.hand_proposal_present[rows], axis=1))
                ),
                "body_fraction": float(np.mean(raw.body_available[rows])),
                "s2_active_rows": int(np.sum(states[rows] == suite.ACTIVE)),
                "s2_acquired": bool(match["acquired"]),
                "event": bool(hits),
                "distinct_event": distinct is not None,
                "merged": bool(hits) and distinct is None,
            }
            # fresh-start S2 control: 5 lead-in observations only (diagnostic, not deployable)
            lead = max(0, first - 5)
            local = suite.slice_raw(raw, lead, min(len(t) - 1, last + 3))
            local_states = np.argmax(
                package.probabilities(suite.features_for_raw(local, "v1")), axis=1
            )
            row["s2_acquired_fresh_start"] = bool(
                np.any(local_states[first - lead : last - lead + 1] == suite.ACTIVE)
            )
            if distinct is not None:
                w = windows[distinct]
                row["runtime_window"] = list(w)
                row["runtime_coverage"] = coverage(w, t, first, last)
                others = [g for g in genuine_rows if g != (first, last)]
                row["runtime_window_contains_other_sign"] = any(
                    max(w[0], a) <= min(w[1], b)
                    and (b - a + 1) > 0
                    and (min(w[1], b) - max(w[0], a) + 1) >= 0.5 * (b - a + 1)
                    for a, b in others
                )
                batch.append(slice_raw_safe(raw, *w))
                keys.append((k, "runtime"))
            tight = (first, last)
            ctx = oracle_ctx_window(t, first, last)
            row["oracle_ctx_window"] = list(ctx)
            batch.append(slice_raw_safe(raw, *tight))
            keys.append((k, "oracle_tight"))
            batch.append(slice_raw_safe(raw, *ctx))
            keys.append((k, "oracle_ctx"))
            per_sign_rows = row
            signs.append(per_sign_rows)
            per_sign_rows["_index"] = len(signs) - 1
        offset = len(signs) - len(positives)
        probs_word = rec.probabilities(batch)
        for (k, kind), p in zip(keys, probs_word, strict=False):
            signs[offset + k][kind] = rec.score(p, signs[offset + k]["gloss"])
        # events not credited to any genuine sign: what does the recognizer say?
        if s2_valid:
            fe_batch, fe_meta = [], []
            for j, e in enumerate(events):
                if j in used:
                    continue
                inside = any(
                    n["first"] <= e["logical_active_start_index"]
                    and e["logical_active_end_index"] <= n["last"]
                    for n in session["negatives"]
                )
                fe_batch.append(slice_raw_safe(raw, *windows[j]))
                fe_meta.append({"session": name, "event": j, "inside_confirmed_nonsign": inside})
            for meta, p in zip(fe_meta, rec.probabilities(fe_batch), strict=False):
                order = np.argsort(-p)
                e = events[meta["event"]]
                before = [s for s in positives if s["last"] < e["logical_active_start_index"]]
                near = before[-1] if before else None
                false_events.append(
                    {
                        **meta,
                        "top1": rec.glosses[int(order[0])],
                        "top1_probability": float(p[order[0]]),
                        "logical": [
                            int(e["logical_active_start_index"]),
                            int(e["logical_active_end_index"]),
                        ],
                        "previous_sign": near["name"] if near else None,
                        "obs_after_previous_sign_end": (
                            (int(e["logical_active_start_index"]) - near["last"]) if near else None
                        ),
                        "previous_sign_matched": bool(near)
                        and any(
                            r["sign"] == near["name"] and r.get("distinct_event")
                            for r in signs[offset:]
                        ),
                    }
                )
            # negative control for the fresh-start diagnostic: same procedure on confirmed
            # non-sign rows, chunked to the median genuine sign length of this session
            length = (
                int(np.median([s["last"] - s["first"] + 1 for s in positives])) if positives else 8
            )
            for n in session["negatives"]:
                for a in range(n["first"], n["last"] - length + 2, length):
                    lead = max(0, a - 5)
                    local = suite.slice_raw(raw, lead, a + length - 1)
                    ls = np.argmax(
                        package.probabilities(suite.features_for_raw(local, "v1")), axis=1
                    )
                    full_fire = bool(np.any(states[a : a + length] == suite.ACTIVE))
                    fresh_controls.append(
                        {
                            "session": name,
                            "rows": [a, a + length - 1],
                            "fresh_start_active": bool(np.any(ls[a - lead :] == suite.ACTIVE)),
                            "full_history_active": full_fire,
                        }
                    )
        uncertain = session.get("uncertain", [])
        for item in uncertain:
            signs.append(
                {
                    "session": name,
                    "sign": item["name"],
                    "gloss": gloss_of(item["name"]),
                    "uncertain": True,
                    "first": item["first"],
                    "last": item["last"],
                }
            )
    for row in signs:
        row.pop("_index", None)
        if not row.get("uncertain"):
            row["first_failure"] = first_failure(row)
    return {
        "signs": signs,
        "unmatched_events": false_events,
        "fresh_start_negative_controls": fresh_controls,
    }


def slice_raw_safe(raw: RawSequence, first: int, last: int) -> RawSequence:
    return suite.slice_raw(raw, int(first), int(last))


def first_failure(row: dict[str, Any]) -> str:
    adequate = (
        row["observations"] >= ADEQUATE_MIN_OBS
        and row["hand_fraction"] >= ADEQUATE_MIN_HAND_FRACTION
    )
    if not row["s2_acquired"]:
        return "NOT_SEGMENTED" + ("" if adequate else "|WEAK_OBSERVATION")
    if not row["event"]:
        return "ACQUIRED_NO_EVENT" + ("" if adequate else "|WEAK_OBSERVATION")
    if row["merged"]:
        return "MERGED"
    if row.get("runtime_coverage", 0.0) < CONTAINMENT or row.get(
        "runtime_window_contains_other_sign"
    ):
        return "BAD_WINDOW" + ("|RIGHT_CLASS" if row["runtime"]["correct"] else "")
    if not row["runtime"]["correct"]:
        return "MISCLASSIFIED" + ("" if adequate else "|WEAK_OBSERVATION")
    return "CORRECT"


# ----------------------------------------------------------------------------- part B
def trim(raw: RawSequence, head: float, tail: float) -> RawSequence:
    n = len(raw.timestamp_ms)
    first = int(np.floor(head * n))
    last = n - 1 - int(np.floor(tail * n))
    last = max(last, first)
    return subset_raw(raw, np.arange(first, last + 1, dtype=np.int32))


def dev_part(root: Path, rec: Recognizer) -> dict[str, Any]:
    rows = [json.loads(line) for line in (root / DATASET_INDEX).open(encoding="utf-8")]
    dev = [r for r in rows if r["split"] == "dev"]
    raws = [load_raw_sequence(Path(r["raw_path"])) for r in dev]
    expected = [r["canonical_gloss"] for r in dev]
    signers = [r["signer_id"] for r in dev]
    hand = [float(np.mean(np.any(raw.hand_observed, axis=1))) for raw in raws]
    results: dict[str, Any] = {"n": len(dev), "conditions": {}}
    per_clip: dict[str, list[bool]] = {}
    for condition in ("dense", "phone_01_sparse"):
        for head, tail in (
            (0, 0),
            (0.1, 0),
            (0.2, 0),
            (0.3, 0),
            (0, 0.1),
            (0, 0.2),
            (0, 0.3),
            (0.2, 0.2),
        ):
            name = f"{condition}:head{int(head * 100)}:tail{int(tail * 100)}"
            batch = raws if head == tail == 0 else [trim(raw, head, tail) for raw in raws]
            probs = rec.probabilities(batch, condition)
            scored = [rec.score(p, g) for p, g in zip(probs, expected, strict=False)]
            correct = [s["correct"] for s in scored]
            per_clip[name] = correct
            by_signer = defaultdict(list)
            for s, c in zip(signers, correct, strict=False):
                by_signer[s].append(c)
            results["conditions"][name] = {
                "top1": float(np.mean(correct)),
                "top5": float(np.mean([s["top5"] for s in scored])),
                "by_signer": {s: round(float(np.mean(v)), 4) for s, v in sorted(by_signer.items())},
            }
            print(f"[dev] {name} top1={results['conditions'][name]['top1']:.4f}", flush=True)
    base = np.asarray(per_clip["phone_01_sparse:head0:tail0"])
    bins = np.digitize(hand, [0.25, 0.5, 0.75, 0.9])
    results["sparse_top1_by_hand_fraction"] = {
        label: {
            "n": int(np.sum(bins == b)),
            "top1": float(np.mean(base[bins == b])) if np.any(bins == b) else None,
        }
        for b, label in enumerate(["<0.25", "0.25-0.5", "0.5-0.75", "0.75-0.9", ">=0.9"])
    }
    results["sparse_observations_median"] = float(
        np.median(
            [
                int(
                    np.sum(
                        temporal_view_v2(
                            r, condition="phone_01_sparse", phone_completed_fps=PHONE_COMPLETED_FPS
                        )["mask"]
                    )
                )
                for r in raws
            ]
        )
    )
    return results


# ----------------------------------------------------------------------------- part D
def drop_hands(raw: RawSequence, fraction: float, mode: str, seed: int) -> RawSequence:
    """Emulate refiner rejection: accepted (frame, hand) entries lose hand_observed while the
    DWPose proposal/presence evidence is kept. 'motion' drops the fastest-moving entries first
    (wrist displacement from the previous observation), the pattern seen on the phone."""
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


def handloss_part(root: Path, rec: Recognizer) -> dict[str, Any]:
    rows = [json.loads(line) for line in (root / DATASET_INDEX).open(encoding="utf-8")]
    dev = [r for r in rows if r["split"] == "dev"]
    raws = [load_raw_sequence(Path(r["raw_path"])) for r in dev]
    keep = [i for i, raw in enumerate(raws) if np.mean(np.any(raw.hand_observed, axis=1)) >= 0.75]
    raws = [raws[i] for i in keep]
    expected = [dev[i]["canonical_gloss"] for i in keep]
    out: dict[str, Any] = {"n_clips": len(raws), "population": "DEV clips with hand_fraction>=0.75"}
    for condition in ("dense", "phone_01_sparse"):
        for mode in ("random", "motion"):
            for fraction in (0.0, 0.25, 0.5, 0.75):
                seeds = (0,) if fraction == 0 or mode == "motion" else (0, 1, 2)
                values = []
                for seed in seeds:
                    batch = [drop_hands(raw, fraction, mode, seed) for raw in raws]
                    probs = rec.probabilities(batch, condition)
                    values.append(
                        float(
                            np.mean(
                                [
                                    rec.score(p, g)["correct"]
                                    for p, g in zip(probs, expected, strict=False)
                                ]
                            )
                        )
                    )
                key = f"{condition}:{mode}:{int(fraction * 100)}"
                out[key] = float(np.mean(values))
                print(f"[handloss] {key} top1={out[key]:.4f}", flush=True)
    return out


# ----------------------------------------------------------------------------- part C
def segdev_part(root: Path, rec: Recognizer, package: suite.Package) -> dict[str, Any]:
    config = suite.read_json(suite.SUITES["03"][0])
    views = suite.load_tier1_views(root, config, "v1")
    glosses = {}
    for line in (root / DATASET_INDEX).open(encoding="utf-8"):
        item = json.loads(line)
        glosses[item["sample_id"]] = item["canonical_gloss"]
    rows = []
    batch: list[RawSequence] = []
    keys: list[tuple[int, str]] = []
    for view in views:
        t = view["timestamps_ms"]
        raw = view["raw"]
        n = len(t)
        inside = np.flatnonzero((t >= view["human_start_ms"]) & (t <= view["human_end_ms"]))
        row: dict[str, Any] = {
            "view": view["key"],
            "signer": view["signer"],
            "gloss": glosses.get(view["sample_id"]),
            "observations": n,
        }
        if row["gloss"] is None or len(inside) == 0:
            rows.append({**row, "skipped": True})
            continue
        first, last = int(inside[0]), int(inside[-1])
        k = len(rows)
        batch.append(raw)
        keys.append((k, "full_clip"))
        batch.append(slice_raw_safe(raw, first, last))
        keys.append((k, "oracle_tight"))
        batch.append(slice_raw_safe(raw, *oracle_ctx_window(t, first, last)))
        keys.append((k, "oracle_ctx"))
        probs = package.probabilities(view["features"])
        decoder = CausalStreamingSignEventDecoder(suite.CONFIG_01)
        decoder.run(t, probs, np.argmax(probs, axis=1))
        best = None
        for e in decoder.events:
            if max(first, e.logical_active_start_index) <= min(last, e.logical_active_end_index):
                best = e
                break
        row["events"] = len(decoder.events)
        if best is not None:
            w = window_for(
                t,
                best.logical_active_start_index,
                best.logical_active_end_index,
                best.first_post_index,
                best.emitted_at_index,
            )
            row["runtime_coverage"] = coverage(w, t, first, last)
            batch.append(slice_raw_safe(raw, *w))
            keys.append((k, "runtime"))
        rows.append(row)
    for (k, kind), p in zip(keys, rec.probabilities(batch), strict=False):
        rows[k][kind] = rec.score(p, rows[k]["gloss"])
    scored = [r for r in rows if not r.get("skipped")]
    summary = {
        kind: {
            "n": sum(kind in r for r in scored),
            "top1": sum(r[kind]["correct"] for r in scored if kind in r),
        }
        for kind in ("full_clip", "oracle_tight", "oracle_ctx", "runtime")
    }
    summary["runtime_as_fraction_of_all"] = summary["runtime"]["top1"] / max(1, len(scored))
    return {"rows": rows, "summary": summary, "scored_views": len(scored)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--parts", nargs="+", default=["phone", "dev", "segdev"])
    parser.add_argument("--s2-keras", type=Path, help="candidate S2 (default: frozen S2-R2)")
    parser.add_argument("--s2-normalization", type=Path)
    parser.add_argument("--recognizer", type=Path, help="candidate recognizer (default: frozen)")
    parser.add_argument("--sparse-fps", type=float, help="override the phone sparse cadence")
    args = parser.parse_args()
    if args.sparse_fps:
        global PHONE_COMPLETED_FPS
        PHONE_COMPLETED_FPS = args.sparse_fps
    root = args.evidence_root
    config = suite.read_json(suite.SUITES["03"][0])
    ref = config["reference_package"]
    if args.s2_keras:
        package = suite.load_package("CANDIDATE", "v1", args.s2_keras, args.s2_normalization)
    else:
        package = suite.load_package(
            ref["package_id"],
            "v1",
            root / ref["keras"],
            root / ref["normalization"],
            ref["keras_sha256"],
            ref["normalization_sha256"],
        )
    rec = Recognizer(root, args.recognizer)
    result: dict[str, Any] = {"recognizer_sha256": rec.sha256, "s2_package": package.identity}
    if "phone" in args.parts:
        result["phone"] = phone_part(root, rec, package)
        signs = [s for s in result["phone"]["signs"] if not s.get("uncertain")]
        result["phone_summary"] = {
            "first_failure": dict(Counter(s["first_failure"] for s in signs)),
            "first_failure_s2_valid": dict(
                Counter(s["first_failure"] for s in signs if s["s2_valid"])
            ),
            "oracle_tight_top1": sum(s["oracle_tight"]["correct"] for s in signs),
            "oracle_ctx_top1": sum(s["oracle_ctx"]["correct"] for s in signs),
            "runtime_top1_s2_valid": sum(
                s.get("runtime", {}).get("correct", False) for s in signs if s["s2_valid"]
            ),
            "n": len(signs),
            "n_s2_valid": sum(s["s2_valid"] for s in signs),
        }
        print(json.dumps(result["phone_summary"], indent=1), flush=True)
    if "segdev" in args.parts:
        result["segdev"] = segdev_part(root, rec, package)
        print(json.dumps(result["segdev"]["summary"], indent=1), flush=True)
    if "dev" in args.parts:
        result["dev"] = dev_part(root, rec)
    if "handloss" in args.parts:
        result["handloss"] = handloss_part(root, rec)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True, default=float) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
