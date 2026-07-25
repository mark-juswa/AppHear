"""Stage D1/D2 tests — scale helper, signals, hysteresis span state machine, schema, config.
All pure/synthetic: no models or dataset needed."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pipeline.detect.config import load_config
from pipeline.detect.schema import SpanSidecar
from pipeline.detect.signals import Signals, compute_signals
from pipeline.detect.span import _longest_run, detect_span
from pipeline.extract.constants import NUM_HAND_LANDMARKS, NUM_HANDS, NUM_POSE_LANDMARKS
from pipeline.extract.schema import ClipLandmarks
from pipeline.normalize.scale import clip_scale, shoulder_width_frame
from pipeline.topology import (
    LEFT_ELBOW,
    LEFT_HIP,
    LEFT_SHOULDER,
    LEFT_WRIST,
    RIGHT_ELBOW,
    RIGHT_HIP,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
)

CONFIG_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "config" / "detect.yaml"


def _cfg(**overrides: object):
    """Fixed thresholds for unit tests, so calibrating detect.yaml never breaks them."""
    import dataclasses

    base = dataclasses.replace(
        load_config(CONFIG_PATH),
        theta_on=0.04,
        theta_off=0.02,
        k_on=3,
        k_off=4,
        backoff=2,
        min_span_frames=8,
        smoothing_window=3,
    )
    return dataclasses.replace(base, **overrides) if overrides else base


def _pose_frame() -> np.ndarray:
    """One pose frame: shoulders width 0.2, hips at y=0.7, everything else NaN by default."""
    p = np.full((NUM_POSE_LANDMARKS, 4), np.nan, np.float32)
    p[LEFT_SHOULDER, :2] = (0.4, 0.3)
    p[RIGHT_SHOULDER, :2] = (0.6, 0.3)
    p[LEFT_HIP, :2] = (0.45, 0.7)
    p[RIGHT_HIP, :2] = (0.55, 0.7)
    return p


def _synth_clip(signing: list[bool]) -> ClipLandmarks:
    """Clip where 'signing' frames have wrists raised and moving; rest frames have wrists down
    and still. Hands are ALL absent (NaN) to prove pose-only detection is robust."""
    t = len(signing)
    pose = np.stack([_pose_frame() for _ in range(t)])
    for i, on in enumerate(signing):
        wy = 0.40 if on else 0.72  # raised (< hip 0.7) vs down
        wx = 0.5 + (0.03 * (i % 2) if on else 0.0)  # oscillate => per-frame motion
        for w, e in ((LEFT_WRIST, LEFT_ELBOW), (RIGHT_WRIST, RIGHT_ELBOW)):
            pose[i, w, :2] = (wx, wy)
            pose[i, e, :2] = (wx, (wy + 0.3) / 1.0)  # elbow below wrist, follows x
    return ClipLandmarks(
        hands_image=np.full((t, NUM_HANDS, NUM_HAND_LANDMARKS, 3), np.nan, np.float32),
        hands_world=np.full((t, NUM_HANDS, NUM_HAND_LANDMARKS, 3), np.nan, np.float32),
        hand_score=np.zeros((t, NUM_HANDS), np.float32),
        pose_image=pose,
        pose_world=np.zeros((t, NUM_POSE_LANDMARKS, 3), np.float32),
        pose_score=np.ones((t,), np.float32),
        timestamps_ms=np.arange(t, dtype=np.int64),
    )


# --- scale --------------------------------------------------------------------------------


def test_shoulder_width_frame() -> None:
    assert shoulder_width_frame(_pose_frame()) == pytest.approx(0.2, abs=1e-6)


def test_clip_scale_median() -> None:
    clip = _synth_clip([False, True, True])
    assert clip_scale(clip.pose_image) == pytest.approx(0.2, abs=1e-6)


def test_clip_scale_all_nan_falls_back_to_one() -> None:
    pose = np.full((3, NUM_POSE_LANDMARKS, 4), np.nan, np.float32)
    assert clip_scale(pose) == 1.0


# --- span hysteresis (hand-built signals) -------------------------------------------------


def test_detect_span_basic() -> None:
    cfg = _cfg()  # theta_on=.04 theta_off=.02 k_on=3 k_off=4 backoff=2 min=8
    motion = np.array([0.0] * 6 + [0.1] * 8 + [0.0] * 6)
    gate = np.ones(motion.shape[0], dtype=bool)
    span = detect_span(Signals(motion, gate, 0.2), cfg)
    assert span.valid
    assert span.n_signing_frames == 8
    assert span.onset == 6 - cfg.backoff  # 4
    assert span.release == 13 + cfg.backoff  # 15


def test_detect_span_too_short_is_invalid() -> None:
    cfg = _cfg()
    motion = np.array([0.0] * 6 + [0.1] * 5 + [0.0] * 9)
    span = detect_span(Signals(motion, np.ones(20, bool), 0.2), cfg)
    assert not span.valid and "too_short" in span.reason


def test_detect_span_no_signing() -> None:
    cfg = _cfg()
    span = detect_span(Signals(np.zeros(20), np.ones(20, bool), 0.2), cfg)
    assert not span.valid and span.reason == "no_signing_detected"


def test_gate_blocks_entry() -> None:
    cfg = _cfg()
    motion = np.array([0.0] * 6 + [0.1] * 8 + [0.0] * 6)
    span = detect_span(Signals(motion, np.zeros(20, bool), 0.2), cfg)  # gate always closed
    assert not span.valid  # high motion but never in signing space


def test_longest_run() -> None:
    mask = np.array([1, 1, 0, 1, 1, 1, 0], dtype=bool)
    assert _longest_run(mask) == (3, 5, 3)


# --- compute_signals on a synthetic clip (pose-only, hands absent) ------------------------


def test_compute_signals_detects_pose_motion_without_hands() -> None:
    cfg = _cfg()
    signing = [False] * 5 + [True] * 10 + [False] * 10  # ample trailing rest for clean exit
    clip = _synth_clip(signing)
    sig = compute_signals(
        clip, cfg.pose_landmarks, cfg.hand_aux_weight, cfg.raise_margin, cfg.smoothing_window
    )
    assert sig.scale == pytest.approx(0.2, abs=1e-6)
    assert sig.gate[7:13].all()  # raised during signing
    assert not sig.gate[:5].any()  # down during rest
    span = detect_span(sig, cfg)
    assert span.valid  # a real span found from pose alone (hands were all NaN)
    assert span.onset <= 8  # caught the onset
    assert span.release >= 14  # covered the sign
    assert span.release < len(signing) - 1  # AND trimmed trailing dead time


# --- schema / config ----------------------------------------------------------------------


def test_span_sidecar_roundtrip(tmp_path: Path) -> None:
    s = SpanSidecar(
        detect_version="d1",
        params_hash="deadbeef",
        clip_id="x-APPLE",
        split="val",
        participant_id="P5",
        gloss="APPLE",
        asl_lex_code="A_03_054",
        n_frames=90,
        native_fps=30.0,
        onset=20,
        release=55,
        valid=True,
        reason="",
        n_signing_frames=32,
        span_duration_s=1.2,
        shoulder_scale=0.21,
        in_span_hand_rate=0.8,
        out_span_hand_rate=0.1,
        motion_p50=0.03,
        motion_p90=0.12,
    )
    path = tmp_path / "x.span.json"
    s.save(path)
    assert SpanSidecar.load(path) == s


def test_config_theta_ordering_validated(tmp_path: Path) -> None:
    import yaml

    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["hysteresis"]["theta_off"] = raw["hysteresis"]["theta_on"] + 1  # invalid
    bad = tmp_path / "detect.yaml"
    bad.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="theta_off"):
        load_config(bad)


def test_params_hash_changes_with_thresholds(tmp_path: Path) -> None:
    import dataclasses

    cfg = load_config(CONFIG_PATH)
    assert dataclasses.replace(cfg, theta_on=cfg.theta_on + 0.01).params_hash != cfg.params_hash
