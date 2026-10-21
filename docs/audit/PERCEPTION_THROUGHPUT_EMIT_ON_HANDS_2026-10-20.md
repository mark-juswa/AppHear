# Perception throughput: emit-on-hands Candidate01 schedule (2026-10-20)

Second, default-off scheduling candidate after `PERCEPTION_THROUGHPUT_PIPELINE_2026-10-20.md`
(first pipeline, commit 06e40b2f). No model, threshold, S2-R3 Arm A, confirm-boundary,
materializer, WORD_BLEND_02 or SentenceBuilder change. Protected TEST, E6 and Tier 3 data were
not opened. Nothing committed. Device: Xiaomi M2101K7AG (3ab64582), front camera, WORD owner,
one non-expert signer; parity and live runs approved by the user on 2026-10-20. Live runs are
engineering measurements: **no accuracy claim from them**; accuracy effects below are offline
predictions.

## Answer

| Question | Result |
|---|---|
| Why did the first pipeline add ~260 ms? | Two causes. (1) Frame *t* was emitted only after frame *t+1* arrived. (2) **CameraX KEEP_ONLY_LATEST dispatches its cached frame the moment the current one is closed.** The first pipeline closed each frame right after preprocess and then ran ~115 ms of hands on the camera thread, so the next frame was already ~150 ms old when analysis started (capture→analysis start p50 270 ms vs ~116 ms serial). |
| Does "emit as soon as own hands finish" fix it by itself? | **No.** Holding each frame until DWPose is free only moves the delay into a queue: modelled 6.96 obs/s at p50 559 ms at first-pipeline contention, ≥ +93 ms even with no contention. Not pursued. |
| Chosen candidate | **Emit-on-hands with drop-when-busy**, pose 2 threads / spinning off / hands 1 thread: DWPose on one worker, hands on a second, each observation posted back to the CameraX thread as soon as its own hands end; a frame arriving while DWPose is busy is released unprocessed so CameraX hands over the next fresh one. |
| Parity | **Bit-identical, 32 of 32 device comparisons** (host re-check agrees), four engines, incl. every committed word and sentence; free-running drop arms equal serial on exactly their accepted frames; no reordering or duplication. |
| Live throughput | **7.18 obs/s** (A/B/A/B arm; serial 5.91 / 5.72; first pipeline 7.16). **Sustained 10-minute run: 6.36 obs/s** (per minute 5.8–7.2) in a scene where 61% of frames needed two hand refinements (36% in the A/B arm). |
| Live latency (capture→observation) | **p50 302 / p95 398 ms** vs serial 298–303 / 362–363 (**+4 / +35 ms**); first pipeline 539 / 637. Same-work frames: +10–20 ms (one hand region), +30–45 ms (two). 10-minute run p50 355 / p95 431. |
| CPU / memory / thermal | CPU 250% of one core vs serial 186–190% (**+~60%**) and first pipeline 309%. PSS ~284–291 MB vs 278–290 serial. 10 minutes: thermal status 0 throughout, battery 38.0→39.5 °C, DWPose time flat (no throttling), no crash or recognition stop. |
| Predicted end-to-end effect (offline, 3 seeds) | At the A/B gap mix: **natural 46.0% → 50.4% correct words (+4.4), continuous 27.2% → 31.8% (+4.6)**, fewer extra events (1.40 → 1.03 /min); first pipeline 49.6 / 29.4. At the two-hand-heavy 10-minute mix: 47.2 / 28.2 (+1.2 / +1.0; serial reference measured in lighter scenes, so conservative). |
| Go / no-go | **Latency target: met. Throughput target (~7 obs/s): met in the A/B arm, missed sustained in two-hand-heavy scenes (6.36).** **Recommendation: GO for later integration as an opt-in, default-off debug build or engine option, not as a default.** It beats the first pipeline on every measured axis and beats serial on throughput, cadence and predicted accuracy at near-serial latency; the remaining costs are +~60% of a core and scene-dependent throughput. See §8. |

## 1. Candidate01 flow (behind `-PrecognitionV3PipelinedPose=true -PrecognitionV3PipelineEmitOnHands=true`, debug only, release hard-off)

CameraX thread, `analyze(frame t)`:
1. Emit every frame whose hands already finished (FIFO queue, this thread only).
2. If DWPose of the previous accepted frame is still running, or the hand stage of the frame that
   last used this frame's native slot is still running: count `busy_drops_total`, close the frame,
   return. Nothing of the frame is used.
3. Otherwise preprocess into one of two alternating native slots, close the CameraX frame (the
   native kernel keeps its own copy), submit DWPose(*t*) to `AppHearV3Pose` and hands(*t*) to
   `AppHearV3Hands`. The hand task waits for DWPose(*t*), crops and refines from the same slot, and
   builds the frame's hand/body evidence (`perceive`, no session/owner/UI access).
4. When hands(*t*) finish, the task queues itself and posts a drain to the CameraX executor. The
   camera thread builds `PhoneRawObservation` (assigning `sourceIndex`), runs the owner,
   `session.consume`, overlay, UI and trace (`deliver`). So session, owner and UI calls stay on
   the CameraX thread, in capture order.

Invariants: one DWPose in flight; a slot is never rewritten before its hand stage finished; the
hand worker never takes the analyzer lock; frames started before `resetTemporalSession` are
dropped on arrival (generation counter); `close()` waits for both workers before releasing native
memory; a pixel-reading owner keeps the serial path (unchanged rule).

Code changes: `Candidate01FrameAnalyzer.kt` (`emit()` split into `perceive()` + `deliver()`, with
the serial and first-pipeline paths calling both back to back; new emit-on-hands path; test hooks
`awaitCapacity()` / `drainPipeline()`), `build.gradle.kts` (flag; requires the pipeline flag),
`RecognitionActivity.kt` (passes `cameraExecutor` as `deliveryExecutor`; file encoding kept).
Trace: emit rows add `v3_emit_on_hands`, `delivery_wait_ms`, `busy_drops_total`; serial and
first-pipeline rows are unchanged.

## 2. Why this design (evidence)

`docs/audit/probes/word_accuracy/perception_throughput/simulate_schedules.py` replays each frame's
measured preprocess / DWPose / hands time from the live traces through a model of CameraX
KEEP_ONLY_LATEST at 66.654 ms frames, with the camera→analyzer delay estimated from serial (99.7 ms)
and the delivery cost (11.6 ms). Calibration against the live runs it was fitted on:

| Live run | Measured obs/s | Model obs/s | Measured p50 / p95 | Model p50 / p95 |
|---|---:|---:|---|---|
| Serial A | 5.60 | 5.88 | 305 / 372 ms | 302 / 367 ms |
| Serial C | 5.12 | 5.34 | 328 / 372 ms | 325 / 367 ms |
| Pipelined B | 6.52 | 6.75 | 578 / 687 ms | 573 / 668 ms |

The pipelined latency only matched once the model took the next frame at *close* time (the
CameraX rule above), not at analyze return; that rule is the main design input.

## 3. Modelled candidate vs contention (no accuracy claim; serial A timings scaled)

| DWPose × / hands × | Drop-when-busy: obs/s, p50, p95 (A / C timings) | Hold (rejected): obs/s, p50 |
|---|---|---|
| 1.0 / 1.0 | 7.54, 256, 322 / 7.49, 297, 319 | 10.66, 395 |
| 1.1 / 1.2 | 7.45, 277, 362 / 7.44, 333, 357 | 9.33, 432 |
| 1.2 / 1.4 | 7.01, 300, 408 / 6.72, 370, 416 | 8.29, 464 |
| 1.3 / 1.6 | 6.53, 321, 452 / 6.03, 411, 462 | 7.45, 505 |
| 1.6 / 2.1 (≈ first pipeline) | 5.30, 379, 562 / 4.75, 520, 574 | 5.86, 610 |

Serial reference: 302 / 325 ms. The 2-frame cadence (7.5 obs/s) holds while DWPose + preprocess
stays under 133 ms; above that the gaps jump to 3 frames, a cliff rather than a slope.

Offline reference points (existing `e2e_camera_grid.py` runs, unchanged models, 406 DEV streams):
steady 2-frame cadence 51.0% correct natural / 30.4% continuous (29.3% with every 2-frame gap
just below the 133.308 ms decoder edge); serial as measured 44.6 / 25.3 (3 seeds); first pipeline
as measured 48.3 / 28.6 (3 seeds). The real prediction needs the measured candidate gap mix (§6).

## 4. Parity design (extended `PipelinedPoseParityInstrumentedTest`)

- Budgets test (STABLE, 51 phone frames and the 174-frame DEV stream): legacy = serial;
  first pipeline p2/spin/h2, p2/nospin/h2, **p2/nospin/h1** (the stream runs missing last time);
  emit-on-hands p2/spin/h2 and p2/nospin/h1, every frame accepted (`awaitCapacity` before each
  frame, so DWPose(*t*) still overlaps hands(*t−1*)), all compared bit for bit with serial,
  including the last frame.
- Engines test (all four engines, stream): legacy, serial, first pipeline, emit p2/spin/h2, emit
  p2/nospin/h1 (all frames), and **free-running** emit p2/nospin/h1 where frames are released
  while DWPose is busy. That arm must emit strictly increasing capture indices (no reordering,
  no duplicates) and equal, bit for bit and in recognition output, a serial run fed exactly the
  accepted frames with their original timestamps (`*_subset_serial`).
- Host: `compare_pipeline_parity.py` re-reads every dump (`emit` = full serial; `X_subset_serial`
  = `X`). Host tool tests: 8 (+18 existing trace tests) pass.

### Device result (2026-10-20, M2101K7AG, user-approved; 731 s, `OK (3 tests)`)

| Comparison | Frames | Result |
|---|---:|---|
| Legacy vs serial, STABLE, phone frames / stream; all four engines, stream | 52 / 175 | identical |
| Serial vs first pipeline p2/spin/h2, p2/nospin/h2, **p2/nospin/h1** (phone frames, stream; default budget on four engines) | 51 / 174 | identical |
| Serial vs **emit p2/spin/h2** and **emit p2/nospin/h1**, every frame accepted (phone frames, stream, four engines) | 52 / 175 | **identical, incl. the last frame and every commit** (STABLE 2, experimental engines 12 sentence changes each) |
| **Free-running emit p2/nospin/h1** vs serial on its accepted frames, four engines | 23–29 accepted of 175 (146–152 released) | **identical**; capture indices strictly increasing (no reordering, no duplicates); owner image released on every frame |
| Pixel-reading owner + flag stays serial | 4 | pass |

Host re-check (`compare_pipeline_parity.py`): PASS, 32 pairs, no failures
(`perception_throughput/emit_device/host_parity_check.json`). The free-running arms release most
frames because the test feeds frames much faster than 15 fps; that exercises the release path
hard but says nothing about the live release rate.

Recorded-input throughput (no camera or preview; the schedule's ceiling, JPEG decode included):
serial 5.4–6.6 frames/s, first pipeline 7.4–8.2, **emit 10.1–11.8** (both budgets). Serial was
slower than in the first session's run (8.3–8.7), so compare within this run only.

## 5. Live device measurement (front camera, WORD, 90 s after 10 s warm-up; 40 rows skipped)

Order: serial A → emit B → serial C → first pipeline D (A/B/A/B), then a 600 s emit run. Each
arm was installed with `adb install -r` (firstInstallTime unchanged) and opened by hand.

| Run | obs/s | Gap mix 1/2/3/4 frames | Interval mean / sd | Capture→obs p50 / p95 | DWPose p50 | Hands p50 | CPU | PSS |
|---|---:|---|---|---|---:|---:|---:|---:|
| Serial A | 5.91 | 0 / 51 / 44 / 5 % | 169 / 40 ms | 298 / 363 ms | 73 ms | 56 ms | 190% | 278 MB |
| **Emit B** (p2/nospin/h1) | **7.18** | 2 / **87** / 10 / 0 % | 139 / **24** ms | **302 / 398 ms** | 103 ms | 58 ms | 250% | 291 MB |
| Serial C | 5.72 | 1 / 41 / 52 / 5 % | 175 / 40 ms | 303 / 362 ms | 72 ms | 65 ms | 186% | 290 MB |
| First pipeline D | 7.16 | 14 / 65 / 19 / 2 % | 140 / 42 ms | 539 / 637 ms | 109 ms | 113 ms | 309% | 292 MB |
| **Emit, 600 s** | **6.36** | 0 / 65 / 33 / 1 % | 157 / 36 ms | 355 / 431 ms | 113 ms | 110 ms | 248% | 284 MB |

- **Same-work latency** (frames binned by refined hand regions, estimated from hand inference
  time): one region, serial 276–280 vs emit 289–299 ms p50; two regions, serial 325–333 vs emit
  362–374 ms; first pipeline 530–599 ms. Delivery is prompt: hands-finished → camera thread
  0.3 ms p50 (`delivery_wait_ms`).
- **Why throughput varies**: two hand refinements per frame (~110 ms) lengthen the hand stage and
  slow DWPose further (≈ 117 ms), pushing DWPose + preprocess past the 133 ms two-frame budget, so
  gaps become 3 frames. In the 600 s run 61% of frames had two refinements (A/B arm: 36%), mostly
  rejected proposals (97% of frames observed no hand), so the scene was light on signing but
  heavy on hand work. Per minute: 5.8–7.2 obs/s; the last, lighter minute reached 7.21.
- **Contention moved, not removed**: with one hand thread, a hand inference stays at ~51 ms
  (serial ~50; first pipeline ~85), while DWPose slows 1.4–1.6× (72 → 103–117 ms). The process uses
  +~60% of a core over serial (first pipeline +~120%). The new threads use 70% (`AppHearV3Pose`) and
  55% (`AppHearV3Hands`); the CameraX thread drops from ~111% to ~44%.
- **Ordering and loss**: every trace has contiguous `source_index` and strictly increasing
  capture and completion times. Analyzer releases while busy: 1.09 (B) and 1.36 (600 s) frames
  per observation; they replace frames that serial would never have seen either (KEEP_ONLY_LATEST
  drops them inside CameraX). Camera HAL drops: NOT MEASURED.
- **Thermal / stability (600 s)**: thermal status 0 at every 60 s sample; battery 38.0 → 39.5 °C
  (the thermal HAL exposes no temperatures); DWPose p50 per minute 112–121 ms with no upward trend;
  PSS 268–291 MB, no growth; no crash, no "recognition stopped". Battery drain NOT MEASURED; 10
  minutes is not a long soak.
- **Decoder edge**: 2-frame gaps just below 133.308 ms were 1.5% of gaps in B but 20.5% in the
  600 s run (serial 0.3–6.3%, first pipeline 8.1%). Offline bound for all-below-edge 2-frame
  cadence: continuous −1.1 points, natural unchanged (first report §5). Not modelled in §6.
- Scenes differ between runs (one signer, hand counts above); treat ±0.3 obs/s as run spread.

## 6. Predicted end-to-end effect (offline, unchanged models, 406 DEV streams, 3 seeds)

`e2e_camera_grid.py --gap-mix <measured>` with S2-R3 Arm A e10, CONFIRM_BOUNDARY_70, materializer
and WORD_BLEND_02 (hashes as in the first report). Serial uses the pooled A + C mix.

| Cadence | Mean interval | NATURAL correct (seed range) / detected / precision / extra per min | CONTINUOUS correct (range) / detected / precision |
|---|---:|---|---|
| Serial, measured A+C | 172 ms | 46.0 (44.8–46.7) / 78.1 / 54.5 / 1.40 | 27.2 (26.4–28.1) / 52.7 / 51.0 |
| First pipeline, measured D | 140 ms | 49.6 (48.8–51.0) / 83.5 / 56.3 / 1.02 | 29.4 (28.6–30.7) / 55.4 / 52.5 |
| **Emit, measured B** | 139 ms | **50.4 (49.8–50.7)** / 84.8 / 56.2 / 1.03 | **31.8 (31.5–32.3)** / 57.4 / 54.9 |
| Emit, measured 600 s (two-hand heavy) | 157 ms | 47.2 (46.7–47.7) / 82.1 / 53.9 / 1.21 | 28.2 (28.0–28.6) / 55.0 / 50.5 |

At the same mean interval as the first pipeline, the emit cadence predicts +0.8 natural and +2.4
continuous over it, consistent with its steadier gaps (fewer 1- and 3-frame gaps). The 600 s mix
gives +1.2 / +1.0 over serial, but serial was measured in lighter scenes, so that delta is a
lower bound. Evidence: `perception_throughput/emit_e2e/`.

## 7. Status of validation

| Item | Status |
|---|---|
| Kotlin compile, all four APK pairs | PASS (§10) |
| Android unit tests | 274/275; the one failure is the pre-existing `OriginalWordBatchTest` manifest mismatch seen in every checkout |
| Device parity (51 frames + 174-frame stream, four engines, drop path) | **PASS** (§4) |
| Live A/B/A/B and 600 s run | DONE (§5) |
| End-to-end prediction at the measured gap mixes (3 seeds) | DONE (§6) |
| Rear camera (30 fps), other devices, other signers | NOT MEASURED |
| Battery drain, soak > 10 min | NOT MEASURED |
| Camera HAL drops | NOT MEASURED (analyzer releases counted) |
| Live recognition accuracy | NOT MEASURED (engineering runs have no lexical ground truth) |

## 8. Recommendation

**GO for later integration as an opt-in, default-off debug option; do not enable by default and
do not enable it automatically.**

- Against the first pipeline it wins on every measured axis: same throughput (7.18 vs 7.16), −237
  ms p50 latency, about half the extra CPU, steadier cadence, higher predicted accuracy.
- Against serial: +21–26% observations at +4 ms p50 / +35 ms p95 (A/B), predicted +4.4 natural and
  +4.6 continuous correct-word points, for +~60% of one core.
- It does **not** reliably reach ~7 obs/s: sustained 6.36 in a two-hand-heavy scene. That limit is
  hardware contention: on the Snapdragon 678's two big cores, DWPose with 2 threads plus 1 hand
  thread slows DWPose 1.4–1.6×, and two hand refinements push it past the 133 ms two-frame budget.
  Further scheduling alone cannot remove that; a cheaper hand stage (e.g. skipping refinement of
  rejected proposals, which would change outputs and needs its own evaluation) or core-aware thread
  placement would be the next levers, not another schedule.
- Before any integration: rear-camera and battery measurements, a longer soak, and a check of the
  decoder-edge effect (§5) on real signing.

## 9. Device session record

Before the "approval before installing" requirement reached this session, the earlier brief was
followed: the user's installed pair was backed up (app d0c86508…, test c21dc8a1…; matching the
previous restore), the serial/parity pair was installed with `adb install -r` (firstInstallTime
2026-10-15 20:28:05 unchanged) and the parity test started. On receiving the requirement the test
was stopped before any test case completed, the original pair was reinstalled with `adb install
-r`, and both installed APKs were hash-verified (d0c86508… / c21dc8a1…), firstInstallTime
unchanged, preferences intact (engine EXPERIMENTAL_WORD_BLEND_02, mode WORD). The previous
session's parity dumps in app storage were deleted before the run; they are preserved on the host
in that worktree's `artifacts/recognition_v3_pipeline/device/parity_dumps/`.

Backups and APK pairs: `C:\Users\Gigabyte\apphear_artifacts\recognition_v3_pipeline_emit\`
(drive F: had 0.7 GB free).

Approved parity session: serial pair (0ea8dd27… / 32d260e8…) installed with `adb install -r`
(firstInstallTime unchanged), test passed, dumps pulled, original pair reinstalled and verified
(d0c86508… / c21dc8a1…, firstInstallTime 2026-10-15 20:28:05, preferences
EXPERIMENTAL_WORD_BLEND_02 / WORD). The new parity dumps remain in app storage
(`files/recognition_v3_pipeline_parity/`) and are copied to the host artifacts.

Approved live session (user at the phone): serial A, emit B, serial C (first attempt timed out
before the screen was opened; retried as C2 without reinstalling), first pipeline D, emit 600 s.
Original pair reinstalled with `adb install -r` and verified: app d0c86508…, test c21dc8a1…,
firstInstallTime 2026-10-15 20:28:05, preferences EXPERIMENTAL_WORD_BLEND_02 / WORD.
Live summaries and run metadata: `perception_throughput/emit_device/`; raw traces in the ignored
`artifacts/recognition_v3_pipeline/live/`.

## 10. Build

Locked debug live-baseline properties (`docs/audit/baselines/debug_word_blend02_2026-10-18.json`)
plus `-PrecognitionV3Profile=true -PrecognitionV3ProfileLimit=6000` and the fixture dir; blank
credentials. APK pairs (SHA-256 prefixes, app / androidTest), all under
`C:\Users\Gigabyte\apphear_artifacts\recognition_v3_pipeline_emit\apks\`:

| Pair | Extra flags | app | androidTest |
|---|---|---|---|
| serial (also the parity pair) | none | 0ea8dd27… | 32d260e8… |
| pipelined (first schedule) | `PipelinedPose=true` | fafa18ff… | 6f4dbcff… |
| emit_p2_nospin_h1 (candidate) | `PipelinedPose`, `PipelineEmitOnHands`, `PipelinePoseSpin=false`, `PipelineHandThreads=1` | e3463c65… | 3879aff7… |
| emit_p2_spin_h2 | `PipelinedPose`, `PipelineEmitOnHands`, spin, 2 hand threads | a9bf4ed0… | 79172711… |

Model output: `docs/audit/probes/word_accuracy/perception_throughput/schedule_model.json`.
