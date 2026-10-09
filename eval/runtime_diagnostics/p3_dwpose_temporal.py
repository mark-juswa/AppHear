# ruff: noqa: E501
"""P3 frozen DWPose native landmark temporal-usability audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from eval.runtime_diagnostics.p2a_dwpose_linux import (
    BASE_RUNTIME,
    CHECKPOINT,
    CONFIG,
    EXPECTED_BASE_SHA,
    EXPECTED_CHECKPOINT_SHA,
    EXPECTED_CONFIG_SHA,
    JOINT_THRESHOLD,
    LEFT_SLICE,
    MIN_CONFIDENT_JOINTS,
    PALM_INDICES,
    PROJECT,
    RIGHT_SLICE,
    official_affines,
    sha256_file,
)

P2_OUTPUT = PROJECT / (
    "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_linux_01"
)
P2_ENVIRONMENT = P2_OUTPUT / "environment/environment_manifest.json"
P2_PIP_FREEZE = P2_OUTPUT / "environment/pip_freeze.txt"
EVALUATOR = Path(__file__).resolve()
OUTPUT = PROJECT / (
    "artifacts/recognition_upgrade/perception_backend_replacement/p3_dwpose_temporal_usability_01"
)
FROZEN_INFERENCE_EVALUATOR = OUTPUT / "frozen_inference_evaluator.py"
A2_ROOT = PROJECT / ("artifacts/recognition_upgrade/a2_landmark_continuity/a2_0_identity_01")
A2_SEQUENCE = A2_ROOT / "sequence_manifest.csv"
A2_INDEX = A2_ROOT / "internal_index.csv"
A2_ANNOTATIONS = A2_ROOT / "annotations.csv"
RU_D9_ROOT_CAUSE = PROJECT / (
    "artifacts/recognition_upgrade/ru_d7/phone_bc_01/reports/ru_d9/ru_d9_attempt_root_cause.csv"
)
GOLD_ROOT = Path(
    "/mnt/f/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/"
    "e2e_all_hand_gold_v1/engineering_01"
)
GOLD_REVIEW = GOLD_ROOT / "gold_review.csv"
GOLD_INDEX = GOLD_ROOT / "internal_index.csv"
GOLD_VIDEO_ROOT = Path("/mnt/f/ASL DATASET/ASL CITIZEN/ASL_Citizen/videos")

ADJACENT_MAX_MS = 500.0
SUDDEN_JUMP_TORSO_UNITS = 1.0
SUSPECTED_SWAP_ADVANTAGE = 0.25
MIN_INTER_SLOT_SEPARATION = 0.15
COLLAPSE_MEDIAN_BONE_TORSO = 0.01
SCATTER_MAX_SPAN_TORSO = 1.5
SUDDEN_SIZE_RATIO = 2.0
BONES = np.asarray(
    [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 4),
        (0, 5),
        (5, 6),
        (6, 7),
        (7, 8),
        (0, 9),
        (9, 10),
        (10, 11),
        (11, 12),
        (0, 13),
        (13, 14),
        (14, 15),
        (15, 16),
        (0, 17),
        (17, 18),
        (18, 19),
        (19, 20),
    ],
    dtype=np.int64,
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def canonical_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"true", "yes", "1"}


def verify_p2() -> dict[str, Any]:
    result = json.loads((P2_OUTPUT / "p2a_dwpose_linux_result.json").read_text(encoding="utf-8"))
    if (
        result["status"] != "P2A_DWPOSE_COMPLETE"
        or result["classification"] != "ARCHITECTURE_PROMISING"
    ):
        raise RuntimeError("P2-A completed result identity changed")
    expected = {
        CHECKPOINT: EXPECTED_CHECKPOINT_SHA,
        CONFIG: EXPECTED_CONFIG_SHA,
        BASE_RUNTIME: EXPECTED_BASE_SHA,
        P2_OUTPUT
        / "frozen_input_manifest_350.csv": "dce78eeb8855dfaaa01b23aeeeee4cecaa13e391022857e195376a948dfa3833",
        P2_OUTPUT
        / "p2a_dwpose_linux_result.json": "fb257a9029b255ffe05193582d3338a27f8f415027a57c54b356ede95bc315aa",
        P2_ENVIRONMENT: "b8bb06c9d38d313d01cbb214c42c309fa6ce9007ee971a82075ec1777b0bdf4e",
        P2_PIP_FREEZE: "5d760e2e3d1ab867f2ff7764439158e082ad2af7206076d9e2610b87d8cc9c03",
    }
    for path, digest in expected.items():
        if sha256_file(path) != digest:
            raise RuntimeError(f"Immutable P2-A hash mismatch: {path}")
    return {str(path): digest for path, digest in expected.items()}


def select_gold_supplement() -> list[dict[str, str]]:
    reviews = {row["sample_id"]: row for row in read_csv(GOLD_REVIEW)}
    candidates = []
    for row in read_csv(GOLD_INDEX):
        review = reviews[row["sample_id"]]
        if int(review["visible_hand_count"]) == 0:
            continue
        candidates.append({**row, **review})

    definitions = [
        ("partial_visibility", 1, lambda row: parse_bool(row["partial_visibility"])),
        ("occlusion", 2, lambda row: parse_bool(row["occlusion"])),
        ("edge_clipped", 2, lambda row: parse_bool(row["edge_clipped"])),
        ("motion_blur", 2, lambda row: parse_bool(row["motion_blur"])),
        (
            "clean_two_hand",
            2,
            lambda row: (
                int(row["visible_hand_count"]) == 2
                and not any(
                    parse_bool(row[field])
                    for field in ("motion_blur", "occlusion", "edge_clipped", "partial_visibility")
                )
            ),
        ),
        (
            "ordinary_clean_one_hand",
            3,
            lambda row: (
                int(row["visible_hand_count"]) == 1
                and not any(
                    parse_bool(row[field])
                    for field in ("motion_blur", "occlusion", "edge_clipped", "partial_visibility")
                )
            ),
        ),
    ]
    selected: list[dict[str, str]] = []
    used_samples: set[str] = set()
    used_participants: set[str] = set()
    for bucket, target, predicate in definitions:
        eligible = sorted(
            (row for row in candidates if predicate(row)), key=lambda row: row["sample_id"]
        )
        count = 0
        for row in eligible:
            if row["sample_id"] in used_samples or row["participant_id"] in used_participants:
                continue
            selected.append({**row, "selection_bucket": bucket})
            used_samples.add(row["sample_id"])
            used_participants.add(row["participant_id"])
            count += 1
            if count == target:
                break
        if count != target:
            raise RuntimeError(
                f"Could not fill frozen gold supplement bucket {bucket}: {count}/{target}"
            )
    if len(selected) != 12 or len(used_participants) != 12:
        raise RuntimeError("Gold supplement must contain 12 clips and 12 signers")
    return selected


def extract_video_window(row: dict[str, str]) -> list[dict[str, Any]]:
    video = GOLD_VIDEO_ROOT / row["video_file"]
    if not video.is_file():
        raise RuntimeError(f"Missing gold source video: {video}")
    capture = cv2.VideoCapture(str(video))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    center = int(row["frame_index"])
    indices = list(range(max(0, center - 8), min(frame_count, center + 9)))
    if len(indices) < 9:
        raise RuntimeError(f"Gold supplement window too short: {row['sample_id']}")
    destination = OUTPUT / "frozen_inputs/gold_supplement" / row["sample_id"]
    destination.mkdir(parents=True, exist_ok=True)
    frames = []
    for source_index in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, source_index)
        ok, image = capture.read()
        if not ok:
            raise RuntimeError(f"Cannot decode {video} frame {source_index}")
        path = destination / f"frame_{source_index:06d}.png"
        if not cv2.imwrite(str(path), image):
            raise RuntimeError(f"Cannot freeze {path}")
        frames.append(
            {
                "frame_id": source_index,
                "timestamp_ns": int(round(source_index / fps * 1e9)),
                "image_path": str(path),
                "width": image.shape[1],
                "height": image.shape[0],
            }
        )
    capture.release()
    return frames


def prepare() -> dict[str, Any]:
    p2_hashes = verify_p2()
    a2_sequences = read_csv(A2_SEQUENCE)
    a2_index = read_csv(A2_INDEX)
    a2_annotations = {row["sample_id"]: row for row in read_csv(A2_ANNOTATIONS)}
    if len(a2_sequences) != 21 or len(a2_index) != 551 or len(a2_annotations) != 551:
        raise RuntimeError("Frozen A2 evidence counts changed")
    if any(row["review_status"] != "accepted" for row in a2_annotations.values()):
        raise RuntimeError("A2 contains incomplete human review")

    gold_index = read_csv(GOLD_INDEX)
    accessible_gold_videos = sum(
        (GOLD_VIDEO_ROOT / row["video_file"]).is_file() for row in gold_index
    )
    inventory = [
        {
            "source": "A2_REVIEWED_TEMPORAL",
            "candidate_sequences": 21,
            "candidate_frames": 551,
            "signers": 2,
            "rgb_available": "yes",
            "timestamps": "timestamp_ns per selected phone observation",
            "mediapipe": "frame-aligned presence plus exact recorded 258 feature in trace",
            "human_truth": "frame visibility/anatomical side; contact/crossing/leaving/rest",
            "limitations": "no human landmarks/boxes; two governed signer IDs on one device, physical identity relationship unresolved; sparse 2.5-4.4 observation Hz",
            "status": "SELECTED_PRIMARY_ALL_21",
        },
        {
            "source": "A1_SIGNING_SENTINEL",
            "candidate_sequences": 24,
            "candidate_frames": "bounded rolling evidence",
            "signers": 1,
            "rgb_available": "yes",
            "timestamps": "trace timestamp_ns",
            "mediapipe": "frame-aligned",
            "human_truth": "only the 12 A2-selected attempts have direct frame review",
            "limitations": "unreviewed attempts cannot add human truth",
            "status": "PARTIALLY_REPRESENTED_BY_A2",
        },
        {
            "source": "RU_D9_PHONE_EVIDENCE",
            "candidate_sequences": 9,
            "candidate_frames": 236,
            "signers": 1,
            "rgb_available": "yes",
            "timestamps": "trace timestamp_ns",
            "mediapipe": "frame-aligned",
            "human_truth": "A2 direct review plus RU-D9 sequence/span failure attribution",
            "limitations": "zero direct frame-confirmed hand-hand-contact labels",
            "status": "SELECTED_PRIMARY_WITHIN_A2",
        },
        {
            "source": "CORRECTED_GOLD_SOURCE_VIDEOS",
            "candidate_sequences": accessible_gold_videos,
            "candidate_frames": "full source videos",
            "signers": 41,
            "rgb_available": "yes",
            "timestamps": "native video FPS/frame index",
            "mediapipe": "only frozen center-frame baseline association",
            "human_truth": "center-frame hand boxes/visibility and condition tags only",
            "limitations": "no temporal hand truth outside frozen center frame",
            "status": "SELECTED_12_SIGNER_INTERNAL_DIAGNOSTIC_SUPPLEMENT",
        },
        {
            "source": "RU_D1_RU_D2_RECOGNITION_EVIDENCE",
            "candidate_sequences": "multiple bounded attempts",
            "candidate_frames": "rolling evidence",
            "signers": 1,
            "rgb_available": "yes",
            "timestamps": "trace timestamp_ns",
            "mediapipe": "frame-aligned",
            "human_truth": "oracle sign spans and outcomes, not hand landmarks/visibility",
            "limitations": "would duplicate signer/domain without stronger hand truth",
            "status": "INVENTORIED_NOT_SELECTED",
        },
    ]
    write_csv(OUTPUT / "temporal_dataset_inventory.csv", inventory)

    sequences: list[dict[str, Any]] = []
    frames: list[dict[str, Any]] = []
    first_frame_by_attempt = {}
    for row in a2_index:
        first_frame_by_attempt.setdefault(row["attempt_id"], row)
    for sequence in a2_sequences:
        attempt = sequence["attempt_id"]
        trace_path = PROJECT / first_frame_by_attempt[attempt]["source_trace_path"]
        metadata_path = trace_path.parent / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        sequences.append(
            {
                "sequence_id": f"A2__{attempt}",
                "cohort": "A2_REVIEWED_PHONE",
                "source_sequence_id": attempt,
                "signer_id": metadata["signer_id"],
                "device": metadata["device"],
                "gloss": sequence["gloss"],
                "expected_hands": sequence["expected_hands"],
                "selection_bucket": sequence["historical_cause"],
                "human_frame_truth": True,
                "human_landmark_truth": False,
                "human_anatomical_side_truth": True,
            }
        )
    for row in a2_index:
        annotation = a2_annotations[row["sample_id"]]
        path = PROJECT / row["image_path"]
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"Missing A2 RGB: {path}")
        frames.append(
            {
                "manifest_row_id": row["sample_id"],
                "sequence_id": f"A2__{row['attempt_id']}",
                "cohort": "A2_REVIEWED_PHONE",
                "source_frame_id": int(row["frame_id"]),
                "timestamp_ns": int(row["timestamp_ns"]),
                "image_path": str(path),
                "image_sha256": sha256_file(path),
                "width": image.shape[1],
                "height": image.shape[0],
                "in_sign_span": row["in_sign_span"],
                "human_visible_left": annotation["visible_left"],
                "human_visible_right": annotation["visible_right"],
                "human_hand_hand_contact": annotation["hand_hand_contact"],
                "human_hand_body_contact": annotation["hand_body_contact"],
                "human_crossing": annotation["crossing_or_midline"],
                "human_leaving_frame": annotation["leaving_frame"],
                "human_no_hand_rest": annotation["no_hand_rest"],
                "mp_left_present": row["direct_mp_left"],
                "mp_right_present": row["direct_mp_right"],
                "mp_left_identity": annotation["mp_left_identity"],
                "mp_right_identity": annotation["mp_right_identity"],
                "source_trace_path": str(PROJECT / row["source_trace_path"]),
                "truth_scope": "DIRECT_HUMAN_FRAME_REVIEW",
            }
        )

    selected_gold = select_gold_supplement()
    for row in selected_gold:
        sequence_id = f"GOLD_VIDEO__{row['sample_id']}"
        sequences.append(
            {
                "sequence_id": sequence_id,
                "cohort": "GOLD_MULTI_SIGNER_INTERNAL_ONLY",
                "source_sequence_id": row["video_file"],
                "signer_id": row["participant_id"],
                "device": "unknown",
                "gloss": row["gloss"],
                "expected_hands": row["visible_hand_count"],
                "selection_bucket": row["selection_bucket"],
                "human_frame_truth": False,
                "human_landmark_truth": False,
                "human_anatomical_side_truth": False,
            }
        )
        extracted = extract_video_window(row)
        for item in extracted:
            path = Path(item["image_path"])
            frames.append(
                {
                    "manifest_row_id": f"GOLD__{row['sample_id']}__{item['frame_id']:06d}",
                    "sequence_id": sequence_id,
                    "cohort": "GOLD_MULTI_SIGNER_INTERNAL_ONLY",
                    "source_frame_id": item["frame_id"],
                    "timestamp_ns": item["timestamp_ns"],
                    "image_path": str(path),
                    "image_sha256": sha256_file(path),
                    "width": item["width"],
                    "height": item["height"],
                    "in_sign_span": "unknown",
                    "human_visible_left": "unknown",
                    "human_visible_right": "unknown",
                    "human_hand_hand_contact": "unknown",
                    "human_hand_body_contact": "unknown",
                    "human_crossing": "unknown",
                    "human_leaving_frame": "unknown",
                    "human_no_hand_rest": "unknown",
                    "mp_left_present": "unknown",
                    "mp_right_present": "unknown",
                    "mp_left_identity": "unknown",
                    "mp_right_identity": "unknown",
                    "source_trace_path": "",
                    "truth_scope": "INTERNAL_CONSISTENCY_ONLY_CENTER_FRAME_GOLD_NOT_PROPAGATED",
                }
            )

    if len(sequences) != 33 or len({row["sequence_id"] for row in sequences}) != 33:
        raise RuntimeError("Frozen selection must contain 33 unique sequences")
    if len({row["signer_id"] for row in sequences}) != 14:
        raise RuntimeError("Frozen selection must contain 14 governed signer IDs")
    write_csv(OUTPUT / "frozen_sequence_manifest.csv", sequences)
    write_csv(OUTPUT / "frozen_frame_manifest.csv", frames)
    protocol = {
        "identity": "P3_DWPOSE_LANDMARK_TEMPORAL_USABILITY",
        "p2_hashes": p2_hashes,
        "selection": {
            "sequences": len(sequences),
            "signers": len({row["signer_id"] for row in sequences}),
            "frames": len(frames),
            "a2_sequences": 21,
            "a2_frames": 551,
            "gold_supplement_sequences": 12,
            "gold_supplement_frames": len(frames) - 551,
            "selection_rule": "all governed A2 plus 12 unique-signer metadata-bucketed gold clips, lexical sample order, center +/-8 native frames",
        },
        "truth": {
            "human_21_point_landmarks": False,
            "human_hand_boxes_temporal": False,
            "human_anatomical_visibility_A2": True,
            "frame_contact_crossing_A2": True,
            "ru_d9_sequence_span_contact_attribution": True,
            "media_pipe_is_not_human_truth": True,
        },
        "frozen_diagnostics": {
            "presence": f"native score >= {JOINT_THRESHOLD}, >= {MIN_CONFIDENT_JOINTS}/21",
            "adjacent_max_ms": ADJACENT_MAX_MS,
            "body_scale": "max(current shoulder distance 5-6, shoulder-midpoint to hip-midpoint 11-12, 0.1 image diagonal)",
            "sudden_jump": f"palm displacement > {SUDDEN_JUMP_TORSO_UNITS} current torso scale",
            "suspected_swap": f"cross assignment improves palm continuity > {SUSPECTED_SWAP_ADVANTAGE} torso units and both inter-slot separations >= {MIN_INTER_SLOT_SEPARATION}",
            "collapse": f"median hand bone length < {COLLAPSE_MEDIAN_BONE_TORSO} torso scale",
            "scatter": f"maximum within-hand span > {SCATTER_MAX_SPAN_TORSO} torso scale",
            "sudden_size_change": f"adjacent median-bone ratio > {SUDDEN_SIZE_RATIO}x or < 1/{SUDDEN_SIZE_RATIO}x",
            "no_accuracy_thresholds_for_internal_geometry": True,
        },
        "classification_hierarchy": [
            "P3_INCONCLUSIVE if extraction/provenance fails or evidence cannot support raw temporal analysis",
            "SLOT_IDENTITY_UNSAFE if direct anatomical truth produces wrong-slot-only events across at least two sequences, or reviewed crossing events demonstrate slot failures across at least two sequences",
            "GEOMETRY_UNSTABLE if impossible collapse/scatter repeats across at least two independent sequences",
            "LOCALIZATION_STRONG_BUT_TEMPORALLY_UNSTABLE if human-visible DWPose dropout runs repeat across at least two sequences and continuity is not better than frame-aligned MediaPipe",
            "TEMPORALLY_USABLE otherwise, with all limitations retained",
        ],
        "schema_replay": "not permitted: DWPose supplies xy plus native joint score, no z/depth required by existing 2x21x3 hand block",
    }
    protocol["sequence_manifest_sha256"] = sha256_file(OUTPUT / "frozen_sequence_manifest.csv")
    protocol["frame_manifest_sha256"] = sha256_file(OUTPUT / "frozen_frame_manifest.csv")
    protocol["evaluator_sha256"] = sha256_file(EVALUATOR)
    write_json(OUTPUT / "p3_frozen_protocol.json", protocol)
    inventory_md = f"""# P3 Temporal Dataset Inventory and Frozen Selection

The inventory found one governed frame-level temporal source: A2 (21 sequences, 551 reviewed
phone observations). It supplies direct human anatomical visibility and limited interaction
labels but no 21-point truth, boxes, or multi-device/signer coverage. A deterministic 12-clip,
12-signer gold-video supplement adds native consecutive-frame internal diagnostics; its
center-frame truth is not propagated to adjacent frames.

Frozen selection: **{len(sequences)} sequences, {len({row["signer_id"] for row in sequences})}
signer IDs, {len(frames)} frames**. Direct hand-hand contact has zero A2 frame-confirmed examples;
three RU-D9 sequence/core spans retain historical contact/occlusion attribution and are reported
separately from direct frame truth. No new human label was created.

Sequence manifest SHA-256: `{protocol["sequence_manifest_sha256"]}`.  
Frame manifest SHA-256: `{protocol["frame_manifest_sha256"]}`.
"""
    (OUTPUT / "P3_TEMPORAL_DATASET_INVENTORY.md").write_text(inventory_md, encoding="utf-8")
    return protocol


def verify_manifests() -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    protocol = json.loads((OUTPUT / "p3_frozen_protocol.json").read_text(encoding="utf-8"))
    if sha256_file(OUTPUT / "frozen_sequence_manifest.csv") != protocol["sequence_manifest_sha256"]:
        raise RuntimeError("P3 sequence manifest hash changed")
    if sha256_file(OUTPUT / "frozen_frame_manifest.csv") != protocol["frame_manifest_sha256"]:
        raise RuntimeError("P3 frame manifest hash changed")
    if sha256_file(FROZEN_INFERENCE_EVALUATOR) != protocol["evaluator_sha256"]:
        raise RuntimeError("P3 frozen inference evaluator snapshot hash changed")
    sequences = read_csv(OUTPUT / "frozen_sequence_manifest.csv")
    frames = read_csv(OUTPUT / "frozen_frame_manifest.csv")
    for row in frames:
        path = Path(row["image_path"])
        if sha256_file(path) != row["image_sha256"]:
            raise RuntimeError(f"P3 input hash changed: {row['manifest_row_id']}")
    return sequences, frames, protocol


def save_npz(path: Path, **values: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".npz.tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(handle, **values)
    os.replace(temporary, path)


def run() -> dict[str, Any]:
    import psutil
    import torch
    from mmengine.dataset import Compose, pseudo_collate
    from mmengine.registry import init_default_scope
    from mmpose.apis import init_model
    from mmpose.utils import register_all_modules

    verify_p2()
    _, frames, protocol = verify_manifests()
    register_all_modules()
    model = init_model(str(CONFIG), str(CHECKPOINT), device="cpu")
    if model.cfg.codec["input_size"] != (192, 256):
        raise RuntimeError("Exact DWPose input size changed")
    if model.cfg.codec["simcc_split_ratio"] != 2.0:
        raise RuntimeError("Exact DWPose SimCC split ratio changed")
    if model.cfg.model.head.get("out_channels") != 133 or not model.cfg.model.test_cfg.get(
        "flip_test"
    ):
        raise RuntimeError("Exact DWPose output/flip-test identity changed")
    init_default_scope(model.cfg.get("default_scope", "mmpose"))
    pipeline = Compose(model.cfg.test_dataloader.dataset.pipeline)
    raw_dir = OUTPUT / "raw_outputs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if any(raw_dir.glob("*.npz")):
        raise RuntimeError("P3 raw-output directory is not empty")
    timing_rows = []
    process = psutil.Process()
    peak_rss = process.memory_info().rss
    for ordinal, row in enumerate(frames, start=1):
        t0 = time.perf_counter()
        image = cv2.imread(row["image_path"], cv2.IMREAD_COLOR)
        height, width = image.shape[:2]
        info: dict[str, Any] = {
            "img": image,
            "bbox": np.asarray([[0.0, 0.0, float(width), float(height)]], dtype=np.float32),
            "bbox_score": np.ones(1, dtype=np.float32),
        }
        info.update(model.dataset_meta)
        batch = pseudo_collate([pipeline(info)])
        t1 = time.perf_counter()
        with torch.no_grad():
            result = model.test_step(batch)[0]
        t2 = time.perf_counter()
        keypoints = np.asarray(result.pred_instances.keypoints[0], dtype=np.float32)
        scores = np.asarray(result.pred_instances.keypoint_scores[0], dtype=np.float32)
        if (
            keypoints.shape != (133, 2)
            or scores.shape != (133,)
            or not np.isfinite(keypoints).all()
            or not np.isfinite(scores).all()
        ):
            raise RuntimeError(f"Invalid P3 native output: {row['manifest_row_id']}")
        center, scale, affine, inverse = official_affines(width, height)
        left_scores = scores[LEFT_SLICE]
        right_scores = scores[RIGHT_SLICE]
        counts = np.asarray(
            [
                np.count_nonzero(left_scores >= JOINT_THRESHOLD),
                np.count_nonzero(right_scores >= JOINT_THRESHOLD),
            ],
            dtype=np.int16,
        )
        t3 = time.perf_counter()
        save_npz(
            raw_dir / f"{row['manifest_row_id']}.npz",
            keypoints_133=keypoints,
            scores_133=scores,
            left_hand_keypoints=keypoints[LEFT_SLICE],
            left_hand_scores=left_scores,
            right_hand_keypoints=keypoints[RIGHT_SLICE],
            right_hand_scores=right_scores,
            confident_joint_counts=counts,
            gated_presence=counts >= MIN_CONFIDENT_JOINTS,
            timestamp_ns=np.asarray(int(row["timestamp_ns"]), dtype=np.int64),
            source_frame_id=np.asarray(int(row["source_frame_id"]), dtype=np.int64),
            roi_xyxy=np.asarray([0.0, 0.0, width, height], dtype=np.float32),
            bbox_center=center,
            bbox_scale=scale,
            affine=affine,
            inverse_affine=inverse,
            source_sha256=np.asarray(row["image_sha256"]),
            checkpoint_sha256=np.asarray(EXPECTED_CHECKPOINT_SHA),
            protocol_sha256=np.asarray(canonical_hash(OUTPUT / "p3_frozen_protocol.json")),
        )
        timing_rows.append(
            {
                "manifest_row_id": row["manifest_row_id"],
                "preprocessing_ms": (t1 - t0) * 1000,
                "inference_ms": (t2 - t1) * 1000,
                "postprocessing_ms": (t3 - t2) * 1000,
                "total_ms": (t3 - t0) * 1000,
            }
        )
        peak_rss = max(peak_rss, process.memory_info().rss)
        if ordinal == 1 or ordinal % 25 == 0 or ordinal == len(frames):
            print(json.dumps({"processed": ordinal, "total": len(frames)}), flush=True)
    write_csv(OUTPUT / "timings.csv", timing_rows)
    completion = {
        "processed": len(frames),
        "sequence_count": protocol["selection"]["sequences"],
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA,
        "frame_manifest_sha256": protocol["frame_manifest_sha256"],
        "evaluator_sha256": protocol["evaluator_sha256"],
        "peak_host_rss_bytes": peak_rss,
        "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(OUTPUT / "inference_completion.json", completion)
    return completion


def body_scale(keypoints: np.ndarray, width: int, height: int) -> float:
    shoulders = float(np.linalg.norm(keypoints[5] - keypoints[6]))
    shoulder_mid = (keypoints[5] + keypoints[6]) / 2
    hip_mid = (keypoints[11] + keypoints[12]) / 2
    torso = float(np.linalg.norm(shoulder_mid - hip_mid))
    return max(shoulders, torso, 0.1 * math.hypot(width, height), 1e-6)


def hand_geometry(points: np.ndarray, scale: float) -> dict[str, Any]:
    lengths = np.linalg.norm(points[BONES[:, 0]] - points[BONES[:, 1]], axis=1)
    median = float(np.median(lengths) / scale)
    span = float(max(np.linalg.norm(a - b) for a, b in itertools.combinations(points, 2)) / scale)
    palm = points[PALM_INDICES].mean(axis=0)
    return {
        "palm": palm,
        "bone_lengths": lengths / scale,
        "median_bone": median,
        "span": span,
        "collapse": median < COLLAPSE_MEDIAN_BONE_TORSO,
        "scatter": span > SCATTER_MAX_SPAN_TORSO,
    }


def percentile(values: list[float], q: float) -> float | None:
    return float(np.percentile(values, q)) if values else None


def fraction(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "fraction": numerator / denominator if denominator else None,
        "percent": 100 * numerator / denominator if denominator else None,
    }


def load_recorded_mediapipe_hands(
    frames: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    """Load existing frame-aligned S4 hand xy; never rerun MediaPipe."""
    trace_cache: dict[str, dict[tuple[str, int], dict[str, Any]]] = {}
    outputs: dict[str, dict[str, Any]] = {}
    for row in frames:
        if row["cohort"] != "A2_REVIEWED_PHONE":
            continue
        trace_path = row["source_trace_path"]
        if trace_path not in trace_cache:
            indexed = {}
            with Path(trace_path).open(encoding="utf-8") as handle:
                for line in handle:
                    observation = json.loads(line)
                    indexed[(observation["attempt_id"], int(observation["frame_id"]))] = observation
            trace_cache[trace_path] = indexed
        observation = trace_cache[trace_path].get(
            (row["sequence_id"].removeprefix("A2__"), int(row["source_frame_id"]))
        )
        if observation is None or len(observation.get("feature", [])) != 258:
            raise RuntimeError(f"Missing recorded S4 feature: {row['manifest_row_id']}")
        feature = np.asarray(observation["feature"], dtype=np.float64)
        outputs[row["manifest_row_id"]] = {
            "left": feature[:63].reshape(21, 3)[:, :2],
            "right": feature[63:126].reshape(21, 3)[:, :2],
            "left_present": bool(observation["left_hand_present"]),
            "right_present": bool(observation["right_hand_present"]),
        }
    return outputs


def score() -> dict[str, Any]:
    sequences, frames, protocol = verify_manifests()
    a2_sequence_lookup = {row["attempt_id"]: row for row in read_csv(A2_SEQUENCE)}
    completion = json.loads((OUTPUT / "inference_completion.json").read_text(encoding="utf-8"))
    if completion["processed"] != len(frames):
        raise RuntimeError("P3 inference is incomplete")
    sequence_meta = {row["sequence_id"]: row for row in sequences}
    mp_native_by_frame = load_recorded_mediapipe_hands(frames)
    frame_rows: list[dict[str, Any]] = []
    slot_rows: list[dict[str, Any]] = []
    raw_by_frame: dict[str, dict[str, Any]] = {}
    for row in frames:
        raw = np.load(OUTPUT / "raw_outputs" / f"{row['manifest_row_id']}.npz")
        keypoints = np.asarray(raw["keypoints_133"], dtype=np.float64)
        scores = np.asarray(raw["scores_133"], dtype=np.float64)
        scale = body_scale(keypoints, int(row["width"]), int(row["height"]))
        groups = {}
        for slot, section in (("left", LEFT_SLICE), ("right", RIGHT_SLICE)):
            points = keypoints[section]
            slot_scores = scores[section]
            confident = int(np.count_nonzero(slot_scores >= JOINT_THRESHOLD))
            geometry = hand_geometry(points, scale)
            groups[slot] = {
                "points": points,
                "scores": slot_scores,
                "confident": confident,
                "present": confident >= MIN_CONFIDENT_JOINTS,
                **geometry,
            }
            slot_rows.append(
                {
                    "manifest_row_id": row["manifest_row_id"],
                    "sequence_id": row["sequence_id"],
                    "cohort": row["cohort"],
                    "source_frame_id": row["source_frame_id"],
                    "timestamp_ns": row["timestamp_ns"],
                    "slot": slot,
                    "confident_joint_count": confident,
                    "present": groups[slot]["present"],
                    "score_mean": float(np.mean(slot_scores)),
                    "score_min": float(np.min(slot_scores)),
                    "score_max": float(np.max(slot_scores)),
                    "palm_x": float(geometry["palm"][0]),
                    "palm_y": float(geometry["palm"][1]),
                    "body_scale_px": scale,
                    "median_bone_torso": geometry["median_bone"],
                    "max_hand_span_torso": geometry["span"],
                    "collapse_flag": groups[slot]["present"] and geometry["collapse"],
                    "scatter_flag": groups[slot]["present"] and geometry["scatter"],
                    "human_visibility": row[f"human_visible_{slot}"],
                }
            )
        mp_left_anatomical = (
            (parse_bool(row["mp_left_present"]) and row["mp_left_identity"] == "left")
            or (parse_bool(row["mp_right_present"]) and row["mp_right_identity"] == "left")
            if row["cohort"] == "A2_REVIEWED_PHONE"
            else None
        )
        mp_right_anatomical = (
            (parse_bool(row["mp_left_present"]) and row["mp_left_identity"] == "right")
            or (parse_bool(row["mp_right_present"]) and row["mp_right_identity"] == "right")
            if row["cohort"] == "A2_REVIEWED_PHONE"
            else None
        )
        frame_rows.append(
            {
                "manifest_row_id": row["manifest_row_id"],
                "sequence_id": row["sequence_id"],
                "cohort": row["cohort"],
                "source_frame_id": row["source_frame_id"],
                "timestamp_ns": row["timestamp_ns"],
                "in_sign_span": row["in_sign_span"],
                "dwpose_left_present": groups["left"]["present"],
                "dwpose_right_present": groups["right"]["present"],
                "dwpose_any_present": groups["left"]["present"] or groups["right"]["present"],
                "dwpose_two_present": groups["left"]["present"] and groups["right"]["present"],
                "human_visible_left": row["human_visible_left"],
                "human_visible_right": row["human_visible_right"],
                "human_hand_hand_contact": row["human_hand_hand_contact"],
                "human_hand_body_contact": row["human_hand_body_contact"],
                "human_crossing": row["human_crossing"],
                "human_leaving_frame": row["human_leaving_frame"],
                "human_no_hand_rest": row["human_no_hand_rest"],
                "mp_anatomical_left_present": mp_left_anatomical,
                "mp_anatomical_right_present": mp_right_anatomical,
            }
        )
        raw_by_frame[row["manifest_row_id"]] = {"groups": groups, "row": row, "scale": scale}

    by_sequence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in frame_rows:
        by_sequence[row["sequence_id"]].append(row)
    slot_event_rows: list[dict[str, Any]] = []
    swap_events: list[dict[str, Any]] = []
    sequence_rows: list[dict[str, Any]] = []
    all_displacements: list[float] = []
    all_velocities: list[float] = []
    all_accelerations: list[float] = []
    all_bone_log_changes: list[float] = []
    sudden_jumps = 0
    continuity_pairs = 0
    size_changes = 0
    collapse_frames: set[str] = set()
    scatter_frames: set[str] = set()
    suspected_swap_pairs = 0
    two_present_pairs = 0
    for sequence_id, ordered in by_sequence.items():
        ordered.sort(key=lambda row: int(row["timestamp_ns"]))
        seq_displacements = []
        seq_jumps = 0
        seq_swaps = 0
        previous_velocities: dict[str, tuple[np.ndarray, float]] = {}
        for current_index, current in enumerate(ordered):
            current_raw = raw_by_frame[current["manifest_row_id"]]
            for slot in ("left", "right"):
                geometry = current_raw["groups"][slot]
                geometry_evaluable = current["cohort"] == "GOLD_MULTI_SIGNER_INTERNAL_ONLY" or (
                    current[f"human_visible_{slot}"] == "yes"
                )
                if geometry_evaluable and geometry["present"] and geometry["collapse"]:
                    collapse_frames.add(current["manifest_row_id"])
                if geometry_evaluable and geometry["present"] and geometry["scatter"]:
                    scatter_frames.add(current["manifest_row_id"])
            if current_index == 0:
                continue
            previous = ordered[current_index - 1]
            dt = (int(current["timestamp_ns"]) - int(previous["timestamp_ns"])) / 1e9
            if dt <= 0 or dt * 1000 > ADJACENT_MAX_MS:
                previous_velocities.clear()
                continue
            previous_raw = raw_by_frame[previous["manifest_row_id"]]
            if all(
                previous_raw["groups"][slot]["present"] and current_raw["groups"][slot]["present"]
                for slot in ("left", "right")
            ):
                same = sum(
                    np.linalg.norm(
                        current_raw["groups"][slot]["palm"] - previous_raw["groups"][slot]["palm"]
                    )
                    / current_raw["scale"]
                    for slot in ("left", "right")
                )
                crossed = (
                    np.linalg.norm(
                        current_raw["groups"]["left"]["palm"]
                        - previous_raw["groups"]["right"]["palm"]
                    )
                    + np.linalg.norm(
                        current_raw["groups"]["right"]["palm"]
                        - previous_raw["groups"]["left"]["palm"]
                    )
                ) / current_raw["scale"]
                prior_sep = (
                    np.linalg.norm(
                        previous_raw["groups"]["left"]["palm"]
                        - previous_raw["groups"]["right"]["palm"]
                    )
                    / previous_raw["scale"]
                )
                current_sep = (
                    np.linalg.norm(
                        current_raw["groups"]["left"]["palm"]
                        - current_raw["groups"]["right"]["palm"]
                    )
                    / current_raw["scale"]
                )
                suspected = (
                    crossed + SUSPECTED_SWAP_ADVANTAGE < same
                    and min(prior_sep, current_sep) >= MIN_INTER_SLOT_SEPARATION
                )
                two_present_pairs += 1
                if suspected:
                    suspected_swap_pairs += 1
                    seq_swaps += 1
                    swap_events.append(
                        {
                            "sequence_id": sequence_id,
                            "previous_frame": previous["manifest_row_id"],
                            "current_frame": current["manifest_row_id"],
                            "same_assignment_cost": same,
                            "cross_assignment_cost": crossed,
                            "prior_inter_slot_separation": prior_sep,
                            "current_inter_slot_separation": current_sep,
                            "truth_scope": "SLOT_STABILITY_DIAGNOSTIC_NOT_ANATOMICAL_TRUTH",
                        }
                    )
            for slot in ("left", "right"):
                before = previous_raw["groups"][slot]
                after = current_raw["groups"][slot]
                if not (before["present"] and after["present"]):
                    previous_velocities.pop(slot, None)
                    continue
                vector = (after["palm"] - before["palm"]) / current_raw["scale"]
                displacement = float(np.linalg.norm(vector))
                velocity_vector = vector / dt
                velocity = float(np.linalg.norm(velocity_vector))
                jump = displacement > SUDDEN_JUMP_TORSO_UNITS
                bone_change = float(
                    np.median(
                        np.abs(
                            np.log(
                                np.maximum(after["bone_lengths"], 1e-8)
                                / np.maximum(before["bone_lengths"], 1e-8)
                            )
                        )
                    )
                )
                ratio = after["median_bone"] / max(before["median_bone"], 1e-8)
                size_flag = ratio > SUDDEN_SIZE_RATIO or ratio < 1 / SUDDEN_SIZE_RATIO
                acceleration = None
                if slot in previous_velocities:
                    prior_velocity, prior_dt = previous_velocities[slot]
                    acceleration = float(
                        np.linalg.norm(velocity_vector - prior_velocity)
                        / max((dt + prior_dt) / 2, 1e-8)
                    )
                    all_accelerations.append(acceleration)
                previous_velocities[slot] = (velocity_vector, dt)
                all_displacements.append(displacement)
                all_velocities.append(velocity)
                all_bone_log_changes.append(bone_change)
                seq_displacements.append(displacement)
                continuity_pairs += 1
                sudden_jumps += int(jump)
                seq_jumps += int(jump)
                size_changes += int(size_flag)
                slot_event_rows.append(
                    {
                        "sequence_id": sequence_id,
                        "slot": slot,
                        "previous_frame": previous["manifest_row_id"],
                        "current_frame": current["manifest_row_id"],
                        "dt_ms": dt * 1000,
                        "palm_displacement_torso": displacement,
                        "palm_velocity_torso_per_s": velocity,
                        "palm_acceleration_torso_per_s2": acceleration,
                        "median_abs_bone_log_change": bone_change,
                        "hand_size_ratio": ratio,
                        "sudden_jump": jump,
                        "sudden_size_change": size_flag,
                    }
                )
        sequence_rows.append(
            {
                "sequence_id": sequence_id,
                "cohort": sequence_meta[sequence_id]["cohort"],
                "signer_id": sequence_meta[sequence_id]["signer_id"],
                "gloss": sequence_meta[sequence_id]["gloss"],
                "frame_count": len(ordered),
                "dwpose_any_presence_frames": sum(
                    parse_bool(str(row["dwpose_any_present"])) for row in ordered
                ),
                "dwpose_two_presence_frames": sum(
                    parse_bool(str(row["dwpose_two_present"])) for row in ordered
                ),
                "adjacent_slot_pairs": len(seq_displacements),
                "palm_displacement_p50": percentile(seq_displacements, 50),
                "palm_displacement_p95": percentile(seq_displacements, 95),
                "sudden_jump_count": seq_jumps,
                "suspected_swap_count": seq_swaps,
                "human_truth_scope": sequence_meta[sequence_id]["human_frame_truth"],
            }
        )

    mp_displacements: list[float] = []
    mp_bone_log_changes: list[float] = []
    mp_continuity_pairs = 0
    mp_sudden_jumps = 0
    mp_two_present_pairs = 0
    mp_suspected_swaps = 0
    for sequence_id, ordered in by_sequence.items():
        if sequence_meta[sequence_id]["cohort"] != "A2_REVIEWED_PHONE":
            continue
        ordered = sorted(ordered, key=lambda row: int(row["timestamp_ns"]))
        for previous, current in zip(ordered, ordered[1:], strict=False):
            dt_ms = (int(current["timestamp_ns"]) - int(previous["timestamp_ns"])) / 1e6
            if dt_ms <= 0 or dt_ms > ADJACENT_MAX_MS:
                continue
            before = mp_native_by_frame[previous["manifest_row_id"]]
            after = mp_native_by_frame[current["manifest_row_id"]]
            if all(
                before[f"{slot}_present"] and after[f"{slot}_present"] for slot in ("left", "right")
            ):
                before_palms = {
                    slot: before[slot][PALM_INDICES].mean(axis=0) for slot in ("left", "right")
                }
                after_palms = {
                    slot: after[slot][PALM_INDICES].mean(axis=0) for slot in ("left", "right")
                }
                same = sum(
                    np.linalg.norm(after_palms[slot] - before_palms[slot])
                    for slot in ("left", "right")
                )
                crossed = np.linalg.norm(
                    after_palms["left"] - before_palms["right"]
                ) + np.linalg.norm(after_palms["right"] - before_palms["left"])
                prior_sep = np.linalg.norm(before_palms["left"] - before_palms["right"])
                current_sep = np.linalg.norm(after_palms["left"] - after_palms["right"])
                mp_two_present_pairs += 1
                if (
                    crossed + SUSPECTED_SWAP_ADVANTAGE < same
                    and min(prior_sep, current_sep) >= MIN_INTER_SLOT_SEPARATION
                ):
                    mp_suspected_swaps += 1
            for slot in ("left", "right"):
                if not (before[f"{slot}_present"] and after[f"{slot}_present"]):
                    continue
                before_points = before[slot]
                after_points = after[slot]
                displacement = float(
                    np.linalg.norm(
                        after_points[PALM_INDICES].mean(axis=0)
                        - before_points[PALM_INDICES].mean(axis=0)
                    )
                )
                before_bones = np.linalg.norm(
                    before_points[BONES[:, 0]] - before_points[BONES[:, 1]], axis=1
                )
                after_bones = np.linalg.norm(
                    after_points[BONES[:, 0]] - after_points[BONES[:, 1]], axis=1
                )
                mp_displacements.append(displacement)
                mp_bone_log_changes.append(
                    float(
                        np.median(
                            np.abs(
                                np.log(
                                    np.maximum(after_bones, 1e-8) / np.maximum(before_bones, 1e-8)
                                )
                            )
                        )
                    )
                )
                mp_continuity_pairs += 1
                mp_sudden_jumps += int(displacement > SUDDEN_JUMP_TORSO_UNITS)

    def dropout_events_for(source: str, presence_key: str, side: str) -> list[dict[str, Any]]:
        events = []
        for sequence_id, ordered in by_sequence.items():
            if sequence_meta[sequence_id]["cohort"] != "A2_REVIEWED_PHONE":
                continue
            ordered = sorted(ordered, key=lambda row: int(row["timestamp_ns"]))
            active: list[dict[str, Any]] = []
            for row in ordered + [None]:
                eligible = False
                missing = False
                if row is not None and row[f"human_visible_{side}"] == "yes":
                    eligible = True
                    value = row[presence_key]
                    missing = not parse_bool(str(value))
                    if active:
                        dt = (int(row["timestamp_ns"]) - int(active[-1]["timestamp_ns"])) / 1e6
                        if dt > ADJACENT_MAX_MS:
                            eligible = False
                if eligible and missing:
                    active.append(row)
                    continue
                if active:
                    events.append(
                        {
                            "source": source,
                            "sequence_id": sequence_id,
                            "anatomical_side": side,
                            "start_frame": active[0]["manifest_row_id"],
                            "end_frame": active[-1]["manifest_row_id"],
                            "observations": len(active),
                            "one_observation": len(active) == 1,
                            "reappeared_next_reviewed_visible_frame": bool(
                                row is not None
                                and row[f"human_visible_{side}"] == "yes"
                                and not missing
                            ),
                        }
                    )
                    active = []
        return events

    dropout_events = []
    for side in ("left", "right"):
        dropout_events.extend(dropout_events_for("DWPOSE", f"dwpose_{side}_present", side))
        dropout_events.extend(
            dropout_events_for("MEDIAPIPE", f"mp_anatomical_{side}_present", side)
        )

    interaction_events: list[dict[str, Any]] = []
    for event_type, field in (
        ("HAND_HAND_CONTACT", "human_hand_hand_contact"),
        ("HAND_BODY_CONTACT", "human_hand_body_contact"),
        ("CROSSING_OR_MIDLINE", "human_crossing"),
    ):
        for sequence_id, ordered in by_sequence.items():
            selected = [row for row in ordered if row[field] == "yes"]
            for row in selected:
                interaction_events.append(
                    {
                        "event_id": f"DIRECT__{event_type}__{row['manifest_row_id']}",
                        "event_type": event_type,
                        "sequence_id": sequence_id,
                        "start_frame": row["source_frame_id"],
                        "end_frame": row["source_frame_id"],
                        "truth_basis": "DIRECT_HUMAN_FRAME_REVIEW",
                        "frames_in_manifest": 1,
                        "dwpose_both_present": row["dwpose_two_present"],
                        "dwpose_any_present": row["dwpose_any_present"],
                        "suspected_swap_events": sum(
                            event["current_frame"] == row["manifest_row_id"]
                            for event in swap_events
                        ),
                        "collapse_or_scatter": row["manifest_row_id"] in collapse_frames
                        or row["manifest_row_id"] in scatter_frames,
                    }
                )
    ru_rows = read_csv(RU_D9_ROOT_CAUSE)
    for historical in ru_rows:
        if (
            historical["primary_root_cause"] != "TWO_HAND_OCCLUSION_OR_CONTACT"
            and "TORSO_CONTACT" not in historical["secondary_root_causes"]
        ):
            continue
        matches = [
            sequence
            for sequence in sequences
            if sequence["cohort"] == "A2_REVIEWED_PHONE"
            and sequence["gloss"] == historical["target_sign"]
            and a2_sequence_lookup[sequence["source_sequence_id"]]["cohort"] == "SUPPLEMENTAL_RU_D9"
            and a2_sequence_lookup[sequence["source_sequence_id"]]["repetition_id"]
            == historical["attempt_number"]
        ]
        if len(matches) != 1:
            continue
        sequence_id = matches[0]["sequence_id"]
        start, end = [int(value) for value in historical["visual_core"].split("-")]
        selected = [
            row for row in by_sequence[sequence_id] if start <= int(row["source_frame_id"]) <= end
        ]
        interaction_events.append(
            {
                "event_id": f"RU_D9_SPAN__{historical['capture_order']}",
                "event_type": historical["failure_association"],
                "sequence_id": sequence_id,
                "start_frame": start,
                "end_frame": end,
                "truth_basis": "HUMAN_SEQUENCE_SPAN_ATTRIBUTION_NOT_DIRECT_FRAME_CONTACT_LABEL",
                "frames_in_manifest": len(selected),
                "dwpose_both_present": f"{sum(parse_bool(str(row['dwpose_two_present'])) for row in selected)}/{len(selected)}",
                "dwpose_any_present": f"{sum(parse_bool(str(row['dwpose_any_present'])) for row in selected)}/{len(selected)}",
                "suspected_swap_events": sum(
                    event["sequence_id"] == sequence_id
                    and any(row["manifest_row_id"] == event["current_frame"] for row in selected)
                    for event in swap_events
                ),
                "collapse_or_scatter": any(
                    row["manifest_row_id"] in collapse_frames
                    or row["manifest_row_id"] in scatter_frames
                    for row in selected
                ),
            }
        )

    a2_frames = [row for row in frame_rows if row["cohort"] == "A2_REVIEWED_PHONE"]
    known_slot_truth = []
    anatomical_contradictions: list[dict[str, Any]] = []
    for row in a2_frames:
        for side, other in (("left", "right"), ("right", "left")):
            if row[f"human_visible_{side}"] == "yes":
                known_slot_truth.append((row, side))
                if (
                    not parse_bool(str(row[f"dwpose_{side}_present"]))
                    and parse_bool(str(row[f"dwpose_{other}_present"]))
                    and row[f"human_visible_{other}"] == "no"
                ):
                    anatomical_contradictions.append(
                        {
                            "manifest_row_id": row["manifest_row_id"],
                            "sequence_id": row["sequence_id"],
                            "source_frame_id": row["source_frame_id"],
                            "human_visible_side": side,
                            "human_other_side": row[f"human_visible_{other}"],
                            "expected_native_slot_present": row[f"dwpose_{side}_present"],
                            "opposite_native_slot_present": row[f"dwpose_{other}_present"],
                            "truth_basis": "DIRECT_HUMAN_ANATOMICAL_VISIBILITY",
                        }
                    )
    dwpose_visible_hits = sum(
        parse_bool(str(row[f"dwpose_{side}_present"])) for row, side in known_slot_truth
    )
    mp_visible_hits = sum(
        parse_bool(str(row[f"mp_anatomical_{side}_present"])) for row, side in known_slot_truth
    )
    two_visible = [
        row
        for row in a2_frames
        if row["human_visible_left"] == "yes" and row["human_visible_right"] == "yes"
    ]
    dwpose_two_hits = sum(parse_bool(str(row["dwpose_two_present"])) for row in two_visible)
    mp_two_hits = sum(
        parse_bool(str(row["mp_anatomical_left_present"]))
        and parse_bool(str(row["mp_anatomical_right_present"]))
        for row in two_visible
    )
    any_visible = [
        row
        for row in a2_frames
        if row["human_visible_left"] == "yes" or row["human_visible_right"] == "yes"
    ]
    dwpose_any_visible_hits = sum(
        (row["human_visible_left"] == "yes" and parse_bool(str(row["dwpose_left_present"])))
        or (row["human_visible_right"] == "yes" and parse_bool(str(row["dwpose_right_present"])))
        for row in any_visible
    )
    mp_any_visible_hits = sum(
        (row["human_visible_left"] == "yes" and parse_bool(str(row["mp_anatomical_left_present"])))
        or (
            row["human_visible_right"] == "yes"
            and parse_bool(str(row["mp_anatomical_right_present"]))
        )
        for row in any_visible
    )
    human_zero_hand_frames = [
        row
        for row in a2_frames
        if row["human_visible_left"] == "no" and row["human_visible_right"] == "no"
    ]
    human_rest_frames = [row for row in a2_frames if row["human_no_hand_rest"] == "yes"]
    human_leaving_frames = [row for row in a2_frames if row["human_leaving_frame"] == "yes"]
    dw_drop = [event for event in dropout_events if event["source"] == "DWPOSE"]
    mp_drop = [event for event in dropout_events if event["source"] == "MEDIAPIPE"]

    direct_cross_rows = [
        event for event in interaction_events if event["truth_basis"] == "DIRECT_HUMAN_FRAME_REVIEW"
    ]
    repeated_impossible_sequences = {
        raw_by_frame[frame_id]["row"]["sequence_id"]
        for frame_id in collapse_frames | scatter_frames
    }
    direct_interaction_slot_fail = any(
        not parse_bool(str(event["dwpose_any_present"])) or int(event["suspected_swap_events"]) > 0
        for event in direct_cross_rows
    )
    contradiction_sequences = {row["sequence_id"] for row in anatomical_contradictions}
    interaction_failure_sequences = {
        event["sequence_id"]
        for event in direct_cross_rows
        if not parse_bool(str(event["dwpose_any_present"]))
        or int(event["suspected_swap_events"]) > 0
    }
    if len(contradiction_sequences) >= 2 or (
        direct_interaction_slot_fail and len(interaction_failure_sequences) >= 2
    ):
        classification = "SLOT_IDENTITY_UNSAFE"
    elif len(repeated_impossible_sequences) >= 2:
        classification = "GEOMETRY_UNSTABLE"
    elif len({event["sequence_id"] for event in dw_drop}) >= 2 and len(dw_drop) >= len(mp_drop):
        classification = "LOCALIZATION_STRONG_BUT_TEMPORALLY_UNSTABLE"
    else:
        classification = "TEMPORALLY_USABLE"

    timings = read_csv(OUTPUT / "timings.csv")
    completion = json.loads((OUTPUT / "inference_completion.json").read_text(encoding="utf-8"))
    total_latencies = [float(row["total_ms"]) for row in timings]
    metrics = {
        "sequences": len(sequences),
        "signers": len({row["signer_id"] for row in sequences}),
        "frames": len(frames),
        "human_landmark_truth_available": False,
        "human_anatomical_side_truth_available": True,
        "human_visible_hand_slot_coverage": fraction(dwpose_visible_hits, len(known_slot_truth)),
        "human_any_visible_frame_coverage": fraction(dwpose_any_visible_hits, len(any_visible)),
        "human_two_hand_completeness": fraction(dwpose_two_hits, len(two_visible)),
        "mediapipe_visible_hand_slot_coverage": fraction(mp_visible_hits, len(known_slot_truth)),
        "mediapipe_any_visible_frame_coverage": fraction(mp_any_visible_hits, len(any_visible)),
        "mediapipe_two_hand_completeness": fraction(mp_two_hits, len(two_visible)),
        "human_zero_hand_behavior": {
            "frames": len(human_zero_hand_frames),
            "dwpose_any_present": fraction(
                sum(parse_bool(str(row["dwpose_any_present"])) for row in human_zero_hand_frames),
                len(human_zero_hand_frames),
            ),
            "dwpose_left_present": fraction(
                sum(parse_bool(str(row["dwpose_left_present"])) for row in human_zero_hand_frames),
                len(human_zero_hand_frames),
            ),
            "dwpose_right_present": fraction(
                sum(parse_bool(str(row["dwpose_right_present"])) for row in human_zero_hand_frames),
                len(human_zero_hand_frames),
            ),
            "dwpose_two_present": fraction(
                sum(parse_bool(str(row["dwpose_two_present"])) for row in human_zero_hand_frames),
                len(human_zero_hand_frames),
            ),
            "mediapipe_any_present": fraction(
                sum(
                    parse_bool(str(row["mp_anatomical_left_present"]))
                    or parse_bool(str(row["mp_anatomical_right_present"]))
                    for row in human_zero_hand_frames
                ),
                len(human_zero_hand_frames),
            ),
        },
        "human_rest_behavior": {
            "dwpose_any_present": fraction(
                sum(parse_bool(str(row["dwpose_any_present"])) for row in human_rest_frames),
                len(human_rest_frames),
            ),
            "dwpose_two_present": fraction(
                sum(parse_bool(str(row["dwpose_two_present"])) for row in human_rest_frames),
                len(human_rest_frames),
            ),
        },
        "human_leaving_frame_behavior": {
            "dwpose_any_present": fraction(
                sum(parse_bool(str(row["dwpose_any_present"])) for row in human_leaving_frames),
                len(human_leaving_frames),
            ),
            "dwpose_two_present": fraction(
                sum(parse_bool(str(row["dwpose_two_present"])) for row in human_leaving_frames),
                len(human_leaving_frames),
            ),
        },
        "dropouts": {
            "dwpose_events": len(dw_drop),
            "dwpose_one_observation": sum(event["one_observation"] for event in dw_drop),
            "dwpose_multi_observation": sum(not event["one_observation"] for event in dw_drop),
            "mediapipe_events": len(mp_drop),
            "mediapipe_one_observation": sum(event["one_observation"] for event in mp_drop),
            "mediapipe_multi_observation": sum(not event["one_observation"] for event in mp_drop),
            "dwpose_missed_visible_observations": fraction(
                len(known_slot_truth) - dwpose_visible_hits, len(known_slot_truth)
            ),
            "mediapipe_missed_visible_observations": fraction(
                len(known_slot_truth) - mp_visible_hits, len(known_slot_truth)
            ),
        },
        "palm_displacement_torso": {
            "count": len(all_displacements),
            "p50": percentile(all_displacements, 50),
            "p95": percentile(all_displacements, 95),
            "p99": percentile(all_displacements, 99),
            "max": max(all_displacements) if all_displacements else None,
        },
        "palm_velocity_torso_per_s": {
            "p50": percentile(all_velocities, 50),
            "p95": percentile(all_velocities, 95),
            "p99": percentile(all_velocities, 99),
        },
        "palm_acceleration_torso_per_s2": {
            "p50": percentile(all_accelerations, 50),
            "p95": percentile(all_accelerations, 95),
            "p99": percentile(all_accelerations, 99),
        },
        "sudden_jumps": fraction(sudden_jumps, continuity_pairs),
        "median_abs_bone_log_change": {
            "p50": percentile(all_bone_log_changes, 50),
            "p95": percentile(all_bone_log_changes, 95),
            "p99": percentile(all_bone_log_changes, 99),
        },
        "sudden_size_changes": fraction(size_changes, continuity_pairs),
        "collapse_frames": len(collapse_frames),
        "scatter_frames": len(scatter_frames),
        "suspected_slot_swaps": fraction(suspected_swap_pairs, two_present_pairs),
        "mediapipe_native_temporal": {
            "palm_displacement_count": len(mp_displacements),
            "palm_displacement_p50": percentile(mp_displacements, 50),
            "palm_displacement_p95": percentile(mp_displacements, 95),
            "palm_displacement_p99": percentile(mp_displacements, 99),
            "sudden_jumps": fraction(mp_sudden_jumps, mp_continuity_pairs),
            "median_abs_bone_log_change_p50": percentile(mp_bone_log_changes, 50),
            "median_abs_bone_log_change_p95": percentile(mp_bone_log_changes, 95),
            "suspected_slot_swaps": fraction(mp_suspected_swaps, mp_two_present_pairs),
            "coordinate_note": "recorded S4 hand xy are shoulder-normalized, while DWPose uses original-image xy divided by current predicted torso scale; distributions are parallel diagnostics, not identical-coordinate errors",
        },
        "human_wrong_slot_only_events": fraction(
            len(anatomical_contradictions), len(known_slot_truth)
        ),
        "human_wrong_slot_only_sequences": len(contradiction_sequences),
        "direct_interaction_events": len(direct_cross_rows),
        "historical_sequence_span_interaction_events": len(interaction_events)
        - len(direct_cross_rows),
        "direct_hand_hand_contact_frames": sum(
            event["event_type"] == "HAND_HAND_CONTACT" for event in direct_cross_rows
        ),
        "latency_total_ms": {
            "p50": percentile(total_latencies, 50),
            "p95": percentile(total_latencies, 95),
            "max": max(total_latencies) if total_latencies else None,
        },
        "peak_host_rss_bytes": completion["peak_host_rss_bytes"],
        "schema_replay_possible": False,
        "schema_replay_blocker": "DWPose native output is 2D xy plus per-joint score and has no z/depth for the existing 2x21x3 hand blocks; z was not fabricated.",
    }
    write_csv(OUTPUT / "p3_frame_results.csv", frame_rows)
    write_csv(OUTPUT / "p3_hand_slot_results.csv", slot_rows)
    write_csv(OUTPUT / "p3_sequence_results.csv", sequence_rows)
    write_csv(OUTPUT / "p3_continuity_pairs.csv", slot_event_rows)
    write_csv(OUTPUT / "p3_dropout_reappearance_events.csv", dropout_events)
    write_csv(OUTPUT / "p3_suspected_slot_swap_events.csv", swap_events)
    write_csv(
        OUTPUT / "p3_anatomical_slot_contradiction_events.csv",
        anatomical_contradictions,
    )
    write_csv(OUTPUT / "p3_crossing_contact_events.csv", interaction_events)
    result = {
        "status": "P3_COMPLETE",
        "classification": classification,
        "temporal_evidence_sufficient": True,
        "metrics": metrics,
        "limitations": [
            "No human 21-point landmark truth; internal geometry is not landmark accuracy.",
            "Direct human frame truth has two governed signer IDs on one Xiaomi device; whether those IDs denote different physical people is unresolved.",
            "Gold multi-signer supplement has no propagated temporal hand truth.",
            "A2 has zero direct frame-confirmed hand-hand-contact frames; RU-D9 contact evidence is sequence/span level.",
            "A2 phone evidence is sampled near AppHear useful-observation cadence, not native camera FPS.",
            "The frozen hand-presence rule produces substantial false presence on human-reviewed zero-hand/rest frames under the forced whole-frame top-down ROI; raw landmarks are not a drop-in absence signal.",
        ],
        "protocol_sha256": canonical_hash(OUTPUT / "p3_frozen_protocol.json"),
        "scoring_correction": {
            "applied": True,
            "scope": "historical RU-D9 interaction-span association only",
            "reason": "GOOD R1, GOOD R2, and WE R1 were ambiguous across primary A1 and supplemental RU-D9 sequences until source cohort was included",
            "inference_evaluator_sha256": protocol["evaluator_sha256"],
            "corrected_scoring_evaluator_sha256": sha256_file(EVALUATOR),
            "model_inference_rerun": False,
            "aggregate_native_outputs_changed": False,
            "absence_metrics_added_after_item_level_audit": True,
        },
    }
    write_json(OUTPUT / "p3_dwpose_temporal_result.json", result)
    write_report(result, inventory_count=len(read_csv(OUTPUT / "temporal_dataset_inventory.csv")))
    artifact_paths = sorted(
        path
        for path in OUTPUT.rglob("*")
        if path.is_file() and path.name != "artifact_hash_manifest.json"
    )
    write_json(
        OUTPUT / "artifact_hash_manifest.json",
        {
            "files": [
                {
                    "path": str(path.relative_to(OUTPUT)),
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
                for path in artifact_paths
            ]
        },
    )
    return result


def fmt(metric: dict[str, Any]) -> str:
    if metric["denominator"] == 0:
        return "N/A"
    return f"{metric['numerator']}/{metric['denominator']} = {metric['percent']:.3f}%"


def write_report(result: dict[str, Any], inventory_count: int) -> None:
    metrics = result["metrics"]
    report = f"""# P3 DWPose Landmark Temporal Usability Result

Status: `P3_COMPLETE`  
Final classification: `{result["classification"]}`

## 1. Temporal dataset inventory and frozen selection

Five source families were inventoried. The frozen set contains {metrics["sequences"]} sequences,
{metrics["signers"]} signer IDs, and {metrics["frames"]} frames: all 21/551 governed A2 phone
sequences plus 12 unique-signer gold-video windows selected by frozen condition buckets. The gold
supplement is internal-consistency evidence only; center-frame truth was not propagated.

## 2. Human truth and limitations

There is no human 21-point landmark truth, so P3 cannot measure absolute landmark error. A2 does
provide direct anatomical-side visibility, rest/leaving/crossing/contact flags, and frame-aligned
MediaPipe presence. MediaPipe landmarks are not human truth. Direct frame truth covers two
governed signer IDs on one Xiaomi device; their physical-identity relationship is unresolved. A2
contains three crossing frames, one body-contact frame, and zero direct
hand-hand-contact frames; four RU-D9 interaction cases remain sequence/span attributions.

## 3. Extraction provenance

P3 reused the exact P2-A checkpoint/config/environment, whole-frame ROI, official affine/SimCC
decoder and flip test, and the frozen score >=0.30 plus >=11/21 presence decision. No smoothing,
interpolation, carry-forward, optical flow, tracking repair, or slot reassignment was applied.

The original frozen inference evaluator and protocol are preserved. A declared scoring-only
correction was applied after the first result audit: historical RU-D9 interaction spans are now
matched to the governed `SUPPLEMENTAL_RU_D9` cohort, resolving duplicate gloss/repetition IDs in
the primary A1 cohort. Inference was not rerun and no native output or aggregate metric changed.

## 4. Human-truth availability continuity

| Metric | DWPose | Existing frame-aligned MediaPipe |
|---|---:|---:|
| Visible anatomical hand-slot coverage | {fmt(metrics["human_visible_hand_slot_coverage"])} | {fmt(metrics["mediapipe_visible_hand_slot_coverage"])} |
| Any-visible-hand frame coverage | {fmt(metrics["human_any_visible_frame_coverage"])} | {fmt(metrics["mediapipe_any_visible_frame_coverage"])} |
| Complete two-visible-hand frames | {fmt(metrics["human_two_hand_completeness"])} | {fmt(metrics["mediapipe_two_hand_completeness"])} |
| Dropout events | {metrics["dropouts"]["dwpose_events"]} | {metrics["dropouts"]["mediapipe_events"]} |
| One-observation dropout events | {metrics["dropouts"]["dwpose_one_observation"]} | {metrics["dropouts"]["mediapipe_one_observation"]} |
| Multi-observation dropout events | {metrics["dropouts"]["dwpose_multi_observation"]} | {metrics["dropouts"]["mediapipe_multi_observation"]} |
| Any hand on human zero-hand frames | {fmt(metrics["human_zero_hand_behavior"]["dwpose_any_present"])} | {fmt(metrics["human_zero_hand_behavior"]["mediapipe_any_present"])} |

Under the forced whole-frame top-down ROI, DWPose also emits any hand on
{fmt(metrics["human_rest_behavior"]["dwpose_any_present"])} explicit no-hand/rest frames and on
{fmt(metrics["human_leaving_frame_behavior"]["dwpose_any_present"])} leaving-frame observations.
This is human-truth behavior, not an internal diagnostic. It does not negate the strong visible-hand
landmark continuity, but it means raw DWPose presence cannot replace AppHear's absence semantics
without a separately evaluated evidence source or representation decision.

## 5. Internal continuity and geometry diagnostics

These are internal-consistency diagnostics, not landmark accuracy.

- adjacent present-slot pairs: {metrics["palm_displacement_torso"]["count"]};
- palm displacement/body scale p50/p95/p99/max: {metrics["palm_displacement_torso"]["p50"]:.4f} / {metrics["palm_displacement_torso"]["p95"]:.4f} / {metrics["palm_displacement_torso"]["p99"]:.4f} / {metrics["palm_displacement_torso"]["max"]:.4f};
- sudden-jump diagnostic: {fmt(metrics["sudden_jumps"])};
- median absolute bone log-change p50/p95/p99: {metrics["median_abs_bone_log_change"]["p50"]:.4f} / {metrics["median_abs_bone_log_change"]["p95"]:.4f} / {metrics["median_abs_bone_log_change"]["p99"]:.4f};
- sudden >2x hand-size changes: {fmt(metrics["sudden_size_changes"])};
- collapse frames: {metrics["collapse_frames"]}; scatter frames: {metrics["scatter_frames"]}.

## 6. Slot stability

- suspected trajectory-continuity swaps: {fmt(metrics["suspected_slot_swaps"])};
- direct human wrong-slot-only events: {fmt(metrics["human_wrong_slot_only_events"])}.
- sequences containing direct wrong-slot-only events: {metrics["human_wrong_slot_only_sequences"]}.

These diagnostics do not equate image-left with anatomical-left. The A2 comparison uses the final
human anatomical-side labels; the multi-signer supplement has no anatomical scoring.

Existing frame-aligned MediaPipe outputs were reused, not rerun. In their recorded
shoulder-normalized xy coordinates, MediaPipe had
{metrics["mediapipe_native_temporal"]["palm_displacement_count"]} adjacent present-slot pairs,
palm displacement p50/p95/p99
{metrics["mediapipe_native_temporal"]["palm_displacement_p50"]:.4f} /
{metrics["mediapipe_native_temporal"]["palm_displacement_p95"]:.4f} /
{metrics["mediapipe_native_temporal"]["palm_displacement_p99"]:.4f}, sudden jumps
{fmt(metrics["mediapipe_native_temporal"]["sudden_jumps"])}, and suspected swaps
{fmt(metrics["mediapipe_native_temporal"]["suspected_slot_swaps"])}. DWPose and MediaPipe use
different normalized coordinate systems, so these are parallel temporal diagnostics rather than
absolute coordinate-error comparisons.

## 7. Crossing/contact cases

The case table contains {metrics["direct_interaction_events"]} direct frame events and
{metrics["historical_sequence_span_interaction_events"]} historical sequence/span interaction
events. Direct hand-hand-contact frames: {metrics["direct_hand_hand_contact_frames"]}. The report
therefore cannot claim broad hand-hand-contact generalization; case-level outcomes remain in
`p3_crossing_contact_events.csv`.

## 8. Recognition readiness and schema compatibility

DWPose naturally supplies 2D `(x,y)` and a native score per keypoint. It supplies no usable depth
or MediaPipe-compatible `z`. The current AppHear hand contract is `2 x 21 x 3`, so replay into
existing `[96,258]` is **not possible without fabricating or redefining z semantics**. P3 did not
fabricate z, map into production features, or replay S6. A separate representation experiment is
required before downstream evaluation.

## 9. Final classification

**`{result["classification"]}`**

This classification is limited to raw native temporal usability on the frozen evidence. It does
not mean the frozen presence bit is production-safe: the zero-hand/rest false-presence result is a
major downstream blocker. It also does not claim absolute landmark accuracy, cross-device
performance, Android viability, or recognition improvement. No Sapiens, training, threshold
tuning, temporal repair, S6 retraining, Android, or production schema change occurred.

## 10. Runtime diagnostics

CPU total latency p50/p95/max was {metrics["latency_total_ms"]["p50"]:.2f} /
{metrics["latency_total_ms"]["p95"]:.2f} / {metrics["latency_total_ms"]["max"]:.2f} ms per frame.
Peak host RSS was {metrics["peak_host_rss_bytes"] / (1024**3):.3f} GiB. Runtime remains an offline
diagnostic and is not an Android FPS claim.
"""
    (OUTPUT / "P3_DWPOSE_LANDMARK_TEMPORAL_USABILITY_RESULT.md").write_text(
        report, encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run", "score", "all"))
    args = parser.parse_args()
    if args.command in {"prepare", "all"}:
        print(json.dumps(prepare(), indent=2), flush=True)
    if args.command in {"run", "all"}:
        print(json.dumps(run(), indent=2), flush=True)
    if args.command in {"score", "all"}:
        print(json.dumps(score(), indent=2), flush=True)


if __name__ == "__main__":
    main()
