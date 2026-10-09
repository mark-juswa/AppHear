"""Post-freeze Phase-6 FULL vs LEARNED vs human-boundary phone replay."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics.finalize_phase4a_gate4a1 import load_raw  # noqa: E402
from eval.runtime_diagnostics.phase4a_gate4a1c_oracle_boundary_replay import (  # noqa: E402
    BOUNDS,
    CHECKPOINT,
    EXPECTED,
    FROZEN,
    SOURCE_SESSION,
    inference_row,
    subset_raw,
    verify_frozen,
)
from pipeline.perception_vnext.governance import VOCAB_MANIFEST  # noqa: E402

MILESTONE = "PHASE_6_FROZEN_LEARNED_SEGMENTER_END_TO_END_PHONE_REPLAY_01"
BASE = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
)
OUT = BASE / "phase6_frozen_learned_segmenter_phone_replay_01"
HISTORICAL = BASE / (
    "phase4a_gate4a1c_oracle_temporal_boundary_replay_01/"
    "oracle_boundary_replay_result.json"
)
EXPECTED_ORACLE_SHA = "0e6f14f159287ce830b68c4d33edba88dbb6aeef386060b80f79e3fed4a1e41f"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def verify_learned_freeze() -> tuple[dict[str, Any], str]:
    sidecar_path = OUT / "learned_events_frozen.sha256.json"
    event_path = OUT / "learned_events_frozen.json"
    if not sidecar_path.is_file() or not event_path.is_file():
        raise RuntimeError("PHASE6_LEARNED_EVENT_FREEZE_MISSING")
    sidecar = read_json(sidecar_path)
    actual = sha256(event_path)
    if sidecar.get("sha256") != actual or not sidecar.get("immutable_before_comparison"):
        raise RuntimeError("PHASE6_LEARNED_EVENT_FREEZE_IDENTITY_FAILURE")
    events = read_json(event_path)
    if (
        events.get("comparison_inputs_opened") is not False
        or events.get("manual_edits") is not False
    ):
        raise RuntimeError("PHASE6_LEARNED_EVENT_FREEZE_GOVERNANCE_FAILURE")
    event_ids = [row["attempt_id"] for row in events["events"]]
    if event_ids != [f"attempt_{index:03d}" for index in range(1, 11)]:
        raise RuntimeError("PHASE6_LEARNED_EVENT_POPULATION_FAILURE")
    return events, actual


def verify_post_freeze_identities(learned_sha: str) -> dict[str, Any]:
    oracle_sha = sha256(BOUNDS)
    if oracle_sha != EXPECTED_ORACLE_SHA:
        raise RuntimeError(f"PHASE6_FROZEN_IDENTITY_MISMATCH:oracle:{oracle_sha}")
    recognizer = verify_frozen()
    return {
        "schema": "apphear.phase6.oracle_and_recognizer_identity.v1",
        "learned_events_sha256": learned_sha,
        "learned_events_verified_before_opening_comparison_inputs": True,
        "oracle": {
            "path": str(BOUNDS.resolve()),
            "expected_sha256": EXPECTED_ORACLE_SHA,
            "actual_sha256": oracle_sha,
            "match": True,
        },
        "recognizer": recognizer,
        "recognition_path": "PYTHON_RECOGNITION_V2_PLUS_FROZEN_ORDINARY_KERAS_TCN",
    }


def attach_glosses(row: dict[str, Any], glosses: list[str]) -> dict[str, Any]:
    return {
        **row,
        "top1_gloss": glosses[int(row["top1_class_id"])],
        "top5_glosses": [glosses[int(index)] for index in row["top5_class_ids"]],
    }


def recognition_document(condition: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if row.get("inference_executed", True)]
    top1 = sum(row["top1_class_id"] == row["expected_class_id"] for row in valid)
    top5 = sum(row["expected_in_top5"] for row in valid)
    probabilities = [row["expected_probability"] for row in valid]
    ranks = [row["expected_rank"] for row in valid]
    return {
        "schema": "apphear.phase6.phone_recognition_condition.v1",
        "condition": condition,
        "attempt_count": len(rows),
        "inference_count": len(valid),
        "top1_correct": top1,
        "expected_in_top5": top5,
        "median_expected_probability": float(np.median(probabilities)) if probabilities else None,
        "median_expected_rank": float(np.median(ranks)) if ranks else None,
        "attempts": rows,
    }


def reproduce_references(
    model: Any,
    bounds: dict[str, Any],
    glosses: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    full_rows: list[dict[str, Any]] = []
    oracle_rows: list[dict[str, Any]] = []
    for bound in bounds["bounds"]:
        attempt = str(bound["attempt_id"])
        expected_class, expected_gloss = EXPECTED[attempt]
        raw, _ = load_raw(SOURCE_SESSION / attempt / "raw_v1.json")
        oracle_raw = subset_raw(
            raw, int(bound["padded_start_index"]), int(bound["padded_end_index"])
        )
        common = {
            "attempt_id": attempt,
            "expected_class_id": expected_class,
            "expected_gloss": expected_gloss,
            "annotation_confidence": bound["annotation_confidence"],
        }
        full_rows.append(
            {
                **common,
                **attach_glosses(inference_row(model, raw, expected_class), glosses),
            }
        )
        oracle_rows.append(
            {
                **common,
                **attach_glosses(inference_row(model, oracle_raw, expected_class), glosses),
                "start_index": int(bound["padded_start_index"]),
                "end_index": int(bound["padded_end_index"]),
            }
        )
    return recognition_document("FULL", full_rows), recognition_document("ORACLE", oracle_rows)


def validate_reference_reproduction(
    full: dict[str, Any], oracle: dict[str, Any]
) -> dict[str, Any]:
    historical = read_json(HISTORICAL)
    historical_by_id = {row["attempt_id"]: row for row in historical["attempts"]}
    mismatches: list[dict[str, Any]] = []
    for document, key in ((full, "full"), (oracle, "oracle")):
        for row in document["attempts"]:
            reference = historical_by_id[row["attempt_id"]][key]
            for field in ("top1_class_id", "top5_class_ids", "expected_rank", "expected_in_top5"):
                if row[field] != reference[field]:
                    mismatches.append(
                        {
                            "attempt_id": row["attempt_id"],
                            "condition": document["condition"],
                            "field": field,
                            "actual": row[field],
                            "historical": reference[field],
                        }
                    )
            for field in ("expected_probability", "top1_probability"):
                if abs(float(row[field]) - float(reference[field])) > 1e-6:
                    mismatches.append(
                        {
                            "attempt_id": row["attempt_id"],
                            "condition": document["condition"],
                            "field": field,
                            "actual": row[field],
                            "historical": reference[field],
                        }
                    )
    aggregate_match = (
        full["top1_correct"] == 2
        and full["expected_in_top5"] == 5
        and oracle["top1_correct"] == 7
        and oracle["expected_in_top5"] == 8
        and abs(full["median_expected_probability"] - 0.05383858270943165) <= 1e-6
        and full["median_expected_rank"] == 5.0
        and abs(oracle["median_expected_probability"] - 0.5851593613624573) <= 1e-6
        and oracle["median_expected_rank"] == 1.0
    )
    return {
        "status": "PASS" if not mismatches and aggregate_match else "FAIL",
        "attempt_field_mismatches": mismatches,
        "aggregate_match": aggregate_match,
    }


def interval_metrics(
    learned_start: float,
    learned_end: float,
    reference_start: float,
    reference_end: float,
) -> dict[str, Any]:
    learned_duration = max(0.0, learned_end - learned_start)
    reference_duration = max(0.0, reference_end - reference_start)
    intersection = max(
        0.0, min(learned_end, reference_end) - max(learned_start, reference_start)
    )
    union = max(learned_end, reference_end) - min(learned_start, reference_start)
    return {
        "reference_start_ms": reference_start,
        "reference_end_ms": reference_end,
        "start_error_ms": learned_start - reference_start,
        "end_error_ms": learned_end - reference_end,
        "intersection_duration_ms": intersection,
        "reference_interval_recall": intersection / reference_duration
        if reference_duration > 0
        else 0.0,
        "learned_window_precision": intersection / learned_duration
        if learned_duration > 0
        else 0.0,
        "iou": intersection / union if union > 0 else 0.0,
    }


def boundary_comparison(
    learned: dict[str, Any], bounds: dict[str, Any]
) -> dict[str, Any]:
    event_by_id = {row["attempt_id"]: row for row in learned["events"]}
    rows: list[dict[str, Any]] = []
    for bound in bounds["bounds"]:
        attempt = bound["attempt_id"]
        raw, _ = load_raw(SOURCE_SESSION / attempt / "raw_v1.json")
        timestamps = np.asarray(raw.timestamp_ms, np.float64)
        relative = timestamps - timestamps[0]
        event = event_by_id[attempt]
        if not event["event_emitted"]:
            rows.append(
                {
                    "attempt_id": attempt,
                    "annotation_confidence": bound["annotation_confidence"],
                    "event_emitted": False,
                }
            )
            continue
        start_index = int(event["start_index"])
        end_index = int(event["end_index"])
        learned_start = float(relative[start_index])
        learned_end = float(relative[end_index])
        unpadded_start = float(relative[int(bound["oracle_start_index"])])
        unpadded_end = float(relative[int(bound["oracle_end_index"])])
        padded_start = float(relative[int(bound["padded_start_index"])])
        padded_end = float(relative[int(bound["padded_end_index"])])
        learned_duration = learned_end - learned_start
        full_duration = float(relative[-1])
        rows.append(
            {
                "attempt_id": attempt,
                "annotation_confidence": bound["annotation_confidence"],
                "primary_boundary_population": bound["annotation_confidence"] in {"HIGH", "MEDIUM"},
                "event_emitted": True,
                "learned_start_index": start_index,
                "learned_end_index": end_index,
                "learned_start_ms": learned_start,
                "learned_end_ms": learned_end,
                "learned_duration_ms": learned_duration,
                "full_duration_ms": full_duration,
                "full_context_removed_ms": full_duration - learned_duration,
                "full_window_reduction_fraction": 1.0 - learned_duration / full_duration,
                "starts_at_first_phone_observation": start_index == 0,
                "ends_at_final_phone_observation": end_index == len(relative) - 1,
                "unpadded_oracle": {
                    "start_index": int(bound["oracle_start_index"]),
                    "end_index": int(bound["oracle_end_index"]),
                    **interval_metrics(
                        learned_start,
                        learned_end,
                        unpadded_start,
                        unpadded_end,
                    ),
                },
                "padded_oracle": {
                    "start_index": int(bound["padded_start_index"]),
                    "end_index": int(bound["padded_end_index"]),
                    **interval_metrics(
                        learned_start,
                        learned_end,
                        padded_start,
                        padded_end,
                    ),
                },
            }
        )
    primary = [row for row in rows if row.get("primary_boundary_population")]
    emitted = [row for row in rows if row["event_emitted"]]
    primary_recalls = [row["unpadded_oracle"]["reference_interval_recall"] for row in primary]
    mean_reduction = float(
        np.mean([row["full_window_reduction_fraction"] for row in emitted])
    ) if emitted else 0.0
    gates = {
        "events_emitted_10_of_10": len(emitted) == 10,
        "primary_recall_ge_0_80_at_least_8_of_9": sum(value >= 0.80 for value in primary_recalls)
        >= 8,
        "primary_recall_below_0_60_no_more_than_1_of_9": sum(
            value < 0.60 for value in primary_recalls
        )
        <= 1,
        "mean_window_reduction_at_least_0_25": mean_reduction >= 0.25,
    }
    return {
        "schema": "apphear.phase6.learned_oracle_boundary_comparison.v1",
        "attempts": rows,
        "primary_population_count": len(primary),
        "descriptive_low_confidence_count": sum(
            row["annotation_confidence"] == "LOW" for row in rows
        ),
        "events_emitted": len(emitted),
        "primary_unpadded_recall_ge_0_80": sum(value >= 0.80 for value in primary_recalls),
        "primary_unpadded_recall_below_0_60": sum(value < 0.60 for value in primary_recalls),
        "primary_unpadded_recall_distribution": {
            "min": float(np.min(primary_recalls)),
            "median": float(np.median(primary_recalls)),
            "mean": float(np.mean(primary_recalls)),
            "max": float(np.max(primary_recalls)),
        },
        "mean_full_window_reduction_fraction": mean_reduction,
        "events_starting_at_first_observation": sum(
            row.get("starts_at_first_phone_observation", False) for row in emitted
        ),
        "events_ending_at_final_observation": sum(
            row.get("ends_at_final_phone_observation", False) for row in emitted
        ),
        "boundary_transfer_gates": gates,
        "boundary_transfer_supported": all(gates.values()),
    }


def learned_recognition(
    model: Any,
    learned: dict[str, Any],
    bounds: dict[str, Any],
    glosses: list[str],
) -> dict[str, Any]:
    event_by_id = {row["attempt_id"]: row for row in learned["events"]}
    confidence = {row["attempt_id"]: row["annotation_confidence"] for row in bounds["bounds"]}
    rows: list[dict[str, Any]] = []
    for attempt in (f"attempt_{index:03d}" for index in range(1, 11)):
        expected_class, expected_gloss = EXPECTED[attempt]
        event = event_by_id[attempt]
        common = {
            "attempt_id": attempt,
            "expected_class_id": expected_class,
            "expected_gloss": expected_gloss,
            "annotation_confidence": confidence[attempt],
            "start_index": event["start_index"],
            "end_index": event["end_index"],
        }
        if not event["event_emitted"]:
            rows.append({**common, "inference_executed": False})
            continue
        raw, _ = load_raw(SOURCE_SESSION / attempt / "raw_v1.json")
        selected = subset_raw(raw, int(event["start_index"]), int(event["end_index"]))
        inference = attach_glosses(inference_row(model, selected, expected_class), glosses)
        rows.append({**common, "inference_executed": True, **inference})
    return recognition_document("LEARNED", rows)


def correctness(row: dict[str, Any]) -> bool:
    return bool(row.get("inference_executed", True)) and (
        row["top1_class_id"] == row["expected_class_id"]
    )


def three_way_comparison(
    full: dict[str, Any],
    learned: dict[str, Any],
    oracle: dict[str, Any],
    boundaries: dict[str, Any],
) -> dict[str, Any]:
    full_by_id = {row["attempt_id"]: row for row in full["attempts"]}
    learned_by_id = {row["attempt_id"]: row for row in learned["attempts"]}
    oracle_by_id = {row["attempt_id"]: row for row in oracle["attempts"]}
    boundary_by_id = {row["attempt_id"]: row for row in boundaries["attempts"]}
    rows: list[dict[str, Any]] = []
    transitions: defaultdict[str, list[str]] = defaultdict(list)
    for attempt in full_by_id:
        full_row = full_by_id[attempt]
        learned_row = learned_by_id[attempt]
        oracle_row = oracle_by_id[attempt]
        f = correctness(full_row)
        learned_correct = correctness(learned_row)
        o = correctness(oracle_row)
        if not f and learned_correct:
            transitions["FULL_WRONG_TO_LEARNED_CORRECT"].append(attempt)
        if f and not learned_correct:
            transitions["FULL_CORRECT_TO_LEARNED_WRONG"].append(attempt)
        if not learned_correct and o:
            transitions["LEARNED_WRONG_TO_ORACLE_CORRECT"].append(attempt)
        if learned_correct and not o:
            transitions["LEARNED_CORRECT_TO_ORACLE_WRONG"].append(attempt)
        if not f and not learned_correct and o:
            transitions["FULL_WRONG_LEARNED_WRONG_ORACLE_CORRECT"].append(attempt)
        if not f and learned_correct and o:
            transitions["FULL_WRONG_LEARNED_CORRECT_ORACLE_CORRECT"].append(attempt)
        if not f and not learned_correct and not o:
            transitions["FULL_WRONG_LEARNED_WRONG_ORACLE_WRONG"].append(attempt)
        rows.append(
            {
                "attempt_id": attempt,
                "expected_gloss": full_row["expected_gloss"],
                "full_correct": f,
                "learned_correct": learned_correct,
                "oracle_correct": o,
                "full_top1": full_row["top1_gloss"],
                "learned_top1": learned_row.get("top1_gloss"),
                "oracle_top1": oracle_row["top1_gloss"],
                "full_expected_probability": full_row["expected_probability"],
                "learned_expected_probability": learned_row.get("expected_probability"),
                "oracle_expected_probability": oracle_row["expected_probability"],
                "full_expected_rank": full_row["expected_rank"],
                "learned_expected_rank": learned_row.get("expected_rank"),
                "oracle_expected_rank": oracle_row["expected_rank"],
                "learned_unpadded_oracle_recall": boundary_by_id[attempt]
                .get("unpadded_oracle", {})
                .get("reference_interval_recall"),
            }
        )
    required_keys = (
        "FULL_WRONG_TO_LEARNED_CORRECT",
        "FULL_CORRECT_TO_LEARNED_WRONG",
        "LEARNED_WRONG_TO_ORACLE_CORRECT",
        "LEARNED_CORRECT_TO_ORACLE_WRONG",
        "FULL_WRONG_LEARNED_WRONG_ORACLE_CORRECT",
        "FULL_WRONG_LEARNED_CORRECT_ORACLE_CORRECT",
        "FULL_WRONG_LEARNED_WRONG_ORACLE_WRONG",
    )
    return {
        "schema": "apphear.phase6.three_way_recognition_comparison.v1",
        "aggregate": {"FULL": full, "LEARNED": learned, "ORACLE": oracle},
        "transitions": {key: transitions[key] for key in required_keys},
        "attempts": rows,
    }


def recognition_utility_gates(
    full: dict[str, Any], learned: dict[str, Any]
) -> dict[str, Any]:
    by_id = {row["attempt_id"]: row for row in learned["attempts"]}
    improved_rank = learned["median_expected_rank"] < full["median_expected_rank"]
    improved_probability = (
        learned["median_expected_probability"] > full["median_expected_probability"]
    )
    gates = {
        "learned_top1_at_least_4_of_10": learned["top1_correct"] >= 4,
        "both_full_correct_hello_attempts_remain_correct": correctness(by_id["attempt_001"])
        and correctness(by_id["attempt_002"]),
        "learned_expected_top5_at_least_6_of_10": learned["expected_in_top5"] >= 6,
        "median_rank_or_probability_improves": improved_rank or improved_probability,
    }
    return {
        "gates": gates,
        "median_rank_improved": improved_rank,
        "median_probability_improved": improved_probability,
        "recognition_utility_supported": all(gates.values()),
    }


def root_causes(comparison: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in comparison["attempts"]:
        if row["full_correct"] and row["learned_correct"]:
            category = "FULL_CORRECT_PRESERVED"
        elif row["learned_correct"] and row["oracle_correct"]:
            category = "AUTOMATIC_BOUNDARY_RESCUE"
        elif not row["learned_correct"] and row["oracle_correct"]:
            category = "SEGMENTATION_TRANSFER_GAP"
        elif not row["learned_correct"] and not row["oracle_correct"]:
            category = "NOT_FIXED_BY_TEMPORAL_BOUNDARY"
        else:
            category = "LEARNED_WINDOW_DIFFERENTIALLY_HELPFUL"
        contributor = None
        if (
            category == "NOT_FIXED_BY_TEMPORAL_BOUNDARY"
            and (row["learned_unpadded_oracle_recall"] or 0.0) >= 0.80
        ):
            contributor = "RECOGNITION_GENERALIZATION_REMAINS"
        rows.append(
            {
                "attempt_id": row["attempt_id"],
                "expected_gloss": row["expected_gloss"],
                "classification": category,
                "supported_contributor": contributor,
                "learned_unpadded_oracle_recall": row[
                    "learned_unpadded_oracle_recall"
                ],
            }
        )
    return {
        "schema": "apphear.phase6.root_cause_attribution.v1",
        "attempts": rows,
        "counts": dict(Counter(row["classification"] for row in rows)),
        "limits": (
            "No signer, perception, or representation cause is inferred beyond temporal-window "
            "and frozen-recognizer outcomes."
        ),
    }


def write_csv(comparison: dict[str, Any], boundaries: dict[str, Any]) -> None:
    boundary_by_id = {row["attempt_id"]: row for row in boundaries["attempts"]}
    fields = [
        "attempt_id",
        "expected_gloss",
        "annotation_confidence",
        "learned_start_index",
        "learned_end_index",
        "learned_duration_ms",
        "unpadded_oracle_recall",
        "unpadded_oracle_precision",
        "unpadded_oracle_iou",
        "full_top1",
        "learned_top1",
        "oracle_top1",
        "full_expected_probability",
        "learned_expected_probability",
        "oracle_expected_probability",
        "full_expected_rank",
        "learned_expected_rank",
        "oracle_expected_rank",
    ]
    rows = []
    for item in comparison["attempts"]:
        boundary = boundary_by_id[item["attempt_id"]]
        interval = boundary.get("unpadded_oracle", {})
        rows.append(
            {
                **item,
                "annotation_confidence": boundary["annotation_confidence"],
                "learned_start_index": boundary.get("learned_start_index"),
                "learned_end_index": boundary.get("learned_end_index"),
                "learned_duration_ms": boundary.get("learned_duration_ms"),
                "unpadded_oracle_recall": interval.get("reference_interval_recall"),
                "unpadded_oracle_precision": interval.get("learned_window_precision"),
                "unpadded_oracle_iou": interval.get("iou"),
            }
        )
    with (OUT / "per_attempt_comparison.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_report(
    decision: dict[str, Any],
    identities: dict[str, Any],
    boundaries: dict[str, Any],
    full: dict[str, Any],
    learned: dict[str, Any],
    oracle: dict[str, Any],
    comparison: dict[str, Any],
    causes: dict[str, Any],
) -> None:
    diagnostics = read_json(OUT / "sparse_phone_feature_diagnostics.json")
    predictions = read_json(OUT / "per_observation_segmenter_predictions.json")
    cadence = diagnostics["aggregate"]
    state_counts = {
        row["attempt_id"]: dict(
            Counter(observation["argmax_state"] for observation in row["observations"])
        )
        for row in predictions["attempts"]
    }
    report = f"""# Phase 6 Frozen Learned-Segmenter Phone Replay

Milestone: `{MILESTONE}`

## A. Frozen identities

All supplied Phase-5.1T-3 model/config/normalization/feature/decoder identities matched before
inference. Learned-event SHA-256: `{identities['learned_events_sha256']}`. The oracle-boundary,
ordinary V2 Keras checkpoint, vocabulary, TFLite, and historical RecognitionV2.kt identities also
matched after the learned-event freeze.

## B. Phone population and cadence

Exactly attempts 001–010 from `session_20260915T065635Z` were replayed:
`{cadence['observation_count']}`
actual observations, aggregate effective cadence `{cadence['effective_observation_hz']:.3f} Hz`,
and raw dt distribution `{cadence['dt_seconds']}`. No Candidate01 rerun, interpolation, duplication,
upsampling, synthetic frames, or timestamp modification occurred.

## C. Sparse-phone distribution shift

- Normalized dt: `{cadence['normalized_dt_z']}`
- Refined-hand delta: `{cadence['hand_xy_delta_normalized']}`
- ROI delta: `{cadence['hand_roi_delta_normalized']}`
- Body delta: `{cadence['body_xy_delta_normalized']}`

These are explanatory diagnostics only. No clipping, renormalization, model, threshold, or decoder
change was made.

## D–E. State predictions and frozen events

Argmax state counts by attempt (0 PRE, 1 ACTIVE, 2 POST): `{state_counts}`.
The exact frozen decoder emitted `{boundaries['events_emitted']}/10` events. Learned events starting
at the first observation: `{boundaries['events_starting_at_first_observation']}`; ending at the
final observation: `{boundaries['events_ending_at_final_observation']}`.

## F. Learned vs oracle-boundary comparison

On the nine HIGH/MEDIUM attempts, `{boundaries['primary_unpadded_recall_ge_0_80']}/9` achieved
unpadded oracle-interval recall >=0.80 and
`{boundaries['primary_unpadded_recall_below_0_60']}/9` fell below 0.60. Recall distribution:
`{boundaries['primary_unpadded_recall_distribution']}`. Mean full-window reduction was
`{boundaries['mean_full_window_reduction_fraction']:.4f}`. Boundary gates:
`{boundaries['boundary_transfer_gates']}`.

## G–H. FULL and ORACLE reproduction

- FULL: Top-1 `{full['top1_correct']}/10`, expected Top-5 `{full['expected_in_top5']}/10`, median
  expected probability `{full['median_expected_probability']:.9f}`, median rank
  `{full['median_expected_rank']:.1f}`.
- ORACLE: Top-1 `{oracle['top1_correct']}/10`, expected Top-5
  `{oracle['expected_in_top5']}/10`, median expected probability
  `{oracle['median_expected_probability']:.9f}`, median rank
  `{oracle['median_expected_rank']:.1f}`.

The reference reproduction gate passed exactly before learned recognition was interpreted.

## I–K. Three-way recognition and attribution

- LEARNED: Top-1 `{learned['top1_correct']}/10`, expected Top-5
  `{learned['expected_in_top5']}/10`, median expected probability
  `{learned['median_expected_probability']:.9f}`, median rank
  `{learned['median_expected_rank']:.1f}`.
- Transitions: `{comparison['transitions']}`
- Root-cause counts: `{causes['counts']}`
- Per-attempt attribution: `{causes['attempts']}`

## L–M. Transfer and recovery behavior

Phone cadence/delta/missingness evidence is reported without intervention. Events ending at the
final phone observation are the direct bounded indicator of persistent/recovery-as-ACTIVE behavior
under this decoder: `{boundaries['events_ending_at_final_observation']}/10`.

## N. Decoder deployability limitation

The TCN is causal, but the frozen primary-run decoder selects the winning ACTIVE run using the
completed sequence. This is an **offline automatic phone-window replay**, not proof of streaming
Android START/END or SignEvent emission. No Android integration or production-readiness claim is
made.

## O–P. Final evidence classification and stop

Boundary-transfer supported: `{decision['boundary_transfer_supported']}`. Recognition utility
supported: `{decision['recognition_utility_supported']}`.

**`{decision['final_evidence_state']}`**

**`{decision['next_stop_boundary']}`**
"""
    (OUT / "PHASE6_FROZEN_SEGMENTER_PHONE_REPLAY_REPORT.md").write_text(
        report, encoding="utf-8"
    )


def write_source_hashes() -> None:
    files = [
        ROOT / "eval/runtime_diagnostics/phase6_freeze_learned_phone_events.py",
        Path(__file__).resolve(),
        ROOT / "tests/test_phase6_frozen_segmenter_phone_replay.py",
        ROOT / "eval/runtime_diagnostics/phase4a_gate4a1c_oracle_boundary_replay.py",
        ROOT / "pipeline/perception_vnext/recognition_schema_v2.py",
        ROOT / "pipeline/perception_vnext/segmentation/learned_features.py",
        BASE / "phase5_1t_3_first_class_agnostic_segmenter_01/training_config.json",
        BASE / "phase5_1t_3_first_class_agnostic_segmenter_01/best_model.keras",
        BASE / "phase5_1t_3_first_class_agnostic_segmenter_01/normalization_stats.json",
        BASE / "phase5_1t_3_first_class_agnostic_segmenter_01/feature_schema.json",
        BOUNDS,
        CHECKPOINT,
        VOCAB_MANIFEST,
        FROZEN["tflite"][0],
        FROZEN["recognition_v2_kt"][0],
        OUT / "learned_events_frozen.json",
        OUT / "test_results.json",
    ]
    write_json(
        OUT / "source_hashes.json",
        {
            "schema": "APPHEAR_PHASE6_SOURCE_HASHES_V1",
            "files": [
                {
                    "path": str(path.resolve()),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
                for path in files
            ],
        },
    )


def evaluate() -> dict[str, Any]:
    learned_events, learned_sha = verify_learned_freeze()
    identities = verify_post_freeze_identities(learned_sha)
    write_json(OUT / "oracle_identity.json", identities)
    bounds = read_json(BOUNDS)

    import tensorflow as tf

    model = tf.keras.models.load_model(CHECKPOINT, compile=False, safe_mode=True)
    vocab_map = read_json(VOCAB_MANIFEST)
    glosses = [gloss for gloss, index in sorted(vocab_map.items(), key=lambda pair: pair[1])]

    full, oracle = reproduce_references(model, bounds, glosses)
    reproduction = validate_reference_reproduction(full, oracle)
    full["reference_reproduction"] = reproduction
    oracle["reference_reproduction"] = reproduction
    write_json(OUT / "recognition_full.json", full)
    write_json(OUT / "recognition_oracle_reproduced.json", oracle)
    if reproduction["status"] != "PASS":
        decision = {
            "final_evidence_state": "PHASE6_REPLAY_INVALID",
            "reason": "PHASE6_REFERENCE_REPRODUCTION_INVALID",
            "next_stop_boundary": "STOP_REFERENCE_REPRODUCTION_INVALID",
        }
        write_json(OUT / "final_decision.json", decision)
        raise RuntimeError("PHASE6_REFERENCE_REPRODUCTION_INVALID")

    boundaries = boundary_comparison(learned_events, bounds)
    write_json(OUT / "boundary_comparison.json", boundaries)
    learned = learned_recognition(model, learned_events, bounds, glosses)
    write_json(OUT / "recognition_learned.json", learned)
    comparison = three_way_comparison(full, learned, oracle, boundaries)
    write_json(OUT / "three_way_recognition_comparison.json", comparison)
    causes = root_causes(comparison)
    write_json(OUT / "root_cause_attribution.json", causes)
    write_csv(comparison, boundaries)

    utility = recognition_utility_gates(full, learned)
    boundary_supported = bool(boundaries["boundary_transfer_supported"])
    utility_supported = bool(utility["recognition_utility_supported"])
    if boundary_supported and utility_supported:
        state = "PHASE6_LEARNED_PHONE_TRANSFER_AND_RECOGNITION_UTILITY_SUPPORTED"
        stop = "WAIT_FOR_PROJECT_LEAD_STREAMING_ANDROID_SEGMENTER_INTEGRATION_DECISION"
    elif boundary_supported:
        state = "PHASE6_BOUNDARY_TRANSFER_SUPPORTED_RECOGNITION_LIMITED"
        stop = "WAIT_FOR_PROJECT_LEAD_RECOGNITION_GENERALIZATION_DECISION"
    else:
        state = "PHASE6_LEARNED_SEGMENTER_PHONE_TRANSFER_NOT_SUPPORTED"
        stop = "WAIT_FOR_PROJECT_LEAD_PHONE_TRANSFER_FAILURE_DIAGNOSIS"
    decision = {
        "schema": "apphear.phase6.final_decision.v1",
        "milestone": MILESTONE,
        "learned_events_sha256": learned_sha,
        "reference_reproduction": reproduction,
        "boundary_transfer_supported": boundary_supported,
        "boundary_transfer_gates": boundaries["boundary_transfer_gates"],
        "recognition_utility_supported": utility_supported,
        "recognition_utility_gates": utility,
        "final_evidence_state": state,
        "next_stop_boundary": stop,
        "production_accuracy_claim": False,
        "streaming_decoder_claim": False,
        "training_executed": False,
        "android_modified": False,
        "recognition_dev_accessed": False,
        "protected_test_accessed": False,
        "other_phone_holdout_accessed": False,
    }
    write_json(OUT / "final_decision.json", decision)
    write_report(decision, identities, boundaries, full, learned, oracle, comparison, causes)
    return decision


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
