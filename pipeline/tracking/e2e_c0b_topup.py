"""Mine an independent hard-condition top-up for the C0-B0 hand detector.

This package is annotation-data readiness only. It excludes frozen evaluation
lineage and the previously reviewed C0-B0 package, then ranks independent
frames by detector failure proxies. It never authorizes training.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import cv2

from pipeline.tracking.e2e_c0b import (
    ANNOTATION_FIELDS,
    _fit,
    _frame,
    _path_key,
    _proposal_boxes,
    _read_csv,
    _sha256,
    _write_csv,
    _write_json,
)
from pipeline.tracking.e2e_gold import INDEX_FIELDS, REVIEW_FIELDS

EXPERIMENT = "c0b_hard_condition_topup_v1"
DEFAULT_ROOT = Path("artifacts/recognition_upgrade/e2e_c0")
DEFAULT_INVENTORY = DEFAULT_ROOT / "c0b_inventory_01"
DEFAULT_BASE_RUN = DEFAULT_ROOT / "c0b_training_annotation_pilot_01"
DEFAULT_NEGATIVE_MANIFEST = Path(
    "artifacts/recognition_upgrade/e6_rejection/e6_3_frozen_embedding_01/"
    "dataset/negative_window_manifest.csv"
)
DEFAULT_SCAN_OUTPUT = DEFAULT_ROOT / "c0b_condition_topup_scan_01"
DEFAULT_OUTPUT = DEFAULT_ROOT / "c0b_condition_topup_01"
DEFAULT_HAND_TASK = Path("assets/mediapipe/hand_landmarker.task")
DEFAULT_POSE_TASK = Path("assets/mediapipe/pose_landmarker_lite.task")

SCAN_FIELDS = (
    "candidate_id",
    "source_dataset",
    "source_split",
    "participant_id",
    "gloss",
    "raw_video_path",
    "raw_video_sha256",
    "frame_fraction",
    "frame_index",
    "timestamp_ms",
    "image_width",
    "image_height",
    "proposal_count",
    "detected_hands_json",
    "proposed_boxes_json",
    "pose_wrists_json",
    "blur_score",
    "max_box_area",
    "min_edge_margin",
    "near_face_proxy",
    "possible_missed_second_hand",
)

SELECTION_FIELDS = (
    "sample_id",
    "mining_stratum",
    "candidate_id",
    "source_dataset",
    "participant_id",
    "gloss",
    "raw_video_path",
    "raw_video_sha256",
    "frame_index",
    "timestamp_ms",
    "blur_score",
    "proposal_count",
    "max_box_area",
    "min_edge_margin",
    "near_face_proxy",
    "possible_missed_second_hand",
)

DEFAULT_QUOTAS = {
    "blur_or_zero_detection": 25,
    "possible_missed_second_hand": 25,
    "edge_or_partial_proxy": 20,
    "near_face_proxy": 20,
    "small_hand_proxy": 10,
}


def _append_csv(path: Path, row: dict[str, Any], fields: Iterable[str]) -> None:
    fieldnames = list(fields)
    exists = path.is_file()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in fieldnames})


def _quantile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return ordered[max(0, min(len(ordered) - 1, index))]


def _balanced_pool(
    rows: list[dict[str, str]], count: int, seed: int
) -> list[dict[str, str]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["source_dataset"], row["participant_id"])].append(row)
    rng = random.Random(seed)
    for group in groups.values():
        rng.shuffle(group)
    source_keys: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for key in groups:
        source_keys[key[0]].append(key)
    source_queues: dict[str, list[dict[str, str]]] = defaultdict(list)
    for source, keys in source_keys.items():
        rng.shuffle(keys)
        while True:
            progressed = False
            for key in keys:
                if groups[key]:
                    source_queues[source].append(groups[key].pop())
                    progressed = True
            if not progressed:
                break
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
    return selected


def _excluded_lineage(
    inventory: Path, base_run: Path
) -> tuple[set[str], set[str]]:
    protected = _read_csv(inventory / "protected_source_registry.csv")
    base = _read_csv(base_run / "annotation_manifest.csv")
    rows = protected + base
    paths = {_path_key(row["raw_video_path"]) for row in rows if row.get("raw_video_path")}
    hashes = {
        row["raw_video_sha256"].strip().upper()
        for row in rows
        if row.get("raw_video_sha256", "").strip()
    }
    return paths, hashes


def _audit_negative_manifest(
    manifest: Path, excluded_paths: set[str], excluded_hashes: set[str]
) -> dict[str, Any]:
    if not manifest.is_file():
        return {
            "manifest": str(manifest.resolve()),
            "development_rows": 0,
            "independent_rows": 0,
            "excluded_overlap_rows": 0,
            "reason": "manifest missing",
        }
    rows = [row for row in _read_csv(manifest) if row.get("role") == "development_negative"]
    independent = []
    for row in rows:
        path_overlap = _path_key(row["raw_video_path"]) in excluded_paths
        digest = row.get("raw_video_sha256", "").strip().upper()
        hash_overlap = bool(digest and digest in excluded_hashes)
        if not path_overlap and not hash_overlap:
            independent.append(row)
    return {
        "manifest": str(manifest.resolve()),
        "development_rows": len(rows),
        "independent_rows": len(independent),
        "excluded_overlap_rows": len(rows) - len(independent),
        "subtype_counts": dict(sorted(Counter(row["negative_subtype"] for row in rows).items())),
        "reason": (
            "all development-negative rows overlap protected evaluation lineage"
            if rows and not independent
            else "independent rows require a separate hand-visibility review"
        ),
    }


def _scan_frame(
    row: dict[str, str], fraction: float, runner: Any
) -> dict[str, Any]:
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
    image = _frame(cap, center, video)
    cap.release()
    hands, wrists = runner.detect(image)
    boxes = _proposal_boxes(hands)
    areas = [
        max(0.0, box["x_max"] - box["x_min"])
        * max(0.0, box["y_max"] - box["y_min"])
        for box in boxes
    ]
    margins = [
        min(box["x_min"], box["y_min"], 1.0 - box["x_max"], 1.0 - box["y_max"])
        for box in boxes
    ]
    upper_center = any(
        (box["y_min"] + box["y_max"]) / 2.0 <= 0.45
        and 0.15 <= (box["x_min"] + box["x_max"]) / 2.0 <= 0.85
        for box in boxes
    )
    visible_wrists = sum(float(wrist.get("visibility", 0.0)) >= 0.5 for wrist in wrists.values())
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return {
        **{field: row.get(field, "") for field in (
            "candidate_id",
            "source_dataset",
            "source_split",
            "participant_id",
            "gloss",
            "raw_video_path",
        )},
        "raw_video_sha256": _sha256(video),
        "frame_fraction": fraction,
        "frame_index": center,
        "timestamp_ms": round(center * 1000.0 / fps),
        "image_width": image.shape[1],
        "image_height": image.shape[0],
        "proposal_count": len(boxes),
        "detected_hands_json": json.dumps(hands, separators=(",", ":")),
        "proposed_boxes_json": json.dumps(boxes, separators=(",", ":")),
        "pose_wrists_json": json.dumps(wrists, separators=(",", ":")),
        "blur_score": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        "max_box_area": max(areas, default=0.0),
        "min_edge_margin": min(margins, default=1.0),
        "near_face_proxy": str(upper_center).lower(),
        "possible_missed_second_hand": str(len(boxes) == 1 and visible_wrists == 2).lower(),
    }


def mine(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    output.mkdir(parents=True, exist_ok=args.resume)
    scan_path = output / "scan_manifest.csv"
    excluded_paths, excluded_hashes = _excluded_lineage(args.inventory, args.base_run)
    negative_audit = _audit_negative_manifest(
        args.negative_manifest, excluded_paths, excluded_hashes
    )
    inventory_rows = [
        row
        for row in _read_csv(args.inventory / "source_inventory.csv")
        if row["eligibility"] == "candidate"
        and _path_key(row["raw_video_path"]) not in excluded_paths
    ]
    pool = _balanced_pool(inventory_rows, args.scan_count, args.seed)
    existing = _read_csv(scan_path) if scan_path.is_file() else []
    completed_ids = {row["candidate_id"] for row in existing}
    rng = random.Random(args.seed)
    fractions = (0.25, 0.50, 0.75)
    fraction_by_id = {
        row["candidate_id"]: fractions[rng.randrange(len(fractions))] for row in pool
    }

    failures: list[dict[str, str]] = []
    pending = [row for row in pool if row["candidate_id"] not in completed_ids]
    if pending:
        from pipeline.tracking.e2e_pilot import HandPoseRunner

        runner_context: Any = HandPoseRunner(args.hand_task, args.pose_task)
    else:
        runner_context = None
    if runner_context is not None:
        with runner_context as runner:
            for index, row in enumerate(pending, start=1):
                try:
                    scanned = _scan_frame(row, fraction_by_id[row["candidate_id"]], runner)
                    if scanned["raw_video_sha256"] in excluded_hashes:
                        failures.append(
                            {
                                "candidate_id": row["candidate_id"],
                                "raw_video_path": row["raw_video_path"],
                                "reason": "protected or base-run hash overlap",
                            }
                        )
                        continue
                    _append_csv(scan_path, scanned, SCAN_FIELDS)
                except (OSError, ValueError) as error:
                    failures.append(
                        {
                            "candidate_id": row["candidate_id"],
                            "raw_video_path": row["raw_video_path"],
                            "reason": str(error),
                        }
                    )
                completed = len(completed_ids) + index
                print(
                    f"[tracking/c0-b0-topup] scan {completed}/{len(pool)} "
                    f"{row['candidate_id']}"
                )
    rows = _read_csv(scan_path) if scan_path.is_file() else []
    _write_csv(
        output / "scan_failures.csv",
        failures,
        ("candidate_id", "raw_video_path", "reason"),
    )
    summary = {
        "experiment": EXPERIMENT,
        "stage": "independent_hard_condition_scan",
        "requested": args.scan_count,
        "completed": len(rows),
        "failures_this_invocation": len(failures),
        "source_counts": dict(sorted(Counter(row["source_dataset"] for row in rows).items())),
        "negative_manifest_audit": negative_audit,
        "passed": len(rows) >= args.scan_count,
        "training_authorized": False,
        "next": "prepare-topup after this scan passes",
    }
    _write_json(output / "scan_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return summary


def _candidate_strata(
    row: dict[str, str], blur_cutoff: float, small_cutoff: float
) -> list[str]:
    count = int(row["proposal_count"])
    result = []
    if count == 0 or float(row["blur_score"]) <= blur_cutoff:
        result.append("blur_or_zero_detection")
    if row["possible_missed_second_hand"] == "true":
        result.append("possible_missed_second_hand")
    if count > 0 and float(row["min_edge_margin"]) <= 0.03:
        result.append("edge_or_partial_proxy")
    if row["near_face_proxy"] == "true":
        result.append("near_face_proxy")
    if count > 0 and float(row["max_box_area"]) <= small_cutoff:
        result.append("small_hand_proxy")
    return result


def _select_topup(
    rows: list[dict[str, str]], count: int, seed: int
) -> tuple[list[tuple[str, dict[str, str]]], dict[str, Any]]:
    if count <= 0:
        raise ValueError("count must be positive")
    blur_cutoff = _quantile([float(row["blur_score"]) for row in rows], 0.20)
    positive_areas = [float(row["max_box_area"]) for row in rows if int(row["proposal_count"]) > 0]
    small_cutoff = _quantile(positive_areas, 0.25)
    by_stratum: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        for stratum in _candidate_strata(row, blur_cutoff, small_cutoff):
            by_stratum[stratum].append(row)

    scale = count / sum(DEFAULT_QUOTAS.values())
    quotas = {name: round(value * scale) for name, value in DEFAULT_QUOTAS.items()}
    while sum(quotas.values()) < count:
        quotas[min(quotas, key=lambda name: quotas[name])] += 1
    while sum(quotas.values()) > count:
        quotas[max(quotas, key=lambda name: quotas[name])] -= 1

    selected: list[tuple[str, dict[str, str]]] = []
    used: set[str] = set()
    for offset, stratum in enumerate(DEFAULT_QUOTAS):
        candidates = _balanced_pool(by_stratum[stratum], len(by_stratum[stratum]), seed + offset)
        for row in candidates:
            if row["candidate_id"] in used:
                continue
            selected.append((stratum, row))
            used.add(row["candidate_id"])
            if sum(item[0] == stratum for item in selected) == quotas[stratum]:
                break
    if len(selected) < count:
        fallback = sorted(
            (row for row in rows if row["candidate_id"] not in used),
            key=lambda row: (float(row["blur_score"]), -int(row["proposal_count"])),
        )
        for row in fallback[: count - len(selected)]:
            selected.append(("hardness_fallback", row))
    if len(selected) < count:
        raise ValueError(f"only {len(selected)} unique top-up candidates; requested {count}")
    diagnostics = {
        "blur_cutoff_scan_q20": blur_cutoff,
        "small_hand_area_cutoff_scan_q25": small_cutoff,
        "requested_quotas": quotas,
        "available_by_stratum": {
            name: len(by_stratum[name]) for name in DEFAULT_QUOTAS
        },
        "selected_by_stratum": dict(sorted(Counter(name for name, _ in selected).items())),
    }
    return selected, diagnostics


def _materialize(
    row: dict[str, str], sample_id: str, output: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    video = Path(row["raw_video_path"])
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise OSError(f"cannot open video: {video}")
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    center = int(row["frame_index"])
    indices = [min(frame_count - 1, max(0, center + delta)) for delta in (-8, -4, 0, 4, 8)]
    frames = [_frame(cap, index, video) for index in indices]
    cap.release()
    center_path = output / "center_images" / f"{sample_id}.png"
    context_path = output / "context_panels" / f"{sample_id}.jpg"
    center_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(center_path), frames[2]):
        raise OSError(f"cannot write {center_path}")
    if not cv2.imwrite(str(context_path), cv2.hconcat([_fit(image) for image in frames])):
        raise OSError(f"cannot write {context_path}")
    boxes = json.loads(row["proposed_boxes_json"])
    index_row = {
        "sample_id": sample_id,
        "clip_id": video.stem,
        "video_file": video.name,
        "participant_id": row["participant_id"],
        "split": "detector_training_candidate",
        "gloss": row["gloss"],
        "frame_index": center,
        "timestamp_ms": row["timestamp_ms"],
        "sampling_cadence": f"mined_fraction_{float(row['frame_fraction']):.2f}",
        "sampling_target_hand": "",
        "sampling_target_detected": "",
        "sampling_raw_detected_hands": "",
        "image_width": row["image_width"],
        "image_height": row["image_height"],
        "center_image_path": str(center_path.resolve()),
        "context_panel_path": str(context_path.resolve()),
        "diagnostic_panel_path": "",
        "detected_hands_json": row.get("detected_hands_json", "[]"),
        "pose_wrists_json": row["pose_wrists_json"],
    }
    review_row = {
        "sample_id": sample_id,
        "review_status": "",
        "source_mirrored": "unknown",
        "mirror_evidence": "",
        "visible_hand_count": str(len(boxes)) if boxes else "",
        "gold_hands_json": json.dumps(boxes, separators=(",", ":")),
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
        "raw_video_sha256": row["raw_video_sha256"],
        "frame_index": center,
        "timestamp_ms": row["timestamp_ms"],
        "frame_fraction": row["frame_fraction"],
        "center_image_path": str(center_path.resolve()),
        "context_panel_path": str(context_path.resolve()),
        "protected_overlap": "false",
    }
    return index_row, review_row, annotation_row


def prepare_topup(args: argparse.Namespace) -> dict[str, Any]:
    scan_run = args.scan_run
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    scan_rows = _read_csv(scan_run / "scan_manifest.csv")
    selected, diagnostics = _select_topup(scan_rows, args.count, args.seed)
    index_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    annotation_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    for number, (stratum, row) in enumerate(selected, start=1):
        sample_id = f"c0b_topup_{number:04d}"
        index_row, review_row, annotation_row = _materialize(row, sample_id, output)
        index_rows.append(index_row)
        review_rows.append(review_row)
        annotation_rows.append(annotation_row)
        selection_rows.append(
            {"sample_id": sample_id, "mining_stratum": stratum, **row}
        )
        print(f"[tracking/c0-b0-topup] prepare {number}/{args.count} {stratum}")
    _write_csv(output / "internal_index.csv", index_rows, INDEX_FIELDS)
    _write_csv(output / "gold_review.csv", review_rows, REVIEW_FIELDS)
    _write_csv(output / "annotation_manifest.csv", annotation_rows, ANNOTATION_FIELDS)
    _write_csv(output / "mining_selection.csv", selection_rows, SELECTION_FIELDS)
    summary = {
        "experiment": EXPERIMENT,
        "stage": "hard_condition_annotation_package",
        "rows": len(selected),
        "source_counts": dict(
            sorted(Counter(row["source_dataset"] for _, row in selected).items())
        ),
        "signer_count": len({row["participant_id"] for _, row in selected}),
        "selection": diagnostics,
        "reviewed": False,
        "passed": True,
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
        "# C0-B0 Hard-Condition Top-Up Review\n\n"
        "This is a mined annotation top-up, not a model-training authorization. Review every "
        "frame. MediaPipe boxes are editable proposals, including zero-box frames. Correct all "
        "visible hands and record the actual condition flags. Mining strata are proxies only.\n\n"
        f"```powershell\n{summary['review_command']}\n{summary['check_command']}\n```\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return summary


def backfill_audit_proposals(args: argparse.Namespace) -> dict[str, Any]:
    """Restore landmark-level proposals required by the gold diagnostic auditor."""
    run = args.run_dir
    index_path = run / "internal_index.csv"
    rows = _read_csv(index_path)
    if not rows:
        raise ValueError("internal_index.csv has no rows")

    from pipeline.tracking.e2e_pilot import HandPoseRunner

    proposal_instances = 0
    with HandPoseRunner(args.hand_task, args.pose_task) as runner:
        for number, row in enumerate(rows, start=1):
            image = cv2.imread(row["center_image_path"])
            if image is None:
                raise OSError(f"cannot read {row['center_image_path']}")
            hands, wrists = runner.detect(image)
            row["detected_hands_json"] = json.dumps(hands, separators=(",", ":"))
            row["pose_wrists_json"] = json.dumps(wrists, separators=(",", ":"))
            proposal_instances += len(hands)
            print(
                f"[tracking/c0-b0-topup] backfill {number}/{len(rows)} "
                f"{row['sample_id']}"
            )
    _write_csv(index_path, rows, INDEX_FIELDS)
    summary = {
        "experiment": EXPERIMENT,
        "stage": "audit_proposal_backfill",
        "rows": len(rows),
        "proposal_instances": proposal_instances,
        "passed": True,
        "training_authorized": False,
        "warning": "Diagnostic metadata repair only; reviewed gold boxes were not modified.",
    }
    _write_json(run / "proposal_backfill_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="C0-B0 independent hard-condition top-up")
    commands = parser.add_subparsers(dest="command", required=True)

    mine_parser = commands.add_parser("mine")
    mine_parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    mine_parser.add_argument("--base-run", type=Path, default=DEFAULT_BASE_RUN)
    mine_parser.add_argument("--negative-manifest", type=Path, default=DEFAULT_NEGATIVE_MANIFEST)
    mine_parser.add_argument("--output", type=Path, default=DEFAULT_SCAN_OUTPUT)
    mine_parser.add_argument("--scan-count", type=int, default=900)
    mine_parser.add_argument("--seed", type=int, default=100826)
    mine_parser.add_argument("--resume", action="store_true")
    mine_parser.add_argument("--hand-task", type=Path, default=DEFAULT_HAND_TASK)
    mine_parser.add_argument("--pose-task", type=Path, default=DEFAULT_POSE_TASK)
    mine_parser.set_defaults(func=mine)

    prepare_parser = commands.add_parser("prepare-topup")
    prepare_parser.add_argument("--scan-run", type=Path, default=DEFAULT_SCAN_OUTPUT)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--count", type=int, default=100)
    prepare_parser.add_argument("--seed", type=int, default=100826)
    prepare_parser.set_defaults(func=prepare_topup)

    backfill_parser = commands.add_parser("backfill-audit-proposals")
    backfill_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    backfill_parser.add_argument("--hand-task", type=Path, default=DEFAULT_HAND_TASK)
    backfill_parser.add_argument("--pose-task", type=Path, default=DEFAULT_POSE_TASK)
    backfill_parser.set_defaults(func=backfill_audit_proposals)

    args = parser.parse_args()
    try:
        result = args.func(args)
        return 0 if result.get("passed", True) else 2
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as error:
        print(f"[tracking/c0-b0-topup] ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
