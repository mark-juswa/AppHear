"""Generate decoder-only Python references from all saved governed DEV logits."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import BinaryIO

import numpy as np

from model.fingerspelling_prefix_beam import decode_beam, decode_greedy
from pipeline.fingerspelling.adapter import sha256
from tools.fingerspelling.decoder_audit import load_logits

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "artifacts/fingerspelling_android_beam_01"
SCHEMA = "apphear.fingerspelling.beam_fixture.v1"


def text(output: BinaryIO, value: str) -> None:
    # All fixture identifiers/vocabulary strings are ASCII, identical to Java UTF.
    data = value.encode("ascii")
    output.write(struct.pack(">H", len(data)))
    output.write(data)


def peaked(tokens: list[int]) -> np.ndarray:
    logits = np.full((len(tokens), 28), -30, np.float32)
    for t, symbol in enumerate(tokens):
        logits[t, symbol] = 30
    return logits


def main() -> None:
    OUT.mkdir(exist_ok=True)
    rows = [
        ("ordinary_AMY", "synthetic", peaked([0, 12, 24])),
        ("repeated_BELLA", "synthetic", peaked([1, 4, 11, 27, 11, 0])),
        ("consecutive_duplicate", "synthetic", peaked([11, 11, 11])),
        ("blank_separated_duplicate", "synthetic", peaked([11, 27, 11])),
        ("literal_SPACE", "synthetic", peaked([0, 26, 1])),
        ("empty", "synthetic", np.empty((0, 28), np.float32)),
        ("all_blank", "synthetic", peaked([27] * 16)),
        ("long_512", "synthetic", peaked([0, 27, 1, 27] * 128)),
        ("equal_symbol_tie", "synthetic", np.zeros((1, 28), np.float32)),
        ("blank_penalty_tie", "synthetic", np.array([[0] + [-30] * 26 + [0.5]], np.float32)),
    ]
    marginal = np.full((2, 28), -50, np.float32)
    marginal[:, 0] = np.log(0.4)
    marginal[:, 27] = np.log(0.6) + 0.5
    rows.append(("alignment_mass_beats_greedy", "synthetic", marginal))
    archives = {}
    audit = REPO / "artifacts/fingerspelling_decoder_audit_01"
    for view in ["native", "phone"]:
        path = audit / f"{view}_logits.npz"
        receipt = json.loads(path.with_suffix(".receipt.json").read_text())
        loaded = load_logits(path, receipt["identity"])
        if len(loaded) != 256:
            raise ValueError("[android/beam] Full governed DEV view required")
        rows.extend((r["sample_id"] + "/" + view, view, r["logits"]) for r in loaded)
        archives[view] = sha256(path)
    records = []
    path = OUT / "beam_fixtures.bin"
    with path.open("wb") as output:
        text(output, SCHEMA)
        output.write(struct.pack(">ifi", 10, 0.5, len(rows)))
        for name, view, logits in rows:
            beam = decode_beam(logits, 0.5, 10, 5)[0]
            greedy = decode_greedy(logits, 0.5)
            text(output, name)
            text(output, view)
            output.write(struct.pack(">i", len(logits)))
            output.write(logits.astype(">f4").tobytes())
            text(output, beam["prediction"])
            text(output, greedy)
            output.write(struct.pack(">d", beam["log_ctc_mass_pruned"]))
            records.append(
                {
                    "id": name,
                    "view": view,
                    "timesteps": len(logits),
                    "expected_beam": beam["prediction"],
                    "expected_greedy": greedy,
                    "beam_differs": beam["prediction"] != greedy,
                }
            )
    report = {
        "schema_version": SCHEMA,
        "fixture_count": len(rows),
        "synthetic_cases": 11,
        "governed_dev_views": 512,
        "beam_width": 10,
        "blank_penalty": 0.5,
        "file_sha256": sha256(path),
        "archive_sha256": archives,
        "rows": records,
        "training": False,
        "test_accessed": False,
    }
    (OUT / "fixture_manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
