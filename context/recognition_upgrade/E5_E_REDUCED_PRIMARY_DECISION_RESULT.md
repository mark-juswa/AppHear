# E5-E Reduced Primary Decision Result

**Purpose:** Record the E5-E decision pass over E5-D and define the next reduced-primary routed simulation candidate.

**Scope:** Offline metrics-only decision result. This document does not authorize Android integration, TFLite export, production recognizer replacement, schema mutation, dataset mutation, or UI changes.

**Current status:** COMPLETE / DECISION PASS / E5-F NEXT.

**Last updated:** 2026-08-03.

## Verified Project References

- Runner: `pipeline/rgb/e5_e_reduced_primary_decision.py`
- Source run: `artifacts/recognition_upgrade/e5_batch_screening/e5_d_reduced_primary_15sign_01`
- E5-E run: `artifacts/recognition_upgrade/e5_batch_screening/e5_e_reduced_primary_decision_01`
- Summary: `artifacts/recognition_upgrade/e5_batch_screening/e5_e_reduced_primary_decision_01/reports/decision_summary.json`
- Report: `artifacts/recognition_upgrade/e5_batch_screening/e5_e_reduced_primary_decision_01/reports/decision_report.md`
- Class decisions: `artifacts/recognition_upgrade/e5_batch_screening/e5_e_reduced_primary_decision_01/tables/e5_e_latest_class_decisions.csv`
- Confusion groups: `artifacts/recognition_upgrade/e5_batch_screening/e5_e_reduced_primary_decision_01/tables/e5_e_confusion_groups.csv`
- Structural check: passed with `--require-summary`

## Result Summary

E5-E consumed the completed E5-D metrics and split the 15 reduced-primary signs into decision buckets.

Latest-policy aggregate from E5-D:

- Mean train accuracy: `0.9586`
- Mean validation accuracy: `0.7279`
- Mean test accuracy: `0.6933`
- Test range across seeds: `0.6687` to `0.7239`
- Mean max predicted-class share: `0.1207`, so no prediction collapse

Best-checkpoint aggregate from E5-D:

- Mean test accuracy: `0.7382`
- Test range across seeds: `0.7239` to `0.7607`

## Tiers

### A: Safe Primary Candidate

- `WASH2`
- `THINK`
- `TAKE`

### B: Guarded Primary Candidate

- `MEET`
- `GOOD`
- `SELL`
- `STAND2`
- `MORNING`
- `HAVE`
- `SLEEP`

### C: Confusion Group Or Repair

- `RUN2`
- `WANT2`
- `DRIVE`
- `WORK`
- `USE`

### D: Defer From Primary

- None from E5-D, but this does not mean every sign is release-ready.

## Recommended Next Primary Candidate

E5-E recommends the next offline primary subset:

`WASH2`, `THINK`, `TAKE`, `MEET`, `GOOD`, `SELL`, `STAND2`

This subset intentionally keeps only the strongest A signs plus the highest-value guarded B signs. `MORNING`, `HAVE`, and `SLEEP` remain useful evidence but should be held out of the first E5-F candidate unless a wider guarded-subset comparison is explicitly planned.

## Registered Confusion Groups

- `USE_WORK`: internal confusion `20`
- `DRIVE_HAVE`: internal confusion `13`
- `DRIVE_WANT2`: internal confusion `10`
- `MORNING_USE`: internal confusion `9`
- `TAKE_WORK`: internal confusion `9`
- `SLEEP_USE`: internal confusion `7`
- `RUN2_WASH2`: internal confusion `6`

These groups should not be solved by blindly adding all signs into the primary model. They require either exclusion, repair, or later specialist/routed handling.

## Decision

E5-D reduced-primary training is useful, but the 15-sign set is not exportable as-is. E5-E selects a smaller 7-sign primary candidate for the next routed-system simulation.

Recommended next experiment: E5-F offline routed simulation using:

`E4-AG no-sign gate -> E5-E 7-sign reduced primary candidate -> existing GOOD/SORRY specialist evidence where applicable -> reject/commit policy`

Weak E5-D signs must stay excluded, routed, or deferred during E5-F.

## Architecture Decisions

- Preserve the landmark-primary dynamic mixed architecture.
- Keep schema v3.0 `[96,258]` unchanged.
- Do not use aggregate 15-class accuracy as a production gate.
- Use the 7-sign E5-E subset as the next primary candidate, not the full E5-D vocabulary.
- Keep `HELLO`, `KNOW`, and `SORRY` outside this primary subset until their repair/routing path is explicitly validated.

## Assumptions

- Latest fixed-epoch metrics remain the conservative decision basis.
- Best-checkpoint metrics are tracked as supporting evidence but are not enough to authorize export.
- E5-F should be an offline simulation first, not Android implementation.

## Open Questions

- Does the 7-sign subset retain high precision when combined with the E4-AG no-sign gate?
- Should E5-F include `MORNING`, `HAVE`, or `SLEEP` as an alternate wider guarded subset, or keep the first simulation strict?
- Can `WORK/USE` or `DRIVE/WANT2/HAVE` be repaired by data/label cleanup, or do they need specialist routing?
- Does the existing GOOD/SORRY specialist remain compatible with the E5-E primary subset under a new routing policy?

## Risks

- Reducing to 7 signs improves safety but limits product vocabulary.
- Adding guarded signs too early may recreate E5-D's confusion pattern.
- Reusing the same test artifacts too often can overfit research decisions.
- Android export before routed/no-sign validation would create unsafe silent translations.

## Next Required Action

Prepare E5-F as an offline routed-system simulation package. Do not train a larger model, export TFLite, change Android, or replace production assets before E5-F is evaluated.
