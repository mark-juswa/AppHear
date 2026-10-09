"""Trusted appearance sidecars; geometry and previous visual artifacts are immutable."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from model.fingerspelling_appearance import encoder_identity
from pipeline.fingerspelling.adapter import identity as adapter_identity
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import verify_raw, verify_source
from pipeline.fingerspelling.visual_crop import (
    config as crop_config,
)
from pipeline.fingerspelling.visual_crop import (
    crop_identity,
    hand_crop,
)
from pipeline.fingerspelling.visual_package import (
    load_visual,
    verified_orientation,
)
from pipeline.fingerspelling.visual_package import (
    receipt_path as old_receipt,
)
from pipeline.fingerspelling.visual_quality import identity as quality_identity
from pipeline.fingerspelling.visual_quality import quality
from pipeline.perception_vnext.offline_candidate01 import iter_video_frames
from pipeline.perception_vnext.recognition_schema import RawSequence

PACKAGE = REPO / "datasets/fingerspelling/residual_visual_01"
SCHEMA = "apphear.fingerspelling.residual_visual_sequence.v1"
PARENT_KEYS = [
    "sample_id",
    "source_sha256",
    "raw_sha256",
    "raw_receipt_sha256",
    "features_sha256",
    "split_role",
    "official_signer_id",
]


def identity() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "quality": quality_identity(),
        "crop": crop_identity(),
        "encoder": encoder_identity(),
        "adapter": adapter_identity(),
        "implementation_sha256": sha256(
            REPO / "pipeline/fingerspelling/residual_visual_package.py"
        ),
    }


def receipt_path(rec: dict[str, Any]) -> Path:
    return PACKAGE / "features" / f"{rec['sample_id']}.receipt.json"


def raw_for(rec: dict[str, Any]) -> RawSequence:
    if rec["split_role"] not in ["TRAIN", "DEV"]:
        raise ValueError("[residual/package] TEST or unknown role refused")
    if sha256(REPO / rec["raw_receipt_path"]) != rec["raw_receipt_sha256"]:
        raise ValueError("[residual/package] Raw receipt changed")
    return verify_raw(
        REPO / rec["raw_path"],
        REPO / rec["raw_receipt_path"],
        rec,
        rec["source_sha256"],
    )


def load(rec: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    saved = json.loads(receipt_path(rec).read_text())
    if saved["identity"] != identity() or saved["parent"] != {
        k: rec[k] for k in PARENT_KEYS
    }:
        raise ValueError("[residual/package] Identity/lineage mismatch")
    path = REPO / saved["artifact_path"]
    if sha256(path) != saved["artifact_sha256"]:
        raise ValueError("[residual/package] Artifact hash mismatch")
    raw = raw_for(rec)
    q = quality(raw)
    with np.load(path, allow_pickle=False) as data:
        if json.loads(str(data["metadata_json"].item())) != saved["metadata"]:
            raise ValueError("[residual/package] Metadata mismatch")
        for key, value in q.items():
            if not np.array_equal(data[key], value):
                raise ValueError(
                    f"[residual/package] Quality/dedup evidence mismatch: {key}"
                )
        if not np.array_equal(
            data["frame_index"], raw.frame_index
        ) or not np.array_equal(data["timestamp_ms"], raw.timestamp_ms):
            raise ValueError("[residual/package] Frame identity/order mismatch")
        emb = np.array(data["embeddings"], np.float32)
        hashes = data["crop_sha256"]
        trusted = q["quality"] > 0
        if (
            emb.shape != (len(raw.frame_index), 2, 576)
            or not np.isfinite(emb).all()
            or np.any(emb[~trusted])
            or hashes.shape != (len(emb), 2, 32)
            or np.any(hashes[~trusted])
            or np.any(~hashes[trusted].any(axis=-1))
        ):
            raise ValueError(
                "[residual/package] Invalid embedding/missingness/crop lineage"
            )
    return emb, q["quality"]


def prepare(rec: dict[str, Any], encoder: Any = None) -> dict[str, Any]:
    if receipt_path(rec).exists():
        load(rec)
        return {"sample_id": rec["sample_id"], "status": "REUSED_VERIFIED"}
    raw = raw_for(rec)
    source = REPO / rec["source_path"]
    if verify_source(source, rec) != rec["source_sha256"]:
        raise ValueError("[residual/package] Source identity changed")
    q = quality(raw)
    trusted = q["quality"] > 0
    n = len(raw.frame_index)
    emb = np.zeros((n, 2, 576), np.float32)
    hashes = np.zeros((n, 2, 32), np.uint8)
    started = time.perf_counter()
    reused = None
    if old_receipt(rec).exists():
        previous, available = load_visual(rec)
        if np.any(trusted & ~available):
            raise ValueError(
                "[residual/package] Trusted crop absent from historical package"
            )
        saved = json.loads(old_receipt(rec).read_text())
        with np.load(REPO / saved["artifact_path"], allow_pickle=False) as data:
            if not np.array_equal(
                data["expanded_rois"][trusted], q["expanded_rois"][trusted]
            ):
                raise ValueError(
                    "[residual/package] Historical crop coordinates changed"
                )
            hashes[trusted] = data["crop_sha256"][trusted]
        emb[trusted] = previous[trusted]
        reused = {
            "receipt_path": old_receipt(rec).relative_to(REPO).as_posix(),
            "receipt_sha256": sha256(old_receipt(rec)),
            "artifact_sha256": saved["artifact_sha256"],
        }
    else:
        if encoder is None:
            raise ValueError(
                "[residual/package] Frozen encoder required for new frames"
            )
        iterator, decoder = iter_video_frames(source, None)
        saved_raw = json.loads((REPO / rec["raw_receipt_path"]).read_text())
        if decoder["orientation_degrees_clockwise"] != verified_orientation(
            saved_raw, rec
        ):
            raise ValueError("[residual/package] Orientation differs from raw")
        pending: list[tuple[int, int, np.ndarray]] = []

        def flush() -> None:
            if not pending:
                return
            values = encoder.apphear_encode(np.stack([x[2] for x in pending])).numpy()
            if not np.isfinite(values).all():
                raise ValueError("[residual/package] Nonfinite encoder output")
            for (i, s, _), value in zip(pending, values, strict=True):
                emb[i, s] = value
            pending.clear()

        count = 0
        for i, (frame, timestamp, _, rgb) in enumerate(iterator):
            if (
                i >= n
                or frame != raw.frame_index[i]
                or abs(timestamp - raw.timestamp_ms[i]) > 0.1
                or tuple(raw.source_size[i]) != (rgb.shape[1], rgb.shape[0])
            ):
                raise ValueError(
                    "[residual/package] Source/raw frame alignment mismatch"
                )
            for slot in range(2):
                if trusted[i, slot]:
                    pixels, info = hand_crop(
                        rgb,
                        raw.hand_roi_center_side[i, slot],
                        bool(raw.hand_proposal_present[i, slot]),
                    )
                    if not info["valid"] or not np.array_equal(
                        info["roi"], q["expanded_rois"][i, slot]
                    ):
                        raise ValueError(
                            "[residual/package] Crop differs from quality geometry"
                        )
                    hashes[i, slot] = np.frombuffer(
                        hashlib.sha256(pixels.tobytes()).digest(), np.uint8
                    )
                    pending.append((i, slot, pixels))
                    if len(pending) >= crop_config()["encoder_batch_size"]:
                        flush()
            count += 1
        flush()
        if count != n:
            raise ValueError("[residual/package] Decoded frame count differs from raw")
    meta = {
        "schema_version": SCHEMA,
        "identity": identity(),
        "source_sha256": rec["source_sha256"],
        "raw_sha256": rec["raw_sha256"],
        "geometry_sha256": rec["features_sha256"],
        "reflection_policy": "USE_RELEASED_PIXELS_AS_IS",
        "historical_reuse": reused,
        "decoder_version": cv2.__version__,
        "frames": n,
        "retained_slots": int(trusted.sum()),
        "duplicate_frames": int(q["duplicate"].sum()),
        "no_crop_frames": int((~trusted.any(axis=1)).sum()),
        "seconds": time.perf_counter() - started,
        "test_accessed": False,
    }
    path = PACKAGE / "features" / f"{rec['sample_id']}.npz"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".pending.npz")
    np.savez_compressed(
        tmp,
        metadata_json=np.asarray(json.dumps(meta, sort_keys=True)),
        embeddings=emb,
        crop_sha256=hashes,
        frame_index=raw.frame_index,
        timestamp_ms=raw.timestamp_ms,
        quality=q["quality"],
        quality_before_dedup=q["quality_before_dedup"],
        rejection_bits=q["rejection_bits"],
        duplicate=q["duplicate"],
        suppressed=q["suppressed"],
        expanded_rois=q["expanded_rois"],
        source_intersection=q["source_intersection"],
        joint_containment=q["joint_containment"],
    )
    tmp.replace(path)
    write_json_atomic(
        receipt_path(rec),
        {
            "identity": identity(),
            "parent": {k: rec[k] for k in PARENT_KEYS},
            "artifact_path": path.relative_to(REPO).as_posix(),
            "artifact_sha256": sha256(path),
            "metadata": meta,
        },
    )
    load(rec)
    return {
        "sample_id": rec["sample_id"],
        "status": "PREPARED_VALIDATED",
        "metadata": meta,
    }
