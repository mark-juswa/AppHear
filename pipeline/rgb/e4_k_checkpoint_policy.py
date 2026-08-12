"""E4-K checkpoint-policy diagnostic for the E4-J 3-sign reliable core.

Experiment-only. Reads completed E4-J metrics and evaluates whether model-selection policy is safe.
No training, Android assets, production recognizer files, or source datasets are modified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_SOURCE_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_j_reliable_core_3sign_pilot_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_k_checkpoint_policy_01")
REQUIRED_CLASSES = ["GOOD", "HELLO", "SORRY"]
REQUIRED_BRANCHES = ["conv1d_baseline", "tcn_masked_pool"]
CHECKPOINTS = ["best", "latest"]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_metrics(source_run: Path) -> dict[str, Any]:
    path = source_run / "metrics" / "metrics.json"
    if not path.exists():
        raise FileNotFoundError(f"missing E4-J metrics: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _per_class_min(split_metrics: dict[str, Any]) -> float:
    rows = split_metrics.get("per_class", [])
    if not rows:
        return 0.0
    return float(min(row["accuracy"] for row in rows))


def _collapse_flags(test_metrics: dict[str, Any], class_count: int) -> list[str]:
    flags: list[str] = []
    total = int(test_metrics.get("count", 0))
    predicted = test_metrics.get("predicted_class_counts", {})
    if total <= 0:
        return ["empty_test_split"]
    max_pred = max(predicted.values()) if predicted else 0
    if max_pred / total >= 0.60:
        flags.append(f"dominant_prediction_share={max_pred / total:.3f}")
    if len(predicted) < class_count:
        flags.append(f"missing_predicted_classes={class_count - len(predicted)}")
    return flags


def _candidate_rows(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    classes = list(metrics.get("classes", REQUIRED_CLASSES))
    rows: list[dict[str, Any]] = []
    for branch, seeds in metrics.get("branches", {}).items():
        for seed, payload in seeds.items():
            for checkpoint in CHECKPOINTS:
                item = payload[checkpoint]
                test = item["test"]
                rows.append(
                    {
                        "branch": branch,
                        "seed": str(seed),
                        "checkpoint": checkpoint,
                        "val_accuracy": float(item["val"]["accuracy"]),
                        "val_loss_last_epoch": float(payload.get("history_last", {}).get("val_loss", np.nan)),
                        "test_accuracy": float(test["accuracy"]),
                        "min_class_test_accuracy": _per_class_min(test),
                        "predicted_class_counts": test.get("predicted_class_counts", {}),
                        "collapse_flags": _collapse_flags(test, len(classes)),
                        "per_class": test.get("per_class", []),
                    }
                )
    return rows


def _family_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for branch in sorted({row["branch"] for row in rows}):
        out[branch] = {}
        for checkpoint in CHECKPOINTS:
            subset = [row for row in rows if row["branch"] == branch and row["checkpoint"] == checkpoint]
            tests = [row["test_accuracy"] for row in subset]
            mins = [row["min_class_test_accuracy"] for row in subset]
            collapses = [row for row in subset if row["collapse_flags"]]
            out[branch][checkpoint] = {
                "seed_count": len(subset),
                "mean_test": float(np.mean(tests)) if tests else 0.0,
                "std_test": float(np.std(tests)) if tests else 0.0,
                "min_seed_test": float(min(tests)) if tests else 0.0,
                "min_class_test": float(min(mins)) if mins else 0.0,
                "collapse_seed_count": len(collapses),
                "stable_at_090": bool(tests and min(tests) >= 0.90 and min(mins) >= 0.90 and not collapses),
            }
    return out


def _select_by_validation_accuracy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(rows, key=lambda row: (row["val_accuracy"], row["test_accuracy"], row["min_class_test_accuracy"]))


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    source_run = args.source_run
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    for relative in ("metrics", "logs"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    metrics = _load_metrics(source_run)
    classes = list(metrics.get("classes", []))
    rows = _candidate_rows(metrics)
    family = _family_summary(rows)
    selected = _select_by_validation_accuracy(rows)
    conv_latest = family.get("conv1d_baseline", {}).get("latest", {})
    conv_best = family.get("conv1d_baseline", {}).get("best", {})
    tcn_latest = family.get("tcn_masked_pool", {}).get("latest", {})

    strict_gate_passed = bool(
        classes == REQUIRED_CLASSES
        and selected["test_accuracy"] >= 0.90
        and selected["min_class_test_accuracy"] >= 0.90
        and not selected["collapse_flags"]
        and conv_latest.get("stable_at_090", False)
        and conv_best.get("stable_at_090", False)
    )
    deployable_policy_found = bool(conv_latest.get("stable_at_090", False))
    report = {
        "experiment": "e4_k_checkpoint_policy_v1",
        "source_run": str(source_run.resolve()),
        "run_dir": str(output.resolve()),
        "classes": classes,
        "source_script_gate_passed": metrics.get("stability_summary", {}).get("gate_passed"),
        "strict_written_gate_passed": strict_gate_passed,
        "deployable_policy_found": deployable_policy_found,
        "recommended_policy": "conv1d_baseline_latest_fixed_epoch" if deployable_policy_found else "none",
        "recommended_next_action": (
            "prepare fixed-epoch Conv1D expansion diagnostic with one added candidate sign"
            if deployable_policy_found
            else "do not expand; collect stronger validation data or rerun with better checkpoint callbacks"
        ),
        "selected_by_validation_accuracy": selected,
        "family_summary": family,
        "policy_rows": rows,
        "decision": (
            "limited_pass_use_conv1d_latest_for_next_offline_expansion_only"
            if deployable_policy_found and not strict_gate_passed
            else "full_pass" if strict_gate_passed else "no_go"
        ),
        "notes": [
            "E4-J script gate passed because it required validation-selected checkpoint plus Conv1D latest stability.",
            "The written E4-J gate also required best-checkpoint-family stability; Conv1D best failed that stricter condition.",
            "This report does not use held-out test to tune a production threshold; it diagnoses why existing selection policy is unsafe before any expansion.",
            "No Android integration or production export is authorized by this diagnostic.",
        ],
    }
    _write_json(output / "metrics" / "policy_report.json", report)
    (output / "metrics" / "policy_report.md").write_text(_markdown(report), encoding="utf-8")
    _write_json(output / "logs" / "policy_rows.json", {"rows": rows},)
    return report


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    for relative in ("metrics/policy_report.json", "metrics/policy_report.md", "logs/policy_rows.json"):
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    report_path = run_dir / "metrics" / "policy_report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("classes") != REQUIRED_CLASSES:
            errors.append("unexpected class list")
        if report.get("recommended_policy") == "tcn_masked_pool":
            errors.append("unexpected TCN recommendation")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# E4-K Checkpoint Policy Diagnostic",
        "",
        "Experiment-only. No Android export or production replacement is authorized.",
        "",
        f"- Source script gate passed: `{report['source_script_gate_passed']}`",
        f"- Strict written gate passed: `{report['strict_written_gate_passed']}`",
        f"- Deployable offline policy found: `{report['deployable_policy_found']}`",
        f"- Recommended policy: `{report['recommended_policy']}`",
        f"- Decision: `{report['decision']}`",
        "",
        "| Branch | Checkpoint | Mean Test | Std Test | Min Seed Test | Min Class Test | Collapse Seeds | Stable >=0.90 |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for branch, checkpoints in report["family_summary"].items():
        for checkpoint, item in checkpoints.items():
            lines.append(
                f"| `{branch}` | `{checkpoint}` | {item['mean_test']:.4f} | {item['std_test']:.4f} | "
                f"{item['min_seed_test']:.4f} | {item['min_class_test']:.4f} | "
                f"{item['collapse_seed_count']} | `{item['stable_at_090']}` |"
            )
    selected = report["selected_by_validation_accuracy"]
    lines.extend([
        "",
        "## Validation-Selected Checkpoint",
        "",
        f"- Branch: `{selected['branch']}`",
        f"- Seed: `{selected['seed']}`",
        f"- Checkpoint: `{selected['checkpoint']}`",
        f"- Validation accuracy: `{selected['val_accuracy']:.4f}`",
        f"- Test accuracy: `{selected['test_accuracy']:.4f}`",
        f"- Minimum class test accuracy: `{selected['min_class_test_accuracy']:.4f}`",
        "",
        "## Recommendation",
        "",
        report["recommended_next_action"],
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-K checkpoint-policy diagnostic")
    sub = parser.add_subparsers(dest="command", required=True)
    analyze_parser = sub.add_parser("analyze")
    analyze_parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    analyze_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.command == "analyze":
            result = analyze(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-k-policy] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())