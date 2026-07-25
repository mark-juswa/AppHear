"""Feature 13 — streaming eval: within-sign emission DYNAMICS on isolated clips.

Diagnostic (per eval-protocol: per-emission numbers are diagnostic, never headline). Answers
"how does the model's answer evolve over the ~1 s sign?" with four cross-signer metrics, all
measured from sign onset (frame 0 of the streaming feature == D1/D2 span start):

  1. time-to-first-correct (TTFC) — first frame argmax==y            (p50/p95, frames + frac)
  2. time-to-stable-correct (TTSC) — first frame it stays==y to end   (p50/p95, frames + frac)
  3. emission stability — argmax switches/sign (flicker) + settled-fraction
  4. confidence trajectory — mean CALIBRATED top-1 prob over 10 normalized sign-time deciles

TTFC/TTSC are reported over clips the model gets right at least once; the never-correct % is
reported separately (averaging time-to-correct over never-correct clips would be meaningless).
Connected-sequence end-to-end is DEFERRED to Phase 2 (no continuous data in ASL Citizen).

  python -m eval.streaming_dynamics            # trained streaming model on test
  python -m eval.streaming_dynamics --smoke    # synthetic; validates the code path

Memory-safe: predicts per-frame in batches and reduces each batch to compact per-clip summaries
(never materializes the N x T x num_classes tensor)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from .confirm import calibrated_logp

_CFG = "model/config/streaming_dynamics.yaml"
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / _CFG


def clip_dynamics(
    per_frame: np.ndarray, y: np.ndarray, lengths: np.ndarray, temperature: float, n_deciles: int
) -> dict[str, np.ndarray]:
    """Reduce a batch of per-frame probs (b,T,C) to compact per-clip summaries. Everything is
    measured only over each clip's real frames [0, length)."""
    b, t, _ = per_frame.shape
    pred = per_frame.argmax(axis=-1)  # (b,T)
    top1_conf = np.exp(calibrated_logp(per_frame, temperature).max(axis=-1))  # (b,T) calibrated

    ttfc = np.full(b, -1, np.int32)
    ttsc = np.full(b, -1, np.int32)
    switches = np.zeros(b, np.int32)
    settled = np.zeros(b, np.float32)
    conf_sum = np.zeros((b, n_deciles), np.float32)
    conf_cnt = np.zeros((b, n_deciles), np.int32)

    for i in range(b):
        length = max(int(lengths[i]), 1)
        p = pred[i, :length]
        correct = p == y[i]
        if correct.any():
            ttfc[i] = int(np.argmax(correct))  # first True
            # first frame from which it stays correct to the end:
            wrong = np.flatnonzero(~correct)
            last_wrong = int(wrong[-1]) if wrong.size else -1
            ttsc[i] = last_wrong + 1 if last_wrong + 1 < length else -1  # -1 == never settles right
        switches[i] = int((p[1:] != p[:-1]).sum())
        final = p[-1]
        settled[i] = float((p == final).mean())  # fraction of sign spent on the final answer
        # accumulate calibrated top-1 confidence into normalized sign-time deciles:
        frac = np.arange(length, dtype=np.float32) / length
        bins = np.minimum((frac * n_deciles).astype(np.int32), n_deciles - 1)
        np.add.at(conf_sum[i], bins, top1_conf[i, :length])
        np.add.at(conf_cnt[i], bins, 1)

    ever = ttfc >= 0
    return {
        "ttfc": ttfc, "ttsc": ttsc, "switches": switches, "settled": settled,
        "ever_correct": ever, "lengths": lengths.astype(np.int32),
        "conf_sum": conf_sum, "conf_cnt": conf_cnt,
    }


def build_summary(
    model: Any, x: np.ndarray, y: np.ndarray, fm: np.ndarray, lengths: np.ndarray,
    temperature: float, n_deciles: int, batch: int,
) -> dict[str, np.ndarray]:
    """Batched per-frame predict -> concatenated per-clip summaries. Memory-safe."""
    parts: list[dict[str, np.ndarray]] = []
    for i in range(0, x.shape[0], batch):
        pf = np.asarray(model(x[i : i + batch], training=False), dtype=np.float32)
        parts.append(clip_dynamics(
            pf, y[i : i + batch], lengths[i : i + batch], temperature, n_deciles))
    return {k: np.concatenate([p[k] for p in parts], axis=0) for k in parts[0]}


def _pctl(values: np.ndarray, lengths: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    """p50/p95 of a latency (frames + fraction-of-sign) over the masked clips."""
    v = values[mask].astype(np.float32)
    if v.size == 0:
        return {"p50_frames": float("nan"), "p95_frames": float("nan"),
                "p50_frac": float("nan"), "p95_frac": float("nan"), "n": 0}
    frac = v / np.clip(lengths[mask].astype(np.float32), 1, None)
    return {
        "p50_frames": float(np.percentile(v, 50)), "p95_frames": float(np.percentile(v, 95)),
        "p50_frac": float(np.percentile(frac, 50)), "p95_frac": float(np.percentile(frac, 95)),
        "n": int(mask.sum()),
    }


def summarize(s: dict[str, np.ndarray], n_deciles: int) -> dict[str, Any]:
    """Aggregate per-clip summaries into the reported dynamics metrics."""
    ever = s["ever_correct"]
    settles = s["ttsc"] >= 0
    conf_sum = s["conf_sum"].sum(axis=0)
    conf_cnt = np.clip(s["conf_cnt"].sum(axis=0), 1, None)
    return {
        "n_clips": int(len(ever)),
        "never_correct_frac": float((~ever).mean()),
        "never_settles_frac": float((~settles).mean()),
        "time_to_first_correct": _pctl(s["ttfc"], s["lengths"], ever),
        "time_to_stable_correct": _pctl(s["ttsc"], s["lengths"], settles),
        "mean_switches_per_sign": float(s["switches"].mean()),
        "mean_settled_fraction": float(s["settled"].mean()),
        "confidence_trajectory_deciles": [float(v) for v in (conf_sum / conf_cnt)],
    }


def _median_frac(vals: np.ndarray, lengths: np.ndarray, mask: np.ndarray) -> float:
    if not mask.any():
        return float("nan")
    return float(np.median(vals[mask] / np.clip(lengths[mask], 1, None)))


def per_signer(s: dict[str, np.ndarray], pids: np.ndarray) -> dict[str, dict[str, float]]:
    """TTFC/TTSC medians per signer — a low aggregate hiding one slow signer is a finding."""
    out: dict[str, dict[str, float]] = {}
    for sid in sorted(set(pids.tolist())):
        m = pids == sid
        lengths = s["lengths"]
        nc = float((~s["ever_correct"][m]).mean()) if m.any() else float("nan")
        out[str(sid)] = {
            "n": int(m.sum()),
            "ttfc_p50_frac": _median_frac(s["ttfc"], lengths, s["ever_correct"] & m),
            "ttsc_p50_frac": _median_frac(s["ttsc"], lengths, (s["ttsc"] >= 0) & m),
            "never_correct_frac": nc,
        }
    return out


def run(smoke: bool, config_path: Path) -> int:
    import tensorflow as tf

    from model.data import load_streaming_split

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    temp = float(cfg["temperature"])
    nd = int(cfg["n_deciles"])
    batch = int(cfg["batch_size"])
    out_dir = Path(cfg["model_dir"])

    if smoke:
        from model.model import build_streaming_classifier

        rng = np.random.default_rng(0)
        model = build_streaming_classifier(96, 258, 10)
        xt, yt, fmt, lent = _syn(rng, 60)
        pids = rng.choice(["P1", "P2", "P3"], size=60)
        out_dir = out_dir / "smoke"
    else:
        mp = out_dir / "best.keras"
        if not mp.exists():
            print(f"[dynamics] no model at {mp} — train streaming first", file=sys.stderr)
            return 2
        model = tf.keras.models.load_model(mp)
        xt, yt, fmt, lent, pids = load_streaming_split(Path(cfg["features_dir"]), "test")

    s = build_summary(model, xt, yt, fmt, lent, temp, nd, batch)
    report = summarize(s, nd)
    report["per_signer"] = per_signer(s, np.asarray(pids))

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "streaming_dynamics_test.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _print(report, out_path)
    return 0


def _print(r: dict[str, Any], out_path: Path) -> None:
    ttfc, ttsc = r["time_to_first_correct"], r["time_to_stable_correct"]
    print("\n=== streaming emission dynamics (test, cross-signer) ===")
    print(f"n={r['n_clips']}  never-correct={r['never_correct_frac']:.1%}  "
          f"never-settles={r['never_settles_frac']:.1%}")
    print(f"time-to-first-correct : p50 {ttfc['p50_frac']:.2f} / p95 {ttfc['p95_frac']:.2f} "
          f"of the sign  ({ttfc['p50_frames']:.0f}/{ttfc['p95_frames']:.0f} frames, n={ttfc['n']})")
    print(f"time-to-stable-correct: p50 {ttsc['p50_frac']:.2f} / p95 {ttsc['p95_frac']:.2f} "
          f"of the sign  ({ttsc['p50_frames']:.0f}/{ttsc['p95_frames']:.0f} frames, n={ttsc['n']})")
    print(f"flicker: {r['mean_switches_per_sign']:.1f} argmax-switches/sign  |  "
          f"settled-fraction {r['mean_settled_fraction']:.2f}")
    traj = "  ".join(f"{v:.2f}" for v in r["confidence_trajectory_deciles"])
    print(f"calibrated top-1 confidence over sign-time deciles:\n  {traj}")
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
    p = argparse.ArgumentParser(description="AppHear 3 streaming emission-dynamics eval (F13)")
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = p.parse_args()
    return run(args.smoke, args.config)


if __name__ == "__main__":
    raise SystemExit(main())
