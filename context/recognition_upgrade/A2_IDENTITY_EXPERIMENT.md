# A2-0 / A2-1 — Landmark Continuity Evidence and Anatomical Identity

Status: **A2-0 complete; A2-1 and the authorized A2-1R repair evaluated and rejected**  
Experiment: `a2_1_identity_only_01`  
Schema: frozen v3.0 `[96,258]`; no feature-contract change  
Runtime: offline only; Android and production behavior unchanged

Final A2-1 result: `context/recognition_upgrade/A2_1_IDENTITY_RESULT.md`. The frozen candidate
failed six of eight gates and is not authorized for A2-2 or Android integration.

Final A2-1R result: `context/recognition_upgrade/A2_1R_IDENTITY_RESULT.md`. Changing only the
handedness prior to non-inverted removed most of the original catastrophic failure, but the
otherwise frozen tracker still failed ordinary identity, new-error, coverage, ambiguity, and
baseline-correction gates. Decision: `REJECT_A2_1R`; do not proceed to A2-2.

**Human-review correction (pre-evaluation):** Human review exposed that raw detector `Left/Right`
labels are unsafe and confusing as annotation concepts. Saved front-camera evidence is unmirrored,
all 551 selected trace rows have `mirrored=false`, and direct inspection found both an anatomical
right hand in detector `LEFT` and another anatomical right hand in detector `RIGHT`. The labels can
therefore vary and must not seed human truth. The final GUI names the two stored slots only by their
rendered colors, BLUE and ORANGE; each present slot starts as `ambiguous` and the reviewer assigns
anatomical identity from the photograph. Recovery controls are derived automatically from visible
and identified-hand answers. The first seven-row correction backup remains historical. A second
backup, `annotations_before_color_ui_correction.csv`, preserves all 38 rows accepted under the
confusing interface; all 38 were reset to neutral/unreviewed. No final annotation or evaluation
result existed when these corrections were made.

## Scope and frozen controls

A2-1 tests only causal anatomical left/right assignment of direct MediaPipe hand landmarks. It
does not carry, interpolate, extrapolate, or recover a missing landmark. Production baseline,
the evaluated A1 scheduler, S4, S5, S6, S7, recognition configuration, TFLite model, vocabulary,
and MediaPipe task files are hashed in `baseline_freeze.json`. The A2 code is not called by the
Android app and remains default-off by construction.

Future comparisons remain three-way:

1. stable production baseline;
2. frozen A1 independent-clock perception;
3. A1 plus an A2 candidate, only after the relevant offline gate passes.

## A2-0 evidence inventory

The generated package uses existing phone evidence only; no new capture is currently justified.

| Cohort | Sequences | Frames | Purpose |
| --- | ---: | ---: | --- |
| A1 signing sentinel, A1 mode | 12 | 315 | Primary frozen chronological cohort |
| RU-D9 adjudicated phone attempts | 9 | 236 | Supplemental failure-stress cohort |
| **Total** | **21** | **551** | Eight glosses: GOOD, HAVE, HELLO, KNOW, NOW, SISTER, WE, WHO |

The set contains 11 one-hand and 10 two-hand sequences. Historical RU-D9 adjudication identifies
three two-hand contact/occlusion sequences, two detector-dropout sequences, two S5 consecutive-
evidence failures, and two S5 signal failures. Every selected sequence also includes sign-span
observations plus two available edge/rest observations on each side. Crossing, true leaving-frame,
no-hand/rest, visible dropout length, and recoverability counts are intentionally **not inferred**
from those historical labels; they are emitted only after frame-level human review.

Selection is frozen as sign span ±4 recorded observations plus two available edge observations.
The primary cohort spans six signing-sentinel glosses rather than tuning only on KNOW/GOOD/WE.
RU-D9 adds WHO and SISTER as stress evidence, but remains a separately reported supplemental
cohort.

## Human-visible annotation contract

One row corresponds to one chronological phone frame and records:

- whether anatomical signer-left and signer-right hands are visibly present;
- the anatomical identity of each directly populated MediaPipe slot (`left`, `right`,
  `ambiguous`, or `none`);
- whether a visible but undetected anatomical hand is genuinely recoverable (`yes`, `no`, or
  `uncertain`);
- hand-hand contact, hand-body contact, crossing/midline ambiguity, leaving-frame state, and
  true no-hand/rest state;
- reviewer acceptance and optional notes.

Stored MediaPipe slots are shown only as BLUE and ORANGE detections and never as anatomical-side
suggestions. A present colored detection defaults to `ambiguous`; an absent detection is locked to
`none`. An unreviewed row is never truth,
and evaluation refuses to run until all rows are accepted and internally consistent. The reviewer
shows the phone image beside a normalized landmark schematic and resumes at the first unaccepted
row. Saves are atomic.

## Frozen A1 direct-only observations

Before human adjudication, only mechanical detector facts can be reported:

| Cohort | Selected frames | Any direct hand | Both direct hands | No direct hand | Expected-hand completeness |
| --- | ---: | ---: | ---: | ---: | ---: |
| Primary A1 | 315 | 106 | 35 | 209 | 26.67% |
| Supplemental RU-D9 | 236 | 77 | 15 | 159 | 20.76% |

For primary A1 frames with consecutive any-hand detections, the pooled direct-observation gap is
267.04 ms median and 386.79 ms p95 (94 gaps). These are not visible-hand recall measurements.
Visible-hand instance recall, false presence, true dropout distributions, handedness disagreement,
and identity switches remain gated on human review. This prevents the detector from grading itself.

## A2-1 causal algorithm

The tracker maintains `Track_L` and `Track_R`, each containing the last directly assigned 21×3
landmarks, direct timestamp, EMA wrist velocity, and direct-update count. It enumerates the two
possible assignments for two observations, or both anatomical choices for one observation.

Assignment cost is frozen before annotation results:

- predicted wrist distance: weight 0.65;
- five-point palm-shape continuity: weight 0.20;
- matching pose-wrist distance: weight 0.05;
- disagreement with the orientation-corrected MediaPipe slot prior: penalty 0.10.

For this frozen unmirrored-front-camera package, detector `LEFT` weakly favors anatomical right and
detector `RIGHT` weakly favors anatomical left. The prior alone is insufficient to cross the 0.12
assignment margin. Wrist velocity uses EMA 0.60 and prediction time is capped at 0.50 seconds. A candidate is rejected
as ambiguous if total assignment cost exceeds 0.85 per observation, the best-versus-second margin
is below 0.12, or two observed wrists are within 0.08 normalized units. Ambiguous observations do
not update either track. Empty frames produce no assignment and no state update. There is no future
frame access and no missing-hand output.

## Metrics and preregistered A2-1 gates

Primary and supplemental cohorts are reported separately, with a combined diagnostic view. The A1
slot-label baseline and A2 tracker are compared on known directly detected hand instances.

Metrics include visible-hand instance recall, any-hand and complete two-hand coverage, false-hand
presence, consecutive dropout lengths, direct gap p50/p95, handedness error, incorrect anatomical
assignments, ambiguous assignments, assignment coverage, identity switches and switches/minute,
new errors, and corrected baseline errors.

A2-1 is retained for A2-2 review only if the primary cohort has at least 80 known direct instances
and 10 contact/crossing frames, tracker identity error is at most 1%, it creates zero new identity
errors, switch rate does not exceed baseline, assignment coverage is at least 95%, ambiguity is at
most 10%, and it corrects at least 50% of baseline identity errors when baseline errors exist. If
the baseline has no errors or switches, a passing tracker is classified as safe but its benefit is
not demonstrated.

## Historical-experiment separation

A2-1 operates after MediaPipe inference on actual normalized 21-landmark sequences. It does not use
static or pose-guided ROI holding, CameraX cadence changes, MediaPipe VIDEO/LIVE_STREAM mode,
confidence lowering, optical flow, RGB/HaGRID/MobileNet fallback, S5 tolerance, or sign-specific
rules. Those earlier approaches changed detection, scheduling, pixels, or downstream gating; this
experiment tests temporal anatomical assignment only.

## Files

- `model/config/recognition_upgrade/a2_identity.json` — frozen selection, algorithm, gates, bounds
- `eval/runtime_diagnostics/a2_identity_tracker.py` — causal identity-only implementation
- `eval/runtime_diagnostics/a2_identity_experiment.py` — package, reviewer, validation, evaluator
- `model/config/recognition_upgrade/run_a2_identity.ps1` — offline workflow entry point
- `tests/test_a2_identity_tracker.py` — causal assignment/ambiguity/no-recovery tests
- `artifacts/recognition_upgrade/a2_landmark_continuity/a2_0_identity_01/` — frozen evidence package

## Manual gate

From any PowerShell working directory:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "F:\ASL DATASET\5. Apphear3\model\config\recognition_upgrade\run_a2_identity.ps1" -Command Review
```

After all 551 frames are accepted, validate without evaluating:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "F:\ASL DATASET\5. Apphear3\model\config\recognition_upgrade\run_a2_identity.ps1" -Command Check
```

Do not run A2-1 evaluation until `Check` reports `remaining: 0` and `passed: true`.
