"""Read-only oracle-context probe for the frozen S2-R2 TFLite model.

For every human-reviewed positive interval, compare S2 ACTIVE acquisition with
(a) the live rolling 61-observation prefix and (b) a fresh prefix that begins
k observations before the reviewed onset (an oracle reset; not deployable).
Uses the exact Android-normalized 378 features saved by the capture.
"""
import json
import sys
from pathlib import Path

import numpy as np
import tensorflow as tf

MODEL = Path(sys.argv[1])
RF = 61


def run(interp, rows):
    interp.resize_tensor_input(0, [1, len(rows), 378], strict=False)
    interp.allocate_tensors()
    interp.set_tensor(interp.get_input_details()[0]["index"], rows[None].astype(np.float32))
    interp.invoke()
    logits = interp.get_tensor(interp.get_output_details()[0]["index"])[0]
    e = np.exp(logits - logits.max())
    return e / e.sum()


def main():
    interp = tf.lite.Interpreter(model_path=str(MODEL))
    for session in sys.argv[2:]:
        s = Path(session)
        obs = [json.loads(line) for line in open(s / "observations.jsonl", encoding="utf-8")]
        n = len(obs)
        x = np.fromfile(s / "s2_exact_parity" / "android_normalized.f32", dtype=np.float32).reshape(n, 378)
        src = np.fromfile(s / "s2_exact_parity" / "source_index.i32", dtype=np.int32)
        pos = {int(v): i for i, v in enumerate(src)}
        labels = json.load(open(s / "transition_review" / "human_boundaries.json", encoding="utf-8"))
        print(f"session {s.name}")
        for sign in labels["signs"]:
            if sign["start_index"] is None:
                continue
            a, b = pos[sign["start_index"]], pos[sign["end_index"]]
            res = {}
            for label, start_fn in (("rolling61", lambda t: max(0, t - RF + 1)),
                                    ("fresh@onset-4", lambda t: max(0, a - 4, t - RF + 1)),
                                    ("fresh@onset-2", lambda t: max(0, a - 2, t - RF + 1)),
                                    ("fresh@onset", lambda t: max(a, t - RF + 1))):
                act = 0
                pmax = 0.0
                for t in range(a, b + 1):
                    p = run(interp, x[start_fn(t): t + 1])
                    act += int(np.argmax(p) == 1)
                    pmax = max(pmax, float(p[1]))
                res[label] = f"{act}/{b - a + 1} (max {pmax:.2f})"
            print(f"  {sign['condition']:18s} {sign['gloss']:6s} #{sign['ordinal']} {sign['judgment']:12s} ACTIVE obs: " +
                  "  ".join(f"{k}={v}" for k, v in res.items()))


if __name__ == "__main__":
    main()
