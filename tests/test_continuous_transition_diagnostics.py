from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from eval.runtime_diagnostics import continuous_transition_diagnostics as diag
from eval.runtime_diagnostics.phone_repeated_recognition_integration import replay


def stream(states: list[int], times: list[float] | None = None) -> tuple[list[dict], list[dict]]:
    rows = [
        {
            "source_index": i,
            "source_timestamp_ms": (times[i] if times else i * 200.0),
            "argmax_state": state,
            "pre_probability": 0.98 if state == 0 else 0.01,
            "active_probability": 0.98 if state == 1 else 0.01,
            "post_probability": 0.98 if state == 2 else 0.01,
            "rearm_reason": None,
            "rearm_timer_start_ms": None,
            "rearm_elapsed_ms": None,
        }
        for i, state in enumerate(states)
    ]
    result = replay(rows, allow_post_rearm=True, exact_android_commit_recovery=True)
    candidate = None
    last_active = None
    for row, trace in zip(rows, result["trace"], strict=True):
        row.update(
            event_action=trace["action"],
            event_state_before=trace["state_before"],
            event_state_after=trace["state_after"],
        )
        if trace["action"] == "START_ACTIVE_CANDIDATE":
            candidate = row["source_index"]
        if row["argmax_state"] == 1 and trace["state_after"] == "ACTIVE_CANDIDATE":
            last_active = row["source_timestamp_ms"]
        row.update(
            candidate_open_index=candidate,
            candidate_active_span_ms=(
                last_active - rows[candidate]["source_timestamp_ms"]
                if candidate is not None
                else None
            ),
        )
        if trace["state_before"] == diag.WAIT and row["argmax_state"] == 1:
            row["rearm_reason"] = "ACTIVE_INTERRUPTED_RECOVERY"
        if trace["state_after"] in ("IDLE", diag.WAIT):
            candidate = None
    events = []
    for e in result["events"]:
        event = {
            k: e[k]
            for k in (
                "event_id",
                "logical_active_start_index",
                "logical_active_end_index",
                "logical_active_start_ms",
                "logical_active_end_ms",
            )
        }
        event.update(
            terminal_post_index=e["first_post_index"],
            terminal_post_ms=e["first_post_ms"],
            commit_index=e["emitted_at_index"],
            commit_ms=e["emitted_at_ms"],
            recognizer_complete_elapsed_realtime_ns=int((e["emitted_at_ms"] + 20) * 1e6),
            materialized_source_indices=list(
                range(e["logical_active_start_index"], e["emitted_at_index"] + 1)
            ),
            recognition_v2_source_indices=list(
                range(e["logical_active_start_index"], e["emitted_at_index"] + 1)
            ),
        )
        events.append(event)
    return rows, events


def sign(start: int, end: int, ordinal: int = 1, condition: str = diag.BLOCKS[0]) -> dict:
    return {
        "condition": condition,
        "ordinal": ordinal,
        "gloss": diag.GLOSSES[ordinal - 1],
        "judgment": "GENUINE_SIGN",
        "start_index": start,
        "end_index": end,
    }


def analyze(
    rows: list[dict], events: list[dict], signs: list[dict], negatives: list[dict] | None = None
) -> dict:
    return diag.evaluate(
        rows, events, {"signs": signs, "negative_intervals": negatives or []}, [], 133.308, 533.232
    )


def test_readiness_control_default_is_not_rewritten() -> None:
    rows, _ = stream([0, 1, 1, 2, 2, 2, 2, 2, 2])
    historical = replay(rows, allow_post_rearm=True)
    exact = replay(rows, allow_post_rearm=True, exact_android_commit_recovery=True)

    def indices(r: dict) -> list[int]:
        return [t["observation_index"] for t in r["trace"] if t["action"] == "REARM_COMPLETE"]

    assert indices(exact) == [7]
    assert indices(historical) == [8]
    assert historical["events"] == exact["events"]


def test_lifecycle_blocked_next_sign_is_not_a_recognizer_error() -> None:
    rows, events = stream([0, 1, 1, 2, 2, 2, 1, 1, 1, 2, 2, 2])
    result = analyze(rows, events, [sign(1, 2), sign(6, 8, 2)])
    assert result["attempts"][1]["classification"] == ["A_REARM_LIFECYCLE_BLOCK"]
    assert result["transitions"][0]["state_before_next_start"] == diag.WAIT
    assert len(result["transitions"][0]["active_recovery_interruptions"]) == 3
    assert result["transitions"][0]["rearm_before_next_sign"] is False


def test_merged_physical_signs_are_reported_not_counted_twice() -> None:
    rows, events = stream([0, 1, 1, 1, 1, 1, 2, 2, 2])
    result = analyze(rows, events, [sign(1, 2), sign(4, 5, 2)])
    assert all("B_NO_INTERSIGN_S2_BOUNDARY" in a["classification"] for a in result["attempts"])
    assert len(events) == 1


def test_unfinished_merged_candidate_is_visible_without_final_event() -> None:
    rows, events = stream([0, 1, 1, 1, 1, 1])
    result = analyze(rows, events, [sign(1, 2), sign(4, 5, 2)])
    assert "B_NO_INTERSIGN_S2_BOUNDARY" in result["attempts"][1]["classification"]
    assert events == []


def test_large_gaps_remain_a_separate_runtime_confound() -> None:
    rows, events = stream([0, 1, 1, 2, 2, 2], [0, 200, 1200, 1400, 1600, 1800])
    assert (
        "OBSERVATION_CADENCE_CONFOUND"
        in analyze(rows, events, [sign(1, 2)])["attempts"][0]["classification"]
    )


def test_ready_but_no_active_is_acquisition_failure() -> None:
    rows, events = stream([2] * 8)
    result = analyze(rows, events, [sign(2, 5)])
    assert result["attempts"][0]["classification"] == ["C_S2_ACTIVE_REACQUISITION_FAILURE"]


def test_single_active_too_short_is_distinct_from_completion_failure() -> None:
    rows, events = stream([0, 1, 2, 2, 2])
    assert analyze(rows, events, [sign(1, 2)])["attempts"][0]["classification"] == [
        "C_S2_ACTIVE_REACQUISITION_FAILURE"
    ]


def test_distinct_delivery_has_separate_window_and_word_evidence() -> None:
    rows, events = stream([0, 1, 1, 2, 2, 2])
    events[0]["top1_gloss"] = "WRONG_WORD"
    result = analyze(rows, events, [sign(1, 2)])
    assert result["attempts"][0]["classification"] == ["D_EVENT_DELIVERY_OK_DOWNSTREAM"]
    assert result["attempts"][0]["events"][0]["top1_gloss"] == "WRONG_WORD"
    assert result["attempts"][0]["timing_ms"]["physical_end_to_completion_source"] == 600


def test_gap_is_not_qualifying_active_or_recovery_evidence() -> None:
    rows, _ = stream([1, 1], [0, 1000])
    assert diag._qualifying_active(rows, 0, 1, 133.308, 533.232) is None
    rows, _ = stream([0, 1, 1, 2, 2, 2, 2, 2, 2], [0, 200, 400, 600, 800, 1000, 2000, 2200, 2400])
    assert rows[6]["event_state_after"] == diag.WAIT
    assert rows[8]["event_action"] == "REARM_COMPLETE"


def test_uncertain_negatives_are_not_false_event_labels() -> None:
    rows, events = stream([0, 1, 1, 2, 2, 2])
    negatives = [
        {"judgment": "UNCERTAIN", "start_index": 1, "end_index": 5},
        {"judgment": "CONFIRMED_NON_SIGN", "start_index": 1, "end_index": 2},
    ]
    result = analyze(rows, events, [], negatives)["reviewed_negatives"]
    assert result[0]["status"] == "EXCLUDED_FROM_NEGATIVE_METRICS"
    assert result[1]["fully_contained_event_ids"] == [1]
    assert result[1]["commits_in_interval_not_automatically_false"] == []


def labels_and_integrity() -> tuple[dict, dict]:
    integrity = {
        "observations_sha256": "evidence",
        "blocks": [
            {"block": b, "start_index": i * 20, "end_index": i * 20 + 19}
            for i, b in enumerate(diag.BLOCKS)
        ],
    }
    labels = {
        "schema": diag.LABEL_SCHEMA,
        "session_id": "session",
        "evidence_sha256": "evidence",
        "reviewer": "human",
        "reviewed_blocks": list(diag.BLOCKS),
        "signs": [
            sign(j * 3 + i * 20, j * 3 + 1 + i * 20, j + 1, b)
            for i, b in enumerate(diag.BLOCKS[:2])
            for j in range(4)
        ],
        "negative_intervals": [
            {"block": b, "start_index": None, "end_index": None, "judgment": "UNCERTAIN"}
            for b in diag.BLOCKS[2:]
        ],
    }
    return labels, integrity


def test_review_accepts_explicit_uncertainty() -> None:
    labels, integrity = labels_and_integrity()
    diag.validate_labels(labels, integrity, 140, "session")


def test_frozen_s2_r2_package_against_existing_host_fixture() -> None:
    """Deployment regression only: same old 669-observation fixture, no new evaluation data."""
    import tensorflow as tf

    root = Path(__file__).resolve().parents[1]
    package = root / "android/app/src/main/assets/phone_causal_recognition_01/s2_r2_candidate"
    fixtures = root / "android/app/src/debug/assets/phone_causal_recognition_01/s2_r2_candidate"
    contract = diag.read_json(package / "contract.json")
    assert contract["source_checkpoint_sha256"] == diag.MODEL_SHA
    assert contract["source_normalization_sha256"] == diag.NORM_SHA
    assert diag.sha256(package / "s2_r2_fp32.tflite") == diag.TFLITE_SHA
    assert diag.sha256(package / "normalization.json") == contract["normalization_asset_sha256"]
    normalization = diag.read_json(package / "normalization.json")
    arrays = {}
    for name in ("raw_features", "features", "probabilities"):
        path = fixtures / contract["fixture"][f"{name}_asset"]
        assert diag.sha256(path) == contract["fixture"][f"{name}_sha256"]
        arrays[name] = np.fromfile(path, dtype="<f4").reshape(
            -1, 3 if name == "probabilities" else 378
        )
    normalized = (
        arrays["raw_features"] - np.asarray(normalization["mean"], np.float32)
    ) / np.asarray(normalization["std"], np.float32)
    assert np.array_equal(normalized, arrays["features"])
    runner = tf.lite.Interpreter(model_path=str(package / "s2_r2_fp32.tflite"), num_threads=1)
    outputs = []
    previous_length = None
    for i in range(len(normalized)):
        sequence = normalized[max(0, i - 60) : i + 1]
        if previous_length != len(sequence):
            runner.resize_tensor_input(
                runner.get_input_details()[0]["index"], [1, len(sequence), 378], strict=True
            )
            runner.allocate_tensors()
            previous_length = len(sequence)
        runner.set_tensor(runner.get_input_details()[0]["index"], sequence[None])
        runner.invoke()
        logits = runner.get_tensor(runner.get_output_details()[0]["index"])[0]
        exponential = np.exp(logits - np.max(logits))
        outputs.append(exponential / exponential.sum())
    probabilities = np.asarray(outputs)
    assert len(probabilities) == 669
    assert np.max(np.abs(probabilities - arrays["probabilities"])) <= 1e-4
    assert np.array_equal(probabilities.argmax(1), arrays["probabilities"].argmax(1))
    candidate = (
        root
        / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
        / "s2_r2_continuous_domain_correction_01/main_candidate"
    )
    assert diag.sha256(candidate / "best_model.keras") == diag.MODEL_SHA
    assert diag.sha256(candidate / "normalization.json") == diag.NORM_SHA
    model = tf.keras.models.load_model(candidate / "best_model.keras", compile=False)
    logits = np.asarray(model(normalized[None], training=False))[0]
    exponential = np.exp(logits - logits.max(axis=1, keepdims=True))
    reference = exponential / exponential.sum(axis=1, keepdims=True)
    maximum_difference = float(np.max(np.abs(reference - probabilities)))
    assert maximum_difference <= 1e-4
    assert np.array_equal(reference.argmax(1), probabilities.argmax(1))
    print(
        f"S2-R2 host fixture: count=669 max_probability_difference={maximum_difference:.9g} "
        "argmax_mismatches=0"
    )


@pytest.mark.parametrize(
    "defect,expected",
    [
        ("hash", "IDENTITY"),
        ("missing", "INCOMPLETE"),
        ("overlap", "OVERLAPPING"),
        ("unbounded", "BOUNDARIES"),
    ],
)
def test_review_fails_closed(defect: str, expected: str) -> None:
    labels, integrity = labels_and_integrity()
    if defect == "hash":
        labels["evidence_sha256"] = "other"
    elif defect == "missing":
        labels["reviewed_blocks"] = []
    elif defect == "overlap":
        labels["signs"][1]["start_index"] = 1
    else:
        labels["negative_intervals"][0]["judgment"] = "CONFIRMED_NON_SIGN"
    with pytest.raises(ValueError, match=expected):
        diag.validate_labels(labels, integrity, 140, "session")


@pytest.mark.parametrize("with_event", [False, True])
def test_capture_audit_and_blinded_review_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, with_event: bool
) -> None:
    rows, events = stream(([0, 1, 1, 2, 2, 2] + [0] * 8) if with_event else [0] * 14)
    for event in events:
        event["materialized_source_indices"] = list(range(6))
        event["recognition_v2_source_indices"] = list(range(6))
        event["recognition_v2_mask_count"] = 6
    deliveries = [
        {"event_id": e["event_id"], "ui_delivery_elapsed_realtime_ns": 1050_000_000} for e in events
    ]
    for i, row in enumerate(rows):
        row.update(
            exact_record_index=i,
            decision_elapsed_realtime_ns=int((row["source_timestamp_ms"] + 50) * 1e6),
            visual_evidence_original=f"continuous_visual/originals/frame_{i + 1:06d}_original.jpg",
        )
        image = tmp_path / row["visual_evidence_original"]
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"synthetic-source-linkage-test-not-a-video")
        diag.write(
            image.with_name(f"frame_{i + 1:06d}_evidence.json"),
            {
                "ordinal": i + 1,
                "source_timestamp_ns": int(row["source_timestamp_ms"] * 1e6),
                "original_sha256": diag.sha256(image),
            },
        )
    diag.write(
        tmp_path / "continuous_visual/evidence_summary.json",
        {"finalized_after_capture_stop": True, "verified_original_files": 14},
    )
    diag.write(
        tmp_path / "session_identity.json",
        {
            "protected_baseline_sha": diag.BASELINE,
            "diagnostic_milestone": diag.MILESTONE,
            "transition_diagnostics_enabled": True,
        },
    )
    diag.write(
        tmp_path / "identity.json",
        {
            "segmentation": {
                "package_id": "S2_R2_CANDIDATE",
                "source_checkpoint_sha256": diag.MODEL_SHA,
                "source_normalization_sha256": diag.NORM_SHA,
                "tflite_sha256": diag.TFLITE_SHA,
            },
            "decoder": {
                "rearm_policy": "PRE_OR_POST_EXPERIMENTAL",
                "admission_policy": "PASS_THROUGH",
                "minimum_active_ms": 133.308,
                "pre_gap_reset_ms": 133.308,
                "post_confirm_ms": 266.616,
                "rearm_pre_stable_ms": 399.924,
                "maximum_continuous_observation_gap_ms": 533.232,
            },
        },
    )
    diag.write(tmp_path / "s2_exact_parity/manifest.json", {"synthetic": True})
    for name, values in (
        ("observations.jsonl", rows),
        ("events.jsonl", events),
        ("ui_delivery.jsonl", deliveries),
    ):
        (tmp_path / name).write_text(
            "".join(json.dumps(v) + "\n" for v in values), encoding="utf-8"
        )
    markers = []
    for i, block in enumerate(diag.BLOCKS):
        for action, index in (("BEGIN", i * 2), ("COMPLETE", i * 2 + 1)):
            markers.append(
                {
                    "action": action,
                    "expected_gloss": block,
                    "attempt_id": i + 1,
                    "marked_at_elapsed_realtime_ns": int(rows[index]["source_timestamp_ms"] * 1e6),
                }
            )
    (tmp_path / "attempts.jsonl").write_text(
        "".join(json.dumps(v) + "\n" for v in markers), encoding="utf-8"
    )
    capture = SimpleNamespace(
        count=14,
        raw=SimpleNamespace(timestamp_ms=np.asarray([r["source_timestamp_ms"] for r in rows])),
        android_argmax=np.asarray([r["argmax_state"] for r in rows]),
        android_probabilities=np.asarray(
            [
                [r[k] for k in ("pre_probability", "active_probability", "post_probability")]
                for r in rows
            ],
            np.float32,
        ),
    )
    monkeypatch.setattr(diag, "load_capture", lambda *args, **kwargs: capture)
    output = diag.prepare(tmp_path)
    assert diag.read_json(output / "integrity.json")["status"] == "CAPTURE_INTEGRITY_PASS"
    manifest = diag.read_json(output / "review_manifest.json")
    assert "probability" not in json.dumps(manifest)
    template = output / "human_boundaries.template.json"
    template.write_text('{"preserved_review": true}', encoding="utf-8")
    diag.prepare(tmp_path)
    assert diag.read_json(template) == {"preserved_review": True}
    correct_path = rows[0]["visual_evidence_original"]
    rows[0]["visual_evidence_original"] = "continuous_visual/originals/frame_000002_original.jpg"
    observation_path = tmp_path / "observations.jsonl"
    observation_path.write_text("".join(json.dumps(v) + "\n" for v in rows), encoding="utf-8")
    with pytest.raises(ValueError, match="OBSERVATION_TENSOR_LINKAGE_MISMATCH"):
        diag.audit(tmp_path)
    rows[0]["visual_evidence_original"] = correct_path
    observation_path.write_text("".join(json.dumps(v) + "\n" for v in rows), encoding="utf-8")
    (tmp_path / rows[0]["visual_evidence_original"]).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="VISUAL_IDENTITY_MISMATCH"):
        diag.audit(tmp_path)
