from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from audit_local_dataset import build_rows, load_experimental_includes, load_labels, load_vocab


def safe_name(value: str) -> str:
    keep = []
    for ch in value:
        if ch.isalnum() or ch in {"_", "-"}:
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep).strip("_") or "clip"


def link_or_copy(src: Path, dst: Path, mode: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    if mode == "copy":
        shutil.copy2(src, dst)
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize Dataset 1/2/3 into AppHearDataset/samples/signs layout.")
    parser.add_argument("--source", type=Path, default=Path(r"F:\ASL DATASET\local"))
    parser.add_argument("--out", type=Path, default=Path("work/prepared_local/AppHearDataset"))
    parser.add_argument("--vocab", type=Path, default=Path("config/deployed_vocab.json"))
    parser.add_argument("--labels", type=Path, default=Path("config/labels.json"))
    parser.add_argument("--mode", choices=["hardlink", "copy"], default="hardlink")
    parser.add_argument("--experimental-includes", type=Path, default=Path("config/include_experimental_labels.json"))
    args = parser.parse_args()

    rows, errors = build_rows(args.source, load_vocab(args.vocab), load_labels(args.labels), load_experimental_includes(args.experimental_includes))
    usable = [r for r in rows if r["usable"]]
    signs_root = args.out / "samples" / "signs"
    signs_root.mkdir(parents=True, exist_ok=True)

    written = 0
    for idx, row in enumerate(usable, 1):
        video = Path(row["video"])
        stem = safe_name(f"D{row['batch']}_{row['signer_id']}_{video.stem}")
        gloss = row["chosen_gloss"]
        target_dir = signs_root / gloss
        target_video = target_dir / f"{stem}.mp4"
        target_json = target_dir / f"{stem}.json"
        link_or_copy(video, target_video, args.mode)
        sidecar = {
            "schema": "apphear-local-supplement-v1",
            "source": "local_supplementary",
            "word": row["word"],
            "gloss": gloss,
            "signer_id": row["signer_id"],
            "sign_language": row["language"] or "ASL",
            "accepted": True,
            "video_file": target_video.name,
            "original_json": row["sidecar"],
            "original_video": row["video"],
            "original_json_gloss": row["json_gloss"],
            "mapped_from_json_gloss": row["needs_remap"],
            "dataset_batch": row["batch"],
            "note": "Video is re-extracted by AppHear 3 pipeline; old baked 258 JSON frames are intentionally ignored.",
        }
        target_json.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        written += 1

    summary = {
        "source": str(args.source),
        "prepared_root": str(args.out),
        "usable_clips_written": written,
        "skipped_or_review_clips": len([r for r in rows if not r["usable"]]),
        "parse_errors": len(errors),
        "link_mode": args.mode,
    }
    (args.out / "prepare_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[prepare] wrote {written} usable clips into {args.out}")
    print(f"[prepare] skipped/review clips: {summary['skipped_or_review_clips']}")
    print(f"[prepare] next recorded-root: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

