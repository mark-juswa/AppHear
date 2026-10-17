"""Confidence abstention policy: calibrate on some held-out signers, validate on the others.

Every runtime word output (event -> WORD top-1) of the held-out DEV benchmark is labelled correct
(credited one-to-one to a sign whose gloss it names) or wrong (wrong gloss, extra event, or a second
event inside a sign). Calibration signers: asl_citizen:P5, P12, P21. Validation signers: P26, P39.
Rule fixed before seeing validation data: threshold maximizing Youden J = (correct kept / correct)
- (wrong kept / wrong) on calibration signers (both modes pooled). The validated threshold is then
also applied to the phone sessions (development-exposed; hands-visible non-sign).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "docs/audit/probes/pipeline_v3"))
sys.path.insert(0, str(REPO / "docs/audit/probes/s2_discrimination"))

import operating_point as op  # noqa: E402
import stage_attribution as sa  # noqa: E402

from eval.runtime_diagnostics import heldout_dev_e2e as bench  # noqa: E402
from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
RU = E / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
CAL_SIGNERS = {"asl_citizen:P5", "asl_citizen:P12", "asl_citizen:P21"}
GRID = np.round(np.arange(0.0, 0.96, 0.05), 2)


def kept(records: list[tuple[float, bool]], th: float) -> dict[str, float]:
    c = sum(1 for p, ok in records if ok)
    w = sum(1 for p, ok in records if not ok)
    ck = sum(1 for p, ok in records if ok and p >= th)
    wk = sum(1 for p, ok in records if not ok and p >= th)
    return {
        "threshold": float(th),
        "correct": c,
        "wrong": w,
        "correct_kept": ck,
        "wrong_kept": wk,
        "precision_kept": ck / max(1, ck + wk),
        "youden": ck / max(1, c) - wk / max(1, w),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--epoch", type=int, help="Arm A epoch (omit for frozen S2-R2)")
    parser.add_argument("--theta", type=float, default=0.5)
    parser.add_argument("--recognizer", type=Path)
    args = parser.parse_args()
    if args.epoch:
        package = op.load(args.epoch, args.theta)
    else:
        ref = suite.read_json(suite.SUITES["03"][0])["reference_package"]
        package = suite.load_package("S2_R2", "v1", E / ref["keras"], E / ref["normalization"])
    word = bench.Word(args.recognizer or RU / "tcn_v2_run_01/best.keras", E / bench.VOCAB)
    summary = bench.evaluate(package, word, bench.build_streams(E, 266.616))
    records = summary.pop("event_records")
    cal = [(p, ok) for _, signer, p, ok in records if signer in CAL_SIGNERS]
    val = [(p, ok) for _, signer, p, ok in records if signer not in CAL_SIGNERS]
    sweep = [kept(cal, th) for th in GRID]
    chosen = max(sweep, key=lambda r: (r["youden"], -r["threshold"]))["threshold"]
    phone = sa.phone_part(E, sa.Recognizer(E, args.recognizer), package)
    signs = [s for s in phone["signs"] if not s.get("uncertain") and s["s2_valid"]]
    phone_records = [
        (s["runtime"]["top1_probability"], s["runtime"]["correct"]) for s in signs if "runtime" in s
    ] + [(e["top1_probability"], False) for e in phone["unmatched_events"]]
    out = {
        "name": args.name,
        "s2": package.identity,
        "recognizer": word.sha256,
        "calibration_signers": sorted(CAL_SIGNERS),
        "selected_threshold": chosen,
        "calibration": {"none": kept(cal, 0.0), "selected": kept(cal, chosen), "sweep": sweep},
        "validation": {"none": kept(val, 0.0), "selected": kept(val, chosen)},
        "phone": {"none": kept(phone_records, 0.0), "selected": kept(phone_records, chosen)},
        "benchmark_summary": summary,
    }
    path = Path(__file__).with_name(f"{args.name}.json")
    path.write_text(json.dumps(out, indent=2, default=float))
    print(args.name, "threshold", chosen)
    for part in ("calibration", "validation", "phone"):
        a, b = out[part]["none"], out[part]["selected"]
        print(
            f"  {part:12s} none {a['correct_kept']}/{a['wrong_kept']}  ->  "
            f"selected {b['correct_kept']}/{b['wrong_kept']}"
            f"  precision {a['precision_kept']:.3f} -> {b['precision_kept']:.3f}"
        )


if __name__ == "__main__":
    main()
