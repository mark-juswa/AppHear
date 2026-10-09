"""Transactional preparation I/O; preserve interrupted uncommitted files for audit."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def recover_partial(output: Path, paths: list[Path], reason: str) -> None:
    existing = [p for p in paths if p.exists()]
    if not existing:
        return
    root = output.resolve()
    for path in existing:
        path.resolve().relative_to(root)
        if not path.is_file():
            raise ValueError("[fingerspelling/recovery] Expected a staging file, not a directory")
    folder = output / "recovery" / str(time.time_ns())
    folder.mkdir(parents=True)
    records = []
    for path in existing:
        destination = folder / path.name
        destination.resolve().relative_to(root)
        path.replace(destination)
        records.append({"original": str(path), "preserved": str(destination)})
    (folder / "recovery.json").write_text(
        json.dumps({"reason": reason, "files": records}, indent=2) + "\n"
    )


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".pending")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
