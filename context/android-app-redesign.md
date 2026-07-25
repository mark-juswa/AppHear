# Android Application Redesign Context

Last updated: 2026-07-21  
Status: Initial architecture assessment complete; no application implementation started

## Purpose

Serve as the entry point for the AppHear3 native Android full-application redesign. This work is
independent of the React Native/iPhone experiment. It preserves the production recognition runtime
and selectively rebuilds AppHear2's fuller user experience around it.

## Scope and source-of-truth priority

1. Application logic, camera, recognition, model, performance, data structures, and runtime behavior:
   `F:/ASL DATASET/5. Apphear3/android/`
2. UI design, navigation intent, page organization, typography, colors, components, and visual assets:
   `D:/Programming/MOBILE APP/3.1 New Way/backup/AppHear2/`
3. When any context and implementation disagree, current AppHear3 runtime contracts win and the
   discrepancy is recorded before changes.

Related documents:

- [Project comparison and risks](android-project-inventory.md)
- [Complete screen/feature mapping](android-screen-mapping.md)
- [Target UI/navigation architecture](android-ui-architecture.md)
- [Design system and resource map](android-design-system.md)
- [Phases, dependencies, tests, rollback, issues, decisions, changelog](android-migration-plan.md)
- [Recognition pipeline contract](architecture.md)
- [Physical-device runtime checklist](device-smoke.md)

## Initial assessment outputs

| Required output | Where documented |
|---|---|
| 1. AppHear3 architecture summary | `android-project-inventory.md` -> Verified AppHear3 facts |
| 2. AppHear2 architecture/design summary | `android-project-inventory.md` -> Verified AppHear2 facts |
| 3. Differences/compatibility | inventory -> Compatibility and safety findings |
| 4. Complete screen/feature inventory | `android-screen-mapping.md` |
| 5. Screen migration mapping | screen mapping tables |
| 6. Target architecture | `android-ui-architecture.md` |
| 7. Navigation plan | UI architecture -> Navigation plan |
| 8. Design-system plan | `android-design-system.md` |
| 9. Recognition protection | migration plan -> Recognition-pipeline protection |
| 10. Dependency risk | inventory dependency deltas + migration dependency gates |
| 11. Resource conflicts | design system -> Resource collision report |
| 12. Phased plan | `android-migration-plan.md` |
| 13. Testing strategy | migration plan -> Testing strategy |
| 14. Rollback strategy | migration plan -> Rollback strategy |
| 15. Context/document plan | this coherent five-document set and context wiring |
| 16. Exact first implementation files | migration plan -> Exact first implementation file surface |

## Verified facts

- AppHear3 is a one-module Kotlin/XML application (`com.example.apphear`) using AGP 8.11.2,
  Kotlin 2.0.21, Java 11, compile/target SDK 36, and min SDK 26.
- It currently has one launcher/activity/layout and no fragments/navigation graph.
- Its recognition path is CameraX -> MediaPipe hand+pose -> S4 schema-3.0 features -> S5 gating ->
  `[1,96,258]` TFLite -> S7 confirmation -> S8 sentence state.
- The target baseline passed `testDebugUnitTest` and `assembleDebug` on 2026-07-21.
- AppHear2 is a one-module Java/XML application using the same namespace/package and eight declared
  activities, explicit-Intent navigation, many UI assets, GLB avatar playback, TTS/speech input,
  local preferences, and custom Supabase REST auth/profile code.
- AppHear2's `ConversationActivity` is declared but no route to it was found.
- AppHear2's `BatchProcessActivity` is an exported ADB developer tool, not a normal user screen.
- AppHear2 and AppHear3 collide on `MainActivity`, `activity_main.xml`, values/theme files, and
  launcher resources.
- The reference's hand/pose task files match AppHear3 byte-for-byte, but AppHear3 copies/paths remain
  authoritative. Old classifiers/labels/face task are incompatible and excluded.
- The reference contains extensive hardcoded UI values and an existing debug APK of about 321.7 MB.

## Assumptions requiring confirmation

- The desired first-release page set includes onboarding, home, recognition, text-to-ASL, and
  profile/settings; combined conversation can be staged later.
- Inter fonts, mascots, launcher art, and GLB animations are licensed/approved for reuse.
- The reference loading screen is design inspiration, not a mandatory 3.15-second delay.
- Guest/offline use is acceptable while auth and cloud speech are rebuilt later.
- A Navigation Component app shell plus a dedicated recognition activity is an acceptable target.

## Missing or unresolved information

- Source-control root/branch location was not available from the workspace root.
- Supabase migrations, table grants, RLS policies, storage policies, and session requirements were
  not found locally.
- Product priority for auth, cloud TTS, history, and the unreachable conversation screen is not set.
- Asset provenance/license and an APK-size budget are not documented.
- The Text-to-ASL playback architecture is now documented in `text-to-asl-architecture-plan.md`; asset provenance/license, APK-size budget, and final offline `model-viewer` strategy remain open.
- The desired visible start/stop behavior for recognition needs a product decision.

## Recommended architecture

- A non-camera `AppShellActivity` owns Home, Text-to-ASL, Profile, and Settings through a navigation
  graph and one bottom navigation.
- A dedicated `RecognitionActivity` owns camera permission/lifecycle and delegates S0-S8 construction
  to a `RecognitionSessionController` adapter around the existing runtime.
- UI consumes immutable recognition snapshots and explicit actions; it never calls TFLite,
  landmarkers, S4, gating, or confirmation directly.
- Shared resources are tokenized before screens. Imported assets are renamed, provenance-checked,
  optimized, and logged.
- Guest/local state ships first. Backend/profile sync and cloud speech are independent, optional
  integrations with offline fallbacks.
- A future conversation screen composes recognition and avatar interfaces rather than copying either
  feature pipeline.

## Proposed implementation phases

1. Phase 0 baseline/backup: baseline build recorded; source-control/backup still to resolve.
2. Phase 1 discovery/docs: complete.
3. Phase 2 design-system tokens with recognition files untouched.
4. Phase 3 navigation shell and placeholder destinations while existing recognition stays reachable.
5. Phase 4 shared components.
6. Phase 5 non-camera screens one group at a time.
7. Phase 6 dedicated recognition screen migration plus full F22 device verification.
8. Phase 7 data/backend/cloud/conversation features only after contracts exist.
9. Phase 8 stabilization, accessibility, release, APK-size, security, and final report.

## Files safe to modify first

After a recoverable backup/source-control point is established, Phase 2 may safely modify:

- `android/app/src/main/res/values/colors.xml`
- `android/app/src/main/res/values/themes.xml`
- `android/app/src/main/res/values-night/themes.xml`
- `android/app/src/main/res/values/strings.xml` for shared copy only
- new `dimens.xml`, `typography.xml`, and `styles.xml`
- selected, licensed font resources
- these Android redesign context files and `progress-tracker.md`

The exact list and exit gate live in `android-migration-plan.md`.

## Files that must remain untouched initially

- `android/app/src/main/java/com/example/apphear/MainActivity.kt`
- `android/app/src/main/res/layout/activity_main.xml`
- `android/app/src/main/AndroidManifest.xml`
- `android/app/build.gradle.kts` and `android/gradle/libs.versions.toml`
- all `android/app/src/main/java/com/example/apphear/pipeline/**`
- all `android/app/src/main/assets/**`
- all S4 golden fixtures and runtime tests except later additive tests

No AppHear2 Java runtime/model/MediaPipe file or classifier asset is safe to copy.

## Troubleshooting routes

- UI/layout/theme problem -> screen layout/component + `android-design-system.md`
- Navigation/back-stack problem -> shell graph/routes + `android-ui-architecture.md`
- Camera/landmark problem -> `FrameAnalyzer.kt`, `LandmarkerBundle.kt`, `OverlayView.kt`, and
  `device-smoke.md`
- Recognition/commit/sentence problem -> `RecognitionPipeline.kt`, `SigningDetector.kt`,
  `Confirmation.kt`, `SentenceBuilder.kt`, and existing recognition context
- Model/schema problem -> `ModelContract.kt`, production assets, and `feature-schema.md`
- Dependency/resource conflict -> `android-project-inventory.md` and `android-design-system.md`
- Migration regression -> phase/changelog/rollback sections in `android-migration-plan.md`
- Repeated failure after one correction -> `/recover`

## Dependencies

Current target dependencies remain authoritative. Navigation/state/WebView/backend libraries are
added only in the phase that uses them and only after compatibility/current-doc checks. CameraX,
MediaPipe, and TFLite are not upgraded as part of UI work.

## Decisions

- Assessment and documentation precede implementation.
- AppHear3 runtime behavior remains protected; AppHear2 is not merged wholesale.
- The first code phase is design tokens only.
- The application remains buildable and recognition remains reachable throughout migration.

## Known risks

- Same-package class/resource collision.
- Camera/model lifecycle regressions during launcher/activity restructuring.
- Unverified backend security and asset licensing.
- APK/memory growth from GLB assets, fonts, and old GenAI dependencies.
- UI work masking or worsening the known low-FPS runtime limit.

## Current status

The initial assessment is complete. Do not begin full migration. The next allowed implementation is
the narrow Phase 2 token foundation after the backup/source-control and relevant asset-license gates
are resolved.
## 2026-07-22 Settings configuration status layer completed

- `android/app/build.gradle.kts` now maps Supabase Gradle properties/environment variables into generated `BuildConfig` fields.
- Settings shows real configuration status for Supabase account sync, ElevenLabs/Android TTS, Android speech input, protected on-device recognition privacy, and AppHear3 runtime ownership.
- Supabase Auth/profile writes remain blocked until table schema, Data API exposure, grants, RLS policies, and storage policies are verified.
- No recognition/camera/model/confirmation/temporal files were changed.
