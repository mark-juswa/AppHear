"""Camera-condition study: how lighting, contrast, blur and resolution change Candidate01 and WORD.

Research only; Candidate01 itself is unchanged (pinned Android assets). A seeded, signer-stratified
subset of the signer-disjoint DEV videos (all 28 P5 clips, 48 each of P12/P21/P26/P39;
220) is re-run
through Candidate01 after a photometric/optical degradation of every frame. The degradations keep
geometry (no flip, rotation, crop or time change), so the sign, its hand orientation and movement
direction are unchanged:
  DIM            gamma 1.8, gain 0.45, Gaussian sensor noise sigma 4 (under-exposed room light)
  LOW_CONTRAST   0.45 x frame + 0.55 x mid-grey (haze / flat lighting)
  MOTION_BLUR    9-pixel diagonal linear blur (slow shutter)
  LOW_RES        0.4x down-sample then back up (distant or low-quality camera)
REFERENCE is the existing full-video raw (re-extraction reproduces it exactly). These are
SYNTHETIC conditions on webcam video; they indicate sensitivity, they do not measure real phones.

``extract --condition C`` writes raw-v1 per clip; ``evaluate`` reports, per condition, perception
(accepted-hand fraction, proposal presence, valid joints) and WORD top-1 for any recognizers on the
runtime-bounded window (span +/-250 ms through the materializer, 3.75 fps, four phases; per-clip
majority so repeated phases are not counted as independent) and the dense span, with paired exact
McNemar against REFERENCE and a signer-cluster bootstrap interval for the change.
"""

from __future__ import annotations

import argparse
import json
import sys
from math import comb
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics import word_vocabulary_eval as wve  # noqa: E402
from eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter import (  # noqa: E402
    subset_raw,
)
from pipeline.perception_vnext.recognition_schema import (  # noqa: E402
    load_raw_sequence,
    save_raw_sequence,
)

RU = Path("artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01")
FULL = RU / "heldout_dev_fullvideo_raw_01/manifest.json"
OUT = RU / "camera_condition_study_01"
VIDEOS = Path(r"I:\ASL CITIZEN\ASL CITIZEN\ASL_Citizen\videos")
ASSETS = ROOT / "android/app/src/main/assets/perception_vnext"
CONDITIONS = ("DIM", "LOW_CONTRAST", "MOTION_BLUR", "LOW_RES")
SEED = 8105


def degrade(rgb: np.ndarray, condition: str, frame: int) -> np.ndarray:
    import cv2

    x = rgb.astype(np.float32)
    if condition == "DIM":
        x = 255.0 * (x / 255.0) ** 1.8 * 0.45
        x += np.random.default_rng([SEED, frame]).normal(0.0, 4.0, x.shape).astype(np.float32)
    elif condition == "LOW_CONTRAST":
        x = 0.45 * x + 0.55 * 128.0
    elif condition == "MOTION_BLUR":
        kernel = np.eye(9, dtype=np.float32) / 9.0
        x = cv2.filter2D(x, -1, kernel)
    elif condition == "LOW_RES":
        h, w = x.shape[:2]
        small = cv2.resize(
            x, (max(1, int(w * 0.4)), max(1, int(h * 0.4))), interpolation=cv2.INTER_AREA
        )
        x = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    else:
        raise ValueError(condition)
    return np.clip(x, 0, 255).astype(np.uint8)


def subset(root: Path) -> list[dict[str, Any]]:
    clips = [
        c for c in json.loads((root / FULL).read_text(encoding="utf-8"))["clips"] if c["span_valid"]
    ]
    rng = np.random.default_rng(SEED)
    chosen = []
    for signer in sorted({c["signer"] for c in clips}):
        mine = sorted((c for c in clips if c["signer"] == signer), key=lambda c: c["sample_id"])
        if len(mine) > 48:
            mine = [mine[i] for i in sorted(rng.choice(len(mine), 48, replace=False))]
        chosen += mine
    return chosen


def extract(root: Path, condition: str) -> None:
    import cv2

    from eval.runtime_diagnostics import s2_r2_continuous_domain_correction as r2
    from pipeline.perception_vnext.offline_candidate01 import Candidate01Offline

    out = root / OUT / condition
    out.mkdir(parents=True, exist_ok=True)
    runtime = Candidate01Offline(
        ASSETS / "dwpose_t_singlepass.onnx", ASSETS / "hand_landmarks_detector.tflite"
    )
    try:
        for k, clip in enumerate(subset(root)):
            stem = Path(clip["raw_path"]).stem
            target = out / f"{stem}.npz"
            if target.exists():
                continue
            video = VIDEOS / f"{stem}.mp4"
            t, _, orientation = r2._video_timestamps(video)
            capture = cv2.VideoCapture(str(video))
            if hasattr(cv2, "CAP_PROP_ORIENTATION_AUTO"):
                capture.set(cv2.CAP_PROP_ORIENTATION_AUTO, 0)
            records, index = [], -1
            while True:
                ok, frame = capture.read()
                if not ok or index + 1 >= len(t):
                    break
                index += 1
                rgb = cv2.cvtColor(r2._rotate_upright(frame, orientation), cv2.COLOR_BGR2RGB)
                records.append(
                    (index, float(t[index]), runtime.process_rgb(degrade(rgb, condition, index)))
                )
            capture.release()
            raw = r2._raw_from_records(
                f"{condition}:{clip['sample_id']}", "ASL_CITIZEN", clip["signer"], records
            )
            save_raw_sequence(target, raw)
            if k % 20 == 0:
                print(f"[camera] {condition} {k}", flush=True)
    finally:
        runtime.close()


def mcnemar(a: np.ndarray, b: np.ndarray) -> dict[str, Any]:
    n01, n10 = int(np.sum(~a & b)), int(np.sum(a & ~b))
    n = n01 + n10
    p = min(1.0, 2 * sum(comb(n, k) for k in range(min(n01, n10) + 1)) / 2**n) if n else 1.0
    return {"fixed": n01, "broken": n10, "p": round(p, 6)}


def cluster_ci(delta: np.ndarray, signers: np.ndarray, reps: int = 4000) -> list[float]:
    groups = sorted(set(signers))
    by = [delta[signers == g] for g in groups]
    rng = np.random.default_rng(SEED)
    stats = []
    for _ in range(reps):
        pick = rng.integers(len(by), size=len(by))
        stats.append(float(np.concatenate([by[i] for i in pick]).mean()))
    return [round(float(np.percentile(stats, q)), 4) for q in (2.5, 97.5)]


def evaluate(root: Path, models: dict[str, Path]) -> dict[str, Any]:
    import tensorflow as tf

    names = wve.glosses(root)
    index = {g: i for i, g in enumerate(names)}
    clips = subset(root)
    keras = {
        k: tf.keras.models.load_model(p, compile=False, safe_mode=True) for k, p in models.items()
    }
    out: dict[str, Any] = {
        "clips": len(clips),
        "signers": sorted({c["signer"] for c in clips}),
        "conditions": {},
    }
    results: dict[str, dict[str, Any]] = {}
    for condition in ("REFERENCE", *CONDITIONS):
        raws = []
        for clip in clips:
            path = (
                (root / clip["raw_path"])
                if condition == "REFERENCE"
                else (root / OUT / condition / f"{Path(clip['raw_path']).stem}.npz")
            )
            raws.append(load_raw_sequence(path) if path.exists() else None)
        if any(r is None for r in raws):
            out["conditions"][condition] = {"missing": sum(r is None for r in raws)}
            continue
        hand = np.asarray([np.mean(np.asarray(r.hand_observed, bool).any(axis=1)) for r in raws])
        both = np.asarray([np.mean(np.asarray(r.hand_observed, bool).all(axis=1)) for r in raws])
        proposal = np.asarray(
            [np.mean(np.asarray(r.hand_proposal_present, bool).any(axis=1)) for r in raws]
        )
        bank = wve.Bank()
        for clip, raw in zip(clips, raws, strict=True):
            meta = {
                "sample_id": clip["sample_id"],
                "gloss": clip["gloss"],
                "signer": clip["signer"],
            }
            span = subset_raw(
                raw,
                np.arange(clip["span_onset_index"], clip["span_release_index"] + 1, dtype=np.int32),
            )
            bank.add("span_dense", span, meta)
            for k in range(4):
                sub, idx = wve.at_cadence(raw, wve.PHONE_MS, k * wve.PHONE_MS / 4)
                a, b = wve.span_in(idx, clip["span_onset_index"], clip["span_release_index"])
                bank.add(f"ctx_c375_p{k}", wve.ctx_window(sub, a, b), meta)
        y = np.asarray([index[c["gloss"]] for c in clips])
        cond: dict[str, Any] = {
            "accepted_hand_fraction_mean": round(float(hand.mean()), 4),
            "both_hands_fraction_mean": round(float(both.mean()), 4),
            "proposal_fraction_mean": round(float(proposal.mean()), 4),
        }
        results[condition] = {}
        for name, model in keras.items():
            dense = wve.predict(model, bank.rows["span_dense"]).argmax(1) == y
            phases = np.stack(
                [wve.predict(model, bank.rows[f"ctx_c375_p{k}"]).argmax(1) == y for k in range(4)]
            )
            realistic = phases.mean(axis=0)  # per-clip share of phases correct
            results[condition][name] = (dense, realistic)
            cond[name] = {
                "dense_top1": round(float(dense.mean()), 4),
                "runtime_window_top1": round(float(realistic.mean()), 4),
            }
        out["conditions"][condition] = cond
        print(condition, json.dumps(cond), flush=True)
    signers = np.asarray([c["signer"] for c in clips])
    for condition in CONDITIONS:
        if condition not in results:
            continue
        for name in models:
            ref_dense, ref_real = results["REFERENCE"][name]
            dense, real = results[condition][name]
            out["conditions"][condition][name]["vs_reference"] = {
                "dense": mcnemar(ref_dense, dense),
                "runtime_window_majority": mcnemar(ref_real >= 0.5, real >= 0.5),
                "runtime_window_delta": round(float((real - ref_real).mean()), 4),
                "runtime_window_delta_signer_ci95": cluster_ci(real - ref_real, signers),
            }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--evidence-root", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--condition", choices=CONDITIONS, required=True)
    v = sub.add_parser("evaluate")
    v.add_argument("--model", action="append", required=True, help="NAME=path (relative to root)")
    args = parser.parse_args()
    if args.command == "extract":
        extract(args.evidence_root, args.condition)
    else:
        models = {m.split("=", 1)[0]: args.evidence_root / m.split("=", 1)[1] for m in args.model}
        result = evaluate(args.evidence_root, models)
        target = args.evidence_root / OUT / "evaluation.json"
        target.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
        print(target)


if __name__ == "__main__":
    main()
