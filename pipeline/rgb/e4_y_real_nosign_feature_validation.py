"""E4-Y real N0/P1 MediaPipe feature validation for routed recognizer.

Extracts schema v3.0 [96,258] windows from reviewed E2e-C0 N0/P1 source videos
using the same MediaPipe LandmarkExtractor and clip_features_realtimed math as
the training pipeline, then evaluates the E4-S primary + E4-V GOOD/SORRY
specialist routed policy from E4-X.

Experiment-only: no Android assets, TFLite exports, production recognizer files,
or source datasets are modified.
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

from pipeline.extract.config import load_config as load_extract_config
from pipeline.extract.landmarks import LandmarkExtractor
from pipeline.features.contract import SCHEMA_VERSION, clip_features_realtimed
from pipeline.normalize.config import load_config as load_normalize_config
from pipeline.rgb.e4_x_routed_system_validation import (
    FINAL_CLASSES,
    NO_SIGN_ID,
    POSITIVE_CLASSES,
    SPECIALIST_CLASSES,
    _apply_policy,
    _evaluate_policy,
    _load_json,
    _load_npz,
    _seed_predictions,
)

DEFAULT_PRIMARY_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01")
DEFAULT_SPECIALIST_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01")
DEFAULT_E4X_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_x_routed_system_validation_01")
DEFAULT_N0_RUN = Path("artifacts/recognition_upgrade/e2e_c0/n0_capture_06")
DEFAULT_P1_RUN = Path("artifacts/recognition_upgrade/e2e_c0/p1_capture_03")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_y_real_nosign_feature_validation_01")
DEFAULT_EXTRACT_CONFIG = Path("pipeline/config/extract.yaml")
DEFAULT_NORMALIZE_CONFIG = Path("pipeline/config/normalize.yaml")
SPLITS = {"val": 1, "test": 2}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _clip_video_map(run_dir: Path) -> dict[str, Path]:
    rows = _read_csv(run_dir / "capture_manifest.csv")
    return {row["clip_id"]: Path(row["video_path"]) for row in rows}


def _selected_rows(run_dir: Path, kind: str, max_rows: int, val_rows: int) -> list[dict[str, Any]]:
    rows = _read_csv(run_dir / "reviewed_manifest.csv")
    selected: list[dict[str, Any]] = []
    for row in rows:
        if row.get("eligible", "").lower() != "true":
            continue
        if row.get("kind") != kind:
            continue
        visible = int(row.get("visible_hand_count", "0") or 0)
        if kind == "n0" and visible != 0:
            continue
        if kind == "p1" and visible <= 0:
            continue
        selected.append(dict(row))
        if len(selected) >= max_rows:
            break
    if len(selected) < max(2, min(max_rows, 2)):
        raise ValueError(f"not enough eligible {kind.upper()} rows in {run_dir}")
    for idx, row in enumerate(selected):
        row["split"] = "val" if idx < val_rows else "test"
        row["source_kind"] = kind.upper()
    return selected


def _window_bounds(center: int, frame_count: int, window: int) -> tuple[int, int]:
    if frame_count <= 0:
        raise ValueError("frame_count must be positive")
    if frame_count <= window:
        return 0, frame_count - 1
    start = max(0, min(center - window // 2, frame_count - window))
    return start, start + window - 1


def _extract_rows(
    rows: list[dict[str, Any]],
    video_by_clip: dict[str, Path],
    extractor: LandmarkExtractor,
    normalize_config: Any,
    window: int,
    cache_dir: Path,
) -> tuple[list[np.ndarray], list[np.ndarray], list[int], list[dict[str, Any]]]:
    features: list[np.ndarray] = []
    frame_masks: list[np.ndarray] = []
    lengths: list[int] = []
    out_rows: list[dict[str, Any]] = []
    by_clip: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_clip.setdefault(str(row["clip_id"]), []).append(row)
    for clip_index, (clip_id, clip_rows) in enumerate(sorted(by_clip.items()), start=1):
        video = video_by_clip.get(clip_id)
        if video is None:
            raise FileNotFoundError(f"missing video path for clip_id {clip_id}")
        cache_path = cache_dir / f"{clip_id}.npz"
        if cache_path.exists():
            cached = np.load(cache_path, allow_pickle=False)
            hands = cached["hands_image"].astype(np.float32)
            pose = cached["pose_image"].astype(np.float32)
            hand_score = cached["hand_score"].astype(np.float32)
            pose_score = cached["pose_score"].astype(np.float32)
            meta = {
                "native_fps": float(cached["native_fps"]),
                "n_frames": int(cached["n_frames"]),
                "frame_width": int(cached["frame_width"]),
                "frame_height": int(cached["frame_height"]),
            }
        else:
            print(f"[e4-y] extract clip {clip_index}/{len(by_clip)} {clip_id}")
            clip, meta = extractor.extract(video)
            hands = clip.hands_image
            pose = clip.pose_image
            hand_score = clip.hand_score
            pose_score = clip.pose_score
            np.savez_compressed(
                cache_path,
                hands_image=hands,
                pose_image=pose,
                hand_score=hand_score,
                pose_score=pose_score,
                native_fps=float(meta["native_fps"]),
                n_frames=int(meta["n_frames"]),
                frame_width=int(meta["frame_width"]),
                frame_height=int(meta["frame_height"]),
            )
        for row in clip_rows:
            center = int(row["frame_index"])
            onset, release = _window_bounds(center, int(meta["n_frames"]), window)
            feature, frame_mask, length, _params = clip_features_realtimed(
                hands, pose, onset, release, normalize_config, window
            )
            hand_window = hand_score[onset : release + 1]
            pose_window = pose_score[onset : release + 1]
            features.append(feature.astype(np.float32))
            frame_masks.append(frame_mask.astype(bool))
            lengths.append(int(length))
            out_rows.append({
                "sample_id": row["sample_id"],
                "source_kind": row["source_kind"],
                "split": row["split"],
                "clip_id": clip_id,
                "participant_id": row.get("participant_id", ""),
                "device_id": row.get("device_id", ""),
                "environment_id": row.get("environment_id", ""),
                "camera_facing": row.get("camera_facing", ""),
                "timestamp_ms": row.get("timestamp_ms", ""),
                "frame_index": center,
                "window_onset": onset,
                "window_release": release,
                "length": int(length),
                "native_fps": float(meta["native_fps"]),
                "native_frames": int(meta["n_frames"]),
                "hand_hit_rate_window": float(np.mean(np.any(hand_window > 0.0, axis=1))) if hand_window.size else 0.0,
                "pose_hit_rate_window": float(np.mean(pose_window > 0.0)) if pose_window.size else 0.0,
                "video_path": str(video),
            })
    return features, frame_masks, lengths, out_rows


def _build_dataset(args: argparse.Namespace, output: Path) -> dict[str, Any]:
    n0_rows = _selected_rows(args.n0_run, "n0", int(args.max_n0), int(args.val_n0))
    p1_rows = _selected_rows(args.p1_run, "p1", int(args.max_p1), int(args.val_p1))
    all_rows = n0_rows + p1_rows
    cache_dir = output / "dataset" / "stage_e_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    extract_config = load_extract_config(args.extract_config)
    normalize_config = load_normalize_config(args.normalize_config)
    video_map = {**_clip_video_map(args.n0_run), **_clip_video_map(args.p1_run)}
    with LandmarkExtractor(extract_config) as extractor:
        features, frame_masks, lengths, manifest = _extract_rows(
            all_rows,
            video_map,
            extractor,
            normalize_config,
            int(args.window),
            cache_dir,
        )
    x = np.stack(features).astype(np.float32)
    frame_mask = np.stack(frame_masks).astype(bool)
    split_index = np.asarray([SPLITS[row["split"]] for row in manifest], dtype=np.int64)
    y = np.full(len(manifest), NO_SIGN_ID, dtype=np.int64)
    sample_ids = np.asarray([row["sample_id"] for row in manifest]).astype(str)
    source = np.asarray([row["source_kind"] for row in manifest]).astype(str)
    lengths_array = np.asarray(lengths, dtype=np.int32)
    np.savez_compressed(
        output / "dataset" / "real_nosign_features.npz",
        landmarks=x,
        frame_mask=frame_mask,
        y=y,
        split_index=split_index,
        lengths=lengths_array,
        sample_ids=sample_ids,
        source=source,
    )
    _write_csv(
        output / "dataset" / "real_nosign_manifest.csv",
        manifest,
        [
            "sample_id", "source_kind", "split", "clip_id", "participant_id", "device_id",
            "environment_id", "camera_facing", "timestamp_ms", "frame_index", "window_onset",
            "window_release", "length", "native_fps", "native_frames", "hand_hit_rate_window",
            "pose_hit_rate_window", "video_path",
        ],
    )
    return {
        "rows": int(x.shape[0]),
        "shape": [int(v) for v in x.shape],
        "split_counts": dict(sorted(Counter(row["split"] for row in manifest).items())),
        "source_counts": dict(sorted(Counter(row["source_kind"] for row in manifest).items())),
        "mean_hand_hit_rate_by_source": {
            kind: float(np.mean([float(row["hand_hit_rate_window"]) for row in manifest if row["source_kind"] == kind]))
            for kind in sorted({row["source_kind"] for row in manifest})
        },
        "mean_pose_hit_rate_by_source": {
            kind: float(np.mean([float(row["pose_hit_rate_window"]) for row in manifest if row["source_kind"] == kind]))
            for kind in sorted({row["source_kind"] for row in manifest})
        },
        "schema_version": SCHEMA_VERSION,
        "extract_config": str(args.extract_config),
        "normalize_config": str(args.normalize_config),
    }


def _combined_eval_dataset(primary_run: Path, nosign_run: Path) -> dict[str, np.ndarray]:
    active = _load_npz(primary_run / "dataset" / "landmark_features.npz", "E4-S active tensor")
    oov = _load_npz(primary_run / "dataset" / "oov_confusion_holdout.npz", "E4-S OOV holdout tensor")
    nosign_path = nosign_run / "dataset" / "real_nosign_features.npz"
    nosign = _load_npz(nosign_path, "E4-Y real no-sign tensor")
    nosign_raw = np.load(nosign_path, allow_pickle=False)
    nosign_source = np.asarray(nosign_raw["source"]).astype(str)
    x = np.concatenate([active["landmarks"], oov["landmarks"], nosign["landmarks"]], axis=0).astype(np.float32)
    frame_mask = np.concatenate([active["frame_mask"], oov["frame_mask"], nosign["frame_mask"]], axis=0).astype(bool)
    y = np.concatenate([
        active["y"],
        np.full(int(oov["landmarks"].shape[0]), POSITIVE_CLASSES.index("SORRY"), dtype=np.int64),
        np.full(int(nosign["landmarks"].shape[0]), NO_SIGN_ID, dtype=np.int64),
    ])
    split_index = np.concatenate([active["split_index"], oov["split_index"], nosign["split_index"]]).astype(np.int64)
    source = np.concatenate([
        np.full(int(active["landmarks"].shape[0]), "e4_s_active"),
        np.full(int(oov["landmarks"].shape[0]), "e4_s_oov_sorry"),
        nosign_source,
    ]).astype(str)
    sample_ids = np.concatenate([active["sample_ids"], oov["sample_ids"], nosign["sample_ids"]]).astype(str)
    return {"landmarks": x, "frame_mask": frame_mask, "y": y, "split_index": split_index, "source": source, "sample_ids": sample_ids}


def _policy(args: argparse.Namespace) -> dict[str, float]:
    if args.primary_confidence is not None and args.specialist_confidence is not None:
        return {"primary_confidence": float(args.primary_confidence), "specialist_confidence": float(args.specialist_confidence)}
    metrics = _load_json(args.e4x_run / "metrics" / "routed_system_metrics.json", "E4-X metrics")
    return {
        "primary_confidence": float(metrics["selected_policy"]["primary_confidence"]),
        "specialist_confidence": float(metrics["selected_policy"]["specialist_confidence"]),
    }


def _source_false_commit_rates(y_true: np.ndarray, y_pred: np.ndarray, source: np.ndarray) -> dict[str, dict[str, Any]]:
    out = {}
    for kind in sorted(set(source.tolist())):
        mask = source == kind
        no_sign = mask & (y_true == NO_SIGN_ID)
        if not np.any(no_sign):
            continue
        accepted = y_pred[no_sign] != NO_SIGN_ID
        out[kind] = {
            "rows": int(np.sum(no_sign)),
            "false_commits": int(np.sum(accepted)),
            "false_commit_rate": float(np.mean(accepted)),
            "predicted_counts": dict(sorted(Counter(FINAL_CLASSES[int(v)] for v in y_pred[no_sign]).items())),
        }
    return out


def _class_recall(metrics: dict[str, Any], gloss: str) -> float:
    for row in metrics["per_class"]:
        if row["gloss"] == gloss:
            return 0.0 if row["recall"] is None else float(row["recall"])
    return 0.0


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    for relative in ("dataset", "logs", "metrics", "predictions"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    dataset_summary = _build_dataset(args, output)
    primary_config = _load_json(args.primary_run / "pilot_config.json", "E4-S config")
    specialist_config = _load_json(args.specialist_run / "pilot_config.json", "E4-V config")
    dataset = _combined_eval_dataset(args.primary_run, output)
    policy = _policy(args)
    seeds = [int(seed) for seed in args.seeds]
    val = dataset["split_index"] == 1
    test = dataset["split_index"] == 2
    seed_results = {}
    prediction_rows: list[dict[str, Any]] = []
    for seed in seeds:
        preds = _seed_predictions(seed, args.primary_run, args.specialist_run, primary_config, specialist_config, dataset)
        final = _apply_policy(preds, policy)
        val_metrics = _evaluate_policy(dataset["y"][val], final[val])
        test_metrics = _evaluate_policy(dataset["y"][test], final[test])
        test_metrics["no_sign_false_commit_by_source"] = _source_false_commit_rates(dataset["y"][test], final[test], dataset["source"][test])
        seed_results[str(seed)] = {"validation": val_metrics, "test": test_metrics}
        for idx in np.where(test)[0].tolist():
            if dataset["source"][idx] not in {"N0", "P1"}:
                continue
            prediction_rows.append({
                "seed": seed,
                "sample_id": dataset["sample_ids"][idx],
                "source": dataset["source"][idx],
                "true_gloss": FINAL_CLASSES[int(dataset["y"][idx])],
                "primary_pred": POSITIVE_CLASSES[int(preds["primary_pred"][idx])],
                "primary_confidence": float(preds["primary_conf"][idx]),
                "routed": bool(preds["route_mask"][idx]),
                "specialist_pred": "" if preds["specialist_pred"][idx] < 0 else SPECIALIST_CLASSES[int(preds["specialist_pred"][idx])],
                "specialist_confidence": "" if preds["specialist_pred"][idx] < 0 else float(preds["specialist_conf"][idx]),
                "final_pred": FINAL_CLASSES[int(final[idx])],
                "accepted": bool(final[idx] != NO_SIGN_ID),
            })
    _write_csv(output / "predictions" / "nosign_test_predictions.csv", prediction_rows, ["seed", "sample_id", "source", "true_gloss", "primary_pred", "primary_confidence", "routed", "specialist_pred", "specialist_confidence", "final_pred", "accepted"])
    test_evals = [payload["test"] for payload in seed_results.values()]
    summary = {
        "mean_test_accepted_precision": float(np.mean([m["accepted_precision"] for m in test_evals])),
        "min_test_accepted_precision": float(np.min([m["accepted_precision"] for m in test_evals])),
        "mean_test_positive_coverage": float(np.mean([m["positive_coverage"] for m in test_evals])),
        "min_test_positive_coverage": float(np.min([m["positive_coverage"] for m in test_evals])),
        "max_test_no_sign_false_commit_rate": float(np.max([m["no_sign_false_commit_rate"] for m in test_evals])),
        "mean_test_sorry_recall": float(np.mean([_class_recall(m, "SORRY") for m in test_evals])),
        "min_test_sorry_recall": float(np.min([_class_recall(m, "SORRY") for m in test_evals])),
        "mean_test_good_recall": float(np.mean([_class_recall(m, "GOOD") for m in test_evals])),
        "min_test_good_recall": float(np.min([_class_recall(m, "GOOD") for m in test_evals])),
    }
    gate = {
        "accepted_precision_min": float(args.accepted_precision_min),
        "positive_coverage_min": float(args.positive_coverage_min),
        "no_sign_false_commit_rate_max": float(args.no_sign_false_commit_rate_max),
        "sorry_recall_min": float(args.sorry_recall_min),
        "good_recall_min": float(args.good_recall_min),
    }
    passed = bool(
        summary["min_test_accepted_precision"] >= gate["accepted_precision_min"]
        and summary["min_test_positive_coverage"] >= gate["positive_coverage_min"]
        and summary["max_test_no_sign_false_commit_rate"] <= gate["no_sign_false_commit_rate_max"]
        and summary["min_test_sorry_recall"] >= gate["sorry_recall_min"]
        and summary["min_test_good_recall"] >= gate["good_recall_min"]
    )
    result = {
        "experiment": "e4_y_real_nosign_feature_validation_v1",
        "run_dir": str(output.resolve()),
        "primary_run": str(args.primary_run.resolve()),
        "specialist_run": str(args.specialist_run.resolve()),
        "e4x_run": str(args.e4x_run.resolve()),
        "n0_run": str(args.n0_run.resolve()),
        "p1_run": str(args.p1_run.resolve()),
        "classes": FINAL_CLASSES,
        "selected_policy": policy,
        "dataset": dataset_summary,
        "gate": gate,
        "seed_results": seed_results,
        "summary": summary,
        "passed": passed,
        "decision": "real_nosign_probe_passed_expand_n0_p1_or_source_disjoint_next" if passed else "real_nosign_probe_no_go_repair_gate_before_android",
        "warnings": [
            "This is offline window-level validation only.",
            "Default row counts are bounded; increase --max-n0 and --max-p1 for the stronger gate.",
            "Passing this gate does not authorize Android integration, TFLite export, or production replacement.",
        ],
    }
    _write_json(output / "metrics" / "real_nosign_metrics.json", result)
    _write_json(output / "logs" / "run_summary.json", {"passed": passed, "summary": summary, "selected_policy": policy})
    return result


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["dataset/real_nosign_features.npz", "dataset/real_nosign_manifest.csv", "metrics/real_nosign_metrics.json", "logs/run_summary.json"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if args.require_predictions and not (run_dir / "predictions" / "nosign_test_predictions.csv").exists():
        errors.append("missing predictions/nosign_test_predictions.csv")
    if args.require_metrics and (run_dir / "metrics" / "real_nosign_metrics.json").exists():
        metrics = json.loads((run_dir / "metrics" / "real_nosign_metrics.json").read_text(encoding="utf-8"))
        if metrics.get("experiment") != "e4_y_real_nosign_feature_validation_v1":
            errors.append("unexpected experiment id")
        if not isinstance(metrics.get("passed"), bool):
            errors.append("metrics missing boolean passed field")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-Y real N0/P1 MediaPipe feature validation")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--primary-run", type=Path, default=DEFAULT_PRIMARY_RUN)
    run_parser.add_argument("--specialist-run", type=Path, default=DEFAULT_SPECIALIST_RUN)
    run_parser.add_argument("--e4x-run", type=Path, default=DEFAULT_E4X_RUN)
    run_parser.add_argument("--n0-run", type=Path, default=DEFAULT_N0_RUN)
    run_parser.add_argument("--p1-run", type=Path, default=DEFAULT_P1_RUN)
    run_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_parser.add_argument("--extract-config", type=Path, default=DEFAULT_EXTRACT_CONFIG)
    run_parser.add_argument("--normalize-config", type=Path, default=DEFAULT_NORMALIZE_CONFIG)
    run_parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    run_parser.add_argument("--max-n0", type=int, default=24)
    run_parser.add_argument("--max-p1", type=int, default=24)
    run_parser.add_argument("--val-n0", type=int, default=8)
    run_parser.add_argument("--val-p1", type=int, default=8)
    run_parser.add_argument("--window", type=int, default=96)
    run_parser.add_argument("--primary-confidence", type=float, default=None)
    run_parser.add_argument("--specialist-confidence", type=float, default=None)
    run_parser.add_argument("--accepted-precision-min", type=float, default=0.95)
    run_parser.add_argument("--positive-coverage-min", type=float, default=0.80)
    run_parser.add_argument("--no-sign-false-commit-rate-max", type=float, default=0.02)
    run_parser.add_argument("--sorry-recall-min", type=float, default=0.90)
    run_parser.add_argument("--good-recall-min", type=float, default=0.90)

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--require-metrics", action="store_true")
    check_parser.add_argument("--require-predictions", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-y] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

