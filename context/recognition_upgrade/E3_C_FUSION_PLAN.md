# E3-C Frozen-Split Landmark + RGB Fusion Plan

- **Purpose:** Test whether visual information adds real signer-independent value when fused with the strongest current landmark feature set, instead of judging RGB as a standalone recognizer.
- **Scope:** Offline experiment only. No Android runtime, production recognizer, model asset, schema contract, or UI behavior changes are authorized.
- **Current status:** Completed on 2026-07-29. Final check passed, but `fusion_aug_rgb` failed the gate and should not be promoted.
- **Source-of-truth files:** `pipeline/rgb/e3_c_fusion.py`, `artifacts/recognition_upgrade/e3_fusion/pilot_02_frozen_50_landmark_rgb/pilot_config.json`, `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed/pilot_manifest.csv`, and `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_03_feature_augmented/dataset/augmented_features.npz`.
- **Related context files:** `E3_B5_RESULT.md`, `E3_B6_RESULT.md`, `E3_B7_RESULT.md`, `HYBRID_FUSION_DESIGN.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `RISK_REGISTER.md`, and parent `../progress-tracker.md`.

## Verified Project References

- E3-B5 frozen 50-class split is the comparison base: 1,200 clips, 800 train / 200 validation / 200 test, signer-disjoint, fixed seeds `101`, `202`, `303`.
- E3-B6 full augmented landmark tensor is the current strongest landmark-feature reference: `[1200,96,728]`, with mean best validation/test `0.5117/0.3867` for masked TCN and `0.5033/0.3883` for Conv1D.
- E3-B7 did not promote reduced feature subsets; full E3-B6 remains the best available landmark test reference.
- Earlier E3-B0/E3-B1/E3-B2 standalone RGB tests were weak, so E3-C treats RGB as an auxiliary stream, not as a replacement recognizer.

## Experiment Contract

- **Run directory:** `artifacts/recognition_upgrade/e3_fusion/pilot_02_frozen_50_landmark_rgb`.
- **Runner:** `pipeline/rgb/e3_c_fusion.py`.
- **Landmark input:** E3-B6 augmented landmark stream `[96,728]` with frame mask.
- **RGB input:** 16 sampled RGB frames per clip, 160x160 upper-body center crop, MobileNetV3Small ImageNet frame embeddings.
- **Branches:** `rgb_only`, `landmark_aug_only`, and `fusion_aug_rgb`.
- **Training defaults:** batch size `8`, epochs `12` per run command, seeds `101`, `202`, `303`, learning rate `5e-4`.
- **Output policy:** all generated RGB tensors, embeddings, checkpoints, logs, metrics, summaries, and smoke outputs stay under the run directory.

## Why This Comes Next

E3-B6 showed that engineered landmark motion/relationship features improve test accuracy, but the gain is not stable enough to promote. E3-B7 showed that smaller subsets do not beat the full augmented stream. The next highest-value question is whether RGB contains complementary hand-shape/appearance evidence that landmarks miss, especially for signs with similar trajectories or unstable landmarks.

## Gate

Promote the direction only if all of these hold:

- Fusion improves mean best test accuracy over E3-B6 full augmented Conv1D by at least `+0.03`.
- Fusion mean best validation is at least the E3-B6 full augmented masked TCN reference.
- Fusion beats both branch-only controls on validation and test.
- Prediction bias and major confusion groups improve rather than just shifting to a different collapsed class set.
- RGB extraction cost remains plausible for later mobile or server-assisted design.

No-go if RGB-only is weak and fusion does not beat landmark-only, if the gain is only train accuracy, or if extraction/embedding is too slow or brittle for the product path.

## Prepared Validation

- Syntax compile passed for `pipeline/rgb/e3_c_fusion.py`.
- Prepare passed and reconstructed the E3-B5 frozen rows with 1,200 mapped videos.
- Structural check passed for the prepared run.
- Smoke test passed on 8 rows: RGB extraction, MobileNetV3 embedding, model creation, forward pass, one training batch, and weight writing for `rgb_only`, `landmark_aug_only`, and `fusion_aug_rgb`.

## Assumptions

- The metadata alignment from `features_streaming/*.npz` back to Stage-E span/video files is valid because it recovered all rows in split order and then validates selected participant/gloss matches against the frozen E3-B5 manifest.
- Upper-body center crops are a practical first RGB stream; hand-detector-derived crops remain a later C0-dependent option.
- ImageNet MobileNetV3 features are sufficient as a low-cost visual baseline. If this fails, the next RGB improvement should be justified by an error analysis, not by more blind epochs.

## Open Questions

- Does visual information improve held-out signer accuracy when fused with the augmented landmark stream?
- Are failures caused by weak RGB crop quality, weak fusion design, insufficient data, or signer-generalization limits?
- Does fusion reduce known confusion groups, or does it merely change prediction bias?
- Would detector-derived hand crops outperform upper-body center crops enough to justify the C0 path?

## Risks

- RGB branch may overfit signer/background/camera cues.
- Fusion may learn to trust the weaker visual stream and regress against landmark-only.
- Extracting full RGB tensors may be slow and disk-heavy on CPU-only machines.
- Mobile deployment is not proven; E3-C is an offline evidence-gathering step only.

## Next Required Action

See `E3_C_RESULT.md`. Do not continue this upper-body frozen-MobileNet fusion design. Next experiment must be explicitly re-architected around either detector-derived hand crops or landmark/data generalization improvements.

