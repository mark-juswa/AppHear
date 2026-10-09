"""Offline foundation CLI: metadata prepare, reuse, validate, bounded acquire/extract.

No training command. Acquisition and Candidate01 work are opt-in separate subcommands.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.fingerspelling.adapter import CONFIG, column_names, sha256
from pipeline.fingerspelling.package_io import recover_partial, write_json_atomic
from pipeline.fingerspelling.sequence_manifest import ADMISSION, MANIFEST_SCHEMA, REPO, prepare
from pipeline.fingerspelling.sequence_package import (
    ASSETS,
    PREPROCESSING,
    reuse_fixed,
    validate,
    verify_source,
    write_features,
)
from pipeline.perception_vnext.recognition_schema import RAW_SCHEMA, RawSequence, save_raw_sequence

DEFAULT_OUTPUT = REPO / "datasets/fingerspelling/foundation_01"


def bounded_rows(output: Path, role: str, start: int, count: int) -> list[dict[str, Any]]:
    if start < 0 or not 1 <= count <= CONFIG["batch_sequences"]:
        raise ValueError("[fingerspelling/batch] Invalid start/count; max batch is 16")
    manifest = json.loads((output / "tranche_manifest.json").read_text())
    if manifest["schema_version"] != MANIFEST_SCHEMA or role not in {"TRAIN", "DEV"}:
        raise ValueError("[fingerspelling/batch] Role/schema refused")
    checked = validate(output, output / "tranche_manifest.json")
    if not checked["structural_pass"]:
        raise ValueError("[fingerspelling/batch] Manifest/package structural validation failed")
    result = [r for r in manifest["samples"] if r["split_role"] == role][start : start + count]
    if not result:
        raise ValueError("[fingerspelling/batch] Empty requested batch")
    return result


def acquire(output: Path, rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Only exact frozen manifest URLs; no recursive or full-corpus download."""
    folder = output / "videos"
    folder.mkdir(exist_ok=True)
    result = []
    for row in rows:
        old_source = ADMISSION / "videos" / row["filename"]
        if old_source.is_file():
            result.append(
                {
                    "sample_id": row["sample_id"],
                    "sha256": verify_source(old_source, row),
                    "disposition": "REUSE_EXISTING_IMMUTABLE_SOURCE",
                }
            )
            continue
        target = folder / row["filename"]
        if target.is_file():
            result.append({"sample_id": row["sample_id"], "sha256": verify_source(target, row)})
            continue
        temporary = folder / (row["filename"] + ".download")
        unpacked = folder / (row["filename"] + ".unpacked")
        recover_partial(
            output,
            [temporary, unpacked],
            "Interrupted acquisition; restart only this missing source",
        )
        # Kaggle may return MP4 bytes or a single-file ZIP. Both are bounded and verified.
        with (
            urllib.request.urlopen(row["direct_download_url"], timeout=60) as response,
            temporary.open("xb") as stream,
        ):
            received = 0
            while chunk := response.read(1024 * 1024):
                received += len(chunk)
                if received > row["file_size_bytes"] + 1024 * 1024:
                    raise ValueError("[fingerspelling/acquire] Unexpected oversized response")
                stream.write(chunk)
        if zipfile.is_zipfile(temporary):
            with zipfile.ZipFile(temporary) as archive:
                members = [m for m in archive.infolist() if not m.is_dir()]
                if (
                    len(members) != 1
                    or Path(members[0].filename).name != row["filename"]
                    or members[0].file_size != row["file_size_bytes"]
                ):
                    raise ValueError("[fingerspelling/acquire] Unexpected archive mapping")
                # Do not use extractall or archive paths.
                with archive.open(members[0]) as source, unpacked.open("xb") as stream:
                    while chunk := source.read(1024 * 1024):
                        stream.write(chunk)
            verify_source(unpacked, dict(row, filename=unpacked.name))
            unpacked.rename(target)
        else:
            verify_source(temporary, dict(row, filename=temporary.name))
            temporary.rename(target)
        source_sha = verify_source(target, row)
        if temporary.exists():
            temporary.unlink()  # Only our verified single download staging file.
        result.append({"sample_id": row["sample_id"], "sha256": source_sha})
    return result


def extract(
    output: Path, rows: list[dict[str, Any]], runtime_cache: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Use frozen runtime/decoder directly, independent of word ingest/gloss schemas."""
    import cv2

    from pipeline.perception_vnext.offline_candidate01 import (
        DEFAULT_ONNX,
        DEFAULT_REFINER,
        Candidate01Offline,
        iter_video_frames,
    )

    for name, expected in PREPROCESSING.items():
        if sha256(REPO / "pipeline/perception_vnext" / name) != expected:
            raise ValueError("[fingerspelling/extraction] Frozen code changed")
    for path in [DEFAULT_ONNX, DEFAULT_REFINER]:
        if sha256(path) != ASSETS[path.name]:
            raise ValueError("[fingerspelling/extraction] Frozen model changed")
    runtime = runtime_cache.get("runtime") if runtime_cache is not None else None
    result = []
    for row in rows:
        old_feature = output / "features" / (row["sample_id"] + ".receipt.json")
        if old_feature.is_file():
            # bounded_rows validates these receipts and deterministic arrays before dispatch.
            result.append(json.loads(old_feature.read_text()))
            continue
        source = output / "videos" / row["filename"]
        if not source.is_file():
            source = ADMISSION / "videos" / row["filename"]
        source_sha = verify_source(source, row)
        folder = output / "raw"
        folder.mkdir(exist_ok=True)
        raw_path = folder / (row["sample_id"] + ".raw-v1.npz")
        receipt_path = folder / (row["sample_id"] + ".receipt.json")
        if raw_path.exists() or receipt_path.exists():
            if not raw_path.is_file() or not receipt_path.is_file():
                recover_partial(
                    output, [raw_path, receipt_path], "Interrupted uncommitted raw/receipt pair"
                )
        if not raw_path.is_file():
            if runtime is None:
                runtime = Candidate01Offline()
                if runtime_cache is not None:
                    runtime_cache["runtime"] = runtime
            probe = cv2.VideoCapture(str(source))
            try:
                if not probe.isOpened():
                    raise ValueError("[fingerspelling/extraction] Source probe failed")
                decoder_backend = probe.getBackendName()
                source_probe = {
                    "container_frame_count": int(probe.get(cv2.CAP_PROP_FRAME_COUNT)),
                    "encoded_width": int(probe.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    "encoded_height": int(probe.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    "container_fps": float(probe.get(cv2.CAP_PROP_FPS)),
                }
            finally:
                probe.release()
            started = time.perf_counter()
            iterator, video_meta = iter_video_frames(source, None)
            frames = [(i, ms, ts, runtime.process_rgb(rgb)) for i, ms, ts, rgb in iterator]
            if not frames:
                raise ValueError("[fingerspelling/extraction] No decoded frames")
            if (
                source_probe["container_frame_count"] > 0
                and len(frames) != source_probe["container_frame_count"]
            ):
                raise ValueError(
                    "[fingerspelling/extraction] Decoder stopped before expected frame count"
                )
            raw = RawSequence(
                metadata={
                    "schema": RAW_SCHEMA,
                    "candidate_id": "dwpose_t_256x192_plus_mp_hand_224",
                    "sample_id": row["sample_id"],
                    "source_video_sha256": source_sha,
                    "split": row["split_role"],
                    "signer_id": "fsboard:" + row["official_signer_id"],
                    "intended_transcript": row["transcript"],
                    "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB",
                    "image_semantics_declaration_caveat": (
                        "Research policy as-is; historical reflection not fully attributed"
                    ),
                    "reflection_policy": CONFIG["reflection_policy"],
                    "reflection_provenance": CONFIG["reflection_provenance"],
                    "timestamp_sources": sorted({f[2] for f in frames}),
                    "duration_scope": "whole_source_video",
                    "current_frame_only": True,
                    "carry_forward": False,
                    "synthetic_depth": False,
                    **video_meta,
                },
                frame_index=np.asarray([f[0] for f in frames], np.int32),
                timestamp_ms=np.asarray([f[1] for f in frames], np.float64),
                source_size=np.stack([f[3]["source_size"] for f in frames]),
                hand_xy=np.stack([[h["xy"] for h in f[3]["hands"]] for f in frames]),
                hand_proposal_support=np.stack(
                    [[h["proposal_support"] for h in f[3]["hands"]] for f in frames]
                ),
                hand_joint_valid=np.stack([[h["valid"] for h in f[3]["hands"]] for f in frames]),
                hand_presence=np.asarray(
                    [[h["presence"] for h in f[3]["hands"]] for f in frames], np.float32
                ),
                hand_observed=np.asarray(
                    [[h["observed"] for h in f[3]["hands"]] for f in frames], bool
                ),
                hand_proposal_present=np.asarray(
                    [[h["proposal_present"] for h in f[3]["hands"]] for f in frames], bool
                ),
                hand_roi_center_side=np.stack([[h["roi"] for h in f[3]["hands"]] for f in frames]),
                hand_handedness_diagnostic=np.asarray(
                    [[h["handedness"] for h in f[3]["hands"]] for f in frames], np.float32
                ),
                body_xy=np.stack([f[3]["body_xy"] for f in frames]),
                body_support=np.stack([f[3]["body_support"] for f in frames]),
                body_valid=np.stack([f[3]["body_valid"] for f in frames]),
                body_available=np.asarray([f[3]["body_available"] for f in frames], bool),
            )
            staged_raw = raw_path.with_name(raw_path.stem + ".pending.npz")
            recover_partial(output, [staged_raw], "Interrupted raw array staging")
            save_raw_sequence(staged_raw, raw)
            staged_raw.rename(raw_path)
            receipt = {
                "schema_version": "apphear.fingerspelling.frozen_extraction_receipt.v1",
                "sample_id": row["sample_id"],
                "source_sha256": source_sha,
                "raw_sha256": sha256(raw_path),
                "raw_schema": RAW_SCHEMA,
                "official_signer_id": row["official_signer_id"],
                "split_role": row["split_role"],
                "intended_transcript": row["transcript"],
                "candidate01_assets": ASSETS,
                "preprocessing_source_sha256": PREPROCESSING,
                "extraction_wrapper_sha256": sha256(Path(__file__)),
                "decoder_version": cv2.__version__,
                "decoder_backend": decoder_backend,
                "source_probe": source_probe,
                "frame_count": len(frames),
                "whole_source_video": True,
                "extraction_wall_seconds": time.perf_counter() - started,
                "timestamp_sources": raw.metadata["timestamp_sources"],
                "timestamp_range_ms": [float(raw.timestamp_ms[0]), float(raw.timestamp_ms[-1])],
                "frame_indices": {
                    "first": int(raw.frame_index[0]),
                    "last": int(raw.frame_index[-1]),
                    "consecutive": bool(np.all(np.diff(raw.frame_index) == 1)),
                },
                "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB",
                **video_meta,
                "reflection_policy": CONFIG["reflection_policy"],
                "reflection_provenance": CONFIG["reflection_provenance"],
            }
            write_json_atomic(receipt_path, receipt)
        result.append(
            write_features(
                output, output / "tranche_manifest.json", row, source, raw_path, receipt_path
            )
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "prepare",
            "reuse-fixed",
            "validate",
            "plan-batch",
            "acquire-batch",
            "extract-batch",
        ],
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--role", choices=["TRAIN", "DEV"], default="TRAIN")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=CONFIG["batch_sequences"])
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(REPO)
    manifest = output / "tranche_manifest.json"
    if args.command == "prepare":
        if manifest.exists():
            raise ValueError(
                "[fingerspelling/prepare] Frozen manifest exists; use a new versioned directory"
            )
        m = prepare(output)
        (output / "feature_columns.json").write_text(json.dumps(column_names(), indent=2) + "\n")
        print(
            json.dumps(
                {
                    r: {k: v for k, v in s.items() if k not in {"lengths", "signer_counts"}}
                    for r, s in m["summary"].items()
                },
                indent=2,
            )
        )
    elif args.command == "reuse-fixed":
        print(json.dumps({"features_written": len(reuse_fixed(output, manifest))}))
    elif args.command == "validate":
        result = validate(output, manifest)
        print(json.dumps({k: v for k, v in result.items() if k != "statistics"}, indent=2))
        if not result["structural_pass"]:
            raise SystemExit(1)
    else:
        rows = bounded_rows(output, args.role, args.start, args.count)
        if args.command == "plan-batch":
            print(
                json.dumps(
                    {
                        "count": len(rows),
                        "bytes": sum(r["file_size_bytes"] for r in rows),
                        "files": [
                            {
                                k: r[k]
                                for k in [
                                    "sample_id",
                                    "filename",
                                    "split_role",
                                    "direct_download_url",
                                ]
                            }
                            for r in rows
                        ],
                    },
                    indent=2,
                )
            )
        elif args.command == "acquire-batch":
            print(json.dumps(acquire(output, rows), indent=2))
        elif args.command == "extract-batch":
            print(json.dumps({"features_written": len(extract(output, rows))}))


if __name__ == "__main__":
    main()
