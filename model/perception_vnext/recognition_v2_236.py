"""Controlled 236-class TCN training/evaluation for recognition-v2.

Only the input schema/width differs from the frozen recognition-v1 baseline.
Candidate 01, population, clip-uniform sampling, dense+sparse weighting, model
architecture, optimizer/loss, seed and validation policy remain unchanged.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from model.perception_vnext.recognition_utility_236 import sha256, write_json
from pipeline.perception_vnext.recognition_schema import MAX_SEQUENCE_LENGTH, RAW_SCHEMA
from pipeline.perception_vnext.recognition_schema_v2 import FEATURE_SCHEMA_V2, FEATURE_WIDTH_V2

MILESTONE = "PERCEPTION_VNEXT_REPRESENTATION_V2_236_PRODUCTION_01"
ROOT = Path(__file__).resolve().parents[2]
BASE = (
    ROOT
    / "artifacts"
    / "recognition_upgrade"
    / "perception_vnext"
    / "recognition_utility_236_01"
)
BASELINE_DATASET = BASE / "dataset"
BASELINE_CONFIG = (
    ROOT
    / "model"
    / "config"
    / "recognition_upgrade"
    / "perception_vnext_recognition_utility_236_01.json"
)
BASELINE_RUN = BASE / "tcn_run_01"
DEFAULT_DATASET = BASE / "representation_v2_236_production_01" / "dataset"
DEFAULT_CONFIG = (
    ROOT
    / "model"
    / "config"
    / "recognition_upgrade"
    / "perception_vnext_representation_v2_236_production_01.json"
)
DEFAULT_RUN = BASE / "tcn_v2_run_01"
VOCAB_MANIFEST = (
    ROOT
    / "artifacts"
    / "recognition_upgrade"
    / "phase1_full_vocab"
    / "dataset_v1"
    / "vocab.json"
)


def _load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    baseline = json.loads(BASELINE_CONFIG.read_text(encoding="utf-8-sig"))
    if (
        config.get("milestone") != MILESTONE
        or config.get("raw_schema") != RAW_SCHEMA
        or config.get("feature_schema") != FEATURE_SCHEMA_V2
        or config.get("input_shape") != [MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2]
        or config.get("classes") != 236
        or config.get("governance", {}).get("protected_test_access") is not False
    ):
        raise RuntimeError("VNEXT_V2_CONFIG_CONTRACT")
    for field in ("seed", "classes", "model", "training", "governance", "runtime_scope"):
        if config.get(field) != baseline.get(field):
            raise RuntimeError(f"VNEXT_V2_NONREPRESENTATION_DELTA:{field}")
    if config.get("training_sampler") is not None:
        raise RuntimeError("VNEXT_V2_BALANCED_SAMPLER_FORBIDDEN")
    return config


def _load_rows(dataset: Path) -> list[dict[str, Any]]:
    contract = json.loads((dataset / "contract.json").read_text(encoding="utf-8"))
    if (
        contract.get("raw_schema") != RAW_SCHEMA
        or contract.get("feature_schema") != FEATURE_SCHEMA_V2
        or contract.get("feature_width") != FEATURE_WIDTH_V2
        or contract.get("max_sequence_length") != MAX_SEQUENCE_LENGTH
        or contract.get("train_clips") != 3926
        or contract.get("dev_clips") != 816
        or contract.get("classes") != 236
        or contract.get("source_dataset_contract_sha256")
        != sha256(BASELINE_DATASET / "contract.json")
        or contract.get("source_index_sha256") != sha256(BASELINE_DATASET / "index.jsonl")
        or contract.get("protected_test_accessed") is not False
    ):
        raise RuntimeError("VNEXT_V2_DATASET_CONTRACT")
    with (dataset / "index.jsonl").open("r", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    train = [row for row in rows if row["split"] == "train"]
    dev = [row for row in rows if row["split"] == "dev"]
    if len(train) != 3926 or len(dev) != 816 or len(rows) != 4742:
        raise RuntimeError("VNEXT_V2_POPULATION_COUNT")
    if {int(row["class_id"]) for row in train} != set(range(236)) or {
        int(row["class_id"]) for row in dev
    } != set(range(236)):
        raise RuntimeError("VNEXT_V2_CLASS_COVERAGE")
    if {row["signer_id"] for row in train} & {row["signer_id"] for row in dev}:
        raise RuntimeError("VNEXT_V2_SIGNER_LEAKAGE")
    if len({row["sample_id"] for row in rows}) != len(rows):
        raise RuntimeError("VNEXT_V2_DUPLICATE_SAMPLE")
    return rows


def _examples(
    rows: list[dict[str, Any]], conditions: tuple[str, ...]
) -> Iterable[tuple[tuple[np.ndarray, np.ndarray], np.int32]]:
    for row in rows:
        with np.load(Path(row["feature_path"]), allow_pickle=False) as package:
            metadata = json.loads(str(package["metadata_json"].item()))
            if (
                metadata.get("schema") != FEATURE_SCHEMA_V2
                or metadata.get("sample_id") != row["sample_id"]
                or int(metadata.get("class_id", -1)) != int(row["class_id"])
            ):
                raise RuntimeError(f"VNEXT_V2_EXAMPLE_IDENTITY:{row['sample_id']}")
            for condition in conditions:
                prefix = "dense" if condition == "dense" else "sparse"
                features = np.asarray(package[f"{prefix}_features"], np.float32)
                mask = np.asarray(package[f"{prefix}_mask"], bool)
                if (
                    features.shape != (MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2)
                    or mask.shape != (MAX_SEQUENCE_LENGTH,)
                    or not np.all(np.isfinite(features))
                    or not np.any(mask)
                    or np.any(features[~mask] != 0.0)
                ):
                    raise RuntimeError(f"VNEXT_V2_EXAMPLE_SHAPE:{row['sample_id']}")
                yield (features, mask), np.int32(row["class_id"])


def _dataset(
    rows: list[dict[str, Any]],
    conditions: tuple[str, ...],
    batch_size: int,
    seed: int,
    training: bool,
) -> Any:
    import tensorflow as tf

    def generator() -> Iterable[tuple[tuple[np.ndarray, np.ndarray], np.int32]]:
        yield from _examples(rows, conditions)

    value = tf.data.Dataset.from_generator(
        generator,
        output_signature=(
            (
                tf.TensorSpec((MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2), tf.float32),
                tf.TensorSpec((MAX_SEQUENCE_LENGTH,), tf.bool),
            ),
            tf.TensorSpec((), tf.int32),
        ),
    )
    if training:
        value = value.shuffle(
            min(len(rows) * len(conditions), 4096),
            seed=seed,
            reshuffle_each_iteration=True,
        )
    batches = math.ceil(len(rows) * len(conditions) / batch_size)
    return (
        value.batch(batch_size)
        .apply(tf.data.experimental.assert_cardinality(batches))
        .prefetch(1)
    )


def _build_tcn(config: dict[str, Any]) -> Any:
    import tensorflow as tf

    from model.model import build_encoder

    model_config = config["model"]
    features = tf.keras.Input(
        (MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2), dtype="float32", name="features"
    )
    mask = tf.keras.Input((MAX_SEQUENCE_LENGTH,), dtype="bool", name="frame_mask")
    encoder = build_encoder(
        MAX_SEQUENCE_LENGTH,
        FEATURE_WIDTH_V2,
        int(model_config["blocks"]),
        int(model_config["channels"]),
        tuple(int(value) for value in model_config["dilations"]),
        int(model_config["kernel"]),
        float(model_config["dropout"]),
    )
    encoded = encoder(features)
    pooled = tf.keras.layers.GlobalAveragePooling1D(name="masked_pool")(encoded, mask=mask)
    probabilities = tf.keras.layers.Dense(
        236, activation="softmax", name="gloss_probabilities"
    )(pooled)
    model = tf.keras.Model(
        [features, mask], probabilities, name="vnext_v2_236_mask_aware_causal_tcn"
    )
    model.compile(
        optimizer=tf.keras.optimizers.AdamW(
            learning_rate=float(config["training"]["learning_rate"]),
            weight_decay=float(config["training"]["weight_decay"]),
        ),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(),
        metrics=[
            tf.keras.metrics.SparseCategoricalAccuracy(name="top1"),
            tf.keras.metrics.SparseTopKCategoricalAccuracy(k=5, name="top5"),
        ],
    )
    return model


def _run_identity(
    dataset: Path, config_path: Path, config: dict[str, Any], smoke: bool
) -> dict[str, Any]:
    baseline_best = BASELINE_RUN / "best.keras"
    if not baseline_best.is_file():
        raise RuntimeError("VNEXT_V2_BASELINE_CONTROL_MISSING")
    return {
        "milestone": MILESTONE,
        "seed": int(config["seed"]),
        "raw_schema": RAW_SCHEMA,
        "feature_schema": FEATURE_SCHEMA_V2,
        "input_shape": [MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2],
        "vocabulary_manifest": str(VOCAB_MANIFEST.resolve()),
        "vocabulary_sha256": sha256(VOCAB_MANIFEST),
        "config_sha256": sha256(config_path),
        "dataset_contract_sha256": sha256(dataset / "contract.json"),
        "baseline_dataset_contract_sha256": sha256(BASELINE_DATASET / "contract.json"),
        "baseline_best_sha256": sha256(baseline_best),
        "baseline_run": str(BASELINE_RUN.resolve()),
        "sampling": "clip_uniform",
        "views_per_clip": ["dense", "sparse"],
        "scientific_delta": "recognition-v1 [96,208] to recognition-v2 [96,350] only",
        "smoke": smoke,
        "protected_test_accessed": False,
    }


def train(
    dataset: Path,
    output: Path,
    config_path: Path,
    *,
    resume: bool,
    smoke: bool,
) -> dict[str, Any]:
    import tensorflow as tf

    config = _load_config(config_path)
    rows = _load_rows(dataset)
    train_rows = [row for row in rows if row["split"] == "train"]
    dev_rows = [row for row in rows if row["split"] == "dev"]
    effective_train = train_rows[:16] if smoke else train_rows
    effective_dev = dev_rows[:16] if smoke else dev_rows
    seed = int(config["seed"])
    tf.keras.utils.set_random_seed(seed)
    output.mkdir(parents=True, exist_ok=True)
    identity = _run_identity(dataset, config_path, config, smoke)
    identity_path = output / "run_identity.json"
    if identity_path.is_file():
        if json.loads(identity_path.read_text(encoding="utf-8")) != identity:
            raise RuntimeError("VNEXT_V2_RUN_IDENTITY_DRIFT")
    else:
        write_json(identity_path, identity)
    reproducibility = output / "reproducibility_config.json"
    if reproducibility.is_file():
        if sha256(reproducibility) != sha256(config_path):
            raise RuntimeError("VNEXT_V2_REPRODUCIBILITY_CONFIG_DRIFT")
    else:
        shutil.copyfile(config_path, reproducibility)

    latest = output / "latest.keras"
    best = output / "best.keras"
    final = output / "final.keras"
    history = output / "history.csv"
    result_path = output / ("smoke_training_result.json" if smoke else "training_result.json")
    if resume and result_path.is_file():
        completed = json.loads(result_path.read_text(encoding="utf-8"))
        if (
            completed.get("status") != "PASS"
            or completed.get("config_sha256") != sha256(config_path)
            or completed.get("dataset_contract_sha256") != sha256(dataset / "contract.json")
            or not best.is_file()
            or not final.is_file()
        ):
            raise RuntimeError("VNEXT_V2_COMPLETED_RUN_INTEGRITY")
        completed["fit_skipped_existing_complete_run"] = True
        return completed
    initial_epoch = 0
    if resume and latest.is_file():
        model = tf.keras.models.load_model(latest, safe_mode=True)
        if history.is_file():
            with history.open("r", encoding="utf-8", newline="") as stream:
                initial_epoch = max(
                    (int(row["epoch"]) for row in csv.DictReader(stream)), default=-1
                ) + 1
    elif resume and not any(path.exists() for path in (best, final, history)):
        model = _build_tcn(config)
    elif not resume and not any(path.exists() for path in (latest, best, final, history)):
        model = _build_tcn(config)
    elif not resume:
        raise RuntimeError("VNEXT_V2_RUN_EXISTS_USE_RESUME")
    else:
        raise RuntimeError("VNEXT_V2_PARTIAL_RUN_WITHOUT_LATEST")

    epochs = 1 if smoke else int(config["training"]["epochs"])
    batch_size = min(4, len(effective_train) * 2) if smoke else int(
        config["training"]["batch_size"]
    )
    train_data = _dataset(
        effective_train, ("dense", "sparse"), batch_size, seed, training=True
    )
    dev_data = _dataset(
        effective_dev, ("dense", "sparse"), batch_size, seed, training=False
    )
    fit_skipped = bool(resume and initial_epoch >= epochs)
    if fit_skipped:
        if not final.is_file() or not best.is_file():
            raise RuntimeError("VNEXT_V2_COMPLETE_RUN_MISSING_FINAL_OR_BEST")
        model = tf.keras.models.load_model(final, safe_mode=True)
    else:
        callbacks: list[Any] = [
            tf.keras.callbacks.ModelCheckpoint(
                str(best), monitor="val_loss", mode="min", save_best_only=True
            ),
            tf.keras.callbacks.ModelCheckpoint(str(latest)),
            tf.keras.callbacks.CSVLogger(str(history), append=resume),
        ]
        if not smoke:
            callbacks.append(
                tf.keras.callbacks.EarlyStopping(
                    monitor="val_loss",
                    mode="min",
                    patience=int(config["training"]["early_stop_patience"]),
                    restore_best_weights=True,
                )
            )
        model.fit(
            train_data,
            validation_data=dev_data,
            initial_epoch=initial_epoch,
            epochs=max(epochs, initial_epoch + (1 if smoke else 0)),
            callbacks=callbacks,
            verbose=2,
            shuffle=False,
        )
        model.save(final)

    reloaded = tf.keras.models.load_model(final, safe_mode=True)
    sample_inputs, _ = next(iter(_dataset(effective_dev[:1], ("dense",), 1, seed, False)))
    before = np.asarray(model(sample_inputs, training=False))
    after = np.asarray(reloaded(sample_inputs, training=False))
    reload_delta = float(np.max(np.abs(before - after)))
    with history.open("r", encoding="utf-8", newline="") as stream:
        history_rows = list(csv.DictReader(stream))
    metric_values = [
        float(value)
        for row in history_rows
        for field, value in row.items()
        if field != "epoch" and value not in (None, "")
    ]
    finite = bool(metric_values) and bool(np.all(np.isfinite(metric_values)))
    if not finite or reload_delta > 1.0e-6:
        raise RuntimeError(f"VNEXT_V2_TRAIN_SANITY:finite={finite}:reload={reload_delta}")
    result = {
        "schema": "APPHEAR_VNEXT_V2_TRAIN_RESULT_V1",
        "status": "PASS",
        "milestone": MILESTONE,
        "smoke": smoke,
        "input_shape": [MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2],
        "architecture": "unchanged established 4x64 mask-aware causal TCN",
        "parameter_count": model.count_params(),
        "train_clips": len(train_rows),
        "dev_clips": len(dev_rows),
        "effective_train_clips": len(effective_train),
        "effective_dev_clips": len(effective_dev),
        "full_train_examples_per_epoch": len(train_rows) * 2,
        "full_steps_per_epoch": math.ceil(
            len(train_rows) * 2 / int(config["training"]["batch_size"])
        ),
        "sampling": "clip_uniform",
        "views_per_clip": ["dense", "sparse"],
        "epochs_in_history": len(history_rows),
        "finite_loss_and_metrics": finite,
        "checkpoint_reload_max_abs": reload_delta,
        "fit_skipped_existing_complete_run": fit_skipped,
        "config_sha256": sha256(config_path),
        "dataset_contract_sha256": sha256(dataset / "contract.json"),
        "best_checkpoint": str(best.resolve()),
        "latest_checkpoint": str(latest.resolve()),
        "final_checkpoint": str(final.resolve()),
        "full_training_executed": not smoke,
        "recognition_accuracy_claim": not smoke,
        "protected_test_accessed": False,
    }
    write_json(result_path, result)
    return result


def _predict(
    model: Any,
    rows: list[dict[str, Any]],
    condition: str,
    batch_size: int,
) -> dict[str, Any]:
    labels: list[int] = []
    predictions: list[int] = []
    top5_correct: list[bool] = []
    records: list[dict[str, Any]] = []
    for start in range(0, len(rows), batch_size):
        batch_rows = rows[start : start + batch_size]
        features: list[np.ndarray] = []
        masks: list[np.ndarray] = []
        for row in batch_rows:
            with np.load(Path(row["feature_path"]), allow_pickle=False) as package:
                prefix = "dense" if condition == "dense" else "sparse"
                value = np.asarray(package[f"{prefix}_features"], np.float32)
                mask = np.asarray(package[f"{prefix}_mask"], bool)
                if value.shape != (MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2):
                    raise RuntimeError(f"VNEXT_V2_EVAL_SHAPE:{row['sample_id']}")
                features.append(value)
                masks.append(mask)
        model_output = model([np.stack(features), np.stack(masks)], training=False)
        if isinstance(model_output, dict):
            model_output = model_output["probabilities"]
        probabilities = np.asarray(model_output, np.float32)
        for row, probability in zip(batch_rows, probabilities, strict=True):
            label = int(row["class_id"])
            prediction = int(np.argmax(probability))
            top5 = np.argpartition(probability, -5)[-5:]
            labels.append(label)
            predictions.append(prediction)
            top5_correct.append(label in top5)
            records.append(
                {
                    "sample_id": row["sample_id"],
                    "label": label,
                    "prediction": prediction,
                    "correct": prediction == label,
                    "top5_correct": label in top5,
                    "signer_id": row["signer_id"],
                    "source_id": row["source_id"],
                }
            )
    return {
        "labels": np.asarray(labels, np.int32),
        "predictions": np.asarray(predictions, np.int32),
        "top5_correct": np.asarray(top5_correct, bool),
        "records": records,
    }


def _classification_metrics(result: dict[str, Any]) -> dict[str, Any]:
    vocabulary = json.loads(VOCAB_MANIFEST.read_text(encoding="utf-8-sig"))
    gloss_by_id = {int(class_id): gloss for gloss, class_id in vocabulary.items()}
    labels = result["labels"]
    predictions = result["predictions"]
    matrix = np.zeros((236, 236), np.int64)
    np.add.at(matrix, (labels, predictions), 1)
    support = matrix.sum(axis=1)
    predicted = matrix.sum(axis=0)
    true_positive = np.diag(matrix)
    recall = np.divide(true_positive, support, out=np.zeros(236), where=support > 0)
    precision = np.divide(true_positive, predicted, out=np.zeros(236), where=predicted > 0)
    f1 = np.divide(
        2 * precision * recall,
        precision + recall,
        out=np.zeros(236),
        where=(precision + recall) > 0,
    )
    off_diagonal = matrix.copy()
    np.fill_diagonal(off_diagonal, 0)
    pairs = []
    for flat in np.argsort(off_diagonal, axis=None)[::-1][:30]:
        actual, predicted_class = np.unravel_index(flat, off_diagonal.shape)
        count = int(off_diagonal[actual, predicted_class])
        if not count:
            break
        pairs.append(
            {
                "actual": int(actual),
                "actual_gloss": gloss_by_id[int(actual)],
                "predicted": int(predicted_class),
                "predicted_gloss": gloss_by_id[int(predicted_class)],
                "count": count,
            }
        )

    def grouped(field: str) -> dict[str, Any]:
        groups: defaultdict[str, list[bool]] = defaultdict(list)
        for record in result["records"]:
            groups[str(record[field])].append(bool(record["correct"]))
        return {
            name: {"clips": len(values), "top1": float(np.mean(values))}
            for name, values in sorted(groups.items())
        }

    return {
        "clips": len(labels),
        "top1": float(np.mean(labels == predictions)),
        "top5": float(np.mean(result["top5_correct"])),
        "macro_f1": float(np.mean(f1)),
        "per_class": [
            {
                "class_id": class_id,
                "canonical_gloss": gloss_by_id[class_id],
                "support": int(support[class_id]),
                "precision": float(precision[class_id]),
                "recall": float(recall[class_id]),
                "f1": float(f1[class_id]),
            }
            for class_id in range(236)
        ],
        "zero_recall_classes": [
            {"class_id": int(value), "canonical_gloss": gloss_by_id[int(value)]}
            for value in np.flatnonzero(recall == 0)
        ],
        "confusion_matrix": matrix.tolist(),
        "largest_confusion_pairs": pairs,
        "by_signer": grouped("signer_id"),
        "by_source": grouped("source_id"),
    }


def evaluate(
    dataset: Path,
    checkpoint: Path,
    output: Path,
    batch_size: int,
    *,
    limit_per_split: int | None = None,
) -> dict[str, Any]:
    import tensorflow as tf

    rows = _load_rows(dataset)
    split_rows = {
        split: [row for row in rows if row["split"] == split] for split in ("train", "dev")
    }
    if limit_per_split is not None:
        split_rows = {key: value[:limit_per_split] for key, value in split_rows.items()}
    model = tf.keras.models.load_model(checkpoint, safe_mode=True)
    details: dict[str, Any] = {}
    raw: dict[tuple[str, str], dict[str, Any]] = {}
    for split, split_values in split_rows.items():
        details[split] = {}
        for condition in ("dense", "phone_01_sparse"):
            predictions = _predict(model, split_values, condition, batch_size)
            raw[(split, condition)] = predictions
            details[split][condition] = _classification_metrics(predictions)
    comparisons: dict[str, Any] = {}
    for split in ("train", "dev"):
        dense = raw[(split, "dense")]
        sparse = raw[(split, "phone_01_sparse")]
        dense_correct = dense["labels"] == dense["predictions"]
        sparse_correct = sparse["labels"] == sparse["predictions"]
        comparisons[split] = {
            "dense_minus_sparse_top1": float(dense_correct.mean() - sparse_correct.mean()),
            "dense_correct_sparse_wrong": int(np.count_nonzero(dense_correct & ~sparse_correct)),
            "sparse_correct_dense_wrong": int(np.count_nonzero(~dense_correct & sparse_correct)),
            "paired_clips": len(dense_correct),
        }
    result = {
        "schema": "APPHEAR_VNEXT_V2_236_EVALUATION_V1",
        "milestone": MILESTONE,
        "status": "PASS",
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": sha256(checkpoint),
        "feature_schema": FEATURE_SCHEMA_V2,
        "input_shape": [MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2],
        "details": details,
        "dense_sparse_paired_comparison": comparisons,
        "train_minus_dev_top1_gap": {
            condition: float(
                details["train"][condition]["top1"]
                - details["dev"][condition]["top1"]
            )
            for condition in ("dense", "phone_01_sparse")
        },
        "smoke": limit_per_split is not None,
        "protected_test_accessed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, result)
    return result


def smoke(dataset: Path, output: Path, config: Path) -> dict[str, Any]:
    training = train(dataset, output, config, resume=False, smoke=True)
    evaluation = evaluate(
        dataset,
        output / "best.keras",
        output / "smoke_evaluation.json",
        batch_size=4,
        limit_per_split=16,
    )
    result = {
        "milestone": MILESTONE,
        "status": "PASS",
        "training": training,
        "evaluation_status": evaluation["status"],
        "recognition_accuracy_claim": False,
        "full_training_executed": False,
        "protected_test_accessed": False,
    }
    write_json(output / "tcn_v2_input_smoke.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    train_parser = commands.add_parser("train")
    train_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    train_parser.add_argument("--output", type=Path, default=DEFAULT_RUN)
    train_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    train_parser.add_argument("--resume", action="store_true")
    smoke_parser = commands.add_parser("smoke")
    smoke_parser.add_argument(
        "--dataset", type=Path, default=DEFAULT_DATASET
    )
    smoke_parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_DATASET.parent / "tcn_v2_input_smoke",
    )
    smoke_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    evaluate_parser = commands.add_parser("evaluate")
    evaluate_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    evaluate_parser.add_argument("--checkpoint", type=Path, default=DEFAULT_RUN / "best.keras")
    evaluate_parser.add_argument("--output", type=Path, default=DEFAULT_RUN / "evaluation.json")
    evaluate_parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    if args.command == "train":
        result = train(
            args.dataset.resolve(),
            args.output.resolve(),
            args.config.resolve(),
            resume=args.resume,
            smoke=False,
        )
    elif args.command == "smoke":
        result = smoke(args.dataset.resolve(), args.output.resolve(), args.config.resolve())
    elif args.command == "evaluate":
        result = evaluate(
            args.dataset.resolve(),
            args.checkpoint.resolve(),
            args.output.resolve(),
            args.batch_size,
        )
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
