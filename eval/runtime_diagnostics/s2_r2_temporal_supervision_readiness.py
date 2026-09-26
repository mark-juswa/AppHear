"""Finalize the governed S2-R2 supervision-readiness decision without training."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MILESTONE = "S2_R2_PHONE_TEMPORAL_SUPERVISION_01"
FEATURE_SCHEMA = "apphear.perception_vnext.segmentation_features.v1"
FEATURE_WIDTH = 378
S2_SHA256 = "dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73"
NORMALIZATION_SHA256 = "3018348ae8cc9fe0671eda913535556e14cebf5a16fbe72a96be73ed494e9130"

BASE = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
)
OUT = BASE / "s2_r2_phone_temporal_supervision_01"
P1_SUMMARY = OUT / "p1_temporal_review_01/p1_temporal_review_summary.json"
P1_INTERVALS = OUT / "p1_temporal_review_01/p1_reviewed_intervals.csv"
PHONE_SUMMARY = (
    OUT
    / "phone_positive_temporal_review_01/phone_positive_temporal_review_summary.json"
)
PHONE_LABELS = (
    OUT / "phone_positive_temporal_review_01/phone_positive_observation_labels.csv"
)
SIGNER_AUDIT = OUT / "signer_governance_audit.json"
POSITIVE_SEARCH = OUT / "existing_positive_signer_diversity_search.json"
N0_DECISION = OUT / "n0_usage_decision.json"
BASELINE_MANIFEST = (
    BASE
    / "phase5_1t_2_bounded_segmentation_seed_dataset_01"
    / "selected_120_manifest.json"
)
UNUSED_AUDIT = (
    BASE
    / "phase8a_u_s2_training_exposure_and_terminal_diversity_audit_01"
    / "unused_governed_data_audit.json"
)
PHONE_OBSERVATIONS = (
    BASE
    / "phone_new_sign_admission_and_active_acquisition_validation_01/device_capture_final"
    / "session_20260921T102840Z/observations.jsonl"
)

STATE_NAMES = {0: "PRE_IDLE", 1: "ACTIVE_SIGN", 2: "POST_RECOVERY"}


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_phone_join(
    labels_path: Path = PHONE_LABELS,
    observations_path: Path = PHONE_OBSERVATIONS,
) -> list[dict[str, Any]]:
    observations: dict[int, dict[str, Any]] = {}
    with observations_path.open("r", encoding="utf-8-sig") as stream:
        for line in stream:
            item = json.loads(line)
            timestamp_ns = round(float(item["source_timestamp_ms"]) * 1_000_000.0)
            if timestamp_ns in observations:
                raise ValueError(f"DUPLICATE_OBSERVATION_TIMESTAMP:{timestamp_ns}")
            observations[timestamp_ns] = item
    joined: list[dict[str, Any]] = []
    seen: set[int] = set()
    with labels_path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            timestamp_ns = int(row["source_timestamp_ns"])
            if timestamp_ns in seen:
                raise ValueError(f"DUPLICATE_PHONE_LABEL_TIMESTAMP:{timestamp_ns}")
            seen.add(timestamp_ns)
            observation = observations.get(timestamp_ns)
            if observation is None:
                raise ValueError(f"PHONE_LABEL_OBSERVATION_NOT_FOUND:{timestamp_ns}")
            # Session-level observations store the numeric attempt ordinal, while the immutable
            # attempt manifest and label export use the canonical ``attempt_NNN`` identifier.
            if int(observation.get("attempt_id")) != int(row["attempt_ordinal"]):
                raise ValueError(f"PHONE_ATTEMPT_LINK_MISMATCH:{timestamp_ns}")
            prediction_id = int(observation["argmax_state"])
            joined.append(
                {
                    **row,
                    "state_id": int(row["state_id"]),
                    "prediction_id": prediction_id,
                    "prediction_name": STATE_NAMES[prediction_id],
                    "pre_probability": float(observation["pre_probability"]),
                    "active_probability": float(observation["active_probability"]),
                    "post_probability": float(observation["post_probability"]),
                }
            )
    return joined


def summarize_phone_baseline(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 202:
        raise RuntimeError(f"PHONE_LABEL_COUNT_MISMATCH:{len(rows)}")
    if {row["attempt_id"] for row in rows} != {
        "attempt_001",
        "attempt_002",
        "attempt_003",
        "attempt_004",
        "attempt_005",
    }:
        raise RuntimeError("PHONE_ATTEMPT_SET_MISMATCH")
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    eligible = [row for row in rows if row["state_name"] != "IGNORED"]
    for row in eligible:
        confusion[row["state_name"]][row["prediction_name"]] += 1
    per_attempt: list[dict[str, Any]] = []
    for attempt_id in sorted({row["attempt_id"] for row in rows}):
        attempt_rows = [row for row in rows if row["attempt_id"] == attempt_id]
        active_rows = [row for row in attempt_rows if row["state_name"] == "ACTIVE_SIGN"]
        predicted_active = [
            row for row in active_rows if row["prediction_name"] == "ACTIVE_SIGN"
        ]
        per_attempt.append(
            {
                "attempt_id": attempt_id,
                "expected_gloss": attempt_rows[0]["expected_gloss"],
                "supervision_role": attempt_rows[0]["supervision_role"],
                "human_active_observations": len(active_rows),
                "s2_active_during_human_active": len(predicted_active),
                "active_acquired": bool(predicted_active),
                "max_active_probability_during_human_active": max(
                    row["active_probability"] for row in active_rows
                ),
            }
        )
    correct = sum(row["state_name"] == row["prediction_name"] for row in eligible)
    human_active = [row for row in eligible if row["state_name"] == "ACTIVE_SIGN"]
    active_correct = sum(row["prediction_name"] == "ACTIVE_SIGN" for row in human_active)
    return {
        "schema": "apphear.s2_r2.phone_positive_baseline_alignment.v1",
        "milestone": MILESTONE,
        "population_role": "DESIGN_AND_HARD_EXAMPLE_ONLY_NOT_INDEPENDENT_VALIDATION",
        "session_id": "session_20260921T102840Z",
        "observations_total": len(rows),
        "observations_scored": len(eligible),
        "human_label_counts": dict(sorted(Counter(row["state_name"] for row in rows).items())),
        "confusion_actual_rows_predicted_columns": {
            actual: dict(sorted(predicted.items()))
            for actual, predicted in sorted(confusion.items())
        },
        "observation_accuracy": correct / len(eligible),
        "active_observation_recall": active_correct / len(human_active),
        "attempts_with_any_s2_active_during_human_active": sum(
            item["active_acquired"] for item in per_attempt
        ),
        "attempt_count": len(per_attempt),
        "per_attempt": per_attempt,
        "interpretation": (
            "Human-reviewed phone signs are valid ACTIVE supervision. Frozen S2 predicts "
            "POST for 50/62 ACTIVE observations and acquires ACTIVE in only the two "
            "positive-anchor attempts. This is design evidence, not an independent "
            "performance estimate."
        ),
    }


def build_dataset_decision() -> dict[str, Any]:
    p1 = read_json(P1_SUMMARY)
    phone = read_json(PHONE_SUMMARY)
    signer = read_json(SIGNER_AUDIT)
    positive = read_json(POSITIVE_SEARCH)
    n0 = read_json(N0_DECISION)
    return {
        "schema": "apphear.s2_r2.dataset_manifest_candidate.v1",
        "milestone": MILESTONE,
        "status": "NOT_FROZEN_GOVERNANCE_BLOCKED",
        "feature_contract": {"schema": FEATURE_SCHEMA, "width": FEATURE_WIDTH},
        "frozen_baseline": {
            "s2_checkpoint_sha256": S2_SHA256,
            "normalization_sha256": NORMALIZATION_SHA256,
            "fit_clips": positive["baseline"]["fit_clips"],
            "fit_signers": positive["baseline"]["fit_signers"],
            "cal_clips": positive["baseline"]["cal_clips"],
            "cal_signers": positive["baseline"]["cal_signers"],
            "dev_clips": positive["baseline"]["dev_clips"],
        },
        "candidate_components": [
            {
                "component": "EXISTING_GOVERNED_FIT_71",
                "role": "FIT",
                "status": "ELIGIBLE_EXISTING_CURRENT_CONTRACT",
            },
            {
                "component": "UNUSED_GOVERNED_HUMAN_LABELED_ENRICHMENT_17",
                "role": "FIT_CANDIDATE",
                "status": "ELIGIBLE_AFTER_CURRENT_CONTRACT_REEXTRACTION",
                "new_independent_apphear_or_local_signer": False,
            },
            {
                "component": "RESTED_PHONE_POSITIVES_5",
                "role": "DESIGN_HARD_POSITIVE_CANDIDATE",
                "status": "QUARANTINED_PENDING_CURRENT_PHONE_SIGNER_ROLE_ATTESTATION",
                "observation_labels": phone["observation_label_counts"],
                "independent_validation": False,
            },
            {
                "component": "P1_REVIEWED_NEGATIVES",
                "role": "HARD_CONTINUOUS_NEGATIVE_CANDIDATE",
                "status": "QUARANTINED_PENDING_P01_P02_SPLIT_ATTESTATION",
                "participants": sorted(
                    p1["confirmed_non_sign_interval_count_by_participant"]
                ),
                "intervals": p1["eligible_intervals"],
                "duration_ms": p1["duration_ms_by_category"]["CONFIRMED_NON_SIGN"],
            },
            {
                "component": "N0",
                "role": "OPTIONAL_SUPPORTING_NEGATIVE",
                "status": n0["decision"],
                "selected_intervals": 0,
            },
            {
                "component": "E6_0F747C_S001",
                "role": "UNTOUCHED_NEGATIVE_AND_ACQUISITION_ONLY_VALIDATION",
                "status": "PRESERVED_UNCONSUMED",
            },
            {
                "component": "HISTORICAL_DEV_23",
                "role": "OPENED_DIAGNOSTIC_REGRESSION_ONLY",
                "status": "NOT_TRAINING_NOT_INDEPENDENT_POST_R2_PROMOTION",
            },
        ],
        "governance_blockers": [
            signer["decision"],
            "CURRENT_PHONE_DESIGN_SIGNER_IDENTITY_AND_SPLIT_ROLE_UNRESOLVED",
            positive["decision"],
        ],
        "minimum_new_data_after_governance_resolution": {
            "negative_capture": "NOT_REQUIRED",
            "positive_capture": (
                "ONE_DISTINCT_PHONE_SIGNER_SESSION_RESERVED_FOR_POST_FREEZE_VALIDATION"
            ),
            "positive_scope": (
                "small class-agnostic cohort with approximately six deliberately performed "
                "attempts spanning at least three temporal behaviors and genuine "
                "PRE/ACTIVE/POST context; not a 236-word collection"
            ),
        },
        "protected_test_accessed": False,
        "training_authorized": False,
    }


def build_training_plan() -> dict[str, Any]:
    return {
        "schema": "apphear.s2_r2.training_plan.v1",
        "milestone": MILESTONE,
        "status": "DESIGN_ONLY_NOT_RUN",
        "candidate_name": "S2_R2_CONTINUOUS_DOMAIN_CORRECTION_01",
        "architecture": "unchanged Phase-7 causal TCN family",
        "feature_contract": {"schema": FEATURE_SCHEMA, "width": FEATURE_WIDTH},
        "normalization_strategy": (
            "fit-only cadence-aligned normalization recomputed only after the governed FIT "
            "manifest is frozen; no CAL/DEV/validation leakage"
        ),
        "sequence_strategy": [
            "retain chronological whole sequences and genuine timestamps",
            "reprocess approved historical MP4 sources through current "
            "Candidate01 -> raw-v1 -> 378",
            "process selected phone observations chronologically with their genuine timestamps",
            "apply loss only to human-reviewed labels; unmarked and 100 ms transition "
            "observations remain ignored",
            "no interpolation, duplication, or stale carry",
        ],
        "sampling_strategy": [
            "preserve signer/source grouping",
            "cap repeated intervals so P1 or the single phone design signer cannot dominate",
            "balance positive ACTIVE acquisition, ordinary-motion PRE suppression, and POST "
            "completion rather than global ACTIVE weighting",
        ],
        "checkpoint_selection": [
            "true-sign ACTIVE acquisition",
            "reviewed non-sign ACTIVE/event suppression",
            "causal event completion with unchanged CONFIG_01",
            "premature/severe cut regression",
            "per-signer and per-source results",
        ],
        "frozen_downstream": [
            "PRE_OR_POST re-arm at 399.924 ms",
            "Admission PASS_THROUGH",
            "CONFIG_01 completion logic",
            "cadence-safe materializer",
            "Recognition V2",
            "236-class recognizer",
        ],
        "training_command": None,
        "training_command_withheld_reason": (
            "The dataset manifest cannot be frozen until P01-P06/current-phone signer roles "
            "and an independent positive validation path are resolved."
        ),
        "training_started": False,
    }


def build_source_hashes() -> dict[str, Any]:
    paths = (
        P1_SUMMARY,
        P1_INTERVALS,
        PHONE_SUMMARY,
        PHONE_LABELS,
        SIGNER_AUDIT,
        POSITIVE_SEARCH,
        N0_DECISION,
        BASELINE_MANIFEST,
        UNUSED_AUDIT,
        PHONE_OBSERVATIONS,
    )
    return {
        "schema": "apphear.s2_r2.supervision_source_hashes.v1",
        "files": {
            str(path.relative_to(ROOT)): sha256_file(path) for path in paths
        },
    }


def write_report(
    baseline: dict[str, Any], dataset: dict[str, Any], training: dict[str, Any]
) -> None:
    phone = read_json(PHONE_SUMMARY)
    report = f"""# S2-R2 Phone Temporal Supervision Readiness

Milestone: `{MILESTONE}`

## P1 temporal review

All 30 hash-locked P1 videos were reviewed. The usable result is 45 bounded
`CONFIRMED_NON_SIGN` intervals totaling 623.065 seconds across P01 and P02. Covered motion
includes visible hand movement, grooming/adjustment, crossing/occlusion, hands entering/leaving
frame, body repositioning, neutral stillness, and other ordinary motion. Unmarked time remains
excluded. P1 is not yet authorized for fitting because P01/P02 cannot be mapped to governed
FIT/CAL/DEV identities.

## N0 decision

No full N0 review is justified. P1 already supplies the required hard-motion and static behavior
coverage. N0 remains preserved for a minimal diversity supplement only after participant/split
attestation; zero N0 intervals are currently selected.

## Phone-positive temporal labels

Five visually reviewed attempts are usable: HELLO 001/002, HOME 003/004, and TABLE 005. All have
clear PRE, ACTIVE, and POST context. With the frozen 100 ms transition ignore band, the labels are
`{phone['observation_label_counts']}`.

Against those human labels, frozen S2 observation accuracy is
`{baseline['observation_accuracy']:.4f}` and ACTIVE observation recall is
`{baseline['active_observation_recall']:.4f}`. S2 predicts POST for 50/62 human ACTIVE
observations and acquires any ACTIVE in only
{baseline['attempts_with_any_s2_active_during_human_active']}/5 attempts. This is
design/hard-example evidence, not independent validation.

## Existing positive diversity

The existing governed pool supplies 17 additional human-labeled TRAIN clips, but no new
independent APPHEAR/LOCAL signer. E6 signer `0F747C-S001` remains untouched and can support
negative and acquisition-only validation, but its short clips cannot validate continuous
PRE/ACTIVE/POST completion. No unreserved independent continuous-phone positive signer was found.

## Dataset and training decision

The candidate dataset design is complete but is **not frozen**. Two governance conditions remain:

1. authoritatively map P01-P06 and the current phone design signer to governed identities, or
   explicitly assign them development-only roles and retire any overlapping historical
   evaluation claim;
2. reserve one distinct phone signer/session for post-freeze positive continuous validation.

No new negative capture is required. The minimum genuinely missing data is one small independent
positive phone validation session—not a vocabulary collection.

The one-candidate plan preserves the causal TCN family and all downstream components. Historical
raw MP4s would be reprocessed through the current Candidate01/raw-v1/378 path, loss would be
masked to reviewed observations, and checkpoint selection would jointly consider ACTIVE
acquisition, non-sign suppression, and completion. No training command is emitted while the split
is unresolved.

## Stop state

`S2_R2_SUPERVISION_READY_GOVERNANCE_BLOCKED`

Stop before extraction or training and wait for signer/split attestation plus the independent
positive-validation role decision.
"""
    (OUT / "S2_R2_PHONE_TEMPORAL_SUPERVISION_REPORT.md").write_text(
        report, encoding="utf-8"
    )


def run() -> dict[str, Any]:
    baseline = summarize_phone_baseline(load_phone_join())
    dataset = build_dataset_decision()
    training = build_training_plan()
    hashes = build_source_hashes()
    atomic_json(OUT / "phone_positive_baseline_alignment.json", baseline)
    atomic_json(OUT / "s2_r2_dataset_manifest_candidate.json", dataset)
    atomic_json(OUT / "s2_r2_training_plan.json", training)
    atomic_json(OUT / "source_hashes.json", hashes)
    decision = {
        "schema": "apphear.s2_r2.supervision_decision.v1",
        "milestone": MILESTONE,
        "decision": "S2_R2_SUPERVISION_READY_GOVERNANCE_BLOCKED",
        "training_authorized": False,
        "long_training_command_emitted": False,
        "new_negative_capture_required": False,
        "minimum_new_positive_validation": dataset[
            "minimum_new_data_after_governance_resolution"
        ]["positive_capture"],
        "next_action": (
            "PROJECT_LEAD_SIGNER_SPLIT_ATTESTATION_AND_INDEPENDENT_POSITIVE_"
            "VALIDATION_ROLE_FREEZE"
        ),
        "protected_test_accessed": False,
    }
    atomic_json(OUT / "final_decision.json", decision)
    write_report(baseline, dataset, training)
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("finalize-readiness",))
    args = parser.parse_args()
    if args.command == "finalize-readiness":
        print(json.dumps(run(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
