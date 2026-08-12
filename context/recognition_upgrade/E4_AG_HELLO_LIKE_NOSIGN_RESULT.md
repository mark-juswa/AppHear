# E4-AG HELLO-Like No-Sign Result

**Purpose:** Record the result of adding targeted hands-visible HELLO-like no-sign footage to the signing-gate dataset.

**Scope:** Offline dataset expansion and gate retraining/evaluation only. No Android integration, TFLite export, production recognizer replacement, or vocabulary expansion.

**Current status:** COMPLETE / STRUCTURAL PASS / OFFLINE GATE PASS.

**Last updated:** 2026-08-02.

## Verified Project References

- Capture/review run: `artifacts/recognition_upgrade/e2e_c0/hello_like_p1_capture_01`
- Expansion runner: `pipeline/rgb/e4_ag_hello_like_nosign_expansion.py`
- Expanded dataset: `artifacts/recognition_upgrade/e4_generalization/e4_ag_hello_like_nosign_expansion_01`
- Gate run: `artifacts/recognition_upgrade/e4_generalization/e4_ag_low_motion_gate_01`
- Gate check: `artifacts/recognition_upgrade/e4_generalization/e4_ag_low_motion_gate_01/check_report.json`

## Capture Review Result

The reviewed HELLO-like P1 no-sign capture passed:

- rows: `160`
- eligible visible-hand no-sign rows: `116`
- no-visible-hand rows: `44`
- participants: `P03`, `P04`
- devices: `phoneA`, `phoneB`
- environment: `indoor`
- camera facing: `front`

## Expanded Dataset

The expanded no-sign tensor passed structural validation:

- base E4-AA no-sign rows: `288`
- added HELLO-like P1 rows: `116`
- combined rows: `404`
- shape: `[404,96,258]`
- split counts: train `235`, validation `78`, test `91`
- source counts: N0 `180`, P1 `108`, P1_HELLO_LIKE `116`
- mean hand-hit rate:
  - N0: `0.0277`
  - P1: `0.7068`
  - P1_HELLO_LIKE: `0.7489`

## Gate Result

The E4-AC low-motion-aware gate was rerun against the expanded E4-AG no-sign dataset.

Summary:

- mean test accepted precision: `0.9798`
- minimum test accepted precision: `0.9739`
- mean test positive coverage: `0.9746`
- minimum test positive coverage: `0.9661`
- max test no-sign false commit rate: `0.0000`
- mean/min GOOD recall: `0.9667/0.9667`
- mean/min SORRY recall: `0.9667/0.9667`

The structural check passed with `--require-metrics`.

## Interpretation

This is the first real no-sign gate result that clearly passes the offline safety floor while preserving low-motion `SORRY`.

The key improvement came from targeted data, not from generic threshold tuning:

- E4-AF showed policy-only thresholding could not remove HELLO false commits without damaging HELLO recall.
- E4-AG added HELLO-like hands-visible no-sign rows.
- The retrained gate reduced held-out no-sign false commits to `0.0000` while preserving positive coverage.

## Decision

E4-AG passes the offline signing/no-sign safety-floor gate for the current 5-class routed system.

This does not authorize Android integration or TFLite export yet. It does authorize moving to E5-A large dual-source candidate screening as the next vocabulary-scale step.

## Remaining Limits

- This is still an offline isolated-window experiment.
- The HELLO-like expansion has only two new participants and indoor/front-camera footage.
- Android streaming behavior and temporal stability remain untested.
- The current gate was trained/evaluated around a small routed vocabulary: `GOOD`, `HELLO`, `HAVE`, `KNOW`, `SORRY`, and `NO_SIGN`.

## Next Required Action

Prepare E5-A large dual-source candidate screening across:

- `F:\ASL DATASET\ASL CITIZEN`
- `F:\ASL DATASET\local`

Use existing features first and rank candidate signs into Tier A/B/C/D before any large training or Android work.

