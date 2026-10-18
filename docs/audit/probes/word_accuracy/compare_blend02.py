"""WORD_BLEND_02 (reviewed Sem-Lex package 02 added) against WORD_BLEND_01 on identical windows.

NAIVE2(s) = WORD_BLEND_01 member recipe (naive Sem-Lex-ENRICH, WORD v2 augmentation, seed s) with
the 40 classes accepted in human review package 02 added (ENRICH-role signers only, at most two
clips per signer and class, fixed before training). BLEND_02 applies the pre-registered rule
unchanged: 0.5 frozen + 0.5 mean(NAIVE2 101/202/303); no weight or seed is selected.

Class groups: NEW40 (review package 02), OLD64 (Sem-Lex classes already in WORD_BLEND_01), REST.
Populations: DEV (selection-exposed), Sem-Lex EVAL of package 01 (OLD64) and of package 02 (NEW40;
13 EVAL-role signers never trained on by any model), PHONE (development-exposed). The clip is the
unit (runtime-window phases averaged); paired tests use the per-clip majority; changes carry a
signer-cluster bootstrap interval. End-to-end word rate = correct own-event words / all stitched
signs (Arm A e10 + CONFIRM_BOUNDARY_70 windows). Writes compare_blend02.json next to this file.
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
SEEDS = (101, 202, 303)
P266 = [f"ctx_c375_p{k}" for k in range(4)]
P200 = ["ctx_c200_p0", "ctx_c200_p1"]
POPS = ("DEV", "SEMLEX", "SEMLEX2", "PHONE")


def mcnemar(a: np.ndarray, b: np.ndarray) -> dict[str, Any]:
    n01, n10 = int(np.sum(~a & b)), int(np.sum(a & ~b))
    n = n01 + n10
    p = min(1.0, 2 * sum(comb(n, k) for k in range(min(n01, n10) + 1)) / 2**n) if n else 1.0
    return {"fixed": n01, "broken": n10, "p": round(p, 6)}


def cluster_ci(delta: np.ndarray, groups: np.ndarray, reps: int = 4000) -> list[float]:
    keys = sorted(set(groups))
    by = [delta[groups == g] for g in keys]
    rng = np.random.default_rng(9207)
    stats = [
        float(np.concatenate([by[i] for i in rng.integers(len(by), size=len(by))]).mean())
        for _ in range(reps)
    ]
    return [round(float(np.percentile(stats, q)), 4) for q in (2.5, 97.5)]


def main() -> None:
    names = wve.glosses(E)
    index = {g: i for i, g in enumerate(names)}
    meta = {p: wve.load_bank(E / wve.OUT / f"bank_{p}.npz")[1] for p in POPS}
    new40 = {x["gloss"] for x in meta["SEMLEX2"]["span_dense"]}
    old64 = {x["gloss"] for x in meta["SEMLEX"]["span_dense"]}

    def group(g: str) -> str:
        return "NEW40" if g in new40 else "OLD64" if g in old64 else "REST"

    def load(name: str) -> dict:
        return {p: dict(np.load(E / wve.OUT / "scores" / name / f"{p}.npz")) for p in POPS}

    probs = {"frozen": load("frozen"), "BLEND_01": load("BLEND_01")}
    for s in SEEDS:
        probs[f"NAIVE{s}"] = load(f"NAIVE_S{s}")
        probs[f"NAIVE2_{s}"] = load(f"NAIVE2_S{s}")
    probs["BLEND_02"] = {
        p: {
            v: 0.5 * probs["frozen"][p][v] + sum(probs[f"NAIVE2_{s}"][p][v] for s in SEEDS) / 6
            for v in probs["frozen"][p]
        }
        for p in POPS
    }
    metrics = {
        "dev_runtime_266": ("DEV", P266, None),
        "dev_runtime_200": ("DEV", P200, None),
        "dev_dense": ("DEV", ["span_dense"], None),
        "semlex01_eval_runtime_266": ("SEMLEX", P266, "EVAL"),
        "semlex02_eval_runtime_266": ("SEMLEX2", P266, "EVAL"),
        "semlex02_eval_runtime_200": ("SEMLEX2", P200, "EVAL"),
    }

    def per_clip(model: str, population: str, views: list[str], role: str | None) -> tuple:
        score: dict[str, list[float]] = {}
        gloss: dict[str, str] = {}
        signer: dict[str, str] = {}
        for v in views:
            for x, p in zip(meta[population][v], probs[model][population][v], strict=True):
                if role and x.get("role") != role:
                    continue
                score.setdefault(x["sample_id"], []).append(
                    float(int(np.argmax(p)) == index[x["gloss"]])
                )
                gloss[x["sample_id"]], signer[x["sample_id"]] = x["gloss"], x["signer"]
        return {k: float(np.mean(v)) for k, v in score.items()}, gloss, signer

    out: dict[str, Any] = {"new40": sorted(new40), "models": {}, "paired": {}}
    for model in probs:
        row: dict[str, Any] = {}
        for metric, (population, views, role) in metrics.items():
            score, gloss, _ = per_clip(model, population, views, role)
            vals = np.asarray(list(score.values()))
            row[metric] = round(float(vals.mean()), 4)
            if population == "DEV":
                g = np.asarray([group(gloss[k]) for k in score])
                for name in ("NEW40", "OLD64", "REST"):
                    row[f"{metric}:{name}"] = round(float(vals[g == name].mean()), 4)
        for mode in ("natural", "continuous"):
            m = meta["DEV"][f"rt_{mode}"]
            pv = probs[model]["DEV"][f"rt_{mode}"]
            hits = sum(int(np.argmax(q)) == index[x["gloss"]] for x, q in zip(m, pv, strict=True))
            row[f"e2e_{mode}_word_rate"] = round(
                hits / (len(m) + len(meta["DEV"][f"rt_{mode}_missed"])), 4
            )
        for v in ("phone_oracle", "phone_runtime"):
            m = meta["PHONE"][v]
            pv = probs[model]["PHONE"][v]
            hits = sum(int(np.argmax(q)) == index[x["gloss"]] for x, q in zip(m, pv, strict=True))
            row[v] = f"{hits}/{len(m)}"
        out["models"][model] = row
        print(model.ljust(10), " ".join(f"{k}={v}" for k, v in row.items()), flush=True)
    pairs = [("BLEND_01", "BLEND_02"), ("frozen", "BLEND_02")] + [
        (f"NAIVE{s}", f"NAIVE2_{s}") for s in SEEDS
    ]
    for a, b in pairs:
        res = {}
        for metric, (population, views, role) in metrics.items():
            sa, gloss, signer = per_clip(a, population, views, role)
            sb, _, _ = per_clip(b, population, views, role)
            keys = sorted(sa)
            va, vb = np.asarray([sa[k] for k in keys]), np.asarray([sb[k] for k in keys])
            groups = np.asarray([signer[k] for k in keys])
            res[metric] = {
                "delta": round(float((vb - va).mean()), 4),
                "signer_ci95": cluster_ci(vb - va, groups),
                **mcnemar(va >= 0.5, vb >= 0.5),
            }
            if population == "DEV":
                g = np.asarray([group(gloss[k]) for k in keys])
                for name in ("NEW40", "OLD64", "REST"):
                    sel = g == name
                    res[f"{metric}:{name}"] = {
                        "delta": round(float((vb[sel] - va[sel]).mean()), 4),
                        "signer_ci95": cluster_ci(vb[sel] - va[sel], groups[sel]),
                        **mcnemar(va[sel] >= 0.5, vb[sel] >= 0.5),
                    }
        out["paired"][f"{a}->{b}"] = res
        print(
            f"{a}->{b}",
            {
                k: (v["delta"], v["signer_ci95"], v["fixed"], v["broken"], v["p"])
                for k, v in res.items()
            },
            flush=True,
        )
    Path(__file__).with_name("compare_blend02.json").write_text(
        json.dumps(out, indent=1) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
