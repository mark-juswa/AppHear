"""E4-L one-sign expansion diagnostic.

Adds one evidence-selected local candidate sign to the E4-J reliable 3-sign core.
Experiment-only: no Android assets, production recognizer files, source videos, or source datasets are modified.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.extract.config import load_config as load_extract_config
from pipeline.extract.landmarks import LandmarkExtractor
from pipeline.features.contract import SCHEMA_VERSION, clip_features_realtimed
from pipeline.normalize.config import load_config as load_normalize_config
from pipeline.rgb.e3_b4_landmark_temporal import _build_model, _inputs_for
from pipeline.rgb.e4_b_strict_runner import run as _base_run

DEFAULT_CORE_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_j_reliable_core_3sign_pilot_01")
DEFAULT_VALIDATION_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_validation_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_l_make_expansion_pilot_01")
DEFAULT_EXTRACT_CONFIG = Path("pipeline/config/extract.yaml")
DEFAULT_NORMALIZE_CONFIG = Path("pipeline/config/normalize.yaml")
CORE_CLASSES = ["GOOD", "HELLO", "SORRY"]
DEFAULT_CANDIDATE = "MAKE"
DEFAULT_CLASSES = ["GOOD", "HELLO", "SORRY", "MAKE"]
SPLITS = {"train": 0, "val": 1, "test": 2}
DEFAULT_SEEDS = [101, 202, 303]
DEFAULT_BRANCHES = ["conv1d_baseline"]


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


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    if not path.exists():
        raise FileNotFoundError(f"missing dataset: {path}")
    data = np.load(path, allow_pickle=False)
    required = {"landmarks", "frame_mask", "y", "split_index", "lengths", "participant_ids", "sample_ids"}
    missing = required.difference(data.files)
    if missing:
        raise ValueError(f"dataset missing keys: {sorted(missing)}")
    return {
        "landmarks": data["landmarks"].astype(np.float32),
        "frame_mask": data["frame_mask"].astype(bool),
        "y": data["y"].astype(np.int64),
        "split_index": data["split_index"].astype(np.int64),
        "lengths": data["lengths"].astype(np.int32),
        "participant_ids": np.asarray(data["participant_ids"]).astype(str),
        "sample_ids": np.asarray(data["sample_ids"]).astype(str),
    }


def _split_counts(split_index: np.ndarray) -> dict[str, int]:
    return {name: int(np.sum(split_index == sid)) for name, sid in SPLITS.items()}


def _class_counts(y: np.ndarray, split_index: np.ndarray, classes: list[str]) -> dict[str, dict[str, int]]:
    return {
        split: {classes[class_id]: int(np.sum(y[split_index == sid] == class_id)) for class_id in range(len(classes))}
        for split, sid in SPLITS.items()
    }


def _candidate_inventory(validation_run: Path, candidate: str) -> list[dict[str, str]]:
    rows = _read_csv(validation_run / "validated_clip_inventory.csv")
    selected = [row for row in rows if row["canonical_gloss"] == candidate and row["eligible"] == "True"]
    if not selected:
        raise ValueError(f"no eligible rows for candidate {candidate}")
    return sorted(selected, key=lambda row: (row["signer_id"], int(row.get("repetition_index") or 0), row["video_path"]))


def _split_candidate(rows: list[dict[str, str]], candidate: str) -> list[dict[str, Any]]:
    by_signer: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_signer.setdefault(row["signer_id"], []).append(row)
    expected = {"3B96F6-S001", "6F7328-S001"}
    if set(by_signer) != expected:
        raise ValueError(f"{candidate} expected signers {sorted(expected)}, got {sorted(by_signer)}")
    out: list[dict[str, Any]] = []
    for signer, split_rows in by_signer.items():
        split_rows = sorted(split_rows, key=lambda row: (int(row.get("repetition_index") or 0), row["video_path"]))
        for index, row in enumerate(split_rows):
            if signer == "6F7328-S001":
                split = "test"
            else:
                split = "val" if index >= 30 else "train"
            stem = Path(row["video_path"]).stem
            out.append(
                {
                    "sample_id": f"{candidate}_{stem}",
                    "source": "e4_c_local_supplementary_validation_01",
                    "split": split,
                    "signer_id": signer,
                    "canonical_gloss": candidate,
                    "class_id": 3,
                    "video_path": row["video_path"],
                    "sidecar_dialect": row.get("sidecar_dialect", ""),
                    "hand_hit_rate": row.get("hand_hit_rate", ""),
                    "warnings": row.get("warnings", ""),
                    "feature_source": "pending_extraction",
                }
            )
    return sorted(out, key=lambda row: (SPLITS[row["split"]], row["signer_id"], row["sample_id"]))


def _core_manifest_rows(core_run: Path) -> list[dict[str, Any]]:
    rows = _read_csv(core_run / "pilot_manifest.csv")
    out = []
    for row in rows:
        if row["canonical_gloss"] not in CORE_CLASSES:
            continue
        out.append(
            {
                "sample_id": row["sample_id"],
                "source": "e4_j_reliable_core_3sign_pilot_01",
                "split": row["split"],
                "signer_id": row["signer_id"],
                "canonical_gloss": row["canonical_gloss"],
                "class_id": CORE_CLASSES.index(row["canonical_gloss"]),
                "video_path": row.get("video_path", ""),
                "sidecar_dialect": row.get("sidecar_dialect", ""),
                "hand_hit_rate": row.get("hand_hit_rate", ""),
                "warnings": row.get("warnings", ""),
                "feature_source": "copied_from_e4_j",
            }
        )
    return out


def _copy_core_dataset(core_run: Path, output: Path) -> dict[str, np.ndarray]:
    core_data = _load_npz(core_run / "dataset" / "landmark_features.npz")
    np.savez_compressed(output / "dataset" / "core_landmark_features.npz", **core_data)
    return core_data


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("dataset/per_clip_candidate", "logs", "metrics", "models", "smoke"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    classes = list(DEFAULT_CLASSES)
    core_rows = _core_manifest_rows(args.core_run)
    candidate_rows = _split_candidate(_candidate_inventory(args.validation_run, args.candidate), args.candidate)
    all_rows = core_rows + candidate_rows
    fields = [
        "sample_id", "source", "split", "signer_id", "canonical_gloss", "class_id", "video_path",
        "sidecar_dialect", "hand_hit_rate", "warnings", "feature_source",
    ]
    _write_csv(output / "pilot_manifest.csv", all_rows, fields)
    _write_csv(output / "candidate_manifest.csv", candidate_rows, fields)
    _write_csv(output / "selected_classes.csv", [{"class_id": i, "gloss": gloss} for i, gloss in enumerate(classes)], ["class_id", "gloss"])
    core_data = _copy_core_dataset(args.core_run, output)
    split_index_preview = np.concatenate([core_data["split_index"], np.asarray([SPLITS[row["split"]] for row in candidate_rows], dtype=np.int64)])
    y_preview = np.concatenate([core_data["y"], np.asarray([3 for _ in candidate_rows], dtype=np.int64)])
    warning_count = sum(1 for row in candidate_rows if row.get("warnings"))
    config = {
        "experiment": "e4_l_one_sign_expansion_v1",
        "purpose": "one-sign expansion diagnostic after E4-K fixed/latest Conv1D policy",
        "run_dir": str(output.resolve()),
        "core_run": str(args.core_run.resolve()),
        "validation_run": str(args.validation_run.resolve()),
        "input_shape": [96, 258],
        "schema_version": SCHEMA_VERSION,
        "classes": classes,
        "class_count": len(classes),
        "candidate_gloss": args.candidate,
        "candidate_reason": "MAKE selected over GET/WELCOME2/HAVE/KNOW/GO: 70 readable clips, two aligned signers, only 3 warning rows, mean hand-hit 0.7258.",
        "active_rows_expected_after_extraction": len(all_rows),
        "core_rows": len(core_rows),
        "candidate_rows": len(candidate_rows),
        "candidate_warning_rows": warning_count,
        "split_counts_expected": _split_counts(split_index_preview),
        "class_counts_expected": _class_counts(y_preview, split_index_preview, classes),
        "batch_size": int(args.batch_size),
        "epochs": int(args.epochs),
        "learning_rate": float(args.learning_rate),
        "branches": list(args.branches),
        "seeds": list(args.seeds),
        "checkpoint_policy": "latest_fixed_epoch_only",
        "long_steps": ["extract-candidate", "run"],
        "gate": {
            "go_if": [
                "Conv1D latest/fixed-epoch mean test accuracy >= 0.90",
                "every class test accuracy >= 0.90",
                "candidate class test accuracy >= 0.90",
                "no predicted-class collapse across seeds",
            ],
            "no_go_if": [
                "candidate class falls below 0.90",
                "adding candidate harms any core class below 0.90",
                "validation remains saturated while held-out test collapses",
            ],
        },
        "warnings": [
            "Candidate has only two signers, so validation is carved from the train-side signer.",
            "This is an expansion diagnostic, not a production-grade signer-independent claim.",
            "No Android integration, model export, or production recognizer replacement is authorized.",
        ],
    }
    _write_json(output / "pilot_config.json", config)
    _write_json(output / "logs" / "prepare_summary.json", config)
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def _per_clip_path(run_dir: Path, sample_id: str) -> Path:
    return run_dir / "dataset" / "per_clip_candidate" / f"{sample_id}.npz"


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
        "hand_hit_rate_extracted": any_hand,
        "pose_hit_rate_extracted": pose_hit,
    }


def extract_candidate(args: argparse.Namespace) -> dict[str, Any]:
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
                print(f"[e4-l/extract] {index}/{len(rows)} {row['sample_id']} {row['canonical_gloss']}")
            except Exception as err:  # noqa: BLE001
                errors.append(f"{row['sample_id']}: {err}")
                manifest_rows.append({**row, "status": "failed", "reason": str(err)[:240]})
                print(f"[e4-l/extract] FAILED {row['sample_id']}: {err}", file=sys.stderr)
    if manifest_rows:
        _write_csv(run_dir / "logs" / "candidate_feature_extraction_manifest.csv", manifest_rows, sorted({k for r in manifest_rows for k in r}))
    dataset_result = _assemble_dataset(run_dir, require_full=args.require_full and args.limit is None)
    result = {
        "experiment": config["experiment"],
        "run_dir": str(run_dir.resolve()),
        "attempted_candidate_rows": len(rows),
        "ok_or_cached_candidate_rows": sum(row.get("status") in {"ok", "cached"} for row in manifest_rows),
        "failed_candidate_rows": sum(row.get("status") == "failed" for row in manifest_rows),
        "elapsed_seconds": time.perf_counter() - start,
        "dataset": dataset_result,
        "errors": errors,
        "passed": not errors and dataset_result.get("assembled", False),
    }
    _write_json(run_dir / "logs" / "candidate_feature_extraction_summary.json", result)
    return result


def _assemble_dataset(run_dir: Path, require_full: bool) -> dict[str, Any]:
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    core = _load_npz(run_dir / "dataset" / "core_landmark_features.npz")
    candidate_rows = _read_csv(run_dir / "candidate_manifest.csv")
    features = [core["landmarks"]]
    masks = [core["frame_mask"]]
    labels = [core["y"]]
    splits = [core["split_index"]]
    lengths = [core["lengths"]]
    participant_ids = [core["participant_ids"]]
    sample_ids = [core["sample_ids"]]
    missing = []
    for row in candidate_rows:
        path = _per_clip_path(run_dir, row["sample_id"])
        if not path.exists():
            missing.append(row["sample_id"])
            continue
        data = np.load(path, allow_pickle=False)
        features.append(data["feature"].astype(np.float32)[None, :, :])
        masks.append(data["frame_mask"].astype(bool)[None, :])
        labels.append(np.asarray([int(data["y"])], dtype=np.int64))
        splits.append(np.asarray([int(data["split_index"])], dtype=np.int64))
        lengths.append(np.asarray([int(data["length"])], dtype=np.int32))
        participant_ids.append(np.asarray([str(np.asarray(data["participant_id"]).item())]))
        sample_ids.append(np.asarray([str(np.asarray(data["sample_id"]).item())]))
    if missing and require_full:
        raise ValueError(f"missing candidate features for {len(missing)} rows; first={missing[:5]}")
    x = np.concatenate(features, axis=0).astype(np.float32)
    fm = np.concatenate(masks, axis=0).astype(bool)
    y = np.concatenate(labels, axis=0).astype(np.int64)
    split_index = np.concatenate(splits, axis=0).astype(np.int64)
    lens = np.concatenate(lengths, axis=0).astype(np.int32)
    pids = np.concatenate(participant_ids, axis=0).astype(str)
    sids = np.concatenate(sample_ids, axis=0).astype(str)
    np.savez_compressed(
        run_dir / "dataset" / "landmark_features.npz",
        landmarks=x,
        frame_mask=fm,
        y=y,
        split_index=split_index,
        lengths=lens,
        participant_ids=pids,
        sample_ids=sids,
    )
    return {
        "assembled": not missing or not require_full,
        "rows": int(x.shape[0]),
        "shape": [int(v) for v in x.shape],
        "missing_candidate_rows": len(missing),
        "split_counts": _split_counts(split_index),
        "class_counts": _class_counts(y, split_index, config["classes"]),
    }


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    data = _load_npz(run_dir / "dataset" / "landmark_features.npz")
    rows = min(int(args.rows), int(data["landmarks"].shape[0]))
    x = data["landmarks"][:rows]
    fm = data["frame_mask"][:rows]
    y = data["y"][:rows]
    result: dict[str, Any] = {"rows": rows, "shape": [int(v) for v in x.shape], "branches": {}}
    for branch in config["branches"]:
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(12345)
        model = _build_model(branch, (96, 258), int(config["class_count"]), float(config["learning_rate"]))
        probs = model.predict(_inputs_for(branch, x, fm), batch_size=2, verbose=0)
        loss = model.train_on_batch(_inputs_for(branch, x, fm), y)
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
    config = json.loads((args.run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    result = _base_run(args)
    result["classes"] = list(config["classes"])
    result["checkpoint_policy"] = config["checkpoint_policy"]
    result["latest_policy_summary"] = _latest_policy_summary(result)
    _write_json(args.run_dir / "metrics" / "metrics.json", result)
    (args.run_dir / "metrics" / "metrics.md").write_text(_metrics_markdown(result), encoding="utf-8")
    return result


def _latest_policy_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    branch = "conv1d_baseline"
    seeds = metrics.get("branches", {}).get(branch, {})
    rows = []
    for seed, payload in seeds.items():
        test = payload["latest"]["test"]
        per_class = test.get("per_class", [])
        rows.append(
            {
                "seed": str(seed),
                "test_accuracy": float(test["accuracy"]),
                "min_class_test_accuracy": float(min(row["accuracy"] for row in per_class)) if per_class else 0.0,
                "candidate_test_accuracy": float(next((row["accuracy"] for row in per_class if row["gloss"] == DEFAULT_CANDIDATE), 0.0)),
                "predicted_class_counts": test.get("predicted_class_counts", {}),
                "per_class": per_class,
            }
        )
    tests = [row["test_accuracy"] for row in rows]
    mins = [row["min_class_test_accuracy"] for row in rows]
    candidate = [row["candidate_test_accuracy"] for row in rows]
    gate_passed = bool(tests and min(tests) >= 0.90 and min(mins) >= 0.90 and min(candidate) >= 0.90)
    return {
        "branch": branch,
        "checkpoint": "latest",
        "seed_rows": rows,
        "mean_test": float(np.mean(tests)) if tests else 0.0,
        "std_test": float(np.std(tests)) if tests else 0.0,
        "min_seed_test": float(min(tests)) if tests else 0.0,
        "min_class_test": float(min(mins)) if mins else 0.0,
        "min_candidate_test": float(min(candidate)) if candidate else 0.0,
        "gate_passed": gate_passed,
        "decision": "eligible_for_next_one_sign_expansion" if gate_passed else "no_go_do_not_expand",
    }


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["pilot_config.json", "pilot_manifest.csv", "candidate_manifest.csv", "selected_classes.csv", "README_RUN.md"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    config = {}
    if (run_dir / "pilot_config.json").exists():
        config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
        if config.get("classes") != DEFAULT_CLASSES:
            errors.append("unexpected class list")
        if config.get("branches") != DEFAULT_BRANCHES:
            errors.append("unexpected branch list")
    dataset_path = run_dir / "dataset" / "landmark_features.npz"
    if args.require_dataset and not dataset_path.exists():
        errors.append("missing output: dataset/landmark_features.npz")
    if dataset_path.exists() and args.require_full_dataset and config:
        data = np.load(dataset_path, allow_pickle=False)
        expected = int(config.get("active_rows_expected_after_extraction", -1))
        if int(data["landmarks"].shape[0]) != expected:
            errors.append(f"dataset row count mismatch: {data['landmarks'].shape[0]} != {expected}")
    if args.require_metrics and not (run_dir / "metrics" / "metrics.json").exists():
        errors.append("missing output: metrics/metrics.json")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def _metrics_markdown(metrics: dict[str, Any]) -> str:
    summary = metrics.get("latest_policy_summary", {})
    lines = [
        "# E4-L One-Sign Expansion Metrics",
        "",
        "Experiment-only result. This is not a production Android model.",
        "",
        f"- Classes: {', '.join(metrics.get('classes', []))}",
        f"- Policy: `{metrics.get('checkpoint_policy')}`",
        f"- Mean test: `{summary.get('mean_test', 0.0):.4f}`",
        f"- Min seed test: `{summary.get('min_seed_test', 0.0):.4f}`",
        f"- Min class test: `{summary.get('min_class_test', 0.0):.4f}`",
        f"- Min candidate test: `{summary.get('min_candidate_test', 0.0):.4f}`",
        f"- Gate passed: `{summary.get('gate_passed')}`",
        f"- Decision: `{summary.get('decision')}`",
        "",
        "| Seed | Test | Min Class | Candidate MAKE |",
        "|---:|---:|---:|---:|",
    ]
    for row in summary.get("seed_rows", []):
        lines.append(f"| {row['seed']} | {row['test_accuracy']:.4f} | {row['min_class_test_accuracy']:.4f} | {row['candidate_test_accuracy']:.4f} |")
    return "\n".join(lines) + "\n"


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join(
        [
            "# E4-L One-Sign Expansion Diagnostic",
            "",
            "Adds MAKE to the E4-J GOOD/HELLO/SORRY core using E4-K's fixed/latest Conv1D policy.",
            "No Android assets or production recognizer files are changed.",
            "",
            "## Candidate",
            "",
            f"- Candidate: `{config['candidate_gloss']}`",
            f"- Reason: {config['candidate_reason']}",
            f"- Expected rows after extraction: {config['active_rows_expected_after_extraction']}",
            f"- Expected split counts: {config['split_counts_expected']}",
            "",
            "## 1. Extract Candidate Features",
            "",
            "This is a longer step. The user should run it manually.",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_l_one_sign_expansion extract-candidate --run-dir "{run_dir}" --require-full',
            "```",
            "",
            "## 2. Smoke Test",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_l_one_sign_expansion smoke --run-dir "{run_dir}"',
            "```",
            "",
            "## 3. Full Training",
            "",
            "This is the other longer step. The user should run it manually.",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_l_one_sign_expansion run --run-dir "{run_dir}"',
            "```",
            "",
            "Resume if interrupted:",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_l_one_sign_expansion run --run-dir "{run_dir}" --resume',
            "```",
            "",
            "## 4. Check",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_l_one_sign_expansion check --run-dir "{run_dir}" --require-full-dataset --require-metrics',
            "```",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-L one-sign expansion diagnostic")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--core-run", type=Path, default=DEFAULT_CORE_RUN)
    prepare_parser.add_argument("--validation-run", type=Path, default=DEFAULT_VALIDATION_RUN)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    prepare_parser.add_argument("--branches", nargs="+", default=DEFAULT_BRANCHES)
    prepare_parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    prepare_parser.add_argument("--batch-size", type=int, default=8)
    prepare_parser.add_argument("--epochs", type=int, default=20)
    prepare_parser.add_argument("--learning-rate", type=float, default=5e-4)
    prepare_parser.add_argument("--overwrite", action="store_true")

    extract_parser = sub.add_parser("extract-candidate")
    extract_parser.add_argument("--run-dir", type=Path, required=True)
    extract_parser.add_argument("--extract-config", type=Path, default=None)
    extract_parser.add_argument("--normalize-config", type=Path, default=None)
    extract_parser.add_argument("--limit", type=int, default=None)
    extract_parser.add_argument("--overwrite-clips", action="store_true")
    extract_parser.add_argument("--require-full", action="store_true")

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
        elif args.command == "extract-candidate":
            result = extract_candidate(args)
        elif args.command == "smoke":
            result = smoke(args)
        elif args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileExistsError, FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-l] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())