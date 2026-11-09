"""Analysis of an offline-probe run against the ground truth the person was asked to produce (numpy only).

Question: for a hand group that the app WOULD observe (refiner accepts it), which measurable signals separate a REAL hand from a PHANTOM
(the other group firing on the same single hand), without relying on overlap alone and without hurting genuine two-hand frames?

Labels (from schedule.json): in a one-hand segment the group of the shown side is REAL and the other group, if observed, is PHANTOM; in a
two-hand segment both observed groups are REAL; `none` and the dynamic segment are excluded from separation analysis.
Nothing here sets a threshold for the app. AUC is threshold-free; the leave-one-segment-out (LOSO) logistic model is an EVALUATION of how
much information the signals carry, trained and scored on different segments. One subject, one session: evidence, not a validated detector.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

SIDES = ("L", "R")
BODY_WRIST_KEY = {"L": "L", "R": "R"}
FEATURES = ["support_mean", "n_ge_030", "presence", "slot_consistency", "wrist_agreement", "body_wrist_support"]


def auc(pos, neg) -> float | None:
    """P(score_pos > score_neg) with ties counted half (Mann-Whitney)."""
    pos = np.asarray(pos, float)
    neg = np.asarray(neg, float)
    if len(pos) == 0 or len(neg) == 0:
        return None
    allv = np.concatenate([pos, neg])
    order = allv.argsort(kind="mergesort")
    ranks = np.empty(len(allv))
    i = 0
    sorted_v = allv[order]
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and sorted_v[j + 1] == sorted_v[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    r_pos = ranks[:len(pos)].sum()
    return float((r_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def observed(group: dict) -> bool:
    r = group.get("refined")
    return bool(r and r["presence"] >= 0.5 and r["n_valid"] >= 18)


def _box(xy):
    a = np.asarray(xy, float)
    return (a[:, 0].min(), a[:, 1].min(), a[:, 0].max(), a[:, 1].max()) if len(a) >= 3 else None


def skeleton_iou(xy_a, xy_b) -> float:
    a, b = _box(xy_a), _box(xy_b)
    if a is None or b is None:
        return 0.0
    iw = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    ih = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = iw * ih
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return float(inter / union) if union > 0 else 0.0


def group_features(frame: dict, side: str) -> dict:
    """Signals for one OBSERVED group of one frame (all from the unmirrored 'normal' pass, i.e. what the app sees)."""
    n = frame["normal"]
    g = n["groups"][side]
    other = n["groups"]["R" if side == "L" else "L"]
    h = g["refined"]["handedness"]
    p_slot = h if side == "R" else 1.0 - h           # probability, under the measured convention, that the crop shows THIS slot's hand
    bw = n["body_wrist"][BODY_WRIST_KEY[side]]
    wrist = np.asarray(g["wrist_xy"], float)
    dist = float(np.hypot(*(wrist - np.asarray(bw["xy"], float))))
    side_len = g["roi"][2]
    return {
        "support_mean": g["support_mean"], "n_ge_030": g["n_ge_030"], "presence": g["refined"]["presence"],
        "slot_consistency": p_slot,
        "wrist_agreement": -min(dist / side_len, 5.0),    # higher = hand wrist is near the SAME-side body wrist
        "body_wrist_support": bw["support"],
        "skeleton_iou_other": skeleton_iou(g["refined"]["xy"], other["refined"]["xy"]) if observed(other) else 0.0,
        "roi_dist_other": float(np.hypot(g["roi"][0] - other["roi"][0], g["roi"][1] - other["roi"][1]) / side_len) if other["roi"] else 99.0,
    }


def build_table(rows: list[dict], schedule: dict) -> list[dict]:
    out = []
    for r in rows:
        truth = schedule[r["segment"]]["truth"]
        if truth is None or not (truth["L"] or truth["R"]):
            continue
        for side in SIDES:
            if not observed(r["normal"]["groups"][side]):
                continue
            f = group_features(r, side)
            f.update(segment=r["segment"], n=r["n"], side=side, real=bool(truth[side]), two_hands=bool(truth["L"] and truth["R"]))
            out.append(f)
    return out


def single_signal_aucs(table: list[dict]) -> dict:
    real = [t for t in table if t["real"]]
    phantom = [t for t in table if not t["real"]]
    real_two = [t for t in real if t["two_hands"]]
    res = {}
    for k in FEATURES + ["skeleton_iou_other", "roi_dist_other"]:
        sign = -1.0 if k == "skeleton_iou_other" else 1.0          # overlap: higher = MORE phantom-like, so negate to rank real above phantom
        pos = [sign * t[k] for t in real]
        neg = [sign * t[k] for t in phantom]
        res[k] = {"auc_all_real_vs_phantom": auc(pos, neg),
                  "auc_two_hand_real_vs_phantom": auc([sign * t[k] for t in real_two], neg)}
    return res


def _fit_logistic(x, y, l2=1.0, iters=50):
    x = np.column_stack([np.ones(len(x)), x])
    w = np.zeros(x.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(x @ w, -30, 30)))
        g = x.T @ (p - y) + l2 * np.r_[0, w[1:]]
        h = x.T @ (x * (p * (1 - p))[:, None]) + l2 * np.diag(np.r_[0, np.ones(len(w) - 1)])
        w -= np.linalg.solve(h + 1e-9 * np.eye(len(w)), g)
    return w


def loso_logistic(table: list[dict], feats: list[str]) -> dict:
    """Train on every segment but one, score the held-out segment. Reports out-of-segment AUC and error rates at p=0.5."""
    segs = sorted({t["segment"] for t in table})
    scores, labels, meta = [], [], []
    for held in segs:
        tr = [t for t in table if t["segment"] != held]
        te = [t for t in table if t["segment"] == held]
        if not te or len({t["real"] for t in tr}) < 2:
            continue
        x = np.array([[t[f] for f in feats] for t in tr], float)
        mu, sd = x.mean(0), x.std(0) + 1e-9
        w = _fit_logistic((x - mu) / sd, np.array([t["real"] for t in tr], float))
        xt = (np.array([[t[f] for f in feats] for t in te], float) - mu) / sd
        p = 1 / (1 + np.exp(-(np.column_stack([np.ones(len(xt)), xt]) @ w)))
        scores += list(p); labels += [t["real"] for t in te]; meta += [t for t in te]
    scores, labels = np.array(scores), np.array(labels)
    two_real = np.array([m["real"] and m["two_hands"] for m in meta])
    ph = ~labels
    return {"features": feats, "n": int(len(scores)), "auc_out_of_segment": auc(scores[labels], scores[ph]),
            "phantom_rejected_at_p0.5": float(np.mean(scores[ph] < 0.5)) if ph.any() else None, "n_phantom": int(ph.sum()),
            "two_hand_real_wrongly_rejected_at_p0.5": float(np.mean(scores[two_real] < 0.5)) if two_real.any() else None,
            "n_two_hand_real": int(two_real.sum()),
            "one_hand_real_wrongly_rejected_at_p0.5": float(np.mean(scores[labels & ~two_real] < 0.5)) if (labels & ~two_real).any() else None}


def reliability(rows: list[dict], schedule: dict, bins=(0, 0.1, 0.3, 0.7, 0.9, 1.0001)) -> list[dict]:
    """Is the refiner handedness value a calibrated probability of 'right hand'? Observed groups that hold a REAL hand of known side."""
    xs, ys = [], []
    for r in rows:
        truth = schedule[r["segment"]]["truth"]
        if truth is None or (truth["L"] and truth["R"]) or not (truth["L"] or truth["R"]):
            continue
        side = "R" if truth["R"] else "L"
        g = r["normal"]["groups"][side]
        if observed(g):
            xs.append(g["refined"]["handedness"]); ys.append(side == "R")
    xs, ys = np.array(xs), np.array(ys)
    out = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (xs >= lo) & (xs < hi)
        out.append({"bin": [lo, round(min(hi, 1.0), 2)], "n": int(m.sum()), "mean_value": float(xs[m].mean()) if m.any() else None,
                    "fraction_truly_right_hand": float(ys[m].mean()) if m.any() else None})
    return out


def roi_iou(a, b) -> float:
    """IoU of two [cx, cy, side] squares (the boxes the app draws and crops)."""
    if not a or not b:
        return 0.0
    ax0, ay0, ax1, ay1 = a[0] - a[2] / 2, a[1] - a[2] / 2, a[0] + a[2] / 2, a[1] + a[2] / 2
    bx0, by0, bx1, by1 = b[0] - b[2] / 2, b[1] - b[2] / 2, b[0] + b[2] / 2, b[1] + b[2] / 2
    inter = max(0.0, min(ax1, bx1) - max(ax0, bx0)) * max(0.0, min(ay1, by1) - max(ay0, by0))
    union = a[2] ** 2 + b[2] ** 2 - inter
    return float(inter / union) if union > 0 else 0.0


def support_ratio_sweep(rows: list[dict], schedule: dict, taus=(0.3, 0.4, 0.5, 0.6, 0.7), min_roi_iou: float = 0.1) -> dict:
    """COUNTERFACTUAL (offline, no deployment threshold): for frames where BOTH groups are observed and their ROIs overlap, the weaker group
    (by mean DWPose support) would be dropped if weak/strong < tau. Reports, per frame category, how often that would fire.
    phantom = one-hand segment (the weaker group is the echo); two_hand_* = genuine pairs (dropping the weaker would remove a real hand);
    crossing is listed separately because its per-group ground truth is doubtful (both groups were seen on one hand)."""
    cats: dict[str, list[float]] = {"phantom_one_hand": [], "two_hand_apart": [], "two_hand_touching": [], "two_hand_crossing": []}
    for r in rows:
        truth = schedule[r["segment"]]["truth"]
        if truth is None or not (truth["L"] or truth["R"]):
            continue
        g = r["normal"]["groups"]
        if not (observed(g["L"]) and observed(g["R"])) or roi_iou(g["L"]["roi"], g["R"]["roi"]) < min_roi_iou:
            continue
        s = sorted([g["L"]["support_mean"], g["R"]["support_mean"]])
        ratio = s[0] / s[1] if s[1] > 0 else 1.0
        if truth["L"] and truth["R"]:
            key = {"both_apart": "two_hand_apart", "both_touching": "two_hand_touching", "both_crossing": "two_hand_crossing"}.get(r["segment"])
            if key:
                cats[key].append(ratio)
        else:
            cats["phantom_one_hand"].append(ratio)
    out = {"min_roi_iou_for_overlap": min_roi_iou, "categories": {}}
    for k, v in cats.items():
        a = np.array(v)
        out["categories"][k] = {"n_frames_both_observed_and_overlapping": int(len(a)),
                                "ratio_min_p50_max": [round(float(a.min()), 3), round(float(np.median(a)), 3), round(float(a.max()), 3)] if len(a) else None,
                                "fraction_weaker_group_dropped": {str(t): round(float(np.mean(a < t)), 3) for t in taus} if len(a) else None}
    return out


def segment_summary(rows: list[dict], schedule: dict) -> dict:
    """Per pose: how often each group makes an ROI / is observed, its support, and (one-hand poses) how the echo group relates to the real one."""
    out = {}
    for seg, meta in schedule.items():
        rs = [r for r in rows if r["segment"] == seg]
        if not rs:
            continue
        d = {"truth": meta["truth"], "frames": len(rs), "groups": {}}
        for s in SIDES:
            gs = [r["normal"]["groups"][s] for r in rs]
            d["groups"][s] = {
                "roi_fraction": round(float(np.mean([g["roi"] is not None for g in gs])), 3),
                "observed_fraction": round(float(np.mean([observed(g) for g in gs])), 3),
                "support_mean": round(float(np.mean([g["support_mean"] for g in gs])), 3),
                "points_ge_0.10_mean": round(float(np.mean([g["n_ge_010"] for g in gs])), 1),
                "handedness_mean": round(float(np.mean([g["refined"]["handedness"] for g in gs if "refined" in g])), 3) if any("refined" in g for g in gs) else None,
                "handedness_mean_flipped_crop": round(float(np.mean([g["refined_flipped_crop"]["handedness"] for g in gs if "refined_flipped_crop" in g])), 3) if any("refined_flipped_crop" in g for g in gs) else None,
                "mirrored_image_support_mean": round(float(np.mean([r["mirrored_image"]["groups"][s]["support_mean"] for r in rs])), 3),
            }
        tr = meta["truth"]
        if tr and (tr["L"] != tr["R"]):
            real = "L" if tr["L"] else "R"
            echo = "R" if real == "L" else "L"
            both = [r for r in rs if r["normal"]["groups"][real]["roi"] and r["normal"]["groups"][echo]["roi"]]
            d["echo_group"] = echo
            d["echo_roi_iou_with_real_median"] = round(float(np.median([roi_iou(r["normal"]["groups"][real]["roi"], r["normal"]["groups"][echo]["roi"]) for r in both])), 3) if both else None
            d["echo_support_over_real_support_median"] = round(float(np.median([r["normal"]["groups"][echo]["support_mean"] / r["normal"]["groups"][real]["support_mean"] for r in rs])), 3)
        out[seg] = d
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    probe_jsonl, schedule_json = Path(argv[0]), Path(argv[1])
    rows = [json.loads(line) for line in probe_jsonl.read_text().splitlines()]
    schedule = json.loads(schedule_json.read_text())
    table = build_table(rows, schedule)
    result = {
        "table_rows": len(table), "single_signal_auc": single_signal_aucs(table),
        "loso": {"support": loso_logistic(table, ["support_mean"]),
                 "support+wrist": loso_logistic(table, ["support_mean", "wrist_agreement", "body_wrist_support"]),
                 "support+handedness": loso_logistic(table, ["support_mean", "slot_consistency"]),
                 "all_signals": loso_logistic(table, FEATURES)},
        "handedness_reliability": reliability(rows, schedule),
        "support_ratio_counterfactual": support_ratio_sweep(rows, schedule),
        "segment_summary": segment_summary(rows, schedule),
    }
    print(json.dumps(result, indent=1))
    if len(argv) > 2:
        Path(argv[2]).write_text(json.dumps(result, indent=1))
        # per-frame scalar table (no coordinates, no images)
        Path(argv[2]).with_name("feature_table.json").write_text(json.dumps(table))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
