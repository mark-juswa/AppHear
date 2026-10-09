"""P5-D1 matched legacy-258 versus DWPose-V2-238 parity experiment.

The protected primary test is intentionally absent from this module.  All model
selection, evaluation, uncertainty, and temporal diagnostics use TRAIN and
primary validation only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import tempfile
from pathlib import Path
from typing import Any

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import numpy as np  # noqa: E402

from model.p5b_temporal_baseline import classification_metrics  # noqa: E402
from model.model import build_streaming_classifier  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/recognition_upgrade"
LEGACY = BASE / "phase1_full_vocab/dataset_v1"
V2 = BASE / "p5_representation_v2/p5b_migration_01/dataset"
MANIFEST = BASE / "phase1_full_vocab/manifest_01/canonical_manifest.csv"
OUT = BASE / "p5_representation_v2/p5d1_matched_representation_parity_01"
SEEDS = (101, 202, 303)
BRANCHES = {"LEGACY258": (LEGACY, 258), "V2_238": (V2, 238)}
COUNTS = {"train": 3926, "val": 816}
EPOCHS = 100
PATIENCE = 8
BATCH = 32
CLASSES = 236
EXPECTED_RCAB_SHA256 = "3b858ca530b616c0d02ca2eee1d30678d092a039c36e9da38ec5f3d491a94a4c"
HISTORY_FIELDS = [
    "branch", "seed", "epoch", "loss", "pf_acc", "val_loss",
    "val_pf_acc", "learning_rate", "optimizer_iterations",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def context_hashes() -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): sha256(path)
        for path in sorted((ROOT / "context").rglob("*"))
        if path.is_file()
    }


def load_split(branch: str, split: str) -> dict[str, np.ndarray]:
    directory, width = BRANCHES[branch]
    path = directory / f"{split}.npz"
    with np.load(path, allow_pickle=False) as data:
        signer_key = "participant_ids" if branch == "LEGACY258" else "signer_group_ids"
        result = {
            "X": np.asarray(data["X"], dtype=np.float32),
            "y": np.asarray(data["y"], dtype=np.int32),
            "frame_mask": np.asarray(data["frame_mask"], dtype=bool),
            "sample_ids": np.asarray(data["sample_ids"]),
            "signers": np.asarray(data[signer_key]),
        }
        if branch == "LEGACY258":
            result["roles"] = np.asarray(data["roles"])
            result["lengths"] = np.asarray(data["lengths"], dtype=np.int32)
    expected = (COUNTS[split], 96, width)
    if result["X"].shape != expected:
        raise RuntimeError(f"P5D1_{branch}_{split}_SHAPE:{result['X'].shape}")
    if result["frame_mask"].shape != (COUNTS[split], 96):
        raise RuntimeError(f"P5D1_{branch}_{split}_MASK_SHAPE")
    if not np.isfinite(result["X"]).all():
        raise RuntimeError(f"P5D1_{branch}_{split}_NONFINITE")
    return result


def inverse_vocab() -> list[str]:
    legacy = json.loads((LEGACY / "vocab.json").read_text(encoding="utf-8"))
    v2 = json.loads((V2 / "vocab.json").read_text(encoding="utf-8"))
    if legacy != v2 or len(legacy) != CLASSES or sorted(legacy.values()) != list(range(CLASSES)):
        raise RuntimeError("P5D1_VOCABULARY_MISMATCH")
    inverse = [""] * CLASSES
    for gloss, index in legacy.items():
        inverse[int(index)] = gloss
    return inverse


def source_hashes() -> dict[str, str]:
    paths = {
        "legacy_train": LEGACY / "train.npz",
        "legacy_val": LEGACY / "val.npz",
        "legacy_vocab": LEGACY / "vocab.json",
        "v2_train": V2 / "train.npz",
        "v2_val": V2 / "val.npz",
        "v2_vocab": V2 / "vocab.json",
        "canonical_manifest": MANIFEST,
        "rcab_checkpoint": BASE / "p5_representation_v2/p5b_rcab_horizon_01/best.keras",
    }
    return {name: sha256(path) for name, path in paths.items()}


def parity_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    vocab = inverse_vocab()
    with MANIFEST.open("r", encoding="utf-8-sig", newline="") as handle:
        manifest_rows = {row["sample_id"]: row for row in csv.DictReader(handle)}
    output: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"counts": {}, "mismatches": [], "contract_checks": {}}
    for split in ("train", "val"):
        legacy = load_split("LEGACY258", split)
        v2 = load_split("V2_238", split)
        summary["counts"][split] = len(legacy["y"])
        for branch, data in (("LEGACY258", legacy), ("V2_238", v2)):
            padding_zero = bool(np.count_nonzero(data["X"][~data["frame_mask"]]) == 0)
            compact_mask = bool(np.all(np.diff(data["frame_mask"].astype(np.int8), axis=1) <= 0))
            summary["contract_checks"][f"{branch}_{split}"] = {
                "finite": bool(np.isfinite(data["X"]).all()),
                "padding_zero": padding_zero,
                "compact_frame_mask": compact_mask,
            }
            if not padding_zero or not compact_mask:
                summary["mismatches"].append({"split": split, "issue": f"{branch}_TENSOR_CONTRACT"})
        # V2 has 59 landmark quartets: x, y, score, valid. Invalid quartets
        # must be exactly zero, and observed masks are binary perception state.
        quartets = v2["X"][:, :, :236].reshape(COUNTS[split], 96, 59, 4)
        invalid = quartets[..., 3] == 0
        invalid_zero = bool(np.count_nonzero(quartets[..., :3][invalid]) == 0)
        valid_binary = bool(np.isin(quartets[..., 3], (0.0, 1.0)).all())
        observed_binary = bool(np.isin(v2["X"][:, :, 236:238], (0.0, 1.0)).all())
        left_unobserved = v2["X"][:, :, 236] == 0
        right_unobserved = v2["X"][:, :, 237] == 0
        unobserved_zero = bool(
            np.count_nonzero(v2["X"][:, :, :84][left_unobserved]) == 0
            and np.count_nonzero(v2["X"][:, :, 84:168][right_unobserved]) == 0
        )
        summary["contract_checks"][f"V2_238_{split}"].update({
            "invalid_landmarks_zero": invalid_zero,
            "valid_masks_binary": valid_binary,
            "observed_masks_binary": observed_binary,
            "unobserved_hand_blocks_zero": unobserved_zero,
        })
        if not all((invalid_zero, valid_binary, observed_binary, unobserved_zero)):
            summary["mismatches"].append({"split": split, "issue": "V2_MISSINGNESS_CONTRACT"})
        for index in range(COUNTS[split]):
            legacy_id = str(legacy["sample_ids"][index])
            v2_id = str(v2["sample_ids"][index])
            sample_id = legacy_id if legacy_id == v2_id else f"{legacy_id}|{v2_id}"
            manifest = manifest_rows.get(legacy_id, {})
            label_equal = bool(legacy["y"][index] == v2["y"][index])
            signer_equal = bool(str(legacy["signers"][index]) == str(v2["signers"][index]))
            mask_equal = bool(np.array_equal(legacy["frame_mask"][index], v2["frame_mask"][index]))
            role = str(legacy["roles"][index])
            role_equal = bool(manifest.get("role") == role)
            identity_equal = legacy_id == v2_id
            class_equal = bool(
                manifest
                and int(manifest["class_id"]) == int(legacy["y"][index])
                and manifest["canonical_gloss"] == vocab[int(legacy["y"][index])]
            )
            expected_role = role in ({"primary_train", "supplement_train"} if split == "train" else {"primary_val"})
            eligible = all((identity_equal, label_equal, signer_equal, mask_equal, role_equal, class_equal, expected_role))
            row = {
                "sample_id": sample_id,
                "gloss": vocab[int(legacy["y"][index])],
                "class_id": int(legacy["y"][index]),
                "signer_group_id": str(legacy["signers"][index]),
                "role": role,
                "legacy_present": 1,
                "v2_present": 1,
                "label_equal": int(label_equal and class_equal),
                "signer_equal": int(signer_equal),
                "mask_equal": int(mask_equal),
                "eligible_for_parity": int(eligible),
            }
            output.append(row)
            if not eligible:
                summary["mismatches"].append({"split": split, "index": index, **row})
        if not np.array_equal(legacy["sample_ids"], v2["sample_ids"]):
            summary["mismatches"].append({"split": split, "issue": "ORDER_MISMATCH"})
        if not np.array_equal(legacy["frame_mask"].sum(axis=1), legacy["lengths"]):
            summary["mismatches"].append({"split": split, "issue": "LEGACY_LENGTH_MASK_MISMATCH"})
    summary["eligible"] = len(output) - len(summary["mismatches"])
    summary["total"] = len(output)
    summary["passed"] = not summary["mismatches"] and len(output) == sum(COUNTS.values())
    return output, summary


def build_model(width: int, seed: int) -> Any:
    import tensorflow as tf

    tf.keras.utils.set_random_seed(seed)
    model = build_streaming_classifier(
        96, width, CLASSES, blocks=4, channels=64,
        dilations=(1, 2, 4, 8), kernel=3, dropout=0.3,
    )
    model.compile(
        optimizer=tf.keras.optimizers.AdamW(5e-4, weight_decay=1e-4),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(),
        weighted_metrics=[tf.keras.metrics.SparseCategoricalAccuracy(name="pf_acc")],
    )
    model.optimizer.build(model.trainable_variables)
    return model


def train_dataset(x: np.ndarray, y: np.ndarray, mask: np.ndarray, seed: int) -> Any:
    import tensorflow as tf

    targets = np.repeat(y[:, None], 96, axis=1)
    dataset = tf.data.Dataset.from_tensor_slices((x, targets, mask.astype(np.float32)))
    return dataset.shuffle(len(x), seed=seed, reshuffle_each_iteration=True).batch(BATCH).prefetch(tf.data.AUTOTUNE).repeat()


def val_dataset(x: np.ndarray, y: np.ndarray, mask: np.ndarray) -> Any:
    import tensorflow as tf

    targets = np.repeat(y[:, None], 96, axis=1)
    return tf.data.Dataset.from_tensor_slices((x, targets, mask.astype(np.float32))).batch(BATCH).prefetch(tf.data.AUTOTUNE)


def fit_dataset(iterator: Any) -> Any:
    import tensorflow as tf

    return tf.data.Dataset.from_generator(lambda: iterator, output_signature=iterator.element_spec)


def run_dir(branch: str, seed: int) -> Path:
    return OUT / "runs" / branch / f"seed_{seed}"


def save_model_atomic(model: Any, path: Path) -> None:
    temporary = path.with_name(path.stem + ".tmp.keras")
    if temporary.exists():
        temporary.unlink()
    model.save(temporary)
    os.replace(temporary, path)


def checkpoint_bundle(model: Any, iterator: Any, directory: Path) -> tuple[Any, Any, Any, Any, Any]:
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
    manager = tf.train.CheckpointManager(checkpoint, str(directory / "resume_state"), max_to_keep=2)
    return checkpoint, completed, best, wait, manager


def contract() -> dict[str, Any]:
    models = {branch: build_model(width, SEEDS[0]) for branch, (_, width) in BRANCHES.items()}
    return {
        "contract_id": "P5D1_MATCHED_REPRESENTATION_PARITY_V1",
        "status": "FROZEN_BEFORE_TRAINING",
        "single_changed_variable": "input representation and required first-layer input width",
        "branches": {
            branch: {"shape": [96, width], "parameter_count": models[branch].count_params()}
            for branch, (_, width) in BRANCHES.items()
        },
        "shared": {
            "classes": CLASSES, "architecture": "4x64 causal TCN",
            "dilations": [1, 2, 4, 8], "kernel": 3, "dropout": 0.3,
            "objective": "per-frame sparse categorical cross entropy",
            "optimizer": "AdamW", "learning_rate": 5e-4, "weight_decay": 1e-4,
            "batch_size": BATCH, "maximum_epochs": EPOCHS, "early_stop_patience": PATIENCE,
            "checkpoint_selection": "maximum primary-validation per-frame accuracy",
            "clip_aggregation": "masked arithmetic mean of per-frame probabilities over real frames",
            "augmentation": "NONE", "warm_start": "NONE", "missingness_augmentation": "NONE",
            "class_weighting": "NONE", "source_balancing": "NONE", "sampling_modification": "NONE",
            "seeds": list(SEEDS), "test_access": False,
        },
        "decision_rule_frozen_before_training": {
            "input_stack_implicated": "all three Top1 deltas LEGACY-V2 positive; at least two signer-blocked 95% intervals exclude zero; mean delta exceeds each branch's across-seed Top1 standard deviation",
            "v2_matched_or_better": "all three Top1 deltas non-positive and V2 median Top1 is at least legacy median Top1",
            "not_primary": "mixed/near-zero deltas whose absolute mean does not exceed observed across-seed stochasticity and no consistent signer-blocked advantage",
            "inconclusive": "parity/integrity failure or seed/sign instability prevents the above determinations",
        },
        "source_hashes": source_hashes(),
    }


def prepare() -> int:
    if OUT.exists():
        raise RuntimeError("P5D1_OUTPUT_EXISTS")
    OUT.mkdir(parents=True)
    context_before = context_hashes()
    hashes_before = source_hashes()
    if hashes_before["rcab_checkpoint"] != EXPECTED_RCAB_SHA256:
        raise RuntimeError("P5D1_RCAB_CHECKPOINT_IDENTITY_MISMATCH")
    rows, summary = parity_rows()
    fields = [
        "sample_id", "gloss", "class_id", "signer_group_id", "role",
        "legacy_present", "v2_present", "label_equal", "signer_equal",
        "mask_equal", "eligible_for_parity",
    ]
    write_csv(OUT / "representation_parity_manifest.csv", rows, fields)
    if not summary["passed"]:
        atomic_json(OUT / "p5d1_integrity.json", {
            "passed": False, "parity": summary,
            "classification": "P5D1_BLOCKED_LEGACY_PARITY_INPUT_UNAVAILABLE",
            "selected_next_gate": "NEXT_TEMPORAL_OBJECTIVE_ABLATION",
            "protected_test_accessed": False,
        })
        print(json.dumps(summary, indent=2))
        return 2
    frozen = contract()
    atomic_json(OUT / "p5d1_training_contract.json", frozen)
    matrix = []
    for branch in BRANCHES:
        for seed in SEEDS:
            matrix.append({
                "branch": branch, "seed": seed, "input_width": BRANCHES[branch][1],
                "parameter_count": frozen["branches"][branch]["parameter_count"],
                "status": "PLANNED", "output_directory": str(run_dir(branch, seed).resolve()),
            })
    write_csv(OUT / "p5d1_run_matrix.csv", matrix, list(matrix[0]))
    roadmap = {
        "gate_1": {
            "name": "CONTROLLED_INPUT_PARITY",
            "legacy_clearly_better": "NEXT_DWPOSE_NATIVE_REPRESENTATION_SUFFICIENCY_AUDIT",
            "parity_or_v2_better": "NEXT_TEMPORAL_OBJECTIVE_ABLATION",
        },
        "gate_2b": {
            "comparison": "per-frame CE versus sequence/clip-level CE; same V2/data/TCN",
            "broad_reproducible_improvement": "TEMPORAL_LEARNING_CAUSAL_CONTRIBUTOR",
            "little_or_no_improvement": "GATE_3_DATA_SUFFICIENCY_LEARNING_CURVE",
        },
        "gate_3": {
            "comparison": "50%/75%/100% signer-aware full-vocabulary TRAIN subsets",
            "strong_positive_scaling": "DATA_LIMITATION_SUPPORTED; audit external data before recording",
            "plateau": "data quantity weakened; return to representation/architecture/label semantics",
        },
        "executed_beyond_gate_1": False,
        "external_data": "DEFERRED_NOT_REJECTED",
    }
    atomic_json(OUT / "p5d1_root_cause_roadmap.json", roadmap)
    hashes_after = source_hashes()
    context_after = context_hashes()
    integrity = {
        "passed": hashes_before == hashes_after and context_before == context_after and summary["passed"],
        "parity": summary, "source_hashes_before": hashes_before, "source_hashes_after": hashes_after,
        "train_count_each_branch": COUNTS["train"], "val_count_each_branch": COUNTS["val"],
        "vocabulary_classes": CLASSES, "no_signer_role_leakage": True,
        "protected_test_accessed": False, "training_performed": False,
        "context_files_modified": context_before != context_after,
        "context_hashes_at_freeze": context_before,
        "progress_tracker_untouched": context_before.get("context/progress-tracker.md") == context_after.get("context/progress-tracker.md"),
    }
    atomic_json(OUT / "p5d1_integrity.json", integrity)
    print(json.dumps({"status": "P5D1_PARITY_PREPARED", "integrity": integrity, "contract_sha256": sha256(OUT / "p5d1_training_contract.json")}, indent=2))
    return 0


def assert_prepared() -> dict[str, Any]:
    integrity = json.loads((OUT / "p5d1_integrity.json").read_text(encoding="utf-8"))
    if not integrity.get("passed"):
        raise RuntimeError("P5D1_PARITY_INTEGRITY_FAILED")
    frozen = json.loads((OUT / "p5d1_training_contract.json").read_text(encoding="utf-8"))
    if frozen["source_hashes"] != source_hashes():
        raise RuntimeError("P5D1_SOURCE_HASH_DRIFT")
    rows, summary = parity_rows()
    if not summary["passed"] or len(rows) != sum(COUNTS.values()):
        raise RuntimeError("P5D1_PARITY_RECHECK_FAILED")
    return frozen


def smoke() -> int:
    import tensorflow as tf

    frozen = assert_prepared()
    results: dict[str, Any] = {"synthetic_only": True, "branches": {}}
    for branch, (_, width) in BRANCHES.items():
        seed = SEEDS[0]
        random.seed(seed); np.random.seed(seed); tf.keras.utils.set_random_seed(seed)
        rng = np.random.default_rng(seed)
        x = rng.normal(size=(8, 96, width)).astype(np.float32)
        y = np.arange(8, dtype=np.int32) % CLASSES
        mask = np.ones((8, 96), dtype=bool)
        model = build_model(width, seed)
        before = int(model.optimizer.iterations.numpy())
        result = model.train_on_batch(x, np.repeat(y[:, None], 96, axis=1), sample_weight=mask.astype(np.float32), return_dict=True)
        with tempfile.TemporaryDirectory(prefix=f"p5d1_{branch.lower()}_") as directory:
            path = Path(directory) / "smoke.keras"
            model.save(path)
            restored = tf.keras.models.load_model(path, safe_mode=False)
            weights_identical = (
                len(model.get_weights()) == len(restored.get_weights())
                and all(np.array_equal(left, right) for left, right in zip(model.get_weights(), restored.get_weights()))
            )
            optimizer_identical = (
                len(model.optimizer.variables) == len(restored.optimizer.variables)
                and all(
                    left.name == right.name and left.shape == right.shape and np.array_equal(left.numpy(), right.numpy())
                    for left, right in zip(model.optimizer.variables, restored.optimizer.variables)
                )
            )
            predictions_identical = bool(np.array_equal(
                model(x[:1], training=False).numpy(), restored(x[:1], training=False).numpy()
            ))
        results["branches"][branch] = {
            "input_shape": list(x.shape), "output_shape": list(model(x[:1], training=False).shape),
            "parameter_count": model.count_params(), "expected_parameter_count": frozen["branches"][branch]["parameter_count"],
            "optimizer_iteration_incremented": int(model.optimizer.iterations.numpy()) == before + 1,
            "finite_loss": bool(np.isfinite(float(result["loss"]))),
            "reload_weights_identical": weights_identical,
            "reload_optimizer_identical": optimizer_identical,
            "reload_predictions_identical": predictions_identical,
        }
    results["passed"] = all(
        row["output_shape"] == [1, 96, CLASSES]
        and row["parameter_count"] == row["expected_parameter_count"]
        and row["optimizer_iteration_incremented"] and row["finite_loss"]
        and row["reload_weights_identical"] and row["reload_optimizer_identical"]
        and row["reload_predictions_identical"]
        for row in results["branches"].values()
    )
    atomic_json(OUT / "p5d1_smoke_results.json", results)
    print(json.dumps(results, indent=2))
    return 0 if results["passed"] else 2


def set_run_status(branch: str, seed: int, status: str) -> None:
    path = OUT / "p5d1_run_matrix.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if row["branch"] == branch and int(row["seed"]) == seed:
            row["status"] = status
    write_csv(path, rows, list(rows[0]))


def train(branch: str, seed: int, resume: bool) -> int:
    import tensorflow as tf

    assert_prepared()
    data = load_split(branch, "train")
    validation = load_split(branch, "val")
    directory = run_dir(branch, seed)
    state_path = directory / "run_state.json"
    history_path = directory / "history.csv"
    if resume:
        if not directory.is_dir() or not state_path.is_file():
            raise RuntimeError("P5D1_NO_RESUMABLE_STATE")
    else:
        if directory.exists():
            raise RuntimeError("P5D1_RUN_EXISTS_USE_RESUME")
        directory.mkdir(parents=True)
        write_csv(history_path, [], HISTORY_FIELDS)
    random.seed(seed); np.random.seed(seed); tf.keras.utils.set_random_seed(seed)
    iterator = iter(train_dataset(data["X"], data["y"], data["frame_mask"], seed))
    fit_data = fit_dataset(iterator)
    validation_data = val_dataset(validation["X"], validation["y"], validation["frame_mask"])
    model = build_model(BRANCHES[branch][1], seed)
    checkpoint, completed, best, wait, manager = checkpoint_bundle(model, iterator, directory)
    if resume:
        if not manager.latest_checkpoint:
            raise RuntimeError("P5D1_NO_RESUMABLE_STATE")
        status = checkpoint.restore(manager.latest_checkpoint)
        status.assert_existing_objects_matched()
    start = int(completed.numpy())
    set_run_status(branch, seed, "RUNNING")
    steps = math.ceil(COUNTS["train"] / BATCH)
    for epoch in range(start, EPOCHS):
        history = model.fit(
            fit_data, steps_per_epoch=steps, validation_data=validation_data,
            initial_epoch=epoch, epochs=epoch + 1, verbose=2, shuffle=False,
        )
        metrics = {key: float(values[-1]) for key, values in history.history.items()}
        improved = metrics["val_pf_acc"] > float(best.numpy())
        if improved:
            best.assign(metrics["val_pf_acc"]); wait.assign(0)
            save_model_atomic(model, directory / "best.keras")
        else:
            wait.assign_add(1)
        completed.assign(epoch + 1)
        checkpoint_path = manager.save(checkpoint_number=epoch + 1)
        save_model_atomic(model, directory / "latest.keras")
        with history_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=HISTORY_FIELDS)
            writer.writerow({
                "branch": branch, "seed": seed, "epoch": epoch,
                "loss": metrics["loss"], "pf_acc": metrics["pf_acc"],
                "val_loss": metrics["val_loss"], "val_pf_acc": metrics["val_pf_acc"],
                "learning_rate": float(tf.keras.backend.get_value(model.optimizer.learning_rate)),
                "optimizer_iterations": int(model.optimizer.iterations.numpy()),
            })
            handle.flush(); os.fsync(handle.fileno())
        run_status = "RUNNING"
        if int(wait.numpy()) >= PATIENCE:
            run_status = "EARLY_STOPPED"
        elif epoch + 1 >= EPOCHS:
            run_status = "MAX_EPOCH_REACHED"
        state = {
            "branch": branch, "seed": seed, "completed_epochs": epoch + 1,
            "last_completed_epoch": epoch, "best_val_pf_acc": float(best.numpy()),
            "early_stop_wait": int(wait.numpy()), "optimizer_iterations": int(model.optimizer.iterations.numpy()),
            "latest_checkpoint": checkpoint_path, "status": run_status,
        }
        atomic_json(state_path, state)
        print(json.dumps(state), flush=True)
        if run_status != "RUNNING":
            set_run_status(branch, seed, run_status)
            break
    return 0


def train_all() -> int:
    assert_prepared()
    for branch in BRANCHES:
        for seed in SEEDS:
            directory = run_dir(branch, seed)
            resume = directory.exists()
            state_path = directory / "run_state.json"
            if state_path.is_file():
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if state.get("status") in {"EARLY_STOPPED", "MAX_EPOCH_REACHED"}:
                    continue
            train(branch, seed, resume)
    return 0


def clip_probabilities(model: Any, x: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    frame_probabilities = np.asarray(model.predict(x, batch_size=BATCH, verbose=0), dtype=np.float64)
    denominator = np.maximum(mask.sum(axis=1, keepdims=True), 1)
    clip = (frame_probabilities * mask[:, :, None]).sum(axis=1) / denominator
    return clip, frame_probabilities


def macro_f1(y: np.ndarray, prediction: np.ndarray) -> float:
    return float(classification_metrics(y, prediction, CLASSES)[-1])


def evaluate_run(branch: str, seed: int) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, np.ndarray]]:
    import tensorflow as tf

    directory = run_dir(branch, seed)
    state = json.loads((directory / "run_state.json").read_text(encoding="utf-8"))
    if state["status"] not in {"EARLY_STOPPED", "MAX_EPOCH_REACHED"}:
        raise RuntimeError(f"P5D1_RUN_INCOMPLETE:{branch}:{seed}")
    with (directory / "history.csv").open("r", encoding="utf-8", newline="") as handle:
        history = list(csv.DictReader(handle))
    selected = max(history, key=lambda row: float(row["val_pf_acc"]))
    model = tf.keras.models.load_model(directory / "best.keras", safe_mode=False)
    val = load_split(branch, "val")
    clip, frame = clip_probabilities(model, val["X"], val["frame_mask"])
    prediction = clip.argmax(axis=1)
    top5 = np.argsort(clip, axis=1)[:, -5:]
    overall = {
        "branch": branch, "seed": seed,
        "selected_epoch": int(selected["epoch"]), "completed_epochs": int(state["completed_epochs"]),
        "parameter_count": model.count_params(), "checkpoint_sha256": sha256(directory / "best.keras"),
        "train_loss": float(selected["loss"]), "train_pf_accuracy": float(selected["pf_acc"]),
        "validation_loss": float(selected["val_loss"]), "pf_accuracy": float(selected["val_pf_acc"]),
        "train_validation_pf_gap": float(selected["pf_acc"]) - float(selected["val_pf_acc"]),
        "top1": float(np.mean(prediction == val["y"])),
        "top5": float(np.mean([val["y"][i] in top5[i] for i in range(len(val["y"]))])),
        "macro_f1": macro_f1(val["y"], prediction),
    }
    signer_rows = []
    for signer in sorted(set(map(str, val["signers"]))):
        selected_signer = np.asarray([str(value) == signer for value in val["signers"]])
        signer_rows.append({
            "branch": branch, "seed": seed, "signer_group_id": signer,
            "clips": int(selected_signer.sum()),
            "top1": float(np.mean(prediction[selected_signer] == val["y"][selected_signer])),
            "macro_f1": macro_f1(val["y"][selected_signer], prediction[selected_signer]),
        })
    taxonomy = []
    labels = val["y"]
    for index in np.flatnonzero(prediction != labels):
        real = np.flatnonzero(val["frame_mask"][index])
        competitor = int(prediction[index])
        thirds = np.array_split(real, 3)
        margins = []
        for third in thirds:
            margins.append(float(np.mean(frame[index, third, labels[index]] - frame[index, third, competitor])) if len(third) else 0.0)
        frame_margin = frame[index, real, labels[index]] - frame[index, real, competitor]
        if all(value < 0 for value in margins):
            category = "PERSISTENT_WRONG_CLASS"
        elif float(np.mean(frame_margin > 0)) > 0.5:
            category = "TRUE_TEMPORAL_MAJORITY_BUT_FINAL_WRONG"
        elif any(value > 0 for value in margins) and any(value < 0 for value in margins):
            category = "PHASE_DEPENDENT_CONFUSION"
        else:
            category = "OTHER"
        taxonomy.append({
            "branch": branch, "seed": seed, "sample_id": str(val["sample_ids"][index]),
            "signer_group_id": str(val["signers"][index]), "true_class": int(labels[index]),
            "predicted_class": competitor, "category": category,
            "first_third_true_minus_wrong": margins[0], "middle_third_true_minus_wrong": margins[1],
            "final_third_true_minus_wrong": margins[2], "true_frame_majority_fraction": float(np.mean(frame_margin > 0)),
        })
    arrays = {"y": labels, "prediction": prediction, "clip": clip, "signers": val["signers"]}
    return overall, signer_rows, taxonomy, arrays


def signer_bootstrap(left: dict[str, np.ndarray], right: dict[str, np.ndarray], seed: int) -> list[dict[str, Any]]:
    y = left["y"]
    if not np.array_equal(y, right["y"]) or not np.array_equal(left["signers"], right["signers"]):
        raise RuntimeError("P5D1_BOOTSTRAP_ALIGNMENT_FAILURE")
    signers = sorted(set(map(str, left["signers"])))
    indices = {signer: np.flatnonzero(np.asarray([str(value) == signer for value in left["signers"]])) for signer in signers}
    rng = np.random.Generator(np.random.PCG64(seed))
    top1_delta = np.empty(10_000, dtype=np.float64)
    macro_delta = np.empty(10_000, dtype=np.float64)
    for replicate in range(10_000):
        draw = rng.choice(signers, size=len(signers), replace=True)
        chosen = np.concatenate([indices[str(signer)] for signer in draw])
        top1_delta[replicate] = np.mean(left["prediction"][chosen] == y[chosen]) - np.mean(right["prediction"][chosen] == y[chosen])
        macro_delta[replicate] = macro_f1(y[chosen], left["prediction"][chosen]) - macro_f1(y[chosen], right["prediction"][chosen])
    return [
        {"seed": seed, "metric": "Top1", "point_delta_legacy_minus_v2": float(np.mean(left["prediction"] == y) - np.mean(right["prediction"] == y)), "ci95_low": float(np.percentile(top1_delta, 2.5)), "ci95_high": float(np.percentile(top1_delta, 97.5)), "replicates": 10_000, "cluster_unit": "signer"},
        {"seed": seed, "metric": "MacroF1", "point_delta_legacy_minus_v2": macro_f1(y, left["prediction"]) - macro_f1(y, right["prediction"]), "ci95_low": float(np.percentile(macro_delta, 2.5)), "ci95_high": float(np.percentile(macro_delta, 97.5)), "replicates": 10_000, "cluster_unit": "signer"},
    ]


def finalize() -> int:
    frozen = assert_prepared()
    context_before = context_hashes(); hashes_before = source_hashes()
    metrics: list[dict[str, Any]] = []
    signer_rows: list[dict[str, Any]] = []
    taxonomy: list[dict[str, Any]] = []
    arrays: dict[tuple[str, int], dict[str, np.ndarray]] = {}
    history_rows: list[dict[str, Any]] = []
    for branch in BRANCHES:
        for seed in SEEDS:
            overall, signers, failures, saved = evaluate_run(branch, seed)
            metrics.append(overall); signer_rows.extend(signers); taxonomy.extend(failures); arrays[(branch, seed)] = saved
            with (run_dir(branch, seed) / "history.csv").open("r", encoding="utf-8", newline="") as handle:
                history_rows.extend(list(csv.DictReader(handle)))
    write_csv(OUT / "p5d1_training_histories.csv", history_rows, HISTORY_FIELDS)
    metric_fields = list(metrics[0])
    write_csv(OUT / "p5d1_validation_metrics.csv", metrics, metric_fields)
    write_csv(OUT / "p5d1_validation_by_signer.csv", signer_rows, list(signer_rows[0]))
    write_csv(OUT / "p5d1_temporal_failure_taxonomy.csv", taxonomy, list(taxonomy[0]))
    deltas = []
    for seed in SEEDS:
        legacy = next(row for row in metrics if row["branch"] == "LEGACY258" and row["seed"] == seed)
        v2 = next(row for row in metrics if row["branch"] == "V2_238" and row["seed"] == seed)
        deltas.append({"seed": seed, **{f"{metric}_legacy_minus_v2": legacy[metric] - v2[metric] for metric in ("top1", "top5", "macro_f1", "pf_accuracy")}})
    for statistic, function in (("mean", np.mean), ("median", np.median), ("min", np.min), ("max", np.max), ("std", lambda values: np.std(values, ddof=0))):
        deltas.append({"seed": statistic, **{f"{metric}_legacy_minus_v2": float(function([row[f"{metric}_legacy_minus_v2"] for row in deltas[:3]])) for metric in ("top1", "top5", "macro_f1", "pf_accuracy")}})
    write_csv(OUT / "p5d1_seed_paired_deltas.csv", deltas, list(deltas[0]))
    uncertainty = []
    for seed in SEEDS:
        uncertainty.extend(signer_bootstrap(arrays[("LEGACY258", seed)], arrays[("V2_238", seed)], seed))
    write_csv(OUT / "p5d1_signer_blocked_uncertainty.csv", uncertainty, list(uncertainty[0]))
    top_deltas = [float(row["top1_legacy_minus_v2"]) for row in deltas[:3]]
    legacy_top = [row["top1"] for row in metrics if row["branch"] == "LEGACY258"]
    v2_top = [row["top1"] for row in metrics if row["branch"] == "V2_238"]
    positive_intervals = sum(row["ci95_low"] > 0 for row in uncertainty if row["metric"] == "Top1")
    stochasticity = max(float(np.std(legacy_top)), float(np.std(v2_top)))
    mean_delta = float(np.mean(top_deltas))
    if all(value > 0 for value in top_deltas) and positive_intervals >= 2 and mean_delta > stochasticity:
        classification = "CURRENT_DWPOSE_V2_INPUT_STACK_IMPLICATED"
        next_gate = "NEXT_DWPOSE_NATIVE_REPRESENTATION_SUFFICIENCY_AUDIT"
        confidence = "HIGH" if positive_intervals == 3 else "MODERATE"
    elif all(value <= 0 for value in top_deltas) and np.median(v2_top) >= np.median(legacy_top):
        classification = "V2_MATCHED_OR_BETTER_THAN_LEGACY"
        next_gate = "NEXT_TEMPORAL_OBJECTIVE_ABLATION"; confidence = "MODERATE"
    elif abs(mean_delta) <= stochasticity and positive_intervals == 0:
        classification = "INPUT_STACK_NOT_PRIMARY_UNDER_MATCHED_TRAINING"
        next_gate = "NEXT_TEMPORAL_OBJECTIVE_ABLATION"; confidence = "MODERATE"
    else:
        classification = "REPRESENTATION_PARITY_EXPERIMENT_INCONCLUSIVE"
        next_gate = "NEXT_TEMPORAL_OBJECTIVE_ABLATION"; confidence = "LOW"
    summaries = {}
    for branch in BRANCHES:
        rows = [row for row in metrics if row["branch"] == branch]
        summaries[branch] = {metric: float(np.median([row[metric] for row in rows])) for metric in ("top1", "top5", "macro_f1", "pf_accuracy")}
    persistent = {
        branch: int(sum(row["category"] == "PERSISTENT_WRONG_CLASS" for row in taxonomy if row["branch"] == branch))
        for branch in BRANCHES
    }
    decision = {
        "classification": classification, "confidence": confidence, "selected_next_gate": next_gate,
        "median_metrics": summaries, "paired_seed_top1_deltas": top_deltas,
        "positive_signer_blocked_top1_intervals": positive_intervals,
        "across_seed_top1_stochasticity": stochasticity,
        "persistent_wrong_class_counts_across_seed_sample_errors": persistent,
        "what_this_establishes": "Matched from-scratch evidence about the broader legacy-versus-V2 input stack on governed TRAIN/primary-validation populations.",
        "what_this_does_not_establish": "It does not isolate MediaPipe vs DWPose, Z, normalization, masks, slot semantics, or any single V2 component.",
        "protected_test_accessed": False,
    }
    atomic_json(OUT / "p5d1_decision.json", decision)
    hashes_after = source_hashes(); context_after = context_hashes()
    integrity_path = OUT / "p5d1_integrity.json"
    integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
    frozen_context = integrity.get("context_hashes_at_freeze", {})
    integrity.update({
        "passed": integrity["passed"] and hashes_before == hashes_after and context_before == context_after and frozen_context == context_after,
        "source_hashes_after_training": hashes_after, "training_performed": True,
        "six_runs_complete": len(metrics) == 6, "protected_test_accessed": False,
        "context_files_modified": frozen_context != context_after,
        "progress_tracker_untouched": frozen_context.get("context/progress-tracker.md") == context_after.get("context/progress-tracker.md"),
    })
    atomic_json(integrity_path, integrity)
    result = f"""# P5-D1 Matched Representation Parity Result

Parity integrity: {'PASS' if integrity['passed'] else 'FAIL'}.

Six from-scratch runs compared frozen legacy `[96,258]` against DWPose V2 `[96,238]` under the same causal TCN, objective, optimizer, horizon, seeds, sample order, labels, signer roles, masks, and clip aggregation. No protected-test tensor was opened.

## Decision

- Classification: `{classification}`
- Confidence: `{confidence}`
- Next gate: `{next_gate}` (not executed)
- Paired seed Top-1 deltas, legacy minus V2: {', '.join(f'{value:.6f}' for value in top_deltas)}
- Legacy median Top-1: {summaries['LEGACY258']['top1']:.6f}
- V2 median Top-1: {summaries['V2_238']['top1']:.6f}

This establishes only broader input-stack attribution. It does not identify which differing input component is responsible. Sem-Lex and other external data remain deferred, not rejected.
"""
    atomic_text(OUT / "P5D1_MATCHED_REPRESENTATION_PARITY_RESULT.md", result)
    artifacts = []
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name != "artifact_hash_manifest.json":
            artifacts.append({"path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size})
    atomic_json(OUT / "artifact_hash_manifest.json", {
        "artifacts": artifacts,
        "supporting_code": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        "protected_test_accessed": False,
    })
    print(json.dumps({"status": "APPHEAR_P5D1_MATCHED_REPRESENTATION_PARITY_COMPLETE", "decision": decision, "integrity": integrity}, indent=2))
    return 0 if integrity["passed"] else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare")
    commands.add_parser("smoke")
    single = commands.add_parser("train")
    single.add_argument("--branch", choices=tuple(BRANCHES), required=True)
    single.add_argument("--seed", choices=SEEDS, type=int, required=True)
    single.add_argument("--resume", action="store_true")
    commands.add_parser("train-all")
    commands.add_parser("finalize")
    args = parser.parse_args()
    if args.command == "prepare": return prepare()
    if args.command == "smoke": return smoke()
    if args.command == "train": return train(args.branch, args.seed, args.resume)
    if args.command == "train-all": return train_all()
    return finalize()


if __name__ == "__main__":
    raise SystemExit(main())
