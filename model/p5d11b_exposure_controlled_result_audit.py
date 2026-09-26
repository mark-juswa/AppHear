"""P5-D11B validation-only audit for exposure-controlled P3.

This module evaluates only the three completed EC_P3 PFCE checkpoints on the
governed 816-clip primary validation population.  Frozen D9B validation
predictions are reused for the PFCE baseline and naive-P3 comparators.  No
test population, optimizer, training data mutation, or model update is used.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from model import p5d2_temporal_objective_ablation as d2

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/recognition_upgrade/p5_representation_v2"
D8 = BASE / "p5d8_supplementation_design_01"
D9B = BASE / "p5d9b_semlex_result_audit_01"
D11 = BASE / "p5d11_exposure_controlled_p3_01"
V2 = BASE / "p5b_migration_01/dataset"
PROGRESS = ROOT / "context/progress-tracker.md"
SEEDS = (101, 202, 303)
CONDITIONS = ("BASELINE", "NAIVE_P3", "EC_P3")
COMPARISONS = ("EC_P3_MINUS_BASELINE", "EC_P3_MINUS_NAIVE_P3")
EXPECTED_VAL_SHA = "627275d03087f49fda65138253425131e35fe9c5cb8ded6a93b914484be5afe2"
EXPECTED_OUTCOME_SHA = "38a427058682249a2c1ae58b561f95e717bf34f1cbc2b563acc0218b0091f009"
EXPECTED_PROGRESS_SHA = "12cf08f81959a413a60aa1f869615a24485a41ee3d796e61fce7489ae5c480cf"


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


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else ["status"]
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def supported_macro_f1(
    labels: np.ndarray, predictions: np.ndarray, class_ids: Iterable[int]
) -> float:
    values: list[float] = []
    for class_id in class_ids:
        actual = labels == class_id
        predicted = predictions == class_id
        true_positive = int(np.sum(actual & predicted))
        false_positive = int(np.sum(~actual & predicted))
        false_negative = int(np.sum(actual & ~predicted))
        denominator = 2 * true_positive + false_positive + false_negative
        values.append(0.0 if denominator == 0 else 2 * true_positive / denominator)
    return float(np.mean(values)) if values else float("nan")


def validation_membership_hash(val: dict[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for index in range(len(val["y"])):
        digest.update(
            f"{val['sample_ids'][index]}|{val['signers'][index]}|{int(val['y'][index])}|".encode()
        )
        digest.update(np.ascontiguousarray(val["frame_mask"][index]).tobytes())
    return digest.hexdigest()


def load_frozen_comparators(
    val: dict[str, np.ndarray],
) -> tuple[dict[tuple[str, int], dict[str, np.ndarray]], list[dict[str, Any]]]:
    manifest = read_csv(D9B / "p5d9b_predictions_manifest.csv")
    lookup = {
        (row["condition"], row["objective"], int(row["seed"])): row
        for row in manifest
    }
    arrays: dict[tuple[str, int], dict[str, np.ndarray]] = {}
    verification: list[dict[str, Any]] = []
    expected_membership = validation_membership_hash(val)
    for condition, old_condition in (("BASELINE", "BASELINE"), ("NAIVE_P3", "SUPPLEMENTED")):
        for seed in SEEDS:
            row = lookup[(old_condition, "PFCE_MATCHED", seed)]
            path = Path(row["prediction_path"])
            hash_exact = sha256(path) == row["prediction_sha256"]
            membership_exact = row["validation_membership_sha256"] == expected_membership
            with np.load(path, allow_pickle=False) as data:
                labels = np.asarray(data["labels"], dtype=np.int32)
                sample_ids = np.asarray(data["sample_ids"]).astype(str)
                frame_mask = np.asarray(data["frame_mask"], dtype=bool)
                values = {
                    "clip": np.asarray(data["clip_probabilities"], dtype=np.float64),
                    "prediction": np.asarray(data["predictions"], dtype=np.int16),
                    "top5": np.asarray(data["top5"], dtype=np.int16),
                    "frame_prediction": np.asarray(data["frame_argmax"], dtype=np.int16),
                }
            content_exact = bool(
                np.array_equal(labels, val["y"])
                and np.array_equal(sample_ids, val["sample_ids"].astype(str))
                and np.array_equal(frame_mask, val["frame_mask"])
            )
            passed = hash_exact and membership_exact and content_exact
            verification.append(
                {
                    "condition": condition,
                    "seed": seed,
                    "artifact": str(path.resolve()),
                    "artifact_sha256": sha256(path),
                    "hash_exact": hash_exact,
                    "validation_membership_exact": membership_exact,
                    "prediction_content_exact": content_exact,
                    "passed": passed,
                }
            )
            if not passed:
                raise RuntimeError(f"P5D11B_FROZEN_COMPARATOR_INTEGRITY:{condition}:{seed}")
            arrays[(condition, seed)] = values
    return arrays, verification


def evaluate_ec(
    val: dict[str, np.ndarray], arrays: dict[tuple[str, int], dict[str, np.ndarray]]
) -> list[dict[str, Any]]:
    import tensorflow as tf

    rows: list[dict[str, Any]] = []
    prediction_dir = D11 / "predictions_d11b"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    membership_sha = validation_membership_hash(val)
    for seed in SEEDS:
        run_dir = D11 / f"runs/EC_P3/PFCE_MATCHED/seed_{seed}"
        checkpoint = run_dir / "best.keras"
        state = json.loads((run_dir / "run_state.json").read_text(encoding="utf-8"))
        contract = json.loads((run_dir / "run_contract.json").read_text(encoding="utf-8"))
        checkpoint_sha = sha256(checkpoint)
        checks = {
            "state_complete": state.get("status") == "COMPLETE",
            "updates_exact": int(state.get("completed_updates", -1)) == 12_300,
            "validation_opportunities_exact": int(
                state.get("validation_opportunities", -1)
            )
            == 100,
            "checkpoint_hash_exact": checkpoint_sha == state.get("checkpoint_sha256"),
            "outcome_contract_exact": contract.get("outcome_contract_sha256")
            == EXPECTED_OUTCOME_SHA,
            "test_access_prohibited": contract.get("test_access") == "PROHIBITED",
        }
        if not all(checks.values()):
            raise RuntimeError(f"P5D11B_EC_RUN_INTEGRITY:{seed}")
        model = tf.keras.models.load_model(checkpoint, safe_mode=False)
        frame = d2.infer_probabilities(model, val["X"])
        denominator = np.maximum(val["frame_mask"].sum(axis=1, keepdims=True), 1)
        clip = (
            frame.astype(np.float64) * val["frame_mask"][:, :, None]
        ).sum(axis=1) / denominator
        prediction = clip.argmax(axis=1).astype(np.int16)
        top5 = np.argsort(clip, axis=1)[:, -5:].astype(np.int16)
        frame_prediction = frame.argmax(axis=2).astype(np.int16)
        output = prediction_dir / f"ec_p3__pfce_matched__seed_{seed}.npz"
        np.savez_compressed(
            output,
            clip_probabilities=clip.astype(np.float32),
            predictions=prediction,
            top5=top5,
            frame_argmax=frame_prediction,
            sample_ids=val["sample_ids"],
            signer_group_ids=val["signers"],
            labels=val["y"],
            frame_mask=val["frame_mask"],
        )
        arrays[("EC_P3", seed)] = {
            "clip": clip,
            "prediction": prediction,
            "top5": top5,
            "frame_prediction": frame_prediction,
        }
        rows.append(
            {
                "condition": "EC_P3",
                "seed": seed,
                "checkpoint_path": str(checkpoint.resolve()),
                "checkpoint_sha256": checkpoint_sha,
                "prediction_path": str(output.resolve()),
                "prediction_sha256": sha256(output),
                "validation_membership_sha256": membership_sha,
                **checks,
                "passed": all(checks.values()),
            }
        )
        del model, frame
        tf.keras.backend.clear_session()
    return rows


def metric_rows(
    val: dict[str, np.ndarray], arrays: dict[tuple[str, int], dict[str, np.ndarray]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    metrics: list[dict[str, Any]] = []
    signer_rows: list[dict[str, Any]] = []
    signers = sorted(set(map(str, val["signers"])))
    for condition in CONDITIONS:
        for seed in SEEDS:
            item = arrays[(condition, seed)]
            true_probability = item["clip"][np.arange(len(val["y"])), val["y"]]
            signer_top1: list[float] = []
            for signer in signers:
                chosen = val["signers"].astype(str) == signer
                top1 = float(np.mean(item["prediction"][chosen] == val["y"][chosen]))
                signer_top1.append(top1)
                class_ids = sorted(set(map(int, val["y"][chosen])))
                signer_rows.append(
                    {
                        "condition": condition,
                        "seed": seed,
                        "signer_group_id": signer,
                        "clips": int(chosen.sum()),
                        "top1": top1,
                        "macro_f1": supported_macro_f1(
                            val["y"][chosen], item["prediction"][chosen], class_ids
                        ),
                        "mean_true_class_probability": float(np.mean(true_probability[chosen])),
                    }
                )
            metrics.append(
                {
                    "condition": condition,
                    "objective": "PFCE_MATCHED",
                    "seed": seed,
                    "validation_clips": len(val["y"]),
                    "ordinary_top1": float(np.mean(item["prediction"] == val["y"])),
                    "signer_balanced_top1": float(np.mean(signer_top1)),
                    "macro_f1": d2.macro_f1(val["y"], item["prediction"]),
                    "top5": float(
                        np.mean(
                            [val["y"][i] in item["top5"][i] for i in range(len(val["y"]))]
                        )
                    ),
                    "clip_nll": float(
                        np.mean(-np.log(np.clip(true_probability, d2.EPSILON, 1.0)))
                    ),
                    "per_frame_accuracy": float(
                        np.sum(
                            (item["frame_prediction"] == val["y"][:, None])
                            * val["frame_mask"]
                        )
                        / val["frame_mask"].sum()
                    ),
                }
            )
    return metrics, signer_rows


def delta_rows(metrics: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lookup = {(row["condition"], int(row["seed"])): row for row in metrics}
    names = (
        "signer_balanced_top1",
        "ordinary_top1",
        "macro_f1",
        "top5",
        "clip_nll",
        "per_frame_accuracy",
    )
    rows: list[dict[str, Any]] = []
    for comparison, reference in (
        ("EC_P3_MINUS_BASELINE", "BASELINE"),
        ("EC_P3_MINUS_NAIVE_P3", "NAIVE_P3"),
    ):
        for seed in SEEDS:
            target = lookup[("EC_P3", seed)]
            base = lookup[(reference, seed)]
            rows.append(
                {
                    "comparison": comparison,
                    "seed": seed,
                    **{f"{name}_delta": target[name] - base[name] for name in names},
                }
            )
    summary: list[dict[str, Any]] = []
    for comparison in COMPARISONS:
        chosen = [row for row in rows if row["comparison"] == comparison]
        for name in names:
            values = np.asarray([row[f"{name}_delta"] for row in chosen], dtype=float)
            summary.append(
                {
                    "comparison": comparison,
                    "metric": name,
                    "mean_delta": float(np.mean(values)),
                    "median_delta": float(np.median(values)),
                    "std_delta": float(np.std(values)),
                    "minimum_delta": float(np.min(values)),
                    "maximum_delta": float(np.max(values)),
                    "positive_seeds": int(np.sum(values > 0)),
                    "negative_seeds": int(np.sum(values < 0)),
                }
            )
    return rows, summary


def slice_rows(
    val: dict[str, np.ndarray],
    arrays: dict[tuple[str, int], dict[str, np.ndarray]],
    supplemented: set[int],
) -> list[dict[str, Any]]:
    slices = {
        "FULL_236": set(range(236)),
        "P3_SUPPLEMENTED_65": supplemented,
        "UNSUPPLEMENTED_171": set(range(236)) - supplemented,
    }
    rows: list[dict[str, Any]] = []
    for name, class_ids in slices.items():
        chosen = np.isin(val["y"], list(class_ids))
        for condition in CONDITIONS:
            for seed in SEEDS:
                prediction = arrays[(condition, seed)]["prediction"]
                rows.append(
                    {
                        "slice": name,
                        "condition": condition,
                        "seed": seed,
                        "support_clips": int(chosen.sum()),
                        "classes_defined": len(class_ids),
                        "top1": float(np.mean(prediction[chosen] == val["y"][chosen])),
                        "macro_f1": supported_macro_f1(
                            val["y"][chosen], prediction[chosen], sorted(class_ids)
                        ),
                    }
                )
    lookup = {(row["slice"], row["condition"], int(row["seed"])): row for row in rows}
    output: list[dict[str, Any]] = []
    for row in rows:
        if row["condition"] != "EC_P3":
            continue
        for comparison, reference in (
            ("EC_P3_MINUS_BASELINE", "BASELINE"),
            ("EC_P3_MINUS_NAIVE_P3", "NAIVE_P3"),
        ):
            base = lookup[(row["slice"], reference, int(row["seed"]))]
            output.append(
                {
                    **row,
                    "comparison": comparison,
                    "reference_top1": base["top1"],
                    "top1_delta": row["top1"] - base["top1"],
                    "reference_macro_f1": base["macro_f1"],
                    "macro_f1_delta": row["macro_f1"] - base["macro_f1"],
                }
            )
    return output


def signer_summaries(signer_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = {
        (row["condition"], int(row["seed"]), row["signer_group_id"]): row
        for row in signer_rows
    }
    signers = sorted({row["signer_group_id"] for row in signer_rows})
    rows: list[dict[str, Any]] = []
    for comparison, reference in (
        ("EC_P3_MINUS_BASELINE", "BASELINE"),
        ("EC_P3_MINUS_NAIVE_P3", "NAIVE_P3"),
    ):
        for signer in signers:
            deltas = [
                lookup[("EC_P3", seed, signer)]["top1"]
                - lookup[(reference, seed, signer)]["top1"]
                for seed in SEEDS
            ]
            rows.append(
                {
                    "comparison": comparison,
                    "signer_group_id": signer,
                    "clips": lookup[("EC_P3", 101, signer)]["clips"],
                    "seed_101_delta": deltas[0],
                    "seed_202_delta": deltas[1],
                    "seed_303_delta": deltas[2],
                    "mean_delta": float(np.mean(deltas)),
                    "median_delta": float(np.median(deltas)),
                    "positive_seeds": int(np.sum(np.asarray(deltas) > 0)),
                    "negative_seeds": int(np.sum(np.asarray(deltas) < 0)),
                    "pattern": "CONSISTENTLY_IMPROVED"
                    if all(value > 0 for value in deltas)
                    else "CONSISTENTLY_DECLINED"
                    if all(value < 0 for value in deltas)
                    else "MIXED",
                }
            )
    return rows


def bootstrap_rows(
    val: dict[str, np.ndarray], arrays: dict[tuple[str, int], dict[str, np.ndarray]]
) -> list[dict[str, Any]]:
    signers = sorted(set(map(str, val["signers"])))
    indices = {
        signer: np.flatnonzero(val["signers"].astype(str) == signer) for signer in signers
    }
    rows: list[dict[str, Any]] = []
    for comparison_index, (comparison, reference) in enumerate(
        (("EC_P3_MINUS_BASELINE", "BASELINE"), ("EC_P3_MINUS_NAIVE_P3", "NAIVE_P3"))
    ):
        for seed in SEEDS:
            target = arrays[("EC_P3", seed)]["prediction"]
            base = arrays[(reference, seed)]["prediction"]
            rng_seed = 1_100_000 + comparison_index * 10_000 + seed
            rng = np.random.Generator(np.random.PCG64(rng_seed))
            ordinary = np.empty(10_000)
            balanced = np.empty(10_000)
            macro = np.empty(10_000)
            signer_delta = {
                signer: float(
                    np.mean(target[index] == val["y"][index])
                    - np.mean(base[index] == val["y"][index])
                )
                for signer, index in indices.items()
            }
            for replicate in range(10_000):
                draw = [str(value) for value in rng.choice(signers, len(signers), replace=True)]
                chosen = np.concatenate([indices[signer] for signer in draw])
                ordinary[replicate] = np.mean(target[chosen] == val["y"][chosen]) - np.mean(
                    base[chosen] == val["y"][chosen]
                )
                balanced[replicate] = np.mean([signer_delta[signer] for signer in draw])
                macro[replicate] = d2.macro_f1(
                    val["y"][chosen], target[chosen]
                ) - d2.macro_f1(val["y"][chosen], base[chosen])
            empirical = {
                "ordinary_top1": float(np.mean(target == val["y"]) - np.mean(base == val["y"])),
                "signer_balanced_top1": float(np.mean(list(signer_delta.values()))),
                "macro_f1": d2.macro_f1(val["y"], target) - d2.macro_f1(val["y"], base),
            }
            for metric, values in (
                ("ordinary_top1", ordinary),
                ("signer_balanced_top1", balanced),
                ("macro_f1", macro),
            ):
                rows.append(
                    {
                        "comparison": comparison,
                        "seed": seed,
                        "metric": metric,
                        "empirical_point_delta": empirical[metric],
                        "bootstrap_mean_delta": float(np.mean(values)),
                        "ci95_low": float(np.percentile(values, 2.5)),
                        "ci95_high": float(np.percentile(values, 97.5)),
                        "replicates": 10_000,
                        "cluster_unit": "signer_group_id",
                        "bootstrap_seed": rng_seed,
                        "signer_clusters": len(signers),
                    }
                )
    return rows


def confusion_rows(
    val: dict[str, np.ndarray],
    arrays: dict[tuple[str, int], dict[str, np.ndarray]],
    supplemented: set[int],
    vocab: dict[int, str],
) -> list[dict[str, Any]]:
    true_unsupplemented = ~np.isin(val["y"], list(supplemented))
    rows: list[dict[str, Any]] = []
    for comparison, reference in (
        ("EC_P3_MINUS_BASELINE", "BASELINE"),
        ("EC_P3_MINUS_NAIVE_P3", "NAIVE_P3"),
    ):
        for seed in SEEDS:
            counts: dict[str, Counter[tuple[int, int]]] = {}
            totals: dict[str, int] = {}
            for condition in (reference, "EC_P3"):
                prediction = arrays[(condition, seed)]["prediction"]
                mask = (
                    true_unsupplemented
                    & (prediction != val["y"])
                    & np.isin(prediction, list(supplemented))
                )
                totals[condition] = int(mask.sum())
                counts[condition] = Counter(
                    (int(true), int(predicted))
                    for true, predicted in zip(
                        val["y"][mask], prediction[mask], strict=True
                    )
                )
            rows.append(
                {
                    "row_type": "SUMMARY",
                    "comparison": comparison,
                    "seed": seed,
                    "true_class_id": "",
                    "true_gloss": "",
                    "predicted_class_id": "",
                    "predicted_gloss": "",
                    "reference_events": totals[reference],
                    "ec_p3_events": totals["EC_P3"],
                    "ec_minus_reference": totals["EC_P3"] - totals[reference],
                    "diagnostic_only": True,
                }
            )
            pairs = set(counts[reference]) | set(counts["EC_P3"])
            ranked = sorted(
                pairs,
                key=lambda pair: abs(counts["EC_P3"][pair] - counts[reference][pair]),
                reverse=True,
            )[:25]
            for true, predicted in ranked:
                rows.append(
                    {
                        "row_type": "PAIR",
                        "comparison": comparison,
                        "seed": seed,
                        "true_class_id": true,
                        "true_gloss": vocab[true],
                        "predicted_class_id": predicted,
                        "predicted_gloss": vocab[predicted],
                        "reference_events": counts[reference][(true, predicted)],
                        "ec_p3_events": counts["EC_P3"][(true, predicted)],
                        "ec_minus_reference": counts["EC_P3"][(true, predicted)]
                        - counts[reference][(true, predicted)],
                        "diagnostic_only": True,
                    }
                )
    return rows


def median_delta(
    rows: list[dict[str, Any]], comparison: str, field: str
) -> float:
    return float(
        np.median(
            [float(row[field]) for row in rows if row["comparison"] == comparison]
        )
    )


def classify(
    deltas: list[dict[str, Any]], slices: list[dict[str, Any]]
) -> tuple[str, dict[str, Any]]:
    primary = [row for row in deltas if row["comparison"] == "EC_P3_MINUS_BASELINE"]
    sb = np.asarray([row["signer_balanced_top1_delta"] for row in primary], dtype=float)
    ordinary = np.asarray([row["ordinary_top1_delta"] for row in primary], dtype=float)
    macro = np.asarray([row["macro_f1_delta"] for row in primary], dtype=float)

    def slice_median(name: str, comparison: str) -> float:
        chosen = [
            row
            for row in slices
            if row["slice"] == name and row["comparison"] == comparison
        ]
        return float(np.median([row["top1_delta"] for row in chosen]))

    supp_base = slice_median("P3_SUPPLEMENTED_65", "EC_P3_MINUS_BASELINE")
    unsupp_base = slice_median("UNSUPPLEMENTED_171", "EC_P3_MINUS_BASELINE")
    unsupp_naive = slice_median("UNSUPPLEMENTED_171", "EC_P3_MINUS_NAIVE_P3")
    full_sb_naive = median_delta(
        deltas, "EC_P3_MINUS_NAIVE_P3", "signer_balanced_top1_delta"
    )
    full_ordinary_naive = median_delta(
        deltas, "EC_P3_MINUS_NAIVE_P3", "ordinary_top1_delta"
    )
    broad = bool(
        np.median(sb) > 0
        and np.sum(sb > 0) >= 2
        and np.median(ordinary) >= 0
        and np.median(macro) >= 0
        and supp_base > 0
        and unsupp_base >= 0
    )
    coherent_recovery = bool(
        unsupp_naive > 0 or full_sb_naive > 0 or full_ordinary_naive > 0
    )
    if supp_base <= 0:
        outcome = "SIGNER_DIVERSITY_GAIN_NOT_RETAINED_UNDER_EXPOSURE_CONTROL"
    elif broad:
        outcome = "EXPOSURE_CONTROL_BROAD_BENEFIT_SUPPORTED"
    elif unsupp_base < 0 and coherent_recovery:
        outcome = "EXPOSURE_CONTROL_PARTIAL_RECOVERY"
    elif unsupp_base < 0 and not coherent_recovery:
        outcome = "INTERFERENCE_PERSISTS_WITH_CLASS_EXPOSURE_CONTROLLED"
    else:
        outcome = "EXPOSURE_CONTROL_EFFECT_MIXED"
    evidence = {
        "median_signer_balanced_top1_delta_ec_minus_baseline": float(np.median(sb)),
        "positive_signer_balanced_seeds": int(np.sum(sb > 0)),
        "median_ordinary_top1_delta_ec_minus_baseline": float(np.median(ordinary)),
        "median_macro_f1_delta_ec_minus_baseline": float(np.median(macro)),
        "median_supplemented_65_top1_delta_ec_minus_baseline": supp_base,
        "median_unsupplemented_171_top1_delta_ec_minus_baseline": unsupp_base,
        "median_unsupplemented_171_top1_delta_ec_minus_naive_p3": unsupp_naive,
        "median_full_signer_balanced_top1_delta_ec_minus_naive_p3": full_sb_naive,
        "median_full_ordinary_top1_delta_ec_minus_naive_p3": full_ordinary_naive,
        "rules_applied_from_frozen_contract": True,
    }
    return outcome, evidence


def main() -> int:
    D11.mkdir(parents=True, exist_ok=True)
    progress_before = sha256(PROGRESS)
    if progress_before != EXPECTED_PROGRESS_SHA:
        raise RuntimeError("P5D11B_PROGRESS_TRACKER_PREHASH_MISMATCH")
    if sha256(V2 / "val.npz") != EXPECTED_VAL_SHA:
        raise RuntimeError("P5D11B_VALIDATION_HASH_MISMATCH")
    if sha256(D11 / "p5d11_preregistered_outcome_contract.json") != EXPECTED_OUTCOME_SHA:
        raise RuntimeError("P5D11B_OUTCOME_CONTRACT_MISMATCH")
    verifier = json.loads(
        (D11 / "p5d11_full_training_verification.json").read_text(encoding="utf-8")
    )
    if not verifier.get("passed") or verifier.get("verified_runs") != 3:
        raise RuntimeError("P5D11B_FULL_TRAINING_NOT_VERIFIED")
    d9b_integrity = json.loads((D9B / "p5d9b_integrity.json").read_text(encoding="utf-8"))
    if not d9b_integrity.get("passed") or d9b_integrity.get("protected_test_accessed"):
        raise RuntimeError("P5D11B_D9B_COMPARATOR_INTEGRITY")

    val = d2.load_split("val")
    if len(val["y"]) != 816 or len(set(map(int, val["y"]))) != 236:
        raise RuntimeError("P5D11B_VALIDATION_POPULATION_MISMATCH")
    arrays, comparator_verification = load_frozen_comparators(val)
    ec_verification = evaluate_ec(val, arrays)
    checkpoint_rows = comparator_verification + ec_verification
    write_csv(D11 / "p5d11b_checkpoint_and_prediction_verification.csv", checkpoint_rows)

    metrics, signer_metrics = metric_rows(val, arrays)
    write_csv(D11 / "p5d11b_metrics_all_runs.csv", metrics)
    write_csv(D11 / "p5d11b_signer_metrics.csv", signer_metrics)
    deltas, summary = delta_rows(metrics)
    write_csv(D11 / "p5d11b_seed_matched_deltas.csv", deltas)
    write_csv(D11 / "p5d11b_comparison_summary.csv", summary)
    signer_summary = signer_summaries(signer_metrics)
    write_csv(D11 / "p5d11b_signer_delta_summary.csv", signer_summary)
    bootstraps = bootstrap_rows(val, arrays)
    write_csv(D11 / "p5d11b_signer_block_bootstrap.csv", bootstraps)

    selected = read_csv(D8 / "p5d8_selected_policy_manifest.csv")
    supplemented = {int(row["apphear_class_id"]) for row in selected}
    if len(supplemented) != 65:
        raise RuntimeError("P5D11B_SUPPLEMENTED_CLASS_SET_MISMATCH")
    slices = slice_rows(val, arrays, supplemented)
    write_csv(D11 / "p5d11b_vocabulary_slices.csv", slices)
    vocab_raw = json.loads((V2 / "vocab.json").read_text(encoding="utf-8"))
    vocab = {int(class_id): gloss for gloss, class_id in vocab_raw.items()}
    confusion = confusion_rows(val, arrays, supplemented, vocab)
    write_csv(D11 / "p5d11b_confusion_into_supplemented_labels.csv", confusion)

    outcome, evidence = classify(deltas, slices)
    confidence = "MODERATE"
    next_gate = "FUTURE_VERSION_EVIDENCE_SYNTHESIS"
    write_json(
        D11 / "p5d11b_decision.json",
        {
            "classification": outcome,
            "confidence": confidence,
            "primary_endpoint": "SIGNER_BALANCED_TOP1",
            "primary_comparison": "EC_P3_MINUS_BASELINE",
            "diagnostic_comparison": "EC_P3_MINUS_NAIVE_P3",
            "outcome_contract_sha256": EXPECTED_OUTCOME_SHA,
            "evidence": evidence,
        },
    )
    write_json(D11 / "p5d11b_next_gate.json", {"next_gate": next_gate, "executed": False})
    interpretation = {
        "verified_fact": {
            "classification": outcome,
            "validation_population": "816 clips / 236 classes / 5 signer groups",
            **evidence,
        },
        "current_interpretation": (
            "Preserving the baseline class-label exposure schedule while introducing frozen P3 "
            "within-class variation changed the observed redistribution behavior according to the "
            "frozen D11 contract."
        ),
        "not_established": [
            "pure signer-diversity causality",
            "performance on the closed D10B secondary test",
            "pristine final-holdout generalization",
            "production Android improvement",
            "continuous ASL performance",
        ],
    }
    write_json(D11 / "p5d11b_scientific_interpretation.json", interpretation)

    progress_after = sha256(PROGRESS)
    integrity_passed = bool(
        progress_after == progress_before == EXPECTED_PROGRESS_SHA
        and all(bool(row["passed"]) for row in checkpoint_rows)
        and sha256(D11 / "p5d11_preregistered_outcome_contract.json")
        == EXPECTED_OUTCOME_SHA
    )
    integrity = {
        "passed": integrity_passed,
        "ec_p3_runs": 3,
        "frozen_baseline_comparators": 3,
        "frozen_naive_p3_comparators": 3,
        "validation_clips": 816,
        "validation_classes": 236,
        "validation_signer_groups": len(set(map(str, val["signers"]))),
        "validation_tensor_sha256": sha256(V2 / "val.npz"),
        "validation_membership_sha256": validation_membership_hash(val),
        "outcome_contract_sha256": sha256(
            D11 / "p5d11_preregistered_outcome_contract.json"
        ),
        "new_training": False,
        "test_accessed": False,
        "d10b_predictions_loaded": False,
        "p3_changed": False,
        "pfce_changed": False,
        "v2_changed": False,
        "p4_reopened": False,
        "android_modified": False,
        "progress_tracker_before": progress_before,
        "progress_tracker_after": progress_after,
        "progress_tracker_untouched": progress_after == progress_before,
    }
    write_json(D11 / "p5d11b_integrity.json", integrity)

    def seed_values(comparison: str, field: str) -> str:
        chosen = [row for row in deltas if row["comparison"] == comparison]
        return ", ".join(f"{int(row['seed'])}: {float(row[field]):+.2%}" for row in chosen)

    supp = evidence["median_supplemented_65_top1_delta_ec_minus_baseline"]
    unsupp = evidence["median_unsupplemented_171_top1_delta_ec_minus_baseline"]
    unsupp_naive = evidence["median_unsupplemented_171_top1_delta_ec_minus_naive_p3"]
    signer_primary = [
        row for row in signer_summary if row["comparison"] == "EC_P3_MINUS_BASELINE"
    ]
    patterns = Counter(row["pattern"] for row in signer_primary)
    seed_delta_text = seed_values(
        "EC_P3_MINUS_BASELINE", "signer_balanced_top1_delta"
    )
    report = (
        "# P5-D11B Exposure-Controlled P3 Result Audit\n\n"
        "## Governed result\n\n"
        "All three EC_P3 checkpoints and all six frozen PFCE comparator "
        "prediction artifacts passed integrity checks on the same 816-clip, "
        "236-class primary-validation population. No training or test access "
        "occurred during D11B.\n\n"
        f"- Classification: `{outcome}`\n"
        "- Median signer-balanced Top1, EC_P3 minus baseline: "
        f"{evidence['median_signer_balanced_top1_delta_ec_minus_baseline']:+.2%} "
        f"({evidence['positive_signer_balanced_seeds']}/3 positive seeds)\n"
        "- Median ordinary Top1: "
        f"{evidence['median_ordinary_top1_delta_ec_minus_baseline']:+.2%}\n"
        "- Median MacroF1: "
        f"{evidence['median_macro_f1_delta_ec_minus_baseline']:+.2%}\n"
        f"- Supplemented 65 median Top1 delta: {supp:+.2%}\n"
        f"- Unsupplemented 171 median Top1 delta: {unsupp:+.2%}\n"
        "- Unsupplemented 171 recovery versus naive P3: "
        f"{unsupp_naive:+.2%}\n\n"
        "Seed-matched signer-balanced deltas versus baseline: "
        f"{seed_delta_text}.\n\n"
        "## Signer and confusion diagnostics\n\n"
        f"Across the five validation signer groups, patterns were {dict(patterns)}. "
        "Signer-blocked intervals are uncertainty evidence only because the "
        "validation population has five signer clusters. Confusion movement "
        "from unsupplemented true classes into supplemented predicted labels "
        "is recorded in `p5d11b_confusion_into_supplemented_labels.csv`.\n\n"
        "## Interpretation boundary\n\n"
        "This validation-only causal audit tests exact class-exposure control "
        "with frozen P3 within-class diversity. It does not isolate signer "
        "diversity alone and does not reopen or evaluate the closed D10B test. "
        "The result is future-version evidence, not a production or "
        "pristine-holdout claim.\n\n"
        f"Next gate: `{next_gate}` (not executed).\n"
    )
    atomic_text(D11 / "P5D11B_EXPOSURE_CONTROLLED_RESULT_AUDIT.md", report)

    generated = [
        path
        for path in D11.rglob("*")
        if path.is_file()
        and (
            path.name.startswith("p5d11b_")
            or path.name == "P5D11B_EXPOSURE_CONTROLLED_RESULT_AUDIT.md"
            or "predictions_d11b" in path.parts
        )
        and path.name != "p5d11b_artifact_hash_manifest.json"
    ]
    generated.append(Path(__file__).resolve())
    governed = [
        V2 / "val.npz",
        D11 / "p5d11_preregistered_outcome_contract.json",
        D11 / "p5d11_full_training_verification.json",
        D8 / "p5d8_selected_policy_manifest.csv",
        D9B / "p5d9b_predictions_manifest.csv",
    ]
    write_json(
        D11 / "p5d11b_artifact_hash_manifest.json",
        {
            "generated_files": [
                {
                    "path": str(path.resolve()),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
                for path in sorted(generated)
            ],
            "governed_references": [
                {
                    "path": str(path.resolve()),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
                for path in governed
            ],
            "training_executed": False,
            "test_accessed": False,
        },
    )
    print(
        json.dumps(
            {
                "classification": outcome,
                "confidence": confidence,
                "integrity": integrity_passed,
                "evidence": evidence,
                "next_gate": next_gate,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
