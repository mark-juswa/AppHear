"""One isolated causal TCN+CTC baseline; --check is forward/loss validation only.

Actual training is a later user-run command guarded by complete dataset validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import traceback
from pathlib import Path
from typing import Any

import numpy as np

from model.fingerspelling_metrics import greedy_decode, summarize
from pipeline.fingerspelling.adapter import VERSION, WIDTH, identity, sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import ARTIFACT_SCHEMA, validate
from tools.fingerspelling.foundation import DEFAULT_OUTPUT

CONFIG_PATH = REPO / "model/config/fingerspelling_ctc_baseline_01.json"


def tensorflow(config: dict[str, Any]) -> Any:
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
    import tensorflow as tf

    tf.config.set_visible_devices([], "GPU")
    tf.config.threading.set_intra_op_parallelism_threads(config["cpu_threads"])
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(config["seed"])
    tf.config.experimental.enable_op_determinism()
    return tf


def build_model(tf: Any, config: dict[str, Any]) -> Any:
    """Embedded evidence masks stay in 405 columns; separate mask handles batch padding."""
    features = tf.keras.Input((None, WIDTH), name="features")
    time_valid = tf.keras.Input((None, 1), name="time_valid")
    x = tf.keras.layers.Multiply()([features, time_valid])
    for i, dilation in enumerate(config["dilations"]):
        residual = x
        for j in range(2):
            x = tf.keras.layers.Conv1D(
                config["channels"],
                config["kernel_size"],
                dilation_rate=dilation,
                padding="causal",
                name=f"block{i}_conv{j}",
            )(x)
            x = tf.keras.layers.LayerNormalization(name=f"block{i}_norm{j}")(x)
            x = tf.keras.layers.ReLU()(x)
            x = tf.keras.layers.Dropout(config["dropout"], seed=config["seed"] + i * 2 + j)(x)
        if residual.shape[-1] != config["channels"]:
            residual = tf.keras.layers.Conv1D(config["channels"], 1)(residual)
        x = tf.keras.layers.Add()([x, residual])
        x = tf.keras.layers.Multiply()([x, time_valid])
    logits = tf.keras.layers.Dense(28, name="character_logits")(x)
    logits = tf.keras.layers.Multiply()([logits, time_valid])
    return tf.keras.Model([features, time_valid], logits, name="fingerspelling_causal_tcn_ctc_01")


def configuration(path: Path) -> dict[str, Any]:
    config: dict[str, Any] = json.loads(path.read_text())
    if (
        config["schema_version"] != "apphear.fingerspelling.ctc_baseline.v1"
        or config["adapter_version"] != VERSION
        or config["feature_width"] != WIDTH
        or config["temporal_stride"] != 1
        or config["logits"] != 28
        or config["blank_index"] != 27
        or config["training_view"] != "native"
        or config["augmentation"] != "NONE"
    ):
        raise ValueError("[fingerspelling/training] Fixed baseline config mismatch")
    return config


def records(output: Path) -> list[dict[str, Any]]:
    return [json.loads(p.read_text()) for p in sorted((output / "features").glob("*.receipt.json"))]


def load_view(rec: dict[str, Any], view: str) -> tuple[np.ndarray, np.ndarray]:
    with np.load(REPO / rec["features_path"], allow_pickle=False) as data:
        meta = json.loads(str(data["metadata_json"].item()))
        if meta["schema_version"] != ARTIFACT_SCHEMA or meta["adapter"] != identity():
            raise ValueError("[fingerspelling/training] Artifact/adapter identity mismatch")
        x = np.asarray(data["features" if view == "native" else "phone_features"], np.float32)
        y = np.asarray(data["targets"], np.int32)
    minimum = len(y) + int(np.sum(y[1:] == y[:-1]))
    if len(x) < minimum:
        raise ValueError("[fingerspelling/training] Infeasible CTC view must not enter loss")
    return x, y


def padded_batch(rows: list[dict[str, Any]], view: str) -> tuple[np.ndarray, ...]:
    arrays = [load_view(r, view) for r in rows]
    length = np.asarray([len(x) for x, _ in arrays], np.int32)
    target_length = np.asarray([len(y) for _, y in arrays], np.int32)
    x = np.zeros((len(rows), int(length.max()), WIDTH), np.float32)
    y = np.zeros((len(rows), int(target_length.max())), np.int32)
    time_valid = np.zeros((len(rows), x.shape[1], 1), np.float32)
    for i, (features, targets) in enumerate(arrays):
        x[i, : len(features)] = features
        y[i, : len(targets)] = targets
        time_valid[i, : len(features)] = 1
    return x, time_valid, y, length, target_length


def ctc_loss(tf: Any, logits: Any, targets: Any, lengths: Any, target_lengths: Any) -> Any:
    losses = tf.nn.ctc_loss(
        labels=targets,
        logits=logits,
        label_length=target_lengths,
        logit_length=lengths,
        logits_time_major=False,
        blank_index=27,
    )
    tf.debugging.assert_all_finite(losses, "[fingerspelling/ctc] Non-finite loss")
    return tf.reduce_mean(losses)


def evaluate(
    tf: Any, model: Any, rows: list[dict[str, Any]], view: str, config: dict[str, Any]
) -> dict[str, Any]:
    predictions = []
    weighted_loss = 0.0
    loss_count = 0
    infeasible = []
    for rec in rows:
        # Evaluate every sequence; structurally infeasible views still get greedy predictions.
        with np.load(REPO / rec["features_path"], allow_pickle=False) as data:
            x = np.asarray(data["features" if view == "native" else "phone_features"], np.float32)
            y = np.asarray(data["targets"], np.int32)
        logits = model([x[None], np.ones((1, len(x), 1), np.float32)], training=False)
        prediction = greedy_decode(np.argmax(logits.numpy()[0], axis=1).tolist())
        predictions.append(
            {
                "sample_id": rec["sample_id"],
                "signer_id": rec["official_signer_id"],
                "reference": rec["normalized_transcript"],
                "prediction": prediction,
            }
        )
        if len(x) >= rec["ctc_min_timesteps"]:
            weighted_loss += float(ctc_loss(tf, logits, y[None], [len(x)], [len(y)]).numpy())
            loss_count += 1
        else:
            infeasible.append(rec["sample_id"])
    metrics = summarize(predictions, config["minimum_subgroup_sequences_to_interpret"])
    return {
        "metrics": metrics,
        "ctc_mean_loss_eligible_only": weighted_loss / loss_count if loss_count else None,
        "ctc_loss_sequence_count": loss_count,
        "ctc_infeasible_retained_ids": infeasible,
        "all_sequences_greedy_evaluated": len(predictions),
        "predictions": predictions,
        "view": view,
        "role": "DEV",
        "test_accessed": False,
    }


def check(output: Path, config: dict[str, Any], report: Path) -> dict[str, Any]:
    checked = validate(output, output / "tranche_manifest.json")
    if not checked["structural_pass"]:
        raise ValueError("[fingerspelling/check] Invalid dataset")
    tf = tensorflow(config)
    model = build_model(tf, config)
    results = []
    for role in ("TRAIN", "DEV"):
        selected = [
            r for r in records(output) if r["split_role"] == role and r["native_ctc_feasible"]
        ][:2]
        if not selected:
            raise ValueError("[fingerspelling/check] Real TRAIN and DEV examples required")
        x, mask, y, lengths, target_lengths = padded_batch(selected, "native")
        logits = model([x, mask], training=False)
        value = float(ctc_loss(tf, logits, y, lengths, target_lengths).numpy())
        if tuple(logits.shape) != (len(selected), x.shape[1], 28):
            raise ValueError("[fingerspelling/check] Wrong output shape")
        prefix = max(1, int(lengths.min()) // 2)
        full = logits.numpy()[:, :prefix]
        early = model([x[:, :prefix], mask[:, :prefix]], training=False).numpy()
        np.testing.assert_allclose(full, early, atol=1e-5, rtol=1e-5)
        altered = x.copy()
        altered[:, prefix:] += 20
        np.testing.assert_allclose(
            full, model([altered, mask], training=False).numpy()[:, :prefix], atol=1e-5, rtol=1e-5
        )
        if np.any(logits.numpy()[mask[:, :, 0] == 0] != 0):
            raise ValueError("[fingerspelling/check] Padding mask not preserved")
        results.append(
            {
                "role": role,
                "sample_ids": [r["sample_id"] for r in selected],
                "input_lengths": lengths.tolist(),
                "target_lengths": target_lengths.tolist(),
                "ctc_loss_finite": np.isfinite(value).item(),
                "causality_pass": True,
            }
        )
    result = {
        "status": "ENTRY_POINT_FORWARD_AND_CTC_CHECK_PASSED",
        "no_optimizer_or_training": True,
        "parameters": model.count_params(),
        "config": config,
        "adapter": identity(),
        "tensorflow": tf.__version__,
        "checks": results,
        "scope": "Untrained model forward/loss/causality validation; no accuracy claim",
    }
    write_json_atomic(report, result)
    return result


def train(output: Path, run: Path, config_path: Path) -> None:
    config = configuration(config_path)
    pinned = json.loads((REPO / "pipeline/config/fingerspelling_execution_v1.json").read_text())
    if sha256(output / "tranche_manifest.json") != pinned["frozen_manifest_sha256"]:
        raise ValueError("[fingerspelling/training] Frozen tranche manifest changed")
    checked = validate(output, output / "tranche_manifest.json")
    if not checked["ready_to_train"]:
        raise ValueError(
            "[fingerspelling/training] Dataset not ready: " + str(checked["readiness_blockers"])
        )
    all_rows = records(output)
    feature_ids = {
        r["sample_id"]: {k: r[k] for k in ["features_sha256", "raw_sha256", "source_sha256"]}
        for r in all_rows
    }
    lineage_digest = hashlib.sha256(json.dumps(feature_ids, sort_keys=True).encode()).hexdigest()
    run_identity = {
        "config": config,
        "config_sha256": sha256(config_path),
        "seed": config["seed"],
        "adapter": identity(),
        "manifest_sha256": sha256(output / "tranche_manifest.json"),
        "dataset_lineage_sha256": lineage_digest,
        "validation_sha256_at_start": sha256(output / "validation.json"),
        "trainer_sha256": sha256(Path(__file__)),
        "metrics_sha256": sha256(REPO / "model/fingerspelling_metrics.py"),
    }
    run.mkdir(parents=True, exist_ok=True)
    config_file = run / "run_identity.json"
    if config_file.is_file():
        old = json.loads(config_file.read_text())
        if old != run_identity:
            raise ValueError(
                "[fingerspelling/training] Resume identities changed; refusing to mix runs"
            )
    else:
        write_json_atomic(config_file, run_identity)
    tf = tensorflow(config)
    model = build_model(tf, config)
    optimizer = tf.keras.optimizers.Adam(
        config["learning_rate"], clipnorm=config["gradient_clip_norm"]
    )
    optimizer.build(model.trainable_variables)
    epoch_variable = tf.Variable(0, trainable=False, dtype=tf.int64)
    ckpt = tf.train.Checkpoint(model=model, optimizer=optimizer, epoch=epoch_variable)
    manager = tf.train.CheckpointManager(
        ckpt, str(run / "checkpoints"), max_to_keep=config["checkpoint_keep"]
    )
    state_path = run / "committed_epoch.json"
    best = float("inf")
    best_model_path: str | None = None
    if state_path.is_file():
        state = json.loads(state_path.read_text())
        ckpt.restore(state["checkpoint"]).assert_existing_objects_matched()
        best = state["best_dev_cer"]
        best_model_path = state.get("best_model_path")
    elif manager.latest_checkpoint:
        raise ValueError("[fingerspelling/training] Uncommitted checkpoint requires review")
    train_rows = [r for r in all_rows if r["split_role"] == "TRAIN" and r["native_ctc_feasible"]]
    excluded_train = [
        r["sample_id"]
        for r in all_rows
        if r["split_role"] == "TRAIN" and not r["native_ctc_feasible"]
    ]
    write_json_atomic(
        run / "ctc_training_inventory.json",
        {
            "fit_ids": [r["sample_id"] for r in train_rows],
            "infeasible_retained_not_entered_into_loss": excluded_train,
            "rule": (
                "All official selected sources retained; "
                "only structurally feasible native views enter CTC loss"
            ),
        },
    )
    dev_rows = [r for r in all_rows if r["split_role"] == "DEV"]
    write_json_atomic(
        run / "environment.json",
        {
            "tensorflow": tf.__version__,
            "keras": tf.keras.__version__,
            "cpu_only": True,
            "resume_granularity": "Completed epochs; interrupted epoch is repeated",
            "resume_bit_exact_claim": False,
        },
    )
    try:
        for epoch in range(int(epoch_variable.numpy()), config["epochs"]):
            order = np.random.default_rng(config["seed"] + epoch).permutation(len(train_rows))
            losses = []
            for start in range(0, len(order), config["batch_size"]):
                rows = [train_rows[i] for i in order[start : start + config["batch_size"]]]
                x, mask, y, lengths, target_lengths = padded_batch(rows, "native")
                with tf.GradientTape() as tape:
                    logits = model([x, mask], training=True)
                    loss = ctc_loss(tf, logits, y, lengths, target_lengths)
                gradients = tape.gradient(loss, model.trainable_variables)
                for gradient in gradients:
                    if gradient is None:
                        raise RuntimeError("[fingerspelling/training] Missing gradient")
                    tf.debugging.assert_all_finite(gradient, "Non-finite gradient")
                optimizer.apply_gradients(zip(gradients, model.trainable_variables, strict=True))
                losses.append((float(loss.numpy()), len(rows)))
            views = {
                view: evaluate(tf, model, dev_rows, view, config) for view in config["dev_views"]
            }
            dev_cer = views["native"]["metrics"]["cer"]
            if dev_cer is None:
                raise RuntimeError("[fingerspelling/training] Empty DEV metric")
            if dev_cer < best:
                best = dev_cer
                candidate = run / "best_candidates" / f"epoch_{epoch + 1:03d}.keras"
                candidate.parent.mkdir(exist_ok=True)
                model.save(candidate)
                best_model_path = str(candidate)
            report = {
                "epoch": epoch + 1,
                "train_mean_ctc": sum(a * n for a, n in losses) / sum(n for _, n in losses),
                "best_native_dev_cer": best,
                "dev": views,
            }
            write_json_atomic(run / "epochs" / f"epoch_{epoch + 1:03d}.json", report)
            epoch_variable.assign(epoch + 1)
            checkpoint_path = manager.save(checkpoint_number=epoch + 1)
            write_json_atomic(
                state_path,
                {
                    "epoch": epoch + 1,
                    "checkpoint": checkpoint_path,
                    "best_dev_cer": best,
                    "best_model_path": best_model_path,
                },
            )
            with (run / "metrics.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {
                            "epoch": epoch + 1,
                            "train_ctc": report["train_mean_ctc"],
                            "dev": {k: v["metrics"] for k, v in views.items()},
                        }
                    )
                    + "\n"
                )
            print(
                json.dumps(
                    {
                        "epoch": epoch + 1,
                        "train_ctc": report["train_mean_ctc"],
                        "native_dev_cer": dev_cer,
                    }
                ),
                flush=True,
            )
        write_json_atomic(
            run / "completion.json",
            {
                "status": "BASELINE_RUN_COMPLETE",
                "epochs": config["epochs"],
                "best_native_dev_cer": best,
                "best_model_path": best_model_path,
                "test_accessed": False,
                "production_promoted": False,
            },
        )
    except BaseException as exc:
        write_json_atomic(
            run / "failure.json",
            {
                "type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "last_committed_epoch": int(epoch_variable.numpy()),
                "resume_command": (
                    "Rerun the identical user command; resume from committed_epoch.json"
                ),
            },
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument(
        "--run-dir", type=Path, default=REPO / "runs/fingerspelling_ctc_baseline_01"
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    dataset = args.dataset.resolve()
    dataset.relative_to(REPO)
    run = args.run_dir.resolve()
    run.relative_to(REPO)
    if args.check:
        print(
            json.dumps(
                check(
                    dataset,
                    configuration(args.config),
                    dataset / "execution/training_entrypoint_check.json",
                ),
                indent=2,
            )
        )
    else:
        train(dataset, run, args.config)


if __name__ == "__main__":
    main()
