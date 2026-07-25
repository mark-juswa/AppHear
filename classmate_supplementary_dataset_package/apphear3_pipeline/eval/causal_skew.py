"""Measure CAUSAL SKEW: does estimating scale/roll/mirror from past frames only (streaming) change
what the model commits vs the proven full-span features? Recognition-level gate (per the INT8
lesson — judge the committed output, not raw feature diffs). Diagnostics explain where/when the
causal path diverges (esp. mirror flips vs the commit frame).

  python -m eval.causal_skew            # features_causal/test vs features_streaming/test
  python -m eval.causal_skew --smoke    # synthetic; validates the code path

GATE (all on the cross-signer test set): causal clip top-1 within `max_top1_delta` of the full-span
baseline AND committed-prediction agreement >= `min_commit_agreement` AND late mirror flips (a flip
at/after the commit frame) <= `max_late_flip_rate`. Memory-safe: mmap-slices X in batches."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from .confirm import _build_summary, commit

ROOT = Path(__file__).resolve().parents[1]
CONFIRM_CONFIG = ROOT / "model" / "config" / "confirm.yaml"
# GATE = the DEPLOYMENT metric: the app shows the S7 COMMITTED prediction, so the real question is
# whether causal commits CORRECT glosses about as often as full-span (commit-accuracy delta), with
# mean-agg top-1 as a secondary sanity. Mean-agg top-1 alone is a DIAGNOSTIC per eval-protocol and
# does NOT reflect the committed output — gating on it was the review's Critical finding.
MAX_COMMIT_ACC_DELTA = 0.02  # commit is on a ~9% subset, so allow a slightly looser band than top-1
MAX_TOP1_DELTA = 0.01
# Diagnostics (reported, NOT gated): commit-agreement caps at the ~88% causal mirror ceiling; and a
# late mirror flip is post-commit, so it cannot change the already-committed gloss (confirmation
# commits once per sign, then resets) — informative, not a deployment failure.


def feature_skew_deciles(
    xc: np.ndarray, xf: np.ndarray, fm: np.ndarray, lengths: np.ndarray, n_dec: int, batch: int
) -> list[float]:
    """Mean over clips/frames of max|causal-fullspan| per frame, bucketed by normalized sign-time.
    Expect high early (unstable params), decaying toward 0 late — the 'where it diverges' view.
    mmap-safe: never holds both full X arrays at once."""
    dec_sum = np.zeros(n_dec, np.float64)
    dec_cnt = np.zeros(n_dec, np.int64)
    for i in range(0, xc.shape[0], batch):
        a = np.asarray(xc[i : i + batch], np.float32)
        b = np.asarray(xf[i : i + batch], np.float32)
        d = np.abs(a - b).max(axis=2)  # (bt, T) per-frame max abs diff over 258 dims
        for j in range(a.shape[0]):
            length = max(int(lengths[i + j]), 1)
            frac = np.arange(length, dtype=np.float32) / length
            bins = np.minimum((frac * n_dec).astype(np.int32), n_dec - 1)
            np.add.at(dec_sum, bins, d[j, :length])
            np.add.at(dec_cnt, bins, 1)
    return [float(s / c) if c else float("nan") for s, c in zip(dec_sum, dec_cnt, strict=True)]


def commit_and_argmax(
    model: Any, x: np.ndarray, fm: np.ndarray, lengths: np.ndarray,
    temp: float, theta_conf: float, theta_margin: float, k: int, batch: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Run one feature path -> (committed_class[N] (-1=drop), commit_frame[N], model_argmax[N])."""
    top1, a1, a2, model_arg = _build_summary(model, x, fm, temp, batch)
    committed, frame = commit(top1, a1, a2, lengths, theta_conf, theta_margin, k)
    return committed, frame, model_arg


def gate_metrics(
    committed_c: np.ndarray, frame_c: np.ndarray, arg_c: np.ndarray,
    committed_f: np.ndarray, frame_f: np.ndarray, arg_f: np.ndarray,
    y: np.ndarray, last_flip: np.ndarray,
) -> dict[str, float]:
    """Recognition-level comparison of the causal path vs the full-span path."""
    top1_f = float((arg_f == y).mean())
    top1_c = float((arg_c == y).mean())
    committed_full = committed_f >= 0
    committed_caus = committed_c >= 0
    # THE DEPLOYMENT METRIC: the app shows the S7 COMMITTED prediction, so the recognition-level
    # question is whether the causal path commits CORRECT glosses as often as full-span (not just
    # the diagnostic mean-agg top-1). Accuracy = correct-commits / commits, per path.
    full_commit_acc = (
        float((committed_f[committed_full] == y[committed_full]).mean())
        if committed_full.any() else float("nan")
    )
    causal_commit_acc = (
        float((committed_c[committed_caus] == y[committed_caus]).mean())
        if committed_caus.any() else float("nan")
    )
    # of clips the full-span path commits, how often does causal commit the SAME class? (diagnostic)
    same = committed_full & committed_caus & (committed_c == committed_f)
    agreement = float(same.sum() / max(int(committed_full.sum()), 1))
    # late mirror flip: mirror last changed AT/AFTER the commit frame — post-commit, so diagnostic.
    late_flip = committed_full & (last_flip >= 0) & (last_flip >= frame_f)
    return {
        "full_commit_accuracy": full_commit_acc,
        "causal_commit_accuracy": causal_commit_acc,
        "commit_accuracy_delta": abs(full_commit_acc - causal_commit_acc),
        "full_top1": top1_f,
        "causal_top1": top1_c,
        "top1_delta": abs(top1_f - top1_c),
        "commit_agreement": agreement,
        "causal_commit_rate": float(committed_caus.mean()),
        "full_commit_rate": float(committed_full.mean()),
        "late_mirror_flip_rate": float(late_flip.sum() / max(int(committed_full.sum()), 1)),
        "any_mirror_flip_rate": float((last_flip >= 0).mean()),
    }


def _group_commit_acc(
    committed_c: np.ndarray, committed_f: np.ndarray, y: np.ndarray, mask: np.ndarray
) -> dict[str, float]:
    """Committed accuracy (full & causal) restricted to a clip group (e.g. left-dominant)."""
    cf, cc = mask & (committed_f >= 0), mask & (committed_c >= 0)
    fa = float((committed_f[cf] == y[cf]).mean()) if cf.any() else float("nan")
    ca = float((committed_c[cc] == y[cc]).mean()) if cc.any() else float("nan")
    return {"full": fa, "causal": ca, "delta": abs(fa - ca), "n_full_commits": int(cf.sum())}


def dominance_signer_breakdown(
    committed_c: np.ndarray, committed_f: np.ndarray, y: np.ndarray,
    offline_mirror: np.ndarray, pids: np.ndarray, min_commits: int = 10,
) -> dict[str, Any]:
    """Split the committed-accuracy delta by handedness (does the cost land on LEFT-dominant
    signers whose mirror the causal path sometimes gets wrong?) and find the worst signer (a low
    mean hiding one collapsed signer is a finding — eval-protocol)."""
    by_dom = {
        "left_dominant_mirrored": _group_commit_acc(committed_c, committed_f, y, offline_mirror),
        "right_or_symmetric": _group_commit_acc(committed_c, committed_f, y, ~offline_mirror),
    }
    worst_sid, worst_delta, worst_n = "", 0.0, 0
    for sid in sorted(set(pids.tolist())):
        g = _group_commit_acc(committed_c, committed_f, y, pids == sid)
        finite = g["delta"] == g["delta"]  # not NaN
        if g["n_full_commits"] >= min_commits and finite and g["delta"] > worst_delta:
            worst_sid, worst_delta, worst_n = str(sid), g["delta"], int(g["n_full_commits"])
    return {
        "by_dominance": by_dom,
        "worst_signer": {"id": worst_sid, "delta": worst_delta, "n_full_commits": worst_n},
    }


def run(smoke: bool) -> int:
    import tensorflow as tf

    cfg = yaml.safe_load(CONFIRM_CONFIG.read_text(encoding="utf-8"))
    temp, margin, k = float(cfg["temperature"]), float(cfg["theta_margin"]), int(cfg["k_stability"])
    model_dir = Path(cfg["model_dir"])
    theta_conf = _load_theta(model_dir, cfg)
    batch, n_dec = 64, 10

    if smoke:
        from model.model import build_streaming_classifier

        rng = np.random.default_rng(0)
        model = build_streaming_classifier(96, 258, 10)
        xc, xf, fm, lengths, y, last_flip, offline_mirror, pids = _syn(rng, 50)
    else:
        stream_dir = Path(cfg["features_dir"])
        causal_dir = stream_dir.parent / "features_causal"
        cpath, fpath = causal_dir / "test.npz", stream_dir / "test.npz"
        if not cpath.exists():
            print(f"[causal] {cpath} missing — run pipeline.features.streaming_causal --split test",
                  file=sys.stderr)
            return 2
        model = tf.keras.models.load_model(model_dir / "best.keras")
        dc = np.load(cpath, mmap_mode="r")
        df = np.load(fpath, mmap_mode="r")
        xc, xf = dc["X"], df["X"]  # memmaps
        fm = np.asarray(dc["frame_mask"])
        lengths = np.asarray(dc["lengths"])
        y = np.asarray(dc["y"])
        last_flip = np.asarray(dc["last_flip_frame"])
        if "offline_mirror" not in dc.files:
            print("[causal] features_causal missing offline_mirror — rebuild "
                  "(pipeline.features.streaming_causal --split test)", file=sys.stderr)
            return 2
        offline_mirror = np.asarray(dc["offline_mirror"])
        pids = np.asarray(dc["participant_ids"])
        if not np.array_equal(y, np.asarray(df["y"])):
            print("[causal] ALIGN ERROR: causal/streaming y differ — rebuild both", file=sys.stderr)
            return 2

    committed_c, frame_c, arg_c = commit_and_argmax(
        model, xc, fm, lengths, temp, theta_conf, margin, k, batch)
    committed_f, frame_f, arg_f = commit_and_argmax(
        model, xf, fm, lengths, temp, theta_conf, margin, k, batch)
    metrics: dict[str, Any] = gate_metrics(
        committed_c, frame_c, arg_c, committed_f, frame_f, arg_f, y, last_flip
    )
    metrics["feature_skew_deciles"] = feature_skew_deciles(xc, xf, fm, lengths, n_dec, batch)
    metrics["breakdown"] = dominance_signer_breakdown(
        committed_c, committed_f, y, offline_mirror, pids
    )

    # Deployment gate: causal commits correct glosses about as often as full-span, AND mean-agg
    # top-1 (secondary sanity) is preserved.
    ok = (metrics["commit_accuracy_delta"] <= MAX_COMMIT_ACC_DELTA
          and metrics["top1_delta"] <= MAX_TOP1_DELTA)
    out_path = model_dir / ("smoke" if smoke else "") / "causal_skew_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({**metrics, "gate_pass": ok}, indent=2), encoding="utf-8")
    _print(metrics, ok, out_path)
    return 0 if ok else 1


def _load_theta(model_dir: Path, cfg: dict) -> float:
    """Use the operating point eval.confirm chose on val; fall back to the strictest grid point."""
    report = model_dir / "confirm_report.json"
    if report.exists():
        return float(json.loads(report.read_text(encoding="utf-8"))["chosen_theta_conf"])
    return float(cfg["theta_conf_grid"][-1])


def _print(m: dict, ok: bool, out_path: Path) -> None:
    print("\n=== causal skew (test, cross-signer) - recognition gate ===")
    print("GATE (does causal COMMIT correct signs as well as full-span? = the app output):")
    print(f"  commit accuracy full/causal : {m['full_commit_accuracy']:.4f} / "
          f"{m['causal_commit_accuracy']:.4f}  (delta {m['commit_accuracy_delta']:.4f}, "
          f"gate <= {MAX_COMMIT_ACC_DELTA})")
    print(f"  clip top-1 full/causal      : {m['full_top1']:.4f} / {m['causal_top1']:.4f}  "
          f"(delta {m['top1_delta']:.4f}, gate <= {MAX_TOP1_DELTA})")
    print("diagnostics (not gated - explain the causal behavior):")
    print(f"  commit rate full/causal     : {m['full_commit_rate']:.3f} / "
          f"{m['causal_commit_rate']:.3f}")
    print(f"  commit agreement            : {m['commit_agreement']:.4f}  (~88% mirror ceiling)")
    print(f"  late mirror-flip rate       : {m['late_mirror_flip_rate']:.4f}  (post-commit, "
          f"doesn't change the committed gloss; any-flip {m['any_mirror_flip_rate']:.3f})")
    traj = "  ".join(f"{v:.3f}" for v in m["feature_skew_deciles"])
    print(f"  feature skew deciles        : {traj}")
    bd = m["breakdown"]
    left = bd["by_dominance"]["left_dominant_mirrored"]
    right = bd["by_dominance"]["right_or_symmetric"]
    ws = bd["worst_signer"]
    print("committed-accuracy by handedness (is the cost concentrated on left-dominant signers?):")
    print(f"  left-dominant (mirrored) : full {left['full']:.4f} / causal {left['causal']:.4f}  "
          f"(delta {left['delta']:.4f}, n={left['n_full_commits']})")
    print(f"  right/symmetric          : full {right['full']:.4f} / causal {right['causal']:.4f}  "
          f"(delta {right['delta']:.4f}, n={right['n_full_commits']})")
    print(f"  worst signer             : {ws['id']} delta {ws['delta']:.4f} "
          f"(n={ws['n_full_commits']})")
    print(f"GATE: {'PASS' if ok else 'FAIL'}\n-> {out_path}")


def _syn(rng: Any, n: int) -> tuple:
    xf = rng.standard_normal((n, 96, 258)).astype(np.float32)
    xc = xf + rng.standard_normal((n, 96, 258)).astype(np.float32) * 0.01  # tiny causal noise
    lengths = rng.integers(48, 97, n).astype(np.int32)
    fm = np.zeros((n, 96), bool)
    for i in range(n):
        fm[i, : lengths[i]] = True
    y = rng.integers(0, 10, n).astype(np.int32)
    last_flip = rng.integers(-1, 20, n).astype(np.int32)
    offline_mirror = rng.random(n) < 0.21  # ~21% mirrored, matching the real base rate
    pids = rng.choice(["P1", "P2", "P3"], size=n)
    return xc, xf, fm, lengths, y, last_flip, offline_mirror, pids


def main() -> int:
    p = argparse.ArgumentParser(description="AppHear 3 causal-param skew measurement (F19 gate)")
    p.add_argument("--smoke", action="store_true")
    args = p.parse_args()
    return run(args.smoke)


if __name__ == "__main__":
    raise SystemExit(main())
