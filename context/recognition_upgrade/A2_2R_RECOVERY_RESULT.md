# A2-2R Conservative One-Observation Recovery — Result

Status: **complete — rejected**  
Decision: `REJECT_A2_2R_RECOVERY`  
Experiment: `a2_2r_one_observation_01`

## Frozen comparison

- `C0_DIRECT_ONLY`: unchanged A1 direct observations.
- `C1_ONE_OBSERVATION_HOLD`: one causal hold from the latest trusted direct landmarks.
- `C2_ONE_OBSERVATION_BOUNDED_VELOCITY`: one bounded causal velocity prediction from two
  trusted direct observations.

Both candidates preserved raw, non-inverted MediaPipe slot identity. Neither imported the rejected
A2-1/A2-1R tracker, seeded history from recovered landmarks, persisted beyond the first missing
observation, changed Android, changed schema v3.0 `[96,258]`, retrained, or changed S5-S7 policy.

## Evidence package

The frozen package has 551 reviewed selected rows from 21 phone attempts and 93 reviewed visible
missing hand-sides. Human review marked 87 recoverable, five uncertain, and one not recoverable.
Twelve recoverable cases were single missing observations bracketed by direct detections; six were
actually recovered by each causal candidate and could be scored using the next direct observation
as a re-entry proxy. Missing-frame landmark truth does not exist, so these geometry numbers are not
missing-frame accuracy claims.

The required post-result integrity check passed with all protected source and input hashes intact.
The evaluator, config, runner, annotations, package index/manifest/freeze, recognition config,
deployed model, and vocabulary hashes are embedded in `a2_2r_result.json`.

## Coverage and recovery

| Metric | C0 direct | C1 hold | C2 velocity |
| --- | ---: | ---: | ---: |
| Visible-hand instance recall | 69.97% | 75.85% | 75.85% |
| Any-hand coverage | 77.88% | 81.86% | 81.86% |
| Complete two-hand coverage | 51.55% | 61.86% | 61.86% |
| Full-trace recoveries | 0 | 27 | 27 |
| Scoreable recoveries / 12 | 0 | 6 | 6 |

The coverage gate passed materially: both candidates gained 5.88 percentage points of visible-hand
recall and 10.31 points of complete two-hand coverage.

## Safety result

Both candidates made the same causal recovery decisions. Each produced eight false recoveries on
true absence, three recoveries on no-hand/rest frames, five on leaving frames, and 19 stale
recoveries at the onset of a longer gap. Those are preregistered hard failures. The intended narrow
boundary did work: there were zero multi-observation persistence events, zero identity swaps, and
zero wrong-hand recoveries.

Within the 93 reviewed visible-missing cases, neither candidate recovered any of the six
`uncertain`/`no` cases; five were correctly left missing and one was already direct in the frozen
trace. Of the 87 human-`yes` cases, 16 were recovered, 70 were left missing, and one was already
direct. This conservative behavior does not rescue the candidates because their full-trace
recoveries still violated absence/rest/leaving/long-gap safety.

## Geometry

| Re-entry/continuity p95 | Gate | C1 hold | C2 velocity |
| --- | ---: | ---: | ---: |
| Wrist error | <= 0.50 | 0.309 | 0.313 |
| Mean-landmark error | <= 0.50 | 0.416 | 0.409 |
| Fingertip error | <= 0.65 | 0.451 | 0.446 |
| Direct-to-recovered jump | <= 0.15 | 0.000 | 0.117 |
| Velocity discontinuity / s | <= 2.00 | **2.358** | **2.308** |

Both variants failed the velocity-continuity limit. C2 reduced mean re-entry landmark error by only
3.3% versus C1, below the frozen 10% complexity threshold; it therefore offers no justified
advantage even apart from the hard safety failures.

## Frozen downstream replay

| Metric across 21 attempts | C0 | C1 | C2 |
| --- | ---: | ---: | ---: |
| Correct commits | 5 | 6 | 5 |
| Wrong commits | 5 | 6 | 6 |
| No commit | 11 | 9 | 10 |
| False onsets outside sign span | 0 | 0 | 0 |
| False commits outside sign span | 0 | 0 | 0 |

Both candidates increased wrong commits by one, violating the frozen no-regression gate. The exact
new failure was `20260816022202793_SISTER`, which changed from no commit to a wrong commit under C1
and C2. C1 also changed `20260816071748026_NOW` from no commit to a correct commit; C2 did not. A
single correct gain does not override a hard wrong-commit regression.

The replay ran the deployed quantized TFLite model on x86. Known ARM/x86 divergence makes it a
controlled same-host comparison, not a claim of exact Android posterior parity.

## Gate decision

Evidence size, recovery count/recall, coverage, one-observation persistence, identity safety, and
no-sign onset/commit gates passed. Both C1 and C2 failed the true-absence, rest, leaving, stale-gap,
velocity-continuity, and wrong-commit gates. C2 additionally failed its complexity-justification
rule.

Therefore the preregistered decision is `REJECT_A2_2R_RECOVERY`. Incremental landmark
carry-forward/extrapolation is closed on this evidence. The next eligible planning activity is a
**Perception Backend Replacement Study**. It has not been started, designed, or implemented here.

## Canonical artifacts

- Machine result: `artifacts/recognition_upgrade/a2_landmark_continuity/a2_2r_one_observation_01/a2_2r_result.json`
- Provenance: `artifacts/recognition_upgrade/a2_landmark_continuity/a2_2r_one_observation_01/a2_2r_provenance.csv`
- Geometry: `artifacts/recognition_upgrade/a2_landmark_continuity/a2_2r_one_observation_01/a2_2r_geometry.csv`
- Downstream replay: `artifacts/recognition_upgrade/a2_landmark_continuity/a2_2r_one_observation_01/a2_2r_downstream_attempts.csv`
- Read-only safety cross-check: `artifacts/recognition_upgrade/a2_landmark_continuity/a2_2r_one_observation_01/a2_2r_safety_audit.json`
