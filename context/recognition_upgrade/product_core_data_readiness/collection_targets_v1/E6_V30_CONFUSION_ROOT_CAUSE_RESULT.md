# E6 v3.0 Five-Sign Confusion Root-Cause Result

Last updated: 2026-08-09

## Purpose

Explain the failed E6 five-sign baseline before authorizing another model run. The bounded audit
targets only `KNOW -> HELLO` and `HAVE -> GOOD` and uses the already extracted v3.0 tensors,
completed checkpoints, deployed control model, and traceable raw videos.

## Scope And Status

Status: **complete**. This was a read-only analysis run. It did not extract features, train a
model, export TFLite, or modify Android.

Run directory:

`artifacts/recognition_upgrade/e6_baseline/e6_v30_confusion_root_cause_01`

## Evidence Classification

### Verified Project Evidence

- The five-sign model was trained from scratch with the same 4-block, 64-channel causal TCN
  family and v3.0 `[96,258]` contract.
- The new model's mean fresh top-1 is `0.7344`; fresh `KNOW` recall is `0.0222` and fresh `HAVE`
  recall is `0.6667`.
- All three seeds agree on the main failure. On fresh clips, 56/60 `KNOW` examples receive a
  unanimous `HELLO` prediction; 18/60 `HAVE` examples receive a unanimous `GOOD` prediction.
- The deployed 236-class model, restricted to the same five labels and evaluated on the exact
  same tensors, reaches `0.9467` fresh top-1, `0.80` `KNOW` recall, and `1.0` `HAVE` recall.
- A simple standardized landmark-geometry descriptor places `60/60` fresh `KNOW` clips nearest
  the training `HELLO` centroid and 41/60 fresh `HAVE` clips nearest the training `GOOD`
  centroid. This descriptor is diagnostic only, not a classifier proposal.
- Historical ASL Citizen performance is much stronger than fresh AppHear performance. The three
  seeds make no unanimous `KNOW -> HELLO` or `HAVE -> GOOD` errors on historical test clips.
- The raw-video review sheets show semantically distinct `KNOW` and `HELLO` performances. The
  fresh `KNOW` examples visibly place the index hand at the temple, while `HELLO` uses the open
  greeting hand. The deployed control also separates almost all of those fresh examples.
- Split support is not production-grade:
  - fresh test has 300 clips but only one signer;
  - validation `HAVE` has only four clips, all from ASL Citizen;
  - validation `KNOW` has 31 clips but 30 come from one AppHear signer;
  - the largest training signer supplies about 48-50% of `GOOD`, `HAVE`, and `KNOW`.

### Engineering Inference

- MediaPipe failure is not the primary explanation for these two confusions. The same extracted
  tensors are substantially more separable to the broader deployed model.
- The strongest current explanation is representation/source shortcut learning: 685 clips are
  insufficient for a five-class TCN trained from scratch to learn the signer variation already
  represented by the broader 236-class model.
- The validation composition also makes early stopping and checkpoint comparison weak for
  `HAVE`, and overly dependent on one AppHear signer for `KNOW`.

### Hypotheses Requiring Experimentation

- Initializing the five-class causal encoder from the broader 236-class checkpoint may preserve
  general hand/pose representations and prevent the fresh `KNOW` collapse.
- Source-balanced or signer-balanced sampling may help, but it must not be combined with the
  first transfer test because doing both would hide which change caused any gain.

## Decision

The from-scratch five-sign checkpoint is **no-go**. Do not use it for the negative gate, vocabulary
expansion, TFLite export, or Android.

The single next model experiment, if approved, is a **warm-start-only five-sign transfer test**:

1. reuse the exact E6 tensors, labels, splits, TCN architecture, augmentation, optimizer, seeds,
   epochs, and gates;
2. initialize only matching causal-encoder layers from the current broader 236-class Keras
   checkpoint;
3. create a new output directory and train a new five-class head;
4. compare against both the from-scratch five-class run and the frozen deployed-control result;
5. do not export or integrate regardless of outcome.

This differs from the historical targeted 236-class v1-v4 runs. Those repeatedly adjusted class
weights while retaining a 236-class head and produced cross-class regressions. The proposed test
changes no weights and asks one narrower question: does broad encoder pretraining explain the
deployed model's advantage on the same new signer?

## Acceptance Gate For The Next Test

Proceed beyond the transfer diagnostic only if all three seeds meet the existing positive gates:

- mean fresh top-1 at least `0.80`;
- minimum-seed fresh top-1 at least `0.70`;
- mean recall for every class at least `0.70`;
- minimum-seed recall for every class at least `0.50`;
- no material regression from the from-scratch run on `GOOD`, `HELLO`, or `SORRY`;
- encoder layers are proven to have loaded, with copied-layer count and source checkpoint hash.

If `KNOW` or `HAVE` still fails, stop the five-class model path. The next decision becomes dataset
split/variant repair, not class weighting, threshold tuning, RGB, or Android work.

Even if the gate passes, the result remains a pilot because the fresh set has only one signer and
has now been inspected. A later production claim requires an untouched signer-disjoint test set.

## Risks

- The broader checkpoint may contain source-specific behavior or historical sample reuse.
- Repeated inspection of the one fresh signer turns that split into a development diagnostic.
- A warm-start gain would validate transfer, not prove a scalable 236-class production upgrade.
- Validation `HAVE` remains too small to support reliable checkpoint selection.

## Source-Of-Truth Files

- `pipeline/rgb/e6_v30_confusion_root_cause.py`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_confusion_root_cause_01/root_cause_summary.json`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_confusion_root_cause_01/sample_diagnostics.csv`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_confusion_root_cause_01/visual_review_queue.csv`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_confusion_root_cause_01/review_sheets/`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_baseline_01/metrics/metrics.json`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_baseline_01/metrics/deployed_236_control.json`

## Related Context

- `E6_V30_FIVE_SIGN_BASELINE_PACKAGE.md`
- `E6_FIVE_SIGN_ASSIGNMENT_RESULT.md`
- `../../../E6_1_CONSOLIDATED_EVIDENCE_DATASET_AUDIT.md`
- `../../../EVALUATION_AND_ACCEPTANCE_GATES.md`
- `../../../ROLLBACK_AND_COMPATIBILITY_PLAN.md`

## Assumptions And Open Questions

- The current broader Keras checkpoint must be hash-verified against the deployed TFLite lineage
  before it is used as a transfer source.
- It remains unknown whether transfer will help the validation signer whose `KNOW` execution is
  also confused by the deployed control.
- A replacement source-balanced validation split may be needed after the isolated transfer test.

## Next Required Action

The isolated warm-start package is prepared and smoke-validated in
`E6_V30_FIVE_SIGN_TRANSFER_PACKAGE.md`. Full three-seed training remains user-run; evaluate it
before authorizing any other recognition experiment.
