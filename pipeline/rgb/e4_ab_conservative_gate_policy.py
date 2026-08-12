"""E4-AB conservative signing-gate policy sweep.

Reuses the E4-AA real no-sign dataset and trained temporal gate models, then
sweeps gate thresholds with explicit low-motion sign protection. This tests
whether E4-AA failed because of threshold policy, not because the temporal gate
model has no usable separation.

Experiment-only: no Android assets, model exports, production recognizer files,
or source datasets are modified.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.rgb.e4_aa_nosign_temporal_gate import _combined_dataset, _evaluate_system, _write_json
from pipeline.rgb.e4_x_routed_system_validation import _apply_policy, _load_json, _seed_predictions
from pipeline.rgb.e4_z_signing_gate import _class_recall, _policy

DEFAULT_E4AA_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_01")
DEFAULT_PRIMARY_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01")
DEFAULT_SPECIALIST_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01")
DEFAULT_E4X_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_x_routed_system_validation_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_ab_conservative_gate_policy_01")
SPLITS = {"train": 0, "val": 1, "test": 2}
NO_SIGN_ID = 5


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _apply_gate(routed_final: np.ndarray, probs: np.ndarray, threshold: float) -> np.ndarray:
    out = routed_final.copy()
    out[probs < threshold] = NO_SIGN_ID
    return out


def _thresholds(probs: np.ndarray, val_mask: np.ndarray) -> np.ndarray:
    base = np.unique(np.quantile(probs[val_mask], np.linspace(0.0, 1.0, 161)))
    fixed = np.linspace(0.0, 1.0, 101)
    return np.unique(np.clip(np.concatenate([base, fixed]), 0.0, 1.0))


def _metrics_row(seed: int, threshold: float, split_name: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "seed": seed,
        "threshold": float(threshold),
        "split": split_name,
        "accepted_precision": float(metrics["accepted_precision"]),
        "positive_coverage": float(metrics["positive_coverage"]),
        "no_sign_false_commit_rate": float(metrics["no_sign_false_commit_rate"]),
        "good_recall": _class_recall(metrics, "GOOD"),
        "hello_recall": _class_recall(metrics, "HELLO"),
        "have_recall": _class_recall(metrics, "HAVE"),
        "know_recall": _class_recall(metrics, "KNOW"),
        "sorry_recall": _class_recall(metrics, "SORRY"),
        "no_sign_recall": _class_recall(metrics, "NO_SIGN"),
    }


def _passes(row: dict[str, Any], args: argparse.Namespace) -> bool:
    return bool(
        row["accepted_precision"] >= float(args.accepted_precision_min)
        and row["positive_coverage"] >= float(args.positive_coverage_min)
        and row["no_sign_false_commit_rate"] <= float(args.no_sign_false_commit_rate_max)
        and row["good_recall"] >= float(args.good_recall_min)
        and row["sorry_recall"] >= float(args.sorry_recall_min)
    )


def _choose_policy(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    val_rows = [row for row in rows if row["split"] == "val"]
    for row in val_rows:
        row["passes_gate"] = _passes(row, args)
    feasible = [row for row in val_rows if row["passes_gate"]]
    if feasible:
        return sorted(
            feasible,
            key=lambda row: (
                row["no_sign_false_commit_rate"],
                -row["accepted_precision"],
                -row["positive_coverage"],
                -row["sorry_recall"],
            ),
        )[0]
    return sorted(
        val_rows,
        key=lambda row: (
            row["sorry_recall"],
            row["positive_coverage"],
            row["accepted_precision"],
            -row["no_sign_false_commit_rate"],
        ),
        reverse=True,
    )[0]


def _summarize(seed_results: dict[str, Any]) -> dict[str, float]:
    tests = [payload["test"] for payload in seed_results.values()]
    return {
        "mean_test_accepted_precision": float(np.mean([m["accepted_precision"] for m in tests])),
        "min_test_accepted_precision": float(np.min([m["accepted_precision"] for m in tests])),
        "mean_test_positive_coverage": float(np.mean([m["positive_coverage"] for m in tests])),
        "min_test_positive_coverage": float(np.min([m["positive_coverage"] for m in tests])),
        "max_test_no_sign_false_commit_rate": float(np.max([m["no_sign_false_commit_rate"] for m in tests])),
        "mean_test_good_recall": float(np.mean([_class_recall(m, "GOOD") for m in tests])),
        "min_test_good_recall": float(np.min([_class_recall(m, "GOOD") for m in tests])),
        "mean_test_sorry_recall": float(np.mean([_class_recall(m, "SORRY") for m in tests])),
        "min_test_sorry_recall": float(np.min([_class_recall(m, "SORRY") for m in tests])),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    start = time.perf_counter()
    output = args.output
    for relative in ("metrics", "logs", "predictions"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    data = _combined_dataset(args.primary_run, args.e4aa_run)
    x = data["landmarks"]
    split = data["split_index"]
    val_mask = split == SPLITS["val"]
    test_mask = split == SPLITS["test"]
    primary_config = _load_json(args.primary_run / "pilot_config.json", "E4-S config")
    specialist_config = _load_json(args.specialist_run / "pilot_config.json", "E4-V config")
    policy = _policy(args.e4x_run)

    seed_results: dict[str, Any] = {}
    grid_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    seeds = [int(seed) for seed in args.seeds]
    for seed in seeds:
        model_path = args.e4aa_run / "models" / f"seed_{seed}" / "temporal_signing_gate.keras"
        if not model_path.exists():
            raise FileNotFoundError(f"missing E4-AA gate model for seed {seed}: {model_path}")
        tf.keras.backend.clear_session()
        model = tf.keras.models.load_model(model_path)
        probs = model.predict(x, batch_size=int(args.batch_size), verbose=0).reshape(-1)
        routed_preds = _seed_predictions(seed, args.primary_run, args.specialist_run, primary_config, specialist_config, data)
        routed_final = _apply_policy(routed_preds, policy)

        seed_grid: list[dict[str, Any]] = []
        for threshold in _thresholds(probs, val_mask):
            final = _apply_gate(routed_final, probs, float(threshold))
            val_metrics = _evaluate_system(data["y_final"], final, data["source"], val_mask)
            test_metrics = _evaluate_system(data["y_final"], final, data["source"], test_mask)
            seed_grid.append(_metrics_row(seed, float(threshold), "val", val_metrics))
            seed_grid.append(_metrics_row(seed, float(threshold), "test", test_metrics))
        chosen = _choose_policy(seed_grid, args)
        threshold = float(chosen["threshold"])
        final = _apply_gate(routed_final, probs, threshold)
        val_metrics = _evaluate_system(data["y_final"], final, data["source"], val_mask)
        test_metrics = _evaluate_system(data["y_final"], final, data["source"], test_mask)
        seed_results[str(seed)] = {
            "threshold": threshold,
            "validation_selection": chosen,
            "validation": val_metrics,
            "test": test_metrics,
        }
        for row in seed_grid:
            row["selected"] = bool(row["split"] == "val" and abs(float(row["threshold"]) - threshold) < 1e-12)
            grid_rows.append(row)
        for idx in np.where(test_mask)[0].tolist():
            prediction_rows.append({
                "seed": seed,
                "sample_id": str(data["sample_ids"][idx]),
                "source": str(data["source"][idx]),
                "true_id": int(data["y_final"][idx]),
                "pred_id": int(final[idx]),
                "sign_probability": float(probs[idx]),
                "threshold": threshold,
            })

    _write_csv(
        output / "metrics" / "threshold_policy_grid.csv",
        grid_rows,
        ["seed", "threshold", "split", "accepted_precision", "positive_coverage", "no_sign_false_commit_rate", "good_recall", "hello_recall", "have_recall", "know_recall", "sorry_recall", "no_sign_recall", "passes_gate", "selected"],
    )
    _write_csv(
        output / "predictions" / "test_predictions.csv",
        prediction_rows,
        ["seed", "sample_id", "source", "true_id", "pred_id", "sign_probability", "threshold"],
    )
    summary = _summarize(seed_results)
    gate = {
        "accepted_precision_min": float(args.accepted_precision_min),
        "positive_coverage_min": float(args.positive_coverage_min),
        "no_sign_false_commit_rate_max": float(args.no_sign_false_commit_rate_max),
        "good_recall_min": float(args.good_recall_min),
        "sorry_recall_min": float(args.sorry_recall_min),
    }
    passed = bool(
        summary["min_test_accepted_precision"] >= gate["accepted_precision_min"]
        and summary["min_test_positive_coverage"] >= gate["positive_coverage_min"]
        and summary["max_test_no_sign_false_commit_rate"] <= gate["no_sign_false_commit_rate_max"]
        and summary["min_test_good_recall"] >= gate["good_recall_min"]
        and summary["min_test_sorry_recall"] >= gate["sorry_recall_min"]
    )
    result = {
        "experiment": "e4_ab_conservative_gate_policy_v1",
        "run_dir": str(output.resolve()),
        "e4aa_run": str(args.e4aa_run.resolve()),
        "primary_run": str(args.primary_run.resolve()),
        "specialist_run": str(args.specialist_run.resolve()),
        "e4x_run": str(args.e4x_run.resolve()),
        "policy_goal": "select threshold on validation that protects SORRY/positive coverage before minimizing no-sign false commits",
        "gate": gate,
        "seed_results": seed_results,
        "summary": summary,
        "elapsed_seconds": time.perf_counter() - start,
        "passed": passed,
        "decision": "conservative_gate_policy_candidate" if passed else "conservative_gate_policy_no_go_tradeoff_unresolved",
        "warnings": [
            "Offline policy sweep only; no Android/export authorized.",
            "Reuses E4-AA trained gate models; this tests threshold policy, not a new gate architecture.",
            "If no threshold preserves SORRY and rejects no-sign, the next step must improve training data/model inputs rather than threshold tuning.",
        ],
    }
    _write_json(output / "metrics" / "conservative_gate_policy_metrics.json", result)
    _write_json(output / "logs" / "run_summary.json", {"passed": passed, "summary": summary})
    return result


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = [
        "metrics/conservative_gate_policy_metrics.json",
        "metrics/threshold_policy_grid.csv",
        "predictions/test_predictions.csv",
        "logs/run_summary.json",
    ]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if args.require_metrics and (run_dir / "metrics" / "conservative_gate_policy_metrics.json").exists():
        metrics = json.loads((run_dir / "metrics" / "conservative_gate_policy_metrics.json").read_text(encoding="utf-8"))
        if metrics.get("experiment") != "e4_ab_conservative_gate_policy_v1":
            errors.append("unexpected experiment id")
        if not isinstance(metrics.get("passed"), bool):
            errors.append("metrics missing boolean passed field")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-AB conservative no-sign gate policy sweep")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--e4aa-run", type=Path, default=DEFAULT_E4AA_RUN)
    run_parser.add_argument("--primary-run", type=Path, default=DEFAULT_PRIMARY_RUN)
    run_parser.add_argument("--specialist-run", type=Path, default=DEFAULT_SPECIALIST_RUN)
    run_parser.add_argument("--e4x-run", type=Path, default=DEFAULT_E4X_RUN)
    run_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    run_parser.add_argument("--batch-size", type=int, default=16)
    run_parser.add_argument("--accepted-precision-min", type=float, default=0.95)
    run_parser.add_argument("--positive-coverage-min", type=float, default=0.80)
    run_parser.add_argument("--no-sign-false-commit-rate-max", type=float, default=0.10)
    run_parser.add_argument("--good-recall-min", type=float, default=0.90)
    run_parser.add_argument("--sorry-recall-min", type=float, default=0.90)

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--require-metrics", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-ab] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

