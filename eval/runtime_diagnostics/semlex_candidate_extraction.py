"""Candidate01 raw-v1 for the staged Sem-Lex signer-diversity candidates (WORD track).

Source: I:/SEM LEX/AppHear_P5D7_candidate/staged (2,425 hash-listed webms; 65 AppHear classes whose
Sem-Lex form was human-accepted as exact or a compatible variant; 32 Sem-Lex signer IDs; Sem-Lex
TRAIN split only). Every frame is processed with the pinned Android Candidate01 assets so a span
can be derived later with the same rule used for the recognizer population. Each file's SHA-256 is
checked against the staged manifest. Outputs go to a new artifact directory; nothing existing is
modified. The AppHear protected TEST population is unrelated and never read.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

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

STAGED = Path(r"I:\SEM LEX\AppHear_P5D7_candidate\staged")
OUT_RELATIVE = Path(
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/semlex_candidate_raw_01"
)
ASSETS = ROOT / "android/app/src/main/assets/perception_vnext"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument("--reverse", action="store_true", help="walk the shard backwards")
    args = parser.parse_args()
    out = args.evidence_root / OUT_RELATIVE
    out.mkdir(parents=True, exist_ok=True)
    rows = [
        r
        for r in csv.DictReader((STAGED / "staged_manifest.csv").open(encoding="utf-8"))
        if r["eligible_for_extraction"] == "True"
    ]
    if args.manifest_only:
        clips = []
        for row in rows:
            target = out / f"{Path(row['raw_video_path']).stem}.npz"
            if not target.exists():
                continue
            raw = load_raw_sequence(target)
            clips.append(
                {
                    "semlex_sample_id": row["semlex_sample_id"],
                    "signer": f"SEMLEX::{row['semlex_signer_id']}",
                    "gloss": row["apphear_gloss"],
                    "class_id": int(row["apphear_class_id"]),
                    "human_decision": row["human_decision"],
                    "raw_path": str(target.relative_to(args.evidence_root)).replace("\\", "/"),
                    "raw_sha256": sha256(target),
                    "observations": int(len(raw.timestamp_ms)),
                }
            )
        write_json(
            out / "manifest.json",
            {
                "schema": "apphear.semlex_candidate_raw.v1",
                "staged_manifest_sha256": sha256(STAGED / "staged_manifest.csv"),
                "candidate01_assets_sha256": {
                    name: sha256(ASSETS / name)
                    for name in ("dwpose_t_singlepass.onnx", "hand_landmarks_detector.tflite")
                },
                "clips": clips,
            },
            overwrite=True,
        )
        print(json.dumps({"clips": len(clips), "eligible": len(rows)}))
        return
    runtime = Candidate01Offline(
        ASSETS / "dwpose_t_singlepass.onnx", ASSETS / "hand_landmarks_detector.tflite"
    )
    try:
        order = list(enumerate(rows))
        for k, row in reversed(order) if args.reverse else order:
            if k % args.shards != args.shard:
                continue
            video = STAGED / "raw" / Path(row["raw_video_path"]).name
            target = out / f"{video.stem}.npz"
            if target.exists():
                continue
            if sha256(video) != row["raw_sha256"]:
                raise ValueError(f"[semlex] VIDEO_HASH:{video.name}")
            try:
                t, _, orientation = r2._video_timestamps(video)
                records = r2._process_video_indices(
                    runtime, video, np.arange(len(t), dtype=np.int32), t, orientation
                )
                if not records:
                    raise RuntimeError("NO_DECODED_FRAMES")
            except RuntimeError as error:  # undecodable source: record, never fabricate
                failures = out / f"undecodable_shard{args.shard}.txt"
                with failures.open("a", encoding="utf-8") as log:
                    fields = [video.name, row["semlex_sample_id"], str(error)]
                    log.write(" | ".join(fields) + chr(10))
                continue
            raw = r2._raw_from_records(
                f"semlex:{row['semlex_sample_id']}",
                "SEM_LEX",
                f"SEMLEX::{row['semlex_signer_id']}",
                records,
            )
            save_raw_sequence(target, raw)
            if k % 100 == args.shard:
                print(f"[semlex] shard {args.shard}: {k}/{len(rows)}", flush=True)
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
