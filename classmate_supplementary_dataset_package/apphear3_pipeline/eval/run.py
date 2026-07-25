"""Cross-signer eval runner: load a trained model, predict on the held-out split, and emit the
report (JSON + printed). Report-only — no hardcoded pass/fail bar; the numbers are the gate.

  python -m eval.run                                  # test split, model from train.yaml output_dir
  python -m eval.run --model path/to/best.keras
  python -m eval.run --smoke                          # synthetic model+data; validates the harness

Real eval runs after the developer trains (needs a real checkpoint + full-split features)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from model.train import load_train_config

from .harness import evaluate

DEFAULT_TRAIN_CONFIG = Path(__file__).resolve().parents[1] / "model" / "config" / "train.yaml"


def _load_vocab_rev(features_dir: Path) -> dict[int, str]:
    vpath = features_dir / "vocab.json"
    if not vpath.exists():
        return {}
    vocab: dict[str, int] = json.loads(vpath.read_text(encoding="utf-8"))
    return {i: g for g, i in vocab.items()}


def _print_report(report: dict[str, Any], rev: dict[int, str]) -> None:
    o, c = report["overall"], report["calibration"]
    print("\n=== cross-signer eval (test) ===")
    print(f"n={report['n_test']} across {report['n_signers']} signers")
    print(
        f"top1={o['top1']:.3f}  top5={o['top5']:.3f}  "
        f"macro-top1-per-signer={o['macro_top1_per_signer']:.3f}"
    )
    print(f"calibration: T={c['temperature']:.3f}  ECE {c['ece_pre']:.3f} -> {c['ece_post']:.3f}")
    print(
        "per-signer top1: "
        + ", ".join(f"{pid}={m['top1']:.2f}(n{m['n']})" for pid, m in report["per_signer"].items())
    )
    if report["most_confused"]:
        conf = ", ".join(
            f"{rev.get(t, t)}->{rev.get(p, p)}x{n}" for t, p, n in report["most_confused"]
        )
        print(f"most confused: {conf}")


def run(model_path: Path | None, calib_split: str, test_split: str, smoke: bool) -> int:
    import tensorflow as tf

    from model.data import load_split

    cfg = load_train_config(DEFAULT_TRAIN_CONFIG)
    if smoke:
        from model.model import build_classifier

        rng = np.random.default_rng(0)
        t, f, c = 64, 258, 10
        model = build_classifier(t, f, num_classes=c)
        xv, yv = rng.standard_normal((40, t, f)).astype(np.float32), rng.integers(0, c, 40)
        xt, yt = rng.standard_normal((60, t, f)).astype(np.float32), rng.integers(0, c, 60)
        pt = rng.choice(["P1", "P2", "P3"], size=60)
        val_probs, test_probs = model.predict(xv, verbose=0), model.predict(xt, verbose=0)
        out_dir, rev = cfg.output_dir / "smoke", {}
    else:
        mp = model_path or (cfg.output_dir / "best.keras")
        if not mp.exists():
            print(f"[eval] no model at {mp} — train first (python -m model.train)", file=sys.stderr)
            return 2
        model = tf.keras.models.load_model(mp)
        xv, yv, _ = load_split(cfg.features_dir, calib_split)
        xt, yt, pt = load_split(cfg.features_dir, test_split)
        val_probs = model.predict(xv, batch_size=cfg.batch_size, verbose=0)
        test_probs = model.predict(xt, batch_size=cfg.batch_size, verbose=0)
        out_dir, rev = cfg.output_dir, _load_vocab_rev(cfg.features_dir)

    report = evaluate(val_probs, yv, test_probs, yt, np.asarray(pt))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"eval_{test_split}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _print_report(report, rev)
    print(f"-> {out_path}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="AppHear 3 cross-signer eval harness")
    p.add_argument("--model", type=Path, default=None)
    p.add_argument("--calib-split", default="val", choices=["train", "val", "test"])
    p.add_argument("--test-split", default="test", choices=["train", "val", "test"])
    p.add_argument("--smoke", action="store_true")
    args = p.parse_args()
    return run(args.model, args.calib_split, args.test_split, args.smoke)


if __name__ == "__main__":
    raise SystemExit(main())
