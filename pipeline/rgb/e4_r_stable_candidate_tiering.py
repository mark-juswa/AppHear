"""E4-R stable-candidate tiering for the dynamic mixed roadmap.

This is an offline report generator. It does not train, extract, export, or touch
Android assets.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path("artifacts/recognition_upgrade/e4_generalization")
E4M = ROOT / "e4_m_dual_source_candidate_screen_01"
E4N = ROOT / "e4_n_dual_source_5sign_screen_01"
E4O = ROOT / "e4_o_get_welcome2_7sign_screen_01"
E4P = ROOT / "e4_p_existing_feature_20sign_pressure_01"
E4Q = ROOT / "e4_q_confusion_resolver_sorry_become_help_01"

CORE_CONTROL = {"GOOD", "HELLO", "SORRY"}
E4N_PASSED_CANDIDATES = {"HAVE", "KNOW"}
KNOWN_COLLAPSE = {"MAKE", "GET"}
KNOWN_LOCAL_HARD = {"BYE", "NO", "YES", "THANKYOU"}
ACTIVE_CONFUSION = {"SORRY", "HELP", "BECOME"}
E4P_WEAK = {"CLEAN", "NICE", "WHAT1", "START"}
E4O_COUPLED = {"WELCOME2"}

RUN_REFS = {
    "e4_m": str(E4M),
    "e4_n": str(E4N),
    "e4_o": str(E4O),
    "e4_p": str(E4P),
    "e4_q": str(E4Q),
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def per_class_latest(metrics: dict, branch: str = "conv1d_baseline") -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    branches = metrics.get("branches", {})
    if branch not in branches:
        return out
    for _seed, seed_metrics in branches[branch].items():
        test = seed_metrics["latest"]["test"]
        matrix = test.get("confusion_matrix", [])
        classes = metrics["classes"]
        pred_counts = test.get("predicted_class_counts", {})
        for pc in test.get("per_class", []):
            gloss = pc["gloss"]
            item = out.setdefault(
                gloss,
                {
                    "accuracies": [],
                    "correct": 0,
                    "count": 0,
                    "confusions": defaultdict(int),
                    "predicted_as_count": 0,
                },
            )
            item["accuracies"].append(float(pc["accuracy"]))
            item["correct"] += int(pc["correct"])
            item["count"] += int(pc["count"])
            item["predicted_as_count"] += int(pred_counts.get(gloss, 0))
            row = matrix[int(pc["class_id"])] if matrix else []
            for idx, value in enumerate(row):
                if value and idx < len(classes) and classes[idx] != gloss:
                    item["confusions"][classes[idx]] += int(value)
    collapsed = {}
    for gloss, item in out.items():
        accs = item["accuracies"]
        confusion_items = sorted(item["confusions"].items(), key=lambda kv: (-kv[1], kv[0]))
        collapsed[gloss] = {
            "mean_latest_acc": mean(accs) if accs else None,
            "min_latest_acc": min(accs) if accs else None,
            "max_latest_acc": max(accs) if accs else None,
            "total_correct": item["correct"],
            "total_count": item["count"],
            "top_confusion": confusion_items[0][0] if confusion_items else "",
            "top_confusion_count": confusion_items[0][1] if confusion_items else 0,
            "all_confusions": ";".join(f"{k}:{v}" for k, v in confusion_items[:5]),
        }
    return collapsed


def e4q_latest_summary(metrics: dict) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for variant, seeds in metrics.get("variants", {}).items():
        for _seed, seed_metrics in seeds.items():
            test = seed_metrics["latest"]["test"]
            matrix = test.get("confusion_matrix", [])
            classes = metrics["classes"]
            for pc in test.get("per_class", []):
                gloss = pc["gloss"]
                item = out.setdefault(gloss, {"accuracies": [], "confusions": defaultdict(int)})
                item["accuracies"].append(float(pc["accuracy"]))
                row = matrix[int(pc["class_id"])] if matrix else []
                for idx, value in enumerate(row):
                    if value and idx < len(classes) and classes[idx] != gloss:
                        item["confusions"][classes[idx]] += int(value)
    result = {}
    for gloss, item in out.items():
        confs = sorted(item["confusions"].items(), key=lambda kv: (-kv[1], kv[0]))
        accs = item["accuracies"]
        result[gloss] = {
            "e4q_mean_acc_all_variants": mean(accs) if accs else None,
            "e4q_min_acc_all_variants": min(accs) if accs else None,
            "e4q_top_confusion": confs[0][0] if confs else "",
            "e4q_top_confusion_count": confs[0][1] if confs else 0,
        }
    return result


def classify(row: dict[str, object]) -> tuple[str, str, str]:
    gloss = str(row["gloss"])
    e4n_mean = row.get("e4n_mean_latest_acc")
    e4p_mean = row.get("e4p_mean_latest_acc")
    e4p_min = row.get("e4p_min_latest_acc")

    if gloss in {"GOOD", "HELLO"}:
        return (
            "A_primary_ready_guarded",
            "primary_landmark",
            "Core control sign with passed small-batch evidence; keep monitored for collapse with new signs.",
        )
    if gloss in E4N_PASSED_CANDIDATES:
        return (
            "A_primary_ready_guarded",
            "primary_landmark",
            "Passed E4-N bounded dual-source screen; eligible for stable-primary batch.",
        )
    if gloss in ACTIVE_CONFUSION:
        return (
            "B_confusion_specialist_or_repair",
            "router_then_specialist_or_reject",
            "Registered SORRY/BECOME/HELP group; E4-P/E4-Q show landmark-only confusion remains unresolved.",
        )
    if gloss in KNOWN_COLLAPSE:
        return (
            "B_confusion_specialist_or_repair",
            "defer_until_data_or_visual_resolver",
            "Known collapse with GOOD from E4-L/E4-O; do not include in primary stable model.",
        )
    if gloss in KNOWN_LOCAL_HARD:
        return (
            "B_confusion_specialist_or_repair",
            "defer_until_label_or_visual_repair",
            "Prior local separability/label issue; keep out of stable primary batch.",
        )
    if gloss in E4O_COUPLED:
        return (
            "C_defer_more_evidence",
            "defer",
            "WELCOME2 cannot be promoted from E4-O because it was coupled with failed GET; needs independent evidence.",
        )
    if gloss in E4P_WEAK:
        return (
            "B_confusion_specialist_or_repair",
            "review_before_primary",
            "Weak class in E4-P pressure test; needs review or targeted evidence before stable primary use.",
        )
    if isinstance(e4p_mean, float) and isinstance(e4p_min, float):
        if e4p_mean >= 0.80 and e4p_min >= 0.70:
            return (
                "A_candidate_needs_stable_training",
                "candidate_for_primary_batch",
                "Looked acceptable in failed E4-P pressure test, but still needs a dedicated stable-primary batch gate.",
            )
        if e4p_mean >= 0.65:
            return (
                "B_borderline_review",
                "review_or_collect_before_primary",
                "Borderline in failed E4-P pressure test; not safe for primary batch without more evidence.",
            )
    recommendation = str(row.get("e4m_recommendation", ""))
    if recommendation == "needs_video_validation_first":
        return ("C_defer_more_evidence", "validate_video_first", "E4-M found support but no validated local video evidence yet.")
    if recommendation == "asl_only_candidate_not_dual_source":
        return ("D_inventory_only", "asl_only_not_current_batch", "ASL Citizen-only candidate; not part of current dual-source stable path.")
    return ("C_defer_more_evidence", "defer", "Insufficient passed evidence for stable-primary inclusion.")


def build(output: Path) -> dict:
    inventory = {r["gloss"]: r for r in load_csv(E4M / "tables" / "candidate_inventory_ranked.csv")}
    e4m_summary = load_json(E4M / "reports" / "screen_summary.json")
    e4n = load_json(E4N / "metrics" / "metrics.json")
    e4p = load_json(E4P / "metrics" / "metrics.json")
    e4q = load_json(E4Q / "metrics" / "metrics.json")
    e4n_pc = per_class_latest(e4n)
    e4p_pc = per_class_latest(e4p)
    e4q_pc = e4q_latest_summary(e4q)

    glosses = sorted(set(inventory) | set(e4n.get("classes", [])) | set(e4p.get("classes", [])) | set(e4q.get("classes", [])))
    rows: list[dict[str, object]] = []
    for gloss in glosses:
        inv = inventory.get(gloss, {})
        row: dict[str, object] = {
            "gloss": gloss,
            "e4m_recommendation": inv.get("recommendation", ""),
            "e4m_score": inv.get("score", ""),
            "asl_train_count": inv.get("asl_train_count", ""),
            "asl_test_count": inv.get("asl_test_count", ""),
            "asl_train_signer_count": inv.get("asl_train_signer_count", ""),
            "asl_test_signer_count": inv.get("asl_test_signer_count", ""),
            "local_feature_count": inv.get("local_feature_count", ""),
            "local_feature_signer_count": inv.get("local_feature_signer_count", ""),
            "validated_eligible_rows": inv.get("validated_eligible_rows", ""),
            "validated_signer_count": inv.get("validated_signer_count", ""),
        }
        for prefix, src in (("e4n", e4n_pc), ("e4p", e4p_pc)):
            pc = src.get(gloss, {})
            row[f"{prefix}_mean_latest_acc"] = pc.get("mean_latest_acc", "")
            row[f"{prefix}_min_latest_acc"] = pc.get("min_latest_acc", "")
            row[f"{prefix}_total_count"] = pc.get("total_count", "")
            row[f"{prefix}_top_confusion"] = pc.get("top_confusion", "")
            row[f"{prefix}_top_confusion_count"] = pc.get("top_confusion_count", "")
            row[f"{prefix}_all_confusions"] = pc.get("all_confusions", "")
        q = e4q_pc.get(gloss, {})
        row.update(q)
        tier, action, reason = classify(row)
        row["tier"] = tier
        row["recommended_action"] = action
        row["reason"] = reason
        rows.append(row)

    tier_order = {
        "A_primary_ready_guarded": 0,
        "A_candidate_needs_stable_training": 1,
        "B_confusion_specialist_or_repair": 2,
        "B_borderline_review": 3,
        "C_defer_more_evidence": 4,
        "D_inventory_only": 5,
    }
    rows.sort(key=lambda r: (tier_order.get(str(r["tier"]), 99), str(r["gloss"])))

    output.mkdir(parents=True, exist_ok=True)
    fields = [
        "tier", "gloss", "recommended_action", "reason", "e4m_recommendation", "e4m_score",
        "e4n_mean_latest_acc", "e4n_min_latest_acc", "e4n_total_count", "e4n_top_confusion", "e4n_top_confusion_count",
        "e4p_mean_latest_acc", "e4p_min_latest_acc", "e4p_total_count", "e4p_top_confusion", "e4p_top_confusion_count", "e4p_all_confusions",
        "e4q_mean_acc_all_variants", "e4q_min_acc_all_variants", "e4q_top_confusion", "e4q_top_confusion_count",
        "asl_train_count", "asl_test_count", "asl_train_signer_count", "asl_test_signer_count",
        "local_feature_count", "local_feature_signer_count", "validated_eligible_rows", "validated_signer_count",
    ]
    write_csv(output / "tiered_candidates.csv", rows, fields)
    for tier in sorted(set(str(r["tier"]) for r in rows), key=lambda t: tier_order.get(t, 99)):
        tier_rows = [r for r in rows if r["tier"] == tier]
        write_csv(output / f"{tier}.csv", tier_rows, fields)

    counts = defaultdict(int)
    for row in rows:
        counts[str(row["tier"])] += 1
    stable = [r["gloss"] for r in rows if r["tier"] == "A_primary_ready_guarded"]
    candidates = [r["gloss"] for r in rows if r["tier"] == "A_candidate_needs_stable_training"]
    confusion = [r["gloss"] for r in rows if str(r["tier"]).startswith("B_")]
    summary = {
        "experiment": "e4_r_stable_candidate_tiering_v1",
        "run_dir": str(output.resolve()),
        "inputs": RUN_REFS,
        "row_count": len(rows),
        "tier_counts": dict(sorted(counts.items())),
        "primary_ready_guarded": stable,
        "candidate_needs_stable_training": candidates,
        "confusion_or_repair": confusion,
        "decision": "prepare_stable_primary_landmark_package_before_specialists",
        "next_recommended_experiment": "E4-S stable-primary landmark model using A_primary_ready_guarded plus optionally A_candidate_needs_stable_training only after review",
        "production_changes": "none",
        "e4_m_recommendation_counts": e4m_summary.get("recommendation_counts", {}),
    }
    (output / "tiering_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md = [
        "# E4-R Stable-Candidate Tiering Report",
        "",
        "Offline analysis only. No training, extraction, Android, or production asset changes.",
        "",
        f"- Rows ranked: `{len(rows)}`",
        f"- Tier counts: `{dict(sorted(counts.items()))}`",
        f"- Primary-ready guarded: `{', '.join(stable)}`",
        f"- Candidate-needs-stable-training: `{', '.join(candidates) if candidates else 'none'}`",
        f"- Confusion/repair signs: `{', '.join(confusion)}`",
        "",
        "## Decision",
        "",
        "Proceed next to E4-S stable-primary landmark package design. Do not jump directly to Android or RGB specialists.",
        "",
        "## Important Interpretation",
        "",
        "`A_primary_ready_guarded` means eligible for the next primary landmark experiment, not production-ready Android release.",
        "`A_candidate_needs_stable_training` means promising only inside a failed pressure run; these signs need a dedicated stable-primary gate.",
        "`B_*` signs need confusion handling, data repair, or specialist evidence before primary inclusion.",
    ]
    (output / "tiering_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return summary


def check(run_dir: Path) -> dict:
    errors = []
    for name in ["tiered_candidates.csv", "tiering_summary.json", "tiering_report.md"]:
        if not (run_dir / name).exists():
            errors.append(f"missing {name}")
    if not errors:
        summary = load_json(run_dir / "tiering_summary.json")
        if not summary.get("primary_ready_guarded"):
            errors.append("no primary_ready_guarded signs")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    (run_dir / "check_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_build = sub.add_parser("build")
    p_build.add_argument("--output", required=True)
    p_build.add_argument("--overwrite", action="store_true")
    p_check = sub.add_parser("check")
    p_check.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    if args.cmd == "build":
        output = Path(args.output)
        if output.exists() and any(output.iterdir()) and not args.overwrite:
            raise SystemExit(f"output exists and is not empty: {output}")
        summary = build(output)
        print(json.dumps(summary, indent=2))
        print(json.dumps(check(output), indent=2))
    elif args.cmd == "check":
        print(json.dumps(check(Path(args.run_dir)), indent=2))


if __name__ == "__main__":
    main()

