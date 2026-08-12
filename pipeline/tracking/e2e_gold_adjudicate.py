"""Prepare and safely merge a blinded correction pass for E2e hand gold."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from pipeline.tracking.e2e_gold import INDEX_FIELDS, REVIEW_FIELDS
from pipeline.tracking.e2e_gold_review import (
    completion_error,
    load_run,
    save_atomic,
    validate_run,
)

PROVENANCE_NAME = "adjudication_provenance.json"
SELECTOR = "original_visible_hand_count_less_than_2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _reset_for_fresh_review(row: dict[str, str]) -> dict[str, str]:
    correction = dict(row)
    correction.update(
        {
            "review_status": "",
            "visible_hand_count": "",
            "gold_hands_json": "",
            "motion_blur": "",
            "occlusion": "",
            "near_face": "",
            "edge_clipped": "",
            "partial_visibility": "",
            "notes": "",
        }
    )
    return correction


def prepare(
    source_run: Path,
    output_dir: Path,
    sample_ids: list[str] | None = None,
) -> dict[str, Any]:
    source_review = source_run / "gold_review.csv"
    if not source_review.is_file():
        raise FileNotFoundError(source_review)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {output_dir}")

    reviews, index = load_run(source_run)
    errors = validate_run(reviews, index)
    incomplete = [row["sample_id"] for row in reviews if completion_error(row) is not None]
    if errors:
        raise ValueError(f"source review has validation errors: {errors[0]}")
    if incomplete:
        raise ValueError(f"source review is incomplete: {incomplete[0]}")

    if sample_ids:
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("explicit sample IDs contain duplicates")
        by_id = {row["sample_id"]: row for row in reviews}
        missing = [sample_id for sample_id in sample_ids if sample_id not in by_id]
        if missing:
            raise ValueError(f"sample absent from source review: {missing[0]}")
        selected = [by_id[sample_id] for sample_id in sample_ids]
        selector = "explicit_sample_ids"
    else:
        selected = [row for row in reviews if int(row["visible_hand_count"]) < 2]
        selector = SELECTOR
    selected_ids = [row["sample_id"] for row in selected]
    if not selected:
        raise ValueError("no rows satisfy the adjudication selector")

    output_dir.mkdir(parents=True, exist_ok=True)
    corrections = [_reset_for_fresh_review(row) for row in selected]
    index_rows = [index[sample_id] for sample_id in selected_ids]
    _write_csv(output_dir / "gold_review.csv", REVIEW_FIELDS, corrections)
    _write_csv(output_dir / "internal_index.csv", INDEX_FIELDS, index_rows)

    provenance: dict[str, Any] = {
        "schema": "apphear.e2e_gold_adjudication.v1",
        "source_run": str(source_run.resolve()),
        "source_gold_review_sha256": sha256(source_review),
        "selector": selector,
        "selected_rows": len(selected_ids),
        "selected_sample_ids": selected_ids,
        "merge_status": "not_merged",
    }
    (output_dir / PROVENANCE_NAME).write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return provenance


def _load_provenance(adjudication_dir: Path) -> dict[str, Any]:
    path = adjudication_dir / PROVENANCE_NAME
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema") != "apphear.e2e_gold_adjudication.v1":
        raise ValueError(f"invalid adjudication provenance: {path}")
    return value


def merge(source_run: Path, adjudication_dir: Path) -> dict[str, Any]:
    provenance = _load_provenance(adjudication_dir)
    recorded_source = Path(str(provenance["source_run"])).resolve()
    if recorded_source != source_run.resolve():
        raise ValueError(
            f"source run mismatch: expected {recorded_source}, got {source_run.resolve()}"
        )

    source_review = source_run / "gold_review.csv"
    pre_merge_sha = sha256(source_review)
    if pre_merge_sha != provenance["source_gold_review_sha256"]:
        raise ValueError("source gold review changed after adjudication preparation")

    corrections, correction_index = load_run(adjudication_dir)
    errors = validate_run(corrections, correction_index)
    incomplete = [row["sample_id"] for row in corrections if completion_error(row) is not None]
    if errors:
        raise ValueError(f"adjudication has validation errors: {errors[0]}")
    if incomplete:
        raise ValueError(f"adjudication is incomplete: {incomplete[0]}")

    expected_ids = list(provenance["selected_sample_ids"])
    correction_ids = [row["sample_id"] for row in corrections]
    if correction_ids != expected_ids:
        raise ValueError("adjudication sample IDs or ordering changed")

    source_rows, source_index = load_run(source_run)
    source_errors = validate_run(source_rows, source_index)
    if source_errors:
        raise ValueError(f"source review has validation errors: {source_errors[0]}")
    correction_by_id = {row["sample_id"]: row for row in corrections}
    merged_rows = [correction_by_id.get(row["sample_id"], row) for row in source_rows]

    backup = source_run / f"gold_review.pre_{adjudication_dir.name}.csv"
    if backup.exists():
        raise ValueError(f"merge backup already exists: {backup}")
    shutil.copy2(source_review, backup)
    save_atomic(source_review, merged_rows)

    receipt = {
        **provenance,
        "merge_status": "merged",
        "backup_path": str(backup.resolve()),
        "pre_merge_sha256": pre_merge_sha,
        "post_merge_sha256": sha256(source_review),
    }
    (adjudication_dir / "merge_receipt.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare or merge E2e gold adjudication")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--run-dir", type=Path, required=True)
    prepare_parser.add_argument("--output-dir", type=Path, required=True)
    prepare_parser.add_argument("--sample-id", action="append", default=None)
    merge_parser = subparsers.add_parser("merge")
    merge_parser.add_argument("--run-dir", type=Path, required=True)
    merge_parser.add_argument("--adjudication-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.run_dir, args.output_dir, args.sample_id)
        else:
            result = merge(args.run_dir, args.adjudication_dir)
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        print(f"[tracking/e2e-gold-adjudicate] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
