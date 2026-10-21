# Perception Scheduler Integration: Serial vs Low-Latency Debug Setting (2026-10-21)

**Where the work is.** Uncommitted in the `apphear-audit-2f2723` worktree (`claude/s2-r3-eval-suite`, HEAD `5833df1c`). It contains three layers:
1. the changes of commit `06e40b2f` (first pipelined experiment, from `claude/strange-colden-466995`);
2. the emit-on-hands work, taken as a reviewed patch (`955f18ed…`) from the uncommitted `upbeat-bardeen-772415` worktree, which is untouched;
3. the integration below.

All three were applied as working-tree changes; nothing is committed or merged. They were first assembled in a scratch worktree, `perception-scheduler-integration` (branch `claude/perception-scheduler-integration` at `06e40b2f`). Its 74 changed files are byte-identical to this worktree; it can be deleted on approval.

**Unchanged:** models, thresholds, S2-R3 Arm A, confirm-boundary, materializer, WORD blends and SentenceBuilder. Protected TEST, E6 and Tier 3 were not opened.

**Device evaluation done (2026-10-21, approved).** Installed with `adb install -r`; parity passed; live comparison run. **Result: outcome C.** On this phone today, Low-latency gave more observations but higher latency and fewer recognized words than Serial. Details in §10.

**Reverted (2026-10-21, user decision).** The Android source is back at HEAD: 9 files restored and 6 new files removed.
- The removed changes are saved in `C:\Users\Gigabyte\apphear_artifacts\perception_scheduler_eval_20261021\reverted_integration\`:
  - `modified_android.patch` and `modified_android_files.tar`;
  - `new_android_files.tar`.
- Kept in the working tree: this report, the evidence under `docs/audit/probes/word_accuracy/perception_throughput/`, and the host tools `tools/recognition_v3/*pipeline*` with their test.
- The phone was restored with `adb install -r` to the previous app (`0469d1b8…`) and test APK (`c21dc8a1…`). `firstInstallTime` is unchanged and the settings were kept. The unused `perception_schedule.xml` preference (value SERIAL) was left in place rather than clearing app data; the previous build ignores it.

The sections below describe the integration as it was evaluated.

## 1. Architecture and integration approach

The path is unchanged: CameraX → **Candidate01 (schedule selectable)** → S2-R3 Arm A → confirm-boundary → materializer → WORD engine → SentenceBuilder/UI.

| Decision | Choice | Why |
|---|---|---|
| Selection mechanism | A **debug-only runtime setting**, "Perception scheduling (debug)": `SERIAL` (default) or `LOW_LATENCY` | Both arms can be compared with one install by switching the setting. No `adb install -r` between arms, so different builds are never compared |
| When it applies | Read once when ASL Recognition opens; each open builds a new analyzer | No mid-session switch. The previous analyzer's workers are drained by the existing `close()`, which joins both workers before freeing native buffers |
| Relation to engines | Independent of the engine setting (Stable / Experimental / Blend 01 / Blend 02) | No duplicated pipeline and no combined engine variants |
| Release builds | Always `SERIAL`: the setting needs `BuildConfig.DEBUG`, and the build-time pipeline flags are hard-off in release | Required |
| Research build flags | Kept. `-PrecognitionV3PipelinedPose…` still wins when set; the toast then reads "build flag" | The measurement harness and parity reproduction keep working |
| Low-latency budget | Emit-on-hands, drop-when-busy: DWPose 2 threads / no spinning, hands 1 thread (`p2/nospin/h1`) | The device-measured candidate (7.18 obs/s at +4 ms p50), and one of the two budgets proven bit-identical |

**Not changed:** the scheduler algorithm. It is reused exactly as validated.

## 2. Components changed

Brought in (reviewed, not rewritten):
- `06e40b2f`: the pipelined analyzer path, parity test, tools and evidence.
- Emit-on-hands:
  - `Candidate01FrameAnalyzer.kt`: `perceive()`/`deliver()` split, emit-on-hands path, generation counter, test hooks;
  - `build.gradle.kts`: research flags;
  - `RecognitionActivity.kt`: `deliveryExecutor = cameraExecutor`;
  - extended `PipelinedPoseParityInstrumentedTest`, host tools, report and evidence.

New in this integration:

| File | Change |
|---|---|
| `perceptionvnext/PerceptionSchedule.kt` (new) | `SERIAL` → no pipeline; `LOW_LATENCY` → `Candidate01PipelineBudget(2, false, 1, emitOnHands = true)`; unknown or release choices resolve to `SERIAL` |
| `data/settings/PerceptionScheduleSettings.kt` (new) | SharedPreferences `perception_schedule` / `selected`; available only in debug builds |
| `RecognitionActivity.kt` | Resolves the schedule when the screen opens and passes `requestedPipeline`; the debug toast reads "Recognition: <engine> \| Perception: <schedule>". Legacy encoding preserved byte for byte |
| `Candidate01FrameAnalyzer.kt` | One log line per analyzer, now also for serial (`candidate01 scheduling=SERIAL \| PIPELINED_POSE_EMIT_ON_HANDS …`), so recognition logs can be attributed to a schedule. Log only |
| Settings UI | `row_setting_perception_schedule.xml` (copy of the engine row), included after the engine row in Settings and Profile; five strings; `SettingsContent.setupPerceptionScheduleChoice()` |
| `PerceptionScheduleTest.kt` (new JVM test) | Default and release resolve to SERIAL; SERIAL keeps the serial path; LOW_LATENCY is exactly the parity-proven budget |

## 3. What stays protected

- **Default perception path:** with the setting at SERIAL (the default for every existing install), the analyzer is built exactly as before (`requestedPipeline = null`).
- **Engines and their models:** Stable, Experimental, Blend 01 and Blend 02 are untouched. The APK carries the same model bytes: frozen WORD `1ccf0afa…`, WORD_BLEND_01 `bc8a6c91…`, WORD_BLEND_02 `40533bc3…`, Arm A `e7725ef2…`, S2-R2 `7d26c896…`, DWPose `37b0f265…`, hand refiner `6acda74a…`.
- **WORD/FINGERSPELL ownership:**
  - **Pixel-reading owners stay serial.** Manual spelling capture reads pixels, so the analyzer keeps the serial path for it (existing rule, device-tested).
  - **Continuous spelling is safe.** `FingerspellRuntime.consume` returns into the continuous path before touching the image (verified in source), so it may use low-latency.
- **Lifecycle:**
  - **Threading:** session, owner, UI and trace calls stay on the CameraX thread.
  - **Resets:** camera switches and spelling resets go through `resetTemporalSession()`. That increments the generation, so frames in flight are dropped on arrival.
  - **Destroy:** the camera executor is shut down and awaited before `close()`, so late deliveries are no-ops, and `close()` joins both workers.
- **Text-to-ASL and unrelated features:** not touched.

## 4. Verification results

| Check | Result |
|---|---|
| JVM unit tests (full `testDebugUnitTest`) | **278 / 278 pass**, including `PerceptionScheduleTest` 3/3 and `ExperimentalRecognitionConfigurationTest` 7/7 |
| Host tool tests (`tests/test_recognition_v3_pipeline_tools.py`) | 8 / 8 pass |
| Debug APK + androidTest APK | Built with the locked live-baseline properties plus `-PrecognitionV3Profile=true -PrecognitionV3ProfileLimit=20000`. Generated `BuildConfig` has `RECOGNITION_V3_PIPELINED_POSE_ENABLED = false`, so the setting alone selects the schedule. Hashes in §9 |
| Recorded-frame parity, ordering, drop path, four engines, pixel-owner fallback (`PipelinedPoseParityInstrumentedTest`) | **Proven on the device on 2026-10-20** for this scheduler code and budget: 32/32 bit-identical, strictly increasing capture indices, accepted-frame subsets equal serial, commits and sentences equal. **Re-run on this build on 2026-10-21: 3/3 on the device, host re-check 32/32** (§10) |
| Selection and release default | JVM-tested (resolve); runtime wiring by code review. The on-device check that the toast and log name the chosen schedule is step 1 of §7 |

**Identical frames give identical observations, not identical live outcomes.** Low-latency processes *different* (more) frames than serial, so live recognition is expected to differ. §7 measures that difference.

## 5. Can the two schedules be selected safely?

**Yes:**
- one analyzer per screen open;
- no mid-session switch;
- the default is unchanged;
- release cannot select low-latency;
- pixel-reading owners fall back to serial;
- worker shutdown and stale-frame dropping use the device-tested design.

**One residual risk:** a recognition failure on the low-latency path stops recognition exactly as on serial. There is no automatic mid-session fallback; choose Serial and reopen the screen.

## 6. Remaining risks

1. **Scene-dependent throughput.** 7.18 obs/s in the A/B run, but 6.36 sustained when 61% of frames needed two hand refinements; DWPose slows 1.4–1.6× under contention. This is a hardware limit.
2. **CPU** rises about 60% of one core (250% vs 186–190%). PSS flat and thermal status 0 over 10 minutes; battery drain not measured.
3. **Decoder edge.** Two-frame gaps just below the 133.308 ms threshold reached 20.5% in the long run; the offline bound is ≤ −1.1 continuous points. The decoder is not changed.
4. **Commit work on the camera thread.** With WORD_BLEND_02 (plus the logged WORD_BLEND_01), about 20 ms per committed word runs in `deliver()`. This happens only on commit frames, but can delay the next frame's acceptance there; watch the live summary.
5. **Coverage limits.** Rear camera, other devices, other signers, and soaks longer than 10 minutes are not measured.

## 7. Proposed device evaluation (needs your approval; nothing installed yet)

**Preserve first.**
1. Record the installed app and test APKs (pull `base.apk`, SHA-256; expected app `d0c86508…`), `firstInstallTime` and preferences (engine `EXPERIMENTAL_WORD_BLEND_02`, mode `WORD`).
2. Back them up to `C:\Users\Gigabyte\apphear_artifacts\` (drive F: is nearly full).

**Install** the pair with `adb install -r` only. Check that `firstInstallTime` is unchanged and preferences are kept. No uninstall, no clearing of data.

**Steps.**
1. **Smoke (1 min).** Open ASL Recognition at Serial, then at Low-latency. Check that the toast and the `candidate01 scheduling=` log name each schedule, and that recognition runs.
2. **On-device parity (about 12 min, unattended).** `am instrument` for `PipelinedPoseParityInstrumentedTest`; pull the dumps; host re-check with `compare_pipeline_parity.py`.
3. **Live A/B/A/B** with one APK, engine WORD_BLEND_02, arms **Serial → Low-latency → Serial → Low-latency**. Switch the setting and reopen the screen between arms; nothing is reinstalled. Each arm runs about 2.5 minutes, captured with `run_pipeline_measurement.ps1 -SkipInstall` (timing trace and `/proc` snapshots). Every arm follows the same protocol:
   - **a. 8 known words, twice each, with a rest between words:** HELLO, HOME, TIME, HOT, TIRED, COLD, SORRY, PLEASE. References are in `artifacts/word_phone_protocol_01/reference/`.
   - **b. Consecutive signing:** HELLO HOME TIME, twice without pauses.
   - **c. Two hands busy for 20 s**, the hand-refinement-heavy condition.
   - **d. 20 s of ordinary non-sign movement.**

Ground truth is the protocol, not the log. Scoring reuses `score_phone_ab.py`, which counts a commit correct only against the intended word of its block; you report any deviation.

**Success criteria, fixed before measurement.** Low-latency is compared with the mean of its neighbouring serial arms.

| Type | Criterion |
|---|---|
| Label-free, must pass | obs/s ≥ +15%; capture→observation p50 ≤ serial + 30 ms and p95 ≤ serial + 60 ms; no "recognition stopped", crash or ordering error; PSS growth < 30 MB; thermal status 0 |
| Recognition, directional | Intended words recognized: Low-latency ≥ Serial (summed over two arms, about 44 signs each); unwanted words (block d plus extras) not higher by more than 1 per arm; duplicates not higher; block c still within the label-free bounds |

**Interpretation.** About 44 signs per schedule from one signer can only show a direction. The offline prediction is +4.4 natural and +4.6 continuous correct-word points; the phone test checks that real use does not contradict it and that nothing regresses. No accuracy claim comes from unlabeled predictions.

## 8. After the evaluation

| Outcome | Next step |
|---|---|
| **A.** Label-free pass and recognition ≥ serial | Keep Low-latency as the leading experimental schedule and propose checkpoint commits. The default stays Serial |
| **B.** Mixed (e.g. good in a/b, poor in c) | Report the condition. A follow-up (e.g. core-aware thread placement) only for a measured limitation, as its own milestone |
| **C.** No recognition benefit | Keep it as research behind the debug setting, or revert; serial stays |

WORD research continues separately: package 03 human review, then WORD_BLEND_03. This milestone trains nothing.

## 9. Build record

Locked debug live-baseline properties (`docs/audit/baselines/debug_word_blend02_2026-10-18.json`) plus `-PrecognitionV3Profile=true -PrecognitionV3ProfileLimit=20000 -PrecognitionV3FixtureDir=<artifacts/recognition_v3_pipeline/android_fixtures>` (androidTest only); blank credentials.

| APK | SHA-256 |
|---|---|
| Candidate app (installed) | `ca8da414e5ef9ae457ae95a22ff11450d417e38356aab062f9aee64a4430509e` |
| Candidate androidTest (with fixtures, installed) | `7161826ac55f511df52e45249a9bbbe8394de1aeb6f9e9efb1090590d7b383ac` |
| Previous app (backup) | `0469d1b8…` |
| Previous androidTest (backup) | `c21dc8a1…` |

The backups and saved preferences are in `C:\Users\Gigabyte\apphear_artifacts\perception_scheduler_eval_20261021\backup\`. To restore the previous build, run `adb install -r` with the backed-up APKs.

## 10. Device evaluation results (2026-10-21)

**Preservation.**
- Installed with `adb install -r` only; `firstInstallTime` was unchanged and preferences were kept (engine `EXPERIMENTAL_WORD_BLEND_02`).
- Nothing was uninstalled or cleared.

**Smoke.**
- Both schedules logged `candidate01 scheduling=` with the expected value, and both committed HELLO.
- The toast named the schedule. No crash.

**On-device parity: 9/9.**
- WORD_BLEND_01/02 parity: max deviation ≤ 3e-7.
- Arm A parity: 0 argmax mismatches.
- Scheduler parity on four engines: 3/3.
- Host re-check: `host_parity_check.json` PASS 32/32.

**Live comparison.** One signer and one APK; engine WORD_BLEND_02; front camera, indoors; 170 s per arm with a 10 s warm-up.

**Arm order** became Low-latency, Serial, Low-latency, Serial. Arm 1 was meant to be Serial, but the saved setting was still Low-latency: the settings label on another screen was stale (a UI bug, see risks). Arm 1 was therefore recorded and analysed as Low-latency. Before every later arm the saved setting was checked over adb, and every arm's schedule was confirmed from its `candidate01 scheduling=` log line.

### Label-free (pre-registered gates; Low-latency vs the mean of the two Serial arms)

| Arm | Schedule | obs/s | capture→obs p50 / p95 (ms) | DWPose p50 | hands wall p50 | CPU (% of one core) | PSS range (MB) | thermal |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 `live_s1` | Low-latency | 6.10 | 372 / 456 | 117 | 111 | 254 | 282–295 | 0 |
| 2 `live_s2` | Serial | 5.62 | 303 / 369 | 76 | 56 | 189 | 263–274 | 0 |
| 3 `live_l3` | Low-latency | 6.30 | 367 / 443 | 114 | 110 | 241 | 265–287* | 0 |
| 4 `live_s4` | Serial | 5.51 | 313 / 370 | 75 | 107 | 187 | 258–270 | 0 |

\*Excluding one transient 118 MB sample at 10.8 s.

Battery temperature was 41.7–43.0 °C throughout. Low-latency released 1.38–1.46 frames per observation while DWPose was busy.

| Gate | Low-latency vs Serial | Pass? |
|---|---|---|
| obs/s ≥ +15% | 6.20 vs 5.57: **+11.4%** | **No** |
| p50 ≤ serial + 30 ms | 370 vs 308: **+62 ms** | **No** |
| p95 ≤ serial + 60 ms | 450 vs 370: **+80 ms** | **No** |
| No crash, "recognition stopped" or ordering error | none in any arm | Yes |
| PSS growth < 30 MB within an arm | flat | Yes |
| Thermal status 0 | 0 throughout | Yes |

**Why the latency grew (MEASURED).**
- DWPose slowed from about 75 ms to about 115 ms when the pose and hand workers competed for cores.
- Each frame also waited a median of about 62 ms (`pose_wait_ms`) before its hand stage started.

The earlier 2026-10-20 A/B run measured 7.18 obs/s at +4 ms p50. Today's result does not reproduce that. A **HYPOTHESIS**, not tested: the warmer phone (about 42 °C) and the scene mix are possible causes.

### Recognition (directional; one signer, 22 intended signs per arm)

The automatic gap grouping in `score_phone_ab.py` misaligned blocks (rests were not always ≥ 7 s), so per-block scoring was not used. Each arm was instead scored **alignment-free**:
- **Intended hits:** commits of an intended word, each word capped at its protocol count (HELLO, HOME and TIME 4 each; HOT, TIRED, COLD, SORRY and PLEASE 2 each). This is an upper bound, because a correct word committed in the wrong block still counts.
- **Extras:** all other commits.

| Arm | Schedule | Commits | Intended hits | Extras | Consecutive repeats |
|---|---|---:|---:|---:|---:|
| 1 | Low-latency | 15 | 7 | 8 | 4 |
| 2 | Serial | 21 | 8 | 13 | 3 |
| 3 | Low-latency | 28 | 9 | 19 | 4 |
| 4 | Serial | 22 | 14 | 8 | 5 |
| **Low-latency total** | | 43 | **16 / 44** | **27** | 8 |
| **Serial total** | | 43 | **22 / 44** | **21** | 8 |

**What these numbers can and cannot support.**
- **Direction:** the recognition direction is against Low-latency. It found fewer intended words (16 vs 22) and made more extras (+3 per arm, above the +1 allowance). Repeats were equal.
- **Sample size:** 44 signs per schedule from one signer cannot establish an accuracy difference.
- **Learning effect:** the best arm was the last one, so learning during the session may have contributed.
- **Missing words:** PLEASE was never recognized and TIME rarely, in either schedule (known hard classes, WORD_PRIORITIES §2).
- **Accuracy claims:** none are made from this session.

### Outcome: C (no benefit on this phone today)

- Both gate groups fail: Low-latency did not reach the throughput or latency gates, and recognition was not better.
- **Decision for the user:**
  - Serial stays the default and the only release behavior (unchanged).
  - Low-latency stays available only behind the debug setting as research, or is reverted.
- **No follow-up scheduling work is proposed** without new evidence. Running the hands on more threads would compete for the same cores, and the measured limit is contention on the CPU cores.

**Found during the evaluation.** The "Perception scheduling (debug)" row shows the choice saved when that screen was built. Another screen (Settings vs Profile) can therefore show a stale label until it is rebuilt. The saved choice itself was always correct. This is a small, debug-only fix that has not been made.

**Artifacts.**
- In git, `docs/audit/probes/word_accuracy/perception_throughput/scheduler_device/`:
  - per-arm summary and run files;
  - `word_scores.json`;
  - `live_protocol.json`;
  - `host_parity_check.json`;
  - both instrument outputs.
- Full logs (ignored): `artifacts/recognition_v3_pipeline/live/live_{s1,s2,l3,s4}_20261021-*` (stream, summary, run, `/proc` and thermal snapshots).
- `C:\Users\Gigabyte\apphear_artifacts\perception_scheduler_eval_20261021\`: backup, parity, smoke log and `live_protocol.json`.
