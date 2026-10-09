"""Finalize the bounded RU-D5 Sem-Lex repair candidate.

This module handles only the already-extracted final COME replacement batch,
freezes the exact-target external pool, and appends that pool to the immutable
RU-D3 cleanup dataset.  It does not scan Sem-Lex archives or train a model.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.extract.schema import ClipLandmarks
from pipeline.features.config import load_config as load_feature_config
from pipeline.features.contract import SCHEMA_VERSION, clip_features_realtimed
from pipeline.normalize.config import load_config as load_normalize_config
from pipeline.splits.ru_d3_repair_candidate import (
    FEATURE_CONFIG,
    NORMALIZE_CONFIG,
    _coverage,
    _extract_one,
    _init_worker,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = ROOT / "artifacts/recognition_upgrade/ru_d5/semlex_candidate_01"
DEFAULT_RU_D3 = ROOT / "artifacts/recognition_upgrade/ru_d3/repair_candidate_01/dataset"
TARGETS = {"KNOW", "WHO", "WE", "COME", "LEAVE"}
REPLACEMENT_VISUAL = {
    "40NUoGm2C3kglAnw1Mcw": "clear one-hand inward arc toward torso",
    "0m47KrzJpXjObEsBMXS6": "clear one-hand inward/downward path toward torso",
    "qSNUBz6BrfogcpPCdKFB": "clear one-hand inward arc toward torso",
    "DGfGoi7GtNAe1i2FkC8u": "one-hand inward/downward COME path; low framing remains quality-gated",
    "mV7NXGseruwyLLVM5JeS": "clear one-hand movement from front toward torso",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    fields = sorted({key for row in rows for key in row})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _array_sha256(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest().upper()


def extract_replacements(args: argparse.Namespace) -> dict[str, Any]:
    replacement = args.run / "replacement"
    manifest = _read_csv(replacement / "replacement_extraction_manifest.csv")
    out = replacement / "apphear_extraction"
    visual_rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    _init_worker()
    for index, row in enumerate(manifest):
        video_id = row["source_video_id"]
        if video_id not in REPLACEMENT_VISUAL:
            raise ValueError(f"replacement lacks bounded visual decision: {video_id}")
        visual_rows.append(
            {
                **row,
                "visual_decision": "EXACT_TARGET",
                "expected_variant": "COME_INWARD_TO_TORSO_V1",
                "visual_reason": REPLACEMENT_VISUAL[video_id],
                "reviewer": "Codex bounded filmstrip review 2026-08-14",
            }
        )
        payload = {
            "sample_id": row["candidate_id"],
            "canonical_gloss": "COME",
            "review_index": str(index),
            "source_dataset": "semlex_train",
            "signer_group_id": row["source_signer_id"],
            "raw_video_path": row["raw_video_path"],
            "raw_video_sha256": row["raw_video_sha256"],
            "output": str(out.resolve()),
        }
        result = _extract_one(payload)
        result.update(
            {
                "source_video_id": video_id,
                "source_metadata_row_id": row["metadata_row_id"],
                "source_label_type": row["source_label_type"],
                "visual_decision": "EXACT_TARGET",
                "variant_id": "COME_INWARD_TO_TORSO_V1",
                "span_source": (
                    "AUTO_D1_D2"
                    if result.get("automatic_recovery_accepted") is True
                    else "PENDING_MANUAL_OR_REJECT"
                ),
            }
        )
        results.append(result)
        print(
            f"[RU-D5 replacement] {index + 1}/5 {video_id} "
            f"accepted={result.get('automatic_recovery_accepted')} "
            f"reason={result.get('automatic_rejection_reason', '')}",
            flush=True,
        )
    _write_csv(replacement / "visual_review/replacement_visual_decisions.csv", visual_rows)
    _write_csv(out / "extraction_manifest.csv", results)
    summary = {
        "phase": "RU-D5",
        "stage": "final_come_replacement_apphear_extraction",
        "videos": len(results),
        "visual_exact_target": len(visual_rows),
        "auto_accepted": sum(
            str(row.get("automatic_recovery_accepted")).lower() == "true" for row in results
        ),
        "pending_manual_or_reject": sum(
            str(row.get("automatic_recovery_accepted")).lower() != "true" for row in results
        ),
        "thresholds_changed": False,
        "archive_scans_performed": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "passed": len(results) == 5 and all(row.get("status") == "ok" for row in results),
    }
    _write_json(out / "extraction_summary.json", summary)
    return summary


def _load_feature(path: Path) -> tuple[np.ndarray, np.ndarray, int]:
    with np.load(path, allow_pickle=False) as payload:
        schema = str(np.asarray(payload["schema_version"]).item())
        feature = np.asarray(payload["feature"], dtype=np.float32)
        mask = np.asarray(payload["frame_mask"], dtype=bool)
        length = int(np.asarray(payload["length"]).item())
    if schema != SCHEMA_VERSION or feature.shape != (96, 258):
        raise ValueError(f"invalid feature contract: {path}")
    if int(mask.sum()) != length:
        raise ValueError(f"mask/length mismatch: {path}")
    return feature, mask, length


def apply_manual_boundaries(args: argparse.Namespace) -> dict[str, Any]:
    """Materialize explicitly reviewed replacement spans; never infer them."""
    out = args.run / "replacement/apphear_extraction"
    rows = _read_csv(out / "extraction_manifest.csv")
    decisions = (
        {row["source_video_id"]: row for row in _read_csv(args.decisions)}
        if args.decisions.is_file()
        else {}
    )
    normalize_cfg = load_normalize_config(NORMALIZE_CONFIG)
    feature_cfg = load_feature_config(FEATURE_CONFIG)
    repaired = 0
    for row in rows:
        decision = decisions.get(row["source_video_id"])
        if str(row.get("automatic_recovery_accepted", "")).lower() == "true" and (
            not decision or decision.get("decision") != "MANUAL_VERIFIED_BOUNDARY"
        ):
            row["span_source"] = "AUTO_D1_D2"
            continue
        if not decision or decision.get("decision") != "MANUAL_VERIFIED_BOUNDARY":
            row["final_status"] = (
                decision.get("decision", "REJECT_MEDIAPIPE_DOMAIN_FAILURE")
                if decision
                else "REJECT_MEDIAPIPE_DOMAIN_FAILURE"
            )
            continue
        onset, release = int(decision["onset"]), int(decision["release"])
        clip = ClipLandmarks.load(Path(row["stage_e_path"]))
        if not (0 <= onset <= release < len(clip.hand_score)):
            raise ValueError(f"invalid manual span for {row['source_video_id']}")
        any_rate, two_rate, left_rate, right_rate = _coverage(clip.hand_score, onset, release)
        if any_rate < 0.45:
            row["final_status"] = "REJECT_MEDIAPIPE_DOMAIN_FAILURE"
            row["final_rejection_reason"] = (
                f"manual span any-hand coverage {any_rate:.3f} below unchanged 0.45 gate"
            )
            continue
        feature, mask, length, _ = clip_features_realtimed(
            clip.hands_image,
            clip.pose_image,
            onset,
            release,
            normalize_cfg,
            feature_cfg.streaming_t_max,
        )
        feature_path = out / "manual_verified/per_clip" / f"{row['sample_id']}.npz"
        span_path = out / "manual_verified/spans" / f"{row['sample_id']}.span.json"
        feature_path.parent.mkdir(parents=True, exist_ok=True)
        span_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            feature_path,
            feature=feature,
            frame_mask=mask,
            length=np.asarray(length, np.int32),
            schema_version=np.asarray(SCHEMA_VERSION),
        )
        span_record = {
            "sample_id": row["sample_id"],
            "onset": onset,
            "release": release,
            "span_length": length,
            "span_source": "MANUAL_VERIFIED_BOUNDARY",
            "visual_evidence": decision.get("visual_evidence", "bounded replacement filmstrip"),
            "any_hand_coverage": any_rate,
            "two_hand_coverage": two_rate,
            "left_hand_coverage": left_rate,
            "right_hand_coverage": right_rate,
        }
        span_path.write_text(json.dumps(span_record, indent=2) + "\n", encoding="utf-8")
        row.update(
            {
                "onset": onset,
                "release": release,
                "span_length": length,
                "any_hand_coverage": f"{any_rate:.6f}",
                "two_hand_coverage": f"{two_rate:.6f}",
                "left_hand_coverage": f"{left_rate:.6f}",
                "right_hand_coverage": f"{right_rate:.6f}",
                "feature_path": str(feature_path.resolve()),
                "feature_sha256": _sha256(feature_path),
                "span_path": str(span_path.resolve()),
                "span_sha256": _sha256(span_path),
                "span_source": "MANUAL_VERIFIED_BOUNDARY",
                "final_status": "ACCEPT_EXACT_TARGET",
            }
        )
        repaired += 1
    for row in rows:
        if str(row.get("automatic_recovery_accepted", "")).lower() == "true" and not row.get(
            "final_status"
        ):
            row["final_status"] = "ACCEPT_EXACT_TARGET"
            row["span_source"] = "AUTO_D1_D2"
    _write_csv(out / "final_extraction_manifest.csv", rows)
    summary = {
        "phase": "RU-D5",
        "stage": "final_replacement_boundary_resolution",
        "rows": len(rows),
        "accepted": sum(row.get("final_status") == "ACCEPT_EXACT_TARGET" for row in rows),
        "manual_repaired": repaired,
        "rejected": sum(row.get("final_status") != "ACCEPT_EXACT_TARGET" for row in rows),
        "thresholds_changed": False,
        "passed": len(rows) == 5,
    }
    _write_json(out / "boundary_resolution_summary.json", summary)
    return summary


def _initial_exact_pool(run: Path) -> list[dict[str, Any]]:
    visual = {
        row["candidate_id"]: row
        for row in _read_csv(run / "visual_review/visual_review_manifest.csv")
    }
    extracted = _read_csv(run / "apphear_extraction/extraction_manifest.csv")
    repairs = {
        row["sample_id"]: row
        for row in _read_csv(run / "failure_review/boundary_repairs/boundary_repair_manifest.csv")
    }
    accepted: list[dict[str, Any]] = []
    for row in extracted:
        if row.get("visual_decision") != "EXACT_TARGET":
            continue
        source = visual[row["sample_id"]]
        if row["sample_id"] in repairs:
            repair = repairs[row["sample_id"]]
            accepted.append(
                {
                    **row,
                    **repair,
                    "span_source": "MANUAL_VERIFIED_BOUNDARY",
                    "final_status": "ACCEPT_EXACT_TARGET",
                    "metadata_row_index": source.get("metadata_row_index", ""),
                    "source_label_type": source.get("label_type", ""),
                }
            )
        elif (
            row.get("feature_path")
            and str(row.get("automatic_recovery_accepted", "")).lower() == "true"
        ):
            accepted.append(
                {
                    **row,
                    "span_source": "AUTO_D1_D2",
                    "final_status": "ACCEPT_EXACT_TARGET",
                    "metadata_row_index": source.get("metadata_row_index", ""),
                    "source_label_type": source.get("label_type", ""),
                }
            )
    return accepted


def build_candidate(args: argparse.Namespace) -> dict[str, Any]:
    output = args.run / "candidate_c"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite frozen Candidate C: {output}")
    replacements = _read_csv(
        args.run / "replacement/apphear_extraction/final_extraction_manifest.csv"
    )
    external = _initial_exact_pool(args.run) + [
        row for row in replacements if row.get("final_status") == "ACCEPT_EXACT_TARGET"
    ]
    if not external:
        raise ValueError("final exact-target pool is empty")
    sample_ids = [row["sample_id"] for row in external]
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("duplicate Sem-Lex sample in final pool")
    vocab = json.loads((args.ru_d3 / "vocab.json").read_text(encoding="utf-8"))
    with np.load(args.ru_d3 / "train.npz", allow_pickle=True) as payload:
        base = {key: np.asarray(payload[key]) for key in payload.files}
    base_manifest = _read_csv(args.ru_d3 / "manifests/train.csv")
    if base["sample_ids"].astype(str).tolist() != [row["sample_id"] for row in base_manifest]:
        raise ValueError("RU-D3 manifest/tensor row order mismatch")

    x_extra: list[np.ndarray] = []
    masks_extra: list[np.ndarray] = []
    lengths_extra: list[int] = []
    lineage: list[dict[str, Any]] = []
    for row in sorted(
        external,
        key=lambda item: (
            item["canonical_gloss"],
            item["signer_group_id"],
            item["source_video_id"],
        ),
    ):
        feature_path = Path(row["feature_path"])
        feature, mask, length = _load_feature(feature_path)
        span_path = Path(row["span_path"])
        span = json.loads(span_path.read_text(encoding="utf-8"))
        raw_path = Path(row["raw_video_path"])
        record = {
            "sample_id": row["sample_id"],
            "role": "external_repair_train",
            "split": "train",
            "source_dataset": "SEM_LEX",
            "canonical_gloss": row["canonical_gloss"],
            "class_id": int(vocab[row["canonical_gloss"]]),
            "signer_group_id": row["signer_group_id"],
            "source_video_id": row["source_video_id"],
            "source_metadata_row_id": row.get(
                "source_metadata_row_id", row.get("metadata_row_index", "")
            ),
            "source_label_type": row.get("source_label_type", ""),
            "source_split": "train",
            "raw_video_path": str(raw_path.resolve()),
            "raw_video_sha256": _sha256(raw_path),
            "stage_e_path": row["stage_e_path"],
            "stage_e_sha256": row["stage_e_sha256"],
            "span_path": str(span_path.resolve()),
            "span_sha256": _sha256(span_path),
            "span_source": row["span_source"],
            "onset": int(span["onset"]),
            "release": int(span["release"]),
            "feature_artifact_path": str(feature_path.resolve()),
            "feature_sha256": _sha256(feature_path),
            "feature_length": length,
            "feature_array_sha256": _array_sha256(feature),
            "schema_version": SCHEMA_VERSION,
            "variant_decision": "EXACT_TARGET",
            "variant_id": {
                "KNOW": "KNOW_ONE_HAND_TEMPLE_V1",
                "WHO": "WHO_ONE_HAND_FACE_CHIN_V1",
                "WE": "WE_ONE_HAND_CROSS_UPPER_TORSO_V1",
                "COME": "COME_INWARD_TO_TORSO_V1",
                "LEAVE": "LEAVE_TWO_HAND_OPEN_CLOSE_WITHDRAW_V1",
            }[row["canonical_gloss"]],
            "any_hand_coverage": row.get("any_hand_coverage", ""),
            "two_hand_coverage": row.get("two_hand_coverage", ""),
            "left_hand_coverage": row.get("left_hand_coverage", ""),
            "right_hand_coverage": row.get("right_hand_coverage", ""),
            "acceptance_reason": (
                "exact target; canonical AppHear extraction and unchanged "
                "class-specific landmark gate passed"
            ),
        }
        lineage.append(record)
        x_extra.append(feature)
        masks_extra.append(mask)
        lengths_extra.append(length)

    n_base = len(base["y"])
    x = np.concatenate([base["X"].astype(np.float32), np.stack(x_extra)], axis=0)
    y = np.concatenate(
        [base["y"].astype(np.int32), np.asarray([row["class_id"] for row in lineage], np.int32)]
    )
    masks = np.concatenate([base["frame_mask"].astype(bool), np.stack(masks_extra)], axis=0)
    lengths = np.concatenate(
        [base["lengths"].astype(np.int32), np.asarray(lengths_extra, np.int32)]
    )
    train_manifest = list(base_manifest)
    for offset, row in enumerate(lineage):
        train_manifest.append(
            {
                **row,
                "feature_artifact_path": str((output / "dataset/train.npz").resolve()),
                "feature_row_index": n_base + offset,
                "lineage_status": "ru_d5_semlex_exact_target_appended",
                "training_eligible": "true",
                "notes": "Sem-Lex TRAIN exact-target repair row; current phone signer withheld",
            }
        )
    dataset = output / "dataset"
    dataset.mkdir(parents=True)
    np.savez_compressed(
        dataset / "train.npz",
        X=x,
        y=y,
        frame_mask=masks,
        lengths=lengths,
        participant_ids=np.concatenate(
            [
                base["participant_ids"].astype(str),
                np.asarray([row["signer_group_id"] for row in lineage]),
            ]
        ),
        sample_ids=np.concatenate(
            [base["sample_ids"].astype(str), np.asarray([row["sample_id"] for row in lineage])]
        ),
        source_datasets=np.concatenate(
            [base["source_datasets"].astype(str), np.asarray(["SEM_LEX"] * len(lineage))]
        ),
        raw_video_sha256=np.concatenate(
            [
                base["raw_video_sha256"].astype(str),
                np.asarray([row["raw_video_sha256"] for row in lineage]),
            ]
        ),
        roles=np.concatenate(
            [base["roles"].astype(str), np.asarray(["external_repair_train"] * len(lineage))]
        ),
        schema_version=np.asarray(SCHEMA_VERSION),
    )
    shutil.copy2(args.ru_d3 / "val.npz", dataset / "val.npz")
    shutil.copy2(args.ru_d3 / "vocab.json", dataset / "vocab.json")
    _write_csv(dataset / "manifests/train.csv", train_manifest)
    shutil.copy2(args.ru_d3 / "manifests/val.csv", dataset / "manifests/val.csv")
    _write_csv(output / "final_external_lineage.csv", lineage)

    by_class: dict[str, Any] = {}
    for gloss in sorted(TARGETS):
        rows = [row for row in lineage if row["canonical_gloss"] == gloss]
        before_rows = [row for row in base_manifest if row["canonical_gloss"] == gloss]
        by_class[gloss] = {
            "ru_d3_clips": len(before_rows),
            "added_clips": len(rows),
            "candidate_c_clips": len(before_rows) + len(rows),
            "external_signers": len({row["signer_group_id"] for row in rows}),
            "external_signer_ids": sorted({row["signer_group_id"] for row in rows}),
        }
    unchanged = np.array_equal(x[:n_base], base["X"]) and np.array_equal(y[:n_base], base["y"])
    val_unchanged = _sha256(dataset / "val.npz") == _sha256(args.ru_d3 / "val.npz")
    vocab_unchanged = _sha256(dataset / "vocab.json") == _sha256(args.ru_d3 / "vocab.json")
    errors = []
    if not unchanged:
        errors.append("RU-D3 prefix tensor changed")
    if not val_unchanged:
        errors.append("validation changed")
    if not vocab_unchanged:
        errors.append("vocabulary changed")
    if set(row["canonical_gloss"] for row in lineage) - TARGETS:
        errors.append("unrelated class appended")
    contract = {
        "phase": "RU-D5",
        "candidate": "C_ru_d3_cleanup_plus_semlex_exact_target",
        "schema_version": SCHEMA_VERSION,
        "feature_contract": [96, 258],
        "train": {
            "path": str((dataset / "train.npz").resolve()),
            "sha256": _sha256(dataset / "train.npz"),
            "rows": len(y),
            "ru_d3_prefix_rows": n_base,
            "semlex_rows": len(lineage),
        },
        "validation": {
            "path": str((dataset / "val.npz").resolve()),
            "sha256": _sha256(dataset / "val.npz"),
            "unchanged_from_ru_d3": val_unchanged,
        },
        "vocabulary": {
            "path": str((dataset / "vocab.json").resolve()),
            "sha256": _sha256(dataset / "vocab.json"),
            "classes": len(vocab),
            "unchanged_from_ru_d3": vocab_unchanged,
        },
        "external_policy": "Sem-Lex TRAIN + EXACT_TARGET only; acceptable variants excluded",
        "current_phone_signer_in_training": False,
        "protected_test_materialized": False,
        "training_authorized": False,
        "frozen": not errors,
        "errors": errors,
    }
    _write_json(dataset / "dataset_contract.json", contract)
    report = {
        "phase": "RU-D5",
        "stage": "candidate_c_frozen",
        "ru_d3_rows": n_base,
        "external_rows": len(lineage),
        "candidate_c_rows": len(y),
        "classes": by_class,
        "acceptable_variants_added": 0,
        "unrelated_vocabulary_rows_changed": not unchanged,
        "validation_unchanged": val_unchanged,
        "vocabulary_unchanged": vocab_unchanged,
        "protected_test_accessed": False,
        "errors": errors,
        "passed": not errors,
    }
    _write_json(output / "candidate_c_report.json", report)
    return report


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("extract-replacements", "apply-manual-boundaries", "build-candidate"):
        child = sub.add_parser(name)
        child.add_argument("--run", type=Path, default=DEFAULT_RUN)
        if name == "apply-manual-boundaries":
            child.add_argument(
                "--decisions",
                type=Path,
                default=DEFAULT_RUN
                / "replacement/apphear_extraction/manual_boundary_decisions.csv",
            )
        if name == "build-candidate":
            child.add_argument("--ru-d3", type=Path, default=DEFAULT_RU_D3)
    return root


def main() -> int:
    args = parser().parse_args()
    result = {
        "extract-replacements": extract_replacements,
        "apply-manual-boundaries": apply_manual_boundaries,
        "build-candidate": build_candidate,
    }[args.command](args)
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
