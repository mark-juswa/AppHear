# Phase 2 — Continuous Detection Reliability and Performance

Date: 2026-11-09 · Branch `jepjep-claude` (working tree; **nothing committed or pushed**)
Builds on: `docs/PROJECT_RECONNAISSANCE.md`, `PHASE_1_RECOGNITION_RELIABILITY.md`, `PHASE_1_1_SHADOW_VALIDATION.md`, `PHASE_1_2_APK_BUILD_REPORT.md`. (`PHASE_1_2_DEVICE_VALIDATION.md` does not exist.)

## 0. Summary and evidence discipline

**What changed:** one bad frame no longer ends recognition. A supervisor classifies each analyzer failure, skips the frame or resets the temporal session, bounds recovery so it cannot loop, and reports a fatal stop exactly once as before. Lightweight diagnostics (counters, per-stage latency, frame age, estimated drops, FPS) were added. One main-thread blocking call was moved off the UI thread. **No model, threshold, vocabulary, camera architecture, commit-gate or shadow-log behaviour changed, and no performance optimisation was applied** (§5, §6 explain why).

Every figure carries one of these labels. Do not read a lower label as a higher one.

| Label | Meaning |
|---|---|
| **[CONFIRMED-CODE]** | read in code |
| **[MEASURED-EMU]** | measured by me in this phase on an **arm64 emulator** (4 vCPU, software GL, virtual camera, no signer). Valid for *relative* behaviour and correctness, **not** for phone speed |
| **[REPO-REPORTED]** | measured by the repo team on the target Xiaomi M2101K7AG, in documents. I did not reproduce them |
| **[ESTIMATE]** | derived by arithmetic or reasoning, not measured |
| **[NOT VERIFIED]** | not tested anywhere |

**No physical-device measurement was made in this phase.** The historical "5–11 FPS" figure is **[REPO-REPORTED]**, not verified current performance.

*Correction to my earlier reports:* my first reconnaissance missed `docs/recognition-v3-stage1-*.md`, which hold on-device stage timings and a measured evaluation of parallel hand inference. They are used below as **[REPO-REPORTED]** evidence.

---

## 1. Initial architecture assessment

### 1.1 Live frame path and threading **[CONFIRMED-CODE]**
```
CameraX (KEEP_ONLY_LATEST, 480x360 RGBA, front AE fixed 15 fps)
  -> cameraExecutor (ONE thread) -> Candidate01FrameAnalyzer.analyze   [@Synchronized]
       native preprocess -> DWPose-t (ORT, 2 threads) -> hand ROIs -> hand refiner x2 (TFLite 2 threads, SERIAL)
       -> PhoneRawObservation -> [FINGERSPELL owner?] -> PhoneProductionSession.consume
            S2-R2 (TFLite 4 threads) -> decoder -> on event: Recognition-v2 (TFLite 4 threads) -> commit gate
       -> onResult -> runOnUiThread
```
`analyze`, `close` and `resetTemporalSession` share one monitor. Nothing else touches the models, so model resources are never entered concurrently on this path. Parallel hands (`RECOGNITION_V3_PARALLEL_HANDS`) is the only second thread and is **off by default**.

### 1.2 What a failure did before Phase 2 **[CONFIRMED-CODE]**
`analyze` caught every `Throwable`, set `failed = true` (never cleared) and called `onFailure`; `RecognitionActivity` then unbound the camera and showed "Causal recognition stopped". Every later frame returned immediately.

### 1.3 Where a failure can occur, and the state it leaves

| Stage | Typical failure (stable code) | Temporal state after the throw |
|---|---|---|
| timestamp guard | `APP_PHONE_NON_CHRONOLOGICAL_SOURCE_TIMESTAMP` | untouched |
| preprocess / preprocessor create | `VNEXT_NATIVE_DIRECT_BUFFER_BOUNDS`, `VNEXT_NATIVE_GEOMETRY_INVALID`, `VNEXT_NATIVE_CREATE_FAILED` | untouched |
| pose (ORT) / hand refiner (TFLite) | runtime exceptions | untouched |
| **observation built** (`sourceIndex++` evaluated) | `PhoneRawObservation` guards | **analyzer index ahead of session** |
| `ownsObservation` (FINGERSPELL), `session.consume` (S2, decoder, Recognition-v2, gate), `onResult` | `APP_PHONE_SOURCE_INDEX_DISCONTINUITY`, `PHONE_SEGMENTATION_NONFINITE_FEATURE`, TFLite errors | **partially updated session; counters possibly out of step** |

The line between rows 3 and 4 is the key design fact.

---

## 2. Root cause analysis

1. **Fail-stop latch** (F-004): any `Throwable`, including a one-frame glitch, stopped recognition for the session. `[CONFIRMED-CODE]`
2. **A second, hidden failure mode that a naive fix would expose.** The analyzer increments its own `sourceIndex` while building the observation; the session demands `observation.sourceIndex == nextSourceIndex`. If the session throws *after* that increment, the counters diverge and **every later frame** fails `APP_PHONE_SOURCE_INDEX_DISCONTINUITY`. "Catch and continue" would therefore not recover; it would loop. A unit test models exactly this (§7.1) and shows that skip-only never resumes while the Phase 2 reset does.
3. **A main-thread block.** `RecognitionActivity.onStop` called `phoneAnalyzer?.resetTemporalSession()` directly. That method shares the analyzer monitor, so the UI thread waits for the in-flight frame (analyzer p50 135–215 ms on the target, **[REPO-REPORTED]**). `[CONFIRMED-CODE]`
4. **A native leak on partial construction.** If the hand model failed to load, the already-built DWPose session was never closed. `[CONFIRMED-CODE]`

---

## 3. Fault recovery design

`AnalyzerFaultSupervisor.kt` (pure Kotlin, JVM-testable) wraps one frame. Outcomes:

| Outcome | When | Action |
|---|---|---|
| **Recovered, frame skipped** | failure in the PERCEPTION phase (before the observation exists) | drop the frame, keep all temporal state; the decoder already tolerates observation gaps |
| **Recovered, session reset** | failure in the SESSION phase | call the existing `resetTemporalSession` (analyzer index, timestamp, decoder state, session, commit-gate ids, shadow-log generation); an in-progress sign is lost; models and native resources are kept |
| **Fatal** | see below | report **once** via `onFailure` (now an `AnalyzerFatalException` naming the code), stop, exactly the old end state |

**Classification (explicit, not catch-all).**
- **Fatal immediately:** any `Error` (OOM, `UnsatisfiedLinkError`, `StackOverflowError`, `AssertionError`…), `InterruptedException`, and any code containing `ASSET_DRIFT`, `CONTRACT`, `CLOSED`, `MODEL_DRIFT`, `MANIFEST_DRIFT` (model integrity or closed resource).
- **Recoverable (one bad frame):** the 13 known guard codes in `KNOWN_FRAME_CODES` and any other `Exception`. Unknown exceptions are recoverable *but counted as "unknown" in diagnostics* and budgeted.
- **Fault codes never carry message text:** a code is an UPPER_SNAKE token from the message or the class name (≤ 80 chars). A test confirms an e-mail address or path in a message never reaches a log.

**No infinite recovery loop.** More than **5 recoverable faults within 10 s** → fatal with `escalation=FAULT_BUDGET_EXHAUSTED`; a recovery action that itself throws → fatal (`RECOVERY_FAILED`, both exceptions kept). Once fatal the supervisor rejects frames without running them. **These two constants are reliability policy, not calibrated values** — there is no field data to calibrate them; the new diagnostics are what will allow tuning.

**Concurrency and teardown.** Recovery runs inside the same `@Synchronized analyze` call, so it can never overlap a frame, a reset or `close()`. `runFrame` is additionally `@Synchronized` (tested with 4 racing threads: max concurrency 1). `close()` is idempotent, stops the diagnostics reporter, and every `ImageProxy` is closed exactly once in every path (verified on the real runtime).

**Stale camera generations — analysis result.** I looked for a path by which an old generation could publish and found none to fix: `resetTemporalSession` (called on the camera executor at every camera change) and `analyze` share one monitor and one thread, so a reset cannot interleave with a frame; the activity's `ticket != cameraGeneration` guard drops UI results from a replaced generation; fingerspelling results are epoch-guarded. I therefore did **not** add an unreachable analyzer-level gate. The behaviour is covered by tests that exercise the real classes (§7.2: timestamps may restart after a reset without a fault; frames after close are ignored and closed).

**Other changes:** (a) `onStop` now resets on `cameraExecutor` (3-line, byte-exact edit of the CRLF file); (b) the DWPose session is closed if the hand model fails to build; (c) every fault logs `analyzer_fault code=… type=… class=… phase=… action=… inWindow=…` (no messages, no frame data).

**Known limits of recovery.** A native crash (SIGSEGV) kills the process and cannot be recovered. A fatal stop still requires leaving the screen to restart (no in-place restart was added). `PhoneProductionSession.consume` is not made internally atomic; the reset is its recovery.

---

## 4. Detection observability (Task 5)

`DetectionMetrics.kt`; read the debug-only log tag **`AppHearDetect`** (every 30 s, debug builds only, from a daemon thread).

Example (a real line from this phase's emulator run, §5.2): `in=335 ok=334 camDropEst=516 faults=0 recov=0/0 fatal=0 fpsIn=6.4 fpsOk=6.3 busy=97.1% frame_age=10.4/70.3 preprocess=0.4/3.0 pose=57.1/128.5 … frame_total=168.0/264.5`

| Field | Meaning |
|---|---|
| `in` / `ok` | frames delivered to the analyzer / completed without a fault |
| `camDropEst` | **estimate** of frames CameraX never delivered, from gaps in sensor timestamps against the **requested** 15 fps (the learned-interval fallback under-counts when saturated, see §5.3) |
| `faults`, `recov a/b`, `fatal`, `codes=` | fault counters (bounded to 16 distinct codes), recovery attempts/successes, fault codes |
| `fpsIn` / `fpsOk` | delivered / completed frames per second over the last 64 frames (camera timestamps / `nanoTime`) |
| `busy` | share of wall time the analyzer spent processing |
| `frame_age` | camera timestamp → analyzer start, only when the camera clock is plausibly comparable (0–10 s) |
| stage `p50/p95` ms | `preprocess, pose, pose_decode, hand_crop, left_hand, right_hand, hands_wall, segmenter, recognizer, frame_total` (per-hand stages are sampled only when a hand proposal exists) |

Properties (tested): preallocated rings (256 samples/stage, no per-frame allocation); array writes under an uncontended monitor on the camera thread, percentile work only on the reporter thread; no user data. **Overhead:** JVM microbenchmark bound of 5 µs per `record` (a guard against regressions; **[ESTIMATE]** for phone cost, not measured on a phone). The existing opt-in `AppHearV3` JSON trace is unchanged.

---

## 5. Performance profiling (Tasks 2–3)

### 5.1 Where the time goes — **[REPO-REPORTED]**, target phone (Xiaomi M2101K7AG), docs/recognition-v3-stage1-validation-2026-10-15.md
Live front WORD, one 14 s run (no significance claim): delivered **4.64 fps**; analyzer p50/p95 **214.7 / 248.1 ms**; pose **86.8 / 115.0 ms**; hands wall **109.8 / 112.8 ms** (≈ 55 ms per hand, two serial 224×224 refinements). Rear: 135.5 ms, 7.43 fps. Identical-input replay: preprocessing ≈ 1.06 ms, pose decode ≈ 0.37 ms. Together pose + hands ≈ 90 % of a frame; preprocessing, decode, S2 and Recognition-v2 are small.
**Parallel hands, measured by the repo:** hand wall for two proposals fell 61.8 → 38.9 ms p50 (−37 %) on identical input, but summed inference time rose (contention) and **live front WORD delivery was −6.2 % with worse p95** (FINGERSPELL +23.2 %); the repo's verdict: *default-off, do not enable globally*. The native `crop` is read-only on the shared frame with no static state (code-confirmed) and an instrumented parity test passes for it, so concurrent crops are structurally safe, **but the measured benefit does not exist for WORD**. Therefore **parallel hands was not enabled.**

### 5.2 Measured in this phase — **[MEASURED-EMU]** (not phone numbers)
| Measurement | Value |
|---|---|
| Java allocation per frame (ART `art.gc.bytes-allocated`, 200 frames) | **≈ 618 KB / frame** (≈ 9 MB/s at 15 fps) |
| Post-GC Java heap, 600 frames in 6 rounds | **flat: 5.2 → 5.4 MB**; native heap flat (≈ 85–111 MB) — **no leak** |
| Session + analyzer initialisation (warm assets) | ≈ 20 ms + ≈ 56 ms |
| Stage times, frames only (no camera/preview), blank scene | preprocess 0.3/0.6, pose 14.0/15.7, pose-decode 0.2/0.5, segmenter 7.2/21.8, total 23.0/37.1 ms (12 frames incl. warm-up) |
| Stage times, **live app + virtual camera + preview** (2 reports, 156 and 335 frames) | pose 58.3/150.7 and 57.1/128.5, **segmenter 98.9/180.2 and 98.0/168.3**, total 171.8/284.3 and 168.0/264.5 ms; delivered 5.8 / 6.4 fps; busy 97.9 / 97.1 % |
| Frame age at analyzer start (live) | p50 10–24 ms, p95 70–92 ms |
| Lifecycle (live camera) | no fault, no crash across background/resume, back/relaunch, permission revoke + re-grant; total PSS 177–179 MB at three observations (two runs, several minutes each) |

*What these do and do not say.* The emulator has no hands, so hand stages never ran; its CPU is shared with software-rendered preview. The same segmenter that took ≈ 4–7 ms with no camera took ≈ 98 ms with the camera and preview running. **[SUSPECTED]**, not established: S2-R2 is a 0.5 MB model run with **4 XNNPACK threads**; under CPU contention thread synchronisation can dominate. That is worth a bounded device experiment (§9) and nothing more: I did not change any thread count.

**Allocation arithmetic [ESTIMATE]:** the DWPose output is converted to nested `Array<Array<FloatArray>>` each frame: (133×384 + 133×512) floats × 4 B ≈ **477 KB**, ≈ 77 % of the measured 618 KB. Removing the conversion (read ORT output as a `FloatBuffer`) is a plausible allocation reduction, but it sits inside the frozen Candidate01 decode path and needs same-pixel parity proof; it was **not** done.

### 5.3 Frame processing strategy — KEEP_ONLY_LATEST (Task 3)
- It is the right policy for this pipeline: the queue is bounded to one frame, so latency cannot accumulate. Live frame age at start stayed small (p50 10–24 ms) even while the analyzer was 97–98 % busy and camera drops were frequent **[MEASURED-EMU]**.
- Cost: when processing (~170 ms here) exceeds the frame interval (66.7 ms), the camera drops most frames: `camDropEst` 516 on 335 delivered, i.e. ≈ 851 sensor frames in ≈ 60 s ≈ the requested 15 fps, completing ≈ 6 fps **[MEASURED-EMU]**. This is the same regime the repo reports on the phone (4.6–7.7 fps).
- **A flaw in my own estimator, found by running the app:** the first version learned the "normal interval" from the stream and reported only 13 drops (implausible). Under saturation, delivered frames are spaced by processing time, so the sensor interval is not observable from them. The estimator now uses the requested 15 fps when known (regression test `withTheRequestedRateKnownDropsAreStillCountedWhenTheAnalyzerIsSaturated`). The 30 fps rear option would mis-estimate; documented.
- **No change was made to frame handling.** Nothing measured on the target supports one: dropping to a bounded queue of 2 would only increase frame age; skipping frames deliberately would reduce temporal resolution that the models need (documented ≥ 15 fps floor); stale-frame skipping is moot because the frame handed to the analyzer is already the newest.

### 5.4 Questions in Task 2, answered
| Question | Answer |
|---|---|
| Dominant operations | pose then two serial hand refinements **[REPO-REPORTED]** |
| Serial vs parallel hands | measured by the repo: mixed (−37 % hand wall, WORD live −6 %); left default-off; instrumentation now exists to repeat it cheaply |
| Model init overhead | ≈ 76 ms warm on the emulator; first run also copies the 22 MB ONNX and hashes it every launch (off main thread) — device cost **[NOT VERIFIED]** |
| Unnecessary image transformations | none on the live path: no Bitmap, one native frame copy + resample; preprocessing ≈ 0.3–1 ms **[MEASURED-EMU / REPO-REPORTED]** |
| Memory allocation | ≈ 618 KB/frame churn, no retention **[MEASURED-EMU]** |
| Frame conversion cost | included in the ≈ 0.3–1 ms preprocessing |
| CPU / XNNPACK | pose ORT 2 threads; hands 2 threads each; S2 4; Recognition-v2 4 — no GPU/NNAPI. Thread budget is the repo's own proposed next experiment |

---

## 6. Optimisations implemented
**None for throughput.** The rule was "optimise only where measured evidence supports it", and the only on-device evidence (the repo's) argues against the one available switch (parallel hands), while the others (allocation reduction, thread budget) need parity proof or device measurement I could not do. What *was* implemented is reliability and the instrumentation that makes those experiments cheap and comparable. The `onStop` change removes UI-thread blocking of up to one frame; its effect is **[CONFIRMED-CODE]** only, not timed.

---

## 7. Tests and results

### 7.1 JVM — `AnalyzerFaultSupervisorTest` (17) and `DetectionMetricsTest` (11)
Classification table (known codes recoverable; contract/asset/closed codes and Errors fatal; no message text in codes); frame skip keeps state; session fault resets once and recognition resumes; **root-cause model** (without reset one fault poisons every later frame; with reset the next frame is consumed); bounded recovery (6th fault → fatal, later frames rejected and never run); sliding window; Error is fatal with no reset and keeps its cause; failed recovery escalates and keeps both exceptions; broken diagnostics callback never breaks recovery; fatal exception message names the code and is truncated; metrics reflect faults/recoveries; frames never run concurrently (4 threads); new supervisor after fatal = session restart. Metrics: nearest-rank percentiles, ring keeps newest samples and does not grow (1 M records), invalid samples ignored, drop estimation (learned and requested-rate), FPS and busy ratio, bounded fault codes, log line character set, frame-age plausibility, per-call cost, concurrent snapshot safety.

### 7.2 Real runtime — `Candidate01AnalyzerRecoveryInstrumentedTest` (9), run on the emulator
Real `Candidate01FrameAnalyzer` + native preprocessor + DWPose-t + hand refiner + S2-R2 + decoder, fed synthetic frames through a fake `ImageProxy`: blank frames processed and metrics wired · backwards timestamp recovered and later frames run · undersized buffer recovered and the preprocessor re-created · injected session-phase failure (via `ownsObservation`) resets and recognition resumes (only the injected frame fails) · repeating fault → exactly one fatal report, later frames ignored and still closed · camera-generation change lets timestamps restart without a fault · close idempotent, late frames closed · heap plateau across 600 frames · init time and allocation measured. **Every frame is closed exactly once in every scenario.**

### 7.3 Results **[CONFIRMED-RUN]**
| Run | Result |
|---|---|
| Full `:app:testDebugUnitTest` | **404 tests, 0 failures** (376 before this phase + 28 new); includes Phase 1 gate (20) and Phase 1.1 shadow log (20) tests, unchanged and passing |
| Mutation checks | removing the session reset → 3 supervisor tests fail; removing the fault budget → 4 fail |
| `:app:compileReleaseKotlin`, `:app:compileDebugAndroidTestKotlin` | success |
| New instrumented class, emulator | **9 / 9 pass** (final code) |
| Existing instrumented tests, packages `perceptionvnext` + `camera` | **22 pass, 4 fail for environment reasons**, none touching Phase 2 code: `CameraSwitchInstrumentedTest` fails on its first line (`assertTrue(BuildConfig.RECOGNITION_REAR_CAMERA_ENABLED)`: build flag not set); `ParallelHandRefiner…` and `RecordedPerceptionBenchmark…` need `v3/manifest.json` fixtures (Gradle property not passed); `LivePerceptionCapture…` needs a launch extra |

**A false alarm I caught:** my first heap test reported a "leak" of ≈ 0.67 MB per frame. It was my own harness retaining every fake frame; with frames no longer retained the post-GC heap is flat. I am recording it so the number is not later mistaken for a finding.

---

## 8. Before / after
| | Before | After |
|---|---|---|
| One recoverable analyzer exception | recognition stopped for the session **[CONFIRMED-CODE]** | frame skipped or session reset; recognition continues **[tested on the real runtime]** |
| Persistent fault | stop | bounded: stop after > 5 faults in 10 s, once |
| Model/contract/resource fault | stop | stop (unchanged) |
| UI thread on `onStop` | could wait for one frame | does not wait **[CONFIRMED-CODE]** |
| Hand-model load failure | leaks the pose session | closed |
| Diagnostics | opt-in 240-frame JSON only | counters + per-stage p50/p95 + frame age + drop estimate, always on, logged in debug |
| **Frame rate / latency** | n/a | **no before/after exists; none was changed** |

---

## 9. Remaining risks and limitations
- **R1. No physical-device run.** All timing in §5.2 is emulator. Whether the new diagnostics add any measurable cost on the phone is **[NOT VERIFIED]**.
- **R2. Policy constants** (5 faults / 10 s) are uncalibrated; too tight could stop a flaky camera early, too loose could hide a bad device. Tune from `AppHearDetect` field data.
- **R3. Reset loses an in-progress sign;** frequent session-phase faults would silently lower sign recall. The counters make this visible.
- **R4. Unknown exceptions are treated as recoverable.** A defect throwing from every frame becomes visible as `codes=` and finally as a budget stop, but briefly masks itself.
- **R5. Fatal stop needs leaving the screen.** No in-place restart.
- **R6. Native crashes and ANRs** cannot be handled here.
- **R7. FINGERSPELL path** (debug) shares the same supervisor but its own faults were not separately injected.
- **R8. Throughput is unchanged** (≈ 5–8 fps on the phone, **[REPO-REPORTED]**), far below the 15 fps floor. This phase made the failure mode survivable and measurable; it did not fix speed.
- **R9. Allocation churn** (≈ 618 KB/frame) will cause GC activity on the phone; impact unmeasured there.
- **R10. Drop estimate** assumes the requested 15 fps; wrong for the optional 30 fps rear path.
- **R11. Permission dialog** was not observed in a UI dump; the revoke → relaunch → re-grant path showed no crash and recognition resumed.
- **R12. The Phase 1.2 APK predates Phase 2.** `artifacts/phase-1.2/…apk` does **not** contain this work; a new APK is needed to test it on a phone (not built here because it was not requested).

## 10. Recommended next steps
1. **Build a Phase 2 APK** and run it on the Xiaomi for ≥ 10 minutes per configuration; collect the `AppHearDetect` lines (`adb logcat -s AppHearDetect`) — the first real per-stage, frame-age and drop data for the current build.
2. **Thread-budget experiment** (the repo's own recommendation), now cheap to read out: S2 at 1–2 threads, one thread per hand interpreter, parallel hands on/off — compare `frame_total` p95, `fpsOk`, `busy` per arm; keep any change only with parity and the owner/lens gates.
3. **Allocation reduction** in the DWPose output path with same-pixel parity (≈ 77 % of per-frame garbage), only if step 1 shows GC pauses.
4. **In-place restart** after a fatal stop (re-create the analyzer instead of leaving the screen) once step 1 shows how often fatal stops really occur.
5. **Tune the fault budget** from field `faults` / `codes=` data.
6. Fold the `fault codes` and counters into the Phase 1.1 shadow `session_end` marker (a schema change that needs its own golden-fixture update) so a study session also records detection health.
7. Run the four environment-dependent instrumented tests with their build flags/fixtures (`-PrecognitionRearCamera=true`, `-PrecognitionV3FixtureDir=…`).

---

## 11. Files

**Modified**
- `android/app/src/main/java/com/example/apphear/perceptionvnext/Candidate01FrameAnalyzer.kt` — body moved into `processFrame` under the supervisor; phase marker before observation construction; stage timings; debug reporter; constructor-failure cleanup; fatal reported as `AnalyzerFatalException`.
- `android/app/src/main/java/com/example/apphear/RecognitionActivity.kt` — **one logical change** in `onStop` (reset on the camera executor); CRLF and the existing non-UTF-8 byte preserved (3 added lines, 1 removed).
- `context/progress-tracker.md` — dated entry.

**Added**
- `perceptionvnext/AnalyzerFaultSupervisor.kt`, `perceptionvnext/DetectionMetrics.kt`
- `src/test/.../AnalyzerFaultSupervisorTest.kt`, `src/test/.../DetectionMetricsTest.kt`
- `src/androidTest/.../Candidate01AnalyzerRecoveryInstrumentedTest.kt`
- `docs/PHASE_2_CONTINUOUS_DETECTION.md`

**Unchanged by design:** Recognition-v2, vocabulary, confidence floors, models, camera binding, Phase 1 gate and Phase 1.1 shadow log (their 40 JVM tests pass), parallel-hands default (off). Earlier-phase files remain as left.

**Not committed.** The emulator used for §5.2/§7 was started read-only and shut down; nothing was installed on any user device.
