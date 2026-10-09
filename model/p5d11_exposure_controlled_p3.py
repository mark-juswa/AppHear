"""P5-D11A exposure-controlled P3 schedule preparation and PFCE runner.

The only intervention is the precomputed sample schedule.  Each schedule
replays the exact D2 baseline class-label sequence while using a deterministic
signer-aware combined within-class pool for the 65 supplemented classes.
This module never references or opens the canonical test or D10B predictions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from model import p5d2_temporal_objective_ablation as d2
from model import p5d9_controlled_semlex_supplementation as d9


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/recognition_upgrade/p5_representation_v2"
OUT = BASE / "p5d11_exposure_controlled_p3_01"
D2 = BASE / "p5d2_temporal_objective_ablation_01"
D8 = BASE / "p5d8_supplementation_design_01"
D9 = BASE / "p5d9_semlex_supplementation_01"
V2 = BASE / "p5b_migration_01/dataset"
P3_MANIFEST = D8 / "p5d8_selected_policy_manifest.csv"
D9_MEMBERSHIP = D9 / "p5d9_derived_combined_membership.csv"
PROGRESS = ROOT / "context/progress-tracker.md"
SEEDS = (101, 202, 303)
UPDATES = 12_300
VALIDATE_EVERY = 123
BATCH = 32
EXPECTED_TRAIN_SHA = "a2261ea8d61e5eed1a526da0493da5b36c1bb54432ccef7f7479d6ca94634f11"
EXPECTED_VAL_SHA = "627275d03087f49fda65138253425131e35fe9c5cb8ded6a93b914484be5afe2"
EXPECTED_P3_SHA = "dda45f801806cd63a7ee6f59cbafe15650a402b59fb41a4f2a93a11acb6c8d08"
EXPECTED_PROGRESS_SHA = "12cf08f81959a413a60aa1f869615a24485a41ee3d796e61fce7489ae5c480cf"
EXPECTED_INITIALIZATIONS = {
    101: "56f482cb07e2829620282a7030ca689e8aa89de5e6e71d094921015dbb78716b",
    202: "ba80647335a498b6644d5d6cf46aa7ebb884bf64bc3c46c78f2170d551e1467b",
    303: "25f9aaaad795133876085917f7a894b436b57195a0e0d16eae789e22a6291724",
}
HISTORY_FIELDS = [
    "objective", "seed", "validation_opportunity", "optimizer_updates",
    "interval_train_objective_loss", "interval_train_clip_top1",
    "interval_train_pf_accuracy", "validation_clip_nll",
    "validation_clip_top1", "validation_pf_accuracy", "learning_rate",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tensor_hash(arrays: Iterable[np.ndarray]) -> str:
    digest = hashlib.sha256()
    for value in arrays:
        array = np.ascontiguousarray(value)
        digest.update(str(array.dtype).encode())
        digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
        digest.update(array.tobytes())
    return digest.hexdigest()


def string_hash(values: Iterable[str]) -> str:
    return hashlib.sha256("\n".join(map(str, values)).encode("utf-8")).hexdigest()


def stable_key(*parts: Any) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def write_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else ["status"]
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def initialization_tensor_hash(seed: int) -> str:
    path = D2 / "initializations" / f"seed_{seed}.weights.npz"
    with np.load(path, allow_pickle=False) as values:
        arrays = [np.asarray(values[key]) for key in sorted(values.files)]
    return d2.tensor_hash(arrays)


def verify_sources() -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], list[dict[str, str]], list[dict[str, str]]]:
    if sha256(V2 / "train.npz") != EXPECTED_TRAIN_SHA:
        raise RuntimeError("P5D11A_BLOCKED_TRAIN_HASH_MISMATCH")
    if sha256(V2 / "val.npz") != EXPECTED_VAL_SHA:
        raise RuntimeError("P5D11A_BLOCKED_VALIDATION_HASH_MISMATCH")
    if sha256(P3_MANIFEST) != EXPECTED_P3_SHA:
        raise RuntimeError("P5D11A_BLOCKED_P3_MANIFEST_MISMATCH")
    if sha256(PROGRESS) != EXPECTED_PROGRESS_SHA:
        raise RuntimeError("P5D11A_PROGRESS_TRACKER_PREHASH_MISMATCH")
    train = d2.load_split("train")
    val = d2.load_split("val")
    p3 = read_csv(P3_MANIFEST)
    membership = d9.read_membership()
    if len(train["y"]) != 3926 or len(val["y"]) != 816 or len(p3) != 881 or len(membership) != 4807:
        raise RuntimeError("P5D11A_SOURCE_COUNT_MISMATCH")
    p3_classes = {int(row["apphear_class_id"]) for row in p3}
    if len(p3_classes) != 65:
        raise RuntimeError("P5D11A_P3_CLASS_COUNT_MISMATCH")
    semlex_rows = [row for row in membership if row["source_dataset"] == "SEMLEX"]
    if len(semlex_rows) != 881 or {row["sample_id"] for row in semlex_rows} != {row["semlex_sample_id"] for row in p3}:
        raise RuntimeError("P5D11A_P3_MEMBERSHIP_LINEAGE_MISMATCH")
    apphear_rows = [row for row in membership if row["source_dataset"] == "APPHEAR"]
    if len(apphear_rows) != 3926:
        raise RuntimeError("P5D11A_APPHEAR_MEMBERSHIP_MISMATCH")
    for seed, expected in EXPECTED_INITIALIZATIONS.items():
        if initialization_tensor_hash(seed) != expected:
            raise RuntimeError(f"P5D11A_INITIALIZATION_MISMATCH:{seed}")
    if set(train["sample_ids"].astype(str)) & set(val["sample_ids"].astype(str)):
        raise RuntimeError("P5D11A_VALIDATION_SAMPLE_LEAKAGE")
    if set(train["signers"].astype(str)) & set(val["signers"].astype(str)):
        raise RuntimeError("P5D11A_VALIDATION_SIGNER_LEAKAGE")
    return train, val, p3, membership


def baseline_draws(seed: int, train: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    indices: list[np.ndarray] = []
    offsets = [0]
    updates = 0
    for epoch in range(100):
        order = d2.batch_permutation(seed, epoch, count=len(train["y"]))
        for start in range(0, len(order), BATCH):
            chosen = order[start:start + BATCH]
            indices.append(chosen.astype(np.int32))
            offsets.append(offsets[-1] + len(chosen))
            updates += 1
    if updates != UPDATES:
        raise RuntimeError(f"P5D11A_BASELINE_UPDATE_COUNT_MISMATCH:{updates}")
    sequence = np.concatenate(indices)
    return sequence, train["y"][sequence].astype(np.int16), np.asarray(offsets, dtype=np.int32)


def signer_aware_cycle(class_indices: list[int], membership: list[dict[str, str]], seed: int, class_id: int, cycle: int) -> list[int]:
    groups: dict[str, list[int]] = defaultdict(list)
    for index in class_indices:
        groups[membership[index]["signer_group_id"]].append(index)
    signers = sorted(groups, key=lambda signer: stable_key("P5D11_EC_P3_V1", seed, class_id, cycle, "SIGNER", signer))
    ordered_groups: dict[str, list[int]] = {}
    for signer in signers:
        ordered_groups[signer] = sorted(
            groups[signer],
            key=lambda index: stable_key("P5D11_EC_P3_V1", seed, class_id, cycle, "SAMPLE", membership[index]["sample_id"]),
        )
    result: list[int] = []
    for round_index in range(max(len(values) for values in ordered_groups.values())):
        for signer in signers:
            if round_index < len(ordered_groups[signer]):
                result.append(ordered_groups[signer][round_index])
    if len(result) != len(class_indices) or len(set(result)) != len(result):
        raise RuntimeError("P5D11A_SIGNER_AWARE_CYCLE_FAILURE")
    return result


def schedule_for_seed(seed: int, train: dict[str, np.ndarray], membership: list[dict[str, str]], supplemented: set[int]) -> dict[str, np.ndarray]:
    baseline_indices, class_ids, offsets = baseline_draws(seed, train)
    apphear_index = {int(row["feature_row_index"]): index for index, row in enumerate(membership) if row["source_dataset"] == "APPHEAR"}
    if len(apphear_index) != 3926:
        raise RuntimeError("P5D11A_APPHEAR_INDEX_MAPPING_FAILURE")
    class_pools: dict[int, list[int]] = defaultdict(list)
    for index, row in enumerate(membership):
        class_pools[int(row["class_id"])].append(index)
    candidate_indices = np.empty(len(class_ids), dtype=np.int32)
    positions = Counter()
    cycle_cache: dict[tuple[int, int], list[int]] = {}
    for draw_index, (baseline_index, class_id_value) in enumerate(zip(baseline_indices, class_ids)):
        class_id = int(class_id_value)
        if class_id not in supplemented:
            candidate_indices[draw_index] = apphear_index[int(baseline_index)]
            continue
        position = positions[class_id]
        pool = class_pools[class_id]
        cycle, within = divmod(position, len(pool))
        key = (class_id, cycle)
        if key not in cycle_cache:
            cycle_cache[key] = signer_aware_cycle(pool, membership, seed, class_id, cycle)
        candidate_indices[draw_index] = cycle_cache[key][within]
        positions[class_id] += 1
    source_codes = np.asarray([0 if membership[index]["source_dataset"] == "APPHEAR" else 1 for index in candidate_indices], dtype=np.int8)
    sample_ids = np.asarray([membership[index]["sample_id"] for index in candidate_indices], dtype="U128")
    signer_ids = np.asarray([membership[index]["signer_group_id"] for index in candidate_indices], dtype="U128")
    if not np.array_equal(np.asarray([int(membership[index]["class_id"]) for index in candidate_indices], dtype=np.int16), class_ids):
        raise RuntimeError("P5D11A_CLASS_SCHEDULE_PARITY_FAILURE")
    return {
        "class_ids": class_ids,
        "candidate_indices": candidate_indices,
        "source_codes": source_codes,
        "sample_ids": sample_ids,
        "signer_ids": signer_ids,
        "update_offsets": offsets,
    }


def component_hashes(schedule: dict[str, np.ndarray]) -> dict[str, str]:
    return {
        "class_draw_sequence_sha256": tensor_hash([schedule["class_ids"]]),
        "candidate_index_sequence_sha256": tensor_hash([schedule["candidate_indices"]]),
        "sample_identity_sequence_sha256": string_hash(schedule["sample_ids"].tolist()),
        "source_sequence_sha256": tensor_hash([schedule["source_codes"]]),
        "signer_identity_sequence_sha256": string_hash(schedule["signer_ids"].tolist()),
        "update_offsets_sha256": tensor_hash([schedule["update_offsets"]]),
    }


def save_or_verify_schedule(seed: int, schedule: dict[str, np.ndarray]) -> tuple[Path, dict[str, Any]]:
    path = OUT / "schedules" / f"seed_{seed}_schedule.npz"
    hashes = component_hashes(schedule)
    if path.exists():
        with np.load(path, allow_pickle=False) as existing:
            existing_schedule = {key: existing[key] for key in existing.files}
        if component_hashes(existing_schedule) != hashes:
            raise RuntimeError(f"P5D11A_FROZEN_SCHEDULE_MISMATCH:{seed}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **schedule)
    record = {
        "seed": seed, "schedule_path": str(path.resolve()), "schedule_file_sha256": sha256(path),
        **hashes, "total_draws": len(schedule["class_ids"]), "updates": len(schedule["update_offsets"]) - 1,
        "frozen": True,
    }
    write_json(OUT / f"p5d11_seed{seed}_schedule_hash.json", record)
    return path, record


def load_schedule(seed: int) -> dict[str, np.ndarray]:
    path = OUT / "schedules" / f"seed_{seed}_schedule.npz"
    with np.load(path, allow_pickle=False) as values:
        schedule = {key: values[key] for key in values.files}
    record = json.loads((OUT / f"p5d11_seed{seed}_schedule_hash.json").read_text(encoding="utf-8"))
    if sha256(path) != record["schedule_file_sha256"] or component_hashes(schedule) != {key: record[key] for key in component_hashes(schedule)}:
        raise RuntimeError(f"P5D11_FROZEN_SCHEDULE_HASH_FAILURE:{seed}")
    return schedule


def schedule_diagnostics(seed: int, schedule: dict[str, np.ndarray], train: dict[str, np.ndarray], membership: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    baseline_counts = Counter(map(int, train["y"]))
    scheduled_counts = Counter(map(int, schedule["class_ids"]))
    class_rows: list[dict[str, Any]] = []
    for class_id in range(236):
        chosen = schedule["class_ids"] == class_id
        source = schedule["source_codes"][chosen]
        expected = baseline_counts[class_id] * 100
        actual = scheduled_counts[class_id]
        class_rows.append({
            "seed": seed, "class_id": class_id, "baseline_train_clips": baseline_counts[class_id],
            "baseline_expected_draws": expected, "ec_p3_draws": actual,
            "absolute_class_draw_difference": abs(actual - expected),
            "relative_class_draw_difference": abs(actual - expected) / expected if expected else 0.0,
            "apphear_draws": int(np.sum(source == 0)), "semlex_draws": int(np.sum(source == 1)),
            "unique_apphear_samples_used": len(set(schedule["sample_ids"][chosen & (schedule["source_codes"] == 0)].tolist())),
            "unique_semlex_samples_used": len(set(schedule["sample_ids"][chosen & (schedule["source_codes"] == 1)].tolist())),
            "unique_semlex_signer_class_slots_used": len(set(schedule["signer_ids"][chosen & (schedule["source_codes"] == 1)].tolist())),
        })
    semlex_members = [row for row in membership if row["source_dataset"] == "SEMLEX"]
    scheduled_semlex = set(schedule["sample_ids"][schedule["source_codes"] == 1].tolist())
    slot_rows = [{
        "seed": seed, "class_id": int(row["class_id"]), "sample_id": row["sample_id"],
        "signer_group_id": row["signer_group_id"], "scheduled": row["sample_id"] in scheduled_semlex,
        "draws": int(np.sum(schedule["sample_ids"] == row["sample_id"])),
    } for row in semlex_members]
    summary = {
        "seed": seed, "total_draws": len(schedule["class_ids"]), "updates": len(schedule["update_offsets"]) - 1,
        "baseline_expected_draws": len(train["y"]) * 100,
        "maximum_absolute_per_class_exposure_deviation": max(row["absolute_class_draw_difference"] for row in class_rows),
        "maximum_relative_per_class_exposure_deviation": max(row["relative_class_draw_difference"] for row in class_rows),
        "unique_apphear_samples_used": len(set(schedule["sample_ids"][schedule["source_codes"] == 0].tolist())),
        "unique_semlex_samples_used": len(scheduled_semlex),
        "semlex_signer_class_slots_available": len(semlex_members),
        "semlex_signer_class_slots_scheduled": sum(row["scheduled"] for row in slot_rows),
        "semlex_draws": int(np.sum(schedule["source_codes"] == 1)),
    }
    return class_rows, summary, slot_rows


def load_batch(rows: list[dict[str, str]], candidate_indices: np.ndarray, apphear: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = np.empty((len(candidate_indices), 96, 238), dtype=np.float32)
    y = np.empty(len(candidate_indices), dtype=np.int32)
    mask = np.empty((len(candidate_indices), 96), dtype=bool)
    for destination, candidate_index in enumerate(candidate_indices):
        row = rows[int(candidate_index)]
        if row["source_dataset"] == "APPHEAR":
            source = int(row["feature_row_index"])
            x[destination] = apphear["X"][source]
            y[destination] = apphear["y"][source]
            mask[destination] = apphear["frame_mask"][source]
        elif row["source_dataset"] == "SEMLEX":
            with np.load(Path(row["feature_path"]), allow_pickle=False) as values:
                x[destination] = np.asarray(values["features"], dtype=np.float32)
                y[destination] = int(np.asarray(values["class_id"]).reshape(()))
                mask[destination] = np.asarray(values["frame_mask"], dtype=bool)
        else:
            raise RuntimeError("P5D11_UNKNOWN_SOURCE")
        if int(row["class_id"]) != int(y[destination]):
            raise RuntimeError("P5D11_BATCH_CLASS_LINEAGE_MISMATCH")
    if not np.isfinite(x).all() or np.count_nonzero(x[~mask]) != 0:
        raise RuntimeError("P5D11_BATCH_TENSOR_INTEGRITY_FAILURE")
    return x, y, mask


def run_smoke(train: dict[str, np.ndarray], membership: list[dict[str, str]]) -> dict[str, Any]:
    import tensorflow as tf

    seed = 101
    schedule = load_schedule(seed)
    model = d2.make_model(seed)
    initial_hash = d2.load_initialization(model, seed)
    if initial_hash != EXPECTED_INITIALIZATIONS[seed]:
        raise RuntimeError("P5D11A_SMOKE_INITIALIZATION_MISMATCH")
    optimizer = tf.keras.optimizers.AdamW(learning_rate=5e-4, weight_decay=1e-4)
    optimizer.build(model.trainable_variables)
    before = d2.tensor_hash([np.asarray(value) for value in model.get_weights()])
    losses: list[float] = []
    gradients_finite = True
    gradients_nonzero = False
    sources_seen: set[int] = set()
    for update in range(10):
        start, stop = int(schedule["update_offsets"][update]), int(schedule["update_offsets"][update + 1])
        chosen = schedule["candidate_indices"][start:stop]
        sources_seen.update(map(int, schedule["source_codes"][start:stop]))
        x, y, mask = load_batch(membership, chosen, train)
        with tf.GradientTape() as tape:
            probabilities = model(tf.convert_to_tensor(x), training=True)
            numerator, denominator = d2.objective_components("PFCE_MATCHED", probabilities, tf.convert_to_tensor(y), tf.convert_to_tensor(mask))
            loss = numerator / denominator
        gradients = tape.gradient(loss, model.trainable_variables)
        gradients_finite = gradients_finite and all(bool(tf.reduce_all(tf.math.is_finite(value))) for value in gradients if value is not None)
        gradients_nonzero = gradients_nonzero or any(bool(tf.reduce_any(value != 0)) for value in gradients if value is not None)
        optimizer.apply_gradients(zip(gradients, model.trainable_variables))
        losses.append(float(loss.numpy()))
    after = d2.tensor_hash([np.asarray(value) for value in model.get_weights()])
    result = {
        "passed": bool(int(optimizer.iterations.numpy()) == 10 and all(np.isfinite(losses)) and gradients_finite and gradients_nonzero and before != after and sources_seen == {0, 1}),
        "seed": seed, "optimizer_updates": int(optimizer.iterations.numpy()), "maximum_updates_authorized": 10,
        "initialization_tensor_sha256": initial_hash, "initialization_exact": initial_hash == EXPECTED_INITIALIZATIONS[seed],
        "losses_finite": bool(all(np.isfinite(losses))), "gradients_finite": gradients_finite,
        "gradients_nonzero": gradients_nonzero, "weights_updated": before != after,
        "apphear_and_semlex_loaded": sources_seen == {0, 1}, "validation_leakage": False,
        "test_accessed": False, "scientific_evidence": False, "full_training_executed": False,
        "losses": losses,
    }
    tf.keras.backend.clear_session()
    return result


def prepare_schedules() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    train, val, p3, membership = verify_sources()
    selected_classes = {int(row["apphear_class_id"]) for row in p3}
    write_csv(OUT / "p5d11_combined_candidate_membership.csv", membership)
    vocab = json.loads((V2 / "vocab.json").read_text(encoding="utf-8"))
    inverse = {int(value): key for key, value in vocab.items()}
    baseline_counts = Counter(map(int, train["y"]))
    baseline_rows = [{
        "class_id": class_id, "gloss": inverse[class_id], "apphear_train_clips": baseline_counts[class_id],
        "baseline_class_prior": baseline_counts[class_id] / len(train["y"]),
        "supplemented_status": class_id in selected_classes,
    } for class_id in range(236)]
    write_csv(OUT / "p5d11_baseline_class_distribution.csv", baseline_rows)

    all_class_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    all_slot_rows: list[dict[str, Any]] = []
    schedule_records: list[dict[str, Any]] = []
    for seed in SEEDS:
        schedule = schedule_for_seed(seed, train, membership, selected_classes)
        _, record = save_or_verify_schedule(seed, schedule)
        schedule_records.append(record)
        class_rows, summary, slot_rows = schedule_diagnostics(seed, schedule, train, membership)
        all_class_rows.extend(class_rows); summaries.append(summary); all_slot_rows.extend(slot_rows)
    write_csv(OUT / "p5d11_class_exposure_parity.csv", all_class_rows)
    write_csv(OUT / "p5d11_seed_schedule_summary.csv", summaries)
    write_csv(OUT / "p5d11_semlex_slot_schedule_coverage.csv", all_slot_rows)

    if any(summary["maximum_absolute_per_class_exposure_deviation"] != 0 for summary in summaries):
        raise RuntimeError("P5D11A_EXPOSURE_PARITY_NOT_RESOLVED")
    if any(summary["semlex_signer_class_slots_scheduled"] != 881 for summary in summaries):
        write_json(OUT / "p5d11a_decision.json", {"classification": "P5D11A_SIGNER_SLOT_EXPOSURE_LIMITATION"})
        raise RuntimeError("P5D11A_SIGNER_SLOT_EXPOSURE_LIMITATION")

    schedule_contract = {
        "implementation": "EXACT_BASELINE_CLASS_SCHEDULE_REPLAY",
        "baseline_sampler": "D2 PCG64 SeedSequence([seed, epoch, 0xD2]) permutation; 100 complete 3926-row passes",
        "total_draws_per_seed": 392600, "updates": UPDATES, "batch_size": BATCH,
        "partial_batch": "final batch of each 123-update pass has 22 draws",
        "class_label_parity": "exact finite-run equality with baseline schedule",
        "unsupplemented_sampling": "exact baseline AppHear sample identity replay",
        "supplemented_sampling": "deterministic source-neutral signer-aware round-robin cycles over frozen combined class pool",
        "stable_key": "SHA256(P5D11_EC_P3_V1|seed|class_id|cycle|role|stable_identity)",
        "no_forced_source_ratio": True, "schedule_records": schedule_records,
        "frozen_before_full_training": True,
    }
    write_json(OUT / "p5d11_schedule_contract.json", schedule_contract)
    training_contract = {
        "objective": "PFCE_MATCHED", "representation": "DWPOSE_REPRESENTATION_V2_238", "input_shape": [96, 238],
        "model": "4x64 causal TCN", "dilations": [1, 2, 4, 8], "kernel": 3, "dropout": 0.3,
        "parameters": 163884, "optimizer": "AdamW", "learning_rate": 0.0005, "weight_decay": 0.0001,
        "batch_size": BATCH, "optimizer_updates": UPDATES, "validation_every_updates": VALIDATE_EVERY,
        "validation_opportunities": 100, "checkpoint_rule": "strict minimum primary-validation clip NLL; earliest tie retained",
        "seeds": list(SEEDS), "initializations": {str(seed): EXPECTED_INITIALIZATIONS[seed] for seed in SEEDS},
        "augmentation": "NONE", "warm_start": "NONE", "class_weights": "NONE", "full_runs": 3,
    }
    write_json(OUT / "p5d11_training_contract.json", training_contract)
    evaluation_contract = {
        "population": "governed primary validation", "clips": 816, "classes": 236,
        "tensor_sha256": EXPECTED_VAL_SHA, "test_access_prohibited": True,
        "primary_endpoint": "SIGNER_BALANCED_TOP1", "primary_comparison": "EC_P3_MINUS_BASELINE",
        "diagnostic_comparison": "EC_P3_MINUS_NAIVE_P3",
        "metrics": ["signer_balanced_top1", "ordinary_top1", "macro_f1", "top5", "clip_nll", "per_frame_accuracy"],
        "slices": ["P3_SUPPLEMENTED_65", "UNSUPPLEMENTED_171", "BY_SIGNER", "CONFUSION_INTO_SUPPLEMENTED_LABELS"],
    }
    write_json(OUT / "p5d11_evaluation_contract.json", evaluation_contract)
    outcome_contract = {
        "status": "FROZEN_BEFORE_FULL_TRAINING", "primary_endpoint": "SIGNER_BALANCED_TOP1",
        "primary_comparison": "EC_P3_MINUS_BASELINE", "diagnostic_comparison": "EC_P3_MINUS_NAIVE_P3",
        "rules": {
            "EXPOSURE_CONTROL_BROAD_BENEFIT_SUPPORTED": "median signer-balanced >0; >=2/3 positive; median ordinary >=0; median MacroF1 >=0; supplemented-65 >0; unsupplemented-171 >=0",
            "EXPOSURE_CONTROL_PARTIAL_RECOVERY": "supplemented-65 >0; unsupplemented-171 <0 versus baseline; but unsupplemented improves versus naive P3 and/or full vocabulary improves versus naive P3",
            "INTERFERENCE_PERSISTS_WITH_CLASS_EXPOSURE_CONTROLLED": "supplemented-65 >0; unsupplemented-171 <0; no coherent recovery versus naive P3",
            "SIGNER_DIVERSITY_GAIN_NOT_RETAINED_UNDER_EXPOSURE_CONTROL": "supplemented-65 median Top1 <=0 versus baseline",
            "EXPOSURE_CONTROL_EFFECT_MIXED": "seed or metric/slice directions do not permit another coherent classification",
        },
        "post_hoc_effect_thresholds": "PROHIBITED", "test_metrics": "PROHIBITED",
    }
    outcome_path = OUT / "p5d11_preregistered_outcome_contract.json"
    if outcome_path.exists():
        old = sha256(outcome_path)
        write_json(outcome_path, outcome_contract)
        if sha256(outcome_path) != old:
            raise RuntimeError("P5D11_OUTCOME_CONTRACT_WAS_ALREADY_FROZEN_DIFFERENTLY")
    else:
        write_json(outcome_path, outcome_contract)

    post_contract = {
        "stage": "P5D11B_EXPOSURE_CONTROLLED_RESULT_AUDIT", "executed": False,
        "inputs": {"ec_p3_runs": 3, "comparators_reused": ["PFCE_BASELINE", "PFCE_NAIVE_P3"], "validation_only": True},
        "required_metrics": evaluation_contract["metrics"], "required_slices": evaluation_contract["slices"],
        "outcome_contract_sha256": sha256(outcome_path), "test_access": "PROHIBITED",
    }
    write_json(OUT / "p5d11b_post_training_audit_contract.json", post_contract)
    smoke = run_smoke(train, membership)
    write_json(OUT / "p5d11_smoke_result.json", smoke)
    if not smoke["passed"]:
        write_json(OUT / "p5d11a_decision.json", {"classification": "P5D11A_SMOKE_FAILURE"})
        raise RuntimeError("P5D11A_SMOKE_FAILURE")

    elapsed = []
    for seed in SEEDS:
        state = json.loads((D9 / "runs/PFCE_MATCHED" / f"seed_{seed}" / "run_state.json").read_text(encoding="utf-8"))
        elapsed.append(float(state["elapsed_seconds"]))
    median_seconds = float(np.median(elapsed))
    commands = [f"& '.\\.venv\\Scripts\\python.exe' -m model.p5d11_exposure_controlled_p3 --seed {seed} --run" for seed in SEEDS]
    sequential = "; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; ".join(commands)
    guide = f"""# Run P5-D11 EC_P3 Full Training

Working directory: `{ROOT}`

Run sequentially, not in parallel. Each completed seed is skip-safe. If a seed is interrupted, rerun that seed with `--restart-incomplete` to archive the incomplete directory and restart only that seed.

## Seed 101

```powershell
{commands[0]}
```

## Seed 202

```powershell
{commands[1]}
```

## Seed 303

```powershell
{commands[2]}
```

## Sequential launcher

```powershell
{sequential}
```

## Verify completion

```powershell
& '.\\.venv\\Scripts\\python.exe' -m model.p5d11_verify_full_training
```

Expected: three PFCE runs, 12,300 updates and 100 validation opportunities each. Estimated sequential runtime: {median_seconds * 3 / 60:.0f}-{median_seconds * 3 * 1.35 / 60:.0f} minutes based on the governed D9 PFCE runs. Do not access the test population or start D11B automatically.
"""
    atomic_text(OUT / "RUN_P5D11_EXPOSURE_CONTROLLED.md", guide)
    decision = {"classification": "P5D11A_EXPOSURE_CONTROLLED_TRAINING_READY", "confidence": "HIGH", "full_training_executed": False, "next_gate": "PROJECT_LEAD_RUNS_THREE_EC_P3_PFCE_RUNS"}
    write_json(OUT / "p5d11a_decision.json", decision)
    write_json(OUT / "p5d11a_next_gate.json", {"next_gate": decision["next_gate"], "executed": False})

    supplemented_draws = sum(row["baseline_expected_draws"] for row in all_class_rows[:236] if int(row["class_id"]) in selected_classes)
    share = supplemented_draws / summaries[0]["total_draws"]
    report = f"""# P5-D11A Exposure-Controlled P3 Preparation

`P5D11A_EXPOSURE_CONTROLLED_TRAINING_READY`.

The exact D2 baseline class-label schedule was reconstructed for seeds 101/202/303: 12,300 updates and 392,600 actual draws per seed, including 100 partial 22-sample batches. EC_P3 has zero per-class draw deviation and preserves the 65-class exposure share at {share:.4%}. Within the 65 classes, deterministic signer-aware combined-pool cycling schedules every one of the 881 frozen P3 signer-class rows at least once. No source ratio is forced.

The seed-101 bounded smoke passed exactly 10 PFCE updates with frozen initialization, finite loss/gradients, both AppHear and Sem-Lex tensors, and no validation or test leakage. No full run was executed. The preregistered outcome contract SHA is `{sha256(outcome_path)}`.
"""
    atomic_text(OUT / "P5D11A_EXPOSURE_CONTROL_PREPARATION_RESULT.md", report)

    d10b_files = [
        BASE / "p5d10b_secondary_confirmation_01/p5d10b_terminal_evidence.json",
        BASE / "p5d10b_secondary_confirmation_01/p5d10b_decision.json",
        BASE / "p5d10b_secondary_confirmation_01/P5D10B_SECONDARY_CONFIRMATION_RESULT.md",
    ]
    integrity = {
        "passed": sha256(PROGRESS) == EXPECTED_PROGRESS_SHA and smoke["passed"],
        "d10b_terminal_artifact_hashes": {str(path.resolve()): sha256(path) for path in d10b_files},
        "d10b_test_accessed": False, "d10b_predictions_loaded": False,
        "apphear_train_sha256": sha256(V2 / "train.npz"), "apphear_train_membership_changed": False,
        "p3_manifest_sha256": sha256(P3_MANIFEST), "p3_membership_changed": False,
        "semlex_clips": 881, "supplemented_classes": 65, "unsupplemented_classes": 171,
        "v2_changed": False, "dwpose_changed": False, "p4_reopened": False,
        "model_changed": False, "pfce_changed": False, "optimizer_changed": False,
        "update_count": UPDATES, "validation_sha256": sha256(V2 / "val.npz"),
        "initializations": {str(seed): initialization_tensor_hash(seed) for seed in SEEDS},
        "outcome_contract_sha256": sha256(outcome_path), "outcome_contract_frozen_before_full_training": True,
        "only_sampling_exposure_differs": True, "smoke_updates": 10, "full_training_executed": False,
        "progress_tracker_sha256": sha256(PROGRESS), "progress_tracker_untouched": True,
    }
    write_json(OUT / "p5d11a_integrity.json", integrity)
    generated = [path for path in OUT.rglob("*") if path.is_file() and path.name != "artifact_hash_manifest.json"]
    references = [V2 / "train.npz", V2 / "val.npz", P3_MANIFEST, D9_MEMBERSHIP] + [D2 / "initializations" / f"seed_{seed}.weights.npz" for seed in SEEDS] + d10b_files
    manifest = {
        "generated_files": [{"path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size} for path in sorted(generated)],
        "governed_references": [{"path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size} for path in references],
        "d10b_test_accessed": False, "full_training_executed": False,
    }
    write_json(OUT / "artifact_hash_manifest.json", manifest)
    print(json.dumps({"classification": decision["classification"], "draws_per_seed": summaries[0]["total_draws"], "maximum_class_deviation": 0, "slots_scheduled": summaries[0]["semlex_signer_class_slots_scheduled"], "smoke": smoke["passed"], "full_training": False}, indent=2))
    return 0


def append_history(path: Path, row: dict[str, Any]) -> None:
    new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HISTORY_FIELDS)
        if new:
            writer.writeheader()
        writer.writerow(row); handle.flush(); os.fsync(handle.fileno())


def run_directory(seed: int) -> Path:
    return OUT / "runs/EC_P3/PFCE_MATCHED" / f"seed_{seed}"


def completed(seed: int) -> bool:
    directory = run_directory(seed)
    state_path = directory / "run_state.json"
    if not state_path.is_file() or not (directory / "best.keras").is_file():
        return False
    state = json.loads(state_path.read_text(encoding="utf-8"))
    return bool(state.get("status") == "COMPLETE" and int(state.get("completed_updates", 0)) == UPDATES and int(state.get("validation_opportunities", 0)) == 100 and state.get("checkpoint_sha256") == sha256(directory / "best.keras"))


def run(seed: int, restart_incomplete: bool) -> int:
    import tensorflow as tf

    if seed not in SEEDS:
        raise RuntimeError("P5D11_RUN_MATRIX_VIOLATION")
    train, validation, _, membership = verify_sources()
    schedule = load_schedule(seed)
    if completed(seed):
        print(f"Verified completed EC_P3 PFCE seed {seed}; skipping")
        return 0
    directory = run_directory(seed)
    if directory.exists():
        if not restart_incomplete:
            raise RuntimeError("P5D11_INCOMPLETE_RUN_USE_--restart-incomplete")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = directory.with_name(directory.name + f".incomplete_{stamp}")
        shutil.move(str(directory), str(destination))
    directory.mkdir(parents=True)
    model = d2.make_model(seed)
    initialization_hash = d2.load_initialization(model, seed)
    if initialization_hash != EXPECTED_INITIALIZATIONS[seed]:
        raise RuntimeError("P5D11_INITIALIZATION_MISMATCH")
    optimizer = tf.keras.optimizers.AdamW(learning_rate=5e-4, weight_decay=1e-4)
    optimizer.build(model.trainable_variables)

    @tf.function(reduce_retracing=True)
    def step(x_batch: Any, y_batch: Any, mask_batch: Any) -> tuple[Any, Any, Any]:
        with tf.GradientTape() as tape:
            probabilities = model(x_batch, training=True)
            numerator, denominator = d2.objective_components("PFCE_MATCHED", probabilities, y_batch, mask_batch)
            loss = numerator / denominator
        gradients = tape.gradient(loss, model.trainable_variables)
        optimizer.apply_gradients(zip(gradients, model.trainable_variables))
        return numerator, denominator, probabilities

    contract = {
        "intervention": "EC_P3", "objective": "PFCE_MATCHED", "seed": seed,
        "schedule_sha256": sha256(OUT / "schedules" / f"seed_{seed}_schedule.npz"),
        "outcome_contract_sha256": sha256(OUT / "p5d11_preregistered_outcome_contract.json"),
        "initialization_tensor_sha256": initialization_hash, "updates": UPDATES,
        "validate_every": VALIDATE_EVERY, "checkpoint_rule": "strict minimum validation clip NLL; earliest tie retained",
        "test_access": "PROHIBITED",
    }
    write_json(directory / "run_contract.json", contract)
    started = time.perf_counter(); best_nll = float("inf"); selected_update = 0; opportunities = 0
    interval_num = interval_den = 0.0; interval_samples = interval_clip = interval_frames = interval_pf = 0
    for update in range(UPDATES):
        begin, end = int(schedule["update_offsets"][update]), int(schedule["update_offsets"][update + 1])
        chosen = schedule["candidate_indices"][begin:end]
        x, y, mask = load_batch(membership, chosen, train)
        numerator, denominator, probability_tensor = step(tf.convert_to_tensor(x), tf.convert_to_tensor(y), tf.convert_to_tensor(mask))
        common = d2.common_metrics(probability_tensor.numpy(), y, mask)
        interval_num += float(numerator); interval_den += float(denominator); interval_samples += len(y)
        interval_clip += int(round(common["clip_top1"] * len(y)))
        real = int(mask.sum()); interval_frames += real; interval_pf += int(round(common["pf_accuracy"] * real))
        if (update + 1) % VALIDATE_EVERY == 0:
            frame = d2.infer_probabilities(model, validation["X"])
            val = d2.common_metrics(frame, validation["y"], validation["frame_mask"])
            opportunities += 1
            if val["clip_nll"] < best_nll:
                best_nll = val["clip_nll"]; selected_update = update + 1
                d2.save_model_atomic(model, directory / "best.keras")
            append_history(directory / "history.csv", {
                "objective": "PFCE_MATCHED", "seed": seed, "validation_opportunity": opportunities,
                "optimizer_updates": update + 1, "interval_train_objective_loss": interval_num / max(interval_den, 1.0),
                "interval_train_clip_top1": interval_clip / max(interval_samples, 1),
                "interval_train_pf_accuracy": interval_pf / max(interval_frames, 1),
                "validation_clip_nll": val["clip_nll"], "validation_clip_top1": val["clip_top1"],
                "validation_pf_accuracy": val["pf_accuracy"], "learning_rate": float(tf.keras.backend.get_value(optimizer.learning_rate)),
            })
            state = {"intervention": "EC_P3", "objective": "PFCE_MATCHED", "seed": seed,
                     "completed_updates": update + 1, "validation_opportunities": opportunities,
                     "optimizer_iterations": int(optimizer.iterations.numpy()), "best_validation_clip_nll": best_nll,
                     "selected_optimizer_update": selected_update, "status": "RUNNING", "elapsed_seconds": time.perf_counter() - started}
            write_json(directory / "run_state.json", state); print(json.dumps(state), flush=True)
            interval_num = interval_den = 0.0; interval_samples = interval_clip = interval_frames = interval_pf = 0
    state.update({"status": "COMPLETE", "checkpoint_sha256": sha256(directory / "best.keras"),
                  "completed_updates": UPDATES, "validation_opportunities": 100,
                  "optimizer_iterations": int(optimizer.iterations.numpy()), "elapsed_seconds": time.perf_counter() - started})
    write_json(directory / "run_state.json", state)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-schedules", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--seed", type=int, choices=SEEDS)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--restart-incomplete", action="store_true")
    args = parser.parse_args()
    if args.prepare_schedules:
        return prepare_schedules()
    if args.smoke:
        train, _, _, membership = verify_sources(); result = run_smoke(train, membership)
        write_json(OUT / "p5d11_smoke_result.json", result); print(json.dumps(result, indent=2)); return 0 if result["passed"] else 1
    if args.run:
        if args.seed is None: parser.error("--run requires --seed")
        return run(args.seed, args.restart_incomplete)
    if args.verify:
        from model import p5d11_verify_full_training
        return p5d11_verify_full_training.main()
    parser.error("choose --prepare-schedules, --smoke, --seed N --run, or --verify")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
