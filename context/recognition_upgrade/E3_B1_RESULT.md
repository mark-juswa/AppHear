# E3-B1 Improved RGB Result

**Purpose:** Record the completed MobileNetV3 upper-body RGB pilot and compare it against E3-B0.

**Scope:** Experiment result documentation only. This does not authorize Android integration,
production model replacement, full RGB extraction, detector training, or hybrid fusion.

**Current status:** COMPLETE / PIPELINE PASS / HELD-OUT ACCURACY NO-GO.

**Last updated:** 2026-07-28.

## Verified Project References

- Runner: `pipeline/rgb/e3_b1_pretrained_rgb.py`.
- Run directory: `artifacts/recognition_upgrade/e3_rgb_b1/pilot_01_mobilenetv3_upper_body`.
- Source split: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support/pilot_manifest.csv`.
- Config: `artifacts/recognition_upgrade/e3_rgb_b1/pilot_01_mobilenetv3_upper_body/pilot_config.json`.
- Features: `artifacts/recognition_upgrade/e3_rgb_b1/pilot_01_mobilenetv3_upper_body/dataset/rgb_frame_features.npz`.
- Metrics: `artifacts/recognition_upgrade/e3_rgb_b1/pilot_01_mobilenetv3_upper_body/metrics/metrics.json`.
- Best checkpoint evaluation: `artifacts/recognition_upgrade/e3_rgb_b1/pilot_01_mobilenetv3_upper_body/metrics/best_checkpoint_eval.json`.
- Check: `artifacts/recognition_upgrade/e3_rgb_b1/pilot_01_mobilenetv3_upper_body/check_report.json`.

## Run Summary

- Experiment: `e3_b1_pretrained_rgb_pilot_v1`.
- Input: 16 sampled frames per clip, 160x160 upper-body center crop.
- Encoder: frozen `MobileNetV3Small` frame embeddings with preferred `imagenet` weights.
- Feature shape: `[168, 16, 576]`.
- Classes: 7.
- Split counts: 112 train, 28 validation, 28 test.
- Per-class split policy: 16 train, 4 validation, 4 test.
- Total epochs after resume: 16.
- `check` result: passed with no reported errors.
- Random top-1 baseline for 7 balanced classes: 0.1429.

## Metrics

Latest checkpoint:

| Split | Accuracy | Mean confidence | Count |
|---|---:|---:|---:|
| Train | 0.9911 | 0.8942 | 112 |
| Validation | 0.1429 | 0.6887 | 28 |
| Test | 0.1429 | 0.7149 | 28 |

Best validation checkpoint:

| Split | Accuracy | Mean confidence | Count |
|---|---:|---:|---:|
| Train | 0.8482 | 0.6300 | 112 |
| Validation | 0.2143 | 0.6267 | 28 |
| Test | 0.1071 | 0.4900 | 28 |

Comparator, E3-B0 strict-support latest:

| Run | Train | Validation | Test |
|---|---:|---:|---:|
| E3-B0 full-frame 112 tiny CNN | 0.3482 | 0.0714 | 0.1071 |
| E3-B1 MobileNetV3 upper-body latest | 0.9911 | 0.1429 | 0.1429 |
| E3-B1 MobileNetV3 upper-body best-val | 0.8482 | 0.2143 | 0.1071 |

## Interpretation

E3-B1 materially improved representational capacity. The model nearly memorized the training split,
which E3-B0 could not do. That means MobileNetV3 embeddings and the 160x160 upper-body crop are much
stronger than the tiny from-scratch CNN for fitting the available examples.

However, held-out signer performance did not become reliable. The latest checkpoint only reached
random baseline on validation and test. The best validation checkpoint briefly rose above random on
validation, but did not improve test accuracy. The increasing train accuracy combined with rising
validation loss is classic overfitting.

The result is therefore not "RGB is fixed." It is "improved RGB can learn the training examples, but
this bounded dataset/protocol still does not produce signer-independent RGB recognition."

## Important Correction

During analysis, the E3-B1 class-name list was found to be saved in manifest order while labels were
inherited from the E3-B0 numeric label order. Accuracy values were valid because numeric labels were
used consistently, but per-class diagnostic names were initially wrong. The runner was corrected to
inherit `classes` from the source `pilot_config.json`, the package metadata was corrected, and
diagnostics were regenerated.

## Decision

E3-B1 is a **technical pass** and a **held-out accuracy no-go**.

Do not scale this exact upper-body MobileNetV3-only RGB branch to a larger dataset yet. It is better
than E3-B0, but not enough to justify Android or full-training work.

## Recommended Next Action

The evidence now points to a data/model issue rather than a plumbing issue. The safest next step is
not more epochs. Choose one of these before scaling:

- run a very small **same-signer overfit sanity** to confirm the visual branch can classify easy
  cases when signer leakage is allowed intentionally for debugging;
- or build a **landmark plus RGB feature-level fusion smoke** using the same 7-class split to test
  whether RGB adds complementary signal to landmarks instead of carrying recognition alone.

Do not treat standalone RGB as the primary recognizer unless a later signer-disjoint test clears the
registered gate.

## Open Questions

- Is 7-class held-out support too small and noisy, or is RGB genuinely not transferring with this
  dataset?
- Would landmark/RGB fusion stabilize the held-out classes where RGB alone fails?
- Would hand-specific crops, once reliable, transfer better than upper-body crops?
- Are ASL Citizen classes in this pilot visually too similar or too signer/style-dependent for RGB
  alone?

## Risks

- More epochs will likely increase train memorization while lowering generalization.
- Testing many variants on the same small validation/test split can overfit experiment decisions.
- A larger standalone RGB run could waste compute if the model continues to learn signer/background
  shortcuts.

## Next Required Action

Do not run more E3-B1 epochs. Decide between a same-signer visual sanity check and a bounded
landmark-plus-RGB fusion smoke before any full E3 training or Android work.

