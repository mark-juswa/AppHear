"""Is S2-R3's phone discrimination failure a data-quantity problem or a source/domain problem?

No training. Arm A e10 (and S2-R2 for reference), full-history probabilities.
1. Source descriptors per population (observation rows): accepted-hand fraction, both-hands
   fraction, body availability, hand scale (wrist->middle-MCP / max image side), hand centre
   height, cadence. Populations: CAL sign ACTIVE rows, CAL P1 (hands-visible) negative rows,
   CAL N0 negative rows, phone reviewed genuine-sign rows, phone confirmed non-sign rows.
2. Separability (AUC of peak P(ACTIVE) per sign vs per 9-observation non-sign chunk), with CAL
   negatives split into P1 and N0 (the earlier CAL AUC pooled both).
3. Source-cue test: can the source descriptors alone (no motion) separate CAL sign rows from
   CAL P1 rows? (per-chunk logistic regression, stream-grouped 2-fold.) High = S2 can win CAL by
   recognising the recording source instead of signing.
4. Counterfactuals on CAL streams (features recomputed from modified raw): body evidence removed;
   zoom x1.5 about the image centre (phone-like close framing). AUC sign vs P1 per condition.
Writes domain_shift.json.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics import event_reliability as er  # noqa: E402
from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics import s2_r3_train  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
CHUNK = 9
WRIST, MCP = 0, 9


def auc(pos: list[float], neg: list[float]) -> float:
    p, n = np.asarray(pos), np.asarray(neg)
    if not len(p) or not len(n):
        return float("nan")
    return float((p[:, None] > n[None, :]).mean() + 0.5 * (p[:, None] == n[None, :]).mean())


def chunks(rows: np.ndarray) -> list[np.ndarray]:
    if not len(rows):
        return []
    blocks = np.split(rows, np.flatnonzero(np.diff(rows) > 1) + 1)
    return [
        b[a : a + CHUNK]
        for b in blocks
        for a in range(0, len(b), CHUNK)
        if len(b[a : a + CHUNK]) >= 4
    ]


def descriptors(raw: Any, rows: np.ndarray) -> np.ndarray:
    """Per-row source descriptors: [any hand, both hands, body available, hand scale, hand y]."""
    size = np.max(np.asarray(raw.source_size, np.float64), axis=1)
    height = np.asarray(raw.source_size, np.float64)[:, 1]
    out = []
    for i in rows:
        obs = np.asarray(raw.hand_observed[i], bool)
        scales, ys = [], []
        for side in range(2):
            if obs[side]:
                xy = np.asarray(raw.hand_xy[i, side], np.float64)
                scales.append(np.linalg.norm(xy[MCP] - xy[WRIST]) / size[i])
                ys.append(xy[WRIST, 1] / height[i])
        out.append(
            [
                float(obs.any()),
                float(obs.all()),
                float(raw.body_available[i]),
                float(np.mean(scales)) if scales else np.nan,
                float(np.mean(ys)) if ys else np.nan,
            ]
        )
    return np.asarray(out, np.float64).reshape(-1, 5)


def summarize(d: np.ndarray, dt: np.ndarray) -> dict[str, float]:
    return {
        "rows": int(len(d)),
        "any_hand": float(np.nanmean(d[:, 0])),
        "both_hands": float(np.nanmean(d[:, 1])),
        "body_available": float(np.nanmean(d[:, 2])),
        "hand_scale_median": float(np.nanmedian(d[:, 3])) if np.any(~np.isnan(d[:, 3])) else None,
        "hand_wrist_y_median": float(np.nanmedian(d[:, 4])) if np.any(~np.isnan(d[:, 4])) else None,
        "cadence_ms_median": float(np.median(dt)) if len(dt) else None,
    }


def zoom(raw: Any, factor: float) -> Any:
    """Close-framing counterfactual: scale every coordinate about the image centre."""
    centre = np.asarray(raw.source_size, np.float32)[:, None, None, :] * 0.5
    hand = (raw.hand_xy - centre) * factor + centre
    bc = np.asarray(raw.source_size, np.float32)[:, None, :] * 0.5
    body = (raw.body_xy - bc) * factor + bc
    roi = raw.hand_roi_center_side.copy()
    rc = np.asarray(raw.source_size, np.float32)[:, None, :] * 0.5
    roi[..., :2] = (roi[..., :2] - rc) * factor + rc
    roi[..., 2] = roi[..., 2] * factor
    return dataclasses.replace(
        raw,
        hand_xy=hand.astype(raw.hand_xy.dtype),
        body_xy=body.astype(raw.body_xy.dtype),
        hand_roi_center_side=roi,
    )


def no_body(raw: Any) -> Any:
    return dataclasses.replace(
        raw,
        body_xy=np.zeros_like(raw.body_xy),
        body_support=np.zeros_like(raw.body_support),
        body_valid=np.zeros_like(raw.body_valid),
        body_available=np.zeros_like(raw.body_available),
    )


def logistic_cv(x: np.ndarray, y: np.ndarray, groups: np.ndarray) -> float:
    """Stream-grouped 2-fold logistic regression AUC on descriptor means per chunk."""
    x = np.nan_to_num(x, nan=0.0)
    scores = np.zeros(len(y))
    fold = (groups % 2).astype(bool)
    for test in (fold, ~fold):
        tr = ~test
        mu, sd = x[tr].mean(0), x[tr].std(0) + 1e-9
        z = (x - mu) / sd
        w, b = np.zeros(z.shape[1]), 0.0
        for _ in range(3000):
            p = 1 / (1 + np.exp(-(z[tr] @ w + b)))
            g = p - y[tr]
            w -= 0.3 * (z[tr].T @ g / tr.sum() + 1e-3 * w)
            b -= 0.3 * float(g.mean())
        scores[test] = z[test] @ w + b
    return auc(list(scores[y == 1]), list(scores[y == 0]))


def cal_units(streams: list[dict], probs: list[np.ndarray]) -> dict[str, list[float]]:
    units: dict[str, list[float]] = {"sign": [], "P1": [], "N0": []}
    for s, p in zip(streams, probs, strict=True):
        a = p[:, 1]
        for o in sorted(set(s["ordinals"].tolist()) - {-1}):
            rows = np.flatnonzero((s["ordinals"] == o) & (s["labels"] == 1))
            if len(rows):
                units["sign"].append(float(a[rows].max()))
        for fam in ("P1", "N0"):
            rows = np.flatnonzero(
                (s["kinds"] == s2_r3_train.NEGATIVE_KIND)
                & (s["labels"] == 0)
                & (s["negative_family"] == fam)
            )
            units[fam] += [float(a[c].max()) for c in chunks(rows)]
    return units


def main() -> None:
    cal = s2_r3_train.build_dataset(E, suite.read_json(s2_r3_train.CONFIG_PATH))["cal_streams"]
    sessions = {
        k: v for k, v in er.phone_sessions(E).items() if v["kind"] != "SHADOW_PROTOCOL_ONLY"
    }
    out: dict[str, Any] = {
        "descriptors": {},
        "separability": {},
        "source_cue_auc": {},
        "counterfactual": {},
    }

    # 1. descriptors
    pops: dict[str, list[np.ndarray]] = {
        k: [] for k in ("cal_sign", "cal_P1", "cal_N0", "phone_genuine", "phone_nonsign")
    }
    dts: dict[str, list[float]] = {k: [] for k in pops}
    chunk_x, chunk_y, chunk_g = [], [], []
    for k, s in enumerate(cal):
        raw = s["raw"]
        t = np.asarray(raw.timestamp_ms, np.float64)
        dt = np.diff(t, prepend=t[0])
        sign_rows = np.flatnonzero(s["labels"] == 1)
        pops["cal_sign"].append(descriptors(raw, sign_rows))
        dts["cal_sign"] += list(dt[sign_rows[1:]]) if len(sign_rows) > 1 else []
        for fam in ("P1", "N0"):
            rows = np.flatnonzero(
                (s["kinds"] == s2_r3_train.NEGATIVE_KIND) & (s["negative_family"] == fam)
            )
            pops[f"cal_{fam}"].append(descriptors(raw, rows))
            dts[f"cal_{fam}"] += list(dt[rows[1:]]) if len(rows) > 1 else []
        for c in chunks(sign_rows):
            chunk_x.append(np.nanmean(descriptors(raw, c), axis=0))
            chunk_y.append(1)
            chunk_g.append(k)
        p1 = np.flatnonzero(
            (s["kinds"] == s2_r3_train.NEGATIVE_KIND) & (s["negative_family"] == "P1")
        )
        for c in chunks(p1):
            chunk_x.append(np.nanmean(descriptors(raw, c), axis=0))
            chunk_y.append(0)
            chunk_g.append(k)
    for s in sessions.values():
        raw = s["capture"].raw
        t = np.asarray(raw.timestamp_ms, np.float64)
        dt = np.diff(t, prepend=t[0])
        for sign in s["positives"]:
            rows = np.arange(sign["first"], sign["last"] + 1)
            pops["phone_genuine"].append(descriptors(raw, rows))
            dts["phone_genuine"] += list(dt[rows[1:]])
        for n in s["negatives"]:
            rows = np.arange(n["first"], n["last"] + 1)
            pops["phone_nonsign"].append(descriptors(raw, rows))
            dts["phone_nonsign"] += list(dt[rows[1:]])
    for k, v in pops.items():
        out["descriptors"][k] = summarize(np.concatenate(v), np.asarray(dts[k]))
    x, y, g = np.asarray(chunk_x), np.asarray(chunk_y), np.asarray(chunk_g)
    out["source_cue_auc"]["cal_sign_vs_P1_descriptors_only"] = logistic_cv(x, y, g)
    out["source_cue_auc"]["cal_sign_vs_P1_body_available_only"] = logistic_cv(x[:, [2]], y, g)
    out["source_cue_auc"]["cal_sign_vs_P1_hand_scale_only"] = logistic_cv(x[:, [3]], y, g)

    # 2. separability, P1 and N0 separately; phone
    for name in ("S2_R2", "ARM_A_E10"):
        pkg = er.load_s2(E, name)
        units = cal_units(cal, [pkg.probabilities(s["features"]) for s in cal])
        pg, pn = [], []
        for s in sessions.values():
            a = pkg.probabilities(s["features"])[:, 1]
            pg += [float(a[x["first"] : x["last"] + 1].max()) for x in s["positives"]]
            for n in s["negatives"]:
                pn += [float(a[c].max()) for c in chunks(np.arange(n["first"], n["last"] + 1))]
        out["separability"][name] = {
            "cal_sign_vs_P1": auc(units["sign"], units["P1"]),
            "cal_sign_vs_N0": auc(units["sign"], units["N0"]),
            "cal_sign_vs_pooled": auc(units["sign"], units["P1"] + units["N0"]),
            "phone_genuine_vs_nonsign": auc(pg, pn),
            "n": {
                "cal_sign": len(units["sign"]),
                "P1": len(units["P1"]),
                "N0": len(units["N0"]),
                "phone_genuine": len(pg),
                "phone_nonsign": len(pn),
            },
            "P1_fired_at_0.5": float(np.mean(np.asarray(units["P1"]) >= 0.5)),
            "phone_nonsign_fired_at_0.5": float(np.mean(np.asarray(pn) >= 0.5)),
        }
        print(name, json.dumps(out["separability"][name]), flush=True)

    # 4. counterfactuals (Arm A e10)
    pkg = er.load_s2(E, "ARM_A_E10")
    for label, fn in (
        ("no_body", no_body),
        ("zoom_1.5", lambda r: zoom(r, 1.5)),
        ("zoom_1.5_no_body", lambda r: no_body(zoom(r, 1.5))),
    ):
        probs = []
        for s in cal:
            raw = fn(s["raw"])
            f = suite.features_for_raw(raw, "v1")[: len(s["labels"])]
            probs.append(pkg.probabilities(f))
        units = cal_units(cal, probs)
        out["counterfactual"][label] = {
            "cal_sign_vs_P1": auc(units["sign"], units["P1"]),
            "cal_sign_detected_at_0.5": float(np.mean(np.asarray(units["sign"]) >= 0.5)),
            "P1_fired_at_0.5": float(np.mean(np.asarray(units["P1"]) >= 0.5)),
        }
        print(label, json.dumps(out["counterfactual"][label]), flush=True)
    print(json.dumps(out["descriptors"], indent=1))
    print(json.dumps(out["source_cue_auc"]))
    Path(__file__).with_name("domain_shift.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
