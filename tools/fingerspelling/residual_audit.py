"""Bounded crop-only audit; no fitting, letter labels or TEST payloads."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

import cv2
import numpy as np

from model import fingerspelling_baseline2 as b2
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import verify_raw, verify_source
from pipeline.fingerspelling.visual_crop import hand_crop
from pipeline.fingerspelling.visual_package import receipt_path, verified_orientation
from pipeline.fingerspelling.visual_quality import identity, quality
from pipeline.perception_vnext.offline_candidate01 import iter_video_frames

EVIDENCE = REPO / "artifacts/fingerspelling_residual_visual_01"


def audit() -> dict[str, Any]:
    cv2.setNumThreads(1)
    rows = [r for r in b2.dataset(b2.DEFAULT_DATA) if receipt_path(r).is_file()]
    summaries, selected = [], []
    indexed = {}
    for r in rows:
        raw = verify_raw(
            REPO / r["raw_path"], REPO / r["raw_receipt_path"], r, r["source_sha256"]
        )
        q = quality(raw)
        indexed[r["sample_id"]] = (r, raw, q)
        summaries.append(
            {
                "sample_id": r["sample_id"],
                "role": r["split_role"],
                "stratum": r["source_stratum"],
                "frames": len(raw.frame_index),
                "retained": int((q["quality"] > 0).sum()),
                "any_retained": int((q["quality"] > 0).any(axis=1).sum()),
                "accepted_before_dedup": int((q["quality_before_dedup"] > 0).sum()),
                "duplicate_frames": int(q["duplicate"].sum()),
                "refiner_rejected_proposals": int(
                    (raw.hand_proposal_present & ~raw.hand_observed).sum()
                ),
                "rejection_bit_counts": [
                    int(((q["rejection_bits"] & (1 << k)) > 0).sum()) for k in range(7)
                ],
            }
        )
    # Metadata/quality selection only; four independent signers per role/stratum,
    # spanning the observed reliability distribution, rather than best crops only.
    for role, stratum in [("TRAIN", "DAUN"), ("TRAIN", "MacKenzie"), ("DEV", "DAUN")]:
        candidates = sorted(
            [
                s
                for s in summaries
                if s["role"] == role and s["stratum"] == stratum and s["retained"]
            ],
            key=lambda s: (s["any_retained"] / s["frames"], s["sample_id"]),
        )
        used = set()
        for fraction in [0.0, 0.33, 0.66, 1.0]:
            start = round(fraction * (len(candidates) - 1))
            candidates_rotated = candidates[start:] + candidates[:start]
            item = next(
                s
                for s in candidates_rotated
                if indexed[s["sample_id"]][0]["official_signer_id"] not in used
            )
            r, raw, q = indexed[item["sample_id"]]
            used.add(r["official_signer_id"])
            positions = np.argwhere(q["quality"] > 0)
            i, slot = map(int, positions[len(positions) // 2])
            selected.append(
                {
                    "sample_id": r["sample_id"],
                    "row": i,
                    "slot": slot,
                    "category": "retained",
                    "role": role,
                    "stratum": stratum,
                    "signer": r["official_signer_id"],
                }
            )
    # Failure modes are separate from the 12 retained-crop review.
    for category in ["duplicate", "refiner_rejected", "low_coverage"]:
        candidates = sorted(
            summaries, key=lambda s: (s["any_retained"] / s["frames"], s["sample_id"])
        )
        for item in candidates:
            r, raw, q = indexed[item["sample_id"]]
            positions = (
                np.argwhere(q["suppressed"])
                if category == "duplicate"
                else (
                    np.argwhere(raw.hand_proposal_present & ~raw.hand_observed)
                    if category == "refiner_rejected"
                    else np.argwhere(raw.hand_proposal_present & (q["quality"] == 0))
                )
            )
            if len(positions):
                i, slot = map(int, positions[len(positions) // 2])
                selected.append(
                    {
                        "sample_id": r["sample_id"],
                        "row": i,
                        "slot": slot,
                        "category": category,
                        "role": r["split_role"],
                        "stratum": r["source_stratum"],
                        "signer": r["official_signer_id"],
                    }
                )
                if sum(x["category"] == category for x in selected) == 3:
                    break
    cells = {}
    for sid in sorted({s["sample_id"] for s in selected}):
        r, raw, q = indexed[sid]
        source = REPO / r["source_path"]
        verify_source(source, r)
        wanted = {s["row"] for s in selected if s["sample_id"] == sid}
        iterator, decoder = iter_video_frames(source, None)
        previous = json.loads((REPO / r["raw_receipt_path"]).read_text())
        if decoder["orientation_degrees_clockwise"] != verified_orientation(
            previous, r
        ):
            raise ValueError("[residual/audit] Orientation differs from extraction")
        for i, (frame, timestamp, _, rgb) in enumerate(iterator):
            if i > max(wanted):
                break
            if i not in wanted:
                continue
            if (
                frame != raw.frame_index[i]
                or abs(timestamp - raw.timestamp_ms[i]) > 0.1
            ):
                raise ValueError("[residual/audit] Source/raw alignment mismatch")
            for s in [s for s in selected if s["sample_id"] == sid and s["row"] == i]:
                slot = s["slot"]
                pixels, _ = hand_crop(
                    rgb,
                    raw.hand_roi_center_side[i, slot],
                    bool(raw.hand_proposal_present[i, slot]),
                )
                shown = np.clip((pixels + 1) * 127.5, 0, 255).astype(np.uint8)
                s.update(
                    frame=int(frame),
                    timestamp_ms=float(timestamp),
                    quality=float(q["quality"][i, slot]),
                    rejection_bits=int(q["rejection_bits"][i, slot]),
                    source_sha256=r["source_sha256"],
                    raw_sha256=r["raw_sha256"],
                )
                cell = np.zeros((294, 512, 3), np.uint8)
                cell[:256, :256] = cv2.resize(rgb, (256, 256))
                cell[:256, 256:] = cv2.resize(shown, (256, 256))
                index = selected.index(s)
                cv2.putText(
                    cell,
                    f"{index}: {s['category']} {s['role']} {s['stratum']} slot{slot}",
                    (4, 273),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.44,
                    (255, 255, 255),
                    1,
                )
                cv2.putText(
                    cell,
                    f"frame {frame} q={s['quality']:.3f} reason={s['rejection_bits']}",
                    (4, 289),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.44,
                    (255, 255, 255),
                    1,
                )
                cells[index] = cell
        if any(
            selected.index(s) not in cells for s in selected if s["sample_id"] == sid
        ):
            raise ValueError("[residual/audit] Missing requested source frame")
    sheets = []
    for start in range(0, len(selected), 4):
        path = EVIDENCE / "crop_audit" / f"sheet_{start//4:02d}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        sheet = np.concatenate(
            [cells[i] for i in range(start, min(start + 4, len(selected)))], axis=0
        )
        if not cv2.imwrite(str(path), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR)):
            raise ValueError("[residual/audit] Cannot write contact sheet")
        sheets.append(
            {"path": path.relative_to(REPO).as_posix(), "sha256": sha256(path)}
        )
    report = {
        "schema_version": "apphear.fingerspelling.residual_crop_audit.v1",
        "quality_identity": identity(),
        "inventory_counts": dict(Counter(r["split_role"] for r in rows)),
        "sequences": summaries,
        "review_items": selected,
        "sheets": sheets,
        "test_accessed": False,
        "review_status": "AWAITING_CONTACT_SHEET_REVIEW",
    }
    write_json_atomic(EVIDENCE / "crop_audit.json", report)
    return {
        "sequences": len(rows),
        "retained_review_items": 12,
        "sheets": sheets,
        "frames": sum(s["frames"] for s in summaries),
        "retained_slot_crops": sum(s["retained"] for s in summaries),
        "duplicate_frames": sum(s["duplicate_frames"] for s in summaries),
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
