# APPHEAR_CONTINUOUS_TRANSITION_AND_READINESS_01

Prepared 2026-09-28 (+08:00). **`DIAGNOSTIC_TOOLING_READY_WAIT_FOR_AB_CAPTURE`**.

No A/B phone experiment has been performed in this milestone. The Supervisor's hands-down vs
hands-up observation remains a hypothesis to test, not a concluded cause or training authorization.

## Baseline, scope and working commit

- Protected baseline: `76d93cecd85bf9f76064d320aa4a5791b5f0704a`.
- Protected branch: `baseline/apphear-s2-r2-integration-complete-2026-09-26`.
- Protected annotated tag: `apphear-s2-r2-integration-complete-2026-09-26`.
- Working branch: `dev/continuous-transition-diagnostics`, created directly from that commit.
- Verified diagnostic implementation commit: `befa94a54b7f0e1ebc471af21a77f2f2036641b7`.
  Subsequent documentation-only commit on this same branch records this report/context.
- Local baseline branch and dereferenced tag still resolve to the protected SHA. No baseline ref
  was moved; no extra development branch was created. This task's diagnostic commits are local,
  not pushed.
- No change under Android main/release sources, main/debug assets, native libraries, build
  configuration, production UI, or `pipeline/`. No model inference rule, threshold, timer,
  Admission, materializer, vocabulary, or recognizer change.

Terminology: **physical boundaries** are human-observed lexical onset/end, not button markers;
**opening** means START_ACTIVE_CANDIDATE, not an emitted event; **completion/commit** is the single
EMIT_SIGN_EVENT decision; **result** is later recognizer/UI delivery. None of the response intervals
below is described as model inference latency.

## Exact current implementation trace

| Responsibility | Current implementation and behavior |
|---|---|
| Normal app owner | `RecognitionActivity.start` loads `PhoneProductionSession` asynchronously; `bindPhoneCamera` binds one `Candidate01FrameAnalyzer` for front CameraX analysis. No legacy 258 backend runs in this mode. |
| Current observation | `Candidate01FrameAnalyzer.analyze` produces genuine current-frame `PhoneRawObservation` with source index and ImageProxy timestamp. In the reused debug Activity the existing `LiveRawFrame.toPhoneRawObservation` performs that adaptation. |
| Features / S2 | `PhoneSegmentationFeatureBuilder.derive` in shared `PhoneCausalCore.kt`; `PhoneS2Runner.predict` applies the atomic selected normalization. `predictNormalized` retains at most 61 genuine rows, invokes TFLite once, softmaxes the **last/current output**, and chooses argmax in PRE/ACTIVE/POST order. |
| Episode owner | `PhoneCausalEventProducer.consume(timestampMs, argmaxState)` in shared `PhoneCausalCore.kt`. The normal session and existing debug controller each instantiate this same class, not two simultaneous live decoders. |
| Admission / opening | Only IDLE + ACTIVE calls `PhoneNewSignAdmission.evaluate`, currently PASS_THROUGH. Accepted onset opens ACTIVE_CANDIDATE immediately. No confidence, hand/body or recognized-class gate. |
| Accumulation | ACTIVE updates lastActiveIndex/lastActiveMs. POST starts POST_CANDIDATE; PRE starts PRE_GAP. PRE gaps shorter than 133.308 ms can bridge; sustained PRE discards the candidate. Discard does not reopen from that same observation. |
| Completion | In POST_CANDIDATE, resumed ACTIVE cancels POST, **including ACTIVE at or beyond the confirmation boundary**. Otherwise after 266.616 ms, lastActiveMs − candidateStartMs must be at least 133.308 ms. Eligible episode emits one immutable event. The code does not require every intervening observation to be POST. |
| WAIT entry | Event ID is assigned at commit. Candidate is cleared and state becomes EVENT_EMITTED_WAIT_REARM. Eligible PRE/POST on the commit observation itself starts recovery at commit time. Completion and temporal commit are the same decision, not separate waiting stages. |
| Recovery | PRE_OR_POST_EXPERIMENTAL accepts either PRE or POST toward 399.924 ms persistence. ACTIVE resets the recovery timer (ACTIVE_INTERRUPTED_RECOVERY). An observation gap **greater than** 533.232 ms resets recovery first; an eligible current observation may start a fresh timer but cannot credit the missing gap. The continuity limit is a recovery guard, not a universal S2-history/ACTIVE-episode reset. |
| READY restoration | REARM_COMPLETE returns IDLE. S2/features continue updating while WAIT; WAIT does not call Admission or open a new candidate. READY is not word-confidence-dependent, and there is no reopening on the same rearm-complete observation. |
| Materializer / V2 | At commit, `PhoneObservationRingBuffer.materialize` uses the same frozen cadence-safe contract, 256 observations / 30 s ring, genuine IDs/timestamps and commit cap. `phoneRecognitionRawSequence` → `RecognitionV2.temporalView(DENSE)` produces `[96,350]` plus mask. |
| Recognition / sentence | `PhoneProductionSession.consume` invokes `RecognitionV2LiveRecognizer.invoke` once; increasing event-ID guard precedes sentence mutation. `SentenceBuilder.add` owns sentence appending. WAIT holds the displayed result; IDLE clears heldCommit, not the sentence. |
| Normal UI | `Candidate01FrameAnalyzer` delivers the session result/sentence; `RecognitionActivity.onFrame` → `RecognitionUiSnapshot.from` → `renderRecognitionSnapshot`. UI renders a sentence snapshot; it does not append again per frame. |

Two plausible mechanisms are observable, **not yet proven on continuous signing**: ACTIVE can
cancel a pending completion, and ACTIVE after commit can interrupt recovery. The audit also found
that the older host replay utility began POST recovery one observation after commit, unlike current
Android. An explicit opt-in reference adapter now aligns that audit timing; historical default replay
behavior is unchanged. This is not an Android/runtime defect fix.

Older architecture/build/runtime documents retain historical MediaPipe-era targets and research
next-step text. The protected integrated baseline, latest integration progress and this bounded
Project Lead instruction govern this task; those historical entries do not reopen prior branches.

## Reused infrastructure and changes

| File | Change |
|---|---|
| `android/app/src/debug/java/com/example/apphear/perceptionvnext/PerceptionVNextLiveRecognitionActivity.kt` | Opt-in seven-block cohort; whole-sequence START/STOP markers; no per-word READY gate. Reuses continuous originals, exact recorder and final drain. Avoids redundant per-attempt RGB/geometry retention and duplicate image writes in this mode only. Records actual debug display delivery. |
| `.../PhoneCausalController.kt` (debug) | Observer-only candidate identity/span, decision/completion clocks, WAIT entry, global materialized/V2 source IDs and recognizer clocks. Flushes logs/snapshot on explicit finalization. Adds synchronized debug UI-delivery log, guarded for teardown. Shared inference calls remain unchanged. |
| `.../PhoneTransitionDiagnosticCohort.kt` (debug) | Fixed A/B sequences and five bounded negative navigation blocks; baseline/milestone identity. Markers never reset features, S2, episode or ring. |
| `android/app/src/test/.../PhoneTransitionDiagnosticCohortTest.kt` | Fixed-cohort/navigation regression. |
| `eval/runtime_diagnostics/phone_repeated_recognition_integration.py` | Optional `exact_android_commit_recovery=True` for current Android replay; existing default unchanged. Uses the existing governed decoder, not another segmentation implementation. |
| `eval/runtime_diagnostics/continuous_transition_diagnostics.py` | Capture integrity audit, source-only review preparation, human-boundary validation and response/transition evaluation. No perception rerun, model fitting, new decision policy or automatic labels. |
| `eval/runtime_diagnostics/continuous_transition_diagnostics.html` | Small source-observation player/label exporter. Genuine timestamp spacing and stepping; no model predictions shown. Local autosave tied to exact evidence hash. |
| `tests/test_continuous_transition_diagnostics.py` | Synthetic A/B/C/D, unfinished merged episode, gap/uncertainty/integrity checks and existing 669-row frozen-package host regression. |

The reusable runtime remains shared/main; the additional recording/cohort remains debug-only,
behind build flags plus an explicit intent extra. Normal RecognitionActivity and release do not save
frames or tensors. Heavy evidence is inherited and bounded at 3,600 processed observations; use a
representative arm64 phone and keep this session roughly 2–3 minutes. Do not target the slow itel.

## Evidence and linkage

Every processed observation links source index ↔ monotonic source timestamp ↔ original/evidence
sidecar ↔ exact raw-v1 binary row ↔ Android 378 and normalized input ↔ S2 probabilities/argmax.
The existing exact recorder preserves binary float values, missingness, source dimensions and hashes.

`observations.jsonl` retains lifecycle before/after/action, candidate opening index/time/span,
WAIT entry, recovery policy/state/timer/elapsed/reason, Admission decision/reason, support/motion,
runtime stage times, exact record index and original path. Event ID does **not** exist before commit;
candidate source-opening identity and a tentative ordinal are recorded instead. Discarded candidates
must not be mistaken for emitted events.

`events.jsonl` retains logical ACTIVE, terminal POST and source commit bounds; materialized global
source IDs; selected global Recognition V2 IDs/mask count; existing Top-5; recognizer start/end and
stage durations. Per-observation decision elapsedRealtime clock records runtime commit timing.
`ui_delivery.jsonl` links one emitted ID to actual **diagnostic Activity** display delivery. It does
not assert normal-app sentence commits; those passed the previous normal-app integration gate and
are untouched here. Only Top-5 plus Top-1 are persisted, not the full 236-output vector.

Full-session originals cover processed observations, not every camera frame. Dropped/unprocessed
camera intervals cannot be visually reconstructed. Human boundaries are therefore inclusive source
observation indices with sampling uncertainty; do not invent sub-observation precision.

## Evaluator and attribution

`prepare` requires: correct cohort/package/config; hash-verified exact binaries/linkage;
chronological indices; complete final visual drain and hashed originals; all seven BEGIN/COMPLETE
pairs; one UI delivery per emitted ID. It checks existing-decoder event identities and **every
lifecycle state** against Android, rearm transitions and reference materializer IDs using the same
bounded causal ring. Any capture failure/incomplete evidence stops automatic analysis.

The reviewer marks eight physical signs and a bounded interval in each negative block, or explicitly
UNCERTAIN. Buttons are navigation only. Entire blocks must be reviewed; uncertain/lexical/preparation
intervals are excluded from negative metrics. No automatic whole-block negative labels.

`analyze` associates logical ACTIVE episodes with human physical signs, identifies shared/unfinished
candidates, reports candidate opening and actual minimum-span acquisition, and conservatively probes
continuous ACTIVE reaching the existing 133.308 ms minimum when lifecycle blocks admission. That
probe is **offline evidence**, not a new online threshold/policy; actual accepted candidate spans
(including existing bridged behavior) are reported separately. Multiple simultaneous mechanisms
can be reported; ambiguous association stays ambiguous.

- `A_REARM_LIFECYCLE_BLOCK`: useful ACTIVE observed while WAIT prevents event opening.
- `B_NO_INTERSIGN_S2_BOUNDARY`: shared logical/pending episode spans consecutive physical signs.
  Inspect recorded POST-cancellation/state traces before attributing this specifically to S2 versus
  the frozen completion requirements; this label alone does not authorize S2 training.
- `C_S2_ACTIVE_REACQUISITION_FAILURE`: available IDLE but no ACTIVE, or a new episode lacks the
  existing minimum ACTIVE span.
- `D_EVENT_DELIVERY_OK_DOWNSTREAM`: a distinct physical-sign episode opens and qualifies/emits;
  opening delay, window containment and lexical/UI outcome remain separate evidence.
- Additional flags: unfinished opened episode, early/wrong episode, multiple events, observation
  cadence confound, and ambiguous/insufficient evidence.

For each of the six sign-to-sign transitions, JSON reports physical end, terminal POST, commit,
state after commit, next physical onset/state, probabilities/actions, recovery completion/reset,
candidate opening, window IDs and recognition/UI evidence. Intervals include end→completion/commit,
commit→rearm, next onset→rearm (signed), next onset→qualifying ACTIVE, opening and recognizer/UI
delivery. Null means unavailable/ambiguous, not zero. Source/runtime clock sanity is checked; mixed
clock response measurements assume compatible ImageProxy/elapsedRealtime timebases, not a calibrated
camera latency measurement. Cadence p50/p95 and over-limit gaps accompany reviewed positive spans.

Confirmed negative intervals report ACTIVE separately from logical episodes fully contained within
the reviewed interval. Overlapping episodes and commits whose onset was elsewhere remain for manual
attribution, not automatically false positives. No production false-positive-rate claim is made.

## Verification performed

- Full JVM suite: **96 tests, zero failures/errors** (includes existing lifecycle/Admission,
  feature, materializer, V2/raw adapter, exact serialization and final visual-drain tests).
- Focused host suite: **51 passing**. Includes new evaluator/integrity regressions and existing
  rearm, Admission evidence, exact-capture loader, materializer/CAL and S2-R2 config regressions.
- Existing 669-observation package fixture: Android-package normalization equals the stored host
  fixture exactly; frozen Keras versus host TFLite max probability difference **8.64267349e-7**;
  zero argmax mismatches. No new model export or phone-model claim.
- Debug and release APKs: **BUILD SUCCESSFUL**. Both contain 128 packaged main assets with zero
  byte/hash differences from source; 32 pre-existing `_backup*` assets are excluded by normal asset
  packaging. Candidate01 `lib/arm64-v8a/libperceptionvnext.so` is present.
- New Python files Ruff clean; reviewer JavaScript syntax passes Node `--check`; CLI help and
  synthetic review/export preparation pass. Full interactive phone/reviewer use awaits capture.
- `git diff --check` passes. Main/release code/assets, `pipeline/` and build config have zero diff
  from baseline. Existing API deprecation warnings are retained, not fixed.
- ADB currently reports **no connected device**. No fresh install, connected parity, capture,
  live cadence, human-boundary result or root-cause conclusion is claimed.
- Black startup hung even on `--version`; isolated tooling issue, not runtime/model failure. Used
  installed Ruff formatter/linter instead, without modifying the environment. The old replay file
  retains pre-existing lint findings outside the small adapter change.

Commands executed (PowerShell, repository root unless noted):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_continuous_transition_diagnostics.py tests/test_phone_event_lifecycle_rearm_correction.py tests/test_phone_s2_exact_parity_and_r2_decision.py tests/test_phone_new_sign_admission_and_active_acquisition.py tests/test_phone_sign_admission_and_rearm.py tests/test_recognition_window_materializer.py tests/test_phase8a_m_causal_sparse_window_materialization.py tests/test_s2_r2_continuous_domain_correction.py -q
.\.venv\Scripts\python.exe -m ruff check eval/runtime_diagnostics/continuous_transition_diagnostics.py tests/test_continuous_transition_diagnostics.py
```

## Supervisor install / launch commands

Use PowerShell. Connect the representative Xiaomi, authorize USB debugging, and keep AppHear closed
before launch. Do not uninstall/clear data. Do not launch again while a capture is in progress.

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
$env:JAVA_HOME = 'C:\Program Files\Java\jdk-17'
Push-Location -LiteralPath '.\android'
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug :app:assembleRelease '-PperceptionVNext=true' '-PphoneCausalRecognition=true' '-PapphearPhoneS2Package=S2_R2_CANDIDATE' --console=plain
if ($LASTEXITCODE -ne 0) { Pop-Location; throw 'Build failed; stop here.' }
Pop-Location
$adb = 'D:\AndroidStudio\Android\Sdk\platform-tools\adb.exe'
& $adb devices -l
$deviceId = Read-Host 'Paste the authorized device serial from the list above'
& $adb -s $deviceId install -r '.\android\app\build\outputs\apk\debug\app-debug.apk'
if ($LASTEXITCODE -ne 0) { throw 'Install failed; stop here.' }
& $adb -s $deviceId shell am start -n 'com.example.apphear/.perceptionvnext.PerceptionVNextLiveRecognitionActivity' --ez perception_vnext_enabled true --ez phone_causal_enabled true --ez continuous_transition_diagnostics true --ez s2_exact_parity_capture true --es phone_s2_package S2_R2_CANDIDATE --es phone_rearm_policy PRE_OR_POST_EXPERIMENTAL --es validation_signer_id supervisor_transition_design_01
if ($LASTEXITCODE -ne 0) { throw 'Launch failed; stop here.' }
```

Here `supervisor_transition_design_01` is a stable non-secret **design** signer ID; it makes no
independent-validation claim. Use the same actual person for A and B. Allow camera permission if
asked. The screen must show Block 1/7 and live processed counts/state, not the normal recognition
screen. This task deliberately reuses the debug capture Activity, not a second normal-app backend.

## Exact physical procedure

1. Keep upper body/hands visible with ordinary front lighting. Let initialization/native warmup
   finish. Before **each whole positive sequence only**, start from neutral and an initial IDLE
   (`state=IDLE` in status). START BLOCK being enabled is **not** proof of READY in this mode.
2. **A_HANDS_DOWN**: tap START BLOCK once. Perform **HELLO → lower hands naturally → HOME → lower
   hands naturally → TABLE → lower hands naturally → HELLO**. No word-level taps; do not wait for
   READY between words, add an artificial long delay, retry, or react to predictions. After the
   last sign, return to neutral and keep recording about three seconds, then tap STOP once.
3. Let the block marker drain; the stream/models continue without reset. Return to the initial
   neutral/IDLE condition once before B. Do not change any settings.
4. **B_HANDS_UP**: tap START BLOCK once. Perform **HELLO → HOME → TABLE → HELLO** with hands
   remaining in signing space during the three transitions. No deliberate hands-down reset,
   READY wait, per-word taps or retries. After the final sign, hold the natural finishing position
   about three seconds, return to neutral for about three seconds, then STOP once.
5. Capture the next five blocks, each with one START/STOP pair, about 5–8 seconds including
   brief natural neutral context: (a) raise/hold an open hand without lexical signing, (b) one
   ordinary seat/body adjustment, (c) stand/move normally, (d) one grooming/clothing adjustment,
   (e) one ordinary phone interaction. Do not intentionally perform ASL. Do not tune or retry;
   ambiguous/preparatory motion will be explicitly excluded during visual review.
6. After STOP on block 7, tap **FINALIZE & SAVE EVIDENCE**. Keep the app open/USB connected until
   **VISUAL EVIDENCE SAVED** and verified-original count appear. Only then close it. A crash,
   missing block, incomplete saved message, cap error or severe slowdown is an incident, not a
   complete A/B result; preserve files and report it rather than silently replacing the run.

The three-second tails retain completion/recovery evidence **after** the sequence, not deliberate
delays between signs. Physically lower hands only for A, not as a workaround inside B.

## Pull, blinded review and analyze

Continue in the same PowerShell with `$adb` / `$deviceId` defined. The root is intentionally reused:

`/sdcard/Android/data/com.example.apphear/files/phone_repeated_recognition_integration_01/session_...`

```powershell
$phoneRoot = '/sdcard/Android/data/com.example.apphear/files/phone_repeated_recognition_integration_01'
$sessionName = (& $adb -s $deviceId shell cat "$phoneRoot/latest_session.txt").Trim()
if ($LASTEXITCODE -ne 0 -or $sessionName -notmatch '^session_\d{8}T\d{6}Z$') { throw 'No valid session pointer; stop.' }
$pullRoot = 'F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\perception_vnext\recognition_utility_236_01\continuous_transition_readiness_01\device_capture'
New-Item -ItemType Directory -Path $pullRoot -Force | Out-Null
$sessionRoot = Join-Path $pullRoot $sessionName
if (Test-Path -LiteralPath $sessionRoot) { throw 'This session already exists locally; preserve it and inspect before pulling again.' }
& $adb -s $deviceId pull "$phoneRoot/$sessionName" $sessionRoot
if ($LASTEXITCODE -ne 0) { throw 'Pull incomplete; stop and preserve the partial copy.' }
.\.venv\Scripts\python.exe -m eval.runtime_diagnostics.continuous_transition_diagnostics prepare --session $sessionRoot
if ($LASTEXITCODE -ne 0) { throw 'Integrity audit failed; do not label or interpret this as a complete run.' }
.\.venv\Scripts\python.exe -m http.server 8774 --bind 127.0.0.1 --directory $sessionRoot
```

While the server runs, open `http://127.0.0.1:8774/transition_review/index.html`. Do not open S2
logs/predictions when deciding human boundaries. Watch each whole block, step through genuine
observations, select each fixed sign and mark physical START/END with inclusive source indices.
End means the lexical sign ends, **not** when the hands finally lower during recovery. Keep
uncertainty explicit. For each negative block, mark only a visually defensible bounded interval,
or leave UNCERTAIN. Check Entire block reviewed and enter a non-secret reviewer ID.

Download `human_boundaries.json` and save/move it into
`$sessionRoot\transition_review\human_boundaries.json` (not the template). Do not overwrite an
existing review blindly. The evaluator checks session/hash, order, interval bounds and overlap.
Stop the HTTP server with Ctrl+C, then, in the same shell:

```powershell
.\.venv\Scripts\python.exe -m eval.runtime_diagnostics.continuous_transition_diagnostics analyze --session $sessionRoot
if ($LASTEXITCODE -ne 0) { throw 'Human labels/integrity require correction; no experimental conclusion yet.' }
Get-Content -LiteralPath (Join-Path $sessionRoot 'transition_analysis\RESULT.md')
```

If using a new PowerShell, set repository location and `$sessionRoot` to the actual pulled directory
first. Outputs: `transition_review/integrity.json`, source-only `review_manifest.json`, labels,
and `transition_analysis/{result.json,RESULT.md}`. Source captures remain unchanged. Share the
small result files rather than trying to paste every telemetry row.

## Review / stop boundary

Architecture review: plan alignment PASS; system-boundary integrity PASS; local handoff readiness
PASS, **device/evidence gate pending**. No critical or important implementation violation found in
the bounded review. Known limitations: sampled originals, inherited diagnostic overhead, observation
boundary uncertainty, uncalibrated mixed-clock result timing, and debug rather than normal-UI delivery.
These must accompany the evidence; they are not permission to modify the model/lifecycle.

Excluded local material remains untouched/uncommitted: `.codex_tmp/`, prior `phone_pull_*` folders,
`context/recognition_upgrade/a1_signing_sentinel_01.csv`, generated builds, datasets and captures.

**STOP HERE.** Await the governed A/B capture and human review. No readiness/admission fix, shorter
recovery, S2 training, recognizer training, feature/window change or protected TEST access. The
Project Lead reviews the resulting same-runtime evidence before authorizing a behavioral change.
