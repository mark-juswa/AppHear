"""Governed P5-D9 full-training runner.

The module is deliberately inert unless --run or --run-all is supplied and
the independent human-review provenance gate is complete. It never accesses
the protected test population.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from model import p5d2_temporal_objective_ablation as d2


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5d9_semlex_supplementation_01"
D8_ATTESTATION = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5d8_supplementation_design_01/human_review_provenance_attestation.json"
MEMBERSHIP = OUT / "p5d9_derived_combined_membership.csv"
CONTRACT = OUT / "p5d9_training_contract.json"
OBJECTIVES = ("PFCE_MATCHED", "CLIPCE_AGGREGATION_ALIGNED")
SEEDS = (101, 202, 303)
UPDATES = 12_300
VALIDATE_EVERY = 123
BATCH = 32
HISTORY_FIELDS = ["objective", "seed", "validation_opportunity", "optimizer_updates", "interval_train_objective_loss", "interval_train_clip_top1", "interval_train_pf_accuracy", "validation_clip_nll", "validation_clip_top1", "validation_pf_accuracy", "learning_rate"]


def provenance_gate() -> dict[str, Any]:
    value = json.loads(D8_ATTESTATION.read_text(encoding="utf-8"))
    required = ("reviewer_name", "review_date", "attestation_date", "project_lead_confirmation")
    missing = [key for key in required if not str(value.get(key, "")).strip()]
    if missing:
        raise RuntimeError("P5D9_TRAINING_BLOCKED_BY_PROVENANCE:" + ",".join(missing))
    return {key: str(value[key]).strip() for key in required}


def read_membership() -> list[dict[str, str]]:
    with MEMBERSHIP.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    contract = json.loads((OUT / "p5d9_combined_membership_contract.json").read_text(encoding="utf-8"))
    if len(rows) != 4807 or not contract.get("passed") or contract.get("computed_membership_sha256") != "142a04b3b7954ea7a8c3d0f1e8036c5f5332c5f45a8ebca2676b9a2a029edde5":
        raise RuntimeError("P5D9_MEMBERSHIP_CONTRACT_MISMATCH")
    return rows


def load_combined(rows: list[dict[str, str]]) -> dict[str, np.ndarray]:
    apphear = d2.load_split("train")
    x = np.empty((len(rows), 96, 238), dtype=np.float32)
    y = np.empty(len(rows), dtype=np.int32)
    mask = np.empty((len(rows), 96), dtype=bool)
    sample_ids = np.empty(len(rows), dtype="U128")
    signers = np.empty(len(rows), dtype="U128")
    for destination, row in enumerate(rows):
        if row["source_dataset"] == "APPHEAR":
            source = int(row["feature_row_index"])
            x[destination] = apphear["X"][source]
            y[destination] = apphear["y"][source]
            mask[destination] = apphear["frame_mask"][source]
            if str(apphear["sample_ids"][source]) != row["sample_id"] or str(apphear["signers"][source]) != row["signer_group_id"]:
                raise RuntimeError("P5D9_APPHEAR_MEMBERSHIP_LINEAGE_MISMATCH")
        elif row["source_dataset"] == "SEMLEX":
            with np.load(Path(row["feature_path"]), allow_pickle=False) as data:
                x[destination] = np.asarray(data["features"], dtype=np.float32)
                mask[destination] = np.asarray(data["frame_mask"], dtype=bool)
                y[destination] = int(np.asarray(data["class_id"]).reshape(()))
                sample = str(np.asarray(data["sample_id"]).reshape(()).item())
                signer = "SEMLEX::" + str(np.asarray(data["signer_id"]).reshape(()).item())
            if sample != row["sample_id"] or signer != row["signer_group_id"]:
                raise RuntimeError("P5D9_SEMLEX_MEMBERSHIP_LINEAGE_MISMATCH")
        else:
            raise RuntimeError("P5D9_UNKNOWN_SOURCE")
        if int(row["class_id"]) != int(y[destination]):
            raise RuntimeError("P5D9_CLASS_MAPPING_MISMATCH")
        sample_ids[destination] = row["sample_id"]
        signers[destination] = row["signer_group_id"]
    if not np.isfinite(x).all() or np.count_nonzero(x[~mask]) != 0 or len(set(sample_ids)) != len(rows):
        raise RuntimeError("P5D9_COMBINED_TENSOR_INTEGRITY_FAILURE")
    return {"X": x, "y": y, "frame_mask": mask, "sample_ids": sample_ids, "signers": signers}


def run_dir(objective: str, seed: int) -> Path:
    return OUT / "runs" / objective / f"seed_{seed}"


def state_complete(directory: Path, objective: str, seed: int) -> bool:
    path = directory / "run_state.json"
    if not path.is_file() or not (directory / "best.keras").is_file():
        return False
    value = json.loads(path.read_text(encoding="utf-8"))
    return bool(value.get("status") == "COMPLETE" and value.get("objective") == objective and int(value.get("seed", -1)) == seed and int(value.get("completed_updates", 0)) == UPDATES and int(value.get("validation_opportunities", 0)) == 100 and value.get("checkpoint_sha256") == d2.sha256(directory / "best.keras"))


def archive_incomplete(directory: Path) -> None:
    resolved = directory.resolve()
    runs_root = (OUT / "runs").resolve()
    if runs_root not in resolved.parents:
        raise RuntimeError("P5D9_UNSAFE_RUN_DIRECTORY")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = directory.with_name(directory.name + f".incomplete_{stamp}")
    if destination.exists():
        raise RuntimeError("P5D9_INCOMPLETE_ARCHIVE_COLLISION")
    shutil.move(str(directory), str(destination))


def append_history(path: Path, row: dict[str, Any]) -> None:
    new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HISTORY_FIELDS)
        if new:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())


def train(objective: str, seed: int, restart_incomplete: bool) -> int:
    import tensorflow as tf

    provenance = provenance_gate()
    if objective not in OBJECTIVES or seed not in SEEDS:
        raise RuntimeError("P5D9_RUN_MATRIX_VIOLATION")
    directory = run_dir(objective, seed)
    if state_complete(directory, objective, seed):
        print(f"Verified completed run; skipping {objective} seed {seed}")
        return 0
    if directory.exists():
        if not restart_incomplete:
            raise RuntimeError("P5D9_INCOMPLETE_RUN_RESTART_REQUIRED")
        archive_incomplete(directory)
    directory.mkdir(parents=True)
    rows = read_membership()
    train_data = load_combined(rows)
    validation = d2.load_split("val")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    model = d2.make_model(seed)
    initialization_hash = d2.load_initialization(model, seed)
    expected_initialization = contract["initializations"][str(seed)]
    if initialization_hash != expected_initialization:
        raise RuntimeError("P5D9_INITIALIZATION_MISMATCH")
    optimizer = tf.keras.optimizers.AdamW(learning_rate=5e-4, weight_decay=1e-4)
    optimizer.build(model.trainable_variables)

    @tf.function(reduce_retracing=True)
    def step(x_batch: Any, y_batch: Any, mask_batch: Any) -> tuple[Any, Any, Any]:
        with tf.GradientTape() as tape:
            probabilities = model(x_batch, training=True)
            numerator, denominator = d2.objective_components(objective, probabilities, y_batch, mask_batch)
            loss = numerator / denominator
        gradients = tape.gradient(loss, model.trainable_variables)
        optimizer.apply_gradients(zip(gradients, model.trainable_variables))
        return numerator, denominator, probabilities

    started = time.perf_counter()
    best_nll = float("inf")
    opportunities = 0
    batches_per_pass = int(np.ceil(len(rows) / BATCH))
    interval_num = interval_den = 0.0
    interval_samples = interval_clip_correct = interval_frames = interval_pf_correct = 0
    cached_pass = -1
    order = np.empty(0, dtype=np.int64)
    d2.atomic_json(directory / "run_contract.json", {
        "objective": objective, "seed": seed, "membership_sha256": "142a04b3b7954ea7a8c3d0f1e8036c5f5332c5f45a8ebca2676b9a2a029edde5",
        "selected_manifest_sha256": "dda45f801806cd63a7ee6f59cbafe15650a402b59fb41a4f2a93a11acb6c8d08",
        "initialization_tensor_sha256": initialization_hash, "provenance": provenance,
        "updates": UPDATES, "validate_every": VALIDATE_EVERY, "checkpoint_rule": "strict minimum validation clip NLL; earliest tie retained",
    })
    for update in range(UPDATES):
        pass_index, batch_index = divmod(update, batches_per_pass)
        if pass_index != cached_pass:
            order = d2.batch_permutation(seed, pass_index, count=len(rows))
            cached_pass = pass_index
        chosen = order[batch_index * BATCH:(batch_index + 1) * BATCH]
        numerator, denominator, probability_tensor = step(tf.convert_to_tensor(train_data["X"][chosen]), tf.convert_to_tensor(train_data["y"][chosen]), tf.convert_to_tensor(train_data["frame_mask"][chosen]))
        common = d2.common_metrics(probability_tensor.numpy(), train_data["y"][chosen], train_data["frame_mask"][chosen])
        interval_num += float(numerator); interval_den += float(denominator)
        interval_samples += len(chosen); interval_clip_correct += int(round(common["clip_top1"] * len(chosen)))
        real = int(train_data["frame_mask"][chosen].sum()); interval_frames += real; interval_pf_correct += int(round(common["pf_accuracy"] * real))
        if (update + 1) % VALIDATE_EVERY == 0:
            frame = d2.infer_probabilities(model, validation["X"])
            val = d2.common_metrics(frame, validation["y"], validation["frame_mask"])
            opportunities += 1
            if val["clip_nll"] < best_nll:
                best_nll = val["clip_nll"]
                d2.save_model_atomic(model, directory / "best.keras")
                selected_update = update + 1
            append_history(directory / "history.csv", {
                "objective": objective, "seed": seed, "validation_opportunity": opportunities, "optimizer_updates": update + 1,
                "interval_train_objective_loss": interval_num / max(interval_den, 1.0),
                "interval_train_clip_top1": interval_clip_correct / max(interval_samples, 1),
                "interval_train_pf_accuracy": interval_pf_correct / max(interval_frames, 1),
                "validation_clip_nll": val["clip_nll"], "validation_clip_top1": val["clip_top1"], "validation_pf_accuracy": val["pf_accuracy"],
                "learning_rate": float(tf.keras.backend.get_value(optimizer.learning_rate)),
            })
            state = {"objective": objective, "seed": seed, "completed_updates": update + 1, "validation_opportunities": opportunities, "optimizer_iterations": int(optimizer.iterations.numpy()), "best_validation_clip_nll": best_nll, "selected_optimizer_update": selected_update, "status": "RUNNING", "elapsed_seconds": time.perf_counter() - started}
            d2.atomic_json(directory / "run_state.json", state)
            print(json.dumps(state), flush=True)
            interval_num = interval_den = 0.0
            interval_samples = interval_clip_correct = interval_frames = interval_pf_correct = 0
    checkpoint_hash = d2.sha256(directory / "best.keras")
    state.update({"status": "COMPLETE", "checkpoint_sha256": checkpoint_hash, "completed_updates": UPDATES, "validation_opportunities": 100, "optimizer_iterations": int(optimizer.iterations.numpy()), "elapsed_seconds": time.perf_counter() - started})
    d2.atomic_json(directory / "run_state.json", state)
    return 0


def run_all(restart_incomplete: bool) -> int:
    provenance_gate()
    for seed in SEEDS:
        for objective in OBJECTIVES:
            train(objective, seed, restart_incomplete)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--objective", choices=OBJECTIVES)
    parser.add_argument("--seed", type=int, choices=SEEDS)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--run-all", action="store_true")
    parser.add_argument("--restart-incomplete", action="store_true")
    args = parser.parse_args()
    if args.run_all:
        return run_all(args.restart_incomplete)
    if args.run:
        if args.objective is None or args.seed is None:
            parser.error("--run requires --objective and --seed")
        return train(args.objective, args.seed, args.restart_incomplete)
    provenance_gate()
    print("P5-D9 provenance and static contracts verified; no training requested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
