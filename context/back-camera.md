# Dual-camera (back-camera) support — decision record + revert anchor

Feature **F24** (Phase 3 addendum; 23 is the parked encoder upgrade). Adds a back-camera option to
the runtime. Written BEFORE any code so we can always revert to the current front-only baseline.
**Status: PLUMBING IMPLEMENTED (camera toggle + session reset on switch), no flip. Device gate (§4)
pending.** §1 below is the pre-feature baseline (the revert target); §6 is the revert.

---

## 1. Baseline snapshot (the state to revert to)

The current, working, **front-only** implementation. If a back-camera change goes wrong, restoring
these to exactly what's described here returns the system to a known-good state.

- **Camera is hardcoded front-only.** [`MainActivity.kt:129`](../android/app/src/main/java/com/example/apphear/MainActivity.kt) — `val isFront = true`; the `CameraSelector` is chosen from it (`DEFAULT_FRONT_CAMERA`).
- **Analysis path is rotate-only, NO mirror.** [`FrameAnalyzer.kt`](../android/app/src/main/java/com/example/apphear/pipeline/FrameAnalyzer.kt) converts the CameraX `ImageProxy` → bitmap → `rotate(bitmap, rotationDegrees)` and feeds that to MediaPipe. There is no horizontal flip anywhere in the path that reaches the model. `isFrontCamera` is carried on `FrameResult` but only passed through.
- **`isFrontCamera` affects display only.** The only consumer is [`OverlayView.kt:54`](../android/app/src/main/java/com/example/apphear/ui/OverlayView.kt) (`if (r.isFrontCamera) width - x`), mirroring the drawn landmark dots to match PreviewView's selfie mirror. It is never read by `LandmarkAdapter`, `SessionNormalizer`, or `RecognitionPipeline` — **the detection/feature path is camera-agnostic.**
- **The only mirror in features is signer-handedness, not camera.** [`SessionNormalizer.kt:98`](../android/app/src/main/java/com/example/apphear/pipeline/recognition/SessionNormalizer.kt) mirrors ONLY when handedness is `LEFT`/`AUTO`. Default is `RIGHT` = no mirror = "matching the offline data". Matches offline [`handedness.py`](../pipeline/normalize/handedness.py) (dominant→RIGHT, left-dominant clips mirrored). Handedness is a per-signer property, independent of camera.
- **`SessionNormalizer.reset()` exists but is never called.** [`SessionNormalizer.kt:106`](../android/app/src/main/java/com/example/apphear/pipeline/recognition/SessionNormalizer.kt) — only `confirmation.reset()` is wired (via `RecognitionPipeline.resetSign()`). Harmless today (single camera); becomes relevant once a switch exists.

**Convention that must be preserved:** the model was trained on the raw, **un-mirrored** analysis
frame (this is what the front camera already delivers — proven by the app recognizing correctly at
the `RIGHT`/no-mirror default). Any camera must feed the pipeline this same un-mirrored convention.

---

## 2. Decision (agreed architecture)

Route the back camera through the **identical, untouched** pipeline. All front/back divergence lives
in the **capture/source layer**; the shared pipeline never learns which camera produced a frame.

- **Front camera = baseline, untouched.** No edits to the front path, pipeline, MediaPipe, landmark
  handling, handedness logic, or the model.
- **No forced mirroring** — not on the analysis path, not on the preview "for consistency". The back
  camera's raw analysis frame is expected to already match the front convention (CameraX does not
  mirror `ImageAnalysis` for either lens; both deliver the un-mirrored sensor frame after rotation).
- **A back-only horizontal flip exists only as a contingency, default OFF, in the capture layer**
  — enabled *only if* the §4 device test proves the back camera's raw chirality differs from the
  front's. If the test says no flip is needed, **no flip is implemented.**

---

## 3. Change surface (what the back camera needs — none of it touches the pipeline)

1. Un-hardcode `isFront` + a camera-select toggle (swap the `CameraSelector`).
2. Propagate the *real* `isFrontCamera` value to the overlay so the dots mirror correctly per lens
   (display layer only).
3. Call `SessionNormalizer.reset()` on camera switch — the scale/roll/handedness estimators are
   session-scoped, and a switch means a new scene/signer.
4. (Optional, UX only) a preview mirror — has zero effect on recognition; decide on looks alone.
   For a *second person* facing the back lens, an un-mirrored preview is arguably more natural.

Handedness (LEFT/RIGHT) stays a per-signer setting, independent of camera.

---

## 4. Verification gate (the one open item — measure, don't guess)

Before shipping: route the back camera through the pipeline unchanged, record a strongly
**one-handed, asymmetric** sign, and confirm the dominant hand lands in the **RIGHT** slot and
recognizes correctly.
- **Pass** (expected) → convention matches; leave the flip toggle OFF; done.
- **Fail** → flip the back-only capture-layer toggle ON. Front path + pipeline stay untouched either
  way, because the flip lives entirely in the source layer.

This converts "raw frames match" from a well-reasoned assumption into a confirmed fact — consistent
with the project's measure-first rule.

---

## 5. Parity guarantee

Nothing here touches `android/features` (S4) or `pipeline/features` (F), so the S4 skew test cannot
regress by construction. Run it as a guardrail anyway.

---

## 6. Revert

Because the front path and pipeline are untouched by design, reverting = removing the additive
back-camera plumbing:
- Restore `MainActivity.kt` to `isFront = true` (front-only) and drop the camera toggle.
- Remove the (only-if-needed) capture-layer flip and the `SessionNormalizer.reset()` call on switch.
- The overlay `isFrontCamera` handling and everything downstream are unchanged from §1.

No model re-export, no feature rebuild, no S4 change — the revert is UI/capture-layer only.

---

**Status:** PLUMBING BUILT (agent, not yet device-verified). Implemented: `frontCamera` state +
camera-flip button (`cameraToggle`) + re-callable `rebindCamera()` in `MainActivity`,
`RecognitionPipeline.resetSession()` called on switch, `OverlayView` mirror driven by the real lens.
**No flip** — `FrameAnalyzer` carries a commented insertion point only. NEXT: developer builds in
Android Studio and runs the §4 device gate (one-handed asymmetric sign on the back camera). Pass →
done; fail → enable the back-only flip. Files touched: `MainActivity.kt`, `RecognitionPipeline.kt`,
`FrameAnalyzer.kt` (comment), `activity_main.xml`, `strings.xml`.
