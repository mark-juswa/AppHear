"""Phase 3.1 recognition error analysis from the evidence tracked in this repository (standard library only).

Sources (all already in the repo; nothing is opened that the repo marks protected):
  docs/audit/probes/word_accuracy/difficult_words.json   per-class evidence for 236 classes x {frozen, BLEND_01, BLEND_02}
                                                          on the independent population (DEV + Sem-Lex EVAL-role signers)
  docs/audit/probes/heldout_dev_e2e/*.json                end-to-end funnel on held-out stitched streams

What it produces
  * the end-to-end FUNNEL (signs -> S2 acquisition -> distinct event -> correct word, plus the oracle ceiling) so an
    upstream loss is never attributed to the classifier;
  * per-class recall table and the 20 weakest classes with their diagnostic labels and dominant confusion partner;
  * estimated confusion-pair counts (from "dominant wrong prediction x its share of the class's errors");
  * model deltas per class, label counts, hand-visibility bands, training-signer coverage statistics.

What this data CANNOT support (stated, not worked around)
  * per-class PRECISION and F1: the file holds recall and only the single dominant wrong prediction per class, never the
    number of times a class was predicted wrongly for another class;
  * a full 236x236 confusion matrix: only the dominant partner per class is stored. The complete matrix needs the external
    artifact `word_vocabulary_eval_01` (see eval/runtime_diagnostics/word_vocabulary_report.py).

Usage: python -m eval.recognition_experiments.error_analysis [--write-json PATH]
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBES = ROOT / "docs/audit/probes"
HARD_RECALL = 0.30       # the producing script's own definition of a "hard" class
MOVE_THRESHOLD = 0.05    # WORD_PRIORITIES: a class "moved" when independent recall changed by more than 5 points
MIN_CLIPS_WEAKEST = 5    # a recall from fewer clips is mostly noise


def load_models(path: Path | None = None) -> dict[str, dict[str, dict]]:
    d = json.loads((path or PROBES / "word_accuracy/difficult_words.json").read_text(encoding="utf-8"))
    return {name: m["classes"] for name, m in d["models"].items()}


def pooled(classes: dict[str, dict]) -> dict:
    n = sum(c["clips"] for c in classes.values())
    ok = sum(c["recall_real"] * c["clips"] for c in classes.values())
    r = [c["recall_real"] for c in classes.values()]
    return {"classes": len(classes), "clips": n, "clip_weighted_accuracy": round(ok / n, 4),
            "macro_recall": round(sum(r) / len(r), 4), "median_class_recall": round(statistics.median(r), 4),
            "classes_zero_recall": sum(1 for x in r if x == 0), "hard_classes_recall_le_0.30": sum(1 for x in r if x <= HARD_RECALL)}


def label_counts(classes: dict[str, dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in classes.values():
        if c["recall_real"] <= HARD_RECALL:
            for lab in c["labels"]:
                out[lab] = out.get(lab, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def weakest(classes: dict[str, dict], k: int = 20, min_clips: int = MIN_CLIPS_WEAKEST) -> list[dict]:
    rows = [dict(c, cls=g) for g, c in classes.items() if c["clips"] >= min_clips]
    rows.sort(key=lambda r: (r["recall_real"], -r["clips"], r["cls"]))
    return rows[:k]


def pair_estimates(classes: dict[str, dict]) -> list[dict]:
    """Estimated wrong predictions per directed pair = clips x (1 - recall) x partner_share; symmetric pairs summed."""
    directed: dict[tuple[str, str], float] = {}
    for g, c in classes.items():
        if c.get("partner"):
            directed[(g, c["partner"])] = c["clips"] * (1 - c["recall_real"]) * c["partner_share"]
    pairs: dict[tuple[str, str], dict] = {}
    for (a, b), v in directed.items():
        key = tuple(sorted((a, b)))
        p = pairs.setdefault(key, {"pair": "/".join(key), "a_to_b": 0.0, "b_to_a": 0.0})
        p["a_to_b" if (a, b) == key else "b_to_a"] += v
    out = []
    for p in pairs.values():
        p["estimated_errors"] = round(p["a_to_b"] + p["b_to_a"], 2)
        p["a_to_b"], p["b_to_a"] = round(p["a_to_b"], 2), round(p["b_to_a"], 2)
        out.append(p)
    return sorted(out, key=lambda p: (-p["estimated_errors"], p["pair"]))


def model_delta(base: dict[str, dict], other: dict[str, dict], threshold: float = MOVE_THRESHOLD) -> dict:
    up = down = within = 0
    biggest_drops: list[tuple[str, float]] = []
    for g in base:
        # Recalls are stored to 3 decimals; round the difference so an exact 5-point change (0.55 - 0.50 =
        # 0.05000000000000004 in floating point) is not counted as "more than 5 points".
        d = round(other[g]["recall_real"] - base[g]["recall_real"], 3)
        if d > threshold:
            up += 1
        elif d < -threshold:
            down += 1
            biggest_drops.append((g, round(d, 3)))
        else:
            within += 1
    biggest_drops.sort(key=lambda t: t[1])
    return {"up": up, "down": down, "within": within, "largest_drops": biggest_drops[:8]}


def spearman(xs: list[float], ys: list[float]) -> float | None:
    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    if len(xs) < 3:
        return None
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return None if den == 0 else round(num / den, 3)


def training_coverage(classes: dict[str, dict]) -> dict:
    ts = [c["train_signers"] for c in classes.values()]
    return {
        "train_signers_per_class": {"min": min(ts), "median": statistics.median(ts), "max": max(ts)},
        "classes_with_fewer_than_12_train_signers": sum(1 for t in ts if t < 12),
        "spearman_train_signers_vs_recall": spearman([c["train_signers"] for c in classes.values()],
                                                     [c["recall_real"] for c in classes.values()]),
        "spearman_train_fit_vs_recall": spearman([c["train_fit"] for c in classes.values()],
                                                 [c["recall_real"] for c in classes.values()]),
        "spearman_hand_fraction_vs_recall": spearman([c["hand"] for c in classes.values()],
                                                     [c["recall_real"] for c in classes.values()]),
        "evaluation_clips_per_class": {"min": min(c["clips"] for c in classes.values()),
                                       "median": statistics.median(c["clips"] for c in classes.values()),
                                       "max": max(c["clips"] for c in classes.values())},
        "classes_with_at_least_8_eval_clips_and_5_signers": sum(1 for c in classes.values() if c["clips"] >= 8 and c["signers"] >= 5),
    }


def funnel(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for mode in ("NATURAL", "CONTINUOUS"):
        s = d["summary"][mode]
        signs = int(s["signs"])
        oracle = int(s["oracle_correct"])
        correct = int(s["correct_words"])
        out[mode] = {
            "signs": signs,
            "acquired_by_s2": int(s["acquired"]),
            "own_distinct_event": int(s["detected"]),
            "correct_words": correct,
            "oracle_correct_perfect_window_same_recognizer": oracle,
            "classifier_limited_signs": signs - oracle,
            "lost_upstream_of_classifier": oracle - correct,
            "share_of_oracle_correct_words_delivered": round(correct / oracle, 4),
            "merged_events": int(s["merged_events"]),
            "acquired_but_no_distinct_event": int(s["acquired_no_distinct_event"]),
            "extra_events": int(s["extra_events"]),
            "word_precision_of_events": round(s["word_precision"], 4),
            "per_signer_correct_word_rate": {k.split(":")[-1]: round(v, 3) for k, v in d["summary"]["per_signer_correct_word_rate"].items()
                                              if k.startswith(mode + ":")},
        }
    return out


def run() -> dict:
    models = load_models()
    f = models["frozen"]
    result = {
        "population": "pooled independent clips: DEV (5 ASL Citizen signers) + Sem-Lex EVAL-role signers; DEV is selection-exposed "
                      "to every compared model, EVAL signers were never trained on",
        "models": {name: {**pooled(c), "hard_label_counts": label_counts(c), **training_coverage(c)} for name, c in models.items()},
        "weakest20_frozen": [{k: r[k] for k in ("cls", "clips", "signers", "recall_real", "recall_dense", "hand", "train_fit",
                                                  "train_signers", "partner", "partner_share", "labels")} for r in weakest(f)],
        "weakest20_blend02": [{k: r[k] for k in ("cls", "clips", "signers", "recall_real", "recall_dense", "hand", "train_fit",
                                                   "train_signers", "partner", "partner_share", "labels")} for r in weakest(models["BLEND_02"])],
        "top_confusion_pairs_frozen": pair_estimates(f)[:20],
        "top_confusion_pairs_blend02": pair_estimates(models["BLEND_02"])[:20],
        "delta_frozen_to_blend02": model_delta(f, models["BLEND_02"]),
        "delta_blend01_to_blend02": model_delta(models["BLEND_01"], models["BLEND_02"]),
        "funnel_s2r2_production": funnel(PROBES / "heldout_dev_e2e/s2r2_base.json"),
        "funnel_armA": funnel(PROBES / "heldout_dev_e2e/armA_base.json"),
        "evidence_gaps": [
            "per-class precision and F1 (no per-class false-positive counts are stored)",
            "full 236x236 confusion matrix (only the dominant wrong prediction per class is stored)",
            "per-signer per-class results (per-signer aggregates only)",
        ],
    }
    pw = weakest(f)
    lab: dict[str, int] = {}
    for r in pw:
        for x in r["labels"]:
            lab[x] = lab.get(x, 0) + 1
    result["weakest20_frozen_label_counts"] = dict(sorted(lab.items(), key=lambda kv: -kv[1]))
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write-json", type=Path)
    a = ap.parse_args(argv)
    r = run()
    for name, m in r["models"].items():
        print(f'{name:9s} clips={m["clips"]} acc={m["clip_weighted_accuracy"]} macro={m["macro_recall"]} hard={m["hard_classes_recall_le_0.30"]} '
              f'zero={m["classes_zero_recall"]} labels={m["hard_label_counts"]}')
    for tag in ("funnel_s2r2_production", "funnel_armA"):
        for mode, v in r[tag].items():
            print(tag, mode, {k: v[k] for k in ("signs", "acquired_by_s2", "own_distinct_event", "correct_words",
                                               "oracle_correct_perfect_window_same_recognizer", "lost_upstream_of_classifier")})
    print("delta blend01->blend02", r["delta_blend01_to_blend02"]["up"], r["delta_blend01_to_blend02"]["down"], r["delta_blend01_to_blend02"]["within"])
    print("weakest (frozen):", [x["cls"] for x in r["weakest20_frozen"]])
    if a.write_json:
        a.write_json.write_text(json.dumps(r, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
