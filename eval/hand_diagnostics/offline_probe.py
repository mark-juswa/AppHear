"""Offline probe of the SHIPPED DWPose-t + MediaPipe hand refiner (investigation tool; not part of the app or the test suite).

Runs the same models (hashes asserted) with the repo's own reference preprocessing (`pipeline.perception_vnext.offline_candidate01`:
pose_input / decode, `hand_roi.build_hand_roi`, hand_input), so a result here is a statement about the models the app ships, on host
fp32 arithmetic. It does NOT reproduce phone timing, camera ISP, or the emulator's webcam scaling.

Per frame and per hand group (L = DWPose group 91..111, R = 112..132) it records:
  * SimCC activation ("support") per keypoint, how many points pass 0.10 / 0.30, and the ROI the app would build;
  * the refiner's presence and handedness on the crop AS THE APP FEEDS IT (unmirrored source) and on the HORIZONTALLY FLIPPED crop;
  * the body wrist keypoints (COCO idx 9 = left wrist, 10 = right wrist) and the hand-wrist to body-wrist distance for the same side;
and the same group-level measurements for a fully MIRRORED copy of the image (DWPose run on the flipped frame).
Requirements (scratch venv, NOT repo dependencies): numpy, opencv-python-headless, onnxruntime, ai-edge-litert.

Usage: python -m eval.hand_diagnostics.offline_probe <frames_dir> <out.jsonl>     (frames_dir holds <segment>__<n>.png RGB frames)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

from pipeline.perception_vnext.hand_roi import HandRoi, build_hand_roi
from pipeline.perception_vnext.offline_candidate01 import (
    EXPECTED_ONNX_SHA256,
    EXPECTED_REFINER_SHA256,
    decode,
    hand_input,
    pose_input,
    sha256,
)
from pipeline.perception_vnext.recognition_schema import LEFT_HAND_START, RIGHT_HAND_START

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "android/app/src/main/assets/perception_vnext"
ONNX = ASSETS / "dwpose_t_singlepass.onnx"
REFINER = ASSETS / "hand_landmarks_detector.tflite"
BODY_WRIST = {"L": 9, "R": 10}          # COCO-WholeBody: 9 = left_wrist, 10 = right_wrist (subject's own side)
GROUP_START = {"L": LEFT_HAND_START, "R": RIGHT_HAND_START}


class LiteRefiner:
    """ai-edge-litert adapter with the same outputs as `MediaPipeHandRefiner` (which needs TensorFlow)."""

    def __init__(self, path: Path = REFINER):
        from ai_edge_litert.interpreter import Interpreter
        self.it = Interpreter(model_path=str(path), num_threads=2)
        self.it.allocate_tensors()
        self.inp = self.it.get_input_details()[0]["index"]
        self.out = {d["name"]: d["index"] for d in self.it.get_output_details()}

    def run(self, rgb01: np.ndarray) -> dict:
        self.it.set_tensor(self.inp, np.ascontiguousarray(rgb01, np.float32)[None])
        self.it.invoke()
        g = lambda n: self.it.get_tensor(self.out[n])
        return {"landmarks": g("Identity").reshape(21, 3), "presence": float(g("Identity_1").reshape(-1)[0]),
                "handedness": float(g("Identity_2").reshape(-1)[0])}


class Probe:
    def __init__(self):
        import onnxruntime as ort
        assert sha256(ONNX) == EXPECTED_ONNX_SHA256, "DWPose model hash mismatch"
        assert sha256(REFINER) == EXPECTED_REFINER_SHA256, "refiner model hash mismatch"
        so = ort.SessionOptions()
        so.intra_op_num_threads = 2
        self.pose = ort.InferenceSession(str(ONNX), sess_options=so, providers=["CPUExecutionProvider"])
        self.refiner = LiteRefiner()

    def _refine(self, rgb: np.ndarray, roi: HandRoi, flip: bool) -> dict:
        crop = hand_input(rgb, roi)
        if flip:
            crop = np.ascontiguousarray(crop[:, ::-1, :])
        out = self.refiner.run(crop)
        lm = out["landmarks"][:, :2]
        if flip:                                    # express the landmarks in the unflipped crop frame again
            lm = lm.copy(); lm[:, 0] = 223.0 - lm[:, 0]
        valid = (lm[:, 0] >= 0) & (lm[:, 0] < 224) & (lm[:, 1] >= 0) & (lm[:, 1] < 224)
        xy = np.stack([roi.center_x - roi.side / 2 + lm[:, 0] / 223.0 * roi.side,
                       roi.center_y - roi.side / 2 + lm[:, 1] / 223.0 * roi.side], axis=1)
        return {"presence": out["presence"], "handedness": out["handedness"], "n_valid": int(valid.sum()),
                "xy": xy[valid].tolist() if valid.any() else []}

    def frame(self, rgb: np.ndarray, flip_probe: bool = True) -> dict:
        h, w = rgb.shape[:2]
        value, transform = pose_input(rgb)
        sx, sy = self.pose.run(["simcc_x", "simcc_y"], {"input": value})
        points, support = decode(sx, sy, transform)
        body = {k: {"xy": points[i].tolist(), "support": float(support[i])} for k, i in BODY_WRIST.items()}
        groups = {}
        for side, start in GROUP_START.items():
            pts, sup = points[start:start + 21], support[start:start + 21]
            roi = build_hand_roi(pts, sup, w, h)
            g = {"support_mean": float(sup.mean()), "support_max": float(sup.max()), "support_p50": float(np.median(sup)),
                 "n_ge_010": int((sup >= 0.10).sum()), "n_ge_030": int((sup >= 0.30).sum()),
                 "wrist_xy": pts[0].tolist(), "wrist_support": float(sup[0]),
                 "roi": None if roi is None else [roi.center_x, roi.center_y, roi.side]}
            if roi is not None:
                g["refined"] = self._refine(rgb, roi, False)
                if flip_probe:
                    g["refined_flipped_crop"] = self._refine(rgb, roi, True)
            groups[side] = g
        return {"size": [w, h], "body_wrist": body, "groups": groups}

    def run(self, rgb: np.ndarray) -> dict:
        out = {"normal": self.frame(rgb)}
        out["mirrored_image"] = self.frame(np.ascontiguousarray(rgb[:, ::-1, :]), flip_probe=False)
        return out


def to_portrait(frame_bgr: np.ndarray, width: int = 480, height: int = 640) -> np.ndarray:
    """Centre-crop a landscape webcam frame to 3:4 portrait and resize to the app's analysis size (upright, UNMIRRORED, RGB)."""
    h, w = frame_bgr.shape[:2]
    cw = int(round(h * width / height))
    x0 = max(0, (w - cw) // 2)
    crop = frame_bgr[:, x0:x0 + cw]
    return cv2.cvtColor(cv2.resize(crop, (width, height), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    frames, out = Path(argv[0]), Path(argv[1])
    probe = Probe()
    with out.open("w") as fh:
        for p in sorted(frames.glob("*.png")):
            seg, _, n = p.stem.partition("__")
            rgb = cv2.cvtColor(cv2.imread(str(p)), cv2.COLOR_BGR2RGB)
            fh.write(json.dumps({"segment": seg, "n": int(n), **probe.run(rgb)}) + "\n")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
