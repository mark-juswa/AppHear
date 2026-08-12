"""C0-B0 training-only hand-detector readiness package.

This module inventories candidate source videos, excludes frozen evaluation
lineage, prepares a small hand-box review package, and checks the deprecated
MediaPipe Model Maker toolchain. It never changes production recognizer assets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import random
import shutil
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from importlib import import_module, util
from pathlib import Path, PureWindowsPath
from typing import Any

import cv2

from pipeline.tracking.e2e_gold import INDEX_FIELDS, REVIEW_FIELDS

EXPERIMENT = "c0b_apphear_hand_roi_readiness_v1"
DEFAULT_ASL_ROOT = Path("F:/ASL DATASET/ASL CITIZEN/ASL_Citizen")
DEFAULT_LOCAL_ROOT = Path("E:/local")
DEFAULT_P0 = Path(
    "F:/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/"
    "e2e_all_hand_gold_v1/engineering_01"
)
DEFAULT_N0 = Path("artifacts/recognition_upgrade/e2e_c0/n0_capture_06")
DEFAULT_P1 = Path("artifacts/recognition_upgrade/e2e_c0/p1_capture_03")
DEFAULT_E6_ASSIGNMENT = Path(
    "artifacts/recognition_upgrade/product_core_data_readiness/"
    "e6_five_sign_assignment_01/assignment_manifest.csv"
)
DEFAULT_OUTPUT_ROOT = Path("artifacts/recognition_upgrade/e2e_c0")
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}

INVENTORY_FIELDS = (
    "candidate_id",
    "source_dataset",
    "source_split",
    "participant_id",
    "gloss",
    "raw_video_path",
    "sidecar_path",
    "previous_experiment_usage",
    "eligibility",
    "exclusion_reason",
)

ANNOTATION_FIELDS = (
    "sample_id",
    "candidate_id",
    "source_dataset",
    "source_split",
    "participant_id",
    "gloss",
    "raw_video_path",
    "raw_video_sha256",
    "frame_index",
    "timestamp_ms",
    "frame_fraction",
    "center_image_path",
    "context_panel_path",
    "protected_overlap",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in writer.fieldnames})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _path_key(path: Path | str) -> str:
    return str(Path(path).resolve()).replace("/", "\\").casefold()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "accepted"}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _resolve_annotation_asset(path_text: str, annotation_run: Path, subdir: str) -> Path:
    """Resolve a reviewed asset after moving a Windows-authored run into Linux."""
    recorded = Path(path_text)
    if recorded.is_file():
        return recorded
    portable = annotation_run / subdir / PureWindowsPath(path_text).name
    if portable.is_file():
        return portable
    raise FileNotFoundError(
        f"annotation asset not found at recorded or portable path: {recorded}; {portable}"
    )


def _protected_registry(
    asl_root: Path,
    p0_run: Path,
    n0_run: Path,
    p1_run: Path,
    e6_assignment: Path,
) -> tuple[set[str], set[str], set[str], dict[str, set[str]], list[dict[str, str]]]:
    protected_paths: set[str] = set()
    protected_hashes: set[str] = set()
    protected_signers: set[str] = set()
    usage: dict[str, set[str]] = defaultdict(set)
    registry: list[dict[str, str]] = []

    def add(
        path: Path,
        source: str,
        sha256: str = "",
        signer: str = "",
        block_signer: bool = False,
    ) -> None:
        key = _path_key(path)
        protected_paths.add(key)
        usage[key].add(source)
        normalized_hash = sha256.strip().upper()
        if normalized_hash:
            protected_hashes.add(normalized_hash)
        if block_signer and signer:
            protected_signers.add(signer)
        registry.append(
            {
                "source": source,
                "raw_video_path": str(path.resolve()),
                "raw_video_sha256": normalized_hash,
                "participant_id": signer,
                "block_signer": str(block_signer).lower(),
            }
        )

    p0_index = p0_run / "internal_index.csv"
    if not p0_index.is_file():
        raise FileNotFoundError(p0_index)
    for row in _read_csv(p0_index):
        add(
            asl_root / "videos" / row["video_file"],
            "P0_FROZEN_POSITIVE_GOLD",
            signer=row.get("participant_id", ""),
        )

    for run, label in ((n0_run, "N0_FROZEN_NO_HAND"), (p1_run, "P1_FROZEN_VISIBLE_HAND")):
        manifest = run / "capture_manifest.csv"
        if not manifest.is_file():
            raise FileNotFoundError(manifest)
        for row in _read_csv(manifest):
            add(
                Path(row["video_path"]),
                label,
                row.get("sha256", ""),
                row.get("participant_id", ""),
            )

    if e6_assignment.is_file():
        for row in _read_csv(e6_assignment):
            path_text = row.get("raw_video_path", "").strip()
            if not path_text:
                continue
            role = row.get("role", "")
            signer_group = row.get("signer_group_id", "")
            signer = signer_group.split(":", 1)[-1] if ":" in signer_group else signer_group
            held_out = role.startswith("test_") or role.startswith("validation_")
            add(
                Path(path_text),
                f"E6_ASSIGNMENT:{role}",
                row.get("raw_video_sha256", ""),
                signer,
                block_signer=held_out,
            )
    return protected_paths, protected_hashes, protected_signers, usage, registry


def _asl_candidates(asl_root: Path) -> list[dict[str, Any]]:
    split_path = asl_root / "splits" / "train.csv"
    if not split_path.is_file():
        raise FileNotFoundError(split_path)
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(_read_csv(split_path), start=1):
        video = asl_root / "videos" / item["Video file"]
        rows.append(
            {
                "candidate_id": f"asl_train_{index:06d}",
                "source_dataset": "ASL_CITIZEN",
                "source_split": "train",
                "participant_id": item["Participant ID"],
                "gloss": item["Gloss"].upper(),
                "raw_video_path": str(video.resolve()),
                "sidecar_path": str(split_path.resolve()),
                "previous_experiment_usage": "ASL Citizen train inventory",
                "eligibility": "candidate",
                "exclusion_reason": "",
            }
        )
    return rows


def _local_candidates(local_root: Path) -> list[dict[str, Any]]:
    if not local_root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for index, sidecar in enumerate(sorted(local_root.rglob("*.json")), start=1):
        try:
            metadata = _load_json(sidecar)
        except (json.JSONDecodeError, OSError, ValueError) as error:
            rows.append(
                {
                    "candidate_id": f"local_{index:06d}",
                    "source_dataset": "LOCAL_SUPPLEMENTARY",
                    "source_split": "unassigned",
                    "participant_id": "",
                    "gloss": "",
                    "raw_video_path": "",
                    "sidecar_path": str(sidecar.resolve()),
                    "previous_experiment_usage": "local sidecar inventory",
                    "eligibility": "excluded",
                    "exclusion_reason": f"invalid sidecar: {error}",
                }
            )
            continue
        video_name = str(metadata.get("video_file", "")).strip()
        video = sidecar.parent / video_name if video_name else sidecar.with_suffix(".mp4")
        accepted = metadata.get("accepted", True)
        reasons = []
        if not str(metadata.get("signer_id", "")).strip():
            reasons.append("missing signer_id")
        if not video.is_file():
            reasons.append("paired video missing")
        if not _as_bool(accepted):
            reasons.append("sidecar accepted=false")
        rows.append(
            {
                "candidate_id": f"local_{index:06d}",
                "source_dataset": "LOCAL_SUPPLEMENTARY",
                "source_split": "unassigned",
                "participant_id": str(metadata.get("signer_id", "")),
                "gloss": str(metadata.get("gloss") or metadata.get("word") or "").upper(),
                "raw_video_path": str(video.resolve()),
                "sidecar_path": str(sidecar.resolve()),
                "previous_experiment_usage": "local sidecar inventory",
                "eligibility": "excluded" if reasons else "candidate",
                "exclusion_reason": " | ".join(reasons),
            }
        )
    return rows


def inventory(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    protected_paths, protected_hashes, protected_signers, usage, registry = _protected_registry(
        args.asl_root,
        args.p0_run,
        args.n0_run,
        args.p1_run,
        args.e6_assignment,
    )
    rows = _asl_candidates(args.asl_root) + _local_candidates(args.local_root)
    for row in rows:
        path_text = row["raw_video_path"]
        key = _path_key(path_text) if path_text else ""
        prior = sorted(usage.get(key, set()))
        if prior:
            row["previous_experiment_usage"] = " | ".join(prior)
        reasons = [part for part in row["exclusion_reason"].split(" | ") if part]
        if key in protected_paths:
            reasons.append("protected evaluation source path")
        if (
            row["source_dataset"] == "LOCAL_SUPPLEMENTARY"
            and row["participant_id"] in protected_signers
        ):
            reasons.append("held-out E6 signer")
        if path_text and not Path(path_text).is_file():
            reasons.append("raw video missing")
        if reasons:
            row["eligibility"] = "excluded"
            row["exclusion_reason"] = " | ".join(sorted(set(reasons)))

    _write_csv(output / "source_inventory.csv", rows, INVENTORY_FIELDS)
    _write_csv(
        output / "protected_source_registry.csv",
        registry,
        ("source", "raw_video_path", "raw_video_sha256", "participant_id", "block_signer"),
    )
    summary = {
        "experiment": EXPERIMENT,
        "stage": "inventory",
        "rows": len(rows),
        "candidate_rows": sum(row["eligibility"] == "candidate" for row in rows),
        "excluded_rows": sum(row["eligibility"] == "excluded" for row in rows),
        "by_source": dict(sorted(Counter(row["source_dataset"] for row in rows).items())),
        "candidate_by_source": dict(
            sorted(
                Counter(
                    row["source_dataset"]
                    for row in rows
                    if row["eligibility"] == "candidate"
                ).items()
            )
        ),
        "candidate_signers_by_source": {
            source: len(
                {
                    row["participant_id"]
                    for row in rows
                    if row["source_dataset"] == source and row["eligibility"] == "candidate"
                }
            )
            for source in sorted({row["source_dataset"] for row in rows})
        },
        "protected_paths": len(protected_paths),
        "protected_hashes": len(protected_hashes),
        "protected_signers": sorted(protected_signers),
        "passed": any(row["eligibility"] == "candidate" for row in rows),
        "training_authorized": False,
    }
    _write_json(output / "inventory_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return summary


def _balanced_select(rows: list[dict[str, str]], count: int, seed: int) -> list[dict[str, str]]:
    candidates = [row for row in rows if row["eligibility"] == "candidate"]
    if not candidates:
        raise ValueError("inventory has no eligible candidates")
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        groups[(row["source_dataset"], row["participant_id"])].append(row)
    rng = random.Random(seed)
    for values in groups.values():
        rng.shuffle(values)

    source_signers: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for key in groups:
        source_signers[key[0]].append(key)
    source_queues: dict[str, list[dict[str, str]]] = defaultdict(list)
    for source, keys in source_signers.items():
        rng.shuffle(keys)
        while True:
            progressed = False
            for key in keys:
                if groups[key]:
                    source_queues[source].append(groups[key].pop())
                    progressed = True
            if not progressed:
                break
        source_queues[source].reverse()

    sources = sorted(source_queues)
    rng.shuffle(sources)
    selected: list[dict[str, str]] = []
    while len(selected) < count:
        progressed = False
        for source in sources:
            if source_queues[source]:
                selected.append(source_queues[source].pop())
                progressed = True
                if len(selected) == count:
                    break
        if not progressed:
            break
    if len(selected) < count:
        raise ValueError(
            f"only {len(selected)} eligible unique videos available; requested {count}"
        )
    return selected


def _frame(cap: cv2.VideoCapture, index: int, path: Path) -> Any:
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, image = cap.read()
    if not ok or image is None:
        raise OSError(f"cannot decode frame {index}: {path}")
    return image


def _fit(image: Any, width: int = 240, height: int = 180) -> Any:
    scale = min(width / image.shape[1], height / image.shape[0])
    resized = cv2.resize(
        image,
        (max(1, round(image.shape[1] * scale)), max(1, round(image.shape[0] * scale))),
        interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_NEAREST,
    )
    top = (height - resized.shape[0]) // 2
    left = (width - resized.shape[1]) // 2
    return cv2.copyMakeBorder(
        resized,
        top,
        height - resized.shape[0] - top,
        left,
        width - resized.shape[1] - left,
        cv2.BORDER_CONSTANT,
        value=(24, 24, 24),
    )


def _proposal_boxes(hands: list[dict[str, Any]], padding: float = 0.12) -> list[dict[str, Any]]:
    proposals = []
    for hand in hands[:2]:
        x1, y1, x2, y2 = (float(value) for value in hand["box"])
        width = max(0.0, x2 - x1)
        height = max(0.0, y2 - y1)
        proposals.append(
            {
                "x_min": round(max(0.0, x1 - width * padding), 6),
                "y_min": round(max(0.0, y1 - height * padding), 6),
                "x_max": round(min(1.0, x2 + width * padding), 6),
                "y_max": round(min(1.0, y2 + height * padding), 6),
                "anatomical_side": "unknown",
            }
        )
    return proposals


def _extract_review_sample(
    row: dict[str, str],
    sample_id: str,
    fraction: float,
    output: Path,
    proposal_runner: Any | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    video = Path(row["raw_video_path"])
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise OSError(f"cannot open video: {video}")
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    if frame_count <= 0 or fps <= 0:
        cap.release()
        raise ValueError(f"invalid video metadata: {video}")
    center = min(frame_count - 1, max(0, round((frame_count - 1) * fraction)))
    indices = [min(frame_count - 1, max(0, center + delta)) for delta in (-8, -4, 0, 4, 8)]
    frames = [_frame(cap, index, video) for index in indices]
    cap.release()
    center_path = output / "center_images" / f"{sample_id}.png"
    context_path = output / "context_panels" / f"{sample_id}.jpg"
    center_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(center_path), frames[2]):
        raise OSError(f"cannot write {center_path}")
    panel = cv2.hconcat([_fit(image) for image in frames])
    if not cv2.imwrite(str(context_path), panel):
        raise OSError(f"cannot write {context_path}")
    height, width = frames[2].shape[:2]
    timestamp_ms = round(center * 1000.0 / fps)
    detected_hands: list[dict[str, Any]] = []
    pose_wrists: dict[str, Any] = {}
    proposed_boxes: list[dict[str, Any]] = []
    if proposal_runner is not None:
        detected_hands, pose_wrists = proposal_runner.detect(frames[2])
        proposed_boxes = _proposal_boxes(detected_hands)
    index_row = {
        "sample_id": sample_id,
        "clip_id": video.stem,
        "video_file": video.name,
        "participant_id": row["participant_id"],
        "split": "detector_training_candidate",
        "gloss": row["gloss"],
        "frame_index": center,
        "timestamp_ms": timestamp_ms,
        "sampling_cadence": f"fraction_{fraction:.2f}",
        "sampling_target_hand": "",
        "sampling_target_detected": "",
        "sampling_raw_detected_hands": "",
        "image_width": width,
        "image_height": height,
        "center_image_path": str(center_path.resolve()),
        "context_panel_path": str(context_path.resolve()),
        "diagnostic_panel_path": "",
        "detected_hands_json": json.dumps(detected_hands, separators=(",", ":")),
        "pose_wrists_json": json.dumps(pose_wrists, separators=(",", ":")),
    }
    review_row = {
        "sample_id": sample_id,
        "review_status": "",
        "source_mirrored": "unknown",
        "mirror_evidence": "",
        "visible_hand_count": str(len(proposed_boxes)) if proposed_boxes else "",
        "gold_hands_json": json.dumps(proposed_boxes, separators=(",", ":")),
        "motion_blur": "no",
        "occlusion": "no",
        "near_face": "no",
        "edge_clipped": "no",
        "partial_visibility": "no",
        "notes": "",
    }
    annotation_row = {
        "sample_id": sample_id,
        "candidate_id": row["candidate_id"],
        "source_dataset": row["source_dataset"],
        "source_split": row["source_split"],
        "participant_id": row["participant_id"],
        "gloss": row["gloss"],
        "raw_video_path": str(video.resolve()),
        "raw_video_sha256": _sha256(video),
        "frame_index": center,
        "timestamp_ms": timestamp_ms,
        "frame_fraction": fraction,
        "center_image_path": str(center_path.resolve()),
        "context_panel_path": str(context_path.resolve()),
        "protected_overlap": "false",
    }
    return index_row, review_row, annotation_row


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    inventory_rows = _read_csv(args.inventory / "source_inventory.csv")
    protected_rows = _read_csv(args.inventory / "protected_source_registry.csv")
    protected_paths = {_path_key(row["raw_video_path"]) for row in protected_rows}
    protected_hashes = {
        row["raw_video_sha256"].strip().upper()
        for row in protected_rows
        if row["raw_video_sha256"].strip()
    }
    candidate_count = sum(row["eligibility"] == "candidate" for row in inventory_rows)
    pool = _balanced_select(inventory_rows, min(args.count * 2, candidate_count), args.seed)
    rng = random.Random(args.seed)
    fractions = (0.25, 0.50, 0.75)
    index_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    annotation_rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    proposal_runner = None
    try:
        if getattr(args, "preannotate_mediapipe", False):
            from pipeline.tracking.e2e_pilot import HandPoseRunner

            proposal_runner = HandPoseRunner(args.hand_task, args.pose_task)
        for candidate in pool:
            if len(annotation_rows) == args.count:
                break
            video = Path(candidate["raw_video_path"])
            digest = _sha256(video)
            reasons = []
            if _path_key(video) in protected_paths:
                reasons.append("protected path")
            if digest in protected_hashes:
                reasons.append("protected hash")
            if reasons:
                rejected.append(
                    {
                        "candidate_id": candidate["candidate_id"],
                        "raw_video_path": str(video.resolve()),
                        "raw_video_sha256": digest,
                        "reason": " | ".join(reasons),
                    }
                )
                continue
            sample_id = f"c0b_{len(annotation_rows) + 1:04d}"
            index_row, review_row, annotation_row = _extract_review_sample(
                candidate,
                sample_id,
                fractions[rng.randrange(len(fractions))],
                output,
                proposal_runner,
            )
            index_rows.append(index_row)
            review_rows.append(review_row)
            annotation_rows.append(annotation_row)
            print(f"[tracking/c0-b0] prepare {len(annotation_rows)}/{args.count} {sample_id}")
    finally:
        if proposal_runner is not None:
            proposal_runner.close()
    if len(annotation_rows) != args.count:
        raise ValueError(
            f"only {len(annotation_rows)} non-protected samples prepared; requested {args.count}"
        )
    _write_csv(output / "internal_index.csv", index_rows, INDEX_FIELDS)
    _write_csv(output / "gold_review.csv", review_rows, REVIEW_FIELDS)
    _write_csv(output / "annotation_manifest.csv", annotation_rows, ANNOTATION_FIELDS)
    _write_csv(
        output / "excluded_overlap.csv",
        rejected,
        ("candidate_id", "raw_video_path", "raw_video_sha256", "reason"),
    )
    summary = {
        "experiment": EXPERIMENT,
        "stage": "annotation_smoke_package",
        "rows": len(annotation_rows),
        "source_counts": dict(
            sorted(Counter(row["source_dataset"] for row in annotation_rows).items())
        ),
        "signers": sorted({row["participant_id"] for row in annotation_rows}),
        "protected_overlap_exclusions": len(rejected),
        "source_hashes_recorded": True,
        "proposal_source": (
            "mediapipe_hand_landmarker_unreviewed"
            if getattr(args, "preannotate_mediapipe", False)
            else "none"
        ),
        "reviewed": False,
        "training_authorized": False,
        "review_command": (
            f'python -m pipeline.tracking.e2e_gold_review --run-dir "{output.resolve()}"'
        ),
        "check_command": (
            f'python -m pipeline.tracking.e2e_c0b check --run-dir "{output.resolve()}" '
            "--require-reviewed"
        ),
    }
    _write_json(output / "prepare_summary.json", summary)
    (output / "README_RUN.md").write_text(
        "# C0-B0 Hand-Box Review\n\n"
        "This package is training-data readiness only. It does not authorize detector training.\n\n"
        "Review every center frame with the existing all-hand-box GUI. Any initial MediaPipe "
        "boxes are untrusted suggestions: accept, resize, delete, or add boxes so every visible "
        "hand has one tight full-hand box. Record blur, occlusion, near-face, edge, and partial "
        "flags.\n\n"
        f"```powershell\n{summary['review_command']}\n{summary['check_command']}\n```\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    run = args.run_dir
    required = [
        "prepare_summary.json",
        "internal_index.csv",
        "gold_review.csv",
        "annotation_manifest.csv",
        "README_RUN.md",
    ]
    errors = [f"missing {name}" for name in required if not (run / name).is_file()]
    rows = _read_csv(run / "gold_review.csv") if not errors else []
    manifest = _read_csv(run / "annotation_manifest.csv") if not errors else []
    if rows and len(rows) != len(manifest):
        errors.append("review and annotation manifest row counts differ")
    completed = sum(row.get("review_status") in {"accepted", "quarantine"} for row in rows)
    accepted = [row for row in rows if row.get("review_status") == "accepted"]
    boxes = 0
    for row in accepted:
        try:
            value = json.loads(row.get("gold_hands_json", "[]"))
            boxes += len(value) if isinstance(value, list) else 0
        except json.JSONDecodeError:
            errors.append(f"{row.get('sample_id')}: invalid gold_hands_json")
    if any(row.get("protected_overlap", "").casefold() == "true" for row in manifest):
        errors.append("annotation manifest contains protected overlap")
    if args.require_reviewed and completed != len(rows):
        errors.append(f"review incomplete: {completed}/{len(rows)}")
    summary = {
        "run_dir": str(run.resolve()),
        "rows": len(rows),
        "completed": completed,
        "accepted": len(accepted),
        "hand_boxes": boxes,
        "condition_counts": {
            field: sum(row.get(field) == "yes" for row in accepted)
            for field in (
                "motion_blur",
                "occlusion",
                "near_face",
                "edge_clipped",
                "partial_visibility",
            )
        },
        "passed": not errors,
        "errors": errors,
        "training_authorized": False,
    }
    _write_json(run / "readiness_check.json", summary)
    print(json.dumps(summary, indent=2))
    return summary


def toolchain_preflight(args: argparse.Namespace) -> dict[str, Any]:
    modules = {}
    for name in ("tensorflow", "mediapipe", "mediapipe_model_maker"):
        spec = util.find_spec(name)
        version = ""
        error = ""
        if spec is not None:
            try:
                module = import_module(name)
                version = str(getattr(module, "__version__", "unknown"))
            except Exception as exc:  # pragma: no cover - dependency-specific
                error = f"{type(exc).__name__}: {exc}"
        modules[name] = {"available": spec is not None, "version": version, "import_error": error}
    python_supported = sys.version_info[:2] in {(3, 8), (3, 9), (3, 10)}
    passed = python_supported and all(
        item["available"] and not item["import_error"] for item in modules.values()
    )
    summary = {
        "experiment": EXPERIMENT,
        "stage": "toolchain_preflight",
        "python": sys.version,
        "platform": platform.platform(),
        "python_supported_by_published_model_maker_metadata": python_supported,
        "modules": modules,
        "passed": passed,
        "training_authorized": False,
        "next": (
            "prepare reviewed COCO smoke and run one epoch"
            if passed
            else "use an isolated Python 3.9/3.10 environment; do not modify the main .venv"
        ),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    _write_json(args.output / "toolchain_preflight.json", summary)
    print(json.dumps(summary, indent=2))
    return summary


def _coco_split(annotation_run: Path, output: Path) -> tuple[Path, Path, Path]:
    reviews = {row["sample_id"]: row for row in _read_csv(annotation_run / "gold_review.csv")}
    manifest = _read_csv(annotation_run / "annotation_manifest.csv")
    usable = [
        row
        for row in manifest
        if reviews.get(row["sample_id"], {}).get("review_status") == "accepted"
        and json.loads(reviews[row["sample_id"]].get("gold_hands_json", "[]"))
    ]
    if len(usable) < 6:
        raise ValueError("toolchain smoke requires at least six accepted frames with hand boxes")
    train = usable[:-2]
    val = usable[-2:]

    def build(name: str, rows: list[dict[str, str]]) -> Path:
        root = output / "coco" / name
        images_dir = root / "images"
        images_dir.mkdir(parents=True, exist_ok=False)
        images = []
        annotations = []
        annotation_id = 1
        for image_id, row in enumerate(rows, start=1):
            source = _resolve_annotation_asset(
                row["center_image_path"], annotation_run, "center_images"
            )
            target = images_dir / source.name
            shutil.copy2(source, target)
            image = cv2.imread(str(source))
            if image is None:
                raise OSError(f"cannot read {source}")
            height, width = image.shape[:2]
            images.append(
                {"id": image_id, "file_name": target.name, "width": width, "height": height}
            )
            boxes = json.loads(reviews[row["sample_id"]]["gold_hands_json"])
            for box in boxes:
                x = float(box["x_min"]) * width
                y = float(box["y_min"]) * height
                w = (float(box["x_max"]) - float(box["x_min"])) * width
                h = (float(box["y_max"]) - float(box["y_min"])) * height
                annotations.append(
                    {
                        "id": annotation_id,
                        "image_id": image_id,
                        "category_id": 1,
                        "bbox": [x, y, w, h],
                        "area": w * h,
                        "iscrowd": 0,
                    }
                )
                annotation_id += 1
        payload = {
            "categories": [{"id": 1, "name": "hand"}],
            "images": images,
            "annotations": annotations,
        }
        _write_json(root / "labels.json", payload)
        return root

    return (
        build("train", train),
        build("validation", val),
        _resolve_annotation_asset(
            usable[0]["center_image_path"], annotation_run, "center_images"
        ),
    )


def toolchain_smoke(args: argparse.Namespace) -> dict[str, Any]:
    preflight_args = argparse.Namespace(output=args.output)
    preflight = toolchain_preflight(preflight_args)
    if not preflight["passed"]:
        raise RuntimeError("toolchain preflight failed; see toolchain_preflight.json")
    from mediapipe.tasks.python import vision
    from mediapipe_model_maker import object_detector

    train_root, val_root, sample_image = _coco_split(args.annotation_run, args.output)
    train_data = object_detector.Dataset.from_coco_folder(
        str(train_root), cache_dir=str(args.output / "cache" / "train")
    )
    val_data = object_detector.Dataset.from_coco_folder(
        str(val_root), cache_dir=str(args.output / "cache" / "validation")
    )
    export_dir = args.output / "export"
    options = object_detector.ObjectDetectorOptions(
        supported_model=object_detector.SupportedModels.MOBILENET_V2,
        hparams=object_detector.HParams(
            export_dir=str(export_dir), epochs=1, batch_size=2
        ),
    )
    model = object_detector.ObjectDetector.create(
        train_data=train_data,
        validation_data=val_data,
        options=options,
    )
    model.export_model("model.tflite")
    model_path = export_dir / "model.tflite"
    if not model_path.is_file():
        raise FileNotFoundError(model_path)
    image = cv2.imread(str(sample_image))
    if image is None:
        raise OSError(f"cannot read {sample_image}")
    import mediapipe as mp

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    with vision.ObjectDetector.create_from_model_path(str(model_path)) as detector:
        result = detector.detect(mp_image)
    summary = {
        "experiment": EXPERIMENT,
        "stage": "one_epoch_export_reload_smoke",
        "model_path": str(model_path.resolve()),
        "model_sha256": _sha256(model_path),
        "model_bytes": model_path.stat().st_size,
        "reload_inference_detections": len(result.detections),
        "passed": True,
        "training_authorized": False,
        "warning": "Wiring smoke only; no detector accuracy claim.",
    }
    _write_json(args.output / "toolchain_smoke_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="C0-B0 hand-detector readiness")
    commands = parser.add_subparsers(dest="command", required=True)

    inventory_parser = commands.add_parser("inventory")
    inventory_parser.add_argument("--asl-root", type=Path, default=DEFAULT_ASL_ROOT)
    inventory_parser.add_argument("--local-root", type=Path, default=DEFAULT_LOCAL_ROOT)
    inventory_parser.add_argument("--p0-run", type=Path, default=DEFAULT_P0)
    inventory_parser.add_argument("--n0-run", type=Path, default=DEFAULT_N0)
    inventory_parser.add_argument("--p1-run", type=Path, default=DEFAULT_P1)
    inventory_parser.add_argument("--e6-assignment", type=Path, default=DEFAULT_E6_ASSIGNMENT)
    inventory_parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT_ROOT / "c0b_inventory_01"
    )
    inventory_parser.set_defaults(func=inventory)

    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument(
        "--inventory", type=Path, default=DEFAULT_OUTPUT_ROOT / "c0b_inventory_01"
    )
    prepare_parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT_ROOT / "c0b_annotation_smoke_01"
    )
    prepare_parser.add_argument("--count", type=int, default=24)
    prepare_parser.add_argument("--seed", type=int, default=90826)
    prepare_parser.add_argument("--preannotate-mediapipe", action="store_true")
    prepare_parser.add_argument(
        "--hand-task", type=Path, default=Path("assets/mediapipe/hand_landmarker.task")
    )
    prepare_parser.add_argument(
        "--pose-task",
        type=Path,
        default=Path("assets/mediapipe/pose_landmarker_lite.task"),
    )
    prepare_parser.set_defaults(func=prepare)

    check_parser = commands.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--require-reviewed", action="store_true")
    check_parser.set_defaults(func=check)

    preflight_parser = commands.add_parser("toolchain-preflight")
    preflight_parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT_ROOT / "c0b_toolchain_preflight_01"
    )
    preflight_parser.set_defaults(func=toolchain_preflight)

    smoke_parser = commands.add_parser("toolchain-smoke")
    smoke_parser.add_argument("--annotation-run", type=Path, required=True)
    smoke_parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT_ROOT / "c0b_toolchain_smoke_01"
    )
    smoke_parser.set_defaults(func=toolchain_smoke)

    args = parser.parse_args()
    try:
        result = args.func(args)
        return 0 if result.get("passed", True) else 2
    except (
        FileNotFoundError,
        ImportError,
        json.JSONDecodeError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        print(f"[tracking/c0-b0] ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
