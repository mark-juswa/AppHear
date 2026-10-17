"""S2-R3 operating point: ACTIVE-probability threshold chosen on CAL (D7 extended), then tested.

The decoder consumes the S2 argmax state. Arm A over-fires on hands-visible movement while
acquiring signs far better than S2-R2. A thresholded state (ACTIVE only when P(ACTIVE) >= theta,
otherwise the larger of PRE/POST) trades acquisition for discrimination with no retraining.
Selection (fixed before any held-out result): over Arm A epochs 1-30 x theta grid, on CAL streams
and CAL isolated views only, eligible iff CAL non-sign ACTIVE rate <= the frozen S2-R2 rate on the
same CAL streams (the original D7 bar); maximize later-sign acquisition, then isolated containment.
The selected (epoch, theta) is then scored on suite v03 (all tiers + gate), the held-out DEV
continuous benchmark and the phone word attribution.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "docs/audit/probes/pipeline_v3"))

import stage_attribution as sa  # noqa: E402

from eval.runtime_diagnostics import heldout_dev_e2e as bench  # noqa: E402
from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics import s2_r3_train  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
RU = E / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
ARM_A = RU / "s2_r3_arm_a_01"
THETAS = (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95)


def thresholded(p: np.ndarray, theta: float) -> np.ndarray:
    """Probabilities whose argmax is the thresholded state (ties never favour ACTIVE)."""
    out = np.asarray(p, np.float64).copy()
    active = out[:, 1] >= theta
    out[~active, 1] = -1.0
    out[active] = np.array([0.0, 1.0, 0.0])
    return out


class ThresholdPackage(suite.Package):
    theta: float = 0.5

    def probabilities(self, features: np.ndarray) -> np.ndarray:
        return thresholded(super().probabilities(features), self.theta)


def load(epoch: int, theta: float) -> ThresholdPackage:
    base = suite.load_package(
        f"ARM_A_E{epoch}_T{theta}",
        "v1",
        ARM_A / f"epoch_{epoch:02d}.keras",
        ARM_A / "normalization.json",
    )
    pkg = ThresholdPackage(
        base.package_id, base.contract, base.model, base.mean, base.std, base.identity
    )
    pkg.theta = theta
    return pkg


def cal_scores(
    probs: list[np.ndarray], iso: list[np.ndarray], data: dict[str, Any], theta: float
) -> dict[str, float]:
    nonsign = active = 0
    later: list[bool] = []
    for stream, p in zip(data["cal_streams"], probs, strict=True):
        states = np.argmax(thresholded(p, theta), axis=1)
        mask = (stream["kinds"] == s2_r3_train.NEGATIVE_KIND) & (stream["labels"] == 0)
        nonsign += int(mask.sum())
        active += int(np.sum(states[mask] == 1))
        for o in sorted(set(stream["ordinals"].tolist()) - {-1, 0}):
            rows = (stream["ordinals"] == o) & (stream["labels"] == 1)
            if rows.any():
                later.append(bool(np.any(states[rows] == 1)))
    contained = 0
    from pipeline.perception_vnext.recognition_window_materializer import (
        LogicalSignEvent,
        materialize_recognition_window,
    )
    from pipeline.perception_vnext.segmentation.streaming_decoder import (
        CausalStreamingSignEventDecoder,
    )

    for clip, p in zip(data["cal_isolated"], iso, strict=True):
        q = thresholded(p, theta)
        t = np.asarray(clip["raw"].timestamp_ms, np.float64)
        dec = CausalStreamingSignEventDecoder(suite.CONFIG_01)
        dec.run(t, q, np.argmax(q, axis=1))
        rows = np.flatnonzero(clip["labels"] == 1)
        lo, hi = t[rows[0]], t[rows[-1]]
        for e in dec.events:
            w = materialize_recognition_window(
                t,
                LogicalSignEvent(
                    e.logical_active_start_index,
                    e.logical_active_end_index,
                    e.logical_active_start_ms,
                    e.logical_active_end_ms,
                    e.first_post_index,
                    e.first_post_ms,
                    e.emitted_at_index,
                    e.emitted_at_ms,
                ),
                suite.MATERIALIZER_CONFIG,
            )
            cover = max(0.0, min(w.selected_end_ms, hi) - max(w.selected_start_ms, lo))
            if hi - lo <= 0 or cover / (hi - lo) >= 0.9:
                contained += 1
                break
    return {
        "nonsign_active_rate": active / max(1, nonsign),
        "later_sign_acquisition": float(np.mean(later)),
        "isolated_containment": contained / len(data["cal_isolated"]),
    }


def main() -> None:
    config = suite.read_json(s2_r3_train.CONFIG_PATH)
    data = s2_r3_train.build_dataset(E, config)
    ref = suite.read_json(ARM_A / "training_result.json")["reference_cal"]
    grid = {}
    for epoch in range(1, 31):
        pkg = load(epoch, 0.5)
        probs = [suite.Package.probabilities(pkg, s["features"]) for s in data["cal_streams"]]
        iso = [suite.Package.probabilities(pkg, c["features"]) for c in data["cal_isolated"]]
        for theta in THETAS:
            grid[f"{epoch}:{theta}"] = cal_scores(probs, iso, data, theta)
        print(
            epoch,
            {t: round(grid[f"{epoch}:{t}"]["nonsign_active_rate"], 4) for t in THETAS},
            {t: round(grid[f"{epoch}:{t}"]["later_sign_acquisition"], 3) for t in THETAS},
            flush=True,
        )
    eligible = [
        k for k, v in grid.items() if v["nonsign_active_rate"] <= ref["nonsign_active_rate"]
    ]
    chosen = max(
        eligible,
        key=lambda k: (grid[k]["later_sign_acquisition"], grid[k]["isolated_containment"]),
        default=None,
    )
    out: dict[str, Any] = {
        "reference_cal": ref,
        "grid": grid,
        "eligible": eligible,
        "selected": chosen,
    }
    print("SELECTED", chosen, grid.get(chosen) if chosen else None, flush=True)
    if chosen:
        epoch, theta = int(chosen.split(":")[0]), float(chosen.split(":")[1])
        pkg = load(epoch, theta)
        sconfig = suite.read_json(suite.SUITES["03"][0])
        frozen = suite.read_json(suite.SUITES["03"][1])
        results, _ = suite.run_suite(E, sconfig, pkg)
        out["suite_v03"] = {
            "results": results,
            "gate": suite.apply_gate(sconfig, results, frozen["reference_results"]),
        }
        word = bench.Word(RU / "tcn_v2_run_01/best.keras", E / bench.VOCAB)
        out["heldout_dev"] = bench.evaluate(pkg, word, bench.build_streams(E, 266.616))
        phone = sa.phone_part(E, sa.Recognizer(E), pkg)
        signs = [s for s in phone["signs"] if not s.get("uncertain") and s["s2_valid"]]
        out["phone"] = {
            "correct_words": sum(s.get("runtime", {}).get("correct", False) for s in signs),
            "unmatched": len(phone["unmatched_events"]),
            "outputs": [
                [s["runtime"]["top1_probability"], s["runtime"]["correct"]]
                for s in signs
                if "runtime" in s
            ]
            + [[e["top1_probability"], False] for e in phone["unmatched_events"]],
            "first_failure": {
                k: sum(1 for s in signs if s["first_failure"] == k)
                for k in sorted({s["first_failure"] for s in signs})
            },
        }
        for line in out["suite_v03"]["gate"]["lines"]:
            print(f"{line['id']:40s} {line['observed']:10.4f} {'PASS' if line['pass'] else 'FAIL'}")
        print(
            {
                m: {
                    k: round(out["heldout_dev"][m][k], 4)
                    for k in (
                        "detection_rate",
                        "correct_word_rate",
                        "word_precision",
                        "extra_events_per_minute",
                    )
                }
                for m in ("NATURAL", "CONTINUOUS")
            }
        )
        print(
            "phone",
            out["phone"]["correct_words"],
            out["phone"]["unmatched"],
            out["phone"]["first_failure"],
        )
    Path(__file__).with_name("operating_point.json").write_text(
        json.dumps(out, indent=2, default=float)
    )


if __name__ == "__main__":
    main()
