# E6-0 Baseline Freeze And Recovery Audit

**Purpose:** Freeze and verify the current working AppHear recognition baseline before any E6 modeling or schema work.

**Scope:** Documentation and hash audit only. No Android code, model asset, recognizer configuration, dataset, feature schema, or production behavior was modified.

**Current status:** COMPLETE / BASELINE VERIFIED FOR E6 PLANNING.

**Last updated:** 2026-08-03.

## Verified Baseline Identity

- Project root: `F:\ASL DATASET\5. Apphear3`
- Git branch: `main`
- Current HEAD: `67afa5f0815e758c32878282d87b3f00b2bdbb19`
- Recovery tag present: `stable-baseline-before-redesign`
- Rollback commit recorded in prior context: `67afa5f0815e758c32878282d87b3f00b2bdbb19`

## Current Production Recognition Contract

Verified from `android/app/src/main/assets/model_manifest.json`:

- Schema version: `3.0`
- Feature dimension: `258`
- Time window: `96`
- Input shape: `[96, 258]`
- Class count: `236`
- Landmarker mode: `IMAGE`
- Quantization: `int8_weights_activations__float32_io`
- Calibration temperature: `0.6262`
- TFLite manifest short hash: `42575710a4adb0a1`

Verified from `context/feature-schema.md`: schema v3.0 is the protected `[96,258]` hand+pose contract. Face landmarks are not part of the current model input.

## Baseline Asset Hashes

| File | Size Bytes | SHA-256 |
|---|---:|---|
| `android/app/src/main/assets/streaming.tflite` | 232888 | `42575710A4ADB0A1433B58BA9093BC4E9F49401381582CC4AD304FEEB669D4BB` |
| `android/app/src/main/assets/vocab.json` | 3852 | `A7D7B08D1C9FF52455AAA93CEFEE40E744B86A11FA5047DCE08D2DD23FC0539B` |
| `android/app/src/main/assets/model_manifest.json` | 937 | `68F3B6D4DE6787883AD0737F1FBE3D44C552A4F728871B0C4E9B5CD9B2A116D3` |
| `android/app/src/main/assets/recognition_config.json` | 2118 | `DAC4B24E0746F2D346819B5357EB97C89C769A26DEC4CF42F55D8640E7AD1D36` |
| `android/app/src/main/assets/mediapipe/hand_landmarker.task` | 7819105 | `FBC2A30080C3C557093B5DDFC334698132EB341044CCEE322CCF8BCF3607CDE1` |
| `android/app/src/main/assets/mediapipe/pose_landmarker_lite.task` | 5777746 | `59929E1D1EE95287735DDD833B19CF4AC46D29BC7AFDDBBF6753C459690D574A` |


## Runtime Configuration Snapshot

Current `recognition_config.json` facts:

- `temperature`: `0.6262`
- `theta_conf`: `-1.2`
- `theta_margin`: `0.3`
- `k_stability`: `3`
- `camera_analysis`: `{'target_width': 480, 'target_height': 360}`
- `pose_cadence_experiment`: `{'hold_last_pose': True, 'pose_every_n': 2, 'enabled': True}`
- `mediapipe_delegate`: `{'mode': 'gpu'}`

Risk note: parent runtime constraints require CPU/XNNPACK/INT8 as the required fallback. The current config records `mediapipe_delegate.mode = gpu`; this is a baseline fact to preserve and test, not something E6 changes.

## Protected Files

Do not overwrite or silently mutate these during E6:

- `android/app/src/main/assets/streaming.tflite`
- `android/app/src/main/assets/vocab.json`
- `android/app/src/main/assets/model_manifest.json`
- `android/app/src/main/assets/recognition_config.json`
- `android/app/src/main/assets/mediapipe/hand_landmarker.task`
- `android/app/src/main/assets/mediapipe/pose_landmarker_lite.task`
- `pipeline/features/contract.py`
- `android/app/src/main/java/com/example/apphear/pipeline/features/S4Features.kt`
- all `android/app/src/main/assets/_backup_*` directories
- ASL Citizen and local raw/derived feature data

## Rollback Instructions

If an experimental recognition path later fails:

1. Disable the experimental feature flag.
2. Restore or keep the asset files listed above.
3. Confirm model/vocab/config hashes match this document.
4. Run the existing Android unit/build/device-smoke gates required by `context/device-smoke.md` and `ROLLBACK_AND_COMPATIBILITY_PLAN.md`.
5. Do not use any E6 model unless schema, label order, hash, and runtime parity checks pass.

## E6-0 Decision

Proceed to E6-1 audit only. Do not start E6-2 richer features, E6-3 rejection, specialists, RGB, routed simulation, Android shadow mode, or production replacement.
