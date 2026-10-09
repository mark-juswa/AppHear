"""Sampling-only experiment utilities for Perception vNext 236 recognition."""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from model.perception_vnext.recognition_utility_236 import (
    DEFAULT_CONFIG as BASELINE_CONFIG,
)
from model.perception_vnext.recognition_utility_236 import (
    DEFAULT_DATASET,
    _classification_metrics,
    _predict_condition,
    _validate_sampling_only_delta,
    build_tcn,
    evaluate_model,
    load_config,
    load_index,
    make_dataset,
    sha256,
    write_json,
)
from model.perception_vnext.recognition_utility_236 import (
    DEFAULT_RUN as BASELINE_RUN,
)
from pipeline.perception_vnext.hierarchical_sampler import (
    SAMPLER_SCHEMA,
    SAMPLER_TYPE,
    draw_identity,
    hierarchical_clip_draws,
)

MILESTONE = "PERCEPTION_VNEXT_SAMPLING_GENERALIZATION_236_01"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / (
    "model/config/recognition_upgrade/perception_vnext_sampling_generalization_236_01.json"
)
DEFAULT_OUTPUT = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "sampling_generalization_236_01"
)
DEFAULT_BALANCED_RUN = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "tcn_sampling_balanced_01"
)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"VNEXT_SAMPLING_EMPTY_CSV:{path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _load_verified(dataset: Path, config_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    config = load_config(config_path)
    _validate_sampling_only_delta(config)
    rows = load_index(dataset)
    train = [row for row in rows if row["split"] == "train"]
    dev = [row for row in rows if row["split"] == "dev"]
    if len(train) != 3926 or len(dev) != 816:
        raise RuntimeError("VNEXT_SAMPLING_DATASET_COUNT")
    if {row["signer_id"] for row in train} & {row["signer_id"] for row in dev}:
        raise RuntimeError("VNEXT_SAMPLING_SIGNER_LEAKAGE")
    baseline_identity = json.loads((BASELINE_RUN / "run_identity.json").read_text(encoding="utf-8"))
    if sha256(dataset / "contract.json") != baseline_identity["dataset_contract_sha256"]:
        raise RuntimeError("VNEXT_SAMPLING_DATASET_IDENTITY")
    return rows, config


def audit_sampler(
    dataset: Path,
    config_path: Path,
    output: Path,
    simulation_epochs: int,
) -> dict[str, Any]:
    rows, config = _load_verified(dataset, config_path)
    train = [row for row in rows if row["split"] == "train"]
    seed = int(config["seed"])
    draws = int(config["training_sampler"]["draws_per_epoch"])
    deterministic_a = hierarchical_clip_draws(train, draws=draws, seed=seed, epoch=0)
    deterministic_b = hierarchical_clip_draws(train, draws=draws, seed=seed, epoch=0)
    next_epoch = hierarchical_clip_draws(train, draws=draws, seed=seed, epoch=1)
    deterministic = draw_identity(deterministic_a) == draw_identity(deterministic_b)
    epoch_specific = draw_identity(deterministic_a) != draw_identity(next_epoch)

    original_by_class: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    original_by_class_signer: defaultdict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in train:
        class_id = int(row["class_id"])
        original_by_class[class_id].append(row)
        original_by_class_signer[(class_id, row["signer_id"])].append(row)
    draw_class = Counter()
    draw_class_signer = Counter()
    per_epoch_class_range = []
    maximum_within_class_signer_range = 0
    for epoch in range(simulation_epochs):
        selected = hierarchical_clip_draws(train, draws=draws, seed=seed, epoch=epoch)
        class_counts = Counter(int(row["class_id"]) for row in selected)
        per_epoch_class_range.append(max(class_counts.values()) - min(class_counts.values()))
        if set(class_counts) != set(range(236)):
            raise RuntimeError(f"VNEXT_SAMPLING_CLASS_COVERAGE:{epoch}")
        for row in selected:
            key = (int(row["class_id"]), row["signer_id"])
            draw_class[key[0]] += 1
            draw_class_signer[key] += 1
        for class_id in range(236):
            signer_counts = Counter(
                row["signer_id"] for row in selected if int(row["class_id"]) == class_id
            )
            maximum_within_class_signer_range = max(
                maximum_within_class_signer_range,
                max(signer_counts.values()) - min(signer_counts.values()),
            )

    vocabulary = {
        int(row["class_id"]): row["canonical_gloss"] for row in train
    }
    class_rows = []
    signer_rows = []
    for class_id in range(236):
        class_train = original_by_class[class_id]
        signers = sorted({row["signer_id"] for row in class_train})
        original_signer_counts = Counter(row["signer_id"] for row in class_train)
        empirical = draw_class[class_id] / simulation_epochs
        class_rows.append(
            {
                "class_id": class_id,
                "canonical_gloss": vocabulary[class_id],
                "original_clips": len(class_train),
                "original_expected_draws_per_epoch": len(class_train),
                "new_draws_total": draw_class[class_id],
                "new_draws_per_epoch": empirical,
                "new_class_probability": draw_class[class_id] / (draws * simulation_epochs),
                "ideal_class_probability": 1.0 / 236.0,
                "distinct_signers": len(signers),
                "original_largest_signer_share": max(original_signer_counts.values())
                / len(class_train),
                "new_largest_signer_share": max(
                    draw_class_signer[(class_id, signer)] for signer in signers
                )
                / draw_class[class_id],
                "ideal_signer_share": 1.0 / len(signers),
            }
        )
        for signer in signers:
            clips = len(original_by_class_signer[(class_id, signer)])
            signer_rows.append(
                {
                    "class_id": class_id,
                    "canonical_gloss": vocabulary[class_id],
                    "signer_id": signer,
                    "original_clips": clips,
                    "original_within_class_share": clips / len(class_train),
                    "new_draws": draw_class_signer[(class_id, signer)],
                    "new_within_class_share": draw_class_signer[(class_id, signer)]
                    / draw_class[class_id],
                    "ideal_within_class_share": 1.0 / len(signers),
                }
            )
    class_values = np.asarray([row["new_draws_total"] for row in class_rows], np.float64)
    new_signer_error = np.asarray(
        [
            abs(row["new_within_class_share"] - row["ideal_within_class_share"])
            for row in signer_rows
        ]
    )
    target_glosses = {"GOOD", "HAVE", "HELLO", "KNOW", "SORRY"}
    ordinary_glosses = {"BIG", "CHAIR", "COMPUTER", "FAMILY", "WATER"}
    highlighted = {
        row["canonical_gloss"]: row
        for row in class_rows
        if row["canonical_gloss"] in target_glosses | ordinary_glosses
    }
    gates = {
        "same_seed_epoch_repeats_exactly": deterministic,
        "different_epoch_changes_sequence": epoch_specific,
        "draws_per_epoch_exact": all(
            sum(
                1
                for row in hierarchical_clip_draws(train, draws=draws, seed=seed, epoch=epoch)
            )
            == draws
            for epoch in (0, simulation_epochs - 1)
        ),
        "class_count_range_per_epoch_at_most_one": max(per_epoch_class_range) <= 1,
        "signer_count_range_within_class_per_epoch_at_most_one": (
            maximum_within_class_signer_range <= 1
        ),
        "aggregate_class_cv_at_most_five_percent": (
            float(class_values.std() / class_values.mean()) <= 0.05
        ),
        "aggregate_signer_share_max_abs_error_at_most_two_percent": (
            float(new_signer_error.max()) <= 0.02
        ),
        "train_only": all(row["split"] == "train" for row in deterministic_a),
    }
    status = "PASS" if all(gates.values()) else "FAIL"
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(config_path, output / "run_config.json")
    _write_csv(output / "sampler_distribution_by_class.csv", class_rows)
    _write_csv(output / "sampler_distribution_by_class_signer.csv", signer_rows)
    contract = {
        "schema": SAMPLER_SCHEMA,
        "type": SAMPLER_TYPE,
        "seed": seed,
        "epoch_seed_identity": "NumPy SeedSequence([seed, epoch, 0x41505048])",
        "draws_per_epoch": draws,
        "views_per_draw": ["dense", "sparse"],
        "views_per_epoch": draws * 2,
        "steps_per_epoch": math.ceil(draws * 2 / int(config["training"]["batch_size"])),
        "class_policy": config["training_sampler"]["class_policy"],
        "signer_policy": config["training_sampler"]["signer_policy"],
        "clip_policy": config["training_sampler"]["clip_policy"],
        "sampling_with_replacement": True,
        "dataset_contract_sha256": sha256(dataset / "contract.json"),
        "config_sha256": sha256(config_path),
        "baseline_config_sha256": sha256(BASELINE_CONFIG),
        "protected_test_accessed": False,
    }
    audit = {
        "schema": "APPHEAR_VNEXT_SAMPLER_DISTRIBUTION_AUDIT_V1",
        "milestone": MILESTONE,
        "status": status,
        "simulation_epochs": simulation_epochs,
        "simulation_draws": draws * simulation_epochs,
        "gates": gates,
        "epoch_zero_draw_sha256": draw_identity(deterministic_a),
        "epoch_one_draw_sha256": draw_identity(next_epoch),
        "class_draws": {
            "mean": float(class_values.mean()),
            "minimum": int(class_values.min()),
            "maximum": int(class_values.max()),
            "coefficient_of_variation": float(class_values.std() / class_values.mean()),
            "maximum_per_epoch_range": max(per_epoch_class_range),
        },
        "within_class_signer": {
            "maximum_per_epoch_count_range": maximum_within_class_signer_range,
            "aggregate_share_max_abs_error": float(new_signer_error.max()),
            "aggregate_share_median_abs_error": float(np.median(new_signer_error)),
        },
        "supplemented_classes": {gloss: highlighted[gloss] for gloss in sorted(target_glosses)},
        "ordinary_classes": {gloss: highlighted[gloss] for gloss in sorted(ordinary_glosses)},
        "protected_test_accessed": False,
    }
    write_json(output / "sampler_contract.json", contract)
    write_json(output / "sampler_distribution_audit.json", audit)
    if status != "PASS":
        raise RuntimeError(f"VNEXT_SAMPLER_DISTRIBUTION_FAILURE:{gates}")
    return audit


def smoke_training(dataset: Path, config_path: Path, output: Path) -> dict[str, Any]:
    import tensorflow as tf

    rows, config = _load_verified(dataset, config_path)
    train = [row for row in rows if row["split"] == "train"]
    dev = [row for row in rows if row["split"] == "dev"]
    seed = int(config["seed"])
    tf.keras.utils.set_random_seed(seed)
    selected = hierarchical_clip_draws(train, draws=236, seed=seed, epoch=0)
    if {int(row["class_id"]) for row in selected} != set(range(236)):
        raise RuntimeError("VNEXT_SAMPLING_SMOKE_CLASS_COVERAGE")
    if any(row["split"] != "train" for row in selected):
        raise RuntimeError("VNEXT_SAMPLING_SMOKE_DEV_LEAKAGE")
    batch_size = int(config["training"]["batch_size"])
    train_ds = make_dataset(selected, ("dense", "sparse"), batch_size, seed, False)
    dev_rows = dev[:16]
    dev_ds = make_dataset(dev_rows, ("dense", "sparse"), batch_size, seed, False)
    model = build_tcn(config)
    history = model.fit(train_ds, validation_data=dev_ds, epochs=1, verbose=2, shuffle=False)
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = output / "smoke_checkpoint.keras"
    model.save(checkpoint)
    reloaded = tf.keras.models.load_model(checkpoint, safe_mode=True)
    sample_inputs, _ = next(iter(make_dataset(dev_rows[:1], ("dense",), 1, seed, False)))
    before = np.asarray(model(sample_inputs, training=False))
    after = np.asarray(reloaded(sample_inputs, training=False))
    reload_max_abs = float(np.max(np.abs(before - after)))
    prediction_result = _predict_condition(reloaded, dev_rows, "dense", batch_size)
    evaluation_smoke = _classification_metrics(prediction_result)
    finite = all(
        np.all(np.isfinite(np.asarray(values, np.float64)))
        for values in history.history.values()
    )
    result = {
        "schema": "APPHEAR_VNEXT_BALANCED_SAMPLING_SMOKE_V1",
        "milestone": MILESTONE,
        "status": "PASS" if finite and reload_max_abs <= 1e-6 else "FAIL",
        "sampler_schema": SAMPLER_SCHEMA,
        "sampler_type": SAMPLER_TYPE,
        "clip_draws": 236,
        "views": 472,
        "classes": 236,
        "train_only": True,
        "dev_leakage": False,
        "feature_shape": [96, 208],
        "mask_shape": [96],
        "finite_loss_and_metrics": finite,
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": sha256(checkpoint),
        "checkpoint_reload_max_abs": reload_max_abs,
        "evaluation_plumbing_clips": evaluation_smoke["clips"],
        "evaluation_plumbing_status": "PASS",
        "recognition_accuracy_claim": False,
        "full_training_executed": False,
        "protected_test_accessed": False,
    }
    write_json(output / "smoke_training_result.json", result)
    if result["status"] != "PASS":
        raise RuntimeError(f"VNEXT_SAMPLING_SMOKE_FAILURE:{result}")
    return result


def evaluate_and_compare(
    dataset: Path,
    checkpoint: Path,
    output: Path,
    baseline: Path,
    batch_size: int,
) -> dict[str, Any]:
    current = evaluate_model(dataset, checkpoint, output, batch_size)
    control = json.loads(baseline.read_text(encoding="utf-8"))
    comparison: dict[str, Any] = {
        "schema": "APPHEAR_VNEXT_SAMPLING_BASELINE_COMPARISON_V1",
        "milestone": MILESTONE,
        "status": "PASS",
        "baseline_evaluation": str(baseline.resolve()),
        "baseline_evaluation_sha256": sha256(baseline),
        "candidate_evaluation": str(output.resolve()),
        "candidate_evaluation_sha256": sha256(output),
        "conditions": {},
        "protected_test_accessed": False,
    }
    for condition in ("dense", "phone_01_sparse"):
        baseline_metrics = control["details"]["dev"][condition]
        candidate_metrics = current["details"]["dev"][condition]
        signer_delta = {
            signer: {
                "baseline_top1": values["top1"],
                "candidate_top1": candidate_metrics["by_signer"][signer]["top1"],
                "delta": candidate_metrics["by_signer"][signer]["top1"] - values["top1"],
                "clips": values["clips"],
            }
            for signer, values in baseline_metrics["by_signer"].items()
        }
        comparison["conditions"][condition] = {
            metric: {
                "baseline": baseline_metrics[metric],
                "candidate": candidate_metrics[metric],
                "delta": candidate_metrics[metric] - baseline_metrics[metric],
            }
            for metric in ("top1", "top5", "macro_f1")
        }
        comparison["conditions"][condition]["zero_recall_classes"] = {
            "baseline": len(baseline_metrics["zero_recall_classes"]),
            "candidate": len(candidate_metrics["zero_recall_classes"]),
            "delta": len(candidate_metrics["zero_recall_classes"])
            - len(baseline_metrics["zero_recall_classes"]),
        }
        comparison["conditions"][condition]["by_signer"] = signer_delta
    comparison["train_minus_dev_top1_gap"] = {
        condition: {
            "baseline": control["train_minus_dev_top1_gap"][condition],
            "candidate": current["train_minus_dev_top1_gap"][condition],
            "delta": current["train_minus_dev_top1_gap"][condition]
            - control["train_minus_dev_top1_gap"][condition],
        }
        for condition in ("dense", "phone_01_sparse")
    }
    comparison_path = output.with_name("baseline_comparison.json")
    write_json(comparison_path, comparison)
    return comparison


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit-sampler")
    audit.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    audit.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    audit.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    audit.add_argument("--simulation-epochs", type=int, default=100)
    smoke = commands.add_parser("smoke-training")
    smoke.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    smoke.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    smoke.add_argument("--output", type=Path, default=DEFAULT_OUTPUT / "smoke_training")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    evaluate.add_argument("--checkpoint", type=Path, default=DEFAULT_BALANCED_RUN / "best.keras")
    evaluate.add_argument("--output", type=Path, default=DEFAULT_BALANCED_RUN / "evaluation.json")
    evaluate.add_argument("--baseline", type=Path, default=BASELINE_RUN / "evaluation.json")
    evaluate.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    if args.command == "audit-sampler":
        if args.simulation_epochs < 10 or args.simulation_epochs > 1000:
            raise RuntimeError("VNEXT_SAMPLING_SIMULATION_EPOCHS_RANGE")
        result = audit_sampler(args.dataset, args.config, args.output, args.simulation_epochs)
    elif args.command == "smoke-training":
        result = smoke_training(args.dataset, args.config, args.output)
    elif args.command == "evaluate":
        result = evaluate_and_compare(
            args.dataset,
            args.checkpoint,
            args.output,
            args.baseline,
            args.batch_size,
        )
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
