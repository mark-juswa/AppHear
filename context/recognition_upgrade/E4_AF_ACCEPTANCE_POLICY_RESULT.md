# E4-AF Acceptance Policy Result

**Purpose:** Evaluate whether the current E4-AC signing gate can be made production-safe through lightweight acceptance-policy changes before moving to larger vocabulary screening.

**Scope:** Offline policy sweep only. No model training, MediaPipe extraction, Android integration, TFLite export, production recognizer replacement, or source dataset mutation.

**Current status:** COMPLETE / STRUCTURAL PASS / POLICY-ONLY NO-GO.

**Last updated:** 2026-08-02.

## Verified Project References

- Runner: `pipeline/rgb/e4_af_acceptance_policy.py`
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_af_acceptance_policy_01`
- Metrics: `artifacts/recognition_upgrade/e4_generalization/e4_af_acceptance_policy_01/metrics/acceptance_policy_metrics.json`
- Grid: `artifacts/recognition_upgrade/e4_generalization/e4_af_acceptance_policy_01/metrics/acceptance_policy_grid.csv`
- Predictions: `artifacts/recognition_upgrade/e4_generalization/e4_af_acceptance_policy_01/predictions/selected_policy_test_predictions.csv`
- Check: `artifacts/recognition_upgrade/e4_generalization/e4_af_acceptance_policy_01/check_report.json`

## Source Runs

- E4-AC gate: `artifacts/recognition_upgrade/e4_generalization/e4_ac_low_motion_aware_gate_01`
- E4-AA no-sign dataset: `artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_01`
- E4-S primary: `artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01`
- E4-V specialist: `artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01`
- E4-X routed policy: `artifacts/recognition_upgrade/e4_generalization/e4_x_routed_system_validation_01`

## What E4-AF Tested

E4-AF reused existing models and outputs. It did not train anything.

Compared policies:

- E4-AC baseline gate and routed recognizer;
- HELLO-specific gate probability floor, because E4-AD showed residual false commits are mostly `NO_SIGN -> HELLO`.

E4-AF also records that true streaming temporal stability cannot be fully validated from isolated positive windows. That must be tested later in Android/device or a streaming replay package.

## Result Summary

E4-AF structural check passed, but the policy-only gate failed.

Selected policy summary:

- mean test accepted precision: `0.9548`
- minimum test accepted precision: `0.9492`
- mean test positive coverage: `0.9746`
- minimum test positive coverage: `0.9661`
- max test no-sign false commit rate: `0.0441`
- mean/min GOOD recall: `0.9667/0.9667`
- mean/min HELLO recall: `0.9556/0.9333`
- mean/min SORRY recall: `0.9667/0.9667`

The result still misses the strict precision gate because minimum accepted precision is below `0.95`.

## Important Finding

HELLO-specific thresholding is not a practical fix.

The grid showed that stricter HELLO thresholds can remove false commits, but only by destroying true HELLO recall and reducing positive coverage. For example, high HELLO floors can reach very high precision and zero no-sign false commits on one seed, but HELLO recall can collapse to `0.2667` or lower. That is not acceptable for production.

This means the remaining failure is not just a threshold problem.

## Decision

Policy-only E4-AF is a no-go.

The best next action is to add targeted HELLO-like no-sign data before moving to E5-A, not to continue generic threshold sweeps or class-weight tuning.

## Approved Next Step

Prepare a bounded E4-AG HELLO-like no-sign capture/feature package, then rerun the low-motion-aware gate with the expanded no-sign set.

The capture target should emphasize:

- ordinary hand movement near the body/face;
- casual waving and non-ASL gestures;
- hands visible but not signing;
- different people, devices, distances, and backgrounds;
- front-camera conditions matching the Android app.

## Relationship To E5-A

E5-A batch candidate screening remains the next vocabulary-scale step. However, E5-A should start only after the safety floor is acceptable or after the project explicitly accepts a reduced safety target for research-only screening.

## Architecture Decisions

- E4-AF confirms ADR-RU-049: short safety floor first, then batch scaling.
- E4-AF does not invalidate the dynamic mixed recognizer.
- E4-AF does not authorize Android/export.
- E4-AF blocks further policy-only tuning unless new evidence or data is added.

## Risks

- Additional HELLO-like no-sign data may expose more false-commit modes.
- The current no-sign dataset remains small for production.
- Without streaming positives, temporal stability cannot be fully proven offline.

## Next Required Action

Prepare E4-AG targeted HELLO-like no-sign expansion, then rerun a gate candidate. Do not run another one-sign vocabulary expansion loop.

