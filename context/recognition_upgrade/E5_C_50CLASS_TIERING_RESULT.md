# E5-C 50-Class Tiering Result

**Purpose:** Convert the completed E5-B 50-class ASL-led diagnostic into actionable keep/repair/specialist/defer tiers.

**Scope:** Offline metrics-only analysis. No training, MediaPipe extraction, Android integration, TFLite export, production recognizer replacement, source dataset mutation, or runtime behavior change.

**Current status:** COMPLETE / STRUCTURAL PASS / E5-B NOT EXPORTABLE / REDUCED PRIMARY VALIDATION RECOMMENDED.

**Last updated:** 2026-08-03.

## Verified Project References

- Runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e5_c_batch_tiering.py`
- Source E5-B run: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_b_asl_led_50_primary_01`
- E5-C run directory: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_c_50class_tiering_01`
- Tier summary: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_c_50class_tiering_01\reports\tiering_summary.json`
- Human report: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_c_50class_tiering_01\reports\tiering_report.md`
- Class tiers: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_c_50class_tiering_01\tables\e5_c_class_tiers.csv`
- Confusion pairs: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_c_50class_tiering_01\tables\top_confusion_pairs.csv`
- Check report: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_c_50class_tiering_01\check_report.json`

## Source E5-B Result

E5-B trained a 50-class landmark-primary Conv1D diagnostic on existing schema v3.0 `[96,258]` features.

- Mean latest test accuracy: `0.4897`
- Random baseline: `0.0200`
- E5-B did not collapse into one class, but it is not production-ready.
- Several signs have usable signal, while others show severe confusion or overfit/provenance risk.

## Tier Counts

- `A_primary_candidate_strong`: `9`
- `B_primary_candidate_guarded`: `6`
- `C_regressed_control_repair`: `2`
- `C_confusion_group_candidate`: `8`
- `D_overfit_or_provenance_risk`: `19`
- `D_defer_from_primary`: `6`

## Recommended Reduced Primary Vocabulary Hypothesis

E5-C recommends the following candidate set for the next reduced-primary validation:

`WASH2`, `TAKE`, `MEET`, `HAVE`, `WANT2`, `WORK`, `GOOD`, `MORNING`, `STAND2`, `SELL`, `THINK`, `DRIVE`, `RUN2`, `USE`, `SLEEP`.

This is not a production vocabulary yet. It is the next hypothesis to validate in a smaller model.

## Stable-Control Finding

E5-C found that the 50-class context damaged two previously stable controls:

| Sign | Mean latest test | Min latest test | Tier | Main confusion |
|---|---:|---:|---|---|
| `HAVE` | `0.800` | `0.800` | `A_primary_candidate_strong` | `WANT2` |
| `GOOD` | `0.741` | `0.667` | `A_primary_candidate_strong` | `WATCH` |
| `HELLO` | `0.400` | `0.200` | `C_regressed_control_repair` | `SEEM` |
| `KNOW` | `0.333` | `0.231` | `C_regressed_control_repair` | `SEEM` |

Decision: `HELLO` and `KNOW` must not be silently promoted from the E5-B 50-class model. They need confusion-aware repair, smaller-batch validation, or specialist/routing evidence.

## Major Confusion Pairs

Top repeated confusion pairs:

- `KNOW -> SEEM`: `17`
- `HELLO -> SEEM`: `13`
- `BUY -> COOK`: `11`
- `FEEL -> GIVE`: `11`
- `CALL1 -> SLEEP`: `10`
- `SIT -> START`: `9`
- `TRY -> PLAY`: `9`
- `US -> TALK1`: `9`
- `WHAT1 -> WRITE`: `8`
- `MOVE -> CLOSE`: `8`
- `WE -> TAKE`: `8`

These groups should be repaired, deferred, or routed to specialists rather than hidden in a large primary classifier.

## Decision

Do not export or integrate the E5-B 50-class model.

Proceed to E5-D as a reduced-primary validation using the E5-C vocabulary hypothesis, plus the already proven routed `SORRY` specialist and the E4-AG no-sign gate in offline evaluation.

## Assumptions

- E5-B metrics are valid outputs from the completed 50-class run.
- The E5-C tier thresholds are diagnostic rules, not final production acceptance criteria.
- Reduced-primary validation is required because E5-B showed that aggregate 50-class learning can degrade previously stable signs.

## Risks

- The reduced vocabulary may still contain hidden confusion groups.
- Removing `HELLO` and `KNOW` may be unacceptable for product vocabulary, but keeping them without repair would create false translations.
- Some high-scoring signs may rely on ASL Citizen provenance and need later local/device validation.
- Specialist and router complexity can grow if many signs behave like `HELLO/KNOW -> SEEM`.

## Next Required Action

Prepare E5-D reduced-primary validation package. It should train/evaluate a smaller primary model on the E5-C candidate vocabulary, keep known hard signs excluded, and evaluate whether stable-control retention and per-class accuracy improve compared with E5-B. No Android/export is authorized.
