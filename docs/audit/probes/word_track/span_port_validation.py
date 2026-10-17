"""Fit (TRAIN) and validate (DEV) the Candidate01 port of the d1 span detector.

Fit population: recognizer-TRAIN ASL Citizen clips that have full-video Candidate01 raw (Phase-7
sources) and a governed d1 span. Validation: the 816 signer-disjoint DEV clips (full-video raw from
heldout_dev_fullvideo_extraction.py) against their governed spans. Agreement = onset/release frame
error and temporal IoU. Only `theta_scale` is fitted; every other d1 parameter is unchanged.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from pipeline.detect.candidate01_span import candidate01_span  # noqa: E402
from pipeline.detect.config import load_config  # noqa: E402
from pipeline.perception_vnext.recognition_schema import load_raw_sequence  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
RU = E / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
SPANS = Path("F:/ASL DATASET/ASL CITIZEN/derived/apphear3/spans")
GRID = (0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.8, 1.0)


def agreement(pairs: list[tuple[tuple[int, int, bool], tuple[int, int]]]) -> dict[str, float]:
    on, off, iou, invalid = [], [], [], 0
    for (o, r, valid), (go, gr) in pairs:
        if not valid or o < 0:
            invalid += 1
            continue
        on.append(abs(o - go))
        off.append(abs(r - gr))
        inter = max(0, min(r, gr) - max(o, go) + 1)
        union = max(r, gr) - min(o, go) + 1
        iou.append(inter / union)
    return {
        "n": len(pairs),
        "invalid": invalid,
        "onset_abs_err_median": float(np.median(on)),
        "release_abs_err_median": float(np.median(off)),
        "onset_within_3": float(np.mean(np.asarray(on) <= 3)),
        "release_within_3": float(np.mean(np.asarray(off) <= 3)),
        "iou_median": float(np.median(iou)),
        "iou_ge_0_7": float(np.mean(np.asarray(iou) >= 0.7)),
    }


def main() -> None:
    cfg = load_config(REPO / "pipeline/config/detect.yaml")
    manifest = json.loads(
        (
            RU / "phase7_production_cadence_aligned_segmenter_01/sparse_view_manifest.json"
        ).read_text()
    )
    train = {}
    train_rows = {
        r["sample_id"]: r
        for r in csv.DictReader(
            open(
                E
                / "artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1/manifests/train.csv",
                encoding="utf-8",
            )
        )
    }
    for row in manifest["rows"]:
        sid = row["sample_id"]
        if sid in train or sid not in train_rows or row["source"] != "ASL_CITIZEN":
            continue
        span_path = Path(train_rows[sid]["span_path"])
        if not span_path.is_file():
            continue
        span = json.loads(span_path.read_text("utf-8-sig"))
        if span.get("valid"):
            train[sid] = (Path(row["source_raw_path"]), int(span["onset"]), int(span["release"]))
    fit_raws = {sid: (load_raw_sequence(p), (o, r)) for sid, (p, o, r) in train.items()}
    fit = {}
    for theta in GRID:
        pairs = []
        for raw, gold in fit_raws.values():
            s = candidate01_span(raw, cfg, theta)
            frames = np.asarray(raw.frame_index)
            pairs.append(
                (
                    (
                        int(frames[s.onset]) if s.onset >= 0 else -1,
                        int(frames[s.release]) if s.release >= 0 else -1,
                        s.valid,
                    ),
                    gold,
                )
            )
        fit[theta] = agreement(pairs)
    best = min(
        GRID,
        key=lambda t: (
            fit[t]["invalid"] > 0.05 * fit[t]["n"],
            fit[t]["onset_abs_err_median"] + fit[t]["release_abs_err_median"],
            -fit[t]["iou_median"],
        ),
    )
    dev = json.loads((RU / "heldout_dev_fullvideo_raw_01/manifest.json").read_text())["clips"]
    results = {}
    for theta in sorted({1.0, best}):
        pairs = []
        for clip in dev:
            if not clip["span_valid"]:
                continue
            raw = load_raw_sequence(E / clip["raw_path"])
            s = candidate01_span(raw, cfg, theta)
            pairs.append(
                (
                    (s.onset, s.release, s.valid),
                    (clip["span_onset_index"], clip["span_release_index"]),
                )
            )
        results[str(theta)] = agreement(pairs)
    out = {
        "fit_population": len(fit_raws),
        "fit_grid": {str(k): v for k, v in fit.items()},
        "selected_theta_scale": best,
        "dev_validation": results,
    }
    Path(__file__).with_name("span_port_validation.json").write_text(json.dumps(out, indent=2))
    print(
        json.dumps(
            {"fit_n": len(fit_raws), "best": best, "fit_best": fit[best], "dev": results}, indent=1
        )
    )


if __name__ == "__main__":
    main()
