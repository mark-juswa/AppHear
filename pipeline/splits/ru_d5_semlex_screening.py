"""Bounded visual review and supplied-pose parity checks for RU-D5 Sem-Lex clips.

This module reads only the already-extracted RU-D5 files. It never opens the
large Sem-Lex archives, accepts training rows, builds Candidate C, or trains.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.extract.config import load_config as load_extract_config
from pipeline.extract.landmarks import LandmarkExtractor

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = ROOT / "artifacts/recognition_upgrade/ru_d5/semlex_candidate_01"
EXTRACT_CONFIG = ROOT / "pipeline/config/extract.yaml"
POSE_PROBE_IDS = (
    "DppaeUWxdf8RUzQU3XsN",  # KNOW
    "DayD3saRrPxgykA1vHaO",  # WHO
    "JH2gRkZ5TO8PurPWGcH1",  # WE, signer 39
    "86F6aQk0RN3tbDcedvjc",  # COME, signer 39
    "tO0NtQa1ea7Z7Z3mTJje",  # LEAVE
)
REVIEW_DECISIONS = (
    "PENDING",
    "EXACT_TARGET",
    "ACCEPTABLE_VARIANT",
    "WRONG_VARIANT",
    "INCOMPLETE_OR_AMBIGUOUS",
    "UNUSABLE",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _decode_all(path: Path) -> tuple[list[np.ndarray], float]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return [], 0.0
    fps = float(capture.get(cv2.CAP_PROP_FPS)) or 0.0
    frames: list[np.ndarray] = []
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frames.append(frame)
    finally:
        capture.release()
    return frames, fps


def _sample_frames(frames: list[np.ndarray], count: int = 8) -> list[np.ndarray]:
    if not frames:
        return []
    indices = np.linspace(0, len(frames) - 1, num=min(count, len(frames)))
    return [frames[int(round(index))] for index in indices]


def _tile(frame: np.ndarray, width: int = 180, height: int = 135) -> np.ndarray:
    canvas = np.full((height, width, 3), 24, np.uint8)
    scale = min(width / frame.shape[1], height / frame.shape[0])
    resized = cv2.resize(
        frame,
        (max(1, int(frame.shape[1] * scale)), max(1, int(frame.shape[0] * scale))),
        interpolation=cv2.INTER_AREA,
    )
    y = (height - resized.shape[0]) // 2
    x = (width - resized.shape[1]) // 2
    canvas[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
    return canvas


def prepare_visual_review(args: argparse.Namespace) -> dict[str, Any]:
    extraction = _read_csv(args.run / "selective_extraction_manifest.csv")
    screening = {
        row["source_video_id"]: row
        for row in _read_csv(args.run / "semlex_screening_manifest.csv")
    }
    review_dir = args.run / "visual_review"
    filmstrip_dir = review_dir / "filmstrips"
    page_dir = review_dir / "contact_sheets"
    filmstrip_dir.mkdir(parents=True, exist_ok=True)
    page_dir.mkdir(parents=True, exist_ok=True)
    review_rows: list[dict[str, Any]] = []
    strips_by_gloss: dict[str, list[tuple[dict[str, Any], np.ndarray]]] = defaultdict(list)

    for row in extraction:
        video_id = row["source_video_id"]
        frames, fps = _decode_all(Path(row["raw_video_path"]))
        samples = _sample_frames(frames)
        if samples:
            tiles = [_tile(frame) for frame in samples]
            strip = np.concatenate(tiles, axis=1)
            label = np.full((42, strip.shape[1], 3), 245, np.uint8)
            cv2.putText(
                label,
                f"{row['canonical_gloss']} | {row['source_signer_id']} | {video_id} | "
                f"frames={len(frames)} fps={fps:.3f}",
                (8, 27),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.56,
                (20, 20, 20),
                1,
                cv2.LINE_AA,
            )
            strip = np.concatenate([label, strip], axis=0)
            filmstrip_path = filmstrip_dir / f"{row['canonical_gloss']}_{video_id}.jpg"
            cv2.imwrite(str(filmstrip_path), strip)
            strips_by_gloss[row["canonical_gloss"]].append((row, strip))
            decode_status = "DECODED"
        else:
            filmstrip_path = Path()
            decode_status = "VIDEO_DECODE_FAILED"
        source = screening[video_id]
        review_rows.append(
            {
                "candidate_id": row["candidate_id"],
                "canonical_gloss": row["canonical_gloss"],
                "source_signer_id": row["source_signer_id"],
                "source_video_id": video_id,
                "metadata_row_index": source.get("metadata_row_index", ""),
                "label_type": source.get("label_type", ""),
                "metadata_variant_status": source.get("metadata_variant_status", ""),
                "raw_video_path": row["raw_video_path"],
                "raw_video_sha256": row["raw_video_sha256"],
                "decoded_frames": len(frames),
                "reported_fps": f"{fps:.6f}",
                "decode_status": decode_status,
                "filmstrip_path": str(filmstrip_path.resolve()) if samples else "",
                "visual_decision": "UNUSABLE" if not samples else "PENDING",
                "visual_reason": "video decoder returned no frames" if not samples else "",
                "reviewer": "",
            }
        )

    pages: list[str] = []
    for gloss, items in strips_by_gloss.items():
        for page_index in range(0, len(items), 5):
            subset = items[page_index : page_index + 5]
            width = max(strip.shape[1] for _, strip in subset)
            normalized = []
            for _, strip in subset:
                if strip.shape[1] < width:
                    pad = np.full((strip.shape[0], width - strip.shape[1], 3), 24, np.uint8)
                    strip = np.concatenate([strip, pad], axis=1)
                normalized.append(strip)
            page = np.concatenate(normalized, axis=0)
            path = page_dir / f"{gloss}_{page_index // 5 + 1:02d}.jpg"
            cv2.imwrite(str(path), page)
            pages.append(str(path.resolve()))

    _write_csv(review_dir / "visual_review_manifest.csv", review_rows)
    summary = {
        "phase": "RU-D5",
        "stage": "semlex_bounded_visual_review_prepared",
        "video_rows": len(review_rows),
        "decoded_rows": sum(row["decode_status"] == "DECODED" for row in review_rows),
        "decode_failed_ids": [
            row["source_video_id"]
            for row in review_rows
            if row["decode_status"] != "DECODED"
        ],
        "samples_per_decoded_video": 8,
        "contact_sheet_pages": pages,
        "valid_decisions": list(REVIEW_DECISIONS),
        "accepted_for_training": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "archive_scans_performed": 0,
        "passed": len(review_rows) == 38,
    }
    _write_json(review_dir / "visual_review_prepare_summary.json", summary)
    return summary


def finalize_visual_review(args: argparse.Namespace) -> dict[str, Any]:
    review_path = args.run / "visual_review/visual_review_manifest.csv"
    decision_path = args.run / "visual_review/visual_review_decisions.csv"
    review = _read_csv(review_path)
    decisions = {
        row["source_video_id"]: row for row in _read_csv(decision_path)
    }
    review_ids = {row["source_video_id"] for row in review}
    if set(decisions) != review_ids:
        raise ValueError(
            "visual decision IDs differ from review manifest: "
            f"missing={sorted(review_ids - set(decisions))}, "
            f"extra={sorted(set(decisions) - review_ids)}"
        )
    for row in review:
        decision = decisions[row["source_video_id"]]
        value = decision["visual_decision"]
        if value not in REVIEW_DECISIONS or value == "PENDING":
            raise ValueError(f"invalid final visual decision: {value}")
        if row["decode_status"] != "DECODED" and value != "UNUSABLE":
            raise ValueError(
                f"decode-failed row must remain unusable: {row['source_video_id']}"
            )
        row["visual_decision"] = value
        row["visual_reason"] = decision["visual_reason"]
        row["reviewer"] = decision["reviewer"]
    _write_csv(review_path, review)
    by_gloss: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in review:
        by_gloss[row["canonical_gloss"]][row["visual_decision"]] += 1
    summary = {
        "phase": "RU-D5",
        "stage": "semlex_bounded_visual_review_completed",
        "reviewed_rows": len(review),
        "decision_counts_by_class": {
            gloss: dict(counts) for gloss, counts in by_gloss.items()
        },
        "accepted_for_training": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "archive_scans_performed": 0,
        "passed": len(review) == 38,
    }
    _write_json(args.run / "visual_review/visual_review_summary.json", summary)
    return summary


def _draw_stage_e_hands(
    frame: np.ndarray, hands: np.ndarray, scores: np.ndarray
) -> np.ndarray:
    image = frame.copy()
    height, width = image.shape[:2]
    colors = ((255, 255, 0), (255, 0, 255))
    for slot, color in enumerate(colors):
        if scores[slot] <= 0 or not np.isfinite(hands[slot]).all():
            continue
        for point in hands[slot]:
            x = int(round(float(point[0]) * width))
            y = int(round(float(point[1]) * height))
            cv2.circle(image, (x, y), 3, color, -1, cv2.LINE_AA)
    return image


def prepare_failure_review(args: argparse.Namespace) -> dict[str, Any]:
    from pipeline.extract.schema import ClipLandmarks

    extraction = _read_csv(args.run / "apphear_extraction/extraction_manifest.csv")
    failed = [row for row in extraction if not row.get("feature_path")]
    output = args.run / "failure_review"
    panel_dir = output / "panels"
    sheet_dir = output / "contact_sheets"
    panel_dir.mkdir(parents=True, exist_ok=True)
    sheet_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    panels_by_gloss: dict[str, list[np.ndarray]] = defaultdict(list)
    for row in failed:
        frames, _ = _decode_all(Path(row["raw_video_path"]))
        clip = ClipLandmarks.load(Path(row["stage_e_path"]))
        if len(frames) != clip.pose_image.shape[0]:
            raise ValueError(f"video/Stage-E frame mismatch: {row['sample_id']}")
        onset = int(row["onset"])
        release = int(row["release"])
        indices = sorted(
            {
                0,
                len(frames) - 1,
                *(
                    int(round(value))
                    for value in np.linspace(onset, release, num=8)
                ),
            }
        )
        tiles: list[np.ndarray] = []
        for frame_index in indices:
            image = _draw_stage_e_hands(
                frames[frame_index],
                clip.hands_image[frame_index],
                clip.hand_score[frame_index],
            )
            tile = _tile(image, width=180, height=135)
            cv2.putText(
                tile,
                (
                    f"f{frame_index} L{clip.hand_score[frame_index, 0]:.2f} "
                    f"R{clip.hand_score[frame_index, 1]:.2f}"
                ),
                (4, 130),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )
            tiles.append(tile)
        strip = np.concatenate(tiles, axis=1)
        header = np.full((52, strip.shape[1], 3), 245, np.uint8)
        cv2.putText(
            header,
            (
                f"{row['canonical_gloss']} {row['signer_group_id']} "
                f"{row['source_video_id']} {row['visual_decision']} "
                f"D1/D2={onset}-{release} reason={row['automatic_rejection_reason']}"
            ),
            (8, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (20, 20, 20),
            1,
            cv2.LINE_AA,
        )
        panel = np.concatenate([header, strip], axis=0)
        panel_path = panel_dir / f"{row['canonical_gloss']}_{row['source_video_id']}.jpg"
        cv2.imwrite(str(panel_path), panel)
        panels_by_gloss[row["canonical_gloss"]].append(panel)
        rows.append(
            {
                "sample_id": row["sample_id"],
                "canonical_gloss": row["canonical_gloss"],
                "source_signer_id": row["signer_group_id"],
                "source_video_id": row["source_video_id"],
                "visual_decision": row["visual_decision"],
                "d1_d2_onset": onset,
                "d1_d2_release": release,
                "d1_d2_rejection_reason": row["automatic_rejection_reason"],
                "any_hand_coverage": row["any_hand_coverage"],
                "two_hand_coverage": row["two_hand_coverage"],
                "panel_path": str(panel_path.resolve()),
                "failure_classification": "PENDING",
                "failure_reason": "",
                "rescue_allowed": "false",
            }
        )
    sheets: list[str] = []
    for gloss, panels in panels_by_gloss.items():
        width = max(panel.shape[1] for panel in panels)
        normalized: list[np.ndarray] = []
        for panel in panels:
            if panel.shape[1] < width:
                padding = np.full(
                    (panel.shape[0], width - panel.shape[1], 3), 24, np.uint8
                )
                panel = np.concatenate([panel, padding], axis=1)
            normalized.append(panel)
        sheet = np.concatenate(normalized, axis=0)
        sheet_path = sheet_dir / f"{gloss}.jpg"
        cv2.imwrite(str(sheet_path), sheet)
        sheets.append(str(sheet_path.resolve()))
    _write_csv(output / "failure_review_manifest.csv", rows)
    summary = {
        "phase": "RU-D5",
        "stage": "semlex_failed_landmark_review_prepared",
        "failed_feature_rows": len(rows),
        "exact_target_rows": sum(
            row["visual_decision"] == "EXACT_TARGET" for row in rows
        ),
        "acceptable_variant_rows": sum(
            row["visual_decision"] == "ACCEPTABLE_VARIANT" for row in rows
        ),
        "contact_sheets": sheets,
        "archive_scans_performed": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "passed": len(rows) == 15,
    }
    _write_json(output / "failure_review_prepare_summary.json", summary)
    return summary


def finalize_failure_review(args: argparse.Namespace) -> dict[str, Any]:
    output = args.run / "failure_review"
    review = _read_csv(output / "failure_review_manifest.csv")
    decisions = {
        row["source_video_id"]: row
        for row in _read_csv(output / "failure_review_decisions.csv")
    }
    if {row["source_video_id"] for row in review} != set(decisions):
        raise ValueError("failure-review decision IDs do not match failed rows")
    allowed = {
        "BAD_FRAMING_OR_HAND_NOT_VISIBLE",
        "MEDIAPIPE_DOMAIN_FAILURE",
        "WRONG_OR_AMBIGUOUS_VARIANT",
        "BOUNDARY_ONLY_REPAIRABLE",
        "PIPELINE_OR_EXTRACTION_BUG",
    }
    for row in review:
        decision = decisions[row["source_video_id"]]
        classification = decision["failure_classification"]
        if classification not in allowed:
            raise ValueError(f"invalid failure classification: {classification}")
        rescue = decision["rescue_allowed"].lower() == "true"
        if rescue != (
            classification
            in {
                "BOUNDARY_ONLY_REPAIRABLE",
                "PIPELINE_OR_EXTRACTION_BUG",
            }
        ):
            raise ValueError(f"invalid rescue policy: {row['source_video_id']}")
        row["failure_classification"] = classification
        row["failure_reason"] = decision["failure_reason"]
        row["rescue_allowed"] = str(rescue).lower()
    _write_csv(output / "failure_review_manifest.csv", review)
    counts: dict[str, int] = defaultdict(int)
    for row in review:
        counts[row["failure_classification"]] += 1
    summary = {
        "phase": "RU-D5",
        "stage": "semlex_failed_landmark_review_completed",
        "reviewed_rows": len(review),
        "classification_counts": dict(counts),
        "boundary_repairable_rows": sum(
            row["failure_classification"] == "BOUNDARY_ONLY_REPAIRABLE"
            for row in review
        ),
        "archive_scans_performed": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "passed": len(review) == 15,
    }
    _write_json(output / "failure_review_summary.json", summary)
    return summary


def apply_boundary_repairs(args: argparse.Namespace) -> dict[str, Any]:
    from pipeline.extract.schema import ClipLandmarks
    from pipeline.features.config import load_config as load_feature_config
    from pipeline.features.contract import SCHEMA_VERSION, clip_features_realtimed
    from pipeline.normalize.config import load_config as load_normalize_config
    from pipeline.splits.ru_d3_repair_candidate import (
        FEATURE_CONFIG,
        NORMALIZE_CONFIG,
        _coverage,
        _recoverable,
    )

    extraction = {
        row["source_video_id"]: row
        for row in _read_csv(args.run / "apphear_extraction/extraction_manifest.csv")
    }
    spans = _read_csv(args.run / "failure_review/boundary_repair_spans.csv")
    normalize_cfg = load_normalize_config(NORMALIZE_CONFIG)
    feature_cfg = load_feature_config(FEATURE_CONFIG)
    output = args.run / "failure_review/boundary_repairs"
    results: list[dict[str, Any]] = []
    for span in spans:
        row = extraction[span["source_video_id"]]
        if row["visual_decision"] != "EXACT_TARGET":
            raise ValueError(f"boundary repair is not exact-target: {span['source_video_id']}")
        clip = ClipLandmarks.load(Path(row["stage_e_path"]))
        onset = int(span["manual_onset"])
        release = int(span["manual_release"])
        if not 0 <= onset <= release < clip.pose_image.shape[0]:
            raise ValueError(f"invalid manual span: {span['source_video_id']}")
        any_rate, two_rate, left_rate, right_rate = _coverage(
            clip.hand_score, onset, release
        )
        valid, rejection = _recoverable(
            row["canonical_gloss"],
            True,
            release - onset + 1,
            any_rate,
            two_rate,
        )
        if not valid:
            raise ValueError(
                f"manual repair does not pass frozen landmark gate: "
                f"{span['source_video_id']} {rejection}"
            )
        feature, frame_mask, length, _ = clip_features_realtimed(
            clip.hands_image,
            clip.pose_image,
            onset,
            release,
            normalize_cfg,
            feature_cfg.streaming_t_max,
        )
        feature_path = output / "per_clip" / f"{row['sample_id']}.npz"
        feature_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            feature_path,
            feature=feature,
            frame_mask=frame_mask,
            length=np.asarray(length, dtype=np.int32),
            schema_version=np.asarray(SCHEMA_VERSION),
        )
        span_record = {
            "method": "ru_d5_manual_visual_boundary_v1",
            "sample_id": row["sample_id"],
            "source_video_id": row["source_video_id"],
            "canonical_gloss": row["canonical_gloss"],
            "onset": onset,
            "release": release,
            "span_length": release - onset + 1,
            "any_hand_coverage": any_rate,
            "two_hand_coverage": two_rate,
            "left_hand_coverage": left_rate,
            "right_hand_coverage": right_rate,
            "visual_basis": span["visual_basis"],
        }
        span_path = output / "spans" / f"{row['sample_id']}.span.json"
        span_path.parent.mkdir(parents=True, exist_ok=True)
        span_path.write_text(json.dumps(span_record, indent=2) + "\n", encoding="utf-8")
        results.append(
            {
                "sample_id": row["sample_id"],
                "canonical_gloss": row["canonical_gloss"],
                "source_signer_id": row["signer_group_id"],
                "source_video_id": row["source_video_id"],
                "manual_onset": onset,
                "manual_release": release,
                "span_length": release - onset + 1,
                "any_hand_coverage": f"{any_rate:.6f}",
                "two_hand_coverage": f"{two_rate:.6f}",
                "feature_path": str(feature_path.resolve()),
                "feature_sha256": _sha256_file(feature_path),
                "span_path": str(span_path.resolve()),
                "span_sha256": _sha256_file(span_path),
                "repair_status": "BOUNDARY_REPAIRED_EXACT_TARGET",
            }
        )
    _write_csv(output / "boundary_repair_manifest.csv", results)
    summary = {
        "phase": "RU-D5",
        "stage": "semlex_manual_boundary_repairs_completed",
        "repair_rows": len(results),
        "repair_counts_by_class": dict(
            sorted(
                (gloss, sum(row["canonical_gloss"] == gloss for row in results))
                for gloss in {row["canonical_gloss"] for row in results}
            )
        ),
        "archive_scans_performed": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "passed": len(results) == 13,
    }
    _write_json(output / "boundary_repair_summary.json", summary)
    return summary


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _finite_metrics(reference: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
    mask = np.isfinite(reference) & np.isfinite(candidate)
    overlap = int(mask.sum())
    if not overlap:
        return {"finite_coordinate_overlap": 0, "mae": None, "correlation": None}
    left = reference[mask].astype(np.float64)
    right = candidate[mask].astype(np.float64)
    correlation = float(np.corrcoef(left, right)[0, 1]) if overlap > 1 else None
    return {
        "finite_coordinate_overlap": overlap,
        "mae": float(np.mean(np.abs(left - right))),
        "correlation": correlation,
    }


def _layout_metrics(semlex: np.ndarray, clip: Any) -> list[dict[str, Any]]:
    layouts = {
        "FACE478_LEFT21_POSE33_RIGHT21": {"left": 478, "pose": 499, "right": 532},
        "POSE33_FACE478_LEFT21_RIGHT21": {"pose": 0, "left": 511, "right": 532},
        "FACE478_POSE33_LEFT21_RIGHT21": {"pose": 478, "left": 511, "right": 532},
    }
    frames = min(semlex.shape[0], clip.pose_image.shape[0])
    results: list[dict[str, Any]] = []
    for name, offsets in layouts.items():
        blocks = {
            "pose_xyz": (
                semlex[:frames, offsets["pose"] : offsets["pose"] + 33, :3],
                clip.pose_image[:frames, :, :3],
            ),
            "left_hand_xyz": (
                semlex[:frames, offsets["left"] : offsets["left"] + 21, :3],
                clip.hands_image[:frames, 0, :, :3],
            ),
            "right_hand_xyz": (
                semlex[:frames, offsets["right"] : offsets["right"] + 21, :3],
                clip.hands_image[:frames, 1, :, :3],
            ),
        }
        for block, (reference, candidate) in blocks.items():
            results.append(
                {
                    "layout": name,
                    "block": block,
                    **_finite_metrics(reference, candidate),
                }
            )
    return results


def pose_equivalence(args: argparse.Namespace) -> dict[str, Any]:
    extraction = {
        row["source_video_id"]: row
        for row in _read_csv(args.run / "selective_extraction_manifest.csv")
    }
    output = args.run / "pose_equivalence"
    stage_dir = output / "apphear_stage_e"
    stage_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    config = load_extract_config(EXTRACT_CONFIG)
    with LandmarkExtractor(config) as extractor:
        for video_id in POSE_PROBE_IDS:
            row = extraction[video_id]
            if row["provided_pose_status"] != "AVAILABLE":
                raise ValueError(f"pose probe row lacks supplied pose: {video_id}")
            clip, meta = extractor.extract(Path(row["raw_video_path"]))
            clip.save(stage_dir / f"{video_id}.npz")
            semlex = np.load(row["provided_pose_path"], allow_pickle=False)
            semlex_finite = np.isfinite(semlex)
            semlex_present = np.all(np.isfinite(semlex), axis=2)
            semlex_left_present = np.all(np.isfinite(semlex[:, 511:532, :]), axis=(1, 2))
            semlex_right_present = np.all(np.isfinite(semlex[:, 532:553, :]), axis=(1, 2))
            metrics = _layout_metrics(semlex, clip)
            best = min(
                (item for item in metrics if item["mae"] is not None),
                key=lambda item: float(item["mae"]),
            )
            results.append(
                {
                    "source_video_id": video_id,
                    "canonical_gloss": row["canonical_gloss"],
                    "source_signer_id": row["source_signer_id"],
                    "video_frames": int(meta["n_frames"]),
                    "video_fps": float(meta["native_fps"]),
                    "semlex_shape": list(semlex.shape),
                    "semlex_dtype": str(semlex.dtype),
                    "frame_count_equal": int(meta["n_frames"]) == int(semlex.shape[0]),
                    "semlex_finite_fraction": float(np.mean(semlex_finite)),
                    "semlex_all_xyz_present_fraction": float(np.mean(semlex_present)),
                    "semlex_left_hand_frame_coverage": float(
                        np.mean(semlex_left_present)
                    ),
                    "semlex_right_hand_frame_coverage": float(
                        np.mean(semlex_right_present)
                    ),
                    "apphear_left_hand_frame_coverage": float(np.mean(clip.hand_score[:, 0] > 0)),
                    "apphear_right_hand_frame_coverage": float(np.mean(clip.hand_score[:, 1] > 0)),
                    "apphear_pose_frame_coverage": float(np.mean(clip.pose_score > 0)),
                    "best_layout_block": best,
                    "layout_block_metrics": metrics,
                }
            )
    frame_alignment = all(row["frame_count_equal"] for row in results)
    visibility_available = False
    exact_schema_reproducible = False
    report = {
        "phase": "RU-D5",
        "stage": "semlex_supplied_pose_equivalence_probe",
        "probe_ids": list(POSE_PROBE_IDS),
        "excluded_missing_supplied_pose_ids": ["XRGDr8F4tCHv6uQNwaPd"],
        "matched_video_pose_rows": len(results),
        "frame_count_alignment_all": frame_alignment,
        "semlex_common_shape_suffix": [553, 3],
        "empirical_landmark_layout": "FACE478_POSE33_LEFT21_RIGHT21",
        "apphear_required_blocks": {
            "hands_image": [2, 21, 3],
            "pose_image": [33, 4],
            "hand_score": [2],
            "pose_score": [],
        },
        "supplied_pose_visibility_available": visibility_available,
        "exact_apphear_schema_v3_reproducible": exact_schema_reproducible,
        "direct_reuse_decision": "REJECT_FOR_APPHEAR_FEATURE_EXTRACTION",
        "reason": (
            "Sem-Lex arrays contain only xyz per landmark and do not carry AppHear's "
            "required pose visibility/hand-score/presence contract; coordinate and slot "
            "equivalence is additionally evaluated below rather than assumed."
        ),
        "clips": results,
        "accepted_for_training": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "archive_scans_performed": 0,
        "passed": len(results) == len(POSE_PROBE_IDS),
    }
    _write_json(output / "pose_equivalence_report.json", report)
    return report


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    for name in (
        "prepare-visual-review",
        "finalize-visual-review",
        "prepare-failure-review",
        "finalize-failure-review",
        "apply-boundary-repairs",
        "pose-equivalence",
    ):
        child = sub.add_parser(name)
        child.add_argument("--run", type=Path, default=DEFAULT_RUN)
    return root


def main() -> int:
    args = parser().parse_args()
    result = {
        "prepare-visual-review": prepare_visual_review,
        "finalize-visual-review": finalize_visual_review,
        "prepare-failure-review": prepare_failure_review,
        "finalize-failure-review": finalize_failure_review,
        "apply-boundary-repairs": apply_boundary_repairs,
        "pose-equivalence": pose_equivalence,
    }[args.command](args)
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
