"""Read-only human-boundary analysis of the frozen phone A/B diagnostic stream.

No perception/model inference, fitting, threshold search or automatic sign labels.
The existing exact-capture reader and baseline replay are the only replay machinery.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from eval.runtime_diagnostics.phone_repeated_recognition_integration import (
    identity as event_identity,
)
from eval.runtime_diagnostics.phone_repeated_recognition_integration import (
    replay,
)
from eval.runtime_diagnostics.phone_s2_exact_parity_and_r2_decision import (
    load_capture,
    read_json,
    sha256,
)
from eval.runtime_diagnostics.transition_protocols import (
    LEGACY,
    TransitionProtocol,
    from_identity,
    from_integrity,
)
from pipeline.perception_vnext.recognition_window_materializer import (
    LogicalSignEvent,
    materialize_recognition_window,
)

BASELINE = "76d93cecd85bf9f76064d320aa4a5791b5f0704a"
MILESTONE = LEGACY.milestone
BLOCKS = LEGACY.blocks
GLOSSES = LEGACY.positive_sequences[0][1]
WAIT = "EVENT_EMITTED_WAIT_REARM"
LABEL_SCHEMA = LEGACY.label_schema
MODEL_SHA = "b6f8b52cece72f0b6f5b802a4ea583060d923e90a6b951059e7013114c8fc151"
NORM_SHA = "65d885f62eaca6f11a596302d304f63149795ddaf01e702f1e6a36dd7da5c005"
TFLITE_SHA = "7d26c896db1a00e7a41ff3e02b02033428cbd2ae4b5cbf3e4d279d45f529d3d7"


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def audit(session: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Fail closed on incomplete captures or broken source/tensor/visual linkage."""
    if (session / "failure.txt").exists():
        raise ValueError("CAPTURE_RUNTIME_FAILURE_REQUIRES_INCIDENT_REVIEW")
    capture = load_capture(session, require_full_session=False)
    identity = read_json(session / "identity.json")
    declared = read_json(session / "session_identity.json")
    protocol = from_identity(declared)
    if (
        declared.get("protected_baseline_sha") != BASELINE
        or declared.get("diagnostic_milestone") != protocol.milestone
        or not declared.get("transition_diagnostics_enabled")
    ):
        raise ValueError("WRONG_DIAGNOSTIC_COHORT_OR_BASELINE")
    package = identity["segmentation"]
    if (
        package.get("package_id") != "S2_R2_CANDIDATE"
        or package.get("source_checkpoint_sha256") != MODEL_SHA
        or package.get("source_normalization_sha256") != NORM_SHA
        or package.get("tflite_sha256") != TFLITE_SHA
    ):
        raise ValueError("WRONG_FROZEN_S2_PACKAGE")
    config = identity["decoder"]
    required = {
        "rearm_policy": "PRE_OR_POST_EXPERIMENTAL",
        "admission_policy": "PASS_THROUGH",
        "minimum_active_ms": 133.308,
        "pre_gap_reset_ms": 133.308,
        "post_confirm_ms": 266.616,
        "rearm_pre_stable_ms": 399.924,
        "maximum_continuous_observation_gap_ms": 533.232,
    }
    if any(config.get(key) != value for key, value in required.items()):
        raise ValueError("FROZEN_LIFECYCLE_CONFIG_CHANGED")
    rows, events = jsonl(session / "observations.jsonl"), jsonl(session / "events.jsonl")
    visual = read_json(session / "continuous_visual/evidence_summary.json")
    if (
        len(rows) != capture.count
        or not visual.get("finalized_after_capture_stop")
        or visual.get("verified_original_files") != capture.count
    ):
        raise ValueError("INCOMPLETE_OBSERVATION_OR_VISUAL_DRAIN")
    originals = session / "continuous_visual/originals"
    if len(list(originals.glob("frame_*_original.jpg"))) != capture.count:
        raise ValueError("VISUAL_COUNT_MISMATCH")
    for i, row in enumerate(rows):
        if (
            row["source_index"] != i
            or row.get("exact_record_index") != i
            or row["source_timestamp_ms"] != float(capture.raw.timestamp_ms[i])
            or row["argmax_state"] != int(capture.android_argmax[i])
            or row["visual_evidence_original"]
            != f"continuous_visual/originals/frame_{i + 1:06d}_original.jpg"
        ):
            raise ValueError(f"OBSERVATION_TENSOR_LINKAGE_MISMATCH:{i}")
        probabilities = [
            row[k] for k in ("pre_probability", "active_probability", "post_probability")
        ]
        if not np.array_equal(
            np.asarray(probabilities, np.float32), capture.android_probabilities[i]
        ):
            raise ValueError(f"PROBABILITY_LINKAGE_MISMATCH:{i}")
        image = originals / f"frame_{i + 1:06d}_original.jpg"
        evidence = read_json(originals / f"frame_{i + 1:06d}_evidence.json")
        if (
            evidence["ordinal"] != i + 1
            or abs(evidence["source_timestamp_ns"] / 1e6 - row["source_timestamp_ms"]) > 1e-6
            or evidence["original_sha256"] != sha256(image)
        ):
            raise ValueError(f"VISUAL_IDENTITY_MISMATCH:{i}")
    markers = jsonl(session / "attempts.jsonl")
    begins = [m for m in markers if m["action"] == "BEGIN"]
    ends = [m for m in markers if m["action"] == "COMPLETE"]
    if (
        tuple(m["expected_gloss"] for m in begins) != protocol.blocks
        or tuple(m["expected_gloss"] for m in ends) != protocol.blocks
        or [m["attempt_id"] for m in begins] != list(range(1, len(protocol.blocks) + 1))
        or [m["attempt_id"] for m in ends] != list(range(1, len(protocol.blocks) + 1))
    ):
        raise ValueError("FIXED_AB_NEGATIVE_MARKERS_INCOMPLETE")
    ranges = []
    for begin, end in zip(begins, ends, strict=True):
        indices = [
            r["source_index"]
            for r in rows
            if begin["marked_at_elapsed_realtime_ns"] / 1e6
            <= r["source_timestamp_ms"]
            <= end["marked_at_elapsed_realtime_ns"] / 1e6
        ]
        if not indices:
            raise ValueError("EMPTY_DIAGNOSTIC_BLOCK")
        ranges.append(
            {"block": begin["expected_gloss"], "start_index": indices[0], "end_index": indices[-1]}
        )
    control = replay(rows, allow_post_rearm=True, exact_android_commit_recovery=True)
    if [event_identity(e) for e in events] != [event_identity(e) for e in control["events"]]:
        raise ValueError("ANDROID_REFERENCE_EVENT_REPLAY_MISMATCH")
    if [r["source_index"] for r in rows if r["event_action"] == "REARM_COMPLETE"] != [
        r["observation_index"] for r in control["trace"] if r["action"] == "REARM_COMPLETE"
    ]:
        raise ValueError("ANDROID_REFERENCE_REARM_REPLAY_MISMATCH")
    for row, reference in zip(rows, control["trace"], strict=True):
        if (
            row["event_state_before"] != reference["state_before"]
            or row["event_state_after"] != reference["state_after"]
        ):
            raise ValueError(f"ANDROID_REFERENCE_LIFECYCLE_MISMATCH:{row['source_index']}")
        # Camera and elapsedRealtime must be compatible before mixing clocks for result timing.
        delay = row["decision_elapsed_realtime_ns"] / 1e6 - row["source_timestamp_ms"]
        if not 0 <= delay < 10_000:
            raise ValueError("SOURCE_RUNTIME_CLOCK_OR_BACKLOG_REQUIRES_REVIEW")
    for event in events:
        # Apply the existing reference materializer to the same bounded ring available at commit.
        stop = event["commit_index"]
        first = max(0, stop - 255)
        while capture.raw.timestamp_ms[stop] - capture.raw.timestamp_ms[first] > 30_000:
            first += 1
        logical = LogicalSignEvent(
            **{
                k: event[k] - first if k.endswith("_index") else event[k]
                for k in LogicalSignEvent.__dataclass_fields__
            }
        )
        try:
            window = materialize_recognition_window(
                capture.raw.timestamp_ms[first : stop + 1], logical
            )
        except ValueError as error:
            raise ValueError("EVENT_EXCEEDS_AVAILABLE_RING_BUFFER") from error
        indices = list(
            range(first + window.selected_start_index, first + window.selected_end_index + 1)
        )
        if indices != event["materialized_source_indices"]:
            raise ValueError("ANDROID_REFERENCE_MATERIALIZER_MISMATCH")
        selected = event["recognition_v2_source_indices"]
        if (
            not selected
            or selected != sorted(set(selected))
            or not set(selected) <= set(indices)
            or len(selected) != event["recognition_v2_mask_count"]
        ):
            raise ValueError("RECOGNITION_WINDOW_SOURCE_LINKAGE_MISMATCH")
    deliveries = jsonl(session / "ui_delivery.jsonl")
    if Counter(d["event_id"] for d in deliveries) != Counter(e["event_id"] for e in events):
        raise ValueError("DIAGNOSTIC_UI_DELIVERY_MISSING_OR_DUPLICATED")
    return (
        rows,
        events,
        {
            **protocol.metadata(),
            **(
                {
                    "declared_signer_proficiency": declared["declared_signer_proficiency"],
                    "comparison_baseline_sha": declared["comparison_baseline_sha"],
                }
                if protocol != LEGACY
                else {}
            ),
            "status": "CAPTURE_INTEGRITY_PASS",
            "count": capture.count,
            "blocks": ranges,
            "event_count": len(events),
            "baseline_replay_events_identical": True,
            "rearm_transitions_identical": True,
            "visual_coverage": "ALL_PROCESSED_OBSERVATIONS",
            "materializer_indices_identical": True,
            "source_runtime_clock_sanity_pass": True,
            "source_clock": (
                "ImageProxy monotonic ns, serialized as ms; runtime/UI elapsedRealtime ns"
            ),
            "session_identity_sha256": sha256(session / "session_identity.json"),
            "exact_manifest_sha256": sha256(session / "s2_exact_parity/manifest.json"),
            "observations_sha256": sha256(session / "observations.jsonl"),
            "events_sha256": sha256(session / "events.jsonl"),
            "attempt_markers_sha256": sha256(session / "attempts.jsonl"),
            "ui_delivery_sha256": sha256(session / "ui_delivery.jsonl"),
            "minimum_active_ms": config["minimum_active_ms"],
            "maximum_observation_gap_ms": config["maximum_continuous_observation_gap_ms"],
        },
    )


def prepare(session: Path) -> Path:
    rows, _, integrity = audit(session)
    protocol = from_integrity(integrity)
    output = session / "transition_review"
    output.mkdir(exist_ok=True)
    public = {
        "schema": protocol.label_schema,
        **protocol.metadata(),
        "session_id": session.name,
        "evidence_sha256": integrity["observations_sha256"],
        "blocks": integrity["blocks"],
        "frames": [
            {
                "source_index": r["source_index"],
                "timestamp_ms": r["source_timestamp_ms"],
                "image": "../" + r["visual_evidence_original"],
            }
            for r in rows
        ],
    }
    write(output / "review_manifest.json", public)
    shutil.copyfile(Path(__file__).with_suffix(".html"), output / "index.html")
    write(output / "integrity.json", integrity)
    template = {
        "schema": protocol.label_schema,
        **protocol.metadata(),
        "session_id": session.name,
        "evidence_sha256": integrity["observations_sha256"],
        "reviewer": "",
        "blinded_to_predictions": True,
        "signs": [
            {
                "condition": b,
                "ordinal": i,
                "gloss": gloss,
                "start_index": None,
                "end_index": None,
                "judgment": "UNCERTAIN",
                "note": "",
            }
            for b, glosses in protocol.positive_sequences
            for i, gloss in enumerate(glosses, 1)
        ],
        "negative_intervals": [
            {
                "block": b,
                "start_index": None,
                "end_index": None,
                "judgment": "UNCERTAIN",
                "note": "",
            }
            for b in protocol.negative_blocks
        ],
        "reviewed_blocks": [],
    }
    # Never replace a reviewer's existing labels.
    if not (output / "human_boundaries.template.json").exists():
        write(output / "human_boundaries.template.json", template)
    return output


def validate_labels(
    labels: dict[str, Any], integrity: dict[str, Any], count: int, session_id: str
) -> None:
    protocol = from_integrity(integrity)
    if (
        labels.get("schema") != protocol.label_schema
        or labels.get("session_id") != session_id
        or labels.get("evidence_sha256") != integrity["observations_sha256"]
    ):
        raise ValueError("HUMAN_LABEL_EVIDENCE_IDENTITY_MISMATCH")
    if any(labels.get(key) != value for key, value in protocol.metadata().items()):
        raise ValueError("HUMAN_LABEL_PROTOCOL_MISMATCH")
    if not labels.get("reviewer", "").strip() or set(labels.get("reviewed_blocks", [])) != set(
        protocol.blocks
    ):
        raise ValueError("HUMAN_REVIEW_INCOMPLETE")
    expected = [
        (b, i, g) for b, glosses in protocol.positive_sequences for i, g in enumerate(glosses, 1)
    ]
    signs = labels.get("signs", [])
    if [(s["condition"], s["ordinal"], s["gloss"]) for s in signs] != expected:
        raise ValueError("PHYSICAL_SIGN_ORDER_CHANGED")
    ranges = {r["block"]: r for r in integrity["blocks"]}
    previous_end: dict[str, int] = {}
    for entry in signs + labels.get("negative_intervals", []):
        judgment = entry.get("judgment")
        allowed = (
            {"GENUINE_SIGN", "UNCERTAIN", "NOT_PERFORMED"}
            if "gloss" in entry
            else {"CONFIRMED_NON_SIGN", "SIGN_PREPARATION_OR_LEXICAL", "UNCERTAIN"}
        )
        if judgment not in allowed:
            raise ValueError("INVALID_HUMAN_JUDGMENT")
        start, end = entry.get("start_index"), entry.get("end_index")
        if start is None or end is None:
            if judgment in {"GENUINE_SIGN", "CONFIRMED_NON_SIGN"}:
                raise ValueError("CONFIDENT_INTERVAL_NEEDS_BOUNDARIES")
            continue
        block = entry.get("condition", entry.get("block"))
        if block not in ranges or not (
            type(start) is int
            and type(end) is int
            and 0 <= start <= end < count
            and ranges[block]["start_index"] <= start <= end <= ranges[block]["end_index"]
        ):
            raise ValueError("INVALID_HUMAN_INTERVAL")
        if "gloss" in entry:
            if start <= previous_end.get(block, -1):
                raise ValueError("OVERLAPPING_OR_REVERSED_PHYSICAL_SIGNS")
            previous_end[block] = end
    negatives = labels.get("negative_intervals", [])
    if {n["block"] for n in negatives} != set(protocol.negative_blocks):
        raise ValueError("NEGATIVE_REVIEW_CATEGORIES_MISSING")
    for i, a in enumerate(negatives):
        if a.get("start_index") is None:
            continue
        for b in negatives[i + 1 :]:
            if b.get("start_index") is not None and max(a["start_index"], b["start_index"]) <= min(
                a["end_index"], b["end_index"]
            ):
                raise ValueError("OVERLAPPING_NEGATIVE_INTERVALS")

    if protocol != LEGACY:
        if [n["block"] for n in negatives] != list(protocol.negative_blocks):
            raise ValueError("COMPACT_NEGATIVE_ORDER_OR_DUPLICATION")
        if labels.get("blinded_to_predictions") is not True:
            raise ValueError("COMPACT_REVIEW_MUST_DECLARE_BLINDING")
        for interval in negatives:
            if interval["judgment"] != "CONFIRMED_NON_SIGN":
                continue
            for sign in signs:
                if sign["judgment"] == "GENUINE_SIGN" and max(
                    interval["start_index"], sign["start_index"]
                ) <= min(interval["end_index"], sign["end_index"]):
                    raise ValueError("NEGATIVE_INTERVAL_OVERLAPS_GENUINE_SIGN")
            if interval["block"] == "D_SIGN_THEN_HOLD":
                sign = next(s for s in signs if s["condition"] == "D_SIGN_THEN_HOLD")
                if (
                    sign["judgment"] == "GENUINE_SIGN"
                    and interval["start_index"] <= sign["end_index"]
                ):
                    raise ValueError("HOLD_MUST_FOLLOW_COMPLETED_PHYSICAL_SIGN")


def _overlap(event: dict[str, Any], sign: dict[str, Any]) -> bool:
    return bool(
        max(event["logical_active_start_index"], sign["start_index"])
        <= min(event["logical_active_end_index"], sign["end_index"])
    )


def _time(rows: list[dict[str, Any]], index: int | None) -> float | None:
    return None if index is None else float(rows[index]["source_timestamp_ms"])


def _delta(end: float | None, start: float | None) -> float | None:
    return None if end is None or start is None else end - start


def cadence(
    rows: list[dict[str, Any]], start: int, end: int, maximum_gap_ms: float
) -> dict[str, Any]:
    spacing = np.diff([r["source_timestamp_ms"] for r in rows[start : end + 1]])
    return {
        "observations": end - start + 1,
        "spacing_p50_ms": float(np.percentile(spacing, 50)) if spacing.size else None,
        "spacing_p95_ms": float(np.percentile(spacing, 95)) if spacing.size else None,
        "gaps_over_continuity_boundary": int(np.count_nonzero(spacing > maximum_gap_ms)),
    }


def _qualifying_active(
    rows: list[dict[str, Any]], start: int, end: int, minimum_ms: float, maximum_gap_ms: float
) -> int | None:
    """Conservative useful ACTIVE evidence probe, not a new online decision rule.

    The actual candidate's span is reported separately. For blocked onsets, require a
    continuous argmax-ACTIVE run reaching the unchanged minimum span; do not bridge gaps.
    """
    beginning: float | None = None
    previous: float | None = None
    for row in rows[start : end + 1]:
        t = row["source_timestamp_ms"]
        if row["argmax_state"] != 1:
            beginning = None
        else:
            if beginning is None or (previous is not None and t - previous > maximum_gap_ms):
                beginning = t
            if t - beginning >= minimum_ms:
                return int(row["source_index"])
        previous = t
    return None


def evaluate(
    rows: list[dict[str, Any]],
    events: list[dict[str, Any]],
    labels: dict[str, Any],
    deliveries: list[dict[str, Any]],
    minimum_ms: float,
    maximum_gap_ms: float,
    protocol: TransitionProtocol = LEGACY,
) -> dict[str, Any]:
    """Retrospective diagnostics anchored only to human-reviewed source indices."""
    genuine = [s for s in labels["signs"] if s["judgment"] == "GENUINE_SIGN"]
    associations = {e["event_id"]: [s for s in genuine if _overlap(e, s)] for e in events}
    ui = {d["event_id"]: d for d in deliveries}
    attempts = []
    for sign in labels["signs"]:
        if sign["judgment"] != "GENUINE_SIGN":
            attempts.append({**sign, "classification": "UNCERTAIN_OR_NOT_PERFORMED"})
            continue
        start, end = sign["start_index"], sign["end_index"]
        interval = rows[start : end + 1]
        matches = [e for e in events if _overlap(e, sign)]
        opened = [r for r in interval if r["event_action"] == "START_ACTIVE_CANDIDATE"]
        active = [r for r in interval if r["argmax_state"] == 1]
        qualifying = _qualifying_active(rows, start, end, minimum_ms, maximum_gap_ms)
        accepted_qualifying = next(
            (
                r["source_index"]
                for r in interval
                if r["argmax_state"] == 1
                and r.get("candidate_active_span_ms", -1) is not None
                and r.get("candidate_active_span_ms", -1) >= minimum_ms
                and r.get("candidate_open_index") is not None
                and r["candidate_open_index"] >= start
            ),
            None,
        )
        shared = [e["event_id"] for e in matches if len(associations[e["event_id"]]) > 1]
        blocked = [r for r in active if r["event_state_before"] == WAIT]
        flags = []
        if shared:
            flags.append("B_NO_INTERSIGN_S2_BOUNDARY")
        prior = next(
            (
                s
                for s in genuine
                if s["condition"] == sign["condition"] and s["ordinal"] == sign["ordinal"] - 1
            ),
            None,
        )
        continuing_previous = prior is not None and any(
            r.get("candidate_open_index") is not None
            and r["candidate_open_index"] <= prior["end_index"]
            and r["event_state_before"] in {"ACTIVE_CANDIDATE", "PRE_GAP", "POST_CANDIDATE"}
            for r in active
        )
        if continuing_previous and "B_NO_INTERSIGN_S2_BOUNDARY" not in flags:
            flags.append("B_NO_INTERSIGN_S2_BOUNDARY")
        if (
            blocked
            and qualifying is not None
            and any(r["source_index"] == qualifying for r in blocked)
        ):
            flags.append("A_REARM_LIFECYCLE_BLOCK")
        if (
            not matches
            and not opened
            and not active
            and any(r["event_state_before"] == "IDLE" for r in interval)
        ):
            flags.append("C_S2_ACTIVE_REACQUISITION_FAILURE")
        elif not matches and opened and accepted_qualifying is None:
            flags.append("C_S2_ACTIVE_REACQUISITION_FAILURE")
        distinct = [
            e
            for e in matches
            if e["event_id"] not in shared and start <= e["logical_active_start_index"] <= end
        ]
        if len(distinct) == 1 and accepted_qualifying is not None:
            flags.append("D_EVENT_DELIVERY_OK_DOWNSTREAM")
        if len(matches) > 1:
            flags.append("MULTIPLE_EVENT_EPISODES")
        if matches and not distinct and not shared:
            flags.append("EARLY_OR_WRONG_EPISODE")
        if not matches and accepted_qualifying is not None:
            flags.append("E_OPENED_EPISODE_NO_COMPLETED_EVENT")
        if cadence(rows, start, end, maximum_gap_ms)["gaps_over_continuity_boundary"]:
            flags.append("OBSERVATION_CADENCE_CONFOUND")
        if not flags:
            flags.append("AMBIGUOUS_INSUFFICIENT_BOUNDARY_OR_EPISODE_EVIDENCE")
        event_details = []
        for e in matches:
            selected = e["materialized_source_indices"]
            selected_v2 = e["recognition_v2_source_indices"]
            event_details.append(
                {
                    **e,
                    "shared_between_physical_signs": e["event_id"] in shared,
                    "human_sign_observation_containment": sum(start <= i <= end for i in selected)
                    / len(interval),
                    "recognizer_selected_sign_containment": sum(
                        start <= i <= end for i in selected_v2
                    )
                    / len(interval),
                    "ui_delivery": ui.get(e["event_id"]),
                }
            )
        first = distinct[0] if len(distinct) == 1 else None
        ui_ns = (
            ui.get(first["event_id"], {}).get("ui_delivery_elapsed_realtime_ns") if first else None
        )
        attempts.append(
            {
                **sign,
                "classification": flags,
                "lifecycle_before_start_observation": rows[start]["event_state_before"],
                "active_observations": len(active),
                "human_sign_observations": len(interval),
                "first_argmax_active_index": active[0]["source_index"] if active else None,
                "first_continuous_qualifying_active_index": qualifying,
                "first_accepted_candidate_minimum_span_index": accepted_qualifying,
                "opened_indices": [r["source_index"] for r in opened],
                "blocked_active_indices": [r["source_index"] for r in blocked],
                "event_count": len(matches),
                "events": event_details,
                "timing_ms": {
                    "physical_start_to_first_qualifying_active": _delta(
                        _time(rows, qualifying), _time(rows, start)
                    ),
                    "physical_start_to_event_open": _delta(
                        _time(rows, opened[0]["source_index"] if opened else None),
                        _time(rows, start),
                    ),
                    "physical_end_to_completion_source": _delta(
                        first["commit_ms"] if first else None, _time(rows, end)
                    ),
                    "physical_start_to_recognizer_result": _delta(
                        first["recognizer_complete_elapsed_realtime_ns"] / 1e6 if first else None,
                        _time(rows, start),
                    ),
                    "physical_start_to_debug_ui_delivery": _delta(
                        ui_ns / 1e6 if ui_ns else None, _time(rows, start)
                    ),
                },
            }
        )
    transitions = []
    for condition, _ in protocol.positive_sequences:
        ordered = [s for s in labels["signs"] if s["condition"] == condition]
        for prior, following in zip(ordered, ordered[1:], strict=False):
            if any(s["judgment"] != "GENUINE_SIGN" for s in (prior, following)):
                transitions.append(
                    {
                        "condition": condition,
                        "from": prior["ordinal"],
                        "to": following["ordinal"],
                        "status": "UNCERTAIN",
                    }
                )
                continue
            prior_events = [e for e in events if _overlap(e, prior)]
            # Never choose an arbitrary event when one physical sign has several candidates.
            previous = prior_events[0] if len(prior_events) == 1 else None
            stop = following["end_index"]
            rearm = next(
                (
                    r
                    for r in rows[
                        (previous["commit_index"] + 1 if previous else stop + 1) : stop + 1
                    ]
                    if r["event_action"] == "REARM_COMPLETE"
                ),
                None,
            )
            between = rows[prior["end_index"] + 1 : following["start_index"]]
            next_span = rows[following["start_index"] : stop + 1]
            resets = [
                r for r in next_span if r.get("rearm_reason") == "ACTIVE_INTERRUPTED_RECOVERY"
            ]
            transitions.append(
                {
                    "condition": condition,
                    "from": prior["ordinal"],
                    "to": following["ordinal"],
                    "physical_end_ms": _time(rows, prior["end_index"]),
                    "physical_next_start_ms": _time(rows, following["start_index"]),
                    "previous_event_id": previous["event_id"] if previous else None,
                    "previous_terminal_post_ms": previous["terminal_post_ms"] if previous else None,
                    "previous_completion_commit_source_ms": (
                        previous["commit_ms"] if previous else None
                    ),
                    "previous_decision_elapsed_realtime_ns": (
                        rows[previous["commit_index"]].get("event_decision_elapsed_realtime_ns")
                        if previous
                        else None
                    ),
                    "state_after_previous_commit": (
                        rows[previous["commit_index"]]["event_state_after"] if previous else None
                    ),
                    "state_before_next_start": rows[following["start_index"]]["event_state_before"],
                    "intersign_argmax_counts": dict(
                        Counter(str(r["argmax_state"]) for r in between)
                    ),
                    "intersign_probability_rows": [
                        {
                            k: r[k]
                            for k in (
                                "source_index",
                                "source_timestamp_ms",
                                "pre_probability",
                                "active_probability",
                                "post_probability",
                                "event_state_after",
                            )
                        }
                        for r in between
                    ],
                    "boundary_episode_trace": [
                        {
                            k: r.get(k)
                            for k in (
                                "source_index",
                                "source_timestamp_ms",
                                "argmax_state",
                                "event_state_before",
                                "event_state_after",
                                "event_action",
                                "candidate_open_index",
                                "candidate_active_span_ms",
                                "rearm_timer_start_ms",
                                "rearm_elapsed_ms",
                                "rearm_reason",
                                "admission_decision",
                            )
                        }
                        for r in rows[prior["end_index"] : stop + 1]
                    ],
                    "rearm_before_next_sign": rearm is not None
                    and rearm["source_index"] < following["start_index"],
                    "rearm_index": rearm["source_index"] if rearm else None,
                    "active_recovery_interruptions": [
                        {
                            k: r.get(k)
                            for k in (
                                "source_index",
                                "event_action",
                                "rearm_timer_start_ms",
                                "rearm_elapsed_ms",
                                "rearm_reason",
                            )
                        }
                        for r in resets
                    ],
                    "timing_ms": {
                        "physical_end_to_completion_commit": _delta(
                            previous["commit_ms"] if previous else None,
                            _time(rows, prior["end_index"]),
                        ),
                        "completion_commit_to_rearm": _delta(
                            _time(rows, rearm["source_index"] if rearm else None),
                            previous["commit_ms"] if previous else None,
                        ),
                        "next_start_to_rearm_signed": _delta(
                            _time(rows, rearm["source_index"] if rearm else None),
                            _time(rows, following["start_index"]),
                        ),
                    },
                }
            )
    negatives = []
    for interval in labels["negative_intervals"]:
        if interval["judgment"] != "CONFIRMED_NON_SIGN":
            negatives.append({**interval, "status": "EXCLUDED_FROM_NEGATIVE_METRICS"})
            continue
        start, end = interval["start_index"], interval["end_index"]
        exclusive = [
            e
            for e in events
            if start <= e["logical_active_start_index"] <= e["logical_active_end_index"] <= end
        ]
        negatives.append(
            {
                **interval,
                "status": "HUMAN_CONFIRMED_BOUNDED_NEGATIVE",
                "observation_count": end - start + 1,
                "active_observations": sum(r["argmax_state"] == 1 for r in rows[start : end + 1]),
                "fully_contained_event_ids": [e["event_id"] for e in exclusive],
                "overlapping_event_ids_for_manual_attribution": [
                    e["event_id"] for e in events if _overlap(e, interval)
                ],
                "commits_in_interval_not_automatically_false": [
                    e["event_id"] for e in events if start <= e["commit_index"] <= end
                ],
            }
        )
    for transition in transitions:
        next_attempt = next(
            a
            for a in attempts
            if a["condition"] == transition["condition"] and a["ordinal"] == transition["to"]
        )
        transition["next_sign_classification"] = next_attempt["classification"]
        transition["next_sign_event_details"] = next_attempt.get("events", [])
        transition["timing_ms"] = {
            **transition.get("timing_ms", {}),
            **{
                k: v
                for k, v in next_attempt.get("timing_ms", {}).items()
                if k.startswith("physical_start_")
            },
        }
    return {
        **(
            {"compact_outcomes": compact_outcomes(attempts, events), **protocol.metadata()}
            if protocol != LEGACY
            else {}
        ),
        "attempts": attempts,
        "transitions": transitions,
        "reviewed_negatives": negatives,
        "block_cadence": {
            block: cadence(
                rows,
                min(s["start_index"] for s in genuine if s["condition"] == block),
                max(s["end_index"] for s in genuine if s["condition"] == block),
                maximum_gap_ms,
            )
            for block, _ in protocol.positive_sequences
            if any(s["condition"] == block for s in genuine)
        },
        "decision": "EVIDENCE_FOR_PROJECT_LEAD_REVIEW_ONLY",
        "behavior_change_authorized": False,
        "timing_caveat": (
            "Human boundaries have observation resolution; missing metrics stay null. "
            "These are response/transition intervals, not inference latency."
        ),
        "ui_caveat": (
            "UI timings belong to the diagnostic Activity; "
            "normal app sentence delivery is not measured by this capture."
        ),
    }


def compact_outcomes(
    attempts: list[dict[str, Any]], events: list[dict[str, Any]]
) -> dict[str, Any]:
    """Event identity and lexical output stay separate from normal-app sentence delivery."""
    outcomes = []
    for attempt in attempts:
        matches = attempt.get("events", [])
        if attempt["judgment"] != "GENUINE_SIGN":
            outcome = "UNCERTAIN_OR_NOT_PERFORMED"
        elif any(e["shared_between_physical_signs"] for e in matches):
            outcome = "MERGED_EVENT"
        elif not matches:
            outcome = "NO_COMPLETED_EVENT"
        elif len(matches) > 1:
            outcome = "MULTIPLE_EVENTS_REVIEW_DUPLICATION_OR_OVERSEGMENTATION"
        elif "EARLY_OR_WRONG_EPISODE" in attempt.get("classification", []):
            outcome = "OVERLAPPING_EARLY_EPISODE_REVIEW_REQUIRED"
        else:
            outcome = (
                "DISTINCT_EVENT_EXPECTED_GLOSS"
                if matches[0]["top1_gloss"] == attempt["gloss"]
                else "DISTINCT_EVENT_CLASSIFICATION_MISMATCH"
            )
        outcomes.append(
            {
                "condition": attempt["condition"],
                "ordinal": attempt["ordinal"],
                "outcome": outcome,
                "event_ids": [e["event_id"] for e in matches],
            }
        )
    repeated = [o for o in outcomes if o["condition"] == "C_REPEAT_HANDS_UP"]
    ids = [o["event_ids"][0] for o in repeated if len(o["event_ids"]) == 1]
    return {
        "physical_signs": outcomes,
        "adjacent_repeat_has_two_distinct_events": len(ids) == 2 and len(set(ids)) == 2,
        "repeat_event_glosses": [e["top1_gloss"] for e in events if e["event_id"] in ids],
        "normal_app_sentence_delivery": "NOT_MEASURED_DIAGNOSTIC_ACTIVITY",
        "accuracy_claim": "NONE_SINGLE_DESIGN_COHORT",
    }


def markdown_result(result: dict[str, Any]) -> str:
    lines = [
        f"# {result.get('milestone', MILESTONE)} — captured evidence",
        "",
        result["decision"],
        "",
        "Diagnostic evidence only. No behavioral fix is authorized by this evaluator.",
        "",
        "| Condition/sign | Intended | Classification | ACTIVE observations | Associated events |",
        "|---|---|---|---|---|",
    ]
    for a in result["attempts"]:
        flags = (
            a["classification"]
            if isinstance(a["classification"], str)
            else ", ".join(a["classification"])
        )
        lines.append(
            f"| {a['condition']}/{a['ordinal']} | {a['gloss']} | {flags} | "
            f"{a.get('active_observations', 'unknown')} | {a.get('event_count', 'unknown')} |"
        )
    lines += [
        "",
        "Shared events can appear against both physical signs; this is not two delivered events.",
        "",
        "## Transition response intervals (milliseconds)",
        "",
        "| Transition | End→commit | Commit→rearm | Next start→rearm (signed) | "
        "Next start→open | Next start→debug UI |",
        "|---|---|---|---|---|---|",
    ]
    for t in result["transitions"]:
        values = t.get("timing_ms", {})
        cells = [
            values.get(k)
            for k in (
                "physical_end_to_completion_commit",
                "completion_commit_to_rearm",
                "next_start_to_rearm_signed",
                "physical_start_to_event_open",
                "physical_start_to_debug_ui_delivery",
            )
        ]
        lines.append(
            f"| {t['condition']} {t['from']}→{t['to']} | "
            + " | ".join("unknown" if v is None else f"{v:.3f}" for v in cells)
            + " |"
        )
    if "compact_outcomes" in result:
        lines += [
            "",
            "## Compact event/lexical outcomes",
            "",
            "| Block/sign | Outcome | Event IDs |",
            "|---|---|---|",
        ]
        for item in result["compact_outcomes"]["physical_signs"]:
            lines.append(
                f"| {item['condition']}/{item['ordinal']} | {item['outcome']} | "
                f"{item['event_ids']} |"
            )
        lines += [
            "",
            "Normal-app sentence delivery is NOT MEASURED by this diagnostic Activity.",
            "This single design cohort is not an accuracy claim.",
        ]
    lines += [
        "",
        result["timing_caveat"],
        "",
        result["ui_caveat"],
        "",
        "Detailed source-linked probabilities, recovery resets, windows, recognition results "
        "and reviewed negatives are in result.json.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "analyze"))
    parser.add_argument("--session", required=True, type=Path)
    parser.add_argument("--labels", type=Path)
    args = parser.parse_args()
    session = args.session.resolve()
    if args.command == "prepare":
        print(
            json.dumps(
                {"status": "READY_FOR_BLINDED_HUMAN_REVIEW", "review": str(prepare(session))},
                indent=2,
            )
        )
        return 0
    labels_path = args.labels or session / "transition_review/human_boundaries.json"
    rows, events, integrity = audit(session)
    labels = read_json(labels_path)
    validate_labels(labels, integrity, len(rows), session.name)
    result = evaluate(
        rows,
        events,
        labels,
        jsonl(session / "ui_delivery.jsonl"),
        integrity["minimum_active_ms"],
        integrity["maximum_observation_gap_ms"],
        protocol=from_integrity(integrity),
    )
    output = session / "transition_analysis"
    write(
        output / "result.json",
        {
            "milestone": from_integrity(integrity).milestone,
            "baseline_sha": BASELINE,
            "human_labels_sha256": sha256(labels_path),
            "integrity": integrity,
            **result,
        },
    )
    (output / "RESULT.md").write_text(
        markdown_result({**result, "milestone": from_integrity(integrity).milestone}),
        encoding="utf-8",
    )
    print(
        json.dumps({"status": result["decision"], "report": str(output / "result.json")}, indent=2)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
