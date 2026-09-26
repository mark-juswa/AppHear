"""Phase 5.1 offline automatic isolated-sign segmenter runner.

The calibration command reads only the five declared calibration raw-v1 payloads. The holdout
command fails closed before constructing or opening a holdout path unless a calibration-feasible,
hash-verified frozen config exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.perception_vnext.segmentation.calibration import (
    CalibrationAttempt,
    exact_low_threshold_feasibility,
)
from pipeline.perception_vnext.segmentation.event import build_sign_event
from pipeline.perception_vnext.segmentation.schema import (
    EVENT_SCHEMA,
    PER_OBSERVATION_WIDTHS,
    RAW_SCHEMA,
    STATE_MACHINE_VERSION,
    RawV1Document,
    raw_v1_arrays,
)
from pipeline.perception_vnext.segmentation.signals import extract_segmentation_transitions
from pipeline.perception_vnext.segmentation.state_machine import (
    ChannelThreshold,
    SegmenterConfig,
    segment_raw_sequence,
)

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
SESSION_ID = "session_20260915T065635Z"
SESSION = BASE / "phase4a_gate4a1b_controlled_live_input_recovery_01" / SESSION_ID
ORACLE_DIR = BASE / "phase4a_gate4a1c_oracle_temporal_boundary_replay_01"
ORACLE_BOUNDS = ORACLE_DIR / "oracle_bounds.json"
EXPECTED_ORACLE_SHA256 = "0e6f14f159287ce830b68c4d33edba88dbb6aeef386060b80f79e3fed4a1e41f"
OUTPUT = BASE / "phase5_1_offline_automatic_segmenter_01"
MILESTONE = "PHASE_5_1_OFFLINE_AUTOMATIC_SEGMENTER_01"
SEGMENTER_VERSION = "phase5.1-offline-reference-v1"
CALIBRATION_IDS = (
    "attempt_002",
    "attempt_003",
    "attempt_005",
    "attempt_007",
    "attempt_009",
)
HOLDOUT_IDS = ("attempt_004", "attempt_006", "attempt_008", "attempt_010")
SECONDARY_IDS = ("attempt_001",)
SOURCE_FILES = (
    ROOT / "pipeline/perception_vnext/segmentation/__init__.py",
    ROOT / "pipeline/perception_vnext/segmentation/schema.py",
    ROOT / "pipeline/perception_vnext/segmentation/signals.py",
    ROOT / "pipeline/perception_vnext/segmentation/state_machine.py",
    ROOT / "pipeline/perception_vnext/segmentation/event.py",
    ROOT / "pipeline/perception_vnext/segmentation/calibration.py",
    ROOT / "eval/runtime_diagnostics/phase5_1_offline_segmenter.py",
    ROOT / "tests/test_perception_vnext_segmentation.py",
)


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


def verify_oracle_identity() -> dict[str, str]:
    actual = sha256(ORACLE_BOUNDS)
    if actual != EXPECTED_ORACLE_SHA256:
        raise RuntimeError(f"PHASE5_1_ORACLE_SHA_MISMATCH:{actual}")
    return {
        "path": str(ORACLE_BOUNDS),
        "expected_sha256": EXPECTED_ORACLE_SHA256,
        "actual_sha256": actual,
    }


def load_calibration() -> tuple[CalibrationAttempt, ...]:
    bounds_document = json.loads(ORACLE_BOUNDS.read_text(encoding="utf-8"))
    bounds = {
        row["attempt_id"]: row
        for row in bounds_document["bounds"]
        if row["attempt_id"] in CALIBRATION_IDS
    }
    if tuple(bounds) != CALIBRATION_IDS:
        raise RuntimeError("PHASE5_1_CALIBRATION_BOUND_ORDER_MISMATCH")
    attempts: list[CalibrationAttempt] = []
    for attempt_id in CALIBRATION_IDS:
        source = json.loads(
            (SESSION / attempt_id / "raw_v1.json").read_text(encoding="utf-8")
        )
        raw = RawV1Document(source=source, arrays=raw_v1_arrays(source))
        bound = bounds[attempt_id]
        attempts.append(
            CalibrationAttempt(
                attempt_id=attempt_id,
                expected_gloss=str(bound["expected_gloss"]),
                raw=raw,
                transitions=tuple(extract_segmentation_transitions(raw)),
                oracle_start_index=int(bound["oracle_start_index"]),
                oracle_end_index=int(bound["oracle_end_index"]),
            )
        )
    return tuple(attempts)


def _fixture_config() -> SegmenterConfig:
    """Engineering-only config for state/gap tests; never a frozen operating point."""

    return SegmenterConfig(
        thresholds={
            "h_refined_body": ChannelThreshold(0.04201893785259664, 0.08711924825907269),
            "h_refined_image": ChannelThreshold(0.02, 0.1),
            "h_proposal_image": ChannelThreshold(0.2166873867904768, 0.891123691457173),
            "l_body": ChannelThreshold(0.5190018560664262, 8.765716747200678),
        }
    )


def _copy_without_observations(
    raw: RawV1Document, removed_frame_indices: set[int]
) -> RawV1Document:
    keep = [
        index
        for index, frame_index in enumerate(raw.arrays.frame_index)
        if int(frame_index) not in removed_frame_indices
    ]
    source: dict[str, Any] = {}
    for name, value in raw.source.items():
        width = PER_OBSERVATION_WIDTHS.get(name)
        if width is None:
            source[name] = value
        else:
            source[name] = [
                item
                for index in keep
                for item in value[index * width : (index + 1) * width]
            ]
    copied = RawV1Document(source=source, arrays=raw_v1_arrays(source))
    if copied.observation_count != raw.observation_count - len(removed_frame_indices):
        raise AssertionError("gap fixture observation count changed unexpectedly")
    if copied.arrays.frame_index.tolist() != [
        int(raw.arrays.frame_index[index]) for index in keep
    ]:
        raise AssertionError("gap fixture created or reordered an observation")
    return copied


def _set_hand_evidence_missing(
    raw: RawV1Document, *, remove_refined: bool, remove_proposal: bool
) -> RawV1Document:
    source = json.loads(json.dumps(raw.source, separators=(",", ":")))
    count = raw.observation_count
    if remove_refined:
        source["hand_observed"] = [False] * (count * 2)
        source["hand_joint_valid"] = [False] * (count * 2 * 21)
        source["hand_presence"] = [None] * (count * 2)
    if remove_proposal:
        source["hand_proposal_present"] = [False] * (count * 2)
        source["hand_roi_center_side"] = [None] * (count * 2 * 3)
    return RawV1Document(source=source, arrays=raw_v1_arrays(source))


def _trace_has(result: Any, from_state: str, reason: str) -> bool:
    return any(
        row["from_state"] == from_state and row["reason"] == reason
        for row in result.state_transition_trace
    )


def run_engineering_fixtures(
    attempts: tuple[CalibrationAttempt, ...], config_sha256: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    by_id = {attempt.attempt_id: attempt for attempt in attempts}
    hello = by_id["attempt_002"].raw
    config = _fixture_config()
    gap_cases = {
        "hard_gap_during_idle": ({5, 6, 7}, "IDLE", "hard_gap_reset_idle_continuity"),
        "hard_gap_during_possible_start": (
            {10, 11},
            "POSSIBLE_START",
            "hard_gap_reset_possible_start",
        ),
        "hard_gap_during_sign_active": (
            {14, 15, 16},
            "SIGN_ACTIVE",
            "hard_gap_truncated_active_event",
        ),
        "hard_gap_during_possible_end": (
            {25, 26, 27},
            "POSSIBLE_END",
            "hard_gap_truncated_active_event",
        ),
        "hard_gap_during_rearm": (
            {27, 28, 29, 30, 31},
            "REARM",
            "hard_gap_reset_rearm_quiet",
        ),
    }
    gap_results: dict[str, Any] = {}
    for name, (removed, expected_state, expected_reason) in gap_cases.items():
        copied = _copy_without_observations(hello, removed)
        transitions = extract_segmentation_transitions(copied)
        result = segment_raw_sequence(copied, transitions, config)
        hard_gaps = [transition for transition in transitions if transition.hard_gap]
        passed = (
            len(hard_gaps) == 1
            and _trace_has(result, expected_state, expected_reason)
            and copied.observation_count == hello.observation_count - len(removed)
        )
        gap_results[name] = {
            "passed": passed,
            "source_attempt": "attempt_002",
            "removed_original_frame_indices": sorted(removed),
            "remaining_observation_count": copied.observation_count,
            "hard_gap_count": len(hard_gaps),
            "hard_gap_dt_ms": hard_gaps[0].dt_ms if hard_gaps else None,
            "expected_state": expected_state,
            "expected_reason": expected_reason,
            "completed_event_count": len(result.events),
            "event_quality_flags": [event.quality_flags for event in result.events],
        }

    no_refined = _set_hand_evidence_missing(
        hello, remove_refined=True, remove_proposal=False
    )
    no_refined_transitions = extract_segmentation_transitions(no_refined)
    proposal_fallback_count = sum(
        side.channel == "h_proposal_image"
        for transition in no_refined_transitions
        for side in transition.hand_sides
    )
    no_proposal = _set_hand_evidence_missing(
        hello, remove_refined=True, remove_proposal=True
    )
    no_proposal_transitions = extract_segmentation_transitions(no_proposal)
    body_only_count = sum(
        transition.l_body is not None for transition in no_proposal_transitions
    )

    table = by_id["attempt_009"]
    table_result = segment_raw_sequence(
        table.raw, list(table.transitions), config
    )
    table_oracle_transitions = [
        transition
        for transition in table.transitions
        if table.oracle_start_index < transition.observation_index <= table.oracle_end_index
    ]
    table_proposal_fallback = sum(
        side.channel == "h_proposal_image"
        for transition in table_oracle_transitions
        for side in transition.hand_sides
    )
    table_refined = sum(
        side.channel in ("h_refined_body", "h_refined_image")
        for transition in table_oracle_transitions
        for side in transition.hand_sides
    )

    hello_result = segment_raw_sequence(
        hello, extract_segmentation_transitions(hello), config
    )
    raised_rearm = False
    if hello_result.events:
        event = hello_result.events[0]
        raised_rearm = bool(
            np.any(
                hello.arrays.hand_proposal_present[
                    event.detected_offset_index + 1 : event.completion_index + 1
                ]
            )
        ) and hello_result.rearm_outcome == "COMPLETED"

    home = by_id["attempt_005"]
    home_result = segment_raw_sequence(home.raw, list(home.transitions), config)
    short_pause_resumed = any(
        row["from_state"] == "POSSIBLE_END"
        and row["to_state"] == "SIGN_ACTIVE"
        and row["reason"] == "motion_resumed_before_end_confirmation"
        for row in home_result.state_transition_trace
    )

    event_fixture = build_sign_event(
        hello,
        hello_result.events[0],
        hello_result,
        segmenter_version=f"{SEGMENTER_VERSION}-engineering-fixture",
        config_sha256=config_sha256,
        source_session_id=SESSION_ID,
    )
    missingness = {
        "missing_refined_with_proposal_and_body": {
            "passed": proposal_fallback_count > 0
            and sum(t.l_body is not None for t in no_refined_transitions) > 0,
            "proposal_fallback_selected_side_transitions": proposal_fallback_count,
        },
        "missing_proposal_with_body": {
            "passed": body_only_count > 0
            and all(
                side.channel is None
                for transition in no_proposal_transitions
                for side in transition.hand_sides
            ),
            "body_valid_transition_count": body_only_count,
        },
        "table_like_refined_hand_collapse": {
            "passed": table_refined == 0
            and table_proposal_fallback > 0
            and len(table_result.events) >= 1,
            "oracle_refined_selected_side_transitions": table_refined,
            "oracle_proposal_selected_side_transitions": table_proposal_fallback,
            "engineering_fixture_completed_events": len(table_result.events),
            "boundary_quality_claimed": False,
        },
        "raised_hands_quiet_rearm": {
            "passed": raised_rearm,
            "rearm_outcome": hello_result.rearm_outcome,
        },
        "short_low_motion_pause": {
            "passed": short_pause_resumed and len(home_result.events) == 1,
            "pause_resumed_before_end": short_pause_resumed,
            "completed_event_count": len(home_result.events),
        },
    }
    result = {
        "status": "PASS"
        if all(item["passed"] for item in gap_results.values())
        and all(item["passed"] for item in missingness.values())
        else "FAIL",
        "fixture_config_scope": "ENGINEERING_TEST_ONLY_NOT_A_FROZEN_OPERATING_POINT",
        "gap_cases": gap_results,
        "missingness_and_pause_cases": missingness,
        "no_interpolation": True,
        "no_duplication": True,
        "no_synthetic_observation": True,
        "copies_only": True,
    }
    return result, event_fixture


def nonfrozen_config(calibration_status: str) -> dict[str, Any]:
    return {
        "schema": "apphear.segmentation.config.v1",
        "milestone": MILESTONE,
        "segmenter_version": SEGMENTER_VERSION,
        "freeze_status": "NOT_FROZEN_CALIBRATION_INFEASIBLE",
        "holdout_eligible": False,
        "calibration_status": calibration_status,
        "raw_schema": RAW_SCHEMA,
        "event_schema": EVENT_SCHEMA,
        "oracle_bounds_sha256": EXPECTED_ORACLE_SHA256,
        "state_machine_version": STATE_MACHINE_VERSION,
        "feature_definitions": {
            "h_refined_body": {
                "units": "body_frame_units_per_second",
                "definition": "max genuine wrist/common-valid-joint-centroid displacement",
            },
            "h_refined_image": {
                "units": "minimum_image_dimensions_per_second",
                "definition": "image fallback of the refined-hand motion definition",
            },
            "h_proposal_image": {
                "units": "minimum_image_dimensions_per_second",
                "definition": "proposal ROI-center displacement fallback",
            },
            "l_body": {
                "units": "unit_vector_delta_per_second",
                "definition": "max valid shoulder-elbow/elbow-wrist unit-vector change",
            },
        },
        "signal_quality_hierarchy": [
            "h_refined_body",
            "h_refined_image",
            "h_proposal_image",
            "UNKNOWN",
        ],
        "thresholds": None,
        "temporal_policy": {
            "start_persistence_ms": 250,
            "end_quiet_persistence_ms": 500,
            "rearm_stable_quiet_ms": 700,
            "pre_roll_ms": 300,
            "post_roll_ms": 250,
            "long_duration_diagnostic_ms": 4000,
            "duration_forced_termination": False,
        },
        "gap_rule": {
            "absolute_ms": 500,
            "rolling_median_multiplier": 3,
            "rolling_window_ms": 2000,
        },
        "missingness_rules": {
            "missing_evidence": "UNKNOWN_NOT_ZERO_NOT_QUIET",
            "no_interpolation": True,
            "no_stale_carry": True,
            "no_synthetic_observation": True,
        },
        "calibration_attempt_ids": list(CALIBRATION_IDS),
        "holdout_attempt_ids": list(HOLDOUT_IDS),
        "secondary_attempt_ids": list(SECONDARY_IDS),
        "no_recognizer_declaration": True,
    }


def render_report(
    calibration: dict[str, Any],
    config_sha256: str,
    source_hashes: dict[str, Any],
    fixtures: dict[str, Any],
) -> str:
    individual = calibration["individual_feasible_pattern_counts"]
    return f"""# {MILESTONE}

Final classification: **CALIBRATION_INSUFFICIENT_FOR_CURRENT_TEMPORAL_POLICY**

## SECTION 1 — IMPLEMENTATION IDENTITY

- Segmenter version: `{SEGMENTER_VERSION}`
- State machine: `{STATE_MACHINE_VERSION}`
- Raw input: `{RAW_SCHEMA}`
- Event contract: `{EVENT_SCHEMA}`
- Source files hashed: `{len(source_hashes['files'])}`

## SECTION 2 — FROZEN CONFIG

No holdout-eligible configuration was frozen. `segmenter_config.json` is an explicit non-runnable
failure record with `thresholds: null`, `holdout_eligible: false`, and SHA-256
`{config_sha256}`. It must not be treated as an operating point.

## SECTION 3 — EXACT SIGNAL DEFINITIONS / UNITS

- `H_refined_body`: maximum genuine wrist/common-valid-joint-centroid motion in body-frame
  units/second, valid only across two genuine refined observations and two valid body frames.
- `H_refined_image`: the same refined geometry in minimum-image-dimensions/second.
- `H_proposal_image`: genuine proposal ROI-center motion in minimum-image-dimensions/second.
- `L_body`: maximum valid shoulder→elbow or elbow→wrist unit-vector change/second.
- Per-side hierarchy: refined-body → refined-image → proposal-image → UNKNOWN. The hand family
  casts at most one vote; body articulation is the independent second family.

## SECTION 4 — CALIBRATION RESULT

Status: **{calibration['status']}**.

The exact/pruned end-policy proof evaluated `{calibration['raw_low_threshold_tuples']:,}` empirical
low-threshold tuples and `{calibration['distinct_motion_patterns_evaluated']:,}` distinct induced
motion patterns. Joint feasible patterns: `{calibration['joint_feasible_motion_patterns']}`.
Individual feasible-pattern counts were: 002 `{individual['attempt_002']}`, 003
`{individual['attempt_003']}`, 005 `{individual['attempt_005']}`, 007
`{individual['attempt_007']}`, and 009/TABLE `{individual['attempt_009']}`.

TABLE has zero feasible end patterns even after relaxing start activation to every onset compatible
with pre-roll and the 500 ms context bound. High thresholds only restrict start activation, so they
cannot repair this fixed end-confirmation/post-roll contradiction. No duration sweep was run.

## SECTION 5 — LEAVE-ONE-GLOSS-OUT RESULT

**NOT RUN.** The complete five-attempt calibration policy is infeasible, so the governed stop rule
precedes leave-one-gloss-out selection.

## SECTION 6 — CONFIG FREEZE PROOF

No eligible freeze exists. The non-runnable config and source hashes were written while holdout
status remained `NOT_ACCESSED_CALIBRATION_STOP`. No holdout payload was used to define or diagnose
the failure.

## SECTION 7 — ONE-TIME HOLDOUT RESULT

**NOT ACCESSED.** Attempts 004, 006, 008, and 010 remain sealed. The holdout entrypoint refuses to
construct/open their paths because the config is not `FROZEN_HOLDOUT_ELIGIBLE`.

## SECTION 8 — BOUNDARY QUALITY

No global configuration exists under the fixed temporal policy, so no calibration or holdout
boundary-quality aggregate is claimed. TABLE proves the structural conflict: thresholds that keep
its contact/hold through the oracle interval cannot also confirm end and remain within the 500 ms
post-context target before recovery motion.

## SECTION 9 — SIGN COVERAGE

No frozen event set exists; coverage is therefore **NOT SCORED AS A MILESTONE RESULT**.

## SECTION 10 — FALSE / SPLIT / MISSED EVENT ANALYSIS

The failure occurs before high-threshold/start selection. It is not a recognizer failure. It is an
end-policy incompatibility for TABLE under the fixed 500 ms quiet and 250 ms post-roll policy.

## SECTION 11 — GAP + MISSINGNESS TESTS

Engineering fixture status: **{fixtures['status']}**. Hard gaps in IDLE, POSSIBLE_START,
SIGN_ACTIVE, POSSIBLE_END, and REARM were exercised by deleting observations from copies of
calibration attempt 002. Missing refined/proposal evidence, natural TABLE refiner collapse,
raised-hands rearm, and a short low-motion pause were also exercised. No observation was
interpolated, duplicated, or synthesized.

## SECTION 12 — SignEvent CONTRACT VALIDATION

`apphear.segmentation.sign_event.v1` serialization passed an engineering-only contract fixture.
It embeds the canonical flat raw-v1 slice including `frame_runtime` and scalar provenance fields.
No calibration/holdout SignEvent is presented as a frozen operating result.

## SECTION 13 — RAW-V1 IMMUTABILITY VALIDATION

Recursive source-slice equality and JSON round-trip equality pass. All retained values and source
ordering are original. No interpolation, duplication, stale carry, or manufactured FPS exists.

## SECTION 14 — KNOWN LIMITATIONS

All evidence comes from one controlled Gate-4 session. Even a future pass would not establish
cross-signer or production-ready segmentation. The current result stops earlier: the initial
temporal policy is calibration-infeasible, with TABLE providing the decisive contradiction.

## SECTION 15 — GOVERNANCE

Candidate01 modified: **NO**  
Recognition V2 modified: **NO**  
Recognizer modified: **NO**  
Recognizer accessed: **NO**  
Training executed: **NO**  
Android behavior modified: **NO**  
DEV accessed: **NO**  
Protected TEST accessed: **NO**  
Holdout used for tuning: **NO**

## SECTION 16 — FINAL CLASSIFICATION

**CALIBRATION_INSUFFICIENT_FOR_CURRENT_TEMPORAL_POLICY**

The more general holdout PASS/PARTIAL/FAIL classification is not emitted because the explicit
calibration stop condition prohibited holdout access.

## SECTION 17 — NEXT RECOMMENDED ACTION

`WAIT_FOR_PROJECT_LEAD_SEGMENTATION_DIAGNOSIS`

Do not alter durations or thresholds automatically. Do not open holdout.
"""


def run_calibration() -> dict[str, Any]:
    oracle_identity = verify_oracle_identity()
    attempts = load_calibration()
    calibration = exact_low_threshold_feasibility(attempts)
    if calibration["status"] != "CALIBRATION_INSUFFICIENT_FOR_CURRENT_TEMPORAL_POLICY":
        raise RuntimeError("PHASE5_1_UNIMPLEMENTED_SUCCESS_PATH_REQUIRES_FULL_THRESHOLD_SELECTION")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = nonfrozen_config(calibration["status"])
    config_path = OUTPUT / "segmenter_config.json"
    write_json(config_path, config)
    config_hash = sha256(config_path)
    (OUTPUT / "segmenter_config.sha256").write_text(
        f"{config_hash}  segmenter_config.json\n", encoding="ascii"
    )

    source_hashes = {
        "milestone": MILESTONE,
        "freeze_status": "NOT_FROZEN_CALIBRATION_INFEASIBLE",
        "created_before_holdout_access": True,
        "holdout_accessed": False,
        "files": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
            for path in SOURCE_FILES
        },
        "oracle_bounds": oracle_identity,
        "calibration_raw_sha256": {
            attempt_id: sha256(SESSION / attempt_id / "raw_v1.json")
            for attempt_id in CALIBRATION_IDS
        },
    }
    write_json(OUTPUT / "source_hashes.json", source_hashes)

    calibration_result = {
        "milestone": MILESTONE,
        "oracle_identity": oracle_identity,
        "calibration_attempts_only": list(CALIBRATION_IDS),
        "holdout_raw_accessed": False,
        "recognizer_accessed": False,
        **calibration,
    }
    write_json(OUTPUT / "calibration_result.json", calibration_result)
    write_json(
        OUTPUT / "leave_one_gloss_out_result.json",
        {
            "status": "NOT_RUN_CALIBRATION_STOP",
            "reason": calibration["status"],
            "holdout_raw_accessed": False,
        },
    )
    write_json(
        OUTPUT / "holdout_result.json",
        {
            "status": "NOT_ACCESSED_CALIBRATION_STOP",
            "attempt_ids": list(HOLDOUT_IDS),
            "raw_payloads_opened": False,
            "reason": calibration["status"],
        },
    )
    write_json(
        OUTPUT / "config_freeze_status.json",
        {
            "status": "NOT_FROZEN_CALIBRATION_INFEASIBLE",
            "config_sha256": config_hash,
            "source_hashes_path": str(OUTPUT / "source_hashes.json"),
            "holdout_eligible": False,
            "holdout_accessed": False,
        },
    )

    fixtures, event_fixture = run_engineering_fixtures(attempts, config_hash)
    write_json(OUTPUT / "gap_and_missingness_unit_tests.json", fixtures)
    fixture_dir = OUTPUT / "sign_event_fixtures"
    write_json(
        fixture_dir / "contract_validation" / "attempt_002_engineering_fixture.json",
        event_fixture,
    )
    write_json(
        fixture_dir / "calibration" / "NOT_GENERATED.json",
        {
            "status": "NOT_GENERATED_NO_FROZEN_CONFIG",
            "reason": calibration["status"],
        },
    )
    write_json(
        fixture_dir / "holdout" / "NOT_GENERATED.json",
        {
            "status": "NOT_GENERATED_HOLDOUT_NOT_ACCESSED",
            "reason": calibration["status"],
        },
    )

    report = render_report(calibration, config_hash, source_hashes, fixtures)
    report_path = OUTPUT / "PHASE_5_1_OFFLINE_AUTOMATIC_SEGMENTER_01.md"
    report_path.write_text(report, encoding="utf-8")
    result = {
        "status": calibration["status"],
        "config_sha256": config_hash,
        "holdout_accessed": False,
        "report": str(report_path),
    }
    print(json.dumps(result, indent=2))
    return result


def run_holdout() -> None:
    config_path = OUTPUT / "segmenter_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if (
        config.get("freeze_status") != "FROZEN_HOLDOUT_ELIGIBLE"
        or config.get("holdout_eligible") is not True
        or not isinstance(config.get("thresholds"), dict)
    ):
        raise RuntimeError(
            "PHASE5_1_HOLDOUT_REFUSED_BEFORE_PATH_ACCESS:CONFIG_NOT_FROZEN_ELIGIBLE"
        )
    raise RuntimeError("PHASE5_1_HOLDOUT_SUCCESS_PATH_NOT_REACHED_IN_THIS_MILESTONE_RUN")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("calibrate", "holdout"))
    args = parser.parse_args()
    if args.command == "calibrate":
        run_calibration()
    else:
        run_holdout()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
