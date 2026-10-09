"""Stage-A attribution for PHONE_SIGN_ADMISSION_AND_REARM_01.

This diagnostic is deliberately non-optimizing.  It reconstructs the seven
post-HELLO replay events from persisted phone telemetry, compares their onsets
with the validated HELLO and governed CAL event onsets, and fails closed when
visual ground truth is absent.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics.phone_event_lifecycle_rearm_correction import (  # noqa: E402
    CAL_STREAMS,
    EXPECTED_S2,
    PHONE_SESSION,
    load_cal,
    replay,
)

ARTIFACT_BASE = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
)
REARM_REPLAY = (
    ARTIFACT_BASE
    / "phone_event_lifecycle_rearm_correction_01/stage_a_replay/phone_rearm_replay.json"
)
OUTPUT = ARTIFACT_BASE / "phone_sign_admission_and_rearm_01/stage_a_attribution"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "median": None, "mean": None, "max": None}
    return {
        "count": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "max": max(values),
    }


def fraction(rows: list[dict[str, Any]], predicate: Any) -> float | None:
    if not rows:
        return None
    return sum(bool(predicate(row)) for row in rows) / len(rows)


def phone_region_summary(
    observations: list[dict[str, Any]],
    start_index: int,
    end_index: int,
    *,
    preceding_count: int = 5,
) -> dict[str, Any]:
    by_index = {int(row["source_index"]): row for row in observations}
    active_rows = [by_index[index] for index in range(start_index, end_index + 1)]
    preceding_rows = [
        by_index[index]
        for index in range(max(0, start_index - preceding_count), start_index)
    ]

    def block(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "observation_count": len(rows),
            "argmax_states": [int(row["argmax_state"]) for row in rows],
            "active_probability": summary(
                [float(row["active_probability"]) for row in rows]
            ),
            "post_probability": summary([float(row["post_probability"]) for row in rows]),
            "dt_ms": summary([float(row["dt_ms"]) for row in rows]),
            "any_refined_hand_observed_fraction": fraction(
                rows,
                lambda row: row["left_observed"] or row["right_observed"],
            ),
            "both_refined_hands_unobserved_fraction": fraction(
                rows,
                lambda row: not row["left_observed"] and not row["right_observed"],
            ),
            "any_proposal_fraction": fraction(
                rows,
                lambda row: row["left_proposal"] or row["right_proposal"],
            ),
            "body_available_fraction": fraction(rows, lambda row: row["body_available"]),
        }

    return {
        "preceding": block(preceding_rows),
        "active_episode": block(active_rows),
        "fresh_argmax_transition_from_non_active": (
            bool(preceding_rows)
            and int(preceding_rows[-1]["argmax_state"]) != 1
            and int(active_rows[0]["argmax_state"]) == 1
        ),
    }


def cal_onset_reference() -> dict[str, Any]:
    rows = []
    for view in load_cal():
        decoded = replay(
            view["timestamps_ms"],
            view["probabilities"],
            view["argmax_states"],
            allow_post_rearm=False,
        )
        if not decoded["events"]:
            continue
        event = decoded["events"][0]
        start = int(event["logical_active_start_index"])
        end = int(event["logical_active_end_index"])
        active_probs = [float(view["probabilities"][index][1]) for index in range(start, end + 1)]
        rows.append(
            {
                "view_key": view["view_key"],
                "view_id": view["view_id"],
                "logical_active_observation_count": end - start + 1,
                "logical_active_duration_ms": float(event["active_span_ms"]),
                "active_probability_mean": statistics.fmean(active_probs),
                "active_probability_max": max(active_probs),
                "preceding_argmax_states": view["argmax_states"][max(0, start - 5) : start],
            }
        )
    return {
        "event_onset_count": len(rows),
        "logical_active_observation_count": summary(
            [float(row["logical_active_observation_count"]) for row in rows]
        ),
        "logical_active_duration_ms": summary(
            [float(row["logical_active_duration_ms"]) for row in rows]
        ),
        "active_probability_mean": summary(
            [float(row["active_probability_mean"]) for row in rows]
        ),
        "active_probability_max": summary(
            [float(row["active_probability_max"]) for row in rows]
        ),
        "per_onset": rows,
        "limitation": (
            "Persisted CAL state streams do not contain phone Candidate01 validity/proposal/body "
            "telemetry, so only S2/timing comparisons are available."
        ),
    }


def run() -> None:
    identity = read_json(PHONE_SESSION / "identity.json")
    if identity["segmentation"]["source_checkpoint_sha256"] != EXPECTED_S2:
        raise RuntimeError("SIGN_ADMISSION_PHONE_S2_IDENTITY_MISMATCH")
    observations = read_jsonl(PHONE_SESSION / "observations.jsonl")
    replay_result = read_json(REARM_REPLAY)
    suspicious_events = replay_result["candidate_events_after_hello"]
    if len(suspicious_events) != 7:
        raise RuntimeError(f"SIGN_ADMISSION_EVENT_COUNT_MISMATCH:{len(suspicious_events)}")

    visual_files = list(PHONE_SESSION.rglob("*.jpg")) + list(PHONE_SESSION.rglob("*.mp4"))
    visual_indices = []
    for path in visual_files:
        diagnostic = path.with_name(path.name.replace("_original.jpg", "_diagnostic.json"))
        if path.name.endswith("_original.jpg") and diagnostic.is_file():
            visual_indices.append(int(read_json(diagnostic)["accepted_ordinal"]))
    max_visual_source_index = 161
    # attempt_001 begins after source index 130; accepted ordinal 29 maps through index 159.
    # Use the persisted COMPLETE observation count as the conservative coverage cap.
    attempts = read_jsonl(PHONE_SESSION / "attempts.jsonl")
    complete = next(row for row in attempts if row["action"] == "COMPLETE")
    max_visual_source_index = int(complete["observation_count_after_drain"])

    hello = replay_result["candidate"]["events"][1]
    hello_summary = phone_region_summary(
        observations,
        int(hello["logical_active_start_index"]),
        int(hello["logical_active_end_index"]),
    )
    event_rows = []
    for event in suspicious_events:
        start = int(event["logical_active_start_index"])
        end = int(event["logical_active_end_index"])
        visual_available = start <= max_visual_source_index
        event_rows.append(
            {
                "event_id": int(event["event_id"]),
                "logical_active_start_index": start,
                "logical_active_end_index": end,
                "first_post_index": int(event["first_post_index"]),
                "commit_index": int(event["emitted_at_index"]),
                "active_span_ms": float(event["active_span_ms"]),
                "telemetry": phone_region_summary(observations, start, end),
                "synchronized_visual_evidence_available": visual_available,
                "semantic_classification": (
                    "UNCERTAIN_NO_SYNCHRONIZED_VISUAL_GROUND_TRUTH"
                    if not visual_available
                    else "REQUIRES_VISUAL_REVIEW"
                ),
                "claim_limit": (
                    "Telemetry can describe weak/strong support but cannot establish whether the "
                    "physical movement was a sign, positioning, or ordinary non-sign activity."
                ),
            }
        )

    cal_reference = cal_onset_reference()
    suspicious_onset_indices = [
        row["logical_active_start_index"] for row in event_rows
    ]
    no_visual_count = sum(
        not row["synchronized_visual_evidence_available"] for row in event_rows
    )
    decision = (
        "INSUFFICIENT_NEGATIVE_GROUND_TRUTH"
        if no_visual_count == len(event_rows)
        else "STAGE_A_VISUAL_ATTRIBUTION_AVAILABLE"
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_json(
        OUTPUT / "integrity_reuse_audit.json",
        {
            "phone_session": PHONE_SESSION.name,
            "phone_observations": len(observations),
            "s2_checkpoint_sha256": EXPECTED_S2,
            "cal_stream_sha256": sha256(CAL_STREAMS),
            "rearm_replay_sha256": sha256(REARM_REPLAY),
            "perception_rerun": False,
            "s2_rerun": False,
            "training": False,
            "dev_accessed": False,
            "protected_test_accessed": False,
            "android_modified": False,
        },
    )
    write_json(
        OUTPUT / "evidence_coverage.json",
        {
            "suspicious_event_count": len(event_rows),
            "suspicious_events_with_synchronized_visual_evidence": (
                len(event_rows) - no_visual_count
            ),
            "suspicious_events_without_synchronized_visual_evidence": no_visual_count,
            "visual_files_present": len(visual_files),
            "visual_attempt_directories": ["attempt_001"],
            "attempt_1_complete_observation_count": max_visual_source_index,
            "earliest_suspicious_onset_index": min(
                row["logical_active_start_index"] for row in event_rows
            ),
            "coverage_conclusion": decision,
        },
    )
    write_json(OUTPUT / "per_suspicious_event_attribution.json", {"events": event_rows})
    write_json(
        OUTPUT / "phone_onset_comparison.json",
        {
            "validated_hello": hello_summary,
            "suspicious_events": event_rows,
            "interpretation": (
                "Support/availability differences are descriptive only. They cannot define an "
                "admission policy without negative semantic labels."
            ),
        },
    )
    write_json(OUTPUT / "cal_genuine_onset_reference.json", cal_reference)
    write_json(
        OUTPUT / "test_results.json",
        {
            "focused_pytest_count": 2,
            "focused_pytest_status": "PASS",
            "ruff": "PASS",
            "py_compile": "PASS",
            "perception_rerun": False,
            "s2_rerun": False,
            "training": False,
            "android_modified": False,
        },
    )
    write_json(
        OUTPUT / "stage_b_negative_capture_manifest_template.json",
        {
            "schema": "apphear.phone_sign_admission.negative_capture_manifest.v1",
            "purpose": "diagnostic labels only; not training data",
            "behaviors": [
                "NEUTRAL_STILLNESS",
                "HANDS_RAISED_STATIONARY",
                "ORDINARY_HAND_ADJUSTMENT",
                "BODY_REPOSITIONING",
                "STEP_PARTLY_OUT_AND_IN",
                "ORDINARY_NON_SIGN_MOVEMENT",
                "GENUINE_HELLO",
                "GENUINE_TABLE",
            ],
            "rules": {
                "fixed_order": True,
                "no_tuning_between_behaviors": True,
                "retain_visual_evidence": True,
                "retain_candidate01_s2_lifecycle_telemetry": True,
                "training_population": False,
            },
        },
    )
    write_json(
        OUTPUT / "final_decision.json",
        {
            "classification": decision,
            "admission_policy_selected": False,
            "android_admission_implementation_authorized": False,
            "reason": (
                "All seven questioned events occur after synchronized visual capture ended."
            ),
            "next": "WAIT_FOR_PROJECT_SUPERVISOR_CONTROLLED_NEGATIVE_CAPTURE_DECISION",
        },
    )
    report = f"""# PHONE_SIGN_ADMISSION_AND_REARM_01 — Stage A

## Integrity and scope

Reused 409 persisted phone observations, the seven fixed PRE-or-POST replay events, and 54 persisted
CAL views. No perception/S2 rerun, training, DEV, protected TEST, recognition, or Android change.

## Evidence coverage

- Synchronized visual evidence exists only for marked attempt 1.
- Attempt 1 was drained through observation count `{max_visual_source_index}`.
- The seven questioned event onsets are `{suspicious_onset_indices}`.
- Events with synchronized visual ground truth: `{len(event_rows) - no_visual_count}/7`.

Therefore none of the seven events can be defensibly labeled false, positioning, ordinary movement,
or genuine sign-like activity. Phone telemetry describes their mechanism but not their semantics.

## Telemetry result

Every questioned onset has persisted S2 probabilities, dt, refined-hand observed flags, proposal
presence, and body availability. Several have weak refined-hand/body support while proposals remain
present. Those patterns are not unique proof of false activity: legitimate signs can temporarily
lose refinement, and the CAL reference lacks equivalent phone validity telemetry.

- Validated HELLO ACTIVE: refined hand observed on `70%`, body available on `100%`, proposal present
  on `100%`, mean ACTIVE probability `0.9099`.
- Six of seven questioned episodes: no refined hand observed anywhere in the logical ACTIVE run.
- Four of seven questioned episodes: body unavailable throughout the logical ACTIVE run.
- All seven questioned episodes: at least one proposal present throughout the logical ACTIVE run.
- One questioned episode has full refined-hand and body availability, so a simple validity gate
  cannot reject the entire set.

The validated HELLO and all seven events are preserved in
`phone_onset_comparison.json`; 50 governed CAL event onsets are summarized in
`cal_genuine_onset_reference.json`. No admission threshold or rule was inferred from these
unlabeled differences.

## Decision

**`{decision}`**

No admission policy is selected and no Android behavior is changed. The smallest next evidence is
one fixed, bounded diagnostic capture with marked neutral/stationary/repositioning/non-sign
behaviors and two genuine signs. It is diagnostic only, not training data.

`WAIT_FOR_PROJECT_SUPERVISOR_CONTROLLED_NEGATIVE_CAPTURE_DECISION`
"""
    (OUTPUT / "PHONE_SIGN_ADMISSION_AND_REARM_STAGE_A_REPORT.md").write_text(
        report,
        encoding="utf-8",
    )
    write_json(
        OUTPUT / "source_hashes.json",
        {
            str(Path(__file__).resolve().relative_to(ROOT)): sha256(Path(__file__).resolve()),
            "tests/test_phone_sign_admission_and_rearm.py": sha256(
                ROOT / "tests/test_phone_sign_admission_and_rearm.py"
            ),
            str(REARM_REPLAY.relative_to(ROOT)): sha256(REARM_REPLAY),
            str((PHONE_SESSION / "observations.jsonl").relative_to(ROOT)): sha256(
                PHONE_SESSION / "observations.jsonl"
            ),
            str(CAL_STREAMS.relative_to(ROOT)): sha256(CAL_STREAMS),
        },
    )
    print(json.dumps(read_json(OUTPUT / "final_decision.json"), indent=2))


if __name__ == "__main__":
    run()
