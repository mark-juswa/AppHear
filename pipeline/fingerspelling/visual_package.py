"""Separate RGB/ROI embedding package with exact raw-frame and source lineage."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from model.fingerspelling_appearance import EVIDENCE, PACKAGE, encoder_identity
from pipeline.fingerspelling.adapter import identity as geometry_identity
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import verify_raw, verify_source
from pipeline.fingerspelling.visual_crop import config, crop_identity, hand_crop
from pipeline.perception_vnext.offline_candidate01 import iter_video_frames

SCHEMA = "apphear.fingerspelling.visual_sequence.v1"
RECEIPT = "apphear.fingerspelling.visual_receipt.v1"


def visual_identity() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "crop": crop_identity(),
        "encoder": encoder_identity(),
        "package_implementation_sha256": sha256(
            REPO / "pipeline/fingerspelling/visual_package.py"
        ),
    }


def receipt_path(rec: dict[str, Any]) -> Path:
    return PACKAGE / "features" / f"{rec['sample_id']}.receipt.json"


def verified_orientation(receipt: dict[str, Any], rec: dict[str, Any]) -> int:
    """Old diagnostic receipts pin orientation indirectly through the source probe."""
    if "orientation_degrees_clockwise" in receipt:
        return int(receipt["orientation_degrees_clockwise"])
    probe = (
        REPO
        / "datasets/fingerspelling/fsboard_candidate01_admission_20261002/admission_check_01/evidence/video_probe.json"
    )
    if receipt.get("source_probe_sha256") != sha256(probe):
        raise ValueError("[visual/package] No verified historical orientation probe")
    matches = [r for r in json.loads(probe.read_text()) if r["sample_id"] == rec["sample_id"]]
    if len(matches) != 1 or matches[0]["source_sha256"] != rec["source_sha256"]:
        raise ValueError("[visual/package] Historical source probe identity mismatch")
    return int(matches[0]["decoder_contract"]["orientation_degrees_clockwise"])


def load_visual(rec: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    path = receipt_path(rec)
    saved = json.loads(path.read_text())
    if (
        saved["schema_version"] != RECEIPT
        or saved["visual_identity"] != visual_identity()
        or saved["geometry_adapter"] != geometry_identity()
    ):
        raise ValueError("[visual/package] Schema/implementation identity mismatch")
    for key in [
        "sample_id",
        "source_sha256",
        "raw_sha256",
        "raw_receipt_sha256",
        "features_sha256",
        "split_role",
        "official_signer_id",
    ]:
        if saved["parent"][key] != rec[key]:
            raise ValueError("[visual/package] Parent lineage mismatch")
    artifact = REPO / saved["artifact_path"]
    if sha256(artifact) != saved["artifact_sha256"]:
        raise ValueError("[visual/package] Embedding artifact hash mismatch")
    raw = verify_raw(
        REPO / rec["raw_path"], REPO / rec["raw_receipt_path"], rec, rec["source_sha256"]
    )
    if sha256(REPO / rec["raw_receipt_path"]) != rec["raw_receipt_sha256"]:
        raise ValueError("[visual/package] Parent raw receipt changed")
    with np.load(artifact, allow_pickle=False) as data:
        meta = json.loads(str(data["metadata_json"].item()))
        if meta != saved["metadata"]:
            raise ValueError("[visual/package] Artifact metadata/receipt mismatch")
        features = np.array(data["embeddings"], dtype=np.float32)
        masks = np.array(data["crop_valid"], dtype=bool)
        frames, times = data["frame_index"], data["timestamp_ms"]
        rois, hashes = data["expanded_rois"], data["crop_sha256"]
        if not np.array_equal(frames, raw.frame_index) or not np.array_equal(
            times, raw.timestamp_ms
        ):
            raise ValueError("[visual/package] Raw/frame chronology mismatch")
        if (
            features.shape != (len(frames), 2, config()["embedding_width"])
            or masks.shape != (len(frames), 2)
            or hashes.shape != (len(frames), 2, 32)
            or rois.shape != (len(frames), 2, 3)
        ):
            raise ValueError("[visual/package] Tensor shape mismatch")
        if (
            not np.isfinite(features).all()
            or not np.isfinite(rois).all()
            or np.any(features[~masks])
            or np.any(hashes[~masks])
            or np.any(rois[~masks])
        ):
            raise ValueError("[visual/package] Nonfinite input or invalid crop not zero")
        if np.any(masks & ~raw.hand_proposal_present):
            raise ValueError("[visual/package] Crop without current proposal")
        if len(frames) != rec["frame_count"] or np.any(np.diff(times) <= 0):
            raise ValueError("[visual/package] Frame count/chronology mismatch")
    features.setflags(write=False)
    masks.setflags(write=False)
    return features, masks


def prepare(rec: dict[str, Any], tf: Any, encoder: Any, qa: bool = False) -> dict[str, Any]:
    if rec["split_role"] not in {"TRAIN", "DEV"}:
        raise ValueError("[visual/package] Protected role refused")
    source = REPO / rec["source_path"]
    if verify_source(source, rec) != rec["source_sha256"]:
        raise ValueError("[visual/package] Source SHA mismatch")
    path = receipt_path(rec)
    if path.exists():
        load_visual(rec)
        return {"sample_id": rec["sample_id"], "status": "REUSED_VERIFIED"}
    cfg = config()
    raw = verify_raw(
        REPO / rec["raw_path"], REPO / rec["raw_receipt_path"], rec, rec["source_sha256"]
    )
    if sha256(REPO / rec["raw_receipt_path"]) != rec["raw_receipt_sha256"]:
        raise ValueError("[visual/package] Raw receipt changed")
    n = len(raw.frame_index)
    embeddings = np.zeros((n, 2, cfg["embedding_width"]), np.float32)
    valid = np.zeros((n, 2), bool)
    rois = np.zeros((n, 2, 3), np.float32)
    hashes = np.zeros((n, 2, 32), np.uint8)
    pending: list[tuple[int, int, np.ndarray]] = []
    border_fractions, containment = [], []
    qa_rows = []
    qa_indices = {int(n * fraction) for fraction in [0.25, 0.5, 0.75]}
    started = time.perf_counter()
    inference_seconds = 0.0

    def flush() -> None:
        nonlocal inference_seconds
        if not pending:
            return
        t0 = time.perf_counter()
        values = encoder.apphear_encode(np.stack([item[2] for item in pending])).numpy()
        inference_seconds += time.perf_counter() - t0
        if not np.isfinite(values).all():
            raise ValueError("[visual/encoder] Nonfinite embedding")
        for (i, slot, _), value in zip(pending, values, strict=True):
            embeddings[i, slot] = value
        pending.clear()

    iterator, decoder = iter_video_frames(source, None)
    previous_receipt = json.loads((REPO / rec["raw_receipt_path"]).read_text())
    if decoder["orientation_degrees_clockwise"] != verified_orientation(previous_receipt, rec):
        raise ValueError("[visual/package] Upright orientation differs from raw extraction")
    count = 0
    for i, (frame, timestamp, _, rgb) in enumerate(iterator):
        if (
            i >= n
            or int(raw.frame_index[i]) != frame
            or abs(float(raw.timestamp_ms[i]) - timestamp) > cfg["timestamp_tolerance_ms"]
            or tuple(raw.source_size[i]) != (rgb.shape[1], rgb.shape[0])
        ):
            raise ValueError(
                "[visual/package] Source frame/dimensions/timestamp differs from raw"
            )
        for slot in range(2):
            pixels, info = hand_crop(
                rgb,
                raw.hand_roi_center_side[i, slot],
                bool(raw.hand_proposal_present[i, slot]),
                cfg,
            )
            if info["valid"]:
                valid[i, slot] = True
                rois[i, slot] = info["roi"]
                hashes[i, slot] = np.frombuffer(
                    hashlib.sha256(pixels.tobytes()).digest(), np.uint8
                )
                pending.append((i, slot, pixels))
                border_fractions.append(info["source_intersection_fraction"])
                joint_valid = raw.hand_joint_valid[i, slot]
                points = raw.hand_xy[i, slot][joint_valid]
                if len(points):
                    center, half = rois[i, slot, :2], rois[i, slot, 2] / 2
                    containment.append(
                        float(
                            np.mean(
                                np.all(
                                    (points >= center - half) & (points <= center + half),
                                    axis=1,
                                )
                            )
                        )
                    )
                if len(pending) >= cfg["encoder_batch_size"]:
                    flush()
            if qa and i in qa_indices:
                source_thumb = cv2.resize(rgb, (256, 256))
                shown = (
                    np.clip((pixels + 1) * 127.5, 0, 255).astype(np.uint8)
                    if info["valid"]
                    else np.zeros((cfg["crop_size"], cfg["crop_size"], 3), np.uint8)
                )
                qa_rows.append(
                    np.concatenate([source_thumb, cv2.resize(shown, (256, 256))], axis=1)
                )
        count += 1
    flush()
    if count != n:
        raise ValueError(
            "[visual/package] Source decoder ended before raw observation sequence"
        )
    quality = {
        "frames": n,
        "valid_slot_crops": int(valid.sum()),
        "any_crop_fraction": float(np.mean(valid.any(axis=1))),
        "slot_crop_fractions": valid.mean(axis=0).tolist(),
        "crops_with_refiner_rejected": int(np.sum(valid & ~raw.hand_observed)),
        "mean_joint_containment_when_observed": (
            float(np.mean(containment)) if containment else None
        ),
        "minimum_joint_containment_when_observed": min(containment) if containment else None,
        "mean_source_intersection_fraction": (
            float(np.mean(border_fractions)) if border_fractions else None
        ),
        "wall_seconds": time.perf_counter() - started,
        "encoder_seconds": inference_seconds,
    }
    metadata = {
        "schema_version": SCHEMA,
        "visual_identity": visual_identity(),
        "sample_id": rec["sample_id"],
        "source_sha256": rec["source_sha256"],
        "raw_sha256": rec["raw_sha256"],
        "geometry_feature_sha256": rec["features_sha256"],
        "reflection_policy": cfg["reflection_policy"],
        "orientation_degrees_clockwise": decoder["orientation_degrees_clockwise"],
        "decoder_version": cv2.__version__,
        "quality": quality,
    }
    artifact = PACKAGE / "features" / f"{rec['sample_id']}.npz"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    temp = artifact.with_suffix(".pending.npz")
    np.savez_compressed(
        temp,
        metadata_json=np.asarray(json.dumps(metadata, sort_keys=True)),
        embeddings=embeddings,
        crop_valid=valid,
        expanded_rois=rois,
        crop_sha256=hashes,
        frame_index=raw.frame_index,
        timestamp_ms=raw.timestamp_ms,
    )
    temp.replace(artifact)
    saved = {
        "schema_version": RECEIPT,
        "visual_identity": visual_identity(),
        "geometry_adapter": geometry_identity(),
        "parent": {
            k: rec[k]
            for k in [
                "sample_id",
                "source_sha256",
                "raw_sha256",
                "raw_receipt_sha256",
                "features_sha256",
                "split_role",
                "official_signer_id",
            ]
        },
        "artifact_path": artifact.relative_to(REPO).as_posix(),
        "artifact_sha256": sha256(artifact),
        "metadata": metadata,
    }
    write_json_atomic(path, saved)
    load_visual(rec)
    if qa_rows:
        destination = EVIDENCE / "crop_review" / f"{rec['sample_id']}.jpg"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(
            str(destination), cv2.cvtColor(np.concatenate(qa_rows, axis=0), cv2.COLOR_RGB2BGR)
        ):
            raise ValueError("[visual/qa] Unable to save contact sheet")
    return {"sample_id": rec["sample_id"], "status": "PREPARED_VALIDATED", "quality": quality}
