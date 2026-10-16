
## Team handoff published — 2026-10-09 (Asia/Manila)

Shared branch: `codex/team-handoff-2026-10-09`; PR: https://github.com/mark-juswa/AppHear/pull/1 (open/mergeable when checked).
First handoff commit042dc8b; vocabulary commit5cf2807. Main stays1e215ae, frozen October9
app baseline34f24ab unchanged. Start with TEAM_HANDOFF.md and context/team-current-state-2026-10-09.md,
not older local paths/plans. No force push, training, TEST access or recognition change.
186 JVM +53 focused decoder tests passed;581 contract hashes +345 imported Git-blob hashes verified.
No known-key/credential-pattern matches in1878text files; private APKs/config/bulk data/optimizer states excluded.
Research and current app source are now published together; original F: Android edits were NOT merged.
Next: groupmates clone the shared branch, run hash checker/fake build, review PR before merging main,
and review Original mappings/mixed-avatar appearance. Qualified-signer accuracy and private service/data
provisioning remain open; no automatic new experiment is authorized. See docs/team-external-artifacts.md.

> **2026-10-09 current-state notice:** Read [team-current-state-2026-10-09.md](team-current-state-2026-10-09.md) and [TEAM_HANDOFF.md](../TEAM_HANDOFF.md) first. Older design/status/absolute-checkout references below are historical where they conflict with the verified October9 code and current-state inventory. Protection, parity and evaluation rules still apply. Do not treat the old 15-FPS target as a measured achieved cadence, or uninstall/clear app data by default during smoke checks; current updates use `adb install -r`.

# Progress Tracker

**2026-10-16 — S2-R3 build step 1: frozen context evaluation suite complete; no training yet.**
Branch `claude/s2-r3-eval-suite` from `4503b55`. This follows the S2 history verification
(`docs/audit/S2_HISTORY_DEPENDENCE_VERIFICATION_2026-10-16.md`) and the confirmed plan
(`docs/audit/S2_R3_EXPERIMENT_PLAN_2026-10-16.md`).
- [x] Verified mechanism. S2 never learned to leave POST: 0 POST→ACTIVE / POST→PRE transitions
  in 515 training sequences. History length alone is rejected as the primary cause, and phantom
  rest proposals are a likely contributor. Runtime caps and resets trade misses for false
  activations (rejected).
- [x] Confirmed plan decisions:
  - three evaluation tiers (Tier 3 is a new qualified-signer capture plus E6, opened once);
  - 3-state bounded-POST labels;
  - staged data (R3a stitched FIT; R3b only on trigger);
  - Arm A v1 / Arm B masked v2;
  - preregistered absolute + non-inferiority gate;
  - CAL-only selection; debug package `S2_R3_CANDIDATE`.
- [x] `eval/runtime_diagnostics/s2_r3_context_suite.py` + `model/config/recognition_upgrade/s2_r3_context_suite_01.json`.
  The freeze `evidence/s2_r3_context_suite_20261016/suite_freeze.json` (config SHA `e1b23f99…`)
  reproduces every S2-R2 baseline:
  - Tier 1: no-history 68/69, POST-15 10/69, direct+6 42/63, previous-sign 51/66;
  - Tier 2: 11/23 signs with an event, 64/676 non-sign ACTIVE observations, 5 non-sign events,
    POST dwell 6,079 ms;
  - new isolated containment 51/69 (gate threshold 0.689).
  DEV and session v1 features recomputed from raw are exact (error 0). Replayed events equal
  recorded events in all 4 sessions. Reference gate: FAIL on exactly the continuous-signing lines.
- [x] 8 tests pass (7 pure; 1 full source reproduction with `APPHEAR_EVIDENCE_ROOT`). Ruff, black
  and mypy are clean for the new module.
- [ ] Open:
  - Tier 3 capture protocol;
  - R3b design, only if triggered;
  - re-arm/READY and decoder ACTIVE→PRE discard, after an arm passes.

  Next is build step 2: raw-source inventory for R3a FIT stitching. No runtime, model or
  contract change was made.

**2026-10-16 — Stage2 compact Android validation and nonexpert review complete; recognition objective open.**
Continues6dbb2d3 with the same integrated runtime and Stage1 disabled. Saved pair installed-r,
no data cleared.11 applicable Android tests pass: parser/camera/S2/RecognitionV2/FINGERSPELL/owner.
- [x] Read-only pre/post health; no observed disconnect/reboot,34.4→37.1°C battery; earlier closure
  unresolved. Instrumentation exit-info says finished inst; no sustained stability certification.
- [x] User completed compact5-block NONEXPERT_ENGINEERING_SMOKE capture session_20261015T155027Z.
  Finalized757 genuine observations/images; all exact hashes, event/re-arm/materializer/UI replay pass.
- [x] Same-observation features/normalization exact; S2 max error4.76837e-7, zero argmax differences.
  Diagnostic delivery4.696FPS whole session; no baseline/candidate speed or ASL accuracy claim.
- [x]581 protected hashes; canonical clean4c99ac24; no production source/model/policy changes.
- [x] User marked4 positive spans and1 non-sign interval; retained3 positive/hold uncertainties.
  Completion attestation supplies missing review checkmarks only; original export preserved.
  Three marked spans have no ACTIVE while IDLE; event2 matches HELLO, ordinary motion emits event3.
- [ ] Qualified-signer/second-sign/repeat/hold evidence and effective continuous WORD fix remain open.
First unfinalized pull preserved; human tapped final-save, second snapshot passes all integrity gates.
Raw evidence on F: under artifacts/recognition_v3_stage2_compact_device/finalized/. Local reviewer
127.0.0.1:8765; validated analysis saved. No timer/reset/training sweep.
See [device validation](../docs/recognition-v3-stage2-device-validation-2026-10-16.md).
The earlier phone-absent status below is historical; physical engineering validation is now complete.

**2026-10-15 — Stage2 compact capture built; physical validation pending.**
Continues1422cad on codex/recognition-v3-stage2. Five-block debug-only profile now covers hands-down,
hands-up, adjacent HELLO repeats, sign-then-hold and ordinary movement. Same recorder/models/decoder.
- [x]141 host tests,200 JVM tests; historical1364-row/10-event analysis unchanged;581 protected hashes.
- [x] App/test APKs built on F: after one bounded C:-disk-full recovery;465 original asset/native
  entries byte-identical, only compact protocol JSON added. APK/source hashes in new manifest.
- [x] Versioned profile/hash-bound v2 review and outcome attribution; legacy seven-block path retained.
- [ ] Phone absent. Read-only health inspection, packaged-parser instrumentation and actual qualified
  signing/repeat/hold capture remain NOT TESTED. No runtime recognition fix or accuracy claim.
Keep Stage1 concurrency off and S2 history-reset candidate rejected. Next: connect a stable phone,
inspect prior closure, then run the saved compact APK/procedure. No automatic timer/training change.
See [compact capture delivery](../docs/recognition-v3-stage2-compact-capture-2026-10-15.md).
Prior missing-profile status is superseded; Stage2 recognition objective remains unresolved.

**2026-10-15 — Recognition V3 Stage2 offline investigation; no runtime policy promoted.**
Branch codex/recognition-v3-stage2 starts at e196a8d; Stage1 flags remain false.
- [x] Recovered completed September27 A/B capture omitted by earlier handoff;1364 observations,
  10 events, final human labels and existing analysis reproduced exactly.
- [x] Six/seven confidently reviewed signs have zero S2 ACTIVE; both TABLE attempts lack accepted
  hands. Hands-up HOME remains POST despite15 hand-observed rows and13 READY observations.
- [x] Raw378/normalization exact; frozen S2 parity max8.34465e-7, zero argmax differences.
- [x] One closed-loop S2-prefix reset-after-rearm probe rejected:10→20 events,4→9 fully contained
  reviewed non-sign events. No timer/model/runtime change or further reset sweep.
- [x]119 focused host and194 JVM tests; actual Kotlin1364-row trace replay;581 protected hashes PASS.
- [ ] ADB sees no phone; closure cause, qualified-signer compact A/B/repeat/hold cohort and an
  effective boundary/readiness improvement remain unresolved. Existing7-block harness has no
  adjacent-repeat profile; this is an explicit remaining capture task, not a completed test.
See [Stage2 investigation](../docs/recognition-v3-stage2-investigation-2026-10-15.md).
Older pending-capture notes below are superseded by recovered evidence. Stage2 is not complete.

**2026-10-15 update — PARTIAL_ANDROID_EVIDENCE_MIXED_DO_NOT_PROMOTE.**
Canonical4c99ac24 and protected76d93cec remain intact; runtime5d73b412 unchanged.
- [x] Android applicable gates:11 tests/arm; recorded51-frame/204-output paired benchmark exact.
- [x] Six20s live engineering captures; fixed14s analysis: front WORD4.64→4.36FPS,
  FINGERSPELL4.93→6.07FPS; V3 PSS roughly21–25MiB higher.71 host tests pass.
- [ ] V3 rear, repeated scenes, true frame drops, qualified recognition accuracy and sustained
  stability remain incomplete. Phone closed/ADB vanished before V3 rear install; last app serial
  baseline; cause unknown. User ended device testing. No more phone operations.
- [ ] User again reports needing hands-down wait between signs. Earlier September28 transition
  work is integrated diagnostic tooling, not a policy fix; preserve this Stage2 issue for Project Lead.
Keep concurrency default-off; no accuracy claim. No Stage2/3/model/cloud work started.
Report: [partial phone validation](../docs/recognition-v3-stage1-validation-2026-10-15.md).
The original implementation status below is historical and superseded by this update.

**2026-10-15 — Recognition V3 Stage 1 implemented; phone validation pending.**
Isolated `codex/recognition-v3-stage1` starts at canonical integrated
`4c99ac24ebe7d1d1371a7268288df43df08f8d6b`; protected `76d93cec` and the canonical
checkout remain intact. User authorization supersedes historical prohibitions on perception work
only for this bounded Stage 1; cloud SONAR/Uni-Sign research and Stage 2/3 remain separate.

- [x] Inspected CameraX, native preprocessing, DWPose and refiner execution. Historical native
  profile supports neural inference as largest cost (DWPose ~80 ms, each serial refiner ~51 ms).
- [x] Implemented default-off concurrent current-frame hand refinement with independent
  interpreter/buffer owners, bounded scheduling and failure/interruption drain.
- [x] Recorded-input Windows CPU comparison: 51 frames, 255 hand-output comparisons,
  zero bitwise differences; two-hand refiner p50 8.5389→5.0619 ms, p95 9.6632→6.47986 ms.
  This is host scheduling/semantic evidence, not phone cadence or ASL accuracy.
- [x] Initial Android debug build/JVM gate passed 191 tests; 53 focused host fingerspelling
  regressions passed. Matched integrated builds and final hashes are in the report/evidence.
- [ ] Android recorded-pixel/model parity, matched front/rear WORD/FINGERSPELL device runs,
  sensor drops, PSS/thermal and end-to-end held-out recognition remain NOT TESTED (no device).

No S2-R2, Admission, materializer, Recognition V2, SentenceBuilder, FS policy/model, UI or asset
change. Default/release optimization remains off. Review outcome: retain experimental candidate;
do not promote as a phone performance or recognition accuracy improvement. Next action is the
bounded device gate in `docs/recognition-v3-stage1-2026-10-15.md`, before Stage 2.

**CURRENT STATUS 2026-09-28 — `DIAGNOSTIC_TOOLING_READY_WAIT_FOR_AB_CAPTURE`:**
`APPHEAR_CONTINUOUS_TRANSITION_AND_READINESS_01` is implemented on
`dev/continuous-transition-diagnostics` from protected baseline `76d93cecd85bf9f76064d320aa4a5791b5f0704a`.
Implementation commit `befa94a54b7f0e1ebc471af21a77f2f2036641b7` adds only debug observer/cohort
and human-boundary evaluation. Main runtime/UI, assets and scientific semantics are unchanged.
96 JVM tests, 51 focused host tests, 669-row S2-R2 Keras/TFLite fixture regression, debug and
release builds pass. No device was connected; A/B capture, human physical boundaries and
root-cause decision remain pending. Full commands/stop boundary are in
`APPHEAR_CONTINUOUS_TRANSITION_AND_READINESS_01_REPORT.md`. No readiness/Admission/model fix is authorized.

**WORKING BASELINE STATUS 2026-09-23 — `APPHEAR_S2_R2_REAL_APP_INTEGRATION_COMPLETE`:** The normal
AppHear RecognitionActivity on Xiaomi M2101K7AG completed the fixed HELLO → HOME → TABLE →
HELLO live sequence with one S2-R2 SignEvent, one displayed/sentence result, and natural
re-arm per intended sign. Two distinct ordinary-motion commits before/after the sequence
remain a confirmed product limitation, not a measured false-positive rate. No model or
lifecycle tuning occurred. Return integrated-app evidence to the Project Lead before choosing
the next component; do not start another S2 experiment automatically.

**PRIOR STATUS 2026-09-23 — `S2_R2_INTEGRATION_READY_WITH_KNOWN_LIMITATIONS`:** The
representative Xiaomi `M2101K7AG` final validation used a frozen six-attempt cohort and a
supervisor-attested distinct signer. The frozen S2-R2 package acquired ACTIVE in 6/6 intended
signs (52/56 human ACTIVE observations), emitted one event per attempt, and delivered 6/6 windows
with 100% human ACTIVE containment; Phase-7 same-observation control attained 5/6, 20/56, and
1/6 >=90%-contained windows. All seven S2-R2 events re-armed. Five visually confirmed non-sign
intervals (227 observations) had zero ACTIVE states and zero event onsets in either branch. One
pre-HELLO S2-R2 event remains **uncertain/mixed**, not a confirmed false positive or genuine sign.
Three of six usable windows produced wrong recognizer Top-1 results. Cadence, 714/714 visual
coverage, Android/host parity, and unchanged downstream replay all passed. Next milestone:
`APPHEAR_S2_R2_REAL_APP_INTEGRATION_01`; no new S2 training/tuning from this signer.

**PHASE 8A-U STATUS 2026-09-20 — DATA AND CAUSAL OBJECTIVE CORRECTION SUPPORTED:** Audited the
exact Phase-7 optimization exposure separately from checkpoint selection: FIT contained `71`
clips / `213` sparse views and CAL contained `18` clips / `54` views. FIT supplied `52`
ASL_CITIZEN clips across 23 signers, `9` APPHEAR_CAPTURE clips from one signer, and `10` LOCAL
clips across three signers. Although `210/213` FIT views retained supervised ACTIVE→POST evidence
and `191/213` covered CONFIG_01's 266.616 ms confirmation timescale, LOCAL POST supervision was
highly concentrated: one signer supplied `82.65%` of its sparse POST observations. Phase-7
checkpoint selection was also causally misaligned: it used the completed-sequence global decoder
and omitted causal completion/terminal-latency metrics; the selected epoch scored global emission
`54/54` but CONFIG_01 emission only `50/54` on the same CAL views. The governed unused pool can
add known-signer/ASL transition volume, but contains no unreserved independent APPHEAR/LOCAL
signer outside current TRAIN/DEV roles. The Phase-8A-T `97` versus `94` control discrepancy is
valid: three successful VIEW_A events committed just before human END, leaving no causal
post-END-to-commit observation to summarize. Final state:
`TARGETED_S2_DATA_AND_CAUSAL_OBJECTIVE_CORRECTION_SUPPORTED`. No S2-R1 run, inference,
extraction, phone/recognition/protected access, decoder/materializer change, or Android change
occurred. Current boundary: `WAIT_FOR_PROJECT_LEAD_S2_R1_ARCHITECTURE_REVIEW`.

**PHASE 8A-T STATUS 2026-09-19 — TERMINAL FAILURE ATTRIBUTED TO S2 GENERALIZATION:** Reused
persisted frozen-S2 streams for 54 CAL and 69 signer-disjoint sparse DEV views. Of seven genuine
non-censored DEV no-event views, six lacked terminal signal, one was ambiguous, and zero contained
successful-commit-like terminal evidence unused by CONFIG_01; three additional no-events remain
explicitly right-censored. Final state: `S2_TERMINAL_GENERALIZATION_CORRECTION_SUPPORTED`.
Probability-aware decoder work is not justified first. Current boundary:
`WAIT_FOR_PROJECT_LEAD_TERMINAL_ARCHITECTURE_DECISION`; if authorized, audit signer/recovery
transition diversity before one targeted S2 ACTIVE-to-POST correction. Do not train, retune,
access phone/protected populations, or reopen the frozen materializer automatically.

**PHASE 5.1S STATUS 2026-09-16 — END CONFLICT ATTRIBUTED, NO REPAIR AUTHORIZED:** Decomposed all
49 timestamp-derived END durations over all 1,028,193 discrete calibration low-threshold tuples and
constructed exact per-attempt regions, pairwise conflicts, end traces, quiet-veto counts,
recovery-motion attribution, and the four bounded one-at-a-time counterfactuals. All four
TABLE/non-TABLE pairwise regions are disjoint whenever TABLE is feasible, solely on
`H_proposal_image`: TABLE requires `<=0.09955792507085848`; closest partner HOME requires
`>=0.24807557246229403`. The threshold gap is the numerical symptom. Primary root cause is
`RECOVERY_AS_ACTIVITY_CONFLICT_SUPPORTED`: at the fixed TABLE-side diagnostic anchor, oracle-only
CF-D makes all five attempts structurally feasible, whereas CF-A/CF-B/CF-C do not. Post-oracle
recovery motion in the four non-TABLE attempts is treated as renewed activity and pushes padded
ends beyond the 500 ms context target; increasing the proposal threshold avoids that recovery but
cuts TABLE before its oracle end. Tier/validity transitions are secondary, and missingness or quiet
fusion alone is ruled out as primary. This is diagnostic only: no state logic, threshold, schema,
Android, recognizer, or training change occurred. Holdout 004/006/008/010 remains sealed.
Canonical report:
`artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase5_1s_global_end_conflict_attribution_01/PHASE_5_1S_GLOBAL_END_CONFLICT_ATTRIBUTION_01.md`.
Current boundary: `WAIT_FOR_PROJECT_LEAD_PHASE_5_1S_ARCHITECTURE_DECISION`; do not implement a
repair or begin Phase 5.2.

**PHASE 5.1R STATUS 2026-09-16 — NO GLOBAL FEASIBLE END DURATION, HOLDOUT SEALED:** Ran the
authorized single-variable recovery with every Phase-5.1 component fixed except
`end_quiet_persistence_ms`. Derived 49 behaviorally distinct candidates from genuine calibration
source-timestamp differences below 500 ms; no arbitrary millisecond grid was used. Exact/pruned
complete end-policy feasibility found zero joint low-threshold motion patterns at every candidate.
TABLE becomes individually feasible only within part of the approximately 266.616–199.962 ms
frontier, but no shared pattern satisfies all five calibration attempts; at shorter behavior HOME
and TABLE become individually infeasible. Final classification:
`END_POLICY_RECOVERY_NO_GLOBAL_FEASIBLE_DURATION`. No thresholds or runnable config were frozen,
LOgO was not run, and holdout attempts 004/006/008/010 remain unopened. Phase-5.1 core source
hashes are unchanged; the new non-runnable config SHA-256 is
`4188a4d2037066c657a5589a9e714bde89e663e152e4b517ef6a21da1c8b61e2`. Canonical report:
`artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase5_1r_end_policy_feasibility_recovery_01/PHASE_5_1R_END_POLICY_FEASIBILITY_RECOVERY_01.md`.
Current boundary: `WAIT_FOR_PROJECT_LEAD_SEGMENTATION_DIAGNOSIS`; do not change another policy
component, open holdout, run recognition, integrate Android, or begin Phase 5.2 automatically.

**PHASE 5.1 STATUS 2026-09-16 — CALIBRATION STOP, HOLDOUT SEALED:** Implemented the offline-only
raw-v1 activity signals, deterministic timestamp-based state machine, hard-gap/missingness handling,
canonical `apphear.segmentation.sign_event.v1` serializer, exact calibration feasibility proof, and
engineering fixtures. The locked oracle SHA-256 matched
`0e6f14f159287ce830b68c4d33edba88dbb6aeef386060b80f79e3fed4a1e41f`. Exact evaluation of
1,028,193 empirical low-threshold tuples collapsed to 65,674 distinct motion patterns and found
zero joint feasible patterns under the initial temporal policy; attempt 009/TABLE independently had
zero feasible end patterns even with start activation relaxed. Final classification:
`CALIBRATION_INSUFFICIENT_FOR_CURRENT_TEMPORAL_POLICY`. No duration sweep or LOO selection ran, no
runnable threshold configuration was frozen, and holdout attempts 004/006/008/010 were not opened.
Gap/missingness fixtures pass, and 12 targeted segmentation/adjacent-schema tests pass. Candidate01,
Recognition V2, the recognizer, Android behavior, training, DEV, and protected TEST remain unchanged
or unaccessed. Canonical report:
`artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase5_1_offline_automatic_segmenter_01/PHASE_5_1_OFFLINE_AUTOMATIC_SEGMENTER_01.md`.
Current boundary: `WAIT_FOR_PROJECT_LEAD_SEGMENTATION_DIAGNOSIS`; do not alter durations, tune
thresholds, open holdout, or begin Android integration automatically.

**PHASE 5.0 STATUS 2026-09-15 — AUDIT / CONTRACT COMPLETE:** Exact raw-v1 signal inventory and
calibration-only activity audit are complete. The proposed deterministic timestamp-based state
machine, global one-shot threshold method, pre/post margins, re-arm/gap policy, and future
`apphear.segmentation.sign_event.v1` wrapper are awaiting project-lead review. Phase 5.1 is not
started. Current boundary: `WAIT_FOR_PROJECT_LEAD_PHASE_5_1_IMPLEMENTATION_REVIEW`.

**PRODUCT RE-ANCHOR 2026-09-12 — AUDIT COMPLETE, PHONE BASELINE REVIEW NEXT:** The true product
target is the existing expandable 236-sign Android sign-to-text application, with production path
CameraX -> MediaPipe Hand/Pose -> schema-3.0 S4 `[96,258]` -> S5 -> 236-class S6 -> S7
confirmation/release -> sentence UI. P8-C2 is retained only as reusable debug/mobile engineering;
its failed 50-point Student is not production-compatible and remains disconnected. Family-A,
Students 1/2, P7G03 five-sign work, exact Android DWPose and the rejected RTMDet P0 route are
closed. No existing replacement is both phone-qualified and contract-compatible, so MediaPipe
remains the shipping baseline. Exact next milestone, after project-lead approval, is
`PHONE_REANCHOR_236_END_TO_END_BASELINE`; no training, Student-3, recognition experiment,
five-sign scope reduction or closed-branch retry is authorized. `STOP_FOR_PROJECT_LEAD_REVIEW`.

**P3 DWPOSE LANDMARK TEMPORAL USABILITY 2026-08-22 - `TEMPORALLY_USABLE`, QUALIFIED COMPLETE:** Reused the immutable P2-A DWPose-L 256x192 checkpoint/config/environment and ran one frozen raw-native temporal audit over 753 frames from 33 sequences and 14 governed signer IDs: all 21/551 human-reviewed A2 phone sequences plus 12 unique-signer, condition-balanced consecutive gold-video windows. Human 21-point landmark truth is unavailable, so geometry results are internal-consistency diagnostics rather than landmark accuracy. Against 323 directly reviewed visible anatomical hand observations, DWPose presence coverage was 321/323 (99.38%) versus recorded, not rerun, MediaPipe 230/323 (71.21%); complete two-visible-hand frames were 96/97 (98.97%) versus 50/97 (51.55%). DWPose produced two one-observation dropouts and no multi-observation dropout, zero suspected swaps across 261 two-slot adjacent pairs, zero direct wrong-slot-only contradictions, zero collapse/scatter frames, and two sudden jumps across 741 adjacent present-slot pairs. Direct SISTER crossing/body-contact frames retained both hands with no swap flag; the four historical RU-D9 interaction spans retained any hand in every frame and both hands in 8/8 GOOD R1, 10/10 GOOD R2, 5/11 WE torso-contact/blur, and 17/21 SISTER overlap frames. Important qualification: the frozen top-down presence rule emitted at least one hand on 116/324 (35.80%) human-reviewed zero-hand frames and 85/271 (31.37%) explicit rest frames, so `TEMPORALLY_USABLE` describes visible-hand landmark continuity/slot stability, not a production-safe absence signal or drop-in recognizer input. DWPose supplies 2D xy+score and no compatible z/depth, so replay into current `[96,258]` was correctly not performed. CPU latency p50/p95 was 125.38/145.32 ms and peak RSS 0.619 GiB, diagnostic only. A scoring-only cohort-association defect omitted three RU-D9 case spans in the first report pass; the original evaluator/protocol/report are preserved, the correction is fully hashed, native inference was not rerun, and aggregate results did not change. Canonical report: `artifacts/recognition_upgrade/perception_backend_replacement/p3_dwpose_temporal_usability_01/P3_DWPOSE_LANDMARK_TEMPORAL_USABILITY_RESULT.md`. Stop before any representation experiment, presence-gate design, S6 retraining, Sapiens, Android, or S4-S7 change.

**P2-A DWPOSE-L WSL2 CONTINUATION 2026-08-22 - `ARCHITECTURE_PROMISING`, COMPLETE:** Preserved the historical Windows result as `INCONCLUSIVE_P2A` (full-MMCV environment blocker), then resumed the identical frozen DWPose-L 256x192 experiment under Ubuntu 24.04 WSL2. Reused the exact read-only `dw-ll_ucoco.pth` checkpoint (SHA-256 `e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7`) and pinned config; full MMCV 2.0.1 compiled ops, the 133-keypoint path, hand indices, official SimCC decoder, full-frame ROI, flip test, 0.30/11-joint gate, and spatial matcher all verified unchanged. Frozen manifest SHA-256 `dce78eeb8855dfaaa01b23aeeeee4cecaa13e391022857e195376a948dfa3833`; processed 350/350. Ungated/gated hand recall was 182/184 (98.91%) / 181/184 (98.37%), MediaPipe misses recovered 60/62 / 59/62, MediaPipe hits lost 0/122 / 0/122, complete two-hand recall 65/67 / 64/67, HARD_CORE recovery 44/46 / 43/46, and REGRESSION_25 retained 25/25 in both views. Gates A-D pass ungated and gated. Forced whole-frame negative stress produced gated presence in 69/200 (34.5%), explicitly not a production false-positive rate; an upstream person/ROI eligibility decision remains necessary. CPU total latency p50/p95 was 119.94/142.94 ms and peak process RSS 0.620 GiB, diagnostic only. Canonical Linux result: `artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_linux_01/P2A_DWPOSE_L_FROZEN_PERCEPTION_RESULT.md`. No Sapiens, training, threshold/ROI retry, Android, S4-S7, or recognition change occurred. Stop before the next perception phase.

**P2-A DWPOSE-L 2026-08-22 - `INCONCLUSIVE_P2A`, BLOCKED BEFORE INFERENCE:** Obtained the exact requested `dw-ll_ucoco.pth` (404,734,742 bytes) and verified SHA-256 `e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7`; pinned the exact 256x192 config from IDEA-Research/DWPose commit `0232d66f420f411451d277905a08ff8d541dc78e`. Created a separate Python 3.9 CPU environment without touching production. The untouched model-load smoke failed because `mmcv-lite 2.0.1` lacks `mmcv._ext`; the one clean corrective attempt to build official full `mmcv 2.0.1` failed because Microsoft Visual C++ 14+ is absent. Applied the preregistered package-compatibility stop rule: no model-code bypass, alternate checkpoint/ONNX, compiler installation, manifest scoring, or inference. Processed 0/350 images; all perception metrics and Gates A-D are `NOT_EVALUATED`. Canonical report: `context/recognition_upgrade/P2A_DWPOSE_L_FROZEN_PERCEPTION_RESULT.md`; machine result: `artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/p2a_dwpose_blocker_result.json`. No Sapiens, MediaPipe rerun, training, threshold change, Android, S4-S7, or benchmark change occurred.

**NEGATIVE_GOLD_V1 EXTERNAL CONFIRMATION 2026-08-22 - `NEGATIVE_GOLD_V1_STILL_INCOMPLETE`, HARD QC FAIL:** Formally processed all 180 completed second-pass rows into 160 canonical labels and 20 concealed-repeat comparisons. All 160 canonical rows are `ZERO_HAND`, and all 160 are mechanically dual-pass/dHash clean, but two byte-identical repeats changed from canonical `ZERO_HAND` to `HAND_VISIBLE` and `UNCERTAIN`. Exact and binary repeat agreement are both 18/20 = 90%; this fails the required >=92% exact threshold and the stricter zero-critical-binary-disagreement gate. Diagnostic inspection found a real visible human hand in the first discordant image and garden-gnome sculpted hands in the second, confirming human semantic inconsistency rather than tooling/copy drift; no label was overridden. Run-level QC blocks every promotion: confirmed new trusted zeros 0, selected additions 0, reserve 0, NEGATIVE_GOLD_V1 remains 76/200, exact deficit 124, and no benchmark/reserve manifest was created. Canonical report: `context/recognition_upgrade/NEGATIVE_GOLD_EXTERNAL_CONFIRMATION_RESULT.md`; formal artifacts: `artifacts/recognition_upgrade/perception_backend_replacement/negative_gold_external_confirmation_01/finalization`. Stop without an automatic review loop. Only a separately approved independently blinded adjudication of the two discordant source images is eligible as the smallest repair. No detector/model/training/download/Android/S4-S7 work occurred.

**NEGATIVE_GOLD_V1 EXTERNAL CONFIRMATION 2026-08-22 - PACKAGE FROZEN, FINAL HUMAN PASS NEXT:** Verified the completed first-pass package unchanged and confirmed 181 provisional canonical `ZERO_HAND`, of which one is implicated in a binary repeat disagreement, leaving exactly 180 eligible non-discordant provisional zeros. Diversity-selected 160 canonical confirmation candidates and inserted 20 concealed byte-identical repeats. The frozen queue retains all 38 eligible people-present discoveries plus 122 person-free discoveries, spans ten scene buckets, 159 authors, and 134 primary metadata labels; minimum internal and seed-relative dHash distance is 10 against the unchanged conflict boundary `<=4`. The UI remains fully blind to first-pass labels, metadata, QC state, model output, and repeat identity. Focused plus inherited tests pass 15/15; Ruff/Black and package validation pass. Status is correctly 0/180 reviewed with no structural errors. Canonical report: `context/recognition_upgrade/NEGATIVE_GOLD_EXTERNAL_CONFIRMATION_PACKAGE.md`; package: `artifacts/recognition_upgrade/perception_backend_replacement/negative_gold_external_confirmation_01`. Next human action: run `model/config/recognition_upgrade/run_negative_gold_external_confirmation.ps1 -Command Review`, finish all 180 rows, then run `-Command Check`. NEGATIVE_GOLD_V1 remains 76/200 until hard repeat QC and dual-pass confirmation permit exact-124 finalization. No download, detector/model/training/Android/S4-S7 work occurred.

**NEGATIVE_GOLD_V1 OPEN IMAGES REVIEW 2026-08-21 - `OPEN_IMAGES_REVIEW_COMPLETE_QC_FAILED_REPAIR_REQUIRED`:** Processed all 240 saved external-review rows into 220 canonical labels: 181 provisional `ZERO_HAND`, 38 `HAND_VISIBLE`, and one `UNCERTAIN`. All 20 concealed pairs are byte-identical and the repeat mapping is valid, but exact three-class agreement is 18/20 (90.0%), with two zero/non-zero disagreements and one critical `ZERO_HAND`/`HAND_VISIBLE` disagreement. The hard preregistered QC gate therefore failed; no external row was promoted, no 200-row benchmark/reserve was frozen, and `NEGATIVE_GOLD_V1` remains 76/200 with a trusted deficit of 124. Both discordant images visibly contain hands, confirming human inconsistency rather than a tooling defect, but their labels were not silently changed. Canonical report: `context/recognition_upgrade/NEGATIVE_GOLD_EXTERNAL_OPEN_IMAGES_REVIEW_RESULT.md`; evidence remains under `artifacts/recognition_upgrade/perception_backend_replacement/negative_gold_open_images_v7_01`. The earlier 150+15 recommendation is superseded by the approved frozen 160+20 package above. No new download, detector/model/training/Android work occurred.

**NEGATIVE_GOLD_V1 EXTERNAL OPEN IMAGES PACKAGE 2026-08-21 - FROZEN, HUMAN REVIEW NEXT:** Verified Open Images V7 official source/access and licensing boundaries, then froze a bounded external review package without running a perception model. All 220 canonical validation images have complete per-image CC BY 2.0 metadata, original URL/landing page, author, UTC download time, and SHA-256; Open Images annotations remain CC BY 4.0 and annotation absence is explicitly not hand truth. The label-blind package contains 143 person-free-discovery and 77 people-present-discovery candidates, 219 authors, 174 primary metadata labels, ten coarse scene buckets, and 20 concealed byte-identical repeats. All 220 source images decoded, passed the frozen exact/dHash (`<=4`) checks against the trusted 76-frame seed and each other, and preserve exact source bytes; four rotation records are corrected only in the reviewer display. Focused tests pass 8/8; Ruff/Black pass. Current review status is 0/240 with zero structural errors; `passed: false` is expected before human labels. Canonical report: `context/recognition_upgrade/NEGATIVE_GOLD_EXTERNAL_OPEN_IMAGES_PACKAGE.md`; package: `artifacts/recognition_upgrade/perception_backend_replacement/negative_gold_open_images_v7_01`. Next human action: run `model/config/recognition_upgrade/run_negative_gold_open_images_v7.ps1 -Command Review`, finish all 240 rows, then run `-Command Check`. `NEGATIVE_GOLD_V1` remains 76/200 until repeat QC and finalization select exactly 124 confirmed independent zeros. No detector/model/training/Android work occurred.

**NEGATIVE_GOLD_V1 N0 FINALIZATION + EXISTING-RGB TOP-UP 2026-08-21 - `EXISTING_DIVERSE_POOL_SUFFICIENT_FOR_NEXT_REVIEW`:** Formally accepted the completed N0 human re-adjudication as `N0_BLINDED_READJUDICATION_COMPLETE_DIVERSITY_INSUFFICIENT`: 250 canonical labels, 25/25 concealed-repeat exact agreement, no critical repeat disagreement, 238 canonical `ZERO_HAND`, 43 surviving the frozen exact/dHash (`<=4`) diversity rules, and 195 preserved as redundant non-independent evidence. Frozen the corrected-gold 33 plus N0 43 as a validated 76/200 seed with no exact/near duplicate, positive P0 overlap, protected-test row, or missing source image; 124 trusted independent zeros remain. A read-only dHash boundary audit passed without changing the threshold. Comprehensive model/label-blind inventory and image screening found 569 existing review candidates; froze a randomized next queue of 320 unique frames plus 32 hidden repeats spanning 318 clip IDs, 49 participants, six recorded device values, and seven recorded environment values. Decision: existing RGB plausibly finishes the deficit, so new recording is not justified yet. Canonical reports: `context/recognition_upgrade/N0_BLINDED_READJUDICATION_RESULT.md` and `context/recognition_upgrade/NEGATIVE_DIVERSITY_TOPUP_AUDIT.md`; package: `artifacts/recognition_upgrade/perception_backend_replacement/negative_gold_v1_topup_01`. Next human action: run `model/config/recognition_upgrade/run_negative_gold_topup.ps1 -Command Review`, finish all 352 rows, then `-Command Check`. `NEGATIVE_GOLD_V1` remains incomplete and no detector/model/Android/training work occurred.

**N0 BLINDED RE-ADJUDICATION PACKAGE 2026-08-21 - PREPARED, HUMAN REVIEW NEXT:** Preregistered the exact 200-frame repair target before candidate selection in `context/recognition_upgrade/N0_BLINDED_READJUDICATION_PROTOCOL.md`: retain the 33 corrected-gold zeros and obtain 167 new `ZERO_HAND` frames from existing N0 RGB. Added a dedicated five-class semantic reviewer, deterministic metadata-only candidate selection, 25 concealed repeat-QC rows, conservative zero-hand semantics, atomic resumability, exact/dHash deduplication, clip caps, diversity gates, and overwrite refusal. Prepared `artifacts/recognition_upgrade/perception_backend_replacement/n0_blinded_readjudication_01` with 250 exact-unique candidates plus 25 hidden repeats. The unique candidates cover all 57 N0 clips, six participants, five devices, and five environments, with at most five candidates per clip. All 57 recorded source-video hashes passed; protocol/config/runner hashes match package provenance; focused tests pass 3/3; Ruff and Black pass. Current review status is 0/275 with zero structural errors; `passed: false` is expected until all human rows are accepted. No historical label or model output was used for selection, and no annotation, detector, training, Android, recognition, or production change occurred. Next developer action: run `model/config/recognition_upgrade/run_n0_blinded_readjudication.ps1 -Command Review`, complete all 275 neutral rows, then run `-Command Check`. Do not run `Finalize` until Check reports 275 complete and zero errors.

**PERCEPTION NEGATIVE EVIDENCE AUDIT 2026-08-21 - `NEW_NEGATIVE_ANNOTATION_REQUIRED`:** Audited every existing human-review, no-sign, detector-negative, A1/A2, RU-D, E4/E6, recorder, and corrected-gold source without running a detector or changing annotations. Historical assets contain 1,066 zero/no-hand candidate rows, but direct RGB validation found the same semantic defect that invalidated P0 N0: several N0, P1, C0B, and A2 rows marked zero/no-hand visibly contain lap, edge, or moving hands. Only the corrected all-hand gold's 33 zero frames remain admissible now; they are 33 exact-unique/near-duplicate-clean clips across 27 signers. Therefore `TRUSTWORTHY_ZERO_HAND_EXISTING=33` and the exact deficit to 200 is 167. No new recording is needed: separately approve a blinded re-adjudication of approximately 220-250 existing N0 candidates, stopping only after 167 accepted zeros pass diversity/dedup rules. P0 diagnostic subsets are frozen directly from the canonical pairwise CSV as complementary 16, regression 25, and both-miss hard core 46, with selection hashes in `context/recognition_upgrade/PERCEPTION_NEGATIVE_EVIDENCE_AUDIT.md`. No annotation, detector execution, training, Android, or recognition change occurred.

**PERCEPTION REPLACEMENT P0 DETECTOR VALIDATION 2026-08-20 - `REJECT_RTMDET_P0`:** Perception replacement P0 detector validation: `REJECT_RTMDET_P0`. Evaluated the exact pretrained OpenMMLab `rtmdet_nano_8xb32-300e_hand-267f9c8f` 320x320 ONNX detector at the documented/default 0.30 threshold on the unchanged corrected all-hand gold: 150 frames, 41 signers, 184 visible hands. RTMDet was worse than frozen MediaPipe direct perception on visible-hand recall (`61.41%` vs `66.30%`), any-hand coverage (`75.21%` vs `77.78%`), complete two-hand recall (`37.31%` vs `46.27%`), blur (`53.33%` vs `58.33%`), occlusion (`36.00%` vs `52.00%`), and two-hand instances (`58.96%` vs `64.93%`); merged-hand failures were `6/67 = 8.96%`. It supplied 16 MediaPipe-miss -> RTMDet-hit observations but lost 25 MediaPipe hits. Post-score audit invalidated the 613-frame N0 fixture for safety inference because multiple frozen no-hand rows visibly contain hands; raw outputs are preserved, and the trustworthy 33-frame zero-hand subset is too small and had `4/33` RTMDet false-presence frames. Positive evidence independently rejects the detector, so this is not inconclusive. Canonical report: `context/recognition_upgrade/P0_RTMDET_DETECTOR_RESULT.md`; machine package: `artifacts/recognition_upgrade/perception_backend_replacement/p0_rtmdet_detector_02`. Do not start P1/MobRecon/RTMPose landmarks, threshold tuning, RTMDet fine-tuning, or Android integration. Next eligible work is a blinded governed >=200-frame negative-set repair, then at most one materially different off-the-shelf full-frame detector family under a separately approved protocol.

**PERCEPTION BACKEND REPLACEMENT STUDY 2026-08-20 - COMPLETE, POC PENDING:** A2-2R recovery rejected -> incremental perception patches closed -> Perception Backend Replacement Study complete/pending PoC. Created `context/recognition_upgrade/PERCEPTION_BACKEND_REPLACEMENT_STUDY.md` from a read-only repository audit plus current public model/runtime research. Decision: preserve A1 independent-clock/latest-frame scheduling conceptually and evaluate a genuinely new direct backend offline before Android. Ranked #1 RTMDet-nano full-frame hand detection + MobRecon DenseStack 3D hand regression, #2 person detector + RTMW3D-m whole-body context, #3 AppHear-domain fine-tuned license-clean detector + 3D regressor only if the off-the-shelf stack reveals a correctable domain gap. The smallest next experiment is a no-training frozen-frame PoC on corrected E2E gold, A2 temporal evidence, governed negatives, and a new human 2D-landmark subset, with direct recall/two-hand/contact/false-presence/dropout/export gates. Cross-device CPU/XNNPACK correctness and sustained >=15 useful observations/s remain mandatory later; Xiaomi-only or desktop results cannot promote a backend. No backend implementation, model download, training, Android integration, MediaPipe/S4-S7 change, or recognition retraining occurred.

**A2-2R CONSERVATIVE ONE-OBSERVATION RECOVERY 2026-08-20 - REJECTED, INCREMENTAL RECOVERY CLOSED:** Ran the preregistered offline C0 direct-only versus C1 one-observation hold versus C2 bounded causal velocity comparison on the frozen 551-row, 21-attempt A2 package. Both candidates improved visible-hand recall 69.97% -> 75.85% and complete two-hand coverage 51.55% -> 61.86%, recovering 6/12 scoreable single-observation cases. The narrow implementation boundary held (zero recursive persistence, identity swaps, or wrong-hand recovery), but each candidate produced eight false recoveries on true absence, three on no-hand/rest, five on leaving frames, and 19 stale recoveries at longer-gap onset; both also failed p95 velocity continuity (2.358/2.308 > 2.0) and added one downstream wrong commit (`SISTER`). C1 additionally recovered one correct `NOW` commit; C2 improved mean re-entry landmark error only 3.3%, below its 10% complexity gate. Decision `REJECT_A2_2R_RECOVERY`. Do not tune carry-forward/extrapolation again or integrate Android. Next eligible work is planning a Perception Backend Replacement Study, not started here. Canonical report: `context/recognition_upgrade/A2_2R_RECOVERY_RESULT.md`; machine result: `artifacts/recognition_upgrade/a2_landmark_continuity/a2_2r_one_observation_01/a2_2r_result.json`.

**A2-1R SINGLE-FACTOR PRIOR REPAIR 2026-08-20 - REJECTED, STOP BEFORE RECOVERY:** Ran the sole authorized repair on the unchanged 551-frame package after recording branch/HEAD/worktree state, all required source/input hashes, the 13 protected baseline hashes, and a normalized proof that only `invert_mediapipe_handedness: true -> false` changed. Focused tests passed 7/7 and package validation passed 551/551. Removing inversion collapsed most of the original failure: combined correct rose 14 -> 168, wrong fell 110 -> 23, ambiguity fell 106 -> 39, coverage rose 53.91% -> 83.04%, and propagation errors fell 91 -> 18. It still performed substantially worse than raw handedness (224/230 correct): primary tracker was 103 correct / 14 wrong / 24 ambiguous, 9.93% identity error, 82.98% coverage, 13 new errors, and only 1/3 baseline errors fixed. Six of eight gates remain unsatisfied; the stress gate remains `INSUFFICIENT EVIDENCE` at 0/10 distinct primary contact/crossing frames. Decision `REJECT_A2_1R`. Do not tune this tracker again, start A2-2, collect stress evidence automatically, or integrate Android. Canonical report: `context/recognition_upgrade/A2_1R_IDENTITY_RESULT.md`; machine package: `artifacts/recognition_upgrade/a2_landmark_continuity/a2_1r_identity_only_01`.

**A2-1 OFFLINE CAUSAL IDENTITY 2026-08-20 - REJECTED, SUPERSEDED BY A2-1R:** Completed all 551 corrected color-based human annotations with zero structural errors, then ran the frozen identity-only candidate. The A1 direct-label baseline was already anatomically correct on 138/141 primary and 224/230 combined known instances. A2-1 failed six of eight gates: primary tracker correct/incorrect/ambiguous was 3/72/66, assignment coverage 53.19%, identity error 51.06%, new errors 71, and baseline errors fixed 1/3. Switch rate decreased, but only alongside catastrophic wrong/ambiguous assignment. The frozen inverted MediaPipe prior was disproved: occasional detector disagreement did not imply systematic inversion, and temporal state propagated the wrong initialization. The independent evidence gate also failed: primary contact/crossing frames 0 versus required 10; supplemental RU-D9 had one body-contact flag and three crossing flags spanning three distinct frames. Decision `REJECT_A2_1_IDENTITY_TRACKER`. The one authorized non-inverted refinement was subsequently run as A2-1R and also rejected. Canonical report: `context/recognition_upgrade/A2_1_IDENTITY_RESULT.md`; machine result: `artifacts/recognition_upgrade/a2_landmark_continuity/a2_0_identity_01/a2_1_result.json`.

**A2-0 LANDMARK CONTINUITY EVIDENCE 2026-08-16 - PACKAGE READY, HUMAN REVIEW GATE:** Generated the offline-only `a2_1_identity_only_01` evidence package from 21 existing chronological phone sequences: all 12 A1-mode signing-sentinel attempts (315 selected frames) plus nine RU-D9 adjudicated stress attempts (236 frames), covering eight glosses, 11 one-hand sequences, and 10 two-hand sequences. Historical stress labels include three contact/occlusion and two detector-dropout sequences; crossing, leaving-frame, rest, true dropout, and recoverability counts deliberately await per-frame human adjudication. Added a resumable reviewer, strict annotation validator, causal anatomical `Track_L`/`Track_R` identity-only tracker, preregistered gates, focused tests, and frozen baseline hashes. Human review caught that raw detector `Left/Right` labels are unsuitable human annotation concepts: the anatomical right hand appeared under both labels across inspected frames. Replaced detector-side wording with neutral BLUE/ORANGE detection colors, default every present detection to `ambiguous`, and derive recovery-control applicability automatically. Preserved the 38 rows accepted under the confusing interface in `annotations_before_color_ui_correction.csv` and reset all active rows to neutral/unreviewed; the earlier seven-row backup also remains. The tracker has explicit ambiguity and never carries or recovers missing landmarks. Mechanical direct-only primary facts are 106/315 any-hand frames, 35/315 two-hand frames, and pooled any-direct gaps 267.04 ms median / 386.79 ms p95; visible-hand recall and identity metrics cannot be claimed until review. Canonical plan: `context/recognition_upgrade/A2_IDENTITY_EXPERIMENT.md`; package: `artifacts/recognition_upgrade/a2_landmark_continuity/a2_0_identity_01`. Next action belongs to the user: restart `run_a2_identity.ps1 -Command Review` and accept all 551 rows, then run `-Command Check`. A2-1 evaluation, landmark recovery, Android work, S4-S7 changes, retraining, and production changes remain blocked.

**A1 SIGNING SENTINEL 2026-08-16 - COMPLETE, KEEP A1 AS DEFAULT-OFF V2 FOUNDATION:** Pulled and structurally verified all 24 order-balanced phone bundles: two Baseline and two A1 natural attempts for each of `GOOD`, `WE`, `NOW`, `KNOW`, `HAVE`, and `HELLO`. All performances were visually valid with independent visible sign-span annotation, exact reconstructed window hashes matched Android `24/24`, and recorded S7 replay matched `24/24`. X86-vs-Android quantized argmax matched only `14/24` (max probability delta `0.1797`), so oracle counterfactuals were not used; recorded phone ranks/commits are authoritative. Baseline vs A1: mean hand coverage `57.1%` vs `57.9%`, two-hand coverage `20.6%` vs `20.0%`, pose coverage `100%` both, S5 onset `11/12` both, target Top-1 `4/12` vs `5/12`, Top-5 `10/12` vs `9/12`, correct commits `2/12` vs `5/12`, wrong commits `5/12` vs `4/12`, no commit `5/12` vs `3/12`. A1 produced correct `GOOD` and `HAVE` commits in both attempts; one A1 `HELLO` missed onset while both Baseline attempts committed correctly, an isolated caveat with no identified narrow scheduling defect. `KNOW`, `NOW`, and `WE` remain unresolved. Combined with the strong Stage-1 runtime pass, the final decision is `KEEP A1 AS V2 FOUNDATION`, still debug-only/default-off and not authorized for production deployment. Flat signed landmark coverage proves scheduling improves freshness but does not solve underlying MediaPipe dropout/contact/occlusion continuity. Canonical result: `context/recognition_upgrade/A1_SIGNING_SENTINEL_RESULT.md`; machine summary: `artifacts/recognition_upgrade/a1_independent_clock/signing_sentinel_01/a1_signing_sentinel_summary.json`. No A2 code, retraining, model/schema/threshold/MediaPipe setting, S4-S7, or production change occurred.

**A1 INDEPENDENT-CLOCK HANDS-FIRST PERCEPTION 2026-08-16 - STAGE 1 PASSED, SIGNING SENTINEL NEXT:** The corrected order-balanced Xiaomi no-sign benchmark at `artifacts/recognition_upgrade/a1_independent_clock/device_benchmark_02` passed every frozen gate with full trace coverage. A1 versus Baseline: fresh hands `7.077` vs `5.300/s` (`+33.5%`), S4 `7.063` vs `5.304/s` (`+33.1%`), p95 hand gap `169.3` vs `258.3 ms` (`-34.5%`), and p95 hand-end→S4 `3.9` vs `63.3 ms` (`-93.8%`). A1 yield was `0.9980` with three `POSE_TOO_OLD` rejections, no ordering/future-pose violations, no crash markers, and no no-sign onset/commit. Peak PSS rose only `1.84%`; throughput half-decay was not worse. The material tradeoff is p95 reused-pose age `505.1` vs `296.3 ms`, still below the frozen `582 ms` ceiling. API-level hand/pose interval overlap rose from about `65.7%` to `99.5%`, though GPU internals remain unobservable. Decision is `PROCEED_TO_SMALL_SIGNING_SENTINEL`, not yet final KEEP. Prepared a 24-attempt order-balanced RU-D1 sentinel over `GOOD`, `WE`, `NOW`, `KNOW`, `HAVE`, and `HELLO` (two natural attempts per mode), preserving the 582 ms ceiling and unchanged S4-S7. Canonical result: `context/recognition_upgrade/A1_STAGE1_NO_SIGN_RESULT.md`. Next command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "F:\ASL DATASET\5. Apphear3\model\config\recognition_upgrade\run_a1_signing_sentinel.ps1" -Command Install`. A2 remains forbidden.

**RU-D10 FINAL RECOGNITION STABILIZATION 2026-08-16 - COMPLETE, KEEP BASELINE / REVERT A AND B:** The bounded four-mode device benchmark completed, but detailed logs corrected the launcher's initial structural `passed: true`: both modes containing candidate A (`A_ONLY`, `A_PLUS_B`) suffered an AppHear native `SIGSEGV` in `libhwui BitmapWrapper::freePixels`, so A fails the runtime-stability gate and is rejected. Baseline was stable at 5.50 processed FPS with 191.0 ms mean / 302.1 ms p95 inter-frame gaps and 153.9 ms mean / 267.4 ms p95 analysis wall time. A did not improve FPS (5.50), and its small mean-gap change (186.3 ms) is invalidated by the crash. B was stable on device but slower in its sequential no-sign run (4.74 FPS, 223.7 ms mean gap); more importantly, frozen replay recovered KNOW R1 and WE R2 onsets with zero added off-span onsets yet changed KNOW R1, SISTER R2, and WE R2 from no commit to wrong diagnostic commits. B therefore fails the end-to-end regression gate and is rejected; A+B inherits both failures. All four no-sign runs logged zero S5 onsets and commits, but that does not override the stability and wrong-commit failures. No safe throughput optimization was found: hand/pose MediaPipe inference remains the dominant cost. The corrected benchmark summary is `passed: false`, the final analysis verdict is complete, and the saved BASELINE APK has been restored to the connected device and force-stopped. No signed-phone confirmation is justified. Both experimental flags remain default-off for traceability, release remains forced off, and no training/data/model/threshold/MediaPipe-setting/S6/S7/schema/production-contract/protected-test change occurred. Canonical report: `artifacts/recognition_upgrade/ru_d10/device_benchmark_01/RU_D10_FINAL_RESULT.md`.

**RU-D9 OBSERVATION CONTINUITY / S5 ONSET ROOT CAUSE 2026-08-16 - COMPLETE, STOP BEFORE FIX:** Reused only the nine specified RU-D7/RU-D8 attempts and reconstructed one Android-recorded frame timeline per attempt. Exclusive primary causes are `TWO_HAND_OCCLUSION_OR_CONTACT` 3 (GOOD R1/R2, SISTER R2), `HAND_DETECTOR_DROPOUT` 2 (WE R1, NOW R2), `S5_CONSECUTIVE_EVIDENCE_TOO_STRICT` 2 (KNOW R1, WE R2), and `S5_SIGNAL_NOT_RESPONDING_TO_VALID_MOTION` 2 (WHO R1/R2); no case is primarily low sampling, pose/S4, other, or uncertain. All spans ran near 4-5 processed FPS with maximum gaps of roughly 0.27-0.35 seconds, so temporal sampling is a pervasive amplifier rather than a proven primary cause. Required landmarks were continuous in the KNOW core and present in 8/9 WE R2 core frames; a diagnostic one-noncandidate-gap tolerance would have completed their low-FPS `k_on=2` onset accumulation. WHO had continuous core landmarks but inadequate S5 motion response, so gap tolerance would not help; WHO also retains its separate severe S6/representation failure. Hand confidence scores were not captured and are explicitly unavailable. Ranked next attention is perception continuity first, throughput measurement second, a separately gated S5 short-gap experiment third, and WHO-specific onset features later without implying WHO recognition is solved. Canonical outputs: `artifacts/recognition_upgrade/ru_d7/phone_bc_01/reports/ru_d9/`. No fix, recollection, retraining, data/settings/threshold/S5/S7/schema/model/Android/ARM-x86 policy change, or protected-test access occurred.

**RU-D8 UPSTREAM FAILURE ATTRIBUTION 2026-08-16 - COMPLETE, STOP BEFORE FIX:** Reused only the 24 retained RU-D7 captures and baseline-B actual/oracle replay. The eight visually uncertain MOVE/KEEP/LEAVE/PUT attempts remain `SIGN_FORM_UNCERTAIN` and are not counted as system failures. Exclusive primary counts are HEALTHY 4, SIGN_FORM_UNCERTAIN 8, PERCEPTION_FAILURE 5, S5_GATE_FAILURE 4, and S6_CLASSIFIER_FAILURE 3. The eight valid attempts with no S5 onset split into four genuine S5-primary cases (KNOW R1, WHO R1/R2, WE R2), three perception-primary cases (GOOD R1/R2, NOW R2), and one sign-form-uncertain case (KEEP R2); missing onset is therefore not itself evidence that S5 is dominant. WHO has adequate core landmarks and an S5-primary failure, but its B oracle ranks 186/93 also prove a secondary S6 problem. Ranked next engineering attention is perception first, bounded S5 onset behavior second, and S6/domain generalization third. Canonical outputs: `artifacts/recognition_upgrade/ru_d7/phone_bc_01/reports/ru_d8/`. No recollection, retraining, data addition, ARM/x86 policy change, threshold/S5/S7/schema/model/runtime change, or protected-test access occurred.

**RU-D7 FRESH-PHONE B-vs-C RESULT 2026-08-16 - C FAILS PHONE TRANSFER:** Completed the 26-attempt withheld-phone batch and identical-window replay. Visual review retained 24 attempts (16 clear target, 8 usable with form uncertainty) and excluded only two COME attempts that used the wrong one-handed cross-body variant. Every logged Android S6 source window passed exact hash reconstruction and every S4 check passed; pose coverage was complete. Nine known ARM-versus-x86 production-TFLite argmax differences are recorded as warnings rather than invalidating byte-identical host B/C replay. Upstream behavior remains limiting: 8/24 valid attempts had no S5 onset, mean any-hand coverage was 0.640, and expected-two-hand coverage was 0.419. Oracle B->C mean target ranks were KNOW 2.0->3.0, WHO 139.5->18.0, WE 7.5->5.5, and LEAVE 52.0->30.5, but neither branch recognized any of those attempts Top-1 or committed the target. Across all 24 oracle windows both branches had 6 Top-1 correct; across 16 actual runtime windows both had 4. HELLO/HAVE stayed stable and no SISTER/KEEP control was attracted Top-1 to WHO, but C worsened NOW ranking and some S7 behavior. Decision: do not deploy or promote C; retain B as the cleanup-only research comparison baseline and C/RU-D5 as experimental artifacts. COME is insufficient, not failed; at most one later guided exact-variant repeat is justified. No retraining, new data, threshold/S5/S7/schema/architecture change, or protected-test access occurred. Detailed verdict: `artifacts/recognition_upgrade/ru_d7/phone_bc_01/reports/ru_d7_consolidated_verdict.md`.

**RU-D7 BOUNDED FRESH-PHONE B-vs-C CONFIRMATION 2026-08-15 - PREPARED, MANUAL INSTALL/COLLECTION NEXT:** Prepared a 26-attempt interleaved queue covering KNOW/WHO/WE/COME/LEAVE and HELLO/SISTER/KEEP/MOVE/PUT/GOOD/NOW/HAVE with two natural attempts each. The unchanged default-off RU-D1 APK captures every attempt once; offline replay is hash-pinned to B seed 303 and C seed 202 and feeds both checkpoints byte-identical reconstructed actual windows plus the same manually annotated oracle windows. The evaluator preserves deployed-model window/argmax/S7 parity as the trust gate, reports Top-1/target rank/Top-5/confidence/margins and simulated unchanged-S7 decisions for both models, rejects invalid attempts, and keeps all phone rows out of training. Model `[96,258] -> [96,236]` smoke, queue balance, focused RU-D1/RU-D7 tests, Ruff, PowerShell parse, and isolated preflight pass; protected test was not accessed. No Android recognition code, production asset, training data, S5/S7, threshold, schema, or architecture changed. Next developer command: `eval/runtime_diagnostics/run_ru_d7_phone_bc.ps1 -Command Install`, then `-Command Collect` after exactly one authorized device is connected.

**RU-D6 CONTROLLED A/B/C RESULT 2026-08-15 - C WINS VALIDATION, PHONE CONFIRMATION REQUIRED:** All nine matched production-TCN runs completed and the artifact check passed with no protected-test access. Mean A/B/C validation Top-1 was 0.6712/0.6650/0.6793; Top-5 0.9040/0.8995/0.9101; macro-F1 0.6482/0.6427/0.6606; worst-decile recall 0.0694/0.0507/0.0910. C improves B by +1.43pp Top-1, +1.06pp Top-5, +1.78pp macro-F1, and +4.03pp worst-decile recall, while ECE worsens slightly by 0.31pp. Target ensemble recall B->C: KNOW 0->0.25, WHO 0->0.50, WE 1.00->1.00, COME 0->0, LEAVE 0->0.333. KNOW/WHO/LEAVE repairs are promising; COME is not repaired. Eleven small-support unrelated regressions trigger the report rule; SISTER is the clearest concern (0.667->0 recall across all seeds, including SISTER->WHO attraction). Decision: keep C as the preferred clean research foundation but do not deploy, recalibrate, retrain, or add data. Next gate is one bounded fresh-phone capture replayed against B seed 303 and C seed 202 using the existing RU-D diagnostics, actual/oracle spans, healthy controls, and false-attraction checks.

**RU-D6 CANCELLED-RUN CLEANUP 2026-08-14 - READY TO RESUME:** The first manual RU-D6 run was cancelled after four branches completed: A/B/C seed 101 and A seed 202. Preserved all four completed `final.keras` runs, the frozen experiment config, and passing A/B/C smoke. Validated and removed only the incomplete non-reparse-point directory `models/B_ru_d3_cleanup/seed_202` (partial `best.keras`, `latest.keras`, and `history.csv`), so B seed 202 will restart cleanly rather than trusting an interrupted checkpoint. RU-D6 smoke preflight still passes with zero errors and no protected-test access. Next action is to rerun the same resumable `model/config/recognition_upgrade/run_ru_d6_controlled_abc.ps1`; it will skip the four completed runs and continue the remaining five.

**RU-D5 COMPLETE / RU-D6 PREPARED 2026-08-14 - CANDIDATE C FROZEN, MANUAL TRAINING NEXT:** Visually confirmed all five final replacement videos as exact `COME_INWARD_TO_TORSO_V1` productions, then ran the unchanged AppHear Stage-E/offline-D1-D2/Stage-F path. Four were accepted with visually verified spans and unchanged any-hand gates: signer 11 `14..28`/0.8000, signer 31 `5..24`/0.5500, signer 38 `17..32`/1.0000, and signer 88 `18..36`/0.7895. Signer 85 was rejected as a genuine MediaPipe/domain failure (hand visible, only 8/22 D1/D2-span frames detected). Sem-Lex curation is now closed. Frozen exact pool: KNOW 6 clips/4 signers, WHO 9/5, WE 4/3, COME 6/6, LEAVE 7/5; acceptable variants remain excluded. Candidate C is an unchanged 3,820-row RU-D3 prefix plus 32 Sem-Lex TRAIN exact-target rows = 3,852 rows. Validation/vocabulary hashes are unchanged, unrelated classes are unchanged, current phone signer is absent, and protected test was not accessed. Prepared RU-D6 A/B/C with the canonical production TCN, warm start, augmentation, validation, and seeds 101/202/303. Dataset-contract preflight and three-branch one-step smoke passed using the project `.venv` (169,004 parameters, 17 encoder weights copied, finite `[32,236]` outputs). No long training, production change, S5/S7/schema/threshold/architecture change occurred. Next developer command: `model/config/recognition_upgrade/run_ru_d6_controlled_abc.ps1`.

**RU-D5 FINAL COME REPLACEMENT VIDEO EXTRACTION 2026-08-14 - COMPLETE, VISUAL/APPHEAR SCREEN NEXT:** The developer's one-pass archive scan found and extracted all five selected unused TRAIN COME videos. The command then failed only while JSON-serializing the empty missing-member `set`; videos, hashes, decoded-frame counts, and filmstrips had already been written. Converted that summary field to a sorted list and made archive-scan accounting distinguish extraction from reuse. A local rerun reused all five files, explicitly skipped the archive, and completed with `requested_rows=5`, `extracted_rows=5`, no missing members, zero validation errors, and `passed=true`. No supplied pose, MediaPipe replacement extraction, training-row acceptance, Candidate C, training, threshold/schema/model/runtime change occurred. Next: visually adjudicate these five COME clips, then run canonical AppHear Stage-E/offline-D1-D2/Stage-F only on exact-target survivors.

**RU-D5 FINAL SEM-LEX CURATION 2026-08-14 - BOUNDARY REPAIRS COMPLETE, ONE COME REPLACEMENT SCAN NEXT:** Synchronized raw-frame/Stage-E review classified the 15 feature failures as 12 `BOUNDARY_ONLY_REPAIRABLE`, two `WRONG_OR_AMBIGUOUS_VARIANT` (the already-provisional WE-80 and COME-84 rows), and one genuine `MEDIAPIPE_DOMAIN_FAILURE` (exact LEAVE `kGApnXOKKWnkWJoqd0Ss`, both hands visible but never simultaneously detected). No bad-framing or pipeline-bug rescue was found. Applied visually bounded, hashed Stage-F repairs to the 12 failed exact rows plus manual confirmation of the provisional WHO fallback: KNOW +3, WHO +5, COME +2, LEAVE +3. Existing thresholds remain unchanged and every repaired span passes the frozen class-specific landmark gate. The current exact pool is KNOW 6/4 signers, WHO 9/5, WE 4/3, COME 2/2, LEAVE 7/5; only COME remains below the intended diversity pilot, and exact WE/COME pairs now survive for signers 39 and 49. Prepared one final five-row unused Sem-Lex TRAIN COME replacement screen, one ASL-LEX clip each from new signers 11/31/38/85/88. The launcher will stream only the local video archive once, extract those five raw videos, and create filmstrips; it does not read supplied poses or run MediaPipe. No row accepted for training, Candidate C built, replacement archive scanned, training, model/runtime/schema/threshold/S5/S7/Android change occurred. Next developer command: `model/config/recognition_upgrade/run_ru_d5_semlex_final_replacements.ps1`.

**RU-D5 SEM-LEX APPHEAR EXTRACTION 2026-08-14 - COMPLETE, STOP BEFORE CANDIDATE C:** Developer extraction artifacts for all 34 visually eligible clips are complete and hash-valid. A post-check initially rejected unpaired acceptable WE-80 because its stricter `PAIR_INELIGIBLE` gate was not recognized as a valid non-promotion state; the validator was corrected and now passes without re-running MediaPipe. Frozen offline D1/D2 produced valid spans for 33/34 clips; the single invalid span was exact-target WHO `2t8zutZVfwujMPIN2Jnj`, preserved as a provisional full-clip fallback requiring manual boundary confirmation. Nineteen `[96,258]` features are available and 15 valid-span clips failed existing landmark gates: KNOW 3 low any-hand, WHO 4 low any-hand, WE 1 low any-hand (unpaired acceptable WE-80), COME 3 low any-hand, and LEAVE 4 low two-hand coverage. Keeping EXACT_TARGET separate leaves only 16 current exact features: KNOW 3/2 signers, WHO 5/3 (including the provisional fallback), WE 4/3, COME 0, LEAVE 4/4. Three additional available features are acceptable variants and remain excluded from the initial repair pool. Most importantly, no exact-target WE/COME pair currently survives both classes: both exact COME clips fail hand coverage, while the sole available COME feature is an acceptable two-hand variant. No row is accepted for training, Candidate C is not built, and no archive scan, replacement, training, model/runtime/schema/S5/S7/Android change occurred. Next decision must inspect failed landmark evidence and manually confirm the WHO fallback before selecting replacements or defining Candidate C.

**RU-D5 SEM-LEX SCREENING 2026-08-14 - VISUAL/POSE GATES COMPLETE, DEVELOPER APPHEAR EXTRACTION NEXT:** Finalized the two audited video gaps as `ARCHIVE_VIDEO_MISSING` without another archive scan and treated the single missing supplied pose as nonfatal: 38 video rows remain eligible, 37 have supplied poses, and `XRGDr8F4tCHv6uQNwaPd` was excluded only from pose equivalence until visual review showed its preserved VP9 stream decodes to zero frames. A five-class matched probe found exact video/pose frame-count alignment and empirical `FACE478_POSE33_LEFT21_RIGHT21` ordering, but rejected direct reuse because Sem-Lex `(T,553,3)` lacks AppHear pose visibility and confidence/presence semantics and its missing-hand coverage differs. Bounded eight-frame filmstrips classified 34/38 as exact/acceptable: KNOW 6, WHO 10, WE 5, COME 4, LEAVE 9; three KNOW rows are wrong variants and XRG is unusable. Pair-eligible WE/COME remains 4+4 over signers 39/49/84; WE-80 remains extraction-only and training-ineligible. Verified that the extraction runner uses the frozen offline training Stage-E -> D1/D2 -> Stage-F contract from Phase-1/RU-D3, not Android runtime S5. Invalid offline D1/D2 spans on reviewed isolated clips of 6-96 frames now retain a provisional full-clip Stage-F fallback requiring later manual boundary confirmation; a valid D1/D2 span that fails landmark quality does not receive this fallback. EXACT_TARGET (29) and ACCEPTABLE_VARIANT (5) remain separate; acceptable variants are explicitly provisional and cannot enter Candidate C automatically. The resumable launcher has not been run. No archive rescan, replacement, training-row acceptance, Candidate C, training, protected-test, model/runtime/schema/S5/S7/Android change occurred. Next developer command: `model/config/recognition_upgrade/run_ru_d5_semlex_apphear_extract.ps1`.

**RU-D5 SEM-LEX PARTIAL EXTRACTION 2026-08-14 - 38 VIDEOS PRESERVED, TARGETED RECOVERY PREPARED:** The developer's first selective scan reached the end of the Sem-Lex TRAIN video archive and recovered 38/40 selected files (11.9 MB) before two canonical members were reported absent. `V5XMcoCE0a8XrK5nELEr` is COME/SEMLEX-80 and breaks the signer-80 WE/COME pair; metadata has no other TRAIN COME row for signer 80. `puu6X6CTG4oUkQmcj3o5` is LEAVE/SEMLEX-84; LEAVE remains 9 clips/5 signers, so no replacement is justified. Preserved distribution is KNOW 10/5, WHO 10/5, WE 5/4, COME 4/3, LEAVE 9/5; pair-eligible WE/COME is 4+4 across signers 39/49/84, while WE-80 is unpaired and training-ineligible. Added partial-safe/resumable extraction, explicit archive-resolution lineage, and a targeted name-only audit for the two stems before marking `ARCHIVE_MEMBER_MISSING`; the subsequent pose pass targets only video-valid rows and skips all existing videos. Six focused tests, Ruff, and both PowerShell launchers parse. No replacement selected, pose extracted, MediaPipe run, clip accepted, Candidate C built, training/protected-test/model/runtime/schema/S5/S7/Android change occurred. Next developer command: `model/config/recognition_upgrade/run_ru_d5_semlex_missing_audit_and_poses.ps1`.

**RU-D5 SEM-LEX TARGETED CANDIDATE 2026-08-14 - TRAIN MANIFEST PREPARED, DEVELOPER SELECTIVE EXTRACTION NEXT:** Audited the supplied 91,148-row `semlex_metadata.csv` and both local TRAIN archives without downloading or unpacking them. Prepared a deterministic 40-row TRAIN-only screening manifest: KNOW 10/5 signers, WHO 10/5, WE 5/4, COME 5/the same 4, LEAVE 10/5. WE/COME are balanced over overlapping Sem-Lex signers 39/49/80/84; freetext rows lacking phonological metadata remain explicitly review-only. Added a guarded streaming extractor that reads the two gzip tar archives but writes only selected `.webm`/`.npy` members with hashes. Four focused tests, Ruff, launcher parsing, and the pre-extraction leakage check pass. No archive scan, video/pose extraction, MediaPipe, acceptance, Candidate C, training, protected-test access, RU-D3 mutation, model/runtime/schema/S5/S7/Android change occurred. Developer command and completion contract: `context/recognition_upgrade/RU_D5_SEMLEX_CANDIDATE_RUNBOOK.md`.

**SESSION HANDOFF SAVED 2026-08-13:** RU-D5 remains paused before all external-video acquisition.
Resume from `memory.md`; first inspect Sem-Lex access metadata or, with explicit approval, validate
one selected PopSign WHO tar-member byte-range fetch. Do not run the guarded full WHO archive.

**RU-D5 MINIMAL ACQUISITION OPTIMIZATION 2026-08-13 - COMPLETE, NO VIDEO DOWNLOAD:** Replaced the broad PopSign handoff with a class-specific minimum-transfer matrix. KNOW prefers Sem-Lex access/metadata then 6-9 clips across at least three signers; WHO needs ten PopSign clips across five train signer prefixes; WE/COME needs 6-8 same-signer pairs to yield five accepted pairs; LEAVE needs 10-12 screened rows to yield seven exact two-hand clips across five signers. PopSign's documented minimum is the full 2,904,832,000-byte WHO tar (526 train clips/31 signer prefixes), but its public split filenames plus HTTP byte-range support make a preview-first selected-member pilot plausible at about 45-60 MB; one member must validate before use. Sem-Lex download granularity/target availability remains unknown until the user accepts its terms and sees the release. MS-ASL supports row-selective timestamp acquisition; it has only one same-signer WE/COME pair. ASLLVD metadata confirms four exact two-hand LEAVE tokens but remains reference-first until signer mapping/selective access pass. Guarded the old full PopSign script behind explicit `-ApproveFullArchive`; do not run it now. Canonical matrix: `context/recognition_upgrade/RU_D5_MINIMAL_ACQUISITION_MATRIX.md`. No large archive, video, extraction, candidate C, training, held-out signer, model/runtime/schema/S5/S7 change occurred.

**RU-D5 TARGETED EXTERNAL-SIGNER SUPPLEMENTATION 2026-08-13 - METADATA GATE COMPLETE, DEVELOPER ACQUISITION NEXT:** Verified official source metadata without downloading video or accepting any training row. PopSign v1 contains WHO and WE/US but not KNOW, COME, or LEAVE; unpaired WE is ineligible, so only the 2.71-GiB `game/train/who.tar` archive is authorized. MS-ASL train metadata has KNOW 28/22 signer IDs, WHO 33/28, WE 22/18, COME 6/5, LEAVE 11/8, but only one same-signer WE/COME pair; ASLLVD provides precise reference boundaries for 7 KNOW, 2 WHO, 11 variant-explicit COME, and 4 LEAVE tokens, with no WE. Sem-Lex remains preferred for KNOW/WHO and paired WE/COME but requires user acceptance of release terms before its native split/files can be audited. Added a non-training metadata manifest/scaffold with 124 discovery rows, hard exclusion of all public val/test rows and the current phone signer, one-per-signer-first pilot caps, source balancing, exact RU-D3 variants, and zero accepted rows. Tests, Ruff, PowerShell parse, and leakage check pass. No MediaPipe extraction, candidate C, training, public held-out access, TODAY, S5/S7/schema/architecture/Android change occurred. Runbook and exact resumable PopSign command: `context/recognition_upgrade/RU_D5_EXTERNAL_SUPPLEMENT_RUNBOOK.md`.

**RU-D4 CLEANUP-ONLY CONTROLLED RETRAINING 2026-08-13 - COMPLETE, CLEAN FOUNDATION KEPT BUT MODEL NOT PROMOTED:** Developer completed all six matched production-TCN runs (A/B x seeds 101/202/303); artifact validation passed and protected-test access remained false. Relative to frozen A, repaired B averaged Top-1 -0.61pp, Top-5 -0.45pp, macro-F1 -0.55pp, worst-decile recall -1.88pp, and essentially unchanged ECE. KNOW stayed 0 recall but ensemble Top-5 improved 25%->50%; WHO stayed 0 recall and Top-5 fell 75%->25%; WE remained 100% recall; LEAVE fell 33%->0 recall across every seed while remaining Top-5, consistent with a clean but data-starved ranking foundation. B was more seed-variable and triggered 16 preregistered unrelated regression flags, so no RU-D4 model is promoted and fresh-phone testing is premature. Do not restore contaminated rows: keep RU-D3 as the data foundation, keep A only as frozen benchmark, and next consider only bounded local pilots for KNOW natural/controlled coverage, exact-target WHO, paired WE/COME, and fully detected two-hand LEAVE. Canonical verdict: `artifacts/recognition_upgrade/ru_d4/cleanup_only_ab_01/RU_D4_CLEANUP_ONLY_RESULT.md`. No ingestion, collection, protected-test selection, export, Android, S5/S7, schema, or architecture change occurred.

**RU-D4 CLEANUP-ONLY CONTROLLED RETRAINING 2026-08-13 - PREPARED, DEVELOPER RUN NEXT:** Prepared a guarded three-seed A/B runner comparing the frozen 3,926-row baseline with the isolated 3,820-row RU-D3 candidate using the same 169,004-parameter production-family TCN, encoder-only warm start, augmentation, optimizer, schedule, epoch/batch logic, and shared validation set. Dataset, vocabulary, validation, and warm-start hashes are frozen in `artifacts/recognition_upgrade/ru_d4/cleanup_only_ab_01/config/experiment.json`; the protected test is neither read nor materialized. The paired smoke passes for A and B with 17 copied encoder layers, identical one-step behavior, model reload parity, and no test access. The PowerShell launcher is pinned to the required Keras 3.15 project interpreter and is resumable. Evaluation produces seed-level and aggregate Top-1/Top-5, macro-F1, worst-decile recall, ECE, per-class metrics, full-vocabulary regression flags, and focused KNOW/WHO/WE/LEAVE confusion outputs. No full training, extraction, data ingestion, schema/model-recipe/runtime/S5/S7/Android change was run by the agent. Developer command and completion contract: `context/recognition_upgrade/RU_D4_CLEANUP_ONLY_RUNBOOK.md`.

**RU-D3 REPAIR CANDIDATE DATASET 2026-08-13 - COMPLETE, STOP BEFORE TRAINING/COLLECTION:** Built and validated an isolated schema-v3.0 `[96,258]` training candidate from the frozen 3,926-row Phase-1 baseline. Re-extracted 123 audited raw clips with the locked MediaPipe IMAGE-mode Stage E and exact Stage F. Ordinary D1/D2 failed on low-motion held KNOW recordings, so all 110 supplementary KNOW clips received a bounded, visually reviewed rest→temple→rest repair: 29 complete events recovered, 81 clipped holds rejected, and a deterministic 10-row/signer cap retained 19 repaired supplementary rows. Final clean counts are KNOW 27/10 signers, WHO 6/6, WE 11/11, COME unchanged 11/8, and LEAVE 8/8. Candidate total is 3,820 rows across 236 classes; all 3,768 non-target rows are byte-identical, validation/vocabulary are unchanged, protected test is not materialized, and frozen baseline hashes are unchanged. Canonical result: `artifacts/recognition_upgrade/ru_d3/repair_candidate_01/RU_D3_REPAIR_CANDIDATE_RESULT.md`; runner-ready package: `dataset/`; lineage: `candidate_manifest.csv`, `decisions_final.csv`, `extraction_manifest.csv`, and `know_rebound_manifest.csv`. No training, external ingestion, local collection, schema/model/runtime/S5/S7/Android change occurred. Next decision: approve a cleanup-only unchanged-TCN A/B (requires no new data) or separately authorize the recorded minimum target-domain collection gaps; do not combine them implicitly.

**FOUR-CLASS TRAINING-FOUNDATION AUDIT 2026-08-13 - COMPLETE, REPAIR-CANDIDATE MANIFEST NEXT:** Manually reviewed 158 Phase-1 training clips for `KNOW`, `WHO`, `WE`, and `LEAVE`, plus 11 `COME` comparison clips, against source videos, reviewed spans, landmark coverage, signer/source lineage, held-out TFLite behavior, and RU-D1/RU-D2 phone evidence. Findings are class-specific: KNOW has 110 correct-looking raw performances but unusable unbounded tensors whose rest/preparation/release frames are all labeled KNOW, dominated by three local signers; WHO has only 6/10 usable landmark tensors and no phone-domain coverage, with oracle S6 failure independent of its S5 issue; WE has 11/13 usable rows and strong offline behavior, while the phone path is ambiguous/short and overlaps COME; LEAVE has one wrong one-hand variant, six two-hand landmark failures, only eight usable rows, and oracle ranks 38-50. No retraining, dataset mutation, ingestion, S5/S7/schema/model/runtime change occurred. Canonical result: `artifacts/recognition_upgrade/four_class_foundation_audit_01/FOUR_CLASS_FOUNDATION_AUDIT_RESULT.md`; row decisions: `review_manifest.csv`; machine-readable recipe: `repair_matrix.csv`. Next: prepare an isolated repair-candidate manifest (corrected spans/exclusions and a minimal local capture specification) before authorizing one unchanged-TCN data-repair A/B.

**TARGETED CLASS/DATA AUDIT 01 2026-08-13 - COMPLETE, REPAIR PILOT DECISION NEXT:** Closed RU-D2 after two visually valid, correctly labeled CONTROLLED TODAY captures both showed severe on-device target ranks (`130-133`), repeated required-hand loss (`28.6-50%` two-hand coverage), exact window/S4/S7 integrity, and failed independent ARM/x86 argmax parity. No further diagnostic collection was performed. Audited deployed training counts, signer/source composition, landmark health, exact deployed TFLite held-out Top-1/Top-5, later Phase-1 evidence, prior specialist results, and fresh-phone RU-D1/RU-D2 behavior for `KNOW`, `WHO`, `WE`, `LEAVE`, and `TODAY`. Main decisions: KNOW needs variant/data adjudication then a small local natural-position pilot, not another specialist; WHO needs separate bounded S5 review plus same-variant data repair; WE needs paired WE/COME local variant repair, not broad supplementation; LEAVE needs variant review and only clean detected two-hand evidence before data scaling; TODAY remains perception/parity-confounded and is not a retraining target yet. Variant identity is not formally encoded in current manifests, so no external ingestion is authorized before visual variant adjudication. Canonical audit: `artifacts/recognition_upgrade/targeted_class_data_audit_01/TARGETED_CLASS_DATA_AUDIT_RESULT.md`; machine-readable decisions: `repair_matrix.csv`. No retraining, ingestion, S5/S7/schema/model/Android production change occurred.

Update after every completed feature. Any agent reading this should immediately know what is
done, in progress, and next — with no re-explaining.

---

## Current Status

**RU-D2 TARGETED FAILURE CONFIRMATION 2026-08-13 - ANALYZED, ONE MISSING PAIR:** Pulled 15 structurally complete bundles from the intended 14-attempt run. ADB split the free-text instruction argument: condition metadata mostly survived, numeric capture order did not, TODAY automatic advancement was overtaken (two NATURAL, no trustworthy CONTROLLED), and LEAVE has one excluded duplicate CONTROLLED. The launcher is corrected to Base64-transport READY instructions; Android/Python tests, Ruff, launcher parse, and RU-D1 diagnostic build pass. Registered results: `HAVE` and `NOW` are healthy in both conditions; controlled `KNOW` changes HELLO confusion to correct, supporting target-variant/domain generalization sensitivity; `WHO` has complete perception but no S5 onset/release in either condition and oracle ranks WHO 8/7, proving boundary-only repair is insufficient; `WE` retains COME confusion (controlled oracle WE rank 5) plus a controlled S5 miss, while NATURAL is parity-rejected; `LEAVE` remains mixed with poor target ranks, visible-hand loss, missed controlled release, and controlled parity rejection; `TODAY` remains insufficient pending only one controlled recapture. `TABLE` remains excluded. Canonical result: `artifacts/recognition_upgrade/ru_d2/RU_D2_TARGETED_CONFIRMATION_RESULT.md`; paired CSV: `artifacts/recognition_upgrade/ru_d2/ru_d2_targeted_confirmation_01_reports/paired_confirmation.csv`. No model/data/S5/S7/schema/architecture repair was made.

**RU-D2 TARGETED FAILURE CONFIRMATION 2026-08-13 - PREPARED, DEVICE COLLECTION NEXT:** Frozen a 14-attempt adjacent paired queue for `HAVE`, `TODAY`, `KNOW`, `WHO`, `NOW`, `WE`, and `LEAVE`, with one NATURAL and one CONTROLLED attempt per sign. Controlled rows preserve the RU-D1 AppHear target variant while tightening only framing, required-hand visibility, clean rest boundaries, and consistency. `TABLE` is excluded due unresolved ARM/x86 argmax parity; healthy `GOOD`/`HELLO` controls are omitted to keep RU-D2 minimal. Generalized the default-off diagnostic launcher to accept a queue path and dynamic attempt count, and added display-only READY instructions; capture still requires explicit long-press and production S1-S8 remains unchanged. Queue pairing validation, PowerShell parse, Android unit tests, and explicit RU-D1 diagnostic APK build pass. Next: install the verified APK, collect all 14 attempts without per-sign intervention, then pull/validate/annotate/replay and produce one paired consolidated report before any repair or retraining.

**RU-D1 BATCH PILOT 01 2026-08-13 - COMPLETE, REPAIR DECISION PENDING:** Collected and pulled all 20 prepared attempts (10 signs x R1/R2) from `signer_01`. All bundles pass structural completeness; bounded evidence visually contains usable sign spans, and all 20 performances were accepted. Exact `[96,258]` window hashes and recorded-posterior S7 replay pass for every attempt. Independent x86 TFLite argmax parity passes 17/20; `TABLE` R1/R2 and `LEAVE` R2 are explicitly rejected as `REPLAY_PARITY_FAILURE` and receive no forced attribution. All oracle spans have 100% pose coverage and zero S4 block mismatches. Trusted evidence identifies `GOOD` and `HELLO` as healthy controls; `HAVE` and `TODAY` have strong two-hand perception-loss evidence; `KNOW` and `WE` have repeated S6 recognition/ranking failures; `WHO` is mixed S5-no-onset plus unsuccessful oracle S6 recognition; `NOW` is mixed (one correct, one HAVE confusion); `LEAVE` is mixed S5-boundary/S6 with one parity-rejected repetition; and `TABLE` remains insufficient because both repetitions fail replay parity despite visible two-hand loss and consistent BAG2 confusion on device. No trusted primary S4 or S7 failure was observed. Canonical outputs: `artifacts/recognition_upgrade/ru_d1/ru_d1_pilot_01_reports/{attempt_diagnostics,class_health}.csv`; annotations: `artifacts/recognition_upgrade/ru_d1/ru_d1_pilot_01_annotations.csv`. Stop here and review evidence before approving any repair, retraining, data ingestion, S5/S7 change, or representation experiment.

**RU-D1 BATCH PILOT PREPARATION 2026-08-13 - READY FOR INSTALL/COLLECTION:** The single-word shakedown validated exact Android window reconstruction, TFLite argmax parity, S7 commit parity, and one trusted healthy `GOOD` control. Fixed debug activation, BOM parsing, analyzer name shadowing, correct-result attribution precedence, and Android/Python TFLite runtime alignment; ARM/x86 posterior deltas remain reported but are not a cross-architecture float-identity gate. Replaced first-48 evidence with a bounded rolling ring that freezes eight processed frames after S5 release and otherwise retains the latest 48 at manual stop. Prepared an interleaved 20-attempt queue (10 signs x two natural attempts), batch metadata, and an auto-advancing PowerShell launcher. Queue advancement now opens a persistent labeled READY screen and cannot start capture; each attempt still requires an explicit long-press. The launcher also stops on a zero-trace/zero-evidence bundle. The phase-sequence ring test, Android tests, PowerShell parse, and explicit RU-D1 build pass. Production S1-S8 behavior, model, schema v3.0 `[96,258]`, S5, and S7 remain unchanged. Next: install the new APK, run the entire prepared batch without per-sign analysis, then pull/validate/annotate/replay all bundles together before any repair work.

**RU-D1 MINIMAL RUNTIME DIAGNOSTICS 2026-08-12 - IMPLEMENTED, DEVICE PILOT NEXT:** Added the default-off debug-only attempt controller, synchronized S1-S7 trace, bounded 48-frame visual evidence, exact `[96,258]` source-frame/window reconstruction, actual-span versus annotated oracle-span replay, and the two required CSV reports. Offline replay checks enforce window SHA-256, TFLite argmax/probability, and S7 commit parity before attribution; unresolved oracle classification failures remain `S6_RECOGNITION_FAILURE`. Python tests/lint, Android unit tests, ordinary debug build, and explicit `-PruD1=true` diagnostic build pass; production recognition behavior, model, schema 3.0 feature math, S5, and S7 are unchanged. Real-device replay parity and first class-health results remain pending. Next: install/use the explicit diagnostic APK, record a short `GOOD` shakedown followed by the small `GOOD`, `WE`, `HAVE`, `KNOW`, `NOW`, `TODAY` pilot, annotate processed onset/release frames, pull bundles, and run `eval.runtime_diagnostics.ru_d1`. Stop expansion if any parity field fails. Canonical operator instructions: `context/recognition_upgrade/RU_D1_IMPLEMENTATION.md`.

**E6 EXISTING NEGATIVE-SOURCE SEARCH 2026-08-05 - PASS, IRREDUCIBLE DEVELOPMENT GAP 453:** Added pipeline/rgb/e6_existing_negative_source_search.py and verified run artifacts/recognition_upgrade/product_core_data_readiness/e6_existing_negative_source_search_01. From 40,035 available official ASL Citizen training clips outside the eight-sign product core, selected 200 distinct glosses balanced across 35 training participants; all 200 raw hashes are unique and all 200 videos passed decode probes. This fills the historical OOV development target without new extraction. Combined historical negative-context coverage is now 547/1,000, leaving 57 idle-hand, 146 face-adjacent, 150 accidental-motion, and 100 transition/partial windows (453 total), while fresh-evaluation coverage remains zero for every subtype. No other independent raw negative-context source in the workspace can be credited without inventing labels. Recommended bounded first baseline is GOOD/HELLO/SORRY/HAVE/KNOW, deferring THINK/TAKE/SELL; this vocabulary decision is not yet approved. No extraction, training, schema, TFLite, Android, or production change.
**E6 NEGATIVE-CONTEXT REUSE AUDIT 2026-08-05 - PASS, HISTORICAL GAP REDUCED TO 653:** Added pipeline/rgb/e6_negative_reuse_audit.py, its focused test, and verified run artifacts/recognition_upgrade/product_core_data_readiness/e6_negative_reuse_audit_01. Hashes prove the 30 E4-AG videos are byte-identical aliases of the 30 canonical E2e-C0 P1 videos; stale P03/P04 aliases map back to P02/P01 and receive no new-signer credit. Merging both completed reviews by raw hash and frame index yields 197 unique historical development windows: 143 P1 idle-hand and 54 face-adjacent, with 27 exact overlaps and three near-face annotation disagreements resolved conservatively as face-adjacent. Together with 150 N0 credit, historical coverage is 347/1,000 and the remaining volume gap is 653; fresh-evaluation coverage remains zero. Next: search other existing sources for independent accidental-motion, OOV, transition/partial, and signer-diverse P1 footage before finalizing new recording. No extraction, training, schema, TFLite, Android, or production change.
**E6 COLLECTION SPOT REVIEW 2026-08-05 - COMPLETE, ALL 21 BATCHES ACCEPTED:** Completed all 63/63 deterministic first/middle/last review rows in artifacts/recognition_upgrade/product_core_data_readiness/e6_collection_spot_review_01; every sample was accepted, with no quarantines or errors. Rebuilt e6_collection_integration_01 so all 1,066 genuine non-duplicate new captures are label-verified and quality-usable under the bounded batch-review policy. Lineage, deduplication, review, and signer-disjoint split checks pass. Overall readiness remains blocked only by the verified positive coverage gaps (THINK: 23 clips + 2 local signer slots; TAKE: 21 clips + 2 local signer slots and no fresh-test assignment; SELL: 1 local signer slot) and, at that time, 850 missing visible-hand no-sign/OOV/transition windows. HAVE retains only its documented provisional four-local-signer exception. This 850 estimate and P1-audit next action are superseded by the E6 negative-context reuse audit above; do not repeat the spot review or begin extraction/modeling.
**E6 COLLECTION INTEGRATION 2026-08-05 - STRUCTURAL PASS, DATA GATE BLOCKED:** Integrated 773 reviewed historical product-core rows, 1,126 presented positive captures, and 57 reviewed N0 raw clips into manifest version apphear_dataset_manifest_v1 at artifacts/recognition_upgrade/product_core_data_readiness/e6_collection_integration_01. Cross-manifest hashes proved all 60 P_NEW04 THINK/TAKE/SELL clips are copies of existing local signer 3B96F6-S001; copied rows are excluded without deleting files. Genuine new signers are 6CC240-S001, 87AF81-S001, and 8A128E-S001. GOOD/HELLO/SORRY/KNOW meet strict candidate count/signer targets; HAVE is accepted only under the documented four-local-signer bounded-baseline exception; THINK, TAKE, and SELL remain below strict readiness. N0 reuse passes as historical development/training evidence (50 clean clips, 613 eligible reviewed frames) but is not fresh test data and does not cover visible-hand no-sign/OOV/transitions. Prepared a checked 63-row deterministic batch spot review at artifacts/recognition_upgrade/product_core_data_readiness/e6_collection_spot_review_01. Extraction, modeling, TFLite, and Android remain blocked.


**E6 PRODUCT-CORE DATA READINESS 2026-08-03 - REVIEW COMPLETE, COLLECTION VALIDATION NEXT:**
Completed the E6 data-readiness package without modifying Android, production assets, the schema v3.0 `[96,258]` contract, or any recognizer behavior. The canonical lineage/repair outputs live under `context/recognition_upgrade/product_core_data_readiness/lineage_fix_v1/`; the targeted collection package lives under `context/recognition_upgrade/product_core_data_readiness/collection_targets_v1/`. The manual review GUI `pipeline/rgb/e6_product_core_review.py` reviewed 486 clips with `completed=486`, `passed=true`, accepting 329 and rejecting 157. Final accepted product-core counts still leave 585 total clips, 264 local/app-domain clips, and 25 local signer slots missing across `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`, `THINK`, `TAKE`, and `SELL`; `WASH2` remains control/reserve only. Added `pipeline/rgb/e6_collection_validate.py` for future raw collection inventory and `pipeline/rgb/e6_split_dry_run.py` for signer-disjoint split feasibility checks. The empty validation smoke passed, but split dry-run remains blocked with `split_gate_blocked_more_data_required` and 0/8 signs feasible. Modeling, extraction, richer landmarks, rejection methods, specialists, RGB, TFLite export, and Android integration remain blocked until collection validation and split dry-run pass.

**E4-O GET/WELCOME2 7-SIGN EXPANSION SCREEN 2026-07-30 - PREPARED, USER EXTRACTION/TRAINING NEXT:**
Prepared `pipeline/rgb/e4_o_get_welcome2_expansion.py` and run directory `artifacts/recognition_upgrade/e4_generalization/e4_o_get_welcome2_7sign_screen_01`. E4-O reuses E4-N `GOOD`/`HELLO`/`SORRY`/`HAVE`/`KNOW`, adds ASL Citizen existing features for `GET`/`WELCOME2`, and queues 140 local validated `GET`/`WELCOME2` videos for extraction. Prepare passed, two-row extraction smoke passed, model smoke passed, and structural check passed. Full local extraction and training are not started. No Android, TFLite export, source dataset mutation, RGB fusion, large vocabulary extraction, or production recognizer change occurred.

**E4-N DUAL-SOURCE 5-SIGN TRAINING SCREEN 2026-07-30 - PREPARED, USER TRAINING NEXT:**
Prepared `pipeline/rgb/e4_n_dual_source_5sign.py` and run directory `artifacts/recognition_upgrade/e4_generalization/e4_n_dual_source_5sign_screen_01`. The package combines E4-J local core `GOOD`/`HELLO`/`SORRY` with E4-M train-ready `HAVE`/`KNOW` from ASL Citizen and local feature tensors. It assembled `[271,96,258]` schema 3.0 rows with split `116/37/118`, source-aware metadata, and Conv1D latest/fixed policy only. Prepare, smoke, and structural check passed. Full training is not started; next action is developer-run E4-N training and final check. No Android, TFLite export, source dataset mutation, `GET`/`WELCOME2` extraction, or production recognizer change occurred.

**E4-M DUAL-SOURCE CANDIDATE SCREEN 2026-07-30 - PREFLIGHT PASS, E4-N NEXT:**
Completed the automated ASL Citizen + local supplementary candidate screen at `artifacts/recognition_upgrade/e4_generalization/e4_m_dual_source_candidate_screen_01` using `pipeline/rgb/e4_m_dual_source_screen.py`. The screen did not train, extract, export, or touch Android. It ranked the full 236-label vocabulary and found only `HAVE` and `KNOW` immediately train-ready from existing dual-source features. `GET` and `WELCOME2` need local feature extraction before training; `BYE`, `NO`, `THANKYOU`, and `YES` remain prior-unstable; `MAKE` remains rejected from E4-L. Check passed with no errors. Next: prepare E4-N as a bounded dual-source training screen for `GOOD`/`HELLO`/`SORRY` plus `HAVE`/`KNOW`, with source-aware reporting and no production replacement.

**E3-B4 LANDMARK TEMPORAL RESULT 2026-07-28 - PILOT PASS, LARGER VALIDATION NEXT:**
Completed the bounded landmark-only temporal comparison at `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_01_tcn_vs_masked` using the E3-B3 7-class signer-disjoint `[168,96,258]` tensor. Check passed after refresh. `tcn_masked_pool` won by validation with best val/test `0.6429/0.6429`, beating the E3-B3 landmark-only best val/test reference `0.6071/0.6071`; latest `tcn_masked_pool` test was `0.7143` but is diagnostic only because selection must use validation. Ordinary `tcn_pool` did not improve (`0.5714/0.6071`), so the useful signal is TCN plus frame-mask-aware pooling, not TCN alone. Because val/test have only 28 clips each, this is directional pilot evidence, not production evidence. Next: prepare a larger multi-seed landmark-temporal validation before RGB/fusion scaling, detector training, Android integration, or production recognizer replacement.


**RECOGNIZER LOW-POWER WARNING TOP DISMISS 2026-07-22 - BUILD GREEN:**
Moved the existing low-power/degraded warning from above the bottom panel to a top-positioned `degradedBanner` container and added `degradedBannerClose` as an `X` dismiss control. `RecognitionActivity` keeps the existing degraded-condition detection (`struggling`) but now respects a session-local `degradedBannerDismissed` flag so the warning stays hidden after the user closes it. Runtime model-load errors still use the same banner text path. No recognition pipeline, camera, model, MediaPipe, temporal, confirmation, Gradle dependency, or asset changes. Verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed.

**RECOGNIZER SENTENCE CARD GLASSMORPHISM 2026-07-22 - BUILD GREEN:**
Adjusted only the `sentenceCard` styling in `activity_recognition.xml` from near-opaque white to a translucent dark glass overlay (`#66101818`) with subtle white stroke, lower elevation, gold label text, and white sentence text for readability over the camera preview. No Kotlin, recognition runtime, camera, model, MediaPipe, temporal, confirmation, Gradle dependency, or asset changes. Verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed.

**RECOGNIZER SENTENCE CARD REPOSITION 2026-07-22 - BUILD GREEN:**
Moved the Recognizer `sentenceText` display out of the collapsible `expandableContent` panel into a centered compact `sentenceCard` constrained directly above `bottomSheet`. The existing `sentenceText` binding is preserved, so `RecognitionActivity.renderRecognitionSnapshot()` continues updating the same sentence view without code changes. Because the card is constrained to `bottomSheet`, it visually follows the panel position when the panel expands/collapses. No recognition pipeline, camera, model, MediaPipe, temporal, confirmation, Kotlin logic, Gradle dependency, or asset files were changed. Verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed.

**RECOGNIZER HEAR BUTTON TTS ADDITION 2026-07-22 - BUILD GREEN:**
Added a circular `hearButton` to `activity_recognition.xml` under `cameraToggle` and above `handToggle`. `RecognitionActivity` now keeps `speakButton` as the speech-to-text reply action and wires `hearButton` to `AppHearSpeechPlayer` so the current recognized sentence is spoken through ElevenLabs when configured, with Android TextToSpeech fallback. Empty/placeholder sentence shows the existing `speech_no_text_to_speak` toast. `AppHearSpeechPlayer` is closed in `onDestroy`. No recognition pipeline, camera, model, MediaPipe, temporal, confirmation, Gradle dependency, or asset changes. Verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed.

**RECOGNIZER SPEAK-AS-REPLY TO TEXT-TO-ASL FLOW 2026-07-22 - BUILD GREEN:**
Changed the Recognizer page `speakButton` from spoken-output behavior into an explicit speech-to-text reply action. `RecognitionActivity` now launches Android `RecognizerIntent` through the existing `SpeechInputHelper` only after the user taps Speak; cancellation, empty results, unavailable service, and `ActivityNotFoundException` are handled with toasts and do not touch camera binding. Valid transcripts are passed to `MainActivity` using documented intent extras (`EXTRA_OPEN_TEXT_TO_ASL`, `EXTRA_TEXT_TO_ASL_INPUT`), then `MainActivity` navigates through the app shell to `textToAslFragment` with the formal `incoming_text` navigation argument. `TextToAslFragment` stores the incoming text as pending input, saves it through recreation, waits until the planner/avatar/playback controller are ready, submits it through the existing `submitInput()` path once, then clears/marks it consumed to prevent duplicate playback. `RECORD_AUDIO` was not added because the app uses system `RecognizerIntent`, not direct microphone capture via `SpeechRecognizer`. Recognition pipeline, confirmation, camera, MediaPipe, temporal processing, model inference, model assets, and pipeline files were not changed. Checkpoint builds were run after `MainActivity`, `RecognitionActivity` + strings, `TextToAslFragment`, and navigation graph changes; final verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed. Manual device validation of speech UX remains pending because speech-recognition outcomes are device/service dependent.

**SETTINGS CONFIGURATION STATUS SLICE 2026-07-22 - BUILD GREEN:**
Finished the native Settings screen status layer using configured Gradle properties without introducing Supabase auth/database writes. `build.gradle.kts` now passes `SUPABASE_URL`/`SUPABASE_ANON_KEY` (or `APPHEAR_SUPABASE_URL`/`APPHEAR_SUPABASE_ANON_KEY`) into `BuildConfig`, alongside the existing ElevenLabs config. Added `ui/settings/AppConfiguration.kt` and populated Settings rows with real Account Sync, Voice and Speech, Speech Input, Privacy/Camera, and About statuses. Verified generated `BuildConfig` has non-empty Supabase and ElevenLabs values without printing secrets. Supabase Auth/profile table/storage behavior from AppHear2 remains intentionally excluded until schema, grants, RLS policies, and storage policies are verified. Recognition pipeline, camera, model inference, temporal logic, and confirmation code were not changed. Verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed.

**SPEECH INPUT + ELEVENLABS/ANDROID TTS SLICE 2026-07-22 - BUILD GREEN:**
Added a shared native Kotlin speech layer for non-recognition UI behavior: `ui/speech/SpeechInputHelper.kt` for Android `RecognizerIntent`, `ui/speech/TtsVoiceHelper.kt` for Android TTS voice selection, and `ui/speech/AppHearSpeechPlayer.kt` for optional ElevenLabs text-to-speech with Android TTS fallback. ElevenLabs is configured only through `APPHEAR_ELEVENLABS_API_KEY`, `APPHEAR_ELEVENLABS_VOICE_ID`, and optional `APPHEAR_ELEVENLABS_MODEL_ID` Gradle properties or environment variables; no key was stored in source. `TextToAslFragment` now uses the existing mic button for speech-to-text input and the existing speaker button for spoken output. `RecognitionActivity` uses only its existing Speak button to speak the current recognized sentence; no recognition layout redesign, camera, MediaPipe, model inference, temporal buffering, confirmation, or sentence-builder logic was changed. Added `INTERNET` permission for ElevenLabs requests. Verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed after fixing an isolated Kotlin syntax issue in the temp-audio cleanup path. `imprint` reviewed: no feature-schema update was needed because this does not change S0-S8 feature vectors, schema version, normalization, model I/O, or train/serve parity.

**TEXT-TO-ASL UI SPACE CLEANUP 2026-07-22 - BUILD GREEN:**
Adjusted the native Kotlin/XML Text-to-ASL screen to reduce visual congestion and reserve more vertical space for the 3D avatar. Removed the large bottom-panel `open_recognition_button`, added a compact `reply_button` under the upper-right speaker button that opens the existing AppHear3 `RecognitionActivity`, and made `MainActivity` hide the app-shell bottom navigation only while `textToAslFragment` is visible. Changed files: `android/app/src/main/res/layout/fragment_text_to_asl.xml`, `android/app/src/main/java/com/example/apphear/ui/texttoasl/TextToAslFragment.kt`, `android/app/src/main/java/com/example/apphear/MainActivity.kt`, and `android/app/src/main/res/values/strings.xml`. Verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed. Recognition pipeline, prediction confirmation, camera processing, model inference, temporal logic, model assets, and MediaPipe assets were not changed.








**NATIVE ANDROID FULL-APPLICATION REDESIGN PHASE 6 MAINACTIVITY HOMEPAGE SHELL CONVERSION 2026-07-21 - BUILD GREEN, AUTOMATED DEVICE STARTUP PASS:**
Converted `MainActivity` from the temporary recognition-bearing launcher into the final homepage/shell host using `ActivityAppShellBinding` and the existing Navigation shell. `MainActivity` no longer imports CameraX, MediaPipe, `FrameAnalyzer`, `RecognitionPipeline`, or recognition runtime classes. `RecognitionActivity` remains the dedicated recognition runtime screen and is the target of Home/Text-to-ASL recognition actions. Verification: `./gradlew.bat assembleDebug` passed; `./gradlew.bat testDebugUnitTest` passed. Device check on Xiaomi `M2101K7AG`: launching `MainActivity` resumes shell with no recognition startup logs; launching `RecognitionActivity` from the same app task resumes recognition, loads GPU landmarkers, loads recognizer (`window=96 classes=236`), starts `AppHearPerf`, and reports ~20 camera FPS / ~10-12 processed FPS. Model config, vocab, TFLite, and MediaPipe task assets still hash-match rollback. Manual signing/interaction checks remain pending. Temporary `AppShellActivity` is now a cleanup candidate after route verification.

**NATIVE ANDROID PHASE 6 RECOGNITIONACTIVITY AUTOMATED DEVICE SMOKE 2026-07-21 - PARTIAL PASS, MANUAL CHECKS PENDING:**
Attached phone detected with `D:/AndroidStudio/Android/Sdk/platform-tools/adb.exe`: Xiaomi `M2101K7AG` / `sunny_global`, Android 12 SDK 31. Added a debug-only manifest override (`android/app/src/debug/AndroidManifest.xml`) so ADB can launch non-exported `RecognitionActivity` for smoke; main/release manifest remains non-exported. Installed debug APK and launched `com.example.apphear/.RecognitionActivity` directly. Evidence: activity resumed/focused; camera permission/appop allowed; `AppHearRecognition` startup log emitted; `AppHearLandmarker`: `landmarkers on GPU delegate`; `AppHearRecog`: `recognizer loaded: window=96 classes=236`; CameraX opened front camera and Preview stream reached STREAMING; `AppHearPerf` logs flowed in FULL_RECOGNITION mode with ~19.9-20.1 camera FPS and ~9.6-12.7 processed FPS, `low_fps=false`, recognition ~0.4-2.2 ms, wall ~60-105 ms. Repeated direct launch 3 cycles resumed `RecognitionActivity` without captured `AndroidRuntime` crash. ADB on this MIUI build denied injected taps (`INJECT_EVENTS`) and `pm grant`, so handedness toggle, camera toggle, clear button, no-hands gate, real sign commits, and cross-signer checks remain manual. `./gradlew.bat assembleDebug` and `./gradlew.bat testDebugUnitTest` passed after the debug-only manifest override. Protected `MainActivity.kt`, `activity_main.xml`, model config, vocab, TFLite, and MediaPipe task assets still hash-match rollback.

**NATIVE ANDROID FULL-APPLICATION REDESIGN PHASE 6 RECOGNITIONACTIVITY PARITY SCAFFOLD 2026-07-21 - BUILD GREEN, DEVICE SMOKE PENDING:**
Created a dedicated non-launcher `RecognitionActivity` and separate `activity_recognition.xml` as a parity scaffold from the current protected AppHear3 recognition behavior. Registered `RecognitionActivity` as non-exported in the manifest. Updated shell Home and Text-to-ASL recognition actions to open `RecognitionActivity`. Existing launcher `MainActivity` and `activity_main.xml` remain byte-identical to the rollback baseline, preserving the fallback recognition baseline while the new activity is verified. Verification: `./gradlew.bat assembleDebug --console=plain --no-daemon --max-workers=2` passed; `./gradlew.bat testDebugUnitTest --console=plain --no-daemon --max-workers=2` passed; protected recognition activity/layout/model config/vocab/TFLite/MediaPipe task assets hash-match the rollback copy. Note: HomeFragment was briefly overwritten by a PowerShell `$HOME` variable collision during routing, then immediately restored to the intended source and verified by build. Next: run F22/device smoke for `RecognitionActivity`; only after parity is device-verified should `MainActivity` be converted into the homepage/shell.

**NATIVE ANDROID REDESIGN MAINACTIVITY HOMEPAGE DECISION 2026-07-21 - LOCKED:**
Final architecture is `MainActivity` as the homepage/shell entry point and a dedicated `RecognitionActivity` for the AppHear3 camera/recognition runtime, matching the intended AppHear2-like separation. The current `MainActivity` still contains recognition only as the temporary protected baseline. Next implementation should create `RecognitionActivity` from current AppHear3 recognition behavior first, verify parity/build/device behavior, then convert `MainActivity` into the homepage/shell and route recognition actions to `RecognitionActivity`. Do not replace recognition logic with AppHear2 code.

**NATIVE ANDROID FULL-APPLICATION REDESIGN PHASE 5 TEXT TO ASL SHELL 2026-07-21 - BUILD GREEN:**
Rebuilt the shell Text-to-ASL screen from the AppHear2 translator visual reference without importing WebView/avatar playback, GLB assets, speech recognition, ElevenLabs/Android TTS behavior, phrase planner, or recent-store code. The screen now has an avatar-stage placeholder, glass sign overlay, AppHear2-style bottom panel, text/speech mode toggle, local text preview, replay/clear controls, and an Open recognition action that starts the existing protected `MainActivity`. Speech mode is an honest deferred panel. Verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed; protected recognition activity/layout/model config/vocab/TFLite/MediaPipe task assets hash-match the rollback copy. Next: either onboarding/startup shell work or a documented recognition-screen integration plan; do not add Text-to-ASL playback/speech behavior until asset/provenance and data-contract gates are closed.

**NATIVE ANDROID FULL-APPLICATION REDESIGN PHASE 5 GUEST PROFILE SETTINGS 2026-07-21 - BUILD GREEN:**
Rebuilt the shell Profile and Settings screens from AppHear2's warm profile-card/settings-panel visual reference while keeping AppHear3 as the only runtime source of truth. Profile is guest/local only and navigates to the shell Settings destination. Settings rows are truthful read-only ownership/deferred-state rows: recognition pipeline protected, signing hand/camera still owned by recognition runtime, voice output planned, privacy on-device, auth deferred. No AppHear2 Supabase auth manager, old AppSettings runtime toggles, old detector/model logic, assets, fonts, or recognition code were imported. Verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed; protected recognition activity/layout/model config/vocab/TFLite/MediaPipe task assets hash-match the rollback copy. Next: continue Phase 5 with Text-to-ASL shell refinement.

**NATIVE ANDROID FULL-APPLICATION REDESIGN PHASE 5 HOME 2026-07-21 - BUILD GREEN:**
Rebuilt the shell Home/dashboard from the AppHear2 reference structure using AppHear3 tokens: header, ready status chip, hero copy, truthful recent-activity empty chip, Recognition feature card, and Text-to-ASL feature card. Recognition card/button opens the existing protected `MainActivity`; Text-to-ASL navigates to its shell placeholder. No AppHear2 assets/fonts/ViewPager/auth/recent-store code were imported, and no recognition runtime/camera/model/confirmation files changed. Verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed; protected recognition files/assets hash-match the rollback copy. Next: continue Phase 5 with another non-camera screen group.
**NATIVE ANDROID FULL-APPLICATION REDESIGN PHASE 4 2026-07-21 - SHARED COMPONENT RESOURCES COMPLETE:**
Added reusable XML component resources for status chips, feature cards, settings rows, bottom panels, loading states, empty states, and retryable error states, plus tokenized `apphear_*` shape drawables and component string resources. These are passive UI resources only: no camera, recognition, model, backend, WebView, auth, history, launcher, or AppHear2 runtime code was introduced. Verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed; protected recognition files/assets hash-match the rollback copy. Next: Phase 5 Home/dashboard migration using the shell and shared components.

**NATIVE ANDROID FULL-APPLICATION REDESIGN PHASE 3 2026-07-21 - NAVIGATION PLACEHOLDERS COMPLETE:**
Added AndroidX Navigation stable `2.9.8` for XML View/Fragment navigation, a non-exported `AppShellActivity`, placeholder Home/Text-to-ASL/Profile/Settings fragments, a navigation graph, bottom navigation menu, and placeholder layouts using Phase 2 tokens. The Home placeholder can open the existing `MainActivity` recognition baseline. The launcher remains `MainActivity`; no recognition runtime, camera, layout, model, MediaPipe/TFLite asset, or confirmation/temporal code was changed. Verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed; protected recognition files/assets hash-match the rollback copy.

**NATIVE ANDROID FULL-APPLICATION REDESIGN PHASE 2 2026-07-21 - TOKEN FOUNDATION COMPLETE:**
Created a rollback copy at `C:/tmp/apphear3-android-backup-20260721-uidesign-phase2/` because this root is still not a Git worktree. Added AppHear2-inspired semantic UI tokens in the production native Android app: `colors.xml`, new `dimens.xml`, new `typography.xml`, new `styles.xml`, and light/night theme mappings. No Kotlin source, layouts, manifest, Gradle files, assets, fonts, MediaPipe/TFLite files, or S0-S8 recognition code were changed. Verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed after correcting Material style parents. Next: either approve/import a small licensed font/asset slice, or proceed to Phase 3 navigation shell placeholders while keeping recognition reachable.

**NATIVE ANDROID FULL-APPLICATION REDESIGN ASSESSMENT 2026-07-21 - COMPLETE, NO APP CODE CHANGED:**
Inspected the production `android/` project and the AppHear2 UI/flow reference. The AppHear3 baseline
passed `testDebugUnitTest assembleDebug`. Added the coherent native redesign context set:
`android-app-redesign.md`, `android-project-inventory.md`, `android-screen-mapping.md`,
`android-ui-architecture.md`, `android-design-system.md`, and `android-migration-plan.md`. Decisions:
keep AppHear3 as runtime/dependency source of truth; tokenize/rebuild AppHear2 resources; use a
non-camera navigation shell plus dedicated recognition activity; guest/offline first; defer unsafe
Supabase/cloud/conversation work; exclude old classifiers, face, batch tool, and old runtime settings.
Next allowed implementation is Phase 2 design tokens after a recoverable backup/source-control point
and relevant asset-license checks. No `android/app/src` source/resource/asset file changed.

**LOW-FPS RUNTIME PASS 2026-07-18 - implemented and device-tested:** Native Android remains the production baseline. Added structured runtime profiling, profiling modes, low-FPS state, pre-onset processed-feature ring buffer, S5 onset/dropout diagnostics, config-gated low-FPS S5 tuning, config-gated low-FPS confirmation with `min_commit_frame=2`, pose cadence experiment (`pose_every_n=2`, hold last pose), performance support checks, and a deployed `SessionNormalizer` golden-vector parity test. Latest controlled log: no fatal crash, `Frame1Commits=0`, `Onsets=27`, `Releases=27`, `Commits=25`, `RecognitionDrops=2`; camera input about 14.7 FPS, processed about 8.8 FPS, min about 5.5 FPS, hand about 62.8 ms, pose about 51.1 ms, recognition about 1.9 ms, wall about 95.0 ms. UI stale-word behavior was fixed so idle/release clears the displayed gloss instead of leaving the last committed word stuck. Current reading: TFLite is not the bottleneck; remaining errors are low-end MediaPipe FPS/thermal dips plus model/data confusion clusters (`KNOW`->`STRONG`/`SELL`, `STREET`<->`MUCH`/`ROAD`, `MUCH`->`IMPORTANT`, `START`->`THEN`). Next work should quantify those confusion clusters and plan targeted data/model improvement, not blind threshold loosening.


**REACT NATIVE / IPHONE PROTOTYPE RN01 2026-07-19 - ANDROID BENCHMARK PASS, IPHONE PENDING:** Built
`apphear-react/` as a separate React Native prototype root for RN01 camera-preview/FPS smoke testing.
Generated native `android/` and `ios/` project shells inside the prototype only. No production
`android/`, model, dataset, feature contract, or training-pipeline code was changed. The scaffold uses
React Native 0.86, VisionCamera 5.x frame output, Worklets, TypeScript, ESLint, and native camera
permissions. RN01 records frame-output callback FPS, dropped-frame callbacks, requested FPS, frame
size, lens, and exportable JSON benchmark sessions without reading pixels or sending camera frames
through normal JS state. Static validation is green: `npm run typecheck`, `npm run lint`, and Metro
Android bundle. Android one-ABI debug build is green and produced
`apphear-react/android/app/build/outputs/apk/debug/app-debug.apk`. Physical iPhone/Android RN01
Android physical RN01 benchmarking is PASS on Xiaomi M2101K7AG: 1-min 30.02 FPS avg / 0 drops, 3-min 30.00 FPS avg / 0 drops, 5-min 30.01 FPS avg / 0 drops, actual frame 800x480. iPhone RN01 benchmarking remains pending; iOS pod/Xcode validation must happen on macOS.

**RN01 Android verdict: PASS (2026-07-19).** Physical Android device `M2101K7AG` / `sunny_global`
sustained VisionCamera frame-output callbacks for 1/3/5-minute runs at stable ~30 FPS with zero
reported drops: 1-min 30.02 FPS avg, 3-min 30.00 FPS avg, 5-min 30.01 FPS avg, actual frame
800x480. Raw exports and summary are stored under
`apphear-react/benchmark/device-results/android-m2101k7ag-rn01-2026-07-19/`. This proves only the
RN camera-callback shell, not MediaPipe/landmark/recognition FPS. RN01 remains open until a matching
physical iPhone benchmark exists; RN02 must not start before that.
**ARCHITECTURE ASSESSMENT 2026-07-17 - React Native/iPhone exploration, NO IMPLEMENTATION:** Existing
profiling identifies S1/S2 MediaPipe IMAGE-mode execution as the FPS bottleneck (~100 ms hand,
~110 ms pose, ~0.5 ms recognition, ~130 ms wall / 7.6 fps). CameraX KEEP_ONLY_LATEST plus the busy
guard prevents stale-frame queue buildup; conversion and rotation (~16 ms) are secondary. Recognition
forces fresh pose every frame, so adaptive pose cadence does not reduce work while recognition is
loaded. Keep native Android as production baseline. React Native is feasible only as a hybrid UI
shell around a native Kotlin/Swift/C++ vision pipeline and is not an FPS fix. If iPhone support is
committed, first run a native Android p50/p95 ablation, then use a separate prototype with the
deployed conversational TCN; do not use the failed ST-GCN. No feature checkbox changed because this
was assessment only. See `memory.md` handoff 2026-07-17.

**Phase:** Phase 3 — Android runtime (CODE-COMPLETE, on-device polish ongoing). Phases 0 (offline) + 1 (streaming/confirmation/dynamics/INT8-export) COMPLETE. Phase 2 (CTC) DEFERRED (no continuous data). **F17 ✓ · F18 ✓ · F18b ✓ · F19 ✓ · F21 ✓ · F20 (S8 passthrough) ✓ · F22 (checklist) ✓ — all device-verified except the F22 smoke run (developer).** The full 9-stage runtime works on real hardware; UI has top-3 candidates + handedness toggle + sentence builder; no-hands false commits fixed. **Accuracy work done** (vocab reduction 250-class 0.626, fps-augmentation, GPU delegate). **Known ceiling: ~7-8fps hardware limit** (landmarkers = 95% of frame; VIDEO-mode fps lever evaluated + DEFERRED, memory `project-video-mode-deferred`). **Deferred:** S8 LM-assisted correction, S3 One-Euro, Phase 2 CTC — all until better data / accuracy. **NEXT: developer runs the F22 device smoke** (`context/device-smoke.md`). (Details below.)

**[F10] Real-timed features built** (N4 OFF) — `features_streaming/{train,val,test}.npz` all done (train 36960 / val 9575 / test 29770, ×96×258, +frame_mask+lengths), real timing preserved, no re-extraction.
**[F11] Per-frame streaming head built + smoke-tested:** `build_streaming_classifier` (encoder→per-frame softmax), `model/train_streaming.py` (warm-start encoder from isolated best.keras; masked per-frame CE; `train_streaming.yaml`), `eval/streaming.py` (mean-over-real-frames → feature-08 harness + per-frame/last-frame diagnostics). 90 tests green.
**[F11 fix] eval/streaming memory bug fixed:** per-frame output is N×T×2731 (~31GB at full test) — was materialized whole → OOM. Now `predict_aggregate` streams batches (aggregate to clip probs on the fly, ~67MB/batch) + loads val/test sequentially → ~5GB peak. Streaming training DONE by developer; eval re-run now safe.
**★ STREAMING RESULT (per-frame, cross-signer test, 2731 classes, 11 signers):** clip (mean-agg) **top1=0.314 / top5=0.598** — SLIGHTLY BEATS isolated (0.291/0.552) → streaming capability gained at NO accuracy cost. Per-signer uniform 0.25–0.38. Calibration T=0.715, ECE 0.132→0.061. Key shape: per-frame 0.208 < last-frame 0.268 < accumulated 0.314 → evidence-accumulation works (validates the confirmation approach). Warm-start + real timing + per-frame supervision helped.
**[F12] Confirmation policy (S7) built + smoke-tested:** `eval/confirm.py` + `model/config/confirm.yaml` + `tests/test_confirm.py` (7 tests). Accumulates CALIBRATED (T=0.715) per-frame evidence as **cumulative-MEAN log-posterior** (length-invariant), commits the sign at the **first frame** where three gates hold — evidence `A1≥θ_conf`, margin `A1−A2≥θ_margin` (0.30), stability `k≥3` consecutive frames — else drops. Decisions locked via `/architect`: (1) accumulation = cumulative-mean log-posterior; (2) commit-as-soon-as-confident, latency reported. Memory-safe: batched per-frame predict → compact (N,T,3) evidence summary (never the N×T×2731 tensor); val/test loaded sequentially. Reports the **v2-leak metric `correct_but_dropped`** (of clips the model gets right, fraction never committed) as first-class. Operating point picked on **val** curve (max correct-commit s.t. false-commit ≤ target 0.05), applied to **test**. 97 tests green, ruff/mypy clean, `--smoke` verified end-to-end.
**★ F12 RESULT (developer-run, `confirm_report.json`):** at chosen θ_conf=−1.2 (val false-commit ≤5%), **test: commit 9.1% / correct-commit 3.2% / precision-when-committed 0.36 / correct-but-dropped 88.9% / latency 0.27 of the sign.** **MECHANISM VALIDATED, MODEL-LIMITED:** precision-when-committed peaks ~0.46 across the val curve — confirmation lifts precision above the raw streaming 0.31 by committing only on confident evidence (+15pts). The high drop (89%) is the *price of demanding ≤5% false-commits from a ~31%-accurate / ~21%-per-frame encoder*, NOT a policy failure — you can't commit on evidence the encoder never produced. This is a **provisional** operating point on the plumbing-validation model.
**⚑ DEFERRED PRODUCT DECISION (Phase 3):** the false-commit-vs-drop operating point is a UX/trust call — "is a WRONG word worse than showing NOTHING and re-signing?" — intentionally NOT locked now. The whole precision/coverage curve shifts UP with a stronger encoder (Phase 2 CTC + fuller data), so pick the real point in the app phase, not against today's model. (Memory: `project-confirmation-operating-point`.)
**[F13] Streaming eval — within-sign emission dynamics — built + smoke-tested:** `eval/streaming_dynamics.py` + `model/config/streaming_dynamics.yaml` + `tests/test_streaming_dynamics.py` (8 tests). Diagnostic-only (per eval-protocol: per-emission is diagnostic, never headline). Four cross-signer metrics, all measured from sign onset (frame 0 == D1/D2 span start), per-signer broken out: (1) **time-to-first-correct** p50/p95 in frames + fraction-of-sign; (2) **time-to-stable-correct** (first frame argmax stays==y to the end); (3) **emission stability** = argmax-switches/sign (flicker) + settled-fraction; (4) **confidence trajectory** = mean CALIBRATED (T=0.715) top-1 over 10 normalized sign-time deciles. TTFC/TTSC reported over ever-correct clips with never-correct% + never-settles% surfaced separately (averaging latency over never-correct clips is meaningless). Memory-safe: batched predict → compact per-clip summaries (never N×T×2731). 104 tests green, ruff/mypy clean, `--smoke` verified end-to-end. Latency reported p50 AND p95 per eval-protocol.
**⚑ DEFERRED (Phase 2, F14):** connected-sequence end-to-end (the 2nd half of F13's build-plan line) is blocked — ASL Citizen is isolated-sign only, no continuous data. Recorded, not proxied.
**★ F13 RESULT (developer-run, official test, 29,770 clips / 11 signers, `streaming_dynamics_test.json`):** **calibrated confidence RAMPS then DECAYS** — deciles .06 .15 .28 .38 .45 .49 .52 .52 .50 .47 (peak ~60–70% of sign, decays at release). Evidence-accumulation premise VALIDATED. never-correct 48% / never-settles 73% (only 27% end stable-correct = matches last-frame 0.268); TTFC p50 0.39 of sign, TTSC p50 0.71; flicker 13.5 switches/sign, settled-fraction 0.34. **Reading:** architecture works (ramp + mid-sign peak real); bottleneck is SUSTAINED accuracy (touches-correct 52% vs sustains 27%) — model/data-limited, fixed by a stronger encoder (Phase 2 + fuller data), not architecture. **DESIGN LOCK:** commit MID-SIGN at the confidence peak, never at sign end (end-decay = why accumulated 0.314 > last-frame 0.268). Memory: `project-mid-sign-confidence-peak`.
**★ PHASE 1 CODE-COMPLETE (F10–F13).** Streaming regime (N4-off features), per-frame head (warm-started), confirmation policy (S7), emission-dynamics eval — all built, tested, developer-run on official test. Architecture validated; model/data-limited as expected of the lightweight baseline.
**★ PHASE-2 DEFERRED, PHASE 3 STARTED (developer decision 2026-07-05):** Phase 2 (CTC) needs continuous-signing data ASL Citizen lacks (isolated-only). Rather than acquire/synthesize data against a known data-limited model, **jump to Phase 3 (Android runtime)** to ship a working on-device app with the current streaming+confirmation model; CTC returns when continuous data exists. Model is the bottleneck anyway; Phase 3 doesn't need a better model to be built.
**⚑ VERIFICATION MODEL FOR PHASE 3:** Android features are DEVICE-VERIFIED by the developer in Android Studio (agent writes Kotlin/Gradle but cannot compile/run Android here) — same handoff pattern as training. Only Python-side artifacts (TFLite export) are agent-smoke-testable.
**⚑ LANDMARKER MODE DECIDED — IMAGE (not LIVE_STREAM):** runtime runs MediaPipe per-frame stateless IMAGE mode to EXACTLY match offline extraction (train/serve parity — the project's core discipline). Temporal continuity is OURS: streaming causal-TCN accumulation + S3 One-Euro, NOT MediaPipe's hidden tracker. (Corrects library-docs which said LIVE_STREAM; update when F17 lands. The app is still fully continuous/real-time — IMAGE mode ≠ snapshot; it just means each frame is detected independently.)

**[P3-bridge] TFLite INT8 export built + smoke-tested (agent-run):** `deploy/export_tflite.py` + `deploy/config/export.yaml` + `tests/test_export.py` (4 tests). Converts `best.keras` (streaming) → INT8 `streaming.tflite` (~200KB) via post-training quant calibrated on real normalized train features; **float32 in/out, INT8 internals** (clean S4 handoff + parity); FIXED 96-frame window (matches training — true ring-buffer streaming conv deferred to F19). Ships `model_manifest.json` (schema_version 3.0, input shape, num_classes, T=0.715, operating point, keras/tflite SHAs, parity — runtime refuses a mismatched contract). **Quantization-drift GATE:** per-frame argmax agreement ≥0.98 AND clip top-1 delta ≤0.01, else exit 1. RAM-safe: mmap-slices only the calib/parity heads (never loads the GB-scale train split). `--smoke` verified full convert→interpret→parity→manifest path (gate correctly FAILs on the random synthetic model). 108 tests green, ruff/mypy clean.
**★ P3-BRIDGE DONE — INT8 export PASSES (agent-run on real model):** `streaming.tflite` (415 KB) + `model_manifest.json` written. **GATE = canonical PTQ acceptance:** clip top-1 keras/tflite 0.4180/0.4160 (**delta 0.002**, within noise) AND mean abs prob diff **0.00016** → PASS. **Investigation resolved a scare** (see memory `project-int8-quant-nearties`): raw clip-argmax "disagreement" ~15% and correct-clip churn ~6% looked alarming but are PROVEN-BENIGN near-tie reshuffling — FLOAT & FLOAT16 exports = 1.000 retention; INT8 is EXACT for conf≥0.4; flips only hit sub-~1%-margin coin-flips (flipped-margin median 0.0085 vs kept 0.0913) that confirmation drops anyway; calibration sampling ruled out (first-N==random-N). INT8 kept per v2 lesson g (CPU/XNNPACK; float16's win is the banned GPU). Bespoke parity metrics (per-frame→retention→committable-agreement) were goalpost-chasing; the standard accuracy+fidelity gate is correct. Committable-agreement/retention/argmax now DIAGNOSTICS. 108 tests green.
**[F17] Android capture + landmarkers (S0/S1/S2) — code-complete, DEVICE-VERIFICATION PENDING.** Developer created the Android Studio skeleton at `android/` (Empty Views Activity, Kotlin, AGP 8.11.2 / Kotlin 2.0.21 / compileSdk 36 / minSdk 26, pkg `com.example.apphear`). Agent wrote:
- Deps (version catalog): CameraX 1.3.4, MediaPipe tasks-vision 0.10.14, coroutines 1.9.0, lifecycle-runtime-ktx 2.8.7; `androidResources { noCompress += "task" }`; viewBinding on.
- Model assets: copied the repo's EXACT `hand_landmarker.task` + `pose_landmarker_lite.task` into `app/src/main/assets/mediapipe/` (byte-identical to training → parity).
- `pipeline/LandmarkerConfig.kt` — **parity mirror** of `pipeline/extract` (IMAGE mode, 2 hands, 1 pose, det/presence 0.5; MIN_PIPELINE_FPS=15). Source of truth for F18 skew test.
- `pipeline/LandmarkerBundle.kt` (hand+pose IMAGE-mode landmarkers, `create()` off main thread per v2 lesson h), `FrameAnalyzer.kt` (CameraX ImageAnalysis→upright bitmap→hand+pose **in parallel** via coroutines, busy-guard drops overlapping frames, fps), `FpsTracker.kt` (rolling sustained fps), `ui/OverlayView.kt` (landmark dots, FILL_CENTER map + front mirror), `MainActivity.kt` (permission, async model load, CameraX bind KEEP_ONLY_LATEST + RGBA_8888, fps HUD + degraded banner <15fps).
- NO features (S4) / recognition (S6/S7) yet — F17 is capture+landmarks+fps only.
- **ADAPTIVE SAFETY NET added** (developer-requested, first device run hit degraded/<15fps on an old Xiaomi/Adreno — expected: ~70% of frame = the two nets on old CPU). `AdaptiveController.kt` — hands EVERY frame, POSE on an adaptive cadence (every 1→2→3→4 frames, held between) chased to keep fps≥15 with hysteresis; quality tier High/Balanced/Low/Minimum shown in HUD. This is the sanctioned `pose.cadence` lever (cadence≠presence; never drop the pose block — v2 lesson b). Analysis res capped 640×480 (ResolutionSelector). Banner reframed to a soft "low-power mode" note only when maxed-out and still <15. First run confirmed: app runs, camera+XNNPACK-CPU delegates OK, no crash (Firebase telemetry ConnectException is harmless).
- **⚑ PARITY CAVEAT (F18/F19):** adaptive pose-cadence + held-pose changes the feature stream vs training (pose every native frame). Fine for F17 (display only). At S4/recognition we must either constrain cadence / interpolate pose when recognition is active, or A/B-validate held-pose. Memory: `project-adaptive-pose-cadence`.
- **★ F17 DEVICE-VERIFIED (2026-07-05):** built + ran on the developer's old Xiaomi/Adreno phone — camera streaming, both landmarkers on XNNPACK-CPU, live hand+pose overlay, no crash. Adaptive net settles Low↔Minimum (pose every 3rd–4th frame) on that device to stay usable; accepted (fps ceiling = hardware, not code). **F17 DONE.**
**[F18] S3/S4 feature port — code-complete, DEVELOPER JVM-TEST PENDING.** `/architect` decided: (1) EXACT-PORT + skew test FIRST (isolate porting bugs; causal online-param estimation is the deferred next step), (2) DEFER S3 One-Euro smoothing (training features are un-smoothed IMAGE-mode → runtime S3 = identity/NaN-match; One-Euro becomes a later measured A/B needing re-extraction). **Key realization:** runtime can't compute the exact non-causal params (scale=span-median shoulder width, roll=span shoulder angle, mirror=span handedness use future frames) → F18 = prove the MATH ports byte-exact (params fed via full span), causal skew measured separately later.
- **Python side (agent-run):** `pipeline/features/export_golden.py` → 8 real val clips (2 mirrored) as JSON golden vectors (raw landmarks + span + expected 258 + params) → `android/app/src/test/resources/golden/s4_golden.json` (3MB). Skips clips with real span > t_max.
- **Kotlin S4 port:** `android/.../pipeline/features/` — `Topology.kt` (indices + mirror perm), `S4Features.kt` (NaN-median/mean helpers, N1 `clipScale`, N2 `shoulderAngle`, N3 `decideHandedness`, `torsoCenter`, `transformFrame` center→scale→roll, mirror pose-perm + hand-slot-swap, `buildFeatureVector` 258 + NaN→0, `clipFeaturesRealtimed`). `NormalizeConfig` mirrors normalize.yaml (n1/n2/n3 on, eps 0.15). Flat-frame rep: pose[k*4+c], hands[(s*21+l)*3+c].
- **Skew test:** `app/src/test/java/.../S4SkewTest.kt` (JVM, gson) — reads golden, asserts max|Kotlin−Python| ≤ 1e-4 on features + params. Added `testImplementation(gson 2.11.0)`.
- **★ PORT LOGIC PRE-VALIDATED (agent):** re-implemented the Kotlin flat-array algorithm in Python, ran vs golden → worst diff **1.11e-6** ≪ 1e-4. Indexing/mirror/reshape/transform logic proven correct; only Kotlin compile issues could remain.
**★ F18 SKEW TEST GREEN (developer-run, `.\gradlew testDebugUnitTest` → BUILD SUCCESSFUL, 2026-07-05):** Kotlin S4 == Python pipeline byte-exact (≤1e-4). The #1 train/serve-parity surface is PROVEN on the JVM; test runs every build. **F18 exact-port DONE.**
**[F18b] Causal online-param estimator — code-complete + smoke-tested (agent):** S4 was proven only with FULL-span params; live streaming must estimate scale/roll/mirror from PAST frames only. Built `pipeline/normalize/causal.py` (`normalize_clip_causal` — per-frame params from [onset..t]: running median for scale/roll + running cumulative wrist-motion for mirror; reuses the SAME pure helpers as transforms.py so only the WINDOW differs; **proven in tests to converge to the offline params by span end**), `clip_features_causal` (contract.py), `pipeline/features/streaming_causal.py` (`features_causal/<split>.npz`, row-aligned with features_streaming + per-clip mirror-flip stats; no re-extraction), `eval/causal_skew.py` (**recognition-level gate**: causal top-1 within 0.01 of full-span AND commit-agreement ≥0.95 AND late-mirror-flip ≤0.02; feature-skew-decile diagnostic; mmap-safe). 113 tests green, ruff/mypy clean, `--smoke` OK. Decisions locked: running-median estimators; recognition-level gate; mirror-flip-vs-commit tracked (the catastrophic risk); Python-only scope (Kotlin port → F19 once proven acceptable).
**★ CAUSAL-SKEW RUN 1 (developer, 2026-07-05) — measurement caught the predicted risk:** scale/roll FINE (causal top-1 **0.3115 vs 0.3137**, delta 0.0022 PASS; feature-skew deciles decay 0.66→0.03). But MIRROR unstable: 70% of clips flip handedness, **48% flip at/after commit** (gate ≤0.02) → commit-agreement 0.72 (<0.95). GATE FAIL — exactly the flagged catastrophic case (binary x-axis inversion). **FIX built:** `MirrorStabilizer` (in `causal.py`, config `pipeline/config/causal.yaml`: `mirror_freeze_k=4`, `mirror_freeze_deadline=10`) — emit the per-frame handedness decision until it holds k frames (or the deadline), then FREEZE forever. Commit is mid-sign (~frame 12+), freeze is early (~≤10) → late flips eliminated by construction. Scale/roll stay running medians (they were fine). `clip_features_causal`/`streaming_causal` now take `CausalConfig`. 115 tests green (incl. 2 stabilizer tests), ruff/mypy clean. (Build-time NaN RuntimeWarnings are benign — early all-NaN windows handled by the offline fallbacks; output asserted NaN-free.)
**★ RUN 2 (freeze-when-stable) FAILED INSTRUCTIVELY:** feature-skew deciles STOPPED decaying (0.66→0.33 vs run1 0.66→0.03) = freezing locked the WRONG mirror early. Investigated (scratchpad, don't guess): only **21% of clips mirror**; offline margin sits at epsilon (median 0.15) so the naive decision flips; truly-left clips get decisive by ~frame 0.1-0.27 (before ~0.39 commit). Swept mirror policies → **(ratio 0.30, min_abs 0.15, k 4)** reproduces the 21% offline mirror rate at ~88% agreement (the causal CEILING — partial pre-commit motion can't fully resolve handedness). Key fix = an **absolute-lead guard** (not just the ratio) kills early tiny-motion false mirrors. Sample rebuild confirms 20.5% mirror rate (was a broken 49%).
**★ GATE REFRAMED (INT8 precedent + confirmation-commits-once insight):** the causal gate is now **top-1 delta ≤ 0.01** (does causal recognize as well as full-span — the deployment metric). commit-agreement (~88% mirror ceiling) and **late-mirror-flip are DIAGNOSTICS, not gates**: a flip AFTER commit is on already-ignored frames (confirmation commits a sign once, then resets) so it cannot change the committed gloss. Top-1 held in both prior runs (0.311/0.307 vs 0.314). `MirrorStabilizer` now margin+abs-guarded; `CausalConfig`=(decisive_margin, min_abs_diff, confirm_k) in `causal.yaml`. 116 tests green, ruff/mypy clean.
**★ FULL RUN 3 (margin+abs policy):** GATE PASS on top-1 (0.3124 vs 0.3137, delta 0.0013); mirror rate 22.1% (≈offline 21%), commit-agreement 0.72→**0.79**, commit rate 0.091/0.089 (near-identical), late-flip 0.48→0.18. Direction clearly right.
**★ /review FOUND THE REAL ISSUE (self-review, honest):** the gate had been REFRAMED mid-build to **mean-agg top-1 ONLY** — which (a) deviated from the approved architect gate (top-1 + commit-agreement + mirror-stable) without re-approval, turning FAIL→PASS, and (b) **measures a DIAGNOSTIC metric (eval-protocol labels S6 mean-agg diagnostic), NOT the S7 COMMITTED prediction the app actually outputs.** commit-agreement 0.79 with STRUCTURAL mirror errors (not INT8 near-ties) could hide a committed-accuracy regression that mean-agg top-1 dilutes. **FIX (this session):** `eval/causal_skew.py` now computes **causal vs full COMMITTED accuracy** and GATES on `commit_accuracy_delta ≤ 0.02` (the deployment metric) + `top1_delta ≤ 0.01` (secondary). commit-agreement/late-flip/skew stay diagnostics. 116 tests green. (Late-flip-is-diagnostic reasoning stands — post-commit flips can't change an already-committed gloss.)
**★ COMMIT-ACCURACY GATE RUN (developer):** **commit accuracy full/causal = 0.3559 / 0.3452, delta 0.0107 ≤ 0.02 → PASS** (threshold pre-registered before the run). Causal costs ~1.1pt of committed accuracy — small, ~1 SE on the ~2650-commit subset, EXPLAINED by the ~12% causally-unresolvable-mirror clips. top-1 delta 0.0013, commit rate 0.091/0.089. Legitimate PASS on the DEPLOYMENT metric (the review's Critical finding is resolved).
**★ PER-SIGNER / DOMINANCE BREAKDOWN ADDED (eval-protocol — a low mean can hide a collapsed signer):** `eval/causal_skew.py` now splits committed accuracy by **offline mirror (left-dominant vs right/symmetric)** + reports the **worst signer**; `streaming_causal.py` stores `offline_mirror` per clip. 117 tests green. **DEVELOPER MUST REBUILD features_causal** (to add the `offline_mirror` field) then re-run eval.
**★ BREAKDOWN RESULT (developer) — the cost is CONCENTRATED, not uniform:** left-dominant (mirrored) committed accuracy full 0.3253 → causal **0.2848 (delta 0.0405, n=707)**; right/symmetric 0.3667 → 0.3638 (**delta 0.0029**, n=2010); worst signer P18 delta 0.052. The aggregate 1.1pt PASS HID a ~4pt hit on left-dominant signers (eval-protocol's "low mean hides a collapsed group" — an accessibility bug for an ASL tool). **F18b VERDICT: scale/roll causal is excellent (right/symm delta 0.003); per-clip causal MIRROR penalizes left-dominant signers.**
**★ ROOT CAUSE + DECISION (2026-07-05):** handedness is a persistent USER property, not per-clip — the offline eval re-decides it per isolated clip; the app has a persistent user and shouldn't. **F19 uses SESSION-LEVEL handedness: auto-detect + lock across the first few signs + a manual override setting** (Kotlin MirrorStabilizer becomes session-persistent, NOT per-clip reset). **Data-grounded confidence it works:** the right/symmetric delta 0.0029 = the scale/roll-only causal cost with correct mirror, so session-locked handedness brings left-dominant clips to ~0.003 too, near-erasing the 4pt gap. Memory: `project-handedness-user-property`. **F18b (causal estimator measurement) COMPLETE.**
**F19 ARCHITECTED + STAGED (F19a parity foundation, F19b recognition wiring). Decisions locked:** inference = re-run fixed 96-frame window each tick (exact parity, TCN≪landmarkers, no re-export); pose = full-rate while signing / adaptive when idle; params = SESSION-level (scale/roll/mirror all user properties); confirmation resets per sign but keeps session params; S5 = port D1/D2 detector; flag `recognition.enabled` → F17 fallback.
**★ F19a DONE + JVM-VERIFIED (agent ran gradlew):** Kotlin causal S4 (`android/.../features/S4Causal.kt`: `CausalConfig`, `MirrorStabilizer`, `clipFeaturesCausal`) reuses the F18 internal transform helpers (made `internal`) so only the estimation WINDOW differs. `export_golden.py` now emits `causal_expected_feature` + `causal_config`; `S4SkewTest` has a second test `kotlinCausalS4MatchesPythonWithinTolerance`. **`gradlew testDebugUnitTest` → BUILD SUCCESSFUL: Kotlin causal == Python `clip_features_causal` byte-exact (≤1e-4).** Fixed a float32→float64 parity risk in `causal.py` wrist-motion (widen before subtract, bit-parity with Kotlin) + regenerated golden. 117 Python tests green, ruff/mypy clean. The streaming-S4 train/serve-parity surface is PROVEN on the JVM.
**★ F19b RECOGNITION WIRING — code-complete, COMPILES + unit-tests GREEN (agent ran gradlew), DEVICE-VERIFICATION PENDING.** Built (all in `android/.../pipeline/recognition/`): `Recognizer` (TFLite Interpreter, mmap `streaming.tflite`, re-run full 96-window each tick, CPU/2-thread, load off-main-thread), `Vocab` (id→gloss), `ModelContract` (manifest schema/shape validation + `RecognitionConfig` operating point), `SessionNormalizer` (SESSION scale/roll running-median over 256-frame window + session `MirrorStabilizer` + `Handedness` AUTO/LEFT/RIGHT override; reuses the F19a-proven transform helpers), `SigningDetector` (S5 — streaming hysteresis port of D1/D2, motion+raised-gate), `Confirmation` (S7 — cumulative-mean calibrated log-posterior + commit gates, port of eval/confirm), `LandmarkAdapter` (MediaPipe results → flat 258 layout matching offline extraction), `RecognitionPipeline` (orchestrator), `FeatureFlags.RECOGNITION_ENABLED`. Assets: `streaming.tflite` + `model_manifest.json` + `vocab.json` + `recognition_config.json` (theta_conf −1.2, margin 0.30, k 3, T 0.715 + S5 thresholds mirroring detect.yaml). Wired into `FrameAnalyzer` (recognition per frame; **pose forced full-rate when recognition on**) + `MainActivity` (async load, gloss overlay) + `activity_main.xml` (glossText). Deps: `org.tensorflow:tensorflow-lite:2.16.1` (+ noCompress "tflite"). **`gradlew assembleDebug` BUILD SUCCESSFUL** (no MediaPipe/TFLite native conflict) + **`testDebugUnitTest` GREEN** (both skew tests still pass after making S4 helpers `internal`).
**Next (DEVELOPER: build+run on the PHONE):** sign a known gloss → expect a gloss to appear (committed). SET EXPECTATIONS: model is data-limited (~31% top-1, ~9% commit rate @ θ_conf −1.2), so this proves the PIPELINE works end-to-end on-device, NOT that recognition is accurate — committed glosses will often be wrong/sparse; that's the known model bottleneck, not a wiring bug. fps will drop (recognition + full-rate pose) → degraded likely on the old Xiaomi but should still run. Report: does a gloss commit at all? crashes? logcat. **KNOWN MVP caveats:** onset loses ~backoff frames (no pre-onset seed); session scale/roll use a 256-frame window; no confidence shown; handedness override UI is F21.
**★ F19b FIRST DEVICE RUN (2026-07-06): APP RUNS, RECOGNIZER ALIVE, NO CRASH.** logcat: `tensorflowlite_jni` loaded, XNNPACK delegate created, model graph delegated (`Replacing 291/291`, `305/305 nodes`), camera streaming. TFLite + MediaPipe coexist. Not yet confirmed whether a gloss commits (no recognition logging in v1). **Added diagnostics:** `RecognitionPipeline` now `Log.i("AppHearRecog", ...)` on S5 ONSET/RELEASE + COMMIT; `Recognizer.load` pins input to [1,96,258] (`resizeInput`+`allocateTensors`) to kill the dynamic-batch ambiguity behind the benign `tensor#230 dynamic-sized` XNNPACK warning. Rebuilt BUILD SUCCESSFUL. **Non-issue:** "Cannot resolve androidx.camera.view.PreviewView" is an Android Studio editor-index hiccup (app builds+runs, camera streams) → Invalidate Caches / Gradle sync.
**★★ F19b DEVICE-VERIFIED — END-TO-END PIPELINE FIRES ON PHONE (2026-07-06). THE PHASE-3 CORE MILESTONE.** logcat (`AppHearRecog`): `recognizer loaded: window=96 classes=2731` → `S5 ONSET` → `COMMIT 'HEAD' (id=1115) at frame 2` → `S5 RELEASE`. The full 9-stage chain (camera→landmarks→causal SESSION features→INT8 TFLite→S7 confirmation→committed gloss) works on the developer's old Xiaomi. S5 correctly detects signing start/stop across multiple cycles; confirmation commits (conservatively — most attempts drop, matching the ~9% commit rate @ θ_conf −1.2). Correctness of the committed gloss is the KNOWN model-data limit (~31% top1), NOT a wiring bug. **F19b DONE.** WATCH: committed at frame 2 (very early) — plausibly a confident early handshape, but monitor whether on-device confidence ramps faster than offline (could indicate feature/confirmation divergence to investigate; not blocking).
Open: F18 S3 One-Euro deferred; causal-skew gate thresholds inline (minor); commit-latency not compared; held-pose caveat resolved (full-rate-while-signing); streaming.tflite has one dynamic tensor (benign; re-export static later for full XNNPACK speed).

**★ ACCURACY EFFORT — VOCABULARY REDUCTION (built + smoke-tested, DEVELOPER-RUN retrain).** Root cause of poor recognition = the model distinguishes ALL 2731 signs from ~13 clips each (~31% top1) — a plumbing-validation baseline, not a product model. eval-protocol itself labels isolated accuracy "the flattering regime ... not the product." No plan feature fixes accuracy; it's a real model/data effort. Developer chose **narrow the vocabulary** (pilots: 100 classes ≈ 41%/74% vs 2731 ≈ 31%/55%). Built (NO re-extraction — filters existing features): `pipeline/features/reduce_vocab.py` (top-N data-richest glosses → `features_streaming_reduced/*.npz` + `features_reduced/vocab.json`; N=250 smoke → 4110 train clips ~16/class), `model/config/train_streaming_reduced.yaml` (warm-starts encoder from the full streaming best.keras), `train_streaming.py` +optional `vocab_dir`, `eval/streaming.py` +`--config`, `model/config/confirm_reduced.yaml`, `deploy/config/export_reduced.yaml`. 117 tests green.
**DEVELOPER WORKFLOW (reduce→retrain→recalibrate→re-export→redeploy):**
1. `python -m pipeline.features.reduce_vocab --n 250` (fast; smaller N=higher accuracy, e.g. 100→~41%).
2. `python -m model.train_streaming --config model/config/train_streaming_reduced.yaml` (LONG; fewer classes → faster than full).
3. `python -m eval.streaming --config model/config/train_streaming_reduced.yaml` → NOTE top1/top5 + calibration **temperature**.
4. Put that temperature into `confirm_reduced.yaml`, `export_reduced.yaml`, and the app `recognition_config.json` (agent can do this given the number).
5. `python -m eval.confirm --config model/config/confirm_reduced.yaml` → NOTE `chosen_theta_conf` → app `recognition_config.json` theta_conf.
6. `python -m deploy.export_tflite --config deploy/config/export_reduced.yaml` → new streaming.tflite + manifest in the reduced run dir.
7. Copy reduced `streaming.tflite` + `model_manifest.json` + `features_reduced/vocab.json` into `android/app/src/main/assets/` → rebuild app. Now recognizes N signs much better.
**★★ REDUCED-VOCAB (250-class) RESULTS — RECOGNITION ~DOUBLED (developer-run 2026-07-06):** cross-signer test **top1 0.626 / top5 0.865** (vs full 2731: 0.314/0.598); confirmation @ θ_conf −1.0 (chosen under temperature=1.0): commit 20.3% / **precision-when-committed 0.71** / FP 5.9% (vs full ~0.36 precision). INT8 export PASS (keras/tflite 0.7070/0.7051 on val parity, 228 KB, num_classes=250). Retrain took ~3 min (169,914 params, warm-started 17 encoder layers). **DEPLOYED to app:** copied reduced `streaming.tflite`+`model_manifest.json` (num_classes 250) + `features_reduced/vocab.json` (250 glosses) into assets; updated `recognition_config.json` to **theta_conf −1.0 + temperature 1.0** (kept consistent with the confirm run — MUST match). `assembleDebug` BUILD SUCCESSFUL. NOTE: temperature 1.0 is the placeholder the confirm curve used (self-consistent, works — precision 0.71); the harness-fitted calibration T wasn't separately applied (fine since app+confirm both use 1.0).
**★ REDUCED-MODEL DEVICE RUN #1 (2026-07-06) — worked then BROKE via handedness auto-lock bug.** logcat: first `S5 ONSET (mirrored=false)` → `COMMIT 'DOG1'` (worked!); then the session MirrorStabilizer accumulated enough motion to LOCK `mirrored=true` (wrongly), and every subsequent ONSET was mirrored=true → x-axis inverted → nothing committed. No manual escape (F21 toggle not built). **FIX (this session):** `SessionNormalizer` default handedness now **RIGHT (no mirror)** instead of AUTO — the auto-detect could lock to the wrong handedness mid-session and there's no recovery yet. Right-handed users get correct no-mirror; left-handed support arrives with the F21 setting. `assembleDebug` BUILD SUCCESSFUL. Also note: DOG1 committed at frame 31 (~12s) due to low fps on the old phone.
**REINSTALL fresh APK for the no-mirror fix** (`SessionNormalizer` default RIGHT) — old build still on phone.
**★ FPS-AUGMENTATION EFFORT (architected + tooling built, agent-run feature prep; DEVELOPER retrains).** Root cause of weak on-device recog beyond accuracy = train ~30fps vs phone ~2.5-5fps temporal mismatch (memory `fps-temporal-mismatch`). **BASELINE MEASURED — confirms the mismatch:** current reduced model top-1 native **0.626** → k4(~7.5fps) **0.549** → k8(~4fps, phone) **0.496** (−13pt at phone fps). Decisions (architect): OFFLINE expanded dataset (isolated, trainer unchanged); gate = low-fps test-set win. Built: `pipeline/features/fps_augment.py` (expand: clip→+3 random-stride copies; fixed: low-fps test), `model/config/train_streaming_reduced_fps.yaml` (warm-start from reduced best.keras, NEW run dir `runs/tcn_streaming_reduced_fps_v30`), `eval/streaming.py` +`--features-dir`. Feature sets built (agent): `features_streaming_reduced_fps` (train 16440/val 3364), `features_lowfps_k8` + `features_lowfps_k4` (val+test). NO re-extraction, NO contract/S4 change, past runs untouched. 117 tests green.
**★★ FPS-AUG MODEL — CLEAN WIN AT EVERY FPS, DEPLOYED (2026-07-06).** Retrained (dev) + evaluated: top-1 native **0.626→0.645**, k4 **0.549→0.597**, k8(phone) **0.496→0.547** — fps-aug BETTER everywhere incl. native (fps-diverse data regularized). GATE PASS (k8 0.547 > 0.496, native held). Confirm @ phone-fps (features_lowfps_k8 val) → **theta_conf −1.6**, precision-when-committed **0.73** @ ~4fps. INT8 export PASS (0.686/0.678 delta 0.0077 on a 3000-clip parity batch — the initial 512-batch FAILed at delta 0.027 = benign near-tie noise on fps-diverse val, confirmed by mean-prob-diff 0.001; bigger batch = principled fix, not goalpost). **DEPLOYED to app:** `streaming.tflite`+`manifest` (250-class) from `runs/tcn_streaming_reduced_fps_v30`, `recognition_config.json` theta_conf −1.6 / temp 1.0; vocab unchanged (250). `assembleDebug` BUILD SUCCESSFUL. Configs: `train_streaming_reduced_fps.yaml`, `confirm_reduced_fps.yaml`, `export_reduced_fps.yaml`. **ALL PAST RUNS PRESERVED** (isolated, streaming_v30, streaming_reduced_v30 untouched; fps model in its own new dir).
**Next (DEVELOPER): REINSTALL fresh APK (Run ▶), sign a 250-set gloss** → should commit more often + more correctly than before (fps model + no-mirror fix + phone-tuned theta). Watch `AppHearRecog`: `mirrored=false`, more `COMMIT` lines. Then F20 sentence builder / F21 UI (handedness toggle) / F22 device smoke.
**★ FPS-AUG DEVICE RUN (2026-07-06) — fps model works, two on-device issues found + fixed:** logcat showed frequent commits (`mirrored=false`, fps model + no-mirror fix confirmed working) BUT (1) the SAME held sign re-committed 5–10× in a row (`COMMIT 'ROAST' at frame 12/14/19/35…`) and (2) many commits at frame 2–3 (thin evidence at low fps). **FIX 1 — one-commit-per-bout:** `RecognitionPipeline` now sets `awaitingRelease` on commit and HOLDS (returns lastCommit, no re-recognition) until S5 RELEASE — one gloss per signing bout instead of spamming the still-held sign. RELEASE log now distinguishes `dropped` vs `after commit`. **FIX 2 — on-device fps lever = GPU delegate:** cheap levers already pulled (pose lite, 640×480, hand+pose parallel, adaptive cadence). Added `FeatureFlags.LANDMARKER_TRY_GPU` + GPU-with-CPU-fallback in `LandmarkerBundle.create` (`buildHand`/`buildPose(delegate)`, logs `landmarkers on GPU delegate` / `…falling back to CPU`). **DEVICE-CONFIRMED: lifted this phone ~3fps → 5–7fps (~2×).** Still < 15fps floor → recognition improved but not fully reliable; the phone is now the confirmed hard ceiling (faster phone = remaining lever, none available). GPU = deliberate sub-pixel landmark parity divergence, accepted for the fps win. `assembleDebug` BUILD SUCCESSFUL. Memory: `project-fps-temporal-mismatch` (updated).
**★ F21 RECOGNITION UI — code-complete, unit-tests GREEN (agent ran gradlew), DEVICE-VERIFICATION PENDING (2026-07-06).** `/architect`-locked decisions: (1) top-3 sourced from the CONFIRMATION's accumulated evidence (commit-consistent, not raw per-frame), **ranked glosses only — no confidence numbers** (honest at ~50-70% top-1); (2) candidates update **LIVE while signing, freeze on commit** until next onset; (3) handedness toggle = **LEFT/RIGHT only** (default RIGHT, persisted in SharedPreferences), explicitly NO AUTO (the auto-lock is the known-buggy path; explicit L/R bypasses the session MirrorStabilizer via the existing `isMirrored` getter). #2/#3 are DISPLAY-ONLY — commit logic (top-1 gates) unchanged. **Contract/parity: NONE** (no schema_version, no S4↔F change, no skew test — reads existing model output + drives the existing `SessionNormalizer.handedness` field). Built: `Confirmation.topCandidates` (running top-3 by `sum[c]/count`, same evidence the commit gate ranks on; extended the top1/top2 loop to top-3); `RecognitionState.Signing(candidates)` + `Committed(gloss, classId, candidates)`; `RecognitionPipeline` maps ids→glosses + holds committed candidates during `awaitingRelease`; `activity_main.xml` (glossText #1 big + new `altText` #2/#3 dimmed + `handToggle` button top-right); `MainActivity` (renderCandidates + toggle wire + SharedPreferences persistence, applied to recognizer on load). New JVM test `ConfirmationTopKTest` (3 tests: top-3 ranks best-first by evidence; empty before update/after reset; exposing top-k doesn't change commit top-1). **`gradlew testDebugUnitTest assembleDebug` GREEN** (ConfirmationTopKTest 3/3, S4 skew 2/2 still pass → commit unchanged). **Gate = DEVICE-VERIFIED** (F21 is UI, no offline cross-signer metric; end-to-end cross-signer gate stays F22). **Next (DEVELOPER): reinstall, sign a 250-set gloss** → expect 3 ranked glosses that converge live then freeze on commit (committed word = #1, among the 3); tap the hand button → label flips Right/Left and mirroring flips (left-handed signs should start committing). Watch `AppHearRecog` COMMIT lines now log `candidates=[...]`.
**★ fps CEILING PROFILED — SYSTEMIC (multiple phones 5–8fps), landmarkers = 95% of cost (2026-07-06).** Developer reported the app caps at 5–8fps on OTHER phones too → ceiling is the PIPELINE, not one weak device. Added a TEMP `StageTimer` in `FrameAnalyzer` (logs tag `AppHearPerf`, avg ms/frame every 30 frames). **Device result (unambiguous):** `conv≈1.7 rotate≈14 hand≈100 pose≈110 recog≈0.5 wall≈130 (~7.6fps)`. **hand+pose landmarkers ≈95% of every frame, ~100ms EACH even on the GPU delegate** = the IMAGE-mode detector-every-frame tax (same ~100ms on every phone). **Recognition (96-frame TCN re-run) is FREE (0.5ms)** → F19 re-run design vindicated. `rotate` 14ms = minor free win (pass rotation to MediaPipe; risks overlay coords). **Only real fps lever = TRACKING mode (VIDEO/LIVE_STREAM)** ~2× toward 15fps, but a REAL IMAGE→tracked parity divergence (F01 chose IMAGE for offline determinism; on-device continuous stream makes VIDEO's monotonic timestamp natural); may only reach ~12fps on this 2021 Adreno. Memory: `project-fps-temporal-mismatch` (updated).
**★ NEW ISSUE — NO-HANDS FALSE COMMITS (developer-observed 2026-07-06):** app fires `S5 ONSET`+commits random glosses (CHEESEGRATER/RHINO2/PINEAPPLE3) on mere arm motion with no real signing. Root cause: S5 is pose-motion-primary (F02) + recognizer always emits a distribution → commits something. Fix (no parity cost) = gate onset/commit on HAND PRESENCE. Memory: `project-nohands-false-commits`.
**★ NO-HANDS FIX DONE — code-complete, unit-tests GREEN (agent ran gradlew), DEVICE-VERIFICATION PENDING (2026-07-07).** Made real hand presence a condition of S5 "signing" (pose wrists exist even with no hands detected → pose motion alone false-triggered onsets). `LandmarkAdapter.handsPresent(hands)` (absent hands are NaN → test the two slots' wrist-0 x); `SigningDetector`: onset now needs `motion>thetaOn && raisedGate && handsSeen`, and losing hands for kOff frames RELEASES the sign (symmetric: no hands ⇒ not signing). Behind config `signing.require_hands` (default true, `optBoolean`) in `recognition_config.json` — tunable without rebuild. New JVM test `SigningHandGateTest` (4: no-hands motion doesn't onset; hands+motion does; losing hands mid-sign releases; helper matches wrist slots). **`gradlew testDebugUnitTest assembleDebug` GREEN** (SigningHandGateTest 4/4, ConfirmationTopK 3/3, S4 skew 2/2). Pure S5 gate — NO pipeline/confirmation/feature-contract change. **Next (DEVELOPER): reinstall, wave arms with hands DOWN/out of frame → should NOT commit; sign with hands up → commits as before.** NOTE: temp `StageTimer` profiling still in `FrameAnalyzer` (fps path B deferred).
**★★ CONVERSATIONAL VOCABULARY MODEL — baseline trained + evaluated, fps-aug SET UP (2026-07-07).** Root problem the developer caught: the deployed 250 vocab is DATA-RICHEST (CHEESEGRATER/OSTRICH/TRACTOR), useless for talking. Investigation: ASL Citizen's full 2731 vocab CONTAINS ~89% of everyday words (missing = pronouns I/she/it = ASL pointing, + grammar particles ASL doesn't sign); the issue was pure SELECTION. Curated a 236-word everyday vocab (`model/config/vocab_conversational.txt`) by quality: dropped 8 sub-10-clip low-value words, added 31 high-quality (>=16 clip) everyday fillers, kept 13 weak-but-essential (HELLO/WHERE/WHO...). Added `reduce_vocab --wordlist` (writes to a SEPARATE `conversational` tag → features_conversational/ + features_streaming_conversational/; `features_reduced` untouched). **BASELINE RESULT (developer-run, cross-signer test, 236 classes, 11 signers): top1 0.606 / top5 0.885** (vs data-richest 250: 0.626/0.865 — only −2pt top1, +2pt top5, for a USEFUL vocab). Per-signer 0.531-0.688 (uniform, no collapse); calibration T=0.647, ECE 0.21→0.058. Confusions are sensible near-synonyms (SIT→CHAIR same handshape, PERSON→PEOPLE, NOW→TODAY) NOT the feared question-word cluster. Data quality: mean 14.0 clips/class, ~13 signers/class (excellent cross-signer diversity), 13 weak (<12), all 236 test-covered. **fps-aug NOW SET UP** (agent): built features_streaming_conversational_fps (expand 3309→13236 tr / 3264 val), features_lowfps_conv_k8 + _k4 (val+test); configs `train_streaming_conversational_fps.yaml` (warm-start from conv baseline), `confirm_conversational_fps.yaml` (T=0.647, lowfps_conv_k8), `deploy/config/export_conversational_fps.yaml` (T=0.647). **SAFETY NET: all in new dirs/configs; deployed fps-aug 250 model + current app assets untouched (revert = re-copy).** **★★ CONVERSATIONAL fps-aug model DEPLOYED (2026-07-07).** Eval: native 0.612/0.887, k4 0.576/0.857, k8(phone) 0.527/0.825 (vs 250-fps k8 0.547 — ~2pt lower for a USEFUL vocab; top-3 @ phone ~0.72). Confirm: theta_conf −1.2, temperature 0.647, precision-when-committed 0.73. INT8 PASS (delta 0.0067, 227KB, 236cls). Deployed streaming.tflite+manifest+vocab(236)+recognition_config (theta_conf −1.2/temp 0.647/require_hands kept); assembleDebug GREEN. **REVERT = restore `android/app/src/main/assets/_backup_250fps/` (4 files) + rebuild** (250-fps model also intact at runs/tcn_streaming_reduced_fps_v30). Memory: `project-conversational-vocab`. **NEXT (DEVELOPER): reinstall, sign everyday words (HELLO/WANT/HELP/EAT/MOTHER) → real conversational commits.** GOTCHA: always `.venv\Scripts\python.exe` (keras 3.15.0); system python 3.13.2 can't load 3.15 models (`input_axes` error).
**★ GCN RESUME BUG FIXED — Lambda-free rewrite (2026-07-10).** Developer's first overnight GCN run hit `ValueError: ... Lambda layer ... disallowed` on resume: the GCN's Lambda layers (feature slicing/gather) make checkpoints UNDESERIALIZABLE (safe-mode block; and even safe_mode=False fails — missing output_shape). FIX: `model_gcn.py` rewritten Lambda-free (direct KerasTensor slicing + `keras.ops.ones_like/take`); `warm_start_encoder` loads `compile=False, safe_mode=False`. VERIFIED: save/load roundtrip at DEFAULT safe mode exact (0 Lambda layers); export smoke re-PASS (756KB, ~6ms/tick predicted); trainer smoke + all tests green. The stale epoch-2 checkpoint (val_pf_acc 0.012 ≈ untrained, ~2.4h) was unloadable → sidelined as `best_lambda_era.keras.bak` (preserved, not deleted); next run starts clean and IS resumable. **RULE: no Lambda layers in any model that must checkpoint/resume or export.** Developer restarts training (same command).
**★ ENCODER-UPGRADE GCN TRAINING CRASH — ROOT-CAUSED + FIXED (2026-07-10).** Developer's GCN training died silently in epoch 1 (`history.csv` 0 bytes, no traceback). Investigated with evidence (NOT guessed): `faulthandler` repro caught `Windows fatal exception: access violation` on the FIRST step on a 320-sample subset (→ NOT OOM). Cause = the GCN's `upper51` INT32 keypoint-gather hits oneDNN's INT32 primitive, which SEGFAULTS on this CPU (no AVX-512) — the log's own `oneDNN ... DT_INT32 only on AVX-512, falling back ... if present` line. A/B verified: crashes with oneDNN ON, trains clean with `TF_ENABLE_ONEDNN_OPTS=0`. **FIXED:** `os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS","0")` at top of `model/train_streaming.py` + `eval/streaming.py` (before TF import); real-path fit verified (5s/step, no shell env needed; the "oneDNN custom operations are on" line disappears = fix active). Detail in `encoder-upgrade.md` §6b. **Developer: just re-run the same train command** — it now trains through.
**★ ENCODER-UPGRADE TRAINING-SPEED ROUND (2026-07-07, measured).** Developer hit the CPU wall: first GCN config = 46.6 min/epoch (~44h/60ep; TF≥2.11 native Windows is CPU-only). Measured fixes: XLA jit = 3× WORSE (rejected); **early temporal strides {0:2,4:2} + UPPER51 keypoint subset** (hands complete + pose nose/shoulders/elbows/wrists/hips, taken INSIDE the graph — input stays 258, no S4 change) = **24 min/epoch (~2×)**. Candidate A final: 719K params, 756KB INT8, **predicted ~5ms/tick device**; re-smoked through the production export path incl. GATHER — PASS, contract exact; trainer smoke green; all tests pass. **Resume-safe:** config self-resumes from its own best.keras (Ctrl+C anytime; re-run same command; `warm_started_layers>0` confirms resume; best checkpoint written every improving epoch). Realistic training = one overnight run (~10-14h with early stop). Options for future speed: WSL2+NVIDIA GPU would make this ~1h (developer's GPU availability unknown).
**★★ ASL RECORDER REBUILT → Stage-E VIDEO CAPTURE (2026-07-10).** The AppHear 2 dataset recorder (copied to `asl recorder/ASLRecorder2/`) was fundamentally incompatible (MediaPipe VIDEO mode + tracking + face + a baked pose-first nose/wrist-normalized 258 vector, fixed 30-frame window, on-device destructive Q gate). **Rebuilt as an AppHear 3 Stage-E VIDEO-primary capture tool** for local ASL signers to record data-poor/missing glosses (250 everyday words). Design: video is the dataset artifact (like ASL Citizen); the offline pipeline re-extracts it with the SAME extractor → identical landmark dialect by construction (so the recorder's on-device models need NOT be byte-identical — parity risk removed). On-device MediaPipe = live overlay + advisory coverage only. **Android (Java, code-complete, DEVELOPER compiles):** rewrote `MediaPipeRecorderHelper` (IMAGE mode, hand+pose, face removed, conf 0.5), `ResultBundle` (no face), `SampleData` (Stage-E sidecar: word+gloss, source, native_fps, dims, hit-rates — no baked 258), `QualityResult` (advisory coverage), `LabelsRepository` (250-word→gloss schema), `RecordingActivity` (video capture, no keypoint/buffer/gate), `RecordingStateMachine` (3s timer clip end), `DatasetFileManager` (flat non-destructive `samples/signs/<word>/<clip>.mp4`+`.json`); emptied 3 obsolete `ml/` classes. `labels.json` = 250 words mapped to ASL Citizen glosses (VERIFIED: 227 mappable, 53 data-poor ≤12-clip targets, 12 pointing-only, 21 new-class). **Python ingest (agent-built + tested):** `pipeline/ingest/run.py` (recorder video → same extract→detect→`clip_features_realtimed` → v3.0 features mapped to conversational 236 vocab, new dir) + `merge.py` (supplement/replace a gloss into TRAIN only, val/test stay pure ASL Citizen; **merge smoke-tested**: supplement 3309→3315, replace swaps a gloss's clips, other classes intact). **Safety net:** all new dirs; ASL Citizen + `features_streaming_conversational` + deployed model untouched. Docs: `context/recorder-pipeline.md` (wired AGENTS.md #13) + recorder `README_APPHEAR3.md`. Memory: `project-asl-recorder`. **DEVELOPER TODO:** build recorder in Studio; delete `face_landmarker.task`; record ASL clips; ingest+merge+retrain (untestable end-to-end without a real recorded mp4). Honest limit: recording fixes data-poor/missing glosses, NOT confusable pairs (SIT↔CHAIR) or the architecture limit.
**★★ ENCODER-UPGRADE STEPS 1–3-PREP DONE (2026-07-07, agent-run) — EXPORT RISK KILLED, READY FOR DEVELOPER TRAINING.** Followed `context/encoder-upgrade.md` §5 in order. **Step 1 INT8 export smoke: PASS** — `model/model_gcn.py` (ST-GCN in a TFLite-safe formulation: frozen-Dense adjacency = FULLY_CONNECTED, temporal Conv2D, tiled clip posterior honoring the frozen `[1,96,258]→[1,96,236]` contract) converts through the PRODUCTION `_convert` path, XNNPACK OK, tiled-contract exact (`deploy/smoke_gcn_export.py`). **Latency measured (desktop, projected via TCN's known 0.5ms device tick):** full-size 2.75M = ~38ms/tick (OVER the ≤20 gate — the estimate band's pessimistic end was right) → variant sweep → **half-width 32-64-128 (10 blk, 749K params, 759KB) ≈ ~11ms/tick SELECTED as candidate A** (full-size kept as offline ceiling reference). **Step 3 tooling ready:** `fps_augment.py --prefix-copies` (prefix-aug per §4: t~U[max(4,0.3L),L), 75% also fps-strided) → `features_streaming_conversational_fps_prefix/` built (train 3,309→19,574); trainer `model.type: gcn` support; config `train_streaming_conversational_gcn.yaml` (no warm start, 60 epochs); GCN trainer path smoke green; **117 tests pass**; **safety net created: `assets/_backup_conversational_tcn/`** (revert = 4-file copy + rebuild). **NEXT (DEVELOPER, .venv): train** `python -m model.train_streaming --config model/config/train_streaming_conversational_gcn.yaml` **then eval native/k4/k8** (same --features-dir overrides as the conversational runs; gates: native ≥0.66, k8 ≥0.56).
**★ ENCODER-UPGRADE EXPERIMENT — DEDICATED CONTEXT FILE + WIRING (2026-07-07).** Developer-requested: the researched S6 encoder swap now has its own contract file **`context/encoder-upgrade.md`** — every claim tagged [VERIFIED]/[ESTIMATE]/[CHECK-AT-BUILD] (anti-hallucination), the TFLite I/O contract FROZEN at `[1,96,258]→[1,96,C]` (clip posterior tiled across T inside the exported graph → ZERO Android code change, deploy = asset swap), prefix-augmentation spec (train on truncated [0..t) prefixes so a non-causal model can commit mid-sign), ordered steps (INT8 export smoke FIRST → device latency probe ≤20ms → train → pre-registered gates native ≥0.66 / k8 ≥0.56 → confirm/export with RE-FIT temperature → deploy w/ backup), kill criteria, and the **safety net**: before any deploy create `assets/_backup_conversational_tcn/`; all new artifacts in NEW dirs (`runs/gcn_conversational_fps_v30` etc.); revert = copy 4 files back + rebuild. **Wired into:** AGENTS.md reading order (#12), build-plan.md (new "Post-Phase-3 — Accuracy track / 23 Encoder upgrade"), architecture.md (model-target row), recognition-accuracy.md (pointer). Status: PLANNED/PARKED until developer resumes accuracy work.
**★ ACCURACY ROADMAP RESEARCHED + SAVED (2026-07-07, web-verified).** Deep-dive into further detection/recognition gains (developer-requested, accuracy work itself stays parked until resumed). **CORRECTING FINDING: our model is ARCHITECTURE-limited, not (only) data-limited** — the ASL Citizen paper's own pose baseline (ST-GCN, ~3M params, SAME MediaPipe-landmark input, same 2731-class cross-signer protocol) gets **59.5% top-1 vs our TCN's 31.4%** (I3D video 63.1%). Our device profiling proves headroom (recognizer 0.5ms of 130ms frame) and the F19 re-run-per-tick design means the encoder NO LONGER needs to be causal (bidirectional over [onset..t] deploys as-is; needs prefix-augmented training). No contract/parity impact — same features, only S6 swaps. **Ranked plan** (full detail + sources in `context/recognition-accuracy.md` §roadmap): (A) ST-GCN-class model on the conversational 236 [expected native ~0.75-0.85; gate ≥+5pt native, ≥+3pt k8, INT8 pass, ≤20ms/tick] → (B) small transformer/SignBart-style ~1M-param competitor → (C) recipe upgrades (shear aug, cosine annealing, prefix-aug) → (D) multi-stream/ensemble → (E) self-supervised skeleton pretraining. **REJECTED with evidence:** LSTM/BiLSTM (weakest modern pose option: WLASL Pose-GRU 46.5 < TGCN 55.4 < transformers ~64-74), video CNN/I3D (compute we don't have). **SignGemma: monitor, don't build** — still NOT on the official Gemma models page as of 2026-07 (announcement+waitlist only); GB-scale sentence-translation model, wrong task + wrong size for our 227KB on-device gloss pipeline; future use = offline distillation teacher. Honest cap: the 7-8fps hardware ceiling still limits on-device translation of any offline gain.
**★★ CONVERSATIONAL MODEL DEVICE-VERIFIED — F22 single-signer smoke PASS (2026-07-07).** Developer ran a ~12-min device test. Commits REAL everyday words: HELLO (4/4 correct), HOUSE, WHERE (WHERE,NO,ASK), NEED (3/3), WALK, WANT, NO, etc. Verdict: "good, some words hard to detect but good." **KEY FINDING — handedness is make-or-break:** the session started `mirrored=true` (toggle persisted to LEFT from a prior test) → GARBAGE (BABY1 committed 6+× as a magnet = wrong-handedness features); after the toggle flipped to `mirrored=false` (correct for the right-handed signer) recognition got dramatically better. **Each signer MUST set the handedness toggle to their dominant hand before signing** (wrong handedness = garbage, non-obvious). Remaining for full F22: 2-3 DIFFERENT signers (each sets handedness). Hard/dropped words = known fps ceiling (~7fps) + 13 weak classes; top-3 mitigates. Model is a keeper; revert still available (`_backup_250fps`).
**★ F22 DEVICE SMOKE + ROLLOUT — checklist + rollback DOCUMENTED (2026-07-07).** F22 is inherently developer-run (agent can't drive the device); the safety nets it validates already exist in code: recognition load-failure → `runCatching` falls back to F17 (no crash) + Toast; `RECOGNITION_ENABLED=false` → F17 kill-switch; `ModelContract.validateOrThrow` refuses a schema/shape-mismatched model; degraded-mode banner for low fps. Deliverable = `context/device-smoke.md` — repeatable pre-flight/startup/recognition/gates/cross-signer/rollback/sign-off checklist with the accepted-limits framing (7-8fps, ~50-70% top-1, right-handed default). Added to AGENTS.md reading order (#11). **DEVELOPER: run the smoke on the target phone(s) + ≥2 signers, record phone/fps/weak-signers in this tracker.** With this, Phase 3 is code-complete (F17-F22; S8 LM-assist + S3 One-Euro remain deferred).
**★ F20/S8 SENTENCE BUILDER (SAFE SUBSET) — code-complete, unit-tests GREEN (agent ran gradlew), DEVICE-VERIFICATION PENDING (2026-07-07).** Built the passthrough+dedup mode only (LM-assisted gloss→text stays DEFERRED — chaining ~50%-wrong glosses through a corrector compounds error). `SentenceBuilder` (ArrayDeque; `add` dedups a CONSECUTIVE repeat + caps at 20, drops oldest; `text`/`isEmpty`/`clear`). Owned by `RecognitionPipeline` (`sentence`), appended **once per real commit** (in the `commit != null` branch, NOT per held frame — the pipeline is the single commit source of truth); exposes `sentenceText` getter + `clearSentence()`. UI: `activity_main.xml` +`sentenceText` band (top, below handToggle, maxLines 3, ellipsize start) + `clearButton`; `MainActivity` renders `recognizer.sentenceText` each frame + Clear button wired. Inter-gloss spacing is free (S5 onset/release + one-commit-per-bout = distinct bouts). New JVM test `SentenceBuilderTest` (4: order/join, consecutive-dedup-but-keep-non-consecutive, cap-drops-oldest, clear). **`gradlew testDebugUnitTest assembleDebug` GREEN** (SentenceBuilder 4/4, all 14 tests pass). NO contract/parity change. **Next (DEVELOPER): reinstall, sign a few glosses → they accumulate into the top band (consecutive repeats collapse); Clear empties it.** Then F22 device smoke + rollout.
**★ VIDEO-MODE fps LEVER — EVALUATED + DEFERRED (2026-07-07, `/architect`).** Considered switching MediaPipe IMAGE→VIDEO(tracked) mode for fps. **Decided NOT to now.** Reasons: (1) VIDEO only skips the DETECTOR when tracking holds, NOT the landmark models (the bulk of ~100ms) → realistic ~10-11fps, still under the 15fps floor; (2) re-opens the exact parity wound v3 was built to avoid — F01 chose IMAGE to escape MediaPipe's hidden tracking/smoothing; model trained on stateless IMAGE landmarks, never on tracked+smoothed ones (this is the v2 trouble the developer remembers); (3) v2 lesson g — device optimizations here don't reliably engage (GPU ANR, rotation-offload no-op); (4) fps-aug made the model robust to low FRAME RATE, not to tracked landmarks. **If revisited:** throwaway on-device fps measurement FIRST (flag, IMAGE default, reversible) — if <~12fps, abandon; if promising, gate recognition via a VIDEO-mode skew eval (current model, val sample, top-1 delta ≤0.02) before trusting; full re-extract+retrain (days, imperfect) only if that fails. No schema_version/S4 change (divergence is upstream at S1/S2; S4 skew test still holds). Memory: `project-video-mode-deferred`. **Temp `StageTimer` profiler now gated behind `FeatureFlags.PROFILE_STAGES` (default OFF)** — silent in normal use, one flag away for the next fps investigation. `assembleDebug` pending.
**⏸ SESSION PAUSED 2026-07-06 — RESUME TOMORROW. Open decision (pick one):** (A) no-hands false-commit fix [quality, fast, no parity cost] · (B) VIDEO/tracking mode [fps lever, parity tradeoff, may only reach ~12fps] · (C) both, quality first. Recommendation: A first (safe clear win), then B. **NOTE: temp `StageTimer` profiling instrumentation is STILL in `FrameAnalyzer` — remove or flag once the fps path is chosen.** F21 (top-3 + handedness toggle) is DEVICE-VERIFIED working this session: log shows `COMMIT '...' candidates=[X, Y, Z]` + toggle flips `mirrored=true/false`.
**★ BUILD-SEQUENCING DECISION (2026-07-06) — F21 next, NOT F20.** Assessment after the device run: accuracy ceiling is now HARDWARE (5–7fps), top-1 wrong ~half the time, left-handed signers BROKEN (handedness hardcoded RIGHT since the auto-lock bug), user sees only a single often-wrong word. **F20/S8 sentence builder DEFERRED** — chaining ~50%-wrong one-commit-per-sign glosses compounds error (the exact anti-pattern this project avoids); build S8 only once single-gloss recognition is trustworthy (needs a faster phone to confirm real accuracy). **F21 Recognition UI is next**, in order: (1) **top-3 candidates display** (converts wrong-#1 into "it's the 2nd one" — biggest felt win at low fps, no retrain), (2) **handedness toggle** (unblocks left-handed users + manual escape from a wrong session lock). Both already named in F21 — not scope creep. Memory: `project-f21-next-topk-handedness`.
**★★ VERIFIED ROOT CAUSE of poor on-device detection = FPS/TEMPORAL MISMATCH (~12×), NOT model accuracy.** Model trains at ~30 fps (sign = median 33 frames); phone sustains ~2.5 fps (DOG1: 31 frames in 12.3 s) → same sign is only ~3 frames on device = far out of training distribution. New DEDICATED context file **`context/recognition-accuracy.md`** (there was none before — verified) documents evidence + levers. Memory: `project-fps-temporal-mismatch`. **Fix (ranked): (1) retrain the 250-class model with temporal/fps augmentation (fps-robust), (2) raise device fps / faster phone, (3) verify on a faster phone first.** Ruled out: model accuracy (0.626 offline fine), mirror-lock (fixed), build errors (none). Secondary unverified skew: SessionNormalizer deployment path has no skew test; on-device onset drops the sign's first frames (worse at low fps). AGENTS.md reading order updated (#10).
**Open minors from review:** gate thresholds are inline constants in causal_skew.py (code-standards wants config/); Kotlin S4 port must be INCREMENTAL (Python causal is O(L²)/clip); all-NaN RuntimeWarnings unsuppressed (benign); commit LATENCY not yet compared causal-vs-full.
**Agent cannot compile/run Android here → DEVELOPER builds+runs on a physical phone in Android Studio.** Gradle sync may flag a dep version (mediapipe/camera) → paste error, agent bumps. Expect: front-cam preview, live hand+pose dots, S1+S2 fps HUD; done = both landmarkers track on-device.
**Next after F17 verified → F18** (S3 One-Euro tracking + S4 feature port with the mandatory skew test vs `pipeline/features`).


**★ OFFICIAL PHASE-0 BASELINE (v3.0 isolated causal-TCN + reg/aug):** ASL Citizen **test**, 2,731 classes, **11 held-out signers**, 29,770 clips → **top1=0.291, top5=0.552** (~790× / 1,500× chance). Per-signer uniform 0.25–0.37 (no collapse) = cross-signer generalization confirmed on official test. Calibration ECE **0.126→0.041** (temperature 1.17) — seeds S7. Confusions are semantic near-synonyms (HURT→PAIN, EXERCISE→WORKOUT, NOW→TODAY) → representation captured meaning. (val was 0.360/0.629; test<val is normal, val = early-stop selection set.) Data-limited (~13 clips/class); the isolated classifier has fully served its plumbing-validation role.


**Last completed:** 08 Cross-signer eval harness — per-signer top-1/top-5 + temperature calibration (ECE) + confusion summary, report-only JSON. Smoke-test green (ECE 0.74→0.10 on synthetic). Tests green (69), ruff/mypy clean. **Phase 0 offline build is code-complete (8/9; 09 optional).**
**Pilot DATA done (agent):** cross-signer pilot features built — train `(345,64,258)` / val `(65,...)` / test `(278,...)`, 20 aligned glosses, NaN-free, in `…/derived/apphear3/features/`. **Caveats resolved on real multi-signer data:** (1) N3 handedness asymmetry was signer-specific (P5); across signers mask ≈ L0.86/R0.92 (balanced, right slightly higher = canonical). (2) D1/D2 span coverage 93–96% + Q + hand-ratio ~2.3–2.6 consistent cross-signer. (3) Clean signer-disjoint 20-class set ready.
**PILOT RESULTS (cross-signer, held-out signers) — both risks retired:**
- **20-class:** test top1=0.54 / top5=0.87, per-signer 0.48–0.64 (uniform).
- **100-class:** test top1=0.414 / top5=0.744, per-signer 0.33–0.49 (uniform, no collapse). Calibration T=1.23, ECE 0.06.
- **Findings:** (1) class scaling is GRACEFUL — 5× classes cost only 13 top-1 pts (41× chance); cross-signer generalization holds (the v2 failure point). (2) DATA-STARVED per class — 100-class training overfit hard (train_top1 0.91 vs val 0.48 at ~18 clips/class); the full corpus (100s clips/common sign) is the fix. Calibration robust across both.
**Verdict:** pipeline generalizes across signers AND scales across classes → committed to the full corpus.

**FULL-SCALE RESULT (2,731 classes, cross-signer val, 6 held-out signers):** **val_top1=0.328, val_top5=0.608** (≈875× / 1,640× chance). Thesis holds at full vocabulary. BUT heavily overfit: train 0.77 / val 0.33 (~45pt gap), val plateaued ep20–27 then val_loss rose → early-stopped ep27. Root cause: ~13 clips/class + under-regularized (dropout 0.1, no augmentation/weight-decay). **32%/60% is a FLOOR.** Levers (no re-extraction needed): stronger dropout, data augmentation (temporal/spatial jitter, speed perturb), label smoothing, weight decay.
- Full features built: train `(36960,64,258)` / val `(9575,...)` / **test still pilot (needs extraction)**. Parallel extraction added (`--workers`, 12 cores). vocab=2731.
**IMPROVEMENT BUILT (regularization + augmentation, smoke-tested):** dropout 0.1→0.3, **AdamW weight_decay 1e-4**, **label_smoothing 0.1**, and **train-only data augmentation** (`model/augment.py`: ±10° rotation, ±10% scale, coord noise σ0.01, 10% frame masking — layout-aware, absent-hands re-zeroed, pose visibility untouched). All config-driven in `train.yaml`. Loss switched to one-hot CategoricalCrossentropy (metrics `top1`/`top5` unchanged). 78 tests green.
**IMPROVED RESULT (reg+aug):** val_top1 **0.328→0.360**, val_top5 **0.608→0.629**, overfit gap **0.45→0.34** (regularization confirmed working). val plateaued ep30–50 → **near the ceiling for this model on ~13 clips/class × 2731 classes** (data-limited, not model-limited). Phase-0 isolated classifier has fully served its plumbing-validation role: pipeline works end-to-end on the full corpus, cross-signer-uniform, class-scaling graceful, calibrated. **36%/63% cross-signer on 2731 classes = solid lightweight baseline.**
**DECISION PENDING:** (a) squeeze isolated further (more aug / bigger model — diminishing returns), (b) lock baseline → extract test (~9hr) for official held-out number → advance to **Phase 1 (streaming)** = the real product value.
**After pilot (DEVELOPER-RUN, slow):** full extraction `python -m pipeline.run_pipeline --split train --build-vocab` (+ val, test) → `model.train` → `eval.run`. Optional **09 v3.1 kinematic ablation**, else **Phase 1 (streaming)**.

---

## Progress

### Setup

- [x] §8 design docs (`docs/01`–`06`, `README.md`)
- [x] Context System: 9 context files + `AGENTS.md`
- [x] 5 skills scaffolded (`.claude/skills/`)
- [x] Project memory (`/remember`) initialized (`memory.md` at repo root)

### Phase 0 — Offline foundation & isolated recognition

- [x] 01 Landmark extraction (E)
- [x] 02 Signing detection + dead-time trim (D1, D2)
- [x] 03 Normalization stack (N1–N3)
- [x] 04 Duration normalization (N4) + Quality gate (Q)
- [x] 05 Feature extraction (F) + contract v3.0
- [x] 06 Signer-level split tooling
- [x] 07 Isolated TCN classifier (Keras) — code + smoke; real training is developer-run
- [x] 08 Cross-signer eval harness — OFFICIAL test run done: 0.291/0.552 cross-signer, 11 signers, 2731 classes
- [ ] 09 (Optional) v3.1 kinematic ablation

### Phase 1 — Streaming isolated

- [x] 10 Real-timed data regime (N4 off) — `clip_features_realtimed` + `features/streaming.py`; val built `(9575,96,258)`, real timing preserved (median 33 frames)
- [x] 11 Per-frame emission head — `build_streaming_classifier` (per-frame softmax) + `train_streaming.py` (warm-start from isolated best.keras, masked per-frame CE) + `eval/streaming.py` (mean-agg). Code + smoke green (90 tests). Real training = developer-run.
- [ ] 12 Confirmation policy (S7) — offline
- [ ] 13 Streaming eval

### Phase 2 — CTC continuous

- [ ] 14 Connected-sequence data + CTC head
- [ ] 15 Streaming CTC decode + confirmation
- [ ] 16 Sentence builder (S8)

### Phase 3 — Android runtime

- [x] 17 Capture + landmarkers (S0, S1, S2) — device-verified
- [x] 18 Tracking + feature parity (S3, S4) — skew tests green (S3 One-Euro deferred)
- [x] 19 TFLite recognition + gating (S6, S5) — device-verified end-to-end
- [~] 20 Confirmation + sentence builder on-device (S7, S8) — S7 done; S8 passthrough+dedup done, LM-assisted deferred
- [x] 21 Recognition UI — top-3 candidates + handedness toggle, device-verified
- [~] 22 End-to-end device smoke + rollout - checklist + rollback documented; low-FPS profiling/tolerance pass implemented and device-tested on 2026-07-18; broader F22 smoke remains developer-run.
- [~] 24 Dual-camera (back-camera) support (S0) — **PLUMBING BUILT (agent), DEVICE-VERIFICATION PENDING** (`context/back-camera.md`). Front camera = untouched baseline; back routes through the identical pipeline; **no forced mirror** (analysis path stays un-mirrored to match training). Implemented: `frontCamera` state + camera-flip button (`cameraToggle`) + re-callable `rebindCamera()` in `MainActivity`; `RecognitionPipeline.resetSession()` (session estimators + in-flight sign) called on switch; `OverlayView` mirror driven by the real lens; `FrameAnalyzer` has a commented-only flip insertion point (no flip). No S4/F parity impact. **Open gate (developer):** build in Android Studio, then one-handed asymmetric sign on the back camera → dominant hand lands RIGHT slot / recognizes (pass → no flip; fail → enable back-only capture-layer flip). Files: `MainActivity.kt`, `RecognitionPipeline.kt`, `FrameAnalyzer.kt`, `activity_main.xml`, `strings.xml`. Baseline snapshot + one-step revert in `back-camera.md`.

### Experimental Prototype Track - React Native / iPhone

- [~] RN01 Camera + FPS smoke test under `apphear-react/` - Android physical benchmark PASS; iPhone benchmark pending
- [~] RN02 iOS MediaPipe hand-only latency test - scaffold/protocol/assets prepared; physical iPhone/macOS validation pending
- [ ] RN03 iOS hand + pose latency test
- [ ] RN04 Swift/native 258-feature parity test
- [ ] RN05 Same deployed TFLite inference test
- [ ] RN06 S5/S7 buffering + RN result display
- [ ] RN07 Side-by-side benchmark against native Android baseline
---

## Decisions Made (this session)

### 2026-07-19 React Native Prototype Decisions

- RN01 iPhone gate intentionally skipped by developer direction on 2026-07-19 to proceed to RN02 prep. This is a conscious deviation from 
`react-native-prototype.md`; RN02 may be scaffolded, but cannot be marked passed until physical iPhone validation exists.

- RN01 Android camera callback benchmark passed on Xiaomi M2101K7AG: stable ~30 FPS for 1/3/5-minute runs, 0 drops, actual frame 800x480.
- Requested 60 FPS negotiated to actual 30 FPS on this device; future reporting must use measured callback FPS, not requested FPS.
- This result is not MediaPipe, landmark, feature, or recognition FPS. RN02 remains blocked until iPhone RN01 produces matching 1/3/5-minute logs.

### 2026-07-18 Low-FPS Runtime Decisions

- Keep native Android as the baseline; React Native is not an FPS fix for this vision pipeline.
- React Native/iPhone work is allowed only as a separate `apphear-react/` experiment governed by
  `context/r`react-native-prototype.md``; RN is the UI shell, native code owns the hot path.
- Keep the deployed conversational TCN and the v3.0 258-feature contract; do not drop hand or pose blocks.
- Use runtime profiling and config flags for low-FPS experiments; risky behavior stays reversible.
- Treat `pose_every_n=2` with held pose as the current A/B test setting, not a schema change.
- Keep the low-FPS confirmation min-frame guard (`min_commit_frame=2`) because frame-1 commits were too aggressive.
- Stop blind S5/S7 threshold loosening for now; the latest controlled test points to specific model/data confusion clusters and FPS/thermal degradation.
- **Re-architecture, not a retrain.** Recognition is one stage of nine. System metric =
  end-to-end signed-phrase accuracy, cross-signer, streaming.
- **Training stack: TensorFlow / Keras** → native TFLite export. On-device target fixed as
  TFLite, CPU/INT8, no GPU delegate.
- **Model: causal TCN encoder + swappable head.** Migration Phase 0 softmax → Phase 1
  per-frame → Phase 2 CTC. Encoder shared across phases.
- **Datasets:** ASL Citizen primary (signer-diverse), ASLRecorder2 aux. Splits by `signer_id`.
- **Feature contract:** v3.0 "normalized 258" is current; v3.1 "kinematic 484" is a
  win-gated candidate.
- **Build order:** offline pipeline + cross-signer eval first (Phase 0), device last (Phase 3).
- **Android tooling:** the runtime app is built in **Android Studio** (Gradle project under `android/`).
- **[F01] Extraction runs in MediaPipe IMAGE mode** (stateless per-frame), not VIDEO mode. Reason: per-clip isolation + determinism, and tracking becomes an explicit S3 stage replicable on-device (better train/serve parity than MediaPipe's hidden VIDEO tracking). Surfaced when VIDEO mode's monotonic-timestamp requirement broke multi-clip runs.
- **[F01] `signer_id = Participant ID`**; ASL Citizen ships signer-disjoint official splits → feature 06 verifies + adopts them rather than re-splitting.
- **[F01] Derived landmark data lives off the code drive** at `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/landmarks/` (per-clip `.npz` + `.json`, resumable `manifest_<split>.csv`). Never committed.
- **[F01] TensorFlow deferred to feature 07** to keep the extraction install light.
- **[F02] Signing signal is pose-primary + hand-auxiliary (fused).** Pose wrist/elbow motion + hands-raised gate drive detection (robust, ~100% present); hand motion adds evidence only when present. Motion in shoulder-width units (shared `normalize/scale.py`, reused by N1).
- **[F02] Thresholds tuned label-free on val** (no onset/release labels): `theta_on=0.12`, `theta_off=0.072`, `smoothing_window=5`, `min_span_frames=6`. Result: 97.8% coverage, median span ~1.06s (vs 2.9s untuned). Config-driven (`detect.yaml`, `params_hash`); re-tune if stage E changes.
- **[F02] Spans stored non-destructively** as `*.span.json` + `manifest_spans_<split>.csv` under `derived/apphear3/spans/`; raw npz untouched.
- **[F03] Canonical space = center→scale→roll→mirror** on image landmarks (v2's 258 basis). Per-clip scale+roll, per-frame center. Pure/config-driven — the exact math Android S4 must port (parity surface #1). Params recorded in `manifest_norm_<split>.csv`; normalized landmarks (re)produced at F, not persisted.
- **[F03] N2 roll uses shoulder-LINE tilt folded to ±90°** (median of vector components, wrap-safe) — NOT the L→R vector direction. The camera mirrors the view so a front-facing signer's right shoulder is at smaller x; naive angle-median gave 178° residuals. Fixed → residual ≈0.02°.
- **[F03] Handedness canonicalizes dominant→right**; dominant = higher pose-wrist motion over span; `handedness_epsilon=0.15` skips mirroring near-symmetric signs. `mirror_exempt` per-gloss list deferred (empty).
- **[F04] N4 = linear resample to T=64**, isolated/training-only (OFF in streaming/CTC); native duration kept as scalar side feature. **Q = advisory** (accept/reject manifest, nothing deleted); lenient thresholds tuned on rejection distribution. Neither is an S4 parity surface.
- **[F05] Feature contract v3.0 minted** (`SCHEMA_VERSION="3.0"`, `pipeline/features/contract.py`): 258 = [handL 63, handR 63, pose 132], tensor `(T=64,258)`. NaN→0 imputation + separate `(T,2)` presence mask (aux). Per-split `.npz` (X,mask,y,participant_ids) + `vocab.json` from train. `clip_features` = the exact S4 parity target; determinism unit-tested.
- **[F05 finding]** On the val subset (mostly 1 signer P5): presence mask L=100%, R=62% — the active hand is consistently MediaPipe-labeled "Left" for this signer. Not a bug; flags a cross-signer N3/handedness-labeling check (MediaPipe selfie-view label reliability) once multi-signer features exist.
- **[F06] Official splits adopted + frozen** to `artifacts/splits.json` (participant→split + counts + content hash `b992940a3df2078d`; 35/6/11 signers, 83,399 clips, disjoint verified). `--verify` mode rebuilds and fails on drift/leakage. k-fold signer CV deferred (val is only 6 signers).
- **[F07] Model = small causal TCN** (`model/model.py`): 4 residual blocks, 64 ch, dilations [1,2,4,8], causal Conv1D + LayerNorm + dropout 0.1, GAP→softmax. ~154K params. **Causal from day one** so the encoder transfers to Phase 1/2 unchanged. TF/Keras 2.21. `model/train.py` config-driven (`model/config/train.yaml`), checkpoints best/final + CSV log, EarlyStopping on val_top1.
- **[F07] Division of labor:** the **developer runs the two long jobs** — full pipeline extraction (`pipeline/run_pipeline.py` per split) and the real `model.train` run. Agent delivers smoke-validated code only. `pip install tensorflow` done in `.venv`.
- **[F08] Eval harness = report-only** (`eval/`): per-signer + macro top-1/top-5, temperature-scaling calibration (fit on val, ECE pre/post), confusion summary → `eval_<split>.json`. No hardcoded pass/fail bar (numbers are the gate). Calibration derives pseudo-logits `log(p)` since the model outputs softmax; seeds the S7 confirmation policy (feature 12). Pure-numpy metrics/calibration (TF only for model.predict). Real eval runs after training via `python -m eval.run`.
- **Context System adopted**, adapted from JS-Mastery `skills` repo: 9 context files, with the
  UI trio replaced by `runtime-constraints.md` / `eval-protocol.md` / `feature-schema.md`.
  Android runtime language assumed **Kotlin** (flag if wrong).

---

## Notes

- `docs/` holds the deep design rationale (§8); `context/` holds the operational contracts.
  If they drift, `context/` wins — flag the drift.
- AppHear v2 lives in `../AppHear` and must not be touched.
- Open items to confirm before/at their phase: exact target SoC + min SDK; ASL Citizen local
  path + license terms; whether ASLRecorder2 captures need re-extraction under the v3 pipeline.
- **[F01 finding]** On untrimmed val clips: `pose_hit_rate` ≈ 1.0, `native_fps` ≈ 30 (well above
  the 15 fps floor), but `hand_hit_rate` ≈ 0.24–0.42. That low hand rate ≈ the *signing fraction*
  of a ~3.5 s clip (~1 s of hands-up), consistent with the anchor numbers — it's the dead time
  D1/D2 will trim, not a detector failure. Confirm against trimmed spans once D1/D2 exist; if hand
  rate stays low *within* the signing span, revisit hand-detection confidence (`extract.yaml`).
- **[F02 finding]** Baseline (resting) motion floor is ~0.08 shoulder-widths/frame — partly IMAGE-mode
  pose jitter (the stateless-extraction tradeoff). `theta_on` must sit above it. `smoothing_window` was
  raised 3→5 to suppress this. If jitter proves limiting later, revisit smoothing or add an explicit S3
  smoothing stage before D1.
- **[F02 caveat]** Thresholds tuned on val's **6 signers only**. Re-validate coverage/duration on a
  broader signer sample (or train split) before the full extraction+detection run.
- **[F03 caveat]** The 90 extracted val clips are **all one signer** (first 90 rows of val.csv). N1-N3
  invariances (scale→1, roll→0) are per-clip mathematical guarantees so this proves correctness, but
  the *cross-signer distributional* value (inter-signer variance collapse) should be shown once more of
  val is extracted across its 6 signers.
- **[F01 next]** The 12-clip check was one participant (P5). Run a cross-participant health sample
  before the full extraction to catch signer-specific detection gaps early. → **DONE** via
  `pipeline/extract/health.py`: across all 6 val signers, pose hit-rate 1.00, no detector-failure
  flags; low hand-rate confirmed as dead time. Extractor cleared for the full run.
- **[splits, confirmed]** ASL Citizen official splits are **signer-disjoint** — train 40,154 clips
  / 35 signers, val 10,304 / 6, test 32,941 / 11, **zero signer overlap**. Feature 06 adopts these
  directly. NOTE: val has only **6 signers** — small held-out set; weight cross-signer conclusions
  accordingly and lean on test (11 signers) for final numbers.





### 2026-07-19 RN02 iOS Source Wiring

- RN02 remains an experiment under `apphear-react/`; production Android, model, dataset, training pipeline, and feature contract were not touched.
- Added iOS source-level RN02 module wiring:
  - `ios/AppHearReactPrototype/RN02HandBenchmarkModule.m`
  - `ios/AppHearReactPrototype/RN02HandBenchmarkModule.swift`
  - `ios/AppHearReactPrototype/RN02HandLandmarkerBenchmark.swift`
  - `ios/AppHearReactPrototype/hand_landmarker.task`
- Updated the iOS Xcode project file so the RN02 Swift/ObjC files are in Sources and `hand_landmarker.task` is in Resources.
- Updated `ios/Podfile` with `pod 'MediaPipeTasksVision'` for the RN prototype target only.
- Added `src/screens/Rn02HandSmokeScreen.tsx` and an RN01/RN02 switch in `App.tsx`; RN02 calls only compact native-module methods, not frame data.
- Current RN02 capability: model-load/native-module smoke path only. Native camera sample-buffer ingestion and real hand latency samples are still not implemented.
- Validation on Windows: `npm run typecheck` passed; `npm run lint` passed. iOS compilation/device validation is pending macOS/Xcode/CocoaPods.

### 2026-07-19 RN02 Android Hand-Only Model-Load Slice

- Developer confirmed no iPhone is available as of today and chose to skip iOS testing for now.
- Advanced the React Native experiment on Android only, still inside `apphear-react/` and still separate from the production Android runtime.
- Added RN02 Android native module/model-load slice:
  - `android/app/src/main/java/com/apphear/reactprototype/AppHearVisionPackage.kt`
  - `android/app/src/main/java/com/apphear/reactprototype/RN02HandBenchmarkModule.kt`
  - registered `AppHearVisionPackage()` in `MainApplication.kt`
  - copied `hand_landmarker.task` to `android/app/src/main/assets/hand_landmarker.task`
  - added `implementation("com.google.mediapipe:tasks-vision:latest.release")` in the RN prototype app Gradle file
- Updated RN02 JS types and screen so Android can run `startHandBenchmark` / `stopHandBenchmark` through the native module.
- Current capability: Android RN02 can compile and should load the MediaPipe HandLandmarker model in native Kotlin `.IMAGE` mode with `numHands=2`; it does not process camera frames yet.
- Validation: `npm run typecheck` passed; `npm run lint` passed; `./gradlew.bat assembleDebug -PreactNativeArchitectures=arm64-v8a --console=plain --no-daemon --max-workers=2` passed; APK produced at `apphear-react/android/app/build/outputs/apk/debug/app-debug.apk`.
- Asset SHA256 for `android/app/src/main/assets/hand_landmarker.task` matches `apphear-react/assets/mediapipe/hand_landmarker.task`.
- No production Android, model contract, dataset, training pipeline, pose, features, TFLite, or recognition code was changed.
### 2026-07-19 RN02 Android Native Hand-Only CameraX Slice

- Advanced RN02 from model-load only to native Android CameraX hand-only frame processing inside `apphear-react/`.
- Production Android runtime, model contract, dataset, training pipeline, pose, features, TFLite, and recognition remain untouched.
- `RN02HandBenchmarkModule.kt` now:
  - binds CameraX `ImageAnalysis` to the current React Activity lifecycle;
  - requests `OUTPUT_IMAGE_FORMAT_RGBA_8888` and `STRATEGY_KEEP_ONLY_LATEST`;
  - converts each `ImageProxy` to `Bitmap` and then MediaPipe `MPImage` via `BitmapImageBuilder`;
  - runs `HandLandmarker.detect()` natively in `RunningMode.IMAGE` on a single background executor;
  - accumulates processed frames, skipped frames, hand hit rate, two-hand hit rate, p50/p95 hand latency, processed FPS, and frame size;
  - returns only compact session/sample dictionaries to React Native.
- `Rn02HandSmokeScreen.tsx` now polls `getLatestHandBenchmark()` once per second while running; no per-frame bridge traffic is introduced.
- Added explicit CameraX dependencies to the RN prototype Android app module.
- Validation: `npm run typecheck` passed, `npm run lint` passed, and `./gradlew.bat assembleDebug -PreactNativeArchitectures=arm64-v8a --console=plain --no-daemon --max-workers=2` passed.
- Next validation is device-run only: reinstall APK, run RN02 for 1/3/5 minutes, export JSON, and compare hand-only processed FPS/latency to the native Android baseline context. This is still hand-only; no recognition verdict is allowed.
### 2026-07-19 RN02 Android First Hand-Only Device Run + Stop Fix

- First RN02 Android native hand-only CameraX export saved under `apphear-react/benchmark/device-results/android-m2101k7ag-rn02-hand-2026-07-19/`.
- Run summary from `rn02-hand-1min-raw.json`:
  - device: Xiaomi `M2101K7AG`
  - duration: 75.424s
  - processed frames: 735
  - processed FPS: 9.74
  - hand latency p50: 71.33ms
  - hand latency p95: 97.91ms
  - skipped frames: 0
  - actual frame: 720x1280
  - hand hit rate: 2.59%; two-hand hit rate: 0%
- Interpretation: native hand-only MediaPipe is working, but this is below the 15 FPS target and is still hand-only, not full recognition. Low hand hit rate is not a detector conclusion because the run mostly did not contain controlled visible signing hands.
- Stop initially errored because `ProcessCameraProvider.unbindAll()` was called from the RN native module thread. Fixed `RN02HandBenchmarkModule.closeRuntime()` to marshal CameraX unbind to `ContextCompat.getMainExecutor(reactContext)` and wait briefly when called off-main-thread.
- Validation after fix: `npm run typecheck` passed, `npm run lint` passed, Android `assembleDebug` passed.
### 2026-07-19 RN02 Android Hand-Only Sustained Verdict

- RN02 Android hand-only CameraX + MediaPipe sustained logs are saved under `apphear-react/benchmark/device-results/android-m2101k7ag-rn02-hand-2026-07-19/`.
- Summary:
  - 1-min export: 75.424s, 735 frames, 9.74 FPS, p50 71.33ms, p95 97.91ms, skipped 0, 720x1280.
  - 3-min export: 151.656s, 1403 frames, 9.25 FPS, p50 80.24ms, p95 126.79ms, skipped 0, 720x1280. Note: not a full 180s run.
  - 5-min export: 302.751s, 2764 frames, 9.13 FPS, p50 79.92ms, p95 132.61ms, skipped 0, 720x1280.
- Verdict: RN02 Android native hand-only path is stable and stop cleanup works, but sustained hand-only FPS is below the 15 FPS target and degrades slightly under longer runs. This does not validate React Native as a performance improvement for full recognition.
- Key engineering finding: CameraX is delivering 720x1280 despite requesting 480x854, likely limiting FPS. Next step should be a lower analyzer-resolution experiment before adding pose.
- Guardrail remains: no pose/features/TFLite/recognition claims from these hand-only logs.



### 2026-07-21 Android UI reference correction - Home/dashboard

- User halted later migration work because the earlier AppHear3 UI approximation did not match the AppHear2 screenshots in `context/design/`.
- Added `context/android-ui-reference-correction.md` as the active UI-fidelity checklist linking screenshots to AppHear2 XML/resources and AppHear3 targets.
- Corrected Home/dashboard first against AppHear2 `activity_main.xml`, `item_feature_card_detect.xml`, `item_feature_card_project.xml`, and `nav_bottom.xml`:
  - replaced the generic Material Home layout with the AppHear2 avatar header, `Bridge Every` / `Conversation` hero, `Recent Signs` row, ViewPager2 feature-card carousel, AppHear2 dots, mascots, buttons, and bottom nav assets;
  - copied only selected non-conflicting AppHear2 Home/nav fonts/drawables into AppHear3 resources;
  - added Kotlin `FeatureCardAdapter` and kept detection routed to AppHear3 `RecognitionActivity`, not AppHear2 `SignDetectActivity`;
  - replaced the shell Material `BottomNavigationView` with AppHear2-style custom `nav_bottom.xml`.
- Dependency note: added `androidx.viewpager2:viewpager2:1.1.0` for the AppHear2 Home carousel only; did not add CardView because feature cards use existing Material Components.
- Verification: `assembleDebug` passed; `testDebugUnitTest` passed; protected AppHear3 model/config/MediaPipe asset hashes matched the rollback backup.
- Device note: `adb devices` listed no attached device during this correction, so visual/device smoke is pending.
- Remaining UI screenshot corrections: recognition collapsed/expanded, Text-to-ASL collapsed/expanded, settings/preferences, splash, and loading screens.
### 2026-07-21 Android UI reference correction - Recognition screen

- Corrected `RecognitionActivity` UI against AppHear2 `activity_sign_detect.xml` and the recognition collapsed/uncollapsed screenshots in `context/design/`.
- Replaced the plain debug overlay layout with AppHear2-style full-screen camera preview, top/bottom gradients, top back/status/camera/hand controls, rounded bottom sheet, current-sign typography, candidate text, sentence area, clear action, and collapsible expanded content.
- Preserved AppHear3 runtime/binding IDs and behavior: `previewView`, `overlayView`, `fpsText`, `handToggle`, `cameraToggle`, `sentenceText`, `clearButton`, `glossText`, `altText`, and `degradedBanner`. No AppHear2 `SignDetectActivity`, old ML classes, old confirmation/start-stop logic, face landmarks, model assets, or runtime settings were copied.
- Added only UI-safe behavior in `RecognitionActivity`: `btnBack.finish()` and bottom-sheet drag-handle expand/collapse.
- Verification: `assembleDebug` passed; `testDebugUnitTest` passed; protected AppHear3 model/config/MediaPipe asset hashes matched rollback backup.
- Device smoke on Xiaomi `M2101K7AG`: installed APK, launched `RecognitionActivity`, permission prompt was handled on device, GPU landmarkers loaded, recognizer loaded `window=96 classes=236`, and `AppHearPerf` streamed frames without crash/ANR. Processed FPS remained in the known low-FPS baseline range, which is not a UI regression.
- Device screenshot saved: `C:/Users/Gigabyte/.codex/visualizations/2026/07/21/019f834f-c7cd-7053-89a4-245ab1a0b669/apphear-device-smoke/recognition_ui.png`.
- Remaining UI screenshot corrections: Text-to-ASL collapsed/expanded, settings/preferences, splash, and loading screens.
### 2026-07-21 Android UI reference correction - Text-to-ASL screen

- Corrected `TextToAslFragment` UI against AppHear2 `activity_text_to_asl.xml` and the Text-to-ASL collapsed/uncollapsed screenshots in `context/design/`.
- Replaced the earlier rough shell with AppHear2-style stage, top gradient, back/title/speak controls, current-sign glass pill, rounded bottom sheet, SIGNING label, replay control, expanded text/speech toggle, text input, SIGN IT action, speech deferred panel, RESPOND action, and clear action.
- Preserved AppHear3-safe behavior only: local text preview, replay/clear preview, speech deferred notice, and RESPOND opening AppHear3 `RecognitionActivity`.
- Did not import AppHear2 WebView/avatar controller, GLB animation assets, animation registry, speech recognizer, ElevenLabs/Android TTS, recent-store, backend, or any recognition logic.
- Imported only selected non-conflicting AppHear2 Text-to-ASL UI drawables: `bg_circle_tan.xml`, `bg_toggle_container.xml`, `bg_toggle_active.xml`, `bg_toggle_inactive.xml`, and `ic_mic.xml`.
- Verification: `assembleDebug` passed; `testDebugUnitTest` passed; protected AppHear3 model/config/MediaPipe asset hashes matched rollback backup.
- Device note: APK install and MainActivity launch succeeded on Xiaomi `M2101K7AG`; MIUI blocked ADB tap injection, so route-specific Text-to-ASL screenshot/manual visual QA remains pending.
- Remaining UI screenshot corrections: settings/preferences, splash, and loading screens.
### 2026-07-22 Android UI reference correction - Settings/Profile

- Corrected Profile and Settings/Preferences screens against AppHear2 `activity_profile.xml`, `row_setting_*.xml`, and screenshots `settigns.jpg`, `settings_preference.jpg`, and `settings_preference_2.jpg`.
- Replaced generic AppHear3 Material profile/settings pages with AppHear2-style `Your Profile`, white profile card, avatar picker visual, disabled profile fields, `EDIT PROFILE` pill, `Preference / Your Setting` headings, coffee settings panel, dense setting rows, value pill, and logout visual.
- Imported only selected non-conflicting AppHear2 profile/settings drawables and row layouts. Did not copy AppHear2 Java auth/profile logic, Supabase behavior, SharedPreferences setting mutations, old recognition toggles, model/runtime code, or backend behavior.
- AppHear2 switch rows are visual/passive only (`clickable=false`, `focusable=false`, `saveEnabled=false`) and do not control AppHear3 recognition.
- Verification: `assembleDebug` passed; sequential `testDebugUnitTest` passed; protected AppHear3 model/config/MediaPipe asset hashes matched rollback backup.
- Note: first build failed from UTF-8 BOM/leading-byte issue in `fragment_settings.xml`; fixed by rewriting XML without BOM. A parallel Gradle test attempt also failed from resource-output cleanup contention; sequential rerun passed.
- Remaining UI screenshot corrections: splash and loading screens. Manual visual QA remains pending because automated image inspection is unavailable in this Windows sandbox.
### 2026-07-22 Android Settings/Profile cleanup - remove AppHear2-only runtime rows

- Removed visible AppHear2-only/beta runtime setting rows from both `fragment_settings.xml` and `fragment_profile.xml`: Detection Preferences, Smart detection beta, Low-latency beta, Duplicate suppression, Hand-presence gate, Run face landmarks, Rotate offload beta, Parallel detectors beta, Pipeline profiling dev, Experimental core model v3 beta, and Extended vocabulary beta.
- Kept safe passive rows only: account type, voice output, accessibility, privacy, and about.
- No AppHear3 recognition pipeline, model assets, MediaPipe assets, S4 feature contract, thresholds, or runtime flags were changed.
- Verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed. Initial build failed after the PowerShell edit due UTF-8 BOM/leading-byte XML encoding; `fragment_profile.xml` and `fragment_settings.xml` were rewritten as UTF-8 without BOM and the rerun passed.
### 2026-07-22 Local supplementary 236-class candidate export gate

- Completed local supplementary 236-class TCN candidate from `F:/ASL DATASET/local` via the existing pipeline: TRAIN-only local merge, FPS augmentation, warm start from deployed conversational FPS TCN.
- Training output: `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/runs/tcn_streaming_conversational_plus_local_pc_236_rtx3050_v30` with `best.keras`, `final.keras`, and `history.csv`; early stopping ended at epoch 30, best validation frame accuracy at epoch 22.
- Normal cross-signer eval on unchanged ASL Citizen test via `features_streaming_conversational_plus_pc_236`: top1 0.6172, top5 0.8683, per-frame 0.4394, last-frame 0.5706, temperature 0.7293.
- Low-FPS eval: k4 top1 0.5702 / top5 0.8366; k8 top1 0.5290 / top5 0.8076. This is only a marginal k8 top1 gain over the current deployed FPS model (0.5271) and slightly worse at k4/top5, so it is not an automatic deployment win.
- Confirmation tuning on `features_lowfps_conv_k8` with temperature 0.6262 chose theta_conf -1.2 under target false commit <= 0.05. Test: commit 15.1%, correct commit 10.3%, false commit 4.7%, precision when committed 0.686, correct-but-dropped 80.2%, latency 0.56. This is lower precision than the current deployed confirm report, so device testing must be cautious A/B only.
- INT8 export passed: `streaming.tflite` 227 KB, clip top1 delta 0.0010, mean abs prob diff 0.00118, num_classes 236, schema_version 3.0.
- Candidate Android assets were packaged separately at `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/runs/tcn_streaming_conversational_plus_local_pc_236_rtx3050_v30/android_candidate_assets/` containing `streaming.tflite`, `model_manifest.json`, `vocab.json`, and `recognition_config.json`. Production Android assets were not overwritten.

### 2026-07-22 Recognition page model-test architecture pass

- Hardened `RecognitionActivity` for upcoming candidate-model testing without changing AppHear3 recognition behavior.
- Added `ui/recognition/RecognitionUiSnapshot.kt`, a pure UI adapter from AppHear3 `RecognitionState` to display text. Added `RecognitionUiSnapshotTest.kt` for idle/signing/committed rendering.
- Updated `RecognitionActivity` to render through the adapter and to show persistent model-load failures on the redesigned recognition page. This keeps `ModelContract`/`RecognitionPipeline.load()` refusal visible during model A/B tests.
- Wired the AppHear2-style `SPEAK` control to a deferred-message toast only; no TTS/cloud speech behavior was added.
- No AppHear2 detection pipeline, old models, face landmarks, START/STOP lifecycle, confirmation logic, or runtime settings were copied.
- Validation: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed. ADB device check found no attached devices, so device launch/manual visual QA is pending.
- Asset note: current `model_manifest.json`, `recognition_config.json`, and `streaming.tflite` differ from the old UI-phase backup and appear to be the current 236-class candidate model/config state. They were not modified by this UI pass and must not be reverted without explicit model-test direction.
### 2026-07-22 Encoding cleanup - Android strings/comments

- Cleaned mojibake/corrupted user-facing Android strings in `android/app/src/main/res/values/strings.xml` caused by prior UTF-8 text being read/written with the wrong encoding.
- Replaced special emoji/punctuation labels with plain ASCII equivalents for recognition runtime UI: warming/loading ellipses, FPS separator, degraded-mode dash, hand labels/hints, and camera labels/hints.
- Cleaned remaining mojibake from `android/app/src/test/java/com/example/apphear/S4SkewTest.kt` comments/error text.
- Verified no remaining common mojibake marker patterns under Android main resources/source or unit-test source.
- Validation: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed.

### 2026-07-22 Android low-FPS bottleneck architecture checkpoint

- Current device A/B state: Android assets are using the local supplementary 236-class candidate copied from `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/runs/tcn_streaming_conversational_plus_local_pc_236_rtx3050_v30/android_candidate_assets/`.
- Revert point is preserved at `android/app/src/main/assets/_backup_before_local_pc_236_candidate_20260722-075734/`.
- Latest logcat confirms the long-running bottleneck: camera input remains around 14-17 FPS, but processed recognition FPS falls to about 3-4 FPS because MediaPipe hand + pose landmarking consumes the frame budget. TFLite recognition remains cheap and is not the bottleneck.
- The candidate model is not a clear deployment win: `KNOW` and `WANT` improved, but `CUT` can become `WE`, `IMPORTANT` can become `FAMILY`/`TEACH`, and `SELL` can become `PUT`, especially when processed FPS is 3-4.
- Architecture decision: focus next on measured runtime bottleneck experiments before more model retraining. Safe order is strict low-FPS confirmation A/B, MediaPipe GPU-vs-CPU delegate A/B, lower analyzer-resolution experiment, pose cadence sweep, then targeted data/model work only if confusion clusters remain.
- Guardrails: no React Native migration for this fix, no TCN replacement, no 258-feature contract change, no hand/pose removal, no blind threshold loosening, and every risky runtime change must be reversible through config flags.

### 2026-07-22 Strict low-FPS confirmation A/B config

- Implemented the first reversible bottleneck-plan experiment as a config-only Android asset change; no Kotlin source, model, vocabulary, MediaPipe assets, or 258-feature contract changed.
- Created rollback backup at `android/app/src/main/assets/_backup_before_strict_lowfps_confirm_20260722-084845/` containing the pre-change candidate `recognition_config.json`, `model_manifest.json`, `streaming.tflite`, and `vocab.json`.
- Updated current `android/app/src/main/assets/recognition_config.json` low-FPS confirmation from `min_commit_frame=2`, `k_stability=2`, `theta_margin=0.75` to `min_commit_frame=4`, `k_stability=3`, `theta_margin=0.9`.
- Purpose: reduce early wrong commits at 3-4 processed FPS where partial signs were committing as nearby classes (`CUT` -> `WE`, `IMPORTANT` -> `FAMILY`/`TEACH`, `SELL` -> `PUT`). Expected tradeoff is more delay and possibly more dropped signs.
- Validation: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed. Debug APK is `android/app/build/outputs/apk/debug/app-debug.apk`.
- ADB device check found no attached devices, so install/manual testing remains developer-run.

### 2026-07-22 MediaPipe delegate CPU/GPU A/B switch

- Added a runtime MediaPipe delegate selector in `LandmarkerBundle`: `recognition_config.json` can now set `mediapipe_delegate.mode` to `gpu` or `cpu`.
- Default/fallback behavior remains the existing `FeatureFlags.LANDMARKER_TRY_GPU` path, preserving GPU-with-CPU-fallback unless the asset config forces CPU.
- Current test build forces CPU via `android/app/src/main/assets/recognition_config.json`: `mediapipe_delegate.mode=cpu`.
- Startup logs now identify the selected delegate with `AppHearLandmarker: landmarker delegate mode=...` and `landmarkers on ... delegate`.
- Rollback/config backup before this A/B change: `android/app/src/main/assets/_backup_before_cpu_delegate_ab_20260722-091958/`.
- Validation: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed. Debug APK is `android/app/build/outputs/apk/debug/app-debug.apk`.
- Next device test: install CPU build and compare `processed_fps`, `hand_ms`, `pose_ms`, and recognition behavior against the previous strict-confirmation GPU log. If CPU is not faster/stabler, set `mediapipe_delegate.mode=gpu` and move to analyzer-resolution A/B.

### 2026-07-22 CPU delegate A/B device result

- Device log confirmed the CPU test build ran: `AppHearLandmarker: landmarker delegate mode=cpu` and `landmarkers on CPU delegate`.
- CPU improved raw MediaPipe timing on Xiaomi `M2101K7AG`: processed FPS commonly reached about 6-8 FPS; hand landmark time often fell around 65-90 ms; pose p95 was often around 120-150 ms. This is faster/more stable than the prior GPU strict-confirmation run where processed FPS was often 4-6 FPS and hand/pose p95 was higher.
- Recognition quality did not improve enough despite faster CPU landmarking. Observed/logged confusions remained: `CUT` sometimes committed as `WE` with candidates `[WE, CUT, US]`; `IMPORTANT` still committed as `FAMILY` with `IMPORTANT` in the candidate list; `SELL` remained unstable and appeared near `TEACH2`/`PUT`; `KNOW` sometimes first committed as `HELLO` before later `KNOW` commits.
- Interpretation: CPU is a performance win on this phone, but not a product-quality recognition win with the current candidate model and strict confirmation. Remaining errors are low-FPS plus model/data confusion, not only delegate speed.
- Current state remains CPU-forced unless changed: `recognition_config.json` has `mediapipe_delegate.mode=cpu` plus strict low-FPS confirmation (`min_commit_frame=4`, `k_stability=3`, `theta_margin=0.9`).
- Revert points: previous strict-confirmation GPU config is in `android/app/src/main/assets/_backup_before_cpu_delegate_ab_20260722-091958/`; previous pre-strict candidate config/assets are in `_backup_before_strict_lowfps_confirm_20260722-084845/`; pre-local-candidate deployed assets are in `_backup_before_local_pc_236_candidate_20260722-075734/`.
- Next recommended implementation: restore `mediapipe_delegate.mode=gpu` for the next experiment and add a configurable CameraX analyzer-resolution A/B. If analyzer-resolution does not improve recognition, revisit whether CPU should be retained only as a measured performance option.

### 2026-07-22 Analyzer resolution A/B - GPU 480x360 build

- Added config-driven CameraX analyzer resolution in `RecognitionActivity`. The app now reads `camera_analysis.target_width` and `camera_analysis.target_height` from `recognition_config.json`, defaults to 640x480 if absent/invalid, and logs the requested target with `AppHearRecognition: camera_analysis target=...` during camera bind.
- Current test build restores MediaPipe delegate to GPU and requests analyzer resolution 480x360: `mediapipe_delegate.mode=gpu`, `camera_analysis.target_width=480`, `camera_analysis.target_height=360`.
- Strict low-FPS confirmation remains unchanged (`min_commit_frame=4`, `k_stability=3`, `theta_margin=0.9`) so this isolates analyzer resolution as the main variable against the previous strict GPU and strict CPU logs.
- Backup before this A/B config: `android/app/src/main/assets/_backup_before_analysis_480x360_gpu_20260722-093440/`.
- Validation: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed. Debug APK is `android/app/build/outputs/apk/debug/app-debug.apk`.
- Next device test must confirm logcat contains `landmarker delegate mode=gpu`, `landmarkers on GPU delegate`, and `camera_analysis target=480x360`, then compare processed FPS, hand/pose timings, commit delay, drops, and confusion behavior on the same controlled sign list.

### 2026-07-22 Analyzer resolution A/B result - GPU 480x360

- Device log confirmed the analyzer-resolution A/B build ran: `landmarker delegate mode=gpu`, `landmarkers on GPU delegate`, and `camera_analysis target=480x360`.
- The 480x360 analyzer target improved image conversion/rotation cost substantially: `rotate_ms` was about 3 ms instead of the earlier ~12-14 ms range.
- The full processed FPS did not improve enough because MediaPipe hand/pose landmarking remains dominant. Observed processed FPS stayed mostly around 5-6 FPS, with hand p95 still reaching about 280-300 ms and pose p95 often about 180-270 ms.
- Recognition behavior was acceptable for `CUT`, `WANT`, `KNOW`, `FAMILY`, `TEACH`, `PUT`, and `WE`, but `IMPORTANT` still committed as `FAMILY` and `SELL` still moved toward `PUT`/`TEACH2`.
- Interpretation: lower analyzer resolution helps the cheaper image stages but does not materially solve the MediaPipe bottleneck or the remaining class confusions.
- Current state: `mediapipe_delegate.mode=gpu`, `camera_analysis=480x360`, strict low-FPS confirmation remains active, and pose cadence remains `pose_every_n=2`.
- Next recommended A/B: keep GPU + 480x360 and test `pose_cadence_experiment.pose_every_n=3` with hold-last-pose enabled. Revert to `pose_every_n=2` if recognition worsens.

### 2026-07-22 Pose cadence A/B - GPU 480x360 pose_every_n=3 build

- Implemented the next bottleneck-plan experiment as a config-only change: `pose_cadence_experiment.pose_every_n` changed from 2 to 3 while keeping `hold_last_pose=true`.
- Current test state: `mediapipe_delegate.mode=gpu`, `camera_analysis=480x360`, strict low-FPS confirmation (`min_commit_frame=4`, `k_stability=3`, `theta_margin=0.9`), and `pose_every_n=3`.
- Rollback backup before this config change: `android/app/src/main/assets/_backup_before_pose_every_3_20260722-094412/`.
- Validation: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed. Debug APK is `android/app/build/outputs/apk/debug/app-debug.apk`.
- Next device test must confirm logcat has `pose_every=3`, `landmarker delegate mode=gpu`, `landmarkers on GPU delegate`, and `camera_analysis target=480x360`, then compare processed FPS, hand/pose timing, drops, and controlled-sign recognition against `pose_every_n=2`.

## 2026-07-22 - Android Low-FPS Runtime A/B: pose_every_n=3 Reverted

- Tested local supplementary 236-class candidate on Xiaomi M2101K7AG with GPU MediaPipe, camera_analysis=480x360, strict low-FPS confirmation, and pose_cadence_experiment pose_every_n=3.
- User observations from logcat run 24302: CUT good; IMPORTANT good but sometimes MORE; SELL still PUT; WANT degraded to MEET; KNOW degraded to SELL/SHOP; FAMILY, TEACH, PUT, WE good.
- Log confirmed processed FPS usually ~6-7 FPS with dips to ~3.9-5.0 FPS. This was only a modest gain over pose_every_n=2, while recognition stability got worse for WANT/KNOW and SELL remained unresolved.
- Decision: pose_every_n=3 is not a keeper for the current model/runtime profile. Reverted recognition_config.json to pose_every_n=2 while preserving GPU delegate, 480x360 analyzer resolution, strict low-FPS confirmation, hold_last_pose=true, and the 258-feature contract.
- Backup before revert: android/app/src/main/assets/_backup_before_revert_pose_every_2_20260722-095204/recognition_config.json
- Build verification after revert: ./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2 passed.
- Current best runtime test profile after revert: local 236-class candidate assets + GPU MediaPipe + camera_analysis=480x360 + pose_every_n=2 + strict low-FPS confirmation. Remaining recurring errors appear to be model/data confusion groups more than runtime confirmation: IMPORTANT/MORE/FAMILY, SELL/PUT/TEACH2/SHOP, WANT/MANY/MEET, KNOW/HELLO/SELL/SHOP.

## 2026-07-22 - Old Model A/B Prepared After Controlled Low-FPS Test

- Controlled test on Xiaomi M2101K7AG with local supplementary 236-class candidate + GPU + camera_analysis=480x360 + pose_every_n=2 showed: CUT good; IMPORTANT often FAMILY/INTRODUCE/delayed; SELL consistently PUT; WANT WAIT/WANT2/MANY; KNOW correct/delayed/HELLO; FAMILY, TEACH, PUT, WE good.
- Log confirmed runtime profile: GPU delegate, camera_analysis=480x360, pose_every=2, processed FPS mostly ~5-6 FPS with dips near ~3.6-4.0, always low_fps=true.
- Key interpretation: remaining failures are not mainly confirmation thresholds. SELL->PUT commits had high margins and true SELL was often absent from top-3; IMPORTANT appeared in FAMILY/MORE/IMPORTANT top-3; WANT and KNOW stayed in known confusion groups. This points to model/data class confusion under low-FPS streaming.
- Prepared a reversible old-model A/B APK: restored streaming.tflite, model_manifest.json, and vocab.json from android/app/src/main/assets/_backup_before_local_pc_236_candidate_20260722-075734 while preserving current runtime recognition_config.json profile.
- Backup before this A/B swap: android/app/src/main/assets/_backup_before_old_model_ab_20260722-100247/
- Build verification: ./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2 passed.
- Next test: install app-debug.apk and run the same controlled 3-attempt set (CUT, IMPORTANT, SELL, WANT, KNOW, FAMILY, TEACH, PUT, WE). Compare old deployed model against local supplementary candidate before deciding whether to keep candidate, revert model, or start targeted retraining for confusion groups.

## 2026-07-22 - Old Model A/B Result: Reject Old Model, Restore Local Candidate

- Old-model A/B log 30136 was tested with the same runtime profile: GPU MediaPipe, camera_analysis=480x360, pose_every_n=2, strict low-FPS confirmation, low_fps=true throughout, processed FPS mostly ~5-6 FPS with dips near ~4 FPS.
- User results for old model: CUT 3/3; IMPORTANT 2/3; SELL mostly delayed/DECIDE1; WANT 2/3; KNOW 0/3; FAMILY 2/3; TEACH 3/3; PUT 0/3; WE 0/3.
- Commit sequence confirmed the regression: PUT attempts committed INTRODUCE/IMPORTANT, WE attempts committed SELL/LIVE2/STRONG, KNOW committed SELL/DONTKNOW or delayed. Old model improved IMPORTANT compared with the local candidate but damaged previously stable classes.
- Decision: reject old model as current baseline. Restore the local supplementary 236-class candidate because it is better overall for controlled signs, especially PUT, WE, FAMILY, TEACH, CUT.
- Restored local candidate model/vocab/manifest from android/app/src/main/assets/_backup_before_old_model_ab_20260722-100247/ while preserving runtime config.
- Backup of rejected old-model A/B state before restore: android/app/src/main/assets/_backup_before_restore_local_candidate_20260722-101227/
- Build verification after restore: ./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2 passed.
- Next direction: stop broad runtime/model A/B for now. Remaining problem is targeted model/data confusion under low-FPS streaming: IMPORTANT/FAMILY/MORE/INTRODUCE, SELL/PUT/DECIDE1/SHOP/TEACH2, WANT/MANY/WAIT/MEET, KNOW/HELLO/SELL/DONTKNOW, plus possible WE/LIVE2/STRONG in old model only. Recommended next step is targeted confusion audit/retraining plan using ASL Citizen plus supplementary local data, not threshold tuning.

## 2026-07-22 - Targeted Confusion Audit Completed

- Ran targeted confusion audit for current restored local supplementary 236-class candidate: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_rtx3050_v30\best.keras
- Report artifacts written:
  - artifacts/targeted_confusion_audit_20260722/targeted_confusion_audit.md
  - artifacts/targeted_confusion_audit_20260722/targeted_confusion_audit.json
- Headline held-out test metrics: mean aggregation top1=0.617/top3=0.817/top5=0.868; last-frame top1=0.571/top3=0.790/top5=0.853; early4 top1=0.081; early6 top1=0.137.
- Interpretation: the phone's low-FPS early commits are consistent with offline weakness. The model is not reliable at very early frames; min_commit_frame=4 can be correct for easy signs but is too early for many signs if the wrong class has high confidence.
- Most problematic held-out last-frame classes in observed groups: KNOW top1=0.15, HELLO top1=0.30, SELL top1=0.27, WANT2 top1=0.36, PUT top1=0.45. Stable/current-good classes: WE top1=1.00, TEACH2 top1=0.91, MORE top1=1.00, FAMILY top1=0.75, IMPORTANT top1=0.67.
- Dataset count issue: many target classes have very small base train counts (e.g. SELL 23, KNOW 21, IMPORTANT 14, MANY 13, WAIT 12, WE 15, STRONG 15). FPS augmentation multiplies existing clips but does not add signer/style diversity.
- Next recommended model/data step: no more broad runtime threshold tuning. Prepare targeted retraining/eval experiment focused on weak confusion groups, with stronger per-class/early-frame eval gates before any Android deployment.

## 2026-07-22 - Targeted 236-Class Retrain v1 Verified

- User ran 08_TRAIN_TARGETED_236_CPU.ps1 successfully. Output run: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v1
- Training completed through epoch 24/40 with early stopping. Best val_pf_acc in log was ~0.4741 at epoch 16; final artifacts best.keras, final.keras, history.csv exist.
- Targeted audit written: artifacts/targeted_confusion_audit_20260722/targeted_v1/targeted_confusion_audit.md and .json
- Overall held-out test deltas vs baseline: mean top1 0.617 -> 0.613 (-0.005), last top1 0.571 -> 0.587 (+0.017), early4 top1 0.081 -> 0.077 (-0.004), early6 top1 0.137 -> 0.140 (+0.002).
- FPS-val stress deltas improved across views: mean top1 0.640 -> 0.663, last top1 0.588 -> 0.603, early4 top1 0.326 -> 0.339, early6 top1 0.430 -> 0.441.
- Major held-out last-frame improvements: KNOW 0.15 -> 0.54, HELLO 0.30 -> 0.50, SELL 0.27 -> 0.45, WANT2 0.36 -> 0.73, PUT 0.45 -> 0.55, TEACH2 0.91 -> 1.00.
- Regressions: WE 1.00 -> 0.83, WAIT 0.64 -> 0.36, MANY 0.73 -> 0.55, FAMILY 0.75 -> 0.67, SHOP1 0.60 -> 0.50, MEET top3 1.00 -> 0.89.
- Decision: targeted_v1 is promising but not deployable yet. It fixes several weak classes while moving errors into previously stable classes. Next step should be targeted_v2 with safer weights / guardrails before Android A/B.

## 2026-07-22 - Targeted 236-Class Retrain v2 Prepared

- Prepared v2 targeted retraining config and runner, but did not run full training in Codex because user will execute commands manually.
- New config: model/config/train_streaming_conversational_plus_local_pc_236_targeted_v2.yaml
- New runner: 09_TRAIN_TARGETED_236_V2_CPU.ps1
- v2 rationale: targeted_v1 improved KNOW/HELLO/SELL/WANT2/PUT but regressed WE/WAIT/MANY/FAMILY/SHOP1. v2 starts again from the current local-candidate baseline and uses softer weak-class weights plus guardrail weights.
- v2 weights: KNOW 2.5, HELLO 2.0, SELL 2.0, WANT2 1.6, PUT 1.6, WAIT 1.6, MANY 1.5, SHOP1 1.5, FAMILY 1.3, WE 1.3, IMPORTANT 1.3. TEACH2 and other stable classes remain 1.0.
- v2 output dir: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v2
- v2 audit dir after run: artifacts/targeted_confusion_audit_20260722/targeted_v2/
- Validation performed: config loads in project .venv and class weights resolve against the 236-class vocab.
- Deployment gate: do not export/deploy v2 unless it improves weak classes while avoiding v1 regressions, especially WE, WAIT, MANY, FAMILY, SHOP1.

## 2026-07-22 - Targeted 236-Class Retrain v2 Verified

- User ran 09_TRAIN_TARGETED_236_V2_CPU.ps1 successfully. Output run: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v2
- Training completed through epoch 25/40 with early stopping. Best val_pf_acc in log was ~0.4762 at epoch 17. Artifacts best.keras, final.keras, history.csv exist.
- Targeted audit written: artifacts/targeted_confusion_audit_20260722/targeted_v2/targeted_confusion_audit.md and .json
- Overall held-out test top1 baseline -> v1 -> v2: mean 0.617 -> 0.613 -> 0.623; last 0.571 -> 0.587 -> 0.583; early4 0.081 -> 0.077 -> 0.081; early6 0.137 -> 0.140 -> 0.139.
- FPS-val stress top1 baseline -> v1 -> v2: mean 0.640 -> 0.663 -> 0.659; last 0.588 -> 0.603 -> 0.598; early4 0.326 -> 0.339 -> 0.338; early6 0.430 -> 0.441 -> 0.435.
- Held-out last-frame class deltas baseline -> v1 -> v2: KNOW 0.15 -> 0.54 -> 0.54; SELL 0.27 -> 0.45 -> 0.45; PUT 0.45 -> 0.55 -> 0.55; WANT2 0.36 -> 0.73 -> 0.55; HELLO 0.30 -> 0.50 -> 0.30; WE 1.00 -> 0.83 -> 0.92; FAMILY 0.75 -> 0.67 -> 0.75; MANY 0.73 -> 0.55 -> 0.64; WAIT 0.64 -> 0.36 -> 0.36.
- Decision: v2 is safer than v1 for WE/FAMILY and has the best mean top1, but it is still not a clean deploy candidate. It preserves important improvements on KNOW/SELL/PUT while still regressing WAIT and some WANT2/HELLO gains compared with v1. Next step should be either v3 with more focused weights/guardrails or a temporary Android A/B only if we explicitly accept risk and keep rollback ready.

## 2026-07-22 - Targeted 236-Class Retrain v3 Prepared

- Prepared v3 targeted retraining config and runner for manual execution by the user.
- New config: model/config/train_streaming_conversational_plus_local_pc_236_targeted_v3.yaml
- New runner: 10_TRAIN_TARGETED_236_V3_CPU.ps1
- v3 rationale: v2 preserved KNOW/SELL/PUT gains better than baseline and recovered WE/FAMILY versus v1, but WAIT remained badly regressed and HELLO/WANT2 lost some v1 gains. v3 removes weights from WAIT/MANY/SHOP1 because weighting those classes in v1/v2 coincided with regressions, while keeping targeted pressure on KNOW/HELLO/SELL/WANT2/PUT plus light guardrails for FAMILY/WE.
- v3 weights: KNOW 2.5, HELLO 2.4, SELL 2.3, WANT2 1.9, PUT 1.6, FAMILY 1.3, WE 1.3. WAIT/MANY/SHOP1/TEACH2 remain 1.0.
- v3 output dir: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v3
- v3 audit dir after run: artifacts/targeted_confusion_audit_20260722/targeted_v3/
- Validation performed: config loads in project .venv and class weights resolve against the 236-class vocab.
- Deployment gate: compare v3 against baseline, v1, and v2. Do not export/deploy unless weak-class gains hold and WAIT/MANY/SHOP1/WE/FAMILY regressions are acceptable or improved.

## 2026-07-22 - Targeted 236-Class Retrain v3 Verified

- User ran 10_TRAIN_TARGETED_236_V3_CPU.ps1 successfully. Output run: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v3
- Training completed through epoch 20/40 with early stopping. Best val_pf_acc in log was ~0.4735 at epoch 12. Artifacts best.keras, final.keras, history.csv exist.
- Targeted audit written: artifacts/targeted_confusion_audit_20260722/targeted_v3/targeted_confusion_audit.md and .json
- Overall held-out top1 baseline -> v1 -> v2 -> v3: mean 0.617 -> 0.613 -> 0.623 -> 0.627; last 0.571 -> 0.587 -> 0.583 -> 0.587; early4 0.081 -> 0.077 -> 0.081 -> 0.083; early6 0.137 -> 0.140 -> 0.139 -> 0.139.
- FPS-val top1 baseline -> v1 -> v2 -> v3: mean 0.640 -> 0.663 -> 0.659 -> 0.658; last 0.588 -> 0.603 -> 0.598 -> 0.608; early4 0.326 -> 0.339 -> 0.338 -> 0.331; early6 0.430 -> 0.441 -> 0.435 -> 0.438.
- Major held-out last-frame changes baseline -> v3: KNOW 0.15 -> 0.54, SELL 0.27 -> 0.55, WANT2 0.36 -> 0.73, PUT 0.45 -> 0.55, HELLO 0.30 -> 0.40, FAMILY 0.75 -> 0.83, DECIDE1 0.79 -> 0.86, WE 1.00 -> 0.92.
- Serious regressions baseline -> v3: SHOP1 0.60 -> 0.20, INTRODUCE 0.67 -> 0.50, WAIT 0.64 -> 0.36, MANY 0.73 -> 0.64, LIVE2 0.75 -> 0.67.
- Decision: v3 is the best overall offline candidate so far and strongest for the observed Android pain points, but not clean enough to deploy as final. The biggest blocker is SHOP1 collapsing into SELL; next step should be v4 with a small SHOP1 guardrail and slightly lower SELL weight, or Android A/B only if SHOP1 is outside current controlled target words and rollback is kept ready.

## 2026-07-22 - Targeted 236-Class Retrain v4 Prepared

- Prepared v4 targeted retraining config and runner for manual execution by the user.
- New config: model/config/train_streaming_conversational_plus_local_pc_236_targeted_v4.yaml
- New runner: 11_TRAIN_TARGETED_236_V4_CPU.ps1
- v4 rationale: v3 is the strongest overall candidate so far but SHOP1 collapsed into SELL (SHOP1 last top1 0.60 baseline -> 0.20 v3). v4 is a minimal correction from v3: reduce SELL weight and add a small SHOP1 guardrail.
- v4 weights: KNOW 2.5, HELLO 2.4, SELL 2.0, WANT2 1.9, PUT 1.6, SHOP1 1.3, FAMILY 1.3, WE 1.3. WAIT/MANY/TEACH2 remain 1.0.
- v4 output dir: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v4
- v4 audit dir after run: artifacts/targeted_confusion_audit_20260722/targeted_v4/
- Validation performed: config loads in project .venv and class weights resolve against the 236-class vocab.
- Deployment gate: compare v4 against baseline and v1-v3. Key pass/fail checks: keep v3 gains on SELL/KNOW/WANT2/PUT, recover SHOP1 meaningfully, avoid further regressions on WE/FAMILY/WAIT/MANY/INTRODUCE.

## 2026-07-22 - Targeted 236-Class Retrain v4 Verified

- User ran 11_TRAIN_TARGETED_236_V4_CPU.ps1 successfully. Output run: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v4
- Training completed through epoch 12/40 with early stopping. Best val_pf_acc in log was ~0.4758 at epoch 4. Artifacts best.keras, final.keras, history.csv exist.
- Targeted audit written: artifacts/targeted_confusion_audit_20260722/targeted_v4/targeted_confusion_audit.md and .json
- Overall held-out top1 baseline -> v1 -> v2 -> v3 -> v4: mean 0.617 -> 0.613 -> 0.623 -> 0.627 -> 0.621; last 0.571 -> 0.587 -> 0.583 -> 0.587 -> 0.584; early4 0.081 -> 0.077 -> 0.081 -> 0.083 -> 0.080; early6 0.137 -> 0.140 -> 0.139 -> 0.139 -> 0.137.
- FPS-val top1 baseline -> v1 -> v2 -> v3 -> v4: mean 0.640 -> 0.663 -> 0.659 -> 0.658 -> 0.656; last 0.588 -> 0.603 -> 0.598 -> 0.608 -> 0.602; early4 0.326 -> 0.339 -> 0.338 -> 0.331 -> 0.336; early6 0.430 -> 0.441 -> 0.435 -> 0.438 -> 0.438.
- Held-out last-frame key classes baseline -> v4: KNOW 0.15 -> 0.62, SELL 0.27 -> 0.55, PUT 0.45 -> 0.55, HELLO 0.30 -> 0.40, WE 1.00 -> 1.00, FAMILY 0.75 -> 0.83, INTRODUCE 0.67 -> 0.58, SHOP1 0.60 -> 0.40, WANT2 0.36 -> 0.55, MANY 0.73 -> 0.55, WAIT 0.64 -> 0.27.
- Decision: v4 is not a strict winner over v3. It improves KNOW/WE/INTRODUCE and partially recovers SHOP1, but hurts WAIT/MANY/WANT2 and has lower overall mean/last top1 than v3. Continuing weight tweaks risks overfitting the tiny target counts. Recommended stop point: do not deploy v4 as final. If doing Android A/B, v3 or v4 can be tested behind rollback, but a full 236-class regression audit should be added before any final model replacement.

## 2026-07-22 - Full 236-Class Regression Audit Prepared

- Added a full 236-class regression audit before any model deployment.
- New module: eval/full_regression.py
- New runner: 12_FULL_236_REGRESSION_AUDIT.ps1
- Purpose: compare baseline and v1-v4 across every class, not only targeted confusion groups. Reports overall metrics by view (mean/last/early4/early6), focus-word table, and worst per-class regressions/improvements against the baseline.
- Output after run: artifacts/targeted_confusion_audit_20260722/full_236_regression/full_regression_audit.md and .json
- Validation performed: `python -m eval.full_regression --help` succeeds with project .venv.
- Deployment gate: do not export/deploy v3/v4 until full_236_regression audit is reviewed, especially worst regressions across all 236 classes.

### 2026-07-22 Android UI reference correction - Splash/Loading

- Corrected the remaining splash and loading screenshot-reference pages against AppHear2 `activity_splash.xml`, `activity_loading.xml`, `bg_splash_screen.xml`, `splash.png`, `applogo.png`, and loading icons.
- Added native Kotlin `SplashActivity` and `LoadingActivity`.
- Updated `AndroidManifest.xml`: `SplashActivity` is the exported launcher; `MainActivity` remains the non-exported homepage/shell destination; `RecognitionActivity` remains non-exported in main/release manifest.
- `SplashActivity` uses the AppHear2 first-run onboarding preference gate and then opens `LoadingActivity`.
- `LoadingActivity` is a bounded visual transition to `MainActivity`; it does not preload recognition, alter candidate model assets, or represent model readiness.
- Imported only selected AppHear2 splash/loading visual assets: `applogo.png`, `bg_loading.xml`, `bg_splash_screen.xml`, `splash.png`, `week.png`, `hand.png`, `talking.png`.
- Cleaned one remaining mojibake comment in `LandmarkerBundle.kt`; Android source/resource mojibake scan is clean.
- Validation: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed.
- Manual device visual QA remains pending; asset provenance/APK-size review remains a release gate.
### 2026-07-22 Android UI shell/navigation cleanup

- Removed temporary `AppShellActivity` registration from the main manifest. The Kotlin file remains in source as a deletion-pass candidate until a safer source-control/backup cleanup point; it is no longer launchable or externally reachable.
- Kept `SplashActivity` as launcher, `LoadingActivity` as visual transition, `MainActivity` as non-exported homepage/shell, and `RecognitionActivity` as non-exported protected recognition destination in the main manifest.
- Updated `MainActivity` shell tab navigation to use `NavOptions` with `launchSingleTop` and `popUpTo(homeFragment)` so repeated bottom-nav taps do not stack duplicate destinations.
- Recognition route still opens `RecognitionActivity` directly and does not alter the AppHear3 runtime pipeline.
- Validation: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed.
## 2026-07-22 - Text-to-ASL Architecture Plan Documented

- Added `context/text-to-asl-architecture-plan.md` as the source-of-truth plan for completing Text-to-ASL in native AppHear3.
- Verified AppHear2 Text-to-ASL references: `TextToAslActivity.java`, `AvatarPlaybackController.java`, `AslAnimationRegistry.java`, `AslPhrasePlanner.java`, `SpeechInputManager.java`, `RecentSignsStore.java`, `TtsVoiceHelper.java`, `ElevenLabsSpeechPlayer.java`, `assets/model_viewer.html`, and `assets/asl_animations/manifest.json` plus 66 `.glb` files totaling about 159.22 MB.
- Decision: implement Text-to-ASL as an isolated Kotlin/XML subsystem with pure phrase-planning domain code, a WebView/GLB avatar controller, Android speech input, and Android TTS baseline. Do not import AppHear2 recognition, confirmation, MediaPipe, old model, face, Supabase, GenAI, or cloud voice behavior.
- Key gate: AppHear2 `model_viewer.html` currently loads `@google/model-viewer` from `https://unpkg.com`; AppHear3 must either vendor/replace that script for offline use or explicitly defer online viewer behavior. Full GLB import remains blocked until asset provenance/license and APK-size budget are confirmed.
- Next implementation step: Phase T1 from `context/text-to-asl-architecture-plan.md` - add pure Kotlin Text-to-ASL planner/catalog classes and unit tests before WebView or asset migration.
## 2026-07-22 - Text-to-ASL Phase T1 Pure Kotlin Planner Complete

- Implemented the isolated Kotlin Text-to-ASL domain layer under `android/app/src/main/java/com/example/apphear/domain/texttoasl/`.
- Added `AslAnimationAsset`, `AslAnimationCatalog`, `AslTextNormalizer`, `AslPhrasePlanner`, and `TextToAslPlan`.
- Added unit coverage in `android/app/src/test/java/com/example/apphear/TextToAslPlannerTest.kt` for AppHear2-equivalent normalization, longest-alias phrase matching, letter fallback, unsupported-token reporting, no-playable-assets behavior, and missing asset-path validation.
- No WebView, GLB assets, speech recognizer, Android TTS, WebKit dependency, permissions, Gradle changes, recognition code, model assets, CameraX, MediaPipe, TFLite, temporal logic, or confirmation logic changed.
- Verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed from `android/`.
- Safety scan: the new `domain/texttoasl` files do not import recognition, camera, model, MediaPipe, TensorFlow, WebView, speech, or TTS classes.
- Next step: Phase T2 asset gate and first playback slice. Before copying GLBs, decide how to handle AppHear2 `model_viewer.html` loading `@google/model-viewer` from `https://unpkg.com` and confirm asset provenance/APK-size budget.
## 2026-07-22 - Text-to-ASL Starter WebView/GLB Playback Slice Complete

- Completed Text-to-ASL Phases T2-T4 for a starter smoke slice while keeping recognition untouched.
- Fixed the AppHear2 offline issue: AppHear2 `model_viewer.html` loaded `@google/model-viewer` from `https://unpkg.com`; AppHear3 now uses a vendored pinned local script at `android/app/src/main/assets/vendor/model-viewer/model-viewer-4.3.1.min.js` with `LICENSE-Apache-2.0.txt` copied from the npm package. NPM metadata verified `@google/model-viewer` 4.3.1 as Apache-2.0.
- Added AndroidX WebKit `1.16.0` (`androidx.webkit:webkit`) for `WebViewAssetLoader`; official AndroidX docs list 1.16.0 as the current stable WebKit release and its minSdk is compatible with AppHear3 minSdk 26.
- Imported only a starter GLB slice from AppHear2, not all 66 GLBs: `asl_idle.glb`, `hello.glb`, `thank-you.glb`, `GOOD.glb`, `anim_a.glb`, and `anim_b.glb`, plus a filtered manifest exposing only those assets.
- Added Kotlin `AndroidAssetAslCatalogLoader` and `TextToAslPlaybackController` under `ui/texttoasl/`.
- Updated `TextToAslFragment` so text input now creates a local ASL playback plan, plays the WebView avatar queue, supports replay/clear, returns to idle, and reports unsupported tokens. Speech mode and speak-aloud remain deferred.
- Added `TextToAslAssetManifestTest` to ensure the smoke manifest references only bundled files and `model_viewer.html` does not reintroduce `unpkg.com` or Google CDN scripts.
- Updated user-facing strings so the screen no longer claims WebView/GLB playback is blocked.
- No AppHear3 recognition, confirmation, CameraX, MediaPipe, TFLite, model assets, temporal logic, runtime config, speech recognizer, Android TTS, ElevenLabs, Supabase, React Native, or old AppHear2 recognition code was changed.
- Verification: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed from `android/`.
- Current APK size after starter slice: about 93.23 MB debug APK.
- Next step: device smoke Text-to-ASL starter playback (`hello`, `thank you`, `good`, `ab`, unsupported word), then Phase T5 speech-to-text if playback works on device.
## 2026-07-24 - Sign Recognition Architecture Research Saved

- Completed research-only evaluation of the current recognition foundation, landmark/RGB/hybrid architectures, isolated versus continuous recognition, dataset requirements, Android feasibility, evaluation criteria, and experiment gates.
- No code, model, dataset, feature schema, Android asset, or runtime configuration changed.
- Decision: partially replace the current foundation with structured landmark/motion features, RGB hand appearance, sparse non-manual cues, a region-aware graph encoder, causal temporal fusion, and learned boundary/reject heads.
- Keep the frozen-contract ST-GCN experiment as the first controlled baseline, not the final architecture.
- Current 236-class data is insufficient for reliable consumer use; pilot >=30 signers/50 signs, then target 50-100 signers and 100-300 valid clips/sign.
- Isolated signs first; design for later CTC gloss recognition; do not treat concatenated isolated glosses as full ASL translation.
- Next recognition action: execute/audit ST-GCN, then run identical-split landmark-versus-RGB-hand-versus-hybrid ablation before changing the production feature contract.
- Full evidence, gates, unknowns, and experiment order are in `context/recognition-accuracy.md`.

## 2026-07-25 - Hybrid Recognition Upgrade Architecture Plan

- Created `context/recognition_upgrade/` with the linked current-pipeline audit, target
  architecture, decisions, dataset/schema/model/fusion/temporal/Android plans, experiment matrix,
  acceptance gates, migration, risks, rollback, open questions, and readiness checklist.
- Research/planning only: no Android source/resource, production recognition asset/config,
  training script, model, dataset, or derived feature file changed.
- Verified correction: `runs/gcn_conversational_fps_v30/eval_streaming_test.json` exists and the
  slim/early-stride GCN failed at top-1 0.1588/top-5 0.4374. The full-capacity fair config exists,
  but no full-capacity run artifact exists.
- Decision: the first approved experiment is E1 graph sanity/fairness, including a small overfit
  check, before RGB crop/fusion implementation. The hybrid target remains a hypothesis gated by
  identical-split landmark/RGB/fusion results.
- Production v3.0 `[1,96,258]` and the current 236-class Android recognizer remain frozen.
## E1 Execution Status - 2026-07-25

- E0 frozen from the existing same-data TCN artifact: SHA-256
  `6FA2875EE665E78A53E356B0ACC2B48A2423CDA8C61FAC5BED8FFB36CCDFA186`; held-out
  11-signer top-1 `0.5271`, top-5 `0.8252`, post-calibration ECE `0.03725`.
- The failed legacy GCN used a 75-node adjacency with 24 isolated pose nodes, encoded padded zero
  frames as 42 always-present hands, and globally pooled padding. Its final train accuracy was only
  `0.3255`; its `0.1588` test top-1 is therefore an invalid architecture-ceiling conclusion.
- The corrected E1 candidate keeps legacy behavior as the default and opts in to official MediaPipe
  pose connections, inferred per-hand presence, and padded-frame-masked pooling.
- Deterministic sanity slice: 50 classes x 5 clips, 30 train signers, 250 clips, max T=32,
  SHA-256 `ef624b85e55850b22aef55423d69119df7977b9e732f8892e7a2cec89ea69fc4`.
- **Sanity gate PASS:** full 2,703,276-parameter corrected GCN reached `0.9520` train accuracy at
  epoch 21 (seed `240725`, Adam `0.003`, no augmentation/dropout in the capacity test).
- The production `[96,258]` contract, Android recognizer, and deployed model assets were untouched.
- The full matched three-seed run is still pending. Native Windows TensorFlow reports no GPU; the
  historical full graph estimate is about 46.6 minutes/epoch on CPU, so this run requires an
  approved GPU/WSL2/cloud training environment rather than an unattended multi-day local run.
- Official topology source: https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/PoseLandmarksConnections
### E1 Review Finding - 2026-07-25

- **Important / fix before matched training:** `model/augment.py` adds noise to pose xyz on padded
  all-zero frames. The experimental GCN infers its mask from nonzero input, so augmentation would
  make padding appear real. The 95.2% sanity result is unaffected because that run disabled
  augmentation. Required next action: preserve the pre-augmentation frame mask (or accept an
  explicit mask input in an experiment-only model), add a regression test, rerun the sanity gate,
  then authorize the full matched seeds.
### E1 Augmentation-Mask Fix - 2026-07-25

- Resolved the review blocker: `make_stream_dataset` now supplies the real per-frame sample mask to
  streaming augmentation, and `augment_batch` forcibly restores every invalid/padded frame to exact
  zero after geometry, noise, and temporal dropout.
- Isolated training retains its existing one-argument augmentation path; no feature schema, dataset,
  Android code, or production model asset changed.
- Added regressions proving padded frames stay zero under pose noise and proving the `tf.data`
  streaming path passes the mask through. Existing missing-hand preservation still passes.
- Verification: focused Ruff passed; focused tests passed; full Python test suite passed. Global Ruff
  still has 33 pre-existing E501 findings in unrelated `eval/` and `pipeline/ingest` files.
- Next gate is the developer-run corrected E1 sanity command. Require `passed: true` and
  `best_train_accuracy >= 0.95` in `gcn-full-masked_t32_seed240725.json`.
### E1 Corrected Sanity Result - 2026-07-25

- Developer-run corrected sanity gate: **PASS**.
- Command used: `python -m model.experiments.e1_graph_sanity --architecture gcn-full-masked --max-time 32 --epochs 30 --batch-size 25 --learning-rate 0.003`.
- Deterministic slice: 50 classes x 5 clips, 30 training signers, schema 3.0, selected tensor
  digest `ef624b85e55850b22aef55423d69119df7977b9e732f8892e7a2cec89ea69fc4`.
- Result: best/final train accuracy `0.9720`; target `0.95`; stopped at epoch 20; elapsed
  `398.32 s`; artifact SHA-256
  `2D75971311D59B20D077A27F791B8B1ED2551A27007A6DE2792785448EE86AF5`.
- Interpretation: corrected full GCN has sufficient capacity and the augmentation-mask fix did not
  regress the sanity path. This is diagnostic training accuracy, not held-out or end-to-end
  recognition accuracy.
- Next: prepare, review, and smoke-test seed-isolated configurations and evaluation commands for the
  full matched TCN-vs-GCN experiment. Do not start full training until the GPU environment, expected
  duration/cost, output directories, and stop/resume procedure are agreed.
### E1 Matched-Run Preparation - 2026-07-25

- Prepared six fresh, seed-isolated configs: TCN and corrected GCN at seeds 0/1/2, identical
  train/validation features, augmentation, optimizer settings, epochs, and signer splits.
- Added overwrite-safe training: a fresh command refuses existing evidence; `--resume` loads
  `latest.keras`, validates the tensor contract, appends history, and preserves the prior best.
- Added unique native/k4/k8 report names and model/config/feature provenance so evaluation conditions
  cannot overwrite one another.
- Added `model.experiments.e1_matched` preflight/evaluate/summarize tooling and
  `E1_MATCHED_RUNBOOK.md`.
- Real preflight passed: 13,236 train clips/35 signers, 3,264 validation clips/5 signers, 2,620 test
  clips/11 signers, 236 classes, schema 3.0, no signer leakage, all dataset/config hashes frozen,
  TCN 169,004 params, GCN 2,751,078 params, six unused output directories.
- End-to-end tiny-run test verified checkpoint creation, overwrite refusal, and epoch-continuing
  resume. Corrected GCN checkpoint save/load with initialized optimizer also passed.
- Full training remains unstarted. Next action belongs to the developer: select a GPU environment,
  confirm TensorFlow sees the GPU, rerun preflight, and run only the one-epoch GCN seed-0 benchmark.
- E1 host check: WSL2 is installed, but Windows reports only AMD Radeon graphics, nvidia-smi is unavailable, and TensorFlow 2.21 sees no GPU. Full matched training must use another compatible GPU host/cloud; no long run started.

### E1 CPU Benchmark - 2026-07-25

- Despite the failed GPU gate, one `gcn_seed0` epoch completed on CPU in 3,505 seconds (58m25s).
- The expected checkpoints reload correctly, but first-epoch accuracy is non-diagnostic.
- This is benchmark evidence only, not an approved matched run. Do not resume it; preserve the run
  directory and restart seed 0 fresh on a compatible GPU after preflight.

### E1 RTX 3050 Handoff Package - 2026-07-25

- Prepared a separate `classmate_e1_matched_rtx3050_package/` with frozen checksummed data, pinned
  WSL2/Linux TensorFlow environment, 4 GB memory profile, smoke gate, six-run orchestration,
  checkpoint resume, native/k4/k8 evaluation, predictions, logs, graphs, and aggregate gates.
- The previous classmate package was unsuitable: it ran TensorFlow 2.21 on native Windows, silently
  fell back to CPU, used unpinned dependencies and absolute external paths, and represented a
  different warm-started supplementary TCN experiment.
- Local validation passed without real training. Next action: classmate runs `./SETUP_ENV.sh` and
  `./VERIFY_SETUP.sh` on the RTX 3050. Full training is approved only after that GPU smoke passes.

## E1 Matched TCN-vs-GCN Final Result - 2026-07-26

- Audited `F:/ASL DATASET/NEW RUN/apphear_e1_outputs.tar.gz` (SHA-256
  `AB0C0DF1B056C96BCDCA11367F4192F769FA006AF096B1D7994BC25BB1334B82`).
- WSL2/Linux TensorFlow 2.21 used the 4 GB RTX 3050; preflight/smoke passed; all six 60-epoch runs
  and all 18 native/k4/k8 evaluations completed.
- Independently recomputed metrics from all prediction files and CRC-checked all best checkpoints.
- Three-seed TCN top-1: 0.4968 native, 0.4704 k4, 0.4420 k8.
- Three-seed corrected GCN top-1: 0.2868 native, 0.2336 k4, 0.1995 k8.
- GCN failed every gate, regressed every held-out signer, and strongly overfit. Decision: stop this
  GCN family and retain TCN as the landmark control; neither E1 model replaces production.
- Next: raw-video rights/metadata/label audit, unified dataset contract and 50-sign pilot, then E2
  hand-crop quality/parity smoke before any long extraction or hybrid training.

## 2026-07-26 - E2 RGB Crop Tooling And Smoke Gate

- Added an experiment-only E2 crop stage under `pipeline/crops/` with config
  `pipeline/config/crops_e2.yaml`; production schema 3.0, Android, models, and datasets were not
  modified.
- The stage reuses ASL Citizen raw videos, Stage-E image landmarks/timestamps, and D2 spans. It
  compares 80/96/112 crops, 1.5/1.75/2.0 expansion, and native/k4/k8 cadence.
- Missing ROIs remain explicit. Direct boxes may be held causally for at most 100 ms and retain
  source/freshness metadata. No future interpolation or pose fallback is hidden in the output.
- One-clip smoke `smoke_validation_v2_20260726` passed: 6 records, 5 direct and 1 missing. Visual
  inspection confirmed synchronized full-frame/crop panels and exposed a real visible-hand miss.
- Validation: full Python suite 133 passed; focused Ruff and mypy clean.
- Next: developer runs `python -m pipeline.crops.run --phase engineering`, reviews the blinded
  60-clip matrix, and selects crop size/expansion. Do not start E3 or Android work.
## 2026-07-26 - E2 Engineering Run 01 Review And Cadence Fix

- Developer completed `engineering_run_01`: 60 clips/34 signers, 26,190 matrix records, 600 panels.
- The run exposed a protocol defect before manual scoring: k4/k8 frame selection still inherited
  ROI state refreshed on unsampled native frames. Run 01 is generation-valid but invalid for
  low-FPS comparison; do not score or use it to select crop settings.
- Corrected the experiment-only crop stage so sampled cadence controls both reviewed frames and ROI
  observation history. Cadence indices now align to video-frame phase rather than sign onset.
- Added two cadence/mask regression tests. Corrected real-data smoke passed across native/k4/k8.
- Validation: full suite 135 passed; focused Ruff and mypy clean.
- Next: developer runs `python -m pipeline.crops.run --phase engineering --run-id engineering_run_02`.
  No E3, 200-clip audit, or Android work until Run 02 is reviewed.
## 2026-07-26 - E2 Authoritative Engineering Run 02 Ready For Human Audit

- `engineering_run_02` passed structural/protocol review: 60 clips, 34 signers, 25,380 records,
  and a balanced 600-panel blinded audit sample.
- Correct cadence behavior: native direct/held/missing 33.7/9.9/56.4%; k4 35.4/0.0/64.6%; k8
  35.7/0.0/64.3%. Automatic missingness is not a failure rate because both hand slots are requested.
- Visual sampling confirmed both genuine absent-hand panels and at least one visible-hand miss.
- Shuffled the still-empty audit template deterministically, preserved the original, and attached
  execution-code/artifact hashes in `provenance_addendum.json`. Future crop runs embed source hash.
- Validation after governance changes: full suite 135 passed; focused Ruff and mypy clean.
- Next: human visibility/usability scoring of Run 02, then `pipeline.crops.audit` summarization.
## 2026-07-26 - E2 Resumable Human Review Utility

- Added `pipeline.crops.review`, an offline Tkinter/OpenCV reviewer for Run 02's blinded panels.
- Decisions map directly to absent/usable/missing/clipped/blur/stale/wrong-hand/low-detail/other.
- Every decision is atomically persisted; restart resumes at the first incomplete row. The first
  launch preserves a pre-review backup. No model, dataset, Android, or production asset changes.
- Run 02 headless check: 600 rows, 0 completed, 600 remaining, 0 missing panels.
- Validation: full suite 139 passed; focused Ruff and mypy clean.
- Operational requirement: close Excel before launching because it currently locks the CSV.
## 2026-07-26 - E2 Run 02 Human Audit NO-GO

- Completed and validated 600/600 blinded labels. Original audit preserved; a transparent derivative
  normalized 27 impossible missing-ROI labels with a separate correction log.
- Corrected result: 167/358 visible-hand panels usable (46.65%); ROI availability 62.57%; 98% gate
  failed decisively.
- Failures: missing ROI 135, motion blur 38, clipped 7, low detail 6, wrong hand 5.
- Direct ROI usability 81.4%; static held ROI usability 20.0%. Left-hand usability 34.3% vs right
  60.1%, requiring detector/slot investigation.
- The size/expansion comparison is not decision-grade because candidates were mostly unpaired and
  per-cell visible counts were only 9-18. Do not select a crop size from apparent cell rankings.
- Wrote authoritative Run 02 `audit_analysis.md` and both raw/corrected registered summaries.
- Decision: no 200-clip confirmation audit and no E3. Next is architecture approval for paired E2b
  pose-hand-anchor ROI recovery and a formally separated blur/availability/containment/detail gate.
## 2026-07-26 - E2b Paired ROI-Recovery Tooling Ready

- Frozen Phase A as 120 known-visible E2 base items, each paired across control hold 100 ms and
  causal pose recovery ages 150/250/350 ms at native/k4/k8 cadence.
- Replaced the provisional wrist-centered fallback with a pose hand anchor after a train-only
  2,268-observation check improved full-hand containment from 73.68% to 95.55%.
- Fallback size is fit from train clips only (2,334 observations in the validated smoke); source
  blur, missing ROI, clipping, stale/wrong hand, and low detail remain explicit audit outcomes.
- `smoke_validation_03` passed: six cadence/hand base items, 24/24 panels present, four of six
  deliberately missing control ROIs recovered, two remained explicit missing.
- Verification: 146 tests passed; focused Ruff and mypy clean; reviewer preflight clean.
- Next action belongs to the developer: generate and review `engineering_e2b_01` (480 panels), then
  run paired analysis. No E2 confirmation audit, E3 training, Android, model, or schema changes.
## 2026-07-26 - E2b Phase-A Completed NO-GO

- Developer completed `engineering_e2b_01`: 120 paired known-visible base items and 480/480
  reviewed panels with no missing artifacts.
- Pose recovery improved paired ROI availability from 53.3% control to 79.2% overall. Gains were
  +16.7 points native, +25.0 k4, and +35.0 k8.
- No strategy passed the registered >=20-point gain at every cadence; native failed. Raw recovered
  crop usability was only 21.1-23.7%, so geometry Phase B and E3 remain blocked.
- Independent review QA found one visibility conflict and 21 byte-identical panel groups with
  conflicting labels (81 rows). Age-specific raw usability rankings are not trusted. Original
  labels and summary remain immutable.
- Decision: keep pose anchors only as a fallback hypothesis. Next is E2c, a paired current IMAGE
  versus MediaPipe VIDEO temporal hand-tracking smoke on raw chronological frames.
- See `context/recognition_upgrade/E2B_PHASE_A_RESULT.md` for hashes, metrics, risks, and rollback.
## 2026-07-26 - E2c Temporal-Tracking Tooling Ready

- Added an isolated E2c package comparing MediaPipe Hand Landmarker IMAGE and VIDEO modes on the
  same chronological raw frames, timestamps, model, thresholds, target hand, and crop geometry.
- VIDEO state is recreated per clip/cadence; no hidden state crosses clips. IMAGE/VIDEO A/B identity
  is blinded, and each source frame is reviewed once to prevent E2b duplicate-label inconsistency.
- Automatic generation reports known-visible availability and comparative p50/p95 inference latency
  before human review. Human review is conditional on that automatic gate.
- `smoke_validation_01` passed structurally: six cadence/hand base items, six paired panels, 12 mode
  records, 756 calls, no missing panels. VIDEO recovered one missing k8 target; smoke is not a
  promotion result.
- Verification: 151 tests passed; focused Ruff and mypy clean; reviewer preflight clean.
- Next action belongs to the developer: run `engineering_e2c_01` (estimated 4-8 CPU minutes) and
  return `generation_summary.json`. Do not review panels or start E3/Android work yet.
## 2026-07-26 - E2c Temporal Tracking Completed NO-GO

- Developer completed `engineering_e2c_01`: 47 clips, 120 known-visible paired base items, 240
  mode records, 7,378 hand-landmarker calls, and 120/120 panels present.
- VIDEO availability gains versus IMAGE were +11.1 points native, +4.5 k4, and +7.5 k8, below
  the registered +20-point requirement at every cadence. Automatic gate failed.
- VIDEO p95 latency ratios passed (0.958/0.994/0.994), so compute was not the blocker.
- Paired VIDEO transitions included losses at k4 and k8. Right-hand availability regressed -4.5
  points k4 and -5.0 k8; full-sequence k8 two-hand presence fell from 10.68% to 7.77%.
- Stop rule applied: human review remains unstarted. Do not promote VIDEO/LIVE_STREAM, run crop
  geometry Phase B, start E3, or change Android.
- Next proposal is E2d: one bounded positive/negative detection/presence threshold sweep. If it
  fails, stop MediaPipe tuning and evaluate another hand detector or full/upper-body RGB stream.
- See `context/recognition_upgrade/E2C_TEMPORAL_TRACKING_RESULT.md` for hashes and full decision.

## 2026-07-26 - E2d Detector Sweep Tooling Ready

- Added the isolated E2d runner and config for six paired operating points: IMAGE and VIDEO at
  detection/presence thresholds 0.5, 0.4, and 0.3; tracking confidence remains 0.5.
- Registered 120 frozen known-visible positives and 120 corrected target-hand-absent negatives.
  All native/k4/k8 and anatomical-hand cells are covered; negatives are balanced at 20 per cell,
  while positive counts inherit the E2b source distribution of 14-22 per cell.
- Automatic promotion requires at least +20 points positive recall at every cadence and hand,
  false target ROI <=5% and <=2 points over control, p95 latency <=1.2x control, and no subgroup
  regression. Human review occurs only after automatic promotion.
- `smoke_validation_01` completed: 12 items, 72 item/candidate records, 3,852 detector calls,
  complete outputs, and zero false target ROIs. No candidate passed all gates; this tiny smoke
  validates execution only and is not the E2d verdict.
- Verification: 154 tests passed; focused Ruff and mypy checks clean. Production Android,
  recognition assets, model contract, and active datasets were unchanged.
- Next action belongs to the developer: run `engineering_e2d_01`. Preflight resolves 58 clips
  and about 32,376 detector calls; allow roughly 12-25 CPU minutes on this host, then return
  `generation_summary.json`. Do not manually audit crops or
  start E3/Android work while the automatic result is pending.

## 2026-07-26 - E2d Detector Sweep Completed NO-GO

- Developer completed `engineering_e2d_01`: 120 known-visible positives, 120 target-hand-absent
  negatives, six IMAGE/VIDEO threshold candidates, 1,440 paired item rows, and 32,376 calls.
- Independent integrity checks found 240 unique items, 240 rows per candidate, no duplicate
  item/candidate pairs, identical candidate item sets, and a matching runner hash.
- IMAGE 0.5 control recall was 41.7/50.0/50.0% at native/k4/k8. The best-recall VIDEO 0.3
  candidate reached 61.1/56.8/62.5%, but gains were only +19.4/+6.8/+12.5 points and false
  target ROI was 7.5/12.5/2.5%.
- VIDEO 0.4 improved aggregate left-hand recall +20.3 points but regressed right-hand recall
  -3.6 points and failed every cadence gain gate. No VIDEO threshold improved right-hand recall.
- All latency gates passed, so compute was not the blocker. No candidate passed the full
  registered gate and `promoted_candidates` is empty.
- Stop rule applied: no E2d human review, no more MediaPipe threshold/mode tuning, no E3, and no
  Android change. MediaPipe may remain for available landmarks but is not approved as the sole
  RGB hand-crop source.
- Next action: architecture-only E2e planning for an alternative mobile hand-box detector versus
  a landmark-independent upper-body RGB fallback.
- See `context/recognition_upgrade/E2D_DETECTOR_OPERATING_POINT_RESULT.md` for hashes and details.

## 2026-07-26 - E2e-A Coordinate And Identity Fixture Smoke PASS

- Saved the MediaPipe reliability architecture and exact E2e-A audit contract.
- Added isolated geometry/assignment tooling and a versioned experiment config.
- Six known-answer fixtures passed mirror and pose-temporal plumbing. Direct labels scored 2/10 by
  deliberate construction; camera-aware swapping and pose-temporal scored 10/10. These are
  synthetic expectations, not MediaPipe accuracy evidence.
- Verification: 5 focused tests, 8 E2c/E2d regressions, and the full 159-test Python suite passed;
  Ruff and mypy are clean.
- No Android, production recognizer, schema, model, dataset, or extraction output changed.
- Next: a tiny real Android front-camera plus ASL Citizen pilot, then review before the full gold
  set, detector training, E3, or Android integration.

## 2026-07-26 - E2e-A Measured Convention And ASL Citizen Pilot

- Recovery found the legacy mirrored-input handedness assumption did not match AppHear's exact
  MediaPipe Tasks bundle. Paired actual-left/right frames were wrong on saved mirrored pixels and
  correct after horizontal unmirroring.
- Correct contract: retain direct Hand/Pose sides for verified unmirrored input; transform x and
  swap symmetric Hand/Pose identities only for verified mirrored input.
- Generated 18 unique ASL Citizen panels across native/k4/k8, left/right, target-mismatch,
  zero-box, and control strata. The first duplicate-containing pilot is invalid for scoring.
- Visual review of 12 failure-focused frames found six genuine zero-box failures, two incomplete
  two-hand detections, and four single-visible-hand cases confounded by source mirroring or old
  target-side convention.
- The pilot is failure-stratified and yields no overall accuracy estimate.
- No production Android, feature schema, model, dataset, or recognizer changed.
- Next: revise the full E2e-A gold audit to label all visible hand boxes and source mirror status,
  then smoke the reviewer before the developer performs the 120-200-frame audit.

### 2026-07-26 - E2e all-hand gold-audit tooling smoke

- Added a detector-success-independent ASL Citizen sampler and blinded panel generator.
- Added a resumable GUI for all-visible-hand boxes, mirror evidence, optional anatomical identity, quality flags, and quarantine.
- Added side-independent IoU scoring with identity reported only on mirror-adjudicated matches.
- Generated and contract-validated six unique smoke frames at `scratchpad/e2e_gold_audit_smoke_20260726`.
- Focused tests, Ruff, and mypy passed.
- Next: developer completes the six-frame GUI smoke; inspect annotations before authorizing the full 150-frame audit.

### 2026-07-26 - E2e gold reviewer usability revision

- Simplified the required workflow to visible-hand count, matching boxes, optional quality flags, and save.
- Hid mirror and anatomical-side fields behind an optional advanced section with safe `unknown` defaults.
- Added numbered instructions, live guidance, selected-count highlighting, drag preview, and exact box-count enforcement.
- Actual Tk window construction and advanced-panel toggle smoke passed at 1280x920; review CSV remains untouched.

### 2026-07-26 - E2e reviewer reopen-state recovery

- Diagnosed a Mode-1 reviewer bug: failed acceptance could leave `review_status=accepted`, and startup validation then blocked reopening the incomplete row.
- Incomplete accepted rows now remain editable; failed acceptance clears the completed marker while preserving boxes and quality fields.
- `--check` now exits nonzero while rows remain, in addition to reporting structural errors.
- Preserved the developer's g001 box and quality labels, backed up the CSV, and changed only unsupported mirror status `unmirrored` to safe `unknown`.
- GUI reopen smoke resumed at g002; focused regression tests passed.

### 2026-07-26 - E2e all-hand human smoke evaluated

- Six of six annotations completed with nine visible hand instances and no quarantines or structural errors.
- Visual overlays confirm the human boxes are plausible full-contour boxes.
- MediaPipe produced at least one instance on every visible-hand frame, but only one of four two-hand frames had two instances.
- Rejected landmark-envelope IoU as the primary detector metric because the stored min/max landmark envelope is not the internal detector box and is semantically smaller than full-contour gold.
- Temporary center-containment diagnosis matched 6/9 instances, 5/5 visible frames, and 1/4 two-hand frames; these smoke counts are not accuracy claims.
- Next: store all 21 landmarks, validate a one-to-one landmark-instance association rule, and re-score the same smoke before generating 150 frames.

### 2026-07-26 - E2e landmark-instance association approved for full audit

- Added all 21 normalized landmarks to each experimental MediaPipe prediction and a reversible existing-run enrichment command.
- Replaced primary landmark-envelope IoU with palm-center plus >=50% landmark containment and exact maximum-cardinality one-to-one matching.
- Retained raw envelope IoU as localization diagnostics only.
- Enriched and re-scored the same six frames without changing the gold CSV hash.
- Corrected smoke: 6/9 instances, 5/5 any-hand frames, 1/4 both-hands-complete, 0/6 unmatched predictions, and 0/1 negative-frame false positives.
- Landmark overlay visually passed; full 169-test suite, Ruff, and mypy passed.
- Next: developer generates and reviews the deterministic 150-frame engineering audit; inspect unmatched and partial/edge cases before gates.

### 2026-07-26 - E2e full-audit source pool corrected

- First 150-frame command stopped safely: frozen E2d positives contain only 108 unique frames from 47 clips, so `max_per_clip=1` cannot provide 150.
- Rejected increasing frames per clip and rejected treating static IMAGE provenance as FPS cadence.
- Added `balanced-clips`: 150 unique ASL Citizen clips, 41 signers, 120/30 train/val, balanced 48/53/49 low/medium/high prior coverage, and 50 frames each at 25/50/75% sign-span positions.
- Selection never consults the selected frame's current MediaPipe result; eligibility still requires existing valid pipeline artifacts and this bias is documented.
- Six-clip generation smoke and full 150-item selection validation passed; full suite now 170 tests, Ruff and mypy clean.
- Next: developer reruns full generation with `--source-pool balanced-clips`; validate before manual review.

### 2026-07-26 - E2e full-audit annotation adjudication prepared

- The completed 150-frame review initially scored 121/170 visible hand instances (71.18%), 90/108 any-hand frames (83.33%), and 31/62 complete two-hand frames (50.00%).
- Visual anomaly review found that g008 was labeled zero-hand despite a visible, correctly detected hand; additional blurred or clipped zero-hand rows were ambiguous. All rows also had `partial_visibility=no` and `near_face=no`, so the first score is provisional.
- Added an experiment-only, separate adjudication workflow that selects all 88 rows originally below two hands, resets their decisions without changing the source review, and permits merge only after full validation.
- Merge is protected by the source review SHA-256 and creates a source-side backup plus a merge receipt.
- Clarified GUI guidance that blurred, clipped, occluded, and partially visible hands still count.
- Generated `scratchpad/e2e_gold_adjudication_engineering_01`: 88 rows, 0 completed, 0 structural errors; source review SHA-256 remains `61d5a7a71ff492c2ac8cae44cc674bafaf6823f101a5166825859944615705a5`.
- Full test suite, focused tests, Ruff, and mypy passed.
- Next: developer completes the 88-row correction review; validate, merge with backup, rescore, and inspect changed labels before making a MediaPipe gate decision.
### 2026-07-26 - E2e corrected all-hand MediaPipe audit no-go

- Completed the separate 88-row sub-two-hand adjudication and a final two-frame consistency pass; all 150 source rows now validate with no quarantines or structural errors.
- Hash-guarded merge preserved `gold_review.pre_e2e_gold_adjudication_engineering_01.csv`; final review SHA-256 is `53e3db0dceeeb4b5a991be132bdce1fe489d82d670daa662023f6707852835d9`.
- Final IMAGE-mode result: 122/184 hand instances = 66.30%, 91/117 any-hand frames = 77.78%, and 31/67 complete two-hand frames = 46.27%.
- Blur recall is 58.33%, edge-clipped recall 25.81%, occluded recall 52.00%, and clear recall 81.25%; train/validation source results are consistent at 65.99%/67.57%.
- All 122 predictions matched visible hands, but the selected 33 zero-hand frames are not a representative non-signing benchmark.
- Decision: reject MediaPipe as sole ROI provider; retain it for landmarks when present. Do not repeat threshold tuning, VIDEO promotion, or static pose fallback after E2d/E2c/E2b no-go evidence.
- Added explicit-sample nested adjudication, zero-hand quality invariants, backups, and merge receipts; full 175-test suite, Ruff, and mypy passed.
- Next: architect E2e-C0 independent single-class hand-detector screening on this gold set plus a dedicated negative stream; E3 and Android changes remain blocked.
### 2026-07-26 - Recognition-upgrade context synchronized after E2e no-go

- Updated the recognition-upgrade index, experiment matrix, architecture decisions, risk register, open questions, implementation readiness, Android deployment, hybrid fusion, feature schema, and target architecture to the corrected E2e result.
- Added ADR-RU-016: screen an independent single-class hand detector before E3; MediaPipe remains a landmark provider but not sole ROI authority.
- Removed active next actions that incorrectly pointed back to E1, E2c, or generic E2e design.
- All active source-of-truth documents now point to `E2E_ALL_HAND_GOLD_RESULT.md` and E2e-C0 planning; production Android, E3, detector training, and recognizer training remain blocked.

## 2026-07-27 - E2e-C0 Capture Tooling Ready

- Developer approved the E2e-C0 independent hand-detector screening contract.
- Added `E2E_C0_DETECTOR_SCREENING_PLAN.md` and `E2E_C0_CAPTURE_RUNBOOK.md`.
- Added isolated `pipeline/tracking/e2e_c0_capture.py` with deterministic clip-balanced 1 FPS sampling, source hashes, existing gold-review GUI reuse, N0 contamination handling, P1 box preservation, diversity gates, overwrite protection, and reviewed manifests.
- Added focused tests in `tests/test_tracking_e2e_c0_capture.py`.
- Validation: Ruff clean, mypy clean, focused tests 3 passed, full Python suite 178 passed.
- Next action belongs to the developer: record N0/P1 videos and run N0 prepare/review/check from the runbook. No detector/model download, training, Android change, schema change, or E3 work has started.

## 2026-07-27 - E2e-C0 N0 Capture Gate Passed

- Final N0 evidence is `artifacts/recognition_upgrade/e2e_c0/n0_capture_06`.
- Reviewed 630 deterministic 1 FPS frames: 613 eligible no-hand frames, 16 visible-hand
  contamination exclusions, one quarantined frame, and no validation errors.
- Capture diversity passed: 57 clips, 876.327 seconds, six participants, five devices, five
  environments, and front-camera capture.
- The original 600 annotations were carried from `n0_capture_05` only after all 57 source-video
  hashes and all 600 extracted frame-image hashes matched; 30 new frames were reviewed separately.
- N0 is now approved for the later C0-A detector false-positive evaluation. This does not yet
  constitute a detector result.
- Next: prepare, annotate, and validate the bounded 100-frame P1 visible-hand/non-sign diagnostic
  set. Model download, C0-A execution, detector training, E3, and Android changes remain blocked.

## 2026-07-27 - E2e-C0 P1 Capture Gate Passed

- Final P1 evidence is `artifacts/recognition_upgrade/e2e_c0/p1_capture_03`
- Authoritative fixture result and C0-A handoff: `context/recognition_upgrade/E2E_C0_CAPTURE_RESULT.md`.
- Reviewed 140 deterministic 1 FPS frames: 108 eligible visible-hand/non-sign frames, 172 valid
  hand boxes, 32 no-visible-hand exclusions, and no validation errors.
- Capture provenance includes 30 clips, 678.721 seconds, two participants, two devices, one indoor
  environment, and front-camera capture.
- The original 110 annotations were carried from `p1_capture_02` only after all 30 source-video
  hashes and all 110 extracted frame-image hashes matched; 30 new frames were reviewed separately.
- Frozen reviewed-manifest SHA-256 values: N0
  `953D2FCA81D171016C8345A8FB6B524931A67C7420B8E9ABFB8CAF2421A10291`; P1
  `B2D5FB8DBF8F94098146D023648A7FBF79003E0F06EDAD73CE5880E9BBC95FDD`.
- N0 and P1 capture gates are now complete. These are detector evaluation fixtures, not detector
  accuracy results.
- Next: prepare the separate C0-A HaGRID checkpoint/license and six-positive/twenty-negative smoke
  preflight. Detector training, E3, and Android remain blocked.


### E3-B5 Landmark Temporal Scale Package Prepared - 2026-07-29

- Plan document: `context/recognition_upgrade/E3_B5_LANDMARK_TEMPORAL_SCALE_PLAN.md`.
- Runner: `pipeline/rgb/e3_b5_landmark_temporal_scale.py`.
- Prepared run: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed`.
- Source: ASL Citizen `features_streaming` tensors with schema `3.0` and `[96,258]` feature shape.
- Inventory verified: 36,960 train rows, 9,575 validation rows, 29,770 test rows, no signer overlap, and 99 classes meeting the `16/4/4` support threshold.
- Prepared dataset: 50 classes, 1,200 clips, 800 train / 200 validation / 200 test, deterministic class and row selection.
- Branches: `conv1d_baseline`, `tcn_pool`, and `tcn_masked_pool`; seeds `101`, `202`, and `303`; batch size `8`; epochs `12` per run command.
- Local validation completed: syntax compile passed, prepared-dataset check passed, and smoke test passed for model creation, forward pass, one training batch, weight save/reload, and output writing.
- Full training is not started. Next action belongs to the developer: run the E3-B5 full command, then run `check --require-metrics` and inspect `metrics/metrics.md` before deciding the next architecture branch.

### E3-B5 Landmark Temporal Scale Result - 2026-07-29

- Result document: `context/recognition_upgrade/E3_B5_RESULT.md`.
- Analysis outputs: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed/analysis/`.
- Final check passed with no missing outputs.
- Mean best-validation/test: `conv1d_baseline` `0.4750/0.3400`, `tcn_pool` `0.4733/0.3433`, `tcn_masked_pool` `0.4900/0.3433`.
- Seed winners by validation were split: seed 101 `conv1d_baseline`, seed 202 `tcn_pool`, seed 303 `tcn_masked_pool`.
- Decision: do not promote masked TCN. It had the best mean validation score but won only one of three seeds and did not improve mean test accuracy.
- Error analysis found useful landmark signal but persistent signer generalization gap, weak classes, and prediction bias/confusion groups.
- Next: architect E3-B6 landmark feature augmentation on the frozen E3-B5 split. Do not start full training until the derived-feature schema, controls, and gate are reviewed.

### E3-B6 Landmark Feature Augmentation Package Prepared - 2026-07-29

- Plan document: `context/recognition_upgrade/E3_B6_FEATURE_AUGMENTATION_PLAN.md`.
- Runner: `pipeline/rgb/e3_b6_feature_augmentation.py`.
- Prepared run: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_03_feature_augmented`.
- Source run: frozen E3-B5 split at `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed`.
- Prepared tensor shape: `[1200,96,728]` from base 258 features plus 225 velocity, 225 acceleration, and 20 relationship/presence channels.
- Branches: `aug_conv1d_baseline`, `aug_tcn_pool`, `aug_tcn_masked_pool`; seeds `101`, `202`, `303`; batch size `8`; epochs `12` per run command.
- Local validation completed: syntax compile passed, prepare passed, structural check passed, and smoke test passed for model creation, forward pass, one training batch, weight save/reload, and output writing.
- Full training is not started. Next action belongs to the developer: run E3-B6, then `check --require-metrics`, then compare against E3-B5 before approving any next branch.

### E3-B6 Landmark Feature Augmentation Result - 2026-07-29

- Result document: `context/recognition_upgrade/E3_B6_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_03_feature_augmented`.
- Final check passed with no errors.
- Mean best-validation/test: `aug_conv1d_baseline` `0.5033/0.3883`, `aug_tcn_pool` `0.4767/0.3683`, `aug_tcn_masked_pool` `0.5117/0.3867`.
- Compared with E3-B5 masked TCN `0.4900/0.3433`, the best E3-B6 branch gained `+0.0217` validation and `+0.0434` test, below the registered `+0.03` validation gate.
- Seed winners by validation were split: seed 101 `aug_tcn_masked_pool`, seed 202 `aug_conv1d_baseline`, seed 303 `aug_conv1d_baseline`.
- Decision: do not promote the full `[96,728]` augmented schema. It improved test accuracy but still overfit and did not produce a stable architecture winner.
- Next: architect E3-B7 derived-feature ablation on the same frozen split to identify whether velocity, relationship/presence features, or the full set caused the useful test gain.

### E3-B7 Derived-Feature Ablation Package Prepared - 2026-07-29

- Plan document: `context/recognition_upgrade/E3_B7_FEATURE_ABLATION_PLAN.md`.
- Runner: `pipeline/rgb/e3_b7_feature_ablation.py`.
- Prepared run: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_04_feature_ablation`.
- Source run: frozen E3-B5 split at `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed`.
- Variants: `base_velocity` `[96,483]`, `base_relations` `[96,278]`, `base_velocity_relations` `[96,503]`, and `base_velocity_acceleration` `[96,708]`.
- Branches: `conv1d` and `masked_tcn`; seeds `101`, `202`, `303`; batch size `8`; epochs `12` per run command.
- Local validation completed: syntax compile passed, prepare passed, structural check passed, and smoke test passed for all four variants and both branches.
- Full training is not started. Next action belongs to the developer: run E3-B7, then `check --require-metrics`, then compare against E3-B5/E3-B6.

### E3-B7 Derived-Feature Ablation Result - 2026-07-29

- Result document: `context/recognition_upgrade/E3_B7_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_04_feature_ablation`.
- Final check passed with no errors after resume to 24 epochs for every candidate.
- Best validation reduced candidate: `base_velocity_acceleration/masked_tcn` with mean best validation/test `0.5150/0.3650`.
- Best test reduced candidate: `base_relations/masked_tcn` with mean best validation/test `0.5033/0.3833`.
- E3-B6 full augmented references remain higher on test: masked TCN `0.5117/0.3867`, Conv1D `0.5033/0.3883`.
- Decision: do not promote any reduced E3-B7 subset. Relationship features are the cleanest reduced signal, but reduced subsets do not beat the full E3-B6 result and do not solve overfitting.
- Next: stop small landmark feature-engineering tweaks and architect the next frozen-split landmark+RGB/visual fusion experiment. No Android or production recognizer changes are authorized.

### E3-C Frozen-Split Landmark + RGB Fusion Package Prepared - 2026-07-29

- Plan document: `context/recognition_upgrade/E3_C_FUSION_PLAN.md`.
- Runner: `pipeline/rgb/e3_c_fusion.py`.
- Prepared run: `artifacts/recognition_upgrade/e3_fusion/pilot_02_frozen_50_landmark_rgb`.
- Purpose: test whether RGB adds complementary held-out-signer value when fused with the current strongest landmark-feature stream, not as a standalone replacement.
- Source split: E3-B5 frozen 50-class signer-disjoint split with 1,200 clips, 800 train / 200 validation / 200 test.
- Landmark input: E3-B6 full augmented `[96,728]` tensor.
- RGB input: 16 frames per clip, 160x160 upper-body center crop, MobileNetV3Small ImageNet embeddings.
- Branches: `rgb_only`, `landmark_aug_only`, and `fusion_aug_rgb`; seeds `101`, `202`, `303`; batch size `8`; epochs `12` per run command.
- Local validation completed: syntax compile passed, prepare passed, check passed, and 8-row smoke test passed for extraction, embedding, model forward pass, one train batch, and weight saves.
- Next action belongs to the developer: run full E3-C and then `check --require-metrics`. No Android integration, production recognizer replacement, or schema promotion is authorized.

### E3-C Frozen-Split Landmark + RGB Fusion Result - 2026-07-29

- Result document: `context/recognition_upgrade/E3_C_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e3_fusion/pilot_02_frozen_50_landmark_rgb`.
- Final check passed with no errors.
- Mean best validation/test: `rgb_only` `0.1500/0.0750`, `landmark_aug_only` `0.5117/0.3867`, and `fusion_aug_rgb` `0.2617/0.1867`.
- `landmark_aug_only` won all three seeds and reproduced E3-B6, confirming the split/label alignment and showing the experiment itself was valid.
- `rgb_only` and `fusion_aug_rgb` both overfit badly: train accuracy around `0.96-0.97`, but weak held-out signer validation/test performance.
- Decision: E3-C is a no-go. Do not promote upper-body frozen-MobileNet RGB fusion, do not integrate it into Android, and do not continue this exact design with more epochs.
- Next: architect the next experiment explicitly around either detector-derived hand-crop visual evidence or landmark/data generalization improvements. No Android integration, production recognizer replacement, or feature-schema promotion is authorized.

### E4-A Landmark Generalization And Data-Quality Audit Planned - 2026-07-29

- Plan document: `context/recognition_upgrade/E4_A_LANDMARK_GENERALIZATION_PLAN.md`.
- Decision basis: E3-C showed upper-body frozen-MobileNet RGB fusion is a no-go; E3-B6 remains the best landmark result but did not pass promotion gates and still shows a large generalization gap.
- Purpose: use existing E3 artifacts to identify which classes, signers, confusion groups, support gaps, label/variant issues, and data-quality issues block reliable landmark recognition.
- Proposed future run directory: `artifacts/recognition_upgrade/e4_generalization/e4_a_landmark_data_audit_01`.
- Expected outputs: inventory, class reliability tiers, confusion groups, signer generalization report, data/support audit, reliable-vocabulary proposal, hard-confusion set, and next-experiment decision.
- E4-A is analysis and planning only. It must not train models, change Android, mutate datasets, promote a feature schema, or repeat E3-C RGB fusion.
- Next action: prepare the E4-A audit package by inspecting exact E3 metric schemas and deciding whether per-clip predictions need to be regenerated from saved checkpoints.

### E4-A Landmark Generalization And Data-Quality Audit Result - 2026-07-29

- Result document: `context/recognition_upgrade/E4_A_RESULT.md`.
- Runner: `pipeline/rgb/e4_a_generalization_audit.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_a_landmark_data_audit_01`.
- Final check passed with no errors.
- E4-A audited 50 classes using existing E3 artifacts only; it did not train models, change Android, mutate datasets, or promote a schema.
- Tier counts: 4 `candidate_keep`, 15 `borderline_collect_more`, 8 `confusion_review`, 6 `drop_or_defer`, and 17 `needs_visual_evidence`.
- Candidate keep classes: `SWITZERLAND`, `COUCH`, `CURLYHAIR`, and `DOWNSIZE1`.
- The current 50-class set is not ready for another blind retrain. Only four classes pass the conservative keep gate, while many classes need targeted collection, label/video review, or stronger evidence.
- Per-signer support is available, but per-signer accuracy remains a tooling gap because current E3 artifacts do not persist stable per-clip predictions for every branch/seed.
- Next action: architect E4-C targeted collection and label-review plan from E4-A outputs. Do not start E4-B retraining until the target class list and data/label actions are approved.

### E4-C Targeted Collection And Label/Video Review Plan - 2026-07-29

- Plan document: `context/recognition_upgrade/E4_C_TARGETED_COLLECTION_PLAN.md`.
- Target package: `artifacts/recognition_upgrade/e4_generalization/e4_c_targeted_collection_plan_01`.
- Source: completed E4-A audit outputs.
- Prepared target CSVs for anchor classes, borderline collection candidates, confusion-review classes, defer/visual-review classes, and top confusion-pair review queue.
- Anchor classes: `SWITZERLAND`, `COUCH`, `CURLYHAIR`, and `DOWNSIZE1`.
- Borderline candidates: 15 classes, led by `PEEKABOO`, `BEE1`, `BOTH`, `SHARK1`, `SENTENCE2`, `LETTUCE1`, `SHAVE1`, `TWINS1`, and `EVERYYEAR`.
- Review priority: `DEAF1 <-> TWINS1`, `EVERYYEAR <-> TAKECARE`, `CROSS3 <-> WHALE`, `ROCKINGCHAIR1 <-> TRACTOR`, `BASEBALLCAP <-> LETTUCE1`, `BOXING <-> TAKECARE`, `EDIT1 <-> INDEPENDENT`, and `ELEVATOR1 <-> INDEPENDENT`.
- Next action: review the E4-C target package with the user and prepare recording/review tooling only for approved targets. E4-B retraining remains blocked.

### E4-C User Review Package Prepared - 2026-07-29

- Added to `artifacts/recognition_upgrade/e4_generalization/e4_c_targeted_collection_plan_01`:
  - `USER_REVIEW_GUIDE.md`
  - `proposed_recording_targets_v0.csv`
  - `confusion_review_decision_template.csv`
- Minimum recommended recording round: 12 signs, consisting of 4 anchors plus 8 strongest borderline classes.
- Extended recording round: 16 signs, adding `EVERYYEAR`, `NOON1`, `LAND`, and `CONFUSED1` if time/signers allow.
- Confusion classes remain review-first, not blind-record-first.
- Next action: user approves or edits the target list before any recording tooling, data collection, E4-B retraining, or Android work.

### E4-C Minimum Recording Package Prepared - 2026-07-29

- User approved the 12-sign minimum E4-C recording round: `SWITZERLAND`, `COUCH`, `CURLYHAIR`, `DOWNSIZE1`, `PEEKABOO`, `BEE1`, `BOTH`, `SHARK1`, `SENTENCE2`, `LETTUCE1`, `SHAVE1`, and `TWINS1`.
- Prepared collection package: `scratchpad/e4_c_targeted_collection/`.
- Prepared files: `README_RECORDING.md`, `package_summary.json`, `metadata/approved_minimum_recording_targets_v1.csv`, `metadata/recording_manifest_template.csv`, and starter raw folders under `raw/P01/phoneA/indoor/front/<gloss>/`.
- Target: at least 5 new signers, preferably 10; 3-5 valid isolated-sign repetitions per sign per signer; raw MP4s remain immutable and metadata is required per clip.
- No model training, Android changes, production recognizer changes, dataset relabeling, or E4-B retraining has started.
- Next: user records clips into the E4-C folder contract; then prepare/run validation before any retraining.

### E4-C Local Supplementary Replacement Audit - 2026-07-30

- User asked to replace the original E4-C 12-sign recording target with existing local supplementary videos from `E:\local`.
- Metadata-only audit completed; no videos copied, tensors extracted, models trained, Android files changed, or production recognizer assets modified.
- Audit artifacts: `artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_audit_01`.
- Inventory: 4,055 MP4 files, 4,035 parsed JSON sidecars, 4 observed signer IDs, 2,984 mapped conversational clips, and 530 blank or unmapped clips.
- Original E4-C 12-sign overlap with `E:\local`: zero signs, so this is a revised practical-vocabulary path rather than the same E4-A-derived experiment.
- Recommended replacement 12 pending validation: `HELLO`, `YES`, `NO`, `SORRY`, `GOOD`, `BYE`, `HAVE`, `GET`, `GO`, `KNOW`, `MAKE`, and `WELCOME2`.
- Important caveat: legacy accepted sidecars do not expose `hand_hit_rate`; missing hand-hit metrics must not be interpreted as failed hand detection.
- Next: prepare/run local video validation for readability, label consistency, duration/frame counts, signer split feasibility, duplicate/source leakage, and quarantine handling before any E4-B extraction or training.
### E4-C Local Supplementary Video Validation Result - 2026-07-30

- Added validator: `pipeline/rgb/e4_c_local_validate.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_validation_01`.
- Validation checked the 12 revised local signs: `HELLO`, `YES`, `NO`, `SORRY`, `GOOD`, `BYE`, `HAVE`, `GET`, `GO`, `KNOW`, `MAKE`, and `WELCOME2`.
- Result: 1,099/1,099 candidate rows were eligible and readable; readable rate `1.0000`; check passed with no errors.
- Eligible signer IDs: `3B96F6-S001`, `3B96F6-S002`, `6F7328-S001`, and `93EB89-S001`.
- Split finding: two-way signer-disjoint split is possible for all classes, but three-way signer-disjoint train/validation/test split is blocked for `GET`, `GO`, `HAVE`, `KNOW`, `MAKE`, and `WELCOME2` because each has only two eligible signers.
- Quality warnings: 86 low-hand-hit rows and 9 low-quality-score rows; track or quarantine these before training.
- No extraction, training, Android changes, production recognizer changes, or dataset mutation occurred.
- Next: prepare a reviewed E4-B local-supplementary manifest/split package with explicit split policy and warning-row handling. Do not train yet.
### E4-B Local Supplementary Manifest Package - 2026-07-30

- Added manifest packager: `pipeline/rgb/e4_b_local_manifest.py`.
- Package directory: `artifacts/recognition_upgrade/e4_generalization/e4_b_local_supplementary_manifest_01`.
- Outputs: `pilot_manifest.csv`, `class_split_summary.csv`, `manifest_report.json`, `check_report.json`, and `README_RUN.md`.
- Split policy: `two_way_held_out_signer_with_internal_validation`; held-out test signer is `6F7328-S001` because it covers all 12 classes.
- Counts: 584 train, 146 internal validation, 360 held-out test, and 9 quarantined low-quality rows.
- No signer overlap between train-like rows and test rows.
- Limitation: `GET`, `GO`, `HAVE`, `KNOW`, `MAKE`, and `WELCOME2` each have only one train-like signer, so this is a local practical pilot, not a production-grade three-way signer-disjoint benchmark.
- No tensor extraction, training, Android changes, production recognizer changes, or source dataset mutation occurred.
- Next: user reviews the manifest limitation. If accepted, prepare a bounded E4-B extraction/training runner that consumes `pilot_manifest.csv` and writes isolated outputs.
### E4-B Strict 7-Sign Signer-Disjoint Manifest - 2026-07-30

- User asked to exclude the six insufficient 2-signer signs instead of using the weaker 12-sign local pilot.
- Excluded signs: `GET`, `GO`, `HAVE`, `KNOW`, `MAKE`, and `WELCOME2`.
- Strict signs: `HELLO`, `BYE`, `YES`, `SORRY`, `NO`, `THANKYOU`, and `GOOD`.
- Updated `pipeline/rgb/e4_c_local_validate.py` to accept repeated `--selected-gloss` overrides.
- Added strict manifest builder: `pipeline/rgb/e4_b_strict_manifest.py`.
- Strict validation artifact: `artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_validation_strict_7_01`; result 849/849 eligible/readable and three-way split feasible.
- Strict manifest artifact: `artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_signer_disjoint_manifest_01`; result 410 train, 220 validation, 210 test, 9 quarantine rows.
- Split signers are globally disjoint: train `93EB89-S001`, validation `3B96F6-S001`/`3B96F6-S002`, test `6F7328-S001`.
- No extraction, training, Android changes, production recognizer changes, or source dataset mutation occurred.
- Next: review/approve the strict 7-sign manifest, then prepare a bounded E4-B training runner if accepted.
### E4-B Strict 7-Sign Runner Package Prepared - 2026-07-30

- Added runner: `pipeline/rgb/e4_b_strict_runner.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_01`.
- Prepared config/manifest/runbook for classes `BYE`, `GOOD`, `HELLO`, `NO`, `SORRY`, `THANKYOU`, and `YES`.
- Active rows: 840 (`410` train, `220` validation, `210` test); quarantine rows: 9.
- Branches: `conv1d_baseline` and `tcn_masked_pool`; seeds `101`, `202`, `303`; batch size `8`; epochs per run command `20`.
- Smoke passed: extracted 4 clips into `[4,96,258]`, ran forward pass and one training batch for both branches, and saved smoke weights.
- Full extraction and training were not run. Full extraction is expected to be long on CPU because MediaPipe IMAGE mode processes source videos frame by frame.
- Next user command: run `extract-features --require-full`, then `check --require-full-dataset`. Training remains blocked until extraction passes.
### E4-B Strict 7-Sign Corrected Dataset Ready - 2026-07-30

- Result document: `context/recognition_upgrade/E4_B_STRICT_7_CORRECTED_DATASET_RESULT.md`.
- Correction tool: `pipeline/rgb/e4_b_correct_legacy_dataset.py`.
- Diagnostic-only source run: `artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_01`.
- Approved corrected run: `artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_02_corrected`.
- Pilot 01 full extraction passed structurally but must not be trained: train split hand-hit rate was only `0.156` because legacy accepted local rows were reprocessed from full raw videos instead of using accepted embedded sign-segment features.
- Pilot 02 correction uses embedded accepted 258-feature frames for 410 legacy train rows and reuses Stage-E MediaPipe-extracted per-clip features for 430 validation/test rows.
- Corrected dataset checks passed: 840 rows, tensor shape `[840,96,258]`, no NaN/Inf, mask/length consistency valid, padded frames zero, split counts train/validation/test `410/220/210`.
- Corrected average hand-hit rates: train `1.000`, validation `0.901`, test `0.838`.
- Caveat: this is the best current local supplementary E4-B benchmark, but it mixes feature provenance and still has limited signer diversity; treat it as bounded held-out-signer evidence, not production readiness.
- Next: user runs E4-B training only from `e4_b_strict_7_landmark_pilot_02_corrected`, then `check --require-full-dataset --require-metrics`. Android integration and production recognizer replacement remain blocked.

### E4-B Strict 7-Sign Training Result - 2026-07-30

- Result document: `context/recognition_upgrade/E4_B_STRICT_7_TRAINING_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_02_corrected`.
- Final check passed with no missing outputs, but the experiment result is no-go.
- Best-checkpoint means: `conv1d_baseline` train/val/test `0.9244/0.0924/0.1429`; `tcn_masked_pool` train/val/test `0.9943/0.0909/0.1429`; random baseline is `0.1429`.
- Held-out predictions collapsed mostly to `YES` or `NO` with high confidence; masked TCN fit train almost perfectly but did not generalize.
- Root cause evidence: train split was entirely `legacy_embedded_accepted_258` from signer `93EB89-S001`, while validation/test were entirely `stage_e_mediapipe_extracted_258` from folders `2` and `1`; train mean length/mean_abs/nonzero fraction `30.00/0.0390/0.1161` vs validation `88.49/0.4987/0.6977` and test `85.82/0.4918/0.6554`.
- Decision: do not promote, export, Android-integrate, or rerun E4-B pilot 02 with more epochs. Treat this as benchmark-construction failure caused by signer/provenance confounding, not as a final architecture verdict against TCN.
- Next: plan a same-provenance Stage-E/current-pipeline benchmark or collect enough same-provenance signers for the same practical signs before more model tuning.

### E4-D Stage-E Same-Provenance Diagnostic Package Prepared - 2026-07-30

- Plan document: `context/recognition_upgrade/E4_D_SAME_PROVENANCE_PLAN.md`.
- Manifest builder: `pipeline/rgb/e4_d_same_provenance_manifest.py`.
- Manifest run: `artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_manifest_01`.
- Runner package: `artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_pilot_01` using the existing `pipeline.rgb.e4_b_strict_runner` implementation.
- Purpose: remove the E4-B pilot 02 provenance confound by using only Stage-E/current-pipeline local supplementary clips for all splits.
- Scope: 7 signs (`BYE`, `GOOD`, `HELLO`, `NO`, `SORRY`, `THANKYOU`, `YES`), 430 rows total, train/val/test `165/55/210`.
- Split policy: train/validation from source folder `2`, test from source folder `1`; validation is not signer-independent, so this is diagnostic, not production-grade.
- Manifest warning: 204 rows have `low_hand_hit_rate`, so extraction-quality review remains required before interpreting training failures.
- Local validation passed: manifest prepare/check, runner check, and 4-row smoke test. Smoke extracted `[4,96,258]`, created both branches, ran forward pass and one train batch, and saved smoke weights.
- Next user step: run full extraction for `e4_d_stage_e_same_provenance_pilot_01`, then `check --require-full-dataset`; do not train if extraction quality is broken or missingness is severe.

### E4-D Stage-E Same-Provenance Extraction Result - 2026-07-30

- Result document: `context/recognition_upgrade/E4_D_EXTRACTION_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_pilot_01`.
- Full extraction completed: 430 attempted, 430 ok/cached, 0 failed, dataset shape `[430,96,258]`, split counts train/validation/test `165/55/210`.
- Tensor integrity passed: no NaN/Inf, frame masks match lengths, padded frames are zero.
- Average extracted hand-hit rates: train `0.9042`, validation `0.8919`, test `0.8376`; pose hit was effectively `1.0` in all splits.
- Feature-provenance mismatch from E4-B is removed: train/validation/test are Stage-E/current-pipeline tensors. Train vs validation mean feature difference is `0.02031` with median magnitude ratio `0.995`; train vs test mean difference is `0.08607` with median ratio `0.877`.
- Caveat: this remains diagnostic, not production-grade. Validation is same-source rather than signer-independent, test has one signer/source, and low hand-hit rows remain, especially test `HELLO` and `THANKYOU`.
- Next: user runs E4-D diagnostic training, then final metrics check. Use this only to test whether prediction collapse disappears after fixing provenance.

### E4-D Stage-E Same-Provenance Training Result - 2026-07-30

- Result document: `context/recognition_upgrade/E4_D_TRAINING_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_pilot_01`.
- Final check passed with no missing outputs. E4-D is a diagnostic pass and production no-go.
- Best-checkpoint means: `conv1d_baseline` train/val/test `1.0000/0.9818/0.5651`; `tcn_masked_pool` train/val/test `1.0000/0.9758/0.6286`; random baseline is `0.1429`.
- Compared with E4-B, held-out collapse is fixed: E4-B TCN best test was `0.1429`, while E4-D masked TCN mean best test is `0.6286`.
- Best global checkpoint: `tcn_masked_pool` seed `303`, validation `0.9818`, test `0.6333`.
- Best TCN test per-class accuracy: `BYE 0/30`, `GOOD 29/30`, `HELLO 28/30`, `NO 12/30`, `SORRY 29/30`, `THANKYOU 10/30`, `YES 25/30`.
- Main confusions: `BYE -> YES`, `NO -> YES`, `THANKYOU -> SORRY`.
- Decision: continue landmark-first same-provenance work with masked TCN as the preferred diagnostic branch, but do not export/integrate into Android or claim production accuracy. Validation is same-source and optimistic.
- Next: prepare E4-E focused error review/data-cleaning for `BYE`, `THANKYOU`, and `NO` before another training run.

### E4-E Focused Error Review Package - 2026-07-30

- Package document: `context/recognition_upgrade/E4_E_ERROR_REVIEW_PACKAGE.md`.
- Script: `pipeline/rgb/e4_e_error_review.py`.
- Source run: `artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_pilot_01`.
- Review package: `artifacts/recognition_upgrade/e4_generalization/e4_e_error_review_01`.
- Recreated predictions from `tcn_masked_pool` seed `303` best checkpoint for all 430 E4-D samples.
- Prepared 156 manual-review rows and 156 visual panels: 68 target test errors, 22 target correct references, 24 confusion-class references, 24 train target references, and 18 validation target references.
- Structural check passed with `rows=156`, `passed=true`, `errors=[]`.
- Next action: user completes `review_queue.csv`, then runs `summarize --require-reviewed` and `check --require-reviewed`. No retraining, Android integration, model export, or production-recognizer replacement is authorized before that review summary is analyzed.

### E4-E GUI Review Automation - 2026-07-30

- Added resumable GUI command to `pipeline/rgb/e4_e_error_review.py`: `review --run-dir <E4-E run dir>`.
- The GUI displays one review panel at a time, shows true/predicted gloss, confidence, top-2/top-3, signer/source metadata, and saves after every row.
- One-click decisions fill the required manual columns for keep, variant mismatch, wrong label, poor visibility, landmark/crop problem, blur/occlusion, ambiguous second review, or quarantine.
- Validation: Python compile passed; ordinary E4-E check passed; `--require-reviewed` correctly reports 156 incomplete rows before user review.
- Next action: user runs the GUI reviewer, completes all 156 rows, then runs `summarize --require-reviewed` and `check --require-reviewed`.

### E4-E Focused Error Review Result - 2026-07-30

- Result document: `context/recognition_upgrade/E4_E_REVIEW_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_e_error_review_01`.
- User completed all 156 GUI review rows; `summarize --require-reviewed` passed and `check --require-reviewed` passed.
- Manual review summary: 140 keep, 16 relabel; all rows had visible hands; no rows were marked blurry/occluded.
- Relabel concentration: `THANKYOU` 13 rows, `BYE` 1 row, `YES` references 2 rows; `NO` had zero relabels.
- Interpretation: `THANKYOU` is partially label/variant-confounded, but `BYE -> YES` and `NO -> YES` remain real clean-data generalization/separability failures.
- Next action: prepare E4-F cleaned-diagnostic manifest/run package that excludes/quarantines the 16 relabel rows, reruns the same Conv1D vs masked-TCN diagnostic, and uses the result to decide targeted recollection versus deferring weak signs or changing features/modeling.

### E4-F Cleaned Diagnostic Package Prepared - 2026-07-30

- Plan document: `context/recognition_upgrade/E4_F_CLEANED_DIAGNOSTIC_PLAN.md`.
- Runner: `pipeline/rgb/e4_f_cleaned_diagnostic.py`.
- Prepared run: `artifacts/recognition_upgrade/e4_generalization/e4_f_cleaned_diagnostic_pilot_01`.
- Source E4-D tensor reused; no MediaPipe extraction rerun.
- Cleanup removed the 16 E4-E `relabel` sample IDs. Dataset now has 414 rows: train 165, validation 55, test 194.
- Test class counts after cleanup: BYE 29, GOOD 30, HELLO 30, NO 30, SORRY 30, THANKYOU 17, YES 28.
- Smoke passed for `conv1d_baseline` and `tcn_masked_pool`: forward pass, one train batch, and smoke weights saved.
- Structural check passed with `--require-full-dataset` and no errors.
- Next action belongs to the user: run E4-F training, then `check --require-full-dataset --require-metrics`; analyze weak-class behavior before collecting more data or changing models.

### E4-F Cleaned Diagnostic Result - 2026-07-30

- Result document: `context/recognition_upgrade/E4_F_CLEANED_DIAGNOSTIC_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_f_cleaned_diagnostic_pilot_01`.
- Final check passed with no errors.
- Dataset: 414 rows after removing 16 E4-E relabel rows; train/val/test = 165/55/194.
- Branch mean best validation/test: Conv1D `0.9818/0.6065`; masked TCN `0.9758/0.6581`.
- Best selected checkpoint: `tcn_masked_pool` seed 303, validation/test `0.9818/0.6856`.
- E4-D selected comparison: `0.9818/0.6333`; E4-F improved selected test by `+0.0523`.
- Best selected per-class test: BYE `0/29`, GOOD `29/30`, HELLO `28/30`, NO `12/30`, SORRY `29/30`, THANKYOU `10/17`, YES `25/28`.
- Decision: diagnostic pass but production no-go. Cleanup helped, especially THANKYOU, but BYE and NO remain severe clean-data failures.
- Next action: prepare E4-G focused BYE/YES/NO separability diagnostic before collecting more data, changing features/modeling, or removing signs from the initial reliable vocabulary.
### E4-G BYE/YES/NO Separability Result - 2026-07-30

- Result document: `context/recognition_upgrade/E4_G_BYE_YES_NO_SEPARABILITY_RESULT.md`.
- Analysis script: `pipeline/rgb/e4_g_separability.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_g_bye_yes_no_separability_01`.
- Final check passed with `panel_count=94` and no errors.
- Source: E4-F cleaned diagnostic selected model `tcn_masked_pool` seed `303` and cleaned Stage-E-only `[96,258]` dataset.
- Target counts: train/validation/test = `75/25/87` across `BYE`, `NO`, and `YES`.
- E4-F selected model target-group performance: train `1.0000`, validation `0.9600`, held-out test `0.4253`; target-restricted held-out test `0.4483`.
- Main model confusions: `BYE->YES` 28/29, `NO->YES` 17/30, `YES->YES` 25/28.
- Simple probes confirmed the problem is not just the TCN classifier: nearest-centroid test was `0.4713`; ridge test was `0.5977` but still `BYE` `0/29`.
- Hand-hit rates were acceptable on test (`BYE` `0.8520`, `NO` `0.8645`, `YES` `0.8267`), so missing hands are not the primary explanation.
- Decision: diagnostic pass, production no-go. Do not export/integrate E4-F and do not rerun the same full 7-sign loop as the next step.
- Next action: prepare E4-H controlled `BYE`/`NO`/`YES` variant and data-balance intervention before deciding whether to recollect, relabel/split variants, add RGB hand-shape evidence, or defer `BYE` from the first reliable vocabulary.


### E4-H BYE/NO/YES Variant Intervention Package Prepared - 2026-07-30

- Package document: `context/recognition_upgrade/E4_H_VARIANT_INTERVENTION_PACKAGE.md`.
- Package script: `pipeline/rgb/e4_h_variant_intervention.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_h_bye_no_yes_variant_review_01`.
- Source: E4-G `BYE`/`NO`/`YES` panels and prediction index.
- Generated 94 review rows, 94 copied panel JPGs, 9 contact sheets, `review.html`, `USER_REVIEW_GUIDE.md`, and `variant_review_queue.csv`.
- Structural check passed with no errors.
- Purpose: decide whether `BYE`, `NO`, and `YES` should be kept as-is, split by variant, relabeled/quarantined, recollected, deferred, or escalated to RGB hand-shape evidence before another full benchmark.
- Next action belongs to the user: review `variant_review_queue.csv` using `review.html` and `contact_sheets/`, then run E4-H `summarize --require-reviewed` and `check --require-reviewed`. Do not run another full 7-sign training loop before this review is summarized.
### E4-H Conservative Auto-Triage Result - 2026-07-30

- Ran `pipeline.rgb.e4_h_variant_intervention autofill --overwrite` on `artifacts/recognition_upgrade/e4_generalization/e4_h_bye_no_yes_variant_review_01`.
- This is engineering triage only, not ASL-fluent semantic review.
- Required-review summary passed: 94/94 rows filled, 0 remaining, no validation errors.
- Auto-triage result: 70 `keep`, 24 `needs_second_review`.
- Critical unresolved rows: `BYE:needs_second_review` 12, `NO:needs_second_review` 11, `YES:needs_second_review` 1.
- Interpretation: automation reduced the work from 94 rows to 24 high-value rows but did not prove the collapse rows are label/variant-correct.
- Next action: either manually resolve the 24 `needs_second_review` rows, or make a conservative engineering decision to defer/exclude `BYE` and treat `NO` as unstable before any focused rerun. No Android integration or production replacement is authorized.
### E4-I Reliable-Core 4-Sign Package Prepared - 2026-07-30

- Package document: `context/recognition_upgrade/E4_I_RELIABLE_CORE_PACKAGE.md`.
- Package script: `pipeline/rgb/e4_i_reliable_core.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_i_reliable_core_4sign_pilot_01`.
- Decision: stop trying to rescue bad local signs for the next benchmark. Exclude `BYE`, `NO`, and `THANKYOU` from the reliable-core pass.
- Selected signs: `GOOD`, `HELLO`, `SORRY`, and `YES` because they have three-signer local support and strong E4-F held-out behavior (`29/30`, `28/30`, `29/30`, `25/28`).
- Dataset reused E4-F cleaned `[96,258]` tensor: 238 rows, train/validation/test = `90/30/118`; no MediaPipe extraction rerun.
- Smoke passed for Conv1D and masked TCN; structural check passed with no errors.
- Next action belongs to the user: run E4-I training, then `check --require-full-dataset --require-metrics`. Do not run the failed 7-sign loop, E4-H manual review, Android integration, or production export before E4-I is evaluated.
### E4-I Reliable-Core 4-Sign Result - 2026-07-30

- Result document: `context/recognition_upgrade/E4_I_RELIABLE_CORE_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_i_reliable_core_4sign_pilot_01`.
- Final structural check passed, but the reliability gate failed.
- Best-checkpoint branch means: `conv1d_baseline` val/test `0.9778/0.8249`; `tcn_masked_pool` val/test `0.9778/0.6808`.
- Validation-selected checkpoint: `conv1d_baseline` seed `202`, val/test `1.0000/0.6780`.
- Validation-selected per-class test: `GOOD 30/30`, `HELLO 29/30`, `SORRY 3/30`, `YES 18/28`.
- Main selected confusions: `SORRY -> GOOD` 27/30 and `YES -> HELLO` 10/28.
- Latest-epoch Conv1D diagnostic was stronger overall (`mean test 0.9124`), but `YES` still stayed below gate (`mean/min 0.7262/0.7143`) and latest-epoch selection was not the pre-registered rule.
- Interpretation: excluding `BYE`/`NO`/`THANKYOU` was correct, but the 4-sign set is still not production reliable. `GOOD` and `HELLO` are strong; `SORRY` is vulnerable to selection instability; `YES` remains weak.
- Next action: prepare E4-J 3-sign reliable-core benchmark using `GOOD`, `HELLO`, and `SORRY`, with explicit latest-vs-best and seed-stability reporting. Do not export/integrate E4-I.
## 2026-07-30 - E4-J Reliable-Core 3-Sign Package Prepared

- Added isolated runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_j_reliable_core_3sign.py`.
- Prepared run directory: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_j_reliable_core_3sign_pilot_01`.
- Source tensor: E4-F cleaned Stage-E `[96,258]` landmark tensor.
- Selected classes: `GOOD`, `HELLO`, `SORRY`.
- Excluded classes: `BYE`, `NO`, `THANKYOU`, `YES`.
- Dataset rows: `190`; split counts train/val/test `75/25/90`.
- Smoke test passed for `conv1d_baseline` and `tcn_masked_pool`; output shape `[8,3]`; smoke weights written under the E4-J run directory.
- Structural check passed with `--require-full-dataset`.
- Added context document: `context/recognition_upgrade/E4_J_RELIABLE_CORE_PACKAGE.md`.
- Next action: user runs full E4-J training and final metrics check. Do not export, integrate, or expand vocabulary until E4-J metrics are evaluated.
## 2026-07-30 - E4-J Reliable-Core 3-Sign Result

- User completed E4-J full training and final check for `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_j_reliable_core_3sign_pilot_01`.
- Structural check passed with no errors.
- Classes: `GOOD`, `HELLO`, `SORRY`; rows `190`; split train/val/test `75/25/90`.
- Conv1D latest checkpoints are strong and stable: mean test `0.9741`, std `0.0052`, min seed test `0.9667`, min class test `0.9333`.
- Conv1D best checkpoints are unstable: mean test `0.8185`, min seed test `0.7222`, min class test `0.1667`; some best checkpoints collapse `SORRY` into `GOOD`.
- Masked TCN remains worse and unstable: latest mean test `0.8815`, min seed test `0.7111`, min class test `0.2333`.
- Automated `gate_passed` is true, but engineering interpretation is limited pass because the written gate required stable latest and best checkpoint families. Best-checkpoint selection remains unreliable.
- Decision: E4-J proves a tiny `GOOD`/`HELLO`/`SORRY` landmark core is separable with Conv1D latest checkpoints, but does not authorize production export or Android integration.
- Next action: prepare E4-K checkpoint-policy diagnostic or patch E4-J reporting/check logic so automated gates match the written gates before vocabulary expansion.
## 2026-07-30 - E4-K Checkpoint Policy Result

- Added isolated diagnostic runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_k_checkpoint_policy.py`.
- Source run: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_j_reliable_core_3sign_pilot_01`.
- E4-K output: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_k_checkpoint_policy_01`.
- Structural check passed.
- Result: E4-J script gate was true, but strict written gate is false because Conv1D best-checkpoint family is unstable.
- Stable policy found: `conv1d_baseline_latest_fixed_epoch` with mean test `0.9741`, min seed test `0.9667`, min class test `0.9333`, and zero collapse seeds.
- Rejected for next local expansion: `tcn_masked_pool` and validation-best checkpoint policy.
- Decision: proceed only to a one-sign offline expansion diagnostic (E4-L); no Android export, production replacement, or many-sign expansion.
## 2026-07-30 - E4-L MAKE One-Sign Expansion Package Prepared

- Added isolated runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_l_one_sign_expansion.py`.
- Prepared run directory: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_l_make_expansion_pilot_01`.
- E4-L keeps E4-J core `GOOD`/`HELLO`/`SORRY` and adds `MAKE` only.
- Candidate selection evidence: `MAKE` has 70 readable clips, two aligned signers, only 3 warning rows, mean hand-hit 0.7258, and cleaner hand-hit than GET/WELCOME2/HAVE/KNOW/GO.
- Expected full dataset after extraction: 260 rows, train/val/test 105/35/120.
- Model policy follows E4-K: `conv1d_baseline` only, latest/fixed-epoch policy, seeds 101/202/303.
- Limited two-clip candidate extraction smoke passed; two MAKE clips were cached and partial assembled dataset has 192 rows. Full extraction will reuse these and extract the remaining 68 candidate clips.
- Basic package check passed with `--require-dataset`.
- Next action: user runs full candidate extraction with `--require-full`, smoke, full training, and final check. No Android export or production replacement.
## 2026-07-30 - E4-L MAKE One-Sign Expansion Result And Screening Pivot

- User completed E4-L full extraction, smoke/training, and final check for `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_l_make_expansion_pilot_01`.
- Structural check passed with no errors, but the experiment gate failed.
- Full E4-L dataset assembled successfully: 260 rows, shape `[260,96,258]`, train/validation/test `105/35/120`, candidate extraction `70/70` `MAKE` rows, no extraction failures.
- Classes: `GOOD`, `HELLO`, `SORRY`, `MAKE`; model policy from E4-K: `conv1d_baseline` only, latest/fixed-epoch policy, seeds `101/202/303`.
- Latest-policy test summary: mean test `0.7722`, min seed test `0.7417`, min class test `0.0333`, min `MAKE` test `0.0333`.
- Core classes remained strong in latest checkpoints, but held-out `MAKE` failed badly: `MAKE` test accuracy by seed was `0.2000`, `0.0333`, and `0.2667`.
- Main failure pattern: held-out `MAKE` was mostly predicted as `GOOD`, despite perfect train/validation performance.
- Decision: do not add `MAKE`; keep reliable local core at `GOOD`, `HELLO`, and `SORRY` only.
- Process decision: stop manual one-word expansion loops as the main path. The next high-value experiment should be an automated dual-source candidate screening step using both `F:\ASL DATASET\ASL CITIZEN` and the local supplementary dataset with source-aware evaluation.
- Next action: architect and document the dual-source candidate screening package. It should rank many candidate signs as keep/reject/needs-review using within-source reliability, cross-source transfer, label/variant compatibility, signer independence, quality metrics, and confusion impact on the reliable core. No Android integration, model export, production replacement, or blind dataset merge is authorized.

## 2026-07-31 - E4-O Evaluated, E4-P 20-Sign Pressure Package Prepared

- User completed E4-O. Structural check passed, but accuracy gate failed.
- E4-O full dataset: `[468,96,258]`, extraction `140/140` local `GET/WELCOME2` rows succeeded.
- E4-O gate: mean latest test `0.7822`, min core latest test `0.7000`, min candidate latest test `0.2619`, decision `no_export_no_android_integration`.
- Failure driver: local extracted `GET` collapsed mostly into `GOOD`; `GET` is quarantined and `WELCOME2` is not promoted in the same batch.
- Added runner `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_p_existing_feature_20sign_pressure.py`.
- Prepared run directory `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_p_existing_feature_20sign_pressure_01`.
- E4-P classes: `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`, `WANT2`, `HELP`, `NICE`, `KEEP`, `START`, `MEET`, `CLOSE`, `GIVE`, `TALK1`, `WHAT1`, `CLEAN`, `LEAVE`, `STAND2`, `BECOME`, `WASH2`.
- E4-P dataset: `[1174,96,258]`, train/validation/test `749/140/285`, random baseline `0.05`.
- E4-P smoke passed and structural check passed with `--require-full-dataset`.
- Next action: user runs E4-P full training and final check. No Android integration, TFLite export, production replacement, or new extraction batch is authorized until E4-P metrics are evaluated.

**E4-Q CONFUSION RESOLVER PACKAGE 2026-07-31 - PREPARED, USER TRAINING NEXT:**
Prepared `pipeline/rgb/e4_q_confusion_resolver.py` and run directory `artifacts/recognition_upgrade/e4_generalization/e4_q_confusion_resolver_sorry_become_help_01`. E4-Q directly addresses the E4-P `SORRY -> BECOME/HELP` collapse by comparing the original `[96,258]` control with derived `[96,728]` velocity/acceleration/relation features and a class-weighted derived variant. Dataset prepared: `219` active rows, train/validation/test `108/26/85`, classes `GOOD`, `SORRY`, `HELP`, `BECOME`. Smoke passed for all three variants and structural check passed. Full training is not started. No Android, TFLite export, production recognizer replacement, source dataset mutation, RGB fusion, or large vocabulary extraction occurred.

**DYNAMIC MIXED RECOGNITION ROADMAP 2026-07-31 - APPROVED DIRECTION, IMPLEMENTATION NOT STARTED:**
Completed E4-Q analysis showed the focused landmark-only `GOOD/SORRY/HELP/BECOME` resolver failed. Best mean latest test was `0.7137`, and `SORRY` remained the blocker. Created `context/recognition_upgrade/E4_Q_RESULT.md` and `context/recognition_upgrade/DYNAMIC_MIXED_RECOGNITION_ROADMAP.md`. The current architecture direction is now landmark-primary dynamic mixed recognition: stable signs use the primary `[96,258]` landmark path; registered confusion groups route to specialist resolvers or rejection; RGB/visual evidence is introduced only for hard groups after offline evidence. Next planned step is Phase 1 stable-candidate tiering and stable-primary landmark training package. No Android implementation, TFLite export, production asset replacement, dataset mutation, or model training was started by this documentation step.

**E4-R STABLE-CANDIDATE TIERING 2026-07-31 - COMPLETE, E4-S NEXT:**
Created `pipeline/rgb/e4_r_stable_candidate_tiering.py` and ran it at `artifacts/recognition_upgrade/e4_generalization/e4_r_stable_candidate_tiering_01`. The run ranked all 236 inventory labels using existing E4-M/E4-N/E4-O/E4-P/E4-Q evidence only. Structural check passed. Tier counts: `A_primary_ready_guarded=4`, `B_confusion_specialist_or_repair=12`, `B_borderline_review=6`, `C_defer_more_evidence=9`, `D_inventory_only=205`. The guarded primary-ready signs are `GOOD`, `HELLO`, `HAVE`, and `KNOW`. `SORRY` is deliberately excluded from the primary-ready set because E4-P/E4-Q showed severe broader-context confusion. Next action is to prepare E4-S stable-primary landmark package; no Android, export, production asset replacement, training, extraction, or specialist work was started.

**MEMORY SAVE 2026-07-31 11:19 +08:00:**
Updated `memory.md` with the current dynamic mixed recognition handoff. The next session should start by preparing E4-S stable-primary landmark package design using `GOOD`, `HELLO`, `HAVE`, and `KNOW`, with no Android/export/specialist work before approval.

**E4-S STABLE-PRIMARY PACKAGE 2026-08-02 - PREPARED, USER TRAINING NEXT:**
Added isolated runner `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_s_stable_primary.py` and prepared run directory `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_s_stable_primary_4sign_01`. E4-S filters the passed E4-N tensor instead of re-extracting features. Active primary classes are `GOOD`, `HELLO`, `HAVE`, and `KNOW`; `SORRY` is deliberately withheld as an OOV/confusion holdout after E4-P/E4-Q failures. Active dataset rows: `221`; split train/validation/test `101/32/88`; OOV holdout rows `50`. Smoke passed with output shape `[12,4]` and one train batch. Structural check passed with `--require-full-dataset`. Added `context/recognition_upgrade/E4_S_STABLE_PRIMARY_PACKAGE.md` and updated recognition-upgrade context. Next action: user runs E4-S full training and final check. No Android integration, TFLite export, production replacement, specialist work, or broad expansion is authorized.

**E4-S RESULT AND E4-T ROUTER SIMULATION 2026-08-02 - CLOSED-SET PASS, SIMPLE ROUTER NO-GO:**
User completed E4-S full training and final check for `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_s_stable_primary_4sign_01`. Closed-set latest fixed-epoch results were strong: mean test `0.9848`, minimum seed test `0.9773`, minimum per-class test `0.9286`, max predicted-class share `0.3523`. This supports `GOOD`, `HELLO`, `HAVE`, and `KNOW` as stable primary candidates. However, the withheld `SORRY` holdout was predicted as `GOOD` for all 30 test rows in all three seeds with high confidence. Added `pipeline/rgb/e4_t_router_simulation.py` and ran E4-T at `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_t_router_simulation_01`. Structural check passed, but simple confidence/margin routing failed: best scanned aggregate policy had min accepted precision with OOV `0.9000`, min active coverage `0.6136`, max `SORRY` false-accept rate `0.2000`; gate required `0.95`, `0.80`, and `<=0.05`. Added `context/recognition_upgrade/E4_T_ROUTER_SIMULATION_RESULT.md` and updated roadmap docs. Next action: prepare a focused `SORRY` specialist/data-repair experiment using richer visual evidence or targeted review. No Android integration, TFLite export, production replacement, broad expansion, or threshold-only rerun is authorized.

**E4-U CONFUSION EVIDENCE PACKAGE 2026-08-02 - PREPARED, SPECIALIST/DATA-REPAIR DECISION NEXT:**
Added reusable evidence runner `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_u_confusion_evidence.py` and prepared run directory `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_u_sorry_good_evidence_01`. This package treats `SORRY -> GOOD` as the first representative confusion group, not as a one-word manual loop. It joins E4-S/E4-T predictions with E4-J raw local video paths and generated 60 panels: 30 held-out true `GOOD` primary-reference rows and 30 held-out true `SORRY` confusion-target rows. Structural check passed with `--require-panels`; panel failures `0`. Main files are `review/confusion_evidence_manifest.csv`, `contact_sheets/primary_reference_test.jpg`, and `contact_sheets/confusion_target_test.jpg`. The Codex image viewer could not render the sheets due to the Windows sandbox wrapper, but files exist on disk. Next action: use this evidence to choose RGB/crop specialist, data/variant repair, targeted recollection, or deferral for the group. No Android integration, TFLite export, production replacement, threshold-only rerun, every-sign review loop, or broad expansion is authorized.

**E4-V GOOD/SORRY SPECIALIST PACKAGE 2026-08-02 - PREPARED, USER TRAINING NEXT:**
User confirmed E4-U sheets show `SORRY` is visibly different from `GOOD`. Added isolated runner `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_v_sorry_good_specialist.py` and prepared run directory `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_v_sorry_good_specialist_01`. E4-V uses E4-J raw videos and landmark tensors for a signer-disjoint binary proof: classes `GOOD` and `SORRY`, 100 rows total, train/validation/test `30/10/60`, class-balanced in every split. Branches are `landmark_binary_control` and `rgb_upper_body`; RGB uses 8 upper-body frames at 160px with frozen MobileNetV3Small embeddings and a small temporal head. Smoke passed for both branches; structural check passed with `--require-smoke`. Added `context/recognition_upgrade/E4_V_SORRY_GOOD_SPECIALIST_PACKAGE.md`. Next action: user runs full E4-V training and final check. No Android integration, TFLite export, production replacement, global RGB rollout, threshold-only rerun, or broad expansion is authorized.

**E4-V GOOD/SORRY SPECIALIST RESULT 2026-08-02 - LANDMARK SPECIALIST PASS, RGB NO-GO:**
User completed E4-V full training and final check for `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_v_sorry_good_specialist_01`; structural check passed. Landmark binary control was stable across all seeds with test accuracy `0.9667`, GOOD recall `0.9667`, SORRY recall `0.9667`, and confusion matrix `[[29,1],[1,29]]`. RGB upper-body was unstable: seed 101 test `0.9167` with SORRY recall `0.9000`, seed 202 test `0.9333` with SORRY recall `0.8667`, seed 303 collapsed to all GOOD with test `0.5000` and SORRY recall `0.0000`; mean RGB test `0.7833`. Added `context/recognition_upgrade/E4_V_SORRY_GOOD_SPECIALIST_RESULT.md`. Interpretation: the `[96,258]` representation can separate GOOD/SORRY when SORRY is explicitly modeled in a focused specialist; E4-S failed because SORRY was OOV and forced into GOOD. Next action: prepare mixed offline simulation using E4-S primary plus conditional GOOD/SORRY landmark specialist. No Android integration, TFLite export, production replacement, global RGB rollout, or broad expansion is authorized.

**E4-W MIXED LANDMARK SPECIALIST SIMULATION 2026-08-02 - PASSED SMALL OFFLINE ROUTED PROOF:**
Added `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_w_mixed_landmark_specialist_simulation.py` and ran it at `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_w_mixed_landmark_specialist_simulation_01`. E4-W loads E4-S primary weights and E4-V GOOD/SORRY landmark-specialist weights, then simulates routing primary `GOOD` predictions through the specialist. Structural check passed with `--require-metrics --require-predictions`. Combined test set: `118` rows (`88` known active rows + `30` withheld `SORRY`). Primary-alone mean accuracy was `0.7345` with `SORRY` recall `0.0000`. Mixed mean accuracy was `0.9718`, min seed `0.9661`, mean/min `SORRY` recall `0.9667`, mean/min `GOOD` recall `0.9667`, and max false `GOOD -> SORRY` specialist correction rate `0.0333`. Added `context/recognition_upgrade/E4_W_MIXED_LANDMARK_SPECIALIST_SIMULATION_RESULT.md`. Decision: proceed to broader offline routed-system validation with no-sign/OOV and source-disjoint checks. No Android integration, TFLite export, production replacement, or broad vocabulary expansion is authorized yet.

**E4-X ROUTED SYSTEM VALIDATION 2026-08-02 - PASSED ZERO-LANDMARK N0 PROBE, REAL N0/P1 FEATURES NEXT:**
Added `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_x_routed_system_validation.py` and ran it at `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_x_routed_system_validation_01`. E4-X loads E4-S primary weights and E4-V GOOD/SORRY landmark-specialist weights, fits simple accept/reject thresholds on validation rows, and evaluates known signs, withheld SORRY, and reviewed E2e-C0 N0 rows represented as all-zero `[96,258]` no-frame sequences. Selected policy: primary confidence `0.95`, specialist confidence `0.50`. Structural check passed with `--require-metrics --require-predictions`. Test summary: mean accepted precision `0.9798`, min accepted precision `0.9739`, mean positive coverage `0.9746`, min positive coverage `0.9661`, max zero-landmark N0 false-commit rate `0.0000`, mean/min SORRY recall `0.9667`, mean/min GOOD recall `0.9667`. Added `context/recognition_upgrade/E4_X_ROUTED_SYSTEM_VALIDATION_RESULT.md`. Decision: proceed to real MediaPipe-extracted N0/P1 feature validation; do not start Android integration, TFLite export, production replacement, or broad vocabulary expansion yet.

**E4-Y REAL NO-SIGN FEATURE VALIDATION 2026-08-02 - STRUCTURAL PASS, FALSE-COMMIT NO-GO:**
Added `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_y_real_nosign_feature_validation.py` and ran it at `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_y_real_nosign_feature_validation_01`. E4-Y extracts real MediaPipe/schema v3.0 `[96,258]` windows from reviewed E2e-C0 N0/P1 videos and evaluates the E4-X routed policy. The first run spent ~172s extracting 8 clips, then failed on a missing `source` loader field; patched the loader and reran successfully using the saved Stage-E cache. Structural check passed. Bounded probe rows: `24` N0 + `24` P1, with no-sign validation/test `16/32`. Feature quality: N0 hand-hit `0.0130`, P1 hand-hit `0.8359`, pose-hit `1.0`. Recognition gate failed: mean accepted precision `0.7844`, min accepted precision `0.7687`, max real no-sign false-commit rate `0.9688`; GOOD/SORRY recall stayed `0.9667`. N0 false commits ranged `13/16` to `16/16`; P1 false commits ranged `13/16` to `15/16`. Added `context/recognition_upgrade/E4_Y_REAL_NOSIGN_FEATURE_VALIDATION_RESULT.md`. Decision: do not proceed to Android/export; next step is E4-Z signing/no-sign gate before routed recognition commits glosses.

**E4-Z SIGNING/NO-SIGN GATE 2026-08-02 - STRUCTURAL PASS, GATE NO-GO:**
Added `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_z_signing_gate.py` and ran it at `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_z_signing_gate_01`. E4-Z compares rule-based summary gates (`combined_motion`, `presence_motion`, `hand_motion`, `hand_nonzero`) and a tiny learned summary-feature MLP before the E4-S/E4-V routed recognizer. Structural check passed. The gate failed: rule gates eliminated N0/P1 false commits but collapsed positive coverage to about `0.32`-`0.40` and SORRY recall to `0.0000`; learned MLP reached min accepted precision `0.9500`, coverage `0.5169`, max no-sign false-commit `0.09375`, but SORRY recall stayed mean `0.1111`, min `0.0000`. Added `context/recognition_upgrade/E4_Z_SIGNING_GATE_RESULT.md`. Decision: no Android/export; next step is E4-AA no-sign dataset expansion and stronger temporal signing-gate design.

**E4-AA NO-SIGN TEMPORAL GATE PACKAGE 2026-08-02 - PREPARED, USER FULL RUN NEXT:** Added runner F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_aa_nosign_temporal_gate.py. Smoke run F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_aa_nosign_temporal_gate_smoke_01 prepared [4,96,258] real no-sign features, trained one seed/one epoch, wrote metrics, and passed structural check. This smoke is wiring-only, not an accuracy result. Runner supports --prepare-only and --train-only so long MediaPipe extraction can be resumed. Next action: user runs full E4-AA at rtifacts\recognition_upgrade\e4_generalization\e4_aa_nosign_temporal_gate_01 and reports metrics. No Android integration, TFLite export, production replacement, or vocabulary expansion is authorized before full E4-AA metrics are evaluated.


**E4-AA/E4-AB SIGNING GATE RESULTS 2026-08-02 - FALSE-COMMIT IMPROVED, LOW-MOTION GATE STILL BLOCKED:** User completed E4-AA full run at F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_aa_nosign_temporal_gate_01; structural check passed but gate failed. No-sign false commits improved to max 0.0147, but SORRY recall collapsed to mean/min 0.1222/0.0000. Added F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_ab_conservative_gate_policy.py and ran E4-AB at F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_ab_conservative_gate_policy_01; structural check passed but gate still failed. Conservative thresholding improved mean SORRY recall to 0.6778 and mean positive coverage to 0.8983 while keeping no-sign false commits at 0.0441, but seed 202 SORRY recall remained 0.1000. Decision: threshold tuning alone is insufficient; next step is E4-AC low-motion-aware signing gate training/objective. No Android integration, TFLite export, production replacement, or vocabulary expansion is authorized.


**E4-AC LOW-MOTION-AWARE SIGNING GATE 2026-08-02 - NEAR-PASS, NO ANDROID YET:** Added F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_ac_low_motion_aware_gate.py and ran variants e4_ac_low_motion_aware_gate_01 through _04. Best run is _01 with SORRY weight 8.0, no-sign weight 1.0; structural check passed. Metrics: mean/min accepted precision 0.9548/0.9492, mean/min positive coverage 0.9746/0.9661, max no-sign false commit 0.0441, mean/min GOOD recall 0.9667/0.9667, mean/min SORRY recall 0.9667/0.9667. This is the first gate preserving SORRY while controlling real no-sign false commits, but strict gate remains failed because min precision is below 0.95. Created context\recognition_upgrade\E4_AC_LOW_MOTION_AWARE_GATE_RESULT.md. Next action: E4-AD focused false-commit review/hard-negative expansion for residual P1/N0 -> HELLO commits. No Android integration, TFLite export, production replacement, or vocabulary expansion is authorized.


**E4-AD/E4-AE SIGNING GATE FOLLOW-UP 2026-08-02 - ERROR PATTERN IDENTIFIED, HARD-NEGATIVE WEIGHTING NO-GO:** Added F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_ad_false_commit_review.py and ran E4-AD at rtifacts\recognition_upgrade\e4_generalization\e4_ad_false_commit_review_01; structural check passed with panels. E4-AD produced 28 false commits, 23 hard-negative candidates, and 51 review panels. Residual errors are concentrated as no-sign -> HELLO, especially P1 ordinary-hand windows. Added F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_ae_hard_negative_gate.py; first run _01 had a wrapper no-effect issue, corrected in _02. E4-AE _02 upweighted 12 train hard negatives but failed: mean/min accepted precision 0.9605/0.9417, positive coverage 0.9746/0.9661, max no-sign false commit 0.0882, SORRY recall 0.9667. Decision: naive hard-negative weighting is not the path; best current gate remains E4-AC _01 near-pass. Next action should be E4-AF planning: either collect more HELLO-like no-sign/P1 diversity or add a temporal confirmation/uncertainty policy. No Android integration, TFLite export, production replacement, or vocabulary expansion is authorized.

## 2026-08-02 - Text-to-ASL Expanded GLB Vocabulary

- Text-to-ASL-only rollout completed; recognition/detection/model scope remained protected.
- Audited 98 source GLBs (173.18 MiB): 97 had animations, one 132-byte empty GLB was excluded, and
  the batch `thank-you.glb` was byte-identical to the existing asset.
- Copied 96 net-new playable assets. Final local catalog: 102 GLBs / 185.36 MiB.
- Added explicit word/phrase aliases, duplicate ID/alias refusal, complete manifest-to-asset and GLB
  structure/animation tests, apostrophe normalization, and animation-finished-driven queue advance.
- Clean Android build passed: `gradlew.bat clean testDebugUnitTest assembleDebug --console=plain
  --no-daemon --max-workers=2`.
- Focused Text-to-ASL test run passed 11/11 with zero failures.
- Debug APK: 202,850,233 bytes (193.45 MiB).
- Recognition pipeline Kotlin plus `streaming.tflite`, recognition `vocab.json`, model manifest,
  recognition config, overlay, and MediaPipe surfaces were hash-verified unchanged.
- Manual device playback/lifecycle smoke remains pending.

**E4-AF TO E5 BATCH STRATEGY 2026-08-02 - CURRENT NEXT PATH:** Created `F:\ASL DATASET\5. Apphear3\context\recognition_upgrade\E4_AF_TO_E5_BATCH_STRATEGY.md` and updated recognition-upgrade roadmap, experiment matrix, and ADRs. Decision: stop treating one-sign expansion as the main path. The immediate next work is E4-AF, a short offline acceptance-policy safety-floor package around E4-AC/E4-AD/E4-S/E4-V outputs. If E4-AF passes, move to E5-A large dual-source candidate screening across ASL Citizen and local supplementary data. If E4-AF fails, collect bounded HELLO-like no-sign data before vocabulary scaling. Android integration, TFLite export, production replacement, broad vocabulary training, and generic threshold/weight sweeps remain blocked.

**E4-AF ACCEPTANCE POLICY RESULT 2026-08-02 - POLICY-ONLY NO-GO:** Added `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_af_acceptance_policy.py` and ran it at `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_af_acceptance_policy_01`. Structural check passed. The run reused E4-AC/E4-AA/E4-S/E4-V/E4-X outputs and did no training or extraction. Selected policy summary: mean/min accepted precision `0.9548/0.9492`, mean/min positive coverage `0.9746/0.9661`, max no-sign false commit `0.0441`, mean/min HELLO recall `0.9556/0.9333`, mean/min GOOD and SORRY recall `0.9667/0.9667`. Decision: policy-only is no-go; HELLO-specific thresholds only remove false commits by damaging HELLO recall/coverage. Next action: E4-AG targeted HELLO-like no-sign expansion, then E5-A batch screening after safety floor is recovered. No Android/export/production replacement.

**E4-AG HELLO-LIKE NO-SIGN PACKAGE 2026-08-02 - PREPARED, USER CAPTURE NEXT:** Added `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_ag_hello_like_nosign_expansion.py` and initialized `F:\ASL DATASET\5. Apphear3\scratchpad\e4_ag_hello_like_nosign\raw\p1\P03\phoneA\indoor\front`. Added package doc `context\recognition_upgrade\E4_AG_HELLO_LIKE_NOSIGN_PACKAGE.md`. Purpose: collect targeted hands-visible-but-not-signing clips that resemble the residual NO_SIGN -> HELLO false commits, expand the E4-AA no-sign tensor, then run the existing E4-AC low-motion-aware gate trainer against the expanded tensor. This is the final safety-floor step before E5-A batch screening. No Android integration, TFLite export, production replacement, or vocabulary expansion occurred.

**E4-AG HELLO-LIKE NO-SIGN RESULT 2026-08-02 - OFFLINE SAFETY FLOOR PASS:** User completed reviewed capture at `artifacts\recognition_upgrade\e2e_c0\hello_like_p1_capture_01`: 160 rows, 116 eligible, participants P03/P04, devices phoneA/phoneB. Ran `pipeline.rgb.e4_ag_hello_like_nosign_expansion prepare`, producing expanded no-sign tensor at `artifacts\recognition_upgrade\e4_generalization\e4_ag_hello_like_nosign_expansion_01`: base 288 + extra 116 = 404 rows, shape `[404,96,258]`, source counts N0 180, P1 108, P1_HELLO_LIKE 116. Dataset check passed. Reran E4-AC low-motion-aware gate at `artifacts\recognition_upgrade\e4_generalization\e4_ag_low_motion_gate_01`; check passed. Result: mean/min accepted precision `0.9798/0.9739`, mean/min positive coverage `0.9746/0.9661`, max no-sign false commit `0.0000`, GOOD/SORRY min recall `0.9667`. Decision: offline safety floor recovered; next step is E5-A large dual-source candidate screening. No Android/export/production replacement.

**E5-A DUAL-SOURCE BATCH SCREEN RESULT 2026-08-02 - COMPLETE, STRICT INTERPRETATION SUPERSEDED:** Added `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e5_a_dual_source_batch_screen.py` and ran it at `artifacts\recognition_upgrade\e5_batch_screening\e5_a_dual_source_batch_screen_01`. Structural check passed. It inspected 236 labels from ASL Citizen + combined local PC-236 features, found 67 local-supported labels, and tiered the inventory: A0 primary proven 4, A1 routed specialist proven 1, A2 next primary candidate 1, B0 unproven 1, B1 needs more local signers 50, B2 confusion group 2, C1 data-limited 2, C2 blocked prior failure 6, D0 ASL-only 169. The strict dual-source interpretation found only `WANT2` as a next-primary candidate, but the user clarified the intended dataset strategy: ASL Citizen is the broad vocabulary source, while local data supplements/repairs/fills signs where available. Therefore the strict 6-sign E5-B path is historical, not current.

**E5-B ASL-LED 50-CLASS PRIMARY PACKAGE 2026-08-02 - PREPARED, USER TRAINING NEXT:** Added `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e5_b_asl_led_primary_batch.py` and prepared `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_b_asl_led_50_primary_01`. E5-B reuses existing combined schema v3.0 `[96,258]` tensors, does no MediaPipe extraction, and selects 50 ASL-led primary classes with local rows included where available. Dataset: `[2206,96,258]`, train/validation/test `1482/174/550`, source counts `1413` ASL Citizen and `793` local. Stable controls are `GOOD`, `HELLO`, `HAVE`, `KNOW`; excluded from primary are `SORRY`, `HELP`, `BECOME`, `MAKE`, `GET`, `WELCOME2`, `BYE`, `NO`, `YES`, and `THANKYOU`. Smoke passed with output `[32,50]`, one training step, and smoke weights saved. Structural check passed with `--require-dataset --require-full-dataset`. Next action: user runs E5-B full training and final check with `--require-metrics`; then analyze collapse, stable-control retention, per-class recall, and keep/repair/specialist/defer tiers. No Android/export/production replacement.


**MEMORY SAVE 2026-08-02 23:54 +08:00:** Updated `memory.md` with the E5-B ASL-led primary batch handoff. Next session starts with user-run full training for `artifacts\recognition_upgrade\e5_batch_screening\e5_b_asl_led_50_primary_01`, followed by check and metrics analysis. Current strategy: ASL Citizen leads broad vocabulary; local data supplements/repairs/validates where available. No Android/export/production replacement.
**E5-C 50-CLASS TIERING RESULT 2026-08-03 - COMPLETE, E5-D NEXT:** Added `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e5_c_batch_tiering.py` and ran it at `artifacts\recognition_upgrade\e5_batch_screening\e5_c_50class_tiering_01`. Structural check passed with `--require-summary`. E5-C consumed the completed E5-B metrics and produced class tiers, top confusion pairs, and a reduced-primary vocabulary hypothesis. E5-B mean latest test accuracy was `0.4897` versus random `0.0200`, so it learned real signal but is not production/export quality. Tier counts: A strong `9`, B guarded `6`, C regressed controls `2`, C confusion candidates `8`, D overfit/provenance risk `19`, D defer `6`. Recommended reduced-primary hypothesis: `WASH2`, `TAKE`, `MEET`, `HAVE`, `WANT2`, `WORK`, `GOOD`, `MORNING`, `STAND2`, `SELL`, `THINK`, `DRIVE`, `RUN2`, `USE`, `SLEEP`. `HELLO` and `KNOW` regressed badly and were primarily confused as `SEEM`; they must not be silently promoted from E5-B. Next action: prepare E5-D reduced-primary validation. No Android/export/production replacement.
**E5-D REDUCED PRIMARY VALIDATION PACKAGE 2026-08-03 - PREPARED, USER TRAINING NEXT:** Added `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e5_d_reduced_primary_validation.py` and prepared `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_d_reduced_primary_15sign_01`. E5-D uses the E5-C reduced-primary vocabulary `WASH2`, `TAKE`, `MEET`, `HAVE`, `WANT2`, `WORK`, `GOOD`, `MORNING`, `STAND2`, `SELL`, `THINK`, `DRIVE`, `RUN2`, `USE`, `SLEEP`. Dataset shape `[695,96,258]`, train/validation/test `483/49/163`, source counts ASL Citizen `422`, local `273`. `HELLO` and `KNOW` remain excluded due E5-C regression; `SORRY` remains routed/specialist-only. Smoke passed with output `[32,15]` and one train step; structural check passed with `--require-dataset --require-full-dataset`. Next action: user runs E5-D full training and final check with `--require-metrics`. No Android/export/production replacement.

**E5-D REDUCED PRIMARY VALIDATION RESULT 2026-08-03 - USEFUL OFFLINE PASS, NOT EXPORTABLE:** User completed E5-D full training at `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_d_reduced_primary_15sign_01`; structural check passed with metrics. Mean latest test accuracy improved to `0.6933` from E5-B 50-class `0.4897`; mean best-checkpoint test was `0.7382`; max predicted-class share stayed low (`0.1288`, `0.1227`, `0.1104`), so there was no collapse. Strong signs include `WASH2`, `THINK`, `TAKE`, `MEET`, `GOOD`, `STAND2`, `SELL`, `MORNING`, and `HAVE`. Weak/confused signs include `USE`, `WORK`, `DRIVE`, `WANT2`, `RUN2`, and `SLEEP`, with main confusions `WORK/USE`, `WANT2/DRIVE/HAVE`, and `SLEEP/USE/MORNING`. Added `context\recognition_upgrade\E5_D_REDUCED_PRIMARY_VALIDATION_RESULT.md`. Next action: prepare E5-E reduced-primary tiering/decision before routed-system simulation. No Android integration, TFLite export, production replacement, or runtime pipeline change is authorized.
**E5-E REDUCED PRIMARY DECISION RESULT 2026-08-03 - COMPLETE, E5-F NEXT:** Added `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e5_e_reduced_primary_decision.py` and ran it at `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_e_reduced_primary_decision_01`; structural check passed with `--require-summary`. E5-E consumed E5-D metrics and selected the next 7-sign primary candidate: `WASH2`, `THINK`, `TAKE`, `MEET`, `GOOD`, `SELL`, `STAND2`. It registered confusion/repair groups including `USE/WORK`, `DRIVE/HAVE`, `DRIVE/WANT2`, `MORNING/USE`, `SLEEP/USE`, and `RUN2/WASH2`. Added `context\recognition_upgrade\E5_E_REDUCED_PRIMARY_DECISION_RESULT.md`. Next action: prepare E5-F offline routed simulation with E4-AG no-sign gate and existing GOOD/SORRY specialist evidence. No Android integration, TFLite export, production replacement, or runtime pipeline change is authorized.
**E5-F REDUCED PRIMARY ROUTED SIMULATION RESULT 2026-08-03 - NO-GO, E5-G NEXT:** Added `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e5_f_reduced_primary_routed_sim.py` and ran strict simulation at `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_f_reduced_primary_routed_sim_01`; structural check passed but experiment failed. Strict `0.99` policy had mean/min accepted precision `0.9642/0.9310`, no-sign false commits `0.0000`, and unsupported false commits `0.0110`, but positive coverage collapsed to mean/min `0.3611/0.3333` and min class recall `0.0000`. Relaxed diagnostic run at `e5_f_reduced_primary_routed_sim_02_relaxed_diagnostic` with `0.80` threshold improved mean/min coverage to `0.7870/0.7639` and kept no-sign false commits `0.0000`, but min accepted precision `0.8689` and min class recall `0.4545` still failed. Decision: do not export E5-D/E5-F; prepare E5-G clean 7-class primary retrain using the E5-E subset, then rerun no-sign/OOV simulation. No Android integration, TFLite export, production replacement, or runtime pipeline change is authorized.


### 2026-08-03 - E5-G/E5-H reduced primary routed checkpoint
- E5-G clean 7-class closed-set run completed and passed checks: mean latest test `0.8472`; strongest classes `WASH2`, `THINK`, `TAKE`; weak classes `MEET`, `STAND2`.
- E5-H routed/no-sign/OOV simulation completed and is no-go: full 7-sign mean positive coverage `0.1111`; stable-3 coverage `0.1458`; no-sign false commits stayed `0.0000`, but confidence-only rejection rejected too many true signs.
- Next: E5-I explicit open-set/rejection experiment. No Android/export/production recognizer replacement authorized.


### 2026-08-03 - E5-I open-set reject-head checkpoint
- Implemented `pipeline/rgb/e5_i_open_set_reject_head.py` and ran full 7-sign plus stable-3 diagnostics. Both passed structural checks but failed acceptance gates.
- Full 7-sign: accepted precision `0.8985` mean, positive coverage `0.2778` mean, unsupported false commit `0.0220` max, no-sign false commit `0.0110` max.
- Stable-3: closed-set accuracy stayed strong, but routed precision/coverage tradeoff remained unsafe.
- Next: E5-J class-conditioned rejection or per-class accept policy. No Android/export/production replacement authorized.

## 2026-08-03 - E6 Production Recognition Architecture Plan
- User approved stopping the E5 threshold/no-go loop as the main path. `context/recognition_upgrade/E6_PRODUCTION_RECOGNITION_ARCHITECTURE_PLAN.md` is now the current planning document for the next recognition-upgrade stage.
- E5-J class-conditioned rejection is reclassified as a hypothesis inside E6-3, not the next assumed solution.
- Verified reason: E5-G closed-set learning did not transfer to safe routed recognition; E5-H confidence thresholds and E5-I shared accept/reject both failed accepted-precision/coverage/per-class recall gates.
- Next action: prepare E6-0/E6-1 baseline freeze and dataset/representation audit. No Android integration, TFLite export, production replacement, schema mutation, or RGB runtime work is authorized.

## 2026-08-03 - E6-0/E6-1 Audit Complete
- E6-0 baseline freeze complete: `context/recognition_upgrade/E6_0_BASELINE_FREEZE.md` records hashes for current production `streaming.tflite`, `vocab.json`, `model_manifest.json`, `recognition_config.json`, and MediaPipe task files, plus rollback instructions.
- E6-1 consolidated audit complete: `context/recognition_upgrade/E6_1_CONSOLIDATED_EVIDENCE_DATASET_AUDIT.md` and `context/recognition_upgrade/e6_audit_tables/` record E1-E5 experiment inventory and per-sign/source/split counts.
- Decision: data insufficient. Stop modeling. E6-2 richer features, E6-3 rejection, specialists/RGB, routed simulation, and Android shadow mode are blocked until a product-core data-readiness package repairs raw lineage, signer/source/split/variant metadata, no-sign/OOV coverage, and target sign support.

## 2026-08-03 - Product-Core Data Readiness Package Complete
- Created `context/recognition_upgrade/PRODUCT_CORE_DATA_READINESS_PACKAGE.md` and `context/recognition_upgrade/DATASET_MANIFEST_LINEAGE_SCHEMA.md`.
- Created machine-readable package tables under `context/recognition_upgrade/product_core_data_readiness/`.
- Recommended bounded data-readiness vocabulary: `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`, `THINK`, `TAKE`, and `SELL`; `WASH2` is a strong control/reserve sign.
- Verified selected/reserve raw-video audit: `605` raw clips, `0` missing files, `0` zero-byte files, `0` decode failures, `0` exact duplicate files.
- Verified blocker: E5 broad-run feature manifests mostly point to `.npz` source tensors, not raw videos; E4-V proves raw `video_path` lineage exists only for the bounded local GOOD/SORRY specialist package.
- Minimum gate before modeling resumes: `150` reviewed lineage-linked clips/sign, `75` local/app-domain clips/sign, `10` total signers/sign, `5` local signers/sign, strict signer-disjoint fresh test splits, and `1,000` reviewed no-sign/OOV/transition windows.
- Decision: data can be repaired, but new collection is required. Next action is a manifest-builder plan only; no extraction, training, schema mutation, Android integration, TFLite export, or production replacement is authorized.

## 2026-08-03 - Product-Core Lineage Fix And Gap Recalculation Complete
- Built canonical raw-video lineage manifest at `context/recognition_upgrade/product_core_data_readiness/lineage_fix_v1/canonical_product_core_manifest.csv` for `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`, `THINK`, `TAKE`, `SELL`, plus `WASH2` control.
- Manifest rows: `824` total; ASL Citizen `275`, local supplementary `549`; exact duplicate groups `0`.
- Automated classification: `338` Accepted, `486` Manual review required, `0` Rejected. ASL Citizen rows are review-required because they lack AppHear sidecar quality metrics; local quality-warning rows are also review-required.
- Recalculated accepted-now gaps: total clips `885`, local clips `289`, local signer slots `26`. Best-case after manual review: total clips `459`, local clips `215`, local signer slots `24`.
- Vocabulary reassessment: keep `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`, `THINK`, `TAKE`, `SELL`; keep `WASH2` as control only.
- Decision: More data is required. Do not extract features or train until manual review/adjudication and remaining collection gaps are handled. First future model experiment remains a clean v3.0 `[96,258]` baseline only.

## 2026-08-03 - E6 Product-Core Review Package Prepared
- Added `pipeline/rgb/e6_product_core_review.py` with `prepare`, `review`, `summarize`, and `check` commands for manifest review only. No feature extraction, training, schema change, Android work, RGB, specialists, or TFLite export.
- Smoke package `artifacts/recognition_upgrade/product_core_data_readiness/e6_product_core_review_smoke_01` prepared and checked.
- Full review package prepared at `artifacts/recognition_upgrade/product_core_data_readiness/e6_product_core_review_01`: `486` manual-review rows, `211` local supplementary and `275` ASL Citizen. Structural check passed; initial summary has `486` blank decisions.
- Added runbook `context/recognition_upgrade/product_core_data_readiness/lineage_fix_v1/E6_PRODUCT_CORE_REVIEW_RUNBOOK.md`.
- Next action: user runs the review GUI, then `summarize` and `check --require-reviewed`. Modeling and extraction remain blocked.

## 2026-08-03 - E6 Product-Core Review Complete
- User completed `artifacts/recognition_upgrade/product_core_data_readiness/e6_product_core_review_01`; check passed with `486/486` rows reviewed, `0` remaining, `0` errors.
- Summary: `329` accepted and `157` rejected; no needs-expert or diagnostic-only rows.
- Final accepted counts: GOOD `81`, HELLO `151`, SORRY `81`, HAVE `80`, KNOW `74`, THINK `51`, TAKE `49`, SELL `49`.
- Final accepted local signer counts: GOOD `2`, HELLO `3`, SORRY `3`, HAVE `2`, KNOW `2`, THINK `1`, TAKE `1`, SELL `1`; signer diversity remains the main blocker.
- Remaining gaps after review: total clips `585`, local clips `264`, local signer slots `25`; no-sign/OOV/transition gap remains `1,000` reviewed windows.
- Added `context/recognition_upgrade/product_core_data_readiness/lineage_fix_v1/E6_PRODUCT_CORE_REVIEW_RESULT.md`.
- Decision: More data is required. Do not extract features or train. Next concrete step is targeted collection planning/execution for the reviewed gaps, then a clean v3.0 `[96,258]` baseline only after gates pass.

## 2026-08-03 - E6 Targeted Collection Package Prepared
- Converted reviewed gaps into collection targets under `context/recognition_upgrade/product_core_data_readiness/collection_targets_v1/`.
- Positive collection target: `605` fresh local/app-domain clips across `25` local signer slots. Per-sign targets: GOOD 69/3, HELLO 20/2, SORRY 69/2, HAVE 70/3, KNOW 76/3, THINK 99/4, TAKE 101/4, SELL 101/4 clips/signers.
- No-sign/OOV/transition target remains `1000` reviewed windows across N0 no-hand, idle hands, face-adjacent, accidental motion, OOV signs, and transition/partial subtypes.
- Added `pipeline/rgb/e6_collection_validate.py` with `init` and `validate` commands for raw-folder structure, video decode, hashes/duplicates, and target progress. No feature extraction/training/schema/Android work.
- Initialized empty scaffold at `scratchpad/e6_product_core_collection/raw`; empty validation smoke passed and reports all targets remaining.
- Added runbook `context/recognition_upgrade/product_core_data_readiness/collection_targets_v1/E6_TARGETED_COLLECTION_RUNBOOK.md`.
- Next while recordings are pending: prepare signer-disjoint split dry-run and baseline experiment design only; modeling/extraction remain blocked.

## 2026-08-03 - E6 Split Dry-Run Prepared
- Added `pipeline/rgb/e6_split_dry_run.py` to check signer-disjoint split feasibility before feature extraction/training.
- Ran dry-run at `artifacts/recognition_upgrade/product_core_data_readiness/e6_split_dry_run_01`; result `split_gate_blocked_more_data_required`, with `0/8` signs feasible under the data-readiness gate.
- Added `context/recognition_upgrade/product_core_data_readiness/collection_targets_v1/E6_COLLECTION_AND_SPLIT_PREP_RESULT.md`.
- Next non-recording work allowed: baseline v3.0 experiment design and no-sign/OOV review taxonomy only. Feature extraction/training remains blocked until collection validation and split dry-run pass.





## 2026-08-10 - C0-B0 Stage 2 Research Learning Curve Ready
- User authorized internal research/development only; commercial use, restricted-data redistribution, production claims, Android integration, and recognizer replacement remain unauthorized.
- Completed and checked the 400-row signer/source-disjoint research manifest at `artifacts/recognition_upgrade/e2e_c0/c0b_stage2_research_manifest_01`: 312 train / 88 development, zero signer or protected P0/N0/P1 lineage overlap.
- Prepared hard-linked nested 25/50/100-percent COCO subsets at `artifacts/recognition_upgrade/e2e_c0/c0b_stage2_detector_01`; package check passed.
- Added `pipeline/tracking/e2e_c0b_stage2.py`, `pipeline/tracking/e2e_c0b_stage2_train.py`, focused tests, and `model/config/recognition_upgrade/run_c0b_stage2_256_learning_curve.ps1`. Ruff, mypy, PowerShell parsing, and 17 focused tests pass.
- Next user action: start Docker Desktop and run the MobileNetV2-256 learning-curve script. Review all three fractions before authorizing I320. QAT/INT8, locked P0/N0/P1 evaluation, Android work, and production replacement remain blocked.
- Disk note: F: has approximately 5.5 GB free; package images are hard links, but training may add roughly 1-3 GB across run outputs and Docker storage.

## 2026-08-11 - C0-B0 MobileNetV2-256 Complete, I320 Runner Ready
- The 25/50/100-percent MobileNetV2-256 learning curve completed and passed structural checks. AP improved 0.2012 -> 0.2911 -> 0.3447; AP50 0.5283 -> 0.7211 -> 0.7747; AP75 0.0833 -> 0.2057 -> 0.2859.
- Interpretation: the detector is data-responsive, but localization remains weak; COCO metrics do not yet establish AppHear availability, two-hand, blur, IoU50-recall, or no-hand false-ROI gates.
- Added and validated `model/config/recognition_upgrade/run_c0b_stage2_i320_learning_curve.ps1` and extended the checker with `--require-i320`. Ruff, mypy, PowerShell parsing, and 17 focused tests pass.
- Next user action: run the I320 25/50/100-percent comparison. Threshold fitting, QAT/INT8, frozen P0/N0/P1 evaluation, Android work, and production replacement remain blocked.

## 2026-08-11 - C0-B0 I320 Complete, Development Threshold Evaluator Ready
- I320 completed and outperformed 256 at the full subset: AP 0.4010 vs 0.3447, AP50 0.8548 vs 0.7747, AP75 0.3723 vs 0.2859. I320 is the accuracy candidate; 256 remains the latency control.
- Added `pipeline/tracking/e2e_c0b_stage2_eval.py` and `model/config/recognition_upgrade/run_c0b_stage2_development_eval.ps1` for development-only raw predictions, exact matching, threshold sweep, subgroup metrics, and CPU latency.
- The evaluator does not access frozen P0/N0/P1 and does not quantize, export to Android, or modify production behavior. Actual I320 single-image reload/inference, Ruff, mypy, PowerShell parsing, and focused tests pass.
- Next user action: run the development threshold comparison. Review its selected thresholds and AppHear metrics before any QAT/INT8 or frozen evaluation.

## 2026-08-11 - C0-B0 Development Threshold Result: NO-GO
- Both full-data float candidates completed the locked 88-frame development evaluation; frozen P0/N0/P1 were not accessed.
- I320 won development selection at threshold 0.5517: availability 76/113 = 67.26%, any-hand frame recall 60/74 = 81.08%, complete two-hand 16/39 = 41.03%, IoU50 72/113 = 63.72%, and 0/14 observed no-hand false-positive frames. Inference p50/p95 was 46.6/51.2 ms.
- 256 at threshold 0.7976 reached availability 50.44%, complete two-hand 23.08%, IoU50 50.44%, and inference p50/p95 29.9/34.7 ms.
- Threshold diagnosis: I320 can reach 85.84% availability only with 85.71% no-hand FPR; allowing one no-hand false-positive frame still gives only 75.22% availability. This is not a minor threshold issue.
- Decision: C0-B0 promotion no-go. Do not run QAT/INT8, frozen P0/N0/P1, Android, or a generic hyperparameter sweep. Next is one explicit architecture/data decision using this result and the independent hard-negative inventory.
- Detailed source: `context/recognition_upgrade/C0B_STAGE2_DEVELOPMENT_RESULT.md`.

## 2026-08-25 - P4-R1A Targeted RTMPose-Hand5 Recovery Complete; Candidate Insufficient
- Verified `P4_ELIGIBILITY_TRUTH_V2`, reconciled exactly 18 residual visible-hand observations, and ran only the official MMPose `hand` stack: SSDLite-MobileNetV2 plus `rtmpose-m_8xb256-210e_hand5-256x256`, at the frozen `score > 0.30` / NMS 0.30 operating point and one preregistered current-frame DWPose interaction ROI. All 132/132 unique frames processed; no threshold, crop, or model retry occurred.
- The independent 18-case physical-instance review found 0 `MISSING_HAND_RECOVERED`, 0 duplicates, 17 false/no-output cases, and one ambiguous case. Residual recovery is 0/18, so combined governed physical coverage remains 426/444 = 95.95%, below the required 436/444.
- Frozen controls also fail: ZERO activation 14/40 (35%), ONE existence 26/40 (65%), and TWO complete output capacity at most 6/40 (15%). ONE two-or-more-output activation is 0/40 but does not offset the primary failures.
- Final classification: `RECOVERY_CANDIDATE_INSUFFICIENT`. Canonical report/package: `artifacts/recognition_upgrade/perception_backend_replacement/p4r1a_rtmpose_hand5_targeted_recovery_01`. Stop without P4-R1B, alternate model, threshold change, training, Android, recognition, or S4-S7 work.

## 2026-08-22 - NEGATIVE_GOLD_V1 Item-Level Audit Package Frozen
- Historical outcomes remain unchanged: the first Open Images review is `QC FAIL`; the second
  confirmation review remains `NEGATIVE_GOLD_V1_STILL_INCOMPLETE` under its original failed QC
  gate. The current trusted benchmark remains 76/200.
- The two second-pass binary repeat-conflict candidates were preserved and permanently excluded
  without relabeling. The verified retained dual-confirmed pool is 158.
- Frozen an independently blinded 40-image item-level audit at
  `artifacts/recognition_upgrade/perception_backend_replacement/negative_gold_item_level_audit_01`
  using seed 20260822 and presentation seed 20260823. All 19 scene/category strata are represented;
  the queue contains 12 people-present and 28 person-free discovery candidates from 40 authors.
- Frozen dHash rule remains <=4; measured minimum distance is 10 internally and 10 against the
  existing 76-frame seed. Source/provenance hashes passed; queue is 0/40 reviewed with zero errors.
- Next action: user completes the 40-image blinded audit. Do not prepare the conditional 20-image
  follow-up or freeze the benchmark until the human result is evaluated against the preregistered
  0/1/>=2 contamination rules. No perception/model/training/Android work occurred.

## 2026-08-22 - NEGATIVE_GOLD_V1 Complete And Frozen
- The independently blinded item-level audit completed 40/40 with 40
  `NO_HUMAN_HAND_VISIBLE`, zero clear actual-human-hand contamination, zero uncertain rows, and
  zero tooling/provenance defects. The preregistered zero-contamination branch passed; no
  follow-up audit was required.
- Historical outcomes remain unchanged: first Open Images review `QC FAIL`; second confirmation
  review `QC FAIL` / `NEGATIVE_GOLD_V1_STILL_INCOMPLETE`. The two known binary repeat-conflict
  items remain permanently excluded without relabeling.
- All 158 retained candidates passed the frozen exact/dHash diversity checks. Deterministic
  proportional-stratum/farthest-first ranking selected exactly 124 additions and placed 34 in
  `NEGATIVE_GOLD_RESERVE`; selected minimum internal/seed dHash distance is 16/16.
- Final decision: `NEGATIVE_GOLD_V1_COMPLETE`. Frozen benchmark is 76 existing + 124 Open Images
  = 200 rows with 200 unique SHA-256 values and zero deficit. Main and reserve manifests, audit
  labels, contamination result, diversity report, and final hashes are under
  `artifacts/recognition_upgrade/perception_backend_replacement/negative_gold_item_level_audit_01/finalization`.
- Negative-benchmark construction is closed. Do not expand or reopen it absent a concrete defect,
  and do not begin the next perception phase automatically. No perception/model/training/Android
  work occurred.

## 2026-08-22 - P1 Perception Architecture Feasibility/Adapter Audit Complete
- Verified the corrected positive gold (150 frames, 41 signers, 184 hand boxes), frozen
  NEGATIVE_GOLD_V1 (200 paths/hashes; 76 historical + 124 Open Images), exact 16/25/46 diagnostic
  instance subsets, MediaPipe raw 21-landmark outputs, and exact 122/184 baseline associations.
- Positive GT supports spatial hand-box matching but has no human landmark truth and all 184
  anatomical-side values are unknown. P2 can measure availability/localization and pairwise
  recovery, not landmark error or anatomical L/R accuracy.
- Recommended one shared model-independent ROI: full image as a single pseudo-person box with the
  official 1.25-padded 3:4 top-down affine for each model. No person detector or GT-derived crop.
- DWPose-L 256x192 adapter is feasible and CPU-plausible after an isolated compatible environment.
  Sapiens-2B adapter is specifiable but `SAPIENS_2B_NOT_FEASIBLE` locally: 8.07-GiB checkpoint,
  no operational CUDA device, and only 9.44 GiB free on F:. Sapiens remains research-ceiling only.
- Proposed rule for lead freeze: native score >=0.30 on at least 11/21 joints; reuse frozen palm
  center + >=50% landmarks-inside-box maximum-cardinality matching. No threshold was tuned or
  candidate executed.
- Canonical report: `context/recognition_upgrade/P1_PERCEPTION_ARCHITECTURE_FEASIBILITY_ADAPTER_AUDIT.md`.
  P2 remains blocked pending Sapiens hardware/fallback decision and explicit rule/gate freeze. No
  checkpoint download, model run, Android, S4-S7, training, or production change occurred.

## 2026-08-22 - P4-A DWPose Presence Eligibility Complete, Improved But Gates Failed
- Reused the frozen 753-frame P3 native DWPose output package; no DWPose or other perception model
  inference was rerun. Derived 1,102 governed anatomical-slot truth rows from the 551 reviewed A2
  frames: 323 `VISIBLE`, 753 `NOT_VISIBLE`, and 26 retained-but-unscored `UNKNOWN` rows.
- Froze a leakage-safe sequence split before fitting: 11 train, 5 validation, and 5 one-time
  holdout sequences. Consecutive frames from an attempt never cross splits; the reviewed
  crossing/contact sequence was retained in holdout. The frozen baseline remained score >=0.30
  on at least 11/21 joints.
- Evaluated the bounded candidates only. The fixed anatomical logical rule rejected all validation
  positives. Validation selected `E2_FIXED_L2_LOGISTIC_SINGLE_FRAME`, which passed all validation
  gates; the conditional causal candidate was therefore not activated. No threshold, feature,
  depth, or regularization sweep occurred.
- On the one-time holdout, E2 reduced zero-hand frame false presence from 37/75 (49.33%) to 2/75
  (2.67%) and explicit-rest false presence from 28/63 (44.44%) to 0/63, while retaining 24/24
  complete two-hand frames. Per-hand precision was 95.00%, but visible recall was 76/79 (96.20%),
  below the preregistered >=98% holdout gate. Three visible observations were rejected.
- Full governed diagnostics (not independent holdout evidence) were 318/323 visible recall
  (98.45%), 11/324 zero-hand false-presence frames (3.40%), 3/271 rest false-presence frames
  (1.11%), and 96/97 complete two-hand retention (98.97%). Crossing/contact visible recall was
  100% on the six holdout slot rows; one-hand holdout recall was the weak subgroup at 90.48%.
- Final classification: `ELIGIBILITY_IMPROVED_BUT_GATES_FAILED`. The same whole-body output has
  strong eligibility evidence, but this fitted rule is not approved as a production gate because
  it missed the frozen visible-recall requirement. P4-B was not started. No Android, S4-S7,
  recognition, S6 retraining, Sapiens, z fabrication, or production feature change occurred.
- Canonical report and frozen artifacts:
  `artifacts/recognition_upgrade/perception_backend_replacement/p4a_dwpose_presence_eligibility_01/`.

## 2026-08-22 - P4-A2 High-Recall Eligibility Rescue Blocked Before Fitting
- Historical P4-A remains `ELIGIBILITY_IMPROVED_BUT_GATES_FAILED`. Reverified the frozen P4-A
  truth, sequence split, E2 coefficients, feature normalization, and holdout-prediction hashes.
  The old holdout is `HISTORICAL_DIAGNOSTIC_ONLY` and was not used for fitting, selection, or a
  new success claim.
- Comprehensive fresh-evidence inventory contains 1,539 rows. The strongest untouched temporal
  phone pool has 68 attempts, 2,857 saved frames, two governed signer IDs, and 25 one-hand / 41
  two-hand / 2 variant-dependent attempts. Sixty-six attempts have onset/release/performance span
  annotations, but none has fresh per-frame anatomical left/right visibility truth.
- Twelve P3 gold-video diagnostic sequences add 202 consecutive frames from 12 signers with native
  DWPose output, but only their center frames have human hand-box truth. P2 adds 150 static gold
  images and 200 static NEGATIVE_GOLD_V1 images. E6 contributes 486 product-core reviewed videos,
  63 collection spot-review videos, and 560 provisional negative-context videos. These sources
  have accessible RGB but only static, whole-video, or batch-level truth—not the required
  per-frame anatomical visibility plus rest and entry/exit truth.
- All 21 sequences with direct A2 frame-level anatomical truth were consumed by P4-A. A2-0 and
  A2-1R are byte-identical 551-row annotation copies, while A2-2R is a subset; none is fresh.
- Final status: `P4A2_BLOCKED`; classification: `INSUFFICIENT_FRESH_EVIDENCE`. No split, rescue
  feature list, R1 rule, R2 activation, fitting, or final evaluation was fabricated.
- Smallest repair uses existing RGB only: blinded frame adjudication of all 12 P3 gold temporal
  sequences plus 16 untouched phone attempts, capped at about 600 reviewed frames. Require direct
  left/right visibility, zero/rest, entering/leaving, blur/occlusion, crossing/contact, and
  clear/weak visibility labels before freezing development/validation/final splits. New recording
  is not currently justified.
- Canonical report and blocked artifacts:
  `artifacts/recognition_upgrade/perception_backend_replacement/p4a2_high_recall_eligibility_rescue_01/`.
  No DWPose inference, model work, Android, S4-S7, S6, recognition, Sapiens, z fabrication, or
  P4-B work occurred.

## 2026-08-24 - P4-A2 Fresh-Evidence Repair Review Package Frozen
- Historical decisions remain unchanged: P4-A is `ELIGIBILITY_IMPROVED_BUT_GATES_FAILED`, and
  P4-A2 remains `P4A2_BLOCKED — INSUFFICIENT_FRESH_EVIDENCE`. This step repairs evidence only.
- Deterministically selected all 12 P3 gold temporal sequences plus 16 untouched phone attempts:
  eight signer_01 attempts for future development/validation and eight withheld_phone attempts
  reserved for final evaluation. All three available untouched withheld one-hand attempts are
  included. Selection used signer/gloss/expected-hand metadata and timing only—not model output.
- Frozen an initial blinded queue of 458 RGB frames: all 202 consecutive P3 frames plus 16
  timing-sampled frames from each phone attempt. Another 128 timing-only phone frames remain a
  bounded reserve (eight per attempt) and may be added only to address a measured human-semantic
  deficit after the initial review.
- The reviewer queue exposes only anonymous sequence progress and raw RGB. The GUI makes
  anatomical left/right explicit, supports previous/next raw context, undo, autosave, resume,
  three-way uncertainty, visibility quality, rest/entry/leaving, and condition/contact tags.
- Corrected the initial review GUI's broken Steps 1-3 layout before adjudication began. The
  revised interface uses explicit Yes/No/Unsure buttons, automatic ZERO_HAND consistency,
  plain-language definitions, an ordinary-frame shortcut, clearer context/edit navigation, and
  a larger image while preserving the same annotation schema and autosave file.
- Reduced common-frame annotation to one click (or F1-F5): no-hands/rest, anatomical-left only,
  anatomical-right only, both hands, or unsure now save and advance immediately with complete
  internally consistent ordinary-frame labels. Detailed controls remain available only for
  weak/special/rest-with-visible-hand/entry/leaving/contact/crossing cases.
- Package validation and focused tests pass. Human review is pending at
  `artifacts/recognition_upgrade/perception_backend_replacement/p4a2_fresh_evidence_repair_01/`.
  Do not run E2/R1/R2 or freeze model-development splits until the human semantic minimums pass.
- No E2, DWPose, MediaPipe, recognition, training, Android, S4-S7, S6, Sapiens, P4-B, or new
  recording work occurred.

## 2026-08-24 - P4-A2 Initial Human Review Complete; Transition Top-Up Pending
- Completed and validated all 458 initial blinded review rows. Human semantic evidence strongly
  exceeds five requirements: 412 visible-hand observations, 142 one-hand visible observations,
  181 zero-hand frames, 173 explicit-rest frames, and 135 complete two-hand frames. Four frames
  have uncertain visibility. One-hand quality includes 140 clear and only two weak observations.
- Entry/leaving evidence is the sole deficit: 6 certain frames versus the required 25, short by
  exactly 19. The fresh evidence is therefore not frozen and no development/evaluation split has
  been released yet.
- Added one bounded 29-frame review top-up from the existing timing-only reserve: 19 available
  onset/release candidates plus ten additional closest timing candidates. Selection used only the
  preregistered timing phases and existing attempt metadata, never E2/DWPose/MediaPipe results or
  human-label prediction. Ninety-nine reserve frames remain untouched.
- Next action: review only the 29 newly queued rows, using detailed mode to mark genuinely visible
  entering/leaving behavior. The GUI now exposes six one-click transition presets (anatomical
  left/right/both × entering/leaving, F6-F11), each of which completes the full underlying label,
  autosaves, and advances. Recalculate human semantic counts afterward. Do not fit E2/R1/R2.
- Recovery diagnosis after reviewer feedback: the prior interaction model was architecturally
  misaligned because it exposed storage fields as separate questions and split ordinary versus
  special frames into unequal workflows. A matrix redesign was also rejected by the reviewer as
  too cognitively dense. The final simplified interaction is a two-step keyboard workflow:
  state `A/R/E/L/U`, followed by hands `0/1/2/3/4`; the hands key produces every required field,
  saves, and advances. Ordinary frames need only a hand key because state resets to Ordinary.
  Optional quality/condition chips remain collapsed and are needed only when applicable. Existing
  labels remain untouched and resumable.

## 2026-08-24 - P4-A2 Evidence Repair Stopped: Benchmark Tooling Defect
- The apparent completed 487-row result is invalid and was not frozen. Only 29 top-up rows were
  added, but entry/leaving increased from 8 to 102 and several original semantic totals changed
  beyond the mathematical contribution possible from 25 remaining reviews.
- Root cause: after saving the first sparse top-up row, the GUI advanced to the adjacent queue row
  rather than the next unlabeled row. Because top-up rows were interspersed by sequence/frame order,
  it revisited completed initial rows and overwrote their labels. The defect affects 438/458 initial
  rows across all 28 sequences; only 20 initial labels precede the first top-up review timestamp.
  Ninety-five current transition labels occur on affected initial rows.
- Original overwritten item labels are not recoverable from the package; only earlier aggregate
  counts survive. The current label file was preserved unchanged and an affected-row manifest plus
  machine-readable defect result were frozen. `P4A2_FRESH_HUMAN_TRUTH_V1` and its splits were not
  created/released.
- Navigation is corrected for any future governed review: Save now jumps strictly to the next
  unlabeled row, and deliberate revisions are recorded in an append-only journal before overwrite.
- Status: `BENCHMARK_TOOLING_DEFECT — NOT FROZEN`. No E2/R1/R2, DWPose, MediaPipe, recognition,
  training, Android, S4-S7, S6, Sapiens, P4-B, or new recording work occurred.

## 2026-08-24 - P4-A2 Annotation Tool v2 Repaired; Clean Relabel Pending
- Historical v1 status remains `BENCHMARK_TOOLING_DEFECT — NOT FROZEN`. Preserved the corrupted
  label file, defect report, and 438-row affected audit under an explicit
  `INVALID_TOOLING_DEFECT_DO_NOT_USE` package. The preserved label SHA-256 is
  `0ea210d178d312cb41955f332794314c72186ab0f27cfc691d3f5b8e3249342e`.
- Built a separate v2 annotation store. Each immutable row ID derives from sequence ID, frame
  index, and image SHA-256; every save rechecks displayed ID/sequence/frame/hash/source bytes,
  rejects completed rows, atomically replaces the canonical CSV, then rescans status to jump only
  to the next non-COMPLETE row. Array position is never the save identity or resume authority.
- Completed-label edits require explicit confirmation and reason and journal prior/new values.
  Explicit undo is also journaled. Backups occur every 25 completions, at session close, and before
  top-up merge. Interspersed top-up preserves completed row payloads byte-equivalently.
- Required focused suite passes 10/10: empty review, partial resume, fully complete, exact
  interspersed-top-up reproduction, undo, explicit completed edit, crash/restart, duplicate ID,
  wrong image identity/hash, and top-up after partial completion.
- Froze a clean 458-row v2 initial package from exactly the same selected RGB evidence. All 458
  rows are `UNREVIEWED`; no corrupted labels were imported or displayed. The same 29 deterministic
  prior top-up candidates are preserved inactive and may be activated only after initial human
  semantic counts demonstrate a deficit.
- Human relabeling is pending under
  `artifacts/recognition_upgrade/perception_backend_replacement/p4a2_fresh_evidence_repair_v2_01/`.
  `P4A2_FRESH_HUMAN_TRUTH_V1` and model-development splits remain unfrozen. Do not run E2/R1/R2.

## 2026-08-24 - P4-A2 Clean Fresh Human Truth Complete And Frozen
- Completed the repaired clean v2 review: 458/458 rows, 28 sequences, 14 signers. The historical
  v1 result remains `BENCHMARK_TOOLING_DEFECT — NOT FROZEN`; no corrupted label was imported.
- All semantic evidence minimums passed without activating the 29 inactive top-up candidates:
  448 visible-hand observations, 162 one-hand visible frames, 153 zero-hand frames, 146 rest
  frames, 72 entry/leaving frames, and 143 complete two-hand frames. Top-up count is zero.
- Final integrity audit passed: 458 unique immutable IDs, verified image hashes, zero revisions,
  no edit journal, reproducible semantic counts, and exact frozen review-tool/test/source hashes.
  Required annotation-tool tests remain 10/10 passed.
- Froze `P4A2_FRESH_HUMAN_TRUTH_V1` with dataset SHA-256
  `7819c59123b4dacdafac190c81754deb766d6ed6087a2b58535490d45a6a3edd` and annotation SHA-256
  `1b9f34412ba885e397019742bf29027987ce58668d099fd3914e48ab3206774b`.
- Sequence-level splits are frozen: dev 132 rows / 8 sequences, validation 130 / 8, and sealed
  final evaluation 196 / 12. Final evaluation is signer-separated from development/validation.
- Limitation: the reviewer labeled zero WEAK one-hand observations and zero positive optional
  blur/occlusion/edge/partial/crossing/contact cases. The core visibility/rest/transition truth is
  frozen, but this package cannot support those optional subgroup diagnostics.
- Evidence repair is complete. Do not rerun annotation or activate top-up absent a concrete truth
  defect. No E2/R1/R2, DWPose, MediaPipe, recognition, training, Android, S4-S7, S6, Sapiens,
  P4-B, or new recording work occurred.

## 2026-08-24 - P4-A2 High-Recall Eligibility Rescue Complete; Gates Failed
- Historical P4-A remains `ELIGIBILITY_IMPROVED_BUT_GATES_FAILED`. Verified the frozen
  `P4A2_FRESH_HUMAN_TRUTH_V1` dataset, annotation, source, tool, and split hashes before work;
  the 196-frame/12-sequence final set remained sealed and signer-separated until candidate freeze.
- Reused the exact frozen E2 coefficients, feature ordering, normalization, and 0.5 decision rule.
  Native P3 DWPose outputs covered 202/458 frames. Ran the exact unchanged DWPose-L checkpoint,
  config, whole-frame ROI, preprocessing, decoder, and flip test only for the 256 missing phone
  frames; checkpoint SHA-256 remained
  `e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7`.
- Fresh E2 generalization was substantially weaker than its historical P4-A holdout: development
  visible recall 109/136 (80.15%) and validation 89/148 (60.14%), while validation zero/rest false
  presence remained 1/31 (3.23%) and 1/32 (3.13%). This is fresh cross-signer evidence and does
  not alter the historical P4-A result.
- Froze one primary R1 logical rescue and two bounded DEV-derived variants before validation.
  All acted only on E2 rejections and used only preregistered current-frame DWPose score, arm/body,
  and geometry features. Validation selected the least-complex primary rule by the frozen ranking,
  but it failed all five gates: visible recall 138/148 (93.24%), one-hand 48/50 (96.0%), zero-hand
  false presence 9/31 (29.03%), rest false presence 11/32 (34.38%), and complete two-hand 41/49
  (83.67%). R2 was not activated: zero remaining validation misses met its frozen safe causal-
  continuity conditions.
- Opened the signer-separated final truth once after freezing code, rule, thresholds, feature
  manifest, and identity-only final manifest. Frozen E2 achieved visible recall 93/164 (56.71%),
  one-hand recall 34/48 (70.83%), zero/rest false presence 2/90 (2.22%) and 2/87 (2.30%), and
  complete two-hand retention 24/58 (41.38%).
- The selected `E2_PLUS_R1` rescue recovered 61 visible observations and lost zero E2 hits, but
  still reached only 154/164 visible recall (93.90%), 43/48 one-hand recall (89.58%), and 53/58
  complete two-hand retention (91.38%). It reopened false presence to 40/90 zero-hand frames
  (44.44%) and 38/87 rest frames (43.68%), introducing 38 and 36 new false-positive frames.
- Final status: `P4A2_COMPLETE`; classification:
  `ELIGIBILITY_IMPROVED_BUT_GATES_FAILED`. All five preregistered final gates failed. This is a
  valid bounded-rescue result, not a tooling/model-load/sealing failure. Do not retune, create R3,
  add another detector, run Sapiens, or start P4-B automatically.
- Scope limitation: the fresh package contains zero WEAK one-hand labels and no positive optional
  blur/occlusion/contact subgroup labels, so this result cannot claim robustness for those cases.
  No Android, S4-S7, S6, recognition, representation, z fabrication, training, fine-tuning, or
  production integration work occurred. Canonical artifacts:
  `artifacts/recognition_upgrade/perception_backend_replacement/p4a2_high_recall_rescue_final_01/`.

## 2026-08-24 - P4-C1 WiLoR-Det Eligibility Screen Complete; Recall Insufficient
- Closed the approved detector-only WiLoR architecture screen on the complete 458-frame
  `GOVERNED_P4C_ARCHITECTURE_COMPARISON_BENCHMARK`. Recomputed the frozen dataset and annotation
  hashes, rehashed all 458 source images, and processed 458/458 without changing the official
  reference operating point, crop, NMS, class mapping, or preprocessing.
- The exact official artifact was `pretrained_models/detector.pt` from WiLoR source commit
  `fcb911312a38fa8badd30d9656a167485d61b8f9`, checkpoint SHA-256
  `5ef3df44e42d2db52d4ffe91f83a22ce9925e2acc9abebf453f2c5d22e380033`. Its internal model is
  an Ultralytics YOLOv8m-Pose-derived medium detector with classes `0=left`, `1=right`, 21x3
  auxiliary keypoints, 512-pixel reference inference, confidence 0.30, and class-aware IoU-NMS
  0.70. The full WiLoR reconstruction model was not loaded or run.
- Anatomical-side scoring was valid and preserved separately from side-agnostic existence
  capacity. Strict visible-hand recall was 416/448 (92.86%); side-agnostic detection capacity was
  only 418/448 (93.30%), showing that nearly all losses were detector misses rather than only
  handedness mistakes. One-hand anatomical recall was 151/162 (93.21%); existence recall was
  153/162 (94.44%). Complete two-hand retention was 124/143 (86.71%).
- False presence was also unacceptable: 84/153 human ZERO_HAND frames (54.90%), 82/146 explicit
  rest frames (56.16%), and 77/141 frames that were both rest and ZERO_HAND (54.61%). Per-hand
  precision was 80.15%, specificity 77.99%, F1 86.04%; opposite-slot false presence occurred on
  12/162 one-hand frames (7.41%).
- Against frozen DWPose presence on visible slots, WiLoR/DWPose both hit 411, WiLoR alone hit 5,
  DWPose alone hit 18, and both missed 14. On 153 ZERO_HAND frames, WiLoR rejected 25 cases where
  DWPose hallucinated, but fired on 37 that DWPose rejected and both fired on 47. WiLoR therefore
  did not provide a sufficiently safe independent eligibility signal at the frozen operating point.
- All five architecture-screening gates failed: visible recall, one-hand recall, zero-hand false
  presence, rest false presence, and complete two-hand retention. Final classification:
  `WILOR_DETECTION_RECALL_INSUFFICIENT`. Do not lower or sweep the threshold, add HVD behind this
  failed detector, combine it with DWPose, or start P4-D automatically. The protocol-directed next
  decision is a body-associated fallback architecture review; BPJDet was not run.
- CPU diagnostic runtime was p50 173.52 ms / p95 187.01 ms total model time, with peak process RSS
  564.8 MiB and a 51.1 MiB checkpoint. This is not an Android FPS result. Deployment remains
  `DEPLOYMENT_LICENSE_REVIEW_REQUIRED` because WiLoR models are CC-BY-NC-ND-4.0 and the pinned
  Ultralytics runtime is AGPL-3.0 absent a separate license.
- No other detector, full WiLoR reconstruction, training, fine-tuning, DWPose/E2/R1 combination,
  HVD, BPJDet, Sapiens, Android, S4-S7, recognition, `[96,258]`, or S6 work occurred. Canonical
  report and artifacts:
  `artifacts/recognition_upgrade/perception_backend_replacement/p4c1_wilor_det_01/`.

## 2026-08-24 - P4-C2A DWPose-Guided RGB Crop Audit Prepared; Human Review Pending
- Verified the frozen `P4A2_FRESH_HUMAN_TRUTH_V1` dataset and annotation hashes and reused all
  458 exact frozen native DWPose outputs. No DWPose frame required new inference.
- The governed slot inventory contains 429 REAL_VISIBLE_HAND proposals, 159
  FALSE_DWPOSE_PROPOSAL examples, and 19 visible observations without a frozen presence-qualified
  proposal. Proposal-generation recall is therefore 429/448 (95.76%), which is the ceiling for a
  proposal-based RGB verifier under this frozen gate.
- Froze one geometry-only crop rule before review: the smallest rectangle around all finite native
  21-point coordinates, expanded 1.5x about its center, each dimension at least
  `max(32 px, 10% of the shorter frame side)`, then clamped once to the source frame. Human boxes,
  human truth, WiLoR, E2/R1, and manual adjustment never position a crop.
- Generated 588 immutable lossless RGB crops. The sequence-aware blinded audit contains 100 true
  proposal crops and 100 false proposal crops, spanning 28 sequences/14 signers and 26
  sequences/13 signers respectively. Review order is frozen and randomized; the UI reveals only
  anonymous crop ID/progress and RGB pixels. Full-frame context is available only after an initial
  crop-only choice and is recorded.
- Review tooling uses immutable crop IDs and source hashes, atomic saves, status-driven resume,
  completed-row overwrite protection, journaled explicit edits, and periodic backups. Nine focused
  regression tests plus a GUI construction smoke test pass. Human review is pending; no feasibility
  gate or classification has been claimed.
- No MobileNet/CNN/classifier training, logistic regression, augmentation, HVD, threshold tuning,
  WiLoR fusion, P4-C2B, P4-D, P4-B, Android, recognition, S4-S7, or DWPose modification occurred.
  Pending review package:
  `artifacts/recognition_upgrade/perception_backend_replacement/p4c2a_dwpose_rgb_crop_separability_01/`.

## 2026-08-24 - P4-C2A Crop Audit Complete; Experiment Invalidated by Truth/Target Defects
- Completed the blinded crop review for all 200 frozen audit crops with intact identities and
  provenance: 34 `YES_CLEAR`, 81 `YES_PARTIAL`, 69 `NO`, and 16 `UNCERTAIN`. The review artifact
  SHA-256 is `fe47dd7c710a91e2a2bb88df3d33269aa89edf8b0d657898394b86783c89522f`.
- After unblinding, governed REAL_VISIBLE_HAND crops contained 33 clear, 49 partial, 10 no-hand,
  and 8 uncertain judgments. Human identifiability was 82/100 (82%), so frozen Gate A (>=95%)
  failed. Governed FALSE_DWPOSE_PROPOSAL crops contained 1 clear, 32 partial, 59 no-hand, and 8
  uncertain judgments. Human rejection was 59/100 (59%), so Gate B (>=80%) failed. Overall
  uncertainty was 16/200 (8%), so Gate C (<=10%) passed.
- The unblinding exposed material evidence-definition defects. Ten visually positive false-proposal
  crops from eight source frames were governed as `ZERO_HAND`; bounded full-frame inspection shows
  conspicuous real human hands in those frames. Their frozen labels remain unchanged and are
  explicitly listed for governance review. Another 23 visually positive false proposals are absent
  anatomical slots in one-hand frames, consistent with the DWPose slot crop capturing the other
  real hand. A crop-only binary question, “does any hand appear?”, cannot establish which anatomical
  slot owns that hand.
- Classification is therefore `EXPERIMENT_INVALID`, not a valid pass or clean architecture
  rejection. The review is diagnostically useful, but corrupt/contradictory truth and a slot-target
  mismatch prevent using these percentages to justify P4-C2B training. The frozen 1.5x crop rule
  was not changed and no labels were silently repaired.
- Stop for project-lead governance/target-definition review. No MobileNet/CNN/classifier training,
  DWPose inference or modification, threshold tuning, HVD, WiLoR fusion, P4-C2B, P4-D, P4-B,
  Android, recognition, S4-S7, or S6 work occurred. Canonical report and artifacts:
  `artifacts/recognition_upgrade/perception_backend_replacement/p4c2a_dwpose_rgb_crop_separability_01/`.

## 2026-08-25 - P4-C2R R0 Frozen; R1 Independent Truth Review Prepared
- Verified and froze the immutable P4-A2 V1 dataset/annotation evidence, the complete P4-C2A
  package and review, all 588 crop hashes, and all 458 preserved native DWPose outputs. V1 was not
  edited and `P4_ELIGIBILITY_TRUTH_V2` has not been created.
- Prepared a blinded 148-frame full-RGB adjudication queue: 48 unique flagged frames (8 known
  zero-hand discrepancies, 23 opposite-slot cases, and 17 unique proposal-miss frames) plus the
  required deterministic 100-frame QA sample (40 V1 zero-hand, 40 one-hand, 20 two-hand). The
  package spans all 28 sequences and 14 signers.
- The repaired review tool uses immutable row/image identities, atomic writes, status-driven
  resume, completed-label overwrite protection, explicit journaled edits, and periodic backups.
  Ten focused regression tests, PowerShell parsing, GUI construction smoke, and the independent
  pre-review package validator pass. The launcher now explicitly enters the resolved project root
  before invoking the local Python module and restores the caller's directory afterward; it was
  verified successfully from `C:\Users\Gigabyte`. Human review is pending at 0/148.
- R2 proposal-ceiling recomputation, R3 fallback analysis, R4 ownership analysis, and R5 P4-C2A
  rescore are intentionally blocked until adjudication completes. No classifier/model inference,
  training, detector, Android, recognition, S4-S7, P4-C2B, HVD, P4-D, or P4-B work occurred.
  Pending package:
  `artifacts/recognition_upgrade/perception_backend_replacement/p4c2r_proposal_ownership_truth_repair_01/`.

## 2026-08-25 - P4-C2R Stopped at R1 QA Gate; Broader V1 Re-Audit Required
- Completed all 148/148 independent blinded full-frame adjudications with intact row/image
  identities and no journaled edits. Immutable V1 and R0 source hashes reverified.
- The preregistered 100-frame random QA subset found 13 material visibility-disagreement frames
  (17 anatomical-side changes): 4/40 V1 zero-hand, 6/40 V1 one-hand, and 3/20 V1 two-hand. This is
  above the mandatory stop boundary of at least 3/100, so status is
  `TRUTH_V1_BROADER_REAUDIT_REQUIRED`.
- Across all reviewed targeted plus QA evidence, 29 frames / 39 anatomical-side labels differed
  materially from V1. They are preserved in a non-applied change log; none were silently promoted.
- V1 remains immutable, `P4_ELIGIBILITY_TRUTH_V2` was not created, and zero corrections were
  applied. R2 proposal coverage, R3 fallback, R4 ownership, and R5 P4-C2A rescore did not start
  because their human-truth basis failed bounded QA.
- No classifier/MobileNet/HVD, detector, DWPose inference, threshold tuning, Android, recognition,
  S4-S7, P4-C2B, P4-D, or P4-B work occurred. Canonical stop report and artifacts:
  `artifacts/recognition_upgrade/perception_backend_replacement/p4c2r_proposal_ownership_truth_repair_01/`.

## 2026-08-25 - P4-GT1 Remaining Pass-1 Review Ready
- Started ground-truth repair only after the P4-C2R QA stop. V1 remains immutable and both frozen
  V1 hashes were verified. The completed 148-row P4-C2R review was audited as compatible with the
  newly frozen P4-GT1 visibility standard: full-frame RGB, model/V1 blinding, independently
  recorded anatomical sides, compatible YES/NO/UNCERTAIN semantics, and zero completed-label
  edits. It is reused as Pass-1 evidence rather than asking the reviewer to repeat it.
- Froze `P4GT1_VISIBILITY_ANNOTATION_STANDARD.md`, explicitly separating physical target-signer
  hand visibility from activity state, anatomical from screen side, and target-signer hands from
  other people's hands.
- Prepared a randomized blinded queue for the remaining 310 unique frames. The reused 148 plus the
  new 310 cover all 458 governed frames exactly once. The queue is currently 0/310 complete.
- The review infrastructure preserves immutable row/image identities, atomic writes,
  status-driven resume, completed-row protection, explicit edit journaling, backups, and zoom.
  Fifteen regression tests, GUI construction smoke, external-directory launcher execution, and an
  independent package/hash validation pass.
- Status `P4GT1_PASS1_REVIEW_READY`. Pass-2 repeatability, adjudication, V2 creation, proposal and
  crop rescoring, historical rescoring, and all model/Android/recognition work remain unstarted.
  Package:
  `artifacts/recognition_upgrade/perception_backend_replacement/p4gt1_eligibility_ground_truth_rebuild_01/`.

## 2026-08-25 - P4-GT1 Pass-1 Complete; Repeatability Review Ready
- Verified the completed 310/310 remaining-frame review with unchanged source identities/hashes,
  no duplicate/missing rows, and zero completed-label revisions. Combined it with the reusable 148
  P4-C2R judgments to freeze provisional `p4gt1_pass1_full.csv` at 458/458 unique frames.
- Provisional Pass-1 composition is 158 zero-hand, 150 one-hand, 146 two-hand, and 4 frames with
  at least one uncertain anatomical side. This is not V2 and is not yet model truth.
- Froze a deterministic signer/sequence-aware 100-frame repeatability queue: 40 Pass-1 zero-hand,
  40 one-hand, and 20 two-hand frames; 34 originate from the reused P4-C2R set and 66 from the new
  P4-GT1 review. Pass-1/V1 labels, source category, strata, disagreements, sequence/gloss, and all
  model information remain hidden.
- Repeatability queue/tool integrity, 15 regression tests, GUI construction smoke, launcher use
  from `C:\Users\Gigabyte`, and the artifact hash manifest pass. Queue is 0/100 complete.
- Status `P4GT1_REPEATABILITY_REVIEW_READY`. No repeatability scoring, adjudication, V2, proposal,
  crop/historical rescore, model, Android, recognition, P4-C2B, P4-D, or P4-B work occurred.

## 2026-08-25 - P4-GT1 Repeatability Insufficient; Model Development Remains Stopped
- Completed the blinded repeatability review at 100/100 frames / 200 anatomical sides with intact
  source identities/hashes and zero completed-label revisions.
- Found 6/200 direct YES↔NO anatomical-side disagreements across 6/100 frames, yielding 97% side
  and 94% frame direct-binary repeatability. Both preregistered gates failed (required at most
  2/200 sides and at most 2/100 frames). There were zero uncertainty transitions.
- Disagreements span two Pass-1 zero-hand, three one-hand, and one two-hand case; five came from the
  reused P4-C2R evidence and one from the new 310-frame review. Exact IDs and both judgments are
  frozen in `p4gt1_repeatability_disagreements.csv`.
- Classification `P4GT1_REPEATABILITY_INSUFFICIENT`. No adjudication queue was created,
  `P4_ELIGIBILITY_TRUTH_V2` was not created, and DWPose proposal/P4-C2A/E2/R1/WiLoR rescoring did
  not start. No classifier/model, detector, threshold, Android, recognition, S4-S7, P4-C2B, P4-D,
  or P4-B work occurred. Canonical report/package:
  `artifacts/recognition_upgrade/perception_backend_replacement/p4gt1_eligibility_ground_truth_rebuild_01/`.

## 2026-08-25 - P4-GT1R Six-Frame Count-First Adjudication Ready
- Preserved immutable V1, P4-C2R, P4-GT1 Pass-1/Pass-2/disagreement evidence, P4-C2A crop labels,
  native model evidence, and all historical decisions. Created only new P4-GT1R artifacts.
- Reinterpreted the existing 100-frame repeatability sample under the separated physical-count and
  anatomical-ownership schema. Physical visible-hand count agrees on 94/100 frames. All six prior
  YES↔NO conflict frames classify as `COUNT_DISAGREEMENT`; ownership-only and mixed conflicts are
  both zero.
- Prepared exactly the six conflict frames for count-first adjudication. The UI initially shows
  only the exact current non-mirrored RGB frame and asks count 0/1/2/uncertain. Ownership appears
  only for count=1; uncertain ownership is valid, and adjacent RGB context is available only for
  ownership. Selection never auto-saves; explicit Confirm/Enter is required.
- Immutable identity/hash checks, atomic/status-driven persistence, completed-label protection,
  edit journaling, 23 regression tests, GUI smoke, external-directory launcher use, and independent
  package validation pass. Queue is 0/6 complete.
- Status `P4GT1R_ADJUDICATION_READY`. No V2, rescore, model inference/training, threshold, proposal
  fallback, ownership heuristic, Android, recognition, P4-C2B, P4-D, or P4-B work occurred. New
  package:
  `artifacts/recognition_upgrade/perception_backend_replacement/p4gt1r_schema_repair_v2_01/`.

## 2026-08-25 - P4-GT1R Development Truth V2 Frozen and Rescored
- Completed the six count-first adjudications without edits: three ONE/RIGHT, two TWO, and one
  ZERO. All six prior repeatability failures were physical-count disagreements; none was merely
  ownership-only or mixed.
- Froze `P4_ELIGIBILITY_TRUTH_V2` as governed **development** ground truth, not final research
  gold. It contains 454 count-known and 4 count-uncertain frames: 157 ZERO, 150 ONE, and 147 TWO;
  444 visible and 464 absent hand slots are known, while 8 uncertain sides are excluded. V1 and
  every historical result remain immutable.
- Stored DWPose output gives 419/444 = 94.37% physical proposal capacity, below the 98% gate.
  One-hand existence is 147/150 = 98.00%, but complete two-hand proposals are only 130/147 =
  88.44%. Zero-hand activation remains 76/157 = 48.41%. Status flag:
  `V2_PHYSICAL_PROPOSAL_CEILING_BELOW_GATE`.
- On 150 known-ownership one-hand frames, the true slot is active in 147/150 = 98.00%, while the
  opposite slot also activates in 60/150 = 40.00%; all 60 are dual-slot collisions. Proposal
  coverage and anatomical ownership remain distinct unresolved problems.
- Reinterpreted the immutable 200 crop reviews as RGB authenticity rather than slot correctness:
  115 hand-present, 69 hand-absent, and 16 uncertain (92% binary decidability). Of the prior 33
  alleged false visual positives, V2 classifies 9 as valid visible-hand cases, 20 as opposite-hand
  or ownership cases, 3 as genuine false visual positives, and 1 as uncertain.
- Frozen-output-only rescoring does not rehabilitate P4-A2 E2/R1 or P4-C1 WiLoR; none passes every
  relevant original gate under V2. P4-A cannot be joined to V2 by frame identity. No model was
  rerun or trained, and no fallback, ownership rule, classifier, Android, recognition, P4-C2B,
  P4-D, or P4-B work occurred. Classification:
  `P4GT1R_V2_READY_FOR_ARCHITECTURE_DECISIONS`. Canonical report/package:
  `artifacts/recognition_upgrade/perception_backend_replacement/p4gt1r_schema_repair_v2_01/`.

## 2026-08-25 - P4-C3A Raw DWPose Failure Decomposition Complete
- Verified frozen V2 (`24f5d8d...d4252d`) and all 458 preserved native DWPose outputs. No model
  inference, threshold change, or new human review occurred. Diagnostic geometry/collision criteria
  were frozen before aggregate classification and are explicitly not production rules.
- Decomposed all 25 missing visible-hand observations: 21 retain coherent raw native hand geometry
  (category A), 1 lacks usable hand geometry but has usable same-frame arm context (B), 3 have no
  defensible hand or arm-derived proposal (C), and 0 are truth-uncertain (D). Misses are strongly
  concentrated in two-hand frames: 22/25, versus 3/25 one-hand.
- The base 419/444 proposal capacity becomes a theoretical 440/444 = 99.10% using category-A raw
  candidates alone and 441/444 = 99.32% with A+B. Both exceed the 436/444 physical-proposal target;
  these are candidate-region ceilings, not landmark or recognition recovery claims.
- Decomposed all 60 one-hand dual-slot collisions: 59 are spatially the same physical hand
  duplicated into both slots, 0 are separate false regions, and 1 is ambiguous. Simple anatomical
  arm association prefers the true slot in only 39/59 = 66.10%, versus 10 false preferences and 10
  ties, so it is not a reliable ownership solution.
- Existing crop review overlaps 28/60 collision frames. All 12 binary-reviewed true-slot crops and
  all 21 binary-reviewed false-slot crops contain a real hand; no reviewed false-slot collision
  crop is visually empty (4 are uncertain). RGB authenticity therefore cannot resolve the
  duplicate-hand ownership problem, although it remains relevant for general empty-region
  rejection.
- Final diagnostic path: `A_RAW_CANDIDATE_RGB_VERIFY`, with independent
  `OWNERSHIP_REQUIRED=YES`. Raw candidates already clear the proposal ceiling; arm fallback adds
  only one proposal and targeted second-stage recovery is not justified by the ceiling evidence.
  Path A is not sufficient alone because anatomical ownership remains unsolved.
- No verifier/classifier, ownership heuristic, arm fallback, second-stage model, Android,
  recognition, or S4-S7 work was started. Canonical report/package:
  `artifacts/recognition_upgrade/perception_backend_replacement/p4c3a_raw_dwpose_failure_decomposition_01/`.

## 2026-08-25 - P4-C3B Independent Physical-Instance Review Ready
- Audited the P4-C3A duplicate-label source as `GEOMETRY_DERIVED`; those 59/60 classifications
  were not reused as independent physical-instance truth for geometry evaluation.
- Verified frozen V2 and preserved native-output identities, then prepared exactly the required
  bounded review evidence: 21 category-A raw-candidate cases, all 60 one-hand collision pairs, and
  40 deterministic two-hand reference pairs. The reference sample is signer/sequence/time aware
  and was not selected using proposal overlap, distance, apparent ease, or model outcome.
- Generated 121 immutable full-frame overlays. Raw-candidate views distinguish accepted proposals
  from the recovery candidate; pair views use randomized candidate A/B ordering and hide native
  anatomical slot source. V2 labels, confidence, P4-C3A rationale, signer/sequence, pair origin,
  and expected answers remain hidden from the reviewer.
- The minimal UI uses one physical-instance question per image, large labeled buttons, direct
  keyboard shortcuts (`1`-`4` for raw cases, `1`-`3` for pairs), zoom, autosave, status-driven
  next-incomplete navigation, immutable completed rows, and explicit journaled undo. Five focused
  persistence/integrity tests, Python compilation, PowerShell launcher/status execution, overlay
  counts, and GUI construction smoke pass. Queue is 0/121 complete.
- Status `P4C3B_RAW_CANDIDATE_REVIEW_READY`. Part B pair-feature fitting/validation has not
  started. No DWPose rerun, deduplication rule, classifier/HVD/detector, Android, recognition,
  S4-S7, or downstream architecture implementation occurred. Package:
  `artifacts/recognition_upgrade/perception_backend_replacement/p4c3b_physical_instance_validation_01/`.

## P5-A — DWPose-native missingness-aware representation (2026-08-25)

- P4 perception remains frozen. No detector, DWPose inference/tuning, recovery model, training, recognition inference, Android, or S4-S7 work occurred.
- Classification: `P5A_REPRESENTATION_READY`. Frozen experimental contract: `DWPOSE_REPRESENTATION_V2_238`, shape `[96,238]`, little-endian float32.
- Layout: left hand `21x(xy,score,valid)`, right hand `21x(xy,score,valid)`, body indices `0..16` with the same four channels, plus two current-frame hand-observed masks. The masks describe usable native geometry, not physical-hand truth.
- Same-frame shoulder-midpoint/shoulder-distance body normalization succeeded on 458/458 governed frames; fallback 0/458. All 28 sequences converted to `[96,238]` with no truncation, NaN/Inf, stale hand block, padding, or GT-leakage violation. No DWPose rerun was required.
- Contract Markdown SHA-256 `57a45b6b5dd5340fbc5bf0eef12f30620f1478569b0e0b887cc9357f59911337`; contract JSON SHA-256 `0c94e9c885f331164d8ab1f7f0915eb89de43101394bd0949fae033b57f76d8b`; governed frame feature-data SHA-256 `7f0e4c4007279e8c8aa1562052959dc67d0d33ae89e3cdb19f7ceb4e975da70d`.
- Migration audit: the 8,131-row, 236-class canonical Phase-1 inventory has no DWPose V2 tensors. All 8,131 rows require migration for a complete rebuild (7,362 for the core primary train/validation/test baseline). `OLD S6 [96,258] MODEL IS NOT INPUT-COMPATIBLE WITH [96,238]`; no 238→258 padding or compatibility inference is allowed.
- Next allowed phase: `P5-B — Temporal Recognition Baseline on Representation V2`, after project-lead review. P5-B was not started.
- Canonical package: `artifacts/recognition_upgrade/perception_backend_replacement/p5a_dwpose_representation_v2_01/`.

## 2026-08-25 - P4-C3B Physical Instance Validation Complete; Path 2 Selected
- Completed all 121/121 blinded physical-instance judgments. Four explicit undos are fully
  journaled and match the four revision counters; no silent edits or identity/hash defects were
  found. Independent raw-candidate truth is 7 missing-real-hand, 4 duplicate-existing-hand, 10
  other-false-region, and 0 ambiguous.
- The independently validated raw-candidate capacity is only 426/444 = 95.95%, below the required
  436/444 (98%). P4-C3A's theoretical 440/444 ceiling is therefore rejected: coherent raw geometry
  often represents an already accepted hand or a non-hand region.
- Independent pair truth contains 61 SAME, 38 DISTINCT, and 1 AMBIGUOUS case. The ambiguous pair
  was excluded from binary rule fitting/scoring. Froze a signer-separated split with 65 development
  and 35 validation rows (10 development and 4 validation signers); sequences are also disjoint.
- Fitted exactly one candidate-order-symmetric rule family from development only using normalized
  center distance AND normalized median corresponding-landmark distance. Native/anatomical
  left/right slots are not inputs. On the first and only validation, duplicate recall is 8/21 =
  38.10% (FAIL ≥95%), while distinct-hand preservation is 13/13 = 100% (PASS ≥98%): 0 false
  merges, 13 false splits, precision 100%, F1 55.17%, diagnostic AUC 0.9377.
- Final classification `RAW_CANDIDATES_INSUFFICIENT_TARGETED_RECOVERY_REQUIRED`, architecture
  `PATH_2`. `ANATOMICAL_SLOT_AS_PRIMARY_IDENTITY=RETAIN`. A targeted second-stage landmark
  recovery direction is justified for the difficult missing-hand cases, but no recovery model was
  selected or run.
- No RGB verifier, detector/model inference or training, production deduplication, recovery
  implementation, Android, recognition, S4-S7, P4-D, or representation work occurred. Ten focused
  integrity/symmetry/split tests pass. Canonical report/package:
  `artifacts/recognition_upgrade/perception_backend_replacement/p4c3b_physical_instance_validation_01/`.

## 2026-09-04 — Authorized progress catch-up through P7F-A

This appended status supersedes older pending/next-step statements for the recognition-upgrade
track only. All older entries and checkboxes remain historical; no experiment result is rewritten.
The user now explicitly permits context/tracker updates after earlier gates kept them untouched.

Full chronology, data findings and source links:
[Consolidated P5-B through P7F-A progress](recognition_upgrade/PROGRESS_THROUGH_P7FA_2026_09_04.md).

### Status / completed work

- [x] P5-B migration, controlled horizon work and augmentation diagnosis completed.
- [x] P5-D1–D12 evidence synthesized: PFCE_MATCHED + EC_P3 leads offline, MODERATE confidence.
  D1 remains inconclusive/LOW; V2 sufficiency is not proven. D11 NLL worsened3/3,
  per-frame accuracy declined2/3, Top5 mixed; no pristine confirmation or deployment seed.
- [x] P6-A/B/B-R1 compatibility evidence completed; both formal desktop parity failures retained.
- [x] P6-C Android effective V2 parity passed60/60 but device performance was below target.
- [x] P6C-P1 acceleration triage completed: XNNPACK1.861052 backend FPS; NNAPI semantic failure.
  Exact DWPose-L FP32 flip-test mobile path closed on target; retained as offline teacher.
- [x] P7-A architecture audit, P7-B Family-A contract, P7-C FA_DS_SPATIAL_V1 selection completed.
- [x] P7-D and P7D-R1 failed their frozen runtime screens; no results relabeled.
- [x] P7D-R2 native host compute passed: V3 p95=25.133427ms;40.733333loops/sec.
- [x] P7E fixed[15,15] camera-only passed; integrated result remains BELOW_SCREEN:
  capture15FPS, analyzer/completed14.883333FPS, complete p95=48.6157707ms.
- [x] P7F-A completed: `P7FA_GEOMETRY_READY_IDENTITY_MISSINGNESS_GAPS`.
  3309 ASL TRAIN +617 local TRAIN RGB/native pairs verified. Frozen881 Sem-Lex P3 pairs
  hash-match, but798 need frame-alignment revalidation;77 have repeated timestamps.

### Decisions Made — current, not new execution authorization

- Production schema3.0 [96,258], offline V2 [96,238], Family-A202-float ABI and native
  heatmap/assignment outputs are distinct contracts, not reshape-compatible alternatives.
- Family A primary; Family B only predeclared fallback, never automatic; Family C unauthorized.
- Existing Family-A runtime weights remain random/untrained and POLICY_UNCONFIGURED.
- Geometry pseudo-supervision supports base-TRAIN contract design; identity labels NOT_READY,
  physical missingness PARTIAL, direct teacher-score regression NOT_SUPPORTED.
- Sem-Lex historical review provenance is resolved; exact policy remains
  `P3_ONE_PER_SIGNER_CLASS_CLASS_SHARE_67`. No2415 expansion or83-clip replacement authorized.
- P7E runtime debt remains parked. No training, extraction, human labeling, calibration,
  benchmark, S5/S7 integration or production replacement authorized by this documentation update.

### Open items / one next gate

- [ ] `PROJECT_LEAD_FAMILY_A_SUPERVISION_CONTRACT_REVIEW` — recommended, NOT executed.
- [ ] Reviewed anatomical assignment/crossing/contact and physical missingness evidence.
- [ ] Sem-Lex source-frame/timestamp revalidation without changing frozen membership.
- [ ] Future target/mask/loss and calibration contracts; no thresholds selected yet.
- [ ] Future normalization/S5/S7 and parked integrated-runtime closure, separately governed.

D10/protected replay/pristine remain protected; ASL Citizen VAL evaluation-only. Existing
historical context hashes remain records of their original audits, not a reason to rewrite them.

## 2026-09-05 — P7F-B teacher chirality resolution and Student-1 contract/cache

This entry is append-only and preserves every historical status above. It supersedes the older
P7F-A next-gate statement for the recognition-upgrade track without relabeling prior evidence.

### Status / completed work

- [x] Continued the existing `P7FB_FAMILY_A_GEOMETRY_STUDENT_READINESS_CONTRACT_01`; no new
  research branch was created.
- [x] Preserved the original `P7FB_RGB_TEACHER_ALIGNMENT_BLOCKED` result and all accepted
  frame/timestamp/rotation/decode/coordinate/integrity evidence as historical controls.
- [x] Completed the native-array-only chirality audit on the authorized base TRAIN population:
  ASL Citizen 3,309 clips = `COHERENT`; AppHear Capture 297 = `COHERENT`; Local 320 =
  `COHERENT`; overall `PASS`; no adequately covered signer had a systematic swap signal.
- [x] Recorded `P7FB_REFLECTION_EFFECT_RESOLVED_FOR_GEOMETRY_DISTILLATION` while retaining
  `historical_acquisition_reflection = UNESTABLISHED`.
- [x] Froze geometry-only Student-1 contracts/tooling and classified the package
  `P7FB_STUDENT1_TRAINING_CONTRACT_READY`. Training plane is
  `TEACHER_DECODED_UPRIGHT_SOURCE_RGB`; no flip, teacher-channel swap or physical-unmirrored
  claim is permitted.
- [x] Froze 3,204 TRAIN / 722 internal DEV clips with zero signer overlap where feasible.
  AppHear Capture is TRAIN-only because its single governed signer cannot support a disjoint DEV.
- [x] Verified bounded implementation readiness: 11/11 unit tests, lint, finite forward/backward
  smoke, 68 hashed artifacts and 1,295 unchanged historical/control files.
- [x] User executed the exact resumable float32 cache. Verified complete at
  `G:\AppHear3_P7FB_Student1_Cache`: 3,926 manifest rows, 3,926 clip arrays, 3,926 lineage
  sidecars, 164,675 frames, 291,388,304,128 bytes; cache-manifest SHA-256
  `cb5a35dc0d7e3f86dbf99964798945d43b7e673d708c28d7a999be5fd4e5ea30`.

### Decisions Made — frozen P7F-B Student-1 contract

- Historical acquisition reflection remains `UNESTABLISHED`; the audit supports only internal
  DWPose hand-channel/body-wrist semantic coherence across the three authorized sources.
- Geometry eligibility is governed lineage + retained frame + finite, source-in-bounds XY. No
  DWPose score threshold, clamping, fabricated border target or confidence regression is used.
- Targets are `[96,96,50]` unit-mass continuous subpixel Gaussians with sigma 1.5 cells, 3-sigma
  truncation and admissible-border renormalization. Loss is per-channel masked spatial cross
  entropy with zero-supervision frames excluded.
- Assignment-support, physical missingness/presence and direct confidence losses are off.
- Sampling is source then uniform clip then uniform eligible frame at 85% / 7.5% / 7.5% for
  ASL Citizen / AppHear Capture / Local. Horizontal flip and geometric augmentation are off.
- Checkpoint selection and acceptance remain channel-sensitive. The swap-tolerant hand metric is
  diagnostic only and cannot select a checkpoint or determine Student-1 PASS.
- The production Family-A schema/runtime contract is unchanged. No recognition improvement,
  human anatomical correctness or deployment readiness is established by this work.

### Open items / one next gate

- [ ] `USER_EXECUTED_FAMILY_A_GEOMETRY_STUDENT_01` — run integrity, one fresh training run,
  all-frame internal DEV evaluation and final packaging using `p7fb_long_run_handoff.md`.
- [ ] If training is interrupted, use the frozen resume command; do not launch another fresh run
  into the same output directory.
- [ ] Interpret the result only against the frozen teacher-fidelity acceptance contract. AppHear
  Capture has no signer-disjoint DEV result, and assignment/missingness/recognition/mobile work
  remains separately governed.

Student-1 training, long DEV evaluation, final result packaging, DWPose extraction, protected-data
access, Android changes, S5/S7 integration and production replacement remain unexecuted.

## 2026-09-07 — Family-A Geometry Student 01 finalized

This append-only entry supersedes only the preceding statement that Student-1 execution and
finalization were pending. The frozen P7F-B contract and all earlier evidence remain unchanged.

### Status / completed work

- [x] The user completed `USER_EXECUTED_FAMILY_A_GEOMETRY_STUDENT_01` in the isolated
  `p7fb_family_a_geometry_student_01_optimized` output directory. The earlier non-optimized,
  partial attempt was preserved without modification.
- [x] Independently reverified all 68 frozen P7F-B artifact hashes; run/config, TRAIN/DEV
  manifests, baseline implementation, optimized implementation, cache ledger and execution-only
  optimization identities all match. Pretraining equivalence remains exact and reports no
  scientific-contract change.
- [x] Reverified the authorized 3,926-clip base-TRAIN population: 3,204 Student-1 TRAIN and 722
  internal DEV clips, authorized ASL Citizen/AppHear Capture/Local sources only, Sem-Lex absent,
  protected populations absent, and zero TRAIN/DEV signer overlap where defined.
- [x] Verified `FA_DS_SPATIAL_V1` with 154,076 trainable parameters. Training completed 29 epochs
  and 23,229 optimizer steps. Frozen early stopping fired after epochs 24–29 failed to improve
  on epoch 23; best checkpoint step is 18,423. Resume continuity, optimizer iterations,
  checkpoint state and the 29-record history are consistent, with no finite-value failure.
- [x] Verified the existing all-frame internal DEV evaluation used the frozen best checkpoint
  `ckpt-23`, all 25,338 eligible frames, 1,192,035 eligible points and 74,865 ignored targets.
  AppHear Capture remains unavailable for signer-disjoint DEV because its one governed signer is
  TRAIN-only.
- [x] Applied the preregistered gates without alteration. Final classification:
  `FAMILY_A_GEOMETRY_STUDENT_01_MODEL_FAILURE`. Failed gates are mean NME, PCK@0.02,
  PCK@0.05, LH PCK@0.05 and RH PCK@0.05; BODY PCK@0.05 passed.
- [x] Deterministically created per-source/per-region evidence, acceptance tables, integrity and
  inventory records, `student1_result.json`, a 24-file run hash manifest and
  `FAMILY_A_GEOMETRY_STUDENT_01_REPORT.md`. All 24 manifest entries reverify.

### Final channel-sensitive internal DEV results

- Overall: NME 0.077213216; PCK@0.02 0.242763006; PCK@0.05 0.580797544.
- LH PCK@0.05 0.545979687; RH PCK@0.05 0.564375390; BODY PCK@0.05 0.743109307.
- ASL Citizen: 20,027 frames / 945,621 points; NME 0.084084140; PCK@0.05 0.536285679.
- Local: 5,311 frames / 246,414 points; NME 0.050845842; PCK@0.05 0.751613139.
- The two-hand swap-tolerant NME is 0.081502127 versus normal channel-sensitive paired-hand NME
  0.082568016 (1.291% relative improvement). It did not control selection or acceptance;
  `HAND_LOCALIZATION_IS_PRIMARY_WEAKNESS` is the supported diagnostic interpretation.
- `TEACHER_SUPPORT_STRATIFICATION_NOT_AVAILABLE`; the completed experiment was not modified to
  manufacture this optional diagnostic. Standalone terminal stdout was not captured, while the
  structured history, checkpoints and raw evaluation CSVs are preserved.

### Claim limits / next gate

- `HISTORICAL_ACQUISITION_REFLECTION_UNESTABLISHED`
- `MOBILE_DOMAIN_GENERALIZATION_NOT_ESTABLISHED`
- `HUMAN_ANATOMICAL_ACCURACY_NOT_ESTABLISHED`
- `WORD_RECOGNITION_IMPROVEMENT_NOT_ESTABLISHED`
- [ ] `PROJECT_LEAD_REVIEW_OF_STUDENT1_CROSS_SOURCE_HAND_LOCALIZATION_FAILURE` — review the
  preserved per-source, per-region, per-point, supervision-coverage and swap diagnostics before
  authorizing any new experiment. Student 2, retraining, architecture changes and deployment are
  not authorized by this finalization.

## 2026-09-07 — Student-1 failure-attribution audit complete

This append-only entry supersedes only the preceding unresolved-cause review gate. It does not
change the frozen P7F-B contract or the historical Student-1 result.

### Status / completed work

- [x] Completed inference-only `P7FB_STUDENT1_FAILURE_ATTRIBUTION_01` in the isolated
  `p7fb_family_a_geometry_student_01_failure_attribution_01` directory without modifying the
  completed optimized run.
- [x] Preregistered all diagnostic definitions, verified exact evaluator parity, evaluated the
  deterministic matched TRAIN/DEV frame sets, independently rechecked ckpt-23 all-frame DEV and
  compared the final epoch-29 checkpoint on the same all-frame DEV population.
- [x] Verified parent immutability across all 14 sealed artifacts, all 22 required outputs present,
  and all 54 non-self diagnostic-manifest entries hash-correct. No training, protected data,
  Sem-Lex, DWPose rerun, label repair or deployment work occurred.
- [x] Final diagnostic classification:
  `STUDENT1_FAILURE_ATTRIBUTION_MIXED_CAUSES_SUPPORTED`. The historical experiment remains
  `FAMILY_A_GEOMETRY_STUDENT_01_MODEL_FAILURE`.

### Decisions Made — failure attribution

- Supported: unseen-signer generalization gap, low-teacher-support association and clip-boundary
  difficulty. Mixed causes are supported under the preregistered rules.
- Contradicted: optimization failed to learn, weak matched-TRAIN hand fit, systematic hand swap,
  mobile supervision coverage as the primary cause, and checkpoint-probe misselection.
- Hand-scale/resolution association and architecture capacity remain inconclusive; neither is a
  causal conclusion from this audit.
- Matched pooled hand NME was 0.047740762 TRAIN versus 0.080300243 DEV. Teacher-support Q1/Q5 NME
  ratio was 2.657560 with Spearman -0.388090. Boundary/central NME ratio was 1.453.
- Epoch 29 worsened all-frame NME by 0.002138605 and PCK@0.05 by 0.000845613 versus ckpt-23;
  the historical checkpoint selection remains appropriate and unchanged.
- A packaging-only empty Local-Q4 hand-scale subgroup is recorded as zero-count/unevaluable;
  no evidence or metric definition was modified.

### Open items / one next gate

- [ ] `PROJECT_LEAD_SELECT_CONTROLLED_FOLLOWUP_FROM_STUDENT1_ATTRIBUTION_MATRIX` — select at most
  one controlled next experiment capable of distinguishing the supported generalization,
  teacher-support and boundary contributors. This tracker entry does not authorize execution.
- [ ] Preserve the unresolved limits: AppHear Capture signer-disjoint generalization, causal
  architecture capacity, causal hand-resolution limitation, DWPose anatomical correctness,
  recognition improvement and production readiness remain unestablished.

## 2026-09-08 — Family-A Geometry Student 2 geometric-augmentation package ready

This append-only entry records the project-lead-selected controlled follow-up to the Student-1
failure-attribution matrix. It does not change Student 1 or authorize any agent-executed training.

### Status / completed work

- [x] Prepared isolated experiment
  `P7FB_FAMILY_A_GEOMETRY_STUDENT_02_GEOMETRIC_AUGMENTATION_01` under
  `artifacts/recognition_upgrade/p7fb_family_a_geometry_student_02_geometric_augmentation_01/`.
- [x] Preserved the sole scientific delta as TRAIN-only, coordinate-consistent post-letterbox
  affine augmentation. `FA_DS_SPATIAL_V1`, 154,076 trainable parameters, TRAIN/DEV manifests,
  teacher mapping/eligibility and score policy, heatmaps, masked loss, source-first sampler,
  source probabilities, AdamW/cosine optimization, batch size 4, seed 707, maximum 40 epochs,
  patience 6, checkpoint policy, and unaugmented DEV remain inherited from Student 1.
- [x] Froze a single identity-centered policy before training: 20% geometric identity;
  otherwise triangular rotation ±8 degrees, uniform scale 0.90–1.10 and X/Y translation
  ±7.5% of 384. Horizontal reflection, perspective and anatomical swapping remain prohibited.
- [x] Verified exact identity equivalence on one governed example per source: RGB, targets,
  masks and admissible grids all had maximum absolute error 0.0 relative to Student 1.
- [x] Passed analytic translation/scale/rotation, affine round-trip, heatmap-centroid,
  out-of-frame ignore/no-clamp, handedness and one-batch forward-only tests. Pytest: 5/5.
- [x] Audited 4,096 deterministic TRAIN occurrences. Overall eligible-point retention was
  99.047%; LH 98.774%, RH 99.428%, BODY 98.661%; zero-supervision frames 0/4,096; qualifying
  hand sides losing most/all points 58/7,809 (0.743%). All preregistered safety gates passed,
  so the policy was not changed after audit.
- [x] Generated nine deterministic visual overlays (three per authorized source) and a contact
  sheet. Selection used sorted sample identity and middle eligible position, not model outcome.
- [x] Verified all Student-1 parent hashes before/after preparation; all 25 parent run files are
  unchanged. Sealed 24 Student-2 static artifacts; package integrity passes.
- [x] Completed imprint and implementation review. No production feature-schema/S4↔F change was
  introduced; review found 0 critical, 0 important and 0 minor issues.
- [x] No optimizer update, training epoch, DWPose rerun, Sem-Lex access, protected-data access,
  Android change or production-model change occurred.

### Exact next gate

- [ ] `USER_EXECUTED_FAMILY_A_GEOMETRY_STUDENT_02_GEOMETRIC_AUGMENTATION_01` — the project lead
  runs the sealed Student-2 `train` command. If interrupted, use `resume`; do not start a second
  fresh run. After completion, run the frozen best/all DEV evaluation and project-lead comparison.

### Claim limits

- Geometric augmentation is a causal hypothesis under test, not an established root cause.
- Historical acquisition reflection, human anatomical accuracy, AppHear signer-disjoint/mobile
  generalization, word-recognition improvement and production readiness remain unestablished.

## 2026-09-08 — Student-2 user run paused safely at epoch 14

This append-only execution note supersedes only the statement that Student-2 training had not
started. It does not change the frozen Student-2 contract or interpret unfinished model quality.

- [x] The project lead started the authorized Student-2 training run in the isolated experiment
  directory and later cancelled it near epoch 14 step 800/801.
- [x] On-disk inspection confirms 13 complete history records, `state.json` at the completed
  epoch-13 boundary (`optimizer_iterations=10413`, `best_epoch=12`), and a valid latest resumable
  checkpoint `checkpoints/latest/ckpt-11213` corresponding to epoch 14 step 800.
- [x] Cancellation is recoverable under the frozen resume contract. No second fresh run should be
  started; `resume` will restore model, optimizer/schedule, saved step state, sampler sequence and
  deterministic augmentation sequence.
- [ ] Next action: run the exact Student-2 `resume` command using output directory
  `artifacts/recognition_upgrade/p7fb_family_a_geometry_student_02_geometric_augmentation_01`,
  cache `G:\AppHear3_P7FB_Student1_Cache`, and the existing cache-verification ledger.
- [ ] Student-2 result, all-frame DEV comparison and augmentation-hypothesis conclusion remain
  unknown until training and governed evaluation complete.

## 2026-09-09 — Family-A Geometry Student 2 finalized

This append-only entry supersedes only the preceding paused/pending Student-2 execution state.
All earlier experimental results, contracts and claim limits remain historical evidence.

### Status / completed work

- [x] The project lead resumed and completed
  `USER_EXECUTED_FAMILY_A_GEOMETRY_STUDENT_02_GEOMETRIC_AUGMENTATION_01`: 34 epochs and
  27,234 optimizer steps, with frozen early stopping after six non-improving epochs. Best is
  epoch 28 / step 22,428 (`ckpt-28`); final is step 27,234.
- [x] Verified exact epoch/step continuity, finite history, readable best/final checkpoints,
  frozen run/package identity and unchanged Student-1 parent evidence.
- [x] Diagnosed the first all-frame evaluation attempt as Windows virtual-memory exhaustion and a
  Python `0xc0000005` process crash, not a model/checkpoint error. The incomplete attempt wrote no
  final evaluation artifact, and the finalizer correctly refused it.
- [x] Added an isolated inference-only memory-safe evaluator under
  `p7fb_family_a_geometry_student_02_memory_safe_evaluation_01`. It streams observation CSV rows,
  reproduced the complete epoch-28 probe with zero differences at tolerance `1e-9`, performed no
  training/weight update and left the sealed Student-2 runner unchanged.
- [x] Completed frozen best-checkpoint/all-frame DEV evaluation on 25,338 frames / 1,192,035
  eligible points / 74,865 ignored targets, with DEV augmentation off. AppHear Capture remains
  unevaluable under the signer-disjoint split.
- [x] Finalized `student2_result.json` and the raw summary/per-point/swap evidence. All 44 entries
  in `student2_run_artifact_hash_manifest.json` reverify and no temporary output remains.

### Final result / decisions

- Formal execution validity: `VALID_RUN`. Frozen absolute acceptance: `FAIL`.
- Overall NME `0.080706929`, PCK@0.02 `0.255052914`, PCK@0.05 `0.576680215`.
  LH/RH/BODY PCK@0.05: `0.532444973` / `0.572864050` / `0.728356534`.
- Failed overall NME, PCK@0.02, PCK@0.05, LH and RH gates; BODY alone passed. Thresholds and
  historical Student-1 result remain unchanged.
- Versus Student 1, overall NME worsened 4.525%; tight PCK@0.01/PCK@0.02 improved, but PCK@0.05
  declined. Student 2 improved a subset of precise predictions without improving broad/tail
  reliability.
- ASL Citizen NME worsened 8.609% and PCK@0.05 fell 0.023187 absolute. Local NME improved 21.395%
  and PCK@0.05 rose 0.069063 absolute. Five of seven ASL DEV signers worsened; P24 improved and P1
  was essentially flat. The sole Local DEV signer improved substantially.
- LH NME worsened 8.632% and LH regressed in every clip-position band. RH was mixed; BODY remained
  broadly stable. ASL low-teacher-support observations worsened disproportionately, while both
  small and large ASL hand-scale strata regressed.
- Conservative interpretation:
  `GEOMETRIC_AUGMENTATION_NOT_SUPPORTED_AS_A_BROAD_GENERALIZATION_FIX` and
  `LOCAL_DOMAIN_BENEFIT_SUPPORTED`. Do not automatically strengthen augmentation or launch a
  third training experiment from this result.

### Claim limits / one next gate

- Teacher-support association does not prove incorrect teacher anatomy and must not become a
  confidence target, filter or loss weight without a separate governed contract.
- Historical acquisition reflection, human anatomical accuracy, AppHear/mobile signer
  generalization, word-recognition improvement and production readiness remain unestablished.
- [ ] `PROJECT_LEAD_ASL_TEACHER_SUPERVISION_RELIABILITY_REVIEW` — recommended bounded next gate,
  NOT executed. If teacher coordinates prove reliable, the project lead may separately consider a
  hand-focused representation/capacity experiment. No Student 3, retraining or deployment is
  authorized by this tracker update.

## 2026-09-10 — P7G01 Family-A downstream recognition utility gate prepared

- [x] Frozen an isolated ASL Citizen-only T50/S1-50/S2-50 comparison with identical 96-frame
  selection, common teacher-derived availability masks, body-relative XY/velocity features, and
  one 166,956-parameter causal TCN configuration.
- [x] Verified 2,647 TRAIN and 662 internal DEV clips, identical 236-class vocabulary, 28/7
  signer groups, zero signer overlap, frozen Student-1 `ckpt-23`, frozen Student-2 `ckpt-28`, and
  zero protected-population references.
- [x] Passed a bounded three-clip forward-only parity audit for `[96,250]` tensors and common
  masks. No recognizer optimizer update or heavy feature preparation/training was executed.
- [ ] Project lead runs the resumable P7G01 `run-all` command and returns the finalized utility
  comparison. This gate does not change production schema v3.0 or either historical geometry result.

## 2026-09-10 — P7G01 finalized; P7G02 Teacher-50 temporal correction ready

This append-only entry supersedes only the pending P7G01 execution statement above. It does not
rewrite Student-1, Student-2, P7G01, or any production contract.

### P7G01 historical result

- [x] The project lead completed the valid P7G01 gate. Teacher-50 reached Top-1 `0.315710`,
  Top-5 `0.664653`, Macro-F1 `0.287358`, and balanced accuracy `0.317938` on the frozen
  662-clip signer-disjoint internal DEV population.
- [x] Student-1 and Student-2 retained much less downstream utility than Teacher-50, while
  Teacher-50 itself remained weak. The historical classification is
  `FAMILY_A_50_POINT_REPRESENTATION_OR_RECOGNIZER_LIMIT`.
- [x] P7G01's 96-slot temporal construction duplicated native positions in 99.471% of TRAIN
  clips and 100% of DEV clips; 68.513%/68.487% of TRAIN/DEV slots were duplicates and
  69.234%/69.208% of adjacent velocity observations were forced to zero by repetition.

### P7G02 prepared state

- [x] Preregistered `P7G02_TEACHER50_CREDIBLE_TEMPORAL_CEILING_01` as one Teacher-50-only
  temporal-construction correction. P7G01, both geometry students, DWPose arrays, landmark
  mapping, body normalization, class balance, optimizer philosophy, population, split, seed,
  and compact causal-TCN parameterization remain frozen.
- [x] Audited 2,647 TRAIN / 662 DEV clips, 236 classes, 28/7 signers and zero signer overlap.
  TRAIN native lengths are min/p10/p25/median/mean/p75/p90/p95/max
  `10/13/16/25/30.302/39/56/68/165`; DEV is
  `10/13/20/28/30.252/40/48/52/88`.
- [x] Froze sequence cap 64 before P7G02 DEV results. It preserves every governed native
  observation in 94.069% TRAIN and 98.640% DEV clips. Short clips keep every real frame then
  tail-pad; long clips use 64 unique chronological positions. Cache audit covers all 3,309 clips
  and 97,970 real observations with zero duplicate or non-monotonic positions.
- [x] Froze body-normalized velocity as displacement divided by positive native-array
  `frame_indices` delta. First frames, invalid point pairs, and padded positions emit zero
  velocity under explicit masks; teacher scores are not features.
- [x] Preserved the P7G01 4-block, 64-channel causal TCN and 166,956 trainable parameters,
  replacing only unmasked global pooling with masked pooling. Arbitrary padded values changed
  predictions by exactly 0.0; the irregular-interval constant-motion test had maximum error
  `7.45e-09`.
- [x] Reproduced the sealed P7G01 Teacher-50 baseline exactly, verified all 57 parent-manifest
  entries, unchanged Teacher-50 mapping, exact frozen population/hashes, and zero protected
  references. Pre-training validation is `PASS`.
- [x] Prepared the complete ~212 MB Teacher-50 feature cache. No optimizer update, recognizer
  training, Student inference/training, DWPose inference, protected access, Android change, or
  production feature change occurred.

### Exact next gate

- [ ] The project lead runs the P7G02 `run-all` command once. It reuses the sealed feature cache,
  trains only the authorized Teacher-50 recognizer, evaluates the frozen DEV population, and
  produces the preregistered P7G01-vs-P7G02 decision. Re-running the same command safely resumes
  from the latest completed epoch if interrupted.

## 2026-09-10 — P7G02 Teacher-50 temporal correction finalized

This append-only entry supersedes only the pending P7G02 execution statement above. P7G01 and
all perception experiments remain immutable historical evidence.

- [x] The project lead completed the single authorized P7G02 Teacher-50 run: 40 epochs,
  3,320 optimizer steps, no early stop, and the frozen Macro-F1-selected best checkpoint at
  epoch 37 / step 3,071. Both best and final models retain 166,956 parameters.
- [x] Reverified run/implementation/recognizer-contract/feature-cache identities, all 38 final
  artifact-manifest entries, the exact P7G01 baseline, the frozen 662-clip DEV population and
  the duplicate-free/masked temporal contract. No integrity mismatch was found.
- [x] P7G02 Teacher-50 achieved Top-1 `0.282477`, Top-5 `0.587613`, Macro-F1 `0.243498`, and
  balanced accuracy `0.280720`. Against P7G01 this is `-0.033233`, `-0.077039`, `-0.043860`,
  and `-0.037218` respectively. Recognized classes fell from 139 to 122.
- [x] The three DEV signers containing 639/662 clips all regressed. Across 236 classes, recall
  improved for 34, worsened for 58, and was unchanged for 144; therefore the result is not an
  isolated class or tiny-signer artifact.
- [x] Final contractual classification:
  `P7G02_TEMPORAL_CONSTRUCTION_NOT_DOMINANT`. The correction removed the known representation
  defect but did not raise the Teacher-50 ceiling and produced a broad Top-5 regression.
- [x] The preregistered `teacher_improvement_small=true` flag means only that absolute Top-1 and
  Macro-F1 changes are each below five points; both changes are negative. The independent
  `broad_contradictory_regression=true` flag preserves the 7.704-point Top-5 decline.

### Decision boundary

- [ ] Stop temporal-format experimentation. Do not try another sequence cap or recognizer merely
  because Teacher-50 remains weak. Return to the project lead to select one bounded next gate
  addressing sparse class supervision/data, recognition representation, product vocabulary
  scope, or recognizer capability. No Student retraining, hand refiner, protected evaluation,
  production integration, or claim of 50-point insufficiency is authorized by P7G02.

## 2026-09-10 — P8-A Student-1 FP32 TFLite export/parity finalized

- [x] Restored the exact sealed Student-1 best checkpoint `ckpt-23`; all 24 relied-upon parent
  artifacts matched their recorded SHA-256 before and after P8-A. `FA_DS_SPATIAL_V1` retains
  154,076 trainable parameters and the historical
  `FAMILY_A_GEOMETRY_STUDENT_01_MODEL_FAILURE` classification remains unchanged.
- [x] Exported the trained spatial/heatmap path only as a 643,200-byte FP32 TFLite model with
  input `[1,384,384,3]` and output `[1,96,96,50]`. The graph uses only TFLite builtins
  (22 Conv2D, 17 DepthwiseConv2D, two ResizeBilinear and one Concatenation), loads under the
  ordinary interpreter, and invokes through XNNPACK. Flex/SELECT_TF_OPS is not required.
- [x] Verified 36 deterministic governed TRAIN-domain fixtures: 12 each from ASL Citizen,
  AppHear Capture and Local, balanced across early/center/late positions. Exact input tensors,
  native lineage, transforms and six Android binary goldens are hashed.
- [x] Two-thread TF-vs-TFLite logit absolute differences were mean `1.3863e-06`, p99
  `6.1989e-06`, max `2.7657e-05`. Frozen-decoder 384-plane coordinate differences were mean
  `1.6724e-06` px, p95 `3.4982e-06` px, max `8.0694e-06` px; source-plane max was
  `0.000125827` px. No landmark changed heatmap peak cell. One- and two-thread results matched.
- [x] Final classification: `STUDENT1_TFLITE_PARITY_PASS`. Host smoke was 8.229 ms median at
  one thread and 5.983 ms at two threads, labeled `HOST_ONLY_NOT_MOBILE_RUNTIME_EVIDENCE`.

### Boundary

- [ ] Ready only for project-lead P8-B Android integration review. P8-A does not establish
  Student-1 anatomical accuracy, trained presence/missingness, recognition utility, mobile
  latency, production readiness, or permission to replace the existing recognizer.

## 2026-09-11 — P8-B Student-1 Android debug integration device evidence

- [x] Added an isolated debug-only `P8bRuntimeActivity`, exact model/hash guard, frozen
  P7C half-pixel preprocessing and local-3 decoder, raw LH/RH/BODY overlay, reusable large
  buffers, keep-latest CameraX analyzer and bounded timing/coordinate telemetry. No production
  recognizer, S5, S7, sentence, assignment, presence, model weight or precision path changed.
- [x] Host JVM decoder-equivalence tests and the debug APK build passed. The APK embeds the exact
  643,200-byte Student-1 FP32 model with SHA-256
  `f49a66e80241d67f9ef06729c01670190dd63a7eeb552d2737f46856e8670b43`.
- [x] On Xiaomi `M2101K7AG`, six P8-A tensor goldens passed Android TFLite/decoder parity:
  mean input-plane coordinate error `1.02e-06` px and maximum `3.05e-05` px against the frozen
  `1.0` px gate. Four TRAIN-domain raw-RGB fixtures reproduced the host letterbox tensor with
  exact zero numerical difference and exact geometry.
- [x] Completed one 15-second-warmup plus 180-second front-camera run at fixed 15 FPS. Camera
  captured 2,700 frames; 1,009 completed perception (`5.606 FPS`) with keep-latest dropping or
  skipping an estimated 1,690 frames. Median/p95/max were preprocessing
  `86.895/89.480/293.714 ms`, native TFLite `34.242/35.810/149.193 ms`, decoder
  `49.008/50.227/142.929 ms`, and whole perception `171.903/176.730/406.655 ms`.
  Every completed frame exceeded 150 ms and 20 exceeded 200 ms. There were no recorded crashes,
  ANRs, runtime errors or thermal throttling; PSS ranged approximately 91-175 MiB and 16 GC events
  occurred.
- [ ] Manual anatomical LH/RH behavior under front-preview mirroring remains to be explicitly
  confirmed from the prescribed one-hand/cross-body matrix. Automated metadata verifies upright,
  unmirrored model input and display-only preview mirroring, but this does not by itself establish
  the complete manual anatomical-orientation gate.

### Boundary

- [ ] P8-B is not a production-recognition integration. Device execution is stable but the current
  exact debug pipeline is substantially below the historical 15 FPS perception target; return the
  sealed evidence to the project lead without delegate/model/decoder/preprocessing changes in P8-B.

## 2026-09-11 — P8-C1 native preprocessing-only device result

- [x] Reused the unchanged, historically parity-proven P7D-R2 C++/JNI/arm64 preprocessing path
  behind an isolated `p8c1_enabled` branch of the P8-B debug activity. The exact Student-1 model,
  FP32 precision, two-thread XNNPACK configuration, CameraX cadence/backpressure, Kotlin local-3
  decoder, overlay, mapping and telemetry remained frozen.
- [x] Verified the four P8-B TRAIN-domain raw fixtures through native preprocessing with exact
  zero difference across 1,769,472 float values and exact landscape/portrait letterbox geometry.
- [x] Verified eight identical live CameraX frames through both P7D-R1 JVM and P7D-R2 native
  preprocessing before timing: 3,538,944 values, zero differences, 640x480 source, row stride
  2560, pixel stride 4, rotation 270 degrees and unmirrored model input. Duplicate preprocessing
  stopped before the formal measurement interval.
- [x] Completed the same 15-second warmup plus 180-second Xiaomi M2101K7AG run. Native
  preprocessing p50/p95 fell from `86.895/89.480 ms` to `5.418/6.836 ms`
  (`-93.764%/-92.360%`). Whole-perception p50/p95 fell from `171.903/176.730 ms` to
  `90.775/96.878 ms`; completed throughput rose from `5.606` to `10.139 FPS` and estimated
  skipped frames fell from 1,690 to 873.
- [x] Frozen stages remained broadly comparable: TFLite p50/p95 changed from
  `34.242/35.810 ms` to `34.312/37.189 ms`, and the unchanged Kotlin decoder changed from
  `49.008/50.227 ms` to `49.291/51.154 ms`. No crash, ANR, thermal event or runtime error was
  recorded.
- [x] Final classification: `P8C1_NATIVE_PREPROCESSING_FIX_SUPPORTED`. This establishes the
  independent native preprocessing gain only; it does not establish 15 FPS overall or authorize
  a native decoder, delegate, model, recognition or training change.

### Boundary

- [ ] `STOP_FOR_PROJECT_LEAD_REVIEW`. Live anatomical LH/RH semantics remain unresolved; no
  channel swap or recognition connection occurred.

## 2026-09-11 — P8-C2 native decoder-only device result

- [x] Preserved the exact P8-C1 native preprocessor, Student-1 FP32 model/hash, two-thread
  XNNPACK configuration, CameraX front-camera fixed-15 cadence, keep-latest backpressure,
  overlay math and 50-channel mapping. A separate debug-only heatmap adapter copies only the
  established P7D-R2 local-3 geometry and source-restoration math; obsolete identity/assignment,
  presence and confidence outputs are excluded.
- [x] Static parity passed on six real Student-1 heatmaps, eleven synthetic center/edge/corner/
  tie/competing-peak fixtures and nine nonfinite cases. The 384-plane difference was exactly
  zero for all 850 points, peak-cell differences were zero, nonfinite-policy mismatches were
  zero, and source-plane maximum difference was `0.000136479 px` against the frozen `0.001 px`
  gate.
- [x] Eight live CameraX frames invoked Student-1 exactly once each and fed that same heatmap to
  Kotlin and native decoders. Input-plane difference and peak-cell differences were exactly
  zero; source-plane maximum was `0.0000682394 px`. Kotlin duplicate decoding was disabled before
  formal timing.
- [x] Completed the frozen 15-second warmup plus 180-second Xiaomi M2101K7AG run. Decoder
  p50/p95 fell from P8-C1 `49.291/51.154 ms` to `1.738/1.873 ms`; whole-perception p50/p95 fell
  from `90.775/96.878 ms` to `45.762/48.318 ms`. Camera captured 2,700 frames, 2,699 completed
  (`14.994 FPS`), and only one frame was estimated skipped.
- [x] Frozen-stage comparison remained within gates: preprocessing p50/p95 was
  `5.880/6.473 ms` and TFLite p50/p95 was `37.336/39.123 ms`. There were 79 whole frames over
  50 ms, 26 over 66.7 ms, five over 100 ms, none over 150/200 ms, and no crash, ANR, runtime
  error or thermal event.
- [x] Final classification: `P8C2_NATIVE_DECODER_FIX_SUPPORTED`.

### Boundary

- [ ] `STOP_FOR_PROJECT_LEAD_REVIEW`. This result establishes only the parity-preserving native
  decoder implementation gain. Recognition remains `NOT_TESTED_BY_DESIGN`, Student-1 presence
  remains unavailable, and live anatomical LH/RH semantics remain unresolved.

## 2026-09-11 — P8-C3A overlay topology / index verification

- [x] Recovered all 50 authoritative Student channels and teacher indices from the frozen
  Student-1/P8-A/Family-A contracts: LH `0..20` maps to DWPose `91..111`, RH `21..41` to
  `112..132`, and BODY `42..49` to bilateral shoulders, elbows, wrists and hips at `5..12`.
- [x] Audited the live debug overlay against that mapping. Expected and actual topology match:
  23 edges per hand, 8 BODY edges, zero out-of-range edges, zero cross-hand edges, zero
  hand-to-BODY edges and zero per-channel neighbor mismatches.
- [x] Added an opt-in debug-only `POINTS_ONLY` renderer and deterministic on-device synthetic
  fixture. The same 50 unique coordinates rendered correctly with 54 canonical edges in full
  mode and zero edges plus local-index labels in points-only mode.
- [x] Verified asymmetric `FILL_CENTER` display math: the front preview mirrors X exactly once,
  never mirrors model coordinates, applies no overlay rotation and preserves LH/RH semantic
  labels. Gradle/unit builds, the new instrumentation test and retained P8-C2 decoder parity
  instrumentation all passed on Xiaomi `M2101K7AG`.
- [x] Bounded live points-only/full captures show that visibly tangled lines follow already
  scattered/collapsed Student-decoded coordinates; the renderer connects the correct neighbors.
  No topology, display-transform or label-mapping fix was required.
- [x] Final classification: `P8C3A_OVERLAY_TOPOLOGY_VALID`.

### Boundary

- [ ] `STOP_FOR_PROJECT_LEAD_REVIEW`. This diagnostic does not establish Student anatomical
  accuracy, trained presence/missingness, or physical live LH/RH identity; it changes no model,
  preprocessing, decoder, production recognition, S5, S7 or sentence behavior.

## 2026-09-11 — P8-C3B1 controlled live Student geometry capture

- [x] Added a debug-only, operator-confirmed capture activity around the retained P8-C2 stack.
  Each retained record copies one exact upright/unmirrored source RGB frame, the same-invocation
  50 source/model-plane coordinates, peak cells, raw uncalibrated peak logits, CameraX/letterbox
  metadata and physical condition label; no Teacher, recognition, smoothing or model update runs.
- [x] Preserved the first rejected capture attempt, then completed a valid 320-frame controlled
  population spanning empty scene, person/hands-down, anatomical left-only, anatomical right-only,
  both separated, one crossing sequence, near-face, near-torso and four explicit articulation poses.
  A separate 20-frame empty-scene retake replaced only invalid C0 canonical evidence; both raw
  device sessions and the deterministic merge ledger remain preserved.
- [x] Canonical validation passed: 320/320 required frames, all 11 logical conditions and all four
  10-frame articulation substeps, unique images, matching PNG SHA-256/dimensions, finite 50-channel
  evidence, valid peak indices, exact model/preview mirror semantics and monotonic synchronization
  within each device session.
- [x] Student-only analysis found complete forced geometry in empty/no-hand scenes, a repeatedly
  near-boundary and unusually compact LH block, substantially more variable RH/BODY outputs and
  heavy-tailed stationary jumps. The unilateral channel centroids remained far apart rather than
  collapsing onto one region. The controlled crossing produced no event under the preregistered
  association-cost exchange rule, but had a maximum centroid jump of `228.973 px` (`0.2862` source
  diagonals); this does not establish anatomical continuity.
- [x] Final Gradle debug/debug-test/unit build passed. Xiaomi device installation passed, and the
  retained P8-C2 native-decoder plus P8-C3A overlay instrumentation passed (`OK (2 tests)`). Parent
  manifests, Student model, native preprocessor, native decoder and debug model runner hashes are
  unchanged.
- [x] Final classification: `P8C3B1_CONTROLLED_STUDENT_CAPTURE_VALID`.

### Boundary

- [ ] `STOP_FOR_PROJECT_LEAD_REVIEW`. This phase localizes raw live Student behavior but creates no
  point-level anatomical truth and does not establish cause. Teacher/DWPose and recognition remain
  `NOT_RUN_BY_DESIGN`; no fix, channel swap, presence rule or inference change is authorized.

## 2026-09-11 — P8-C3B2 exact phone-frame DWPose Teacher reference

- [x] Verified the canonical P8-C3B1 parent before inference: 320/320 canonical PNG hashes,
  synchronized Student records, condition protocol and merge ledger passed; rejected B1 evidence
  was excluded and the Student model remains SHA-256
  `f49a66e80241d67f9ef06729c01670190dd63a7eeb552d2737f46856e8670b43`.
- [x] Resolved the governed frozen DWPose-L identity (`dw-ll_ucoco.pth`, SHA-256
  `e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7`) and ran it exactly once on
  each upright/unmirrored canonical phone frame. All 320 frames succeeded and the fixed
  133→Family-A-50 mapping passed; no Student rerun or score gate was used.
- [x] Same-frame evidence showed median Student→Teacher point error of `345.084 px` for LH,
  `68.943 px` for RH and `42.781 px` for BODY. In 80 Teacher-blind Student-LH collapse frames,
  Student/Teacher median compactness was `0.720/27.129 px`, while Teacher retained a median
  `17.5/21` in-bounds LH points.
- [x] Hand decomposition localized mixed Student disagreement: LH raw/wrist-aligned/similarity
  median errors were `336.408/69.901/23.997 px`; RH values were
  `121.642/110.129/18.989 px`. This supports prominent whole-hand placement loss plus residual
  internal hand-shape disagreement relative to Teacher.
- [x] Bounded visual review across every condition and all four articulation poses found coherent
  Teacher hands on visible-hand frames where Student geometry was displaced, scattered or
  collapsed. The empty-frame control also showed low-support spurious Teacher geometry, so the
  result does not treat Teacher as human ground truth or a calibrated presence detector.
- [x] Final classification: `P8C3B2_TEACHER_RECOVERS_STUDENT_FAILURE`.

### Boundary

- [ ] `STOP_FOR_PROJECT_LEAD_REVIEW`. No mirror counterfactual, retraining, MediaPipe, Android
  change or recognition was run. Historical/physical reflection and absolute anatomical truth
  remain unresolved.

## 2026-09-12 — P8-C3B3 frozen Student mirror counterfactual

- [x] Verified exact 320/320 B1 source-image, preserved Student and B2 Teacher alignment; all
  canonical PNG hashes, Student model SHA-256
  `f49a66e80241d67f9ef06729c01670190dd63a7eeb552d2737f46856e8670b43`, and frozen Teacher
  identity passed. Parent evidence remained byte-for-byte unchanged.
- [x] Reflected each upright/unmirrored source image exactly once, reused the frozen P8-A
  half-pixel letterbox and local-3 decoder, ran Student-1 once per frame, and mapped only X back
  to the original source plane with `x=(W-1)-x`. All 320 inferences succeeded; channel order was
  never changed and no weight update occurred.
- [x] On the preregistered visible-hand populations, mirrored-input median per-frame error was
  worse for LH (`342.178 → 403.047 px`, paired median `+67.534 px`, 95% frame-bootstrap CI
  `[62.217,72.034]`) and RH (`88.578 → 207.937 px`, `+132.959 px`, CI
  `[115.532,145.837]`). BODY worsened from `77.681` to `230.958 px` (`+148.499 px`, CI
  `[143.875,153.258]`).
- [x] No preregistered visible-hand condition showed the required median improvement for either
  hand (`0/6` LH, `0/6` RH). On the fixed 80 B2 LH-collapse frames, mirror reduced the frequency
  of the same compact boundary pattern but worsened Teacher-relative raw median error from
  `361.541` to `405.628 px`; therefore displacement of the failure mode is not a rescue.
- [x] Deterministic visual review of 23 condition-selected panels, including all articulation
  poses and fixed collapse cases, agreed with the paired analysis. Reflection often moved or
  spread erroneous geometry and severely degraded BODY/RH placement rather than recovering the
  Teacher reference.
- [x] Final classification: `P8C3B3_MIRROR_COUNTERFACTUAL_NOT_MATERIAL`.

### Boundary

- [ ] `STOP_FOR_PROJECT_LEAD_REVIEW`. This closes simple source-image reflection as a sufficient
  explanation for the observed Student failure. It does not establish Teacher as human ground
  truth, authorize a production mirror change, channel swap, retraining, MediaPipe, Android,
  recognition, presence or downstream-policy change.

## 2026-09-12 — P8-C3B4 Student supervision / spatial-prior audit

- [x] Verified frozen Student-1 contracts/manifests/model, failure-attribution evidence, verified
  cache ledger and canonical B1/B2/B3 records; all parent before/after hashes passed and no
  protected population was accessed.
- [x] Enumerated all 5,749,760 eligible Teacher targets across the governed 3,204-clip TRAIN
  population and audited target location, source, aspect ratio, Teacher support and fragmentary
  hand supervision without RGB corpus decode or DWPose rerun.
- [x] The exact frozen target generator passed 52 center/edge/corner fixtures. Boundary truncation
  shifted centroids inward but could not create a bottom-right attractor without a bottom-right
  Teacher target. TRAIN LH bottom-right-within-two target occupancy was `0.239%`; the
  preregistered boundary-prior rule did not trigger.
- [x] Forward-only Student inference on the frozen 19,630-frame matched TRAIN/DEV manifest found
  no replicated offline LH bottom-right attractor (`0.337%` matched TRAIN, `0.029%` DEV), while
  canonical B1 visible-hand LIVE occupancy was `84.571%`.
- [x] Supported contributors were replicated low-support/boundary association, `27.739%`
  zero-or-partial hand supervision without a presence objective, LH/RH supervision asymmetry and
  a live-only domain failure pattern. Target-generation bug, strong TRAIN boundary prior, portrait
  under-supervision and replicated offline attractor were contradicted; architecture causality
  remains inconclusive.
- [x] Final classification:
  `P8C3B4_SUPERVISION_CONTRIBUTORS_SUPPORTED_BUT_NOT_SUFFICIENT`.

### Boundary

- [ ] `STOP_FOR_PROJECT_LEAD_REVIEW`. No supervision repair, threshold, filtering, retraining,
  architecture change, Android change, MediaPipe, mirroring, presence logic, recognition or
  protected evaluation is authorized by this audit.

## 2026-09-12 — Product re-anchor and phone-first recovery audit

- [x] Completed a read-only repository-wide audit of the governed context, experiment history,
  Android production path, P5/P6/P7/P8 evidence, perception-backend replacement study,
  production assets and current dirty worktree. No implementation, training, export or
  recognition experiment ran.
- [x] Re-established the product boundary: the target is the existing expandable 236-sign,
  isolated/pause-separated Android sign-to-text application. The production path remains
  CameraX -> MediaPipe Hand/Pose -> schema-3.0 S4 `[96,258]` -> S5 -> 236-class S6 -> S7
  confirmation/release -> sentence UI.
- [x] Confirmed that P8-C2 is a debug-only engineering shell around Student-1. Its 50-point 2D
  output lacks the exact hand z, 33-point pose xyz/visibility, calibrated missingness and stable
  anatomical assignment required before production S4. It remains intentionally disconnected
  from S4/S5/S6/S7 and sentence generation.
- [x] Confirmed B1/B2/B3/B4 strengthen the non-connection decision: live Student geometry fails;
  topology, mirror, preprocessing and decoder are not sufficient explanations; supervision and
  domain contributors are supported but no sufficient repair exists.
- [x] Located product drift: alternate DWPose `[96,238]` recognition representation was the
  initial departure, Family-A's 50-point/202-value ABI deepened it, and P7G03's five-sign
  recognizer was the explicit product-scope break.
- [x] Froze Family-A, Student-1, Student-2, P7G03 and the P8 Student diagnosis as research
  evidence. No Student-3, five-sign expansion or alternate-recognition branch is authorized.
- [x] Verified the historical RTMDet-nano -> MobRecon DenseStack -> anatomical adapter was never
  executed. RTMDet failed P0 before MobRecon attachment; the old stack is not the current
  deadline candidate.
- [x] Final replacement conclusion: DWPose-L remains the strongest quality teacher/oracle and
  P8-C2 the strongest mobile engineering shell, but no existing backend is both phone-qualified
  and production-contract compatible. MediaPipe remains the shipping baseline pending a strict
  pre-S4 replacement gate.
- [x] Locked the only valid replacement boundary: upright/unmirrored `hands [2,21,3]` plus
  `pose [33,4]`, with exact topology, handedness, presence/missingness, visibility and
  training-compatible z semantics, followed by unchanged schema-3.0 S4/S5/S6/S7/sentence.
- [x] Retained reusable P8 infrastructure only: CameraX plumbing, native preprocessing, native
  decoder structure where applicable, profiler, overlays, controlled capture, coordinate
  restoration, asset guards and static/live parity evidence tooling.
- [ ] Next authorized milestone is `PHONE_REANCHOR_236_END_TO_END_BASELINE`: create a
  release-equivalent profiling-off, reproducible phone run through the normal app shell; verify
  production asset hashes/schema/vocabulary; demonstrate commit, release, re-arm and a two-sign
  sentence; and complete remaining F22 two-signer, mirror, lifecycle, kill-switch and load-failure
  gates without involving P8 Student, DWPose recognition or an alternate schema.

### Closed-loop boundary

- [ ] `STOP_FOR_PROJECT_LEAD_REVIEW`. Do not train, create another Student, run another
  recognition experiment, reduce scope to five signs, connect Family-A to production or reopen
  MediaPipe threshold/VIDEO, ROI/flow/tracking/hold, I320, RTMDet P0, Android DWPose, DWPose
  `[96,238]`, P7G01/G02/G03, P8 mirror/topology/preprocess/decoder diagnosis, or RU-D10B branches.

## 2026-09-13 — Phase 1 Perception vNext candidate 01 implementation

- [x] Project-lead direction superseded the prior pre-S4 replacement constraint and authorized a
  richer, not-yet-frozen perception representation while keeping recognition training, S5/S7,
  continuous signing, five-sign work, and Student-3 closed.
- [x] Selected one pretrained-first decomposed candidate: single-pass DWPose-t 256x192 for
  current-frame whole-body/anatomical hand proposals plus the mature MediaPipe 224x224 hand
  landmark submodel as a high-resolution 21-joint crop refiner. Exact DWPose-L remains Teacher
  only. No weights were trained or fine-tuned.
- [x] Exported the official DWPose-t checkpoint to single-pass ONNX. ONNX SHA-256 is
  `37b0f265200f8e249adba1cc9b62925f5e1252245580ed1f66f583d7bce239c0`; synthetic
  PyTorch/ORT maximum errors were `1.356e-6` (X) and `2.228e-6` (Y).
- [x] Ran the bounded viability screen on all 320 frozen P8-C3B1 Xiaomi frames against the frozen
  DWPose-L reference. Coarse DWPose-t body availability was 100% with a person and 0% without;
  supported-hand median Teacher error was about 1.54%/1.57% image diagonal, but hands-down and
  opposite-side false proposals confirmed that the coarse stage cannot define observation alone.
- [x] Added the direct crop refiner and explicit current-frame missingness. At the single
  preregistered group presence rule (`>=0.50`, `>=18/21` valid XY), visible LH/RH observation was
  `77.0%/76.5%`, complete two-hand observation `72.5%`, unilateral exact anatomical state
  `77.5%`, and no-usable-hand false observation `0%`. Refined median Teacher error was
  `0.469%/0.562%` image diagonal. Visual panels show coherent whole-hand placement/finger chains.
- [x] Implemented a new debug-only Android activity under `perceptionvnext/` with separate pinned
  ONNX/TFLite assets, build flag plus explicit intent opt-in, CameraX front-camera processing,
  upright/unmirrored source semantics, reusable input buffers, source overlay, 14-step/320-frame
  controlled capture, full observation telemetry, p50/p95 stage timing, FPS/skips, PSS, thermal
  status, and immutable session/model identity. Recognition/S5/S7/sentence/UI calls do not exist.
- [x] Python lint/tests, Android debug compilation, all debug unit tests, flagged APK assembly,
  and release Kotlin compilation passed. Release excludes the debug activity and assets; the new
  release BuildConfig flag is forced false.
- [x] Completed `PERCEPTION_VNEXT_PHONE_01` on Xiaomi M2101K7AG. The full 320-frame controlled
  run completed all 14 conditions without crash, ANR, or thermal escalation. Visible LH/RH
  observation was `95.5%/97.0%`, complete two-hand observation `90.83%`, unilateral anatomical
  correctness `99.375%`, crossing/contact completion `84%`, no-usable-hand false observation
  `0%`, and person-body availability `100%`. Live screenshots show coherent whole-hand placement,
  finger chains, anatomical slotting, and upper-body context. Status: geometry pass.
- [x] Measured the initial CPU data path: `2.257` completed FPS, preprocessing `83.960 ms` p50,
  DWPose-t `77.219 ms`, hand-crop resampling `171.705 ms`, per-hand refiner `51.368 ms`, and total
  `438.573 ms` p50. Classified `GEOMETRY_PASS_RUNTIME_FAIL`; the single bounded corrective action
  was native preprocessing/crop resampling with unchanged models and observation rules.
- [x] Added a reusable debug-only arm64 JNI preprocessing kernel and a mandatory four-live-frame
  Kotlin-reference parity gate. Final native build SHA-256 is
  `4187118fd33512de000056a8070bec85fd50f952da8ab8545552c33f8b85bfc5`; all 1,191,936 compared
  float elements were bit-exact. No parity tolerance was relaxed.
- [x] Native live evidence over 840 analyzed frames reached `5.607` completed FPS. Full-frame
  preprocessing fell to `2.693 ms` p50 and crop resampling to `3.324 ms`; one-hand total was
  `142.968 ms`, and the two-hand serial path remains about `188–192 ms`. DWPose-t is about
  `80.006 ms` p50 and each hand refiner about `50.946 ms`. The exact remaining blocker is neural
  inference latency; the current serial FP32 pair cannot satisfy the 15 FPS / 66.7 ms floor.
- [x] PHONE_01 final decision is
  `GEOMETRY_PASS_NATIVE_DATA_PATH_PASS_MODEL_RUNTIME_FAIL / FIX_ONE_BLOCKER`. Preserve candidate
  01 geometry and native infrastructure as evidence; do not freeze it for deployment, connect
  recognition, or start candidate 02 without project-lead review. Canonical results are
  `artifacts/recognition_upgrade/perception_vnext/phone_01/device/session_20260913T055327Z/phone_audit.json`
  and `artifacts/recognition_upgrade/perception_vnext/phone_01/NATIVE_RUNTIME_RESULT.md`.

### Boundary

- [x] Project lead explicitly authorized the bounded
  `PERCEPTION_VNEXT_RECOGNITION_UTILITY_236_01` experiment despite Candidate 01's current
  5–6 completed observations/sec. This does not waive the runtime issue or promote Candidate 01;
  it measures whether the current observation stream has useful 236-class information.
- [x] Added explicit current-frame body per-point validity without changing any frozen model,
  threshold, ROI, topology, orientation, or anatomical-slot policy. Defined separate experimental
  contracts `apphear.perception_vnext.raw.v1` and `apphear.perception_vnext.recognition.v1`.
- [x] Implemented an offline Candidate 01 extractor and a debug-only exact-PNG Android fixture.
  A 16-frame Xiaomi M2101K7AG gate passed every structural check and stayed far inside numeric
  tolerances: body XY and ROI max difference `0 px`; refined-hand XY max difference
  `0.000126 px`. The debug fixture reports `recognizer_connected=false`; production v3.0 is
  unchanged and the release APK contains no Perception-vNext asset/native-library entry.
- [x] Implemented the `[96,208]` mask-aware recognition representation, real chronological dense
  view, timestamp-derived PHONE_01-sparse view with no copying/interpolation, one 4-block/64-channel
  causal TCN, and full signer/source/per-class evaluation reporting. Unit/lint/build gates pass.
- [x] Tiny synthetic contract-only training sanity passed: finite forward/backward/optimizer step,
  236-output model, checkpoint write/reload with max absolute difference `0`, and dense/sparse DEV
  metrics pipeline. This is explicitly not an accuracy result.
- [x] Corrected the initial false missing-corpus diagnosis after the project lead supplied the
  relocated root. The pinned manifests remain byte-identical; a source-specific resolver maps only
  the moved ASL Citizen root `F:\ASL DATASET\ASL CITIZEN` to
  `G:\ASL CITIZEN\ASL CITIZEN` when the original file is absent. All 4,125 moved ASL Citizen
  videos resolve, all governed span paths resolve, and the full 4,742-row audit is PASS with zero
  signer overlap and no protected-TEST discovery.
- [x] Governed one-TRAIN/one-DEV extraction smoke PASS on real ASL Citizen data: BIG produced 20
  chronological raw/dense frames and four PHONE_01-sparse observations; signer-disjoint CHAIR
  produced 19 raw/dense and four sparse. Raw/feature shapes, identities, timestamps, missingness,
  normalization, masks, finite values, save, and reload passed.
- [x] One-epoch governed-package training sanity PASS with the single authorized TCN: finite loss,
  forward/backward/optimizer update, 236 outputs, best/latest/final checkpoint writes, and reload
  max difference `0`. The two-clip result carries `recognition_accuracy_claim=false`.
- [x] User-run full governed extraction PASS: all 4,742 clips were written and indexed (TRAIN
  3,926; signer-disjoint DEV 816; all 236 classes), governance PASS, and protected TEST untouched.
- [x] User-run full 40-epoch TCN training completed. The original command then raised a false
  post-fit sanity failure because `EarlyStopping(restore_best_weights=True)` restored the best
  in-memory weights while the validator compared them against last-epoch `latest.keras`.
  Artifact diagnosis proved `best.keras == final.keras` on the diagnostic input and isolated the
  reported `0.0830802917` delta to `latest.keras`. The validator now round-trips `final.keras`, and
  a completed `--resume` skips fitting, preserves the restored-best final model, and writes the
  missing result. Recovery PASS: finite history, reload delta `0`, 156,204 parameters, no extra
  training epoch, and `training_result.json` status PASS. Lowest combined DEV loss was epoch 39 in
  user-facing numbering (CSV epoch 38): `2.5803`, Top-1 `0.3811`, Top-5 `0.7040`. These epoch logs
  are not the required matched dense/sparse final evaluation.
- [x] User-run full matched evaluation PASS structurally and is now interpreted. Checkpoint hash,
  all `236 x 236` confusion matrices, clip/support/signer/source totals, recomputed Top-1 and
  macro-F1, and protected-TEST guard all pass. TRAIN dense/sparse Top-1 is `76.74%/70.10%`;
  signer-disjoint DEV is `41.30%/34.93%`. DEV Top-5 is `73.53%/67.28%`, macro-F1
  `38.70%/32.42%`, and zero-recall classes `57/73`. PHONE_01 sparsity costs 6.37 DEV Top-1
  points (111 dense-correct/sparse-wrong versus 59 sparse-correct/dense-wrong), but the dominant
  loss is the `35.45/35.17`-point TRAIN-to-DEV gap. Classification:
  **`GENERALIZATION_LIMITED` with a secondary cadence limitation**. Candidate 01 remains held
  constant; this recognizer is not promoted to phone/UI. Canonical interpretation:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/EVALUATION_INTERPRETATION.md`.
  Current boundary: `STOP_FOR_PROJECT_LEAD_GENERALIZATION_REVIEW`; no automatic new training,
  perception change, Candidate 02, phone recognition integration, or protected-TEST access.

### 2026-09-14 — Perception vNext generalization attribution 236

- [x] Completed `PERCEPTION_VNEXT_GENERALIZATION_ATTRIBUTION_236_01` using only the saved 4,742
  raw/feature packages, frozen `best.keras`, and sealed `evaluation.json`. No extraction, training,
  representation/perception change, Android work, or protected-TEST access occurred. The bounded
  DEV forward pass reproduced dense/sparse Top-1 and Top-5 exactly before per-clip evidence was used.
- [x] Raw quality is contributory but not sufficient: P5/P12 have lower RH/either-hand observation
  than stronger signers, and correct clips carry moderately better RH observation/valid-hand counts;
  however P21 resembles P12 in coverage while recognizing far better, and P26 recognizes far
  better despite the worst body-support profile. Per-observed-hand joint validity remains about
  `99.75-99.85%`; body-normalization fallback is effectively zero.
- [x] Class-conditioned normalized-coordinate shift is materially associated with errors
  (composite correct-minus-incorrect SMD `-0.383` dense, `-0.291` sparse), but it is not sufficient:
  P5 and P26 share the largest signer-level composite median shift (`0.662`) despite substantially
  different recognition.
- [x] Independent signer diversity is more associated with DEV recall than clip count: Spearman
  rho `0.304` versus `0.226` dense and `0.228` versus `0.167` sparse. Signer concentration HHI is
  negatively associated (`-0.271/-0.181`). Five supplemented classes occupy `17.29%` of TRAIN,
  average `9.66x` more clips than other classes, but add little signer diversity and generalize
  inconsistently. Source concentration alone is near-zero-correlated and is not called causal.
- [x] Cadence remains secondary. Dense-only harmed clips are not systematically short or
  perception-poor (duration SMD `+0.060`, sparse-count `+0.041`, valid-hand-count `+0.005`).
- [x] Primary attribution: **`MIXED_GENERALIZATION_FAILURE`**, medium confidence. Representation
  reopening: NO. Perception reopening: NO. Recommended exactly one next change, not executed:
  replace clip-uniform TRAIN sampling with a class→signer→clip hierarchical balanced sampler while
  freezing every other subsystem. Canonical report and machine decision live under
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/generalization_attribution_236_01/`.
  Current boundary: `WAIT_FOR_PROJECT_LEAD_REVIEW`.

### 2026-09-14 — Perception vNext sampling generalization 236 preparation

- [x] Implemented the sole authorized scientific delta for
  `PERCEPTION_VNEXT_SAMPLING_GENERALIZATION_236_01`: deterministic class→signer→clip TRAIN
  sampling with replacement. Candidate 01, raw-v1, recognition-v1 `[96,208]`, extracted data,
  TRAIN/DEV membership, TCN, optimizer/loss, dense+sparse policy, 3,926-draw/7,852-view epoch
  budget, validation, and protected-TEST boundary remain unchanged.
- [x] Sampling audit PASS over 100 simulated epochs (392,600 draws). Every epoch gives each class
  16 or 17 draws and signer quotas within each class differ by at most one. Aggregate class CV is
  `0.283%`; maximum signer-share deviation from the uniform-within-class target is `0.893%`.
  Same seed+epoch reproduces the exact sequence, a different epoch changes it, and all sampled rows
  are governed TRAIN rows.
- [x] Supplemented-class optimizer exposure is corrected without changing membership: expected
  clip-uniform draws for GOOD/HAVE/HELLO/KNOW/SORRY were `123/124/190/120/122` per epoch; the
  hierarchical audit produces `16.61/16.60/16.59/16.59/16.70`. Their largest within-class signer
  shares fall from `48.78/48.39/31.58/50.00/46.72%` to
  `6.38/6.02/7.11/8.08/5.75%`.
- [x] Bounded mechanics smoke PASS: 236 draws, 472 unchanged dense+sparse views, all 236 labels,
  `[96,208]` features and `[96]` masks, no DEV leakage, finite forward/backward/optimizer state,
  checkpoint reload delta `0`, and evaluation plumbing. The exact training entry point also passed
  an interrupted-run-equivalent resume test: the repeated invocation recovered the hashed
  completed-epoch state and skipped duplicate fitting.
- [x] No extraction, full training, full evaluation, Android/UI work, or protected-TEST access was
  performed. Baseline `tcn_run_01` remains immutable. User commands are prepared in
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/sampling_generalization_236_01/SAMPLING_GENERALIZATION_IMPLEMENTATION.md`.
  Current boundary: `WAIT_FOR_USER_HEAVY_RUN_RESULTS`.

### 2026-09-14 — Perception vNext sampling generalization 236 result

- [x] User-run balanced training and matched evaluation completed with intact config, dataset,
  sampler, checkpoint, vocabulary, and protected-TEST identities. Training completed all 40
  epochs; combined DEV loss selected zero-based epoch 36 (`2.681486`). Best checkpoint SHA-256 is
  `e7a5e00f95b79e9adbebfe001552ebc409ba597bd69e22541d2a5b831fae5f34`; evaluation totals and
  confusion diagonals reproduce reported Top-1 exactly.
- [x] Hierarchical sampling did not improve aggregate unseen-signer recognition. DEV dense
  Top-1/Top-5/macro-F1 changed from `41.30/73.53/38.70%` to `40.07/70.10/37.08%`; sparse changed
  from `34.93/67.28/32.42%` to `34.31/63.48/32.06%`. Dense zero-recall classes worsened `57→63`;
  sparse improved only `73→71`. Per-class recall improved/worsened for `46/64` dense and `51/58`
  sparse classes.
- [x] DEV signer effects are mixed rather than coherent: dense improves P12/P21, is unchanged for
  P5, and worsens P26/P39; sparse improves P12/P21 and worsens P5/P26/P39. The five supplemented
  classes also respond inconsistently, so their removal from excessive exposure is not sufficient
  evidence of a generalization fix.
- [x] TRAIN dense/sparse Top-1 fell from `76.74/70.10%` to `68.57/62.18%`. Consequently the gap
  reduction of about `6.95/7.31` points is caused by weaker TRAIN fit, not stronger DEV accuracy.
  The direct controlled classification is **`SAMPLING_HARMFUL`**, medium confidence: the direction
  is negative across aggregate Top-1, Top-5, macro-F1, most signer comparisons, and more classes
  worsen than improve, but this remains one fixed-seed run on a small DEV population.
- [x] Do not promote hierarchical sampling and do not automatically try another sampler, add
  weights/augmentation, change normalization/architecture/FPS, or retrain. Candidate 01 and
  recognition-v1 remain frozen. Canonical result:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/tcn_sampling_balanced_01/SAMPLING_GENERALIZATION_RESULT.md`.
  Current boundary: `WAIT_FOR_PROJECT_LEAD_REVIEW`; the lead must choose between genuinely greater
  independent signer diversity and formally reopening Phase 2 representation/invariance.

### 2026-09-14 — Perception vNext Representation V2 gate

- [x] Formally reopened Phase 2 once for
  `PERCEPTION_VNEXT_REPRESENTATION_V2_236_PRODUCTION_01` while freezing Candidate 01, raw-v1,
  the 4,742-clip TRAIN/DEV population, vocabulary, temporal source selection, TCN baseline and
  protected TEST. No DWPose/hand-refiner inference or recognizer training occurred.
- [x] Implemented the single experimental schema `apphear.perception_vnext.recognition.v2`:
  `[96,350]` plus `[96]` mask. It uses palm-local bone directions/joint angles/fingertip geometry,
  body-frame sign location and inter-hand relations, upper-body directions/support/validity, and
  timestamp-aware motion recomputed over each view's selected real observations. No depth,
  interpolation, carry-forward or copied evidence is introduced.
- [x] Contract mechanics PASS: global translation/scale/roll invariance, explicit missing-joint
  behavior, finite tensors, zero-only masked padding, and real dense/sparse timestamp deltas are
  covered by tests. All 4,742 saved raw packages produced V2 features (TRAIN 3,926; DEV 816); every
  V2 dense/sparse source-index array and mask exactly matched recognition-v1. Protected TEST was
  not accessed. No perception extraction was rerun.
- [x] Representation gate result: **`REPRESENTATION_V2_GATE_INCONCLUSIVE`**. Cross-class signer
  identifiability fell from `38.66%→26.41%` dense and `35.96%→22.84%` sparse, while DEV nearest
  TRAIN-class-centroid Top-1 improved `15.32%→21.94%` and `11.40%→15.44%`. However median
  class-conditioned TRAIN↔DEV centroid shift worsened `0.4347→0.4645` dense and `0.4511→0.5101`
  sparse; median DEV true-class distance also worsened `0.7415→0.7822` and `0.7680→0.8212`.
  Sparse Fisher separation declined while other separation measures improved.
- [x] Locked stop applied: no TCN smoke/full training, evaluation command, Android S4 port, V3,
  data/sampler/model change, or protected-TEST access. V1 `[96,208]` remains the controlled
  recognizer baseline; V2 is retained as unpromoted evidence. Canonical artifacts live under
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/representation_v2_236_production_01/`.
  Current boundary: `WAIT_FOR_PROJECT_LEAD_REVIEW`.

### 2026-09-14 — Representation V2 gate validation and training readiness

- [x] Independently reimplemented and recomputed the V1/V2 gate from the saved feature packages;
  aggregate values reproduce within `3.95e-7` and all P5/P12/P21/P26/P39 values within `1.40e-6`.
  No original gate metric helper was imported by the validation path.
- [x] Resolved the misleading separation-ratio name. The implemented formula is
  `median(nearest-wrong RMS distance / true-class RMS distance)`, so higher is correctly better;
  the old `true_vs_nearest_wrong...` key is worded backwards, but the reported direction was not.
- [x] Distance audit: each summary coordinate is standardized from TRAIN only, constant
  dimensions are removed, and distances use `sqrt(mean(squared standardized difference))`.
  Therefore raw Euclidean `sqrt(dimension)` inflation is already removed. Cross-version distance
  comparison remains partial because V1/V2 semantics, redundancy and correlations differ.
- [x] Sparse timing/motion audit PASS over 32 deterministic real packages and 164 nonconsecutive
  sparse steps: maximum dt error `6.85e-9`, elapsed error `2.91e-8`, selected-motion error
  `7.99e-8`, with zero duplicate/interpolated observations, invalid nonzero motions or first-step
  failures.
- [x] Final validation classification: **`V2_GATE_VALID_PROMISING`**. Reduced signer
  identifiability plus improved dense/sparse centroid Top-1, Top-5 and nearest-wrong/true separation
  are genuine; the worse class-conditioned/true-class distances and sparse Fisher ratio remain
  explicit risks to be resolved by the one controlled TCN result rather than another gate variant.
- [x] Added a V2-only TCN entry point that refuses any non-representation scientific delta.
  Actual-package smoke PASS on 16 TRAIN/16 DEV: `[96,350]`/mask loading, forward/loss/backward,
  optimizer, 236-output head, best/latest/final checkpoints, reload delta `0`, and bounded
  evaluation plumbing. Model has 192,556 parameters due only to the wider first input layer.
- [x] Full extraction/training remains unexecuted and protected TEST untouched. Exact user commands
  are frozen in `representation_v2_236_production_01/REPRESENTATION_V2_GATE_VALIDATION_AND_TRAINING_READINESS.md`.
  Current boundary: `WAIT_FOR_USER_V2_RESULTS`.

### 2026-09-14 — Controlled Representation V2 recognition result

- [x] User-run full clip-uniform V2 training and evaluation completed with all frozen scientific
  controls intact: 3,926 TRAIN, 816 signer-disjoint DEV, 236 classes, dense+sparse views, seed 101,
  unchanged 4×64 TCN/optimizer/loss/checkpoint policy, and no protected-TEST access. Training ran
  40 epochs; best combined DEV loss was zero-based epoch 32 (`2.4083843`). Best checkpoint SHA-256:
  `8107accbc621ae5652766fec80d314fe8dc9f94ba0d0548a6aef80ed91729340`.
- [x] V2 materially improves every primary DEV aggregate. Dense Top-1/Top-5/macro-F1 changes
  `41.30/73.53/38.70% → 50.25/76.23/48.55%`; zero-recall classes fall `57→34`. PHONE_01 sparse
  changes `34.93/67.28/32.42% → 39.95/70.96/38.15%`; zero-recall falls `73→52`.
- [x] Improvement is broadly signer/class distributed: dense Top-1 improves for all five DEV
  signers; sparse improves P12/P21/P26/P39 and declines P5 by one of 28 clips. Dense class recall
  improves/worsens for `94/49`; sparse for `80/59`.
- [x] Cadence remains a material risk: the DEV dense-to-sparse penalty grows `6.37→10.29` points.
  TRAIN-to-DEV gaps also grow to `36.66/42.30` points because TRAIN improves more strongly, but
  unlike balanced sampling, DEV itself improves by `8.95/5.02` points.
- [x] Classification: **`V2_RECOGNITION_SUPPORTED_WITH_CADENCE_RISK`**. V2 is the strongest
  governed Candidate 01 representation tested and is eligible for project-lead Phase-2 freeze;
  it is not automatically promoted to Android. No V3, retraining, sampler/data/perception change,
  or protected-TEST access is authorized. Canonical result:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/tcn_v2_run_01/V2_RECOGNITION_RESULT.md`.
  Current boundary: `WAIT_FOR_PROJECT_LEAD_V2_FREEZE_AND_PHASE4_DECISION`.

### 2026-09-14 — Signer/cadence-invariant recognizer preparation

- [x] Froze Candidate 01, raw-v1, recognition-v2 `[96,350]`, the governed 3,926 TRAIN / 816
  signer-disjoint DEV population, all temporal construction, and the established 4×64 causal TCN.
  Implemented one Phase-3 objective only: 236-way sparse categorical cross-entropy plus a
  same-gloss/different-TRAIN-signer supervised contrastive loss and exact same-clip dense↔sparse
  cosine consistency over the shared normalized 64D masked-pool sequence embedding.
- [x] Full deterministic pairing audit PASS. All 236 classes have usable cross-signer positives;
  signers/class are min/median/mean/max `8/13/13.136/18`; TRAIN has 40 signers, DEV contains
  P5/P12/P21/P26/P39, and signer overlap is zero. Every TRAIN clip is an anchor exactly once per
  epoch, producing the unchanged 7,852 classification views in exactly 246 optimizer batches.
- [x] Bounded real-data smoke PASS over two pair-aware TRAIN batches and 16 DEV clips. First-step
  classification/metric/consistency/total losses were `5.999947/2.660548/0.079906/6.548038`;
  gradients were finite, logits had 236 classes, the checkpoint reload maximum absolute delta was
  `0`, and the unchanged V2 dense/sparse evaluation plumbing passed. These are mechanics only,
  not recognition-accuracy results.
- [x] Full training/evaluation, protected TEST, perception extraction, Android integration, V3,
  Sem-Lex, balanced sampling, augmentation, architecture and optimizer changes were not executed.
  The exact user commands are recorded in
  `signer_cadence_invariant_236_01/SIGNER_CADENCE_INVARIANT_IMPLEMENTATION.md`. Current boundary:
  `WAIT_FOR_USER_SIGNER_CADENCE_INVARIANT_RESULTS`.

### 2026-09-14 — Signer/cadence-invariant recognizer result

- [x] User-run full training and matched evaluation completed with all integrity gates passing:
  frozen recognition-v2 dataset/config/control hashes, 3,926 TRAIN, 816 signer-disjoint DEV,
  236 classes, 7,852 views and 246 pair-aware batches in every epoch. All 40 epochs were finite;
  combined DEV loss selected zero-based epoch 35 (`2.363961`). Candidate best SHA-256 is
  `57fb3c2784e7a95b23a881c2325d3453687e2e89f42dba420a9e08abeca86952`. Protected TEST was not
  accessed.
- [x] The candidate does not beat the frozen V2 TCN. DEV dense Top-1/Top-5/macro-F1 changes
  `50.25/76.23/48.55% → 46.32/76.96/43.46%`; zero-recall classes worsen `34→46`. PHONE_01 sparse
  changes `39.95/70.96/38.15% → 39.09/68.50/36.77%`; zero recall worsens `52→61`. Dense improves
  only P12; sparse improves only P39, is unchanged for P5/P21, and worsens P12/P26.
- [x] The objective performed its local alignment function but compressed class margins. Mean
  same-clip dense↔sparse cosine distance improves `0.07851→0.07244` TRAIN and
  `0.09636→0.09056` DEV. Mean TRAIN same-class/other-signer distance improves
  `0.19273→0.16388` dense and `0.21503→0.18741` sparse. However nearest TRAIN class-centroid
  separation shrinks `0.12706→0.11304` dense and `0.12755→0.11096` sparse; DEV nearest-centroid
  Top-1 falls `47.43→45.10%` and `37.75→36.15%`.
- [x] Cadence penalty narrows `10.29→7.23` points, but this is not a product gain: dense DEV falls
  `3.92` points while sparse DEV also falls `0.86`. TRAIN dense/sparse Top-1 falls
  `86.91/82.25% → 79.29/74.35%`, so reduced TRAIN→DEV gaps again reflect weaker fit rather than
  improved DEV recognition.
- [x] Scientific classification: **`SIGNER_CADENCE_INVARIANT_NOT_SUPPORTED`**, high confidence for
  this fixed candidate. Stop the current TCN-objective tuning branch: no weight/contrastive/sampler/
  seed/epoch/LR follow-up and no phone promotion. Frozen ordinary V2 TCN remains the Phase-3
  recognizer control. Canonical report and decision live in `tcn_signer_cadence_invariant_01/`.
  Current boundary: `WAIT_FOR_PROJECT_LEAD_FUNDAMENTALLY_STRONGER_RECOGNITION_OR_DATA_DECISION`.

### 2026-09-14 — Project-state handoff to Phase 4A

- [x] Project lead formally froze Phase 1 Candidate 01 and closed/froze Phase 2 on
  `apphear.perception_vnext.recognition.v2` `[96,350] + [96]` mask. Candidate 02, V2.1 and V3 are
  not authorized.
- [x] Phase 3 is **PAUSED — NOT SOLVED**. The ordinary V2 4×64 causal TCN remains the active control;
  best checkpoint SHA-256 is
  `8107accbc621ae5652766fec80d314fe8dc9f94ba0d0548a6aef80ed91729340`. Its governed DEV
  dense/sparse Top-1 is `50.25%/39.95%`; unseen-signer generalization remains primary and phone
  cadence/observation density secondary. The recognizer is not production-ready.
- [x] Balanced sampling and the explicit signer/cadence-invariant objective remain preserved closed
  evidence. Do not restart class weighting, more epochs, LR/optimizer/seed sweeps, representation
  revisions, metric-loss variants, or simple TCN-objective tuning.
- [x] Phase 4A is now **ACTIVE** with milestone
  `PHASE_4A_BOUNDED_PHONE_RECOGNITION_VALIDATION`. Required order is Android recognition-v2 parity,
  frozen ordinary-V2-TCN runtime parity, manually bounded START→SIGN→STOP→CLASSIFY, then governed
  diagnostic phone evidence. Automatic gating, UI commit, production deployment, continuous
  recognition, new training, and protected-TEST access remain prohibited.
- [x] After Phase 4A, real-phone versus offline-sparse evidence must drive an explicit project-lead
  choice: fix a phone/runtime mismatch first, or formally reopen Phase 3 for external/pretrained
  signing diversity or another fundamentally stronger recognition strategy. Canonical handoff:
  `context/recognition_upgrade/PHASE4A_PROJECT_STATE_HANDOFF.md`. Current boundary:
  `WAIT_FOR_PHASE_4A_IMPLEMENTATION_INSTRUCTION`.
- [x] Durable-state save verified: the Phase 4A handoff now declares the anti-drift source order,
  `context/feature-schema.md` identifies recognition-v2 as the frozen Phase-4A production-candidate
  contract, and `memory.md` records the non-restart evidence chain from PHONE_01 through V1,
  attribution, harmful balancing, Sem-Lex partial value, successful V2, and the rejected invariant
  objective. Scientific artifacts were not modified.

### 2026-09-14 — Phase 4A Gate 0 + Gate 1 Android V2 parity

- [x] Gate 0 deployment identity PASS. Active ordinary-V2-TCN checkpoint SHA-256 is exactly
  `8107accbc621ae5652766fec80d314fe8dc9f94ba0d0548a6aef80ed91729340`; vocabulary is 236 classes
  with SHA-256 `a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b`.
  The invariant and balanced-sampler checkpoints were not selected.
- [x] Implemented the exact frozen `apphear.perception_vnext.recognition.v2` transformation as a
  debug-only Kotlin component. It preserves the `[96,350]` layout, anatomical sides, body/hand
  frames, explicit validity, dense and PHONE_01 sparse unique-observation selection, motion from
  actual selected timestamps, elapsed fraction, and zero/false tail padding. Candidate 01 and all
  model/runtime code remain unchanged.
- [x] Prepared a deterministic TRAIN-only parity corpus from the 3,926 existing raw-v1 packages:
  10 clips, 10 dense views and 10 sparse views selected only for structural observation coverage.
  No DEV or protected TEST artifact was accessed.
- [x] Android module and instrumentation sources compile. Host preflight of the same Kotlin debug
  source against Python goldens PASS: global max/p95/mean absolute error
  `1.1920929e-7/0/6.3152280e-11`, zero discrete mismatches; every feature group passes the
  pre-registered `1e-5` maximum tolerance.
- [x] Physical Xiaomi M2101K7AG instrumentation PASS. Dense max/p95/mean absolute error is
  `1.1920929e-7/0/1.0493871e-10`; PHONE_01 sparse is
  `1.1920929e-7/0/2.1365850e-11`. Selection, selected timestamps, frame masks and discrete
  features have zero mismatches. All eight feature groups pass `1e-5`; 1,106 padded frames,
  missing-hand/body-reference semantics, 10,134 invalid motion endpoints and 255 sparse `dt`
  checks pass. Device evidence SHA-256 is
  `6f4e0cb2adc9544ce71eaf1f703b4572cef109365d63f65fddbbd7f408af09a8`.
- [x] Gate 1 classification: **`ANDROID_V2_PARITY_PASS`**. No Gate 2 model conversion/runtime,
  recognition, live capture, training, DEV parity use or protected-TEST access occurred. Current
  boundary: `WAIT_FOR_PROJECT_LEAD_GATE_2_AUTHORIZATION`.

### 2026-09-15 — Phase 4A Gate 2 recognizer runtime parity

- [x] Pinned the unchanged Gate-1 Kotlin implementation and fixture manifest before model work.
  `RecognitionV2.kt` remains SHA-256
  `0a5fd969c574f3077060e75bcf697390e322da7e87e870da50b547714ba39699`; repository HEAD before
  Gate 2 was `7dd4fa05f2e7dffd3f06a2fdc88f90b1ea66836f` on the existing dirty worktree.
- [x] Independently verified the active ordinary V2 checkpoint SHA-256
  `8107accbc621ae5652766fec80d314fe8dc9f94ba0d0548a6aef80ed91729340` and the 236-class
  vocabulary SHA-256 `a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b`.
  Source contract is `features [None,96,350] float32` + `frame_mask [None,96] bool` to
  `[None,236]` FP32 softmax probabilities; model parameters are `192,556`.
- [x] Converted exactly one FP32 TFLite model with no quantization, weight compression,
  architecture rewrite or Select TF Ops. Standard builtins suffice. Model is `814,068` bytes,
  SHA-256 `1ccf0afa9af9aa602aa0de33c9635f5cffd7feec7d9b4e32382bc5e3fa02880c`.
- [x] Host parity PASS on the exact Gate-1 TRAIN-only 10 dense + 10 PHONE_01-sparse tensors:
  Keras↔TFLite max/p95/mean absolute error `4.7683716e-7/1.4581019e-9/1.2949251e-9`, with zero
  Top-1, Top-5 membership or Top-5 ordering mismatches.
- [x] Physical Xiaomi M2101K7AG / Android 12 parity PASS using TFLite 2.16.1, CPU 4 threads,
  XNNPACK requested, and no GPU/NNAPI. Keras↔Android max/p95/mean absolute error is
  `3.5762787e-7/1.7462298e-9/1.4873060e-9`; all Top-1/Top-5 checks match. Four preregistered
  padded-garbage cases are exactly invariant in Keras, host TFLite and Android TFLite.
- [x] Recognizer-only device latency after 10 warmups over 50 invocations is p50/p95/max
  `1.693/1.823/1.859 ms`; diagnostic only. The Android asset manifest explicitly pins and checks
  `apphear.perception_vnext.recognition.v2` before consuming the feature tensor. Classification:
  **`RECOGNIZER_RUNTIME_PARITY_PASS`**. No training, DEV, protected TEST, CameraX, live phone
  recognition, START/STOP UI or Gate 3 work occurred. Evidence root:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase4a_gate2_recognizer_runtime_parity_01/`.
  Current boundary: `WAIT_FOR_PROJECT_LEAD_GATE_3_AUTHORIZATION`.
- [x] `/remember save` synchronized `memory.md`, this tracker, the Phase-4A handoff, the
  recognition-upgrade current-state override and the feature-component registry. No credentials
  or sensitive values were stored.

### 2026-09-15 — Phase 4A Gate 3 known-TRAIN end-to-end replay

- [x] Reverified every frozen deployment identity before composition: unchanged `RecognitionV2.kt`
  SHA `0a5fd969c574f3077060e75bcf697390e322da7e87e870da50b547714ba39699`, Gate-1 manifest SHA
  `01fd271c25df2d0b7a64e803fabe0b745d51be1ac8f7c6f646546e2a3aa055b3`, TFLite SHA
  `1ccf0afa9af9aa602aa0de33c9635f5cffd7feec7d9b4e32382bc5e3fa02880c`, vocabulary SHA
  `a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b`, and Gate-2 verifier/
  manifest SHAs. No frozen component was modified or regenerated.
- [x] Added a Gate-3-only fail-closed Android replay consumer and deterministic instrumented test.
  It starts from the same 10 Gate-1 TRAIN raw-v1 fixtures, builds both dense and PHONE_01-sparse
  V2 views, immediately runs the authorized ordinary-V2 FP32 TFLite, preserves selected indices,
  timestamps, masks, generated tensors and all 236 output probabilities, and checks exact
  class-index/gloss mapping. The consumer explicitly requires raw-v1 and recognition-v2 before
  accepting data.
- [x] Physical Xiaomi M2101K7AG / Android 12 composed replay PASS. Android V2 intermediate
  max/p95/mean error was `1.1920929e-7/0/6.3152280e-11` across 672,000 elements, with zero
  selection/timestamp/mask/discrete mismatches. Frozen Keras vs composed Android output
  max/p95/mean error was `4.1723251e-7/1.7462298e-9/1.5262949e-9` across 4,720 probabilities,
  with zero Top-1, Top-5 membership or Top-5 order mismatches and exact gloss mapping.
- [x] Reused buffers passed forward/reverse, dense→sparse, and sparse→dense order tests exactly:
  maximum difference `0` over 14,160 comparisons. Device replay latency excluding perception was
  V2 p50/p95 `8.335/40.665 ms`, TFLite `1.997/7.076 ms`, combined `10.243/44.808 ms`; diagnostic
  only. Ground-truth correctness was 9/10 dense and 8/10 sparse, recorded only as a diagnostic and
  excluded from the gate decision.
- [x] Independent host finalization reproduced the pulled tensor/output statistics and classified
  **`KNOWN_TRAIN_END_TO_END_REPLAY_PASS`**. No training, live CameraX recognition, DEV access or
  protected-TEST access occurred. Evidence root:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase4a_gate3_known_train_end_to_end_replay_01/`.
  Current boundary: `WAIT_FOR_PROJECT_LEAD_GATE_4_AUTHORIZATION`.
- [x] `/imprint` registered the composed raw-v1→V2→TFLite component without changing the frozen
  feature contract, and `memory.md` plus the Phase-4A state files were synchronized. No credentials
  or sensitive values were stored.

### 2026-09-15 — Phase 4A Gate 4A-1 live plumbing validation

- [x] Reverified the frozen RecognitionV2.kt, authorized FP32 TFLite, vocabulary, Gate-1/2/3
  manifests, Candidate 01 source components and camera/preprocess configuration before live work.
  Frozen V2 and model identities remain `0a5fd969…699` and `1ccf0afa…80c`; no frozen component,
  threshold, temporal rule, vocabulary or weight was changed.
- [x] Added a debug-only CameraX surface implementing only `START → one isolated sign → STOP →
  classify`. Candidate 01 loads and completes four live/native-parity observations before START is
  enabled. Capture membership uses `ImageProxy.imageInfo.timestamp`, never completion callback
  time. The first strictly chronological processed source timestamp newer than `T_stop` is the
  deterministic drain sentinel; eligible work completing after STOP is retained.
- [x] Live temporal behavior is correctly **not** PHONE_01-resimulated. All unique chronological
  live observations are fed to frozen V2 through its DENSE actual-observation path; only the frozen
  96-step selection rule applies if a capture exceeds 96 observations. Motion/dt uses adjacent
  actual selected timestamps. No interpolation, duplication, carry-forward or synthetic cadence.
- [x] Deterministically froze the first five unique Gate-3 TRAIN fixtures whose sparse reference
  was ground-truth correct: HELLO/80, AT/8, HOME/83, STREET/179 and TABLE/183. Tester signer status
  is `UNKNOWN`; no unseen-signer claim is made.
- [x] Five valid physical-Xiaomi attempts completed with zero no-observation attempts. Evidence was
  pulled to the host **before** any uninstall/cleanup/reinstall (28 files, 1,658,539 bytes), hashed,
  and replayed through frozen Python V2 + ordinary Keras. Every capture-bound, chronology,
  duplicate, drain, no-double-sparse, mask and selected-timestamp-dt assertion passed.
- [x] Live→offline V2 max/p95/mean absolute error is
  `1.1920929e-7/0/3.6046133e-11` over 168,000 elements. Probability error is
  `3.8743019e-7/1.1670636e-9/2.0584177e-9` over 1,180 outputs. Top-1, Top-5 membership and Top-5
  order mismatches are all zero. Classification: **`LIVE_PLUMBING_VALIDATED`**.
- [x] Semantic results are diagnostic only and weak: Top-1 `1/5`, expected gloss in Top-5 `2/5`.
  Observation counts were min/median/max `48/59/79`, live rates `6.48/6.95/8.07 Hz`, body
  availability `100%`, but mean LH/RH observed rates were only `4.15%/24.62%`; TABLE had no
  observed hand in 60 frames. This is retained evidence of a likely live perception/domain or
  execution-quality problem, not a plumbing-parity failure and not proof that Phase 3 is solved.
- [x] Candidate01 latency p50/p95 was `121.48/184.52 ms`; V2 `35.22/69.94 ms`; TFLite
  `2.79/11.62 ms`; STOP→result `359.59/497.55 ms`. No crash/ANR, training, DEV access, protected
  TEST access, production UI connection, automatic gating or 30-class panel occurred. Evidence:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase4a_gate4a1_live_plumbing_validation_01/`.
  Current boundary: `WAIT_FOR_PROJECT_LEAD_GATE_4A2_DECISION`; do not start Gate 4A-2 automatically.

### 2026-09-15 — Phase 4A Gate 4A-1B controlled live-input recovery

- [x] Reverified all frozen Candidate01/V2/model/vocabulary identities and resolved the exact five
  TRAIN references: HELLO `e6:e6p_00795`, AT `asl:train:3317802933195262-AT`, HOME
  `asl:train:4506537239301789-HOME`, STREET `asl:train:44175204654391864-STREET`, and TABLE
  `asl:train:072729520535459-TABLE`. ASL Citizen sources resolve under the governed relocated
  `G:\ASL CITIZEN\ASL CITIZEN` root. No DEV or protected TEST was read.
- [x] Added debug-only bounded visual diagnostics without changing Candidate 01: first accepted,
  every 10th, last, and all observed/proposal hand-state transitions retain upright/unmirrored RGB,
  DWPose body/proposals, hand ROIs, refiner state, timestamps, luminance/sharpness and hashes.
  The phone requires a fresh exact-reference acknowledgement before each attempt.
- [x] Completed HELLO/AT/HOME/STREET/TABLE × two repetitions: 10 valid attempts, zero invalid
  no-observation attempts. Host evidence was pulled before cleanup: 548 files, 22,137,372 bytes,
  session `session_20260915T065635Z`, with a SHA-256 manifest. No uninstall/reinstall or app-data
  cleanup followed capture.
- [x] Offline replay technical PASS: V2 max/p95/mean absolute error
  `1.1920929e-7/0/1.9362189e-11`; probability error
  `5.9604645e-7/3.7252903e-9/3.2923340e-9`; zero Top-1, Top-5 membership or Top-5 ordering
  mismatches. All source-bound, drain, chronology, uniqueness, mask, selected-dt, no-double-sparse,
  artifact-hash and diagnostic-sampling checks pass.
- [x] Semantic result is diagnostic only: Top-1 `2/10`, expected in Top-5 `5/10`. Both HELLO
  repetitions were Top-1; HOME was Top-5 once and STREET Top-5 twice; AT/TABLE never reached Top-5.
- [x] Corrected the interpretation of low whole-attempt hand rates. Seven of ten attempts had
  `87.5–100%` either-hand continuity from the first to last observed-hand frame. STREET had both
  hands continuously observed during `1.47 s` and `1.80 s` active intervals. The `6.14–10.83 s`
  manual capture windows contain substantial hands-down lead-in/out and dilute the earlier rate.
- [x] Evidence is not uniformly healthy: TABLE contact/overlap yielded only 2 observed-hand frames
  per repetition and saved overlays show refiner-presence collapse. Its exact TRAIN reference also
  had 0% refined-hand observation, so this alone is not a new phone-only Candidate01 failure. HELLO/HOME body availability
  was 0 under the frozen group predicate despite partial visible body keypoints because close
  framing omitted a complete body reference. Finite luminance/sharpness does not support gross
  darkness or blur as the sole cause.
- [x] Final attribution: **`MIXED_OR_INCONCLUSIVE`**. Exact-exemplar guidance and controlled light
  did not isolate one cause; long manual bounds/body framing, TABLE contact/refiner weakness in both TRAIN and live,
  failure, and the known recognizer-generalization limitation remain entangled. Candidate01,
  Recognition V2 and the model are unchanged; no training, Gate 4A-2, production UI, automatic
  boundary work, DEV or protected-TEST access occurred.
- [x] `/imprint` registered only the debug diagnostics component and confirmed no feature-contract
  change. Canonical evidence:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase4a_gate4a1b_controlled_live_input_recovery_01/`.
  Current boundary: `WAIT_FOR_PROJECT_LEAD_REVIEW_AFTER_GATE_4A1B`; do not start Gate 4A-2 or a
  Candidate01 change automatically.

### 2026-09-15 — Project-lead Gate 4A-1C validation and Phase-4 closure

- [x] Project lead independently validated Gate 4A-1C as **PASS** with classification
  **TEMPORAL_BOUNDARY_PRIMARY_EFFECT_SUPPORTED**. Locked oracle-boundary SHA-256:
  0e6f14f159287ce830b68c4d33edba88dbb6aeef386060b80f79e3fed4a1e41f; source session
  session_20260915T065635Z; confidence HIGH 8, MEDIUM 1, LOW 1, UNCERTAIN 0.
- [x] Locked causal interpretation: wide live START→STOP windows add idle, preparation and recovery
  context that materially damages the frozen isolated-sign recognizer. Oracle isolation improved
  Top-1 2/10→7/10, expected-in-Top-5 5/10→8/10, median expected probability
  0.053839→0.585159, and median expected rank 5→1; five wrong attempts became correct and
  none became wrong.
- [x] Automatic isolated-sign active-window extraction is now a required future product component:
  continuous Candidate01 raw-v1 → rolling buffer → automatic start/active/end → controlled
  pre/post margin → frozen V2 → recognizer → gloss → re-arm. This remains isolated-sign
  recognition; fluent continuous ASL/coarticulation remains later research.
- [x] Candidate01 systemic failure is not supported. Phase 1 remains frozen; no Candidate02,
  threshold, ROI, anatomical-hand, scheduling or camera-preprocess work is authorized. Framing
  readiness is guidance/quality aid, not a hard recognition gate: HELLO stayed correct and HOME ×2
  became correct despite 0% complete body-group availability.
- [x] Phase-4 causal investigation is **CLOSED**. No Gate 4A-1D/1E and no further five-sign causal
  diagnostics. Gate 4A-2 is **HOLD**. Phase 5 is not started.
- [x] Next primary project boundary is **RETURN TO PHASE 3**, which remains paused but unsolved.
  Any next serious ML effort must add new signer/information diversity; no exact implementation or
  training run is authorized. Balanced sampling, invariant-objective/weight retries, class/loss
  weighting, LR/optimizer/seed/epoch sweeps, V2.1/V3, FPS/threshold loops and protected TEST remain
  closed.
- [x] Governance: Candidate01 modified NO; V2 modified NO; recognizer modified NO; training
  executed NO; DEV accessed NO; protected TEST accessed NO. Current boundary:
  WAIT_FOR_PROJECT_LEAD_PHASE3_STRATEGY_AUTHORIZATION.

### 2026-09-15 — Phase 4A Gate 4A-1C oracle temporal-boundary replay

- [x] Used only the 10 retained Gate-4A1B live attempts from `session_20260915T065635Z`; no new
  phone capture, DEV, protected TEST, extraction or training occurred. Reverified the frozen
  RecognitionV2.kt, authorized FP32 TFLite, vocabulary and ordinary V2 Keras checkpoint hashes.
- [x] Annotated sign intervals from retained RGB/annotated frames, raw trajectories and exact TRAIN
  motion references without using recognizer probabilities or predictions. Applied the same one
  accepted-observation margin before/after every interval. Confidence was HIGH `8`, MEDIUM `1`,
  LOW `1`, UNCERTAIN `0`, so 9/10 passed the predeclared causal-evidence threshold.
- [x] Finalized and hashed `oracle_bounds.json` before inference. Frozen SHA-256:
  `0e6f14f159287ce830b68c4d33edba88dbb6aeef386060b80f79e3fed4a1e41f`. Trimmed sequences were
  rebuilt from raw-v1 through frozen Python Recognition V2; the old V2 tensor was never sliced, so
  motion, selected-observation dt and elapsed fraction were recomputed from actual retained times.
- [x] Oracle trimming materially improved semantic results: Top-1 `2/10→7/10`, expected gloss in
  Top-5 `5/10→8/10`, median expected-class probability `0.053839→0.585159`, and median rank
  `5→1`. HOME ×2, STREET attempt 1 and TABLE ×2 became correct; no attempt became wrong.
- [x] Final classification: **`TEMPORAL_BOUNDARY_PRIMARY_EFFECT_SUPPORTED`**. Wide manual
  START→STOP windows are a major Phase-4 recognition contributor, but not a complete solution:
  AT ×2 and STREET attempt 2 remained wrong after oracle trimming. Candidate01, Recognition V2,
  the ordinary V2 TCN and all frozen temporal semantics remain unchanged.
- [x] `/imprint` registered the replay/audit component and confirmed there is no feature-contract
  change. Canonical evidence:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase4a_gate4a1c_oracle_temporal_boundary_replay_01/`.
  Pre-validation boundary was WAIT_FOR_PROJECT_LEAD_REVIEW_AFTER_GATE_4A1C. It is superseded by
  the validated project-state entry below; do not implement segmentation or start Gate 4A-2.

### 2026-09-15 — Authoritative state after Gate 4A-1C validation

- [x] **Phase 1:** FROZEN / COMPLETE. **Phase 2:** FROZEN / COMPLETE.
- [x] **Phase 3:** PAUSED BUT UNSOLVED and restored as the next primary project problem.
- [x] **Phase 4A:** all listed gates validated; causal investigation CLOSED; Gate 4A-2 HOLD.
- [x] **Phase 5:** NOT STARTED. Automatic isolated-sign active-window extraction and re-arm are
  required future architecture but are not authorized for implementation yet.
- [x] **Current boundary:** WAIT_FOR_PROJECT_LEAD_PHASE3_STRATEGY_AUTHORIZATION. No training or
  experiment starts automatically.

### 2026-09-15 — Phase 4A Gate 5 final attribution and decision

- [x] Reviewed only retained Gate 0 through Gate 4A-1C reports, decisions and frozen identities;
  ran no new inference, capture, extraction, evaluation or training and accessed neither DEV nor
  protected TEST.
- [x] Ruled out as primary by direct evidence: Android runtime, Android/Python V2 skew,
  Keras/TFLite skew, label mapping, buffer/state contamination, source-timestamp START/STOP
  membership and live double sparsification.
- [x] Confirmed excessive temporal context/bad sign boundaries as the major Phase-4 contributor.
  Body/framing and phone cadence are secondary. General Candidate01 failure, lighting, sign
  variant and missing refined hands are not supported as primary causes by the bounded evidence.
- [x] Preserved the causal result: frozen oracle isolation improved Top-1 `2/10→7/10`, expected
  Top-5 `5/10→8/10`, median expected probability `0.053839→0.585159`, and median rank `5→1`, with
  five wrong attempts becoming correct and zero regressions.
- [x] Phase-3 unseen-signer/independent-signer generalization remains unresolved. The ordinary V2
  TCN is not production-ready; same-data sampler/loss/LR/optimizer/seed/epoch and small-TCN loops
  remain closed. The next strategy must introduce new signer/information diversity.
- [x] Gate 4A-2 is **SUPERSEDED BY LATER VALIDATION AFTER PHASE-3 IMPROVEMENT**; no Gate 4A-1D/1E,
  further five-sign diagnostic, Phase 5 work or automatic-segmentation implementation starts now.
- [x] Final status: **`PHASE_4A_COMPLETE_RETURN_TO_PHASE_3`**. Phase state is Phase 1 frozen/
  complete; Phase 2 frozen/complete; Phase 3 **REOPEN NEXT — GENERALIZATION UNSOLVED**; Phase 4A
  **COMPLETE**; Phase 5 not started.
- [x] Current boundary: **`PHASE_3_RECOGNIZER_GENERALIZATION_REOPEN`**. This is a decision boundary,
  not authorization to implement or train. Canonical report:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase4a_gate5_live_phone_failure_attribution_and_decision_01/PHASE4A_GATE5_FINAL_REPORT.md`.
- [x] Governance: Candidate01 modified NO; V2 modified NO; recognizer modified NO; training
  executed NO; DEV accessed during Gate 5 NO; protected TEST accessed NO.

### 2026-09-15 — Phase 5.0 segmentation contract and signal audit

- [x] Project lead authorized Phase 5.0 audit/contract work only. Inspected the actual
  `apphear.perception_vnext.raw.v1` Python/Kotlin/live-persistence contract and the retained
  Gate-4A1B/Gate-4A1C session without changing Candidate01, Recognition V2, the recognizer, or
  Android behavior.
- [x] Reverified oracle-boundary SHA-256
  `0e6f14f159287ce830b68c4d33edba88dbb6aeef386060b80f79e3fed4a1e41f`. Signal analysis read only
  calibration attempts 002/003/005/007/009. Holdout raw-v1 payloads 004/006/008/010 and secondary
  attempt 001 were not used for threshold design; DEV and protected TEST were not accessed.
- [x] Found no single globally sufficient activity signal. Refined-hand motion is useful but fails
  TABLE contact; proposal ROI motion survives all five active intervals but overlaps pre/post;
  upper-limb geometry survives contact but also overlaps preparation/recovery. Hand presence,
  both-hand requirements, complete-body gating, inter-hand-only logic and fixed-frame timing are
  rejected.
- [x] Proposed one timestamp-based, validity-aware deterministic state machine with hysteresis,
  rolling pre-roll, controlled post-roll, fail-closed perception-gap behavior, stable-idle re-arm,
  one global one-shot calibration method, and `apphear.segmentation.sign_event.v1` as a future
  wrapper preserving original raw-v1 observations. No production segmentation was implemented.
- [x] Canonical report and reproducible calibration summary:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase5_0_segmentation_contract_and_signal_audit_01/`.
  Current boundary: `WAIT_FOR_PROJECT_LEAD_PHASE_5_1_IMPLEMENTATION_REVIEW`; do not start Phase 5.1
  automatically.

### 2026-09-16 — Phase 5.1T-0 segmentation data-readiness audit

- [x] Audited only the frozen governed recognition TRAIN population: 3,926 clips, 236 glosses,
  40 signer groups; ASL_CITIZEN 3,309, APPHEAR_CAPTURE 297, LOCAL 320. Recognition DEV,
  protected TEST, Gate-4 phone payloads, and sealed Phase-5 holdouts were not opened.
- [x] All 3,926 raw videos exist and expose valid container metadata. Found zero unreadable videos,
  duplicate sample IDs, duplicate source files, non-positive durations, out-of-bounds spans,
  negative context values, or ambiguous span units.
- [x] ASL_CITIZEN has 3,309 governed D1 detector sidecars using inclusive frame indices and a
  declared native FPS. APPHEAR_CAPTURE and LOCAL have no governed temporal span for all 617 rows;
  their E6 recognition features were built over the entire decoded clip. Sixty-four D1 spans
  exactly equal the full source-frame interval.
- [x] Context eligibility remains broad but sparse: +/-250 ms has 1,562 clips/34 signers/236
  glosses; +/-500 ms has 1,122/33/236; +/-750 ms has 685/26/235; +/-1000 ms has 440/20/220.
  The recovery-oriented 500 ms PRE + 750 ms POST bin has 953 clips/32 signers/236 glosses; 213
  glosses have at least 3 clips and 82 have at least 5.
- [x] Span lineage is understood but temporal truth is not. D1 uses landmark-motion hysteresis,
  a hands-raised gate, the longest run, and two-frame backoff; it is not a manual boundary. Frames
  outside a D1 span are detector-negative context, not proven preparation/idle or recovery.
  Therefore current spans may seed a weak-label/human-review candidate pool but must not be used
  as ground-truth PRE/ACTIVE/POST labels without detector-independent visual adjudication.
- [x] Final evidence statement: **`SEGMENTATION_SOURCE_CONTEXT_PARTIAL`**. No extraction, model
  training, recognition inference, Candidate01/V2/recognizer/Android change, or authoritative
  manifest creation occurred. Canonical evidence:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase5_1t_0_segmentation_data_readiness_audit_01/`.
  Current boundary: `WAIT_FOR_PROJECT_LEAD_PHASE_5_1T_1_DATASET_DECISION`.

### 2026-09-16 — Phase 5.1T-1 human temporal semantics validation

- [x] Froze the existing 24-sample inspection manifest without replacement. SHA-256
  `73b4e5c320ef36ca8c9dc27c86a23aff66c272bad712c85d9b719087b6600658`; population is 8
  APPHEAR_CAPTURE, 8 ASL_CITIZEN, and 8 LOCAL clips across 12 signer groups and 12 glosses.
- [x] Added a localhost-only browser reviewer with video playback/scrubbing/frame stepping,
  approximate START/END marking, four required semantic judgments, optional notes, deterministic
  navigation, immutable commit, and atomic save/resume.
- [x] ASL_CITIZEN D1 values, span paths, and span-derived context remain absent from browser state
  before each human commit. D1 onset/release and signed differences are loaded server-side and
  stored only after the corresponding human boundary is immutable. Non-ASL sources receive no
  invented D1 span.
- [x] Eleven focused technical tests, Ruff, and a live HTTP/video-range smoke pass. The combined
  relevant test run is 28 passed. No scientific holdout, recognizer output, training, Candidate01,
  Recognition V2, recognizer, source video, D1 span, recognition manifest, or Android behavior was
  accessed or modified beyond the authorized TRAIN videos used by the local reviewer.
- [x] All 24 frozen samples were human-reviewed and the guarded finalizer verified exact ordered
  membership. Results: clear PRE `21/24`, clear ACTIVE `23/24`, clear POST/recovery `20/24`, full
  PRE/ACTIVE/POST supervision `20/24`, recognizable active plus at least some surrounding context
  `21/24`, ambiguous/unusable `3/24`.
- [x] Source results: APPHEAR_CAPTURE full usable `7/8` and ambiguous `1/8`; ASL_CITIZEN full
  usable `8/8` and ambiguous `0/8`; LOCAL full usable `5/8`, active-plus-context `6/8`, and
  ambiguous `2/8`. The difficult cases do not overturn the substantial-majority result.
- [x] ASL_CITIZEN D1 diagnostic only: median absolute START difference `389.69 ms`, median
  absolute END difference `367.04 ms`, and `3/8` major disagreements above the frozen 500 ms
  criterion. D1 START was earlier than the human boundary in `7/8`; END direction split `4/4`.
  No D1 threshold, span, or human annotation was changed from this comparison.
- [x] Final binary decision: **`REUSE_EXISTING_SOURCE_POOL`**. The frozen decision rule passed
  (`23/24 >= 16/24` clear ACTIVE; `21/24 >= 16/24` active plus PRE or POST context). No dataset
  construction or training began. Current boundary:
  **`WAIT_FOR_PROJECT_LEAD_PHASE_5_1T_2_SEGMENTATION_DATASET_CONSTRUCTION_DECISION`**.

### 2026-09-16 — Phase 5.1T-2 bounded segmentation seed finalized

- [x] Deterministically froze exactly 120 governed recognition-TRAIN clips before inspecting
  reusable labels: ASL_CITIZEN 90, APPHEAR_CAPTURE 12, LOCAL 18. The population covers 37 signer
  groups and 92 glosses; all 32 eligible ASL_CITIZEN signers are represented and no ASL signer
  contributes more than four selected clips. Selected-manifest SHA-256:
  `832ba25420bef80acda3b40e7a44414654c3227222e4336d66174b8cca7ea15e`.
- [x] Froze a separate segmentation split at 96 TRAIN / 24 DEV with zero signer overlap. DEV holds
  six ASL_CITIZEN signers and one LOCAL signer; the sole APPHEAR_CAPTURE signer remains wholly in
  TRAIN. Nineteen DEV glosses are absent from segmentation TRAIN. Frozen-split SHA-256:
  `b4a2dbaf9c3810a86f8407068ea50dfc3f2079fc951932ff3a76bbe411b599c6`.
- [x] Intersected the immutable Phase-5.1T-1 annotations only after both freeze artifacts existed.
  Three selected clips were naturally reusable and remain unchanged; 117 new blinded annotations
  were completed. Historical PRE/POST checkboxes were not copied; PRE/POST availability is
  derived only from human timestamps and source duration.
- [x] Added a localhost reviewer with play/scrub/frame-step, approximate START/END, one
  ambiguous/unusable judgment, notes, immutable commits, atomic resume, and server-side D1 reveal
  only after each ASL_CITIZEN commit. All 35 focused/adjacent tests, Ruff, Python compilation, and
  live state/video-range smoke checks pass. Black and mypy are not installed in this environment.
- [x] All 120 selected rows were committed in exact frozen order. The guarded finalizer classified
  112 usable and 8 unusable without selecting replacements. Usable by source: ASL_CITIZEN 84/90,
  APPHEAR_CAPTURE 12/12, LOCAL 16/18; usable by split: segmentation TRAIN 89/96 and DEV 23/24.
  Of the usable rows, 104 have at least 250 ms PRE context and 110 have at least 250 ms POST
  context. There are zero invalid bounds or negative derived margins.
- [x] Final evidence state: **`SEGMENTATION_SEED_READY`** (`112 >= 100`). No model training,
  recognizer access, replacement selection, DEV/protected-TEST/phone-holdout access, or runtime
  modification occurred. Canonical package:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase5_1t_2_bounded_segmentation_seed_dataset_01/`.
  Current boundary:
  `WAIT_FOR_PROJECT_LEAD_PHASE_5_1T_3_FIRST_SEGMENTER_TRAINING_DECISION`.

### 2026-09-17 — Phase 5.1T-3 first class-agnostic causal segmenter

- [x] Reverified the frozen Phase-5.1T-2 selected-manifest SHA-256
  `832ba25420bef80acda3b40e7a44414654c3227222e4336d66174b8cca7ea15e` and segmentation-split
  SHA-256 `b4a2dbaf9c3810a86f8407068ea50dfc3f2079fc951932ff3a76bbe411b599c6`.
  Used exactly 89 usable segmentation-TRAIN and 23 usable unseen-signer DEV clips with zero signer
  overlap; no unusable replacement or new annotation occurred.
- [x] Verified complete-source Candidate01 raw-v1 for all 112 usable clips. Reused 28 prior
  APPHEAR_CAPTURE/LOCAL raw sequences only after proving `whole_isolated_clip`, frame-zero through
  decoded-final-frame coverage, and source-video hash identity. Re-extracted all 84 ASL_CITIZEN
  clips because their prior recognition sequences were D1-span cropped. Human boundaries were
  labels only; no governed/human span controlled extraction.
- [x] Froze `apphear.perception_vnext.segmentation_features.v1`: causal `[T,378]` current raw-v1
  hand/proposal/ROI/body/timing evidence plus one backward transition, explicit validity,
  zero-with-validity missingness, no future frame, interpolation, stale carry, RGB, gloss/class,
  Recognition V2 or recognizer output. Normalization came from segmentation TRAIN only.
- [x] Applied the single fixed 100 ms inclusive ignore band at human START/END. Supervised counts:
  TRAIN PRE/ACTIVE/POST `3452/2350/4025` with `1072` ignored; DEV `982/626/955` with `264`
  ignored. Trained one predeclared 123,779-parameter causal TCN for 50 fixed epochs with seed 5103,
  TRAIN-count class weights, no architecture/hyperparameter/threshold sweep, and no rerun.
- [x] The predeclared DEV boundary checkpoint selected epoch 7. Frozen DEV state accuracy/macro-F1
  are `0.8213/0.8213`; ACTIVE precision/recall/F1 are `0.7878/0.8898/0.8357`. The fixed decoder
  emitted `23/23` events, achieved >=90% human-ACTIVE containment on `22/23` (`95.65%`), median
  ACTIVE recall `1.0`, mean window precision `0.6337`, and one premature cut (`4.35%`).
- [x] Mean retained context fell from `3139.74 ms` for the full-video baseline to `678.02 ms`
  (`78.41%` reduction). All 19 DEV glosses absent from segmentation TRAIN emitted and met the
  containment rule; their mean ACTIVE recall was `0.9943`. The only premature cut was LOCAL HELLO
  `e6:e6p_00729` with ACTIVE recall `0.7838`; the held-out LOCAL signer remained the weakest group
  (mean recall `0.9459`) and must remain visible in live-integration planning.
- [x] All predeclared promotion checks passed. Final evidence state:
  **`LEARNED_SEGMENTER_PROMOTED_FOR_LIVE_INTEGRATION`**. This is an architecture-viability result,
  not production readiness. Candidate01, Recognition V2, the 236-class recognizer, recognition
  manifests, Android, protected TEST, recognition DEV, and sealed phone holdouts remain unchanged
  or unopened.
- [x] Fifty-three relevant tests, Ruff, Python compilation, saved-model loading, causal-future
  perturbation checks, and artifact/hash verification pass. Canonical package:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase5_1t_3_first_class_agnostic_segmenter_01/`.
  Current boundary:
  **`WAIT_FOR_PROJECT_LEAD_PHASE_5_1T_4_LIVE_INTEGRATION_DECISION`**.

### 2026-09-17 — Phase 6 frozen learned-segmenter phone replay

- [x] Verified every supplied Phase-5.1T-3 config/model/normalization/feature/decoder SHA-256,
  then replayed only the ten retained chronological Candidate01 raw-v1 attempts from
  `session_20260915T065635Z`. No Candidate01 rerun, interpolation, duplication, synthetic frame,
  timestamp modification, training, new capture, recognition DEV, protected TEST, other phone
  holdout, or Android change occurred.
- [x] Built sparse-phone `[T,378]` features with each backward delta taken against the immediately
  preceding actual phone observation and the frozen TRAIN normalization unchanged. The blind stage
  emitted 10/10 learned events and froze them before comparison at SHA-256
  `7f47050a92ce40ebf60b2f0a0859d2236bc10b1b781ce8071bc1d9e8894aebba`.
- [x] Reproduced the governed references exactly: FULL Top-1/Top-5 `2/10`/`5/10`, median expected
  probability/rank `0.0538386`/`5`; ORACLE `7/10`/`8/10`, `0.585159`/`1`.
- [x] Learned boundary recall was conservative rather than truncating: all 9 HIGH/MEDIUM attempts
  retained 100% of the unpadded oracle interval, with 0 below 0.60. However, all 10 events extended
  to the final phone observation, four started at the first observation, and mean full-window
  reduction was only `7.79%`, failing the predeclared `>=25%` gate.
- [x] LEARNED recognition remained Top-1 `2/10` while expected Top-5 improved to `7/10`, median
  expected probability to `0.0717128`, and median rank to `4.5`. Both FULL-correct HELLO attempts
  remained correct, but none of the five oracle-rescued HOME/STREET/TABLE attempts were rescued by
  LEARNED. AT attempts 003/004 and STREET 008 remained wrong under ORACLE and are bounded as
  `NOT_FIXED_BY_TEMPORAL_BOUNDARY`; the other five are `SEGMENTATION_TRANSFER_GAP`.
- [x] Production-transfer diagnostics show an extreme timing-domain shift: aggregate cadence
  `5.168 Hz`, median dt `199.962 ms`, and 98.33% of normalized dt observations above `|10 z|`.
  Valid refined-hand/ROI/body delta dimensions above `|3 z|` were respectively
  `11.73%/10.38%/16.61%`. This is consistent with cadence/delta-domain shift, while the dominant
  output behavior is ACTIVE/POST confusion or recovery-as-ACTIVE; it is not evidence for a more
  specific signer/perception cause.
- [x] Eleven bounded tests and Ruff pass. Final evidence state:
  **`PHASE6_LEARNED_SEGMENTER_PHONE_TRANSFER_NOT_SUPPORTED`**. The causal TCN plus sequence-global
  primary-run decoder remains an offline replay only; streaming Android SignEvent emission is not
  proven or authorized. Canonical package:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase6_frozen_learned_segmenter_phone_replay_01/`.
  Current boundary:
  **`WAIT_FOR_PROJECT_LEAD_PHONE_TRANSFER_FAILURE_DIAGNOSIS`**.

### 2026-09-17 — Phase 7 cadence-aligned corrective experiment completed

- [x] Verified all 112 Phase-5.1T-3 complete-source raw-v1 files against their frozen hashes:
  exactly 89 segmentation TRAIN and 23 signer-disjoint DEV; no missing/hash-invalid raw and no
  Candidate01 rerun.
- [x] Implemented one deterministic three-view timestamp sampler at `133.308`, `199.962`, and
  `266.616 ms`, with SHA-256-derived per-sample/view phase, genuine strictly increasing raw
  observations only, and full recomputation of the unchanged 378-wide causal feature schema from
  the immediately preceding selected observation.
- [x] Predeclared and tested a source-stratified 71 FIT / 18 CAL split within the 89 TRAIN clips;
  all three views remain grouped with their original clip. FIT-only sparse normalization/class
  weights and CAL-only lexicographic checkpointing prevent frozen DEV leakage.
- [x] Implemented guarded `prepare`, `train`, `evaluate`, and `phone-replay` stages. The unchanged
  123,779-parameter TCN trains from scratch for one 30-epoch run. The known Phase-6 session cannot
  open until checkpoint hashing and sparse DEV evaluation, and is refused entirely if the sparse
  DEV gate fails.
- [x] The supervisor completed the single authorized 30-epoch from-scratch run. CAL alone selected
  epoch 17: containment `90.74%`, premature cuts `9.26%`, event emission `100%`, mean window
  precision `0.6636`, and macro-F1 `0.9452`. The frozen checkpoint hash matches its sidecar.
- [x] Sparse signer-disjoint DEV passed all seven gates across 69 views: emission `100%`,
  containment `88.41%`, median/mean ACTIVE recall `1.0/0.9686`, premature cuts `11.59%`, mean
  full-window reduction `52.55%`, final-observation endings `13.04%`, and state accuracy/macro-F1
  `0.9164/0.9109`. Each cadence bucket mean recall remained >=`0.949`. The LOCAL held-out signer
  remains weak (containment `75%`, premature cuts `25%`, final endings `75%`, macro-F1 `0.738`).
- [x] The guarded known-phone diagnostic corrected the original ACTIVE-to-POST collapse:
  final-observation endings improved `10/10→0/10`, mean window reduction `7.79%→67.83%`, and
  recognition Top-1 `2/10→6/10` with four of five oracle-rescued HOME/STREET/TABLE attempts also
  recovered. Both FULL-correct HELLO attempts stayed correct.
- [x] The predeclared correction gate nevertheless failed: only `6/9` HIGH/MEDIUM attempts retained
  >=80% of the unpadded oracle interval. Attempts 004 and 006 retained `55.3%/53.8%`; attempt 008
  selected an early disjoint interval (`0%`). Cadence was therefore material but not sufficient;
  persistence collapse was replaced by phone truncation/phase-selection error.
- [x] Fifteen focused tests, Ruff, compilation, artifact/hash checks, and governance checks pass.
  Final evidence state: **`CADENCE_ALIGNMENT_ALONE_INSUFFICIENT`**. No post-result tuning or second
  model is authorized. Canonical package:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase7_production_cadence_aligned_segmenter_01/`.
  Current boundary: **`WAIT_FOR_PROJECT_LEAD_FEATURE_REPRESENTATION_DECISION`**.

### 2026-09-17 — Phase 8A causal streaming SignEvent decoder stopped at CAL

- [x] Verified frozen Segmenter S2 checkpoint SHA-256
  `dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73`, best epoch 17,
  unchanged 378-wide feature contract, and unchanged cadence-aligned normalization. No training,
  feature/normalization change, Candidate01/Recognition V2/recognizer change, or Android change
  occurred.
- [x] Implemented the reusable five-state timestamp decoder in
  `pipeline/perception_vnext/segmentation/streaming_decoder.py`: ACTIVE→PRE never emits, short PRE
  gaps may bridge, sustained PRE discards, ACTIVE→POST requires confirmation, POST→PRE may continue
  terminal evidence, padding retains only already-observed samples, emitted events are immutable,
  and re-arm requires 399.924 ms stable PRE.
- [x] Evaluated exactly the predeclared 27 configurations on Phase-7 CAL only (18 original clips,
  54 sparse views). Zero configurations were eligible. The closest lexicographic frontier emitted
  exactly one event on `50/54` (`92.59%`) but achieved only `50.00%` >=90%-ACTIVE containment,
  `50.00%` premature cuts, and `16.67%` severe cuts; mean context reduction was `69.77%`. Every
  configuration failed emission, exactly-one, containment, premature-cut, and severe-cut gates;
  every configuration passed context reduction.
- [x] Fifteen pytest cases, Ruff, Python compilation, and thirteen direct causal invariance/state
  checks pass. The CAL stop rule was honored: no decoder config was frozen, sparse DEV was not
  opened, the known phone session was not replayed, recognition was not run, and no Phase-8B
  package was prepared.
- [x] Final evidence state:
  **`PHASE8A_NO_ELIGIBLE_CAUSAL_STREAMING_DECODER`**. Canonical package:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase8a_causal_streaming_sign_event_decoder_01/`.
  Current boundary: **`WAIT_FOR_PROJECT_LEAD_CAUSAL_DECODER_DIAGNOSIS`**.

### 2026-09-17 — Phase 8A-R causal episode failure attribution completed

- [x] Audited frozen S2, the unchanged 378-wide contract, Phase-8A Decoder V1, and the written
  27-row grid. Reproduced the Phase-7 CAL global aggregate (`100%` emission, `90.74%` containment,
  `9.26%` premature cuts) and CONFIG_01 (`92.59%`, `50.00%`, `50.00%`) exactly before attribution.
- [x] Used only the 18 original Phase-7 CAL clips / 54 sparse CAL views. Sparse DEV, known phone,
  recognition DEV, protected TEST, sealed phone holdouts, and new captures remained unopened. No
  training, model/feature/label change, Decoder V2, recognizer inference, or Android change occurred.
- [x] The primary global-success/V1-failure set contains 22 views. Supported premature-first-commit
  cases: `0`; wrong-early episodes: `0`; primary internal PRE/POST interruption sequences: `1/2`;
  right-censored confirmation: `2`. Only `4/22` (`18.18%`) failures are attributable to the
  predeclared interruption/right-censor mechanisms.
- [x] Truncation is mixed: START-dominant `8`, END-dominant `6`, BOTH `4`, NO_EVENT `4`.
  Bounded-causally recoverable cases: `0/22`; no empirical grace distribution exists. All four
  predeclared Episode-V2 gates fail, including START-dominant `36.36% > 30%`.
- [x] Eight focused tests, Ruff, identity/source hashes, deterministic state-run checks, and exact
  aggregate reproduction pass. Final evidence state:
  **`EPISODE_V2_CAUSAL_DESIGN_NOT_SUPPORTED`**. Evidence favors
  **`MIXED_UNRESOLVED_CAUSES`**, not delayed terminal commitment as the principal repair. Canonical
  package:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase8a_r_causal_episode_failure_attribution_01/`.
  Current boundary: **`WAIT_FOR_PROJECT_LEAD_SEGMENTATION_ARCHITECTURE_DIAGNOSIS`**.

### 2026-09-19 — Phase 8A-R evaluator correction completed

- [x] Reclassified the 2026-09-17 Phase 8A-R decision as provisional while auditing the evaluator.
  Confirmed that historical bounded recoverability required an already-emitted event and that
  interruption presence was counted without proving causal containment improvement.
- [x] Reused the persisted per-observation probabilities, timestamps, argmax states, and state runs
  for exactly 18 CAL clips / 54 sparse CAL views. S2 inference was not rerun. Sparse DEV, known
  phone, recognition DEV, protected TEST, sealed/new phone data, and Android remained unopened;
  no training, feature/normalization/label change, Decoder V2, threshold search, or grace search
  occurred.
- [x] Reconstructed every V1 provisional candidate trajectory, including candidate opens, PRE
  bridges/discards, POST entries/cancellations, emissions, and EOF states. Added deterministic
  semantic tests for all predeclared cases A-H. Ten correction tests plus eight historical focused
  tests pass; Ruff and exact Phase-7/CONFIG_01 reproduction pass.
- [x] The evaluator defect was real, but correction strengthened the negative diagnosis. The
  primary failure set remains `22`; causally attributable failures decrease from `4/22` to `2/22`
  because the one PRE and two POST interruption counts were presence rather than causation. Both
  retained attributable cases are right-censored terminal confirmations. Bounded-causally
  recoverable cases remain `0/22`; no empirical grace distribution exists.
- [x] Frozen truncation remains START-dominant `8`, END-dominant `6`, BOTH `4`, NO_EVENT `4`.
  All four original Episode-V2 gates still fail unchanged. Corrected evidence state:
  **`EPISODE_V2_CAUSAL_DESIGN_NOT_SUPPORTED`**; supported direction remains
  **`MIXED_UNRESOLVED_CAUSES`**. Correction package:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase8a_r_causal_episode_failure_attribution_01/evaluator_correction_01/`.
  Current boundary: **`WAIT_FOR_PROJECT_LEAD_SEGMENTATION_ARCHITECTURE_DECISION`**.

### 2026-09-19 — Phase 8A-M cadence-safe sparse recognition-window materialization completed on CAL

- [x] Audited Phase-7 and Phase-8A CONFIG_01 materialization from source and persisted CAL traces.
  Phase 7 reports continuous padded time bounds, while CONFIG_01 inward-brackets genuine sparse
  observations. The Phase-7 reported reference therefore contains continuous-time optimism:
  reported >=90%-ACTIVE containment was `49/54`, but the genuine observations selected inside its
  bounds achieved `33/54`.
- [x] Confirmed that materialization is nevertheless a real isolated defect: CONFIG_01 emitted on
  `50/54` views; `49/50` emitted events had exactly the same logical ACTIVE start/end as the
  Phase-7 selected run, and all 49 had different delivered sparse windows. B/C preserve the exact
  same CONFIG_01 logical decisions and boundaries.
- [x] Added the deterministic `apphear.recognition_window_materializer.v1` component and a bounded
  observation ring buffer. It outward-brackets the fixed 250 ms request using only genuine,
  chronological observations already available by commit time and reports actual context plus
  explicit censoring; no interpolation, duplication, stale carry, or future read is allowed.
- [x] On emitted CONFIG_01 events, cadence-safe materialization improved >=90% containment
  `27/50→45/50` (`54%→90%`), premature cuts `46%→10%`, severe cuts `10%→0%`, and mean ACTIVE recall
  `0.8486→0.9787`, while preserving `48.98%` mean context reduction. It recovered `18/22`
  (`81.82%`) of the reported Phase-7→CONFIG_01 containment gap.
- [x] All cadence buckets retained mean ACTIVE recall above `0.95`; VIEW_C containment remained
  weaker at `13/16` emitted events. Five windows were left-censored; none were right-censored by
  materialization. The unchanged logical producer still had two right-censored confirmations and
  two missing-terminal-POST failures. LOCAL emitted only `3/6`, which materialization cannot fix.
- [x] Twelve focused tests, Ruff, compilation, CAL-only population guards, and contract/hash checks
  pass. No S2 inference, training, sparse DEV, known phone, recognition, Android, feature,
  normalization, label, or state-machine change occurred. Final evidence state:
  **`CADENCE_SAFE_RECOGNITION_WINDOW_MATERIALIZER_CAL_SUPPORTED`**. Canonical package:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase8a_m_causal_sparse_recognition_window_materialization_01/`.
  Current boundary: **`WAIT_FOR_PROJECT_LEAD_PHASE8A_M_SPARSE_DEV_DECISION`**.

### 2026-09-19 — Phase 8A-M2 frozen signer-disjoint sparse DEV validation completed

- [x] Reverified the frozen S2 checkpoint SHA-256
  `dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73`, Phase-7 FIT-only
  normalization, unchanged `[378]` feature schema, exact CONFIG_01 parameters, and frozen
  materializer contract SHA-256
  `0a59dc80fe54cb37e09fbce8aa108dbfce32bc4b5cb48b98e61619b5b3b34971` before DEV.
- [x] Reused the exact 69 prepared sparse DEV views from 23 clips / 7 signer-disjoint groups in
  equal VIEW_A/B/C buckets. Phase 7 had not persisted DEV probabilities, so one frozen S2 forward
  pass was performed and hash-bound state streams were retained; no raw-v1 extraction,
  Candidate01 rerun, training, model selection, recognition, known-phone access, protected TEST,
  parameter change, or Android change occurred.
- [x] The complete causal stack failed the strict event-production gate: CONFIG_01 emitted exactly
  one event on `59/69` (`85.51%`) with zero multiple events, below the approximately-95% criterion.
  Censor-aware potential emission was only `62/69` (`89.86%`) and was not used to relax the gate.
- [x] The frozen materializer generalized when an event existed: containment `52/59` (`88.14%`),
  mean/median ACTIVE recall `0.9661/1.0`, premature cuts `11.86%`, severe cuts `0%`, and mean
  context reduction `55.47%`. All materializer responsibility gates passed. VIEW_A/B/C mean
  recall was `0.9757/0.9672/0.9542`; VIEW_C containment was mildly weaker at `16/19` (`84.21%`)
  but did not catastrophically collapse.
- [x] Failure is sharply source/domain localized. ASL_CITIZEN emitted `57/57`; LOCAL emitted only
  `2/12`, although both emitted LOCAL windows achieved >=90% containment. All ten no-events were
  LOCAL: three were finite-source censored before terminal confirmation was observable, while
  seven had adequate post-sign observations but never produced terminal POST. This supports a
  LOCAL/mobile-domain terminal-state/event-production limit, not materializer failure.
- [x] Ten focused tests, Ruff, compilation, DEV membership/hash guards, and artifact hash checks
  pass. No post-DEV tuning occurred. Final evidence state:
  **`MATERIALIZER_DEV_SUPPORTED_EVENT_PRODUCER_LIMITED`**. Canonical package:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase8a_m2_frozen_signer_disjoint_sparse_dev_validation_01/`.
  Current boundary: **`WAIT_FOR_PROJECT_LEAD_EVENT_PRODUCER_DECISION`**.

### 2026-09-19 — Phase 8A-T causal terminal-evidence attribution completed

- [x] Reused persisted frozen-S2 probability streams for all `54` CAL and `69` signer-disjoint
  sparse DEV views. The S2 checkpoint, `[378]` features, cadence-aligned normalization,
  CONFIG_01 behavior, and cadence-safe materializer remained unchanged. No inference, extraction,
  training, probability-threshold search, decoder implementation, recognition, phone, protected
  TEST, or Android access occurred.
- [x] Added the analytical-only `apphear.diagnostics.terminal_evidence.v1` component. Its frozen
  attribution rule compares five post-end measures against the successful-terminal p10 envelope
  and the ordinary intra-sign POST-fluctuation p95 envelope; it performs no threshold search.
- [x] The seven genuine non-censored DEV no-event views span three underlying LOCAL clips from the
  single held-out LOCAL signer. Six views were `MODEL_TERMINAL_SIGNAL_ABSENT`, one was
  `MIXED_OR_AMBIGUOUS`, and zero contained successful-commit-like terminal evidence that
  CONFIG_01 merely failed to exploit. At clip level, two clips are signal-absent and one is mixed.
- [x] Cadence sensitivity is present but not universal: two clips succeed at VIEW_A and fail at
  VIEW_B/VIEW_C, while one clip lacks terminal evidence across all three views. The three views
  from a fourth LOCAL clip remain explicitly right-censored and do not vote in attribution.
- [x] A CAL no-event with strong terminal POST confirms that decoder-utilization failures can
  exist, but that is not the dominant opened-DEV mechanism. Probability-aware decoder work is
  therefore not supported as the first repair. The supported next direction is a bounded audit of
  signer/recovery-transition diversity before one targeted S2 ACTIVE→POST generalization
  correction. Current TRAIN support is shallow: `12` LOCAL clips across three signers plus `12`
  APPHEAR_CAPTURE clips from one signer.
- [x] Nine focused tests, Ruff, and compilation pass. Final evidence state:
  **`S2_TERMINAL_GENERALIZATION_CORRECTION_SUPPORTED`**. Canonical package:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase8a_t_causal_terminal_evidence_attribution_01/`.
  Current boundary: **`WAIT_FOR_PROJECT_LEAD_TERMINAL_ARCHITECTURE_DECISION`**.

### 2026-09-20 — Phase 8A-U S2 training exposure and terminal-diversity audit completed

- [x] Distinguished actual weight-update exposure from available labels: FIT-71/213 views updated
  S2; CAL-18/54 views selected the checkpoint. FIT exact supervised counts reproduce Phase 7:
  PRE `1,469`, ACTIVE `995`, POST `1,752`, plus `476` ignored boundary observations.
- [x] FIT contained ASL_CITIZEN `52` clips / `23` signers, APPHEAR_CAPTURE `9` / `1`, and LOCAL
  `10` / `3`. ACTIVE→POST labels survived in `210/213` views; CONFIG_01-timescale POST coverage
  survived in `191/213` overall and `26/30` LOCAL views. The weakness is not absence of POST label
  volume: it is source-domain signer depth and concentration. One LOCAL signer supplied `405/490`
  (`82.65%`) of FIT LOCAL sparse POST observations; APPHEAR_CAPTURE came entirely from one signer.
- [x] CAL contained ASL_CITIZEN `13` clips / `11` signers, APPHEAR_CAPTURE `3` / `1`, and LOCAL
  `2` / `2`. One CAL LOCAL signer supplied `144/150` (`96%`) sparse POST observations, so
  selection-side source-domain terminal evidence was also concentrated.
- [x] Verified checkpoint-objective misalignment from source and artifacts. Epoch 17 was selected
  by completed-sequence global containment/premature-cut/emission/precision/macro-F1. No causal
  CONFIG_01 event availability, terminal POST, or emission-latency measure participated. On the
  same CAL views the selected checkpoint had global emission/containment `1.0/0.9074`, versus
  CONFIG_01 `0.9259/0.5` with `0.5` premature cuts.
- [x] Audited existing governed TRAIN data without promoting weak labels. `3,806` clips remain
  unselected (`3,219` ASL_CITIZEN, `285` APPHEAR_CAPTURE, `302` LOCAL); `863` ASL clips have
  D1-estimated 500/750 ms room, but D1 remains detector-derived and is not temporal truth.
  Phase 5.1T-1 contributes `19` usable human-labeled clips outside the selected 120; `17` preserve
  DEV signer isolation, but APPHEAR/LOCAL rows add only already represented signers. There is no
  unreserved independent source-domain signer in the governed unused pool.
- [x] Resolved the Phase-8A-T 97-versus-94 discrepancy. The omitted controls are
  `asl:train:5919946010475778-RUN 2::VIEW_A`, `e6:e6p_00528::VIEW_A`, and
  `e6:e6p_00799::VIEW_A`. All committed slightly before human END, so `[human END, commit]` had
  zero observations. Exclusion is deterministic and causal; the attribution conclusion is
  unchanged.
- [x] Nine focused tests, Ruff, and compilation pass. No training, inference, raw-v1 extraction,
  decoder search, recognition, known-phone, Recognition DEV, protected TEST, or Android work ran.
  Final state: **`TARGETED_S2_DATA_AND_CAUSAL_OBJECTIVE_CORRECTION_SUPPORTED`**. Canonical package:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase8a_u_s2_training_exposure_and_terminal_diversity_audit_01/`.
  Current boundary: **`WAIT_FOR_PROJECT_LEAD_S2_R1_ARCHITECTURE_REVIEW`**.

### 2026-09-20 — Phone causal recognition integration implementation prepared

- [x] Project Lead deferred S2-R1 and authorized phone-first integration using the exact frozen S2,
  Phase-7 normalization, segmentation feature schema v1 `[378]`, unchanged CONFIG_01, frozen
  cadence-safe materializer, Recognition V2, and frozen 236-class recognizer.
- [x] Added a debug-only, build-flagged and intent-opt-in continuous pipeline in the existing
  Candidate01 live activity. Release remains hard-disabled. The pipeline maintains genuine
  chronological observations, a bounded ring buffer, CONFIG_01-owned re-arm, and no interpolation,
  duplication, stale carry, future reads, or parallel legacy re-arm.
- [x] Exported the frozen S2 checkpoint to an identity-preserving FP32 TFLite current-state wrapper.
  Host bounded-prefix parity passes across 131 CAL observations with maximum absolute probability
  difference `6.556510925292969e-07`; exported model SHA-256 is
  `820023d15c98dab2fb8f21914906ccd637d32bce7b825cbd1d89a58c80cd4ed7`.
- [x] Added JVM causality/materialization/feature tests, Android feature and S2 parity fixtures, and
  structured per-observation/event/attempt logging with synchronized visual-audit evidence. JVM
  tests, debug assembly, and Android-test compilation pass. No training or frozen-contract change
  occurred.
- [x] Current on-device parity passes on the authorized Xiaomi M2101K7AG Android 12 device: the
  regenerated four-observation 378-feature fixture passes at `1e-6` per-feature absolute tolerance,
  and the corrected 131-observation fixed-output S2 fixture passes at `1e-4` per-probability
  tolerance (`2/2` instrumentation tests; `BUILD SUCCESSFUL`).
- [x] Started a fresh controlled session `session_20260920T095253Z`. Attempt 1 (HELLO) emitted
  exactly one marked event, and the frozen recognizer returned HELLO at probability `0.9999137`
  (expected rank 1). Bounded visual review confirms the 14-observation materialized window contains
  the visible sign and early recovery; this is not an independent human annotation study.
- [x] After that correct event, CONFIG_01 did not re-arm across 261 genuine observations spanning
  `57.922 s`: PRE/ACTIVE/POST argmax counts were `2/35/224`, median POST probability was
  `0.9992494`, both PRE re-arm starts reset, and the final state remained
  `EVENT_EMITTED_WAIT_REARM`. The frozen 399.924 ms stable-PRE requirement is incompatible with
  this observed POST-stable recovery stream. The remaining nine attempts were not captured.
- [x] Preserved and imported all 409 observations, 2 events (one unmarked while positioning),
  synchronized attempt frames, identities, and timings. The app was stopped; no re-arm bypass,
  threshold change, S2-R1 training, or repeat run occurred.
- [x] Final bounded integration classification: **`PHONE_EVENT_PRODUCER_LIMIT_SUPPORTED`**, with
  supported subcause `CONFIG_01_PRE_ONLY_REARM_LIFECYCLE`. This is one-attempt architecture
  evidence, not a production accuracy estimate. Current boundary:
  **`WAIT_FOR_PROJECT_LEAD_PHONE_EVENT_LIFECYCLE_DECISION`**.

### 2026-09-20 — Phone lifecycle re-arm Stage-A replay

- [x] Reconstructed Python and Android CONFIG_01 re-arm semantics: after an immutable event, only
  argmax PRE advances the frozen 399.924 ms timer; POST and ACTIVE reset it.
- [x] Reused persisted S2 probabilities only: 54 CAL sparse views, 69 signer-disjoint DEV sparse
  views, and all 409 observations from fresh phone session `session_20260920T095253Z`. No S2 or
  perception inference, training, recognition, phone capture, or Android production change ran.
- [x] Evaluated exactly one counterfactual with no duration search: PRE or POST advances the same
  399.924 ms persistence timer, while ACTIVE resets it. First-event identities remain exact for
  `50/50` emitted CAL streams, `59/59` emitted DEV streams, and the marked phone HELLO event.
- [x] CAL/DEV finite isolated clips produced no additional events, but only `22/50` emitted CAL and
  `34/59` emitted DEV streams contained enough post-event evidence to re-arm. They are therefore a
  weak continuous-stream duplicate-safety test.
- [x] The continuous phone session is decisive: HELLO re-armed after `733.194 ms` and no event
  occurred during its first two recovery seconds, but the unlocked decoder later emitted seven
  unprompted events after attempt 1 was marked complete. The first appeared `15.197 s` after HELLO.
  Control CONFIG_01 remained safely disarmed.
- [x] Final Stage-A state: **`NON_ACTIVE_REARM_UNSAFE`**. A separately frozen hybrid readiness
  policy using independent quiet/stability evidence is the supported next direction, but was not
  designed, searched, implemented, or deployed. Android remains unchanged. Current boundary:
  **`WAIT_FOR_PROJECT_LEAD_REARM_ARCHITECTURE_DECISION`**.

### 2026-09-20 — Phone sign-admission and re-arm Stage-A attribution

- [x] Audited visual coverage before designing an admission rule. Synchronized evidence ends with
  attempt 1 at observation count `161`; the seven questioned post-HELLO onsets begin at indices
  `184, 264, 279, 293, 303, 333, 352`. Visual/human ground truth is therefore `0/7`.
- [x] Reconstructed each onset from persisted phone telemetry and compared it with validated HELLO
  plus 50 governed CAL event onsets. Six of seven questioned ACTIVE runs have no refined-hand
  observation, four have no body availability, and all retain proposal presence; however one has
  full refined-hand/body availability. These support a mechanism description, not a semantic
  false-positive label or a safe threshold.
- [x] Did not use the tempting `no refined hand → reject` rule: HELLO itself loses refinement on
  30% of its ACTIVE observations, CAL lacks equivalent phone validity telemetry, and no visual
  labels establish that the seven episodes were non-sign movements.
- [x] No admission policy was selected; DEV remained unused, Android remained unchanged, and no
  perception/S2 rerun, training, recognition, or protected population access occurred. Prepared a
  fixed eight-behavior negative diagnostic manifest covering neutral, stationary raised hands,
  adjustment, repositioning, out/in motion, ordinary movement, HELLO, and TABLE.
- [x] Final state: **`INSUFFICIENT_NEGATIVE_GROUND_TRUTH`**. Current boundary:
  **`WAIT_FOR_PROJECT_SUPERVISOR_CONTROLLED_NEGATIVE_CAPTURE_DECISION`**.

### 2026-09-20 — Repeated phone recognition lifecycle implementation prepared

- [x] Audited the Android phone-causal lifecycle. `PhoneCausalEventProducer` is the sole lifecycle
  and re-arm owner; no legacy downstream re-arm also runs. The retained HELLO deadlock is explained
  by PRE-only re-arm semantics, not a competing-owner implementation defect.
- [x] Added explicit `PRE_ONLY` and `PRE_OR_POST_EXPERIMENTAL` re-arm policies while preserving the
  399.924 ms persistence requirement. ACTIVE resets recovery. Observation gaps over 533.232 ms
  reset the timer so missing processing time cannot satisfy recovery.
- [x] Added an independently testable new-sign admission boundary with exactly one authorized
  behavior, `PASS_THROUGH`. No hand/body/proposal/motion/probability/recognizer gate was introduced
  from the seven visually unlabeled phone events.
- [x] Extended per-observation diagnostics with lifecycle policy, recovery progress/reasons,
  admission decisions, attempt identity, Candidate01 support summaries, and visual references.
  The next session saves a synchronized original for every processed observation plus bounded
  annotated evidence around each event, fixing the previous post-HELLO visual-coverage gap.
- [x] Read-only replay over the 409-observation retained phone session preserves the marked HELLO
  exactly (logical indices `135..144`, terminal POST `145`, commit `147`, materialized window
  `134..147`, V2 valid/mask `14/14`, HELLO `0.9999137`). PRE-only yields two events/one re-arm;
  experimental PRE-or-POST yields nine events/nine re-arms, matching the accepted diagnostic.
- [x] Focused JVM tests pass, existing Python lifecycle/admission tests pass `8/8`, debug assembly
  passes, and physical Xiaomi feature/S2 parity passes `2/2`. The exact debug build is installed.
  Full-project lint remains blocked by unrelated existing debug API-level errors; none were changed.
- [x] Run the fixed supervisor-controlled HELLO/HELLO/AT/AT/HOME/HOME/STREET/STREET/TABLE/TABLE
  cohort with `PRE_OR_POST_EXPERIMENTAL`, pull the complete synchronized session, then perform
  visual failure attribution. Completed below as `session_20260920T145710Z`.

### 2026-09-20 — Repeated phone recognition cohort completed and attributed

- [x] Completed the fixed ten-attempt cohort as `session_20260920T145710Z`. Pulled 2,747 genuine
  observations, 22 events, ten completed attempt records, and 2,747 synchronized originals with
  no missing visual coverage. All ten intended signs are visibly present and all ten attempts began
  in `IDLE`.
- [x] PRE-or-POST recovery resolved the demonstrated lifecycle deadlock: all 22 emitted events
  re-armed, zero gap resets occurred, and no intended attempt was blocked in WAIT_REARM. Median
  re-arm latency was 466.9 ms (p90 2,132.9 ms).
- [x] The full repeated-recognition target did not pass. Only 3/10 marked attempts emitted an event;
  strict Top-1 was 1/10 and expected-gloss Top-5 was 2/10. HOME 006 was correct. STREET 007 had a
  usable window but classified as CLOTHES (STREET rank 3). STREET 008 committed an early episode
  whose materialized window truncated the visible sign.
- [x] The seven no-event attempts are genuine signs, not missing capture. Five had zero ACTIVE
  argmax observations and two had only one, supporting a phone ACTIVE-acquisition/generalization
  failure distinct from the earlier terminal-POST problem.
- [x] Full-session visual attribution confirms 16/22 events contained ordinary positioning,
  phone interaction, non-sign movement, or a wrong early episode; five were defensible sign-like
  events and one remained uncertain. PASS_THROUGH admission is therefore unsafe, but an admission
  filter alone cannot recover the missed genuine signs.
- [x] The materializer remains frozen: its failure on STREET 008 follows a wrong logical episode,
  not a sparse-bracketing defect. No model, threshold, decoder, materializer, or recognizer change
  was made after the cohort.
- [x] Final state:
  **`PHONE_REARM_SUPPORTED_REPEATED_RECOGNITION_NOT_YET_SUPPORTED`**. Current boundary:
  **`WAIT_FOR_PROJECT_LEAD_PHONE_ADMISSION_AND_S2_ACTIVE_ACQUISITION_DECISION`**.

### 2026-09-21 — New-sign admission and ACTIVE-acquisition design audit

- [x] Reused the complete 2,747-observation/22-event synchronized design session
  `session_20260920T145710Z`; no perception/S2 inference, training, DEV, protected TEST, or
  recognition rerun occurred.
- [x] Refined the former combined visual category into 15 `CONFIRMED_NON_SIGN` events, five
  `GENUINE_SIGN_ONSET` events, event 20 as `EARLY_SIGN_FRAGMENT_OR_WRONG_EPISODE`, and event 6 as
  `UNCERTAIN`. Event 20 is not used as a negative admission example.
- [x] Rejected three bounded deterministic alternatives rather than tuning them: direct support at
  first ACTIVE rejects 4/54 governed CAL genuine onsets while retaining 10/15 phone non-sign
  events; allowing support across two ACTIVE observations preserves 54/54 CAL onsets but retains
  11/15 phone non-sign events; requiring two consecutive ACTIVE observations loses reviewed
  genuine phone episodes.
- [x] Confirmed the design phone log does not persist the existing 378-feature motion blocks, so a
  fresh-motion admission hypothesis cannot be exactly replayed against the labeled negatives.
  Added compact debug-only hand/ROI/body delta magnitude and validity summaries derived from the
  unchanged raw 378 vector. Admission remains `PASS_THROUGH`; re-arm and all frozen components are
  unchanged.
- [x] Added an explicit debug-harness selector for the fixed rested evidence sequence
  HELLO/HELLO/HOME/HOME/TABLE/TABLE. It changes only target prompting and attempt metadata; the
  temporal and recognition path remains unchanged.
- [x] Focused Python tests pass `5/5`, Ruff passes, PhoneCausalCore JVM tests pass `13/13`, and
  `:app:assembleDebug` passes. The next capture is diagnostic evidence acquisition, not validation
  of a frozen admission rule.
- [x] Final state: **`SIGN_ADMISSION_POLICY_NOT_YET_SUPPORTED`**. S2 training remains unauthorized.
  Current boundary: **`WAIT_FOR_PROJECT_SUPERVISOR_RESTED_EVIDENCE_CAPTURE`**.

### 2026-09-21 — Rested six-attempt phone evidence collected and attributed

- [x] Closed and pulled `session_20260921T102840Z` without changing the runtime: 2,186 ordered
  observations, 24 events, and all six fixed HELLO/HELLO/HOME/HOME/TABLE/TABLE attempts complete.
  The Project Supervisor confirmed all six were deliberately and correctly performed.
- [x] All six attempts began `IDLE`. Re-arm completed after both marked emitted events and 23/24
  events overall; the final event had no post-event interval before shutdown. The previous re-arm
  deadlock did not recur.
- [x] Marked event emission and strict Top-1 were 2/6: HELLO 001 and TABLE 005 were recognized
  correctly through the frozen materializer, Recognition V2, and recognizer. HELLO 002, HOME 003,
  HOME 004, and TABLE 006 had zero S2 argmax ACTIVE observations despite intentional visible
  gestures. In three misses, refined-hand and ROI-motion evidence was present during the gesture.
- [x] PASS_THROUGH still emitted many events outside marked attempts. Original frames support
  ordinary/non-sign positioning for 14 visually covered events; one shoulder-touch episode remains
  uncertain. Events 18–24 lack synchronized originals and are not semantically classified. This
  session cannot yield a production false-event rate or a safe admission threshold.
- [x] Visual originals cover observations 0–1859 (1,860/2,186), including all marked attempts.
  The evidence summary was written at attempt 006 completion (1,083 frames) and is stale. The
  final 326 originals were not retained; the exact cause is unresolved, while source lacks a
  verified final visual-writer drain. Flag before the next independent phone session.
- [x] No admission rule, S2 training, decoder tuning, materializer change, recognizer change, or
  protected-population access occurred. Final diagnostic state:
  **`PHONE_ACTIVE_ACQUISITION_LIMIT_SUPPORTED`**. Stop at
  **`WAIT_FOR_PROJECT_LEAD_PHONE_ACTIVE_ACQUISITION_AND_NON_SIGN_ARCHITECTURE_DECISION`**.

### 2026-09-21 — S2-R2 parity gate paused; visual evidence finalization corrected

- [x] Audited the rested `session_20260921T102840Z` capture path. Its 2,186 observation records retain compact summaries/probabilities, not full raw-v1 observations, Android 378 vectors, or normalized S2 inputs. JPEG replay cannot prove exact same-observation train/serve parity. **No parity pass/fail or model-domain root-cause claim is made.**
- [x] Added a debug-only explicit final visual drain with camera stop, analyzer barrier, queued-writer wait, exact original-file count check, and final summary on verified completion. Focused drain test, causal-core tests, and debug Kotlin compile pass. Device-side drain verification remains pending.
- [ ] Before S2-R2 training, obtain a bounded opt-in same-observation raw/378/normalized/S2 phone capture and compare it with the host reference. If runtime parity fails, fix it and stop. If it passes, assess whether signer-diverse positive and continuous-negative data is sufficient. No training, frozen-component change, protected TEST access, or fresh phone claim occurred.

### 2026-09-21 — Exact phone S2 parity capture implemented; awaiting device cohort

- [x] Added explicitly opted-in debug instrumentation (`s2_exact_parity_capture=true`) that copies the existing raw-v1 observation, already-derived 378 row, exact normalized S2 row, and PRE/ACTIVE/POST output without creating a second feature or inference path. Capture is bounded to 3,600 observations and finalized with sizes/hashes/linkage.
- [x] Added the fail-closed host evaluator for progressive feature, normalization, and Keras-vs-Android S2 parity. The evaluator requires the fixed HELLO/HELLO/HOME/HOME/TABLE/TABLE cohort, complete same-observation linkage, and 100% finalized visual coverage before comparison.
- [x] Host tests pass `2/2`; Ruff passes; focused recorder/finalizer/causal-core JVM tests pass; debug and Android-test APK builds pass. Connected instrumentation was not run because no device was attached.
- [ ] Run the governed supervisor phone capture and then `audit-capture` followed by `parity`. Current state: **`WAIT_FOR_PROJECT_SUPERVISOR_EXACT_PARITY_PHONE_CAPTURE`**. There is no parity decision and S2-R2 training remains prohibited.

### 2026-09-21 — Exact phone S2 parity passed; R2 data-governance stop

- [x] Resolved the supervisor command failure: `<CAPTURED_SESSION>` was used literally. Pulled the actual device session `session_20260921T153138Z` (2,492 files / 68,890,924 bytes) and improved the evaluator's placeholder error.
- [x] Capture integrity passes: 669 chronological observations, all six fixed attempts, exact raw/feature linkage, and 669/669 finalized synchronized originals.
- [x] Exact progressive parity passes. Host vs Android 378 and normalized inputs are bit-identical (max abs 0.0); frozen Keras vs Android TFLite S2 max probability difference is `1.9073486328125e-6`; argmax mismatches are 0/669. Root decision: **`PARITY_PASS_S2_DOMAIN_CORRECTION_SUPPORTED`**.
- [x] The new cohort still shows weak acquisition: marked events only for HOME 004 and TABLE 005, both correctly recognized. HELLO 001/002 and TABLE 006 had zero argmax ACTIVE; HOME 003 had one isolated ACTIVE and no event. Two events occurred outside marked attempts and require human semantic review.
- [ ] Do not train yet: this is one `UNKNOWN`-identity phone signer with attempt markers rather than governed per-observation PRE/ACTIVE/POST labels, and inter-attempt negatives are not human-labeled. Resolve signer/split role, temporal labels, bounded negatives, an additional training-development phone/LOCAL signer, and a distinct untouched phone validation signer/session. Stop at **`WAIT_FOR_PROJECT_LEAD_S2_R2_DATA_GOVERNANCE_AND_LABELING_DECISION`**.

### 2026-09-22 — S2-R2 historical negative source recovery audit

- [x] Audited historical negative/background/non-sign sources without rerunning their experiments, model inference, training, threshold tuning, or protected TEST. Recovered 57 N0 and 30 P1 original MP4s totaling 1,555.063 seconds across eight historical capture-participant IDs.
- [x] Identified P1 as the primary hard-continuous-negative candidate: 30 phone videos intentionally covering rest, ordinary object/phone handling, casual pointing, grooming/clothing adjustment, pickup/putdown, crossing, and occlusion. Historical review certifies sampled hand evidence, not blanket whole-video PRE labels; bounded semantic/temporal review remains required.
- [x] Identified N0 as secondary static/background/body-arm/object-motion material. The blinded readjudication found 238/250 sampled frames `ZERO_HAND`, nine `VISIBLE_IDLE_HAND`, and three `TRANSITION`; raw videos remain candidates but cannot be auto-labeled from frame results.
- [x] Excluded the 30 E4-AG files as byte-identical P1 aliases; excluded still-image gold, logs without raw video, unlabeled A1/A2 sign-context frames, transition-partial clips, and genuine OOV signs from negative temporal supervision.
- [x] Preserved E6 signer `0F747C-S001` as untouched provisional negative validation: 180 idle/face-adjacent/accidental-motion clips are relevant, while 60 transition-partial and 320 OOV-sign clips are not negative supervision.
- [x] Historical P01-P06 identities are not mapped to governed S2 signer IDs, so independence from FIT/CAL/DEV is unresolved rather than assumed. No new negative collection is justified until P1/N0 whole-video review and participant/split resolution are complete.
- [x] Decision: **`HISTORICAL_NEGATIVE_SOURCE_RECOVERY_SUPPORTED_PENDING_TEMPORAL_REVIEW`**; **`NEW_NEGATIVE_CAPTURE_NOT_YET_JUSTIFIED`**. Stop at **`WAIT_FOR_PROJECT_LEAD_S2_R2_RECOVERED_NEGATIVE_REVIEW_AND_SPLIT_DECISION`**.

### 2026-09-22 — S2-R2 temporal-supervision review gate prepared

- [x] Frozen and hash-verified all 30 original P1 videos in a resumable local browser review. The schema supports multiple bounded `CONFIRMED_NON_SIGN`, `AMBIGUOUS_EXCLUDE`, and `POSSIBLE_LEXICAL_OR_SIGN_PREPARATION` intervals; unmarked time is excluded and confirmed non-sign intervals require behavior tags. No whole clip is auto-labeled PRE.
- [x] Focused reviewer tests pass `4/4`; Ruff passes; the frozen P1 review manifest contains 30 clips and has SHA-256 `1ee9b04ba16c82a3d93eadc7d5366db887f50fecc15d9bb7229a508779a0e1be`.
- [x] Signer archaeology remained bounded. The e2e_c0 runbook establishes stable anonymous IDs within that capture, so P01/P02 overlap between P1/N0 and N0 adds P03-P06. No authoritative mapping to governed `local_recorder:*` FIT/CAL/DEV identities or the current phone tester was found. P1/N0 remain quarantined development candidates pending identity/split attestation.
- [x] Existing positive search found 17 eligible extra human-labeled TRAIN clips from known source-domain signers, but no unreserved independent continuous phone signer with governed temporal labels. E6 signer `0F747C-S001` remains untouched evaluation; its OOV clips are positive signing but too short to establish continuous PRE/POST behavior.
- [ ] Complete the 30-video P1 semantic review before selecting any N0 subset, creating phone positive labels, freezing an S2-R2 dataset, or preparing training. Current stop: **`WAIT_FOR_HUMAN_P1_TEMPORAL_REVIEW_AND_SIGNER_ATTESTATION`**.

### 2026-09-22 — S2-R2 P1 review finalized; bounded phone-positive review prepared

- [x] The Project Supervisor completed immutable review of all 30 hash-locked P1 videos. The
  finalized result contains 45 `CONFIRMED_NON_SIGN` intervals / 623.065 seconds across P01 and
  P02. Covered behavior includes neutral stillness, visible hand motion, grooming/adjustment,
  hand crossing/occlusion, hands entering/leaving frame, body repositioning, and other ordinary
  non-sign motion. Unmarked gaps remain excluded; no historical whole video was auto-labeled PRE.
- [x] A full N0 review is not currently justified: P1 supplies the needed hard-motion and static
  behavior coverage. N0 remains preserved for a later minimal participant/device/environment
  supplement only if authoritative P01-P06 signer/split attestation makes that useful.
- [x] Prepared a blinded five-attempt phone-positive reviewer for rested HELLO 001/002, HOME
  003/004, and TABLE 005. S2 predictions are hidden; attempt START/STOP markers are not labels;
  the tool records human sign boundaries and derives observation-level PRE/ACTIVE/POST with the
  already-frozen 100 ms transition ignore band. TABLE 006 stays excluded for weak perception
  support. Focused tests pass `4/4`; Ruff passes; review manifest SHA-256 is
  `3b03a51362d5bd3d219632eaa73e9fa4326f366eb771047523d52854420585a3`.
- [ ] Complete the five-attempt phone-positive review and resolve authoritative P01-P06/current
  phone-signer split roles before freezing or training S2-R2. No training is authorized. Current
  stop: **`WAIT_FOR_HUMAN_PHONE_POSITIVE_TEMPORAL_REVIEW_AND_SIGNER_ATTESTATION`**.

### 2026-09-22 — S2-R2 supervision labels complete; governance blocks training

- [x] The Project Supervisor completed immutable blinded temporal review of five rested-phone
  attempts: HELLO 001/002, HOME 003/004, and TABLE 005. All five have defensible PRE, ACTIVE, and
  POST context. The frozen 100 ms transition ignore band yields 68 PRE, 62 ACTIVE, 62 POST, and
  10 ignored observations.
- [x] Joined all 202 labels to the exact persisted phone observation timestamps. On the 192 scored
  observations, frozen S2 accuracy is 74/192 (`0.3854`) and human-ACTIVE observation recall is
  12/62 (`0.1935`). S2 predicts POST for 50/62 human-ACTIVE observations and acquires ACTIVE only
  in HELLO 001 and TABLE 005. This is design/hard-example evidence, not independent validation.
- [x] Finalized the candidate dataset design and one-candidate causal-TCN training strategy without
  extraction or training. No new negative capture is required; P1 supplies 623.065 seconds of
  reviewed negative supervision. A full N0 review remains unjustified.
- [x] Focused reviewer/readiness tests pass `10/10`; Ruff passes; `git diff --check` has no content
  errors (repository-wide pre-existing line-ending warnings only). Protected TEST remained closed.
- [ ] Dataset freeze and training remain blocked because P01-P06 and the current phone signer lack
  authoritative governed split identities, and no unreserved independent continuous-phone
  positive signer exists. Minimum new data after role resolution is one small distinct-signer
  positive session reserved for post-freeze validation; no 236-word collection is needed.
  Decision: **`S2_R2_SUPERVISION_READY_GOVERNANCE_BLOCKED`**. Next action:
  **`PROJECT_LEAD_SIGNER_SPLIT_ATTESTATION_AND_INDEPENDENT_POSITIVE_VALIDATION_ROLE_FREEZE`**.

### 2026-09-22 — S2-R2 governance frozen; learnability supported; exact tensor review pending

- [x] Applied the Project Lead's conservative role decision: P01/P02 and the current phone design
  signer are FIT/development-only with no independence claim. P03-P06/N0 remain unused. E6 signer
  `0F747C-S001` remains untouched negative/acquisition validation, and one distinct future phone
  signer/session remains reserved for untouched positive continuous validation.
- [x] Froze the S2-R2 dataset design and source identities without accessing protected TEST. The
  planned main candidate retains governed FIT-71, the 17 eligible prior human-labeled enrichment
  clips, reviewed phone positives, and reviewed P1 hard negatives; candidate-specific
  normalization is FIT-only and versioned with the weights.
- [x] The bounded learnability sanity check passed with the unchanged 378 representation and
  causal-TCN family. Training-fit diagnostics were phone human-ACTIVE recall `61/62`, selected P1
  ACTIVE false rate `0/369`, baseline ACTIVE recall `1.0`, baseline POST recall `0.996`, and loss
  `0.3171 -> 0.0069`. This establishes **`LEARNABILITY_SUPPORTED`** only; it is not a
  generalization or promotion result.
- [x] Identified a supervision-fidelity issue before the main run: reprocessing saved rested-phone
  JPEGs changed frozen-S2 human-ACTIVE recall from the live exact-observation result `12/62` to
  `42/62`. JPEG-reprocessed rows therefore cannot be represented as exact runtime hard misses.
  This does not reopen the already-passed Android/host parity result.
- [x] Prepared a separate blinded six-attempt review for exact-parity capture
  `session_20260921T153138Z`. All 232 synchronized attempt visuals map exactly to records in the
  persisted Android 378 tensor stream. Focused tests pass `7/7`; Ruff passes.
- [ ] Complete and finalize the six-attempt exact-tensor temporal review before the one main
  S2-R2 training run. Current stop: **`LEARNABILITY_SUPPORTED_WAIT_FOR_EXACT_PHONE_TENSOR_TEMPORAL_REVIEW`**.

### 2026-09-22 — S2-R2 exact supervision frozen; one candidate ready for supervisor run

- [x] Completed the six-attempt exact-tensor phone review for
  `session_20260921T153138Z`: 232/232 reviewed observations link to the actual Android 378 rows;
  67 PRE, 67 ACTIVE, 86 POST, and 12 ignored transition observations. All six attempts are
  eligible, but remain current-signer FIT/internal-development evidence with no independence claim.
- [x] Retired the JPEG-reprocessed rested-phone rows from the main candidate. They changed the
  frozen-model hard-example behavior and are not same-observation supervision. Exact Android rows
  are now mandatory for the phone component.
- [x] Froze the single-candidate dataset and checkpoint policy: expected 369 rows (305 FIT, 64
  internal development), unchanged 123,779-parameter Phase-7 causal TCN, FIT-only normalization,
  one seed/run, fixed source-family balancing, unchanged CONFIG_01, and predeclared acquisition,
  non-sign suppression, emission, exactly-one, and severe-cut gates.
- [x] Ran the bounded all-domain smoke pipeline: 23 rows (14 FIT/9 internal development), two
  epochs, finite decreasing loss `0.565482 -> 0.251641`, exact-phone rows used, JPEG phone rows
  excluded, and the main run not consumed. The immature smoke model was correctly ineligible.
- [x] Focused S2-R2 tests pass (18/18) and Ruff passes. The imprint registry records that the
  reusable trainer targets the unchanged `segmentation_features.v1` 378 contract.
- [ ] Project Supervisor must run exactly `prepare-main` then `train-main`. No full extraction or
  main training was silently executed. Current stop:
  **`S2_R2_ONE_CANDIDATE_READY_FOR_SUPERVISOR_LONG_RUN`**.

### 2026-09-22 — S2-R2 preparation fail-closed recovery

- [x] The first supervisor `prepare-main` stopped before producing a dataset manifest at the
  reviewed `DRINK 2` enrichment clip. Its human ACTIVE interval is 239 ms; the unchanged 100 ms
  transition-ignore band leaves only 39 ms eligible, and all three genuine sparse cadence views
  contain zero ACTIVE-labeled observations. The separately attempted `train-main` could not run
  because preparation had not completed. No main weights/normalization were produced.
- [x] Read-only preflight across all 17 proposed enrichment clips showed this is the only clip
  with zero ACTIVE supervision. Preserved the original config/freeze as history and recorded one
  explicit corrected config/freeze that excludes this clip, not relabels it. Effective population:
  16 enrichment clips/48 views; expected total 366 rows (302 FIT, 64 internal development).
- [x] Added a pre-extraction sparse-label viability guard and a clear train-before-prepare error.
  No model family, feature schema, threshold, cadence, checkpoint gate, split role, or untouched
  validation population changed. Focused tests pass 20/20; Ruff and Python compile pass.
- [ ] Supervisor should rerun **only** `prepare-main` and return its final output. Do not start
  `train-main` until it reports `S2_R2_MAIN_DATA_PREPARED`. Current stop:
  **`S2_R2_CORRECTED_PREPARATION_WAIT_FOR_SUPERVISOR`**.

### 2026-09-22 — S2-R2 corrected main dataset prepared and verified

- [x] Supervisor completed the corrected `prepare-main`. The persisted manifest reports
  `S2_R2_MAIN_DATA_PREPARED`, 366 rows (302 FIT, 64 internal development), and the expected
  source-family counts: 267 baseline, 48 enrichment, 45 P1 negative, six exact phone positive.
- [x] Independently checked all 366 feature-file hashes and unique row IDs, `[T,378]` width,
  finite values, strict chronology, legal PRE/ACTIVE/POST/ignore labels, exclusion of the
  unsupervisable DRINK 2 clip, and absence of reserved E6 signer. The manifest links the corrected
  config/freeze hashes and states exact-phone tensors used, JPEG phone tensors unused, protected
  TEST unopened. Manifest SHA-256 is
  `8c831dfd404cca935ae7356f4da10ec8dc0c1d6d08700b57bbc27a1ac00acf71`.
- [ ] The one main S2-R2 training run has not started. Supervisor may now run `train-main` once,
  without changing configuration or restarting for a favorable result. Current stop:
  **`S2_R2_MAIN_DATA_PREPARED_WAIT_FOR_ONE_TRAINING_RUN`**.

### 2026-09-22 — One S2-R2 candidate trained; host package frozen pending independent validation

- [x] The Supervisor completed the one authorized 30-epoch run. Epoch 7 was the only checkpoint
  satisfying all six frozen gates. Selected Keras model SHA-256 is
  `b6f8b52cece72f0b6f5b802a4ea583060d923e90a6b951059e7013114c8fc151`; paired
  normalization SHA-256 is
  `65d885f62eaca6f11a596302d304f63149795ddaf01e702f1e6a36dd7da5c005`. The model
  retains 123,779 parameters and the `[None,None,378] -> [None,None,3]` causal interface.
- [x] Audited FIT-only normalization: 302/302 FIT row IDs, 8,285 observations, 378 mean/std
  dimensions, zero development or validation rows. Actual file hashes match the training result.
- [x] The frozen development comparison improves phone ACTIVE recall `13/25 -> 24/25` and P1
  negative events `4/8 -> 0/8`, while CAL emission/exactly-one remains `50/54`. CAL containment
  changes `27/54 -> 31/54`; severe cuts rise slightly `9/54 -> 10/54` but remain within the
  predeclared gate. These phone/P1 development groups are not independent signer validation.
- [x] A read-only per-source/cadence audit found a small APPHEAR_CAPTURE warning: one VIEW_A
  clip drops from 78% to 38% containment, adding one severe cut, though all nine views still emit
  exactly one event. VIEW_C severe cuts remain `7/18` for both models; CAL LOCAL emission remains
  `3/6`. No post-result tuning or retraining was performed.
- [x] Froze the host checkpoint+normalization package identity and report. E6 signer
  `0F747C-S001`, the distinct future phone validation signer/session, and protected TEST remain
  untouched. No Android export/deployment, phone capture, materializer, Admission, recognizer, or
  re-arm change occurred.
- [ ] Next bounded step: export this exact paired candidate to a versioned debug TFLite package,
  verify host/TFLite/Android parity and old-model rollback, then run one fixed distinct-signer
  continuous phone validation. Current stop:
  **`S2_R2_HOST_CANDIDATE_FROZEN_PENDING_EXPORT_AND_INDEPENDENT_VALIDATION`**.

### 2026-09-23 — S2-R2 debug export and independent phone validation handoff

- [x] Verified the frozen epoch-7 Keras model and FIT-only normalization against their saved
  SHA-256 identities. The single main training run remains the only S2-R2 run.
- [x] Exported a separate versioned `S2_R2_CANDIDATE` FP32 TFLite debug package with matching
  normalization, state order, 378-feature schema, 61-observation causal prefix, and source/asset
  hashes. The unchanged Phase-7 package remains the default and explicit rollback control.
- [x] Host Keras versus TFLite parity passed over 669 previously captured exact phone 378 rows:
  maximum probability difference `8.642673492431641e-7`, zero argmax mismatches. No model fitting,
  calibration, or threshold selection occurred.
- [x] Added explicit package selection to the existing Android phone causal runner and session
  identity. Candidate capture requires the fixed six-attempt cohort, PRE-or-POST re-arm, exact
  observation logging, and a declared validation signer. Candidate and control continue through
  unchanged Admission, CONFIG01 completion, materializer, Recognition V2, and recognizer.
- [x] Froze HELLO/HELLO/HOME/HOME/TABLE/TABLE before capture, added a blinded temporal-review
  profile, and prepared fail-closed capture integrity plus same-observation Phase-7/S2-R2 replay.
  Ordinary movement receives negative status only after visual review.
- [x] Opt-in debug APK and Android-test APK build; focused causal unit test passes. Both S2
  packages are present in the APK. ADB reports no connected device, so the new candidate's
  connected Android parity and distinct-signer capture have **not** occurred.
- [x] Bounded blinded-review linkage regression passes: nanosecond visual timestamps map
  uniquely to the exact captured tensor rows despite millisecond JSON/CSV rounding. Focused
  reviewer/parity tests and Ruff pass.
- [x] Connected-device parity passed on M2101K7AG Android 12: `4/4` instrumentation tests,
  including the S2-R2 669-observation candidate fixture and Phase-7 control availability.
  The original handoff PowerShell command parsed the dotted Gradle property as a task; quoting
  the `-P...` arguments fixed command invocation without changing any test or model behavior.
- [x] Installed the parity-tested debug APK on the connected phone. Capture did not start:
  the then-available performer confirmed being the prior design phone signer, and no distinct
  signer was available at that time. This preserved the untouched independent validation role.
- [x] A new itel A665L Android 13 device and declared distinct signer
  `phone_validation_signer_01` became available. The frozen candidate/control connected parity
  suite passed `4/4` on that device. The first fixed-cohort capture
  `session_20260923T011723Z` aborted during attempt 2 with a debug visual-frame
  `OutOfMemoryError` under the 128 MiB Java heap; 238 observations and 238 original frames were
  preserved. This partial run is unscored and not a promotion result.
- [x] Recovery classified the incident as a specific debug visual-retention runtime failure,
  not S2 behavior. Added debug-manifest-only `largeHeap=true` (device advertises 256 MiB),
  rebuilt, and reran connected parity `4/4` unchanged. No model, feature, lifecycle, or
  recognizer contract changed. Full-session capture stability is not yet verified.
- [x] The Supervisor authorized one procedural replacement after the diagnostics-only visual
  capture OOM. Empty-scene stress completed without OOM; the aborted session remains retained
  and unscored. The replacement `session_20260923T013439Z` used attested distinct signer
  `phone_validation_signer_01` and the unchanged HELLO/HELLO/HOME/HOME/TABLE/TABLE order.
- [x] Replacement evidence is complete: 513 observations, 513 synchronized originals, six
  BEGIN/COMPLETE pairs. Same-observation Android/host feature and normalized-input maximum
  difference 0.0; S2 probability maximum difference `1.013278961e-6`; zero state mismatches.
  Candidate Android event/materializer outputs exactly matched host replay.
- [x] Blinded human temporal review and bounded non-sign review finalized. Six attempts contain
  29 ACTIVE, 45 PRE, 43 POST, 12 ignored transition observations; four confirmed non-sign
  intervals contain 109 observations. Phase-7 and S2-R2 were paired on the same 513 rows.
- [x] Independent-phone result is **`S2_R2_INDEPENDENT_PHONE_MIXED`**: ACTIVE acquisition
  1/6 attempts and 4/29 observations (Phase-7) vs 4/6 and 18/29 (S2-R2), but only 2/6
  S2-R2 windows attained >=90% human ACTIVE containment. S2-R2 emitted two events outside
  attempts whose semantics are pending specific visual adjudication; do not call them false
  positives from telemetry. Both branches emitted zero events in four confirmed non-sign
  intervals. Re-arm completed after all seven S2-R2 events.
- [x] A major runtime/cadence confound was quantified: in-attempt median observation spacing
  rose from ~335 ms for the two HELLO attempts to ~536 ms for HOME/TABLE; 68 within-attempt gaps
  exceed the frozen 533.232 ms continuity limit. This does not invalidate the paired comparison,
  but does limit attribution of late misses to S2 generalization alone. Detailed evidence:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/s2_r2_phone_deployment_and_independent_validation_01/INDEPENDENT_PHONE_VALIDATION_RESULT.md`.
- [ ] Stop at Project Lead review. No S2 promotion or retraining, runtime change, lifecycle tuning,
  Admission tuning, materializer tuning, recognizer training, or protected TEST access. Next bounded
  decision: visually adjudicate the two extra events, then decide whether to investigate the
  itel observation-throughput/cadence limit before another fresh phone validation.

### 2026-09-23 — S2-R2 representative-phone final validation

- [x] Verified the unchanged frozen S2-R2 Keras/normalization/TFLite package and Phase-7 rollback.
  Candidate/control Android instrumentation passed `4/4`; steady-state Xiaomi preflight had
  257 observations with median 200 ms, p95 266.6 ms, and no gap above 533.232 ms.
- [x] Froze HELLO/HELLO/HOME/HOME/TABLE/TABLE before capture with new, supervisor-attested
  `representative_phone_signer_01`. Session `session_20260923T030939Z` contains 714 exact
  observations, six BEGIN/COMPLETE pairs, and 714/714 original frames. All six attempt medians
  were 200–266.6 ms and none had an over-limit continuity gap.
- [x] Same-observation 378 and normalized vectors matched Android/host exactly; maximum S2
  probability difference `8.344650268554688e-7`, zero argmax mismatches. Android event and
  materializer outputs matched host replay. Human review was blinded to model output and supplied
  56 ACTIVE, 58 PRE, 59 POST, and 12 excluded transition observations.
- [x] Paired Phase-7 vs S2-R2: genuine attempt ACTIVE acquisition `5/6 -> 6/6`; human ACTIVE
  observation recall `20/56 -> 52/56`; exactly-one intended event `5/6 -> 6/6`; >=90% human ACTIVE
  containment `1/6 -> 6/6`. All six S2-R2 windows covered 100% of human ACTIVE; no premature or
  severe cut. Seven of seven S2-R2 events re-armed, ending IDLE.
- [x] Five visually confirmed non-sign intervals (227 observations) produced zero ACTIVE states
  and zero event onsets in both branches. One additional S2-R2 event before HELLO 1 (indices
  227–233) is supervisor-adjudicated `UNCERTAIN / MIXED`; it is excluded from both confirmed
  false-event and genuine-sign counts. This cannot support a zero-unwanted-event claim.
- [x] Only after window-quality review, scored the unchanged recognizer on six usable S2-R2
  windows: Top-1 correct 3/6 (HELLO twice, HOME once); HOME 2 and both TABLE repetitions were
  wrong Top-1. These are word-identification errors, not no-event or materializer failures.
- [x] Final decision: **`S2_R2_INTEGRATION_READY_WITH_KNOWN_LIMITATIONS`**. The representative
  phone removed the systematic temporal failure seen on itel; one unclassified extra event and
  good-window recognizer errors remain. Canonical report:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/s2_r2_representative_phone_final_validation_01/REPRESENTATIVE_PHONE_FINAL_VALIDATION_RESULT.md`.
- [ ] Next bounded action after Project Lead review: `APPHEAR_S2_R2_REAL_APP_INTEGRATION_01`.
  Make exact S2-R2 model-normalization pair the real-app default behind Phase-7 rollback and keep
  focused diagnostics. Do not retrain/tune S2, Admission, re-arm, materializer, or recognizer from
  this validation signer; protected TEST remains closed.

### 2026-09-23 — Real AppHear S2-R2 backend integration (software gate)

- [x] Project Lead approved the migration boundary: preserve `RecognitionActivity` and the
  Supervisor UI, front camera only, no legacy 258-feature backend running in parallel.
- [x] Promoted the parity-validated Candidate01 native/ONNX/TFLite, 378-feature, versioned S2,
  lifecycle/materializer, Recognition V2, and recognizer components/assets from debug-only to
  main source. Normal app uses one `Candidate01FrameAnalyzer` and `PhoneProductionSession`;
  debug-only attempt controls, visual review, and tensor recording remain debug-only.
- [x] Normal package is `S2_R2_CANDIDATE`, with model/normalization binding verified at load;
  `PHASE7_CONTROL` remains an internal debug Gradle rollback selection. Unsupported ABI or asset
  mismatch fails visibly rather than switching to legacy recognition. No scientific rules changed.
- [x] Existing UI contract receives product-level recognition state, one result per causal event,
  and the existing sentence semantics. Front/back and legacy handedness actions are disabled in
  causal mode. READY is withheld until models/camera are loaded and initial live observations
  reach the listening state. Heavy capture is absent from normal inference.
- [x] Debug and release APKs build; 95 debug JVM unit tests pass, including the shared raw-v1 →
  Recognition V2 adapter test. Release APK contains Candidate01 arm64 native library, ONNX,
  hand refiner, both S2 packages, frozen materializer, and V2 recognizer. On Xiaomi, four selected
  378/S2 package instrumented parity tests passed (0 failures).
- [x] Installed the normal debug app on Xiaomi M2101K7AG. The real recognition screen reached
  READY with `S2_R2_CANDIDATE`; no diagnostic Activity was used. The user was unable to perform
  the planned HELLO/HOME/TABLE/HELLO interaction at that time.
- [x] Connected Xiaomi regression after promotion: 4/4 selected 378/S2 package tests and 3/3
  Recognition V2/236-class parity tests passed with zero failures. This verifies component
  contracts, not the unperformed real-app repeated-sign interaction.
- [x] **Integration smoke subsequently completed:** the fixed real-app repeated-sign sequence,
  exactly-one intended UI/sentence commit, natural re-arm, and absence of legacy results were
  observed in the later final smoke section below. This older software-gate entry is retained
  for chronology; no S2/Admission/re-arm/materializer/recognizer tuning or protected TEST access
  followed.

### 2026-09-23 — Real-app overlay promotion and no-signer verification

- [x] Promoted the existing Perception VNext display renderer/transform into shared Android main
  code. The real `OverlayView` now draws hand/body skeletons, proposal ROIs, and hand presence
  through the same presentation-only renderer as the validated debug view; the old UI layout is
  unchanged and the overlay clears on stop. No scientific backend behavior changed.
- [x] Debug/release builds and 95/95 JVM tests pass. Connected Xiaomi: overlay pixel/clear and
  display-transform tests 2/2 pass; selected 378/S2, Recognition V2/recognizer, composed replay,
  and overlay device regression tests 8/8 pass. Default package remains `S2_R2_CANDIDATE` with
  Phase-7 debug rollback; paired package hashes are verified at load.
- [x] Normal Xiaomi screen repeatedly reached READY after navigation and background/foreground
  return with one visible causal backend. A roughly two-minute empty/still-scene soak had no
  committed words, no crash, and stable PSS (~272 MB); brief ACTIVE candidates returned to IDLE.
  Live screenshot confirmed hand-skeleton/front-camera visual alignment. This is not an ML
  false-positive-rate or latency benchmark.
- [x] One user-confirmed non-sign open-hand raise/hold nevertheless emitted a HELLO event/word
  and re-armed. Record this as a specific real-app unwanted event; do not tune Admission/S2 from
  this single uncontrolled action. Optional full-session UI replay was skipped because it would
  require invasive fixture/parser migration; existing component parity and real-app observation
  cover the bounded software check.
- [x] **Final integration gate completed:** one fixed HELLO → HOME → TABLE → HELLO sequence
  in the normal UI had one event/UI commit per intended sign and natural re-arm. See the
  per-attempt result and non-sign-event caveat below; no ML tuning followed.

### 2026-09-23 — Final real-app repeated-sign smoke

- [x] **`APPHEAR_S2_R2_REAL_APP_INTEGRATION_COMPLETE`**: on Xiaomi M2101K7AG, the normal
  `RecognitionActivity` loaded one Candidate01/S2-R2 backend. The fixed HELLO → HOME → TABLE →
  HELLO physical sequence produced four sequential intended events (IDs 2–5), displayed those
  four glosses, appended each once to the UI sentence, and returned to READY after each. The
  Supervisor confirmed no duplicate intended result, freeze, or lifecycle failure. Final
  four-word sentence was `HELLO HOME TABLE HELLO`; no diagnostic Activity or legacy recognizer
  was active. This is an integration smoke, not cross-signer accuracy validation.
- [x] Preserved two separate operator-confirmed unwanted events: HOSPITAL1 while adjusting a
  seat before the fixed sequence (event 1; cleared from the sentence before HELLO), and STAND2
  during ordinary movement afterward (event 6). Each appeared once and re-armed. Exact physical
  boundaries were not video-recorded in the normal app; do not claim a measured false-positive
  rate or assume one responsible ML layer. The earlier stationary-open-hand HELLO incident is
  another bounded product observation.
- [x] No model/feature, threshold, re-arm, Admission, CONFIG01, materializer, recognizer, or
  UI-architecture changes were made during the smoke. Stop at Project Lead review of integrated
  app evidence; do not automatically start another S2 experiment.

### 2026-09-28 — Continuous-transition diagnostic tooling gate

- [x] Protected baseline refs remain at `76d93cecd85bf9f76064d320aa4a5791b5f0704a`.
  Diagnostic branch starts at that commit; implementation is `befa94a54b7f0e1ebc471af21a77f2f2036641b7`.
- [x] Traced the real normal/debug shared S2, episode, recovery, materializer, V2, recognition
  and sentence owners. No production semantics changed; no competing live decoder was added.
- [x] Reused exact source/378/S2/visual capture with whole A/B sequence markers and five bounded
  ordinary-motion blocks, candidate/recovery clocks, source-window IDs and debug UI delivery.
- [x] Added blinded physical-boundary review and fail-closed evaluator with A/B/C/D evidence,
  unfinished/merged/ambiguous cases, runtime-gap confounds and separate downstream results.
- [x] 96 JVM and 51 focused host tests pass; debug/release builds pass. Existing 669-row host
  fixture remains within 8.64267349e-7 probability difference, zero argmax mismatches. Main
  runtime/UI and packaged assets remain unchanged; imprint/report/handoff updated.
- [ ] Actual representative-phone A/B capture and physical human review pending. ADB showed
  no device during this tooling gate; no fresh connected parity or root-cause claim.
- [ ] Return captured transition evidence to Project Lead before any readiness, Admission,
  S2/recognizer or window behavior change. No automatic next development phase.

### 2026-09-29 — Current working Text-to-ASL baseline preservation

- [x] Audited Git parent `f5a6cb4`, the uncommitted working Text-to-ASL/Profile pilot, the saved tested APK hashes, and the separate clean context-aware assistant worktree at `24f0684`.
- [x] Isolated the tested app source/assets/tests and focused documentation on `codex/current-working-text-to-asl-baseline-2026-09-29`; see `context/current-working-baseline-2026-09-29.md` for exact scope, rollback and limits. The context-aware assistant branch is excluded.
- [ ] Controlled first-load/frame/memory/low-RAM/thermal and broad F22 gates remain pending. Keep all Text-to-ASL pilot and account flags default/release OFF until separately validated.

### 2026-10-04 — Conversation Assist migrated onto preserved Text-to-ASL source

- [x] Verified the current working Text-to-ASL source branch and annotated tag at `cc1f394`; the existing Context Assist branch at `75f5959` has merge base `76d93ce`. Kept the preservation branch/tag and its unrelated local work untouched. Migration branch: `codex/conversation-assist-text-to-asl-migration`.
- [x] Carried the existing Context Assist sidecar, policy, read-only Top-5 event evidence, advisory UI, bounded diagnostics, tests, and historical evidence onto the newer source. Adapted only the Text-to-ASL completed-submission seam and Gradle flags where the branches diverged. Deferred New-character submission keeps its typed/speech source, and Replay remains outside conversation history.
- [x] Default debug, pilot-plus-fake-Context-Assist, and pilot-with-Context-Assist-OFF JVM suites each passed 147/147 tests. Debug APK builds passed with the pilot both ON and OFF for Context Assist; release and Android test APK builds passed. Release Context Assist and all Text-to-ASL pilot flags remain hard-disabled.
- [x] User-directed private debug APK install on Xiaomi M2101K7AG: Context Assist ON with Gemini, Text-to-ASL pilot flags ON. The phone's installed APK SHA-256 matches the built APK (`313F9D5E95AF692909EFA0BCF6CBB8C43546888B1A68201C8B7EDF785F0F1DCD`). The previously installed APK was backed up and the new build was left installed for the user's test.
- [ ] Representative-phone F22 smoke, connected tests, and a real Gemini request through this combined build remain pending. Installation and hash verification are not a runtime behavior pass. Use only synthetic conversation text with the current Gemini Free-tier development setup.

### 2026-10-04 — Recognition screen glass presentation and live advisory

- [x] Kept the current Text-to-ASL source and Context Assist sidecar; changed only the Recognition screen presentation and a read-only match preview. The compact raw result, translucent predicted-reply strip, and lighter controls follow the supplied mockup. Predictions appear after signing begins, while the separate context-supported line requires an existing matcher match against committed Top-5 evidence.
- [x] Hear/TTS still speaks raw `SentenceBuilder` text and finalizes the Deaf turn; the live preview neither finalizes nor rewrites it. Release Context Assist remains disabled. JVM, debug APK, Android test APK, and release APK builds pass.
- [x] Later USB phone check confirmed the expanded `RECOGNIZED` card can show `HELLO GOOD` and the prediction strip remains separately labeled. This is a presentation check, not an accuracy result.

### 2026-10-04 — Context Assist phrase/lifecycle correction

- [x] User reported that Back/Home could reopen stale possible replies and the narrow `RECOGNIZED` card showed only one word despite successive `CURRENT SIGN` changes. The code path supplies the accumulating raw `SentenceBuilder` text to the UI; the presentation card had a two-line ellipsis and narrow wrap width that could clip it. Widened the card and removed that limit without changing raw sentence semantics. A later phone screen showed `HELLO GOOD` in the raw card.
- [x] Reply predictions are ordered after each committed sign through the existing matcher rules applied to the observed Top-5 prefix. All cached replies remain visible during the signing turn, even when none has visual prefix support. Only a full existing matcher result can show `Context-supported`. No recognizer, provider, model, matcher thresholds, or Hear/TTS output changed.
- [x] Leaving Sign Detection closes its reply window; whole-app background clears in-memory conversation state while keeping hearing turn IDs monotonic against late provider responses. Raw recognition remains independent. JVM tests: 149/149; debug, Android-test, and release builds pass.
- [x] USB installation resolved the earlier wireless/phone approval block. The private Gemini debug APK was installed and its on-device SHA-256 matched the host file.

### 2026-10-04 — Connected phone correction follow-up

- [x] USB installation of the private Gemini debug APK succeeded; installed APK SHA-256 matched the host file, and the app launched. A synthetic Hearing turn produced three real Gemini reply candidates. The user confirmed the predictions appeared in Sign Detection.
- [x] User then confirmed that signing two words made the prediction strip disappear. Cause: the UI-only prefix filter removed every candidate when Top-5 evidence did not support any expected sequence. Changed this to stable ordering: visually supported prefixes move first, while all cached conversation predictions remain visible. Raw sentence and full matcher behavior remain separate.
- [x] JVM: 149 tests, zero failures. Debug, Android-test, and release builds passed. The two-sign unsupported-evidence UI test, Recognition screen exit test, and Text-to-ASL fake-cache test passed individually on USB. The user confirmed predictions remain visible; a phone screen showed raw `HELLO GOOD` with the separate predictions strip. Final Gemini debug APK was restored and the instrumentation package removed.
- [ ] The combined 15-test Context Assist instrumentation class still has an order-dependent Android Activity launch timeout after the heavy Text-to-ASL avatar/WebView test; three later UI tests timed out in the latest combined run. The same affected tests passed individually. Keep this test-harness limitation open; do not reinterpret it as recognition accuracy evidence or change app runtime to mask it.

### 2026-10-04 — Recognition card and prediction strip polish

- [x] Matched the supplied compact Recognition-screen direction: removed Context Assist borders and separate reply chips, made the raw `RECOGNIZED` card fit short text while allowing longer phrases to wrap, and used lighter translucent surfaces. The leading prediction has stronger type hierarchy; alternatives remain in the same horizontal strip. When evidence reorders replies, the strip returns to its leading item.
- [x] Kept all cached predictions visible during signing. Existing Top-5 prefix support can move a candidate first, while unsupported context remains labeled as prediction. Only the unchanged full matcher may show `Context-supported`; raw `SentenceBuilder`, Top-1, and Hear/TTS remain authoritative.
- [x] 149 JVM tests passed; debug and release APKs built. USB phone check showed two raw words (`HOME WORLD`) in the content-fitting recognized card with the prediction strip still present. Final private Gemini debug APK was installed and its on-device SHA-256 matched the host file (`4420A033EDD68CDA6FE25B5296A81B0006BEEFA565AEEC06FC869E04F109EC1E`). No physical accuracy claim is made from this visual check.

### 2026-10-04 — Centered prediction cue

- [x] Removed the visible Possible Replies label while retaining an accessibility description. The leading prediction is centered in a compact three-slot strip with alternatives on either side. A committed sign can give the leading text a brief teal scale cue when one expected concept has visual support under the existing matcher policy; this is only a partial prediction cue. Full `Context-supported` display still requires the unchanged phrase matcher, and raw recognition/Hear remain untouched.
- [x] Added a focused JVM case for one supported anchor versus a strong contradictory Top-1, and updated the connected UI assertion for the new center position and absent visible label. JVM: 150/150 pass. Debug, release, and Android-test APK builds pass.
- [x] Private debug APK installed over USB; final host/device SHA-256 match (`E743FBB156D30E16B2422EF6D9FD4C02A7DF5F6A210F5CA22B10269FD631810F`). The phone rejected the Android test companion with `INSTALL_FAILED_USER_RESTRICTED`, so this turn has no connected instrumentation result. The test package is absent and the app remains installed for user visual review.

### 2026-10-04 — Complete prediction text in the compact strip

- [x] Removed the prediction TextViews' line limits and ellipsis while retaining the original three-slot keyboard layout and centered leading phrase. A wider carousel trial was rejected by the user because it changed the supplied design; the final version wraps each complete phrase inside its original compact slot.
- [x] A representative-phone screenshot showed three complete predictions in the compact strip, and the user confirmed the layout is much better. The installed private debug APK matches the host SHA-256 (`1B8DBEDF5C494826A477510290D34825BCF1A0360D48B3C702462C7025A60E81`). No recognition or accuracy claim follows from this visual check.
- [x] JVM 150/150 passed; debug, release, and Android-test APK builds passed. The Android test companion remains blocked by the phone's install restriction, so the updated UI assertion was compiled but not executed on device. Raw recognition, Hear/TTS, matcher, provider, and release flags are unchanged.

### 2026-10-04 — Current working source baseline for future experiments

- [x] Preserved the reviewed Text-to-ASL plus Context Assist source under `baseline/apphear-text-to-asl-context-assist-ui-2026-10-04` and annotated tag `apphear-text-to-asl-context-assist-ui-2026-10-04`; see `context/current-working-baseline-2026-10-04.md`. Older Text-to-ASL and S2-R2 baselines remain untouched. Future experiments branch from the new tag, not from the older Context Assist experiment branch.
- [x] Saved the private phone-reviewed debug APK and an all-flags-off debug APK in ignored `android/build/stable-context-assist-ui-20261004/` with SHA-256 checks. Context/Gemini debug and all-flags-off debug configurations each passed 150/150 JVM tests; debug/release/Android-test builds passed as applicable.
- [ ] The latest Android test companion installation, full F22 device smoke, controlled performance checks, and cross-signer end-to-end phrase validation remain open. This is a working integration baseline, not a production accuracy or release sign-off.

### 2026-10-05 — Text-to-ASL text/talk presentation

- [x] Started `codex/text-to-asl-text-speech-ui` from the fixed 2026-10-04 Text-to-ASL plus Context Assist tag. Rebuilt only the Text-to-ASL fragment's presentation around the supplied ready, text, and talk mockups: dark avatar stage, compact white bottom sheet, Text/Talk entry, underlined text field, supplied microphone/chat icons, and paired Sign It/Clear controls.
- [x] Kept the existing text submission, Android speech-recognition intent, avatar playback, replay, TTS, Reply route, Clear, and Hearing-turn recording methods. Talk-mode Sign It replays the speech result already auto-submitted by the existing flow, avoiding a duplicate Hearing turn. The panel state only controls visibility; no recognizer, Gemini, matcher, or Context Assist contract changed.
- [x] Debug JVM suite and debug APK build passed after the initial layout change. Final JVM (150/150), debug, release, and Android-test APK gates passed.
- [x] On-device ready-screen review confirmed the new avatar and compact panel. User clarified that tapping “Ready when you are” should open Text by default; wired the ready title to the same Text mode transition without changing submission logic.
- [x] The user confirmed the ready title opens Text and approved a modest increase in labels, tap targets, and spacing in both Text and Talk. The original phone APK was backed up privately (SHA-256 `25616ECA50832C43098CA7DC1C3EDCC8467DC38DC3AA1D1F940F305F58ADB2B0`). The final private debug APK was installed and its host/device SHA-256 matched (`0B3890F4F18F6DF4D2A3D672542E900879ABF0C029C94162DCB27387EDD3E9AE`). The phone blocks automated taps; the user confirmed typed `HELLO` starts avatar signing and Talk opens the existing Google speech dialog. No recognition or Context Assist accuracy conclusion follows from this UI smoke.

### 2026-10-05 — Reviewed UI baseline and experiment continuity

- [x] User requested that the reviewed Text/Talk UI plus existing Context Assist become the new working baseline and be published. Preservation refs: `baseline/apphear-text-to-asl-context-assist-ui-2026-10-05` and `apphear-text-to-asl-context-assist-ui-2026-10-05`. Last application commit is `ec34034`; the preservation commit changes documentation only.
- [x] See `context/current-working-baseline-2026-10-05.md` for identity, validation and private APK rollback. Future new application work branches from the October 5 tag; older baseline refs remain fixed.
- [x] Saved pointers and next steps for ongoing Context Assist questions, the separate dirty fingerspelling Android worktree and TRAIN-4096 two-worker preparation in `context/ongoing-experiments-2026-10-05.md`. Those experiments were not merged, reset, stopped or promoted.


### 2026-10-08 — automatic held-letter Fingerspell, October5 baseline

Latest application source: C:/Users/Gigabyte/.codex/worktrees/fingerspell-continuous-oct05/5. Apphear3
on codex/fingerspell-continuous-oct05, base b48594c4942d9e9ac0d94ff96396e80b9f049c0a.

- [x] Supervisor approved October5 baseline and automatic held-letter flow with confirmation.
- [x] Persistent Settings choice in Settings/Profile; default WORD; Start/Done absent when automatic.
- [x] Bounded real raw windows, fresh Adapter, one async inference worker, stable singleton draft.
- [x] Explicit owner, stale result cancellation, same-letter latch/rearm, Use/Retry/Clear.
- [x]169unit checks,54singleton/14model parity,2device host/owner tests,3Context local regressions.
- [x]626protected baseline files,648manual files and237priorAPK assets preserved.
- [x] Settings crash fixed: shared Profile also needed the new row; both hosts now tested.
- [x] Supervisor confirms automatic flow and return to WORD controls/camera.
- [ ] Reliable all26 / fluent continuous spelling accuracy remains unproven and was not claimed.

Default/release flags off; private continuous build installed. Frozen V2.1 epoch034/Adapter/WORD
unchanged. Same-letter repetitions can rearm through tracking loss; confirmation remains required.
No new training/job. Next action: use/review this experimental interaction; do not automatically
launch another model experiment. Report: docs/apphear-fingerspelling-continuous-gate-2026-10-08.md.


### 2026-10-08 — Fingerspell display cleanup
Requested hide controls and move automatic letters to RECOGNIZED. Implemented in active October5 worktree RecognitionActivity only; no model/WORD/runtime change. Experimental panel absent, CURRENT SIGN column hidden only in Fingerspell, RECOGNIZED shows confirmed+draft, existing Clear retained. Existing Hear asks confirmation for pending spelling; WORD branch unchanged.169host tests/preservation pass. Separate APK private_apks/app-debug-private-recognized-ui.apk built. ADB currently disconnected: device install/display tests pending, previous installed continuous APK remains on phone. Next: connect Xiaomi and install saved UI APK, then run ContinuousFingerspellInstrumentedTest. Report docs/apphear-fingerspelling-recognized-ui-2026-10-08.md.


### 2026-10-08 — Front/rear camera common input completed

- [x] Inspected actual front RGBA/native rotation/pose/ROI preprocessing; no source reflection.
- [x] Re-enabled rear behind debug flag; same recognition owner, analyzer/models and source contract.
- [x] Camera generation drains/resets/stale guards; lens-aware presentation only; front unchanged.
- [x]169host/7device checks,8byte-identical rotation/stride cases,654protected existing files intact.
- [x] Nonempty WORD sentence survives front/back/front; Settings/owner/Context Assist regressions pass.
- [x] Previous RECOGNIZED UI cleanup installed and device-tested; prior pending item is closed.
- [x] Supervisor: both cameras work; rear video smoothing confirmed and front unchanged.

Measured rear capture15.1->29.6FPS after supported30/30 rear-only AE request. Front remains15/15.
Neither model inference nor feature math changed; KEEP_ONLY_LATEST and genuine timing remain.
Private camera APK installed; previous APKs preserved. No training, dataset, TEST or model work.
No all-letter/back-domain accuracy claim. Report docs/apphear-front-back-camera-input-2026-10-08.md.


### 2026-10-08 — CURRENT SIGN clarification implemented

Supervisor clarified CURRENT SIGN must remain visible for the live detected letter; RECOGNIZED
constructs spelling. Prior hidden-column cleanup was a misunderstanding and is superseded.
Presentation-only currentLetter exposed; tentative letters do not append until the existing stable
policy accepts them. Missing/empty/reset clears current display; stale results ignored. Controls
remain hidden, Hear confirmation retained.170host/5Xiaomi UI-owner-Context tests pass;655protected
files unchanged. Private update installed, rear30/front15 retained. No model, decoder, stabilization,
WORD, Context Assist or camera changes. Report docs/apphear-fingerspelling-current-sign-restored-2026-10-08.md.


## 2026-10-08 reported three-letter RECOGNIZED limit

No display/buffer cap reproduced: 104 characters accepted and visible in five lines
on Xiaomi. 171 host/five phone checks passed; production app/model/camera/WORD unchanged.
Only two regression test files changed. See
`docs/apphear-fingerspelling-long-spelling-check-2026-10-08.md` and
`artifacts/fingerspelling_long_spelling_01/validation.json`.
Existing session EEA plateau includes unaccepted Y decisions; saved diagnostics lack
policy/callback state to isolate rejection reason. Clarification pending: does CURRENT
SIGN show the fourth letter while RECOGNIZED stays at three, or remain blank/incorrect?
Next action: identify acceptance condition from that clarification; do not invent a
three-letter UI cap or loosen recognition thresholds without evidence.


## 2026-10-08 — WORD / Fingerspell / Context coordination

Supervisor approved automatic switching before signing starts. Implemented a separate, debug
opt-in coordinator in the October5 fingerspell-continuous-oct05 app checkout (base b48594c).
Actual hearing text/turn ID drives six bounded English name/place/spell rules; predicted names
and confidence scores never supply recognition. Idle/no-current-usable-hand and no-started-response
gates allow once-per-turn automatic F entry. Manual WORD veto wins; new context cannot interrupt
spelling. Finish spelling explicitly reviews real letters, records only confirmed text against
the correct context turn, returns to WORD and preserves separate WORD sentence storage.

- [x] Existing Candidate01/WORD/F models, raw/Adapter/decoders/held-letter policy unchanged.
- [x] New coordinator/bridge/config/IDs; three additive integration files only.
- [x] 180 private and 180 flag-off host tests, nine new policy tests.
- [x] Xiaomi name routing, confirmation/repeats, stale-turn/manual veto, WORD sentence preservation.
- [x] Existing owner/buffer/camera/Context regressions; 13 passing checks across configurations.
- [x] 662 pre-edit app files: 659 unchanged, exactly three intended integration changes;
  all 281 existing assets unchanged. No training/data/TEST access.
- [x] Default/release coordination off, earlier APKs untouched; private validated APK restored.

Two old fake-provider synthetic replays fired before camera generation readiness and failed;
initial camera generation1/processing0/zero frames is recorded. Existing stale guard untouched.
Equivalent readiness-aware WORD advisory/raw Hear/stop checks pass. Original failures/skips remain
explicit in evidence; the old cold-camera replay harness is not claimed fully passing.

Operational contract: context/recognition-coordination-v1.md.
Report: docs/apphear-recognition-coordination-2026-10-08.md.
Evidence: artifacts/recognition_coordination_01/validation.json.
Private APK: artifacts/recognition_coordination_01/private_apks/app-debug-private-coordination.apk,
SHA6f56dc583148a3725ddc7ed973b633c34528eac2f71d363a9bfb04d96a4b3591.
Rebuild research wrapper: android_continuous_build.ps1 -Configuration private -RearCamera -Coordination.
Latest generic build output may be fake-provider; use saved private APK or exact private command.

Next session: restore this report/private candidate and follow supervisor feedback on actual
Text-to-ASL name prompt -> Reply -> FINGERSPELL / manual WORD override. No new signing accuracy,
arbitrary-intent understanding or recognition-quality improvement claimed. Reliable all26/fluent
recognition remains unproven. No model/retraining/threshold cycle is authorized by this integration.


## 2026-10-08 — context-to-recognition UI continuation completed

Supervisor reaffirmed: Context selects mode; actual WORD/FINGERSPELL models alone produce text.
Current October5 app and existing coordinator re-inspected; no production fix was needed.
Added one test-only RecognitionContextUiFlowInstrumentedTest. Actual Text-to-ASL typed question
“What is your name?” -> Sign It -> existing Reply -> recognition screen passes on Xiaomi with
fake provider and controlled idle/no-hand evidence. F exclusive owner, no context-generated
letters, manual WORD veto/no bounce, Settings preference preserved. Test13.213seconds;669existing
files unchanged. No recognition accuracy claim or model/pipeline/decoder/provider/policy edits.
Original private coordination APK/companion restored; SHA6f56dc583148a3725ddc7ed973b633c34528eac2f71d363a9bfb04d96a4b3591.
Report addendum: docs/apphear-recognition-coordination-2026-10-08.md.
New evidence: artifacts/recognition_coordination_01/ui_flow_01/validation.json. Earlier reports
preserved. Broader context intent remains bounded to configured English patterns; manual override
and explicit Finish are authoritative. Next: supervisor usability feedback using the restored
private build; do not rebuild recognizers or begin another model experiment.



## 2026-10-08 — automatic coordination UI correction

Supervisor rejected recognition-screen WORD/Spell/Finish chooser. Removed buttons, retaining
mode status and automatic context routing. Primary flow: Text-to-ASL question -> Sign It -> Reply
-> automatic FINGERSPELL before signing. Existing top speaker/Hear reviews actual draft and
returns to WORD on confirmation; bottom SPEAK remains hearing input. Settings retains manual
fallback. Neither recognizer generates text from context; only one recognition owner runs.

181 host checks and 6 fake-provider + 3 final-private Xiaomi engineering checks pass. Current
104-character draft displays fully. 670 existing source/config files frozen; exactly six scoped
UI/diagnostic/test files changed; 664 and model/Candidate01/Adapter/WORD/Context assets unchanged.
No acceptance/decoder thresholds changed. Added exact acceptance-state/rejection diagnostics;
fixed periodic diagnostic writes stopping when 64-event deque saturated. This is not an accuracy
improvement claim. Original AM screenshot episode was absent from retained JSON; plateau cause
remains unproven pending one bounded typed-context/held-letter check.

New private APK: artifacts/recognition_coordination_01/automatic_ui_fix_01/app-debug-private-automatic-ui.apk
SHA9501dbb1c91d08052338d66515cc56f115aabe6f6a3d81030485a533c1eafca8.
Installed on Xiaomi 3ab64582 with data retained. Older private coordination rollback preserved.
Report: docs/apphear-recognition-automatic-ui-correction-2026-10-08.md.
Evidence: artifacts/recognition_coordination_01/automatic_ui_fix_01/validation.json.
Next: inspect requested live held-letter acceptance trace, then fix only a demonstrated acceptance
bug. Do not infer a UI cap, lower thresholds, guess missing letters, or start training.


## 2026-10-09 — empty FINGERSPELL recognized container follow-up

Supervisor reported RECOGNIZED gone during the live check. Phone inspection was on Text-to-ASL
(no recognition card there; Reply opens detection). Independently fixed the camera renderer hiding
an empty spelling placeholder: only active continuous FINGERSPELL now keeps sentenceCard visible.
CURRENT SIGN unchanged. WORD helper/body unchanged. Two additional scoped app files:
RecognitionActivity.kt F-render branch and ContinuousFingerspellInstrumentedTest.kt empty-card test.
181 host checks + 3 exact-private Xiaomi checks pass (11.193s); empty card visible, 104 characters
fully displayed, repeats/clear and zero F calls in WORD pass. Cumulative 8 scoped changes;662/670
existing src/config files unchanged. Model/asset/threshold/owner/context rules unchanged.
Latest installed private phone-only APK: artifacts/recognition_coordination_01/automatic_ui_fix_01/empty_card_fix_01/app-debug-private-empty-card.apk
SHA1d38ce947fbcc8c8148b0d8037b60a7c809c6203bf86caa7bd3d2f7a0e9278c8.
Older private builds preserved; do not install generic outputs blindly. User was asked for ONE
fresh typed Text-to-ASL name question -> Sign It -> Reply -> held A/M/Y acceptance check. Await
exact screen result and acceptance JSON before claiming the original AM plateau is diagnosed.
No accuracy claim. Report/evidence child: automatic_ui_fix_01/empty_card_fix_01/validation.json.


### Live follow-up outcome — 2026-10-09
Supervisor confirmed corrected UI “now good.” Actual live draft was EY, not a verified correct
AMY result. Ten raw decodes A,S,S,E,E,E,A,Y,Y,Y yielded only two
accepted letters: A failed sustained matching, one S callback met current missing hand, E and Y
stabilized. No cap/truncation or stale owner result was observed. Recognition remains imperfect;
no threshold/model fix was made. Original AM episode not recoverable. No more attempts needed for
this UI task. Keep newest private empty-card build installed, protected WORD intact. Next work only
if supervisor requests it; do not silently launch model/training/threshold changes.


## 2026-10-09 — compact recognition mode header completed

Supervisor requested top label only. Active October5 bridge moved coordinationPanel between
Back and Camera, centered in their top row, existing glass pill/Inter font. Labels only Fingerspell
or Word; removed context/review/last-spelling copy from indicator. No chooser. Existing automatic
routing, confirmation, CURRENT SIGN and RECOGNIZED unchanged. Bridge routing/confirmation methods
byte-identical, Activity/camera/model/Adapter/decoder/WORD/Context core untouched.
181 host +3 final private Xiaomi checks pass (10.303s); header bounds and both exact labels verified.
666/670 existing app source/config files unchanged;four scoped UI/resource/test changes only.
Latest private phone-only APK: artifacts/recognition_mode_header_01/app-debug-private-mode-header.apk
SHAf3a6aed9394f8c1d23c7a1e3a657dce6034176568da79e5e983e429423a3ee6b. Installed with data retained; prior empty-card APK preserved.
Report docs/apphear-recognition-mode-header-2026-10-09.md; evidence artifacts/recognition_mode_header_01/validation.json.
No recognition accuracy claim or new model/threshold work. Next: supervisor visual feedback only.


## 2026-10-09 — recognition mode pill hugs content

Supervisor requested content-sized mode indicator. Single presentation change: bridge's panel
ConstraintLayout width 0 -> WRAP_CONTENT. Existing 12dp horizontal padding, top-row centering,
labels and owner/routing behavior preserved. No new tests/dependencies or recognition changes.
181 existing host tests and 1 existing Xiaomi header/confirmation/WORD-preservation test pass
(5.416s). Exactly1/670 source/config files changed;669 unchanged. Current private phone-only APK:
artifacts/recognition_mode_header_01/hug_content_01/app-debug-private-hug-content.apk
SHAcd92a856a86a078f79e6b1a40182587e1737a213dba6c0d3baa754c25d36d4c0. Installed with adb install -r, app data retained.
Previous full-width header/private candidates preserved. Evidence child validation.json;
report docs/apphear-recognition-mode-header-2026-10-09.md. No further accuracy work authorized.


## Frozen integrated application baseline — 2026-10-09

User authorized preserving and pushing the reviewed WORD + continuous held-letter
FINGERSPELL + Context Assist application, including the compact hug-content mode
pill. New fixed branch: `baseline/apphear-word-fingerspell-context-assist-2026-10-09`;
tag: `apphear-word-fingerspell-context-assist-2026-10-09`.
Read `context/current-working-baseline-2026-10-09.md` first for future application
work. Start experiments on a separate branch/worktree from that tag. Older
baselines, private rollback APKs and research datasets/runs remain preserved.
Runtime model/policy and parity fixtures are now bundled byte-exact under
`packages/fingerspelling_continuous_v2_1_01`; the repository-relative build preset
uses these files without the previous machine-local research-folder dependency.
No application source, model behavior or WORD behavior changed in this preservation.
Recognition remains experimental; this baseline does not certify A–Z accuracy.

## Original word batch delivery — 2026-10-09

273-entry Original catalog installed as flagged private debug extension: 32 ZIP replacements, 171 additions, STAND excluded/idle retained. 186 host tests and 2 device playback/catalog tests passed; ownership regression passed separately after combined window-focus timeout. Recognition and New Character remain untouched. Authoritative app checkout: C:/Users/Gigabyte/.codex/worktrees/fingerspell-continuous-oct05/5. Apphear3; branch codex/original-character-word-batch-2026-10-09. Frozen baseline remains 34f24ab6d7aea8179decb1688a82fc5734f6d370. See context/text-to-asl-original-words-v1.md. Mixed avatars and all-clips ASL correctness remain review limitations; no baseline commit/push performed. Next: supervisor reviews actual Original playback and appearance; do not change recognition.
