# Product-Core Data Readiness Package

**Purpose:** Define the bounded data package required before AppHear resumes recognition modeling after E6-1.

**Scope:** Data audit, vocabulary selection, manifest contract, collection/repair planning, and acceptance gates only. This document does not authorize model training, feature-schema changes, TFLite export, Android integration, dataset mutation, or production recognizer replacement.

**Current status:** COMPLETE / MODELING BLOCKED UNTIL DATA-READINESS GATE PASSES.

**Last updated:** 2026-08-03.

## Source-Of-Truth Inputs

Verified project references:

- Baseline freeze: `context/recognition_upgrade/E6_0_BASELINE_FREEZE.md`
- Consolidated audit: `context/recognition_upgrade/E6_1_CONSOLIDATED_EVIDENCE_DATASET_AUDIT.md`
- Dataset policy: `context/recognition_upgrade/DATASET_UPGRADE_PLAN.md`
- E5 reduced-primary evidence: `context/recognition_upgrade/E5_D_REDUCED_PRIMARY_VALIDATION_RESULT.md`, `context/recognition_upgrade/E5_E_REDUCED_PRIMARY_DECISION_RESULT.md`, `context/recognition_upgrade/E5_G_CLEAN_7_PRIMARY_RESULT.md`, `context/recognition_upgrade/E5_H_CLEAN_7_ROUTED_SIM_RESULT.md`, `context/recognition_upgrade/E5_I_OPEN_SET_REJECT_HEAD_RESULT.md`
- No-sign evidence: `context/recognition_upgrade/E4_Y_REAL_NOSIGN_FEATURE_VALIDATION_RESULT.md`, `context/recognition_upgrade/E4_Z_SIGNING_GATE_RESULT.md`, `context/recognition_upgrade/E4_AG_HELLO_LIKE_NOSIGN_RESULT.md`
- Specialist evidence: `context/recognition_upgrade/E4_V_SORRY_GOOD_SPECIALIST_RESULT.md`, `context/recognition_upgrade/E4_W_MIXED_LANDMARK_SPECIALIST_SIMULATION_RESULT.md`
- Machine-readable audit tables: `context/recognition_upgrade/product_core_data_readiness/`

Verified dataset files inspected:

- `F:/ASL DATASET/ASL CITIZEN/ASL_Citizen/splits/{train,val,test}.csv`
- `F:/ASL DATASET/ASL CITIZEN/ASL_Citizen/videos/*.mp4`
- `E:/local/*/signs/*/*.mp4`
- E4/E5 pilot manifests and tensors under `artifacts/recognition_upgrade/`
- E6 aggregate audit tables under `context/recognition_upgrade/e6_audit_tables/`

## Verified Current Finding

The existing data is repairable, but it is not ready for more modeling.

Verified project evidence:

- Current E5 tensors are valid schema v3.0 `[96,258]` arrays, but broad E5 manifests trace most rows only to source `.npz` tensors, not to raw videos.
- The E4-V local GOOD/SORRY specialist manifest does include true raw `video_path` lineage, proving that the project can preserve raw lineage when the package requires it.
- For the bounded vocabulary below, raw videos exist and basic file checks passed: `605` selected/reserve raw clips, `0` missing files, `0` zero-byte files, `0` decode failures, and `0` exact duplicate files.
- Official ASL Citizen rows provide many signer IDs but only about `29-32` clips per selected sign in the local installed ASL Citizen subset.
- Local raw videos provide app-domain examples but are concentrated in only `1-2` local signers per sign.

Engineering inference:

- Rebuilding from raw with strict lineage is worthwhile.
- Training again on the current E5 `.npz` inventories without repaired lineage would repeat the E5 loop and should remain blocked.

## Recommended Bounded Vocabulary

The recommended product-core data-readiness vocabulary is:

`GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`, `THINK`, `TAKE`, `SELL`

`WASH2` is kept as a strong control/reserve sign, not part of the first product-core vocabulary. It should be used to verify that the rebuilt manifest/extraction/evaluation pipeline can reproduce a known strong class without inflating product scope.

Rationale by evidence:

| Sign | Decision | Evidence |
|---|---|---|
| `GOOD` | Keep, repair lineage, guard confusion | Product-value sign; current combined features `95`; E4-V/E4-W showed GOOD/SORRY can be separated by focused landmark evidence, but GOOD-like false commits/confusions remain a risk. |
| `HELLO` | Keep, recollect/repair | Product-value sign; E4-S closed-set was strong, but E5-B regressed HELLO to SEEM and E4-AD/E4-AG showed HELLO-like no-sign false commits. Needs stronger no-sign and fresh signer testing. |
| `SORRY` | Keep as product-core repair target, not primary-ready | Product-value sign; E4-V landmark specialist passed, but E4-P/E4-Q broader contexts failed. Must not be trained as a normal primary sign until data/route evidence is rebuilt. |
| `HAVE` | Keep, repair lineage | Useful conversation sign; E4-S closed-set was strong, E5-D guarded/medium. Confusion with DRIVE/WANT2 is documented, so source-aware split and fresh test are required. |
| `KNOW` | Keep, recollect/repair | Product-value sign; E4-S closed-set was strong, but E5-B regressed KNOW to SEEM. Needs data repair and fresh held-out validation. |
| `THINK` | Keep | E5-D/E5-G strong sign; current local app-domain support is weak, so collect local signers. |
| `TAKE` | Keep | E5-D/E5-G strong sign; current local app-domain support is weak, so collect local signers. |
| `SELL` | Keep | E5-D/E5-G reasonably strong sign; current local app-domain support is weak, so collect local signers. |
| `WASH2` | Reserve/control | Strongest E5 class, but lower first-product priority than the selected core. Use as a pipeline sanity/control sign. |

Deferred despite product value:

- `YES`, `NO`, `THANKYOU`, `BYE`: previous E4 review showed label/variant or separability failures. They should be recollected later as their own cleanup package, not mixed into the first product-core rebuild.
- `MAKE`, `GET`, `WELCOME2`: previous expansion collapsed into GOOD-like predictions. Do not include in this package.
- `USE`, `WORK`, `DRIVE`, `WANT2`, `SLEEP`, `RUN2`, `MORNING`, `MEET`, `STAND2`: useful but currently confusion-prone or weaker under E5. Do not include until the first bounded package passes.

## Verified Counts

Machine-readable tables:

- `context/recognition_upgrade/product_core_data_readiness/verified_product_core_counts.csv`
- `context/recognition_upgrade/product_core_data_readiness/current_run_manifest_counts.csv`
- `context/recognition_upgrade/product_core_data_readiness/raw_video_lineage_audit.csv`
- `context/recognition_upgrade/product_core_data_readiness/raw_video_lineage_audit_summary.json`
- `context/recognition_upgrade/product_core_data_readiness/collection_requirements.csv`

Summary:

| Sign | Current Combined Feature Rows | ASL Raw Clips Found | Local Raw Clips Found | Local Raw Signers | Status |
|---|---:|---:|---:|---:|---|
| `GOOD` | 95 | 31 | 50 | 2 | Repairable, but needs lineage and fresh test. |
| `HELLO` | 37 | 32 | 50 | 2 | Underpowered; needs rebuild plus local signer expansion. |
| `SORRY` | 42 | 30 | 50 | 2 | Underpowered and confusion-sensitive; needs rebuild plus local signer expansion. |
| `HAVE` | 43 | 30 | 50 | 2 | Underpowered; needs rebuild plus local signer expansion. |
| `KNOW` | 38 | 31 | 50 | 2 | Underpowered and regression-prone; needs rebuild plus local signer expansion. |
| `THINK` | 31 | 31 | 20 | 1 | Underpowered locally; needs app-domain signer expansion. |
| `TAKE` | 32 | 30 | 20 | 1 | Underpowered locally; needs app-domain signer expansion. |
| `SELL` | 36 | 29 | 20 | 1 | Underpowered locally; needs app-domain signer expansion. |
| `WASH2` | 43 | 31 | 20 | 1 | Reserve/control only; underpowered locally. |

Current E5/E4 broad-run lineage status:

- E5-B/E5-D/E5-G manifests have `source_path` pointing to `.npz` tensors and `source_index`, but no raw video path.
- E4-S also lacks raw video paths for active rows.
- E4-V GOOD/SORRY specialist rows have local raw `video_path`.
- Therefore no new model may use E5-derived rows as source-of-truth training rows unless a lineage join or rebuild creates per-row raw paths and hashes.

## Data Gaps

Minimum gate to resume modeling for this bounded vocabulary:

- `150` reviewed, lineage-linked clips per selected sign.
- At least `75` app-domain/local clips per selected sign.
- At least `10` total signers per sign.
- At least `5` app-domain/local signers per sign.
- Signer-disjoint split with at least `6` train signers, `2` validation signers, and `2` fresh test signers per sign where feasible.
- Every row has raw video path, raw SHA256, source, signer, device/environment/camera if known, canonical label, label variant, extraction version, and split.

Current additional workload from `collection_requirements.csv`:

- Total additional clips needed to reach `150` clips/sign across the selected 8 signs: `646`.
- Total additional local/app-domain clips needed to reach `75` local clips/sign: `290`.
- Total additional local signer slots needed to reach `5` local signers/sign: `27`.

This is the minimum to resume credible modeling, not a production-release dataset. Production silent translation will still require larger signer diversity and continuous/non-isolated data later.

## No-Sign And OOV Plan

Before modeling resumes, collect/rebuild a no-sign/OOV package with the same manifest standard.

Required classes of negatives:

- `N0_NO_HAND`: no visible hands, person absent or hands outside frame.
- `P1_IDLE_HANDS`: hands visible but not signing.
- `P1_FACE_ADJACENT`: hands near face, head, hair, mask, phone, glasses, scratching, waving-like but not signing.
- `P1_ACCIDENTAL_MOTION`: reaching, adjusting camera, drinking, typing, holding objects, resting hands.
- `TRANSITION`: preparation, rest-to-sign, sign-to-rest, and between-sign movement for selected signs.
- `OOV_SIGN`: real signs not in the product-core vocabulary, especially GOOD-like, HELLO-like, SORRY-like, KNOW/SEEM-like, and HAVE/DRIVE/WANT-like signs.

Minimum gate:

- At least `1,000` reviewed no-sign/OOV windows total.
- At least `250` hands-visible idle/accidental-motion windows.
- At least `200` face-adjacent/HELLO-like windows.
- At least `300` unsupported-sign/OOV windows.
- At least `250` transition/partial-sign windows from selected signs.
- Signer-disjoint validation and fresh test negatives; no negative source may appear only in train.

Verified evidence behind this requirement:

- E4-Y proved zero-landmark no-sign is misleading.
- E4-Z/E4-AA showed simple gates can suppress false commits but can damage low-motion signs.
- E4-AG showed targeted HELLO-like negatives helped, but the no-sign set remains small and targeted.

## Split Rules

Required split rules before modeling resumes:

1. Assign `signer_id` to train/validation/test before feature extraction.
2. Keep all clips from the same signer/session/device burst in only one split.
3. Do not use local data as train-only unless the evaluation explicitly tests source transfer.
4. Do not mix ASL Citizen and local examples without preserving `source`.
5. Create a fresh test split that was not used in E3-E5 decisions.
6. Label variants must be explicit. If a sign has multiple lexical variants, either split the variant label or mark it excluded until review.
7. All rows must pass raw video existence, decode, hash, label, and boundary/quality checks before extraction.

## Collection And Cleaning Checklist

Before modeling:

- Rebuild selected ASL Citizen rows from `splits/*.csv` and `videos/*.mp4` into a strict manifest.
- Rebuild selected local rows from `E:/local/*/signs/*/*.mp4` into the same strict manifest.
- Add missing local/app-domain clips and signer diversity according to `collection_requirements.csv`.
- Review labels and variants for `HELLO`, `SORRY`, `GOOD`, `HAVE`, and `KNOW` first.
- Record or preserve device, environment, camera-facing, distance, and handedness when possible.
- Hash every raw video and reject exact duplicates before split assignment.
- Verify every selected raw video decodes and has at least one readable frame.
- Keep reviewed row-level status instead of silently deleting rows.
- Build no-sign/OOV/transition package with the same manifest rules.

## Acceptance Gate Before Modeling Resumes

Modeling may resume only when all gates pass:

| Gate | Required Result |
|---|---|
| Lineage | `100%` of selected positive, no-sign, OOV, and transition rows have raw path, raw SHA256, source, signer, label, variant, extraction version, and split. |
| Decodability | `0` missing videos, `0` zero-byte videos, `0` decode failures in selected manifest. |
| Duplicates | `0` exact duplicate raw videos across train/val/test; near-duplicate/session burst grouped by split. |
| Vocabulary | Selected vocabulary is fixed to the 8 product-core signs unless explicitly revised in context. |
| Counts | Each selected sign has at least `150` reviewed lineage-linked clips and at least `75` app-domain/local clips. |
| Signers | Each selected sign has at least `10` total signers and at least `5` app-domain/local signers. |
| Splits | Signer-disjoint train/val/fresh-test splits exist and are source-balanced or source-heldout by design. |
| Labels | All selected signs have explicit `canonical_gloss` and `label_variant`; unresolved variants are excluded or marked `needs_adjudication`. |
| No-sign/OOV | At least `1,000` reviewed no-sign/OOV/transition windows with required subtype coverage. |
| Test freshness | The fresh test split is not reused from E3-E5 promotion decisions. |

## Decision

**Data can be repaired, but new collection is required.**

Do not resume modeling from the existing E5 tensors alone. The fastest credible path is:

1. Build the strict manifest/lineage package for the 8 selected signs plus `WASH2` control.
2. Rebuild features from raw videos using the frozen schema v3.0 path only after the manifest gate passes.
3. Collect only the missing app-domain clips/signers and no-sign/OOV/transition coverage.
4. Start exactly one next modeling experiment only after the data-readiness gate passes.

## Architecture Decisions

- The v3.0 production recognizer remains frozen.
- E6-2+ modeling remains blocked.
- Product-core data readiness is now the next approved work item.
- `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`, `THINK`, `TAKE`, and `SELL` are the bounded selected vocabulary.
- `WASH2` is a reserve/control sign, not product-core v0.
- Raw video plus manifest is canonical; `.npz` tensors are derived artifacts.

## Assumptions

- Existing ASL Citizen and local videos are legally usable for this project; rights/consent still require review.
- Local file names reliably encode signer IDs enough for preliminary audit; final manifest should not rely only on filename parsing.
- The `150` clips/sign and `5` local signers/sign targets are minimum modeling-resumption gates, not final production scale.

## Open Questions

- Who will adjudicate ASL lexical variants for `HELLO`, `SORRY`, `GOOD`, `HAVE`, and `KNOW`?
- Can ASL Citizen rows be joined exactly to prior extracted features, or should selected signs be fully re-extracted from raw to avoid lineage ambiguity?
- Which devices and environments should define the first app-domain fresh test split?
- Should `WASH2` remain only a control, or be promoted if one selected sign fails the data-readiness gate?

## Risks

- Source confounding if ASL Citizen and local rows are mixed without source-aware validation.
- Local signer concentration can still produce high local accuracy and poor real-user generalization.
- Product-value signs are harder than some high-accuracy signs; replacing them with easy signs may create misleading progress.
- Label variants may be the real cause of some apparent model failures.
- No-sign/OOV negatives may still be too narrow if collected only by the project team.

## Next Required Action

Prepare, but do not yet run, a strict manifest-builder implementation plan for the selected 8 signs plus `WASH2` control. The implementation must create a canonical CSV/JSONL manifest and validation report first; only after the manifest gate passes should any extraction or training be considered.
