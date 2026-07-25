# Android UI and Navigation Architecture

Last updated: 2026-07-21  
Status: MainActivity is homepage/shell; RecognitionActivity owns recognition runtime; temporary AppShellActivity cleanup pending

## Purpose

Define the safe target architecture for turning the single-screen production runtime into a full
application while keeping camera, feature construction, model inference, confirmation, and sentence
behavior insulated from UI migration.

## Scope and sources of truth

- Production source: `F:/ASL DATASET/5. Apphear3/android/`
- Reference UX: `D:/Programming/MOBILE APP/3.1 New Way/backup/AppHear2/`
- Runtime contract: [`architecture.md`](architecture.md),
  [`runtime-constraints.md`](runtime-constraints.md),
  [`feature-schema.md`](feature-schema.md)
- Verified inventory: [`android-project-inventory.md`](android-project-inventory.md)
- Screen decisions: [`android-screen-mapping.md`](android-screen-mapping.md)
- Phases/gates: [`android-migration-plan.md`](android-migration-plan.md)

This document does not authorize a feature-schema, model, camera, or recognition-policy change.

## Recommended architecture

Use a hybrid navigation structure:

- Final `MainActivity`: the app homepage/shell launcher hosting a Navigation Component `NavHostFragment` for Home, Text-to-ASL, Profile, Settings, and future non-camera screens. The existing `AppShellActivity` scaffold is temporary and should be folded into or replaced by `MainActivity` during the launcher/shell migration.
- `RecognitionActivity`: a dedicated activity for CameraX, MediaPipe, recognition-session state,
  and its full-screen overlay/control layout.
- A small launcher/startup route decides whether first-run onboarding is shown before the shell.
- Do not put CameraX/MediaPipe ownership in the shell or a long-lived application singleton.

This keeps the most lifecycle-sensitive screen independent while eliminating AppHear2's repeated
explicit-Intent bottom-navigation implementation for normal destinations.

```text
Launcher / first-run gate`r`n        |`r`n        v`r`nMainActivity + NavHostFragment
  |-- HomeFragment
  |-- TextToAslFragment
  |-- ProfileFragment
  `-- SettingsFragment
        |
        +-- explicit activity route --> RecognitionActivity
                                         |
                                         `-- RecognitionSessionController
                                             -> existing S0-S8 implementation
```



## MainActivity-as-homepage decision - 2026-07-21

The final native app must treat `MainActivity` as the homepage/shell entry point, matching the user's intended product structure. The current `MainActivity` still contains the protected AppHear3 recognition implementation only as a temporary baseline. Phase 6 must first create a dedicated `RecognitionActivity` by moving/adapting the current recognition behavior without changing camera, inference, temporal, confirmation, model, or sentence logic. Only after that route is verified should `MainActivity` become the homepage/shell and open `RecognitionActivity` for recognition, similar to AppHear2's separate sign-detection screen structure.
## Implementation checkpoint - 2026-07-21

Phase 3 added a non-exported `ui.shell.AppShellActivity` with a Navigation Component graph and placeholder Home, Text-to-ASL, Profile, and Settings destinations. Home can explicitly open the existing `MainActivity` recognition baseline. The launcher was not switched; CameraX, MediaPipe, S4-S8 recognition, model assets, and `activity_main.xml` were not changed.


## MainActivity shell conversion checkpoint - 2026-07-21

`MainActivity` now hosts the existing app shell layout through `ActivityAppShellBinding`; it no longer imports CameraX, MediaPipe, `FrameAnalyzer`, `RecognitionPipeline`, or recognition runtime classes. `RecognitionActivity` remains the dedicated recognition runtime screen and is opened from Home/Text-to-ASL routes. Device smoke after conversion showed launcher `MainActivity` resumes as shell with no recognition startup logs, while direct debug launch of `RecognitionActivity` loads landmarkers, recognizer, CameraX preview, and `AppHearPerf` runtime logs. Manual signing/interaction smoke remains pending.
## RecognitionActivity parity checkpoint - 2026-07-21

A non-launcher `RecognitionActivity` now exists as a parity scaffold using the current AppHear3 recognition behavior and a separate `activity_recognition.xml` copied from the baseline recognition layout. Shell Home and Text-to-ASL recognition actions route to `RecognitionActivity`. The existing recognition-bearing `MainActivity` and `activity_main.xml` remain byte-identical to the rollback baseline and are still the launcher/fallback. This is build-green only; physical-device smoke is still required before converting `MainActivity` into the homepage/shell.
## What remains unchanged initially

The following files are protected during design-system, navigation-placeholder, and shared-component
phases:

- `pipeline/FrameAnalyzer.kt`
- `pipeline/LandmarkerBundle.kt`
- `pipeline/LandmarkerConfig.kt`
- `pipeline/AdaptiveController.kt`
- `pipeline/LowFpsMonitor.kt`
- all `pipeline/features/*.kt`
- all `pipeline/recognition/*.kt`
- production and backup files under `app/src/main/assets/`
- S4 golden fixtures and recognition unit tests

`ui/OverlayView.kt` may be restyled or wrapped only when the recognition screen phase begins; its
coordinate mapping and front-camera display mirroring remain unchanged.

## Planned refactoring surface

`MainActivity.kt` currently combines six responsibilities: permission, runtime construction,
CameraX binding, settings persistence, lifecycle cleanup, and view rendering. Refactor it only in
the recognition-integration phase into these roles:

| Role | Proposed class/package | Responsibility |
|---|---|---|
| Screen | `ui/recognition/RecognitionActivity.kt` | lifecycle, permission, route result, binds state/actions |
| Session owner | `ui/recognition/RecognitionSessionController.kt` | constructs/tears down landmarkers, analyzer, recognition pipeline, and camera use cases |
| UI state | `ui/recognition/RecognitionUiState.kt` | immutable warmup/ready/signing/committed/error/degraded state |
| UI actions | `ui/recognition/RecognitionActions.kt` or controller methods | camera/hand switch, clear, pause/resume, retry |
| Settings access | `data/settings/AppSettingsRepository.kt` | dominant hand, camera preference, user-level settings only |
| General shell | `MainActivity.kt` final / temporary `ui/shell/AppShellActivity.kt` scaffold | NavHost and bottom navigation only; no recognition runtime ownership |

The controller is an adapter around the existing runtime. It does not recreate feature math,
signing detection, confirmation, or sentence logic.

## Recognition state interface

UI code may consume a single immutable snapshot/stream shaped like this conceptually:

```kotlin
data class RecognitionUiState(
    val phase: RecognitionPhase,
    val candidates: List<String>,
    val committedGloss: String?,
    val sentence: String,
    val processedFps: Double?,
    val qualityLabel: String?,
    val lowFps: Boolean,
    val handedness: Handedness,
    val camera: CameraFacing,
    val error: UserFacingError?,
)
```

Implementation may use `StateFlow` once the required lifecycle/ViewModel dependencies are approved.
The hard boundary is more important than the mechanism:

- `FrameAnalyzer` and `RecognitionPipeline` produce runtime results.
- The controller converts them to a UI snapshot.
- Views render the snapshot and send explicit actions back.
- No fragment/layout calls `Recognizer`, `SigningDetector`, `Confirmation`, `SessionNormalizer`,
  `LandmarkAdapter`, or TFLite directly.
- UI update frequency is throttled when necessary; camera-frame rate must not drive expensive view
  recreation.

## Recognition lifecycle contract

1. Inflate and render a non-blocking warm-up state.
2. Request camera permission through Activity Result API.
3. Load runtime config, MediaPipe tasks, and TFLite off the main thread.
4. Bind CameraX only after lifecycle and models are ready.
5. Use `STRATEGY_KEEP_ONLY_LATEST` and the existing analyzer busy guard.
6. On camera or handedness change, reset the recognition session using the existing contract.
7. On `onStop`, stop accepting UI work; decide whether camera stays bound only from measured UX and
   lifecycle tests. Default safe behavior is unbind/release when the recognition activity is not
   visible.
8. On destruction, close analyzer, executor, landmarkers, and recognizer exactly once.
9. A schema/model load failure renders an error and retains the camera-only fallback where current
   behavior permits it.

Do not preserve recognition state across process death. Sentence/history persistence, if desired,
uses a documented repository; low-level model/camera objects are never serialized or retained by a
general ViewModel.

## Navigation plan

### Destinations

| Route | Owner | Back behavior |
|---|---|---|
| `onboarding` | startup graph | completes into Home; not on returning-user back stack |
| `home` | app shell | root |
| `text_to_asl` | app shell | bottom-nav root |
| `profile` | app shell | bottom-nav root |
| `settings` | app shell | child of profile; back to profile |
| `recognition` | dedicated activity | finish to the originating shell destination |
| `conversation` | deferred | child/full-screen flow after prerequisite features |

Bottom navigation must use one graph/back stack policy and maintain selected state. Do not recreate
AppHear2's pattern of every screen launching another copy of an activity.

### Startup

- A first-run flag controls the onboarding destination.
- The branded loading animation may be incorporated as a short transition but must not impose an
  arbitrary delay on every launch.
- Recognition models remain lazily loaded when recognition is opened unless measured startup work
  later justifies prewarming. Any prewarming still runs off-main-thread and must not bind a camera.

## Application state and persistence

Separate state by lifetime:

| State | Lifetime/owner | Initial storage |
|---|---|---|
| Current candidates/FPS/warmup | recognition session | memory only |
| Current sentence | `RecognitionPipeline` during session | memory; optional explicit save later |
| Dominant hand/camera preference | application setting | repository over `SharedPreferences` initially |
| First-run completed | application setting | repository over `SharedPreferences` |
| Recent activity/history | feature data | not implemented until retention/data contract approved |
| Guest profile | UI default/local setting | local |
| Auth/session/profile sync | backend feature | deferred; never piggyback on runtime prefs |

Do not introduce Room or DataStore solely to imitate AppHear2. Add storage only when its data and
retention contract are explicit.

## Text-to-ASL boundary

If approved, organize the reference implementation behind interfaces:

- `AvatarAssetRegistry`: validates bundled manifest and maps aliases.
- `PhrasePlanner`: converts normalized input to a playback plan; reports unmapped tokens.
- `AvatarPlayer`: owns WebView and playback lifecycle.
- `SpeechInput`: wraps Android recognizer availability/result.
- `SpeechOutput`: Android TTS baseline; cloud provider is an optional implementation.

This feature does not import recognition pipeline classes. A future conversation screen composes
`RecognitionSession` output and `AvatarPlayer` input instead of duplicating either implementation.

## Profile/settings boundary

- Ship a functional guest profile and supported settings independently of cloud auth.
- Only expose settings with a real AppHear3 contract: dominant hand, camera preference (if desired),
  accessibility, privacy/about, and user-facing speech options that are actually implemented.
- Feature flags, profiler modes, face model, old vocabulary/model switches, and experimental timing
  controls are not production settings.
- Developer diagnostics may live in a debug-only destination guarded by build type.
- Auth is a separate repository/service with secure token storage, refresh, logout/revocation, error
  mapping, and a verified Supabase schema/RLS/storage contract before rollout.

## Error handling

| Failure | User behavior | Developer source |
|---|---|---|
| Camera permission denied | Explain why + retry/open-settings action; non-camera app remains usable | RecognitionActivity/controller |
| No requested camera | Human-readable unavailable state; do not crash/rebind loop | camera controller |
| MediaPipe/model warmup | Persistent loading state, no blocked main thread | controller |
| Model/schema mismatch | Refuse recognition; camera-only fallback/error action | `ModelContract`, controller |
| Low FPS | Existing reliability warning; avoid hiding diagnostics | `LowFpsMonitor`, UI mapping |
| Text has no avatar asset | Show unmapped words and safe fallback; do not pretend translation succeeded | PhrasePlanner/UI |
| Speech recognizer absent | Text input remains available | SpeechInput/UI |
| Auth/backend unavailable | Guest mode remains usable; no loss of local settings | auth repository/UI |
| WebView/GLB load failure | Error/fallback illustration; release WebView | AvatarPlayer |

Raw exceptions, endpoint responses, and secret-looking values never surface in production UI.

## Package and resource organization

```text
com.example.apphear/
  pipeline/                    # existing protected S0-S8 runtime
  ui/
    shell/
    onboarding/
    home/
    recognition/
    texttoasl/
    profile/
    settings/
    components/
    theme/
  data/
    settings/
    history/                   # only after contract approval
    profile/                   # guest/local first; backend later
  domain/
    recognition/               # UI/domain snapshots only, no feature math
    texttoasl/
```

Resource naming uses a feature prefix (`home_*`, `recognition_*`, `profile_*`, `component_*`) and
semantic tokens (`color_surface_brand`, `space_16`), avoiding generic AppHear2 names such as
`bg_white_pill` when meaning differs.

## Buildability strategy

- Add one small, flaggable phase at a time.
- Keep the existing recognition behavior reachable until a dedicated `RecognitionActivity` route from the `MainActivity` homepage/shell builds and passes tests.
- Placeholder shell destinations contain no camera/model code.
- The launcher manifest should ultimately point to `MainActivity` as the homepage/shell. This switch happens only after a build and navigation/device test prove `MainActivity -> RecognitionActivity` always reaches recognition.
- Do not overwrite the current recognition-bearing `MainActivity` in-place. First create `RecognitionActivity` from the current AppHear3 recognition behavior, verify parity, then convert `MainActivity` into the homepage/shell in a dedicated reversible step.
- Every phase ends with unit tests + debug assemble; runtime phases also require F22 device smoke.

## Assumptions requiring confirmation

- A Navigation Component dependency is acceptable for the non-camera shell.
- The dedicated recognition activity is preferred over embedding camera in a fragment.
- Text-to-ASL and account features can be staged independently.

## Decisions

- General navigation is hosted by final `MainActivity`; recognition is a dedicated `RecognitionActivity`.
- UI consumes an adapter-owned recognition snapshot and cannot call low-level runtime classes.
- No model preloading is placed on the launcher critical path by default.
- Guest/offline behavior is the baseline; backend features are additive.

## Known risks

- Renaming the current launcher can break manifest, view binding, tests, or deep links if combined
  with unrelated changes.
- `StateFlow`/ViewModel dependencies must be version-checked before addition.
- A WebView inside the shell needs explicit pause/resume/destroy handling.
- Keeping camera bound behind another screen can waste power or conflict with later camera access.

## Current status

Architecture is recommended but unimplemented. The first implementation files and gates are listed
in [`android-migration-plan.md`](android-migration-plan.md).
