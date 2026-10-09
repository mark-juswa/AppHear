"""Freeze the read-only P4-A2 fresh-evidence audit.

This utility never fits or evaluates a rescue rule.  It inventories evidence that is
independent of P4-A and emits explicit blocked placeholders when no fresh governed
frame-level anatomical visibility evaluation exists.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = (
    ROOT
    / "artifacts"
    / "recognition_upgrade"
    / "perception_backend_replacement"
    / "p4a2_high_recall_eligibility_rescue_01"
)
P4A = (
    ROOT
    / "artifacts"
    / "recognition_upgrade"
    / "perception_backend_replacement"
    / "p4a_dwpose_presence_eligibility_01"
)
P3 = (
    ROOT
    / "artifacts"
    / "recognition_upgrade"
    / "perception_backend_replacement"
    / "p3_dwpose_temporal_usability_01"
)
P2 = (
    ROOT
    / "artifacts"
    / "recognition_upgrade"
    / "perception_backend_replacement"
    / "p2a_dwpose_l_linux_01"
)
A1 = ROOT / "artifacts" / "recognition_upgrade" / "a1_independent_clock" / "signing_sentinel_01"
PRODUCT = ROOT / "artifacts" / "recognition_upgrade" / "product_core_data_readiness"


INVENTORY_FIELDS = [
    "record_type",
    "source_family",
    "sequence_id",
    "signer_id",
    "gloss",
    "frame_count",
    "visible_left_right_truth",
    "zero_hand_rest_truth",
    "leaving_entry_truth",
    "blur_occlusion_truth",
    "one_two_hand_composition",
    "dwpose_native_outputs_exist",
    "rgb_accessible",
    "prior_human_review",
    "fresh_vs_p4a",
    "p4a2_role_status",
    "restriction_or_limitation",
    "source_path",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bool_text(value: bool) -> str:
    return "yes" if value else "no"


def collect_phone_inventory() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    used = {
        row["sequence_id"].removeprefix("A2__") for row in read_csv(P4A / "p4a_split_manifest.csv")
    }
    annotation_paths = [
        ROOT / "artifacts" / "recognition_upgrade" / "ru_d1" / "ru_d1_pilot_01_annotations.csv",
        ROOT
        / "artifacts"
        / "recognition_upgrade"
        / "ru_d2"
        / "ru_d2_targeted_confirmation_01_annotations.csv",
        ROOT
        / "artifacts"
        / "recognition_upgrade"
        / "ru_d2"
        / "ru_d2_today_controlled_closeout_01_annotations.csv",
        ROOT
        / "artifacts"
        / "recognition_upgrade"
        / "ru_d2"
        / "ru_d2_today_controlled_closeout_02_annotations.csv",
        ROOT / "artifacts" / "recognition_upgrade" / "ru_d7" / "phone_bc_01" / "annotations.csv",
        A1 / "annotations.csv",
    ]
    annotated = {
        row["attempt_id"]
        for path in annotation_paths
        for row in read_csv(path)
        if row.get("attempt_id")
    }
    rows: list[dict[str, Any]] = []
    all_attempts = 0
    for directory in sorted((A1 / "phone_bundles").iterdir()):
        metadata_path = directory / "metadata.json"
        if not directory.is_dir() or not metadata_path.exists():
            continue
        all_attempts += 1
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        attempt_id = metadata["attempt_id"]
        if attempt_id in used:
            continue
        evidence_frames = len(list((directory / "evidence").glob("frame_*.jpg")))
        has_span = attempt_id in annotated
        rows.append(
            {
                "record_type": "sequence",
                "source_family": "A1_RU_PHONE_EVIDENCE_UNTOUCHED",
                "sequence_id": attempt_id,
                "signer_id": metadata.get("signer_id", "unknown"),
                "gloss": metadata.get("ground_truth", "unknown"),
                "frame_count": evidence_frames,
                "visible_left_right_truth": "no",
                "zero_hand_rest_truth": (
                    "attempt-span note only; not frame-level truth" if has_span else "no"
                ),
                "leaving_entry_truth": "no direct frame truth",
                "blur_occlusion_truth": "no direct frame truth",
                "one_two_hand_composition": metadata.get("expected_hands", "unknown"),
                "dwpose_native_outputs_exist": "no",
                "rgb_accessible": bool_text(evidence_frames > 0),
                "prior_human_review": (
                    "attempt onset/release/performance span only" if has_span else "none found"
                ),
                "fresh_vs_p4a": "yes",
                "p4a2_role_status": "NEEDS_FRAME_ADJUDICATION",
                "restriction_or_limitation": (
                    "cannot derive anatomical slot truth or exact rest/entry/exit from span label"
                ),
                "source_path": str(directory),
            }
        )
    summary = {
        "all_phone_attempts": all_attempts,
        "p4a_used_attempts": len(used),
        "untouched_attempts": len(rows),
        "untouched_frames": sum(int(row["frame_count"]) for row in rows),
        "untouched_signers": len({row["signer_id"] for row in rows}),
        "span_annotated_untouched": sum("span only" in row["prior_human_review"] for row in rows),
        "composition": dict(Counter(row["one_two_hand_composition"] for row in rows)),
    }
    return rows, summary


def collect_p3_gold() -> list[dict[str, Any]]:
    frame_counts = Counter(
        row["sequence_id"]
        for row in read_csv(P3 / "frozen_frame_manifest.csv")
        if row["cohort"] == "GOLD_MULTI_SIGNER_INTERNAL_ONLY"
    )
    rows = []
    for sequence in read_csv(P3 / "frozen_sequence_manifest.csv"):
        if sequence["cohort"] != "GOLD_MULTI_SIGNER_INTERNAL_ONLY":
            continue
        rows.append(
            {
                "record_type": "sequence",
                "source_family": "P3_GOLD_VIDEO_TEMPORAL_DIAGNOSTIC",
                "sequence_id": sequence["sequence_id"],
                "signer_id": sequence["signer_id"],
                "gloss": sequence["gloss"],
                "frame_count": frame_counts[sequence["sequence_id"]],
                "visible_left_right_truth": "no",
                "zero_hand_rest_truth": "no temporal truth",
                "leaving_entry_truth": "no temporal truth",
                "blur_occlusion_truth": sequence["selection_bucket"],
                "one_two_hand_composition": sequence["expected_hands"],
                "dwpose_native_outputs_exist": "yes",
                "rgb_accessible": "yes",
                "prior_human_review": "one frozen center-frame hand-box label only",
                "fresh_vs_p4a": "yes",
                "p4a2_role_status": "NEEDS_FRAME_ADJUDICATION",
                "restriction_or_limitation": (
                    "center-frame truth cannot be propagated to adjacent temporal frames"
                ),
                "source_path": sequence["source_sequence_id"],
            }
        )
    return rows


def collect_p2_static() -> list[dict[str, Any]]:
    p0 = read_csv(
        ROOT
        / "artifacts"
        / "recognition_upgrade"
        / "perception_backend_replacement"
        / "p0_rtmdet_detector_01"
        / "p0_input_manifest.csv"
    )
    positive_meta = {row["sample_id"]: row for row in p0 if row["kind"] == "positive"}
    rows = []
    for item in read_csv(P2 / "frozen_input_manifest_350.csv"):
        positive = item["benchmark_type"] == "POSITIVE_GOLD"
        metadata = positive_meta.get(item["sample_id"], {})
        gold_count = int(metadata.get("gold_hand_count", "0")) if positive else 0
        rows.append(
            {
                "record_type": "isolated_frame",
                "source_family": item["benchmark_type"],
                "sequence_id": item["sample_id"],
                "signer_id": metadata.get("participant_id", "source-governed"),
                "gloss": metadata.get("clip_id", "zero-hand image"),
                "frame_count": 1,
                "visible_left_right_truth": (
                    "hand boxes without anatomical side" if positive and gold_count else "no"
                ),
                "zero_hand_rest_truth": (
                    "human ZERO_HAND"
                    if not positive
                    else ("human zero-visible frame" if not gold_count else "no")
                ),
                "leaving_entry_truth": "not available",
                "blur_occlusion_truth": "positive hand tags only" if positive else "not available",
                "one_two_hand_composition": str(gold_count) if positive else "zero",
                "dwpose_native_outputs_exist": "yes",
                "rgb_accessible": bool_text(Path(item["source_path_original"]).exists()),
                "prior_human_review": (
                    "frozen hand boxes/visibility" if positive else "frozen ZERO_HAND truth"
                ),
                "fresh_vs_p4a": "yes",
                "p4a2_role_status": (
                    "STATIC_SUPPLEMENT_ONLY" if positive else "STATIC_ZERO_CONTROL_ONLY"
                ),
                "restriction_or_limitation": (
                    "no consecutive frames, rest semantics, entry/exit, or anatomical slot truth"
                ),
                "source_path": item["source_path_original"],
            }
        )
    return rows


def reviewed_video_rows(path: Path, family: str, review_basis: str) -> list[dict[str, Any]]:
    rows = []
    for item in read_csv(path):
        video_path = item.get("raw_video_path", "")
        rows.append(
            {
                "record_type": "sequence",
                "source_family": family,
                "sequence_id": item.get("row_id") or item.get("sample_id") or Path(video_path).stem,
                "signer_id": item.get("signer_id", "unknown"),
                "gloss": item.get("canonical_gloss") or item.get("oov_label") or "negative-context",
                "frame_count": item.get("frame_count", "unknown"),
                "visible_left_right_truth": "no; clip-level hand_visible only",
                "zero_hand_rest_truth": "no direct frame truth",
                "leaving_entry_truth": "no direct frame truth",
                "blur_occlusion_truth": item.get("quality_warnings", "not reviewed per frame"),
                "one_two_hand_composition": "unknown per frame",
                "dwpose_native_outputs_exist": "no",
                "rgb_accessible": bool_text(bool(video_path) and Path(video_path).exists()),
                "prior_human_review": review_basis,
                "fresh_vs_p4a": "yes",
                "p4a2_role_status": "NEEDS_FRAME_ADJUDICATION",
                "restriction_or_limitation": (
                    "video-level acceptance/hand-visible field cannot become per-frame "
                    "anatomical truth"
                ),
                "source_path": video_path,
            }
        )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    immutable = {
        "p4a_eligibility_truth.csv": (
            "e60557d700374fbbd95c29aabc35bec94f7b835c0a51ccab5a3f73c0707ff72e"
        ),
        "p4a_split_manifest.csv": (
            "09e1325d20d15788af6a305a5d5980fe796bcb568fe4fd9929d77ac66b46e9bb"
        ),
        "p4a_selected_model.json": (
            "4b0aaf87f1ecad89a4fe0634ced694446d6d295d6d2db1e4382db77576d64fd6"
        ),
        "p4a_feature_manifest.json": (
            "09af20ec781526e19ccf3d857044d834e9364347c255e2065231b0a3424fa84a"
        ),
        "p4a_holdout_predictions.csv": (
            "2cfe1c06cf6c30dbf2f2a5e331e7852bb36e5b5de31081cb1ef9a358ed26d91f"
        ),
    }
    for name, expected in immutable.items():
        actual = sha256(P4A / name)
        if actual != expected:
            raise RuntimeError(f"immutable P4-A hash mismatch for {name}: {actual}")

    inventory, phone_summary = collect_phone_inventory()
    inventory.extend(collect_p3_gold())
    inventory.extend(collect_p2_static())
    inventory.extend(
        reviewed_video_rows(
            PRODUCT / "e6_product_core_review_01" / "review_manifest.csv",
            "E6_PRODUCT_CORE_VIDEO_REVIEW",
            "direct human whole-video review; not frame anatomical review",
        )
    )
    inventory.extend(
        reviewed_video_rows(
            PRODUCT / "e6_collection_spot_review_01" / "review_manifest.csv",
            "E6_COLLECTION_SPOT_REVIEW",
            "direct human whole-video spot review; not frame anatomical review",
        )
    )
    inventory.extend(
        reviewed_video_rows(
            PRODUCT / "e6_negative_upload_review_01" / "source_manifest_snapshot.csv",
            "E6_NEGATIVE_UPLOAD_PROVISIONAL_560",
            "54-row batch spot review governs 560 provisional rows; not per-frame truth",
        )
    )
    inventory.sort(key=lambda row: (row["source_family"], row["sequence_id"]))
    write_csv(OUT / "p4a2_fresh_evidence_inventory.csv", inventory, INVENTORY_FIELDS)

    # Required artifacts are explicit blocked placeholders, not fabricated experiment results.
    write_csv(
        OUT / "p4a2_split_manifest.csv",
        [],
        ["sequence_id", "split", "split_seed", "status", "reason"],
    )
    write_json(
        OUT / "p4a2_rescue_feature_manifest.json",
        {
            "status": "BLOCKED_BEFORE_FEATURE_FREEZE",
            "r1_features": [],
            "r2_features": [],
            "reason": (
                "no fresh per-frame anatomical visibility truth supports "
                "development/validation/final evaluation"
            ),
        },
    )
    write_json(
        OUT / "p4a2_e2_baseline_results.json",
        {
            "status": "NOT_EVALUATED_ON_FRESH_FINAL_EVIDENCE",
            "historical_diagnostic_only": {
                "visible_recall": {"numerator": 76, "denominator": 79},
                "zero_hand_false_presence": {"numerator": 2, "denominator": 75},
                "rest_false_presence": {"numerator": 0, "denominator": 63},
                "complete_two_hand_retention": {"numerator": 24, "denominator": 24},
            },
            "p4a_decision_unchanged": "ELIGIBILITY_IMPROVED_BUT_GATES_FAILED",
        },
    )
    write_csv(
        OUT / "p4a2_candidate_comparison.csv",
        [
            {
                "candidate": "R1_HIGH_CONFIDENCE_STATIC_RESCUE",
                "status": "NOT_RUN",
                "reason": "fresh truth unavailable",
            },
            {
                "candidate": "R2_CAUSAL_ONE_FRAME_CONTINUITY_RESCUE",
                "status": "NOT_ACTIVATED",
                "reason": "R1 not evaluated",
            },
        ],
        ["candidate", "status", "reason"],
    )
    prediction_fields = [
        "sequence_id",
        "frame_id",
        "anatomical_side",
        "truth",
        "e2_prediction",
        "rescue_prediction",
        "status",
    ]
    write_csv(OUT / "p4a2_final_evaluation_predictions.csv", [], prediction_fields)
    write_csv(OUT / "p4a2_rescued_visible_cases.csv", [], prediction_fields)
    write_csv(OUT / "p4a2_new_false_positive_cases.csv", [], prediction_fields)
    write_csv(
        OUT / "p4a2_leaving_entry_cases.csv",
        [],
        prediction_fields + ["entry", "leaving", "rescue_duration_frames"],
    )
    write_json(
        OUT / "p4a2_selected_rescue_rule.json",
        {
            "status": "NOT_SELECTED",
            "selected_rescue": None,
            "r2_activated": False,
            "reason": "P4A2 blocked before fitting",
        },
    )

    counts = Counter(row["source_family"] for row in inventory)
    summary = {
        "status": "P4A2_BLOCKED",
        "classification": "INSUFFICIENT_FRESH_EVIDENCE",
        "fresh_untouched_final_evaluation_available": False,
        "inventory_rows": len(inventory),
        "inventory_by_source": dict(sorted(counts.items())),
        "phone_candidate_summary": phone_summary,
        "direct_frame_anatomical_truth_fresh_sequences": 0,
        "r1_run": False,
        "r2_activated": False,
        "p4b_started": False,
        "new_recording_justified_now": False,
        "next_requirement": "bounded frame-level human adjudication of existing RGB",
    }
    write_json(OUT / "p4a2_blocked_result.json", summary)

    report = f"""# P4-A2 High-Recall Eligibility Rescue Result

Status: `P4A2_BLOCKED`  
Classification: `INSUFFICIENT_FRESH_EVIDENCE`  
Historical P4-A decision: `ELIGIBILITY_IMPROVED_BUT_GATES_FAILED` (unchanged)

## Frozen-history verification

The P4-A truth, split, selected E2 coefficients, feature normalization, and holdout predictions
match their frozen SHA-256 values. The old P4-A holdout remains
`HISTORICAL_DIAGNOSTIC_ONLY`: E2 achieved 76/79 visible recall, 2/75 zero-hand false presence,
0/63 rest false presence, and 24/24 complete two-hand retention. None of those rows was reused
for fitting, selection, or a fresh success claim.

## Untouched evidence inventory

The detailed inventory contains {len(inventory):,} rows across the audited sources. The most useful
temporal pool is {phone_summary["untouched_attempts"]} untouched phone attempts from
{phone_summary["untouched_signers"]} governed signer IDs with {phone_summary["untouched_frames"]:,}
saved RGB frames. Of these, {phone_summary["span_annotated_untouched"]} have human attempt-level
onset/release/performance spans. Those spans do **not** say which anatomical hand is visible on
each frame and cannot establish exact rest, entry, leaving, blur, or occlusion truth.

The 12 untouched P3 gold-video diagnostic sequences contribute 202 consecutive frames from 12
additional signers and already have native DWPose output, but only one center frame per source
video has human hand-box truth. That truth cannot be propagated to neighboring frames.

The P2 package provides 150 frozen positive/zero center images and 200 NEGATIVE_GOLD_V1 images
with native DWPose output. They are useful static controls but cannot satisfy the mandatory
temporal rest/entry/leaving evaluation. The E6 product-core and negative-capture reviews provide
abundant accessible videos, but their `hand_visible` decisions are clip/batch level rather than
per-frame anatomical-side truth.

All 21 A2 sequences carrying direct frame-level left/right visibility truth were used by P4-A.
The A2-0 and A2-1R annotation files are byte-identical 551-row copies, and A2-2R is a subset of
the same evidence—not fresh data.

## Why fitting stopped

There are zero untouched sequences with the complete truth required for a defensible P4-A2 final
evaluation: per-frame anatomical left/right visibility plus zero/rest and entry/leaving labels.
Consequently no train/validation/final split can be frozen without inventing labels, and R1/R2
cannot be selected fairly. The static gold and negative sets cannot replace the required temporal
test. E2 was not refit, R1 was not designed from failures, R2 was not activated, and the historical
holdout was not reused.

## Smallest evidence repair

No new recording is justified yet. Prepare one blinded frame-adjudication package from existing
RGB, targeting approximately 28 sequences and no more than about 600 frames:

- all 12 P3 gold temporal diagnostic sequences (202 frames, 12 signers; native DWPose already
  frozen), balanced across five one-hand and seven two-hand clips and the existing clean/blur/
  occlusion/edge/partial buckets;
- 16 untouched phone attempts, sampled by a fixed timing-only rule at up to 24 frames per attempt:
  eight signer-01 attempts for development/validation and eight withheld-phone attempts for the
  fresh signer-separated evaluation; include all three untouched withheld one-hand attempts;
- review physical `visible_left`, `visible_right`, zero-hand/rest, entering, leaving, blur,
  occlusion, crossing/contact, and human-rated clear/weak visibility. Do not show E2/DWPose/
  MediaPipe outputs.

Before model work, require the reviewed package to yield at least 120 visible-hand observations,
70 one-hand visible observations, 100 zero-hand frames, 80 explicit-rest frames, 25 entry/leaving
frames, and 30 complete two-hand control frames. Freeze sequence/signer splits only after these
non-model semantic counts are known. If the yields are short, request only the exact annotation
top-up; do not record automatically.

## Decision

`INSUFFICIENT_FRESH_EVIDENCE`

This is an evidence/split blocker, not a rescue-architecture failure. No rescue parameters or
features were fitted, no DWPose inference was rerun, and no model, Android, S4-S7, S6, recognition,
Sapiens, z-value, or P4-B work occurred.
"""
    (OUT / "P4A2_HIGH_RECALL_ELIGIBILITY_RESCUE_RESULT.md").write_text(report, encoding="utf-8")

    manifest_files = [
        path
        for path in sorted(OUT.iterdir())
        if path.is_file() and path.name != "provenance_hash_manifest.json"
    ]
    write_json(
        OUT / "provenance_hash_manifest.json",
        {
            "input_hashes": immutable,
            "output_files": [
                {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
                for path in manifest_files
            ],
            "audit_script": {
                "path": str(Path(__file__).relative_to(ROOT)),
                "sha256": sha256(Path(__file__)),
            },
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
