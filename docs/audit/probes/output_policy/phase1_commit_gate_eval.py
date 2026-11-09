"""Phase 1 word-commit gate: offline evaluation on the repo's existing event ledgers.

Standard library only; deterministic; reads only files already in the repository
(`docs/audit/probes/event_reliability/`). It does not run any model, does not open protected TEST data
and does not invent labels: every label is the one already assigned by `event_reliability.py`
(human review for phone sessions; the held-out benchmark's own credit rule for DEV signers).

What it answers (see docs/PHASE_1_RECOGNITION_RELIABILITY.md):
  A. Which commit-time score separates correct words from everything else, under the repo's
     pre-registered signer-split rule (calibrate on CAL signers, validate on the other signers)?
  B. Does an independent re-implementation reproduce the repo's published gate numbers?
  C. Does the structural "no hand observed inside the logical sign span" rule lose correct words?
  D. Metrics of the SHIPPED policy (floor + structural rule): false-positive rate on non-sign events,
     false rejection rate, precision, recall, F1, with Wilson 95% intervals (sample sizes are small).
  E. Per-class retention on the held-out DEV benchmark.

Usage:  python docs/audit/probes/output_policy/phase1_commit_gate_eval.py [--write-json]
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path

ER = Path(__file__).resolve().parents[1] / "event_reliability"
OUT = Path(__file__).resolve().parent / "phase1_commit_gate_eval.json"

# Same split as docs/audit/probes/output_policy/calibrate.py.
CAL_SIGNERS = {"asl_citizen:P5", "asl_citizen:P12", "asl_citizen:P21"}

CONFIGS = {
    # name: (phone ledger, DEV stream ledger, shipped top-1 floor, published gate_policy.json key)
    "STABLE (S2-R2 + frozen Gate-2)": ("ledger_S2_R2__BASELINE.json",
                                       "stream_ledger_S2_R2__BASELINE.json", 0.55, "S2_R2__BASELINE"),
    "EXPERIMENTAL (Arm A e10 + CB70 + frozen Gate-2)": ("ledger_ARM_A_E10__CONFIRM_BOUNDARY_70.json",
                                                         "stream_ledger_ARM_A_E10__CONFIRM_BOUNDARY_70.json",
                                                         0.75, "ARM_A_E10__CONFIRM_BOUNDARY_70"),
}

SCORES = {  # all oriented so that HIGHER = more evidence of a correct word
    "top1_probability": lambda e: e["word_p1"],
    "top1_top2_margin": lambda e: e["word_margin"],
    "negative_entropy": lambda e: -e["word_entropy"],
    "top1_stability_under_trim": lambda e: e["word_stability"],
    "accepted_hand_fraction_in_span": lambda e: e["hand_fraction"],
}


def load(name: str) -> dict:
    return json.loads((ER / name).read_text(encoding="utf-8"))


def sha256(name: str) -> str:
    return hashlib.sha256((ER / name).read_bytes()).hexdigest()


def wilson(k: int, n: int, z: float = 1.96) -> list[float | None]:
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def rate(k: int, n: int) -> dict:
    return {"k": k, "n": n, "value": None if n == 0 else round(k / n, 4), "wilson95": wilson(k, n)}


# ---- labels -------------------------------------------------------------------------------------------

def dev_label(e: dict) -> str:
    if e["category"] == "GENUINE":
        return "correct" if e.get("frozen_correct") else "wrong_genuine"
    return "nonsign_fragment"  # held-out DEV non-sign events are mostly sign fragments (audit doc, s.2)


def phone_label(e: dict) -> str:
    cat = e["category"]
    if cat == "GENUINE" and e.get("frozen_correct") is True:
        return "correct"
    if cat == "GENUINE" and e.get("frozen_correct") is False:
        return "wrong_genuine"
    if cat in ("CONFIRMED_NONSIGN", "PROTOCOL_ORDINARY_MOVEMENT"):
        return "nonsign"
    return "unscored"  # UNREVIEWED / PARTIAL_NONSIGN / PROTOCOL_SIGN_BLOCK: never counted as a false word


def phone_events(ledger: dict) -> list[dict]:
    return [e for s in ledger["sessions"].values() for e in s["events"]]


# ---- policy --------------------------------------------------------------------------------------------

def shipped_outcome(e: dict, floor: float) -> str:
    """Mirror of PhoneCommitPolicy.evaluate (floor on top-1 + no-hand-evidence invariant)."""
    if e["hand_fraction"] <= 0.0:
        return "REJECT"
    if e["word_p1"] < floor:
        return "UNCERTAIN"
    return "ACCEPT"


def metrics(events: list[dict], label, outcome) -> dict:
    """Event-level confusion of the commit decision. 'Recall' is relative to emitted events (signs the
    decoder never emitted are upstream misses and are not visible here)."""
    c = collections.Counter()
    for e in events:
        c[(label(e), outcome(e) == "ACCEPT")] += 1
    n_correct = c[("correct", True)] + c[("correct", False)]
    kept_correct = c[("correct", True)]
    kept_wrong = c[("wrong_genuine", True)]
    wrong = c[("wrong_genuine", True)] + c[("wrong_genuine", False)]
    nonsign_keys = [k for k in ("nonsign", "nonsign_fragment") if any(l == k for (l, _) in c)]
    ns_total = sum(c[(k, a)] for k in nonsign_keys for a in (True, False))
    ns_kept = sum(c[(k, True)] for k in nonsign_keys)
    committed_scored = kept_correct + kept_wrong + ns_kept
    precision = kept_correct / committed_scored if committed_scored else None
    recall = kept_correct / n_correct if n_correct else None
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall else None
    unscored = sum(v for (l, _), v in c.items() if l == "unscored")
    unscored_kept = c[("unscored", True)]
    return {
        "events": len(events),
        "correct_words": n_correct,
        "correct_kept": kept_correct,
        "wrong_on_genuine": wrong,
        "wrong_on_genuine_kept": kept_wrong,
        "nonsign_events": ns_total,
        "nonsign_kept": ns_kept,
        "unscored_events": unscored,
        "unscored_kept": unscored_kept,
        "recall_correct_retention": rate(kept_correct, n_correct),
        "false_rejection_rate": rate(n_correct - kept_correct, n_correct),
        "false_positive_rate_nonsign": rate(ns_kept, ns_total),
        "wrong_word_commit_rate": rate(kept_wrong, wrong),
        "precision_of_committed_scored": None if precision is None else round(precision, 4),
        "f1_correct_commit": None if f1 is None else round(f1, 4),
    }


# ---- A: pre-registered score comparison -------------------------------------------------------------

def youden_threshold(cal: list[dict], score) -> tuple[float, float]:
    ok = [e for e in cal if dev_label(e) == "correct"]
    bad = [e for e in cal if dev_label(e) != "correct"]
    best = (-9.0, 0.0)
    for th in sorted({score(e) for e in cal}):
        j = sum(score(e) >= th for e in ok) / len(ok) - sum(score(e) >= th for e in bad) / len(bad)
        if j > best[0]:
            best = (j, th)
    return best


def compare_scores(dev: list[dict]) -> dict:
    cal = [e for e in dev if e["signer"] in CAL_SIGNERS]
    val = [e for e in dev if e["signer"] not in CAL_SIGNERS]
    out = {"calibration_signers": sorted(CAL_SIGNERS),
           "validation_signers": sorted({e["signer"] for e in val}),
           "cal_events": len(cal), "val_events": len(val), "scores": {}}
    for name, score in SCORES.items():
        j, th = youden_threshold(cal, score)
        ok = [e for e in val if dev_label(e) == "correct"]
        bad = [e for e in val if dev_label(e) != "correct"]
        ck = sum(score(e) >= th for e in ok)
        wk = sum(score(e) >= th for e in bad)
        pos = [score(e) for e in ok]
        neg = [score(e) for e in bad]
        auc = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))
        out["scores"][name] = {
            "cal_youden_J": round(j, 4), "threshold": round(th, 4),
            "val_correct_kept": rate(ck, len(ok)), "val_wrong_kept": rate(wk, len(bad)),
            "val_precision_kept": round(ck / (ck + wk), 4) if ck + wk else None,
            "val_auc_correct_vs_rest": round(auc, 4),
        }
    return out


# ---- E: per-class ---------------------------------------------------------------------------------------

def per_class(dev: list[dict], floor: float) -> dict:
    rows: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for e in dev:
        lab = dev_label(e)
        kept = shipped_outcome(e, floor) == "ACCEPT"
        g = e["frozen_top1"]
        rows[g][f"{lab}_{'kept' if kept else 'withheld'}"] += 1
    table = []
    for g, c in rows.items():
        correct = c["correct_kept"] + c["correct_withheld"]
        committed = c["correct_kept"] + c["wrong_genuine_kept"] + c["nonsign_fragment_kept"]
        table.append({
            "predicted_gloss": g, "correct_events": correct, "correct_kept": c["correct_kept"],
            "retention": None if not correct else round(c["correct_kept"] / correct, 3),
            "wrong_or_fragment_kept": c["wrong_genuine_kept"] + c["nonsign_fragment_kept"],
            "precision_of_committed": None if not committed else round(c["correct_kept"] / committed, 3),
        })
    table.sort(key=lambda r: (-r["correct_events"], r["predicted_gloss"]))
    by_support = {}
    for s in (1, 3, 5):
        rows_s = [r for r in table if r["correct_events"] >= s]
        by_support[f"support_ge_{s}"] = {
            "classes": len(rows_s),
            "zero_retention_classes": sorted(r["predicted_gloss"] for r in rows_s if r["retention"] == 0),
            "median_retention": None if not rows_s else sorted(r["retention"] for r in rows_s)[len(rows_s) // 2],
        }
    return {
        "note": "Per PREDICTED class of emitted events on the held-out DEV benchmark; support is the number of "
                "correct events per class, which is small (hundreds of events over ~130 classes).",
        "by_support": by_support,
        "table": table,
    }


# ---- main --------------------------------------------------------------------------------------------------

def evaluate(name: str, phone_file: str, dev_file: str, floor: float, published_key: str) -> dict:
    phone = phone_events(load(phone_file))
    dev = load(dev_file)["dev"]
    val = [e for e in dev if e["signer"] not in CAL_SIGNERS]

    def shipped(e):
        return shipped_outcome(e, floor)

    def floor_only(e):
        return "ACCEPT" if e["word_p1"] >= floor else "UNCERTAIN"

    def ungated(_):
        return "ACCEPT"

    zero_hand = lambda es, lab: collections.Counter(lab(e) for e in es if e["hand_fraction"] <= 0.0)  # noqa: E731
    result = {
        "inputs": {phone_file: sha256(phone_file), dev_file: sha256(dev_file)},
        "shipped_floor": floor,
        "score_comparison_preregistered_split": compare_scores(dev) if floor == 0.55 else "see STABLE",
        "structural_rule_zero_hand_events": {
            "dev_all_signers": dict(zero_hand(dev, dev_label)),
            "phone_all_sessions": dict(zero_hand(phone, phone_label)),
            "correct_words_lost_by_rule": zero_hand(dev, dev_label)["correct"] + zero_hand(phone, phone_label)["correct"],
        },
        "dev_validation_signers": {
            "ungated": metrics(val, dev_label, ungated),
            "floor_only": metrics(val, dev_label, floor_only),
            "shipped": metrics(val, dev_label, shipped),
        },
        "dev_all_signers_shipped": metrics(dev, dev_label, shipped),
        "phone_reviewed_sessions": {
            "ungated": metrics(phone, phone_label, ungated),
            "floor_only": metrics(phone, phone_label, floor_only),
            "shipped": metrics(phone, phone_label, shipped),
        },
        "per_class_dev_all_signers_shipped": per_class(dev, floor),
    }
    pub = json.loads((ER / "gate_policy.json").read_text(encoding="utf-8")).get(published_key)
    if pub:
        v = result["dev_validation_signers"]["floor_only"]
        result["reproduces_published_gate_policy_json"] = {
            "published_dev_gated": pub["dev_validation"]["gated"],
            "recomputed_dev_gated": {"correct": v["correct_kept"], "wrong": v["wrong_on_genuine_kept"]
                                     + v["nonsign_kept"]},
            "match": pub["dev_validation"]["gated"] == {"correct": v["correct_kept"],
                                                        "wrong": v["wrong_on_genuine_kept"] + v["nonsign_kept"]},
        }
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write-json", action="store_true")
    args = ap.parse_args()
    report = {name: evaluate(name, *cfg) for name, cfg in CONFIGS.items()}
    text = json.dumps(report, indent=1, sort_keys=False)
    if args.write_json:
        OUT.write_text(text + "\n", encoding="utf-8")
    for name, r in report.items():
        print("=" * 100)
        print(name, "| shipped floor", r["shipped_floor"])
        rep = r.get("reproduces_published_gate_policy_json")
        if rep:
            print("  reproduces published gate_policy.json:", rep["match"], rep["published_dev_gated"], rep["recomputed_dev_gated"])
        sc = r["score_comparison_preregistered_split"]
        if isinstance(sc, dict):
            print("  A. pre-registered split (cal", sc["cal_events"], "events / val", sc["val_events"], "events)")
            for k, v in sc["scores"].items():
                print(f"     {k:32s} calJ={v['cal_youden_J']:.3f} th={v['threshold']:+.3f} "
                      f"val correct kept {v['val_correct_kept']['k']}/{v['val_correct_kept']['n']} "
                      f"wrong kept {v['val_wrong_kept']['k']}/{v['val_wrong_kept']['n']} AUC={v['val_auc_correct_vs_rest']:.3f}")
        print("  C. zero-hand-evidence events:", r["structural_rule_zero_hand_events"])
        for part in ("dev_validation_signers", "phone_reviewed_sessions"):
            for pol in ("ungated", "floor_only", "shipped"):
                m = r[part][pol]
                print(f"  D. {part:24s} {pol:10s} correct {m['correct_kept']}/{m['correct_words']} "
                      f"wrongGenuine {m['wrong_on_genuine_kept']}/{m['wrong_on_genuine']} "
                      f"nonsign {m['nonsign_kept']}/{m['nonsign_events']} unscored {m['unscored_kept']}/{m['unscored_events']} "
                      f"P={m['precision_of_committed_scored']} F1={m['f1_correct_commit']} "
                      f"FRR={m['false_rejection_rate']['value']} FPRns={m['false_positive_rate_nonsign']['value']}")
        pc = r["per_class_dev_all_signers_shipped"]
        for k, v in pc["by_support"].items():
            print(f"  E. per-class {k}: {v['classes']} classes, median retention {v['median_retention']}, "
                  f"zero-retention classes: {len(v['zero_retention_classes'])}")


if __name__ == "__main__":
    main()
