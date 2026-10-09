# A2-1R Single-Factor Handedness-Prior Repair — Result

Date: 2026-08-20  
Classification: **REJECT_A2_1R**  
Boundary: offline causal identity only; no recovery, Android, A1, S4-S7, model, or schema change

## Controlled change

A normalized full-file comparison against the original frozen A2-1 configuration passed before
evaluation. The only changed leaf was:

```text
tracker.invert_mediapipe_handedness: true -> false
```

All tracker weights, distance thresholds, ambiguity rules, velocity/state logic, annotations,
sequence selection, cohorts, metrics, and eight gates remained frozen. The original configuration
and evidence package were not modified. Pre-evaluation provenance is recorded in
`artifacts/recognition_upgrade/a2_landmark_continuity/a2_1r_identity_only_01/pre_evaluation_provenance.json`.

The copied configuration retains the old `identity_semantics` descriptive strings byte-for-byte so
the configuration diff remains one leaf. Those strings are not consumed by the evaluator; the
effective tracker configuration recorded in the result has `invert_mediapipe_handedness=false`.

## Validation

- Focused unit tests: `7 passed`.
- Evidence validation: `551/551` complete, zero errors.
- Dataset: unchanged 21 sequences, 551 frames, eight glosses, and 230 combined known direct
  identity instances.
- All 13 protected A1/runtime/model files matched the original baseline freeze.

## Identity metrics

| Cohort | Method | Known | Correct | Wrong | Ambiguous | Error | Coverage | New errors | Baseline fixed | Switches/min |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Primary A1 | Raw handedness | 141 | 138 | 3 | 0 | 2.13% | 100.00% | — | — | 2.812 |
| Primary A1 | A2-1R tracker | 141 | 103 | 14 | 24 | 9.93% | 82.98% | 13 | 1 | 2.812 |
| Supplemental RU-D9 | Raw handedness | 89 | 86 | 3 | 0 | 3.37% | 100.00% | — | — | 3.357 |
| Supplemental RU-D9 | A2-1R tracker | 89 | 65 | 9 | 15 | 10.11% | 83.15% | 9 | 1 | 1.679 |
| Combined | Raw handedness | 230 | 224 | 6 | 0 | 2.61% | 100.00% | — | — | 3.061 |
| Combined | A2-1R tracker | 230 | 168 | 23 | 39 | 10.00% | 83.04% | 22 | 2 | 2.295 |

The corrected prior materially improved the tracker relative to the broken original A2-1, but it
remained substantially worse than preserving raw non-inverted handedness.

## Original A2-1 versus A2-1R

| Combined tracker metric | Original inverted A2-1 | A2-1R non-inverted | Change |
| --- | ---: | ---: | ---: |
| Correct | 14 | 168 | +154 |
| Wrong | 110 | 23 | -87 |
| Ambiguous | 106 | 39 | -67 |
| Assignment coverage | 53.91% | 83.04% | +29.13 points |
| New errors | 108 | 22 | -86 |
| Temporal-propagation errors | 91 | 18 | -73 |

Removing inversion collapsed most of the original failure mode, confirming that the inverted prior
was a major defect. The remaining 22 new errors, 39 ambiguous assignments, and 83.04% coverage show
that the frozen temporal cost/margin/state design still does not safely improve the frame-local
baseline.

## Residual error decomposition

All 62 wrong or ambiguous known instances are listed in
`a2_1r_residual_assignments.csv`.

| Classification | Instances |
| --- | ---: |
| Reassociation error | 5 |
| Temporal propagation of a wrong assignment | 18 |
| Initialization ambiguity | 3 |
| Ambiguity after a correct state | 11 |
| Continued ambiguity | 25 |

Mechanism/context audit:

- All 39 ambiguous instances were rejected by the frozen `0.12` assignment-margin rule; none was
  a wrist-collision or maximum-cost rejection.
- The tracker overrode a correct raw label on 22 wrong instances.
- One wrong instance involved a detector handedness disagreement that the tracker did not correct.
- Four residual instances total carried a detector-handedness-disagreement tag: one wrong and
  three ambiguous.
- No residual wrong or ambiguous instance occurred on a reviewed crossing, hand-body-contact, or
  hand-hand-contact frame.
- No wrong assignment occurred at the first known observation for a track under A2-1R. This is a
  major improvement over the inverted candidate, but later reassociation and propagation remain
  unsafe.

The classifications are causal sequence diagnostics from saved assignments. They do not expose
the individual internal cost contribution that caused each low margin.

## Frozen gates

| Gate | Threshold | Primary measured | Outcome | Interpretation |
| --- | --- | ---: | --- | --- |
| Known direct evidence | >=80 | 141 | PASS | Adequate ordinary evidence |
| Contact/crossing evidence | >=10 distinct frames | 0 | **INSUFFICIENT EVIDENCE** | Dataset limitation |
| Tracker identity error | <=1% | 9.93% | **FAIL** | Tracker behavior |
| New identity errors | 0 | 13 | **FAIL** | Tracker behavior |
| Switch rate | <= raw baseline | 2.812 vs 2.812/min | PASS | No improvement; equality only |
| Assignment coverage | >=95% | 82.98% | **FAIL** | Excess refusal/ambiguity |
| Ambiguous assignment rate | <=10% | 17.02% | **FAIL** | Low-margin tracker behavior |
| Baseline errors corrected | >=50% | 1/3 = 33.33% | **FAIL** | Insufficient benefit |

Six of eight gates remain unsatisfied, including the independent evidence gate.

## Decision

**REJECT_A2_1R.** The corrected prior proves that inversion caused most of the original A2-1
catastrophe, but the otherwise frozen temporal tracker still introduces unacceptable errors and
ambiguity relative to raw handedness. This is stronger evidence that the current temporal
assignment design—not only its prior—needs reconsideration.

Do not start A2-2, Android integration, threshold tuning, weight tuning, or another automatic A2-1
refinement. A crossing/contact supplement remains necessary before any future identity candidate
can claim stress-case validity, but it is not the immediate next step for this rejected candidate.

