# FINGERSPELL — Recognition, Continuous Detection and Word-Commit Improvement (practical v1)

Date: 2026-10-23

**Integration update (2026-10-23):** practical v1 is committed as `1affb6ea` on
`claude/fingerspell-practical-integration`, based on the application baseline `ae7afc98`.
See §13 for integration checks and APK identities. Earlier uncommitted/build status below is
historical; this integration has not been merged into the baseline or installed on the phone.

Original experiment history: worktree `claude/friendly-torvalds-9872e5`, fast-forwarded from
`1e215aeb` to `098f3682` (= `claude/s2-r3-eval-suite`, the WORD_BLEND_02 lineage the installed
phone build came from). **Nothing committed, pushed or merged.** With your approval the candidate
was installed on the phone with `adb install -r` for a partial device session (§11); the session is
paused and the phone still runs candidate `b74dcda5`. No model asset, package asset, training or
dataset admission. No TEST, E6 or Tier 3 data opened.

Everything new is behind a debug Gradle flag, `-PfingerspellPractical=true`
(`BuildConfig.FINGERSPELL_PRACTICAL_ENABLED`, requires `fingerspell` + `fingerspellContinuous`;
release = false). With the flag off the build is the locked baseline.

## Summary

| | Finding / change | Evidence class |
|---|---|---|
| 1 | Natural, fluent fingerspelling is beyond the frozen model (~40% sequence CER, 1/42 exact single words, prior V2.1 review). The held-letter design is the right one to make practical, not replace. | Offline, prior |
| 2 | **Lost letters:** a decode is thrown away if the hand is missing for even one frame *when the result returns*, although its window was fully usable. Seen on the phone (E: 3 matching decodes, window 12/12 usable, 1 missing frame → letter lost). Fixed: judge a result by its own window. **+25% letters on DEV (89→111, time-plausible 46→60), 0 new false letters on 86 min of ordinary movement at 200 ms worker latency;** at 400 ms latency +38% real letters but also +16% false letters. | Phone logs (exact replay) + offline |
| 3 | **False letters from ordinary hand movement are the dominant error:** 712 letters (8.3/min) appended on 86 min of non-sign gestures, in all 40 clips. No decision threshold fixes it (margin gate removes true and false letters at the same rate). This is a model limit (no "not a letter" output). Mitigated by making correction cheap, not hidden. | Offline (IPN Hand) |
| 4 | **No per-letter correction:** one wrong letter = expand panel + CLEAR + re-spell the whole word. Added **DELETE LAST LETTER** in the pull-up panel, in its own row above CLEAR (your choice: not in the RECOGNIZED card). | Code |
| 5 | **Double letters:** 0 of 139 natural doubles captured (they need a ≥0.8 s hand lowering), while 89 of the 712 false letters are accidental doubles from tracking loss. Added one-tap Repeat. | Offline + code |
| 6 | **Draft lost on any interruption** (screen off, app switch, camera rebind) and **previous word carried into the next commit** when FINGERSPELL is re-entered via Settings. Fixed. | Code (JVM/instrumented tests) |
| 7 | **Commit could be invalidated** by a letter arriving while the confirm dialog is open ("Spelling changed. Review it again."). Acceptance is now held during review. | Code |
| 8 | **Guidance never shown** in continuous mode. A hint line with a hold counter was added, then removed at your request; the card now shows only the spelling plus Repeat and Done. | Code |
| 9 | **Phone session (§11):** two bugs found and fixed: clipped Repeat/Done buttons, and an extra letter (MARY → MMARY) when a letter was added just as the hand left. Rotating the phone rebuilds the recognition screen and wipes the draft (existing behaviour, not fixed). | Phone |

---

## 1. Architecture and active model (as built in the locked debug baseline)

```
CameraX ImageAnalysis (KEEP_ONLY_LATEST, front 15 fps / rear 30 fps)
 → Candidate01FrameAnalyzer (DWPose-T + MediaPipe hand refiner)  [shared perception, unchanged]
 → ownsObservation(observation, image)                           [RecognitionActivity]
     coordination.observation(wordIdle, usableHand)   → may auto-switch WORD→FINGERSPELL
     if FingerspellRuntime.fingerspellOwnsFrames: FingerspellRuntime.consume → ContinuousFingerspell.consume
         (returns before reading pixels; WORD session.consume is NOT called for this frame)
     else: WORD path (PhoneProductionSession.consume → S2 decoder → materializer → WORD model → SentenceBuilder)
 ContinuousFingerspell (camera executor; 1 inference worker "apphear-held-letter")
   HeldLetterPolicy.observe(raw CommonObservation, deep copy)  window ≤4000 ms / ≤64 obs
   request(): ≥1000 ms span, ≥4 usable, ≥500 ms since last request, hand present now
   worker: fresh Adapter v1 [T,405] → geometry_sequence.tflite [T,28] → singleton CTC decoder
   accept(): epoch check → hand check → 3 matching decodes spanning ≥1000 ms → append to draft,
             latch the letter, clear the window. Same letter again only after ≥3 missing obs over ≥800 ms.
 Snapshot → RECOGNIZED card = confirmed + draft; CURRENT SIGN = latest valid decode
 Commit (coordination on, as locked): Hear → dialog "Confirm spelling and return to WORD"
   → confirm() → RecognitionCoordinator.complete(text) → select(WORD) → speak(text)
     → ConversationPhraseAssist.recordConfirmedSpelling. Letters never enter the WORD event pipeline.
```

* **Active model/package:** `packages/fingerspelling_continuous_v2_1_01` via `-PfingerspellArtifactDir`
  (debug asset srcDir). Candidate `SEQUENCE_V2_1_EPOCH034_GEOMETRY_ONLY`, `geometry_sequence.tflite`
  sha `e78de274…`, geometry only (405-wide, no visual branch), non-causal symmetric TCN, 292,956 params.
  Decoder `apphear.fingerspelling.single_letter_ctc.v1` (blank 27, penalty 0.5, empty/SPACE refusal).
  Policy asset `held_letter_policy.v1` (values above; "engineering defaults, not accuracy calibrated").
  B2 reference and later candidates are not on the runtime path.
* **Flags:** `-Pfingerspell=true` (models + runtime), `-PfingerspellContinuous=true` (automatic held
  letters; `false` restores manual Start/Done), `-PrecognitionCoordination=true` (context auto-entry
  and the confirm-and-return dialog). New: `-PfingerspellPractical=true`.
* **Exclusivity:** `RecognitionModeController` is the single owner (`WORD` | `FINGERSPELL`); a switch
  calls the WORD reset and bumps a generation; `ContinuousFingerspell.select` joins any in-flight
  inference under `inferenceLock` before WORD becomes owner. When FINGERSPELL owns a frame the
  analyzer skips `session.consume`, so WORD sees no frames and no letters.
* **Protected baseline record:** `docs/audit/baselines/fingerspell_practical_v1_baseline_2026-10-23.json`
  (package hashes, policy, decoder, base commit, and the file-level proof in §9).

## 2. Main causes of failure (ranked by user impact)

1. **False letters from ordinary hand movement (model limit).** Any steady hand in view becomes a
   letter after ~2 s: 8.3 false letters/min on IPN Hand (non-sign gestures and idle hands), every clip.
2. **Correction cost.** No way to remove one letter; the only correction is CLEAR (inside the collapsed
   panel) and re-spelling everything. Combined with (1), a single stray letter costs a whole word.
3. **Lost letters at the end of a hold** (one-frame dropout at callback). Verified on the phone.
4. **Double letters** need a hand lowering ≥0.8 s; natural doubles are never captured, and tracking
   loss creates accidental doubles.
5. **State loss / stale state:** draft erased by any `onStop`/camera rebind; previous committed word
   prefixed to the next commit when re-entering via Settings.
6. **Commit friction:** the confirm dialog can be invalidated by a letter arriving behind it.
7. **No guidance:** users cannot see how long to hold or why nothing is added.
8. **Speed:** ≈2.1–2.3 s of steady hold per letter (unchanged here — see §4 for why).

## 3. Evidence

### Verified
* **Phone decision logs** (`fingerspell_continuous_last_active.json`, pulled earlier;
  `android/app/src/test/resources/fingerspell_practical/device_decision_logs.json`):
  * `LOST_E_SESSION`: S,S · E,E,**E → `HAND_CURRENTLY_MISSING`** (`missing_observations=1`,
    window 12/12 usable) · Y,Y. Final draft "" — the held E was lost.
  * `EY_SESSION`: an S decode discarded the same way; E and Y appended after 1.14 s of matching decodes
    (≈2.1–2.3 s from window start).
  * Replayed through the Kotlin policy: baseline reproduces **every logged reason and preview**;
    practical keeps the E ("E") and leaves "EY" unchanged.
* **Offline end-to-end replay** (`tools/fingerspelling/practical_replay.py`): real Candidate01 raw →
  frozen phone cadence gate (6.23 obs/s) → exact Python port of `HeldLetterPolicy` with the single
  async worker (200 ms result latency, phone median) → Adapter v1 → frozen TFLite → singleton decoder.
  The port is tied to the Kotlin code by a parity test on 4,902 recorded policy calls
  (`pythonReplayPortMatchesKotlinPolicy`). Results: `docs/audit/probes/fingerspell_practical/replay_evidence.json`.
  * Positives: FSboard v13 official validation, **256 clips, 15 held-out signers** (DEV role; TEST sealed).
  * Negatives: IPN Hand, **40 clips, 10 subjects, 86.2 min**, non-sign gestures + idle.
* **Code reading + tests** for items 4–8 of the summary (draft loss in `pause()`/`select()`, stale
  `confirmed` across owner changes, missing status view in continuous mode, dialog invalidation path).

### Hypotheses (not verified; need the phone)
* Accidental doubles during *deliberate held-letter* signing from tracking loss (verified only on IPN).
* How often the confirm dialog was actually invalidated in practice.
* Whether the new hint text and controls reduce user time/taps for real users (needs a session).
* Front-camera cadence (5–12 obs/s observed) vs. the replay's 6.23 obs/s.

## 4. Selected improvements and why (and what was rejected)

Selected (all FINGERSPELL-only, flag-gated):

| Change | Why | Risk control |
|---|---|---|
| Evidence-based acceptance (`acceptWhileHandMissing`) | Verified lost letters; +22 DEV letters, 0 new IPN false letters at 200 ms latency (+16% at 400 ms, for +38% real letters) | A sustained absence still rearms (new epoch → stale result refused) |
| Latch kept through the absence a letter was added in | Phone: MARY → MMARY when M was added as the hand left and the user re-showed M | Only that absence; a later deliberate lowering still allows a double; DEV/IPN numbers unchanged |
| DELETE LAST LETTER (pull-up panel, above CLEAR) | One wrong letter no longer costs the word; main mitigation for model-limit false letters | New epoch drops in-flight results; latch kept; row GONE in WORD, CLEAR untouched |
| Repeat last letter | Natural doubles: 0/139 captured; lowering is slow and error-prone | Latched; holding the letter never adds a third |
| Draft survives pause/resume/camera rebind | Interruptions erased the whole draft | Only same-owner reselect; owner change still resets |
| Fresh word on every owner change | Stale previous word prefixed to the next commit | — |
| Hold letters while reviewing | Commit can't be invalidated behind the dialog | Resumed on dismiss; WORD frames still excluded |
| Done button in RECOGNIZED (guidance line removed on request) | Done = clearer commit entry than the top-right speaker | Done opens the *existing* review; nothing commits without the confirm tap |

Rejected with evidence (same inputs):

| Variant | DEV letters (time-plausible) | IPN false letters | Decision |
|---|---|---|---|
| V0 baseline | 89 (46) | 712 (8.26/min) | — |
| **V1 evidence accept (shipped)** | **111 (60)** | **712 (8.26/min)** | ✅ |
| + trim latched window | 111 (60) | 723 | ❌ no gain |
| faster: 2 decodes ≥500 ms, span 700 ms | 253 (176) | 1161 (13.5/min) | ❌ +63% false letters |
| faster: 3 decodes ≥500 ms, span 700 ms | 117 (70) | 785 | ❌ +10% false for +6 letters |
| 2 s window | 93 (52) | 626 | ❌ fewer real letters |
| singleton margin ≥4 | 58 (31) | 467 | ❌ keeps 52% of real vs 66% of false letters |
| singleton margin ≥8 | 9 (6) | 163 | ❌ removes almost all real letters |

The margin result holds in both signer halves (A: 41/78 real vs 303/467 false kept at margin 4;
B: 17/33 vs 164/245). The faster timing was not shipped because ordinary movement already
produces false letters; making them 63% more frequent would cost more Delete taps than it saves
in hold time. No retraining: the A–Z phone collection (`az1_collection`) has zero verified samples.

## 5. Components changed

| File | Change | WORD reachable? |
|---|---|---|
| `fingerspelling/HeldLetterPolicy.kt` | `acceptWhileHandMissing` config (default false), latch kept through the absence a letter was added in, `deleteLast()`, `repeatLast()`, read-only candidate progress | No (FINGERSPELL only) |
| `fingerspelling/ContinuousFingerspell.kt` | `practical` ctor param (default false); practical branches in `select`/`pause`/`consume`/`emit`; `deleteLast`/`repeatLast`/`holdForReview`/`resumeAfterReview`; interaction counters in the diagnostic JSON | No |
| `fingerspelling/FingerspellRuntime.kt` | `practicalEnabled` param, delegations, 2 snapshot fields with baseline defaults | No |
| `fingerspelling/FingerspellPracticalControls.kt` (new) | Repeat / Done inside RECOGNIZED (own WRAP_CONTENT width); DELETE LAST LETTER row in the pull-up panel above the CLEAR row (same style as CLEAR); all `GONE` unless FINGERSPELL owns | No |
| `res/values/fingerspell_practical.xml` (new) | 4 view ids | No |
| `RecognitionActivity.kt` (+24/−1) | 1 field; 1 ctor arg; 1 flag-gated call in the **FINGERSPELL-continuous** render branch; `renderFingerspellPractical()`; 3 lines in the FINGERSPELL-only Hear branch (hold/resume) | No: every new line is inside a FINGERSPELL branch or flag-gated |
| `coordination/RecognitionCoordinationBridge.kt` (+4) | In `review()` (only reachable when FINGERSPELL owns): hold on open, resume on dismiss, only if `practicalMode` | No |
| `build.gradle.kts` (+8) | `fingerspellPractical` → `FINGERSPELL_PRACTICAL_ENABLED` (debug), `false` (release); `recognitionPortrait` → manifest placeholder `recognitionOrientation` (`portrait` when set, otherwise `unspecified` = Android default; release always `unspecified`) | Orientation: **yes, by your decision** (screen shared with WORD); flags: no |
| `AndroidManifest.xml` (+1) | `RecognitionActivity` `android:screenOrientation="${recognitionOrientation}"` | Same as above; without `-PrecognitionPortrait=true` it is the Android default |

Tools (offline, research only): `tools/fingerspelling/practical_replay.py`,
`practical_parity_fixture.py`, `practical_baseline_record.py`.

## 6. Tests and regression results

* **JVM, flag off (locked config):** `testDebugUnitTest` — 58 suites, **283 tests, 0 failures**
  (first build; includes all existing fingerspelling, coordination, WORD/S2, SentenceBuilder,
  S4 skew and Text-to-ASL suites).
* **New JVM tests** (`FingerspellPracticalPolicyTest`, 9): baseline-defaults; one-frame dropout
  (baseline loses, practical keeps); sustained absence still stale; latch kept through the absence
  a letter was added in; Delete (latch kept, in-flight refused); Repeat (no third copy); draft
  retention vs full reset; **real phone-log replay** (incl. today's MMARY session → MARY);
  **Python↔Kotlin parity on 4,902 recorded calls** (incl. 2 clips where the variants differ).
* **Latest build (`def46844`, `-PfingerspellPractical=true -PrecognitionPortrait=true`):** BUILD SUCCESSFUL,
  fresh JVM run **284/284**; merged manifest shows `RecognitionActivity screenOrientation="portrait"`.
  Not installed (the phone runs `b74dcda5`).
* **Instrumented (written; could not run on the phone — MIUI blocks the test from opening the screen,
  op 10021 "start in background" stays `ignore`):**
  `FingerspellPracticalInstrumentedTest` (Delete/Repeat UI, draft survives pause + reselect, review
  hold blocks inference, WORD owner: panel GONE, 0 fingerspell calls, WORD sentence unchanged, fresh
  word on re-entry). Skips itself when the flag is off. Existing `ContinuousFingerspellInstrumentedTest`
  and `FingerspellOwnershipInstrumentedTest` should be re-run on the candidate.

### 6a. Flag-on build

Locked property set + `-PfingerspellPractical=true`, blank credentials, PowerShell from `android/`:
`testDebugUnitTest assembleDebug assembleDebugAndroidTest` — **BUILD SUCCESSFUL**.
Generated `BuildConfig`: `FINGERSPELL_PRACTICAL_ENABLED = true`, `FINGERSPELL_CONTINUOUS_ENABLED = true`,
`RECOGNITION_COORDINATION_ENABLED = true`. JVM: **283 tests, 0 failures** (same suite, flag on).

| Artifact (not installed) | sha256 | bytes |
|---|---|---|
| first candidate (superseded) | `f26178ef3098c57b33ec8ae98bbabb106e2eae805a196ce34f4981f93b76bd62` | 850,761,837 |
| second candidate (installed on the phone) | `b74dcda5ff3b8732c6534f805ff0b11fb2f97a8b41808ca41fb5409ba640c0e6` | 852,209,150 |
| third candidate (Delete in panel, no portrait lock) | `d0d8da9441595d625256db48be4fdbb6406bdc3945512aa9afdd04960eaa8226` | 852,209,198 |
| **current candidate** `app-debug.apk` (+ portrait lock; not installed) | `def468442289c1b54f0134fb5574e2dba6d77b04ec6d2d998e9924d1bb3b2a85` | — |
| current `app-debug-androidTest.apk` (not installed) | `1ca12fd5a11d511686c38e08b7a6c73fb2a0531c468ffa497a39fe8429bfad0a` | — |

The candidate is built from `098f3682` (it also contains the Text-to-ASL commits that precede it on
this lineage). Rollback target: `76bc90a4…` (the build that was on the phone this morning, from the
Text-to-ASL integration worktree), backed up with your preferences in
`C:\Users\Gigabyte\apphear_artifacts\fingerspell_practical_v1_20261023\backup\`.

## 7. Before/after measurements (identical inputs)

Offline end-to-end, DEV 256 clips / 15 signers + IPN 40 clips / 86 min, worker latency 200 ms:

| Metric | Before (V0) | After (V1) |
|---|---|---|
| DEV letters appended | 89 | **111 (+25%)** |
| DEV time-plausible letters | 46 | **60 (+30%)** |
| DEV results discarded for a momentary dropout | 125 | **0** |
| DEV CER (fluent, median 3.2 letters/s) | 97.3% | 96.6% |
| DEV substitutions / insertions (edit alignment) | 2 / 0 | 2 / 0 |
| DEV exact words | 0 | 0 |
| DEV natural doubles captured | 0 / 139 | 0 / 139 (Repeat is the path) |
| IPN false letters (ordinary movement) | 712 · 8.26/min | 712 · 8.26/min (unchanged) |
| IPN accidental doubles | 89 | 89 |
| False **commits** from movement | 0 (explicit confirm) | 0 (explicit confirm) |

Latency sensitivity (same inputs, 400 ms worker latency; the phone showed 130–780 ms):

| Metric | Before (V0) | After (V1) |
|---|---|---|
| DEV letters appended / time-plausible | 78 / 42 | 107 / 58 (+38% plausible) |
| DEV results discarded for a momentary dropout | 172 | 0 |
| IPN false letters | 587 | 679 (+16%) |

So the fix is not free when inference is slow: some results that return while a resting/gesturing
hand briefly drops out now count. Real letters still grow more than twice as fast as false ones,
and the verified failure (a correctly held letter silently lost) is worse for the user than an
extra letter, which DELETE LAST LETTER removes. The phone protocol (§10, step 7) measures this directly.

Phone logs (exact acceptance-layer replay): LOST_E "" → **"E"**; EY "EY" → "EY".

Interaction cost (deterministic, from the code paths; per-letter hold ≈2.1–2.3 s in both):

| Task | Before | After |
|---|---|---|
| Commit a correct word | Hear + Confirm (2 taps) | Done or Hear + Confirm (2 taps) |
| Fix one wrong letter in an N-letter draft | expand + CLEAR (2 taps) + re-hold N letters (≈2.2·N s) | expand + DELETE LAST LETTER (2 taps) + re-hold 1 letter |
| Remove a stray letter from ordinary movement | same as above | expand + DELETE LAST LETTER (2 taps) |
| Double letter (LL) | lower hand ≥0.8 s, raise, hold ≈2.2 s again | Repeat (1 tap) |
| Screen off / app switch mid-word | draft lost, re-spell N letters | draft kept |
| Re-enter via Settings after a commit | old word silently prefixed to the next commit | fresh word |
| Letter arrives behind the confirm dialog | "Spelling changed", +2 taps | cannot happen |

**Claims are separated:** offline numbers are cross-signer replay on fluent public data and non-sign
gestures; the phone-log result is an exact replay of decisions only; **no real-user claim is made** —
that needs the device protocol in §10.

## 8. Remaining model / data limits

* **No "not a letter" output.** The V2.1 model was trained only on fingerspelling, so steady
  non-letter hands become letters (8.3/min on ordinary movement). Fixing this needs negative
  (non-fingerspelling) training data with signer splits — none is verified today.
* **Letter discrimination** (prior V2.1 DEV phone review, no-space recall): weakest Q 0.24, X 0.32,
  V 0.36, D 0.39, Y 0.41, U 0.43, P/M 0.46, L 0.48; strongest A 0.81, H/I 0.77, B 0.72. No isolated
  all-26 phone test exists; the A–Z phone collection is empty (0 verified samples). Only A/M/Y were
  physically checked (3/3).
* **Fluent speed:** sequence decoding is ~40% CER; held letters at ≈2 s each remain necessary.
* **J/Z** need motion inside one held window; untested on the phone.
* **Doubles by motion** (slide/bounce) are not separable by the singleton window.

## 9. WORD unchanged — confirmation

* `docs/audit/baselines/fingerspell_practical_v1_baseline_2026-10-23.json`: of 1,041 tracked files under
  `android/app/src`, `build.gradle.kts` and the FINGERSPELL package, **1,034 are unchanged**; the 7
  changed files are the three `fingerspelling/` files plus the four shared files justified in §5
  (the manifest only for your portrait-lock decision, behind `-PrecognitionPortrait=true`).
  **No packaged asset differs in content**; the FINGERSPELL package is unchanged.
* Untouched: Candidate01 (`perceptionvnext/`), S2-R3 Arm A and S2-R2 packages, decoder/confirm-boundary/
  re-arm, Recognition Window Materializer, WORD_BLEND_01/02 and the frozen WORD model, SentenceBuilder,
  WORD output/speech, Context Assist matching. Not coupled to R1_CB70; WORD_BLEND_03 not started.
* With the flag off, every new branch is unreachable (`practical=false` everywhere; the bridge and the
  Activity only add calls when `practicalMode`).
* With the flag on, ownership is unchanged (`fingerspellOwnsFrames == (mode == FINGERSPELL)`), and the
  only new state on a WORD switch is clearing the FINGERSPELL draft/confirmed text.
* Note: 12 Text-to-ASL web assets in this worktree differ from their commits only by checkout line
  endings — the same bytes as the locked-baseline worktree (`apphear-audit-2f2723`).

## 10. Next step and phone validation

Phone validation **is needed** before any claim about real users. Candidate APK: §6a
(`f26178ef…`). **Not installed — needs your approval.**

Short device protocol (Xiaomi, ~15 min):
0. Back up the installed app (`adb shell pm path com.example.apphear` → pull base.apk, record sha
   0469d1b8…). Install with `adb install -r` only (keeps data). Never uninstall/clear; never
   `connectedDebugAndroidTest`. Instrumented tests via `adb install -r` of the test APK +
   `adb shell am instrument -w -e class com.example.apphear.fingerspelling.FingerspellPracticalInstrumentedTest …`.
1. **WORD smoke** (unchanged check): sign 3 known words in WORD; same commits/speech as before.
2. **Spell a name** (e.g. MARY) holding each letter; watch "Holding M (1/3)" → "Added M"; Done → Confirm.
   Record time and taps.
3. **Correction:** spell a 4-letter word with one wrong letter, Delete it, finish, commit.
4. **Double:** H-E-L, Repeat L, O → HELLO.
5. **Interruption:** 3 letters, Home, return → draft still there.
6. **Review hold:** 2 letters, Done, keep signing 5 s with the dialog open, Cancel → draft unchanged;
   Done → Confirm succeeds first time.
7. **Ordinary movement:** 30 s of resting/gesturing hands in FINGERSPELL, once on the old build (before
   installing) and once on the candidate; count false letters (offline predicts ≈4 per 30 s on both, up
   to +16% on the candidate when inference is slow); clear with long-press Delete.
8. Pull `files/fingerspell_continuous_last_active.json` (practical_v1 counters) and
   `files/fingerspell_practical_flow.json`.
Rollback: `adb install -r` the backed-up APK (0469d1b8…).

After that, the next real accuracy lever is data, not decision logic: a verified, signer-split set of
held A–Z letters and non-letter hand movement from the phone (recorder pipeline), used first for an
evaluation set and only then for a negative-aware model.

Tracker entry (to add to `context/progress-tracker.md` when this worktree is merged; not added here to
avoid clashing with uncommitted tracker edits in the audit worktree):
> 2026-10-23 — FINGERSPELL practical v1 (debug flag `fingerspellPractical`, default off). Evidence-based
> acceptance (+25% DEV letters; 0 new false letters at 200 ms, +16% at 400 ms latency), Repeat/Done, draft kept across
> interruptions, fresh word per entry, review hold, no extra letter after a mid-letter hand exit. 284 JVM tests pass; WORD files
> untouched. Ordinary movement still yields 8.3 false letters/min (model limit). Partial phone session; open decisions in §12.
> Report: docs/audit/FINGERSPELL_PRACTICAL_V1_2026-10-23.md.

## 11. Device session, 2026-10-23 (partial, paused)

Phone: Xiaomi M2101K7AG (Android 12). Installed with your approval via `adb install -r`; data and
settings kept (`firstInstallTime` unchanged). The phone was running `76bc90a4…` (Text-to-ASL toggle
build installed 09:35 today), not `0469d1b8…`; both are backed up.

| Step | Result | Evidence |
|---|---|---|
| Instrumented tests | **Not run.** MIUI blocked the test from opening the recognition screen ("Permission Denied Activity"); the setting change did not flip MIUI op 10021. No crash. | logcat |
| 1. WORD smoke | **Pass.** HELLO, HOME, YES committed on EXPERIMENTAL_WORD_BLEND_02 as before. | logcat `commit` lines |
| 2. Spell MARY (`f26178ef`) | First M added during a one-frame dropout (the fix working). **Bug:** result MMARY — M added as the hand left, the absence rearmed, re-shown M added again. **Bug:** Repeat/Done clipped (controls took the card's narrow width), so no commit. | `fingerspell_continuous_last_active.json`, screenshot |
| Fixes → `b74dcda5` | Latch kept through the absence a letter was added in; controls get their own width; hint line, counter and Delete removed at your request. Replay of the MMARY log → MARY. | JVM 284/284 |
| A–C (`b74dcda5`) | Last session MAE committed on the first Confirm (review hold 1, confirm 1); per-letter ≈1.1 s from first decode. Earlier sessions overwritten (the log keeps one session). Two **screen rotations** rebuilt the recognition screen. | diagnostic JSON, logcat |
| D. Ordinary movement | Not done (paused). | — |

Open from the session: your observations for A (MARY) and B (HELLO with Repeat), and step D on the
candidate and on the old build. Evidence is in
`C:\Users\Gigabyte\apphear_artifacts\fingerspell_practical_v1_20261023\device\`.

## 12. Plan from here

Decisions for you:
1. ~~Correction without Delete~~ — **decided:** DELETE LAST LETTER in the pull-up panel above CLEAR
   (build `d0d8da94`).
2. ~~Rotation wipes the draft~~ — **decided:** recognition screen locked to portrait (WORD too), behind
   `-PrecognitionPortrait=true` (build `def46844`). Note: the debug "rear camera" mode also stays portrait.

Next work, in order:
1. **Finish the device session** when signing is easy: A/B notes, step D on candidate and old build,
   then roll back to `76bc90a4` (or keep the candidate, your choice).
2. **Short phone check with `def46844`**: rotate the phone mid-spelling (draft must stay), DELETE LAST
   LETTER, Repeat, Done; WORD smoke in portrait.
3. **Diagnostics that survive a session:** append each FINGERSPELL session to a small rolling file so a
   multi-step phone test can be scored afterwards (today only the last session is kept).
4. **Data, the real accuracy lever:** record a small, signer-split phone set with the ASL Recorder —
   held A–Z letters plus ordinary non-letter hand movement — first as an evaluation set (per-letter
   accuracy, false letters/min on this phone), later for a model with a "not a letter" output.
5. **Merge path:** commit on this branch after your review; expect small conflicts with the Text-to-ASL
   toggle branch in `RecognitionActivity.kt` and `RecognitionCoordinationBridge.kt`.

Not planned: faster hold timings or score thresholds (rejected with evidence in §4), retraining
without verified data, any change to the WORD path.

## 13. Integration into the application baseline — 2026-10-23

Publication branch: `claude/fingerspell-practical-integration`. Parent baseline:
`ae7afc987747fc21658fd8d1ce8881acdb5d16bf` on `claude/text-to-asl-integration-c98d88`.
The only implementation commit above it is `1affb6ea` (practical FINGERSPELL); the original
FINGERSPELL source remains `51c93496` on `claude/friendly-torvalds-9872e5`. The separate WORD
research commit was not brought over. This section supersedes the pending commit/merge path
in §12; baseline merge and integration phone validation remain pending.

Integration checks:

- The WORD/FINGERSPELL toolbar still uses `manual()` -> `apply()` -> `ContinuousFingerspell.select()`.
  Entering FINGERSPELL starts a fresh word and ends review hold; leaving pending letters for WORD
  still asks for confirmation. The baseline layout XML is unchanged; the new Delete row attaches
  above the original CLEAR row, and Repeat/Done attach to RECOGNIZED.
- Rechecked `git diff ae7afc98 1affb6ea` across `android/app/src`, `android/app/build.gradle.kts`
  and `packages`: **1,087 existing tracked files; 1,080 unchanged, seven modified, none deleted;
  six added Android files**. The seven modified files are the three existing FINGERSPELL files
  and the four shared files justified in §5. Dedicated WORD/Candidate01/S2/materializer/
  SentenceBuilder/Context Assist implementation and all package assets are unchanged from
  `ae7afc98`. The only shared WORD-screen effect is the opted-in portrait lock.
- Prior integration handoff records **336/336 JVM tests passing with both new switches on and
  with both off**. On continuation, the saved final flag-off XML independently confirms 66 suites,
  336 tests, zero failures/errors/skips, including 11 coordinator and nine practical-policy tests.
  Generated BuildConfig confirms practical mode off for that final regression run. No tests were
  rerun for this documentation-only continuation; the earlier flag-on result is handoff evidence.
- Flag-on integration build retained the locked baseline properties plus `conversationTimeline`,
  `sentenceAssist=visible`, `conversationFlowV1`, `conversationAutoReply`, `conversationAutoListen`,
  `llmFallback` (blank key), `recognitionModeToolbar`, `fingerspellPractical=true` and
  `recognitionPortrait=true`. The APK hashes below were independently rechecked on continuation.

| Integration artifact (not installed) | SHA-256 | Bytes |
|---|---|---|
| `app-debug.apk` | `2709fd4dd7680fb1794d68991552b8332367e4cd45cdf72566532180daa8f500` | 852,218,564 |
| `app-debug-androidTest.apk` | `51b34c4c3f14ba1a47267aaaf960f7b6f4d0708797a278dec3dc707892038baa` | 7,629,193 |

The final flag-off test run regenerated BuildConfig/merged manifests; those files describe that
test configuration, not the previously assembled flag-on APK. Do not infer APK flag values from
the latest generated files alone.

No merge or device action was performed during this continuation. Last reported phone build is
`b74dcda5`; rollback build `76bc90a4` remains backed up (§11). Next: review this integration branch,
then separately merge into the application baseline when approved. Before rollout, finish the
portrait mid-spelling, DELETE LAST LETTER, Repeat, Done, ordinary-movement and WORD phone checks.
Engineering tests and source preservation do not establish live cross-signer recognition accuracy.
