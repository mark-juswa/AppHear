"""Execution safety checks without starting training or touching the reference run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from model.fingerspelling_ctc_fast import train
from model.fingerspelling_fast_execution import FeatureCache
from pipeline.fingerspelling.adapter import WIDTH, identity, sha256
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import ARTIFACT_SCHEMA, RECEIPT_SCHEMA


def record(tmp_path: Path) -> dict[str, Any]:
    features = np.zeros((4, WIDTH), np.float32)
    features[1, 0] = 0.5
    path = tmp_path / "fixture.npz"
    adapter = identity()
    np.savez_compressed(
        path,
        features=features,
        phone_features=features[:2],
        targets=np.array([12, 12], np.int32),
        metadata_json=np.array(json.dumps({"schema_version": ARTIFACT_SCHEMA, "adapter": adapter})),
    )
    return {
        "schema_version": RECEIPT_SCHEMA,
        "sample_id": "fixture",
        "split_role": "DEV",
        "features_path": str(path),
        "features_sha256": sha256(path),
        "adapter": adapter,
    }


def test_cache_immutable_and_loads_once(tmp_path: Path) -> None:
    rec = record(tmp_path)
    cache = FeatureCache()
    native, targets = cache.load(rec, "native")
    phone, _ = cache.load(rec, "phone")
    assert cache.file_loads == 1 and len(phone) == 2 and len(native) == 4
    assert targets.tolist() == [12, 12]
    with pytest.raises(ValueError):
        native[0, 0] = 1
    with pytest.raises(ValueError):
        targets[0] = 0
    Path(rec["features_path"]).unlink()
    assert cache.load(rec, "native")[0] is native


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("schema_version", "invalid", "schema"),
        ("split_role", "TEST", "Protected"),
        ("features_sha256", "0" * 64, "hash"),
    ],
)
def test_cache_refuses_invalid_lineage(tmp_path: Path, field: str, value: str, error: str) -> None:
    rec = record(tmp_path)
    rec[field] = value
    with pytest.raises(ValueError, match=error):
        FeatureCache().load(rec, "native")


def test_cache_identity_cannot_change(tmp_path: Path) -> None:
    rec = record(tmp_path)
    cache = FeatureCache()
    cache.load(rec, "native")
    rec["features_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="identity changed"):
        cache.load(rec, "native")


def test_padding_and_infeasible_phone_not_dropped(tmp_path: Path) -> None:
    rec = record(tmp_path)
    cache = FeatureCache()
    x, mask, y, lengths, target_lengths = cache.batch([rec], "phone")
    assert x.shape == (1, 2, WIDTH) and mask.sum() == 2
    assert y.tolist() == [[12, 12]] and lengths.tolist() == [2]
    assert target_lengths.tolist() == [2]  # minimum=3; retained for decoding, not loss


def test_fast_runner_cannot_write_reference_run(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="read-only"):
        train(tmp_path, REPO / "runs/fingerspelling_ctc_baseline_01", tmp_path / "absent.json")
