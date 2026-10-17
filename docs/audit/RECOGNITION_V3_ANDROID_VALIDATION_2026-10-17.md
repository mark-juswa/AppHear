# Recognition V3 — Android Validation Milestone (2026-10-17)

Branch `claude/s2-r3-eval-suite`, uncommitted; the work is prepared for your approval (§8).

**Protected and unchanged:**
- Candidate01, the frozen S2-R2 package and the frozen Gate-2 recognizer;
- the decoder, the materializer, SentenceBuilder, FINGERSPELL and the release build.

Protected TEST, E6 and Tier 3 were not opened.

A device was attached later in the session. On-device parity and a live shadow smoke run then passed (§3b). A paired run with real signing is still pending (§5).

---

## 1. What was implemented, and why

| Item | Why | Files |
|---|---|---|
| WORD v2 TFLite package, debug assets only | The device needs a hash-pinned model with proven parity; release builds must not be able to load it | `deploy/export_word_v2_candidate.py`, `android/app/src/debug/assets/word_v2_candidate/` |
| Recognizer package spec (main), frozen default | The smallest change that lets the same loader open a second pinned package. Default behaviour and the frozen identity JSON are byte-identical | `RecognitionV2LiveRecognizer.kt` (+20/−7) |
| **WORD shadow mode** (debug only, `--es word_shadow_package WORD_V2_CANDIDATE`) | Paired device evidence on identical inputs: WORD v2 classifies the same materialized window and V2 view, its prediction is logged next to the frozen one, and the displayed word is unchanged. S2-R2 and the rest of the pipeline are untouched | `WordShadowPackages.kt` (new), `PhoneCausalController.kt` (+26), `PerceptionVNextLiveRecognitionActivity.kt` (+5) |
| On-device parity test | The first device run proves the shipped v2 asset matches Keras through the same loader path the shadow uses, and that the frozen package still loads unchanged | `androidTest/.../WordV2ShadowParityInstrumentedTest.kt` |
| Paired comparison on device-recorded windows | The strongest available evidence without a device: the exact windows the phone produced | `docs/audit/probes/word_track/device_window_pairing.{py,json}` |
| S2-R3 phone-domain diagnosis | Explains the operating-point trade-off before any new training or sweep | `docs/audit/probes/s2_discrimination/phone_domain_diagnosis.{py,json}`, `phone_nonsign_evidence.json` |

**Not built, on purpose:** an on-device S2-R3 shadow. Every exact-parity capture already persists the device observations, and offline replay of any S2 package on them is exact (rolling-equivalence-checked in the suite). S2 candidates can therefore be compared on identical phone observations without touching the runtime.

## 2. Model identities

| Model | Source | Android asset |
|---|---|---|
| Frozen WORD (default, rollback) | `tcn_v2_run_01/best.keras` `8107accb…` | `phase4a_gate2_recognizer_parity/ordinary_v2_tcn_fp32.tflite` `1ccf0afa…` (main assets) |
| WORD v2 (shadow candidate) | `word_track_robust_aug_02/best.keras` `4f56ce61…` | `word_v2_candidate/word_v2_fp32.tflite` `1de85b3c…`, manifest `2d4fd4ec…` (debug assets only) |
| S2 baseline | S2-R2 `b6f8b52c…` | unchanged |
| S2-R3 candidates (offline only) | Arm A epoch 10 `17915b02…`; epoch 21 `f7d8df31…`; shared normalization `754e5e0e…` | none |

## 3. Verification results

**WORD v2 host parity, Keras vs TFLite** (`word_v2_candidate/manifest.json` → `host_parity`):

| Check | Result |
|---|---|
| 20 pinned fixture views | max abs **2.4e-7**; top-1 / top-5 mismatches 0 / 0 |
| Mask-padding invariance | 4 / 4 exact |
| All 816 signer-disjoint DEV clips at 3.75 fps | top-1 agreement **816 / 816**, max abs 1.7e-6 |

**Android build** (`gradlew :app:assembleDebug :app:compileDebugAndroidTestKotlin :app:testDebugUnitTest`):
- `assembleDebug` and the instrumented-test compile succeed.
- JVM unit tests: 199 / 200 pass.

The one failure is `OriginalWordBatchTest.all203PayloadsMatchPinnedManifestAndNamedAnimation`, a hash pin on the ASL-Original-Words animation asset manifest. This change set touches nothing in that area, so the failure is independent of it. It was not re-run at HEAD to confirm it pre-dates this work, and it still needs its own look.

**Python tests:** suite, data split, event separation and detect: 35 / 35 pass. Lint is clean on new modules.

## 3b. Device run (2026-10-17, Xiaomi M2101K7AG, Android 12, serial 3ab64582)

**Install.** Built with the documented device flag set: the `build_working_baseline.ps1` option list, credential-free "fake" configuration, `-PperceptionVNext=true -PphoneCausalRecognition=true -PrecognitionV3ParallelHands=false -PrecognitionV3Profile=false`, Original Words on. Installed with `adb install -r`, which keeps app data. `connectedAndroidTest` was deliberately not used, because it uninstalls the app and its on-device sessions.

**Instrumented tests on the phone, all pass:**

| Test | Result |
|---|---|
| `WordV2ShadowParityInstrumentedTest` (20 fixtures, ≤ 1e-4, identical top-1; frozen identity unchanged) | OK |
| `RecognitionV2TfliteParityInstrumentedTest` (frozen Gate-2) | OK |
| `RecognitionV2EndToEndReplayInstrumentedTest` (through the modified loader) | OK |
| `PhoneS2ParityInstrumentedTest` | OK (3 tests) |

**Live shadow smoke session** (`session_20261017T022315Z`, 30 s, nobody signing, `word_shadow_package=WORD_V2_CANDIDATE`, S2-R2):

| Check | Result |
|---|---|
| Primary recognizer | frozen `1ccf0afa…`, identity unchanged |
| Shadow recognizer | `WORD_V2_CANDIDATE` `1de85b3c…` loaded, recorded in `identity.json` and `session_identity.json` |
| Observations / events | 182 / 0 (none expected) |
| Crashes | none |
| Observation interval | 200 ms median, 267 ms p95 |
| Candidate01 total | 146 ms median, 229 ms p95 |
| S2 | 7.9 ms median, 26.7 ms p95 |

Per-observation cost is unchanged from earlier sessions. The shadow runs only per event, so its cost was not exercised here.

**Still missing:** a session with real signing, to produce paired frozen/v2 device predictions (§5).

## 3c. First signed shadow session (`session_20261017T022535Z`)

- **Setup:** compact Stage-2 protocol (5 blocks), signer `shadow_word_v2_signer_01` (proficiency UNKNOWN), S2-R2 primary and WORD v2 shadow.
- **Data:** 461 observations; 461/461 frames verified; 6 events.
- **Location:** `artifacts/recognition_v3_stage2_compact_device/session_20261017T022535Z/`; analysis in `docs/audit/probes/word_track/shadow_session_20261017T022535Z.json`.
- **Labels:** protocol expectations only, NOT human-reviewed. The blinded review package is prepared (`transition_review/`).

**Integration on device: exact.**
- Device-logged primary and shadow outputs equal offline frozen / v2 on the identical windows for 6/6 events (top-1 and probability within 1e-3).
- Shadow invocation: 2.1–2.9 ms per event, against 2.4–2.9 ms for the primary.

| Event (block) | Expected | Frozen (displayed) | WORD v2 (shadow) | Hand fraction |
|---|---|---|---|---:|
| 1 (before block A) | — | RIGHT3 0.71 | RIGHT3 0.38 | 0.00 |
| 2 (A hands-down) | HELLO, HOME | MAN 0.35 | FIND 0.29 | 0.25 |
| 3 (B hands-up) | HELLO, HOME | LUNCH1 0.33 | LUNCH1 0.54 | 0.78 |
| 4 (C repeat) | HELLO, HELLO | **HELLO 0.83** | LUNCH1 0.56 | 0.83 |
| 5 (D sign-then-hold) | HELLO | **HELLO 1.00** | **HELLO 1.00** | 1.00 |
| 6 (E ordinary movement) | — | BREAKFAST1 0.41 | BREAKFAST1 0.28 | 0.70 |

**Reading (provisional until review):**
- **Frozen:** 2 expected-gloss outputs.
- **WORD v2:** 1, because it turned a HELLO into LUNCH1.
- **The session is perception-starved:**
  - body available in 3.5% of observations, hands in 19% (3% in block A);
  - only 6 events for 7 expected signs, and S2-R2 acquired little;
  - the screenshots show close, head-centred framing.
- **On non-sign events, v2 is again less confident** (0.38 / 0.28 against 0.71 / 0.41). That helps a confidence gate, but does not make a word correct.

**Combined device evidence, recorded windows plus this session:** frozen 12, v2 12 expected-gloss outputs. There is no demonstrated phone improvement for WORD v2, so it stays shadow-only.

## 3d. Second signed shadow session (`session_20261017T023004Z`, reframed) and both sessions together

- **Data:** 364 observations, 364/364 frames verified, 6 events.
- **Framing:** improved. Body available in 12% of observations (0% inside sign blocks; the shoulders were still mostly out of frame); hands in 22% (25–66% inside sign blocks).
- **Analysis:** `docs/audit/probes/word_track/shadow_session_analysis.py` → `shadow_session_20261017T023004Z.json` and `shadow_session_20261017T022535Z.json`.
- **Labels:** protocol expectations only (7 expected signs per session; block E is ordinary movement). Blinded review packages are ready in each session's `transition_review/`.

**WORD on device** (S2-R2 live; device = offline parity 12/12 events for both models):

| Session | Frozen expected-gloss outputs | WORD v2 expected-gloss outputs |
|---|---:|---:|
| 022535Z (close framing) | 2 / 7 | 1 / 7 |
| 023004Z (reframed) | 4 / 7 | 2 / 7 |
| **Total** | **6 / 14** | **3 / 14** |

**WORD v2 regresses on this signer's HELLO:**
- in 3 windows where frozen output HELLO (0.45–0.85), v2 output LUNCH1 (0.55–0.82);
- it never produced an expected gloss that frozen missed;
- together with its earlier loss of a hands-down HELLO on the phone oracle windows, this is a consistent HELLO→LUNCH1 weakness on phone input.

The offline DEV gain (+4.4 points, p = 0.002) did **not** transfer to this device and signer. WORD v2 stays shadow-only and is **not** promotable.

**S2 replay on the same observations** (frozen recognizer):

| S2 | Events | Expected-gloss outputs (of 14) | Outputs in ordinary-movement block | Outputs outside blocks | Other outputs in sign blocks |
|---|---:|---:|---:|---:|---:|
| S2-R2 | 12 | 6 | 2 | 2 | 2 |
| S2-R3 Arm A e10 | 15 | 6 | 3 | 2 | 4 |
| S2-R3 Arm A e21 @ θ 0.8 | 12 | **7** | 3 | **0** | 2 |

- In session 1, S2-R3 separated the hands-up HELLO→HOME and HELLO→HELLO pairs into distinct events, which S2-R2 did not. In session 2 it did not help.
- With n = 14 signs from one signer, nothing here is significant.
- It agrees with §6: S2-R3 can split consecutive signs, but still fires in ordinary movement.

## 3e. Human labels for `session_20261017T023004Z` (provisional)

**Label provenance.** Reviewer `gch` labelled 6 GENUINE signs, the second C-block HELLO as UNCERTAIN, and block E (314–342) as CONFIRMED_NON_SIGN.
- The file declares `blinded_to_predictions: true`, but per-event model outputs for this session had already been shown in chat.
- No block was attested as "entire block reviewed", so the project analyzer rejects it (`HUMAN_REVIEW_INCOMPLETE`).
- The file is kept unchanged beside the review page.
- Scores: `docs/audit/probes/word_track/shadow_session_20261017T023004Z_human_labels.json`.

| Windows (6 genuine signs) | Frozen correct | WORD v2 correct |
|---|---:|---:|
| Device S2-R2 event windows | 4 | 2 |
| Human boundaries ±250 ms (runtime materializer rule) | 4 | **6** |
| Offline S2-R3 Arm A e10 windows | 2 | 3 |
| Offline S2-R3 e21 @ θ 0.8 windows (3 signs detected) | 2 | 3 |

**What happened:**
- **Clean windows:** with human boundaries, WORD v2 is correct on all 6, including both HOME signs. The frozen model reads both as LUNCH1.
- **Contaminated windows:** v2's two device errors are windows that ran past the sign. Event 3's window (163–176) covers HELLO (165–169) and the onset of HOME (175–180). Event 4's window (216–233) extends past HELLO (217–223) into the uncertain second repetition. In both, frozen still says HELLO and v2 says LUNCH1.
- **Missed signs:** S2-R2 gave neither HOME its own event (A, B).

**Conclusion:**
- WORD v2 is the better classifier of a correctly bounded phone sign, but less robust than frozen to the next sign's onset inside the window.
- On the phone the two problems are coupled: merged or over-long windows from segmentation decide which recognizer wins.
- **WORD improvement to try (data-only, cheap):** train with windows that include neighbouring-sign onset and tail context, cut from stitched TRAIN sequences, so the classifier learns to ignore them.
- **Segmentation:** separating HELLO from HOME in hands-up signing remains the S2 goal.

## 3f. WORD v3 (neighbour-context augmentation): tested, not adopted

**Hypothesis (from §3e).** v2 fails when the event window holds the next sign's onset.

**v3.** v2 plus neighbour context: 40% of augmented TRAIN views carry the tail of a preceding and/or the onset of a following sign, from the same signer where possible. Seed, epochs and selection are the same as v2.
- Run: `artifacts/.../word_track_robust_aug_03` (val_loss 2.171; v2 2.169).
- Evaluation: `docs/audit/probes/word_track/word_v3_eval.{py,json}`.

**Controlled test on held-out signers.** Built from the full-length DEV videos, independently of the TRAIN-side construction; 816 clips at 3.75 fps:

| Window | Frozen | v2 | v3 |
|---|---:|---:|---:|
| Clean span ±250 ms | 39.6% | 43.1% | 44.4% |
| + next sign lead-in and first 30% | 35.7% | 36.8% | 35.9% |
| + next sign lead-in and first 50% | 34.1% | 34.9% | 34.3% |
| + previous sign's last 30% | 28.1% | 33.9% | 34.2% (vs frozen p = 1e-6) |

| Phone windows | n | Frozen | v2 | v3 |
|---|---:|---:|---:|---:|
| Recorded device windows (human-reviewed) | 13 | 10 | 11 | 10 |
| Shadow 023004Z device windows (unblinded labels) | 4 | 4 | 2 | 2 |
| Shadow 023004Z human-boundary windows (unblinded labels) | 6 | 4 | 6 | 4 |

**Findings:**
- Trailing contamination costs every model 4–9 points. v2 is **not** more fragile to it than frozen on held-out signers, and neighbour training did not reduce the loss.
- Leading contamination is where v2 and v3 are clearly better than frozen.
- The two device HELLO→LUNCH1 flips in §3e are therefore not explained by a general weakness. They are two windows from one signer.
- **v3 is not adopted.** v2 remains the WORD candidate.

**The lever for merged windows is segmentation**, which keeps the next sign out of the window, not recognizer augmentation.

## 3g. Splitting consecutive signs: the confirm-boundary rule

**Diagnosis** (`docs/audit/probes/s2_discrimination/transition_split_probe.{py,json}`).
- **S2-R2 cannot be helped by any decoder rule.** Across hands-up HELLO→HOME it stays in POST after HELLO and never enters ACTIVE for HOME (SEP27 B, shadow 023004Z B).
- **S2-R3 (Arm A) does produce a second ACTIVE run for HOME,** separated by only 1–2 POST observations. The decoder trace for 023004Z block B (observations 171–175) shows why it still merges. At phone cadence (200–267 ms), that POST lasts exactly the confirmation time (266.6 ms), so the next ACTIVE lands on the confirmation boundary, where production treats it as a continuation (`CANCEL_POST_ACTIVE_AT_CONFIRM_BOUNDARY`).
- Yesterday's SHORT_POST variant only handled POST shorter than the confirmation time, so it never covered this case.

**Rule** (`event_separation.py`, `CONFIRM_BOUNDARY_{50,70}`). If ACTIVE arrives after POST has already lasted the full confirmation time, and the POST probability peaked at 0.5 or 0.7 or above, commit the previous sign and start a new candidate. All production thresholds are unchanged; BASELINE remains identical to production (tested).

**Provenance.** Derived from the trace of shadow session 023004Z. That session is reported separately; the other evidence did not inform the rule.

| Evidence (Arm A e10, frozen recognizer unless stated) | Production decoder | Confirm-boundary 0.7 |
|---|---:|---:|
| CAL streams: distinct signs / merged / within-sign false splits / events on non-sign blocks | 73.8% / 132 / 0 / 85 | 75.7% / 93 / 7 / 96 (+13%) |
| Held-out DEV continuous (stitched): detected / correct words / extra events per min | 43.7% / 15.4% / 0.17 | 49.0% / 18.7% / 0.30 |
| Held-out DEV natural (stitched): correct words / extra events per min | 29.1% / 1.95 | 29.3% / 2.09 |
| Tier-2 genuine phone: correct words (of 23) / distinct signs / continuous distinct (of 11) | 13 / 15 / 8 | **14 / 16 / 9** |
| Tier-2: events inside confirmed non-sign / unmatched events | 9 / 18 | **9 / 18** |
| Shadow 022535Z (protocol labels): expected words (of 7), frozen / v2 / ordinary-movement words | 4 / 4 / 2 | **5 / 5 / 2** |
| Shadow 023004Z (derivation session): expected words, frozen / v2 / ordinary-movement words | 2 / 3 / 1 | 5 / 4 / 1 |

**Reading:**
- **It works on genuine signing.** This is the first lifecycle change that adds correct words on genuine phone signing (Tier 2 +1; independent shadow session +1) without adding phone false events.
- **Its cost is small.** About +0.1–0.15 extra events per minute on held-out stitched rest, and +13% events on CAL non-sign blocks, which is over the pre-registered +10% CAL limit. It is therefore **not selected under the D7-style rule** and stays a research variant.

**Against today's production system** (S2-R2 + production decoder + frozen):

| Evidence | Production | S2-R3 Arm A e10 + confirm-boundary + frozen |
|---|---:|---:|
| Tier-2 correct words (of 23) | 8 | 14 |
| Tier-2 events inside confirmed non-sign | 5 | 9 |
| Two shadow sessions, expected words (of 14) | 6 | 10 |
| Two shadow sessions, ordinary-movement words | 2 | 3 |
| Held-out continuous correct words | 9.6% | 18.7% |

The remaining false-activation cost comes from S2-R3's discrimination (§6), not from this rule. The split rule is ready to pair with whichever S2 candidate fixes discrimination. It needs no change to the materializer or recognizer.

## 4. Does WORD v2 improve recognition on the phone?

**Not yet measured on a live device; no device was attached.** The strongest substitute is the exact recognition windows the phone itself produced, classified offline by both models (`device_window_pairing.json`).

- **Parity:** offline frozen top-1 reproduces the device-logged top-1 on **32 / 32** recorded events, so offline replay of the device windows is faithful.
- **Population:** 32 events from 5 sessions (Tier 2 plus the S2-FIT exact session).

| Window label (human review) | Events | Frozen correct | WORD v2 correct | Top-1 ≥ 0.5: frozen / v2 |
|---|---:|---:|---:|---|
| GENUINE sign | 13 | 10 | **11** | 11 / 10 |
| CONFIRMED_NON_SIGN | 5 | — | — | 2 / 2 |
| UNLABELED (never counted as confirmed false) | 14 | — | — | 6 / **3** |

- **Fixed:** HOME in SEP23-representative event 5. The frozen model said THINK (0.92); v2 says HOME (0.37).
- **Broken:** none.
- **TABLE:** both models are wrong when the refiner accepts no hands (hand fraction 0.00–0.06), and both are right in the one TABLE event with hands (S2-FIT event 4).
- **Signers:** genuine windows come from the design signer plus two declared distinct signers, so per-signer numbers are too small to report.

**Consistent offline evidence** from the previous milestone:
- signer-disjoint DEV at 3.75 fps: 38.6% → 43.0% (p = 0.002);
- all 5 held-out signers at or above frozen;
- phone oracle windows 22 → 22;
- more robust to hand loss.

**Conclusion (updated after the signed shadow sessions, §3d).**
- On historical device windows: no regression, +1.
- On two live sessions: −3, all HELLO→LUNCH1.
- Combined device evidence: frozen 16, WORD v2 14 expected-gloss outputs.

WORD v2 does not improve recognition on this phone and signer and must not be promoted. The next WORD step is to diagnose the HELLO/LUNCH1 confusion under phone input (likely the augmentation's hand-drop and cadence views shifting a location-based decision) before any further WORD training.

## 5. How to run the device validation

1. **Build and install** the debug APK (`android/app/build/outputs/apk/debug/app-debug.apk`).
2. **Run on-device parity:**
   ```
   gradlew :app:connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.example.apphear.perceptionvnext.WordV2ShadowParityInstrumentedTest
   ```
3. **Capture** with the existing Stage-2 launch, adding one extra:
   ```
   adb shell am start -n com.example.apphear/.perceptionvnext.PerceptionVNextLiveRecognitionActivity --ez perception_vnext_enabled true --ez phone_causal_enabled true --ez continuous_transition_diagnostics true --ez recognition_v3_stage2_diagnostics true --ez s2_exact_parity_capture true --es phone_s2_package S2_R2_CANDIDATE --es phone_rearm_policy PRE_OR_POST_EXPERIMENTAL --es validation_signer_id <id> --es validation_signer_proficiency <level> --es word_shadow_package WORD_V2_CANDIDATE
   ```
4. **What each event logs:** `shadow_top1_gloss`, `shadow_top1_probability`, `shadow_top5`, `shadow_expected_rank`, `shadow_recognition_invocation_ms`. `identity.json` records both recognizers' identities.
5. **Analyse** after review with `device_window_pairing.py`. It reports frozen-vs-v2 correctness on human-labelled events and checks the device shadow against offline v2 (`device_shadow_parity`).
6. **Expected cost:** one extra invocation of an identical-size model per event. The frozen model measured 2.7 ms median on the Xiaomi; no per-observation cost.

## 6. What we learned about S2-R3 phone discrimination

`phone_domain_diagnosis.json` measures each S2 model's peak P(ACTIVE) per reviewed genuine phone sign (23) and per 9-observation chunk of confirmed non-sign intervals (76), against the same units on CAL streams.

| Model | CAL AUC | **Phone AUC** | Phone genuine ≥ 0.8 | Phone non-sign chunks ≥ 0.8 | CAL non-sign ≥ 0.8 |
|---|---:|---:|---:|---:|---:|
| S2-R2 | 0.922 | **0.770** | 52% | 16% | 2.0% |
| S2-R3 Arm A e10 | 0.991 | **0.832** | 70% | 22% | 3.4% |
| S2-R3 Arm A e21 | 0.996 | **0.773** | 61% | 20% | 3.4% |

1. **This is not a calibration problem.** On CAL, S2-R3 separates signs from non-sign almost perfectly (AUC 0.99+). On the phone, genuine and non-sign peaks overlap (AUC 0.77–0.83): 20–28% of confirmed non-sign chunks peak above 0.5. No threshold, CAL-chosen or phone-chosen, can keep the consecutive-sign gains without false activations. More operating-point sweeps are not worth running.
2. **S2-R3 has learned "accepted hands moving = signing".**
   - Missed phone signs have little hand evidence: Arm A e10 signs peaking below 0.8 have a mean accepted-hand fraction of 0.11, against 0.89 for detected signs. These are mostly TABLE.
   - Non-sign chunks that fire have hand fraction 0.61, against 0.18 for quiet chunks. They come from open-hand holds, grooming adjustments, phone interaction, ordinary movement and body repositioning (`phone_nonsign_evidence.json`).
3. **The original assumption to challenge:** that the false activations are a threshold or history artefact. They are a training-evidence and input problem.
   - The CAL/FIT negatives are mostly no-hands N0 plus P1 from only two participants, so hand-visible everyday behaviour is barely represented.
   - On the positive side, phone signs whose hands the refiner rejects carry almost no hand evidence for S2 to use.
   - Arm B (masking refiner-rejected phantom proposals) would not help either failure. The false activations come from real accepted hands, and the misses from missing ones.

**Better direction, in order:**
- **(a) Training evidence:** hands-visible non-sign recordings from several people, covering the five behaviours above, split by person into FIT / CAL / held-out.
- **(b) A window-level admission check.** The event's whole window, not per-frame S2, decides sign vs non-sign. WORD v2 is already less confident on unlabelled windows (3 vs 6 at ≥ 0.5), which is the signal such a check would build on.
- **(c) Flat-hand perception** (TABLE), which also caps WORD.

## 7. Comparison with the frozen baseline (summary across milestones)

| Component | Evidence type | Frozen | Candidate |
|---|---|---|---|
| WORD | Device-recorded windows, genuine (n = 13) | 10 correct | **11** (v2), 0 regressions |
| WORD | Signer-disjoint DEV, 3.75 fps | 38.6% | **43.0%** (p = 0.002) |
| S2 | Genuine phone, continuous distinct events (of 11) | 2 | 8 (Arm A e10) / 5 (e21 @ 0.8) |
| S2 | Genuine phone, events inside confirmed non-sign | 5 | 9 / 6 |
| S2 | Phone genuine-vs-non-sign separability (AUC) | 0.770 | 0.832 / 0.773 |
| System | Held-out signers, stitched (correct / wrong) | 135 / 242 | 261 / 348; 198 / 135 with calibrated gate (previous milestone) |

## 8. Proposed research commit (awaiting your approval)

**Scope:** everything uncommitted on `claude/s2-r3-eval-suite`, as one commit or split by topic.

| Area | Contents |
|---|---|
| Evaluation infrastructure | Suite v03 + freeze; data split; N0, negative, held-out-DEV and Sem-Lex extractors; held-out end-to-end benchmark; event-separation research decoder; span port; their tests |
| Research trainers and configs | S2-R3 trainer + `s2_r3_train_{01,02}.json`; WORD robustness / Sem-Lex trainer |
| Android | WORD v2 debug package + shadow mode + parity test; the main-source change is the default-preserving spec parameter |
| Reports and probes | Four audit reports plus this one; all probe scripts and their JSON outputs |
| Context | Progress-tracker entries (insert-only) and feature-schema registry rows |

**Not committed:** trained models and raw data, which stay in the evidence root by hash; `android/local.properties` and `android/gradle.properties` (gitignored; the worktree copy holds no credentials).

**Suggested message:**
> Add S2-R3/WORD research tracks, WORD v2 debug shadow package and held-out benchmarks.
> Frozen S2-R2, Gate-2 recognizer, decoder and release behaviour unchanged.

## 9. Next practical step

**One short capture session with the shadow APK:**
1. On-device parity test.
2. Design signer plus 1–2 other signers performing the protocol vocabulary (incl. HOME and TABLE) in isolated and hands-up continuous blocks, with `word_shadow_package` and `s2_exact_parity_capture` on.
3. 3–5 minutes per person of the five hands-visible non-sign behaviours.

One session gives three things at once:
- paired device evidence for WORD v2 (promotion decision);
- exact-parity observations for replaying every S2 candidate offline;
- the person-separated hands-visible negatives that S2-R3 needs next.

Review the recordings with the existing blinded boundary tool before any training uses them.
