"""Saved B2 checkpoint references for zero-visual mobile parity; no model export/training."""
from __future__ import annotations

import json
import os
import struct

import numpy as np

from tools.fingerspelling.android_export import OUT


def main() -> None:
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    import tensorflow as tf

    from model.fingerspelling_residual_execution import base_model

    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    b2 = base_model(tf)
    directory = OUT / "parity_assets/fingerspelling_fixtures"
    cases = json.loads((directory / "cases.json").read_text())
    for case in cases["sequence_cases"]:
        with np.load(OUT / case["fixture"]) as data:
            x = data["packed"].copy()
        x[:, 405:] = 0
        mask: np.ndarray = np.ones((1, len(x), 1), np.float32)
        reference = b2([x[None, :, :405], mask], training=False).numpy()[0]
        with (directory / (case["fixture"] + ".b2.bin")).open("wb") as stream:
            stream.write(struct.pack(">i", len(x)))
            stream.write(x.astype(">f4").tobytes())
            stream.write(reference.astype(">f4").tobytes())
    print(json.dumps({"status": "FROZEN_B2_FALLBACK_REFERENCES_READY", "cases": 6}))


if __name__ == "__main__":
    main()
