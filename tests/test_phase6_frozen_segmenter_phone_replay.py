from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from eval.runtime_diagnostics.finalize_phase4a_gate4a1 import load_raw
from eval.runtime_diagnostics.phase6_evaluate_phone_replay import (
    EXPECTED_ORACLE_SHA,
    OUT,
    verify_learned_freeze,
    verify_post_freeze_identities,
)
from eval.runtime_diagnostics.phase6_freeze_learned_phone_events import (
    ATTEMPTS,
    IDENTITIES,
    SESSION,
    SESSION_ID,
    freeze_json,
    load_phone_inputs,
    read_json,
    sha256,
    verify_identities,
)
from pipeline.perception_vnext.segmentation.learned_features import (
    FEATURE_WIDTH,
    derive_causal_segmentation_features,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE_SOURCE = ROOT / "eval/runtime_diagnostics/phase6_freeze_learned_phone_events.py"
EVALUATION_SOURCE = ROOT / "eval/runtime_diagnostics/phase6_evaluate_phone_replay.py"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_exact_phone_population_and_source_session() -> None:
    assert SESSION_ID == "session_20260915T065635Z"
    assert ATTEMPTS == tuple(f"attempt_{index:03d}" for index in range(1, 11))
    manifest, sequences = load_phone_inputs()
    assert [row["attempt_id"] for row in manifest] == list(ATTEMPTS)
    assert len(sequences) == 10
    assert all(SESSION_ID in row["raw_v1_path"] for row in manifest)


def test_phone_observations_are_chronological_and_not_resampled() -> None:
    manifest, sequences = load_phone_inputs()
    for row, raw in zip(manifest, sequences, strict=True):
        assert np.all(np.diff(raw.timestamp_ms) > 0)
        assert row["observation_count"] == len(raw.timestamp_ms)
        assert not row["resampled"]
        assert not row["interpolated"]
        assert not row["duplicated"]


def test_sparse_features_use_immediately_previous_phone_observation() -> None:
    raw, _ = load_raw(SESSION / "attempt_001/raw_v1.json")
    features = derive_causal_segmentation_features(raw)
    assert features.shape == (len(raw.timestamp_ms), FEATURE_WIDTH)
    expected_dt = np.clip(np.diff(raw.timestamp_ms) / 1000.0, 0.0, 1.0)
    np.testing.assert_allclose(features[1:, 215], expected_dt, atol=1e-7)

    scale = raw.source_size.astype(np.float32)
    body_xy = raw.body_xy.astype(np.float32) / scale[:, None, :]
    valid = raw.body_valid[1:] & raw.body_valid[:-1]
    candidates = np.argwhere(valid)
    assert len(candidates) > 0
    transition, point = candidates[0]
    current = int(transition + 1)
    expected = body_xy[current, point] - body_xy[current - 1, point]
    start = 350 + int(point) * 2
    np.testing.assert_allclose(features[current, start : start + 2], expected, atol=1e-7)


def test_frozen_segmenter_and_decoder_identities() -> None:
    identity = verify_identities()
    assert identity["all_match"]
    assert identity["feature_contract"]["width"] == 378
    assert identity["decoder"] == {
        "active_decision": "ARGMAX_CLASS_1",
        "short_gap_merge_ms": 150.0,
        "primary_run": (
            "MAX_ACTIVE_PROBABILITY_TIME_INTEGRAL_THEN_DURATION_THEN_EARLIEST"
        ),
        "pre_padding_ms": 250.0,
        "post_padding_ms": 250.0,
        "probability_threshold": None,
    }
    assert all(sha256(path) == expected for path, expected in IDENTITIES.values())


def test_blind_freeze_has_no_comparison_dependency_or_training_call() -> None:
    text = FREEZE_SOURCE.read_text(encoding="utf-8")
    forbidden = (
        "phase4a_gate4a1c_oracle_boundary_replay",
        "recognition_schema_v2",
        "VOCAB_MANIFEST",
        "expected_class",
        ".fit(",
        "train_on_batch",
    )
    assert all(token not in text for token in forbidden)
    assert "decode_event" in text
    assert "model(normalized[None], training=False)" in text


def test_freeze_file_is_write_once(tmp_path: Path) -> None:
    path = tmp_path / "freeze.json"
    freeze_json(path, {"event": 1})
    initial = path.read_bytes()
    freeze_json(path, {"event": 1})
    assert path.read_bytes() == initial
    with pytest.raises(RuntimeError, match="FROZEN_LEARNED_EVENT_MUTATION_REFUSED"):
        freeze_json(path, {"event": 2})


def test_learned_event_freeze_is_hash_checked_and_has_no_labels() -> None:
    events, actual_sha = verify_learned_freeze()
    sidecar = _json(OUT / "learned_events_frozen.sha256.json")
    assert actual_sha == sidecar["sha256"] == _hash(OUT / "learned_events_frozen.json")
    assert events["comparison_inputs_opened"] is False
    assert events["manual_edits"] is False
    assert [row["attempt_id"] for row in events["events"]] == list(ATTEMPTS)
    forbidden_keys = {"expected_gloss", "expected_class", "oracle_start_ms", "oracle_end_ms"}
    assert all(forbidden_keys.isdisjoint(row) for row in events["events"])


def test_oracle_and_recognizer_identities_remain_frozen() -> None:
    _, learned_sha = verify_learned_freeze()
    identities = verify_post_freeze_identities(learned_sha)
    assert identities["oracle"]["actual_sha256"] == EXPECTED_ORACLE_SHA
    assert identities["oracle"]["match"]
    assert all(
        item["actual"] == item["expected"]
        for item in identities["recognizer"].values()
    )


def test_reference_reproduction_matches_governed_results() -> None:
    full = _json(OUT / "recognition_full.json")
    oracle = _json(OUT / "recognition_oracle_reproduced.json")
    assert full["reference_reproduction"]["status"] == "PASS"
    assert oracle["reference_reproduction"]["status"] == "PASS"
    assert full["top1_correct"] == 2
    assert full["expected_in_top5"] == 5
    assert oracle["top1_correct"] == 7
    assert oracle["expected_in_top5"] == 8


def test_final_governance_and_no_unauthorized_operations() -> None:
    decision = _json(OUT / "final_decision.json")
    assert decision["training_executed"] is False
    assert decision["android_modified"] is False
    assert decision["recognition_dev_accessed"] is False
    assert decision["protected_test_accessed"] is False
    assert decision["other_phone_holdout_accessed"] is False
    evaluation_text = EVALUATION_SOURCE.read_text(encoding="utf-8")
    assert ".fit(" not in evaluation_text
    assert "train_on_batch" not in evaluation_text
    assert "CameraX" not in evaluation_text


def test_artifact_population_and_source_hashes_are_consistent() -> None:
    manifest = read_json(OUT / "phone_input_manifest.json")
    assert manifest["attempt_count"] == 10
    assert manifest["attempt_ids"] == list(ATTEMPTS)
    assert manifest["candidate01_rerun"] is False
    assert manifest["timestamp_modification"] is False
    for row in manifest["rows"]:
        path = Path(row["raw_v1_path"])
        assert row["raw_v1_sha256"] == sha256(path)
