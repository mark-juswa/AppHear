# E4-V GOOD/SORRY Specialist Result

**Purpose:** Record the completed binary specialist proof-of-value for the `SORRY -> GOOD` confusion group.
**Scope:** Offline experiment result only. No Android integration, TFLite export, production recognizer replacement, global RGB rollout, or broad vocabulary expansion is authorized.
**Current status:** COMPLETE / STRUCTURAL CHECK PASSED / LANDMARK BINARY SPECIALIST PASS / RGB UPPER-BODY NO-GO.
**Last updated:** 2026-08-02.

## Verified Project References

- Runner: `pipeline/rgb/e4_v_sorry_good_specialist.py`
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01`
- Metrics: `artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01/metrics/metrics.json`
- Package plan: `E4_V_SORRY_GOOD_SPECIALIST_PACKAGE.md`
- Prior evidence: `E4_U_CONFUSION_EVIDENCE_PACKAGE.md`
- Prior router result: `E4_T_ROUTER_SIMULATION_RESULT.md`

## Dataset

- Classes: `GOOD`, `SORRY`
- Total rows: `100`
- Split counts: train `30`, validation `10`, test `60`
- Class counts:
  - Train: `GOOD 15`, `SORRY 15`
  - Validation: `GOOD 5`, `SORRY 5`
  - Test: `GOOD 30`, `SORRY 30`

The split is inherited from E4-J and is signer-disjoint but small.

## Branch Results

### Landmark Binary Control

Latest fixed-epoch test result was stable across all three seeds:

| Seed | Test Accuracy | GOOD Recall | SORRY Recall | Confusion Matrix |
|---:|---:|---:|---:|---|
| `101` | `0.9667` | `0.9667` | `0.9667` | `[[29,1],[1,29]]` |
| `202` | `0.9667` | `0.9667` | `0.9667` | `[[29,1],[1,29]]` |
| `303` | `0.9667` | `0.9667` | `0.9667` | `[[29,1],[1,29]]` |

Summary:

- Mean latest test: `0.9667`
- Minimum latest test: `0.9667`
- Mean `GOOD` recall: `0.9667`
- Mean `SORRY` recall: `0.9667`
- Minimum `SORRY` recall: `0.9667`

### RGB Upper-Body Specialist

RGB was unstable:

| Seed | Test Accuracy | GOOD Recall | SORRY Recall | Failure Pattern |
|---:|---:|---:|---:|---|
| `101` | `0.9167` | `0.9333` | `0.9000` | acceptable but below landmark |
| `202` | `0.9333` | `1.0000` | `0.8667` | SORRY below gate |
| `303` | `0.5000` | `1.0000` | `0.0000` | collapsed to all `GOOD` |

Summary:

- Mean latest test: `0.7833`
- Minimum latest test: `0.5000`
- Mean `GOOD` recall: `0.9778`
- Mean `SORRY` recall: `0.5889`
- Minimum `SORRY` recall: `0.0000`
- RGB gain over landmark: `-0.1833`
- RGB specialist promising: `false`

## Decision

E4-V is a **go for a landmark binary specialist pattern** and a **no-go for the current upper-body RGB specialist**.

This is a meaningful correction to the previous hypothesis. The failure in E4-S/E4-T was not that `[96,258]` can never separate `SORRY` from `GOOD`; it was that the 4-sign primary model did not contain `SORRY`, so `SORRY` was forced into the nearest known primary class. When `SORRY` is explicitly included in a focused binary landmark specialist, the same `[96,258]` representation separates it well.

## Engineering Interpretation

- The stable primary model should remain small and conservative.
- Some hard signs may be handled by lightweight landmark specialists before RGB specialists are needed.
- RGB should remain available as a fallback for groups where landmark specialists fail, but the current `rgb_upper_body` setup is not reliable enough for this group.
- The next high-value step is an offline mixed simulation: primary E4-S plus a conditional `GOOD/SORRY` landmark specialist triggered when the primary predicts `GOOD` or another registered confusion route.

## Risks

- The specialist result is based on a small local split.
- A binary specialist may not remain strong when the group expands to `GOOD/SORRY/HELP/BECOME` or other related signs.
- Routing every primary `GOOD` prediction to a specialist has runtime cost and may introduce new false corrections if not calibrated.
- The current result does not prove Android readiness.

## Next Required Action

Prepare the next offline mixed simulation using:

`E4-S primary model + conditional GOOD/SORRY landmark specialist + SORRY holdout`

The simulation should measure whether routing primary `GOOD` candidates through the binary specialist can preserve true `GOOD` while recovering true `SORRY`, without reducing `HELLO`, `HAVE`, and `KNOW` behavior.
