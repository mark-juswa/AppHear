"""Generate the bounded ASL Citizen E2e-A identity/reliability review pilot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

PILOT_FIELDS = (
    "sample_id",
    "diagnostic_group",
    "clip_id",
    "video_file",
    "participant_id",
    "split",
    "gloss",
    "frame_index",
    "timestamp_ms",
    "cadence",
    "target_hand",
    "e2d_target_detected",
    "e2d_raw_detected_hands",
    "detected_hands_json",
    "pose_wrists_json",
    "panel_path",
)

REVIEW_FIELDS = (
    "sample_id",
    "target_label_valid",
    "visible_anatomical_hands",
    "target_hand_visible",
    "detection_result",
    "identity_result",
    "notes",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def select_pilot(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    controls = [
        row for row in rows if row["label"] == "positive" and row["candidate_id"] == "image_d50_p50"
    ]
    grouped: dict[tuple[int, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in controls:
        detected = int(row["target_detected"])
        raw_hands = int(row["raw_detected_hands"])
        if detected:
            category = "control_detected"
        elif raw_hands:
            category = "target_miss_other_detected"
        else:
            category = "no_hand_detected"
        grouped[(int(row["cadence"]), row["hand"], category)].append(row)

    selected = []
    used_frames: set[tuple[str, str]] = set()
    for cadence in (1, 4, 8):
        for hand in ("left", "right"):
            for category in (
                "target_miss_other_detected",
                "no_hand_detected",
                "control_detected",
            ):
                candidates = sorted(
                    grouped[(cadence, hand, category)],
                    key=lambda row: (row["item_id"], row["clip_id"]),
                )
                if not candidates:
                    raise ValueError(f"missing pilot stratum: {cadence}/{hand}/{category}")
                candidate = next(
                    (
                        row
                        for row in candidates
                        if (row["clip_id"], row["frame_index"]) not in used_frames
                    ),
                    None,
                )
                if candidate is None:
                    raise ValueError(f"no unique pilot frame: {cadence}/{hand}/{category}")
                used_frames.add((candidate["clip_id"], candidate["frame_index"]))
                selected.append({**candidate, "diagnostic_group": category})
    return selected


class HandPoseRunner:
    def __init__(self, hand_task: Path, pose_task: Path) -> None:
        self._hand = vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(hand_task)),
                running_mode=vision.RunningMode.IMAGE,
                num_hands=2,
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        )
        self._pose = vision.PoseLandmarker.create_from_options(
            vision.PoseLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(pose_task)),
                running_mode=vision.RunningMode.IMAGE,
                num_poses=1,
                min_pose_detection_confidence=0.5,
                min_pose_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        )

    def close(self) -> None:
        self._hand.close()
        self._pose.close()

    def __enter__(self) -> HandPoseRunner:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def detect(self, frame_bgr: Any) -> tuple[list[dict[str, Any]], dict[str, dict[str, float]]]:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        hand_result = self._hand.detect(image)
        pose_result = self._pose.detect(image)
        hands = []
        for index, landmarks in enumerate(hand_result.hand_landmarks):
            handedness = hand_result.handedness[index][0]
            xs = [float(point.x) for point in landmarks]
            ys = [float(point.y) for point in landmarks]
            hands.append(
                {
                    "label": handedness.category_name.lower(),
                    "score": float(handedness.score),
                    "box": [min(xs), min(ys), max(xs), max(ys)],
                    "landmarks": [
                        {"x": float(point.x), "y": float(point.y), "z": float(point.z)}
                        for point in landmarks
                    ],
                }
            )
        wrists: dict[str, dict[str, float]] = {}
        if pose_result.pose_landmarks:
            pose = pose_result.pose_landmarks[0]
            for side, index in (("left", 15), ("right", 16)):
                wrists[side] = {
                    "x": float(pose[index].x),
                    "y": float(pose[index].y),
                    "visibility": float(pose[index].visibility),
                }
        return hands, wrists


def _frame(cap: Any, index: int) -> Any:
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = cap.read()
    if not ok:
        raise ValueError(f"could not decode frame {index}")
    return frame


def _fit(frame: Any, width: int = 240, height: int = 180) -> Any:
    scale = min(width / frame.shape[1], height / frame.shape[0])
    resized = cv2.resize(
        frame,
        (max(1, round(frame.shape[1] * scale)), max(1, round(frame.shape[0] * scale))),
        interpolation=cv2.INTER_AREA,
    )
    canvas = cv2.copyMakeBorder(
        resized,
        0,
        height - resized.shape[0],
        0,
        width - resized.shape[1],
        cv2.BORDER_CONSTANT,
        value=(20, 20, 20),
    )
    return canvas


def _annotate(
    frame: Any,
    hands: list[dict[str, Any]],
    wrists: dict[str, dict[str, float]],
) -> Any:
    output = frame.copy()
    height, width = output.shape[:2]
    colors = {"left": (80, 220, 80), "right": (80, 160, 255)}
    for hand in hands:
        label = str(hand["label"])
        x1, y1, x2, y2 = hand["box"]
        points = (
            max(0, min(width - 1, round(x1 * width))),
            max(0, min(height - 1, round(y1 * height))),
            max(0, min(width - 1, round(x2 * width))),
            max(0, min(height - 1, round(y2 * height))),
        )
        color = colors[label]
        cv2.rectangle(output, points[:2], points[2:], color, 3)
        cv2.putText(
            output,
            f"hand:{label} {hand['score']:.2f}",
            (points[0], max(24, points[1] - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
            cv2.LINE_AA,
        )
    for side, wrist in wrists.items():
        x = round(float(wrist["x"]) * width)
        y = round(float(wrist["y"]) * height)
        color = colors[side]
        cv2.circle(output, (x, y), 9, color, -1)
        cv2.putText(
            output,
            f"pose:{side}",
            (x + 8, y - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
            cv2.LINE_AA,
        )
    return output


def _panel(
    context_frames: list[Any],
    center_position: int,
    hands: list[dict[str, Any]],
    wrists: dict[str, dict[str, float]],
    title: str,
) -> Any:
    rendered = []
    for position, frame in enumerate(context_frames):
        shown = _annotate(frame, hands, wrists) if position == center_position else frame
        rendered.append(_fit(shown))
    strip = cv2.hconcat(rendered)
    cv2.putText(
        strip,
        title,
        (10, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return strip


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def run(
    e2d_index: Path,
    video_root: Path,
    hand_task: Path,
    pose_task: Path,
    output_dir: Path,
) -> Path:
    selected = select_pilot(_read_csv(e2d_index))
    output_dir.mkdir(parents=True, exist_ok=False)
    panel_dir = output_dir / "panels"
    panel_dir.mkdir()
    rows = []
    with HandPoseRunner(hand_task, pose_task) as runner:
        for number, item in enumerate(selected, start=1):
            video_path = video_root / item["video_file"]
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise FileNotFoundError(video_path)
            center = int(item["frame_index"])
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            offsets = (-8, -4, 0, 4, 8)
            indices = [max(0, min(frame_count - 1, center + offset)) for offset in offsets]
            frames = [_frame(cap, index) for index in indices]
            cap.release()
            hands, wrists = runner.detect(frames[2])
            sample_id = f"p{number:02d}_{item['item_id']}"
            title = (
                f"{sample_id} target={item['hand']} cadence={item['cadence']} "
                f"group={item['diagnostic_group']}"
            )
            panel = _panel(frames, 2, hands, wrists, title)
            panel_path = panel_dir / f"{sample_id}.jpg"
            if not cv2.imwrite(str(panel_path), panel):
                raise OSError(f"failed to write panel: {panel_path}")
            rows.append(
                {
                    "sample_id": sample_id,
                    "diagnostic_group": item["diagnostic_group"],
                    "clip_id": item["clip_id"],
                    "video_file": item["video_file"],
                    "participant_id": item["participant_id"],
                    "split": item["split"],
                    "gloss": item["gloss"],
                    "frame_index": center,
                    "timestamp_ms": item["timestamp_ms"],
                    "cadence": item["cadence"],
                    "target_hand": item["hand"],
                    "e2d_target_detected": item["target_detected"],
                    "e2d_raw_detected_hands": item["raw_detected_hands"],
                    "detected_hands_json": json.dumps(hands, separators=(",", ":")),
                    "pose_wrists_json": json.dumps(wrists, separators=(",", ":")),
                    "panel_path": str(panel_path.resolve()),
                }
            )
    _write_csv(output_dir / "pilot_index.csv", PILOT_FIELDS, rows)
    _write_csv(
        output_dir / "review_template.csv",
        REVIEW_FIELDS,
        [{"sample_id": row["sample_id"]} for row in rows],
    )
    provenance = {
        "items": len(rows),
        "e2d_index": str(e2d_index.resolve()),
        "e2d_index_sha256": hashlib.sha256(e2d_index.read_bytes()).hexdigest(),
        "hand_task_sha256": hashlib.sha256(hand_task.read_bytes()).hexdigest(),
        "pose_task_sha256": hashlib.sha256(pose_task.read_bytes()).hexdigest(),
        "interpretation": "Pilot review only; no automatic accuracy claim.",
    }
    (output_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the E2e-A ASL Citizen pilot")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--e2d-index",
        type=Path,
        default=Path(
            "F:/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/"
            "e2d_detector_operating_point_v0/engineering_e2d_01/item_index.csv"
        ),
    )
    parser.add_argument(
        "--video-root",
        type=Path,
        default=Path("F:/ASL DATASET/ASL CITIZEN/ASL_Citizen/videos"),
    )
    parser.add_argument(
        "--hand-task", type=Path, default=Path("assets/mediapipe/hand_landmarker.task")
    )
    parser.add_argument(
        "--pose-task",
        type=Path,
        default=Path("assets/mediapipe/pose_landmarker_lite.task"),
    )
    args = parser.parse_args()
    try:
        output = run(
            args.e2d_index,
            args.video_root,
            args.hand_task,
            args.pose_task,
            args.output,
        )
    except (FileExistsError, FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[tracking/e2e-pilot] ERROR: {error}")
        return 2
    print(f"[tracking/e2e-pilot] complete -> {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
