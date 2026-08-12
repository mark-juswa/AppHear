"""E4-AG HELLO-like no-sign expansion.

Builds an expanded no-sign dataset by appending a targeted reviewed P1-style
"hands visible but not signing" capture set to the existing E4-AA N0/P1 no-sign
dataset. The output is intentionally shaped like an E4-AA run directory so the
existing E4-AC low-motion-aware gate trainer can consume it unchanged.

Experiment-only: no Android assets, TFLite exports, production recognizer files,
or source datasets are modified.
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

from pipeline.extract.config import load_config as load_extract_config
from pipeline.extract.landmarks import LandmarkExtractor
from pipeline.features.contract import SCHEMA_VERSION
from pipeline.normalize.config import load_config as load_normalize_config
from pipeline.rgb.e4_aa_nosign_temporal_gate import (
    DEFAULT_E4Y_RUN,
    DEFAULT_EXTRACT_CONFIG,
    DEFAULT_NORMALIZE_CONFIG,
    SPLITS,
    _eligible_rows,
    _extract_nosign,
    _read_csv,
    _write_csv,
    _write_json,
)
from pipeline.rgb.e4_y_real_nosign_feature_validation import _clip_video_map

DEFAULT_BASE_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_01")
DEFAULT_EXTRA_P1_RUN = Path("artifacts/recognition_upgrade/e2e_c0/hello_like_p1_capture_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_ag_hello_like_nosign_expansion_01")


def _load_npz(path: Path, description: str) -> dict[str, np.ndarray]:
    if not path.exists():
        raise FileNotFoundError(f"missing {description}: {path}")
    data = np.load(path, allow_pickle=False)
    return {key: data[key] for key in data.files}


def _copy_base_cache(base_run: Path, output: Path) -> None:
    source = base_run / "dataset" / "stage_e_cache"
    target = output / "dataset" / "stage_e_cache"
    target.mkdir(parents=True, exist_ok=True)
    if source.exists():
        for item in source.glob("*.npz"):
            dest = target / item.name
            if not dest.exists():
                shutil.copy2(item, dest)


def _prefixed_extra_rows(rows: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        item["sample_id"] = f"{prefix}_{row['sample_id']}"
        item["source_kind"] = "P1_HELLO_LIKE"
        out.append(item)
    return out


def _write_capture_guide(output: Path) -> None:
    guide = """# E4-AG HELLO-Like No-Sign Capture Guide

Record short clips where hands are visible but the person is not signing.

Goal: capture ordinary hand movement that can look like HELLO to the current
recognizer.

Recommended content:

- casual waving that is not intended as ASL HELLO;
- hands near face, chest, shoulder, or side of body;
- talking gestures;
- adjusting hair, glasses, sleeves, phone, or sitting posture;
- resting hands with small movement;
- different people, phones, distances, shirts, and backgrounds.

Do not include actual ASL signs.

Folder layout:

```text
scratchpad/e4_ag_hello_like_nosign/raw/p1/<participant>/<device>/<environment>/front/<video>.mp4
```

Example:

```text
scratchpad/e4_ag_hello_like_nosign/raw/p1/P03/phoneA/indoor/front/p03_hello_like_01.mp4
```

Target for this bounded pass:

- at least 4 participants if available;
- 2 devices if available;
- 8 to 15 clips total;
- 15 to 30 seconds per clip;
- hands visible in most frames;
- front camera first, because that matches the current app path.
"""
    (output / "README_CAPTURE_GUIDE.md").write_text(guide, encoding="utf-8")


def _summarize_manifest(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "split_counts": dict(sorted(Counter(row["split"] for row in rows).items())),
        "source_counts": dict(sorted(Counter(row["source_kind"] for row in rows).items())),
        "participant_counts": dict(sorted(Counter(row.get("participant_id", "") for row in rows).items())),
        "device_counts": dict(sorted(Counter(row.get("device_id", "") for row in rows).items())),
        "environment_counts": dict(sorted(Counter(row.get("environment_id", "") for row in rows).items())),
        "mean_hand_hit_rate_by_source": {
            source: float(np.mean([float(row["hand_hit_rate_window"]) for row in rows if row["source_kind"] == source]))
            for source in sorted({row["source_kind"] for row in rows})
            if any(row["source_kind"] == source for row in rows)
        },
        "mean_pose_hit_rate_by_source": {
            source: float(np.mean([float(row["pose_hit_rate_window"]) for row in rows if row["source_kind"] == source]))
            for source in sorted({row["source_kind"] for row in rows})
            if any(row["source_kind"] == source for row in rows)
        },
        "schema_version": SCHEMA_VERSION,
    }


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    for relative in ("dataset/stage_e_cache", "logs"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    _write_capture_guide(output)

    base_features_path = args.base_run / "dataset" / "nosign_features.npz"
    base_manifest_path = args.base_run / "dataset" / "nosign_manifest.csv"
    base = _load_npz(base_features_path, "base E4-AA no-sign tensor")
    base_manifest = _read_csv(base_manifest_path)
    _copy_base_cache(args.base_run, output)

    extra_rows = _eligible_rows(
        args.extra_p1_run,
        "p1",
        int(args.max_extra_p1),
        int(args.split_seed),
        float(args.train_ratio),
        float(args.val_ratio),
    )
    if not extra_rows:
        raise ValueError("no eligible reviewed HELLO-like P1 rows found")
    extra_rows = _prefixed_extra_rows(extra_rows, str(args.extra_prefix))

    extract_config = load_extract_config(args.extract_config)
    normalize_config = load_normalize_config(args.normalize_config)
    video_map = _clip_video_map(args.extra_p1_run)
    cache_sources = [args.e4y_run / "dataset" / "stage_e_cache", args.base_run / "dataset" / "stage_e_cache"]
    with LandmarkExtractor(extract_config) as extractor:
        extra_dataset, extra_manifest = _extract_nosign(
            extra_rows,
            video_map,
            extractor,
            normalize_config,
            int(args.window),
            output / "dataset" / "stage_e_cache",
            cache_sources,
        )

    dataset = {
        "landmarks": np.concatenate([base["landmarks"].astype(np.float32), extra_dataset["landmarks"].astype(np.float32)], axis=0),
        "frame_mask": np.concatenate([base["frame_mask"].astype(bool), extra_dataset["frame_mask"].astype(bool)], axis=0),
        "y": np.concatenate([base["y"].astype(np.int64), extra_dataset["y"].astype(np.int64)], axis=0),
        "split_index": np.concatenate([base["split_index"].astype(np.int64), extra_dataset["split_index"].astype(np.int64)], axis=0),
        "lengths": np.concatenate([base["lengths"].astype(np.int32), extra_dataset["lengths"].astype(np.int32)], axis=0),
        "sample_ids": np.concatenate([np.asarray(base["sample_ids"]).astype(str), np.asarray(extra_dataset["sample_ids"]).astype(str)]).astype(str),
        "source": np.concatenate([np.asarray(base["source"]).astype(str), np.asarray(extra_dataset["source"]).astype(str)]).astype(str),
    }
    np.savez_compressed(output / "dataset" / "nosign_features.npz", **dataset)
    manifest = [dict(row) for row in base_manifest] + extra_manifest
    fields = [
        "sample_id",
        "source_kind",
        "split",
        "clip_id",
        "participant_id",
        "device_id",
        "environment_id",
        "camera_facing",
        "timestamp_ms",
        "frame_index",
        "window_onset",
        "window_release",
        "length",
        "native_fps",
        "hand_hit_rate_window",
        "pose_hit_rate_window",
    ]
    _write_csv(output / "dataset" / "nosign_manifest.csv", manifest, fields)
    summary = {
        "experiment": "e4_ag_hello_like_nosign_expansion_v1",
        "run_dir": str(output.resolve()),
        "base_run": str(args.base_run.resolve()),
        "extra_p1_run": str(args.extra_p1_run.resolve()),
        "base_rows": int(base["landmarks"].shape[0]),
        "extra_rows": int(extra_dataset["landmarks"].shape[0]),
        "combined_rows": int(dataset["landmarks"].shape[0]),
        "shape": [int(v) for v in dataset["landmarks"].shape],
        **_summarize_manifest(manifest),
        "next_train_command": f"python -m pipeline.rgb.e4_ac_low_motion_aware_gate run --e4aa-run \"{output}\" --output \"artifacts/recognition_upgrade/e4_generalization/e4_ag_low_motion_gate_01\"",
        "warning": "Dataset expansion only; train/evaluate the gate with E4-AC runner next.",
    }
    _write_json(output / "logs" / "dataset_summary.json", summary)
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["dataset/nosign_features.npz", "dataset/nosign_manifest.csv", "logs/dataset_summary.json", "README_CAPTURE_GUIDE.md"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if args.require_dataset and (run_dir / "dataset" / "nosign_features.npz").exists():
        data = np.load(run_dir / "dataset" / "nosign_features.npz", allow_pickle=False)
        if tuple(data["landmarks"].shape[1:]) != (96, 258):
            errors.append(f"unexpected landmarks shape: {data['landmarks'].shape}")
        if data["landmarks"].shape[0] <= 288:
            errors.append("combined dataset did not grow beyond E4-AA baseline")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def init(args: argparse.Namespace) -> dict[str, Any]:
    raw = args.raw_root / "p1" / "P03" / "phoneA" / "indoor" / "front"
    raw.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    _write_capture_guide(args.output)
    return {
        "experiment": "e4_ag_hello_like_nosign_expansion_v1",
        "raw_folder_created": str(raw.resolve()),
        "capture_guide": str((args.output / "README_CAPTURE_GUIDE.md").resolve()),
        "next_prepare_capture_command": f"python -m pipeline.tracking.e2e_c0_capture prepare --raw-root \"{args.raw_root}\" --kind p1 --output \"{args.extra_p1_run}\" --max-total 160",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-AG HELLO-like no-sign expansion")
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init")
    init_p.add_argument("--raw-root", type=Path, default=Path("scratchpad/e4_ag_hello_like_nosign/raw"))
    init_p.add_argument("--extra-p1-run", type=Path, default=DEFAULT_EXTRA_P1_RUN)
    init_p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)

    prep = sub.add_parser("prepare")
    prep.add_argument("--base-run", type=Path, default=DEFAULT_BASE_RUN)
    prep.add_argument("--extra-p1-run", type=Path, default=DEFAULT_EXTRA_P1_RUN)
    prep.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prep.add_argument("--e4y-run", type=Path, default=DEFAULT_E4Y_RUN)
    prep.add_argument("--extract-config", type=Path, default=DEFAULT_EXTRACT_CONFIG)
    prep.add_argument("--normalize-config", type=Path, default=DEFAULT_NORMALIZE_CONFIG)
    prep.add_argument("--window", type=int, default=96)
    prep.add_argument("--max-extra-p1", type=int, default=120)
    prep.add_argument("--split-seed", type=int, default=280803)
    prep.add_argument("--train-ratio", type=float, default=0.60)
    prep.add_argument("--val-ratio", type=float, default=0.20)
    prep.add_argument("--extra-prefix", default="e4ag")

    check_p = sub.add_parser("check")
    check_p.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    check_p.add_argument("--require-dataset", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "init":
            result = init(args)
        elif args.command == "prepare":
            result = prepare(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-ag] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
