"""Ingest the human Sem-Lex form decisions of review package 02 into Candidate01 raw.

Research only.

Input: docs/audit/probes/word_accuracy/semlex_review_02_decisions.csv (human P5-D6 decisions,
one per
AppHear class x Sem-Lex lexical id). Only ACCEPT_EXACT_FORM / ACCEPT_COMPATIBLE_VARIANT forms are
used; REJECT and UNRESOLVED forms never are. Every Sem-Lex TRAIN clip carrying an accepted label is
streamed from the local Sem-Lex TRAIN archive (no download), hashed, run through the pinned Android
Candidate01 assets (unchanged), and listed in a manifest with the same schema as
semlex_candidate_raw_01 plus the lexical id and the human decision. Undecodable files are logged,
never fabricated. Both signer roles are extracted: ENRICH-role clips may train candidates, EVAL-role
clips are evaluation only (word_vocabulary_eval.semlex_role).

  stage                   stream the accepted clips out of the archive (one pass)
  extract --shard k/n     Candidate01 raw per staged video
  manifest                write manifest.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import tarfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DECISIONS = ROOT / "docs/audit/probes/word_accuracy/semlex_review_02_decisions.csv"
DECISIONS_SHA = "005099ec84286dcb251e56c2e3e87bdabd203bac20b70bf34bc3f5bb867ff174"
OUT = Path(
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/semlex_candidate_raw_02"
)
VOCAB = Path("artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1/vocab.json")
ASSETS = ROOT / "android/app/src/main/assets/perception_vnext"
ACCEPT = ("ACCEPT_EXACT_FORM", "ACCEPT_COMPATIBLE_VARIANT")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def accepted_rows(metadata: Path) -> list[dict]:
    if sha256(DECISIONS) != DECISIONS_SHA:
        raise ValueError("SEMLEX_DECISIONS_DRIFT")
    decisions = [
        d for d in csv.DictReader(DECISIONS.open(encoding="utf-8")) if d["decision"] in ACCEPT
    ]
    form = {d["semlex_lexical_id"]: d for d in decisions}
    if len(form) != len(decisions):
        raise ValueError("SEMLEX_LEXICAL_ID_ACCEPTED_FOR_TWO_CLASSES")
    rows, seen = [], set()
    for r in csv.DictReader(metadata.open(encoding="utf-8")):
        lexical = f"{r['label_type']}:{r['label'].strip()}"
        if r["split"] != "train" or lexical not in form or r["video_id"] in seen:
            continue
        seen.add(r["video_id"])
        d = form[lexical]
        rows.append(
            {
                "video_id": r["video_id"],
                "signer_id": r["signer_id"],
                "gloss": d["gloss"],
                "semlex_lexical_id": lexical,
                "human_decision": d["decision"],
            }
        )
    return sorted(rows, key=lambda x: x["video_id"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--archive", type=Path, required=True)
    x = sub.add_parser("extract")
    x.add_argument("--shard", type=int, default=0)
    x.add_argument("--shards", type=int, default=1)
    sub.add_parser("manifest")
    args = parser.parse_args()
    out = args.evidence_root / OUT
    (out / "videos").mkdir(parents=True, exist_ok=True)
    rows = accepted_rows(args.metadata)
    if args.command == "stage":
        wanted = {f"train/{r['video_id']}.webm" for r in rows}
        with tarfile.open(args.archive, mode="r|gz") as tar:
            for member in tar:
                name = member.name.removeprefix("./")
                if name not in wanted:
                    continue
                target = out / "videos" / Path(name).name
                source = tar.extractfile(member)
                if source is not None and not target.exists():
                    with target.open("wb") as f:
                        shutil.copyfileobj(source, f)
                wanted.discard(name)
                if not wanted:
                    break
        print(json.dumps({"accepted_clips": len(rows), "missing_from_archive": len(wanted)}))
        return
    if args.command == "extract":
        from eval.runtime_diagnostics import s2_r2_continuous_domain_correction as r2
        from pipeline.perception_vnext.offline_candidate01 import Candidate01Offline
        from pipeline.perception_vnext.recognition_schema import save_raw_sequence

        runtime = Candidate01Offline(
            ASSETS / "dwpose_t_singlepass.onnx", ASSETS / "hand_landmarks_detector.tflite"
        )
        try:
            for k, row in enumerate(rows):
                if k % args.shards != args.shard:
                    continue
                video = out / "videos" / f"{row['video_id']}.webm"
                target = out / f"{row['video_id']}.npz"
                if target.exists() or not video.exists():
                    continue
                try:
                    t, _, orientation = r2._video_timestamps(video)
                    records = r2._process_video_indices(
                        runtime, video, np.arange(len(t), dtype=np.int32), t, orientation
                    )
                    if not records:
                        raise RuntimeError("NO_DECODED_FRAMES")
                except RuntimeError as error:  # undecodable source: record, never fabricate
                    with (out / f"undecodable_shard{args.shard}.txt").open(
                        "a", encoding="utf-8"
                    ) as log:
                        log.write(f"{video.name} | {error}\n")
                    continue
                raw = r2._raw_from_records(
                    f"semlex:{row['video_id']}", "SEM_LEX", f"SEMLEX::{row['signer_id']}", records
                )
                save_raw_sequence(target, raw)
                if k % 100 == args.shard:
                    print(f"[semlex02] shard {args.shard}: {k}/{len(rows)}", flush=True)
        finally:
            runtime.close()
        return
    from pipeline.perception_vnext.recognition_schema import load_raw_sequence

    vocab = json.loads((args.evidence_root / VOCAB).read_text(encoding="utf-8"))
    clips = []
    for row in rows:
        target = out / f"{row['video_id']}.npz"
        if not target.exists():
            continue
        clips.append(
            {
                "class_id": int(vocab[row["gloss"]]),
                "gloss": row["gloss"],
                "human_decision": row["human_decision"],
                "semlex_lexical_id": row["semlex_lexical_id"],
                "observations": int(len(load_raw_sequence(target).timestamp_ms)),
                "raw_path": str(target.relative_to(args.evidence_root)).replace("\\", "/"),
                "raw_sha256": sha256(target),
                "semlex_sample_id": row["video_id"],
                "signer": f"SEMLEX::{row['signer_id']}",
                "video_sha256": sha256(out / "videos" / f"{row['video_id']}.webm"),
            }
        )
    manifest = {
        "schema": "apphear.semlex_candidate_raw.v2",
        "decisions_sha256": DECISIONS_SHA,
        "metadata_sha256": sha256(args.metadata),
        "accepted_clips": len(rows),
        "candidate01_assets_sha256": {
            n: sha256(ASSETS / n)
            for n in ("dwpose_t_singlepass.onnx", "hand_landmarks_detector.tflite")
        },
        "clips": clips,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"accepted": len(rows), "extracted": len(clips)}))


if __name__ == "__main__":
    main()
