# Text-to-ASL phone pilot — 2026-09-28

## Scope and device

Seven exact catalog replacements: A, B, ALL, BROTHER, CHILD, CITY, FAMILY. The original
102 assets, catalog, vocabulary, planner, recognition, camera, model and configuration remain
unchanged. Replacement remains a default-off debug flag; no broad rollout is approved.

Physical device: M2101K7AG (sunny_global), Android 12/API 31, arm64, MemTotal 5,717,968 KiB
(approximately 6 GB marketed RAM); System WebView 153.0.8010.36. These observations do not
establish performance on low-RAM phones.

The installed APK was backed up before `adb install -r`; app data was preserved. Launch used
the ordinary exported SplashActivity after the non-exported MainActivity correctly rejected
direct launch. No export/security change, uninstall, data clear or recognition experiment.
Backup and raw evidence: `artifacts/text_to_asl_device_smoke_20260928/`.

## Human checks and discovered completion issue

The user confirmed initial seven-sign appearance/playback, two completed replays, Clear during
playback, and leaving/reopening Text-to-ASL worked normally. These are functional/visual
attestations, not semantic ASL accuracy validation. On the next build the user reported both
sequences finishing, but uneven movement and a pause before the next word.

Logs exposed a defect hidden by the safety timer: every sign advanced at its configured
duration plus two seconds, with no native completion callback. A first targeted attempt waited
for `animationName`'s asynchronous update before `play({repetitions:1})`. That retained correct
one-shot settings but did not restore events. `/recover` classified this as an isolated renderer
integration defect, not an architecture or recognition failure.

Inspection of the pinned model-viewer 4.3.1 bundle proved `subscribeMixerEvent` registers only
on currently existing mixers, while the constructor registers before model loading creates
them. A live debug-WebView read confirmed the FAMILY action had LoopOnce/repetitions=1,
currentTime=duration=2.566666603 seconds. Thus the absent event was not evidence of looping.
The temporary debug forwarding port was removed afterward.

The focused pilot fix retains the asynchronous update barrier, and watches the public
`currentTime >= duration` animation timeline using one cancellable animation-frame callback.
It completes a matching active request exactly once, accepts the renderer event when present,
and cancels on new input/Clear/lifecycle pause. It does not guess completion from elapsed wall
time. The native duration watchdog remains available for stalls. Vendor source is unchanged.

## Validation and performance

Both pilot/default JVM gates pass: 99 tests each; seven deterministic player tests pass,
including missing renderer events, exactly-once timeline completion and cancellation.
Pilot/default APK inspection verifies all seven pilot payloads against source and all 102
original GLBs unchanged; default excludes pilot assets. Pilot 379.86 MiB, rollback 307.88 MiB.
The ordinary final build is flag OFF; the phone is deliberately running the pilot.

Initial evidence: A request-to-start 3,804 ms; reopened ALL 2,658 ms; preloaded transitions
32–64 ms. These earlier timings include the defective extra watchdog gap and must not be
used to claim good phrase latency. App plus associated WebView renderer paired PSS reached
998.61 MiB during repeated playback. Later idle samples fell to about 540 MiB, so that peak
alone does not prove a leak. It remains substantial memory pressure.

Final timeline-run measurements and direct user feedback are recorded in
`artifacts/text_to_asl_device_smoke_20260928/timeline-summary.json` and the continuation below.
Request-to-start samples mix cold decoding and ready preloads; p50/p95 from this tiny sample
are diagnostic only. Paired dumpsys sampling can miss transient allocation peaks and perturb
performance. App/UI gfxinfo statistics include loading, input and navigation; they are not
isolated WebGL animation FPS. No animation FPS or thermal-stability claim is made.

### Final result

User final feedback: **much better, shorter pauses, all signs finish** for the requested
play/replay check. Captured final logs independently confirm one seven-sign sequence with
seven matching timeline completion callbacks, zero watchdog advances, and no captured
replacement-failure/crash errors. Final request-to-start times (A through FAMILY):
4,227 / 1,547 / 1,168 / 79 / 123 / 42 / 41 ms. Diagnostic nearest-rank p50 123 ms, p95
4,227 ms (n=7; mixed cold/preloaded requests). Final sampled combined PSS peak 719.02 MiB;
the earlier 998.61 MiB playback peak remains relevant and cannot be dismissed from this
single shorter capture. An improvement in long-term memory behavior is not established.

Corrected pilot delivery: `G:\3d Characters\android_pilot_phone_tested_20260928\`.
Older three/seven-sign APKs are retained as historical builds and lack the completion fix.

## Review and next gate

Plan alignment PASS: focused replacements and completion handling. System integrity PASS:
flag/fallback and original assets intact; no feature-vector schema or train/serve change.
Production readiness PENDING. Critical issues: 0 known after the focused fix; important: 2
(memory/decode/uneven frame performance; wider fault-injection/device/semantic validation).
Minor: 1 (mixed original idle/remaining signs). Recommendation: retain default-off pilot;
optimize before expansion or default activation.

The most promising next experiment is offline shared-character plus per-sign animation
packaging: inspect equality of geometry, textures, skeleton, node targets and inverse bind
matrices across all seven before attempting reuse. Equal-looking characters are insufficient.
Do not strip hierarchy, prune animation tracks or retarget blindly. Benchmark a compatible
animation-only pilot against current full-GLB decoding before replacing the loader. This is a
next-stage proposal, not an implemented renderer rewrite. A smaller rig/mesh variant would
need hand/finger deformation and semantic visual QA before acceptance.

Current KTX2/Meshopt compression reduces download/disk bytes but does not reduce the
1,575-node / 4,674-channel runtime animation workload. Enlarging a GLB cache or preloading
all signs is unsuitable at the measured memory levels. Full recognition F22 cross-signer
smoke, physical decoder-failure fallback injection, semantic approval and low-RAM/thermal
measurements remain pending; this report claims only Text-to-ASL pilot testing.
