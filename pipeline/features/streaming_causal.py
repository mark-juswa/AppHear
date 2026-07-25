"""Causal streaming feature builder — same clips / same order / same filtering as
`pipeline.features.streaming` (so the output aligns row-for-row with features_streaming), but each
frame's scale/roll/mirror is estimated causally from past frames only. Also records per-clip
mirror-flip stats so the eval can correlate flips with the commit frame.

  python -m pipeline.features.streaming_causal --split test

Output (features_causal/<split>.npz): X, frame_mask, lengths, y, participant_ids (as streaming)
plus mirror_flips:[N] i32, last_flip_frame:[N] i32. No re-extraction; reuses landmarks + spans."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from ..detect.schema import SpanSidecar
from ..extract.schema import ClipLandmarks
from ..normalize.causal import load_causal_config
from ..normalize.config import load_config as load_normalize_config
from ..normalize.handedness import decide_handedness
from ..quality.config import load_config as load_quality_config
from ..quality.gate import evaluate_quality
from .config import FeaturesConfig, load_config
from .contract import FEATURE_DIM, SCHEMA_VERSION, clip_features_causal

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "features.yaml"


def _load_vocab(fcfg: FeaturesConfig) -> dict[str, int]:
    vpath = fcfg.output_root / "vocab.json"
    if not vpath.exists():
        raise FileNotFoundError(f"no vocab at {vpath} — build isolated features (F) first")
    vocab: dict[str, int] = json.loads(vpath.read_text(encoding="utf-8"))
    return vocab


def run(split: str, limit: int | None, config_path: Path) -> int:
    fcfg = load_config(config_path)
    ncfg = load_normalize_config(fcfg.normalize_config)
    ccfg = load_causal_config()
    qcfg = load_quality_config(fcfg.quality_config)
    t_max = fcfg.streaming_t_max
    vocab = _load_vocab(fcfg)

    in_dir = qcfg.input_root / split
    npz_files = sorted(in_dir.glob("*.npz"))
    if not npz_files:
        print(f"[causal] no clips in {in_dir} — run stages E and D first", file=sys.stderr)
        return 2
    if limit is not None:
        npz_files = npz_files[:limit]

    feats: list[np.ndarray] = []
    fmasks: list[np.ndarray] = []
    lengths: list[int] = []
    labels: list[int] = []
    pids: list[str] = []
    flips: list[int] = []
    last_flip: list[int] = []
    off_mirror: list[bool] = []  # offline (full-span) mirror decision — ground truth for splits
    n_skipped_q = n_oov = n_failed = 0

    for npz_path in npz_files:
        cid = npz_path.stem
        span_path = qcfg.spans_root / split / f"{cid}.span.json"
        if not span_path.exists():
            continue
        try:
            span = SpanSidecar.load(span_path)
            if span.gloss not in vocab:
                n_oov += 1
                continue
            clip = ClipLandmarks.load(npz_path)
            if fcfg.accepted_only:
                res = evaluate_quality(
                    clip.hand_score, clip.pose_score, span.onset, span.release,
                    span.valid, span.native_fps, qcfg,
                )
                if not res.accept:
                    n_skipped_q += 1
                    continue
            feat, fmask, length, (n_flip, lf) = clip_features_causal(
                clip.hands_image, clip.pose_image, span.onset, span.release, ncfg, ccfg, t_max
            )
            off = decide_handedness(
                clip.pose_image, span.onset, span.release, ncfg.handedness_epsilon
            ).mirrored
            feats.append(feat)
            fmasks.append(fmask)
            lengths.append(length)
            labels.append(vocab[span.gloss])
            pids.append(span.participant_id)
            flips.append(n_flip)
            last_flip.append(lf)
            off_mirror.append(off)
        except Exception as err:  # noqa: BLE001
            print(f"[causal] FAILED {cid}: {err}", file=sys.stderr)
            n_failed += 1

    if not feats:
        print("[causal] no accepted clips", file=sys.stderr)
        return 2

    x = np.stack(feats).astype(np.float32)
    fm = np.stack(fmasks)
    out_root = fcfg.streaming_output_root.parent / "features_causal"
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / f"{split}.npz"
    np.savez_compressed(
        out_path,
        X=x,
        frame_mask=fm,
        lengths=np.array(lengths, dtype=np.int32),
        y=np.array(labels, dtype=np.int32),
        participant_ids=np.array(pids),
        mirror_flips=np.array(flips, dtype=np.int32),
        last_flip_frame=np.array(last_flip, dtype=np.int32),
        offline_mirror=np.array(off_mirror, dtype=bool),
        schema_version=SCHEMA_VERSION,
        t_max=t_max,
    )
    has_nan = bool(np.isnan(x).any())
    print(f"\n=== causal streaming feature build ({split}, N4 OFF, v{SCHEMA_VERSION}) ===")
    print(f"clips={x.shape[0]}  Q-skipped={n_skipped_q}  OOV={n_oov}  failed={n_failed}")
    print(f"X={x.shape}  NaN={has_nan} (MUST be False)")
    any_flip = float(np.mean(np.array(flips) > 0))
    print(f"mirror flips/clip: mean={np.mean(flips):.3f}  clips-with-any-flip={any_flip:.1%}")
    print(f"-> {out_path}")
    assert not has_nan, "causal feature matrix contains NaN"
    assert x.shape[-1] == FEATURE_DIM
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="AppHear 3 causal streaming feature builder")
    p.add_argument("--split", default="test", choices=["train", "val", "test"])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = p.parse_args()
    return run(args.split, args.limit, args.config)


if __name__ == "__main__":
    raise SystemExit(main())
