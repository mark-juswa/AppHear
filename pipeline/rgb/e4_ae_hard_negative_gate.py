"""E4-AE hard-negative weighted signing gate.

Retrains the E4-AC low-motion-aware gate while upweighting train-split hard
negative no-sign windows mined by E4-AD. Validation and test rows are never used
as training hard negatives.

Experiment-only: no Android assets, model exports, production recognizer files,
or source datasets are modified.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.rgb.e4_ac_low_motion_aware_gate import run as ac_run, check as ac_check

DEFAULT_E4AD_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_ad_false_commit_review_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_ae_hard_negative_gate_01")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _collect_train_hard_negatives(e4ad_run: Path) -> list[str]:
    sample_ids: set[str] = set()
    for name in ("false_commit_manifest.csv", "hard_negative_candidates.csv"):
        path = e4ad_run / "review" / name
        if not path.exists():
            continue
        for row in _read_csv(path):
            if row.get("split") == "train" and row.get("source_kind") in {"N0", "P1"}:
                sample_ids.add(row["sample_id"])
    return sorted(sample_ids)


def _patch_sample_weights(args: argparse.Namespace, hard_negative_ids: set[str], sample_id_holder: dict[str, list[str]]):
    from pipeline.rgb import e4_ac_low_motion_aware_gate as ac

    original = ac._sample_weights

    def weighted(y_final: np.ndarray, train_mask: np.ndarray, ac_args: argparse.Namespace) -> np.ndarray:
        weights = original(y_final, train_mask, ac_args)
        sample_ids = sample_id_holder.get("sample_ids", [])
        if not sample_ids:
            return weights
        for index, sample_id in enumerate(sample_ids):
            if train_mask[index] and sample_id in hard_negative_ids:
                weights[index] = float(args.hard_negative_weight)
        return weights

    ac._sample_weights = weighted
    return original


def run(args: argparse.Namespace) -> dict[str, Any]:
    from pipeline.rgb import e4_ac_low_motion_aware_gate as ac

    hard_negative_ids = set(_collect_train_hard_negatives(args.e4ad_run))
    if not hard_negative_ids:
        raise ValueError("no train hard negatives found in E4-AD run")
    original_combined = ac._combined_dataset
    sample_id_holder: dict[str, list[str]] = {}

    def combined_with_ids(primary_run: Path, e4aa_run: Path) -> dict[str, np.ndarray]:
        data = original_combined(primary_run, e4aa_run)
        sample_id_holder["sample_ids"] = [str(v) for v in data["sample_ids"]]
        return data

    ac._combined_dataset = combined_with_ids
    original_weights = _patch_sample_weights(args, hard_negative_ids, sample_id_holder)
    try:
        ac_args = argparse.Namespace(**vars(args))
        ac_args.output = args.output
        result = ac_run(ac_args)
    finally:
        ac._combined_dataset = original_combined
        ac._sample_weights = original_weights
    result["experiment"] = "e4_ae_hard_negative_gate_v1"
    result["e4ad_run"] = str(args.e4ad_run.resolve())
    result["hard_negative_training"] = {
        "train_hard_negative_count": len(hard_negative_ids),
        "hard_negative_weight": float(args.hard_negative_weight),
        "sample_ids": sorted(hard_negative_ids),
        "leakage_guard": "only split=train rows from E4-AD manifests are upweighted",
    }
    result["decision"] = "hard_negative_gate_candidate" if result.get("passed") else "hard_negative_gate_no_go"
    _write_json(args.output / "metrics" / "hard_negative_gate_metrics.json", result)
    return result


def check(args: argparse.Namespace) -> dict[str, Any]:
    result = ac_check(args)
    if not (args.run_dir / "metrics" / "hard_negative_gate_metrics.json").exists():
        result["errors"].append("missing output: metrics/hard_negative_gate_metrics.json")
        result["passed"] = False
    _write_json(args.run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-AE hard-negative weighted signing gate")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--e4ad-run", type=Path, default=DEFAULT_E4AD_RUN)
    run_parser.add_argument("--e4aa-run", type=Path, default=Path("artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_01"))
    run_parser.add_argument("--primary-run", type=Path, default=Path("artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01"))
    run_parser.add_argument("--specialist-run", type=Path, default=Path("artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01"))
    run_parser.add_argument("--e4x-run", type=Path, default=Path("artifacts/recognition_upgrade/e4_generalization/e4_x_routed_system_validation_01"))
    run_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    run_parser.add_argument("--epochs", type=int, default=30)
    run_parser.add_argument("--batch-size", type=int, default=16)
    run_parser.add_argument("--learning-rate", type=float, default=8e-4)
    run_parser.add_argument("--positive-weight", type=float, default=1.0)
    run_parser.add_argument("--sorry-weight", type=float, default=8.0)
    run_parser.add_argument("--no-sign-weight", type=float, default=1.0)
    run_parser.add_argument("--hard-negative-weight", type=float, default=6.0)
    run_parser.add_argument("--accepted-precision-min", type=float, default=0.95)
    run_parser.add_argument("--positive-coverage-min", type=float, default=0.80)
    run_parser.add_argument("--no-sign-false-commit-rate-max", type=float, default=0.10)
    run_parser.add_argument("--good-recall-min", type=float, default=0.90)
    run_parser.add_argument("--sorry-recall-min", type=float, default=0.90)

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--require-metrics", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-ae] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

