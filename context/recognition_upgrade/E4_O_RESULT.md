# E4-O GET/WELCOME2 7-Sign Expansion Result

**Purpose:** Record the completed E4-O result and explain why `GET`/`WELCOME2` are not promoted into the next batch.

**Scope:** Offline extraction/training result only. No Android integration, TFLite export, production recognizer replacement, source videos, or source datasets were modified.

**Current status:** COMPLETE / STRUCTURAL PASS / ACCURACY GATE FAIL.

**Last updated:** 2026-07-31.

## Verified Artifacts

- Runner: `pipeline/rgb/e4_o_get_welcome2_expansion.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_o_get_welcome2_7sign_screen_01`.
- Metrics: `artifacts/recognition_upgrade/e4_generalization/e4_o_get_welcome2_7sign_screen_01/metrics/metrics.json`.
- Summary: `artifacts/recognition_upgrade/e4_generalization/e4_o_get_welcome2_7sign_screen_01/metrics/metrics.md`.
- Extraction summary: `artifacts/recognition_upgrade/e4_generalization/e4_o_get_welcome2_7sign_screen_01/logs/candidate_feature_extraction_summary.json`.

## Result Summary

E4-O completed extraction and training successfully, but failed the recognition gate.

- Classes: `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`, `GET`, `WELCOME2`.
- Full dataset shape: `[468,96,258]`.
- Split counts: train `221`, validation `45`, test `202`.
- Local candidate extraction: `140/140` ok or cached, `0` failed.
- Mean latest test accuracy: `0.7822` against required `0.80`.
- Minimum core latest test accuracy: `0.7000` against required `0.90`.
- Minimum candidate latest test accuracy: `0.2619` against required `0.60`.
- Gate passed: `false`.
- Decision: `no_export_no_android_integration`.

## Failure Pattern

The dominant failure is local extracted `GET`.

- Seed `101`: overall `GET` test `22/42`; local extracted `GET` `10/30`.
- Seed `202`: overall `GET` test `11/42`; local extracted `GET` `2/30`.
- Seed `303`: overall `GET` test `13/42`; local extracted `GET` `1/30`.

Most failed local `GET` rows are predicted as `GOOD`. `WELCOME2` performs better, but bundling it with unstable `GET` is not safe.

ASL Citizen `GET/WELCOME2` rows perform much better than local extracted `GET`, so the failure is likely source/provenance mismatch, local variant mismatch, or insufficient landmark-only separability for local `GET`, not a generic inability to learn the gloss.

## Decision

- Do not export or integrate E4-O.
- Quarantine `GET` from the next batch.
- Do not promote `WELCOME2` with `GET`; retest separately only if needed.
- Proceed to a larger existing-feature pressure test that excludes known unstable/rejected signs.

## Next Required Action

Prepare E4-P as a no-extraction 20-sign pressure test using already-extracted ASL Citizen and local supplementary feature tensors. E4-P should answer whether the current landmark-only pipeline can scale beyond the tiny proven core before spending more time on extraction or Android work.
