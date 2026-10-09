"""Phase 8A-U: audit the terminal supervision that actually trained frozen S2.

This utility is deliberately read-only with respect to scientific inputs.  It
uses the frozen Phase-7 FIT/CAL split, persisted sparse labels, retained full
raw-v1 timestamps, and already-written Phase-8A evidence.  It performs no
model inference, training, decoder search, recognition, or phone access.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MILESTONE = "PHASE_8A_U_S2_TRAINING_EXPOSURE_AND_TERMINAL_DIVERSITY_AUDIT_01"
BASE = ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
T0 = BASE / "phase5_1t_0_segmentation_data_readiness_audit_01"
T1 = BASE / "phase5_1t_1_human_temporal_semantics_validation_01"
T2 = BASE / "phase5_1t_2_bounded_segmentation_seed_dataset_01"
T3 = BASE / "phase5_1t_3_first_class_agnostic_segmenter_01"
P7 = BASE / "phase7_production_cadence_aligned_segmenter_01"
P8A = BASE / "phase8a_causal_streaming_sign_event_decoder_01"
P8T = BASE / "phase8a_t_causal_terminal_evidence_attribution_01"
OUT = BASE / "phase8a_u_s2_training_exposure_and_terminal_diversity_audit_01"

EXPECTED_SELECTED_SHA = "832ba25420bef80acda3b40e7a44414654c3227222e4336d66174b8cca7ea15e"
EXPECTED_SPLIT_SHA = "b4a2dbaf9c3810a86f8407068ea50dfc3f2079fc951932ff3a76bbe411b599c6"
EXPECTED_S2_SHA = "dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73"
IGNORE_BAND_MS = 100.0
CONFIG01_POST_CONFIRM_MS = 266.616
VIEW_IDS = ("VIEW_A", "VIEW_B", "VIEW_C")
LABEL_NAMES = {-1: "IGNORED", 0: "PRE_IDLE", 1: "ACTIVE_SIGN", 2: "POST_RECOVERY"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def distribution(values: Iterable[float]) -> dict[str, float | int | None]:
    array = np.asarray(list(values), np.float64)
    if not len(array):
        return {
            key: None for key in ("min", "p10", "p25", "median", "mean", "p75", "p90", "max")
        } | {"count": 0}
    return {
        "count": int(len(array)),
        "min": float(np.min(array)),
        "p10": float(np.percentile(array, 10)),
        "p25": float(np.percentile(array, 25)),
        "median": float(np.median(array)),
        "mean": float(np.mean(array)),
        "p75": float(np.percentile(array, 75)),
        "p90": float(np.percentile(array, 90)),
        "max": float(np.max(array)),
    }


def temporal_labels(timestamps_ms: np.ndarray, start_ms: float, end_ms: float) -> np.ndarray:
    """Mirror the frozen Phase-5.1T-3/Phase-7 label policy exactly."""
    timestamps = np.asarray(timestamps_ms, np.float64)
    labels = np.full(len(timestamps), -1, np.int8)
    labels[timestamps < start_ms - IGNORE_BAND_MS] = 0
    labels[(timestamps > start_ms + IGNORE_BAND_MS) & (timestamps < end_ms - IGNORE_BAND_MS)] = 1
    labels[timestamps > end_ms + IGNORE_BAND_MS] = 2
    return labels


def label_counts(labels: Iterable[int]) -> dict[str, int]:
    counts = Counter(int(value) for value in labels)
    return {LABEL_NAMES[index]: int(counts[index]) for index in (-1, 0, 1, 2)}


def transition_profile(timestamps_ms: Iterable[float], labels: Iterable[int]) -> dict[str, Any]:
    timestamps = np.asarray(list(timestamps_ms), np.float64)
    target = np.asarray(list(labels), np.int8)
    active = np.flatnonzero(target == 1)
    post = np.flatnonzero(target == 2)
    post_span = float(timestamps[post[-1]] - timestamps[post[0]]) if len(post) else 0.0
    has_pair = bool(len(active) and len(post) and timestamps[post[0]] > timestamps[active[-1]])
    return {
        "active_observations": int(len(active)),
        "post_observations": int(len(post)),
        "has_active_to_post_supervision": has_pair,
        "first_post_ms": float(timestamps[post[0]]) if len(post) else None,
        "last_post_ms": float(timestamps[post[-1]]) if len(post) else None,
        "post_supervised_span_ms": post_span,
        "has_config01_confirmation_timespan": bool(
            len(post) >= 2 and post_span >= CONFIG01_POST_CONFIRM_MS
        ),
    }


def integrity_audit() -> dict[str, Any]:
    required = [
        T2 / "selected_120_manifest.json",
        T2 / "frozen_segmentation_split.json",
        T2 / "segmentation_human_annotations.json",
        P7 / "frozen_fit_cal_split.json",
        P7 / "sparse_view_manifest.json",
        P7 / "generated_sparse_temporal_labels.json",
        P7 / "training_history.json",
        P7 / "best_model.keras",
        P8A / "cal_decoder_grid_results.csv",
        P8T / "population_inventory.json",
        T0 / "per_sample_context.csv",
        T1 / "human_annotations.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"PHASE8A_U_CONTINUITY_MISMATCH:MISSING:{missing}")
    if sha256(T2 / "selected_120_manifest.json") != EXPECTED_SELECTED_SHA:
        raise RuntimeError("PHASE8A_U_SELECTED_MANIFEST_HASH_MISMATCH")
    if sha256(T2 / "frozen_segmentation_split.json") != EXPECTED_SPLIT_SHA:
        raise RuntimeError("PHASE8A_U_SEGMENTATION_SPLIT_HASH_MISMATCH")
    if sha256(P7 / "best_model.keras") != EXPECTED_S2_SHA:
        raise RuntimeError("PHASE8A_U_S2_HASH_MISMATCH")

    split = read_json(P7 / "frozen_fit_cal_split.json")
    manifest = read_json(P7 / "sparse_view_manifest.json")
    labels = read_json(P7 / "generated_sparse_temporal_labels.json")
    if (split["fit_count"], split["cal_count"]) != (71, 18):
        raise RuntimeError("PHASE8A_U_FIT_CAL_COUNT_MISMATCH")
    if (manifest["fit_view_count"], manifest["cal_view_count"]) != (213, 54):
        raise RuntimeError("PHASE8A_U_SPARSE_VIEW_COUNT_MISMATCH")
    if len(labels["views"]) != 336:
        raise RuntimeError("PHASE8A_U_LABEL_VIEW_COUNT_MISMATCH")
    return {
        "schema": "apphear.phase8a_u.integrity_audit.v1",
        "milestone": MILESTONE,
        "selected_manifest_sha256": EXPECTED_SELECTED_SHA,
        "segmentation_split_sha256": EXPECTED_SPLIT_SHA,
        "s2_checkpoint_sha256": EXPECTED_S2_SHA,
        "fit_clips": 71,
        "cal_clips": 18,
        "fit_sparse_views": 213,
        "cal_sparse_views": 54,
        "actual_optimization_population": "FIT_71_ONLY",
        "checkpoint_selection_population": "CAL_18_ONLY",
        "model_inference_rerun": False,
        "raw_v1_extraction_rerun": False,
        "training": False,
        "decoder_search": False,
        "recognition": False,
        "known_phone_access": False,
        "recognition_dev_access": False,
        "protected_test_access": False,
        "android_change": False,
    }


def build_exposure_rows() -> list[dict[str, Any]]:
    split = read_json(P7 / "frozen_fit_cal_split.json")
    fit_ids = set(map(str, split["fit_sample_ids"]))
    cal_ids = set(map(str, split["cal_sample_ids"]))
    manifest_rows = read_json(P7 / "sparse_view_manifest.json")["rows"]
    label_rows = {
        str(row["view_key"]): row
        for row in read_json(P7 / "generated_sparse_temporal_labels.json")["views"]
    }
    annotations = {
        str(row["sample_id"]): row
        for row in read_json(T2 / "segmentation_human_annotations.json")["annotations"]
    }
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in manifest_rows:
        sample_id = str(row["sample_id"])
        if sample_id in fit_ids or sample_id in cal_ids:
            grouped[sample_id].append(row)
    if set(grouped) != fit_ids | cal_ids:
        raise RuntimeError("PHASE8A_U_EXPOSURE_MEMBERSHIP_MISMATCH")

    output: list[dict[str, Any]] = []
    for sample_id in sorted(grouped):
        views = sorted(grouped[sample_id], key=lambda row: str(row["view_id"]))
        if [row["view_id"] for row in views] != list(VIEW_IDS):
            raise RuntimeError(f"PHASE8A_U_VIEW_MEMBERSHIP_MISMATCH:{sample_id}")
        annotation = annotations[sample_id]
        start_ms = float(annotation["human_sign_start_ms"])
        end_ms = float(annotation["human_sign_end_ms"])
        raw_path = Path(str(views[0]["source_raw_path"]))
        with np.load(raw_path, allow_pickle=False) as raw:
            raw_timestamps = np.asarray(raw["timestamp_ms"], np.float64)
            raw_labels = temporal_labels(raw_timestamps, start_ms, end_ms)
            post_mask = raw_labels == 2
            hand_usable = np.any(
                np.asarray(raw["hand_observed"], bool)
                | np.asarray(raw["hand_proposal_present"], bool),
                axis=1,
            )
            body_usable = np.asarray(raw["body_available"], bool)
        view_profiles = {}
        for view in views:
            label_row = label_rows[str(view["view_key"])]
            timestamps = np.asarray(label_row["timestamps_ms"], np.float64)
            labels = np.asarray(label_row["labels"], np.int8)
            view_profiles[str(view["view_id"])] = {
                "target_interval_ms": float(view["target_interval_ms"]),
                "selected_observations": int(len(timestamps)),
                "label_counts": label_counts(labels),
                **transition_profile(timestamps, labels),
            }
        output.append(
            {
                "partition": "FIT" if sample_id in fit_ids else "CAL",
                "sample_id": sample_id,
                "source": str(views[0]["source"]),
                "signer_id": str(views[0]["signer_id"]),
                "gloss": str(annotation["gloss"]),
                "human_start_ms": start_ms,
                "human_end_ms": end_ms,
                "raw_first_timestamp_ms": float(raw_timestamps[0]),
                "raw_last_timestamp_ms": float(raw_timestamps[-1]),
                "genuine_post_context_ms": max(0.0, float(raw_timestamps[-1] - end_ms)),
                "full_raw_observation_count": int(len(raw_timestamps)),
                "full_raw_label_counts": label_counts(raw_labels),
                "full_raw_transition": transition_profile(raw_timestamps, raw_labels),
                "full_raw_post_hand_usable_fraction": (
                    float(np.mean(hand_usable[post_mask])) if np.any(post_mask) else None
                ),
                "full_raw_post_body_usable_fraction": (
                    float(np.mean(body_usable[post_mask])) if np.any(post_mask) else None
                ),
                "views": view_profiles,
            }
        )
    return output


def _concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals: Counter[str] = Counter()
    clips: Counter[str] = Counter()
    for row in rows:
        signer = str(row["signer_id"])
        clips[signer] += 1
        totals[signer] += sum(int(row["views"][view]["post_observations"]) for view in VIEW_IDS)
    total = sum(totals.values())
    ordered = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    shares = [value / total for _, value in ordered] if total else []
    return {
        "total_sparse_post_observations": total,
        "top_signer_share": shares[0] if shares else None,
        "top_three_signer_share": sum(shares[:3]) if shares else None,
        "herfindahl_index": sum(value * value for value in shares),
        "effective_signer_count": 1.0 / sum(value * value for value in shares) if shares else 0.0,
        "by_signer": [
            {
                "signer_id": signer,
                "clips": clips[signer],
                "sparse_post_observations": count,
                "share": count / total if total else 0.0,
            }
            for signer, count in ordered
        ],
    }


def summarize_exposure(rows: list[dict[str, Any]], partition: str) -> dict[str, Any]:
    selected = [row for row in rows if row["partition"] == partition]
    source_groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        source_groups[str(row["source"])].append(row)

    def summarize_group(group: list[dict[str, Any]]) -> dict[str, Any]:
        sparse_counts: Counter[str] = Counter()
        transition_views = 0
        confirmation_views = 0
        total_views = 0
        for row in group:
            for view in VIEW_IDS:
                profile = row["views"][view]
                sparse_counts.update(profile["label_counts"])
                transition_views += int(profile["has_active_to_post_supervision"])
                confirmation_views += int(profile["has_config01_confirmation_timespan"])
                total_views += 1
        return {
            "clips": len(group),
            "signers": len({row["signer_id"] for row in group}),
            "clips_per_signer": dict(sorted(Counter(row["signer_id"] for row in group).items())),
            "genuine_post_context_ms": distribution(
                row["genuine_post_context_ms"] for row in group
            ),
            "full_raw_post_observations": distribution(
                row["full_raw_transition"]["post_observations"] for row in group
            ),
            "full_raw_post_hand_usable_fraction": distribution(
                row["full_raw_post_hand_usable_fraction"]
                for row in group
                if row["full_raw_post_hand_usable_fraction"] is not None
            ),
            "full_raw_post_body_usable_fraction": distribution(
                row["full_raw_post_body_usable_fraction"]
                for row in group
                if row["full_raw_post_body_usable_fraction"] is not None
            ),
            "sparse_label_counts": dict(sorted(sparse_counts.items())),
            "active_to_post_supervision_views": transition_views,
            "active_to_post_supervision_rate": transition_views / total_views
            if total_views
            else 0.0,
            "config01_timespan_covered_views": confirmation_views,
            "config01_timespan_covered_rate": confirmation_views / total_views
            if total_views
            else 0.0,
            "terminal_supervision_concentration": _concentration(group),
        }

    by_cadence = {}
    for view in VIEW_IDS:
        profiles = [(row, row["views"][view]) for row in selected]
        by_cadence[view] = {
            "target_interval_ms": profiles[0][1]["target_interval_ms"] if profiles else None,
            "views": len(profiles),
            "post_observations": sum(item["post_observations"] for _, item in profiles),
            "post_observation_distribution": distribution(
                item["post_observations"] for _, item in profiles
            ),
            "active_to_post_supervision_count": sum(
                item["has_active_to_post_supervision"] for _, item in profiles
            ),
            "config01_timespan_covered_count": sum(
                item["has_config01_confirmation_timespan"] for _, item in profiles
            ),
        }
    result = summarize_group(selected)
    result.update(
        {
            "schema": "apphear.phase8a_u.terminal_exposure_summary.v1",
            "partition": partition,
            "actual_role": "OPTIMIZATION_WEIGHT_UPDATES"
            if partition == "FIT"
            else "CHECKPOINT_SELECTION_ONLY",
            "source_breakdown": {
                source: summarize_group(group) for source, group in sorted(source_groups.items())
            },
            "by_cadence": by_cadence,
        }
    )
    return result


def checkpoint_selection_audit() -> dict[str, Any]:
    config = read_json(P7 / "phase7_config.json")
    history = read_json(P7 / "training_history.json")
    with (P8A / "cal_decoder_grid_results.csv").open(encoding="utf-8-sig", newline="") as stream:
        config01 = next(row for row in csv.DictReader(stream) if row["config_id"] == "CONFIG_01")
    selected_epoch = next(
        row
        for row in history["epoch_cal_metrics"]
        if int(row["epoch"]) == int(history["best_epoch"])
    )
    global_metrics = selected_epoch["cal_event_metrics"]
    return {
        "schema": "apphear.phase8a_u.checkpoint_selection_alignment.v1",
        "best_epoch": int(history["best_epoch"]),
        "checkpoint_population": history["checkpoint_population"],
        "decoder_used_for_selection": config["decoding"],
        "selection_rule": config["training"]["checkpoint_rule"],
        "selection_is_sequence_global": config["decoding"]["primary_run"].startswith("MAX_ACTIVE"),
        "causal_event_completion_metric_in_selection": False,
        "terminal_post_availability_metric_in_selection": False,
        "causal_emission_latency_metric_in_selection": False,
        "selected_epoch_global_reference": {
            "event_emission_rate": global_metrics["event_emission_rate"],
            "containment_rate": global_metrics["containment_rate"],
            "premature_cut_rate": global_metrics["premature_cut_rate"],
            "post_recovery_recall": selected_epoch["cal_state_metrics"]["per_class"][
                "POST_RECOVERY"
            ]["recall"],
        },
        "same_checkpoint_config01_causal_reference": {
            "event_emission_rate": float(config01["event_emission_rate"]),
            "containment_rate": float(config01["containment_rate"]),
            "premature_cut_rate": float(config01["premature_cut_rate"]),
            "severe_cut_rate": float(config01["severe_cut_rate"]),
        },
        "alignment_assessment": "MISALIGNED_WITH_CAUSAL_SIGN_EVENT_COMPLETION",
        "reason": (
            "CAL selection rewarded completed-sequence primary-run containment, precision, and "
            "state macro-F1. It did not score causal CONFIG_01 emission, timely terminal POST, or "
            "emission latency; the selected checkpoint reached 100% global emission but only "
            "92.59% CONFIG_01 emission on the same CAL views."
        ),
        "limit": (
            "Only the selected checkpoint was retained, so this audit cannot retrospectively rank "
            "all 30 epochs by causal completion without rerunning unavailable epoch checkpoints."
        ),
    }


def unused_data_audit() -> dict[str, Any]:
    selected = {
        str(row["sample_id"]) for row in read_json(T2 / "selected_120_manifest.json")["rows"]
    }
    frozen_split = read_json(T2 / "frozen_segmentation_split.json")
    reserved_dev_signers = set(map(str, frozen_split["dev_signers"]))
    with (T0 / "per_sample_context.csv").open(encoding="utf-8-sig", newline="") as stream:
        governed_train = list(csv.DictReader(stream))
    unused = [row for row in governed_train if str(row["sample_id"]) not in selected]
    source_counts = Counter(str(row["source"]) for row in unused)
    signer_counts = {
        source: dict(
            sorted(
                Counter(str(row["signer_id"]) for row in unused if row["source"] == source).items()
            )
        )
        for source in sorted(source_counts)
    }
    asl_room = [
        row
        for row in unused
        if row["source"] == "ASL_CITIZEN"
        and float(row["pre_context_ms"] or -1) >= 500.0
        and float(row["post_context_ms"] or -1) >= 750.0
    ]
    t1 = read_json(T1 / "human_annotations.json")["annotations"]
    outside = [row for row in t1 if str(row["sample_id"]) not in selected]
    usable = [row for row in outside if not bool(row["ambiguous_or_unusable"])]
    eligible = [row for row in usable if str(row["signer_id"]) not in reserved_dev_signers]
    source_domain_signers = {
        str(row["signer_id"]) for row in unused if row["source"] in {"LOCAL", "APPHEAR_CAPTURE"}
    }
    training_signers = set(map(str, frozen_split["train_signers"]))
    independent_unreserved = sorted(source_domain_signers - training_signers - reserved_dev_signers)
    return {
        "schema": "apphear.phase8a_u.unused_governed_data_audit.v1",
        "governed_population_role": "RECOGNITION_TRAIN_ONLY",
        "unused_clips": len(unused),
        "unused_by_source": dict(sorted(source_counts.items())),
        "unused_signers_by_source": signer_counts,
        "unused_asl_citizen_d1_room_500pre_750post": len(asl_room),
        "d1_label_warning": (
            "D1 is detector-derived and is not authorized as temporal ground truth."
        ),
        "unused_apphear_local_governed_span_status": "NO_GOVERNED_TEMPORAL_SPAN",
        "phase5_1t_1_human_labels_outside_selected_120": {
            "total": len(outside),
            "usable": len(usable),
            "eligible_without_reserved_dev_signers": len(eligible),
            "eligible_by_source": dict(sorted(Counter(row["source"] for row in eligible).items())),
            "eligible_signers_by_source": {
                source: sorted({row["signer_id"] for row in eligible if row["source"] == source})
                for source in sorted({row["source"] for row in eligible})
            },
            "rows": [
                {
                    "sample_id": row["sample_id"],
                    "source": row["source"],
                    "signer_id": row["signer_id"],
                    "gloss": row["gloss"],
                    "usable": not bool(row["ambiguous_or_unusable"]),
                    "reserved_dev_signer": str(row["signer_id"]) in reserved_dev_signers,
                }
                for row in sorted(outside, key=lambda item: str(item["sample_id"]))
            ],
        },
        "independent_unreserved_apphear_local_signers": independent_unreserved,
        "raw_v1_status": (
            "Full raw-v1 was retained only for the frozen 112 usable Phase-5.1T-2 clips; unused "
            "governed clips would require a separately authorized deterministic extraction."
        ),
        "assessment": "EXISTING_DATA_ADDS_VOLUME_BUT_NOT_NEW_APPHEAR_LOCAL_SIGNER_DIVERSITY",
        "new_collection_needed": {
            "for_more_known_signer_or_asl_transition_examples": False,
            "for_independent_local_phone_like_signer_diversity": True,
        },
    }


def terminal_control_discrepancy() -> dict[str, Any]:
    # Reconstruct only from persisted CAL/DEV state streams; this does not run S2.
    from eval.runtime_diagnostics import phase8a_t_terminal_evidence_attribution as phase8at

    records = [
        phase8at._sequence_record(stream)
        for stream in phase8at._cal_streams() + phase8at._dev_streams()
    ]
    successful = [row for row in records if row["outcome"] == "SUCCESSFUL_EVENT"]
    omitted = [row for row in successful if not row["terminal_evidence"]["observation_count"]]
    if len(successful) != 97 or len(omitted) != 3:
        raise RuntimeError("PHASE8A_U_TERMINAL_CONTROL_COUNT_MISMATCH")
    rows = [
        {
            "population": row["population"],
            "sample_id": row["sample_id"],
            "view_id": row["view_id"],
            "human_end_ms": row["human_end_ms"],
            "commit_ms": row["commit_ms"],
            "commit_minus_human_end_ms": float(row["commit_ms"] - row["human_end_ms"]),
            "post_context_available_ms": row["post_context_available_ms"],
            "exclusion_reason": "NO_OBSERVATION_IN_HUMAN_END_TO_CAUSAL_COMMIT_INTERVAL",
        }
        for row in omitted
    ]
    return {
        "schema": "apphear.phase8a_u.terminal_control_discrepancy.v1",
        "successful_event_views": len(successful),
        "successful_terminal_controls": len(successful) - len(omitted),
        "omitted_views": rows,
        "exclusion_is_deterministic": True,
        "exclusion_is_legitimate": True,
        "explanation": (
            "All three events committed slightly before the human END. The frozen Phase-8A-T "
            "terminal interval was [human END, causal commit], so it contained zero observations. "
            "Using observations after commit would violate the causal terminal-control definition."
        ),
        "material_effect_on_phase8a_t_conclusion": False,
        "reason_no_material_effect": (
            "The omitted rows contain no causally available post-human-END evidence to add to the "
            "terminal envelope. Their intra-ACTIVE controls remained included, and the 6/7 absent "
            "DEV finding does not depend on inventing post-commit evidence for these rows."
        ),
    }


def _write_exposure_csv(rows: list[dict[str, Any]]) -> None:
    fields = [
        "partition",
        "sample_id",
        "source",
        "signer_id",
        "gloss",
        "human_start_ms",
        "human_end_ms",
        "genuine_post_context_ms",
        "full_raw_observation_count",
        "full_raw_post_observations",
    ]
    for view in VIEW_IDS:
        fields.extend(
            [
                f"{view.lower()}_post_observations",
                f"{view.lower()}_has_active_to_post_supervision",
                f"{view.lower()}_post_supervised_span_ms",
                f"{view.lower()}_config01_timespan_covered",
            ]
        )
    path = OUT / "per_clip_terminal_exposure.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            flat = {key: row[key] for key in fields[:9]}
            flat["full_raw_post_observations"] = row["full_raw_transition"]["post_observations"]
            for view in VIEW_IDS:
                profile = row["views"][view]
                prefix = view.lower()
                flat[f"{prefix}_post_observations"] = profile["post_observations"]
                flat[f"{prefix}_has_active_to_post_supervision"] = profile[
                    "has_active_to_post_supervision"
                ]
                flat[f"{prefix}_post_supervised_span_ms"] = profile["post_supervised_span_ms"]
                flat[f"{prefix}_config01_timespan_covered"] = profile[
                    "has_config01_confirmation_timespan"
                ]
            writer.writerow(flat)


def source_hashes() -> dict[str, Any]:
    paths = [
        Path(__file__),
        ROOT / "tests/test_phase8a_u_s2_training_exposure_audit.py",
        P7 / "phase7_config.json",
        P7 / "frozen_fit_cal_split.json",
        P7 / "sparse_view_manifest.json",
        P7 / "generated_sparse_temporal_labels.json",
        P7 / "training_history.json",
        P8A / "cal_decoder_grid_results.csv",
        P8T / "population_inventory.json",
        T0 / "per_sample_context.csv",
        T1 / "human_annotations.json",
        T2 / "selected_120_manifest.json",
        T2 / "frozen_segmentation_split.json",
    ]
    return {
        "schema": "apphear.phase8a_u.source_hashes.v1",
        "files": {str(path.relative_to(ROOT)): sha256(path) for path in paths},
    }


def render_report(
    fit: dict[str, Any],
    cal: dict[str, Any],
    checkpoint: dict[str, Any],
    unused: dict[str, Any],
    discrepancy: dict[str, Any],
    decision: dict[str, Any],
) -> str:
    fit_sources = fit["source_breakdown"]
    cal_sources = cal["source_breakdown"]
    fit_asl = fit_sources["ASL_CITIZEN"]
    fit_app = fit_sources["APPHEAR_CAPTURE"]
    fit_local = fit_sources["LOCAL"]
    cal_asl = cal_sources["ASL_CITIZEN"]
    cal_app = cal_sources["APPHEAR_CAPTURE"]
    cal_local = cal_sources["LOCAL"]
    fit_labels = fit["sparse_label_counts"]
    omitted_names = ", ".join(
        row["sample_id"] + "::" + row["view_id"] for row in discrepancy["omitted_views"]
    )
    return f"""# {MILESTONE}

## 1. Scope and governance

This was a read-only data/training-readiness audit. Frozen S2, the 378-feature contract,
normalization, CONFIG_01, the cadence-safe materializer, Recognition V2, the recognizer, and
Android were unchanged. No training, inference, extraction, recognition, phone replay,
Recognition DEV, or protected TEST access occurred.

## 2. Actual optimization exposure — FIT-71

Only FIT updated S2. It contained **{fit["clips"]} clips / {fit["signers"]} signers / 213 sparse
views**: ASL_CITIZEN **{fit_asl["clips"]} clips / {fit_asl["signers"]} signers**,
APPHEAR_CAPTURE **{fit_app["clips"]} / {fit_app["signers"]}**, and LOCAL
**{fit_local["clips"]} / {fit_local["signers"]}**. FIT sparse label counts were
PRE `{fit_labels["PRE_IDLE"]}`, ACTIVE `{fit_labels["ACTIVE_SIGN"]}`,
POST `{fit_labels["POST_RECOVERY"]}`, ignored `{fit_labels["IGNORED"]}`.

APPHEAR_CAPTURE supervision came from one signer. LOCAL supervision came from three signers. The
source-domain terminal signal therefore had useful volume but shallow independent-signer support.
The per-signer concentration and per-cadence retention are in `fit_terminal_exposure.json`.

## 3. Checkpoint-selection exposure — CAL-18

CAL did not update weights. It contained **{cal["clips"]} clips / {cal["signers"]} signers / 54
sparse views**: ASL_CITIZEN **{cal_asl["clips"]} / {cal_asl["signers"]}**,
APPHEAR_CAPTURE **{cal_app["clips"]} / {cal_app["signers"]}**, and LOCAL
**{cal_local["clips"]} / {cal_local["signers"]}**. Its role was checkpoint selection only.

## 4. Sparse terminal supervision

All counts use the frozen ±100 ms ignore band and genuine selected observations. VIEW_A/B/C
statistics report whether each view retained both supervised ACTIVE and POST, how many POST
observations survived, and whether supervised POST spans covered CONFIG_01's 266.616 ms terminal
timescale. They are supervision-availability measures, not claims that S2 predicted POST.

## 5. Checkpoint-selection alignment

Assessment: **{checkpoint["alignment_assessment"]}**. Epoch {checkpoint["best_epoch"]} was selected
with the completed-sequence primary-run decoder. It achieved global emission
`{checkpoint["selected_epoch_global_reference"]["event_emission_rate"]:.4f}` and containment
`{checkpoint["selected_epoch_global_reference"]["containment_rate"]:.4f}`, while the same frozen
checkpoint under CONFIG_01 achieved emission
`{checkpoint["same_checkpoint_config01_causal_reference"]["event_emission_rate"]:.4f}` and
containment `{checkpoint["same_checkpoint_config01_causal_reference"]["containment_rate"]:.4f}`.
No causal completion, terminal-POST availability, or emission-latency metric participated in
checkpoint selection.

## 6. Existing unused governed data

There are **{unused["unused_clips"]}** unselected recognition-TRAIN clips. ASL_CITIZEN contributes
`{unused["unused_by_source"]["ASL_CITIZEN"]}` clips, including
`{unused["unused_asl_citizen_d1_room_500pre_750post"]}` with D1-estimated 500 ms PRE / 750 ms POST
room, but D1 is not temporal ground truth. APPHEAR_CAPTURE/LOCAL contribute
`{unused["unused_by_source"]["APPHEAR_CAPTURE"]}` / `{unused["unused_by_source"]["LOCAL"]}` clips
without governed temporal spans.

Phase 5.1T-1 supplies 19 usable human-labeled clips outside the selected 120; 17 remain eligible
after preserving frozen DEV signer roles. They add examples from already represented source-domain
signers, not a new independent APPHEAR/LOCAL signer. Existing data can add transition volume, but
new capture is required for genuinely independent LOCAL/phone-like signer diversity.

## 7. Phase 8A-T 97-versus-94 control audit

The three omitted controls were `{omitted_names}`.
Each committed slightly before the human END, leaving no observation in the causal `[human END,
commit]` terminal interval. Exclusion was deterministic and legitimate; adding later post-commit
observations would violate the control definition. The Phase 8A-T conclusion is unchanged.

## 8. Decision

**{decision["evidence_state"]}**

The smallest justified future correction is one S2-R1 run that combines modest source/signer-aware
terminal data enrichment with causal completion-aligned checkpoint selection while preserving the
378 features, causal TCN family, CONFIG_01 evaluation, and frozen materializer. That run is not
authorized by this audit.

New collection is not necessary merely to increase ASL or known-signer transition volume. It is
needed before an independent LOCAL/phone-like signer generalization claim because the governed
unused pool contains no unreserved source-domain signer outside existing TRAIN/DEV roles.

## 9. Claim limits

The terminal failure evidence comes from one held-out LOCAL signer. This audit does not prove all
LOCAL/mobile users fail, does not establish that data alone will repair S2, and cannot reconstruct
causal checkpoint quality for every epoch because only the selected checkpoint was retained.

## 10. Stop

`WAIT_FOR_PROJECT_LEAD_S2_R1_ARCHITECTURE_REVIEW`
"""


def run() -> dict[str, Any]:
    audit = integrity_audit()
    rows = build_exposure_rows()
    fit = summarize_exposure(rows, "FIT")
    cal = summarize_exposure(rows, "CAL")
    history = read_json(P7 / "training_history.json")
    if fit["sparse_label_counts"] != history["class_label_counts_fit_only"] | {"IGNORED": 0}:
        # The history excludes ignored labels, so compare the supervised classes explicitly below.
        for key in ("PRE_IDLE", "ACTIVE_SIGN", "POST_RECOVERY"):
            if fit["sparse_label_counts"][key] != history["class_label_counts_fit_only"][key]:
                raise RuntimeError("PHASE8A_U_FIT_LABEL_REPRODUCTION_FAILURE")
    checkpoint = checkpoint_selection_audit()
    unused = unused_data_audit()
    discrepancy = terminal_control_discrepancy()
    data_weak = (
        fit["source_breakdown"]["APPHEAR_CAPTURE"]["signers"] == 1
        and fit["source_breakdown"]["LOCAL"]["signers"] == 3
        and not unused["independent_unreserved_apphear_local_signers"]
    )
    objective_weak = (
        checkpoint["alignment_assessment"] == "MISALIGNED_WITH_CAUSAL_SIGN_EVENT_COMPLETION"
    )
    if data_weak and objective_weak:
        state = "TARGETED_S2_DATA_AND_CAUSAL_OBJECTIVE_CORRECTION_SUPPORTED"
    elif data_weak:
        state = "TARGETED_S2_DATA_ENRICHMENT_SUPPORTED"
    elif objective_weak:
        state = "TARGETED_S2_CAUSAL_TRAINING_OBJECTIVE_CORRECTION_SUPPORTED"
    else:
        state = "S2_FAILURE_NOT_EXPLAINED_BY_TRAINING_EXPOSURE"
    decision = {
        "schema": "apphear.phase8a_u.final_decision.v1",
        "evidence_state": state,
        "data_diversity_or_supervision_weak": data_weak,
        "causal_checkpoint_objective_weak": objective_weak,
        "smallest_justified_future_correction": (
            "ONE_S2_R1_WITH_SOURCE_SIGNER_AWARE_TERMINAL_ENRICHMENT_AND_CAUSAL_CAL_SELECTION"
            if state == "TARGETED_S2_DATA_AND_CAUSAL_OBJECTIVE_CORRECTION_SUPPORTED"
            else "PROJECT_LEAD_REVIEW_REQUIRED"
        ),
        "new_collection_needed_for_known_signer_volume": False,
        "new_collection_needed_for_independent_local_phone_signer_diversity": True,
        "s2_r1_started": False,
        "next": "WAIT_FOR_PROJECT_LEAD_S2_R1_ARCHITECTURE_REVIEW",
    }

    _write_exposure_csv(rows)
    write_json(OUT / "integrity_audit.json", audit)
    write_json(OUT / "fit_terminal_exposure.json", fit)
    write_json(OUT / "cal_terminal_exposure.json", cal)
    write_json(OUT / "checkpoint_selection_alignment.json", checkpoint)
    write_json(OUT / "unused_governed_data_audit.json", unused)
    write_json(OUT / "terminal_control_94_vs_97_audit.json", discrepancy)
    write_json(OUT / "final_decision.json", decision)
    (OUT / "PHASE8A_U_S2_TRAINING_EXPOSURE_AND_TERMINAL_DIVERSITY_AUDIT_REPORT.md").write_text(
        render_report(fit, cal, checkpoint, unused, discrepancy, decision), encoding="utf-8"
    )
    write_json(OUT / "source_hashes.json", source_hashes())
    return decision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("audit",))
    args = parser.parse_args()
    if args.command == "audit":
        print(json.dumps(run(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
