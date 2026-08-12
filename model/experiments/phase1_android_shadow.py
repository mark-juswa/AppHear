"""Export the frozen Phase 1 three-seed TCN ensemble for Android shadow evaluation.

Outputs remain outside Android assets. This module never reads protected test data,
changes production assets, or authorizes candidate predictions to affect the UI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = "phase1_android_shadow_export_v1"
DEFAULT_PHASE1_RUN = ROOT / (
    "artifacts/recognition_upgrade/phase1_full_vocab/tcn_comparison_01"
)
DEFAULT_DATASET = ROOT / "artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1"
DEFAULT_OUTPUT = ROOT / "artifacts/recognition_upgrade/phase1_android_shadow/export_01"
ANDROID_VOCAB = ROOT / "android/app/src/main/assets/vocab.json"
SEEDS = (101, 202, 303)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _load_split(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with np.load(path, allow_pickle=False) as data:
        return (
            np.asarray(data["X"], dtype=np.float32),
            np.asarray(data["y"], dtype=np.int32),
            np.asarray(data["frame_mask"], dtype=bool),
        )


def _last_valid(probabilities: np.ndarray, frame_mask: np.ndarray) -> np.ndarray:
    lengths = frame_mask.sum(axis=1).astype(np.int32)
    if np.any(lengths <= 0):
        raise ValueError("validation includes an empty feature sequence")
    return np.asarray(
        probabilities[np.arange(len(probabilities)), lengths - 1], dtype=np.float32
    )


def _representative_samples(x: np.ndarray, count: int, seed: int) -> Iterator[list[np.ndarray]]:
    rng = np.random.default_rng(seed)
    chosen = rng.choice(len(x), size=min(count, len(x)), replace=False)
    for index in chosen:
        yield [x[index : index + 1]]


def _export_int8_float_io(model: Any, representative_x: np.ndarray, seed: int) -> bytes:
    import tensorflow as tf

    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = lambda: _representative_samples(
        representative_x, 256, seed
    )
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.float32
    converter.inference_output_type = tf.float32
    return bytes(converter.convert())


def _export_float32(model: Any) -> bytes:
    import tensorflow as tf

    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
    return bytes(converter.convert())


def _export_model(
    model: Any, representative_x: np.ndarray, seed: int, quantization: str
) -> bytes:
    if quantization == "int8_float_io":
        return _export_int8_float_io(model, representative_x, seed)
    if quantization == "float32":
        return _export_float32(model)
    raise ValueError(f"unsupported quantization: {quantization}")


def _tflite_predict(model_path: Path, x: np.ndarray) -> tuple[np.ndarray, list[float]]:
    import tensorflow as tf

    interpreter = tf.lite.Interpreter(model_path=str(model_path), num_threads=2)
    input_info = interpreter.get_input_details()[0]
    output_info = interpreter.get_output_details()[0]
    interpreter.resize_tensor_input(input_info["index"], [1, 96, 258], strict=True)
    interpreter.allocate_tensors()
    outputs = []
    latency_ms = []
    for sample in x:
        interpreter.set_tensor(input_info["index"], sample[None].astype(np.float32))
        started = time.perf_counter()
        interpreter.invoke()
        latency_ms.append((time.perf_counter() - started) * 1000.0)
        outputs.append(interpreter.get_tensor(output_info["index"])[0].copy())
    return np.asarray(outputs, dtype=np.float32), latency_ms


def _assert_frozen_contract(phase1_run: Path, dataset: Path) -> dict[str, Any]:
    freeze_path = phase1_run / "config/selection_freeze.json"
    freeze = _read_json(freeze_path)
    if freeze.get("frozen_branch") != "production_streaming_tcn":
        raise ValueError("Phase 1 frozen branch is not production_streaming_tcn")
    if tuple(int(seed) for seed in freeze.get("seeds", [])) != SEEDS:
        raise ValueError("Phase 1 frozen seeds differ from 101/202/303")
    expected = {int(item["seed"]): item for item in freeze["checkpoints"]}
    for seed in SEEDS:
        checkpoint = phase1_run / f"models/production_streaming_tcn/seed_{seed}/best.keras"
        if _sha256(checkpoint) != expected[seed]["sha256"]:
            raise ValueError(f"seed {seed} checkpoint hash drift")
    experiment = _read_json(phase1_run / "config/experiment.json")
    for split in ("train", "val"):
        if _sha256(dataset / f"{split}.npz") != experiment["dataset_hashes"][split]:
            raise ValueError(f"{split} tensor hash drift")
    vocab_hash = _sha256(dataset / "vocab.json")
    if vocab_hash != _sha256(ANDROID_VOCAB):
        raise ValueError("Phase 1 and Android vocabulary hashes differ")
    return freeze


def export(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    if args.output.exists():
        raise FileExistsError(f"output already exists: {args.output}")
    freeze = _assert_frozen_contract(args.phase1_run, args.dataset)
    x_train, _, _ = _load_split(args.dataset / "train.npz")
    x_val, y_val, mask_val = _load_split(args.dataset / "val.npz")
    parity_count = min(args.parity_rows, len(x_val))
    parity_x = x_val[:parity_count]
    parity_y = y_val[:parity_count]
    parity_mask = mask_val[:parity_count]
    args.output.mkdir(parents=True)
    models_dir = args.output / "models"
    models_dir.mkdir()

    keras_clip: list[np.ndarray] = []
    tflite_clip: list[np.ndarray] = []
    models = []
    for seed in SEEDS:
        checkpoint = args.phase1_run / (
            f"models/production_streaming_tcn/seed_{seed}/best.keras"
        )
        model = tf.keras.models.load_model(checkpoint, compile=False, safe_mode=False)
        keras_frames = np.asarray(model.predict(parity_x, batch_size=32, verbose=0))
        keras_seed_clip = _last_valid(keras_frames, parity_mask)
        model_path = models_dir / f"phase1_shadow_seed_{seed}.tflite"
        model_path.write_bytes(
            _export_model(model, x_train, seed, args.quantization)
        )
        tflite_frames, latency = _tflite_predict(model_path, parity_x)
        if tuple(tflite_frames.shape[1:]) != (96, 236):
            raise ValueError(f"seed {seed} TFLite output shape={list(tflite_frames.shape)}")
        tflite_seed_clip = _last_valid(tflite_frames, parity_mask)
        keras_clip.append(keras_seed_clip)
        tflite_clip.append(tflite_seed_clip)
        models.append(
            {
                "seed": seed,
                "source_checkpoint_sha256": _sha256(checkpoint),
                "asset_name": model_path.name,
                "tflite_sha256": _sha256(model_path),
                "bytes": model_path.stat().st_size,
                "input_shape": [1, 96, 258],
                "output_shape": [1, 96, 236],
                "host_latency_ms": {
                    "p50": float(np.percentile(latency, 50)),
                    "p95": float(np.percentile(latency, 95)),
                },
            }
        )

    keras_ensemble = np.mean(np.stack(keras_clip), axis=0)
    tflite_ensemble = np.mean(np.stack(tflite_clip), axis=0)
    keras_top1 = np.argmax(keras_ensemble, axis=1)
    tflite_top1 = np.argmax(tflite_ensemble, axis=1)
    parity = {
        "rows": parity_count,
        "mean_abs_probability_difference": float(
            np.mean(np.abs(keras_ensemble - tflite_ensemble))
        ),
        "max_abs_probability_difference": float(
            np.max(np.abs(keras_ensemble - tflite_ensemble))
        ),
        "ensemble_argmax_agreement": float(np.mean(keras_top1 == tflite_top1)),
        "keras_validation_subset_top1": float(np.mean(keras_top1 == parity_y)),
        "tflite_validation_subset_top1": float(np.mean(tflite_top1 == parity_y)),
    }
    parity["absolute_top1_delta"] = abs(
        parity["keras_validation_subset_top1"] - parity["tflite_validation_subset_top1"]
    )
    parity_passed = bool(
        parity["mean_abs_probability_difference"] <= 0.01
        and parity["ensemble_argmax_agreement"] >= 0.98
        and parity["absolute_top1_delta"] <= 0.01
    )
    manifest = {
        "experiment": EXPERIMENT,
        "candidate_id": "phase1_production_tcn_ensemble_101_202_303",
        "schema_version": "3.0",
        "feature_dim": 258,
        "time_window": 96,
        "num_classes": 236,
        "ensemble": "arithmetic_mean_probabilities",
        "quantization": args.quantization,
        "models": models,
        "vocab_asset": "phase1_shadow_vocab.json",
        "vocab_sha256": _sha256(args.dataset / "vocab.json"),
        "selection_freeze_sha256": _sha256(
            args.phase1_run / "config/selection_freeze.json"
        ),
        "selection_freeze": freeze,
        "parity": parity,
        "parity_gates": {
            "mean_abs_probability_difference_max": 0.01,
            "ensemble_argmax_agreement_min": 0.98,
            "absolute_top1_delta_max": 0.01,
        },
        "shadow_only": True,
        "may_commit": False,
        "may_update_sentence_or_ui": False,
        "protected_test_accessed": False,
        "production_authorized": False,
        "passed": parity_passed,
    }
    shutil.copy2(args.dataset / "vocab.json", args.output / "phase1_shadow_vocab.json")
    _write_json(args.output / "phase1_shadow_manifest.json", manifest)
    print(json.dumps(manifest, indent=2))
    if not parity_passed:
        raise ValueError("Phase 1 shadow TFLite parity gate failed")
    return manifest


def check(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    manifest_path = args.output / "phase1_shadow_manifest.json"
    if not manifest_path.is_file():
        errors.append("missing phase1_shadow_manifest.json")
        manifest: dict[str, Any] = {}
    else:
        manifest = _read_json(manifest_path)
    if manifest and not manifest.get("passed"):
        errors.append("manifest parity gate did not pass")
    if manifest.get("protected_test_accessed") is not False:
        errors.append("protected test access state is not false")
    if manifest.get("may_commit") is not False:
        errors.append("shadow candidate may_commit must be false")
    for item in manifest.get("models", []):
        path = args.output / "models" / item["asset_name"]
        if not path.is_file():
            errors.append(f"missing {path.name}")
        elif _sha256(path) != item["tflite_sha256"]:
            errors.append(f"hash mismatch {path.name}")
    vocab = args.output / "phase1_shadow_vocab.json"
    if not vocab.is_file():
        errors.append("missing phase1_shadow_vocab.json")
    elif manifest and _sha256(vocab) != manifest["vocab_sha256"]:
        errors.append("shadow vocabulary hash mismatch")
    report = {
        "run_dir": str(args.output.resolve()),
        "models": len(manifest.get("models", [])),
        "errors": errors,
        "passed": not errors,
        "production_authorized": False,
    }
    print(json.dumps(report, indent=2))
    if errors:
        raise ValueError("; ".join(errors))
    return report


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Phase 1 Android shadow export")
    sub = root.add_subparsers(dest="command", required=True)
    export_parser = sub.add_parser("export")
    export_parser.add_argument("--phase1-run", type=Path, default=DEFAULT_PHASE1_RUN)
    export_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    export_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    export_parser.add_argument("--parity-rows", type=int, default=128)
    export_parser.add_argument(
        "--quantization",
        choices=("int8_float_io", "float32"),
        default="int8_float_io",
    )
    export_parser.set_defaults(func=export)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    check_parser.set_defaults(func=check)
    return root


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
