# E3-B0 Pilot 02 Strict-Support Result

**Purpose:** Record the completed stricter RGB feasibility pilot and its decision impact.

**Scope:** Experiment result documentation only. This does not authorize Android integration,
production model replacement, full RGB extraction, or hybrid training.

**Current status:** COMPLETE / PIPELINE PASS / STANDALONE FULL-FRAME RGB NO-GO IN THIS FORM.

**Last updated:** 2026-07-28.

## Verified Project References

- Runner: `pipeline/rgb/e3_b0_pilot.py`.
- Run directory: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support`.
- Source preflight: `artifacts/recognition_upgrade/e3_rgb_b0/preflight_01`.
- Config: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support/pilot_config.json`.
- Manifest: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support/dataset/dataset_manifest.csv`.
- Tensor archive: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support/dataset/rgb_pilot_dataset.npz`.
- Metrics: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support/metrics/metrics.json`.
- Diagnostic: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support/metrics/prediction_diagnostic.json`.
- Models: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support/models/latest.keras` and
  `artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support/models/best.keras`.

## Run Summary

- Experiment: `e3_b0_rgb_bounded_pilot_v1`.
- Dataset tensor shape: `[168, 16, 112, 112, 3]`.
- Classes: 7.
- Class list: `DOG1`, `BITE1`, `DEMAND1`, `WHATFOR1`, `DEAF1`, `PARTY1`,
  `ROCKINGCHAIR1`.
- Split counts: 112 train, 28 validation, 28 test.
- Per-class split policy: 16 train, 4 validation, 4 test.
- Signer leakage check: none across train, validation, and test.
- Total epochs after resume: 6.
- `check` result: passed with no reported errors.
- Random top-1 baseline for 7 balanced classes: 0.1429.

## Metrics

| Split | Accuracy | Loss | Count |
|---|---:|---:|---:|
| Train | 0.3482 | 1.7332 | 112 |
| Validation | 0.0714 | 2.0675 | 28 |
| Test | 0.1071 | 2.1379 | 28 |

Training accuracy increased from 0.1339 to 0.3214 across the six logged epochs, while validation
accuracy declined from the random baseline level of 0.1429 to 0.0714. Test accuracy was 0.1071,
below the 7-class random baseline.

## Diagnostic Findings

- Validation predictions were biased toward `BITE1` and `DEMAND1`; only `BITE1` had any validation
  correct predictions.
- Test predictions were biased toward `DEMAND1`, `DOG1`, and `BITE1`; `WHATFOR1`, `DEAF1`,
  `PARTY1`, and `ROCKINGCHAIR1` had zero correct test predictions.
- Mean confidence was low and poorly calibrated: incorrect held-out predictions were at least as
  confident as correct predictions.
- The model did not learn a signer-independent full-frame RGB representation under this tiny
  architecture and 112x112 full-frame preprocessing.

## Interpretation

This run answers the question that `pilot_01` left open. The poor validation result was not only
caused by having two held-out clips per class. Even with twice as many held-out clips per class and
fewer classes, standalone full-frame RGB with the tiny temporal CNN failed to generalize.

This does not prove that RGB is useless. It proves that the current bounded **full-frame 112x112
RGB + tiny temporal CNN** setup should not be scaled or promoted. It likely loses hand-shape detail,
learns signer/background/camera artifacts, and lacks the pretrained visual features or ROI focus
needed for ASL hand-shape recognition.

## Decision

E3-B0 `pilot_02_strict_support` is a **technical pass** and an **accuracy no-go**.

Do not run larger standalone full-frame RGB training with this architecture. Do not integrate this
model path into Android.

## Recommended Next Action

Pivot from standalone full-frame RGB to a more defensible visual branch:

- keep the existing landmark/TCN baseline as the control;
- test a small pretrained hand/upper-body visual encoder rather than a from-scratch tiny CNN;
- use landmark-guided or detector-guided crops when reliable enough, with full-frame kept only as a
  fallback/context stream;
- keep all experiments signer-disjoint and bounded before any full E3 training.

## Architecture Decisions

- Standalone full-frame 112x112 RGB is not recommended as the primary AppHear recognition path.
- RGB remains a candidate only as a focused/pretrained stream inside a hybrid model.
- The production v3.0 recognizer remains untouched.

## Assumptions

- ASL Citizen labels and official split files are authoritative for this pilot.
- The tiny CNN is intentionally small, so this no-go applies to this full-frame setup, not every
  possible RGB model.

## Open Questions

- Would hand crops at higher effective hand resolution outperform full-frame 112x112?
- Would a frozen or lightly fine-tuned MobileNetV3/EfficientNet-Lite visual encoder generalize
  better than the from-scratch tiny CNN?
- Can crop reliability be made good enough without causing MediaPipe-dependent failures?
- Should the next visual test use hand crops, upper-body crops, or a two-stream crop/full-frame
  design?

## Risks

- Scaling full-frame RGB now would likely waste compute and confuse the architecture decision.
- A pretrained RGB branch may still overfit if the dataset is too small or signer variation is not
  strong enough.
- Crop-based RGB depends on reliable ROI generation, which remains an unresolved project risk.

## Next Required Action

Prepare the next E3 branch as a bounded pretrained/crop-aware visual experiment, or return to the
landmark branch and improve temporal/feature modeling before attempting hybrid fusion.

