# E3-B2 Same-Signer RGB Sanity Result

**Purpose:** Record the completed intentionally signer-leaky RGB sanity check after E3-B1 failed
cross-signer generalization.

**Scope:** Debugging result only. This split intentionally includes signer overlap and must not be
reported as production or cross-signer accuracy.

**Current status:** COMPLETE / PIPELINE PASS / SAME-SIGNER WEAK NO-GO.

**Last updated:** 2026-07-28.

## Verified Project References

- Plan: `context/recognition_upgrade/E3_B2_SAME_SIGNER_SANITY_PLAN.md`.
- Builder: `pipeline/rgb/e3_b2_same_signer_sanity.py`.
- Runner: `pipeline/rgb/e3_b1_pretrained_rgb.py`.
- Run directory: `artifacts/recognition_upgrade/e3_rgb_b2/pilot_01_same_signer_mobilenetv3`.
- Metrics: `artifacts/recognition_upgrade/e3_rgb_b2/pilot_01_same_signer_mobilenetv3/metrics/metrics.json`.
- Best checkpoint eval:
  `artifacts/recognition_upgrade/e3_rgb_b2/pilot_01_same_signer_mobilenetv3/metrics/best_checkpoint_eval.json`.
- Check: `artifacts/recognition_upgrade/e3_rgb_b2/pilot_01_same_signer_mobilenetv3/check_report.json`.

## Run Summary

- Experiment: `e3_b2_same_signer_rgb_sanity_v1`.
- Input: 16 sampled frames per clip, 160x160 upper-body center crop.
- Encoder: frozen `MobileNetV3Small` frame embeddings with `imagenet` weights.
- Feature shape: `[84, 16, 576]`.
- Classes: 7.
- Split counts: 56 train, 14 validation, 14 test.
- Per-class split policy: 8 train, 2 validation, 2 test.
- Signer leakage: intentional; validation/test signers overlap train signers for same-class sanity.
- Total epochs after resume: 16.
- `check` result: passed with no reported errors.
- Random top-1 baseline for 7 balanced classes: 0.1429.

## Metrics

Latest checkpoint:

| Split | Accuracy | Mean confidence | Count |
|---|---:|---:|---:|
| Train | 1.0000 | 0.9505 | 56 |
| Validation | 0.2143 | 0.6090 | 14 |
| Test | 0.2857 | 0.6397 | 14 |

Best validation checkpoint:

| Split | Accuracy | Mean confidence | Count |
|---|---:|---:|---:|
| Train | 0.9464 | 0.8112 | 56 |
| Validation | 0.3571 | 0.5665 | 14 |
| Test | 0.3571 | 0.5854 | 14 |

Pre-registered gate:

- strong pass: validation and test both >=0.70;
- weak pass: validation and test both >=0.50;
- no-go: near random, unstable, or collapsed predictions.

E3-B2 did not reach the weak-pass gate.

## Interpretation

E3-B2 confirms that the improved RGB branch can memorize the training set, but it still does not
solve even the intentionally easier same-signer held-out sanity test. The best checkpoint performs
above random but remains far below the weak-pass threshold. The final checkpoint overfits further:
training reaches 100%, while validation and test remain low.

This is an important result. It means the current visual-only branch is not merely failing because
of signer-independent generalization. Even when the signer barrier is relaxed, the branch does not
extract robust enough sign-discriminative information from upper-body RGB alone at this small scale.

## Comparison

| Run | Split policy | Train | Validation | Test |
|---|---|---:|---:|---:|
| E3-B1 latest | signer-disjoint | 0.9911 | 0.1429 | 0.1429 |
| E3-B1 best-val | signer-disjoint | 0.8482 | 0.2143 | 0.1071 |
| E3-B2 latest | same-signer sanity | 1.0000 | 0.2143 | 0.2857 |
| E3-B2 best-val | same-signer sanity | 0.9464 | 0.3571 | 0.3571 |

E3-B2 improves held-out accuracy relative to E3-B1, but not enough to call the RGB branch viable.

## Decision

E3-B2 is a **technical pass** and a **same-signer weak no-go**.

Do not scale standalone RGB-only training. Do not spend more time adding epochs to this branch.
Do not start Android integration from these RGB-only experiments.

## Recommended Next Action

The next practical step should be a bounded landmark-plus-RGB fusion smoke only if it can reuse
existing extracted features without long extraction. The purpose would be to test whether RGB adds
complementary signal to the already stronger landmark path, not whether RGB can work alone.

If fusion cannot be prepared cheaply, return to landmark temporal/feature improvements first.

## Open Questions

- Is upper-body RGB missing hand-shape detail that only reliable hand crops can provide?
- Would a larger same-signer clip count change the sanity result, or is the model mostly learning
  shortcuts?
- How does the current landmark TCN perform on the exact same 7-class subset?
- Does RGB add any useful signal when fused with landmarks, despite weak standalone accuracy?

## Risks

- Continuing RGB-only experiments may consume time without addressing the stronger landmark branch.
- Same-signer results can overstate progress; this run still failed the weak sanity gate.
- Small validation/test counts make exact percentages noisy, but the gap from 0.50 is large enough
  that this is not a pass.

## Next Required Action

Do not run more E3-B2 epochs. Decide whether to prepare a bounded landmark-plus-RGB fusion smoke or
return to landmark temporal/feature improvements.

