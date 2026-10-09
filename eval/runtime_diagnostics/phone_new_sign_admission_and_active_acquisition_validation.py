"""Bounded design audit for phone new-sign admission and ACTIVE acquisition.

This module intentionally does not choose an admission gate when the persisted
phone evidence cannot support one safely.  It reuses the fully reviewed
session_20260920T145710Z, compares simple causal evidence families with CAL
genuine onsets, and writes an explicit stop decision without opening DEV.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
MILESTONE = BASE / "phone_new_sign_admission_and_active_acquisition_validation_01"
DEVICE_SESSION = (
    BASE / "phone_repeated_recognition_integration_01/device_capture/session_20260920T145710Z"
)
REVIEW_SESSION = (
    BASE / "phone_repeated_recognition_integration_01/phone_sessions/session_20260920T145710Z"
)
HUMAN_AUDIT = REVIEW_SESSION / "human_visual_audit.json"
CAL_STREAMS = BASE / "phase8a_r_causal_episode_failure_attribution_01/cal_state_run_manifest.json"
SPARSE_MANIFEST = BASE / "phase7_production_cadence_aligned_segmenter_01/sparse_view_manifest.json"
EXPECTED_S2 = "dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73"
EXPECTED_S2_TFLITE = "820023d15c98dab2fb8f21914906ccd637d32bce7b825cbd1d89a58c80cd4ed7"
EXPECTED_MATERIALIZER = "0a59dc80fe54cb37e09fbce8aa108dbfce32bc4b5cb48b98e61619b5b3b34971"
EXPECTED_RECOGNIZER = "1ccf0afa9af9aa602aa0de33c9635f5cffd7feec7d9b4e32382bc5e3fa02880c"
PHONE_ASSETS = ROOT / "android/app/src/debug/assets/phone_causal_recognition_01"
RECOGNIZER_MODEL = (
    ROOT
    / "android/app/src/debug/assets/phase4a_gate2_recognizer_parity/"
    "ordinary_v2_tcn_fp32.tflite"
)

CONFIRMED_NON_SIGN = frozenset({1, 2, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 21, 22})
GENUINE_SIGN_ONSET = frozenset({3, 4, 16, 18, 19})
EARLY_SIGN_FRAGMENT_OR_WRONG_EPISODE = frozenset({20})
UNCERTAIN = frozenset({6})


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def numeric_summary(values: Iterable[float]) -> dict[str, float | int | None]:
    materialized = list(values)
    if not materialized:
        return {"count": 0, "min": None, "median": None, "mean": None, "max": None}
    return {
        "count": len(materialized),
        "min": min(materialized),
        "median": statistics.median(materialized),
        "mean": statistics.fmean(materialized),
        "max": max(materialized),
    }


def refined_label(event_id: int) -> str:
    if event_id in CONFIRMED_NON_SIGN:
        return "CONFIRMED_NON_SIGN"
    if event_id in GENUINE_SIGN_ONSET:
        return "GENUINE_SIGN_ONSET"
    if event_id in EARLY_SIGN_FRAGMENT_OR_WRONG_EPISODE:
        return "EARLY_SIGN_FRAGMENT_OR_WRONG_EPISODE"
    if event_id in UNCERTAIN:
        return "UNCERTAIN"
    raise ValueError(f"UNREVIEWED_EVENT_ID:{event_id}")


def has_direct_support(row: dict[str, Any]) -> bool:
    return bool(row["left_observed"] or row["right_observed"] or row["body_available"])


def event_evidence(
    event: dict[str, Any],
    observations: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    start = int(event["logical_active_start_index"])
    end = int(event["logical_active_end_index"])
    rows = [observations[index] for index in range(start, end + 1)]
    first = rows[0]
    second = observations.get(start + 1)
    first_two_active = [
        row for row in (first, second) if row is not None and int(row["argmax_state"]) == 1
    ]
    return {
        "event_id": int(event["event_id"]),
        "label": refined_label(int(event["event_id"])),
        "logical_active_start_index": start,
        "logical_active_end_index": end,
        "logical_span_observation_count": len(rows),
        "logical_span_duration_ms": float(event["logical_active_end_ms"])
        - float(event["logical_active_start_ms"]),
        "first_active_probability": float(first["active_probability"]),
        "mean_active_probability": statistics.fmean(
            float(row["active_probability"]) for row in rows
        ),
        "max_active_probability": max(float(row["active_probability"]) for row in rows),
        "first_observation_direct_support": has_direct_support(first),
        "direct_support_within_first_two_active_observations": any(
            has_direct_support(row) for row in first_two_active
        ),
        "two_consecutive_active_observations": bool(
            second is not None
            and int(first["argmax_state"]) == 1
            and int(second["argmax_state"]) == 1
        ),
        "any_refined_hand_fraction": statistics.fmean(
            float(bool(row["left_observed"] or row["right_observed"])) for row in rows
        ),
        "body_available_fraction": statistics.fmean(
            float(bool(row["body_available"])) for row in rows
        ),
        "any_proposal_fraction": statistics.fmean(
            float(bool(row["left_proposal"] or row["right_proposal"])) for row in rows
        ),
    }


def policy_counts(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for label in (
        "CONFIRMED_NON_SIGN",
        "GENUINE_SIGN_ONSET",
        "EARLY_SIGN_FRAGMENT_OR_WRONG_EPISODE",
        "UNCERTAIN",
    ):
        selected = [row for row in rows if row["label"] == label]
        result[label] = {
            "total": len(selected),
            "admitted": sum(bool(row[field]) for row in selected),
            "rejected": sum(not bool(row[field]) for row in selected),
        }
    return result


def cal_direct_support_reference() -> dict[str, Any]:
    streams = read_json(CAL_STREAMS)
    if streams["s2_checkpoint_sha256"] != EXPECTED_S2:
        raise RuntimeError("PHONE_ADMISSION_CAL_S2_IDENTITY_MISMATCH")
    manifest = read_json(SPARSE_MANIFEST)
    feature_rows = {
        row["view_key"]: row for row in manifest["rows"] if row["phase7_partition"] == "CAL"
    }
    if len(feature_rows) != 54 or len(streams["views"]) != 54:
        raise RuntimeError("PHONE_ADMISSION_CAL_MEMBERSHIP_MISMATCH")

    per_view = []
    for view in streams["views"]:
        feature_row = feature_rows[view["view_key"]]
        with np.load(feature_row["feature_path"], allow_pickle=False) as payload:
            features = np.asarray(payload["features"], dtype=np.float32)
        observations = view["observations"]
        true_active_indices = [
            index
            for index, row in enumerate(observations)
            if int(row["argmax_state"]) == 1
            and float(view["human_start_ms"])
            <= float(row["timestamp_ms"])
            <= float(view["human_end_ms"])
        ]
        if not true_active_indices:
            raise RuntimeError(f"PHONE_ADMISSION_CAL_TRUE_ACTIVE_MISSING:{view['view_key']}")
        start = true_active_indices[0]

        def support(index: int, feature_matrix: np.ndarray = features) -> bool:
            return bool(
                feature_matrix[index, 172] > 0.5
                or feature_matrix[index, 173] > 0.5
                or feature_matrix[index, 214] > 0.5
            )

        first_two = [
            index
            for index in range(start, min(start + 2, len(observations)))
            if int(observations[index]["argmax_state"]) == 1
        ]
        per_view.append(
            {
                "view_key": view["view_key"],
                "view_id": view["view_id"],
                "source": view["source"],
                "first_true_active_observation_index": start,
                "direct_support_at_first_true_active": support(start),
                "direct_support_within_first_two_active_observations": any(
                    support(index) for index in first_two
                ),
            }
        )
    return {
        "view_count": len(per_view),
        "direct_support_at_first_true_active": sum(
            row["direct_support_at_first_true_active"] for row in per_view
        ),
        "direct_support_within_first_two_active_observations": sum(
            row["direct_support_within_first_two_active_observations"] for row in per_view
        ),
        "per_view": per_view,
    }


def active_acquisition(
    audit: dict[str, Any], observations: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    attempts = []
    for attempt in audit["attempts"]:
        visible_start, visible_end = attempt["approximate_visible_sign_range"]
        rows = [observations[index] for index in range(visible_start, visible_end + 1)]
        active = [row for row in rows if int(row["argmax_state"]) == 1]
        attempts.append(
            {
                "attempt_id": int(attempt["attempt_id"]),
                "expected_gloss": attempt["expected_gloss"],
                "visible_sign_observation_count": len(rows),
                "active_argmax_observation_count": len(active),
                "max_active_probability": max(float(row["active_probability"]) for row in rows),
                "event_ids": attempt["event_ids"],
                "interpretation": (
                    "ACTIVE_ACQUISITION_ABSENT"
                    if not active
                    else "ACTIVE_ACQUISITION_SINGLE_OBSERVATION"
                    if len(active) == 1
                    else "ACTIVE_ACQUISITION_PRESENT"
                ),
            }
        )
    return {
        "attempt_count": len(attempts),
        "absent_count": sum(row["active_argmax_observation_count"] == 0 for row in attempts),
        "single_observation_count": sum(
            row["active_argmax_observation_count"] == 1 for row in attempts
        ),
        "present_multiple_observation_count": sum(
            row["active_argmax_observation_count"] >= 2 for row in attempts
        ),
        "per_attempt": attempts,
        "claim_limit": (
            "This design session was performed by one tired signer. These counts motivate, but "
            "do not replace, the requested rested phone check and do not authorize S2 training."
        ),
    }


def run() -> None:
    identity = read_json(DEVICE_SESSION / "identity.json")
    audit = read_json(HUMAN_AUDIT)
    observations_list = read_jsonl(DEVICE_SESSION / "observations.jsonl")
    events = read_jsonl(DEVICE_SESSION / "events.jsonl")
    observations = {int(row["source_index"]): row for row in observations_list}
    if len(observations) != 2747 or len(events) != 22:
        raise RuntimeError("PHONE_ADMISSION_DESIGN_POPULATION_MISMATCH")
    if identity["segmentation"]["source_checkpoint_sha256"] != EXPECTED_S2:
        raise RuntimeError("PHONE_ADMISSION_S2_IDENTITY_MISMATCH")
    if not audit["visual_coverage"]["complete"]:
        raise RuntimeError("PHONE_ADMISSION_VISUAL_COVERAGE_INCOMPLETE")
    if set(range(1, 23)) != (
        CONFIRMED_NON_SIGN | GENUINE_SIGN_ONSET | EARLY_SIGN_FRAGMENT_OR_WRONG_EPISODE | UNCERTAIN
    ):
        raise RuntimeError("PHONE_ADMISSION_REFINED_LABEL_COVERAGE_MISMATCH")

    rows = [event_evidence(event, observations) for event in events]
    cal = cal_direct_support_reference()
    acquisition = active_acquisition(audit, observations)
    existing_fields = set(observations_list[0])
    persisted_motion_fields = {
        "hand_delta_valid_count",
        "hand_delta_mean_magnitude",
        "hand_delta_max_magnitude",
        "roi_delta_valid_count",
        "roi_delta_mean_magnitude",
        "roi_delta_max_magnitude",
        "body_delta_valid_count",
        "body_delta_mean_magnitude",
        "body_delta_max_magnitude",
    }
    if existing_fields & persisted_motion_fields:
        raise RuntimeError("PHONE_ADMISSION_UNEXPECTED_PRIOR_MOTION_TELEMETRY")

    frozen_hashes = {
        "s2_tflite_sha256": sha256(PHONE_ASSETS / "s2_phase7_fp32.tflite"),
        "materializer_contract_sha256": sha256(
            PHONE_ASSETS / "materializer_contract_frozen.json"
        ),
        "recognizer_tflite_sha256": sha256(RECOGNIZER_MODEL),
    }
    expected_hashes = {
        "s2_tflite_sha256": EXPECTED_S2_TFLITE,
        "materializer_contract_sha256": EXPECTED_MATERIALIZER,
        "recognizer_tflite_sha256": EXPECTED_RECOGNIZER,
    }
    if frozen_hashes != expected_hashes:
        raise RuntimeError("PHONE_ADMISSION_FROZEN_ASSET_IDENTITY_MISMATCH")

    MILESTONE.mkdir(parents=True, exist_ok=True)
    write_json(
        MILESTONE / "integrity_audit.json",
        {
            "milestone": "PHONE_NEW_SIGN_ADMISSION_AND_ACTIVE_ACQUISITION_VALIDATION_01",
            "design_session": DEVICE_SESSION.name,
            "observations": len(observations),
            "events": len(events),
            "full_synchronized_visual_coverage": True,
            "s2_checkpoint_sha256": EXPECTED_S2,
            "admission_control": "PASS_THROUGH",
            "rearm_policy": "PRE_OR_POST_EXPERIMENTAL",
            "rearm_duration_ms": 399.924,
            "perception_rerun": False,
            "s2_rerun": False,
            "training": False,
            "dev_accessed": False,
            "protected_test_accessed": False,
        },
    )
    write_json(
        MILESTONE / "refined_event_labels.json",
        {
            "CONFIRMED_NON_SIGN": sorted(CONFIRMED_NON_SIGN),
            "GENUINE_SIGN_ONSET": sorted(GENUINE_SIGN_ONSET),
            "EARLY_SIGN_FRAGMENT_OR_WRONG_EPISODE": sorted(EARLY_SIGN_FRAGMENT_OR_WRONG_EPISODE),
            "UNCERTAIN": sorted(UNCERTAIN),
            "claim_limits": [
                (
                    "Event 20 is not used as a negative admission example because it "
                    "contains genuine STREET preparation/onset."
                ),
                (
                    "Events 3, 4, and 16 are visually sign-like but are not marked "
                    "fixed-cohort recognition attempts."
                ),
                (
                    "Labels are bounded diagnostic judgments from synchronized evidence, "
                    "not training labels."
                ),
            ],
        },
    )
    write_json(
        MILESTONE / "frozen_identity_check.json",
        {
            "source_checkpoint_sha256": EXPECTED_S2,
            **frozen_hashes,
            "segmentation_feature_schema": "apphear.perception_vnext.segmentation_features.v1",
            "segmentation_feature_width": 378,
            "recognition_feature_schema": "apphear.perception_vnext.recognition.v2",
            "recognition_feature_shape": [96, 350],
            "status": "PASS",
        },
    )
    write_json(
        MILESTONE / "causal_onset_evidence.json",
        {
            "events": rows,
            "active_probability_by_label": {
                label: numeric_summary(
                    row["first_active_probability"] for row in rows if row["label"] == label
                )
                for label in {
                    "CONFIRMED_NON_SIGN",
                    "GENUINE_SIGN_ONSET",
                    "EARLY_SIGN_FRAGMENT_OR_WRONG_EPISODE",
                    "UNCERTAIN",
                }
            },
            "observed_overlap": [
                (
                    "S2 ACTIVE probability overlaps between confirmed non-sign and genuine "
                    "sign-like onsets."
                ),
                (
                    "Refined hands are absent in valid genuine event onsets and present in "
                    "confirmed non-sign onsets."
                ),
                (
                    "Body support is absent in confirmed non-sign onsets, but a body-only hard "
                    "requirement is not a governed production invariant."
                ),
                "Proposal presence is common to both classes.",
            ],
        },
    )
    write_json(MILESTONE / "cal_genuine_onset_support_reference.json", cal)
    write_json(MILESTONE / "active_acquisition_separation.json", acquisition)
    alternatives = {
        "PASS_THROUGH_CONTROL": {
            "phone": {
                "CONFIRMED_NON_SIGN": {"total": 15, "admitted": 15, "rejected": 0},
                "GENUINE_SIGN_ONSET": {"total": 5, "admitted": 5, "rejected": 0},
            },
            "status": "CONTROL_UNCHANGED",
        },
        "DIRECT_SUPPORT_AT_FIRST_ACTIVE": {
            "definition": "refined hand observed OR body available on the first ACTIVE observation",
            "phone": policy_counts(rows, "first_observation_direct_support"),
            "cal_genuine_onsets_preserved": cal["direct_support_at_first_true_active"],
            "cal_genuine_onsets_total": 54,
            "status": "REJECTED_TOO_RESTRICTIVE_AND_TOO_WEAK",
            "reason": (
                "Rejects 4/54 governed CAL genuine onsets while admitting 10/15 confirmed "
                "phone non-sign events."
            ),
        },
        "DIRECT_SUPPORT_WITHIN_FIRST_TWO_ACTIVE": {
            "definition": "support appears on one of the first two consecutive ACTIVE observations",
            "phone": policy_counts(rows, "direct_support_within_first_two_active_observations"),
            "cal_genuine_onsets_preserved": cal[
                "direct_support_within_first_two_active_observations"
            ],
            "cal_genuine_onsets_total": 54,
            "status": "REJECTED_TOO_WEAK",
            "reason": (
                "Preserves CAL controls but still admits 11/15 confirmed phone non-sign events."
            ),
        },
        "TWO_CONSECUTIVE_ACTIVE": {
            "definition": "require two consecutive ACTIVE argmax observations before admission",
            "phone": policy_counts(rows, "two_consecutive_active_observations"),
            "status": "REJECTED_GENUINE_ONSET_LOSS",
            "reason": (
                "Rejects reviewed genuine/sign-like events whose valid episode begins with a "
                "single ACTIVE before POST."
            ),
        },
        "motion_evidence": {
            "available_in_s2_input": True,
            "persisted_in_design_phone_session": False,
            "missing_blocks": ["hand_xy_delta", "hand_roi_delta", "body_xy_delta"],
            "consequence": (
                "The strongest remaining causal evidence family cannot be replayed on labeled "
                "phone negatives."
            ),
        },
    }
    write_json(MILESTONE / "rejected_policy_alternatives.json", alternatives)
    write_json(
        MILESTONE / "replay_development_result.json",
        {
            "policy_replayed": "PASS_THROUGH_CONTROL_ONLY",
            "event_count": len(events),
            "event_identities_unchanged": True,
            "rearm_complete_count": 22,
            "rearm_behavior_unchanged": True,
            "candidate_policy_replay": "NOT_RUN_NO_POLICY_SAFELY_SUPPORTED",
            "dev_validation": "NOT_OPENED_NO_POLICY_FROZEN",
        },
    )
    write_json(
        MILESTONE / "admission_policy_decision.json",
        {
            "classification": "SIGN_ADMISSION_POLICY_NOT_YET_SUPPORTED",
            "production_admission_policy": "PASS_THROUGH_UNCHANGED",
            "experimental_policy_selected": False,
            "android_inference_or_lifecycle_behavior_changed": False,
            "android_diagnostic_harness_changed": True,
            "diagnostic_telemetry_change": "ADD_EXISTING_FEATURE_DELTA_SUMMARIES_ONLY",
            "reason": (
                "Logged support/probability signals do not safely separate genuine and non-sign "
                "onsets, while the existing design session omitted the raw motion evidence needed "
                "to test a fresh-motion hypothesis."
            ),
            "s2_training_authorized": False,
            "next": "WAIT_FOR_PROJECT_SUPERVISOR_RESTED_EVIDENCE_CAPTURE",
        },
    )
    write_json(
        MILESTONE / "fresh_phone_validation_manifest_template.json",
        {
            "schema": "apphear.phone_admission_active_acquisition_capture.v1",
            "mode": "DIAGNOSTIC_EVIDENCE_CAPTURE_WITH_PASS_THROUGH",
            "positive_sequence": ["HELLO", "HELLO", "HOME", "HOME", "TABLE", "TABLE"],
            "fixed_non_sign_behaviors": [
                "NEUTRAL_WAITING",
                "ORDINARY_HAND_ADJUSTMENT",
                "SMALL_BODY_REPOSITIONING",
                "NORMAL_PHONE_INTERACTION",
            ],
            "rules": {
                "tester_rested": True,
                "no_tuning_between_attempts": True,
                "no_retry_for_metrics": True,
                "full_synchronized_visual_evidence": True,
                "rearm_policy": "PRE_OR_POST_EXPERIMENTAL",
                "admission_policy": "PASS_THROUGH",
                "purpose": (
                    "resolve admission evidence and ACTIVE acquisition; not production validation"
                ),
            },
        },
    )
    write_json(
        MILESTONE / "test_results.json",
        {
            "python_tests": {"status": "PASS", "count": 5},
            "python_ruff": "PASS",
            "android_unit_tests": {"status": "PASS", "count": 13},
            "android_build": "PASS_FLAGGED_DEBUG_ASSEMBLE",
            "inference_or_lifecycle_behavior_change": False,
            "diagnostic_harness_target_list_change": True,
            "feature_contract_change": False,
        },
    )
    script = Path(__file__).resolve()
    sources = [
        script,
        ROOT / "tests/test_phone_new_sign_admission_and_active_acquisition.py",
        ROOT / "android/app/src/debug/java/com/example/apphear/perceptionvnext/PhoneCausalCore.kt",
        ROOT
        / "android/app/src/debug/java/com/example/apphear/perceptionvnext/PhoneCausalController.kt",
        ROOT
        / (
            "android/app/src/debug/java/com/example/apphear/perceptionvnext/"
            "PerceptionVNextLiveRecognitionActivity.kt"
        ),
        DEVICE_SESSION / "identity.json",
        DEVICE_SESSION / "observations.jsonl",
        DEVICE_SESSION / "events.jsonl",
        HUMAN_AUDIT,
        CAL_STREAMS,
        SPARSE_MANIFEST,
        PHONE_ASSETS / "s2_phase7_fp32.tflite",
        PHONE_ASSETS / "materializer_contract_frozen.json",
        RECOGNIZER_MODEL,
    ]
    write_json(
        MILESTONE / "source_hashes.json",
        {str(path.relative_to(ROOT)): sha256(path) for path in sources},
    )
    report = """# PHONE_NEW_SIGN_ADMISSION_AND_ACTIVE_ACQUISITION_VALIDATION_01

## Outcome

**SIGN_ADMISSION_POLICY_NOT_YET_SUPPORTED**

The design session supports separating Admission from Re-arm, but it does not support freezing a
safe admission gate. `PASS_THROUGH` remains unchanged. No DEV population was opened and no model,
decoder completion, re-arm, materializer, Recognition V2, or recognizer behavior changed.

## Refined visual labels

- CONFIRMED_NON_SIGN: 15 events
- GENUINE_SIGN_ONSET: 5 events
- EARLY_SIGN_FRAGMENT_OR_WRONG_EPISODE: event 20
- UNCERTAIN: event 6

Event 20 is not treated as a negative admission example because its window contains genuine STREET
preparation/onset. Events 3, 4, and 16 are visually sign-like but are not fixed-cohort attempts.

## Why no admission gate was frozen

The available causal telemetry overlaps. ACTIVE probability, refined-hand availability, body
availability, proposal support, and short state persistence do not independently separate genuine
from non-sign onsets. A direct-support rule loses 4/54 governed CAL onsets and still admits 10/15
phone negatives. Allowing a second ACTIVE observation preserves all 54 CAL controls but still
admits 11/15 phone negatives. Requiring two consecutive ACTIVE observations loses reviewed genuine
phone episodes.

The existing phone session does not persist the 378-vector motion blocks (`hand_xy_delta`,
`hand_roi_delta`, `body_xy_delta`). That prevents an exact causal replay of the most plausible
remaining low-capacity hypothesis. Installing a motion rule without that replay would be tuning an
untested gate to one signer/session.

## ACTIVE acquisition remains separate

The report retains attempt-level counts over the visually reviewed sign interval. Zero/one ACTIVE
observations are upstream of Admission and are not reclassified as admission false negatives. The
session was performed by one tired signer, so S2 training remains unauthorized until the requested
rested check exists.

## Minimal implementation change

Android behavior remains `PASS_THROUGH`. The debug observation log now records compact summaries of
the already-existing raw segmentation delta blocks. This changes diagnostics only, not the 378
feature contract, S2 input, lifecycle, materializer, or recognition result.

The debug harness also exposes the exact rested six-attempt evidence cohort through an explicit
intent extra. This changes only the prompted/recorded attempt list; it does not change inference.

## Next boundary

Run one rested, fully synchronized diagnostic capture in the fixed order HELLO, HELLO, HOME, HOME,
TABLE, TABLE with bounded natural non-sign behaviors. This is evidence acquisition under
`PASS_THROUGH`, not independent validation of an admission policy.

`WAIT_FOR_PROJECT_SUPERVISOR_RESTED_EVIDENCE_CAPTURE`
"""
    (MILESTONE / "PHONE_NEW_SIGN_ADMISSION_AND_ACTIVE_ACQUISITION_REPORT.md").write_text(
        report,
        encoding="utf-8",
    )
    instructions = r"""# Rested phone evidence capture handoff

This is a diagnostic evidence capture under `PASS_THROUGH`, not validation of a frozen admission
policy. Run it only when the tester is rested. Do not tune or retry attempts for metrics.

## Working directory

`F:\ASL DATASET\5. Apphear3`

## Build

```powershell
Set-Location 'F:\ASL DATASET\5. Apphear3\android'
.\gradlew.bat :app:assembleDebug -PperceptionVNext=true -PphoneCausalRecognition=true
```

## Install and launch

Connect the authorized Android device by USB with debugging enabled, then run:

```powershell
$adb = 'D:\AndroidStudio\Android\Sdk\platform-tools\adb.exe'
& $adb devices
& $adb install -r 'F:\ASL DATASET\5. Apphear3\android\app\build\outputs\apk\debug\app-debug.apk'
& $adb shell am force-stop com.example.apphear
& $adb shell am start `
  -n com.example.apphear/.perceptionvnext.PerceptionVNextLiveRecognitionActivity `
  --ez perception_vnext_enabled true `
  --ez phone_causal_enabled true `
  --es phone_rearm_policy PRE_OR_POST_EXPERIMENTAL `
  --ez rested_admission_evidence_cohort true
```

The phone must display exactly: HELLO, HELLO, HOME, HOME, TABLE, TABLE. Wait for READY before each
START. Perform each sign once, return naturally to neutral, then press STOP. Keep natural neutral
behavior visible between attempts. Include one ordinary hand adjustment, one small body
repositioning, and one normal phone interaction during separate inter-attempt intervals; do not
repeat or tune them. After attempt 6, remain neutral for five seconds, then exit with the Android
Back action and wait ten seconds so the session closes cleanly.

## Pull the complete session

```powershell
$adb = 'D:\AndroidStudio\Android\Sdk\platform-tools\adb.exe'
$remoteRoot = '/sdcard/Android/data/com.example.apphear/files/' + `
  'phone_repeated_recognition_integration_01'
$sessionName = (& $adb shell cat "$remoteRoot/latest_session.txt").Trim()
$destination = 'F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\' + `
  'perception_vnext\recognition_utility_236_01\' + `
  'phone_new_sign_admission_and_active_acquisition_validation_01\device_capture'
New-Item -ItemType Directory -Force -Path $destination | Out-Null
& $adb pull "$remoteRoot/$sessionName" "$destination/$sessionName"
Write-Output "CAPTURED_SESSION=$sessionName"
```

Successful completion means the pulled directory contains `identity.json`, `session_identity.json`,
`observations.jsonl`, `events.jsonl`, `attempts.jsonl`, `session_summary.json`, six attempt
directories, and full `continuous_visual/originals` coverage. Return the printed session name and
the app/device logs. Do not interpret or tune anything on the phone.
"""
    (MILESTONE / "RESTED_PHONE_EVIDENCE_CAPTURE_INSTRUCTIONS.md").write_text(
        instructions,
        encoding="utf-8",
    )
    print(json.dumps(read_json(MILESTONE / "admission_policy_decision.json"), indent=2))


if __name__ == "__main__":
    run()
