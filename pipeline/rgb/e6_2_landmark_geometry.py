"""E6-2 bounded landmark-geometry control package.

Preparation and smoke testing are local. Full three-seed training remains an
explicit user-run step. Nothing in this module writes Android assets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from pipeline.features.contract import FEATURE_DIM
from pipeline.features.landmark_geometry import GEOMETRY_DIM, SCHEMA_ID, build_landmark_geometry
from pipeline.rgb.e6_v30_five_sign_baseline import CLASSES, SEEDS, _evaluate_model, _load_split

EXPERIMENT = "e6_2_landmark_geometry_control_v1"
DEFAULT_REPAIRED = Path(
    "artifacts/recognition_upgrade/e6_baseline/e6_v30_validation_repair_01"
)
DEFAULT_CONTROL = Path(
    "artifacts/recognition_upgrade/e6_baseline/"
    "e6_v30_five_sign_transfer_repaired_val_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e6_landmark_geometry/e6_2_geometry_01"
)
DEFAULT_SOURCE = Path(
    "F:/ASL DATASET/ASL CITIZEN/derived/apphear3/runs/"
    "tcn_streaming_conversational_plus_local_pc_236_rtx3050_v30/best.keras"
)
SPLITS = ("train", "val", "validation_variant_stress", "test_fresh", "test_historical")
CONTROL = {
    "fresh_top1": 0.888888888888889,
    "stress_top1": 0.6973,
    "historical_top1": 0.9630,
    "fresh_recall": {
        "GOOD": 0.9833333333333333,
        "HELLO": 1.0,
        "SORRY": 0.9666666666666667,
        "HAVE": 0.9333333333333332,
        "KNOW": 0.5611111111111111,
    },
}
GATES = {
    "mean_fresh_top1_min": 0.9089,
    "mean_fresh_know_recall_min": 0.70,
    "minimum_seed_fresh_know_recall_min": 0.60,
    "mean_stress_know_recall_min": 0.30,
    "mean_stress_top1_min": 0.7273,
    "maximum_stable_class_fresh_recall_loss": 0.03,
    "mean_historical_top1_min": 0.9330,
    "maximum_fresh_top1_seed_std": 0.03,
}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _training_config(run_dir: Path, feature_root: Path, initializer: Path, seed: int) -> dict[str, Any]:
    return {
        "model": {
            "type": "tcn",
            "blocks": 4,
            "channels": 64,
            "dilations": [1, 2, 4, 8],
            "kernel": 3,
            "dropout": 0.3,
        },
        "train": {
            "seed": seed,
            "batch_size": 32,
            "epochs": 40,
            "learning_rate": 0.0005,
            "early_stop_patience": 8,
            "weight_decay": 0.0001,
        },
        "augment": {
            "enabled": True,
            "contract": SCHEMA_ID,
            "rotation_deg": 10.0,
            "scale": 0.10,
            "noise_std": 0.01,
            "frame_mask_frac": 0.0,
        },
        "class_weighting": {"enabled": False, "weights": {}},
        "warm_start_from": str(initializer),
        "features_dir": str(feature_root),
        "vocab_dir": str(feature_root),
        "output_dir": str(run_dir / "models" / f"seed_{seed}"),
    }


def _derive_split(source_path: Path, output_path: Path) -> dict[str, Any]:
    with np.load(source_path, allow_pickle=False) as data:
        required = {"X", "frame_mask", "lengths", "y", "participant_ids"}
        missing = required.difference(data.files)
        if missing:
            raise ValueError(f"{source_path} missing keys: {sorted(missing)}")
        base = data["X"].astype(np.float32)
        mask = data["frame_mask"].astype(bool)
        geometry, schema = build_landmark_geometry(base, mask)
        payload = {key: data[key] for key in data.files}
    payload["X"] = geometry
    payload["schema_id"] = np.asarray(SCHEMA_ID)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, **payload)
    return {
        "source": str(source_path.resolve()),
        "source_sha256": _sha256(source_path),
        "output": str(output_path.resolve()),
        "output_sha256": _sha256(output_path),
        "rows": int(geometry.shape[0]),
        "shape": list(geometry.shape),
        "base_channels_exact": bool(np.array_equal(geometry[..., :FEATURE_DIM], base)),
        "finite": bool(np.isfinite(geometry).all()),
        "padded_zero": bool(np.all(geometry[~mask] == 0.0)),
        "schema": schema,
    }


def _validate_geometry_features(feature_root: Path) -> None:
    for split in SPLITS:
        path = feature_root / f"{split}.npz"
        with np.load(path, allow_pickle=False) as data:
            if "schema_id" not in data.files or str(data["schema_id"].item()) != SCHEMA_ID:
                raise ValueError(f"{split}: missing or mismatched schema_id")
            if tuple(data["X"].shape[1:]) != (96, GEOMETRY_DIM):
                raise ValueError(f"{split}: expected [N,96,{GEOMETRY_DIM}], got {data['X'].shape}")


def _copy_zero_extended(control: Any, candidate: Any) -> dict[str, Any]:
    source_layers = {layer.name: layer for layer in control.layers}
    exact = []
    extended = []
    errors = []
    for target in candidate.layers:
        target_weights = target.get_weights()
        if not target_weights:
            continue
        source = source_layers.get(target.name)
        if source is None:
            errors.append(f"missing source layer {target.name}")
            continue
        source_weights = source.get_weights()
        if [item.shape for item in source_weights] == [item.shape for item in target_weights]:
            target.set_weights(source_weights)
            exact.append(target.name)
            continue
        if target.name not in {"tcn0_conv1", "tcn0_proj"} or len(target_weights) != 2:
            errors.append(f"unsupported shape change in {target.name}")
            continue
        source_kernel, source_bias = source_weights
        target_kernel = np.zeros_like(target_weights[0])
        if source_kernel.shape[0] != target_kernel.shape[0] or source_kernel.shape[2] != target_kernel.shape[2]:
            errors.append(f"kernel axis mismatch in {target.name}")
            continue
        target_kernel[:, : source_kernel.shape[1], :] = source_kernel
        target.set_weights([target_kernel, source_bias])
        extended.append(target.name)
    return {"exact_layers": exact, "zero_extended_layers": extended, "errors": errors}


def _build_initializers(
    run_dir: Path, feature_root: Path, source_checkpoint: Path
) -> dict[str, Any]:
    import tensorflow as tf

    from model.train_streaming import _build_and_compile, load_stream_config, warm_start_encoder

    train = _load_split(feature_root, "train")
    base_train = _load_split(run_dir / "source_v30", "train")
    reports = {}
    for seed in SEEDS:
        config_path = run_dir / "config" / f"train_seed_{seed}.yaml"
        cfg = load_stream_config(config_path)
        tf.keras.utils.set_random_seed(seed)
        control = _build_and_compile(96, FEATURE_DIM, len(CLASSES), cfg)
        broad_layers = warm_start_encoder(control, source_checkpoint)
        tf.keras.utils.set_random_seed(seed)
        candidate = _build_and_compile(96, GEOMETRY_DIM, len(CLASSES), cfg)
        copy_report = _copy_zero_extended(control, candidate)
        base_x = base_train["X"][:2].astype(np.float32)
        candidate_x = train["X"][:2].astype(np.float32)
        control_probs = control.predict(base_x, verbose=0)
        candidate_probs = candidate.predict(candidate_x, verbose=0)
        max_abs = float(np.max(np.abs(control_probs - candidate_probs)))
        initializer = run_dir / "initialization" / f"seed_{seed}.keras"
        initializer.parent.mkdir(parents=True, exist_ok=True)
        candidate.save(initializer)
        reports[str(seed)] = {
            "broad_encoder_layers_copied": broad_layers,
            **copy_report,
            "control_params": int(control.count_params()),
            "candidate_params": int(candidate.count_params()),
            "parameter_increase": int(candidate.count_params() - control.count_params()),
            "max_abs_initial_logit_difference": max_abs,
            "initializer": str(initializer.resolve()),
            "initializer_sha256": _sha256(initializer),
            "passed": bool(
                broad_layers == 17
                and copy_report["zero_extended_layers"] == ["tcn0_conv1", "tcn0_proj"]
                and not copy_report["errors"]
                and candidate.count_params() - control.count_params() == 47616
                and max_abs <= 1e-6
            ),
        }
    return reports


def _runbook(run_dir: Path) -> str:
    module = "pipeline.rgb.e6_2_landmark_geometry"
    return f"""# E6-2 Landmark Geometry Run

This is an offline five-sign experiment. It does not modify Android or production assets.

## Full training (long; user runs)

```powershell
cd "F:\\ASL DATASET\\5. Apphear3"
.\\.venv\\Scripts\\python.exe -m {module} train --run-dir "{run_dir}"
```

Resume after interruption by adding `--resume`.

## Evaluate and check

```powershell
.\\.venv\\Scripts\\python.exe -m {module} evaluate --run-dir "{run_dir}"
.\\.venv\\Scripts\\python.exe -m {module} check --run-dir "{run_dir}" --require-smoke --require-metrics
```

Do not export any checkpoint from this run to Android.
"""


def prepare(args: argparse.Namespace) -> int:
    repaired = args.repaired.resolve()
    control = args.control.resolve()
    source = args.source.resolve()
    output = args.output.resolve()
    source_features = repaired / "dataset" / "features"
    repair_report_path = repaired / "validation_repair_report.json"
    required = [source_features / f"{split}.npz" for split in SPLITS]
    required.extend(
        [source_features / "vocab.json", repair_report_path, control / "metrics" / "metrics.json", source]
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing E6-2 inputs: {missing}")
    repair_report = json.loads(repair_report_path.read_text(encoding="utf-8"))
    baseline_config_path = Path(repair_report["baseline_run"]) / "pilot_config.json"
    if not baseline_config_path.is_file():
        raise FileNotFoundError(f"missing source schema manifest: {baseline_config_path}")
    baseline_config = json.loads(baseline_config_path.read_text(encoding="utf-8"))
    if baseline_config.get("schema_version") != "3.0" or baseline_config.get("input_shape") != [96, 258]:
        raise ValueError("repaired source is not pinned to v3.0 [96,258]")
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite only for a disposable run: {output}")
    for relative in ("config", "dataset/features", "initialization", "logs", "metrics", "models", "smoke", "source_v30"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    split_reports = {}
    for split in SPLITS:
        source_path = source_features / f"{split}.npz"
        geometry_path = output / "dataset" / "features" / f"{split}.npz"
        split_reports[split] = _derive_split(source_path, geometry_path)
        shutil.copy2(source_path, output / "source_v30" / f"{split}.npz")
    shutil.copy2(source_features / "vocab.json", output / "dataset" / "features" / "vocab.json")
    shutil.copy2(source_features / "vocab.json", output / "source_v30" / "vocab.json")

    feature_root = output / "dataset" / "features"
    for seed in SEEDS:
        initializer = output / "initialization" / f"seed_{seed}.keras"
        config = _training_config(output, feature_root, initializer, seed)
        (output / "config" / f"train_seed_{seed}.yaml").write_text(
            yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
        )
    initializers = _build_initializers(output, feature_root, source)
    _validate_geometry_features(feature_root)
    schema = split_reports["train"]["schema"]
    _write_json(output / "feature_schema.json", schema)
    _write_json(
        output / "initialization" / "zero_extension_report.json",
        {"seeds": initializers, "passed": all(item["passed"] for item in initializers.values())},
    )
    pilot = {
        "experiment": EXPERIMENT,
        "run_dir": str(output),
        "schema_id": SCHEMA_ID,
        "input_shape": [96, GEOMETRY_DIM],
        "classes": CLASSES,
        "seeds": SEEDS,
        "source_repaired_run": str(repaired),
        "source_schema_manifest": str(baseline_config_path.resolve()),
        "source_schema_version": baseline_config["schema_version"],
        "frozen_control_run": str(control),
        "broad_source_checkpoint": str(source),
        "broad_source_sha256": _sha256(source),
        "split_reports": split_reports,
        "initialization": initializers,
        "gates": GATES,
        "prohibited": ["Android export", "production replacement", "E6-3", "RGB", "specialists"],
        "passed": all(item["passed"] for item in initializers.values()),
    }
    _write_json(output / "pilot_config.json", pilot)
    (output / "README_RUN.md").write_text(_runbook(output), encoding="utf-8")
    print(json.dumps({"run_dir": str(output), "input_shape": [96, GEOMETRY_DIM], "passed": pilot["passed"]}, indent=2))
    return 0 if pilot["passed"] else 1


def smoke(args: argparse.Namespace) -> int:
    import tensorflow as tf

    from model.augment import AugmentConfig
    from model.train_streaming import _build_and_compile, load_stream_config, warm_start_encoder
    from pipeline.features.landmark_geometry import augment_landmark_geometry_batch

    run_dir = args.run_dir.resolve()
    _validate_geometry_features(run_dir / "dataset" / "features")
    cfg = load_stream_config(run_dir / "config" / "train_seed_101.yaml")
    initializer = run_dir / "initialization" / "seed_101.keras"
    model = _build_and_compile(96, GEOMETRY_DIM, len(CLASSES), cfg)
    copied = warm_start_encoder(model, initializer)
    reference = tf.keras.models.load_model(initializer, compile=False, safe_mode=False)
    data = _load_split(run_dir / "dataset" / "features", "train")
    x = data["X"][:2].astype(np.float32)
    y = data["y"][:2].astype(np.int32)
    mask = data["frame_mask"][:2].astype(bool)
    before = model.predict(x, verbose=0)
    reference_probs = reference.predict(x, verbose=0)
    augmented = augment_landmark_geometry_batch(
        x,
        AugmentConfig(cfg.rotation_deg, cfg.scale, cfg.noise_std, cfg.frame_mask_frac),
        np.random.default_rng(cfg.seed),
        mask,
    )
    loss = model.train_on_batch(
        augmented,
        np.repeat(y[:, None], 96, axis=1),
        sample_weight=mask.astype(np.float32),
    )
    saved = run_dir / "smoke" / "geometry_smoke.keras"
    saved.parent.mkdir(parents=True, exist_ok=True)
    model.save(saved)
    reloaded = tf.keras.models.load_model(saved, compile=False, safe_mode=False)
    after = reloaded.predict(x[:1], verbose=0)
    init_report = json.loads(
        (run_dir / "initialization" / "zero_extension_report.json").read_text(encoding="utf-8")
    )
    result = {
        "copied_initializer_layers": copied,
        "expected_weighted_layers": 18,
        "initial_model_max_abs_difference": float(np.max(np.abs(before - reference_probs))),
        "input_shape": list(x.shape),
        "forward_shape": list(before.shape),
        "reload_shape": list(after.shape),
        "augmented_shape": list(augmented.shape),
        "augmentation_finite": bool(np.isfinite(augmented).all()),
        "augmentation_padding_zero": bool(np.all(augmented[~mask] == 0.0)),
        "one_training_step_loss": np.asarray(loss).tolist(),
        "zero_extension_report_passed": bool(init_report["passed"]),
    }
    result["passed"] = bool(
        copied == 18
        and result["initial_model_max_abs_difference"] <= 1e-6
        and result["forward_shape"] == [2, 96, 5]
        and result["reload_shape"] == [1, 96, 5]
        and result["augmentation_finite"]
        and result["augmentation_padding_zero"]
        and result["zero_extension_report_passed"]
    )
    _write_json(run_dir / "smoke" / "smoke_summary.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


def train(args: argparse.Namespace) -> int:
    from model.train_streaming import run as train_streaming

    _validate_geometry_features(args.run_dir / "dataset" / "features")
    failures = []
    for seed in SEEDS:
        code = train_streaming(
            args.run_dir / "config" / f"train_seed_{seed}.yaml",
            False,
            args.epochs,
            args.resume,
        )
        if code:
            failures.append({"seed": seed, "exit_code": code})
            break
    _write_json(
        args.run_dir / "logs" / "training_summary.json",
        {"seeds": SEEDS, "resume": args.resume, "failures": failures, "passed": not failures},
    )
    return 0 if not failures else 1


def _stress_report(model: Any, feature_root: Path) -> dict[str, Any]:
    from eval.streaming import predict_aggregate
    from pipeline.rgb.e6_v30_five_sign_baseline import _per_class

    data = _load_split(feature_root, "validation_variant_stress")
    probs, pf_acc, last_acc = predict_aggregate(
        model,
        data["X"].astype(np.float32),
        data["frame_mask"].astype(bool),
        data["y"].astype(np.int32),
        data["lengths"].astype(np.int32),
        32,
    )
    prediction = probs.argmax(axis=1)
    return {
        "count": len(data["y"]),
        "clip_top1": float(np.mean(prediction == data["y"])),
        "per_frame_accuracy": pf_acc,
        "last_frame_accuracy": last_acc,
        "per_class": _per_class(probs, data["y"]),
    }


def evaluate(args: argparse.Namespace) -> int:
    import tensorflow as tf

    feature_root = args.run_dir / "dataset" / "features"
    _validate_geometry_features(feature_root)
    results = {}
    for seed in SEEDS:
        results[str(seed)] = {}
        for checkpoint in ("latest", "best", "final"):
            path = args.run_dir / "models" / f"seed_{seed}" / f"{checkpoint}.keras"
            if not path.is_file():
                raise FileNotFoundError(path)
            model = tf.keras.models.load_model(path, compile=False, safe_mode=False)
            report = _evaluate_model(model, feature_root, 32)
            report["validation_variant_stress"] = _stress_report(model, feature_root)
            results[str(seed)][checkpoint] = report

    latest = [results[str(seed)]["latest"] for seed in SEEDS]
    fresh = [item["test_fresh"] for item in latest]
    stress = [item["validation_variant_stress"] for item in latest]
    historical = [item["test_historical"] for item in latest]
    fresh_top1 = np.asarray([item["clip_top1"] for item in fresh], dtype=np.float64)
    fresh_recalls = {
        label: float(np.mean([item["per_class"][label]["recall"] for item in fresh]))
        for label in CLASSES
    }
    min_fresh_recalls = {
        label: float(np.min([item["per_class"][label]["recall"] for item in fresh]))
        for label in CLASSES
    }
    stress_top1 = float(np.mean([item["clip_top1"] for item in stress]))
    stress_know = float(np.mean([item["per_class"]["KNOW"]["recall"] for item in stress]))
    historical_top1 = float(np.mean([item["clip_top1"] for item in historical]))
    stable_losses = {
        label: CONTROL["fresh_recall"][label] - fresh_recalls[label]
        for label in ("GOOD", "HELLO", "SORRY", "HAVE")
    }
    gate_checks = {
        "fresh_top1": float(np.mean(fresh_top1)) >= GATES["mean_fresh_top1_min"],
        "fresh_know_mean": fresh_recalls["KNOW"] >= GATES["mean_fresh_know_recall_min"],
        "fresh_know_min_seed": min_fresh_recalls["KNOW"] >= GATES["minimum_seed_fresh_know_recall_min"],
        "stress_know_mean": stress_know >= GATES["mean_stress_know_recall_min"],
        "stress_top1": stress_top1 >= GATES["mean_stress_top1_min"],
        "stable_class_regression": max(stable_losses.values()) <= GATES["maximum_stable_class_fresh_recall_loss"],
        "historical_top1": historical_top1 >= GATES["mean_historical_top1_min"],
        "seed_stability": float(np.std(fresh_top1)) <= GATES["maximum_fresh_top1_seed_std"],
    }
    summary = {
        "experiment": EXPERIMENT,
        "primary_checkpoint": "latest",
        "control": CONTROL,
        "gates": GATES,
        "mean_fresh_top1": float(np.mean(fresh_top1)),
        "fresh_top1_seed_std": float(np.std(fresh_top1)),
        "mean_fresh_recall_by_class": fresh_recalls,
        "minimum_seed_fresh_recall_by_class": min_fresh_recalls,
        "mean_stress_top1": stress_top1,
        "mean_stress_know_recall": stress_know,
        "mean_historical_top1": historical_top1,
        "stable_class_fresh_recall_losses": stable_losses,
        "gate_checks": gate_checks,
        "passed": all(gate_checks.values()),
        "decision": "e6_2_geometry_go" if all(gate_checks.values()) else "e6_2_geometry_no_go",
        "results": results,
    }
    _write_json(args.run_dir / "metrics" / "metrics.json", summary)
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, indent=2))
    return 0


def check(args: argparse.Namespace) -> int:
    required = [
        "pilot_config.json",
        "feature_schema.json",
        "README_RUN.md",
        "initialization/zero_extension_report.json",
        *[f"dataset/features/{split}.npz" for split in SPLITS],
        *[f"initialization/seed_{seed}.keras" for seed in SEEDS],
    ]
    if args.require_smoke:
        required.append("smoke/smoke_summary.json")
    if args.require_metrics:
        required.append("metrics/metrics.json")
    errors = [name for name in required if not (args.run_dir / name).is_file()]
    if not errors:
        pilot = json.loads((args.run_dir / "pilot_config.json").read_text(encoding="utf-8"))
        if pilot.get("schema_id") != SCHEMA_ID or pilot.get("input_shape") != [96, GEOMETRY_DIM]:
            errors.append("E6-2 schema/input mismatch")
        if not pilot.get("passed"):
            errors.append("prepare/initialization gate failed")
        try:
            _validate_geometry_features(args.run_dir / "dataset" / "features")
        except (FileNotFoundError, KeyError, ValueError) as exc:
            errors.append(str(exc))
    if args.require_smoke and not errors:
        smoke_data = json.loads((args.run_dir / "smoke" / "smoke_summary.json").read_text(encoding="utf-8"))
        if not smoke_data.get("passed"):
            errors.append("smoke gate failed")
    report = {"run_dir": str(args.run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(args.run_dir / "check_report.json", report)
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--repaired", type=Path, default=DEFAULT_REPAIRED)
    prep.add_argument("--control", type=Path, default=DEFAULT_CONTROL)
    prep.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    prep.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prep.add_argument("--overwrite", action="store_true")
    prep.set_defaults(func=prepare)
    smoke_parser = sub.add_parser("smoke")
    smoke_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    smoke_parser.set_defaults(func=smoke)
    train_parser = sub.add_parser("train")
    train_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    train_parser.add_argument("--epochs", type=int)
    train_parser.add_argument("--resume", action="store_true")
    train_parser.set_defaults(func=train)
    eval_parser = sub.add_parser("evaluate")
    eval_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    eval_parser.set_defaults(func=evaluate)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    check_parser.add_argument("--require-smoke", action="store_true")
    check_parser.add_argument("--require-metrics", action="store_true")
    check_parser.set_defaults(func=check)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
