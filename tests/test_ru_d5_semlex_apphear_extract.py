from pathlib import Path

import numpy as np

from pipeline.extract.schema import ClipLandmarks
from pipeline.splits.ru_d5_semlex_apphear_extract import _apply_training_span_policy


def _clip(frames: int) -> ClipLandmarks:
    pose = np.zeros((frames, 33, 4), np.float32)
    pose[:, :, 3] = 1.0
    pose[:, 11, 0] = 0.4
    pose[:, 12, 0] = 0.6
    return ClipLandmarks(
        hands_image=np.full((frames, 2, 21, 3), np.nan, np.float32),
        hands_world=np.full((frames, 2, 21, 3), np.nan, np.float32),
        hand_score=np.zeros((frames, 2), np.float32),
        pose_image=pose,
        pose_world=np.zeros((frames, 33, 3), np.float32),
        pose_score=np.ones((frames,), np.float32),
        timestamps_ms=np.arange(frames, dtype=np.int64) * 33,
    )


def test_invalid_d1_d2_gets_provisional_isolated_fallback(tmp_path: Path) -> None:
    stage = tmp_path / "stage.npz"
    _clip(12).save(stage)
    result = {
        "sample_id": "SEMLEX-TRAIN-WHO1",
        "source_video_id": "WHO1",
        "status": "ok",
        "automatic_recovery_accepted": "false",
        "span_valid": False,
        "n_frames": 12,
        "stage_e_path": str(stage),
        "automatic_rejection_reason": "no_active_run",
    }
    source = {
        "sample_id": "SEMLEX-TRAIN-WHO1",
        "source_video_id": "WHO1",
        "visual_decision": "EXACT_TARGET",
        "candidate_c_variant_gate": "PENDING_APPHEAR_QUALITY",
        "initial_repair_pool_status": "ELIGIBLE_AFTER_APPHEAR_AND_BOUNDARY_GATES",
        "we_come_pair_eligible": "true",
    }
    updated = _apply_training_span_policy(result, source, tmp_path)
    assert updated["training_span_available"] == "true"
    assert updated["training_span_method"] == (
        "REVIEWED_ISOLATED_FULL_CLIP_FALLBACK_V1"
    )
    assert updated["boundary_requires_manual_confirmation"] == "true"
    with np.load(updated["feature_path"], allow_pickle=False) as payload:
        assert payload["feature"].shape == (96, 258)
        assert str(payload["schema_version"]) == "3.0"


def test_acceptable_variant_stays_provisional_when_d1_d2_passes(
    tmp_path: Path,
) -> None:
    result = {
        "sample_id": "SEMLEX-TRAIN-COME1",
        "source_video_id": "COME1",
        "status": "ok",
        "automatic_recovery_accepted": "true",
        "span_path": str(tmp_path / "span.json"),
    }
    source = {
        "sample_id": "SEMLEX-TRAIN-COME1",
        "source_video_id": "COME1",
        "visual_decision": "ACCEPTABLE_VARIANT",
        "candidate_c_variant_gate": "PROVISIONAL_VARIANT_REVIEW_REQUIRED",
        "initial_repair_pool_status": "EXCLUDED_PROVISIONAL_VARIANT",
        "we_come_pair_eligible": "true",
    }
    updated = _apply_training_span_policy(result, source, tmp_path)
    assert updated["training_span_method"] == "CANONICAL_OFFLINE_D1_D2"
    assert updated["candidate_c_variant_gate"] == (
        "PROVISIONAL_VARIANT_REVIEW_REQUIRED"
    )
