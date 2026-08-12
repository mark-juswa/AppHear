"""E5-B ASL-led broad primary batch pilot.

Builds a 50-class ASL Citizen-led landmark dataset from existing [96,258]
feature tensors. Local supplementary rows are included where available, but
local support is not required for every class. This is a diagnostic batch for
scaling, not production export.

Experiment-only: no extraction, Android changes, model export, production
recognizer replacement, or source dataset mutation.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.features.contract import SCHEMA_VERSION
from pipeline.rgb.e3_b4_landmark_temporal import _build_model, _inputs_for
from pipeline.rgb.e4_b_strict_runner import check as _base_check
from pipeline.rgb.e4_b_strict_runner import run as _base_run

DEFAULT_E5A_RUN = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_a_dual_source_batch_screen_01")
DEFAULT_COMBINED_DIR = Path(r"F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_pc_236")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_b_asl_led_50_primary_01")
DEFAULT_BRANCHES = ["conv1d_baseline"]
DEFAULT_SEEDS = [101, 202, 303]
SPLITS = {"train": 0, "val": 1, "test": 2}
SPLIT_NAMES = {v: k for k, v in SPLITS.items()}
STABLE_PRIMARY = ["GOOD", "HELLO", "HAVE", "KNOW"]
EXCLUDED_PRIMARY = {"SORRY", "HELP", "BECOME", "MAKE", "GET", "WELCOME2", "BYE", "NO", "YES", "THANKYOU"}
LOCAL_ID_RE = re.compile(r"^[0-9A-F]{6}-S\d{3}$", re.IGNORECASE)


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


def _load_vocab(combined_dir: Path) -> dict[str, int]:
    for path in [combined_dir / "vocab.json", combined_dir.parent / "features_conversational" / "vocab.json"]:
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            return {str(k).upper(): int(v) for k, v in raw.items()}
    raise FileNotFoundError(f"missing vocab.json near {combined_dir}")


def _source_of(participant_id: str) -> str:
    return "local" if LOCAL_ID_RE.match(participant_id) else "asl_citizen"


def _select_classes(e5a_run: Path, class_count: int) -> list[str]:
    inventory = _read_csv(e5a_run / "tables" / "candidate_inventory_236.csv")
    by_gloss = {row["gloss"]: row for row in inventory}
    selected = list(STABLE_PRIMARY)
    candidates = []
    for row in inventory:
        gloss = row["gloss"]
        if gloss in selected or gloss in EXCLUDED_PRIMARY:
            continue
        asl_train = int(row.get("asl_train_count") or 0)
        asl_val = int(row.get("asl_val_count") or 0)
        asl_test = int(row.get("asl_test_count") or 0)
        asl_test_signers = int(row.get("asl_test_signer_count") or 0)
        if asl_train < 10 or asl_val < 2 or asl_test < 2 or asl_test_signers < 5:
            continue
        local_count = int(row.get("local_total_count") or 0)
        local_signers = int(row.get("local_total_signer_count") or 0)
        e4p_mean = float(row["e4p_mean_latest_acc"]) if row.get("e4p_mean_latest_acc") else 0.0
        e4p_min = float(row["e4p_min_latest_acc"]) if row.get("e4p_min_latest_acc") else 0.0
        score = asl_train + asl_val + asl_test + local_count * 1.5 + local_signers * 15 + e4p_mean * 30 + e4p_min * 20
        candidates.append((score, gloss))
    for _score, gloss in sorted(candidates, reverse=True):
        if len(selected) >= class_count:
            break
        selected.append(gloss)
    if len(selected) < class_count:
        raise ValueError(f"only selected {len(selected)} classes, requested {class_count}")
    missing = [gloss for gloss in selected if gloss not in by_gloss]
    if missing:
        raise ValueError(f"selected classes missing from E5-A inventory: {missing}")
    return selected


def _load_split(path: Path) -> dict[str, np.ndarray]:
    if not path.exists():
        raise FileNotFoundError(f"missing tensor: {path}")
    data = np.load(path, allow_pickle=False)
    return {
        "X": data["X"].astype(np.float32),
        "frame_mask": data["frame_mask"].astype(bool),
        "lengths": data["lengths"].astype(np.int32),
        "y": data["y"].astype(np.int64),
        "participant_ids": np.asarray(data["participant_ids"]).astype(str),
    }


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("dataset", "logs", "metrics", "models", "smoke", "tables"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    vocab = _load_vocab(args.combined_dir)
    selected = list(args.classes) if args.classes else _select_classes(args.e5a_run, int(args.class_count))
    if any(gloss in EXCLUDED_PRIMARY for gloss in selected):
        raise ValueError(f"selected primary classes include excluded/confusion signs: {sorted(set(selected) & EXCLUDED_PRIMARY)}")
    missing_vocab = [gloss for gloss in selected if gloss not in vocab]
    if missing_vocab:
        raise ValueError(f"selected classes missing from vocab: {missing_vocab}")
    class_to_new = {vocab[gloss]: idx for idx, gloss in enumerate(selected)}

    features = []
    masks = []
    labels = []
    split_ids = []
    lengths = []
    participants = []
    sample_ids = []
    source_ids = []
    rows = []
    for split_name, split_id in SPLITS.items():
        data = _load_split(args.combined_dir / f"{split_name}.npz")
        for source_class, new_class in class_to_new.items():
            indices = np.flatnonzero(data["y"] == source_class)
            if indices.size == 0:
                continue
            gloss = selected[new_class]
            features.append(data["X"][indices])
            masks.append(data["frame_mask"][indices])
            labels.append(np.full(indices.size, new_class, dtype=np.int64))
            split_ids.append(np.full(indices.size, split_id, dtype=np.int64))
            lengths.append(data["lengths"][indices])
            participants.append(data["participant_ids"][indices])
            these_sources = np.asarray([_source_of(pid) for pid in data["participant_ids"][indices]])
            source_ids.append(these_sources)
            ids = np.asarray([f"{split_name}_{gloss}_{int(i):05d}" for i in indices]).astype(str)
            sample_ids.append(ids)
            for pos, idx in enumerate(indices):
                rows.append({
                    "sample_id": str(ids[pos]),
                    "split": split_name,
                    "canonical_gloss": gloss,
                    "class_id": new_class,
                    "source_class_id": int(source_class),
                    "participant_id": str(data["participant_ids"][idx]),
                    "source_id": str(these_sources[pos]),
                    "source_index": int(idx),
                    "source_path": str((args.combined_dir / f"{split_name}.npz").resolve()),
                })
    dataset = {
        "landmarks": np.concatenate(features, axis=0).astype(np.float32),
        "frame_mask": np.concatenate(masks, axis=0).astype(bool),
        "y": np.concatenate(labels, axis=0).astype(np.int64),
        "split_index": np.concatenate(split_ids, axis=0).astype(np.int64),
        "lengths": np.concatenate(lengths, axis=0).astype(np.int32),
        "participant_ids": np.concatenate(participants, axis=0).astype(str),
        "sample_ids": np.concatenate(sample_ids, axis=0).astype(str),
        "source_ids": np.concatenate(source_ids, axis=0).astype(str),
    }
    order = np.lexsort((dataset["sample_ids"], dataset["source_ids"], dataset["split_index"], dataset["y"]))
    dataset = {key: value[order] for key, value in dataset.items()}
    rows = sorted(rows, key=lambda row: str(row["sample_id"]))
    np.savez_compressed(output / "dataset" / "landmark_features.npz", **dataset)
    _write_csv(output / "pilot_manifest.csv", rows, ["sample_id", "split", "canonical_gloss", "class_id", "source_class_id", "participant_id", "source_id", "source_index", "source_path"])
    _write_csv(output / "selected_classes.csv", [{"class_id": idx, "gloss": gloss} for idx, gloss in enumerate(selected)], ["class_id", "gloss"])
    counts = Counter(dataset["source_ids"].tolist())
    split_counts = {name: int(np.sum(dataset["split_index"] == sid)) for name, sid in SPLITS.items()}
    class_counts = {
        split_name: {
            gloss: int(np.sum((dataset["split_index"] == split_id) & (dataset["y"] == idx)))
            for idx, gloss in enumerate(selected)
        }
        for split_name, split_id in SPLITS.items()
    }
    config = {
        "experiment": "e5_b_asl_led_primary_batch_v1",
        "purpose": "ASL Citizen-led 50-class primary diagnostic with local supplementary rows where available",
        "run_dir": str(output.resolve()),
        "e5a_run": str(args.e5a_run.resolve()),
        "combined_dir": str(args.combined_dir.resolve()),
        "schema_version": SCHEMA_VERSION,
        "input_shape": [96, 258],
        "classes": selected,
        "class_count": len(selected),
        "active_rows": int(dataset["landmarks"].shape[0]),
        "split_counts": split_counts,
        "source_counts": dict(sorted(counts.items())),
        "class_counts": class_counts,
        "branches": list(args.branches),
        "seeds": [int(seed) for seed in args.seeds],
        "batch_size": int(args.batch_size),
        "epochs": int(args.epochs),
        "learning_rate": float(args.learning_rate),
        "gate": {
            "diagnostic_go_if": [
                "macro/per-class ASL held-out test accuracy is clearly above random baseline",
                "stable controls remain strong",
                "local-supported signs do not collapse into one dominant class",
                "confusion groups are exported as tier recommendations, not hidden by aggregate accuracy",
            ],
            "no_go_if": [
                "prediction collapse repeats E4-P failure pattern",
                "stable controls degrade materially",
                "candidate signs only work for one source or one signer",
            ],
        },
        "warnings": [
            "Diagnostic only; not production-ready even if accuracy is high.",
            "Local data supplements where available but is not required for every class.",
            "SORRY and known hard groups are excluded from this primary model and remain routed/deferred.",
            "No Android/export is authorized by this package.",
        ],
    }
    _write_json(output / "pilot_config.json", config)
    _write_json(output / "logs" / "dataset_summary.json", {"rows": config["active_rows"], "split_counts": split_counts, "source_counts": config["source_counts"], "class_count": len(selected)})
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    data = np.load(run_dir / "dataset" / "landmark_features.npz", allow_pickle=False)
    x = data["landmarks"].astype(np.float32)
    fm = data["frame_mask"].astype(bool)
    y = data["y"].astype(np.int64)
    take = min(int(args.rows), x.shape[0])
    summary: dict[str, Any] = {"rows": take, "shape": [int(v) for v in x[:take].shape], "branches": {}}
    for branch in config["branches"]:
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(12345)
        model = _build_model(branch, (96, 258), int(config["class_count"]), float(config["learning_rate"]))
        probs = model.predict(_inputs_for(branch, x[:take], fm[:take]), batch_size=min(8, take), verbose=0)
        loss = model.train_on_batch(_inputs_for(branch, x[:take], fm[:take]), y[:take])
        weights_path = run_dir / "smoke" / f"{branch}.weights.h5"
        model.save_weights(weights_path)
        summary["branches"][branch] = {
            "forward_shape": [int(v) for v in probs.shape],
            "train_on_batch": [float(v) for v in np.atleast_1d(loss).tolist()],
            "weights_saved": str(weights_path.resolve()),
        }
    _write_json(run_dir / "smoke" / "smoke_summary.json", summary)
    return summary


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join([
        "# E5-B ASL-Led Primary Batch",
        "",
        "Diagnostic-only broad landmark batch. It does not modify Android or production assets.",
        "",
        f"- Classes: `{config['class_count']}`",
        f"- Rows: `{config['active_rows']}`",
        f"- Split counts: `{config['split_counts']}`",
        f"- Source counts: `{config['source_counts']}`",
        "",
        "## Smoke",
        "```powershell",
        'cd "F:\\ASL DATASET\\5. Apphear3"',
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_b_asl_led_primary_batch smoke --run-dir "{run_dir}"',
        "```",
        "",
        "## Full Training",
        "```powershell",
        'cd "F:\\ASL DATASET\\5. Apphear3"',
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_b_asl_led_primary_batch run --run-dir "{run_dir}"',
        "```",
        "",
        "## Check",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_b_asl_led_primary_batch check --run-dir "{run_dir}" --require-dataset --require-metrics',
        "```",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description="E5-B ASL-led primary batch")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--e5a-run", type=Path, default=DEFAULT_E5A_RUN)
    prep.add_argument("--combined-dir", type=Path, default=DEFAULT_COMBINED_DIR)
    prep.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prep.add_argument("--class-count", type=int, default=50)
    prep.add_argument("--classes", nargs="*")
    prep.add_argument("--branches", nargs="+", default=DEFAULT_BRANCHES)
    prep.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    prep.add_argument("--epochs", type=int, default=24)
    prep.add_argument("--batch-size", type=int, default=32)
    prep.add_argument("--learning-rate", type=float, default=8e-4)
    prep.add_argument("--overwrite", action="store_true")

    smoke_p = sub.add_parser("smoke")
    smoke_p.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    smoke_p.add_argument("--rows", type=int, default=32)

    run_p = sub.add_parser("run")
    run_p.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    run_p.add_argument("--resume", action="store_true")

    check_p = sub.add_parser("check")
    check_p.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    check_p.add_argument("--require-dataset", action="store_true")
    check_p.add_argument("--require-full-dataset", action="store_true")
    check_p.add_argument("--require-metrics", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "smoke":
            result = smoke(args)
        elif args.command == "run":
            result = _base_run(args)
        elif args.command == "check":
            result = _base_check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileExistsError, FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e5-b] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
