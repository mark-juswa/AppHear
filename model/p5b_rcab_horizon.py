"""P5-B RCA-B fresh-100 controlled horizon runner.

Long training is user-run only. The trainer changes only the epoch ceiling relative to P5-B.
Its resumable TensorFlow checkpoint includes model, AdamW slots, dropout seed-generator state,
the shuffled training iterator, completed epoch, best validation metric, and early-stop wait.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
import numpy as np  # noqa: E402

from model.p5b_temporal_baseline import (  # noqa: E402
    classification_metrics,
    clip_probs,
    load_split,
    missingness,
)
from model.p5b_temporal_baseline import build_model as build_baseline_model  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5b_rcab_preparation_01"
CONTRACT = PREP / "p5b_rcab_training_horizon_contract.json"
RUN = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5b_rcab_horizon_01"
BASELINE = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5b_baseline_01"
DATA = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5b_migration_01/dataset"
EXPECTED_CONTRACT_SHA256 = "f5e623113ee4a7c1f0ca8374bc41e6a6f7957ed39f302f0e2dfff150978f677a"
EXPECTED_DATA_HASHES = {
    "train": "a2261ea8d61e5eed1a526da0493da5b36c1bb54432ccef7f7479d6ca94634f11",
    "val": "627275d03087f49fda65138253425131e35fe9c5cb8ded6a93b914484be5afe2",
    "test": "a0a7c46803b20ca984d08dd8ce80b8aab24c561333d14fd2538e7b415c4a0518",
}
EXPECTED_BASELINE_CHECKPOINT = "e0ea93a7bfac5935e8720e6f11597ba5a73df624579ff68330969fa6c7aa7e68"
MAX_EPOCHS = 100
PATIENCE = 8
BATCH = 32
SEED = 101
STEPS_PER_EPOCH = math.ceil(3926 / BATCH)
HISTORY_FIELDS = [
    "epoch", "phase", "continuation_boundary", "loss", "pf_acc", "val_loss",
    "val_pf_acc", "learning_rate", "optimizer_iterations",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def atomic_model_save(model: Any, path: Path) -> None:
    temp = path.with_name(path.stem + ".tmp.keras")
    if temp.exists():
        temp.unlink()
    model.save(temp)
    os.replace(temp, path)


def build_model() -> Any:
    import tensorflow as tf
    tf.keras.utils.set_random_seed(SEED)
    model = build_baseline_model(236)
    model.optimizer.build(model.trainable_variables)
    return model


def train_dataset(x: np.ndarray, y: np.ndarray, mask: np.ndarray) -> Any:
    import tensorflow as tf
    ypf = np.repeat(y[:, None], 96, axis=1)
    ds = tf.data.Dataset.from_tensor_slices((x, ypf, mask.astype(np.float32)))
    ds = ds.shuffle(len(x), seed=SEED, reshuffle_each_iteration=True)
    return ds.batch(BATCH).prefetch(tf.data.AUTOTUNE).repeat()


def val_dataset(x: np.ndarray, y: np.ndarray, mask: np.ndarray) -> Any:
    import tensorflow as tf
    ypf = np.repeat(y[:, None], 96, axis=1)
    return tf.data.Dataset.from_tensor_slices((x, ypf, mask.astype(np.float32))).batch(BATCH).prefetch(tf.data.AUTOTUNE)


def keras_fit_dataset(iterator: Any) -> Any:
    """Expose a checkpointed iterator through a Keras-supported Dataset boundary."""
    import tensorflow as tf
    return tf.data.Dataset.from_generator(lambda: iterator, output_signature=iterator.element_spec)


def preflight(include_test: bool = False) -> dict[str, Any]:
    if sha256(CONTRACT) != EXPECTED_CONTRACT_SHA256:
        raise RuntimeError("P5B_RCAB_CONTRACT_HASH_MISMATCH")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract["selected_path"] != "PATH_B_FRESH100" or contract["training"]["maximum_total_epochs"] != 100:
        raise RuntimeError("P5B_RCAB_CONTRACT_CONTENT_MISMATCH")
    if sha256(BASELINE / "best.keras") != EXPECTED_BASELINE_CHECKPOINT:
        raise RuntimeError("P5B_RCAB_BASELINE_CHECKPOINT_MISMATCH")
    names = ["train", "val"] + (["test"] if include_test else [])
    for name in names:
        if sha256(DATA / f"{name}.npz") != EXPECTED_DATA_HASHES[name]:
            raise RuntimeError(f"P5B_RCAB_{name.upper()}_HASH_MISMATCH")
    loaded = {name: load_split(name) for name in names}
    return {
        "passed": True, "selected_path": "PATH_B_FRESH100",
        "contract_sha256": EXPECTED_CONTRACT_SHA256,
        "counts": {name: len(values[1]) for name, values in loaded.items()},
        "maximum_total_epochs": MAX_EPOCHS, "test_loaded": include_test,
    }


def checkpoint_bundle(model: Any, iterator: Any) -> tuple[Any, Any, Any, Any, Any]:
    import tensorflow as tf
    completed = tf.Variable(0, trainable=False, dtype=tf.int64, name="completed_epochs")
    best = tf.Variable(-np.inf, trainable=False, dtype=tf.float64, name="best_val_pf_acc")
    wait = tf.Variable(0, trainable=False, dtype=tf.int64, name="early_stop_wait")
    seed_states = {
        f"dropout_seed_state_{index}": variable
        for index, variable in enumerate(model.non_trainable_variables)
        if "seed_generator_state" in variable.name
    }
    checkpoint = tf.train.Checkpoint(
        model=model, optimizer=model.optimizer, train_iterator=iterator,
        completed_epochs=completed, best_val_pf_acc=best, early_stop_wait=wait,
        **seed_states,
    )
    return checkpoint, completed, best, wait, tf.train.CheckpointManager(checkpoint, str(RUN / "resume_state"), max_to_keep=2)


def initialize_history() -> None:
    path = RUN / "history_extended.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.DictWriter(f, fieldnames=HISTORY_FIELDS).writeheader()


def append_history(row: dict[str, Any]) -> None:
    with (RUN / "history_extended.csv").open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        writer.writerow(row)
        f.flush()
        os.fsync(f.fileno())


def unstarted_run_shell() -> bool:
    """Recognize the harmless header-only shell left by a pre-epoch failure."""
    history = RUN / "history_extended.csv"
    if not RUN.is_dir() or not history.is_file():
        return False
    disallowed = [RUN / "run_state.json", RUN / "best.keras", RUN / "latest.keras", RUN / "resume_state"]
    if any(path.exists() for path in disallowed):
        return False
    with history.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return not rows and {path.name for path in RUN.iterdir()} == {history.name}


def train(resume: bool) -> int:
    import tensorflow as tf
    preflight(False)
    xtr, ytr, mtr, _, _ = load_split("train")
    xv, yv, mv, _, _ = load_split("val")
    iterator = iter(train_dataset(xtr, ytr, mtr))
    training = keras_fit_dataset(iterator)
    validation = val_dataset(xv, yv, mv)
    model = build_model()
    checkpoint, completed, best, wait, manager = checkpoint_bundle(model, iterator)
    state_path = RUN / "run_state.json"

    if resume:
        if not manager.latest_checkpoint or not state_path.is_file():
            raise RuntimeError("P5B_RCAB_NO_RESUMABLE_CHECKPOINT")
        status = checkpoint.restore(manager.latest_checkpoint)
        status.assert_existing_objects_matched()
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if int(completed.numpy()) != int(state["completed_epochs"]):
            raise RuntimeError("P5B_RCAB_STATE_CHECKPOINT_EPOCH_MISMATCH")
    else:
        if RUN.exists() and any((RUN / name).exists() for name in ["run_state.json", "history_extended.csv", "resume_state"]):
            if not unstarted_run_shell():
                raise RuntimeError("P5B_RCAB_RUN_EXISTS_USE_RESUME")
        else:
            RUN.mkdir(parents=True, exist_ok=True)
            initialize_history()
        state = {"completed_epochs": 0, "best_val_pf_acc": None, "early_stop_wait": 0, "status": "RUNNING"}

    start = int(completed.numpy())
    if start >= MAX_EPOCHS or state.get("status") in {"EARLY_STOPPED", "MAX_EPOCH_REACHED"}:
        print(json.dumps({**state, "message": "RCA-B training already complete"}, indent=2))
        return 0

    for epoch in range(start, MAX_EPOCHS):
        history = model.fit(
            training, steps_per_epoch=STEPS_PER_EPOCH,
            validation_data=validation, initial_epoch=epoch, epochs=epoch + 1,
            verbose=2, shuffle=False,
        )
        metrics = {key: float(values[-1]) for key, values in history.history.items()}
        value = metrics["val_pf_acc"]
        improved = value > float(best.numpy())
        if improved:
            best.assign(value); wait.assign(0)
            atomic_model_save(model, RUN / "best.keras")
        else:
            wait.assign_add(1)
        completed.assign(epoch + 1)
        latest_checkpoint = manager.save(checkpoint_number=epoch + 1)
        atomic_model_save(model, RUN / "latest.keras")
        append_history({
            "epoch": epoch, "phase": "RCAB_FRESH100", "continuation_boundary": int(epoch == 0),
            "loss": metrics["loss"], "pf_acc": metrics["pf_acc"],
            "val_loss": metrics["val_loss"], "val_pf_acc": metrics["val_pf_acc"],
            "learning_rate": float(tf.keras.backend.get_value(model.optimizer.learning_rate)),
            "optimizer_iterations": int(model.optimizer.iterations.numpy()),
        })
        state = {
            "selected_path": "PATH_B_FRESH100", "completed_epochs": int(completed.numpy()),
            "last_completed_epoch": epoch, "best_val_pf_acc": float(best.numpy()),
            "early_stop_wait": int(wait.numpy()), "optimizer_iterations": int(model.optimizer.iterations.numpy()),
            "latest_checkpoint": latest_checkpoint, "status": "RUNNING",
        }
        if int(wait.numpy()) >= PATIENCE:
            state["status"] = "EARLY_STOPPED"
        elif int(completed.numpy()) >= MAX_EPOCHS:
            state["status"] = "MAX_EPOCH_REACHED"
        atomic_json(state_path, state)
        print(json.dumps(state, indent=2), flush=True)
        if state["status"] != "RUNNING":
            break
    return 0


def smoke() -> int:
    import tensorflow as tf
    preflight(False)
    rng = np.random.default_rng(SEED)
    x = rng.normal(size=(8, 96, 238)).astype(np.float32)
    y = np.arange(8, dtype=np.int32) % 236
    m = np.ones((8, 96), dtype=bool)
    with tempfile.TemporaryDirectory(prefix="p5b_rcab_smoke_") as td:
        root = Path(td)
        iterator = iter(train_dataset(x, y, m))
        training = keras_fit_dataset(iterator)
        model = build_model()
        epoch = tf.Variable(0, trainable=False, dtype=tf.int64)
        seed_states = {f"dropout_seed_state_{i}": v for i, v in enumerate(model.non_trainable_variables) if "seed_generator_state" in v.name}
        checkpoint = tf.train.Checkpoint(model=model, optimizer=model.optimizer, train_iterator=iterator, completed_epochs=epoch, **seed_states)
        manager = tf.train.CheckpointManager(checkpoint, str(root / "state"), max_to_keep=1)
        before_iterations = int(model.optimizer.iterations.numpy())
        before_weights = [v.numpy().copy() for v in model.trainable_variables]
        model.fit(training, steps_per_epoch=1, epochs=1, verbose=0, shuffle=False)
        epoch.assign(1)
        saved = manager.save(checkpoint_number=1)
        after_iterations = int(model.optimizer.iterations.numpy())
        changed = any(not np.array_equal(a, b.numpy()) for a, b in zip(before_weights, model.trainable_variables))
        optimizer_after = [v.numpy().copy() for v in model.optimizer.variables]
        model_after = [v.numpy().copy() for v in model.variables]
        expected_next = next(iterator)[1].numpy().copy()

        iterator2 = iter(train_dataset(x, y, m))
        restored = build_model()
        epoch2 = tf.Variable(0, trainable=False, dtype=tf.int64)
        seed_states2 = {f"dropout_seed_state_{i}": v for i, v in enumerate(restored.non_trainable_variables) if "seed_generator_state" in v.name}
        checkpoint2 = tf.train.Checkpoint(model=restored, optimizer=restored.optimizer, train_iterator=iterator2, completed_epochs=epoch2, **seed_states2)
        status = checkpoint2.restore(saved); status.assert_existing_objects_matched()
        actual_next = next(iterator2)[1].numpy().copy()
        optimizer_equal = len(optimizer_after) == len(restored.optimizer.variables) and all(np.array_equal(a,b.numpy()) for a,b in zip(optimizer_after,restored.optimizer.variables))
        model_equal = len(model_after) == len(restored.variables) and all(np.array_equal(a,b.numpy()) for a,b in zip(model_after,restored.variables))
        result = {
            "selected_path": "PATH_B_FRESH100", "synthetic_only": True,
            "optimizer_iterations_before": before_iterations,
            "optimizer_iterations_after_batch": after_iterations,
            "optimizer_iterations_after_reload": int(restored.optimizer.iterations.numpy()),
            "weights_changed": changed, "model_state_equal_after_reload": model_equal,
            "optimizer_state_equal_after_reload": optimizer_equal,
            "iterator_next_batch_equal_after_reload": bool(np.array_equal(expected_next, actual_next)),
            "completed_epoch_after_reload": int(epoch2.numpy()),
        }
        result["passed"] = bool(after_iterations == before_iterations + 1 and changed and model_equal and optimizer_equal and result["iterator_next_batch_equal_after_reload"] and int(epoch2.numpy()) == 1)
        atomic_json(PREP / "p5b_rcab_resume_smoke_test.json", result)
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 2


def status() -> int:
    path = RUN / "run_state.json"
    payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"status": "NOT_STARTED"}
    print(json.dumps(payload, indent=2))
    return 0


def evaluate() -> int:
    import tensorflow as tf
    preflight(True)
    state_path = RUN / "run_state.json"
    if not state_path.is_file() or not (RUN / "best.keras").is_file():
        raise RuntimeError("P5B_RCAB_FINAL_VALIDATION_CHECKPOINT_NOT_FROZEN")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") not in {"EARLY_STOPPED", "MAX_EPOCH_REACHED"}:
        raise RuntimeError("P5B_RCAB_TRAINING_NOT_COMPLETE")
    model = tf.keras.models.load_model(RUN / "best.keras", safe_mode=False)
    x, y, mask, ids, signers = load_split("test")
    probs = clip_probs(model, x, mask); pred = probs.argmax(1); top5 = np.argsort(probs, axis=1)[:, -5:]
    matrix, precision, recall, f1, support, macro = classification_metrics(y, pred, 236)
    miss = missingness(x, mask); both = np.asarray([r["both_observed_fraction"] for r in miss])
    bins = {"strong_both": both >= .9, "moderate": (both >= .5) & (both < .9), "weak_both": both < .5}
    strata = {name: {"n": int(sel.sum()), "top1": float(np.mean(pred[sel] == y[sel])), "macro_f1": classification_metrics(y[sel], pred[sel], 236)[-1]} for name, sel in bins.items()}
    test_ds = val_dataset(x, y, mask); test_eval = model.evaluate(test_ds, verbose=0, return_dict=True)
    summary = {
        "top1": float(np.mean(pred == y)), "top5": float(np.mean([y[i] in top5[i] for i in range(len(y))])),
        "macro_f1": macro, "test_per_frame_loss_accuracy": {k: float(v) for k, v in test_eval.items()},
        "strata": strata, "selected_by": "maximum validation per-frame accuracy only",
        "training_state": state, "passed": True,
    }
    atomic_json(RUN / "evaluation_summary.json", summary)
    np.save(RUN / "confusion_matrix.npy", matrix)
    with (RUN / "test_predictions.csv").open("w", encoding="utf-8", newline="") as f:
        fields = ["sample_id", "signer_group_id", "true_class", "pred_class", "correct", *miss[0].keys()]
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
        for i in range(len(y)): writer.writerow({"sample_id": ids[i], "signer_group_id": signers[i], "true_class": int(y[i]), "pred_class": int(pred[i]), "correct": int(y[i] == pred[i]), **miss[i]})
    with (RUN / "per_class_metrics.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f); writer.writerow(["class_id", "precision", "recall", "f1", "support"])
        for i in range(236): writer.writerow([i, float(precision[i]), float(recall[i]), float(f1[i]), int(support[i])])
    print(json.dumps(summary, indent=2)); return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="P5-B RCA-B controlled fresh-100 training")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    run = sub.add_parser("train"); run.add_argument("--resume", action="store_true")
    sub.add_parser("smoke"); sub.add_parser("status"); sub.add_parser("evaluate")
    args = parser.parse_args()
    if args.command == "preflight": print(json.dumps(preflight(False), indent=2)); return 0
    if args.command == "train": return train(args.resume)
    if args.command == "smoke": return smoke()
    if args.command == "status": return status()
    return evaluate()


if __name__ == "__main__":
    raise SystemExit(main())
