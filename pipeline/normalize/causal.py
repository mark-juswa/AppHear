"""Causal (streaming) variant of N1-N3 param estimation.

Offline `normalize_clip` computes the three clip-constant params (scale, roll, mirror) once from
the WHOLE span, then applies them to every frame. On-device we don't have the whole span yet: at
frame t we can only estimate from [onset..t]. Scale and roll use running medians (stable, converge
to the offline value). MIRROR is the hard one: a binary handedness flip that inverts the x-axis, so
a flip AFTER commit is catastrophic. Investigation (scratchpad, on test): only ~21% of clips are
mirrored; the offline margin sits right at epsilon (median 0.15) so the naive per-frame decision
flips constantly; but truly-left clips become DECISIVE (left-margin >= ~0.3) by ~frame 0.1-0.27 of
the span, before the ~0.39 commit. So the policy: default no-mirror, switch to mirror only on a
DECISIVE, confirmed left-dominance margin, then FREEZE. Right/symmetric clips never trip it.

Reuses the SAME scale/roll/center helpers as `transforms.py` so those can't drift; only the WINDOW
(causal [onset..t]) and the mirror policy differ."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from ..topology import LEFT_WRIST, RIGHT_WRIST, pose_mirror_perm
from .config import NormalizeConfig
from .scale import clip_scale
from .transforms import NormParams, _shoulder_angle, _torso_center_xy, _transform_block

_MIRROR_PERM = pose_mirror_perm()
DEFAULT_CAUSAL_CONFIG = Path(__file__).resolve().parents[1] / "config" / "causal.yaml"


@dataclass(frozen=True)
class CausalConfig:
    """Streaming param-estimation policy. Scale/roll use running medians (stable). Mirror defaults
    to no-mirror and only flips (then freezes) on decisive, confirmed left-dominance. Thresholds
    from the mirror-policy sweep (scratchpad): (0.30, 0.15, 4) matched the offline 21% mirror rate
    at ~88% agreement — the causal ceiling (partial motion can't fully resolve handedness)."""

    mirror_decisive_margin: float  # signed (cum_L-cum_R)/(cum_L+cum_R) ratio for decisive-left
    mirror_min_abs_diff: float  # ALSO require an absolute left lead — kills early tiny-motion noise
    mirror_confirm_k: int  # both conditions must hold this many consecutive frames before freezing


def load_causal_config(path: Path = DEFAULT_CAUSAL_CONFIG) -> CausalConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return CausalConfig(
        mirror_decisive_margin=float(raw["mirror_decisive_margin"]),
        mirror_min_abs_diff=float(raw["mirror_min_abs_diff"]),
        mirror_confirm_k=int(raw["mirror_confirm_k"]),
    )


class MirrorStabilizer:
    """Default no-mirror. Freeze to MIRROR the first time left-dominance is decisive — ratio
    (cum_L-cum_R)/(cum_L+cum_R) >= `decisive_margin` AND absolute lead (cum_L-cum_R) >= `min_abs`
    (the abs guard rejects early tiny-motion noise) — held for `confirm_k` consecutive frames. Once
    frozen it never changes (no post-commit flip); right/symmetric clips never trip it, matching the
    offline canonical no-mirror default."""

    def __init__(self, decisive_margin: float, min_abs: float, confirm_k: int) -> None:
        self._m, self._abs, self._k = decisive_margin, min_abs, confirm_k
        self._frozen = False
        self._streak = 0

    def update(self, cum_l: float, cum_r: float) -> bool:
        if self._frozen:
            return True
        diff, total = cum_l - cum_r, cum_l + cum_r
        if total > 0 and diff >= self._abs and diff / total >= self._m:
            self._streak += 1
            if self._streak >= self._k:
                self._frozen = True
        else:
            self._streak = 0
        return self._frozen


def normalize_clip_causal(
    hands_image: np.ndarray,
    pose_image: np.ndarray,
    onset: int,
    release: int,
    cfg: NormalizeConfig,
    ccfg: CausalConfig,
) -> tuple[np.ndarray, np.ndarray, list[NormParams]]:
    """Per-frame causal normalization over the span. Returns (hands_norm (L,2,21,3),
    pose_norm (L,33,4), per_frame_params [L]). Each frame i uses scale/roll from a running median
    over [0..i] and the frozen-once-decisive mirror decision."""
    t = pose_image.shape[0]
    if onset < 0:
        onset, release = 0, t - 1
    span_pose = pose_image[onset : release + 1]  # (L,33,4)
    span_hands = hands_image[onset : release + 1]  # (L,2,21,3)
    length = span_pose.shape[0]
    do_center = cfg.n1_scale or cfg.n2_roll or cfg.n3_handedness

    pose_out = np.empty((length, span_pose.shape[1], span_pose.shape[2]), np.float32)
    hands_out = np.empty((length, 2, 21, 3), np.float32)
    per_frame: list[NormParams] = []
    stabilizer = MirrorStabilizer(
        ccfg.mirror_decisive_margin, ccfg.mirror_min_abs_diff, ccfg.mirror_confirm_k
    )
    cum_l = cum_r = 0.0  # running cumulative wrist motion (left / right), for the mirror margin
    prev_l = span_pose[0, LEFT_WRIST, :2]
    prev_r = span_pose[0, RIGHT_WRIST, :2]

    for i in range(length):
        win = span_pose[: i + 1]  # causal window [0..i]
        s = clip_scale(win) if cfg.n1_scale else 1.0
        theta = _shoulder_angle(win) if cfg.n2_roll else 0.0
        if cfg.n3_handedness:
            if i > 0:
                lw, rw = span_pose[i, LEFT_WRIST, :2], span_pose[i, RIGHT_WRIST, :2]
                # widen to float64 BEFORE subtracting so the cumulative sum (and thus the mirror
                # decision) is bit-parity with the Kotlin S4 port (which widens then subtracts).
                dl = float(np.linalg.norm(lw.astype(np.float64) - prev_l.astype(np.float64)))
                dr = float(np.linalg.norm(rw.astype(np.float64) - prev_r.astype(np.float64)))
                if np.isfinite(dl):
                    cum_l += dl
                if np.isfinite(dr):
                    cum_r += dr
                prev_l, prev_r = lw, rw
            mirrored = stabilizer.update(cum_l, cum_r)
            dominant = "Left" if mirrored else "Right"
        else:
            mirrored, dominant = False, "Right"

        center_i = (
            _torso_center_xy(win)[-1:] if do_center else np.zeros((1, 2), np.float32)
        )
        pose_i = _transform_block(
            span_pose[i : i + 1], center_i, s, theta, do_center, cfg.n1_scale, cfg.n2_roll
        )
        hands_i = _transform_block(
            span_hands[i : i + 1].reshape(1, -1, 3), center_i, s, theta,
            do_center, cfg.n1_scale, cfg.n2_roll,
        ).reshape(1, 2, 21, 3)
        if mirrored:
            pose_i[..., 0] *= -1.0
            hands_i[..., 0] *= -1.0
            pose_i = pose_i[:, _MIRROR_PERM, :]
            hands_i = hands_i[:, ::-1, :, :]

        pose_out[i] = pose_i[0]
        hands_out[i] = hands_i[0]
        per_frame.append(
            NormParams(scale=s, roll_angle=theta, dominant=dominant, mirrored=mirrored)
        )

    return hands_out, pose_out, per_frame


def mirror_flip_summary(per_frame: list[NormParams]) -> tuple[int, int]:
    """(#mirror flips over the span, last-flip frame index or -1). With the freeze policy there is
    at most one flip (no-mirror -> mirror); we still track it to correlate with the commit frame."""
    m = np.array([p.mirrored for p in per_frame], dtype=bool)
    if m.size < 2:
        return 0, -1
    changes = np.nonzero(m[1:] != m[:-1])[0] + 1
    return int(changes.size), int(changes[-1]) if changes.size else -1
