# A2-1 Offline Causal Anatomical Identity — Result

Date: 2026-08-20  
Experiment: `a2_1_identity_only_01`  
Decision: **REJECT_A2_1_IDENTITY_TRACKER**  
Boundary: identity only; no landmark recovery, Android, S4-S7, model, or schema change

## Executive result

The frozen A2-1 tracker failed six of eight preregistered gates. It reduced the count of identity
switches, but only by assigning the wrong anatomical hand or refusing assignment on most direct
observations. On the primary A1 cohort, it created 71 new errors, had 51.06% identity error,
46.81% ambiguity, and only 53.19% assignment coverage.

The principal algorithm defect is the frozen `invert_mediapipe_handedness=true` prior. Human truth
showed that raw A1 detector slots already agreed with anatomical identity for 224/230 known direct
instances across the complete package (97.39%). The earlier visual discovery of a real right hand
under detector `LEFT` proved that labels can disagree; it did not prove systematic inversion. The
color-based reviewer correctly removed detector labels from human truth, but the candidate retained
the inversion as a weak algorithm prior. That prior poisoned initial track state and temporal
continuity then propagated the wrong identity.

This result rejects this exact tracker configuration. It does not evaluate or reject landmark
recovery because A2-1 never emitted recovered landmarks.

## Frozen A2-0 continuity baseline

| Metric | Primary A1 | Supplemental RU-D9 | Combined |
| --- | ---: | ---: | ---: |
| Frames / sequences | 315 / 12 | 236 / 9 | 551 / 21 |
| Visible-hand instance recall | 72.68% | 68.99% | 71.21% |
| Any-hand coverage | 77.94% | 82.22% | 79.65% |
| Complete two-hand coverage | 60.34% | 38.46% | 51.55% |
| False-presence frames | 0 | 3 | 3 |
| Direct gap p50 / p95 | 300.46 / 677.65 ms | 288.71 / 641.74 ms | 292.11 / 647.78 ms |
| Dropout runs | 30 | 19 | 49 |
| One-observation dropout runs | 20 | 10 | 30 |
| Maximum dropout | 6 observations | 6 observations | 6 observations |

Combined reviewed context contains 271 true no-hand/rest frames, 48 leaving-frame observations,
one hand-body-contact frame, three crossing/midline frames, and zero hand-hand-contact frames.
Review marked 87 anatomical-hand dropouts recoverable (`yes`) across 77 frames, with five further
hand-side judgments uncertain and one explicitly not recoverable. These labels are future A2-2
evidence only; no recovery was attempted here.

## Identity result

| Metric | Primary raw A1 labels | Primary A2-1 tracker | Combined raw A1 labels | Combined A2-1 tracker |
| --- | ---: | ---: | ---: | ---: |
| Known direct instances | 141 | 141 | 230 | 230 |
| Correct | 138 | 3 | 224 | 14 |
| Incorrect | 3 | 72 | 6 | 110 |
| Ambiguous | — | 66 | — | 106 |
| Assignment coverage | 100% | 53.19% | 100% | 53.91% |
| Identity error / disagreement | 2.13% | 51.06% | 2.61% | 47.83% |
| Identity switches | 4 | 3 | 8 | 5 |
| Switches/minute | 2.812 | 2.109 | 3.061 | 1.913 |
| New tracker errors | — | 71 | — | 108 |
| Baseline errors corrected | — | 1 | — | 3 |

The lower switch count is not a benefit: it was purchased with catastrophic error and ambiguity.
A false anatomical assignment is worse than a missing observation under the frozen safety policy.

## Preregistered gates

| Gate | Result | Evidence |
| --- | --- | --- |
| At least 80 primary known instances | PASS | 141 |
| At least 10 primary contact/crossing frames | **FAIL** | 0 |
| Tracker identity error ≤1% | **FAIL** | 51.06% |
| Zero new identity errors | **FAIL** | 71 |
| Switch rate does not regress | PASS | 2.109 vs 2.812/min |
| Assignment coverage ≥95% | **FAIL** | 53.19% |
| Ambiguity ≤10% | **FAIL** | 46.81% |
| Correct ≥50% of baseline errors | **FAIL** | 1/3 = 33.33% |

Machine result:
`artifacts/recognition_upgrade/a2_landmark_continuity/a2_0_identity_01/a2_1_result.json`.

## Evidence limitation

The preregistered stress-evidence gate also failed independently of the algorithm. Human review
found no contact/crossing frames in the primary A1 cohort. The supplemental RU-D9 cohort contained
only one hand-body-contact and three crossing frames, despite historical attempt-level attribution
to contact/occlusion. Attempt-level cause names cannot substitute for frame-level visible evidence.

Therefore the current package is sufficient to reject this candidate on ordinary direct identity,
but insufficient to claim success through contact/crossing even if a later tracker performs well.

## Recommendation and hard stop

1. **Do not begin A2-2 landmark recovery.** Identity is not safe and the contact/crossing evidence
   gate is unmet.
2. **Do not integrate Android A2 or change S4-S7.** A1 remains the default-off foundation.
3. If continuing A2-1, allow only one narrowly preregistered refinement: change the orientation
   prior from inverted to non-inverted while leaving all other weights, state, ambiguity rules, and
   causal behavior frozen. This is justified by 224/230 empirical slot agreements, not by tuning a
   threshold.
4. Before treating that refinement as sufficient for A2-2, add a bounded frame-level
   contact/crossing supplement. Search existing chronological bundles first; capture new evidence
   only if fewer than ten adjudicated stress frames can be recovered. The current 551 rows must not
   be relabeled or used as fresh confirmation evidence.

Stop here pending explicit approval of that one refinement and evidence supplement.
