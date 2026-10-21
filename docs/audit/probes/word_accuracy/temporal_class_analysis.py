"""Is temporal information the limit? Per-class WORD accuracy on identical clips at real densities.

Every condition uses only real Candidate01 observations of the same source clip (no interpolation
or duplication): the runtime-bounded window (span +/-250 ms through the materializer) of the
full-length raw re-sampled at ALL frames (~33 ms), 100 / 133 / 200 / 266.6 / 400 ms with two phases,
and IRREGULAR (phone-like spacing: 200-267 ms with occasional 400 ms gaps, seeded) at the same
mean as 230 ms. Populations: DEV (816 clips, selection-exposed) and the EVAL-role signers of both
reviewed Sem-Lex packages (never trained on). TRAIN span fit at ALL vs 266 ms tells information
loss apart from cross-signer generalization (in-sample). Per class (clip is the unit):

  TEMPORAL        recall at ALL frames - recall at 200 ms >= 0.25: the cue exists in denser real
                  observations and is lost at the phone rate
  GENERALIZATION  recall at ALL frames <= 0.35 while TRAIN fit at ALL frames >= 0.8: the model
                  separates the class in-sample at full density but not on new signers
  INCONSISTENT    TRAIN fit at ALL frames < 0.6: not separable even in-sample at full density
                  (variant mixture, confusable forms or label inconsistency)
  WEAK_HANDS      mean accepted-hand fraction < 0.45 (perception supplies little hand evidence)
Writes temporal_class_analysis.json next to this file.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics import heldout_dev_e2e as e2e  # noqa: E402
from eval.runtime_diagnostics import word_vocabulary_eval as wve  # noqa: E402
from pipeline.perception_vnext.recognition_schema import (  # noqa: E402
    load_raw_sequence,
    select_nearest_unique,
)

E = Path("F:/ASL DATASET/5. Apphear3")
RU = E / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
MODELS = {"frozen": RU / "tcn_v2_run_01/best.keras", "BLEND_02": RU / "word_blend_02/blend.keras"}
INTERVALS = {"ALL": None, "100": 100.0, "133": 133.3, "200": 200.0, "266": 266.616, "400": 400.0}
PAIRS = [
    ("CHAIR", "SIT"),
    ("CAR", "DRIVE"),
    ("NOW", "TODAY"),
    ("MUCH", "TOOMUCH"),
    ("STAND2", "JUMP"),
    ("HAPPY", "PLEASE"),
    ("SORRY", "LOVE"),
    ("FIND", "PICK"),
    ("PERSON", "PEOPLE"),
    ("BAD", "GOOD"),
]


def irregular(t: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    targets, x = [], float(t[0]) + float(rng.uniform(0, 230))
    while x <= t[-1]:
        targets.append(x)
        x += 400.0 if rng.random() < 0.08 else float(rng.uniform(200.0, 267.0))
    return select_nearest_unique(t, np.asarray(targets)) if targets else np.zeros(0, np.int32)


def clips(root: Path) -> list[dict]:
    from pipeline.detect.candidate01_span import candidate01_span
    from pipeline.detect.config import load_config

    out = []
    for c in json.loads((root / e2e.MANIFEST).read_text(encoding="utf-8"))["clips"]:
        if c["span_valid"]:
            out.append(
                {
                    "pop": "DEV",
                    "gloss": c["gloss"],
                    "signer": c["signer"],
                    "raw": root / c["raw_path"],
                    "on": c["span_onset_index"],
                    "off": c["span_release_index"],
                }
            )
    cfg = load_config(REPO / "pipeline/config/detect.yaml")
    for manifest in (wve.SEMLEX, wve.SEMLEX2):
        for c in json.loads((root / manifest).read_text(encoding="utf-8"))["clips"]:
            if wve.semlex_role(c["signer"]) != "EVAL":
                continue
            raw = load_raw_sequence(root / c["raw_path"])
            span = candidate01_span(raw, cfg, 0.4)
            if span.valid:
                out.append(
                    {
                        "pop": "SEMLEX_EVAL",
                        "gloss": c["gloss"],
                        "signer": c["signer"],
                        "raw": root / c["raw_path"],
                        "on": span.onset,
                        "off": span.release,
                    }
                )
    return out


def main() -> None:
    import tensorflow as tf

    names = wve.glosses(E)
    index = {g: i for i, g in enumerate(names)}
    models = {
        k: tf.keras.models.load_model(p, compile=False, safe_mode=True) for k, p in MODELS.items()
    }
    cl = clips(E)
    raws = [load_raw_sequence(c["raw"]) for c in cl]
    y = np.asarray([index[c["gloss"]] for c in cl])
    hand = np.asarray(
        [
            float(np.mean(np.asarray(r.hand_observed, bool)[c["on"] : c["off"] + 1].any(axis=1)))
            for c, r in zip(cl, raws, strict=True)
        ]
    )
    correct: dict[str, dict[str, np.ndarray]] = defaultdict(dict)
    obs: dict[str, float] = {}
    pred_top1: dict[str, dict[str, list[np.ndarray]]] = defaultdict(lambda: defaultdict(list))
    conditions = list(INTERVALS) + ["IRREGULAR"]
    for name in conditions:
        bank = wve.Bank()
        phases = 1 if name == "ALL" else 2
        for k in range(phases):
            for c, raw in zip(cl, raws, strict=True):
                t = np.asarray(raw.timestamp_ms, np.float64)
                if name == "ALL":
                    idx = np.arange(len(t), dtype=np.int32)
                elif name == "IRREGULAR":
                    idx = irregular(t, 9300 + k * 100000 + len(t))
                else:
                    step = INTERVALS[name]
                    idx = select_nearest_unique(
                        t, np.arange(t[0] + k * step / 2, t[-1] + 1e-6, step)
                    )
                sub = wve.subset_raw(raw, idx)
                a, b = wve.span_in(idx, c["on"], c["off"])
                bank.add(f"p{k}", wve.ctx_window(sub, a, b), {})
        obs[name] = float(np.median([m["observations"] for m in bank.meta["p0"]]))
        for model_name, model in models.items():
            preds = [wve.predict(model, bank.rows[f"p{k}"]).argmax(1) for k in range(phases)]
            correct[model_name][name] = np.mean([p == y for p in preds], axis=0)
            pred_top1[model_name][name] = preds
        print(
            name,
            "obs",
            obs[name],
            {m: round(float(correct[m][name].mean()), 4) for m in models},
            flush=True,
        )
    # in-sample TRAIN fit at full density vs phone rate (span only)
    train = [json.loads(line) for line in (E / wve.INDEX).open(encoding="utf-8")]
    train = [r for r in train if r["split"] == "train"]
    traw = [load_raw_sequence(Path(r["raw_path"])) for r in train]
    ty = np.asarray([index[r["canonical_gloss"]] for r in train])
    tfit: dict[str, dict[str, dict[str, float]]] = {}
    for model_name, model in models.items():
        tfit[model_name] = {}
        for name, step in (("ALL", None), ("266", 266.616)):
            bank = wve.Bank()
            for raw in traw:
                bank.add("t", raw if step is None else wve.at_cadence(raw, step, 0.0)[0], {})
            ok = wve.predict(model, bank.rows["t"]).argmax(1) == ty
            per = defaultdict(list)
            for r, o in zip(train, ok, strict=True):
                per[r["canonical_gloss"]].append(float(o))
            tfit[model_name][name] = {g: float(np.mean(v)) for g, v in per.items()}
    out: dict = {
        "clips": len(cl),
        "populations": {p: int(sum(c["pop"] == p for c in cl)) for p in ("DEV", "SEMLEX_EVAL")},
        "median_window_observations": obs,
        "models": {},
    }
    for model_name in models:
        summary = {}
        for name in conditions:
            v = correct[model_name][name]
            summary[name] = {
                pop: round(float(v[[c["pop"] == pop for c in cl]].mean()), 4)
                for pop in ("DEV", "SEMLEX_EVAL")
            }
            summary[name]["ALL_POPS"] = round(float(v.mean()), 4)
        classes = {}
        for g in names:
            sel = y == index[g]
            if not sel.any():
                continue
            rec = {
                name: round(float(correct[model_name][name][sel].mean()), 3) for name in conditions
            }
            row = {
                "clips": int(sel.sum()),
                "signers": len({c["signer"] for c, s in zip(cl, sel, strict=True) if s}),
                "recall": rec,
                "hand": round(float(hand[sel].mean()), 3),
                "train_fit_all": round(tfit[model_name]["ALL"].get(g, float("nan")), 3),
                "train_fit_266": round(tfit[model_name]["266"].get(g, float("nan")), 3),
            }
            labels = []
            if rec["ALL"] - rec["200"] >= 0.25:
                labels.append("TEMPORAL")
            if rec["ALL"] <= 0.35 and row["train_fit_all"] >= 0.8:
                labels.append("GENERALIZATION")
            if row["train_fit_all"] < 0.6:
                labels.append("INCONSISTENT")
            if row["hand"] < 0.45:
                labels.append("WEAK_HANDS")
            row["labels"] = labels
            classes[g] = row
        pairs = {}
        for a, b in PAIRS:
            if a not in index or b not in index:
                continue
            row = {}
            for name in conditions:
                conf = 0
                tot = 0
                for k_pred in pred_top1[model_name][name]:
                    for yy, pp in zip(y, k_pred, strict=True):
                        if yy in (index[a], index[b]):
                            tot += 1
                            conf += int(pp in (index[a], index[b]) and pp != yy)
                row[name] = f"{conf}/{tot}"
            pairs[f"{a}/{b}"] = row
        out["models"][model_name] = {
            "summary": summary,
            "classes": classes,
            "pairs": pairs,
            "train_fit_mean": {
                k: round(float(np.mean(list(v.values()))), 4) for k, v in tfit[model_name].items()
            },
        }
    Path(__file__).with_name("temporal_class_analysis.json").write_text(
        json.dumps(out, indent=1) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
