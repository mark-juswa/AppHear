"""E4-I reliable-core local vocabulary benchmark package.

Experiment-only. Builds a small benchmark from E4-F cleaned Stage-E features using only the local
signs that are three-signer-supported and already strong in held-out E4-F evidence.

No Android assets, production recognizer files, source videos, or source datasets are modified.
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
from pipeline.rgb.e3_b4_landmark_temporal import _build_model, _inputs_for
from pipeline.rgb.e4_b_strict_runner import check as _base_check
from pipeline.rgb.e4_b_strict_runner import run as _base_run

DEFAULT_SOURCE_RUN = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_f_cleaned_diagnostic_pilot_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_i_reliable_core_4sign_pilot_01"
)
DEFAULT_CLASSES = ["GOOD", "HELLO", "SORRY", "YES"]
DEFAULT_EXCLUDED = ["BYE", "NO", "THANKYOU"]
DEFAULT_BRANCHES = ["conv1d_baseline", "tcn_masked_pool"]
DEFAULT_SEEDS = [101, 202, 303]
SPLITS = {"train": 0, "val": 1, "test": 2}


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


def _load_dataset(run_dir: Path) -> dict[str, np.ndarray]:
    path = run_dir / "dataset" / "landmark_features.npz"
    if not path.exists():
        raise FileNotFoundError(f"missing dataset: {path}")
    data = np.load(path, allow_pickle=False)
    required = {"landmarks", "frame_mask", "y", "split_index", "lengths", "participant_ids", "sample_ids"}
    missing = required.difference(data.files)
    if missing:
        raise ValueError(f"dataset missing keys: {sorted(missing)}")
    landmarks = data["landmarks"].astype(np.float32)
    if landmarks.ndim != 3 or tuple(landmarks.shape[1:]) != (96, 258):
        raise ValueError(f"expected [N,96,258], got {list(landmarks.shape)}")
    return {
        "landmarks": landmarks,
        "frame_mask": data["frame_mask"].astype(bool),
        "y": data["y"].astype(np.int64),
        "split_index": data["split_index"].astype(np.int64),
        "lengths": data["lengths"].astype(np.int32),
        "participant_ids": np.asarray(data["participant_ids"]).astype(str),
        "sample_ids": np.asarray(data["sample_ids"]).astype(str),
    }


def _split_counts(split_index: np.ndarray) -> dict[str, int]:
    return {split: int(np.sum(split_index == idx)) for split, idx in SPLITS.items()}


def _class_counts(y: np.ndarray, split_index: np.ndarray, classes: list[str]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for split, split_id in SPLITS.items():
        split_y = y[split_index == split_id]
        result[split] = {classes[class_id]: int(np.sum(split_y == class_id)) for class_id in range(len(classes))}
    return result


def _signer_counts(manifest: list[dict[str, str]], classes: list[str]) -> dict[str, dict[str, list[str]]]:
    result: dict[str, dict[str, set[str]]] = {gloss: {split: set() for split in SPLITS} for gloss in classes}
    for row in manifest:
        gloss = row.get("canonical_gloss", "")
        split = row.get("split", "")
        signer = row.get("signer_id", "")
        if gloss in result and split in result[gloss] and signer:
            result[gloss][split].add(signer)
    return {gloss: {split: sorted(signers) for split, signers in split_map.items()} for gloss, split_map in result.items()}


def _load_e4f_reference(source_run: Path) -> dict[str, Any]:
    metrics_path = source_run / "metrics" / "metrics.json"
    if not metrics_path.exists():
        return {}
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    try:
        return {
            row["gloss"]: {
                "count": row["count"],
                "correct": row["correct"],
                "accuracy": row["accuracy"],
            }
            for row in metrics["branches"]["tcn_masked_pool"]["303"]["best"]["test"]["per_class"]
        }
    except KeyError:
        return {}


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    source_run = args.source_run
    output = args.output
    classes = list(args.classes)
    class_to_new = {gloss: idx for idx, gloss in enumerate(classes)}
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("dataset", "logs", "metrics", "models", "smoke"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    source_config = json.loads((source_run / "pilot_config.json").read_text(encoding="utf-8"))
    source_classes = list(source_config["classes"])
    missing = sorted(set(classes).difference(source_classes))
    if missing:
        raise ValueError(f"selected classes missing from source config: {missing}")
    old_to_new = {source_classes.index(gloss): new_id for gloss, new_id in class_to_new.items()}
    source_dataset = _load_dataset(source_run)
    source_manifest = _read_csv(source_run / "pilot_manifest.csv")

    keep_mask = np.asarray([int(label) in old_to_new for label in source_dataset["y"]], dtype=bool)
    if not np.any(keep_mask):
        raise ValueError("selected classes produced an empty dataset")
    new_y = np.asarray([old_to_new[int(label)] for label in source_dataset["y"][keep_mask]], dtype=np.int64)
    kept_ids = set(source_dataset["sample_ids"][keep_mask].tolist())

    kept_manifest: list[dict[str, Any]] = []
    excluded_manifest: list[dict[str, Any]] = []
    for row in source_manifest:
        if row["sample_id"] in kept_ids:
            updated = dict(row)
            updated["class_id"] = str(class_to_new[updated["canonical_gloss"]])
            kept_manifest.append(updated)
        else:
            excluded_manifest.append(row)

    if not kept_manifest:
        raise ValueError("selected classes produced an empty manifest")
    fields = list(source_manifest[0].keys())
    _write_csv(output / "pilot_manifest.csv", kept_manifest, fields)
    _write_csv(output / "excluded_manifest_rows.csv", excluded_manifest, fields)
    _write_csv(output / "selected_classes.csv", [{"class_id": idx, "gloss": gloss} for idx, gloss in enumerate(classes)], ["class_id", "gloss"])

    subset = {
        "landmarks": source_dataset["landmarks"][keep_mask],
        "frame_mask": source_dataset["frame_mask"][keep_mask],
        "y": new_y,
        "split_index": source_dataset["split_index"][keep_mask],
        "lengths": source_dataset["lengths"][keep_mask],
        "participant_ids": source_dataset["participant_ids"][keep_mask],
        "sample_ids": source_dataset["sample_ids"][keep_mask],
    }
    np.savez_compressed(output / "dataset" / "landmark_features.npz", **subset)

    e4f_reference = _load_e4f_reference(source_run)
    local_candidate_report = []
    for gloss in classes + list(args.excluded):
        ref = e4f_reference.get(gloss, {})
        local_candidate_report.append(
            {
                "gloss": gloss,
                "decision": "selected_reliable_core" if gloss in classes else "excluded_from_core",
                "e4f_selected_tcn_seed303_test_accuracy": ref.get("accuracy", ""),
                "e4f_test_count": ref.get("count", ""),
                "reason": _reason_for(gloss),
            }
        )
    _write_csv(
        output / "logs" / "candidate_decision_report.csv",
        local_candidate_report,
        ["gloss", "decision", "e4f_selected_tcn_seed303_test_accuracy", "e4f_test_count", "reason"],
    )

    config = {
        "experiment": "e4_i_reliable_core_4sign_v1",
        "purpose": "reliable-core local benchmark after excluding weak/bad local signs; no extraction or Android changes",
        "run_dir": str(output.resolve()),
        "source_run": str(source_run.resolve()),
        "input_shape": [96, 258],
        "schema_version": SCHEMA_VERSION,
        "classes": classes,
        "class_count": len(classes),
        "excluded_classes": list(args.excluded),
        "active_rows": int(subset["landmarks"].shape[0]),
        "excluded_rows": len(excluded_manifest),
        "split_counts": _split_counts(subset["split_index"]),
        "class_counts": _class_counts(subset["y"], subset["split_index"], classes),
        "signers_by_class_split": _signer_counts(kept_manifest, classes),
        "batch_size": int(args.batch_size),
        "epochs": int(args.epochs),
        "learning_rate": float(args.learning_rate),
        "branches": list(args.branches),
        "seeds": list(args.seeds),
        "random_baseline": 1.0 / len(classes),
        "long_steps": ["run"],
        "gate": {
            "go_if": [
                "validation-selected mean test accuracy >= 0.85",
                "every selected class test accuracy >= 0.80 on the held-out signer",
                "no predicted-class collapse and no single class dominates predictions",
            ],
            "no_go_if": [
                "any selected reliable-core class falls below 0.80 test accuracy",
                "validation remains near-perfect while held-out test is much lower",
                "prediction distribution collapses to one or two classes",
            ],
        },
        "warnings": [
            "This is a small reliable-core benchmark, not a full vocabulary model.",
            "It intentionally excludes BYE, NO, and THANKYOU from the next pass due E4-F/E4-G evidence.",
            "No Android integration, model export, or production replacement is authorized from prepare/smoke alone.",
        ],
        "e4f_reference_selected_tcn_seed303_test_per_class": {gloss: e4f_reference.get(gloss, {}) for gloss in classes + list(args.excluded)},
    }
    _write_json(output / "pilot_config.json", config)
    _write_json(
        output / "logs" / "prepare_summary.json",
        {
            "experiment": config["experiment"],
            "run_dir": config["run_dir"],
            "classes": classes,
            "excluded_classes": list(args.excluded),
            "active_rows": config["active_rows"],
            "excluded_rows": config["excluded_rows"],
            "split_counts": config["split_counts"],
            "class_counts": config["class_counts"],
            "passed": True,
        },
    )
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def _reason_for(gloss: str) -> str:
    reasons = {
        "GOOD": "selected: three-signer local support and E4-F test 29/30",
        "HELLO": "selected: three-signer local support and E4-F test 28/30",
        "SORRY": "selected: three-signer local support and E4-F test 29/30",
        "YES": "selected: three-signer local support and E4-F test 25/28",
        "BYE": "excluded: E4-F test 0/29 and E4-G BYE->YES collapse 28/29",
        "NO": "excluded: E4-F test 12/30 and E4-G NO->YES confusion 17/30",
        "THANKYOU": "excluded for core: E4-E relabel concentration and E4-F only 10/17",
    }
    return reasons.get(gloss, "not selected for this reliable-core benchmark")


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    data = _load_dataset(run_dir)
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
        if config.get("experiment") != "e4_i_reliable_core_4sign_v1":
            result["errors"].append("unexpected experiment id")
            result["passed"] = False
        if config.get("classes") != DEFAULT_CLASSES:
            result["errors"].append("unexpected reliable-core class list")
            result["passed"] = False
        for required in ("excluded_manifest_rows.csv", "logs/candidate_decision_report.csv", "logs/prepare_summary.json"):
            if not (run_dir / required).exists():
                result["errors"].append(f"missing output: {required}")
                result["passed"] = False
    _write_json(run_dir / "check_report.json", result)
    return result


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join(
        [
            "# E4-I Reliable-Core 4-Sign Benchmark",
            "",
            "This benchmark intentionally stops trying to rescue bad local signs.",
            "It keeps only the local signs that are three-signer-supported and already strong in E4-F.",
            "",
            "## Selected Classes",
            "",
            f"- {', '.join(config['classes'])}",
            "",
            "## Excluded From This Core",
            "",
            f"- {', '.join(config['excluded_classes'])}",
            "",
            "## Dataset",
            "",
            f"- Active rows: {config['active_rows']}",
            f"- Split counts: {config['split_counts']}",
            f"- Class counts: {config['class_counts']}",
            "",
            "## Smoke Test",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_i_reliable_core smoke --run-dir "{run_dir}"',
            "```",
            "",
            "## Full Training",
            "",
            "This is the only longer step. The user should run it manually.",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_i_reliable_core run --run-dir "{run_dir}"',
            "```",
            "",
            "Resume if interrupted:",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_i_reliable_core run --run-dir "{run_dir}" --resume',
            "```",
            "",
            "## Check",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_i_reliable_core check --run-dir "{run_dir}" --require-full-dataset --require-metrics',
            "```",
            "",
            "## Gate",
            "",
            "Go only if validation-selected mean test accuracy is >= 0.85 and every class is >= 0.80 on held-out test.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-I reliable-core local benchmark package")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--classes", nargs="+", default=DEFAULT_CLASSES)
    prepare_parser.add_argument("--excluded", nargs="+", default=DEFAULT_EXCLUDED)
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
        print(f"[rgb/e4-i-core] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
