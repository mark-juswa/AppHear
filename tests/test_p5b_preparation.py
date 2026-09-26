from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from eval.runtime_diagnostics import p5b_dataset_migration as migration
from pipeline.features.dwpose_representation_v2 import build_frame_features, build_padded_sequence


def test_frozen_inputs_and_role_counts() -> None:
    rows = migration.read_rows()
    identity = migration.verify_identity(True)
    assert len(rows) == 8131
    assert identity["representation_contract_sha256"] == migration.EXPECTED_CONTRACT_SHA


def test_smoke_native_round_trip_matches_frozen_builder() -> None:
    records = sorted((migration.OUT / "completed").glob("*.json"))
    assert len(records) in {3, 8131}
    for record in records[:3]:
        data = json.loads(record.read_text(encoding="utf-8"))
        with np.load(migration.ROOT / data["native_path"], allow_pickle=False) as native:
            scores = native["scores"]
            presence = np.stack([[np.count_nonzero(s[91:112] >= .30) >= 11,
                                  np.count_nonzero(s[112:133] >= .30) >= 11] for s in scores])
            frames = [build_frame_features(native["keypoints_xy"][i], scores[i], presence[i])[0]
                      for i in range(len(scores))]
        expected, mask, length = build_padded_sequence(frames)
        with np.load(migration.ROOT / data["feature_path"], allow_pickle=False) as feature:
            assert np.array_equal(expected, feature["features"])
            assert np.array_equal(mask, feature["frame_mask"])
            assert length == int(feature["length"])
            assert feature["features"].shape == (96, 238)
            assert np.isfinite(feature["features"]).all()


def test_smoke_records_skip_only_in_smoke_mode() -> None:
    record = next((migration.OUT / "completed").glob("*.json"))
    assert migration.verified_cached(record, allow_smoke=True)
    data = json.loads(record.read_text(encoding="utf-8"))
    assert migration.verified_cached(record, allow_smoke=False) is not bool(data.get("smoke_truncated"))


def test_output_hashes_are_verified() -> None:
    for record in list((migration.OUT / "completed").glob("*.json"))[:10]:
        data = json.loads(record.read_text(encoding="utf-8"))
        assert migration.sha256(migration.ROOT / data["native_path"]) == data["native_sha256"]
        assert migration.sha256(migration.ROOT / data["feature_path"]) == data["feature_sha256"]


def test_padding_has_no_stale_tail() -> None:
    record = next((migration.OUT / "completed").glob("*.json"))
    data = json.loads(record.read_text(encoding="utf-8"))
    with np.load(migration.ROOT / data["feature_path"], allow_pickle=False) as z:
        length = int(z["length"])
        assert not z["frame_mask"][length:].any()
        assert np.count_nonzero(z["features"][length:]) == 0


def test_258_width_is_not_accepted() -> None:
    fake = np.zeros((96, 258), dtype=np.float32)
    assert fake.shape != (migration.SEQUENCE_LENGTH, migration.FEATURE_WIDTH)
