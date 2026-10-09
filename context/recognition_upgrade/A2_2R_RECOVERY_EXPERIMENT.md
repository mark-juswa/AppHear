# A2-2R — Conservative One-Observation Landmark Recovery

Status: **complete — `REJECT_A2_2R_RECOVERY`**  
Experiment: `a2_2r_one_observation_01`  
Boundary: offline only; raw non-inverted direct identity; no A2-1 tracker; no Android or schema change

Final report: `context/recognition_upgrade/A2_2R_RECOVERY_RESULT.md`. Both candidates improved
coverage but failed the frozen absence/rest/leaving/stale-gap, velocity-continuity, and downstream
wrong-commit gates. Incremental recovery is closed; the Perception Backend Replacement Study is
the next eligible planning activity and was not started by this experiment.

## Causal interpretation

A runtime cannot know at the first missing observation whether a detector gap will last exactly one
or several observations. A2-2R therefore means: recover at most the first missing observation after
two consecutive trusted direct observations, never let recovered data seed history, and emit
`MISSING` on the second consecutive miss. The next direct observation is used only for retrospective
quality scoring.

## Frozen conditions

- `C0_DIRECT_ONLY`: unchanged A1 feature rows.
- `C1_ONE_OBSERVATION_HOLD`: copy the latest trusted direct 21-landmark block once.
- `C2_ONE_OBSERVATION_BOUNDED_VELOCITY`: predict once from two trusted direct blocks. Decompose
  motion into clipped wrist translation plus clipped landmark-relative articulation, then cap wrist
  displacement at 0.12 and every landmark displacement at 0.15 shoulder-normalized units.

Both recovery candidates use raw non-inverted MediaPipe slots as anatomical identity. The rejected
A2-1/A2-1R assignment tracker is not imported or called.

## Frozen eligibility

Recovery requires two consecutive direct observations in the same slot, history and recovery ages
within 50-400 ms, hand scale 0.08-0.45, current pose-wrist distance at most 0.50, wrist radius at
most 1.25, no strong outward motion, and either a previously active signing state or another direct
hand in the current frame. A recovered observation never updates direct history. Session boundaries
reset all state, and a second consecutive miss is always `MISSING`.

Human visibility, recoverability, leaving, and rest labels are evaluation truth only. They are not
available to or used by the causal recovery decision.

## Evidence and ground-truth boundary

The frozen 551-row A2 package contains 93 visible missing hand-sides: 87 marked recoverable, five
uncertain, and one not recoverable. Twelve recoverable missing observations are bracketed by direct
detections in the complete source trace; eight also have the required two-direct history. Audit will
freeze their exact IDs before evaluation.

The missing-frame landmarks are unknowable. Geometry metrics compare recovery with the next trusted
direct observation and measure entry/exit continuity. They are re-entry proxies, not claims of exact
missing-frame ground truth.

## Preregistered gates

A candidate must have at least eight scoreable events available, recover at least six and at least
50% of the scoreable recoverable universe, and improve either visible-hand instance recall by 1.5
percentage points or complete two-hand coverage by 2.0 points. It must produce zero recovery on
annotated true absence, no-hand/rest, or leaving frames; zero long-gap-onset stale recovery; zero
multi-observation persistence, swaps, or wrong-hand recovery.

Re-entry p95 limits are 0.50 for wrist and mean landmarks, 0.65 for fingertips, 0.15 for
direct-to-recovered jump, and 2.0 shoulder-normalized units/second for the two-segment velocity
discontinuity. Frozen replay allows no increase in wrong commits, no-sign false onsets, or no-sign
false commits.

C2 is preferred over C1 only if it passes every gate and reduces mean-landmark re-entry error by at
least 10% without a safety or downstream regression. Otherwise the simpler passing C1 wins. If
neither passes, use `REJECT_A2_2R_RECOVERY` and stop incremental recovery work.
