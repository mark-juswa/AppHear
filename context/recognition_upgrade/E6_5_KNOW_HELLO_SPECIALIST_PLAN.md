# E6-5 KNOW/HELLO Specialist Plan

**Purpose:** Test the smallest evidence-supported specialist for the only E6-4 registered
confusion group, `KNOW -> HELLO`.

**Scope:** Offline preparation, training, and evaluation only. This plan does not authorize RGB
extraction, fusion, routing integration, TFLite export, Android changes, production-model
replacement, raw-data mutation, or a new production feature schema.

**Current status:** COMPLETE / RESULT NO-GO. See `E6_5_KNOW_HELLO_SPECIALIST_RESULT.md`.

**Last updated:** 2026-08-09.

## Evidence And Duplicate Audit

| Closest experiment | Similarity | Verified result | Material E6-5 difference | Decision |
|---|---:|---|---|---|
| E4-V `GOOD/SORRY` binary specialist | 65% | v3 landmark binary reached `0.9667`; upper-body RGB was unstable (`0.7833` mean, `0.50` minimum) | E6-5 uses the E6 repaired dataset, the registered `KNOW/HELLO` group, the production-style TCN, seed-matched warm starts, and fresh/stress/historical views | Extend the landmark specialist pattern; do not repeat RGB |
| E4-Q four-class resolver | 45% | v3 and `[96,728]` resolvers failed; `SORRY` remained weak | E6-5 is binary, uses a registry-proven pair, excludes the exhausted `[96,728]` motion representation, and preserves source-aware views | Proceed with modified method |
| E6-2 `[96,444]` global geometry | 55% | fresh `KNOW` improved, but stress `KNOW` remained `0.0556`; global replacement failed | Geometry is tested only as a binary specialist and must beat the simpler v3 specialist | Proceed as one bounded comparator |
| E3-B3 / E3-C RGB fusion | 25% | RGB overfit and fusion degraded landmarks | No RGB or fusion branch in this stage | Skip |
| E6-4 registry | 100% prerequisite | only `KNOW -> HELLO` met the fixed cross-view/cross-seed rule | E6-5 consumes the frozen registry; it does not mine another group | Proceed |

## Fixed Question

Can a binary temporal specialist separate `HELLO` and `KNOW` on the difficult held-out AppHear
signers without damaging historical ASL Citizen behavior?

This is not a general vocabulary model and not evidence that routing or open-set rejection works.

## Data Contract

- Classes: `HELLO=0`, `KNOW=1` inside specialist artifacts only.
- Source tensors remain immutable:
  - v3.0: `artifacts/recognition_upgrade/e6_baseline/e6_v30_validation_repair_01/dataset/features`
  - geometry: `artifacts/recognition_upgrade/e6_landmark_geometry/e6_2_geometry_01/dataset/features`
- Roles are preserved exactly: `train`, `val`, `validation_variant_stress`, `test_fresh`, and
  `test_historical`.
- No sample or signer may move between roles.
- `test_fresh` and `validation_variant_stress` remain evaluation-only. Their prior use makes this
  a diagnostic promotion result, not a final production claim.
- Every derived row retains `sample_ids`, `participant_ids`, `source_ids`, `lengths`, masks, and
  the original five-class label.

Verified pair inventory before filtering:

| View | HELLO | KNOW | Signer/domain role |
|---|---:|---:|---|
| Train | 163 | 90 | ASL Citizen plus local/AppHear development signers |
| Validation | 34 | 31 | repaired signer-disjoint validation |
| Variant stress | 60 | 30 | one held-out AppHear signer |
| Fresh test | 60 | 60 | one held-out AppHear signer |
| Historical test | 14 | 13 | eleven ASL Citizen test signers across the five-sign set |

## Branches

1. **Frozen five-way primary control:** no training. Measure the current v3.0 primary on pair
   rows and its pair-restricted decision (`HELLO` versus `KNOW`). This distinguishes head
   competition from representational failure.
2. **v3 TCN specialist:** `[96,258]`, two-class production-style TCN, initialized from the
   matching seed of the repaired five-sign v3.0 primary. A new two-class head is trained.
3. **Geometry TCN specialist:** `[96,444]`, same two-class TCN and matching seed initialization
   from E6-2. This is specialist-only evidence; it cannot promote the geometry schema globally.

No class weighting is introduced. E4-Q did not justify it, and changing both representation and
loss weighting would confound the result.

## Metrics And Gates

The fixed policy uses each seed's `latest.keras`; `best` and `final` are diagnostic only.

A specialist branch passes only if all conditions hold:

- mean fresh pair accuracy `>=0.90` and minimum-seed fresh pair accuracy `>=0.85`;
- mean fresh recall for both `HELLO` and `KNOW` `>=0.85`, minimum-seed recall `>=0.75`;
- mean stress pair accuracy `>=0.85`;
- mean stress `HELLO` recall `>=0.95` and `KNOW` recall `>=0.70`;
- mean historical pair accuracy `>=0.90` and historical `KNOW` recall `>=0.80`;
- mean fresh gain over the frozen five-way primary `>=0.10`;
- mean stress gain over the frozen five-way primary `>=0.15`;
- fresh pair accuracy standard deviation across seeds `<=0.05`.

If both specialists pass, v3 remains preferred unless geometry improves the minimum of fresh,
stress, and historical pair accuracy by at least `0.03` without more than `0.03` historical
regression. This is the complexity gate.

## Failure Paths

- If neither specialist passes: do not add RGB automatically. Classify the pair as a data/variant
  generalization failure and obtain new independent `KNOW` signers or defer `KNOW`.
- If v3 passes and geometry does not materially beat it: retain v3 for the future specialist.
- If only geometry passes: preserve it as an offline candidate and require a new feature-parity and
  Android-cost plan before any routed simulation.
- If a branch passes only on already-inspected AppHear views but fails historical data: reject it as
  domain repair rather than generalization.
- If any split/hash/shape/lineage check fails: stop before training.

## Protection And Rollback

- All outputs live under
  `artifacts/recognition_upgrade/e6_specialists/e6_5_know_hello_specialist_01`.
- Source NPZs and source checkpoints are read-only and hashed during preparation.
- The current Android assets, `[96,258]` production contract, confirmation logic, and sentence/UI
  remain untouched.
- Deleting the E6-5 output directory fully removes the experiment; no working behavior depends on
  it.

## Source-Of-Truth Files

- `E6_4_CONFUSION_REGISTRY_RESULT.md`
- `E6_2_LANDMARK_GEOMETRY_RESULT.md`
- `E4_Q_RESULT.md`
- `E4_V_SORRY_GOOD_SPECIALIST_RESULT.md`
- `E3_B3_RESULT.md`
- `E3_C_RESULT.md`
- `E6_PRODUCTION_RECOGNITION_ARCHITECTURE_PLAN.md`
- `context/feature-schema.md`
- `context/eval-protocol.md`

## Architecture Decisions

- E6-5 is one group, two landmark representations, and no RGB.
- A binary specialist is per confusion group, not per word.
- Training and evaluation remain offline; routing is deferred to E6-6.
- No result from reused diagnostic test views can be called production-ready.

## Assumptions And Open Questions

- **Assumption requiring validation:** source-scoped participant IDs correspond to distinct people.
- **Unknown:** whether existing development signers contain enough compatible `KNOW` variation to
  generalize to both difficult AppHear signers.
- **Unknown:** whether the five-way failure is mainly head competition; the pair-restricted frozen
  control measures this directly.
- **Risk:** the local training inventory is concentrated in a few recorder identities and may still
  encode signer/source shortcuts.

## Next Required Action

E6-5 is complete. Follow `E6_COMPONENT_DECISION.md`; do not repeat the specialist or start E6-6.
