"""Analyze E3-B5 landmark temporal scale results.

Reads the completed E3-B5 metrics artifact and writes reproducible error-analysis reports under
the same run directory. This does not train models or modify production assets.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_RUN_DIR = Path("artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed")


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    metrics_path = run_dir / "metrics" / "metrics.json"
    config_path = run_dir / "pilot_config.json"
    if not metrics_path.exists():
        raise FileNotFoundError(f"missing metrics: {metrics_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"missing config: {config_path}")

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    classes = list(config["classes"])
    out_dir = run_dir / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    branch_rows = _branch_rows(metrics)
    seed_rows = _seed_rows(metrics)
    class_rows = _class_rows(metrics, classes)
    confusion_rows = _confusion_rows(metrics, classes)
    bias_rows = _prediction_bias_rows(metrics, classes)

    _write_csv(out_dir / "branch_summary.csv", branch_rows, ["branch", "mean_best_val", "std_best_val", "mean_best_test", "std_best_test", "test_val_gap", "seed_count"])
    _write_csv(out_dir / "seed_summary.csv", seed_rows, ["branch", "seed", "best_train", "best_val", "best_test", "train_val_gap", "val_test_gap"])
    _write_csv(
        out_dir / "class_accuracy_summary.csv",
        class_rows,
        ["branch", "split", "gloss", "correct", "count", "accuracy", "rank_worst", "rank_best"],
    )
    _write_csv(
        out_dir / "confusion_pairs.csv",
        confusion_rows,
        ["branch", "split", "truth", "predicted", "count", "truth_total", "confusion_rate"],
    )
    _write_csv(
        out_dir / "prediction_bias.csv",
        bias_rows,
        ["branch", "seed", "split", "gloss", "predicted_count", "expected_count", "predicted_over_expected", "rank"],
    )

    result = {
        "experiment": "e3_b5_error_analysis_v1",
        "run_dir": str(run_dir.resolve()),
        "analysis_dir": str(out_dir.resolve()),
        "source_metrics": str(metrics_path.resolve()),
        "class_count": int(config["class_count"]),
        "split_counts": config["split_counts"],
        "decision": _decision(metrics),
        "top_findings": _top_findings(branch_rows, seed_rows, class_rows, confusion_rows, bias_rows),
        "outputs": [
            "analysis/analysis.json",
            "analysis/analysis.md",
            "analysis/branch_summary.csv",
            "analysis/seed_summary.csv",
            "analysis/class_accuracy_summary.csv",
            "analysis/confusion_pairs.csv",
            "analysis/prediction_bias.csv",
        ],
    }
    (out_dir / "analysis.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (out_dir / "analysis.md").write_text(_markdown(result, branch_rows, seed_rows, class_rows, confusion_rows, bias_rows), encoding="utf-8")
    return result


def _branch_rows(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for branch, item in metrics["summary"]["by_branch"].items():
        rows.append(
            {
                "branch": branch,
                "mean_best_val": float(item["mean_best_val"]),
                "std_best_val": float(item["std_best_val"]),
                "mean_best_test": float(item["mean_best_test"]),
                "std_best_test": float(item["std_best_test"]),
                "test_val_gap": float(item["mean_best_val"] - item["mean_best_test"]),
                "seed_count": int(item["seed_count"]),
            }
        )
    return sorted(rows, key=lambda row: -row["mean_best_val"])


def _seed_rows(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for branch, seeds in metrics["branches"].items():
        for seed, result in seeds.items():
            best = result["best"]
            rows.append(
                {
                    "branch": branch,
                    "seed": int(seed),
                    "best_train": float(best["train"]["accuracy"]),
                    "best_val": float(best["val"]["accuracy"]),
                    "best_test": float(best["test"]["accuracy"]),
                    "train_val_gap": float(best["train"]["accuracy"] - best["val"]["accuracy"]),
                    "val_test_gap": float(best["val"]["accuracy"] - best["test"]["accuracy"]),
                }
            )
    return sorted(rows, key=lambda row: (row["branch"], row["seed"]))


def _class_rows(metrics: dict[str, Any], classes: list[str]) -> list[dict[str, Any]]:
    rows = []
    for branch, seeds in metrics["branches"].items():
        for split in ("val", "test"):
            totals: dict[str, list[int]] = {name: [0, 0] for name in classes}
            for result in seeds.values():
                for row in result["best"][split]["per_class"]:
                    totals[row["gloss"]][0] += int(row["correct"])
                    totals[row["gloss"]][1] += int(row["count"])
            ranked = []
            for gloss, (correct, count) in totals.items():
                ranked.append((gloss, correct, count, correct / count if count else 0.0))
            worst_order = {gloss: idx + 1 for idx, (gloss, *_rest) in enumerate(sorted(ranked, key=lambda item: (item[3], item[0])))}
            best_order = {gloss: idx + 1 for idx, (gloss, *_rest) in enumerate(sorted(ranked, key=lambda item: (-item[3], item[0])))}
            for gloss, correct, count, acc in ranked:
                rows.append(
                    {
                        "branch": branch,
                        "split": split,
                        "gloss": gloss,
                        "correct": int(correct),
                        "count": int(count),
                        "accuracy": float(acc),
                        "rank_worst": worst_order[gloss],
                        "rank_best": best_order[gloss],
                    }
                )
    return sorted(rows, key=lambda row: (row["branch"], row["split"], row["rank_worst"]))


def _confusion_rows(metrics: dict[str, Any], classes: list[str]) -> list[dict[str, Any]]:
    rows = []
    for branch, seeds in metrics["branches"].items():
        for split in ("val", "test"):
            matrix = np.zeros((len(classes), len(classes)), dtype=np.int64)
            for result in seeds.values():
                matrix += np.asarray(result["best"][split]["confusion_matrix"], dtype=np.int64)
            truth_totals = matrix.sum(axis=1)
            for truth_idx, truth in enumerate(classes):
                for pred_idx, pred in enumerate(classes):
                    if truth_idx == pred_idx:
                        continue
                    count = int(matrix[truth_idx, pred_idx])
                    if count <= 0:
                        continue
                    total = int(truth_totals[truth_idx])
                    rows.append(
                        {
                            "branch": branch,
                            "split": split,
                            "truth": truth,
                            "predicted": pred,
                            "count": count,
                            "truth_total": total,
                            "confusion_rate": float(count / total) if total else 0.0,
                        }
                    )
    return sorted(rows, key=lambda row: (-row["count"], -row["confusion_rate"], row["branch"], row["split"], row["truth"], row["predicted"]))


def _prediction_bias_rows(metrics: dict[str, Any], classes: list[str]) -> list[dict[str, Any]]:
    rows = []
    for branch, seeds in metrics["branches"].items():
        for seed, result in seeds.items():
            for split in ("val", "test"):
                split_count = int(result["best"][split]["count"])
                expected = split_count / len(classes)
                counts = Counter(result["best"][split]["predicted_class_counts"])
                ranked = []
                for gloss in classes:
                    predicted = int(counts.get(gloss, 0))
                    ranked.append((gloss, predicted, predicted / expected if expected else 0.0))
                for rank, (gloss, predicted, ratio) in enumerate(sorted(ranked, key=lambda item: (-item[1], item[0])), start=1):
                    rows.append(
                        {
                            "branch": branch,
                            "seed": int(seed),
                            "split": split,
                            "gloss": gloss,
                            "predicted_count": predicted,
                            "expected_count": float(expected),
                            "predicted_over_expected": float(ratio),
                            "rank": rank,
                        }
                    )
    return rows


def _decision(metrics: dict[str, Any]) -> dict[str, Any]:
    summary = metrics["summary"]
    return {
        "promote_masked_tcn": False,
        "reason": "Masked TCN had the best mean validation score but won only one of three seeds; gate required at least two stable seed wins/ties.",
        "best_mean_validation_branch": summary["decision_hint"]["best_mean_validation_branch"],
        "masked_tcn_validation_wins": int(summary["decision_hint"]["masked_tcn_validation_wins"]),
        "seed_count": int(summary["decision_hint"]["seed_count"]),
    }


def _top_findings(
    branch_rows: list[dict[str, Any]],
    seed_rows: list[dict[str, Any]],
    class_rows: list[dict[str, Any]],
    confusion_rows: list[dict[str, Any]],
    bias_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    worst_gap = sorted(seed_rows, key=lambda row: -row["train_val_gap"])[:5]
    worst_val_classes = [row for row in class_rows if row["split"] == "val"][:15]
    worst_test_classes = [row for row in class_rows if row["split"] == "test"][:15]
    top_bias = [row for row in bias_rows if row["split"] == "test" and row["rank"] <= 5]
    top_bias_sorted = sorted(top_bias, key=lambda row: -row["predicted_over_expected"])[:15]
    return {
        "branch_ranking_by_mean_best_val": branch_rows,
        "largest_train_val_gaps": worst_gap,
        "worst_validation_classes": worst_val_classes,
        "worst_test_classes": worst_test_classes,
        "top_confusions": confusion_rows[:25],
        "strongest_test_prediction_biases": top_bias_sorted,
    }


def _markdown(
    result: dict[str, Any],
    branch_rows: list[dict[str, Any]],
    seed_rows: list[dict[str, Any]],
    class_rows: list[dict[str, Any]],
    confusion_rows: list[dict[str, Any]],
    bias_rows: list[dict[str, Any]],
) -> str:
    lines = [
        "# E3-B5 Error Analysis",
        "",
        "This report analyzes the completed 50-class signer-disjoint landmark-temporal validation. It does not train or modify production assets.",
        "",
        "## Decision",
        "",
        f"- Promote masked TCN: `{result['decision']['promote_masked_tcn']}`",
        f"- Reason: {result['decision']['reason']}",
        "",
        "## Branch Summary",
        "",
        "| Branch | Mean Best Val | Mean Best Test | Val-Test Gap | Val Std | Test Std |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in branch_rows:
        lines.append(
            f"| {row['branch']} | {row['mean_best_val']:.4f} | {row['mean_best_test']:.4f} | "
            f"{row['test_val_gap']:.4f} | {row['std_best_val']:.4f} | {row['std_best_test']:.4f} |"
        )
    lines.extend(["", "## Seed Summary", "", "| Branch | Seed | Train | Val | Test | Train-Val Gap | Val-Test Gap |", "|---|---:|---:|---:|---:|---:|---:|"])
    for row in seed_rows:
        lines.append(
            f"| {row['branch']} | {row['seed']} | {row['best_train']:.4f} | {row['best_val']:.4f} | "
            f"{row['best_test']:.4f} | {row['train_val_gap']:.4f} | {row['val_test_gap']:.4f} |"
        )
    lines.extend(["", "## Worst Validation Classes", "", "| Branch | Gloss | Correct / Count | Accuracy |", "|---|---|---:|---:|"])
    for row in [r for r in class_rows if r["split"] == "val"][:20]:
        lines.append(f"| {row['branch']} | {row['gloss']} | {row['correct']} / {row['count']} | {row['accuracy']:.4f} |")
    lines.extend(["", "## Top Confusions", "", "| Branch | Split | Truth | Predicted | Count | Rate |", "|---|---|---|---|---:|---:|"])
    for row in confusion_rows[:30]:
        lines.append(f"| {row['branch']} | {row['split']} | {row['truth']} | {row['predicted']} | {row['count']} | {row['confusion_rate']:.4f} |")
    lines.extend(["", "## Strongest Test Prediction Biases", "", "| Branch | Seed | Gloss | Predicted | Expected | Ratio |", "|---|---:|---|---:|---:|---:|"])
    for row in sorted([r for r in bias_rows if r["split"] == "test" and r["rank"] <= 5], key=lambda r: -r["predicted_over_expected"])[:20]:
        lines.append(
            f"| {row['branch']} | {row['seed']} | {row['gloss']} | {row['predicted_count']} | "
            f"{row['expected_count']:.1f} | {row['predicted_over_expected']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Engineering Interpretation",
            "",
            "- The current landmark features are useful: every branch is far above the 50-class random baseline.",
            "- The masked TCN result is directional but unstable; it should not be promoted as the sole landmark baseline yet.",
            "- The consistent validation-to-test drop points to signer generalization and class-specific confusion, not a simple training failure.",
            "- The next experiment should keep this same 50-class split and test one controlled improvement at a time.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze E3-B5 landmark temporal results")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    try:
        result = analyze(args)
    except (FileNotFoundError, KeyError, ValueError, OSError) as error:
        print(f"[rgb/e3-b5-analysis] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
