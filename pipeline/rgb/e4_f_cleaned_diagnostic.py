"""E4-F cleaned diagnostic package.

This experiment removes rows marked relabel in E4-E from the already-extracted E4-D tensor, then
runs the same Conv1D vs masked-TCN diagnostic. It does not rerun MediaPipe extraction and does not
modify Android or production recognizer assets.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.features.contract import SCHEMA_VERSION
from pipeline.rgb.e3_b4_landmark_temporal import _build_model, _inputs_for
from pipeline.rgb.e4_b_strict_runner import check as _base_check
from pipeline.rgb.e4_b_strict_runner import run as _base_run

DEFAULT_SOURCE_RUN = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_pilot_01"
)
DEFAULT_REVIEW_RUN = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_e_error_review_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_f_cleaned_diagnostic_pilot_01"
)
DEFAULT_BRANCHES = ["conv1d_baseline", "tcn_masked_pool"]
DEFAULT_SEEDS = [101, 202, 303]
SPLITS = {"train": 0, "val": 1, "test": 2}
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


def _load_source_dataset(source_run: Path) -> dict[str, np.ndarray]:
    path = source_run / "dataset" / "landmark_features.npz"
    if not path.exists():
        raise FileNotFoundError(f"missing source dataset: {path}")
    data = np.load(path, allow_pickle=False)
    required = {"landmarks", "frame_mask", "y", "split_index", "lengths", "participant_ids", "sample_ids"}
    missing = required.difference(data.files)
    if missing:
        raise ValueError(f"source dataset missing keys: {sorted(missing)}")
    landmarks = data["landmarks"].astype(np.float32)
    if landmarks.ndim != 3 or tuple(landmarks.shape[1:]) != (96, 258):
        raise ValueError(f"expected source landmarks [N,96,258], got {list(landmarks.shape)}")
    return {
        "landmarks": landmarks,
        "frame_mask": data["frame_mask"].astype(bool),
        "y": data["y"].astype(np.int64),
        "split_index": data["split_index"].astype(np.int64),
        "lengths": data["lengths"].astype(np.int32),
        "participant_ids": np.asarray(data["participant_ids"]).astype(str),
        "sample_ids": np.asarray(data["sample_ids"]).astype(str),
    }


def _load_relabel_sample_ids(review_run: Path) -> set[str]:
    path = review_run / "review_queue.csv"
    if not path.exists():
        raise FileNotFoundError(f"missing E4-E review queue: {path}")
    rows = _read_csv(path)
    relabel = {
        row["sample_id"]
        for row in rows
        if row.get("recommended_action", "").strip().lower() == "relabel"
    }
    if not relabel:
        raise ValueError("E4-E review queue has no relabel rows; E4-F cleanup would be a no-op")
    return relabel


def _split_counts(split_index: np.ndarray) -> dict[str, int]:
    return {split: int(np.sum(split_index == index)) for split, index in SPLITS.items()}


def _class_counts(y: np.ndarray, split_index: np.ndarray, classes: list[str]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for split, split_id in SPLITS.items():
        split_y = y[split_index == split_id]
        result[split] = {classes[class_id]: int(np.sum(split_y == class_id)) for class_id in range(len(classes))}
    return result


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    source_run = args.source_run
    review_run = args.review_run
    output = args.output
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("dataset", "logs", "metrics", "models", "smoke"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    source_config = json.loads((source_run / "pilot_config.json").read_text(encoding="utf-8"))
    source_manifest = _read_csv(source_run / "pilot_manifest.csv")
    source_dataset = _load_source_dataset(source_run)
    relabel_ids = _load_relabel_sample_ids(review_run)

    sample_ids = source_dataset["sample_ids"]
    keep_mask = np.asarray([sample_id not in relabel_ids for sample_id in sample_ids], dtype=bool)
    if int(np.sum(~keep_mask)) != len(relabel_ids):
        missing = sorted(relabel_ids.difference(set(sample_ids.tolist())))
        raise ValueError(f"some relabel sample_ids were not found in E4-D tensor: {missing[:10]}")

    kept_manifest = [row for row in source_manifest if row["sample_id"] not in relabel_ids]
    removed_manifest = [row for row in source_manifest if row["sample_id"] in relabel_ids]
    fields = list(source_manifest[0].keys()) if source_manifest else []
    _write_csv(output / "pilot_manifest.csv", kept_manifest, fields)
    _write_csv(output / "removed_relabel_rows.csv", removed_manifest, fields)
    _write_csv(output / "selected_classes.csv", [{"class_id": idx, "gloss": gloss} for idx, gloss in enumerate(source_config["classes"])], ["class_id", "gloss"])

    cleaned = {
        "landmarks": source_dataset["landmarks"][keep_mask],
        "frame_mask": source_dataset["frame_mask"][keep_mask],
        "y": source_dataset["y"][keep_mask],
        "split_index": source_dataset["split_index"][keep_mask],
        "lengths": source_dataset["lengths"][keep_mask],
        "participant_ids": source_dataset["participant_ids"][keep_mask],
        "sample_ids": source_dataset["sample_ids"][keep_mask],
    }
    np.savez_compressed(output / "dataset" / "landmark_features.npz", **cleaned)

    config = {
        "experiment": "e4_f_cleaned_diagnostic_v1",
        "purpose": "cleaned diagnostic rerun after E4-E manual relabel audit; not production training",
        "run_dir": str(output.resolve()),
        "source_run": str(source_run.resolve()),
        "review_run": str(review_run.resolve()),
        "input_shape": [96, 258],
        "schema_version": SCHEMA_VERSION,
        "classes": list(source_config["classes"]),
        "class_count": int(source_config["class_count"]),
        "manifest_rows": len(kept_manifest),
        "active_rows": int(cleaned["landmarks"].shape[0]),
        "removed_rows": len(removed_manifest),
        "removed_policy": "exclude rows whose E4-E recommended_action is relabel",
        "split_counts": _split_counts(cleaned["split_index"]),
        "class_counts": _class_counts(cleaned["y"], cleaned["split_index"], source_config["classes"]),
        "batch_size": int(args.batch_size),
        "epochs": int(args.epochs),
        "learning_rate": float(args.learning_rate),
        "branches": list(args.branches),
        "seeds": list(args.seeds),
        "long_steps": ["run"],
        "baseline_reference": {
            "e4_d_masked_tcn_mean_best_test": 0.6286,
            "e4_d_best_tcn_seed_303_best_val": 0.9818,
            "e4_d_best_tcn_seed_303_best_test": 0.6333,
            "random_baseline": 1.0 / int(source_config["class_count"]),
        },
        "gate": {
            "go_if": [
                "cleaned diagnostic improves weak-class behavior without prediction collapse",
                "masked TCN remains at least as strong as Conv1D after validation selection",
                "BYE/NO/THANKYOU per-class results are reported explicitly",
            ],
            "no_go_if": [
                "BYE and NO remain weak after label cleanup",
                "validation stays near-perfect while held-out test remains much lower",
                "prediction distribution remains dominated by YES/SORRY or another small group",
            ],
        },
        "warnings": [
            "Cleaned diagnostic only: relabel rows were removed after looking at E4-D prediction failures.",
            "Do not report this as a pristine untouched test-set result.",
            "No Android integration, model export, or production recognizer replacement is authorized.",
            "This reuses existing E4-D MediaPipe features; no new extraction is performed.",
        ],
    }
    _write_json(output / "pilot_config.json", config)
    _write_json(
        output / "logs" / "cleanup_summary.json",
        {
            "source_rows": int(source_dataset["landmarks"].shape[0]),
            "kept_rows": int(cleaned["landmarks"].shape[0]),
            "removed_rows": len(removed_manifest),
            "removed_sample_ids": sorted(relabel_ids),
            "split_counts": config["split_counts"],
            "class_counts": config["class_counts"],
            "passed": True,
        },
    )
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    data = _load_source_dataset(run_dir)
    rows = min(int(args.rows), int(data["landmarks"].shape[0]))
    x = data["landmarks"][:rows]
    frame_mask = data["frame_mask"][:rows]
    y = data["y"][:rows]
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


def run(args: argparse.Namespace) -> dict[str, Any]:
    return _base_run(args)


def check(args: argparse.Namespace) -> dict[str, Any]:
    result = _base_check(args)
    run_dir = args.run_dir
    config_path = run_dir / "pilot_config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if config.get("experiment") != "e4_f_cleaned_diagnostic_v1":
            result["errors"].append("unexpected experiment id")
            result["passed"] = False
        if not (run_dir / "removed_relabel_rows.csv").exists():
            result["errors"].append("missing output: removed_relabel_rows.csv")
            result["passed"] = False
        if not (run_dir / "logs" / "cleanup_summary.json").exists():
            result["errors"].append("missing output: logs/cleanup_summary.json")
            result["passed"] = False
    _write_json(run_dir / "check_report.json", result)
    return result


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join(
        [
            "# E4-F Cleaned Diagnostic",
            "",
            "Experiment-only cleaned diagnostic. It reuses E4-D extracted features and removes rows marked relabel in E4-E.",
            "",
            "## Scope",
            "",
            f"- Classes: {', '.join(config['classes'])}",
            f"- Active rows: {config['active_rows']}",
            f"- Removed rows: {config['removed_rows']}",
            f"- Split counts: {config['split_counts']}",
            f"- Branches: {', '.join(config['branches'])}",
            f"- Seeds: {', '.join(str(seed) for seed in config['seeds'])}",
            f"- Epochs per run command: {config['epochs']}",
            "",
            "## Smoke Test",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_f_cleaned_diagnostic smoke --run-dir "{run_dir}"',
            "```",
            "",
            "## Full Training",
            "",
            "This is the long step. The user should run it manually.",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_f_cleaned_diagnostic run --run-dir "{run_dir}"',
            "```",
            "",
            "Resume interrupted training:",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_f_cleaned_diagnostic run --run-dir "{run_dir}" --resume',
            "```",
            "",
            "## Check",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_f_cleaned_diagnostic check --run-dir "{run_dir}" --require-full-dataset --require-metrics',
            "```",
            "",
            "## Important",
            "",
            "Do not treat this as a pristine test-set result. It is a cleaned diagnostic after E4-E review.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-F cleaned diagnostic package")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    prepare_parser.add_argument("--review-run", type=Path, default=DEFAULT_REVIEW_RUN)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--branches", nargs="+", default=DEFAULT_BRANCHES)
    prepare_parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    prepare_parser.add_argument("--batch-size", type=int, default=8)
    prepare_parser.add_argument("--epochs", type=int, default=20)
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
        print(f"[rgb/e4-f-cleaned] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
