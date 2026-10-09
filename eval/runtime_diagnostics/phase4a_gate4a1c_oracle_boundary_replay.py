"""Freeze and evaluate Gate 4A-1C oracle temporal boundaries.

The ``lock`` phase reads only retained raw-v1 evidence and a human-authored draft. It never loads
recognizer outputs or a model. The ``replay`` phase refuses to run unless the exact frozen bounds
SHA-256 is supplied, then recomputes Recognition V2 from each trimmed raw sequence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import fields
from pathlib import Path
from typing import Any

import numpy as np

from eval.runtime_diagnostics.finalize_phase4a_gate4a1 import (
    PHONE_COMPLETED_FPS,
    load_raw,
)
from pipeline.perception_vnext.governance import VOCAB_MANIFEST
from pipeline.perception_vnext.recognition_schema import RawSequence
from pipeline.perception_vnext.recognition_schema_v2 import temporal_view_v2

ROOT = Path(__file__).resolve().parents[2]
MILESTONE = "PHASE_4A_GATE_4A1C_ORACLE_TEMPORAL_BOUNDARY_REPLAY_01"
SOURCE_SESSION = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "phase4a_gate4a1b_controlled_live_input_recovery_01/session_20260915T065635Z"
)
OUTPUT = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "phase4a_gate4a1c_oracle_temporal_boundary_replay_01"
)
DRAFT = OUTPUT / "oracle_bounds_draft.json"
BOUNDS = OUTPUT / "oracle_bounds.json"
CHECKPOINT = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "tcn_v2_run_01/best.keras"
)
EXPECTED_CHECKPOINT_SHA = "8107accbc621ae5652766fec80d314fe8dc9f94ba0d0548a6aef80ed91729340"
FROZEN = {
    "recognition_v2_kt": (
        ROOT / "android/app/src/debug/java/com/example/apphear/perceptionvnext/RecognitionV2.kt",
        "0a5fd969c574f3077060e75bcf697390e322da7e87e870da50b547714ba39699",
    ),
    "tflite": (
        ROOT
        / "android/app/src/debug/assets/phase4a_gate2_recognizer_parity"
        / "ordinary_v2_tcn_fp32.tflite",
        "1ccf0afa9af9aa602aa0de33c9635f5cffd7feec7d9b4e32382bc5e3fa02880c",
    ),
    "vocabulary": (
        VOCAB_MANIFEST,
        "a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b",
    ),
}
EXPECTED = {
    "attempt_001": (80, "HELLO"),
    "attempt_002": (80, "HELLO"),
    "attempt_003": (8, "AT"),
    "attempt_004": (8, "AT"),
    "attempt_005": (83, "HOME"),
    "attempt_006": (83, "HOME"),
    "attempt_007": (179, "STREET"),
    "attempt_008": (179, "STREET"),
    "attempt_009": (183, "TABLE"),
    "attempt_010": (183, "TABLE"),
}
CONFIDENCE = {"HIGH", "MEDIUM", "LOW", "BOUNDARY_UNCERTAIN"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def verify_frozen() -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name, (path, expected) in FROZEN.items():
        actual = sha256(path)
        values[name] = {"path": str(path), "expected": expected, "actual": actual}
        if actual != expected:
            raise RuntimeError(f"GATE4A1C_FROZEN_IDENTITY_FAILURE:{name}:{actual}")
    checkpoint = sha256(CHECKPOINT)
    if checkpoint != EXPECTED_CHECKPOINT_SHA:
        raise RuntimeError(f"GATE4A1C_CHECKPOINT_IDENTITY_FAILURE:{checkpoint}")
    values["checkpoint"] = {
        "path": str(CHECKPOINT),
        "expected": EXPECTED_CHECKPOINT_SHA,
        "actual": checkpoint,
    }
    return values


def lock_bounds() -> dict[str, Any]:
    """Finalize/hash boundaries without opening attempt predictions or loading the recognizer."""

    identities = verify_frozen()
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    if draft.get("milestone") != MILESTONE or draft.get("index_base") != "zero_based_inclusive":
        raise RuntimeError("GATE4A1C_DRAFT_CONTRACT_FAILURE")
    rows = draft.get("bounds", [])
    if {row["attempt_id"] for row in rows} != set(EXPECTED):
        raise RuntimeError("GATE4A1C_DRAFT_POPULATION_FAILURE")

    finalized: list[dict[str, Any]] = []
    confidence_counts = {key: 0 for key in ("HIGH", "MEDIUM", "LOW", "BOUNDARY_UNCERTAIN")}
    for draft_row in sorted(rows, key=lambda row: row["attempt_id"]):
        attempt = draft_row["attempt_id"]
        expected_id, expected_gloss = EXPECTED[attempt]
        if (
            int(draft_row["expected_class_id"]) != expected_id
            or draft_row["expected_gloss"] != expected_gloss
        ):
            raise RuntimeError(f"GATE4A1C_EXPECTED_IDENTITY_FAILURE:{attempt}")
        confidence = draft_row["annotation_confidence"]
        if confidence not in CONFIDENCE:
            raise RuntimeError(f"GATE4A1C_CONFIDENCE_FAILURE:{attempt}")
        raw, _ = load_raw(SOURCE_SESSION / attempt / "raw_v1.json")
        count = len(raw.frame_index)
        start = int(draft_row["oracle_start_index"])
        end = int(draft_row["oracle_end_index"])
        if not (0 <= start <= end < count):
            raise RuntimeError(f"GATE4A1C_BOUNDARY_RANGE_FAILURE:{attempt}")
        padded_start = max(0, start - 1)
        padded_end = min(count - 1, end + 1)
        row = {
            **draft_row,
            "original_observation_count": count,
            "padded_start_index": padded_start,
            "padded_end_index": padded_end,
            "retained_observation_count": padded_end - padded_start + 1,
            "original_sequence_duration_ms": float(raw.timestamp_ms[-1] - raw.timestamp_ms[0]),
            "annotated_sign_duration_ms": float(raw.timestamp_ms[end] - raw.timestamp_ms[start]),
            "trimmed_sequence_duration_ms": float(
                raw.timestamp_ms[padded_end] - raw.timestamp_ms[padded_start]
            ),
            "safety_margin_rule": "one accepted raw observation before and after when available",
        }
        finalized.append(row)
        confidence_counts[confidence] += 1

    sufficient = confidence_counts["HIGH"] + confidence_counts["MEDIUM"] >= 8
    result = {
        "milestone": MILESTONE,
        "source_session": str(SOURCE_SESSION),
        "index_base": "zero_based_inclusive",
        "boundary_selection_blinding": (
            "retained RGB/raw trajectory and exact TRAIN motion reference only; no recognizer "
            "probability, rank, Top-1, or Top-5 used"
        ),
        "frozen_identity": identities,
        "confidence_summary": confidence_counts,
        "primary_conclusion_allowed": sufficient,
        "bounds": finalized,
        "dev_accessed": False,
        "protected_test_accessed": False,
        "training_executed": False,
    }
    write_json(BOUNDS, result)
    bounds_sha = sha256(BOUNDS)
    (OUTPUT / "oracle_bounds.sha256").write_text(
        f"{bounds_sha}  oracle_bounds.json\n", encoding="ascii"
    )
    print(json.dumps({"status": "LOCKED", "sha256": bounds_sha, "confidence": confidence_counts}))
    return result


def subset_raw(raw: RawSequence, start: int, end: int) -> RawSequence:
    values: dict[str, Any] = {"metadata": dict(raw.metadata)}
    for field in fields(RawSequence):
        if field.name != "metadata":
            values[field.name] = np.asarray(getattr(raw, field.name))[start : end + 1].copy()
    subset = RawSequence(**values)
    subset.validate()
    return subset


def inference_row(model: Any, raw: RawSequence, expected: int) -> dict[str, Any]:
    view = temporal_view_v2(
        raw,
        condition="dense",
        phone_completed_fps=PHONE_COMPLETED_FPS,
    )
    output = (
        model([view["features"][None].astype(np.float32), view["mask"][None]], training=False)
        .numpy()[0]
        .astype(np.float32)
    )
    order = np.argsort(-output, kind="stable")
    top = order[:5].astype(int).tolist()
    return {
        "observation_count": int(np.sum(view["mask"])),
        "source_observation_count": len(raw.frame_index),
        "duration_ms": float(raw.timestamp_ms[-1] - raw.timestamp_ms[0]),
        "top1_class_id": int(top[0]),
        "top1_probability": float(output[top[0]]),
        "top5_class_ids": top,
        "expected_probability": float(output[expected]),
        "expected_rank": int(np.flatnonzero(order == expected)[0]) + 1,
        "expected_in_top5": expected in top,
        "body_available_rate": float(np.mean(raw.body_available)),
    }


def replay(bounds_sha: str) -> dict[str, Any]:
    identities = verify_frozen()
    actual_bounds_sha = sha256(BOUNDS)
    if bounds_sha.lower() != actual_bounds_sha:
        raise RuntimeError(f"GATE4A1C_BOUNDS_IDENTITY_FAILURE:{actual_bounds_sha}")
    bounds = json.loads(BOUNDS.read_text(encoding="utf-8"))
    confidence = bounds["confidence_summary"]
    if confidence["HIGH"] + confidence["MEDIUM"] < 8:
        result = {
            "milestone": MILESTONE,
            "status": "ORACLE_BOUNDARY_EVIDENCE_INSUFFICIENT",
            "oracle_bounds_sha256": actual_bounds_sha,
            "confidence_summary": confidence,
            "candidate01_modified": False,
            "v2_modified": False,
            "model_modified": False,
            "training_executed": False,
            "dev_accessed": False,
            "protected_test_accessed": False,
        }
        write_json(OUTPUT / "oracle_boundary_replay_result.json", result)
        return result

    import tensorflow as tf

    model = tf.keras.models.load_model(CHECKPOINT, compile=False, safe_mode=True)
    vocab_map = json.loads(VOCAB_MANIFEST.read_text(encoding="utf-8"))
    glosses = [gloss for gloss, index in sorted(vocab_map.items(), key=lambda pair: pair[1])]
    rows: list[dict[str, Any]] = []
    for bound in bounds["bounds"]:
        attempt = bound["attempt_id"]
        expected = int(bound["expected_class_id"])
        raw, _ = load_raw(SOURCE_SESSION / attempt / "raw_v1.json")
        trimmed = subset_raw(raw, int(bound["padded_start_index"]), int(bound["padded_end_index"]))
        full = inference_row(model, raw, expected)
        oracle = inference_row(model, trimmed, expected)
        row = {
            "attempt_id": attempt,
            "expected_class_id": expected,
            "expected_gloss": bound["expected_gloss"],
            "annotation_confidence": bound["annotation_confidence"],
            "oracle_start_index": bound["oracle_start_index"],
            "oracle_end_index": bound["oracle_end_index"],
            "padded_start_index": bound["padded_start_index"],
            "padded_end_index": bound["padded_end_index"],
            "full": {**full, "top1_gloss": glosses[full["top1_class_id"]]},
            "oracle": {**oracle, "top1_gloss": glosses[oracle["top1_class_id"]]},
            "change": {
                "top1_changed": full["top1_class_id"] != oracle["top1_class_id"],
                "became_correct": full["top1_class_id"] != expected
                and oracle["top1_class_id"] == expected,
                "became_incorrect": full["top1_class_id"] == expected
                and oracle["top1_class_id"] != expected,
                "expected_rank_change_after_minus_before": oracle["expected_rank"]
                - full["expected_rank"],
                "expected_probability_change": oracle["expected_probability"]
                - full["expected_probability"],
            },
        }
        rows.append(row)

    full_top1 = sum(row["full"]["top1_class_id"] == row["expected_class_id"] for row in rows)
    oracle_top1 = sum(row["oracle"]["top1_class_id"] == row["expected_class_id"] for row in rows)
    full_top5 = sum(row["full"]["expected_in_top5"] for row in rows)
    oracle_top5 = sum(row["oracle"]["expected_in_top5"] for row in rows)
    if (full_top1, full_top5) != (2, 5):
        raise RuntimeError(f"GATE4A1C_BASELINE_IDENTITY_FAILURE:{full_top1}:{full_top5}")

    full_probs = [row["full"]["expected_probability"] for row in rows]
    oracle_probs = [row["oracle"]["expected_probability"] for row in rows]
    full_ranks = [row["full"]["expected_rank"] for row in rows]
    oracle_ranks = [row["oracle"]["expected_rank"] for row in rows]
    median_prob_before = float(np.median(full_probs))
    median_prob_after = float(np.median(oracle_probs))
    median_rank_before = float(np.median(full_ranks))
    median_rank_after = float(np.median(oracle_ranks))
    primary = (
        oracle_top1 - full_top1 >= 3 or oracle_top5 - full_top5 >= 3
    ) and median_prob_after >= median_prob_before
    helpful = (
        oracle_top1 > full_top1
        or oracle_top5 > full_top5
        or median_prob_after > median_prob_before
        or median_rank_after < median_rank_before
    )
    if primary:
        classification = "TEMPORAL_BOUNDARY_PRIMARY_EFFECT_SUPPORTED"
        next_boundary = (
            "Project-lead review of automatic isolated-sign active-window extraction "
            "plus a framing-readiness guard before V2."
        )
    elif helpful:
        classification = "TEMPORAL_BOUNDARY_HELPFUL_BUT_NOT_PRIMARY"
        next_boundary = (
            "Project-lead review: retain segmentation as required product work, then "
            "return primary focus to Phase 3 generalization."
        )
    else:
        classification = "TEMPORAL_BOUNDARY_EFFECT_NOT_SUPPORTED"
        next_boundary = (
            "Close the Phase-4 causal branch and return primary focus to Phase 3 "
            "signer/generalization; automatic segmentation remains later product work."
        )

    result = {
        "milestone": MILESTONE,
        "status": "PASS",
        "frozen_identity": identities,
        "source_session": str(SOURCE_SESSION),
        "oracle_bounds_path": str(BOUNDS),
        "oracle_bounds_sha256": actual_bounds_sha,
        "confidence_summary": confidence,
        "attempts": rows,
        "baseline": {"top1_correct": full_top1, "expected_in_top5": full_top5},
        "oracle_result": {"top1_correct": oracle_top1, "expected_in_top5": oracle_top5},
        "expected_class": {
            "median_probability_before": median_prob_before,
            "median_probability_after": median_prob_after,
            "median_rank_before": median_rank_before,
            "median_rank_after": median_rank_after,
        },
        "became_correct": [row["attempt_id"] for row in rows if row["change"]["became_correct"]],
        "became_wrong": [row["attempt_id"] for row in rows if row["change"]["became_incorrect"]],
        "unchanged_correct": [
            row["attempt_id"]
            for row in rows
            if row["full"]["top1_class_id"] == row["expected_class_id"]
            and row["oracle"]["top1_class_id"] == row["expected_class_id"]
        ],
        "unchanged_wrong": [
            row["attempt_id"]
            for row in rows
            if row["full"]["top1_class_id"] != row["expected_class_id"]
            and row["oracle"]["top1_class_id"] != row["expected_class_id"]
        ],
        "final_classification": classification,
        "next_recommended_engineering_boundary": next_boundary,
        "candidate01_modified": False,
        "v2_modified": False,
        "model_modified": False,
        "training_executed": False,
        "dev_accessed": False,
        "protected_test_accessed": False,
    }
    write_json(OUTPUT / "oracle_boundary_replay_result.json", result)

    with (OUTPUT / "full_vs_oracle.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "attempt",
                "expected",
                "confidence",
                "full_obs",
                "full_duration_ms",
                "full_top1",
                "full_top1_probability",
                "full_expected_probability",
                "full_expected_rank",
                "full_expected_top5",
                "oracle_obs",
                "oracle_duration_ms",
                "oracle_top1",
                "oracle_top1_probability",
                "oracle_expected_probability",
                "oracle_expected_rank",
                "oracle_expected_top5",
                "full_body_available",
                "oracle_body_available",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["attempt_id"],
                    row["expected_gloss"],
                    row["annotation_confidence"],
                    row["full"]["source_observation_count"],
                    row["full"]["duration_ms"],
                    row["full"]["top1_gloss"],
                    row["full"]["top1_probability"],
                    row["full"]["expected_probability"],
                    row["full"]["expected_rank"],
                    row["full"]["expected_in_top5"],
                    row["oracle"]["source_observation_count"],
                    row["oracle"]["duration_ms"],
                    row["oracle"]["top1_gloss"],
                    row["oracle"]["top1_probability"],
                    row["oracle"]["expected_probability"],
                    row["oracle"]["expected_rank"],
                    row["oracle"]["expected_in_top5"],
                    row["full"]["body_available_rate"],
                    row["oracle"]["body_available_rate"],
                ]
            )

    report = [
        f"# {MILESTONE}",
        "",
        f"Final classification: **{classification}**",
        "",
        f"Oracle bounds SHA-256: `{actual_bounds_sha}`",
        "",
        (
            "| Attempt | Expected | Confidence | Full obs/duration | Full Top-1 | "
            "Full rank/P | Oracle obs/duration | Oracle Top-1 | Oracle rank/P |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        report.append(
            f"| {row['attempt_id']} | {row['expected_gloss']} | {row['annotation_confidence']} | "
            f"{row['full']['source_observation_count']}/"
            f"{row['full']['duration_ms'] / 1000:.2f}s | "
            f"{row['full']['top1_gloss']} | {row['full']['expected_rank']}/"
            f"{row['full']['expected_probability']:.4f} | "
            f"{row['oracle']['source_observation_count']}/"
            f"{row['oracle']['duration_ms'] / 1000:.2f}s | "
            f"{row['oracle']['top1_gloss']} | {row['oracle']['expected_rank']}/"
            f"{row['oracle']['expected_probability']:.4f} |"
        )
    report.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- Top-1: `{full_top1}/10` → `{oracle_top1}/10`",
            f"- Expected in Top-5: `{full_top5}/10` → `{oracle_top5}/10`",
            (
                f"- Median expected probability: `{median_prob_before:.6f}` "
                f"→ `{median_prob_after:.6f}`"
            ),
            f"- Median expected rank: `{median_rank_before:.1f}` → `{median_rank_after:.1f}`",
            "",
            f"Next boundary: {next_boundary}",
            "",
            "Candidate01 modified: **NO**  ",
            "Recognition V2 modified: **NO**  ",
            "Model modified: **NO**  ",
            "Training executed: **NO**  ",
            "DEV accessed: **NO**  ",
            "Protected TEST accessed: **NO**",
            "",
        ]
    )
    (OUTPUT / "PHASE4A_GATE4A1C_FINAL_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": classification,
                "top1": [full_top1, oracle_top1],
                "top5": [full_top5, oracle_top5],
            }
        )
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("lock", "replay"))
    parser.add_argument("--bounds-sha256")
    args = parser.parse_args()
    if args.command == "lock":
        lock_bounds()
    else:
        if not args.bounds_sha256:
            parser.error("--bounds-sha256 is required for replay")
        replay(args.bounds_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
