# E4-A Landmark Generalization And Data-Quality Plan

- **Purpose:** Decide the highest-value landmark/data improvement path after E3-C showed that the current RGB fusion design is a no-go.
- **Scope:** Planning and future offline analysis only. This document does not authorize Android changes, production model replacement, dataset mutation, model training, feature-schema promotion, or deleting/relabeling data.
- **Current status:** Completed on 2026-07-29. See `E4_A_RESULT.md`; final check passed and the next recommendation is E4-C targeted collection then E4-B.
- **Verified project references:** `E3_B5_RESULT.md`, `E3_B6_RESULT.md`, `E3_B7_RESULT.md`, `E3_C_RESULT.md`, `DATASET_UPGRADE_PLAN.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, and the run artifacts listed below.
- **Source-of-truth files:** This plan, `context/recognition_upgrade/README.md`, `EXPERIMENT_MATRIX.md`, `ARCHITECTURE_DECISIONS.md`, and parent `../progress-tracker.md`.
- **Related context files:** `RISK_REGISTER.md`, `OPEN_QUESTIONS.md`, `FEATURE_SCHEMA_PLAN.md`, `MODEL_RESEARCH_PLAN.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../eval-protocol.md`.

## Why E4-A Comes Next

E3-C answered the immediate RGB question: the current upper-body frozen-MobileNet RGB stream overfits and damages fusion. The best verified branch remains landmark-only, specifically the E3-B6 full augmented landmark reference.

The verified metric pattern across E3-B5, E3-B6, E3-B7, and E3-C points to signer generalization and data quality as the next highest-value bottleneck:

- E3-B5 `[96,258]` landmark models learned useful signal but stayed around `0.34` mean best test accuracy on 50 classes.
- E3-B6 `[96,728]` derived landmark features improved mean best test to about `0.3867-0.3883`, but did not pass the validation promotion gate and still had large train-validation gaps.
- E3-B7 reduced feature subsets did not beat the full E3-B6 landmark result.
- E3-C `landmark_aug_only` reproduced E3-B6, while RGB-only and fusion overfit badly.

The next experiment should therefore stop asking “which small model tweak wins?” and instead ask “what exactly prevents this landmark system from generalizing to held-out signers, and what data/vocabulary changes would produce the largest reliable gain?”

## Verified Inputs Available Now

E4-A should consume existing artifacts first, before any new long run:

- E3-B5 frozen split: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed`.
- E3-B5 analysis outputs:
  - `analysis/analysis.json`;
  - `analysis/analysis.md`;
  - `analysis/branch_summary.csv`;
  - `analysis/class_accuracy_summary.csv`;
  - `analysis/confusion_pairs.csv`;
  - `analysis/prediction_bias.csv`;
  - `analysis/seed_summary.csv`.
- E3-B6 metrics: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_03_feature_augmented/metrics/metrics.json`.
- E3-B7 metrics: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_04_feature_ablation/metrics/metrics.json`.
- E3-C metrics: `artifacts/recognition_upgrade/e3_fusion/pilot_02_frozen_50_landmark_rgb/metrics/metrics.json`.
- E3-B5/E3-B6 manifests and selected classes: `pilot_manifest.csv`, `selected_classes.csv`.
- ASL Citizen streaming features: `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/features_streaming/{train,val,test}.npz`.
- ASL Citizen vocabulary: `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/features/vocab.json`.
- Stage-E spans/landmarks if deeper metadata is required: `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/{spans,landmarks}`.

## Non-Goals

E4-A must not:

- train a new model;
- change Android;
- change the production recognizer;
- change the v3.0 feature contract;
- relabel, delete, move, or overwrite dataset files;
- claim real-user readiness;
- tune on the test set for model selection;
- use RGB results as a reason to integrate RGB into Android.

## Primary Questions

E4-A must answer these questions with evidence:

1. Which classes are reliable, borderline, and unreliable under the current landmark-only evidence?
2. Which classes fail consistently across seeds/branches, and which fail only in one architecture?
3. Which confusion pairs are stable enough to require vocabulary merge/split/drop decisions?
4. Which classes look weak because of support count, signer coverage, landmark quality, label/variant ambiguity, or true visual similarity?
5. Which held-out signers or source splits are hardest, and do they correlate with class set, clip length, landmark missingness, or motion profile?
6. Does E3-B6 help the same classes as E3-B5, or does it trade one error group for another?
7. Can a smaller reliable-first vocabulary be selected that would be worth training next?
8. What targeted data should be collected first if the goal is a reliable AppHear vocabulary?
9. Is the current 50-class benchmark still a useful promotion target, or should the next benchmark be a cleaned reliable-vocabulary subset plus a separate hard-confusion set?
10. What is the next training experiment after the audit, and what go/no-go criteria make it honest?

## Proposed E4-A Pipeline

E4-A should produce an offline report from existing artifacts:

`E3 metrics + manifests + selected classes + feature metadata -> class/signer/confusion audit -> vocabulary/data recommendations -> next experiment decision`

### Stage 1 - Artifact Inventory

- **Input:** E3-B5/E3-B6/E3-B7/E3-C run directories.
- **Output:** `inventory.json`, listing present metrics, manifests, class lists, split counts, branch/seed availability, and missing files.
- **Purpose:** Prevent the analysis from silently mixing incompatible runs.
- **Gate:** all cited runs must pass their own `check_report.json` or equivalent metrics check.
- **Risk:** stale or partial metrics can create false conclusions.

### Stage 2 - Class Reliability Audit

- **Input:** per-class accuracy, branch/seed metrics, confusion pairs, prediction bias, and selected-class support.
- **Output:** `class_reliability.csv` and `class_reliability.md`.
- **Fields:** gloss, old class id, train/val/test support, best/worst/mean accuracy, seed variance, branch variance, confusion in/out counts, prediction bias, reliability tier, and recommended action.
- **Reliability tiers:**
  - `candidate_keep`: consistently above threshold and not bias-driven;
  - `borderline_collect_more`: plausible but unstable or under-supported;
  - `confusion_review`: stable confusions require label/variant review;
  - `drop_or_defer`: too weak for near-term user release;
  - `needs_visual_evidence`: likely hand-shape/non-landmark cue limitation, not proven until reviewed.
- **Gate:** no class can be marked `candidate_keep` based only on train accuracy.

### Stage 3 - Confusion Group Audit

- **Input:** confusion pairs from E3-B5 plus comparable predictions from E3-B6/E3-B7/E3-C if available.
- **Output:** `confusion_groups.csv`, `confusion_groups.md`, and a machine-readable grouped JSON.
- **Purpose:** Identify stable near-neighbor groups such as those already observed: `TAKECARE -> EVERYYEAR`, `CROSS3 -> WHALE`, `ROCKINGCHAIR1 -> TRACTOR`, `EDIT1 -> INDEPENDENT`, `RIVER1 -> DEMAND1`, and related variants.
- **Required classification:** each group must be marked as likely `label_variant`, `insufficient_data`, `landmark_geometry_limit`, `motion_timing_limit`, `boundary_span_issue`, or `unknown`.
- **Important:** these causes are hypotheses unless manually verified against video/metadata.

### Stage 4 - Signer And Split Generalization Audit

- **Input:** manifests, participant ids, split labels, per-clip predictions when available.
- **Output:** `signer_generalization.csv` and `signer_generalization.md`.
- **Purpose:** Determine whether poor test accuracy is concentrated in specific held-out signers or broad across the split.
- **Required checks:** per-signer accuracy, per-signer class coverage, per-signer confidence, class mix, clip length distribution, and missingness proxies if available.
- **Risk:** if per-clip predictions are not currently persisted for every E3 branch, E4-A must first report that as a tooling gap rather than inventing signer metrics.

### Stage 5 - Data Quality And Support Audit

- **Input:** selected-class support, manifests, spans, lengths, feature masks, participant ids, and available quality metadata.
- **Output:** `data_quality_support.csv` and `data_quality_support.md`.
- **Purpose:** Separate model failure from weak data.
- **Measurements:** train/val/test clips per class, unique signers per class/split, clip length distribution, low-frame/missing-frame proxies, class imbalance, variant naming, and possible near-duplicates.
- **Gate:** any recommendation to collect more data must name the exact glosses, desired signers, repetition targets, and variation targets.

### Stage 6 - Reliable Vocabulary Proposal

- **Input:** Stages 2-5.
- **Output:** `reliable_vocabulary_v0.csv`, `hard_confusion_set_v0.csv`, and `vocabulary_recommendation.md`.
- **Purpose:** Decide whether AppHear should train next on the original 50 classes, a smaller reliable-first vocabulary, or a split benchmark with reliable classes and hard classes separated.
- **Recommended default:** propose a conservative reliable-first subset only if at least 15-25 classes meet keep criteria; otherwise recommend targeted data collection before training.
- **No hidden product decision:** any dropped/deferred sign must be documented with its reason and can be restored later.

### Stage 7 - Next Experiment Decision

- **Input:** all E4-A outputs.
- **Output:** `next_experiment_decision.md`.
- **Allowed next decisions:**
  - `E4-B cleaned reliable-vocabulary retrain`;
  - `E4-C targeted local signer data collection`;
  - `E4-D label/variant adjudication before training`;
  - `C0 hand-crop detector path before visual fusion`;
  - `no-go: current data cannot support a reliable recognizer yet`.
- **Forbidden next decision:** repeat E3-C upper-body frozen-MobileNet fusion.

## Proposed Output Directory

Future E4-A artifacts should be written under:

`artifacts/recognition_upgrade/e4_generalization/e4_a_landmark_data_audit_01`

Required files:

- `inventory.json`
- `class_reliability.csv`
- `class_reliability.md`
- `confusion_groups.csv`
- `confusion_groups.md`
- `signer_generalization.csv`
- `signer_generalization.md`
- `data_quality_support.csv`
- `data_quality_support.md`
- `reliable_vocabulary_v0.csv`
- `hard_confusion_set_v0.csv`
- `vocabulary_recommendation.md`
- `next_experiment_decision.md`
- `summary.json`
- `summary.md`
- `README_RUN.md`
- `check_report.json`

All generated files must stay under that run directory.

## Acceptance Gates For E4-A

E4-A passes only if:

- all source runs and hashes/paths are recorded;
- metrics are traced to exact files and branches;
- no claim uses train accuracy as release evidence;
- reliability tiers are based on held-out validation/test behavior and seed/branch stability;
- every class recommendation includes evidence and uncertainty;
- every proposed data-collection target names glosses and reason;
- every unknown is explicitly marked unknown;
- the report identifies one concrete next experiment with go/no-go criteria.

E4-A fails if:

- metrics cannot be aligned across runs;
- per-class/signer evidence is unavailable and not reported as a tooling gap;
- recommendations are generic, such as “collect more data” without targets;
- it silently tunes to test accuracy as the only selection rule;
- it proposes Android integration or production replacement.

## Recommended Next Experiment After E4-A

The likely next experiment, if E4-A produces enough reliable classes, is **E4-B cleaned reliable-vocabulary retrain**:

- use the best verified landmark candidate from E3-B6 as the reference model family;
- train only on a documented reliable-first class subset;
- compare against the original 50-class result;
- report top-1, macro-F1, worst-class F1, confusion groups, calibration, and signer metrics;
- require a meaningful jump in held-out signer performance before any Android work.

If E4-A finds that most failures are data/label/variant issues, E4-B should be deferred and E4-C/E4-D should happen first.

## Engineering Recommendation

The safest high-value path is:

1. Run E4-A audit from existing artifacts.
2. If at least 15-25 classes are reliable or near-reliable, prepare E4-B cleaned-vocabulary retrain.
3. If reliability is low or confusion is label-driven, prepare E4-C/E4-D targeted data and label adjudication.
4. Return to RGB only after detector-derived hand crops or hand-shape evidence are available and the landmark benchmark is clean.

## Architecture Decisions

- Landmark/data generalization is the next active path after E3-C no-go.
- RGB remains a future research path, but only with a changed visual evidence source.
- E4-A is an audit/decision package, not a training package.
- Production Android remains frozen.
- The E3-B5 50-class split remains useful as evidence, but E4-A may recommend a cleaned subset for the next training benchmark.

## Assumptions

- Existing E3 artifacts contain enough per-class and branch/seed evidence to start the audit.
- Some per-signer or per-clip prediction details may be missing; if so, E4-A must report the tooling gap.
- A smaller reliable vocabulary may be more valuable than a larger weak vocabulary for the first usable AppHear release.

## Hypotheses To Test

- Current accuracy is limited more by signer/data/label/generalization issues than by the specific TCN-vs-Conv1D choice.
- A cleaned reliable-vocabulary subset will improve held-out signer accuracy more than another small architecture tweak.
- Some persistent confusion groups require data or label decisions before model improvements are meaningful.

## Risks

- The audit could overfit conclusions to the reused E3-B5 frozen split.
- A reliable subset may be too small for the desired product vocabulary.
- Some important user-facing signs may be weak and require targeted collection rather than removal.
- Existing artifacts may lack per-clip predictions needed for signer-level analysis.

## Open Questions

- What minimum vocabulary size is acceptable for the next AppHear milestone?
- Which signs are product-critical even if current evidence says they are weak?
- Who will review label/variant ambiguity for confusing ASL signs?
- Can local data collection provide enough signer diversity, or is ASL Citizen-only still the honest benchmark?

## Next Required Action

See `E4_A_RESULT.md`. E4-A is complete. Next required action is to architect E4-C targeted data and label review before E4-B retraining.

