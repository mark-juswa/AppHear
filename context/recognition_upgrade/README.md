# AppHear Recognition Upgrade

**Purpose:** Source-of-truth index for the planned transition from the deployed landmark-only
recognizer to an experimentally proven hybrid landmark + RGB recognizer.

**Scope:** Research, contracts, experiments, migration, and acceptance gates only. No document in
this folder authorizes implementation or replacement of production assets.

**Status:** Phase 1 full-vocabulary landmark-baseline preparation is active. The fully hashed
236-class canonical manifest, full tensor assembly, and equal-budget TCN training smoke have
passed. Full six-run training is the next developer-run step. E1-E6 and C0-B0
remain historical evidence: geometry, embedding rejection, the `KNOW/HELLO` specialist, and the
AppHear-domain detector-derived crop route did not pass their registered gates. The protected
production v3.0 path remains unchanged.

**Last updated:** 2026-08-11.

## Direction

The approved research roadmap is:

1. build the strongest trustworthy 236-sign v3.0 `[96,258]` landmark baseline;
2. use its held-out confusion evidence to develop an isolated-sign hybrid landmark + RGB
   hand-crop recognizer;
3. develop continuous boundary/gloss recognition only after natural phrase-level data with
   gloss sequences and boundary annotations exists;
4. add sentence/language intelligence only after visual recognition is reliable.

Phase 1 compares the existing production TCN with one mask-aware TCN branch. It does not authorize
ST-GCN, richer geometry, specialists, rejection experiments, global RGB, Android export, or
production replacement. `DYNAMIC_MIXED_RECOGNITION_ROADMAP.md` is retained as historical design
evidence, not the active execution order. Production v3.0 remains frozen until a later migration
is separately approved and passes offline, export, and device gates.

## Read Order Before Any Implementation

1. Parent contracts: `../project-overview.md`, `../architecture.md`,
   `../runtime-constraints.md`, `../eval-protocol.md`, `../feature-schema.md`,
   `../code-standards.md`, `../library-docs.md`, `../progress-tracker.md`.
2. Existing accuracy history: `../recognition-accuracy.md`, `../encoder-upgrade.md`,
   `../device-smoke.md`, `../recorder-pipeline.md`.
3. This folder: `CURRENT_PIPELINE_AUDIT.md`, `ARCHITECTURE_DECISIONS.md`,
   `TARGET_ARCHITECTURE.md`, `FEATURE_SCHEMA_PLAN.md`, `DATASET_UPGRADE_PLAN.md`.
4. Then model/fusion/temporal/deployment plans, experiment matrix, gates, migration, risks,
   rollback, open questions, and readiness checklist.

## Documents

| File | Authority |
|---|---|
| `CURRENT_PIPELINE_AUDIT.md` | Verified current implementation and measured state |
| `TARGET_ARCHITECTURE.md` | Proposed end-state and component boundaries |
| `ARCHITECTURE_DECISIONS.md` | Accepted, rejected, deferred, and experimental decisions |
| `DATASET_UPGRADE_PLAN.md` | Capture, metadata, split, annotation, and scale strategy |
| `FEATURE_SCHEMA_PLAN.md` | Experimental multimodal contract and parity rules |
| `MODEL_RESEARCH_PLAN.md` | Candidate encoders and research evidence |
| `HYBRID_FUSION_DESIGN.md` | Landmark/RGB stream and fusion design |
| `TEMPORAL_AND_BOUNDARY_PLAN.md` | Timestamping, variable duration, boundary, CTC path |
| `ANDROID_DEPLOYMENT_PLAN.md` | Android stages, runtime budget, delegates, profiling |
| `EXPERIMENT_MATRIX.md` | Ordered ablations with go/no-go criteria |
| E1_MATCHED_RUNBOOK.md | Exact three-seed training, resume, evaluation, and handoff procedure |
| `EVALUATION_AND_ACCEPTANCE_GATES.md` | Metrics and real-user release thresholds |
| E2_CROP_QUALITY_RUNBOOK.md | Bounded RGB crop generation, blinded review, and E2 commands |
| `E2B_ROI_RECOVERY_PLAN.md` | Paired control-vs-pose ROI-recovery contract and gates |
| `E2B_PHASE_A_RESULT.md` | Verified E2b result, audit consistency finding, and no-go decision |
| `E2C_TEMPORAL_TRACKING_PLAN.md` | Paired IMAGE-vs-VIDEO tracker contract, gates, and commands |
| `E2C_TEMPORAL_TRACKING_RESULT.md` | Verified E2c automatic result and no-go decision |
| `E2D_DETECTOR_OPERATING_POINT_PLAN.md` | Final MediaPipe threshold sweep, automatic gates, smoke evidence, and command |
| `E2D_DETECTOR_OPERATING_POINT_RESULT.md` | Verified E2d artifacts, metrics, no-go decision, and stop-rule consequence |
| `E2E_ALL_HAND_GOLD_RESULT.md` | Corrected all-hand MediaPipe recall audit, gate decision, and E2e-C0 handoff |
| `E2E_C0_DETECTOR_SCREENING_PLAN.md` | Approved E2e-C0 candidates, dataset contract, metrics, and gates |
| `E2E_C0_CAPTURE_RUNBOOK.md` | N0/P1 recording, sampling, review, and validation procedure |
| `E2E_C0_CAPTURE_RESULT.md` | Frozen N0/P1 artifacts, hashes, counts, limitations, and C0-A handoff |
| `C0A_HAGRID_PREFLIGHT.md` | HaGRID checkpoint/license boundary, smoke scaffold, and user-run handoff |
| `C0A_HAGRID_SMOKE_RESULT.md` | Completed HaGRID smoke threshold sweep and no-go decision for direct promotion |
| `C0_DECISION_PACKAGE_PLAN.md` | Next route-decision package for detector pilot versus upper-body/full-frame RGB fallback |
| `C0_ROUTE_DECISION_REPORT.md` | Selected staged two-branch comparison and E3-B0 RGB feasibility as the next executable path |
| `E3_B0_RGB_FEASIBILITY_PLAN.md` | E3-B0 RGB inventory/preflight contract, verified preflight results, and tensor-smoke handoff |
| `E3_B0_PILOT_01_RESULT.md` | Completed bounded RGB pilot metrics, interpretation, no-promotion decision, and next pilot recommendation |
| `E3_B0_PILOT_02_RESULT.md` | Completed strict-support RGB pilot metrics and no-go decision for standalone full-frame tiny RGB |
| `E3_B1_IMPROVED_RGB_PLAN.md` | Prepared MobileNetV3 upper-body RGB pilot, gates, risks, and user-run next action |
| `E3_B1_RESULT.md` | Completed MobileNetV3 upper-body RGB result, E3-B0 comparison, class-order correction, and no-go decision |
| `E3_B2_SAME_SIGNER_SANITY_PLAN.md` | Prepared intentionally signer-leaky RGB sanity check, gates, warnings, and commands |
| `E3_B2_RESULT.md` | Completed same-signer RGB sanity result, comparison, no-go decision, and next fork |
| `E3_B3_FUSION_SMOKE_PLAN.md` | Prepared signer-disjoint landmark+RGB fusion smoke, branch controls, gates, and commands |
| `E3_B3_RESULT.md` | Completed fusion smoke result, branch comparison, no-go decision, and landmark-first next action |
| `E3_B4_LANDMARK_TEMPORAL_PLAN.md` | Prepared landmark-only Conv1D vs TCN vs masked-TCN temporal comparison |
| `E3_B4_RESULT.md` | Completed E3-B4 result, masked-TCN pilot pass, and larger-validation next action |
| `E3_B5_LANDMARK_TEMPORAL_SCALE_PLAN.md` | Prepared 50-class three-seed landmark-temporal scale validation |
| `E3_B5_RESULT.md` | Completed E3-B5 result, no-promotion decision, and E3-B6 recommendation |
| `E3_B6_FEATURE_AUGMENTATION_PLAN.md` | Prepared frozen-split landmark derived-feature augmentation experiment |
| `E3_B6_RESULT.md` | Completed derived-feature result, no-promotion decision, and E3-B7 ablation recommendation |
| `E3_B7_FEATURE_ABLATION_PLAN.md` | Prepared frozen-split derived-feature subset ablation |
| `E3_B7_RESULT.md` | Completed reduced-feature ablation, no-promotion decision, and fusion recommendation |
| `E3_C_FUSION_PLAN.md` | Prepared frozen-split landmark + RGB fusion experiment, gates, smoke result, and developer-run command |
| `E3_C_RESULT.md` | Completed E3-C result: upper-body frozen-MobileNet RGB fusion no-go; landmark-only control remains strongest |
| `E4_A_LANDMARK_GENERALIZATION_PLAN.md` | Landmark/data generalization audit plan and output contract |
| `E4_A_RESULT.md` | Completed E4-A audit: only 4 candidate-keep classes; E4-C targeted collection then E4-B recommended |
| `E4_C_TARGETED_COLLECTION_PLAN.md` | Planned targeted collection and label/video review package derived from E4-A outputs |
| `E4_C_LOCAL_SUPPLEMENTARY_AUDIT_RESULT.md` | Completed metadata audit for replacing E4-C target signs with `E:\local` practical-vocabulary candidates |
| `E4_C_LOCAL_SUPPLEMENTARY_VALIDATION_RESULT.md` | Completed video-readability and split-feasibility validation for revised E4-C local candidates |
| `E4_B_LOCAL_SUPPLEMENTARY_MANIFEST_RESULT.md` | Completed reviewed manifest/split package for the bounded E4-B local supplementary pilot |
| `E4_B_STRICT_7_SIGNER_DISJOINT_MANIFEST_RESULT.md` | Completed strict 7-sign signer-disjoint manifest after excluding two-signer classes |
| `E4_B_STRICT_7_RUNNER_PACKAGE.md` | Prepared strict 7-sign extraction/training runner and smoke result; pilot 01 extraction is diagnostic-only |
| `E4_B_STRICT_7_CORRECTED_DATASET_RESULT.md` | Corrected pilot 01 legacy temporal-source flaw; pilot 02 corrected dataset was approved only for bounded training |
| `E4_B_STRICT_7_TRAINING_RESULT.md` | Completed pilot 02 training; no-go due held-out collapse and split/provenance confound |
| `E4_D_SAME_PROVENANCE_PLAN.md` | Prepared Stage-E-only same-provenance diagnostic manifest/runner and smoke result |
| `E4_D_EXTRACTION_RESULT.md` | Completed E4-D extraction; same-provenance tensor quality passed and diagnostic training is next |
| `E4_D_TRAINING_RESULT.md` | Completed E4-D training; same-provenance fixed collapse but production remains blocked |
| `E4_E_ERROR_REVIEW_PACKAGE.md` | Prepared focused review package for BYE, THANKYOU, and NO failure analysis |
| `E4_E_REVIEW_RESULT.md` | Completed E4-E review; label issues found mostly in THANKYOU, while BYE/NO remain real failures |
| `E4_F_CLEANED_DIAGNOSTIC_PLAN.md` | Prepared cleaned diagnostic package excluding E4-E relabel rows |
| `E4_F_CLEANED_DIAGNOSTIC_RESULT.md` | Completed cleaned diagnostic; cleanup helped but BYE/NO remain severe failures |
| `E4_G_BYE_YES_NO_SEPARABILITY_RESULT.md` | Completed focused BYE/NO/YES separability diagnostic; target group still collapses on held-out signer |
| `E4_H_VARIANT_INTERVENTION_PACKAGE.md` | Prepared and auto-triaged controlled BYE/NO/YES variant-review package; weak signs deferred from next core benchmark |
| `E4_I_RELIABLE_CORE_PACKAGE.md` | Prepared 4-sign reliable-core benchmark using GOOD, HELLO, SORRY, and YES; weak local signs excluded |
| `E4_I_RELIABLE_CORE_RESULT.md` | Completed 4-sign reliable-core benchmark; gate failed due unstable checkpoint selection and weak YES |
| `E4_J_RELIABLE_CORE_PACKAGE.md` | Prepared 3-sign reliable-core benchmark using GOOD, HELLO, and SORRY; smoke/check passed |
| `E4_J_RELIABLE_CORE_RESULT.md` | Completed 3-sign benchmark; Conv1D latest stable, best-checkpoint policy unstable |
| `E4_K_CHECKPOINT_POLICY_RESULT.md` | Completed checkpoint-policy diagnostic; fixed/latest Conv1D is the only stable next offline policy |
| `E4_L_ONE_SIGN_EXPANSION_PACKAGE.md` | Prepared MAKE one-sign expansion package; limited extraction smoke and basic check passed |
| `E4_L_RESULT_AND_SCREENING_PIVOT.md` | Completed MAKE expansion result, no-go decision, and dual-source screening pivot |
| `E4_M_DUAL_SOURCE_SCREEN_RESULT.md` | Completed dual-source ASL Citizen/local candidate preflight and ranked next candidate queue |
| `E4_N_DUAL_SOURCE_5SIGN_PACKAGE.md` | Prepared bounded 5-sign dual-source training screen for `GOOD`/`HELLO`/`SORRY` + `HAVE`/`KNOW` |
| `E4_N_RESULT.md` | Completed E4-N result, gate pass, and authorization for GET/WELCOME2 extraction screen |
| `E4_O_GET_WELCOME2_PACKAGE.md` | Prepared 7-sign GET/WELCOME2 extraction/training screen |
| `E4_Q_RESULT.md` | Completed focused confusion resolver result: landmark-only resolver no-go |
| `DYNAMIC_MIXED_RECOGNITION_ROADMAP.md` | Current source-of-truth architecture for landmark-primary dynamic mixed recognition |
| `E4_R_STABLE_CANDIDATE_TIERING_RESULT.md` | Completed tiering over 236 labels; guarded Tier-A signs are `GOOD`, `HELLO`, `HAVE`, and `KNOW` |
| E4_S_STABLE_PRIMARY_PACKAGE.md | Completed stable-primary 4-sign landmark package; closed-set pass but SORRY false-commits as GOOD |
| E4_T_ROUTER_SIMULATION_RESULT.md | Completed offline router simulation; simple confidence/margin thresholds no-go for rejecting SORRY |
| `E4_AF_TO_E5_BATCH_STRATEGY.md` | Current next-step strategy: short no-sign acceptance safety floor, then large dual-source candidate screening instead of one-sign loops |
| `E5_A_DUAL_SOURCE_BATCH_SCREEN_RESULT.md` | Completed 236-label inventory screen; strict dual-source recommendation is historical, ASL-led strategy is current |
| `E5_B_ASL_LED_PRIMARY_BATCH_PACKAGE.md` | Prepared ASL Citizen-led 50-class primary diagnostic with local supplementary rows where available |
| `E5_C_50CLASS_TIERING_RESULT.md` | Completed E5-B metrics tiering; E5-B is not exportable and E5-D reduced-primary validation is next |
| `E5_D_REDUCED_PRIMARY_VALIDATION_PACKAGE.md` | Prepared reduced 15-sign primary validation package and user-run training command |
| `E5_D_REDUCED_PRIMARY_VALIDATION_RESULT.md` | Completed E5-D training result; reduced-primary strategy improved materially but still needs E5-E tiering before routing/export |
| `E6_PRODUCTION_RECOGNITION_ARCHITECTURE_PLAN.md` | Current E6 architecture and experiment plan after E5-H/E5-I proved threshold-only and shared reject-head paths insufficient |
| `E6_2_LANDMARK_GEOMETRY_RESULT.md` | Completed E6-2 metrics, strict no-go, and preserved future specialist evidence |
| `E6_3_OPEN_SET_REJECTION_PLAN.md` | Approved frozen-v3.0 embedding rejection contract, duplicate audit, data roles, metrics, and stop gates |
| `E6_3_OPEN_SET_REJECTION_PACKAGE.md` | Implemented E6-3 runner, real-data smoke result, full-run commands, outputs, and limitations |
| `E6_3_OPEN_SET_REJECTION_RESULT.md` | Completed extraction, score frontiers, subtype failure analysis, strict no-go, and E6-4 handoff |
| `E6_4_CONFUSION_REGISTRY_PLAN.md` | Frozen-prediction mining contract, duplicate audit, reproducibility rule, and evidence boundaries |
| `E6_4_CONFUSION_REGISTRY_RESULT.md` | Registered `KNOW -> HELLO`, deferred `SORRY -> HAVE`, negative-attraction evidence, and E6-5 boundary |
| `E6_5_KNOW_HELLO_SPECIALIST_PLAN.md` | Duplicate audit, fixed data roles, two-branch design, preregistered gates, and failure paths |
| `E6_5_KNOW_HELLO_SPECIALIST_PACKAGE.md` | Prepared package, real-data smoke evidence, full-run commands, outputs, and limitations |
| `E6_5_KNOW_HELLO_SPECIALIST_RESULT.md` | Completed metrics, checkpoint robustness, no-go decision, and `KNOW` deferral |
| `E6_COMPONENT_DECISION.md` | Consolidated E6 component ledger, blocked E6-6/E6-7 dependencies, do-not-repeat list, and protected-baseline decision |
| `E6_0_BASELINE_FREEZE.md` | Baseline asset/schema/config hash audit and rollback instructions for E6 |
| `E6_1_CONSOLIDATED_EVIDENCE_DATASET_AUDIT.md` | Consolidated E1-E5 duplicate/evidence/dataset audit; final decision: data insufficient, stop modeling |
| `PRODUCT_CORE_DATA_READINESS_PACKAGE.md` | Bounded 8-sign product-core data readiness decision, verified raw-video counts, gaps, no-sign/OOV plan, and gates before modeling can resume |
| `DATASET_MANIFEST_LINEAGE_SCHEMA.md` | Required strict manifest and raw-video lineage schema for any future product-core extraction/training package |
| `product_core_data_readiness/lineage_fix_v1/LINEAGE_FIX_AND_GAP_RECALCULATION_RESULT.md` | Completed raw-video lineage fix, supplementary validation, cleaned counts, real gap recalculation, and decision that more data is still required |
| `product_core_data_readiness/lineage_fix_v1/E6_PRODUCT_CORE_REVIEW_RUNBOOK.md` | Prepared user-run review workflow for the 486 manual-review rows before collection or baseline extraction |
| `product_core_data_readiness/lineage_fix_v1/E6_PRODUCT_CORE_REVIEW_RESULT.md` | Completed human review result: 329 accepted, 157 rejected, final remaining gaps before collection/baseline extraction |
| `product_core_data_readiness/collection_targets_v1/E6_TARGETED_COLLECTION_RUNBOOK.md` | Targeted positive/no-sign/OOV/transition collection targets, folder structure, validator commands, and blocked/unblocked next work |
| `product_core_data_readiness/collection_targets_v1/E6_COLLECTION_AND_SPLIT_PREP_RESULT.md` | Prepared collection validator and split dry-run; current reviewed data fails split gate and more data is required |
| `product_core_data_readiness/collection_targets_v1/E6_COLLECTION_INTEGRATION_RESULT.md` | Integrated historical/new/N0 lineage, excluded 60 copied local videos, completed the 63-row review with all 21 batches accepted, and recorded remaining coverage blockers |
| `product_core_data_readiness/collection_targets_v1/E6_NEGATIVE_REUSE_AUDIT_RESULT.md` | Proved E4-AG duplicates the canonical P1 videos, recovered 197 unique historical development windows, and reduced the remaining negative-context volume gap from 850 to 653 without granting fresh-test credit |
| `product_core_data_readiness/collection_targets_v1/E6_EXISTING_NEGATIVE_SOURCE_SEARCH_RESULT.md` | Validated 200 signer-balanced ASL Citizen OOV videos, filled historical OOV development volume, and established the irreducible 453-window plus fresh-evaluation gap |
| `product_core_data_readiness/collection_targets_v1/E6_NEGATIVE_UPLOAD_REVIEW_PACKAGE.md` | Imported 560 unique short-event negative/OOV clips from one new signer; all 18 session batches passed the 54-row review and remain reserved for provisional fresh evaluation |
| `product_core_data_readiness/collection_targets_v1/E6_V30_FIVE_SIGN_BASELINE_PACKAGE.md` | Completed five-sign v3.0 from-scratch baseline; structural pass but positive accuracy no-go from fresh `KNOW`/`HAVE` collapse |
| `product_core_data_readiness/collection_targets_v1/E6_V30_CONFUSION_ROOT_CAUSE_RESULT.md` | Completed read-only confusion audit; broad deployed encoder evidence supports one isolated warm-start diagnostic next |
| `product_core_data_readiness/collection_targets_v1/E6_V30_FIVE_SIGN_TRANSFER_PACKAGE.md` | Prepared and smoke-validated the one-variable 236-encoder-to-five-class transfer test; full training is user-run |
| `product_core_data_readiness/collection_targets_v1/E6_V30_FIVE_SIGN_TRANSFER_RESULT.md` | Completed transfer result: +17-point fresh gain and `HAVE` repaired, but `KNOW` seed instability exposes validation-split failure; no deployment |
| `product_core_data_readiness/collection_targets_v1/E6_V30_VALIDATION_REPAIR_RESULT.md` | Reassigned existing tensors to balanced complete-signer validation, preserved old AppHear validation as stress, and prepared the final warm-start rerun |
| `product_core_data_readiness/collection_targets_v1/E6_V30_REPAIRED_VALIDATION_TRANSFER_RESULT.md` | Final v3.0 control: stable 88.9% fresh/96.3% historical but `KNOW` domain gap remains; baseline loop closed and E6-2 planning unblocked |
| `E6_2_RICHER_LANDMARK_CONTROL_PLAN.md` | Exact non-duplicative `[96,444]` geometry contract, zero-extension warm start, matched gates, risks, and rollback for E6-2 |
| `E6_2_LANDMARK_GEOMETRY_PACKAGE.md` | Implemented E6-2 package, 21-test result, actual-data smoke evidence, corrected parameter count, and user-run commands |
| `E6_2_LANDMARK_GEOMETRY_RESULT.md` | Completed E6-2 metrics: fresh gain but stress/`HAVE` gate failures; v3.0 retained and handcrafted feature iteration stopped |
| `E4_AF_ACCEPTANCE_POLICY_RESULT.md` | Completed E4-AF policy sweep; policy-only no-go, targeted HELLO-like no-sign expansion required before E5-A |
| `E4_AG_HELLO_LIKE_NOSIGN_PACKAGE.md` | Prepared targeted HELLO-like no-sign capture, expansion, and gate-evaluation package |
| `E4_AG_HELLO_LIKE_NOSIGN_RESULT.md` | Completed E4-AG; targeted HELLO-like no-sign expansion passed offline safety floor and authorizes E5-A screening next |
| `E5_A_DUAL_SOURCE_BATCH_SCREEN_RESULT.md` | Completed E5-A 236-label dual-source batch screen; only WANT2 is strict next primary candidate |
| `MIGRATION_PHASES.md` | Safe transition sequence |
| `RISK_REGISTER.md` | Failure modes, warnings, mitigations, fallbacks |
| `ROLLBACK_AND_COMPATIBILITY_PLAN.md` | Isolation and recovery contract |
| `OPEN_QUESTIONS.md` | Unknowns that require measurements or product decisions |
| `IMPLEMENTATION_READINESS_CHECKLIST.md` | Approval gate before code changes |

## Sources Of Truth

- Current runtime behavior: Kotlin under `android/app/src/main/java/com/example/apphear/pipeline/`
  plus `android/app/src/main/assets/{model_manifest.json,recognition_config.json}`.
- Current feature math: `pipeline/features/contract.py` and Kotlin `S4Features.kt`.
- Current dataset/splits: `pipeline/config/*.yaml`, `artifacts/splits.json`, raw ASL Citizen videos,
  and recorder/local raw videos.
- Current model/eval: `model/`, `eval/`, run artifacts under
  `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/runs/`.
- This folder controls only the upgrade plan. Existing parent contracts still win for production.

## Architecture Decisions

- Hybrid input is selected as the target hypothesis, not yet a proven production winner.
- Isolated recognition is the first release scope; continuous gloss recognition is a later phase.
- Production v3.0 remains frozen until all offline and device gates pass.

## Assumptions, Risks, Open Questions, Next Action

- **Assumption:** raw videos remain legally usable for feature/crop derivation; rights audit pending.
- **Primary risk:** insufficient signer diversity, especially in local supplementary clips.
- **Open question:** who can perform fluent-ASL label/variant review for the confusion-review-first classes.
- **Approved decision (2026-08-07):** the bounded first baseline vocabulary is `GOOD`, `HELLO`, `SORRY`, `HAVE`, and `KNOW`; `HAVE` retains its documented provisional four-local-signer exception. `THINK`, `TAKE`, and `SELL` are deferred expansion candidates.
- **Completed assignment (2026-08-09):** `E6_FIVE_SIGN_ASSIGNMENT_RESULT.md` records a structural gate pass for 2,334 assigned rows: 1,227 positives, 547 historical development negatives, and 560 provisional fresh negative evaluation clips. No signer group or raw-video hash crossed incompatible roles. The lean pilot explicitly waives the unverified 1,000-negative engineering target while preserving the 453-row shortfall as a limitation. `HAVE` has only four validation clips, and the fresh negative set has one signer, so neither supports a production claim.
- **Prepared baseline (2026-08-09):** `E6_V30_FIVE_SIGN_BASELINE_PACKAGE.md` defines the clean raw-video re-extraction and deployed-family streaming-TCN experiment. Its 10-row actual-data smoke passed `[10,96,258] -> [10,96,5]`, one training step, and checkpoint reload. Full extraction and training have not started.
- **Completed extraction/control (2026-08-09):** all 1,227 positive clips extracted with zero failures or missing rows; tensor and signer-disjoint checks passed. Three clips have zero detected hands and remain as honest baseline evidence. The deployed 236-class model scored fresh-test top-1 `0.5867` (`0.9467` when restricted to the five labels), showing that broad-vocabulary competition is the current error source for this subset.
- **Completed five-sign training (2026-08-09):** all three streaming-TCN seeds completed, but the positive gate failed. Mean latest fresh top-1 was `0.7344`; fresh `KNOW` recall collapsed to `0.0222` mean (`KNOW -> HELLO`) and fresh `HAVE` recall was `0.6667` (`HAVE -> GOOD`). Historical results were much stronger, and the deployed model restricted to these five labels retained fresh `KNOW 0.80` and `HAVE 1.0`, so checkpoint selection and invalid fresh labels do not explain the failure. No trained E6 checkpoint is approved.
- **Next action:** review and approve `E6_COMPONENT_DECISION.md`. No new architecture, dataset repair, vocabulary expansion, training, routing, RGB, export, or Android work is authorized automatically.


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-017 apply; component-specific decisions in this document apply only after their experiment gate passes.
- **Assumptions:** Any forecast or unmeasured dimension remains a hypothesis, not a project fact.
- **Open questions:** Unresolved items are tracked in this document and `OPEN_QUESTIONS.md`.
- **Risks:** Applicable failure modes and fallbacks are tracked in this document and `RISK_REGISTER.md`.
- **Next required action:** Follow the explicit next action above and the ordering in `EXPERIMENT_MATRIX.md`; do not skip gates.













































## 2026-07-31 - E4-O Result And E4-P Prepared

- E4-O result recorded in `E4_O_RESULT.md`: full extraction succeeded, but recognition gate failed. `GET` is quarantined because local extracted `GET` collapsed mostly into `GOOD`.
- E4-P package recorded in `E4_P_EXISTING_FEATURE_20SIGN_PACKAGE.md`.
- E4-P runner: `pipeline/rgb/e4_p_existing_feature_20sign_pressure.py`.
- E4-P run directory: `artifacts/recognition_upgrade/e4_generalization/e4_p_existing_feature_20sign_pressure_01`.
- E4-P is a no-extraction 20-sign pressure test using existing ASL Citizen and local supplementary feature tensors.
- Smoke and structural checks passed. Full training remains user-run.
- Historical next action at that time: developer ran E4-P training and metrics were later analyzed. Superseded by E4-P result, E4-Q result, and `DYNAMIC_MIXED_RECOGNITION_ROADMAP.md`.

## 2026-07-31 - E4-P Result And E4-Q Confusion Resolver Prepared

- E4-P full training completed structurally but failed the 20-sign pressure gate. Mean latest test was `0.6643`; the critical repeated failure was `SORRY` collapsing mostly to `BECOME` and sometimes `HELP`.
- The next path is not blind vocabulary expansion. The selected design is a dynamic recognizer strategy: stable signs can stay in a global model, while known similar-looking signs require a specialist confusion resolver or rejection path.
- E4-Q package recorded in `E4_Q_CONFUSION_RESOLVER_PACKAGE.md`.
- E4-Q runner: `pipeline/rgb/e4_q_confusion_resolver.py`.
- E4-Q run directory: `artifacts/recognition_upgrade/e4_generalization/e4_q_confusion_resolver_sorry_become_help_01`.
- E4-Q prepared `219` rows for `GOOD`, `SORRY`, `HELP`, and `BECOME`; base input `[96,258]`, derived input `[96,728]`.
- E4-Q smoke and structural check passed. Full training remains user-run.
- Historical next action at that time: developer ran E4-Q and metrics were later analyzed. Superseded by `E4_Q_RESULT.md` and `DYNAMIC_MIXED_RECOGNITION_ROADMAP.md`.


## 2026-07-31 - Dynamic Mixed Recognition Roadmap Approved

- Current source-of-truth roadmap: `DYNAMIC_MIXED_RECOGNITION_ROADMAP.md`.
- E4-Q result recorded in `E4_Q_RESULT.md`: the focused `GOOD/SORRY/HELP/BECOME` landmark-only resolver failed. Best mean latest test was `0.7137`; minimum latest `SORRY` stayed far below gate.
- Architectural consequence: preserve landmark-primary recognition for stable signs, but route known hard groups through a confusion registry to specialist resolvers or rejection.
- `SORRY/BECOME/HELP` is now an active confusion group requiring visual evidence and/or data/variant repair before production promotion.
- `GET`, `MAKE`, `BYE`, `NO`, `THANKYOU`, and `YES` remain deferred or unstable under the evidence already recorded.
- Next action: prepare Phase 1 stable-candidate tiering and stable-primary landmark training. Android integration, production export, global hybrid fusion, and broad vocabulary expansion remain blocked.





## 2026-07-31 - E4-R Stable-Candidate Tiering Complete

- Result document: `E4_R_STABLE_CANDIDATE_TIERING_RESULT.md`.
- Runner: `pipeline/rgb/e4_r_stable_candidate_tiering.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_r_stable_candidate_tiering_01`.
- E4-R ranked all `236` inventory labels using existing E4-M/E4-N/E4-O/E4-P/E4-Q evidence only.
- Tier counts: `A_primary_ready_guarded=4`, `B_confusion_specialist_or_repair=12`, `B_borderline_review=6`, `C_defer_more_evidence=9`, `D_inventory_only=205`.
- Primary-ready guarded signs for E4-S: `GOOD`, `HELLO`, `HAVE`, `KNOW`.
- `SORRY` is not primary-ready despite earlier local-core strength because E4-P/E4-Q showed severe `SORRY -> BECOME/HELP` failure.
- Next action: prepare E4-S stable-primary landmark model package. Do not start Android integration, production export, broad RGB/hybrid work, or specialist resolver training before E4-S is defined and approved.







## 2026-08-02 - E4-W Mixed Landmark Specialist Simulation Result

- Result document: `E4_W_MIXED_LANDMARK_SPECIALIST_SIMULATION_RESULT.md`.
- Runner: `pipeline/rgb/e4_w_mixed_landmark_specialist_simulation.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_w_mixed_landmark_specialist_simulation_01`.
- E4-W simulates E4-S primary `GOOD/HELLO/HAVE/KNOW` plus conditional E4-V GOOD/SORRY landmark specialist routing.
- Combined test set: `118` rows, with `88` active known-sign rows and `30` withheld `SORRY` rows.
- Primary-alone mean combined accuracy was `0.7345` with `SORRY` recall `0.0000`.
- Mixed mean accuracy was `0.9718`, minimum seed accuracy `0.9661`, mean/min `SORRY` recall `0.9667`, mean/min `GOOD` recall `0.9667`, and maximum false `GOOD -> SORRY` correction rate `0.0333`.
- Structural check passed with `--require-metrics --require-predictions`.
- Decision: dynamic mixed recognition is now supported by a first positive offline proof. The next step is broader routed-system validation with no-sign/OOV and source-disjoint checks, not Android export or production replacement.

### E4-X Routed System Validation Result - 2026-08-02

- Result document: `E4_X_ROUTED_SYSTEM_VALIDATION_RESULT.md`.
- Runner: `pipeline/rgb/e4_x_routed_system_validation.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_x_routed_system_validation_01`.
- Source runs: E4-S stable primary, E4-V GOOD/SORRY specialist, and E2e-C0 `n0_capture_06`.
- Simulated decision path: E4-S primary -> conditional GOOD/SORRY specialist -> confidence accept/reject -> final class or `NO_SIGN`.
- Dataset rows: `451` total; validation/test `97/238`; sources were `221` E4-S active rows, `50` E4-S withheld SORRY rows, and `180` reviewed N0 rows represented as zero-landmark/no-frame sequences.
- Selected validation policy: primary confidence `0.95`, specialist confidence `0.50`.
- Test result: mean accepted precision `0.9798`, minimum accepted precision `0.9739`, mean positive coverage `0.9746`, minimum positive coverage `0.9661`, max zero-landmark N0 false-commit rate `0.0000`, mean/min SORRY recall `0.9667`, mean/min GOOD recall `0.9667`.
- Structural check passed with `--require-metrics --require-predictions`.
- Decision: routed system passes the zero-landmark no-hand probe, but real MediaPipe-extracted N0/P1 feature validation remains required before Android/export.

### E4-Y Real No-Sign Feature Validation Result - 2026-08-02

- Result document: `E4_Y_REAL_NOSIGN_FEATURE_VALIDATION_RESULT.md`.
- Runner: `pipeline/rgb/e4_y_real_nosign_feature_validation.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_y_real_nosign_feature_validation_01`.
- E4-Y extracted real MediaPipe/schema v3.0 `[96,258]` windows from reviewed E2e-C0 N0/P1 footage, then evaluated the E4-X routed policy.
- Bounded probe rows: `24` N0 and `24` P1; no-sign validation/test split `16/32`; combined test rows after adding positives: `150`.
- Feature quality: N0 mean hand-hit `0.0130`, P1 mean hand-hit `0.8359`, pose-hit `1.0000` for both.
- Structural check passed with `--require-metrics --require-predictions`, but the recognition false-commit gate failed.
- Test summary: mean accepted precision `0.7844`, minimum accepted precision `0.7687`, positive coverage `0.9746`, max real no-sign false-commit rate `0.9688`, GOOD/SORRY recall `0.9667`.
- False commits were severe: N0 false commits ranged `13/16` to `16/16`; P1 false commits ranged `13/16` to `15/16` by seed.
- Decision: Android/export remains blocked. Next step is a signing/no-sign gate experiment before the routed recognizer can commit glosses.

### E4-Z Signing/No-Sign Gate Result - 2026-08-02

- Result document: `E4_Z_SIGNING_GATE_RESULT.md`.
- Runner: `pipeline/rgb/e4_z_signing_gate.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_z_signing_gate_01`.
- E4-Z compared rule-based motion/presence gates and a tiny learned summary-feature MLP before the E4-S/E4-V routed recognizer.
- Dataset rows: `319`; sources were `221` E4-S active rows, `50` withheld SORRY rows, `24` N0 rows, and `24` P1 rows from E4-Y.
- Structural check passed with `--require-metrics`, but the gate failed.
- Rule gates removed N0/P1 false commits but destroyed positive coverage (`~0.32` to `0.40`) and reduced SORRY recall to `0.0000`.
- Learned summary MLP improved coverage to `0.5169` and kept max no-sign false-commit rate to `0.09375`, but SORRY recall remained unacceptable: mean `0.1111`, min `0.0000`.
- Decision: do not proceed to Android/export. Next step is E4-AA no-sign dataset expansion and stronger temporal signing-gate design.

### E4-AA No-Sign Temporal Gate Package Prepared - 2026-08-02

- Package document: `E4_AA_NOSIGN_TEMPORAL_GATE_PACKAGE.md`.
- Runner: `pipeline/rgb/e4_aa_nosign_temporal_gate.py`.
- Smoke run: `artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_smoke_01`.
- E4-AA expands from E4-Z by building real MediaPipe/schema v3.0 no-sign windows from reviewed N0/P1 captures and training a small temporal Conv1D signing/no-sign gate before the E4-S/E4-V routed recognizer.
- Smoke status: prepared `[4,96,258]` no-sign features, trained one seed for one epoch, wrote metrics, and structural check passed. This smoke is wiring-only and is not an accuracy decision.
- Resume controls added: `--prepare-only` and `--train-only`; completed clip caches and completed dataset outputs are reused.
- Next action: user runs full E4-AA at `artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_01`, then checks with `--require-metrics`. No Android/export or production replacement is authorized before full metrics are evaluated.

### E4-AA Full No-Sign Temporal Gate Result - 2026-08-02

- Result document: `E4_AA_NOSIGN_TEMPORAL_GATE_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_01`.
- Structural check passed, but the experiment gate failed.
- E4-AA no-sign dataset: `288` rows shaped `[288,96,258]`, with N0 `180` and P1 `108`.
- E4-AA fixed most no-sign false commits: max test no-sign false commit rate `0.0147`.
- E4-AA failed low-motion sign preservation: mean/min SORRY recall `0.1222/0.0000`, and minimum positive coverage `0.6780`.
- Decision: no Android/export. Test conservative threshold/uncertainty policy before changing gate architecture.

### E4-AB Conservative Gate Policy Result - 2026-08-02

- Result document: `E4_AB_CONSERVATIVE_GATE_POLICY_RESULT.md`.
- Runner: `pipeline/rgb/e4_ab_conservative_gate_policy.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_ab_conservative_gate_policy_01`.
- E4-AB reuses E4-AA trained gate models and sweeps conservative thresholds selected to protect `SORRY`/positive coverage.
- Structural check passed, but the experiment gate failed.
- Compared with E4-AA, mean SORRY recall improved from `0.1222` to `0.6778`, mean positive coverage improved from `0.7345` to `0.8983`, and max no-sign false commit remained acceptable at `0.0441`.
- However, seed `202` still produced test SORRY recall `0.1000`; probability inspection showed true SORRY windows overlapped no-sign under that model.
- Decision: threshold tuning alone is insufficient. Next step is E4-AC low-motion-aware gate training/objective, not Android/export or broad vocabulary expansion.

### E4-AC Low-Motion-Aware Signing Gate Result - 2026-08-02

- Result document: `E4_AC_LOW_MOTION_AWARE_GATE_RESULT.md`.
- Runner: `pipeline/rgb/e4_ac_low_motion_aware_gate.py`.
- Best run directory: `artifacts/recognition_upgrade/e4_generalization/e4_ac_low_motion_aware_gate_01`.
- E4-AC retrained the E4-AA temporal signing/no-sign gate with explicit low-motion `SORRY` weighting.
- Structural check passed, but the strict experiment gate failed narrowly.
- Best run metrics: mean/min accepted precision `0.9548/0.9492`, mean/min positive coverage `0.9746/0.9661`, max no-sign false commit `0.0441`, mean/min GOOD recall `0.9667/0.9667`, mean/min SORRY recall `0.9667/0.9667`.
- E4-AC is the first gate result that preserves SORRY while controlling no-sign false commits, but it is not approved for Android/export because min accepted precision is below `0.95` and the no-sign dataset remains small.
- Decision: use E4-AC as the basis for the next gate iteration. Next step should focus on false-commit review/hard-negative expansion, especially P1/N0 windows predicted as `HELLO`, not vocabulary expansion or Android integration.

### E4-AD False-Commit Review Result - 2026-08-02

- Result document: `E4_AD_FALSE_COMMIT_REVIEW_RESULT.md`.
- Runner: `pipeline/rgb/e4_ad_false_commit_review.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_ad_false_commit_review_01`.
- Structural check passed with panels.
- Generated `51` panels: `28` false commits and `23` hard-negative candidates.
- Residual false commits are concentrated as no-sign -> `HELLO`: `test:N0->HELLO=2`, `test:P1->HELLO=7`, `train:P1->HELLO=3`, `val:P1->HELLO=15`; one train P1 row became `KNOW`.
- Decision: the remaining gate error is mostly HELLO-like ordinary-hand no-sign, especially P1. Test false commits are diagnostic only and must not be added to training.

### E4-AE Hard-Negative Weighted Gate Result - 2026-08-02

- Result document: `E4_AE_HARD_NEGATIVE_GATE_RESULT.md`.
- Runner: `pipeline/rgb/e4_ae_hard_negative_gate.py`.
- Corrected run directory: `artifacts/recognition_upgrade/e4_generalization/e4_ae_hard_negative_gate_02`.
- Structural check passed, but experiment gate failed.
- Upweighted `12` train-split hard negatives from E4-AD with hard-negative weight `6.0`.
- Metrics: mean/min accepted precision `0.9605/0.9417`, mean/min positive coverage `0.9746/0.9661`, max no-sign false commit `0.0882`, mean/min GOOD recall `0.9667/0.9667`, mean/min SORRY recall `0.9667/0.9667`.
- Decision: naive hard-negative weighting is not the solution; it worsened minimum precision compared with E4-AC. The best current gate remains E4-AC `01`, but it is still not Android/export approved.












## 2026-08-03 E5-E Result Update

- Result document: `E5_E_REDUCED_PRIMARY_DECISION_RESULT.md`.
- Runner: `pipeline/rgb/e5_e_reduced_primary_decision.py`.
- Run directory: `artifacts/recognition_upgrade/e5_batch_screening/e5_e_reduced_primary_decision_01`.
- E5-E is a metrics-only decision pass over E5-D; it does not train, extract, export, or modify Android assets.
- Selected next primary candidate: `WASH2`, `THINK`, `TAKE`, `MEET`, `GOOD`, `SELL`, `STAND2`.
- Registered confusion groups: `USE/WORK`, `DRIVE/HAVE`, `DRIVE/WANT2`, `MORNING/USE`, `TAKE/WORK`, `SLEEP/USE`, `RUN2/WASH2`.
- Next action: prepare E5-F offline routed simulation with E4-AG no-sign gate and existing GOOD/SORRY specialist evidence. Android/export remains unapproved.

## 2026-08-03 E5-F Result Update

- Result document: `E5_F_REDUCED_PRIMARY_ROUTED_SIM_RESULT.md`.
- Runner: `pipeline/rgb/e5_f_reduced_primary_routed_sim.py`.
- Strict run: `artifacts/recognition_upgrade/e5_batch_screening/e5_f_reduced_primary_routed_sim_01`.
- Relaxed diagnostic run: `artifacts/recognition_upgrade/e5_batch_screening/e5_f_reduced_primary_routed_sim_02_relaxed_diagnostic`.
- E5-F confirmed that no-sign false commits can remain at `0.0000` in this replay, but the E5-D 15-class model cannot be safely reused as a 7-sign recognizer by thresholding/rejection alone.
- Next action: E5-G clean 7-class primary retrain using the E5-E subset. Android/export remains unapproved.

## 2026-08-09 C0-B0 Toolchain And Annotation-Pilot Checkpoint

- `c0b_toolchain_smoke_03` passed isolated Linux/Python 3.10 one-epoch training, TFLite export,
  MediaPipe reload, and CPU/XNNPACK inference. This proves wiring only; detector training and
  Android integration remain unauthorized.
- Exported smoke model: `10,902,225` bytes; SHA-256
  `079BCA51A3008AF60F1A35E0073D499614AA87E53EC3EA5A00D38713C2DAF06E`.
- Dependency, Windows/Linux path, and COCO `images/` contract failures from Runs 01/02 are fixed
  and regression-tested. Focused C0-B0 validation is `7 passed`; Ruff and mypy pass.
- `prepare --preannotate-mediapipe` now creates editable, untrusted hand-box suggestions after
  unbiased selection. A real two-frame preparation smoke passed.
- Next user-run action: prepare `c0b_training_annotation_pilot_01` with 300 source/signer-balanced
  frames and seed `90827`, then inspect package coverage before opening the review GUI.
- P0/N0/P1, production v3.0 `[96,258]`, Android assets, and production behavior remain frozen.

The 300-frame package is now prepared and structurally valid: 150/150 ASL/local, 36 represented
signers, 300 unique videos/hashes, zero protected overlap, and 299 unreviewed MediaPipe proposal
boxes across 227 frames. Human review is next; condition coverage and training readiness remain
unknown until all rows are adjudicated.

Human review is now complete: 300 accepted frames, 351 boxes, and zero errors. MediaPipe proposal
diagnostics show `0.8490` instance recall overall, `0.9483` on non-blurred hands, `0.3770` on blur,
and `0.6792` complete two-hand recall. Near-face (`1`) and partial (`2`) coverage are too sparse.
Next is one automated condition-targeted top-up, not another random 300-frame review and not Stage
2 detector training yet.


## 2026-08-03 - E5-G/E5-H Reduced Primary Routed Evidence
- E5-G clean 7-class closed-set primary training passed structurally and improved mean latest test accuracy to `0.8472`, with strong `WASH2`, `THINK`, and `TAKE` but weaker `MEET` and `STAND2`. See `E5_G_CLEAN_7_PRIMARY_RESULT.md`.
- E5-H routed simulation was no-go for both full 7-sign and stable-3 commit subsets. Confidence thresholds could not preserve recall while rejecting unsupported signs. See `E5_H_CLEAN_7_ROUTED_SIM_RESULT.md`.
- Decision: do not export to Android. Next required action is E5-I explicit open-set/rejection training or auxiliary accept/reject modeling, not more vocabulary shrinking or softmax threshold tuning.


## 2026-08-03 - E5-I Open-Set Reject Head Result
- E5-I added a two-head landmark model: sign softmax plus supported-vs-unsupported/no-sign accept head. See `E5_I_OPEN_SET_REJECT_HEAD_RESULT.md`.
- Full 7-sign routed result remained no-go: mean/min accepted precision `0.8985/0.8333`, mean/min positive coverage `0.2778/0.2083`, max unsupported false commit `0.0220`, max no-sign false commit `0.0110`, min class recall `0.0000`.
- Stable-3 diagnostic remained no-go but improved coverage: mean/min accepted precision `0.7129/0.5532`, mean/min positive coverage `0.5833/0.4375`, max unsupported false commit `0.1170`, max no-sign false commit `0.0220`.
- Decision: shared accept/reject is useful but too blunt. Next required action is E5-J class-conditioned rejection/per-class accept policy before Android/export.

## 2026-08-09 - Post-E6 Architecture Review

- Source of truth: `POST_E6_ARCHITECTURE_REVIEW.md`.
- E6-2 richer geometry, E6-3 rejection, and E6-5 KNOW/HELLO specialist are no-go; E6-6/E6-7 remain blocked.
- The original upper-body/full-frame RGB bypass was already exhausted by E3-B0/B1/B2/B3/C.
- The unresolved original hybrid prerequisite is a production-compatible AppHear-domain hand ROI detector.
- Exactly one next experiment is selected: `C0B_APPHEAR_HAND_ROI_FEASIBILITY_PLAN.md`.
- Its first stage is inventory and toolchain readiness only. Detector training, RGB recognition,
  fusion, schema changes, export to the app, and Android integration remain unapproved.
- C0-B0 Stage 1 implementation result: `C0B_STAGE1_READINESS_RESULT.md`. The real inventory found
  `42,251` independent candidates after exclusions. The authoritative balanced 24-frame review
  smoke is `c0b_annotation_smoke_03`, covering 12/12 sources and 15 signers. Review completed with
  24 accepted frames and 28 boxes. The main Python 3.11 environment correctly failed the
  deprecated Model Maker preflight and remains untouched.
- Native Windows Python 3.9 dependency installation also failed because `tensorflow-text` has no
  matching Windows distribution. The packaged Python 3.10 Linux Docker Run 03 subsequently passed
  one-epoch training, TFLite export, MediaPipe reload, and CPU inference. The next action is the
  300-frame annotation pilot, not looser pip pins or changes to the main environment.

## 2026-08-10 - C0-B0 Stage 2 Research Authorization

- User authorization is strictly internal research/development only. It does not authorize
  commercial use, restricted-data redistribution, production claims, Android integration, or
  replacement of the frozen recognizer.
- The checked 400-row consolidated manifest is
  `artifacts/recognition_upgrade/e2e_c0/c0b_stage2_research_manifest_01`: `312` train and `88`
  signer-disjoint development rows with zero protected P0/N0/P1 path/hash overlap.
- The deterministic hard-linked COCO package is
  `artifacts/recognition_upgrade/e2e_c0/c0b_stage2_detector_01`, with nested `25/50/100%` train
  subsets and one unchanged development set.
- Next action is only the MobileNetV2-256 float learning curve via
  `model/config/recognition_upgrade/run_c0b_stage2_256_learning_curve.ps1`.
- MobileNetV2-I320, confidence fitting, QAT/INT8, locked P0/N0/P1 evaluation, and Android work are
  blocked until the 256 learning curve is reviewed.

The MobileNetV2-256 learning curve completed on 2026-08-11. AP rose `0.2012 -> 0.2911 -> 0.3447`,
AP50 rose `0.5283 -> 0.7211 -> 0.7747`, and AP75 rose `0.0833 -> 0.2057 -> 0.2859` across nested
`25/50/100%` subsets. This supports the registered I320 comparison but does not pass the AppHear
detector gate. Next user-run action:
`model/config/recognition_upgrade/run_c0b_stage2_i320_learning_curve.ps1`. Threshold fitting,
QAT/INT8, frozen P0/N0/P1 evaluation, and Android remain blocked.

The I320 learning curve subsequently completed and won the COCO comparison at 100%: AP `0.4010`,
AP50 `0.8548`, AP75 `0.3723`. I320 is the accuracy candidate and 256 remains the latency control.
The next action is development-only AppHear matching and threshold evaluation via
`model/config/recognition_upgrade/run_c0b_stage2_development_eval.ps1`. Frozen P0/N0/P1, QAT/INT8,
and Android remain blocked until this comparison is reviewed.

The development threshold comparison is now complete; see
`C0B_STAGE2_DEVELOPMENT_RESULT.md`. I320 won but failed the screening gate: availability `67.26%`,
complete two-hand `41.03%`, IoU50 `63.72%`, and edge `0/4` at zero observed false-positive frames
on only 14 no-hand development frames. Lower thresholds recover more hands only by producing
unacceptable no-hand false positives. Decision: no QAT/INT8, frozen P0/N0/P1 evaluation, Android,
or generic threshold/hyperparameter sweep. The next step is one explicit architecture/data
decision, not another automatic model run.

The required post-I320 inventory decision is complete; see
`C0B_POST_I320_DATA_DECISION.md`. Stage 2 has only `53` training and `14` development no-hand
frames, while all `547` historical E6 development-negative rows overlap protected evaluation
lineage. The `560` fresh provisional negative videos are reserved for evaluation and represent one
signer. Existing data therefore does not justify another I320 round. C0-B0 promotion is stopped,
and detector-derived hand-crop RGB is retired as the immediate mobile route. No new model starts
automatically; v3.0 remains protected.

The required product-scope resolution is complete in `POST_C0_PRODUCT_SCOPE_DECISION.md`. The
long-term silent translator goal is preserved, but the current evidence supports only a bounded
236-sign isolated-sign research prototype. Continuous translation, production signer-independent
reliability, and open-set safety are not supported claims. The next executable action is the
existing F22 device smoke on the current behavior-preserving baseline; no new recognizer is
authorized. Hash verification found the model, vocabulary, manifest, and MediaPipe tasks unchanged,
but `recognition_config.json` contains a pre-existing disabled `post_commit_rearm` block. F22 must
confirm that flag remains disabled; strict rollback remains the E6-0 recovery commit/tag.

F22 was executed on 2026-08-11 and recorded in `F22_DEVICE_SMOKE_RESULT.md`. The result is a partial
pass, not sign-off: startup, clean installation, bounded no-hands behavior, commit/release, sentence
Clear, camera switching, and warm resume passed on Xiaomi M2101K7AG at approximately `6.2-8.2 fps`.
Controlled GOOD committed correctly, while intended HELLO committed as GOOD; edge tracking was
intermittent. Full F22 remains blocked by `PROFILE_STAGES=true`, missing second-signer evidence,
unverified handedness mirror parity, and untested kill-switch/load-failure builds. I320 was not
integrated into the tested APK. No new recognizer work is authorized by this smoke.

The post-F22 existing-data audit is complete in
`POST_C0_BASELINE_EVALUATION_ELIGIBILITY.md`. Independent path/hash verification passed for all
`1,626` August candidate videos. Exactly `306` positive clips (`SELL=150`, `TAKE=80`, `THINK=76`)
across three recorded signer IDs were not found in the E6 baseline or 105 scanned E6/C0 experiment
CSVs; they are authorized only for the next frozen-model isolated replay diagnostic. The other
`760` positives were used by the E6 five-sign baseline and all `560` negatives were used by E6-3.
No natural phrase sessions or project-fresh negatives exist, so held-out end-to-end phrase accuracy
remains blocked. Next: prepare a smoke-first replay harness; do not train, calibrate, export, or
modify Android.

Phase 1 full-vocabulary training and validation selection completed on 2026-08-12. Across three
seeds, the production streaming TCN reached mean validation top-1 `0.6712` and macro-F1 `0.6482`;
the equal-budget mask-aware TCN reached `0.6614` and `0.6439`. The production branch, experiment
configuration, validation report, three best checkpoints, and sealed 2,620-row test tensor are now
hash-frozen in `tcn_comparison_01/config/selection_freeze.json`. The protected test has not been
accessed. Next: execute the guarded one-time protected test, then use its signer/class/confusion and
degradation evidence to decide Phase 2 scope. Android and production assets remain unchanged.

The guarded P1-FV1 test subsequently completed. The production-TCN three-seed ensemble reached
top-1 `0.6095`, top-5 `0.8866`, macro-F1 `0.5964`, worst-decile mean F1 `0.1741`, and uncalibrated
ECE `0.2183` across 2,620 clips and 11 signer IDs. This is below release gates and slightly below
the historical local-supplementary candidate's top-1, although its top-5 is higher. Phase 1 is now
closed as a trustworthy within-experiment landmark control and Phase 2 error registry. Do not tune
against this test or deploy it. The next planned work is bounded Phase 2 preparation driven by the
recorded class/confusion failures, with fresh evaluation evidence required for final claims.

Phase 2 preparation is now active and recorded in `PHASE2_PREPARATION_RESULT.md`. The automated
registry covers all 236 signs; a deterministic 40-sign pilot and four-branch comparison contract
are frozen. Raw RGB exists for all 2,519 selected lineage rows, but only 1,133 currently have
canonical synchronized Stage-E/span metadata, including just 550 ASL Citizen training clips
(10-16 per sign). No RGB was decoded and no crop route is promoted. The immediate next gate is a
bounded pilot-specific crop-quality smoke; hybrid training remains blocked until a route supplies
reliable reviewed hand crops and the data/evaluation sufficiency decision is revisited.





