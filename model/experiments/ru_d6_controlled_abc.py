"""RU-D6 controlled A/B/C retraining on one frozen validation split.

A is the original Phase-1 dataset, B is RU-D3 cleanup-only, and C is exactly B
plus the frozen RU-D5 Sem-Lex exact-target rows.  The protected test is never
opened, hashed, materialized, or used for selection.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

import model.experiments.ru_d4_cleanup_only_ab as base

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = "ru_d6_controlled_abc_retraining_v1"
BRANCHES = ("A_frozen_baseline", "B_ru_d3_cleanup", "C_ru_d5_semlex")
SEEDS = (101, 202, 303)
DEFAULT_A = ROOT / "artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1"
DEFAULT_B = ROOT / "artifacts/recognition_upgrade/ru_d3/repair_candidate_01/dataset"
DEFAULT_C = ROOT / "artifacts/recognition_upgrade/ru_d5/semlex_candidate_01/candidate_c/dataset"
DEFAULT_OUTPUT = ROOT / "artifacts/recognition_upgrade/ru_d6/controlled_abc_01"
DEFAULT_WARM_START = base.DEFAULT_WARM_START
TARGETS = ("KNOW", "WHO", "WE", "COME", "LEAVE")
CONFUSION_PARTNERS = {
    "KNOW": ("HELLO", "LUNCH1", "BECAUSE", "WHY", "SEEM"),
    "WHO": ("MOUTH", "SISTER", "YOU", "TALK1"),
    "WE": ("COME",),
    "COME": ("WE",),
    "LEAVE": ("GRAB", "WASH2", "SELL", "WORK", "CLOSE", "COME"),
}


def _configure_base() -> None:
    base.EXPERIMENT = EXPERIMENT
    base.BRANCHES = BRANCHES
    base.SEEDS = SEEDS
    base.TARGETS = TARGETS
    base.CONFUSION_PARTNERS = CONFUSION_PARTNERS


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=True) as payload:
        return {key: np.asarray(payload[key]) for key in payload.files}


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    required = [
        *(
            folder / name
            for folder in (args.a, args.b, args.c)
            for name in ("train.npz", "val.npz", "vocab.json", "dataset_contract.json")
            if not (folder == args.a and name == "dataset_contract.json")
        ),
        args.warm_start,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing RU-D6 input: {missing}")
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty RU-D6 output: {args.output}")
    contracts = {
        name: base._split_contract(folder / "train.npz")
        for name, folder in zip(BRANCHES, (args.a, args.b, args.c), strict=True)
    }
    validations = [base._split_contract(folder / "val.npz") for folder in (args.a, args.b, args.c)]
    errors = [
        error for contract in (*contracts.values(), *validations) for error in contract["errors"]
    ]
    expected_rows = dict(zip(BRANCHES, (3926, 3820, 3852), strict=True))
    for branch, expected in expected_rows.items():
        if contracts[branch]["rows"] != expected:
            errors.append(f"{branch} rows={contracts[branch]['rows']} expected={expected}")
        if contracts[branch]["classes"] != 236:
            errors.append(f"{branch} does not cover 236 classes")
    if len({item["sha256"] for item in validations}) != 1:
        errors.append("A/B/C validation hashes differ")
    if len({base._sha256(folder / "vocab.json") for folder in (args.a, args.b, args.c)}) != 1:
        errors.append("A/B/C vocab hashes differ")
    b_data, c_data = _load_npz(args.b / "train.npz"), _load_npz(args.c / "train.npz")
    if len(c_data["y"]) - len(b_data["y"]) != 32:
        errors.append("C does not add exactly the frozen 32-row Sem-Lex pool")
    for key in (
        "X",
        "y",
        "frame_mask",
        "lengths",
        "participant_ids",
        "sample_ids",
        "source_datasets",
        "raw_video_sha256",
        "roles",
    ):
        if not np.array_equal(c_data[key][: len(b_data["y"])], b_data[key]):
            errors.append(f"C prefix differs from B for {key}")
    c_contract = json.loads((args.c / "dataset_contract.json").read_text(encoding="utf-8"))
    if c_contract.get("protected_test_materialized") or c_contract.get("errors"):
        errors.append("Candidate C contract is not clean/protected-test-free")
    added_glosses = set()
    vocab = json.loads((args.c / "vocab.json").read_text(encoding="utf-8"))
    by_id = {int(value): key for key, value in vocab.items()}
    for class_id in c_data["y"][len(b_data["y"]) :]:
        added_glosses.add(by_id[int(class_id)])
    if added_glosses != set(TARGETS):
        errors.append(f"unexpected C added glosses: {sorted(added_glosses)}")
    if errors:
        raise ValueError("; ".join(errors))
    for relative in ("config", "logs", "models", "metrics", "smoke"):
        (args.output / relative).mkdir(parents=True, exist_ok=True)
    recipe = base._canonical_recipe()
    config = {
        "experiment": EXPERIMENT,
        "scope": (
            "controlled A/B/C; B-to-C difference is only 32 frozen "
            "Sem-Lex exact-target TRAIN rows"
        ),
        "schema_version": "3.0",
        "input_shape": [96, 258],
        "classes": 236,
        "branches": {
            branch: {"dataset_dir": str(folder.resolve()), "train": contracts[branch]}
            for branch, folder in zip(BRANCHES, (args.a, args.b, args.c), strict=True)
        },
        "shared_validation": validations[0],
        "shared_validation_hash_equal": True,
        "vocabulary": {
            "path": str((args.a / "vocab.json").resolve()),
            "sha256": base._sha256(args.a / "vocab.json"),
        },
        **recipe,
        "warm_start": {
            "path": str(args.warm_start.resolve()),
            "sha256": base._sha256(args.warm_start),
            "policy": "same encoder weights only; classifier head fresh per branch/seed",
        },
        "selection": {
            "source": "shared validation only",
            "metric": "validation clip top-1 per branch/seed",
            "protected_test_access": "prohibited",
        },
        "interpretation": {
            "aggregate_material_regression_points": 0.03,
            "class_regression_report_threshold": 0.10,
            "class_regression_requires_worse_seeds": 2,
            "fresh_phone_confirmation_required_after_offline_decision": True,
        },
        "b_to_c_contract": {
            "added_rows": 32,
            "allowed_glosses": list(TARGETS),
            "acceptable_variants": 0,
            "prefix_byte_equal": True,
        },
        "production_authorized": False,
        "training_authorized_for_ru_d6_only": True,
    }
    base._write_json(args.output / "config/experiment.json", config)
    result = {
        "experiment": EXPERIMENT,
        "rows": expected_rows,
        "seeds": list(SEEDS),
        "shared_validation_sha256": validations[0]["sha256"],
        "b_to_c_added_rows": 32,
        "protected_test_accessed": False,
        "errors": [],
        "passed": True,
    }
    base._write_json(args.output / "logs/prepare_summary.json", result)
    return result


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    _configure_base()
    return base.smoke(args)


def train(args: argparse.Namespace) -> dict[str, Any]:
    _configure_base()
    return base.train(args)


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    config = base._config(args.run_dir)
    validation_path = Path(config["shared_validation"]["path"])
    if base._sha256(validation_path) != config["shared_validation"]["sha256"]:
        raise ValueError("shared validation changed after RU-D6 preparation")
    x, y, mask, _, participant_ids = base._load_split(validation_path)
    vocab = json.loads(Path(config["vocabulary"]["path"]).read_text(encoding="utf-8"))
    labels_by_id = {int(class_id): gloss for gloss, class_id in vocab.items()}
    id_by_label = {gloss: class_id for class_id, gloss in labels_by_id.items()}
    per_seed: dict[str, dict[str, Any]] = {branch: {} for branch in BRANCHES}
    probabilities: dict[str, list[np.ndarray]] = {branch: [] for branch in BRANCHES}
    for seed in SEEDS:
        for branch in BRANCHES:
            checkpoint = args.run_dir / "models" / branch / f"seed_{seed}/best.keras"
            if not checkpoint.is_file():
                raise FileNotFoundError(f"missing RU-D6 checkpoint: {checkpoint}")
            tf.keras.backend.clear_session()
            model = tf.keras.models.load_model(checkpoint, compile=False, safe_mode=False)
            probs = base.predict_clip_probs(model, base.MODEL_BRANCH, x, mask, 32)
            probabilities[branch].append(probs)
            per_seed[branch][str(seed)] = base._metrics(probs, y, participant_ids, labels_by_id)
    ensembles = {
        branch: np.mean(np.stack(values), axis=0) for branch, values in probabilities.items()
    }
    metrics = {
        branch: base._metrics(values, y, participant_ids, labels_by_id)
        for branch, values in ensembles.items()
    }
    np.savez_compressed(
        args.run_dir / "metrics/validation_predictions.npz",
        labels=y,
        participant_ids=participant_ids,
        A_probabilities=ensembles[BRANCHES[0]],
        B_probabilities=ensembles[BRANCHES[1]],
        C_probabilities=ensembles[BRANCHES[2]],
        validation_sha256=np.asarray(config["shared_validation"]["sha256"]),
    )
    metric_names = (
        "top1",
        "top5",
        "macro_f1",
        "worst_decile_mean_recall",
        "worst_decile_mean_f1",
        "ece_15_bin",
    )
    means = {
        branch: {
            metric: float(np.mean([per_seed[branch][str(seed)][metric] for seed in SEEDS]))
            for metric in metric_names
        }
        for branch in BRANCHES
    }
    class_rows: list[dict[str, Any]] = []
    for class_id in range(236):
        gloss = labels_by_id[class_id]
        row: dict[str, Any] = {
            "class_id": class_id,
            "gloss": gloss,
            "support": metrics[BRANCHES[0]]["per_class"][class_id]["support"],
            "target": gloss in TARGETS,
        }
        for branch, prefix in zip(BRANCHES, ("A", "B", "C"), strict=True):
            item = metrics[branch]["per_class"][class_id]
            row[f"{prefix}_recall"], row[f"{prefix}_f1"] = item["recall"], item["f1"]
        row["C_minus_B_recall"] = row["C_recall"] - row["B_recall"]
        row["C_minus_B_f1"] = row["C_f1"] - row["B_f1"]
        row["C_worse_than_B_seed_count"] = sum(
            per_seed[BRANCHES[2]][str(seed)]["per_class"][class_id]["recall"]
            < per_seed[BRANCHES[1]][str(seed)]["per_class"][class_id]["recall"]
            for seed in SEEDS
        )
        class_rows.append(row)
    base._write_csv(args.run_dir / "metrics/per_class_comparison.csv", class_rows)
    confusion_rows: list[dict[str, Any]] = []
    seen = set()
    for target, partners in CONFUSION_PARTNERS.items():
        for partner in partners:
            for true_gloss, predicted_gloss in ((target, partner), (partner, target)):
                if (true_gloss, predicted_gloss) in seen:
                    continue
                seen.add((true_gloss, predicted_gloss))
                truth, predicted = id_by_label[true_gloss], id_by_label[predicted_gloss]
                row = {"true_gloss": true_gloss, "predicted_gloss": predicted_gloss}
                for branch, prefix in zip(BRANCHES, ("A", "B", "C"), strict=True):
                    row[prefix] = int(
                        np.sum((y == truth) & (np.argmax(ensembles[branch], axis=1) == predicted))
                    )
                row["C_minus_B"] = row["C"] - row["B"]
                confusion_rows.append(row)
    base._write_csv(args.run_dir / "metrics/target_confusions.csv", confusion_rows)
    severe = [
        row
        for row in class_rows
        if not row["target"]
        and row["C_minus_B_recall"]
        <= -float(config["interpretation"]["class_regression_report_threshold"])
        and row["C_worse_than_B_seed_count"]
        >= int(config["interpretation"]["class_regression_requires_worse_seeds"])
    ]
    report = {
        "experiment": EXPERIMENT,
        "stage": "shared_validation_controlled_abc",
        "validation_sha256": config["shared_validation"]["sha256"],
        "per_seed": per_seed,
        "mean_seed_metrics": means,
        "ensemble_metrics": metrics,
        "B_minus_A_mean_seed": {
            metric: means[BRANCHES[1]][metric] - means[BRANCHES[0]][metric]
            for metric in metric_names
        },
        "C_minus_B_mean_seed": {
            metric: means[BRANCHES[2]][metric] - means[BRANCHES[1]][metric]
            for metric in metric_names
        },
        "target_class_comparison": {row["gloss"]: row for row in class_rows if row["target"]},
        "severe_unrelated_C_vs_B_regressions": severe,
        "protected_test_accessed": False,
        "fresh_phone_confirmation_pending": True,
        "production_authorized": False,
        "passed": True,
    }
    base._write_json(args.run_dir / "metrics/abc_validation_report.json", report)
    return {
        "experiment": EXPERIMENT,
        "mean_seed_metrics": means,
        "C_minus_B_mean_seed": report["C_minus_B_mean_seed"],
        "severe_unrelated_regression_count": len(severe),
        "protected_test_accessed": False,
        "report": str((args.run_dir / "metrics/abc_validation_report.json").resolve()),
        "passed": True,
    }


def check(args: argparse.Namespace) -> dict[str, Any]:
    _configure_base()
    errors: list[str] = []
    config_path = args.run_dir / "config/experiment.json"
    if not config_path.is_file():
        errors.append("missing experiment config")
    else:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if config["selection"]["protected_test_access"] != "prohibited":
            errors.append("protected-test policy changed")
        if (
            base._sha256(Path(config["shared_validation"]["path"]))
            != config["shared_validation"]["sha256"]
        ):
            errors.append("shared validation hash changed")
    if args.require_smoke:
        path = args.run_dir / "smoke/smoke_summary.json"
        if not path.is_file() or not json.loads(path.read_text()).get("passed"):
            errors.append("A/B/C smoke missing or failed")
    if args.require_models:
        for seed in SEEDS:
            for branch in BRANCHES:
                for name in ("best.keras", "final.keras", "history.csv"):
                    if not (args.run_dir / "models" / branch / f"seed_{seed}" / name).is_file():
                        errors.append(f"missing {branch}/seed_{seed}/{name}")
    if args.require_evaluation:
        path = args.run_dir / "metrics/abc_validation_report.json"
        if not path.is_file() or not json.loads(path.read_text()).get("passed"):
            errors.append("A/B/C evaluation missing or failed")
    if list(args.run_dir.rglob("protected_test*")):
        errors.append("RU-D6 output contains protected-test artifact")
    result = {
        "run_dir": str(args.run_dir.resolve()),
        "errors": errors,
        "protected_test_accessed": False,
        "passed": not errors,
    }
    base._write_json(args.run_dir / "logs/check_report.json", result)
    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--a", type=Path, default=DEFAULT_A)
    prep.add_argument("--b", type=Path, default=DEFAULT_B)
    prep.add_argument("--c", type=Path, default=DEFAULT_C)
    prep.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prep.add_argument("--warm-start", type=Path, default=DEFAULT_WARM_START)
    for command in ("smoke", "train", "evaluate", "check"):
        child = sub.add_parser(command)
        child.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
        if command == "train":
            child.add_argument("--resume", action="store_true")
        if command == "check":
            child.add_argument("--require-smoke", action="store_true")
            child.add_argument("--require-models", action="store_true")
            child.add_argument("--require-evaluation", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    result = {
        "prepare": prepare,
        "smoke": smoke,
        "train": train,
        "evaluate": evaluate,
        "check": check,
    }[args.command](args)
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
