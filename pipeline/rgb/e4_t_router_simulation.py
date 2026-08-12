"""E4-T offline primary-router simulation.

Loads the E4-S stable-primary model and evaluates whether confidence/margin/router rules
can accept stable signs while rejecting the withheld SORRY confusion holdout. Experiment-only:
no Android assets, production recognizer files, or model exports are modified.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.rgb.e3_b4_landmark_temporal import _inputs_for, _load_weights_model

DEFAULT_SOURCE_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_t_router_simulation_01")
SPLITS = {"train": 0, "val": 1, "test": 2}
BRANCH = "conv1d_baseline"
POLICY_SPLIT = "test"


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


def _load_config(source_run: Path) -> dict[str, Any]:
    path = source_run / "pilot_config.json"
    if not path.exists():
        raise FileNotFoundError(f"missing E4-S config: {path}")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("experiment") != "e4_s_stable_primary_4sign_v1":
        raise ValueError("E4-T requires an E4-S stable-primary source run")
    return config


def _load_dataset(path: Path) -> dict[str, np.ndarray]:
    if not path.exists():
        raise FileNotFoundError(f"missing dataset: {path}")
    data = np.load(path, allow_pickle=False)
    out = {
        "landmarks": data["landmarks"].astype(np.float32),
        "frame_mask": data["frame_mask"].astype(bool),
        "split_index": data["split_index"].astype(np.int64),
        "sample_ids": np.asarray(data["sample_ids"]).astype(str),
    }
    if "y" in data.files:
        out["y"] = data["y"].astype(np.int64)
    return out


def _top_stats(probs: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    order = np.argsort(probs, axis=1)
    top1 = order[:, -1]
    top1_conf = probs[np.arange(probs.shape[0]), top1]
    top2_conf = probs[np.arange(probs.shape[0]), order[:, -2]]
    return top1, top1_conf, top1_conf - top2_conf


def _predict_source(source_run: Path, output: Path, config: dict[str, Any]) -> dict[str, Any]:
    dataset = _load_dataset(source_run / "dataset" / "landmark_features.npz")
    oov = _load_dataset(source_run / "dataset" / "oov_confusion_holdout.npz")
    classes = list(config["classes"])
    seeds = [int(seed) for seed in config["seeds"]]
    output.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "source_run": str(source_run.resolve()),
        "classes": classes,
        "seeds": seeds,
        "active_rows": int(dataset["landmarks"].shape[0]),
        "oov_rows": int(oov["landmarks"].shape[0]),
        "seeds_summary": {},
    }
    for seed in seeds:
        weights = source_run / "models" / BRANCH / f"seed_{seed}" / "latest.weights.h5"
        if not weights.exists():
            raise FileNotFoundError(f"missing latest E4-S weights: {weights}")
        model = _load_weights_model(BRANCH, (96, 258), int(config["class_count"]), float(config["learning_rate"]), weights)
        active_probs = model.predict(_inputs_for(BRANCH, dataset["landmarks"], dataset["frame_mask"]), batch_size=int(config["batch_size"]), verbose=0)
        oov_probs = model.predict(_inputs_for(BRANCH, oov["landmarks"], oov["frame_mask"]), batch_size=int(config["batch_size"]), verbose=0)
        np.savez_compressed(
            output / f"seed_{seed}_probs.npz",
            active_probs=active_probs.astype(np.float32),
            active_y=dataset["y"].astype(np.int64),
            active_split_index=dataset["split_index"].astype(np.int64),
            active_sample_ids=dataset["sample_ids"].astype(str),
            oov_probs=oov_probs.astype(np.float32),
            oov_split_index=oov["split_index"].astype(np.int64),
            oov_sample_ids=oov["sample_ids"].astype(str),
        )
        active_pred, active_conf, active_margin = _top_stats(active_probs)
        oov_pred, oov_conf, oov_margin = _top_stats(oov_probs)
        summary["seeds_summary"][str(seed)] = {
            "active_test_accuracy": float(np.mean(active_pred[dataset["split_index"] == SPLITS["test"]] == dataset["y"][dataset["split_index"] == SPLITS["test"]])),
            "active_test_mean_confidence": float(np.mean(active_conf[dataset["split_index"] == SPLITS["test"]])),
            "active_test_mean_margin": float(np.mean(active_margin[dataset["split_index"] == SPLITS["test"]])),
            "oov_test_mean_confidence": float(np.mean(oov_conf[oov["split_index"] == SPLITS["test"]])),
            "oov_test_mean_margin": float(np.mean(oov_margin[oov["split_index"] == SPLITS["test"]])),
            "oov_test_predicted_class_counts": dict(sorted(Counter(classes[int(v)] for v in oov_pred[oov["split_index"] == SPLITS["test"]]).items())),
        }
    return summary


def _evaluate_policy(
    active_probs: np.ndarray,
    active_y: np.ndarray,
    active_split: np.ndarray,
    oov_probs: np.ndarray,
    oov_split: np.ndarray,
    classes: list[str],
    confidence: float,
    margin: float,
    good_confidence: float | None,
) -> dict[str, Any]:
    active_pred, active_conf, active_margin = _top_stats(active_probs)
    oov_pred, oov_conf, oov_margin = _top_stats(oov_probs)
    active_mask = active_split == SPLITS[POLICY_SPLIT]
    oov_mask = oov_split == SPLITS[POLICY_SPLIT]

    active_accept = active_mask & (active_conf >= confidence) & (active_margin >= margin)
    oov_accept = oov_mask & (oov_conf >= confidence) & (oov_margin >= margin)
    if good_confidence is not None:
        good_id = classes.index("GOOD")
        active_accept &= (active_pred != good_id) | (active_conf >= good_confidence)
        oov_accept &= (oov_pred != good_id) | (oov_conf >= good_confidence)

    active_correct_accept = int(np.sum(active_accept & (active_pred == active_y)))
    active_wrong_accept = int(np.sum(active_accept & (active_pred != active_y)))
    oov_false_accept = int(np.sum(oov_accept))
    all_accept = active_correct_accept + active_wrong_accept + oov_false_accept
    active_total = int(np.sum(active_mask))
    oov_total = int(np.sum(oov_mask))
    predicted_counts = Counter(classes[int(v)] for v in active_pred[active_accept])
    oov_counts = Counter(classes[int(v)] for v in oov_pred[oov_accept])
    return {
        "confidence": float(confidence),
        "margin": float(margin),
        "good_confidence": None if good_confidence is None else float(good_confidence),
        "active_total": active_total,
        "oov_total": oov_total,
        "active_accepts": int(np.sum(active_accept)),
        "active_correct_accepts": active_correct_accept,
        "active_wrong_accepts": active_wrong_accept,
        "oov_false_accepts": oov_false_accept,
        "active_coverage": float(np.sum(active_accept) / max(active_total, 1)),
        "active_accepted_accuracy": float(active_correct_accept / max(int(np.sum(active_accept)), 1)),
        "accepted_precision_with_oov": float(active_correct_accept / max(all_accept, 1)),
        "oov_false_accept_rate": float(oov_false_accept / max(oov_total, 1)),
        "active_predicted_accept_counts": dict(sorted(predicted_counts.items())),
        "oov_predicted_accept_counts": dict(sorted(oov_counts.items())),
    }


def _candidate_grid(args: argparse.Namespace) -> list[tuple[float, float, float | None]]:
    confidences = [float(v) for v in args.confidences]
    margins = [float(v) for v in args.margins]
    good_confidences = [None] + [float(v) for v in args.good_confidences]
    return [(conf, margin, good_conf) for conf in confidences for margin in margins for good_conf in good_confidences]


def run(args: argparse.Namespace) -> dict[str, Any]:
    source_run = args.source_run
    output = args.output
    for relative in ("logs", "metrics", "predictions"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    config = _load_config(source_run)
    prediction_summary = _predict_source(source_run, output / "predictions", config)
    classes = list(config["classes"])
    policies: list[dict[str, Any]] = []
    seed_rollups: dict[str, Any] = {}
    for seed in config["seeds"]:
        seed = int(seed)
        probs = np.load(output / "predictions" / f"seed_{seed}_probs.npz", allow_pickle=False)
        seed_rows = []
        for conf, margin, good_conf in _candidate_grid(args):
            seed_rows.append(_evaluate_policy(
                probs["active_probs"],
                probs["active_y"],
                probs["active_split_index"],
                probs["oov_probs"],
                probs["oov_split_index"],
                classes,
                conf,
                margin,
                good_conf,
            ))
        seed_rows = sorted(seed_rows, key=lambda row: (-row["accepted_precision_with_oov"], -row["active_coverage"], row["oov_false_accept_rate"], row["confidence"], row["margin"]))
        seed_rollups[str(seed)] = seed_rows[:20]
        for row in seed_rows:
            policies.append({"seed": seed, **row})

    grouped: dict[tuple[float, float, float | None], list[dict[str, Any]]] = {}
    for row in policies:
        key = (float(row["confidence"]), float(row["margin"]), row["good_confidence"])
        grouped.setdefault(key, []).append(row)
    aggregate_rows = []
    for (confidence, margin, good_confidence), rows in grouped.items():
        if len(rows) != len(config["seeds"]):
            continue
        aggregate_rows.append({
            "confidence": confidence,
            "margin": margin,
            "good_confidence": good_confidence,
            "mean_accepted_precision_with_oov": float(np.mean([row["accepted_precision_with_oov"] for row in rows])),
            "min_accepted_precision_with_oov": float(np.min([row["accepted_precision_with_oov"] for row in rows])),
            "mean_active_coverage": float(np.mean([row["active_coverage"] for row in rows])),
            "min_active_coverage": float(np.min([row["active_coverage"] for row in rows])),
            "mean_oov_false_accept_rate": float(np.mean([row["oov_false_accept_rate"] for row in rows])),
            "max_oov_false_accept_rate": float(np.max([row["oov_false_accept_rate"] for row in rows])),
            "mean_active_accepted_accuracy": float(np.mean([row["active_accepted_accuracy"] for row in rows])),
            "max_active_wrong_accepts": int(np.max([row["active_wrong_accepts"] for row in rows])),
        })
    aggregate_rows = sorted(
        aggregate_rows,
        key=lambda row: (
            -row["min_accepted_precision_with_oov"],
            -row["min_active_coverage"],
            row["max_oov_false_accept_rate"],
            row["confidence"],
            row["margin"],
            0.0 if row["good_confidence"] is None else row["good_confidence"],
        ),
    )
    selected = aggregate_rows[0] if aggregate_rows else None
    gate = {
        "accepted_precision_with_oov_min": float(args.accepted_precision_min),
        "active_coverage_min": float(args.active_coverage_min),
        "oov_false_accept_rate_max": float(args.oov_false_accept_rate_max),
    }
    passed = bool(
        selected
        and selected["min_accepted_precision_with_oov"] >= gate["accepted_precision_with_oov_min"]
        and selected["min_active_coverage"] >= gate["active_coverage_min"]
        and selected["max_oov_false_accept_rate"] <= gate["oov_false_accept_rate_max"]
    )
    result = {
        "experiment": "e4_t_offline_router_simulation_v1",
        "run_dir": str(output.resolve()),
        "source_run": str(source_run.resolve()),
        "classes": classes,
        "oov_holdout": config.get("excluded_oov_confusion_classes", []),
        "prediction_summary": prediction_summary,
        "gate": gate,
        "selected_policy": selected,
        "top_aggregate_policies": aggregate_rows[:25],
        "top_seed_policies": seed_rollups,
        "passed": passed,
        "decision": "router_policy_candidate_ready_for_review" if passed else "simple_threshold_router_no_go",
        "warnings": [
            "This is offline window-level router simulation only.",
            "The OOV/confusion holdout contains SORRY only, not a complete unknown/no-sign set.",
            "Passing this gate would authorize a broader router simulation, not Android deployment.",
        ],
    }
    _write_json(output / "metrics" / "router_metrics.json", result)
    _write_json(output / "logs" / "run_summary.json", {"passed": passed, "selected_policy": selected})
    fields = [
        "confidence",
        "margin",
        "good_confidence",
        "mean_accepted_precision_with_oov",
        "min_accepted_precision_with_oov",
        "mean_active_coverage",
        "min_active_coverage",
        "mean_oov_false_accept_rate",
        "max_oov_false_accept_rate",
        "mean_active_accepted_accuracy",
        "max_active_wrong_accepts",
    ]
    _write_csv(output / "metrics" / "aggregate_policy_grid.csv", aggregate_rows, fields)
    return result


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["metrics/router_metrics.json", "metrics/aggregate_policy_grid.csv", "logs/run_summary.json"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if args.require_predictions and not list((run_dir / "predictions").glob("seed_*_probs.npz")):
        errors.append("missing prediction probability files")
    if args.require_metrics and (run_dir / "metrics" / "router_metrics.json").exists():
        metrics = json.loads((run_dir / "metrics" / "router_metrics.json").read_text(encoding="utf-8"))
        if metrics.get("experiment") != "e4_t_offline_router_simulation_v1":
            errors.append("unexpected experiment id")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-T offline primary-router simulation")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    run_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_parser.add_argument("--confidences", nargs="+", type=float, default=[0.50, 0.70, 0.80, 0.90, 0.95, 0.98, 0.99, 0.995, 0.999])
    run_parser.add_argument("--margins", nargs="+", type=float, default=[0.00, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.98])
    run_parser.add_argument("--good-confidences", nargs="+", type=float, default=[0.95, 0.98, 0.99, 0.995, 0.999])
    run_parser.add_argument("--accepted-precision-min", type=float, default=0.95)
    run_parser.add_argument("--active-coverage-min", type=float, default=0.80)
    run_parser.add_argument("--oov-false-accept-rate-max", type=float, default=0.05)

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--require-metrics", action="store_true")
    check_parser.add_argument("--require-predictions", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-t] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
