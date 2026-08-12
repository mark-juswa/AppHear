"""Assemble versioned Phase 1 v3.0 tensors from the verified manifest.

This module reuses existing feature artifacts. It does not extract landmarks,
train a model, read protected replay as model input, or modify Android assets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_DIR = ROOT / (
    "artifacts/recognition_upgrade/phase1_full_vocab/manifest_01"
)
DEFAULT_OUTPUT = ROOT / (
    "artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1"
)
DEFAULT_VOCAB = Path(
    r"F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_conversational\vocab.json"
)
OUTPUT_ROLES = {
    "train": ("primary_train", "supplement_train"),
    "val": ("primary_val",),
    "test": ("primary_test",),
    "diagnostic_validation_stress": ("supplement_validation_stress",),
    "diagnostic_reused_positive": ("reused_positive_diagnostic",),
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _write_rows(path: Path, rows: Iterable[dict[str, str]]) -> None:
    rows = list(rows)
    if not rows:
        raise ValueError(f"cannot write empty row manifest: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _load_feature_row(
    row: dict[str, str], cache: dict[Path, dict[str, np.ndarray]]
) -> tuple[np.ndarray, int, np.ndarray, int]:
    path = Path(row["feature_artifact_path"])
    if not path.is_file():
        raise FileNotFoundError(f"missing feature artifact: {path}")
    row_index = row["feature_row_index"].strip()
    if row_index:
        if path not in cache:
            with np.load(path, allow_pickle=True) as data:
                cache[path] = {
                    "X": np.asarray(data["X"]),
                    "y": np.asarray(data["y"]),
                    "frame_mask": np.asarray(data["frame_mask"]),
                    "lengths": np.asarray(data["lengths"]),
                }
        source = cache[path]
        index = int(row_index)
        feature = source["X"][index]
        label = int(source["y"][index])
        frame_mask = source["frame_mask"][index]
        length = int(source["lengths"][index])
    else:
        with np.load(path, allow_pickle=False) as data:
            feature = np.asarray(data["feature"])
            frame_mask = np.asarray(data["frame_mask"])
            length = int(np.asarray(data["length"]).item())
        label = int(row["class_id"])
    expected_label = int(row["class_id"])
    if label != expected_label:
        raise ValueError(
            f"{row['sample_id']}: tensor label {label} != manifest {expected_label}"
        )
    if length != int(row["feature_length"]):
        raise ValueError(f"{row['sample_id']}: feature length mismatch")
    return (
        np.asarray(feature, dtype=np.float32),
        label,
        np.asarray(frame_mask, dtype=bool),
        length,
    )


def validate_arrays(
    x: np.ndarray,
    y: np.ndarray,
    frame_mask: np.ndarray,
    lengths: np.ndarray,
) -> list[str]:
    """Validate the frozen v3.0 tensor contract without changing values."""
    errors: list[str] = []
    n = len(y)
    if x.shape != (n, 96, 258):
        errors.append(f"X shape={x.shape}, expected={(n, 96, 258)}")
    if frame_mask.shape != (n, 96):
        errors.append(f"frame_mask shape={frame_mask.shape}, expected={(n, 96)}")
    if lengths.shape != (n,):
        errors.append(f"lengths shape={lengths.shape}, expected={(n,)}")
    if x.dtype != np.float32:
        errors.append(f"X dtype={x.dtype}, expected=float32")
    if y.dtype != np.int32:
        errors.append(f"y dtype={y.dtype}, expected=int32")
    if frame_mask.dtype != np.bool_:
        errors.append(f"frame_mask dtype={frame_mask.dtype}, expected=bool")
    if lengths.dtype != np.int32:
        errors.append(f"lengths dtype={lengths.dtype}, expected=int32")
    if not np.isfinite(x).all():
        errors.append("X contains non-finite values")
    if n and (int(y.min()) < 0 or int(y.max()) >= 236):
        errors.append("labels fall outside [0,235]")
    if n and (int(lengths.min()) < 1 or int(lengths.max()) > 96):
        errors.append("lengths fall outside [1,96]")
    if frame_mask.shape == (n, 96) and not np.array_equal(
        frame_mask.sum(axis=1).astype(np.int32), lengths
    ):
        errors.append("frame_mask counts do not equal lengths")
    return errors


def _select_rows(
    rows: list[dict[str, str]], roles: tuple[str, ...], smoke_limit: int | None
) -> list[dict[str, str]]:
    if smoke_limit is None:
        return [row for row in rows if row["role"] in roles]
    selected: list[dict[str, str]] = []
    for role in roles:
        role_rows = [row for row in rows if row["role"] == role]
        selected.extend(role_rows[:smoke_limit])
    return selected


def _assemble_split(
    name: str,
    rows: list[dict[str, str]],
    output: Path,
    cache: dict[Path, dict[str, np.ndarray]],
) -> dict[str, Any]:
    loaded = [_load_feature_row(row, cache) for row in rows]
    x = np.stack([item[0] for item in loaded]).astype(np.float32, copy=False)
    y = np.asarray([item[1] for item in loaded], dtype=np.int32)
    frame_mask = np.stack([item[2] for item in loaded]).astype(bool, copy=False)
    lengths = np.asarray([item[3] for item in loaded], dtype=np.int32)
    errors = validate_arrays(x, y, frame_mask, lengths)
    if errors:
        raise ValueError(f"{name}: {'; '.join(errors)}")

    sample_ids = np.asarray([row["sample_id"] for row in rows])
    signer_ids = np.asarray([row["signer_group_id"] for row in rows])
    sources = np.asarray([row["source_dataset"] for row in rows])
    hashes = np.asarray([row["raw_video_sha256"] for row in rows])
    roles = np.asarray([row["role"] for row in rows])
    npz_path = output / f"{name}.npz"
    np.savez_compressed(
        npz_path,
        X=x,
        y=y,
        frame_mask=frame_mask,
        lengths=lengths,
        participant_ids=signer_ids,
        sample_ids=sample_ids,
        source_datasets=sources,
        raw_video_sha256=hashes,
        roles=roles,
        schema_version=np.asarray("3.0"),
    )
    _write_rows(output / "manifests" / f"{name}.csv", rows)
    return {
        "rows": len(rows),
        "classes": len(set(y.tolist())),
        "signers": len(set(signer_ids.tolist())),
        "source_counts": dict(sorted(Counter(sources.tolist()).items())),
        "role_counts": dict(sorted(Counter(roles.tolist()).items())),
        "npz": str(npz_path.resolve()),
        "npz_sha256": _sha256(npz_path),
        "npz_bytes": npz_path.stat().st_size,
    }


def assemble(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = args.manifest_dir / "canonical_manifest.csv"
    manifest_summary_path = args.manifest_dir / "manifest_summary.json"
    if not manifest_path.is_file() or not manifest_summary_path.is_file():
        raise FileNotFoundError("verified Phase 1 manifest package is incomplete")
    manifest_summary = json.loads(manifest_summary_path.read_text(encoding="utf-8"))
    if not manifest_summary.get("passed") or not manifest_summary.get("verify_hashes"):
        raise ValueError("manifest package has not passed full hash verification")
    rows = _read_csv(manifest_path)
    if any(row["schema_version"] != "3.0" for row in rows):
        raise ValueError("manifest contains a non-v3.0 feature row")
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)

    smoke_limit = args.smoke_limit if args.smoke else None
    cache: dict[Path, dict[str, np.ndarray]] = {}
    split_summaries: dict[str, Any] = {}
    for name, roles in OUTPUT_ROLES.items():
        selected = _select_rows(rows, roles, smoke_limit)
        if not selected:
            raise ValueError(f"no rows selected for {name}")
        split_summaries[name] = _assemble_split(name, selected, args.output, cache)

    shutil.copy2(args.vocab, args.output / "vocab.json")
    summary = {
        "experiment": "phase1_full_vocab_dataset_v1",
        "scope": "tensor assembly only; no extraction, training, export, or Android changes",
        "schema_version": "3.0",
        "feature_contract": [96, 258],
        "smoke": args.smoke,
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256": _sha256(manifest_path),
        "splits": split_summaries,
        "protected_replay_materialized": False,
        "passed": True,
        "next": "run check, then prepare equal-budget TCN training smoke",
    }
    (args.output / "assembly_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    summary_path = args.output / "assembly_summary.json"
    if not summary_path.is_file():
        errors.append(f"missing assembly summary: {summary_path}")
        summary: dict[str, Any] = {}
    else:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    manifest_path = args.manifest_dir / "canonical_manifest.csv"
    if summary and manifest_path.is_file():
        if summary.get("manifest_sha256") != _sha256(manifest_path):
            errors.append("canonical manifest changed after assembly")
    for name in OUTPUT_ROLES:
        path = args.output / f"{name}.npz"
        if not path.is_file():
            errors.append(f"missing tensor split: {path}")
            continue
        with np.load(path, allow_pickle=True) as data:
            required = {
                "X",
                "y",
                "frame_mask",
                "lengths",
                "participant_ids",
                "sample_ids",
                "source_datasets",
                "raw_video_sha256",
                "roles",
                "schema_version",
            }
            missing = sorted(required - set(data.files))
            if missing:
                errors.append(f"{name}: missing keys {missing}")
                continue
            errors.extend(
                f"{name}: {error}"
                for error in validate_arrays(
                    data["X"], data["y"], data["frame_mask"], data["lengths"]
                )
            )
            if str(np.asarray(data["schema_version"]).item()) != "3.0":
                errors.append(f"{name}: schema_version is not 3.0")
            if name == "train" and not summary.get("smoke"):
                if len(set(data["y"].astype(int).tolist())) != 236:
                    errors.append("train: full assembly does not cover 236 classes")
    if (args.output / "protected_replay.npz").exists():
        errors.append("protected replay was materialized as a model tensor")
    result = {
        "run_dir": str(args.output.resolve()),
        "smoke": bool(summary.get("smoke", False)),
        "errors": errors,
        "passed": not errors,
    }
    if args.output.exists():
        (args.output / "check_report.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("assemble", "check"):
        child = sub.add_parser(command)
        child.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR)
        child.add_argument("--vocab", type=Path, default=DEFAULT_VOCAB)
        child.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
        child.add_argument("--smoke", action="store_true")
        child.add_argument("--smoke-limit", type=int, default=8)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = assemble(args) if args.command == "assemble" else check(args)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
