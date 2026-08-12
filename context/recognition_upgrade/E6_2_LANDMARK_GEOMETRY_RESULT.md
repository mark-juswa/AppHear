# E6-2 Landmark Geometry Result

**Purpose:** Record the completed richer-landmark comparison and decide whether
`apphear.landmark_geometry.v0` can replace the frozen v3.0 control.

**Scope:** Offline five-sign diagnostic only. No Android assets, production behavior, source
datasets, rejection logic, RGB branch, specialist, export, or v3.0 contract changed.

**Current status:** COMPLETE / STRICT PROMOTION GATE NO-GO.

**Last updated:** 2026-08-09.

## Verified Run

- Run: `artifacts/recognition_upgrade/e6_landmark_geometry/e6_2_geometry_01`.
- Package check: passed with zero structural errors.
- Schema: experiment-only `[96,444]` `apphear.landmark_geometry.v0`.
- Control: frozen repaired-validation `[96,258]` broad-transfer TCN.
- Seeds: `101`, `202`, `303`.
- Primary checkpoint policy: latest.

The package-level `passed: true` reported by `check` means required artifacts and metrics are
complete. It does **not** mean the recognition promotion gate passed. The metrics decision is
`e6_2_geometry_no_go`.

## Aggregate Comparison

| Metric | Frozen v3.0 control | E6-2 geometry | Change | Gate |
|---|---:|---:|---:|---|
| Fresh AppHear top-1 | `0.8889` | `0.9456` | `+0.0567` | pass |
| Fresh `KNOW` recall | `0.5611` | `0.8611` | `+0.3000` | pass |
| Minimum-seed fresh `KNOW` | `0.5000` | `0.6833` | `+0.1833` | pass |
| Variant-stress top-1 | `0.6973` | `0.7219` | `+0.0246` | fail; required `0.7273` |
| Variant-stress `KNOW` | approximately `0.0222` | `0.0556` | approximately `+0.0334` | fail; required `0.30` |
| Historical top-1 | `0.9630` | `0.9630` | approximately `0.0000` | pass |
| Fresh seed standard deviation | `0.0063` | `0.0300` | less stable | pass at boundary |

Fresh mean recall:

- `GOOD 0.9833`
- `HELLO 0.9944`
- `SORRY 1.0000`
- `HAVE 0.8889`
- `KNOW 0.8611`

`HAVE` regressed from `0.9333` to `0.8889`, a `0.0444` loss, exceeding the allowed `0.03`.
Therefore the stable-class regression gate failed.

## Seed Behavior

| Seed | Fresh top-1 | Fresh `KNOW` | Fresh `HAVE` | Stress top-1 | Historical top-1 |
|---:|---:|---:|---:|---:|---:|
| 101 | `0.9833` | `0.9667` | `0.9667` | `0.7178` | `0.9841` |
| 202 | `0.9100` | `0.6833` | `0.9000` | `0.7239` | `0.9683` |
| 303 | `0.9433` | `0.9333` | `0.8000` | `0.7239` | `0.9365` |

Geometry improves the fresh signer substantially, but the benefit is seed-sensitive and trades
`KNOW` improvement against `HAVE` stability in seed 303.

## Variant-Stress Error Evidence

The stress set contains 30 `KNOW` rows. Latest-checkpoint predictions were:

- seed 101: `25 HELLO`, `2 GOOD`, `1 SORRY`, `1 HAVE`, `1 KNOW`;
- seed 202: `25 HELLO`, `1 SORRY`, `3 HAVE`, `1 KNOW`;
- seed 303: `25 HELLO`, `2 HAVE`, `3 KNOW`.

Thus `75/90` aggregate stress `KNOW` predictions were still `HELLO`. The richer geometry did not
resolve the established variant-specific confusion. Stress `SORRY` also remained confused mainly
with `HAVE`, with recall `0.45`, `0.55`, and `0.45` across seeds.

## Conclusions

### Verified project evidence

- Hand-local and head/body geometry contains useful information: fresh top-1 gained `5.67` points
  and fresh `KNOW` recall gained `30` points.
- That gain does not transfer to the preserved AppHear variant-stress signer.
- Historical performance is preserved on average.
- `HAVE` regresses beyond the preregistered tolerance.
- All eight primary gate checks did not pass; three failed.

### Engineering inference

- The stress `KNOW -> HELLO` failure is unlikely to be solved by another small handcrafted feature
  combination. Its consistency across all seeds is more compatible with sign-variant/domain
  mismatch or systematically different landmark evidence.
- Geometry may remain useful in a later evidence-routed specialist, but it is not reliable enough
  to replace the primary v3.0 contract.
- Repeating E3-style feature subsets would tune to already reused tests and violate the registered
  stop rule.

### Hypotheses still requiring experimentation

- Explicit open-set/class-conditioned rejection may prevent unsafe commits even when the primary
  classifier cannot resolve a variant.
- A later registered confusion specialist may need richer landmarks, RGB, or variant-specific
  data, but only after E6-3 rejection and E6-4 registry gates.

## Decision

**Do not promote `[96,444]`. Keep production and the next primary control on v3.0 `[96,258]`.**

Do not run another geometry subset, change the gate, select seed 101 as a production shortcut,
export E6-2, or port it to Android. Preserve this run as positive representation evidence for a
future justified specialist comparison.

The next planned phase is E6-3 architecture and duplicate review against E4-T, E5-H, and E5-I.
E6-3 must use the frozen v3.0 primary control and the existing negative/OOV evidence. It must not
be implemented until its rejection methods, data limitations, metrics, and stop conditions are
specified. E6-4+ remain blocked.

## Risks

- Fresh and historical test views have already influenced multiple decisions.
- The fresh AppHear test has limited signer diversity.
- The negative/OOV package has limited fresh-signer diversity, constraining future E6-3 claims.
- Choosing the strongest seed would hide real training variance.

## Source-Of-Truth Files

- `artifacts/recognition_upgrade/e6_landmark_geometry/e6_2_geometry_01/metrics/metrics.json`
- `artifacts/recognition_upgrade/e6_landmark_geometry/e6_2_geometry_01/check_report.json`
- `E6_2_RICHER_LANDMARK_CONTROL_PLAN.md`
- `E6_2_LANDMARK_GEOMETRY_PACKAGE.md`
- `product_core_data_readiness/collection_targets_v1/E6_V30_REPAIRED_VALIDATION_TRANSFER_RESULT.md`

## Related Context Files

- `README.md`
- `FEATURE_SCHEMA_PLAN.md`
- `EXPERIMENT_MATRIX.md`
- `E6_PRODUCTION_RECOGNITION_ARCHITECTURE_PLAN.md`
- `EVALUATION_AND_ACCEPTANCE_GATES.md`
- `ROLLBACK_AND_COMPATIBILITY_PLAN.md`
- `RISK_REGISTER.md`
- `OPEN_QUESTIONS.md`

## Architecture Decisions

- Retain v3.0 as primary.
- Preserve E6-2 as diagnostic evidence, not a deployable model.
- Stop handcrafted richer-landmark iteration.
- Architect E6-3 independently before implementation.

## Assumptions And Open Questions

- Is the stress `KNOW` performance a compatible label variant?
- Can E6-3 reject this failure without destroying coverage for valid low-motion signs?
- What additional negative signer diversity is required before a production rejection claim?

## Next Required Action

Architect E6-3 open-set/rejection comparison with a strict duplicate audit against E4-T, E5-H,
and E5-I. Do not train or implement E6-3 until that contract is reviewed.
