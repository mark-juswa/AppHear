# Hand detection and tracking latency investigation (BUG-001 duplicate hands, BUG-002 overlay lag)

Date: 2026-11-10 · Branch `jepjep-claude` · **nothing committed**. Supersedes the diagnostic notes in
[`BUG_DUPLICATE_HAND_DETECTION.md`](BUG_DUPLICATE_HAND_DETECTION.md).

## Status — read this first
**Neither bug is verified fixed, and neither root cause is confirmed by measurement. No fix has been implemented.**
The brief says the previous diagnostics were run on a physical device and asks me to use those logs. **No log reached me**: no device is
attached to this machine and no log file exists on it (checked `adb devices`, the repo, Downloads, Desktop, /private/tmp). I have therefore
not analysed any device data and do not claim any measured number below. What this round delivers: a code-level trace of both bugs, a
sharper instrumentation set that discriminates between the candidate causes in one phone run, a debug APK containing it, and the test
protocol. Evidence labels: CONFIRMED-CODE (read in source), REPO-REPORTED (earlier repo/phase measurements, not re-measured now),
UNMEASURED (needs the phone).

## 1. BUG-001 duplicate hands — what is established

CONFIRMED-CODE: two independent hand proposals, no cross-check.

| Stage | Behaviour | Implication |
|---|---|---|
| DWPose-t | outputs a left group (idx 91–111) and a right group (112–132) every frame | two proposals always exist, whatever is in view |
| `PerceptionVNextMath.handRoi` | a group yields an ROI if ≥ 5 of its 21 points have support ≥ 0.10 and are in frame | a weak group is enough to create an ROI |
| `Candidate01FrameAnalyzer.runHand` ×2 | each ROI cropped and refined independently | the refiner sees a hand in whichever crop it is given |
| `HandRefinerRunner.run` | `observed = presence ≥ 0.50 && ≥ 18 valid joints`; the refiner's handedness output is stored, never used | slot identity = DWPose group only |
| overlay / mirroring | draws the current frame's two slots; display-only mirror | ruled out as the cause (no persistence, no tracker) |

There are **two distinct candidate mechanisms**, which call for different fixes:
- **M1 — DWPose proposes the same hand twice**: the two ROIs coincide *before* refinement.
- **M2 — refiner snaps two different crops onto one hand**: the ROIs differ (e.g. one is a partial/shifted proposal), but each crop contains
  the real hand, so both refinements converge on it.

The first diagnostic could not tell M1 from M2, and not "two real hands" from "one hand twice" beyond skeleton overlap. The new counters can.

### New diagnostic (debug only; no behaviour change)
The 30-second `AppHearDetect` line now ends with, for example:
`hands[n=450 none=40 L=120 R=95 both=195 same=170 part=15 sep=10 na=0 same.roi=160/10 same.pres=0.93/0.91 same.hand=0.12/0.88 same.sup=0.31/0.27]`
- `both`/`same`/`part`/`sep`: both slots observed, binned by skeleton-box IoU (≥ 0.5 / 0.1–0.5 / < 0.1; descriptive labels, not a decision rule).
- `same.roi=a/b`: among `same` frames, a = DWPose ROIs already coincided (IoU ≥ 0.5, M1), b = ROIs differed (M2).
- `same.pres`, `same.hand`, `same.sup`: mean refiner presence, mean refiner handedness output and mean DWPose group support, left/right slot,
  on `same` frames. These show whether the refiner is confident about both (presence), what it says about handedness for each slot, and
  which DWPose group was the weaker proposal (support).
With `-PrecognitionV3Profile=true` the existing bounded (240 frames) `AppHearV3` JSON line also carries `frame_age_ms`, `hand_presence`,
`hand_handedness`, `hand_roi_iou` and `hand_skeleton_iou` per frame, which gives the raw series (numbers only, no images).

### Constraints any fix must meet (from the brief) and how the evidence will choose
- Two-hand signs that touch/overlap/cross must survive: the real two-hands case is exactly where skeleton IoU is high *legitimately*, so
  **overlap alone is not a valid suppression test**. The discriminators to evaluate from the logs are: handedness output vs slot, presence,
  DWPose support asymmetry, and temporal continuity of each slot's skeleton (a real second hand has an independent trajectory).
- If M1 dominates: the fix belongs at proposal level (the weaker group should not become an observed hand when it duplicates the stronger).
- If M2 dominates: the fix belongs at refinement acceptance (use the refiner's own handedness/presence evidence, and slot assignment).
- No threshold is chosen until the distributions from a one-hand run and a two-hand run are compared; a candidate rule is then validated on
  both, plus the 236-class regression suite, before it is enabled.

## 2. BUG-002 overlay lag — what is established

CONFIRMED-CODE, camera to screen:
1. CameraX `ImageAnalysis`, 480×360 RGBA, `STRATEGY_KEEP_ONLY_LATEST`, front AE fixed at 15 fps, analyzer on a **single-thread executor**.
2. `analyze` runs synchronously: preprocess → DWPose → hand ROI → refiner (serial, or parallel if `RECOGNITION_V3_PARALLEL_HANDS_ENABLED`) → S2 →
   recognizer → `onResult` → `runOnUiThread` → `OverlayView.setResult` → `postInvalidate`.
3. The overlay shows the landmarks of the frame whose analysis *just finished*; the preview behind it is the live camera.
4. **There is no smoothing, filtering or interpolation anywhere on this path** (searched `perceptionvnext`, `ui`, `pipeline/FrameResult`).
5. Because analysis is single-threaded and synchronous, **results cannot arrive out of order and there is no inference backlog**; the only
   queue is the one-frame `KEEP_ONLY_LATEST` slot. So "stale-result rejection" and "latest-frame-wins" are already structurally in place and
   would change nothing; removing smoothing is not available as a fix because there is none.

So the visible lag is the sum: (capture → analyzer start) + (analyzer time) + (UI hop), and the overlay can only update when a frame finishes.
REPO-REPORTED on the Xiaomi (earlier phases, not re-measured now): analyzer p50 ≈ 215 ms, pose ≈ 87 ms, hands wall ≈ 110 ms, live ≈ 4.6 fps.
If those hold, the overlay is ≈ 215 ms + capture/queue delay behind the preview and moves in ≈ 215 ms steps. That is a **hypothesis for the
dominant cause (inference time, not filtering or rendering)** until the new measurement splits it.

### New measurement (debug only)
`RenderLatencyMeter`: every overlay frame now carries a sequence number, the camera sensor timestamp and the analyzer delivery time; `onDraw`
records, on the same 30-second line (stage columns are `p50/p95`):
- `frame_age` (capture → analyzer start; existing), `frame_total` (analyzer time; existing), **`ui_hop`** (delivery → draw), **`end_to_end`**
  (capture → draw; only when the camera clock is comparable, otherwise omitted rather than guessed),
- `render[n= skipped= stale= redraw=]`: frames drawn, frames analyzed but never drawn, older-after-newer draws, repeat draws.
Existing, unchanged: `fpsIn`/`fpsOk` (delivered/processed FPS), `camDropEst` (dropped frames), `busy`, per-stage inference times.
Reading it: end_to_end ≈ frame_age + frame_total + ui_hop. Whichever term dominates is the origin: inference (`pose`, `hands_wall`),
scheduling (`frame_age`, `busy` near 100%), or rendering (`ui_hop`). Only after that is a lever justified; the known candidates are the
Phase 2 thread-budget experiment, parallel hand refinement (REPO-REPORTED −37% isolated but −6.2% live and off by default), or lowering
per-frame work. Overlay extrapolation/prediction is **not** proposed: no evidence, and it would hide rather than fix the delay.

## 3. Regression testing (Task 3)
Automated (JVM, scratch-copy Gradle build): **434 tests, 0 failures** — the 415 earlier tests (including the 236-class
`RecognitionAccuracyRegressionTest`, the gate, shadow log and Phase 2 recovery tests) plus 19 new:
`HandPairDiagnosticsTest` (11: identical/shifted/separate skeletons, invalid and non-finite points, ROI IoU, bins, stage discrimination M1/M2,
means with NaN exclusion, log format) and `RenderLatencyMeterTest` (8: hop/end-to-end, redraw, sequence gaps, out-of-order, implausible
clock, untimed frames, log format, probe no-op). `:app:compileReleaseKotlin` and `:app:compileDebugAndroidTestKotlin` succeed.
No recognition, gating, threshold or perception behaviour changed in this round.

The eight live scenarios cannot be executed or automated here (they need a person and a camera). Protocol, 30–60 s each, debug APK, `adb logcat -s AppHear:I AppHearDetect:I AppHearV3:I`:

| # | Scenario | What the log should show if the system is healthy |
|---|---|---|
| 1 | one hand only, still then moving | `both` ≈ 0; mostly `L` or `R` |
| 2 | two hands separated | `both` high, `sep` high |
| 3 | two hands touching | `both` high, `part`/`same` rises legitimately — the case a suppression rule must not break |
| 4 | two hands crossing | as 3, plus slot identity swaps (watch `same.hand`) |
| 5 | fast movement | `end_to_end` and `ui_hop` p95; skeleton visibly behind |
| 6 | slow movement | same, baseline |
| 7 | continuous signing | `busy`, `fpsOk`, `skipped` over a long run |
| 8 | hand leaves and returns | `none`/`L`/`R` transitions, no stuck `both` |

## 4. Build for the physical-device run
`artifacts/phase-3.2/apphear-hand-diagnostics-debug.apk` (debug, `-PrecognitionV3Profile=true -PshadowEval=true`, gate on).
SHA-256 `cbd5bc06ea065e21ca2ae46f6ba278dce985a4e5dfca8323996202df4e89a519`. Built, **not installed anywhere**: no device was available.
Install: `adb install -r artifacts/phase-3.2/apphear-hand-diagnostics-debug.apk`.

## 5. What I need to finish
Both bugs need the device data. Please send the `AppHearDetect` lines (and `AppHearV3` lines if possible) for scenarios 1–3 at minimum.
With them I will (a) state which of M1/M2 produces the duplicates, (b) split the lag into inference/scheduling/render, (c) design the
fix from the measured distributions, (d) add tests for it, and (e) rerun the regression suite. Before/after latency numbers can only
come from running the old and new build on the phone; none are claimed here.

## 6. Remaining limitations
- No device in this environment: nothing in this report was measured on a phone.
- The previous device logs referred to in the brief were not received.
- `end_to_end` is only available where the camera timestamp clock matches elapsed-realtime (device dependent).
- The skeleton-IoU bins are descriptive; they are not a validated duplicate detector.

## Files
Added: `perceptionvnext/HandPairDiagnostics.kt`, `perceptionvnext/RenderLatencyMeter.kt`, `HandPairDiagnosticsTest.kt`, `RenderLatencyMeterTest.kt`,
`artifacts/phase-3.2/apphear-hand-diagnostics-debug.apk`, this document.
Modified: `Candidate01FrameAnalyzer.kt` (pair counters + sample, render meter, profile fields, `handedness` on `HandFrame`),
`DetectionMetrics.kt` (two stages `UI_HOP`, `END_TO_END`), `ui/PhoneOverlayFrame.kt` (three defaulted timing fields), `ui/OverlayView.kt`
(one probe call), `context/progress-tracker.md`.
