"""Synthetic byte fixtures for offline integrity; no videos/models/network."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/fsboard_admission"))
from prepare_manifest import SCHEMA, download_url, sample_id, source_path  # noqa: E402
from verify_downloads import validate_manifest, verify  # noqa: E402


class DownloadIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.videos = self.root / "videos"
        self.videos.mkdir()
        self.path = self.root / "manifest.json"
        self.payloads = [b"synthetic first source bytes", b"synthetic second source bytes"]
        rows = []
        for index, payload in enumerate(self.payloads, 1):
            signer = f"test{index}"
            filename = f"{signer}_0_20260101_000000_0_1000.mp4"
            relative = source_path("daun_v3", filename)
            md5 = hashlib.md5(payload, usedforsecurity=False).hexdigest()
            row = {
                "selection_index": index,
                "sample_id": sample_id(relative),
                "source_group": "daun_v3",
                "official_split": "train",
                "fsboard_version": 13,
                "signer_id": signer,
                "clip_filename": filename,
                "kaggle_relative_path": relative,
                "download_relative_path": filename,
                "direct_download_url": download_url(relative),
                "phrase": f"synthetic {'first' if index == 1 else 'second'}",
                "normalized_phrase": f"SYNTHETIC {'FIRST' if index == 1 else 'SECOND'}",
                "file_size_bytes": len(payload),
                "official_md5": md5,
                "collection_id": "synthetic_not_real_data",
                "full_video_filename": filename,
                "full_video_provenance_key": f"fixture:{filename}",
            }
            row["official_metadata"] = {
                "clipFilename": filename,
                "signerId": signer,
                "collectionId": row["collection_id"],
                "phrase": row["phrase"],
                "clipFileSize": len(payload),
                "clipFileMd5": md5,
                "fullVideoFilename": filename,
            }
            rows.append(row)
            (self.videos / filename).write_bytes(payload)
        self.manifest: dict[str, Any] = {
            "schema_version": SCHEMA,
            "dataset": "googleai/fsboard",
            "dataset_version": 13,
            "download_destination": str(self.videos),
            "samples": rows,
            "summary": {"file_count": 2, "expected_bytes": sum(map(len, self.payloads))},
        }
        self.save()

    def save(self) -> None:
        self.path.write_text(json.dumps(self.manifest), encoding="utf-8")
        rows = self.manifest["samples"]
        fields = [key for key in rows[0] if key != "official_metadata"]
        with self.path.with_suffix(".csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows({k: row[k] for k in fields} for row in rows)

    def test_valid_bytes_and_sha256(self) -> None:
        result = verify(self.path, sha256=True)
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual(result["files"][0]["sha256"], hashlib.sha256(self.payloads[0]).hexdigest())

    def test_missing_and_renamed_file(self) -> None:
        row = self.manifest["samples"][0]
        (self.videos / row["clip_filename"]).rename(self.videos / "renamed.mp4")
        result = verify(self.path)
        self.assertFalse(result["passed"])
        self.assertTrue(any("Missing required" in e for e in result["errors"]))
        self.assertIn("renamed.mp4", result["unexpected_files"])

    def test_size_and_md5_mismatch(self) -> None:
        (self.videos / self.manifest["samples"][0]["clip_filename"]).write_bytes(b"broken")
        result = verify(self.path)
        self.assertTrue(any("Size mismatch" in e for e in result["errors"]))
        self.assertTrue(any("MD5 mismatch" in e for e in result["errors"]))

    def test_same_size_wrong_content(self) -> None:
        (self.videos / self.manifest["samples"][0]["clip_filename"]).write_bytes(
            b"x" * len(self.payloads[0])
        )
        result = verify(self.path)
        self.assertTrue(result["files"][0]["size_matches"])
        self.assertFalse(result["passed"])

    def test_duplicate_source_content(self) -> None:
        (self.videos / self.manifest["samples"][1]["clip_filename"]).write_bytes(self.payloads[0])
        self.assertTrue(any("Duplicate source content" in e for e in verify(self.path)["errors"]))

    def test_unexpected_nested_file(self) -> None:
        (self.videos / "nested").mkdir()
        (self.videos / "nested" / "extra.mp4").write_bytes(b"extra")
        self.assertIn("nested/extra.mp4", verify(self.path)["unexpected_files"])

    def test_json_csv_disagreement(self) -> None:
        self.path.with_suffix(".csv").write_text("incorrect,csv\n", encoding="utf-8")
        self.assertFalse(verify(self.path)["passed"])

    def test_invalid_schema_role_mapping_and_hash(self) -> None:
        for change in ("schema", "role", "path", "md5", "sample"):
            altered = copy.deepcopy(self.manifest)
            if change == "schema":
                altered["schema_version"] = "wrong"
            elif change == "role":
                altered["samples"][0]["official_split"] = "test"
            elif change == "path":
                altered["samples"][0]["download_relative_path"] = "../escape.mp4"
            elif change == "md5":
                altered["samples"][0]["official_md5"] = None
            else:
                altered["samples"][0]["sample_id"] = "wrong"
            with self.subTest(change=change):
                self.assertTrue(validate_manifest(altered))

    def test_duplicate_selected_identity(self) -> None:
        altered = copy.deepcopy(self.manifest)
        altered["samples"].append(altered["samples"][0])
        self.assertTrue(any("Duplicate selected identity" in e for e in validate_manifest(altered)))

    def test_missing_signer_and_metadata(self) -> None:
        altered = copy.deepcopy(self.manifest)
        altered["samples"][0]["signer_id"] = None
        altered["samples"][0]["official_metadata"] = None
        self.assertTrue(validate_manifest(altered))


if __name__ == "__main__":
    unittest.main()
