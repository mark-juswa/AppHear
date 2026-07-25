# Android UI Reference Correction

Last updated: 2026-07-22
Status: Home/dashboard, Recognition, Text-to-ASL, and Settings/Profile UI corrected to AppHear2 XML/assets and build green; splash/loading corrected and build green

## Purpose

Track the correction pass requested after the initial AppHear3 UI migration drifted from the AppHear2 reference. This file is the working checklist for comparing `context/design/` screenshots, AppHear2 XML/resources, and the current AppHear3 native Kotlin/XML implementation.

## Scope

This document covers UI fidelity only: screen layout, navigation presentation, typography, colors, drawables, icons, cards, bottom sheets, and assets. It does not authorize changes to recognition, prediction confirmation, CameraX, MediaPipe, TFLite, temporal buffering, model assets, runtime configuration, or feature-schema contracts.

## Source-of-truth files

- AppHear3 target app: `F:/ASL DATASET/5. Apphear3/android/`
- AppHear3 screenshot reference folder: `F:/ASL DATASET/5. Apphear3/context/design/`
- AppHear2 UI reference app: `D:/Programming/MOBILE APP/3.1 New Way/backup/AppHear2/`
- AppHear2 layouts: `D:/Programming/MOBILE APP/3.1 New Way/backup/AppHear2/app/src/main/res/layout/`
- AppHear2 visual resources: `D:/Programming/MOBILE APP/3.1 New Way/backup/AppHear2/app/src/main/res/drawable/`, `.../font/`, `.../values/`

## Related context documents

- `context/android-screen-mapping.md`
- `context/android-design-system.md`
- `context/android-migration-plan.md`
- `context/android-ui-architecture.md`
- `context/device-smoke.md`
- `context/progress-tracker.md`

## Screenshot inventory and correction status

| Screenshot | AppHear2 implementation to inspect | AppHear3 target | Current correction status |
|---|---|---|---|
| `context/design/homapage.jpg` | `activity_main.xml`, `item_feature_card_detect.xml`, `item_feature_card_project.xml`, `nav_bottom.xml`, `FeatureCardAdapter.java` | `MainActivity`, `HomeFragment`, `activity_app_shell.xml`, `nav_bottom.xml` | Corrected 2026-07-21; build/unit green |
| `context/design/recognition_screen_collapsed.jpg` | `activity_sign_detect.xml`, detection drawables, SignDetect visual controls only | `RecognitionActivity`, `activity_recognition.xml` | Corrected visually with collapsible bottom sheet; runtime smoke passed |
| `context/design/recognition_screen_uncollapsed.jpg` | `activity_sign_detect.xml`, bottom controls expanded/collapsed behavior | `RecognitionActivity`, `activity_recognition.xml` | Corrected visually with expanded content; AppHear2 recognition logic not copied |
| `context/design/text_to_asl_collapsed.jpg.jpg` | `texttoasl/activity_text_to_asl.xml`, text-to-ASL drawables/assets | `TextToAslFragment` | Corrected visually; route-specific device screenshot pending due MIUI ADB tap block |
| `context/design/text_to_asl_uncollapsed.jpg` | `texttoasl/activity_text_to_asl.xml`, expanded controls | `TextToAslFragment` | Corrected visually with expanded content; WebView/GLB/speech behavior still gated |
| `context/design/settigns.jpg` | `activity_profile.xml`, profile card, settings rows | `ProfileFragment` / `SettingsFragment` | Corrected 2026-07-22; spelling is filename as provided |
| `context/design/settings_preference.jpg` | `activity_profile.xml`, `row_setting_*.xml`, profile/settings resources | `SettingsFragment` / `ProfileFragment` | Corrected 2026-07-22; passive UI rows only |
| `context/design/settings_preference_2.jpg` | `activity_profile.xml`, `row_setting_*.xml`, profile/settings resources | `SettingsFragment` / `ProfileFragment` | Corrected 2026-07-22; passive UI rows only |
| `context/design/splash.jpg` | `activity_splash.xml`, `bg_splash_screen.xml`, `splash.png` | `SplashActivity` launcher/onboarding visual | Corrected 2026-07-22; first-run gate only |
| `context/design/loading_screen.jpg` | `activity_loading.xml`, `applogo.png`, loading drawables | `LoadingActivity` visual transition | Corrected 2026-07-22; bounded visual transition only |

## Verified incorrect areas from the current AppHear3 approximation

| Area | Incorrect AppHear3 state before correction | Required AppHear2 reference behavior | Current status |
|---|---|---|---|
| Home header | Text-only Material-style header | Avatar circle with `account.png`, `Welcome Back,`, `AppHear User`, `Ready` status pill | Corrected |
| Home hero | Single generic headline/body | `Your communication companion`, split `Bridge Every` / `Conversation` display text | Corrected |
| Home recent area | Generic recent activity chip | `Recent Signs` horizontal chip row using AppHear2 active/inactive chip drawables | Corrected with truthful empty chip; no old RecentSignsStore copied |
| Home feature cards | Material cards without mascots | AppHear2 ViewPager2 with `mascot_detect.png`, `mascot_project.png`, exact live badges, typography, dots | Corrected with Kotlin adapter |
| Bottom navigation | Generic Material BottomNavigationView and Android system icons | AppHear2 custom active circle + inactive pill using `homes.png`, `user_images.png`, `wave_hand.png`, `users.png` | Corrected visually in shell; active-state variants for non-home screens still pending |
| Fonts/assets | No AppHear2 Inter fonts or mascots | Inter font weights and selected AppHear2 Home/nav assets | Home/nav slice imported; provenance/license still marked open |

## Home correction source files changed

- `android/app/src/main/res/layout/fragment_home.xml`
- `android/app/src/main/res/layout/activity_app_shell.xml`
- `android/app/src/main/res/layout/nav_bottom.xml`
- `android/app/src/main/res/layout/item_feature_card_detect.xml`
- `android/app/src/main/res/layout/item_feature_card_project.xml`
- `android/app/src/main/java/com/example/apphear/MainActivity.kt`
- `android/app/src/main/java/com/example/apphear/ui/shell/AppShellActivity.kt`
- `android/app/src/main/java/com/example/apphear/ui/home/HomeFragment.kt`
- `android/app/src/main/java/com/example/apphear/ui/home/FeatureCardAdapter.kt`
- `android/gradle/libs.versions.toml`
- `android/app/build.gradle.kts`
- selected non-conflicting AppHear2 Home/nav drawable/font resources under `android/app/src/main/res/`

## Dependencies

- Added `androidx.viewpager2:viewpager2:1.1.0` because AppHear2 Home uses `ViewPager2` for the feature-card carousel.
- Did not add `androidx.cardview`; AppHear2 card XML was adapted to existing Material Components `MaterialCardView`.
- Did not change CameraX, MediaPipe, TensorFlow Lite, Kotlin, AGP, model, or runtime dependencies.

## Assumptions

- `No recent signs` is a truthful placeholder until a real AppHear3 history/data-retention contract exists.
- Home feature card click for detection opens AppHear3 `RecognitionActivity`, not AppHear2 `SignDetectActivity`.
- Home feature card click for projection navigates to the current native `TextToAslFragment` shell.
- AppHear2 font/mascot/icon provenance still needs release confirmation before final distribution.

## Decisions

- Use AppHear2 XML/layout metrics directly where compatible.
- Rebuild behavior in Kotlin instead of copying AppHear2 Java application/auth/recent-store logic.
- Keep `RecognitionActivity` as the only recognition runtime destination.
- Treat remaining screenshot pages as pending UI correction work before later feature migration resumes.

## Known risks

- Screenshot-level visual QA is still required on a physical device; ADB listed no attached devices during the 2026-07-21 Home correction check.
- Bottom-nav active visual state currently matches the Home screenshot first; per-destination selected styling must be handled when correcting Text-to-ASL/Profile/Settings screenshots.
- Imported raster/font assets may affect APK size and require provenance/license confirmation.
- Recognition UI correction is high risk because it touches the camera screen; preserve existing ids/binding or adapt only presentation around the AppHear3 runtime code.

## Current status

Home/dashboard has been corrected against AppHear2 `activity_main.xml` and related components. Verification completed: `assembleDebug` passed, `testDebugUnitTest` passed, and protected AppHear3 model/config/MediaPipe asset hashes matched the rollback backup. Next UI correction should be either `RecognitionActivity` visual layout from `activity_sign_detect.xml` with protected runtime bindings, or `TextToAslFragment` from `activity_text_to_asl.xml` if choosing the safer non-camera screen first.
## 2026-07-21 Recognition UI correction

Purpose: correct `RecognitionActivity` against `context/design/recognition_screen_collapsed.jpg`, `context/design/recognition_screen_uncollapsed.jpg`, and AppHear2 `activity_sign_detect.xml` while keeping AppHear3 recognition runtime as source of truth.

Changed files:

- `android/app/src/main/res/layout/activity_recognition.xml`
- `android/app/src/main/java/com/example/apphear/RecognitionActivity.kt`
- selected non-conflicting AppHear2 recognition drawables under `android/app/src/main/res/drawable/`

Imported recognition UI resources:

- `gradient_top.xml`, `gradient_bottom.xml`, `arrow.png`, `flip.png`, `circle_btn_white.xml`, `bg_landmark_toggle.xml`, `hand_recognition.png`, `btn_start_bg.xml`, `btn_stop_bg.xml`, `play.png`, `soundwaves.png`, `ic_conversation.xml`, `bar_track.xml`, `bar_fill.xml`, `bg_white_pill.xml`, `bg_detect_card.xml`, `ic_replay.xml`, `ic_volume.xml`, `bg_glass_pill.xml`.

Decisions:

- Preserved AppHear3 binding/runtime IDs: `previewView`, `overlayView`, `fpsText`, `handToggle`, `cameraToggle`, `sentenceText`, `clearButton`, `glossText`, `altText`, and `degradedBanner`.
- Adapted AppHear2 `LandmarkOverlayView` reference to AppHear3 `OverlayView`; no old face overlay or old recognition classes were copied.
- Kept AppHear3 automatic recognition startup. The AppHear2 START visual is represented as a passive `LIVE` indicator, not as old start/stop detection logic.
- Added only UI-safe actions: top back button calls `finish()`, drag handle toggles bottom-sheet expanded content.

Verification:

- `assembleDebug --console=plain --no-daemon --max-workers=2`: PASS.
- `testDebugUnitTest --console=plain --no-daemon --max-workers=2`: PASS.
- Protected AppHear3 model/config/MediaPipe asset hashes match rollback backup.
- Device smoke on Xiaomi `M2101K7AG`, Android 12 SDK 31: installed debug APK, launched `com.example.apphear/.RecognitionActivity`, GPU landmarkers loaded, recognizer loaded `window=96 classes=236`, `AppHearPerf` streamed frames. No crash/ANR from the UI change. ADB permission grant remains denied by MIUI, but the permission prompt was handled on device and runtime started.
- Device screenshot captured at `C:/Users/Gigabyte/.codex/visualizations/2026/07/21/019f834f-c7cd-7053-89a4-245ab1a0b669/apphear-device-smoke/recognition_ui.png`.

Known remaining gaps:

- Manual visual comparison against the screenshots is still required by the developer because automated image inspection is unavailable in this Windows sandbox.
- The bottom-sheet selected/collapsed state is UI-only; no AppHear2 detection lifecycle was migrated.
- Text-to-ASL, settings/preferences, splash, and loading screenshots remain pending.
## 2026-07-21 Text-to-ASL UI correction

Purpose: correct `TextToAslFragment` against `context/design/text_to_asl_collapsed.jpg.jpg`, `context/design/text_to_asl_uncollapsed.jpg`, and AppHear2 `activity_text_to_asl.xml` while avoiding premature import of AppHear2 avatar, speech, WebView, GLB, TTS, or recent-store behavior.

Changed files:

- `android/app/src/main/res/layout/fragment_text_to_asl.xml`
- `android/app/src/main/java/com/example/apphear/ui/texttoasl/TextToAslFragment.kt`
- selected non-conflicting AppHear2 Text-to-ASL drawables under `android/app/src/main/res/drawable/`

Imported Text-to-ASL UI resources:

- `bg_circle_tan.xml`, `bg_toggle_container.xml`, `bg_toggle_active.xml`, `bg_toggle_inactive.xml`, `ic_mic.xml`.

Decisions:

- AppHear2 `WebView` was represented by a native placeholder stage instead of enabling avatar playback. The real WebView/GLB path remains gated by asset provenance, size, privacy, and lifecycle/security contracts.
- Speech mode remains a deferred UI state. AppHear2 `SpeechInputManager`, `RecognizerIntent`, ElevenLabs, and Android TTS behavior were not copied.
- Existing safe preview behavior remains: text input updates the displayed phrase and reports that animation mapping is not connected yet.
- `RESPOND` opens AppHear3 `RecognitionActivity`.

Verification:

- `assembleDebug --console=plain --no-daemon --max-workers=2`: PASS.
- `testDebugUnitTest --console=plain --no-daemon --max-workers=2`: PASS.
- Protected AppHear3 model/config/MediaPipe asset hashes match rollback backup.
- Device install and `MainActivity` launch succeeded on Xiaomi `M2101K7AG`; no app crash was found in filtered logs. MIUI denied ADB `input tap` (`INJECT_EVENTS`), so route-specific Text-to-ASL visual screenshot remains pending unless manually tapped or a debug-only navigation hook is added.

Known remaining gaps:

- Manual visual QA against the two Text-to-ASL screenshots is still required.
- Splash and loading screenshots remain pending.
## 2026-07-22 Settings/Profile UI correction

Purpose: correct `ProfileFragment` and `SettingsFragment` against `context/design/settigns.jpg`, `context/design/settings_preference.jpg`, `context/design/settings_preference_2.jpg`, and AppHear2 `activity_profile.xml` / `row_setting_*.xml` while avoiding AppHear2 auth, persistence, backend, or runtime-setting behavior.

Changed files:

- `android/app/src/main/res/layout/fragment_profile.xml`
- `android/app/src/main/res/layout/fragment_settings.xml`
- `android/app/src/main/res/values/strings.xml`
- selected non-conflicting AppHear2 profile/settings drawables under `android/app/src/main/res/drawable/`
- selected AppHear2 visual row layouts under `android/app/src/main/res/layout/row_setting_*.xml`

Imported Settings/Profile UI resources:

- `bg_profile_card_white.xml`, `bg_profile_avatar_teal.xml`, `bg_auth_input_large.xml`, `bg_settings_panel_coffee.xml`, `bg_setting_row.xml`, `bg_setting_value_pill.xml`, `bg_teal_pill_btn.xml`.
- `row_setting_account_type.xml`, `row_setting_voice.xml`, `row_setting_detection.xml`, `row_setting_smart_detection.xml`, `row_setting_low_latency.xml`, `row_setting_dup_suppression.xml`, `row_setting_hand_gate.xml`, `row_setting_run_face.xml`, `row_setting_rotate_offload.xml`, `row_setting_parallel_detectors.xml`, `row_setting_profiling.xml`, `row_setting_core_model_v3.xml`, `row_setting_extended_vocab.xml`, `row_setting_accessibility.xml`, `row_setting_privacy.xml`, and `row_setting_about.xml`.

Decisions:

- AppHear2 profile/auth Java logic, Supabase behavior, local preference persistence, and runtime-setting behavior were not copied.
- AppHear2 switch rows were initially imported as passive visuals, then the AppHear2-only/beta runtime rows were removed from visible Profile/Settings screens: Detection Preferences, Smart detection beta, Low-latency beta, Duplicate suppression, Hand-presence gate, Run face landmarks, Rotate offload beta, Parallel detectors beta, Pipeline profiling dev, Experimental core model v3 beta, and Extended vocabulary beta. Remaining visible rows are account type, voice output, accessibility, privacy, and about.
- The Profile `EDIT PROFILE` visual opens the current Settings/Preferences fragment through AppHear3 navigation instead of AppHear2 auth/profile editing.
- AppHear3 recognition, model, MediaPipe, temporal, and confirmation files were not changed.

Verification:

- Initial `assembleDebug` failed because PowerShell wrote layout XML with a BOM/invalid leading byte; fixed by rewriting edited layout XML as UTF-8 without BOM.
- `assembleDebug --console=plain --no-daemon --max-workers=2`: PASS.
- A parallel `testDebugUnitTest` run collided with Gradle resource-output cleanup while `assembleDebug` was running; rerunning sequentially passed.
- `testDebugUnitTest --console=plain --no-daemon --max-workers=2`: PASS.
- Protected AppHear3 model/config/MediaPipe asset hashes match rollback backup.

Known remaining gaps:

- Manual visual QA is still required because automated screenshot viewing is unavailable in this Windows sandbox.
- Splash and loading screenshots remain pending.
- Imported asset/font provenance and APK-size impact remain release gates.
## 2026-07-22 Settings/Profile AppHear2-only row removal

Purpose: remove misleading AppHear2-only settings from Profile and Settings after user review.

Changed files:

- `android/app/src/main/res/layout/fragment_profile.xml`
- `android/app/src/main/res/layout/fragment_settings.xml`

Removed from visible screens:

- Detection Preferences
- Smart detection (beta)
- Low-latency mode (beta)
- Duplicate suppression
- Hand-presence gate
- Run face landmarks
- Rotate offload (beta)
- Parallel detectors (beta)
- Pipeline profiling (dev)
- Experimental core model (v3, beta)
- Extended vocabulary (beta)

Decision: these rows came from AppHear2/UI reference material and either imply obsolete runtime controls, unsafe face-landmark behavior, dev-only profiling, or model/vocabulary switches that AppHear3 does not expose as user settings. The row resource files remain unused for now; visible screens only include safe passive app/profile rows.

Verification:

- `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2`: PASS.

## 2026-07-22 Recognition page model-test architecture pass

Purpose: harden the redesigned `RecognitionActivity` for upcoming model testing while keeping AppHear3 recognition/runtime behavior as the only source of truth.

Changed files:

- `android/app/src/main/java/com/example/apphear/RecognitionActivity.kt`
- `android/app/src/main/java/com/example/apphear/ui/recognition/RecognitionUiSnapshot.kt`
- `android/app/src/test/java/com/example/apphear/RecognitionUiSnapshotTest.kt`
- `android/app/src/main/res/values/strings.xml`

Decisions:

- Added a pure UI snapshot adapter that maps AppHear3 `RecognitionState` to display fields. It does not infer, confirm, gate, buffer, or mutate recognition behavior.
- `RecognitionActivity` still owns CameraX startup and still delegates recognition to AppHear3 `RecognitionPipeline`, `FrameAnalyzer`, `LandmarkerBundle`, `RuntimeConfig`, and `RecognitionState`.
- AppHear2 detection/runtime classes remain excluded: no `SignDetectActivity`, no AppHear2 `LandmarkOverlayView`, no face-landmark toggle, no AppHear2 START/STOP detection lifecycle, no old model/classifier assets.
- Model-load failure is now persistent in the recognition UI instead of a short-lived toast only. This supports upcoming candidate-model tests because schema/shape/model failures remain visible while camera preview may still run.
- The AppHear2-style `SPEAK` visual is wired to a deferred-message toast only; no TTS/cloud speech behavior was added.

Validation:

- `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2`: PASS.
- Added unit coverage for idle/signing/committed UI snapshot rendering.
- ADB device check found no attached devices, so device launch/manual visual QA is pending.

Asset note:

- Current `model_manifest.json`, `recognition_config.json`, and `streaming.tflite` differ from the old 2026-07-21 UI-phase backup and were last written before this pass. They appear to be the 236-class candidate model/config state (`schema_version=3.0`, `time_window=96`, `feature_dim=258`, `num_classes=236`). They were not modified by this UI architecture pass. Do not revert or replace them without an explicit model-test decision.
## 2026-07-22 Splash/Loading UI correction

Purpose: complete the remaining AppHear2 screenshot-reference UI pages using native Kotlin/XML while keeping recognition/model startup separate from visual loading.

Changed files:

- `android/app/src/main/AndroidManifest.xml`
- `android/app/src/main/java/com/example/apphear/SplashActivity.kt`
- `android/app/src/main/java/com/example/apphear/LoadingActivity.kt`
- `android/app/src/main/res/layout/activity_splash.xml`
- `android/app/src/main/res/layout/activity_loading.xml`
- `android/app/src/main/res/values/strings.xml`
- selected AppHear2 visual assets under `android/app/src/main/res/drawable/`: `applogo.png`, `bg_loading.xml`, `bg_splash_screen.xml`, `splash.png`, `week.png`, `hand.png`, `talking.png`.

Decisions:

- `SplashActivity` is now the launcher. `MainActivity` remains the non-exported homepage/shell destination.
- `SplashActivity` uses AppHear2's first-run `apphear_onboarding/has_seen_splash` gate and opens `LoadingActivity`.
- `LoadingActivity` is a bounded visual brand transition into `MainActivity`; it does not preload recognition, alter model loading, or imply model readiness.
- AppHear2 Java code was adapted into Kotlin. No AppHear2 detection, backend, auth, model, MediaPipe, or recognition logic was copied.

Validation:

- `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2`: PASS.
- Android source/resource mojibake scan is clean.

Known remaining gaps:

- Manual launch visual QA on a device/emulator is pending.
- Imported splash/loading raster asset provenance and APK-size impact remain release gates.
## 2026-07-22 Shell/navigation cleanup

Purpose: stabilize the native AppHear3 app shell after the AppHear2 screenshot pages were corrected.

Changed files:

- `android/app/src/main/AndroidManifest.xml`
- `android/app/src/main/java/com/example/apphear/MainActivity.kt`

Decisions:

- `SplashActivity` remains the launcher, `LoadingActivity` remains a visual transition, `MainActivity` remains the homepage/shell, and `RecognitionActivity` remains the dedicated recognition runtime screen.
- Removed `AppShellActivity` from the main manifest but did not delete its Kotlin file yet because the workspace has no visible Git/source-control root. It remains a documented cleanup candidate.
- Shell tab navigation now uses single-top/pop-to-home behavior to avoid duplicate fragment back-stack entries.

Validation:

- `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2`: PASS.