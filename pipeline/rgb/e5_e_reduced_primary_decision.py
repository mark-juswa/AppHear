"""E5-E reduced-primary decision pass for E5-D.

Reads the completed E5-D reduced-primary metrics, tiers the 15 signs into
safe primary, guarded primary, confusion-group, and defer/repair buckets, and
writes decision artifacts. Metrics-only: no training, extraction, export,
Android changes, or production asset replacement.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

DEFAULT_E5D_RUN = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_d_reduced_primary_15sign_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_e_reduced_primary_decision_01")

# These were explicitly excluded before E5-D and must not be silently restored.
EXCLUDED_REPAIR_OR_ROUTED = {"HELLO", "KNOW", "SORRY"}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _seed_blocks(metrics: dict[str, Any]) -> dict[str, Any]:
    branches = metrics.get("branches", {})
    if "conv1d_baseline" not in branches:
        raise KeyError("E5-D metrics missing branches.conv1d_baseline")
    return branches["conv1d_baseline"]


def _policy_block(seed_metrics: dict[str, Any], policy: str) -> dict[str, Any]:
    if policy not in seed_metrics:
        raise KeyError(f"seed metrics missing policy: {policy}")
    return seed_metrics[policy]


def _collect_class_rows(config: dict[str, Any], metrics: dict[str, Any], policy: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    classes = list(config["classes"])
    seeds = _seed_blocks(metrics)
    per: dict[str, dict[str, Any]] = {}
    confusion_counter: Counter[tuple[str, str]] = Counter()

    for seed, seed_metrics in seeds.items():
        block = _policy_block(seed_metrics, policy)
        test = block["test"]
        train = block["train"]
        val = block["val"]
        per_by_split = {"train": train["per_class"], "val": val["per_class"], "test": test["per_class"]}
        by_gloss: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for split, rows in per_by_split.items():
            for item in rows:
                by_gloss[item["gloss"]][split] = item

        cm = test.get("confusion_matrix", [])
        pred_counts = test.get("predicted_class_counts", {})
        for gloss in classes:
            record = per.setdefault(
                gloss,
                {
                    "gloss": gloss,
                    "train_acc": [],
                    "val_acc": [],
                    "test_acc": [],
                    "test_count_total": 0,
                    "test_correct_total": 0,
                    "test_predicted_as_total": 0,
                    "top_confusions": Counter(),
                    "seeds": [],
                },
            )
            record["seeds"].append(seed)
            for split in ("train", "val", "test"):
                item = by_gloss[gloss][split]
                record[f"{split}_acc"].append(float(item["accuracy"]))
                if split == "test":
                    record["test_count_total"] += int(item["count"])
                    record["test_correct_total"] += int(item["correct"])
                    record["test_predicted_as_total"] += int(pred_counts.get(gloss, 0))
                    class_id = int(item["class_id"])
                    if cm:
                        for pred_idx, count in enumerate(cm[class_id]):
                            if count and pred_idx < len(classes) and classes[pred_idx] != gloss:
                                predicted = classes[pred_idx]
                                record["top_confusions"][predicted] += int(count)
                                confusion_counter[(gloss, predicted)] += int(count)

    rows: list[dict[str, Any]] = []
    for gloss, record in per.items():
        test_vals = record["test_acc"]
        val_vals = record["val_acc"]
        train_vals = record["train_acc"]
        confusions = record["top_confusions"].most_common()
        mean_test = mean(test_vals)
        min_test = min(test_vals)
        std_test = pstdev(test_vals) if len(test_vals) > 1 else 0.0
        top_confusion_count = int(confusions[0][1]) if confusions else 0
        top_confusion = confusions[0][0] if confusions else ""
        row = {
            "gloss": gloss,
            "policy": policy,
            "mean_train_acc": mean(train_vals),
            "mean_val_acc": mean(val_vals),
            "mean_test_acc": mean_test,
            "min_test_acc": min_test,
            "max_test_acc": max(test_vals),
            "std_test_acc": std_test,
            "train_test_gap": mean(train_vals) - mean_test,
            "val_test_gap": mean(val_vals) - mean_test,
            "test_count_total": int(record["test_count_total"]),
            "test_correct_total": int(record["test_correct_total"]),
            "test_predicted_as_total": int(record["test_predicted_as_total"]),
            "top_confusion": top_confusion,
            "top_confusion_count": top_confusion_count,
            "top_confusions": ";".join(f"{name}:{count}" for name, count in confusions[:6]),
        }
        row["tier"], row["recommended_action"], row["reason"] = _tier(row)
        rows.append(row)

    confusion_rows = [
        {"true_gloss": true, "predicted_gloss": pred, "count": count}
        for (true, pred), count in confusion_counter.most_common()
    ]
    return rows, confusion_rows


def _tier(row: dict[str, Any]) -> tuple[str, str, str]:
    mean_test = float(row["mean_test_acc"])
    min_test = float(row["min_test_acc"])
    std_test = float(row["std_test_acc"])
    top_confusion_count = int(row["top_confusion_count"])
    train_gap = float(row["train_test_gap"])

    if mean_test >= 0.85 and min_test >= 0.78 and std_test <= 0.08:
        return (
            "A_safe_primary_candidate",
            "keep_in_next_primary_candidate",
            "High mean/min test accuracy and stable across seeds.",
        )
    if mean_test >= 0.72 and min_test >= 0.65 and std_test <= 0.12:
        return (
            "B_guarded_primary_candidate",
            "keep_with_calibration_and_reject_policy",
            "Usable landmark signal, but below a release-like safe-primary floor.",
        )
    if mean_test >= 0.55 and min_test >= 0.45 and top_confusion_count <= 7:
        return (
            "B_guarded_primary_candidate",
            "keep_only_if_routed_simulation_preserves_precision",
            "Borderline signal that might survive as guarded primary after calibration.",
        )
    if top_confusion_count >= 6 or (mean_test >= 0.40 and train_gap >= 0.35):
        return (
            "C_confusion_group_or_repair",
            "register_confusion_group_or_repair_before_primary",
            "Repeated held-out confusion or large train-test gap makes this unsafe as a plain primary class.",
        )
    return (
        "D_defer_from_primary",
        "defer_until_more_data_or_better_evidence",
        "Held-out performance is too weak or unstable for the next primary candidate.",
    )


def _group_confusions(rows: list[dict[str, Any]], confusion_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tier_by_gloss = {row["gloss"]: row["tier"] for row in rows}
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for item in confusion_rows:
        if int(item["count"]) < 6:
            continue
        a = item["true_gloss"]
        b = item["predicted_gloss"]
        members = tuple(sorted({a, b}))
        if members in seen:
            continue
        seen.add(members)
        related = [x for x in confusion_rows if x["true_gloss"] in members or x["predicted_gloss"] in members]
        total = sum(int(x["count"]) for x in related if x["true_gloss"] in members and x["predicted_gloss"] in members)
        candidates.append(
            {
                "group_id": "_".join(members),
                "members": ",".join(members),
                "internal_confusion_count": total,
                "member_tiers": ";".join(f"{m}:{tier_by_gloss.get(m, '')}" for m in members),
                "recommended_action": "specialist_or_defer_unless_e5f_safe_subset_excludes_weak_member",
            }
        )
    candidates.sort(key=lambda row: (-int(row["internal_confusion_count"]), row["group_id"]))
    return candidates


def _aggregate(metrics: dict[str, Any], policy: str) -> dict[str, Any]:
    seeds = _seed_blocks(metrics)
    split_accs: dict[str, list[float]] = defaultdict(list)
    max_predicted_share: list[float] = []
    for seed_metrics in seeds.values():
        block = _policy_block(seed_metrics, policy)
        for split in ("train", "val", "test"):
            split_accs[split].append(float(block[split]["accuracy"]))
        pred_counts = block["test"].get("predicted_class_counts", {})
        total = sum(int(v) for v in pred_counts.values())
        if total:
            max_predicted_share.append(max(int(v) for v in pred_counts.values()) / total)
    return {
        "mean_train_accuracy": mean(split_accs["train"]),
        "mean_val_accuracy": mean(split_accs["val"]),
        "mean_test_accuracy": mean(split_accs["test"]),
        "min_test_accuracy": min(split_accs["test"]),
        "max_test_accuracy": max(split_accs["test"]),
        "max_predicted_share_by_seed": max_predicted_share,
        "mean_max_predicted_share": mean(max_predicted_share) if max_predicted_share else None,
    }


def _report(summary: dict[str, Any], latest_rows: list[dict[str, Any]], groups: list[dict[str, Any]]) -> str:
    lines = [
        "# E5-E Reduced Primary Decision Report",
        "",
        "E5-E is metrics-only. It does not train, export, extract, or modify Android assets.",
        "",
        f"Source E5-D run: `{summary['source_e5d_run']}`",
        f"Latest mean test: `{summary['latest_policy']['mean_test_accuracy']:.4f}`",
        f"Best mean test: `{summary['best_policy']['mean_test_accuracy']:.4f}`",
        "",
        "## Decision Buckets",
        "",
    ]
    for tier, glosses in summary["tiered_glosses"].items():
        lines.append(f"- `{tier}`: " + (", ".join(f"`{g}`" for g in glosses) or "None"))
    lines += ["", "## Recommended Next Primary Candidate", ""]
    lines.append(", ".join(f"`{g}`" for g in summary["recommended_next_primary_subset"]) or "None")
    lines += ["", "## Confusion Groups", ""]
    if groups:
        for group in groups:
            lines.append(f"- `{group['group_id']}`: members `{group['members']}`, internal confusion `{group['internal_confusion_count']}`")
    else:
        lines.append("No high-count confusion groups found.")
    lines += ["", "## Per-Class Latest Policy", ""]
    for row in latest_rows:
        lines.append(
            f"- `{row['gloss']}`: tier `{row['tier']}`, mean `{float(row['mean_test_acc']):.3f}`, "
            f"min `{float(row['min_test_acc']):.3f}`, top confusion `{row['top_confusion']}`"
        )
    lines += ["", "## Final Decision", "", summary["decision"], "", "## Next", "", summary["next_required_action"], ""]
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    e5d_run = args.e5d_run.resolve()
    output = args.output
    metrics_path = e5d_run / "metrics" / "metrics.json"
    config_path = e5d_run / "pilot_config.json"
    if not metrics_path.exists():
        raise FileNotFoundError(f"missing E5-D metrics: {metrics_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"missing E5-D config: {config_path}")
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("reports", "tables", "logs"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    config = _load_json(config_path)
    metrics = _load_json(metrics_path)
    latest_rows, latest_confusions = _collect_class_rows(config, metrics, "latest")
    best_rows, best_confusions = _collect_class_rows(config, metrics, "best")

    tier_order = {
        "A_safe_primary_candidate": 0,
        "B_guarded_primary_candidate": 1,
        "C_confusion_group_or_repair": 2,
        "D_defer_from_primary": 3,
    }
    latest_rows.sort(key=lambda row: (tier_order.get(row["tier"], 99), -float(row["mean_test_acc"]), row["gloss"]))
    best_rows.sort(key=lambda row: (tier_order.get(row["tier"], 99), -float(row["mean_test_acc"]), row["gloss"]))
    groups = _group_confusions(latest_rows, latest_confusions)

    fields = [
        "tier", "gloss", "policy", "recommended_action", "reason",
        "mean_train_acc", "mean_val_acc", "mean_test_acc", "min_test_acc", "max_test_acc", "std_test_acc",
        "train_test_gap", "val_test_gap", "test_count_total", "test_correct_total", "test_predicted_as_total",
        "top_confusion", "top_confusion_count", "top_confusions",
    ]
    _write_csv(output / "tables" / "e5_e_latest_class_decisions.csv", latest_rows, fields)
    _write_csv(output / "tables" / "e5_e_best_class_decisions.csv", best_rows, fields)
    _write_csv(output / "tables" / "e5_e_top_confusion_pairs_latest.csv", latest_confusions[:40], ["true_gloss", "predicted_gloss", "count"])
    _write_csv(output / "tables" / "e5_e_confusion_groups.csv", groups, ["group_id", "members", "internal_confusion_count", "member_tiers", "recommended_action"])

    tiered = defaultdict(list)
    for row in latest_rows:
        tiered[row["tier"]].append(row["gloss"])
    recommended_subset = tiered["A_safe_primary_candidate"] + tiered["B_guarded_primary_candidate"][: args.max_guarded]
    summary = {
        "experiment": "e5_e_reduced_primary_decision_v1",
        "run_dir": str(output.resolve()),
        "source_e5d_run": str(e5d_run),
        "class_count": int(config["class_count"]),
        "classes": list(config["classes"]),
        "excluded_repair_or_routed": sorted(EXCLUDED_REPAIR_OR_ROUTED),
        "latest_policy": _aggregate(metrics, "latest"),
        "best_policy": _aggregate(metrics, "best"),
        "tiered_glosses": {tier: tiered.get(tier, []) for tier in tier_order},
        "recommended_next_primary_subset": recommended_subset,
        "confusion_groups": groups,
        "decision": "E5-D reduced-primary strategy is useful, but the 15-sign set is not exportable as-is.",
        "next_required_action": "Prepare E5-F as a smaller safe/guarded primary routed simulation with E4-AG no-sign gate and existing GOOD/SORRY specialist evidence; keep weak E5-D signs out or routed/deferred.",
        "warnings": [
            "Metrics-only decision pass; no Android/export authorized.",
            "Aggregate accuracy is not sufficient for silent translation.",
            "HELLO, KNOW, and SORRY remain outside this primary subset until repaired or routed.",
            "Weak E5-D signs must not be forced into the next runtime candidate.",
        ],
        "passed": True,
    }
    _write_json(output / "reports" / "decision_summary.json", summary)
    _write_json(output / "logs" / "source_config_snapshot.json", config)
    (output / "reports" / "decision_report.md").write_text(_report(summary, latest_rows, groups), encoding="utf-8")
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors: list[str] = []
    required = [
        "reports/decision_summary.json",
        "reports/decision_report.md",
        "tables/e5_e_latest_class_decisions.csv",
        "tables/e5_e_best_class_decisions.csv",
        "tables/e5_e_top_confusion_pairs_latest.csv",
        "tables/e5_e_confusion_groups.csv",
    ]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if args.require_summary:
        summary_path = run_dir / "reports" / "decision_summary.json"
        if summary_path.exists():
            summary = _load_json(summary_path)
            if not summary.get("recommended_next_primary_subset"):
                errors.append("missing recommended_next_primary_subset")
            if not summary.get("confusion_groups"):
                errors.append("missing confusion groups")
            for blocked in EXCLUDED_REPAIR_OR_ROUTED:
                if blocked in summary.get("recommended_next_primary_subset", []):
                    errors.append(f"blocked/routed gloss appeared in primary subset: {blocked}")
        else:
            errors.append("missing summary for required summary check")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E5-E reduced primary decision pass")
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run")
    run_p.add_argument("--e5d-run", type=Path, default=DEFAULT_E5D_RUN)
    run_p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_p.add_argument("--max-guarded", type=int, default=4)
    run_p.add_argument("--overwrite", action="store_true")
    check_p = sub.add_parser("check")
    check_p.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    check_p.add_argument("--require-summary", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileExistsError, FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e5-e] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
