"""Compare two P5-D7 extraction roots without modifying either output."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def records(root: Path) -> dict[str, dict]:
    return {
        value["sample_id"]: value
        for path in (root / "completed").glob("*.json")
        for value in [json.loads(path.read_text(encoding="utf-8"))]
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    reference_root, candidate_root = Path(args.reference), Path(args.candidate)
    reference, candidate = records(reference_root), records(candidate_root)
    if set(reference) != set(candidate):
        raise RuntimeError("sample sets differ")
    output = []
    passed = True
    for sample_id in sorted(reference):
        a, b = reference[sample_id], candidate[sample_id]
        with np.load(reference_root / a["native_relative_path"], allow_pickle=False) as na, np.load(candidate_root / b["native_relative_path"], allow_pickle=False) as nb:
            xy_delta = float(np.max(np.abs(na["keypoints_xy"] - nb["keypoints_xy"])))
            score_delta = float(np.max(np.abs(na["scores"] - nb["scores"])))
            native_exact = bool(np.array_equal(na["keypoints_xy"], nb["keypoints_xy"]) and np.array_equal(na["scores"], nb["scores"]))
        with np.load(reference_root / a["v2_relative_path"], allow_pickle=False) as va, np.load(candidate_root / b["v2_relative_path"], allow_pickle=False) as vb:
            v2_delta = float(np.max(np.abs(va["features"] - vb["features"])))
            v2_exact = bool(np.array_equal(va["features"], vb["features"]) and np.array_equal(va["frame_mask"], vb["frame_mask"]))
        within_tolerance = xy_delta <= 1e-5 and score_delta <= 1e-6 and v2_delta <= 1e-6
        passed = passed and within_tolerance
        output.append({"sample_id": sample_id, "native_exact": native_exact, "v2_exact": v2_exact,
                       "max_xy_delta": xy_delta, "max_score_delta": score_delta,
                       "max_v2_delta": v2_delta, "within_frozen_tolerance": within_tolerance,
                       "reference_seconds": a["elapsed_seconds"], "candidate_seconds": b["elapsed_seconds"],
                       "speedup": a["elapsed_seconds"] / b["elapsed_seconds"]})
    result = {"passed": passed, "samples": output,
              "aggregate_speedup": sum(x["reference_seconds"] for x in output) / sum(x["candidate_seconds"] for x in output)}
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
