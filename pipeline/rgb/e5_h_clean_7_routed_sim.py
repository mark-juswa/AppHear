"""E5-H clean 7-class routed simulation.

Evaluates the E5-G clean 7-class primary model in the same no-sign/OOV routed
setting that made E5-F fail. This tests whether retraining the primary on only
the selected stable subset improves usable commit behavior.

Experiment-only: no extraction, Android changes, TFLite export, production
recognizer replacement, or source dataset mutation.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.rgb.e3_b4_landmark_temporal import _inputs_for, _load_weights_model
from pipeline.rgb.e5_f_reduced_primary_routed_sim import (
    BRANCH,
    DEFAULT_E5D_RUN,
    DEFAULT_GATE_RUN,
    DEFAULT_NOSIGN_RUN,
    NO_SIGN,
    SPLITS,
    _apply_policy,
    _evaluate,
    _gate_threshold,
    _grid,
    _load_gate,
    _load_json,
    _load_npz,
    _select_threshold,
    _write_csv,
    _write_json,
)

DEFAULT_E5G_RUN = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_g_clean_7_primary_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_h_clean_7_routed_sim_01")


def _load_positive_dataset(e5g_run: Path, commit_classes: list[str] | None = None) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    config = _load_json(e5g_run / "pilot_config.json", "E5-G config")
    data = _load_npz(e5g_run / "dataset" / "landmark_features.npz", "E5-G landmark tensor")
    classes = list(config["classes"])
    y_raw = data["y"].astype(np.int64)
    glosses = np.asarray([classes[int(y)] for y in y_raw]).astype(str)
    commit_set = set(commit_classes or classes)
    row_kind = np.asarray(["positive" if gloss in commit_set else "unsupported" for gloss in glosses]).astype(str)
    return {
        "landmarks": data["landmarks"].astype(np.float32),
        "frame_mask": data["frame_mask"].astype(bool),
        "split_index": data["split_index"].astype(np.int64),
        "sample_ids": np.asarray(data["sample_ids"]).astype(str),
        "source": np.asarray(["e5g_positive" if gloss in commit_set else "e5g_subset_unsupported" for gloss in glosses]).astype(str),
        "true_gloss": glosses,
        "row_kind": row_kind,
    }, config


def _load_unsupported_dataset(e5d_run: Path, selected: list[str]) -> dict[str, np.ndarray]:
    config = _load_json(e5d_run / "pilot_config.json", "E5-D config")
    data = _load_npz(e5d_run / "dataset" / "landmark_features.npz", "E5-D landmark tensor")
    classes = list(config["classes"])
    y_raw = data["y"].astype(np.int64)
    glosses = np.asarray([classes[int(y)] for y in y_raw]).astype(str)
    keep = np.asarray([gloss not in set(selected) for gloss in glosses], dtype=bool)
    return {
        "landmarks": data["landmarks"][keep].astype(np.float32),
        "frame_mask": data["frame_mask"][keep].astype(bool),
        "split_index": data["split_index"][keep].astype(np.int64),
        "sample_ids": np.asarray(data["sample_ids"])[keep].astype(str),
        "source": np.asarray(["e5d_unsupported"] * int(np.sum(keep))).astype(str),
        "true_gloss": glosses[keep].astype(str),
        "row_kind": np.asarray(["unsupported"] * int(np.sum(keep))).astype(str),
    }


def _load_nosign_dataset(nosign_run: Path) -> dict[str, np.ndarray]:
    data = _load_npz(nosign_run / "dataset" / "nosign_features.npz", "E4-AG no-sign tensor")
    return {
        "landmarks": data["landmarks"].astype(np.float32),
        "frame_mask": data["frame_mask"].astype(bool),
        "split_index": data["split_index"].astype(np.int64),
        "sample_ids": np.asarray(data["sample_ids"]).astype(str),
        "source": np.asarray(data["source"]).astype(str),
        "true_gloss": np.asarray([NO_SIGN] * int(data["landmarks"].shape[0])).astype(str),
        "row_kind": np.asarray(["no_sign"] * int(data["landmarks"].shape[0])).astype(str),
    }


def _combined_dataset(e5g_run: Path, e5d_run: Path, nosign_run: Path, commit_classes: list[str] | None = None) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    positive, config = _load_positive_dataset(e5g_run, commit_classes)
    unsupported = _load_unsupported_dataset(e5d_run, list(commit_classes or config["classes"]))
    nosign = _load_nosign_dataset(nosign_run)
    return {
        "landmarks": np.concatenate([positive["landmarks"], unsupported["landmarks"], nosign["landmarks"]], axis=0).astype(np.float32),
        "frame_mask": np.concatenate([positive["frame_mask"], unsupported["frame_mask"], nosign["frame_mask"]], axis=0).astype(bool),
        "split_index": np.concatenate([positive["split_index"], unsupported["split_index"], nosign["split_index"]]).astype(np.int64),
        "sample_ids": np.concatenate([positive["sample_ids"], unsupported["sample_ids"], nosign["sample_ids"]]).astype(str),
        "source": np.concatenate([positive["source"], unsupported["source"], nosign["source"]]).astype(str),
        "true_gloss": np.concatenate([positive["true_gloss"], unsupported["true_gloss"], nosign["true_gloss"]]).astype(str),
        "row_kind": np.concatenate([positive["row_kind"], unsupported["row_kind"], nosign["row_kind"]]).astype(str),
    }, config


def _load_primary(seed: int, e5g_run: Path, config: dict[str, Any]):
    weights = e5g_run / "models" / BRANCH / f"seed_{seed}" / "latest.weights.h5"
    if not weights.exists():
        raise FileNotFoundError(f"missing E5-G primary weights: {weights}")
    return _load_weights_model(BRANCH, (96, 258), int(config["class_count"]), float(config["learning_rate"]), weights)


def _predict_seed(seed: int, dataset: dict[str, np.ndarray], e5g_run: Path, gate_run: Path, config: dict[str, Any], batch_size: int) -> dict[str, np.ndarray]:
    primary = _load_primary(seed, e5g_run, config)
    gate = _load_gate(seed, gate_run)
    x = dataset["landmarks"]
    mask = dataset["frame_mask"]
    primary_probs = primary.predict(_inputs_for(BRANCH, x, mask), batch_size=batch_size, verbose=0).astype(np.float32)
    primary_pred = np.argmax(primary_probs, axis=1).astype(np.int64)
    primary_conf = np.max(primary_probs, axis=1).astype(np.float32)
    gate_prob = gate.predict(x, batch_size=batch_size, verbose=0).reshape(-1).astype(np.float32)
    return {
        "primary_probs": primary_probs,
        "primary_pred": primary_pred,
        "primary_conf": primary_conf,
        "gate_prob": gate_prob,
        "gate_threshold": np.asarray([_gate_threshold(seed, gate_run)], dtype=np.float32),
    }


def _class_recall(metrics: dict[str, Any], gloss: str) -> float:
    for row in metrics["per_class"]:
        if row["gloss"] == gloss:
            return 0.0 if row["recall"] is None else float(row["recall"])
    return 0.0


def _runbook(args: argparse.Namespace) -> str:
    return "\n".join([
        "# E5-H Clean 7-Class Routed Simulation",
        "",
        "Offline-only routed validation for the E5-G clean 7-class model.",
        "",
        "```powershell",
        'cd "F:\\ASL DATASET\\5. Apphear3"',
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_h_clean_7_routed_sim run --output "{args.output}"',
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_h_clean_7_routed_sim check --run-dir "{args.output}" --require-metrics',
        "```",
    ])


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    for relative in ("metrics", "predictions", "logs"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    commit_classes = [str(item).upper() for item in args.commit_classes] if args.commit_classes else None
    dataset, config = _combined_dataset(args.e5g_run, args.e5d_run, args.nosign_run, commit_classes)
    selected = list(commit_classes or config["classes"])
    seeds = [int(seed) for seed in args.seeds]
    seed_predictions = {
        seed: _predict_seed(seed, dataset, args.e5g_run, args.gate_run, config, int(args.batch_size))
        for seed in seeds
    }
    selected_threshold, grid_rows = _select_threshold(seed_predictions, dataset, config, selected, args)
    test_mask = dataset["split_index"] == SPLITS["test"]
    val_mask = dataset["split_index"] == SPLITS["val"]
    seed_results: dict[str, Any] = {}
    prediction_rows: list[dict[str, Any]] = []
    for seed, preds in seed_predictions.items():
        final = _apply_policy(preds, config, selected, selected_threshold)
        seed_results[str(seed)] = {
            "gate_threshold": float(preds["gate_threshold"][0]),
            "primary_confidence_threshold": selected_threshold,
            "validation": _evaluate(dataset, final, selected, val_mask),
            "test": _evaluate(dataset, final, selected, test_mask),
        }
        classes = list(config["classes"])
        for idx in np.where(test_mask)[0].tolist():
            prediction_rows.append({
                "seed": seed,
                "sample_id": str(dataset["sample_ids"][idx]),
                "source": str(dataset["source"][idx]),
                "row_kind": str(dataset["row_kind"][idx]),
                "true_gloss": str(dataset["true_gloss"][idx]),
                "gate_probability": float(preds["gate_prob"][idx]),
                "gate_threshold": float(preds["gate_threshold"][0]),
                "primary_pred": classes[int(preds["primary_pred"][idx])],
                "primary_confidence": float(preds["primary_conf"][idx]),
                "final_pred": str(final[idx]),
                "accepted": bool(final[idx] != "REJECT"),
                "correct": bool(final[idx] == dataset["true_gloss"][idx]),
            })
    _write_csv(output / "metrics" / "validation_policy_grid.csv", grid_rows, ["primary_confidence", "mean_accepted_precision", "min_accepted_precision", "mean_positive_coverage", "min_positive_coverage", "max_unsupported_false_commit_rate", "max_no_sign_false_commit_rate", "min_class_recall", "passes_gate"])
    _write_csv(output / "predictions" / "test_predictions.csv", prediction_rows, ["seed", "sample_id", "source", "row_kind", "true_gloss", "gate_probability", "gate_threshold", "primary_pred", "primary_confidence", "final_pred", "accepted", "correct"])
    tests = [payload["test"] for payload in seed_results.values()]
    summary = {
        "mean_test_accepted_precision": float(np.mean([m["accepted_precision"] for m in tests])),
        "min_test_accepted_precision": float(np.min([m["accepted_precision"] for m in tests])),
        "mean_test_positive_coverage": float(np.mean([m["positive_coverage"] for m in tests])),
        "min_test_positive_coverage": float(np.min([m["positive_coverage"] for m in tests])),
        "max_test_unsupported_false_commit_rate": float(np.max([m["unsupported_false_commit_rate"] for m in tests])),
        "max_test_no_sign_false_commit_rate": float(np.max([m["no_sign_false_commit_rate"] for m in tests])),
        "min_test_class_recall": float(np.min([min([_class_recall(m, g) for g in selected] or [0.0]) for m in tests])),
        "mean_test_class_recall": float(np.mean([_class_recall(m, g) for m in tests for g in selected])),
    }
    gate = {
        "accepted_precision_min": float(args.accepted_precision_min),
        "positive_coverage_min": float(args.positive_coverage_min),
        "unsupported_false_commit_rate_max": float(args.unsupported_false_commit_rate_max),
        "no_sign_false_commit_rate_max": float(args.no_sign_false_commit_rate_max),
        "min_class_recall_min": float(args.min_class_recall_min),
    }
    passed = bool(
        summary["min_test_accepted_precision"] >= gate["accepted_precision_min"]
        and summary["min_test_positive_coverage"] >= gate["positive_coverage_min"]
        and summary["max_test_unsupported_false_commit_rate"] <= gate["unsupported_false_commit_rate_max"]
        and summary["max_test_no_sign_false_commit_rate"] <= gate["no_sign_false_commit_rate_max"]
        and summary["min_test_class_recall"] >= gate["min_class_recall_min"]
    )
    unsupported_classes = sorted(set(dataset["true_gloss"][dataset["row_kind"] == "unsupported"].tolist()))
    result = {
        "experiment": "e5_h_clean_7_routed_sim_v1",
        "run_dir": str(output.resolve()),
        "e5g_run": str(args.e5g_run.resolve()),
        "e5d_unsupported_run": str(args.e5d_run.resolve()),
        "gate_run": str(args.gate_run.resolve()),
        "nosign_run": str(args.nosign_run.resolve()),
        "selected_primary_subset": selected,
        "trained_e5g_classes": list(config["classes"]),
        "unsupported_pressure_classes": unsupported_classes,
        "seeds": seeds,
        "dataset": {
            "rows": int(dataset["landmarks"].shape[0]),
            "split_counts": dict(sorted(Counter(dataset["split_index"].tolist()).items())),
            "row_kind_counts": dict(sorted(Counter(dataset["row_kind"].tolist()).items())),
            "source_counts": dict(sorted(Counter(dataset["source"].tolist()).items())),
        },
        "selected_policy": {"primary_confidence": selected_threshold},
        "gate": gate,
        "seed_results": seed_results,
        "summary": summary,
        "passed": passed,
        "decision": "clean_7_routed_candidate" if passed else "clean_7_routed_no_go_or_needs_subset_threshold_repair",
        "warnings": [
            "Offline simulation only; no Android/export authorized.",
            "Uses E5-G clean 7-class model plus E4-AG no-sign gate.",
            "Unsupported signs are pressure rows from E5-D, not a complete real-world OOV set.",
            "Passing this gate would authorize review of model export readiness, not production replacement.",
        ],
    }
    _write_json(output / "metrics" / "routed_sim_metrics.json", result)
    _write_json(output / "logs" / "run_summary.json", {"passed": passed, "summary": summary, "selected_policy": result["selected_policy"]})
    (output / "README_RUN.md").write_text(_runbook(args), encoding="utf-8")
    return result


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = [
        "metrics/routed_sim_metrics.json",
        "metrics/validation_policy_grid.csv",
        "predictions/test_predictions.csv",
        "logs/run_summary.json",
        "README_RUN.md",
    ]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if args.require_metrics and (run_dir / "metrics" / "routed_sim_metrics.json").exists():
        metrics = _load_json(run_dir / "metrics" / "routed_sim_metrics.json", "E5-H metrics")
        if metrics.get("experiment") != "e5_h_clean_7_routed_sim_v1":
            errors.append("unexpected experiment id")
        if not isinstance(metrics.get("passed"), bool):
            errors.append("metrics missing boolean passed field")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E5-H clean 7-class routed simulation")
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run")
    run_p.add_argument("--e5g-run", type=Path, default=DEFAULT_E5G_RUN)
    run_p.add_argument("--e5d-run", type=Path, default=DEFAULT_E5D_RUN)
    run_p.add_argument("--gate-run", type=Path, default=DEFAULT_GATE_RUN)
    run_p.add_argument("--nosign-run", type=Path, default=DEFAULT_NOSIGN_RUN)
    run_p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_p.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    run_p.add_argument("--batch-size", type=int, default=32)
    run_p.add_argument("--primary-confidences", nargs="+", type=float, default=[0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.93, 0.95, 0.97, 0.98, 0.99, 0.995])
    run_p.add_argument("--commit-classes", nargs="*", help="Optional subset of E5-G classes allowed to commit; other E5-G rows become unsupported pressure.")
    run_p.add_argument("--accepted-precision-min", type=float, default=0.90)
    run_p.add_argument("--positive-coverage-min", type=float, default=0.65)
    run_p.add_argument("--unsupported-false-commit-rate-max", type=float, default=0.20)
    run_p.add_argument("--no-sign-false-commit-rate-max", type=float, default=0.05)
    run_p.add_argument("--min-class-recall-min", type=float, default=0.55)
    check_p = sub.add_parser("check")
    check_p.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    check_p.add_argument("--require-metrics", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e5-h] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
