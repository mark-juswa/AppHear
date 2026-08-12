"""E6-5 bounded KNOW/HELLO temporal-specialist package.

Preparation and smoke testing are local. Full two-branch, three-seed training is
an explicit developer-run step. Nothing in this module writes Android assets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml

from pipeline.features.landmark_geometry import GEOMETRY_DIM, SCHEMA_ID
from pipeline.rgb.e6_v30_five_sign_baseline import CLASSES as PRIMARY_CLASSES
from pipeline.rgb.e6_v30_five_sign_baseline import SEEDS, _load_split


EXPERIMENT = "e6_5_know_hello_specialist_v1"
PAIR_CLASSES = ("HELLO", "KNOW")
PRIMARY_IDS = np.asarray([PRIMARY_CLASSES.index(label) for label in PAIR_CLASSES], dtype=np.int32)
SPLITS = ("train", "val", "validation_variant_stress", "test_fresh", "test_historical")
EVAL_SPLITS = ("val", "validation_variant_stress", "test_fresh", "test_historical")
BRANCHES = ("v30_tcn_specialist", "geometry_tcn_specialist")

DEFAULT_V30_FEATURES = Path(
    "artifacts/recognition_upgrade/e6_baseline/e6_v30_validation_repair_01/dataset/features"
)
DEFAULT_GEOMETRY_FEATURES = Path(
    "artifacts/recognition_upgrade/e6_landmark_geometry/e6_2_geometry_01/dataset/features"
)
DEFAULT_V30_MODELS = Path(
    "artifacts/recognition_upgrade/e6_baseline/"
    "e6_v30_five_sign_transfer_repaired_val_01/models"
)
DEFAULT_GEOMETRY_MODELS = Path(
    "artifacts/recognition_upgrade/e6_landmark_geometry/e6_2_geometry_01/models"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e6_specialists/e6_5_know_hello_specialist_01"
)

GATES = {
    "mean_fresh_pair_accuracy_min": 0.90,
    "minimum_seed_fresh_pair_accuracy_min": 0.85,
    "mean_fresh_member_recall_min": 0.85,
    "minimum_seed_fresh_member_recall_min": 0.75,
    "mean_stress_pair_accuracy_min": 0.85,
    "mean_stress_hello_recall_min": 0.95,
    "mean_stress_know_recall_min": 0.70,
    "mean_historical_pair_accuracy_min": 0.90,
    "mean_historical_know_recall_min": 0.80,
    "mean_fresh_gain_over_primary_min": 0.10,
    "mean_stress_gain_over_primary_min": 0.15,
    "maximum_fresh_pair_accuracy_seed_std": 0.05,
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


def _filter_pair_payload(data: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    original_y = data["y"].astype(np.int32)
    keep = np.isin(original_y, PRIMARY_IDS)
    if not keep.any():
        raise ValueError("split contains no HELLO/KNOW rows")
    remapped = np.full(original_y.shape, -1, dtype=np.int32)
    remapped[original_y == PRIMARY_IDS[0]] = 0
    remapped[original_y == PRIMARY_IDS[1]] = 1
    payload = {key: value[keep] for key, value in data.items() if value.ndim > 0 and len(value) == len(original_y)}
    for key, value in data.items():
        if key not in payload and key != "y":
            payload[key] = value
    payload["original_y"] = original_y[keep]
    payload["y"] = remapped[keep]
    return payload


def _validate_source_split(data: dict[str, np.ndarray], split: str, feature_dim: int) -> None:
    required = {"X", "frame_mask", "lengths", "y", "participant_ids", "sample_ids", "source_ids"}
    missing = required.difference(data)
    if missing:
        raise ValueError(f"{split}: missing keys {sorted(missing)}")
    if tuple(data["X"].shape[1:]) != (96, feature_dim):
        raise ValueError(f"{split}: expected [N,96,{feature_dim}], got {data['X'].shape}")
    if data["frame_mask"].shape != data["X"].shape[:2]:
        raise ValueError(f"{split}: frame-mask shape mismatch")
    if not np.isfinite(data["X"]).all():
        raise ValueError(f"{split}: non-finite feature values")


def _save_pair_split(source: Path, output: Path, split: str, feature_dim: int) -> dict[str, Any]:
    data = _load_split(source, split)
    _validate_source_split(data, split, feature_dim)
    payload = _filter_pair_payload(data)
    if feature_dim == GEOMETRY_DIM:
        schema = str(np.asarray(data.get("schema_id", "")).item())
        if schema != SCHEMA_ID:
            raise ValueError(f"{split}: geometry schema mismatch: {schema!r}")
    output.mkdir(parents=True, exist_ok=True)
    target = output / f"{split}.npz"
    np.savez_compressed(target, **payload)
    return {
        "source": str((source / f"{split}.npz").resolve()),
        "source_sha256": _sha256(source / f"{split}.npz"),
        "output": str(target.resolve()),
        "output_sha256": _sha256(target),
        "shape": list(payload["X"].shape),
        "class_counts": {
            PAIR_CLASSES[class_id]: int(count)
            for class_id, count in sorted(Counter(payload["y"].tolist()).items())
        },
        "participant_counts": dict(sorted(Counter(payload["participant_ids"].astype(str)).items())),
        "source_counts": dict(sorted(Counter(payload["source_ids"].astype(str)).items())),
    }


def _training_config(
    run_dir: Path,
    branch: str,
    feature_root: Path,
    warm_start: Path,
    seed: int,
) -> dict[str, Any]:
    augment: dict[str, Any] = {
        "enabled": True,
        "rotation_deg": 10.0,
        "scale": 0.10,
        "noise_std": 0.01,
        "frame_mask_frac": 0.0,
    }
    if branch == "geometry_tcn_specialist":
        augment["contract"] = SCHEMA_ID
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
        "augment": augment,
        "class_weighting": {"enabled": False, "weights": {}},
        "warm_start_from": str(warm_start.resolve()),
        "features_dir": str(feature_root.resolve()),
        "vocab_dir": str(feature_root.resolve()),
        "output_dir": str((run_dir / "models" / branch / f"seed_{seed}").resolve()),
    }


def _checkpoint_report(path: Path, expected_dim: int) -> dict[str, Any]:
    import tensorflow as tf

    model = tf.keras.models.load_model(path, compile=False, safe_mode=False)
    errors = []
    if tuple(model.input_shape) != (None, 96, expected_dim):
        errors.append(f"input mismatch {model.input_shape}")
    if tuple(model.output_shape) != (None, 96, 5):
        errors.append(f"output mismatch {model.output_shape}")
    return {
        "path": str(path.resolve()),
        "sha256": _sha256(path),
        "input_shape": list(model.input_shape[1:]),
        "output_shape": list(model.output_shape[1:]),
        "errors": errors,
        "compatible": not errors,
    }


def _assert_pair_alignment(v30_root: Path, geometry_root: Path) -> dict[str, Any]:
    reports = {}
    for split in SPLITS:
        v30 = _load_split(v30_root, split)
        geometry = _load_split(geometry_root, split)
        keys = ("y", "original_y", "sample_ids", "participant_ids", "source_ids", "lengths", "frame_mask")
        mismatches = [key for key in keys if not np.array_equal(v30[key], geometry[key])]
        if mismatches:
            raise ValueError(f"{split}: v3/geometry pair alignment mismatch: {mismatches}")
        if not np.array_equal(v30["X"], geometry["X"][..., :258]):
            raise ValueError(f"{split}: geometry base channels differ from v3")
        reports[split] = {"rows": len(v30["y"]), "aligned": True}
    return reports


def _runbook(run_dir: Path) -> str:
    module = "pipeline.rgb.e6_5_know_hello_specialist"
    return f"""# E6-5 KNOW/HELLO Specialist Run

This package trains two offline binary temporal specialists. It does not modify Android or the
production recognizer. Run the smoke and check before full training.

```powershell
.\\.venv\\Scripts\\python.exe -m {module} smoke --run-dir \"{run_dir}\"
.\\.venv\\Scripts\\python.exe -m {module} check --run-dir \"{run_dir}\" --require-smoke
.\\.venv\\Scripts\\python.exe -m {module} train --run-dir \"{run_dir}\"
.\\.venv\\Scripts\\python.exe -m {module} evaluate --run-dir \"{run_dir}\"
.\\.venv\\Scripts\\python.exe -m {module} check --run-dir \"{run_dir}\" --require-smoke --require-metrics
```

Resume an interrupted training run by adding `--resume` to `train`.
"""


def prepare(args: argparse.Namespace) -> int:
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        if not args.overwrite:
            raise FileExistsError(f"output is not empty: {output}; use a new run or --overwrite")
        shutil.rmtree(output)

    source_roots = {
        "v30_tcn_specialist": args.v30_features.resolve(),
        "geometry_tcn_specialist": args.geometry_features.resolve(),
    }
    model_roots = {
        "v30_tcn_specialist": args.v30_models.resolve(),
        "geometry_tcn_specialist": args.geometry_models.resolve(),
    }
    dims = {"v30_tcn_specialist": 258, "geometry_tcn_specialist": GEOMETRY_DIM}
    missing = []
    for branch in BRANCHES:
        missing.extend(
            str(source_roots[branch] / f"{split}.npz")
            for split in SPLITS
            if not (source_roots[branch] / f"{split}.npz").is_file()
        )
        missing.extend(
            str(model_roots[branch] / f"seed_{seed}" / "latest.keras")
            for seed in SEEDS
            if not (model_roots[branch] / f"seed_{seed}" / "latest.keras").is_file()
        )
    if missing:
        raise FileNotFoundError(f"missing E6-5 inputs: {missing}")

    output.mkdir(parents=True, exist_ok=True)
    reports: dict[str, Any] = {}
    checkpoint_reports: dict[str, Any] = {}
    for branch in BRANCHES:
        feature_root = output / "dataset" / branch
        reports[branch] = {
            split: _save_pair_split(source_roots[branch], feature_root, split, dims[branch])
            for split in SPLITS
        }
        (feature_root / "vocab.json").write_text(
            json.dumps({label: index for index, label in enumerate(PAIR_CLASSES)}, indent=2),
            encoding="utf-8",
        )
        checkpoint_reports[branch] = {}
        for seed in SEEDS:
            checkpoint = model_roots[branch] / f"seed_{seed}" / "latest.keras"
            checkpoint_reports[branch][str(seed)] = _checkpoint_report(checkpoint, dims[branch])
            if not checkpoint_reports[branch][str(seed)]["compatible"]:
                raise ValueError(checkpoint_reports[branch][str(seed)])
            config = _training_config(output, branch, feature_root, checkpoint, seed)
            path = output / "config" / branch / f"train_seed_{seed}.yaml"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    alignment = _assert_pair_alignment(
        output / "dataset" / "v30_tcn_specialist",
        output / "dataset" / "geometry_tcn_specialist",
    )
    pilot = {
        "experiment": EXPERIMENT,
        "pair_classes": PAIR_CLASSES,
        "primary_class_ids": PRIMARY_IDS.tolist(),
        "branches": BRANCHES,
        "seeds": SEEDS,
        "splits": SPLITS,
        "fixed_checkpoint_policy": "latest",
        "gates": GATES,
        "split_reports": reports,
        "alignment": alignment,
        "checkpoint_reports": checkpoint_reports,
        "prohibited": ["RGB", "fusion", "Android", "TFLite export", "routing integration"],
        "passed": True,
    }
    _write_json(output / "pilot_config.json", pilot)
    _write_json(output / "source_lineage.json", {"features": reports, "checkpoints": checkpoint_reports})
    (output / "README_RUN.md").write_text(_runbook(output), encoding="utf-8")
    print(json.dumps({"run_dir": str(output), "pair": PAIR_CLASSES, "passed": True}, indent=2))
    return 0


def _validate_prepared(run_dir: Path) -> None:
    pilot = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    if pilot.get("experiment") != EXPERIMENT or tuple(pilot.get("pair_classes", [])) != PAIR_CLASSES:
        raise ValueError("E6-5 pilot contract mismatch")
    for branch, dim in ((BRANCHES[0], 258), (BRANCHES[1], GEOMETRY_DIM)):
        root = run_dir / "dataset" / branch
        for split in SPLITS:
            data = _load_split(root, split)
            _validate_source_split(data, split, dim)
            if not set(np.unique(data["y"]).tolist()).issubset({0, 1}):
                raise ValueError(f"{branch}/{split}: non-binary labels")
            if "original_y" not in data:
                raise ValueError(f"{branch}/{split}: missing original_y")
    _assert_pair_alignment(run_dir / "dataset" / BRANCHES[0], run_dir / "dataset" / BRANCHES[1])


def smoke(args: argparse.Namespace) -> int:
    import tensorflow as tf

    from model.train_streaming import _build_and_compile, load_stream_config, warm_start_encoder

    run_dir = args.run_dir.resolve()
    _validate_prepared(run_dir)
    result: dict[str, Any] = {"branches": {}}
    for branch, dim in ((BRANCHES[0], 258), (BRANCHES[1], GEOMETRY_DIM)):
        cfg = load_stream_config(run_dir / "config" / branch / "train_seed_101.yaml")
        tf.keras.utils.set_random_seed(101)
        model = _build_and_compile(96, dim, 2, cfg)
        copied = warm_start_encoder(model, cfg.warm_start_from)
        data = _load_split(run_dir / "dataset" / branch, "train")
        x = data["X"][:4].astype(np.float32)
        y = data["y"][:4].astype(np.int32)
        mask = data["frame_mask"][:4].astype(np.float32)
        before = model.predict(x, verbose=0)
        loss = model.train_on_batch(x, np.repeat(y[:, None], 96, axis=1), sample_weight=mask)
        target = run_dir / "smoke" / f"{branch}.keras"
        target.parent.mkdir(parents=True, exist_ok=True)
        model.save(target)
        reloaded = tf.keras.models.load_model(target, compile=False, safe_mode=False)
        after = reloaded.predict(x[:1], verbose=0)
        branch_result = {
            "copied_encoder_layers": copied,
            "input_shape": list(x.shape),
            "forward_shape": list(before.shape),
            "reload_shape": list(after.shape),
            "one_training_step_loss": np.asarray(loss).tolist(),
            "finite": bool(np.isfinite(before).all() and np.isfinite(after).all()),
        }
        branch_result["passed"] = bool(
            copied == 17
            and branch_result["forward_shape"] == [4, 96, 2]
            and branch_result["reload_shape"] == [1, 96, 2]
            and branch_result["finite"]
        )
        result["branches"][branch] = branch_result

    primary = tf.keras.models.load_model(
        Path(json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))["checkpoint_reports"]
             [BRANCHES[0]]["101"]["path"]),
        compile=False,
        safe_mode=False,
    )
    primary_data = _load_split(run_dir / "dataset" / BRANCHES[0], "train")
    primary_output = primary.predict(primary_data["X"][:2].astype(np.float32), verbose=0)
    result["primary_forward_shape"] = list(primary_output.shape)
    result["passed"] = bool(
        all(item["passed"] for item in result["branches"].values())
        and result["primary_forward_shape"] == [2, 96, 5]
    )
    _write_json(run_dir / "smoke" / "smoke_summary.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


def train(args: argparse.Namespace) -> int:
    from model.train_streaming import run as train_streaming

    run_dir = args.run_dir.resolve()
    _validate_prepared(run_dir)
    failures = []
    completed = []
    skipped_completed = []
    for branch in BRANCHES:
        for seed in SEEDS:
            final_path = run_dir / "models" / branch / f"seed_{seed}" / "final.keras"
            if args.resume and final_path.is_file():
                skipped_completed.append({"branch": branch, "seed": seed})
                continue
            code = train_streaming(
                run_dir / "config" / branch / f"train_seed_{seed}.yaml",
                False,
                args.epochs,
                args.resume,
            )
            if code:
                failures.append({"branch": branch, "seed": seed, "exit_code": code})
                break
            completed.append({"branch": branch, "seed": seed})
        if failures:
            break
    _write_json(
        run_dir / "logs" / "training_summary.json",
        {
            "branches": BRANCHES,
            "seeds": SEEDS,
            "resume": args.resume,
            "completed": completed,
            "skipped_completed": skipped_completed,
            "failures": failures,
            "passed": not failures,
        },
    )
    return 0 if not failures else 1


def _aggregate(model: Any, data: dict[str, np.ndarray], batch_size: int = 32) -> np.ndarray:
    from eval.streaming import predict_aggregate

    probs, _pf_acc, _last_acc = predict_aggregate(
        model,
        data["X"].astype(np.float32),
        data["frame_mask"].astype(bool),
        data["y"].astype(np.int32),
        data["lengths"].astype(np.int32),
        batch_size,
    )
    return probs


def _pair_report(prediction: np.ndarray, truth: np.ndarray) -> dict[str, Any]:
    prediction = np.asarray(prediction, dtype=np.int32)
    truth = np.asarray(truth, dtype=np.int32)
    if prediction.shape != truth.shape:
        raise ValueError("prediction/truth shape mismatch")
    per_class = {}
    confusion = np.zeros((2, 2), dtype=np.int64)
    for expected, guessed in zip(truth, prediction):
        if guessed in (0, 1):
            confusion[int(expected), int(guessed)] += 1
    for class_id, label in enumerate(PAIR_CLASSES):
        mask = truth == class_id
        per_class[label] = {
            "count": int(mask.sum()),
            "correct": int((prediction[mask] == class_id).sum()),
            "recall": float((prediction[mask] == class_id).mean()) if mask.any() else None,
        }
    return {
        "count": len(truth),
        "accuracy": float((prediction == truth).mean()),
        "per_class": per_class,
        "confusion_matrix": confusion.tolist(),
    }


def _primary_controls(primary_probs: np.ndarray, pair_data: dict[str, np.ndarray]) -> dict[str, Any]:
    truth_pair = pair_data["y"].astype(np.int32)
    truth_primary = pair_data["original_y"].astype(np.int32)
    full_pred = primary_probs.argmax(axis=1).astype(np.int32)
    full_as_pair = np.full(full_pred.shape, -1, dtype=np.int32)
    full_as_pair[full_pred == PRIMARY_IDS[0]] = 0
    full_as_pair[full_pred == PRIMARY_IDS[1]] = 1
    restricted = primary_probs[:, PRIMARY_IDS].argmax(axis=1).astype(np.int32)
    full_report = _pair_report(full_as_pair, truth_pair)
    full_report["route_coverage"] = float(np.isin(full_pred, PRIMARY_IDS).mean())
    full_report["full_primary_correct"] = int((full_pred == truth_primary).sum())
    return {
        "five_way_primary": full_report,
        "pair_restricted_primary": _pair_report(restricted, truth_pair),
        "full_prediction": full_pred,
    }


def _specialist_view(
    primary_probs: np.ndarray,
    specialist_probs: np.ndarray,
    pair_data: dict[str, np.ndarray],
) -> dict[str, Any]:
    truth = pair_data["y"].astype(np.int32)
    primary_full = primary_probs.argmax(axis=1).astype(np.int32)
    specialist_pred = specialist_probs.argmax(axis=1).astype(np.int32)
    routed = np.full(truth.shape, -1, dtype=np.int32)
    route = np.isin(primary_full, PRIMARY_IDS)
    routed[route] = specialist_pred[route]
    result = {
        "direct_specialist": _pair_report(specialist_pred, truth),
        "routed_specialist": _pair_report(routed, truth),
        "route_coverage": float(route.mean()),
    }
    return result


def _mean_metric(rows: Iterable[dict[str, Any]], *keys: str) -> float:
    values = []
    for row in rows:
        value: Any = row
        for key in keys:
            value = value[key]
        values.append(float(value))
    return float(np.mean(values))


def _summarize_branch(
    branch_rows: list[dict[str, Any]],
    primary_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    by_split = {split: [row[split]["routed_specialist"] for row in branch_rows] for split in EVAL_SPLITS}
    primary_by_split = {
        split: [row[split]["five_way_primary"] for row in primary_rows] for split in EVAL_SPLITS
    }
    fresh = by_split["test_fresh"]
    stress = by_split["validation_variant_stress"]
    historical = by_split["test_historical"]
    fresh_accuracy = np.asarray([row["accuracy"] for row in fresh], dtype=np.float64)
    summary = {
        "mean_fresh_pair_accuracy": float(fresh_accuracy.mean()),
        "minimum_seed_fresh_pair_accuracy": float(fresh_accuracy.min()),
        "fresh_pair_accuracy_seed_std": float(fresh_accuracy.std()),
        "mean_fresh_recall": {
            label: _mean_metric(fresh, "per_class", label, "recall") for label in PAIR_CLASSES
        },
        "minimum_seed_fresh_recall": {
            label: float(min(row["per_class"][label]["recall"] for row in fresh))
            for label in PAIR_CLASSES
        },
        "mean_stress_pair_accuracy": _mean_metric(stress, "accuracy"),
        "mean_stress_recall": {
            label: _mean_metric(stress, "per_class", label, "recall") for label in PAIR_CLASSES
        },
        "mean_historical_pair_accuracy": _mean_metric(historical, "accuracy"),
        "mean_historical_recall": {
            label: _mean_metric(historical, "per_class", label, "recall") for label in PAIR_CLASSES
        },
    }
    primary_fresh = _mean_metric(primary_by_split["test_fresh"], "accuracy")
    primary_stress = _mean_metric(primary_by_split["validation_variant_stress"], "accuracy")
    summary["mean_fresh_gain_over_primary"] = summary["mean_fresh_pair_accuracy"] - primary_fresh
    summary["mean_stress_gain_over_primary"] = summary["mean_stress_pair_accuracy"] - primary_stress
    checks = {
        "fresh_pair_mean": summary["mean_fresh_pair_accuracy"] >= GATES["mean_fresh_pair_accuracy_min"],
        "fresh_pair_min_seed": summary["minimum_seed_fresh_pair_accuracy"] >= GATES["minimum_seed_fresh_pair_accuracy_min"],
        "fresh_member_mean": min(summary["mean_fresh_recall"].values()) >= GATES["mean_fresh_member_recall_min"],
        "fresh_member_min_seed": min(summary["minimum_seed_fresh_recall"].values()) >= GATES["minimum_seed_fresh_member_recall_min"],
        "stress_pair_mean": summary["mean_stress_pair_accuracy"] >= GATES["mean_stress_pair_accuracy_min"],
        "stress_hello": summary["mean_stress_recall"]["HELLO"] >= GATES["mean_stress_hello_recall_min"],
        "stress_know": summary["mean_stress_recall"]["KNOW"] >= GATES["mean_stress_know_recall_min"],
        "historical_pair": summary["mean_historical_pair_accuracy"] >= GATES["mean_historical_pair_accuracy_min"],
        "historical_know": summary["mean_historical_recall"]["KNOW"] >= GATES["mean_historical_know_recall_min"],
        "fresh_gain": summary["mean_fresh_gain_over_primary"] >= GATES["mean_fresh_gain_over_primary_min"],
        "stress_gain": summary["mean_stress_gain_over_primary"] >= GATES["mean_stress_gain_over_primary_min"],
        "seed_stability": summary["fresh_pair_accuracy_seed_std"] <= GATES["maximum_fresh_pair_accuracy_seed_std"],
    }
    summary["gate_checks"] = checks
    summary["passed"] = all(checks.values())
    return summary


def evaluate(args: argparse.Namespace) -> int:
    import tensorflow as tf

    run_dir = args.run_dir.resolve()
    _validate_prepared(run_dir)
    pilot = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    primary_rows = []
    results: dict[str, Any] = {branch: {} for branch in BRANCHES}
    for seed in SEEDS:
        primary_path = Path(pilot["checkpoint_reports"][BRANCHES[0]][str(seed)]["path"])
        primary_model = tf.keras.models.load_model(primary_path, compile=False, safe_mode=False)
        primary_seed: dict[str, Any] = {}
        primary_probs: dict[str, np.ndarray] = {}
        for split in EVAL_SPLITS:
            pair_data = _load_split(run_dir / "dataset" / BRANCHES[0], split)
            probs = _aggregate(primary_model, pair_data)
            primary_probs[split] = probs
            controls = _primary_controls(probs, pair_data)
            controls.pop("full_prediction")
            primary_seed[split] = controls
        primary_rows.append(primary_seed)

        for branch in BRANCHES:
            results[branch][str(seed)] = {}
            for checkpoint in ("latest", "best", "final"):
                path = run_dir / "models" / branch / f"seed_{seed}" / f"{checkpoint}.keras"
                if not path.is_file():
                    raise FileNotFoundError(path)
                specialist = tf.keras.models.load_model(path, compile=False, safe_mode=False)
                checkpoint_result = {}
                for split in EVAL_SPLITS:
                    pair_data = _load_split(run_dir / "dataset" / branch, split)
                    specialist_probs = _aggregate(specialist, pair_data)
                    checkpoint_result[split] = _specialist_view(
                        primary_probs[split], specialist_probs, pair_data
                    )
                results[branch][str(seed)][checkpoint] = checkpoint_result

    latest_by_branch = {
        branch: [results[branch][str(seed)]["latest"] for seed in SEEDS] for branch in BRANCHES
    }
    summaries = {
        branch: _summarize_branch(latest_by_branch[branch], primary_rows) for branch in BRANCHES
    }
    primary_summary = {
        split: {
            "mean_five_way_pair_accuracy": _mean_metric(
                [row[split]["five_way_primary"] for row in primary_rows], "accuracy"
            ),
            "mean_pair_restricted_accuracy": _mean_metric(
                [row[split]["pair_restricted_primary"] for row in primary_rows], "accuracy"
            ),
            "mean_route_coverage": _mean_metric(
                [row[split]["five_way_primary"] for row in primary_rows], "route_coverage"
            ),
        }
        for split in EVAL_SPLITS
    }

    passing = [branch for branch in BRANCHES if summaries[branch]["passed"]]
    selected = None
    decision = "e6_5_no_go_data_or_variant_repair"
    if "v30_tcn_specialist" in passing:
        selected = "v30_tcn_specialist"
        decision = "e6_5_v30_specialist_provisional_go"
        if "geometry_tcn_specialist" in passing:
            v30_worst = min(
                summaries["v30_tcn_specialist"][key]
                for key in ("mean_fresh_pair_accuracy", "mean_stress_pair_accuracy", "mean_historical_pair_accuracy")
            )
            geometry_worst = min(
                summaries["geometry_tcn_specialist"][key]
                for key in ("mean_fresh_pair_accuracy", "mean_stress_pair_accuracy", "mean_historical_pair_accuracy")
            )
            historical_loss = (
                summaries["v30_tcn_specialist"]["mean_historical_pair_accuracy"]
                - summaries["geometry_tcn_specialist"]["mean_historical_pair_accuracy"]
            )
            if geometry_worst >= v30_worst + 0.03 and historical_loss <= 0.03:
                selected = "geometry_tcn_specialist"
                decision = "e6_5_geometry_specialist_provisional_go_requires_parity_plan"
    elif "geometry_tcn_specialist" in passing:
        selected = "geometry_tcn_specialist"
        decision = "e6_5_geometry_specialist_provisional_go_requires_parity_plan"

    payload = {
        "experiment": EXPERIMENT,
        "fixed_checkpoint_policy": "latest",
        "primary_controls": primary_summary,
        "gates": GATES,
        "branch_summaries": summaries,
        "selected_branch": selected,
        "passed": selected is not None,
        "decision": decision,
        "warning": "Diagnostic only: fresh/stress views were previously inspected; no production claim or Android promotion.",
        "primary_results": {str(seed): row for seed, row in zip(SEEDS, primary_rows)},
        "results": results,
    }
    _write_json(run_dir / "metrics" / "metrics.json", payload)
    print(json.dumps({key: value for key, value in payload.items() if key not in {"results", "primary_results"}}, indent=2))
    return 0


def check(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.resolve()
    required = ["pilot_config.json", "source_lineage.json", "README_RUN.md"]
    for branch in BRANCHES:
        required.extend(f"dataset/{branch}/{split}.npz" for split in SPLITS)
        required.append(f"dataset/{branch}/vocab.json")
        required.extend(f"config/{branch}/train_seed_{seed}.yaml" for seed in SEEDS)
    if args.require_smoke:
        required.append("smoke/smoke_summary.json")
    if args.require_metrics:
        required.append("metrics/metrics.json")
        required.extend(
            f"models/{branch}/seed_{seed}/{checkpoint}.keras"
            for branch in BRANCHES
            for seed in SEEDS
            for checkpoint in ("latest", "best", "final")
        )
    errors = [name for name in required if not (run_dir / name).is_file()]
    if not errors:
        try:
            _validate_prepared(run_dir)
        except (FileNotFoundError, KeyError, ValueError) as exc:
            errors.append(str(exc))
    if args.require_smoke and not errors:
        smoke_data = json.loads((run_dir / "smoke" / "smoke_summary.json").read_text(encoding="utf-8"))
        if not smoke_data.get("passed"):
            errors.append("smoke gate failed")
    report = {"run_dir": str(run_dir), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", report)
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    prep = commands.add_parser("prepare")
    prep.add_argument("--v30-features", type=Path, default=DEFAULT_V30_FEATURES)
    prep.add_argument("--geometry-features", type=Path, default=DEFAULT_GEOMETRY_FEATURES)
    prep.add_argument("--v30-models", type=Path, default=DEFAULT_V30_MODELS)
    prep.add_argument("--geometry-models", type=Path, default=DEFAULT_GEOMETRY_MODELS)
    prep.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prep.add_argument("--overwrite", action="store_true")
    prep.set_defaults(func=prepare)

    smoke_parser = commands.add_parser("smoke")
    smoke_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    smoke_parser.set_defaults(func=smoke)

    train_parser = commands.add_parser("train")
    train_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    train_parser.add_argument("--epochs", type=int)
    train_parser.add_argument("--resume", action="store_true")
    train_parser.set_defaults(func=train)

    evaluate_parser = commands.add_parser("evaluate")
    evaluate_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    evaluate_parser.set_defaults(func=evaluate)

    check_parser = commands.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    check_parser.add_argument("--require-smoke", action="store_true")
    check_parser.add_argument("--require-metrics", action="store_true")
    check_parser.set_defaults(func=check)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        return int(args.func(args))
    except (FileNotFoundError, FileExistsError, KeyError, ValueError) as error:
        print(f"[rgb/e6-5] ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
