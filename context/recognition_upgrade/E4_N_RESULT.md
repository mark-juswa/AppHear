# E4-N Dual-Source 5-Sign Training Screen Result

**Purpose:** Record the completed E4-N result and its effect on the next recognition-upgrade step.

**Scope:** Offline experiment result only. This does not authorize Android integration, TFLite export, production recognizer replacement, or larger vocabulary training.

**Current status:** COMPLETE / GATE PASS / NEXT EXTRACTION SCREEN APPROVED.

**Last updated:** 2026-07-30.

## Verified Artifacts

- Runner: `pipeline/rgb/e4_n_dual_source_5sign.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_n_dual_source_5sign_screen_01`.
- Metrics: `artifacts/recognition_upgrade/e4_generalization/e4_n_dual_source_5sign_screen_01/metrics/metrics.json`.
- Summary: `artifacts/recognition_upgrade/e4_generalization/e4_n_dual_source_5sign_screen_01/metrics/metrics.md`.
- Final check: passed with `--require-full-dataset --require-metrics`.

## Result Summary

Classes tested: `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`.

Latest/fixed Conv1D policy across seeds passed the registered gate:

- Mean latest test accuracy: `0.9774`.
- Minimum core-class latest test accuracy: `0.9667`.
- Minimum candidate-class latest test accuracy: `0.9286`.
- Gate passed: `true`.
- Decision: `eligible_for_get_welcome2_extraction_screen`.

Per-class latest test behavior was stable:

- `GOOD`: `30/30`.
- `HELLO`: `29/30`.
- `SORRY`: `29-30/30` depending on seed.
- `HAVE`: `14/14`.
- `KNOW`: `13/14`.

## Checkpoint Policy Finding

The latest/fixed checkpoint remains the safer policy. Seed `101` best-validation checkpoint regressed `SORRY` to `16/30`, while the latest checkpoint reached `30/30` for `SORRY`. This confirms the E4-K decision that best-validation checkpoints can be misleading on tiny validation sets.

## Source-Aware Finding

ASL Citizen candidate test rows were strong across seeds:

- `HAVE`: `10/10`.
- `KNOW`: `13/13`.

Local recorded candidate test rows were mixed:

- `HAVE`: `4/4`.
- `KNOW`: `0/1`.

The local `KNOW` failure is not enough to reject the class because there was only one local held-out row. It remains a diagnostic limitation, not production evidence.

## Decision

E4-N passed as a bounded expansion-method gate. The project may proceed to an extraction screen for `GET` and `WELCOME2`, because those were the E4-M candidates with enough validated raw/local support but insufficient existing local feature tensors.

This does not mean AppHear is production-ready. It means the source-aware expansion method is now credible enough to test the next small queued extraction batch before moving to a larger automated 20-50 sign batch.

## Next Required Action

Prepare E4-O as an experiment-only package that:

- Reuses E4-N `GOOD`/`HELLO`/`SORRY`/`HAVE`/`KNOW` data.
- Adds ASL Citizen existing features for `GET` and `WELCOME2`.
- Extracts local validated videos for `GET` and `WELCOME2` only.
- Trains the 7-sign screen after extraction.
- Reports source-aware metrics.

Do not start Android integration, production export, RGB fusion, or larger vocabulary training until E4-O is evaluated.