"""E4-Z signing/no-sign gate experiment.

Compares lightweight signing gates before the E4-S primary + E4-V GOOD/SORRY
routed recognizer commits a gloss. Uses E4-Y real MediaPipe N0/P1 no-sign
features and E4-S positive windows.

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

from pipeline.rgb.e4_x_routed_system_validation import (
    FINAL_CLASSES,
    NO_SIGN_ID,
    POSITIVE_CLASSES,
    SPECIALIST_CLASSES,
    _apply_policy,
    _evaluate_policy,
    _load_json,
    _seed_predictions,
)
from pipeline.rgb.e4_y_real_nosign_feature_validation import _combined_eval_dataset

DEFAULT_PRIMARY_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01")
DEFAULT_SPECIALIST_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01")
DEFAULT_E4X_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_x_routed_system_validation_01")
DEFAULT_E4Y_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_y_real_nosign_feature_validation_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_z_signing_gate_01")
SPLITS = {"train": 0, "val": 1, "test": 2}


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


def _policy(e4x_run: Path) -> dict[str, float]:
    metrics = _load_json(e4x_run / "metrics" / "routed_system_metrics.json", "E4-X metrics")
    return {
        "primary_confidence": float(metrics["selected_policy"]["primary_confidence"]),
        "specialist_confidence": float(metrics["selected_policy"]["specialist_confidence"]),
    }


def _summary_features(x: np.ndarray, frame_mask: np.ndarray) -> tuple[np.ndarray, list[str]]:
    valid = frame_mask.astype(bool)
    hand = x[:, :, :126]
    pose = x[:, :, 126:]
    valid_f = valid[:, :, None].astype(np.float32)
    denom = np.maximum(np.sum(valid_f, axis=1), 1.0)
    hand_abs = np.sum(np.mean(np.abs(hand), axis=2, keepdims=True) * valid_f, axis=1)[:, 0] / denom[:, 0]
    pose_abs = np.sum(np.mean(np.abs(pose), axis=2, keepdims=True) * valid_f, axis=1)[:, 0] / denom[:, 0]
    hand_nonzero = np.sum(np.mean(np.abs(hand) > 1e-5, axis=2, keepdims=True) * valid_f, axis=1)[:, 0] / denom[:, 0]
    pose_nonzero = np.sum(np.mean(np.abs(pose) > 1e-5, axis=2, keepdims=True) * valid_f, axis=1)[:, 0] / denom[:, 0]
    hand_diff = np.abs(np.diff(hand, axis=1))
    pose_diff = np.abs(np.diff(pose, axis=1))
    diff_valid = (valid[:, 1:] & valid[:, :-1]).astype(np.float32)[:, :, None]
    diff_denom = np.maximum(np.sum(diff_valid, axis=1), 1.0)
    hand_motion = np.sum(np.mean(hand_diff, axis=2, keepdims=True) * diff_valid, axis=1)[:, 0] / diff_denom[:, 0]
    pose_motion = np.sum(np.mean(pose_diff, axis=2, keepdims=True) * diff_valid, axis=1)[:, 0] / diff_denom[:, 0]
    coverage = np.mean(valid, axis=1).astype(np.float32)
    combined_motion = hand_motion + 0.25 * pose_motion
    presence_motion = combined_motion * (0.25 + hand_nonzero)
    features = np.stack([
        hand_abs,
        pose_abs,
        hand_nonzero,
        pose_nonzero,
        hand_motion,
        pose_motion,
        coverage,
        combined_motion,
        presence_motion,
    ], axis=1).astype(np.float32)
    names = [
        "hand_abs",
        "pose_abs",
        "hand_nonzero",
        "pose_nonzero",
        "hand_motion",
        "pose_motion",
        "coverage",
        "combined_motion",
        "presence_motion",
    ]
    return features, names


def _class_recall(metrics: dict[str, Any], gloss: str) -> float:
    for row in metrics["per_class"]:
        if row["gloss"] == gloss:
            return 0.0 if row["recall"] is None else float(row["recall"])
    return 0.0


def _source_false_commit_rates(y_true: np.ndarray, y_pred: np.ndarray, source: np.ndarray) -> dict[str, dict[str, Any]]:
    out = {}
    for kind in sorted(set(source.tolist())):
        mask = source == kind
        no_sign = mask & (y_true == NO_SIGN_ID)
        if not np.any(no_sign):
            continue
        accepted = y_pred[no_sign] != NO_SIGN_ID
        out[kind] = {
            "rows": int(np.sum(no_sign)),
            "false_commits": int(np.sum(accepted)),
            "false_commit_rate": float(np.mean(accepted)),
            "predicted_counts": dict(sorted(Counter(FINAL_CLASSES[int(v)] for v in y_pred[no_sign]).items())),
        }
    return out


def _apply_gate_to_routed(routed_final: np.ndarray, gate_accept: np.ndarray) -> np.ndarray:
    final = routed_final.copy()
    final[~gate_accept] = NO_SIGN_ID
    return final


def _evaluate_system(y_true: np.ndarray, y_pred: np.ndarray, source: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    metrics = _evaluate_policy(y_true[mask], y_pred[mask])
    metrics["no_sign_false_commit_by_source"] = _source_false_commit_rates(y_true[mask], y_pred[mask], source[mask])
    return metrics


def _score_rule(feature_values: np.ndarray, name_to_index: dict[str, int], rule: str) -> np.ndarray:
    if rule == "combined_motion":
        return feature_values[:, name_to_index["combined_motion"]]
    if rule == "presence_motion":
        return feature_values[:, name_to_index["presence_motion"]]
    if rule == "hand_motion":
        return feature_values[:, name_to_index["hand_motion"]]
    if rule == "hand_nonzero":
        return feature_values[:, name_to_index["hand_nonzero"]]
    raise ValueError(f"unsupported rule: {rule}")


def _select_rule_threshold(score: np.ndarray, y_sign: np.ndarray, val: np.ndarray, args: argparse.Namespace) -> tuple[float, list[dict[str, Any]]]:
    values = np.unique(np.quantile(score[val], np.linspace(0.0, 1.0, 41)))
    rows = []
    for threshold in values:
        pred = score >= threshold
        positive = y_sign.astype(bool)
        val_pred = pred[val]
        val_positive = positive[val]
        no_sign = ~val_positive
        sign_recall = float(np.mean(val_pred[val_positive])) if np.any(val_positive) else 0.0
        no_sign_false_accept = float(np.mean(val_pred[no_sign])) if np.any(no_sign) else 0.0
        rows.append({
            "threshold": float(threshold),
            "sign_recall": sign_recall,
            "no_sign_false_accept_rate": no_sign_false_accept,
            "passes_gate": bool(sign_recall >= args.gate_sign_recall_min and no_sign_false_accept <= args.gate_no_sign_false_accept_max),
        })
    ranked = sorted(rows, key=lambda row: (row["passes_gate"], -row["no_sign_false_accept_rate"], row["sign_recall"]), reverse=True)
    return float(ranked[0]["threshold"]), rows


def _train_learned_gate(features: np.ndarray, y_sign: np.ndarray, split: np.ndarray, source: np.ndarray, seed: int) -> Any:
    import tensorflow as tf

    train = (split == SPLITS["train"]) | ((split == SPLITS["val"]) & (source != "e4_s_active") & (source != "e4_s_oov_sorry"))
    x_train = features[train].astype(np.float32)
    y_train = y_sign[train].astype(np.float32)
    mean = np.mean(x_train, axis=0, keepdims=True)
    std = np.maximum(np.std(x_train, axis=0, keepdims=True), 1e-6)
    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(seed)
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(features.shape[1],)),
        tf.keras.layers.Normalization(mean=mean[0], variance=(std[0] ** 2)),
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dropout(0.10),
        tf.keras.layers.Dense(1, activation="sigmoid"),
    ])
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3), loss="binary_crossentropy", metrics=["accuracy"])
    neg = max(int(np.sum(y_train == 0)), 1)
    pos = max(int(np.sum(y_train == 1)), 1)
    class_weight = {0: float((pos + neg) / (2 * neg)), 1: float((pos + neg) / (2 * pos))}
    model.fit(x_train, y_train, batch_size=16, epochs=80, verbose=0, class_weight=class_weight)
    return model


def _select_probability_threshold(probs: np.ndarray, y_sign: np.ndarray, val: np.ndarray, args: argparse.Namespace) -> tuple[float, list[dict[str, Any]]]:
    thresholds = np.unique(np.quantile(probs[val], np.linspace(0.0, 1.0, 61)))
    rows = []
    for threshold in thresholds:
        pred = probs >= threshold
        positive = y_sign.astype(bool)
        val_pred = pred[val]
        val_positive = positive[val]
        no_sign = ~val_positive
        sign_recall = float(np.mean(val_pred[val_positive])) if np.any(val_positive) else 0.0
        no_sign_false_accept = float(np.mean(val_pred[no_sign])) if np.any(no_sign) else 0.0
        rows.append({
            "threshold": float(threshold),
            "sign_recall": sign_recall,
            "no_sign_false_accept_rate": no_sign_false_accept,
            "passes_gate": bool(sign_recall >= args.gate_sign_recall_min and no_sign_false_accept <= args.gate_no_sign_false_accept_max),
        })
    ranked = sorted(rows, key=lambda row: (row["passes_gate"], -row["no_sign_false_accept_rate"], row["sign_recall"]), reverse=True)
    return float(ranked[0]["threshold"]), rows


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    for relative in ("logs", "metrics", "predictions"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    primary_config = _load_json(args.primary_run / "pilot_config.json", "E4-S config")
    specialist_config = _load_json(args.specialist_run / "pilot_config.json", "E4-V config")
    dataset = _combined_eval_dataset(args.primary_run, args.e4y_run)
    features, feature_names = _summary_features(dataset["landmarks"], dataset["frame_mask"])
    name_to_index = {name: idx for idx, name in enumerate(feature_names)}
    y_sign = (dataset["y"] != NO_SIGN_ID).astype(np.int64)
    val = dataset["split_index"] == SPLITS["val"]
    test = dataset["split_index"] == SPLITS["test"]
    policy = _policy(args.e4x_run)
    seeds = [int(seed) for seed in args.seeds]
    seed_payloads = {seed: _seed_predictions(seed, args.primary_run, args.specialist_run, primary_config, specialist_config, dataset) for seed in seeds}
    routed_by_seed = {seed: _apply_policy(payload, policy) for seed, payload in seed_payloads.items()}

    branches: dict[str, Any] = {}
    threshold_rows: list[dict[str, Any]] = []
    for rule in args.rules:
        score = _score_rule(features, name_to_index, rule)
        threshold, rows = _select_rule_threshold(score, y_sign, val, args)
        gate_accept = score >= threshold
        seed_results = {}
        for seed, routed in routed_by_seed.items():
            final = _apply_gate_to_routed(routed, gate_accept)
            seed_results[str(seed)] = {
                "validation": _evaluate_system(dataset["y"], final, dataset["source"], val),
                "test": _evaluate_system(dataset["y"], final, dataset["source"], test),
            }
        branches[f"rule_{rule}"] = {"threshold": threshold, "seed_results": seed_results}
        for row in rows:
            threshold_rows.append({"branch": f"rule_{rule}", **row})

    learned_seed_results = {}
    learned_threshold_rows = []
    for seed in seeds:
        model = _train_learned_gate(features, y_sign, dataset["split_index"], dataset["source"], seed)
        probs = model.predict(features.astype(np.float32), batch_size=32, verbose=0).reshape(-1)
        threshold, rows = _select_probability_threshold(probs, y_sign, val, args)
        gate_accept = probs >= threshold
        final = _apply_gate_to_routed(routed_by_seed[seed], gate_accept)
        learned_seed_results[str(seed)] = {
            "threshold": threshold,
            "validation": _evaluate_system(dataset["y"], final, dataset["source"], val),
            "test": _evaluate_system(dataset["y"], final, dataset["source"], test),
        }
        for row in rows:
            learned_threshold_rows.append({"branch": "learned_summary_mlp", "seed": seed, **row})
    branches["learned_summary_mlp"] = {"seed_results": learned_seed_results}
    threshold_rows.extend(learned_threshold_rows)

    summary = _summary(branches)
    gate = {
        "accepted_precision_min": float(args.accepted_precision_min),
        "positive_coverage_min": float(args.positive_coverage_min),
        "no_sign_false_commit_rate_max": float(args.no_sign_false_commit_rate_max),
        "good_recall_min": float(args.good_recall_min),
        "sorry_recall_min": float(args.sorry_recall_min),
    }
    best_branch = summary["best_branch"]
    best = summary["by_branch"].get(best_branch, {})
    passed = bool(
        best
        and best["min_test_accepted_precision"] >= gate["accepted_precision_min"]
        and best["min_test_positive_coverage"] >= gate["positive_coverage_min"]
        and best["max_test_no_sign_false_commit_rate"] <= gate["no_sign_false_commit_rate_max"]
        and best["min_test_good_recall"] >= gate["good_recall_min"]
        and best["min_test_sorry_recall"] >= gate["sorry_recall_min"]
    )
    _write_csv(output / "metrics" / "gate_threshold_grid.csv", threshold_rows, ["branch", "seed", "threshold", "sign_recall", "no_sign_false_accept_rate", "passes_gate"])
    result = {
        "experiment": "e4_z_signing_no_sign_gate_v1",
        "run_dir": str(output.resolve()),
        "primary_run": str(args.primary_run.resolve()),
        "specialist_run": str(args.specialist_run.resolve()),
        "e4x_run": str(args.e4x_run.resolve()),
        "e4y_run": str(args.e4y_run.resolve()),
        "policy": policy,
        "feature_names": feature_names,
        "dataset": {
            "rows": int(dataset["y"].shape[0]),
            "split_counts": dict(sorted(Counter(str(int(v)) for v in dataset["split_index"]).items())),
            "source_counts": dict(sorted(Counter(dataset["source"].tolist()).items())),
        },
        "gate": gate,
        "branches": branches,
        "summary": summary,
        "passed": passed,
        "decision": "signing_gate_candidate_ready_for_larger_nosign_validation" if passed else "signing_gate_no_go_or_needs_more_negative_data",
        "warnings": [
            "This is a small offline diagnostic; no Android/export is authorized.",
            "Learned gate uses E4-Y validation no-sign rows for training because no-sign training split does not yet exist.",
            "A passing result must be rerun with larger N0/P1 splits before production work.",
        ],
    }
    _write_json(output / "metrics" / "signing_gate_metrics.json", result)
    _write_json(output / "logs" / "run_summary.json", {"passed": passed, "summary": summary})
    return result


def _summary(branches: dict[str, Any]) -> dict[str, Any]:
    by_branch: dict[str, Any] = {}
    for branch, payload in branches.items():
        seeds = payload["seed_results"]
        tests = [seed_payload["test"] for seed_payload in seeds.values()]
        by_branch[branch] = {
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
    ranked = sorted(
        by_branch.items(),
        key=lambda item: (
            item[1]["max_test_no_sign_false_commit_rate"],
            -item[1]["min_test_accepted_precision"],
            -item[1]["min_test_positive_coverage"],
        ),
    )
    return {"by_branch": by_branch, "best_branch": ranked[0][0] if ranked else None}


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["metrics/signing_gate_metrics.json", "metrics/gate_threshold_grid.csv", "logs/run_summary.json"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if args.require_metrics and (run_dir / "metrics" / "signing_gate_metrics.json").exists():
        metrics = json.loads((run_dir / "metrics" / "signing_gate_metrics.json").read_text(encoding="utf-8"))
        if metrics.get("experiment") != "e4_z_signing_no_sign_gate_v1":
            errors.append("unexpected experiment id")
        if not isinstance(metrics.get("passed"), bool):
            errors.append("metrics missing boolean passed field")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-Z signing/no-sign gate")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--primary-run", type=Path, default=DEFAULT_PRIMARY_RUN)
    run_parser.add_argument("--specialist-run", type=Path, default=DEFAULT_SPECIALIST_RUN)
    run_parser.add_argument("--e4x-run", type=Path, default=DEFAULT_E4X_RUN)
    run_parser.add_argument("--e4y-run", type=Path, default=DEFAULT_E4Y_RUN)
    run_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    run_parser.add_argument("--rules", nargs="+", default=["combined_motion", "presence_motion", "hand_motion", "hand_nonzero"])
    run_parser.add_argument("--gate-sign-recall-min", type=float, default=0.90)
    run_parser.add_argument("--gate-no-sign-false-accept-max", type=float, default=0.10)
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
        print(f"[rgb/e4-z] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
