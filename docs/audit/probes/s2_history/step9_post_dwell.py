"""Step 9: after each committed event: decoder READY time vs when S2 itself first leaves POST.
Continuous sessions only (SEP23 sessions contain 20-130 s capture pauses between attempts)."""
import numpy as np
from common import Decoder, load_session
rows = []
for name in ("SEP27_TRANSITION", "OCT15_COMPACT"):
    s = load_session(name); st = s.android_probs.argmax(1); t = s.timestamps_ms
    d = Decoder(); states = [d.consume(float(a), int(b)) for a, b in zip(t, st)]
    for e in d.events:
        c = e["commit"]
        idle = next(i for i in range(c + 1, len(st)) if states[i] == "IDLE")
        leave = next(i for i in range(c, len(st)) if st[i] != 2)
        rows.append((name, c, t[idle] - t[c], idle - c, t[leave] - t[c], leave - c, "PRE" if st[leave] == 0 else "ACTIVE"))
        print(f"  {name:18s} commit row {c:4d}: READY after {t[idle]-t[c]:5.0f} ms ({idle-c} obs); "
              f"S2 leaves POST after {t[leave]-t[c]:5.0f} ms ({leave-c} obs) -> {rows[-1][-1]}")
r = np.asarray([x[2] for x in rows]); l = np.asarray([x[4] for x in rows]); lo = np.asarray([x[5] for x in rows])
print(f"median READY {np.median(r):.0f} ms; median S2-leaves-POST {np.median(l):.0f} ms ({np.median(lo):.0f} obs); "
      f"S2 still in POST when READY shown: {int(np.sum(l > r))}/{len(r)}")
