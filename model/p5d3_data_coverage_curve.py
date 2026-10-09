"""P5-D3 nested current-data-coverage learning curve.

This module can reach only frozen DWPose V2 train/primary-validation data.
It reuses the frozen P5-D2 definitions and 100% checkpoints, and trains only
the preregistered 50% and 75% nested subsets. Protected test and external-data
paths are deliberately absent.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import numpy as np  # noqa: E402

from model import p5d2_temporal_objective_ablation as d2  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
OUT = d2.BASE / "p5_representation_v2/p5d3_data_coverage_curve_01"
D2 = d2.OUT
FRACTIONS = (50, 75, 100)
NEW_FRACTIONS = (50, 75)
OBJECTIVES = d2.BRANCHES
SEEDS = d2.SEEDS
UPDATES = 12_300
VALIDATE_EVERY = 123
VALIDATION_OPPORTUNITIES = 100
BATCH = 32
HISTORY_FIELDS = [
    "fraction", "objective", "seed", "validation_opportunity",
    "optimizer_updates", "interval_train_objective_loss",
    "interval_train_clip_top1", "interval_train_pf_accuracy",
    "validation_clip_nll", "validation_clip_top1",
    "validation_pf_accuracy", "learning_rate",
]


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def manifest_rows() -> dict[str, dict[str, str]]:
    with d2.MANIFEST.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["sample_id"]: row for row in csv.DictReader(handle)}


def d2_checkpoint_hashes() -> dict[str, str]:
    rows = read_csv(D2 / "p5d2_validation_metrics.csv")
    return {
        f"{row['branch']}|{row['seed']}": row["checkpoint_sha256"]
        for row in rows
    }


def d2_initialization_hashes() -> dict[str, dict[str, str]]:
    rows = read_csv(D2 / "p5d2_initialization_parity.csv")
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        result.setdefault(row["seed"], {
            "file_sha256": row["initialization_file_sha256"],
            "tensor_sha256": row["initial_weight_tensor_sha256"],
            "path": row["initialization_path"],
        })
    return result


def d2_reuse_integrity() -> dict[str, Any]:
    integrity = json.loads((D2 / "p5d2_integrity.json").read_text(encoding="utf-8"))
    artifact_manifest = json.loads((D2 / "artifact_hash_manifest.json").read_text(encoding="utf-8"))
    code_record = artifact_manifest["supporting_code"]
    initialization = d2_initialization_hashes()
    init_checks = {}
    for seed in SEEDS:
        record = initialization[str(seed)]
        path = Path(record["path"])
        init_checks[str(seed)] = {
            "path": str(path),
            "expected_sha256": record["file_sha256"],
            "actual_sha256": d2.sha256(path),
            "passed": path.is_file() and d2.sha256(path) == record["file_sha256"],
        }
    checkpoint_expected = d2_checkpoint_hashes()
    checkpoint_checks = {}
    for seed in SEEDS:
        for objective in OBJECTIVES:
            path = D2 / "runs" / objective / f"seed_{seed}" / "best.keras"
            key = f"{objective}|{seed}"
            checkpoint_checks[key] = {
                "path": str(path.resolve()),
                "expected_sha256": checkpoint_expected[key],
                "actual_sha256": d2.sha256(path),
                "passed": path.is_file() and d2.sha256(path) == checkpoint_expected[key],
            }
    return {
        "d2_integrity_passed": bool(integrity.get("passed") and integrity.get("six_runs_complete")),
        "source_hashes_match": d2.source_hashes() == d2.EXPECTED_HASHES,
        "d2_runner_hash_match": d2.sha256(Path(code_record["path"])) == code_record["sha256"],
        "initializations": init_checks,
        "checkpoints": checkpoint_checks,
        "passed": bool(
            integrity.get("passed") and integrity.get("six_runs_complete")
            and d2.source_hashes() == d2.EXPECTED_HASHES
            and d2.sha256(Path(code_record["path"])) == code_record["sha256"]
            and all(row["passed"] for row in init_checks.values())
            and all(row["passed"] for row in checkpoint_checks.values())
        ),
    }


def build_master_order(data: dict[str, np.ndarray]) -> tuple[list[dict[str, Any]], dict[int, list[int]]]:
    manifest = manifest_rows()
    by_class_signer: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for index, (class_id, signer) in enumerate(zip(data["y"], data["signers"])):
        by_class_signer[int(class_id)][str(signer)].append(index)
    rows: list[dict[str, Any]] = []
    orders: dict[int, list[int]] = {}
    for class_id in range(d2.CLASSES):
        signer_samples = by_class_signer[class_id]
        signer_order = sorted(
            signer_samples,
            key=lambda signer: stable_hash(f"P5D3_SUBSET_V1|{class_id}|{signer}|SIGNER"),
        )
        ordered_within: dict[str, list[int]] = {}
        for signer in signer_order:
            ordered_within[signer] = sorted(
                signer_samples[signer],
                key=lambda index: stable_hash(
                    f"P5D3_SUBSET_V1|{class_id}|{signer}|{str(data['sample_ids'][index])}"
                ),
            )
        master: list[int] = []
        for round_index in range(max(len(values) for values in ordered_within.values())):
            for signer in signer_order:
                values = ordered_within[signer]
                if round_index < len(values):
                    master.append(values[round_index])
        orders[class_id] = master
        n50 = math.ceil(0.50 * len(master)); n75 = math.ceil(0.75 * len(master))
        for master_index, index in enumerate(master):
            sample_id = str(data["sample_ids"][index]); lineage = manifest[sample_id]
            rows.append({
                "sample_id": sample_id,
                "class_id": class_id,
                "gloss": lineage["canonical_gloss"],
                "signer_group_id": str(data["signers"][index]),
                "source": lineage["source_dataset"],
                "master_order_index": master_index,
                "included_50": int(master_index < n50),
                "included_75": int(master_index < n75),
                "included_100": 1,
                "train_tensor_index": index,
            })
    return rows, orders


def subset_indices(rows: list[dict[str, Any]], fraction: int) -> np.ndarray:
    field = f"included_{fraction}"
    return np.asarray(sorted(int(row["train_tensor_index"]) for row in rows if int(row[field]) == 1), dtype=np.int64)


def effective_count(values: list[str]) -> float:
    counts = np.asarray(list(Counter(values).values()), dtype=np.float64)
    shares = counts / counts.sum()
    return float(1.0 / np.sum(shares ** 2))


def coverage_profiles(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[tuple[int, int], dict[str, float]]]:
    output: list[dict[str, Any]] = []
    lookup: dict[tuple[int, int], dict[str, float]] = {}
    for fraction in FRACTIONS:
        selected = [row for row in rows if int(row[f"included_{fraction}"]) == 1]
        class_rows = []
        for class_id in range(d2.CLASSES):
            chosen = [row for row in selected if int(row["class_id"]) == class_id]
            signer_counts = Counter(str(row["signer_group_id"]) for row in chosen)
            source_counts = Counter(str(row["source"]) for row in chosen)
            record = {
                "row_type": "CLASS", "fraction": fraction, "statistic": "",
                "class_id": class_id, "gloss": chosen[0]["gloss"], "clips": len(chosen),
                "unique_signers": len(signer_counts),
                "effective_signer_count": effective_count([str(row["signer_group_id"]) for row in chosen]),
                "largest_signer_share": max(signer_counts.values()) / len(chosen),
                "clips_per_signer_json": json.dumps(dict(sorted(signer_counts.items())), sort_keys=True),
                "source_composition_json": json.dumps(dict(sorted(source_counts.items())), sort_keys=True),
            }
            class_rows.append(record); output.append(record)
            lookup[(fraction, class_id)] = {
                "clips": float(record["clips"]), "unique_signers": float(record["unique_signers"]),
                "effective_signer_count": float(record["effective_signer_count"]),
            }
        for statistic, percentile in (("p10", 10), ("p25", 25), ("p50", 50), ("p75", 75), ("p90", 90), ("p95", 95)):
            summary = {"row_type": "SUMMARY", "fraction": fraction, "statistic": statistic, "class_id": "", "gloss": "__SUMMARY__", "clips_per_signer_json": "", "source_composition_json": ""}
            for field in ("clips", "unique_signers", "effective_signer_count", "largest_signer_share"):
                summary[field] = float(np.percentile([float(row[field]) for row in class_rows], percentile))
            output.append(summary)
    return output, lookup


def run_dir(fraction: int, objective: str, seed: int) -> Path:
    return OUT / "runs" / str(fraction) / objective / f"seed_{seed}"


def batch_permutation(seed: int, fraction: int, pass_index: int, count: int) -> np.ndarray:
    sequence = np.random.SeedSequence([seed, fraction, pass_index, 0xD3])
    return np.random.Generator(np.random.PCG64(sequence)).permutation(count)


def contract(counts: dict[int, int], reuse: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_id": "P5D3_NESTED_DATA_COVERAGE_CURVE_V1",
        "status": "FROZEN_BEFORE_NEW_TRAINING",
        "single_experimental_factor": "amount of existing training coverage",
        "objectives_as_fixed_factor": list(OBJECTIVES),
        "fractions": list(FRACTIONS), "counts": {str(key): value for key, value in counts.items()},
        "nesting": "50 subset 75 subset 100; one seed/objective-independent signer-first master order",
        "ordering": "SHA256 P5D3_SUBSET_V1 keys; signer-first deterministic round robin within class",
        "per_class_counts": "ceil(0.50*N), ceil(0.75*N), N",
        "representation": "DWPOSE_REPRESENTATION_V2_238", "input": [96, 238], "classes": 236,
        "model": {"architecture": "4x64 causal TCN", "kernel": 3, "dilations": [1, 2, 4, 8], "dropout": 0.3, "parameters": 163884, "output": [96, 236]},
        "objectives": json.loads((D2 / "p5d2_objective_contract.json").read_text(encoding="utf-8"))["objectives"],
        "training": {"optimizer": "AdamW", "learning_rate": 5e-4, "weight_decay": 1e-4, "batch": 32, "optimizer_updates": UPDATES, "validation_every_updates": VALIDATE_EVERY, "validation_opportunities": VALIDATION_OPPORTUNITIES, "checkpoint_selection": "minimum primary-validation clip NLL", "augmentation": "NONE", "class_weights": "NONE", "source_balancing": "NONE", "warm_start": "NONE"},
        "seeds": list(SEEDS), "new_runs": 12, "reused_d2_runs": 6,
        "initializations": d2_initialization_hashes(), "d2_checkpoint_reuse": d2_checkpoint_hashes(),
        "decision_rule": {
            "CURRENT_DATA_COVERAGE_LIMITATION_SUPPORTED_BROADLY": "both objectives pass the preregistered objective-scaling rule",
            "DATA_COVERAGE_OBJECTIVE_INTERACTION": "exactly one objective passes the objective-scaling rule",
            "CURRENT_DATA_DISTRIBUTION_NEAR_PLATEAU": "integrity-valid result where neither objective passes and severe cross-seed instability is absent",
            "DATA_CURVE_MIXED_OR_INCONCLUSIVE": "integrity/reuse failure or mixed-sign 75-to-100 delta range > max(0.10, four times 100-percent seed SD)",
            "objective_scaling_rule": "median Top1 strictly 50<75<100; 75-to-100 Top1 and MacroF1 positive >=2/3 seeds; median signer-balanced delta positive; median Top1 gain >= 100-percent seed SD; median signer-seed delta nonnegative and no seed has >60% signers regress",
        },
        "source_hashes": d2.source_hashes(), "d2_reuse_integrity": reuse,
        "protected_test_access": False, "external_data": "DEFERRED_NOT_REJECTED",
    }


def prepare() -> int:
    if OUT.exists():
        raise RuntimeError("P5D3_OUTPUT_EXISTS")
    OUT.mkdir(parents=True)
    context_before = d2.context_hashes(); reuse = d2_reuse_integrity(); train = d2.load_split("train"); val = d2.load_split("val")
    rows, _ = build_master_order(train)
    counts = {fraction: len(subset_indices(rows, fraction)) for fraction in FRACTIONS}
    sets = {fraction: set(map(int, subset_indices(rows, fraction))) for fraction in FRACTIONS}
    class_presence = {fraction: len(set(int(row["class_id"]) for row in rows if int(row[f"included_{fraction}"]) == 1)) for fraction in FRACTIONS}
    val_ids = set(map(str, val["sample_ids"])); selected_ids = {str(row["sample_id"]) for row in rows}
    subset_integrity = {
        "counts": {str(key): value for key, value in counts.items()},
        "nested": sets[50] < sets[75] < sets[100],
        "all_classes": {str(key): value == d2.CLASSES for key, value in class_presence.items()},
        "no_duplicate_membership_rows": len(rows) == len({str(row["sample_id"]) for row in rows}) == d2.COUNTS["train"],
        "no_validation_in_train": not bool(selected_ids & val_ids),
        "full_population_exact": sets[100] == set(range(d2.COUNTS["train"])),
        "labels_and_signers_match_tensor": all(int(row["class_id"]) == int(train["y"][int(row["train_tensor_index"])]) and str(row["signer_group_id"]) == str(train["signers"][int(row["train_tensor_index"])]) for row in rows),
    }
    subset_integrity["passed"] = bool(reuse["passed"] and all(subset_integrity["all_classes"].values()) and all(value for key, value in subset_integrity.items() if key not in {"counts", "all_classes", "passed"}))
    membership_fields = ["sample_id", "class_id", "gloss", "signer_group_id", "source", "master_order_index", "included_50", "included_75", "included_100", "train_tensor_index"]
    d2.write_csv(OUT / "p5d3_subset_membership.csv", sorted(rows, key=lambda row: (int(row["class_id"]), int(row["master_order_index"]))), membership_fields)
    profiles, _ = coverage_profiles(rows)
    d2.write_csv(OUT / "p5d3_data_coverage_profile.csv", profiles, list(profiles[0]))
    frozen_contract = contract(counts, reuse); d2.atomic_json(OUT / "p5d3_subset_contract.json", frozen_contract)
    run_rows = []
    for fraction in FRACTIONS:
        for objective in OBJECTIVES:
            for seed in SEEDS:
                run_rows.append({"fraction": fraction, "objective": objective, "seed": seed, "status": "REUSED_D2" if fraction == 100 else "PLANNED", "optimizer_updates": UPDATES, "validation_opportunities": VALIDATION_OPPORTUNITIES, "output_directory": str((D2 / "runs" / objective / f"seed_{seed}").resolve()) if fraction == 100 else str(run_dir(fraction, objective, seed).resolve())})
    d2.write_csv(OUT / "p5d3_run_matrix.csv", run_rows, list(run_rows[0]))
    budget = []
    for fraction in NEW_FRACTIONS:
        subset_count = counts[fraction]; batches_per_pass = math.ceil(subset_count / BATCH)
        for objective in OBJECTIVES:
            for seed in SEEDS:
                budget.append({"fraction": fraction, "objective": objective, "seed": seed, "subset_samples": subset_count, "batch_size": BATCH, "batches_per_full_pass": batches_per_pass, "required_optimizer_updates": UPDATES, "validation_every_updates": VALIDATE_EVERY, "required_validation_opportunities": VALIDATION_OPPORTUNITIES, "actual_optimizer_updates": 0, "actual_validation_opportunities": 0, "status": "PLANNED"})
    d2.write_csv(OUT / "p5d3_training_budget_audit.csv", budget, list(budget[0]))
    integrity = {
        "passed": subset_integrity["passed"] and context_before == d2.context_hashes(),
        "d2_reuse": reuse, "subset_integrity": subset_integrity,
        "source_hashes_before": d2.source_hashes(), "context_hashes_at_freeze": context_before,
        "training_performed": False, "new_runs_complete": 0, "protected_test_accessed": False,
        "external_data_used": False, "context_files_modified": context_before != d2.context_hashes(),
        "progress_tracker_untouched": context_before == d2.context_hashes(),
    }
    d2.atomic_json(OUT / "p5d3_integrity.json", integrity)
    print(json.dumps({"status": "P5D3_PREPARED", "integrity_passed": integrity["passed"], "actual_counts": counts, "contract_sha256": d2.sha256(OUT / "p5d3_subset_contract.json")}, indent=2))
    return 0 if integrity["passed"] else 2


def assert_prepared() -> dict[str, Any]:
    integrity = json.loads((OUT / "p5d3_integrity.json").read_text(encoding="utf-8"))
    contract_data = json.loads((OUT / "p5d3_subset_contract.json").read_text(encoding="utf-8"))
    if not integrity.get("passed") or contract_data["source_hashes"] != d2.source_hashes() or not d2_reuse_integrity()["passed"]:
        raise RuntimeError("P5D3_FROZEN_INTEGRITY_FAILURE")
    return contract_data


def load_membership() -> list[dict[str, Any]]:
    rows = read_csv(OUT / "p5d3_subset_membership.csv")
    return [{**row, "class_id": int(row["class_id"]), "master_order_index": int(row["master_order_index"]), "included_50": int(row["included_50"]), "included_75": int(row["included_75"]), "included_100": int(row["included_100"]), "train_tensor_index": int(row["train_tensor_index"])} for row in rows]


def unit_tests() -> int:
    import tensorflow as tf

    contract_data = assert_prepared(); rows = load_membership()
    sets = {fraction: set(map(int, subset_indices(rows, fraction))) for fraction in FRACTIONS}
    tests: dict[str, Any] = {}
    tests["nested_subsets"] = {"passed": sets[50] < sets[75] < sets[100], "counts": {str(key): len(value) for key, value in sets.items()}}
    tests["all_classes"] = {"passed": all(len({int(row["class_id"]) for row in rows if int(row[f"included_{fraction}"])}) == d2.CLASSES for fraction in FRACTIONS)}
    validation_points = list(range(VALIDATE_EVERY, UPDATES + 1, VALIDATE_EVERY))
    tests["update_budget"] = {"passed": len(validation_points) == VALIDATION_OPPORTUNITIES and validation_points[-1] == UPDATES, "validation_points": len(validation_points), "last_update": validation_points[-1]}
    schedule_checks = []
    for fraction in NEW_FRACTIONS:
        count = int(contract_data["counts"][str(fraction)]); batches = math.ceil(count / BATCH)
        for seed in SEEDS:
            for pass_index in (0, 1, UPDATES // batches):
                a = batch_permutation(seed, fraction, pass_index, count); b = batch_permutation(seed, fraction, pass_index, count)
                schedule_checks.append(np.array_equal(a, b) and len(np.unique(a)) == count)
    tests["batch_schedule"] = {"passed": all(schedule_checks), "checks": len(schedule_checks), "shared_across_objectives": True}
    init_checks = []
    for seed in SEEDS:
        left = d2.make_model(seed); right = d2.make_model(seed)
        left_hash = d2.load_initialization(left, seed); right_hash = d2.load_initialization(right, seed)
        init_checks.append(left_hash == right_hash == contract_data["initializations"][str(seed)]["tensor_sha256"] and left.count_params() == right.count_params() == 163884)
    tests["initialization_and_parameters"] = {"passed": all(init_checks), "seeds": len(init_checks)}
    rng = np.random.default_rng(101); model = d2.make_model(101); d2.load_initialization(model, 101)
    optimizer = tf.keras.optimizers.AdamW(learning_rate=5e-4, weight_decay=1e-4); optimizer.build(model.trainable_variables)
    x = tf.constant(rng.normal(size=(2, 96, d2.WIDTH)).astype(np.float32)); y = tf.constant([1, 2]); mask = tf.constant(np.ones((2, 96), dtype=bool))
    with tf.GradientTape() as tape:
        probabilities = model(x, training=True); numerator, denominator = d2.objective_components("CLIPCE_AGGREGATION_ALIGNED", probabilities, y, mask); loss = numerator / denominator
    optimizer.apply_gradients(zip(tape.gradient(loss, model.trainable_variables), model.trainable_variables))
    with tempfile.TemporaryDirectory(prefix="p5d3_smoke_") as temporary:
        checkpoint = tf.train.Checkpoint(model=model, optimizer=optimizer); manager = tf.train.CheckpointManager(checkpoint, temporary, max_to_keep=1); saved = manager.save(checkpoint_number=1)
        restored_model = d2.make_model(101); restored_optimizer = tf.keras.optimizers.AdamW(learning_rate=5e-4, weight_decay=1e-4); restored_optimizer.build(restored_model.trainable_variables)
        tf.train.Checkpoint(model=restored_model, optimizer=restored_optimizer).restore(saved).assert_existing_objects_matched()
        resume_pass = int(restored_optimizer.iterations.numpy()) == 1 and d2.tensor_hash([np.asarray(value) for value in restored_model.get_weights()]) == d2.tensor_hash([np.asarray(value) for value in model.get_weights()])
    tests["bounded_resume_state"] = {"passed": resume_pass, "optimizer_iterations": int(restored_optimizer.iterations.numpy()), "synthetic_only": True}
    tests["d2_objective_tests_reused"] = {"passed": json.loads((D2 / "p5d2_unit_tests.json").read_text(encoding="utf-8"))["passed"]}
    tests["passed"] = all(row.get("passed", False) for row in tests.values())
    d2.atomic_json(OUT / "p5d3_smoke_tests.json", tests)
    print(json.dumps(tests, indent=2))
    return 0 if tests["passed"] else 2


def set_table_status(path: Path, fraction: int, objective: str, seed: int, status: str, updates: int | None = None, opportunities: int | None = None) -> None:
    rows = read_csv(path)
    for row in rows:
        if int(row["fraction"]) == fraction and row["objective"] == objective and int(row["seed"]) == seed:
            row["status"] = status
            if updates is not None and "actual_optimizer_updates" in row: row["actual_optimizer_updates"] = updates
            if opportunities is not None and "actual_validation_opportunities" in row: row["actual_validation_opportunities"] = opportunities
    d2.write_csv(path, rows, list(rows[0]))


def save_model_atomic(model: Any, path: Path) -> None:
    temporary = path.with_name(path.stem + ".tmp.keras")
    if temporary.exists(): temporary.unlink()
    model.save(temporary); os.replace(temporary, path)


def train(fraction: int, objective: str, seed: int, resume: bool) -> int:
    import tensorflow as tf

    if fraction not in NEW_FRACTIONS: raise RuntimeError("P5D3_ONLY_50_75_ARE_NEW")
    assert_prepared()
    if not json.loads((OUT / "p5d3_smoke_tests.json").read_text(encoding="utf-8")).get("passed"): raise RuntimeError("P5D3_SMOKE_GATE_FAILED")
    train_data = d2.load_split("train"); validation = d2.load_split("val"); rows = load_membership(); indices = subset_indices(rows, fraction); count = len(indices); batches_per_pass = math.ceil(count / BATCH)
    directory = run_dir(fraction, objective, seed); state_path = directory / "run_state.json"; history_path = directory / "history.csv"
    if resume:
        if not state_path.is_file(): raise RuntimeError("P5D3_NO_RESUMABLE_STATE")
    else:
        if directory.exists(): raise RuntimeError("P5D3_RUN_EXISTS_USE_RESUME")
        directory.mkdir(parents=True); d2.write_csv(history_path, [], HISTORY_FIELDS)
    model = d2.make_model(seed); loaded_hash = d2.load_initialization(model, seed)
    expected_hash = d2_initialization_hashes()[str(seed)]["tensor_sha256"]
    if loaded_hash != expected_hash: raise RuntimeError("P5D3_INITIALIZATION_MISMATCH")
    optimizer = tf.keras.optimizers.AdamW(learning_rate=5e-4, weight_decay=1e-4); optimizer.build(model.trainable_variables)
    completed_updates = tf.Variable(0, trainable=False, dtype=tf.int64); best_nll = tf.Variable(np.inf, trainable=False, dtype=tf.float64); opportunities = tf.Variable(0, trainable=False, dtype=tf.int64)
    checkpoint = tf.train.Checkpoint(model=model, optimizer=optimizer, completed_updates=completed_updates, best_validation_clip_nll=best_nll, validation_opportunities=opportunities)
    manager = tf.train.CheckpointManager(checkpoint, str(directory / "resume_state"), max_to_keep=2)
    if resume:
        if not manager.latest_checkpoint: raise RuntimeError("P5D3_NO_CHECKPOINT")
        checkpoint.restore(manager.latest_checkpoint).assert_existing_objects_matched()
    else:
        initial = manager.save(checkpoint_number=0)
        d2.atomic_json(state_path, {"fraction": fraction, "objective": objective, "seed": seed, "completed_updates": 0, "validation_opportunities": 0, "best_validation_clip_nll": None, "optimizer_iterations": 0, "latest_checkpoint": initial, "status": "READY"})

    @tf.function(reduce_retracing=True)
    def step(x_batch: Any, y_batch: Any, mask_batch: Any) -> tuple[Any, Any, Any]:
        with tf.GradientTape() as tape:
            probabilities = model(x_batch, training=True); numerator, denominator = d2.objective_components(objective, probabilities, y_batch, mask_batch); loss = numerator / denominator
        optimizer.apply_gradients(zip(tape.gradient(loss, model.trainable_variables), model.trainable_variables))
        return numerator, denominator, probabilities

    start_update = int(completed_updates.numpy()); set_table_status(OUT / "p5d3_run_matrix.csv", fraction, objective, seed, "RUNNING")
    interval_num = interval_den = 0.0; interval_clip_correct = interval_pf_correct = interval_frames = interval_samples = 0
    cached_pass = -1; order = np.empty(0, dtype=np.int64)
    for update in range(start_update, UPDATES):
        pass_index = update // batches_per_pass; batch_index = update % batches_per_pass
        if pass_index != cached_pass:
            order = batch_permutation(seed, fraction, pass_index, count); cached_pass = pass_index
        local = order[batch_index * BATCH:(batch_index + 1) * BATCH]; chosen = indices[local]
        numerator, denominator, probability_tensor = step(tf.convert_to_tensor(train_data["X"][chosen]), tf.convert_to_tensor(train_data["y"][chosen]), tf.convert_to_tensor(train_data["frame_mask"][chosen]))
        probabilities = probability_tensor.numpy(); common = d2.common_metrics(probabilities, train_data["y"][chosen], train_data["frame_mask"][chosen])
        interval_num += float(numerator); interval_den += float(denominator); interval_samples += len(chosen); interval_clip_correct += int(round(common["clip_top1"] * len(chosen))); real = int(train_data["frame_mask"][chosen].sum()); interval_frames += real; interval_pf_correct += int(round(common["pf_accuracy"] * real))
        if (update + 1) % VALIDATE_EVERY == 0:
            val_probabilities = d2.infer_probabilities(model, validation["X"]); val_common = d2.common_metrics(val_probabilities, validation["y"], validation["frame_mask"])
            if val_common["clip_nll"] < float(best_nll.numpy()): best_nll.assign(val_common["clip_nll"]); save_model_atomic(model, directory / "best.keras")
            completed_updates.assign(update + 1); opportunities.assign_add(1); saved = manager.save(checkpoint_number=update + 1)
            row = {"fraction": fraction, "objective": objective, "seed": seed, "validation_opportunity": int(opportunities.numpy()), "optimizer_updates": update + 1, "interval_train_objective_loss": interval_num / max(interval_den, 1.0), "interval_train_clip_top1": interval_clip_correct / max(interval_samples, 1), "interval_train_pf_accuracy": interval_pf_correct / max(interval_frames, 1), "validation_clip_nll": val_common["clip_nll"], "validation_clip_top1": val_common["clip_top1"], "validation_pf_accuracy": val_common["pf_accuracy"], "learning_rate": float(tf.keras.backend.get_value(optimizer.learning_rate))}
            with history_path.open("a", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=HISTORY_FIELDS); writer.writerow(row); handle.flush(); os.fsync(handle.fileno())
            status = "MAX_UPDATES_REACHED" if update + 1 == UPDATES else "RUNNING"
            state = {"fraction": fraction, "objective": objective, "seed": seed, "completed_updates": update + 1, "validation_opportunities": int(opportunities.numpy()), "best_validation_clip_nll": float(best_nll.numpy()), "optimizer_iterations": int(optimizer.iterations.numpy()), "latest_checkpoint": saved, "status": status}
            d2.atomic_json(state_path, state); print(json.dumps(state), flush=True)
            interval_num = interval_den = 0.0; interval_clip_correct = interval_pf_correct = interval_frames = interval_samples = 0
    set_table_status(OUT / "p5d3_run_matrix.csv", fraction, objective, seed, "MAX_UPDATES_REACHED")
    set_table_status(OUT / "p5d3_training_budget_audit.csv", fraction, objective, seed, "PASS", UPDATES, VALIDATION_OPPORTUNITIES)
    return 0


def train_all() -> int:
    assert_prepared()
    for fraction in NEW_FRACTIONS:
        for seed in SEEDS:
            for objective in OBJECTIVES:
                directory = run_dir(fraction, objective, seed); state_path = directory / "run_state.json"
                if state_path.is_file():
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    if state.get("status") == "MAX_UPDATES_REACHED" and int(state.get("completed_updates", 0)) == UPDATES: continue
                train(fraction, objective, seed, resume=directory.exists())
    return 0


def objective_loss_numpy(objective: str, frame: np.ndarray, clip: np.ndarray, labels: np.ndarray, mask: np.ndarray) -> float:
    true_frame = frame[np.arange(len(labels))[:, None], np.arange(frame.shape[1])[None, :], labels[:, None]].astype(np.float64)
    if objective == "PFCE_MATCHED": return float(np.sum(-np.log(np.clip(true_frame, d2.EPSILON, 1.0)) * mask) / np.sum(mask))
    return float(np.mean(-np.log(np.clip(clip[np.arange(len(labels)), labels], d2.EPSILON, 1.0))))


def evaluate_point(fraction: int, objective: str, seed: int, membership: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, np.ndarray], dict[int, tuple[int, float]]]:
    import tensorflow as tf

    checkpoint_path = (D2 / "runs" / objective / f"seed_{seed}" / "best.keras") if fraction == 100 else (run_dir(fraction, objective, seed) / "best.keras")
    if fraction != 100:
        state = json.loads((run_dir(fraction, objective, seed) / "run_state.json").read_text(encoding="utf-8"))
        if state.get("status") != "MAX_UPDATES_REACHED" or state.get("completed_updates") != UPDATES or state.get("validation_opportunities") != VALIDATION_OPPORTUNITIES or state.get("optimizer_iterations") != UPDATES: raise RuntimeError(f"P5D3_RUN_INCOMPLETE:{fraction}:{objective}:{seed}")
    model = tf.keras.models.load_model(checkpoint_path, safe_mode=False); train = d2.load_split("train"); val = d2.load_split("val"); indices = subset_indices(membership, fraction)
    train_frame = d2.infer_probabilities(model, train["X"][indices]); train_mask = train["frame_mask"][indices]; train_y = train["y"][indices]; train_clip = (train_frame.astype(np.float64) * train_mask[:, :, None]).sum(axis=1) / np.maximum(train_mask.sum(axis=1, keepdims=True), 1); train_prediction = train_clip.argmax(axis=1); train_objective = objective_loss_numpy(objective, train_frame, train_clip, train_y, train_mask); train_top1 = float(np.mean(train_prediction == train_y)); train_pf = float(np.sum((train_frame.argmax(axis=2) == train_y[:, None]) * train_mask) / train_mask.sum()); del train_frame, train_clip
    frame = d2.infer_probabilities(model, val["X"]); clip = (frame.astype(np.float64) * val["frame_mask"][:, :, None]).sum(axis=1) / np.maximum(val["frame_mask"].sum(axis=1, keepdims=True), 1); prediction = clip.argmax(axis=1); top5 = np.argsort(clip, axis=1)[:, -5:]
    selected_update = (int(min(read_csv(run_dir(fraction, objective, seed) / "history.csv"), key=lambda row: float(row["validation_clip_nll"]))["optimizer_updates"]) if fraction != 100 else (int(next(row for row in read_csv(D2 / "p5d2_validation_metrics.csv") if row["branch"] == objective and int(row["seed"]) == seed)["selected_epoch"]) + 1) * VALIDATE_EVERY)
    metric = {"fraction": fraction, "objective": objective, "seed": seed, "selected_optimizer_update": selected_update, "checkpoint_sha256": d2.sha256(checkpoint_path), "clip_top1": float(np.mean(prediction == val["y"])), "signer_balanced_top1": 0.0, "clip_top5": float(np.mean([val["y"][i] in top5[i] for i in range(len(val["y"]))])), "macro_f1": d2.macro_f1(val["y"], prediction), "validation_clip_nll": float(np.mean(-np.log(np.clip(clip[np.arange(len(val["y"])), val["y"]], d2.EPSILON, 1.0)))), "pf_accuracy": float(np.sum((frame.argmax(axis=2) == val["y"][:, None]) * val["frame_mask"]) / val["frame_mask"].sum()), "train_clip_top1": train_top1, "train_pf_accuracy": train_pf, "train_objective_metric": train_objective, "train_validation_top1_gap": train_top1 - float(np.mean(prediction == val["y"]))}
    signer_rows = []
    for signer in sorted(set(map(str, val["signers"]))):
        chosen = np.asarray([str(value) == signer for value in val["signers"]]); signer_rows.append({"fraction": fraction, "objective": objective, "seed": seed, "signer_group_id": signer, "clips": int(chosen.sum()), "top1": float(np.mean(prediction[chosen] == val["y"][chosen])), "macro_f1": d2.macro_f1(val["y"][chosen], prediction[chosen])})
    metric["signer_balanced_top1"] = float(np.mean([row["top1"] for row in signer_rows]))
    taxonomy = []
    for index in range(len(val["y"])):
        true = int(val["y"][index]); predicted = int(prediction[index])
        if predicted == true: continue
        real = np.flatnonzero(val["frame_mask"][index]); thirds = np.array_split(real, 3); third_margins = [float(np.mean(frame[index, third, true] - frame[index, third, predicted])) if len(third) else 0.0 for third in thirds]; frame_margin = frame[index, real, true] - frame[index, real, predicted]
        if all(value < 0 for value in third_margins): category = "PERSISTENT_WRONG_CLASS"
        elif float(np.mean(frame_margin > 0)) > 0.5: category = "TRUE_TEMPORAL_MAJORITY_BUT_FINAL_WRONG"
        elif any(value > 0 for value in third_margins) and any(value < 0 for value in third_margins): category = "PHASE_DEPENDENT_CONFUSION"
        else: category = "OTHER"
        taxonomy.append({"fraction": fraction, "objective": objective, "seed": seed, "sample_id": str(val["sample_ids"][index]), "signer_group_id": str(val["signers"][index]), "true_class": true, "predicted_class": predicted, "category": category})
    per_class = {}
    for class_id in range(d2.CLASSES):
        chosen = val["y"] == class_id; per_class[class_id] = (int(chosen.sum()), float(np.mean(prediction[chosen] == class_id)) if chosen.any() else float("nan"))
    arrays = {"y": val["y"], "prediction": prediction, "signers": val["signers"]}
    return metric, signer_rows, taxonomy, arrays, per_class


def bootstrap_75_100(arrays_75: dict[str, np.ndarray], arrays_100: dict[str, np.ndarray], objective: str, seed: int) -> list[dict[str, Any]]:
    y = arrays_75["y"]
    if not np.array_equal(y, arrays_100["y"]) or not np.array_equal(arrays_75["signers"], arrays_100["signers"]): raise RuntimeError("P5D3_BOOTSTRAP_ALIGNMENT")
    signers = sorted(set(map(str, arrays_75["signers"]))); indices = {signer: np.flatnonzero(np.asarray([str(value) == signer for value in arrays_75["signers"]])) for signer in signers}; rng = np.random.Generator(np.random.PCG64(seed + (0 if objective == "PFCE_MATCHED" else 10_000))); top = np.empty(10_000); f1 = np.empty(10_000)
    for replicate in range(10_000):
        draw = rng.choice(signers, len(signers), replace=True); chosen = np.concatenate([indices[str(value)] for value in draw]); top[replicate] = np.mean(arrays_100["prediction"][chosen] == y[chosen]) - np.mean(arrays_75["prediction"][chosen] == y[chosen]); f1[replicate] = d2.macro_f1(y[chosen], arrays_100["prediction"][chosen]) - d2.macro_f1(y[chosen], arrays_75["prediction"][chosen])
    return [{"objective": objective, "seed": seed, "metric": name, "point_delta_100_minus_75": float(np.mean(values)), "ci95_low": float(np.percentile(values, 2.5)), "ci95_high": float(np.percentile(values, 97.5)), "replicates": 10000, "cluster_unit": "signer_group_id"} for name, values in (("Top1", top), ("MacroF1", f1))]


def finalize() -> int:
    assert_prepared(); membership = load_membership(); profiles, profile_lookup = coverage_profiles(membership); metrics = []; signer_rows = []; taxonomy = []; arrays = {}; per_class = {}; histories = []
    for fraction in FRACTIONS:
        for objective in OBJECTIVES:
            for seed in SEEDS:
                metric, signers, failures, saved, class_recall = evaluate_point(fraction, objective, seed, membership); metrics.append(metric); signer_rows.extend(signers); taxonomy.extend(failures); arrays[(fraction, objective, seed)] = saved; per_class[(fraction, objective, seed)] = class_recall
                if fraction == 100:
                    for row in read_csv(D2 / "p5d2_training_histories.csv"):
                        if row["branch"] == objective and int(row["seed"]) == seed: histories.append({"fraction": 100, "objective": objective, "seed": seed, "validation_opportunity": int(row["epoch"]) + 1, "optimizer_updates": int(row["optimizer_iterations"]), "interval_train_objective_loss": row["train_objective_loss"], "interval_train_clip_top1": row["train_clip_top1"], "interval_train_pf_accuracy": row["train_pf_accuracy"], "validation_clip_nll": row["validation_clip_nll"], "validation_clip_top1": row["validation_clip_top1"], "validation_pf_accuracy": row["validation_pf_accuracy"], "learning_rate": row["learning_rate"]})
                else: histories.extend(read_csv(run_dir(fraction, objective, seed) / "history.csv"))
    d2.write_csv(OUT / "p5d3_training_histories.csv", histories, HISTORY_FIELDS); d2.write_csv(OUT / "p5d3_validation_metrics.csv", metrics, list(metrics[0])); d2.write_csv(OUT / "p5d3_validation_by_signer.csv", signer_rows, list(signer_rows[0])); d2.write_csv(OUT / "p5d3_signer_balanced_metrics.csv", [{key: row[key] for key in ("fraction", "objective", "seed", "clip_top1", "signer_balanced_top1")} for row in metrics], ["fraction", "objective", "seed", "clip_top1", "signer_balanced_top1"]); d2.write_csv(OUT / "p5d3_temporal_failure_taxonomy.csv", taxonomy, list(taxonomy[0]))
    delta_rows = []
    metric_names = ("clip_top1", "signer_balanced_top1", "macro_f1", "clip_top5", "validation_clip_nll")
    for objective in OBJECTIVES:
        for seed in SEEDS:
            points = {fraction: next(row for row in metrics if row["fraction"] == fraction and row["objective"] == objective and row["seed"] == seed) for fraction in FRACTIONS}
            for start, end in ((50, 75), (75, 100), (50, 100)):
                delta_rows.append({"row_type": "SEED", "objective": objective, "seed": seed, "transition": f"{start}_TO_{end}", **{f"{name}_delta": points[end][name] - points[start][name] for name in metric_names}})
    for objective in OBJECTIVES:
        for transition in ("50_TO_75", "75_TO_100", "50_TO_100"):
            chosen = [row for row in delta_rows if row["objective"] == objective and row["transition"] == transition]
            for statistic, function in (("mean", np.mean), ("median", np.median), ("min", np.min), ("max", np.max), ("std", np.std)):
                delta_rows.append({"row_type": "SUMMARY", "objective": objective, "seed": statistic, "transition": transition, **{f"{name}_delta": float(function([row[f"{name}_delta"] for row in chosen])) for name in metric_names}})
    d2.write_csv(OUT / "p5d3_learning_curve_deltas.csv", delta_rows, list(delta_rows[0]))
    interaction = []
    for fraction in FRACTIONS:
        for seed in SEEDS:
            pf = next(row for row in metrics if row["fraction"] == fraction and row["objective"] == "PFCE_MATCHED" and row["seed"] == seed); clip = next(row for row in metrics if row["fraction"] == fraction and row["objective"] == "CLIPCE_AGGREGATION_ALIGNED" and row["seed"] == seed); pf_errors = [row for row in taxonomy if row["fraction"] == fraction and row["objective"] == "PFCE_MATCHED" and row["seed"] == seed]; cl_errors = [row for row in taxonomy if row["fraction"] == fraction and row["objective"] == "CLIPCE_AGGREGATION_ALIGNED" and row["seed"] == seed]; interaction.append({"fraction": fraction, "seed": seed, "top1_clipce_minus_pfce": clip["clip_top1"] - pf["clip_top1"], "signer_balanced_top1_clipce_minus_pfce": clip["signer_balanced_top1"] - pf["signer_balanced_top1"], "macro_f1_clipce_minus_pfce": clip["macro_f1"] - pf["macro_f1"], "persistent_error_fraction_clipce_minus_pfce": (sum(row["category"] == "PERSISTENT_WRONG_CLASS" for row in cl_errors) / max(len(cl_errors), 1)) - (sum(row["category"] == "PERSISTENT_WRONG_CLASS" for row in pf_errors) / max(len(pf_errors), 1))})
    d2.write_csv(OUT / "p5d3_objective_data_interaction.csv", interaction, list(interaction[0]))
    uncertainty = []
    for objective in OBJECTIVES:
        for seed in SEEDS: uncertainty.extend(bootstrap_75_100(arrays[(75, objective, seed)], arrays[(100, objective, seed)], objective, seed))
    d2.write_csv(OUT / "p5d3_signer_blocked_uncertainty.csv", uncertainty, list(uncertainty[0]))
    full_counts = np.asarray([profile_lookup[(100, class_id)]["clips"] for class_id in range(d2.CLASSES)]); order = np.argsort(full_counts, kind="stable"); quartile = {int(class_id): int(rank * 4 // d2.CLASSES) + 1 for rank, class_id in enumerate(order)}; coverage_response = []
    for objective in OBJECTIVES:
        for seed in SEEDS:
            for start, end in ((50, 75), (75, 100)):
                for class_id in range(d2.CLASSES):
                    support, recall_start = per_class[(start, objective, seed)][class_id]; _, recall_end = per_class[(end, objective, seed)][class_id]; a = profile_lookup[(start, class_id)]; b = profile_lookup[(end, class_id)]; coverage_response.append({"row_type": "CLASS", "objective": objective, "seed": seed, "transition": f"{start}_TO_{end}", "support_quartile": quartile[class_id], "class_id": class_id, "validation_support": support, "clips_added": b["clips"] - a["clips"], "unique_signers_added": b["unique_signers"] - a["unique_signers"], "effective_signer_count_delta": b["effective_signer_count"] - a["effective_signer_count"], "validation_recall_start": recall_start, "validation_recall_end": recall_end, "validation_recall_delta": recall_end - recall_start})
    for objective in OBJECTIVES:
        for transition in ("50_TO_75", "75_TO_100"):
            for q in range(1, 5):
                chosen = [row for row in coverage_response if row["objective"] == objective and row["transition"] == transition and row["support_quartile"] == q]
                coverage_response.append({"row_type": "QUARTILE_SUMMARY", "objective": objective, "seed": "ALL", "transition": transition, "support_quartile": q, "class_id": "", "validation_support": sum(row["validation_support"] for row in chosen), "clips_added": float(np.mean([row["clips_added"] for row in chosen])), "unique_signers_added": float(np.mean([row["unique_signers_added"] for row in chosen])), "effective_signer_count_delta": float(np.mean([row["effective_signer_count_delta"] for row in chosen])), "validation_recall_start": float(np.nanmean([row["validation_recall_start"] for row in chosen])), "validation_recall_end": float(np.nanmean([row["validation_recall_end"] for row in chosen])), "validation_recall_delta": float(np.nanmean([row["validation_recall_delta"] for row in chosen]))})
    d2.write_csv(OUT / "p5d3_coverage_response_summary.csv", coverage_response, list(coverage_response[0]))
    median_curve = {objective: {fraction: {name: float(np.median([row[name] for row in metrics if row["objective"] == objective and row["fraction"] == fraction])) for name in ("clip_top1", "signer_balanced_top1", "macro_f1")} for fraction in FRACTIONS} for objective in OBJECTIVES}
    scaling = {}; instability = {}
    for objective in OBJECTIVES:
        near = [row for row in delta_rows if row["row_type"] == "SEED" and row["objective"] == objective and row["transition"] == "75_TO_100"]; top = [row["clip_top1_delta"] for row in near]; macro = [row["macro_f1_delta"] for row in near]; signer_deltas = [row["signer_balanced_top1_delta"] for row in near]; sd100 = float(np.std([row["clip_top1"] for row in metrics if row["objective"] == objective and row["fraction"] == 100])); signer_seed = []
        for seed in SEEDS:
            for signer_id in sorted(set(row["signer_group_id"] for row in signer_rows if row["objective"] == objective and row["seed"] == seed)):
                a = next(row for row in signer_rows if row["fraction"] == 75 and row["objective"] == objective and row["seed"] == seed and row["signer_group_id"] == signer_id); b = next(row for row in signer_rows if row["fraction"] == 100 and row["objective"] == objective and row["seed"] == seed and row["signer_group_id"] == signer_id); signer_seed.append((seed, b["top1"] - a["top1"]))
        no_major = float(np.median([value for _, value in signer_seed])) >= 0 and all(np.mean([value < 0 for current, value in signer_seed if current == seed]) <= 0.60 for seed in SEEDS)
        scaling[objective] = bool(median_curve[objective][50]["clip_top1"] < median_curve[objective][75]["clip_top1"] < median_curve[objective][100]["clip_top1"] and sum(value > 0 for value in top) >= 2 and sum(value > 0 for value in macro) >= 2 and float(np.median(signer_deltas)) > 0 and float(np.median(top)) >= sd100 and no_major)
        instability[objective] = bool(min(top) < 0 < max(top) and (max(top) - min(top)) > max(0.10, 4 * sd100))
    if all(scaling.values()): classification = "CURRENT_DATA_COVERAGE_LIMITATION_SUPPORTED_BROADLY"; confidence = "HIGH"; next_gate = "EXTERNAL_DATA_COVERAGE_AND_COMPATIBILITY_AUDIT"
    elif sum(scaling.values()) == 1: classification = "DATA_COVERAGE_OBJECTIVE_INTERACTION"; confidence = "MODERATE"; next_gate = "EXTERNAL_DATA_COVERAGE_AND_COMPATIBILITY_AUDIT"
    elif any(instability.values()): classification = "DATA_CURVE_MIXED_OR_INCONCLUSIVE"; confidence = "LOW"; next_gate = "DATA_PREPARATION_AND_VARIANT_QUALITY_AUDIT"
    else: classification = "CURRENT_DATA_DISTRIBUTION_NEAR_PLATEAU"; confidence = "MODERATE"; next_gate = "DATA_PREPARATION_AND_VARIANT_QUALITY_AUDIT"
    decision = {"classification": classification, "confidence": confidence, "next_gate": next_gate, "objective_scaling_rule_passed": scaling, "severe_instability": instability, "median_curve": median_curve, "what_this_establishes": "Whether validation performance remains systematically unsaturated from 75% to 100% of the current signer-first training distribution.", "what_this_does_not_establish": "It does not prove behavior beyond 100%, external-data compatibility, data quality, or that more data will fix AppHear.", "next_gate_executed": False}
    d2.atomic_json(OUT / "p5d3_decision.json", decision); d2.atomic_json(OUT / "p5d3_next_gate.json", {"selected_next_gate": next_gate, "executed": False, "external_data": "DEFERRED_NOT_REJECTED"})
    integrity_path = OUT / "p5d3_integrity.json"; integrity = json.loads(integrity_path.read_text(encoding="utf-8")); context_now = d2.context_hashes(); reuse_now = d2_reuse_integrity(); states = [json.loads((run_dir(fraction, objective, seed) / "run_state.json").read_text(encoding="utf-8")) for fraction in NEW_FRACTIONS for objective in OBJECTIVES for seed in SEEDS]; integrity.update({"passed": integrity["passed"] and d2.source_hashes() == d2.EXPECTED_HASHES and reuse_now["passed"] and context_now == integrity["context_hashes_at_freeze"] and all(state["completed_updates"] == UPDATES and state["optimizer_iterations"] == UPDATES and state["validation_opportunities"] == VALIDATION_OPPORTUNITIES for state in states), "source_hashes_after_training": d2.source_hashes(), "d2_reuse_after_training": reuse_now, "new_runs_complete": len(states), "training_performed": True, "protected_test_accessed": False, "external_data_used": False, "context_files_modified": context_now != integrity["context_hashes_at_freeze"], "progress_tracker_untouched": context_now == integrity["context_hashes_at_freeze"]}); d2.atomic_json(integrity_path, integrity)
    result = f"""# P5-D3 Data Coverage Result\n\nIntegrity: {'PASS' if integrity['passed'] else 'FAIL'}\n\n- Classification: `{classification}`\n- Confidence: `{confidence}`\n- Next gate: `{next_gate}` (not executed)\n- Actual nested counts: 50%={len(subset_indices(membership, 50))}, 75%={len(subset_indices(membership, 75))}, 100%={len(subset_indices(membership, 100))}\n- PFCE median Top1: {median_curve['PFCE_MATCHED']}\n- CLIPCE median Top1: {median_curve['CLIPCE_AGGREGATION_ALIGNED']}\n\nThis downsampling curve measures only current-distribution coverage. It does not extrapolate performance beyond 100%. No protected test, external data, new recordings, representation/model changes, or context modifications occurred.\n"""; d2.atomic_text(OUT / "P5D3_DATA_COVERAGE_RESULT.md", result)
    artifacts = [{"path": str(path.resolve()), "sha256": d2.sha256(path), "bytes": path.stat().st_size} for path in sorted(OUT.rglob("*")) if path.is_file() and path.name != "artifact_hash_manifest.json"]
    d2.atomic_json(OUT / "artifact_hash_manifest.json", {"artifacts": artifacts, "supporting_code": [{"path": str(Path(__file__).resolve()), "sha256": d2.sha256(Path(__file__).resolve())}, {"path": str(Path(d2.__file__).resolve()), "sha256": d2.sha256(Path(d2.__file__).resolve())}], "protected_test_accessed": False})
    print(json.dumps({"status": "APPHEAR_P5D3_DATA_COVERAGE_LEARNING_CURVE_COMPLETE", "decision": decision, "integrity": integrity}, indent=2)); return 0 if integrity["passed"] else 2


def main() -> int:
    parser = argparse.ArgumentParser(); commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare"); commands.add_parser("unit-tests"); commands.add_parser("train-all"); commands.add_parser("finalize")
    single = commands.add_parser("train"); single.add_argument("--fraction", choices=NEW_FRACTIONS, type=int, required=True); single.add_argument("--objective", choices=OBJECTIVES, required=True); single.add_argument("--seed", choices=SEEDS, type=int, required=True); single.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare": return prepare()
    if args.command == "unit-tests": return unit_tests()
    if args.command == "train-all": return train_all()
    if args.command == "train": return train(args.fraction, args.objective, args.seed, args.resume)
    return finalize()


if __name__ == "__main__":
    raise SystemExit(main())
