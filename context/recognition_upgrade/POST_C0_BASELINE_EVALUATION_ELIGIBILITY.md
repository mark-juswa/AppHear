# Post-C0 Protected-Baseline Evaluation Eligibility

**Purpose:** Determine which existing recordings may be used to evaluate the frozen 236-class
Android recognizer after the partial F22 smoke.

**Scope:** Raw-video lineage, hash verification, deployed-model identity, and prior-experiment
usage only. No feature extraction, inference, training, calibration, schema change, TFLite export,
or Android change was performed.

**Status:** Audit passed. A bounded three-sign isolated replay diagnostic is available. A fresh
held-out end-to-end phrase evaluation remains blocked.

**Last updated:** 2026-08-11.

## Verified Project References

- Audit utility: `pipeline/rgb/post_c0_baseline_eligibility.py`.
- Focused tests: `tests/test_post_c0_baseline_eligibility.py` (`3` passed).
- Run: `artifacts/recognition_upgrade/heldout_baseline_evaluation/eligibility_audit_01/`.
- Eligibility manifest: `eligibility_manifest.csv`.
- Machine-readable decision: `eligibility_summary.json`.
- Positive lineage source: `artifacts/recognition_upgrade/product_core_data_readiness/e6_collection_integration_01/manifest.csv`.
- Negative lineage source: `artifacts/recognition_upgrade/product_core_data_readiness/e6_negative_upload_review_01/accepted_fresh_negative_manifest.csv`.
- E6 positive usage source: `artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_baseline_01/positive_extraction_manifest.csv`.
- E6 negative usage source: `artifacts/recognition_upgrade/e6_rejection/e6_3_frozen_embedding_01/dataset/negative_window_manifest.csv`.

## Protected Model Identity

The audited model is the current Android asset:

`android/app/src/main/assets/streaming.tflite`

Its SHA-256 is
`42575710A4ADB0A1433B58BA9093BC4E9F49401381582CC4AD304FEEB669D4BB`, exactly matching
`E6_0_BASELINE_FREEZE.md`. The August AppHear captures postdate the July 22 model artifact, so the
exact deployed model could not have trained on those video files. This establishes model-held-out
status. It does not by itself establish project-fresh status or real-person identity separation.

## Actual File Verification

- Candidate rows checked: `1,626`.
- Positive videos: `1,066`.
- Negative-context videos: `560`.
- Existing paths: `1,626/1,626`.
- SHA-256 matches: `1,626/1,626`.
- Missing or changed files: `0`.
- Bytes read for independent verification: `6,277,948,218`.
- Later experiment CSVs scanned for the clean positive hashes: `105`.

The audit used raw videos and hashes, not NPZ row indexes.

## Eligibility Classes

| Eligibility | Rows | Allowed interpretation |
|---|---:|---|
| Clean isolated replay candidate | `306` | Primary input for the next protected-model diagnostic |
| Reused E6 positive diagnostic only | `760` | Historical sensitivity analysis only; not fresh evidence |
| Reused E6-3 negative diagnostic only | `560` | Historical false-commit diagnostic only; not fresh evidence |

### Clean Positive Set

| Sign | Clips | Recorded signer IDs | Prior model-experiment hash use |
|---|---:|---|---|
| `SELL` | `150` | `6CC240-S001`, `87AF81-S001`, `8A128E-S001` | None found |
| `TAKE` | `80` | `6CC240-S001`, `8A128E-S001` | None found |
| `THINK` | `76` | `87AF81-S001`, `8A128E-S001` | None found |
| **Total** | **306** | **3 recorded IDs** | **0/306 hashes found in scanned E6/C0 experiment CSVs** |

These clips were batch-reviewed during data readiness, but no model prediction result was found for
their hashes. `SELL` has three recorded signer IDs; `TAKE` and `THINK` each have two. Folder/sidecar
IDs are internally consistent, but the project cannot prove that these IDs are three distinct human
identities or that none overlaps a differently named historical local signer.

### Reused Positive Set

The `760` AppHear captures for `GOOD`, `HELLO`, `SORRY`, `HAVE`, and `KNOW` were all consumed by the
E6 five-sign baseline. They remain held out from the frozen Android model itself because they were
recorded after that model was produced, but they are no longer untouched project evidence. They may
be reported only as a repeated-test diagnostic with that limitation stated.

### Negative Set

All `560` uploaded negative clips were consumed by E6-3:

| Subtype | Rows | Clean unused rows |
|---|---:|---:|
| Idle hands | `60` | `0` |
| Face-adjacent non-signing | `60` | `0` |
| Accidental motion | `60` | `0` |
| OOV signs | `320` | `0` |
| Transition/partial signs | `60` | `0` |

The clips come from one recorded signer ID, `0F747C-S001`. Historical N0/P1 data is also reused and
cannot repair the lack of project-fresh negative evidence.

## What Existing Data Cannot Measure

- Natural multi-sign phrase accuracy or gloss error rate.
- Coarticulation and real sign-boundary behavior.
- Project-fresh no-sign/OOV false-commit rate.
- Robust cross-signer generalization to verified distinct people.
- Multi-device or environment generalization.

The available positive files are isolated citation-form clips. Concatenating them would be a
synthetic sequence and must not be reported as natural phrase recognition.

## Decision

Existing data is sufficient for exactly one next step:

> Run the frozen 236-class model on the 306 clean `SELL`/`TAKE`/`THINK` clips as an isolated replay
> diagnostic, reporting per-sign and per-recorded-signer results.

This run must use the exact deployed model, vocabulary, schema v3.0 feature path, and confirmation
configuration. It must not train or calibrate anything. Reused positives and negatives may be
included only in separately labelled historical sensitivity tables.

Existing data is not sufficient for the previously proposed fresh held-out end-to-end phrase
evaluation. That claim remains blocked until natural phrase sessions and independent negative
sessions from verified held-out signers exist.

## Next Required Action

Prepare a parity-controlled isolated replay harness for the 306 clean clips. First run only a small
smoke that verifies raw-video loading, schema `3.0`, `[1,96,258]` TFLite input, vocabulary order,
deployed thresholds, and organized output writing. If the smoke passes, the developer may run the
full 306-video extraction/replay because MediaPipe extraction is the long step.

The primary outputs must include top-1/top-5, per-sign and per-signer recall, commit coverage,
precision when committed, wrong-commit rate, drop rate, hand/pose hit rates, and extraction/inference
latency. These are isolated diagnostic metrics, not phrase accuracy.

## Risks And Unknowns

- The deployed local-supplementary model lacks a raw-row training manifest, so training exclusion
  is established by capture/model chronology rather than direct training-hash subtraction.
- Recorded signer IDs may not equal verified human identities.
- Data review exposed the signing/background domain before evaluation, although predictions for the
  306 clean hashes were not found.
- A clip replay cannot reproduce live-camera S5 onset, release timing, or coarticulation without a
  separate parity-tested streaming replay implementation.

## Related Context

- `POST_C0_PRODUCT_SCOPE_DECISION.md`
- `F22_DEVICE_SMOKE_RESULT.md`
- `E6_0_BASELINE_FREEZE.md`
- `E6_1_CONSOLIDATED_EVIDENCE_DATASET_AUDIT.md`
- `DATASET_MANIFEST_LINEAGE_SCHEMA.md`
- `EVALUATION_AND_ACCEPTANCE_GATES.md`
- `../eval-protocol.md`
- `../feature-schema.md`

