"""E4-AF acceptance-policy sweep for the routed recognizer.

This is a short safety-floor experiment. It reuses the best E4-AC signing gate
and the E4-S/E4-V routed recognizer, then tests whether Android-realistic
acceptance rules can remove residual real no-sign false commits without
retraining or extracting new data.

Experiment-only: no Android assets, TFLite exports, production recognizer files,
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

DEFAULT_E4AC_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_ac_low_motion_aware_gate_01")
DEFAULT_E4AA_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_01")
DEFAULT_PRIMARY_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01")
DEFAULT_SPECIALIST_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01")
DEFAULT_E4X_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_x_routed_system_validation_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_af_acceptance_policy_01")
SPLITS = {"train": 0, "val": 1, "test": 2}
FINAL_CLASSES = ["GOOD", "HELLO", "HAVE", "KNOW", "SORRY", "NO_SIGN"]
NO_SIGN_ID = FINAL_CLASSES.index("NO_SIGN")
HELLO_ID = FINAL_CLASSES.index("HELLO")


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _load_gate_probabilities(args: argparse.Namespace, data: dict[str, np.ndarray], seed: int) -> np.ndarray:
    import tensorflow as tf

    model_path = args.e4ac_run / "models" / f"seed_{seed}" / "low_motion_signing_gate.keras"
    if not model_path.exists():
        raise FileNotFoundError(f"missing E4-AC gate model: {model_path}")
    tf.keras.backend.clear_session()
    model = tf.keras.models.load_model(model_path)
    return model.predict(data["landmarks"], batch_size=int(args.batch_size), verbose=0).reshape(-1)


def _metric_row(seed: int, policy: str, split_name: str, params: dict[str, float], metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "seed": seed,
        "policy": policy,
        "split": split_name,
        "hello_gate_probability_min": params.get("hello_gate_probability_min", ""),
        "accepted_precision": float(metrics["accepted_precision"]),
        "positive_coverage": float(metrics["positive_coverage"]),
        "no_sign_false_commit_rate": float(metrics["no_sign_false_commit_rate"]),
        "good_recall": _class_recall(metrics, "GOOD"),
        "hello_recall": _class_recall(metrics, "HELLO"),
        "have_recall": _class_recall(metrics, "HAVE"),
        "know_recall": _class_recall(metrics, "KNOW"),
        "sorry_recall": _class_recall(metrics, "SORRY"),
        "no_sign_recall": _class_recall(metrics, "NO_SIGN"),
        "false_no_sign_accepts": int(metrics["false_no_sign_accepts"]),
        "accepted": int(metrics["accepted"]),
    }


def _passes(row: dict[str, Any], args: argparse.Namespace) -> bool:
    return bool(
        row["accepted_precision"] >= float(args.accepted_precision_min)
        and row["positive_coverage"] >= float(args.positive_coverage_min)
        and row["no_sign_false_commit_rate"] <= float(args.no_sign_false_commit_rate_max)
        and row["good_recall"] >= float(args.good_recall_min)
        and row["hello_recall"] >= float(args.hello_recall_min)
        and row["sorry_recall"] >= float(args.sorry_recall_min)
    )


def _apply_gate_and_policy(routed_final: np.ndarray, sign_probs: np.ndarray, base_threshold: float, hello_min: float | None) -> np.ndarray:
    final = routed_final.copy()
    final[sign_probs < base_threshold] = NO_SIGN_ID
    if hello_min is not None:
        hello_mask = final == HELLO_ID
        final[hello_mask & (sign_probs < hello_min)] = NO_SIGN_ID
    return final


def _candidate_hello_thresholds(sign_probs: np.ndarray, routed_final: np.ndarray, val_mask: np.ndarray) -> list[float]:
    hello_probs = sign_probs[val_mask & (routed_final == HELLO_ID)]
    fixed = np.asarray([0.0, 0.001, 0.005, 0.01, 0.025, 0.05, 0.10, 0.20, 0.35, 0.50, 0.70, 0.85, 0.95, 0.98, 0.99, 0.995, 0.999], dtype=np.float64)
    if hello_probs.size:
        quantiles = np.quantile(hello_probs, np.linspace(0.0, 1.0, 101))
        values = np.concatenate([fixed, quantiles])
    else:
        values = fixed
    return [float(x) for x in np.unique(np.clip(values, 0.0, 1.0))]


def _choose_policy(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    val_rows = [row for row in rows if row["split"] == "val"]
    for row in val_rows:
        row["passes_gate"] = _passes(row, args)
    feasible = [row for row in val_rows if row["passes_gate"]]
    if feasible:
        return sorted(feasible, key=lambda row: (row["no_sign_false_commit_rate"], -row["accepted_precision"], -row["positive_coverage"]))[0]
    return sorted(
        val_rows,
        key=lambda row: (row["accepted_precision"], row["positive_coverage"], row["hello_recall"], row["sorry_recall"], -row["no_sign_false_commit_rate"]),
        reverse=True,
    )[0]


def _summarize(seed_results: dict[str, Any], policy_name: str) -> dict[str, float]:
    tests = [payload["policies"][policy_name]["test"] for payload in seed_results.values()]
    return {
        "mean_test_accepted_precision": float(np.mean([m["accepted_precision"] for m in tests])),
        "min_test_accepted_precision": float(np.min([m["accepted_precision"] for m in tests])),
        "mean_test_positive_coverage": float(np.mean([m["positive_coverage"] for m in tests])),
        "min_test_positive_coverage": float(np.min([m["positive_coverage"] for m in tests])),
        "max_test_no_sign_false_commit_rate": float(np.max([m["no_sign_false_commit_rate"] for m in tests])),
        "mean_test_good_recall": float(np.mean([_class_recall(m, "GOOD") for m in tests])),
        "min_test_good_recall": float(np.min([_class_recall(m, "GOOD") for m in tests])),
        "mean_test_hello_recall": float(np.mean([_class_recall(m, "HELLO") for m in tests])),
        "min_test_hello_recall": float(np.min([_class_recall(m, "HELLO") for m in tests])),
        "mean_test_sorry_recall": float(np.mean([_class_recall(m, "SORRY") for m in tests])),
        "min_test_sorry_recall": float(np.min([_class_recall(m, "SORRY") for m in tests])),
    }


def _summary_passes(summary: dict[str, float], args: argparse.Namespace) -> bool:
    return bool(
        summary["min_test_accepted_precision"] >= float(args.accepted_precision_min)
        and summary["min_test_positive_coverage"] >= float(args.positive_coverage_min)
        and summary["max_test_no_sign_false_commit_rate"] <= float(args.no_sign_false_commit_rate_max)
        and summary["min_test_good_recall"] >= float(args.good_recall_min)
        and summary["min_test_hello_recall"] >= float(args.hello_recall_min)
        and summary["min_test_sorry_recall"] >= float(args.sorry_recall_min)
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    start = time.perf_counter()
    output = args.output
    for relative in ("metrics", "predictions", "logs"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    data = _combined_dataset(args.primary_run, args.e4aa_run)
    y_final = data["y_final"]
    split = data["split_index"]
    val_mask = split == SPLITS["val"]
    test_mask = split == SPLITS["test"]
    primary_config = _load_json(args.primary_run / "pilot_config.json", "E4-S config")
    specialist_config = _load_json(args.specialist_run / "pilot_config.json", "E4-V config")
    route_policy = _policy(args.e4x_run)
    ac_metrics = _load_json(args.e4ac_run / "metrics" / "low_motion_gate_metrics.json", "E4-AC metrics")

    grid_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    seed_results: dict[str, Any] = {}

    for seed in [int(seed) for seed in args.seeds]:
        threshold = float(ac_metrics["seed_results"][str(seed)]["threshold"])
        sign_probs = _load_gate_probabilities(args, data, seed)
        routed = _seed_predictions(seed, args.primary_run, args.specialist_run, primary_config, specialist_config, data)
        routed_final = _apply_policy(routed, route_policy)

        seed_policy_rows: list[dict[str, Any]] = []
        for policy_name, hello_min in [("e4_ac_baseline", None)]:
            final = _apply_gate_and_policy(routed_final, sign_probs, threshold, hello_min)
            seed_policy_rows.append(_metric_row(seed, policy_name, "val", {}, _evaluate_system(y_final, final, data["source"], val_mask)))
            seed_policy_rows.append(_metric_row(seed, policy_name, "test", {}, _evaluate_system(y_final, final, data["source"], test_mask)))

        for hello_min in _candidate_hello_thresholds(sign_probs, routed_final, val_mask):
            params = {"hello_gate_probability_min": hello_min}
            final = _apply_gate_and_policy(routed_final, sign_probs, threshold, hello_min)
            seed_policy_rows.append(_metric_row(seed, "hello_specific_gate", "val", params, _evaluate_system(y_final, final, data["source"], val_mask)))
            seed_policy_rows.append(_metric_row(seed, "hello_specific_gate", "test", params, _evaluate_system(y_final, final, data["source"], test_mask)))

        selected = _choose_policy(seed_policy_rows, args)
        selected_policy = str(selected["policy"])
        hello_min_value = selected.get("hello_gate_probability_min", "")
        hello_min = None if hello_min_value == "" else float(hello_min_value)
        selected_final = _apply_gate_and_policy(routed_final, sign_probs, threshold, hello_min)
        val_metrics = _evaluate_system(y_final, selected_final, data["source"], val_mask)
        test_metrics = _evaluate_system(y_final, selected_final, data["source"], test_mask)
        for row in seed_policy_rows:
            row["selected"] = bool(
                row["split"] == "val"
                and row["policy"] == selected_policy
                and str(row.get("hello_gate_probability_min", "")) == str(selected.get("hello_gate_probability_min", ""))
            )
            row["passes_gate"] = _passes(row, args) if row["split"] == "val" else ""
            grid_rows.append(row)
        seed_results[str(seed)] = {
            "selected_policy": selected_policy,
            "base_gate_threshold": threshold,
            "hello_gate_probability_min": hello_min,
            "validation_selection": selected,
            "policies": {
                "selected": {
                    "validation": val_metrics,
                    "test": test_metrics,
                }
            },
        }
        for idx in np.where(test_mask)[0].tolist():
            prediction_rows.append({
                "seed": seed,
                "sample_id": str(data["sample_ids"][idx]),
                "source": str(data["source"][idx]),
                "true_gloss": FINAL_CLASSES[int(y_final[idx])],
                "routed_gloss": FINAL_CLASSES[int(routed_final[idx])],
                "final_gloss": FINAL_CLASSES[int(selected_final[idx])],
                "sign_probability": float(sign_probs[idx]),
                "base_gate_threshold": threshold,
                "selected_policy": selected_policy,
                "hello_gate_probability_min": "" if hello_min is None else hello_min,
            })

    _write_csv(
        output / "metrics" / "acceptance_policy_grid.csv",
        grid_rows,
        [
            "seed",
            "policy",
            "split",
            "hello_gate_probability_min",
            "accepted_precision",
            "positive_coverage",
            "no_sign_false_commit_rate",
            "good_recall",
            "hello_recall",
            "have_recall",
            "know_recall",
            "sorry_recall",
            "no_sign_recall",
            "false_no_sign_accepts",
            "accepted",
            "passes_gate",
            "selected",
        ],
    )
    _write_csv(
        output / "predictions" / "selected_policy_test_predictions.csv",
        prediction_rows,
        [
            "seed",
            "sample_id",
            "source",
            "true_gloss",
            "routed_gloss",
            "final_gloss",
            "sign_probability",
            "base_gate_threshold",
            "selected_policy",
            "hello_gate_probability_min",
        ],
    )
    selected_summary = _summarize(seed_results, "selected")
    passed = _summary_passes(selected_summary, args)
    result = {
        "experiment": "e4_af_acceptance_policy_v1",
        "run_dir": str(output.resolve()),
        "e4ac_run": str(args.e4ac_run.resolve()),
        "e4aa_run": str(args.e4aa_run.resolve()),
        "primary_run": str(args.primary_run.resolve()),
        "specialist_run": str(args.specialist_run.resolve()),
        "e4x_run": str(args.e4x_run.resolve()),
        "gate": {
            "accepted_precision_min": float(args.accepted_precision_min),
            "positive_coverage_min": float(args.positive_coverage_min),
            "no_sign_false_commit_rate_max": float(args.no_sign_false_commit_rate_max),
            "good_recall_min": float(args.good_recall_min),
            "hello_recall_min": float(args.hello_recall_min),
            "sorry_recall_min": float(args.sorry_recall_min),
        },
        "seed_results": seed_results,
        "summary": selected_summary,
        "passed": passed,
        "decision": "safety_floor_policy_pass_move_to_e5a" if passed else "policy_only_no_go_collect_hello_like_nosign_or_revisit_gate_data",
        "elapsed_seconds": time.perf_counter() - start,
        "warnings": [
            "Offline policy sweep only; no Android/export authorized.",
            "No new extraction or training is performed.",
            "Temporal stability cannot be fully validated on isolated positive windows; Android streaming validation remains required after offline gates.",
        ],
    }
    _write_json(output / "metrics" / "acceptance_policy_metrics.json", result)
    _write_json(output / "logs" / "run_summary.json", {"passed": passed, "summary": selected_summary})
    return result


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = [
        "metrics/acceptance_policy_metrics.json",
        "metrics/acceptance_policy_grid.csv",
        "predictions/selected_policy_test_predictions.csv",
        "logs/run_summary.json",
    ]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if args.require_metrics and (run_dir / "metrics" / "acceptance_policy_metrics.json").exists():
        metrics = json.loads((run_dir / "metrics" / "acceptance_policy_metrics.json").read_text(encoding="utf-8"))
        if metrics.get("experiment") != "e4_af_acceptance_policy_v1":
            errors.append("unexpected experiment id")
        if "summary" not in metrics:
            errors.append("missing summary")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run")
    run_p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_p.add_argument("--e4ac-run", type=Path, default=DEFAULT_E4AC_RUN)
    run_p.add_argument("--e4aa-run", type=Path, default=DEFAULT_E4AA_RUN)
    run_p.add_argument("--primary-run", type=Path, default=DEFAULT_PRIMARY_RUN)
    run_p.add_argument("--specialist-run", type=Path, default=DEFAULT_SPECIALIST_RUN)
    run_p.add_argument("--e4x-run", type=Path, default=DEFAULT_E4X_RUN)
    run_p.add_argument("--seeds", nargs="+", default=["101", "202", "303"])
    run_p.add_argument("--batch-size", type=int, default=64)
    run_p.add_argument("--accepted-precision-min", type=float, default=0.95)
    run_p.add_argument("--positive-coverage-min", type=float, default=0.90)
    run_p.add_argument("--no-sign-false-commit-rate-max", type=float, default=0.05)
    run_p.add_argument("--good-recall-min", type=float, default=0.90)
    run_p.add_argument("--hello-recall-min", type=float, default=0.90)
    run_p.add_argument("--sorry-recall-min", type=float, default=0.90)
    check_p = sub.add_parser("check")
    check_p.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    check_p.add_argument("--require-metrics", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            parser.error(f"unknown command {args.command}")
        print(json.dumps(result, indent=2))
        return 0 if result.get("passed", True) or args.command == "run" else 1
    except Exception as exc:
        print(f"[e4-af] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
