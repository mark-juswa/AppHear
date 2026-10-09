"""P5-D10B terminal secondary confirmation on frozen PFCE checkpoints.

This module has two explicit phases. ``prepare`` freezes and hashes all
pre-inference contracts after verifying checkpoints and the governed test
population. ``evaluate`` performs inference only when those frozen gates pass.
It contains no optimizer or training code.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from model import p5d2_temporal_objective_ablation as d2


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/recognition_upgrade/p5_representation_v2"
D2 = BASE / "p5d2_temporal_objective_ablation_01"
D8 = BASE / "p5d8_supplementation_design_01"
D9 = BASE / "p5d9_semlex_supplementation_01"
D10A = BASE / "p5d10a_final_holdout_audit_01"
OUT = BASE / "p5d10b_secondary_confirmation_01"
V2 = BASE / "p5b_migration_01/dataset"
TEST = V2 / "test.npz"
PROGRESS = ROOT / "context/progress-tracker.md"
SEEDS = (101, 202, 303)
CONDITIONS = ("BASELINE", "P3_SUPPLEMENTED")
EXPECTED_TEST_FILE_SHA = "a0a7c46803b20ca984d08dd8ce80b8aab24c561333d14fd2538e7b415c4a0518"
EXPECTED_MEMBERSHIP_SHA = "53a216024ed2cefe2ac0809a10bf18efb9c3ff00a6485f86cf99d66557844a32"
EXPECTED_PROGRESS_SHA = "12cf08f81959a413a60aa1f869615a24485a41ee3d796e61fce7489ae5c480cf"
EXPECTED_CHECKPOINTS = {
    ("BASELINE", 101): "31e0ce88c95add99138f68588406892e29dfb8e1d14e780bf49667cf74a2c7a7",
    ("BASELINE", 202): "6e76e951b5049ea3bac8b60f97f41fe9545a58b3b01fd6997bafece647a2121d",
    ("BASELINE", 303): "8986110ae5a97ca571bbda986b9877a22e1d6a77cc5d62c7bbd36b7f4ea88057",
    ("P3_SUPPLEMENTED", 101): "ac51c2d711092a6e3de825331f66816487b431a4e9de2354fd7c54a5a2bed258",
    ("P3_SUPPLEMENTED", 202): "a541dab88b0209ad0bffd2285b5000f0f3c36928b1df3c9d472f772f144ce5c3",
    ("P3_SUPPLEMENTED", 303): "82055daf5950e1e31a1707222bc479299cbd3a6a376dd0a9af111d72a7a3b309",
}
BOOTSTRAP_BASE_SEED = 51010
EPSILON = 1e-7


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def membership_sha(sample_ids: Iterable[str]) -> str:
    return hashlib.sha256("\n".join(map(str, sample_ids)).encode("utf-8")).hexdigest()


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


def checkpoint_path(condition: str, seed: int) -> Path:
    root = D2 if condition == "BASELINE" else D9
    return root / "runs/PFCE_MATCHED" / f"seed_{seed}" / "best.keras"


def load_test() -> dict[str, np.ndarray]:
    with np.load(TEST, allow_pickle=False) as data:
        return {
            "X": np.asarray(data["X"], dtype=np.float32),
            "y": np.asarray(data["y"], dtype=np.int32),
            "frame_mask": np.asarray(data["frame_mask"], dtype=bool),
            "sample_ids": np.asarray(data["sample_ids"]).astype(str),
            "signers": np.asarray(data["signer_group_ids"]).astype(str),
        }


def macro_f1(y: np.ndarray, prediction: np.ndarray, class_ids: Iterable[int]) -> float:
    values: list[float] = []
    for class_id in class_ids:
        true = y == class_id
        predicted = prediction == class_id
        tp = int(np.sum(true & predicted))
        fp = int(np.sum(~true & predicted))
        fn = int(np.sum(true & ~predicted))
        denominator = 2 * tp + fp + fn
        values.append(2 * tp / denominator if denominator else 0.0)
    return float(np.mean(values)) if values else 0.0


def verify_checkpoints() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        for seed in SEEDS:
            path = checkpoint_path(condition, seed)
            actual = sha256(path) if path.is_file() else "MISSING"
            expected = EXPECTED_CHECKPOINTS[(condition, seed)]
            rows.append({
                "condition": condition,
                "objective": "PFCE_MATCHED",
                "seed": seed,
                "checkpoint_path": str(path.resolve()),
                "expected_sha256": expected,
                "actual_sha256": actual,
                "passed": actual == expected,
            })
    return rows


def verify_test(data: dict[str, np.ndarray]) -> dict[str, Any]:
    x, y, mask = data["X"], data["y"], data["frame_mask"]
    quartets = x[:, :, :236].reshape(len(x), 96, 59, 4)
    observed = x[:, :, 236:238]
    train = d2.load_split("train")
    val = d2.load_split("val")
    manifest_membership = membership_sha(data["sample_ids"].tolist())
    checks = {
        "rows_exact": len(y) == 2620,
        "shape_exact": x.shape == (2620, 96, 238),
        "dtype_float32": x.dtype == np.float32,
        "classes_exact": len(set(map(int, y))) == 236 and sorted(set(map(int, y))) == list(range(236)),
        "signers_exact": len(set(data["signers"].tolist())) == 11,
        "membership_sha_exact": manifest_membership == EXPECTED_MEMBERSHIP_SHA,
        "feature_tensor_sha_exact": sha256(TEST) == EXPECTED_TEST_FILE_SHA,
        "finite": bool(np.isfinite(x).all()),
        "mask_shape": mask.shape == (2620, 96),
        "compact_masks": bool(np.all(np.diff(mask.astype(np.int8), axis=1) <= 0)),
        "nonempty_masks": bool(np.all(mask.sum(axis=1) > 0)),
        "zero_tail_padding": bool(np.count_nonzero(x[~mask]) == 0),
        "labels_in_range": bool(np.all((y >= 0) & (y < 236))),
        "sample_ids_unique": len(set(data["sample_ids"].tolist())) == 2620,
        "observed_flags_binary": bool(np.isin(observed, (0.0, 1.0)).all()),
        "invalid_landmarks_zero": bool(np.count_nonzero(quartets[..., :3][quartets[..., 3] == 0]) == 0),
        "train_signer_overlap_zero": not bool(set(data["signers"]) & set(train["signers"].astype(str))),
        "val_signer_overlap_zero": not bool(set(data["signers"]) & set(val["signers"].astype(str))),
        "train_sample_overlap_zero": not bool(set(data["sample_ids"]) & set(train["sample_ids"].astype(str))),
        "val_sample_overlap_zero": not bool(set(data["sample_ids"]) & set(val["sample_ids"].astype(str))),
    }
    selected = read_csv(D8 / "p5d8_selected_policy_manifest.csv")
    supplemented = {int(row["apphear_class_id"]) for row in selected}
    checks["supplemented_65_exact"] = len(supplemented) == 65 and supplemented <= set(map(int, y))
    checks["unsupplemented_171_exact"] = len(set(range(236)) - supplemented) == 171 and (set(range(236)) - supplemented) <= set(map(int, y))
    overlap = read_csv(D10A / "p5d10a_sample_overlap_audit.csv")
    primary_overlap = [row for row in overlap if row["population_name"] == "CANONICAL_PRIMARY_TEST_236"]
    checks["raw_media_overlap_zero"] = bool(primary_overlap) and all(int(row["raw_video_sha256_overlap"]) == 0 for row in primary_overlap)
    checks["derived_feature_overlap_zero"] = bool(primary_overlap) and all(int(row["derived_feature_overlap"]) == 0 for row in primary_overlap)
    return {
        "population": "CANONICAL_PRIMARY_TEST_236",
        "representation": "DWPOSE_REPRESENTATION_V2_238",
        "shape": list(x.shape),
        "membership_sha256": manifest_membership,
        "feature_tensor_sha256": sha256(TEST),
        "rows": len(y),
        "classes": len(set(map(int, y))),
        "signers": len(set(data["signers"].tolist())),
        "checks": checks,
        "passed": all(checks.values()),
        "model_inference_executed": False,
    }


def prepare() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "predictions").exists():
        raise RuntimeError("P5D10B_PREPARE_REFUSES_AFTER_PREDICTIONS_EXIST")
    reconciliation = """# P5-D10B Pre-inference Reconciliation

This bookkeeping correction was frozen before D10B inference. It does not change any D10A scientific classification.

## Signer wording

`SUPPLEMENT_VALIDATION_STRESS` and `REUSED_POSITIVE_DIAGNOSTIC` are **development-exposed, signer-disjoint partial-vocabulary diagnostics**. Their exact source-aware audit found zero current TRAIN/VAL signer overlap. They remain unsuitable for full-vocabulary final confirmation because they are partial-vocabulary and development-exposed.

## Protected clean replay exposure

The conservative final exposure label is `EXPOSURE_NOT_RESOLVED_NO_EVALUATION_ARTIFACT_FOUND`. No evaluation artifact was found, but pristine status is not proven. Independently, the population has only 3 classes, 3 signers, and one TRAIN-overlapping signer, so it cannot support full-vocabulary signer-independent confirmation.
"""
    atomic_text(OUT / "p5d10b_preinference_reconciliation.md", reconciliation)
    checkpoint_rows = verify_checkpoints()
    write_csv(OUT / "p5d10b_checkpoint_verification.csv", checkpoint_rows)
    if not all(row["passed"] for row in checkpoint_rows):
        raise RuntimeError("P5D10B_BLOCKED_CHECKPOINT_INTEGRITY")
    test = load_test()
    test_verification = verify_test(test)
    write_json(OUT / "p5d10b_test_population_verification.json", test_verification)
    if not test_verification["passed"]:
        raise RuntimeError("P5D10B_BLOCKED_TEST_POPULATION_INTEGRITY")
    contract = {
        "status": "FROZEN_BEFORE_INFERENCE",
        "evaluation_status": "SECONDARY_CONFIRMATION_ONLY",
        "historical_exposure": "DEVELOPMENT_EXPOSED_NOT_FINAL_HOLDOUT",
        "population": "CANONICAL_PRIMARY_TEST_236",
        "candidate": "PFCE_MATCHED + P3_SEMLEX",
        "comparator": "PFCE_MATCHED BASELINE",
        "candidate_selection_source": "P5-D9B VALIDATION RESULT",
        "test_used_for_candidate_selection": False,
        "clipce_status": "RESEARCH_DIAGNOSTIC_NOT_FINAL_CANDIDATE",
        "seeds": list(SEEDS),
        "design": "THREE_MATCHED_SEED_PAIRS_NO_ENSEMBLING_NO_SEED_SELECTION",
        "aggregation": "per-frame probabilities -> masked arithmetic mean over real frames -> clip probability -> argmax",
        "primary_endpoint": "SIGNER_BALANCED_TOP1_DELTA_CANDIDATE_MINUS_BASELINE",
        "bootstrap": {"replicates": 10000, "cluster": "signer_group_id", "base_seed": BOOTSTRAP_BASE_SEED, "seed_formula": "base_seed + matched_model_seed"},
        "required_slices": ["FULL_236", "P3_SUPPLEMENTED_65", "UNSUPPLEMENTED_171", "HUMAN_EXACT_45", "PRIOR_METADATA_EXACT_2", "GOVERNED_EXACT_COMBINED_47", "COMPATIBLE_VARIANT_18", "BY_SIGNER"],
        "full_vocab_rules": {
            "SECONDARY_FULL_VOCAB_BENEFIT_DIRECTIONALLY_SUPPORTED": "median signer-balanced Top1 > 0; at least 2/3 seeds positive; median ordinary Top1 >= 0; median MacroF1 >= 0",
            "SECONDARY_FULL_VOCAB_EFFECT_MIXED": "signer-balanced, ordinary Top1, MacroF1, or seed directions materially conflict",
            "SECONDARY_FULL_VOCAB_BENEFIT_NOT_REPRODUCED": "median signer-balanced Top1 <= 0; fewer than 2/3 seeds improve; no coherent secondary pattern",
            "SECONDARY_FULL_VOCAB_HARM_DIRECTIONALLY_SUPPORTED": "median signer-balanced Top1 < 0; at least 2/3 seeds negative; median ordinary Top1 or MacroF1 declines",
        },
        "redistribution_rules": {
            "REDISTRIBUTION_NOT_REPRODUCED_BROADENED_BENEFIT": "supplemented-65 median Top1 > 0 and unsupplemented-171 median Top1 >= 0",
            "REDISTRIBUTION_REPRODUCED": "supplemented-65 median Top1 > 0 and unsupplemented-171 median Top1 < 0",
            "SUPPLEMENTED_CLASS_GAIN_NOT_REPRODUCED": "supplemented-65 median Top1 <= 0",
            "REDISTRIBUTION_PATTERN_MIXED": "seed/slice directions prevent a coherent classification",
        },
        "terminal_evidence": True,
        "automatic_retraining_authorized": False,
        "automatic_new_experiment_authorized": False,
    }
    contract_path = OUT / "p5d10b_secondary_confirmation_outcome_contract.json"
    write_json(contract_path, contract)
    freeze = {
        "contract_sha256": sha256(contract_path),
        "checkpoint_verification_sha256": sha256(OUT / "p5d10b_checkpoint_verification.csv"),
        "test_verification_sha256": sha256(OUT / "p5d10b_test_population_verification.json"),
        "reconciliation_sha256": sha256(OUT / "p5d10b_preinference_reconciliation.md"),
        "progress_tracker_sha256": sha256(PROGRESS),
        "predictions_existed_when_frozen": False,
    }
    write_json(OUT / "p5d10b_preinference_freeze.json", freeze)
    print(json.dumps({"prepared": True, "contract_sha256": freeze["contract_sha256"], "checkpoint_gate": True, "population_gate": True}, indent=2))
    return 0


def assert_frozen() -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    freeze_path = OUT / "p5d10b_preinference_freeze.json"
    if not freeze_path.is_file():
        raise RuntimeError("P5D10B_PREINFERENCE_FREEZE_MISSING")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    paths = {
        "contract_sha256": OUT / "p5d10b_secondary_confirmation_outcome_contract.json",
        "checkpoint_verification_sha256": OUT / "p5d10b_checkpoint_verification.csv",
        "test_verification_sha256": OUT / "p5d10b_test_population_verification.json",
        "reconciliation_sha256": OUT / "p5d10b_preinference_reconciliation.md",
    }
    for key, path in paths.items():
        if sha256(path) != freeze[key]:
            raise RuntimeError(f"P5D10B_FROZEN_ARTIFACT_CHANGED:{key}")
    if sha256(PROGRESS) != freeze["progress_tracker_sha256"]:
        raise RuntimeError("P5D10B_PROGRESS_TRACKER_CHANGED_BEFORE_INFERENCE")
    checkpoints = verify_checkpoints()
    if not all(row["passed"] for row in checkpoints):
        raise RuntimeError("P5D10B_BLOCKED_CHECKPOINT_INTEGRITY")
    test = load_test()
    verification = verify_test(test)
    if not verification["passed"]:
        raise RuntimeError("P5D10B_BLOCKED_TEST_POPULATION_INTEGRITY")
    return test, freeze


def infer_checkpoint(model: Any, data: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    clip_parts: list[np.ndarray] = []
    pf_correct = 0
    pf_total = 0
    for start in range(0, len(data["y"]), 32):
        stop = min(start + 32, len(data["y"]))
        probabilities = np.asarray(model(data["X"][start:stop], training=False), dtype=np.float32)
        mask = data["frame_mask"][start:stop]
        labels = data["y"][start:stop]
        denominator = np.maximum(mask.sum(axis=1, keepdims=True), 1)
        clip = (probabilities.astype(np.float64) * mask[:, :, None]).sum(axis=1) / denominator
        clip_parts.append(clip)
        frame_prediction = probabilities.argmax(axis=2)
        pf_correct += int(np.sum((frame_prediction == labels[:, None]) & mask))
        pf_total += int(mask.sum())
    clip_probability = np.concatenate(clip_parts, axis=0)
    prediction = clip_probability.argmax(axis=1).astype(np.int16)
    top5 = np.argsort(clip_probability, axis=1)[:, -5:].astype(np.int16)
    return clip_probability, prediction, top5, pf_correct / pf_total


def metric_row(condition: str, seed: int, data: dict[str, np.ndarray], arrays: dict[str, np.ndarray], pf_accuracy: float) -> dict[str, Any]:
    y, prediction, clip, top5 = data["y"], arrays["prediction"], arrays["clip"], arrays["top5"]
    signers = sorted(set(data["signers"].tolist()))
    signer_top1 = [float(np.mean(prediction[data["signers"] == signer] == y[data["signers"] == signer])) for signer in signers]
    true_probability = clip[np.arange(len(y)), y]
    return {
        "condition": condition,
        "objective": "PFCE_MATCHED",
        "seed": seed,
        "clips": len(y),
        "signers": len(signers),
        "signer_balanced_top1": float(np.mean(signer_top1)),
        "ordinary_top1": float(np.mean(prediction == y)),
        "macro_f1": macro_f1(y, prediction, range(236)),
        "top5": float(np.mean([int(y[i]) in top5[i] for i in range(len(y))])),
        "clip_nll": float(np.mean(-np.log(np.clip(true_probability, EPSILON, 1.0)))),
        "per_frame_accuracy": float(pf_accuracy),
    }


def signer_rows(condition: str, seed: int, data: dict[str, np.ndarray], arrays: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for signer in sorted(set(data["signers"].tolist())):
        chosen = data["signers"] == signer
        y = data["y"][chosen]
        prediction = arrays["prediction"][chosen]
        output.append({
            "condition": condition, "objective": "PFCE_MATCHED", "seed": seed,
            "signer_group_id": signer, "clips": int(chosen.sum()),
            "top1": float(np.mean(prediction == y)),
            "macro_f1": macro_f1(y, prediction, sorted(set(map(int, y)))),
            "mean_true_class_probability": float(np.mean(arrays["clip"][chosen][np.arange(len(y)), y])),
        })
    return output


def slice_sets() -> dict[str, set[int]]:
    rows = read_csv(D8 / "p5d8_selected_policy_manifest.csv")
    supplemented = {int(row["apphear_class_id"]) for row in rows}
    human_exact = {int(row["apphear_class_id"]) for row in rows if row["human_lexical_decision"] == "ACCEPT_EXACT_FORM"}
    metadata_exact = {int(row["apphear_class_id"]) for row in rows if row["human_lexical_decision"] == "ACCEPT_METADATA_EXACT"}
    compatible = {int(row["apphear_class_id"]) for row in rows if row["human_lexical_decision"] == "ACCEPT_COMPATIBLE_VARIANT"}
    if (len(supplemented), len(human_exact), len(metadata_exact), len(compatible)) != (65, 45, 2, 18):
        raise RuntimeError("P5D10B_CORRECTED_TAXONOMY_MISMATCH")
    return {
        "FULL_236": set(range(236)),
        "P3_SUPPLEMENTED_65": supplemented,
        "UNSUPPLEMENTED_171": set(range(236)) - supplemented,
        "HUMAN_EXACT_45": human_exact,
        "PRIOR_METADATA_EXACT_2": metadata_exact,
        "GOVERNED_EXACT_COMBINED_47": human_exact | metadata_exact,
        "COMPATIBLE_VARIANT_18": compatible,
    }


def compute_slice_rows(data: dict[str, np.ndarray], arrays: dict[tuple[str, int], dict[str, np.ndarray]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for name, ids in slice_sets().items():
        selected = np.isin(data["y"], sorted(ids))
        y = data["y"][selected]
        for seed in SEEDS:
            values: dict[str, dict[str, float]] = {}
            for condition in CONDITIONS:
                prediction = arrays[(condition, seed)]["prediction"][selected]
                values[condition] = {
                    "top1": float(np.mean(prediction == y)),
                    "macro_f1": macro_f1(y, prediction, sorted(ids)),
                }
            output.append({
                "slice": name, "seed": seed, "classes_defined": len(ids), "support_clips": int(selected.sum()),
                "classes_with_test_support": len(set(map(int, y))),
                "baseline_top1": values["BASELINE"]["top1"],
                "supplemented_top1": values["P3_SUPPLEMENTED"]["top1"],
                "top1_delta": values["P3_SUPPLEMENTED"]["top1"] - values["BASELINE"]["top1"],
                "baseline_macro_f1": values["BASELINE"]["macro_f1"],
                "supplemented_macro_f1": values["P3_SUPPLEMENTED"]["macro_f1"],
                "macro_f1_delta": values["P3_SUPPLEMENTED"]["macro_f1"] - values["BASELINE"]["macro_f1"],
            })
    return output


def bootstrap(data: dict[str, np.ndarray], arrays: dict[tuple[str, int], dict[str, np.ndarray]], deltas: dict[int, dict[str, float]]) -> list[dict[str, Any]]:
    signers = sorted(set(data["signers"].tolist()))
    indices = {signer: np.flatnonzero(data["signers"] == signer) for signer in signers}
    output: list[dict[str, Any]] = []
    for seed in SEEDS:
        base = arrays[("BASELINE", seed)]["prediction"]
        supp = arrays[("P3_SUPPLEMENTED", seed)]["prediction"]
        signer_delta = {signer: float(np.mean(supp[idx] == data["y"][idx]) - np.mean(base[idx] == data["y"][idx])) for signer, idx in indices.items()}
        bootstrap_seed = BOOTSTRAP_BASE_SEED + seed
        rng = np.random.Generator(np.random.PCG64(bootstrap_seed))
        values = {name: np.empty(10000) for name in ("signer_balanced_top1", "ordinary_top1", "macro_f1")}
        for replicate in range(10000):
            draw = [str(item) for item in rng.choice(signers, len(signers), replace=True)]
            chosen = np.concatenate([indices[signer] for signer in draw])
            values["signer_balanced_top1"][replicate] = np.mean([signer_delta[signer] for signer in draw])
            values["ordinary_top1"][replicate] = np.mean(supp[chosen] == data["y"][chosen]) - np.mean(base[chosen] == data["y"][chosen])
            values["macro_f1"][replicate] = macro_f1(data["y"][chosen], supp[chosen], range(236)) - macro_f1(data["y"][chosen], base[chosen], range(236))
        for metric, distribution in values.items():
            output.append({
                "seed": seed, "metric": metric,
                "empirical_observed_delta": deltas[seed][f"{metric}_delta"],
                "bootstrap_distribution_mean": float(np.mean(distribution)),
                "ci95_low": float(np.percentile(distribution, 2.5)),
                "ci95_high": float(np.percentile(distribution, 97.5)),
                "replicates": 10000, "cluster_unit": "signer_group_id",
                "bootstrap_seed": bootstrap_seed, "signer_clusters": len(signers),
            })
    return output


def confusion_redistribution(data: dict[str, np.ndarray], arrays: dict[tuple[str, int], dict[str, np.ndarray]]) -> list[dict[str, Any]]:
    supplemented = slice_sets()["P3_SUPPLEMENTED_65"]
    unsupplemented = set(range(236)) - supplemented
    vocab_raw = json.loads((V2 / "vocab.json").read_text(encoding="utf-8"))
    vocab = {int(value): key for key, value in vocab_raw.items()}
    output: list[dict[str, Any]] = []
    for seed in SEEDS:
        base = arrays[("BASELINE", seed)]["prediction"]
        supp = arrays[("P3_SUPPLEMENTED", seed)]["prediction"]
        y = data["y"]
        base_counts = Counter((int(t), int(p)) for t, p in zip(y, base) if int(t) in unsupplemented and int(p) in supplemented and int(t) != int(p))
        supp_counts = Counter((int(t), int(p)) for t, p in zip(y, supp) if int(t) in unsupplemented and int(p) in supplemented and int(t) != int(p))
        newly_worsened = Counter((int(y[i]), int(supp[i])) for i in range(len(y)) if int(y[i]) in unsupplemented and int(supp[i]) in supplemented and base[i] == y[i] and supp[i] != y[i])
        pairs = sorted(set(base_counts) | set(supp_counts), key=lambda pair: (supp_counts[pair] - base_counts[pair], newly_worsened[pair]), reverse=True)
        for rank, pair in enumerate(pairs, 1):
            additional = supp_counts[pair] - base_counts[pair]
            if additional <= 0 and newly_worsened[pair] <= 0:
                continue
            true, predicted = pair
            output.append({
                "seed": seed, "rank": rank, "true_unsupplemented_class_id": true,
                "true_gloss": vocab[true], "predicted_supplemented_class_id": predicted,
                "predicted_gloss": vocab[predicted], "baseline_error_events": base_counts[pair],
                "supplemented_error_events": supp_counts[pair], "additional_error_events": additional,
                "newly_worsened_events_baseline_correct": newly_worsened[pair], "diagnostic_only": True,
            })
    return output


def evaluate() -> int:
    import tensorflow as tf

    data, freeze = assert_frozen()
    progress_before = sha256(PROGRESS)
    source_before = {str(TEST.resolve()): sha256(TEST)}
    for condition in CONDITIONS:
        for seed in SEEDS:
            source_before[str(checkpoint_path(condition, seed).resolve())] = sha256(checkpoint_path(condition, seed))
    prediction_dir = OUT / "predictions"
    prediction_dir.mkdir(parents=True, exist_ok=False)
    arrays: dict[tuple[str, int], dict[str, np.ndarray]] = {}
    metric_rows: list[dict[str, Any]] = []
    all_signer_rows: list[dict[str, Any]] = []
    prediction_manifest: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        for seed in SEEDS:
            path = checkpoint_path(condition, seed)
            model = tf.keras.models.load_model(path, safe_mode=False)
            clip, prediction, top5, pf_accuracy = infer_checkpoint(model, data)
            current = {"clip": clip, "prediction": prediction, "top5": top5}
            arrays[(condition, seed)] = current
            metric_rows.append(metric_row(condition, seed, data, current, pf_accuracy))
            all_signer_rows.extend(signer_rows(condition, seed, data, current))
            output = prediction_dir / f"{condition.lower()}__pfce_matched__seed_{seed}.npz"
            np.savez_compressed(output, clip_probabilities=clip.astype(np.float32), predictions=prediction,
                                top5=top5, sample_ids=data["sample_ids"], signer_group_ids=data["signers"],
                                labels=data["y"], frame_mask=data["frame_mask"])
            prediction_manifest.append({
                "condition": condition, "objective": "PFCE_MATCHED", "seed": seed,
                "prediction_path": str(output.resolve()), "prediction_sha256": sha256(output),
                "checkpoint_sha256": sha256(path), "test_membership_sha256": EXPECTED_MEMBERSHIP_SHA,
                "outcome_contract_sha256": freeze["contract_sha256"], "clips": len(data["y"]),
            })
            print(json.dumps({"evaluated": condition, "seed": seed, "clips": len(data["y"])}), flush=True)
            del model
            tf.keras.backend.clear_session()
    write_csv(OUT / "p5d10b_predictions_manifest.csv", prediction_manifest)
    write_csv(OUT / "p5d10b_metrics_all_runs.csv", metric_rows)
    write_csv(OUT / "p5d10b_signer_metrics.csv", all_signer_rows)

    lookup = {(row["condition"], int(row["seed"])): row for row in metric_rows}
    delta_rows: list[dict[str, Any]] = []
    delta_lookup: dict[int, dict[str, float]] = {}
    metric_names = ("signer_balanced_top1", "ordinary_top1", "macro_f1", "top5", "clip_nll", "per_frame_accuracy")
    for seed in SEEDS:
        base, supp = lookup[("BASELINE", seed)], lookup[("P3_SUPPLEMENTED", seed)]
        row = {"objective": "PFCE_MATCHED", "seed": seed}
        for name in metric_names:
            row[f"{name}_delta"] = supp[name] - base[name]
        delta_rows.append(row)
        delta_lookup[seed] = row
    write_csv(OUT / "p5d10b_seed_matched_deltas.csv", delta_rows)
    summary_rows: list[dict[str, Any]] = []
    for name in metric_names:
        values = np.asarray([row[f"{name}_delta"] for row in delta_rows])
        summary_rows.append({
            "objective": "PFCE_MATCHED", "metric": name, "mean_delta": float(np.mean(values)),
            "median_delta": float(np.median(values)), "minimum_delta": float(np.min(values)),
            "maximum_delta": float(np.max(values)), "std_delta": float(np.std(values)),
            "positive_seeds": int(np.sum(values > 0)), "negative_seeds": int(np.sum(values < 0)),
        })
    write_csv(OUT / "p5d10b_objective_summary.csv", summary_rows)

    signer_lookup = {(row["condition"], int(row["seed"]), row["signer_group_id"]): row for row in all_signer_rows}
    signer_summary: list[dict[str, Any]] = []
    for signer in sorted(set(data["signers"].tolist())):
        deltas = [float(signer_lookup[("P3_SUPPLEMENTED", seed, signer)]["top1"]) - float(signer_lookup[("BASELINE", seed, signer)]["top1"]) for seed in SEEDS]
        signer_summary.append({
            "signer_group_id": signer, "clips": signer_lookup[("BASELINE", 101, signer)]["clips"],
            "seed_101_delta": deltas[0], "seed_202_delta": deltas[1], "seed_303_delta": deltas[2],
            "mean_delta": float(np.mean(deltas)), "median_delta": float(np.median(deltas)),
            "positive_seeds": int(np.sum(np.asarray(deltas) > 0)), "negative_seeds": int(np.sum(np.asarray(deltas) < 0)),
            "pattern": "CONSISTENT_IMPROVEMENT" if all(value > 0 for value in deltas) else "CONSISTENT_DECLINE" if all(value < 0 for value in deltas) else "MIXED",
        })
    write_csv(OUT / "p5d10b_signer_delta_summary.csv", signer_summary)
    bootstrap_rows = bootstrap(data, arrays, delta_lookup)
    write_csv(OUT / "p5d10b_signer_block_bootstrap.csv", bootstrap_rows)

    slices = compute_slice_rows(data, arrays)
    write_csv(OUT / "p5d10b_vocabulary_slices.csv", slices)
    exact_variant = [row for row in slices if row["slice"] in {"HUMAN_EXACT_45", "PRIOR_METADATA_EXACT_2", "GOVERNED_EXACT_COMBINED_47", "COMPATIBLE_VARIANT_18"}]
    write_csv(OUT / "p5d10b_exact_variant_diagnostic.csv", exact_variant)
    slice_by_name = {name: [row for row in slices if row["slice"] == name] for name in slice_sets()}
    supp_values = [float(row["top1_delta"]) for row in slice_by_name["P3_SUPPLEMENTED_65"]]
    unsupp_values = [float(row["top1_delta"]) for row in slice_by_name["UNSUPPLEMENTED_171"]]
    supp_median, unsupp_median = float(np.median(supp_values)), float(np.median(unsupp_values))
    if supp_median > 0 and unsupp_median >= 0:
        redistribution = "REDISTRIBUTION_NOT_REPRODUCED_BROADENED_BENEFIT"
    elif supp_median > 0 and unsupp_median < 0:
        redistribution = "REDISTRIBUTION_REPRODUCED"
    elif supp_median <= 0:
        redistribution = "SUPPLEMENTED_CLASS_GAIN_NOT_REPRODUCED"
    else:
        redistribution = "REDISTRIBUTION_PATTERN_MIXED"
    redistribution_rows = [
        {"slice": "P3_SUPPLEMENTED_65", "seed": row["seed"], "top1_delta": row["top1_delta"], "median_across_seeds": supp_median, "classification": redistribution}
        for row in slice_by_name["P3_SUPPLEMENTED_65"]
    ] + [
        {"slice": "UNSUPPLEMENTED_171", "seed": row["seed"], "top1_delta": row["top1_delta"], "median_across_seeds": unsupp_median, "classification": redistribution}
        for row in slice_by_name["UNSUPPLEMENTED_171"]
    ]
    write_csv(OUT / "p5d10b_redistribution_diagnostic.csv", redistribution_rows)
    confusion = confusion_redistribution(data, arrays)
    write_csv(OUT / "p5d10b_confusion_redistribution.csv", confusion)

    sb = np.asarray([row["signer_balanced_top1_delta"] for row in delta_rows])
    ordinary = np.asarray([row["ordinary_top1_delta"] for row in delta_rows])
    macro = np.asarray([row["macro_f1_delta"] for row in delta_rows])
    median_sb, median_ordinary, median_macro = float(np.median(sb)), float(np.median(ordinary)), float(np.median(macro))
    positive, negative = int(np.sum(sb > 0)), int(np.sum(sb < 0))
    if median_sb > 0 and positive >= 2 and median_ordinary >= 0 and median_macro >= 0:
        classification = "SECONDARY_FULL_VOCAB_BENEFIT_DIRECTIONALLY_SUPPORTED"
    elif median_sb < 0 and negative >= 2 and (median_ordinary < 0 or median_macro < 0):
        classification = "SECONDARY_FULL_VOCAB_HARM_DIRECTIONALLY_SUPPORTED"
    elif median_sb <= 0 and positive < 2 and not (median_ordinary > 0 or median_macro > 0):
        classification = "SECONDARY_FULL_VOCAB_BENEFIT_NOT_REPRODUCED"
    else:
        classification = "SECONDARY_FULL_VOCAB_EFFECT_MIXED"

    exposure = {
        "supplemented_classes": 65,
        "current_train_share": 0.2061,
        "p3_train_share": 0.3516,
        "causal_boundary": "The governed P3 supplementation recipe jointly changed class exposure and external signer/variant diversity.",
    }
    write_json(OUT / "p5d10b_class_exposure_context.json", exposure)
    consistent_improvement = sum(row["pattern"] == "CONSISTENT_IMPROVEMENT" for row in signer_summary)
    consistent_decline = sum(row["pattern"] == "CONSISTENT_DECLINE" for row in signer_summary)
    mixed_signers = len(signer_summary) - consistent_improvement - consistent_decline
    exact47 = float(np.median([row["top1_delta"] for row in slice_by_name["GOVERNED_EXACT_COMBINED_47"]]))
    variant18 = float(np.median([row["top1_delta"] for row in slice_by_name["COMPATIBLE_VARIANT_18"]]))
    confusion_additional = sum(max(0, int(row["additional_error_events"])) for row in confusion)
    d9b_reproduced = "YES" if classification == "SECONDARY_FULL_VOCAB_BENEFIT_DIRECTIONALLY_SUPPORTED" and redistribution == "REDISTRIBUTION_REPRODUCED" else "PARTIAL" if classification != "SECONDARY_FULL_VOCAB_BENEFIT_NOT_REPRODUCED" else "NO"
    interpretation = {
        "verified_fact": {
            "classification": classification, "seed_matched_deltas": delta_rows,
            "redistribution_classification": redistribution,
            "supplemented_65_top1_deltas": supp_values, "unsupplemented_171_top1_deltas": unsupp_values,
            "signer_patterns": {"consistent_improvement": consistent_improvement, "consistent_decline": consistent_decline, "mixed": mixed_signers},
        },
        "current_interpretation": "The secondary signer-independent population tests whether the D9B direction reproduces, while retaining the causal boundary that P3 jointly changed class exposure and external signer/variant diversity.",
        "scientific_limitation": "This is secondary confirmation on a development-exposed test population, not a pristine final holdout.",
        "not_established": ["unbiased pristine-holdout performance", "pure signer-diversity causality", "production Android improvement", "continuous ASL performance"],
    }
    write_json(OUT / "p5d10b_scientific_interpretation.json", interpretation)
    decision = {
        "classification": classification, "evaluation_status": "SECONDARY_CONFIRMATION_ONLY",
        "confidence": "MODERATE" if any(float(row["ci95_low"]) <= 0 <= float(row["ci95_high"]) for row in bootstrap_rows if row["metric"] == "signer_balanced_top1") else "HIGH",
        "redistribution_classification": redistribution, "d9b_direction_reproduced": d9b_reproduced,
        "research_cycle_status": "CLOSED_AFTER_D10B", "automatic_next_experiment": "NONE",
    }
    write_json(OUT / "p5d10b_decision.json", decision)
    terminal = {
        "current_research_cycle_closed": True,
        "automatic_retraining_authorized": False,
        "automatic_new_experiment_authorized": False,
        "holdout_status": "SECONDARY_CONFIRMATION_ONLY",
        "future_work_triggered_by_results": "Record any remaining vocabulary redistribution or signer heterogeneity as future-version work; do not tune the current system against this population.",
        "no_code_launch_authorized": True,
    }
    write_json(OUT / "p5d10b_terminal_evidence.json", terminal)

    bootstrap_sb = [row for row in bootstrap_rows if row["metric"] == "signer_balanced_top1"]
    strongest = sorted(confusion, key=lambda row: int(row["additional_error_events"]), reverse=True)[:5]
    strongest_text = ", ".join(f"{row['true_gloss']}->{row['predicted_gloss']} ({int(row['additional_error_events']):+d})" for row in strongest) or "none"
    report = f"""# P5-D10B Secondary Full-Vocabulary Confirmation

## Status

`{classification}` on the development-exposed canonical 236-class test. This is secondary signer-independent confirmation only, never a pristine final-holdout result.

The three matched signer-balanced Top1 deltas were {sb[0]:+.4%}, {sb[1]:+.4%}, and {sb[2]:+.4%}; median {median_sb:+.4%}. Ordinary Top1 median delta was {median_ordinary:+.4%}; MacroF1 median delta was {median_macro:+.4%}.

## Vocabulary redistribution

- 65 supplemented classes: {supp_values[0]:+.4%}, {supp_values[1]:+.4%}, {supp_values[2]:+.4%}; median {supp_median:+.4%}.
- 171 unsupplemented classes: {unsupp_values[0]:+.4%}, {unsupp_values[1]:+.4%}, {unsupp_values[2]:+.4%}; median {unsupp_median:+.4%}.
- Classification: `{redistribution}`.
- Governed exact 47 median Top1 delta: {exact47:+.4%}; compatible variants 18: {variant18:+.4%}.

## Signers and uncertainty

Across 11 signers: {consistent_improvement} consistently improved, {consistent_decline} consistently declined, and {mixed_signers} were mixed. Signer-block intervals are recorded for every seed using 10,000 PCG64 replicates; CI crossing zero is treated as uncertainty, not an automatic failure.

## Confusion diagnostic

Additional unsupplemented-true to supplemented-predicted error events across reported positive pair changes: {confusion_additional}. Strongest pairs: {strongest_text}.

## Scientific boundary

P3 changed the 65-class TRAIN share from 20.61% to 35.16% while adding external signer/variant coverage. D10B does not isolate pure signer-diversity causality. It does not establish pristine-holdout, Android, or continuous-ASL performance. The P5 research cycle is closed; no retraining or automatic next experiment is authorized.
"""
    atomic_text(OUT / "P5D10B_SECONDARY_CONFIRMATION_RESULT.md", report)

    source_after = {path: sha256(Path(path)) for path in source_before}
    progress_after = sha256(PROGRESS)
    contract_unchanged = sha256(OUT / "p5d10b_secondary_confirmation_outcome_contract.json") == freeze["contract_sha256"]
    integrity = {
        "passed": source_after == source_before and progress_after == progress_before == EXPECTED_PROGRESS_SHA and contract_unchanged,
        "six_pfce_checkpoints_exact": all(row["passed"] for row in verify_checkpoints()),
        "baseline_checkpoints": 3, "supplemented_checkpoints": 3,
        "clipce_evaluated": False, "training_performed": False, "checkpoint_mutation": False,
        "seed_selected": False, "ensembling": False, "test_membership_changed": False,
        "test_tensor_changed": sha256(TEST) != EXPECTED_TEST_FILE_SHA,
        "test_rows": 2620, "classes": 236, "signers": 11,
        "train_signer_overlap": 0, "val_signer_overlap": 0, "sample_raw_overlap": 0,
        "p3_changed": False, "pfce_changed": False, "v2_changed": False, "dwpose_changed": False,
        "p4_reopened": False, "android_modified": False,
        "outcome_contract_unchanged_after_predictions": contract_unchanged,
        "source_hashes_before": source_before, "source_hashes_after": source_after,
        "progress_tracker_before": progress_before, "progress_tracker_after": progress_after,
        "progress_tracker_untouched": progress_before == progress_after,
        "temporal_diagnostics": "SKIPPED_TO_AVOID_NONPRIMARY_COMPLEXITY",
    }
    write_json(OUT / "p5d10b_integrity.json", integrity)

    generated = [path for path in OUT.rglob("*") if path.is_file() and path.name != "artifact_hash_manifest.json"]
    manifest = {
        "generated_files": [{"path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size} for path in sorted(generated)],
        "governed_sources": [{"path": path, "sha256": digest} for path, digest in source_after.items()],
        "training_performed": False, "clipce_evaluated": False,
        "evaluation_status": "SECONDARY_CONFIRMATION_ONLY", "research_cycle_closed": True,
    }
    write_json(OUT / "artifact_hash_manifest.json", manifest)
    print(json.dumps({"classification": classification, "redistribution": redistribution, "median_signer_balanced_delta": median_sb, "integrity": integrity["passed"], "research_cycle": "CLOSED_AFTER_D10B"}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "evaluate"))
    args = parser.parse_args()
    return prepare() if args.command == "prepare" else evaluate()


if __name__ == "__main__":
    raise SystemExit(main())
