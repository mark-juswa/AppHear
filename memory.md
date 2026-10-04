# Memory — Centered prediction cue

Last updated: 2026-10-04 +08:00

## What was built

- Removed the visible prediction-strip label, centered the leading predicted phrase, retained smaller alternatives, and added a brief teal pop when the latest committed sign visually supports any one expected concept under the existing matcher policy. This remains a partial prediction cue; it cannot create a full context-supported interpretation or mutate raw output.

## Decisions made

- Rank and animate predictions only; keep `RECOGNIZED` and Hear/TTS raw. A single anchor can guide visual hierarchy but never counts as a verified whole phrase. No recognizer, model, provider, or matcher thresholds changed.

## Problems solved

- The high-ranked suggestion is now visibly centered. A single supported sign can respond visually even when the full predicted phrase is not yet signed.

## Current state

- JVM 150/150 pass; debug, release, and Android-test APKs build. Private debug APK is installed on the representative phone with matching host/device hash. The phone denied the test companion installation (`INSTALL_FAILED_USER_RESTRICTED`); no instrumentation result from this turn. Prior APK backup remains private in ignored `android/build`.

## Next session starts with

- Review the user's visual feedback on the installed strip. If the layout needs polish, adjust only presentation. Do not call one supported anchor a full phrase match or alter raw recognition.

## Open questions

- Whether the center typography and teal pop are clear on the device. The existing combined instrumentation suite's order-dependent Activity timeout remains unresolved separately.

---

# Memory — Compact recognition and prediction UI

Last updated: 2026-10-04 +08:00

## What was built

- Refined only the Recognition screen: borderless translucent card and unified prediction strip, content-fitting multiword raw result, emphasized leading suggestion, and scroll reset when evidence reorders suggestions. Updated `context/progress-tracker.md`.

## Decisions made

- User chose to rank context as a labeled prediction while keeping `RECOGNIZED` and Hear/TTS raw. Existing Top-5 prefix support may reorder predictions; a separate `Context-supported` interpretation still requires the unchanged full matcher.

## Problems solved

- A phone screenshot exposed the first suggestion partly offscreen after strip reordering. The strip now returns to its leading item. The same screenshot showed two raw words (`HOME WORLD`) fitting inside the card and predictions remaining visible.

## Current state

- JVM 149/149 pass; debug and release builds pass. The final private Gemini debug APK is installed on the representative phone with matching host/device SHA-256. The prior APK is privately backed up in ignored `android/build`. The combined Android instrumentation class has the previously documented order-dependent launch timeout; this screen polish did not change that suite.

## Next session starts with

- Ask the user to review the installed UI in normal use. If the keyboard-style suggestion ranking needs further tuning, use the existing visual evidence and keep raw output untouched. Do not repeat Stage 3 physical accuracy collection for this UI change.

## Open questions

- Whether the final transparency and typography meet the user's visual preference. Cross-signer phrase accuracy and contextual benefit remain unmeasured.

---

# Memory — Context Assist phone verification and prediction visibility fix

Last updated: 2026-10-04 +08:00

## What was built

- The feature branch now keeps all cached conversation predictions visible during signing. Existing Top-5 prefix support only promotes a candidate's display order; the full matcher alone can show `Context-supported`. An Android regression test covers two unsupported signs without hiding predictions.

## Decisions made

- Leave raw `SentenceBuilder`, Hear/TTS, recognizer, and matcher behavior unchanged. Do not hide a prediction merely because the current visual prefix has no support; keep it labeled as a prediction.

## Problems solved

- USB install succeeded after wireless/phone approval failures. A phone screen showed raw `HELLO GOOD` in the widened `RECOGNIZED` card while the possible-replies strip remained visible. The user confirmed the strip no longer disappeared after two signs.

## Current state

- JVM 149/149 pass; debug, Android-test, and release builds pass. The Text-to-ASL fake-cache test, two-sign unsupported-evidence test, and Recognition exit test pass individually on the representative phone. The full 15-test instrumentation class still has an order-dependent Activity launch timeout after its heavy avatar/WebView test; three later UI tests timed out in the latest combined run. The private Gemini build was reinstalled after testing, with matching host/device APK hash and no test package left behind.

## Next session starts with

- Review the focused correction commit and decide whether to isolate the heavy Text-to-ASL instrumentation test into a separate process/run. Continue product evaluation only from real signed evidence; do not tune the recognizer or matcher from this UI check.

## Open questions

- What is the smallest test-runner isolation for the combined Android suite's Activity launch timeout? Cross-signer phrase accuracy and contextual benefit remain unmeasured.

---

# Memory — Context Assist recognition UI correction

Last updated: 2026-10-04 +08:00

## What was built

- Commit `ae9f038` on `codex/conversation-assist-text-to-asl-migration` widens the raw sentence card, narrows visible predicted replies using committed Top-5 phrase prefixes, and closes stale reply windows on Sign Detection exit or app background.

## Decisions made

- Keep raw `SentenceBuilder` text and Hear speech authoritative. The prefix-filtered replies remain predictions; only the existing full matcher may display a separate context-supported phrase.

## Problems solved

- Source inspection found that the raw sentence accumulates in `PhoneProductionSession`; the former two-line, narrow card could clip the phrase. In-memory prediction turns no longer survive Back/Home into a later session.

## Current state

- 149 JVM tests pass; debug, Android-test, and release build gates pass. The corrected phone UI and connected test suite remain unverified because Android returned `INSTALL_FAILED_USER_RESTRICTED` after wireless ADB transfer. AppHear is currently absent from the connected phone after Gradle's canceled test install. A private debug APK and the backed-up pretest APK remain in this isolated worktree's `android/build`/`android/app/build` outputs. No credential value is recorded here.

## Next session starts with

- Obtain phone-side approval of the AppHear installation (or a stable USB install path), install the corrected private debug APK, verify the multiword raw card and stale-reply behavior, then run the focused connected test suite if transport permits. Do not repeat physical accuracy collection.

## Open questions

- Does the expanded card display a multiword sentence correctly on the representative phone? Does the corrected Android instrumentation pass once package installation is permitted?

---

# Memory — S2-R2 itel capture aborted from debug OOM; replacement decision pending

Last updated: 2026-09-23 +08:00

## What was built

- Exported the exact frozen epoch-7 candidate as a separate Android debug FP32 TFLite/model-
  normalization package. The unchanged Phase-7 control remains the default rollback.
- Added explicit debug package selection, 669-observation Android parity instrumentation, a
  frozen six-attempt cohort, fail-closed capture audit, blinded review, and paired Phase-7/R2
  replay. Full commands are in `PHONE_VALIDATION_HANDOFF.md` under the S2-R2 deployment artifact.

## Decisions made

- No second training run or tuning. Distinct-signer validation follows passed connected-device parity.
  The old 669-observation phone fixture is deployment parity evidence, not independent validation.
- Human temporal labels and confirmed non-sign intervals must precede paired-result interpretation.

## Problems solved

- Frozen source hashes verified. Host Keras/TFLite max probability difference is `8.64e-7` with
  zero argmax mismatches across 669 exact phone observations.
- Review linkage now tolerates millisecond serialization rounding while requiring a unique match
  to each exact phone tensor row. Focused tests and lint pass.
- Connected M2101K7AG Android 12 parity instrumentation passed `4/4` tests with zero failures,
  including the S2-R2 669-observation candidate fixture and Phase-7 control availability.
  Corrected the PowerShell handoff command: quote all Gradle `-P...` arguments.
- Installed the parity-tested debug APK on the phone. The available performer confirmed being
  the prior design phone signer; no distinct signer was available at that time, so capture was
  not launched then.
- Later, an itel A665L Android 13 and declared distinct signer `phone_validation_signer_01`
  became available. Connected candidate/control parity passed 4/4 on the itel. The fixed cohort
  `session_20260923T011723Z` aborted during attempt 2 from a debug visual-frame Java-heap OOM;
  238/238 observation originals were preserved. The run is unscored.
- Built a debug-manifest-only `largeHeap=true` mitigation (256 MiB advertised vs 128 MiB default)
  and reran unchanged connected parity 4/4. Full-session capture stability is unproven. See
  `ITEL_RUNTIME_ABORT_20260923.md` in the deployment artifact.

## Current state

- `S2_R2_ITEL_DEBUG_CAPTURE_OOM_MITIGATED_WAIT_FOR_REPLACEMENT_DECISION`.
- The first distinct-signer session is an incomplete runtime incident, not validation. Android
  parity passes; human review and independent promotion remain pending. Protected TEST is unopened.

## Next session starts with

Obtain Project Supervisor decision on one documented procedural replacement with the same
distinct signer after runtime abort. Before any full rerun, confirm the new debug visual heap
mitigation survives a bounded on-device stress check. Then capture the fixed six attempts,
pull, audit, blind-review, and replay; preserve the aborted session and do not retrain or tune.

## Open questions

- Does the 256 MiB debug heap keep all synchronized originals through a full itel capture?
- If a procedural replacement is authorized, does R2 improve acquisition without ordinary-motion
  or completion regression on this signer?

---

Historical handoff below (superseded where it conflicts with the update above).

# Memory — S2-R2 host candidate frozen pending independent validation

Last updated: 2026-09-22 +08:00

## What was built

- Supervisor completed the single authorized S2-R2 training run. Saved epoch-7 Keras model and
  paired FIT-only normalization were hash-verified, with all six frozen development gates passing.
- Added a read-only source/cadence post-run decomposition and froze a host-candidate identity
  manifest and result report.

## Decisions made

- Stop model exploration. Treat S2-R2 as a frozen **host candidate**, not a production model.
  Do not retrain another seed or tune gates on opened development evidence.
- Next gate is versioned TFLite/Android export parity followed by one untouched distinct-signer
  continuous phone validation. Keep the old Phase-7 package for rollback.

## Problems solved

- Development phone ACTIVE recall improved `13/25 -> 24/25`; reviewed P1 negative events fell
  `4/8 -> 0/8`. CAL emission stayed `50/54`, while severe cuts rose `9/54 -> 10/54` within gate.
- Source audit exposed one APPHEAR_CAPTURE VIEW_A severe-cut regression and unchanged VIEW_C
  weakness; these are explicit validation risks, not reasons to restart the one-run experiment.

## Current state

- Stop state: `S2_R2_HOST_CANDIDATE_FROZEN_PENDING_EXPORT_AND_INDEPENDENT_VALIDATION`.
- Model SHA-256: `b6f8b52cece72f0b6f5b802a4ea583060d923e90a6b951059e7013114c8fc151`.
- Normalization SHA-256: `65d885f62eaca6f11a596302d304f63149795ddaf01e702f1e6a36dd7da5c005`.
- E6 signer, future positive phone signer/session, and protected TEST remain unopened. Android
  still uses the old Phase-7 package; no S2-R2 phone claim exists yet.

## Next session starts with

Build a versioned debug-only S2-R2 TFLite/normalization package from the frozen pair; verify
Keras/TFLite/Android parity and explicit rollback without changing feature/lifecycle/recognition
semantics. Only after parity, run one fixed distinct-signer phone validation with full visuals.

## Open questions

- Will the distinct phone signer reproduce the development ACTIVE-acquisition and non-sign gains?
- Will the small APPHEAR_CAPTURE regression or slow-cadence VIEW_C weakness matter on phone?

---

Historical handoff below (superseded where it conflicts with the update above).

# Memory — S2-R2 prepared; one training run awaits supervisor

Last updated: 2026-09-22 +08:00

## What was built

- Supervisor completed the corrected main extraction. An independent read-only audit accepted
  its saved manifest and all 366 hashed feature rows.
- Added a compact preparation-acceptance artifact and advanced the progress tracker.

## Decisions made

- The corrected 16-enrichment-clip dataset is ready for the single authorized S2-R2 run. Keep
  its config, source-family weights, checkpoint gates, split roles, and frozen downstream stack
  unchanged. Do not use this opened development evidence as independent validation.

## Problems solved

- The earlier DRINK 2 sparse-supervision failure is avoided by an explicit one-clip correction.
  Manifest counts are 366 total, 302 FIT, 64 internal development; all rows are unique,
  hash-valid, finite, chronological, and 378-wide. Excluded DRINK 2 and reserved E6 are absent.

## Current state

- Stop state: `S2_R2_MAIN_DATA_PREPARED_WAIT_FOR_ONE_TRAINING_RUN`.
- The main training run has not started; no main model weights or FIT normalization exist yet.
- Manifest SHA-256: `8c831dfd404cca935ae7356f4da10ec8dc0c1d6d08700b57bbc27a1ac00acf71`.

## Next session starts with

Supervisor runs exactly once from repository root:

`.\.venv\Scripts\python.exe eval\runtime_diagnostics\s2_r2_continuous_domain_correction.py train-main`

Inspect `main_candidate/training_result.json` afterward. Do not rerun the 30-epoch candidate to
search for a favorable result.

## Open questions

- Does the one candidate pass all frozen acquisition, non-sign suppression, and completion gates?
- If supported, does untouched independent negative/positive phone validation confirm it?

---

Historical handoff below (superseded where it conflicts with the update above).

# Memory — S2-R2 corrected preparation awaits supervisor

Last updated: 2026-09-22 +08:00

## What was built

- Added a versioned sparse-label-viability correction to the S2-R2 main preparation. The
  original 17-clip freeze remains historical; the effective candidate has 16 enrichment clips.
- Added a pre-extraction check of all enrichment cadence views and a clear train-before-prepare
  error. Documented the exact exclusion and corrected 366-row population.

## Decisions made

- Do not relabel the 239 ms DRINK 2 sign as non-sign or weaken the frozen 100 ms transition-ignore
  band. Its three sparse views have zero defensible ACTIVE-labeled observations, so exclude it
  from the one candidate only. No training or checkpoint gates changed.
- Run only `prepare-main` next. Do not invoke `train-main` until the prepared dataset manifest is
  complete and preparation reports `S2_R2_MAIN_DATA_PREPARED`.

## Problems solved

- Diagnosed the failed supervisor preparation precisely. The later `train-main` FileNotFoundError
  was downstream of the absent manifest, not an independent training failure.
- Checked all 17 enrichment clips using source-video timestamps without Candidate01 reprocessing:
  only this one clip lacked ACTIVE supervision. Focused tests pass 20/20; Ruff and compilation pass.

## Current state

- Stop state: `S2_R2_CORRECTED_PREPARATION_WAIT_FOR_SUPERVISOR`.
- No `main_candidate/dataset_manifest.json`, candidate normalization, or main model weights exist.
  The single main training run has not been consumed.

## Next session starts with

Ask the Project Supervisor to run only:

`.\.venv\Scripts\python.exe eval\runtime_diagnostics\s2_r2_continuous_domain_correction.py prepare-main`

Inspect its final status and row counts before providing the separate `train-main` command.

## Open questions

- Will the corrected 16-clip extraction complete with 366 rows (302 FIT, 64 internal development)?
- Only after that, will the one main candidate pass the frozen acquisition/suppression/completion
  gates?

---

Historical handoff below (superseded where it conflicts with the update above).

# Memory — S2-R2 one candidate ready for supervisor long run

Last updated: 2026-09-22 +08:00

## What was built

- Completed and finalized the exact-tensor phone temporal review for
  `session_20260921T153138Z`: 232 linked observations, 220 scored, and 12 ignored transitions.
- Froze the one-candidate S2-R2 dataset/config/checkpoint gates and added full extraction plus
  training commands to `eval/runtime_diagnostics/s2_r2_continuous_domain_correction.py`.
- Passed the all-domain preparation/training smoke, added focused tests, and registered the reusable
  trainer against the unchanged 378-feature contract.

## Decisions made

- Use exact Android 378 rows for the phone component; do not use JPEG-reprocessed rested-phone rows.
- Attempts 2/3/4/6 are FIT and 1/5 are internal development. All belong to the current design
  signer and support no independent-validation claim.
- The one candidate is the unchanged Phase-7 causal TCN, one seed/run, 30 epochs, FIT-only
  normalization, fixed source-family balancing, and predeclared acquisition/suppression/completion
  gates. E6, future distinct phone validation, historical DEV selection, and protected TEST remain
  untouched.

## Problems solved

- Exact labels are complete: 67 PRE, 67 ACTIVE, 86 POST, 12 ignored.
- Learnability is supported on bounded fit-only evidence; the full smoke pipeline completed with
  finite decreasing loss and correctly declined to promote the immature two-epoch model.
- Focused tests pass 18/18; Ruff and Python compile pass; JSON artifacts parse; no feature-contract
  semantic/order change exists.

## Current state

- Stop state: `S2_R2_ONE_CANDIDATE_READY_FOR_SUPERVISOR_LONG_RUN`.
- Full source re-extraction and the single 30-epoch candidate have not run. Candidate weights and
  candidate FIT-normalization hashes therefore do not yet exist.

## Next session starts with

From repository root, run exactly:

`.\.venv\Scripts\python.exe eval\runtime_diagnostics\s2_r2_continuous_domain_correction.py prepare-main`

then, only after successful preparation:

`.\.venv\Scripts\python.exe eval\runtime_diagnostics\s2_r2_continuous_domain_correction.py train-main`

Do not rerun for a favorable outcome. Inspect `main_candidate/training_result.json`; if supported,
package/export it and validate on the reserved distinct phone signer/session.

## Open questions

- Does the single candidate meet every predeclared acquisition, P1 suppression, CAL emission,
  exactly-one, and severe-cut gate?
- If supported, does untouched E6 and the distinct phone signer/session confirm the improvement?

---

Historical handoff below (superseded where it conflicts with the update above).

# Memory — Exact phone S2 parity passed; R2 data stop

Last updated: 2026-09-21 23:55:15 +08:00 (Asia/Manila)

# Memory — S2-R2 governance, learnability, and exact phone supervision

Last updated: 2026-09-22 +08:00

## What was built

- Froze conservative S2-R2 roles and dataset design under
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/s2_r2_continuous_domain_correction_01/`.
- Added `model/config/recognition_upgrade/s2_r2_continuous_domain_correction_01.json` and
  `eval/runtime_diagnostics/s2_r2_continuous_domain_correction.py` for the bounded learnability
  check and later one-candidate preparation.
- Added an isolated blinded temporal-review profile for exact-parity phone session
  `session_20260921T153138Z`. All 232 attempt visuals link to the actual persisted Android 378
  records. The UI is served at `http://127.0.0.1:8769/` when its local server is running.

## Decisions made

- P01/P02 and the current phone design signer are FIT/development-only with no independence claim.
  P03-P06/N0 remain unused. E6 `0F747C-S001` stays untouched validation, and a distinct future
  phone signer/session stays reserved for untouched positive validation.
- The bounded sanity result is `LEARNABILITY_SUPPORTED`; it is training-fit evidence only, not a
  generalization or promotion claim.
- Do not use JPEG-reprocessed rested-phone features as exact runtime hard misses. Frozen S2 ACTIVE
  recall changed from `12/62` on live exact observations to `42/62` after JPEG reprocessing.
- Do not begin the one main S2-R2 run until the exact-parity phone attempts receive defensible human
  PRE/ACTIVE/POST boundaries and the linked exact tensors are finalized.

## Problems solved

- The unchanged 378 representation and causal TCN can learn the bounded positive/negative
  distinctions: phone ACTIVE recall `61/62`, P1 ACTIVE false rate `0/369`, baseline ACTIVE recall
  `1.0`, baseline POST recall `0.996`, loss `0.3171 -> 0.0069` on the training-fit sanity cohort.
- The exact review profile reuses the tested blinded UI and writes immutable labels plus exact
  record indices and a compact NPZ; focused tests pass `7/7` and Ruff passes.

## Current state

- Stop state: `LEARNABILITY_SUPPORTED_WAIT_FOR_EXACT_PHONE_TENSOR_TEMPORAL_REVIEW`.
- The six-attempt review is prepared but not yet completed/finalized. No full S2-R2 training has
  started. Protected TEST remains unopened; re-arm, Admission, CONFIG01, materializer, Recognition
  V2, and the recognizer remain frozen.

## Next session starts with

After the Project Supervisor commits all six reviews, run:

`.\.venv\Scripts\python.exe eval\runtime_diagnostics\s2_r2_exact_phone_temporal_review.py finalize`

Verify exact linkage and label counts, replace the approximate JPEG phone rows in the main S2-R2
dataset with these exact Android 378 rows, then prepare/smoke-test the single governed candidate.

## Open questions

- Which of the six exact-parity attempts have sufficiently clear PRE, ACTIVE, and POST context for
  supervised use?
- After exact labels are frozen, does the one S2-R2 candidate improve phone acquisition and P1
  suppression while preserving governed CAL completion behavior?

---

Historical handoff below (superseded where it conflicts with the update above).

## What was built

- Pulled and evaluated exact-parity phone session `session_20260921T153138Z`. Added final parity/readiness artifacts under `phone_s2_exact_parity_and_r2_decision_01` and improved the evaluator's literal-placeholder error.

## Decisions made

- Exact root decision: `PARITY_PASS_S2_DOMAIN_CORRECTION_SUPPORTED`. Android and host 378/normalization are identical; S2 Keras/TFLite probability difference is at most `1.9073486328125e-6`, with zero state mismatches.
- Runtime repair is not warranted. S2/domain correction is the responsible direction, but training is stopped at `WAIT_FOR_PROJECT_LEAD_S2_R2_DATA_GOVERNANCE_AND_LABELING_DECISION` because current phone supervision is not signer-safe or temporally governed.

## Problems solved

- The user error came from passing `<CAPTURED_SESSION>` literally, not from sign performance. The actual session was found on-device, pulled, integrity-audited, and compared. Evaluator/docs now produce an actionable placeholder message.
- New visual drain passed physically: 669 observations and 669 verified originals.

## Current state

- Capture has six fixed attempts. HOME 004 and TABLE 005 emitted and classified correctly; both HELLOs and TABLE 006 had zero argmax ACTIVE; HOME 003 had one ACTIVE but no event. Two unmarked events need human semantic review.
- No S2-R2 training ran. Current exact phone signer status is `UNKNOWN`; there are no governed observation-level PRE/ACTIVE/POST phone labels or human-labeled continuous negative intervals. This session is design evidence, not independent validation.

## Next session starts with

Project Lead data-governance decision: resolve current signer identity/split role and obtain governed temporal positive labels plus bounded negative labels. Identify at least one additional independent phone/LOCAL training-development signer and reserve another untouched phone validation signer/session before one S2-R2 run.

## Open questions

- Are the two unmarked events confirmed non-sign, sign-like, or uncertain?
- Which additional phone/LOCAL signer can enter training-development without contaminating validation roles?
- Who will provide observation-level PRE/ACTIVE/POST boundaries for selected phone positives and continuous negatives?

---

# Memory — Exact phone S2 parity capture ready

Last updated: 2026-09-21 (Asia/Manila)

## What was built

- Added explicit debug-only `apphear.phone_s2_exact_parity_capture.v1` instrumentation behind `s2_exact_parity_capture=true`. It records the same raw observation, existing 378 feature row, exact normalized row consumed by S2, probabilities/state/history, and attempt linkage; bounded at 3,600 observations with final sizes/hashes.
- Added the fail-closed host evaluator `eval/runtime_diagnostics/phone_s2_exact_parity_and_r2_decision.py` with `audit-capture` and `parity` commands. Added the complete supervisor handoff under the new milestone artifact directory.
- Preserved the verified continuous-visual finalizer and registered the diagnostic contract in `context/feature-schema.md`.

## Decisions made

- Current state is `WAIT_FOR_PROJECT_SUPERVISOR_EXACT_PARITY_PHONE_CAPTURE`. There is no feature/normalization/S2 parity decision yet and no S2-R2 training is authorized.
- Frozen S2, 378 semantics, Candidate01, PRE_OR_POST re-arm, PASS_THROUGH admission, event completion, materializer, Recognition V2, and recognizer are unchanged. The instrumentation observes the existing path and does not create parallel inference.

## Problems solved

- Future fixed phone cohorts can now establish exact same-observation progressive parity instead of attempting invalid JPEG replay. Capture linkage, file sizes/hashes, chronological history, and full visual coverage fail closed.
- Host contract tests `2/2`, Ruff, focused JVM tests, debug APK build, and Android-test APK build pass. The no-output-change Android instrumentation test compiles.

## Current state

- No Android device was connected (`adb devices` empty), so connected instrumentation and the governed HELLO/HELLO/HOME/HOME/TABLE/TABLE capture were not run. The debug APK is packaged and the supervisor commands are ready.
- No protected TEST access, data curation, model training, new checkpoint, or S2-R2 result exists.

## Next session starts with

Run the exact supervisor sequence in `phone_s2_exact_parity_and_r2_decision_01/CAPTURE_AND_PARITY_HANDOFF.md`: connected instrumented parity tests, install/launch with exact capture enabled, fixed six attempts, explicit finalization, pull, `audit-capture`, then `parity`. Return the session name and full logs. Do not train in that same run.

## Open questions

- Does same-observation parity first diverge in raw→378, normalization, or S2 runtime output—or pass all stages?
- If parity passes, is signer-diverse positive/continuous-negative evidence sufficient for one S2-R2 run without one-signer overfit?
- Does physical-device finalization verify one visual original per observation in the new capture?

---

# Memory — S2-R2 parity gate and visual drain

Last updated: 2026-09-21 (Asia/Manila)

## What was built

- Added debug-only explicit continuous-visual finalization in the live phone capture, with a verified async writer drain and focused JVM test. Documented the component in `context/feature-schema.md` and the status in `context/progress-tracker.md`.
- Wrote `phone_s2_r2_continuous_domain_correction_01/PARITY_GATE_STATUS.md` under the recognition utility artifacts.

## Decisions made

- The required same-observation 378-d train/serve parity on `session_20260921T102840Z` is **unavailable**, not passed or failed: its persisted observations contain only compact summaries/S2 outputs, not raw-v1 landmarks or Android feature/normalized tensors. JPEG reprocessing cannot substitute. Do not start S2-R2 training or claim model-domain root cause.
- Keep all frozen runtime/model/recognition components and `PASS_THROUGH` admission unchanged. Historical rested session remains design/diagnostic evidence, not independent S2-R2 validation.

## Problems solved

- The visual summary no longer certifies a still-running stream at last-attempt completion. An explicit `FINALIZE & SAVE EVIDENCE` action stops new camera admission, waits for queued writes, verifies original count, and then certifies completion. Back at a completed cohort triggers the same finalization. Focused drain test, causal-core tests, and debug Kotlin compile passed.

## Current state

- Old session: 2,186 observations, 1,860 originals, stale summary at 1,083; last 326 originals cannot be recovered from current artifacts. Exact loss mechanism remains unproven.
- New drain is code/test validated but **not yet verified on a physical device**. A force-kill before explicit finalization still cannot be guaranteed; wait for `VISUAL EVIDENCE SAVED`.
- No S2-R2 candidate, data curation, model training, offline comparison, or fresh phone validation has occurred.

## Next session starts with

Prepare a bounded, explicitly opted-in phone parity capture that persists the *same* raw-v1 observations, Android 378 vectors, normalized inputs, and S2 probabilities for successful, missed, and visually confirmed non-sign intervals; run host reference comparisons before considering training. Device-check the final visual drain.

## Open questions

- Does exact same-observation phone/reference 378 + normalization + S2 parity pass? Until captured, implementation skew and model/domain causes remain unresolved.
- Is signer-diverse phone positive/continuous-negative data sufficient for one S2-R2 training run if parity passes?
- Does the new finalizer retain 100% of originals during an actual governed device session?

---

# Memory — Rested phone ACTIVE-acquisition evidence

Last updated: 2026-09-21 (Asia/Manila)

## What was built

- Closed and pulled the rested six-attempt session `session_20260921T102840Z` to `phone_pull_20260921/session_20260921T102840Z/`, then wrote a bounded analysis, decision JSON, and source hashes under the `phone_new_sign_admission_and_active_acquisition_validation_01` artifact directory.
- Updated `context/progress-tracker.md`. No runtime, model, policy, or feature implementation changed.

## Decisions made

- Evidence state: `PHONE_ACTIVE_ACQUISITION_LIMIT_SUPPORTED`.
- Stop at `WAIT_FOR_PROJECT_LEAD_PHONE_ACTIVE_ACQUISITION_AND_NON_SIGN_ARCHITECTURE_DECISION`.
- Keep `PRE_OR_POST_EXPERIMENTAL` recovery, `PASS_THROUGH` admission, frozen S2, materializer, Recognition V2, and recognizer unchanged pending the next scoped decision. Do not automatically run old terminal-only S2-R1 or invent an admission gate from this one signer.

## Problems solved

- The final phone session is now closed and its complete structured observation/event/attempt logs were pulled; the initial host pull was incomplete.
- The Project Supervisor confirmed all six marked signs were deliberately and correctly performed.
- All six began READY/IDLE. HELLO 001 and TABLE 005 completed and classified correctly; the other four had zero S2 argmax ACTIVE. Re-arm completed after both intended emitted events and after 23 of 24 overall events; the final event ended at shutdown.

## Current state

- 2,186 observations, 24 events, six fixed attempts; strict intended event emission and Top-1 are 2/6. Three of the four zero-ACTIVE misses had refined-hand and ROI-motion evidence during visible gestures, making re-arm/admission non-causes. Attempt 006 has weak refined-hand evidence, so its upstream attribution is less certain.
- PASS_THROUGH still emits outside marked attempts. Original frames support ordinary/non-sign activity for 14 events; one shoulder-touch episode remains uncertain. Events 18–24 cannot be visually classified.
- Only observations 0–1859 of 0–2185 have synchronized originals. The visual summary is stale at 1,083 frames and source lacks a verified final writer drain. Do not claim full-session visual coverage or a production false-event rate.

## Next session starts with

Project Lead review of the rested-session report. Choose one bounded architecture/evidence plan for both true-sign ACTIVE acquisition and continuous non-sign discrimination, with independent signer/phone validation. Verify representative train/serve parity and fix final visual-writer drain before relying on another full-session visual audit. No training, admission tuning, or recognition redesign is authorized by this diagnostic alone.

## Open questions

- How much of the four missed signs is S2 phone-domain generalization versus upstream perception/feature quality, especially TABLE 006?
- What signer-diverse phone positive and continuous-negative evidence can support one targeted correction without reusing opened diagnostic data as independent validation?
- What caused the final 326 original frames not to persist after the capture closed?

---

Historical handoff below (superseded where it conflicts with the update above).

# Memory — Repeated phone recognition cohort attribution

Last updated: 2026-09-20 23:33:30 +08:00

## What was built

- Completed and analyzed governed phone session `session_20260920T145710Z` for `PHONE_REPEATED_RECOGNITION_INTEGRATION_01`.
- Pulled the intact session to `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phone_repeated_recognition_integration_01/device_capture/session_20260920T145710Z`.
- Completed synchronized visual audit of all 2,747 observations/frames, all 10 intended attempts, and all 22 emitted events.
- Wrote the final report and structured evidence package under `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phone_repeated_recognition_integration_01/`.
- Preserved the implemented lifecycle separation: `PRE_ONLY` control, `PRE_OR_POST_EXPERIMENTAL` re-arm, and a `PASS_THROUGH` new-sign admission boundary.

## Decisions made

- Final evidence state: `PHONE_REARM_SUPPORTED_REPEATED_RECOGNITION_NOT_YET_SUPPORTED`.
- Exact stop boundary: `WAIT_FOR_PROJECT_LEAD_PHONE_ADMISSION_AND_S2_ACTIVE_ACQUISITION_DECISION`.
- Retain the `PRE_OR_POST` re-arm direction: all 22 emitted events re-armed and all 10 intended attempts began READY/IDLE.
- Do not freeze the complete temporal stack yet.
- The pass-through admission behavior is unsafe: 16 of 22 emitted events were visually confirmed as non-sign activity or the wrong early episode; 5 were defensible sign-like events and 1 was uncertain.
- Admission filtering alone cannot recover the missed intended signs. Five intended signs had zero ACTIVE argmax observations and two had only one isolated ACTIVE observation.
- Do not automatically run the existing terminal-only S2-R1 plan. The newly demonstrated S2 weakness is ACTIVE acquisition, distinct from the earlier terminal-generalization diagnosis.
- Keep the cadence-safe materializer frozen. The STREET attempt 008 failure came from the wrong logical episode, not materializer behavior.
- Preserve recognition as a separate responsibility: STREET attempt 007 had a usable temporal window but was classified as CLOTHES, with STREET rank 3.

## Problems solved

- The PRE-only post-event deadlock was removed by the experimental PRE-or-POST recovery semantics without changing event completion, materialization, Recognition V2, or the recognizer.
- Full-session evidence coverage was fixed: synchronized visual evidence exists for all 2,747 observations, so unexpected events can now be attributed rather than guessed about.
- The phone cohort separated re-arm success from two remaining blockers: false/wrong episode admission while READY and inadequate S2 ACTIVE acquisition for several genuine signs.
- Source-hash and JSON validation completed successfully for the final evidence package.

## Current state

- Session totals: 2,747 observations, 22 emitted events, 10 attempts begun/completed, 22 re-arm completions, and 0 gap resets.
- Re-arm latency: minimum 399.9 ms, median 466.9 ms, p90 2,132.9 ms, maximum 3,266.0 ms.
- Intended-attempt event emission: 3/10; exactly-one-event: 3/10.
- Strict recognition: Top-1 1/10; expected-gloss Top-5 2/10.
- Attempt 006 HOME emitted a usable window and predicted HOME with probability 0.870555.
- Attempt 007 STREET emitted a usable window but predicted CLOTHES; this is recognizer generalization evidence.
- Attempt 008 STREET emitted an early/wrong logical episode whose window omitted substantial visible sign content.
- Attempts 001 HELLO, 002 HELLO, 003 AT, 004 AT, and 009 TABLE had zero ACTIVE argmax observations during the visible sign.
- Attempts 005 HOME and 010 TABLE had one isolated ACTIVE argmax observation, insufficient for frozen CONFIG_01 to emit.
- Candidate01 is not established as the sole cause: refined-hand observations were sparse, but proposals were generally present and successful attempts also had low refined-hand fractions.
- No model, threshold, decoder-completion, materializer, or recognizer changes were made after observing this cohort. No training or protected TEST access occurred.
- Canonical report: `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phone_repeated_recognition_integration_01/PHONE_REPEATED_RECOGNITION_INTEGRATION_REPORT.md`.
- `context/progress-tracker.md` already records this accepted state and stop boundary.

## Next session starts with

Project Lead review must choose the next bounded milestone. The evidence supports two separately scoped tasks:

1. Design one bounded new-sign admission experiment using the newly human-labeled non-sign/wrong-episode events, while avoiding reuse of this same session as independent validation.
2. Define one targeted S2 ACTIVE-acquisition correction plan for genuine signs that never produced a credible ACTIVE episode. Do not substitute the existing terminal-only S2-R1 plan without revising its measured target.

Do not implement either branch until the Project Lead freezes its population roles, policy/training scope, and independent validation plan.

## Open questions

- Can one simple class-agnostic admission rule reject the confirmed non-sign/wrong-episode onsets without rejecting valid signs with sparse refined-hand support?
- Which governed data and objective should support an S2 ACTIVE-acquisition correction while preserving terminal behavior and avoiding DEV/phone overfitting?
- Should continuous negative activity and positive phone-onset diversity be handled in one bounded S2 correction or kept as separate evidence paths?
- Which genuinely independent phone population will validate any admission or S2 correction?
- After the temporal path is reliable, how should the 236-class recognizer's signer/domain generalization be addressed using good phone windows?

---

# Memory — S2-R2 independent phone validation

Last updated: 2026-09-23 (supersedes the older phone-session handoff above)

## What was built

- The frozen epoch-7 S2-R2 model and its FIT-only normalization were exported as an opt-in versioned Android debug package. Phase-7 remains the default rollback package. Connected-device parity passed 4/4 on the itel A665L; same-observation replacement-capture parity passed on all 513 rows.
- A diagnostics-only `largeHeap` mitigation addressed the first itel visual-frame OOM; that aborted session remains unscored. The Supervisor authorized one procedural replacement `session_20260923T013439Z` with distinct `phone_validation_signer_01`.
- Finalized six-attempt blinded human temporal review, bounded full-session non-sign review, and paired Phase-7/S2-R2 replay. The canonical report is `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/s2_r2_phone_deployment_and_independent_validation_01/INDEPENDENT_PHONE_VALIDATION_RESULT.md`; machine-readable result is alongside it under `session_20260923T013439Z/paired_temporal_result.json`.

## Decisions made

- Current stop state: `S2_R2_INDEPENDENT_PHONE_MIXED`. S2-R2 improved same-observation ACTIVE acquisition (4/29 to 18/29; 1/6 to 4/6 attempts), but only two of six intended signs received >=90%-contained windows. Do not promote to production or tune from this validation signer.
- Retain the S2-R2 candidate and Phase-7 rollback unchanged. No training, Admission/re-arm/CONFIG01/materializer/recognizer change, or protected TEST access occurred.

## Problems solved

- The replacement capture has 513/513 synchronized originals and six fixed attempts. Android vs host 378 and normalized inputs match exactly; S2 probability max difference is `1.013278961e-6`; zero state mismatches. Re-arm completed after all seven candidate events.

## Current state

- Blinded human labels: 29 ACTIVE, 45 PRE, 43 POST, 12 ignored transition observations. Four confirmed non-sign intervals contain 109 observations; neither branch emitted an event within them. Two S2-R2 events outside attempts (indices 195–198 and 472–474) remain semantically uncertain pending specific visual adjudication; the reviewer was asked to classify both.
- Later itel attempts slowed from about 335 ms median observation spacing for HELLO to about 536 ms for HOME/TABLE, with 68 within-attempt gaps above the frozen 533.232 ms continuity limit. The source of slowdown is not established. This is a serious cadence confound for late misses, not proof of S2-only failure.

## Next session starts with

Record the Supervisor's visual classification of the two extra events if provided. Then seek Project Lead decision on one bounded itel throughput/cadence investigation before another fresh phone validation. Do not use this now-open signer for post-change independent promotion.

## Open questions

- Were the two extra events ordinary non-sign movement, sign preparation, genuine signs, or uncertain?
- Why did itel effective observation spacing rise to ~536 ms, above the frozen continuity limit, during HOME/TABLE?
- After cadence is stabilized, does frozen S2-R2 still miss genuine signs or form wrong episodes on fresh independent phone evidence?

---

# Memory — S2-R2 representative-phone final validation

Last updated: 2026-09-23 (supersedes the earlier itel handoff above)

## What was built

- No model or runtime algorithm changed. Froze the representative-phone cohort, verified the frozen S2-R2 package and Xiaomi connected parity, captured `session_20260923T030939Z`, finalized blinded temporal and non-sign review, and ran Phase-7/S2-R2 paired replay on the same 714 observations.
- Canonical report: `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/s2_r2_representative_phone_final_validation_01/REPRESENTATIVE_PHONE_FINAL_VALIDATION_RESULT.md`. The pre-HELLO extra event has separate `UNCERTAIN` adjudication in the same folder.

## Decisions made

- Final stop state: `S2_R2_INTEGRATION_READY_WITH_KNOWN_LIMITATIONS`. Proceed next to `APPHEAR_S2_R2_REAL_APP_INTEGRATION_01`, not another S2 experiment. Preserve Phase-7 rollback and current lifecycle/materializer/recognizer contracts.
- Do not treat the one event before HELLO 1 as a confirmed false positive or genuine sign: the reviewer response was `Uncertain / mixed`. Do not tune from this or the now-open validation signer.

## Problems solved

- The representative Xiaomi did not reproduce the itel cadence collapse: all six attempts had median spacing 200–266.6 ms with zero over-limit continuity gaps.
- S2-R2 acquired all six human signs, emitted exactly one intended event for each, delivered 6/6 100%-contained ACTIVE windows, and re-armed after every event. Phase-7 same-observation control missed one intended event and produced only 1/6 >=90%-contained windows.
- Five visually confirmed non-sign intervals (227 observations) had no ACTIVE states or event onsets in either branch. Capture retained 714/714 synchronized originals; feature/normalization parity was exact and S2 max probability difference was below `8.4e-7`.

## Current state

- All six intended S2-R2 windows were usable; the frozen recognizer's Top-1 was correct on 3/6. The remaining three are good-window word-identification errors, not temporal failures.
- One S2-R2 extra pre-attempt event remains semantically uncertain. This limits any claim of zero unwanted events. One signer, one device, and three glosses are bounded integration-readiness evidence, not full production validation.
- No S2 retraining/tuning, Admission, re-arm, CONFIG01, materializer, recognizer, or protected TEST change/access occurred.

## Next session starts with

Inspect the real AppHear application shell and integrate the exact frozen S2-R2 model-normalization pair as the default behind an internal Phase-7 rollback, using the established phone causal path and disabling heavy validation capture by default. Verify repeat-use and diagnostic parity without changing scientific behavior.

## Open questions

- What does the pre-HELLO uncertain event represent under richer real-app use, and does ordinary behavior produce committed words at an unacceptable frequency?
- How well does the frozen 236-class recognizer generalize on usable real-app windows beyond these three glosses and one signer?

---

# Memory — AppHear S2-R2 real-app integration software gate

Last updated: 2026-09-23 (supersedes the prior integration-to-do handoff)

## What was built

- Promoted the previously validated Candidate01, 378-feature, versioned S2, lifecycle,
  materializer, Recognition V2, recognizer code/assets/native library into the normal app source
  set. `RecognitionActivity` now runs one front-camera causal backend and passes existing
  product-level recognition state/sentence to the unchanged UI. Diagnostic capture stays debug-only.
- Added a shared raw-v1 → Recognition V2 adapter and focused regression test. Exact integration
  notes are in `context/recognition_upgrade/APPHEAR_S2_R2_REAL_APP_INTEGRATION_01.md`.

## Decisions made

- S2-R2 is the normal default and Phase-7 is an internal debug rollback. Model and normalization
  are versioned and checked together; there is no silent legacy fallback. Front/back and obsolete
  handedness actions are disabled in the causal screen. No ML thresholds or feature semantics changed.

## Problems solved

- Debug and release builds succeed; 95 JVM unit tests pass. The Xiaomi passed 4/4 selected
  378/S2 on-device parity tests and 3/3 Recognition V2/recognizer tests. The normal UI loaded
  `S2_R2_CANDIDATE` and reached READY, without opening the diagnostic Activity.

## Current state

- **Partial integration gate:** the Project Supervisor could not perform the planned real-app
  HELLO/HOME/TABLE/HELLO smoke at this time. No repeated-sign, UI-commit, recognition, or re-arm
  outcome has been claimed for the normal app. The remaining gate is human interaction, not a
  known parity/build failure.
- The connected Xiaomi is M2101K7AG. Android ADB tap injection is denied on this device, so
  the Supervisor must navigate/sign manually; do not assume shell-driven sign simulation.

## Next session starts with

On the Xiaomi, open the normal AppHear Sign Detection screen, wait for READY, then perform
HELLO → HOME → TABLE → HELLO once each with natural recovery. Inspect the displayed result,
sentence update, exactly-one commit, and return to READY after each. Read lightweight logcat
events only to attribute any failure; do not tune the frozen pipeline from this smoke.

## Open questions

- Does the normal UI commit exactly once and re-arm naturally across several physical signs?
- Do good real-app windows show the same recognizer signer/domain errors seen in validation?

---

# Memory — Real-app overlay and no-signer integration gate

Last updated: 2026-09-23 16:35 +08:00

## What was built

- Promoted the validated debug overlay renderer/transform into shared main Android code and
  connected it to the existing real-app overlay. Detailed files/tests are recorded in the
  integration report and `context/feature-schema.md`; no model or feature path changed.

## Decisions made

- The optional full exact-observation `PhoneProductionSession` → UI replay was not added: it
  would require migrating a large host-side raw fixture/parser into Android tests. Existing
  connected component/composed parity and the still-pending fixed human smoke are the gates.
- Do not tune S2/Admission/re-arm from the single unplanned open-hand event observed today.

## Problems solved

- Build, JVM, connected overlay/backend parity, visual hand alignment, normal startup/READY,
  bounded empty-scene soak, and navigation/background return now pass. The normal app did not
  show a stale word after return; the empty-scene soak committed no words.

## Current state

- Integration is still **partial**: the fixed HELLO → HOME → TABLE → HELLO real-app signer smoke
  has not happened. During a separate overlay check, a user-confirmed non-sign open-hand
  raise/hold emitted one HELLO and re-armed. This is a real product limitation, but neither a
  false-positive rate nor a reason to change scientific behavior in this milestone.
- The Xiaomi has the updated debug APK installed; instrumentation may leave the app off the
  recognition screen. The user must navigate manually because ADB tap injection is blocked.

## Next session starts with

When a signer is available, run the fixed four-sign sequence once in the normal AppHear Sign
Detection UI, logging one intended event/result/sentence commit and recovery per attempt.
Classify any no-event, wrong-window, wrong-gloss, or non-sign event separately; stop for Project
Lead review without model or lifecycle tuning.

## Open questions

- Does the real UI reliably commit once and re-arm across the fixed intended sign sequence?
- How often, under controlled visual evidence, does ordinary hand raising produce a word event?

---

# Memory — AppHear S2-R2 real-app integration final smoke

Last updated: 2026-09-23 22:07 +08:00

## What was built

- No code or model change in this session. The current debug APK was reinstalled on the
  connected Xiaomi, and the fixed normal-UI HELLO → HOME → TABLE → HELLO smoke was completed.
  Per-attempt timestamps, event IDs, windows and caveats are in the integration report.

## Decisions made

- Final state: `APPHEAR_S2_R2_REAL_APP_INTEGRATION_COMPLETE`. The integration software gate
  passed, but this is not a population accuracy or false-positive-rate claim.
- Do not automatically tune S2, Admission, re-arm, materializer, recognizer, or UI from this
  single smoke. Return to Project Lead for the next product decision.

## Problems solved

- Each of the four intended real signs produced exactly one committed backend event, one
  displayed/sentence result, and a natural return to READY. The screen's final four-word
  sentence matched the intended sequence. No crash, duplicate intended result, stale UI,
  second analyzer, or legacy backend appeared.

## Current state

- The Project Supervisor reported two distinct unwanted words during ordinary behavior:
  HOSPITAL1 while adjusting a seat before the first intended sign (cleared before the sequence),
  and STAND2 during movement after the sequence. Each appeared once and re-armed. The normal
  app did not record synchronized visual video, so detailed causation remains unresolved.
- The earlier stationary-open-hand HELLO remains a separate similar product observation.
  Do not treat these bounded incidents as a measured false-positive rate.

## Next session starts with

Present the complete real-app integration result to the Project Lead and choose one bounded
next milestone based on the observed unwanted ordinary-motion commits. Do not reopen S2
research or change Admission automatically.

## Open questions

- Which layer admits ordinary movement as a sign under governed continuous-phone evidence?
- Do broader real-app signers/words preserve the four-attempt repeated-use behavior while
  recognizer generalization remains imperfect?

---

# Memory — Continuous-transition diagnostic tooling handoff

Last updated: 2026-09-28 +08:00

## Current state and decisions

- Working real-app baseline stays `APPHEAR_S2_R2_REAL_APP_INTEGRATION_COMPLETE`, protected at
  `76d93cecd85bf9f76064d320aa4a5791b5f0704a`; its named baseline branch/tag were not moved.
- Diagnostic branch `dev/continuous-transition-diagnostics` starts at that exact commit.
  Implementation commit: `befa94a54b7f0e1ebc471af21a77f2f2036641b7`.
- Status `DIAGNOSTIC_TOOLING_READY_WAIT_FOR_AB_CAPTURE`. Debug-only whole-sequence A/B blocks
  avoid per-word READY waits; five bounded ordinary-motion blocks follow. The same frozen
  shared runtime produces source-linked raw/378/normalization/S2/lifecycle/window/Top-5 records.
- New host evaluator requires complete evidence and human physical boundaries, not START/STOP
  labels. It distinguishes recovery blocking, merged/no boundary, ACTIVE reacquisition,
  downstream delivery and uncertainty; cadence gaps remain a separate confound.
- Current Android starts eligible POST recovery on the commit observation itself. The old host
  replay adapter needed an explicit opt-in to match that timing; its historical default remains
  unchanged. This is an audit adaptation, not a production lifecycle fix.
- No main/release runtime, UI, feature/model/normalization, Admission, CONFIG01, materializer,
  recognizer, native library or asset changes. No training or protected TEST access.

## Verification and next session

- 96/96 JVM and 51 focused host tests pass; debug/release builds pass. The existing 669-row
  Keras/TFLite fixture max probability difference is 8.64267349e-7, with zero state mismatches.
  Both APKs preserve all 128 packaged main assets byte-for-byte. No phone is currently attached,
  so connected parity and actual A/B capture are **not** claimed.
- Start with the exact Supervisor install/run/pull/review/analyze instructions in
  `APPHEAR_CONTINUOUS_TRANSITION_AND_READINESS_01_REPORT.md`. Use one representative phone and
  the same signer for A (hands down) and B (hands up), each HELLO/HOME/TABLE/HELLO once.
- Wait for explicit final evidence save; preserve any runtime incident rather than silently
  replacing it. Review physical lexical onset/end from synchronized originals without looking
  at predictions, then run the evaluator and return evidence to Project Lead.
- Stop before any behavioral fix, shorter recovery, Admission tuning or model training.
  The hands-up responsiveness mechanism is still unproven.

## 2026-09-29 — Git baseline handoff

The user requested preservation, not another functionality change. The known-working Text-to-ASL alphabet pilot source was uncommitted on `dev/continuous-transition-diagnostics` at `f5a6cb4`. The separate context-aware assistant worktree/branch `feature/conversation-phrase-assist-mvp` at `24f0684` is clean and was not merged. The isolated preservation branch is `codex/current-working-text-to-asl-baseline-2026-09-29`; its scope and exact APK/asset hashes are in `context/current-working-baseline-2026-09-29.md`. Keep the assistant worktree separate and review overlapping Gradle/Text-to-ASL files before future integration. The tested APKs remain checksum-verified on I:; experimental source files are versioned while service configuration stays ignored. This is a stable Text-to-ASL pilot baseline, not promotion of recognition or release flags. Next development starts from its tag on a fresh branch/worktree after baseline push verification.
