"""Paired WORD candidate comparison on the identical word_vocabulary_eval windows.

For each seed s: exposure-controlled Sem-Lex enrichment EC(s) against its same-recipe control
C(s) (identical WORD v2 augmentation, no Sem-Lex) and against the frozen recognizer, plus the
naive (exposure-uncontrolled) ENRICH-signer enrichment N(s), the frozen+EC averages and the
pre-registered BLEND = 0.5 frozen + 0.5 mean(N101, N202, N303).
Metrics: DEV pooled runtime-bounded windows (3.75 fps, 4 phases), DEV dense, DEV 200 ms, DEV
runtime event windows (Arm A e10 + CONFIRM_BOUNDARY_70; natural / continuous), DEV hand loss,
Sem-Lex EVAL signers (never trained on by any model), PHONE (development-exposed); DEV and
Sem-Lex EVAL split into the 64 Sem-Lex-covered and the uncovered classes. Paired exact McNemar
per metric (clip-level, pooled phases). Writes compare_candidates.json next to this file.
"""

from __future__ import annotations

import json
import sys
from math import comb
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics import word_vocabulary_eval as wve  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
RU = "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
MODELS = {
    "frozen": None,
    "C101": f"{RU}/word_track_robust_aug_02/best.keras",
    "C202": f"{RU}/word_ec_semlex_01/control_s202/best.keras",
    "C303": f"{RU}/word_ec_semlex_01/control_s303/best.keras",
    "EC101": f"{RU}/word_ec_semlex_01/ec_s101/best.keras",
    "EC202": f"{RU}/word_ec_semlex_01/ec_s202/best.keras",
    "EC303": f"{RU}/word_ec_semlex_01/ec_s303/best.keras",
    "NAIVE101": f"{RU}/word_ec_semlex_01/naive_s101/best.keras",
    "NAIVE202": f"{RU}/word_ec_semlex_01/naive_s202/best.keras",
    "NAIVE303": f"{RU}/word_ec_semlex_01/naive_s303/best.keras",
}
SCORE_NAME = {
    "frozen": "frozen",
    "C101": "word_track_robust_aug_02",
    **{f"C{s}": f"CONTROL_S{s}" for s in (202, 303)},
    **{f"EC{s}": f"EC_S{s}" for s in (101, 202, 303)},
    **{f"NAIVE{s}": f"NAIVE_S{s}" for s in (101, 202, 303)},
}
METRICS = {
    "dev_realistic": ("DEV", [f"ctx_c375_p{k}" for k in range(4)], None),
    "dev_dense": ("DEV", ["span_dense"], None),
    "dev_200ms": ("DEV", ["ctx_c200_p0", "ctx_c200_p1"], None),
    "dev_rt_natural": ("DEV", ["rt_natural"], None),
    "dev_rt_continuous": ("DEV", ["rt_continuous"], None),
    "dev_hand50": ("DEV", ["rob_hand50", "rob_motion50"], None),
    "semlex_eval_realistic": ("SEMLEX", [f"ctx_c375_p{k}" for k in range(4)], "EVAL"),
    "semlex_eval_dense": ("SEMLEX", ["span_dense"], "EVAL"),
    "phone_oracle": ("PHONE", ["phone_oracle"], None),
    "phone_runtime": ("PHONE", ["phone_runtime"], None),
}


def mcnemar(a: np.ndarray, b: np.ndarray) -> dict[str, Any]:
    n01, n10 = int(np.sum(~a & b)), int(np.sum(a & ~b))
    n = n01 + n10
    p = min(1.0, 2 * sum(comb(n, k) for k in range(min(n01, n10) + 1)) / 2**n) if n else 1.0
    return {"fixed": n01, "broken": n10, "p": round(p, 6)}


def main() -> None:
    names = wve.glosses(E)
    index = {g: i for i, g in enumerate(names)}
    metas = {p: wve.load_bank(E / wve.OUT / f"bank_{p}.npz")[1] for p in ("DEV", "SEMLEX", "PHONE")}
    covered = {m["gloss"] for m in metas["SEMLEX"]["span_dense"] if m["role"] == "ENRICH"}
    probs = {
        k: {
            p: dict(np.load(E / wve.OUT / "scores" / SCORE_NAME.get(k, k) / f"{p}.npz"))
            for p in metas
        }
        for k in MODELS
    }
    # pre-registered candidate (model/perception_vnext/word_blend.py CANDIDATE_01)
    probs["BLEND"] = {
        p: {
            v: 0.5 * probs["frozen"][p][v]
            + sum(probs[f"NAIVE{s}"][p][v] for s in (101, 202, 303)) / 6
            for v in probs["frozen"][p]
        }
        for p in metas
    }
    for seed in (101, 202, 303):
        probs[f"F+EC{seed}"] = {
            p: {
                v: (probs["frozen"][p][v] + probs[f"EC{seed}"][p][v]) / 2
                for v in probs["frozen"][p]
            }
            for p in metas
        }

    def hits(model: str, metric: str) -> tuple[np.ndarray, np.ndarray]:
        population, views, role = METRICS[metric]
        ok, cov = [], []
        for v in views:
            m = metas[population][v]
            keep = np.asarray([role is None or x.get("role") == role for x in m])
            y = np.asarray([index[x["gloss"]] for x in m])
            ok.append((probs[model][population][v].argmax(1) == y)[keep])
            cov.append(np.asarray([x["gloss"] in covered for x in m])[keep])
        return np.concatenate(ok), np.concatenate(cov)

    out: dict[str, Any] = {"covered_classes": len(covered), "models": {}, "paired": {}}
    for model in probs:
        row = {}
        for metric in METRICS:
            ok, cov = hits(model, metric)
            row[metric] = round(float(ok.mean()), 4)
            if metric.startswith(("dev_realistic", "dev_rt", "semlex_eval_realistic")):
                row[f"{metric}:covered"] = round(float(ok[cov].mean()), 4) if cov.any() else None
                row[f"{metric}:uncovered"] = (
                    round(float(ok[~cov].mean()), 4) if (~cov).any() else None
                )
            if metric.startswith("phone"):
                row[f"{metric}:count"] = f"{int(ok.sum())}/{len(ok)}"
        out["models"][model] = row
        print(model.ljust(10), " ".join(f"{k}={v}" for k, v in row.items()), flush=True)
    pairs = (
        [(f"C{s}", f"EC{s}") for s in (101, 202, 303)]
        + [("frozen", f"EC{s}") for s in (101, 202, 303)]
        + [("frozen", f"F+EC{s}") for s in (101, 202, 303)]
        + [(f"C{s}", f"NAIVE{s}") for s in (101, 202, 303)]
        + [("frozen", f"NAIVE{s}") for s in (101, 202, 303)]
        + [("frozen", "BLEND"), ("NAIVE101", "EC101"), ("C101", "BLEND")]
    )
    for a, b in pairs:
        res = {}
        for metric in METRICS:
            ha, cov = hits(a, metric)
            hb, _ = hits(b, metric)
            res[metric] = mcnemar(ha, hb)
            if metric in ("dev_realistic", "semlex_eval_realistic"):
                res[f"{metric}:uncovered"] = mcnemar(ha[~cov], hb[~cov])
                res[f"{metric}:covered"] = mcnemar(ha[cov], hb[cov])
        out["paired"][f"{a}->{b}"] = res
    Path(__file__).with_name("compare_candidates.json").write_text(
        json.dumps(out, indent=1) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
