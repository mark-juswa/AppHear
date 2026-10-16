"""Read-only: hand acceptance rate versus DWPose ROI speed (proxy for motion blur)."""
import sys
from pathlib import Path

import numpy as np


def load(session):
    p = Path(session) / "s2_exact_parity"
    n = len(np.fromfile(p / "source_index.i32", dtype=np.int32))
    ts = np.fromfile(p / "timestamp_ms.f64", dtype=np.float64)
    roi = np.fromfile(p / "raw_hand_roi_center_side.f32", dtype=np.float32).reshape(n, 2, 3)
    prop = np.fromfile(p / "raw_hand_proposal_present.u8", dtype=np.uint8).reshape(n, 2)
    obs = np.fromfile(p / "raw_hand_observed.u8", dtype=np.uint8).reshape(n, 2)
    pres = np.fromfile(p / "raw_hand_presence.f32", dtype=np.float32).reshape(n, 2)
    return ts, roi, prop, obs, pres


bins = [0, 100, 250, 500, 1000, 1e9]
rows = []
for session in sys.argv[1:]:
    ts, roi, prop, obs, pres = load(session)
    for i in range(1, len(ts)):
        dt = (ts[i] - ts[i - 1]) / 1000.0
        if dt <= 0 or dt > 0.6:
            continue
        for s in range(2):
            if prop[i, s] and prop[i - 1, s] and obs[i - 1, s]:
                d = np.hypot(*(roi[i, s, :2] - roi[i - 1, s, :2]))
                # speed in ROI-side units per second (scale-free across distance)
                side = max(float(roi[i, s, 2]), 1.0)
                rows.append((d / dt / side * 100.0, obs[i, s], pres[i, s]))
rows = np.asarray(rows)
print("slots with consecutive proposals:", len(rows))
for lo, hi in zip(bins[:-1], bins[1:]):
    m = (rows[:, 0] >= lo) & (rows[:, 0] < hi)
    if m.sum():
        print(f"ROI speed {lo:>5.0f}-{hi if hi < 1e8 else 'inf':>5} %side/s: n={m.sum():4d} "
              f"accepted={rows[m, 1].mean():.3f} median_presence={np.nanmedian(rows[m, 2]):.3f}")
