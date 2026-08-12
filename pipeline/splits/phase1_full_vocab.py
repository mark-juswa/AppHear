"""Prepare and validate the Phase 1 full-vocabulary dataset manifest.

This module is deliberately data-only. It reconstructs the existing ASL Citizen
236-class feature rows from Stage-E and span lineage, attaches reviewed E6
supplementary rows, and protects clean replay clips. It never extracts features,
trains a model, or changes Android assets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.detect.schema import SpanSidecar
from pipeline.features.config import load_config as load_features_config
from pipeline.quality.config import load_config as load_quality_config
from pipeline.quality.gate import evaluate_quality

ROOT = Path(__file__).resolve().parents[2]
ASL_ROOT = Path(r"F:\ASL DATASET\ASL CITIZEN")
DERIVED_ROOT = ASL_ROOT / "derived/apphear3"
DEFAULT_CONFIG = ROOT / "pipeline/config/features.yaml"
DEFAULT_VOCAB = DERIVED_ROOT / "features_conversational/vocab.json"
DEFAULT_FEATURES = DERIVED_ROOT / "features_streaming_conversational"
DEFAULT_ASL_SPLITS = ASL_ROOT / "ASL_Citizen/splits"
DEFAULT_ASL_VIDEOS = ASL_ROOT / "ASL_Citizen/videos"
DEFAULT_E6_RUN = ROOT / (
    "artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_baseline_01"
)
DEFAULT_ELIGIBILITY = ROOT / (
    "artifacts/recognition_upgrade/heldout_baseline_evaluation/"
    "eligibility_audit_01/eligibility_manifest.csv"
)
DEFAULT_OUTPUT = ROOT / (
    "artifacts/recognition_upgrade/phase1_full_vocab/manifest_01"
)
SPLITS = ("train", "val", "test")
MANIFEST_FIELDS = (
    "sample_id",
    "role",
    "split",
    "source_dataset",
    "canonical_gloss",
    "class_id",
    "signer_group_id",
    "raw_video_path",
    "raw_video_sha256",
    "raw_video_bytes",
    "source_manifest_path",
    "source_row_index",
    "stage_e_path",
    "span_path",
    "feature_artifact_path",
    "feature_row_index",
    "feature_length",
    "schema_version",
    "lineage_status",
    "training_eligible",
    "notes",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in MANIFEST_FIELDS})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _source_rows(path: Path) -> dict[str, tuple[int, dict[str, str]]]:
    rows = _read_csv(path)
    return {row["Video file"]: (index, row) for index, row in enumerate(rows)}


def _tensor_identity(path: Path) -> list[tuple[int, str, int]]:
    with np.load(path, allow_pickle=True) as data:
        return list(
            zip(
                data["y"].astype(int).tolist(),
                data["participant_ids"].astype(str).tolist(),
                data["lengths"].astype(int).tolist(),
                strict=True,
            )
        )


def reconstruct_asl_rows(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[str]]:
    """Recreate the exact ASL Citizen row order used by the 236-class tensors."""
    feature_cfg = load_features_config(args.features_config)
    quality_cfg = load_quality_config(feature_cfg.quality_config)
    vocab: dict[str, int] = json.loads(args.vocab.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for split in SPLITS:
        source_path = args.asl_splits / f"{split}.csv"
        source_by_video = _source_rows(source_path)
        reconstructed: list[tuple[int, str, int]] = []
        split_rows: list[dict[str, Any]] = []
        for stage_e in sorted((quality_cfg.input_root / split).glob("*.npz")):
            span_path = quality_cfg.spans_root / split / f"{stage_e.stem}.span.json"
            if not span_path.is_file():
                continue
            span = SpanSidecar.load(span_path)
            if span.gloss not in vocab:
                continue
            with np.load(stage_e, allow_pickle=False) as data:
                quality = evaluate_quality(
                    data["hand_score"],
                    data["pose_score"],
                    span.onset,
                    span.release,
                    span.valid,
                    span.native_fps,
                    quality_cfg,
                )
            if not quality.accept:
                continue

            video_name = f"{stage_e.stem}.mp4"
            source = source_by_video.get(video_name)
            if source is None:
                errors.append(f"{split}: source CSV missing {video_name}")
                continue
            source_index, source_row = source
            length = min(feature_cfg.streaming_t_max, span.release - span.onset + 1)
            identity = (vocab[span.gloss], span.participant_id, length)
            reconstructed.append(identity)
            raw_video = args.asl_videos / video_name
            exists = raw_video.is_file()
            digest = _sha256(raw_video) if exists and args.verify_hashes else ""
            if not exists:
                errors.append(f"missing raw video: {raw_video}")
            if source_row["Participant ID"] != span.participant_id:
                errors.append(f"{split}:{stage_e.stem}: participant mismatch")
            split_rows.append(
                {
                    "sample_id": f"asl:{split}:{stage_e.stem}",
                    "role": f"primary_{split}",
                    "split": split,
                    "source_dataset": "ASL_CITIZEN",
                    "canonical_gloss": span.gloss,
                    "class_id": vocab[span.gloss],
                    "signer_group_id": f"asl_citizen:{span.participant_id}",
                    "raw_video_path": str(raw_video.resolve()),
                    "raw_video_sha256": digest,
                    "raw_video_bytes": raw_video.stat().st_size if exists else "",
                    "source_manifest_path": str(source_path.resolve()),
                    "source_row_index": source_index,
                    "stage_e_path": str(stage_e.resolve()),
                    "span_path": str(span_path.resolve()),
                    "feature_artifact_path": str(
                        (args.features / f"{split}.npz").resolve()
                    ),
                    "feature_row_index": len(split_rows),
                    "feature_length": length,
                    "schema_version": "3.0",
                    "lineage_status": "verified_raw_stage_e_span_tensor",
                    "training_eligible": str(split == "train").lower(),
                    "notes": "official signer split preserved",
                }
            )

        observed = _tensor_identity(args.features / f"{split}.npz")
        if reconstructed != observed:
            mismatch = sum(a != b for a, b in zip(reconstructed, observed, strict=False))
            mismatch += abs(len(reconstructed) - len(observed))
            errors.append(f"{split}: reconstructed tensor identity mismatches={mismatch}")
        rows.extend(split_rows)
    return rows, errors


def e6_rows(
    args: argparse.Namespace, vocab: dict[str, int]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Attach reviewed E6 rows without allowing them to alter the ASL test protocol."""
    manifest = args.e6_run / "positive_extraction_manifest.csv"
    per_clip = args.e6_run / "dataset/per_clip"
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for source_index, row in enumerate(_read_csv(manifest)):
        if row["source_dataset"].lower() == "asl_citizen":
            continue
        role_by_split = {
            "train": "supplement_train",
            "val": "supplement_validation_stress",
            "test_fresh": "reused_positive_diagnostic",
        }
        role = role_by_split.get(row["split"])
        if role is None:
            continue
        gloss = row["canonical_label"]
        if gloss not in vocab:
            errors.append(f"E6 unknown vocabulary label: {gloss}")
            continue
        feature_path = per_clip / f"{row['sample_id']}.npz"
        raw_video = Path(row["raw_video_path"])
        if not feature_path.is_file():
            errors.append(f"missing E6 feature: {feature_path}")
            continue
        if not raw_video.is_file():
            errors.append(f"missing E6 raw video: {raw_video}")
            continue
        with np.load(feature_path, allow_pickle=False) as data:
            feature = np.asarray(data["feature"])
            frame_mask = np.asarray(data["frame_mask"])
            length = int(np.asarray(data["length"]).item())
        if feature.shape != (96, 258) or frame_mask.shape != (96,):
            errors.append(f"bad E6 feature contract: {feature_path}")
            continue
        expected_hash = row["raw_video_sha256"].upper()
        if args.verify_hashes and _sha256(raw_video) != expected_hash:
            errors.append(f"E6 hash mismatch: {raw_video}")
        training_eligible = role == "supplement_train"
        rows.append(
            {
                "sample_id": f"e6:{row['sample_id']}",
                "role": role,
                "split": "train" if training_eligible else "diagnostic",
                "source_dataset": row["source_dataset"].upper(),
                "canonical_gloss": gloss,
                "class_id": vocab[gloss],
                "signer_group_id": row["signer_group_id"],
                "raw_video_path": str(raw_video.resolve()),
                "raw_video_sha256": expected_hash,
                "raw_video_bytes": raw_video.stat().st_size,
                "source_manifest_path": str(manifest.resolve()),
                "source_row_index": source_index,
                "stage_e_path": "",
                "span_path": "",
                "feature_artifact_path": str(feature_path.resolve()),
                "feature_row_index": "",
                "feature_length": length,
                "schema_version": "3.0",
                "lineage_status": "verified_reviewed_e6_feature",
                "training_eligible": str(training_eligible).lower(),
                "notes": "E6 validation/fresh rows remain diagnostic only",
            }
        )
    return rows, errors


def protected_replay_rows(
    args: argparse.Namespace, vocab: dict[str, int]
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for source_index, row in enumerate(_read_csv(args.eligibility_manifest)):
        if row["eligibility"] != "clean_isolated_replay_candidate":
            continue
        gloss = row["label_or_subtype"]
        if gloss not in vocab:
            errors.append(f"protected replay unknown vocabulary label: {gloss}")
            continue
        raw_video = Path(row["raw_video_path"])
        if not raw_video.is_file():
            errors.append(f"missing protected replay video: {raw_video}")
            continue
        expected_hash = row["raw_video_sha256"].upper()
        if args.verify_hashes and _sha256(raw_video) != expected_hash:
            errors.append(f"protected replay hash mismatch: {raw_video}")
        rows.append(
            {
                "sample_id": f"replay:{expected_hash[:16]}",
                "role": "protected_clean_replay",
                "split": "protected_replay",
                "source_dataset": "APPHEAR_CAPTURE",
                "canonical_gloss": gloss,
                "class_id": vocab[gloss],
                "signer_group_id": row["signer_group_id"],
                "raw_video_path": str(raw_video.resolve()),
                "raw_video_sha256": expected_hash,
                "raw_video_bytes": raw_video.stat().st_size,
                "source_manifest_path": str(args.eligibility_manifest.resolve()),
                "source_row_index": source_index,
                "stage_e_path": "",
                "span_path": "",
                "feature_artifact_path": "",
                "feature_row_index": "",
                "feature_length": "",
                "schema_version": "3.0",
                "lineage_status": "verified_reserved_raw_video",
                "training_eligible": "false",
                "notes": "must remain excluded from training and model selection",
            }
        )
    return rows, errors


def audit_rows(rows: list[dict[str, Any]], expected_classes: int = 236) -> list[str]:
    errors: list[str] = []
    train = [row for row in rows if row["training_eligible"] == "true"]
    primary = [row for row in rows if row["role"].startswith("primary_")]
    primary_signers: dict[str, set[str]] = defaultdict(set)
    for row in primary:
        primary_signers[row["split"]].add(row["signer_group_id"])
    for left, right in (("train", "val"), ("train", "test"), ("val", "test")):
        overlap = primary_signers[left] & primary_signers[right]
        if overlap:
            errors.append(f"primary signer leakage {left}/{right}: {sorted(overlap)}")
    classes = {int(row["class_id"]) for row in primary if row["split"] == "train"}
    if len(classes) != expected_classes:
        errors.append(f"primary train classes={len(classes)}, expected={expected_classes}")

    hash_roles: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        digest = str(row["raw_video_sha256"]).strip().upper()
        if digest:
            hash_roles[digest].add(row["role"])
    for digest, roles in hash_roles.items():
        if "protected_clean_replay" in roles and any(
            row["training_eligible"] == "true" and row["raw_video_sha256"] == digest
            for row in rows
        ):
            errors.append(f"protected replay hash entered training: {digest}")

    sample_ids = [str(row["sample_id"]) for row in rows]
    if len(sample_ids) != len(set(sample_ids)):
        errors.append("duplicate sample_id values")
    if not train:
        errors.append("no training-eligible rows")
    return errors


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    required = (
        args.features_config,
        args.vocab,
        args.eligibility_manifest,
        args.e6_run / "positive_extraction_manifest.csv",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing required inputs: {missing}")
    vocab: dict[str, int] = json.loads(args.vocab.read_text(encoding="utf-8"))
    if len(vocab) != 236:
        raise ValueError(f"expected 236-class vocabulary, found {len(vocab)}")

    asl, errors = reconstruct_asl_rows(args)
    e6, e6_errors = e6_rows(args, vocab)
    replay, replay_errors = protected_replay_rows(args, vocab)
    rows = asl + e6 + replay
    errors.extend(e6_errors)
    errors.extend(replay_errors)
    errors.extend(audit_rows(rows))

    args.output.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output / "canonical_manifest.csv", rows)
    _write_csv(args.output / "protected_replay_manifest.csv", replay)

    role_counts = Counter(str(row["role"]) for row in rows)
    source_counts = Counter(str(row["source_dataset"]) for row in rows)
    training_rows = [row for row in rows if row["training_eligible"] == "true"]
    summary = {
        "experiment": "phase1_full_vocab_manifest_v1",
        "scope": "manifest and preflight only; no extraction, training, export, or Android changes",
        "schema_version": "3.0",
        "feature_contract": [96, 258],
        "vocabulary_classes": len(vocab),
        "verify_hashes": args.verify_hashes,
        "rows": len(rows),
        "training_eligible_rows": len(training_rows),
        "role_counts": dict(sorted(role_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "training_class_count": len({int(row["class_id"]) for row in training_rows}),
        "training_signer_count": len({row["signer_group_id"] for row in training_rows}),
        "protected_replay_rows": len(replay),
        "errors": errors,
        "passed": not errors,
        "next": (
            "assemble versioned Phase 1 tensors and run smoke tests"
            if not errors and args.verify_hashes
            else "rerun with --verify-hashes before tensor assembly"
        ),
    }
    (args.output / "manifest_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = args.output / "canonical_manifest.csv"
    summary_path = args.output / "manifest_summary.json"
    errors: list[str] = []
    if not manifest_path.is_file():
        errors.append(f"missing manifest: {manifest_path}")
        rows: list[dict[str, Any]] = []
    else:
        rows = _read_csv(manifest_path)
        errors.extend(audit_rows(rows))
    if not summary_path.is_file():
        errors.append(f"missing summary: {summary_path}")
        prepared: dict[str, Any] = {}
    else:
        prepared = json.loads(summary_path.read_text(encoding="utf-8"))
    if prepared and not prepared.get("verify_hashes", False):
        errors.append("manifest was prepared without full raw-video hash verification")
    result = {
        "run_dir": str(args.output.resolve()),
        "rows": len(rows),
        "errors": errors,
        "passed": not errors,
    }
    (args.output / "check_report.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "check"):
        child = sub.add_parser(command)
        child.add_argument("--features-config", type=Path, default=DEFAULT_CONFIG)
        child.add_argument("--vocab", type=Path, default=DEFAULT_VOCAB)
        child.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
        child.add_argument("--asl-splits", type=Path, default=DEFAULT_ASL_SPLITS)
        child.add_argument("--asl-videos", type=Path, default=DEFAULT_ASL_VIDEOS)
        child.add_argument("--e6-run", type=Path, default=DEFAULT_E6_RUN)
        child.add_argument("--eligibility-manifest", type=Path, default=DEFAULT_ELIGIBILITY)
        child.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
        child.add_argument("--verify-hashes", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = prepare(args) if args.command == "prepare" else check(args)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
