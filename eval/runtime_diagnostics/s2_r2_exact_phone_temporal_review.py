"""Blinded temporal review for the exact Android S2 parity capture.

This profile reuses the governed phone-positive review workflow, but binds it to
the capture that persisted the exact Android 378-vector stream. Finalization
links every reviewed visual observation to its exact tensor record and writes a
compact NPZ for S2-R2 preparation. S2 predictions remain hidden during review.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics import s2_r2_phone_positive_temporal_review as review  # noqa: E402

SESSION_ID = "session_20260921T153138Z"
SESSION_ROOT = ROOT / "phone_pull_s2_exact_parity" / SESSION_ID
PARITY_ROOT = SESSION_ROOT / "s2_exact_parity"
OUTPUT_ROOT = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
    / "s2_r2_continuous_domain_correction_01/exact_phone_temporal_review_01"
)
TOOL_VERSION = "s2-r2-exact-phone-temporal-review-v1"

SELECTED_ATTEMPTS = (
    (1, "HELLO", "HARD_POSITIVE_MISS"),
    (2, "HELLO", "HARD_POSITIVE_MISS"),
    (3, "HOME", "HARD_POSITIVE_MISS"),
    (4, "HOME", "POSITIVE_ANCHOR"),
    (5, "TABLE", "POSITIVE_ANCHOR"),
    (6, "TABLE", "HARD_POSITIVE_MISS"),
)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _configure_review_profile(output_root: Path) -> None:
    review.MILESTONE = "S2_R2_CONTINUOUS_DOMAIN_CORRECTION_01"
    review.SESSION_ID = SESSION_ID
    review.SESSION_ROOT = SESSION_ROOT
    review.OUTPUT_ROOT = output_root
    review.REVIEW_MANIFEST = output_root / "phone_positive_review_manifest.json"
    review.ANNOTATIONS = output_root / "phone_positive_temporal_annotations.json"
    review.SELECTED_ATTEMPTS = SELECTED_ATTEMPTS
    review.TOOL_VERSION = TOOL_VERSION


def _load_linkage() -> tuple[list[dict[str, str]], dict[int, int]]:
    linkage_path = PARITY_ROOT / "linkage.csv"
    rows = list(csv.DictReader(linkage_path.open(encoding="utf-8")))
    by_timestamp_ns: dict[int, int] = {}
    for row in rows:
        timestamp_ns = round(float(row["timestamp_ms"]) * 1_000_000.0)
        if timestamp_ns in by_timestamp_ns:
            raise RuntimeError(f"DUPLICATE_PARITY_TIMESTAMP:{timestamp_ns}")
        by_timestamp_ns[timestamp_ns] = int(row["record_index"])
    return rows, by_timestamp_ns


def _write_exact_linkage(output_root: Path) -> dict[str, Any]:
    labels_path = output_root / "phone_positive_observation_labels.csv"
    label_rows = list(csv.DictReader(labels_path.open(encoding="utf-8")))
    linkage_rows, by_timestamp_ns = _load_linkage()
    exact_rows: list[dict[str, Any]] = []
    missing: list[int] = []
    for row in label_rows:
        timestamp_ns = int(row["source_timestamp_ns"])
        record_index = by_timestamp_ns.get(timestamp_ns)
        if record_index is None:
            missing.append(timestamp_ns)
            continue
        exact_rows.append({**row, "record_index": record_index})
    if missing or len(exact_rows) != len(label_rows):
        raise RuntimeError(
            f"EXACT_PHONE_LINKAGE_INCOMPLETE:{len(exact_rows)}/{len(label_rows)}"
        )
    exact_rows.sort(key=lambda row: int(row["record_index"]))

    exact_csv = output_root / "exact_phone_observation_labels.csv"
    with exact_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(exact_rows[0]))
        writer.writeheader()
        writer.writerows(exact_rows)

    manifest = json.loads((PARITY_ROOT / "manifest.json").read_text(encoding="utf-8"))
    observation_count = int(manifest["observation_count"])
    features = np.fromfile(PARITY_ROOT / "android_features.f32", dtype="<f4").reshape(
        observation_count, 378
    )
    probabilities = np.fromfile(
        PARITY_ROOT / "android_probabilities.f32", dtype="<f4"
    ).reshape(observation_count, 3)
    record_indices = np.asarray([int(row["record_index"]) for row in exact_rows], dtype=np.int32)
    state_ids = np.asarray([int(row["state_id"]) for row in exact_rows], dtype=np.int8)
    timestamps_ns = np.asarray(
        [int(row["source_timestamp_ns"]) for row in exact_rows], dtype=np.int64
    )
    attempt_ordinals = np.asarray(
        [int(row["attempt_ordinal"]) for row in exact_rows], dtype=np.int8
    )
    npz_path = output_root / "exact_phone_labeled_features.npz"
    np.savez_compressed(
        npz_path,
        features=features[record_indices],
        frozen_s2_probabilities=probabilities[record_indices],
        state_ids=state_ids,
        record_indices=record_indices,
        source_timestamps_ns=timestamps_ns,
        attempt_ordinals=attempt_ordinals,
    )
    result = {
        "schema": "apphear.s2_r2.exact_phone_tensor_linkage.v1",
        "session_id": SESSION_ID,
        "reviewed_visual_observations": len(exact_rows),
        "linked_exact_tensor_observations": len(exact_rows),
        "eligible_supervised_observations": int(np.sum(state_ids >= 0)),
        "ignored_transition_observations": int(np.sum(state_ids < 0)),
        "parity_capture_observations": len(linkage_rows),
        "android_features_sha256": _sha256_file(PARITY_ROOT / "android_features.f32"),
        "android_probabilities_sha256": _sha256_file(
            PARITY_ROOT / "android_probabilities.f32"
        ),
        "exact_labels_csv_sha256": _sha256_file(exact_csv),
        "exact_labeled_npz_sha256": _sha256_file(npz_path),
        "jpeg_reprocessing_used_for_training_features": False,
        "independent_validation_claim": False,
        "training_role": "FIT_DEVELOPMENT_ONLY_CURRENT_PHONE_DESIGN_SIGNER",
    }
    (output_root / "exact_phone_tensor_linkage.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "serve", "finalize"))
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8769)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    _configure_review_profile(args.output_root)
    if args.command == "prepare":
        prepared = review.prepare(args.output_root)
        print(
            json.dumps(
                {
                    "attempts": len(prepared["attempts"]),
                    "manifest": str(prepared["manifest_path"]),
                    "manifest_sha256": prepared["manifest_sha256"],
                    "annotations": str(prepared["annotation_path"]),
                },
                indent=2,
            )
        )
        return 0
    if args.command == "serve":
        return review.serve(args.output_root, args.host, args.port, not args.no_browser)
    review_summary = review.finalize(args.output_root)
    print(
        json.dumps(
            {
                "review": review_summary,
                "exact_tensor_linkage": _write_exact_linkage(args.output_root),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
