# Phase 1.2 — Shadow-Validation Debug APK: Build Report

Date: 2026-11-09 (UTC build time 13:51–13:54) · Nothing committed or pushed.

**Status: APK built and verified. Physical-device validation has NOT been performed — no physical device was connected.** The only Android device available during this work was an arm64 emulator, and it disappeared (shut down) before the final install step.

Evidence labels: **[CONFIRMED-RUN]** executed and observed in this task · **[CONFIRMED-FILE]** read from a produced file · **[NOT VERIFIED]**.

## 1. Deliverable

| Item | Value |
|---|---|
| File | `artifacts/phase-1.2/apphear-phase-1.2-shadow-validation-debug.apk` |
| Checksum file | `artifacts/phase-1.2/apphear-phase-1.2-shadow-validation-debug.apk.sha256` |
| Size | **331,144,659 bytes (≈ 316 MiB)** |
| SHA-256 | `abd1fa9e2b1827214cd8329490b8e13c3eecf98ddee6e5336e9d5d6ffa81d8f3` |
| Byte-identical to the Gradle output | yes (`cmp`) |

`artifacts/` and `*.apk` are git-ignored, so the file does not appear in `git status`.

## 2. Build

| Item | Value |
|---|---|
| Module / task | `:app` (the only module, `include(":app")`) → `assembleDebug` |
| Working directory | `android/` of the real working tree (not a copy) |
| Command (exact) | `sh ./gradlew assembleDebug -PshadowEval=true -Pandroid.useAndroidX=true -Pandroid.nonTransitiveRClass=true -Pkotlin.code.style=official -Dorg.gradle.jvmargs="-Xmx3g -Dfile.encoding=UTF-8" --no-daemon` |
| Why the extra `-P` flags | `android/gradle.properties` is git-ignored and does not exist in this checkout; the three `-P` values are the ones from `gradle.properties.example`, passed on the command line so **no project configuration file was created or changed**. `sh ./gradlew` was used so the wrapper's file mode (tracked, 100644) was not changed. |
| Toolchain | repo wrapper → Gradle 8.13 (downloaded on demand), AGP 8.11.2, Kotlin 2.0.21, JDK 17, Android SDK build-tools 36.0.0, compileSdk/targetSdk 36 |
| Result | **BUILD SUCCESSFUL in 2m 23s**, 38 tasks executed, exit 0 **[CONFIRMED-RUN]** |
| Variant | `debug` (`BUILD_TYPE="debug"`, `DEBUG=true`, `application-debuggable`) — **not** a release APK **[CONFIRMED-FILE]** |
| Reproducibility | A second build of the same sources (in a scratch copy, Phase 1.1) produced a **byte-identical APK** (same SHA-256 and all 1,542 entry CRCs equal). |

### 2.1 Built from the current working tree
State recorded **before** the build and re-checked **after** it (identical, so the build did not alter the tree):

| | Value |
|---|---|
| `HEAD` | `1f9e571a8571e78eb06995d6d7f1f2990027608a` (branch `jepjep-claude`) |
| SHA-256 of `git diff` (tracked changes) | `d9cd0ae55e2c99529d2423ff2eefb5f6119c9f5cb8c350d2fc9f108412cd2840` |
| SHA-256 over all untracked, non-ignored files | `4b0f6619a30b307f60cca323be9eff7cf634cf480e175ba38f3bc8ba090de177` |
| Changed/untracked entries | 18 (Phase 1, 1.1 and this phase's documents/code; nothing reverted, nothing committed) |

So the APK contains Phase 1 (commit gate) and Phase 1.1 (shadow log) exactly as they are in the tree. The Gradle outputs (`android/app/build`, `android/.gradle`) are git-ignored.

## 3. Build configuration (generated `BuildConfig`, debug) **[CONFIRMED-FILE]**

| Field | Value | Meaning |
|---|---|---|
| `APPLICATION_ID` | `com.example.apphear` | correct |
| `SHADOW_EVAL_ENABLED` | **true** | shadow logging compiled in (from `-PshadowEval=true`) |
| `WORD_COMMIT_GATE_ENABLED` | **true** | gate ON (the default; `-PwordCommitGate` not passed) |
| `APP_PHONE_S2_PACKAGE` | `S2_R2_CANDIDATE` | STABLE segmenter |
| `RECOGNITION_V3_PARALLEL_HANDS_ENABLED` | false | existing default (serial hands) |
| `FINGERSPELL_EXPERIMENT_ENABLED` | false | WORD recognition only |
| `CONTEXT_PHRASE_ASSIST_ENABLED` | false | no cloud context assist |
| `LLM_FALLBACK_ENABLED` / `SENTENCE_ASSIST_MODE` | false / `OFF` | no cloud LLM, no sentence assist |
| `PROFILE_ACCOUNTS_ENABLED` | false | no accounts |
| `ELEVENLABS_API_KEY`, `SUPABASE_URL` | empty | **no service keys embedded**; "Hear" uses on-device TTS |

Recognition thresholds are untouched: STABLE floor 0.55 and EXPERIMENTAL floor 0.75 come from `PhoneRecognitionConfiguration.commitPolicy()` (no source change in this task). No recognition code, model, vocabulary, camera or security setting was changed to obtain the build.

## 4. APK verification

| Check | Result |
|---|---|
| Exists, non-empty | 331,144,659 bytes **[CONFIRMED-RUN]** |
| ZIP integrity | `unzip -t`: no errors |
| Signature | `apksigner verify`: **Verifies**; scheme **v2 = true** (v1/v3/v3.1/v4 false), 1 signer, `CN=Android Debug` (the standard debug key `~/.android/debug.keystore`). Debug-signed only — not suitable for Play distribution. |
| Package identity | `aapt2 dump badging`: `com.example.apphear`, versionCode 1, versionName 1.0, compileSdk/targetSdk 36, `application-debuggable` |
| Permissions | `CAMERA`, `INTERNET`, `ACCESS_NETWORK_STATE` (+ the AndroidX dynamic-receiver permission) |
| Native libs | `libperceptionvnext.so` (arm64-v8a only), ONNX Runtime, TFLite, MediaPipe; **the recognition path requires an arm64 device** (existing behaviour, `PhoneProductionSession.load` checks `arm64-v8a`) |
| Model assets packaged byte-for-byte | 9 of 9 sampled files have the same SHA-256 inside the APK as in `android/app/src/main/assets`: `dwpose_t_singlepass.onnx`, `hand_landmarks_detector.tflite`, `s2_r2_fp32.tflite`, `s2_phase7_fp32.tflite`, `materializer_contract_frozen.json`, `ordinary_v2_tcn_fp32.tflite`, Gate-2 `manifest.json`, `phase4a_gate4a1_live/contract.json`, `vocab.json` |
| Recognition-v2 model pin | packaged `ordinary_v2_tcn_fp32.tflite` SHA-256 = `1ccf0afa…2880c` = `RecognitionV2LiveRecognizer.MODEL_SHA` |
| Vocabulary | packaged Gate-2 manifest has **236** `class_index_to_gloss` entries, schema `apphear.perception_vnext.recognition.v2` |
| Experimental package assets present | `s2_r3_arm_a_e10_candidate/*` and `word_blend_candidate_*` are in the APK, so Experimental *can* load. **Runtime selection was not exercised** — see §6. |

## 5. Installation verification

| Check | Result |
|---|---|
| `adb devices` at install time | **no device listed** (the emulator seen earlier had shut down) **[CONFIRMED-RUN]** |
| Install of the deliverable file | **not performed in this task** |
| Physical-device validation | **NOT PERFORMED** |

**Indirect, emulator-only evidence (not physical-device validation).** In Phase 1.1 an arm64 emulator (`sdk_gphone16k_arm64`, Android SDK 37, virtual camera) installed and ran an APK built from the same sources, **and that APK has the same SHA-256 as the deliverable**, so the bytes are identical. On it (camera permission granted with `pm grant`, recognition screen opened via the debug alias): install succeeded; the Candidate01 session loaded (`configuration=STABLE … fallback=false`); the shadow log was created with a run label and a `session_start` line showing `gate_enabled=true`; camera-generation resets and a `session_end` summary (`written=3 dropped=0 write_failures=0`) were logged; no crash or ANR. See `docs/PHASE_1_1_SHADOW_VALIDATION.md` §8.3.

**Not verified for this APK on any device:** the runtime camera-permission dialog, the live camera preview on screen, any sign event, Stable ↔ Experimental selection at runtime, and behaviour on the target Xiaomi M2101K7AG.

## 6. Build warnings and errors
- **Errors: none.**
- **Warnings: 10, all Kotlin deprecations, none introduced by Phase 1/1.1/1.2 code.** Nine are `ImageAnalysis.Builder.setTargetResolution` (eight in debug research activities: `P7dRuntimeActivity`, `P7dr1…`, `P7dr2…`, `P7eRuntimeActivity`, `P8bRuntimeActivity`, `P8c3b1CaptureActivity`, `PerceptionVNextActivity`, `PerceptionVNextLiveRecognitionActivity`; and one in `RecognitionActivity.kt:817`, the production camera binding, already noted as reconnaissance finding F-020). One is `LoadingActivity.overridePendingTransition`.
- Gradle downloaded the wrapper distribution (8.13) from services.gradle.org; dependencies resolved from the repo's configured Google/Maven Central repositories. No security setting was disabled.

## 7. Limitations (outstanding)
1. **No physical-device run.** The exact checks you asked for (permission flow, preview, session load, shadow init on a phone) are unverified on real hardware and must be done with §8.
2. **Debug build only**: debug-signed, debuggable, ≈ 316 MiB, contains ~15 exported debug research activities, and is for study devices only. It is not a release candidate and must not be distributed.
3. **WORD recognition only**: FINGERSPELL, Context Assist, cloud TTS/LLM and accounts are off in this build.
4. **Settings lists four engines** (Stable, Experimental, Blend 01, Blend 02). **Use only Stable and Experimental for this study.** The Blend entries have no calibrated confidence floor (only the structural no-hand rule applies) and are outside the Phase 1 evidence.
5. **Experimental can silently fall back to Stable** if it fails to load; confirm `fallback=false` in logcat (and in the log's `session_start`/event lines) before every Experimental run.
6. arm64 only for recognition; 4 KB-aligned `libperceptionvnext.so` (reconnaissance F-006) — irrelevant to sideloading, relevant to any future Play release.
7. The shadow log is only a measurement aid: **this APK does not by itself provide accuracy evidence** (see `docs/PHASE_1_1_SHADOW_VALIDATION.md` §0).

## 8. Physical-device testing instructions

### 8.1 Prepare the phone
1. Use an **arm64** Android phone (target: Xiaomi M2101K7AG). Enable Developer options → **USB debugging**; connect by USB and accept the RSA prompt.
2. On the computer: `adb devices` must list the phone as `device`.

### 8.2 Verify and install
```bash
cd <repo>/artifacts/phase-1.2
shasum -a 256 apphear-phase-1.2-shadow-validation-debug.apk
#   expect abd1fa9e2b1827214cd8329490b8e13c3eecf98ddee6e5336e9d5d6ffa81d8f3
adb install -r apphear-phase-1.2-shadow-validation-debug.apk
```
`-r` keeps existing app data (repo rule: do not clear data by default). For a clean participant start, run `adb shell pm clear com.example.apphear` deliberately and note it. If the install is slow, the file is ≈ 316 MiB. To remove: `adb uninstall com.example.apphear`.

### 8.3 Startup checklist (record pass/fail for each; these are exactly the items not yet verified)
1. **Launch** AppHear from the launcher: it starts without a crash (`adb logcat -s AndroidRuntime:E` stays empty).
2. Open **ASL Recognition**; the **camera permission dialog** appears; choose "While using the app". Denying must show the app's "camera permission needed" message, not a crash.
3. **Camera preview** appears and the HUD shows an fps value.
4. `adb logcat -s AppHearPhone` shows `configuration=STABLE package=S2_R2_CANDIDATE … fallback=false` (the recognition session loaded; allow a few seconds for model load).
5. **Shadow logging initialised:** `adb shell run-as com.example.apphear ls -l no_backup/shadow_eval` lists a `shadow_*.jsonl` whose first line is `"type":"session_start"` with `"meta_gate_enabled":"true"`.
6. Close the screen; the file's last line is `"type":"session_end"` with `dropped` and `write_failures` equal to 0.
7. **Select Experimental:** Settings → "Recognition engine (debug)" → "Experimental - Arm A e10 + confirm-boundary"; **reopen ASL Recognition**; logcat must show `configuration=EXPERIMENTAL … fallback=false`. If it shows `STABLE` with `fallback=true`, Experimental failed to load — report it. Select Stable again for Stable runs.
8. Show a hand and sign; at least one `"type":"event"` line should appear (the first time an `event` line is written on real hardware).

### 8.4 Running a study session
Follow `docs/PHASE_1_1_SHADOW_VALIDATION.md` §5 (protocol) and §8.1 (run label, session conduct, log pull, label freeze, analysis). In short: set the run label before opening the recognition screen,

```bash
adb shell "run-as com.example.apphear sh -c 'mkdir -p no_backup/shadow_eval && echo E01_normal_normal_natural_r1 > no_backup/shadow_eval/run_label.txt'"
```

record the signer with a separate camera that does not show the phone screen, then pull the logs:

```bash
adb exec-out run-as com.example.apphear sh -c 'cd no_backup/shadow_eval && tar cf - shadow_*.jsonl' > logs.tar
```

Participants must have consented to the external video and to the log contents (predicted words, probabilities, timings; no images or identifiers). Delete with `adb shell pm clear com.example.apphear` when requested.

### 8.5 If something fails
Capture `adb logcat -d > logcat.txt`, the `session_end` line, and the phone model/Android version; do not work around a failure by changing recognition code or disabling checks — report it.

## 9. Not committed
No commit, push, or branch change was made; all project changes from earlier phases are preserved.
