# E3-C Frozen-Split Landmark + RGB Fusion Result

- **Purpose:** Record the completed E3-C result and decide whether the current RGB fusion design should continue.
- **Scope:** Offline recognition-upgrade experiment only. No Android runtime, production recognizer, model asset, feature schema, dataset, or UI behavior was changed.
- **Current status:** Completed on 2026-07-29. Final check passed, but the experiment is a no-go for this RGB fusion design.
- **Verified project references:** `pipeline/rgb/e3_c_fusion.py`, `artifacts/recognition_upgrade/e3_fusion/pilot_02_frozen_50_landmark_rgb/metrics/metrics.json`, `metrics/metrics.md`, `pilot_config.json`, and `check_report.json`.
- **Source-of-truth files:** This result document, `E3_C_FUSION_PLAN.md`, `E3_B6_RESULT.md`, `E3_B7_RESULT.md`, and the run directory named above.
- **Related context files:** `README.md`, `EXPERIMENT_MATRIX.md`, `HYBRID_FUSION_DESIGN.md`, `RISK_REGISTER.md`, `OPEN_QUESTIONS.md`, and parent `../progress-tracker.md`.

## Verified Run

- **Run directory:** `artifacts/recognition_upgrade/e3_fusion/pilot_02_frozen_50_landmark_rgb`.
- **Final check:** `passed: true`, no missing outputs.
- **Landmark tensor:** `[1200,96,728]`, using the E3-B6 augmented landmark stream.
- **RGB tensor:** `[1200,16,576]`, using 16 sampled upper-body center-crop MobileNetV3Small frame embeddings.
- **Split:** 50 classes, 1,200 clips, 800 train / 200 validation / 200 test, signer-disjoint E3-B5 frozen split.
- **Seeds:** `101`, `202`, `303`.
- **Epoch count:** 24 total epochs per branch/seed after resume.
- **Elapsed time reported by the run:** `177.79` seconds for the final run phase after RGB tensors/embeddings already existed.

## Metrics

| Branch | Mean Best Train | Mean Best Val | Mean Best Test | Train-Val Gap | Val-Test Gap | Decision |
|---|---:|---:|---:|---:|---:|---|
| `rgb_only` | `0.9625` | `0.1500` | `0.0750` | `0.8125` | `0.0750` | No-go |
| `landmark_aug_only` | `0.8258` | `0.5117` | `0.3867` | `0.3142` | `0.1250` | Best control |
| `fusion_aug_rgb` | `0.9696` | `0.2617` | `0.1867` | `0.7079` | `0.0750` | No-go |

Seed winners by best validation:

- Seed `101`: `landmark_aug_only`
- Seed `202`: `landmark_aug_only`
- Seed `303`: `landmark_aug_only`

Gate comparison:

- Fusion validation gain over E3-B6 masked reference: `-0.2500`.
- Fusion test gain over E3-B6 Conv1D reference: `-0.2016`.
- `decision_hint.promising`: `false`.

## Interpretation

The run is valid because the `landmark_aug_only` branch reproduced the E3-B6 result almost exactly: mean best validation/test `0.5117/0.3867`. That means the split, label mapping, and landmark tensor alignment were not broken.

The RGB-only branch heavily overfit. It reached mean best train accuracy `0.9625`, but only `0.1500` validation and `0.0750` test. This indicates that the current upper-body frozen-MobileNet visual stream is learning signer, clothing, background, camera, or other non-generalizing cues rather than signer-independent sign evidence.

The fusion branch also overfit and damaged the landmark signal. It reached mean best train accuracy `0.9696`, but only `0.2617` validation and `0.1867` test. Fusion did not merely fail to help; it pulled performance far below landmark-only because the model learned to trust the weak visual stream.

## Decision

Do not promote E3-C. Do not integrate this RGB branch into Android. Do not repeat this exact design with more epochs.

Specifically rejected for now:

- Upper-body center crop as the main visual stream.
- Frozen MobileNetV3Small embeddings as the only RGB representation.
- Simple concat fusion without safeguards against a weak RGB stream overpowering landmarks.
- Scaling this same RGB-only or naive-fusion approach to Android.

This does not prove RGB is useless. It proves this specific RGB representation and fusion strategy are not reliable enough on the current signer-disjoint 50-class benchmark.

## Engineering Recommendations

The strongest current path remains landmark-first. The best verified offline recognizer evidence is still E3-B6 full augmented landmarks, but it was not promoted because validation gain was below gate and seed winners were unstable.

Future RGB work should only continue if it changes the visual evidence source, not by rerunning the same upper-body MobileNet setup. Acceptable next RGB directions require one or more of:

- Real hand crops from a more reliable detector or reviewed crop pipeline.
- Hand-shape-focused visual pretraining or fine-tuning instead of generic frozen ImageNet embeddings.
- Stronger fusion controls such as late fusion, gated fusion, branch dropout, frozen landmark control, or confidence-based visual weighting.
- Explicit crop-quality filtering and failure analysis.

The immediate next architecture choice should be between:

- **Landmark/data path:** improve signer-independent generalization through better data splits, more signers, stronger validation, calibration, and possibly a cleaner landmark temporal architecture.
- **Detector/hand-crop path:** continue C0-style detector/crop reliability work before attempting RGB fusion again.

## Assumptions

- E3-C used the intended E3-B5 frozen split because the landmark control reproduced E3-B6 metrics and the run check passed.
- The visual failure is attributed to the current RGB representation and fusion design, not to a broken run. This is an engineering inference from the metric pattern.
- The result does not evaluate detector-derived hand crops or fine-tuned visual models.

## Open Questions

- Would detector-derived hand crops provide materially better visual signal than upper-body center crops?
- Would a hand-shape classifier trained on signer-diverse hand crops help specific confusion groups?
- Is the current dataset large/diverse enough for any RGB visual branch, or does it need more signers before RGB can generalize?
- Can gated/late fusion protect the landmark branch from weak visual evidence?
- Should the next promotion attempt focus on landmarks/data rather than RGB?

## Risks

- Repeating weak RGB fusion may waste time and produce misleading train accuracy.
- Adding RGB to Android too early would increase compute and battery cost while reducing recognition reliability.
- Landmark-only gains may also remain capped without more signer-diverse data and better acceptance/calibration logic.

## Next Required Action

Do not continue E3-C as-is. Decide and architect the next experiment explicitly. The safest next technical step is to analyze whether C0 detector/hand-crop reliability is good enough to support a real hand-crop RGB stream; if not, return to landmark/data improvements before another visual fusion attempt.
