"""E6 clean v3.0 five-sign streaming-TCN baseline package.

Long extraction and training are developer-run. This module never exports to or
modifies Android production assets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml

from pipeline.extract.config import load_config as load_extract_config
from pipeline.extract.landmarks import LandmarkExtractor
from pipeline.features.contract import FEATURE_DIM, SCHEMA_VERSION, clip_features_realtimed
from pipeline.normalize.config import load_config as load_normalize_config


EXPERIMENT = "e6_v30_five_sign_streaming_tcn_baseline_v1"
CLASSES = ["GOOD", "HELLO", "SORRY", "HAVE", "KNOW"]
CLASS_TO_ID = {label: index for index, label in enumerate(CLASSES)}
ROLE_TO_SPLIT = {
    "train_positive": "train",
    "validation_positive": "val",
    "test_positive_fresh": "test_fresh",
    "test_positive_historical": "test_historical",
}
SEEDS = [101, 202, 303]
DEFAULT_ASSIGNMENT_RUN = Path(
    "artifacts/recognition_upgrade/product_core_data_readiness/"
    "e6_five_sign_assignment_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_baseline_01"
)
DEFAULT_EXTRACT_CONFIG = Path("pipeline/config/extract.yaml")
DEFAULT_NORMALIZE_CONFIG = Path("pipeline/config/normalize.yaml")
DEFAULT_DEPLOYED_MODEL = Path("android/app/src/main/assets/streaming.tflite")
DEFAULT_DEPLOYED_VOCAB = Path("android/app/src/main/assets/vocab.json")

MANIFEST_FIELDS = [
    "sample_id",
    "assignment_id",
    "split",
    "role",
    "class_id",
    "canonical_label",
    "source_dataset",
    "signer_group_id",
    "raw_video_path",
    "raw_video_sha256",
    "previous_experiment_usage",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _per_clip_path(run_dir: Path, sample_id: str) -> Path:
    return run_dir / "dataset" / "per_clip" / f"{sample_id}.npz"


def _extract_feature(
    row: dict[str, Any], extractor: LandmarkExtractor, normalize_config: Any
) -> dict[str, Any]:
    clip, meta = extractor.extract(Path(row["raw_video_path"]))
    release = int(clip.timestamps_ms.shape[0] - 1)
    if release < 0:
        raise ValueError("no frames extracted")
    feature, frame_mask, length, _params = clip_features_realtimed(
        clip.hands_image,
        clip.pose_image,
        0,
        release,
        normalize_config,
        96,
    )
    hand_present = clip.hand_score > 0.0
    hand_hit = float(np.mean(np.any(hand_present, axis=1))) if len(hand_present) else 0.0
    pose_hit = float(np.mean(clip.pose_score > 0.0)) if len(clip.pose_score) else 0.0
    return {
        "feature": feature.astype(np.float32),
        "frame_mask": frame_mask.astype(bool),
        "length": int(length),
        "native_frames": int(meta["n_frames"]),
        "native_fps": float(meta["native_fps"]),
        "hand_hit_rate": hand_hit,
        "pose_hit_rate": pose_hit,
    }


def _prepare_rows(assignment_path: Path) -> list[dict[str, Any]]:
    source = _read_csv(assignment_path)
    positives = [row for row in source if row.get("sample_kind") == "positive"]
    rows = []
    for index, row in enumerate(positives, start=1):
        label = row["canonical_label"]
        role = row["role"]
        if label not in CLASS_TO_ID:
            raise ValueError(f"unexpected positive class: {label}")
        if role not in ROLE_TO_SPLIT:
            raise ValueError(f"unexpected positive role: {role}")
        rows.append(
            {
                "sample_id": f"e6p_{index:05d}",
                "assignment_id": row["assignment_id"],
                "split": ROLE_TO_SPLIT[role],
                "role": role,
                "class_id": CLASS_TO_ID[label],
                "canonical_label": label,
                "source_dataset": row["source_dataset"],
                "signer_group_id": row["signer_group_id"],
                "raw_video_path": row["raw_video_path"],
                "raw_video_sha256": row["raw_video_sha256"],
                "previous_experiment_usage": row.get("previous_experiment_usage", ""),
            }
        )
    return rows


def _training_config(run_dir: Path, seed: int) -> dict[str, Any]:
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
        "warm_start_from": None,
        "features_dir": str((run_dir / "dataset" / "features").resolve()),
        "vocab_dir": str((run_dir / "dataset" / "features").resolve()),
        "output_dir": str((run_dir / "models" / f"seed_{seed}").resolve()),
    }


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    module = "pipeline.rgb.e6_v30_five_sign_baseline"
    return "\n".join(
        [
            "# E6 v3.0 Five-Sign Baseline",
            "",
            "This is an offline pilot. It does not modify Android or production assets.",
            "",
            "## Verified preparation",
            "",
            f"- Vocabulary: {', '.join(CLASSES)}",
            f"- Positive rows: {config['positive_rows']}",
            "- Model: deployed-family causal streaming TCN, trained from scratch",
            "- Primary checkpoint: latest; best/final are diagnostic",
            "",
            "## 1. Full positive extraction (long, resumable)",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m {module} extract-positive --run-dir "{run_dir}" --require-full',
            "```",
            "",
            "Re-run the same command to resume cached clips.",
            "",
            "## 2. Train three seeds (long, resumable)",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m {module} train --run-dir "{run_dir}"',
            "```",
            "",
            "Resume after interruption:",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m {module} train --run-dir "{run_dir}" --resume',
            "```",
            "",
            "## 3. Evaluate trained TCN and deployed 236-class control",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m {module} evaluate --run-dir "{run_dir}"',
            f'.\\.venv\\Scripts\\python.exe -m {module} evaluate-deployed --run-dir "{run_dir}"',
            f'.\\.venv\\Scripts\\python.exe -m {module} check --run-dir "{run_dir}" --require-smoke --require-full --require-metrics',
            "```",
            "",
            "Do not export or copy a model into Android from this run.",
            "",
        ]
    )


def prepare(args: argparse.Namespace) -> int:
    assignment_summary_path = args.assignment_run / "assignment_summary.json"
    assignment_path = args.assignment_run / "assignment_manifest.csv"
    assignment_summary = json.loads(assignment_summary_path.read_text(encoding="utf-8"))
    if not assignment_summary.get("gate", {}).get("passed"):
        raise ValueError("source assignment gate did not pass")
    if assignment_summary.get("vocabulary") != CLASSES:
        raise ValueError("source assignment vocabulary differs from five-sign contract")
    if args.output.exists() and any(args.output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {args.output}")
    for relative in (
        "config",
        "dataset/per_clip",
        "dataset/features",
        "logs",
        "metrics",
        "models",
        "smoke",
    ):
        (args.output / relative).mkdir(parents=True, exist_ok=True)

    rows = _prepare_rows(assignment_path)
    _write_csv(args.output / "positive_extraction_manifest.csv", rows, MANIFEST_FIELDS)
    _write_csv(
        args.output / "selected_classes.csv",
        ({"class_id": index, "gloss": label} for index, label in enumerate(CLASSES)),
        ["class_id", "gloss"],
    )
    (args.output / "dataset" / "features" / "vocab.json").write_text(
        json.dumps(CLASS_TO_ID, indent=2), encoding="utf-8"
    )
    for seed in SEEDS:
        (args.output / "config" / f"train_seed_{seed}.yaml").write_text(
            yaml.safe_dump(_training_config(args.output, seed), sort_keys=False),
            encoding="utf-8",
        )

    split_counts = Counter(row["split"] for row in rows)
    class_split_counts: dict[str, dict[str, int]] = defaultdict(dict)
    for label in CLASSES:
        for split in ROLE_TO_SPLIT.values():
            class_split_counts[label][split] = sum(
                row["canonical_label"] == label and row["split"] == split for row in rows
            )
    config = {
        "experiment": EXPERIMENT,
        "run_dir": str(args.output.resolve()),
        "scope": "clean raw-video re-extraction and five-sign streaming-TCN pilot",
        "schema_version": SCHEMA_VERSION,
        "input_shape": [96, FEATURE_DIM],
        "classes": CLASSES,
        "class_count": len(CLASSES),
        "positive_rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "class_split_counts": class_split_counts,
        "seeds": SEEDS,
        "extract_config": str(args.extract_config.resolve()),
        "normalize_config": str(args.normalize_config.resolve()),
        "assignment_run": str(args.assignment_run.resolve()),
        "input_hashes": {
            "assignment_manifest": _sha256(assignment_path),
            "assignment_summary": _sha256(assignment_summary_path),
            "extract_config": _sha256(args.extract_config),
            "normalize_config": _sha256(args.normalize_config),
        },
        "model_decision": {
            "primary": "causal streaming TCN matching deployed model family",
            "warm_start": False,
            "reason": "avoid old-checkpoint contamination and test repaired data honestly",
            "checkpoint_policy": "latest primary; best and final diagnostic",
        },
        "gates": {
            "mean_fresh_top1_min": 0.80,
            "minimum_seed_fresh_top1_min": 0.70,
            "mean_per_class_fresh_recall_min": 0.70,
            "minimum_seed_per_class_fresh_recall_min": 0.50,
        },
        "limitations": [
            "HAVE has four validation clips; validation is not production evidence.",
            "Fresh positive test has one signer.",
            "Negative assignment is preserved for a separate gate evaluation and is not a sixth softmax class.",
            "No Android export is authorized by this pilot.",
        ],
        "long_steps": ["extract-positive", "train"],
    }
    _write_json(args.output / "pilot_config.json", config)
    _write_json(args.output / "logs" / "prepare_summary.json", {**config, "passed": True})
    (args.output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    print(json.dumps(config, indent=2))
    return 0


def _select_smoke_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected = []
    for split in ("train", "val"):
        for label in CLASSES:
            candidates = [
                row for row in rows if row["split"] == split and row["canonical_label"] == label
            ]
            if not candidates:
                raise ValueError(f"smoke requires {label} in {split}")
            selected.append(candidates[0])
    return selected


def smoke(args: argparse.Namespace) -> int:
    import tensorflow as tf

    from model.model import build_streaming_classifier

    config = json.loads((args.run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    rows = _select_smoke_rows(_read_csv(args.run_dir / "positive_extraction_manifest.csv"))
    extract_config = load_extract_config(Path(config["extract_config"]))
    normalize_config = load_normalize_config(Path(config["normalize_config"]))
    features, masks, labels, details = [], [], [], []
    with LandmarkExtractor(extract_config) as extractor:
        for row in rows:
            item = _extract_feature(row, extractor, normalize_config)
            features.append(item["feature"])
            masks.append(item["frame_mask"])
            labels.append(int(row["class_id"]))
            details.append(
                {
                    "sample_id": row["sample_id"],
                    "split": row["split"],
                    "label": row["canonical_label"],
                    "length": item["length"],
                    "hand_hit_rate": item["hand_hit_rate"],
                    "pose_hit_rate": item["pose_hit_rate"],
                }
            )
    x = np.stack(features).astype(np.float32)
    frame_mask = np.stack(masks).astype(bool)
    y = np.asarray(labels, dtype=np.int32)
    y_per_frame = np.repeat(y[:, None], 96, axis=1)
    tf.keras.utils.set_random_seed(101)
    model = build_streaming_classifier(
        96, FEATURE_DIM, len(CLASSES), blocks=4, channels=64,
        dilations=(1, 2, 4, 8), kernel=3, dropout=0.3,
    )
    model.compile(
        optimizer=tf.keras.optimizers.AdamW(0.0005, weight_decay=0.0001),
        loss="sparse_categorical_crossentropy",
        weighted_metrics=[tf.keras.metrics.SparseCategoricalAccuracy(name="pf_acc")],
    )
    output = np.asarray(model(x, training=False))
    loss = model.train_on_batch(x, y_per_frame, sample_weight=frame_mask.astype(np.float32))
    checkpoint = args.run_dir / "smoke" / "actual_data_checkpoint.keras"
    model.save(checkpoint)
    loaded = tf.keras.models.load_model(checkpoint, safe_mode=False)
    reloaded = np.asarray(loaded(x[:1], training=False))
    summary = {
        "experiment": EXPERIMENT,
        "actual_rows": len(rows),
        "input_shape": list(x.shape),
        "output_shape": list(output.shape),
        "finite_input": bool(np.isfinite(x).all()),
        "finite_output": bool(np.isfinite(output).all()),
        "reload_output_shape": list(reloaded.shape),
        "train_on_batch": [float(v) for v in np.atleast_1d(loss)],
        "checkpoint": str(checkpoint.resolve()),
        "details": details,
        "passed": x.shape == (10, 96, FEATURE_DIM)
        and output.shape == (10, 96, len(CLASSES))
        and reloaded.shape == (1, 96, len(CLASSES))
        and bool(np.isfinite(x).all())
        and bool(np.isfinite(output).all()),
    }
    _write_json(args.run_dir / "smoke" / "smoke_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


def _assemble_features(run_dir: Path, require_full: bool) -> dict[str, Any]:
    rows = _read_csv(run_dir / "positive_extraction_manifest.csv")
    by_split: dict[str, dict[str, list[Any]]] = defaultdict(
        lambda: defaultdict(list)
    )
    missing = []
    for row in rows:
        path = _per_clip_path(run_dir, row["sample_id"])
        if not path.exists():
            missing.append(row["sample_id"])
            continue
        data = np.load(path, allow_pickle=False)
        split = row["split"]
        by_split[split]["X"].append(data["feature"])
        by_split[split]["frame_mask"].append(data["frame_mask"])
        by_split[split]["lengths"].append(int(data["length"]))
        by_split[split]["y"].append(int(row["class_id"]))
        by_split[split]["participant_ids"].append(row["signer_group_id"])
        by_split[split]["sample_ids"].append(row["sample_id"])
        by_split[split]["source_ids"].append(row["source_dataset"])
    if missing and require_full:
        raise ValueError(f"missing {len(missing)} positive features; first={missing[:5]}")
    counts = {}
    feature_root = run_dir / "dataset" / "features"
    for split, data in by_split.items():
        np.savez_compressed(
            feature_root / f"{split}.npz",
            X=np.stack(data["X"]).astype(np.float32),
            frame_mask=np.stack(data["frame_mask"]).astype(bool),
            lengths=np.asarray(data["lengths"], dtype=np.int32),
            y=np.asarray(data["y"], dtype=np.int32),
            participant_ids=np.asarray(data["participant_ids"], dtype=str),
            sample_ids=np.asarray(data["sample_ids"], dtype=str),
            source_ids=np.asarray(data["source_ids"], dtype=str),
        )
        counts[split] = len(data["y"])
    return {"split_counts": counts, "missing": len(missing), "assembled": bool(by_split)}


def extract_positive(args: argparse.Namespace) -> int:
    config = json.loads((args.run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    rows = _read_csv(args.run_dir / "positive_extraction_manifest.csv")
    if args.limit is not None:
        rows = rows[: args.limit]
    extract_config = load_extract_config(Path(config["extract_config"]))
    normalize_config = load_normalize_config(Path(config["normalize_config"]))
    log_rows, errors = [], []
    start = time.perf_counter()
    with LandmarkExtractor(extract_config) as extractor:
        for index, row in enumerate(rows, start=1):
            output = _per_clip_path(args.run_dir, row["sample_id"])
            if output.exists() and not args.overwrite_clips:
                log_rows.append({**row, "status": "cached", "feature_path": str(output)})
                continue
            try:
                item = _extract_feature(row, extractor, normalize_config)
                np.savez_compressed(
                    output,
                    feature=item["feature"],
                    frame_mask=item["frame_mask"],
                    length=np.asarray(item["length"], dtype=np.int32),
                )
                log_rows.append(
                    {
                        **row,
                        "status": "ok",
                        "feature_path": str(output),
                        "length": item["length"],
                        "native_frames": item["native_frames"],
                        "native_fps": round(item["native_fps"], 4),
                        "hand_hit_rate": round(item["hand_hit_rate"], 4),
                        "pose_hit_rate": round(item["pose_hit_rate"], 4),
                    }
                )
                print(f"[e6-v30/extract] {index}/{len(rows)} {row['sample_id']}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{row['sample_id']}: {exc}")
                log_rows.append({**row, "status": "failed", "reason": str(exc)[:300]})
                print(f"[e6-v30/extract] FAILED {row['sample_id']}: {exc}", file=sys.stderr)
    if log_rows:
        fields = sorted({key for row in log_rows for key in row})
        _write_csv(args.run_dir / "logs" / "positive_extraction_manifest.csv", log_rows, fields)
    dataset = _assemble_features(
        args.run_dir, require_full=args.require_full and args.limit is None
    )
    summary = {
        "attempted": len(rows),
        "ok_or_cached": sum(row["status"] in {"ok", "cached"} for row in log_rows),
        "failed": sum(row["status"] == "failed" for row in log_rows),
        "elapsed_seconds": time.perf_counter() - start,
        "dataset": dataset,
        "errors": errors,
        "passed": not errors and dataset["assembled"],
    }
    _write_json(args.run_dir / "logs" / "positive_extraction_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


def train(args: argparse.Namespace) -> int:
    from model.train_streaming import run as train_streaming

    features = args.run_dir / "dataset" / "features"
    for split in ("train", "val", "test_fresh", "test_historical"):
        if not (features / f"{split}.npz").is_file():
            raise FileNotFoundError(f"missing full feature split: {split}.npz")
    failures = []
    for seed in SEEDS:
        config = args.run_dir / "config" / f"train_seed_{seed}.yaml"
        result = train_streaming(config, False, args.epochs, args.resume)
        if result != 0:
            failures.append({"seed": seed, "exit_code": result})
            break
    summary = {"seeds": SEEDS, "resume": args.resume, "failures": failures, "passed": not failures}
    _write_json(args.run_dir / "logs" / "training_summary.json", summary)
    return 0 if not failures else 1


def _load_split(feature_root: Path, split: str) -> dict[str, np.ndarray]:
    data = np.load(feature_root / f"{split}.npz", allow_pickle=False)
    return {key: data[key] for key in data.files}


def _per_class(probs: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    pred = probs.argmax(axis=1)
    result = {}
    for class_id, label in enumerate(CLASSES):
        mask = y == class_id
        result[label] = {
            "count": int(mask.sum()),
            "correct": int((pred[mask] == class_id).sum()),
            "recall": float((pred[mask] == class_id).mean()) if mask.any() else None,
        }
    return result


def _evaluate_model(model: Any, feature_root: Path, batch_size: int) -> dict[str, Any]:
    from eval.harness import evaluate as evaluate_harness
    from eval.streaming import predict_aggregate

    splits = {name: _load_split(feature_root, name) for name in ("val", "test_fresh", "test_historical")}
    aggregated = {}
    diagnostics = {}
    for name, data in splits.items():
        probs, pf_acc, last_acc = predict_aggregate(
            model,
            data["X"].astype(np.float32),
            data["frame_mask"].astype(bool),
            data["y"].astype(np.int32),
            data["lengths"].astype(np.int32),
            batch_size,
        )
        aggregated[name] = probs
        predicted = probs.argmax(axis=1)
        confusion = np.zeros((len(CLASSES), len(CLASSES)), dtype=np.int64)
        for truth, guess in zip(data["y"].astype(np.int32), predicted):
            confusion[int(truth), int(guess)] += 1
        diagnostics[name] = {
            "count": len(data["y"]),
            "clip_top1": float((predicted == data["y"]).mean()),
            "per_frame_accuracy": pf_acc,
            "last_frame_accuracy": last_acc,
            "per_class": _per_class(probs, data["y"]),
            "predicted_class_counts": {
                CLASSES[int(class_id)]: int(count)
                for class_id, count in zip(*np.unique(predicted, return_counts=True))
            },
            "confusion_matrix": confusion.tolist(),
        }
    val = splits["val"]
    for name in ("test_fresh", "test_historical"):
        test = splits[name]
        diagnostics[name]["calibrated_report"] = evaluate_harness(
            aggregated["val"],
            val["y"],
            aggregated[name],
            test["y"],
            test["participant_ids"].astype(str),
        )
    return diagnostics


def evaluate(args: argparse.Namespace) -> int:
    import tensorflow as tf

    feature_root = args.run_dir / "dataset" / "features"
    results = {}
    for seed in SEEDS:
        seed_dir = args.run_dir / "models" / f"seed_{seed}"
        results[str(seed)] = {}
        for checkpoint_name in ("latest", "best", "final"):
            path = seed_dir / f"{checkpoint_name}.keras"
            if not path.exists():
                raise FileNotFoundError(f"missing checkpoint: {path}")
            model = tf.keras.models.load_model(path, compile=False, safe_mode=False)
            results[str(seed)][checkpoint_name] = _evaluate_model(model, feature_root, 32)
    latest_fresh = [results[str(seed)]["latest"]["test_fresh"] for seed in SEEDS]
    mean_top1 = float(np.mean([item["clip_top1"] for item in latest_fresh]))
    min_top1 = float(np.min([item["clip_top1"] for item in latest_fresh]))
    mean_recalls = {
        label: float(np.mean([item["per_class"][label]["recall"] for item in latest_fresh]))
        for label in CLASSES
    }
    min_seed_recalls = {
        label: float(np.min([item["per_class"][label]["recall"] for item in latest_fresh]))
        for label in CLASSES
    }
    config = json.loads((args.run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    gates = config["gates"]
    passed = (
        mean_top1 >= gates["mean_fresh_top1_min"]
        and min_top1 >= gates["minimum_seed_fresh_top1_min"]
        and min(mean_recalls.values()) >= gates["mean_per_class_fresh_recall_min"]
        and min(min_seed_recalls.values()) >= gates["minimum_seed_per_class_fresh_recall_min"]
    )
    summary = {
        "primary_checkpoint": "latest",
        "mean_fresh_top1": mean_top1,
        "minimum_seed_fresh_top1": min_top1,
        "mean_fresh_recall_by_class": mean_recalls,
        "minimum_seed_fresh_recall_by_class": min_seed_recalls,
        "gates": gates,
        "passed": passed,
        "decision": "positive_baseline_gate_passed_negative_gate_next"
        if passed
        else "positive_baseline_no_go_root_cause_review",
        "results": results,
    }
    _write_json(args.run_dir / "metrics" / "metrics.json", summary)
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, indent=2))
    return 0


def _tflite_probs(interpreter: Any, x: np.ndarray, frame_mask: np.ndarray) -> np.ndarray:
    input_info = interpreter.get_input_details()[0]
    output_info = interpreter.get_output_details()[0]
    result = np.empty((len(x), int(output_info["shape"][-1])), dtype=np.float32)
    for index in range(len(x)):
        interpreter.set_tensor(input_info["index"], x[index : index + 1].astype(np.float32))
        interpreter.invoke()
        per_frame = interpreter.get_tensor(output_info["index"])[0].astype(np.float32)
        mask = frame_mask[index].astype(np.float32)[:, None]
        result[index] = (per_frame * mask).sum(axis=0) / max(float(mask.sum()), 1.0)
    return result


def evaluate_deployed(args: argparse.Namespace) -> int:
    import tensorflow as tf

    vocab = json.loads(args.vocab.read_text(encoding="utf-8"))
    missing = [label for label in CLASSES if label not in vocab]
    if missing:
        raise ValueError(f"deployed vocabulary missing classes: {missing}")
    interpreter = tf.lite.Interpreter(model_path=str(args.model))
    interpreter.allocate_tensors()
    input_shape = tuple(int(value) for value in interpreter.get_input_details()[0]["shape"])
    output_shape = tuple(int(value) for value in interpreter.get_output_details()[0]["shape"])
    if input_shape != (1, 96, FEATURE_DIM) or output_shape != (1, 96, 236):
        raise ValueError(f"deployed contract mismatch: {input_shape} -> {output_shape}")
    result = {
        "model": str(args.model.resolve()),
        "model_sha256": _sha256(args.model),
        "vocab_sha256": _sha256(args.vocab),
        "input_shape": input_shape,
        "output_shape": output_shape,
        "splits": {},
    }
    selected_ids = np.asarray([vocab[label] for label in CLASSES], dtype=np.int32)
    for split in ("val", "test_fresh", "test_historical"):
        data = _load_split(args.run_dir / "dataset" / "features", split)
        probs = _tflite_probs(interpreter, data["X"], data["frame_mask"])
        true_full = selected_ids[data["y"].astype(np.int32)]
        full_pred = probs.argmax(axis=1)
        restricted_pred = probs[:, selected_ids].argmax(axis=1)
        top5 = np.argpartition(probs, -5, axis=1)[:, -5:]
        per_class = {}
        for class_id, label in enumerate(CLASSES):
            mask = data["y"] == class_id
            per_class[label] = {
                "count": int(mask.sum()),
                "full_236_recall": float((full_pred[mask] == true_full[mask]).mean()),
                "restricted_five_recall": float((restricted_pred[mask] == class_id).mean()),
            }
        result["splits"][split] = {
            "count": len(data["y"]),
            "full_236_top1": float((full_pred == true_full).mean()),
            "full_236_top5": float(np.mean([truth in row for truth, row in zip(true_full, top5)])),
            "restricted_five_top1": float((restricted_pred == data["y"]).mean()),
            "per_class": per_class,
        }
    result["passed"] = True
    _write_json(args.run_dir / "metrics" / "deployed_236_control.json", result)
    print(json.dumps(result, indent=2))
    return 0


def check(args: argparse.Namespace) -> int:
    required = [
        "pilot_config.json",
        "positive_extraction_manifest.csv",
        "selected_classes.csv",
        "README_RUN.md",
    ]
    if args.require_smoke:
        required.append("smoke/smoke_summary.json")
    if args.require_full:
        required.extend(
            f"dataset/features/{split}.npz"
            for split in ("train", "val", "test_fresh", "test_historical")
        )
    if args.require_metrics:
        required.extend(["metrics/metrics.json", "metrics/deployed_236_control.json"])
    errors = [name for name in required if not (args.run_dir / name).is_file()]
    config_path = args.run_dir / "pilot_config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if config.get("schema_version") != "3.0" or config.get("input_shape") != [96, 258]:
            errors.append("schema/input contract mismatch")
    smoke_path = args.run_dir / "smoke" / "smoke_summary.json"
    if smoke_path.exists() and not json.loads(smoke_path.read_text(encoding="utf-8")).get("passed"):
        errors.append("actual-data smoke did not pass")
    report = {"run_dir": str(args.run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(args.run_dir / "check_report.json", report)
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--assignment-run", type=Path, default=DEFAULT_ASSIGNMENT_RUN)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--extract-config", type=Path, default=DEFAULT_EXTRACT_CONFIG)
    p.add_argument("--normalize-config", type=Path, default=DEFAULT_NORMALIZE_CONFIG)
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=prepare)
    p = commands.add_parser("smoke")
    p.add_argument("--run-dir", type=Path, required=True)
    p.set_defaults(func=smoke)
    p = commands.add_parser("extract-positive")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--limit", type=int)
    p.add_argument("--require-full", action="store_true")
    p.add_argument("--overwrite-clips", action="store_true")
    p.set_defaults(func=extract_positive)
    p = commands.add_parser("train")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--epochs", type=int)
    p.add_argument("--resume", action="store_true")
    p.set_defaults(func=train)
    p = commands.add_parser("evaluate")
    p.add_argument("--run-dir", type=Path, required=True)
    p.set_defaults(func=evaluate)
    p = commands.add_parser("evaluate-deployed")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--model", type=Path, default=DEFAULT_DEPLOYED_MODEL)
    p.add_argument("--vocab", type=Path, default=DEFAULT_DEPLOYED_VOCAB)
    p.set_defaults(func=evaluate_deployed)
    p = commands.add_parser("check")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--require-smoke", action="store_true")
    p.add_argument("--require-full", action="store_true")
    p.add_argument("--require-metrics", action="store_true")
    p.set_defaults(func=check)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"[e6-v30-five-sign] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
