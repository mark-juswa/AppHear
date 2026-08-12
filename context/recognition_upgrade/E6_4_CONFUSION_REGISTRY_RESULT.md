# E6-4 Frozen Confusion Registry Result

**Purpose:** Record which supported-sign confusions are reproducible across frozen seeds, views,
and signer groups, and define the evidence boundary for E6-5.

**Scope:** Offline inference and reporting only. No extraction, training, rejection, specialist,
RGB, export, Android change, or production migration occurred.

**Current status:** COMPLETE / EVIDENCE GATE PASS / ONE PROVISIONAL GROUP REGISTERED.

**Last updated:** 2026-08-09.

## Verified Run

- Run: `artifacts/recognition_upgrade/e6_registry/e6_4_confusion_registry_01`.
- Frozen families: v3.0 primary and E6-2 geometry corroboration.
- Seeds: `101`, `202`, `303`.
- Positive prediction rows: `4,152`.
- Negative prediction rows: `3,321`.
- Positive consensus rows: `1,384`.
- Split counts: train `535`, validation `166`, stress `163`, fresh `300`, historical `63`.
- Sample overlap across roles: `0`.
- Signer overlap across roles: `0`.
- Structural check: pass.

## Registered Provisional Group

### `KNOW -> HELLO`

- qualifying v3.0 views: `test_fresh` and `validation_variant_stress`;
- strongest majority confusion rate: `0.8667`;
- fresh majority confusion: `28/60` (`0.4667`);
- stress majority confusion: `26/30` (`0.8667`);
- distinct majority-confused samples: `54`;
- source-scoped signer groups: `2`;
- signers: `local_recorder:87AF81-S001` and `local_recorder:8A128E-S001`;
- seed error counts across qualifying views: seed 101 `48`, seed 202 `58`, seed 303 `50`;
- E6-2 geometry corroboration: stress view, `24/30` majority `KNOW -> HELLO` (`0.80`).

This pair meets every preregistered rule: at least 20% in two diagnostic views, at least ten
samples, at least two signer groups, and at least one error in every seed.

It remains **provisional**, not production-proven, because both qualifying signers are from the
local/AppHear domain and historical ASL Citizen `KNOW` remains much stronger.

## Strong But Unregistered Evidence

### `SORRY -> HAVE`

- stress majority confusion: `13/20` (`0.65`);
- geometry stress corroboration: `11/20` (`0.55`);
- qualifying views: one;
- supporting signer groups: one.

Status: `single_domain_strong`. It does not meet the cross-view or cross-signer registry rule and
must not receive an E6-5 specialist yet.

No other directed supported pair reached monitor or registry status under the fixed rule.

## Negative Attraction Evidence

This is not part of the supported-sign registry, but it explains E6-3 overlap:

- fresh idle hands were predicted `HELLO` for `60/60` rows in seeds 202 and 303;
- fresh face-adjacent activity was predicted `KNOW` for `59/60`, `60/60`, and `48/60` across the
  three seeds;
- fresh transition/partial windows were frequently predicted `HELLO`;
- historical N0 no-hand windows were mostly attracted to `HELLO` in seeds 101 and 202;
- fresh OOV signs were frequently attracted to `GOOD` in seed 303.

These patterns confirm that no-sign/OOV pressure is class- and subtype-dependent. They do not
authorize a negative-context specialist or a post-hoc combination of E4-AG and E6-3.

## Conclusions

### Verified project evidence

- `KNOW -> HELLO` is not a one-seed accident or one-signer-only failure.
- The direction recurs in two AppHear signer groups and all three v3.0 seeds.
- E6-2 geometry does not resolve the hardest stress form and corroborates the pair there.
- `SORRY -> HAVE` is severe but still signer/domain-specific under current evidence.
- The previous E4/E5 practice of listing raw confusion counts would have over-promoted the
  `SORRY -> HAVE` case; the E6-4 rule correctly keeps it diagnostic.

### Engineering inference

- `KNOW/HELLO` is the only justified first E6-5 intervention group.
- Its source pattern suggests signer/variant/domain generalization is at least as important as
  model capacity.
- A future specialist must be evaluated on both local difficult signers and historical ASL
  evidence so it cannot fix one domain by damaging another.

### Hypotheses requiring experimentation

- A binary group resolver may separate `KNOW` from `HELLO` better than the five-way primary head.
- E6-2 geometry may be useful inside that bounded resolver despite failing as a global schema.
- RGB upper-body/hand evidence may distinguish temple index-hand placement from the open greeting
  hand, but prior RGB experiments do not prove this on the registered E6 group.

## Decision

Register one provisional supported confusion group:

`KNOW/HELLO`, triggered by the directed primary failure `KNOW -> HELLO`.

Do not register `SORRY/HAVE`, alter the primary vocabulary, implement routing, or modify Android.
E6-4 authorizes architecture review for one E6-5 `KNOW/HELLO` specialist comparison only.

## Source-Of-Truth Files

- `artifacts/recognition_upgrade/e6_registry/e6_4_confusion_registry_01/reports/registry_summary.json`
- `artifacts/recognition_upgrade/e6_registry/e6_4_confusion_registry_01/reports/registry_report.md`
- `artifacts/recognition_upgrade/e6_registry/e6_4_confusion_registry_01/tables/confusion_registry.csv`
- `artifacts/recognition_upgrade/e6_registry/e6_4_confusion_registry_01/tables/pair_decisions.csv`
- `artifacts/recognition_upgrade/e6_registry/e6_4_confusion_registry_01/tables/negative_attraction.csv`
- `artifacts/recognition_upgrade/e6_registry/e6_4_confusion_registry_01/predictions/`
- `E6_4_CONFUSION_REGISTRY_PLAN.md`

## Related Context Files

- `E6_2_LANDMARK_GEOMETRY_RESULT.md`
- `E6_3_OPEN_SET_REJECTION_RESULT.md`
- `E4_U_CONFUSION_EVIDENCE_PACKAGE.md`
- `E5_E_REDUCED_PRIMARY_DECISION_RESULT.md`
- `E6_PRODUCTION_RECOGNITION_ARCHITECTURE_PLAN.md`
- `EXPERIMENT_MATRIX.md`
- `RISK_REGISTER.md`

## Architecture Decisions

- Use `KNOW/HELLO` as the sole first E6-5 candidate group.
- Preserve `SORRY/HAVE` as diagnostic evidence only.
- Keep v3.0 as primary and E6-2 geometry as specialist-only candidate evidence.
- Keep negative attraction separate from the supported-sign registry.
- Require E6-5 architecture and duplicate review before any specialist implementation.

## Assumptions And Open Questions

- The two local recorder IDs represent distinct human signers.
- It remains unknown whether the local `KNOW` variant is sufficiently represented in specialist
  training without contaminating evaluation.
- The exact E6-5 RGB crop source and signer-disjoint split must be verified before training.

## Next Required Action

Architect and duplicate-audit one E6-5 `KNOW/HELLO` specialist proof against E4-Q, E4-V, E6-2,
and prior RGB/fusion failures. Do not implement it until its data roles, controls, and gates are
fixed.
