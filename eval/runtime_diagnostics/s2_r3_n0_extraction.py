"""Complete-source Candidate01 raw-v1 extraction for the N0 (no visible hands) negative clips.

Uses the frozen S2-R3 data split for roles, the pinned Candidate01 assets, and the same video
decoding / raw construction as S2-R2 preparation (byte-exact re-extraction was verified in the
readiness review). Every frame of each clip is processed, so later stitching can select any
cadence view. The 1-FPS human hand-presence review is carried as an exclusion sidecar: samples
marked visible-hand contamination or quarantined are excluded from non-sign scoring windows.
Outputs go to a new artifact directory; existing artifacts are never modified.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics import s2_r2_continuous_domain_correction as r2  # noqa: E402
from eval.runtime_diagnostics.s2_r3_context_suite import read_json, sha256, write_json  # noqa: E402
from eval.runtime_diagnostics.s2_r3_data_split import FREEZE_PATH as SPLIT_PATH  # noqa: E402
from pipeline.perception_vnext.offline_candidate01 import Candidate01Offline  # noqa: E402
from pipeline.perception_vnext.recognition_schema import (  # noqa: E402
    load_raw_sequence,
    save_raw_sequence,
)

OUT_RELATIVE = Path(
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/s2_r3_n0_raw_01"
)
REVIEW_RELATIVE = Path("artifacts/recognition_upgrade/e2e_c0/n0_capture_06/reviewed_manifest.csv")
ASSETS = ROOT / "android/app/src/main/assets/perception_vnext"


def exclusions(review_path: Path) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    with review_path.open(encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["eligible"] != "true":
                result.setdefault(row["clip_id"], []).append(
                    {"timestamp_ms": float(row["timestamp_ms"]), "reason": row["exclusion_reason"]}
                )
    return result


def extract(root: Path, roles: set[str]) -> dict[str, Any]:
    split = read_json(SPLIT_PATH)
    out = root / OUT_RELATIVE
    out.mkdir(parents=True, exist_ok=True)
    excluded = exclusions(root / REVIEW_RELATIVE)
    runtime = Candidate01Offline(
        ASSETS / "dwpose_t_singlepass.onnx", ASSETS / "hand_landmarks_detector.tflite"
    )
    rows = []
    try:
        for clip in split["n0_negatives"]:
            if clip["role"] not in roles:
                continue
            video = Path(clip["video_path"])
            if sha256(video) != clip["video_sha256"]:
                raise ValueError(f"[s2_r3/n0] VIDEO_HASH_MISMATCH:{clip['clip_id']}")
            target = out / f"{clip['clip_id']}.npz"
            if target.exists():
                raw = load_raw_sequence(target)
            else:
                timestamps, _, orientation = r2._video_timestamps(video)
                indices = np.arange(len(timestamps), dtype=np.int32)
                records = r2._process_video_indices(
                    runtime, video, indices, timestamps, orientation
                )
                raw = r2._raw_from_records(
                    f"n0:{clip['clip_id']}", "E2E_C0_N0", clip["participant"], records
                )
                save_raw_sequence(target, raw)
            rows.append(
                {
                    **{
                        key: clip[key]
                        for key in ("clip_id", "participant", "device", "environment", "role")
                    },
                    "raw_path": str(target.relative_to(root)).replace("\\", "/"),
                    "raw_sha256": sha256(target),
                    "observations": int(len(raw.timestamp_ms)),
                    "duration_ms": float(raw.timestamp_ms[-1] - raw.timestamp_ms[0]),
                    "accepted_hand_fraction": float(np.mean(np.any(raw.hand_observed, axis=1))),
                    "excluded_review_samples": excluded.get(clip["clip_id"], []),
                }
            )
            print(
                f"[s2_r3/n0] {clip['clip_id']} {clip['role']} obs={rows[-1]['observations']}",
                flush=True,
            )
    finally:
        runtime.close()
    return {
        "schema": "apphear.s2_r3.n0_raw_manifest.v1",
        "split_sha256": sha256(SPLIT_PATH),
        "candidate01_assets_sha256": {
            name: sha256(ASSETS / name)
            for name in ("dwpose_t_singlepass.onnx", "hand_landmarks_detector.tflite")
        },
        "exclusion_rule": (
            "score as non-sign only observations farther than 1000 ms from any excluded "
            "1-FPS review sample"
        ),
        "clips": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--roles", nargs="+", default=["HELD_OUT_EVAL", "FIT", "CAL"])
    args = parser.parse_args()
    manifest = extract(args.evidence_root, set(args.roles))
    write_json(args.evidence_root / OUT_RELATIVE / "manifest.json", manifest, overwrite=True)
    print(json.dumps({"clips": len(manifest["clips"])}, indent=2))


if __name__ == "__main__":
    main()
