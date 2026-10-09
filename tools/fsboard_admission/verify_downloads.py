"""Verify manually downloaded FSboard originals offline; never decode or infer."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from prepare_manifest import SCHEMA, download_url, sample_id, source_path

CHUNK_BYTES = 1024 * 1024


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors = []
    if manifest.get("schema_version") != SCHEMA:
        errors.append("Manifest schema_version mismatch")
    if manifest.get("dataset") != "googleai/fsboard" or manifest.get("dataset_version") != 13:
        errors.append("Only the pinned googleai/fsboard v13 package is accepted")
    rows = manifest.get("samples")
    if not isinstance(rows, list) or not rows:
        return errors + ["Manifest samples must be a nonempty list"]
    seen: dict[str, set[Any]] = {
        key: set()
        for key in (
            "sample_id",
            "clip_filename",
            "kaggle_relative_path",
            "download_relative_path",
            "official_md5",
            "signer_id",
            "normalized_phrase",
            "full_video_provenance_key",
        )
    }
    for index, row in enumerate(rows, 1):
        prefix = f"Row {index}: "
        if not isinstance(row, dict):
            errors.append(prefix + "Sample must be an object")
            continue
        group = row.get("source_group")
        filename = row.get("clip_filename", "")
        if group not in ("daun_v3", "dmk_v3"):
            errors.append(prefix + "Unexpected source group")
        if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9_]+\.mp4", filename):
            errors.append(prefix + "Invalid filename/path mapping")
        expected = source_path(str(group), str(filename))
        if row.get("official_split") != "train" or row.get("fsboard_version") != 13:
            errors.append(prefix + "Only official TRAIN v13 identities are allowed")
        if (
            row.get("kaggle_relative_path") != expected
            or row.get("download_relative_path") != filename
        ):
            errors.append(prefix + "Relative path does not map to the exact TRAIN filename")
        if row.get("sample_id") != sample_id(expected):
            errors.append(prefix + "Stable sample identity mismatch")
        if row.get("direct_download_url") != download_url(expected):
            errors.append(prefix + "Pinned per-file URL mismatch (URL is not invoked)")
        signer = row.get("signer_id")
        if (
            not isinstance(signer, str)
            or not signer
            or not isinstance(filename, str)
            or not filename.startswith(signer + "_")
        ):
            errors.append(prefix + "Signer/filename linkage mismatch")
        phrase = row.get("phrase")
        if (
            not isinstance(phrase, str)
            or not re.fullmatch(r"[A-Za-z ]+", phrase)
            or not re.search(r"[A-Za-z]", phrase)
        ):
            errors.append(prefix + "Invalid alphabet/space transcript")
        elif row.get("normalized_phrase") != phrase.upper():
            errors.append(prefix + "Transcript normalization mismatch")
        size = row.get("file_size_bytes")
        if type(size) is not int or size <= 0:
            errors.append(prefix + "Missing/invalid expected size")
        if not isinstance(row.get("official_md5"), str) or not re.fullmatch(
            r"[0-9a-f]{32}", row["official_md5"]
        ):
            errors.append(prefix + "Missing/invalid official MD5")
        official = row.get("official_metadata", {})
        if not isinstance(official, dict):
            errors.append(prefix + "Missing official metadata")
            official = {}
        for source_key, manifest_key in (
            ("clipFilename", "clip_filename"),
            ("signerId", "signer_id"),
            ("collectionId", "collection_id"),
            ("phrase", "phrase"),
            ("clipFileSize", "file_size_bytes"),
            ("clipFileMd5", "official_md5"),
            ("fullVideoFilename", "full_video_filename"),
        ):
            if official.get(source_key) != row.get(manifest_key) or row.get(manifest_key) is None:
                errors.append(prefix + f"Official metadata linkage mismatch: {manifest_key}")
        for key, values in seen.items():
            value = row.get(key)
            if not isinstance(value, str) or not value:
                errors.append(prefix + f"Missing identity: {key}")
                continue
            if value in values:
                errors.append(prefix + f"Duplicate selected identity: {key}={value}")
            values.add(value)
        if row.get("selection_index") != index:
            errors.append(prefix + "Selection indices must remain consecutive and ordered")
    summary = manifest.get("summary", {})
    if not isinstance(summary, dict):
        return errors + ["Missing/invalid manifest summary"]
    if summary.get("file_count") != len(rows):
        errors.append("Summary file count mismatch")
    if all(isinstance(r, dict) and type(r.get("file_size_bytes")) is int for r in rows):
        if summary.get("expected_bytes") != sum(r["file_size_bytes"] for r in rows):
            errors.append("Summary expected size mismatch")
    return errors


def check_csv(manifest_path: Path, rows: list[dict[str, Any]]) -> list[str]:
    path = manifest_path.with_suffix(".csv")
    if not path.is_file():
        return [f"Missing companion CSV: {path}"]
    expected = [
        {
            key: "" if value is None else str(value)
            for key, value in row.items()
            if key != "official_metadata"
        }
        for row in rows
    ]
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        actual = list(reader)
        if reader.fieldnames != list(expected[0]):
            return ["CSV columns/order differ from JSON"]
    return [] if actual == expected else ["CSV rows differ from JSON selected identities/metadata"]


def file_hashes(path: Path, sha256: bool) -> dict[str, str]:
    md5 = hashlib.md5(usedforsecurity=False)
    sha = hashlib.sha256() if sha256 else None
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_BYTES):
            md5.update(chunk)
            if sha is not None:
                sha.update(chunk)
    result = {"md5": md5.hexdigest()}
    if sha is not None:
        result["sha256"] = sha.hexdigest()
    return result


def verify(
    manifest_path: Path, videos_dir: Path | None = None, sha256: bool = False
) -> dict[str, Any]:
    content = manifest_path.read_bytes()
    manifest = json.loads(content)
    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be a JSON object")
    errors = validate_manifest(manifest)
    rows = manifest.get("samples", [])
    if not errors:
        errors += check_csv(manifest_path, rows)
    root = (videos_dir or Path(manifest.get("download_destination", "."))).resolve()
    report: dict[str, Any] = {
        "schema_version": "apphear.fsboard.download_integrity.v1",
        "manifest_sha256": hashlib.sha256(content).hexdigest(),
        "videos_directory": root.as_posix(),
        "scope": "FILE_INTEGRITY_ONLY_NOT_TRAINING_ADMISSION; no network/decode/Candidate01",
        "sha256_requested": sha256,
        "errors": errors,
        "files": [],
        "unexpected_files": [],
        "passed": False,
    }
    if errors:
        return report
    expected_paths = {r["download_relative_path"] for r in rows}
    if root.exists():
        extras = sorted(
            p.relative_to(root).as_posix()
            for p in root.rglob("*")
            if p.is_file() and p.relative_to(root).as_posix() not in expected_paths
        )
        report["unexpected_files"] = extras
        if extras:
            errors.append("Unexpected files in dedicated videos directory: " + ", ".join(extras))
    actual_md5: dict[str, str] = {}
    for row in rows:
        path = root / row["download_relative_path"]
        record: dict[str, Any] = {
            "sample_id": row["sample_id"],
            "filename": row["clip_filename"],
            "exists": path.is_file(),
            "expected_bytes": row["file_size_bytes"],
            "expected_md5": row["official_md5"],
            "passed": False,
        }
        report["files"].append(record)
        if not path.is_file():
            errors.append(f'Missing required file: {row["clip_filename"]}')
            continue
        if not path.resolve().is_relative_to(root):
            errors.append(f'Source link escapes videos directory: {row["clip_filename"]}')
            continue
        try:
            record["actual_bytes"] = path.stat().st_size
            record.update(file_hashes(path, sha256))
        except OSError as exc:
            errors.append(f'Cannot read {row["clip_filename"]}: {exc}')
            continue
        record["size_matches"] = record["actual_bytes"] == row["file_size_bytes"]
        record["md5_matches"] = record["md5"] == row["official_md5"]
        if not record["size_matches"]:
            errors.append(f'Size mismatch: {row["clip_filename"]}')
        if not record["md5_matches"]:
            errors.append(f'MD5 mismatch: {row["clip_filename"]}')
        if record["md5"] in actual_md5:
            errors.append(
                f'Duplicate source content: {row["clip_filename"]} and {actual_md5[record["md5"]]}'
            )
        actual_md5[record["md5"]] = row["clip_filename"]
        record["passed"] = record["size_matches"] and record["md5_matches"]
    report["passed"] = not errors
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--videos-dir", type=Path)
    parser.add_argument("--sha256", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = verify(args.manifest, args.videos_dir, args.sha256)
    except (OSError, ValueError, TypeError) as exc:
        print(f"[fsboard/downloads] Invalid/unreadable package: {exc}")
        return 2
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "checked_files": len(report["files"]),
                "errors": report["errors"],
            },
            indent=2,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
