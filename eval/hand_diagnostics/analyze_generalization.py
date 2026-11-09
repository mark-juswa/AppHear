"""Cross-subject generalization of DWPose echo-detection signals (numpy only). Offline-probe data + manually specified ground truth.

DECISION UNIT. Echo suppression can only matter when BOTH hand groups are observed in a frame (otherwise nothing is duplicated), so every
analysis here is restricted to those frames. In such a frame each observed group is one unit, labelled from the ground truth the person was asked to
produce: one-hand segment -> the shown side is REAL and the other group is an ECHO; two-hand segment -> both groups are REAL. Segments with no truth
(dynamic enter/leave) or no hands are excluded. Crossing and overlapping-pair poses are flagged DOUBTFUL: the overlays showed both groups on ONE hand,
so "both real" is not a safe per-group label there; they are reported separately and with/without.

RULES (each flags units as echo; the app would drop a flagged group):
  support_abs      flag group if its mean DWPose support < T
  body_wrist_abs   flag group if its same-side body-wrist support < T
  ratio            ROIs overlap (IoU >= 0.1) and weaker/stronger support < T  -> flag the weaker group
  handedness       flag group if the refiner says it is the OTHER hand (slot-consistency < 0.5; the natural decision boundary, not tuned)
  overlap_only     ROI IoU >= T -> flag the weaker-support group (generous to this baseline: it is told WHICH group; overlap alone cannot say)
  ratio+corrob     ratio rule AND (weaker group's handedness disagrees with its slot OR its body-wrist support is lower than the other group's)
THRESHOLD DISCIPLINE. T is chosen on the TRAINING subject only (max Youden J = echo rejection - false suppression of real units) and then
APPLIED UNCHANGED to the held-out subject. No threshold is chosen from the data it is scored on, and none is recommended for production here.

Metrics (units unless noted): echo_rejection_rate; genuine_two_hand_preservation_rate (real units of two-hand poses not flagged);
false_suppression_rate (real units flagged, all real); and the frame-level two-hand preservation (no group of a genuine two-hand frame flagged).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from eval.hand_diagnostics.analyze_probe import observed, roi_iou
from eval.hand_diagnostics.capture_pose_session import CONFIG

DOUBTFUL = {"crossing", "overlap"}
MIN_ROI_IOU = 0.1
RULES = ("support_abs", "body_wrist_abs", "ratio", "handedness", "overlap_only", "ratio+corrob")
LEARNED = {"support_abs": "support", "body_wrist_abs": "bws", "ratio": "ratio", "overlap_only": "roi_iou", "ratio+corrob": "ratio"}


def frames_from_probe(rows: list[dict], schedule: dict, subject: str, exclude: set[str] = frozenset()) -> list[dict]:
    """One record per frame in which both groups are observed and ground truth is known."""
    out = []
    for r in rows:
        seg = r["segment"]
        meta = schedule.get(seg)
        if seg in exclude or not meta or meta["truth"] is None:
            continue
        tr = meta["truth"]
        if not (tr["L"] or tr["R"]):
            continue
        g = r["normal"]["groups"]
        if not (observed(g["L"]) and observed(g["R"])):
            continue
        bw = r["normal"]["body_wrist"]
        sup = {"L": g["L"]["support_mean"], "R": g["R"]["support_mean"]}
        weaker = "L" if sup["L"] <= sup["R"] else "R"
        strong = "R" if weaker == "L" else "L"
        h = {s: g[s]["refined"]["handedness"] for s in "LR"}
        out.append({
            "subject": subject, "segment": seg, "n": r["n"], "config": meta.get("config") or CONFIG.get(seg, "other"),
            "truth": tr, "two_hands": bool(tr["L"] and tr["R"]), "roi_iou": roi_iou(g["L"]["roi"], g["R"]["roi"]),
            "support": sup, "ratio": (sup[weaker] / sup[strong]) if sup[strong] > 0 else 1.0, "weaker": weaker,
            "bws": {"L": bw["L"]["support"], "R": bw["R"]["support"]},
            "slot_consistency": {"L": 1.0 - h["L"], "R": h["R"]},
        })
    return out


def units(frames: list[dict]) -> list[dict]:
    """(frame, side) units with label real/echo."""
    u = []
    for f in frames:
        for s in "LR":
            u.append({"frame": f, "side": s, "real": bool(f["truth"][s]), "config": f["config"], "subject": f["subject"], "two_hands": f["two_hands"]})
    return u


def flagged(f: dict, rule: str, T: float | None) -> set[str]:
    """Sides the rule would drop in this frame."""
    w = f["weaker"]
    s_ = "R" if w == "L" else "L"
    if rule == "support_abs":
        return {s for s in "LR" if f["support"][s] < T}
    if rule == "body_wrist_abs":
        return {s for s in "LR" if f["bws"][s] < T}
    if rule == "handedness":
        return {s for s in "LR" if f["slot_consistency"][s] < 0.5}
    if rule == "overlap_only":
        return {w} if f["roi_iou"] >= T else set()
    if rule in ("ratio", "ratio+corrob"):
        if f["roi_iou"] < MIN_ROI_IOU or not f["ratio"] < T:
            return set()
        if rule == "ratio+corrob" and not (f["slot_consistency"][w] < 0.5 or f["bws"][w] < f["bws"][s_]):
            return set()
        return {w}
    raise ValueError(rule)


def feature_values(frames: list[dict], rule: str) -> list[float]:
    key = LEARNED[rule]
    vals = []
    for f in frames:
        if key == "support":
            vals += list(f["support"].values())
        elif key == "bws":
            vals += list(f["bws"].values())
        else:
            vals.append(f[key])
    return vals


def rates(frames: list[dict], rule: str, T: float | None, drop_doubtful: bool = False) -> dict:
    echo_n = echo_hit = real_n = real_hit = two_n = two_hit = 0
    two_frames = two_frames_clean = 0
    for f in frames:
        if drop_doubtful and f["config"] in DOUBTFUL:
            continue
        fl = flagged(f, rule, T)
        for s in "LR":
            if f["truth"][s]:
                real_n += 1
                real_hit += s in fl
                if f["two_hands"]:
                    two_n += 1
                    two_hit += s in fl
            else:
                echo_n += 1
                echo_hit += s in fl
        if f["two_hands"]:
            two_frames += 1
            two_frames_clean += not fl
    r = lambda a, b: round(a / b, 4) if b else None
    return {"echo_rejection_rate": r(echo_hit, echo_n), "n_echo_units": echo_n,
            "genuine_two_hand_preservation_rate": r(two_n - two_hit, two_n), "n_two_hand_real_units": two_n,
            "false_suppression_rate": r(real_hit, real_n), "n_real_units": real_n,
            "two_hand_frame_preservation_rate": r(two_frames_clean, two_frames), "n_two_hand_frames": two_frames}


def learn_threshold(train: list[dict], rule: str) -> float | None:
    """Max Youden J on TRAINING data; candidates = midpoints of the observed feature values."""
    if rule == "handedness":
        return None
    vals = np.unique(np.array(feature_values(train, rule), float))
    if len(vals) < 2:
        return None
    cands = list(np.r_[vals[0] - 1e-6, (vals[:-1] + vals[1:]) / 2, vals[-1] + 1e-6])
    if len(cands) > 400:
        cands = list(np.quantile(vals, np.linspace(0, 1, 400)))
    best, bestJ = None, -9.0
    for T in cands:
        r = rates(train, rule, T)
        if r["echo_rejection_rate"] is None or r["false_suppression_rate"] is None:
            continue
        J = r["echo_rejection_rate"] - r["false_suppression_rate"]
        if J > bestJ + 1e-9 or (abs(J - bestJ) <= 1e-9 and best is not None and r["false_suppression_rate"] < rates(train, rule, best)["false_suppression_rate"]):
            best, bestJ = T, J
    return float(best) if best is not None else None


def transfer(frames: list[dict], subjects: list[str]) -> dict:
    """Train on one subject, test on every other; all rules; per config."""
    out = {}
    for train_s in subjects:
        for test_s in subjects:
            if train_s == test_s:
                continue
            tr = [f for f in frames if f["subject"] == train_s]
            te = [f for f in frames if f["subject"] == test_s]
            block = {}
            for rule in RULES:
                T = learn_threshold(tr, rule)
                if T is None and rule != "handedness":
                    block[rule] = {"threshold_learned_on_train": None, "note": "no threshold could be learned on the training subject"}
                    continue
                per_cfg = {cfg: rates([f for f in te if f["config"] == cfg], rule, T) for cfg in sorted({f["config"] for f in te})}
                block[rule] = {"threshold_learned_on_train": None if T is None else round(T, 4), "overall": rates(te, rule, T),
                               "overall_without_doubtful_configs": rates(te, rule, T, drop_doubtful=True), "per_config": per_cfg}
            out[f"train={train_s} -> test={test_s}"] = block
    return out


def separation(frames: list[dict]) -> dict:
    """Threshold-free picture: per subject and config, echo vs genuine ranges of the relative ratio and of absolute support."""
    out = {}
    for s in sorted({f["subject"] for f in frames}):
        fs = [f for f in frames if f["subject"] == s]
        echo_r = [f["ratio"] for f in fs if not f["two_hands"] and f["roi_iou"] >= MIN_ROI_IOU]
        d = {"echo_ratio_min_p50_max": _q(echo_r), "n_echo_frames": len(echo_r), "genuine_pair_ratio_by_config": {}}
        for cfg in sorted({f["config"] for f in fs if f["two_hands"]}):
            v = [f["ratio"] for f in fs if f["two_hands"] and f["config"] == cfg and f["roi_iou"] >= MIN_ROI_IOU]
            d["genuine_pair_ratio_by_config"][cfg] = {"n": len(v), "min_p50_max": _q(v), "min_above_echo_max": (round(min(v) - max(echo_r), 3) if v and echo_r else None)}
        out[s] = d
    return out


def _q(v):
    return [round(float(np.min(v)), 3), round(float(np.median(v)), 3), round(float(np.max(v)), 3)] if len(v) else None


def run(datasets: list[tuple[str, Path, Path, set]]) -> dict:
    frames = []
    for subject, probe, sched, exclude in datasets:
        rows = [json.loads(line) for line in Path(probe).read_text().splitlines()]
        frames += frames_from_probe(rows, json.loads(Path(sched).read_text()), subject, exclude)
    subjects = sorted({f["subject"] for f in frames})
    return {"subjects": subjects, "frames_both_groups_observed": {s: sum(1 for f in frames if f["subject"] == s) for s in subjects},
            "configs": {c: sum(1 for f in frames if f["config"] == c) for c in sorted({f["config"] for f in frames})},
            "separation": separation(frames), "transfer": transfer(frames, subjects), "_frames": frames}


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text())
    res = run([(d["subject"], d["probe"], d["schedule"], set(d.get("exclude", []))) for d in spec["datasets"]])
    frames = res.pop("_frames")
    Path(sys.argv[2]).write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("subjects", "frames_both_groups_observed", "configs")}, indent=1))
