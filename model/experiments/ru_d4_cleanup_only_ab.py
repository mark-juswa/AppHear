"""RU-D4 cleanup-only controlled retraining package.

Compares the frozen Phase-1 training set (A) with the RU-D3 cleanup candidate
(B) using only the production-family streaming TCN and the canonical Phase-1
three-seed recipe. The protected test is never opened, hashed, or evaluated.
"""

from __future__ import annotations

import os

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import argparse  # noqa: E402
import csv  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
from collections import Counter  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

import numpy as np  # noqa: E402

from model.experiments.phase1_full_vocab_baseline import (  # noqa: E402
    _dataset,
    _history_epoch,
    _load_split,
    build_branch,
    compile_branch,
    copy_encoder_weights,
    expected_calibration_error,
    predict_clip_probs,
)

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = "ru_d4_cleanup_only_controlled_retraining_v1"
BRANCHES = ("A_frozen_baseline", "B_ru_d3_cleanup")
SEEDS = (101, 202, 303)
MODEL_BRANCH = "production_streaming_tcn"
DEFAULT_BASELINE = ROOT / ("artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1")
DEFAULT_CANDIDATE = ROOT / ("artifacts/recognition_upgrade/ru_d3/repair_candidate_01/dataset")
DEFAULT_OUTPUT = ROOT / "artifacts/recognition_upgrade/ru_d4/cleanup_only_ab_01"
DEFAULT_WARM_START = Path(
    "F:/ASL DATASET/ASL CITIZEN/derived/apphear3/runs/"
    "tcn_streaming_conversational_fps_v30/best.keras"
)
TARGETS = ("KNOW", "WHO", "WE", "LEAVE")
CONFUSION_PARTNERS = {
    "KNOW": ("HELLO", "LUNCH1", "BECAUSE", "WHY", "SEEM"),
    "WHO": ("MOUTH", "SISTER", "YOU", "TALK1"),
    "WE": ("COME",),
    "LEAVE": ("GRAB", "WASH2", "SELL", "WORK", "CLOSE", "COME"),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _split_contract(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=True) as data:
        schema = str(np.asarray(data["schema_version"]).item())
        labels = np.asarray(data["y"], dtype=np.int32)
        lengths = np.asarray(data["lengths"], dtype=np.int32)
        masks = np.asarray(data["frame_mask"], dtype=bool)
        shape = list(np.asarray(data["X"]).shape)
    errors: list[str] = []
    if schema != "3.0":
        errors.append(f"schema={schema}")
    if shape != [len(labels), 96, 258]:
        errors.append(f"shape={shape}")
    if not np.array_equal(masks.sum(axis=1).astype(np.int32), lengths):
        errors.append("mask/length mismatch")
    return {
        "path": str(path.resolve()),
        "sha256": _sha256(path),
        "rows": len(labels),
        "classes": len(set(labels.tolist())),
        "schema_version": schema,
        "shape": shape,
        "errors": errors,
    }


def _canonical_recipe() -> dict[str, Any]:
    return {
        "model_branch": MODEL_BRANCH,
        "seeds": list(SEEDS),
        "model": {
            "blocks": 4,
            "channels": 64,
            "dilations": [1, 2, 4, 8],
            "kernel": 3,
            "dropout": 0.3,
        },
        "training": {
            "batch_size": 32,
            "epochs": 40,
            "learning_rate": 0.0005,
            "weight_decay": 0.0001,
            "early_stop_patience": 8,
            "checkpoint_selection": "maximum validation clip top-1",
        },
        "augmentation": {
            "temporal": {
                "policy": "existing stride-compact-zero-pad Stage-F policy",
                "probability": 0.75,
                "max_stride": 5,
                "min_frames": 4,
            },
            "geometric": {
                "rotation_deg": 10.0,
                "scale": 0.10,
                "noise_std": 0.01,
            },
            "missing_landmark": "evaluation only; no training transform",
        },
    }


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    required = (
        args.baseline / "train.npz",
        args.baseline / "val.npz",
        args.baseline / "vocab.json",
        args.candidate / "train.npz",
        args.candidate / "val.npz",
        args.candidate / "vocab.json",
        args.candidate / "dataset_contract.json",
        args.warm_start,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing RU-D4 input: {missing}")
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output: {args.output}")

    a_train = _split_contract(args.baseline / "train.npz")
    b_train = _split_contract(args.candidate / "train.npz")
    a_val = _split_contract(args.baseline / "val.npz")
    b_val = _split_contract(args.candidate / "val.npz")
    errors = a_train["errors"] + b_train["errors"] + a_val["errors"] + b_val["errors"]
    if a_train["rows"] != 3926:
        errors.append(f"baseline rows={a_train['rows']}, expected=3926")
    if b_train["rows"] != 3820:
        errors.append(f"candidate rows={b_train['rows']}, expected=3820")
    if a_train["classes"] != 236 or b_train["classes"] != 236:
        errors.append("a training branch does not cover 236 classes")
    if a_val["sha256"] != b_val["sha256"]:
        errors.append("A/B validation hashes differ")
    if _sha256(args.baseline / "vocab.json") != _sha256(args.candidate / "vocab.json"):
        errors.append("A/B vocabulary hashes differ")
    candidate_contract = json.loads(
        (args.candidate / "dataset_contract.json").read_text(encoding="utf-8")
    )
    if candidate_contract.get("protected_test_materialized"):
        errors.append("RU-D3 candidate unexpectedly materialized protected test")
    if errors:
        raise ValueError("; ".join(errors))

    for relative in ("config", "logs", "models", "metrics", "smoke"):
        (args.output / relative).mkdir(parents=True, exist_ok=True)
    recipe = _canonical_recipe()
    config = {
        "experiment": EXPERIMENT,
        "scope": "cleanup-only A/B; no new data and no protected-test access",
        "schema_version": "3.0",
        "input_shape": [96, 258],
        "classes": 236,
        "branches": {
            "A_frozen_baseline": {
                "dataset_dir": str(args.baseline.resolve()),
                "train": a_train,
            },
            "B_ru_d3_cleanup": {
                "dataset_dir": str(args.candidate.resolve()),
                "train": b_train,
            },
        },
        "shared_validation": a_val,
        "shared_validation_hash_equal": True,
        "vocabulary": {
            "path": str((args.baseline / "vocab.json").resolve()),
            "sha256": _sha256(args.baseline / "vocab.json"),
        },
        **recipe,
        "warm_start": {
            "path": str(args.warm_start.resolve()),
            "sha256": _sha256(args.warm_start),
            "policy": "same encoder weights only; classifier head fresh per branch/seed",
        },
        "selection": {
            "source": "shared validation only",
            "metric": "validation clip top-1 per branch/seed",
            "protected_test_access": "prohibited",
        },
        "interpretation": {
            "aggregate_material_regression_points": 0.03,
            "class_regression_report_threshold": 0.10,
            "class_regression_requires_worse_seeds": 2,
            "know_count_drop_does_not_authorize_contaminated_rows": True,
            "fresh_phone_confirmation_required_after_offline_decision": True,
        },
        "production_authorized": False,
        "training_authorized_for_ru_d4_only": True,
    }
    _write_json(args.output / "config/experiment.json", config)
    summary = {
        "experiment": EXPERIMENT,
        "baseline_rows": a_train["rows"],
        "candidate_rows": b_train["rows"],
        "shared_validation_sha256": a_val["sha256"],
        "warm_start_sha256": config["warm_start"]["sha256"],
        "seeds": list(SEEDS),
        "protected_test_accessed": False,
        "errors": [],
        "passed": True,
        "next": "run smoke, then developer runs the PowerShell training command",
    }
    _write_json(args.output / "logs/prepare_summary.json", summary)
    return summary


def _config(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "config/experiment.json"
    if not path.is_file():
        raise FileNotFoundError(f"RU-D4 is not prepared: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    config = _config(args.run_dir)
    results: dict[str, Any] = {}
    for branch in BRANCHES:
        dataset = Path(config["branches"][branch]["dataset_dir"])
        x, y, mask, _, _ = _load_split(dataset / "train.npz")
        indices = np.concatenate(
            [np.flatnonzero(y == class_id)[:1] for class_id in np.unique(y)[:32]]
        )
        x, y, mask = x[indices], y[indices], mask[indices]
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(SEEDS[0])
        model = build_branch(MODEL_BRANCH, 236, float(config["model"]["dropout"]))
        compile_branch(
            model,
            MODEL_BRANCH,
            float(config["training"]["learning_rate"]),
            float(config["training"]["weight_decay"]),
        )
        copied = copy_encoder_weights(model, Path(config["warm_start"]["path"]))
        history = model.fit(
            _dataset(MODEL_BRANCH, x, y, mask, 16, SEEDS[0], config, True),
            steps_per_epoch=1,
            epochs=1,
            verbose=0,
        )
        probabilities = predict_clip_probs(model, MODEL_BRANCH, x, mask, 8)
        checkpoint = args.run_dir / "smoke" / f"{branch}.keras"
        model.save(checkpoint)
        loaded = tf.keras.models.load_model(checkpoint, compile=False, safe_mode=False)
        reload_probs = predict_clip_probs(loaded, MODEL_BRANCH, x[:2], mask[:2], 2)
        results[branch] = {
            "rows": len(x),
            "parameters": model.count_params(),
            "encoder_weights_copied": copied,
            "one_step_history": {key: float(values[-1]) for key, values in history.history.items()},
            "finite": bool(np.isfinite(probabilities).all() and np.isfinite(reload_probs).all()),
            "shape": list(probabilities.shape),
        }
    passed = all(result["finite"] and result["shape"] == [32, 236] for result in results.values())
    summary = {
        "experiment": EXPERIMENT,
        "stage": "paired_one_step_smoke",
        "branches": results,
        "protected_test_accessed": False,
        "passed": passed,
    }
    _write_json(args.run_dir / "smoke/smoke_summary.json", summary)
    return summary


def train(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    config = _config(args.run_dir)
    validation_path = Path(config["shared_validation"]["path"])
    if _sha256(validation_path) != config["shared_validation"]["sha256"]:
        raise ValueError("shared validation changed after RU-D4 preparation")
    x_val, y_val, mask_val, _, _ = _load_split(validation_path)
    training = config["training"]
    completed: list[dict[str, Any]] = []

    class ValidationClipAccuracy(tf.keras.callbacks.Callback):
        def on_epoch_end(self, epoch: int, logs: dict[str, Any] | None = None) -> None:
            assert self.model is not None
            probabilities = predict_clip_probs(
                self.model,
                MODEL_BRANCH,
                x_val,
                mask_val,
                int(training["batch_size"]),
            )
            accuracy = float(np.mean(np.argmax(probabilities, axis=1) == y_val))
            if logs is not None:
                logs["val_clip_acc"] = accuracy
            print(f" - val_clip_acc: {accuracy:.4f}")

    for seed in SEEDS:
        for branch in BRANCHES:
            dataset = Path(config["branches"][branch]["dataset_dir"])
            expected_hash = config["branches"][branch]["train"]["sha256"]
            if _sha256(dataset / "train.npz") != expected_hash:
                raise ValueError(f"{branch} train tensor changed after preparation")
            x_train, y_train, mask_train, _, _ = _load_split(dataset / "train.npz")
            tf.keras.backend.clear_session()
            tf.keras.utils.set_random_seed(seed)
            model_dir = args.run_dir / "models" / branch / f"seed_{seed}"
            model_dir.mkdir(parents=True, exist_ok=True)
            history_path = model_dir / "history.csv"
            latest = model_dir / "latest.keras"
            best = model_dir / "best.keras"
            final = model_dir / "final.keras"
            if args.resume and final.is_file():
                completed.append({"branch": branch, "seed": seed, "status": "already_complete"})
                continue
            resuming = args.resume and latest.is_file()
            initial_epoch = _history_epoch(history_path) if resuming else 0
            if resuming:
                model = tf.keras.models.load_model(latest, safe_mode=False)
                copied = 0
            else:
                if any(path.exists() for path in (history_path, latest, best, final)):
                    raise FileExistsError(f"refusing to overwrite {model_dir}; rerun with --resume")
                model = build_branch(MODEL_BRANCH, 236, float(config["model"]["dropout"]))
                compile_branch(
                    model,
                    MODEL_BRANCH,
                    float(training["learning_rate"]),
                    float(training["weight_decay"]),
                )
                copied = copy_encoder_weights(model, Path(config["warm_start"]["path"]))
            print(
                f"\n[RU-D4] branch={branch} seed={seed} "
                f"rows={len(x_train)} initial_epoch={initial_epoch}"
            )
            model.fit(
                _dataset(
                    MODEL_BRANCH,
                    x_train,
                    y_train,
                    mask_train,
                    int(training["batch_size"]),
                    seed,
                    config,
                    True,
                ),
                validation_data=_dataset(
                    MODEL_BRANCH,
                    x_val,
                    y_val,
                    mask_val,
                    int(training["batch_size"]),
                    seed,
                    config,
                    False,
                ),
                initial_epoch=initial_epoch,
                epochs=int(training["epochs"]),
                callbacks=[
                    ValidationClipAccuracy(),
                    tf.keras.callbacks.ModelCheckpoint(
                        best, monitor="val_clip_acc", mode="max", save_best_only=True
                    ),
                    tf.keras.callbacks.ModelCheckpoint(latest, save_best_only=False),
                    tf.keras.callbacks.CSVLogger(history_path, append=resuming),
                    tf.keras.callbacks.EarlyStopping(
                        monitor="val_clip_acc",
                        mode="max",
                        patience=int(training["early_stop_patience"]),
                        restore_best_weights=True,
                    ),
                ],
                verbose=2,
            )
            model.save(final)
            completed.append(
                {
                    "branch": branch,
                    "seed": seed,
                    "rows": len(x_train),
                    "initial_epoch": initial_epoch,
                    "encoder_weights_copied": copied,
                    "status": "completed",
                }
            )
            _write_json(args.run_dir / "logs/train_progress.json", completed)
            del x_train, y_train, mask_train
    summary = {
        "experiment": EXPERIMENT,
        "stage": "paired_training",
        "runs": completed,
        "protected_test_accessed": False,
        "passed": len(completed) == len(BRANCHES) * len(SEEDS),
    }
    _write_json(args.run_dir / "logs/train_summary.json", summary)
    return summary


def _metrics(
    probabilities: np.ndarray,
    labels: np.ndarray,
    participant_ids: np.ndarray,
    labels_by_id: dict[int, str],
) -> dict[str, Any]:
    predictions = np.argmax(probabilities, axis=1)
    top_k = min(5, probabilities.shape[1])
    top5 = np.argpartition(-probabilities, kth=top_k - 1, axis=1)[:, :top_k]
    per_class: list[dict[str, Any]] = []
    recalls: list[float] = []
    f1_values: list[float] = []
    for class_id in range(probabilities.shape[1]):
        truth = labels == class_id
        predicted = predictions == class_id
        support = int(truth.sum())
        true_positive = int(np.sum(truth & predicted))
        precision = true_positive / max(int(predicted.sum()), 1)
        recall = true_positive / max(support, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-12)
        if support:
            recalls.append(recall)
            f1_values.append(f1)
        per_class.append(
            {
                "class_id": class_id,
                "gloss": labels_by_id[class_id],
                "support": support,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
        )
    decile_count = max(1, int(np.ceil(len(recalls) * 0.1)))
    per_signer: dict[str, Any] = {}
    for signer in sorted(set(participant_ids.tolist())):
        selected = participant_ids == signer
        per_signer[str(signer)] = {
            "rows": int(selected.sum()),
            "top1": float(np.mean(predictions[selected] == labels[selected])),
        }
    confusion = Counter(
        (int(truth), int(predicted))
        for truth, predicted in zip(labels.tolist(), predictions.tolist(), strict=True)
        if truth != predicted
    )
    return {
        "rows": len(labels),
        "top1": float(np.mean(predictions == labels)),
        "top5": float(np.mean(np.any(top5 == labels[:, None], axis=1))),
        "macro_f1": float(np.mean(f1_values)),
        "worst_decile_mean_recall": float(np.mean(sorted(recalls)[:decile_count])),
        "worst_decile_mean_f1": float(np.mean(sorted(f1_values)[:decile_count])),
        "ece_15_bin": expected_calibration_error(probabilities, labels),
        "per_class": per_class,
        "per_signer": per_signer,
        "confusions": [
            {
                "true_class_id": truth,
                "true_gloss": labels_by_id[truth],
                "predicted_class_id": predicted,
                "predicted_gloss": labels_by_id[predicted],
                "count": count,
            }
            for (truth, predicted), count in sorted(
                confusion.items(), key=lambda item: (-item[1], item[0])
            )
        ],
    }


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    config = _config(args.run_dir)
    validation_path = Path(config["shared_validation"]["path"])
    if _sha256(validation_path) != config["shared_validation"]["sha256"]:
        raise ValueError("shared validation changed after preparation")
    x, y, mask, _, participant_ids = _load_split(validation_path)
    vocab = json.loads(Path(config["vocabulary"]["path"]).read_text(encoding="utf-8"))
    labels_by_id = {int(class_id): gloss for gloss, class_id in vocab.items()}
    id_by_label = {gloss: class_id for class_id, gloss in labels_by_id.items()}
    per_seed: dict[str, dict[str, Any]] = {branch: {} for branch in BRANCHES}
    branch_probabilities: dict[str, list[np.ndarray]] = {branch: [] for branch in BRANCHES}
    for seed in SEEDS:
        for branch in BRANCHES:
            checkpoint = args.run_dir / "models" / branch / f"seed_{seed}/best.keras"
            if not checkpoint.is_file():
                raise FileNotFoundError(f"missing RU-D4 checkpoint: {checkpoint}")
            tf.keras.backend.clear_session()
            model = tf.keras.models.load_model(checkpoint, compile=False, safe_mode=False)
            probabilities = predict_clip_probs(model, MODEL_BRANCH, x, mask, 32)
            branch_probabilities[branch].append(probabilities)
            per_seed[branch][str(seed)] = _metrics(probabilities, y, participant_ids, labels_by_id)
    ensembles = {
        branch: np.mean(np.stack(probabilities, axis=0), axis=0)
        for branch, probabilities in branch_probabilities.items()
    }
    ensemble_metrics = {
        branch: _metrics(probabilities, y, participant_ids, labels_by_id)
        for branch, probabilities in ensembles.items()
    }
    np.savez_compressed(
        args.run_dir / "metrics/validation_predictions.npz",
        labels=y,
        participant_ids=participant_ids,
        A_probabilities=ensembles[BRANCHES[0]],
        B_probabilities=ensembles[BRANCHES[1]],
        validation_sha256=np.asarray(config["shared_validation"]["sha256"]),
    )

    class_rows: list[dict[str, Any]] = []
    class_deltas: dict[str, dict[str, Any]] = {}
    for class_id in range(236):
        a = ensemble_metrics[BRANCHES[0]]["per_class"][class_id]
        b = ensemble_metrics[BRANCHES[1]]["per_class"][class_id]
        gloss = labels_by_id[class_id]
        worse_seeds = sum(
            per_seed[BRANCHES[1]][str(seed)]["per_class"][class_id]["recall"]
            < per_seed[BRANCHES[0]][str(seed)]["per_class"][class_id]["recall"]
            for seed in SEEDS
        )
        row = {
            "class_id": class_id,
            "gloss": gloss,
            "support": a["support"],
            "A_recall": a["recall"],
            "B_recall": b["recall"],
            "delta_recall": b["recall"] - a["recall"],
            "A_f1": a["f1"],
            "B_f1": b["f1"],
            "delta_f1": b["f1"] - a["f1"],
            "B_worse_seed_count": worse_seeds,
            "target_or_partner": gloss in TARGETS
            or any(gloss in partners for partners in CONFUSION_PARTNERS.values()),
        }
        class_rows.append(row)
        class_deltas[gloss] = row
    _write_csv(args.run_dir / "metrics/per_class_comparison.csv", class_rows)

    confusion_rows: list[dict[str, Any]] = []
    for target, partners in CONFUSION_PARTNERS.items():
        for partner in partners:
            for true_gloss, predicted_gloss in ((target, partner), (partner, target)):
                truth = id_by_label[true_gloss]
                predicted = id_by_label[predicted_gloss]
                row = {
                    "true_gloss": true_gloss,
                    "predicted_gloss": predicted_gloss,
                }
                for branch in BRANCHES:
                    predictions = np.argmax(ensembles[branch], axis=1)
                    row[branch] = int(np.sum((y == truth) & (predictions == predicted)))
                row["B_minus_A"] = row[BRANCHES[1]] - row[BRANCHES[0]]
                confusion_rows.append(row)
    _write_csv(args.run_dir / "metrics/target_confusions.csv", confusion_rows)

    severe_regressions = [
        row
        for row in class_rows
        if row["gloss"] not in TARGETS
        and row["delta_recall"]
        <= -float(config["interpretation"]["class_regression_report_threshold"])
        and row["B_worse_seed_count"]
        >= int(config["interpretation"]["class_regression_requires_worse_seeds"])
    ]
    mean_seed_metrics: dict[str, Any] = {}
    for branch in BRANCHES:
        mean_seed_metrics[branch] = {
            metric: float(np.mean([per_seed[branch][str(seed)][metric] for seed in SEEDS]))
            for metric in (
                "top1",
                "top5",
                "macro_f1",
                "worst_decile_mean_recall",
                "worst_decile_mean_f1",
                "ece_15_bin",
            )
        }
    aggregate_delta = {
        metric: mean_seed_metrics[BRANCHES[1]][metric] - mean_seed_metrics[BRANCHES[0]][metric]
        for metric in mean_seed_metrics[BRANCHES[0]]
    }
    report = {
        "experiment": EXPERIMENT,
        "stage": "shared_validation_cleanup_ab",
        "selection_view": "shared frozen validation only",
        "validation_sha256": config["shared_validation"]["sha256"],
        "per_seed": per_seed,
        "mean_seed_metrics": mean_seed_metrics,
        "ensemble_metrics": ensemble_metrics,
        "B_minus_A_mean_seed": aggregate_delta,
        "target_class_comparison": {gloss: class_deltas[gloss] for gloss in TARGETS},
        "severe_unrelated_regressions": severe_regressions,
        "protected_test_accessed": False,
        "fresh_phone_confirmation_pending": True,
        "production_authorized": False,
        "passed": True,
    }
    _write_json(args.run_dir / "metrics/ab_validation_report.json", report)
    return {
        "experiment": EXPERIMENT,
        "mean_seed_metrics": mean_seed_metrics,
        "B_minus_A_mean_seed": aggregate_delta,
        "target_class_comparison": report["target_class_comparison"],
        "severe_unrelated_regression_count": len(severe_regressions),
        "protected_test_accessed": False,
        "report": str((args.run_dir / "metrics/ab_validation_report.json").resolve()),
        "passed": True,
    }


def check(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    config_path = args.run_dir / "config/experiment.json"
    if not config_path.is_file():
        errors.append("missing experiment config")
    else:
        config = _config(args.run_dir)
        if config["selection"]["protected_test_access"] != "prohibited":
            errors.append("protected-test policy changed")
        if (
            _sha256(Path(config["shared_validation"]["path"]))
            != config["shared_validation"]["sha256"]
        ):
            errors.append("shared validation hash changed")
    if args.require_smoke:
        smoke_path = args.run_dir / "smoke/smoke_summary.json"
        if not smoke_path.is_file() or not json.loads(smoke_path.read_text()).get("passed"):
            errors.append("paired smoke missing or failed")
    if args.require_models:
        for seed in SEEDS:
            for branch in BRANCHES:
                for name in ("best.keras", "final.keras", "history.csv"):
                    if not (args.run_dir / "models" / branch / f"seed_{seed}" / name).is_file():
                        errors.append(f"missing {branch}/seed_{seed}/{name}")
    if args.require_evaluation:
        report = args.run_dir / "metrics/ab_validation_report.json"
        if not report.is_file() or not json.loads(report.read_text()).get("passed"):
            errors.append("A/B evaluation missing or failed")
    if list(args.run_dir.rglob("protected_test*")):
        errors.append("RU-D4 output contains a protected-test artifact")
    result = {
        "run_dir": str(args.run_dir.resolve()),
        "errors": errors,
        "protected_test_accessed": False,
        "passed": not errors,
    }
    _write_json(args.run_dir / "logs/check_report.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    prepare_parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--warm-start", type=Path, default=DEFAULT_WARM_START)
    for command in ("smoke", "train", "evaluate", "check"):
        child = sub.add_parser(command)
        child.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
        if command == "train":
            child.add_argument("--resume", action="store_true")
        if command == "check":
            child.add_argument("--require-smoke", action="store_true")
            child.add_argument("--require-models", action="store_true")
            child.add_argument("--require-evaluation", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = {
        "prepare": prepare,
        "smoke": smoke,
        "train": train,
        "evaluate": evaluate,
        "check": check,
    }[args.command](args)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
