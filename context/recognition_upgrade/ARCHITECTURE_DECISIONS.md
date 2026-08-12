# Architecture Decisions

**Purpose:** Prevent future agents from reopening settled choices or treating hypotheses as facts.
**Status:** ACTIVE PLAN / DYNAMIC MIXED LANDMARK-PRIMARY ROADMAP APPROVED. **Last updated:** 2026-08-02.

## Decision Log

| ID | Decision | State | Evidence / tradeoff |
|---|---|---|---|
| ADR-RU-001 | Preserve production v3.0 as control and fallback | Accepted | Working app, stable Git tag, model/schema checks |
| ADR-RU-002 | Target hybrid landmarks + RGB hand crops | Accepted as research direction, not production fact | Published multimodal gains and 258 information loss; must pass E3 |
| ADR-RU-003 | Isolated 50-sign pilot before 100/236 or continuous | Accepted | Current data/early-frame/device results are below real-user gates |
| ADR-RU-004 | MediaPipe remains the preferred landmark provider, not sole ROI authority | Superseded by E2e audit | Corrected all-hand recall 66.30%; retain valid landmarks but add detector-agnostic ROI management |
| ADR-RU-005 | IMAGE -> VIDEO/LIVE_STREAM is not the primary ROI-reliability fix | Rejected as primary solution | E2c gains were too small and failed coverage gates; do not repeat mode tuning |
| ADR-RU-006 | New multimodal schema, never mutate 3.0 | Accepted | Train/serve parity and rollback |
| ADR-RU-007 | Intermediate quality-gated fusion | Proposed primary | Preserves modality specialization and missing-stream fallback |
| ADR-RU-008 | Shared lightweight hand RGB encoder | Proposed primary | Controls params and enforces left/right feature consistency |
| ADR-RU-009 | Causal bounded cache with real timestamps | Accepted | Streaming requirement and low/variable FPS |
| ADR-RU-010 | Boundary 4-state auxiliary head + isolated gloss head | Proposed | Replaces frame-count onset/release as primary evidence; S5 remains fallback |
| ADR-RU-011 | CTC only after natural continuous annotated data | Accepted | Isolated concatenation does not model coarticulation |
| ADR-RU-012 | CPU/XNNPACK remains required fallback | Accepted | Device/delegate variability; current MediaPipe GPU may still be device-specific |
| ADR-RU-013 | No default face stream | Accepted for pilot | Cost and prior v2 evidence; add only via E6 |
| ADR-RU-014 | No full-frame RGB in default mobile path | Accepted | Compute/thermal budget; retain offline ceiling |
| ADR-RU-015 | Failed slim ST-GCN is negative evidence, not proof graphs fail | Accepted | Run scored 0.1588; speed cuts/training setup differ from published baseline |
| ADR-RU-016 | Screen an independent single-class hand detector before E3 | Deferred after C0 route decision | HaGRID smoke no-go; detector pilot held until annotation inventory is approved |
| ADR-RU-017 | Continue landmark-first after E3-B3/E3-B4 | Superseded by E3-B5/E3-B6/E3-C evidence | E3-B5/E3-B6/E3-B7/E3-C completed; landmarks remain strongest, but small feature/model tweaks and naive RGB fusion did not pass production gates |
| ADR-RU-018 | Run E4-A landmark/data generalization audit before further training | Completed | E4-A found only 4 candidate-keep classes, 15 borderline, 8 confusion-review, 6 drop/defer, and 17 needs-visual-evidence classes |
| ADR-RU-019 | Targeted collection and label/video review before E4-B retrain | Accepted next step | E4-A showed the 50-class set is not ready for blind retraining; E4-C must define class targets, signer/repetition requirements, and review actions first |
| ADR-RU-020 | Use E4-C target package as the next collection/review contract | Superseded by E4 local/generalization results | E4-C/E4-F through E4-L showed local supplementary data can form a tiny core but single-candidate expansion failed; targeted collection remains useful but is no longer the immediate next step |
| ADR-RU-021 | Replace manual one-word expansion with dual-source batch candidate screening | Accepted next step | E4-L MAKE expansion passed extraction but failed held-out signer testing; next work must screen ASL Citizen and local supplementary candidates with source-aware gates before larger model or Android work |
| ADR-RU-022 | Use E4-M ranking to bound the next dual-source training screen | Accepted | E4-M found only `HAVE` and `KNOW` train-ready from existing dual-source features; `GET`/`WELCOME2` need extraction and `BYE`/`NO`/`YES` remain prior-unstable |
| ADR-RU-023 | Run E4-N before extracting more signs or changing Android | Accepted | E4-N passed with mean latest test `0.9774`, min core `0.9667`, min candidate `0.9286`; this authorizes the next queued extraction screen but not Android/export |`r`n| ADR-RU-024 | Prepare E4-O before any large batch | Accepted next step | E4-O tests `GET`/`WELCOME2`, the remaining E4-M extraction-needed candidates, before committing time to a 20-50 sign batch |

## Terminology

- **Accuracy:** held-out-signer, end-to-end unless explicitly labeled S6 diagnostic.
- **Window/cache:** a timestamped bounded history, not 96 semantic frames.
- **Confidence:** calibrated probability/acceptance score, never raw softmax alone.
- **Sign span:** onset through release with explicit annotation uncertainty.
- **Done:** offline gates, quantized parity, device smoke, sustained thermal test.

## Rejected Or Deferred

- LSTM/BiLSTM as primary encoder: no compelling advantage over temporal conv/graph/attention.
- Raw I3D/video transformer on low-end Android: useful offline ceiling, not default deployment.
- Synthetic data as signer-diversity substitute: rejected.
- Language model correcting weak glosses: deferred; it can hide or amplify recognizer errors.
- Direct ASL-to-English translation: deferred beyond continuous gloss recognition.

## References, Assumptions, Risks, Open Questions, Next Action

- **Project references:** `CURRENT_PIPELINE_AUDIT.md`, parent `encoder-upgrade.md`,
  `recognition-accuracy.md`.
- **Assumption:** a controlled 50-sign vocabulary can be selected without collapsing meaningful
  lexical variants.
- **Risk:** the hybrid direction may fail mobile cost or data scale gates.
- **Open question:** exact Tier-A stable vocabulary after applying E4-N/E4-O/E4-P/E4-Q evidence.
- **Next action:** prepare an offline mixed simulation with E4-S primary plus conditional `GOOD/SORRY` landmark specialist. Keep Android integration, production export, global RGB/fusion scaling, and broad vocabulary expansion blocked.


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-017 apply; component-specific decisions in this document apply only after their experiment gate passes.
- **Assumptions:** Any forecast or unmeasured dimension remains a hypothesis, not a project fact.
- **Open questions:** Unresolved items are tracked in this document and `OPEN_QUESTIONS.md`.
- **Risks:** Applicable failure modes and fallbacks are tracked in this document and `RISK_REGISTER.md`.
- **Next required action:** Follow the explicit next action above and the ordering in `EXPERIMENT_MATRIX.md`; do not skip gates.








| ADR-RU-025 | E4-O failed; exclude `GET/WELCOME2` from the next batch | Accepted | E4-O completed extraction/training but failed gate: mean latest test `0.7822`, min core `0.7000`, min candidate `0.2619`; local extracted `GET` collapsed mostly into `GOOD` |
| ADR-RU-026 | Run E4-P 20-sign existing-feature pressure test before more extraction | Accepted next step | E4-P uses existing ASL Citizen and local feature tensors only, excludes known unstable/rejected signs, and tests whether landmark-only recognition collapses at 20 classes before spending more extraction/training time |

| ADR-RU-027 | Use specialist confusion resolvers for known similar-sign groups before broader expansion | Accepted next step | E4-P failed the 20-sign gate and exposed a specific `SORRY -> BECOME/HELP` collapse; E4-Q tests whether `[96,258]` or derived `[96,728]` landmark features can resolve the group before RGB fallback or large expansion |


## Dynamic Mixed Recognition ADRs - 2026-07-31

| ID | Decision | State | Evidence / tradeoff |
|---|---|---|---|
| ADR-RU-028 | Adopt landmark-primary dynamic mixed recognition as the current target architecture | Accepted | E4-N showed a bounded landmark stable set can pass; E4-O/E4-P/E4-Q showed broad expansion and landmark-only resolvers fail for specific signs. This supports routed specialization, not hybrid everywhere. |
| ADR-RU-029 | Preserve `[96,258]` schema 3.0 as the primary stable-sign input until a new schema passes parity and device gates | Accepted | E4-N passed with existing features; E4-Q derived `[96,728]` failed to resolve `SORRY` and is not approved for Android. |
| ADR-RU-030 | Introduce a versioned confusion registry/router before any specialist runtime model | Accepted as architecture plan; implementation blocked | E4-P and E4-Q identify concrete confusion groups. Routing must be simulated offline before Android to avoid scattered hard-coded logic and false commits. |
| ADR-RU-031 | Specialist resolvers are group-specific and optional, not a replacement global recognizer | Accepted | Previous broad RGB/fusion attempts failed; complexity should be paid only where a registered confusion group needs extra evidence. |
| ADR-RU-032 | For `SORRY/BECOME/HELP`, do not retry landmark-only resolver or derived-feature-only resolver as the next step | Accepted | E4-Q failed: best mean latest test `0.7137`, minimum latest `SORRY` `0.2333`; derived and class-weighted variants worsened `SORRY`. Next evidence must be visual crops and/or data/variant repair. |
| ADR-RU-033 | Treat user confirmation as unsuitable for silent translation accuracy | Accepted | Product goal is translating another person signing for a non-signing user. Acceptance must be algorithmic through calibration, temporal stability, router agreement, and rejection. |
| ADR-RU-034 | Vocabulary expansion must use tiered batch screening, not blind all-sign training or repeated one-word loops | Accepted | E4-L one-word MAKE failed; E4-M/E4-N showed batch screening can identify useful candidates; E4-P showed broad 20-sign pressure can expose collapse before expensive extraction. |

| ADR-RU-035 | Use E4-R guarded Tier-A signs as the next stable-primary landmark batch | Accepted | E4-R ranked 236 labels and found only `GOOD`, `HELLO`, `HAVE`, and `KNOW` primary-ready guarded. `SORRY` is moved to confusion handling because E4-P/E4-Q failed despite earlier local-core strength. |
| ADR-RU-036 | Prepare E4-S as a filtered stable-primary package, not a new extraction | Accepted | E4-S reuses the passed E4-N [96,258] tensor, keeps GOOD, HELLO, HAVE, and KNOW, and withholds SORRY as an OOV/confusion holdout. This tests primary stability before router/specialist work and avoids re-running extraction for a vocabulary-composition question. |
| ADR-RU-037 | Do not rely on simple softmax confidence/margin routing for SORRY -> GOOD | Accepted | E4-T showed withheld SORRY test rows are predicted as GOOD with very high confidence across all E4-S seeds. The best threshold scan failed the joint precision/coverage/OOV gate, so this confusion requires richer evidence, targeted repair, or a specialist path. |
| ADR-RU-038 | Treat SORRY -> GOOD as the first reusable confusion-group evidence package, not a one-word loop | Accepted | E4-U prepares paired held-out GOOD and false-commit SORRY source-video evidence, panels, and prediction summaries. The purpose is to choose a reusable specialist/data-repair pattern before applying it to other groups. |
| ADR-RU-039 | Test GOOD/SORRY specialist proof with landmark binary control and upper-body RGB | Accepted as next experiment | User confirmed E4-U sheets show SORRY is visibly different from GOOD. E4-V tests whether RGB evidence resolves this representative high-confidence false-commit group before any global RGB rollout or Android integration. |
| ADR-RU-040 | Prefer lightweight landmark specialist before RGB for GOOD/SORRY | Accepted | E4-V showed the binary [96,258] landmark specialist reached stable  .9667 test accuracy and  .9667 SORRY recall across all seeds, while upper-body RGB was unstable and collapsed to all GOOD in one seed. Specialist routing should use the simplest passing evidence source first. |






| ADR-RU-041 | Advance to broader offline routed-system validation after E4-W, not Android export | Accepted | E4-W primary-plus-landmark-specialist simulation passed: mean mixed accuracy `0.9718`, min mixed accuracy `0.9661`, mean/min `SORRY` recall `0.9667`, and false `GOOD -> SORRY` correction rate `0.0333`. This supports the dynamic mixed architecture but remains small offline same-source evidence, so the next gate must add no-sign/OOV/source-disjoint validation before runtime work. |

| ADR-RU-042 | Require real MediaPipe N0/P1 feature validation after E4-X before Android export | Accepted | E4-X passed an accept/reject routed-system probe with mean accepted precision `0.9798`, min accepted precision `0.9739`, min positive coverage `0.9661`, and zero false commits on zero-landmark N0 rows. Because zero-landmark rows are not real MediaPipe runtime features, the next gate must extract actual N0/P1 feature windows before Android or TFLite work. |

| ADR-RU-043 | Add signing/no-sign gate before Android or production routing | Accepted | E4-Y showed real MediaPipe N0/P1 features cause severe false commits under the E4-X routed policy: mean accepted precision `0.7844`, minimum accepted precision `0.7687`, and max no-sign false-commit rate `0.9688`. Positive-sign recall stayed strong, so the blocker is not primary/specialist separation; it is absence of a real signing gate. |

| ADR-RU-044 | Do not use crude motion/presence gate as production signing detector | Accepted | E4-Z showed motion/presence rules can eliminate N0/P1 false commits but collapse positive coverage to roughly `0.32`-`0.40` and SORRY recall to `0.0000`. The learned summary MLP also failed SORRY. A larger no-sign split and stronger temporal signing gate are required before Android/export. |

## ADR-RU-045 - E4-AA Temporal Signing Gate Package Is Authorized Before Android Export

Date: 2026-08-02

Status: Active experiment package; full result pending.

Decision: After E4-Y and E4-Z, the next required recognition-upgrade step is E4-AA: train/evaluate a temporal signing/no-sign gate on real MediaPipe schema v3.0 `[96,258]` N0/P1 windows before the E4-S/E4-V routed recognizer. Android integration, TFLite export, production replacement, and broad vocabulary expansion remain blocked until the full E4-AA run passes its gates.

Evidence: E4-Y showed real MediaPipe no-sign windows caused severe false commits even though zero-landmark no-sign rows passed. E4-Z showed simple rule gates and summary-feature MLP gates were insufficient, especially for low-motion `SORRY`. E4-AA preserves schema v3.0 and tests a stronger temporal gate using actual feature sequences.

Implementation note: `pipeline/rgb/e4_aa_nosign_temporal_gate.py` supports resumable extraction and separated training through `--prepare-only` and `--train-only`. Smoke run `artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_smoke_01` passed structural validation only; it is not an accuracy result.

Related files: `E4_AA_NOSIGN_TEMPORAL_GATE_PACKAGE.md`, `E4_Z_SIGNING_GATE_RESULT.md`, `E4_Y_REAL_NOSIGN_FEATURE_VALIDATION_RESULT.md`, `DYNAMIC_MIXED_RECOGNITION_ROADMAP.md`.

## ADR-RU-046 - Threshold Tuning Alone Is Insufficient For The Signing Gate

Date: 2026-08-02

Status: Accepted.

Decision: Do not proceed to Android/export with E4-AA or E4-AB. E4-AA proves a temporal gate can suppress real no-sign false commits, but it over-rejects low-motion signs. E4-AB proves conservative thresholding improves the trade-off, but it remains unstable across seeds and cannot guarantee SORRY recall.

Evidence: E4-AA reduced max real no-sign false commit rate to `0.0147`, but mean/min SORRY recall was only `0.1222/0.0000`. E4-AB improved mean SORRY recall to `0.6778`, but seed `202` test SORRY recall remained `0.1000`. Probability inspection showed seed `202` true SORRY windows had very low signing probabilities, overlapping no-sign.

Consequence: The next gate experiment must change the training objective/data or representation for low-motion positives, not only the threshold. Android integration, TFLite export, production replacement, and vocabulary expansion remain blocked.

Related files: `E4_AA_NOSIGN_TEMPORAL_GATE_RESULT.md`, `E4_AB_CONSERVATIVE_GATE_POLICY_RESULT.md`, `E4_AA_NOSIGN_TEMPORAL_GATE_PACKAGE.md`.

## ADR-RU-047 - Low-Motion-Aware Gate Is Promising But Not Runtime-Approved

Date: 2026-08-02

Status: Accepted.

Decision: E4-AC is the current best signing/no-sign gate direction, but it is not approved for Android/export. It should be used as the basis for the next gate iteration with hard-negative expansion.

Evidence: E4-AC best run restored mean/min SORRY recall to `0.9667/0.9667` while keeping max no-sign false commit rate at `0.0441` and mean positive coverage at `0.9746`. It narrowly missed strict accepted precision with minimum `0.9492` versus the `0.95` gate. This is a meaningful improvement over E4-AA and E4-AB, but the no-sign set is still small and the residual errors are enough to block production.

Consequence: Proceed to false-commit review/hard-negative expansion for the signing gate. Do not broaden vocabulary, export TFLite, or integrate with Android until the signing gate passes with margin.

Related files: `E4_AC_LOW_MOTION_AWARE_GATE_RESULT.md`, `E4_AB_CONSERVATIVE_GATE_POLICY_RESULT.md`, `E4_AA_NOSIGN_TEMPORAL_GATE_RESULT.md`.

## ADR-RU-048 - Residual Signing-Gate Error Is HELLO-Like No-Sign, Not A Broad Gate Failure

Date: 2026-08-02

Status: Accepted.

Decision: Treat the remaining signing-gate blocker as a focused `NO_SIGN -> HELLO` false-commit problem. Do not broaden vocabulary or export to Android while this remains unresolved.

Evidence: E4-AD found `28` false commits, concentrated as `NO_SIGN -> HELLO`, especially P1 ordinary-hand windows. E4-AE upweighted `12` train hard negatives but failed to improve the gate; corrected run `_02` had minimum accepted precision `0.9417`, worse than E4-AC `_01` at `0.9492`.

Consequence: Naive hard-negative weighting is not enough. The next decision should compare collecting more HELLO-like no-sign/P1 data against adding temporal confirmation/uncertainty policy before any runtime work.

Related files: `E4_AD_FALSE_COMMIT_REVIEW_RESULT.md`, `E4_AE_HARD_NEGATIVE_GATE_RESULT.md`, `E4_AC_LOW_MOTION_AWARE_GATE_RESULT.md`.

## ADR-RU-049 - Split The Next Work Into A Short Safety Floor And A Batch Scaling Phase

Date: 2026-08-02

Status: Accepted.

Decision: Do not continue one-sign expansion loops as the main project path, and do not blindly train a large vocabulary before no-sign safety is controlled. The next work is E4-AF, a short offline acceptance-policy/safety-floor experiment, followed by E5-A large dual-source candidate screening if E4-AF passes.

Evidence: E4-AC nearly passed while preserving GOOD/SORRY and controlling real no-sign false commits. E4-AD localized residual errors to NO_SIGN -> HELLO. E4-AE showed naive hard-negative weighting worsened minimum precision. Earlier E4-L/E4-O one-sign expansion loops were slow and failed; E4-P showed broad training without tiering collapses. This supports a short safety step followed by batch screening.

Consequence: Future agents must not propose another one-word loop as the main path unless it is a targeted confusion-group or safety-floor diagnostic. Future agents must not propose Android/export or broad vocabulary training until the E4-AF safety floor is evaluated.

Related files: `E4_AF_TO_E5_BATCH_STRATEGY.md`, `E4_AC_LOW_MOTION_AWARE_GATE_RESULT.md`, `E4_AD_FALSE_COMMIT_REVIEW_RESULT.md`, `E4_AE_HARD_NEGATIVE_GATE_RESULT.md`, `EXPERIMENT_MATRIX.md`.

## ADR-RU-050 - E5-A Batch Screening Is The Next Vocabulary-Scale Mechanism

Date: 2026-08-02

Status: Accepted.

Decision: Vocabulary scaling must happen through E5-A dual-source candidate screening across ASL Citizen and the local supplementary dataset, not by appending signs directly to the production candidate model. E5-A should rank many candidate signs at once into Tier A primary candidates, Tier B confusion/specialist candidates, Tier C data/label repair, Tier D defer/reject, and inventory-only.

Evidence: E4-M/E4-N showed source-aware screening can identify useful candidates (`HAVE`, `KNOW`), while E4-L/E4-O single-candidate expansion and E4-P 20-sign pressure training exposed collapse. The correct scale-up mechanism is batch triage with per-class gates, not aggregate accuracy alone.

Consequence: After E4-AF, the next large work should be an E5-A screening package using existing feature inventories first. Raw extraction and training should be requested only when the inventory report proves they are needed.

Related files: `E4_AF_TO_E5_BATCH_STRATEGY.md`, `DYNAMIC_MIXED_RECOGNITION_ROADMAP.md`, `DATASET_UPGRADE_PLAN.md`, `EXPERIMENT_MATRIX.md`.

## ADR-RU-051 - Policy-Only Acceptance Sweep Is Not Enough

Date: 2026-08-02

Status: Accepted.

Decision: E4-AF policy-only tuning is a no-go. Do not continue generic acceptance-threshold sweeps against the same no-sign data. The next safety step is targeted HELLO-like no-sign expansion, then gate retraining/evaluation.

Evidence: E4-AF structural check passed, but selected policy minimum accepted precision remained `0.9492`, below the `0.95` gate. HELLO-specific probability floors can remove false commits only by damaging true HELLO recall and positive coverage. E4-AD already showed residual false commits are concentrated as NO_SIGN -> HELLO.

Consequence: E5-A batch screening remains the next scale-up step, but only after the safety floor is recovered or explicitly marked research-only. Android integration, TFLite export, and production replacement remain blocked.

Related files: `E4_AF_ACCEPTANCE_POLICY_RESULT.md`, `E4_AF_TO_E5_BATCH_STRATEGY.md`, `E4_AD_FALSE_COMMIT_REVIEW_RESULT.md`, `E4_AC_LOW_MOTION_AWARE_GATE_RESULT.md`.

## ADR-RU-052 - Targeted HELLO-Like No-Sign Data Recovered The Offline Safety Floor

Date: 2026-08-02

Status: Accepted.

Decision: E4-AG passes the offline signing/no-sign safety floor for the current small routed recognizer and authorizes E5-A large dual-source candidate screening as the next vocabulary-scale step. Android integration, TFLite export, and production replacement remain blocked until later streaming/device gates.

Evidence: E4-AG added `116` reviewed P1_HELLO_LIKE no-sign rows and expanded the no-sign tensor to `[404,96,258]`. Rerunning the E4-AC low-motion-aware gate produced mean/min accepted precision `0.9798/0.9739`, mean/min positive coverage `0.9746/0.9661`, max no-sign false commit rate `0.0000`, and GOOD/SORRY mean/min recall `0.9667/0.9667`.

Consequence: Stop no-sign threshold/policy tuning for now. Proceed to E5-A batch candidate screening using ASL Citizen and the local supplementary dataset, while preserving the current production recognizer untouched.

Related files: `E4_AG_HELLO_LIKE_NOSIGN_RESULT.md`, `E4_AF_ACCEPTANCE_POLICY_RESULT.md`, `E4_AF_TO_E5_BATCH_STRATEGY.md`, `EXPERIMENT_MATRIX.md`.

## ADR-RU-053 - E5-A Strict Dual-Source Screen Is Conservative Evidence, Not The Scaling Strategy

Date: 2026-08-02

Status: Superseded by ADR-RU-054 for the immediate scaling path.

Decision: Do not train all 236 labels or the 67 local-supported labels as a production candidate. The strict E5-A interpretation authorized only a strict E5-B pilot with `WANT2` as the next primary candidate, while the broader local-supported list became a diagnostic/data-collection queue.

Evidence: E5-A inspected 236 labels and found 67 with local support, but only `WANT2` passed strict dual-source criteria for the next primary pilot: 69 local rows, 2 local signers, E4-P mean/min latest `0.7879/0.6364`. Fifty labels need more local signers, and 169 are ASL-only inventory. E4-P already showed broad training without tiering collapses.

Consequence: This remains a valid conservative production-readiness screen, but the user clarified that ASL Citizen should drive broad vocabulary learning and local data should supplement or repair signs where available. The immediate experiment is therefore replaced by ADR-RU-054.

Related files: `E5_A_DUAL_SOURCE_BATCH_SCREEN_RESULT.md`, `E4_AG_HELLO_LIKE_NOSIGN_RESULT.md`, `E4_P_EXISTING_FEATURE_20SIGN_PACKAGE.md`, `DYNAMIC_MIXED_RECOGNITION_ROADMAP.md`.

## ADR-RU-054 - ASL Citizen Leads Broad Vocabulary, Local Data Supplements

Date: 2026-08-02

Status: Accepted.

Decision: Proceed with E5-B as an ASL Citizen-led 50-class landmark-primary diagnostic. Local supplementary rows are included when available, but local support is not required for every class. Known blocked/confusion signs are excluded from the primary model and remain routed, repaired, or deferred.

Evidence: The product goal requires scaling beyond the local supplementary vocabulary. E5-A showed that strict dual-source support is too restrictive for near-term batch progress: only one new sign met that bar. E4-P showed blind broad training can collapse, so E5-B keeps the batch broad but controlled by excluding known hard signs, preserving stable controls, using signer-disjoint splits already present in the combined tensor, and reporting per-class behavior instead of relying on aggregate accuracy.

Consequence: E5-B is diagnostic and does not authorize Android export or production replacement. Its result will determine which signs become primary candidates, which signs require specialist routing, and which signs need dataset/label repair.

Related files: `E5_B_ASL_LED_PRIMARY_BATCH_PACKAGE.md`, `E5_A_DUAL_SOURCE_BATCH_SCREEN_RESULT.md`, `E4_AG_HELLO_LIKE_NOSIGN_RESULT.md`, `DYNAMIC_MIXED_RECOGNITION_ROADMAP.md`, `EXPERIMENT_MATRIX.md`.
## ADR-RU-055 - E5-B Is Diagnostic-Only; Use E5-C Tiering For Reduced Primary

Date: 2026-08-03

Status: Accepted.

Decision: Do not export or integrate the E5-B 50-class model. Use E5-C tiers to define a reduced-primary validation set before any Android or production work.

Evidence: E5-B mean latest test accuracy was `0.4897` against random baseline `0.0200`, proving real signal but not production quality. E5-C found `9` strong primary candidates and `6` guarded candidates, while `HELLO` and `KNOW` regressed badly in the 50-class context (`HELLO` mean/min `0.400/0.200`, `KNOW` `0.333/0.231`) with both primarily confused as `SEEM`.

Consequence: The next experiment is E5-D reduced-primary validation using the E5-C candidate vocabulary and offline routed-system assumptions. `HELLO` and `KNOW` require repair or specialist/routing evidence before primary promotion. Android export and production replacement remain blocked.

Related files: `E5_C_50CLASS_TIERING_RESULT.md`, `E5_B_ASL_LED_PRIMARY_BATCH_PACKAGE.md`, `DYNAMIC_MIXED_RECOGNITION_ROADMAP.md`, `EXPERIMENT_MATRIX.md`.


## ADR-RU-056 - Stop The E5 Threshold/Shared-Reject Loop And Move To E6 Modular Architecture Validation

Date: 2026-08-03

Status: Accepted.

Decision: Do not treat E5-J class-conditioned rejection as the guaranteed next solution. It remains a possible sub-experiment, but the immediate roadmap moves to E6: baseline freeze, dataset/representation audit, richer landmark-feature control, independent open-set rejection comparison, confusion-registry mining, and optional specialist/RGB tests only after their controls pass.

Evidence: E5-H proved confidence-only routing is unsafe or unusable: the full 7-sign strict policy had mean/min positive coverage `0.1111/0.0833` and min class recall `0.0000`. E5-I proved a shared accept/reject head is helpful but insufficient: full 7-sign mean/min accepted precision `0.8985/0.8333`, positive coverage `0.2778/0.2083`, and min class recall `0.0000`. E5-G closed-set success (`0.8472` mean latest test) therefore does not transfer to safe open-set silent translation.

Consequence: Future agents must not continue small threshold sweeps, vocabulary shrinking, or accept-head variants as the main path without first completing E6-0/E6-1. Android integration, TFLite export, production replacement, schema mutation, and RGB runtime work remain blocked.

Related files: `E6_PRODUCTION_RECOGNITION_ARCHITECTURE_PLAN.md`, `E5_H_CLEAN_7_ROUTED_SIM_RESULT.md`, `E5_I_OPEN_SET_REJECT_HEAD_RESULT.md`, `E5_G_CLEAN_7_PRIMARY_RESULT.md`, `DYNAMIC_MIXED_RECOGNITION_ROADMAP.md`.

## ADR-RU-057 - E6-1 Data Insufficient Stop-Modeling Gate

Date: 2026-08-03

Status: Accepted.

Decision: After E6-0/E6-1, stop recognition modeling. Do not proceed to E6-2 richer features, E6-3 rejection methods, E6-5 specialists/RGB, E6-6 routed simulation, or E6-7 Android shadow mode until a bounded product-core data-readiness package exists.

Evidence: E6-1 consolidated E1-E5 and counted the current feature inventories. All 236 labels have ASL Citizen feature rows, but the audited derived subset has no label with >=50 ASL feature rows, only 67 labels with any local recorded rows, only 3 labels with >=50 local rows, and 0 labels with >=100 local rows. E5-H/E5-I already showed that closed-set learning does not transfer to safe open-set/routed recognition.

Consequence: The next action is data readiness: per-row raw-video lineage, signer/source/split/variant metadata, product-core sign selection, no-sign/OOV coverage expansion, and label/variant repair. Future modeling proposals must cite the closest previous experiment and prove a meaningful difference before approval.

Related files: `E6_0_BASELINE_FREEZE.md`, `E6_1_CONSOLIDATED_EVIDENCE_DATASET_AUDIT.md`, `e6_audit_tables/e1_to_e5_experiment_inventory.csv`, `e6_audit_tables/per_sign_aggregate_counts.csv`.

## ADR-RU-058 - Return To The Unresolved Hand-ROI Prerequisite After E6

Date: 2026-08-09

Status: Accepted as architecture plan; implementation and training require separate approval.

Decision: E6-2, E6-3, and E6-5 did not supply components that can advance to E6-6. Do not weaken
or rename E6-6. The one next experiment is C0-B0: an AppHear-domain, production-compatible
single-class hand detector feasibility gate. Its first stage is a training-only annotation inventory,
overlap audit, and TFLite export/reload smoke. Long detector training is not automatically approved.

Evidence: corrected MediaPipe hand-instance recall was `66.30%` and complete two-hand recall was
`46.27%`; pose recovery and MediaPipe mode/threshold tuning failed; HaGRID YOLOv10n could not
control N0 false ROIs without losing positive recall; E3 crop-free upper-body RGB and naive fusion
failed. No AppHear-domain detector was trained because an independent training-only box set was
never approved.

Consequence: Keep MediaPipe for landmarks but not as the assumed sole RGB ROI source. Keep RGB
recognition, fusion, face cues, continuous recognition, Android integration, and production
replacement blocked. If C0-B0 fails, retire detector-derived hand-crop hybrid as the immediate
mobile route and make an explicit product-scope decision while preserving v3.0.

Related files: `POST_E6_ARCHITECTURE_REVIEW.md`,
`C0B_APPHEAR_HAND_ROI_FEASIBILITY_PLAN.md`, `C0_ROUTE_DECISION_REPORT.md`,
`E6_COMPONENT_DECISION.md`, `E6_0_BASELINE_FREEZE.md`.

## ADR-RU-059 - Close C0-B0 After I320 Development No-Go

Date: 2026-08-11

Status: Accepted from registered evidence and stop rules.

Decision: Do not retrain or promote I320 using the existing negative inventory. Retire
detector-derived hand-crop hybrid as the immediate mobile route, preserve the v3.0 `[96,258]`
recognizer, and require an explicit product-scope decision before any new model work.

Evidence: I320 was the stronger detector but reached only `67.26%` availability, `41.03%`
complete two-hand recall, and `63.72%` IoU50 at the valid development threshold. The Stage 2 train
and development partitions contain only `53` and `14` no-hand frames. The independent hard-
condition scan found `0` training-eligible rows among `547` historical E6 development negatives
because all overlap protected evaluation lineage. The `560` fresh provisional negatives are
evaluation-only and represent one signer.

Consequence: No QAT/INT8, frozen P0/N0/P1 evaluation, Android detector integration, RGB sign
recognizer, generic sweep, or automatic fallback model. C0-B0 may be reopened only through a
separately approved, new, signer-diverse, training-only hard-negative collection with zero
protected overlap and a preregistered single-round gate.

Related files: `C0B_POST_I320_DATA_DECISION.md`, `C0B_STAGE2_DEVELOPMENT_RESULT.md`,
`C0B_APPHEAR_HAND_ROI_FEASIBILITY_PLAN.md`, `POST_E6_ARCHITECTURE_REVIEW.md`.

## ADR-RU-060 - Bound The Current Deliverable To The Protected Research Prototype

Date: 2026-08-11

Status: Accepted after the C0-B0 stop decision.

Decision: Preserve the reliable silent-translator goal as long-term scope, but define the current
deliverable as a bounded on-device isolated-sign research prototype using the unchanged 236-sign
schema v3.0 recognizer. Do not claim continuous translation or production signer-independent
reliability. The next executable action is the existing F22 baseline device smoke, not another
recognition model.

Evidence: No E1-E6 replacement component stack passed its integration gates. Crop-free RGB/fusion,
global geometry, open-set rejection, and the broader specialist attempt failed. C0-B0 closed the
remaining detector-derived hand-crop route for the current data. The deployed baseline retains
measured cross-signer offline signal but has no completed held-out end-to-end phrase metric and
runs below the `>=15 fps` target.

Consequence: Keep production assets and behavior frozen. Report the app as an isolated-sign/gloss
research demonstrator. Resume recognition R&D only with materially new data or model evidence and
a preregistered gate. F22 validates baseline integrity but cannot establish recognition accuracy.

Recorded drift: the model, vocabulary, model manifest, and MediaPipe task hashes match E6-0, while
`recognition_config.json` contains a pre-existing disabled `post_commit_rearm` block and therefore
does not match the E6-0 config hash. F22 must verify the flag remains disabled; strict rollback uses
the recorded recovery commit/tag.

Related files: `POST_C0_PRODUCT_SCOPE_DECISION.md`, `C0B_POST_I320_DATA_DECISION.md`,
`E6_0_BASELINE_FREEZE.md`, `../device-smoke.md`, `../eval-protocol.md`.

## ADR-RU-061 - Close Phase 1 And Open Only Bounded Phase 2 Preparation

Date: 2026-08-12

Status: Accepted from the completed P1-FV1 protected result and preparation audit.

Decision: Freeze P1-FV1 as the full-vocabulary landmark control. Do not tune or deploy it. Open
Phase 2 only through a deterministic 40-sign error-registry pilot and a pixel crop-quality gate.
Intermediate fusion and RGB top-k reranking are competing hypotheses. No full 236-sign extraction,
hybrid training, detector retraining, or Android integration is authorized.

Evidence: P1-FV1 reached top-1 `0.6095` and top-5 `0.8866`, with 58 classes below F1 `0.50`, which
supports testing whether appearance evidence can rerank landmark candidates. Earlier upper-body RGB
and naive fusion failed, and current MediaPipe/pose/I320 ROI routes did not pass reliability gates.
The Phase 2 scan found all 2,519 pilot raw videos present but only 1,133 synchronized rows and 550
immediately eligible training clips (10-16 per sign). Pixel crop quality remains unmeasured.

Consequence: Run P2-P2 before any recognition model. Reuse prior ROI routes only as explicit
controls/hypotheses with their no-go history attached. If no route passes, stop or collect materially
new ROI data. If one passes, revisit data sufficiency and fresh evaluation before P2-P3. Preserve
v3.0 and all Android assets.

Related files: `PHASE2_PREPARATION_RESULT.md`, `HYBRID_FUSION_DESIGN.md`,
`EVALUATION_AND_ACCEPTANCE_GATES.md`, `EXPERIMENT_MATRIX.md`.
