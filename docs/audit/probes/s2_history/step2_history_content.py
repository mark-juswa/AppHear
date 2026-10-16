"""Step 2: what is in the history before each reviewed sign, and does it predict acquisition?"""
import numpy as np

from common import ACTIVE, POST, PRE, SESSIONS, load_session

# feature indices (segmentation_features.v1 layout, see PhoneCausalCore.kt derive())
HAND_OBSERVED = [172, 173]          # 168:presence(2) 170:presence-finite(2) 172:observed(2)
BODY_AVAILABLE = 214              # 182 body xy(16), 198 support(8), 206 valid(8), 214 available, 215 dt
HAND_Y = [2 * j + 1 for j in range(42)]  # left then right y coordinates (0..83)

print("Per reviewed sign: S2 state mix in the 10 observations before onset (Android, rolling),"
      " and acquisition result")
rows = []
for name in SESSIONS:
    s = load_session(name)
    st = s.android_probs.argmax(1)
    whole = np.bincount(st, minlength=3) / len(st)
    print(f"\n== {name}: whole-session state share PRE/ACTIVE/POST = "
          f"{whole[0]:.2f}/{whole[1]:.2f}/{whole[2]:.2f}; body_available share={s.features[:, BODY_AVAILABLE].mean():.2f}")
    for p in s.positives:
        a = p["a"]
        hist = st[max(0, a - 10):a]
        pre_share = float(np.mean(hist == PRE)) if len(hist) else float("nan")
        post_share = float(np.mean(hist == POST)) if len(hist) else float("nan")
        hands_hist = s.features[max(0, a - 10):a][:, HAND_OBSERVED].sum(1).mean()
        acquired = int(sum(st[i] == ACTIVE for i in p["active_rows"])) > 0
        rows.append((name, p["name"], p["judgment"], pre_share, post_share, acquired))
        print(f"  {p['name']:32s} prev10 PRE={pre_share:.1f} POST={post_share:.1f} "
              f"state@onset-1={'PRE ACT POST'.split()[st[a - 1]]:4s} hands/obs prev10={hands_hist:.1f} "
              f"acquired={acquired}")

genuine = [r for r in rows if r[2] == "GENUINE_SIGN"]
pre_led = [r for r in genuine if r[3] >= 0.5]
post_led = [r for r in genuine if r[4] > 0.5]
print("\nGenuine signs:", len(genuine))
print(f"  history mostly PRE  : acquired {sum(r[5] for r in pre_led)}/{len(pre_led)}")
print(f"  history mostly POST : acquired {sum(r[5] for r in post_led)}/{len(post_led)}")
