# Phase 3 — DWPose echo-suppression validation (second subject, hard cases, on-device shadow)

Date: 2026-11-10 · Branch `jepjep-claude` · **nothing committed** · **no production behaviour changed**
Builds on [`DWPOSE_DUPLICATE_PROPOSAL_VALIDATION.md`](DWPOSE_DUPLICATE_PROPOSAL_VALIDATION.md). Evidence: `docs/hand_diagnostics_runs/phase3_2026-11-10/`, tools: `eval/hand_diagnostics/`.

## DECISION

| | |
|---|---|
| **Production echo suppression** | **NO-GO (not yet).** |
| **Shadow-only logging (default off)** | **GO** — implemented, tested, and the way to close the evidence gaps below. |
| **Why** | The relative support-ratio rule generalizes across two subjects and the mandatory hard cases (echo rejection 95.5–99.7 %, zero wrong-group drops), **but** it falsely dropped real hands in overlapping/crossing poses (up to 14.5 % of units offline, 26 % of frames on-device in one take), the evidence is 2 subjects with 1–4 takes per hard configuration, **no physical phone**, per-group ground truth for crossing/overlap is doubtful, and the effect on recognition inputs is unmeasured. Overlapping hands are common in real signs. |
| **What flips it to GO** | §9: pre-registered gates (more subjects, phone, landmark-level truth for overlapping poses, recognition A/B, shadow-log results on devices). |

## 0. Scope, honesty and limits
- **Subjects:** 2 people (subject 1 = the user; subject 2 = a second person who followed spoken instructions with their own left/right hands). Different appearance, clothing, background and lighting.
- **Devices:** host fp32 offline + the **emulator** app (webcam). **No physical phone, no timing claim of any kind** is made.
- **Ground truth:** the hand count/side each person was asked to produce, **verified by me from contact sheets at 3 time points per take** (all hand counts held). Configuration attributes (edge, no-arm, back-of-hand) are only partly verified, see §2.
- **Effective sample size:** frames inside a 7 s take are highly correlated. The unit of evidence is the **take** (1–4 per configuration per subject, §3.5), not the frame count.
- **Thresholds:** no production threshold exists. In every cross-subject result the threshold was learned on the *other* subject and applied unchanged; the app logs a fixed evaluation **grid** (0.3–0.7), never a chosen value.
- **Restrictions kept:** no production behaviour change, no IoU-only rule, no recognition change, no latency claim, no commit.

## 1. What was built (Task 3, shadow-only)
`HandEchoShadow.kt` (+13 JVM tests) and 3 lines in `Candidate01FrameAnalyzer.kt`:
- **OFF by default** (`-PhandEchoShadow=true` only; release BuildConfig hard-coded `false`; verified in the default debug build and the release BuildConfig).
- **Read-only:** never alters an observation, the overlay, the segmenter or the recognizer input; never removes a candidate; original candidate data untouched; every failure is swallowed (a diagnostic can never fault the analyzer).
- **Logs** per frame (`AppHearEcho`, numbers/flags only, no coordinates, ≤ 1500 lines per analyzer start): the raw per-group signals (support mean, points ≥ 0.30/0.10, presence, refiner handedness and slot-consistency, same-side body-wrist support and agreement), ratio, weaker side, ROI IoU, skeleton IoU, and a **bitmask of which grid values would have suppressed the weaker group** (rule: both observed ∧ ROI IoU ≥ 0.1 ∧ weak/strong support < grid value).
- **Existing counters preserved:** the 30 s `AppHearDetect` line still carries `hands[...]`, `render[...]`, stage timings, `faults=0` (checked in the shadow-enabled run).
- APK `artifacts/phase-3.3/apphear-echo-shadow-debug.apk` (SHA-256 `8abb7062cbc3208ef9aed36a66e3a4452271f49e461143041b5424427fa67bc7`), currently installed on the emulator only.

## 2. Data collected (Tasks 1 and 2) and how well each case was achieved
Sessions ran with host clean frames (offline probe) **and** the app's shadow log at the same moment (device/host clocks equal to the second); each take has a wall-clock window.

| Subject | Set | Takes | Device shadow coverage |
|---|---|---|---|
| 1 | core 12 poses (earlier session) | 12 | none (shadow did not exist yet) |
| 1 | hard 9 + redo of 3 | 9 + 3 (3 superseded) | full |
| 2 | core 12 poses + re-take of 3 | 12 + 3 | full after re-take (first log hit its 1500-line cap) |
| 2 | hard 9 | 9 | full |

Verification notes (from contact sheets; **caveats on achieved configurations**):
| Case | Hand count | Configuration actually achieved |
|---|---|---|
| unequal pair, near right/far left and reverse | 2 ✓ (both subjects) | ✓ clearly different apparent sizes |
| image boundary | ✓ | subject 1: ✓ in `h_R_edge` (start) and in the redo; **subject 2: hands not cut by the edge — not achieved** |
| no visible forearm | ✓ | subject 1 single hand ✓ after redo, two-hand case only partly (second arm visible); **subject 2 ✓** |
| back of hand | ✓ | plausible, orientation not individually verified |
| overlapping hands, crossing | ✓ | achieved, but **both hand groups sit on one hand in the overlays → per-group truth doubtful** |
| fast movement, enter/leave | ✓ | dynamic; enter/leave has no per-frame truth and is excluded from scoring |
Three subject-1 takes (old `h_R_no_arm`, `h_both_L_edge`, `h_both_R_no_arm`) did not show what was asked and are excluded as superseded.

## 3. Signal comparison (Task 4): train on one subject, test on the other
Unit = a hand group in a frame where **both** groups are observed (otherwise nothing is duplicated); label real/echo from truth; 712 + 586 frames. Thresholds learned on the training subject only (max Youden J).

| Signal (rule) | Train→Test | T learned | Echo rejection | Genuine two-hand preservation | False suppression (all real) | Two-hand **frame** preservation |
|---|---|---:|---:|---:|---:|---:|
| group support (absolute) | S1→S2 | 0.261 | 68.8 % | 93.9 % | 4.9 % | 88.8 % |
| | S2→S1 | 0.381 | 99.7 % | 80.9 % | 13.8 % | 75.2 % |
| same-side body-wrist support (abs.) | S1→S2 | 0.297 | 96.5 % | 87.5 % | 9.9 % | 85.4 % |
| | S2→S1 | 0.212 | 67.3 % | 99.9 % | 0.1 % | 99.7 % |
| **relative support ratio** | S1→S2 | **0.527** | **95.5 %** | **100 %** | **0.0 %** | 100 % |
| | S2→S1 | **0.558** | **99.7 %** | **98.3 %** | **1.1 %** | 96.6 % |
| handedness corroboration (slot disagreement) | S1→S2 | n/a (0.5) | 94.5 % | 79.7 % | 16.6 % | 69.3 % |
| | S2→S1 | n/a | 82.1 % | 64.8 % | 29.5 % | 54.4 % |
| spatial overlap only (drops weaker group) | S1→S2 | 0.366 | 96.5 % | 90.6 % | 7.4 % | 81.2 % |
| | S2→S1 | 0.407 | 97.7 % | 83.5 % | 10.4 % | 67.0 % |
| ratio + corroborator (handedness ∨ wrist) | both | as ratio | identical to ratio | identical | identical | identical |

Findings:
1. **Only the relative ratio generalizes.** Absolute signals need different thresholds per subject (support 0.26 vs 0.38; body wrist 0.30 vs 0.21) and then fail badly on the other subject (e.g. support rejects 0 % of echoes in `no_arm`, or falsely drops 88 % of units in `crossing`). The ratio's two independently learned thresholds are close (0.527 / 0.558).
2. **Handedness is the worst signal** (false suppression 16.6–29.5 %). It must not be a decision input; adding it as a corroborator changed nothing here (it agreed in every case the ratio fired, including the overlap frames), so it adds no protection.
3. **Overlap alone is not acceptable** (false suppression 7.4–10.4 %, two-hand frame preservation 67–81 %), although this baseline was told which group to drop; overlap cannot even say that.

### 3.1 Ratio rule on the difficult configurations (held-out subject)
| Config | S1→S2 echo rej. / false sup. | S2→S1 echo rej. / false sup. |
|---|---|---|
| unequal pair (near/far) | – / **0 %** | – / **0 %** |
| boundary | – / 0 % | 100 % / 0 % |
| no visible arm | 100 % / 0 % | 100 % / 0 % |
| back of hand | 100 % / 0 % | 100 % / 0 % |
| distance (one hand) | **86.0 %** / 0 % | 99.3 % / 0 % |
| pose, motion | 100 %, 97.1 % / 0 % | 100 %, 100 % / 0 % |
| **crossing** | – / 0 % | – / **2.3 %** |
| **overlapping hands** | – / 0 % | – / **14.5 %** |
Caution on **unequal pairs**: a near and a far hand do not overlap spatially, so the rule (which requires ROI overlap) never engages; 0 % is real but is **not** evidence about a near hand that *covers* a far hand. Not tested.

### 3.2 Threshold-free picture (is there a gap?)
Echo ratio range: subject 1 0.17–0.52 (p50 0.29), subject 2 0.16–0.54 (p50 0.35). Genuine pairs: apart/touching 0.70–1.00 (clean gap), but **crossing 0.50–1.00 (S1) / 0.62–0.83 (S2)** and **overlapping 0.39–1.00 (S1) / 0.60–0.76 (S2)**. The clean single-subject gap (echo ≤ 0.40 vs genuine ≥ 0.87) **does not hold** with hard configurations and a second subject: echoes now reach 0.54 and genuine overlapping pairs go down to 0.39. The learned thresholds sit inside that overlap.

### 3.3 Sensitivity of the ratio rule on all data (grid, no value selected)
| T | echo rejection S1 / S2 | false suppression S1 / S2 | genuine overlap+crossing units flagged S1 / S2 |
|---|---|---|---|
| 0.4 | 92.2 / 66.3 % | 0.2 / 0.0 % | 1.4 / 0.0 % |
| 0.5 | 98.7 / 95.0 % | 0.6 / 0.0 % | 4.0 / 0.0 % |
| 0.6 | 99.7 / 96.5 % | 1.1 / 0.2 % | 8.1 / 0.8 % |
| 0.7 | 99.7 / 96.5 % | 1.5 / 4.5 % | 10.8 / 17.3 % |
A residual **3.5 % (S2) of echo units are never caught at any grid value** (ratio above 0.7 or non-overlapping). There is a usable window (≈ 0.5–0.6) but it is narrow and subject-dependent.

### 3.4 Take-level exposure
Genuine two-hand takes: **17 of 19 had no flagged frame**. The two that did are both subject 1 (S2-trained threshold): crossing 2/43 frames, overlapping hands 9/31 frames (29 %).

### 3.5 Takes per configuration (effective sample)
back-of-hand 2/2 (S1/S2), boundary 2/1, crossing 1/2, distance 4/3, motion 1/1, no-arm 2/2, overlap 1/1, pose 2/1, two-hand apart+touching 2/2, unequal pair 2/2. **Conclusions about "0 % false suppression" in a configuration rest on 2–4 takes.**

## 4. On-device (emulator) shadow decisions vs manually specified truth (Task 3)
Scored per frame where both groups were observed on the device; counterfactual only (nothing was suppressed).

| Grid value | Subject 1: echo dropped | Wrong (real) group dropped | Genuine pair dropped | Subject 2: echo dropped | Wrong group | Genuine pair dropped |
|---|---|---|---|---|---|---|
| 0.3 | 37.1 % | 0 | 0.0 % | 43.9 % | 0 | 0.0 % |
| 0.4 | 68.5 % | 0 | 0.9 % | 56.6 % | 0 | 0.0 % |
| **0.5** | **96.5 %** (138/143) | **0** | **4.4 %** (10/226) | **96.3 %** (182/189) | **0** | **0.0 %** (0/368) |
| 0.6 | 100 % | 0 | 6.2 % | 98.9 % | 0 | 0.3 % |
| 0.7 | 100 % | 0 | 8.0 % | 98.9 % | 0 | 10.6 % |
- **The real hand was never the one dropped (0 of 332 one-hand frames at every grid value):** the stronger group is always the real one.
- All of subject 1's genuine-pair drops at 0.5 are in **overlapping hands** (10 of 38 frames); subject 2's overlap take had none.
- **Parity:** device (emulator) vs offline host median ratio per scenario: median |Δ| = **0.012**, max 0.074 over 24 scenario/subject pairs. The offline analysis therefore transfers to the app's pipeline (emulator, not phone).
- Subject 1 core poses have no device log (collected before the shadow existed); subject 2 core coverage required a re-take.

## 5. False-positive analysis — where the rule can harm
1. **Overlapping and crossing hands (the blocker).** Weak/strong ratio genuinely drops to 0.39–0.62 there. In these frames both groups were seen on one hand, so the "genuine" label may itself be wrong (one group may truly be a duplicate); but the real signs that use overlapping hands would have one of their two hand slots removed. Handedness/wrist corroboration agreed with the drop, so **it cannot tell the two situations apart**. Landmark-level truth is needed.
2. **Near hand covering a far hand** (spatial overlap with very different support): untested.
3. **Hands cut by the frame edge** (support drops legitimately): only subject 1 achieved it; 1 take.
4. **Hand with no arm / back of hand:** passed (2–4 takes), not proof.
5. **Residual echoes (≈ 3.5–4 %):** suppression would not be complete.
6. **Recognition impact:** Recognition-v2 and the segmenter consume both slots; a wrongly dropped slot changes their input. No recognition-level measurement exists, and no recognition behaviour was changed here.

## 6. Updated root-cause assessment
- **Unchanged (now on two subjects):** the duplicate is an opposite-group echo produced by DWPose-t; weak (support ≈ 0.12–0.24 absolute, ≈ 0.17–0.54 of the real group); present in every one-hand pose; accepted by the refiner.
- **Revised:** the "wide gap" claim of the previous report is withdrawn (§3.2). Absolute support/body-wrist thresholds **do not transfer** between subjects; the **relative** ratio does, with a narrow margin. Handedness is not a usable decision input.
- **Still open:** why the model echoes; behaviour on a phone; overlap/crossing ground truth.

## 7. QA matrix (updated)
| Scenario | S1 | S2 | Device shadow |
|---|---|---|---|
| left only / right only, near+far, pointing | ✓ | ✓ | S2 ✓ |
| fast movement | ✓ | ✓ | S2 ✓ |
| enter/leave | ✓ (unscored) | ✓ (unscored) | S2 ✓ |
| two apart / touching | ✓ | ✓ | S2 ✓ |
| crossing | ✓ | ✓ (2 takes) | S2 ✓ |
| unequal pair near/far (both orders) | ✓ | ✓ | ✓ |
| hand at image boundary | ✓ | ✗ not achieved | S1 ✓ |
| hand with no visible arm | ✓ single; partial two-hand | ✓ | ✓ |
| back of hand | ✓ (orientation unverified) | ✓ (unverified) | ✓ |
| overlapping hands | ✓ | ✓ | ✓ |
| near hand covering a far hand | ✗ | ✗ | ✗ |
| third+ subject, other lighting/clothing/skin tone | ✗ | | |
| physical phone (Xiaomi) | ✗ | | |
| signing sequences / recognition A/B | ✗ | | |
| 236-class regression + full JVM suite | ✓ 447 pass (415 earlier + 19 diagnostics + 13 shadow) | | |

## 8. Remaining risks
R1 two subjects only; R2 emulator, not a phone (proposal behaviour should match, unverified); R3 overlapping/crossing false suppression and doubtful truth; R4 near-covers-far untested; R5 edge-cut hands under-tested; R6 recognition impact unmeasured; R7 3.5–4 % residual echoes; R8 shadow log is capped (1500 lines per start) so long sessions need re-starts; R9 `h_both_one_no_arm` and subject-2 boundary cases not as specified.

## 9. Recommended implementation decision
**NO-GO for production suppression. GO for a shadow-only collection campaign** with the existing flag.
**Proposed gates for a production GO (to be agreed *before* collecting, to avoid post-hoc choices):**
1. **Subjects/devices:** ≥ 8 subjects (varied skin tone, hair, glasses, sleeves, handedness) on ≥ 2 physical phones including the Xiaomi M2101K7AG, several lighting conditions.
2. **Pre-registered threshold procedure:** a single ratio threshold chosen by leave-one-subject-out on the shadow logs (no value picked from any one subject), reported with subject-level confidence intervals (resample subjects/takes, not frames).
3. **Pass criteria (proposed):** echo rejection ≥ 95 %; genuine two-hand false suppression ≤ 1 % overall and ≤ 3 % in overlapping/crossing, **measured with landmark-level truth for those poses**; **zero** wrong-group drops; near-covers-far and edge-cut configurations included.
4. **Recognition A/B:** offline replay of signing sequences (the 236-class suite plus recorded two-hand signs) with and without the drop; non-inferiority on sign accuracy, no regression on the existing suite.
5. **Rollout:** behind a default-off flag, shadow-first on devices, kill-switch; if the shadow log on a device shows any wrong-group drop or genuine-pair drop above the gate, stay off.
**If gates fail:** keep the duplicate (its cost is one extra refiner run per one-hand frame and a duplicate overlay), or consider a model-side fix (the echo comes from DWPose-t).

## 10. Regression and compliance
- JVM: **447 tests, 0 failures** (includes the 236-class `RecognitionAccuracyRegressionTest`, the commit gate, shadow-eval log, Phase 2 recovery); `:app:compileReleaseKotlin` and `:app:compileDebugAndroidTestKotlin` succeed.
- Python: **71 tests pass** (10 need numpy and run only in the investigation environment, where all 17 hand-diagnostics tests pass).
- Defaults: shadow, shadow-eval, profile flags off by default; commit gate unchanged (on); thresholds 0.55/0.75 unchanged; recognition, segmentation, overlay unchanged; existing diagnostic counters unchanged and present.
- No latency or phone claim is made anywhere in this report.

## Files
Added: `android/app/src/main/java/com/example/apphear/perceptionvnext/HandEchoShadow.kt`, `.../test/.../HandEchoShadowTest.kt`, `eval/hand_diagnostics/{analyze_generalization,shadow_join,run_session_with_shadow}.{py,sh}`,
`docs/hand_diagnostics_runs/phase3_2026-11-10/*`, `artifacts/phase-3.3/apphear-echo-shadow-debug.apk`, this report.
Modified: `android/app/build.gradle.kts` (flag `HAND_ECHO_SHADOW_ENABLED`, default false, release false), `Candidate01FrameAnalyzer.kt` (read-only shadow call + input view),
`eval/hand_diagnostics/capture_pose_session.py` (hard set, subject label, wall-clock windows), `tests/test_hand_diagnostics.py`, `docs/DWPOSE_DUPLICATE_PROPOSAL_VALIDATION.md` (status note), `context/progress-tracker.md`.
Scratch (outside repo, contains faces): all frames, probe outputs with landmark coordinates, contact sheets, venv.
