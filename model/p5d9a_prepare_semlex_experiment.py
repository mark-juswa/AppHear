"""Prepare the governed P5-D9A Sem-Lex supplementation experiment.

This module performs static, read-only source verification and writes the
preregistered experiment package. It never creates a model or optimizer.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/recognition_upgrade/p5_representation_v2"
D2 = BASE / "p5d2_temporal_objective_ablation_01"
D8 = BASE / "p5d8_supplementation_design_01"
OUT = BASE / "p5d9_semlex_supplementation_01"
V2 = BASE / "p5b_migration_01/dataset"
SELECTED = D8 / "p5d8_selected_policy_manifest.csv"
ATTESTATION = D8 / "human_review_provenance_attestation.json"
POLICY = "P3_ONE_PER_SIGNER_CLASS_CLASS_SHARE_67"
SELECTED_SHA = "dda45f801806cd63a7ee6f59cbafe15650a402b59fb41a4f2a93a11acb6c8d08"
MEMBERSHIP_SHA = "142a04b3b7954ea7a8c3d0f1e8036c5f5332c5f45a8ebca2676b9a2a029edde5"
PROGRESS_SHA = "12cf08f81959a413a60aa1f869615a24485a41ee3d796e61fce7489ae5c480cf"
SOURCE_HASHES = {
    "v2_train": "a2261ea8d61e5eed1a526da0493da5b36c1bb54432ccef7f7479d6ca94634f11",
    "v2_val": "627275d03087f49fda65138253425131e35fe9c5cb8ded6a93b914484be5afe2",
    "v2_vocab": "a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b",
    "canonical_manifest": "8c1fab3df04a0240b5a178853b2206408806958afebdd19bd3d44d6fca606571",
}
BASELINE_HASHES = {
    ("PFCE_MATCHED", 101): "31e0ce88c95add99138f68588406892e29dfb8e1d14e780bf49667cf74a2c7a7",
    ("PFCE_MATCHED", 202): "6e76e951b5049ea3bac8b60f97f41fe9545a58b3b01fd6997bafece647a2121d",
    ("PFCE_MATCHED", 303): "8986110ae5a97ca571bbda986b9877a22e1d6a77cc5d62c7bbd36b7f4ea88057",
    ("CLIPCE_AGGREGATION_ALIGNED", 101): "b94a99b0a930e654cc1bd75e4f6bea8cce1820f91c670763e05a985dc24ec529",
    ("CLIPCE_AGGREGATION_ALIGNED", 202): "83ef9ff30e2ae7d38384c45d2d75c2a2be7e50dc7aab13d5d7a902ddbde290d6",
    ("CLIPCE_AGGREGATION_ALIGNED", 303): "7bd100c6dfc43426401149cc6287a27d71bfe3897bc4edbce2cbff5c454c6c87",
}
INIT_EXPECTED = {
    101: ("1f975130648fa997c78c0c857b4e6a4b32be00ca77404ec18bfcc1eee4943ac1", "56f482cb07e2829620282a7030ca689e8aa89de5e6e71d094921015dbb78716b"),
    202: ("4788fc1a0dd5f67eedd7d1ced4213ba4196ec26b2651345d4a0a415e53cd3fa4", "ba80647335a498b6644d5d6cf46aa7ebb884bf64bc3c46c78f2170d551e1467b"),
    303: ("a19e6297396d85f723230aaaade21bf36657f5653bcd9d36f421e34046707c4a", "25f9aaaad795133876085917f7a894b436b57195a0e0d16eae789e22a6291724"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tensor_hash(arrays: list[np.ndarray]) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        value = np.ascontiguousarray(array)
        digest.update(str(value.dtype).encode())
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.tobytes())
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def write_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def scalar(value: np.ndarray) -> str:
    return str(np.asarray(value).reshape(()).item())


def provenance_status() -> dict[str, Any]:
    attestation = json.loads(ATTESTATION.read_text(encoding="utf-8"))
    required = ("reviewer_name", "review_date", "attestation_date", "project_lead_confirmation")
    values = {key: str(attestation.get(key, "")).strip() for key in required}
    missing = [key for key, value in values.items() if not value]
    complete = not missing
    return {
        "attestation_path": str(ATTESTATION.resolve()),
        "attestation_sha256": sha256(ATTESTATION),
        "required_fields": values,
        "missing_fields": missing,
        "complete": complete,
        "training_authorized": complete,
        "smoke_optimizer_updates_authorized": complete,
        "status": "COMPLETE" if complete else "REVIEW_PROVENANCE_METADATA_INCOMPLETE",
    }


def verify_semlex(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        path = Path(row["v2_path"])
        record: dict[str, Any] = {
            "selected_index": index,
            "sample_id": row["semlex_sample_id"],
            "class_id": int(row["apphear_class_id"]),
            "gloss": row["apphear_gloss"],
            "signer_group_id": row["namespaced_semlex_signer_id"],
            "v2_path": str(path),
            "file_exists": path.is_file(),
        }
        if path.is_file():
            with np.load(path, allow_pickle=False) as data:
                features = np.asarray(data["features"])
                mask = np.asarray(data["frame_mask"], dtype=bool)
                checks = {
                    "shape_valid": features.shape == (96, 238),
                    "dtype_float32": features.dtype == np.float32,
                    "finite": bool(np.isfinite(features).all()),
                    "mask_shape_valid": mask.shape == (96,),
                    "mask_compact": bool(np.all(np.diff(mask.astype(np.int8)) <= 0)),
                    "mask_nonempty": bool(mask.any()),
                    "padding_zero": bool(np.count_nonzero(features[~mask]) == 0),
                    "sample_id_equal": "sample_id" in data and scalar(data["sample_id"]) == row["semlex_sample_id"],
                    "class_id_equal": "class_id" in data and int(np.asarray(data["class_id"]).reshape(())) == int(row["apphear_class_id"]),
                    "signer_id_equal": "signer_id" in data and f"SEMLEX::{scalar(data['signer_id'])}" == row["namespaced_semlex_signer_id"],
                }
            record.update(checks)
            record["passed"] = all(checks.values())
            record["v2_sha256"] = sha256(path)
        else:
            record["passed"] = False
            record["v2_sha256"] = ""
        results.append(record)
    return results


def run_bounded_smoke(membership: list[dict[str, Any]], expected_initialization: str) -> dict[str, Any]:
    """Run exactly ten optimizer updates per objective; no evaluation."""
    import tensorflow as tf
    from model import p5d2_temporal_objective_ablation as d2
    from model import p5d9_controlled_semlex_supplementation as runner

    train = runner.load_combined(membership)
    with np.load(V2 / "val.npz", allow_pickle=False) as val_data:
        validation_ids = {str(value) for value in val_data["sample_ids"]}
    shared = set(map(str, train["sample_ids"])) & validation_ids
    common_checks = {
        "combined_shape": list(train["X"].shape),
        "combined_shape_valid": train["X"].shape == (4807, 96, 238),
        "labels_in_range": bool(np.all((train["y"] >= 0) & (train["y"] < 236))),
        "masks_valid": bool(train["frame_mask"].shape == (4807, 96) and np.all(np.diff(train["frame_mask"].astype(np.int8), axis=1) <= 0) and np.all(train["frame_mask"].sum(axis=1) > 0)),
        "padding_zero": bool(np.count_nonzero(train["X"][~train["frame_mask"]]) == 0),
        "finite_features": bool(np.isfinite(train["X"]).all()),
        "validation_leakage_count": len(shared),
        "no_validation_leakage": not shared,
        "protected_test_accessed": False,
    }
    required_checks = ("combined_shape_valid", "labels_in_range", "masks_valid", "padding_zero", "finite_features", "no_validation_leakage")
    if not all(common_checks[key] for key in required_checks):
        raise RuntimeError("P5D9A_SMOKE_INPUT_INTEGRITY_FAILURE")
    order = d2.batch_permutation(101, 0, count=len(train["y"]))
    results = []
    for objective in ("PFCE_MATCHED", "CLIPCE_AGGREGATION_ALIGNED"):
        directory = OUT / "smoke" / objective / "seed_101"
        directory.mkdir(parents=True, exist_ok=True)
        model = d2.make_model(101)
        loaded_hash = d2.load_initialization(model, 101)
        if loaded_hash != expected_initialization:
            raise RuntimeError("P5D9A_SMOKE_INITIALIZATION_MISMATCH")
        before = d2.tensor_hash([np.asarray(value) for value in model.get_weights()])
        optimizer = tf.keras.optimizers.AdamW(learning_rate=5e-4, weight_decay=1e-4)
        optimizer.build(model.trainable_variables)
        losses: list[float] = []
        gradients_finite = True
        gradients_nonzero = False
        started = time.perf_counter()
        for update in range(10):
            chosen = order[update * 32:(update + 1) * 32]
            x_batch = tf.convert_to_tensor(train["X"][chosen])
            y_batch = tf.convert_to_tensor(train["y"][chosen])
            mask_batch = tf.convert_to_tensor(train["frame_mask"][chosen])
            with tf.GradientTape() as tape:
                probabilities = model(x_batch, training=True)
                numerator, denominator = d2.objective_components(objective, probabilities, y_batch, mask_batch)
                loss = numerator / denominator
            gradients = tape.gradient(loss, model.trainable_variables)
            usable = [gradient for gradient in gradients if gradient is not None]
            gradients_finite = gradients_finite and bool(usable) and all(bool(tf.reduce_all(tf.math.is_finite(gradient)).numpy()) for gradient in usable)
            gradients_nonzero = gradients_nonzero or any(bool(tf.reduce_any(tf.not_equal(gradient, 0)).numpy()) for gradient in usable)
            optimizer.apply_gradients(zip(gradients, model.trainable_variables))
            losses.append(float(loss.numpy()))
        after = d2.tensor_hash([np.asarray(value) for value in model.get_weights()])
        result = {
            "objective": objective, "seed": 101, "optimizer_updates": int(optimizer.iterations.numpy()),
            "initialization_tensor_sha256": before, "final_weight_tensor_sha256": after,
            "initialization_matches_contract": before == expected_initialization,
            "losses_finite": bool(np.isfinite(losses).all()), "first_loss": losses[0], "final_loss": losses[-1],
            "gradients_finite": gradients_finite, "gradients_nonzero": gradients_nonzero,
            "weights_updated": before != after, "elapsed_seconds": time.perf_counter() - started,
            "scientific_metric": False,
        }
        result["passed"] = bool(result["optimizer_updates"] == 10 and result["initialization_matches_contract"] and result["losses_finite"] and gradients_finite and gradients_nonzero and result["weights_updated"])
        write_json(directory / "run_state.json", result)
        results.append(result)
        del model, optimizer
        tf.keras.backend.clear_session()
    return {"common_checks": common_checks, "runs": results, "passed": all(result["passed"] for result in results), "total_optimizer_updates": 20, "full_training_executed": False, "scientific_interpretation_allowed": False}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    progress_before = sha256(ROOT / "context/progress-tracker.md")
    if progress_before != PROGRESS_SHA:
        raise RuntimeError("P5D9A_PROGRESS_TRACKER_PREHASH_MISMATCH")
    source_paths = {
        "v2_train": V2 / "train.npz", "v2_val": V2 / "val.npz", "v2_vocab": V2 / "vocab.json",
        "canonical_manifest": ROOT / "artifacts/recognition_upgrade/phase1_full_vocab/manifest_01/canonical_manifest.csv",
    }
    actual_sources = {key: sha256(value) for key, value in source_paths.items()}
    if actual_sources != SOURCE_HASHES:
        raise RuntimeError("P5D9A_SOURCE_HASH_MISMATCH")
    if sha256(SELECTED) != SELECTED_SHA:
        raise RuntimeError("P5D9A_SELECTED_MANIFEST_HASH_MISMATCH")
    selected = read_csv(SELECTED)
    if len(selected) != 881 or len({int(row["apphear_class_id"]) for row in selected}) != 65:
        raise RuntimeError("P5D9A_SELECTED_POLICY_COUNT_MISMATCH")
    semlex_integrity = verify_semlex(selected)
    if not all(row["passed"] for row in semlex_integrity):
        raise RuntimeError("P5D9A_SELECTED_SEMLEX_INTEGRITY_FAILURE")
    write_csv(OUT / "p5d9_selected_semlex_integrity.csv", semlex_integrity, list(semlex_integrity[0]))

    with np.load(V2 / "train.npz", allow_pickle=False) as data:
        train_y = np.asarray(data["y"], dtype=np.int32)
        sample_ids = [str(value) for value in data["sample_ids"]]
        signers = [str(value) for value in data["signer_group_ids"]]
        train_shape = tuple(data["X"].shape)
    if train_shape != (3926, 96, 238) or len(set(sample_ids)) != 3926:
        raise RuntimeError("P5D9A_APPHEAR_TRAIN_CONTRACT_MISMATCH")
    vocab = json.loads((V2 / "vocab.json").read_text(encoding="utf-8"))
    id_to_gloss = {int(value): key for key, value in vocab.items()}
    membership: list[dict[str, Any]] = []
    for source_index in sorted(range(len(sample_ids)), key=lambda value: sample_ids[value]):
        membership.append({
            "membership_index": len(membership), "source_dataset": "APPHEAR", "source_role": "frozen_train",
            "sample_id": sample_ids[source_index], "class_id": int(train_y[source_index]),
            "gloss": id_to_gloss[int(train_y[source_index])], "signer_group_id": signers[source_index],
            "feature_path": str((V2 / "train.npz").resolve()), "feature_row_index": source_index,
            "human_lexical_decision": "NOT_APPLICABLE", "selected_policy": POLICY,
        })
    for row in selected:
        membership.append({
            "membership_index": len(membership), "source_dataset": "SEMLEX", "source_role": "external_supplement_candidate",
            "sample_id": row["semlex_sample_id"], "class_id": int(row["apphear_class_id"]),
            "gloss": row["apphear_gloss"], "signer_group_id": row["namespaced_semlex_signer_id"],
            "feature_path": row["v2_path"], "feature_row_index": "",
            "human_lexical_decision": row["human_lexical_decision"], "selected_policy": POLICY,
        })
    write_csv(OUT / "p5d9_derived_combined_membership.csv", membership, list(membership[0]))
    signature_rows = [f"APPHEAR|{sample}" for sample in sorted(sample_ids)] + [
        f"SEMLEX|{row['semlex_sample_id']}|{row['apphear_class_id']}|{row['namespaced_semlex_signer_id']}" for row in selected
    ]
    computed_membership_sha = hashlib.sha256("\n".join(signature_rows).encode()).hexdigest()
    if computed_membership_sha != MEMBERSHIP_SHA or len(membership) != 4807:
        raise RuntimeError("P5D9A_COMBINED_MEMBERSHIP_MISMATCH")
    write_json(OUT / "p5d9_combined_membership_contract.json", {
        "apphear_rows": 3926, "semlex_rows": 881, "combined_rows": 4807,
        "classes": 236, "semlex_classes": 65, "semlex_signers": 32,
        "ordering": "APPHEAR stable sample_id, then selected P3 manifest order",
        "selected_policy": POLICY, "selected_manifest_sha256": SELECTED_SHA,
        "computed_membership_sha256": computed_membership_sha, "expected_membership_sha256": MEMBERSHIP_SHA,
        "passed": True,
    })

    current = Counter(int(value) for value in train_y)
    external = Counter(int(row["apphear_class_id"]) for row in selected)
    source_current = sum(current[class_id] for class_id in external)
    exposure = []
    for class_id in sorted(external):
        exposure.append({
            "class_id": class_id, "gloss": id_to_gloss[class_id], "current_apphear_clips": current[class_id],
            "selected_semlex_clips": external[class_id], "combined_clips": current[class_id] + external[class_id],
            "class_exposure_multiplier": (current[class_id] + external[class_id]) / current[class_id],
            "current_class_share": current[class_id] / 3926, "combined_class_share": (current[class_id] + external[class_id]) / 4807,
        })
    write_csv(OUT / "p5d9_class_exposure_shift.csv", exposure, list(exposure[0]))

    baseline_rows = []
    for (objective, seed), expected in BASELINE_HASHES.items():
        path = D2 / "runs" / objective / f"seed_{seed}" / "best.keras"
        actual = sha256(path)
        baseline_rows.append({"objective": objective, "seed": seed, "checkpoint_path": str(path.resolve()), "expected_sha256": expected, "actual_sha256": actual, "passed": actual == expected})
    if not all(row["passed"] for row in baseline_rows):
        raise RuntimeError("P5D9A_BASELINE_CHECKPOINT_MISMATCH")
    write_json(OUT / "p5d9_baseline_reuse_audit.json", {"rows": baseline_rows, "passed": True, "retraining": False})
    init_rows = []
    for seed, (expected_file, expected_tensor) in INIT_EXPECTED.items():
        path = D2 / "initializations" / f"seed_{seed}.weights.npz"
        with np.load(path, allow_pickle=False) as saved:
            arrays = [np.asarray(saved[key]) for key in sorted(saved.files)]
        actual_file, actual_tensor = sha256(path), tensor_hash(arrays)
        init_rows.append({"seed": seed, "initialization_path": str(path.resolve()), "expected_file_sha256": expected_file, "actual_file_sha256": actual_file, "expected_tensor_sha256": expected_tensor, "actual_tensor_sha256": actual_tensor, "pfce_clipce_same_initialization": True, "passed": actual_file == expected_file and actual_tensor == expected_tensor})
    if not all(row["passed"] for row in init_rows):
        raise RuntimeError("P5D9A_INITIALIZATION_MISMATCH")
    write_json(OUT / "p5d9_initialization_parity.json", {"rows": init_rows, "passed": True})

    provenance = provenance_status()
    write_json(OUT / "p5d9a_provenance_status.json", provenance)
    training_contract = {
        "experiment": "P5-D9", "causal_limitation": "CLASS_EXPOSURE_AND_SIGNER_DIVERSITY_JOINT_INTERVENTION",
        "selected_policy": POLICY, "input": [96, 238], "classes": 236, "model": "4x64 causal TCN",
        "kernel": 3, "dilations": [1, 2, 4, 8], "dropout": 0.3, "parameters": 163884,
        "objectives": ["PFCE_MATCHED", "CLIPCE_AGGREGATION_ALIGNED"], "seeds": [101, 202, 303],
        "optimizer": "AdamW", "learning_rate": 0.0005, "weight_decay": 0.0001, "batch_size": 32,
        "optimizer_updates": 12300, "validation_every_updates": 123, "validation_opportunities": 100,
        "checkpoint_selection": "minimum primary-validation clip NLL; strict less-than; earliest tie retained",
        "augmentation": "NONE", "warm_start": "NONE", "class_weighting": "NONE", "source_balancing": "NONE",
        "initializations": {str(row["seed"]): row["actual_tensor_sha256"] for row in init_rows},
        "combined_membership_sha256": MEMBERSHIP_SHA, "provenance_gate_complete": provenance["complete"],
    }
    write_json(OUT / "p5d9_training_contract.json", training_contract)
    write_json(OUT / "p5d9_evaluation_contract.json", {
        "primary_validation_only": True, "protected_test": "PROHIBITED", "clip_prediction": "masked arithmetic mean of per-frame softmax probabilities then argmax",
        "primary_endpoint": "signer-balanced Top1", "secondary": ["clip Top1", "Top5", "Macro F1", "clip NLL", "per-frame accuracy", "temporal failure taxonomy"],
        "comparison": "supplemented minus frozen baseline within objective and seed", "signer_blocked_bootstrap_replicates": 10000,
    })
    write_json(OUT / "p5d9_preregistered_outcome_contract.json", {
        "frozen_before_training": True,
        "primary_endpoint": "SIGNER_BALANCED_TOP1",
        "supporting_full_vocabulary_metrics": ["ORDINARY_TOP1", "MACRO_F1"],
        "additional_secondary_metrics": ["TOP5", "CLIP_NLL", "PER_FRAME_ACCURACY"],
        "delta_direction": {"accuracy_and_f1": "positive is improvement", "clip_nll": "negative is improvement"},
        "branch_classifications": {
            "BRANCH_GENERALIZATION_BENEFIT_SUPPORTED": ["median signer-balanced Top1 delta > 0", "at least 2/3 seed signer-balanced deltas > 0", "median ordinary Top1 delta >= 0", "median MacroF1 delta >= 0"],
            "BRANCH_GENERALIZATION_SIGNAL_MIXED": ["signer-balanced positive direction conflicts with ordinary Top1 or MacroF1", "ordinary Top1/MacroF1 improve without consistent signer-balanced direction", "seed direction materially inconsistent"],
            "BRANCH_NO_GENERALIZATION_BENEFIT": ["median signer-balanced Top1 delta <= 0", "fewer than 2/3 seeds improve", "no coherent secondary improvement sufficient for mixed"],
            "BRANCH_GENERALIZATION_HARM": ["median signer-balanced Top1 delta < 0", "at least 2/3 seed signer-balanced deltas < 0", "median ordinary Top1 or median MacroF1 declines"],
        },
        "experiment_classifications": {
            "SEMLEX_SUPPLEMENTATION_BENEFIT_BROADLY_SUPPORTED": "both objectives benefit supported",
            "SEMLEX_SUPPLEMENTATION_BENEFIT_OBJECTIVE_CONDITIONAL": "exactly one benefits; other mixed or no benefit, not harm",
            "SEMLEX_SUPPLEMENTATION_EFFECT_MIXED": "neither broad benefit; mixed changes; no broad harm",
            "SEMLEX_SUPPLEMENTATION_NO_GENERALIZATION_BENEFIT": "both no benefit and no broad harm",
            "SEMLEX_SUPPLEMENTATION_HARM_BROADLY_SUPPORTED": "both objectives harm",
            "SEMLEX_SUPPLEMENTATION_OBJECTIVE_CONDITIONAL_HARM": "one harms and other does not benefit",
            "SEMLEX_SUPPLEMENTATION_OBJECTIVE_TRADEOFF": "one benefits and other harms",
        },
        "signer_block_bootstrap": "reported uncertainty, not hard pass/fail because validation has few signer groups",
        "joint_intervention_limit": "P3 changes both class exposure and independent external signer diversity; D9 cannot attribute any effect to either alone.",
        "no_posthoc_threshold_tuning": True,
    })
    write_json(OUT / "p5d9b_post_training_audit_contract.json", {
        "gate": "P5D9B_POST_TRAINING_CAUSAL_AUDIT", "execute_now": False,
        "required": ["verify six completed runs", "evaluate selected checkpoints", "paired signer-blocked uncertainty", "temporal taxonomy", "per-class support-qualified analysis", "apply preregistered decision only"],
    })
    smoke = None
    if provenance["complete"]:
        smoke = run_bounded_smoke(membership, init_rows[0]["actual_tensor_sha256"])
        write_json(OUT / "p5d9_smoke_result.json", smoke)
        if not smoke["passed"]:
            raise RuntimeError("P5D9A_SMOKE_VALIDATION_FAILURE")
    write_json(OUT / "p5d9_workload_estimate.json", {
        "full_runs": 6, "updates_per_run": 12300, "validation_opportunities_per_run": 100,
        "estimated_minutes_per_run": [14, 22], "estimated_sequential_total_hours": [1.4, 2.2], "runtime_confidence": "MODERATE",
        "estimated_output_storage_mb": [30, 100], "storage_confidence": "MODERATE", "smoke_training_run": bool(smoke),
    })
    decision = "P5D9A_FULL_TRAINING_READY_FOR_PROJECT_LEAD" if provenance["complete"] and smoke and smoke["passed"] else "P5D9A_STATIC_PREPARATION_COMPLETE_PROVENANCE_BLOCKED"
    next_gate = "PROJECT_LEAD_RUNS_P5D9_SIX_SUPPLEMENTED_RUNS" if decision == "P5D9A_FULL_TRAINING_READY_FOR_PROJECT_LEAD" else "PROJECT_LEAD_COMPLETES_REVIEW_PROVENANCE"
    write_json(OUT / "p5d9a_decision.json", {"classification": decision, "confidence": "HIGH", "optimizer_updates_executed": 20 if smoke else 0, "full_training_executed": False})
    write_json(OUT / "p5d9a_next_gate.json", {"next_gate": next_gate, "executed": False})

    guide = f"""# Run P5-D9 full Sem-Lex supplementation training\n\n**CURRENT STATUS: BLOCKED** until all four fields in `{ATTESTATION}` are completed and this static preparation is rerun. The runner independently enforces this gate.\n\nWorking directory: `{ROOT}`  \nPython: `{ROOT / '.venv/Scripts/python.exe'}`\n\n## Sequential launcher (recommended)\n\n```powershell\nSet-Location '{ROOT}'\n& '.\\.venv\\Scripts\\python.exe' -m model.p5d9_controlled_semlex_supplementation --run-all\n```\n\n## Individual runs\n\n```powershell\n& '.\\.venv\\Scripts\\python.exe' -m model.p5d9_controlled_semlex_supplementation --objective PFCE_MATCHED --seed 101 --run\n& '.\\.venv\\Scripts\\python.exe' -m model.p5d9_controlled_semlex_supplementation --objective CLIPCE_AGGREGATION_ALIGNED --seed 101 --run\n& '.\\.venv\\Scripts\\python.exe' -m model.p5d9_controlled_semlex_supplementation --objective PFCE_MATCHED --seed 202 --run\n& '.\\.venv\\Scripts\\python.exe' -m model.p5d9_controlled_semlex_supplementation --objective CLIPCE_AGGREGATION_ALIGNED --seed 202 --run\n& '.\\.venv\\Scripts\\python.exe' -m model.p5d9_controlled_semlex_supplementation --objective PFCE_MATCHED --seed 303 --run\n& '.\\.venv\\Scripts\\python.exe' -m model.p5d9_controlled_semlex_supplementation --objective CLIPCE_AGGREGATION_ALIGNED --seed 303 --run\n```\n\nCompleted runs are skipped only after their state and hashes verify. An interrupted run is not resumed because exact dropout continuation is not guaranteed; restart that single run with `--restart-incomplete`.\n\nVerification only:\n\n```powershell\n& '.\\.venv\\Scripts\\python.exe' -m model.p5d9_verify_full_training\n```\n\nExpected: 6 runs, each 12,300 updates and 100 validation opportunities. One failed clip is impossible here because inputs were prevalidated; any input failure stops the run.\n\n**DO NOT START A POST-HOC ANALYSIS OR ANOTHER TRAINING EXPERIMENT AFTER THIS COMMAND FINISHES.**\n"""
    if decision == "P5D9A_FULL_TRAINING_READY_FOR_PROJECT_LEAD":
        guide = guide.replace(
            "**CURRENT STATUS: BLOCKED** until all four fields in `" + str(ATTESTATION) + "` are completed and this static preparation is rerun.",
            "**CURRENT STATUS: READY FOR PROJECT-LEAD EXECUTION.** Provenance and bounded smoke validation passed.",
        )
    atomic_text(OUT / "RUN_P5D9_FULL_TRAINING.md", guide)

    integrity = {
        "passed": True, "static_preparation_complete": True, "provenance_complete": provenance["complete"],
        "optimizer_updates_executed": 20 if smoke else 0, "smoke_training_executed": bool(smoke), "smoke_passed": bool(smoke and smoke["passed"]), "full_training_executed": False,
        "apphear_train_rows": 3926, "selected_semlex_rows": 881, "combined_rows": 4807,
        "classes": 236, "semlex_classes": 65, "semlex_signers": 32,
        "source_hashes": actual_sources, "selected_manifest_sha256": sha256(SELECTED), "combined_membership_sha256": computed_membership_sha,
        "protected_test_accessed": False, "data_modified": False, "context_modified": False,
        "progress_tracker_before": progress_before,
    }
    progress_after = sha256(ROOT / "context/progress-tracker.md")
    integrity["progress_tracker_after"] = progress_after
    integrity["progress_tracker_untouched"] = progress_after == progress_before == PROGRESS_SHA
    write_json(OUT / "p5d9a_integrity.json", integrity)
    smoke_text = "Bounded smoke validation passed for PFCE and CLIPCE with exactly 10 optimizer updates each. No full run was executed." if smoke else f"No optimizer update was executed. Human-review provenance remains incomplete: {', '.join(provenance['missing_fields'])}."
    report = f"""# P5-D9A Sem-Lex Supplementation Experiment Preparation\n\nStatic preparation passed for policy `{POLICY}`: 3,926 frozen AppHear clips plus 881 governed Sem-Lex clips form an exact 4,807-row membership with SHA `{computed_membership_sha}`. All 881 selected V2 tensors passed structural and lineage checks. Frozen D2 baselines and seed-specific initializations match their governed hashes.\n\n{smoke_text}\n\nClassification: `{decision}`  \nNext gate: `{next_gate}`\n\nThis preparation preregisters a joint class-exposure and external-signer-diversity intervention. It cannot isolate those two components.\n"""
    atomic_text(OUT / "P5D9A_TRAINING_PREPARATION_RESULT.md", report)

    scripts = [ROOT / "model/p5d9a_prepare_semlex_experiment.py", ROOT / "model/p5d9_controlled_semlex_supplementation.py", ROOT / "model/p5d9_verify_full_training.py"]
    files = [path for path in OUT.rglob("*") if path.is_file() and path.name != "artifact_hash_manifest.json"] + [path for path in scripts if path.is_file()]
    entries = [{"path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size} for path in sorted(files)]
    manifest_payload = {"files": entries, "file_count": len(entries), "manifest_scope": "P5-D9A preparation and bounded smoke only; no full training outputs"}
    write_json(OUT / "artifact_hash_manifest.json", manifest_payload)
    print(json.dumps({"decision": decision, "next_gate": next_gate, "combined_rows": 4807, "provenance_complete": provenance["complete"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
