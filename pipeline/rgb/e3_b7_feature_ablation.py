"""E3-B7 derived-feature ablation on the frozen E3-B5 split.

This experiment narrows E3-B6 by training smaller derived-feature subsets. It writes isolated
outputs only and does not change production assets or the v3.0 feature contract.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.rgb.e3_b4_landmark_temporal import _build_model, _inputs_for, _load_weights_model
from pipeline.rgb.e3_b5_landmark_temporal_scale import _evaluate as _evaluate_e3b5
from pipeline.rgb.e3_b6_feature_augmentation import _load_source, _relation_features, _temporal_delta, _xyz_streams

DEFAULT_SOURCE_RUN = Path("artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed")
DEFAULT_OUTPUT_ROOT = Path("artifacts/recognition_upgrade/e3_landmark_temporal")
DEFAULT_RUN_ID = "pilot_04_feature_ablation"
SPLITS = {"train": 0, "val": 1, "test": 2}
BRANCH_KIND = {
    "conv1d": "conv1d_baseline",
    "masked_tcn": "tcn_masked_pool",
}
VARIANTS = {
    "base_velocity": ["base", "velocity"],
    "base_relations": ["base", "relations"],
    "base_velocity_relations": ["base", "velocity", "relations"],
    "base_velocity_acceleration": ["base", "velocity", "acceleration"],
}


def _components(landmarks: np.ndarray, frame_mask: np.ndarray) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    base = landmarks.astype(np.float32)
    mask = frame_mask.astype(np.float32)
    xyz = _xyz_streams(base)
    velocity = _temporal_delta(xyz, mask)
    acceleration = _temporal_delta(velocity, mask)
    relations, relation_names = _relation_features(base, mask)
    invalid = mask <= 0.5
    for arr in (base, velocity, acceleration, relations):
        arr[invalid] = 0.0
    parts = {
        "base": base,
        "velocity": velocity,
        "acceleration": acceleration,
        "relations": relations,
    }
    schema = {
        "experiment_schema": "e3_b7_feature_ablation_v1",
        "components": {
            "base": {"dim": 258, "description": "original v3.0 258 landmark tensor"},
            "velocity": {"dim": 225, "description": "xyz delta for hand and pose xyz channels"},
            "acceleration": {"dim": 225, "description": "delta of velocity"},
            "relations": {"dim": 20, "description": "hand/body relationship and presence features", "items": relation_names},
        },
        "variants": {},
        "mask_rule": "all components are zeroed on padded frames; deltas require adjacent real frames",
    }
    return parts, schema


def _build_variant(parts: dict[str, np.ndarray], names: list[str]) -> np.ndarray:
    tensor = np.concatenate([parts[name] for name in names], axis=-1).astype(np.float32)
    if np.isnan(tensor).any() or np.isinf(tensor).any():
        raise ValueError("variant tensor contains NaN or Inf")
    return tensor


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    source_config, source = _load_source(args.source_run)
    output = args.output_root / args.run_id
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"output already exists: {output}")
    for relative in ("dataset", "logs", "metrics", "models", "smoke"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    landmarks = source["landmarks"].astype(np.float32)
    frame_mask = source["frame_mask"].astype(np.float32)
    parts, schema = _components(landmarks, frame_mask)
    selected_variants = list(args.variants)
    unknown_variants = [name for name in selected_variants if name not in VARIANTS]
    if unknown_variants:
        raise ValueError(f"unsupported variants: {unknown_variants}")
    unknown_branches = [branch for branch in args.branches if branch not in BRANCH_KIND]
    if unknown_branches:
        raise ValueError(f"unsupported branches: {unknown_branches}")

    variant_shapes: dict[str, list[int]] = {}
    for variant in selected_variants:
        tensor = _build_variant(parts, VARIANTS[variant])
        variant_shapes[variant] = [int(v) for v in tensor.shape[1:]]
        schema["variants"][variant] = {
            "components": VARIANTS[variant],
            "feature_dim": int(tensor.shape[-1]),
        }
        np.savez_compressed(
            output / "dataset" / f"{variant}.npz",
            features=tensor,
            frame_mask=frame_mask,
            y=source["y"].astype(np.int64),
            split_index=source["split_index"].astype(np.int64),
            lengths=source["lengths"].astype(np.int32),
            old_y=source["old_y"].astype(np.int64),
            source_indices=source["source_indices"].astype(np.int64),
            participant_ids=source["participant_ids"].astype(str),
        )
    (output / "feature_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    for name in ("pilot_manifest.csv", "selected_classes.csv"):
        source_path = args.source_run / name
        if source_path.exists():
            (output / name).write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")

    config = {
        "experiment": "e3_b7_feature_ablation_v1",
        "purpose": "identify which E3-B6 derived feature group caused the useful test gain",
        "run_dir": str(output.resolve()),
        "source_run": str(args.source_run.resolve()),
        "source_experiment": source_config["experiment"],
        "classes": source_config["classes"],
        "class_count": int(source_config["class_count"]),
        "rows": int(landmarks.shape[0]),
        "split_counts": {name: int(np.sum(source["split_index"] == sid)) for name, sid in SPLITS.items()},
        "variants": selected_variants,
        "variant_components": {name: VARIANTS[name] for name in selected_variants},
        "variant_shapes": variant_shapes,
        "branches": list(args.branches),
        "branch_model_map": BRANCH_KIND,
        "seeds": [int(seed) for seed in args.seeds],
        "batch_size": int(args.batch_size),
        "epochs": int(args.epochs),
        "learning_rate": float(args.learning_rate),
        "baseline_reference": {
            "e3_b5_masked_val": 0.4900,
            "e3_b5_masked_test": 0.3433,
            "e3_b6_aug_masked_val": 0.5117,
            "e3_b6_aug_masked_test": 0.3867,
            "e3_b6_aug_conv_val": 0.5033,
            "e3_b6_aug_conv_test": 0.3883,
        },
        "gate": {
            "go_if": [
                "a reduced variant retains E3-B6 mean best-test >= 0.3867",
                "mean best-validation is at least E3-B5 masked TCN 0.4900",
                "train-validation gap is lower than full E3-B6 augmented branches",
                "seed winners and prediction distribution are more stable",
            ],
            "no_go_if": [
                "test gain disappears",
                "only train accuracy improves",
                "reduced features still overfit like full E3-B6",
                "no subset identifies a clear useful feature group",
            ],
        },
        "warnings": [
            "Experiment-only feature subsets; no production contract change.",
            "If a subset is promoted later, Kotlin parity/skew tests are required.",
            "Repeated use of the same frozen split can overfit experiment decisions.",
        ],
    }
    (output / "pilot_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def _load_variant(run_dir: Path, variant: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    path = run_dir / "dataset" / f"{variant}.npz"
    if not path.exists():
        raise FileNotFoundError(f"missing variant tensor: {path}")
    data = np.load(path, allow_pickle=False)
    required = {"features", "frame_mask", "y", "split_index", "lengths"}
    missing = required.difference(data.files)
    if missing:
        raise ValueError(f"{variant} tensor missing keys: {sorted(missing)}")
    return (
        data["features"].astype(np.float32),
        data["frame_mask"].astype(np.float32),
        data["y"].astype(np.int64),
        data["split_index"].astype(np.int64),
        data["lengths"].astype(np.int32),
    )


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    summary: dict[str, Any] = {"experiment": config["experiment"], "run_dir": str(run_dir.resolve()), "variants": {}}
    for variant in config["variants"]:
        features, frame_mask, y, split_index, _ = _load_variant(run_dir, variant)
        train_rows = np.flatnonzero(split_index == 0)[: max(2, min(args.rows, 8))]
        val_rows = np.flatnonzero(split_index == 1)[: max(2, min(args.rows, 8))]
        summary["variants"][variant] = {"input_shape": [int(v) for v in features.shape[1:]], "branches": {}}
        for branch in config["branches"]:
            kind = BRANCH_KIND[branch]
            tf.keras.backend.clear_session()
            tf.keras.utils.set_random_seed(12345)
            model = _build_model(kind, tuple(features.shape[1:]), int(config["class_count"]), float(config["learning_rate"]))
            probs = model.predict(_inputs_for(kind, features[val_rows], frame_mask[val_rows]), batch_size=2, verbose=0)
            loss = model.train_on_batch(_inputs_for(kind, features[train_rows], frame_mask[train_rows]), y[train_rows])
            weights_path = run_dir / "smoke" / f"{variant}_{branch}.weights.h5"
            model.save_weights(weights_path)
            reloaded = _load_weights_model(kind, tuple(features.shape[1:]), int(config["class_count"]), float(config["learning_rate"]), weights_path)
            reloaded_probs = reloaded.predict(_inputs_for(kind, features[val_rows[:2]], frame_mask[val_rows[:2]]), batch_size=2, verbose=0)
            summary["variants"][variant]["branches"][branch] = {
                "model_kind": kind,
                "forward_shape": [int(v) for v in probs.shape],
                "train_on_batch": [float(v) for v in np.atleast_1d(loss).tolist()],
                "reload_forward_shape": [int(v) for v in reloaded_probs.shape],
                "weights_saved": str(weights_path.resolve()),
            }
    (run_dir / "smoke" / "smoke_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config_path = run_dir / "pilot_config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"missing config; run prepare first: {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    start = time.perf_counter()
    metrics: dict[str, Any] = {
        "experiment": config["experiment"],
        "run_dir": str(run_dir.resolve()),
        "baseline_reference": config["baseline_reference"],
        "results": {},
        "elapsed_seconds": None,
        "passed": True,
    }
    for variant in config["variants"]:
        features, frame_mask, y, split_index, _ = _load_variant(run_dir, variant)
        train_mask = split_index == 0
        val_mask = split_index == 1
        metrics["results"][variant] = {}
        for branch in config["branches"]:
            kind = BRANCH_KIND[branch]
            metrics["results"][variant][branch] = {}
            for seed in config["seeds"]:
                seed = int(seed)
                tf.keras.backend.clear_session()
                tf.keras.utils.set_random_seed(seed)
                seed_dir = run_dir / "models" / variant / branch / f"seed_{seed}"
                seed_dir.mkdir(parents=True, exist_ok=True)
                latest = seed_dir / "latest.weights.h5"
                best = seed_dir / "best.weights.h5"
                epoch_file = run_dir / "logs" / f"{variant}_{branch}_seed_{seed}_epoch_count.txt"
                history_path = run_dir / "logs" / f"{variant}_{branch}_seed_{seed}_history.csv"
                if latest.exists() and not args.resume:
                    raise FileExistsError(f"{variant}/{branch} seed {seed}: latest weights exist; rerun with --resume")
                model = _build_model(kind, tuple(features.shape[1:]), int(config["class_count"]), float(config["learning_rate"]))
                if args.resume and latest.exists():
                    model.load_weights(latest)
                    initial_epoch = int(epoch_file.read_text(encoding="utf-8"))
                else:
                    initial_epoch = 0
                history = model.fit(
                    _inputs_for(kind, features[train_mask], frame_mask[train_mask]),
                    y[train_mask],
                    validation_data=(_inputs_for(kind, features[val_mask], frame_mask[val_mask]), y[val_mask]),
                    batch_size=int(config["batch_size"]),
                    epochs=initial_epoch + int(config["epochs"]),
                    initial_epoch=initial_epoch,
                    callbacks=[
                        tf.keras.callbacks.ModelCheckpoint(str(best), monitor="val_accuracy", mode="max", save_best_only=True, save_weights_only=True),
                        tf.keras.callbacks.CSVLogger(str(history_path), append=history_path.exists()),
                    ],
                    verbose=2,
                )
                model.save_weights(latest)
                total_epochs = initial_epoch + int(config["epochs"])
                epoch_file.write_text(str(total_epochs), encoding="utf-8")
                metrics["results"][variant][branch][str(seed)] = {
                    "input_shape": [int(v) for v in features.shape[1:]],
                    "latest": _evaluate_e3b5(kind, model, features, frame_mask, y, split_index, int(config["batch_size"]), config["classes"]),
                    "best": _evaluate_e3b5(
                        kind,
                        _load_weights_model(kind, tuple(features.shape[1:]), int(config["class_count"]), float(config["learning_rate"]), best),
                        features,
                        frame_mask,
                        y,
                        split_index,
                        int(config["batch_size"]),
                        config["classes"],
                    ),
                    "epoch_count_total": int(total_epochs),
                    "history_last": {key: float(values[-1]) for key, values in history.history.items() if values},
                }
                (run_dir / "metrics" / "metrics_partial.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    metrics["elapsed_seconds"] = time.perf_counter() - start
    metrics["summary"] = _summarize(metrics)
    (run_dir / "metrics" / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (run_dir / "metrics" / "metrics.md").write_text(_metrics_markdown(metrics), encoding="utf-8")
    return metrics


def _summarize(metrics: dict[str, Any]) -> dict[str, Any]:
    by_candidate: dict[str, Any] = {}
    winners: dict[str, str] = {}
    for variant, branches in metrics["results"].items():
        for branch, seeds in branches.items():
            key = f"{variant}/{branch}"
            trains = np.asarray([result["best"]["train"]["accuracy"] for result in seeds.values()], dtype=np.float32)
            vals = np.asarray([result["best"]["val"]["accuracy"] for result in seeds.values()], dtype=np.float32)
            tests = np.asarray([result["best"]["test"]["accuracy"] for result in seeds.values()], dtype=np.float32)
            by_candidate[key] = {
                "variant": variant,
                "branch": branch,
                "mean_best_train": float(np.mean(trains)),
                "mean_best_val": float(np.mean(vals)),
                "std_best_val": float(np.std(vals)),
                "mean_best_test": float(np.mean(tests)),
                "std_best_test": float(np.std(tests)),
                "mean_train_val_gap": float(np.mean(trains - vals)),
                "mean_val_test_gap": float(np.mean(vals - tests)),
                "seed_count": int(len(vals)),
            }
    seed_ids = sorted({seed for variant in metrics["results"].values() for branch in variant.values() for seed in branch})
    for seed in seed_ids:
        candidates: dict[str, float] = {}
        for variant, branches in metrics["results"].items():
            for branch, seeds in branches.items():
                if seed in seeds:
                    candidates[f"{variant}/{branch}"] = float(seeds[seed]["best"]["val"]["accuracy"])
        winners[seed] = max(candidates, key=candidates.get)
    best_val = max(by_candidate, key=lambda key: by_candidate[key]["mean_best_val"])
    best_test = max(by_candidate, key=lambda key: by_candidate[key]["mean_best_test"])
    ref = metrics["baseline_reference"]
    return {
        "by_candidate": dict(sorted(by_candidate.items(), key=lambda item: -item[1]["mean_best_val"])),
        "winner_by_seed_best_val": winners,
        "decision_hint": {
            "best_mean_validation_candidate": best_val,
            "best_mean_test_candidate": best_test,
            "best_val_gain_over_e3_b5_masked": float(by_candidate[best_val]["mean_best_val"] - ref["e3_b5_masked_val"]),
            "best_test_gain_over_e3_b6_full_aug_masked": float(by_candidate[best_test]["mean_best_test"] - ref["e3_b6_aug_masked_test"]),
            "promising": bool(
                by_candidate[best_test]["mean_best_test"] >= ref["e3_b6_aug_masked_test"]
                and by_candidate[best_test]["mean_best_val"] >= ref["e3_b5_masked_val"]
                and by_candidate[best_test]["mean_train_val_gap"] < 0.30
            ),
        },
    }


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["pilot_config.json", "feature_schema.json", "README_RUN.md"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    config: dict[str, Any] = {}
    config_path = run_dir / "pilot_config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        for variant in config.get("variants", []):
            path = run_dir / "dataset" / f"{variant}.npz"
            if not path.exists():
                errors.append(f"missing variant tensor: dataset/{variant}.npz")
                continue
            features, frame_mask, y, split_index, _ = _load_variant(run_dir, variant)
            if list(features.shape[1:]) != config["variant_shapes"][variant]:
                errors.append(f"{variant}: shape mismatch")
            if np.isnan(features).any() or np.isinf(features).any():
                errors.append(f"{variant}: contains NaN or Inf")
            if np.any(features[frame_mask <= 0.5] != 0.0):
                errors.append(f"{variant}: padded frames are not zeroed")
            if len(y) != int(config["rows"]) or len(split_index) != int(config["rows"]):
                errors.append(f"{variant}: row count mismatch")
    metrics_path = run_dir / "metrics" / "metrics.json"
    if args.require_metrics and not metrics_path.exists():
        errors.append("missing output: metrics/metrics.json")
    if metrics_path.exists() and config:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        for variant in config.get("variants", []):
            for branch in config.get("branches", []):
                for seed in config.get("seeds", []):
                    for relative in (
                        f"models/{variant}/{branch}/seed_{seed}/latest.weights.h5",
                        f"models/{variant}/{branch}/seed_{seed}/best.weights.h5",
                        f"logs/{variant}_{branch}_seed_{seed}_history.csv",
                        f"logs/{variant}_{branch}_seed_{seed}_epoch_count.txt",
                    ):
                        if not (run_dir / relative).exists():
                            errors.append(f"missing output: {relative}")
                    if str(seed) not in metrics.get("results", {}).get(variant, {}).get(branch, {}):
                        errors.append(f"missing metrics for {variant}/{branch} seed {seed}")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    (run_dir / "check_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join(
        [
            "# E3-B7 Derived-Feature Ablation",
            "",
            "This is an isolated ablation on the frozen E3-B5 split. It does not change Android or production assets.",
            "",
            "## Settings",
            "",
            f"- Variants: {', '.join(config['variants'])}",
            f"- Branches: {', '.join(config['branches'])}",
            f"- Seeds: {', '.join(str(seed) for seed in config['seeds'])}",
            f"- Epochs per run command: {config['epochs']}",
            f"- Batch size: {config['batch_size']}",
            "",
            "## Full Run",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b7_feature_ablation run --run-dir "{run_dir}"',
            "```",
            "",
            "## Resume",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b7_feature_ablation run --run-dir "{run_dir}" --resume',
            "```",
            "",
            "## Check",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b7_feature_ablation check --run-dir "{run_dir}" --require-metrics',
            "```",
            "",
        ]
    )


def _metrics_markdown(metrics: dict[str, Any]) -> str:
    lines = [
        "# E3-B7 Derived-Feature Ablation Metrics",
        "",
        "Frozen E3-B5 split. Test accuracy is reporting-only after validation selection.",
        "",
        "| Variant | Branch | Seed | Best Val | Best Test | Latest Val | Latest Test |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for variant, branches in metrics["results"].items():
        for branch, seeds in branches.items():
            for seed, result in seeds.items():
                lines.append(
                    f"| {variant} | {branch} | {seed} | {result['best']['val']['accuracy']:.4f} | "
                    f"{result['best']['test']['accuracy']:.4f} | {result['latest']['val']['accuracy']:.4f} | "
                    f"{result['latest']['test']['accuracy']:.4f} |"
                )
    lines.extend(["", "## Summary", "", "```json", json.dumps(metrics.get("summary", {}), indent=2), "```", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="E3-B7 derived-feature ablation")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    prepare_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    prepare_parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    prepare_parser.add_argument("--variants", nargs="+", default=list(VARIANTS))
    prepare_parser.add_argument("--branches", nargs="+", default=list(BRANCH_KIND))
    prepare_parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    prepare_parser.add_argument("--batch-size", type=int, default=8)
    prepare_parser.add_argument("--epochs", type=int, default=12)
    prepare_parser.add_argument("--learning-rate", type=float, default=5e-4)
    prepare_parser.add_argument("--overwrite", action="store_true")

    smoke_parser = sub.add_parser("smoke")
    smoke_parser.add_argument("--run-dir", type=Path, required=True)
    smoke_parser.add_argument("--rows", type=int, default=8)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--run-dir", type=Path, required=True)
    run_parser.add_argument("--resume", action="store_true")

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--require-metrics", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "smoke":
            result = smoke(args)
        elif args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, KeyError, ValueError, OSError) as error:
        print(f"[rgb/e3-b7] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
