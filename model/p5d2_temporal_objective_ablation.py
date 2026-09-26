"""P5-D2 matched temporal-objective ablation.

Only frozen DWPose V2 TRAIN and primary validation are reachable here. The
protected test and external datasets are deliberately absent from this module.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
from pathlib import Path
from typing import Any

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import numpy as np  # noqa: E402

from model.model import build_streaming_classifier  # noqa: E402
from model.p5b_temporal_baseline import classification_metrics  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/recognition_upgrade"
V2 = BASE / "p5_representation_v2/p5b_migration_01/dataset"
MANIFEST = BASE / "phase1_full_vocab/manifest_01/canonical_manifest.csv"
D1 = BASE / "p5_representation_v2/p5d1_matched_representation_parity_01"
OUT = BASE / "p5_representation_v2/p5d2_temporal_objective_ablation_01"
BRANCHES = ("PFCE_MATCHED", "CLIPCE_AGGREGATION_ALIGNED")
SEEDS = (101, 202, 303)
COUNTS = {"train": 3926, "val": 816}
WIDTH = 238
CLASSES = 236
BATCH = 32
EPOCHS = 100
EPSILON = 1e-7
EXPECTED_HASHES = {
    "v2_train": "a2261ea8d61e5eed1a526da0493da5b36c1bb54432ccef7f7479d6ca94634f11",
    "v2_val": "627275d03087f49fda65138253425131e35fe9c5cb8ded6a93b914484be5afe2",
    "v2_vocab": "a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b",
    "canonical_manifest": "8c1fab3df04a0240b5a178853b2206408806958afebdd19bd3d44d6fca606571",
}
HISTORY_FIELDS = [
    "branch", "seed", "epoch", "train_objective_loss", "train_clip_top1",
    "train_pf_accuracy", "validation_clip_nll", "validation_clip_top1",
    "validation_pf_accuracy", "learning_rate", "optimizer_iterations",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tensor_hash(arrays: list[np.ndarray]) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode())
        digest.update(np.asarray(contiguous.shape, dtype=np.int64).tobytes())
        digest.update(contiguous.tobytes())
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
        for path in sorted((ROOT / "context").rglob("*")) if path.is_file()
    }


def source_hashes() -> dict[str, str]:
    paths = {
        "v2_train": V2 / "train.npz",
        "v2_val": V2 / "val.npz",
        "v2_vocab": V2 / "vocab.json",
        "canonical_manifest": MANIFEST,
    }
    return {name: sha256(path) for name, path in paths.items()}


def load_split(split: str) -> dict[str, np.ndarray]:
    with np.load(V2 / f"{split}.npz", allow_pickle=False) as data:
        result = {
            "X": np.asarray(data["X"], dtype=np.float32),
            "y": np.asarray(data["y"], dtype=np.int32),
            "frame_mask": np.asarray(data["frame_mask"], dtype=bool),
            "sample_ids": np.asarray(data["sample_ids"]),
            "signers": np.asarray(data["signer_group_ids"]),
        }
    if result["X"].shape != (COUNTS[split], 96, WIDTH):
        raise RuntimeError(f"P5D2_{split}_SHAPE_MISMATCH:{result['X'].shape}")
    if result["frame_mask"].shape != (COUNTS[split], 96):
        raise RuntimeError(f"P5D2_{split}_MASK_SHAPE")
    return result


def data_integrity() -> dict[str, Any]:
    hashes = source_hashes()
    d1_contract = json.loads((D1 / "p5d1_training_contract.json").read_text(encoding="utf-8"))
    d1_integrity = json.loads((D1 / "p5d1_integrity.json").read_text(encoding="utf-8"))
    vocab = json.loads((V2 / "vocab.json").read_text(encoding="utf-8"))
    with MANIFEST.open("r", encoding="utf-8-sig", newline="") as handle:
        manifest = {row["sample_id"]: row for row in csv.DictReader(handle)}
    checks: dict[str, Any] = {
        "source_hashes": hashes,
        "expected_hashes_equal": hashes == EXPECTED_HASHES,
        "d1_source_hashes_equal": all(d1_contract["source_hashes"][key] == value for key, value in hashes.items()),
        "d1_integrity_passed": bool(d1_integrity.get("passed") and d1_integrity.get("six_runs_complete")),
        "vocabulary_classes": len(vocab),
        "class_ids_exact": sorted(vocab.values()) == list(range(CLASSES)),
        "splits": {},
    }
    split_signers: dict[str, set[str]] = {}
    for split in ("train", "val"):
        data = load_split(split)
        quartets = data["X"][:, :, :236].reshape(COUNTS[split], 96, 59, 4)
        invalid = quartets[..., 3] == 0
        left_unobserved = data["X"][:, :, 236] == 0
        right_unobserved = data["X"][:, :, 237] == 0
        expected_roles = {"primary_train", "supplement_train"} if split == "train" else {"primary_val"}
        lineage = []
        for index, sample_id_value in enumerate(data["sample_ids"]):
            sample_id = str(sample_id_value)
            row = manifest.get(sample_id)
            lineage.append(bool(
                row and row["role"] in expected_roles
                and int(row["class_id"]) == int(data["y"][index])
                and row["signer_group_id"] == str(data["signers"][index])
            ))
        split_checks = {
            "count": len(data["y"]),
            "sample_ids_unique": len(set(map(str, data["sample_ids"]))) == COUNTS[split],
            "labels_in_range": bool(np.all((data["y"] >= 0) & (data["y"] < CLASSES))),
            "finite": bool(np.isfinite(data["X"]).all()),
            "compact_mask": bool(np.all(np.diff(data["frame_mask"].astype(np.int8), axis=1) <= 0)),
            "nonempty_masks": bool(np.all(data["frame_mask"].sum(axis=1) > 0)),
            "padding_zero": bool(np.count_nonzero(data["X"][~data["frame_mask"]]) == 0),
            "invalid_landmarks_zero": bool(np.count_nonzero(quartets[..., :3][invalid]) == 0),
            "valid_masks_binary": bool(np.isin(quartets[..., 3], (0.0, 1.0)).all()),
            "observed_masks_binary": bool(np.isin(data["X"][:, :, 236:238], (0.0, 1.0)).all()),
            "unobserved_hands_zero": bool(
                np.count_nonzero(data["X"][:, :, :84][left_unobserved]) == 0
                and np.count_nonzero(data["X"][:, :, 84:168][right_unobserved]) == 0
            ),
            "manifest_lineage_exact": all(lineage),
        }
        checks["splits"][split] = split_checks
        split_signers[split] = set(map(str, data["signers"]))
    checks["no_signer_role_leakage"] = not bool(split_signers["train"] & split_signers["val"])
    checks["passed"] = bool(
        checks["expected_hashes_equal"] and checks["d1_source_hashes_equal"]
        and checks["d1_integrity_passed"] and checks["vocabulary_classes"] == CLASSES
        and checks["class_ids_exact"] and checks["no_signer_role_leakage"]
        and all(all(value for key, value in row.items() if key != "count") for row in checks["splits"].values())
        and checks["splits"]["train"]["count"] == COUNTS["train"]
        and checks["splits"]["val"]["count"] == COUNTS["val"]
    )
    return checks


def make_model(seed: int) -> Any:
    import tensorflow as tf

    random.seed(seed)
    np.random.seed(seed)
    tf.keras.utils.set_random_seed(seed)
    model = build_streaming_classifier(
        96, WIDTH, CLASSES, blocks=4, channels=64,
        dilations=(1, 2, 4, 8), kernel=3, dropout=0.3,
    )
    if model.count_params() != 163_884 or model.output_shape != (None, 96, CLASSES):
        raise RuntimeError("P5D2_MODEL_CONTRACT_MISMATCH")
    return model


def initialization_path(seed: int) -> Path:
    return OUT / "initializations" / f"seed_{seed}.weights.npz"


def save_initialization(seed: int) -> dict[str, Any]:
    model = make_model(seed)
    arrays = [np.asarray(value) for value in model.get_weights()]
    path = initialization_path(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp.npz")
    np.savez(temporary, **{f"weight_{index:03d}": array for index, array in enumerate(arrays)})
    os.replace(temporary, path)
    return {"path": str(path.resolve()), "file_sha256": sha256(path), "tensor_sha256": tensor_hash(arrays), "weight_arrays": len(arrays)}


def load_initialization(model: Any, seed: int) -> str:
    path = initialization_path(seed)
    with np.load(path, allow_pickle=False) as saved:
        arrays = [np.asarray(saved[key]) for key in sorted(saved.files)]
    model.set_weights(arrays)
    return tensor_hash([np.asarray(value) for value in model.get_weights()])


def batch_permutation(seed: int, epoch: int, count: int = COUNTS["train"]) -> np.ndarray:
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, epoch, 0xD2])))
    return rng.permutation(count)


def clip_probabilities(probabilities: Any, mask: Any) -> Any:
    import tensorflow as tf

    mask_float = tf.cast(mask, probabilities.dtype)
    denominator = tf.maximum(tf.reduce_sum(mask_float, axis=1, keepdims=True), 1.0)
    return tf.reduce_sum(probabilities * mask_float[:, :, None], axis=1) / denominator


def objective_components(branch: str, probabilities: Any, labels: Any, mask: Any) -> tuple[Any, Any]:
    import tensorflow as tf

    if branch == "PFCE_MATCHED":
        targets = tf.repeat(tf.cast(labels[:, None], tf.int32), tf.shape(probabilities)[1], axis=1)
        ce = tf.keras.losses.sparse_categorical_crossentropy(targets, probabilities)
        mask_float = tf.cast(mask, ce.dtype)
        return tf.reduce_sum(ce * mask_float), tf.maximum(tf.reduce_sum(mask_float), 1.0)
    clip = clip_probabilities(probabilities, mask)
    true_probability = tf.gather(clip, tf.cast(labels, tf.int32), axis=1, batch_dims=1)
    loss = -tf.math.log(tf.clip_by_value(true_probability, EPSILON, 1.0))
    return tf.reduce_sum(loss), tf.cast(tf.shape(labels)[0], loss.dtype)


def run_dir(branch: str, seed: int) -> Path:
    return OUT / "runs" / branch / f"seed_{seed}"


def save_model_atomic(model: Any, path: Path) -> None:
    temporary = path.with_name(path.stem + ".tmp.keras")
    if temporary.exists():
        temporary.unlink()
    model.save(temporary)
    os.replace(temporary, path)


def contract() -> dict[str, Any]:
    return {
        "contract_id": "P5D2_MATCHED_TEMPORAL_OBJECTIVE_V1",
        "status": "FROZEN_BEFORE_TRAINING",
        "single_changed_variable": "training objective",
        "data": {"representation": "DWPOSE_REPRESENTATION_V2_238", "shape": [96, 238], "train": 3926, "primary_validation": 816, "classes": 236},
        "model": {"architecture": "4x64 causal TCN", "dilations": [1, 2, 4, 8], "kernel": 3, "dropout": 0.3, "per_frame_output": [96, 236], "parameter_count": 163884, "additional_trainable_parameters": 0},
        "objectives": {
            "PFCE_MATCHED": "sum(real-frame sparse CE)/number of real frames",
            "CLIPCE_AGGREGATION_ALIGNED": "-log(true class of masked arithmetic mean of per-frame softmax probabilities)",
        },
        "shared_training": {"optimizer": "AdamW", "learning_rate": 5e-4, "weight_decay": 1e-4, "batch": 32, "epochs": 100, "early_stopping": "NONE", "checkpoint_selection": "minimum primary-validation clip NLL", "augmentation": "NONE", "warm_start": "NONE", "class_weighting": "NONE", "source_balancing": "NONE", "sampling_modification": "NONE"},
        "inference": "per-frame softmax -> masked arithmetic mean over real frames -> argmax",
        "seeds": list(SEEDS),
        "paired_controls": {"initial_weights": "same seed-specific frozen weight artifact", "batch_order": "same deterministic seed+epoch permutation", "dropout_rng": "same seed-specific initial generator state and one training-mode forward pass per matched batch; exact masks not claimed unless tested"},
        "decision_rule": {
            "TEMPORAL_OBJECTIVE_CAUSAL_CONTRIBUTOR": "Top1 CLIPCE-PFCE >0 all seeds; MacroF1 >0 at least 2/3; at least 2 signer-blocked Top1 CIs have lower bound >0; mean Top1 delta exceeds maximum branch across-seed Top1 SD; no negative mean Top5/MacroF1; persistent failures improve or total errors fall",
            "TEMPORAL_OBJECTIVE_HELPFUL_BUT_NOT_SUFFICIENT": "Top1 improves at least 2/3 seeds with positive mean but strong rule is not met",
            "CLIP_OBJECTIVE_HARMFUL": "Top1 worsens all seeds, mean Top5 and MacroF1 regress, and at least 2 signer-blocked Top1 CIs have upper bound <0",
            "TEMPORAL_OBJECTIVE_NOT_PRIMARY": "all remaining integrity-valid mixed/near-zero patterns",
            "P5D2_INCONCLUSIVE": "integrity, objective, matched-initialization, or matched-order failure only",
        },
        "protected_test_access": False,
        "external_data": "DEFERRED_NOT_REJECTED",
        "source_hashes": source_hashes(),
    }


def prepare() -> int:
    if OUT.exists():
        raise RuntimeError("P5D2_OUTPUT_EXISTS")
    OUT.mkdir(parents=True)
    before_context = context_hashes()
    before_sources = source_hashes()
    integrity = data_integrity()
    if not integrity["passed"]:
        atomic_json(OUT / "p5d2_integrity.json", {"passed": False, "classification": "P5D2_BLOCKED_INPUT_INTEGRITY_FAILURE", "details": integrity, "protected_test_accessed": False})
        print(json.dumps(integrity, indent=2))
        return 2
    initialization_rows: list[dict[str, Any]] = []
    initialization_records: dict[int, dict[str, Any]] = {}
    for seed in SEEDS:
        record = save_initialization(seed)
        initialization_records[seed] = record
        for branch in BRANCHES:
            probe = make_model(seed)
            loaded_hash = load_initialization(probe, seed)
            initialization_rows.append({
                "seed": seed, "branch": branch, "initialization_path": record["path"],
                "initialization_file_sha256": record["file_sha256"],
                "initial_weight_tensor_sha256": loaded_hash,
                "pair_equal": int(loaded_hash == record["tensor_sha256"]),
                "parameter_count": probe.count_params(),
            })
    write_csv(OUT / "p5d2_initialization_parity.csv", initialization_rows, list(initialization_rows[0]))
    frozen_contract = contract()
    atomic_json(OUT / "p5d2_objective_contract.json", frozen_contract)
    run_rows = []
    for seed in SEEDS:
        for branch in BRANCHES:
            run_rows.append({"seed": seed, "branch": branch, "status": "PLANNED", "epochs": EPOCHS, "selection": "minimum_validation_clip_nll", "output_directory": str(run_dir(branch, seed).resolve())})
    write_csv(OUT / "p5d2_run_matrix.csv", run_rows, list(run_rows[0]))
    permutation_audit = []
    for seed in SEEDS:
        for epoch in range(EPOCHS):
            order = batch_permutation(seed, epoch)
            permutation_audit.append({"seed": seed, "epoch": epoch, "permutation_sha256": tensor_hash([order]), "samples": len(order), "unique": len(np.unique(order)) == len(order), "shared_by_branches": True})
    atomic_json(OUT / "p5d2_rng_and_batch_order_audit.json", {
        "initialization": initialization_records,
        "python_seed": "experiment seed before model creation",
        "numpy_seed": "experiment seed before model creation",
        "tensorflow_seed": "tf.keras.utils.set_random_seed(experiment seed)",
        "shuffle": "PCG64 SeedSequence([seed, epoch, 0xD2]); identical within pair",
        "dropout": "same initialized seed-generator state and one training forward per batch; exact mask identity not claimed",
        "epoch_permutations": permutation_audit,
        "passed": all(row["unique"] for row in permutation_audit),
    })
    roadmap = {
        "D1": "input stack not primary/inconclusive matched parity",
        "D2_strong": "temporal learning causal contributor; develop simplest same-TCN objective solution",
        "D2_partial": "retain candidate objective and still test data sufficiency",
        "D2_none_or_harmful": "GATE_3_DATA_SUFFICIENCY_LEARNING_CURVE",
        "D3": "50/75/100 percent signer-aware full-vocabulary train subsets; not executed",
        "external_data": "DEFERRED_NOT_REJECTED",
        "next_gate_executed": False,
    }
    atomic_json(OUT / "p5d2_root_cause_roadmap.json", roadmap)
    after_sources = source_hashes()
    after_context = context_hashes()
    integrity.update({
        "passed": integrity["passed"] and before_sources == after_sources and before_context == after_context,
        "source_hashes_before": before_sources,
        "source_hashes_after": after_sources,
        "context_hashes_at_freeze": before_context,
        "initialization_pairs_equal": all(bool(row["pair_equal"]) for row in initialization_rows),
        "training_performed": False,
        "six_runs_complete": False,
        "protected_test_accessed": False,
        "external_data_used": False,
        "context_files_modified": before_context != after_context,
        "progress_tracker_untouched": before_context.get("context/progress-tracker.md") == after_context.get("context/progress-tracker.md"),
    })
    atomic_json(OUT / "p5d2_integrity.json", integrity)
    print(json.dumps({"status": "P5D2_PREPARED", "integrity_passed": integrity["passed"], "contract_sha256": sha256(OUT / "p5d2_objective_contract.json")}, indent=2))
    return 0


def assert_prepared() -> dict[str, Any]:
    integrity = json.loads((OUT / "p5d2_integrity.json").read_text(encoding="utf-8"))
    frozen = json.loads((OUT / "p5d2_objective_contract.json").read_text(encoding="utf-8"))
    if not integrity.get("passed") or frozen["source_hashes"] != source_hashes():
        raise RuntimeError("P5D2_FROZEN_INTEGRITY_FAILURE")
    return frozen


def unit_tests() -> int:
    import tensorflow as tf

    assert_prepared()
    tests: dict[str, Any] = {}
    probabilities_real = np.asarray([[[0.7, 0.2, 0.1], [0.4, 0.5, 0.1], [0.6, 0.2, 0.2]]], dtype=np.float32)
    padded_5 = np.pad(probabilities_real, ((0, 0), (0, 2), (0, 0)))
    padded_8 = np.pad(probabilities_real, ((0, 0), (0, 5), (0, 0)))
    mask_5 = np.asarray([[1, 1, 1, 0, 0]], dtype=bool)
    mask_8 = np.asarray([[1, 1, 1, 0, 0, 0, 0, 0]], dtype=bool)
    clip_5 = clip_probabilities(tf.constant(padded_5), tf.constant(mask_5)).numpy()
    clip_8 = clip_probabilities(tf.constant(padded_8), tf.constant(mask_8)).numpy()
    loss_5 = float(objective_components("CLIPCE_AGGREGATION_ALIGNED", tf.constant(padded_5), tf.constant([0]), tf.constant(mask_5))[0].numpy())
    loss_8 = float(objective_components("CLIPCE_AGGREGATION_ALIGNED", tf.constant(padded_8), tf.constant([0]), tf.constant(mask_8))[0].numpy())
    tests["padding_invariance"] = {"passed": bool(np.allclose(clip_5, clip_8, atol=1e-7) and np.isclose(loss_5, loss_8, atol=1e-7)), "clip_probability": clip_5.tolist(), "loss": loss_5}
    rng = np.random.default_rng(101)
    logits = rng.normal(size=(4, 7, 6)).astype(np.float32)
    exp = np.exp(logits - logits.max(axis=-1, keepdims=True)); probs = exp / exp.sum(axis=-1, keepdims=True)
    mask = np.asarray([[1] * length + [0] * (7 - length) for length in (7, 5, 3, 1)], dtype=bool)
    manual = (probs * mask[:, :, None]).sum(axis=1) / mask.sum(axis=1, keepdims=True)
    tensorflow_value = clip_probabilities(tf.constant(probs), tf.constant(mask)).numpy()
    tests["numpy_tensorflow_agreement"] = {"passed": bool(np.allclose(manual, tensorflow_value, atol=1e-7)), "max_abs_error": float(np.max(np.abs(manual - tensorflow_value)))}
    one = tf.constant([[[0.1, 0.8, 0.1], [0.0, 0.0, 0.0]]], dtype=tf.float32)
    one_mask = tf.constant([[True, False]]); one_label = tf.constant([1])
    pf_num, pf_den = objective_components("PFCE_MATCHED", one, one_label, one_mask)
    clip_num, clip_den = objective_components("CLIPCE_AGGREGATION_ALIGNED", one, one_label, one_mask)
    tests["single_frame_equivalence"] = {"passed": bool(np.isclose(float(pf_num / pf_den), float(clip_num / clip_den), atol=1e-7)), "pfce": float(pf_num / pf_den), "clipce": float(clip_num / clip_den)}
    model = make_model(101); load_initialization(model, 101)
    x = tf.constant(rng.normal(size=(2, 96, WIDTH)).astype(np.float32)); labels = tf.constant([1, 2]); full_mask = tf.constant(np.ones((2, 96), dtype=bool))
    with tf.GradientTape() as tape:
        probabilities = model(x, training=True)
        numerator, denominator = objective_components("CLIPCE_AGGREGATION_ALIGNED", probabilities, labels, full_mask)
        loss = numerator / denominator
    gradients = tape.gradient(loss, model.trainable_variables)
    finite = all(gradient is not None and bool(tf.reduce_all(tf.math.is_finite(gradient))) for gradient in gradients)
    nonzero = any(float(tf.reduce_sum(tf.abs(gradient))) > 0 for gradient in gradients if gradient is not None)
    tests["clipce_gradient"] = {"passed": bool(finite and nonzero and np.isfinite(float(loss))), "finite": finite, "nonzero": nonzero, "loss": float(loss)}
    left = make_model(202); right = make_model(202)
    left_hash = load_initialization(left, 202); right_hash = load_initialization(right, 202)
    tests["no_new_variables_and_initialization"] = {"passed": bool(left.count_params() == right.count_params() == 163884 and left_hash == right_hash), "pfce_params": left.count_params(), "clipce_params": right.count_params(), "weight_hash": left_hash}
    order_checks = []
    for seed in SEEDS:
        for epoch in (0, 1, 99):
            first = batch_permutation(seed, epoch); second = batch_permutation(seed, epoch)
            order_checks.append(bool(np.array_equal(first, second) and len(np.unique(first)) == COUNTS["train"]))
    tests["batch_order_deterministic_and_shared"] = {"passed": all(order_checks), "checks": len(order_checks)}
    tests["passed"] = all(row.get("passed", False) for row in tests.values())
    atomic_json(OUT / "p5d2_unit_tests.json", tests)
    print(json.dumps(tests, indent=2))
    return 0 if tests["passed"] else 2


def set_run_status(branch: str, seed: int, status: str) -> None:
    path = OUT / "p5d2_run_matrix.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if row["branch"] == branch and int(row["seed"]) == seed:
            row["status"] = status
    write_csv(path, rows, list(rows[0]))


def checkpoint_bundle(model: Any, optimizer: Any, directory: Path) -> tuple[Any, Any, Any, Any]:
    import tensorflow as tf

    completed = tf.Variable(0, trainable=False, dtype=tf.int64, name="completed_epochs")
    best_nll = tf.Variable(np.inf, trainable=False, dtype=tf.float64, name="best_validation_clip_nll")
    checkpoint = tf.train.Checkpoint(model=model, optimizer=optimizer, completed_epochs=completed, best_validation_clip_nll=best_nll)
    manager = tf.train.CheckpointManager(checkpoint, str(directory / "resume_state"), max_to_keep=2)
    return checkpoint, completed, best_nll, manager


def common_metrics(probabilities: np.ndarray, labels: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    denominator = np.maximum(mask.sum(axis=1, keepdims=True), 1)
    clip = (probabilities.astype(np.float64) * mask[:, :, None]).sum(axis=1) / denominator
    prediction = clip.argmax(axis=1)
    frame_prediction = probabilities.argmax(axis=2)
    true_probability = clip[np.arange(len(labels)), labels]
    return {
        "clip_nll": float(np.mean(-np.log(np.clip(true_probability, EPSILON, 1.0)))),
        "clip_top1": float(np.mean(prediction == labels)),
        "pf_accuracy": float(np.sum((frame_prediction == labels[:, None]) * mask) / np.sum(mask)),
    }


def infer_probabilities(model: Any, x: np.ndarray) -> np.ndarray:
    outputs = []
    for start in range(0, len(x), BATCH):
        outputs.append(np.asarray(model(x[start:start + BATCH], training=False), dtype=np.float32))
    return np.concatenate(outputs, axis=0)


def train(branch: str, seed: int, resume: bool) -> int:
    import tensorflow as tf

    assert_prepared()
    tests = json.loads((OUT / "p5d2_unit_tests.json").read_text(encoding="utf-8"))
    if not tests.get("passed"):
        raise RuntimeError("P5D2_UNIT_TEST_GATE_FAILED")
    data = load_split("train"); validation = load_split("val")
    directory = run_dir(branch, seed); state_path = directory / "run_state.json"; history_path = directory / "history.csv"
    if resume:
        if not directory.is_dir() or not state_path.is_file():
            raise RuntimeError("P5D2_NO_RESUMABLE_STATE")
    else:
        if directory.exists():
            raise RuntimeError("P5D2_RUN_EXISTS_USE_RESUME")
        directory.mkdir(parents=True)
        write_csv(history_path, [], HISTORY_FIELDS)
    model = make_model(seed)
    loaded_hash = load_initialization(model, seed)
    optimizer = tf.keras.optimizers.AdamW(learning_rate=5e-4, weight_decay=1e-4)
    optimizer.build(model.trainable_variables)
    checkpoint, completed, best_nll, manager = checkpoint_bundle(model, optimizer, directory)
    if resume:
        if not manager.latest_checkpoint:
            raise RuntimeError("P5D2_NO_RESUMABLE_STATE")
        checkpoint.restore(manager.latest_checkpoint).assert_existing_objects_matched()
    else:
        expected = next(row for row in csv.DictReader((OUT / "p5d2_initialization_parity.csv").open("r", encoding="utf-8", newline="")) if int(row["seed"]) == seed)
        if loaded_hash != expected["initial_weight_tensor_sha256"]:
            raise RuntimeError("P5D2_INITIALIZATION_HASH_MISMATCH")
        initial_checkpoint = manager.save(checkpoint_number=0)
        atomic_json(state_path, {
            "branch": branch, "seed": seed, "completed_epochs": 0,
            "last_completed_epoch": -1, "best_validation_clip_nll": None,
            "optimizer_iterations": int(optimizer.iterations.numpy()),
            "latest_checkpoint": initial_checkpoint, "status": "READY",
        })

    @tf.function(reduce_retracing=True)
    def train_step(x_batch: Any, y_batch: Any, mask_batch: Any) -> tuple[Any, Any, Any]:
        with tf.GradientTape() as tape:
            probabilities = model(x_batch, training=True)
            numerator, denominator = objective_components(branch, probabilities, y_batch, mask_batch)
            loss = numerator / denominator
        gradients = tape.gradient(loss, model.trainable_variables)
        optimizer.apply_gradients(zip(gradients, model.trainable_variables))
        return numerator, denominator, probabilities

    start_epoch = int(completed.numpy())
    set_run_status(branch, seed, "RUNNING")
    for epoch in range(start_epoch, EPOCHS):
        order = batch_permutation(seed, epoch)
        objective_numerator = 0.0; objective_denominator = 0.0
        train_clip_correct = 0; train_pf_correct = 0; train_real_frames = 0
        for start in range(0, COUNTS["train"], BATCH):
            chosen = order[start:start + BATCH]
            x_batch = tf.convert_to_tensor(data["X"][chosen])
            y_batch = tf.convert_to_tensor(data["y"][chosen])
            mask_batch = tf.convert_to_tensor(data["frame_mask"][chosen])
            numerator, denominator, probabilities_tensor = train_step(x_batch, y_batch, mask_batch)
            probabilities = probabilities_tensor.numpy()
            objective_numerator += float(numerator); objective_denominator += float(denominator)
            common = common_metrics(probabilities, data["y"][chosen], data["frame_mask"][chosen])
            train_clip_correct += int(round(common["clip_top1"] * len(chosen)))
            real = int(data["frame_mask"][chosen].sum())
            train_pf_correct += int(round(common["pf_accuracy"] * real)); train_real_frames += real
        validation_probabilities = infer_probabilities(model, validation["X"])
        val_common = common_metrics(validation_probabilities, validation["y"], validation["frame_mask"])
        improved = val_common["clip_nll"] < float(best_nll.numpy())
        if improved:
            best_nll.assign(val_common["clip_nll"])
            save_model_atomic(model, directory / "best.keras")
        completed.assign(epoch + 1)
        checkpoint_path = manager.save(checkpoint_number=epoch + 1)
        state = {
            "branch": branch, "seed": seed, "completed_epochs": epoch + 1,
            "last_completed_epoch": epoch, "best_validation_clip_nll": float(best_nll.numpy()),
            "optimizer_iterations": int(optimizer.iterations.numpy()), "latest_checkpoint": checkpoint_path,
            "status": "MAX_EPOCH_REACHED" if epoch + 1 == EPOCHS else "RUNNING",
        }
        row = {
            "branch": branch, "seed": seed, "epoch": epoch,
            "train_objective_loss": objective_numerator / max(objective_denominator, 1.0),
            "train_clip_top1": train_clip_correct / COUNTS["train"],
            "train_pf_accuracy": train_pf_correct / max(train_real_frames, 1),
            "validation_clip_nll": val_common["clip_nll"],
            "validation_clip_top1": val_common["clip_top1"],
            "validation_pf_accuracy": val_common["pf_accuracy"],
            "learning_rate": float(tf.keras.backend.get_value(optimizer.learning_rate)),
            "optimizer_iterations": int(optimizer.iterations.numpy()),
        }
        with history_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=HISTORY_FIELDS); writer.writerow(row); handle.flush(); os.fsync(handle.fileno())
        atomic_json(state_path, state)
        print(json.dumps(state), flush=True)
    set_run_status(branch, seed, "MAX_EPOCH_REACHED")
    return 0


def train_all() -> int:
    assert_prepared()
    for seed in SEEDS:
        for branch in BRANCHES:
            directory = run_dir(branch, seed); state_path = directory / "run_state.json"
            if state_path.is_file():
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if state.get("status") == "MAX_EPOCH_REACHED" and int(state.get("completed_epochs", 0)) == EPOCHS:
                    continue
            train(branch, seed, resume=directory.exists())
    return 0


def macro_f1(y: np.ndarray, prediction: np.ndarray) -> float:
    return float(classification_metrics(y, prediction, CLASSES)[-1])


def evaluate_model(branch: str, seed: int) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, np.ndarray]]:
    import tensorflow as tf

    directory = run_dir(branch, seed)
    state = json.loads((directory / "run_state.json").read_text(encoding="utf-8"))
    if state.get("status") != "MAX_EPOCH_REACHED" or int(state.get("completed_epochs", 0)) != EPOCHS:
        raise RuntimeError(f"P5D2_RUN_INCOMPLETE:{branch}:{seed}")
    model = tf.keras.models.load_model(directory / "best.keras", safe_mode=False)
    results: dict[str, dict[str, Any]] = {}
    arrays: dict[str, np.ndarray] = {}
    for split in ("train", "val"):
        data = load_split(split); frame = infer_probabilities(model, data["X"])
        denominator = np.maximum(data["frame_mask"].sum(axis=1, keepdims=True), 1)
        clip = (frame.astype(np.float64) * data["frame_mask"][:, :, None]).sum(axis=1) / denominator
        prediction = clip.argmax(axis=1); top5 = np.argsort(clip, axis=1)[:, -5:]
        true_frame_probability = frame[
            np.arange(len(data["y"]))[:, None],
            np.arange(frame.shape[1])[None, :],
            data["y"][:, None],
        ].astype(np.float64)
        if branch == "PFCE_MATCHED":
            objective_loss = float(
                np.sum(-np.log(np.clip(true_frame_probability, EPSILON, 1.0)) * data["frame_mask"])
                / np.sum(data["frame_mask"])
            )
        else:
            objective_loss = float(
                np.mean(-np.log(np.clip(clip[np.arange(len(data["y"])), data["y"]], EPSILON, 1.0)))
            )
        results[split] = {
            "top1": float(np.mean(prediction == data["y"])),
            "top5": float(np.mean([data["y"][index] in top5[index] for index in range(len(data["y"]))])),
            "macro_f1": macro_f1(data["y"], prediction),
            "clip_nll": float(np.mean(-np.log(np.clip(clip[np.arange(len(data["y"])), data["y"]], EPSILON, 1.0)))),
            "pf_accuracy": float(np.sum((frame.argmax(axis=2) == data["y"][:, None]) * data["frame_mask"]) / data["frame_mask"].sum()),
            "objective_loss": objective_loss,
        }
        if split == "val":
            arrays = {"y": data["y"], "prediction": prediction, "clip": clip, "frame": frame, "mask": data["frame_mask"], "signers": data["signers"], "sample_ids": data["sample_ids"]}
    with (directory / "history.csv").open("r", encoding="utf-8", newline="") as handle:
        history = list(csv.DictReader(handle))
    selected = min(history, key=lambda row: float(row["validation_clip_nll"]))
    overall = {
        "branch": branch, "seed": seed, "selected_epoch": int(selected["epoch"]), "completed_epochs": EPOCHS,
        "parameter_count": model.count_params(), "checkpoint_sha256": sha256(directory / "best.keras"),
        "top1": results["val"]["top1"], "top5": results["val"]["top5"], "macro_f1": results["val"]["macro_f1"],
        "validation_clip_nll": results["val"]["clip_nll"], "pf_accuracy": results["val"]["pf_accuracy"],
        "train_top1": results["train"]["top1"], "train_pf_accuracy": results["train"]["pf_accuracy"],
        "train_objective_loss": results["train"]["objective_loss"], "train_validation_top1_gap": results["train"]["top1"] - results["val"]["top1"],
    }
    signer_rows = []
    for signer in sorted(set(map(str, arrays["signers"]))):
        chosen = np.asarray([str(value) == signer for value in arrays["signers"]])
        signer_rows.append({
            "branch": branch, "seed": seed, "signer_group_id": signer, "clips": int(chosen.sum()),
            "top1": float(np.mean(arrays["prediction"][chosen] == arrays["y"][chosen])),
            "macro_f1": macro_f1(arrays["y"][chosen], arrays["prediction"][chosen]),
            "mean_true_class_probability": float(np.mean(arrays["clip"][chosen, arrays["y"][chosen]])),
        })
    taxonomy = []; margins = []; concentration = []
    for index in range(len(arrays["y"])):
        true = int(arrays["y"][index]); predicted = int(arrays["prediction"][index]); real = np.flatnonzero(arrays["mask"][index])
        wrong_scores = arrays["clip"][index].copy(); wrong_scores[true] = -np.inf
        competitor = predicted if predicted != true else int(np.argmax(wrong_scores))
        frame_margin = arrays["frame"][index, real, true] - arrays["frame"][index, real, competitor]
        thirds = np.array_split(real, 3)
        third_margins = [float(np.mean(arrays["frame"][index, third, true] - arrays["frame"][index, third, competitor])) if len(third) else 0.0 for third in thirds]
        if predicted != true:
            if all(value < 0 for value in third_margins): category = "PERSISTENT_WRONG_CLASS"
            elif float(np.mean(frame_margin > 0)) > 0.5: category = "TRUE_TEMPORAL_MAJORITY_BUT_FINAL_WRONG"
            elif any(value > 0 for value in third_margins) and any(value < 0 for value in third_margins): category = "PHASE_DEPENDENT_CONFUSION"
            else: category = "OTHER"
            taxonomy.append({"branch": branch, "seed": seed, "sample_id": str(arrays["sample_ids"][index]), "signer_group_id": str(arrays["signers"][index]), "true_class": true, "predicted_class": predicted, "category": category})
        margins.append({"branch": branch, "seed": seed, "sample_id": str(arrays["sample_ids"][index]), "correct": int(predicted == true), "true_class": true, "competitor_class": competitor, "first_third_margin": third_margins[0], "middle_third_margin": third_margins[1], "final_third_margin": third_margins[2], "whole_clip_margin": float(arrays["clip"][index, true] - arrays["clip"][index, competitor])})
        true_frame = arrays["frame"][index, real, true].astype(np.float64); total = max(float(true_frame.sum()), EPSILON); normalized = true_frame / total
        contributions = [float(true_frame[np.isin(real, third)].sum() / total) if len(third) else 0.0 for third in thirds]
        concentration.append({"branch": branch, "seed": seed, "sample_id": str(arrays["sample_ids"][index]), "correct": int(predicted == true), "max_true_frame_probability": float(true_frame.max()), "mean_true_frame_probability": float(true_frame.mean()), "fraction_frames_above_clip_true_mean": float(np.mean(true_frame > arrays["clip"][index, true])), "temporal_hhi": float(np.sum(normalized ** 2)), "first_third_contribution": contributions[0], "middle_third_contribution": contributions[1], "final_third_contribution": contributions[2]})
    return overall, signer_rows, taxonomy, margins, concentration, arrays


def signer_bootstrap(pfce: dict[str, np.ndarray], clipce: dict[str, np.ndarray], seed: int) -> list[dict[str, Any]]:
    if not np.array_equal(pfce["y"], clipce["y"]) or not np.array_equal(pfce["signers"], clipce["signers"]):
        raise RuntimeError("P5D2_BOOTSTRAP_ALIGNMENT_FAILURE")
    y = pfce["y"]; signers = sorted(set(map(str, pfce["signers"])))
    indices = {signer: np.flatnonzero(np.asarray([str(value) == signer for value in pfce["signers"]])) for signer in signers}
    rng = np.random.Generator(np.random.PCG64(seed)); top = np.empty(10_000); f1 = np.empty(10_000)
    for replicate in range(10_000):
        draw = rng.choice(signers, size=len(signers), replace=True); chosen = np.concatenate([indices[str(signer)] for signer in draw])
        top[replicate] = np.mean(clipce["prediction"][chosen] == y[chosen]) - np.mean(pfce["prediction"][chosen] == y[chosen])
        f1[replicate] = macro_f1(y[chosen], clipce["prediction"][chosen]) - macro_f1(y[chosen], pfce["prediction"][chosen])
    return [
        {"seed": seed, "metric": "Top1", "point_delta_clipce_minus_pfce": float(np.mean(clipce["prediction"] == y) - np.mean(pfce["prediction"] == y)), "ci95_low": float(np.percentile(top, 2.5)), "ci95_high": float(np.percentile(top, 97.5)), "replicates": 10000, "cluster_unit": "signer"},
        {"seed": seed, "metric": "MacroF1", "point_delta_clipce_minus_pfce": macro_f1(y, clipce["prediction"]) - macro_f1(y, pfce["prediction"]), "ci95_low": float(np.percentile(f1, 2.5)), "ci95_high": float(np.percentile(f1, 97.5)), "replicates": 10000, "cluster_unit": "signer"},
    ]


def finalize() -> int:
    assert_prepared(); context_now = context_hashes(); sources_now = source_hashes()
    metrics = []; signer_rows = []; taxonomy = []; margins = []; concentration = []; arrays = {}; histories = []
    for seed in SEEDS:
        for branch in BRANCHES:
            overall, signer, failures, temporal, evidence, saved = evaluate_model(branch, seed)
            metrics.append(overall); signer_rows.extend(signer); taxonomy.extend(failures); margins.extend(temporal); concentration.extend(evidence); arrays[(branch, seed)] = saved
            with (run_dir(branch, seed) / "history.csv").open("r", encoding="utf-8", newline="") as handle: histories.extend(list(csv.DictReader(handle)))
    write_csv(OUT / "p5d2_training_histories.csv", histories, HISTORY_FIELDS)
    write_csv(OUT / "p5d2_validation_metrics.csv", metrics, list(metrics[0]))
    write_csv(OUT / "p5d2_validation_by_signer.csv", signer_rows, list(signer_rows[0]))
    write_csv(OUT / "p5d2_temporal_failure_taxonomy.csv", taxonomy, list(taxonomy[0]))
    write_csv(OUT / "p5d2_temporal_margin_summary.csv", margins, list(margins[0]))
    write_csv(OUT / "p5d2_evidence_concentration.csv", concentration, list(concentration[0]))
    deltas = []
    for seed in SEEDS:
        pf = next(row for row in metrics if row["branch"] == "PFCE_MATCHED" and row["seed"] == seed)
        clip = next(row for row in metrics if row["branch"] == "CLIPCE_AGGREGATION_ALIGNED" and row["seed"] == seed)
        deltas.append({"seed": seed, **{f"{metric}_clipce_minus_pfce": clip[metric] - pf[metric] for metric in ("top1", "top5", "macro_f1", "validation_clip_nll", "pf_accuracy")}})
    for name, function in (("mean", np.mean), ("median", np.median), ("min", np.min), ("max", np.max), ("std", np.std)):
        deltas.append({"seed": name, **{f"{metric}_clipce_minus_pfce": float(function([row[f"{metric}_clipce_minus_pfce"] for row in deltas[:3]])) for metric in ("top1", "top5", "macro_f1", "validation_clip_nll", "pf_accuracy")}})
    write_csv(OUT / "p5d2_seed_paired_deltas.csv", deltas, list(deltas[0]))
    uncertainty = []
    for seed in SEEDS: uncertainty.extend(signer_bootstrap(arrays[("PFCE_MATCHED", seed)], arrays[("CLIPCE_AGGREGATION_ALIGNED", seed)], seed))
    write_csv(OUT / "p5d2_signer_blocked_uncertainty.csv", uncertainty, list(uncertainty[0]))
    summaries = {branch: {metric: float(np.median([row[metric] for row in metrics if row["branch"] == branch])) for metric in ("top1", "top5", "macro_f1", "validation_clip_nll", "pf_accuracy")} for branch in BRANCHES}
    persistent = {branch: int(sum(row["branch"] == branch and row["category"] == "PERSISTENT_WRONG_CLASS" for row in taxonomy)) for branch in BRANCHES}
    errors = {branch: int(sum(row["branch"] == branch for row in taxonomy)) for branch in BRANCHES}
    persistent_fraction = {branch: persistent[branch] / max(errors[branch], 1) for branch in BRANCHES}
    top_deltas = [float(row["top1_clipce_minus_pfce"]) for row in deltas[:3]]; macro_deltas = [float(row["macro_f1_clipce_minus_pfce"]) for row in deltas[:3]]
    top_positive_ci = sum(row["metric"] == "Top1" and float(row["ci95_low"]) > 0 for row in uncertainty)
    top_negative_ci = sum(row["metric"] == "Top1" and float(row["ci95_high"]) < 0 for row in uncertainty)
    branch_top_sd = max(float(np.std([row["top1"] for row in metrics if row["branch"] == branch])) for branch in BRANCHES)
    mean_delta = float(np.mean(top_deltas)); top5_mean = float(np.mean([float(row["top5_clipce_minus_pfce"]) for row in deltas[:3]])); macro_mean = float(np.mean(macro_deltas))
    if all(value > 0 for value in top_deltas) and sum(value > 0 for value in macro_deltas) >= 2 and top_positive_ci >= 2 and mean_delta > branch_top_sd and top5_mean >= 0 and macro_mean >= 0 and (persistent_fraction["CLIPCE_AGGREGATION_ALIGNED"] < persistent_fraction["PFCE_MATCHED"] or mean_delta > 0):
        classification = "TEMPORAL_OBJECTIVE_CAUSAL_CONTRIBUTOR"; confidence = "HIGH" if top_positive_ci == 3 else "MODERATE"; next_gate = "DEVELOP_SIMPLEST_SEQUENCE_LEVEL_SUPERVISION_WITH_SAME_TCN"
    elif sum(value > 0 for value in top_deltas) >= 2 and mean_delta > 0:
        classification = "TEMPORAL_OBJECTIVE_HELPFUL_BUT_NOT_SUFFICIENT"; confidence = "MODERATE"; next_gate = "GATE_3_DATA_SUFFICIENCY_LEARNING_CURVE"
    elif all(value < 0 for value in top_deltas) and top5_mean < 0 and macro_mean < 0 and top_negative_ci >= 2:
        classification = "CLIP_OBJECTIVE_HARMFUL"; confidence = "HIGH" if top_negative_ci == 3 else "MODERATE"; next_gate = "GATE_3_DATA_SUFFICIENCY_LEARNING_CURVE"
    else:
        classification = "TEMPORAL_OBJECTIVE_NOT_PRIMARY"; confidence = "MODERATE"; next_gate = "GATE_3_DATA_SUFFICIENCY_LEARNING_CURVE"
    decision = {"classification": classification, "confidence": confidence, "next_gate": next_gate, "median_metrics": summaries, "top1_deltas_clipce_minus_pfce": top_deltas, "macro_f1_deltas_clipce_minus_pfce": macro_deltas, "signer_blocked_positive_top1_intervals": top_positive_ci, "signer_blocked_negative_top1_intervals": top_negative_ci, "ordinary_across_seed_top1_stochasticity": branch_top_sd, "persistent_wrong_class": persistent, "total_errors_across_seed_runs": errors, "persistent_wrong_class_fraction": persistent_fraction, "protected_test_accessed": False, "what_this_establishes": "Causal evidence about replacing per-frame CE with aggregation-aligned whole-clip CE under an otherwise matched V2/TCN contract.", "what_this_does_not_establish": "It does not establish data sufficiency, external-data value, architecture superiority, or protected-test performance."}
    atomic_json(OUT / "p5d2_decision.json", decision)
    integrity_path = OUT / "p5d2_integrity.json"; integrity = json.loads(integrity_path.read_text(encoding="utf-8")); frozen_context = integrity["context_hashes_at_freeze"]
    integrity.update({"passed": integrity["passed"] and sources_now == EXPECTED_HASHES and frozen_context == context_now, "six_runs_complete": len(metrics) == 6, "training_performed": True, "source_hashes_after_training": sources_now, "protected_test_accessed": False, "external_data_used": False, "context_files_modified": frozen_context != context_now, "progress_tracker_untouched": frozen_context.get("context/progress-tracker.md") == context_now.get("context/progress-tracker.md")})
    atomic_json(integrity_path, integrity)
    result = f"""# P5-D2 Temporal Objective Result

Integrity: {'PASS' if integrity['passed'] else 'FAIL'}

Six matched full-horizon runs compared per-frame CE with aggregation-aligned clip CE using frozen DWPose V2 `[96,238]`, the same 4x64 causal TCN, seed-paired initial weights, deterministic seed-paired batch order, and the same minimum-validation-clip-NLL checkpoint rule.

## Decision

- Classification: `{classification}`
- Confidence: `{confidence}`
- Next gate: `{next_gate}` (not executed)
- Matched Top-1 deltas CLIPCE-PFCE: {', '.join(f'{value:.6f}' for value in top_deltas)}
- PFCE median Top-1: {summaries['PFCE_MATCHED']['top1']:.6f}
- CLIPCE median Top-1: {summaries['CLIPCE_AGGREGATION_ALIGNED']['top1']:.6f}

No protected test, external data, new recording, representation change, augmentation, Android change, or P4 reopening occurred.
"""
    atomic_text(OUT / "P5D2_TEMPORAL_OBJECTIVE_RESULT.md", result)
    artifacts = [{"path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size} for path in sorted(OUT.rglob("*")) if path.is_file() and path.name != "artifact_hash_manifest.json"]
    atomic_json(OUT / "artifact_hash_manifest.json", {"artifacts": artifacts, "supporting_code": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())}, "protected_test_accessed": False})
    print(json.dumps({"status": "APPHEAR_P5D2_TEMPORAL_OBJECTIVE_ABLATION_COMPLETE", "decision": decision, "integrity": integrity}, indent=2))
    return 0 if integrity["passed"] else 2


def main() -> int:
    parser = argparse.ArgumentParser(); commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare"); commands.add_parser("unit-tests"); commands.add_parser("train-all"); commands.add_parser("finalize")
    single = commands.add_parser("train"); single.add_argument("--branch", choices=BRANCHES, required=True); single.add_argument("--seed", choices=SEEDS, type=int, required=True); single.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare": return prepare()
    if args.command == "unit-tests": return unit_tests()
    if args.command == "train-all": return train_all()
    if args.command == "train": return train(args.branch, args.seed, args.resume)
    return finalize()


if __name__ == "__main__":
    raise SystemExit(main())
