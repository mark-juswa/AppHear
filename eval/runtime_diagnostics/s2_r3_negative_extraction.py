"""Hands-visible non-sign sources for S2-R3 (raw-v1, pinned Candidate01), extracted once.

Closes the hands-visible negative gap with existing, already-governed material only
(S2-R2 negative source recovery audit, s2_r2_phone_temporal_supervision_01):
  P1     the 45 human-reviewed eligible P1 intervals (ordinary visible-hand behaviour), every
         frame inside each interval, so any cadence view can be selected later. Labels PRE.
  PHONE  design-signer continuous session 20260920T145710Z (2,747 observations, every synchronized
         original JPEG). Only the materialized windows of the 15 human-confirmed non-sign events are
         labelled PRE; every other row (attempts, onsets, uncertain, unreviewed) is IGNORE and only
         supplies real causal context. The approximate visible-sign ranges are NOT used as labels.
Roles follow the frozen S2-R3 data split (P1 participant roles; phone design signer = FIT).
E6 and every gate/Tier-3 source stay untouched. Outputs go to a new artifact directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics import s2_r2_continuous_domain_correction as r2  # noqa: E402
from eval.runtime_diagnostics.s2_r3_context_suite import read_json, sha256, write_json  # noqa: E402
from eval.runtime_diagnostics.s2_r3_data_split import FREEZE_PATH as SPLIT_PATH  # noqa: E402
from pipeline.perception_vnext.offline_candidate01 import Candidate01Offline  # noqa: E402
from pipeline.perception_vnext.recognition_schema import (  # noqa: E402
    load_raw_sequence,
    save_raw_sequence,
)

RU = Path("artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01")
OUT_RELATIVE = RU / "s2_r3_negative_raw_01"
P1_INTERVALS = (
    RU / "s2_r2_phone_temporal_supervision_01/p1_temporal_review_01/p1_reviewed_intervals.csv"
)
PHONE_SESSION = (
    RU / "phone_repeated_recognition_integration_01/device_capture/session_20260920T145710Z"
)
PHONE_LABELS = (
    RU / "phone_new_sign_admission_and_active_acquisition_validation_01/refined_event_labels.json"
)
ASSETS = ROOT / "android/app/src/main/assets/perception_vnext"
PRE, IGNORE = 0, -1


def extract_p1(
    root: Path, runtime: Candidate01Offline, roles: dict[str, str]
) -> list[dict[str, Any]]:
    rows = []
    with (root / P1_INTERVALS).open(encoding="utf-8") as stream:
        intervals = [
            r for r in csv.DictReader(stream) if r["eligible_for_s2_r2_negative"].lower() == "true"
        ]
    for interval in intervals:
        target = root / OUT_RELATIVE / f"p1_{interval['interval_id'].replace(':', '_')}.npz"
        video = Path(interval["video_path"])
        if not target.exists():
            if sha256(video) != interval["video_sha256"]:
                raise ValueError(f"[s2_r3/neg] P1_VIDEO_HASH:{interval['interval_id']}")
            t, _, orientation = r2._video_timestamps(video)
            inside = np.flatnonzero(
                (t >= float(interval["start_ms"])) & (t <= float(interval["end_ms"]))
            ).astype(np.int32)
            records = r2._process_video_indices(runtime, video, inside, t, orientation)
            raw = r2._raw_from_records(
                f"p1:{interval['interval_id']}",
                "P1_CAPTURE_03",
                interval["participant_id"],
                records,
            )
            save_raw_sequence(target, raw)
        raw = load_raw_sequence(target)
        rows.append(
            {
                "source_id": f"p1::{interval['interval_id']}",
                "family": "P1_NEGATIVE",
                "participant": interval["participant_id"],
                "role": roles[interval["participant_id"]],
                "raw_path": str(target.relative_to(root)).replace("\\", "/"),
                "raw_sha256": sha256(target),
                "observations": int(len(raw.timestamp_ms)),
                "label_rule": "ALL_PRE",
            }
        )
        print(
            f"[s2_r3/neg] {rows[-1]['source_id']} {rows[-1]['role']} "
            f"obs={rows[-1]['observations']}",
            flush=True,
        )
    return rows


def extract_phone(root: Path, runtime: Candidate01Offline, role: str) -> dict[str, Any]:
    session = root / PHONE_SESSION
    target = root / OUT_RELATIVE / "phone_20260920T145710Z.npz"
    observations = [
        json.loads(line) for line in (session / "observations.jsonl").open(encoding="utf-8")
    ]
    if len(observations) != 2747:
        raise ValueError("[s2_r3/neg] PHONE_OBSERVATION_COUNT")
    if not target.exists():
        records = []
        for obs in observations:
            image = session / str(obs["visual_evidence_original"]).replace("\\/", "/")
            bgr = cv2.imread(str(image), cv2.IMREAD_COLOR)
            if bgr is None:
                raise ValueError(f"[s2_r3/neg] PHONE_IMAGE_DECODE:{image}")
            records.append(
                (
                    int(obs["source_index"]),
                    float(obs["source_timestamp_ms"]),
                    runtime.process_rgb(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)),
                )
            )
            if len(records) % 500 == 0:
                print(f"[s2_r3/neg] phone {len(records)}/2747", flush=True)
        raw = r2._raw_from_records(
            "phone:session_20260920T145710Z", "PHONE_DESIGN_JPEG", "phone_design:S001", records
        )
        save_raw_sequence(target, raw)
    raw = load_raw_sequence(target)
    labels = np.full(len(raw.timestamp_ms), IGNORE, np.int32)
    confirmed = set(read_json(root / PHONE_LABELS)["CONFIRMED_NON_SIGN"])
    events = [json.loads(line) for line in (session / "events.jsonl").open(encoding="utf-8")]
    windows = []
    for event in events:
        if int(event["event_id"]) in confirmed:
            first, last = int(event["materialized_start_index"]), int(
                event["materialized_end_index"]
            )
            labels[first : last + 1] = PRE
            windows.append([int(event["event_id"]), first, last])
    if len(windows) != len(confirmed):
        raise ValueError("[s2_r3/neg] PHONE_EVENT_COVERAGE")
    label_path = root / OUT_RELATIVE / "phone_20260920T145710Z_labels.npy"
    np.save(label_path, labels)
    return {
        "source_id": "phone::session_20260920T145710Z",
        "family": "PHONE_DESIGN_NEGATIVE_STREAM",
        "participant": "phone_design:S001",
        "role": role,
        "raw_path": str(target.relative_to(root)).replace("\\", "/"),
        "raw_sha256": sha256(target),
        "labels_path": str(label_path.relative_to(root)).replace("\\", "/"),
        "labels_sha256": sha256(label_path),
        "observations": int(len(raw.timestamp_ms)),
        "pre_observations": int(np.sum(labels == PRE)),
        "confirmed_non_sign_windows": windows,
        "label_rule": "PRE inside confirmed non-sign event windows; IGNORE elsewhere",
        "provenance": "SYNCED_JPEG_REPROCESSED_CURRENT_CANDIDATE01",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.evidence_root
    split = read_json(SPLIT_PATH)
    roles = {item["participant"]: item["role"] for item in split["p1_negatives"]}
    (root / OUT_RELATIVE).mkdir(parents=True, exist_ok=True)
    runtime = Candidate01Offline(
        ASSETS / "dwpose_t_singlepass.onnx", ASSETS / "hand_landmarks_detector.tflite"
    )
    try:
        p1 = extract_p1(root, runtime, roles)
        phone = extract_phone(root, runtime, split["phone_positive_design_signer"]["role"])
    finally:
        runtime.close()
    write_json(
        root / OUT_RELATIVE / "manifest.json",
        {
            "schema": "apphear.s2_r3.negative_raw_manifest.v1",
            "split_sha256": sha256(SPLIT_PATH),
            "candidate01_assets_sha256": {
                name: sha256(ASSETS / name)
                for name in ("dwpose_t_singlepass.onnx", "hand_landmarks_detector.tflite")
            },
            "sources": p1 + [phone],
        },
        overwrite=True,
    )
    print(json.dumps({"p1": len(p1), "phone_pre": phone["pre_observations"]}), flush=True)


if __name__ == "__main__":
    main()
