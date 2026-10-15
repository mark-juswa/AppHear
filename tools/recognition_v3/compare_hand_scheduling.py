"""Host same-input scheduling diagnostic; no ASL accuracy or phone speed claim."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(values: list[float]) -> dict:
    return {
        "n": len(values),
        "p50_ms": float(np.quantile(values, 0.5)) if values else None,
        "p95_ms": float(np.quantile(values, 0.95)) if values else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.evidence_root.resolve()
    sys.path.insert(0, str(root))
    from pipeline.perception_vnext.hand_refiner import MediaPipeHandRefiner
    from pipeline.perception_vnext.hand_roi import HandRoi, crop_hand

    evidence = root / "artifacts/recognition_upgrade"
    candidate = evidence / "perception_vnext/phone_01/candidate_01_dwpose_t_mp_hand"
    rows_path = candidate / "offline_refined/refined_phone_frames.jsonl"
    frame_root = evidence / "p8c3b1_controlled_live_student_geometry_capture_01"
    model = candidate / "refiner/hand_landmarks_detector.tflite"
    assert sha256(model) == "6acda74af3fbf40e68265c20c7394b2bad81a16a481dcd79ad7a081887c3d6b9"
    selected = []
    counts: dict[str, int] = {}
    for line in rows_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        proposals = sum(row[s]["proposal"] is not None for s in ("left_hand", "right_hand"))
        condition = f"{row['condition_id']}/proposals_{proposals}"
        if counts.get(condition, 0) < 2:
            selected.append(row)
            counts[condition] = counts.get(condition, 0) + 1
    args.out.mkdir(parents=True, exist_ok=True)
    fixture_dir = args.out / "android_fixtures/v3"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    fixtures, cases = [], []
    for row in selected:
        image_path = frame_root / row["image_filename"]
        assert sha256(image_path) == row["image_sha256"]
        image = cv2.imread(str(image_path))
        assert image is not None
        assert image.shape[:2] == (row["source_height"], row["source_width"])
        inputs: list[Any] = []
        for side in ("left_hand", "right_hand"):
            p = row[side]["proposal"]
            if p is None:
                inputs.append(None)
            else:
                roi = HandRoi(
                    *p["center_xy_source"],
                    p["side_source_px"],
                    row["source_width"],
                    row["source_height"],
                    p["support_count_0p10"],
                )
                crop = crop_hand(image, roi)[:, :, ::-1].astype(np.float32) / np.float32(255)
                inputs.append((crop, roi))
        cases.append((row, inputs))
        name = f"frame_{row['retained_sequence_id']:04d}.rgba"
        rgba = cv2.cvtColor(image, cv2.COLOR_BGR2RGBA).tobytes()
        (fixture_dir / name).write_bytes(rgba)
        fixtures.append(
            {
                "asset": name,
                "sha256": hashlib.sha256(rgba).hexdigest(),
                "source_sha256": row["image_sha256"],
                "timestamp_ns": row["sensor_timestamp_ns"],
                "condition": row["condition_id"],
                "width": row["source_width"],
                "height": row["source_height"],
                "rois": [row[s]["proposal"] for s in ("left_hand", "right_hand")],
            }
        )
    (fixture_dir / "manifest.json").write_text(json.dumps({"fixtures": fixtures}, indent=2))
    first = MediaPipeHandRefiner(model, num_threads=2)
    second = MediaPipeHandRefiner(model, num_threads=2)
    timings: dict[str, dict[str, list[float]]] = {
        str(i): {"serial": [], "parallel": []} for i in range(3)
    }
    mismatches = compared = 0
    fields = ("xy_source", "xy_crop", "raw_z", "world_xyz", "presence", "handedness", "valid")
    try:
        with ThreadPoolExecutor(max_workers=1) as worker:
            for _, inputs in cases:
                for item in inputs:
                    if item is not None:
                        first.refine_input(*item)
                        second.refine_input(*item)
            for repeat in range(5):
                for _, inputs in cases:
                    result = {}
                    for mode in (
                        ("serial", "parallel") if repeat % 2 == 0 else ("parallel", "serial")
                    ):
                        start = time.perf_counter_ns()
                        if mode == "parallel" and all(v is not None for v in inputs):
                            pending = worker.submit(first.refine_input, *inputs[0])
                            try:
                                right = second.refine_input(*inputs[1])
                            finally:
                                left = pending.result()
                            values = [left, right]
                        else:
                            values = [
                                first.refine_input(*v) if v is not None else None for v in inputs
                            ]
                        timings[str(sum(v is not None for v in inputs))][mode].append(
                            (time.perf_counter_ns() - start) / 1e6
                        )
                        result[mode] = values
                    for left, right in zip(result["serial"], result["parallel"], strict=True):
                        if left is None:
                            assert right is None
                            continue
                        compared += 1
                        mismatches += any(
                            not np.array_equal(getattr(left, f), getattr(right, f)) for f in fields
                        )
    finally:
        first.close()
        second.close()
    report = {
        "schema_version": "apphear.v3.host_hand_scheduling.v1",
        "model_sha256": sha256(model),
        "source_manifest_sha256": sha256(rows_path),
        "scope": "Windows CPU refiner scheduling only; identical precomputed crops/ROIs",
        "frames": len(cases),
        "conditions": counts,
        "repeats": 5,
        "compared_hand_outputs": compared,
        "bitwise_output_mismatches": mismatches,
        "by_hand_count": {k: {m: stats(v) for m, v in d.items()} for k, d in timings.items()},
        "phone_fps": "NOT_TESTED",
        "word_accuracy": "NOT_TESTED",
        "fingerspell_accuracy": "NOT_TESTED",
    }
    (args.out / "host_comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if mismatches:
        raise SystemExit("PARITY_FAIL")


if __name__ == "__main__":
    main()
