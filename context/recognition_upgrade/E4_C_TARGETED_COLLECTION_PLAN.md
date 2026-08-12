# E4-C Targeted Collection And Label/Video Review Plan

- **Purpose:** Convert the completed E4-A audit into a concrete collection and review plan before any E4-B retraining.
- **Scope:** Planning and handoff only. This document does not authorize training, Android changes, production recognizer replacement, feature-schema promotion, dataset mutation, or relabeling without review.
- **Current status:** Planned on 2026-07-29 from E4-A outputs. Target CSV package prepared; no recording or label review has started.
- **Verified project references:** `E4_A_RESULT.md`, `artifacts/recognition_upgrade/e4_generalization/e4_a_landmark_data_audit_01/*`, and `artifacts/recognition_upgrade/e4_generalization/e4_c_targeted_collection_plan_01/*`.
- **Source-of-truth files:** This document, `E4_A_RESULT.md`, `DATASET_UPGRADE_PLAN.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, and parent `../recorder-pipeline.md`.
- **Related context files:** `README.md`, `EXPERIMENT_MATRIX.md`, `ARCHITECTURE_DECISIONS.md`, `OPEN_QUESTIONS.md`, `RISK_REGISTER.md`, and parent `../progress-tracker.md`.

## Why E4-C Comes Next

E4-A found that the current 50-class landmark benchmark is not ready for another blind retrain:

- only 4 classes passed the conservative `candidate_keep` tier;
- 15 classes are plausible but need more signer evidence or stability;
- 8 classes have dominant confusion patterns requiring label/video review;
- 23 classes are currently defer or visual-review candidates;
- current E3 artifacts do not persist stable per-clip predictions, so per-signer accuracy cannot yet be claimed.

Therefore the next high-value action is not a new model. It is a targeted data and label/video review package that creates an approved class list for E4-B.

## Prepared E4-C Target Package

Run directory:

`artifacts/recognition_upgrade/e4_generalization/e4_c_targeted_collection_plan_01`

Files:

- `anchor_keep_classes.csv`
- `borderline_collection_candidates.csv`
- `confusion_review_classes.csv`
- `defer_or_visual_review_classes.csv`
- `confusion_pair_review_queue.csv`
- `summary.json`
- `proposed_recording_targets_v0.csv`
- `confusion_review_decision_template.csv`
- `USER_REVIEW_GUIDE.md`
- `README.md`

Summary:

- Anchor keep classes: 4.
- Borderline collection candidates: 15.
- Confusion-review classes: 8.
- Defer or visual-review classes: 23.
- Confusion-pair review queue: 20.

## Class Groups

### Anchor Classes

These classes should be preserved as reference classes for future E4-B training and data sanity checks:

- `SWITZERLAND`
- `COUCH`
- `CURLYHAIR`
- `DOWNSIZE1`

They are not production-ready by themselves. They are anchors because E4-A found stronger held-out landmark evidence and no dominant confusion under the conservative gate.

### Borderline Collection Candidates

These classes are the first candidates for targeted collection and possible inclusion in a 15-25 class E4-B vocabulary after review:

- `PEEKABOO`
- `BEE1`
- `BOTH`
- `SHARK1`
- `SENTENCE2`
- `LETTUCE1`
- `SHAVE1`
- `TWINS1`
- `EVERYYEAR`
- `NOON1`
- `LAND`
- `CONFUSED1`
- `AUTISM1`
- `ARTICULATESIGN`
- `OSTRICH`

Priority should start from the top of `borderline_collection_candidates.csv`, but the final target list must also consider product value and label-review outcomes.

### Confusion-Review Classes

These require video/label review before deciding whether to collect, merge, split, defer, or add visual evidence:

- `BASEBALLCAP`
- `DEAF1`
- `TAKECARE`
- `BOXING`
- `EDIT1`
- `ELEVATOR1`
- `CROSS3`
- `ROCKINGCHAIR1`

Do not treat these as simple data-shortage cases until their paired confusions are reviewed.

## Review Queue

The highest-priority review pairs are:

1. `DEAF1 <-> TWINS1`
2. `EVERYYEAR <-> TAKECARE`
3. `CROSS3 <-> WHALE`
4. `ROCKINGCHAIR1 <-> TRACTOR`
5. `BASEBALLCAP <-> LETTUCE1`
6. `BOXING <-> TAKECARE`
7. `EDIT1 <-> INDEPENDENT`
8. `ELEVATOR1 <-> INDEPENDENT`
9. `LETTUCE1 <-> NOON1`
10. `CURLYHAIR <-> PEEKABOO`
11. `NIGHT1 <-> SHAVE1`
12. `DEMAND1 <-> SINK`

For each pair, E4-C review must classify the likely issue as one of:

- `label_variant_or_alias`
- `insufficient_signer_diversity`
- `landmark_geometry_limit`
- `motion_timing_or_boundary_issue`
- `needs_visual_handshape_evidence`
- `unclear_requires_fluent_review`

The cause must remain `unknown` unless a human/video review supports it.

## Recommended Collection Target

E4-C should not ask for all 50 classes. The recommended first collection package is:

- 4 anchor classes;
- 8-12 strongest borderline classes after product review;
- selected confusion-pair classes only after label/video review confirms they are recoverable;
- no `drop_or_defer` class unless the user explicitly marks it as product-critical.

Target scale for the next local collection round:

- **New signers:** at least 5 new signers for the selected target list as the minimum useful local round; 10+ preferred if available.
- **Repetitions:** 3-5 valid repetitions per selected sign per signer.
- **Conditions:** at least two distances, at least two backgrounds, front camera, varied clothing, normal indoor lighting, and at least one lower-quality realistic condition per signer.
- **Handedness:** record dominant hand if known; include left-handed signers if available.
- **Metadata:** signer ID, device, camera facing, environment, distance, lighting, handedness if known, gloss, variant notes, recording date, and consent/provenance.

These are engineering targets for the next local round, not universal dataset-size claims. Learning curves after E4-B decide whether they are enough.

## Folder And Naming Contract

Future E4-C raw recordings should be placed under a new isolated folder, not inside existing E3/E4-A artifacts:

`scratchpad/e4_c_targeted_collection/raw/<participant>/<device>/<environment>/<camera>/<gloss>/<video>`

Example:

`scratchpad/e4_c_targeted_collection/raw/P01/phoneA/indoor/front/PEEKABOO/clip_001.mp4`

Rules:

- Keep raw videos immutable once recorded.
- Do not overwrite old clips; add new filenames.
- Do not mix no-sign footage into gloss folders.
- Do not relabel ASL Citizen files.
- Preserve sidecar/metadata when collection tooling is prepared.

## Review Procedure

1. Review the `confusion_pair_review_queue.csv` pairs first.
2. For each pair, inspect multiple source videos if available, not a single still frame.
3. Record whether the pair is a label/variant issue, a real visual-similarity issue, a boundary/timing issue, or unknown.
4. Decide per pair: collect more, merge/split labels, defer, or require visual hand-shape evidence.
5. Only then finalize the E4-B target vocabulary.

## E4-B Entry Gate

E4-B retraining is allowed only after E4-C produces:

- approved class list;
- reviewed confusion-pair decisions;
- collection target list by gloss;
- metadata/recording checklist;
- explicit excluded/deferred class list with reasons;
- decision whether local data is train-only or whether a signer-held-out local validation split exists;
- updated evaluation requirements, including per-clip prediction persistence.

## Tooling Requirements Before E4-B

E4-B evaluation must persist per-clip predictions, including:

- clip row index;
- split;
- participant ID;
- true gloss;
- predicted gloss;
- confidence;
- branch;
- seed;
- checkpoint type;
- correctness.

This closes the E4-A tooling gap and enables honest per-signer accuracy.

## Non-Goals

E4-C must not:

- train a model;
- change Android;
- promote E3-B6 or any E4-A class list as production-ready;
- permanently drop classes without product/user review;
- claim that RGB is required for any class without video evidence;
- use generated/synthetic data as a signer-diversity substitute.

## Acceptance Gates

E4-C passes if:

- every target class is assigned a reason: anchor, borderline collection, confusion review, product-critical, or defer;
- every top confusion pair has a review status;
- collection instructions are concrete enough for a person to record clips without guessing;
- E4-B has an approved class list and evaluation contract;
- unknowns remain marked unknown.

E4-C fails if:

- it recommends collecting all 50 classes without prioritization;
- it ignores the top confusion groups;
- it starts training before review;
- it produces generic data advice without gloss-specific targets.

## Next Required Action

Review `USER_REVIEW_GUIDE.md`, `proposed_recording_targets_v0.csv`, and `confusion_review_decision_template.csv` with the user. If approved, prepare recording/review tooling for the selected targets. Do not start E4-B retraining yet.


## Approved Minimum Recording Package - 2026-07-29

User approved the first E4-C minimum recording round. The package was prepared under:

`scratchpad/e4_c_targeted_collection/`

Prepared files:

- `README_RECORDING.md`
- `package_summary.json`
- `metadata/approved_minimum_recording_targets_v1.csv`
- `metadata/recording_manifest_template.csv`
- starter raw folders under `raw/P01/phoneA/indoor/front/<gloss>/`

Approved 12-sign minimum target list:

- `SWITZERLAND`, `COUCH`, `CURLYHAIR`, `DOWNSIZE1`
- `PEEKABOO`, `BEE1`, `BOTH`, `SHARK1`, `SENTENCE2`, `LETTUCE1`, `SHAVE1`, `TWINS1`

Optional extended targets remain `EVERYYEAR`, `NOON1`, `LAND`, and `CONFUSED1`. Confusion-review-first classes remain blocked from blind recording until reviewed: `DEAF1`, `TAKECARE`, `CROSS3`, `ROCKINGCHAIR1`, `BASEBALLCAP`, `BOXING`, `EDIT1`, and `ELEVATOR1`.

Next required action: user records raw isolated-sign MP4 clips into the folder contract, then a validation/audit step checks folder naming, clip counts, metadata coverage, video readability, duration, and placement before E4-B retraining is considered.

## Local Supplementary Replacement Audit - 2026-07-30

The user asked whether the E4-C 12-sign experiment could be changed from the original ASL Citizen-derived target list to the local supplementary dataset at `E:\local`.

A metadata-only audit was completed and recorded in `E4_C_LOCAL_SUPPLEMENTARY_AUDIT_RESULT.md` with artifacts under:

`artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_audit_01`

Verified audit summary:

- 4,055 MP4 files found.
- 4,035 JSON sidecars parsed.
- 4 observed signer IDs.
- 2,984 mapped conversational clips.
- 530 blank or unmapped clips.
- zero overlap with the originally approved E4-C 12 signs.

Recommended replacement 12 for a revised practical-vocabulary E4-C path:

`HELLO`, `YES`, `NO`, `SORRY`, `GOOD`, `BYE`, `HAVE`, `GET`, `GO`, `KNOW`, `MAKE`, and `WELCOME2`.

Decision: this replacement is allowed only as a revised local-supplementary path after video/readability validation. It does not invalidate the original recording package, and it does not authorize extraction, training, Android changes, or production recognizer replacement.

Next required action: build/run validation for `recommended_replacement_12_v1.csv`: video readability, label consistency, duration/frame counts, signer-disjoint split feasibility, duplicate/source leakage, and quarantine handling.
## Local Supplementary Video Validation - 2026-07-30

Validation tooling was added under `pipeline/rgb/e4_c_local_validate.py` and run against the selected local supplementary 12-sign set.

Validation artifact folder:

`artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_validation_01`

Result:

- 1,099 candidate rows checked.
- 1,099 eligible rows.
- 1,099 readable rows.
- readable rate: 1.0000.
- 4 eligible signer IDs.
- two-way signer-disjoint split is possible for every class.
- three-way signer-disjoint train/validation/test split is blocked by `GET`, `GO`, `HAVE`, `KNOW`, `MAKE`, and `WELCOME2`, which each have only two eligible signers.

Decision: video readiness passes, but a rigorous three-way signer-disjoint experiment requires more signer coverage or a reduced class list. A bounded two-way held-out-signer local pilot may proceed as an engineering experiment if explicitly labeled as such.

Next required action: prepare a reviewed E4-B local-supplementary manifest/split package with explicit split policy and warning-row handling. Do not train yet.
## E4-B Local Supplementary Manifest Package - 2026-07-30

A manifest/split package was prepared from the validated local supplementary rows.

Tooling:

`pipeline/rgb/e4_b_local_manifest.py`

Artifact folder:

`artifacts/recognition_upgrade/e4_generalization/e4_b_local_supplementary_manifest_01`

Result:

- 1,099 total manifest rows.
- 584 train rows.
- 146 internal-validation rows.
- 360 held-out test rows.
- 9 quarantined low-quality rows.
- held-out test signer: `6F7328-S001`.
- no signer overlap between train-like rows and test rows.

Important limitation: this is a two-way held-out-signer local pilot. Six classes (`GET`, `GO`, `HAVE`, `KNOW`, `MAKE`, `WELCOME2`) have only one train-like signer, so the result cannot be treated as a production-grade three-way signer-disjoint benchmark.

Next required action: review/approve the manifest package before any extraction or training runner is prepared.
## E4-B Strict 7-Sign Signer-Disjoint Package - 2026-07-30

The user requested excluding the six insufficient 2-signer signs instead of accepting the weaker 12-sign two-way split.

Excluded for insufficient signer coverage:

`GET`, `GO`, `HAVE`, `KNOW`, `MAKE`, and `WELCOME2`.

Strict 7-sign package:

`HELLO`, `BYE`, `YES`, `SORRY`, `NO`, `THANKYOU`, and `GOOD`.

Artifact folders:

- validation: `artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_validation_strict_7_01`
- manifest: `artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_signer_disjoint_manifest_01`

Result:

- 849/849 strict candidate rows eligible and readable.
- three-way signer-disjoint split feasible for every class.
- manifest: 410 train, 220 validation, 210 test, and 9 quarantine rows.
- split signers are globally disjoint: train `93EB89-S001`, validation `3B96F6-S001`/`3B96F6-S002`, test `6F7328-S001`.

Decision: prefer this strict 7-sign package for the next E4-B benchmark. It is protocol-cleaner than the 12-sign local pilot, but still limited by only three signer sources per class.