"""Explicit managed external package paths; legacy repository-relative paths stay valid."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.sequence_manifest import REPO

SCHEMA = "apphear.fingerspelling.external_storage.v1"
MARKER = "storage.json"


def declaration(output: Path) -> dict[str, Any] | None:
    marker = output / MARKER
    if not marker.is_file():
        return None
    value: dict[str, Any] = json.loads(marker.read_text(encoding="utf-8"))
    if (
        value["schema_version"] != SCHEMA
        or Path(value["package_root"]).resolve() != output.resolve()
        or value["manifest_sha256"] != sha256(output / "tranche_manifest.json")
        or value["path_convention"] != "ABSOLUTE_MANAGED_PACKAGE_V1"
    ):
        raise ValueError("[fingerspelling/storage] Storage declaration mismatch")
    return value


def checked_path(path: Path, output: Path | None = None) -> Path:
    resolved = path.resolve()
    if resolved.is_relative_to(REPO):
        return resolved
    if output is not None and declaration(output) is not None:
        if resolved.is_relative_to(output.resolve()):
            return resolved
    raise ValueError("[fingerspelling/storage] Path outside declared package/repository")


def relative(path: Path, output: Path | None = None) -> str:
    resolved = checked_path(path, output)
    if resolved.is_relative_to(REPO):
        return resolved.relative_to(REPO).as_posix()
    return resolved.as_posix()


def receipt_identity(output: Path) -> dict[str, str]:
    if declaration(output) is None:
        return {}
    return {"storage_schema": SCHEMA, "storage_marker_sha256": sha256(output / MARKER)}
