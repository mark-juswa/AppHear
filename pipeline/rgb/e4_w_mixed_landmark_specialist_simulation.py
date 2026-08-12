"""E4-W mixed primary + GOOD/SORRY landmark specialist simulation.

Replays the E4-S stable-primary recognizer and routes primary GOOD predictions
through the passing E4-V landmark binary specialist. Experiment-only: no Android
assets, TFLite exports, production recognizer files, or source datasets are modified.
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

DEFAULT_PRIMARY_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01")
DEFAULT_SPECIALIST_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_w_mixed_landmark_specialist_simulation_01")
PRIMARY_BRANCH = "conv1d_baseline"
SPECIALIST_BRANCH = "landmark_binary_control"
SPLITS = {"train": 0, "val": 1, "test": 2}
FINAL_CLASSES = ["GOOD", "HELLO", "HAVE", "KNOW", "SORRY"]
SPECIALIST_CLASSES = ["GOOD", "SORRY"]


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


def _load_json(path: Path, description: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing {description}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_npz(path: Path, description: str) -> dict[str, np.ndarray]:
    if not path.exists():
        raise FileNotFoundError(f"missing {description}: {path}")
    data = np.load(path, allow_pickle=False)
    out: dict[str, np.ndarray] = {
        "landmarks": data["landmarks"].astype(np.float32),
        "frame_mask": data["frame_mask"].astype(bool),
        "split_index": data["split_index"].astype(np.int64),
        "sample_ids": np.asarray(data["sample_ids"]).astype(str),
    }
    if "y" in data.files:
        out["y"] = data["y"].astype(np.int64)
    return out


def _predict(branch: str, model: Any, x: np.ndarray, frame_mask: np.ndarray, batch_size: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    probs = model.predict(_inputs_for(branch, x, frame_mask), batch_size=batch_size, verbose=0)
    pred = np.argmax(probs, axis=1).astype(np.int64)
    conf = np.max(probs, axis=1).astype(np.float32)
    return probs.astype(np.float32), pred, conf


def _confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, class_count: int) -> list[list[int]]:
    return [[int(np.sum((y_true == true) & (y_pred == guess))) for guess in range(class_count)] for true in range(class_count)]


def _per_class(y_true: np.ndarray, y_pred: np.ndarray, classes: list[str]) -> list[dict[str, Any]]:
    rows = []
    for cid, gloss in enumerate(classes):
        mask = y_true == cid
        rows.append({
            "gloss": gloss,
            "count": int(np.sum(mask)),
            "correct": int(np.sum(mask & (y_pred == cid))),
            "recall": float(np.mean(y_pred[mask] == cid)) if np.any(mask) else None,
        })
    return rows


def _evaluate(y_true: np.ndarray, y_pred: np.ndarray, classes: list[str]) -> dict[str, Any]:
    return {
        "accuracy": float(np.mean(y_pred == y_true)) if y_true.size else 0.0,
        "count": int(y_true.size),
        "predicted_class_counts": dict(sorted(Counter(classes[int(cid)] for cid in y_pred).items())),
        "per_class": _per_class(y_true, y_pred, classes),
        "confusion_matrix": _confusion_matrix(y_true, y_pred, len(classes)),
    }


def _class_recall(eval_result: dict[str, Any], gloss: str) -> float:
    for row in eval_result["per_class"]:
        if row["gloss"] == gloss:
            return 0.0 if row["recall"] is None else float(row["recall"])
    return 0.0


def _build_test_set(primary_run: Path) -> dict[str, np.ndarray]:
    active = _load_npz(primary_run / "dataset" / "landmark_features.npz", "E4-S active tensor")
    oov = _load_npz(primary_run / "dataset" / "oov_confusion_holdout.npz", "E4-S OOV holdout tensor")
    active_test = active["split_index"] == SPLITS["test"]
    oov_test = oov["split_index"] == SPLITS["test"]
    if not np.any(active_test):
        raise ValueError("E4-S active tensor has no test rows")
    if not np.any(oov_test):
        raise ValueError("E4-S OOV holdout has no test rows")
    return {
        "landmarks": np.concatenate([active["landmarks"][active_test], oov["landmarks"][oov_test]], axis=0).astype(np.float32),
        "frame_mask": np.concatenate([active["frame_mask"][active_test], oov["frame_mask"][oov_test]], axis=0).astype(bool),
        "y_true": np.concatenate([active["y"][active_test], np.full(int(np.sum(oov_test)), FINAL_CLASSES.index("SORRY"), dtype=np.int64)], axis=0),
        "sample_ids": np.concatenate([active["sample_ids"][active_test], oov["sample_ids"][oov_test]], axis=0).astype(str),
        "source": np.concatenate([np.full(int(np.sum(active_test)), "e4_s_active_test"), np.full(int(np.sum(oov_test)), "e4_s_oov_sorry_test")]).astype(str),
    }


def _simulate_seed(
    seed: int,
    primary_run: Path,
    specialist_run: Path,
    primary_config: dict[str, Any],
    specialist_config: dict[str, Any],
    test_set: dict[str, np.ndarray],
    output: Path,
) -> dict[str, Any]:
    primary_weights = primary_run / "models" / PRIMARY_BRANCH / f"seed_{seed}" / "latest.weights.h5"
    specialist_weights = specialist_run / "models" / SPECIALIST_BRANCH / f"seed_{seed}" / "latest.weights.h5"
    if not primary_weights.exists():
        raise FileNotFoundError(f"missing primary weights: {primary_weights}")
    if not specialist_weights.exists():
        raise FileNotFoundError(f"missing specialist weights: {specialist_weights}")

    primary = _load_weights_model(PRIMARY_BRANCH, (96, 258), len(primary_config["classes"]), float(primary_config["learning_rate"]), primary_weights)
    specialist = _load_weights_model("conv1d_baseline", (96, 258), len(SPECIALIST_CLASSES), float(specialist_config["learning_rate"]), specialist_weights)
    x = test_set["landmarks"]
    frame_mask = test_set["frame_mask"]
    y_true = test_set["y_true"]
    primary_probs, primary_pred, primary_conf = _predict(PRIMARY_BRANCH, primary, x, frame_mask, int(primary_config["batch_size"]))
    primary_final = primary_pred.copy()
    route_mask = np.asarray([primary_config["classes"][int(cid)] == "GOOD" for cid in primary_pred], dtype=bool)
    specialist_pred = np.full(y_true.shape, -1, dtype=np.int64)
    specialist_conf = np.zeros(y_true.shape, dtype=np.float32)
    mixed_pred = primary_final.copy()
    if np.any(route_mask):
        _specialist_probs, routed_pred, routed_conf = _predict("conv1d_baseline", specialist, x[route_mask], frame_mask[route_mask], int(specialist_config["batch_size"]))
        routed_indices = np.where(route_mask)[0]
        specialist_pred[routed_indices] = routed_pred
        specialist_conf[routed_indices] = routed_conf
        for index, specialist_class in zip(routed_indices, routed_pred):
            mixed_pred[index] = FINAL_CLASSES.index(SPECIALIST_CLASSES[int(specialist_class)])

    primary_eval = _evaluate(y_true, primary_final, FINAL_CLASSES)
    mixed_eval = _evaluate(y_true, mixed_pred, FINAL_CLASSES)
    true_good = y_true == FINAL_CLASSES.index("GOOD")
    false_sorry_corrections = int(np.sum(true_good & route_mask & (mixed_pred == FINAL_CLASSES.index("SORRY"))))
    routed_rows = []
    for i, sample_id in enumerate(test_set["sample_ids"].tolist()):
        routed_rows.append({
            "seed": seed,
            "sample_id": sample_id,
            "source": test_set["source"][i],
            "true_gloss": FINAL_CLASSES[int(y_true[i])],
            "primary_pred": FINAL_CLASSES[int(primary_final[i])],
            "primary_confidence": float(primary_conf[i]),
            "routed_to_specialist": bool(route_mask[i]),
            "specialist_pred": "" if specialist_pred[i] < 0 else SPECIALIST_CLASSES[int(specialist_pred[i])],
            "specialist_confidence": "" if specialist_pred[i] < 0 else float(specialist_conf[i]),
            "mixed_pred": FINAL_CLASSES[int(mixed_pred[i])],
            "mixed_correct": bool(mixed_pred[i] == y_true[i]),
        })
    _write_csv(
        output / "predictions" / f"seed_{seed}_mixed_predictions.csv",
        routed_rows,
        ["seed", "sample_id", "source", "true_gloss", "primary_pred", "primary_confidence", "routed_to_specialist", "specialist_pred", "specialist_confidence", "mixed_pred", "mixed_correct"],
    )
    np.savez_compressed(
        output / "predictions" / f"seed_{seed}_probs_and_preds.npz",
        primary_probs=primary_probs,
        primary_pred=primary_pred,
        mixed_pred=mixed_pred,
        y_true=y_true,
        route_mask=route_mask,
        specialist_pred=specialist_pred,
    )
    active_mask = test_set["source"] == "e4_s_active_test"
    oov_mask = test_set["source"] == "e4_s_oov_sorry_test"
    return {
        "seed": seed,
        "primary_alone": primary_eval,
        "mixed": mixed_eval,
        "active_known_accuracy": float(np.mean(mixed_pred[active_mask] == y_true[active_mask])),
        "primary_active_known_accuracy": float(np.mean(primary_final[active_mask] == y_true[active_mask])),
        "oov_sorry_recall": float(np.mean(mixed_pred[oov_mask] == y_true[oov_mask])),
        "primary_oov_sorry_recall": float(np.mean(primary_final[oov_mask] == y_true[oov_mask])),
        "routed_count": int(np.sum(route_mask)),
        "route_rate": float(np.mean(route_mask)),
        "false_sorry_corrections_on_true_good": false_sorry_corrections,
        "false_sorry_correction_rate_on_true_good": float(false_sorry_corrections / max(int(np.sum(true_good)), 1)),
        "accuracy_gain_over_primary": float(mixed_eval["accuracy"] - primary_eval["accuracy"]),
    }


def _summary(seed_results: list[dict[str, Any]]) -> dict[str, Any]:
    mixed_acc = [float(row["mixed"]["accuracy"]) for row in seed_results]
    primary_acc = [float(row["primary_alone"]["accuracy"]) for row in seed_results]
    active = [float(row["active_known_accuracy"]) for row in seed_results]
    sorry = [float(row["oov_sorry_recall"]) for row in seed_results]
    good = [_class_recall(row["mixed"], "GOOD") for row in seed_results]
    gains = [float(row["accuracy_gain_over_primary"]) for row in seed_results]
    false_good = [float(row["false_sorry_correction_rate_on_true_good"]) for row in seed_results]
    return {
        "mean_primary_accuracy": float(np.mean(primary_acc)),
        "mean_mixed_accuracy": float(np.mean(mixed_acc)),
        "min_mixed_accuracy": float(np.min(mixed_acc)),
        "mean_active_known_accuracy": float(np.mean(active)),
        "min_active_known_accuracy": float(np.min(active)),
        "mean_good_recall": float(np.mean(good)),
        "min_good_recall": float(np.min(good)),
        "mean_sorry_recall": float(np.mean(sorry)),
        "min_sorry_recall": float(np.min(sorry)),
        "mean_accuracy_gain_over_primary": float(np.mean(gains)),
        "min_accuracy_gain_over_primary": float(np.min(gains)),
        "max_false_sorry_correction_rate_on_true_good": float(np.max(false_good)),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    for relative in ("logs", "metrics", "predictions"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    primary_config = _load_json(args.primary_run / "pilot_config.json", "E4-S config")
    specialist_config = _load_json(args.specialist_run / "pilot_config.json", "E4-V config")
    if primary_config.get("experiment") != "e4_s_stable_primary_4sign_v1":
        raise ValueError("E4-W requires E4-S stable-primary as --primary-run")
    if specialist_config.get("experiment") != "e4_v_sorry_good_specialist_v1":
        raise ValueError("E4-W requires E4-V GOOD/SORRY specialist as --specialist-run")
    if primary_config.get("classes") != FINAL_CLASSES[:4]:
        raise ValueError("unexpected primary class contract")
    if specialist_config.get("classes") != SPECIALIST_CLASSES:
        raise ValueError("unexpected specialist class contract")
    test_set = _build_test_set(args.primary_run)
    seeds = [int(seed) for seed in args.seeds]
    seed_results = [_simulate_seed(seed, args.primary_run, args.specialist_run, primary_config, specialist_config, test_set, output) for seed in seeds]
    gate = {
        "mixed_accuracy_min": float(args.mixed_accuracy_min),
        "active_known_accuracy_min": float(args.active_known_accuracy_min),
        "good_recall_min": float(args.good_recall_min),
        "sorry_recall_min": float(args.sorry_recall_min),
        "accuracy_gain_over_primary_min": float(args.accuracy_gain_min),
        "false_sorry_correction_rate_on_true_good_max": float(args.false_sorry_good_max),
    }
    summary = _summary(seed_results)
    passed = bool(
        summary["min_mixed_accuracy"] >= gate["mixed_accuracy_min"]
        and summary["min_active_known_accuracy"] >= gate["active_known_accuracy_min"]
        and summary["min_good_recall"] >= gate["good_recall_min"]
        and summary["min_sorry_recall"] >= gate["sorry_recall_min"]
        and summary["min_accuracy_gain_over_primary"] >= gate["accuracy_gain_over_primary_min"]
        and summary["max_false_sorry_correction_rate_on_true_good"] <= gate["false_sorry_correction_rate_on_true_good_max"]
    )
    result = {
        "experiment": "e4_w_mixed_landmark_specialist_simulation_v1",
        "run_dir": str(output.resolve()),
        "primary_run": str(args.primary_run.resolve()),
        "specialist_run": str(args.specialist_run.resolve()),
        "classes": FINAL_CLASSES,
        "seeds": seeds,
        "test_set": {
            "rows": int(test_set["landmarks"].shape[0]),
            "active_known_rows": int(np.sum(test_set["source"] == "e4_s_active_test")),
            "oov_sorry_rows": int(np.sum(test_set["source"] == "e4_s_oov_sorry_test")),
        },
        "gate": gate,
        "seeds_result": {str(row["seed"]): row for row in seed_results},
        "summary": summary,
        "passed": passed,
        "decision": "mixed_landmark_specialist_promising_for_broader_router_simulation" if passed else "mixed_landmark_specialist_no_go_or_needs_more_validation",
        "warnings": [
            "This is offline window-level simulation only.",
            "The specialist is evaluated on a small local same-source GOOD/SORRY proof set; broader signer/source validation remains required.",
            "Passing this gate does not authorize Android integration, TFLite export, or production replacement.",
        ],
    }
    _write_json(output / "metrics" / "mixed_router_metrics.json", result)
    _write_json(output / "logs" / "run_summary.json", {"passed": passed, "summary": summary})
    return result


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["metrics/mixed_router_metrics.json", "logs/run_summary.json"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if args.require_predictions and not list((run_dir / "predictions").glob("seed_*_mixed_predictions.csv")):
        errors.append("missing mixed prediction CSV files")
    if args.require_metrics and (run_dir / "metrics" / "mixed_router_metrics.json").exists():
        metrics = json.loads((run_dir / "metrics" / "mixed_router_metrics.json").read_text(encoding="utf-8"))
        if metrics.get("experiment") != "e4_w_mixed_landmark_specialist_simulation_v1":
            errors.append("unexpected experiment id")
        if not isinstance(metrics.get("passed"), bool):
            errors.append("metrics missing boolean passed field")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-W mixed E4-S primary + E4-V landmark specialist simulation")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--primary-run", type=Path, default=DEFAULT_PRIMARY_RUN)
    run_parser.add_argument("--specialist-run", type=Path, default=DEFAULT_SPECIALIST_RUN)
    run_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    run_parser.add_argument("--mixed-accuracy-min", type=float, default=0.90)
    run_parser.add_argument("--active-known-accuracy-min", type=float, default=0.95)
    run_parser.add_argument("--good-recall-min", type=float, default=0.90)
    run_parser.add_argument("--sorry-recall-min", type=float, default=0.90)
    run_parser.add_argument("--accuracy-gain-min", type=float, default=0.15)
    run_parser.add_argument("--false-sorry-good-max", type=float, default=0.10)

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
        print(f"[rgb/e4-w] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
