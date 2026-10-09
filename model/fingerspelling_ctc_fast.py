"""Separate opt-in execution runner; never overwrite/import the active reference run."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np

from model.fingerspelling_ctc import build_model, configuration, records, tensorflow
from model.fingerspelling_fast_execution import CompiledSteps, FeatureCache, evaluate_batched
from pipeline.fingerspelling.adapter import identity, sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import validate


def train(output: Path, run: Path, config_path: Path) -> None:
    if run.resolve() == (REPO / "runs/fingerspelling_ctc_baseline_01").resolve():
        raise ValueError("[fingerspelling/fast] Reference run is read-only")
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
        "model_reference_sha256": sha256(REPO / "model/fingerspelling_ctc.py"),
        "execution_sha256": sha256(REPO / "model/fingerspelling_fast_execution.py"),
        "execution_mode": "COMPILED_CACHED_BATCHED_DEV_V1",
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
    cache = FeatureCache()
    steps = CompiledSteps(tf, model, optimizer)
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
            epoch_start = time.perf_counter()
            train_start = epoch_start
            order = np.random.default_rng(config["seed"] + epoch).permutation(len(train_rows))
            losses = []
            for start in range(0, len(order), config["batch_size"]):
                rows = [train_rows[i] for i in order[start : start + config["batch_size"]]]
                x, mask, y, lengths, target_lengths = cache.batch(rows, "native")
                if steps.update is None:
                    raise RuntimeError("[fingerspelling/fast] Compiled optimizer missing")
                loss = steps.update(x, mask, y, lengths, target_lengths)
                losses.append((float(loss.numpy()), len(rows)))
            train_seconds = time.perf_counter() - train_start
            views, dev_seconds = {}, {}
            for view in config["dev_views"]:
                view_start = time.perf_counter()
                views[view] = evaluate_batched(tf, steps, cache, dev_rows, view, config)
                dev_seconds[view] = time.perf_counter() - view_start
            dev_cer = views["native"]["metrics"]["cer"]
            if dev_cer is None:
                raise RuntimeError("[fingerspelling/training] Empty DEV metric")
            if dev_cer < best:
                best = dev_cer
                candidate = run / "best_candidates" / f"epoch_{epoch + 1:03d}.keras"
                candidate.parent.mkdir(exist_ok=True)
                model.save(candidate)
                best_model_path = str(candidate)
            report: dict[str, Any] = {
                "epoch": epoch + 1,
                "timings": {
                    "train_seconds": train_seconds,
                    "dev_seconds": dev_seconds,
                    "before_checkpoint_seconds": time.perf_counter() - epoch_start,
                },
                "cache": {"bytes": cache.bytes, "files_loaded": cache.file_loads},
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
            elapsed = time.perf_counter() - epoch_start
            report["timings"]["epoch_seconds"] = elapsed
            report["timings"]["checkpoint_and_reports_seconds"] = (
                elapsed - train_seconds - sum(dev_seconds.values())
            )
            write_json_atomic(run / "epochs" / f"epoch_{epoch + 1:03d}.json", report)
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
                        "epoch_seconds": elapsed,
                        "stage_seconds": report["timings"],
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
    parser.add_argument(
        "--dataset", type=Path, default=REPO / "datasets/fingerspelling/foundation_01"
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--config", type=Path, default=REPO / "model/config/fingerspelling_ctc_baseline_01.json"
    )
    args = parser.parse_args()
    output, run = args.dataset.resolve(), args.run_dir.resolve()
    output.relative_to(REPO)
    run.relative_to(REPO)
    if run == (REPO / "runs/fingerspelling_ctc_baseline_01").resolve():
        raise ValueError(
            "[fingerspelling/fast] Reference run is read-only; use an independent folder"
        )
    train(output, run, args.config)


if __name__ == "__main__":
    main()
