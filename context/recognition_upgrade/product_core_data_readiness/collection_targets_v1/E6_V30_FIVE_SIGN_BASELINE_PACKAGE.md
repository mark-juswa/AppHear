# E6 v3.0 Five-Sign Baseline Package

Last updated: 2026-08-09

## Purpose

Define the first trustworthy model experiment after E6 data repair: re-extract the approved raw
videos with one schema-v3.0 pipeline, train the deployed-family streaming TCN from scratch, and
measure signer-independent performance without mixing fresh and historical tests.

## Scope And Status

- **Status:** TRAINING COMPLETE / STRUCTURAL PASS / POSITIVE ACCURACY GATE FAIL.
- **Vocabulary:** `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`.
- **Input:** `[96,258]`, schema `3.0`.
- **Model:** four-block, 64-channel causal streaming TCN matching the deployed model family.
- **Not authorized:** Android export, production replacement, richer features, rejection heads,
  specialists, RGB, or vocabulary expansion.

## Verified Project References

- Runner: `pipeline/rgb/e6_v30_five_sign_baseline.py`
- Tests: `tests/test_e6_v30_five_sign_baseline.py`
- Frozen assignment: `artifacts/recognition_upgrade/product_core_data_readiness/e6_five_sign_assignment_01/`
- Run package: `artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_baseline_01/`
- Shared extractor: `pipeline/extract/landmarks.py`
- Shared v3.0 feature contract: `pipeline/features/contract.py::clip_features_realtimed`
- Shared deployed-family model: `model/model.py::build_streaming_classifier`
- Shared trainer: `model/train_streaming.py`
- Deployed control: `android/app/src/main/assets/streaming.tflite` and `vocab.json`

## Architecture Decisions

- Every positive row is re-extracted from its verified raw video. Old E4/E5 feature row indexes are
  not reused as data authority.
- The primary model is the causal streaming TCN because the experiment asks whether repaired data
  improves the current deployed pipeline. E4's clip-level Conv1D is not an equivalent deployment
  baseline and is omitted to avoid unnecessary branches.
- Training starts from random initialization. Warm-starting the old 236-class checkpoint could
  carry prior E3-E5 data reuse into this test.
- Seeds are `101`, `202`, and `303`. Training is resumable and uses separate output directories.
- The latest checkpoint is primary. Best/final checkpoints remain diagnostic because E4-K showed
  that tiny validation sets can select misleading checkpoints.
- Fresh positive test and historical ASL Citizen diagnostic test remain separate.
- The deployed 236-class TFLite control reports both full-vocabulary and restricted-five-class
  results. Restricted-five accuracy must never be presented as 236-class production accuracy.
- Historical and fresh negatives remain frozen for a separate signing/rejection gate evaluation.
  They are not silently added as a sixth softmax class.

## Prepared Data Contract

| Split | Rows | Purpose |
|---|---:|---|
| Train | 685 | Model fitting |
| Validation | 179 | Training diagnostics/checkpoints |
| Fresh test | 300 | Primary signer-independent pilot result |
| Historical test | 63 | Reused source diagnostic only |

`HAVE` has only four validation rows. Its 60 fresh-test rows are more informative, but the fresh
test remains promotion-only and must not be used to tune the model.

## Smoke Result

The 10-row actual-data smoke passed:

- extracted one train and one validation clip for each class;
- produced finite `[10,96,258]` input;
- produced `[10,96,5]` TCN output;
- completed one weighted training step;
- saved and reloaded a Keras checkpoint;
- observed pose on all sampled frames and hand-hit rates of approximately `0.40-0.59`.

The smoke proves executable contracts, not recognition accuracy. Full extraction must retain and
review hand/pose hit rates.

## Full Extraction Result

The developer completed the full extraction in `5,792.28` seconds:

- attempted `1,227`;
- extracted/cached `1,227`;
- failed `0`;
- missing `0`;
- assembled train `685`, validation `179`, fresh test `300`, historical test `63`.

All arrays are finite, all have shape `[N,96,258]`, masks match stored lengths, every split contains
all five labels, no clip tensor is entirely zero, and no signer crosses splits.

Quality findings:

- pose coverage is effectively complete;
- mean hand-hit rate is train `0.7123`, validation `0.5316`, fresh test `0.9919`, and historical
  test `0.4396`;
- three clips have zero detected hands: two training clips and one fresh-test clip;
- 49 additional clips have hand-hit rate below `0.25`;
- 152 clips reach the 96-frame cap, concentrated in validation and historical/local sources.

The three zero-hand clips remain in the frozen baseline. Removing the fresh-test failure after
inspection would bias the end-to-end result, while two of 685 training rows are not a material
reason to mutate the preregistered dataset. Low-hand rows remain visible in source-aware analysis.

## Deployed 236-Class Control

The current Android `streaming.tflite` was evaluated on the newly extracted tensors:

| Split | Full 236 top-1 | Full 236 top-5 | Restricted-five top-1 |
|---|---:|---:|---:|
| Validation | 0.4358 | 0.8045 | 0.7654 |
| Fresh test | 0.5867 | 0.8967 | 0.9467 |
| Historical test | 0.5397 | 0.8413 | 0.9365 |

**Verified interpretation:** the deployed model separates these five labels well when competition
is restricted, but often selects one of the other 231 classes. A five-class model is therefore
expected to score much higher than the deployed full-vocabulary model. Passing this pilot validates
the repaired extraction/training path; it does not demonstrate 236-class scalability.

## Training Configuration

- 4 TCN blocks, 64 channels, dilations `1/2/4/8`, kernel 3, dropout `0.3`.
- Batch size `32`, up to `40` epochs, AdamW learning rate `0.0005`, weight decay `0.0001`.
- Early-stop patience `8`.
- Training-only rotation, scale, and coordinate noise augmentation.
- No class weighting and no warm start.

## Acceptance Gates

The primary checkpoint is `latest.keras`, aggregated across three seeds:

- mean fresh-test top-1 `>= 0.80`;
- minimum seed fresh-test top-1 `>= 0.70`;
- every class mean fresh-test recall `>= 0.70`;
- every class minimum-seed fresh-test recall `>= 0.50`.

Passing these gates permits the separate negative-gate evaluation and planning a larger automated
batch. It does not permit Android deployment. Failure stops model expansion and triggers extraction,
label, signer, and source-aware root-cause review.

## Developer-Run Commands

Full extraction is the first long, resumable step:

```powershell
cd "F:\ASL DATASET\5. Apphear3"

.\.venv\Scripts\python.exe -m pipeline.rgb.e6_v30_five_sign_baseline extract-positive `
  --run-dir "artifacts\recognition_upgrade\e6_baseline\e6_v30_five_sign_baseline_01" `
  --require-full
```

Re-run the same command after interruption; completed per-clip outputs are cached.

Then train three seeds:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_v30_five_sign_baseline train `
  --run-dir "artifacts\recognition_upgrade\e6_baseline\e6_v30_five_sign_baseline_01"
```

Resume interrupted training:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_v30_five_sign_baseline train `
  --run-dir "artifacts\recognition_upgrade\e6_baseline\e6_v30_five_sign_baseline_01" `
  --resume
```

Evaluate and check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_v30_five_sign_baseline evaluate `
  --run-dir "artifacts\recognition_upgrade\e6_baseline\e6_v30_five_sign_baseline_01"

.\.venv\Scripts\python.exe -m pipeline.rgb.e6_v30_five_sign_baseline evaluate-deployed `
  --run-dir "artifacts\recognition_upgrade\e6_baseline\e6_v30_five_sign_baseline_01"

.\.venv\Scripts\python.exe -m pipeline.rgb.e6_v30_five_sign_baseline check `
  --run-dir "artifacts\recognition_upgrade\e6_baseline\e6_v30_five_sign_baseline_01" `
  --require-smoke `
  --require-full `
  --require-metrics
```

## Risks And Failure Paths

- **Low MediaPipe hand coverage:** stop and audit failed/low-hit clips; do not train around missing
  evidence.
- **Fresh-signer collapse:** stop expansion and inspect source/signer/variant confounds.
- **Only historical test succeeds:** treat as leakage/domain overfit; no-go.
- **High seed variance:** collect or rebalance data before scaling.
- **Deployed control wins:** investigate training and preprocessing before changing architecture.
- **Five-class model wins only through reduced vocabulary:** do not claim it improves 236-class
recognition; proceed only to controlled batch scaling.

## Three-Seed Training Result

All three seeds (`101`, `202`, `303`) completed and produced latest, best, and final checkpoints.
The run was structurally valid, but the preregistered positive gate failed.

Primary latest-checkpoint result:

- mean fresh-test top-1: `0.7344` versus required `0.80`;
- minimum-seed fresh-test top-1: `0.7233` versus required `0.70`;
- mean recall: `GOOD 0.9833`, `HELLO 1.0000`, `SORRY 1.0000`, `HAVE 0.6667`,
  `KNOW 0.0222`;
- minimum-seed recall: `GOOD 0.9833`, `HELLO 1.0000`, `SORRY 1.0000`, `HAVE 0.6333`,
  `KNOW 0.0000`.

The confusion is stable across seeds:

- fresh `KNOW`: 56-60 of 60 clips are classified as `HELLO`;
- fresh `HAVE`: 18-22 of 60 clips are classified as `GOOD`;
- fresh `GOOD`, `HELLO`, and `SORRY` are essentially perfect.

Changing checkpoint policy does not repair the failure. Best/final fresh `KNOW` recall remains
between `0.0167` and `0.10`; validation `KNOW` remains between `0.0` and `0.0645`.

Historical performance is materially stronger: latest historical top-1 is `0.8571-0.9365`, and
historical `KNOW` recall is `0.5385-1.0`. This is evidence of source/signer-domain failure rather
than a universally inseparable pair.

The deployed control strengthens that conclusion. On the same fresh tensors, its restricted-five
recall is `KNOW 0.80` and `HAVE 1.0`, while the new from-scratch model collapses those classes.
Therefore, the fresh labels are not disproved by this run. The clean five-class model likely learned
training-source or signer-specific shortcuts and failed to transfer them.

**Decision:** `positive_baseline_no_go_root_cause_review`. Do not run the negative-gate experiment,
scale vocabulary, export TFLite, or modify Android from these checkpoints.

## Assumptions And Open Questions

- The full re-extraction may expose more quality failures than the reviewed raw-video audit.
- One fresh signer is enough for a pilot discriminator, not a production confidence interval.
- Negative false-commit evaluation remains mandatory after positive classification passes.
- Larger-vocabulary scaling size will be selected only after this result; it will be a batch, not
  one sign at a time.

## Next Required Action

The bounded root-cause audit is complete; see `E6_V30_CONFUSION_ROOT_CAUSE_RESULT.md`. It found
that the broader deployed model separates the same fresh tensors much better than the new
from-scratch model, while the split remains weak for validation `HAVE` and population-level fresh
signer claims. The only recommended next model test is a one-variable warm-start diagnostic using
the broader causal encoder and the exact same five-sign data/configuration. Do not start it without
approval. Negative-gate modeling, TFLite export, Android integration, richer features, RGB, and
vocabulary expansion remain blocked.

## Related Context

- `E6_FIVE_SIGN_ASSIGNMENT_RESULT.md`
- `E6_V30_CONFUSION_ROOT_CAUSE_RESULT.md`
- `E6_NEGATIVE_UPLOAD_REVIEW_PACKAGE.md`
- `../../EVALUATION_AND_ACCEPTANCE_GATES.md`
- `../../ROLLBACK_AND_COMPATIBILITY_PLAN.md`
- `../../../feature-schema.md`
