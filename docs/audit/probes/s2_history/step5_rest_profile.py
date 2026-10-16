"""Step 5: what does 'rest' look like to S2 in each session? Rows outside reviewed signs,
split by the Android S2 state (PRE vs POST). Raw (un-normalized) 378 features."""
import numpy as np
from common import SESSIONS, load_session, s2r2_rows

def profile(f):
    prop = f[:, 174:176].max(1)
    obs = f[:, 172:174].max(1)
    # ROI centre y of any proposed hand (normalized by height); NaN when none
    ys = np.where(f[:, 174:176] > 0.5, f[:, [177, 180]], np.nan)
    roi_y = np.nanmean(ys, axis=1)
    sh_y = np.where(f[:, 206] * f[:, 207] > 0, (f[:, 183] + f[:, 185]) / 2, np.nan)  # shoulders y
    body_valid = f[:, 206:214].sum(1)
    motion = np.abs(f[:, 342:348]).sum(1)
    return {"n": len(f), "hand_proposal": prop.mean(), "hand_observed": obs.mean(),
            "roi_y": np.nanmedian(roi_y) if np.isfinite(roi_y).any() else np.nan,
            "shoulder_y": np.nanmedian(sh_y) if np.isfinite(sh_y).any() else np.nan,
            "roi_minus_shoulder": np.nanmedian(roi_y - sh_y) if np.isfinite(roi_y - sh_y).any() else np.nan,
            "body_valid_pts": body_valid.mean(), "roi_motion": motion.mean()}

def show(tag, d):
    print(f"  {tag:28s} n={d['n']:4d} proposal={d['hand_proposal']:.2f} observed={d['hand_observed']:.2f} "
          f"roiY={d['roi_y']:.2f} shoulderY={d['shoulder_y']:.2f} roiY-shY={d['roi_minus_shoulder']:+.2f} "
          f"bodyPts={d['body_valid_pts']:.1f} roiMotion={d['roi_motion']:.3f}")

for name in SESSIONS:
    s = load_session(name)
    st = s.android_probs.argmax(1)
    inside = np.zeros(len(st), bool)
    for p in s.positives:
        inside[p.get("attempt_a", p["a"]):p.get("attempt_b", p["b"]) + 1] = True
    print(f"== {name}")
    for k, lab in ((0, "rest rows S2=PRE"), (2, "rest rows S2=POST")):
        m = (~inside) & (st == k)
        if m.sum():
            show(lab, profile(s.features[m]))
print("== S2-R2 FIT training rows by label (BASELINE + PHONE positives, P1 negatives)")
rows = s2r2_rows(role="FIT")
for dom in ("BASELINE_SIGN", "PHONE_POSITIVE", "P1_NEGATIVE"):
    R = [r for r in rows if r["domain"] == dom]
    F = np.concatenate([r["features"] for r in R]); L = np.concatenate([r["labels"] for r in R])
    for k, lab in ((0, "PRE"), (1, "ACTIVE"), (2, "POST")):
        if (L == k).any():
            show(f"{dom[:12]} {lab}", profile(F[L == k]))
