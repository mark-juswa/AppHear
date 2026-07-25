"""Named MediaPipe landmark indices. Shared across stages so nobody hardcodes 15/16 etc.
These are fixed properties of the MediaPipe pose model — never configurable."""

from __future__ import annotations

# Pose (33 landmarks)
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24

# Convenience groups
SHOULDERS = (LEFT_SHOULDER, RIGHT_SHOULDER)
HIPS = (LEFT_HIP, RIGHT_HIP)
WRISTS = (LEFT_WRIST, RIGHT_WRIST)
ELBOWS = (LEFT_ELBOW, RIGHT_ELBOW)

# Left/right symmetric pose-landmark pairs, used to swap sides when mirroring (N3 handedness).
POSE_MIRROR_PAIRS: tuple[tuple[int, int], ...] = (
    (1, 4),
    (2, 5),
    (3, 6),  # eyes
    (7, 8),  # ears
    (9, 10),  # mouth
    (11, 12),
    (13, 14),
    (15, 16),  # shoulders, elbows, wrists
    (17, 18),
    (19, 20),
    (21, 22),  # pinky, index, thumb
    (23, 24),
    (25, 26),
    (27, 28),
    (29, 30),
    (31, 32),  # hips, knees, ankles, heels, feet
)


def pose_mirror_perm() -> list[int]:
    """Index permutation that swaps every left/right pose pair (nose stays put)."""
    perm = list(range(33))
    for a, b in POSE_MIRROR_PAIRS:
        perm[a], perm[b] = b, a
    return perm


# Named pose landmarks selectable from config (motion.landmarks).
POSE_NAME_TO_INDEX: dict[str, int] = {
    "left_shoulder": LEFT_SHOULDER,
    "right_shoulder": RIGHT_SHOULDER,
    "left_elbow": LEFT_ELBOW,
    "right_elbow": RIGHT_ELBOW,
    "left_wrist": LEFT_WRIST,
    "right_wrist": RIGHT_WRIST,
    "left_hip": LEFT_HIP,
    "right_hip": RIGHT_HIP,
}
