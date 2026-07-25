"""Frame-rate (temporal) augmentation for the streaming features — NO re-extraction. The model was
trained on ~30fps clips but the phone delivers ~2.5-5fps, a ~12x temporal mismatch that hurts
on-device recognition (memory: fps-temporal-mismatch). This SUBSAMPLES clips (keep every k-th real
frame, compact to the front, re-pad to t_max) to simulate lower capture rates. v3.0 features are
POSITIONS (not velocities), so subsampling positions faithfully reproduces what the phone sees.

Two modes:
  expand : each clip -> original (k=1) + N random-stride copies -> a fps-robust TRAIN/VAL set.
  fixed  : each clip -> one copy at stride ~k -> a low-fps TEST set for the on-device-regime eval.

  python -m pipeline.features.fps_augment --mode expand
  python -m pipeline.features.fps_augment --mode fixed --k 8 --splits val test

Subsampling starts at frame 0 (the sign onset, matching the on-device buffer). k is capped per clip
so the result keeps >= --min-frames real frames (a short sign must not collapse)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

BASE = Path("F:/ASL DATASET/ASL CITIZEN/derived/apphear3")
DEFAULT_IN = BASE / "features_streaming_reduced"


def _subsample(x_row: np.ndarray, length: int, k: int, t_max: int) -> tuple[np.ndarray, int]:
    """Keep every k-th of the first `length` frames, compact to front, zero-pad to t_max."""
    idx = np.arange(0, length, k)
    new_len = int(idx.size)
    out = np.zeros((t_max, x_row.shape[1]), np.float32)
    out[:new_len] = x_row[idx]
    return out, new_len


def _eff_k(length: int, k: int, min_frames: int) -> int:
    """Cap stride so the subsample keeps >= min_frames frames; >=1."""
    return max(1, min(k, length // min_frames if min_frames > 0 else k))


def run(args: argparse.Namespace) -> int:
    in_dir = Path(args.in_dir)
    rng = np.random.default_rng(args.seed)
    if args.mode == "expand":
        default_out = in_dir.parent / "features_streaming_reduced_fps"
        splits = ["train", "val"]
    else:
        default_out = in_dir.parent / f"features_lowfps_k{args.k}"
        splits = args.splits
    out_dir = Path(args.out_dir) if args.out_dir else default_out
    out_dir.mkdir(parents=True, exist_ok=True)

    for split in splits:
        path = in_dir / f"{split}.npz"
        if not path.exists():
            print(f"[fps] skip {split} (missing {path})", file=sys.stderr)
            continue
        with np.load(path, allow_pickle=True) as d:
            x, lengths = np.asarray(d["X"]), np.asarray(d["lengths"])
            y, pids = np.asarray(d["y"]), np.asarray(d["participant_ids"])
        t_max = x.shape[1]

        xs: list[np.ndarray] = []
        masks: list[np.ndarray] = []
        lens: list[int] = []
        ys: list[int] = []
        ps: list[str] = []
        eff_ks: list[int] = []

        for i in range(x.shape[0]):
            length = int(lengths[i])
            variants: list[int] = []
            if args.mode == "expand":
                variants.append(1)  # native
                kmax_eff = _eff_k(length, args.kmax, args.min_frames)
                for _ in range(args.n_copies):
                    if kmax_eff >= 2:
                        variants.append(int(rng.integers(2, kmax_eff + 1)))
            else:  # fixed
                variants.append(_eff_k(length, args.k, args.min_frames))

            for k in variants:
                sub_x, sub_len = _subsample(x[i], length, k, t_max)
                mask = np.zeros(t_max, bool)
                mask[:sub_len] = True
                xs.append(sub_x)
                masks.append(mask)
                lens.append(sub_len)
                ys.append(int(y[i]))
                ps.append(str(pids[i]))
                eff_ks.append(k)

            # PREFIX augmentation (encoder-upgrade.md §4, expand mode only): additional copies
            # truncated to a random prefix [0..t) of the sign — a non-causal clip model must learn
            # to classify PARTIAL signs, because at runtime S7 asks for a posterior MID-sign
            # (F13: confidence peaks mid-sign; commits happen before release). Prefixes are drawn
            # from the fps-subsampled variant so low-fps and partial-sign conditions co-occur, as
            # they do on the phone. t ~ uniform[max(min_frames, 0.3*L), L).
            if args.mode == "expand" and args.prefix_copies > 0:
                for _ in range(args.prefix_copies):
                    k = 1
                    kmax_eff = _eff_k(length, args.kmax, args.min_frames)
                    if kmax_eff >= 2 and rng.random() < 0.75:  # 75% of prefixes also low-fps
                        k = int(rng.integers(2, kmax_eff + 1))
                    sub_x, sub_len = _subsample(x[i], length, k, t_max)
                    lo = max(args.min_frames, int(np.ceil(0.3 * sub_len)))
                    if sub_len <= lo:
                        continue  # too short to truncate meaningfully
                    t_cut = int(rng.integers(lo, sub_len))
                    pre = np.zeros_like(sub_x)
                    pre[:t_cut] = sub_x[:t_cut]
                    mask = np.zeros(t_max, bool)
                    mask[:t_cut] = True
                    xs.append(pre)
                    masks.append(mask)
                    lens.append(t_cut)
                    ys.append(int(y[i]))
                    ps.append(str(pids[i]))
                    eff_ks.append(k)

        xa = np.stack(xs).astype(np.float32)
        out = out_dir / f"{split}.npz"
        np.savez_compressed(
            out, X=xa, frame_mask=np.stack(masks), lengths=np.array(lens, np.int32),
            y=np.array(ys, np.int32), participant_ids=np.array(ps),
            schema_version="3.0", t_max=t_max,
        )
        ek = np.array(eff_ks)
        print(f"[fps] {split}: {x.shape[0]} -> {xa.shape[0]} clips  mean-stride={ek.mean():.2f} "
              f"(k=1 frac {np.mean(ek == 1):.0%})  median-len {int(np.median(lens))} -> {out}")
    print(f"[fps] done -> {out_dir}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Frame-rate augmentation for streaming features")
    p.add_argument("--mode", choices=["expand", "fixed"], default="expand")
    p.add_argument("--k", type=int, default=8, help="target stride for fixed mode (capped)")
    p.add_argument("--splits", nargs="+", default=["val", "test"], help="splits for fixed mode")
    p.add_argument("--n-copies", type=int, default=3, help="subsampled copies/clip (expand mode)")
    p.add_argument("--prefix-copies", type=int, default=0,
                   help="expand mode: extra PREFIX-truncated copies/clip (encoder-upgrade.md §4 — "
                        "required for non-causal clip models to commit mid-sign)")
    p.add_argument("--kmax", type=int, default=10, help="max stride drawn (expand mode)")
    p.add_argument("--min-frames", type=int, default=4, help="floor on frames after subsampling")
    p.add_argument("--in-dir", type=Path, default=DEFAULT_IN)
    p.add_argument("--out-dir", type=Path, default=None)
    p.add_argument("--seed", type=int, default=0)
    return run(p.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
