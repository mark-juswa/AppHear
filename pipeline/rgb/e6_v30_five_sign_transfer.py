"""E6 warm-start-only five-sign transfer experiment package.

Preparation and smoke testing are safe to run locally. Full three-seed training
is intentionally a separate developer-run command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from pipeline.rgb.e6_v30_five_sign_baseline import (
    CLASSES,
    SEEDS,
    _evaluate_model,
    _load_split,
    _per_class,
)


EXPERIMENT = "e6_v30_five_sign_warm_start_transfer_v1"
DEFAULT_BASELINE = Path(
    "artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_baseline_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_transfer_01"
)
DEFAULT_SOURCE = Path(
    "F:/ASL DATASET/ASL CITIZEN/derived/apphear3/runs/"
    "tcn_streaming_conversational_plus_local_pc_236_rtx3050_v30/best.keras"
)
CURRENT_ANDROID_TFLITE = Path("android/app/src/main/assets/streaming.tflite")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _training_config(
    output: Path, feature_root: Path, source: Path, seed: int
) -> dict[str, Any]:
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
            "rotation_deg": 10.0,
            "scale": 0.10,
            "noise_std": 0.01,
            "frame_mask_frac": 0.0,
        },
        "class_weighting": {"enabled": False, "weights": {}},
        "warm_start_from": str(source),
        "features_dir": str(feature_root),
        "vocab_dir": str(feature_root),
        "output_dir": str(output / "models" / f"seed_{seed}"),
    }


def _source_compatibility(source: Path) -> dict[str, Any]:
    import tensorflow as tf

    model = tf.keras.models.load_model(source, compile=False, safe_mode=False)
    weighted = {
        layer.name: [tuple(weight.shape) for weight in layer.get_weights()]
        for layer in model.layers
        if layer.get_weights() and layer.name != "logits_perframe"
    }
    expected = {
        "tcn0_conv1", "tcn0_ln1", "tcn0_conv2", "tcn0_ln2", "tcn0_proj",
        "tcn1_conv1", "tcn1_ln1", "tcn1_conv2", "tcn1_ln2",
        "tcn2_conv1", "tcn2_ln1", "tcn2_conv2", "tcn2_ln2",
        "tcn3_conv1", "tcn3_ln1", "tcn3_conv2", "tcn3_ln2",
    }
    errors = []
    if tuple(model.input_shape) != (None, 96, 258):
        errors.append(f"source input mismatch: {model.input_shape}")
    if tuple(model.output_shape) != (None, 96, 236):
        errors.append(f"source output mismatch: {model.output_shape}")
    if set(weighted) != expected:
        errors.append(f"source encoder layer mismatch: {sorted(set(weighted) ^ expected)}")
    return {
        "path": str(source.resolve()),
        "bytes": source.stat().st_size,
        "sha256": _sha256(source),
        "input_shape": list(model.input_shape[1:]),
        "output_shape": list(model.output_shape[1:]),
        "weighted_encoder_layers": weighted,
        "expected_copied_layers": len(expected),
        "errors": errors,
        "compatible": not errors,
    }


def prepare(args: argparse.Namespace) -> int:
    baseline = args.baseline.resolve()
    output = args.output.resolve()
    source = args.source.resolve()
    feature_root = (
        args.features.resolve() if args.features is not None else baseline / "dataset" / "features"
    )
    required = [feature_root / f"{split}.npz" for split in ("train", "val", "test_fresh", "test_historical")]
    required.append(feature_root / "vocab.json")
    missing = [str(path) for path in required if not path.is_file()]
    if not source.is_file():
        missing.append(str(source))
    if missing:
        raise FileNotFoundError(f"missing required inputs: {missing}")
    compatibility = _source_compatibility(source)
    if not compatibility["compatible"]:
        raise ValueError(f"incompatible source checkpoint: {compatibility['errors']}")
    output.mkdir(parents=True, exist_ok=True)
    for seed in SEEDS:
        config = _training_config(output, feature_root, source, seed)
        path = output / "config" / f"train_seed_{seed}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    source_exported_tflite = source.parent / "android_candidate_assets" / "streaming.tflite"
    lineage = {
        "experiment": EXPERIMENT,
        "baseline_run": str(baseline),
        "source_checkpoint": compatibility,
        "production_lineage": {
            "source_exported_tflite": str(source_exported_tflite),
            "source_exported_tflite_sha256": (
                _sha256(source_exported_tflite) if source_exported_tflite.is_file() else None
            ),
            "current_android_tflite": str(CURRENT_ANDROID_TFLITE.resolve()),
            "current_android_tflite_sha256": (
                _sha256(CURRENT_ANDROID_TFLITE) if CURRENT_ANDROID_TFLITE.is_file() else None
            ),
            "tflite_hashes_match": (
                source_exported_tflite.is_file()
                and CURRENT_ANDROID_TFLITE.is_file()
                and _sha256(source_exported_tflite) == _sha256(CURRENT_ANDROID_TFLITE)
            ),
        },
        "feature_files": {
            path.name: {"path": str(path.resolve()), "sha256": _sha256(path)}
            for path in required
        },
        "controlled_change": "warm_start_from only",
        "unchanged": [
            "v3.0 [96,258] features", "five classes", "splits", "TCN architecture",
            "augmentation", "optimizer", "epochs", "three seeds", "acceptance gates",
        ],
        "prohibited": ["Android export", "production asset replacement", "negative gate", "RGB"],
    }
    _write_json(output / "source_checkpoint_lineage.json", lineage)
    _write_json(
        output / "pilot_config.json",
        {
            "experiment": EXPERIMENT,
            "classes": CLASSES,
            "seeds": SEEDS,
            "input_shape": [96, 258],
            "source_checkpoint_sha256": compatibility["sha256"],
            "feature_root": str(feature_root),
            "expected_copied_layers": compatibility["expected_copied_layers"],
            "gates": {
                "mean_fresh_top1_min": 0.80,
                "minimum_seed_fresh_top1_min": 0.70,
                "mean_per_class_fresh_recall_min": 0.70,
                "minimum_seed_per_class_fresh_recall_min": 0.50,
            },
        },
    )
    readme = f"""# E6 Five-Sign Warm-Start Transfer Run

Controlled change: initialize the 17 weighted causal-encoder layers from the verified broader
236-class checkpoint. The five-class head remains new. No class weighting or split changes.

Source SHA-256: `{compatibility['sha256']}`

Run smoke first, then use `train` only after reviewing the smoke report. This run is diagnostic
and must never be exported to Android.
"""
    (output / "README_RUN.md").write_text(readme, encoding="utf-8")
    print(json.dumps({"run_dir": str(output), "source": compatibility, "passed": True}, indent=2))
    return 0


def smoke(args: argparse.Namespace) -> int:
    import tensorflow as tf

    from model.train_streaming import _build_and_compile, load_stream_config, warm_start_encoder

    config_path = args.run_dir / "config" / "train_seed_101.yaml"
    cfg = load_stream_config(config_path)
    model = _build_and_compile(96, 258, len(CLASSES), cfg)
    copied = warm_start_encoder(model, cfg.warm_start_from)
    source = tf.keras.models.load_model(cfg.warm_start_from, compile=False, safe_mode=False)
    source_layers = {layer.name: layer for layer in source.layers}
    equality = {}
    for layer in model.layers:
        if layer.name == "logits_perframe" or not layer.get_weights():
            continue
        reference = source_layers[layer.name].get_weights()
        equality[layer.name] = all(
            np.array_equal(left, right) for left, right in zip(layer.get_weights(), reference)
        )
    data = _load_split(cfg.features_dir, "train")
    x = data["X"][:2].astype(np.float32)
    y = data["y"][:2].astype(np.int32)
    mask = data["frame_mask"][:2].astype(np.float32)
    before = model.predict(x, verbose=0)
    loss = model.train_on_batch(x, np.repeat(y[:, None], 96, axis=1), sample_weight=mask)
    smoke_path = args.run_dir / "smoke" / "warm_start_smoke.keras"
    smoke_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(smoke_path)
    reloaded = tf.keras.models.load_model(smoke_path, compile=False, safe_mode=False)
    after = reloaded.predict(x[:1], verbose=0)
    expected = json.loads((args.run_dir / "pilot_config.json").read_text(encoding="utf-8"))[
        "expected_copied_layers"
    ]
    result = {
        "copied_layers": copied,
        "expected_copied_layers": expected,
        "all_encoder_weights_exact_before_training": all(equality.values()),
        "encoder_weight_checks": equality,
        "forward_shape": list(before.shape),
        "reload_shape": list(after.shape),
        "one_training_step_loss": np.asarray(loss).tolist(),
        "passed": bool(
            copied == expected
            and all(equality.values())
            and before.shape == (2, 96, len(CLASSES))
            and after.shape == (1, 96, len(CLASSES))
            and np.isfinite(before).all()
            and np.isfinite(after).all()
        ),
    }
    _write_json(args.run_dir / "smoke" / "smoke_summary.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


def train(args: argparse.Namespace) -> int:
    from model.train_streaming import run as train_streaming

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


def evaluate(args: argparse.Namespace) -> int:
    import tensorflow as tf

    baseline_metrics = json.loads(
        (args.baseline / "metrics" / "metrics.json").read_text(encoding="utf-8")
    )
    pilot = json.loads((args.run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    feature_root = Path(pilot["feature_root"])
    results = {}
    for seed in SEEDS:
        results[str(seed)] = {}
        for checkpoint in ("latest", "best", "final"):
            path = args.run_dir / "models" / f"seed_{seed}" / f"{checkpoint}.keras"
            if not path.is_file():
                raise FileNotFoundError(path)
            model = tf.keras.models.load_model(path, compile=False, safe_mode=False)
            results[str(seed)][checkpoint] = _evaluate_model(model, feature_root, 32)
            stress_path = feature_root / "validation_variant_stress.npz"
            if stress_path.is_file():
                from eval.streaming import predict_aggregate

                stress = _load_split(feature_root, "validation_variant_stress")
                probs, pf_acc, last_acc = predict_aggregate(
                    model,
                    stress["X"].astype(np.float32),
                    stress["frame_mask"].astype(bool),
                    stress["y"].astype(np.int32),
                    stress["lengths"].astype(np.int32),
                    32,
                )
                predicted = probs.argmax(axis=1)
                results[str(seed)][checkpoint]["validation_variant_stress"] = {
                    "count": len(stress["y"]),
                    "clip_top1": float((predicted == stress["y"]).mean()),
                    "per_frame_accuracy": pf_acc,
                    "last_frame_accuracy": last_acc,
                    "per_class": _per_class(probs, stress["y"]),
                }
    fresh = [results[str(seed)]["latest"]["test_fresh"] for seed in SEEDS]
    mean_top1 = float(np.mean([item["clip_top1"] for item in fresh]))
    min_top1 = float(np.min([item["clip_top1"] for item in fresh]))
    mean_recalls = {
        label: float(np.mean([item["per_class"][label]["recall"] for item in fresh]))
        for label in CLASSES
    }
    min_recalls = {
        label: float(np.min([item["per_class"][label]["recall"] for item in fresh]))
        for label in CLASSES
    }
    gates = json.loads((args.run_dir / "pilot_config.json").read_text(encoding="utf-8"))["gates"]
    passed = (
        mean_top1 >= gates["mean_fresh_top1_min"]
        and min_top1 >= gates["minimum_seed_fresh_top1_min"]
        and min(mean_recalls.values()) >= gates["mean_per_class_fresh_recall_min"]
        and min(min_recalls.values()) >= gates["minimum_seed_per_class_fresh_recall_min"]
    )
    summary = {
        "primary_checkpoint": "latest",
        "mean_fresh_top1": mean_top1,
        "minimum_seed_fresh_top1": min_top1,
        "mean_fresh_recall_by_class": mean_recalls,
        "minimum_seed_fresh_recall_by_class": min_recalls,
        "from_scratch_mean_fresh_top1": baseline_metrics["mean_fresh_top1"],
        "gain_over_from_scratch": mean_top1 - baseline_metrics["mean_fresh_top1"],
        "gates": gates,
        "passed": passed,
        "decision": "transfer_gate_passed" if passed else "transfer_no_go",
        "results": results,
    }
    _write_json(args.run_dir / "metrics" / "metrics.json", summary)
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, indent=2))
    return 0


def check(args: argparse.Namespace) -> int:
    required = ["pilot_config.json", "source_checkpoint_lineage.json", "README_RUN.md"]
    if args.require_smoke:
        required.append("smoke/smoke_summary.json")
    if args.require_metrics:
        required.append("metrics/metrics.json")
    errors = [name for name in required if not (args.run_dir / name).is_file()]
    if not errors and args.require_smoke:
        smoke_data = json.loads((args.run_dir / "smoke" / "smoke_summary.json").read_text(encoding="utf-8"))
        if not smoke_data.get("passed"):
            errors.append("smoke did not pass")
    result = {"run_dir": str(args.run_dir.resolve()), "passed": not errors, "errors": errors}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    prep.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prep.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    prep.add_argument("--features", type=Path)
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
    eval_parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
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
