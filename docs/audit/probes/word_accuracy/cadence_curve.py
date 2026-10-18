"""WORD accuracy as a function of the observation interval (how much faster perception would buy).

DEV runtime-bounded windows (span +/-250 ms through the materializer, full-length Candidate01
raw) re-sampled at 100 / 133 / 200 / 266.6 / 400 ms with two phases, scored with the frozen
recognizer and WORD_BLEND_01; plus the in-sample TRAIN span fit at the same intervals (800 ASL
Citizen TRAIN clips, fixed seed) to separate information loss from generalization. Per-clip
averages over phases. Writes cadence_curve.json next to this file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics import heldout_dev_e2e as e2e  # noqa: E402
from eval.runtime_diagnostics import word_vocabulary_eval as wve  # noqa: E402
from pipeline.perception_vnext.recognition_schema import load_raw_sequence  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
RU = E / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
INTERVALS = (100.0, 133.3, 200.0, 266.616, 400.0)
MODELS = {"frozen": RU / "tcn_v2_run_01/best.keras", "BLEND_01": RU / "word_blend_01/blend.keras"}


def main() -> None:
    import tensorflow as tf

    names = wve.glosses(E)
    index = {g: i for i, g in enumerate(names)}
    models = {
        k: tf.keras.models.load_model(p, compile=False, safe_mode=True) for k, p in MODELS.items()
    }
    clips = [
        c
        for c in json.loads((E / e2e.MANIFEST).read_text(encoding="utf-8"))["clips"]
        if c["span_valid"]
    ]
    raws = [load_raw_sequence(E / c["raw_path"]) for c in clips]
    y = np.asarray([index[c["gloss"]] for c in clips])
    train = [json.loads(line) for line in (E / wve.INDEX).open(encoding="utf-8")]
    train = [r for r in train if r["split"] == "train" and r["source_id"] == "ASL_CITIZEN"]
    rng = np.random.default_rng(0)
    train = [train[i] for i in rng.choice(len(train), 800, replace=False)]
    train_raws = [load_raw_sequence(Path(r["raw_path"])) for r in train]
    ty = np.asarray([index[r["canonical_gloss"]] for r in train])
    out: dict = {"dev_clips": len(clips), "train_clips": len(train), "curve": {}}
    for interval in INTERVALS:
        bank = wve.Bank()
        for k in range(2):
            for c, raw in zip(clips, raws, strict=True):
                sub, idx = wve.at_cadence(raw, interval, k * interval / 2)
                a, b = wve.span_in(idx, c["span_onset_index"], c["span_release_index"])
                bank.add(f"dev{k}", wve.ctx_window(sub, a, b), {})
            for raw in train_raws:
                bank.add(f"train{k}", wve.at_cadence(raw, interval, k * interval / 2)[0], {})
        obs = float(np.median([m["observations"] for m in bank.meta["dev0"]]))
        row = {"dev_window_observations_median": obs}
        for name, model in models.items():
            dev = np.mean(
                [wve.predict(model, bank.rows[f"dev{k}"]).argmax(1) == y for k in range(2)], axis=0
            )
            fit = np.mean(
                [wve.predict(model, bank.rows[f"train{k}"]).argmax(1) == ty for k in range(2)],
                axis=0,
            )
            row[name] = {
                "dev_runtime_window_top1": round(float(dev.mean()), 4),
                "train_span_fit": round(float(fit.mean()), 4),
            }
        out["curve"][f"{interval:g}ms"] = row
        print(f"{interval:g}ms", json.dumps(row), flush=True)
    Path(__file__).with_name("cadence_curve.json").write_text(
        json.dumps(out, indent=1) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
