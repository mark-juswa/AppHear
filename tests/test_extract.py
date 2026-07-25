"""Stage-E tests.

Unit tests (fast, no models/dataset): schema round-trip + validation, config hashing,
missing-data convention, manifest resumability, hit-rate math.

Integration test (needs fetched models + the ASL Citizen dataset): runs the real extractor on
one clip and checks the contract. Skipped automatically when assets/dataset are absent."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from pipeline.extract.config import load_config
from pipeline.extract.constants import NUM_HAND_LANDMARKS, NUM_HANDS, NUM_POSE_LANDMARKS
from pipeline.extract.manifest import ManifestWriter, clip_id, load_done
from pipeline.extract.run import _hit_rates
from pipeline.extract.schema import ClipLandmarks, ClipSidecar

CONFIG_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "config" / "extract.yaml"


def _make_clip(t: int) -> ClipLandmarks:
    return ClipLandmarks(
        hands_image=np.zeros((t, NUM_HANDS, NUM_HAND_LANDMARKS, 3), np.float32),
        hands_world=np.zeros((t, NUM_HANDS, NUM_HAND_LANDMARKS, 3), np.float32),
        hand_score=np.zeros((t, NUM_HANDS), np.float32),
        pose_image=np.zeros((t, NUM_POSE_LANDMARKS, 4), np.float32),
        pose_world=np.zeros((t, NUM_POSE_LANDMARKS, 3), np.float32),
        pose_score=np.zeros((t,), np.float32),
        timestamps_ms=np.arange(t, dtype=np.int64),
    )


# --- schema -------------------------------------------------------------------------------


def test_clip_roundtrip(tmp_path: Path) -> None:
    clip = _make_clip(5)
    clip.hands_image[0, 0, 0, 0] = np.nan  # missing-data sentinel survives round-trip
    path = tmp_path / "clip.npz"
    clip.save(path)
    loaded = ClipLandmarks.load(path)
    assert loaded.timestamps_ms.shape == (5,)
    assert loaded.pose_image.shape == (5, NUM_POSE_LANDMARKS, 4)
    assert np.isnan(loaded.hands_image[0, 0, 0, 0])
    assert loaded.hands_image.dtype == np.float32


def test_validate_rejects_bad_shape() -> None:
    clip = _make_clip(4)
    clip.pose_world = np.zeros((4, NUM_POSE_LANDMARKS, 2), np.float32)  # wrong last dim
    with pytest.raises(ValueError, match="pose_world"):
        clip.validate()


def test_sidecar_roundtrip(tmp_path: Path) -> None:
    sidecar = ClipSidecar(
        schema_stage="E",
        extraction_version="e1",
        model_config_hash="abc123",
        mediapipe_version="0.10",
        source="asl_citizen",
        split="val",
        participant_id="P42",
        gloss="APPLE",
        asl_lex_code="A_03_054",
        video_file="x-APPLE.mp4",
        native_fps=30.0,
        n_frames=45,
        frame_width=640,
        frame_height=480,
        hand_hit_rate=0.9,
        two_hand_hit_rate=0.4,
        pose_hit_rate=1.0,
    )
    path = tmp_path / "clip.json"
    sidecar.save(path)
    assert ClipSidecar.load(path) == sidecar


# --- config -------------------------------------------------------------------------------


def test_config_hash_is_stable_and_variant_sensitive() -> None:
    cfg = load_config(CONFIG_PATH)
    assert cfg.model_config_hash == load_config(CONFIG_PATH).model_config_hash
    # switching the pose model name must change the hash (parity guard)
    import dataclasses

    swapped = dataclasses.replace(
        cfg, pose_task=cfg.pose_task.with_name("pose_landmarker_full.task")
    )
    assert swapped.model_config_hash != cfg.model_config_hash


def test_config_points_at_lite_pose() -> None:
    cfg = load_config(CONFIG_PATH)
    assert "lite" in cfg.pose_task.name.lower()  # locked decision


# --- hit rates + missing-data -------------------------------------------------------------


def test_hit_rates() -> None:
    clip = _make_clip(4)
    clip.hand_score[:, 0] = [1.0, 1.0, 0.0, 0.0]  # left hand present in 2/4
    clip.hand_score[:, 1] = [1.0, 0.0, 0.0, 0.0]  # right hand present in 1/4
    clip.pose_score[:] = [1.0, 1.0, 1.0, 0.0]
    any_hand, both_hands, pose = _hit_rates(clip)
    assert any_hand == pytest.approx(0.5)  # frames with >=1 hand: 2/4
    assert both_hands == pytest.approx(0.25)  # both hands: 1/4
    assert pose == pytest.approx(0.75)


def test_hit_rates_empty_clip() -> None:
    assert _hit_rates(_make_clip(0)) == (0.0, 0.0, 0.0)


# --- manifest resumability ----------------------------------------------------------------


def test_manifest_resumability(tmp_path: Path) -> None:
    path = tmp_path / "manifest_val.csv"
    with ManifestWriter(path) as m:
        m.append({"clip_id": "aaa", "status": "ok"})
        m.append({"clip_id": "bbb", "status": "failed", "reason": "boom"})
    done = load_done(path)
    assert done == {"aaa"}  # only successful clips are skipped on resume


def test_clip_id() -> None:
    assert clip_id("000123-APPLE.mp4") == "000123-APPLE"


# --- health sampler -----------------------------------------------------------------------


def test_health_sample_is_cross_signer_and_deterministic(tmp_path: Path) -> None:
    import dataclasses

    from pipeline.extract import health

    splits = tmp_path / "splits"
    splits.mkdir()
    with (splits / "val.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Participant ID", "Video file", "Gloss", "ASL-LEX Code"])
        for pid in ("P1", "P2", "P3"):
            for k in range(4):
                w.writerow([pid, f"{pid}-{k}-X.mp4", "X", "A_00_000"])

    cfg = dataclasses.replace(load_config(CONFIG_PATH), dataset_root=tmp_path)
    picked = health._sample(cfg, "val", participants=2, per=2, seed=0)
    pids = {r["Participant ID"] for r in picked}
    assert len(picked) == 4 and len(pids) == 2  # 2 signers x 2 clips, spans signers
    again = health._sample(cfg, "val", participants=2, per=2, seed=0)
    assert [r["Video file"] for r in picked] == [r["Video file"] for r in again]  # deterministic


# --- integration (needs models + dataset) -------------------------------------------------


def test_real_extraction_contract() -> None:
    cfg = load_config(CONFIG_PATH)
    if not (cfg.hand_task.exists() and cfg.pose_task.exists()):
        pytest.skip("model assets not fetched (run python -m pipeline.extract.assets)")
    split_csv = cfg.splits_dir / "val.csv"
    if not split_csv.exists():
        pytest.skip("ASL Citizen dataset not available")

    import csv as _csv

    from pipeline.extract.landmarks import LandmarkExtractor

    with split_csv.open("r", encoding="utf-8", newline="") as fh:
        row = next(_csv.DictReader(fh))
    video_path = cfg.videos_dir / row["Video file"]
    if not video_path.exists():
        pytest.skip("sample video missing")

    with LandmarkExtractor(cfg) as ex:
        clip, meta = ex.extract(video_path)
    clip.validate()
    assert meta["n_frames"] > 0
    assert clip.pose_image.shape[1:] == (NUM_POSE_LANDMARKS, 4)
    assert clip.hands_image.shape[1:] == (NUM_HANDS, NUM_HAND_LANDMARKS, 3)
