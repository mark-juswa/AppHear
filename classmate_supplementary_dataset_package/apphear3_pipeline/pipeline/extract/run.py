"""Stage-E runner: extract landmarks for the clips in an ASL Citizen split.

Examples:
  python -m pipeline.extract.run --split val --limit 20
  python -m pipeline.extract.run --split train --workers 8   # parallel across cores

Resumable: re-running skips clips already marked 'ok' in the manifest. Failures are recorded,
never fatal to the run (context/code-standards.md § error handling).

Parallelism: clips are independent, so extraction fans out across worker processes (each with
its own MediaPipe instance). IMAGE mode runs full detection every frame, so extraction is CPU
bound (~seconds/clip) — multiprocessing is the main lever (the ~83k full run is days
single-process, hours across cores)."""

from __future__ import annotations

import argparse
import csv
import multiprocessing as mpx
import os
import sys
from pathlib import Path
from typing import Any

import mediapipe as mp
import numpy as np

from .config import ExtractConfig, load_config
from .landmarks import LandmarkExtractor
from .manifest import ManifestWriter, clip_id, load_done
from .schema import ClipLandmarks, ClipSidecar

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "extract.yaml"


def _read_split_rows(config: ExtractConfig, split: str) -> list[dict[str, str]]:
    path = config.splits_dir / f"{split}.csv"
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _hit_rates(clip: ClipLandmarks) -> tuple[float, float, float]:
    if clip.timestamps_ms.shape[0] == 0:
        return 0.0, 0.0, 0.0
    hand_present = clip.hand_score > 0.0  # (T, 2)
    any_hand = float(np.mean(np.any(hand_present, axis=1)))
    both_hands = float(np.mean(np.all(hand_present, axis=1)))
    pose = float(np.mean(clip.pose_score > 0.0))
    return any_hand, both_hands, pose


def _process_row(
    extractor: LandmarkExtractor,
    row: dict[str, str],
    split: str,
    out_root: Path,
    config: ExtractConfig,
    mp_version: str,
) -> dict[str, Any]:
    """Extract + persist one clip. Returns its manifest row (status ok|failed). Shared by the
    sequential and parallel paths so both produce identical output."""
    video_file = row["Video file"]
    cid = clip_id(video_file)
    base = {
        "clip_id": cid,
        "split": split,
        "participant_id": row["Participant ID"],
        "gloss": row["Gloss"],
        "asl_lex_code": row.get("ASL-LEX Code", ""),
        "video_file": video_file,
        "model_config_hash": config.model_config_hash,
    }
    try:
        clip, meta = extractor.extract(config.videos_dir / video_file)
        any_hand, both_hands, pose = _hit_rates(clip)
        npz_path = out_root / f"{cid}.npz"
        sidecar_path = out_root / f"{cid}.json"
        clip.save(npz_path)
        ClipSidecar(
            schema_stage="E",
            extraction_version=config.extraction_version,
            model_config_hash=config.model_config_hash,
            mediapipe_version=mp_version,
            source=config.source,
            split=split,
            participant_id=row["Participant ID"],
            gloss=row["Gloss"],
            asl_lex_code=row.get("ASL-LEX Code", ""),
            video_file=video_file,
            native_fps=float(meta["native_fps"]),
            n_frames=int(meta["n_frames"]),
            frame_width=int(meta["frame_width"]),
            frame_height=int(meta["frame_height"]),
            hand_hit_rate=any_hand,
            two_hand_hit_rate=both_hands,
            pose_hit_rate=pose,
        ).save(sidecar_path)
        return {
            **base,
            "status": "ok",
            "reason": "",
            "n_frames": meta["n_frames"],
            "native_fps": meta["native_fps"],
            "hand_hit_rate": round(any_hand, 4),
            "two_hand_hit_rate": round(both_hands, 4),
            "pose_hit_rate": round(pose, 4),
            "npz_path": str(npz_path),
            "sidecar_path": str(sidecar_path),
        }
    except Exception as err:  # noqa: BLE001 — one bad clip must not kill the run
        print(f"[extract] FAILED {cid}: {err}", file=sys.stderr)
        return {**base, "status": "failed", "reason": str(err)[:200]}


# --- parallel worker (module-level so it's picklable under spawn) --------------------------
_WORKER: dict[str, Any] = {}


def _init_worker(config: ExtractConfig, split: str) -> None:
    _WORKER["ext"] = LandmarkExtractor(config)
    _WORKER["cfg"] = config
    _WORKER["split"] = split
    _WORKER["out"] = config.output_root / split
    _WORKER["mpv"] = getattr(mp, "__version__", "unknown")


def _work(row: dict[str, str]) -> dict[str, Any]:
    return _process_row(
        _WORKER["ext"], row, _WORKER["split"], _WORKER["out"], _WORKER["cfg"], _WORKER["mpv"]
    )


def run(
    split: str,
    limit: int | None,
    config_path: Path,
    only: set[str] | None = None,
    workers: int = 1,
) -> int:
    config = load_config(config_path)
    for task in (config.hand_task, config.pose_task):
        if not task.exists():
            print(
                f"[extract] missing model asset: {task}\n"
                f"          run: python -m pipeline.extract.assets",
                file=sys.stderr,
            )
            return 2

    rows = _read_split_rows(config, split)
    if only is not None:  # explicit clip allowlist (e.g. the cross-signer pilot)
        rows = [r for r in rows if r["Video file"] in only]
    if limit is not None:
        rows = rows[:limit]

    out_root = config.output_root / split
    out_root.mkdir(parents=True, exist_ok=True)
    manifest_path = config.output_root / f"manifest_{split}.csv"
    done = load_done(manifest_path)
    mp_version = getattr(mp, "__version__", "unknown")

    todo = [r for r in rows if clip_id(r["Video file"]) not in done]
    n_skipped = len(rows) - len(todo)
    n_ok = n_failed = 0
    total = len(todo)
    print(f"[extract] {split}: {total} to do, {n_skipped} already done, workers={workers}")

    with ManifestWriter(manifest_path) as manifest:
        if workers <= 1:
            with LandmarkExtractor(config) as extractor:
                seq = (
                    _process_row(extractor, r, split, out_root, config, mp_version) for r in todo
                )
                n_ok, n_failed = _drain(seq, manifest, split, total, n_skipped)
        else:
            ctx = mpx.get_context("spawn")
            with ctx.Pool(workers, initializer=_init_worker, initargs=(config, split)) as pool:
                par = pool.imap_unordered(_work, todo, chunksize=4)
                n_ok, n_failed = _drain(par, manifest, split, total, n_skipped)

    print(
        f"[extract] done {split}: ok={n_ok} failed={n_failed} skipped={n_skipped} "
        f"-> {manifest_path}"
    )
    return 0


def _drain(
    results: Any, manifest: ManifestWriter, split: str, total: int, n_skipped: int
) -> tuple[int, int]:
    n_ok = n_failed = 0
    for i, res in enumerate(results, start=1):
        manifest.append(res)
        if res["status"] == "ok":
            n_ok += 1
        else:
            n_failed += 1
        if i % 25 == 0:
            print(
                f"[extract] {split}: {i}/{total} (ok={n_ok} failed={n_failed} "
                f"skipped={n_skipped})"
            )
    return n_ok, n_failed


def main() -> int:
    default_workers = max(1, (os.cpu_count() or 2) - 1)
    parser = argparse.ArgumentParser(description="AppHear 3 stage-E landmark extraction")
    parser.add_argument("--split", default="val", choices=["train", "val", "test"])
    parser.add_argument("--limit", type=int, default=None, help="max clips (subset runs)")
    parser.add_argument(
        "--workers",
        type=int,
        default=default_workers,
        help=f"parallel worker processes (default {default_workers})",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    return run(args.split, args.limit, args.config, workers=args.workers)


if __name__ == "__main__":
    raise SystemExit(main())
