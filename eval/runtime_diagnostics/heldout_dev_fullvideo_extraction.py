"""Full-length Candidate01 raw-v1 for the 816 signer-disjoint recognizer DEV clips.

The recognizer DEV raw is cut to the governed onset/release span, so no runtime segmenter can be
measured on it. This extracts every frame of each original video (hash-verified against the frozen
DEV manifest; the archive now lives on I: instead of the historical F:/G: path) with the pinned
Android Candidate01 assets, and records the governed span as frame/observation indices. The five DEV
signers are absent from every S2 FIT/CAL source and from recognizer TRAIN. Outputs go to a new
artifact directory; nothing existing is modified. Protected TEST is never read.
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
from eval.runtime_diagnostics.s2_r3_context_suite import sha256, write_json  # noqa: E402
from pipeline.perception_vnext.offline_candidate01 import Candidate01Offline  # noqa: E402
from pipeline.perception_vnext.recognition_schema import (  # noqa: E402
    load_raw_sequence,
    save_raw_sequence,
)

DEV_MANIFEST = Path("artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1/manifests/val.csv")
OUT_RELATIVE = Path(
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/heldout_dev_fullvideo_raw_01"
)
VIDEO_ROOT = Path(r"I:\ASL CITIZEN\ASL CITIZEN\ASL_Citizen\videos")
SPAN_ROOT = Path(r"F:\ASL DATASET\ASL CITIZEN\derived\apphear3\spans\val")
ASSETS = ROOT / "android/app/src/main/assets/perception_vnext"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.evidence_root
    out = root / OUT_RELATIVE
    out.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader((root / DEV_MANIFEST).open(encoding="utf-8")))
    if len(rows) != 816 or any(r["split"] != "val" for r in rows):
        raise ValueError("[heldout_dev] DEV_POPULATION")
    runtime = Candidate01Offline(
        ASSETS / "dwpose_t_singlepass.onnx", ASSETS / "hand_landmarks_detector.tflite"
    )
    clips: list[dict[str, Any]] = []
    try:
        for k, row in enumerate(rows):
            name = Path(row["raw_video_path"]).name
            video = VIDEO_ROOT / name
            target = out / f"{Path(name).stem}.npz"
            if not target.exists():
                if sha256(video).upper() != row["raw_video_sha256"].upper():
                    raise ValueError(f"[heldout_dev] VIDEO_HASH:{name}")
                t, _, orientation = r2._video_timestamps(video)
                records = r2._process_video_indices(
                    runtime, video, np.arange(len(t), dtype=np.int32), t, orientation
                )
                raw = r2._raw_from_records(
                    f"dev_full:{row['sample_id']}", "ASL_CITIZEN", row["signer_group_id"], records
                )
                save_raw_sequence(target, raw)
            raw = load_raw_sequence(target)
            span = json.loads((SPAN_ROOT / f"{Path(name).stem}.span.json").read_text("utf-8-sig"))
            frames = np.asarray(raw.frame_index)
            onset = int(np.searchsorted(frames, int(span["onset"])))
            release = int(np.searchsorted(frames, int(span["release"]), side="right")) - 1
            clips.append(
                {
                    "sample_id": row["sample_id"],
                    "gloss": row["canonical_gloss"],
                    "class_id": int(row["class_id"]),
                    "signer": row["signer_group_id"],
                    "raw_path": str(target.relative_to(root)).replace("\\", "/"),
                    "raw_sha256": sha256(target),
                    "observations": int(len(raw.timestamp_ms)),
                    "span_valid": bool(span.get("valid", False)),
                    "span_onset_index": onset,
                    "span_release_index": release,
                }
            )
            if k % 50 == 0:
                print(f"[heldout_dev] {k}/{len(rows)}", flush=True)
    finally:
        runtime.close()
    write_json(
        out / "manifest.json",
        {
            "schema": "apphear.heldout_dev_fullvideo_raw.v1",
            "dev_manifest_sha256": sha256(root / DEV_MANIFEST),
            "video_root": str(VIDEO_ROOT),
            "candidate01_assets_sha256": {
                name: sha256(ASSETS / name)
                for name in ("dwpose_t_singlepass.onnx", "hand_landmarks_detector.tflite")
            },
            "span_semantics": "governed automatic onset/release (detect_version d1), not human",
            "clips": clips,
        },
        overwrite=True,
    )
    print(json.dumps({"clips": len(clips)}), flush=True)


if __name__ == "__main__":
    main()
