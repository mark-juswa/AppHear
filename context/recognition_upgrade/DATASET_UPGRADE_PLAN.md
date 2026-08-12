# Dataset Upgrade Plan

**Purpose:** Define data required for reliable signer-independent hybrid recognition.
**Status:** PROPOSED. **Last updated:** 2026-07-25.

## Verified Current State

- ASL Citizen official split: 40,154/35 train, 10,304/6 val, 32,941/11 test clips/signers.
- It is isolated citation-form video and supplies broad signer diversity, but selected classes can
  have only 12-23 training clips.
- Local/classmate audit: 4,035 sidecars, 4,055 videos, 3,654 usable mapped clips, one to three
  signers per class. It is TRAIN-only and cannot validate generalization.
- Recorder is video-primary; raw MP4 plus sidecar is re-extracted offline. This is the correct
  foundation for RGB crops and new landmarks.

## Required Pilot

Select 50 signs using frequency, user value, confusion coverage, and visually distinct/near-neighbor
pairs. Collect:

- at least 30 signers for the pilot; 50 minimum and 75-100 preferred before a 100-236 sign release;
- 2-5 valid repetitions per signer/sign/condition, targeting 100-300 valid clips per sign;
- balanced handedness, age, body size, skin tone, signing proficiency/style/speed;
- multiple phones, front/back cameras, distance, yaw/pitch, clothing, background, and lighting;
- idle/no-sign sessions, transitional motions, partial/aborted signs, occlusions, one-hand/two-hand
  failures, and out-of-vocabulary signs.

These are engineering targets, not literature-derived minima. Learning curves decide whether they
are enough.

## Canonical Record

Preserve immutable raw video and a versioned sidecar containing:

`clip_id, signer_id, consent/provenance, source, language, gloss, lexical_variant, dominant_hand,
camera/device, width, height, nominal_fps, frame timestamps, orientation, environment tags,
onset/release with annotator and uncertainty, quality flags, extraction version, split`.

Derived landmarks, masks, crops, optical/motion features, and tensors are rebuildable artifacts.
Never preserve only 258 vectors. Hash raw files and deduplicate near-identical clips/signer identity
before split assignment.

## Annotation

- Isolated clips: annotate preparation/idle, onset, active sign, release, and post-sign idle.
- Use two-pass review for lexical label and boundaries; adjudicate disagreements.
- Record variant aliases instead of forcing distinct signs under one English word.
- Continuous phase: collect natural sentence-level ASL from fluent signers with gloss sequence,
  sentence translation, approximate boundaries/alignment, and non-manual notes. Do not synthesize
  continuous data by concatenating isolated clips.

## Split And Leakage Rules

Assign signer to train/val/test before preprocessing. Keep household/session/device near-duplicates
together. Report per-signer metrics. Public datasets may pretrain the RGB/landmark encoders only
after license, language, label, signer, and preprocessing provenance review; fine-tune and evaluate
on AppHear target-domain signer-held-out data.

## Augmentation

Use geometric/color/blur/compression/crop jitter, temporal subsampling/jitter, dropped landmarks,
modality dropout, handedness-consistent mirroring, and prefix truncation. Never use augmentation to
claim additional signer diversity. Synthetic avatars can test geometry invariance or pretrain, but
not replace real hands, occlusion, skin, motion, or linguistic variation.

## Acceptance And Learning Curves

At 10, 20, and 30 pilot signers, plot held-out top-1/macro-F1/worst-decile F1 against signer count.
Proceed to collection scale-up only if performance improves and signer variance narrows. No-go if
performance plateaus below 0.80 top-1 by 30 signers or any class lacks at least 10 independent
training signers; resolve labels/vocabulary/model before collecting blindly.

## References, Decisions, Assumptions, Risks, Unknowns, Next Action

- **Sources:** `artifacts/splits.json`, `recorder-pipeline.md`, local audit report, raw video roots.
- **Decision:** raw video + timestamped metadata are canonical; derived tensors are disposable.
- **Assumption:** consent/license permits RGB training; must be audited.
- **Risks:** label inconsistency, signer concentration, privacy, public-domain mismatch.
- **Open questions:** signer demographics/rights in existing local batches; exact 50-sign pilot list.
- **Next action:** run E4-N full training and final check for `GOOD`/`HELLO`/`SORRY` plus `HAVE`/`KNOW`. Do not extract `GET`/`WELCOME2`, retry RGB fusion, or integrate Android until this source-aware screen shows whether expansion can preserve the reliable core.


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-018 apply; component-specific decisions in this document apply only after their experiment gate passes.
- **Assumptions:** Any forecast or unmeasured dimension remains a hypothesis, not a project fact.
- **Open questions:** Unresolved items are tracked in this document and `OPEN_QUESTIONS.md`.
- **Risks:** Applicable failure modes and fallbacks are tracked in this document and `RISK_REGISTER.md`.
- **Next required action:** Follow the explicit next action above and the ordering in `EXPERIMENT_MATRIX.md`; do not skip gates.


## E4-L Dataset Lesson And Dual-Source Screening Requirement - 2026-07-30

E4-L completed a technically valid one-sign expansion from `GOOD`/`HELLO`/`SORRY` to `GOOD`/`HELLO`/`SORRY`/`MAKE`, but failed the held-out test gate. `MAKE` reached perfect train/validation accuracy and then collapsed on the held-out signer, mostly into `GOOD`. This is now treated as evidence that manual one-word expansion is too slow and too sensitive to signer/provenance mismatch.

The next dataset step is not another blind retrain and not a blind ASL Citizen/local merge. It is an automated dual-source candidate screen using both `F:\ASL DATASET\ASL CITIZEN` and the local supplementary dataset. The screen must preserve source labels, signer IDs, clip provenance, quality metrics, and variant warnings, then report within-source reliability, cross-source transfer, held-out-signer accuracy, and confusion impact on the reliable core.

A sign may be considered a candidate for expansion only after the screen shows enough source/signer support and does not damage the current reliable core. A sign that works only within one source should be labeled diagnostic, not production-ready.

## E4-M Dual-Source Candidate Screen Result - 2026-07-30

E4-M completed the first automated inventory across ASL Citizen conversational features and the local supplementary feature/raw/validated inventories. It ranked all 236 labels without training, extraction, model export, or Android changes.

The only immediate existing-feature candidates were `HAVE` and `KNOW`. `GET` and `WELCOME2` have enough validated local raw/video support but need local feature extraction before they can join a training screen. `BYE`, `NO`, `THANKYOU`, and `YES` remain prior-unstable because earlier local experiments showed label/variant or generalization failures. `MAKE` remains rejected by the E4-L gate.

The next dataset action is therefore bounded: train and evaluate only `GOOD`/`HELLO`/`SORRY` plus `HAVE`/`KNOW` before approving any broader extraction or vocabulary expansion.

## E6 Product-Core Data Readiness Decision - 2026-08-03

E6-1 supersedes the E4/E5 modeling loop. Data is insufficient for additional modeling until a bounded product-core package passes strict lineage, count, signer, split, label, and no-sign/OOV gates.

The active data-readiness vocabulary is `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`, `THINK`, `TAKE`, and `SELL`. `WASH2` is retained as a strong control/reserve sign, not as a first product-core sign.

Verified package outputs:

- `context/recognition_upgrade/PRODUCT_CORE_DATA_READINESS_PACKAGE.md`
- `context/recognition_upgrade/DATASET_MANIFEST_LINEAGE_SCHEMA.md`
- `context/recognition_upgrade/product_core_data_readiness/verified_product_core_counts.csv`
- `context/recognition_upgrade/product_core_data_readiness/current_run_manifest_counts.csv`
- `context/recognition_upgrade/product_core_data_readiness/raw_video_lineage_audit.csv`
- `context/recognition_upgrade/product_core_data_readiness/raw_video_lineage_audit_summary.json`
- `context/recognition_upgrade/product_core_data_readiness/collection_requirements.csv`

Verified raw-video audit for the bounded selected/reserve set found `605` raw clips, `0` missing files, `0` zero-byte files, `0` decode failures, and `0` exact duplicate files. However, E5 broad-run manifests still trace most rows only to source `.npz` tensors, not raw videos. Therefore raw videos are available, but current feature rows are not lineage-complete enough to support the next modeling claim.

Minimum gate before modeling resumes:

- `150` reviewed, lineage-linked clips per selected sign.
- `75` app-domain/local clips per selected sign.
- `10` total signers per sign.
- `5` app-domain/local signers per sign.
- `1,000` reviewed no-sign/OOV/transition windows with real MediaPipe-compatible source video lineage.
- `100%` row-level raw path/hash/source/signer/variant/split/extraction-version completeness.

Next action: create a manifest-builder plan only. Do not extract features, train models, change schemas, export TFLite, or integrate Android until the data-readiness gate passes.

## Phase 1 Full-Vocabulary Dataset Decision - 2026-08-11

The approved Phase 1 target is all 236 deployed glosses, with ASL Citizen as the primary
signer-disjoint source. Reconstruction of the existing v3.0 tensors found exact row counts of
`3309` train, `816` validation, and `2620` test with zero class, participant, or sequence-length
mismatches against raw Stage-E, span, quality, and official-split records. Final SHA256 verification
is still required.

The preparation manifest assigns those ASL rows to primary train/validation/protected test; `617`
reviewed E6 non-ASL rows to supplemental train; `163` E6 rows to validation stress; `300` E6 rows
to reused-positive diagnostics; and `306` clean replay rows to a separate protected replay set.

The older `933`-row local merge is excluded because its tensor rows lack authoritative raw-video
IDs, hashes, and variants. No protected or diagnostic row may be moved into training to raise
counts. Full raw-video hashing passed on 2026-08-11 with `8131/8131` manifest rows and no errors.
The next gate is full versioned tensor assembly and validation.

## Phase 2 Synchronized RGB Readiness - 2026-08-12

The 40-sign Phase 2 pilot has 2,519 present raw videos, but only 1,133 rows currently provide the
canonical raw-video + Stage-E + span synchronization required for landmark/RGB pairing. Immediate
eligible support is 550 ASL Citizen training, 138 validation, and 445 historical test clips. Each
sign has only 10-16 synchronized training clips. The remaining AppHear/local/replay rows must not be
joined to RGB by feature-row index; they require a new versioned timestamped extraction or remain
excluded. Pixel crop quality is still unknown.

The historical test helped select pilot classes and is diagnostic only for Phase 2. Model selection
must use signer-disjoint development folds, and scale-up requires fresh signer/domain evidence.
Before P2-P3, decide whether shared visual pretraining and frame sampling make 550 clips adequate
for a bounded research pilot, or whether synchronized AppHear/local extraction/new data is required.
