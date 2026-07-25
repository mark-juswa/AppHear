"""Core stage-E extractor: video → raw MediaPipe hand + pose landmarks.

Runs the Hand and Pose landmarkers in MediaPipe IMAGE mode (stateless per-frame detection —
see constants.RUNNING_MODE for the rationale). Face is never run (v2 lesson a). Hands are
stored into canonical slots by handedness label (Left=0, Right=1); missing landmarks are NaN
with score 0. Timestamps are still recorded (from native fps) for downstream duration use,
but are not fed to MediaPipe."""

from __future__ import annotations

from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from .config import ExtractConfig
from .constants import HAND_SLOTS, MISSING, NUM_HAND_LANDMARKS, NUM_HANDS, NUM_POSE_LANDMARKS
from .schema import ClipLandmarks


class LandmarkExtractor:
    """Wraps the hand + pose landmarkers. Not thread-safe — one instance per process/worker."""

    def __init__(self, config: ExtractConfig) -> None:
        self._config = config
        # IMAGE mode: min_tracking_confidence is unused (no cross-frame tracking).
        self._hand = vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(config.hand_task)),
                running_mode=vision.RunningMode.IMAGE,
                num_hands=config.hand.num_hands,
                min_hand_detection_confidence=config.hand.min_hand_detection_confidence,
                min_hand_presence_confidence=config.hand.min_hand_presence_confidence,
            )
        )
        self._pose = vision.PoseLandmarker.create_from_options(
            vision.PoseLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(config.pose_task)),
                running_mode=vision.RunningMode.IMAGE,
                num_poses=config.pose.num_poses,
                min_pose_detection_confidence=config.pose.min_pose_detection_confidence,
                min_pose_presence_confidence=config.pose.min_pose_presence_confidence,
            )
        )

    def close(self) -> None:
        self._hand.close()
        self._pose.close()

    def __enter__(self) -> LandmarkExtractor:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def extract(self, video_path: Path) -> tuple[ClipLandmarks, dict[str, float | int]]:
        """Extract landmarks for one clip. Returns the arrays and a small meta dict
        (native_fps, n_frames, frame_width, frame_height)."""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise OSError(f"cannot open video: {video_path}")
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if fps <= 0:
            cap.release()
            raise ValueError(f"invalid fps ({fps}) for {video_path}")

        hands_image: list[np.ndarray] = []
        hands_world: list[np.ndarray] = []
        hand_score: list[np.ndarray] = []
        pose_image: list[np.ndarray] = []
        pose_world: list[np.ndarray] = []
        pose_score: list[float] = []
        timestamps: list[int] = []

        frame_idx = 0
        try:
            while True:
                ok, frame_bgr = cap.read()
                if not ok:
                    break
                ts_ms = int(round(frame_idx * 1000.0 / fps))

                rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

                h_img, h_wld, h_sc = self._detect_hands(mp_image)
                p_img, p_wld, p_sc = self._detect_pose(mp_image)

                hands_image.append(h_img)
                hands_world.append(h_wld)
                hand_score.append(h_sc)
                pose_image.append(p_img)
                pose_world.append(p_wld)
                pose_score.append(p_sc)
                timestamps.append(ts_ms)
                frame_idx += 1
        finally:
            cap.release()

        clip = ClipLandmarks(
            hands_image=_stack(hands_image, (NUM_HANDS, NUM_HAND_LANDMARKS, 3)),
            hands_world=_stack(hands_world, (NUM_HANDS, NUM_HAND_LANDMARKS, 3)),
            hand_score=_stack(hand_score, (NUM_HANDS,)),
            pose_image=_stack(pose_image, (NUM_POSE_LANDMARKS, 4)),
            pose_world=_stack(pose_world, (NUM_POSE_LANDMARKS, 3)),
            pose_score=np.asarray(pose_score, dtype=np.float32),
            timestamps_ms=np.asarray(timestamps, dtype=np.int64),
        )
        clip.validate()
        meta: dict[str, float | int] = {
            "native_fps": fps,
            "n_frames": frame_idx,
            "frame_width": width,
            "frame_height": height,
        }
        return clip, meta

    def _detect_hands(self, image: mp.Image) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        img = np.full((NUM_HANDS, NUM_HAND_LANDMARKS, 3), MISSING, dtype=np.float32)
        wld = np.full((NUM_HANDS, NUM_HAND_LANDMARKS, 3), MISSING, dtype=np.float32)
        score = np.zeros((NUM_HANDS,), dtype=np.float32)

        result = self._hand.detect(image)
        for i, handedness in enumerate(result.handedness):
            label = handedness[0].category_name  # "Left" | "Right"
            slot = HAND_SLOTS.index(label) if label in HAND_SLOTS else i % NUM_HANDS
            img[slot] = np.array([[p.x, p.y, p.z] for p in result.hand_landmarks[i]], np.float32)
            wld[slot] = np.array(
                [[p.x, p.y, p.z] for p in result.hand_world_landmarks[i]], np.float32
            )
            score[slot] = float(handedness[0].score)
        return img, wld, score

    def _detect_pose(self, image: mp.Image) -> tuple[np.ndarray, np.ndarray, float]:
        img = np.full((NUM_POSE_LANDMARKS, 4), MISSING, dtype=np.float32)
        wld = np.full((NUM_POSE_LANDMARKS, 3), MISSING, dtype=np.float32)
        score = 0.0

        result = self._pose.detect(image)
        if result.pose_landmarks:
            lms = result.pose_landmarks[0]
            img = np.array([[p.x, p.y, p.z, p.visibility] for p in lms], np.float32)
            wld = np.array([[p.x, p.y, p.z] for p in result.pose_world_landmarks[0]], np.float32)
            score = float(np.mean([p.visibility for p in lms]))
        return img, wld, score


def _stack(frames: list[np.ndarray], per_frame_shape: tuple[int, ...]) -> np.ndarray:
    if not frames:
        return np.empty((0, *per_frame_shape), dtype=np.float32)
    return np.stack(frames).astype(np.float32)
