# E6-4 Frozen Confusion Registry Mining Plan

**Purpose:** Determine which supported-sign confusion pairs are reproducible enough to justify a
future data-repair or specialist experiment, using frozen E6 models and existing tensors only.

**Scope:** Offline inference and evidence mining only. No extraction, model training, rejection
method, threshold routing, specialist, RGB, export, Android change, or production migration.

**Current status:** ARCHITECTURE REVIEW COMPLETE / PACKAGE IMPLEMENTATION AUTHORIZED.

**Last updated:** 2026-08-09.

## Exact Question

Which directed errors, such as `KNOW -> HELLO`, recur across seeds, signer groups, and evaluation
views rather than appearing because of one checkpoint, one signer, or one reused split?

E6-4 does not decide how to solve a group. It decides whether a group is real enough to deserve a
later bounded intervention.

## Verified Project Evidence

- E4-T registered `SORRY -> GOOD` after all three E4-S seeds made high-confidence errors, but its
  evidence came from one historical bounded setup.
- E4-U prepared manual evidence for that one group; it did not mine all five-sign E6 predictions.
- E5-E listed confusion counts from a 15-sign run, but that run had mean test accuracy `0.6933` and
  did not require cross-view/signer reproducibility.
- E6 v3.0 has fresh `KNOW` recall `0.5611` and variant-stress `KNOW` approximately `0.0222`.
- E6-2 geometry left `75/90` stress `KNOW` predictions as `HELLO`, despite improving the fresh
  signer.
- E6-3 proved that no scalar rejection score can safely protect the primary classifier at useful
  coverage.

## Duplicate Audit

| E6-4 element | Closest prior work | Similarity | Meaningful difference | Decision |
|---|---|---:|---|---|
| Supported-pair mining | E5-E confusion table | `65%` | repaired five-sign lineage, per-sample three-seed consensus, signer/view requirements | proceed |
| Known-group evidence bundle | E4-U | `55%` | automatic all-pair discovery before selecting a group; no panels/manual review | proceed |
| Confidence/margin routing | E4-T, E5-H | `95%` | none relevant | skip |
| Rejection scoring | E5-I, E6-3 | `100%` | none relevant | skip |
| Specialist training | E4-Q, E4-V | `100%` as intervention | E6-4 is discovery only | blocked until E6-5 |
| Geometry-model promotion | E6-2 | `100%` | already failed | use only as corroborating evidence |

## Frozen Inputs

### Primary evidence

- v3.0 repaired-validation latest checkpoints, seeds `101`, `202`, `303`;
- v3.0 `[96,258]` tensors for `val`, `validation_variant_stress`, `test_fresh`, and
  `test_historical`;
- class order `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`;
- sample IDs, source IDs, and signer/participant IDs from each NPZ.

### Corroborating evidence

- E6-2 `[96,444]` latest checkpoints and matched tensors for the same seeds/views;
- E6-3 negative windows and frozen v3.0 predictions, used only to report which supported labels
  attract each negative subtype.

E6-2 cannot register a group by itself because it failed promotion. Negative attraction cannot be
treated as a supported-sign confusion group.

## Required Outputs

- `predictions/positive_predictions.csv`: every sample/family/seed/view prediction;
- `predictions/negative_predictions.csv`: every negative/seed prediction and subtype;
- `tables/directed_confusions.csv`: per family/view/seed true-to-predicted counts and rates;
- `tables/consensus_confusions.csv`: majority/unanimous error evidence per directed pair/view;
- `tables/negative_attraction.csv`: predicted-label distribution by negative subtype/role/seed;
- `tables/confusion_registry.csv`: only pairs that meet the preregistered registry rule;
- `reports/registry_summary.json` and `reports/registry_report.md`;
- `check_report.json`.

## Registry Rule

A directed pair `A -> B` becomes `registered_provisional` only when all are true on the frozen
v3.0 primary:

1. `A != B`;
2. majority-of-three seeds predicts `B` for at least `20%` of true `A` samples in at least two of
   `validation_variant_stress`, `test_fresh`, and `test_historical`;
3. at least `10` distinct samples support the pair across qualifying views;
4. confused samples span at least two source-scoped signer IDs;
5. every seed produces at least one `A -> B` error across qualifying views;
6. no sample ID or signer appears in incompatible repaired roles.

Evidence statuses below this bar:

- `single_domain_strong`: majority rate `>=0.50` in one view and the geometry family shows the same
  direction there, but the pair lacks a second qualifying v3.0 view;
- `monitor`: majority rate `>=0.10` in one view or at least five supporting samples;
- `not_reproducible`: all weaker pairs; omitted from the registry table but retained in evidence.

The `val` view is reported but cannot qualify a pair because it selected the checkpoint.

## Gate

E6-4 passes as an evidence phase when:

- every required prediction and table is complete;
- row counts, class order, sample IDs, signer IDs, and view assignments match source tensors;
- registry decisions are reproduced mechanically from the rule above;
- no pair is registered from validation, geometry, negatives, confidence, or prior narrative alone;
- every registered pair includes exact supporting sample IDs and signer/view counts.

E6-4 may legitimately produce zero registered groups. That is a valid no-specialist result, not a
reason to lower thresholds.

## Failure Paths

- If no pair qualifies, stop specialist work and return to data/variant collection for unstable
  signs.
- If a pair is one-view or one-signer only, keep it diagnostic and do not build a specialist.
- If v3.0 and geometry disagree strongly, preserve both results; do not select the model that makes
  the desired story.
- If lineage fields are missing, repair the source tensor metadata before mining.
- Do not merge multiple pairs into a large specialist automatically.

## Negative Evidence Boundary

E6-4 reports negative attraction to support future architecture, but E6-3 already closed
single-score rejection. A pattern such as face-adjacent windows attracting `HELLO` does not create a
`FACE_ADJACENT/HELLO` specialist. It may later justify a separately preregistered temporal gate or
negative-context component only after E6-5/E6-6 architecture review.

## Protected Baseline

Do not modify schema v3.0, E6 checkpoints, E6 tensors, E6-2 artifacts, E6-3 artifacts, raw videos,
or any Android/production asset. E6-4 writes only under its own run directory.

## Source-Of-Truth Files

- `E6_2_LANDMARK_GEOMETRY_RESULT.md`
- `E6_3_OPEN_SET_REJECTION_RESULT.md`
- `E4_R_STABLE_CANDIDATE_TIERING_RESULT.md`
- `E4_T_ROUTER_SIMULATION_RESULT.md`
- `E4_U_CONFUSION_EVIDENCE_PACKAGE.md`
- `E5_E_REDUCED_PRIMARY_DECISION_RESULT.md`
- repaired v3.0 and E6-2 tensor/model directories named above.

## Related Context Files

- `README.md`
- `E6_PRODUCTION_RECOGNITION_ARCHITECTURE_PLAN.md`
- `EXPERIMENT_MATRIX.md`
- `EVALUATION_AND_ACCEPTANCE_GATES.md`
- `RISK_REGISTER.md`
- `ROLLBACK_AND_COMPATIBILITY_PLAN.md`

## Architecture Decisions

- Mine errors before designing a specialist.
- Use v3.0 as primary evidence and geometry only as corroboration.
- Require cross-view, cross-signer, and all-seed evidence.
- Keep negative attraction separate from supported-sign confusion groups.
- Do not make routing or intervention decisions in E6-4.

## Assumptions And Open Questions

- Source-scoped participant IDs represent distinct signer groups within each source.
- It is unknown whether `KNOW -> HELLO` qualifies across two v3.0 views or only the stress signer.
- It is unknown whether another pair meets the same evidence bar.

## Next Required Action

Implement and execute the frozen E6-4 evidence package. It is a short inference/reporting run and
must not train, extract, or modify production assets.
