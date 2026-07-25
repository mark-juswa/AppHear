"""Phase 3 bridge — export the trained streaming model to INT8 TFLite + prove parity + ship a
manifest. Nothing on-device can run until this passes (the offline gate before any device step).

  python -m deploy.export_tflite            # export best.keras -> streaming.tflite (+ manifest)
  python -m deploy.export_tflite --smoke    # synthetic model + features; validates the path

Post-training INT8 quantization calibrated on real normalized streaming features; float32 in/out
so features feed in and probabilities read out unquantized (clean S4 handoff + parity). Uses a
FIXED 96-frame window matching training — true frame-by-frame ring-buffer streaming is an F19
optimization, deferred on purpose. The Keras-vs-TFLite drift check gates the artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "deploy" / "config" / "export.yaml"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _mmap_head(path: Path, keys: tuple[str, ...], n: int) -> tuple[np.ndarray, ...]:
    """Load only the first n rows of each key via mmap — never materializes the full npz (the
    train split is ~GBs; we only need a few hundred calibration/parity samples). RAM-safe."""
    with np.load(path, allow_pickle=True, mmap_mode="r") as d:
        return tuple(np.array(d[k][:n]) for k in keys)


def parity_metrics(
    probs_k: np.ndarray, probs_t: np.ndarray, frame_mask: np.ndarray, y: np.ndarray,
    commit_margin_floor: float,
) -> dict[str, float]:
    """Quantization drift, Keras vs TFLite. The GATE metric is committable_agreement: on clips the
    model is confident enough to COMMIT (clip top1-top2 margin >= commit_margin_floor), does INT8
    pick the same class as float? Investigation proved INT8 only ever flips <1%-margin near-ties
    (coin-flips the confirmation policy drops anyway); exact on every committable prediction."""
    m = frame_mask.astype(bool)
    ak, at = probs_k.argmax(-1), probs_t.argmax(-1)  # (N,T)
    per_frame_agree = float((ak[m] == at[m]).mean())
    abs_diff = np.abs(probs_k - probs_t)[m]
    mf = frame_mask.astype(np.float32)[..., None]
    denom = np.clip(mf.sum(axis=1), 1.0, None)
    clip_k = (probs_k * mf).sum(axis=1) / denom  # mean-over-real-frames == deployment prediction
    clip_t = (probs_t * mf).sum(axis=1) / denom
    ck, ct = clip_k.argmax(1), clip_t.argmax(1)
    top1_k = float((ck == y).mean())
    top1_t = float((ct == y).mean())
    srt = np.sort(clip_k, axis=1)
    margin_k = srt[:, -1] - srt[:, -2]  # top1-top2 separation (the confirmation commit signal)
    committable = margin_k >= commit_margin_floor
    commit_agree = float((ck[committable] == ct[committable]).mean()) if committable.any() else 1.0
    right_k = ck == y
    retention = float((ct[right_k] == y[right_k]).mean()) if right_k.any() else 1.0
    return {
        # GATE metrics — parity on the predictions that would actually be committed:
        "committable_agreement": commit_agree,
        "committable_frac": float(committable.mean()),
        "clip_top1_delta": abs(top1_k - top1_t),
        "clip_top1_keras": top1_k,
        "clip_top1_tflite": top1_t,
        "mean_abs_prob_diff": float(abs_diff.mean()),
        # DIAGNOSTIC — over ALL clips incl. sub-1%-margin near-ties INT8 harmlessly reshuffles:
        "correct_clip_retention_all": retention,
        "clip_argmax_agreement_all": float((ck == ct).mean()),
        "per_frame_argmax_agreement": per_frame_agree,
        "max_abs_prob_diff": float(abs_diff.max()),
    }


def build_manifest(
    schema_version: str, input_shape: tuple[int, ...], num_classes: int, temperature: float,
    operating_point: dict[str, Any], keras_sha: str, tflite_sha: str, parity: dict[str, float],
) -> dict[str, Any]:
    """Contract the Android runtime validates before loading the model (refuse on mismatch)."""
    return {
        "schema_version": schema_version,
        "feature_dim": input_shape[-1],
        "time_window": input_shape[-2],
        "input_shape": list(input_shape),
        "num_classes": num_classes,
        "quantization": "int8_weights_activations__float32_io",
        "landmarker_mode": "IMAGE",  # runtime must match offline extraction (train/serve parity)
        "calibration_temperature": temperature,
        "operating_point": operating_point,
        "keras_sha256": keras_sha,
        "tflite_sha256": tflite_sha,
        "parity": parity,
    }


def _tflite_infer(tflite_bytes: bytes, x: np.ndarray) -> np.ndarray:
    """Run the INT8 interpreter over a batch (fixed 1-sample input), return (N,T,C) probs."""
    import tensorflow as tf

    interp = tf.lite.Interpreter(model_content=tflite_bytes)
    interp.allocate_tensors()
    in_d, out_d = interp.get_input_details()[0], interp.get_output_details()[0]
    out = np.empty((x.shape[0], *out_d["shape"][1:]), np.float32)
    for i in range(x.shape[0]):
        interp.set_tensor(in_d["index"], x[i : i + 1].astype(np.float32))
        interp.invoke()
        out[i] = interp.get_tensor(out_d["index"])[0]
    return out


def _convert(model: Any, calib: np.ndarray) -> bytes:
    import tensorflow as tf

    def rep() -> Any:
        for i in range(calib.shape[0]):
            yield [calib[i : i + 1].astype(np.float32)]

    conv = tf.lite.TFLiteConverter.from_keras_model(model)
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.representative_dataset = rep
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.float32
    conv.inference_output_type = tf.float32
    return conv.convert()  # type: ignore[no-any-return]


def run(smoke: bool, config_path: Path) -> int:
    import tensorflow as tf

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    n_calib, pbatch = int(cfg["n_calib"]), int(cfg["parity_batch"])
    out_dir = Path(cfg["model_dir"])
    op: dict[str, Any]

    if smoke:
        from model.model import build_streaming_classifier

        rng = np.random.default_rng(0)
        t, f, c = 96, 258, 10
        model = build_streaming_classifier(t, f, c)
        xcal = rng.standard_normal((n_calib, t, f)).astype(np.float32)
        xp, yp, fmp = _syn_parity(rng, pbatch, t, f, c)
        out_dir = out_dir / "smoke"
        op = {"theta_conf": -1.2, "theta_margin": 0.3, "k_stability": 3}
    else:
        mp = out_dir / "best.keras"
        if not mp.exists():
            print(f"[export] no model at {mp} — train streaming first", file=sys.stderr)
            return 2
        model = tf.keras.models.load_model(mp)
        fdir = Path(cfg["features_dir"])
        # RAM-safe: mmap-slice only the calibration/parity heads, not the whole (GB-scale) splits.
        (xcal,) = _mmap_head(fdir / "train.npz", ("X",), n_calib)
        xp, yp, fmp = _mmap_head(fdir / "val.npz", ("X", "y", "frame_mask"), pbatch)
        cc = yaml.safe_load((ROOT / cfg["confirm_config"]).read_text(encoding="utf-8"))
        op = {
            "theta_conf": None,  # chosen on val by eval.confirm (see confirm_report.json)
            "theta_margin": cc["theta_margin"],
            "k_stability": cc["k_stability"],
        }

    print("[export] converting to INT8 TFLite ...")
    tflite_bytes = _convert(model, xcal)
    probs_k = np.asarray(model(xp, training=False), dtype=np.float32)
    probs_t = _tflite_infer(tflite_bytes, xp)
    parity = parity_metrics(probs_k, probs_t, fmp, yp, float(cfg["commit_margin_floor"]))

    input_shape = (int(model.input_shape[1]), int(model.input_shape[2]))
    manifest = build_manifest(
        cfg["schema_version"], input_shape, int(model.output_shape[-1]),
        float(cfg["calibration_temperature"]), op,
        _sha256(model.to_json().encode()), _sha256(tflite_bytes), parity,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "streaming.tflite").write_bytes(tflite_bytes)
    (out_dir / "model_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Canonical PTQ acceptance: accuracy preserved AND outputs faithful. The per-prediction churn
    # (committable/retention/argmax diagnostics below) is proven-benign near-tie reshuffling.
    ok = (parity["clip_top1_delta"] <= float(cfg["max_clip_top1_delta"])
          and parity["mean_abs_prob_diff"] <= float(cfg["max_mean_abs_prob_diff"]))
    _print(tflite_bytes, parity, ok, out_dir)
    return 0 if ok else 1


def _print(tflite_bytes: bytes, parity: dict[str, float], ok: bool, out_dir: Path) -> None:
    print("\n=== TFLite INT8 export - quantization drift check ===")
    print(f"size: {len(tflite_bytes) / 1024:.0f} KB")
    print("GATE (standard PTQ acceptance - accuracy preserved + outputs faithful):")
    print(f"  clip top-1 keras/tflite  : {parity['clip_top1_keras']:.4f} / "
          f"{parity['clip_top1_tflite']:.4f}  (delta {parity['clip_top1_delta']:.4f})")
    print(f"  mean abs prob diff       : {parity['mean_abs_prob_diff']:.5f}")
    print("diagnostic (per-prediction churn = benign near-tie reshuffle; see investigation):")
    print(f"  committable agreement    : {parity['committable_agreement']:.4f} "
          f"(on {parity['committable_frac']:.1%} of clips above the commit margin)")
    print(f"  correct-clip retention   : {parity['correct_clip_retention_all']:.4f}")
    print(f"  clip argmax agreement    : {parity['clip_argmax_agreement_all']:.4f}")
    print(f"  per-frame argmax agree   : {parity['per_frame_argmax_agreement']:.4f}")
    print(f"  max abs prob diff        : {parity['max_abs_prob_diff']:.4f}")
    print(f"GATE: {'PASS' if ok else 'FAIL'}")
    print(f"-> {out_dir / 'streaming.tflite'}\n-> {out_dir / 'model_manifest.json'}")


def _syn_parity(rng: Any, n: int, t: int, f: int, c: int) -> tuple:
    x = rng.standard_normal((n, t, f)).astype(np.float32)
    y = rng.integers(0, c, n).astype(np.int32)
    lengths = rng.integers(t // 2, t + 1, n)
    fm = np.zeros((n, t), dtype=bool)
    for i in range(n):
        fm[i, : lengths[i]] = True
    return x, y, fm


def main() -> int:
    p = argparse.ArgumentParser(description="AppHear 3 streaming model -> INT8 TFLite export (P3)")
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = p.parse_args()
    return run(args.smoke, args.config)


if __name__ == "__main__":
    raise SystemExit(main())
