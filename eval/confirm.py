"""Feature 12 — confirmation policy (S7): accumulate calibrated per-frame evidence and commit a
sign the first frame it's confident enough (FP-guarded). Offline; runs on the streaming model's
per-frame emissions. Directly targets v2 lesson e (dropped ~50% of correct signs) — the
'correct-but-dropped' rate is a first-class reported metric.

  python -m eval.confirm            # val operating curve -> pick point -> test metrics
  python -m eval.confirm --smoke    # synthetic; validates the code path

Memory-safe: predicts per-frame in batches and reduces to a compact per-clip evidence summary
(N,T,3); never materializes the full N x T x num_classes tensor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from .streaming import mean_over_real

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "model" / "config" / "confirm.yaml"


def calibrated_logp(probs: np.ndarray, temperature: float) -> np.ndarray:
    """log-softmax(log(probs)/T) — temperature-scaled per-frame log-posterior. (...,C)."""
    logits = np.log(np.clip(probs, 1e-8, 1.0)) / temperature
    logits = logits - logits.max(axis=-1, keepdims=True)
    out: np.ndarray = logits - np.log(np.exp(logits).sum(axis=-1, keepdims=True))
    return out


def frame_evidence_summary(
    per_frame: np.ndarray, temperature: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(B,T,C) probs -> (leading class (B,T), A1 (B,T), A2 (B,T)) where A = cumulative-MEAN
    calibrated log-posterior (length-normalized so thresholds are frame-average, not sum)."""
    logp = calibrated_logp(per_frame, temperature)  # (B,T,C)
    csum = np.cumsum(logp, axis=1)
    counts = np.arange(1, per_frame.shape[1] + 1, dtype=np.float32).reshape(1, -1, 1)
    a = csum / counts  # (B,T,C) cumulative mean
    top1 = a.argmax(axis=-1)
    a1 = np.take_along_axis(a, top1[..., None], axis=-1)[..., 0]
    a_wo = a.copy()
    np.put_along_axis(a_wo, top1[..., None], -np.inf, axis=-1)
    a2 = a_wo.max(axis=-1)
    return top1.astype(np.int32), a1.astype(np.float32), a2.astype(np.float32)


def commit(
    top1: np.ndarray, a1: np.ndarray, a2: np.ndarray, lengths: np.ndarray,
    theta_conf: float, theta_margin: float, k: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Per clip, commit the first frame where evidence + margin + stability all hold; else drop.
    Returns (committed_class (N,) with -1 = dropped, commit_frame (N,) with -1 = dropped)."""
    n, _ = top1.shape
    committed = np.full(n, -1, np.int32)
    frame = np.full(n, -1, np.int32)
    for i in range(n):
        length = int(lengths[i])
        stable = 0
        prev = -1
        for t in range(length):
            c = int(top1[i, t])
            stable = stable + 1 if c == prev else 1
            prev = c
            if a1[i, t] >= theta_conf and (a1[i, t] - a2[i, t]) >= theta_margin and stable >= k:
                committed[i] = c
                frame[i] = t
                break
    return committed, frame


def confirmation_metrics(
    committed: np.ndarray, frame: np.ndarray, y: np.ndarray, lengths: np.ndarray,
    model_argmax: np.ndarray,
) -> dict[str, float]:
    """Report rates over ALL clips + the v2-leak metric (correct-but-dropped) + commit latency."""
    did = committed >= 0
    correct = did & (committed == y)
    model_right = model_argmax == y
    lat = frame[did] / np.clip(lengths[did], 1, None)
    return {
        "commit_rate": float(did.mean()),
        "correct_commit_rate": float(correct.mean()),  # of all clips
        "false_commit_rate": float((did & (committed != y)).mean()),
        "drop_rate": float((~did).mean()),
        "precision_when_committed": float(correct.sum() / max(int(did.sum()), 1)),
        "correct_but_dropped": float(((~did) & model_right).sum() / max(int(model_right.sum()), 1)),
        "mean_commit_latency_frac": float(lat.mean()) if did.any() else float("nan"),
    }


def _build_summary(
    model: Any, x: np.ndarray, fm: np.ndarray, temperature: float, batch: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Batched: per-clip evidence summary (top1,A1,A2) + model_argmax (mean-agg). Memory-safe."""
    n, t = x.shape[0], x.shape[1]
    top1 = np.empty((n, t), np.int32)
    a1 = np.empty((n, t), np.float32)
    a2 = np.empty((n, t), np.float32)
    model_arg = np.empty(n, np.int32)
    for i in range(0, n, batch):
        pf = np.asarray(model(x[i : i + batch], training=False), dtype=np.float32)
        s1, sa1, sa2 = frame_evidence_summary(pf, temperature)
        top1[i : i + batch] = s1
        a1[i : i + batch] = sa1
        a2[i : i + batch] = sa2
        model_arg[i : i + batch] = mean_over_real(pf, fm[i : i + batch]).argmax(axis=1)
    return top1, a1, a2, model_arg


def _operating_curve(
    summary: tuple, y: np.ndarray, lengths: np.ndarray, model_arg: np.ndarray,
    grid: list[float], theta_margin: float, k: int,
) -> list[dict[str, float]]:
    top1, a1, a2 = summary
    curve = []
    for tc in grid:
        committed, frame = commit(top1, a1, a2, lengths, tc, theta_margin, k)
        m = confirmation_metrics(committed, frame, y, lengths, model_arg)
        m["theta_conf"] = tc
        curve.append(m)
    return curve


def run(smoke: bool, config_path: Path) -> int:
    import tensorflow as tf

    from model.data import load_streaming_split

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    temp = float(cfg["temperature"])
    k = int(cfg["k_stability"])
    margin = float(cfg["theta_margin"])
    target_fp = float(cfg["target_false_commit"])
    grid = [float(g) for g in cfg["theta_conf_grid"]]
    features_dir = Path(cfg["features_dir"])
    out_dir = Path(cfg["model_dir"])
    batch = 64

    if smoke:
        from model.model import build_streaming_classifier

        rng = np.random.default_rng(0)
        model = build_streaming_classifier(96, 258, 10)
        xv, yv, fmv, lenv = _syn(rng, 40)
        xt, yt, fmt, lent = _syn(rng, 60)
        out_dir = out_dir / "smoke"
    else:
        mp = out_dir / "best.keras"
        if not mp.exists():
            print(f"[confirm] no model at {mp} — train streaming first", file=sys.stderr)
            return 2
        model = tf.keras.models.load_model(mp)
        xv, yv, fmv, lenv, _ = load_streaming_split(features_dir, "val")
        xt, yt, fmt, lent, _ = load_streaming_split(features_dir, "test")

    t1v, a1v, a2v, argv = _build_summary(model, xv, fmv, temp, batch)
    del xv, fmv
    curve = _operating_curve((t1v, a1v, a2v), yv, lenv, argv, grid, margin, k)

    # pick the strictest point whose false-commit <= target (max correct-commit under the cap)
    ok = [p for p in curve if p["false_commit_rate"] <= target_fp]
    chosen = max(ok, key=lambda p: p["correct_commit_rate"]) if ok else curve[-1]

    t1t, a1t, a2t, argt = _build_summary(model, xt, fmt, temp, batch)
    del xt, fmt
    committed, frame = commit(t1t, a1t, a2t, lent, chosen["theta_conf"], margin, k)
    test_m = confirmation_metrics(committed, frame, yt, lent, argt)

    report = {"chosen_theta_conf": chosen["theta_conf"], "theta_margin": margin, "k": k,
              "val_operating_curve": curve, "test": test_m}
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "confirm_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _print(curve, chosen, test_m, out_path)
    return 0


def _print(curve: list, chosen: dict, test_m: dict, out_path: Path) -> None:
    print("\n=== confirmation val operating curve ===")
    print(f"{'theta':>7}{'commit%':>9}{'correct%':>9}{'FP%':>7}{'drop%':>7}{'prec':>7}{'lat':>6}")
    for p in curve:
        print(f"{p['theta_conf']:>7.1f}{p['commit_rate']:>9.1%}{p['correct_commit_rate']:>9.1%}"
              f"{p['false_commit_rate']:>7.1%}{p['drop_rate']:>7.1%}"
              f"{p['precision_when_committed']:>7.2f}{p['mean_commit_latency_frac']:>6.2f}")
    print(f"\nchosen theta_conf={chosen['theta_conf']:.1f}")
    print("=== TEST @ chosen point ===")
    print(f"commit={test_m['commit_rate']:.1%}  "
          f"correct-commit={test_m['correct_commit_rate']:.1%}  "
          f"FP={test_m['false_commit_rate']:.1%}  "
          f"precision-when-committed={test_m['precision_when_committed']:.2f}")
    print(f"correct-but-dropped={test_m['correct_but_dropped']:.1%} (v2 leak)  "
          f"latency={test_m['mean_commit_latency_frac']:.2f} of the sign")
    print(f"-> {out_path}")


def _syn(rng: Any, n: int) -> tuple:
    x = rng.standard_normal((n, 96, 258)).astype(np.float32)
    y = rng.integers(0, 10, n).astype(np.int32)
    lengths = rng.integers(48, 97, n).astype(np.int32)
    fm = np.zeros((n, 96), dtype=bool)
    for i in range(n):
        fm[i, : lengths[i]] = True
    return x, y, fm, lengths


def main() -> int:
    p = argparse.ArgumentParser(description="AppHear 3 confirmation policy (S7) offline eval")
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = p.parse_args()
    return run(args.smoke, args.config)


if __name__ == "__main__":
    raise SystemExit(main())
