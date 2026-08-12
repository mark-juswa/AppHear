"""E4-B strict 7-sign local supplementary extraction/training runner.

Experiment-only. Consumes the strict signer-disjoint manifest, extracts v3.0 [96,258]
landmark tensors from source videos, and trains bounded landmark-temporal baselines. It writes
isolated outputs only and never modifies Android or production recognizer assets.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.extract.config import load_config as load_extract_config
from pipeline.extract.landmarks import LandmarkExtractor
from pipeline.features.contract import SCHEMA_VERSION, clip_features_realtimed
from pipeline.normalize.config import load_config as load_normalize_config
from pipeline.rgb.e3_b4_landmark_temporal import _build_model, _inputs_for, _load_weights_model
from pipeline.rgb.e3_b5_landmark_temporal_scale import _evaluate

DEFAULT_MANIFEST_RUN = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_signer_disjoint_manifest_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_01"
)
DEFAULT_EXTRACT_CONFIG = Path("pipeline/config/extract.yaml")
DEFAULT_NORMALIZE_CONFIG = Path("pipeline/config/normalize.yaml")
SPLITS = {"train": 0, "val": 1, "test": 2}
DEFAULT_BRANCHES = ["conv1d_baseline", "tcn_masked_pool"]
DEFAULT_SEEDS = [101, 202, 303]
ACTIVE_SPLITS = set(SPLITS)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_manifest(manifest_run: Path) -> list[dict[str, str]]:
    path = manifest_run / "pilot_manifest.csv"
    if not path.exists():
        raise FileNotFoundError(f"missing strict manifest: {path}")
    rows = _read_csv(path)
    active = [row for row in rows if row["split"] in ACTIVE_SPLITS]
    if not active:
        raise ValueError(f"manifest has no active train/val/test rows: {path}")
    return rows


def _class_names(rows: list[dict[str, str]]) -> list[str]:
    active = [row for row in rows if row["split"] in ACTIVE_SPLITS]
    pairs = sorted({(int(row["class_id"]), row["canonical_gloss"]) for row in active})
    expected = list(range(len(pairs)))
    actual = [class_id for class_id, _ in pairs]
    if actual != expected:
        raise ValueError(f"class ids must be contiguous from zero: {actual}")
    return [gloss for _, gloss in pairs]


def _split_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = Counter(row["split"] for row in rows)
    return {split: int(counts[split]) for split in ("train", "val", "test", "quarantine")}


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    rows = _load_manifest(args.manifest_run)
    classes = _class_names(rows)
    output = args.output
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("dataset/per_clip", "logs", "metrics", "models", "smoke"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    _write_csv(output / "pilot_manifest.csv", rows, list(rows[0].keys()))
    selected = [{"class_id": idx, "gloss": gloss} for idx, gloss in enumerate(classes)]
    _write_csv(output / "selected_classes.csv", selected, ["class_id", "gloss"])

    config = {
        "experiment": "e4_b_strict_7_landmark_pilot_v1",
        "purpose": "bounded landmark-temporal pilot on strict 7-sign local supplementary signer-disjoint split",
        "run_dir": str(output.resolve()),
        "manifest_run": str(args.manifest_run.resolve()),
        "input_shape": [96, 258],
        "schema_version": SCHEMA_VERSION,
        "classes": classes,
        "class_count": len(classes),
        "manifest_rows": len(rows),
        "active_rows": sum(1 for row in rows if row["split"] in ACTIVE_SPLITS),
        "split_counts": _split_counts(rows),
        "extract_config": str(args.extract_config),
        "normalize_config": str(args.normalize_config),
        "branches": args.branches,
        "seeds": args.seeds,
        "batch_size": args.batch_size,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "long_steps": ["extract-features", "run"],
        "gate": {
            "go_if": [
                "strict signer-disjoint test accuracy is materially above 7-class random baseline 0.1429",
                "validation and test per-class accuracy do not collapse to one or two classes",
                "held-out test signer performance is reported as diagnostic local evidence only",
            ],
            "no_go_if": [
                "training memorizes but held-out test remains near random",
                "predictions collapse to one dominant class",
                "MediaPipe extraction fails for a large fraction of clips",
            ],
        },
        "warnings": [
            "Experiment-only local pilot; not production recognizer training.",
            "This uses IMAGE-mode MediaPipe extraction from local videos to preserve current train/serve feature semantics.",
            "The strict split is signer-disjoint but small: one train signer and one test signer source per class.",
        ],
    }
    _write_json(output / "pilot_config.json", config)
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def _extract_feature(row: dict[str, str], extractor: LandmarkExtractor, normalize_config: Any) -> dict[str, Any]:
    video_path = Path(row["video_path"])
    clip, meta = extractor.extract(video_path)
    release = int(clip.timestamps_ms.shape[0] - 1)
    if release < 0:
        raise ValueError(f"no frames extracted: {video_path}")
    feature, frame_mask, length, _params = clip_features_realtimed(
        clip.hands_image, clip.pose_image, 0, release, normalize_config, 96
    )
    hand_present = clip.hand_score > 0.0
    any_hand = float(np.mean(np.any(hand_present, axis=1))) if len(hand_present) else 0.0
    pose_hit = float(np.mean(clip.pose_score > 0.0)) if len(clip.pose_score) else 0.0
    return {
        "feature": feature.astype(np.float32),
        "frame_mask": frame_mask.astype(bool),
        "length": int(length),
        "native_frames": int(meta["n_frames"]),
        "native_fps": float(meta["native_fps"]),
        "frame_width": int(meta["frame_width"]),
        "frame_height": int(meta["frame_height"]),
        "hand_hit_rate_extracted": any_hand,
        "pose_hit_rate_extracted": pose_hit,
    }


def _per_clip_path(run_dir: Path, sample_id: str) -> Path:
    return run_dir / "dataset" / "per_clip" / f"{sample_id}.npz"


def extract_features(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    rows = [row for row in _read_csv(run_dir / "pilot_manifest.csv") if row["split"] in ACTIVE_SPLITS]
    if args.limit is not None:
        rows = rows[: args.limit]
    extract_config = load_extract_config(args.extract_config or config["extract_config"])
    normalize_config = load_normalize_config(args.normalize_config or config["normalize_config"])
    errors = []
    manifest_rows = []
    start = time.perf_counter()
    with LandmarkExtractor(extract_config) as extractor:
        for index, row in enumerate(rows, start=1):
            out_path = _per_clip_path(run_dir, row["sample_id"])
            if out_path.exists() and not args.overwrite_clips:
                manifest_rows.append({**row, "status": "cached", "feature_path": str(out_path)})
                continue
            try:
                item = _extract_feature(row, extractor, normalize_config)
                np.savez_compressed(
                    out_path,
                    feature=item["feature"],
                    frame_mask=item["frame_mask"],
                    y=np.asarray(int(row["class_id"]), dtype=np.int64),
                    split_index=np.asarray(SPLITS[row["split"]], dtype=np.int64),
                    length=np.asarray(item["length"], dtype=np.int32),
                    participant_id=np.asarray(row["signer_id"]),
                    sample_id=np.asarray(row["sample_id"]),
                )
                manifest_rows.append(
                    {
                        **row,
                        "status": "ok",
                        "feature_path": str(out_path),
                        "native_frames_extracted": item["native_frames"],
                        "native_fps_extracted": item["native_fps"],
                        "hand_hit_rate_extracted": round(item["hand_hit_rate_extracted"], 4),
                        "pose_hit_rate_extracted": round(item["pose_hit_rate_extracted"], 4),
                    }
                )
                print(f"[e4-b/extract] {index}/{len(rows)} {row['sample_id']} {row['canonical_gloss']}")
            except Exception as err:  # noqa: BLE001
                errors.append(f"{row['sample_id']}: {err}")
                manifest_rows.append({**row, "status": "failed", "reason": str(err)[:240]})
                print(f"[e4-b/extract] FAILED {row['sample_id']}: {err}", file=sys.stderr)
    _write_csv(
        run_dir / "logs" / "feature_extraction_manifest.csv",
        manifest_rows,
        sorted({key for item in manifest_rows for key in item.keys()}),
    )
    dataset_result = _assemble_dataset(run_dir, require_full=args.require_full and args.limit is None)
    result = {
        "experiment": config["experiment"],
        "run_dir": str(run_dir.resolve()),
        "attempted_rows": len(rows),
        "ok_or_cached_rows": sum(row.get("status") in {"ok", "cached"} for row in manifest_rows),
        "failed_rows": sum(row.get("status") == "failed" for row in manifest_rows),
        "elapsed_seconds": time.perf_counter() - start,
        "dataset": dataset_result,
        "errors": errors,
        "passed": not errors,
    }
    _write_json(run_dir / "logs" / "feature_extraction_summary.json", result)
    return result


def _assemble_dataset(run_dir: Path, require_full: bool) -> dict[str, Any]:
    rows = [row for row in _read_csv(run_dir / "pilot_manifest.csv") if row["split"] in ACTIVE_SPLITS]
    features = []
    masks = []
    labels = []
    splits = []
    lengths = []
    participant_ids = []
    sample_ids = []
    missing = []
    for row in rows:
        path = _per_clip_path(run_dir, row["sample_id"])
        if not path.exists():
            missing.append(row["sample_id"])
            continue
        data = np.load(path, allow_pickle=False)
        features.append(data["feature"].astype(np.float32))
        masks.append(data["frame_mask"].astype(bool))
        labels.append(int(data["y"]))
        splits.append(int(data["split_index"]))
        lengths.append(int(data["length"]))
        participant_ids.append(str(np.asarray(data["participant_id"]).item()))
        sample_ids.append(str(np.asarray(data["sample_id"]).item()))
    if missing and require_full:
        raise ValueError(f"missing per-clip features for {len(missing)} rows; first={missing[:5]}")
    if not features:
        return {"assembled": False, "rows": 0, "missing_rows": len(missing)}
    x = np.stack(features).astype(np.float32)
    fm = np.stack(masks).astype(bool)
    y = np.asarray(labels, dtype=np.int64)
    split_index = np.asarray(splits, dtype=np.int64)
    lens = np.asarray(lengths, dtype=np.int32)
    np.savez_compressed(
        run_dir / "dataset" / "landmark_features.npz",
        landmarks=x,
        frame_mask=fm,
        y=y,
        split_index=split_index,
        lengths=lens,
        participant_ids=np.asarray(participant_ids),
        sample_ids=np.asarray(sample_ids),
    )
    return {
        "assembled": True,
        "rows": int(x.shape[0]),
        "shape": [int(v) for v in x.shape],
        "missing_rows": len(missing),
        "split_counts": {name: int(np.sum(split_index == sid)) for name, sid in SPLITS.items()},
    }


def _load_dataset(run_dir: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    path = run_dir / "dataset" / "landmark_features.npz"
    if not path.exists():
        raise FileNotFoundError(f"missing dataset; run extract-features first: {path}")
    data = np.load(path, allow_pickle=False)
    return (
        data["landmarks"].astype(np.float32),
        data["frame_mask"].astype(bool),
        data["y"].astype(np.int64),
        data["split_index"].astype(np.int64),
        data["lengths"].astype(np.int32),
    )


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    rows = [row for row in _read_csv(run_dir / "pilot_manifest.csv") if row["split"] in {"train", "val"}]
    rows = rows[: max(4, args.rows)]
    extract_config = load_extract_config(config["extract_config"])
    normalize_config = load_normalize_config(config["normalize_config"])
    feats = []
    masks = []
    y = []
    with LandmarkExtractor(extract_config) as extractor:
        for row in rows:
            item = _extract_feature(row, extractor, normalize_config)
            feats.append(item["feature"])
            masks.append(item["frame_mask"])
            y.append(int(row["class_id"]))
    x = np.stack(feats).astype(np.float32)
    fm = np.stack(masks).astype(bool)
    yy = np.asarray(y, dtype=np.int64)
    summary = {"rows": int(x.shape[0]), "shape": [int(v) for v in x.shape], "branches": {}}
    for branch in config["branches"]:
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(12345)
        model = _build_model(branch, (96, 258), int(config["class_count"]), float(config["learning_rate"]))
        probs = model.predict(_inputs_for(branch, x, fm), batch_size=2, verbose=0)
        loss = model.train_on_batch(_inputs_for(branch, x, fm), yy)
        weights_path = run_dir / "smoke" / f"{branch}.weights.h5"
        model.save_weights(weights_path)
        summary["branches"][branch] = {
            "forward_shape": [int(v) for v in probs.shape],
            "train_on_batch": [float(v) for v in np.atleast_1d(loss).tolist()],
            "weights_saved": str(weights_path.resolve()),
        }
    _write_json(run_dir / "smoke" / "smoke_summary.json", summary)
    return summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    landmarks, frame_mask, y, split_index, _lengths = _load_dataset(run_dir)
    metrics: dict[str, Any] = {
        "experiment": config["experiment"],
        "run_dir": str(run_dir.resolve()),
        "input_shape": [96, 258],
        "class_count": int(config["class_count"]),
        "random_baseline": 1.0 / int(config["class_count"]),
        "split_counts": {name: int(np.sum(split_index == sid)) for name, sid in SPLITS.items()},
        "branches": {},
        "passed": True,
    }
    train_mask = split_index == SPLITS["train"]
    val_mask = split_index == SPLITS["val"]
    start = time.perf_counter()
    for branch in config["branches"]:
        metrics["branches"][branch] = {}
        for seed in config["seeds"]:
            seed = int(seed)
            tf.keras.backend.clear_session()
            tf.keras.utils.set_random_seed(seed)
            seed_dir = run_dir / "models" / branch / f"seed_{seed}"
            seed_dir.mkdir(parents=True, exist_ok=True)
            latest = seed_dir / "latest.weights.h5"
            best = seed_dir / "best.weights.h5"
            epoch_file = run_dir / "logs" / f"{branch}_seed_{seed}_epoch_count.txt"
            history_path = run_dir / "logs" / f"{branch}_seed_{seed}_history.csv"
            if latest.exists() and not args.resume:
                raise FileExistsError(f"{branch} seed {seed}: latest weights exist; rerun with --resume")
            model = _build_model(branch, (96, 258), int(config["class_count"]), float(config["learning_rate"]))
            initial_epoch = 0
            if args.resume and latest.exists():
                model.load_weights(latest)
                initial_epoch = int(epoch_file.read_text(encoding="utf-8"))
            history = model.fit(
                _inputs_for(branch, landmarks[train_mask], frame_mask[train_mask]),
                y[train_mask],
                validation_data=(_inputs_for(branch, landmarks[val_mask], frame_mask[val_mask]), y[val_mask]),
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
            metrics["branches"][branch][str(seed)] = {
                "latest": _evaluate(branch, model, landmarks, frame_mask, y, split_index, int(config["batch_size"]), config["classes"]),
                "best": _evaluate(
                    branch,
                    _load_weights_model(branch, (96, 258), int(config["class_count"]), float(config["learning_rate"]), best),
                    landmarks,
                    frame_mask,
                    y,
                    split_index,
                    int(config["batch_size"]),
                    config["classes"],
                ),
                "epoch_count_total": total_epochs,
                "history_last": {key: float(values[-1]) for key, values in history.history.items()},
            }
    metrics["elapsed_seconds"] = time.perf_counter() - start
    _write_json(run_dir / "metrics" / "metrics.json", metrics)
    return metrics


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["pilot_config.json", "pilot_manifest.csv", "selected_classes.csv", "README_RUN.md"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    config = {}
    config_path = run_dir / "pilot_config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    dataset_path = run_dir / "dataset" / "landmark_features.npz"
    if args.require_dataset and not dataset_path.exists():
        errors.append("missing output: dataset/landmark_features.npz")
    if dataset_path.exists() and config:
        data = np.load(dataset_path, allow_pickle=False)
        if tuple(data["landmarks"].shape[1:]) != (96, 258):
            errors.append(f"dataset shape mismatch: {list(data['landmarks'].shape)}")
        expected = int(config.get("active_rows", -1))
        if args.require_full_dataset and int(data["landmarks"].shape[0]) != expected:
            errors.append(f"dataset row count mismatch: {data['landmarks'].shape[0]} != {expected}")
    metrics_path = run_dir / "metrics" / "metrics.json"
    if args.require_metrics and not metrics_path.exists():
        errors.append("missing output: metrics/metrics.json")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join(
        [
            "# E4-B Strict 7-Sign Landmark Pilot",
            "",
            "Experiment-only runner. It does not modify Android or production recognizer assets.",
            "",
            "## Scope",
            "",
            f"- Classes: {', '.join(config['classes'])}",
            f"- Active rows: {config['active_rows']}",
            f"- Split counts: {config['split_counts']}",
            f"- Branches: {', '.join(config['branches'])}",
            f"- Seeds: {', '.join(str(seed) for seed in config['seeds'])}",
            "",
            "## Smoke Test",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_b_strict_runner smoke --run-dir "{run_dir}"',
            "```",
            "",
            "## Full Feature Extraction",
            "",
            "This is the first long step. The user should run it manually.",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_b_strict_runner extract-features --run-dir "{run_dir}" --require-full',
            "```",
            "",
            "## Training",
            "",
            "Run only after feature extraction passes check.",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_b_strict_runner run --run-dir "{run_dir}"',
            "```",
            "",
            "Resume interrupted training:",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_b_strict_runner run --run-dir "{run_dir}" --resume',
            "```",
            "",
            "## Check",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_b_strict_runner check --run-dir "{run_dir}" --require-full-dataset --require-metrics',
            "```",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-B strict 7-sign landmark pilot runner")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--manifest-run", type=Path, default=DEFAULT_MANIFEST_RUN)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--extract-config", type=Path, default=DEFAULT_EXTRACT_CONFIG)
    prepare_parser.add_argument("--normalize-config", type=Path, default=DEFAULT_NORMALIZE_CONFIG)
    prepare_parser.add_argument("--branches", nargs="+", default=DEFAULT_BRANCHES)
    prepare_parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    prepare_parser.add_argument("--batch-size", type=int, default=8)
    prepare_parser.add_argument("--epochs", type=int, default=20)
    prepare_parser.add_argument("--learning-rate", type=float, default=5e-4)
    prepare_parser.add_argument("--overwrite", action="store_true")

    smoke_parser = sub.add_parser("smoke")
    smoke_parser.add_argument("--run-dir", type=Path, required=True)
    smoke_parser.add_argument("--rows", type=int, default=6)

    extract_parser = sub.add_parser("extract-features")
    extract_parser.add_argument("--run-dir", type=Path, required=True)
    extract_parser.add_argument("--extract-config", type=Path, default=None)
    extract_parser.add_argument("--normalize-config", type=Path, default=None)
    extract_parser.add_argument("--limit", type=int, default=None)
    extract_parser.add_argument("--overwrite-clips", action="store_true")
    extract_parser.add_argument("--require-full", action="store_true")

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--run-dir", type=Path, required=True)
    run_parser.add_argument("--resume", action="store_true")

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--require-dataset", action="store_true")
    check_parser.add_argument("--require-full-dataset", action="store_true")
    check_parser.add_argument("--require-metrics", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "smoke":
            result = smoke(args)
        elif args.command == "extract-features":
            result = extract_features(args)
        elif args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileExistsError, FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-b-runner] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())