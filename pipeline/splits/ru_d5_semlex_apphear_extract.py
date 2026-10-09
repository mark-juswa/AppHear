"""Run canonical AppHear E -> offline D1/D2 -> Stage-F extraction for RU-D5.

Inputs are limited to clips that passed bounded visual variant review. This is
still a screening stage: it cannot accept training rows or build Candidate C.
The landmark/feature implementation is deliberately reused from RU-D3 so the
schema-v3.0 extraction path is not duplicated for Sem-Lex.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import multiprocessing as mp_process
from collections import Counter
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
VISUALLY_ELIGIBLE = {"EXACT_TARGET", "ACCEPTABLE_VARIANT"}


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


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    review = _read_csv(args.run / "visual_review/visual_review_manifest.csv")
    if any(row["visual_decision"] == "PENDING" for row in review):
        raise ValueError("visual review is incomplete")
    pair_signers = {
        row["source_signer_id"]
        for row in review
        if row["canonical_gloss"] == "WE"
        and row["visual_decision"] in VISUALLY_ELIGIBLE
    } & {
        row["source_signer_id"]
        for row in review
        if row["canonical_gloss"] == "COME"
        and row["visual_decision"] in VISUALLY_ELIGIBLE
    }
    selected: list[dict[str, Any]] = []
    for index, row in enumerate(review):
        if row["visual_decision"] not in VISUALLY_ELIGIBLE:
            continue
        pair_eligible = (
            row["canonical_gloss"] not in {"WE", "COME"}
            or row["source_signer_id"] in pair_signers
        )
        if not pair_eligible:
            initial_pool_status = "EXCLUDED_UNPAIRED_WE_COME"
            variant_gate = "PAIR_INELIGIBLE"
        elif row["visual_decision"] == "EXACT_TARGET":
            initial_pool_status = "ELIGIBLE_AFTER_APPHEAR_AND_BOUNDARY_GATES"
            variant_gate = "PENDING_APPHEAR_QUALITY"
        else:
            initial_pool_status = "EXCLUDED_PROVISIONAL_VARIANT"
            variant_gate = "PROVISIONAL_VARIANT_REVIEW_REQUIRED"
        selected.append(
            {
                "sample_id": row["candidate_id"],
                "canonical_gloss": row["canonical_gloss"],
                "review_index": index,
                "source_dataset": "semlex_train",
                "signer_group_id": row["source_signer_id"],
                "source_video_id": row["source_video_id"],
                "visual_decision": row["visual_decision"],
                "candidate_c_variant_gate": variant_gate,
                "initial_repair_pool_status": initial_pool_status,
                "we_come_pair_eligible": str(pair_eligible).lower(),
                "raw_video_path": row["raw_video_path"],
                "raw_video_sha256": row["raw_video_sha256"],
            }
        )
    output = args.run / "apphear_extraction"
    _write_csv(output / "input_manifest.csv", selected)
    counts = Counter(row["canonical_gloss"] for row in selected)
    summary = {
        "phase": "RU-D5",
        "stage": "semlex_apphear_extraction_prepared",
        "visually_reviewed_rows": len(review),
        "selected_rows": len(selected),
        "selected_by_class": dict(counts),
        "exact_target_rows": sum(
            row["visual_decision"] == "EXACT_TARGET" for row in selected
        ),
        "acceptable_variant_rows": sum(
            row["visual_decision"] == "ACCEPTABLE_VARIANT" for row in selected
        ),
        "acceptable_variant_candidate_c_policy": (
            "PROVISIONAL_ONLY_NOT_AUTOMATICALLY_ELIGIBLE"
        ),
        "initial_exact_target_repair_pool_rows": sum(
            row["initial_repair_pool_status"]
            == "ELIGIBLE_AFTER_APPHEAR_AND_BOUNDARY_GATES"
            for row in selected
        ),
        "we_come_pair_signers": sorted(pair_signers),
        "we_come_pair_ineligible_selected_ids": [
            row["source_video_id"]
            for row in selected
            if row["we_come_pair_eligible"] == "false"
        ],
        "archive_scans_performed": 0,
        "accepted_for_training": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "passed": len(selected) == 34,
    }
    _write_json(output / "prepare_summary.json", summary)
    return summary


def _bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _apply_training_span_policy(
    result: dict[str, Any], source: dict[str, str], output: Path
) -> dict[str, Any]:
    """Preserve D1/D2, with a non-promoting fallback for reviewed isolated clips."""
    merged = {
        **result,
        "source_video_id": source["source_video_id"],
        "visual_decision": source["visual_decision"],
        "candidate_c_variant_gate": source["candidate_c_variant_gate"],
        "initial_repair_pool_status": source["initial_repair_pool_status"],
        "we_come_pair_eligible": source["we_come_pair_eligible"],
    }
    if result.get("status") != "ok":
        merged.update(
            {
                "training_span_available": "false",
                "training_span_method": "EXTRACTION_FAILED",
                "boundary_requires_manual_confirmation": "false",
            }
        )
        return merged
    if _bool(result.get("automatic_recovery_accepted")):
        merged.update(
            {
                "training_span_available": "true",
                "training_span_method": "CANONICAL_OFFLINE_D1_D2",
                "selected_span_path": result.get("span_path", ""),
                "boundary_requires_manual_confirmation": "false",
            }
        )
        return merged

    n_frames = int(result.get("n_frames") or 0)
    if _bool(result.get("span_valid")):
        merged.update(
            {
                "training_span_available": "false",
                "training_span_method": "D1_D2_VALID_LANDMARK_GATE_FAILED",
                "boundary_requires_manual_confirmation": "false",
            }
        )
        return merged
    if not 6 <= n_frames <= 96:
        merged.update(
            {
                "training_span_available": "false",
                "training_span_method": "MANUAL_SPAN_REQUIRED",
                "boundary_requires_manual_confirmation": "true",
            }
        )
        return merged

    clip = ClipLandmarks.load(Path(result["stage_e_path"]))
    normalize_cfg = load_normalize_config(NORMALIZE_CONFIG)
    feature_cfg = load_feature_config(FEATURE_CONFIG)
    onset, release = 0, n_frames - 1
    feature, frame_mask, length, _ = clip_features_realtimed(
        clip.hands_image,
        clip.pose_image,
        onset,
        release,
        normalize_cfg,
        feature_cfg.streaming_t_max,
    )
    sample_id = source["sample_id"]
    feature_path = output / "per_clip_isolated_fallback" / f"{sample_id}.npz"
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        feature_path,
        feature=feature,
        frame_mask=frame_mask,
        length=np.asarray(length, dtype=np.int32),
        schema_version=np.asarray(SCHEMA_VERSION),
    )
    any_rate, two_rate, left_rate, right_rate = _coverage(
        clip.hand_score, onset, release
    )
    span_record = {
        "method": "reviewed_isolated_full_clip_fallback_v1",
        "status": "PROVISIONAL_MANUAL_BOUNDARY_CONFIRMATION_REQUIRED",
        "sample_id": sample_id,
        "visual_decision": source["visual_decision"],
        "onset": onset,
        "release": release,
        "span_length": n_frames,
        "any_hand_coverage": any_rate,
        "two_hand_coverage": two_rate,
        "left_hand_coverage": left_rate,
        "right_hand_coverage": right_rate,
        "d1_d2_failure_reason": result.get("automatic_rejection_reason", ""),
    }
    span_path = output / "spans_isolated_fallback" / f"{sample_id}.span.json"
    span_path.parent.mkdir(parents=True, exist_ok=True)
    span_path.write_text(json.dumps(span_record, indent=2) + "\n", encoding="utf-8")
    merged.update(
        {
            "training_span_available": "true",
            "training_span_method": "REVIEWED_ISOLATED_FULL_CLIP_FALLBACK_V1",
            "selected_span_path": str(span_path.resolve()),
            "selected_span_sha256": _sha256(span_path),
            "feature_path": str(feature_path.resolve()),
            "feature_sha256": _sha256(feature_path),
            "boundary_requires_manual_confirmation": "true",
            "fallback_any_hand_coverage": f"{any_rate:.6f}",
            "fallback_two_hand_coverage": f"{two_rate:.6f}",
        }
    )
    return merged


def extract(args: argparse.Namespace) -> dict[str, Any]:
    output = args.run / "apphear_extraction"
    selected = _read_csv(output / "input_manifest.csv")
    selected_by_id = {row["sample_id"]: row for row in selected}
    existing_path = output / "extraction_manifest.csv"
    existing = (
        {row["sample_id"]: row for row in _read_csv(existing_path)}
        if existing_path.is_file()
        else {}
    )
    todo = [
        dict(row, output=str(output.resolve()))
        for row in selected
        if row["sample_id"] not in existing
    ]
    results = list(existing.values())
    pool = None
    if todo:
        if args.workers <= 1:
            _init_worker()
            iterator = map(_extract_one, todo)
        else:
            context = mp_process.get_context("spawn")
            pool = context.Pool(processes=args.workers, initializer=_init_worker)
            iterator = pool.imap_unordered(_extract_one, todo, chunksize=1)
        try:
            for index, result in enumerate(iterator, start=1):
                result = _apply_training_span_policy(
                    result, selected_by_id[result["sample_id"]], output
                )
                results.append(result)
                results.sort(key=lambda row: int(row["review_index"]))
                _write_csv(existing_path, results)
                print(
                    f"[ru-d5-apphear] processed {index}/{len(todo)} "
                    f"{result.get('canonical_gloss', '')} "
                    f"{result.get('sample_id', '')} status={result.get('status', '')}",
                    flush=True,
                )
        finally:
            if pool is not None:
                pool.close()
                pool.join()
    refreshed: list[dict[str, Any]] = []
    for row in results:
        source = selected_by_id[row["sample_id"]]
        if "training_span_method" not in row:
            row = _apply_training_span_policy(row, source, output)
        else:
            row.update(
                {
                    "source_video_id": source["source_video_id"],
                    "visual_decision": source["visual_decision"],
                    "candidate_c_variant_gate": source["candidate_c_variant_gate"],
                    "initial_repair_pool_status": source[
                        "initial_repair_pool_status"
                    ],
                    "we_come_pair_eligible": source["we_come_pair_eligible"],
                }
            )
        refreshed.append(row)
    results = refreshed
    results.sort(key=lambda row: int(row["review_index"]))
    _write_csv(existing_path, results)
    summary = {
        "phase": "RU-D5",
        "stage": "semlex_apphear_extraction_completed",
        "selected": len(selected),
        "previously_complete": len(existing),
        "processed_now": len(todo),
        "status_counts": dict(Counter(row.get("status", "") for row in results)),
        "s4_feature_counts": dict(
            Counter("AVAILABLE" if row.get("feature_path") else "UNAVAILABLE" for row in results)
        ),
        "training_span_methods": dict(
            Counter(row.get("training_span_method", "") for row in results)
        ),
        "manual_boundary_confirmation_required": sum(
            _bool(row.get("boundary_requires_manual_confirmation"))
            for row in results
        ),
        "acceptable_variants_promoted": 0,
        "archive_scans_performed": 0,
        "accepted_for_training": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "passed": len(results) == len(selected)
        and all(row.get("status") == "ok" for row in results),
    }
    _write_json(output / "extraction_summary.json", summary)
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    output = args.run / "apphear_extraction"
    inputs = _read_csv(output / "input_manifest.csv")
    errors: list[str] = []
    if len(inputs) != 34:
        errors.append(f"expected 34 visually eligible rows, found {len(inputs)}")
    if any(row["visual_decision"] not in VISUALLY_ELIGIBLE for row in inputs):
        errors.append("visually rejected row leaked into extraction input")
    extraction_path = output / "extraction_manifest.csv"
    if args.require_complete:
        if not extraction_path.is_file():
            errors.append("extraction manifest is missing")
        else:
            rows = _read_csv(extraction_path)
            if len(rows) != len(inputs):
                errors.append("extraction row count mismatch")
            for row in rows:
                if row.get("status") != "ok":
                    errors.append(f"extraction failed: {row.get('sample_id', '')}")
                    continue
                for path_key, hash_key in (
                    ("stage_e_path", "stage_e_sha256"),
                    ("span_path", "span_sha256"),
                ):
                    path = Path(row[path_key])
                    if not path.is_file() or _sha256(path) != row[hash_key]:
                        errors.append(f"invalid extracted artifact: {path}")
                if row.get("feature_path"):
                    feature_path = Path(row["feature_path"])
                    if not feature_path.is_file() or _sha256(feature_path) != row["feature_sha256"]:
                        errors.append(f"invalid S4 feature artifact: {feature_path}")
                    else:
                        with np.load(feature_path, allow_pickle=False) as payload:
                            if payload["feature"].shape != (96, 258):
                                errors.append(f"wrong S4 shape: {feature_path}")
                            if str(payload["schema_version"]) != SCHEMA_VERSION:
                                errors.append(f"wrong schema version: {feature_path}")
                if row.get("visual_decision") == "ACCEPTABLE_VARIANT" and row.get(
                    "candidate_c_variant_gate"
                ) not in {
                    "PROVISIONAL_VARIANT_REVIEW_REQUIRED",
                    "PAIR_INELIGIBLE",
                }:
                    errors.append(
                        "acceptable variant lost provisional gate: "
                        f"{row.get('sample_id', '')}"
                    )
    result = {
        "phase": "RU-D5",
        "stage": "semlex_apphear_extraction_check",
        "selected_rows": len(inputs),
        "require_complete": args.require_complete,
        "errors": errors,
        "accepted_for_training": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "passed": not errors,
    }
    _write_json(output / "check_summary.json", result)
    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("prepare", "extract", "check"):
        child = sub.add_parser(name)
        child.add_argument("--run", type=Path, default=DEFAULT_RUN)
        if name == "extract":
            child.add_argument("--workers", type=int, default=2)
        if name == "check":
            child.add_argument("--require-complete", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    result = {"prepare": prepare, "extract": extract, "check": check}[args.command](args)
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
