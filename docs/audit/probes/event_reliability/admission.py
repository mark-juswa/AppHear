"""Whole-event admission: can a completed event be rejected as non-sign without losing words?

Inputs: stream_ledger_<CFG>.json (CAL + held-out DEV) and ledger_<CFG>.json (phone).
Pools (fixed before any validation or phone result was looked at):
  CALIBRATION  CAL streams (GENUINE vs NONSIGN; P1 = hands-visible, N0 = no-hands) and held-out DEV
               calibration signers P5/P12/P21 (GENUINE with a correct word vs NONSIGN rest events)
  VALIDATION   held-out DEV signers P26/P39 (same definitions)
  PHONE        Tier-2 + labelled shadow session (development-exposed): GENUINE vs CONFIRMED_NONSIGN;
               UNREVIEWED / UNCERTAIN events are reported, never counted as false
Rules, each a monotone admit-if-score>=threshold:
  HANDS        accepted-hand fraction over the logical ACTIVE span
  WORD_P1      frozen WORD top-1 probability
  HANDS+WORD   both thresholds (grid)
  LOGISTIC     L2 logistic regression on all ledger evidence, fit on CALIBRATION only
Selection rule (pre-registered): on CALIBRATION, keep >= 95% of GENUINE events on CAL and >= 95%
of correct-word events on DEV-cal; among those, maximise the fraction of NONSIGN events removed
(CAL P1 and DEV-cal pooled per event); ties -> lower threshold.
Correction (made after the first run, reported as such): 72 of 82 DEV "rest" events lie within one
observation of a governed sign span and 37 output that sign's gloss, so DEV rest events are mostly
fragments of the adjacent sign, not ordinary movement. `--nonsign p1` therefore calibrates the
non-sign side on CAL P1 (hands-visible, reviewed) only; DEV rest events are reported as
"fragments". Both runs are kept (admission_<CFG>.json and admission_<CFG>__p1.json).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).parent
CAL_SIGNERS = {"asl_citizen:P5", "asl_citizen:P12", "asl_citizen:P21"}
FEATURES = (
    "hand_fraction",
    "both_hands_fraction",
    "window_hand_fraction",
    "s2_peak_active",
    "s2_mean_active",
    "s2_active_fraction",
    "duration_ms",
    "logical_observations",
    "motion_wrist_travel_per_s",
    "motion_shape_change",
    "word_p1",
    "word_margin",
    "word_entropy",
    "word_stability",
    "v2_p1",
    "word_models_agree",
)
KEEP_FLOOR = 0.95
GRID = np.round(np.arange(0.0, 1.0001, 0.05), 2)


def auc(pos: np.ndarray, neg: np.ndarray) -> float | None:
    if len(pos) == 0 or len(neg) == 0:
        return None
    greater = (pos[:, None] > neg[None, :]).mean()
    ties = (pos[:, None] == neg[None, :]).mean()
    return float(greater + 0.5 * ties)


class Logistic:
    def __init__(self, l2: float = 1.0) -> None:
        self.l2 = l2

    def fit(self, x: np.ndarray, y: np.ndarray, w: np.ndarray) -> Logistic:
        self.mean, self.std = x.mean(0), x.std(0) + 1e-9
        z = (x - self.mean) / self.std
        coef, bias = np.zeros(z.shape[1]), 0.0
        w = w / w.sum()
        for _ in range(4000):
            p = 1.0 / (1.0 + np.exp(-(z @ coef + bias)))
            g = p - y
            coef -= 0.5 * (z.T @ (w * g) + self.l2 * coef / len(y))
            bias -= 0.5 * float(np.sum(w * g))
        self.coef, self.bias = coef, bias
        return self

    def score(self, x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-(((x - self.mean) / self.std) @ self.coef + self.bias)))


def matrix(rows: list[dict[str, Any]]) -> np.ndarray:
    return np.asarray([[float(r.get(f, 0.0)) for f in FEATURES] for r in rows], np.float64)


def pools(stream: dict[str, Any], phone: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    dev_cal = [r for r in stream["dev"] if r["signer"] in CAL_SIGNERS]
    dev_val = [r for r in stream["dev"] if r["signer"] not in CAL_SIGNERS]
    phone_rows = [
        r
        for name, v in phone["sessions"].items()
        if v["kind"] != "SHADOW_PROTOCOL_ONLY"
        for r in v["events"]
    ]
    return {
        "cal_genuine": [r for r in stream["cal"] if r["category"] == "GENUINE"],
        "cal_nonsign_p1": [
            r for r in stream["cal"] if r["category"] == "NONSIGN" and r["family"] == "P1"
        ],
        "cal_nonsign_n0": [
            r for r in stream["cal"] if r["category"] == "NONSIGN" and r["family"] == "N0"
        ],
        "devcal_correct": [
            r for r in dev_cal if r["category"] == "GENUINE" and r.get("frozen_correct")
        ],
        "devcal_wrong": [
            r for r in dev_cal if r["category"] == "GENUINE" and not r.get("frozen_correct")
        ],
        "devcal_nonsign": [r for r in dev_cal if r["category"] == "NONSIGN"],
        "devval_correct": [
            r for r in dev_val if r["category"] == "GENUINE" and r.get("frozen_correct")
        ],
        "devval_wrong": [
            r for r in dev_val if r["category"] == "GENUINE" and not r.get("frozen_correct")
        ],
        "devval_nonsign": [r for r in dev_val if r["category"] == "NONSIGN"],
        "phone_correct": [
            r for r in phone_rows if r["category"] == "GENUINE" and r.get("frozen_correct")
        ],
        "phone_wrong": [
            r for r in phone_rows if r["category"] == "GENUINE" and not r.get("frozen_correct")
        ],
        "phone_nonsign": [r for r in phone_rows if r["category"] == "CONFIRMED_NONSIGN"],
        "phone_unreviewed": [
            r for r in phone_rows if r["category"] in ("UNREVIEWED", "UNCERTAIN", "PARTIAL_NONSIGN")
        ],
    }


def kept(rows: list[dict[str, Any]], admit: Any) -> float:
    return float(np.mean([admit(r) for r in rows])) if rows else float("nan")


NONSIGN_POOL = ("cal_nonsign_p1", "devcal_nonsign")


def select(p: dict[str, list[dict[str, Any]]], make: Any, grid: list[Any]) -> dict[str, Any]:
    best = None
    nonsign = [r for k in NONSIGN_POOL for r in p[k]]
    for th in grid:
        admit = make(th)
        keep_cal = kept(p["cal_genuine"], admit)
        keep_dev = kept(p["devcal_correct"], admit)
        removed = 1.0 - kept(nonsign, admit)
        if keep_cal >= KEEP_FLOOR and keep_dev >= KEEP_FLOOR:
            key = (removed, -float(np.sum(th)) if isinstance(th, tuple) else -float(th))
            if best is None or key > best["key"]:
                best = {"key": key, "threshold": th, "calibration_removed": removed}
    assert best is not None
    return best


def report(p: dict[str, list[dict[str, Any]]], admit: Any) -> dict[str, Any]:
    return {k: {"n": len(v), "kept": kept(v, admit)} for k, v in p.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="ARM_A_E10__CONFIRM_BOUNDARY_70")
    parser.add_argument("--nonsign", choices=("p1_and_dev", "p1"), default="p1_and_dev")
    args = parser.parse_args()
    global NONSIGN_POOL
    if args.nonsign == "p1":
        NONSIGN_POOL = ("cal_nonsign_p1",)
    stream = json.loads((HERE / f"stream_ledger_{args.config}.json").read_text(encoding="utf-8"))
    phone = json.loads((HERE / f"ledger_{args.config}.json").read_text(encoding="utf-8"))
    p = pools(stream, phone)
    out: dict[str, Any] = {"config": args.config, "pool_sizes": {k: len(v) for k, v in p.items()}}
    out["feature_auc"] = {
        f: {
            "cal_genuine_vs_p1": auc(
                matrix(p["cal_genuine"])[:, i], matrix(p["cal_nonsign_p1"])[:, i]
            ),
            "devcal_correct_vs_nonsign": auc(
                matrix(p["devcal_correct"])[:, i], matrix(p["devcal_nonsign"])[:, i]
            ),
            "devval_correct_vs_nonsign": auc(
                matrix(p["devval_correct"])[:, i], matrix(p["devval_nonsign"])[:, i]
            ),
            "phone_correct_vs_nonsign": auc(
                matrix(p["phone_correct"])[:, i], matrix(p["phone_nonsign"])[:, i]
            ),
        }
        for i, f in enumerate(FEATURES)
    }
    rules: dict[str, Any] = {}
    hand = lambda th: (lambda r: r["hand_fraction"] >= th)  # noqa: E731
    word = lambda th: (lambda r: r["word_p1"] >= th)  # noqa: E731
    both = lambda th: (lambda r: hand(th[0])(r) and word(th[1])(r))  # noqa: E731
    pos = p["cal_genuine"] + p["devcal_correct"]
    neg = [r for k in NONSIGN_POOL for r in p[k]]
    x = matrix(pos + neg)
    y = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
    w = np.r_[np.full(len(pos), 0.5 / len(pos)), np.full(len(neg), 0.5 / len(neg))]
    model = Logistic().fit(x, y, w)
    logit = lambda th: (lambda r: float(model.score(matrix([r]))[0]) >= th)  # noqa: E731
    specs = {
        "HANDS": (hand, list(GRID)),
        "WORD_P1": (word, list(GRID)),
        "HANDS+WORD": (both, [(a, b) for a in GRID for b in GRID]),
        "LOGISTIC": (logit, list(np.round(np.arange(0.0, 1.0001, 0.02), 2))),
    }
    for name, (make, grid) in specs.items():
        chosen = select(p, make, grid)
        admit = make(chosen["threshold"])
        rules[name] = {
            "threshold": chosen["threshold"],
            "calibration_nonsign_removed": chosen["calibration_removed"],
            "pools": report(p, admit),
        }
    rules["LOGISTIC"]["coefficients"] = dict(
        zip(FEATURES, model.coef.round(3).tolist(), strict=True)
    )
    out["rules"] = rules
    out["nonsign_calibration_pool"] = list(NONSIGN_POOL)
    suffix = "__p1" if args.nonsign == "p1" else ""
    (HERE / f"admission_{args.config}{suffix}.json").write_text(
        json.dumps(out, indent=1, default=float)
    )
    print("pool sizes", out["pool_sizes"])
    for f, a in out["feature_auc"].items():
        print(f"  {f:28s}", {k: (round(v, 3) if v is not None else None) for k, v in a.items()})
    for name, r in rules.items():
        keys = (
            "cal_genuine",
            "cal_nonsign_p1",
            "cal_nonsign_n0",
            "devcal_correct",
            "devcal_nonsign",
            "devval_correct",
            "devval_wrong",
            "devval_nonsign",
            "phone_correct",
            "phone_wrong",
            "phone_nonsign",
            "phone_unreviewed",
        )
        print(
            name, "th", r["threshold"], " ".join(f"{k}={r['pools'][k]['kept']:.2f}" for k in keys)
        )


if __name__ == "__main__":
    main()
