"""E5-F reduced-primary routed simulation.

Replays the completed E5-D 15-class landmark model, restricts commits to the
E5-E selected 7-sign primary subset, and places the E4-AG no-sign gate in front
of it. Non-selected E5-D signs are treated as unsupported/OOV pressure rows.

Metrics-only offline simulation: no training, extraction, export, Android
changes, or production asset replacement.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np

from pipeline.rgb.e3_b4_landmark_temporal import _inputs_for, _load_weights_model

DEFAULT_E5D_RUN = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_d_reduced_primary_15sign_01")
DEFAULT_E5E_RUN = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_e_reduced_primary_decision_01")
DEFAULT_GATE_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_ag_low_motion_gate_01")
DEFAULT_NOSIGN_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_ag_hello_like_nosign_expansion_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_f_reduced_primary_routed_sim_01")
BRANCH = "conv1d_baseline"
SPLITS = {"train": 0, "val": 1, "test": 2}
REJECT = "REJECT"
UNSUPPORTED = "UNSUPPORTED_SIGN"
NO_SIGN = "NO_SIGN"


def _load_json(path: Path, description: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing {description}: {path}")
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


def _load_npz(path: Path, description: str) -> dict[str, np.ndarray]:
    if not path.exists():
        raise FileNotFoundError(f"missing {description}: {path}")
    data = np.load(path, allow_pickle=False)
    return {key: data[key] for key in data.files}


def _selected_classes(e5e_run: Path) -> list[str]:
    summary = _load_json(e5e_run / "reports" / "decision_summary.json", "E5-E decision summary")
    classes = [str(item).upper() for item in summary.get("recommended_next_primary_subset", [])]
    if not classes:
        raise ValueError("E5-E summary did not provide recommended_next_primary_subset")
    return classes


def _load_e5d_dataset(e5d_run: Path, selected: list[str]) -> dict[str, np.ndarray]:
    config = _load_json(e5d_run / "pilot_config.json", "E5-D config")
    data = _load_npz(e5d_run / "dataset" / "landmark_features.npz", "E5-D landmark tensor")
    classes = list(config["classes"])
    y_raw = data["y"].astype(np.int64)
    glosses = np.asarray([classes[int(y)] for y in y_raw]).astype(str)
    selected_set = set(selected)
    row_kind = np.asarray(["positive" if g in selected_set else "unsupported" for g in glosses]).astype(str)
    return {
        "landmarks": data["landmarks"].astype(np.float32),
        "frame_mask": data["frame_mask"].astype(bool),
        "split_index": data["split_index"].astype(np.int64),
        "sample_ids": np.asarray(data["sample_ids"]).astype(str),
        "source": np.asarray(["e5d_positive_or_unsupported"] * int(data["landmarks"].shape[0])).astype(str),
        "true_gloss": glosses,
        "row_kind": row_kind,
        "e5d_classes": np.asarray(classes).astype(str),
        "class_count": np.asarray([len(classes)], dtype=np.int64),
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


def _combined_dataset(e5d_run: Path, nosign_run: Path, selected: list[str]) -> dict[str, np.ndarray]:
    e5d = _load_e5d_dataset(e5d_run, selected)
    nosign = _load_nosign_dataset(nosign_run)
    return {
        "landmarks": np.concatenate([e5d["landmarks"], nosign["landmarks"]], axis=0).astype(np.float32),
        "frame_mask": np.concatenate([e5d["frame_mask"], nosign["frame_mask"]], axis=0).astype(bool),
        "split_index": np.concatenate([e5d["split_index"], nosign["split_index"]]).astype(np.int64),
        "sample_ids": np.concatenate([e5d["sample_ids"], nosign["sample_ids"]]).astype(str),
        "source": np.concatenate([e5d["source"], nosign["source"]]).astype(str),
        "true_gloss": np.concatenate([e5d["true_gloss"], nosign["true_gloss"]]).astype(str),
        "row_kind": np.concatenate([e5d["row_kind"], nosign["row_kind"]]).astype(str),
    }


def _load_primary(seed: int, e5d_run: Path, config: dict[str, Any]):
    weights = e5d_run / "models" / BRANCH / f"seed_{seed}" / "latest.weights.h5"
    if not weights.exists():
        raise FileNotFoundError(f"missing E5-D primary weights: {weights}")
    return _load_weights_model(BRANCH, (96, 258), int(config["class_count"]), float(config["learning_rate"]), weights)


def _load_gate(seed: int, gate_run: Path):
    import tensorflow as tf

    candidates = [
        gate_run / "models" / f"seed_{seed}" / "low_motion_signing_gate.keras",
        gate_run / "models" / f"seed_{seed}" / "temporal_signing_gate.keras",
    ]
    for path in candidates:
        if path.exists():
            return tf.keras.models.load_model(path)
    raise FileNotFoundError(f"missing gate model for seed {seed}: {candidates}")


def _gate_threshold(seed: int, gate_run: Path) -> float:
    metrics = _load_json(gate_run / "metrics" / "low_motion_gate_metrics.json", "E4-AG gate metrics")
    seed_payload = metrics.get("seed_results", {}).get(str(seed), {})
    if "threshold" not in seed_payload:
        raise KeyError(f"missing threshold for seed {seed} in gate metrics")
    return float(seed_payload["threshold"])


def _predict_seed(seed: int, dataset: dict[str, np.ndarray], e5d_run: Path, gate_run: Path, config: dict[str, Any], batch_size: int) -> dict[str, np.ndarray]:
    primary = _load_primary(seed, e5d_run, config)
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


def _apply_policy(preds: dict[str, np.ndarray], config: dict[str, Any], selected: list[str], primary_threshold: float) -> np.ndarray:
    classes = list(config["classes"])
    selected_set = set(selected)
    out = np.asarray([REJECT] * int(preds["primary_pred"].shape[0]), dtype=object)
    gate_accept = preds["gate_prob"] >= float(preds["gate_threshold"][0])
    primary_accept = preds["primary_conf"] >= float(primary_threshold)
    for idx, pred_id in enumerate(preds["primary_pred"].tolist()):
        pred_gloss = classes[int(pred_id)]
        if gate_accept[idx] and primary_accept[idx] and pred_gloss in selected_set:
            out[idx] = pred_gloss
    return out.astype(str)


def _evaluate(dataset: dict[str, np.ndarray], final: np.ndarray, selected: list[str], split_mask: np.ndarray) -> dict[str, Any]:
    true = dataset["true_gloss"][split_mask]
    kind = dataset["row_kind"][split_mask]
    pred = final[split_mask]
    accepted = pred != REJECT
    positive = kind == "positive"
    unsupported = kind == "unsupported"
    no_sign = kind == "no_sign"
    correct_accepts = accepted & positive & (pred == true)
    metrics = {
        "rows": int(true.size),
        "positive_rows": int(np.sum(positive)),
        "unsupported_rows": int(np.sum(unsupported)),
        "no_sign_rows": int(np.sum(no_sign)),
        "accepted": int(np.sum(accepted)),
        "accepted_precision": float(np.sum(correct_accepts) / max(int(np.sum(accepted)), 1)),
        "positive_coverage": float(np.sum(accepted & positive) / max(int(np.sum(positive)), 1)),
        "positive_accuracy_with_rejects": float(np.mean(pred[positive] == true[positive])) if np.any(positive) else 0.0,
        "unsupported_false_commit_rate": float(np.mean(accepted[unsupported])) if np.any(unsupported) else 0.0,
        "no_sign_false_commit_rate": float(np.mean(accepted[no_sign])) if np.any(no_sign) else 0.0,
        "predicted_counts": dict(sorted(Counter(pred.tolist()).items())),
        "per_class": [],
        "false_commit_by_source": {},
    }
    for gloss in selected:
        class_mask = positive & (true == gloss)
        metrics["per_class"].append({
            "gloss": gloss,
            "count": int(np.sum(class_mask)),
            "correct": int(np.sum(class_mask & (pred == gloss))),
            "recall": float(np.mean(pred[class_mask] == gloss)) if np.any(class_mask) else None,
        })
    source = dataset["source"][split_mask]
    for source_name in sorted(set(source.tolist())):
        smask = source == source_name
        bad = smask & (unsupported | no_sign)
        if np.any(bad):
            metrics["false_commit_by_source"][source_name] = {
                "rows": int(np.sum(bad)),
                "false_commits": int(np.sum(accepted[bad])),
                "false_commit_rate": float(np.mean(accepted[bad])),
                "predicted_counts": dict(sorted(Counter(pred[bad].tolist()).items())),
            }
    return metrics


def _class_recall(metrics: dict[str, Any], gloss: str) -> float:
    for row in metrics["per_class"]:
        if row["gloss"] == gloss:
            return 0.0 if row["recall"] is None else float(row["recall"])
    return 0.0


def _grid(args: argparse.Namespace) -> list[float]:
    return [float(x) for x in args.primary_confidences]


def _select_threshold(seed_predictions: dict[int, dict[str, np.ndarray]], dataset: dict[str, np.ndarray], config: dict[str, Any], selected: list[str], args: argparse.Namespace) -> tuple[float, list[dict[str, Any]]]:
    val_mask = dataset["split_index"] == SPLITS["val"]
    rows: list[dict[str, Any]] = []
    for threshold in _grid(args):
        evals = []
        for seed, preds in seed_predictions.items():
            final = _apply_policy(preds, config, selected, threshold)
            evals.append(_evaluate(dataset, final, selected, val_mask))
        row = {
            "primary_confidence": threshold,
            "mean_accepted_precision": float(np.mean([m["accepted_precision"] for m in evals])),
            "min_accepted_precision": float(np.min([m["accepted_precision"] for m in evals])),
            "mean_positive_coverage": float(np.mean([m["positive_coverage"] for m in evals])),
            "min_positive_coverage": float(np.min([m["positive_coverage"] for m in evals])),
            "max_unsupported_false_commit_rate": float(np.max([m["unsupported_false_commit_rate"] for m in evals])),
            "max_no_sign_false_commit_rate": float(np.max([m["no_sign_false_commit_rate"] for m in evals])),
            "min_class_recall": float(np.min([min([_class_recall(m, g) for g in selected] or [0.0]) for m in evals])),
        }
        row["passes_gate"] = bool(
            row["min_accepted_precision"] >= args.accepted_precision_min
            and row["min_positive_coverage"] >= args.positive_coverage_min
            and row["max_unsupported_false_commit_rate"] <= args.unsupported_false_commit_rate_max
            and row["max_no_sign_false_commit_rate"] <= args.no_sign_false_commit_rate_max
            and row["min_class_recall"] >= args.min_class_recall_min
        )
        rows.append(row)
    feasible = [row for row in rows if row["passes_gate"]]
    ranked = sorted(
        feasible or rows,
        key=lambda row: (
            row["passes_gate"],
            row["min_accepted_precision"],
            row["min_positive_coverage"],
            row["min_class_recall"],
            -row["max_unsupported_false_commit_rate"],
            -row["max_no_sign_false_commit_rate"],
        ),
        reverse=True,
    )
    return float(ranked[0]["primary_confidence"]), rows


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    for relative in ("metrics", "predictions", "logs"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    selected = _selected_classes(args.e5e_run)
    config = _load_json(args.e5d_run / "pilot_config.json", "E5-D config")
    dataset = _combined_dataset(args.e5d_run, args.nosign_run, selected)
    seeds = [int(seed) for seed in args.seeds]
    seed_predictions = {
        seed: _predict_seed(seed, dataset, args.e5d_run, args.gate_run, config, int(args.batch_size))
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
            primary_pred = classes[int(preds["primary_pred"][idx])]
            prediction_rows.append({
                "seed": seed,
                "sample_id": str(dataset["sample_ids"][idx]),
                "source": str(dataset["source"][idx]),
                "row_kind": str(dataset["row_kind"][idx]),
                "true_gloss": str(dataset["true_gloss"][idx]),
                "gate_probability": float(preds["gate_prob"][idx]),
                "gate_threshold": float(preds["gate_threshold"][0]),
                "primary_pred": primary_pred,
                "primary_confidence": float(preds["primary_conf"][idx]),
                "final_pred": str(final[idx]),
                "accepted": bool(final[idx] != REJECT),
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
        "mean_test_class_recall": float(mean([_class_recall(m, g) for m in tests for g in selected])),
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
    result = {
        "experiment": "e5_f_reduced_primary_routed_sim_v1",
        "run_dir": str(output.resolve()),
        "e5d_run": str(args.e5d_run.resolve()),
        "e5e_run": str(args.e5e_run.resolve()),
        "gate_run": str(args.gate_run.resolve()),
        "nosign_run": str(args.nosign_run.resolve()),
        "selected_primary_subset": selected,
        "full_e5d_classes": list(config["classes"]),
        "rejected_or_unsupported_e5d_classes": [c for c in config["classes"] if c not in set(selected)],
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
        "decision": "reduced_primary_routed_sim_candidate" if passed else "reduced_primary_routed_sim_no_go_or_needs_threshold_subset_repair",
        "warnings": [
            "Offline simulation only; no Android/export authorized.",
            "Uses E5-D 15-class model with non-selected signs rejected, not a newly trained 7-class model.",
            "GOOD/SORRY specialist is not exercised because SORRY is absent from E5-D primary data; specialist integration remains separate evidence from E4-W/E4-X.",
            "Passing this gate would authorize a cleaner E5-G train/export package only after review, not production replacement.",
        ],
    }
    _write_json(output / "metrics" / "routed_sim_metrics.json", result)
    _write_json(output / "logs" / "run_summary.json", {"passed": passed, "summary": summary, "selected_policy": result["selected_policy"]})
    return result


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = [
        "metrics/routed_sim_metrics.json",
        "metrics/validation_policy_grid.csv",
        "predictions/test_predictions.csv",
        "logs/run_summary.json",
    ]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if args.require_metrics and (run_dir / "metrics" / "routed_sim_metrics.json").exists():
        metrics = _load_json(run_dir / "metrics" / "routed_sim_metrics.json", "E5-F metrics")
        if metrics.get("experiment") != "e5_f_reduced_primary_routed_sim_v1":
            errors.append("unexpected experiment id")
        if not isinstance(metrics.get("passed"), bool):
            errors.append("metrics missing boolean passed field")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E5-F reduced-primary routed simulation")
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run")
    run_p.add_argument("--e5d-run", type=Path, default=DEFAULT_E5D_RUN)
    run_p.add_argument("--e5e-run", type=Path, default=DEFAULT_E5E_RUN)
    run_p.add_argument("--gate-run", type=Path, default=DEFAULT_GATE_RUN)
    run_p.add_argument("--nosign-run", type=Path, default=DEFAULT_NOSIGN_RUN)
    run_p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_p.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    run_p.add_argument("--batch-size", type=int, default=32)
    run_p.add_argument("--primary-confidences", nargs="+", type=float, default=[0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.93, 0.95, 0.97, 0.98, 0.99, 0.995])
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
        print(f"[rgb/e5-f] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
