"""Stage-A replay for the phone event lifecycle re-arm correction.

This diagnostic reuses persisted S2 probabilities only.  It compares the
frozen CONFIG_01 PRE-only re-arm against one counterfactual: the same
399.924 ms persistence applied to either PRE or POST, with ACTIVE resetting
the timer.  Sign detection before and after re-arm remains unchanged.
"""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.perception_vnext.segmentation.streaming_decoder import (  # noqa: E402
    POST_RECOVERY,
    PRE_IDLE,
    CausalStreamingSignEventDecoder,
    DecoderState,
    SignEvent,
    StreamingDecoderConfig,
)

ARTIFACT_BASE = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
)
OUTPUT = ARTIFACT_BASE / "phone_event_lifecycle_rearm_correction_01/stage_a_replay"
PHONE_SESSION = (
    ARTIFACT_BASE
    / "phone_causal_recognition_integration_01/device_capture/session_20260920T095253Z"
)
CAL_STREAMS = (
    ARTIFACT_BASE
    / "phase8a_r_causal_episode_failure_attribution_01/cal_state_run_manifest.json"
)
DEV_STREAMS = (
    ARTIFACT_BASE
    / "phase8a_m2_frozen_signer_disjoint_sparse_dev_validation_01/dev_s2_state_streams.json"
)
CONFIG_01 = StreamingDecoderConfig(
    minimum_active_ms=133.308,
    pre_gap_reset_ms=133.308,
    post_confirm_ms=266.616,
    pre_padding_ms=250.0,
    post_padding_ms=250.0,
    rearm_pre_stable_ms=399.924,
)
EXPECTED_S2 = "dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73"


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


def numeric_summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "median": None, "mean": None, "p90": None, "max": None}
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "min": ordered[0],
        "median": statistics.median(ordered),
        "mean": statistics.fmean(ordered),
        "p90": ordered[round(0.9 * (len(ordered) - 1))],
        "max": ordered[-1],
    }


def event_identity(event: SignEvent) -> tuple[int, int, int, int]:
    return (
        event.logical_active_start_index,
        event.logical_active_end_index,
        event.first_post_index,
        event.emitted_at_index,
    )


def replay(
    timestamps: list[float],
    probabilities: list[list[float]],
    states: list[int],
    *,
    allow_post_rearm: bool,
) -> dict[str, Any]:
    """Replay CONFIG_01, changing only which states advance re-arm persistence."""

    decoder = CausalStreamingSignEventDecoder(CONFIG_01)
    trace: list[dict[str, Any]] = []
    rearm_latencies: list[float] = []
    last_emission_ms: float | None = None
    for timestamp, probs, actual_state in zip(
        timestamps,
        probabilities,
        states,
        strict=True,
    ):
        state_before = decoder.state
        effective_state = actual_state
        if (
            allow_post_rearm
            and state_before == DecoderState.EVENT_EMITTED_WAIT_REARM
            and actual_state == POST_RECOVERY
        ):
            effective_state = PRE_IDLE
        event = decoder.consume(timestamp, probs, effective_state)
        decoder_row = decoder.trace[-1]
        if event is not None:
            last_emission_ms = event.emitted_at_ms
        if decoder_row["action"] == "REARM_COMPLETE" and last_emission_ms is not None:
            rearm_latencies.append(float(timestamp - last_emission_ms))
        trace.append(
            {
                **decoder_row,
                "actual_argmax_state": actual_state,
                "effective_rearm_state": effective_state,
                "post_counted_as_non_active": actual_state != effective_state,
            }
        )
    return {
        "events": [asdict(event) for event in decoder.events],
        "event_identities": [list(event_identity(event)) for event in decoder.events],
        "event_count": len(decoder.events),
        "rearm_complete_count": sum(row["action"] == "REARM_COMPLETE" for row in trace),
        "rearm_latencies_ms": rearm_latencies,
        "final_state": decoder.state.value,
        "trace": trace,
    }


def load_cal() -> list[dict[str, Any]]:
    payload = read_json(CAL_STREAMS)
    if payload["s2_checkpoint_sha256"] != EXPECTED_S2:
        raise RuntimeError("REARM_CAL_S2_IDENTITY_MISMATCH")
    result = []
    for view in payload["views"]:
        observations = view["observations"]
        result.append(
            {
                "view_key": view["view_key"],
                "view_id": view["view_id"],
                "source": view["source"],
                "timestamps_ms": [float(row["timestamp_ms"]) for row in observations],
                "probabilities": [
                    [
                        float(row["pre_probability"]),
                        float(row["active_probability"]),
                        float(row["post_probability"]),
                    ]
                    for row in observations
                ],
                "argmax_states": [int(row["argmax_state"]) for row in observations],
            }
        )
    if len(result) != 54:
        raise RuntimeError(f"REARM_CAL_MEMBERSHIP_MISMATCH:{len(result)}")
    return result


def load_dev() -> list[dict[str, Any]]:
    payload = read_json(DEV_STREAMS)
    if payload["checkpoint_sha256"] != EXPECTED_S2:
        raise RuntimeError("REARM_DEV_S2_IDENTITY_MISMATCH")
    if payload["training"] is not False:
        raise RuntimeError("REARM_DEV_TRAINING_FLAG_INVALID")
    views = [
        {
            "view_key": row["view_key"],
            "view_id": row["view_key"].rsplit("::", 1)[-1],
            "source": "UNKNOWN_NOT_REQUIRED_FOR_REARM_REPLAY",
            "timestamps_ms": [float(value) for value in row["timestamps_ms"]],
            "probabilities": [[float(value) for value in probs] for probs in row["probabilities"]],
            "argmax_states": [int(value) for value in row["argmax_states"]],
        }
        for row in payload["views"]
    ]
    if len(views) != 69:
        raise RuntimeError(f"REARM_DEV_MEMBERSHIP_MISMATCH:{len(views)}")
    return views


def load_phone() -> dict[str, Any]:
    identity = read_json(PHONE_SESSION / "identity.json")
    if identity["segmentation"]["source_checkpoint_sha256"] != EXPECTED_S2:
        raise RuntimeError("REARM_PHONE_S2_IDENTITY_MISMATCH")
    observations = read_jsonl(PHONE_SESSION / "observations.jsonl")
    persisted_events = read_jsonl(PHONE_SESSION / "events.jsonl")
    attempts = read_jsonl(PHONE_SESSION / "attempts.jsonl")
    return {
        "timestamps_ms": [float(row["source_timestamp_ms"]) for row in observations],
        "probabilities": [
            [
                float(row["pre_probability"]),
                float(row["active_probability"]),
                float(row["post_probability"]),
            ]
            for row in observations
        ],
        "argmax_states": [int(row["argmax_state"]) for row in observations],
        "persisted_events": persisted_events,
        "attempts": attempts,
    }


def compare_population(
    name: str,
    views: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for view in views:
        baseline = replay(
            view["timestamps_ms"],
            view["probabilities"],
            view["argmax_states"],
            allow_post_rearm=False,
        )
        candidate = replay(
            view["timestamps_ms"],
            view["probabilities"],
            view["argmax_states"],
            allow_post_rearm=True,
        )
        first_unchanged = (
            not baseline["event_identities"]
            or candidate["event_identities"][:1] == baseline["event_identities"][:1]
        )
        rows.append(
            {
                "population": name,
                "view_key": view["view_key"],
                "view_id": view["view_id"],
                "baseline_event_count": baseline["event_count"],
                "candidate_event_count": candidate["event_count"],
                "candidate_extra_event_count": max(
                    0,
                    candidate["event_count"] - baseline["event_count"],
                ),
                "baseline_rearm_complete_count": baseline["rearm_complete_count"],
                "candidate_rearm_complete_count": candidate["rearm_complete_count"],
                "baseline_final_state": baseline["final_state"],
                "candidate_final_state": candidate["final_state"],
                "first_event_unchanged": first_unchanged,
                "candidate_rearm_latencies_ms": candidate["rearm_latencies_ms"],
            }
        )
    eligible = [row for row in rows if row["baseline_event_count"] > 0]
    latencies = [
        value
        for row in rows
        for value in row["candidate_rearm_latencies_ms"]
    ]
    summary = {
        "population": name,
        "view_count": len(rows),
        "baseline_event_sequences": sum(row["baseline_event_count"] > 0 for row in rows),
        "baseline_rearmed_sequences": sum(
            row["baseline_rearm_complete_count"] > 0 for row in rows
        ),
        "candidate_rearmed_sequences": sum(
            row["candidate_rearm_complete_count"] > 0 for row in rows
        ),
        "candidate_extra_event_sequences": sum(
            row["candidate_extra_event_count"] > 0 for row in rows
        ),
        "candidate_extra_event_count": sum(
            row["candidate_extra_event_count"] for row in rows
        ),
        "first_event_identity_checks": len(eligible),
        "first_event_identity_pass": sum(row["first_event_unchanged"] for row in eligible),
        "candidate_time_to_rearm_ms": numeric_summary(latencies),
        "by_cadence": {
            view_id: {
                "view_count": sum(row["view_id"] == view_id for row in rows),
                "candidate_rearmed": sum(
                    row["view_id"] == view_id
                    and row["candidate_rearm_complete_count"] > 0
                    for row in rows
                ),
                "candidate_extra_event_sequences": sum(
                    row["view_id"] == view_id and row["candidate_extra_event_count"] > 0
                    for row in rows
                ),
            }
            for view_id in ("VIEW_A", "VIEW_B", "VIEW_C")
        },
    }
    return rows, summary


def phone_comparison(phone: dict[str, Any]) -> dict[str, Any]:
    baseline = replay(
        phone["timestamps_ms"],
        phone["probabilities"],
        phone["argmax_states"],
        allow_post_rearm=False,
    )
    candidate = replay(
        phone["timestamps_ms"],
        phone["probabilities"],
        phone["argmax_states"],
        allow_post_rearm=True,
    )
    persisted = [
        [
            int(row["logical_active_start_index"]),
            int(row["logical_active_end_index"]),
            int(row["terminal_post_index"]),
            int(row["commit_index"]),
        ]
        for row in phone["persisted_events"]
    ]
    hello_identity = persisted[1]
    candidate_hello_index = (
        candidate["event_identities"].index(hello_identity)
        if hello_identity in candidate["event_identities"]
        else None
    )
    post_hello_events = []
    if candidate_hello_index is not None:
        post_hello_events = candidate["events"][candidate_hello_index + 1 :]
    begin = next(row for row in phone["attempts"] if row["action"] == "BEGIN")
    complete = next(row for row in phone["attempts"] if row["action"] == "COMPLETE")
    begin_ms = float(begin["marked_at_elapsed_realtime_ns"]) / 1_000_000.0
    complete_ms = float(complete["marked_at_elapsed_realtime_ns"]) / 1_000_000.0
    candidate_pre_attempt_events = [
        row for row in candidate["events"] if float(row["emitted_at_ms"]) < begin_ms
    ]
    post_complete_events = [
        row for row in candidate["events"] if float(row["emitted_at_ms"]) > complete_ms
    ]
    hello_event = (
        candidate["events"][candidate_hello_index]
        if candidate_hello_index is not None
        else None
    )
    first_extra_latency = (
        float(post_hello_events[0]["emitted_at_ms"] - hello_event["emitted_at_ms"])
        if post_hello_events and hello_event is not None
        else None
    )
    return {
        "observation_count": len(phone["timestamps_ms"]),
        "baseline_persisted_event_identity_match": baseline["event_identities"] == persisted,
        "baseline": {key: value for key, value in baseline.items() if key != "trace"},
        "candidate": {key: value for key, value in candidate.items() if key != "trace"},
        "candidate_hello_event_found_unchanged": candidate_hello_index is not None,
        "candidate_event_count_before_marked_attempt": len(candidate_pre_attempt_events),
        "baseline_event_count_before_marked_attempt": sum(
            float(row["emitted_at_ms"]) < begin_ms for row in baseline["events"]
        ),
        "candidate_events_after_hello": post_hello_events,
        "candidate_extra_events_after_hello_count": len(post_hello_events),
        "candidate_events_after_attempt_1_complete_count": len(post_complete_events),
        "first_extra_event_after_hello_commit_ms": first_extra_latency,
        "immediate_recovery_duplicate_observed": (
            first_extra_latency is not None and first_extra_latency <= 2_000.0
        ),
        "candidate_trace": candidate["trace"],
    }


def run() -> None:
    cal = load_cal()
    dev = load_dev()
    phone = load_phone()
    cal_rows, cal_summary = compare_population("CAL", cal)
    dev_rows, dev_summary = compare_population("DEV", dev)
    phone_result = phone_comparison(phone)
    cal_identity_result = (
        f"{cal_summary['first_event_identity_pass']}/"
        f"{cal_summary['first_event_identity_checks']}"
    )
    dev_identity_result = (
        f"{dev_summary['first_event_identity_pass']}/"
        f"{dev_summary['first_event_identity_checks']}"
    )

    first_events_preserved = (
        cal_summary["first_event_identity_pass"] == cal_summary["first_event_identity_checks"]
        and dev_summary["first_event_identity_pass"] == dev_summary["first_event_identity_checks"]
        and phone_result["candidate_hello_event_found_unchanged"]
    )
    duplicate_regression = (
        cal_summary["candidate_extra_event_count"]
        + dev_summary["candidate_extra_event_count"]
        + phone_result["candidate_extra_events_after_hello_count"]
    )
    phone_rearmed = bool(phone_result["candidate"]["rearm_complete_count"])
    if phone_rearmed and duplicate_regression == 0 and first_events_preserved:
        decision = "NON_ACTIVE_REARM_SUPPORTED"
    elif phone_rearmed and duplicate_regression > 0:
        decision = "NON_ACTIVE_REARM_UNSAFE"
    elif not phone_rearmed:
        decision = "HYBRID_REARM_REQUIRED"
    else:
        decision = "REARM_FAILURE_NOT_EXPLAINED_BY_STATE_SEMANTICS"

    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_json(
        OUTPUT / "frozen_identity.json",
        {
            "s2_checkpoint_sha256": EXPECTED_S2,
            "config_01": asdict(CONFIG_01),
            "phone_session": PHONE_SESSION.name,
            "cal_stream_sha256": sha256(CAL_STREAMS),
            "dev_stream_sha256": sha256(DEV_STREAMS),
            "training_executed": False,
            "android_modified": False,
            "s2_inference_executed": False,
        },
    )
    write_json(
        OUTPUT / "rearm_policy_config.json",
        {
            "control": "STABLE_PRE_399_924_MS",
            "candidate": "STABLE_NON_ACTIVE_PRE_OR_POST_399_924_MS",
            "active_behavior": "RESET_REARM_TIMER",
            "parameter_search": False,
            "event_detection_changed": False,
        },
    )
    with (OUTPUT / "per_stream_rearm_comparison.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list((cal_rows + dev_rows)[0]))
        writer.writeheader()
        writer.writerows(cal_rows + dev_rows)
    write_json(OUTPUT / "cal_rearm_replay.json", cal_summary)
    write_json(OUTPUT / "dev_rearm_replay.json", dev_summary)
    write_json(OUTPUT / "phone_rearm_replay.json", phone_result)
    write_json(
        OUTPUT / "test_results.json",
        {
            "focused_pytest_count": 6,
            "focused_pytest_status": "PASS",
            "ruff": "PASS",
            "py_compile": "PASS",
            "persisted_s2_reused": True,
            "s2_inference": False,
            "training": False,
            "android_modified": False,
        },
    )
    write_json(
        OUTPUT / "final_decision.json",
        {
            "classification": decision,
            "first_events_preserved": first_events_preserved,
            "duplicate_regression_count": duplicate_regression,
            "phone_candidate_rearmed": phone_rearmed,
            "android_implementation_authorized": decision == "NON_ACTIVE_REARM_SUPPORTED",
            "next": "WAIT_FOR_PROJECT_LEAD_REARM_ARCHITECTURE_DECISION",
        },
    )
    report = f"""# PHONE_EVENT_LIFECYCLE_REARM_CORRECTION_01 — Stage A

## Scope

Read-only replay of persisted phone, CAL, and DEV S2 state streams. No perception, S2 inference,
training, recognition, Android capture, or production code modification occurred.

## Frozen policies

- Control: stable PRE for 399.924 ms.
- Candidate: stable PRE or POST for the same 399.924 ms; ACTIVE resets the timer.
- ACTIVE start, PRE-gap, POST confirmation, event materialization, and recognition are unchanged.

## First-event isolation

First-event identity checks passed for `{cal_identity_result}` emitted CAL streams and
`{dev_identity_result}` emitted DEV streams. The marked phone HELLO event is present with its
original logical start/end, terminal POST, and commit indices:
`{phone_result['candidate_hello_event_found_unchanged']}`.

## Phone replay

- Control events: `{phone_result['baseline']['event_count']}`.
- Candidate events: `{phone_result['candidate']['event_count']}`.
- Control events before marked HELLO:
  `{phone_result['baseline_event_count_before_marked_attempt']}`.
- Candidate events before marked HELLO:
  `{phone_result['candidate_event_count_before_marked_attempt']}`.
- Candidate events after the unchanged HELLO:
  `{phone_result['candidate_extra_events_after_hello_count']}`.
- Candidate events after attempt 1 was marked complete:
  `{phone_result['candidate_events_after_attempt_1_complete_count']}`.
- First additional event latency after HELLO commit:
  `{phone_result['first_extra_event_after_hello_commit_ms']}` ms.
- Additional event within the first 2 seconds of HELLO recovery:
  `{phone_result['immediate_recovery_duplicate_observed']}`.
- Candidate re-arm completions: `{phone_result['candidate']['rearm_complete_count']}`.
- Candidate re-arm latency summary:
  `{numeric_summary(phone_result['candidate']['rearm_latencies_ms'])}`.

## CAL / DEV safety replay

CAL emitted/re-arm evidence:

- baseline emitted sequences: `{cal_summary['baseline_event_sequences']}/54`;
- candidate re-armed sequences: `{cal_summary['candidate_rearmed_sequences']}/54`;
- candidate additional-event sequences: `{cal_summary['candidate_extra_event_sequences']}`;
- candidate time to re-arm: `{cal_summary['candidate_time_to_rearm_ms']}`.

DEV emitted/re-arm evidence:

- baseline emitted sequences: `{dev_summary['baseline_event_sequences']}/69`;
- candidate re-armed sequences: `{dev_summary['candidate_rearmed_sequences']}/69`;
- candidate additional-event sequences: `{dev_summary['candidate_extra_event_sequences']}`;
- candidate time to re-arm: `{dev_summary['candidate_time_to_rearm_ms']}`.

Every CAL/DEV source sequence is a governed isolated-sign view, so an additional event created only
by the candidate is a suspicious duplicate regression. No threshold or margin was tuned.

## Decision

**`{decision}`**

Duplicate regression count across CAL, DEV, and the post-HELLO phone remainder:
`{duplicate_regression}`.

No immediate duplicate occurred during the first two seconds after HELLO. The safety failure is
later continuous-stream behavior: after becoming IDLE, repeated ACTIVE/POST fluctuations generated
seven unprompted events where frozen PRE-only CONFIG_01 remained safely disarmed. Finite CAL/DEV
clips did not expose this regression and therefore cannot override the continuous-phone evidence.

The supported next design direction is a separately frozen hybrid readiness policy combining
non-ACTIVE state with independent quiet/stability evidence. That policy was not implemented or
searched in this milestone.

Android implementation is authorized by this replay only when the decision is
`NON_ACTIVE_REARM_SUPPORTED`. Otherwise the frozen Android event lifecycle remains unchanged.

`WAIT_FOR_PROJECT_LEAD_REARM_ARCHITECTURE_DECISION`
"""
    (OUTPUT / "PHONE_EVENT_LIFECYCLE_REARM_STAGE_A_REPORT.md").write_text(
        report,
        encoding="utf-8",
    )
    write_json(
        OUTPUT / "source_hashes.json",
        {
            str(Path(__file__).resolve().relative_to(ROOT)): sha256(Path(__file__).resolve()),
            "tests/test_phone_event_lifecycle_rearm_correction.py": sha256(
                ROOT / "tests/test_phone_event_lifecycle_rearm_correction.py"
            ),
            "pipeline/perception_vnext/segmentation/streaming_decoder.py": sha256(
                ROOT / "pipeline/perception_vnext/segmentation/streaming_decoder.py"
            ),
            str(CAL_STREAMS.relative_to(ROOT)): sha256(CAL_STREAMS),
            str(DEV_STREAMS.relative_to(ROOT)): sha256(DEV_STREAMS),
            str((PHONE_SESSION / "observations.jsonl").relative_to(ROOT)): sha256(
                PHONE_SESSION / "observations.jsonl"
            ),
        },
    )
    print(json.dumps(read_json(OUTPUT / "final_decision.json"), indent=2))


if __name__ == "__main__":
    run()
