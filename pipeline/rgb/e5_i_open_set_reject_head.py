"""E5-I explicit open-set / rejection landmark experiment.

Two-head schema v3.0 [96,258] landmark model:
- sign head predicts the supported sign class;
- accept head predicts supported vs unsupported/no-sign.

Offline experiment only. No Android/export/production replacement.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.rgb.e5_f_reduced_primary_routed_sim import DEFAULT_E5D_RUN, DEFAULT_NOSIGN_RUN
from pipeline.rgb.e5_h_clean_7_routed_sim import DEFAULT_E5G_RUN, NO_SIGN, SPLITS, _load_json, _load_npz, _write_csv, _write_json

DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_i_open_set_reject_head_01")
DEFAULT_SEEDS = [101, 202, 303]
DEFAULT_SUPPORTED = ["WASH2", "THINK", "TAKE", "MEET", "GOOD", "SELL", "STAND2"]
BRANCH = "conv1d_reject_head"


def _load_positive_dataset(e5g_run: Path, supported: list[str]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    config = _load_json(e5g_run / "pilot_config.json", "E5-G config")
    data = _load_npz(e5g_run / "dataset" / "landmark_features.npz", "E5-G landmark tensor")
    classes = list(config["classes"])
    class_to_supported = {gloss: idx for idx, gloss in enumerate(supported)}
    glosses = np.asarray([classes[int(y)] for y in data["y"].astype(np.int64)]).astype(str)
    row_kind = np.asarray(["positive" if gloss in class_to_supported else "unsupported" for gloss in glosses]).astype(str)
    return {
        "landmarks": data["landmarks"].astype(np.float32),
        "frame_mask": data["frame_mask"].astype(bool),
        "split_index": data["split_index"].astype(np.int64),
        "sample_ids": np.asarray(data["sample_ids"]).astype(str),
        "source": np.asarray(["e5g_positive" if kind == "positive" else "e5g_subset_unsupported" for kind in row_kind]).astype(str),
        "true_gloss": glosses,
        "row_kind": row_kind,
        "y_sign": np.asarray([class_to_supported.get(gloss, 0) for gloss in glosses], dtype=np.int64),
        "y_accept": (row_kind == "positive").astype(np.float32),
    }, config


def _load_unsupported_dataset(e5d_run: Path, supported: list[str]) -> dict[str, np.ndarray]:
    config = _load_json(e5d_run / "pilot_config.json", "E5-D config")
    data = _load_npz(e5d_run / "dataset" / "landmark_features.npz", "E5-D landmark tensor")
    classes = list(config["classes"])
    glosses_all = np.asarray([classes[int(y)] for y in data["y"].astype(np.int64)]).astype(str)
    keep = np.asarray([gloss not in set(supported) for gloss in glosses_all], dtype=bool)
    n = int(np.sum(keep))
    return {
        "landmarks": data["landmarks"][keep].astype(np.float32),
        "frame_mask": data["frame_mask"][keep].astype(bool),
        "split_index": data["split_index"][keep].astype(np.int64),
        "sample_ids": np.asarray(data["sample_ids"])[keep].astype(str),
        "source": np.asarray(["e5d_unsupported"] * n).astype(str),
        "true_gloss": glosses_all[keep].astype(str),
        "row_kind": np.asarray(["unsupported"] * n).astype(str),
        "y_sign": np.zeros(n, dtype=np.int64),
        "y_accept": np.zeros(n, dtype=np.float32),
    }


def _load_nosign_dataset(nosign_run: Path) -> dict[str, np.ndarray]:
    data = _load_npz(nosign_run / "dataset" / "nosign_features.npz", "E4-AG no-sign tensor")
    n = int(data["landmarks"].shape[0])
    return {
        "landmarks": data["landmarks"].astype(np.float32),
        "frame_mask": data["frame_mask"].astype(bool),
        "split_index": data["split_index"].astype(np.int64),
        "sample_ids": np.asarray(data["sample_ids"]).astype(str),
        "source": np.asarray(data["source"]).astype(str),
        "true_gloss": np.asarray([NO_SIGN] * n).astype(str),
        "row_kind": np.asarray(["no_sign"] * n).astype(str),
        "y_sign": np.zeros(n, dtype=np.int64),
        "y_accept": np.zeros(n, dtype=np.float32),
    }


def _combine(parts: list[dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    keys = ["landmarks", "frame_mask", "split_index", "sample_ids", "source", "true_gloss", "row_kind", "y_sign", "y_accept"]
    out = {key: np.concatenate([part[key] for part in parts], axis=0) for key in keys}
    order = np.lexsort((out["sample_ids"], out["source"], out["row_kind"], out["split_index"]))
    return {key: value[order] for key, value in out.items()}


def _dataset(args: argparse.Namespace) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    supported = [str(item).upper() for item in args.supported_classes]
    positive, e5g_config = _load_positive_dataset(args.e5g_run, supported)
    unsupported = _load_unsupported_dataset(args.e5d_run, supported)
    nosign = _load_nosign_dataset(args.nosign_run)
    data = _combine([positive, unsupported, nosign])
    config = {
        "experiment": "e5_i_open_set_reject_head_v1",
        "purpose": "explicit supported-vs-unsupported/no-sign rejection head after E5-H confidence-only no-go",
        "run_dir": str(args.output.resolve()),
        "e5g_run": str(args.e5g_run.resolve()),
        "e5d_run": str(args.e5d_run.resolve()),
        "nosign_run": str(args.nosign_run.resolve()),
        "schema_version": e5g_config.get("schema_version", "3.0"),
        "input_shape": [96, 258],
        "supported_classes": supported,
        "class_count": len(supported),
        "trained_e5g_classes": list(e5g_config["classes"]),
        "active_rows": int(data["landmarks"].shape[0]),
        "split_counts": {name: int(np.sum(data["split_index"] == sid)) for name, sid in SPLITS.items()},
        "row_kind_counts": dict(sorted(Counter(data["row_kind"].tolist()).items())),
        "source_counts": dict(sorted(Counter(data["source"].tolist()).items())),
        "branches": [BRANCH],
        "seeds": [int(seed) for seed in args.seeds],
        "epochs": int(args.epochs),
        "batch_size": int(args.batch_size),
        "learning_rate": float(args.learning_rate),
        "loss_weights": {"sign": float(args.sign_loss_weight), "accept": float(args.accept_loss_weight)},
        "gate": {
            "accepted_precision_min": float(args.accepted_precision_min),
            "positive_coverage_min": float(args.positive_coverage_min),
            "unsupported_false_commit_rate_max": float(args.unsupported_false_commit_rate_max),
            "no_sign_false_commit_rate_max": float(args.no_sign_false_commit_rate_max),
            "min_class_recall_min": float(args.min_class_recall_min),
        },
        "warnings": [
            "Offline experiment only; no Android/export authorized.",
            "Unsupported signs are pressure rows, not a complete real-world OOV universe.",
            "Passing this gate authorizes review and replication, not production replacement.",
        ],
    }
    return data, config


def _manifest_rows(data: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    split_names = {value: key for key, value in SPLITS.items()}
    rows = []
    for i in range(int(data["landmarks"].shape[0])):
        rows.append({
            "sample_id": str(data["sample_ids"][i]),
            "split": split_names.get(int(data["split_index"][i]), str(int(data["split_index"][i]))),
            "row_kind": str(data["row_kind"][i]),
            "true_gloss": str(data["true_gloss"][i]),
            "source": str(data["source"][i]),
            "y_sign": int(data["y_sign"][i]),
            "y_accept": int(data["y_accept"][i]),
        })
    return rows


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join([
        "# E5-I Open-Set Reject Head",
        "",
        "Offline-only two-head landmark experiment. It does not modify Android or production assets.",
        "",
        f"- Supported classes: `{', '.join(config['supported_classes'])}`",
        f"- Rows: `{config['active_rows']}`",
        f"- Split counts: `{config['split_counts']}`",
        f"- Row kinds: `{config['row_kind_counts']}`",
        "",
        "## Smoke",
        "```powershell",
        'cd "F:\\ASL DATASET\\5. Apphear3"',
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_i_open_set_reject_head smoke --run-dir "{run_dir}"',
        "```",
        "",
        "## Full Run",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_i_open_set_reject_head run --run-dir "{run_dir}"',
        "```",
        "",
        "Resume interrupted training:",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_i_open_set_reject_head run --run-dir "{run_dir}" --resume',
        "```",
        "",
        "## Check",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_i_open_set_reject_head check --run-dir "{run_dir}" --require-dataset --require-full-dataset --require-metrics',
        "```",
    ])


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("dataset", "logs", "metrics", "models", "predictions", "smoke", "tables"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    data, config = _dataset(args)
    np.savez_compressed(output / "dataset" / "open_set_features.npz", **data)
    _write_json(output / "pilot_config.json", config)
    _write_csv(output / "pilot_manifest.csv", _manifest_rows(data), ["sample_id", "split", "row_kind", "true_gloss", "source", "y_sign", "y_accept"])
    _write_csv(output / "selected_classes.csv", [{"class_id": idx, "gloss": gloss} for idx, gloss in enumerate(config["supported_classes"])], ["class_id", "gloss"])
    _write_json(output / "logs" / "dataset_summary.json", {key: config[key] for key in ["active_rows", "split_counts", "row_kind_counts", "source_counts", "supported_classes"]})
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def _load_dataset(run_dir: Path) -> dict[str, np.ndarray]:
    path = run_dir / "dataset" / "open_set_features.npz"
    if not path.exists():
        raise FileNotFoundError(f"missing dataset; run prepare first: {path}")
    raw = np.load(path, allow_pickle=False)
    return {key: raw[key] for key in raw.files}


def _build_model(input_shape: tuple[int, int], classes: int, lr: float, loss_weights: dict[str, float]):
    import tensorflow as tf

    inputs = tf.keras.Input(shape=input_shape, name="features")
    x = tf.keras.layers.LayerNormalization(name="norm")(inputs)
    x = tf.keras.layers.Conv1D(128, 5, padding="same", activation="relu", name="conv5")(x)
    x = tf.keras.layers.Dropout(0.25, name="drop1")(x)
    x = tf.keras.layers.Conv1D(128, 3, padding="same", activation="relu", name="conv3")(x)
    pooled = tf.keras.layers.GlobalAveragePooling1D(name="pool")(x)
    hidden = tf.keras.layers.Dense(96, activation="relu", name="shared_dense")(pooled)
    hidden = tf.keras.layers.Dropout(0.20, name="shared_drop")(hidden)
    sign = tf.keras.layers.Dense(classes, activation="softmax", name="sign")(hidden)
    accept = tf.keras.layers.Dense(1, activation="sigmoid", name="accept")(hidden)
    model = tf.keras.Model(inputs, {"sign": sign, "accept": accept}, name="e5_i_conv1d_reject_head")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
        loss={"sign": "sparse_categorical_crossentropy", "accept": "binary_crossentropy"},
        loss_weights=loss_weights,
        metrics={"sign": ["accuracy"], "accept": ["binary_accuracy", tf.keras.metrics.AUC(name="auc")]},
    )
    return model


def _targets(data: dict[str, np.ndarray], mask: np.ndarray) -> dict[str, np.ndarray]:
    return {"sign": data["y_sign"][mask].astype(np.int64), "accept": data["y_accept"][mask].astype(np.float32)}


def _sample_weights(data: dict[str, np.ndarray], mask: np.ndarray) -> dict[str, np.ndarray]:
    y_accept = data["y_accept"][mask].astype(np.float32)
    sign_weight = y_accept.copy()
    pos = int(np.sum(y_accept == 1.0))
    neg = int(np.sum(y_accept == 0.0))
    total = max(pos + neg, 1)
    accept_weight = np.ones_like(y_accept, dtype=np.float32)
    if pos > 0:
        accept_weight[y_accept == 1.0] = total / (2.0 * pos)
    if neg > 0:
        accept_weight[y_accept == 0.0] = total / (2.0 * neg)
    return {"sign": sign_weight, "accept": accept_weight}


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = _load_json(run_dir / "pilot_config.json", "E5-I config")
    data = _load_dataset(run_dir)
    take = min(int(args.rows), int(data["landmarks"].shape[0]))
    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(12345)
    model = _build_model((96, 258), int(config["class_count"]), float(config["learning_rate"]), config["loss_weights"])
    x = data["landmarks"][:take].astype(np.float32)
    mini = {k: v[:take] for k, v in data.items()}
    mask = np.ones(take, dtype=bool)
    preds = model.predict(x, batch_size=min(8, take), verbose=0)
    loss = model.train_on_batch(x, _targets(mini, mask), sample_weight=_sample_weights(mini, mask))
    weights = run_dir / "smoke" / "open_set_reject_head.weights.h5"
    model.save_weights(weights)
    summary = {
        "rows": take,
        "input_shape": [int(v) for v in x.shape],
        "sign_shape": [int(v) for v in preds["sign"].shape],
        "accept_shape": [int(v) for v in preds["accept"].shape],
        "train_on_batch": [float(v) for v in np.atleast_1d(loss).tolist()],
        "weights_saved": str(weights.resolve()),
        "passed": True,
    }
    _write_json(run_dir / "smoke" / "smoke_summary.json", summary)
    return summary


def _policy_eval(data: dict[str, np.ndarray], sign_probs: np.ndarray, accept_prob: np.ndarray, classes: list[str], split_mask: np.ndarray, accept_threshold: float, sign_threshold: float) -> dict[str, Any]:
    true = data["true_gloss"][split_mask].astype(str)
    kind = data["row_kind"][split_mask].astype(str)
    source = data["source"][split_mask].astype(str)
    probs = sign_probs[split_mask]
    accept = accept_prob[split_mask]
    pred_id = np.argmax(probs, axis=1)
    sign_conf = np.max(probs, axis=1)
    final = np.asarray(["REJECT"] * int(true.size), dtype=object)
    commit = (accept >= accept_threshold) & (sign_conf >= sign_threshold)
    for i, ok in enumerate(commit.tolist()):
        if ok:
            final[i] = classes[int(pred_id[i])]
    final = final.astype(str)
    positive = kind == "positive"
    unsupported = kind == "unsupported"
    no_sign = kind == "no_sign"
    accepted = final != "REJECT"
    correct_accepts = accepted & positive & (final == true)
    metrics = {
        "rows": int(true.size),
        "positive_rows": int(np.sum(positive)),
        "unsupported_rows": int(np.sum(unsupported)),
        "no_sign_rows": int(np.sum(no_sign)),
        "accepted": int(np.sum(accepted)),
        "accepted_precision": float(np.sum(correct_accepts) / max(int(np.sum(accepted)), 1)),
        "positive_coverage": float(np.sum(accepted & positive) / max(int(np.sum(positive)), 1)),
        "positive_accuracy_with_rejects": float(np.mean(final[positive] == true[positive])) if np.any(positive) else 0.0,
        "unsupported_false_commit_rate": float(np.mean(accepted[unsupported])) if np.any(unsupported) else 0.0,
        "no_sign_false_commit_rate": float(np.mean(accepted[no_sign])) if np.any(no_sign) else 0.0,
        "predicted_counts": dict(sorted(Counter(final.tolist()).items())),
        "per_class": [],
        "false_commit_by_source": {},
    }
    for gloss in classes:
        cmask = positive & (true == gloss)
        metrics["per_class"].append({"gloss": gloss, "count": int(np.sum(cmask)), "correct": int(np.sum(cmask & (final == gloss))), "recall": float(np.mean(final[cmask] == gloss)) if np.any(cmask) else None})
    for source_name in sorted(set(source.tolist())):
        bad = (source == source_name) & (unsupported | no_sign)
        if np.any(bad):
            metrics["false_commit_by_source"][source_name] = {"rows": int(np.sum(bad)), "false_commits": int(np.sum(accepted[bad])), "false_commit_rate": float(np.mean(accepted[bad])), "predicted_counts": dict(sorted(Counter(final[bad].tolist()).items()))}
    return metrics


def _class_recall(metrics: dict[str, Any], gloss: str) -> float:
    for row in metrics["per_class"]:
        if row["gloss"] == gloss:
            return 0.0 if row["recall"] is None else float(row["recall"])
    return 0.0


def _select_policy(data: dict[str, np.ndarray], seed_preds: dict[int, dict[str, np.ndarray]], classes: list[str], config: dict[str, Any], args: argparse.Namespace) -> tuple[dict[str, float], list[dict[str, Any]]]:
    val_mask = data["split_index"] == SPLITS["val"]
    rows = []
    gate = config["gate"]
    for accept_th in args.accept_thresholds:
        for sign_th in args.sign_thresholds:
            evals = [_policy_eval(data, pred["sign_probs"], pred["accept_prob"], classes, val_mask, float(accept_th), float(sign_th)) for pred in seed_preds.values()]
            row = {
                "accept_threshold": float(accept_th),
                "sign_threshold": float(sign_th),
                "mean_accepted_precision": float(np.mean([m["accepted_precision"] for m in evals])),
                "min_accepted_precision": float(np.min([m["accepted_precision"] for m in evals])),
                "mean_positive_coverage": float(np.mean([m["positive_coverage"] for m in evals])),
                "min_positive_coverage": float(np.min([m["positive_coverage"] for m in evals])),
                "max_unsupported_false_commit_rate": float(np.max([m["unsupported_false_commit_rate"] for m in evals])),
                "max_no_sign_false_commit_rate": float(np.max([m["no_sign_false_commit_rate"] for m in evals])),
                "min_class_recall": float(np.min([min([_class_recall(m, g) for g in classes] or [0.0]) for m in evals])),
            }
            row["passes_gate"] = bool(
                row["min_accepted_precision"] >= gate["accepted_precision_min"]
                and row["min_positive_coverage"] >= gate["positive_coverage_min"]
                and row["max_unsupported_false_commit_rate"] <= gate["unsupported_false_commit_rate_max"]
                and row["max_no_sign_false_commit_rate"] <= gate["no_sign_false_commit_rate_max"]
                and row["min_class_recall"] >= gate["min_class_recall_min"]
            )
            rows.append(row)
    ranked = sorted(rows, key=lambda row: (row["passes_gate"], row["min_accepted_precision"], row["min_positive_coverage"], row["min_class_recall"], -row["max_unsupported_false_commit_rate"], -row["max_no_sign_false_commit_rate"]), reverse=True)
    return {"accept_threshold": float(ranked[0]["accept_threshold"]), "sign_threshold": float(ranked[0]["sign_threshold"])}, rows


def _predict(model: Any, x: np.ndarray, batch_size: int) -> dict[str, np.ndarray]:
    preds = model.predict(x, batch_size=batch_size, verbose=0)
    return {"sign_probs": preds["sign"].astype(np.float32), "accept_prob": preds["accept"].reshape(-1).astype(np.float32)}


def _positive_closed_set(data: dict[str, np.ndarray], sign_probs: np.ndarray, classes: list[str], split_mask: np.ndarray) -> dict[str, Any]:
    mask = split_mask & (data["row_kind"] == "positive")
    true = data["true_gloss"][mask].astype(str)
    pred = np.asarray([classes[int(i)] for i in np.argmax(sign_probs[mask], axis=1)]).astype(str)
    return {"count": int(true.size), "accuracy": float(np.mean(pred == true)) if true.size else 0.0, "predicted_counts": dict(sorted(Counter(pred.tolist()).items()))}


def _append_predictions(rows: list[dict[str, Any]], seed: int, data: dict[str, np.ndarray], preds: dict[str, np.ndarray], classes: list[str], split_mask: np.ndarray, policy: dict[str, float]) -> None:
    for idx in np.where(split_mask)[0].tolist():
        sign_id = int(np.argmax(preds["sign_probs"][idx]))
        sign_pred = classes[sign_id]
        sign_conf = float(np.max(preds["sign_probs"][idx]))
        accepted = bool(preds["accept_prob"][idx] >= policy["accept_threshold"] and sign_conf >= policy["sign_threshold"])
        final = sign_pred if accepted else "REJECT"
        rows.append({
            "seed": seed,
            "sample_id": str(data["sample_ids"][idx]),
            "source": str(data["source"][idx]),
            "row_kind": str(data["row_kind"][idx]),
            "true_gloss": str(data["true_gloss"][idx]),
            "accept_probability": float(preds["accept_prob"][idx]),
            "sign_pred": sign_pred,
            "sign_confidence": sign_conf,
            "final_pred": final,
            "accepted": accepted,
            "correct": bool(final == data["true_gloss"][idx]),
        })


def _summary(tests: list[dict[str, Any]], classes: list[str]) -> dict[str, float]:
    return {
        "mean_test_accepted_precision": float(np.mean([m["accepted_precision"] for m in tests])),
        "min_test_accepted_precision": float(np.min([m["accepted_precision"] for m in tests])),
        "mean_test_positive_coverage": float(np.mean([m["positive_coverage"] for m in tests])),
        "min_test_positive_coverage": float(np.min([m["positive_coverage"] for m in tests])),
        "max_test_unsupported_false_commit_rate": float(np.max([m["unsupported_false_commit_rate"] for m in tests])),
        "max_test_no_sign_false_commit_rate": float(np.max([m["no_sign_false_commit_rate"] for m in tests])),
        "min_test_class_recall": float(np.min([min([_class_recall(m, g) for g in classes] or [0.0]) for m in tests])),
        "mean_test_class_recall": float(np.mean([_class_recall(m, g) for m in tests for g in classes])),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = _load_json(run_dir / "pilot_config.json", "E5-I config")
    data = _load_dataset(run_dir)
    classes = list(config["supported_classes"])
    train_mask = data["split_index"] == SPLITS["train"]
    val_mask = data["split_index"] == SPLITS["val"]
    test_mask = data["split_index"] == SPLITS["test"]
    start = time.perf_counter()
    seed_preds = {}
    seed_results = {}
    for seed in config["seeds"]:
        seed = int(seed)
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(seed)
        seed_dir = run_dir / "models" / BRANCH / f"seed_{seed}"
        seed_dir.mkdir(parents=True, exist_ok=True)
        latest = seed_dir / "latest.weights.h5"
        best = seed_dir / "best.weights.h5"
        epoch_file = run_dir / "logs" / f"{BRANCH}_seed_{seed}_epoch_count.txt"
        history_path = run_dir / "logs" / f"{BRANCH}_seed_{seed}_history.csv"
        if latest.exists() and not args.resume:
            raise FileExistsError(f"seed {seed}: latest weights exist; rerun with --resume")
        model = _build_model((96, 258), int(config["class_count"]), float(config["learning_rate"]), config["loss_weights"])
        initial_epoch = 0
        if args.resume and latest.exists():
            model.load_weights(latest)
            initial_epoch = int(epoch_file.read_text(encoding="utf-8"))
        history = model.fit(
            data["landmarks"][train_mask],
            _targets(data, train_mask),
            sample_weight=_sample_weights(data, train_mask),
            validation_data=(data["landmarks"][val_mask], _targets(data, val_mask), _sample_weights(data, val_mask)),
            batch_size=int(config["batch_size"]),
            epochs=initial_epoch + int(config["epochs"]),
            initial_epoch=initial_epoch,
            callbacks=[
                tf.keras.callbacks.ModelCheckpoint(str(best), monitor="val_accept_auc", mode="max", save_best_only=True, save_weights_only=True),
                tf.keras.callbacks.CSVLogger(str(history_path), append=history_path.exists()),
            ],
            verbose=2,
        )
        model.save_weights(latest)
        total_epochs = initial_epoch + int(config["epochs"])
        epoch_file.write_text(str(total_epochs), encoding="utf-8")
        latest_preds = _predict(model, data["landmarks"], int(config["batch_size"]))
        best_model = _build_model((96, 258), int(config["class_count"]), float(config["learning_rate"]), config["loss_weights"])
        best_model.load_weights(best)
        best_preds = _predict(best_model, data["landmarks"], int(config["batch_size"]))
        seed_preds[seed] = latest_preds
        seed_results[str(seed)] = {
            "latest_positive_closed_set": _positive_closed_set(data, latest_preds["sign_probs"], classes, test_mask),
            "best_positive_closed_set": _positive_closed_set(data, best_preds["sign_probs"], classes, test_mask),
            "epoch_count_total": total_epochs,
            "history_last": {key: float(values[-1]) for key, values in history.history.items()},
        }
    policy, grid_rows = _select_policy(data, seed_preds, classes, config, args)
    prediction_rows = []
    tests = []
    for seed, preds in seed_preds.items():
        val_metrics = _policy_eval(data, preds["sign_probs"], preds["accept_prob"], classes, val_mask, policy["accept_threshold"], policy["sign_threshold"])
        test_metrics = _policy_eval(data, preds["sign_probs"], preds["accept_prob"], classes, test_mask, policy["accept_threshold"], policy["sign_threshold"])
        tests.append(test_metrics)
        seed_results[str(seed)]["validation"] = val_metrics
        seed_results[str(seed)]["test"] = test_metrics
        _append_predictions(prediction_rows, seed, data, preds, classes, test_mask, policy)
    summary = _summary(tests, classes)
    gate = config["gate"]
    passed = bool(
        summary["min_test_accepted_precision"] >= gate["accepted_precision_min"]
        and summary["min_test_positive_coverage"] >= gate["positive_coverage_min"]
        and summary["max_test_unsupported_false_commit_rate"] <= gate["unsupported_false_commit_rate_max"]
        and summary["max_test_no_sign_false_commit_rate"] <= gate["no_sign_false_commit_rate_max"]
        and summary["min_test_class_recall"] >= gate["min_class_recall_min"]
    )
    result = {
        "experiment": config["experiment"],
        "run_dir": str(run_dir.resolve()),
        "supported_classes": classes,
        "dataset": {key: config[key] for key in ["active_rows", "split_counts", "row_kind_counts", "source_counts"]},
        "selected_policy": policy,
        "gate": gate,
        "seed_results": seed_results,
        "summary": summary,
        "elapsed_seconds": time.perf_counter() - start,
        "passed": passed,
        "decision": "open_set_reject_head_candidate" if passed else "open_set_reject_head_no_go_or_needs_architecture_data_repair",
        "warnings": config["warnings"],
    }
    _write_csv(run_dir / "metrics" / "validation_policy_grid.csv", grid_rows, ["accept_threshold", "sign_threshold", "mean_accepted_precision", "min_accepted_precision", "mean_positive_coverage", "min_positive_coverage", "max_unsupported_false_commit_rate", "max_no_sign_false_commit_rate", "min_class_recall", "passes_gate"])
    _write_csv(run_dir / "predictions" / "test_predictions.csv", prediction_rows, ["seed", "sample_id", "source", "row_kind", "true_gloss", "accept_probability", "sign_pred", "sign_confidence", "final_pred", "accepted", "correct"])
    _write_json(run_dir / "metrics" / "open_set_metrics.json", result)
    _write_json(run_dir / "logs" / "run_summary.json", {"passed": passed, "summary": summary, "selected_policy": policy})
    return result


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["pilot_config.json", "pilot_manifest.csv", "selected_classes.csv", "README_RUN.md"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    config = {}
    if (run_dir / "pilot_config.json").exists():
        config = _load_json(run_dir / "pilot_config.json", "E5-I config")
    dataset_path = run_dir / "dataset" / "open_set_features.npz"
    if args.require_dataset and not dataset_path.exists():
        errors.append("missing output: dataset/open_set_features.npz")
    if dataset_path.exists() and config:
        data = np.load(dataset_path, allow_pickle=False)
        if tuple(data["landmarks"].shape[1:]) != (96, 258):
            errors.append(f"dataset shape mismatch: {list(data['landmarks'].shape)}")
        if args.require_full_dataset and int(data["landmarks"].shape[0]) != int(config.get("active_rows", -1)):
            errors.append("dataset row count mismatch")
    metrics_path = run_dir / "metrics" / "open_set_metrics.json"
    if args.require_metrics and not metrics_path.exists():
        errors.append("missing output: metrics/open_set_metrics.json")
    if metrics_path.exists() and args.require_metrics:
        metrics = _load_json(metrics_path, "E5-I metrics")
        if metrics.get("experiment") != "e5_i_open_set_reject_head_v1":
            errors.append("unexpected experiment id")
        if not isinstance(metrics.get("passed"), bool):
            errors.append("metrics missing boolean passed field")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E5-I explicit open-set/rejection landmark experiment")
    sub = parser.add_subparsers(dest="command", required=True)

    prep = sub.add_parser("prepare")
    prep.add_argument("--e5g-run", type=Path, default=DEFAULT_E5G_RUN)
    prep.add_argument("--e5d-run", type=Path, default=DEFAULT_E5D_RUN)
    prep.add_argument("--nosign-run", type=Path, default=DEFAULT_NOSIGN_RUN)
    prep.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prep.add_argument("--supported-classes", nargs="+", default=DEFAULT_SUPPORTED)
    prep.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    prep.add_argument("--epochs", type=int, default=24)
    prep.add_argument("--batch-size", type=int, default=32)
    prep.add_argument("--learning-rate", type=float, default=8e-4)
    prep.add_argument("--sign-loss-weight", type=float, default=1.0)
    prep.add_argument("--accept-loss-weight", type=float, default=1.0)
    prep.add_argument("--accepted-precision-min", type=float, default=0.90)
    prep.add_argument("--positive-coverage-min", type=float, default=0.65)
    prep.add_argument("--unsupported-false-commit-rate-max", type=float, default=0.20)
    prep.add_argument("--no-sign-false-commit-rate-max", type=float, default=0.05)
    prep.add_argument("--min-class-recall-min", type=float, default=0.55)
    prep.add_argument("--overwrite", action="store_true")

    smoke_p = sub.add_parser("smoke")
    smoke_p.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    smoke_p.add_argument("--rows", type=int, default=32)

    run_p = sub.add_parser("run")
    run_p.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    run_p.add_argument("--resume", action="store_true")
    run_p.add_argument("--accept-thresholds", nargs="+", type=float, default=[0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95])
    run_p.add_argument("--sign-thresholds", nargs="+", type=float, default=[0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90])

    check_p = sub.add_parser("check")
    check_p.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    check_p.add_argument("--require-dataset", action="store_true")
    check_p.add_argument("--require-full-dataset", action="store_true")
    check_p.add_argument("--require-metrics", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "smoke":
            result = smoke(args)
        elif args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileExistsError, FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e5-i] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
