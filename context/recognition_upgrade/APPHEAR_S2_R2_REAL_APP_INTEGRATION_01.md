# AppHear S2-R2 real-app integration — software gate

Date: 2026-09-23. Status: **integrated locally; repeated-sign smoke pending**.

## Architecture implemented

`RecognitionActivity` and its layout/navigation/sentence/Speak/Hear contract remain in place.
The normal recognition screen now loads one front-camera `Candidate01FrameAnalyzer` and one
`PhoneProductionSession`. CameraX current frames pass through the validated native preprocessor,
DWPose-t ONNX, hand refiner, raw-v1, 378 causal features, one selected S2 package, PRE-or-POST
recovery, PASS_THROUGH Admission, CONFIG01 completion, the frozen materializer, Recognition V2,
and the unchanged 236-class recognizer. One logical event triggers one recognizer invocation
and a strictly increasing event-ID guard before a UI/sentence commit. The UI receives only the
existing product-level `RecognitionState` and sentence text; tensors and state probabilities stay
in the backend. The normal app does not write source frames, parity tensors, or review evidence.

Reusable inference code/assets were moved from `src/debug` to `src/main` rather than rewritten.
The debug capture/review Activity and fixture assets remain debug-only. No old MediaPipe/258
recognition pipeline is initialized by the normal screen. The legacy camera/hand controls are
disabled there; front camera is the only supported causal mode. An unsupported ABI or failed
asset verification shows an error and does not fall back to legacy recognition.

## Frozen package/rollback

- S2-R2 source Keras: `b6f8b52cece72f0b6f5b802a4ea583060d923e90a6b951059e7013114c8fc151`
- S2-R2 FIT normalization source: `65d885f62eaca6f11a596302d304f63149795ddaf01e702f1e6a36dd7da5c005`
- S2-R2 TFLite: `7d26c896db1a00e7a41ff3e02b02033428cbd2ae4b5cbf3e4d279d45f529d3d7`
- Candidate01 ONNX: `37b0f265200f8e249adba1cc9b62925f5e1252245580ed1f66f583d7bce239c0`
- Candidate01 hand refiner: `6acda74af3fbf40e68265c20c7394b2bad81a16a481dcd79ad7a081887c3d6b9`
- Materializer contract: `0a59dc80fe54cb37e09fbce8aa108dbfce32bc4b5cb48b98e61619b5b3b34971`
- Recognizer TFLite: `1ccf0afa9af9aa602aa0de33c9635f5cffd7feec7d9b4e32382bc5e3fa02880c`

The debug build defaults to `S2_R2_CANDIDATE`. To build an internal rollback instead, use
`cd android; .\gradlew.bat :app:assembleDebug '-PapphearPhoneS2Package=PHASE7_CONTROL'`.
Release builds remain fixed to S2-R2. Each package's own model and normalization identities
are checked together by `PhoneS2Runner` before inference; both are never run live together.

## Verification and remaining gate

- Debug and release APK builds passed. The release APK contains the Candidate01 native arm64
  library, ONNX and hand-refiner assets, both S2 packages, materializer, and frozen recognizer.
- 95 debug JVM tests passed, including the shared raw-v1 → Recognition V2 mapping regression.
- Connected Xiaomi M2101K7AG: 4/4 selected 378/S2 package parity tests and 3/3 Recognition
  V2/recognizer parity tests passed after source promotion.
- The normal AppHear recognition screen loaded `S2_R2_CANDIDATE` and reached READY on Xiaomi.
  This verifies startup/listening, not event/result/re-arm behavior in the real UI.
- The planned HELLO → HOME → TABLE → HELLO manual smoke was **not performed** because the
  Supervisor could not continue at that time. No repeated-use or word-accuracy result is claimed.

Next action: with the installed normal app, run that fixed four-sign sequence once, returning
to neutral/READY between attempts. Check one result/sentence commit per physical sign,
front-camera preview, responsiveness, natural re-arm, and absence of legacy results. Use
lightweight `AppHearPhone`/`AppHearRecognition` logcat lines to separate no/wrong event from a
good-window wrong word. Do not tune S2, lifecycle, materializer, or recognizer from this smoke.

## No-signer overlay and runtime verification (2026-09-23)

The real `OverlayView` now reuses the validated Perception VNext hand/body/ROI renderer and
fill-center/front-mirror transform. Only presentation fields (hand presence, ROI center/side,
body support) were added to the UI copy of an existing Candidate01 observation. The normal
screen still has the same layout, navigation, sentence and recognition owner. Overlay state is
cleared on stop. No inference input, model asset, 378 feature, lifecycle, materializer, or
recognizer rule was changed. Experiment attempt controls and evidence recording remain
debug-only. A connected Android pixel-comparison test showed the real and validated debug
overlays render identical synthetic geometry, including full-frame clear behavior; the
existing transform test also passed. A live Xiaomi screenshot showed the rendered hand bones
over the visible fingers/palm with the expected front-camera orientation. Empty-scene frames
may still show a faint proposal ROI outline; this is proposal visualization, not a committed
hand observation or recognition event.

The updated debug and release APKs built; 95/95 JVM tests passed. After the overlay move,
8/8 selected connected Xiaomi feature/S2, Recognition V2/recognizer, composed replay, and
overlay parity tests passed. The normal screen repeatedly loaded `S2_R2_CANDIDATE`, opened
the front camera, and reached READY. Navigation away/back and background/foreground return
each reached READY again; there was no stale displayed word on return, second analyzer, app
crash, or legacy inference log. In a bounded approximately two-minute empty/still-scene soak,
there were no committed word events; a few short ACTIVE candidates returned to IDLE. Process
PSS was about 272 MB at start/end (271,982 → 272,143 KB), with no apparent runaway growth.
This is a runtime check, not a measured false-positive rate. A still-scene screenshot showed
the UI live and a roughly 11 FPS instantaneous HUD value; short transition logs were roughly
5–7 FPS. This is not a controlled pre/post overlay benchmark.

One presentation-only hand check yielded an important limitation: after the user raised and
held an open hand (explicitly **no lexical sign**), the normal app committed event 1 as HELLO
at 16:31:56, then returned from WAIT_REARM to IDLE at 16:31:56.560. The screenshot confirms
the overlay alignment and displayed HELLO; the user supplied the behavior label. This is one
confirmed unwanted committed event under a simple non-sign action, not a population estimate
or grounds to tune Admission/S2 in this integration milestone. Earlier words on the same
installation were produced while the user reported actual signs/hand motion and are not
counted as idle false events. The fixed HELLO → HOME → TABLE → HELLO human smoke is still
unperformed and remains the integration completion gate.

An optional exact-observation `PhoneProductionSession` → UI replay was inspected but not
added: the retained binary/raw session is host-side, while current connected parity fixtures
exercise the component contracts and composed Recognition V2 path. Moving a full raw session
and parser into `androidTest` solely for this optional UI replay would expand test/runtime
infrastructure without changing the above live gate. The on-device normal app has already
shown one sentence append per logged event across observed uncontrolled commits, but the
fixed human repeated-sign sequence is still required before claiming that behavior for
intended signs.

## Final normal-app repeated-sign smoke (2026-09-23)

**Decision: `APPHEAR_S2_R2_REAL_APP_INTEGRATION_COMPLETE`**, with a separate, confirmed
non-sign-event product limitation. The current debug APK was reinstalled on Xiaomi M2101K7AG.
The normal `RecognitionActivity`, not the diagnostic capture Activity, logged one backend owner:
`normal backend=Candidate01 package=S2_R2_CANDIDATE`. The phone reported READY before the fixed
sequence. No model, threshold, lifecycle, Admission, materializer, recognizer, or UI architecture
setting was changed during the run.

The phone log start boundary was 21:58:23 device time. The Project Supervisor performed the
fixed HELLO → HOME → TABLE → HELLO sequence once each, waiting for READY between attempts,
and confirmed one visible result/sentence update and natural re-arm for each. The final UI
sentence screenshot read `HELLO HOME TABLE HELLO` after the Supervisor cleared a preceding
unwanted HOSPITAL1. The four intended events were:

| Attempt | Intended | Displayed / backend Top-1 | Event ID, commit time, selected observations | UI/sentence commit | Returned READY | Attribution |
|---|---|---|---|---|---|---|
| 1 | HELLO | HELLO | 2, 21:58:59.901, 518–535 (18) | one | yes, 21:59:00.291 | no integration failure |
| 2 | HOME | HOME | 3, 21:59:23.788, 645–663 (19) | one | yes, 21:59:24.183 | no integration failure |
| 3 | TABLE | TABLE | 4, 21:59:30.618, 684–701 (18) | one | yes, 21:59:31.039 | no integration failure |
| 4 | HELLO | HELLO | 5, 21:59:35.214, 723–730 (8) | one | yes, 21:59:35.737 | no integration failure |

No duplicate result, stale UI result, camera stop, app crash, second analyzer/result owner, or
legacy backend output was observed. The process stayed alive in `RecognitionActivity` after
the test. The exactly-one UI observations are supported by the Supervisor's report and the
final four-word sentence; there is no separate per-render UI telemetry. This is a bounded
integration smoke, not independent population accuracy or a visual boundary/containment audit.

Two unwanted commits must remain visible in the handoff:

- At 21:58:29.164, event 1 committed **HOSPITAL1** (window 221–241, 21 observations)
  while the Supervisor was adjusting their seat before the first intended HELLO. It appeared
  once; the Supervisor tapped CLEAR before the fixed four-attempt sequence. The backend
  returned to IDLE at 21:58:29.594.
- At 22:00:53.763, event 6 committed **STAND2** (window 1241–1255, 15 observations)
  during ordinary movement after the four intended signs, with no deliberate lexical sign.
  It appeared/was appended once and returned to IDLE at 22:00:54.159.

Those are operator-confirmed non-sign behaviors with committed words; the normal app did not
retain synchronized diagnostic video, so exact motion/episode boundaries cannot be independently
reviewed. Together with the earlier open-hand HELLO incident, they show a product-level
unwanted-event risk, but this short smoke does not estimate a false-positive rate or isolate
whether perception, S2, or pass-through Admission is chiefly responsible. It does not authorize
an immediate threshold/model/lifecycle change. The integration objective—normal UI, one S2-R2
backend, four sequential intended signs, one result/sentence commit each, and automatic READY
recovery—is met. Return to Project Lead for the next product decision; do not start S2 research.
