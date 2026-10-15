"""Reproduce the partial phone evaluation from saved evidence; never impute missing runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

from summarize_trace import parse_trace, summarize


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(directory: Path) -> dict:
    result: dict = {
        "schema_version": "apphear.v3.partial_android_validation.v1",
        "device": "Xiaomi M2101K7AG / Android12 / SM6150",
        "signer_status": "NONEXPERT_ENGINEERING_SMOKE",
        "scope": "six completed 20-second live runs; paired recorded compute test",
        "analysis_window": (
            "completion clock [BEGIN+5s, BEGIN+19s); " "five-second warmup; 14s denominator"
        ),
        "analysis_is_exploratory": True,
        "runs": {},
        "source_evidence_sha256": {},
        "missing_runs": ["v3_word_rear_02", "v3_fingerspell_rear_02"],
        "initial_run_excluded_from_pairs": {
            "baseline_word_front_01": (
                "pilot before clarified live/automated-test instructions; preserved separately"
            )
        },
        "incident": (
            "Phone closed and both ADB transports vanished before V3 rear install; "
            "cause unresolved"
        ),
        "last_confirmed_installed_arm": "baseline",
        "frame_drops": "NOT_MEASURED_SENSOR_TIMESTAMPS_UNAVAILABLE",
        "sustained_stability": "NOT_ESTABLISHED",
        "cpu_percent_comparison": "EXCLUDED_STALE_DUMPSYS_INTERVALS",
        "accuracy_claim": "NONE",
        "decision": "RETAIN_DEFAULT_OFF_CANDIDATE_DO_NOT_PROMOTE",
    }
    for lens, arms in (("front", ("baseline", "v3")), ("rear", ("baseline",))):
        for owner in ("word", "fingerspell"):
            for arm in arms:
                label = f"{arm}_{owner}_{lens}_02"
                trace_path = directory / f"{label}.log"
                ui_path = directory / f"{label}-ui.json"
                rows = parse_trace(trace_path.read_text(encoding="utf-8-sig").splitlines())
                summarize(rows)
                ui = json.loads(ui_path.read_text(encoding="utf-8-sig"))
                assert ui["owner"] == owner.upper() and ui["rear"] == (lens == "rear")
                start = ui["started_elapsed_ns"]
                lower, upper = start + 5_000_000_000, start + 19_000_000_000
                selected = [r for r in rows if lower <= r["completed_timestamp_ns"] < upper]
                summary = summarize(selected)
                assert summary["v3_parallel_hands"] == (arm == "v3")
                assert summary["owner"] == owner.upper()
                samples = [r for r in ui["samples"] if lower <= r["elapsed_ns"] < upper]
                assert samples
                summary.update(
                    window_delivered_observation_fps=len(selected) / 14.0,
                    window_seconds=14,
                    pss_median_kb=statistics.median(r["pss_kb"] for r in samples),
                    pss_max_kb=max(r["pss_kb"] for r in samples),
                    pss_scope="instrumented app snapshots; scene-dependent allocations included",
                    mean_valid_body_fraction=summary["body_valid_points_total"] / len(selected) / 8,
                    mean_accepted_hands=summary["hands_observed_total"] / len(selected),
                    parallel_frames=sum(r["hands_parallel_this_frame"] for r in selected),
                    observed_sentences=list(
                        dict.fromkeys(
                            r["displayed_sentence"]
                            for r in ui["samples"]
                            if r["displayed_sentence"] != "..."
                        )
                    ),
                    observed_spelling_drafts=list(
                        dict.fromkeys(
                            r["spelling_preview"] for r in ui["samples"] if r["spelling_preview"]
                        )
                    ),
                )
                result["runs"][label] = summary
                result["source_evidence_sha256"][trace_path.name] = digest(trace_path)
                result["source_evidence_sha256"][ui_path.name] = digest(ui_path)
    result["front_comparisons"] = {}
    for owner in ("word", "fingerspell"):
        baseline = result["runs"][f"baseline_{owner}_front_02"]
        v3 = result["runs"][f"v3_{owner}_front_02"]
        result["front_comparisons"][owner] = {
            "observed_fps_change_percent": 100
            * (
                v3["window_delivered_observation_fps"]
                / baseline["window_delivered_observation_fps"]
                - 1
            ),
            "pss_median_delta_mib": (v3["pss_median_kb"] - baseline["pss_median_kb"]) / 1024,
            "causal_accuracy_effect": "UNVERIFIED_DIFFERENT_LIVE_GESTURES_AND_VALIDITY",
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(args.data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["front_comparisons"], indent=2))


if __name__ == "__main__":
    main()
