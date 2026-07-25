"""Encoder-upgrade STEP 1 (context/encoder-upgrade.md §5.1) — INT8 export smoke-test of the
ST-GCN candidate BEFORE any training. Builds the full-size untrained model, converts it through
the SAME INT8 path as deploy/export_tflite.py, and verifies: conversion succeeds, the interpreter
instantiates (XNNPACK), the frozen I/O contract holds ([1,96,258] -> [1,96,C]), and outputs are
finite softmax rows. Also benchmarks desktop ms/invoke for GCN vs the DEPLOYED conversational TCN
to project device latency (device runs the TCN at a measured 0.5 ms -> predicted GCN ms =
0.5 x ratio). PASS here = proceed to the device latency probe; FAIL = matmul rewrite or candidate B.

  .venv\\Scripts\\python.exe -m deploy.smoke_gcn_export
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from deploy.export_tflite import _convert, _tflite_infer  # the REAL export path
from model.model_gcn import build_stgcn

DEPLOYED_TCN = Path(
    "F:/ASL DATASET/ASL CITIZEN/derived/apphear3/runs/tcn_streaming_conversational_fps_v30/streaming.tflite"
)


def _bench(tflite_bytes: bytes, x: np.ndarray, n: int = 20) -> float:
    import tensorflow as tf

    interp = tf.lite.Interpreter(model_content=tflite_bytes, num_threads=2)  # app uses 2 threads
    interp.allocate_tensors()
    in_d = interp.get_input_details()[0]
    interp.set_tensor(in_d["index"], x)
    interp.invoke()  # warmup
    t0 = time.perf_counter()
    for _ in range(n):
        interp.invoke()
    return (time.perf_counter() - t0) / n * 1e3


def main() -> int:
    rng = np.random.default_rng(0)
    t, f, c = 96, 258, 236

    from model.model_gcn import UPPER51

    print("[smoke] building candidate-A untrained ST-GCN (half-width, early strides, upper51) ...")
    model = build_stgcn(
        t, f, c,
        channels=(32, 32, 32, 32, 64, 64, 64, 128, 128, 128),
        strides={0: 2, 4: 2},
        keypoint_subset=UPPER51,
    )
    print(f"[smoke] params: {model.count_params():,}")

    print("[smoke] converting through the production INT8 path ...")
    calib = rng.standard_normal((32, t, f)).astype(np.float32)
    tflite_bytes = _convert(model, calib)
    print(f"[smoke] converted OK: {len(tflite_bytes) / 1024:.0f} KB")

    x = rng.standard_normal((2, t, f)).astype(np.float32)
    out = _tflite_infer(tflite_bytes, x)
    assert out.shape == (2, t, c), f"contract violated: {out.shape} != (2,{t},{c})"
    rows = out.reshape(-1, c)
    assert np.all(np.isfinite(rows)), "non-finite outputs"
    sums = rows.sum(axis=1)
    # loose tolerance ON PURPOSE: an UNTRAINED model outputs a near-uniform softmax (236 x ~0.004),
    # where INT8 rounding accumulates a few % of drift in the row sum. Fidelity of the TRAINED
    # model is gated later by export_tflite's mean-abs-prob-diff <= 0.005 — not here.
    assert np.allclose(sums, 1.0, atol=0.1), f"not softmax rows (sum range {sums.min():.3f}..{sums.max():.3f})"
    tile_dev = float(np.abs(out - out[:, :1, :]).max())
    assert tile_dev < 1e-5, f"clip posterior not tiled uniformly (max dev {tile_dev})"
    print(f"[smoke] I/O contract holds: [1,{t},{f}] -> [1,{t},{c}], softmax rows, tiled ({tile_dev:.1e})")

    one = x[:1]
    gcn_ms = _bench(tflite_bytes, one)
    line = f"[smoke] desktop GCN: {gcn_ms:.1f} ms/invoke"
    if DEPLOYED_TCN.exists():
        tcn_ms = _bench(DEPLOYED_TCN.read_bytes(), one)
        ratio = gcn_ms / max(tcn_ms, 1e-9)
        line += (f" | deployed TCN: {tcn_ms:.2f} ms | ratio {ratio:.0f}x"
                 f" -> predicted device ~{0.5 * ratio:.0f} ms/tick (gate: <=20)")
    print(line)
    print("[smoke] PASS — proceed to the on-device latency probe (encoder-upgrade.md §5.2)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
