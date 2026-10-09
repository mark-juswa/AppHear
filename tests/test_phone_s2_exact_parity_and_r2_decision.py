from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from eval.runtime_diagnostics.phone_s2_exact_parity_and_r2_decision import (
    comparison,
    load_capture,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_android_binary_capture_contract_round_trips(tmp_path: Path) -> None:
    root = tmp_path / "s2_exact_parity"
    root.mkdir()
    count = 2
    values = {
        "source_index.i32": np.arange(count, dtype="<i4"),
        "timestamp_ms.f64": np.asarray([100.0, 300.0], dtype="<f8"),
        "source_size.i32": np.tile(np.asarray([480, 640], dtype="<i4"), count),
        "raw_hand_xy.f32": np.zeros(count * 84, dtype="<f4"),
        "raw_hand_joint_valid.u8": np.zeros(count * 42, dtype="u1"),
        "raw_hand_proposal_support.f32": np.zeros(count * 42, dtype="<f4"),
        "raw_hand_presence.f32": np.full(count * 2, np.nan, dtype="<f4"),
        "raw_hand_observed.u8": np.zeros(count * 2, dtype="u1"),
        "raw_hand_proposal_present.u8": np.zeros(count * 2, dtype="u1"),
        "raw_hand_roi_center_side.f32": np.zeros(count * 6, dtype="<f4"),
        "raw_body_xy.f32": np.zeros(count * 16, dtype="<f4"),
        "raw_body_support.f32": np.zeros(count * 8, dtype="<f4"),
        "raw_body_valid.u8": np.zeros(count * 8, dtype="u1"),
        "raw_body_available.u8": np.zeros(count, dtype="u1"),
        "android_features.f32": np.zeros(count * 378, dtype="<f4"),
        "android_normalized.f32": np.ones(count * 378, dtype="<f4"),
        "android_probabilities.f32": np.tile(
            np.asarray([0.8, 0.1, 0.1], dtype="<f4"), count
        ),
        "android_argmax.u8": np.zeros(count, dtype="u1"),
        "history_length.i32": np.asarray([1, 2], dtype="<i4"),
    }
    files = {}
    for name, value in values.items():
        path = root / name
        path.write_bytes(value.tobytes())
        files[name] = {
            "bytes_per_observation": path.stat().st_size // count,
            "sha256": _sha(path),
        }
    linkage = root / "linkage.csv"
    with linkage.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ["record_index", "source_index", "timestamp_ms", "attempt_id", "expected_gloss"]
        )
        writer.writerow([0, 0, 100.0, "", ""])
        writer.writerow([1, 1, 300.0, 1, "HELLO"])
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "apphear.phone_s2_exact_parity_capture.v1",
                "raw_schema": "apphear.perception_vnext.raw.v1",
                "feature_schema": "apphear.perception_vnext.segmentation_features.v1",
                "feature_width": 378,
                "observation_count": count,
                "maximum_observations": 3600,
                "files": files,
                "linkage_sha256": _sha(linkage),
            }
        ),
        encoding="utf-8",
    )

    capture = load_capture(tmp_path, require_full_session=False)
    assert capture.count == 2
    assert capture.raw.timestamp_ms.tolist() == [100.0, 300.0]
    assert capture.android_features.shape == (2, 378)
    assert capture.android_probabilities.shape == (2, 3)


def test_comparison_reports_first_material_row() -> None:
    reference = np.zeros((3, 2), np.float32)
    android = reference.copy()
    android[1, 0] = np.float32(2.0e-5)
    result = comparison(reference, android, tolerance=1.0e-6)
    assert result["pass"] is False
    assert result["rows_exceeding_tolerance"] == 1
    assert result["first_row_exceeding_tolerance"] == 1


def test_placeholder_path_fails_with_actionable_message() -> None:
    with pytest.raises(ValueError, match="REPLACE_CAPTURED_SESSION_PLACEHOLDER"):
        load_capture(Path("phone_pull_s2_exact_parity/<CAPTURED_SESSION>"))
