# E5-F Reduced Primary Routed Simulation Result

**Purpose:** Record the E5-F offline routed simulation over the E5-E 7-sign primary subset, E5-D model predictions, and E4-AG no-sign gate.

**Scope:** Offline replay/simulation only. This document does not authorize Android integration, TFLite export, production recognizer replacement, schema mutation, dataset mutation, or UI changes.

**Current status:** COMPLETE / NO-GO FOR EXPORT / E5-G CLEAN 7-CLASS RETRAIN RECOMMENDED.

**Last updated:** 2026-08-03.

## Verified Project References

- Runner: `pipeline/rgb/e5_f_reduced_primary_routed_sim.py`
- Strict run: `artifacts/recognition_upgrade/e5_batch_screening/e5_f_reduced_primary_routed_sim_01`
- Relaxed diagnostic run: `artifacts/recognition_upgrade/e5_batch_screening/e5_f_reduced_primary_routed_sim_02_relaxed_diagnostic`
- Source E5-D run: `artifacts/recognition_upgrade/e5_batch_screening/e5_d_reduced_primary_15sign_01`
- Source E5-E run: `artifacts/recognition_upgrade/e5_batch_screening/e5_e_reduced_primary_decision_01`
- Gate run: `artifacts/recognition_upgrade/e4_generalization/e4_ag_low_motion_gate_01`
- No-sign tensor: `artifacts/recognition_upgrade/e4_generalization/e4_ag_hello_like_nosign_expansion_01`
- Structural checks: passed for strict and relaxed diagnostic runs with `--require-metrics`

## Simulation Design

E5-F did not train a new model. It replayed the completed E5-D 15-class model and allowed commits only for the E5-E selected 7-sign subset:

`WASH2`, `THINK`, `TAKE`, `MEET`, `GOOD`, `SELL`, `STAND2`

The remaining E5-D signs were treated as unsupported/OOV pressure rows:

`HAVE`, `WANT2`, `WORK`, `MORNING`, `DRIVE`, `RUN2`, `USE`, `SLEEP`

Real no-sign rows came from E4-AG:

- `N0`: `180`
- `P1`: `108`
- `P1_HELLO_LIKE`: `116`

Combined rows: `1099`

- selected positive rows: `344`
- unsupported rows: `351`
- no-sign rows: `404`

Decision policy:

`E4-AG signing gate -> E5-D primary prediction -> commit only if predicted class is in E5-E 7-sign subset and confidence passes threshold -> otherwise reject`

The GOOD/SORRY specialist was not exercised because SORRY is absent from E5-D primary data. Existing GOOD/SORRY specialist evidence remains separate from E4-W/E4-X.

## Strict Result

Strict run selected primary confidence `0.99`.

Test summary:

- mean accepted precision: `0.9642`
- minimum accepted precision: `0.9310`
- mean positive coverage: `0.3611`
- minimum positive coverage: `0.3333`
- max unsupported false commit rate: `0.0110`
- max no-sign false commit rate: `0.0000`
- minimum class recall: `0.0000`
- mean class recall: `0.3467`

Interpretation: safety was good, but the policy rejected too many real signs. This is not usable for translation.

## Relaxed Diagnostic Result

Relaxed diagnostic selected primary confidence `0.80` by removing the per-class recall gate.

Test summary:

- mean accepted precision: `0.9081`
- minimum accepted precision: `0.8689`
- mean positive coverage: `0.7870`
- minimum positive coverage: `0.7639`
- max unsupported false commit rate: `0.0659`
- max no-sign false commit rate: `0.0000`
- minimum class recall: `0.4545`
- mean class recall: `0.7612`

Interpretation: coverage improved and no-sign false commits stayed at zero, but precision and minimum class recall remained below the required floor.

## Decision

E5-F is a no-go for Android/export. The E5-E 7-sign subset is promising, but replaying a 15-class model and rejecting non-selected outputs is not strong enough.

The failure mode is clear:

- no-sign rejection works well in this simulation;
- unsupported false commits are manageable;
- the real blocker is that selected-class recall and precision are not both high enough when using a 15-class model as a 7-sign recognizer.

## Recommended Next Action

Prepare E5-G: a clean 7-class retrain using only the E5-E selected primary subset, with the same E4-AG no-sign gate simulation after training.

Reason: E5-F shows the system should not rely on post-hoc rejection over a 15-class model. A clean 7-class model may recover recall and confidence calibration because the classifier no longer has to distribute probability across weak/unsupported E5-D classes.

E5-G should still be offline-only first. It should not export or touch Android unless it passes accepted precision, coverage, no-sign false-commit, unsupported/OOV, and per-class recall gates.

## Architecture Decisions

- Preserve landmark-primary dynamic mixed recognition.
- Keep schema v3.0 `[96,258]` unchanged.
- Do not export E5-D or E5-F artifacts.
- Do not continue broad 15-sign runtime simulation as the next step.
- Train a clean 7-class primary candidate next, then rerun the routed/no-sign simulation.

## Open Questions

- Will a clean 7-class model recover the low recalls seen for `GOOD`, `SELL`, `STAND2`, and `MEET` under the replay policy?
- Should E5-G include `MORNING` or `HAVE` as an alternate wider subset, or keep the first clean retrain strict?
- Does the E4-AG no-sign gate remain reliable when paired with a newly trained E5-G primary model?
- When SORRY is reintroduced through the specialist path, does the combined routed system preserve precision?

## Risks

- A 7-class clean retrain may still overfit source/provenance artifacts.
- A smaller vocabulary improves safety but limits product usefulness.
- Reusing E5-D/E5-F test artifacts for too many decisions can overfit experiment planning.
- Android export before E5-G/E5-H gates would risk silent wrong translations.

## Next Required Action

Prepare E5-G clean 7-class primary retrain package. Do not export TFLite, change Android, or replace production assets before E5-G is trained and evaluated offline.
