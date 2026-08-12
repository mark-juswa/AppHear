"""E5-C tiering for the E5-B ASL-led 50-class diagnostic.

Offline report generator only. It reads E5-B metrics and dataset manifests, then
produces per-class keep/repair/specialist/defer recommendations. It does not
train, extract, export, or touch Android/production assets.
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

DEFAULT_E5B_RUN = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_b_asl_led_50_primary_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_c_50class_tiering_01")
STABLE_CONTROLS = {"GOOD", "HELLO", "HAVE", "KNOW"}
SPECIALIST_READY = {"SORRY"}
EXCLUDED_FROM_E5B = {"SORRY", "HELP", "BECOME", "MAKE", "GET", "WELCOME2", "BYE", "NO", "YES", "THANKYOU"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _per_class(metrics: dict[str, Any], policy: str = "latest") -> tuple[list[dict[str, Any]], dict[tuple[str, str], int]]:
    classes = _load_json(Path(metrics["run_dir"]) / "pilot_config.json")["classes"]
    seeds = metrics["branches"]["conv1d_baseline"]
    per: dict[str, dict[str, Any]] = {}
    confusions: dict[tuple[str, str], int] = defaultdict(int)
    for seed, seed_metrics in seeds.items():
        for split in ("train", "val", "test"):
            split_metrics = seed_metrics[policy][split]
            matrix = split_metrics.get("confusion_matrix", [])
            pred_counts = split_metrics.get("predicted_class_counts", {})
            for item in split_metrics["per_class"]:
                gloss = item["gloss"]
                record = per.setdefault(
                    gloss,
                    {
                        "gloss": gloss,
                        "train_acc": [],
                        "val_acc": [],
                        "test_acc": [],
                        "test_count": 0,
                        "test_correct": 0,
                        "test_predicted_as": 0,
                        "top_confusions": defaultdict(int),
                    },
                )
                record[f"{split}_acc"].append(float(item["accuracy"]))
                if split == "test":
                    record["test_count"] += int(item["count"])
                    record["test_correct"] += int(item["correct"])
                    record["test_predicted_as"] += int(pred_counts.get(gloss, 0))
                    row = matrix[int(item["class_id"])] if matrix else []
                    for idx, value in enumerate(row):
                        if idx < len(classes) and classes[idx] != gloss and value:
                            target = classes[idx]
                            count = int(value)
                            record["top_confusions"][target] += count
                            confusions[(gloss, target)] += count
    rows: list[dict[str, Any]] = []
    for gloss, record in per.items():
        conf_items = sorted(record["top_confusions"].items(), key=lambda kv: (-kv[1], kv[0]))
        test_vals = record["test_acc"]
        train_vals = record["train_acc"]
        val_vals = record["val_acc"]
        rows.append(
            {
                "gloss": gloss,
                "mean_train_acc": mean(train_vals),
                "mean_val_acc": mean(val_vals),
                "mean_test_acc": mean(test_vals),
                "min_test_acc": min(test_vals),
                "max_test_acc": max(test_vals),
                "std_test_acc": pstdev(test_vals) if len(test_vals) > 1 else 0.0,
                "train_test_gap": mean(train_vals) - mean(test_vals),
                "val_test_gap": mean(val_vals) - mean(test_vals),
                "test_count_total": int(record["test_count"]),
                "test_correct_total": int(record["test_correct"]),
                "test_predicted_as_total": int(record["test_predicted_as"]),
                "top_confusion": conf_items[0][0] if conf_items else "",
                "top_confusion_count": conf_items[0][1] if conf_items else 0,
                "top_confusions": ";".join(f"{k}:{v}" for k, v in conf_items[:5]),
            }
        )
    return rows, dict(confusions)


def _source_counts(manifest: list[dict[str, str]]) -> dict[str, Counter[str]]:
    out: dict[str, Counter[str]] = defaultdict(Counter)
    for row in manifest:
        out[row["canonical_gloss"]][row["source_id"]] += 1
    return out


def _classify(row: dict[str, Any]) -> tuple[str, str, str]:
    gloss = row["gloss"]
    mean_test = float(row["mean_test_acc"])
    min_test = float(row["min_test_acc"])
    std_test = float(row["std_test_acc"])
    train_gap = float(row["train_test_gap"])
    top_conf_count = int(row["top_confusion_count"])

    if gloss in {"HELLO", "KNOW"} and mean_test < 0.60:
        return (
            "C_regressed_control_repair",
            "remove_from_large_primary_until_confusion_repaired",
            "Previously stable control regressed in 50-class context; likely needs confusion-aware pruning or specialist/repair.",
        )
    if mean_test >= 0.70 and min_test >= 0.65 and std_test <= 0.10:
        return (
            "A_primary_candidate_strong",
            "candidate_for_reduced_primary_model",
            "Strong mean and minimum test accuracy across seeds in the 50-class stress test.",
        )
    if mean_test >= 0.60 and min_test >= 0.50:
        return (
            "B_primary_candidate_guarded",
            "candidate_for_reduced_primary_model_with_monitoring",
            "Useful signal but not enough margin for production without a smaller-batch validation.",
        )
    if mean_test >= 0.45 and top_conf_count >= 5:
        return (
            "C_confusion_group_candidate",
            "review_confusion_or_specialist_before_primary",
            "Moderate accuracy with repeated confusion; should be grouped or repaired before promotion.",
        )
    if train_gap >= 0.45 and mean_test < 0.45:
        return (
            "D_overfit_or_provenance_risk",
            "defer_and_repair_data_or_split",
            "High train-test gap with weak held-out performance suggests overfit, provenance, or label/variant mismatch.",
        )
    return (
        "D_defer_from_primary",
        "defer_until_more_data_or_repair",
        "Held-out performance is too weak for primary recognizer inclusion.",
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    e5b_run = args.e5b_run.resolve()
    output = args.output
    metrics_path = e5b_run / "metrics" / "metrics.json"
    config_path = e5b_run / "pilot_config.json"
    manifest_path = e5b_run / "pilot_manifest.csv"
    if not metrics_path.exists():
        raise FileNotFoundError(f"missing E5-B metrics: {metrics_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"missing E5-B config: {config_path}")
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing E5-B manifest: {manifest_path}")
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("tables", "reports", "logs"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    metrics = _load_json(metrics_path)
    config = _load_json(config_path)
    manifest = _read_csv(manifest_path)
    rows, confusions = _per_class(metrics, "latest")
    sources = _source_counts(manifest)

    for row in rows:
        counts = sources[row["gloss"]]
        row["asl_citizen_rows"] = int(counts.get("asl_citizen", 0))
        row["local_rows"] = int(counts.get("local", 0))
        tier, action, reason = _classify(row)
        row["tier"] = tier
        row["recommended_action"] = action
        row["reason"] = reason

    tier_order = {
        "A_primary_candidate_strong": 0,
        "B_primary_candidate_guarded": 1,
        "C_regressed_control_repair": 2,
        "C_confusion_group_candidate": 3,
        "D_overfit_or_provenance_risk": 4,
        "D_defer_from_primary": 5,
    }
    rows.sort(key=lambda r: (tier_order.get(r["tier"], 99), -float(r["mean_test_acc"]), r["gloss"]))

    fields = [
        "tier", "gloss", "recommended_action", "reason",
        "mean_train_acc", "mean_val_acc", "mean_test_acc", "min_test_acc", "max_test_acc", "std_test_acc",
        "train_test_gap", "val_test_gap", "test_count_total", "test_correct_total", "test_predicted_as_total",
        "top_confusion", "top_confusion_count", "top_confusions", "asl_citizen_rows", "local_rows",
    ]
    _write_csv(output / "tables" / "e5_c_class_tiers.csv", rows, fields)
    for tier in tier_order:
        _write_csv(output / "tables" / f"{tier}.csv", [r for r in rows if r["tier"] == tier], fields)

    top_confusions = [
        {"true_gloss": a, "predicted_gloss": b, "count": c}
        for (a, b), c in sorted(confusions.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))[:40]
    ]
    _write_csv(output / "tables" / "top_confusion_pairs.csv", top_confusions, ["true_gloss", "predicted_gloss", "count"])

    tier_counts = Counter(row["tier"] for row in rows)
    strong = [row["gloss"] for row in rows if row["tier"] == "A_primary_candidate_strong"]
    guarded = [row["gloss"] for row in rows if row["tier"] == "B_primary_candidate_guarded"]
    reduced_primary = strong + guarded[: max(0, int(args.max_reduced_primary) - len(strong))]
    stable_control_rows = [row for row in rows if row["gloss"] in STABLE_CONTROLS]
    summary = {
        "experiment": "e5_c_50class_tiering_v1",
        "run_dir": str(output.resolve()),
        "source_e5b_run": str(e5b_run),
        "class_count": int(config["class_count"]),
        "e5b_mean_latest_test_accuracy": mean([
            seed["latest"]["test"]["accuracy"] for seed in metrics["branches"]["conv1d_baseline"].values()
        ]),
        "e5b_random_baseline": metrics["random_baseline"],
        "tier_counts": dict(sorted(tier_counts.items())),
        "strong_primary_candidates": strong,
        "guarded_primary_candidates": guarded,
        "recommended_reduced_primary_vocabulary": reduced_primary,
        "specialist_ready_external": sorted(SPECIALIST_READY),
        "excluded_from_e5b_primary": sorted(EXCLUDED_FROM_E5B),
        "stable_control_summary": {
            row["gloss"]: {
                "mean_test_acc": row["mean_test_acc"],
                "min_test_acc": row["min_test_acc"],
                "tier": row["tier"],
                "top_confusion": row["top_confusion"],
            }
            for row in stable_control_rows
        },
        "decision": "do_not_export_e5b_train_reduced_primary_next",
        "next_recommended_experiment": "E5-D reduced primary validation using E5-C recommended vocabulary plus routed SORRY specialist and E4-AG no-sign gate",
        "warnings": [
            "Metrics-only tiering; no Android/export authorized.",
            "Recommended reduced vocabulary is a hypothesis requiring a new smaller-batch validation.",
            "HELLO and KNOW regressed in 50-class context and must not be silently promoted from E5-B.",
        ],
    }
    _write_json(output / "reports" / "tiering_summary.json", summary)
    _write_json(output / "logs" / "source_config_snapshot.json", config)
    (output / "reports" / "tiering_report.md").write_text(_report(summary, rows, top_confusions), encoding="utf-8")
    return summary


def _report(summary: dict[str, Any], rows: list[dict[str, Any]], confusions: list[dict[str, Any]]) -> str:
    lines = [
        "# E5-C 50-Class Tiering Report",
        "",
        "E5-C is metrics-only. It does not train, export, or modify Android assets.",
        "",
        f"Source E5-B run: `{summary['source_e5b_run']}`",
        f"Mean latest test accuracy: `{summary['e5b_mean_latest_test_accuracy']:.4f}` against random baseline `{summary['e5b_random_baseline']:.4f}`.",
        "",
        "## Tier Counts",
        "",
    ]
    for tier, count in summary["tier_counts"].items():
        lines.append(f"- `{tier}`: `{count}`")
    lines += ["", "## Recommended Reduced Primary Vocabulary", ""]
    lines.append(", ".join(f"`{x}`" for x in summary["recommended_reduced_primary_vocabulary"]) or "None")
    lines += ["", "## Stable Controls", ""]
    for gloss, item in summary["stable_control_summary"].items():
        lines.append(f"- `{gloss}`: mean `{item['mean_test_acc']:.3f}`, min `{item['min_test_acc']:.3f}`, tier `{item['tier']}`, top confusion `{item['top_confusion']}`")
    lines += ["", "## Top Confusion Pairs", ""]
    for item in confusions[:20]:
        lines.append(f"- `{item['true_gloss']}` -> `{item['predicted_gloss']}`: `{item['count']}`")
    lines += ["", "## Class Tiers", ""]
    for row in rows:
        lines.append(f"- `{row['gloss']}`: `{row['tier']}`, mean `{float(row['mean_test_acc']):.3f}`, min `{float(row['min_test_acc']):.3f}`, action `{row['recommended_action']}`")
    lines += ["", "## Decision", "", summary["decision"], "", "## Next", "", summary["next_recommended_experiment"], ""]
    return "\n".join(lines)


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors: list[str] = []
    required = [
        "reports/tiering_summary.json",
        "reports/tiering_report.md",
        "tables/e5_c_class_tiers.csv",
        "tables/top_confusion_pairs.csv",
    ]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if args.require_summary:
        summary_path = run_dir / "reports" / "tiering_summary.json"
        if summary_path.exists():
            summary = _load_json(summary_path)
            if not summary.get("recommended_reduced_primary_vocabulary"):
                errors.append("missing recommended reduced primary vocabulary")
            if "HELLO" in summary.get("recommended_reduced_primary_vocabulary", []) and summary.get("stable_control_summary", {}).get("HELLO", {}).get("tier") == "C_regressed_control_repair":
                errors.append("HELLO regressed but was recommended for reduced primary")
        else:
            errors.append("missing summary for required summary check")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E5-C tier E5-B 50-class results")
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run")
    run_p.add_argument("--e5b-run", type=Path, default=DEFAULT_E5B_RUN)
    run_p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_p.add_argument("--max-reduced-primary", type=int, default=16)
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
        print(f"[rgb/e5-c] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
