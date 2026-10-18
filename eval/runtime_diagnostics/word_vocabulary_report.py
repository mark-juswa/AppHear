"""Vocabulary-wide WORD report from word_vocabulary_eval banks and scores (research only).

For every class: evaluation coverage (held-out clips and independent signers), reliability tier,
TRAIN coverage, recall per condition, Top-5 presence and the dominant confusion. For every model:
aggregate metrics per view and population, paired exact McNemar against the reference model,
the confusion pairs, the error decomposition (discrimination / cadence / window / perception)
and the robustness deltas. Writes ``report/<name>.json`` and ``report/<name>_classes.csv``.

Reliability tiers use only data independent of every compared model: DEV (5 signers) plus the
Sem-Lex EVAL-role signers. RELIABLE >= 8 clips from >= 5 signers; LIMITED >= 3 clips from >= 3
signers; otherwise UNRELIABLE. DEV is selection-exposed for every recognizer (checkpoint
selection on DEV val_loss); Sem-Lex EVAL is untouched by all of them; PHONE is development-exposed.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from math import comb
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics import word_vocabulary_eval as wve  # noqa: E402

REALISTIC = [f"ctx_c375_p{k}" for k in range(4)]
SEMLEX_REALISTIC = ["ctx_c375_p0", "ctx_c375_p1"]


def mcnemar(a: np.ndarray, b: np.ndarray) -> dict[str, Any]:
    n01, n10 = int(np.sum(~a & b)), int(np.sum(a & ~b))
    n = n01 + n10
    p = min(1.0, 2 * sum(comb(n, k) for k in range(min(n01, n10) + 1)) / 2**n) if n else 1.0
    return {"fixed": n01, "broken": n10, "p": p}


class Scores:
    def __init__(self, root: Path, name: str, population: str, names: list[str]) -> None:
        self.prob = dict(np.load(root / wve.OUT / "scores" / name / f"{population}.npz"))
        self.names = names

    def view(self, view: str) -> np.ndarray:
        return self.prob[view]


def ranks(prob: np.ndarray, y: np.ndarray) -> np.ndarray:
    order = np.argsort(-prob, axis=1, kind="stable")
    return np.argmax(order == y[:, None], axis=1) + 1


def labels(meta: list[dict[str, Any]], index: dict[str, int]) -> np.ndarray:
    return np.asarray([index[m["gloss"]] for m in meta], np.int64)


def coverage(
    root: Path, metas: dict[str, dict[str, list[dict[str, Any]]]]
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = defaultdict(lambda: defaultdict(set))
    train = [json.loads(line) for line in (root / wve.INDEX).open(encoding="utf-8")]
    for r in train:
        if r["split"] == "train":
            c = out[r["canonical_gloss"]]
            c["train_clips"].add(r["sample_id"])
            c["train_signers"].add(r["signer_id"])
            c["train_sources"].add(r["source_id"])
    for m in metas["DEV"]["span_dense"]:
        out[m["gloss"]]["dev_clips"].add(m["sample_id"])
        out[m["gloss"]]["dev_signers"].add(m["signer"])
    for m in metas["SEMLEX"]["span_dense"]:
        key = "semlex_eval" if m["role"] == "EVAL" else "semlex_enrich"
        out[m["gloss"]][f"{key}_clips"].add(m["sample_id"])
        out[m["gloss"]][f"{key}_signers"].add(m["signer"])
    for m in metas["PHONE"]["phone_oracle"]:
        out[m["gloss"]]["phone_signs"].add(m["sample_id"])
    table = {}
    for gloss, c in out.items():
        row = {k: len(v) for k, v in c.items() if k != "train_sources"}
        row["train_sources"] = sorted(c["train_sources"])
        clips = row.get("dev_clips", 0) + row.get("semlex_eval_clips", 0)
        signers = row.get("dev_signers", 0) + row.get("semlex_eval_signers", 0)
        row["independent_clips"], row["independent_signers"] = clips, signers
        row["tier"] = (
            "RELIABLE"
            if clips >= 8 and signers >= 5
            else "LIMITED"
            if clips >= 3 and signers >= 3
            else "UNRELIABLE"
        )
        table[gloss] = row
    return table


def view_metrics(prob: np.ndarray, y: np.ndarray, meta: list[dict[str, Any]]) -> dict[str, Any]:
    r = ranks(prob, y)
    per_class = defaultdict(list)
    for yi, ri in zip(y, r, strict=True):
        per_class[int(yi)].append(ri == 1)
    recall = [float(np.mean(v)) for v in per_class.values()]
    by_signer = defaultdict(list)
    for m, ri in zip(meta, r, strict=True):
        by_signer[m["signer"]].append(ri == 1)
    return {
        "n": int(len(y)),
        "classes": len(per_class),
        "top1": float(np.mean(r == 1)),
        "top5": float(np.mean(r <= 5)),
        "macro_recall": float(np.mean(recall)) if recall else None,
        "zero_recall_classes": int(sum(x == 0 for x in recall)),
        "per_signer_top1": {k: round(float(np.mean(v)), 4) for k, v in sorted(by_signer.items())},
    }


def model_report(
    root: Path,
    name: str,
    ref: str | None,
    banks: dict[str, Any],
    names: list[str],
    cover: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    index = {g: i for i, g in enumerate(names)}
    rep: dict[str, Any] = {"views": {}, "paired_vs_reference": {}}
    probs = {p: Scores(root, name, p, names) for p in banks}
    refs = {p: Scores(root, ref, p, names) for p in banks} if ref else None
    for population, (_, meta) in banks.items():
        for view in probs[population].prob:
            m = meta[view]
            y = labels(m, index)
            subsets = {"ALL": np.ones(len(m), bool)}
            if population == "SEMLEX":
                subsets = {
                    "EVAL": np.asarray([x["role"] == "EVAL" for x in m]),
                    "ENRICH": np.asarray([x["role"] == "ENRICH" for x in m]),
                }
            for label, keep in subsets.items():
                key = f"{population}:{label}:{view}"
                p = probs[population].view(view)[keep]
                rep["views"][key] = view_metrics(
                    p, y[keep], [x for x, k in zip(m, keep, strict=True) if k]
                )
                if refs:
                    a = ranks(refs[population].view(view)[keep], y[keep]) == 1
                    b = ranks(p, y[keep]) == 1
                    rep["paired_vs_reference"][key] = mcnemar(a, b)
    # pooled realistic view: DEV ctx_c375 over four phases, SEMLEX EVAL over two
    pooled: dict[str, Any] = {}
    for population, views, keep_role in (
        ("DEV", REALISTIC, None),
        ("SEMLEX", SEMLEX_REALISTIC, "EVAL"),
    ):
        meta = banks[population][1]
        hits = []
        for v in views:
            m = meta[v]
            keep = np.asarray([keep_role is None or x["role"] == keep_role for x in m])
            y = labels(m, index)[keep]
            hits.append(ranks(probs[population].view(v)[keep], y))
        r = np.concatenate(hits)
        pooled[population] = {
            "top1": float(np.mean(r == 1)),
            "top5": float(np.mean(r <= 5)),
            "rows": int(len(r)),
        }
    rep["pooled_realistic"] = pooled
    rep["classes"] = class_table(probs, banks, names, index, cover)
    rep["confusions"] = confusions(probs, banks, names, index)
    rep["decomposition"] = decomposition(probs, banks, index)
    rep["robustness"] = {
        k: rep["views"][f"DEV:ALL:{k}"]["top1"] - rep["views"]["DEV:ALL:ctx_c375_p0"]["top1"]
        for k in (f"rob_{x}" for x in list(wve.JITTER) + list(wve.HAND_DROP))
        if f"DEV:ALL:{k}" in rep["views"]
    }
    rep["runtime"] = runtime_summary(probs, banks, index)
    return rep


def class_table(
    probs: dict[str, Scores],
    banks: dict[str, Any],
    names: list[str],
    index: dict[str, int],
    cover: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    acc: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    wrong_to: dict[str, Counter[str]] = defaultdict(Counter)

    def collect(population: str, views: list[str], key: str, role: str | None = None) -> None:
        meta = banks[population][1]
        for v in views:
            if v not in probs[population].prob:
                continue
            m = meta[v]
            p = probs[population].view(v)
            y = labels(m, index)
            r = ranks(p, y)
            for i, x in enumerate(m):
                if role and x.get("role") != role:
                    continue
                acc[x["gloss"]][key].append(float(r[i] == 1))
                acc[x["gloss"]][f"{key}_top5"].append(float(r[i] <= 5))
                if key in ("dev_realistic", "semlex_realistic") and r[i] != 1:
                    wrong_to[x["gloss"]][names[int(np.argmax(p[i]))]] += 1

    collect("DEV", ["span_dense"], "dev_dense")
    collect("DEV", REALISTIC, "dev_realistic")
    collect("DEV", ["rt_natural"], "dev_runtime_natural")
    collect("DEV", ["rt_continuous"], "dev_runtime_continuous")
    collect("SEMLEX", SEMLEX_REALISTIC, "semlex_realistic", "EVAL")
    collect("SEMLEX", ["span_dense"], "semlex_dense", "EVAL")
    collect("TRAIN", ["span_dense"], "train_dense")
    collect("TRAIN", ["span_c375_p0"], "train_c375")
    collect("PHONE", ["phone_oracle"], "phone_oracle")
    table = {}
    for gloss in names:
        row: dict[str, Any] = dict(cover.get(gloss, {}))
        for k, v in acc[gloss].items():
            row[k] = round(float(np.mean(v)), 4) if v else None
        realistic = acc[gloss]["dev_realistic"] + acc[gloss]["semlex_realistic"]
        row["independent_realistic_recall"] = (
            round(float(np.mean(realistic)), 4) if realistic else None
        )
        top5 = acc[gloss]["dev_realistic_top5"] + acc[gloss]["semlex_realistic_top5"]
        row["independent_realistic_top5"] = round(float(np.mean(top5)), 4) if top5 else None
        row["top_confusion"] = ";".join(f"{g}:{n}" for g, n in wrong_to[gloss].most_common(3))
        table[gloss] = row
    return table


def confusions(
    probs: dict[str, Scores], banks: dict[str, Any], names: list[str], index: dict[str, int]
) -> dict[str, Any]:
    directed: Counter[tuple[str, str]] = Counter()
    for population, views, role in (("DEV", REALISTIC, None), ("SEMLEX", SEMLEX_REALISTIC, "EVAL")):
        meta = banks[population][1]
        for v in views:
            p = probs[population].view(v)
            for i, x in enumerate(meta[v]):
                if role and x.get("role") != role:
                    continue
                pred = names[int(np.argmax(p[i]))]
                if pred != x["gloss"]:
                    directed[(x["gloss"], pred)] += 1
    pair: Counter[tuple[str, str]] = Counter()
    for (a, b), n in directed.items():
        pair[tuple(sorted((a, b)))] += n
    attractors = Counter()
    for (_, b), n in directed.items():
        attractors[b] += n
    return {
        "directed_top": [[a, b, n] for (a, b), n in directed.most_common(40)],
        "symmetric_top": [[a, b, n] for (a, b), n in pair.most_common(40)],
        "attractors_top": attractors.most_common(25),
    }


def decomposition(
    probs: dict[str, Scores], banks: dict[str, Any], index: dict[str, int]
) -> dict[str, Any]:
    """Per DEV clip: dense (training view), span at phone cadence, bounded runtime window."""
    meta = banks["DEV"][1]

    def majority(views: list[str]) -> dict[str, tuple[bool, bool]]:
        votes: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
        for v in views:
            r = ranks(probs["DEV"].view(v), labels(meta[v], index))
            for x, ri in zip(meta[v], r, strict=True):
                votes[x["sample_id"]].append((ri == 1, ri <= 5))
        return {
            k: (np.mean([a for a, _ in x]) >= 0.5, np.mean([b for _, b in x]) >= 0.5)
            for k, x in votes.items()
        }

    dense = majority(["span_dense"])
    span = majority([f"span_c375_p{k}" for k in range(4)])
    ctx = majority(REALISTIC)
    hand = {x["sample_id"]: x.get("hand_fraction", 1.0) for x in meta["ctx_c375_p0"]}
    cats: Counter[str] = Counter()
    for sid, (ok, top5) in ctx.items():
        if ok:
            cats["CORRECT"] += 1
            continue
        weak = hand.get(sid, 1.0) < 0.5
        if not dense[sid][0]:
            base = "DISCRIMINATION_TOP5" if dense[sid][1] else "DISCRIMINATION_ABSENT"
        elif not span[sid][0]:
            base = "CADENCE"
        else:
            base = "WINDOW_CONTEXT"
        cats[base + ("|WEAK_HANDS" if weak else "")] += 1
        cats["WRONG_BUT_TOP5" if top5 else "WRONG_ABSENT_TOP5"] += 1
    return dict(cats)


def runtime_summary(
    probs: dict[str, Scores], banks: dict[str, Any], index: dict[str, int]
) -> dict[str, Any]:
    meta = banks["DEV"][1]
    out = {}
    for mode in ("natural", "continuous"):
        v = f"rt_{mode}"
        m = meta[v]
        r = ranks(probs["DEV"].view(v), labels(m, index))
        contaminated = np.asarray([x["contaminated"] for x in m])
        missed = len(meta.get(f"{v}_missed", []))
        out[mode] = {
            "signs": len(m) + missed,
            "own_event": len(m),
            "correct_given_event": float(np.mean(r == 1)),
            "correct_word_rate": float(np.sum(r == 1) / (len(m) + missed)),
            "clean_windows": int((~contaminated).sum()),
            "correct_clean": float(np.mean(r[~contaminated] == 1))
            if (~contaminated).any()
            else None,
            "contaminated_windows": int(contaminated.sum()),
            "correct_contaminated": float(np.mean(r[contaminated] == 1))
            if contaminated.any()
            else None,
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--model", required=True, help="score directory name")
    parser.add_argument("--reference", help="score directory name for paired tests")
    args = parser.parse_args()
    root = args.evidence_root
    names = wve.glosses(root)
    banks = {
        p: wve.load_bank(root / wve.OUT / f"bank_{p}.npz")
        for p in ("DEV", "SEMLEX", "PHONE", "TRAIN")
    }
    metas = {p: b[1] for p, b in banks.items()}
    cover = coverage(root, metas)
    rep = model_report(root, args.model, args.reference, banks, names, cover)
    tiers = Counter(c["tier"] for c in cover.values())
    rep["coverage_tiers"] = dict(tiers)
    out = root / wve.OUT / "report"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.model}.json").write_text(
        json.dumps(rep, indent=1, default=float) + "\n", encoding="utf-8"
    )
    columns = sorted({k for row in rep["classes"].values() for k in row})
    with (out / f"{args.model}_classes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["gloss", *columns])
        w.writeheader()
        for gloss, row in rep["classes"].items():
            w.writerow(
                {
                    "gloss": gloss,
                    **{k: (";".join(v) if isinstance(v, list) else v) for k, v in row.items()},
                }
            )
    print(
        json.dumps(
            {
                "tiers": rep["coverage_tiers"],
                "pooled": rep["pooled_realistic"],
                "decomposition": rep["decomposition"],
                "runtime": rep["runtime"],
                "robustness": rep["robustness"],
            },
            indent=1,
            default=float,
        )
    )


if __name__ == "__main__":
    main()
