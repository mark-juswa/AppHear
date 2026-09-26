"""Phase 5.1R single-variable end-policy feasibility recovery.

This runner reads only the five declared calibration attempts. Holdout access fails closed unless
the recovery produced a runnable, hash-verified configuration; the governed run did not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.runtime_diagnostics.phase5_1_offline_segmenter import (
    CALIBRATION_IDS,
    EXPECTED_ORACLE_SHA256,
    HOLDOUT_IDS,
    ROOT,
    load_calibration,
    verify_oracle_identity,
)
from eval.runtime_diagnostics.phase5_1_offline_segmenter import (
    SOURCE_FILES as PHASE5_1_SOURCE_FILES,
)
from pipeline.perception_vnext.segmentation.calibration import (
    CalibrationAttempt,
    exact_low_threshold_feasibility,
)
from pipeline.perception_vnext.segmentation.schema import (
    EVENT_SCHEMA,
    RAW_SCHEMA,
    STATE_MACHINE_VERSION,
)

MILESTONE = "PHASE_5_1R_END_POLICY_FEASIBILITY_RECOVERY_01"
FINAL_STATUS = "END_POLICY_RECOVERY_NO_GLOBAL_FEASIBLE_DURATION"
BASE = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
)
PREVIOUS = BASE / "phase5_1_offline_automatic_segmenter_01"
OUTPUT = BASE / "phase5_1r_end_policy_feasibility_recovery_01"
RUNNER = ROOT / "eval/runtime_diagnostics/phase5_1r_end_policy_recovery.py"
RECOVERY_TEST = ROOT / "tests/test_phase5_1r_end_policy_recovery.py"
RECOVERY_SOURCE_FILES = (RUNNER, RECOVERY_TEST)
ORIGINAL_END_QUIET_MS = 500.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def end_duration_candidates(
    attempts: tuple[CalibrationAttempt, ...], *, upper_ms: float = 500.0
) -> tuple[float, ...]:
    """Return exact source-time breakpoints where quiet confirmation can change.

    Quiet starts and confirmation checks occur only on genuine retained observation timestamps.
    Between adjacent pairwise timestamp differences the state-machine result is constant, so an
    arbitrary millisecond grid would add duplicate behavior rather than evidence.
    """

    values = {
        round(float(timestamps[end] - timestamps[start]), 9)
        for attempt in attempts
        for timestamps in (attempt.raw.arrays.timestamp_ms,)
        for start in range(len(timestamps))
        for end in range(start + 1, len(timestamps))
        if 0.0 < float(timestamps[end] - timestamps[start]) < upper_ms
    }
    return tuple(sorted(values, reverse=True))


def evaluate_frontier(
    attempts: tuple[CalibrationAttempt, ...], candidates: tuple[float, ...]
) -> dict[str, Any]:
    frontier: list[dict[str, Any]] = []
    selected: float | None = None
    for duration_ms in candidates:
        result = exact_low_threshold_feasibility(
            attempts,
            end_quiet_ms=duration_ms,
        )
        feasible = result["joint_feasible_motion_patterns"] > 0
        frontier.append(
            {
                "end_quiet_persistence_ms": duration_ms,
                "globally_feasible": feasible,
                "joint_feasible_motion_patterns": result[
                    "joint_feasible_motion_patterns"
                ],
                "individual_feasible_pattern_counts": result[
                    "individual_feasible_pattern_counts"
                ],
                "distinct_motion_patterns_evaluated": result[
                    "distinct_motion_patterns_evaluated"
                ],
            }
        )
        if selected is None and feasible:
            selected = duration_ms
    return {
        "milestone": MILESTONE,
        "status": FINAL_STATUS if selected is None else "GLOBAL_FEASIBLE_DURATION_FOUND",
        "candidate_construction": {
            "source": "UNIQUE_POSITIVE_CALIBRATION_SOURCE_TIMESTAMP_DIFFERENCES",
            "upper_bound_exclusive_ms": ORIGINAL_END_QUIET_MS,
            "rounding_decimal_places": 9,
            "reason": (
                "Quiet starts and confirmations occur only at retained source timestamps; "
                "state behavior is constant between these exact differences."
            ),
            "arbitrary_millisecond_grid_used": False,
            "candidate_count": len(candidates),
            "search_order": "DESCENDING",
        },
        "selected_largest_feasible_end_quiet_persistence_ms": selected,
        "globally_feasible_candidate_count": sum(
            int(row["globally_feasible"]) for row in frontier
        ),
        "frontier": frontier,
    }


def non_runnable_config(frontier: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "apphear.segmentation.config.v1",
        "milestone": MILESTONE,
        "freeze_status": "NOT_FROZEN_NO_GLOBAL_FEASIBLE_DURATION",
        "holdout_eligible": False,
        "raw_schema": RAW_SCHEMA,
        "event_schema": EVENT_SCHEMA,
        "state_machine_version": STATE_MACHINE_VERSION,
        "oracle_bounds_sha256": EXPECTED_ORACLE_SHA256,
        "calibration_attempt_ids": list(CALIBRATION_IDS),
        "holdout_attempt_ids": list(HOLDOUT_IDS),
        "no_recognizer_declaration": True,
        "feature_definitions": {
            "h_refined_body": "body-frame-units-per-second",
            "h_refined_image": "minimum-image-dimensions-per-second",
            "h_proposal_image": "minimum-image-dimensions-per-second",
            "l_body": "unit-vector-delta-per-second",
        },
        "signal_quality_hierarchy": [
            "h_refined_body",
            "h_refined_image",
            "h_proposal_image",
            "UNKNOWN",
        ],
        "thresholds": None,
        "temporal_policy": {
            "start_persistence_ms": 250.0,
            "end_quiet_persistence_ms": None,
            "original_end_quiet_persistence_ms": ORIGINAL_END_QUIET_MS,
            "rearm_stable_quiet_ms": 700.0,
            "pre_roll_ms": 300.0,
            "post_roll_ms": 250.0,
            "long_duration_diagnostic_ms": 4000.0,
            "duration_forced_termination": False,
        },
        "gap_rule": {
            "absolute_ms": 500.0,
            "rolling_median_multiplier": 3.0,
            "rolling_window_ms": 2000.0,
        },
        "missingness_rules": {
            "missing_evidence": "UNKNOWN_NOT_ZERO_NOT_QUIET",
            "no_interpolation": True,
            "no_stale_carry": True,
            "no_synthetic_observation": True,
        },
        "recovery_status": frontier["status"],
    }


def _frontier_table(frontier: dict[str, Any]) -> str:
    rows = [
        "| T_end ms | Joint | 002 | 003 | 005 | 007 | 009 |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in frontier["frontier"]:
        counts = item["individual_feasible_pattern_counts"]
        rows.append(
            f"| {item['end_quiet_persistence_ms']:.9f} | "
            f"{item['joint_feasible_motion_patterns']} | "
            f"{counts['attempt_002']} | {counts['attempt_003']} | "
            f"{counts['attempt_005']} | {counts['attempt_007']} | "
            f"{counts['attempt_009']} |"
        )
    return "\n".join(rows)


def render_report(
    frontier: dict[str, Any], config_hash: str, fixed_sources_unchanged: bool
) -> str:
    return f"""# {MILESTONE}

Final classification: **{FINAL_STATUS}**

## SECTION 1 — RECOVERY SCOPE

Only `end_quiet_persistence_ms` was varied below the original 500 ms value. This is an
offline calibration-only recovery; it does not redesign the segmenter.

## SECTION 2 — PREVIOUS FAILURE IDENTITY

The validated Phase-5.1 result was `CALIBRATION_INSUFFICIENT_FOR_CURRENT_TEMPORAL_POLICY`.
Its non-runnable config SHA-256 was
`6d3f8f85129949404f174c9f0783a68fc06a1cc3738b30da0c85a0b86341bc37`, and
attempt 009/TABLE had zero feasible end patterns at 500 ms.

## SECTION 3 — FIXED COMPONENTS

Candidate01, raw-v1, SignEvent, all four signal equations, the hand hierarchy, one-vote hand
family, independent body family, UNKNOWN missingness, gap logic, 250 ms start persistence,
300 ms pre-roll, 250 ms post-roll, 700 ms re-arm, 500 ms context target, and absence of forced
duration termination were fixed. Phase-5.1 core source hashes unchanged:
**{fixed_sources_unchanged}**.

## SECTION 4 — END-DURATION CANDIDATE CONSTRUCTION

Candidates are the {frontier['candidate_construction']['candidate_count']} unique positive
pairwise source-timestamp differences below 500 ms across calibration attempts 002/003/005/007/009,
rounded to 9 decimal places only to remove binary serialization noise. These are exactly the points
where a source-timestamp state decision can change. No arbitrary millisecond grid was used.

## SECTION 5 — END-POLICY FEASIBILITY FRONTIER

Every behaviorally distinct candidate was evaluated by the complete exact/pruned low-threshold end
feasibility procedure. Counts are distinct low-threshold motion patterns.

{_frontier_table(frontier)}

Every candidate has zero joint feasible patterns. TABLE gains individual feasibility in only part
of the 266.616–199.962 ms frontier, but no one low-threshold pattern satisfies all five attempts.
At still shorter behavior, HOME and TABLE have zero individual feasible patterns.

## SECTION 6 — SELECTED LARGEST FEASIBLE T_end

**NONE.** No source-timestamp breakpoint below 500 ms is globally feasible.

## SECTION 7 — FULL CALIBRATION RESULT

`{FINAL_STATUS}`. Full high-threshold selection was not run because every duration was soundly
pruned by zero joint low-threshold end feasibility. High thresholds only restrict start activation
and cannot repair this end-policy contradiction.

## SECTION 8 — THRESHOLD CONFIGURATION

No thresholds were selected. `segmenter_config.json` is an explicit non-runnable stop record with
`thresholds: null`, `holdout_eligible: false`, and SHA-256 `{config_hash}`.

## SECTION 9 — OPTIONAL LOgO DIAGNOSTIC

**NOT RUN.** No complete calibration configuration exists; LOgO cannot diagnose a frozen global
operating point.

## SECTION 10 — CONFIG FREEZE PROOF

No holdout-eligible freeze exists. Config and source identities were written with holdout access
false. `config_freeze_status.json` records `NOT_FROZEN_NO_GLOBAL_FEASIBLE_DURATION`.

## SECTION 11 — ONE-SHOT HOLDOUT RESULT

**NOT ACCESSED.** Attempts 004/006/008/010 remain sealed. The holdout entrypoint refuses access
before constructing their paths because no eligible frozen configuration exists.

## SECTION 12 — BOUNDARY / COVERAGE RESULT

No runnable configuration exists, so calibration/holdout SignEvents and aggregate boundary or
coverage claims are not emitted. This is a calibration-policy stop, not a holdout result.

## SECTION 13 — GOVERNANCE

Candidate01 modified: **NO**  
Recognition V2 modified: **NO**  
Recognizer modified/accessed: **NO**  
Android modified: **NO**  
Training executed: **NO**  
DEV accessed: **NO**  
Protected TEST accessed: **NO**  
Holdout used for tuning: **NO**

## SECTION 14 — FINAL CLASSIFICATION

**{FINAL_STATUS}**

## SECTION 15 — NEXT

`WAIT_FOR_PROJECT_LEAD_SEGMENTATION_DIAGNOSIS`

Do not change another policy component, open holdout, run recognition, or start Phase 5.2.
"""


def run_recovery() -> dict[str, Any]:
    oracle_identity = verify_oracle_identity()
    attempts = load_calibration()
    candidates = end_duration_candidates(attempts)
    frontier = evaluate_frontier(attempts, candidates)
    if frontier["selected_largest_feasible_end_quiet_persistence_ms"] is not None:
        raise RuntimeError(
            "PHASE5_1R_FEASIBLE_PATH_REQUIRES_FULL_THRESHOLD_FREEZE_IMPLEMENTATION"
        )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT / "end_policy_feasibility.json", frontier)

    config = non_runnable_config(frontier)
    config_path = OUTPUT / "segmenter_config.json"
    write_json(config_path, config)
    config_hash = sha256(config_path)
    (OUTPUT / "segmenter_config.sha256").write_text(
        f"{config_hash}  segmenter_config.json\n", encoding="ascii"
    )

    previous_hashes = json.loads(
        (PREVIOUS / "source_hashes.json").read_text(encoding="utf-8")
    )["files"]
    current_fixed_hashes = {
        str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
        for path in PHASE5_1_SOURCE_FILES
    }
    fixed_sources_unchanged = all(
        previous_hashes.get(name) == digest
        for name, digest in current_fixed_hashes.items()
    )
    source_hashes = {
        "milestone": MILESTONE,
        "created_before_holdout_access": True,
        "holdout_accessed": False,
        "phase5_1_fixed_sources_unchanged": fixed_sources_unchanged,
        "fixed_source_files": current_fixed_hashes,
        "recovery_source_files": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
            for path in RECOVERY_SOURCE_FILES
        },
        "oracle_bounds": oracle_identity,
    }
    write_json(OUTPUT / "source_hashes.json", source_hashes)

    write_json(
        OUTPUT / "calibration_result.json",
        {
            "milestone": MILESTONE,
            "status": FINAL_STATUS,
            "oracle_identity": oracle_identity,
            "calibration_attempt_ids": list(CALIBRATION_IDS),
            "selected_end_quiet_persistence_ms": None,
            "threshold_selection": "NOT_RUN_ZERO_JOINT_END_FEASIBILITY",
            "holdout_raw_accessed": False,
            "recognizer_accessed": False,
        },
    )
    write_json(
        OUTPUT / "leave_one_gloss_out_result.json",
        {
            "status": "NOT_RUN_NO_COMPLETE_CALIBRATION_CONFIG",
            "reason": FINAL_STATUS,
            "diagnostic_only": True,
        },
    )
    write_json(
        OUTPUT / "config_freeze_status.json",
        {
            "status": "NOT_FROZEN_NO_GLOBAL_FEASIBLE_DURATION",
            "freeze_timestamp_utc": datetime.now(UTC).isoformat(),
            "config_sha256": config_hash,
            "holdout_eligible": False,
            "holdout_accessed": False,
            "source_hashes_recorded": True,
        },
    )
    write_json(
        OUTPUT / "holdout_result.json",
        {
            "status": "NOT_ACCESSED_CALIBRATION_STOP",
            "attempt_ids": list(HOLDOUT_IDS),
            "raw_payloads_opened": False,
            "reason": FINAL_STATUS,
        },
    )
    fixture_dir = OUTPUT / "sign_event_fixtures"
    write_json(
        fixture_dir / "calibration" / "NOT_GENERATED.json",
        {"status": "NOT_GENERATED_NO_RUNNABLE_CONFIG", "reason": FINAL_STATUS},
    )
    write_json(
        fixture_dir / "holdout" / "NOT_GENERATED.json",
        {"status": "NOT_GENERATED_HOLDOUT_NOT_ACCESSED", "reason": FINAL_STATUS},
    )

    report_path = OUTPUT / f"{MILESTONE}.md"
    report_path.write_text(
        render_report(frontier, config_hash, fixed_sources_unchanged),
        encoding="utf-8",
    )
    result = {
        "status": FINAL_STATUS,
        "candidate_count": len(candidates),
        "selected_end_quiet_persistence_ms": None,
        "config_sha256": config_hash,
        "holdout_accessed": False,
        "report": str(report_path),
    }
    print(json.dumps(result, indent=2))
    return result


def run_holdout() -> None:
    config = json.loads((OUTPUT / "segmenter_config.json").read_text(encoding="utf-8"))
    if (
        config.get("freeze_status") != "FROZEN_HOLDOUT_ELIGIBLE"
        or config.get("holdout_eligible") is not True
        or not isinstance(config.get("thresholds"), dict)
        or config.get("temporal_policy", {}).get("end_quiet_persistence_ms") is None
    ):
        raise RuntimeError(
            "PHASE5_1R_HOLDOUT_REFUSED_BEFORE_PATH_ACCESS:CONFIG_NOT_FROZEN_ELIGIBLE"
        )
    raise RuntimeError("PHASE5_1R_HOLDOUT_SUCCESS_PATH_NOT_AUTHORIZED_BY_RECOVERY_RESULT")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("recover", "holdout"))
    args = parser.parse_args()
    if args.command == "recover":
        run_recovery()
    else:
        run_holdout()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
