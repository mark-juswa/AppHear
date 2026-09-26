"""Read-only regression replay for PHONE_REPEATED_RECOGNITION_INTEGRATION_01.

This utility reuses the persisted phone S2 probabilities. It does not run perception,
S2, Recognition V2, recognition, training, DEV, or protected TEST.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.perception_vnext.segmentation.streaming_decoder import (
    ACTIVE_SIGN,
    POST_RECOVERY,
    CausalStreamingSignEventDecoder,
    DecoderState,
)
from eval.runtime_diagnostics.phone_event_lifecycle_rearm_correction import CONFIG_01


SOURCE_SESSION = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
    / "phone_causal_recognition_integration_01/device_capture/session_20260920T095253Z"
)
OUTPUT = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
    / "phone_repeated_recognition_integration_01"
)
MAXIMUM_CONTINUOUS_OBSERVATION_GAP_MS = 533.232


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(event: dict[str, Any]) -> dict[str, int]:
    return {
        "logical_active_start_index": int(event["logical_active_start_index"]),
        "logical_active_end_index": int(event["logical_active_end_index"]),
        "terminal_post_index": int(event.get("first_post_index", event.get("terminal_post_index"))),
        "commit_index": int(event.get("emitted_at_index", event.get("commit_index"))),
    }


def replay(rows: list[dict[str, Any]], *, allow_post_rearm: bool) -> dict[str, Any]:
    decoder = CausalStreamingSignEventDecoder(CONFIG_01)
    previous_timestamp: float | None = None
    gap_resets: list[dict[str, float]] = []
    rearm_completions: list[dict[str, float]] = []
    last_emission_ms: float | None = None
    trace: list[dict[str, Any]] = []
    for row in rows:
        timestamp = float(row["source_timestamp_ms"])
        actual_state = int(row["argmax_state"])
        gap = None if previous_timestamp is None else timestamp - previous_timestamp
        state_before = decoder.state
        if (
            state_before == DecoderState.EVENT_EMITTED_WAIT_REARM
            and gap is not None
            and gap > MAXIMUM_CONTINUOUS_OBSERVATION_GAP_MS
        ):
            # Exact Android safety meaning: elapsed missing-observation time is not recovery
            # evidence. The current eligible observation may begin a fresh timer.
            decoder._rearm_pre_start_ms = None  # noqa: SLF001 - parity probe of frozen reference
            gap_resets.append({"timestamp_ms": timestamp, "gap_ms": gap})
        effective_state = actual_state
        if (
            allow_post_rearm
            and decoder.state == DecoderState.EVENT_EMITTED_WAIT_REARM
            and actual_state == POST_RECOVERY
        ):
            effective_state = 0
        event = decoder.consume(
            timestamp,
            [
                float(row["pre_probability"]),
                float(row["active_probability"]),
                float(row["post_probability"]),
            ],
            effective_state,
        )
        action = str(decoder.trace[-1]["action"])
        if event is not None:
            last_emission_ms = float(event.emitted_at_ms)
        if action == "REARM_COMPLETE" and last_emission_ms is not None:
            rearm_completions.append(
                {
                    "timestamp_ms": timestamp,
                    "latency_after_event_ms": timestamp - last_emission_ms,
                }
            )
        trace.append(
            {
                **decoder.trace[-1],
                "actual_argmax_state": actual_state,
                "effective_rearm_state": effective_state,
                "observation_gap_ms": gap,
            }
        )
        previous_timestamp = timestamp
    return {
        "policy": "PRE_OR_POST_EXPERIMENTAL" if allow_post_rearm else "PRE_ONLY",
        "maximum_continuous_observation_gap_ms": MAXIMUM_CONTINUOUS_OBSERVATION_GAP_MS,
        "events": [asdict(event) for event in decoder.events],
        "event_count": len(decoder.events),
        "rearm_completions": rearm_completions,
        "rearm_complete_count": len(rearm_completions),
        "gap_reset_count": len(gap_resets),
        "gap_resets": gap_resets,
        "action_counts": dict(Counter(str(item["action"]) for item in trace)),
        "final_state": decoder.state.value,
        "trace": trace,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_replay() -> None:
    observations_path = SOURCE_SESSION / "observations.jsonl"
    events_path = SOURCE_SESSION / "events.jsonl"
    attempts_path = SOURCE_SESSION / "attempts.jsonl"
    rows = read_jsonl(observations_path)
    historical_events = read_jsonl(events_path)
    attempts = read_jsonl(attempts_path)
    if len(rows) != 409 or len(historical_events) != 2:
        raise RuntimeError("PHONE_REPEATED_RECOGNITION_SOURCE_CONTINUITY_MISMATCH")
    hello_events = [event for event in historical_events if event.get("expected_gloss") == "HELLO"]
    if len(hello_events) != 1 or hello_events[0]["top1_gloss"] != "HELLO":
        raise RuntimeError("PHONE_REPEATED_RECOGNITION_HELLO_REFERENCE_MISMATCH")
    historical_hello = hello_events[0]

    control = replay(rows, allow_post_rearm=False)
    experimental = replay(rows, allow_post_rearm=True)
    historical_identity = identity(historical_hello)
    control_matches = [event for event in control["events"] if identity(event) == historical_identity]
    experimental_matches = [event for event in experimental["events"] if identity(event) == historical_identity]
    if len(control_matches) != 1 or len(experimental_matches) != 1:
        raise RuntimeError("PHONE_REPEATED_RECOGNITION_HELLO_EVENT_NOT_FOUND")
    control_identity = identity(control_matches[0])
    experimental_identity = identity(experimental_matches[0])
    hello_preserved = historical_identity == control_identity == experimental_identity
    if not hello_preserved:
        raise RuntimeError("PHONE_REPEATED_RECOGNITION_HELLO_EVENT_DRIFT")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_json(
        OUTPUT / "lifecycle_audit.json",
        {
            "milestone": "PHONE_REPEATED_RECOGNITION_INTEGRATION_01",
            "source_session": SOURCE_SESSION.name,
            "observations": len(rows),
            "historical_events": len(historical_events),
            "marked_attempt_records": len(attempts),
            "single_lifecycle_owner": "PhoneCausalEventProducer",
            "legacy_rearm_also_active": False,
            "control_policy": "PRE_ONLY",
            "experimental_policy": "PRE_OR_POST_EXPERIMENTAL",
            "admission_policy": "PASS_THROUGH",
            "rearm_stability_ms": 399.924,
            "maximum_continuous_observation_gap_ms": MAXIMUM_CONTINUOUS_OBSERVATION_GAP_MS,
            "training_executed": False,
            "dev_accessed": False,
            "protected_test_accessed": False,
        },
    )
    write_json(
        OUTPUT / "persisted_phone_replay.json",
        {"control": control, "experimental": experimental},
    )
    write_json(
        OUTPUT / "known_hello_regression.json",
        {
            "hello_event_identity_preserved": hello_preserved,
            "historical_event": historical_identity,
            "control_event": control_identity,
            "experimental_event": experimental_identity,
            "historical_materialized_start_index": historical_hello["materialized_start_index"],
            "historical_materialized_end_index": historical_hello["materialized_end_index"],
            "historical_recognition_v2_valid_count": historical_hello["recognition_v2_valid_count"],
            "historical_recognition_v2_mask_count": historical_hello["recognition_v2_mask_count"],
            "historical_top1_gloss": historical_hello["top1_gloss"],
            "historical_top1_probability": historical_hello["top1_probability"],
            "downstream_recomputation_required": False,
            "reason": "The first logical event is identical and the lifecycle change begins after commit.",
        },
    )
    write_json(
        OUTPUT / "source_hashes.json",
        {
            str(observations_path.relative_to(ROOT)): sha256(observations_path),
            str(events_path.relative_to(ROOT)): sha256(events_path),
            str(attempts_path.relative_to(ROOT)): sha256(attempts_path),
            str(Path(__file__).resolve().relative_to(ROOT)): sha256(Path(__file__).resolve()),
        },
    )
    print(
        json.dumps(
            {
                "hello_preserved": hello_preserved,
                "control_rearms": control["rearm_complete_count"],
                "experimental_rearms": experimental["rearm_complete_count"],
                "experimental_events": experimental["event_count"],
                "experimental_gap_resets": experimental["gap_reset_count"],
            },
            indent=2,
        )
    )


def summarize_session(session_root: Path) -> None:
    identity_path = session_root / "identity.json"
    observations_path = session_root / "observations.jsonl"
    events_path = session_root / "events.jsonl"
    attempts_path = session_root / "attempts.jsonl"
    for required in (identity_path, observations_path, events_path, attempts_path):
        if not required.is_file():
            raise RuntimeError(f"PHONE_REPEATED_RECOGNITION_MISSING_ARTIFACT: {required}")
    identity_value = json.loads(identity_path.read_text(encoding="utf-8"))
    if identity_value.get("milestone") != "PHONE_REPEATED_RECOGNITION_INTEGRATION_01":
        raise RuntimeError("PHONE_REPEATED_RECOGNITION_IDENTITY_MISMATCH")
    decoder = identity_value.get("decoder", {})
    if decoder.get("rearm_policy") != "PRE_OR_POST_EXPERIMENTAL":
        raise RuntimeError("PHONE_REPEATED_RECOGNITION_REARM_POLICY_MISMATCH")
    if decoder.get("admission_policy") != "PASS_THROUGH":
        raise RuntimeError("PHONE_REPEATED_RECOGNITION_ADMISSION_POLICY_MISMATCH")

    observations = read_jsonl(observations_path)
    events = read_jsonl(events_path)
    attempts = read_jsonl(attempts_path)
    completed_attempts = [row for row in attempts if row.get("action") == "COMPLETE"]
    begin_attempts = [row for row in attempts if row.get("action") == "BEGIN"]
    rearm_completions = [row for row in observations if row.get("event_action") == "REARM_COMPLETE"]
    gap_resets = [
        row
        for row in observations
        if str(row.get("event_action", "")).startswith("RESET_REARM_GAP")
    ]
    attempt_rows: list[dict[str, Any]] = []
    for begin in begin_attempts:
        attempt_id = int(begin["attempt_id"])
        matching_events = [event for event in events if event.get("attempt_id") == attempt_id]
        attempt_rows.append(
            {
                "attempt_id": attempt_id,
                "expected_gloss": begin.get("expected_gloss"),
                "completed": any(int(row["attempt_id"]) == attempt_id for row in completed_attempts),
                "event_count": len(matching_events),
                "events": [
                    {
                        "event_id": event.get("event_id"),
                        "top1_gloss": event.get("top1_gloss"),
                        "top1_probability": event.get("top1_probability"),
                        "recognition_v2_valid_count": event.get("recognition_v2_valid_count"),
                        "materialized_start_index": event.get("materialized_start_index"),
                        "materialized_end_index": event.get("materialized_end_index"),
                        "visual_evidence_directory": event.get("event_visual_evidence_directory"),
                    }
                    for event in matching_events
                ],
            }
        )

    originals = list((session_root / "continuous_visual/originals").glob("*_original.jpg"))
    result = {
        "milestone": "PHONE_REPEATED_RECOGNITION_INTEGRATION_01",
        "session": session_root.name,
        "observations": len(observations),
        "events": len(events),
        "attempts_begun": len(begin_attempts),
        "attempts_completed": len(completed_attempts),
        "rearm_completions": len(rearm_completions),
        "gap_resets": len(gap_resets),
        "continuous_original_frames": len(originals),
        "continuous_visual_coverage_complete": len(originals) == len(observations),
        "attempts": attempt_rows,
        "human_visual_audit_required_before_failure_attribution": True,
        "training_executed": False,
        "dev_accessed": False,
        "protected_test_accessed": False,
    }
    destination = OUTPUT / "phone_sessions" / session_root.name
    write_json(destination / "automatic_session_summary.json", result)
    write_json(
        destination / "source_hashes.json",
        {
            str(path.relative_to(session_root)): sha256(path)
            for path in (identity_path, observations_path, events_path, attempts_path)
        },
    )
    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("replay")
    summarize = subcommands.add_parser("summarize")
    summarize.add_argument("--session-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command in (None, "replay"):
        run_replay()
    elif args.command == "summarize":
        summarize_session(args.session_root.resolve())
    else:
        parser.error("unknown command")


if __name__ == "__main__":
    main()
