"""Host-side check of the pipelined-pose parity dumps pulled from the device.

PipelinedPoseParityInstrumentedTest writes, per arm, the canonical raw-v1 observation stream
(`<arm>.raw`: little-endian, floats as raw IEEE bits, wall-clock fields excluded) plus
budgets.json / engines.json. This script independently re-reads every dump and requires:
  legacy == serial          (flag off is unchanged; same frames, all fields bit-identical)
  serial[:n-1] == pipelined (pipelined holds back only the trailing flush frame)
  serial == emit            (emit-on-hands emits every frame, the flush frame included)
  X_subset_serial == X      (free-running emit-on-hands vs serial fed exactly its accepted frames)
and reports the first differing field if any. Usage:
  python compare_pipeline_parity.py <pulled dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

FLOATS = (("hand_xy", 84), ("hand_proposal_support", 42), ("hand_presence", 2),
          ("hand_roi_center_side", 6), ("body_xy", 16), ("body_support", 8))
FLAGS = (("hand_joint_valid", 42), ("hand_observed", 2), ("hand_proposal_present", 2),
         ("body_valid", 8), ("body_available", 1))
RECORD = 20 + 4 * sum(n for _, n in FLOATS) + sum(n for _, n in FLAGS)


def records(data: bytes) -> list[dict[str, object]]:
    if len(data) % RECORD:
        raise ValueError(f"dump length {len(data)} is not a multiple of {RECORD}")
    out = []
    for offset in range(0, len(data), RECORD):
        index, ts_bits, width, height = struct.unpack_from("<iQii", data, offset)
        pos = offset + 20
        row: dict[str, object] = {"source_index": index, "timestamp_bits": ts_bits,
                                  "source_size": (width, height)}
        for name, count in FLOATS:
            row[name] = struct.unpack_from(f"<{count}I", data, pos)  # raw bits, NaN-safe
            pos += 4 * count
        for name, count in FLAGS:
            row[name] = tuple(data[pos:pos + count])
            pos += count
        out.append(row)
    return out


def first_difference(a: list[dict], b: list[dict]) -> str | None:
    for i, (x, y) in enumerate(zip(a, b)):
        for key in x:
            if x[key] != y[key]:
                return f"observation {i} field {key}"
    return None


def compare(directory: Path) -> dict:
    dumps = {p.stem: p.read_bytes() for p in sorted(directory.glob("*.raw"))}
    checks, failures = [], []
    pairs = []
    for name in dumps:
        if name.endswith("_subset_serial"):
            if name[: -len("_subset_serial")] in dumps:
                pairs.append((name, name[: -len("_subset_serial")], False))
            continue
        if name.endswith("_serial"):
            stem = name[: -len("_serial")]
            if f"{stem}_legacy" in dumps:
                pairs.append((f"{stem}_legacy", name, False))
            pairs += [(name, other, True) for other in dumps
                      if other.startswith(f"{stem}_pipelined")]
            pairs += [(name, other, False) for other in dumps if other.startswith(f"{stem}_emit")]
    for reference, candidate, holds_back in sorted(pairs):
        ref, cand = records(dumps[reference]), records(dumps[candidate])
        expected = len(ref) - 1 if holds_back else len(ref)
        problem = None
        if len(cand) != expected:
            problem = f"{len(cand)} observations, expected {expected}"
        else:
            problem = first_difference(ref[:expected], cand)
        prefix = dumps[reference][: expected * RECORD]
        checks.append({"reference": reference, "candidate": candidate, "observations": expected,
                       "reference_prefix_sha256": hashlib.sha256(prefix).hexdigest(),
                       "candidate_sha256": hashlib.sha256(dumps[candidate]).hexdigest(),
                       "identical": problem is None, "problem": problem})
        if problem:
            failures.append(f"{candidate} vs {reference}: {problem}")
    return {"schema": "apphear.v3_pipeline_parity_host_check.v1", "record_bytes": RECORD,
            "pairs": checks, "failures": failures, "status": "FAIL" if failures or not checks else "PASS"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = compare(args.directory)
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
