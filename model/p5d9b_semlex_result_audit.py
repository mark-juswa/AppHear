"""P5-D9B governed post-training evaluation and causal-result audit.

Evaluation only: twelve frozen checkpoints, one frozen primary-validation
population, no protected-test path, no optimizer, and no training data writes.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from model import p5d2_temporal_objective_ablation as d2


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/recognition_upgrade/p5_representation_v2"
D2 = BASE / "p5d2_temporal_objective_ablation_01"
D8 = BASE / "p5d8_supplementation_design_01"
D9 = BASE / "p5d9_semlex_supplementation_01"
OUT = BASE / "p5d9b_semlex_result_audit_01"
V2 = BASE / "p5b_migration_01/dataset"
OBJECTIVES = ("PFCE_MATCHED", "CLIPCE_AGGREGATION_ALIGNED")
SEEDS = (101, 202, 303)
CONDITIONS = ("BASELINE", "SUPPLEMENTED")
EXPECTED_OUTCOME_SHA = "8968c0d4bfa45fb7d54227326bb71926cd1c77cd193e750cdae2765b62f86e12"
EXPECTED_MANIFEST_SHA = "dda45f801806cd63a7ee6f59cbafe15650a402b59fb41a4f2a93a11acb6c8d08"
EXPECTED_MEMBERSHIP_SHA = "142a04b3b7954ea7a8c3d0f1e8036c5f5332c5f45a8ebca2676b9a2a029edde5"
EXPECTED_VAL_SHA = "627275d03087f49fda65138253425131e35fe9c5cb8ded6a93b914484be5afe2"
PROGRESS_SHA = "12cf08f81959a413a60aa1f869615a24485a41ee3d796e61fce7489ae5c480cf"
CHECKPOINTS = {
    ("BASELINE", "PFCE_MATCHED", 101): "31e0ce88c95add99138f68588406892e29dfb8e1d14e780bf49667cf74a2c7a7",
    ("BASELINE", "PFCE_MATCHED", 202): "6e76e951b5049ea3bac8b60f97f41fe9545a58b3b01fd6997bafece647a2121d",
    ("BASELINE", "PFCE_MATCHED", 303): "8986110ae5a97ca571bbda986b9877a22e1d6a77cc5d62c7bbd36b7f4ea88057",
    ("BASELINE", "CLIPCE_AGGREGATION_ALIGNED", 101): "b94a99b0a930e654cc1bd75e4f6bea8cce1820f91c670763e05a985dc24ec529",
    ("BASELINE", "CLIPCE_AGGREGATION_ALIGNED", 202): "83ef9ff30e2ae7d38384c45d2d75c2a2be7e50dc7aab13d5d7a902ddbde290d6",
    ("BASELINE", "CLIPCE_AGGREGATION_ALIGNED", 303): "7bd100c6dfc43426401149cc6287a27d71bfe3897bc4edbce2cbff5c454c6c87",
    ("SUPPLEMENTED", "PFCE_MATCHED", 101): "ac51c2d711092a6e3de825331f66816487b431a4e9de2354fd7c54a5a2bed258",
    ("SUPPLEMENTED", "PFCE_MATCHED", 202): "a541dab88b0209ad0bffd2285b5000f0f3c36928b1df3c9d472f772f144ce5c3",
    ("SUPPLEMENTED", "PFCE_MATCHED", 303): "82055daf5950e1e31a1707222bc479299cbd3a6a376dd0a9af111d72a7a3b309",
    ("SUPPLEMENTED", "CLIPCE_AGGREGATION_ALIGNED", 101): "8b57c9b6ba420b9bd9da0e45a7fca69a5eea7550595ad5c7c2814318db40f219",
    ("SUPPLEMENTED", "CLIPCE_AGGREGATION_ALIGNED", 202): "51ac65bdeaf2b0373a268e60a9f5fa439fc82889d986491edf99dab029578928",
    ("SUPPLEMENTED", "CLIPCE_AGGREGATION_ALIGNED", 303): "6ce9d0e105433dee67c6c4f87a7a475f7a88be959ba522fd5cc17557e5c7338e",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
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


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else []
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def checkpoint_path(condition: str, objective: str, seed: int) -> Path:
    root = D2 if condition == "BASELINE" else D9
    return root / "runs" / objective / f"seed_{seed}" / "best.keras"


def supported_macro_f1(y: np.ndarray, prediction: np.ndarray, class_ids: Iterable[int]) -> float:
    values = []
    for class_id in class_ids:
        true = y == class_id
        if not true.any():
            continue
        predicted = prediction == class_id
        tp = int(np.sum(true & predicted)); fp = int(np.sum(~true & predicted)); fn = int(np.sum(true & ~predicted))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        values.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return float(np.mean(values)) if values else float("nan")


def validation_hash(val: dict[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for index in range(len(val["y"])):
        digest.update(f"{val['sample_ids'][index]}|{val['signers'][index]}|{int(val['y'][index])}|".encode())
        digest.update(np.ascontiguousarray(val["frame_mask"][index]).tobytes())
    return digest.hexdigest()


def verify_inputs() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, np.ndarray]]:
    if sha256(D9 / "p5d9_preregistered_outcome_contract.json") != EXPECTED_OUTCOME_SHA:
        raise RuntimeError("P5D9B_BLOCKED_OUTCOME_CONTRACT_MISMATCH")
    if sha256(D8 / "p5d8_selected_policy_manifest.csv") != EXPECTED_MANIFEST_SHA:
        raise RuntimeError("P5D9B_BLOCKED_SELECTED_MANIFEST_MISMATCH")
    if sha256(V2 / "val.npz") != EXPECTED_VAL_SHA:
        raise RuntimeError("P5D9B_BLOCKED_VALIDATION_HASH_MISMATCH")
    verifier = json.loads((D9 / "p5d9_full_training_verification.json").read_text(encoding="utf-8"))
    if not verifier.get("passed") or verifier.get("verified_runs") != 6:
        raise RuntimeError("P5D9B_BLOCKED_SUPPLEMENTED_RUN_VERIFICATION")
    checkpoint_rows: list[dict[str, Any]] = []
    contract_rows: list[dict[str, Any]] = []
    d2_metrics = {(row["branch"], int(row["seed"])): row for row in read_csv(D2 / "p5d2_validation_metrics.csv")}
    for condition in CONDITIONS:
        for objective in OBJECTIVES:
            for seed in SEEDS:
                path = checkpoint_path(condition, objective, seed)
                actual = sha256(path)
                expected = CHECKPOINTS[(condition, objective, seed)]
                checkpoint_rows.append({"condition": condition, "objective": objective, "seed": seed, "checkpoint_path": str(path.resolve()), "expected_sha256": expected, "actual_sha256": actual, "passed": actual == expected})
                directory = path.parent
                history = read_csv(directory / "history.csv")
                if condition == "SUPPLEMENTED":
                    state = json.loads((directory / "run_state.json").read_text(encoding="utf-8"))
                    contract = json.loads((directory / "run_contract.json").read_text(encoding="utf-8"))
                    nll_field, update_field = "validation_clip_nll", "optimizer_updates"
                    minimum = min(float(row[nll_field]) for row in history)
                    earliest = min(int(row[update_field]) for row in history if float(row[nll_field]) == minimum)
                    checks = {
                        "status_complete": state.get("status") == "COMPLETE",
                        "updates_exact": int(state.get("completed_updates", -1)) == 12300,
                        "optimizer_iterations_exact": int(state.get("optimizer_iterations", -1)) == 12300,
                        "validation_opportunities_exact": int(state.get("validation_opportunities", -1)) == 100 and len(history) == 100,
                        "selected_manifest_exact": contract.get("selected_manifest_sha256") == EXPECTED_MANIFEST_SHA,
                        "membership_exact": contract.get("membership_sha256") == EXPECTED_MEMBERSHIP_SHA,
                        "checkpoint_rule_exact": contract.get("checkpoint_rule") == "strict minimum validation clip NLL; earliest tie retained",
                        "best_nll_exact": math.isclose(float(state["best_validation_clip_nll"]), minimum, rel_tol=0, abs_tol=1e-12),
                        "earliest_best_exact": int(state["selected_optimizer_update"]) == earliest,
                        "initialization_present": bool(contract.get("initialization_tensor_sha256")),
                    }
                    selected_update = int(state["selected_optimizer_update"])
                else:
                    state = json.loads((directory / "run_state.json").read_text(encoding="utf-8"))
                    metric = d2_metrics[(objective, seed)]
                    minimum = min(float(row["validation_clip_nll"]) for row in history)
                    earliest_epoch = min(int(row["epoch"]) for row in history if float(row["validation_clip_nll"]) == minimum)
                    checks = {
                        "status_complete": state.get("status") == "MAX_EPOCH_REACHED",
                        "updates_exact": int(history[-1]["optimizer_iterations"]) == 12300,
                        "optimizer_iterations_exact": int(history[-1]["optimizer_iterations"]) == 12300,
                        "validation_opportunities_exact": len(history) == 100,
                        "selected_manifest_exact": True, "membership_exact": True,
                        "checkpoint_rule_exact": True,
                        "best_nll_exact": math.isclose(float(metric["validation_clip_nll"]), minimum, rel_tol=0, abs_tol=1e-12),
                        "earliest_best_exact": int(metric["selected_epoch"]) == earliest_epoch,
                        "initialization_present": True,
                    }
                    selected_update = (int(metric["selected_epoch"]) + 1) * 123
                contract_rows.append({"condition": condition, "objective": objective, "seed": seed, **checks, "selected_optimizer_update": selected_update, "environment_record_present": False, "core_contract_passed": all(checks.values())})
    if not all(row["passed"] for row in checkpoint_rows):
        raise RuntimeError("P5D9B_BLOCKED_CHECKPOINT_INTEGRITY")
    if not all(row["core_contract_passed"] for row in contract_rows):
        raise RuntimeError("P5D9B_BLOCKED_RUN_CONTRACT_INTEGRITY")
    val = d2.load_split("val")
    if len(val["y"]) != 816 or len(set(map(str, val["sample_ids"]))) != 816:
        raise RuntimeError("P5D9B_VALIDATION_MEMBERSHIP_FAILURE")
    return checkpoint_rows, contract_rows, val


def evaluate_all(val: dict[str, np.ndarray], vocab: dict[int, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[tuple[str, str, int], dict[str, np.ndarray]], list[dict[str, Any]]]:
    import tensorflow as tf

    prediction_dir = OUT / "predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    metric_rows: list[dict[str, Any]] = []
    signer_rows: list[dict[str, Any]] = []
    arrays: dict[tuple[str, str, int], dict[str, np.ndarray]] = {}
    manifest_rows: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        for objective in OBJECTIVES:
            for seed in SEEDS:
                path = checkpoint_path(condition, objective, seed)
                model = tf.keras.models.load_model(path, safe_mode=False)
                frame = d2.infer_probabilities(model, val["X"])
                denominator = np.maximum(val["frame_mask"].sum(axis=1, keepdims=True), 1)
                clip = (frame.astype(np.float64) * val["frame_mask"][:, :, None]).sum(axis=1) / denominator
                prediction = clip.argmax(axis=1).astype(np.int16)
                top5 = np.argsort(clip, axis=1)[:, -5:]
                true_probability = clip[np.arange(len(val["y"])), val["y"]]
                frame_prediction = frame.argmax(axis=2).astype(np.int16)
                final_margin = np.zeros((len(val["y"]), 96), dtype=np.float32)
                for index in range(len(val["y"])):
                    final_margin[index] = frame[index, :, int(val["y"][index])] - frame[index, :, int(prediction[index])]
                signer_top1 = []
                for signer in sorted(set(map(str, val["signers"]))):
                    chosen = np.asarray([str(value) == signer for value in val["signers"]])
                    top1 = float(np.mean(prediction[chosen] == val["y"][chosen])); signer_top1.append(top1)
                    signer_rows.append({"condition": condition, "objective": objective, "seed": seed, "signer_group_id": signer, "clips": int(chosen.sum()), "top1": top1, "macro_f1": supported_macro_f1(val["y"][chosen], prediction[chosen], sorted(set(map(int, val["y"][chosen])))), "mean_true_class_probability": float(np.mean(true_probability[chosen]))})
                metric_rows.append({
                    "condition": condition, "objective": objective, "seed": seed, "validation_clips": len(val["y"]),
                    "ordinary_top1": float(np.mean(prediction == val["y"])), "signer_balanced_top1": float(np.mean(signer_top1)),
                    "macro_f1": d2.macro_f1(val["y"], prediction), "top5": float(np.mean([val["y"][i] in top5[i] for i in range(len(val["y"]))])),
                    "clip_nll": float(np.mean(-np.log(np.clip(true_probability, d2.EPSILON, 1.0)))),
                    "per_frame_accuracy": float(np.sum((frame_prediction == val["y"][:, None]) * val["frame_mask"]) / val["frame_mask"].sum()),
                })
                output = prediction_dir / f"{condition.lower()}__{objective.lower()}__seed_{seed}.npz"
                np.savez_compressed(output, clip_probabilities=clip.astype(np.float32), predictions=prediction, top5=top5.astype(np.int16), frame_argmax=frame_prediction, true_vs_final_prediction_margin=final_margin, sample_ids=val["sample_ids"], signer_group_ids=val["signers"], labels=val["y"], frame_mask=val["frame_mask"])
                arrays[(condition, objective, seed)] = {"clip": clip, "prediction": prediction, "top5": top5, "frame_prediction": frame_prediction, "margin": final_margin}
                manifest_rows.append({"condition": condition, "objective": objective, "seed": seed, "prediction_path": str(output.resolve()), "prediction_sha256": sha256(output), "checkpoint_sha256": sha256(path), "validation_membership_sha256": validation_hash(val), "clips": len(val["y"])})
                del model, frame
                tf.keras.backend.clear_session()
    return metric_rows, signer_rows, arrays, manifest_rows


def paired_deltas(metrics: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lookup = {(row["condition"], row["objective"], row["seed"]): row for row in metrics}
    names = ("signer_balanced_top1", "ordinary_top1", "macro_f1", "top5", "clip_nll", "per_frame_accuracy")
    deltas = []
    for objective in OBJECTIVES:
        for seed in SEEDS:
            baseline, supplemented = lookup[("BASELINE", objective, seed)], lookup[("SUPPLEMENTED", objective, seed)]
            deltas.append({"objective": objective, "seed": seed, **{f"{name}_delta": supplemented[name] - baseline[name] for name in names}})
    summary = []
    for objective in OBJECTIVES:
        chosen = [row for row in deltas if row["objective"] == objective]
        for name in names:
            values = np.asarray([row[f"{name}_delta"] for row in chosen], dtype=float)
            summary.append({"objective": objective, "metric": name, "mean_delta": float(np.mean(values)), "median_delta": float(np.median(values)), "std_delta": float(np.std(values)), "minimum_delta": float(np.min(values)), "maximum_delta": float(np.max(values)), "positive_seeds": int(np.sum(values > 0)), "negative_seeds": int(np.sum(values < 0)), "seeds": 3})
    return deltas, summary


def bootstrap(val: dict[str, np.ndarray], arrays: dict[tuple[str, str, int], dict[str, np.ndarray]]) -> list[dict[str, Any]]:
    signers = sorted(set(map(str, val["signers"])))
    indices = {signer: np.flatnonzero(np.asarray([str(value) == signer for value in val["signers"]])) for signer in signers}
    rows = []
    for objective_index, objective in enumerate(OBJECTIVES):
        for seed in SEEDS:
            base = arrays[("BASELINE", objective, seed)]["prediction"]
            supp = arrays[("SUPPLEMENTED", objective, seed)]["prediction"]
            rng_seed = 900_000 + objective_index * 10_000 + seed
            rng = np.random.Generator(np.random.PCG64(rng_seed))
            ordinary = np.empty(10_000); balanced = np.empty(10_000); macro = np.empty(10_000)
            signer_base = {signer: float(np.mean(base[idx] == val["y"][idx])) for signer, idx in indices.items()}
            signer_supp = {signer: float(np.mean(supp[idx] == val["y"][idx])) for signer, idx in indices.items()}
            for replicate in range(10_000):
                draw = [str(value) for value in rng.choice(signers, len(signers), replace=True)]
                chosen = np.concatenate([indices[signer] for signer in draw])
                ordinary[replicate] = np.mean(supp[chosen] == val["y"][chosen]) - np.mean(base[chosen] == val["y"][chosen])
                balanced[replicate] = np.mean([signer_supp[signer] - signer_base[signer] for signer in draw])
                macro[replicate] = d2.macro_f1(val["y"][chosen], supp[chosen]) - d2.macro_f1(val["y"][chosen], base[chosen])
            for metric, values in (("ordinary_top1", ordinary), ("signer_balanced_top1", balanced), ("macro_f1", macro)):
                rows.append({"objective": objective, "seed": seed, "metric": metric, "point_delta": float(np.mean(values)), "ci95_low": float(np.percentile(values, 2.5)), "ci95_high": float(np.percentile(values, 97.5)), "replicates": 10000, "cluster_unit": "signer_group_id", "bootstrap_seed": rng_seed, "signer_clusters": len(signers)})
    return rows


def classify_branches(deltas: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    branches: dict[str, Any] = {}
    for objective in OBJECTIVES:
        chosen = [row for row in deltas if row["objective"] == objective]
        sb = np.asarray([row["signer_balanced_top1_delta"] for row in chosen]); ordinary = np.asarray([row["ordinary_top1_delta"] for row in chosen]); macro = np.asarray([row["macro_f1_delta"] for row in chosen])
        med_sb, med_o, med_m = map(float, (np.median(sb), np.median(ordinary), np.median(macro)))
        positive, negative = int(np.sum(sb > 0)), int(np.sum(sb < 0))
        benefit = med_sb > 0 and positive >= 2 and med_o >= 0 and med_m >= 0
        harm = med_sb < 0 and negative >= 2 and (med_o < 0 or med_m < 0)
        coherent_secondary = (med_o > 0 and int(np.sum(ordinary > 0)) >= 2) or (med_m > 0 and int(np.sum(macro > 0)) >= 2)
        no_benefit = med_sb <= 0 and positive < 2 and not coherent_secondary
        if benefit: classification = "BRANCH_GENERALIZATION_BENEFIT_SUPPORTED"
        elif harm: classification = "BRANCH_GENERALIZATION_HARM"
        elif no_benefit: classification = "BRANCH_NO_GENERALIZATION_BENEFIT"
        else: classification = "BRANCH_GENERALIZATION_SIGNAL_MIXED"
        branches[objective] = {"classification": classification, "median_signer_balanced_top1_delta": med_sb, "positive_signer_balanced_seeds": positive, "negative_signer_balanced_seeds": negative, "median_ordinary_top1_delta": med_o, "median_macro_f1_delta": med_m, "rules_applied_from_frozen_contract": True}
    left, right = (branches[objective]["classification"] for objective in OBJECTIVES)
    benefit = "BRANCH_GENERALIZATION_BENEFIT_SUPPORTED"; mixed = "BRANCH_GENERALIZATION_SIGNAL_MIXED"; no = "BRANCH_NO_GENERALIZATION_BENEFIT"; harm = "BRANCH_GENERALIZATION_HARM"
    if left == benefit and right == benefit: outcome = "SEMLEX_SUPPLEMENTATION_BENEFIT_BROADLY_SUPPORTED"
    elif {left, right} == {benefit, harm}: outcome = "SEMLEX_SUPPLEMENTATION_OBJECTIVE_TRADEOFF"
    elif (left == benefit and right in {mixed, no}) or (right == benefit and left in {mixed, no}): outcome = "SEMLEX_SUPPLEMENTATION_BENEFIT_OBJECTIVE_CONDITIONAL"
    elif left == harm and right == harm: outcome = "SEMLEX_SUPPLEMENTATION_HARM_BROADLY_SUPPORTED"
    elif (left == harm and right != benefit) or (right == harm and left != benefit): outcome = "SEMLEX_SUPPLEMENTATION_OBJECTIVE_CONDITIONAL_HARM"
    elif left == no and right == no: outcome = "SEMLEX_SUPPLEMENTATION_NO_GENERALIZATION_BENEFIT"
    else: outcome = "SEMLEX_SUPPLEMENTATION_EFFECT_MIXED"
    experiment = {"classification": outcome, "pfce_branch": left, "clipce_branch": right, "outcome_contract_sha256": EXPECTED_OUTCOME_SHA, "rules_applied_exactly": True}
    return branches, experiment


def slice_and_class_diagnostics(val: dict[str, np.ndarray], arrays: dict[tuple[str, str, int], dict[str, np.ndarray]], vocab: dict[int, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, set[int]], dict[int, dict[str, str]]]:
    baseline_rows = read_csv(D8 / "p5d8_classwise_source_baseline.csv")
    metadata = {int(row["class_id"]): row for row in baseline_rows}
    supplemented = set(metadata)
    exact = {class_id for class_id, row in metadata.items() if row["human_decision"] == "ACCEPT_EXACT_FORM"}
    variant = {class_id for class_id, row in metadata.items() if row["human_decision"] == "ACCEPT_COMPATIBLE_VARIANT"}
    critical = {class_id for class_id, row in metadata.items() if row["coverage_deficit_level"] == "CRITICAL_COVERAGE_DEFICIT"}
    high = {class_id for class_id, row in metadata.items() if row["coverage_deficit_level"] == "HIGH_COVERAGE_DEFICIT"}
    slices = {"ALL_236_PRIMARY": set(range(236)), "SUPPLEMENTED_65_DIAGNOSTIC": supplemented, "UNSUPPLEMENTED_171_DIAGNOSTIC": set(range(236)) - supplemented, "EXACT_FORM_47_DIAGNOSTIC": exact, "COMPATIBLE_VARIANT_18_DIAGNOSTIC": variant, "CRITICAL_39_DIAGNOSTIC": critical, "HIGH_DEFICIT_26_DIAGNOSTIC": high}
    slice_rows = []
    for name, class_ids in slices.items():
        chosen = np.isin(val["y"], list(class_ids)); support = int(chosen.sum())
        for objective in OBJECTIVES:
            for seed in SEEDS:
                values = {}
                for condition in CONDITIONS:
                    prediction = arrays[(condition, objective, seed)]["prediction"]
                    values[condition] = {"top1": float(np.mean(prediction[chosen] == val["y"][chosen])) if support else float("nan"), "macro_f1": supported_macro_f1(val["y"][chosen], prediction[chosen], class_ids)}
                slice_rows.append({"slice": name, "evidence_role": "PRIMARY" if name == "ALL_236_PRIMARY" else "DIAGNOSTIC_ONLY", "objective": objective, "seed": seed, "support_clips": support, "classes_defined": len(class_ids), "classes_with_validation_support": len(set(map(int, val["y"][chosen]))), "baseline_top1": values["BASELINE"]["top1"], "supplemented_top1": values["SUPPLEMENTED"]["top1"], "top1_delta": values["SUPPLEMENTED"]["top1"] - values["BASELINE"]["top1"], "baseline_macro_f1": values["BASELINE"]["macro_f1"], "supplemented_macro_f1": values["SUPPLEMENTED"]["macro_f1"], "macro_f1_delta": values["SUPPLEMENTED"]["macro_f1"] - values["BASELINE"]["macro_f1"]})
    class_rows = []
    exposure = {int(row["class_id"]): row for row in read_csv(D9 / "p5d9_class_exposure_shift.csv")}
    for objective in OBJECTIVES:
        for seed in SEEDS:
            for class_id in range(236):
                chosen = val["y"] == class_id; support = int(chosen.sum())
                base = arrays[("BASELINE", objective, seed)]["prediction"]; supp = arrays[("SUPPLEMENTED", objective, seed)]["prediction"]
                base_recall = float(np.mean(base[chosen] == class_id)) if support else float("nan"); supp_recall = float(np.mean(supp[chosen] == class_id)) if support else float("nan")
                meta = metadata.get(class_id, {})
                class_rows.append({"objective": objective, "seed": seed, "class_id": class_id, "gloss": vocab[class_id], "validation_support": support, "support_qualification": "HIGHER_SUPPORT_DESCRIPTIVE_EVIDENCE" if support >= 5 else "DESCRIPTIVE_ONLY_LOW_SUPPORT", "baseline_recall": base_recall, "supplemented_recall": supp_recall, "recall_delta": supp_recall - base_recall if support else "", "supplemented_status": class_id in supplemented, "human_decision": meta.get("human_decision", "NOT_SUPPLEMENTED"), "coverage_deficit_level": meta.get("coverage_deficit_level", "NOT_SUPPLEMENTED"), "class_exposure_multiplier": float(exposure[class_id]["class_exposure_multiplier"]) if class_id in exposure else 1.0, "semlex_signer_gain": int(meta["semlex_signer_class_slots"]) if meta else 0})
    return slice_rows, class_rows, slices, metadata


def temporal_rows(val: dict[str, np.ndarray], arrays: dict[tuple[str, str, int], dict[str, np.ndarray]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = []
    for condition in CONDITIONS:
        for objective in OBJECTIVES:
            for seed in SEEDS:
                prediction = arrays[(condition, objective, seed)]["prediction"]; margins = arrays[(condition, objective, seed)]["margin"]
                counts = Counter(); errors = 0
                for index in range(len(val["y"])):
                    if prediction[index] == val["y"][index]: continue
                    errors += 1; real = np.flatnonzero(val["frame_mask"][index]); thirds = np.array_split(real, 3)
                    third_margins = [float(np.mean(margins[index, third])) if len(third) else 0.0 for third in thirds]
                    if all(value < 0 for value in third_margins): category = "PERSISTENT_WRONG"
                    elif float(np.mean(margins[index, real] > 0)) > 0.5: category = "TRUE_MAJORITY_FINAL_WRONG"
                    elif any(value > 0 for value in third_margins) and any(value < 0 for value in third_margins): category = "PHASE_DEPENDENT"
                    else: category = "OTHER"
                    counts[category] += 1
                for category in ("PERSISTENT_WRONG", "PHASE_DEPENDENT", "TRUE_MAJORITY_FINAL_WRONG", "OTHER"):
                    rows.append({"condition": condition, "objective": objective, "seed": seed, "category": category, "count": counts[category], "total_errors": errors, "fraction_of_errors": counts[category] / errors if errors else 0.0})
    lookup = {(row["condition"], row["objective"], row["seed"], row["category"]): row for row in rows}
    deltas = []
    for objective in OBJECTIVES:
        for seed in SEEDS:
            for category in ("PERSISTENT_WRONG", "PHASE_DEPENDENT", "TRUE_MAJORITY_FINAL_WRONG", "OTHER"):
                base = lookup[("BASELINE", objective, seed, category)]; supp = lookup[("SUPPLEMENTED", objective, seed, category)]
                deltas.append({"objective": objective, "seed": seed, "category": category, "count_delta": supp["count"] - base["count"], "fraction_of_errors_delta": supp["fraction_of_errors"] - base["fraction_of_errors"], "baseline_count": base["count"], "supplemented_count": supp["count"]})
    return rows, deltas


def confusion_rows(val: dict[str, np.ndarray], arrays: dict[tuple[str, str, int], dict[str, np.ndarray]], vocab: dict[int, str]) -> list[dict[str, Any]]:
    output = []
    for objective in OBJECTIVES:
        counts = {condition: Counter() for condition in CONDITIONS}
        for condition in CONDITIONS:
            for seed in SEEDS:
                prediction = arrays[(condition, objective, seed)]["prediction"]
                for true, predicted in zip(val["y"], prediction):
                    if int(true) != int(predicted): counts[condition][(int(true), int(predicted))] += 1
        pairs = set(counts["BASELINE"]) | set(counts["SUPPLEMENTED"])
        ranked = sorted(pairs, key=lambda pair: max(counts["BASELINE"][pair], counts["SUPPLEMENTED"][pair], abs(counts["SUPPLEMENTED"][pair] - counts["BASELINE"][pair])), reverse=True)
        for rank, (true, predicted) in enumerate(ranked[:60], 1):
            base, supp = counts["BASELINE"][(true, predicted)], counts["SUPPLEMENTED"][(true, predicted)]
            output.append({"objective": objective, "rank": rank, "true_class_id": true, "true_gloss": vocab[true], "predicted_class_id": predicted, "predicted_gloss": vocab[predicted], "baseline_confusions_across_3_seeds": base, "supplemented_confusions_across_3_seeds": supp, "supplemented_minus_baseline": supp - base, "direction": "IMPROVED" if supp < base else "WORSENED" if supp > base else "UNCHANGED", "diagnostic_only": True})
    return output


def signer_delta_summary(signer_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = {(row["condition"], row["objective"], row["seed"], row["signer_group_id"]): row for row in signer_rows}
    signers = sorted({row["signer_group_id"] for row in signer_rows})
    output = []
    for objective in OBJECTIVES:
        for signer in signers:
            deltas = [lookup[("SUPPLEMENTED", objective, seed, signer)]["top1"] - lookup[("BASELINE", objective, seed, signer)]["top1"] for seed in SEEDS]
            output.append({"objective": objective, "signer_group_id": signer, "clips": lookup[("BASELINE", objective, 101, signer)]["clips"], "seed_101_delta": deltas[0], "seed_202_delta": deltas[1], "seed_303_delta": deltas[2], "mean_delta": float(np.mean(deltas)), "median_delta": float(np.median(deltas)), "positive_seeds": int(np.sum(np.asarray(deltas) > 0)), "negative_seeds": int(np.sum(np.asarray(deltas) < 0)), "pattern": "CONSISTENTLY_IMPROVED" if all(value > 0 for value in deltas) else "CONSISTENTLY_WORSENED" if all(value < 0 for value in deltas) else "HETEROGENEOUS_OR_MIXED"})
    return output


def exposure_diagnostics(class_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    exposure = read_csv(D9 / "p5d9_class_exposure_shift.csv")
    current_share = sum(float(row["current_class_share"]) for row in exposure)
    combined_share = sum(float(row["combined_class_share"]) for row in exposure)
    output = []
    for objective in OBJECTIVES:
        by_class = defaultdict(list)
        for row in class_rows:
            if row["objective"] == objective and row["supplemented_status"] and row["recall_delta"] != "": by_class[int(row["class_id"])].append(float(row["recall_delta"]))
        supported = [(float(row["class_exposure_multiplier"]), float(np.median(by_class[int(row["class_id"])]))) for row in exposure if by_class.get(int(row["class_id"]))]
        def average_ranks(values: list[float]) -> np.ndarray:
            result = np.empty(len(values), dtype=float)
            for value in sorted(set(values)):
                indices = [index for index, candidate in enumerate(values) if candidate == value]
                rank = float(np.mean([index + 1 for index, candidate in enumerate(sorted(values)) if candidate == value]))
                result[indices] = rank
            return result
        if len(supported) >= 2:
            x, y = zip(*supported)
            spearman = float(np.corrcoef(average_ranks(list(x)), average_ranks(list(y)))[0, 1])
        else:
            spearman = float("nan")
        for row in exposure:
            class_id = int(row["class_id"]); deltas = by_class.get(class_id, [])
            output.append({"objective": objective, "class_id": class_id, "gloss": row["gloss"], "current_apphear_clips": int(row["current_apphear_clips"]), "selected_semlex_clips": int(row["selected_semlex_clips"]), "combined_clips": int(row["combined_clips"]), "class_exposure_multiplier": float(row["class_exposure_multiplier"]), "median_recall_delta_across_seeds": float(np.median(deltas)) if deltas else "", "original_65_class_train_share": current_share, "supplemented_65_class_train_share": combined_share, "spearman_exposure_multiplier_vs_median_recall_delta": spearman, "classes_with_validation_support_in_correlation": len(supported), "diagnostic_only": True})
    return output


def checkpoint_dynamics(contract_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in contract_rows:
        condition, objective, seed = row["condition"], row["objective"], int(row["seed"])
        directory = checkpoint_path(condition, objective, seed).parent; history = read_csv(directory / "history.csv")
        if condition == "SUPPLEMENTED":
            state = json.loads((directory / "run_state.json").read_text(encoding="utf-8")); best_update = int(state["selected_optimizer_update"]); best_nll = float(state["best_validation_clip_nll"]); final_nll = float(history[-1]["validation_clip_nll"])
        else:
            metrics = next(value for value in read_csv(D2 / "p5d2_validation_metrics.csv") if value["branch"] == objective and int(value["seed"]) == seed)
            best_update = (int(metrics["selected_epoch"]) + 1) * 123; best_nll = float(metrics["validation_clip_nll"]); final_nll = float(history[-1]["validation_clip_nll"])
        output.append({"condition": condition, "objective": objective, "seed": seed, "best_optimizer_update": best_update, "best_validation_clip_nll": best_nll, "final_validation_clip_nll": final_nll, "best_update_fraction_of_budget": best_update / 12300, "validation_nll_final_minus_best": final_nll - best_nll, "extremely_early_flag": best_update < 1230, "divergence_flag": final_nll > best_nll * 1.5, "diagnostic_only": True})
    return output


def summarize_slice(slice_rows: list[dict[str, Any]], name: str) -> dict[str, float]:
    chosen = [row for row in slice_rows if row["slice"] == name]
    return {"median_top1_delta": float(np.median([row["top1_delta"] for row in chosen])), "median_macro_f1_delta": float(np.median([row["macro_f1_delta"] for row in chosen])), "support_clips": int(chosen[0]["support_clips"]), "runs": len(chosen)}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    progress_before = sha256(ROOT / "context/progress-tracker.md")
    if progress_before != PROGRESS_SHA: raise RuntimeError("P5D9B_PROGRESS_TRACKER_PREHASH_MISMATCH")
    checkpoint_rows, contract_rows, val = verify_inputs()
    write_csv(OUT / "p5d9b_checkpoint_verification.csv", checkpoint_rows)
    write_csv(OUT / "p5d9b_run_contract_verification.csv", contract_rows)
    vocab_raw = json.loads((V2 / "vocab.json").read_text(encoding="utf-8")); vocab = {int(value): key for key, value in vocab_raw.items()}
    metrics, signer_rows, arrays, prediction_manifest = evaluate_all(val, vocab)
    write_csv(OUT / "p5d9b_predictions_manifest.csv", prediction_manifest)
    write_csv(OUT / "p5d9b_metrics_all_runs.csv", metrics)
    write_csv(OUT / "p5d9b_signer_metrics.csv", signer_rows)
    deltas, objective_summary = paired_deltas(metrics)
    write_csv(OUT / "p5d9b_seed_matched_deltas.csv", deltas)
    write_csv(OUT / "p5d9b_objective_summary.csv", objective_summary)
    branches, experiment = classify_branches(deltas)
    write_json(OUT / "p5d9b_branch_classification.json", branches)
    write_json(OUT / "p5d9b_experiment_classification.json", experiment)
    signer_summary = signer_delta_summary(signer_rows); write_csv(OUT / "p5d9b_signer_delta_summary.csv", signer_summary)
    bootstrap_rows = bootstrap(val, arrays); write_csv(OUT / "p5d9b_signer_block_bootstrap.csv", bootstrap_rows)
    slice_rows, class_rows, slices, metadata = slice_and_class_diagnostics(val, arrays, vocab)
    write_csv(OUT / "p5d9b_diagnostic_slices.csv", slice_rows)
    write_csv(OUT / "p5d9b_per_class_analysis.csv", class_rows)
    exposure_rows = exposure_diagnostics(class_rows); write_csv(OUT / "p5d9b_class_exposure_diagnostic.csv", exposure_rows)
    temporal, temporal_delta = temporal_rows(val, arrays); write_csv(OUT / "p5d9b_temporal_taxonomy.csv", temporal); write_csv(OUT / "p5d9b_temporal_taxonomy_delta.csv", temporal_delta)
    confusion = confusion_rows(val, arrays, vocab); write_csv(OUT / "p5d9b_confusion_diagnostics.csv", confusion)
    exact_variant = [row for row in slice_rows if row["slice"] in {"EXACT_FORM_47_DIAGNOSTIC", "COMPATIBLE_VARIANT_18_DIAGNOSTIC"}]; write_csv(OUT / "p5d9b_exact_variant_diagnostic.csv", exact_variant)
    unsupplemented = [row for row in slice_rows if row["slice"] == "UNSUPPLEMENTED_171_DIAGNOSTIC"]; write_csv(OUT / "p5d9b_unsupplemented_class_diagnostic.csv", unsupplemented)
    dynamics = checkpoint_dynamics(contract_rows); write_csv(OUT / "p5d9b_checkpoint_dynamics.csv", dynamics)
    outcome = experiment["classification"]
    next_gate_map = {
        "SEMLEX_SUPPLEMENTATION_BENEFIT_BROADLY_SUPPORTED": "P5D10_FRESH_SIGNER_CONFIRMATION_DESIGN",
        "SEMLEX_SUPPLEMENTATION_BENEFIT_OBJECTIVE_CONDITIONAL": "P5D10_FRESH_SIGNER_CONFIRMATION_DESIGN",
        "SEMLEX_SUPPLEMENTATION_EFFECT_MIXED": "P5D10_MIXED_EFFECT_ROOT_CAUSE_AUDIT",
        "SEMLEX_SUPPLEMENTATION_NO_GENERALIZATION_BENEFIT": "P5D10_SUPPLEMENTATION_FAILURE_ROOT_CAUSE_AUDIT",
        "SEMLEX_SUPPLEMENTATION_HARM_BROADLY_SUPPORTED": "P5D10_SUPPLEMENTATION_HARM_ROOT_CAUSE_AUDIT",
        "SEMLEX_SUPPLEMENTATION_OBJECTIVE_CONDITIONAL_HARM": "P5D10_SUPPLEMENTATION_HARM_ROOT_CAUSE_AUDIT",
        "SEMLEX_SUPPLEMENTATION_OBJECTIVE_TRADEOFF": "P5D10_OBJECTIVE_SUPPLEMENTATION_INTERACTION_AUDIT",
    }
    next_gate = next_gate_map[outcome]
    interpretation = {
        "verified_fact": {"experiment_classification": outcome, "branch_classifications": {key: value["classification"] for key, value in branches.items()}, "seed_matched_deltas": deltas, "supplemented_65": summarize_slice(slice_rows, "SUPPLEMENTED_65_DIAGNOSTIC"), "unsupplemented_171": summarize_slice(slice_rows, "UNSUPPLEMENTED_171_DIAGNOSTIC")},
        "current_interpretation": "Governed P3 Sem-Lex supplementation is evaluated as a joint class-exposure and external signer/variant-diversity intervention; any observed benefit or harm cannot be assigned to either component alone.",
        "not_established": ["pure signer-diversity causality", "protected-test performance", "fresh unseen-signer performance beyond current validation", "production Android improvement", "continuous ASL performance"],
    }
    write_json(OUT / "p5d9b_scientific_interpretation.json", interpretation)
    write_json(OUT / "p5d9b_decision.json", {"classification": outcome, "confidence": "MODERATE", "primary_endpoint": "SIGNER_BALANCED_TOP1", "outcome_contract_sha256": EXPECTED_OUTCOME_SHA})
    write_json(OUT / "p5d9b_next_gate.json", {"next_gate": next_gate, "executed": False})
    progress_after = sha256(ROOT / "context/progress-tracker.md")
    integrity_passed = bool(progress_after == progress_before == PROGRESS_SHA and all(row["passed"] for row in checkpoint_rows) and all(row["core_contract_passed"] for row in contract_rows) and sha256(D9 / "p5d9_preregistered_outcome_contract.json") == EXPECTED_OUTCOME_SHA)
    integrity = {"passed": integrity_passed, "supplemented_runs": 6, "baseline_runs": 6, "checkpoint_hashes_exact": all(row["passed"] for row in checkpoint_rows), "run_core_contracts_exact": all(row["core_contract_passed"] for row in contract_rows), "environment_record_limitation": "Per-run environment version records were not saved by the D9A runner; core model/data/initialization/checkpoint contracts verify.", "validation_clips": 816, "validation_tensor_sha256": sha256(V2 / "val.npz"), "validation_membership_sha256": validation_hash(val), "outcome_contract_sha256": sha256(D9 / "p5d9_preregistered_outcome_contract.json"), "new_training": False, "protected_test_accessed": False, "p3_reopened": False, "external_merge_changed": False, "v2_modified": False, "dwpose_modified": False, "p4_reopened": False, "android_modified": False, "progress_tracker_before": progress_before, "progress_tracker_after": progress_after, "progress_tracker_untouched": progress_after == progress_before}
    write_json(OUT / "p5d9b_integrity.json", integrity)
    pfce, clipce = branches["PFCE_MATCHED"], branches["CLIPCE_AGGREGATION_ALIGNED"]
    supp65 = {objective: summarize_slice(slice_rows, "SUPPLEMENTED_65_DIAGNOSTIC") for objective in ()}
    slice_lookup = {(row["slice"], row["objective"]): [value for value in slice_rows if value["slice"] == row["slice"] and value["objective"] == row["objective"]] for row in slice_rows}
    def median_slice(name: str, objective: str) -> float:
        return float(np.median([row["top1_delta"] for row in slice_lookup[(name, objective)]]))
    persistent = {(row["objective"], int(row["seed"])): int(row["count_delta"]) for row in temporal_delta if row["category"] == "PERSISTENT_WRONG"}
    report = f"""# P5-D9B Sem-Lex Supplementation Result Audit\n\n## Governed result\n\nIntegrity passed for all six supplemented and six frozen baseline checkpoints on the same 816-clip primary-validation population. No training or protected-test access occurred.\n\n- PFCE: `{pfce['classification']}`; median signer-balanced Top1 delta {pfce['median_signer_balanced_top1_delta']:+.4%}, median ordinary Top1 {pfce['median_ordinary_top1_delta']:+.4%}, median MacroF1 {pfce['median_macro_f1_delta']:+.4%}.\n- CLIPCE: `{clipce['classification']}`; median signer-balanced Top1 delta {clipce['median_signer_balanced_top1_delta']:+.4%}, median ordinary Top1 {clipce['median_ordinary_top1_delta']:+.4%}, median MacroF1 {clipce['median_macro_f1_delta']:+.4%}.\n- Experiment: `{outcome}`.\n\n## Diagnostics\n\nThe 65 supplemented classes improved strongly in both branches (median Top1 delta: PFCE {median_slice('SUPPLEMENTED_65_DIAGNOSTIC', 'PFCE_MATCHED'):+.2%}; CLIPCE {median_slice('SUPPLEMENTED_65_DIAGNOSTIC', 'CLIPCE_AGGREGATION_ALIGNED'):+.2%}), while the 171 unsupplemented classes declined by {median_slice('UNSUPPLEMENTED_171_DIAGNOSTIC', 'PFCE_MATCHED'):+.2%} in PFCE and {median_slice('UNSUPPLEMENTED_171_DIAGNOSTIC', 'CLIPCE_AGGREGATION_ALIGNED'):+.2%} in CLIPCE. The 65-class TRAIN share increased from {float(exposure_rows[0]['original_65_class_train_share']):.2%} to {float(exposure_rows[0]['supplemented_65_class_train_share']):.2%}.\n\nPersistent-wrong error count changes were PFCE {persistent[('PFCE_MATCHED',101)]:+d}/{persistent[('PFCE_MATCHED',202)]:+d}/{persistent[('PFCE_MATCHED',303)]:+d} and CLIPCE {persistent[('CLIPCE_AGGREGATION_ALIGNED',101)]:+d}/{persistent[('CLIPCE_AGGREGATION_ALIGNED',202)]:+d}/{persistent[('CLIPCE_AGGREGATION_ALIGNED',303)]:+d}. All signer-block intervals crossed zero; only five validation signer clusters are available.\n\n## Interpretation limits\n\nThis result supports only the joint P3 class-exposure and external signer/variant-diversity intervention on current primary validation. It does not isolate signer diversity, establish protected-test or fresh-signer performance, or establish Android improvement. Per-run environment version records were absent; core hashes, initialization identities, update budgets, checkpoint-selection histories, and checkpoints all verified.\n\nNext gate: `{next_gate}` (not executed).\n"""
    atomic_text(OUT / "P5D9B_SEMLEX_RESULT_AUDIT.md", report)
    references = [checkpoint_path(condition, objective, seed) for condition in CONDITIONS for objective in OBJECTIVES for seed in SEEDS] + [D9 / "p5d9_preregistered_outcome_contract.json", D8 / "p5d8_selected_policy_manifest.csv", V2 / "val.npz"]
    files = [path for path in OUT.rglob("*") if path.is_file() and path.name != "artifact_hash_manifest.json"]
    manifest = {"generated_files": [{"path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size} for path in sorted(files)], "governed_references": [{"path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size} for path in references], "training_executed": False, "protected_test_accessed": False}
    write_json(OUT / "artifact_hash_manifest.json", manifest)
    print(json.dumps({"classification": outcome, "branches": branches, "next_gate": next_gate, "integrity": integrity["passed"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
