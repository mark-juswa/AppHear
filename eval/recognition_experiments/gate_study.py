"""Phase 3.5 commit-gate study on the repo's event ledgers (standard library only, deterministic).

Question set (from the Phase 3 brief), each answered only as far as the data allows:
  G1  Is the recognizer's top-1 probability CALIBRATED (reliability, ECE, Brier)?  It is never assumed to be.
  G2  Is ONE global confidence threshold appropriate?  (per-signer optima vs the shipped floor)
  G3  Does the global floor treat hard and easy classes differently?
  G4  Is there enough independent calibration data for CLASS-SPECIFIC thresholds?
  G5  Frozen recognizer vs the WORD-v2 candidate on IDENTICAL events: precision, recall (retention), coverage, F1.
  G6  Is there evidence that a TEMPORAL-consistency rule (stability under trimming) helps?

Data: docs/audit/probes/event_reliability/stream_ledger_*.json (held-out stitched ASL-Citizen streams, 5 signers) with the
repo's own labels. Calibration signers P5/P12/P21 and validation signers P26/P39 are the repo's pre-registered split
(docs/audit/probes/output_policy/calibrate.py). DEV signers were used for checkpoint selection of every recognizer
(DEV-EXPOSED); nothing here trains or tunes a model, and no threshold selected here is shipped (the shipped floors are
unchanged: they come from gate_policy.json).

Label convention (as in Phase 1): an event is CORRECT when it is credited to a sign and its top-1 equals that sign;
everything else (wrong gloss, duplicate, non-sign fragment) is WRONG.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path

from eval.recognition_experiments.error_analysis import HARD_RECALL, load_models
from eval.shadow_validation.shadow_report import wilson

ROOT = Path(__file__).resolve().parents[2]
ER = ROOT / "docs/audit/probes/event_reliability"
CAL = {"asl_citizen:P5", "asl_citizen:P12", "asl_citizen:P21"}
SHIPPED = {"S2_R2 baseline (STABLE)": 0.55, "Arm A + CB70 (EXPERIMENTAL)": 0.75}
LEDGERS = {"S2_R2 baseline (STABLE)": "stream_ledger_S2_R2__BASELINE.json",
           "Arm A + CB70 (EXPERIMENTAL)": "stream_ledger_ARM_A_E10__CONFIRM_BOUNDARY_70.json"}
MODELS = {"frozen": ("word_p1", "frozen_correct", "frozen_top1"), "word_v2": ("v2_p1", "v2_correct", "v2_top1")}


def load_events(name: str) -> list[dict]:
    return json.loads((ER / LEDGERS[name]).read_text(encoding="utf-8"))["dev"]


def is_correct(e: dict, model: str) -> bool:
    return e["category"] == "GENUINE" and bool(e.get(MODELS[model][1]))


def mcnemar_exact_p(b: int, c: int) -> float | None:
    """Two-sided exact binomial (sign) test on the discordant pairs."""
    n = b + c
    if n == 0:
        return None
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return round(min(1.0, 2 * p), 4)


def rate(k: int, n: int) -> dict:
    return {"k": k, "n": n, "value": None if n == 0 else round(k / n, 4), "wilson95": wilson(k, n)}


def auc(pos: list[float], neg: list[float]) -> float | None:
    if not pos or not neg:
        return None
    return round(sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg)), 4)


def youden(events: list[dict], model: str) -> tuple[float, float]:
    p = MODELS[model][0]
    ok = [e for e in events if is_correct(e, model)]
    bad = [e for e in events if not is_correct(e, model)]
    best = (-9.0, 0.0)
    for th in sorted({e[p] for e in events}):
        j = sum(e[p] >= th for e in ok) / len(ok) - sum(e[p] >= th for e in bad) / len(bad)
        if j > best[0]:
            best = (j, th)
    return round(best[0], 4), round(best[1], 4)


def metrics_at(events: list[dict], model: str, th: float | None) -> dict:
    p = MODELS[model][0]
    kept = [e for e in events if th is None or e[p] >= th]
    c_total = sum(is_correct(e, model) for e in events)
    c_kept = sum(is_correct(e, model) for e in kept)
    precision = c_kept / len(kept) if kept else None
    retention = c_kept / c_total if c_total else None
    f1 = 2 * precision * retention / (precision + retention) if precision and retention else None
    return {
        "events": len(events), "committed": len(kept), "committed_correct": c_kept, "committed_wrong": len(kept) - c_kept,
        "coverage_committed_per_event": round(len(kept) / len(events), 4) if events else None,
        "precision": rate(c_kept, len(kept)), "retention_recall": rate(c_kept, c_total),
        "false_rejection_rate": rate(c_total - c_kept, c_total),
        "f1": None if f1 is None else round(f1, 4),
    }


def reliability(events: list[dict], model: str, genuine_only: bool) -> dict:
    p = MODELS[model][0]
    pool = [e for e in events if (e["category"] == "GENUINE" or not genuine_only)]
    bins = collections.defaultdict(list)
    for e in pool:
        bins[min(9, int(e[p] * 10))].append((e[p], is_correct(e, model)))
    rows, ece = [], 0.0
    for b in sorted(bins):
        v = bins[b]
        conf = sum(x for x, _ in v) / len(v)
        acc = sum(1 for _, o in v if o) / len(v)
        ece += len(v) / len(pool) * abs(acc - conf)
        rows.append({"bin": f"{b / 10:.1f}-{(b + 1) / 10:.1f}", "n": len(v), "mean_confidence": round(conf, 3), "empirical_correct": round(acc, 3)})
    brier = sum((e[p] - (1.0 if is_correct(e, model) else 0.0)) ** 2 for e in pool) / len(pool)
    return {"events": len(pool), "ece": round(ece, 4), "brier": round(brier, 4), "bins": rows}


def study(name: str) -> dict:
    ev = load_events(name)
    cal = [e for e in ev if e["signer"] in CAL]
    val = [e for e in ev if e["signer"] not in CAL]
    shipped = SHIPPED[name]
    hard = {g for g, c in load_models()["frozen"].items() if c["recall_real"] <= HARD_RECALL}
    out: dict = {"events": len(ev), "cal_events": len(cal), "val_events": len(val), "shipped_floor": shipped}

    # G1 calibration
    out["G1_calibration"] = {m: {"all_events_is_it_a_correct_word": reliability(ev, m, False),
                                 "genuine_events_is_top1_right": reliability(ev, m, True)} for m in MODELS}

    # G2 per-signer optimum vs shipped floor (frozen model, the production recognizer)
    per_signer = {}
    for s in sorted({e["signer"] for e in ev}):
        es = [e for e in ev if e["signer"] == s]
        ok = sum(is_correct(e, "frozen") for e in es)
        if ok < 3 or ok == len(es):
            per_signer[s] = {"events": len(es), "correct": ok, "note": "too few correct/wrong events to estimate a threshold"}
            continue
        j, th = youden(es, "frozen")
        at = metrics_at(es, "frozen", shipped)
        c_total = ok
        j_shipped = (at["committed_correct"] / c_total) - ((at["committed"] - at["committed_correct"]) / (len(es) - c_total))
        per_signer[s] = {"events": len(es), "correct": ok, "signer_optimal_threshold": th, "J_at_signer_optimum": j,
                         "J_at_shipped_floor": round(j_shipped, 4)}
    ths = [v["signer_optimal_threshold"] for v in per_signer.values() if "signer_optimal_threshold" in v]
    out["G2_per_signer_thresholds_frozen"] = {"per_signer": per_signer,
                                              "optimal_threshold_range": [min(ths), max(ths)] if ths else None}

    # G3 hard vs easy predicted class under the shipped floor (frozen)
    g3 = {}
    for label, group in (("hard_classes(recall<=0.30)", lambda e: e["frozen_top1"] in hard), ("other_classes", lambda e: e["frozen_top1"] not in hard)):
        es = [e for e in ev if group(e)]
        ok = [e for e in es if is_correct(e, "frozen")]
        bad = [e for e in es if not is_correct(e, "frozen")]
        g3[label] = {"events": len(es), "correct": rate(sum(e["word_p1"] >= shipped for e in ok), len(ok)),
                     "wrong_kept": rate(sum(e["word_p1"] >= shipped for e in bad), len(bad)),
                     "mean_p1_correct": round(sum(e["word_p1"] for e in ok) / len(ok), 3) if ok else None}
    out["G3_global_floor_by_predicted_class_group"] = g3

    # G4 class-specific feasibility
    per_class = collections.Counter(e["frozen_top1"] for e in ev)
    per_class_cal = collections.Counter(e["frozen_top1"] for e in cal)
    out["G4_class_specific_support"] = {
        "classes_with_any_event": len(per_class), "max_events_for_one_class_all_signers": max(per_class.values()),
        "classes_with_>=10_events_all_signers": sum(1 for v in per_class.values() if v >= 10),
        "classes_with_>=10_events_calibration_signers": sum(1 for v in per_class_cal.values() if v >= 10),
        "classes_with_>=30_events_all_signers": sum(1 for v in per_class.values() if v >= 30),
        "median_events_per_class": sorted(per_class.values())[len(per_class) // 2],
        "verdict": "insufficient independent calibration data for class-specific thresholds"
                   if sum(1 for v in per_class_cal.values() if v >= 10) < 10 else "see counts"}

    # G5 frozen vs WORD v2 on the same events, each calibrated on the calibration signers only
    g5 = {}
    for m in MODELS:
        j, th = youden(cal, m)
        g5[m] = {"calibration_J": j, "calibrated_threshold_on_cal_signers": th,
                 "validation_ungated": metrics_at(val, m, None), "validation_gated_at_own_calibrated_threshold": metrics_at(val, m, th),
                 "validation_gated_at_shipped_floor_for_reference": metrics_at(val, m, shipped)}
    gen = [e for e in val if e["category"] == "GENUINE"]
    f_only = sum(1 for e in gen if e["frozen_correct"] and not e["v2_correct"])
    v_only = sum(1 for e in gen if e["v2_correct"] and not e["frozen_correct"])
    both = sum(1 for e in gen if e["v2_correct"] and e["frozen_correct"])
    g5["paired_top1_on_genuine_validation_events"] = {"both_correct": both, "frozen_only": f_only, "v2_only": v_only,
                                                       "mcnemar_exact_p_two_sided": mcnemar_exact_p(f_only, v_only),
                                                       "note": "same events, ungated; McNemar discordant pair counts"}
    out["G5_frozen_vs_word_v2"] = g5

    # G7 calibration check of the SHIPPED floor against this ledger's own signer-split optimum (frozen model)
    def j_at(es: list[dict], th: float) -> float:
        ok = [e for e in es if is_correct(e, "frozen")]
        bad = [e for e in es if not is_correct(e, "frozen")]
        return round(sum(e["word_p1"] >= th for e in ok) / len(ok) - sum(e["word_p1"] >= th for e in bad) / len(bad), 4)
    jopt, thopt = youden(cal, "frozen")
    out["G7_shipped_floor_vs_ledger_optimum"] = {
        "ledger_calibration_optimum": {"threshold": thopt, "J_cal": jopt, "J_val": j_at(val, thopt),
                                       "val": metrics_at(val, "frozen", thopt)},
        "shipped_floor": {"threshold": shipped, "J_cal": j_at(cal, shipped), "J_val": j_at(val, shipped),
                          "val": metrics_at(val, "frozen", shipped)},
        "note": "both points lie on the same trade-off curve; the shipped value was selected by the repo's own procedure "
                "(calibrate.py: both stream modes pooled, its own labelling) and is not changed here",
    }

    # G6 temporal strategy evidence: stability of top-1 under trimming the window (3 extra inferences per event)
    ok = [e["word_stability"] for e in ev if is_correct(e, "frozen")]
    bad = [e["word_stability"] for e in ev if not is_correct(e, "frozen")]
    okp = [e["word_p1"] for e in ev if is_correct(e, "frozen")]
    badp = [e["word_p1"] for e in ev if not is_correct(e, "frozen")]
    stable = [e for e in ev if e["word_stability"] >= 1.0]
    c_all = len(ok)
    out["G6_temporal_stability_evidence"] = {
        "auc_stability_correct_vs_rest": auc(ok, bad), "auc_top1_probability_correct_vs_rest": auc(okp, badp),
        "filter_stability_eq_1": {"correct_kept": rate(sum(is_correct(e, "frozen") for e in stable), c_all),
                                  "wrong_kept": rate(sum(not is_correct(e, "frozen") for e in stable), len(bad))},
        "verdict": "stability is not a better separator than top-1 probability and would triple recognizer cost; not supported"
                   if (auc(ok, bad) or 0) <= (auc(okp, badp) or 0) else "stability separates better; needs its own cost/latency evaluation",
    }
    return out


def run() -> dict:
    return {name: study(name) for name in LEDGERS}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write-json", type=Path)
    a = ap.parse_args(argv)
    r = run()
    for name, s in r.items():
        print("=" * 90)
        print(name, "events", s["events"], "| shipped floor", s["shipped_floor"])
        for m, v in s["G1_calibration"].items():
            print(f'  G1 {m:8s} ECE(all events)={v["all_events_is_it_a_correct_word"]["ece"]} ECE(genuine, top-1 right)={v["genuine_events_is_top1_right"]["ece"]}')
        print("  G2 per-signer optimal thresholds:", {k: v.get("signer_optimal_threshold") for k, v in s["G2_per_signer_thresholds_frozen"]["per_signer"].items()})
        print("  G3", {k: (v["events"], v["correct"]["value"], v["wrong_kept"]["value"]) for k, v in s["G3_global_floor_by_predicted_class_group"].items()})
        print("  G4", {k: v for k, v in s["G4_class_specific_support"].items() if k != "verdict"}, "->", s["G4_class_specific_support"]["verdict"])
        for m in MODELS:
            g = s["G5_frozen_vs_word_v2"][m]
            u, d = g["validation_ungated"], g["validation_gated_at_own_calibrated_threshold"]
            print(f'  G5 {m:8s} th={g["calibrated_threshold_on_cal_signers"]}: ungated correct {u["committed_correct"]}/wrong {u["committed_wrong"]} -> gated correct {d["committed_correct"]}/wrong {d["committed_wrong"]} '
                  f'precision {d["precision"]["value"]} retention {d["retention_recall"]["value"]} F1 {d["f1"]}')
        print("  G5 paired:", s["G5_frozen_vs_word_v2"]["paired_top1_on_genuine_validation_events"])
        g7 = s["G7_shipped_floor_vs_ledger_optimum"]
        print("  G7 optimum", g7["ledger_calibration_optimum"]["threshold"], "J_val", g7["ledger_calibration_optimum"]["J_val"], "| shipped", g7["shipped_floor"]["threshold"], "J_val", g7["shipped_floor"]["J_val"])
        print("  G6", {k: v for k, v in s["G6_temporal_stability_evidence"].items() if k.startswith("auc")}, s["G6_temporal_stability_evidence"]["verdict"])
    if a.write_json:
        a.write_json.write_text(json.dumps(r, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
