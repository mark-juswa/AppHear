"""E4-X routed-system validation with no-hand zero-landmark probe.

Loads E4-S primary and E4-V GOOD/SORRY landmark specialist checkpoints, scans
accept/reject thresholds on validation rows, and evaluates the selected policy
on held-out known signs, withheld SORRY, and reviewed N0 no-visible-hand rows
represented as all-zero/no-frame landmark sequences.

Experiment-only: no Android assets, TFLite exports, production recognizer files,
or source datasets are modified.
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
DEFAULT_N0_RUN = Path("artifacts/recognition_upgrade/e2e_c0/n0_capture_06")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_x_routed_system_validation_01")
PRIMARY_BRANCH = "conv1d_baseline"
SPECIALIST_BRANCH = "landmark_binary_control"
SPLITS = {"train": 0, "val": 1, "test": 2}
FINAL_CLASSES = ["GOOD", "HELLO", "HAVE", "KNOW", "SORRY", "NO_SIGN"]
POSITIVE_CLASSES = FINAL_CLASSES[:-1]
SPECIALIST_CLASSES = ["GOOD", "SORRY"]
NO_SIGN_ID = FINAL_CLASSES.index("NO_SIGN")


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


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def _eligible_n0_ids(n0_run: Path, max_rows: int) -> list[str]:
    rows = _read_csv(n0_run / "gold_review.csv")
    eligible = []
    for row in rows:
        if row.get("review_status") != "accepted":
            continue
        if int(row.get("visible_hand_count", "0") or 0) != 0:
            continue
        eligible.append(row["sample_id"])
    if len(eligible) < 2:
        raise ValueError("not enough eligible N0 rows")
    return eligible[:max_rows]


def _build_dataset(primary_run: Path, n0_run: Path, n0_max_rows: int, n0_val_rows: int) -> dict[str, np.ndarray]:
    active = _load_npz(primary_run / "dataset" / "landmark_features.npz", "E4-S active tensor")
    oov = _load_npz(primary_run / "dataset" / "oov_confusion_holdout.npz", "E4-S OOV holdout tensor")
    n0_ids = _eligible_n0_ids(n0_run, n0_max_rows)
    n0_count = len(n0_ids)
    n0_val = min(n0_val_rows, max(1, n0_count // 3))
    n0_split = np.full(n0_count, SPLITS["test"], dtype=np.int64)
    n0_split[:n0_val] = SPLITS["val"]
    n0_x = np.zeros((n0_count, 96, 258), dtype=np.float32)
    n0_frame_mask = np.zeros((n0_count, 96), dtype=bool)

    x = np.concatenate([active["landmarks"], oov["landmarks"], n0_x], axis=0).astype(np.float32)
    frame_mask = np.concatenate([active["frame_mask"], oov["frame_mask"], n0_frame_mask], axis=0).astype(bool)
    y = np.concatenate([
        active["y"],
        np.full(int(oov["landmarks"].shape[0]), POSITIVE_CLASSES.index("SORRY"), dtype=np.int64),
        np.full(n0_count, NO_SIGN_ID, dtype=np.int64),
    ])
    split_index = np.concatenate([active["split_index"], oov["split_index"], n0_split]).astype(np.int64)
    source = np.concatenate([
        np.full(int(active["landmarks"].shape[0]), "e4_s_active"),
        np.full(int(oov["landmarks"].shape[0]), "e4_s_oov_sorry"),
        np.full(n0_count, "e2e_c0_n0_zero_landmark_probe"),
    ]).astype(str)
    sample_ids = np.concatenate([active["sample_ids"], oov["sample_ids"], np.asarray(n0_ids).astype(str)]).astype(str)
    return {"landmarks": x, "frame_mask": frame_mask, "y": y, "split_index": split_index, "source": source, "sample_ids": sample_ids}


def _predict(branch: str, model: Any, x: np.ndarray, frame_mask: np.ndarray, batch_size: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    probs = model.predict(_inputs_for(branch, x, frame_mask), batch_size=batch_size, verbose=0)
    pred = np.argmax(probs, axis=1).astype(np.int64)
    conf = np.max(probs, axis=1).astype(np.float32)
    return probs.astype(np.float32), pred, conf


def _seed_predictions(
    seed: int,
    primary_run: Path,
    specialist_run: Path,
    primary_config: dict[str, Any],
    specialist_config: dict[str, Any],
    dataset: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    primary_weights = primary_run / "models" / PRIMARY_BRANCH / f"seed_{seed}" / "latest.weights.h5"
    specialist_weights = specialist_run / "models" / SPECIALIST_BRANCH / f"seed_{seed}" / "latest.weights.h5"
    if not primary_weights.exists():
        raise FileNotFoundError(f"missing primary weights: {primary_weights}")
    if not specialist_weights.exists():
        raise FileNotFoundError(f"missing specialist weights: {specialist_weights}")
    primary = _load_weights_model(PRIMARY_BRANCH, (96, 258), 4, float(primary_config["learning_rate"]), primary_weights)
    specialist = _load_weights_model("conv1d_baseline", (96, 258), 2, float(specialist_config["learning_rate"]), specialist_weights)
    x = dataset["landmarks"]
    frame_mask = dataset["frame_mask"]
    primary_probs, primary_pred, primary_conf = _predict(PRIMARY_BRANCH, primary, x, frame_mask, int(primary_config["batch_size"]))
    primary_classes = list(primary_config["classes"])
    route_mask = np.asarray([primary_classes[int(cid)] == "GOOD" for cid in primary_pred], dtype=bool)
    specialist_pred = np.full(primary_pred.shape, -1, dtype=np.int64)
    specialist_conf = np.zeros(primary_pred.shape, dtype=np.float32)
    mixed_pred = primary_pred.copy()
    if np.any(route_mask):
        _sp, spred, sconf = _predict("conv1d_baseline", specialist, x[route_mask], frame_mask[route_mask], int(specialist_config["batch_size"]))
        routed_indices = np.where(route_mask)[0]
        specialist_pred[routed_indices] = spred
        specialist_conf[routed_indices] = sconf
        for index, specialist_class in zip(routed_indices, spred):
            mixed_pred[index] = POSITIVE_CLASSES.index(SPECIALIST_CLASSES[int(specialist_class)])
    return {
        "primary_pred": primary_pred,
        "primary_conf": primary_conf,
        "primary_probs": primary_probs,
        "route_mask": route_mask,
        "specialist_pred": specialist_pred,
        "specialist_conf": specialist_conf,
        "mixed_pred": mixed_pred,
    }


def _apply_policy(preds: dict[str, np.ndarray], policy: dict[str, float]) -> np.ndarray:
    accepted = preds["primary_conf"] >= float(policy["primary_confidence"])
    routed = preds["route_mask"]
    accepted &= (~routed) | (preds["specialist_conf"] >= float(policy["specialist_confidence"]))
    final = np.full(preds["mixed_pred"].shape, NO_SIGN_ID, dtype=np.int64)
    final[accepted] = preds["mixed_pred"][accepted]
    return final


def _per_class(y_true: np.ndarray, y_pred: np.ndarray) -> list[dict[str, Any]]:
    rows = []
    for cid, gloss in enumerate(FINAL_CLASSES):
        mask = y_true == cid
        rows.append({
            "gloss": gloss,
            "count": int(np.sum(mask)),
            "correct": int(np.sum(mask & (y_pred == cid))),
            "recall": float(np.mean(y_pred[mask] == cid)) if np.any(mask) else None,
        })
    return rows


def _evaluate_policy(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    positive = y_true != NO_SIGN_ID
    accepted = y_pred != NO_SIGN_ID
    correct_accepts = int(np.sum(accepted & positive & (y_pred == y_true)))
    wrong_positive_accepts = int(np.sum(accepted & positive & (y_pred != y_true)))
    false_no_sign_accepts = int(np.sum(accepted & (y_true == NO_SIGN_ID)))
    total_accepts = int(np.sum(accepted))
    return {
        "rows": int(y_true.size),
        "positive_rows": int(np.sum(positive)),
        "no_sign_rows": int(np.sum(y_true == NO_SIGN_ID)),
        "accepted": total_accepts,
        "accepted_precision": float(correct_accepts / max(total_accepts, 1)),
        "positive_coverage": float(np.sum(accepted & positive) / max(int(np.sum(positive)), 1)),
        "positive_accuracy_with_rejects": float(np.mean(y_pred[positive] == y_true[positive])) if np.any(positive) else 0.0,
        "no_sign_false_commit_rate": float(false_no_sign_accepts / max(int(np.sum(y_true == NO_SIGN_ID)), 1)),
        "correct_accepts": correct_accepts,
        "wrong_positive_accepts": wrong_positive_accepts,
        "false_no_sign_accepts": false_no_sign_accepts,
        "predicted_class_counts": dict(sorted(Counter(FINAL_CLASSES[int(cid)] for cid in y_pred).items())),
        "per_class": _per_class(y_true, y_pred),
    }


def _class_recall(eval_result: dict[str, Any], gloss: str) -> float:
    for row in eval_result["per_class"]:
        if row["gloss"] == gloss:
            return 0.0 if row["recall"] is None else float(row["recall"])
    return 0.0


def _candidate_grid(args: argparse.Namespace) -> list[dict[str, float]]:
    return [{"primary_confidence": float(pc), "specialist_confidence": float(sc)} for pc in args.primary_confidences for sc in args.specialist_confidences]


def _select_policy(seed_payloads: dict[int, dict[str, np.ndarray]], dataset: dict[str, np.ndarray], args: argparse.Namespace) -> tuple[dict[str, float], list[dict[str, Any]]]:
    val = dataset["split_index"] == SPLITS["val"]
    rows = []
    for policy in _candidate_grid(args):
        evals = []
        for seed, preds in seed_payloads.items():
            final = _apply_policy(preds, policy)
            metrics = _evaluate_policy(dataset["y"][val], final[val])
            evals.append(metrics)
        row = {
            **policy,
            "mean_accepted_precision": float(np.mean([m["accepted_precision"] for m in evals])),
            "min_accepted_precision": float(np.min([m["accepted_precision"] for m in evals])),
            "mean_positive_coverage": float(np.mean([m["positive_coverage"] for m in evals])),
            "min_positive_coverage": float(np.min([m["positive_coverage"] for m in evals])),
            "max_no_sign_false_commit_rate": float(np.max([m["no_sign_false_commit_rate"] for m in evals])),
            "mean_sorry_recall": float(np.mean([_class_recall(m, "SORRY") for m in evals])),
            "min_sorry_recall": float(np.min([_class_recall(m, "SORRY") for m in evals])),
        }
        rows.append(row)
    viable = [
        row for row in rows
        if row["min_accepted_precision"] >= args.accepted_precision_min
        and row["min_positive_coverage"] >= args.positive_coverage_min
        and row["max_no_sign_false_commit_rate"] <= args.no_sign_false_commit_rate_max
        and row["min_sorry_recall"] >= args.sorry_recall_min
    ]
    ranked = sorted(
        viable or rows,
        key=lambda row: (
            row in viable,
            row["min_accepted_precision"],
            row["min_positive_coverage"],
            -row["max_no_sign_false_commit_rate"],
            row["min_sorry_recall"],
        ),
        reverse=True,
    )
    return {"primary_confidence": float(ranked[0]["primary_confidence"]), "specialist_confidence": float(ranked[0]["specialist_confidence"])}, rows


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    for relative in ("logs", "metrics", "predictions"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    primary_config = _load_json(args.primary_run / "pilot_config.json", "E4-S config")
    specialist_config = _load_json(args.specialist_run / "pilot_config.json", "E4-V config")
    if primary_config.get("experiment") != "e4_s_stable_primary_4sign_v1":
        raise ValueError("E4-X requires E4-S stable-primary as --primary-run")
    if specialist_config.get("experiment") != "e4_v_sorry_good_specialist_v1":
        raise ValueError("E4-X requires E4-V GOOD/SORRY specialist as --specialist-run")
    dataset = _build_dataset(args.primary_run, args.n0_run, int(args.n0_max_rows), int(args.n0_val_rows))
    seeds = [int(seed) for seed in args.seeds]
    seed_payloads = {seed: _seed_predictions(seed, args.primary_run, args.specialist_run, primary_config, specialist_config, dataset) for seed in seeds}
    selected_policy, policy_rows = _select_policy(seed_payloads, dataset, args)
    val = dataset["split_index"] == SPLITS["val"]
    test = dataset["split_index"] == SPLITS["test"]
    seed_results = {}
    prediction_rows: list[dict[str, Any]] = []
    for seed, preds in seed_payloads.items():
        final = _apply_policy(preds, selected_policy)
        val_metrics = _evaluate_policy(dataset["y"][val], final[val])
        test_metrics = _evaluate_policy(dataset["y"][test], final[test])
        seed_results[str(seed)] = {"validation": val_metrics, "test": test_metrics}
        for idx in np.where(test)[0].tolist():
            prediction_rows.append({
                "seed": seed,
                "sample_id": dataset["sample_ids"][idx],
                "source": dataset["source"][idx],
                "true_gloss": FINAL_CLASSES[int(dataset["y"][idx])],
                "primary_pred": POSITIVE_CLASSES[int(preds["primary_pred"][idx])],
                "primary_confidence": float(preds["primary_conf"][idx]),
                "routed": bool(preds["route_mask"][idx]),
                "specialist_pred": "" if preds["specialist_pred"][idx] < 0 else SPECIALIST_CLASSES[int(preds["specialist_pred"][idx])],
                "specialist_confidence": "" if preds["specialist_pred"][idx] < 0 else float(preds["specialist_conf"][idx]),
                "final_pred": FINAL_CLASSES[int(final[idx])],
                "accepted": bool(final[idx] != NO_SIGN_ID),
                "correct": bool(final[idx] == dataset["y"][idx]),
            })
    _write_csv(output / "predictions" / "test_predictions.csv", prediction_rows, ["seed", "sample_id", "source", "true_gloss", "primary_pred", "primary_confidence", "routed", "specialist_pred", "specialist_confidence", "final_pred", "accepted", "correct"])
    _write_csv(output / "metrics" / "validation_policy_grid.csv", policy_rows, ["primary_confidence", "specialist_confidence", "mean_accepted_precision", "min_accepted_precision", "mean_positive_coverage", "min_positive_coverage", "max_no_sign_false_commit_rate", "mean_sorry_recall", "min_sorry_recall"])
    test_evals = [payload["test"] for payload in seed_results.values()]
    summary = {
        "mean_test_accepted_precision": float(np.mean([m["accepted_precision"] for m in test_evals])),
        "min_test_accepted_precision": float(np.min([m["accepted_precision"] for m in test_evals])),
        "mean_test_positive_coverage": float(np.mean([m["positive_coverage"] for m in test_evals])),
        "min_test_positive_coverage": float(np.min([m["positive_coverage"] for m in test_evals])),
        "max_test_no_sign_false_commit_rate": float(np.max([m["no_sign_false_commit_rate"] for m in test_evals])),
        "mean_test_sorry_recall": float(np.mean([_class_recall(m, "SORRY") for m in test_evals])),
        "min_test_sorry_recall": float(np.min([_class_recall(m, "SORRY") for m in test_evals])),
        "mean_test_good_recall": float(np.mean([_class_recall(m, "GOOD") for m in test_evals])),
        "min_test_good_recall": float(np.min([_class_recall(m, "GOOD") for m in test_evals])),
    }
    gate = {
        "accepted_precision_min": float(args.accepted_precision_min),
        "positive_coverage_min": float(args.positive_coverage_min),
        "no_sign_false_commit_rate_max": float(args.no_sign_false_commit_rate_max),
        "sorry_recall_min": float(args.sorry_recall_min),
        "good_recall_min": float(args.good_recall_min),
    }
    passed = bool(
        summary["min_test_accepted_precision"] >= gate["accepted_precision_min"]
        and summary["min_test_positive_coverage"] >= gate["positive_coverage_min"]
        and summary["max_test_no_sign_false_commit_rate"] <= gate["no_sign_false_commit_rate_max"]
        and summary["min_test_sorry_recall"] >= gate["sorry_recall_min"]
        and summary["min_test_good_recall"] >= gate["good_recall_min"]
    )
    result = {
        "experiment": "e4_x_routed_system_validation_v1",
        "run_dir": str(output.resolve()),
        "primary_run": str(args.primary_run.resolve()),
        "specialist_run": str(args.specialist_run.resolve()),
        "n0_run": str(args.n0_run.resolve()),
        "classes": FINAL_CLASSES,
        "seeds": seeds,
        "dataset": {
            "rows": int(dataset["y"].size),
            "validation_rows": int(np.sum(val)),
            "test_rows": int(np.sum(test)),
            "source_counts": dict(sorted(Counter(dataset["source"].tolist()).items())),
            "n0_representation": "all-zero [96,258] feature tensor with all-false frame_mask; this is a no-hand probe, not MediaPipe-extracted N0 features",
        },
        "selected_policy": selected_policy,
        "gate": gate,
        "seed_results": seed_results,
        "summary": summary,
        "passed": passed,
        "decision": "routed_system_probe_passed_needs_real_n0_feature_extraction" if passed else "routed_system_probe_no_go_or_needs_policy_repair",
        "warnings": [
            "This is offline window-level validation only.",
            "N0 is represented as zero-landmark/no-frame sequences; real MediaPipe N0 feature extraction remains required before Android.",
            "Passing this gate does not authorize Android integration, TFLite export, or production replacement.",
        ],
    }
    _write_json(output / "metrics" / "routed_system_metrics.json", result)
    _write_json(output / "logs" / "run_summary.json", {"passed": passed, "summary": summary, "selected_policy": selected_policy})
    return result


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["metrics/routed_system_metrics.json", "metrics/validation_policy_grid.csv", "logs/run_summary.json"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if args.require_predictions and not (run_dir / "predictions" / "test_predictions.csv").exists():
        errors.append("missing predictions/test_predictions.csv")
    if args.require_metrics and (run_dir / "metrics" / "routed_system_metrics.json").exists():
        metrics = json.loads((run_dir / "metrics" / "routed_system_metrics.json").read_text(encoding="utf-8"))
        if metrics.get("experiment") != "e4_x_routed_system_validation_v1":
            errors.append("unexpected experiment id")
        if not isinstance(metrics.get("passed"), bool):
            errors.append("metrics missing boolean passed field")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-X routed-system validation")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--primary-run", type=Path, default=DEFAULT_PRIMARY_RUN)
    run_parser.add_argument("--specialist-run", type=Path, default=DEFAULT_SPECIALIST_RUN)
    run_parser.add_argument("--n0-run", type=Path, default=DEFAULT_N0_RUN)
    run_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    run_parser.add_argument("--n0-max-rows", type=int, default=180)
    run_parser.add_argument("--n0-val-rows", type=int, default=60)
    run_parser.add_argument("--primary-confidences", nargs="+", type=float, default=[0.50, 0.70, 0.80, 0.90, 0.95, 0.98, 0.99, 0.995, 0.999])
    run_parser.add_argument("--specialist-confidences", nargs="+", type=float, default=[0.50, 0.70, 0.80, 0.90, 0.95, 0.98, 0.99, 0.995, 0.999])
    run_parser.add_argument("--accepted-precision-min", type=float, default=0.95)
    run_parser.add_argument("--positive-coverage-min", type=float, default=0.80)
    run_parser.add_argument("--no-sign-false-commit-rate-max", type=float, default=0.02)
    run_parser.add_argument("--sorry-recall-min", type=float, default=0.90)
    run_parser.add_argument("--good-recall-min", type=float, default=0.90)

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
        print(f"[rgb/e4-x] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
