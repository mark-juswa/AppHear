# Android Application Project Inventory

Last updated: 2026-07-21  
Status: Phase 1 discovery complete; no application source changed

## Purpose

Record the verified architecture, dependencies, source files, data dependencies, and compatibility
risks of the production AppHear3 Android project and the AppHear2 UI reference before migration.
Use this file when a build, dependency, manifest, or source-ownership question arises.

## Scope and sources of truth

- Runtime and application-logic source of truth: `F:/ASL DATASET/5. Apphear3/android/`
- UI, visual-language, and application-flow reference only:
  `D:/Programming/MOBILE APP/3.1 New Way/backup/AppHear2/`
- Recognition contracts: [`architecture.md`](architecture.md),
  [`feature-schema.md`](feature-schema.md), and
  [`recognition-accuracy.md`](recognition-accuracy.md)
- Screen decisions: [`android-screen-mapping.md`](android-screen-mapping.md)
- Target UI boundaries: [`android-ui-architecture.md`](android-ui-architecture.md)
- Implementation gates: [`android-migration-plan.md`](android-migration-plan.md)

The AppHear2 directory is read-only reference material. Its recognition, model, camera, and
settings logic is not eligible to become the AppHear3 runtime source of truth.

## Verified AppHear3 facts

### Project and build

| Item | Verified value | Source |
|---|---|---|
| Root project | `AppHear` | `android/settings.gradle.kts` |
| Modules | One application module, `:app` | `android/settings.gradle.kts` |
| Namespace/application ID | `com.example.apphear` | `android/app/build.gradle.kts` |
| Language | Kotlin; Java 11 bytecode target | `android/app/build.gradle.kts` |
| Android Gradle Plugin | 8.11.2 | `android/gradle/libs.versions.toml` |
| Kotlin plugin | 2.0.21 | `android/gradle/libs.versions.toml` |
| compile/target/min SDK | 36 / 36 / 26 | `android/app/build.gradle.kts` |
| UI toolkit | XML Views + View Binding; no Compose | `app/build.gradle.kts`, `activity_main.xml` |
| Navigation | One launcher `MainActivity`; no fragments or navigation graph | manifest/source inventory |
| Baseline command | `.\gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` | run 2026-07-21 |
| Baseline result | PASS, exit code 0 | run 2026-07-21 |

### Dependencies

| Dependency | Version | Runtime ownership |
|---|---:|---|
| AndroidX AppCompat | 1.7.1 | base activity |
| Material Components | 1.14.0 | theme/widgets |
| ConstraintLayout | 2.2.1 | XML layout |
| CameraX core/camera2/lifecycle/view | 1.3.4 | S0 capture |
| MediaPipe Tasks Vision | 0.10.14 | S1/S2 hand + pose |
| Kotlin coroutines Android | 1.9.0 | async landmark/model work |
| Lifecycle runtime KTX | 2.8.7 | lifecycle coroutine scope |
| TensorFlow Lite | 2.16.1 | S6 recognizer |
| Gson | 2.11.0, test only | golden-vector tests |

Do not change these versions merely to match AppHear2. Any future addition must be justified and
checked against the target versions above.

### Manifest, activities, and screens

- `android/app/src/main/AndroidManifest.xml` declares camera permission, required camera hardware,
  and one exported launcher: `com.example.apphear.MainActivity`.
- The only current screen is `android/app/src/main/res/layout/activity_main.xml`.
- `MainActivity.kt` owns camera permission, async runtime loading, CameraX binding, camera selection,
  handedness persistence, sentence clearing, and rendering of recognition state.
- Current UI-only capabilities that must survive the redesign: camera preview, landmark overlay,
  processed-FPS/quality HUD, low-FPS banner, front/back camera toggle, dominant-hand toggle, live
  top-three candidates, committed gloss, sentence accumulation, and clear action.

### Recognition entry points and state flow

```text
MainActivity.start()
  -> RuntimeConfig.load()
  -> LandmarkerBundle.create() on Dispatchers.IO
  -> RecognitionPipeline.load() on Dispatchers.IO
  -> MainActivity.rebindCamera()
  -> CameraX ImageAnalysis / FrameAnalyzer.analyze()
  -> LandmarkerBundle.detectHands() + detectPose()
  -> RecognitionPipeline.processFrame()
  -> RecognitionState
  -> MainActivity.onFrame()
```

Exact source files:

- S0/S1/S2 orchestration: `pipeline/FrameAnalyzer.kt`, `LandmarkerBundle.kt`,
  `LandmarkerConfig.kt`, `AdaptiveController.kt`, `FpsTracker.kt`
- Profiling/degraded behavior: `RuntimeProfiler.kt`, `RuntimeLog.kt`, `LowFpsMonitor.kt`,
  `ProfilingMode.kt`
- S4 parity: `pipeline/features/S4Features.kt`, `S4Causal.kt`, `Topology.kt`
- S4-S8 orchestration: `pipeline/recognition/RecognitionPipeline.kt`
- Model loading/contract/inference: `ModelContract.kt`, `Recognizer.kt`, `Vocab.kt`
- Temporal and commit behavior: `SigningDetector.kt`, `SessionNormalizer.kt`, `Confirmation.kt`
- Sentence state: `SentenceBuilder.kt`
- UI overlay: `ui/OverlayView.kt`

`RecognitionPipeline` owns the live sign window and sentence builder. Its public UI-facing state is
the sealed `RecognitionState` (`Idle`, `Signing`, `Committed`) plus `sentenceText`. There is no
ViewModel, repository abstraction, or observable state stream yet.

### Persistence and assets

- `SharedPreferences("apphear")` stores only the selected `Handedness` in current source.
- Sentence and recognition-session state are memory-only and reset when the activity/runtime dies.
- No account, history database, cloud backend, Room database, or DataStore exists in AppHear3.
- Production model assets: `streaming.tflite`, `model_manifest.json`, `recognition_config.json`,
  `vocab.json`.
- MediaPipe assets: `mediapipe/hand_landmarker.task` and
  `mediapipe/pose_landmarker_lite.task`.
- `_backup_250fps/` and `_backup_conversational_tcn/` are rollback assets, not UI resources.

## Verified AppHear2 facts

### Project and build

| Item | Verified value | Source |
|---|---|---|
| Root/modules | `AppHear`, one `:app` module | settings file |
| Namespace/application ID | `com.example.apphear` | app Gradle file |
| Language | Java; Java 11 target | source/build file |
| AGP | 8.11.2 | version catalog |
| compile/target/min SDK | 36 / 36 / 24 | app Gradle file |
| UI toolkit | XML Views; no Compose; no fragments | source/resource inventory |
| Navigation | Explicit `Intent` calls among activities | activity source |
| Existing APK | `app/build/outputs/apk/debug/app-debug.apk`, 321,690,599 bytes | disk inspection |

The reference APK was not rebuilt during this assessment. Its Gradle file reads local secret values,
and rebuilding the external read-only project is not required to plan the UI migration.

### Declared activities and reachability

| Activity | Layout | Reachability | Verified purpose |
|---|---|---|---|
| `SplashActivity` | `activity_splash.xml` | Launcher, first run only | Get Started/brand entry |
| `LoadingActivity` | `activity_loading.xml` | From splash or returning launch | Timed brand animation, then home |
| `MainActivity` | `activity_main.xml` | From loading | Home/dashboard and feature cards |
| `SignDetectActivity` | `activity_sign_detect.xml` | Home/nav/text-to-ASL | Old camera recognition UI |
| `TextToAslActivity` | `activity_text_to_asl.xml` | Home/nav/detection | Text/speech to local GLB avatar |
| `ProfileActivity` | `activity_profile.xml` | Home/nav | Guest/auth profile and settings |
| `ConversationActivity` | `activity_conversation.xml` | Declared but no source `Intent` found | Combined signing/responding screen |
| `BatchProcessActivity` | `activity_batch_process.xml` | ADB only; exported | Developer dataset-regeneration tool |

There are no fragments and no navigation resource graph. The bottom navigation is an included XML
layout (`nav_bottom.xml`) with repeated activity-specific click handling, so it can create duplicate
activity instances and inconsistent selected state.

### User-facing feature inventory

- One-time splash/get-started screen and timed loading animation.
- Home greeting, connection badge, recent-word chips, and a two-card feature pager.
- Sign detection with start/stop, old candidate/confidence UI, camera flip, sentence, TTS, and a
  link to text-to-ASL.
- Text/speech input to locally bundled GLB avatar animations in a WebView, with replay and TTS.
- Profile/login/register/edit/avatar UI backed by a custom Supabase REST manager.
- Preference switches stored in `SharedPreferences`.
- A combined two-way conversation layout/activity.
- Developer-only video/landmark batch processing.

### Data and external dependencies

- `RecentSignsStore`: `SharedPreferences` JSON list of up to six words. Despite its name, entries
  come from the first word submitted to text-to-ASL, not from confirmed camera recognition.
- `AppSettings`: `SharedPreferences` flags for the old pipeline and experiments.
- `PhraseRepository`: ten in-memory default phrases; no durable history database.
- `SupabaseAuthManager`: direct `HttpURLConnection` calls to Auth, REST `users`, and Storage
  `profile-images`; URL and anon key are injected from `local.properties` into `BuildConfig`.
- `ElevenLabsSpeechPlayer`: optional remote speech using build-time key/voice/model configuration,
  with Android TTS fallback.
- `AvatarPlaybackController`: WebView local origin plus bundled GLB assets and `model_viewer.html`.
- Android speech recognition intent for voice input.
- No Room dependency is active, despite a stale Room3 compiler catalog entry.

### Reference dependency deltas

| Area | AppHear2 reference | Decision for AppHear3 |
|---|---|---|
| CameraX | 1.6.0 | Keep AppHear3 1.3.4 until separately justified/tested |
| MediaPipe Vision | 0.10.33 | Never copy; keep AppHear3 parity-pinned 0.10.14 |
| TFLite | 2.17.0 + support 0.5.0 | Keep AppHear3 2.16.1 and current model contract |
| Tasks GenAI | 0.10.33 | Exclude initially; not required for UI migration |
| CardView | 1.0.0 | Add only if retained XML cannot use MaterialCardView |
| ViewPager2 | 1.0.0 | Optional for exact home carousel; justify in Phase 4/5 |
| WebKit | 1.11.0 | Required only if text-to-ASL avatar is approved |
| Supabase | Custom REST, no SDK | Rebuild/defer after backend and security contract verification |

## Compatibility and safety findings

### Critical conflicts

1. Both projects use `com.example.apphear`; `MainActivity` has the same fully qualified name but
   completely different ownership. Copying AppHear2 source would overwrite the production launcher.
2. Both have `layout/activity_main.xml`, `colors.xml`, `strings.xml`, and theme/launcher resources
   with different content. They must be merged or renamed, never overwritten.
3. AppHear2 contains old `sign_classifier*.tflite`, label JSON files, `DetectionPipelineController`,
   temporal buffers, keypoint extraction, MediaPipe helpers, and optional face model. All are excluded
   from the runtime migration.
4. AppHear2 settings expose behaviors forbidden or obsolete in AppHear3: face landmarks, old core/
   extended models, sliding/temporal normalization experiments, and old detection gates.

### Resource facts

- Same-path files with different contents: `activity_main.xml`, `colors.xml`, `strings.xml`, both
  theme files, launcher background, and all launcher bitmap densities.
- `ic_launcher_foreground.xml`, backup rules, and extraction rules are byte-identical.
- The two MediaPipe `.task` assets are byte-identical between projects, but the AppHear3 paths and
  parity ownership remain canonical.
- AppHear2 layouts contain 115 hardcoded text attributes, 129 literal color occurrences, and 507
  `dp` literals. Visual reuse therefore requires tokenization, not raw layout copying.
- AppHear2 bundles Inter fonts plus many raster/vector assets and GLB animations. Asset licensing,
  provenance, accessibility descriptions, size, and actual runtime reachability require verification.

### Backend/security findings

The following are verified source characteristics, not claims about the unseen Supabase project:

- The access token is stored unencrypted in `SharedPreferences`.
- No refresh-token persistence or token-refresh flow exists.
- `logout()` clears local preferences only; it does not call the Auth logout endpoint or revoke the
  server session.
- The code assumes a public `users` table and a public `profile-images` bucket. RLS policies, table
  grants, storage policies, and ownership checks were not found locally and remain unverified.
- The app manually implements Auth/REST/Storage protocols instead of a pinned client library.

Do not migrate this auth implementation unchanged. Guest mode can ship independently; account
support needs a separately approved backend contract and security review.

## Assumptions requiring confirmation

- The visual style, home, detection, text-to-ASL, and profile/settings are intended product areas;
  the unreachable `ConversationActivity` may be a prototype rather than a required launch feature.
- The bundled GLB animations and mascot/icon art are owned/licensed for reuse in AppHear3.
- A forced 3.15-second loading screen is a visual reference, not a hard UX requirement.
- Account sync and ElevenLabs cloud speech are optional, not blockers for an offline-first release.

## Missing or unresolved information

- No Supabase migrations, RLS policies, bucket policies, project reference, or backend schema are in
  either inspected Android source tree.
- No source-level route to `ConversationActivity` was found.
- No evidence shows the AppHear2 settings rows for voice, detection, privacy, accessibility, or about
  open detail pages; the layouts are static rows without IDs/listeners.
- No localization set exists beyond a minimal `strings.xml`; most reference copy is hardcoded.
- No automated navigation, screenshot, accessibility, or lifecycle tests exist in AppHear2.
- Asset licensing/provenance and production privacy copy were not found.
- Whether accounts, cloud TTS, and the text-to-ASL avatar are required for the first production
  release still needs product confirmation.

## Decisions

- Preserve AppHear3 Gradle/package/runtime assets as the baseline.
- Treat AppHear2 UI resources as references to audit, rename, tokenize, and selectively import.
- Do not copy any AppHear2 `ml/`, `mediapipe/`, classifier asset, model metadata, or runtime flag.
- Keep the camera/recognition screen isolated from the general app shell.
- Defer backend/auth and cloud speech until their contracts are verified separately.

## Known risks

- Package/resource collisions can compile while silently selecting the wrong class or asset.
- Moving camera ownership into a fragment can introduce lifecycle leaks and duplicate bindings.
- A large GLB/WebView payload can significantly increase APK size and memory use.
- Reusing old settings language can expose unsupported or unsafe controls to users.
- Manual explicit-Intent bottom navigation can accumulate duplicate activities.

## Current status

Discovery is complete and the AppHear3 baseline build is green. Implementation is not authorized by
this document. Start with the gates and file lists in
[`android-migration-plan.md`](android-migration-plan.md).
