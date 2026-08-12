# E3-B0 Pilot 01 Result

**Purpose:** Record the completed bounded RGB feasibility pilot result so later E3 planning does
not overstate or lose the evidence from this run.

**Scope:** Experiment result documentation only. This does not authorize Android integration,
production model replacement, full RGB extraction, or hybrid training.

**Current status:** COMPLETE / PIPELINE PASS / ACCURACY NOT PROVEN.

**Last updated:** 2026-07-28.

## Verified Project References

- Runner: `pipeline/rgb/e3_b0_pilot.py`.
- Run directory: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_01`.
- Config: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_01/pilot_config.json`.
- Manifest: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_01/dataset/dataset_manifest.csv`.
- Tensor archive: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_01/dataset/rgb_pilot_dataset.npz`.
- Metrics: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_01/metrics/metrics.json`.
- History: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_01/logs/history.csv`.
- Diagnostic: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_01/metrics/prediction_diagnostic.json`.
- Models: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_01/models/latest.keras` and
  `artifacts/recognition_upgrade/e3_rgb_b0/pilot_01/models/best.keras`.

## Run Summary

- Experiment: `e3_b0_rgb_bounded_pilot_v1`.
- Dataset tensor shape: `[120, 16, 112, 112, 3]`.
- Classes: 10.
- Clips per class: 12.
- Split counts: 80 train, 20 validation, 20 test.
- Per-class split policy: 8 train, 2 validation, 2 test.
- Total epochs after resume: 6.
- `check` result: passed with no reported errors.

## Metrics

| Split | Accuracy | Loss | Count |
|---|---:|---:|---:|
| Train | 0.3000 | 2.0476 | 80 |
| Validation | 0.0500 | 2.3601 | 20 |
| Test | 0.2500 | 2.3170 | 20 |

Training accuracy increased from 0.0875 to 0.3625 across the six logged epochs, while validation
accuracy stayed at 0.1000 for the first three epochs and dropped to 0.0500 during the resumed
epochs. The 0.2500 test result is above the 0.1000 random baseline for 10 classes, but it is based
on only 20 test clips and must be treated as unstable.

## Interpretation

The E3-B0 pilot proves that the bounded RGB pipeline can:

- read ASL Citizen videos;
- build a timestamp-independent sampled RGB tensor set;
- create balanced signer-disjoint train/validation/test splits for the selected classes;
- train the tiny temporal CNN;
- resume from checkpoint;
- save models, logs, metrics, diagnostics, and check reports under the isolated run directory.

The pilot does not prove that the current RGB approach is accurate. Validation accuracy failed to
improve and became worse after additional epochs, which is a warning sign for overfitting, split
difficulty, weak model capacity, weak preprocessing, or insufficient validation examples. The model
did not collapse to one class; predictions were spread across several labels, so the main failure is
not a trivial single-class collapse.

## Decision

E3-B0 `pilot_01` is a **technical pass** and an **accuracy no-go for promotion**.

Do not proceed directly to large RGB training or Android integration from this result. The next
experiment should reduce statistical noise and separate "RGB has no useful signal" from "the pilot
was too small/noisy."

## Recommended Next Action

Prepare, but do not auto-run, a stricter follow-up pilot using fewer classes with more held-out
clips per class:

- candidate ID: `pilot_02_strict_support`;
- class count: 7;
- split policy: 16 train, 4 validation, 4 test per class;
- total clips: 168;
- input: 16 frames, 112x112 RGB;
- purpose: determine whether validation failure in `pilot_01` was caused by the very small
  2-example validation/test support per class.

If this stricter pilot still fails to exceed random baseline meaningfully on validation, E3 should
not scale RGB training yet. The branch should return to preprocessing/model design: crop quality,
temporal sampling, stronger pretrained RGB encoders, or landmark/RGB fusion instead of standalone
tiny RGB.

## Architecture Decisions

- Keep E3-B0 as a feasibility gate, not an accuracy claim.
- Keep the production v3.0 recognizer untouched.
- Keep ASL Citizen signer-disjoint splitting as mandatory.
- Do not use this pilot to change the current Android recognizer, feature schema, or model assets.

## Assumptions

- The ASL Citizen clips selected by the pilot are label-correct and readable.
- The selected 10 classes are not necessarily representative of the full intended vocabulary.
- The tiny CNN is intentionally a smoke-level architecture, not the final recommended RGB encoder.

## Open Questions

- Would strict-support class selection produce stable validation behavior?
- Would upper-body/full-frame RGB need a pretrained encoder to learn hand shape reliably?
- Would hand crops or landmark-guided ROIs outperform full-frame resizing at 112x112?
- How much of the failure is due to signer variation versus low image resolution versus model
  capacity?

## Risks

- Repeating small pilots can overfit planning decisions to noisy test sets.
- Scaling RGB before a clean validation signal may waste extraction/training time.
- Full-frame 112x112 may discard hand-shape detail needed for many ASL classes.

## Next Required Action

Create a bounded `pilot_02_strict_support` package and have the user run it locally only after
reviewing the command and expected duration.

