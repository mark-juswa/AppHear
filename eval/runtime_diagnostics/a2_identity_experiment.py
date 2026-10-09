"""A2-0 evidence preparation and A2-1 identity-only evaluation.

The package is deliberately human-gated.  ``prepare`` never treats MediaPipe handedness as
anatomical truth; ``evaluate`` refuses to run until every selected frame has been reviewed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from eval.runtime_diagnostics.a2_identity_tracker import (
    AnatomicalIdentityTracker,
    IdentityConfig,
    MediaPipeSlot,
    observations_from_feature,
    pose_wrists_from_feature,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "model/config/recognition_upgrade/a2_identity.json"
DEFAULT_OUTPUT = ROOT / "artifacts/recognition_upgrade/a2_landmark_continuity/a2_0_identity_01"
A1_ROOT = ROOT / "artifacts/recognition_upgrade/a1_independent_clock/signing_sentinel_01"
RU_D7_ROOT = ROOT / "artifacts/recognition_upgrade/ru_d7/phone_bc_01"

INDEX_FIELDS = (
    "sample_id",
    "cohort",
    "attempt_id",
    "gloss",
    "repetition_id",
    "expected_hands",
    "frame_id",
    "timestamp_ns",
    "in_sign_span",
    "direct_mp_left",
    "direct_mp_right",
    "image_path",
    "panel_path",
    "source_trace_path",
)

ANNOTATION_FIELDS = (
    "sample_id",
    "review_status",
    "visible_left",
    "visible_right",
    "mp_left_identity",
    "mp_right_identity",
    "recoverable_left",
    "recoverable_right",
    "hand_hand_contact",
    "hand_body_contact",
    "crossing_or_midline",
    "leaving_frame",
    "no_hand_rest",
    "notes",
)

VISIBILITY_VALUES = {"yes", "no", "uncertain"}
IDENTITY_VALUES = {"left", "right", "ambiguous", "none"}
RECOVERABILITY_VALUES = {"yes", "no", "uncertain", "not_applicable"}
BOOL_VALUES = {"yes", "no"}
FRAME_RE = re.compile(r"frame_(\d+)\.jpg$", re.IGNORECASE)

HASH_FILES = (
    "android/app/src/main/java/com/example/apphear/pipeline/A1Scheduling.kt",
    "android/app/src/main/java/com/example/apphear/pipeline/IndependentClockFrameAnalyzer.kt",
    "android/app/src/main/java/com/example/apphear/pipeline/recognition/LandmarkAdapter.kt",
    "android/app/src/main/java/com/example/apphear/pipeline/recognition/SessionNormalizer.kt",
    "android/app/src/main/java/com/example/apphear/pipeline/recognition/SigningDetector.kt",
    "android/app/src/main/java/com/example/apphear/pipeline/recognition/Recognizer.kt",
    "android/app/src/main/java/com/example/apphear/pipeline/recognition/Confirmation.kt",
    "android/app/src/main/assets/recognition_config.json",
    "android/app/src/main/assets/model_manifest.json",
    "android/app/src/main/assets/streaming.tflite",
    "android/app/src/main/assets/vocab.json",
    "android/app/src/main/assets/mediapipe/hand_landmarker.task",
    "android/app/src/main/assets/mediapipe/pose_landmarker_lite.task",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json_lines(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _evidence_images(bundle: Path) -> dict[int, Path]:
    result: dict[int, Path] = {}
    for image in sorted((bundle / "evidence").glob("frame_*.jpg")):
        match = FRAME_RE.search(image.name)
        if match:
            result[int(match.group(1))] = image
    return result


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _selected_frame_ids(
    available: list[int], onset: int, release: int, padding: int, rest_per_edge: int
) -> set[int]:
    selected = {frame for frame in available if onset - padding <= frame <= release + padding}
    selected.update(available[:rest_per_edge])
    selected.update(available[-rest_per_edge:])
    return selected


def _a1_sequences() -> list[dict[str, Any]]:
    annotations = {row["attempt_id"]: row for row in _read_csv(A1_ROOT / "annotations.csv")}
    sequences: list[dict[str, Any]] = []
    for bundle in sorted((A1_ROOT / "session_bundles").iterdir()):
        if not bundle.is_dir():
            continue
        metadata = json.loads((bundle / "metadata.json").read_text(encoding="utf-8"))
        if not str(metadata.get("session_id", "")).endswith("_a1"):
            continue
        annotation = annotations[metadata["attempt_id"]]
        sequences.append(
            {
                "cohort": "PRIMARY_A1",
                "bundle": bundle,
                "metadata": metadata,
                "onset": int(annotation["onset_frame"]),
                "release": int(annotation["release_frame"]),
                "historical_cause": "A1_SIGNING_SENTINEL",
            }
        )
    return sequences


def _ru_d9_sequences() -> list[dict[str, Any]]:
    annotations = {
        int(row["capture_order"]): row for row in _read_csv(RU_D7_ROOT / "annotations.csv")
    }
    root_causes = _read_csv(RU_D7_ROOT / "reports/ru_d9/ru_d9_attempt_root_cause.csv")
    sequences: list[dict[str, Any]] = []
    for cause in root_causes:
        capture_order = int(cause["capture_order"])
        annotation = annotations[capture_order]
        bundle = RU_D7_ROOT / "phone_bundles" / annotation["attempt_id"]
        metadata = json.loads((bundle / "metadata.json").read_text(encoding="utf-8"))
        sequences.append(
            {
                "cohort": "SUPPLEMENTAL_RU_D9",
                "bundle": bundle,
                "metadata": metadata,
                "onset": int(annotation["onset_frame"]),
                "release": int(annotation["release_frame"]),
                "historical_cause": cause["primary_root_cause"],
            }
        )
    return sequences


def _draw_points(
    canvas: np.ndarray,
    points: np.ndarray,
    color: tuple[int, int, int],
    bounds: tuple[float, float, float, float],
    edges: tuple[tuple[int, int], ...],
) -> None:
    x_min, y_min, x_max, y_max = bounds
    height, width = canvas.shape[:2]

    def pixel(point: np.ndarray) -> tuple[int, int]:
        x = int(24 + (point[0] - x_min) / max(x_max - x_min, 1e-6) * (width - 48))
        y = int(46 + (point[1] - y_min) / max(y_max - y_min, 1e-6) * (height - 80))
        return x, y

    for first, second in edges:
        cv2.line(canvas, pixel(points[first]), pixel(points[second]), color, 2)
    for point in points:
        cv2.circle(canvas, pixel(point), 3, color, -1)


HAND_EDGES = tuple(
    (chain[index], chain[index + 1])
    for chain in ((0, 1, 2, 3, 4), (0, 5, 6, 7, 8), (0, 9, 10, 11, 12),
                  (0, 13, 14, 15, 16), (0, 17, 18, 19, 20))
    for index in range(len(chain) - 1)
)
POSE_EDGES = ((11, 12), (11, 13), (13, 15), (12, 14), (14, 16))


def _render_panel(image_path: Path, trace: dict[str, Any], output_path: Path, title: str) -> None:
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"cannot read evidence image: {image_path}")
    target_h = 720
    scale = min(760 / image.shape[1], target_h / image.shape[0])
    resized = cv2.resize(image, (int(image.shape[1] * scale), int(image.shape[0] * scale)))
    frame = np.full((target_h, 800, 3), 24, dtype=np.uint8)
    x0 = (800 - resized.shape[1]) // 2
    y0 = (target_h - resized.shape[0]) // 2
    frame[y0 : y0 + resized.shape[0], x0 : x0 + resized.shape[1]] = resized

    plot = np.full((target_h, 400, 3), 20, dtype=np.uint8)
    feature = np.asarray(trace["feature"], dtype=np.float64)
    pose = feature[126:].reshape(33, 4)[:, :2]
    hands = [feature[:63].reshape(21, 3)[:, :2], feature[63:126].reshape(21, 3)[:, :2]]
    present = [np.any(hand != 0.0) for hand in hands]
    point_sets = [pose[[11, 12, 13, 14, 15, 16]]]
    point_sets.extend(hand for hand, exists in zip(hands, present, strict=True) if exists)
    all_points = np.concatenate(point_sets, axis=0)
    x_min, y_min = np.nanmin(all_points, axis=0)
    x_max, y_max = np.nanmax(all_points, axis=0)
    padding = 0.15
    bounds = (x_min - padding, y_min - padding, x_max + padding, y_max + padding)
    _draw_points(plot, pose, (180, 180, 180), bounds, POSE_EDGES)
    if present[0]:
        _draw_points(plot, hands[0], (255, 160, 40), bounds, HAND_EDGES)
    if present[1]:
        _draw_points(plot, hands[1], (40, 180, 255), bounds, HAND_EDGES)
    cv2.putText(plot, "BLUE DETECTION", (18, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.52,
                (255, 160, 40), 2, cv2.LINE_AA)
    cv2.putText(plot, "ORANGE DETECTION", (210, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.48,
                (40, 180, 255), 2, cv2.LINE_AA)
    cv2.putText(plot, title[:42], (18, 705), cv2.FONT_HERSHEY_SIMPLEX, 0.48,
                (235, 235, 235), 1, cv2.LINE_AA)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), np.concatenate((frame, plot), axis=1)):
        raise RuntimeError(f"failed to write panel: {output_path}")


def prepare(config_path: Path, output_dir: Path) -> dict[str, Any]:
    annotation_path = output_dir / "annotations.csv"
    if annotation_path.exists():
        raise FileExistsError(
            f"refusing to overwrite existing human-review state: {annotation_path}"
        )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    selection = config["selection"]
    sequences = _a1_sequences()
    if selection["include_ru_d9_supplement"]:
        sequences.extend(_ru_d9_sequences())

    index_rows: list[dict[str, Any]] = []
    annotation_rows: list[dict[str, Any]] = []
    sequence_rows: list[dict[str, Any]] = []
    for sequence in sequences:
        bundle: Path = sequence["bundle"]
        metadata = sequence["metadata"]
        trace_path = bundle / "trace.jsonl"
        traces = {int(row["frame_id"]): row for row in _load_json_lines(trace_path)}
        images = _evidence_images(bundle)
        available = sorted(set(traces) & set(images))
        selected = _selected_frame_ids(
            available,
            sequence["onset"],
            sequence["release"],
            int(selection["sign_span_padding_observations"]),
            int(selection["rest_observations_per_edge"]),
        )
        selected_ids = sorted(selected)
        sequence_rows.append(
            {
                "cohort": sequence["cohort"],
                "attempt_id": metadata["attempt_id"],
                "gloss": metadata["ground_truth"],
                "repetition_id": metadata.get("repetition_id", ""),
                "expected_hands": metadata["expected_hands"],
                "onset_frame": sequence["onset"],
                "release_frame": sequence["release"],
                "selected_frames": len(selected_ids),
                "historical_cause": sequence["historical_cause"],
            }
        )
        for frame_id in selected_ids:
            trace = traces[frame_id]
            sample_id = f"{sequence['cohort']}__{metadata['attempt_id']}__{frame_id:06d}"
            panel_path = output_dir / "panels" / f"{sample_id}.jpg"
            title = (
                f"{metadata['ground_truth']} {metadata.get('repetition_id', '')} frame={frame_id} "
                f"L={trace['left_hand_present']} R={trace['right_hand_present']}"
            )
            _render_panel(images[frame_id], trace, panel_path, title)
            index_rows.append(
                {
                    "sample_id": sample_id,
                    "cohort": sequence["cohort"],
                    "attempt_id": metadata["attempt_id"],
                    "gloss": metadata["ground_truth"],
                    "repetition_id": metadata.get("repetition_id", ""),
                    "expected_hands": metadata["expected_hands"],
                    "frame_id": frame_id,
                    "timestamp_ns": trace["timestamp_ns"],
                    "in_sign_span": str(
                        sequence["onset"] <= frame_id <= sequence["release"]
                    ).lower(),
                    "direct_mp_left": str(bool(trace["left_hand_present"])).lower(),
                    "direct_mp_right": str(bool(trace["right_hand_present"])).lower(),
                    "image_path": _relative(images[frame_id]),
                    "panel_path": _relative(panel_path),
                    "source_trace_path": _relative(trace_path),
                }
            )
            annotation_rows.append(
                {
                    "sample_id": sample_id,
                    "review_status": "unreviewed",
                    "visible_left": "uncertain",
                    "visible_right": "uncertain",
                    "mp_left_identity": "ambiguous" if trace["left_hand_present"] else "none",
                    "mp_right_identity": "ambiguous" if trace["right_hand_present"] else "none",
                    "recoverable_left": "not_applicable",
                    "recoverable_right": "not_applicable",
                    "hand_hand_contact": "no",
                    "hand_body_contact": "no",
                    "crossing_or_midline": "no",
                    "leaving_frame": "no",
                    "no_hand_rest": "no",
                    "notes": "",
                }
            )

    _write_csv(output_dir / "internal_index.csv", INDEX_FIELDS, index_rows)
    _write_csv(annotation_path, ANNOTATION_FIELDS, annotation_rows)
    sequence_fields = tuple(sequence_rows[0])
    _write_csv(output_dir / "sequence_manifest.csv", sequence_fields, sequence_rows)
    hashes = []
    for relative in HASH_FILES:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(f"frozen baseline file missing: {path}")
        hashes.append({"path": relative, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    _write_json(
        output_dir / "baseline_freeze.json",
        {
            "experiment_id": config["experiment_id"],
            "config_path": _relative(config_path),
            "config_sha256": _sha256(config_path),
            "protected_files": hashes,
        },
    )
    cohort_counts = Counter(row["cohort"] for row in index_rows)
    summary = {
        "experiment_id": config["experiment_id"],
        "sequences": len(sequence_rows),
        "frames": len(index_rows),
        "cohort_frames": dict(sorted(cohort_counts.items())),
        "glosses": sorted({row["gloss"] for row in sequence_rows}),
        "annotations_complete": False,
        "a2_1_evaluation_allowed": False,
    }
    _write_json(output_dir / "prepare_summary.json", summary)
    return summary


def _load_package(output_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    return _read_csv(output_dir / "internal_index.csv"), _read_csv(output_dir / "annotations.csv")


def correct_color_review_semantics(config_path: Path, output_dir: Path) -> dict[str, Any]:
    """Replace detector-side guesses with neutral color-coded human review."""
    index_rows, annotation_rows = _load_package(output_dir)
    accepted = [row["sample_id"] for row in annotation_rows if row["review_status"] == "accepted"]
    backup_path = output_dir / "annotations_before_color_ui_correction.csv"
    if backup_path.exists():
        raise RuntimeError(
            "color-review correction was already applied; refusing to overwrite its backup"
        )
    _write_csv(backup_path, ANNOTATION_FIELDS, annotation_rows)
    annotations = {row["sample_id"]: row for row in annotation_rows}
    trace_cache: dict[Path, dict[int, dict[str, Any]]] = {}
    mirrored_counts: Counter[bool] = Counter()
    for index_row in index_rows:
        annotation = annotations[index_row["sample_id"]]
        annotation["review_status"] = "unreviewed"
        annotation["visible_left"] = "uncertain"
        annotation["visible_right"] = "uncertain"
        annotation["mp_left_identity"] = (
            "ambiguous" if index_row["direct_mp_left"] == "true" else "none"
        )
        annotation["mp_right_identity"] = (
            "ambiguous" if index_row["direct_mp_right"] == "true" else "none"
        )
        annotation["recoverable_left"] = "not_applicable"
        annotation["recoverable_right"] = "not_applicable"
        for field in (
            "hand_hand_contact",
            "hand_body_contact",
            "crossing_or_midline",
            "leaving_frame",
            "no_hand_rest",
        ):
            annotation[field] = "no"
        annotation["notes"] = ""
        trace_path = ROOT / index_row["source_trace_path"]
        if trace_path not in trace_cache:
            trace_cache[trace_path] = {
                int(row["frame_id"]): row for row in _load_json_lines(trace_path)
            }
        trace = trace_cache[trace_path][int(index_row["frame_id"])]
        mirrored_counts[bool(trace.get("mirrored", False))] += 1
        title = (
            f"{index_row['gloss']} {index_row['repetition_id']} frame={index_row['frame_id']} "
            f"blue={trace['left_hand_present']} orange={trace['right_hand_present']}"
        )
        _render_panel(
            ROOT / index_row["image_path"],
            trace,
            ROOT / index_row["panel_path"],
            title,
        )
    if mirrored_counts[True]:
        raise RuntimeError(
            "selected evidence contains S4-mirrored frames; a single inverted slot prior is unsafe"
        )
    _write_csv(output_dir / "annotations.csv", ANNOTATION_FIELDS, annotation_rows)
    freeze_path = output_dir / "baseline_freeze.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    freeze["config_sha256"] = _sha256(config_path)
    freeze["identity_semantics"] = {
        "camera_evidence_orientation": "unmirrored_front_camera",
        "selected_trace_mirrored_true": mirrored_counts[True],
        "selected_trace_mirrored_false": mirrored_counts[False],
        "human_truth_perspective": "signer_anatomical",
        "human_review_slot_names": {"mp_left": "blue", "mp_right": "orange"},
        "detected_slot_identity_default": "ambiguous",
        "detector_label_used_as_human_truth": False,
    }
    _write_json(freeze_path, freeze)
    result = {
        "rows": len(index_rows),
        "accepted_rows_before_correction": len(accepted),
        "accepted_rows_reset_for_rereview": len(accepted),
        "annotation_backup": _relative(backup_path),
        "panels_refreshed": len(index_rows),
        "trace_mirrored_false": mirrored_counts[False],
        "trace_mirrored_true": mirrored_counts[True],
        "human_review_mapping": {"mp_left": "blue", "mp_right": "orange"},
        "identity_default_for_detected_slots": "ambiguous",
        "passed": mirrored_counts[True] == 0,
    }
    _write_json(output_dir / "color_ui_correction.json", result)
    return result


def _annotation_error(row: dict[str, str], index: dict[str, str]) -> str | None:
    if row["review_status"] != "accepted":
        return "review_status is not accepted"
    if (
        row["visible_left"] not in VISIBILITY_VALUES
        or row["visible_right"] not in VISIBILITY_VALUES
    ):
        return "visible hand fields must be yes/no/uncertain"
    if row["mp_left_identity"] not in IDENTITY_VALUES:
        return "mp_left_identity is invalid"
    if row["mp_right_identity"] not in IDENTITY_VALUES:
        return "mp_right_identity is invalid"
    if row["recoverable_left"] not in RECOVERABILITY_VALUES:
        return "recoverable_left is invalid"
    if row["recoverable_right"] not in RECOVERABILITY_VALUES:
        return "recoverable_right is invalid"
    for field in (
        "hand_hand_contact",
        "hand_body_contact",
        "crossing_or_midline",
        "leaving_frame",
        "no_hand_rest",
    ):
        if row[field] not in BOOL_VALUES:
            return f"{field} must be yes/no"
    direct_left = index["direct_mp_left"] == "true"
    direct_right = index["direct_mp_right"] == "true"
    if direct_left != (row["mp_left_identity"] != "none"):
        return "mp_left_identity must be none exactly when the direct slot is absent"
    if direct_right != (row["mp_right_identity"] != "none"):
        return "mp_right_identity must be none exactly when the direct slot is absent"
    known = [value for value in (row["mp_left_identity"], row["mp_right_identity"])
             if value in {"left", "right"}]
    if len(known) != len(set(known)):
        return "both direct slots cannot be assigned to the same anatomical hand"
    if row["visible_left"] != "yes" and row["recoverable_left"] == "yes":
        return "an invisible left hand cannot be recoverable"
    if row["visible_right"] != "yes" and row["recoverable_right"] == "yes":
        return "an invisible right hand cannot be recoverable"
    detected_left = "left" in (row["mp_left_identity"], row["mp_right_identity"])
    detected_right = "right" in (row["mp_left_identity"], row["mp_right_identity"])
    left_missing_visible = row["visible_left"] == "yes" and not detected_left
    right_missing_visible = row["visible_right"] == "yes" and not detected_right
    if left_missing_visible == (row["recoverable_left"] == "not_applicable"):
        return "recoverable_left is required exactly when a visible left hand is not detected"
    if right_missing_visible == (row["recoverable_right"] == "not_applicable"):
        return "recoverable_right is required exactly when a visible right hand is not detected"
    if row["no_hand_rest"] == "yes" and (
        row["visible_left"] != "no" or row["visible_right"] != "no"
    ):
        return "no_hand_rest requires both anatomical hands to be not visible"
    return None


def check(output_dir: Path, require_complete: bool = False) -> dict[str, Any]:
    index_rows, annotations = _load_package(output_dir)
    index = {row["sample_id"]: row for row in index_rows}
    errors: list[str] = []
    if len(index) != len(index_rows):
        errors.append("internal_index.csv contains duplicate sample_id values")
    seen: set[str] = set()
    completed = 0
    for number, row in enumerate(annotations, start=2):
        sample_id = row["sample_id"]
        if sample_id in seen:
            errors.append(f"annotations.csv:{number}: duplicate sample_id {sample_id}")
        seen.add(sample_id)
        metadata = index.get(sample_id)
        if metadata is None:
            errors.append(f"annotations.csv:{number}: unknown sample_id {sample_id}")
            continue
        error = _annotation_error(row, metadata)
        if error is None:
            completed += 1
        elif row["review_status"] == "accepted" or require_complete:
            errors.append(f"annotations.csv:{number}: {error}")
        for field in ("image_path", "panel_path", "source_trace_path"):
            if not (ROOT / metadata[field]).is_file():
                errors.append(f"annotations.csv:{number}: missing {field}: {metadata[field]}")
    if seen != set(index):
        errors.append(f"annotation/index sample mismatch: {len(seen)} vs {len(index)}")
    result = {
        "rows": len(index_rows),
        "completed": completed,
        "remaining": len(index_rows) - completed,
        "errors": errors,
        "passed": not errors and (not require_complete or completed == len(index_rows)),
    }
    _write_json(output_dir / "check_report.json", result)
    return result


def review(output_dir: Path) -> None:
    """Open the resumable human-review UI for the frozen A2-0 evidence package."""
    import tkinter as tk
    from tkinter import messagebox, ttk

    from PIL import Image, ImageTk

    index_rows, annotation_rows = _load_package(output_dir)
    if not index_rows:
        raise ValueError(f"empty A2-0 package: {output_dir}")
    by_sample = {row["sample_id"]: row for row in annotation_rows}
    if set(by_sample) != {row["sample_id"] for row in index_rows}:
        raise ValueError("annotation/index sample mismatch; run Check for details")

    root = tk.Tk()
    root.title("AppHear A2-0 anatomical hand review")
    root.geometry("1540x980")
    root.minsize(1180, 760)
    style = ttk.Style(root)
    style.configure("Step.TLabel", font=("Segoe UI", 10, "bold"), foreground="#124b73")
    style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 7))
    position = tk.IntVar(value=0)
    photo: ImageTk.PhotoImage | None = None
    status = tk.StringVar()
    metadata_text = tk.StringVar()
    fields = {
        "visible_left": tk.StringVar(),
        "visible_right": tk.StringVar(),
        "mp_left_identity": tk.StringVar(),
        "mp_right_identity": tk.StringVar(),
        "recoverable_left": tk.StringVar(),
        "recoverable_right": tk.StringVar(),
        "hand_hand_contact": tk.StringVar(),
        "hand_body_contact": tk.StringVar(),
        "crossing_or_midline": tk.StringVar(),
        "leaving_frame": tk.StringVar(),
        "no_hand_rest": tk.StringVar(),
    }

    image_label = ttk.Label(root)
    image_label.grid(row=0, column=0, rowspan=20, padx=10, pady=10, sticky="n")
    controls = ttk.Frame(root, padding=10)
    controls.grid(row=0, column=1, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=0)
    root.rowconfigure(0, weight=1)
    ttk.Label(controls, textvariable=status, font=("Segoe UI", 11, "bold")).grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 6)
    )
    ttk.Label(controls, textvariable=metadata_text, wraplength=370).grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(0, 12)
    )
    ttk.Label(
        controls,
        text=(
            "Answer only about YOUR own left and right hands. Ignore where a hand appears on the "
            "screen."
        ),
        wraplength=390,
        foreground="#9a2f00",
        font=("Segoe UI", 10, "bold"),
    ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 4))
    ttk.Label(
        controls,
        text=(
            "Review in four steps: what is visible → which of YOUR hands the detector found → "
            "whether a visible missing hand is recoverable → special circumstances."
        ),
        wraplength=390,
    ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 12))

    combo_specs = (
        ("Can you see YOUR LEFT hand?", "visible_left", ("yes", "no", "uncertain")),
        ("Can you see YOUR RIGHT hand?", "visible_right", ("yes", "no", "uncertain")),
        (
            "BLUE detected skeleton is YOUR",
            "mp_left_identity",
            ("left", "right", "ambiguous"),
        ),
        (
            "ORANGE detected skeleton is YOUR",
            "mp_right_identity",
            ("left", "right", "ambiguous"),
        ),
        (
            "Visible LEFT missing: safely recoverable?",
            "recoverable_left",
            ("yes", "no", "uncertain"),
        ),
        (
            "Visible RIGHT missing: safely recoverable?",
            "recoverable_right",
            ("yes", "no", "uncertain"),
        ),
    )
    section_labels = {
        0: "STEP 1 — What hands can you actually see?",
        2: "STEP 2 — Match each COLORED skeleton to YOUR hand",
        4: "STEP 3 — Only when a visible hand was missed",
    }
    section_help = {
        0: "Choose uncertain only when the camera image is genuinely unclear.",
        2: (
            "Use only the skeleton color shown in the middle panel. Colors do not mean left or "
            "right. Choose ambiguous when you cannot identify the hand safely."
        ),
        4: (
            "These controls are automatic. Answer only if a visible hand has no identified "
            "skeleton."
        ),
    }
    combo_widgets: dict[str, ttk.Combobox] = {}
    row_number = 4
    for index, (label, field, values) in enumerate(combo_specs):
        if index in section_labels:
            ttk.Separator(controls).grid(
                row=row_number, column=0, columnspan=2, sticky="ew", pady=(7, 6)
            )
            row_number += 1
            ttk.Label(controls, text=section_labels[index], style="Step.TLabel").grid(
                row=row_number, column=0, columnspan=2, sticky="w"
            )
            row_number += 1
            ttk.Label(
                controls, text=section_help[index], wraplength=390, foreground="#555555"
            ).grid(row=row_number, column=0, columnspan=2, sticky="w", pady=(0, 4))
            row_number += 1
        ttk.Label(controls, text=label).grid(row=row_number, column=0, sticky="w", pady=3)
        combo = ttk.Combobox(
            controls,
            textvariable=fields[field],
            values=values,
            state="readonly",
            width=18,
        )
        combo.grid(row=row_number, column=1, sticky="ew", pady=3)
        combo_widgets[field] = combo
        row_number += 1

    ttk.Separator(controls).grid(
        row=row_number, column=0, columnspan=2, sticky="ew", pady=(8, 6)
    )
    row_number += 1
    ttk.Label(controls, text="STEP 4 — Does anything special happen?", style="Step.TLabel").grid(
        row=row_number, column=0, columnspan=2, sticky="w", pady=(0, 4)
    )
    row_number += 1
    check_specs = (
        ("Hands touch or overlap", "hand_hand_contact"),
        ("A hand touches/overlaps the body", "hand_body_contact"),
        ("Hands cross or identity is difficult", "crossing_or_midline"),
        ("A hand is leaving the camera view", "leaving_frame"),
        ("No hands visible (rest frame)", "no_hand_rest"),
    )
    for label, field in check_specs:
        ttk.Checkbutton(
            controls,
            text=label,
            variable=fields[field],
            onvalue="yes",
            offvalue="no",
        ).grid(row=row_number, column=0, columnspan=2, sticky="w", pady=3)
        row_number += 1

    ttk.Label(controls, text="Notes").grid(row=row_number, column=0, sticky="w", pady=(8, 2))
    row_number += 1
    notes = tk.Text(controls, width=44, height=5, wrap="word")
    notes.grid(row=row_number, column=0, columnspan=2, sticky="ew")
    row_number += 1
    ttk.Label(
        controls,
        text=(
            "BLUE and ORANGE are only colors. They never mean anatomical left/right and they are "
            "not screen columns. Match the colored skeleton to your actual hand in the photo."
        ),
        wraplength=370,
        foreground="#7a3e00",
    ).grid(row=row_number, column=0, columnspan=2, sticky="w", pady=10)
    row_number += 1

    def current() -> tuple[dict[str, str], dict[str, str]]:
        index_row = index_rows[position.get()]
        return index_row, by_sample[index_row["sample_id"]]

    def sync_recovery_controls(_event: object | None = None) -> None:
        identified = {
            fields["mp_left_identity"].get(),
            fields["mp_right_identity"].get(),
        }
        for side in ("left", "right"):
            field = f"recoverable_{side}"
            visible_missing = fields[f"visible_{side}"].get() == "yes" and side not in identified
            if visible_missing:
                if fields[field].get() == "not_applicable":
                    fields[field].set("uncertain")
                combo_widgets[field].configure(state="readonly")
            else:
                fields[field].set("not_applicable")
                combo_widgets[field].configure(state="disabled")

    def load_current() -> None:
        nonlocal photo
        index_row, annotation = current()
        panel = Image.open(ROOT / index_row["panel_path"])
        panel.thumbnail((1040, 900), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(panel)
        image_label.configure(image=photo)
        for field, variable in fields.items():
            variable.set(annotation[field])
        left_direct = index_row["direct_mp_left"] == "true"
        right_direct = index_row["direct_mp_right"] == "true"
        combo_widgets["mp_left_identity"].configure(
            state="readonly" if left_direct else "disabled"
        )
        combo_widgets["mp_right_identity"].configure(
            state="readonly" if right_direct else "disabled"
        )
        sync_recovery_controls()
        preset_button.configure(
            state="normal" if not left_direct and not right_direct else "disabled"
        )
        notes.delete("1.0", "end")
        notes.insert("1.0", annotation["notes"])
        accepted = sum(row["review_status"] == "accepted" for row in annotation_rows)
        status.set(
            f"Frame {position.get() + 1}/{len(index_rows)} | accepted {accepted} | "
            f"status={annotation['review_status']}"
        )
        metadata_text.set(
            f"{index_row['cohort']}  {index_row['gloss']}  rep={index_row['repetition_id']}\n"
            f"attempt={index_row['attempt_id']}  frame={index_row['frame_id']}  "
            f"in_sign={index_row['in_sign_span']}\n"
            f"colored detections: BLUE={index_row['direct_mp_left']} "
            f"ORANGE={index_row['direct_mp_right']}"
        )

    def save(mark_accepted: bool = True) -> bool:
        index_row, annotation = current()
        sync_recovery_controls()
        for field, variable in fields.items():
            annotation[field] = variable.get()
        annotation["notes"] = notes.get("1.0", "end-1c").strip()
        annotation["review_status"] = "accepted" if mark_accepted else "unreviewed"
        error = _annotation_error(annotation, index_row) if mark_accepted else None
        if error:
            annotation["review_status"] = "unreviewed"
            messagebox.showerror("Cannot accept frame", error)
            return False
        _write_csv(output_dir / "annotations.csv", ANNOTATION_FIELDS, annotation_rows)
        return True

    def move(delta: int) -> None:
        position.set(max(0, min(len(index_rows) - 1, position.get() + delta)))
        load_current()

    def save_next(_event: object | None = None) -> None:
        if save() and position.get() < len(index_rows) - 1:
            move(1)
        else:
            load_current()

    def set_no_hand_rest() -> None:
        fields["visible_left"].set("no")
        fields["visible_right"].set("no")
        fields["mp_left_identity"].set("none")
        fields["mp_right_identity"].set("none")
        fields["recoverable_left"].set("not_applicable")
        fields["recoverable_right"].set("not_applicable")
        for field in (
            "hand_hand_contact",
            "hand_body_contact",
            "crossing_or_midline",
            "leaving_frame",
        ):
            fields[field].set("no")
        fields["no_hand_rest"].set("yes")
        sync_recovery_controls()

    for field in (
        "visible_left",
        "visible_right",
        "mp_left_identity",
        "mp_right_identity",
    ):
        combo_widgets[field].bind("<<ComboboxSelected>>", sync_recovery_controls)

    preset_button = ttk.Button(
        controls,
        text="Quick fill: No hands / rest",
        command=set_no_hand_rest,
    )
    preset_button.grid(row=row_number, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    row_number += 1
    buttons = ttk.Frame(controls)
    buttons.grid(row=row_number, column=0, columnspan=2, sticky="ew")
    ttk.Button(buttons, text="← Back", command=lambda: move(-1)).grid(row=0, column=0, padx=3)
    ttk.Button(
        buttons,
        text="SAVE FRAME →  (Ctrl+S)",
        command=save_next,
        style="Primary.TButton",
    ).grid(
        row=0, column=1, padx=3
    )
    ttk.Button(buttons, text="Skip for now →", command=lambda: move(1)).grid(
        row=0, column=2, padx=3
    )
    row_number += 1
    ttk.Label(
        controls,
        text="SAVE FRAME records your answer. Skip moves forward without accepting it.",
        wraplength=390,
        foreground="#555555",
    ).grid(row=row_number, column=0, columnspan=2, sticky="w", pady=(6, 0))
    root.bind("<Control-s>", save_next)
    root.bind("<Left>", lambda _event: move(-1))
    root.bind("<Right>", lambda _event: move(1))
    first_unreviewed = next(
        (index for index, row in enumerate(annotation_rows) if row["review_status"] != "accepted"),
        0,
    )
    position.set(first_unreviewed)
    load_current()
    root.mainloop()


def _slot_truth(annotation: dict[str, str]) -> dict[MediaPipeSlot, str]:
    return {
        MediaPipeSlot.LEFT: annotation["mp_left_identity"],
        MediaPipeSlot.RIGHT: annotation["mp_right_identity"],
    }


def _prediction_by_slot(assignment: Any) -> dict[MediaPipeSlot, str]:
    result: dict[MediaPipeSlot, str] = {}
    if assignment.left is not None:
        result[assignment.left.slot] = "left"
    if assignment.right is not None:
        result[assignment.right.slot] = "right"
    for slot in assignment.ambiguous_slots:
        result[slot] = "ambiguous"
    return result


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=np.float64), percentile))


def _evaluate_cohort(rows: list[dict[str, Any]]) -> dict[str, Any]:
    known_instances = 0
    baseline_correct = baseline_wrong = 0
    tracker_correct = tracker_wrong = tracker_ambiguous = 0
    new_tracker_errors = 0
    baseline_errors_fixed = 0
    baseline_switches = tracker_switches = 0
    duration_ns = 0
    previous_baseline: dict[tuple[str, str], str] = {}
    previous_tracker: dict[tuple[str, str], str] = {}
    visible_instances = detected_instances = 0
    visible_frames = covered_frames = 0
    two_visible_frames = two_covered_frames = 0
    false_presence_frames = 0
    dropout_runs: list[int] = []
    direct_gaps_ms: list[float] = []
    last_direct: dict[tuple[str, str], int] = {}
    active_dropout: dict[tuple[str, str], int] = defaultdict(int)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["attempt_id"]].append(row)
    for attempt_id, sequence in grouped.items():
        sequence.sort(key=lambda row: row["timestamp_ns"])
        duration_ns += max(0, sequence[-1]["timestamp_ns"] - sequence[0]["timestamp_ns"])
        for row in sequence:
            annotation = row["annotation"]
            truth = row["slot_truth"]
            tracker_prediction = row["tracker_prediction"]
            baseline_prediction = {MediaPipeSlot.LEFT: "left", MediaPipeSlot.RIGHT: "right"}
            for slot, anatomical in truth.items():
                if anatomical not in {"left", "right"}:
                    continue
                known_instances += 1
                baseline_value = baseline_prediction[slot]
                tracker_value = tracker_prediction.get(slot, "ambiguous")
                baseline_ok = baseline_value == anatomical
                tracker_ok = tracker_value == anatomical
                baseline_correct += int(baseline_ok)
                baseline_wrong += int(not baseline_ok)
                tracker_correct += int(tracker_ok)
                tracker_wrong += int(tracker_value in {"left", "right"} and not tracker_ok)
                tracker_ambiguous += int(tracker_value == "ambiguous")
                new_tracker_errors += int(baseline_ok and tracker_value in {"left", "right"}
                                          and not tracker_ok)
                baseline_errors_fixed += int(not baseline_ok and tracker_ok)
                key = (attempt_id, anatomical)
                if key in previous_baseline and previous_baseline[key] != baseline_value:
                    baseline_switches += 1
                previous_baseline[key] = baseline_value
                if tracker_value in {"left", "right"}:
                    if key in previous_tracker and previous_tracker[key] != tracker_value:
                        tracker_switches += 1
                    previous_tracker[key] = tracker_value

            visible = {
                "left": annotation["visible_left"] == "yes",
                "right": annotation["visible_right"] == "yes",
            }
            detected = {
                side: any(value == side for value in truth.values()) for side in ("left", "right")
            }
            visible_instances += sum(visible.values())
            detected_instances += sum(visible[side] and detected[side] for side in visible)
            if any(visible.values()):
                visible_frames += 1
                covered_frames += int(any(detected.values()))
            if all(visible.values()):
                two_visible_frames += 1
                two_covered_frames += int(all(detected.values()))
            direct_exists = any(value != "none" for value in truth.values())
            false_presence_frames += int(not any(visible.values()) and direct_exists)
            for side in ("left", "right"):
                key = (attempt_id, side)
                if visible[side] and not detected[side]:
                    active_dropout[key] += 1
                elif active_dropout[key]:
                    dropout_runs.append(active_dropout.pop(key))
                if detected[side]:
                    previous_ns = last_direct.get(key)
                    if previous_ns is not None:
                        direct_gaps_ms.append((row["timestamp_ns"] - previous_ns) / 1_000_000.0)
                    last_direct[key] = row["timestamp_ns"]
        for side in ("left", "right"):
            key = (attempt_id, side)
            if active_dropout[key]:
                dropout_runs.append(active_dropout.pop(key))

    minutes = duration_ns / 60_000_000_000.0
    assigned = tracker_correct + tracker_wrong
    return {
        "frames": len(rows),
        "sequences": len(grouped),
        "duration_minutes": minutes,
        "visible_hand_instance_recall": (
            detected_instances / visible_instances if visible_instances else None
        ),
        "any_hand_coverage": covered_frames / visible_frames if visible_frames else None,
        "complete_two_hand_coverage": (
            two_covered_frames / two_visible_frames if two_visible_frames else None
        ),
        "false_presence_frames": false_presence_frames,
        "dropout_run_observations": {
            "count": len(dropout_runs),
            "p50": _percentile([float(value) for value in dropout_runs], 50),
            "p95": _percentile([float(value) for value in dropout_runs], 95),
            "max": max(dropout_runs, default=None),
            "distribution": dict(sorted(Counter(dropout_runs).items())),
        },
        "direct_observation_gap_ms": {
            "p50": _percentile(direct_gaps_ms, 50),
            "p95": _percentile(direct_gaps_ms, 95),
        },
        "known_direct_instances": known_instances,
        "baseline": {
            "correct": baseline_correct,
            "incorrect": baseline_wrong,
            "handedness_disagreement_rate": (
                baseline_wrong / known_instances if known_instances else None
            ),
            "identity_switches": baseline_switches,
            "identity_switches_per_minute": baseline_switches / minutes if minutes else None,
        },
        "tracker": {
            "correct": tracker_correct,
            "incorrect": tracker_wrong,
            "ambiguous": tracker_ambiguous,
            "assignment_coverage": assigned / known_instances if known_instances else None,
            "identity_error_rate": tracker_wrong / known_instances if known_instances else None,
            "ambiguous_assignment_rate": (
                tracker_ambiguous / known_instances if known_instances else None
            ),
            "identity_switches": tracker_switches,
            "identity_switches_per_minute": tracker_switches / minutes if minutes else None,
            "new_identity_errors": new_tracker_errors,
            "baseline_errors_fixed": baseline_errors_fixed,
        },
    }


def evaluate(config_path: Path, output_dir: Path) -> dict[str, Any]:
    report = check(output_dir, require_complete=True)
    if not report["passed"]:
        raise RuntimeError("A2-1 evaluation is blocked until check_report.json passes completely")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    tracker_config = IdentityConfig(**config["tracker"])
    index_rows, annotation_rows = _load_package(output_dir)
    annotations = {row["sample_id"]: row for row in annotation_rows}
    trace_cache: dict[Path, dict[int, dict[str, Any]]] = {}
    by_attempt: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in index_rows:
        by_attempt[row["attempt_id"]].append(row)

    evaluation_rows: list[dict[str, Any]] = []
    frame_output_rows: list[dict[str, Any]] = []
    for attempt_id, rows in by_attempt.items():
        tracker = AnatomicalIdentityTracker(tracker_config)
        for row in sorted(rows, key=lambda value: int(value["timestamp_ns"])):
            trace_path = ROOT / row["source_trace_path"]
            if trace_path not in trace_cache:
                trace_cache[trace_path] = {
                    int(value["frame_id"]): value for value in _load_json_lines(trace_path)
                }
            trace = trace_cache[trace_path][int(row["frame_id"])]
            feature = np.asarray(trace["feature"], dtype=np.float64)
            timestamp_ns = int(row["timestamp_ns"])
            assignment = tracker.update(
                timestamp_ns,
                observations_from_feature(feature, timestamp_ns),
                pose_wrists_from_feature(feature),
            )
            annotation = annotations[row["sample_id"]]
            truth = _slot_truth(annotation)
            prediction = _prediction_by_slot(assignment)
            evaluation_rows.append(
                {
                    **row,
                    "timestamp_ns": timestamp_ns,
                    "annotation": annotation,
                    "slot_truth": truth,
                    "tracker_prediction": prediction,
                }
            )
            frame_output_rows.append(
                {
                    "sample_id": row["sample_id"],
                    "cohort": row["cohort"],
                    "attempt_id": attempt_id,
                    "frame_id": row["frame_id"],
                    "mp_left_truth": truth[MediaPipeSlot.LEFT],
                    "mp_right_truth": truth[MediaPipeSlot.RIGHT],
                    "mp_left_tracker": prediction.get(MediaPipeSlot.LEFT, "none"),
                    "mp_right_tracker": prediction.get(MediaPipeSlot.RIGHT, "none"),
                    "ambiguous_slots": "|".join(slot.value for slot in assignment.ambiguous_slots),
                    "assignment_margin": assignment.assignment_margin,
                    "assignment_cost": assignment.assignment_cost,
                }
            )

    cohorts = {
        cohort: _evaluate_cohort([row for row in evaluation_rows if row["cohort"] == cohort])
        for cohort in sorted({row["cohort"] for row in evaluation_rows})
    }
    combined = _evaluate_cohort(evaluation_rows)
    gates = config["preregistered_gates"]
    primary = cohorts["PRIMARY_A1"]
    baseline = primary["baseline"]
    tracker_metrics = primary["tracker"]
    baseline_error_reduction = (
        tracker_metrics["baseline_errors_fixed"] / baseline["incorrect"]
        if baseline["incorrect"]
        else None
    )
    contact_frames = sum(
        row["annotation"]["hand_hand_contact"] == "yes"
        or row["annotation"]["hand_body_contact"] == "yes"
        or row["annotation"]["crossing_or_midline"] == "yes"
        for row in evaluation_rows
        if row["cohort"] == "PRIMARY_A1"
    )
    baseline_switch_rate = baseline["identity_switches_per_minute"] or 0.0
    tracker_switch_rate = tracker_metrics["identity_switches_per_minute"] or 0.0
    identity_error_rate = tracker_metrics["identity_error_rate"]
    assignment_coverage = tracker_metrics["assignment_coverage"]
    ambiguous_assignment_rate = tracker_metrics["ambiguous_assignment_rate"]
    switch_gate = (
        tracker_switch_rate <= baseline_switch_rate * gates["maximum_identity_switch_rate_ratio"]
        if baseline_switch_rate > 0
        else tracker_switch_rate == 0
    )
    gate_results = {
        "evidence_instances": primary["known_direct_instances"]
        >= gates["minimum_known_direct_instances"],
        "contact_or_crossing_evidence": contact_frames
        >= gates["minimum_contact_or_crossing_frames"],
        "identity_error": identity_error_rate is not None
        and identity_error_rate <= gates["maximum_tracker_identity_error_rate"],
        "no_new_errors": tracker_metrics["new_identity_errors"]
        <= gates["maximum_new_identity_errors"],
        "switch_rate": switch_gate,
        "assignment_coverage": assignment_coverage is not None
        and assignment_coverage >= 1.0 - gates["maximum_assignment_coverage_drop_fraction"],
        "ambiguity": ambiguous_assignment_rate is not None
        and ambiguous_assignment_rate <= gates["maximum_ambiguous_assignment_rate"],
        "baseline_error_reduction": (
            baseline_error_reduction
            >= gates["minimum_baseline_error_reduction_fraction_when_errors_exist"]
            if baseline_error_reduction is not None
            else True
        ),
    }
    if not all(gate_results.values()):
        decision = "REJECT_A2_1_IDENTITY_TRACKER"
    elif baseline["incorrect"] == 0 and baseline["identity_switches"] == 0:
        decision = "A2_1_SAFE_BUT_BENEFIT_NOT_DEMONSTRATED"
    else:
        decision = "RETAIN_A2_1_FOR_A2_2_REVIEW"
    result = {
        "experiment_id": config["experiment_id"],
        "tracker_config": asdict(tracker_config),
        "primary_contact_or_crossing_frames": contact_frames,
        "baseline_error_reduction_fraction": baseline_error_reduction,
        "cohorts": cohorts,
        "combined": combined,
        "gates": gate_results,
        "passed": all(gate_results.values()),
        "decision": decision,
        "hard_boundary": "IDENTITY_ONLY_NO_LANDMARK_RECOVERY",
    }
    _write_csv(
        output_dir / "a2_1_frame_assignments.csv",
        tuple(frame_output_rows[0]),
        frame_output_rows,
    )
    _write_json(output_dir / "a2_1_result.json", result)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("prepare", "correct-color-ui", "review", "check", "evaluate"),
        help="A2-0/A2-1 offline workflow step",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="make check fail while any frame remains unreviewed",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config_path = args.config.resolve()
    output_dir = args.output_dir.resolve()
    if args.command == "prepare":
        result = prepare(config_path, output_dir)
    elif args.command == "correct-color-ui":
        result = correct_color_review_semantics(config_path, output_dir)
    elif args.command == "review":
        review(output_dir)
        result = check(output_dir)
    elif args.command == "check":
        result = check(output_dir, require_complete=args.require_complete)
    else:
        result = evaluate(config_path, output_dir)
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
