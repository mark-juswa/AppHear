# E4-T Offline Router Simulation Result

**Purpose:** Record whether simple confidence/margin routing can safely accept E4-S stable primary signs while rejecting the withheld `SORRY` confusion/OOV holdout.
**Scope:** Offline window-level simulation only. No Android integration, TFLite export, production recognizer replacement, model retraining, or specialist resolver implementation is authorized.
**Current status:** COMPLETE / STRUCTURAL CHECK PASSED / SIMPLE THRESHOLD ROUTER NO-GO.
**Last updated:** 2026-08-02.

## Verified Project References

- Runner: `pipeline/rgb/e4_t_router_simulation.py`
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_t_router_simulation_01`
- Source run: `artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01`
- Source package: `context/recognition_upgrade/E4_S_STABLE_PRIMARY_PACKAGE.md`
- Roadmap: `context/recognition_upgrade/DYNAMIC_MIXED_RECOGNITION_ROADMAP.md`
- Architecture decisions: `context/recognition_upgrade/ARCHITECTURE_DECISIONS.md`

## What Was Tested

E4-T loaded the E4-S latest fixed-epoch `conv1d_baseline` weights for seeds `101`, `202`, and `303`.

Active primary classes:

- `GOOD`
- `HELLO`
- `HAVE`
- `KNOW`

OOV/confusion holdout:

- `SORRY`

The simulation scanned confidence, top-1/top-2 margin, and a stricter `GOOD` confidence threshold because E4-S showed `SORRY` is usually misread as `GOOD`.

## Gate

The router policy had to satisfy all of:

- Minimum accepted precision including OOV/confusion rows >= `0.95`
- Minimum active coverage >= `0.80`
- Maximum `SORRY` false-accept rate <= `0.05`

## Key Measurements

E4-S closed-set active test accuracy remained strong:

- Seed `101`: active test accuracy `0.9886`
- Seed `202`: active test accuracy `0.9886`
- Seed `303`: active test accuracy `0.9773`

But withheld `SORRY` remained a high-confidence `GOOD` false commit:

- Seed `101`: `SORRY` test mean confidence `0.9943`, predicted `GOOD` for `30/30`
- Seed `202`: `SORRY` test mean confidence `0.9997`, predicted `GOOD` for `30/30`
- Seed `303`: `SORRY` test mean confidence `0.9995`, predicted `GOOD` for `30/30`

Best scanned aggregate policy:

- Confidence threshold: `0.98`
- Margin threshold: `0.90`
- `GOOD` confidence threshold: `0.99999`
- Mean accepted precision including OOV: `0.9561`
- Minimum accepted precision including OOV: `0.9000`
- Mean active coverage: `0.6439`
- Minimum active coverage: `0.6136`
- Mean `SORRY` false-accept rate: `0.0889`
- Maximum `SORRY` false-accept rate: `0.2000`
- Active accepted accuracy: `1.0000`

## Decision

E4-T is a **no-go for simple softmax confidence/margin routing**.

Reason: the policy cannot simultaneously preserve useful active-sign coverage and reject `SORRY`. The model is not uncertain on `SORRY`; it is often extremely confident that `SORRY` is `GOOD`.

This result does not invalidate E4-S. It means E4-S can be a stable closed-set primary recognizer, but it cannot be deployed alone or protected by simple confidence thresholds.

## Engineering Interpretation

The problem is not ordinary low-confidence uncertainty. The problem is representation-level confusion: under `[96,258]`, `SORRY` occupies a region the primary model treats as `GOOD`.

Therefore:

- Raising confidence thresholds is insufficient.
- Top-1/top-2 margin is insufficient.
- A special `GOOD` threshold is insufficient unless coverage becomes too low.
- E4-T should not be repeated as another threshold-only tuning loop.

## Architecture Decisions

- Keep E4-S as evidence that `GOOD`, `HELLO`, `HAVE`, and `KNOW` are stable in closed-set landmark recognition.
- Do not promote E4-S to Android without a stronger rejection/specialist path.
- Treat `SORRY -> GOOD` as a registered hard confusion.
- Move the next work toward a specialist or richer-evidence experiment for `SORRY` instead of further threshold-only routing.

## Assumptions

- The current holdout contains only `SORRY`, so it is not a complete unknown/no-sign evaluation.
- The current simulation is per-window, not full streaming temporal confirmation.
- The result is strong enough to reject simple confidence/margin routing for this confusion case, because all three seeds misread test `SORRY` as `GOOD`.

## Open Questions

- Can an RGB hand/body crop specialist separate `SORRY` from `GOOD` reliably?
- Is the `SORRY` label/variant consistent enough, or does it need fluent review/recollection?
- Can a binary `GOOD` vs `SORRY-like` detector outperform the 4-way primary model on this group?
- What no-sign/OOV capture set is needed after the first specialist result?

## Risks

- Specialist work can add complexity without fixing data/variant mismatch.
- A `GOOD`-specific reject rule may reduce real `GOOD` coverage too much.
- If `SORRY` remains visually/semantically variant-mixed, RGB may also fail without data cleanup.
- The product vocabulary may remain small until hard groups are either fixed or safely rejected.

## Next Required Action

Prepare a focused specialist/data-repair experiment for the `SORRY` confusion, using the existing dynamic mixed roadmap. The next experiment should compare the E4-S primary evidence against richer visual evidence or targeted `GOOD/SORRY` review, not another threshold-only router scan.
