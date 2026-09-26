# Runtime Constraints

*(This file occupies the `ui-tokens.md` slot in the Context System convention. For a web app
that slot holds the fixed design values no component may violate. For AppHear 3 it holds the
fixed **on-device physics** no code may violate.)*

These are **measured facts from AppHear v2 (on-device or via offline ablation), plus the
timing budget from the ASL literature.** Treat every number as ground truth. Design around
them; do not re-derive or "optimize" them away. Full detail:
[`../docs/05-v2-lessons-map.md`](../docs/05-v2-lessons-map.md).

---

## The Timing Budget (the constraint everything respects)

| Quantity | Value | Source |
|----------|-------|--------|
| Isolated citation-form sign duration | mean **851 ms** (SD 301) | ASL-LEX 2.0 |
| Shortest signs (e.g. FOUR, STUPID) | **~170–200 ms** | ASL-LEX 2.0 |
| Fluent signing rate | **1.5–2.5 signs/sec** (new sign every ~400–650 ms) | literature |
| Minimum viable pipeline fps | **≥ 15 fps** (hard requirement) | derived from shortest signs |

Below ~15 fps a 200 ms sign spans <3 frames and is physically unresolvable — accuracy is
capped regardless of model quality. If the device can't sustain it, the app enters **degraded
mode** and reports it, rather than emitting garbage windows.

---

## Compute Floor (v2 lesson a)

- **~70% of every frame's time is the hand + pose landmarker models themselves.** This is a
  fixed architectural cost on the target SoC, not a software bug.
- v2 ceiling: parallelizing pose+hands and disabling face took fps **4.37 → 8.10 (+85%)** —
  and that was ~the software ceiling.
- **Do not plan performance around "optimizing the code."** The only real levers:
  1. Lighter landmarker models (`landmarker.backend` is swappable).
  2. Asymmetric **pose cadence** (`pose.cadence`) — run pose less often, hold/interpolate.
     A/B-gated only, because pose *features* are load-bearing (below).
  3. Different hardware.

## Features Are Load-Bearing (v2 lesson b)

- Ablating pose collapsed accuracy **35–83 points** depending on feature block.
- **Never drop pose or hand feature blocks to save compute.** Feature reduction is not a
  latency lever. Cadence (sample rate) is a different axis from presence, and even that is
  A/B-validated before shipping.

## The Window Is the Latency (v2 lesson d)

- v2's 30-frame @ ~8 fps window ≈ **3.7 s ≈ 4× a sign**. Most of it is non-sign frames.
- `MIN_FRAMES` cannot simply be lowered — confidence doesn't stabilize before ~frame 15, so a
  shorter *fixed* window feeds garbage.
- **The only fix is an incremental/streaming architecture** that emits within a sign's
  ~1 s lifetime. Build for streaming from day one; never rebuild the sliding-window state
  machine.

## Device Assumptions Are Traps (v2 lesson g)

- The **GPU delegate caused an ANR** (blocking `createFromOptions` on the main thread) and was
  removed. **CPU / XNNPACK / INT8 is the baseline.** GPU is only ever a flagged,
  off-main-thread, device-measured experiment.
- CameraX rotation offload didn't engage on the device — validate device-level behavior
  before building on it.

## Startup Is Separate (v2 lesson h)

- Model loading cost ~1 s in `onCreate`. **Load models async, off the critical path.** The UI
  comes up in a "warming up" state and the recognizer attaches when ready.

---

## Constraint Checklist (apply to every runtime change)

- [ ] Does it keep the pipeline ≥ 15 fps on the target SoC?
- [ ] Does it avoid dropping any pose/hand feature block?
- [ ] Does it emit incrementally (no fixed multi-second window)?
- [ ] Does it stay off the main thread for load and inference?
- [ ] Does it assume CPU/INT8 (not GPU)?
- [ ] Is per-frame latency reported as p50 **and** p95 (not mean)?

## 2026-09-04 — Governed runtime evidence (not a relaxed product target)

See [P6/P7 history](recognition_upgrade/PROGRESS_THROUGH_P7FA_2026_09_04.md). Minimum useful product cadence stays≥15FPS.
Target: Xiaomi M2101K7AG / SM6150 / Android12. P7 skeleton uses explicitly authorized
FP32 TFLite2.16.1/XNNPACK2threads; this experimental pin does not change the production baseline.

P7C's conditional perception-only screen is p95≤62.7532812ms AND completed processing≥15FPS,
not proof of full S5/S6/S7/UI cadence. No formal memory ceiling exists.
P7D-R2 V3 native compute passed(p95=25.133427ms;40.733333loops/sec).
P7E fixed15 camera-only passed, but integrated capture15FPS versus analyzer/completed14.883333FPS
failed the full screen despite p95=48.6157707ms. Do not round upward, equate reciprocal latency
with delivered FPS, or reclassify the gate. Runtime debt is parked; no automatic tuning/new run.
Exact DWPose-L FP32 flip-test mobile serving is closed on this target, retained offline only.
