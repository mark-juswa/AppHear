# E4-L MAKE Expansion Result And Dual-Source Screening Pivot

**Purpose:** Record the completed E4-L one-sign expansion result and the resulting change in next-step strategy.

**Scope:** Offline recognition-upgrade experiment only. This document does not authorize Android integration, model export, production recognizer replacement, or dataset relabeling.

**Current status:** Complete; gate failed; do not expand with `MAKE`.

**Last updated:** 2026-07-30.

## Verified Project References

- Runner: `pipeline/rgb/e4_l_one_sign_expansion.py`
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_l_make_expansion_pilot_01`
- Metrics: `artifacts/recognition_upgrade/e4_generalization/e4_l_make_expansion_pilot_01/metrics/metrics.json`
- Metrics summary: `artifacts/recognition_upgrade/e4_generalization/e4_l_make_expansion_pilot_01/metrics/metrics.md`
- Extraction summary: `artifacts/recognition_upgrade/e4_generalization/e4_l_make_expansion_pilot_01/logs/candidate_feature_extraction_summary.json`
- Package plan: `context/recognition_upgrade/E4_L_ONE_SIGN_EXPANSION_PACKAGE.md`
- Source context: `context/recognition_upgrade/E4_J_RELIABLE_CORE_RESULT.md`, `context/recognition_upgrade/E4_K_CHECKPOINT_POLICY_RESULT.md`

## Result Summary

E4-L tested whether the reliable local 3-sign core could safely expand from `GOOD`/`HELLO`/`SORRY` to `GOOD`/`HELLO`/`SORRY`/`MAKE` using the E4-K policy: `conv1d_baseline`, latest/fixed-epoch checkpoint, seeds `101`, `202`, and `303`.

Extraction completed successfully:

- Candidate rows attempted: `70`
- Candidate rows ok or cached: `70`
- Failed candidate rows: `0`
- Assembled dataset rows: `260`
- Tensor shape: `[260,96,258]`
- Split counts: train `105`, validation `35`, test `120`

Latest-policy test result:

| Seed | Test Accuracy | Worst Class | MAKE Test |
|---:|---:|---:|---:|
| 101 | 0.7750 | 0.2000 | 0.2000 |
| 202 | 0.7417 | 0.0333 | 0.0333 |
| 303 | 0.8000 | 0.2667 | 0.2667 |

Aggregate:

- Mean test accuracy: `0.7722`
- Minimum seed test accuracy: `0.7417`
- Minimum class test accuracy: `0.0333`
- Minimum `MAKE` test accuracy: `0.0333`
- Gate passed: `false`
- Decision: `no_go_do_not_expand`

## Interpretation

This was not a package failure. The final check passed and the full dataset was assembled. The failure is a held-out signer/generalization failure.

The model learned train and validation `MAKE` perfectly, but held-out `MAKE` collapsed. In the latest checkpoints, `MAKE` was mostly predicted as `GOOD` on the held-out signer. This shows that selecting one visually plausible candidate is not enough; candidate eligibility needs source-aware and signer-aware screening before training larger vocabularies.

## Architecture Decisions

- Keep the current reliable local core at `GOOD`, `HELLO`, and `SORRY`.
- Reject `MAKE` for the next reliable vocabulary expansion.
- Stop using manual one-word expansion as the main path.
- Move next to automated dual-source candidate screening using both ASL Citizen and local supplementary data.
- Preserve source/provenance separation; do not blindly merge public and local datasets.
- Do not promote E4-L models to Android or production.

## Assumptions

- The E4-L metrics reflect the completed user run reported on 2026-07-30.
- `F:\ASL DATASET\ASL CITIZEN` remains the ASL Citizen source root.
- Local supplementary data may exist under `E:\local`, `F:\ASL DATASET\local`, or both; this must be verified before the next package is built.

## Open Questions

- Which ASL Citizen derived artifacts are reliable enough to reuse for dual-source screening?
- Which local supplementary root is authoritative if duplicate local datasets exist?
- Should the first dual-source screen restrict to overlapping labels or rank overlapping and source-specific signs separately?
- What minimum signer count per source should be required for a sign to be called reliable instead of diagnostic?

## Risks

- ASL Citizen and local labels may represent different variants under the same English gloss.
- The model may learn dataset provenance instead of sign semantics if sources are merged without source-aware splits.
- A CPU-only batch candidate screen can become slow if too many candidates are trained naively.
- Quality metrics like hand-hit rate can identify some bad samples but cannot prove semantic label correctness.

## Next Required Action

Architect and prepare a dual-source candidate screening package. It should inspect ASL Citizen and local supplementary inventories, choose eligible candidate signs, run bounded source-aware evaluations, and output a ranked keep/reject/needs-review table before any larger hybrid or Android work resumes.

## Related Context Files

- `context/recognition_upgrade/README.md`
- `context/recognition_upgrade/EXPERIMENT_MATRIX.md`
- `context/recognition_upgrade/DATASET_UPGRADE_PLAN.md`
- `context/recognition_upgrade/E4_J_RELIABLE_CORE_RESULT.md`
- `context/recognition_upgrade/E4_K_CHECKPOINT_POLICY_RESULT.md`
- `context/progress-tracker.md`
