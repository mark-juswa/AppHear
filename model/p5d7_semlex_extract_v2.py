"""Resume-safe frozen DWPose-L -> V2 extraction for accepted Sem-Lex rows.

The module never mutates source videos or AppHear datasets. Full extraction is
project-lead-run only. Native 133-point evidence is retained before V2 build.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import tarfile
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.features.dwpose_representation_v2 import (
    BODY_OFFSET,
    FEATURE_WIDTH,
    LEFT_OBSERVED_OFFSET,
    RIGHT_HAND_OFFSET,
    RIGHT_OBSERVED_OFFSET,
    SEQUENCE_LENGTH,
    build_frame_features,
    build_padded_sequence,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/toolchain/source_snapshot/mmpose/configs/wholebody_2d_keypoint/rtmpose/ubody/rtmpose-l_8xb64-270e_coco-ubody-wholebody-256x192.py"
CHECKPOINT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/checkpoint/dw-ll_ucoco.pth"
P5A_CONTRACT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p5a_dwpose_representation_v2_01/p5a_representation_contract.json"
EXPECTED_CHECKPOINT_SHA = "e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7"
EXPECTED_CONFIG_SHA = "b2e741d2428667c99e74218f5170a183337602755c76e5b4138546a9b59d5032"
EXPECTED_CONTRACT_SHA = "0c94e9c885f331164d8ab1f7f0915eb89de43101394bd0949fae033b57f76d8b"
HAND_SCORE_THRESHOLD = 0.30
MIN_HAND_POINTS = 11


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_id(sample_id: str) -> str:
    return hashlib.sha256(sample_id.encode("utf-8")).hexdigest()[:24]


def platform_path(value: str) -> Path:
    if os.name != "nt" and len(value) > 2 and value[1:3] == ":\\":
        return Path(f"/mnt/{value[0].lower()}/" + value[3:].replace("\\", "/"))
    return Path(value)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_csv(path: Path, values: list[dict[str, Any]]) -> None:
    if not values:
        raise ValueError("cannot write an empty staged manifest")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(values[0]), extrasaction="ignore")
        writer.writeheader(); writer.writerows(values)
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_npz(path: Path, **values: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(handle, **values)
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


def verify_contracts() -> dict[str, str]:
    identity = {
        "checkpoint_sha256": sha256(CHECKPOINT),
        "config_sha256": sha256(CONFIG),
        "representation_contract_sha256": sha256(P5A_CONTRACT),
    }
    expected = {
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA,
        "config_sha256": EXPECTED_CONFIG_SHA,
        "representation_contract_sha256": EXPECTED_CONTRACT_SHA,
    }
    if identity != expected:
        raise RuntimeError(f"P5D7A_BLOCKED_DWPOSE_CONTRACT_MISMATCH: {identity}")
    return identity


def load_model(torch_threads: int = 0) -> tuple[Any, Any]:
    import torch  # noqa: F401
    from mmengine.dataset import Compose
    from mmpose.apis import init_model
    from mmpose.utils import register_all_modules

    register_all_modules()
    if torch_threads > 0:
        torch.set_num_threads(torch_threads)
    model = init_model(str(CONFIG), str(CHECKPOINT), device="cpu")
    if model.cfg.model.head.get("out_channels") != 133:
        raise RuntimeError("DWPose output is not 133 keypoints")
    if model.cfg.codec["input_size"] != (192, 256) or model.cfg.codec["simcc_split_ratio"] != 2.0:
        raise RuntimeError("DWPose input/decoder contract mismatch")
    if not model.cfg.model.test_cfg.get("flip_test", False):
        raise RuntimeError("frozen DWPose flip_test is disabled")
    return model, Compose(model.cfg.test_dataloader.dataset.pipeline)


def infer_frames(model: Any, pipeline: Any, frames: list[np.ndarray], batch_size: int) -> tuple[np.ndarray, np.ndarray]:
    import torch
    from mmengine.dataset import pseudo_collate
    if batch_size < 1:
        raise ValueError("frame batch size must be positive")
    all_xy: list[np.ndarray] = []
    all_scores: list[np.ndarray] = []
    for start in range(0, len(frames), batch_size):
        prepared = []
        for frame in frames[start:start + batch_size]:
            height, width = frame.shape[:2]
            info: dict[str, Any] = {
                "img": frame,
                "bbox": np.asarray([[0.0, 0.0, float(width), float(height)]], np.float32),
                "bbox_score": np.ones(1, np.float32),
            }
            info.update(model.dataset_meta)
            prepared.append(pipeline(info))
        batch = pseudo_collate(prepared)
        with torch.no_grad():
            results = model.test_step(batch)
        if len(results) != len(prepared):
            raise RuntimeError("DWPose batch result count mismatch")
        for result in results:
            xy = np.asarray(result.pred_instances.keypoints[0], np.float32)
            scores = np.asarray(result.pred_instances.keypoint_scores[0], np.float32)
            if xy.shape != (133, 2) or scores.shape != (133,) or not np.isfinite(xy).all() or not np.isfinite(scores).all():
                raise RuntimeError(f"invalid native DWPose output {xy.shape}/{scores.shape}")
            all_xy.append(xy); all_scores.append(scores)
    return np.stack(all_xy).astype(np.float32), np.stack(all_scores).astype(np.float32)


def decode_first_96(video: Path) -> tuple[list[np.ndarray], np.ndarray, np.ndarray, int, float]:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {video}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frames: list[np.ndarray] = []
    indices: list[int] = []
    timestamps: list[float] = []
    reached_eof = False
    for index in range(SEQUENCE_LENGTH):
        ok, frame = capture.read()
        if not ok:
            reached_eof = True
            break
        frames.append(frame); indices.append(index)
        timestamps.append(float(capture.get(cv2.CAP_PROP_POS_MSEC)))
    original_frames = len(frames)
    if not reached_eof:
        while capture.grab():
            original_frames += 1
    capture.release()
    if not frames:
        raise RuntimeError("video decoded zero frames")
    return frames, np.asarray(indices, np.int32), np.asarray(timestamps, np.float64), original_frames, fps


def invariant_errors(features: np.ndarray, mask: np.ndarray, length: int) -> list[str]:
    errors: list[str] = []
    if features.shape != (96, 238): errors.append("SHAPE")
    if features.dtype != np.float32: errors.append("DTYPE")
    if mask.shape != (96,) or mask.dtype != bool: errors.append("MASK")
    if not np.isfinite(features).all(): errors.append("NONFINITE")
    if not mask[:length].all() or mask[length:].any(): errors.append("NONCOMPACT_MASK")
    if np.any(features[length:] != 0): errors.append("NONZERO_PADDING")
    valid_channels = np.concatenate([
        np.arange(3, RIGHT_HAND_OFFSET, 4),
        np.arange(RIGHT_HAND_OFFSET + 3, BODY_OFFSET, 4),
        np.arange(BODY_OFFSET + 3, LEFT_OBSERVED_OFFSET, 4),
    ])
    if not np.isin(features[:length, valid_channels], [0.0, 1.0]).all(): errors.append("VALID_MASK_NONBINARY")
    if not np.isin(features[:length, [LEFT_OBSERVED_OFFSET, RIGHT_OBSERVED_OFFSET]], [0.0, 1.0]).all(): errors.append("OBSERVED_MASK_NONBINARY")
    for frame in features[:length]:
        if frame[LEFT_OBSERVED_OFFSET] == 0 and np.any(frame[:RIGHT_HAND_OFFSET] != 0): errors.append("LEFT_UNOBSERVED_NONZERO")
        if frame[RIGHT_OBSERVED_OFFSET] == 0 and np.any(frame[RIGHT_HAND_OFFSET:BODY_OFFSET] != 0): errors.append("RIGHT_UNOBSERVED_NONZERO")
        for start, stop in ((0, RIGHT_HAND_OFFSET), (RIGHT_HAND_OFFSET, BODY_OFFSET), (BODY_OFFSET, LEFT_OBSERVED_OFFSET)):
            block = frame[start:stop].reshape(-1, 4)
            if np.any(block[block[:, 3] == 0] != 0): errors.append("INVALID_LANDMARK_NONZERO")
    return sorted(set(errors))


def completed_ok(output_root: Path, row: dict[str, str]) -> bool:
    record = output_root / "completed" / f"{safe_id(row['semlex_sample_id'])}.json"
    if not record.is_file(): return False
    try:
        data = json.loads(record.read_text(encoding="utf-8"))
        for key in ("native", "v2"):
            path = output_root / data[f"{key}_relative_path"]
            if not path.is_file() or sha256(path) != data[f"{key}_sha256"]: return False
        if int(data.get("original_frame_count", -1)) < int(data.get("processed_frame_count", 0)): return False
        with np.load(output_root / data["native_relative_path"], allow_pickle=False) as native:
            if int(native["original_frame_count"]) < int(native["processed_frame_count"]): return False
        with np.load(output_root / data["v2_relative_path"], allow_pickle=False) as values:
            return not invariant_errors(values["features"], values["frame_mask"], int(values["length"]))
    except Exception:
        return False


def process_video(model: Any, pipeline: Any, row: dict[str, str], video: Path,
                  output_root: Path, identity: dict[str, str], frame_batch_size: int) -> dict[str, Any]:
    if sha256(video).lower() != row["raw_sha256"].lower():
        raise RuntimeError("raw video SHA-256 mismatch")
    started = time.perf_counter()
    frames, frame_indices, timestamps, original_frames, fps = decode_first_96(video)
    coordinates_a, scores_a = infer_frames(model, pipeline, frames, frame_batch_size)
    presence = np.stack([
        np.asarray([np.count_nonzero(score[91:112] >= HAND_SCORE_THRESHOLD) >= MIN_HAND_POINTS,
                    np.count_nonzero(score[112:133] >= HAND_SCORE_THRESHOLD) >= MIN_HAND_POINTS], bool)
        for score in scores_a
    ])
    built, centers, scales = [], [], []
    for index in range(len(coordinates_a)):
        feature, diagnostic = build_frame_features(coordinates_a[index], scores_a[index], presence[index])
        built.append(feature); centers.append(diagnostic.center_method); scales.append(diagnostic.scale_method)
    sequence, frame_mask, length = build_padded_sequence(built)
    errors = invariant_errors(sequence, frame_mask, length)
    if errors: raise RuntimeError(f"V2 invariant failure: {errors}")
    identifier = safe_id(row["semlex_sample_id"])
    native = output_root / "native" / f"{identifier}.npz"
    v2 = output_root / "v2" / f"{identifier}.npz"
    atomic_npz(native, keypoints_xy=coordinates_a, scores=scores_a, frame_indices=frame_indices,
               timestamps_ms=timestamps, sample_id=np.asarray(row["semlex_sample_id"]),
               source_raw_sha256=np.asarray(row["raw_sha256"].lower()), signer_id=np.asarray(row["semlex_signer_id"]),
               lexical_id=np.asarray(row["semlex_lexical_id"]), original_frame_count=np.asarray(original_frames, np.int64),
               processed_frame_count=np.asarray(len(frames), np.int32), checkpoint_sha256=np.asarray(EXPECTED_CHECKPOINT_SHA))
    atomic_npz(v2, features=sequence, frame_mask=frame_mask, length=np.asarray(length, np.int32),
               class_id=np.asarray(int(row["apphear_class_id"]), np.int32), sample_id=np.asarray(row["semlex_sample_id"]),
               signer_id=np.asarray(row["semlex_signer_id"]), left_observed=presence[:, 0], right_observed=presence[:, 1],
               center_methods=np.asarray(centers), scale_methods=np.asarray(scales))
    result = {
        "sample_id": row["semlex_sample_id"], "apphear_class_id": int(row["apphear_class_id"]),
        "apphear_gloss": row["apphear_gloss"], "human_decision": row["human_decision"],
        "signer_id": row["semlex_signer_id"], "lexical_id": row["semlex_lexical_id"],
        "raw_sha256": row["raw_sha256"].lower(), "original_frame_count": original_frames,
        "processed_frame_count": len(frames), "stored_length": length, "fps": fps,
        "frame_batch_size": frame_batch_size,
        "temporal_contract": "WHOLE_ISOLATED_SOURCE_CLIP_FIRST_96_NO_RESAMPLING_ZERO_TAIL",
        "native_relative_path": native.relative_to(output_root).as_posix(), "native_sha256": sha256(native),
        "v2_relative_path": v2.relative_to(output_root).as_posix(), "v2_sha256": sha256(v2),
        "elapsed_seconds": time.perf_counter() - started, "invariant_errors": [], **identity,
    }
    atomic_json(output_root / "completed" / f"{identifier}.json", result)
    failure = output_root / "failures" / f"{identifier}.json"
    if failure.exists(): failure.unlink()
    return result


def extract_files(args: argparse.Namespace) -> int:
    identity = verify_contracts()
    manifest = read_csv(platform_path(args.manifest))
    if len(manifest) > 3: raise RuntimeError("P5-D7A smoke may process at most three videos")
    output_root = platform_path(args.output_root)
    model, pipeline = load_model(args.torch_threads)
    failed = 0
    for position, row in enumerate(manifest, 1):
        if completed_ok(output_root, row):
            print(json.dumps({"position": position, "total": len(manifest), "status": "VERIFIED_SKIP", "sample_id": row["semlex_sample_id"]}), flush=True)
            continue
        try:
            result = process_video(model, pipeline, row, platform_path(row["raw_video_path"]), output_root, identity, args.frame_batch_size)
            print(json.dumps({"position": position, "total": len(manifest), "status": "COMPLETED",
                              "sample_id": row["semlex_sample_id"], "seconds": result["elapsed_seconds"]}), flush=True)
        except Exception as exc:
            failed += 1
            atomic_json(output_root / "failures" / f"{safe_id(row['semlex_sample_id'])}.json",
                        {"sample_id": row["semlex_sample_id"], "error": repr(exc)})
            print(f"FAILED {row['semlex_sample_id']}: {exc}", flush=True)
    return 1 if failed else 0


def extract_archive(args: argparse.Namespace) -> int:
    identity = verify_contracts()
    manifest = [row for row in read_csv(platform_path(args.manifest)) if row.get("eligible_for_extraction", "").lower() == "true"]
    if args.sample_id: manifest = [row for row in manifest if row["semlex_sample_id"] == args.sample_id]
    if args.limit: manifest = manifest[:args.limit]
    expected = {row["archive_member"].lstrip("./"): row for row in manifest}
    output_root = platform_path(args.output_root)
    pending = {member: row for member, row in expected.items() if not completed_ok(output_root, row)}
    preexisting = len(manifest) - len(pending)
    model, pipeline = load_model(args.torch_threads)
    archive_path = platform_path(args.archive)
    temp_root = output_root / "temporary_raw"
    completed = failed = 0
    last_reported_percent = -1
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive:
            normalized = member.name.lstrip("./")
            row = pending.get(normalized)
            if row is not None:
                temporary = temp_root / f"{safe_id(row['semlex_sample_id'])}.webm"
                temporary.parent.mkdir(parents=True, exist_ok=True)
                partial = temporary.with_suffix(".webm.partial")
                source = archive.extractfile(member)
                if source is None:
                    failed += 1; continue
                with source, partial.open("wb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
                os.replace(partial, temporary)
                try:
                    process_video(model, pipeline, row, temporary, output_root, identity, args.frame_batch_size)
                    completed += 1
                except Exception as exc:
                    failed += 1
                    atomic_json(output_root / "failures" / f"{safe_id(row['semlex_sample_id'])}.json",
                                {"sample_id": row["semlex_sample_id"], "error": repr(exc)})
                    print(f"FAILED {row['semlex_sample_id']}: {exc}", flush=True)
                finally:
                    if temporary.exists(): temporary.unlink()
                del pending[normalized]
            compressed = getattr(archive.fileobj, "fileobj", None)
            position = compressed.tell() if compressed is not None else 0
            percent = min(100, int(100 * position / archive_path.stat().st_size))
            if row is not None or (percent % 2 == 0 and percent != last_reported_percent):
                print(f"\rArchive {percent:3d}% | completed {completed} | failed {failed} | pending {len(pending)}", end="", flush=True)
                last_reported_percent = percent
            if not pending: break
    print()
    for member, row in pending.items():
        if completed_ok(output_root, row): continue
        failed += 1
        atomic_json(output_root / "failures" / f"{safe_id(row['semlex_sample_id'])}.json",
                    {"sample_id": row["semlex_sample_id"], "error": f"ARCHIVE_MEMBER_NOT_FOUND:{member}"})
    atomic_json(output_root / "run_summary.json", {"expected": len(manifest), "completed_this_run": completed,
                "verified_preexisting": preexisting, "failed": failed,
                "full_extraction_command": True})
    return 1 if failed else 0


def stage_archive(args: argparse.Namespace) -> int:
    """Project-lead step: stream selected raw members once to a G-drive staging root."""
    manifest = [row for row in read_csv(platform_path(args.manifest)) if row.get("eligible_for_extraction", "").lower() == "true"]
    archive_path = platform_path(args.archive)
    staging_root = platform_path(args.staging_root)
    staged_rows: list[dict[str, Any]] = []
    pending: dict[str, tuple[dict[str, str], Path]] = {}
    for row in manifest:
        target = staging_root / "raw" / f"{safe_id(row['semlex_sample_id'])}.webm"
        staged = dict(row); staged["raw_video_path"] = str(target); staged["mapping_status"] = "STAGED_RAW_VERIFIED"
        staged_rows.append(staged)
        if not target.is_file() or sha256(target).lower() != row["raw_sha256"].lower():
            pending[row["archive_member"].lstrip("./")] = (row, target)
    last_percent = -1
    staged_this_run = failed = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive:
            normalized = member.name.lstrip("./")
            item = pending.get(normalized)
            if item is not None:
                row, target = item
                target.parent.mkdir(parents=True, exist_ok=True)
                partial = target.with_suffix(".webm.partial")
                source = archive.extractfile(member)
                try:
                    if source is None: raise RuntimeError("archive member cannot be opened")
                    with source, partial.open("wb") as handle:
                        shutil.copyfileobj(source, handle, length=1024 * 1024)
                        handle.flush(); os.fsync(handle.fileno())
                    if sha256(partial).lower() != row["raw_sha256"].lower():
                        raise RuntimeError("staged raw SHA-256 mismatch")
                    os.replace(partial, target); staged_this_run += 1
                except Exception as exc:
                    failed += 1
                    if partial.exists(): partial.unlink()
                    print(f"FAILED STAGE {row['semlex_sample_id']}: {exc}", flush=True)
                del pending[normalized]
            compressed = getattr(archive.fileobj, "fileobj", None)
            position = compressed.tell() if compressed is not None else 0
            percent = min(100, int(100 * position / archive_path.stat().st_size))
            if percent != last_percent:
                print(f"\rArchive staging {percent:3d}% | staged this run {staged_this_run} | pending {len(pending)} | failed {failed}", end="", flush=True)
                last_percent = percent
            if not pending: break
    print()
    for member, (row, _) in pending.items():
        failed += 1; print(f"MISSING STAGE MEMBER {row['semlex_sample_id']}: {member}", flush=True)
    verified_rows = [row for row in staged_rows if platform_path(row["raw_video_path"]).is_file() and sha256(platform_path(row["raw_video_path"])).lower() == row["raw_sha256"].lower()]
    atomic_csv(staging_root / "staged_manifest.csv", verified_rows)
    atomic_json(staging_root / "staging_summary.json", {"expected": len(manifest), "verified_staged": len(verified_rows),
                "staged_this_run": staged_this_run, "failed": failed, "passed": len(verified_rows) == len(manifest)})
    return 0 if len(verified_rows) == len(manifest) else 1


def extract_staged(args: argparse.Namespace) -> int:
    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        raise ValueError("invalid shard index/count")
    identity = verify_contracts()
    manifest = [row for row in read_csv(platform_path(args.manifest)) if row.get("eligible_for_extraction", "true").lower() == "true"]
    manifest = [row for row in manifest if int(hashlib.sha256(row["semlex_sample_id"].encode()).hexdigest(), 16) % args.shard_count == args.shard_index]
    output_root = platform_path(args.output_root)
    model, pipeline = load_model(args.torch_threads)
    completed = failed = skipped = 0
    for position, row in enumerate(manifest, 1):
        if completed_ok(output_root, row):
            skipped += 1; continue
        try:
            result = process_video(model, pipeline, row, platform_path(row["raw_video_path"]), output_root, identity, args.frame_batch_size)
            completed += 1
            print(f"worker {args.shard_index}: {position}/{len(manifest)} completed {result['sample_id']} in {result['elapsed_seconds']:.2f}s", flush=True)
        except Exception as exc:
            failed += 1
            atomic_json(output_root / "failures" / f"{safe_id(row['semlex_sample_id'])}.json",
                        {"sample_id": row["semlex_sample_id"], "error": repr(exc), "shard_index": args.shard_index})
            print(f"worker {args.shard_index}: FAILED {row['semlex_sample_id']}: {exc}", flush=True)
    atomic_json(output_root / f"run_summary_worker_{args.shard_index}.json", {
        "shard_index": args.shard_index, "shard_count": args.shard_count, "expected": len(manifest),
        "completed_this_run": completed, "verified_preexisting": skipped, "failed": failed,
        "frame_batch_size": args.frame_batch_size, "torch_threads": args.torch_threads,
    })
    return 1 if failed else 0


def verify_outputs(manifest_path: Path, output_root: Path) -> dict[str, Any]:
    rows = [row for row in read_csv(manifest_path) if row.get("eligible_for_extraction", "true").lower() == "true"]
    completed = failed = missing = corrupt = shape = lineage = 0
    details: list[dict[str, str]] = []
    for row in rows:
        identifier = safe_id(row["semlex_sample_id"])
        record_path = output_root / "completed" / f"{identifier}.json"
        failure_path = output_root / "failures" / f"{identifier}.json"
        if failure_path.is_file() and not record_path.is_file(): failed += 1; details.append({"sample_id": row["semlex_sample_id"], "status": "FAILED"}); continue
        if not record_path.is_file(): missing += 1; details.append({"sample_id": row["semlex_sample_id"], "status": "MISSING"}); continue
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
            native = output_root / record["native_relative_path"]
            v2 = output_root / record["v2_relative_path"]
            if not native.is_file() or not v2.is_file() or sha256(native) != record["native_sha256"] or sha256(v2) != record["v2_sha256"]:
                corrupt += 1; details.append({"sample_id": row["semlex_sample_id"], "status": "CORRUPT"}); continue
            with np.load(v2, allow_pickle=False) as values:
                errors = invariant_errors(values["features"], values["frame_mask"], int(values["length"]))
                if errors: shape += 1; details.append({"sample_id": row["semlex_sample_id"], "status": "V2_INVALID"}); continue
                if str(values["sample_id"]) != row["semlex_sample_id"] or int(values["class_id"]) != int(row["apphear_class_id"]):
                    lineage += 1; details.append({"sample_id": row["semlex_sample_id"], "status": "LINEAGE_INVALID"}); continue
            completed += 1
        except Exception:
            corrupt += 1; details.append({"sample_id": row["semlex_sample_id"], "status": "CORRUPT"})
    result = {"expected_samples": len(rows), "completed_native_and_v2": completed, "failed_samples": failed,
              "missing_samples": missing, "corrupt_outputs": corrupt, "shape_failures": shape,
              "lineage_failures": lineage, "completion_percentage": 100 * completed / len(rows) if rows else 0,
              "passed": completed == len(rows), "details": details[:200]}
    atomic_json(output_root / "verification_summary.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    smoke = sub.add_parser("extract-files")
    smoke.add_argument("--manifest", required=True); smoke.add_argument("--output-root", required=True)
    smoke.add_argument("--frame-batch-size", type=int, default=1)
    smoke.add_argument("--torch-threads", type=int, default=0)
    smoke.set_defaults(func=extract_files)
    full = sub.add_parser("extract-archive")
    full.add_argument("--manifest", required=True); full.add_argument("--archive", required=True)
    full.add_argument("--output-root", required=True); full.add_argument("--sample-id"); full.add_argument("--limit", type=int)
    full.add_argument("--frame-batch-size", type=int, default=1)
    full.add_argument("--torch-threads", type=int, default=0)
    full.set_defaults(func=extract_archive)
    stage = sub.add_parser("stage-archive")
    stage.add_argument("--manifest", required=True); stage.add_argument("--archive", required=True)
    stage.add_argument("--staging-root", required=True); stage.set_defaults(func=stage_archive)
    staged = sub.add_parser("extract-staged")
    staged.add_argument("--manifest", required=True); staged.add_argument("--output-root", required=True)
    staged.add_argument("--shard-count", type=int, required=True); staged.add_argument("--shard-index", type=int, required=True)
    staged.add_argument("--frame-batch-size", type=int, default=1); staged.add_argument("--torch-threads", type=int, default=0)
    staged.set_defaults(func=extract_staged)
    verify = sub.add_parser("verify")
    verify.add_argument("--manifest", required=True); verify.add_argument("--output-root", required=True)
    verify.set_defaults(func=lambda args: (print(json.dumps(verify_outputs(platform_path(args.manifest), platform_path(args.output_root)), indent=2)), 0)[1])
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
