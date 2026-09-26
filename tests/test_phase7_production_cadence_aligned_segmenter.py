from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pytest

import eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter as p7
from eval.runtime_diagnostics.phase5_1t_first_segmenter import temporal_labels
from pipeline.perception_vnext.recognition_schema import load_raw_sequence
from pipeline.perception_vnext.segmentation.learned_features import (
    FEATURE_WIDTH,
    derive_causal_segmentation_features,
)


def _population_and_manifest() -> tuple[list[dict], dict[str, dict]]:
    return p7.verify_frozen_inputs()


def test_exact_frozen_population_and_full_raw_hashes() -> None:
    rows, manifest = _population_and_manifest()
    assert len(rows) == 112
    assert sum(row["segmentation_split"] == "SEGMENTATION_TRAIN" for row in rows) == 89
    assert sum(row["segmentation_split"] == "SEGMENTATION_DEV" for row in rows) == 23
    assert len(manifest) == 112
    assert p7.sha256(p7.SELECTED) == p7.EXPECTED_SELECTED_SHA
    assert p7.sha256(p7.SPLIT) == p7.EXPECTED_SPLIT_SHA


def test_fit_cal_split_is_deterministic_grouped_and_excludes_dev() -> None:
    rows, _ = _population_and_manifest()
    first = p7.deterministic_fit_cal_split(rows, 5103)
    second = p7.deterministic_fit_cal_split(rows, 5103)
    assert first == second
    assert first["fit_count"] == 71
    assert first["cal_count"] == 18
    assert first["dev_count"] == 23
    fit = set(first["fit_sample_ids"])
    cal = set(first["cal_sample_ids"])
    dev = set(first["excluded_segmentation_dev_sample_ids"])
    assert not fit & cal
    assert not (fit | cal) & dev
    assert first["all_three_views_grouped_with_original_clip"]


def test_target_intervals_are_exactly_frozen() -> None:
    config = p7.load_config()
    assert [(row["view_id"], row["target_interval_ms"]) for row in config["cadence_views"]] == [
        ("VIEW_A", 133.308),
        ("VIEW_B", 199.962),
        ("VIEW_C", 266.616),
    ]


def test_sparse_sampling_is_deterministic_genuine_unique_and_chronological() -> None:
    rows, manifest = _population_and_manifest()
    row = rows[0]
    raw = load_raw_sequence(Path(manifest[str(row["sample_id"])]["raw_path"]))
    first, offset_first = p7.sparse_observation_indices(
        raw.timestamp_ms, str(row["sample_id"]), "VIEW_B", 199.962
    )
    second, offset_second = p7.sparse_observation_indices(
        raw.timestamp_ms, str(row["sample_id"]), "VIEW_B", 199.962
    )
    np.testing.assert_array_equal(first, second)
    assert offset_first == offset_second
    assert 0 <= offset_first < 199.962
    assert np.all(np.diff(first) > 0)
    assert len(first) == len(np.unique(first))
    np.testing.assert_array_equal(p7.subset_raw(raw, first).timestamp_ms, raw.timestamp_ms[first])


def test_sampling_phase_depends_on_sample_and_view() -> None:
    values = {
        p7.deterministic_offset_ms("sample-a", "VIEW_A", 133.308),
        p7.deterministic_offset_ms("sample-a", "VIEW_B", 199.962),
        p7.deterministic_offset_ms("sample-b", "VIEW_A", 133.308),
    }
    assert len(values) == 3


def test_sparse_deltas_and_dt_use_previous_selected_observation() -> None:
    rows, manifest = _population_and_manifest()
    row = next(item for item in rows if item["source"] == "ASL_CITIZEN")
    raw = load_raw_sequence(Path(manifest[str(row["sample_id"])]["raw_path"]))
    indices, _ = p7.sparse_observation_indices(
        raw.timestamp_ms, str(row["sample_id"]), "VIEW_C", 266.616
    )
    assert np.any(np.diff(indices) > 1)
    sparse = p7.subset_raw(raw, indices)
    features = derive_causal_segmentation_features(sparse)
    expected_dt = np.clip(np.diff(raw.timestamp_ms[indices]) / 1000.0, 0.0, 1.0)
    np.testing.assert_allclose(features[1:, 215], expected_dt, atol=1e-7)

    scale = sparse.source_size.astype(np.float32)
    body_xy = sparse.body_xy.astype(np.float32) / scale[:, None, :]
    valid = sparse.body_valid[1:] & sparse.body_valid[:-1]
    transition, point = np.argwhere(valid)[0]
    current = int(transition + 1)
    expected_delta = body_xy[current, point] - body_xy[current - 1, point]
    start = 350 + int(point) * 2
    np.testing.assert_allclose(features[current, start : start + 2], expected_delta, atol=1e-7)


def test_human_boundaries_only_change_labels_not_sampling_or_features() -> None:
    rows, manifest = _population_and_manifest()
    row = rows[0]
    manifest_row = manifest[str(row["sample_id"])]
    view = {"view_id": "VIEW_A", "target_interval_ms": 133.308}
    first = p7.make_view(row, manifest_row, view, 100.0)
    changed = dict(row)
    changed["human_sign_start_ms"] = float(row["human_sign_start_ms"]) + 50.0
    changed["human_sign_end_ms"] = float(row["human_sign_end_ms"]) + 50.0
    second = p7.make_view(changed, manifest_row, view, 100.0)
    np.testing.assert_array_equal(first["selected_indices"], second["selected_indices"])
    np.testing.assert_array_equal(first["features"], second["features"])
    assert not np.array_equal(first["labels"], second["labels"])


def test_ignore_band_policy_is_exactly_100_ms() -> None:
    timestamps = np.asarray([799, 800, 900, 1000, 1100, 1200, 1201], np.float64)
    labels = temporal_labels(timestamps, 900.0, 1100.0, 100.0)
    assert labels.tolist() == [0, -1, -1, -1, -1, -1, 2]
    assert p7.load_config()["labels"]["ignore_band_ms"] == 100.0


def test_feature_width_and_model_contract_remain_unchanged() -> None:
    config = p7.load_config()
    assert FEATURE_WIDTH == 378
    assert config["features"]["schema"] == "apphear.perception_vnext.segmentation_features.v1"
    assert config["model"]["dilations"] == [1, 2, 4, 8]
    assert config["model"]["dropout"] == 0.2


def test_prepare_normalization_uses_fit_views_only() -> None:
    source = inspect.getsource(p7.prepare)
    assert 'row["phase7_partition"] == "FIT"' in source
    assert "normalization_from_train(fit_features)" in source
    assert '"cal_influenced_statistics": False' in source
    assert '"dev_influenced_statistics": False' in source
    assert '"phase6_phone_influenced_statistics": False' in source


def test_checkpoint_selection_uses_cal_only_and_not_dev() -> None:
    source = inspect.getsource(p7.train)
    assert '_load_view_rows({"FIT"})' in source
    assert '_load_view_rows({"CAL"})' in source
    assert "predict_rows(self.model, cal_rows, config)" in source
    assert '_load_view_rows({"DEV"})' not in source
    assert '"dev_evaluated_during_training": False' in source


def test_no_candidate01_rerun_recognizer_training_or_android_mutation() -> None:
    source = Path(p7.__file__).read_text(encoding="utf-8")
    assert "Candidate01Offline" not in source
    assert "extract_video" not in source
    assert "save_raw_sequence" not in source
    assert "RecognitionV2" not in inspect.getsource(p7.train)
    assert "recognizer" not in inspect.getsource(p7.train).lower()
    assert "android/" not in source
    assert p7.load_config()["governance"]["recognizer_training"] is False


def test_phase6_phone_is_excluded_from_prepare_and_training() -> None:
    assert "PHONE_SESSION" not in inspect.getsource(p7.prepare)
    assert "PHONE_SESSION" not in inspect.getsource(p7.train)
    assert "phone_replay_used_during_training" in inspect.getsource(p7.train)


def test_protected_populations_are_not_referenced() -> None:
    config = p7.load_config()
    assert config["governance"]["recognition_dev_access"] is False
    assert config["governance"]["protected_test_access"] is False
    assert config["governance"]["sealed_phone_holdout_access"] is False
    source = Path(p7.__file__).read_text(encoding="utf-8")
    assert "attempt_004/" not in source
    assert "protected_test" not in source.lower()


def test_phone_replay_is_guarded_by_sparse_dev_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    original = p7.read_json

    def guarded(path: Path) -> dict:
        if Path(path).name == "sparse_dev_event_metrics.json":
            return {"gate": {"passed": False}}
        return original(path)

    monkeypatch.setattr(p7, "read_json", guarded)
    with pytest.raises(RuntimeError, match="SPARSE_DEV_GATE_FAILED"):
        p7.phone_replay()
