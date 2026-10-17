"""IPN-aware epoch selection (pre-registered) and IPN scoring for S2 candidates.

IPN metrics per package and subject role (ipn_hand_split_01.json), VIEW_B (200 ms) through the
reference lifecycle (BASELINE decoder):
  nog_events_per_min   events whose logical span lies only on NOG rows (>= 500 ms from gestures)
  nog_chunk_fire       fraction of hand-visible 9-observation NOG chunks with peak P(ACTIVE) >= 0.5
  gesture_canary       fraction of dynamic IPN gestures (classes 3-14) overlapped by an event
The canary guards against source bias: a model that learned "IPN source = quiet" also stops
firing on IPN's articulated gestures; one that learned "everyday movement != signing" should not.
Selection rule (fixed 2026-10-17 before any Arm B/I result): eligible epochs have CAL later-sign
acquisition >= Arm A e10 - 0.03 and IPN-CAL gesture_canary >= 0.7 x Arm A e10's; choose the
lowest IPN-CAL nog_events_per_min; ties -> lower CAL non-sign ACTIVE rate. Applied identically to
Arm A's own epochs (selection-only control). Writes selection_<run>.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics import event_reliability as er  # noqa: E402
from eval.runtime_diagnostics import ipn_hand_feasibility as ipn  # noqa: E402
from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter import (  # noqa: E402
    subset_raw,
)
from pipeline.perception_vnext.recognition_schema import load_raw_sequence  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
HERE = Path(__file__).parent
SPLIT = REPO / "model/config/recognition_upgrade/ipn_hand_split_01.json"
RUNS = {
    "ARM_A": "s2_r3_arm_a_01",
    "ARM_B": "s2_r3_arm_b_01",
    "ARM_I": "s2_r3_arm_i_01",
    "ARM_J": "s2_r3_arm_j_01",
    "ARM_K": "s2_r3_arm_k_01",
}


def ipn_videos(role: str) -> list[dict[str, Any]]:
    roles = suite.read_json(SPLIT)["roles"]
    out = []
    for path in sorted((E / ipn.IPN / "raw_v1").glob("*.npz")):
        full = load_raw_sequence(path)
        video = str(full.metadata["sample_id"]).split(":", 1)[1]
        if roles[ipn.subject_of(video)] != role:
            continue
        raw = subset_raw(full, ipn.view(full, 199.962))
        t = np.asarray(raw.timestamp_ms, np.float64)
        segs = ipn.hands_segments(E, video)
        out.append(
            {
                "video": video,
                "raw": raw,
                "t": t,
                "features": suite.features_for_raw(raw, "v1"),
                "cls": ipn.row_classes(t, segs, 500.0),
                "segments": segs,
            }
        )
    return out


def ipn_metrics(pkg: suite.Package, videos: list[dict[str, Any]]) -> dict[str, float]:
    nog_events = nog_rows = fired = chunks = canary_hit = canary_n = 0
    for v in videos:
        p = pkg.probabilities(v["features"])
        events = er.replay_events(p, v["t"], "BASELINE")
        cls, t = v["cls"], v["t"]
        nog_rows += int(np.sum(cls == ipn.NOG))
        spans = []
        for e in events:
            s, f = int(e["logical_active_start_index"]), int(e["logical_active_end_index"])
            spans.append((s, f))
            nog_events += int(np.all(cls[s : f + 1] == ipn.NOG))
        nog = np.flatnonzero(cls == ipn.NOG)
        for block in np.split(nog, np.flatnonzero(np.diff(nog) > 1) + 1) if len(nog) else []:
            for a in range(0, len(block), ipn.CHUNK):
                c = block[a : a + ipn.CHUNK]
                if len(c) >= 4 and np.asarray(v["raw"].hand_observed, bool)[c].any():
                    chunks += 1
                    fired += int(p[c, 1].max() >= 0.5)
        rel = (t - t[0]) * 30.0 / 1000.0 + 1
        for c, s, e in v["segments"]:
            if c >= 3:
                rows = np.flatnonzero((rel >= s) & (rel <= e))
                if len(rows):
                    canary_n += 1
                    canary_hit += int(any(max(a, rows[0]) <= min(b, rows[-1]) for a, b in spans))
    return {
        "nog_events_per_min": nog_events / max(1e-9, nog_rows * 0.2 / 60.0),
        "nog_events": nog_events,
        "nog_minutes": nog_rows * 0.2 / 60.0,
        "nog_chunk_fire": fired / max(1, chunks),
        "gesture_canary": canary_hit / max(1, canary_n),
        "gesture_segments": canary_n,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", choices=sorted(RUNS), required=True)
    args = parser.parse_args()
    run = E / er.RU / RUNS[args.run]
    training = suite.read_json(run / "training_result.json")
    cal_videos = ipn_videos("CAL")
    ref = ipn_metrics(er.load_s2(E, "ARM_A_E10"), cal_videos)
    ref_cal = suite.read_json(E / er.RU / RUNS["ARM_A"] / "training_result.json")["epochs"][9][
        "cal"
    ]
    rows = []
    for rec in training["epochs"]:
        epoch = rec["epoch"]
        pkg = suite.load_package(
            f"{args.run}_E{epoch}",
            "v1",
            run / f"epoch_{epoch:02d}.keras",
            run / "normalization.json",
        )
        m = ipn_metrics(pkg, cal_videos)
        eligible = (
            rec["cal"]["later_sign_acquisition"] >= ref_cal["later_sign_acquisition"] - 0.03
            and m["gesture_canary"] >= 0.7 * ref["gesture_canary"]
        )
        rows.append({"epoch": epoch, "cal": rec["cal"], "ipn_cal": m, "eligible": eligible})
        print(
            epoch,
            round(rec["cal"]["later_sign_acquisition"], 3),
            round(rec["cal"]["nonsign_active_rate"], 4),
            {k: round(v, 3) for k, v in m.items()},
            "ELIGIBLE" if eligible else "",
            flush=True,
        )
    options = [r for r in rows if r["eligible"]]
    chosen = (
        min(
            options,
            key=lambda r: (r["ipn_cal"]["nog_events_per_min"], r["cal"]["nonsign_active_rate"]),
        )["epoch"]
        if options
        else None
    )
    out = {
        "run": args.run,
        "rule": __doc__.split("Selection rule")[1].split("Writes")[0].strip(),
        "reference_arm_a_e10": {"cal": ref_cal, "ipn_cal": ref},
        "epochs": rows,
        "selected_epoch": chosen,
    }
    (HERE / f"selection_{args.run}.json").write_text(json.dumps(out, indent=1, default=float))
    print("SELECTED", args.run, chosen, flush=True)


if __name__ == "__main__":
    main()
