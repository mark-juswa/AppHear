"""Phase-1 streaming feature builder: real-timed (N4 OFF) padded sequences from existing
stage-E landmarks + D2 spans. No re-extraction. Reuses the isolated v3.0 vocab.json.

  python -m pipeline.features.streaming --split val
  python -m pipeline.features.streaming --split train

Output (features_streaming/<split>.npz): X:[N,t_max,258] f32 (post-padded), frame_mask:[N,t_max]
bool, lengths:[N] i32, y:[N] i32, participant_ids:[N]. Same 258 layout as isolated v3.0."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from ..detect.schema import SpanSidecar
from ..extract.schema import ClipLandmarks
from ..normalize.config import load_config as load_normalize_config
from ..quality.config import load_config as load_quality_config
from ..quality.gate import evaluate_quality
from .config import FeaturesConfig, load_config
from .contract import FEATURE_DIM, SCHEMA_VERSION, clip_features_realtimed

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "features.yaml"


def _load_vocab(fcfg: FeaturesConfig) -> dict[str, int]:
    """Reuse the isolated-features vocab (same 2731 glosses / same corpus)."""
    vpath = fcfg.output_root / "vocab.json"
    if not vpath.exists():
        raise FileNotFoundError(f"no vocab at {vpath} — build isolated features (F) first")
    vocab: dict[str, int] = json.loads(vpath.read_text(encoding="utf-8"))
    return vocab


def run(split: str, limit: int | None, config_path: Path) -> int:
    fcfg = load_config(config_path)
    ncfg = load_normalize_config(fcfg.normalize_config)
    qcfg = load_quality_config(fcfg.quality_config)
    t_max = fcfg.streaming_t_max
    vocab = _load_vocab(fcfg)

    in_dir = qcfg.input_root / split
    npz_files = sorted(in_dir.glob("*.npz"))
    if not npz_files:
        print(f"[streaming] no clips in {in_dir} — run stages E and D first", file=sys.stderr)
        return 2
    if limit is not None:
        npz_files = npz_files[:limit]

    feats: list[np.ndarray] = []
    fmasks: list[np.ndarray] = []
    lengths: list[int] = []
    labels: list[int] = []
    pids: list[str] = []
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
                    clip.hand_score,
                    clip.pose_score,
                    span.onset,
                    span.release,
                    span.valid,
                    span.native_fps,
                    qcfg,
                )
                if not res.accept:
                    n_skipped_q += 1
                    continue
            feat, fmask, length, _ = clip_features_realtimed(
                clip.hands_image, clip.pose_image, span.onset, span.release, ncfg, t_max
            )
            feats.append(feat)
            fmasks.append(fmask)
            lengths.append(length)
            labels.append(vocab[span.gloss])
            pids.append(span.participant_id)
        except Exception as err:  # noqa: BLE001
            print(f"[streaming] FAILED {cid}: {err}", file=sys.stderr)
            n_failed += 1

    if not feats:
        print("[streaming] no accepted clips", file=sys.stderr)
        return 2

    x = np.stack(feats).astype(np.float32)
    fm = np.stack(fmasks)
    lens = np.array(lengths, dtype=np.int32)
    y = np.array(labels, dtype=np.int32)
    participants = np.array(pids)

    out_root = fcfg.streaming_output_root
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / f"{split}.npz"
    np.savez_compressed(
        out_path,
        X=x,
        frame_mask=fm,
        lengths=lens,
        y=y,
        participant_ids=participants,
        schema_version=SCHEMA_VERSION,
        t_max=t_max,
    )
    _report(split, x, fm, lens, vocab, n_skipped_q, n_oov, n_failed, out_path)
    return 0


def _report(
    split: str,
    x: np.ndarray,
    fm: np.ndarray,
    lens: np.ndarray,
    vocab: dict,
    n_skipped_q: int,
    n_oov: int,
    n_failed: int,
    out_path: Path,
) -> None:
    has_nan = bool(np.isnan(x).any())
    print(f"\n=== streaming feature build ({split}, N4 OFF, v{SCHEMA_VERSION}) ===")
    print(f"clips={x.shape[0]}  Q-skipped={n_skipped_q}  OOV={n_oov}  failed={n_failed}")
    print(f"X={x.shape}  frame_mask={fm.shape}  vocab={len(vocab)}")
    print(f"X has NaN: {has_nan} (MUST be False)  range=[{x.min():.3f}, {x.max():.3f}]")
    print(
        f"real length: median={int(np.median(lens))} p90={int(np.percentile(lens, 90))} "
        f"max={int(lens.max())}  (t_max={x.shape[1]})"
    )
    frac_pad = 1.0 - fm.mean()
    print(f"padding fraction: {frac_pad:.1%}  (mask True = real frame)")
    print(f"-> {out_path}")
    assert not has_nan, "streaming feature matrix contains NaN"
    assert x.shape[-1] == FEATURE_DIM
    # frame_mask must be a prefix of `lengths` real frames, padded region exactly zero
    assert np.array_equal(fm.sum(axis=1).astype(np.int32), lens)
    assert np.all(x[~fm] == 0.0)


def main() -> int:
    p = argparse.ArgumentParser(description="AppHear 3 Phase-1 streaming feature builder (N4 off)")
    p.add_argument("--split", default="val", choices=["train", "val", "test"])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = p.parse_args()
    return run(args.split, args.limit, args.config)


if __name__ == "__main__":
    raise SystemExit(main())
