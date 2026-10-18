"""Sparse-only training vs its paired dense+sparse members, alone and inside the blend rule.

SPARSE(s) = naive Sem-Lex-ENRICH recipe with no dense view in training or selection;
NAIVE(s) = the same recipe with the dense view (the WORD_BLEND_01 members). Same seeds, same data.
BLEND_SPARSE applies the pre-registered WORD_BLEND_01 rule unchanged (0.5 frozen + 0.5 mean of
the three seeds), so no new weight or seed is selected. Clip is the unit: the four runtime-window
phases are averaged per clip; paired tests use the per-clip majority, and the change is reported
with a signer-cluster bootstrap interval (DEV: 5 signers; Sem-Lex EVAL: 13 signers).
End-to-end word rate = correct own-event words / all signs of the held-out stitched streams.
Writes compare_sparse_only.json next to this file.
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
PHASES = [f"ctx_c375_p{k}" for k in range(4)]
PHASES_200 = ["ctx_c200_p0", "ctx_c200_p1"]


def mcnemar(a: np.ndarray, b: np.ndarray) -> dict[str, Any]:
    n01, n10 = int(np.sum(~a & b)), int(np.sum(a & ~b))
    n = n01 + n10
    p = min(1.0, 2 * sum(comb(n, k) for k in range(min(n01, n10) + 1)) / 2**n) if n else 1.0
    return {"fixed": n01, "broken": n10, "p": round(p, 6)}


def cluster_ci(delta: np.ndarray, groups: np.ndarray, reps: int = 4000) -> list[float]:
    keys = sorted(set(groups))
    by = [delta[groups == g] for g in keys]
    rng = np.random.default_rng(9107)
    stats = [
        float(np.concatenate([by[i] for i in rng.integers(len(by), size=len(by))]).mean())
        for _ in range(reps)
    ]
    return [round(float(np.percentile(stats, q)), 4) for q in (2.5, 97.5)]


def main() -> None:
    names = wve.glosses(E)
    index = {g: i for i, g in enumerate(names)}
    meta = {p: wve.load_bank(E / wve.OUT / f"bank_{p}.npz")[1] for p in ("DEV", "SEMLEX", "PHONE")}
    covered = {x["gloss"] for x in meta["SEMLEX"]["span_dense"] if x["role"] == "ENRICH"}

    def load(name: str) -> dict:
        return {p: dict(np.load(E / wve.OUT / "scores" / name / f"{p}.npz")) for p in meta}

    probs = {"frozen": load("frozen"), "BLEND_01": load("BLEND_01")}
    for s in SEEDS:
        probs[f"NAIVE{s}"] = load(f"NAIVE_S{s}")
        probs[f"SPARSE{s}"] = load(f"SPARSE_S{s}")
    probs["BLEND_SPARSE"] = {
        p: {
            v: 0.5 * probs["frozen"][p][v] + sum(probs[f"SPARSE{s}"][p][v] for s in SEEDS) / 6
            for v in probs["frozen"][p]
        }
        for p in meta
    }
    probs["SPARSE_MEAN"] = {
        p: {v: sum(probs[f"SPARSE{s}"][p][v] for s in SEEDS) / 3 for v in probs["frozen"][p]}
        for p in meta
    }

    def per_clip(
        model: str, population: str, views: list[str], role: str | None
    ) -> tuple[dict, dict, dict]:
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

    metrics = {
        "dev_runtime_266": ("DEV", PHASES, None),
        "dev_runtime_200": ("DEV", PHASES_200, None),
        "dev_dense": ("DEV", ["span_dense"], None),
        "semlex_eval_runtime_266": ("SEMLEX", PHASES, "EVAL"),
        "semlex_eval_runtime_200": ("SEMLEX", PHASES_200, "EVAL"),
    }
    out: dict[str, Any] = {"models": {}, "paired": {}}

    def e2e(model: str) -> dict[str, float]:
        res = {}
        for mode in ("natural", "continuous"):
            m = meta["DEV"][f"rt_{mode}"]
            p = probs[model]["DEV"][f"rt_{mode}"]
            correct = sum(int(np.argmax(q)) == index[x["gloss"]] for x, q in zip(m, p, strict=True))
            total = len(m) + len(meta["DEV"][f"rt_{mode}_missed"])  # every stitched sign
            res[f"e2e_{mode}_word_rate"] = round(correct / total, 4)
            res[f"own_event_{mode}_top1"] = round(correct / len(m), 4)
        return res

    for model in probs:
        row: dict[str, Any] = {}
        for metric, (population, views, role) in metrics.items():
            score, gloss, _ = per_clip(model, population, views, role)
            vals = np.asarray(list(score.values()))
            cov = np.asarray([gloss[k] in covered for k in score])
            row[metric] = round(float(vals.mean()), 4)
            if population == "DEV":
                row[f"{metric}:uncovered"] = round(float(vals[~cov].mean()), 4)
                row[f"{metric}:covered"] = round(float(vals[cov].mean()), 4)
        row.update(e2e(model))
        for v in ("phone_oracle", "phone_runtime"):
            m = meta["PHONE"][v]
            pv = probs[model]["PHONE"][v]
            hits = sum(int(np.argmax(q)) == index[x["gloss"]] for x, q in zip(m, pv, strict=True))
            row[v] = f"{hits}/{len(m)}"
        out["models"][model] = row
        print(model.ljust(13), " ".join(f"{k}={v}" for k, v in row.items()), flush=True)
    pairs = [(f"NAIVE{s}", f"SPARSE{s}") for s in SEEDS] + [
        ("BLEND_01", "BLEND_SPARSE"),
        ("frozen", "BLEND_SPARSE"),
        ("BLEND_01", "SPARSE_MEAN"),
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
        out["paired"][f"{a}->{b}"] = res
        print(
            f"{a}->{b}",
            {
                k: (v["delta"], v["signer_ci95"], v["fixed"], v["broken"], v["p"])
                for k, v in res.items()
            },
            flush=True,
        )
    Path(__file__).with_name("compare_sparse_only.json").write_text(
        json.dumps(out, indent=1) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
