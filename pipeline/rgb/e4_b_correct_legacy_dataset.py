"""Build a corrected E4-B strict dataset using embedded legacy accepted features.

The first E4-B strict extraction reprocessed legacy accepted videos from timestamp zero. Those
legacy rows already contain curated 30x258 accepted frames, so this package creates a corrected
run directory that uses embedded legacy features and reuses existing Stage-E per-clip features.
No MediaPipe extraction, model training, Android change, or production asset change is performed.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_SOURCE_RUN = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_02_corrected"
)
ACTIVE_SPLITS = {"train", "val", "test"}
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


def _legacy_json_path(video_path: str) -> Path:
    video = Path(video_path)
    return video.parent.parent / "accepted" / f"{video.stem}_ACCEPTED.json"


def _legacy_feature(row: dict[str, str]) -> dict[str, Any]:
    path = _legacy_json_path(row["video_path"])
    if not path.exists():
        raise FileNotFoundError(f"missing legacy accepted JSON: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if int(data.get("feature_size", -1)) != 258:
        raise ValueError(f"{path}: expected feature_size 258, got {data.get('feature_size')}")
    frames = np.asarray(data.get("frames"), dtype=np.float32)
    if frames.ndim != 2 or frames.shape[1] != 258:
        raise ValueError(f"{path}: expected frames [T,258], got {list(frames.shape)}")
    if np.isnan(frames).any() or np.isinf(frames).any():
        raise ValueError(f"{path}: frames contain NaN or Inf")
    length = min(int(frames.shape[0]), 96)
    feature = np.zeros((96, 258), dtype=np.float32)
    feature[:length] = frames[:length]
    frame_mask = np.zeros((96,), dtype=bool)
    frame_mask[:length] = True
    hand_hit = _hand_hit_from_feature(feature[:length])
    pose_hit = _pose_hit_from_feature(feature[:length])
    return {
        "feature": feature,
        "frame_mask": frame_mask,
        "length": length,
        "source_feature_kind": "legacy_embedded_accepted_258",
        "source_feature_path": str(path),
        "hand_hit_rate_corrected": hand_hit,
        "pose_hit_rate_corrected": pose_hit,
        "legacy_quality_score": data.get("quality_score", ""),
    }


def _stage_e_feature(source_run: Path, row: dict[str, str]) -> dict[str, Any]:
    path = source_run / "dataset" / "per_clip" / f"{row['sample_id']}.npz"
    if not path.exists():
        raise FileNotFoundError(f"missing Stage-E per-clip feature: {path}")
    data = np.load(path, allow_pickle=False)
    feature = data["feature"].astype(np.float32)
    frame_mask = data["frame_mask"].astype(bool)
    if feature.shape != (96, 258) or frame_mask.shape != (96,):
        raise ValueError(f"{path}: expected feature [96,258] and mask [96]")
    length = int(data["length"])
    return {
        "feature": feature,
        "frame_mask": frame_mask,
        "length": length,
        "source_feature_kind": "stage_e_mediapipe_extracted_258",
        "source_feature_path": str(path),
        "hand_hit_rate_corrected": _hand_hit_from_feature(feature[frame_mask]),
        "pose_hit_rate_corrected": _pose_hit_from_feature(feature[frame_mask]),
        "legacy_quality_score": "",
    }


def _hand_hit_from_feature(feature: np.ndarray) -> float:
    if feature.shape[0] == 0:
        return 0.0
    hands = feature[:, :126].reshape(feature.shape[0], 2, 63)
    present = np.any(np.abs(hands) > 1e-8, axis=2)
    return float(np.mean(np.any(present, axis=1)))


def _pose_hit_from_feature(feature: np.ndarray) -> float:
    if feature.shape[0] == 0:
        return 0.0
    pose = feature[:, 126:]
    present = np.any(np.abs(pose) > 1e-8, axis=1)
    return float(np.mean(present))


def _copy_package_files(source_run: Path, output: Path) -> None:
    for relative in ("pilot_manifest.csv", "selected_classes.csv", "README_RUN.md"):
        shutil.copy2(source_run / relative, output / relative)
    config = json.loads((source_run / "pilot_config.json").read_text(encoding="utf-8"))
    config["experiment"] = "e4_b_strict_7_landmark_pilot_corrected_legacy_v1"
    config["source_run"] = str(source_run.resolve())
    config["run_dir"] = str(output.resolve())
    config["correction"] = {
        "reason": "legacy_accepted videos were long and first extraction reprocessed from timestamp zero",
        "legacy_rows": "use embedded accepted 30x258 frames",
        "stage_e_rows": "reuse existing per-clip MediaPipe extracted features from source run",
    }
    _write_json(output / "pilot_config.json", config)


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    source_run = args.source_run
    output = args.output
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("dataset/per_clip", "logs", "metrics", "models", "smoke"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    _copy_package_files(source_run, output)

    rows = [row for row in _read_csv(source_run / "pilot_manifest.csv") if row["split"] in ACTIVE_SPLITS]
    features = []
    masks = []
    labels = []
    split_index = []
    lengths = []
    participant_ids = []
    sample_ids = []
    manifest_rows = []
    errors = []

    for row in rows:
        try:
            if row["sidecar_dialect"] == "legacy_accepted":
                item = _legacy_feature(row)
            else:
                item = _stage_e_feature(source_run, row)
            out_path = output / "dataset" / "per_clip" / f"{row['sample_id']}.npz"
            np.savez_compressed(
                out_path,
                feature=item["feature"],
                frame_mask=item["frame_mask"],
                y=np.asarray(int(row["class_id"]), dtype=np.int64),
                split_index=np.asarray(SPLITS[row["split"]], dtype=np.int64),
                length=np.asarray(item["length"], dtype=np.int32),
                participant_id=np.asarray(row["signer_id"]),
                sample_id=np.asarray(row["sample_id"]),
                source_feature_kind=np.asarray(item["source_feature_kind"]),
                source_feature_path=np.asarray(item["source_feature_path"]),
            )
            features.append(item["feature"])
            masks.append(item["frame_mask"])
            labels.append(int(row["class_id"]))
            split_index.append(SPLITS[row["split"]])
            lengths.append(int(item["length"]))
            participant_ids.append(row["signer_id"])
            sample_ids.append(row["sample_id"])
            manifest_rows.append(
                {
                    **row,
                    "status": "ok",
                    "feature_path": str(out_path),
                    "source_feature_kind": item["source_feature_kind"],
                    "source_feature_path": item["source_feature_path"],
                    "hand_hit_rate_corrected": round(float(item["hand_hit_rate_corrected"]), 4),
                    "pose_hit_rate_corrected": round(float(item["pose_hit_rate_corrected"]), 4),
                    "length_corrected": int(item["length"]),
                    "legacy_quality_score": item["legacy_quality_score"],
                }
            )
        except Exception as err:  # noqa: BLE001
            errors.append(f"{row['sample_id']}: {err}")
            manifest_rows.append({**row, "status": "failed", "reason": str(err)[:240]})

    _write_csv(
        output / "logs" / "corrected_feature_manifest.csv",
        manifest_rows,
        sorted({key for item in manifest_rows for key in item.keys()}),
    )
    if errors:
        result = _summary(output, source_run, rows, manifest_rows, None, errors)
        _write_json(output / "logs" / "corrected_dataset_summary.json", result)
        return result

    x = np.stack(features).astype(np.float32)
    fm = np.stack(masks).astype(bool)
    y = np.asarray(labels, dtype=np.int64)
    si = np.asarray(split_index, dtype=np.int64)
    lens = np.asarray(lengths, dtype=np.int32)
    np.savez_compressed(
        output / "dataset" / "landmark_features.npz",
        landmarks=x,
        frame_mask=fm,
        y=y,
        split_index=si,
        lengths=lens,
        participant_ids=np.asarray(participant_ids),
        sample_ids=np.asarray(sample_ids),
    )
    dataset = {
        "rows": int(x.shape[0]),
        "shape": [int(v) for v in x.shape],
        "nan": bool(np.isnan(x).any()),
        "inf": bool(np.isinf(x).any()),
        "mask_matches_lengths": bool(np.array_equal(fm.sum(axis=1).astype(np.int32), lens)),
        "padded_zero": bool(np.all(x[~fm] == 0.0)),
        "split_counts": {name: int(np.sum(si == sid)) for name, sid in SPLITS.items()},
        "length_min": int(lens.min()),
        "length_median": float(np.median(lens)),
        "length_max": int(lens.max()),
    }
    result = _summary(output, source_run, rows, manifest_rows, dataset, errors)
    _write_json(output / "logs" / "corrected_dataset_summary.json", result)
    return result


def _summary(
    output: Path,
    source_run: Path,
    rows: list[dict[str, str]],
    manifest_rows: list[dict[str, Any]],
    dataset: dict[str, Any] | None,
    errors: list[str],
) -> dict[str, Any]:
    status = Counter(row.get("status", "") for row in manifest_rows)
    source_kind = Counter(row.get("source_feature_kind", "") for row in manifest_rows if row.get("status") == "ok")
    by_split: dict[str, list[float]] = defaultdict(list)
    by_gloss: dict[str, list[float]] = defaultdict(list)
    for row in manifest_rows:
        if row.get("status") != "ok":
            continue
        hand = float(row.get("hand_hit_rate_corrected", 0.0))
        by_split[row["split"]].append(hand)
        by_gloss[row["canonical_gloss"]].append(hand)
    return {
        "experiment": "e4_b_strict_7_corrected_legacy_dataset_v1",
        "source_run": str(source_run.resolve()),
        "run_dir": str(output.resolve()),
        "input_rows": len(rows),
        "status_counts": dict(sorted(status.items())),
        "source_feature_counts": dict(sorted(source_kind.items())),
        "dataset": dataset,
        "hand_hit_by_split": {
            split: {"count": len(values), "mean": float(np.mean(values)) if values else None}
            for split, values in sorted(by_split.items())
        },
        "hand_hit_by_gloss": {
            gloss: {"count": len(values), "mean": float(np.mean(values)) if values else None}
            for gloss, values in sorted(by_gloss.items())
        },
        "errors": errors,
        "passed": not errors and dataset is not None and not dataset["nan"] and not dataset["inf"] and dataset["mask_matches_lengths"] and dataset["padded_zero"],
        "production_changes": "none",
        "next_required_action": "run package check, then train only if corrected dataset is accepted",
    }


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = [
        "pilot_config.json",
        "pilot_manifest.csv",
        "selected_classes.csv",
        "dataset/landmark_features.npz",
        "logs/corrected_feature_manifest.csv",
        "logs/corrected_dataset_summary.json",
    ]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    summary_path = run_dir / "logs" / "corrected_dataset_summary.json"
    summary = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        errors.extend(summary.get("errors", []))
        dataset = summary.get("dataset") or {}
        if dataset.get("shape") != [840, 96, 258]:
            errors.append(f"unexpected dataset shape: {dataset.get('shape')}")
        if not dataset.get("mask_matches_lengths"):
            errors.append("mask does not match lengths")
        if not dataset.get("padded_zero"):
            errors.append("padded frames are not zero")
    result = {
        "run_dir": str(run_dir.resolve()),
        "passed": not errors and bool(summary.get("passed")),
        "errors": errors,
        "source_feature_counts": summary.get("source_feature_counts"),
        "dataset": summary.get("dataset"),
        "hand_hit_by_split": summary.get("hand_hit_by_split"),
    }
    _write_json(run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build corrected E4-B strict dataset")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--overwrite", action="store_true")

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileExistsError, FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-b-correct] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())