# S2-R3 Arm A epoch 10 — debug-only phone S2 package (2026-10-17)

## What was done

S2-R3 Arm A epoch 10 is the strongest research S2 so far. Offline replay of device-recorded
observations with the experimental confirm-boundary decoder rule recognises 14/23 reviewed
phone signs; frozen S2-R2 recognises 8/23 (`RECOGNITION_V3_CONTINUOUS_RELIABILITY_2026-10-17.md`).
It had never run on the phone. This change makes it loadable on device as a third debug
package, so the blinded multi-person capture can use it.

Caveat carried into the package contract: the Arm A run ended with status
`NO_ELIGIBLE_EPOCH`. Epoch 10 is its recorded `diagnostic_fallback_epoch`, not a gate-selected
epoch. The contract marks the package `research_only: true`.

## Package identity

| Item | Value |
|---|---|
| Package id | `ARM_A_E10_CANDIDATE` |
| Asset root (debug source set only) | `android/app/src/debug/assets/phone_causal_recognition_01/s2_r3_arm_a_e10_candidate/` |
| Source checkpoint | `s2_r3_arm_a_01/epoch_10.keras` `17915b023694cec1c85f10f96b44608c95f06ef655c49b7d1453c3a4a47b1c7c` |
| Source FIT normalization | `s2_r3_arm_a_01/normalization.json` `754e5e0e05e012333cd96170ba63602c26d7ab2a8b87ae8e3af99d76ed1268dc` |
| FP32 TFLite | `s2_r3_arm_a_e10_fp32.tflite` `e7725ef2602b83aedac8c2bfdab3ab2293b7e471061f9d4019f4454f6f68f295` |
| Normalization asset | `normalization.json` `35473a783fd9340480c72a0c9b028871ca98eeb132b3bca6b4341b38e97914c0` |
| Contract | `contract.json` `d5f4e2b17c16f92db779d16621660af7681d7c2d26cca41a23279b5f75393e15` |
| Feature contract | `apphear.perception_vnext.segmentation_features.v1` `[378]`; PRE_IDLE / ACTIVE_SIGN / POST_RECOVERY; receptive field 61; 123,779 params |

`PhoneS2Runner` refuses to load the package unless the contract's checkpoint hash,
normalization hash, package id, `research_only` flag, normalization-asset hash and TFLite hash
all match. This is the same fail-closed check S2-R2 uses, plus the `research_only` flag.

## Host parity (Keras vs TFLite)

Run with `deploy/export_s2_r3_arm_a_phone.py export --source-root <main checkout>`. The script
uses the main checkout's `.venv` (TF 2.21.0, Keras 3.15.0, the version that saved both
checkpoints). The system Python's Keras 3.13.2 cannot deserialize them.

- Fixture: the same 669 prior-phone observations the S2-R2 export used. These are
  `session_20260921T153138Z`, read from the committed asset
  `s2_r2_candidate/phone_parity_raw_features.f32` (`17ed546b…7618`), and their hash is checked
  against the frozen S2-R2 contract.
- Method: identical to S2-R2. Keras runs the full sequence. TFLite runs once per observation on
  a rolling prefix of at most 61 observations and keeps only the last output.
- **Max absolute probability difference: `1.31e-6`. Argmax state mismatches: 0 / 669.**
  The tolerance is `1e-4`. For reference, S2-R2 gave `8.64e-7` with zero mismatches.
- TFLite argmax state counts on this stream: PRE 20, ACTIVE 64, POST 585. This is descriptive
  only and not an evaluation; the stream was already development-exposed.

`tests/test_s2_r3_arm_a_phone_package.py` re-checks the committed package without the
git-ignored checkpoint: all hashes, exact normalization, and TFLite against the stored
probabilities (≤1e-4, identical argmax). Both tests pass.

## Android wiring (debug only)

- `PhoneS2Runner.kt` (main) gains one enum entry. Release still hard-codes
  `APP_PHONE_S2_PACKAGE = S2_R2_CANDIDATE`. The debug Gradle property `apphearPhoneS2Package`
  still accepts only `S2_R2_CANDIDATE` / `PHASE7_CONTROL`, so the normal app can never select
  Arm A. Its assets exist only in the debug source set.
- `PerceptionVNextLiveRecognitionActivity` (debug) accepts `--es phone_s2_package
  ARM_A_E10_CANDIDATE` under the same opt-ins as S2-R2: the validation cohort or transition
  diagnostics, exact-parity evidence, `PRE_OR_POST_EXPERIMENTAL` re-arm, and a declared signer.
  Failures report `ARM_A_E10_*` reasons. Transition diagnostics now accept either research
  candidate. The S2-R2 and Phase-7 code paths, their failure strings, and the default
  (`PHASE7_CONTROL` when the extra is omitted) are unchanged.
- The session identity already records `s2_package_id`. With the validation-cohort extra, the
  cohort label stays `S2_R2_VALIDATION_6`, which is the same six targets. Read `s2_package_id`
  to tell which package ran.
- `PhoneS2ParityInstrumentedTest.armAE10PhonePrefixMatchesKerasExportOnTheS2R2PhoneFixture`
  is the on-device check. Normalization must match within 1e-6, probabilities within 1e-4, and
  argmax mismatches must be zero. It also checks that the Phase-7 and S2-R2 packages still load.
  It logs `ARM_A_E10 device parity: …` under the tag `PhoneS2Parity`.

## Build and device parity

Built credential-free with
`tools/android/build_working_baseline.ps1 -Configuration fake -OriginalWords -Tasks testDebugUnitTest,assembleDebug,assembleDebugAndroidTest,--continue`
(JDK 17). `android/gradle.properties` was copied from `gradle.properties.example`, with empty
values; no real properties were copied.

- That first build (harness flags off) produced `app-debug.apk` `f65a83e1…4c1`. It contains the
  Arm A package; the TFLite is stored uncompressed, so it maps the same way as S2-R2.
- The APK pair now in `android/app/build/outputs/apk/` was rebuilt for live capture with
  `-Tasks assembleDebug,assembleDebugAndroidTest,-PperceptionVNext=true,-PphoneCausalRecognition=true,-PrecognitionV3ParallelHands=false,-PrecognitionV3Profile=false`
  (BUILD SUCCESSFUL). BuildConfig: `PERCEPTION_VNEXT_ENABLED = true`,
  `PHONE_CAUSAL_RECOGNITION_ENABLED = true`, `APP_PHONE_S2_PACKAGE = "S2_R2_CANDIDATE"`, so the
  default is unchanged.
  - `app-debug.apk` `6d37fa12d2cda092c39f6774b8b2f9cbcf65c4602abfd244f1b11d8d890639b8`
  - `app-debug-androidTest.apk` `25e6ce419eb6cb32f3292f3952ee4476381323d5b9e89d9b9565b6d752e34ebc`
- Kotlin compiles. Unit tests: 199 / 200 pass. The one failure,
  `OriginalWordBatchTest.all203PayloadsMatchPinnedManifestAndNamedAnimation`, was there before
  this change and is unrelated. It happens because the working-tree
  `src/main/assets/asl_animations/manifest.json` hashes to `bd6200cd…` in every checkout on this
  machine, including the main checkout, while the committed blob is `ec2d0714…`. This looks like
  a line-ending conversion. The file is not touched here.

**Device parity: PASS (2026-10-17 16:02).**

- Device: `3ab64582`, model M2101K7AG (`sunny_global`), the only device `adb devices -l` listed.
- Installed the `6d37fa12…` / `25e6ce41…` pair with `adb install -r`. `firstInstallTime` stayed
  `2026-10-15 20:28:05` before and after, so app data and on-device sessions were kept.
  `connectedDebugAndroidTest` was not used.
- `armAE10PhonePrefixMatchesKerasExportOnTheS2R2PhoneFixture`: `OK (1 test)`. Logcat:
  `ARM_A_E10 device parity: observations=669 max_abs_prob_diff=4.7683716E-7 argmax_mismatches=0`.
  Normalization matched the host within 1e-6 on every feature, and each probability matched
  within 1e-4.
- Full `PhoneS2ParityInstrumentedTest` class: `OK (4 tests)` in 6.27 s. That covers Phase-7 CAL
  prefix parity, S2-R2 phone-prefix parity with the control still loadable, the diagnostic-row
  invariance check, and Arm A.

The first device run had been blocked because `adb devices` listed no phone. The commands
used, from the worktree root, were (do not use `gradlew connectedDebugAndroidTest`, because it
uninstalls the app and its on-device data):

```powershell
$adb = 'D:\AndroidStudio\Android\Sdk\platform-tools\adb.exe'
& $adb devices -l
& $adb install -r android/app/build/outputs/apk/debug/app-debug.apk
& $adb install -r android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
& $adb shell am instrument -w -r -e class com.example.apphear.perceptionvnext.PhoneS2ParityInstrumentedTest#armAE10PhonePrefixMatchesKerasExportOnTheS2R2PhoneFixture com.example.apphear.test/androidx.test.runner.AndroidJUnitRunner
& $adb logcat -d -s PhoneS2Parity:I
# Regression for the frozen packages (same class, all four tests):
& $adb shell am instrument -w -r -e class com.example.apphear.perceptionvnext.PhoneS2ParityInstrumentedTest com.example.apphear.test/androidx.test.runner.AndroidJUnitRunner
```

Pass means `OK (1 test)` (or `OK (4 tests)` for the full class) and a logcat line reporting
`observations=669` and `argmax_mismatches=0`, with the max difference ≤ 1e-4.

Live capture opt-in (debug only), added to the existing launch extras:
`--ez phone_causal_enabled true --es phone_s2_package ARM_A_E10_CANDIDATE --ez s2_exact_parity_capture true --es phone_rearm_policy PRE_OR_POST_EXPERIMENTAL --es validation_signer_id <id>`,
plus either `--ez continuous_transition_diagnostics true` or `--ez s2_r2_validation_cohort true`.

## Rollback

Omit the `phone_s2_package` extra or pass `PHASE7_CONTROL` / `S2_R2_CANDIDATE`. To remove the
package entirely, delete the `s2_r3_arm_a_e10_candidate` asset directory, the enum entry, the
activity guard block, and the test. No production asset or default is touched.

## Not done / out of scope

No live capture yet; device parity passed. No confirm-boundary decoder change on device: the 14/23 figure depends on
that rule, which remains offline-only. No new evaluation data, and no TEST, E6 or Tier 3 data
was opened.
