"""Repair E6 five-sign validation using existing v3.0 tensors only.

No extraction, training, model export, or Android modification is performed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from pipeline.rgb.e6_v30_five_sign_baseline import CLASSES, _load_split


EXPERIMENT = "e6_v30_validation_repair_v1"
DEFAULT_BASELINE = Path(
    "artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_baseline_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e6_baseline/e6_v30_validation_repair_01"
)
DEFAULT_VALIDATION_SIGNER = "local_recorder:6F7328-S001"
SPLITS = ("train", "val", "test_fresh", "test_historical")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    records = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in records for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def plan_assignments(
    rows: list[dict[str, str]], validation_signer: str
) -> list[dict[str, str]]:
    coverage = Counter(
        (row["canonical_label"], row["signer_group_id"])
        for row in rows
        if row["split"] == "train"
    )
    missing = [label for label in CLASSES if coverage[(label, validation_signer)] < 20]
    if missing:
        raise ValueError(
            f"validation signer {validation_signer} lacks >=20 clips for: {missing}"
        )
    planned = []
    for row in rows:
        original = row["split"]
        if original == "train" and row["signer_group_id"] == validation_signer:
            new_split = "val"
            reason = "complete_local_signer_holdout"
        elif original == "val" and row["source_dataset"] == "asl_citizen":
            new_split = "val"
            reason = "retain_signer_disjoint_asl_cross_source_validation"
        elif original == "val":
            new_split = "validation_variant_stress"
            reason = "preserve_original_apphear_validation_as_variant_stress"
        else:
            new_split = original
            reason = "unchanged"
        planned.append({**row, "original_split": original, "new_split": new_split, "split_reason": reason})
    return planned


def _sample_store(feature_root: Path) -> dict[str, dict[str, Any]]:
    store: dict[str, dict[str, Any]] = {}
    for split in SPLITS:
        data = _load_split(feature_root, split)
        for index, sample_id in enumerate(data["sample_ids"].astype(str)):
            if sample_id in store:
                raise ValueError(f"duplicate feature sample_id: {sample_id}")
            store[sample_id] = {
                key: data[key][index]
                for key in (
                    "X", "frame_mask", "lengths", "y", "participant_ids", "sample_ids", "source_ids"
                )
            }
    return store


def _assemble(
    planned: list[dict[str, str]], store: dict[str, dict[str, Any]], output: Path
) -> dict[str, int]:
    counts = {}
    feature_root = output / "dataset" / "features"
    feature_root.mkdir(parents=True, exist_ok=True)
    for split in ("train", "val", "validation_variant_stress", "test_fresh", "test_historical"):
        selected = [row for row in planned if row["new_split"] == split]
        if not selected:
            raise ValueError(f"empty repaired split: {split}")
        items = [store[row["sample_id"]] for row in selected]
        np.savez_compressed(
            feature_root / f"{split}.npz",
            X=np.stack([item["X"] for item in items]).astype(np.float32),
            frame_mask=np.stack([item["frame_mask"] for item in items]).astype(bool),
            lengths=np.asarray([item["lengths"] for item in items], dtype=np.int32),
            y=np.asarray([item["y"] for item in items], dtype=np.int32),
            participant_ids=np.asarray([item["participant_ids"] for item in items], dtype=str),
            sample_ids=np.asarray([item["sample_ids"] for item in items], dtype=str),
            source_ids=np.asarray([item["source_ids"] for item in items], dtype=str),
        )
        counts[split] = len(items)
    return counts


def _summarize(planned: list[dict[str, str]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for split in ("train", "val", "validation_variant_stress", "test_fresh", "test_historical"):
        rows = [row for row in planned if row["new_split"] == split]
        by_class = {}
        for label in CLASSES:
            selected = [row for row in rows if row["canonical_label"] == label]
            by_class[label] = {
                "clips": len(selected),
                "signers": len({row["signer_group_id"] for row in selected}),
                "sources": dict(Counter(row["source_dataset"] for row in selected)),
            }
        summary[split] = {
            "clips": len(rows),
            "signers": len({row["signer_group_id"] for row in rows}),
            "sources": dict(Counter(row["source_dataset"] for row in rows)),
            "by_class": by_class,
        }
    return summary


def prepare(args: argparse.Namespace) -> int:
    baseline = args.baseline.resolve()
    output = args.output.resolve()
    feature_root = baseline / "dataset" / "features"
    manifest_path = baseline / "positive_extraction_manifest.csv"
    rows = _read_csv(manifest_path)
    planned = plan_assignments(rows, args.validation_signer)
    store = _sample_store(feature_root)
    if set(store) != {row["sample_id"] for row in planned}:
        raise ValueError("feature/manifest sample set mismatch")
    counts = _assemble(planned, store, output)
    shutil.copy2(feature_root / "vocab.json", output / "dataset" / "features" / "vocab.json")
    _write_csv(output / "repaired_assignment_manifest.csv", planned)
    summary = _summarize(planned)

    train_signers = {row["signer_group_id"] for row in planned if row["new_split"] == "train"}
    val_signers = {row["signer_group_id"] for row in planned if row["new_split"] == "val"}
    train_hashes = {row["raw_video_sha256"] for row in planned if row["new_split"] == "train"}
    val_hashes = {row["raw_video_sha256"] for row in planned if row["new_split"] == "val"}
    old_test_ids = {
        split: {row["sample_id"] for row in rows if row["split"] == split}
        for split in ("test_fresh", "test_historical")
    }
    new_test_ids = {
        split: {row["sample_id"] for row in planned if row["new_split"] == split}
        for split in ("test_fresh", "test_historical")
    }
    errors = []
    if train_signers & val_signers:
        errors.append(f"train/val signer overlap: {sorted(train_signers & val_signers)}")
    if train_hashes & val_hashes:
        errors.append(f"train/val raw hash overlap: {len(train_hashes & val_hashes)}")
    for label in CLASSES:
        if summary["val"]["by_class"][label]["clips"] < 20:
            errors.append(f"validation {label} below 20 clips")
        local_count = summary["val"]["by_class"][label]["sources"].get("local", 0)
        if local_count < 20:
            errors.append(f"validation {label} below 20 local clips")
    if summary["validation_variant_stress"]["clips"] != 163:
        errors.append("original AppHear variant-stress rows not preserved")
    for split in old_test_ids:
        if old_test_ids[split] != new_test_ids[split]:
            errors.append(f"{split} sample IDs changed")
    source_files = [manifest_path, *[feature_root / f"{split}.npz" for split in SPLITS]]
    report = {
        "experiment": EXPERIMENT,
        "baseline_run": str(baseline),
        "validation_signer": args.validation_signer,
        "controlled_change": "split reassignment only; tensors copied unchanged by sample_id",
        "counts": counts,
        "summary": summary,
        "integrity": {
            "train_val_signer_overlap": sorted(train_signers & val_signers),
            "train_val_raw_hash_overlap_count": len(train_hashes & val_hashes),
            "test_fresh_unchanged": old_test_ids["test_fresh"] == new_test_ids["test_fresh"],
            "test_historical_unchanged": old_test_ids["test_historical"] == new_test_ids["test_historical"],
            "source_file_sha256": {str(path.resolve()): _sha256(path) for path in source_files},
        },
        "errors": errors,
        "passed": not errors,
    }
    _write_json(output / "validation_repair_report.json", report)
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


def check(args: argparse.Namespace) -> int:
    required = [
        "repaired_assignment_manifest.csv",
        "validation_repair_report.json",
        "dataset/features/vocab.json",
        *[
            f"dataset/features/{split}.npz"
            for split in ("train", "val", "validation_variant_stress", "test_fresh", "test_historical")
        ],
    ]
    errors = [name for name in required if not (args.run_dir / name).is_file()]
    if not errors:
        report = json.loads((args.run_dir / "validation_repair_report.json").read_text(encoding="utf-8"))
        if not report.get("passed"):
            errors.extend(report.get("errors", ["repair report failed"]))
    result = {"run_dir": str(args.run_dir.resolve()), "passed": not errors, "errors": errors}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    prep.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prep.add_argument("--validation-signer", default=DEFAULT_VALIDATION_SIGNER)
    prep.set_defaults(func=prepare)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    check_parser.set_defaults(func=check)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
