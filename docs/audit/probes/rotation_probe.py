"""Exploratory, read-only paired probe: does rotating the hand crop so the
DWPose wrist->middle-MCP axis points up change MediaPipe refiner acceptance?

Uses saved JPEG originals (not exact live RGBA pixels). Baseline arm reproduces
the axis-aligned Candidate01 crop; the rotated arm uses the same centre/side
with an in-plane rotation. Nothing is written except stdout.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(sys.argv[1])
sys.path.insert(0, str(REPO))
from pipeline.perception_vnext import offline_candidate01 as oc  # noqa: E402
from pipeline.perception_vnext.hand_roi import HandRoi, build_hand_roi  # noqa: E402
from pipeline.perception_vnext.recognition_schema import (  # noqa: E402
    HAND_POINTS, LEFT_HAND_START, RIGHT_HAND_START, HAND_PRESENCE_THRESHOLD,
    MINIMUM_REFINED_VALID_POINTS,
)

ASSETS = REPO / "android/app/src/main/assets/perception_vnext"


def rotated_input(image, roi, angle):
    """Sample a 224 crop of side roi.side centred on the ROI, rotated by angle (rad)."""
    dx, dy = np.meshgrid(np.arange(224, dtype=np.float32), np.arange(224, dtype=np.float32))
    u = (dx / 223.0 - 0.5) * roi.side
    v = (dy / 223.0 - 0.5) * roi.side
    c, s = math.cos(angle), math.sin(angle)
    x = roi.center_x + c * u - s * v
    y = roi.center_y + s * u + c * v
    return np.ascontiguousarray(oc._sample_rgb(image, x, y) / np.float32(255.0), np.float32)


def accepted(refined):
    return bool(refined.presence >= HAND_PRESENCE_THRESHOLD
                and np.count_nonzero(refined.valid) >= MINIMUM_REFINED_VALID_POINTS)


def main():
    model = oc.Candidate01Offline(ASSETS / "dwpose_t_singlepass.onnx",
                                  ASSETS / "hand_landmarks_detector.tflite")
    totals = {}
    for session in sys.argv[2:]:
        s = Path(session)
        obs = {}
        for line in open(s / "observations.jsonl", encoding="utf-8"):
            o = json.loads(line)
            obs[o["source_index"]] = o
        labels = json.load(open(s / "transition_review" / "human_boundaries.json", encoding="utf-8"))
        for sign in labels["signs"]:
            if sign["start_index"] is None or sign["judgment"] != "GENUINE_SIGN":
                continue
            key = f"{s.name[-8:]}:{sign['condition']}:{sign['gloss']}#{sign['ordinal']}"
            row = {"slots": 0, "base_acc": 0, "rot_acc": 0, "live_acc": 0, "base_p": [], "rot_p": []}
            for idx in range(sign["start_index"], sign["end_index"] + 1):
                o = obs.get(idx)
                if o is None:
                    continue
                image = np.asarray(Image.open(s / o["visual_evidence_original"]).convert("RGB"))
                value, transform = oc.pose_input(image)
                sx, sy = model.pose.run(["simcc_x", "simcc_y"], {"input": value})
                points, support = oc.decode(sx, sy, transform)
                h, w = image.shape[:2]
                for side_name, start in (("left", LEFT_HAND_START), ("right", RIGHT_HAND_START)):
                    pts = points[start:start + HAND_POINTS]
                    sup = support[start:start + HAND_POINTS]
                    roi = build_hand_roi(pts, sup, w, h)
                    if roi is None:
                        continue
                    base = model.refiner.refine_input(oc.hand_input(image, roi), roi)
                    if sup[0] >= 0.10 and sup[9] >= 0.10:
                        vx, vy = pts[9] - pts[0]
                        # rotate so wrist->MCP points to -y (up) in the crop
                        angle = math.atan2(vy, vx) + math.pi / 2
                    else:
                        angle = 0.0
                    rot = model.refiner.refine_input(rotated_input(image, roi, angle), roi)
                    row["slots"] += 1
                    row["base_acc"] += accepted(base)
                    row["rot_acc"] += accepted(rot)
                    row["live_acc"] += bool(o[f"{side_name}_observed"])
                    row["base_p"].append(base.presence)
                    row["rot_p"].append(rot.presence)
            totals[key] = row
            print(f"{key:45s} ROI slots={row['slots']:3d} live_accepted={row['live_acc']:3d} "
                  f"jpeg_axis_aligned_accepted={row['base_acc']:3d} jpeg_rotated_accepted={row['rot_acc']:3d} "
                  f"median_presence axis/rot={np.median(row['base_p']):.3f}/{np.median(row['rot_p']):.3f}")
    agg = {k: sum(r[k] for r in totals.values()) for k in ("slots", "live_acc", "base_acc", "rot_acc")}
    print("TOTAL", agg)
    model.close()


if __name__ == "__main__":
    main()
