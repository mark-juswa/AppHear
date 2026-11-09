# Phase 1.1 — Blind-Reviewed Shadow Validation

Date: 2026-11-09 · Branch: `jepjep-claude` (working tree; **nothing committed or pushed**)
Builds on: `docs/PROJECT_RECONNAISSANCE.md`, `docs/PHASE_1_RECOGNITION_RELIABILITY.md`, `docs/audit/`.

Evidence labels: **[CONFIRMED-CODE]** read in code · **[CONFIRMED-RUN]** executed in this phase · **[REPRODUCED]** repo numbers I recomputed · **[REPO-REPORTED]** · **[SUSPECTED]** · **[EVIDENCE GAP]**.

## 0. What this phase does and does not establish

**It builds the instrument and the protocol. It produces no accuracy evidence.** No signer was recorded, no annotation was made, no shadow log from a real signing session exists. Every number in this document is either (a) a Phase 1 offline-replay number restated with its tier, or (b) the output of a unit test on a hand-written synthetic scenario, which is labelled synthetic and must never be quoted as a result about the system. Shadow evaluation does **not** prove accuracy by itself; it only becomes evidence once independently reviewed phone recordings are collected under §5 and evaluated under §6.

---

## 1. Audit of the Phase 1 gate (Task 1)

Files re-read in the working tree: `PhoneCommitGate.kt`, `PhoneProductionSession.kt`, `PhoneRecognitionConfiguration.kt`, `Candidate01FrameAnalyzer.kt`, plus `docs/audit/probes/output_policy/phase1_commit_gate_eval.py`.

| Check | Result |
|---|---|
| One integration point | `PhoneProductionSession.consume` is the only place `PhoneEventCommitter.decide` is called; the only other gate consumer is `Candidate01FrameAnalyzer` via `isReadyForDisplay`. **[CONFIRMED-CODE]** |
| Gate input = the signal it was validated on | `phoneHandSpanFraction` reads `PhoneRawObservation.handObserved`, which `phoneRecognitionRawSequence` copies 1:1 into the raw sequence's `hand_observed` (`PhoneRecognitionRawSequence.kt:36-37`), the field the offline ledgers' `hand_fraction` is computed from (`event_reliability.py`). **[CONFIRMED-CODE]** |
| Floors match the calibrated pairing | STABLE 0.55, EXPERIMENTAL 0.75, BLEND none (`commitPolicy()`); my recomputation of the repo's published gate counts matches exactly for both (101/102, 173/98). **[REPRODUCED]** |
| A withheld event leaves no trace | Not in sentence, evidence, UI state, last-gloss memory; the event id still advances. **[CONFIRMED-CODE + JVM tests]** |
| Flag semantics | `WORD_COMMIT_GATE_ENABLED` default true (debug property `wordCommitGate`), release true. |

**Findings from the audit (new in this phase)**
1. **Configuration fallback is silent.** If `EXPERIMENTAL` fails to load, `PhoneProductionSession.load` runs `STABLE` and sets `fallbackReason`. The gate correctly uses the *actual* configuration, but a log that recorded only the requested one would mislabel events. The shadow record therefore stores the actual configuration **and** a `fallback` flag, and the report calls fallback events out. **[CONFIRMED-CODE]**
2. **The gate does not address duplicate events.** A second event on the same physical sign is judged on its own probability and can be committed; `SentenceBuilder` only collapses *consecutive identical* words. The shadow report counts duplicates explicitly (`committed_duplicate`) so this is measured instead of assumed. **[CONFIRMED-CODE]**
3. **The gate has never run end to end on a device.** Phase 1 verified it at JVM level and by offline replay. The emulator smoke in §8.3 is the first run inside the real app, and it proves wiring only.
4. **No defect found in the gate itself.** No change to thresholds or rules was made (per the rules of this phase).

---

## 2. Shadow evaluation mechanism (Task 2)

### 2.1 What is compared

For every emitted sign event, one record holds both policies side by side, computed from **the numbers the session already produced** (no extra inference, no extra model call):

- **A — original behaviour:** `legacy = COMMIT` (every usable top-1 would be committed).
- **B — Phase 1 gate:** `gated ∈ {ACCEPT, REJECT, UNCERTAIN}` + `reason`. If the gate flag is off, B is still evaluated arithmetically (`PhoneCommitPolicy.evaluate`) so the log shows what the gate *would* have done.
- **What the app actually did:** `actual ∈ {COMMIT, WITHHELD}` (so a gate-off run is distinguishable).

### 2.2 Record contents (schema `apphear.shadow_event.v1`, pinned by a golden fixture)

`sid` (random per process), `gen` (camera generation), `run` (coordinator label), `seq`, `wall_ms`, `cfg` + `s2` + `fallback`, `gate_on`, `floor`, `hand_rule`, `event` id, `top1`, `top5` glosses, `p1`, `p2`, `margin`, `hand_frac`, `span_obs`, `win_obs`, `start_ago_ms`/`end_ago_ms` (logical sign span relative to the commit observation), `s2_ms`, `rec_ms`, `lag_ms` (camera timestamp → decision, only when plausibly comparable, else `null`), `legacy`, `gated`, `reason`, `actual`. Marker lines: `session_start` (app version, SDK, device model, configuration, gate flag), `generation_reset`, `session_end` (written / dropped / write_failures / internal_errors).

### 2.3 Guarantees and how each is enforced

| Requirement | Mechanism | Test |
|---|---|---|
| Never enters the sentence / does not modify recognition | `ShadowEvalLog` gets an immutable record built **after** `committer.decide`; it has no reference to the sentence, committer, decoder or models | `attachingAFailingOrStalledShadowLogDoesNotChangeTheSentenceOrAnyDecision` |
| No added inference | Only already-computed values are copied; `phoneHandSpanFraction`/`policy.evaluate` are arithmetic | by construction, `[CONFIRMED-CODE]` |
| Cannot block the camera thread | `record()` = non-blocking `ArrayBlockingQueue.offer` (capacity 256, drop + count when full); JSON building and file I/O run on a separate minimum-priority daemon thread | `recordNeverBlocksWhenTheSinkIsStalledAndTheQueueStaysBounded` (5,000 records against a stalled sink), `eachRecordCallIsCheapEvenWhenEveryWriteFails` |
| Cannot throw into recognition | every path catches `Throwable` and increments a counter; the session wraps record building in its own `try/catch` | `sinkFailuresNever…`, mutation test (§8.2) |
| Failure recovery | 5 consecutive sink failures → log disables itself (records are dropped, nothing accumulates); the next camera generation (`resetTemporalSession`) re-enables it | `sinkFailuresNeverReachTheCallerDisableTheLogAndRecoverAtTheNextGeneration`, `anIsolatedFailureDoesNotDisableTheLog` |
| No memory growth | bounded queue; records are small immutable objects; `close()` joins and stops the writer thread | `closeStopsTheWriterThread…`, `closeReturnsPromptlyEvenWithAStalledSink`, `separateLogsNeverShareState…` |
| Bounded storage | ≤ 8 files × 256 KiB = **2 MiB**; lines > 4096 chars rejected; files older than 14 days deleted at open; only `shadow_*.jsonl` are ever touched | `fileSinkNeverExceedsItsFileCountAndSizeBudget`, `fileSinkDeletesFilesOlderThanTheRetentionWindow` |
| Privacy | no image, video, landmark, tensor, user or device identifier; explicit key allow-list; random session id; run label restricted to `[A-Za-z0-9_-]{≤64}`; files in `noBackupFilesDir` (excluded from backup/transfer); **default build never creates the log** (`SHADOW_EVAL_ENABLED` false; release hard-coded false) | `eventLinesAreValidJsonWithExactlyTheAllowedKeys…`, `noImageLandmark…`, `runLabelCanNeverCarryFreeText…`, `sessionIds…` |
| Python reader and app writer cannot drift | one golden line produced by the real Kotlin serializer, compared byte-for-byte on the Kotlin side and parsed on the Python side | `theEventLineMatchesTheSharedGoldenFixture…`, `KotlinContractTest` |

### 2.4 Privacy position (and what remains a human obligation)
The log contains **what the model predicted and when**, not what the user signed, and no media. Predicted words can still reveal content, so: the logger exists only in opt-in debug builds given to consenting participants; participants must be told what is logged (§5.5); logs can be deleted by clearing app data. **There is no in-app consent screen** — consent is procedural (signed form + the study build), a product decision I did not make. `device_model` and `sdk_int` are recorded for stratification and are not user identifiers. Wall-clock time is recorded because it is the only way to align with video.

---

## 3. Evaluation methodology (Tasks 3–4)

### 3.1 Evidence tiers — never mixed in one number

| Tier | Meaning | Status |
|---|---|---|
| `offline_replay` | Device-recorded observations or stitched clips replayed offline through the production decoder/recognizer, labelled by the repo's own review. | **Exists** (Phase 1 §3.4, `docs/audit/`). Development-exposed; not independent evidence. |
| `phone_recorded` | New phone recordings of consenting signers, replayed offline through the same Candidate01 → S2 → decoder → Recognition-v2 code, labelled blind from video. | **Does not exist.** Requires the capture rig that exports raw observations (existing debug tooling `PerceptionVNextLiveRecognitionActivity`); not built here. |
| `live_device` | The real app running on a phone while a person signs; shadow log + independent video labels. | **Does not exist.** This phase delivers the instrument and protocol. |

The report tool takes the tier from the manifest and writes one section per `(tier, configuration)`.

### 3.2 Label independence
- Labels are made **from video only**, by annotators who have not seen app output; the app screen must not be visible in the recording.
- The annotation file schema is a **structural allow-list**: signs (`start_ms`, `end_ms`, `gloss`), non-sign intervals (`activity`), excluded intervals (`reason`), annotator id. Any other key (e.g. `predicted`, `p1`, `top1`, `confidence`) makes the tool refuse to run.
- **Freeze before looking:** the SHA-256 and lock time of the annotation file are written into the manifest *before* logs are pulled; the tool refuses if the file's hash differs.
- The manifest carries an annotator attestation (count, blind yes/no). The tool prints it and warns when blindness is not attested or there is a single annotator. **The tool cannot prove blindness**; it can only make a violation explicit and auditable.

### 3.3 Signer-leakage prevention
- Evaluation signers get new pseudonymous ids. A **signer registry** must list every signer ever used for training, tuning or threshold calibration (including the phone design signer and the two declared signers of existing phone sessions, and the ASL-Citizen calibration signers P5/P12/P21).
- The tool **refuses** if an `evaluation` signer appears in the registry, or if the registry is missing. `--development-only` runs anyway but stamps the report *"DEVELOPMENT-EXPOSED RUN – NOT EVIDENCE"* and lists the leakage.
- Thresholds are frozen (0.55 / 0.75). The tool reads the logged decision (`gated`) and **never searches thresholds**; any new operating point requires a new, signer-disjoint calibration set *and* a new evaluation set.

### 3.4 Event ↔ label join (documented rule, `shadow_report.py`)
1. Convert each event's logical sign span to video time: `commit_capture = wall_ms − lag_ms` (lag 0 if unknown), `span = [commit − start_ago, commit − end_ago]`, minus the session's `video_t0_wall_utc_ms`.
2. A **sign** label claims an event if ≥ 50 % of the event's span lies inside the labelled sign ± the clock tolerance (default 300 ms). Among events claiming one sign, the largest overlap is **credited** (`CORRECT` if its top-1 equals the annotated gloss, else `WRONG`); the others are `DUPLICATE`.
3. Otherwise ≥ 50 % inside a **non-sign** interval → `NONSIGN` (with its activity); inside an **excluded** interval → `EXCLUDED`.
4. Anything else → `UNLABELED` (ambiguous/partial overlap), or `UNLOCATED` (no span). These are **counted and reported but never scored** (same convention as the repo's `UNREVIEWED`).
5. Signs with no claiming event are **upstream misses** (the decoder never emitted); they are invisible to the gate and reported separately.

### 3.5 Metrics (per policy A and B, per `(tier, configuration)`)
- **Precision** = committed correct ÷ (committed correct + committed wrong + committed duplicate + committed non-sign).
- **Recall, event level (correct-word retention)** = committed correct ÷ correct events; **false-rejection rate** = 1 − retention.
- **Recall, end to end (sign recall)** = signs whose credited event is correct *and* committed ÷ all labelled signs.
- **Recognition coverage** = signs whose credited event was committed (any word) ÷ all signs. **Upstream-miss rate** = signs with no event ÷ signs.
- **False-positive rate (non-sign)** = committed non-sign events ÷ non-sign events; also **false non-sign commits per minute** of labelled non-sign video.
- **F1:** `f1_event` = H(precision, retention); `f1_end_to_end` = H(precision, sign recall). Both are reported and named; they are not interchangeable.
- **Confusion matrix:** rows = annotated gloss, `NONSIGN:<activity>`, `DUPLICATE_OF:<gloss>`; columns = committed top-1 or `WITHHELD` / `NO_EVENT`. Written as CSV per policy.
- **Latency:** `capture_to_decision_ms`, decoder's by-design `logical_end_to_commit_ms`, recognizer and S2 invocation ms (all from the log); and **physical sign end → decision** from labelled signs (video-labelled end vs credited event). Percentiles p50/p95 only, never the mean.
- **Intervals:** Wilson 95 %; every rate also carries `n` and a `small_n` flag (n < 20).

### 3.6 Reports produced
Per `(tier, configuration)` — **STABLE and EXPERIMENTAL are separate sections** — with sub-reports **by signer**, **by sign class** (sign recall, coverage, precision-when-predicted, A vs B), **by non-sign activity** (committed / events / minutes, A vs B), **by condition** (lighting, distance, speed, …), overall confusion matrices and latency. Output: `report.json`, `report.md`, `confusion_*.csv`.

### 3.7 Automatic caveats (cannot be switched off)
Fewer than 3 evaluation signers → "no generalisation claim"; fewer than 30 labelled non-sign events (the repo's own bar for reopening admission) → "false-positive rate not decision-grade"; fallback events; mixed gate-on/off; and "Wilson intervals ignore signer clustering — not population intervals". Log health (dropped / write failures per session) is included so silent data loss is visible.

### 3.7a Why sample sizes matter (Wilson 95 %, computed with the tool's own function)
| Observed | n | 95 % interval |
|---|---:|---|
| 0 false commits | 30 non-sign events | [0, 0.114] |
| 0 false commits | 60 | [0, 0.060] |
| 0 false commits | 100 | [0, 0.037] |
| 3 false commits | 60 | [0.017, 0.137] |
| 25 correct words withheld | 100 correct events | [0.176, 0.343] |
| 50 withheld | 200 | [0.195, 0.314] |

So 30 non-sign events (the repo's bar) can only show "≤ ~11 %" at best; **≥ 60 non-sign events and ≥ 100 correct events per configuration** are needed for intervals narrow enough to support a product decision. Per-class claims need ≥ 10 signs per class; with fewer the report shows `small_n` and the class table is descriptive only.

---

## 4. Data requirements (summary)
Per configuration (STABLE, EXPERIMENTAL): **≥ 5 evaluation signers (minimum 3)**, all signer-disjoint from the registry; **≥ 60 labelled non-sign events**, **≥ 100 correct-word events**; ≥ 10 signs for every class that will be reported individually; every condition cell in §5.2 with at least 2 signers. Existing development-exposed phone sessions may be used for **debugging the tool**, never counted as evidence.

---

## 5. Phone-recorded evaluation protocol (Task 3) — reproducible

### 5.1 Participants
- ≥ 5 signers per configuration, recruited independently of anyone whose data trained, tuned or calibrated any model (check against the registry).
- "Qualified" is defined by the study team **before** recruiting (e.g. community-recognised ASL fluency judged by a Deaf reviewer) and recorded in the manifest. I do not assert any qualification standard here.
- Written informed consent covering the external video, the app log content (§2.4), storage, retention and deletion. Participants are pseudonymised (`E01…`).

### 5.2 Session matrix (counterbalanced order, recorded per run in `manifest.sessions[].conditions`)
| Factor | Levels |
|---|---|
| Lighting | bright · normal indoor · dim · backlit/window |
| Distance (hand-to-camera framing) | near · normal · far (as the app's guidance allows) |
| Signing speed | slow/careful · natural · fast |
| Configuration | STABLE; EXPERIMENTAL (separate runs; confirm `fallback` is false) |
| Camera | front (the verified path) |
| Device | the target Xiaomi M2101K7AG first; further devices as separate strata |

Not every cell for every signer: use a fractional design that guarantees each level is covered by ≥ 2 signers and varies one factor at a time from the "normal indoor / normal / natural" baseline.

### 5.3 Run blocks (each run is one `run_label`, e.g. `E03_dim_far_fast_r2`)
1. **Isolated signs:** a scripted list of vocabulary signs with rest between each; classes chosen to cover **every class to be reported individually**, the repo's documented confusable pairs (e.g. BYE/YES/NO, SORRY/GOOD, KNOW/HELLO) and a spread of handshapes/locations; ≥ 10 repetitions per class across signers.
2. **Continuous signing:** short scripted phrases (consecutive signs) to exercise duplicate/merge behaviour.
3. **Partial and incomplete signs:** signs deliberately started and aborted; signs with the hand dropped early.
4. **Non-sign blocks**, ≥ 3 minutes per category per signer, each a separate labelled interval: open-hand idle · random hand movements · hand-to-face/hair/glasses · drinking/typing/phone handling · body movement · **seat adjustment** · hand repositioning (rest ↔ ready) · background movement by a second person (hands of the signer out of frame) · transitions between signs.
5. **Out-of-vocabulary real signs** (so rejection of valid-but-unsupported signing is also measured).

### 5.4 Capture rig and clock alignment
- The app runs on the study phone. **A separate camera** records the signer (upper body + hands) for labelling; the app screen is not visible in that video.
- Time alignment: before each run the external video shows a clock synchronised to the same network time as the phone (or a displayed UTC time); the annotator reads the UTC wall-clock of video t = 0 into `video_t0_wall_utc_ms`. Expected alignment error is the clock error plus the ~0.3 s tolerance; **measure it** with two or three hand-clap/known-event checks per session and record the worst case in the manifest (`clock_tolerance_ms`).
- Set the run label *before* opening the recognition screen (§8.1) so the log is attributable.

### 5.5 Labelling procedure
1. Two annotators, independently, from video only, with no access to app logs or screen.
2. Per run: label every sign (`start_ms`, `end_ms`, gloss), every non-sign interval (activity), and mark uncertain stretches as `excluded`.
3. A third reviewer adjudicates disagreements (gloss mismatch, interval IoU below the study's pre-stated cut-off). Report inter-annotator agreement (gloss agreement; interval IoU) — **not implemented in the tool** (limitation L4); compute it before freezing.
4. Write the merged file, compute its SHA-256, record hash + UTC lock time + annotator attestation in the manifest, **then** pull the logs.

### 5.6 Pre-registration
Before any log is opened, write down (and date) the decision rule: which metric/CI statement would count as the gate "improving reliability without unacceptable loss". The acceptable **false-rejection budget is a product decision I have not set**; the rule must state it numerically, e.g. "upper Wilson bound of FPR(non-sign) for B ≤ X and lower bound of sign recall for B ≥ Y". Changing the rule after seeing data invalidates the study.

---

## 6. Tool and file inventory
- Android: `ShadowEvalLog.kt` (log, bounded sink), `ShadowEvalLogFactory.kt` (Android wiring), wiring in `PhoneProductionSession.kt`, flag `SHADOW_EVAL_ENABLED` / property `shadowEval` (debug only, default false; release hard-coded false).
- Analysis: `eval/shadow_validation/shadow_report.py`, `templates/{manifest,annotations,signer_registry}.template.json`.
- Tests: `ShadowEvalLogTest.kt` (20), `tests/test_shadow_report.py` (29), shared fixture `android/app/src/test/resources/shadow_eval/golden_event_line.json`.

---

## 7. Performance and reliability (Task 5)

- **Camera thread cost per event:** building one small record and one `offer`. JVM tests bound the call cost (< 0.5 ms per call averaged over 2,000 calls with a failing sink; 5,000 calls in < 1 s with a stalled sink). **Not measured on a phone** `[EVIDENCE GAP]`; events occur about once per sign, not per frame.
- **No frame delay / inference:** nothing runs per frame; the writer is a separate minimum-priority thread.
- **Memory:** bounded queue (256 records) and one writer thread; the thread ends on `close()` (session close). Long-run heap behaviour on a device not measured.
- **Storage:** hard cap 2 MiB (8 × 256 KiB), 14-day retention, never in backup.
- **UI:** untouched.
- **Failure/recovery:** sink failures, stalls, close-while-stalled, unwritable directory, oversized lines, torn log lines (Python side skips a torn final line) and generation recovery are tested.
- **How to verify on a device** is in §8.1 step 6.

---

## 8. Device-testing procedure

### 8.1 Procedure
1. **Build (debug only):** `./gradlew :app:assembleDebug -PshadowEval=true` (add the usual project flags; the logger is compiled in only with this property). Optionally `-PwordCommitGate=false` for a gate-off arm (B is then logged hypothetically; `actual` shows the truth).
2. **Install** with `adb install -r`. Do **not** clear app data by default (repo rule); to start a participant clean, clear data deliberately and record that you did.
3. **Select the configuration** in the app's Settings (debug builds). Confirm in logcat (`AppHearPhone`: `configuration=… fallback=false`).
4. **Label the run** before opening the recognition screen:
   `adb shell run-as com.example.apphear sh -c 'mkdir -p no_backup/shadow_eval && echo E03_dim_far_fast_r2 > no_backup/shadow_eval/run_label.txt'`
   (allowed characters `A–Z a–z 0–9 _ -`; read at session start and at each camera generation).
5. **Run the session** (§5.3) while the external camera records; note the UTC time of video t = 0.
6. **Overhead check (per device, once):** run 10 minutes with and without `-PshadowEval=true`; compare `AppHearPerf`/`AppHearV3` p50/p95 inter-frame gap and processed fps (existing profiling flags), `adb shell dumpsys meminfo com.example.apphear` before and after 30 minutes, and the size of `no_backup/shadow_eval` (must stay ≤ 2 MiB). Any increase in p95 frame gap beyond noise is a defect.
7. **Pull logs:** `adb exec-out run-as com.example.apphear sh -c 'cd no_backup/shadow_eval && tar cf - shadow_*.jsonl' > logs.tar`. Check the `session_end` lines: `dropped` and `write_failures` should be 0; otherwise report them as data loss.
8. **Delete on request / at study end:** `adb shell pm clear com.example.apphear` (or `run-as … rm -r no_backup/shadow_eval`).
9. **Freeze labels, then analyse:** fill the three templates, then
   `python -m eval.shadow_validation.shadow_report --manifest M.json --logs LOGDIR --out OUT`
   (exit code 2 + `REFUSED: …` if any precondition fails).

### 8.2 What the tests demonstrated  **[CONFIRMED-RUN]**
Scratch-copy runs (repo untouched; Gradle 8.14.3, Python 3.14.6):

| Run | Result |
|---|---|
| Full `:app:testDebugUnitTest` | **376 tests, 0 failures, 0 errors, 0 skipped** (Phase 1 baseline 356; +20 shadow-log tests) |
| `ShadowEvalLogTest` fresh runs | 5 consecutive runs, all 20 pass (concurrency-flakiness check) |
| Mutation check A | removing the self-disable rule → `sinkFailuresNever…Recover…` fails |
| Mutation check B | making `record()` throw/propagate → `eachRecordCallIsCheap…`, `attachingAFailing…DoesNotChange…`, `closeReturnsPromptly…` fail |
| `:app:compileReleaseKotlin`, `:app:compileDebugAndroidTestKotlin` | success |
| `python -m unittest tests.test_shadow_report` | **29 tests pass** (hand-computed synthetic scenario; refusal rules; Kotlin golden contract; CLI exit codes) |
| Phase 1 `PhoneCommitGateTest` | 20 / 20 still pass |

**Not run:** Python research suite, instrumented tests, release APK build, any on-device timing, any real-signer data.

### 8.3 Emulator wiring smoke  **[CONFIRMED-RUN]**
Scope: an arm64 emulator (`sdk_gphone16k_arm64`, SDK 37) with a **virtual camera**. A debug APK built with `-PshadowEval=true` from the scratch copy was installed, the camera permission granted, a run label written with `run-as`, and the recognition screen opened through the existing debug alias `.RuD10BenchmarkActivity`. The app was uninstalled afterwards (the emulator had no AppHear before).

| Observation | Result |
|---|---|
| Candidate01 session loaded | yes (`configuration=STABLE … fallback=false`) |
| Shadow log created in `no_backup/shadow_eval` | yes; file mode `-rw-------` |
| Run label picked up | yes (`"run":"PILOT_wiring_smoke_r1"`) |
| `session_start` metadata | app version, SDK, device model, configuration, gate flag |
| `generation_reset` on camera bind and on screen stop | yes (gen 1, gen 2) |
| `session_end` on closing the screen | yes: `written=3 dropped=0 write_failures=0 internal_errors=0` |
| Crash / ANR in logcat | none |

**What this does not show:** no hands were in the virtual scene, so **no sign event was emitted and no `event` line was written on a device**; event serialisation is covered by the JVM golden-line test only. Nothing was timed, so overhead is still unmeasured. (Side observation, not a finding: the 4 KB-aligned native library from reconnaissance finding F-006 loaded on this 16 KB-page emulator image; that says nothing about Google Play's alignment requirement.)

---

## 9. Limitations and risks

- **L1. No evidence yet.** Everything depends on collecting §5 data; until then the gate's real-world effect is unmeasured. Phase 1's replay numbers remain development-exposed.
- **L2. Blindness cannot be enforced by software**, only attested and made auditable. A study with non-blind annotators is not independent.
- **L3. Time alignment error** (clock offset between phone and external video) directly causes mis-joined events. Tolerance and measured error must be reported; very fast sign sequences are most exposed.
- **L4. Not implemented:** inter-annotator agreement statistics; signer-clustered (cluster bootstrap) intervals; automatic power analysis; the `phone_recorded` capture/replay rig. Intervals are event-level Wilson and must not be read as population intervals.
- **L5. Logging records predictions, not a transcript of the user**, yet predicted words are still user-derived data; consent is procedural, there is no in-app consent screen.
- **L6. `lag_ms` is only meaningful when CameraX timestamps share the elapsed-realtime clock;** implausible values are nulled. Verify on each device model before quoting latency.
- **L7. Shadow of an unevaluated gate.** The gate is already ON by default (Phase 1 L7). This phase makes its effect measurable but does not change the default.
- **L8. Duplicates** are not addressed by the gate (§1 finding 2); the report measures them.
- **L9. Latency "end to end" here ends at the decision**, not at pixels on screen; add a screen recording if display latency is needed.
- **L10. Temporal consistency** was deliberately not added (rule of this phase); it would need its own evaluation.

## 10. Recommended next steps
1. Approve/adjust §5 (qualification standard, consent form, FRR budget, pre-registered decision rule).
2. Run the device overhead check (§8.1 step 6) on the Xiaomi, then a pilot with 1–2 *development* signers to debug alignment; **mark them development-only**.
3. Recruit ≥ 5 independent signers; run STABLE first, then EXPERIMENTAL; freeze labels; analyse.
4. Only if the evaluation supports it, decide on thresholds/policy with a **new** calibration set; otherwise keep `-PwordCommitGate=false` as the documented rollback.
5. Build the `phone_recorded` replay rig so the same recordings can be re-scored offline as the models change.
