"""P5-B resumable DWPose-native dataset migration.

Full extraction is intentionally user-run.  This module preserves native 133-point
outputs before deriving the frozen DWPOSE_REPRESENTATION_V2_238 tensors.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.features.dwpose_representation_v2 import (
    FEATURE_WIDTH,
    SEQUENCE_LENGTH,
    build_frame_features,
    build_padded_sequence,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "artifacts/recognition_upgrade/phase1_full_vocab/manifest_01/canonical_manifest.csv"
VOCAB = ROOT / "artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1/vocab.json"
P5A_CONTRACT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p5a_dwpose_representation_v2_01/p5a_representation_contract.json"
OUT = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5b_migration_01"
CONFIG = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/toolchain/source_snapshot/mmpose/configs/wholebody_2d_keypoint/rtmpose/ubody/rtmpose-l_8xb64-270e_coco-ubody-wholebody-256x192.py"
CHECKPOINT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/checkpoint/dw-ll_ucoco.pth"

EXPECTED_ROWS = 8131
EXPECTED_CLASSES = 236
EXPECTED_MANIFEST_SHA = "8c1fab3df04a0240b5a178853b2206408806958afebdd19bd3d44d6fca606571"
EXPECTED_CHECKPOINT_SHA = "e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7"
EXPECTED_CONTRACT_SHA = "0c94e9c885f331164d8ab1f7f0915eb89de43101394bd0949fae033b57f76d8b"
EXPECTED_ROLES = {
    "primary_train": 3309,
    "supplement_train": 617,
    "primary_val": 816,
    "primary_test": 2620,
    "supplement_validation_stress": 163,
    "reused_positive_diagnostic": 300,
    "protected_clean_replay": 306,
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def atomic_npz(path: Path, **values: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        np.savez_compressed(f, **values)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fields = sorted({key for row in rows for key in row}) if rows else ["sample_id"]
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def safe_id(sample_id: str) -> str:
    return hashlib.sha256(sample_id.encode("utf-8")).hexdigest()[:24]


def platform_path(value: str) -> Path:
    if os.name != "nt" and len(value) > 2 and value[1:3] == ":\\":
        drive = value[0].lower()
        return Path(f"/mnt/{drive}/" + value[3:].replace("\\", "/"))
    return Path(value)


def read_rows() -> list[dict[str, str]]:
    if sha256(MANIFEST) != EXPECTED_MANIFEST_SHA:
        raise RuntimeError("canonical manifest SHA-256 mismatch")
    with MANIFEST.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != EXPECTED_ROWS or len({r["class_id"] for r in rows}) != EXPECTED_CLASSES:
        raise RuntimeError(f"canonical identity mismatch rows={len(rows)} classes={len({r['class_id'] for r in rows})}")
    roles = Counter(r["role"] for r in rows)
    if dict(roles) != EXPECTED_ROLES:
        raise RuntimeError(f"canonical role mismatch: {dict(roles)}")
    if len({r["sample_id"] for r in rows}) != len(rows):
        raise RuntimeError("duplicate canonical sample_id")
    return rows


def verify_identity(verify_checkpoint: bool = True) -> dict[str, str]:
    values = {
        "canonical_manifest_sha256": sha256(MANIFEST),
        "representation_contract_sha256": sha256(P5A_CONTRACT),
        "checkpoint_sha256": sha256(CHECKPOINT) if verify_checkpoint else EXPECTED_CHECKPOINT_SHA,
        "config_sha256": sha256(CONFIG),
    }
    if values["representation_contract_sha256"] != EXPECTED_CONTRACT_SHA:
        raise RuntimeError("P5-A representation contract SHA-256 mismatch")
    if verify_checkpoint and values["checkpoint_sha256"] != EXPECTED_CHECKPOINT_SHA:
        raise RuntimeError("DWPose checkpoint SHA-256 mismatch")
    return values


def governance(row: dict[str, str], frame_count: int) -> tuple[int, int, str]:
    if row["source_dataset"] == "ASL_CITIZEN":
        sidecar = platform_path(row["span_path"])
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        onset, release = int(data["onset"]), int(data["release"])
        source = "frozen_stage_e_span_onset_release_inclusive"
    else:
        onset, release = 0, frame_count - 1
        source = (
            "historical_e6_whole_isolated_clip"
            if row["role"] != "protected_clean_replay"
            else "canonical_reserved_whole_isolated_clip"
        )
    if onset < 0 or release < onset or release >= frame_count:
        raise RuntimeError(f"invalid governed span {onset}..{release} for {frame_count} frames")
    return onset, release, source


def decode_governed(video: Path, row: dict[str, str], max_frames: int | None) -> tuple[list[np.ndarray], np.ndarray, np.ndarray, str]:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video: {video}")
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    onset, release, source = governance(row, n)
    stop = min(release, onset + max_frames - 1) if max_frames else release
    frames, indices, timestamps = [], [], []
    cap.set(cv2.CAP_PROP_POS_FRAMES, onset)
    for index in range(onset, stop + 1):
        ok, frame = cap.read()
        if not ok:
            cap.release()
            raise RuntimeError(f"decode failed at frame {index}: {video}")
        frames.append(frame)
        indices.append(index)
        timestamps.append(float(cap.get(cv2.CAP_PROP_POS_MSEC)))
    cap.release()
    if not frames:
        raise RuntimeError("governed span decoded zero frames")
    if not np.isfinite(fps) or fps <= 0:
        fps = 0.0
    return frames, np.asarray(indices, np.int32), np.asarray(timestamps, np.float64), source


def load_model() -> tuple[Any, Any]:
    import torch  # noqa: F401
    from mmengine.dataset import Compose
    from mmpose.apis import init_model
    from mmpose.utils import register_all_modules

    register_all_modules()
    model = init_model(str(CONFIG), str(CHECKPOINT), device="cpu")
    if model.cfg.model.head.get("out_channels") != 133:
        raise RuntimeError("DWPose output is not 133 keypoints")
    if model.cfg.codec["input_size"] != (192, 256) or model.cfg.codec["simcc_split_ratio"] != 2.0:
        raise RuntimeError("DWPose decoder/input contract mismatch")
    if not model.cfg.model.test_cfg.get("flip_test", False):
        raise RuntimeError("frozen flip-test is disabled")
    return model, Compose(model.cfg.test_dataloader.dataset.pipeline)


def infer_frame(model: Any, pipeline: Any, frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    import torch
    from mmengine.dataset import pseudo_collate
    h, w = frame.shape[:2]
    info: dict[str, Any] = {
        "img": frame,
        "bbox": np.asarray([[0.0, 0.0, float(w), float(h)]], np.float32),
        "bbox_score": np.ones(1, np.float32),
    }
    info.update(model.dataset_meta)
    batch = pseudo_collate([pipeline(info)])
    with torch.no_grad():
        result = model.test_step(batch)[0]
    xy = np.asarray(result.pred_instances.keypoints[0], np.float32)
    score = np.asarray(result.pred_instances.keypoint_scores[0], np.float32)
    if xy.shape != (133, 2) or score.shape != (133,) or not np.isfinite(xy).all() or not np.isfinite(score).all():
        raise RuntimeError(f"invalid native output {xy.shape}/{score.shape}")
    return xy, score


def verified_cached(record: Path, allow_smoke: bool = False) -> bool:
    if not record.is_file():
        return False
    try:
        data = json.loads(record.read_text(encoding="utf-8"))
        if data.get("smoke_truncated") and not allow_smoke:
            return False
        for key in ("native_path", "feature_path"):
            p = ROOT / data[key]
            if not p.is_file() or sha256(p) != data[key.replace("path", "sha256")]:
                return False
        with np.load(ROOT / data["feature_path"], allow_pickle=False) as z:
            return z["features"].shape == (96, 238) and z["frame_mask"].shape == (96,)
    except Exception:
        return False


def extract(args: argparse.Namespace) -> int:
    rows = read_rows()
    identity = verify_identity(True)
    if args.smoke:
        chosen = []
        for role in ("primary_train", "primary_val", "primary_test"):
            chosen.append(next(r for r in rows if r["role"] == role))
        rows = chosen
    elif args.limit:
        rows = rows[: args.limit]
    OUT.mkdir(parents=True, exist_ok=True)
    model, pipeline = load_model()
    started = time.perf_counter()
    completed = skipped = failed = 0
    for ordinal, row in enumerate(rows, 1):
        sid = safe_id(row["sample_id"])
        record = OUT / "completed" / f"{sid}.json"
        if verified_cached(record, allow_smoke=args.smoke):
            skipped += 1
            if ordinal == 1 or ordinal % 25 == 0 or ordinal == len(rows):
                print(json.dumps({"completed_this_run": completed, "verified_skipped": skipped,
                                  "failed": failed, "position": ordinal, "total": len(rows),
                                  "remaining": len(rows)-ordinal}), flush=True)
            continue
        try:
            video = platform_path(row["raw_video_path"])
            if sha256(video).upper() != row["raw_video_sha256"].upper():
                raise RuntimeError("raw video SHA-256 mismatch")
            frames, frame_idx, ts, gov = decode_governed(video, row, args.max_frames)
            coords, scores = [], []
            for frame in frames:
                xy, sc = infer_frame(model, pipeline, frame)
                coords.append(xy); scores.append(sc)
            coords_a, scores_a = np.stack(coords), np.stack(scores)
            native = OUT / "native" / f"{sid}.npz"
            atomic_npz(native, keypoints_xy=coords_a, scores=scores_a, frame_indices=frame_idx,
                       timestamps_ms=ts, sample_id=np.asarray(row["sample_id"]),
                       source_video_sha256=np.asarray(row["raw_video_sha256"].lower()),
                       checkpoint_sha256=np.asarray(EXPECTED_CHECKPOINT_SHA))
            presence = np.stack([
                np.asarray([np.count_nonzero(sc[91:112] >= 0.30) >= 11,
                            np.count_nonzero(sc[112:133] >= 0.30) >= 11], dtype=bool)
                for sc in scores_a
            ])
            built = [build_frame_features(coords_a[i], scores_a[i], presence[i])[0] for i in range(len(coords_a))]
            seq, mask, length = build_padded_sequence(built)
            feature = OUT / "features" / f"{sid}.npz"
            atomic_npz(feature, features=seq, frame_mask=mask, length=np.asarray(length, np.int32),
                       class_id=np.asarray(int(row["class_id"]), np.int32), sample_id=np.asarray(row["sample_id"]),
                       left_observed=presence[:, 0], right_observed=presence[:, 1])
            meta = {
                "sample_id": row["sample_id"], "safe_id": sid, "role": row["role"],
                "split": row["split"], "class_id": int(row["class_id"]),
                "signer_group_id": row["signer_group_id"], "governance": gov,
                "governed_frames_decoded": len(frames), "stored_length": length,
                "smoke_truncated": bool(args.max_frames),
                "native_path": native.relative_to(ROOT).as_posix(), "native_sha256": sha256(native),
                "feature_path": feature.relative_to(ROOT).as_posix(), "feature_sha256": sha256(feature),
                **identity,
            }
            atomic_json(record, meta)
            failure_record = OUT / "failures" / f"{sid}.json"
            if failure_record.exists():
                failure_record.unlink()
            completed += 1
        except Exception as exc:
            failed += 1
            atomic_json(OUT / "failures" / f"{sid}.json", {"sample_id": row["sample_id"], "error": repr(exc)})
            print(f"FAILED {row['sample_id']}: {exc}", flush=True)
        elapsed = time.perf_counter() - started
        rate = completed / elapsed if elapsed else 0.0
        remaining = len(rows) - ordinal
        print(json.dumps({"completed_this_run": completed, "verified_skipped": skipped,
                          "failed": failed, "position": ordinal, "total": len(rows),
                          "remaining": remaining, "eta_seconds": remaining / rate if rate else None}), flush=True)
    return 0 if failed == 0 else 1


def validate(args: argparse.Namespace) -> int:
    rows = read_rows(); verify_identity(args.verify_checkpoint)
    records = {}
    errors = []
    for p in (OUT / "completed").glob("*.json") if (OUT / "completed").exists() else []:
        d = json.loads(p.read_text(encoding="utf-8")); records[d["sample_id"]] = d
    expected = rows if args.require_complete else [r for r in rows if r["sample_id"] in records]
    for row in expected:
        rec = records.get(row["sample_id"])
        if rec is None or not verified_cached(OUT / "completed" / f"{safe_id(row['sample_id'])}.json", allow_smoke=not args.require_complete):
            errors.append(f"missing/invalid: {row['sample_id']}"); continue
        if rec["role"] != row["role"] or rec["class_id"] != int(row["class_id"]):
            errors.append(f"identity mismatch: {row['sample_id']}")
        with np.load(ROOT / rec["feature_path"], allow_pickle=False) as z:
            if z["features"].shape != (SEQUENCE_LENGTH, FEATURE_WIDTH): errors.append(f"shape: {row['sample_id']}")
            if not np.isfinite(z["features"]).all(): errors.append(f"nonfinite: {row['sample_id']}")
    summary = {"expected": len(expected), "canonical": len(rows), "verified": len(expected)-len(errors),
               "errors": errors[:100], "passed": not errors and (not args.require_complete or len(records) == len(rows))}
    atomic_csv(OUT / "completed_manifest.csv", [records[r["sample_id"]] for r in expected if r["sample_id"] in records])
    atomic_json(OUT / "validation_summary.json", summary); print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


def assemble(_: argparse.Namespace) -> int:
    rows = read_rows()
    validation = argparse.Namespace(require_complete=True, verify_checkpoint=False)
    if validate(validation): return 2
    groups = {"train": [], "val": [], "test": [], "diagnostic_validation_stress": [],
              "diagnostic_reused_positive": [], "protected_replay": []}
    role_group = {"primary_train":"train", "supplement_train":"train", "primary_val":"val",
                  "primary_test":"test", "supplement_validation_stress":"diagnostic_validation_stress",
                  "reused_positive_diagnostic":"diagnostic_reused_positive", "protected_clean_replay":"protected_replay"}
    for row in rows: groups[role_group[row["role"]]].append(row)
    out = OUT / "dataset"
    for name, members in groups.items():
        X=[]; M=[]; Y=[]; IDs=[]; SG=[]
        for row in members:
            with np.load(OUT/"features"/f"{safe_id(row['sample_id'])}.npz", allow_pickle=False) as z:
                X.append(z["features"]); M.append(z["frame_mask"]); Y.append(int(row["class_id"])); IDs.append(row["sample_id"]); SG.append(row["signer_group_id"])
        atomic_npz(out/f"{name}.npz", X=np.stack(X).astype(np.float32), frame_mask=np.stack(M).astype(bool),
                   y=np.asarray(Y,np.int32), sample_ids=np.asarray(IDs), signer_group_ids=np.asarray(SG))
    (out/"vocab.json").parent.mkdir(parents=True, exist_ok=True)
    tmp=out/"vocab.json.tmp"; tmp.write_bytes(VOCAB.read_bytes()); os.replace(tmp,out/"vocab.json")
    atomic_json(out/"assembly_summary.json", {k:len(v) for k,v in groups.items()})
    return 0


def main() -> int:
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="command",required=True)
    x=sub.add_parser("extract"); x.add_argument("--smoke",action="store_true"); x.add_argument("--limit",type=int); x.add_argument("--max-frames",type=int); x.set_defaults(func=extract)
    v=sub.add_parser("validate"); v.add_argument("--require-complete",action="store_true"); v.add_argument("--verify-checkpoint",action="store_true"); v.set_defaults(func=validate)
    a=sub.add_parser("assemble"); a.set_defaults(func=assemble)
    args=p.parse_args(); return args.func(args)


if __name__ == "__main__": raise SystemExit(main())
