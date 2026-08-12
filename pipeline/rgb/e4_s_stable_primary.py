"""E4-S stable-primary landmark package.

Builds a guarded 4-sign primary dataset from the passed E4-N tensor by keeping only
E4-R Tier-A signs and moving SORRY into an OOV/confusion holdout. Experiment-only:
no Android assets, TFLite files, source videos, or production recognizer files are changed.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.features.contract import SCHEMA_VERSION
from pipeline.rgb.e3_b4_landmark_temporal import _build_model, _inputs_for, _load_weights_model
from pipeline.rgb.e4_b_strict_runner import check as _base_check
from pipeline.rgb.e4_b_strict_runner import run as _base_run

DEFAULT_SOURCE_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_n_dual_source_5sign_screen_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01")
DEFAULT_CLASSES = ["GOOD", "HELLO", "HAVE", "KNOW"]
OOV_CLASSES = ["SORRY"]
DEFAULT_BRANCHES = ["conv1d_baseline"]
DEFAULT_SEEDS = [101, 202, 303]
SPLITS = {"train": 0, "val": 1, "test": 2}
SPLIT_NAMES = {v: k for k, v in SPLITS.items()}


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


def _load_source(source_run: Path) -> tuple[dict[str, np.ndarray], list[dict[str, str]], dict[str, Any]]:
    dataset_path = source_run / "dataset" / "landmark_features.npz"
    manifest_path = source_run / "pilot_manifest.csv"
    config_path = source_run / "pilot_config.json"
    if not dataset_path.exists():
        raise FileNotFoundError(f"missing source dataset: {dataset_path}")
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing source manifest: {manifest_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"missing source config: {config_path}")
    data = np.load(dataset_path, allow_pickle=False)
    dataset = {
        "landmarks": data["landmarks"].astype(np.float32),
        "frame_mask": data["frame_mask"].astype(bool),
        "y": data["y"].astype(np.int64),
        "split_index": data["split_index"].astype(np.int64),
        "lengths": data["lengths"].astype(np.int32),
        "participant_ids": np.asarray(data["participant_ids"]).astype(str),
        "sample_ids": np.asarray(data["sample_ids"]).astype(str),
        "source_ids": np.asarray(data["source_ids"]).astype(str),
    }
    return dataset, _read_csv(manifest_path), json.loads(config_path.read_text(encoding="utf-8"))


def _subset(dataset: dict[str, np.ndarray], mask: np.ndarray, y: np.ndarray) -> dict[str, np.ndarray]:
    return {
        "landmarks": dataset["landmarks"][mask].astype(np.float32),
        "frame_mask": dataset["frame_mask"][mask].astype(bool),
        "y": y.astype(np.int64),
        "split_index": dataset["split_index"][mask].astype(np.int64),
        "lengths": dataset["lengths"][mask].astype(np.int32),
        "participant_ids": dataset["participant_ids"][mask].astype(str),
        "sample_ids": dataset["sample_ids"][mask].astype(str),
        "source_ids": dataset["source_ids"][mask].astype(str),
    }


def _split_counts(split_index: np.ndarray) -> dict[str, int]:
    return {name: int(np.sum(split_index == sid)) for name, sid in SPLITS.items()}


def _class_counts(y: np.ndarray, split_index: np.ndarray, classes: list[str]) -> dict[str, dict[str, int]]:
    return {
        split: {classes[cid]: int(np.sum(y[split_index == sid] == cid)) for cid in range(len(classes))}
        for split, sid in SPLITS.items()
    }


def _source_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(row["source_id"]) for row in rows).items()))


def _rows_for_samples(
    rows: list[dict[str, str]],
    sample_ids: np.ndarray,
    class_remap: dict[str, int],
    notes_suffix: str,
) -> list[dict[str, Any]]:
    by_sample = {row["sample_id"]: row for row in rows}
    out: list[dict[str, Any]] = []
    for sample_id in sample_ids.tolist():
        row = dict(by_sample[str(sample_id)])
        gloss = str(row["canonical_gloss"]).upper()
        row["class_id"] = class_remap[gloss]
        row["notes"] = f"{row.get('notes', '')}; {notes_suffix}".strip("; ")
        out.append(row)
    return out


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("dataset", "logs", "metrics", "models", "smoke"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    source, source_rows, source_config = _load_source(args.source_run)
    source_classes = [str(item).upper() for item in source_config["classes"]]
    if source_config.get("experiment") != "e4_n_dual_source_5sign_training_screen_v1":
        raise ValueError("E4-S must be prepared from the E4-N 5-sign screen output")
    if [str(item).upper() for item in args.classes] != DEFAULT_CLASSES:
        raise ValueError(f"E4-S class contract is fixed: {DEFAULT_CLASSES}")

    active_source_ids = [source_classes.index(gloss) for gloss in DEFAULT_CLASSES]
    oov_source_ids = [source_classes.index(gloss) for gloss in OOV_CLASSES]
    active_mask = np.isin(source["y"], active_source_ids)
    oov_mask = np.isin(source["y"], oov_source_ids)
    remap_by_source = {source_classes.index(gloss): idx for idx, gloss in enumerate(DEFAULT_CLASSES)}
    active_y = np.asarray([remap_by_source[int(item)] for item in source["y"][active_mask]], dtype=np.int64)
    active = _subset(source, active_mask, active_y)
    oov = _subset(source, oov_mask, np.zeros(int(np.sum(oov_mask)), dtype=np.int64))

    class_remap = {gloss: idx for idx, gloss in enumerate(DEFAULT_CLASSES)}
    oov_remap = {gloss: idx for idx, gloss in enumerate(OOV_CLASSES)}
    active_rows = _rows_for_samples(source_rows, active["sample_ids"], class_remap, "selected_by_e4_s_stable_primary")
    oov_rows = _rows_for_samples(source_rows, oov["sample_ids"], oov_remap, "withheld_as_e4_s_oov_confusion_holdout")

    np.savez_compressed(output / "dataset" / "landmark_features.npz", **active)
    np.savez_compressed(output / "dataset" / "oov_confusion_holdout.npz", **oov, oov_classes=np.asarray(OOV_CLASSES))
    np.savez_compressed(
        output / "dataset" / "source_metadata.npz",
        source_ids=active["source_ids"],
        sample_ids=active["sample_ids"],
        participant_ids=active["participant_ids"],
    )

    fields = ["sample_id", "source_id", "source_split", "split", "canonical_gloss", "class_id", "participant_id", "source_index", "source_path", "notes"]
    _write_csv(output / "pilot_manifest.csv", active_rows, fields)
    _write_csv(output / "oov_confusion_holdout_manifest.csv", oov_rows, fields)
    _write_csv(output / "selected_classes.csv", [{"class_id": i, "gloss": gloss} for i, gloss in enumerate(DEFAULT_CLASSES)], ["class_id", "gloss"])

    config = {
        "experiment": "e4_s_stable_primary_4sign_v1",
        "purpose": "train a guarded stable-primary landmark recognizer from E4-R Tier-A signs only",
        "run_dir": str(output.resolve()),
        "source_run": str(args.source_run.resolve()),
        "input_shape": [96, 258],
        "schema_version": SCHEMA_VERSION,
        "classes": DEFAULT_CLASSES,
        "class_count": len(DEFAULT_CLASSES),
        "excluded_oov_confusion_classes": OOV_CLASSES,
        "active_rows": int(active["landmarks"].shape[0]),
        "oov_holdout_rows": int(oov["landmarks"].shape[0]),
        "split_counts": _split_counts(active["split_index"]),
        "class_counts": _class_counts(active["y"], active["split_index"], DEFAULT_CLASSES),
        "source_counts": _source_counts(active_rows),
        "oov_source_counts": _source_counts(oov_rows),
        "batch_size": int(args.batch_size),
        "epochs": int(args.epochs),
        "learning_rate": float(args.learning_rate),
        "branches": list(args.branches),
        "seeds": list(args.seeds),
        "random_baseline": 1.0 / len(DEFAULT_CLASSES),
        "long_steps": ["run"],
        "gate": {
            "mean_latest_test_min": 0.90,
            "min_seed_latest_test_min": 0.85,
            "min_class_latest_test_min": 0.85,
            "max_predicted_class_share": 0.45,
        },
        "warnings": [
            "This is an offline experiment package, not a production Android model.",
            "SORRY is deliberately withheld as an OOV/confusion holdout after E4-P/E4-Q failures.",
            "The holdout is for later router simulation; this package does not implement unknown-sign rejection.",
            "No Android integration, TFLite export, or production recognizer replacement is authorized.",
        ],
    }
    _write_json(output / "pilot_config.json", config)
    _write_json(output / "logs" / "prepare_summary.json", {**config, "passed": True})
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    data = np.load(run_dir / "dataset" / "landmark_features.npz", allow_pickle=False)
    rows = min(int(args.rows), int(data["landmarks"].shape[0]))
    x = data["landmarks"][:rows].astype(np.float32)
    frame_mask = data["frame_mask"][:rows].astype(bool)
    y = data["y"][:rows].astype(np.int64)
    result: dict[str, Any] = {"rows": rows, "shape": [int(v) for v in x.shape], "branches": {}}
    for branch in config["branches"]:
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(12345)
        model = _build_model(branch, (96, 258), int(config["class_count"]), float(config["learning_rate"]))
        probs = model.predict(_inputs_for(branch, x, frame_mask), batch_size=2, verbose=0)
        loss = model.train_on_batch(_inputs_for(branch, x, frame_mask), y)
        weights_path = run_dir / "smoke" / f"{branch}.weights.h5"
        model.save_weights(weights_path)
        result["branches"][branch] = {
            "forward_shape": [int(v) for v in probs.shape],
            "train_on_batch": [float(v) for v in np.atleast_1d(loss).tolist()],
            "weights_saved": str(weights_path.resolve()),
        }
    _write_json(run_dir / "smoke" / "smoke_summary.json", result)
    return result


def _oov_probe(run_dir: Path, metrics: dict[str, Any]) -> dict[str, Any]:
    data_path = run_dir / "dataset" / "oov_confusion_holdout.npz"
    if not data_path.exists():
        return {"available": False}
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    data = np.load(data_path, allow_pickle=False)
    x = data["landmarks"].astype(np.float32)
    frame_mask = data["frame_mask"].astype(bool)
    split_index = data["split_index"].astype(np.int64)
    out: dict[str, Any] = {"available": True, "rows": int(x.shape[0]), "classes": config["classes"], "branches": {}}
    for branch, seeds in metrics.get("branches", {}).items():
        out["branches"][branch] = {}
        for seed in seeds:
            latest = _load_weights_model(branch, (96, 258), int(config["class_count"]), float(config["learning_rate"]), run_dir / "models" / branch / f"seed_{seed}" / "latest.weights.h5")
            probs = latest.predict(_inputs_for(branch, x, frame_mask), batch_size=int(config["batch_size"]), verbose=0)
            pred = np.argmax(probs, axis=1)
            seed_out = {"mean_confidence": float(np.mean(np.max(probs, axis=1))), "by_split": {}}
            for split, sid in SPLITS.items():
                mask = split_index == sid
                if not np.any(mask):
                    seed_out["by_split"][split] = {"count": 0, "predicted_class_counts": {}}
                    continue
                counts = Counter(config["classes"][int(cid)] for cid in pred[mask])
                seed_out["by_split"][split] = {"count": int(np.sum(mask)), "predicted_class_counts": dict(sorted(counts.items()))}
            out["branches"][branch][seed] = seed_out
    return out


def run(args: argparse.Namespace) -> dict[str, Any]:
    result = _base_run(args)
    result["oov_confusion_probe"] = _oov_probe(args.run_dir, result)
    _write_json(args.run_dir / "metrics" / "metrics.json", result)
    return result


def check(args: argparse.Namespace) -> dict[str, Any]:
    result = _base_check(args)
    run_dir = args.run_dir
    config_path = run_dir / "pilot_config.json"
    dataset_path = run_dir / "dataset" / "landmark_features.npz"
    oov_path = run_dir / "dataset" / "oov_confusion_holdout.npz"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if config.get("experiment") != "e4_s_stable_primary_4sign_v1":
            result["errors"].append("unexpected experiment id")
            result["passed"] = False
        if config.get("classes") != DEFAULT_CLASSES:
            result["errors"].append("unexpected E4-S class list")
            result["passed"] = False
        if config.get("excluded_oov_confusion_classes") != OOV_CLASSES:
            result["errors"].append("unexpected E4-S OOV holdout class list")
            result["passed"] = False
    if dataset_path.exists():
        data = np.load(dataset_path, allow_pickle=False)
        if np.any(data["y"] == len(DEFAULT_CLASSES)):
            result["errors"].append("active dataset contains an unmapped source class")
            result["passed"] = False
        if "source_ids" not in data.files:
            result["errors"].append("active dataset missing source_ids")
            result["passed"] = False
    for required in ("logs/prepare_summary.json", "dataset/source_metadata.npz", "dataset/oov_confusion_holdout.npz", "oov_confusion_holdout_manifest.csv"):
        if not (run_dir / required).exists():
            result["errors"].append(f"missing output: {required}")
            result["passed"] = False
    if oov_path.exists():
        oov = np.load(oov_path, allow_pickle=False)
        if int(oov["landmarks"].shape[0]) <= 0:
            result["errors"].append("OOV/confusion holdout is empty")
            result["passed"] = False
    _write_json(run_dir / "check_report.json", result)
    return result


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join([
        "# E4-S Stable-Primary 4-Sign Landmark Package",
        "",
        "This package trains only the guarded Tier-A primary signs from E4-R: GOOD, HELLO, HAVE, and KNOW.",
        "SORRY is intentionally withheld as an OOV/confusion holdout for later router simulation.",
        "",
        "## Scope",
        "",
        f"- Classes: {', '.join(config['classes'])}",
        f"- Active rows: {config['active_rows']}",
        f"- OOV/confusion holdout rows: {config['oov_holdout_rows']}",
        f"- Split counts: {config['split_counts']}",
        f"- Source counts: {config['source_counts']}",
        f"- Branches: {', '.join(config['branches'])}",
        f"- Seeds: {', '.join(str(seed) for seed in config['seeds'])}",
        "",
        "## Smoke Test",
        "",
        "```powershell",
        'cd "F:\\ASL DATASET\\5. Apphear3"',
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_s_stable_primary smoke --run-dir "{run_dir}"',
        "```",
        "",
        "## Full Training",
        "",
        "This is the only longer step. The user should run it manually.",
        "",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_s_stable_primary run --run-dir "{run_dir}"',
        "```",
        "",
        "Resume if interrupted:",
        "",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_s_stable_primary run --run-dir "{run_dir}" --resume',
        "```",
        "",
        "## Check",
        "",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_s_stable_primary check --run-dir "{run_dir}" --require-full-dataset --require-metrics',
        "```",
        "",
    ]) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-S stable-primary 4-sign landmark package")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--classes", nargs="+", default=DEFAULT_CLASSES)
    prepare_parser.add_argument("--branches", nargs="+", default=DEFAULT_BRANCHES)
    prepare_parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    prepare_parser.add_argument("--batch-size", type=int, default=8)
    prepare_parser.add_argument("--epochs", type=int, default=20)
    prepare_parser.add_argument("--learning-rate", type=float, default=5e-4)
    prepare_parser.add_argument("--overwrite", action="store_true")

    smoke_parser = sub.add_parser("smoke")
    smoke_parser.add_argument("--run-dir", type=Path, required=True)
    smoke_parser.add_argument("--rows", type=int, default=12)

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
        elif args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileExistsError, FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-s] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
