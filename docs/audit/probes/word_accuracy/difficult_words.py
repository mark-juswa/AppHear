"""Which vocabulary classes stay hard, and why (frozen, WORD_BLEND_01, WORD_BLEND_02).

Unit of evidence is the clip: the four runtime-window phases of a clip are averaged into one
per-clip score, so repeated views are not counted as independent. Populations: DEV (5 signers,
selection-exposed) and Sem-Lex EVAL (13 signers, never trained on). Per class:
  recall_real    per-clip runtime-window recall (DEV + Sem-Lex EVAL)
  recall_dense   dense span recall on the same clips (the training view)
  hand           mean accepted-hand fraction of the class's runtime windows
  train_fit      TRAIN recall at 3.75 fps (in-sample: can the model fit it at phone cadence?)
  partner        the most frequent wrong prediction and its share of the class's errors
Hard = recall_real <= 0.3. Each hard class gets every applicable label:
  WEAK_HANDS      hand < 0.45 (perception supplies little hand evidence)
  CADENCE         recall_dense - recall_real >= 0.25 (lost when sampled at phone rate)
  LOW_FIT         train_fit < 0.6 (not separable at phone cadence even on training clips)
  PAIR            >= 40% of errors go to one partner (a specific confusion)
  THIN_COVERAGE   fewer than 12 TRAIN signers
Writes difficult_words.json next to this file.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics import word_vocabulary_eval as wve  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
MODELS = ("frozen", "BLEND_01", "BLEND_02")
PHASES = [f"ctx_c375_p{k}" for k in range(4)]


def main() -> None:
    names = wve.glosses(E)
    index = {g: i for i, g in enumerate(names)}
    meta = {
        p: wve.load_bank(E / wve.OUT / f"bank_{p}.npz")[1]
        for p in ("DEV", "SEMLEX", "SEMLEX2", "TRAIN")
    }
    probs = {
        m: {p: dict(np.load(E / wve.OUT / "scores" / m / f"{p}.npz")) for p in meta} for m in MODELS
    }
    train = [json.loads(line) for line in (E / wve.INDEX).open(encoding="utf-8")]
    signers = defaultdict(set)
    for r in train:
        if r["split"] == "train":
            signers[r["canonical_gloss"]].add(r["signer_id"])
    out: dict = {"models": {}}
    for model in MODELS:
        clip_real: dict[str, list[float]] = {}
        clip_dense: dict[str, float] = {}
        clip_hand: dict[str, list[float]] = defaultdict(list)
        clip_gloss: dict[str, str] = {}
        clip_signer: dict[str, str] = {}
        wrong_to: dict[str, Counter] = defaultdict(Counter)
        for population, role in (("DEV", None), ("SEMLEX", "EVAL"), ("SEMLEX2", "EVAL")):
            for view in PHASES:
                for x, p in zip(
                    meta[population][view], probs[model][population][view], strict=True
                ):
                    if role and x.get("role") != role:
                        continue
                    sid = x["sample_id"]
                    pred = int(np.argmax(p))
                    clip_real.setdefault(sid, []).append(float(pred == index[x["gloss"]]))
                    clip_hand[sid].append(float(x.get("hand_fraction", np.nan)))
                    clip_gloss[sid], clip_signer[sid] = x["gloss"], x["signer"]
                    if pred != index[x["gloss"]]:
                        wrong_to[x["gloss"]][names[pred]] += 1
            for x, p in zip(
                meta[population]["span_dense"], probs[model][population]["span_dense"], strict=True
            ):
                if role and x.get("role") != role:
                    continue
                clip_dense[x["sample_id"]] = float(int(np.argmax(p)) == index[x["gloss"]])
        tfit: dict[str, list[float]] = defaultdict(list)
        for x, p in zip(
            meta["TRAIN"]["span_c375_p0"], probs[model]["TRAIN"]["span_c375_p0"], strict=True
        ):
            tfit[x["gloss"]].append(float(int(np.argmax(p)) == index[x["gloss"]]))
        classes = {}
        for gloss in names:
            sids = [s for s, g in clip_gloss.items() if g == gloss]
            if not sids:
                continue
            real = float(np.mean([np.mean(clip_real[s]) for s in sids]))
            dense = float(np.mean([clip_dense[s] for s in sids if s in clip_dense]))
            hand = float(np.nanmean([np.nanmean(clip_hand[s]) for s in sids]))
            errs = wrong_to[gloss]
            partner, share = (
                (errs.most_common(1)[0][0], errs.most_common(1)[0][1] / sum(errs.values()))
                if errs
                else ("", 0.0)
            )
            row = {
                "clips": len(sids),
                "signers": len({clip_signer[s] for s in sids}),
                "recall_real": round(real, 3),
                "recall_dense": round(dense, 3),
                "hand": round(hand, 3),
                "train_fit": round(float(np.mean(tfit[gloss])), 3),
                "train_signers": len(signers[gloss]),
                "partner": partner,
                "partner_share": round(share, 2),
            }
            labels = []
            if real <= 0.3:
                if hand < 0.45:
                    labels.append("WEAK_HANDS")
                if dense - real >= 0.25:
                    labels.append("CADENCE")
                if row["train_fit"] < 0.6:
                    labels.append("LOW_FIT")
                if share >= 0.4 and sum(errs.values()) >= 3:
                    labels.append("PAIR")
                if row["train_signers"] < 12:
                    labels.append("THIN_COVERAGE")
                labels = labels or ["UNEXPLAINED"]
            row["labels"] = labels
            classes[gloss] = row
        hard = {g: r for g, r in classes.items() if r["recall_real"] <= 0.3}
        label_counts = Counter(lab for r in hard.values() for lab in r["labels"])
        # clip-level association with hand evidence (runtime windows, one value per clip)
        hand_c = np.asarray([np.nanmean(clip_hand[s]) for s in clip_real])
        acc_c = np.asarray([np.mean(clip_real[s]) for s in clip_real])
        bins = {
            f"{lo:.2f}-{hi:.2f}": round(float(acc_c[(hand_c >= lo) & (hand_c < hi)].mean()), 3)
            for lo, hi in ((0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.01))
        }
        out["models"][model] = {
            "classes_evaluated": len(classes),
            "hard_classes": len(hard),
            "hard_label_counts": dict(label_counts),
            "clip_accuracy_by_hand_fraction": bins,
            "clip_count": len(clip_real),
            "hard": dict(sorted(hard.items(), key=lambda kv: kv[1]["recall_real"])),
            "classes": classes,
        }
        print(model, "hard", len(hard), dict(label_counts), "by hand", bins, flush=True)
    Path(__file__).with_name("difficult_words.json").write_text(
        json.dumps(out, indent=1) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
