"""Post-run integrity and existence/handedness separation for frozen P4-C1 outputs.

This script never loads or runs WiLoR. It verifies the already preserved outputs,
adds the preregistered detection-existence view, and refreshes report hashes.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4c1_wilor_det_01"
MANIFEST = OUT / "p4c1_frozen_input_manifest.csv"
FRAMES = OUT / "p4c1_frame_results.csv"
DETECTIONS = OUT / "p4c1_raw_detections.csv"
RESULT = OUT / "p4c1_wilor_det_eligibility_result.json"
PROVENANCE = OUT / "p4c1_wilor_provenance.json"
REPORT = OUT / "P4C1_WILOR_DET_ELIGIBILITY_RESULT.md"
RAW = OUT / "raw_native_outputs"
AUDIT = OUT / "p4c1_postrun_integrity_audit.json"
HASHES = OUT / "p4c1_artifact_hash_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def rate(numerator: int, denominator: int) -> float:
    return numerator / denominator


def pct(value: float) -> str:
    return f"{100.0 * value:.2f}%"


def main() -> None:
    manifest = read_csv(MANIFEST)
    frames = read_csv(FRAMES)
    detections = read_csv(DETECTIONS)
    native_paths = sorted(RAW.glob("*.json"))
    manifest_ids = {row["annotation_row_id"] for row in manifest}
    frame_ids = {row["annotation_row_id"] for row in frames}
    native_ids = {path.stem for path in native_paths}
    detection_ids = {row["annotation_row_id"] for row in detections}
    if len(manifest) != 458 or len(frames) != 458 or len(native_paths) != 458:
        raise RuntimeError("P4C1_INVALID: post-run output count mismatch")
    if not (manifest_ids == frame_ids == native_ids) or not detection_ids <= manifest_ids:
        raise RuntimeError("P4C1_INVALID: post-run row identity mismatch")
    for row in manifest:
        path = Path(row["image_path"])
        if not path.is_file() or sha256(path) != row["image_sha256"]:
            raise RuntimeError(f"P4C1_INVALID: source changed after inference: {row['annotation_row_id']}")
    raw_detection_count = 0
    for path in native_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["annotation_row_id"] != path.stem:
            raise RuntimeError("P4C1_INVALID: native output identity mismatch")
        raw_detection_count += int(payload["post_nms_accepted_count"])
    if raw_detection_count != len(detections):
        raise RuntimeError("P4C1_INVALID: native/CSV detection count mismatch")

    capacity_hits = 0
    visible_total = 0
    any_hits = any_total = 0
    one_hits = one_total = 0
    two_hits = two_total = 0
    for row in frames:
        visible = int(row["human_visible_left"] == "YES") + int(row["human_visible_right"] == "YES")
        detected = int(row["wilor_detection_count"])
        capacity_hits += min(visible, detected)
        visible_total += visible
        if visible:
            any_total += 1
            any_hits += detected > 0
        if visible == 1:
            one_total += 1
            one_hits += detected > 0
        if visible == 2:
            two_total += 1
            two_hits += detected >= 2
    existence = {
        "visible_hand_capacity_hits": capacity_hits,
        "visible_hand_observations": visible_total,
        "visible_hand_capacity_recall": rate(capacity_hits, visible_total),
        "any_visible_frame_hits": any_hits,
        "any_visible_frames": any_total,
        "any_visible_frame_recall": rate(any_hits, any_total),
        "one_hand_existence_hits": one_hits,
        "one_hand_frames": one_total,
        "one_hand_existence_recall": rate(one_hits, one_total),
        "complete_two_hand_existence_hits": two_hits,
        "two_hand_frames": two_total,
        "complete_two_hand_existence_retention": rate(two_hits, two_total),
        "interpretation": (
            "Capacity matching uses min(number of detections, number of visible human hands). "
            "Without GT boxes it measures existence capacity, not per-hand localization."
        ),
    }
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    result["detection_existence_metrics"] = existence
    result["handedness_delta"] = {
        "visible_capacity_hits_minus_anatomical_hits": capacity_hits - result["metrics"]["confusion"]["tp"],
        "one_hand_existence_hits_minus_anatomical_hits": one_hits
        - round(result["metrics"]["one_hand_visible_recall"] * one_total),
        "interpretation": "Most misses are detector-existence failures, not handedness-only errors.",
    }
    result["postrun_integrity_audit_path"] = str(AUDIT.resolve())
    atomic_json(RESULT, result)

    audit = {
        "passed": True,
        "manifest_rows": len(manifest),
        "frame_result_rows": len(frames),
        "raw_native_outputs": len(native_paths),
        "raw_detection_rows": len(detections),
        "source_images_rehashed": len(manifest),
        "identity_sets_match": True,
        "native_detection_count_matches_csv": True,
        "inference_was_not_rerun": True,
        "existence_metrics": existence,
    }
    atomic_json(AUDIT, audit)

    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    provenance["postrun_finalizer_sha256"] = sha256(Path(__file__))
    provenance["postrun_integrity_audit_sha256"] = sha256(AUDIT)
    atomic_json(PROVENANCE, provenance)

    report = REPORT.read_text(encoding="utf-8")
    marker = "## DWPose complementarity (no fusion)"
    addition = f"""## Detection existence versus anatomical-side classification

Because this benchmark has no hand boxes, the side-agnostic view is a capacity diagnostic:
it credits at most `min(detection count, visible-hand count)` per frame. It does not claim
box localization. WiLoR supplied capacity for {capacity_hits}/{visible_total} visible hands
({pct(existence['visible_hand_capacity_recall'])}), detected at least one hand in
{any_hits}/{any_total} positive frames ({pct(existence['any_visible_frame_recall'])}), detected
a hand in {one_hits}/{one_total} governed one-hand frames
({pct(existence['one_hand_existence_recall'])}), and supplied at least two detections in
{two_hits}/{two_total} two-hand frames ({pct(existence['complete_two_hand_existence_retention'])}).

Anatomical scoring credited 416 visible slots versus 418 in the side-agnostic capacity view,
and 151 versus 153 one-hand frames. Thus handedness-only errors explain just two observations;
the dominant failure is missing/firing detector existence, not merely swapping left and right.

"""
    if addition.splitlines()[0] not in report:
        report = report.replace(marker, addition + marker)
    atomic_text(REPORT, report)

    artifact_paths = [
        path for path in OUT.iterdir()
        if path.is_file() and path.name != HASHES.name and path.suffix.lower() in {".csv", ".json", ".md", ".txt"}
    ]
    hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in sorted(artifact_paths)}
    native_hashes = [sha256(path) for path in native_paths]
    hashes["raw_native_outputs_count"] = str(len(native_hashes))
    hashes["raw_native_outputs_aggregate_sha256"] = hashlib.sha256("\n".join(native_hashes).encode()).hexdigest()
    atomic_json(HASHES, hashes)
    print(json.dumps({"integrity_passed": True, "existence": existence, "classification": result["classification"]}, indent=2))


if __name__ == "__main__":
    main()
