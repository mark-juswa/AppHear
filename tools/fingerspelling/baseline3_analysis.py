"""Bounded B2 inference and governed raw-only slot diagnostics; no perception or training."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

import numpy as np

from model import fingerspelling_ctc as reference
from model.fingerspelling_baseline2 import DEFAULT_DATA, dataset, policy
from model.fingerspelling_emission import evaluate_views
from model.fingerspelling_fast_execution import CompiledSteps, FeatureCache
from model.fingerspelling_metrics import alignment
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import verify_raw

OUT = REPO / "artifacts/fingerspelling_baseline3"


def character_metrics(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    labels = [chr(65 + i) for i in range(26)] + [" "]
    counts: dict[str, Counter] = {c: Counter() for c in labels}
    insertions: Counter = Counter()
    for row in predictions:
        for op, a, b in alignment(row["reference"], row["prediction"])["operations"]:
            if op == "I":
                insertions[b] += 1
            else:
                counts[a][b if b else "DELETION"] += 1
    return {
        "per_character": {
            c: {
                "reference_count": sum(counts[c].values()),
                "correct": counts[c][c],
                "recall": counts[c][c] / sum(counts[c].values()) if counts[c] else None,
                "confusions": dict(counts[c]),
            }
            for c in labels
        },
        "inserted_characters": dict(insertions),
        "alignment": "DETERMINISTIC_LEVENSHTEIN_NOT_LETTER_TIMESTAMPS",
    }


def roi_iou(roi: np.ndarray) -> np.ndarray:
    low = roi[:, :, :2] - roi[:, :, 2:3] / 2
    high = roi[:, :, :2] + roi[:, :, 2:3] / 2
    overlap = np.maximum(0, np.minimum(high[:, 0], high[:, 1]) - np.maximum(low[:, 0], low[:, 1]))
    area = overlap[:, 0] * overlap[:, 1]
    union = roi[:, 0, 2] ** 2 + roi[:, 1, 2] ** 2 - area
    return cast(
        np.ndarray, np.divide(area, union, out=np.zeros(len(roi), np.float32), where=union > 0)
    )


def run() -> dict[str, Any]:
    p, base = policy()
    rows = dataset(DEFAULT_DATA)
    selected = []
    for stratum in ["DAUN", "MacKenzie"]:
        candidates = sorted(
            [r for r in rows if r["split_role"] == "TRAIN" and r["source_stratum"] == stratum],
            key=lambda r: (r["official_signer_id"], r["sample_id"]),
        )
        first: dict[str, Any] = {}
        for r in candidates:
            first.setdefault(r["official_signer_id"], r)
        selected.extend(list(first.values())[:32])
    model_path = Path(
        json.loads((REPO / "runs/fingerspelling_ctc_baseline_02/completion.json").read_text())[
            "best_model_path"
        ]
    )
    write_json_atomic(
        OUT / "diagnostic_manifest.json",
        {
            "sample_ids": [r["sample_id"] for r in selected],
            "role": "TRAIN",
            "strata_counts": dict(Counter(r["source_stratum"] for r in selected)),
            "selection": "FIRST_SOURCE_PER_SIGNER_METADATA_SORT_32_PER_STRATUM",
            "checkpoint_sha256": sha256(model_path),
            "test_accessed": False,
        },
    )
    tf = reference.tensorflow(base)
    model = tf.keras.models.load_model(model_path)
    views, _, times = evaluate_views(
        tf, CompiledSteps(tf, model), FeatureCache(), selected, p, base["batch_size"]
    )
    final = json.loads(
        (REPO / "runs/fingerspelling_ctc_baseline_02/final_evaluation.json").read_text()
    )
    for value in views.values():
        value["characters"] = character_metrics(value["predictions"])
    dev = final["uncalibrated"]
    for value in dev.values():
        value["characters"] = character_metrics(value["predictions"])
    write_json_atomic(
        OUT / "train_dev_decoding.json",
        {
            "schema_version": "apphear.fingerspelling.baseline3_train_dev_diagnostic.v1",
            "train": views,
            "dev": dev,
            "train_count": len(selected),
            "dev_count": 256,
            "timings": times,
            "checkpoint_sha256": sha256(model_path),
            "dev_reused_saved_predictions": True,
            "capacity_decision": "KEEP_64_CHANNELS_ISOLATE_REPRESENTATION",
            "interpretation": (
                "Bounded TRAIN fit diagnostic is not a full TRAIN/generalization estimate; "
                "poor fit permits but does not require capacity change."
            ),
            "test_accessed": False,
        },
    )
    clips = []
    for rec in rows:
        raw = verify_raw(
            REPO / rec["raw_path"], REPO / rec["raw_receipt_path"], rec, rec["source_sha256"]
        )
        observed = raw.hand_observed.astype(bool)
        both = observed.all(axis=1)
        roi = raw.hand_roi_center_side
        valid_roi = (
            raw.hand_proposal_present.all(axis=1)
            & np.isfinite(roi).all(axis=(1, 2))
            & (roi[:, :, 2] > 0).all(axis=1)
        )
        iou = roi_iou(roi)
        wrist_valid = (raw.hand_joint_valid[:, :, 0] & observed).all(axis=1)
        distance = np.sqrt(
            np.sum((raw.hand_xy[:, 0, 0] - raw.hand_xy[:, 1, 0]) ** 2, axis=1)
        ) / raw.source_size.min(axis=1)
        close = both & valid_roi & wrist_valid & (iou >= 0.6) & (distance <= 0.08)
        only = np.where(
            observed[:, 0] & ~observed[:, 1], 0, np.where(observed[:, 1] & ~observed[:, 0], 1, -1)
        )
        single_switch = (only[1:] >= 0) & (only[:-1] >= 0) & (only[1:] != only[:-1])
        transitions = 0
        for position in np.flatnonzero(single_switch).tolist():
            i = int(position) + 1
            a, b = only[i - 1], only[i]
            if (raw.source_size[i] == raw.source_size[i - 1]).all() and raw.timestamp_ms[
                i
            ] - raw.timestamp_ms[i - 1] <= 1000:
                if raw.hand_joint_valid[i - 1, a, 0] and raw.hand_joint_valid[i, b, 0]:
                    d = (
                        np.linalg.norm(raw.hand_xy[i, b, 0] - raw.hand_xy[i - 1, a, 0])
                        / raw.source_size[i].min()
                    )
                    transitions += int(d <= 0.08)
        clips.append(
            {
                "sample_id": rec["sample_id"],
                "role": rec["split_role"],
                "stratum": rec["source_stratum"],
                "frames": len(raw.frame_index),
                "none": int((~observed.any(axis=1)).sum()),
                "only0": int((only == 0).sum()),
                "only1": int((only == 1).sum()),
                "both": int(both.sum()),
                "overlap_iou_ge_06": int((both & valid_roi & (iou >= 0.6)).sum()),
                "likely_duplicate_proxy": int(close.sum()),
                "single_slot_change": int(single_switch.sum()),
                "spatially_continuous_single_slot_change": transitions,
            }
        )
    keys = [
        "frames",
        "none",
        "only0",
        "only1",
        "both",
        "overlap_iou_ge_06",
        "likely_duplicate_proxy",
        "single_slot_change",
        "spatially_continuous_single_slot_change",
    ]
    groups = {
        name: {k: sum(r[k] for r in clips if predicate(r)) for k in keys}
        for name, predicate in [
            ("all", lambda r: True),
            ("TRAIN", lambda r: r["role"] == "TRAIN"),
            ("DEV", lambda r: r["role"] == "DEV"),
            ("DAUN", lambda r: r["stratum"] == "DAUN"),
            ("MacKenzie", lambda r: r["stratum"] == "MacKenzie"),
        ]
    }
    result = {
        "schema_version": "apphear.fingerspelling.slot_diagnostic.v1",
        "groups": groups,
        "clips": clips,
        "criteria": {
            "overlap_iou": 0.6,
            "duplicate_wrist_distance_short_side": 0.08,
            "continuity_gap_ms": 1000,
        },
        "physical_identity_proven": False,
        "note": (
            "Overlap+close wrists are duplicate proxies, not physical-hand truth. "
            "Single-slot transitions are a conservative lower-bound proxy; "
            "ambiguous dual-slot transitions are not assigned identity."
        ),
        "test_accessed": False,
        "candidate01_rerun": False,
    }
    write_json_atomic(OUT / "slot_diagnostics.json", result)
    return {
        "train": {v: r["metrics"]["cer"] for v, r in views.items()},
        "dev": {v: r["metrics"]["cer"] for v, r in dev.items()},
        "slot_counts": groups,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
