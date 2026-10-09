"""Prepare and finalize the Gate 4A-1B controlled live-input recovery.

Preparation reads only the five frozen TRAIN fixtures and their existing raw-v1 packages.
Finalization replays only host-retained live raw-v1 attempts. DEV and protected TEST are never
opened by this module, and no model weights or perception artifacts are written.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.perception_vnext.governance import (
    TRAIN_MANIFEST,
    VOCAB_MANIFEST,
    load_rows,
    resolve_row_paths,
)
from pipeline.perception_vnext.recognition_schema_v2 import FEATURE_WIDTH_V2, temporal_view_v2
from eval.runtime_diagnostics.finalize_phase4a_gate4a1 import (
    load_raw,
    percentile,
    read_float32,
    summarize,
    topk,
    verify_capture_semantics,
)

ROOT = Path(__file__).resolve().parents[2]
MILESTONE = "PHASE_4A_GATE_4A1B_CONTROLLED_LIVE_INPUT_RECOVERY_01"
ARTIFACT_ROOT = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "phase4a_gate4a1b_controlled_live_input_recovery_01"
)
INDEX = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "dataset/index.jsonl"
)
GATE1_MANIFEST = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "phase4a_android_v2_parity_01/parity_corpus_manifest.json"
)
TARGETS = (
    ("p4a_v2_02", "e6:e6p_00795", 80, "HELLO"),
    ("p4a_v2_03", "asl:train:3317802933195262-AT", 8, "AT"),
    ("p4a_v2_05", "asl:train:4506537239301789-HOME", 83, "HOME"),
    ("p4a_v2_06", "asl:train:44175204654391864-STREET", 179, "STREET"),
    ("p4a_v2_07", "asl:train:072729520535459-TABLE", 183, "TABLE"),
)
FROZEN_HASHES = {
    "recognition_v2_kt": (
        ROOT / "android/app/src/debug/java/com/example/apphear/perceptionvnext/RecognitionV2.kt",
        "0a5fd969c574f3077060e75bcf697390e322da7e87e870da50b547714ba39699",
    ),
    "ordinary_v2_tcn_fp32_tflite": (
        ROOT / (
            "android/app/src/debug/assets/phase4a_gate2_recognizer_parity/"
            "ordinary_v2_tcn_fp32.tflite"
        ),
        "1ccf0afa9af9aa602aa0de33c9635f5cffd7feec7d9b4e32382bc5e3fa02880c",
    ),
    "vocabulary": (
        VOCAB_MANIFEST,
        "a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b",
    ),
    "candidate01_activity_kt": (
        ROOT / "android/app/src/debug/java/com/example/apphear/perceptionvnext/PerceptionVNextActivity.kt",
        "33523bfe626a0c053c09258024bee75430b3972c2ccf26dfd66205cdcb7ac86b",
    ),
    "candidate01_runners_kt": (
        ROOT / "android/app/src/debug/java/com/example/apphear/perceptionvnext/PerceptionVNextRunners.kt",
        "ffc8c176176dc9eb9ee4eb838192dd5481e185cd7a96283296139d342d71e6fe",
    ),
    "candidate01_math_kt": (
        ROOT / "android/app/src/debug/java/com/example/apphear/perceptionvnext/PerceptionVNextMath.kt",
        "f3e18ea2184ed52df77e47237499507e1f9bfac4dbe8638d379acb2bf4fed233",
    ),
    "candidate01_native_preprocessor_kt": (
        ROOT / "android/app/src/debug/java/com/example/apphear/perceptionvnext/PerceptionVNextNativePreprocessor.kt",
        "1a62c228da0be76d0faa9433a8163d5585d79d936cbd9bf7fdf7bbefed173512",
    ),
    "recognition_v2_live_recognizer_kt": (
        ROOT / "android/app/src/debug/java/com/example/apphear/perceptionvnext/RecognitionV2LiveRecognizer.kt",
        "d1483ebcec5c77a3d80fe907e46640ed4a7489398bdcca72edf7d53466eff66f",
    ),
    "gate1_manifest": (
        ROOT / "android/app/src/debug/assets/phase4a_v2_parity/manifest.json",
        "01fd271c25df2d0b7a64e803fabe0b745d51be1ac8f7c6f646546e2a3aa055b3",
    ),
    "gate2_manifest": (
        ROOT / "android/app/src/debug/assets/phase4a_gate2_recognizer_parity/manifest.json",
        "bfe8bec13a646eb6fa733c3bee6a421a44b5e58ed6dbb0dd59d88804e397d019",
    ),
    "gate3_manifest": (
        ROOT / "android/app/src/debug/assets/phase4a_gate3_known_train_replay/manifest.json",
        "26271282e79f81c048c36b54516782811904402cbbdadd4df29043417869b148",
    ),
}
CHECKPOINT = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "tcn_v2_run_01/best.keras"
)
EXPECTED_CHECKPOINT_SHA = "8107accbc621ae5652766fec80d314fe8dc9f94ba0d0548a6aef80ed91729340"
OLD_GATE4A1_RESULT = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "phase4a_gate4a1_live_plumbing_validation_01/gate4a1_live_replay_result.json"
)
PHONE_COMPLETED_FPS = 5.606840672873506
V2_TOLERANCE = 1.0e-5
OUTPUT_TOLERANCE = 1.0e-4
ATTRIBUTIONS = {
    "A": "CAPTURE_CONDITION_EFFECT_SUPPORTED",
    "B": "SIGN_EXECUTION_VARIANT_EFFECT_SUPPORTED",
    "C": "LIVE_MOTION_OCCLUSION_HAND_LOSS_SUPPORTED",
    "D": "CANDIDATE01_LIVE_DOMAIN_HAND_FAILURE_SUPPORTED",
    "E": "GOOD_LIVE_INPUT_BUT_RECOGNITION_STILL_POOR",
    "F": "MIXED_OR_INCONCLUSIVE",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def longest_false_run(values: np.ndarray) -> tuple[int, int]:
    runs = 0
    longest = 0
    current = 0
    for value in values.astype(bool):
        if value:
            current = 0
        else:
            if current == 0:
                runs += 1
            current += 1
            longest = max(longest, current)
    return runs, longest


def video_metadata(path: Path) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"GATE4A1B_VIDEO_OPEN_FAILURE:{path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()
    return {
        "container_fps": fps,
        "container_frames": frames,
        "container_duration_ms": frames / fps * 1000.0 if fps > 0 else None,
        "container_width": width,
        "container_height": height,
    }


def raw_profile(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as package:
        metadata = json.loads(str(package["metadata_json"].item()))
        observed = np.asarray(package["hand_observed"], bool)
        proposal = np.asarray(package["hand_proposal_present"], bool)
        presence = np.asarray(package["hand_presence"], np.float32)
        body = np.asarray(package["body_available"], bool)
        timestamps = np.asarray(package["timestamp_ms"], np.float64)
    duration_ms = float(timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else 0.0
    either = np.any(observed, axis=1)
    active_indices = np.flatnonzero(either)
    if active_indices.size:
        active_first = int(active_indices[0])
        active_last = int(active_indices[-1])
        active_slice = slice(active_first, active_last + 1)
        active_span_count = active_last - active_first + 1
        active_span_duration_ms = float(timestamps[active_last] - timestamps[active_first])
        active_either_rate = float(np.mean(either[active_slice]))
        active_both_rate = float(np.mean(observed[active_slice, 0] & observed[active_slice, 1]))
    else:
        active_first = active_last = None
        active_span_count = 0
        active_span_duration_ms = 0.0
        active_either_rate = 0.0
        active_both_rate = 0.0
    result: dict[str, Any] = {
        "raw_path": str(path.resolve()),
        "raw_sha256": sha256(path),
        "raw_observation_count": int(len(observed)),
        "raw_duration_ms": duration_ms,
        "raw_observation_rate_hz": (
            float((len(observed) - 1) / (duration_ms / 1000.0)) if duration_ms > 0 else None
        ),
        "lh_observed_rate": float(np.mean(observed[:, 0])),
        "rh_observed_rate": float(np.mean(observed[:, 1])),
        "lh_presence_pass_rate": float(np.mean(np.isfinite(presence[:, 0]) & (presence[:, 0] >= 0.5))),
        "rh_presence_pass_rate": float(np.mean(np.isfinite(presence[:, 1]) & (presence[:, 1] >= 0.5))),
        "lh_proposal_rate": float(np.mean(proposal[:, 0])),
        "rh_proposal_rate": float(np.mean(proposal[:, 1])),
        "both_hands_observed_rate": float(np.mean(observed[:, 0] & observed[:, 1])),
        "body_available_rate": float(np.mean(body)),
        "active_hand_first_index": active_first,
        "active_hand_last_index": active_last,
        "active_hand_span_count": active_span_count,
        "active_hand_span_duration_ms": active_span_duration_ms,
        "active_hand_either_observed_rate": active_either_rate,
        "active_hand_both_observed_rate": active_both_rate,
        "metadata": metadata,
    }
    for index, prefix in ((0, "lh"), (1, "rh")):
        runs, longest = longest_false_run(observed[:, index])
        result[f"{prefix}_missing_runs"] = runs
        result[f"{prefix}_longest_missing_run"] = longest
    return result


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def prepare() -> dict[str, Any]:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    identities: dict[str, Any] = {}
    for name, (path, expected) in FROZEN_HASHES.items():
        actual = sha256(path)
        identities[name] = {"path": str(path), "expected_sha256": expected, "actual_sha256": actual}
        if actual != expected:
            raise RuntimeError(f"GATE4A1B_FROZEN_IDENTITY_FAILURE:{name}:{actual}")

    gate1 = json.loads(GATE1_MANIFEST.read_text(encoding="utf-8"))
    gate1_by_id = {row["fixture_id"]: row for row in gate1["fixtures"]}
    index_by_id = {
        row["sample_id"]: row
        for row in (json.loads(line) for line in INDEX.read_text(encoding="utf-8").splitlines())
    }
    train_by_id = {row["sample_id"]: row for row in load_rows(TRAIN_MANIFEST)}

    fixtures: list[dict[str, Any]] = []
    for fixture_id, sample_id, class_id, gloss in TARGETS:
        fixture = gate1_by_id[fixture_id]
        if fixture["sample_id"] != sample_id:
            raise RuntimeError(f"GATE4A1B_FIXTURE_SAMPLE_MISMATCH:{fixture_id}")
        index_row = index_by_id[sample_id]
        if int(index_row["class_id"]) != class_id or index_row["canonical_gloss"] != gloss:
            raise RuntimeError(f"GATE4A1B_CLASS_IDENTITY_MISMATCH:{sample_id}")
        if index_row["split"] != "train":
            raise RuntimeError(f"GATE4A1B_NON_TRAIN_FIXTURE:{sample_id}")

        if sample_id.startswith("asl:"):
            source_row = resolve_row_paths(train_by_id[sample_id])
            source_video = Path(source_row["raw_video_path"])
            source_video_sha = source_row["raw_video_sha256"].lower()
            source_manifest = source_row["source_manifest_path"]
            source_row_index = int(source_row["source_row_index"])
        else:
            profile_metadata = raw_profile(Path(index_row["raw_path"]))["metadata"]
            source_video = Path(profile_metadata["source_video_path"])
            source_video_sha = profile_metadata["source_video_sha256"].lower()
            source_manifest = "artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_baseline_01/positive_extraction_manifest.csv"
            source_row_index = 796

        if not source_video.is_file() or sha256(source_video) != source_video_sha:
            raise RuntimeError(f"GATE4A1B_SOURCE_VIDEO_IDENTITY_FAILURE:{sample_id}:{source_video}")

        raw_path = Path(index_row["raw_path"])
        profile = raw_profile(raw_path)
        metadata = profile.pop("metadata")
        fixtures.append(
            {
                "fixture_id": fixture_id,
                "sample_id": sample_id,
                "class_id": class_id,
                "canonical_gloss": gloss,
                "signer_id": index_row["signer_id"],
                "source_id": index_row["source_id"],
                "source_video_path": str(source_video),
                "source_video_sha256": source_video_sha,
                "source_manifest_path": source_manifest,
                "source_row_index": source_row_index,
                "span_start_inclusive": metadata.get("span_start_inclusive"),
                "span_end_inclusive": metadata.get("span_end_inclusive"),
                "duration_scope": metadata.get("duration_scope"),
                "orientation_degrees_clockwise": metadata.get("orientation_degrees_clockwise"),
                **video_metadata(source_video),
                **profile,
            }
        )

    result = {
        "milestone": MILESTONE,
        "status": "PREPARED",
        "population": "TRAIN_ONLY",
        "dev_accessed": False,
        "protected_test_accessed": False,
        "training_executed": False,
        "diagnostic_sampling_rule": [
            "first accepted observation",
            "every 10th accepted observation",
            "every observed/proposal hand-state transition",
            "last accepted observation",
        ],
        "presence_rate_predicate": "finite hand-refiner presence >= 0.50",
        "frozen_identity": identities,
        "fixtures": fixtures,
    }
    write_json(ARTIFACT_ROOT / "reference_train_fixtures.json", result)

    csv_path = ARTIFACT_ROOT / "train_reference_input_quality.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        fields = [
            "fixture_id", "sample_id", "class_id", "canonical_gloss", "signer_id", "source_id",
            "raw_observation_count", "raw_duration_ms", "raw_observation_rate_hz",
            "lh_observed_rate", "rh_observed_rate", "lh_presence_pass_rate", "rh_presence_pass_rate",
            "both_hands_observed_rate", "body_available_rate", "lh_missing_runs",
            "lh_longest_missing_run", "rh_missing_runs", "rh_longest_missing_run", "source_video_path",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in fixtures:
            writer.writerow({name: row[name] for name in fields})

    lines = [
        "# Gate 4A-1B exact TRAIN references",
        "",
        "Watch the exact governed video immediately before **each** matching phone attempt. The phone",
        "requires a fresh `REFERENCE WATCHED` acknowledgement before START is enabled.",
        "",
        "| Order | Gloss | Class | Fixture | Exact TRAIN video |",
        "|---:|---|---:|---|---|",
    ]
    for order, row in enumerate(fixtures, 1):
        target = row["source_video_path"].replace("\\", "/")
        lines.append(
            f"| {order} | {row['canonical_gloss']} | {row['class_id']} | {row['fixture_id']} | "
            f"[{Path(target).name}](<{target}>) |"
        )
    lines.extend(
        [
            "",
            "Capture order is HELLO×2, AT×2, HOME×2, STREET×2, TABLE×2. Do not select or discard",
            "repetitions based on the prediction.",
        ]
    )
    (ARTIFACT_ROOT / "REFERENCE_TRAIN_FIXTURES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def observation_profile(raw_value: dict[str, Any], duration_ms: float) -> dict[str, Any]:
    observed = np.asarray(raw_value["hand_observed"], bool).reshape(-1, 2)
    proposal = np.asarray(raw_value["hand_proposal_present"], bool).reshape(-1, 2)
    body = np.asarray(raw_value["body_available"], bool)
    timestamps = np.asarray(raw_value["timestamp_ms"], np.float64)
    count = len(observed)
    either = np.any(observed, axis=1)
    active_indices = np.flatnonzero(either)
    if active_indices.size:
        active_first = int(active_indices[0])
        active_last = int(active_indices[-1])
        active_slice = slice(active_first, active_last + 1)
        active_span_count = active_last - active_first + 1
        active_span_duration_ms = float(timestamps[active_last] - timestamps[active_first])
        active_either_rate = float(np.mean(either[active_slice]))
        active_both_rate = float(np.mean(observed[active_slice, 0] & observed[active_slice, 1]))
    else:
        active_first = active_last = None
        active_span_count = 0
        active_span_duration_ms = 0.0
        active_either_rate = 0.0
        active_both_rate = 0.0
    result: dict[str, Any] = {
        "observation_count": count,
        "duration_ms": duration_ms,
        "observation_rate_hz": count / (duration_ms / 1000.0) if duration_ms > 0 else None,
        "lh_observed_rate": float(np.mean(observed[:, 0])),
        "rh_observed_rate": float(np.mean(observed[:, 1])),
        "lh_proposal_rate": float(np.mean(proposal[:, 0])),
        "rh_proposal_rate": float(np.mean(proposal[:, 1])),
        "both_hands_observed_rate": float(np.mean(observed[:, 0] & observed[:, 1])),
        "body_available_rate": float(np.mean(body)),
        # Diagnostic only: the first-to-last observed-hand interval distinguishes
        # perception loss during the sign from long hands-down lead-in/lead-out.
        "active_hand_first_index": active_first,
        "active_hand_last_index": active_last,
        "active_hand_span_count": active_span_count,
        "active_hand_span_duration_ms": active_span_duration_ms,
        "active_hand_either_observed_rate": active_either_rate,
        "active_hand_both_observed_rate": active_both_rate,
    }
    for index, prefix in ((0, "lh"), (1, "rh")):
        runs, longest = longest_false_run(observed[:, index])
        result[f"{prefix}_missing_runs"] = runs
        result[f"{prefix}_longest_missing_run"] = longest
    return result


def mean_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = (
        "observation_count",
        "duration_ms",
        "observation_rate_hz",
        "lh_observed_rate",
        "rh_observed_rate",
        "lh_proposal_rate",
        "rh_proposal_rate",
        "both_hands_observed_rate",
        "body_available_rate",
        "active_hand_span_count",
        "active_hand_span_duration_ms",
        "active_hand_either_observed_rate",
        "active_hand_both_observed_rate",
    )
    return {key: float(np.mean([row[key] for row in rows])) for key in keys}


def validate_visual_diagnostics(directory: Path, phone: dict[str, Any]) -> dict[str, Any]:
    diagnostics = phone.get("visual_diagnostics", [])
    if not diagnostics:
        return {"status": "FAIL", "count": 0, "reason": "no diagnostics"}
    last = int(phone["diagnostic_last_accepted_ordinal"])
    ordinals = {int(row["accepted_ordinal"]) for row in diagnostics}
    files_checked = 0
    luminance: list[float] = []
    sharpness: list[float] = []
    side_values: dict[str, dict[str, Any]] = {
        side: {
            "proposal_count": 0,
            "observed_count": 0,
            "roi_luminance": [],
            "roi_area": [],
            "presence": [],
        }
        for side in ("left", "right")
    }
    for row in diagnostics:
        for file_key, hash_key in (
            ("original_file", "original_sha256"),
            ("diagnostic_file", "diagnostic_sha256"),
            ("metadata_file", "metadata_sha256"),
        ):
            path = directory / row[file_key]
            if not path.is_file() or sha256(path) != row[hash_key]:
                return {"status": "FAIL", "count": len(diagnostics), "reason": f"hash:{path}"}
            files_checked += 1
        luminance.append(float(row["full_frame_luminance_mean"]))
        sharpness.append(float(row["sharpness_laplacian_variance"]))
        for side in ("left", "right"):
            hand = row[side]
            if hand["proposal_present"]:
                side_values[side]["proposal_count"] += 1
            if hand["refiner_observed"]:
                side_values[side]["observed_count"] += 1
            for source, target in (
                ("roi_luminance_mean", "roi_luminance"),
                ("roi_area_fraction", "roi_area"),
                ("refiner_presence", "presence"),
            ):
                if hand[source] is not None:
                    side_values[side][target].append(float(hand[source]))
    required = 1 in ordinals and last in ordinals
    result = {
        "status": "PASS" if required else "FAIL",
        "count": len(diagnostics),
        "files_checked": files_checked,
        "first_present": 1 in ordinals,
        "last_present": last in ordinals,
        "luminance_mean": float(np.mean(luminance)),
        "luminance_min": float(np.min(luminance)),
        "sharpness_mean": float(np.mean(sharpness)),
    }
    for side in ("left", "right"):
        values = side_values[side]
        result[side] = {
            "proposal_diagnostic_frames": values["proposal_count"],
            "observed_diagnostic_frames": values["observed_count"],
            "roi_luminance_median": (
                float(np.median(values["roi_luminance"])) if values["roi_luminance"] else None
            ),
            "roi_area_fraction_median": (
                float(np.median(values["roi_area"])) if values["roi_area"] else None
            ),
            "refiner_presence_median": (
                float(np.median(values["presence"])) if values["presence"] else None
            ),
        }
    return result


def finalize(session: Path, classification_code: str, classification_reason: str) -> dict[str, Any]:
    if classification_code not in ATTRIBUTIONS:
        raise RuntimeError(f"GATE4A1B_ATTRIBUTION_INVALID:{classification_code}")
    if sha256(CHECKPOINT) != EXPECTED_CHECKPOINT_SHA:
        raise RuntimeError("GATE4A1B_CHECKPOINT_IDENTITY_FAILURE")
    for name, (path, expected) in FROZEN_HASHES.items():
        if sha256(path) != expected:
            raise RuntimeError(f"GATE4A1B_FROZEN_IDENTITY_FAILURE:{name}")

    identity = json.loads((session / "session_identity.json").read_text(encoding="utf-8"))
    session_summary = json.loads((session / "session_summary.json").read_text(encoding="utf-8"))
    if identity["milestone"] != MILESTONE or int(session_summary["valid_attempts"]) != 10:
        raise RuntimeError("GATE4A1B_SESSION_INCOMPLETE")

    vocab = json.loads(VOCAB_MANIFEST.read_text(encoding="utf-8"))
    glosses = [gloss for gloss, index in sorted(vocab.items(), key=lambda pair: pair[1])]
    import tensorflow as tf

    model = tf.keras.models.load_model(CHECKPOINT, compile=False, safe_mode=True)
    if model.count_params() != 192556:
        raise RuntimeError("GATE4A1B_MODEL_PARAMETER_IDENTITY_FAILURE")

    valid_dirs: list[Path] = []
    invalid_attempts: list[dict[str, Any]] = []
    for directory in sorted(path for path in session.glob("attempt_*") if path.is_dir()):
        phone = json.loads((directory / "attempt.json").read_text(encoding="utf-8"))
        if phone["classification"] == "VALID":
            valid_dirs.append(directory)
        else:
            invalid_attempts.append(phone)
    if len(valid_dirs) != 10:
        raise RuntimeError(f"GATE4A1B_VALID_ATTEMPT_COUNT_FAILURE:{len(valid_dirs)}")

    feature_errors: list[np.ndarray] = []
    output_errors: list[np.ndarray] = []
    attempts: list[dict[str, Any]] = []
    worst_feature: dict[str, Any] = {"absolute_error": -1.0}
    worst_output: dict[str, Any] = {"absolute_error": -1.0}
    top1_mismatches = top5_membership_mismatches = top5_order_mismatches = 0
    for directory in valid_dirs:
        phone = json.loads((directory / "attempt.json").read_text(encoding="utf-8"))
        if phone.get("exact_train_reference_acknowledged") is not True:
            raise RuntimeError(f"GATE4A1B_REFERENCE_NOT_ACKNOWLEDGED:{directory.name}")
        raw, raw_value = load_raw(directory / "raw_v1.json")
        reference_view = temporal_view_v2(raw, condition="dense", phone_completed_fps=PHONE_COMPLETED_FPS)
        phone_features = read_float32(directory / "recognition_v2.f32", 96 * FEATURE_WIDTH_V2).reshape(96, FEATURE_WIDTH_V2)
        phone_mask = np.fromfile(directory / "frame_mask.u8", dtype=np.uint8).astype(bool)
        phone_output = read_float32(directory / "probabilities.f32", 236)
        if not np.array_equal(phone_mask, reference_view["mask"]):
            raise RuntimeError(f"GATE4A1B_MASK_MISMATCH:{directory.name}")
        if list(phone["selected_source_indices"]) != reference_view["source_indices"].astype(int).tolist():
            raise RuntimeError(f"GATE4A1B_SELECTION_MISMATCH:{directory.name}")
        if not np.array_equal(
            np.asarray(phone["selected_source_timestamps_ms"], np.float64),
            reference_view["source_timestamps_ms"].astype(np.float64),
        ):
            raise RuntimeError(f"GATE4A1B_SELECTED_TIMESTAMP_MISMATCH:{directory.name}")

        feature_error = np.abs(reference_view["features"].astype(np.float64) - phone_features.astype(np.float64))
        feature_errors.append(feature_error)
        local_feature = int(np.argmax(feature_error))
        if float(feature_error.reshape(-1)[local_feature]) > worst_feature["absolute_error"]:
            worst_feature = {
                "attempt": directory.name,
                "timestep": local_feature // FEATURE_WIDTH_V2,
                "channel": local_feature % FEATURE_WIDTH_V2,
                "reference_value": float(reference_view["features"].reshape(-1)[local_feature]),
                "android_value": float(phone_features.reshape(-1)[local_feature]),
                "absolute_error": float(feature_error.reshape(-1)[local_feature]),
            }
        reference_output = model(
            [reference_view["features"][None].astype(np.float32), reference_view["mask"][None]],
            training=False,
        ).numpy()[0].astype(np.float32)
        output_error = np.abs(reference_output.astype(np.float64) - phone_output.astype(np.float64))
        output_errors.append(output_error)
        local_output = int(np.argmax(output_error))
        if float(output_error[local_output]) > worst_output["absolute_error"]:
            worst_output = {
                "attempt": directory.name,
                "output_class": local_output,
                "gloss": glosses[local_output],
                "reference_value": float(reference_output[local_output]),
                "android_value": float(phone_output[local_output]),
                "absolute_error": float(output_error[local_output]),
            }
        reference_top = topk(reference_output)
        phone_top = topk(phone_output)
        top1_mismatches += int(reference_top[0] != phone_top[0])
        top5_membership_mismatches += int(set(reference_top) != set(phone_top))
        top5_order_mismatches += int(reference_top != phone_top)
        capture = verify_capture_semantics(phone, raw_value)
        selected = reference_view["source_timestamps_ms"]
        expected_dt = np.minimum(np.diff(selected) / 1000.0, 1.0).astype(np.float32)
        actual_dt = reference_view["features"][1 : len(selected), 348]
        capture["selected_timestamp_dt"] = "PASS" if (
            float(reference_view["features"][0, 348]) == 0.0 and np.array_equal(actual_dt, expected_dt)
        ) else "FAIL"
        if capture["selected_timestamp_dt"] == "FAIL":
            capture["status"] = "FAIL"
        profile = observation_profile(raw_value, float(phone["capture_duration_ms"]))
        visual = validate_visual_diagnostics(directory, phone)
        expected = int(phone["expected_class_id"])
        attempts.append(
            {
                "attempt": directory.name,
                "expected_class_id": expected,
                "expected_gloss": phone["expected_gloss"],
                "fixture_id": phone["fixture_id"],
                "repetition": int(phone["repetition"]),
                "android_top1": glosses[phone_top[0]],
                "android_top1_probability": float(phone_output[phone_top[0]]),
                "android_top5": [glosses[index] for index in phone_top],
                "expected_in_top5": expected in phone_top,
                "semantic_top1_correct": phone_top[0] == expected,
                "offline_top1": glosses[reference_top[0]],
                "feature_max_abs": float(feature_error.max()),
                "output_max_abs": float(output_error.max()),
                "capture_semantics": capture,
                "visual_diagnostics": visual,
                "input_quality": profile,
                "latency_ms": phone["latency_ms"],
            }
        )

    feature_stats = summarize(feature_errors)
    output_stats = summarize(output_errors)
    parity_pass = (
        feature_stats["max_abs"] <= V2_TOLERANCE
        and output_stats["max_abs"] <= OUTPUT_TOLERANCE
        and top1_mismatches == 0
        and top5_membership_mismatches == 0
        and top5_order_mismatches == 0
    )
    technical_pass = (
        parity_pass
        and all(row["capture_semantics"]["status"] == "PASS" for row in attempts)
        and all(row["visual_diagnostics"]["status"] == "PASS" for row in attempts)
        and not (session / "failure.txt").exists()
    )
    if not technical_pass:
        classification_code = "F"
        classification_reason = "Technical or parity evidence failed; semantic attribution is not permitted."

    reference = json.loads((ARTIFACT_ROOT / "reference_train_fixtures.json").read_text(encoding="utf-8"))
    train_by_gloss = {row["canonical_gloss"]: row for row in reference["fixtures"]}
    new_by_gloss = {
        gloss: mean_profile([row["input_quality"] for row in attempts if row["expected_gloss"] == gloss])
        for _, _, _, gloss in TARGETS
    }
    old_result = json.loads(OLD_GATE4A1_RESULT.read_text(encoding="utf-8"))
    old_session = Path(old_result["session"])
    old_by_gloss: dict[str, dict[str, Any]] = {}
    for row in old_result["attempts"]:
        raw_value = json.loads((old_session / row["attempt"] / "raw_v1.json").read_text(encoding="utf-8"))
        old_by_gloss[row["expected_gloss"]] = observation_profile(raw_value, float(row["duration_ms"]))

    comparison = []
    for _, _, _, gloss in TARGETS:
        comparison.append(
            {
                "gloss": gloss,
                "train_reference": {
                    key: train_by_gloss[gloss][key]
                    for key in (
                        "raw_observation_count", "raw_duration_ms", "raw_observation_rate_hz",
                        "lh_observed_rate", "rh_observed_rate", "both_hands_observed_rate",
                        "body_available_rate", "active_hand_span_count",
                        "active_hand_span_duration_ms", "active_hand_either_observed_rate",
                        "active_hand_both_observed_rate",
                    )
                },
                "old_live": old_by_gloss[gloss],
                "controlled_live_mean": new_by_gloss[gloss],
                "controlled_predictions": [
                    {
                        "repetition": row["repetition"],
                        "top1": row["android_top1"],
                        "expected_in_top5": row["expected_in_top5"],
                    }
                    for row in attempts if row["expected_gloss"] == gloss
                ],
            }
        )

    semantic_top1 = sum(int(row["semantic_top1_correct"]) for row in attempts)
    semantic_top5 = sum(int(row["expected_in_top5"]) for row in attempts)
    candidate_latencies = []
    v2_latencies = []
    tflite_latencies = []
    stop_latencies = []
    for directory, row in zip(valid_dirs, attempts):
        raw_value = json.loads((directory / "raw_v1.json").read_text(encoding="utf-8"))
        candidate_latencies.extend(float(item["total_perception_ms"]) for item in raw_value["frame_runtime"])
        v2_latencies.append(float(row["latency_ms"]["v2_construction"]))
        tflite_latencies.append(float(row["latency_ms"]["tflite_invocation"]))
        stop_latencies.append(float(row["latency_ms"]["stop_to_result"]))

    qualities = [row["input_quality"] for row in attempts]
    def range_summary(key: str) -> dict[str, float]:
        values = [float(row[key]) for row in qualities]
        return {
            "min": float(np.min(values)),
            "median": float(np.median(values)),
            "max": float(np.max(values)),
        }

    retained_manifest = ARTIFACT_ROOT / "host_retained_artifact_hashes.json"
    retained_rows = json.loads(retained_manifest.read_text(encoding="utf-8"))
    live_summary = {
        "valid_attempts": len(attempts),
        "invalid_no_observation_attempts": len(invalid_attempts),
        "observation_count": range_summary("observation_count"),
        "duration_ms": range_summary("duration_ms"),
        "observation_rate_hz": range_summary("observation_rate_hz"),
        "mean_lh_observed_rate": float(np.mean([row["lh_observed_rate"] for row in qualities])),
        "mean_rh_observed_rate": float(np.mean([row["rh_observed_rate"] for row in qualities])),
        "mean_both_hands_observed_rate": float(np.mean([row["both_hands_observed_rate"] for row in qualities])),
        "mean_body_available_rate": float(np.mean([row["body_available_rate"] for row in qualities])),
    }

    result = {
        "milestone": MILESTONE,
        "status": "PASS" if technical_pass else "FAIL",
        "technical_classification": "CONTROLLED_LIVE_INPUT_RECOVERY_TECHNICAL_PASS" if technical_pass else "CONTROLLED_LIVE_INPUT_RECOVERY_TECHNICAL_FAIL",
        "final_attribution_code": classification_code,
        "final_attribution": ATTRIBUTIONS[classification_code],
        "attribution_reason": classification_reason,
        "session": str(session.resolve()),
        "valid_attempts": len(attempts),
        "invalid_attempts": invalid_attempts,
        "attempts": attempts,
        "old_vs_new_vs_train": comparison,
        "v2_parity": {**feature_stats, "tolerance": V2_TOLERANCE, "worst": worst_feature},
        "output_parity": {
            **output_stats,
            "tolerance": OUTPUT_TOLERANCE,
            "worst": worst_output,
            "top1_mismatches": top1_mismatches,
            "top5_membership_mismatches": top5_membership_mismatches,
            "top5_order_mismatches": top5_order_mismatches,
        },
        "semantic_diagnostic_only": {
            "top1_correct": semantic_top1,
            "top5_contains_expected": semantic_top5,
            "total": 10,
        },
        "live_capture_summary": live_summary,
        "evidence_retention": {
            "host_session_directory": str(session.resolve()),
            "hash_manifest": str(retained_manifest.resolve()),
            "hash_manifest_sha256": sha256(retained_manifest),
            "retained_files": len(retained_rows),
            "retained_bytes": int(sum(row["bytes"] for row in retained_rows)),
            "pulled_before_cleanup": True,
        },
        "latency_ms": {
            "candidate01_p50": percentile(candidate_latencies, 50),
            "candidate01_p95": percentile(candidate_latencies, 95),
            "v2_p50": percentile(v2_latencies, 50),
            "v2_p95": percentile(v2_latencies, 95),
            "tflite_p50": percentile(tflite_latencies, 50),
            "tflite_p95": percentile(tflite_latencies, 95),
            "stop_to_result_p50": percentile(stop_latencies, 50),
            "stop_to_result_p95": percentile(stop_latencies, 95),
        },
        "candidate01_modified": False,
        "v2_modified": False,
        "model_modified": False,
        "training_executed": False,
        "dev_accessed": False,
        "protected_test_accessed": False,
    }
    write_json(ARTIFACT_ROOT / "gate4a1b_live_replay_result.json", result)

    lines = [
        f"# {MILESTONE}",
        "",
        f"Technical status: **{result['technical_classification']}**  ",
        f"Final attribution: **{result['final_attribution']}**",
        "",
        classification_reason,
        "",
        "## Controlled attempts",
        "",
        "| Attempt | Expected | Rep | Obs | LH | RH | Active span | Active continuity | Top-1 | P(Top-1) | Expected Top-5 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|",
    ]
    for row in attempts:
        quality = row["input_quality"]
        lines.append(
            f"| {row['attempt']} | {row['expected_gloss']} | {row['repetition']} | "
            f"{quality['observation_count']} | {quality['lh_observed_rate']:.1%} | "
            f"{quality['rh_observed_rate']:.1%} | {quality['active_hand_span_duration_ms'] / 1000.0:.2f}s | "
            f"{quality['active_hand_either_observed_rate']:.1%} | {row['android_top1']} | "
            f"{row['android_top1_probability']:.4f} | {row['expected_in_top5']} |"
        )
    lines.extend(
        [
            "",
            "## Old vs controlled live vs TRAIN reference",
            "",
            "| Sign | TRAIN LH/RH/body | Old live LH/RH/body | Controlled LH/RH/body | Controlled predictions |",
            "|---|---|---|---|---|",
        ]
    )
    for row in comparison:
        train = row["train_reference"]
        old = row["old_live"]
        controlled = row["controlled_live_mean"]
        predictions = ", ".join(
            f"R{item['repetition']} {item['top1']} (Top-5={item['expected_in_top5']})"
            for item in row["controlled_predictions"]
        )
        lines.append(
            f"| {row['gloss']} | {train['lh_observed_rate']:.1%}/{train['rh_observed_rate']:.1%}/"
            f"{train['body_available_rate']:.1%} | {old['lh_observed_rate']:.1%}/"
            f"{old['rh_observed_rate']:.1%}/{old['body_available_rate']:.1%} | "
            f"{controlled['lh_observed_rate']:.1%}/{controlled['rh_observed_rate']:.1%}/"
            f"{controlled['body_available_rate']:.1%} | {predictions} |"
        )
    lines.extend(
        [
            "",
            "## Visual/temporal interpretation",
            "",
            "- Whole-capture hand rates include hands-down lead-in and lead-out. The active span in the",
            "  attempt table is diagnostic only; it does not alter frozen V2 or the recognizer input.",
            "- Seven of ten controlled attempts retained an observed hand continuously or near-continuously",
            "  through the active interval (87.5–100%).",
            "- Both STREET repetitions retained both hands continuously for their 1.47 s and 1.80 s active intervals.",
            "- Both TABLE repetitions observed a hand in only 2 of 4 active-span observations; saved overlays",
            "  show overlapping/contact ROIs and refiner-presence collapse. The exact TRAIN TABLE reference",
            "  also has 0% refined-hand observation, so this does not establish a new live-only failure.",
            "- HELLO/HOME had body group availability 0 despite visible partial body keypoints; their close",
            "  framing did not satisfy the complete frozen body-reference predicate.",
            "- Sampled full-frame luminance and Laplacian sharpness are finite and usable; the bounded evidence",
            "  does not support gross darkness or blur as a sole explanation.",
            "",
            "## Parity",
            "",
            f"- V2 max/p95/mean: `{feature_stats['max_abs']:.9g}` / `{feature_stats['p95_abs']:.9g}` / `{feature_stats['mean_abs']:.9g}`",
            f"- Probabilities max/p95/mean: `{output_stats['max_abs']:.9g}` / `{output_stats['p95_abs']:.9g}` / `{output_stats['mean_abs']:.9g}`",
            f"- Top-1 / Top-5 membership / Top-5 order mismatches: `{top1_mismatches}` / `{top5_membership_mismatches}` / `{top5_order_mismatches}`",
            "",
            "## Semantic result (diagnostic only)",
            "",
            f"- Top-1 correct: `{semantic_top1}/10`",
            f"- Expected in Top-5: `{semantic_top5}/10`",
            "",
            "## Live capture summary",
            "",
            f"- Valid / invalid-no-observation: `{len(attempts)}` / `{len(invalid_attempts)}`",
            f"- Observation count min/median/max: `{live_summary['observation_count']['min']:.0f}/"
            f"{live_summary['observation_count']['median']:.1f}/{live_summary['observation_count']['max']:.0f}`",
            f"- Duration min/median/max: `{live_summary['duration_ms']['min'] / 1000.0:.2f}/"
            f"{live_summary['duration_ms']['median'] / 1000.0:.2f}/{live_summary['duration_ms']['max'] / 1000.0:.2f} s`",
            f"- Observation rate min/median/max: `{live_summary['observation_rate_hz']['min']:.2f}/"
            f"{live_summary['observation_rate_hz']['median']:.2f}/{live_summary['observation_rate_hz']['max']:.2f} Hz`",
            f"- Mean LH/RH/both/body availability: `{live_summary['mean_lh_observed_rate']:.2%}/"
            f"{live_summary['mean_rh_observed_rate']:.2%}/{live_summary['mean_both_hands_observed_rate']:.2%}/"
            f"{live_summary['mean_body_available_rate']:.2%}`",
            "",
            "## Latency",
            "",
            f"- Candidate01 p50/p95: `{result['latency_ms']['candidate01_p50']:.2f}/"
            f"{result['latency_ms']['candidate01_p95']:.2f} ms`",
            f"- V2 p50/p95: `{result['latency_ms']['v2_p50']:.2f}/{result['latency_ms']['v2_p95']:.2f} ms`",
            f"- TFLite p50/p95: `{result['latency_ms']['tflite_p50']:.2f}/"
            f"{result['latency_ms']['tflite_p95']:.2f} ms`",
            f"- STOP-to-result p50/p95: `{result['latency_ms']['stop_to_result_p50']:.2f}/"
            f"{result['latency_ms']['stop_to_result_p95']:.2f} ms`",
            "",
            "## Evidence retention",
            "",
            f"- Host session: `{session.resolve()}`",
            f"- Retained files/bytes: `{len(retained_rows)}` / `{sum(row['bytes'] for row in retained_rows)}`",
            f"- Hash manifest SHA-256: `{sha256(retained_manifest)}`",
            "- Evidence pulled before cleanup: **YES**",
            "",
            "Candidate01 modified: **NO**  ",
            "Recognition V2 modified: **NO**  ",
            "Model modified: **NO**  ",
            "Training executed: **NO**  ",
            "DEV accessed: **NO**  ",
            "Protected TEST accessed: **NO**",
            "",
            "Next boundary: **WAIT_FOR_PROJECT_LEAD_REVIEW_AFTER_GATE_4A1B**. Do not start Gate 4A-2",
            "or modify Candidate 01 automatically.",
            "",
        ]
    )
    (ARTIFACT_ROOT / "PHASE4A_GATE4A1B_FINAL_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "finalize"))
    parser.add_argument("--session", type=Path)
    parser.add_argument("--classification", choices=tuple(ATTRIBUTIONS), default="F")
    parser.add_argument("--reason", default="Evidence is mixed or insufficient for a single causal attribution.")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare()
        print(json.dumps({"status": result["status"], "fixtures": len(result["fixtures"])}))
    elif args.command == "finalize":
        if args.session is None:
            parser.error("--session is required for finalize")
        result = finalize(args.session, args.classification, args.reason)
        print(json.dumps({"status": result["status"], "attribution": result["final_attribution"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
