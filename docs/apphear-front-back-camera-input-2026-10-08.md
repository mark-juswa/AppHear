# Front/reference and rear camera input — 2026-10-08

Active app checkout: `C:/Users/Gigabyte/.codex/worktrees/fingerspell-continuous-oct05/5. Apphear3`.
Branch: `codex/fingerspell-continuous-oct05`, approved base
`b48594c4942d9e9ac0d94ff96396e80b9f049c0a`. Research checkout is separate.

## Inspected baseline

RecognitionActivity previously disabled cameraToggle and bound the normal Candidate01 path to
DEFAULT_FRONT_CAMERA. The existing native preprocessor consumes CameraX RGBA using actual row/pixel
strides and ImageInfo.rotationDegrees. It rotates the sensor buffer into upright source coordinates;
it does not horizontally reflect it. Pose affine sampling and hand-ROI sampling read that same source.
Candidate01 outputs actual upright source width/height and source XY. Adapter.v1 is unchanged.

On this Xiaomi the front reports 270 degrees and rear 90 degrees. Both delivered 640x480 sensor
buffers and 480x640 upright source geometry. Requested 480x360 is a resolution preference;
the actual returned dimensions are authoritative. No new pixel conversion is needed for rear.

Front PreviewView selfie mirroring is presentation only. The app's phone overlay renderer previously
assumed mirrored preview for every frame. It now receives the actual bound lens's display-mirror
flag, defaults to the old front behavior, and draws ROI bounds in either direction. Recognition
receives unmirrored XY regardless of preview mirroring. These are not two recognition pipelines.

CameraX rotation semantics are documented by
[Android Developers](https://developer.android.com/media/camera/camerax/orientation-rotation).
The conclusions here also rely on the inspected native implementation and byte-level device tests.

## Implementation

- Opt-in debug `recognitionRearCamera=true`; default/release false preserves front-only rollback.
- Reuse the same Candidate01 analyzer, perception assets, feature computation and selected owner.
- Enable the camera button only after binding and when both lenses exist.
- Clear old analysis, unbind, drain camera-executor work, reset through existing public session APIs,
  invalidate spelling worker results, then bind the requested lens. Camera-generation guards prevent
  stale frames from rendering. WORD stored sentence and confirmed spelling remain separate/preserved;
  incomplete spelling windows/drafts are cleared when changing camera.
- No model, decoder, Candidate01, native pixel math, feature contract or protected WORD change.
- Bounded debug metadata: at most 120 input entries per Activity. Timing probes retain at most
  240 capture timestamps and 48 analysis entries per camera binding. No image/video is saved.

Modified app files: RecognitionActivity.kt, ui/OverlayView.kt,
perceptionvnext/PerceptionVNextOverlayView.kt, app/build.gradle.kts, and the existing
ContinuousFingerspellInstrumentedTest.kt startup/counter assertions. Added camera input/switch device
tests and main camera/CameraTimingProbe.kt. All are in the active checkout above.

## Rear-preview lag follow-up

Supervisor confirmed both cameras work, then reported choppy rear **video**, not just delayed letters.
Initial camera settings requested 15 FPS on both lenses. Capture callbacks measured approximately
15.0–15.2 FPS on front and 15.1 FPS on rear. Rear analysis was not slower in this bounded scene:
Fingerspell rear median 103.9ms vs cold front 217.9ms; WORD rear 127.2ms vs front 184–231ms.
These are scene/startup diagnostics, not a controlled cross-camera benchmark or recognition accuracy.
Sensor capture FPS is also not a measurement of frames actually presented on screen.

The 15-FPS camera cap is a confirmed smoothness limitation and a plausible contributor to the report.
One camera-only correction requests fixed 30 FPS on rear **only if the camera explicitly advertises
that exact range**; otherwise rear retains 15. Front remains at its original 15 FPS. KEEP_ONLY_LATEST
still prevents an analysis backlog; timestamps remain genuine. Feature and spatial preprocessing
semantics stay identical. This does not force Candidate01 or recognition to run at 30 observations/s.
Before/after measured timing and final human feedback belong in artifacts/camera_input_01/summary.json.

## Validation and evidence

- 169 host unit tests, no failures/errors.
- Eight asymmetric-scene native rotation/stride cases: 0/90/180/270 and pixel strides 4/8 with row
  padding; pose tensors and off-center hand crops byte-identical across cases. No horizontal flip.
- Xiaomi real CameraX front/back/front works in FINGERSPELL and WORD. Nonempty `CAMERA CHECK`
  WORD sentence survives switching. Original models, ownership and feature semantics are unchanged.
- Existing UI/Settings/owner and three local Context Assist regressions pass. Earlier failed test
  attempts are retained: a 30-second startup timeout and a mistaken absolute-zero inference counter
  assertion. Harness now waits for binding, uses a 45-second startup bound and checks zero **new**
  calls for all-missing/WORD input. No runtime workaround was made for those test failures.
- Protected hashes are checked against a before-task inventory. Exact counts, final APK SHA256,
  final test logs, timings and supervisor feedback are in artifacts/camera_input_01/summary.json.
- The preceding RECOGNIZED display cleanup is installed and its device UI assertions passed here.

Preserved rollback APKs remain in artifacts/fingerspelling_continuous_01/private_apks. New private
APK is artifacts/camera_input_01/private_apks/app-debug-private-camera.apk. Credentials remain local;
the APK must not be distributed. Rebuild with:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& tools\fingerspelling\android_continuous_build.ps1 -RearCamera
```

The common input contract is verified. Different lenses still have different optics, framing,
exposure and image quality; equivalent coordinates do not guarantee identical recognition accuracy.
No training, data acquisition, TEST payload access, accuracy claim or recognition redesign occurred.
