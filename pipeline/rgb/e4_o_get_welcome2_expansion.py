"""E4-O GET/WELCOME2 dual-source extraction and 7-sign training screen.

Experiment-only. Reuses the E4-N 5-sign dataset, adds ASL Citizen existing features for
GET/WELCOME2, and extracts local validated GET/WELCOME2 videos before training. No Android
assets, production models, source videos, or source datasets are modified.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.extract.config import load_config as load_extract_config
from pipeline.extract.landmarks import LandmarkExtractor
from pipeline.features.contract import SCHEMA_VERSION, clip_features_realtimed
from pipeline.normalize.config import load_config as load_normalize_config
from pipeline.rgb.e3_b4_landmark_temporal import _build_model, _inputs_for, _load_weights_model
from pipeline.rgb.e4_b_strict_runner import check as _base_check
from pipeline.rgb.e4_b_strict_runner import run as _base_run

DEFAULT_BASE_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_n_dual_source_5sign_screen_01")
DEFAULT_VALIDATION_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_validation_01")
DEFAULT_ASL_FEATURE_DIR = Path(r"F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_o_get_welcome2_7sign_screen_01")
DEFAULT_EXTRACT_CONFIG = Path("pipeline/config/extract.yaml")
DEFAULT_NORMALIZE_CONFIG = Path("pipeline/config/normalize.yaml")
BASE_CLASSES = ["GOOD", "HELLO", "SORRY", "HAVE", "KNOW"]
CANDIDATE_CLASSES = ["GET", "WELCOME2"]
DEFAULT_CLASSES = ["GOOD", "HELLO", "SORRY", "HAVE", "KNOW", "GET", "WELCOME2"]
CORE_CLASSES = ["GOOD", "HELLO", "SORRY"]
SPLITS = {"train": 0, "val": 1, "test": 2}
SPLIT_NAMES = {v: k for k, v in SPLITS.items()}
DEFAULT_BRANCHES = ["conv1d_baseline"]
DEFAULT_SEEDS = [101, 202, 303]


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


def _load_vocab(feature_dir: Path) -> dict[str, int]:
    for path in (feature_dir / "vocab.json", feature_dir.parent / "features_conversational" / "vocab.json"):
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return {str(k).upper(): int(v) for k, v in data.items()}
    raise FileNotFoundError(f"missing vocab.json near {feature_dir}")


def _load_base(run_dir: Path) -> dict[str, np.ndarray]:
    path = run_dir / "dataset" / "landmark_features.npz"
    if not path.exists():
        raise FileNotFoundError(f"missing E4-N base dataset: {path}")
    data = np.load(path, allow_pickle=False)
    return {
        "landmarks": data["landmarks"].astype(np.float32),
        "frame_mask": data["frame_mask"].astype(bool),
        "y": data["y"].astype(np.int64),
        "split_index": data["split_index"].astype(np.int64),
        "lengths": data["lengths"].astype(np.int32),
        "participant_ids": data["participant_ids"].astype(str),
        "sample_ids": data["sample_ids"].astype(str),
        "source_ids": data["source_ids"].astype(str),
    }


def _load_feature_npz(path: Path) -> dict[str, np.ndarray]:
    data = np.load(path, allow_pickle=False)
    return {
        "X": data["X"].astype(np.float32),
        "frame_mask": data["frame_mask"].astype(bool),
        "lengths": data["lengths"].astype(np.int32),
        "y": data["y"].astype(np.int64),
        "participant_ids": data["participant_ids"].astype(str),
    }


def _split_counts(split_index: np.ndarray) -> dict[str, int]:
    return {name: int(np.sum(split_index == sid)) for name, sid in SPLITS.items()}


def _class_counts(y: np.ndarray, split_index: np.ndarray, classes: list[str]) -> dict[str, dict[str, int]]:
    return {split: {classes[cid]: int(np.sum(y[split_index == sid] == cid)) for cid in range(len(classes))} for split, sid in SPLITS.items()}

def _source_class_counts(y: np.ndarray, split_index: np.ndarray, source_ids: np.ndarray, classes: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for source in sorted(set(source_ids.tolist())):
        out[source] = {}
        smask = source_ids == source
        for split, sid in SPLITS.items():
            mask = smask & (split_index == sid)
            out[source][split] = {classes[cid]: int(np.sum(y[mask] == cid)) for cid in range(len(classes))}
    return out


def _asl_candidate_block(feature_dir: Path, vocab: dict[str, int], classes: list[str]) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    blocks: dict[str, list[np.ndarray]] = defaultdict(list)
    rows: list[dict[str, Any]] = []
    for split, split_id in SPLITS.items():
        data = _load_feature_npz(feature_dir / f"{split}.npz")
        for gloss in CANDIDATE_CLASSES:
            source_class = vocab[gloss]
            class_id = classes.index(gloss)
            indices = np.flatnonzero(data["y"] == source_class)
            if indices.size == 0:
                continue
            sample_ids = np.asarray([f"asl_{split}_{gloss}_{int(i):05d}" for i in indices])
            source_id = f"asl_citizen_{split}"
            blocks["landmarks"].append(data["X"][indices])
            blocks["frame_mask"].append(data["frame_mask"][indices])
            blocks["y"].append(np.full(indices.size, class_id, dtype=np.int64))
            blocks["split_index"].append(np.full(indices.size, split_id, dtype=np.int64))
            blocks["lengths"].append(data["lengths"][indices])
            blocks["participant_ids"].append(data["participant_ids"][indices])
            blocks["sample_ids"].append(sample_ids)
            blocks["source_ids"].append(np.asarray([source_id] * indices.size))
            for local_idx, source_index in enumerate(indices):
                rows.append({
                    "sample_id": str(sample_ids[local_idx]),
                    "source_id": source_id,
                    "source_split": split,
                    "split": split,
                    "canonical_gloss": gloss,
                    "class_id": class_id,
                    "participant_id": str(data["participant_ids"][source_index]),
                    "source_index": int(source_index),
                    "source_path": str((feature_dir / f"{split}.npz").resolve()),
                    "notes": "selected_from_asl_citizen_streaming_conversational",
                })
    return {key: np.concatenate(value, axis=0).astype(str if key in {"participant_ids", "sample_ids", "source_ids"} else None) for key, value in blocks.items()}, rows


def _candidate_inventory(validation_run: Path) -> list[dict[str, Any]]:
    rows = _read_csv(validation_run / "validated_clip_inventory.csv")
    selected = [row for row in rows if row.get("canonical_gloss", "").upper() in CANDIDATE_CLASSES and row.get("eligible") == "True"]
    if not selected:
        raise ValueError("no eligible GET/WELCOME2 validation rows found")
    out = []
    for row in selected:
        gloss = row["canonical_gloss"].upper()
        signer = row["signer_id"]
        rep = int(row.get("repetition_index") or 0)
        if signer == "6F7328-S001":
            split = "test"
        else:
            split = "val" if rep > 30 else "train"
        stem = Path(row["video_path"]).stem
        out.append({
            "sample_id": f"local_extract_{gloss}_{stem}",
            "source_id": "local_validated_extracted",
            "source_split": "generated_from_participant",
            "split": split,
            "canonical_gloss": gloss,
            "class_id": DEFAULT_CLASSES.index(gloss),
            "participant_id": signer,
            "source_index": row.get("row_index", ""),
            "source_path": row["video_path"],
            "video_path": row["video_path"],
            "hand_hit_rate": row.get("hand_hit_rate", ""),
            "warnings": row.get("warnings", ""),
            "notes": "pending_local_mediapipe_extraction",
        })
    return sorted(out, key=lambda row: (row["canonical_gloss"], SPLITS[row["split"]], row["participant_id"], row["sample_id"]))


def _per_clip_path(run_dir: Path, sample_id: str) -> Path:
    return run_dir / "dataset" / "per_clip_local_candidates" / f"{sample_id}.npz"


def _extract_feature(row: dict[str, Any], extractor: LandmarkExtractor, normalize_config: Any) -> dict[str, Any]:
    clip, meta = extractor.extract(Path(row["video_path"]))
    release = int(clip.timestamps_ms.shape[0] - 1)
    if release < 0:
        raise ValueError(f"no frames extracted: {row['video_path']}")
    feature, frame_mask, length, _params = clip_features_realtimed(clip.hands_image, clip.pose_image, 0, release, normalize_config, 96)
    hand_present = clip.hand_score > 0.0
    any_hand = float(np.mean(np.any(hand_present, axis=1))) if len(hand_present) else 0.0
    pose_hit = float(np.mean(clip.pose_score > 0.0)) if len(clip.pose_score) else 0.0
    return {"feature": feature.astype(np.float32), "frame_mask": frame_mask.astype(bool), "length": int(length), "native_frames": int(meta["n_frames"]), "native_fps": float(meta["native_fps"]), "hand_hit_rate_extracted": any_hand, "pose_hit_rate_extracted": pose_hit}


def _write_base_dataset(output: Path, base_run: Path, asl_feature_dir: Path, validation_run: Path, classes: list[str]) -> dict[str, Any]:
    base = _load_base(base_run)
    vocab = _load_vocab(asl_feature_dir)
    asl_block, asl_rows = _asl_candidate_block(asl_feature_dir, vocab, classes)
    candidate_rows = _candidate_inventory(validation_run)
    parts = {key: [base[key], asl_block[key]] for key in ("landmarks", "frame_mask", "y", "split_index", "lengths", "participant_ids", "sample_ids", "source_ids")}
    base_rows = _read_csv(base_run / "pilot_manifest.csv")
    for row in base_rows:
        row["source_id"] = row.get("source_id", "e4_n_base")
        row["notes"] = "copied_from_e4_n_base"
    all_rows = base_rows + asl_rows
    dataset = {key: np.concatenate(value, axis=0) for key, value in parts.items()}
    np.savez_compressed(output / "dataset" / "base_plus_asl_features.npz", **dataset)
    fields = ["sample_id", "source_id", "source_split", "split", "canonical_gloss", "class_id", "participant_id", "source_index", "source_path", "notes"]
    _write_csv(output / "pilot_manifest_base_plus_asl.csv", all_rows, fields)
    _write_csv(output / "candidate_manifest.csv", candidate_rows, ["sample_id", "source_id", "source_split", "split", "canonical_gloss", "class_id", "participant_id", "source_index", "source_path", "video_path", "hand_hit_rate", "warnings", "notes"])
    return {"base_plus_asl_rows": int(dataset["landmarks"].shape[0]), "candidate_rows_pending_extraction": len(candidate_rows)}


def _assemble_dataset(run_dir: Path, require_full: bool) -> dict[str, Any]:
    base = np.load(run_dir / "dataset" / "base_plus_asl_features.npz", allow_pickle=False)
    arrays = {key: [base[key]] for key in ("landmarks", "frame_mask", "y", "split_index", "lengths", "participant_ids", "sample_ids", "source_ids")}
    missing = []
    for row in _read_csv(run_dir / "candidate_manifest.csv"):
        path = _per_clip_path(run_dir, row["sample_id"])
        if not path.exists():
            missing.append(row["sample_id"])
            continue
        data = np.load(path, allow_pickle=False)
        arrays["landmarks"].append(data["feature"][None, :, :].astype(np.float32))
        arrays["frame_mask"].append(data["frame_mask"][None, :].astype(bool))
        arrays["y"].append(np.asarray([int(data["y"])], dtype=np.int64))
        arrays["split_index"].append(np.asarray([int(data["split_index"])], dtype=np.int64))
        arrays["lengths"].append(np.asarray([int(data["length"])], dtype=np.int32))
        arrays["participant_ids"].append(np.asarray([str(data["participant_id"])], dtype=str))
        arrays["sample_ids"].append(np.asarray([str(data["sample_id"])], dtype=str))
        arrays["source_ids"].append(np.asarray(["local_validated_extracted"], dtype=str))
    if missing and require_full:
        raise ValueError(f"missing local candidate features for {len(missing)} rows; first={missing[:5]}")
    dataset = {key: np.concatenate(value, axis=0) for key, value in arrays.items()}
    order = np.lexsort((dataset["sample_ids"].astype(str), dataset["source_ids"].astype(str), dataset["split_index"]))
    dataset = {key: value[order] for key, value in dataset.items()}
    np.savez_compressed(run_dir / "dataset" / "landmark_features.npz", **dataset)
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    return {"assembled": True, "rows": int(dataset["landmarks"].shape[0]), "shape": [int(v) for v in dataset["landmarks"].shape], "missing_candidate_rows": len(missing), "split_counts": _split_counts(dataset["split_index"]), "class_counts": _class_counts(dataset["y"], dataset["split_index"], config["classes"]), "source_class_counts": _source_class_counts(dataset["y"], dataset["split_index"], dataset["source_ids"].astype(str), config["classes"])}


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("dataset/per_clip_local_candidates", "logs", "metrics", "models", "smoke"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    classes = list(args.classes)
    if classes != DEFAULT_CLASSES:
        raise ValueError(f"E4-O class contract is fixed: {DEFAULT_CLASSES}")
    base_summary = _write_base_dataset(output, args.base_run, args.asl_feature_dir, args.validation_run, classes)
    active_rows = base_summary["base_plus_asl_rows"] + base_summary["candidate_rows_pending_extraction"]
    base_rows = _read_csv(output / "pilot_manifest_base_plus_asl.csv")
    pending_rows = _read_csv(output / "candidate_manifest.csv")
    combined_rows = base_rows + [{key: row.get(key, "") for key in base_rows[0].keys()} for row in pending_rows]
    _write_csv(output / "pilot_manifest.csv", combined_rows, list(base_rows[0].keys()))
    _write_csv(output / "selected_classes.csv", [{"class_id": idx, "gloss": gloss} for idx, gloss in enumerate(classes)], ["class_id", "gloss"])
    config = {
        "experiment": "e4_o_get_welcome2_7sign_screen_v1",
        "purpose": "extract local GET/WELCOME2 and test 7-sign source-aware expansion after E4-N pass",
        "run_dir": str(output.resolve()),
        "base_run": str(args.base_run.resolve()),
        "validation_run": str(args.validation_run.resolve()),
        "asl_feature_dir": str(args.asl_feature_dir.resolve()),
        "input_shape": [96, 258],
        "schema_version": SCHEMA_VERSION,
        "classes": classes,
        "class_count": len(classes),
        "base_classes": BASE_CLASSES,
        "candidate_classes": CANDIDATE_CLASSES,
        "active_rows": active_rows,
        "base_plus_asl_rows": base_summary["base_plus_asl_rows"],
        "candidate_rows_pending_extraction": base_summary["candidate_rows_pending_extraction"],
        "batch_size": int(args.batch_size),
        "epochs": int(args.epochs),
        "learning_rate": float(args.learning_rate),
        "branches": list(args.branches),
        "seeds": list(args.seeds),
        "random_baseline": 1.0 / len(classes),
        "long_steps": ["extract-candidates", "run"],
        "gate": {"mean_latest_test_min": 0.80, "core_class_test_min": 0.90, "candidate_class_test_min": 0.60},
        "warnings": ["Experiment-only; not production training.", "Local GET/WELCOME2 extraction is the first long step and should be run by the developer.", "No Android integration, TFLite export, or production recognizer replacement is authorized."],
    }
    _write_json(output / "pilot_config.json", config)
    _write_json(output / "logs" / "prepare_summary.json", {**config, "passed": True})
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def extract_candidates(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    rows = _read_csv(run_dir / "candidate_manifest.csv")
    if args.limit is not None:
        rows = rows[: args.limit]
    extract_config = load_extract_config(args.extract_config or DEFAULT_EXTRACT_CONFIG)
    normalize_config = load_normalize_config(args.normalize_config or DEFAULT_NORMALIZE_CONFIG)
    manifest_rows = []
    errors = []
    start = time.perf_counter()
    with LandmarkExtractor(extract_config) as extractor:
        for index, row in enumerate(rows, start=1):
            out_path = _per_clip_path(run_dir, row["sample_id"])
            if out_path.exists() and not args.overwrite_clips:
                manifest_rows.append({**row, "status": "cached", "feature_path": str(out_path)})
                continue
            try:
                item = _extract_feature(row, extractor, normalize_config)
                np.savez_compressed(out_path, feature=item["feature"], frame_mask=item["frame_mask"], y=np.asarray(int(row["class_id"]), dtype=np.int64), split_index=np.asarray(SPLITS[row["split"]], dtype=np.int64), length=np.asarray(item["length"], dtype=np.int32), participant_id=np.asarray(row["participant_id"]), sample_id=np.asarray(row["sample_id"]))
                manifest_rows.append({**row, "status": "ok", "feature_path": str(out_path), "native_frames_extracted": item["native_frames"], "native_fps_extracted": item["native_fps"], "hand_hit_rate_extracted": round(item["hand_hit_rate_extracted"], 4), "pose_hit_rate_extracted": round(item["pose_hit_rate_extracted"], 4)})
                print(f"[e4-o/extract] {index}/{len(rows)} {row['sample_id']}")
            except Exception as err:  # noqa: BLE001
                errors.append(f"{row['sample_id']}: {err}")
                manifest_rows.append({**row, "status": "failed", "reason": str(err)[:240]})
                print(f"[e4-o/extract] FAILED {row['sample_id']}: {err}", file=sys.stderr)
    if manifest_rows:
        _write_csv(run_dir / "logs" / "candidate_feature_extraction_manifest.csv", manifest_rows, sorted({key for row in manifest_rows for key in row}))
    dataset_result = _assemble_dataset(run_dir, require_full=args.require_full and args.limit is None)
    result = {"experiment": config["experiment"], "run_dir": str(run_dir.resolve()), "attempted_candidate_rows": len(rows), "ok_or_cached_candidate_rows": sum(row.get("status") in {"ok", "cached"} for row in manifest_rows), "failed_candidate_rows": sum(row.get("status") == "failed" for row in manifest_rows), "elapsed_seconds": time.perf_counter() - start, "dataset": dataset_result, "errors": errors, "passed": not errors and dataset_result.get("assembled", False)}
    _write_json(run_dir / "logs" / "candidate_feature_extraction_summary.json", result)
    return result


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    data = np.load(run_dir / "dataset" / "landmark_features.npz", allow_pickle=False)
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
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
        result["branches"][branch] = {"forward_shape": [int(v) for v in probs.shape], "train_on_batch": [float(v) for v in np.atleast_1d(loss).tolist()], "weights_saved": str(weights_path.resolve())}
    _write_json(run_dir / "smoke" / "smoke_summary.json", result)
    return result


def _source_eval(branch: str, model: Any, run_dir: Path, batch_size: int, classes: list[str]) -> dict[str, Any]:
    data = np.load(run_dir / "dataset" / "landmark_features.npz", allow_pickle=False)
    x = data["landmarks"].astype(np.float32)
    frame_mask = data["frame_mask"].astype(bool)
    y = data["y"].astype(np.int64)
    split_index = data["split_index"].astype(np.int64)
    source_ids = data["source_ids"].astype(str)
    probs = model.predict(_inputs_for(branch, x, frame_mask), batch_size=batch_size, verbose=0)
    pred = np.argmax(probs, axis=1)
    result: dict[str, Any] = {}
    for source in sorted(set(source_ids.tolist())):
        result[source] = {}
        smask = source_ids == source
        for split, sid in SPLITS.items():
            mask = smask & (split_index == sid)
            if not np.any(mask):
                result[source][split] = {"count": 0, "accuracy": None, "per_class": []}
                continue
            per_class = []
            for class_id, gloss in enumerate(classes):
                cmask = mask & (y == class_id)
                if np.any(cmask):
                    per_class.append({"gloss": gloss, "count": int(np.sum(cmask)), "correct": int(np.sum(pred[cmask] == y[cmask])), "accuracy": float(np.mean(pred[cmask] == y[cmask]))})
            result[source][split] = {"count": int(np.sum(mask)), "accuracy": float(np.mean(pred[mask] == y[mask])), "per_class": per_class, "predicted_class_counts": {classes[int(cid)]: int(count) for cid, count in zip(*np.unique(pred[mask], return_counts=True))}}
    return result


def _source_aware_summary(run_dir: Path, metrics: dict[str, Any]) -> dict[str, Any]:
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    classes = list(config["classes"])
    batch_size = int(config["batch_size"])
    summary: dict[str, Any] = {"branches": {}, "gate": {}}
    for branch, seeds in metrics.get("branches", {}).items():
        summary["branches"][branch] = {}
        for seed in seeds:
            seed_dir = run_dir / "models" / branch / f"seed_{seed}"
            latest = _load_weights_model(branch, (96, 258), int(config["class_count"]), float(config["learning_rate"]), seed_dir / "latest.weights.h5")
            summary["branches"][branch][seed] = {"latest": _source_eval(branch, latest, run_dir, batch_size, classes)}
    latest_tests = []
    min_core = []
    min_candidate = []
    for payload in metrics.get("branches", {}).get("conv1d_baseline", {}).values():
        test = payload["latest"]["test"]
        latest_tests.append(float(test["accuracy"]))
        by_gloss = {row["gloss"]: float(row["accuracy"]) for row in test.get("per_class", [])}
        min_core.append(min(by_gloss.get(gloss, 0.0) for gloss in CORE_CLASSES))
        min_candidate.append(min(by_gloss.get(gloss, 0.0) for gloss in CANDIDATE_CLASSES))
    gate = config["gate"]
    gate_passed = bool(latest_tests and float(np.mean(latest_tests)) >= gate["mean_latest_test_min"] and min(min_core) >= gate["core_class_test_min"] and min(min_candidate) >= gate["candidate_class_test_min"])
    summary["gate"] = {"mean_latest_test": float(np.mean(latest_tests)) if latest_tests else 0.0, "min_core_latest_test": float(min(min_core)) if min_core else 0.0, "min_candidate_latest_test": float(min(min_candidate)) if min_candidate else 0.0, "passed": gate_passed, "decision": "eligible_for_larger_batch_screen" if gate_passed else "no_export_no_android_integration"}
    return summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    result = _base_run(args)
    config = json.loads((args.run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    result["classes"] = list(config["classes"])
    result["source_aware_summary"] = _source_aware_summary(args.run_dir, result)
    _write_json(args.run_dir / "metrics" / "metrics.json", result)
    (args.run_dir / "metrics" / "metrics.md").write_text(_metrics_markdown(result), encoding="utf-8")
    return result


def _metrics_markdown(metrics: dict[str, Any]) -> str:
    gate = metrics.get("source_aware_summary", {}).get("gate", {})
    lines = ["# E4-O GET/WELCOME2 7-Sign Screen Metrics", "", "Experiment-only result. This is not a production Android model.", "", f"- Classes: {', '.join(metrics.get('classes', []))}", f"- Mean latest test: `{gate.get('mean_latest_test', 0.0):.4f}`", f"- Min core latest test: `{gate.get('min_core_latest_test', 0.0):.4f}`", f"- Min candidate latest test: `{gate.get('min_candidate_latest_test', 0.0):.4f}`", f"- Gate passed: `{gate.get('passed')}`", f"- Decision: `{gate.get('decision')}`", "", "| Branch | Seed | Latest Test | Best Test |", "|---|---:|---:|---:|"]
    for branch, seeds in metrics.get("branches", {}).items():
        for seed, payload in seeds.items():
            lines.append(f"| {branch} | {seed} | {payload['latest']['test']['accuracy']:.4f} | {payload['best']['test']['accuracy']:.4f} |")
    return "\n".join(lines) + "\n"


def check(args: argparse.Namespace) -> dict[str, Any]:
    result = _base_check(args)
    run_dir = args.run_dir
    config_path = run_dir / "pilot_config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if config.get("experiment") != "e4_o_get_welcome2_7sign_screen_v1":
            result["errors"].append("unexpected experiment id")
            result["passed"] = False
    dataset_path = run_dir / "dataset" / "landmark_features.npz"
    if dataset_path.exists():
        data = np.load(dataset_path, allow_pickle=False)
        if "source_ids" not in data.files:
            result["errors"].append("dataset missing source_ids")
            result["passed"] = False
    for required in ("logs/prepare_summary.json", "candidate_manifest.csv", "dataset/base_plus_asl_features.npz"):
        if not (run_dir / required).exists():
            result["errors"].append(f"missing output: {required}")
            result["passed"] = False
    _write_json(run_dir / "check_report.json", result)
    return result


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join(["# E4-O GET/WELCOME2 7-Sign Expansion Screen", "", "This experiment reuses E4-N and adds GET/WELCOME2. It is not production training.", "", f"- Classes: {', '.join(config['classes'])}", f"- Base + ASL rows before local extraction: {config['base_plus_asl_rows']}", f"- Local candidate rows to extract: {config['candidate_rows_pending_extraction']}", "", "## 1. Extract Local Candidates", "", "```powershell", 'cd "F:\\ASL DATASET\\5. Apphear3"', f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_o_get_welcome2_expansion extract-candidates --run-dir "{run_dir}" --require-full', "```", "", "## 2. Smoke", "", "```powershell", f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_o_get_welcome2_expansion smoke --run-dir "{run_dir}"', "```", "", "## 3. Full Training", "", "```powershell", f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_o_get_welcome2_expansion run --run-dir "{run_dir}"', "```", "", "Resume:", "", "```powershell", f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_o_get_welcome2_expansion run --run-dir "{run_dir}" --resume', "```", "", "## 4. Check", "", "```powershell", f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_o_get_welcome2_expansion check --run-dir "{run_dir}" --require-full-dataset --require-metrics', "```", ""]) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-O GET/WELCOME2 dual-source expansion screen")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--base-run", type=Path, default=DEFAULT_BASE_RUN)
    prepare_parser.add_argument("--validation-run", type=Path, default=DEFAULT_VALIDATION_RUN)
    prepare_parser.add_argument("--asl-feature-dir", type=Path, default=DEFAULT_ASL_FEATURE_DIR)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--classes", nargs="+", default=DEFAULT_CLASSES)
    prepare_parser.add_argument("--branches", nargs="+", default=DEFAULT_BRANCHES)
    prepare_parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    prepare_parser.add_argument("--batch-size", type=int, default=8)
    prepare_parser.add_argument("--epochs", type=int, default=20)
    prepare_parser.add_argument("--learning-rate", type=float, default=5e-4)
    prepare_parser.add_argument("--overwrite", action="store_true")
    extract_parser = sub.add_parser("extract-candidates")
    extract_parser.add_argument("--run-dir", type=Path, required=True)
    extract_parser.add_argument("--extract-config", type=Path, default=None)
    extract_parser.add_argument("--normalize-config", type=Path, default=None)
    extract_parser.add_argument("--limit", type=int, default=None)
    extract_parser.add_argument("--overwrite-clips", action="store_true")
    extract_parser.add_argument("--require-full", action="store_true")
    smoke_parser = sub.add_parser("smoke")
    smoke_parser.add_argument("--run-dir", type=Path, required=True)
    smoke_parser.add_argument("--rows", type=int, default=10)
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
        elif args.command == "extract-candidates":
            result = extract_candidates(args)
        elif args.command == "smoke":
            result = smoke(args)
        elif args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileExistsError, FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-o] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

