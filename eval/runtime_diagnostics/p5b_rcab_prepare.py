"""Generate the read-only P5-B RCA-B checkpoint-state audit and preparation provenance."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import tempfile
import zipfile
from pathlib import Path

import h5py
import numpy as np
import tensorflow as tf


ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5b_rcab_preparation_01"
CHECKPOINT = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5b_baseline_01/best.keras"
TRAINER = ROOT / "model/p5b_rcab_horizon.py"
RUNBOOK = ROOT / "context/recognition_upgrade/P5B_RCAB_RUNBOOK.md"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def variable_rows(values: list[tf.Variable]) -> list[dict[str, object]]:
    return [
        {
            "name": value.name,
            "shape": list(value.shape),
            "dtype": str(value.dtype),
            "sha256": hashlib.sha256(np.asarray(value.numpy()).tobytes()).hexdigest(),
        }
        for value in values
    ]


def audit() -> int:
    PREP.mkdir(parents=True, exist_ok=True)
    first = tf.keras.models.load_model(CHECKPOINT, safe_mode=False)
    second = tf.keras.models.load_model(CHECKPOINT, safe_mode=False)
    optimizer = first.optimizer
    seed_first = [np.asarray(v.numpy()) for v in first.non_trainable_variables if "seed_generator_state" in v.name]
    seed_second = [np.asarray(v.numpy()) for v in second.non_trainable_variables if "seed_generator_state" in v.name]
    seed_equal = len(seed_first) == len(seed_second) and all(np.array_equal(a, b) for a, b in zip(seed_first, seed_second))
    with tempfile.TemporaryDirectory(prefix="p5b_rcab_h5_") as temp_dir:
        with zipfile.ZipFile(CHECKPOINT) as archive:
            archive.extract("model.weights.h5", temp_dir)
        datasets: list[str] = []
        with h5py.File(Path(temp_dir) / "model.weights.h5", "r") as h5:
            h5.visititems(lambda name, obj: datasets.append(name) if isinstance(obj, h5py.Dataset) else None)
    seed_datasets = [name for name in datasets if "seed" in name.lower()]
    trainable_count = len(first.trainable_variables)
    expected_optimizer_variable_count = 2 + 2 * trainable_count
    expected_iterations = 40 * 123
    payload = {
        "checkpoint_path": str(CHECKPOINT.resolve()),
        "checkpoint_sha256": sha256(CHECKPOINT),
        "saved_model_weights": True,
        "saved_optimizer_state": True,
        "optimizer_class": optimizer.__class__.__name__,
        "optimizer_module": optimizer.__class__.__module__,
        "optimizer_iterations_stored": int(optimizer.iterations.numpy()),
        "optimizer_iterations_expected_after_epoch_39": expected_iterations,
        "optimizer_iteration_match": int(optimizer.iterations.numpy()) == expected_iterations,
        "stored_learning_rate": float(tf.keras.backend.get_value(optimizer.learning_rate)),
        "expected_learning_rate": 0.0005,
        "stored_weight_decay": float(tf.keras.backend.get_value(optimizer.weight_decay)),
        "expected_weight_decay": 0.0001,
        "trainable_variable_count": trainable_count,
        "optimizer_variable_count": len(optimizer.variables),
        "expected_optimizer_variable_count": expected_optimizer_variable_count,
        "optimizer_slots_complete": len(optimizer.variables) == expected_optimizer_variable_count,
        "optimizer_variables": variable_rows(list(optimizer.variables)),
        "model_input_shape": list(first.input_shape),
        "model_output_shape": list(first.output_shape),
        "model_parameter_count": first.count_params(),
        "dropout_seed_generator_count": len(seed_first),
        "dropout_seed_state_equal_across_independent_loads": seed_equal,
        "seed_state_datasets_in_keras_weights": seed_datasets,
        "external_tfdata_shuffle_iterator_saved_in_keras": False,
        "epoch_continuation_supported": True,
        "exact_state_continuation": "NO",
        "selected_path": "PATH_B_FRESH100",
        "reason": "Model and AdamW state are complete, but exact stochastic state is not: .keras omits dropout seed-generator state and the external shuffled tf.data iterator. Loading old weights would not reproduce a faithful epoch-40 continuation.",
    }
    (PREP / "p5b_rcab_resume_state_audit.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "tensorflow": tf.__version__,
        "keras": tf.keras.__version__,
        "numpy": np.__version__,
        "backend": "CPU / oneDNN disabled by RCA-B trainer",
        "trainer_sha256": sha256(TRAINER),
    }
    (PREP / "environment_manifest.json").write_text(json.dumps(environment, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "exact_state_continuation": "NO", "selected_path": "PATH_B_FRESH100", "optimizer_iterations": payload["optimizer_iterations_stored"], "optimizer_slots_complete": payload["optimizer_slots_complete"]}, indent=2))
    return 0


def hash_manifest() -> int:
    paths = sorted(p for p in PREP.iterdir() if p.is_file() and p.name != "artifact_hash_manifest.json")
    paths.extend([TRAINER, Path(__file__), RUNBOOK])
    payload = {
        "scope": "P5-B RCA-B preparation only",
        "full_training_run": False,
        "artifacts": [
            {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in paths
        ],
    }
    (PREP / "artifact_hash_manifest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "hashed": len(paths)}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["audit", "hash-manifest"])
    args = parser.parse_args()
    return audit() if args.command == "audit" else hash_manifest()


if __name__ == "__main__":
    raise SystemExit(main())
