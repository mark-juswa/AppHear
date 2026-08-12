"""Feature 11 cross-signer eval for the per-frame streaming model.

Aggregates the per-frame probabilities to one clip prediction (mean over real frames) and feeds
the SAME feature-08 harness → comparable to the isolated baseline. Also reports per-frame and
last-frame accuracy as streaming diagnostics.

  python -m eval.streaming            # streaming model on test
  python -m eval.streaming --smoke    # synthetic; validates the code path"""

from __future__ import annotations

import os

# See model/train_streaming.py: oneDNN's INT32 fallback segfaults on non-AVX-512 CPUs (the GCN
# encoder's keypoint-gather). Disable BEFORE TensorFlow is imported so GCN eval doesn't crash.
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

import numpy as np  # noqa: E402

from model.train_streaming import DEFAULT_CONFIG, load_stream_config  # noqa: E402

from .harness import evaluate  # noqa: E402


def mean_over_real(per_frame: np.ndarray, frame_mask: np.ndarray) -> np.ndarray:
    """(N,T,C) per-frame probs + (N,T) mask -> (N,C) clip probs, averaged over real frames."""
    m = frame_mask.astype(np.float32)[..., None]
    denom = np.clip(m.sum(axis=1), 1.0, None)
    clip: np.ndarray = (per_frame * m).sum(axis=1) / denom
    return clip


def per_frame_accuracy(per_frame: np.ndarray, y: np.ndarray, frame_mask: np.ndarray) -> float:
    pred = per_frame.argmax(axis=-1)  # (N,T)
    correct = (pred == y[:, None]).astype(np.float32)
    m = frame_mask.astype(np.float32)
    return float((correct * m).sum() / m.sum())


def last_frame_accuracy(per_frame: np.ndarray, y: np.ndarray, lengths: np.ndarray) -> float:
    idx = np.clip(lengths - 1, 0, per_frame.shape[1] - 1)
    last = per_frame[np.arange(len(y)), idx]  # (N,C)
    return float((last.argmax(axis=1) == y).mean())


def predict_aggregate(
    model: Any,
    x: np.ndarray,
    frame_mask: np.ndarray,
    y: np.ndarray,
    lengths: np.ndarray,
    batch_size: int,
) -> tuple[np.ndarray, float, float]:
    """Batched per-frame prediction + on-the-fly aggregation. The per-frame output is huge
    (N x T x num_classes ~ tens of GB at full scale), so we NEVER materialize it whole: predict
    one batch, aggregate to clip probs (N x C), accumulate per-frame/last-frame accuracy, discard.
    Returns (clip_probs (N,C), per_frame_acc, last_frame_acc)."""
    n = x.shape[0]
    num_classes = int(model.output_shape[-1])
    clip = np.empty((n, num_classes), np.float32)
    pf_correct = pf_total = 0.0
    last_correct = 0
    for i in range(0, n, batch_size):
        xb = x[i : i + batch_size]
        mb = frame_mask[i : i + batch_size]
        yb = y[i : i + batch_size]
        pf = np.asarray(model(xb, training=False), dtype=np.float32)  # (b,T,C) — one batch only
        clip[i : i + batch_size] = mean_over_real(pf, mb)
        m = mb.astype(np.float32)
        pf_correct += float(((pf.argmax(-1) == yb[:, None]).astype(np.float32) * m).sum())
        pf_total += float(m.sum())
        idx = np.clip(lengths[i : i + batch_size] - 1, 0, pf.shape[1] - 1)
        last_correct += int((pf[np.arange(len(yb)), idx].argmax(1) == yb).sum())
    return clip, pf_correct / pf_total, last_correct / n


def _report_path(output_dir: Path, report_name: str) -> Path:
    candidate = Path(report_name)
    if candidate.name != report_name or candidate.suffix.lower() != ".json":
        raise ValueError("report_name must be a plain .json filename")
    return output_dir / candidate


def run(
    smoke: bool,
    config_path: Path = DEFAULT_CONFIG,
    features_dir: Path | None = None,
    report_name: str = "eval_streaming_test.json",
) -> int:
    import tensorflow as tf

    from model.data import load_streaming_split

    cfg = load_stream_config(config_path)
    # optional override: evaluate this model on a DIFFERENT feature set (e.g. a low-fps test set)
    # while still reading the trained model from the config's output_dir.
    feat_dir = features_dir or cfg.features_dir
    bs = cfg.batch_size
    if smoke:
        from model.model import build_streaming_classifier

        rng = np.random.default_rng(0)
        t, f, c = 96, 258, 10
        model = build_streaming_classifier(t, f, c)
        xv, yv, fmv, lenv = _syn(rng, 40, t, f, c, with_len=True)
        xt, yt, fmt, lent = _syn(rng, 60, t, f, c, with_len=True)
        pt = rng.choice(["P1", "P2", "P3"], size=60)
        out_dir = cfg.output_dir / "smoke"
    else:
        mp = cfg.output_dir / "best.keras"
        if not mp.exists():
            print(
                f"[eval-stream] no model at {mp} — train first (model.train_streaming)",
                file=sys.stderr,
            )
            return 2
        model = tf.keras.models.load_model(mp)
        xv, yv, fmv, lenv, _ = load_streaming_split(feat_dir, "val")
        xt, yt, fmt, lent, pt = load_streaming_split(feat_dir, "test")
        out_dir = cfg.output_dir

    # Batched aggregation: the per-frame output is ~tens of GB at full scale, so never hold it
    # whole. Aggregate val, free it, then test — bounds peak RAM to one split + one batch.
    clip_v, _, _ = predict_aggregate(model, xv, fmv, yv, lenv, bs)
    del xv, fmv
    clip_t, pf_acc, last_acc = predict_aggregate(model, xt, fmt, yt, lent, bs)
    del xt, fmt

    report = evaluate(clip_v, yv, clip_t, yt, np.asarray(pt))
    report["streaming"] = {"per_frame_acc": pf_acc, "last_frame_acc": last_acc}
    report["provenance"] = {
        "config": str(config_path.resolve()),
        "features_dir": str(feat_dir.resolve()),
        "model": "synthetic-smoke" if smoke else str(mp.resolve()),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = _report_path(out_dir, report_name)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    o, s = report["overall"], report["streaming"]
    print("\n=== streaming cross-signer eval (test) ===")
    print(f"n={report['n_test']} across {report['n_signers']} signers")
    print(
        f"clip (mean-agg) top1={o['top1']:.3f} top5={o['top5']:.3f}  "
        f"per-frame acc={s['per_frame_acc']:.3f}  last-frame acc={s['last_frame_acc']:.3f}"
    )
    print(f"-> {out_path}")
    return 0


def _syn(rng: Any, n: int, t: int, f: int, c: int, with_len: bool = False) -> tuple:
    x = rng.standard_normal((n, t, f)).astype(np.float32)
    y = rng.integers(0, c, n).astype(np.int32)
    lengths = rng.integers(t // 2, t + 1, n).astype(np.int32)
    fm = np.zeros((n, t), dtype=bool)
    for i in range(n):
        fm[i, : lengths[i]] = True
    return (x, y, fm, lengths) if with_len else (x, y, fm, c)


def main() -> int:
    p = argparse.ArgumentParser(description="AppHear 3 streaming cross-signer eval")
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument(
        "--features-dir",
        type=Path,
        default=None,
        help="override: eval the config model on THIS feature set (e.g. low-fps test)",
    )
    p.add_argument("--report-name", default="eval_streaming_test.json")
    args = p.parse_args()
    return run(args.smoke, args.config, args.features_dir, args.report_name)


if __name__ == "__main__":
    raise SystemExit(main())
