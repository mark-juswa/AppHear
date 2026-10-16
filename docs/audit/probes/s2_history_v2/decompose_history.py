"""Held-out decomposition of S2 history dependence (read-only diagnostic).

Targets: the 69 signer-disjoint segmentation DEV views. Histories are stitched at the RAW level
and the 378 features are recomputed over the combined sequence, so no artificial
"no previous observation" marker appears at the join unless a condition asks for it.

Factors separated:
  PADDING/LENGTH   still copies of the target's own first observation (same scene, no motion)
  JOIN MARKER      identical POST-content history joined at feature level (marker) vs raw level
  IDLE SCENE       human-confirmed 'No sign' interval (rows 0-39, close face, no hands) of the
                   untouched distinct-signer session vs phone rest. (Labelled 'motion' in the
                   first run by mistake; suite v02 adds the true 'Non sign movement' interval.)
  SIGN CONTEXT     previous sign of the same held-out signer, then a still gap of g observations
                   (does acquisition recover once the previous sign leaves the 61-obs field?)
  HOLD             previous sign cut at its last ACTIVE observation, held still for g observations,
                   then the next sign starting one observation before its ACTIVE (hands-up)
Synthetic still/hold rows are duplicated real observations; they exist only in this diagnostic.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from collections import defaultdict
from dataclasses import fields
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

ROOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])
ACTIVE, POST = 1, 2


def concat_raw(parts: list[RawSequence], interval_ms: float) -> RawSequence:
    """Chronological concatenation; each part keeps its internal spacing, joins use interval."""
    arrays: dict[str, list[np.ndarray]] = defaultdict(list)
    offset, timestamps = 0.0, []
    for part in parts:
        t = np.asarray(part.timestamp_ms, np.float64)
        shifted = t - t[0] + offset
        timestamps.append(shifted)
        offset = float(shifted[-1]) + interval_ms
        for f in fields(RawSequence):
            if f.name not in ("metadata", "frame_index", "timestamp_ms"):
                arrays[f.name].append(np.asarray(getattr(part, f.name)))
    stamp = np.concatenate(timestamps)
    value = RawSequence(
        metadata=dict(parts[-1].metadata),
        frame_index=np.arange(len(stamp), dtype=np.int32),
        timestamp_ms=stamp,
        **{name: np.concatenate(chunks) for name, chunks in arrays.items()},
    )
    value.validate()
    return value


def repeat_obs(raw: RawSequence, index: int, count: int, interval_ms: float) -> RawSequence:
    idx = np.full(count, index, np.int32)
    base = subset_raw_unchecked(raw, idx)
    value = dataclasses.replace(
        base,
        timestamp_ms=np.arange(count, dtype=np.float64) * interval_ms,
        frame_index=np.arange(count, dtype=np.int32),
    )
    value.validate()
    return value


def subset_raw_unchecked(raw: RawSequence, idx: np.ndarray) -> RawSequence:
    return RawSequence(
        **{
            f.name: (dict(raw.metadata) if f.name == "metadata" else np.asarray(getattr(raw, f.name))[idx])
            for f in fields(RawSequence)
        }
    )


def slice_raw(raw: RawSequence, first: int, last: int) -> RawSequence:
    return subset_raw(raw, np.arange(first, last + 1, dtype=np.int32))


def main() -> None:
    config = suite.read_json(suite.CONFIG_PATH)
    manifest = suite.read_json(ROOT / config["tier1_dev"]["sparse_view_manifest"])
    raw_cache: dict[str, RawSequence] = {}
    views = []
    for item in manifest["rows"]:
        if item["phase7_partition"] != "DEV":
            continue
        with np.load(item["feature_path"], allow_pickle=False) as data:
            labels = np.asarray(data["labels"], np.int64)
            selected = np.asarray(data["selected_indices"], np.int32)
        path = str(item["source_raw_path"])
        raw_cache.setdefault(path, load_raw_sequence(Path(path)))
        raw = subset_raw(raw_cache[path], selected)
        views.append({"key": item["view_key"], "sample": item["sample_id"], "signer": item["signer_id"],
                      "view": item["view_id"], "interval": float(item["target_interval_ms"]),
                      "raw": raw, "labels": labels})
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for v in views:
        groups[(v["signer"], v["view"])].append(v)

    sessions = {}
    for name in ("OCT15_COMPACT", "SEP23_INDEPENDENT", "SEP23_REPRESENTATIVE"):
        sessions[name] = load_capture(ROOT / config["tier2_sessions"][name]["capture"],
                                      require_full_session=False).raw
    post_src = config["history_sources"]["POST_PHONE"]
    phone_post = slice_raw(sessions["OCT15_COMPACT"], post_src["first_row"], post_src["last_row"])
    rest_src = config["history_sources"]["REST_PHONE"]
    phone_rest = slice_raw(sessions["SEP23_REPRESENTATIVE"], rest_src["first_row"], rest_src["last_row"])
    # first confirmed non-sign interval >= 30 rows = the 'No sign' idle interval (rows 0-39)
    review = ROOT / config["tier2_sessions"]["SEP23_INDEPENDENT"]["review"]
    intervals = suite.read_json(review / "non_sign_visual_review.json")["confirmed_non_sign_intervals"]
    motion_iv = next(iv for iv in intervals if iv["end_index"] - iv["start_index"] + 1 >= 30)
    phone_motion = slice_raw(sessions["SEP23_INDEPENDENT"], motion_iv["start_index"], motion_iv["end_index"])

    results: dict[str, dict[str, Any]] = {}
    packages = {
        "S2_R2": suite.load_package("S2_R2", "v1", ROOT / config["reference_package"]["keras"],
                                    ROOT / config["reference_package"]["normalization"]),
        "PHASE7": suite.load_package(
            "PHASE7", "v1",
            ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase7_production_cadence_aligned_segmenter_01/best_model.keras",
            Path(str(ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase7_production_cadence_aligned_segmenter_01/cadence_aligned_normalization_stats.json")),
        ),
    }

    def score(pkg: Any, history: RawSequence | None, target: RawSequence, labels: np.ndarray,
              interval: float, history_active_mask: np.ndarray | None = None,
              feature_join: bool = False) -> dict[str, float]:
        if history is None:
            feats = suite.features_for_raw(target, "v1")
            n_hist = 0
        elif feature_join:
            feats = np.concatenate([suite.features_for_raw(history, "v1"), suite.features_for_raw(target, "v1")])
            n_hist = len(history.timestamp_ms)
        else:
            feats = suite.features_for_raw(concat_raw([history, target], interval), "v1")
            n_hist = len(history.timestamp_ms)
        pred = np.argmax(pkg.probabilities(feats), axis=1)
        tp, hp = pred[n_hist:], pred[:n_hist]
        act = labels == ACTIVE
        other = (labels != ACTIVE) & (labels >= 0)
        hist_ok = np.ones(n_hist, bool) if history_active_mask is None else ~history_active_mask
        return {
            "acquired": float(np.any(tp[act] == ACTIVE)),
            "recall": float(np.mean(tp[act] == ACTIVE)),
            "target_false_active": float(np.mean(tp[other] == ACTIVE)) if other.any() else 0.0,
            "history_false_active": float(np.mean(hp[hist_ok] == ACTIVE)) if n_hist and hist_ok.any() else 0.0,
        }

    for pname, pkg in packages.items():
        cond: dict[str, list[dict[str, float]]] = defaultdict(list)
        for v in views:
            raw, lab, iv = v["raw"], v["labels"], v["interval"]
            cond["NONE"].append(score(pkg, None, raw, lab, iv))
            for L in (1, 2, 4, 8, 16, 32, 60):
                cond[f"A_STILL_SELF_{L:02d}"].append(score(pkg, repeat_obs(raw, 0, L, iv), raw, lab, iv))
            for L in (15, 60):
                hist = slice_raw(phone_post, len(phone_post.timestamp_ms) - L, len(phone_post.timestamp_ms) - 1)
                cond[f"B_PHONE_POST_{L}_feature_join"].append(score(pkg, hist, raw, lab, iv, feature_join=True))
                cond[f"B_PHONE_POST_{L}_raw_join"].append(score(pkg, hist, raw, lab, iv))
            n_rest = len(phone_rest.timestamp_ms)
            cond["C_PHONE_REST_30"].append(score(pkg, slice_raw(phone_rest, n_rest - 30, n_rest - 1), raw, lab, iv))
            n_mot = len(phone_motion.timestamp_ms)
            cond["C_PHONE_NO_SIGN_IDLE_30"].append(
                score(pkg, slice_raw(phone_motion, n_mot - 30, n_mot - 1), raw, lab, iv))
            group = groups[(v["signer"], v["view"])]
            others = [o for o in group if o["sample"] != v["sample"]]
            if others:
                prev = others[0]
                pmask = prev["labels"] == ACTIVE
                last = len(prev["raw"].timestamp_ms) - 1
                for g in (0, 10, 20, 40, 60):
                    parts = [prev["raw"]] + ([repeat_obs(prev["raw"], last, g, iv)] if g else [])
                    hist = concat_raw(parts, iv)
                    mask = np.concatenate([pmask, np.zeros(g, bool)])
                    cond[f"D_PREV_SIGN_then_still_{g:02d}"].append(score(pkg, hist, raw, lab, iv, mask))
                p_act = np.flatnonzero(pmask)
                first_t = int(np.flatnonzero(lab == ACTIVE)[0])
                tgt = slice_raw(raw, max(0, first_t - 1), len(raw.timestamp_ms) - 1)
                tlab = lab[max(0, first_t - 1):]
                for g in (0, 3, 6, 12, 24):
                    parts = [slice_raw(prev["raw"], 0, int(p_act[-1]))]
                    if g:
                        parts.append(repeat_obs(prev["raw"], int(p_act[-1]), g, iv))
                    hist = concat_raw(parts, iv)
                    mask = np.concatenate([pmask[: int(p_act[-1]) + 1], np.zeros(g, bool)])
                    cond[f"E_HOLD_AT_SIGN_END_{g:02d}"].append(score(pkg, hist, tgt, tlab, iv, mask))
        summary = {}
        for c, rows in cond.items():
            summary[c] = {k: float(np.mean([r[k] for r in rows])) for k in rows[0]} | {"n": len(rows)}
        results[pname] = summary
        print(f"\n== {pname}")
        print(f"  {'condition':34s} {'n':>3s} {'acquired':>8s} {'recall':>7s} {'tgtFA':>6s} {'histFA':>7s}")
        for c, s in summary.items():
            print(f"  {c:34s} {s['n']:3d} {s['acquired']:8.3f} {s['recall']:7.3f} {s['target_false_active']:6.3f} {s['history_false_active']:7.3f}")
    OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
