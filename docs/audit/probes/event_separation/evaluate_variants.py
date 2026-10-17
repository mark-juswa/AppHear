"""Held-out and genuine-session evaluation of decoder variants (selection was CAL-only).

For each variant and S2 package: (1) the signer-disjoint DEV continuous benchmark (stitched,
heldout_dev_e2e.py), (2) suite v03 Tier 2 (four genuine phone sessions with reviewed boundaries;
development-exposed), (3) per-sign WORD attribution on the same phone sessions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "docs/audit/probes/pipeline_v3"))

import stage_attribution as sa  # noqa: E402

from eval.runtime_diagnostics import heldout_dev_e2e as bench  # noqa: E402
from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics.event_separation import VARIANTS, use_variant  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
RU = E / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s2-keras", type=Path, required=True)
    parser.add_argument("--s2-normalization", type=Path, required=True)
    parser.add_argument("--recognizer", type=Path)
    parser.add_argument("--variants", nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    package = suite.load_package("EVAL", "v1", args.s2_keras, args.s2_normalization)
    word = bench.Word(args.recognizer or RU / "tcn_v2_run_01/best.keras", E / bench.VOCAB)
    rec = sa.Recognizer(E, args.recognizer)
    streams = bench.build_streams(E, 266.616)
    config = suite.read_json(suite.SUITES["03"][0])
    tier = config["tier2_sessions"]
    sessions = {
        name: suite.load_tier2_session(
            E, name, spec, "v1", int(tier["timestamp_match_tolerance_ns"])
        )
        for name, spec in tier.items()
        if isinstance(spec, dict) and "capture" in spec
    }
    out = {"s2": package.identity, "recognizer": rec.sha256, "variants": {}}
    for name in args.variants:
        variant = next(v for v in VARIANTS if v.name == name)
        with use_variant(variant):
            dev = bench.evaluate(package, word, streams)
            tier2 = suite.evaluate_tier2(package, config, sessions)
            phone = sa.phone_part(E, rec, package)
        signs = [s for s in phone["signs"] if not s.get("uncertain") and s["s2_valid"]]
        out["variants"][name] = {
            "heldout_dev": dev,
            "tier2_total": tier2["total"],
            "tier2_continuous": tier2["continuous"],
            "phone_correct_words": sum(s.get("runtime", {}).get("correct", False) for s in signs),
            "phone_unmatched_events": len(
                [e for e in phone["unmatched_events"] if e["session"] in sessions]
            ),
            "phone_first_failure": {
                k: sum(1 for s in signs if s["first_failure"] == k)
                for k in sorted({s["first_failure"] for s in signs})
            },
            "phone_runtime_outputs": [
                [s["runtime"]["top1_probability"], s["runtime"]["correct"]]
                for s in signs
                if "runtime" in s
            ]
            + [
                [e["top1_probability"], False]
                for e in phone["unmatched_events"]
                if e["session"] in sessions
            ],
        }
        v = out["variants"][name]
        print(
            name,
            json.dumps(
                {
                    m: {
                        k: round(v["heldout_dev"][m][k], 4)
                        for k in (
                            "detection_rate",
                            "correct_word_rate",
                            "word_precision",
                            "extra_events_per_minute",
                            "split_signs",
                            "merged_events",
                            "duplicate_words",
                        )
                    }
                    for m in ("NATURAL", "CONTINUOUS")
                }
            ),
            "| tier2",
            {
                k: v["tier2_total"][k]
                for k in (
                    "signs_with_distinct_event",
                    "events_inside_nonsign",
                    "nonsign_active_observations",
                    "merged_events",
                )
            },
            "cont",
            v["tier2_continuous"]["signs_with_distinct_event"],
            "| phone words",
            v["phone_correct_words"],
            "unmatched",
            v["phone_unmatched_events"],
            flush=True,
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    main()
