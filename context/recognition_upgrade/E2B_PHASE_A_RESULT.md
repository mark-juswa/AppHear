# E2b Phase-A Result

## Purpose

Record the verified result and decision from the paired causal ROI-recovery experiment.

## Scope

This result covers E2b Phase A only. It does not approve crop-geometry Phase B, E3 hybrid
training, production Android changes, or a feature-schema change.

## Current Status

COMPLETE - NO-GO. No tested pose-recovery age passed every registered diagnostic gate.

## Verified Project References

- Run directory:
  `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/e2b_roi_recovery_v0/engineering_e2b_01`
- `internal_index.csv`: 120 known-visible base items and 480 paired strategy records.
- `audit_template.csv`: 480/480 human-reviewed records.
- `audit_summary.json`: registered analyzer output.
- Experiment contract: `E2B_ROI_RECOVERY_PLAN.md`.
- Generator and analyzer: `pipeline/crops/e2b.py`, `pipeline/crops/e2b_audit.py`.

Artifact SHA-256:

- Audit: `76D79DBC29017354FEAB7B0F88F1A72314B5FFA47FAFD74E6EE455C11D070CAE`
- Index: `2977BA20881040A3A95559BCD9642BF1A3D29A8172D68A753D76E1462CC9365A`
- Registered summary:
  `07C5787E5AEEB1876B68EDC6CE8B59DCFAE6E69ED7CD682A3763E031A2963A0E`

## Verified Result

All 120 base items were selected from the corrected E2 audit as known-visible. Availability
therefore uses the fixed 120-item denominator rather than the one inconsistent E2b visibility
label.

| Strategy | Available | Raw audit usable |
|---|---:|---:|
| Control hold 100 ms | 64/120 (53.3%) | 42/119 (35.3%) |
| Pose 150 ms | 95/120 (79.2%) | 54/119 (45.4%) |
| Pose 250 ms | 95/120 (79.2%) | 49/120 (40.8%) |
| Pose 350 ms | 95/120 (79.2%) | 46/120 (38.3%) |

Paired availability gain for every pose strategy:

| Cadence | Control | Pose | Gain | 20-point gate |
|---|---:|---:|---:|---|
| Native | 22/36 (61.1%) | 28/36 (77.8%) | +16.7 points | FAIL |
| k4 | 22/44 (50.0%) | 33/44 (75.0%) | +25.0 points | PASS |
| k8 | 20/40 (50.0%) | 34/40 (85.0%) | +35.0 points | PASS |

Across the 38 records recovered by pose tracking/fallback, raw usable counts were 9 for
150 ms and 8 for both 250 and 350 ms. The best raw recovery usability was therefore only
23.7%. Pose availability is useful, but its recovered box quality is not sufficient.

## Audit Consistency Finding

The original audit remains immutable. Independent checking found:

- one base item with conflicting target-hand visibility across identical source frames;
- 21 exact-panel-content groups with conflicting labels, covering 81 rows;
- 14/57 all-direct base items with disagreements even though all four panels were
  byte-identical;
- 25/120 base items with inconsistent source-motion-blur labels across strategies;
- one missing ROI assigned a non-missing failure reason;
- 11 present ROIs assigned `missing_roi`.

Consequently, raw usable-rate differences between 150/250/350 ms are not decision-grade.
The availability result is still valid because it comes from paired index metadata and
the prior E2 known-visible selection.

## Architecture Decision

- Do not promote any tested pose age.
- Do not run crop-size/expansion Phase B.
- Do not start E3 RGB/hybrid training.
- Keep pose hand anchors as a potentially useful fallback signal, not the primary tracker.
- The next bounded experiment must test a true temporal hand detector/tracker on raw
  chronological frames, with current IMAGE-mode output as the paired control.

## Engineering Recommendation

Prepare E2c as a paired Hand Landmarker IMAGE-versus-VIDEO tracking experiment before
considering LIVE_STREAM Android integration. Measure known-visible target-hand recall,
handedness stability, temporal continuity, full-hand crop containment, source blur, and
per-frame latency at native/k4/k8 conditions. Start with a small clip smoke; no model
training is required.

## Assumptions

- The corrected E2 visibility labels remain the source for known-visible base-item status.
- Exact JPEG byte equality implies identical review content.
- The 20-point diagnostic gate remains unchanged.

## Open Questions

- Does MediaPipe VIDEO tracking materially improve target-hand recall over current IMAGE mode?
- Will temporal tracking preserve anatomical hand identity during crossing and occlusion?
- Can a tracker reduce missingness without stale/wrong-hand crops or unacceptable Android cost?
- Should source blur be audited in a separate full-frame-only task in future experiments?

## Risks

- VIDEO mode may only smooth landmarks and may not recover missed detections.
- Tracking may improve continuity but increase stale or wrong-hand errors.
- The current ASL Citizen source videos may cap RGB quality because of motion blur.
- Repeating manual review without deduplication can reproduce reviewer inconsistency.

## Rollback

No production artifact changed. Preserve E2b outputs and ignore all pose-recovery candidates.
The current production recognizer and E1 TCN control remain unchanged.

## Next Required Action

Architect and smoke-test E2c IMAGE-versus-VIDEO temporal hand tracking. Future review sets
must deduplicate exact panel content and separate source-frame blur from crop-quality labels.

## Related Context Files

- `README.md`
- `E2B_ROI_RECOVERY_PLAN.md`
- `E2_CROP_QUALITY_RUNBOOK.md`
- `EXPERIMENT_MATRIX.md`
- `EVALUATION_AND_ACCEPTANCE_GATES.md`
- `RISK_REGISTER.md`

## Last Updated

2026-07-26
