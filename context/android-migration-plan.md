# Android Full-Application Migration Plan

Last updated: 2026-07-21  
Status: MainActivity homepage/shell conversion build-green; RecognitionActivity remains runtime destination; manual signing smoke pending

## Purpose

Provide the reversible implementation order, dependency/resource gates, test strategy, rollback
procedure, issue log, decision log, and exact initial file surface for migrating AppHear2's complete
experience into the production AppHear3 Android application.

## Scope and sources of truth

- Runtime source of truth: `F:/ASL DATASET/5. Apphear3/android/`
- UI reference: `D:/Programming/MOBILE APP/3.1 New Way/backup/AppHear2/`
- Verified inventory/risks: [`android-project-inventory.md`](android-project-inventory.md)
- Screen decisions/status: [`android-screen-mapping.md`](android-screen-mapping.md)
- Target boundaries/navigation: [`android-ui-architecture.md`](android-ui-architecture.md)
- Tokens/assets: [`android-design-system.md`](android-design-system.md)
- Runtime smoke/rollback: [`device-smoke.md`](device-smoke.md)

No phase may override [`feature-schema.md`](feature-schema.md),
[`runtime-constraints.md`](runtime-constraints.md), or
[`eval-protocol.md`](eval-protocol.md).

## Baseline record (Phase 0)

| Check | Result |
|---|---|
| Target root | `F:/ASL DATASET/5. Apphear3/android/` |
| Command | `.\gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` |
| Date | 2026-07-21 |
| Result | PASS, exit code 0 |
| Source tree state | No pre-existing source changes detected by the assessment; workspace root is not a Git worktree in this shell |
| Runtime baseline | Current S0-S8 production implementation and F22 expectations in existing context files |

Because no usable Git repository was detected from the project root, a feature branch was not
created. Before implementation, verify whether source control lives elsewhere; if not, create a
recoverable archive/copy of `android/` outside the working tree without replacing the target.

## Non-negotiable migration rules

1. AppHear3 recognition/camera/model code wins every conflict.
2. AppHear2 contributes design intent, assets, layouts, and feature requirementsâ€”not runtime code.
3. One screen or tightly related component group per change.
4. Every meaningful change ends with unit tests and `assembleDebug`.
5. Recognition-runtime changes additionally require the F22 device smoke.
6. New behavior is feature-flagged or introduced as an unreachable placeholder until verified.
7. No broad dependency upgrade accompanies the UI migration.
8. No old model, labels, face landmarker, `ml/`, or `mediapipe/` source enters AppHear3.
9. No backend behavior is invented. Guest/local states remain honest when backend contracts are
   missing.
10. Update this file, screen status, and the migration changelog after each completed phase/screen.

## Phased implementation

### Phase 0 - Backup and baseline - COMPLETE for assessment

- Record target versions, build command, manifest, activity, runtime entry points, and assets.
- Run target unit tests and debug assemble.
- Record existing device expectations from context.
- Before code work, establish a branch or recoverable backup when source-control location is known.

Exit gate: green build recorded and exact rollback source identified.

### Phase 1 - Discovery and architecture - COMPLETE

- Inventory both projects, activity reachability, layouts, dependencies, data, assets, and conflicts.
- Map every screen/feature.
- Define target shell/recognition boundary, design tokens, migration phases, tests, and rollback.
- Wire these documents into the existing context system.

Exit gate: the five Android redesign documents are internally linked and no app source changed.

### Phase 2 - Design-system foundation

- Add semantic colors, dimensions, text appearances, component styles, and deliberate theme/system
  bar behavior.
- Import only approved Inter weights and a very small approved asset slice.
- Add an old-to-new resource ledger to this document or a dedicated generated table if it grows.
- Do not change `activity_main.xml` or recognition rendering in this phase.

Exit gate: unit tests + assemble pass; no resource collision; token sample renders in a non-runtime
preview/test layout or later placeholder.

### Phase 3 - Navigation shell with placeholders

- Add Navigation Component versions compatible with the existing AGP/Kotlin/AndroidX set after
  checking current official release metadata at implementation time.
- Create `AppShellActivity`, navigation graph, Home/Text-to-ASL/Profile placeholders, and one shared
  bottom navigation.
- Keep existing `MainActivity` as the launcher/recognition baseline initially, or make the new shell
  reachable only through an explicit temporary route/debug flag.
- Do not move CameraX or recognition code yet.

Exit gate: graph navigation/back behavior tests pass, repeated tab selection does not duplicate
destinations, and existing recognition remains directly reachable.

### Phase 4 - Shared components

- Build status chips, feature cards, icon actions, buttons, settings rows, and common loading/error/
  empty states from tokens.
- Move all component text/descriptions to resources.
- Add accessibility checks and screenshot/manual visual baselines.

Exit gate: component tests/build pass and no screen-specific runtime logic is embedded.

### Phase 5 - Non-camera screens, one group at a time

Recommended order:

1. Onboarding/startup transition.
2. Home/dashboard with truthful placeholder/recent-activity semantics.
3. Guest profile and supported settings.
4. Text-to-ASL shell; then avatar playback only after GLB/WebView gate.
5. Auth/cloud speech only as separately approved backend/provider features.

For every screen: inspect reference -> document data contract -> implement UI -> connect route ->
test -> build -> update mapping/changelog.

Exit gate per screen: build green, navigation verified, state/error/empty/accessibility cases tested.

### Phase 6 - Recognition screen integration

- Create the dedicated `RecognitionActivity` and controller adapter.
- Move/adapt the current recognition behavior out of the temporary recognition-bearing `MainActivity` without changing algorithms, camera behavior, temporal logic, confirmation, model config, or assets.
- After `RecognitionActivity` is verified, convert final `MainActivity` into the homepage/shell entry point that hosts Home/Text-to-ASL/Profile/Settings and opens `RecognitionActivity` for recognition.
- Apply the AppHear2-inspired full-screen camera, gradient, status, and bottom-controls design.
- Preserve current top-three candidates, dominant-hand control, camera toggle, sentence/clear, FPS/
  quality, degraded warning, schema refusal, kill-switch, and load-failure fallback.
- Add optional Android TTS only as a UI/domain consumer of committed sentence text.
- Keep launcher switching separate and reversible: final launcher is `MainActivity` as homepage/shell, and it switches only after `MainActivity -> RecognitionActivity` is verified.

Exit gate: JVM tests, assemble, navigation/lifecycle tests, and complete F22 device smoke including
camera switch/rotation/mirroring/resource release. Any recognition metric or behavior change is a
separate proposal and offline eval gate.

### Phase 7 - Data and extended features

- Introduce a documented local history contract if approved; do not rename text-input history as
  detected-sign history.
- Finish text-to-ASL asset coverage and unmapped-token behavior.
- Implement auth/profile sync only after Supabase schema, grants, RLS, storage policies, secure
  session storage/refresh/logout, and privacy behavior are documented and tested.
- Implement cloud speech only with secret handling, privacy, failure, and TTS fallback contracts.
- Rebuild combined conversation from recognition and avatar interfaces; never copy the 782-line
  activity or duplicate pipelines.

Exit gate: each feature has tests, offline fallback, documented retention/privacy, and build/device
verification proportional to risk.

### Phase 8 - Stabilization and release readiness

- Run unit, instrumentation, navigation, lifecycle, rotation, process-death, accessibility, UI,
  and F22 device tests.
- Inspect APK size, R8/release build, permissions, backup behavior, secrets, WebView security, and
  asset provenance.
- Remove dead code/resources only after `rg`/IDE reference checks and a green build.
- Produce final screen-status table and migration report.

Exit gate: all required screens `DONE`, unresolved items explicitly deferred, rollback verified,
and no runtime/eval contract regression.

## Exact first implementation file surface

The first implementation phase is Phase 2 (design-system foundation). Expected existing files to
modify:

- `android/app/src/main/res/values/colors.xml`
- `android/app/src/main/res/values/themes.xml`
- `android/app/src/main/res/values-night/themes.xml`
- `android/app/src/main/res/values/strings.xml` only for shared design/accessibility copy introduced
  in the phase
- `context/android-design-system.md` to record the final token/resource mapping
- `context/android-migration-plan.md` changelog/status
- `context/progress-tracker.md` after the phase is complete

Expected new files:

- `android/app/src/main/res/values/dimens.xml`
- `android/app/src/main/res/values/typography.xml`
- `android/app/src/main/res/values/styles.xml`
- selected, renamed font files under `android/app/src/main/res/font/` only after license approval

Files explicitly not changed in Phase 2:

- `android/app/src/main/java/com/example/apphear/MainActivity.kt`
- `android/app/src/main/res/layout/activity_main.xml`
- `android/app/src/main/AndroidManifest.xml`
- `android/app/build.gradle.kts`
- `android/gradle/libs.versions.toml`
- every `pipeline/**` file
- every `app/src/main/assets/**` file

If a design token phase needs to touch any protected file, stop and re-scope rather than expanding
the change silently.

## Dependency map and gates

| Candidate | Needed for | Existing equivalent | Gate/decision |
|---|---|---|---|
| Navigation Fragment/UI KTX | app shell graph | none | add in Phase 3 only; pin compatible versions |
| Lifecycle ViewModel/StateFlow integration | shell/view state | runtime KTX + coroutines partly available | add only when state holder is implemented |
| ViewPager2 | exact two-card home carousel | simple RecyclerView/horizontal cards possible | optional; choose simplest faithful UI |
| CardView | old XML cards | Material library already present | prefer `MaterialCardView`; likely no new dep |
| WebKit | text-to-ASL local WebView | platform WebView exists | add AndroidX WebKit only if required API/security features are used |
| Supabase client | future auth/profile | custom old REST is unsafe to copy | separate approved backend phase; pin library/lock contract |
| ElevenLabs/network client | cloud TTS | Android `HttpURLConnection`/TTS fallback | defer; no secret in source/APK beyond publishable client contract |
| Room/DataStore | history/settings | SharedPreferences exists | do not add until a real data contract requires it |
| Tasks GenAI | old gloss translator | S8 LM assist deferred | exclude |

Before any dependency change:

1. Check whether current Android/Material/Java/Kotlin APIs already solve it.
2. Verify compatibility with AGP 8.11.2, Kotlin 2.0.21, compile/target 36, and min 26.
3. Read current official library documentation and changelog.
4. Add one dependency group only, sync/build, and record why it exists.
5. Never align CameraX/MediaPipe/TFLite to AppHear2 as collateral work.

## Recognition-pipeline protection plan

### Protected behavior

- Image acquisition, `KEEP_ONLY_LATEST`, accepted-frame busy guard.
- Explicit rotation and front/back analysis/preview mirroring rules.
- IMAGE-mode hand and pose landmarker configuration and parallel/cadence behavior.
- S4 258-feature math and schema 3.0 checks.
- pre-onset context, S5 onset/release/hand gates, low-FPS tuning.
- `[1,96,258]` model input and TFLite inference.
- evidence accumulation/top-three/confirmation/one-commit-per-bout.
- S8 dedup/cap/clear behavior and runtime profiling.

### Required adapter tests

- Given each `RecognitionState`, the UI snapshot renders candidates/gloss/sentence correctly.
- Idle/release clears live gloss without erasing the sentence.
- Camera/hand change calls the same session reset behavior.
- Closing/leaving recognition releases camera, executor, landmarkers, and recognizer once.
- Schema/load failure never starts inference and retains the documented fallback.
- UI recreation does not create two analyzers or model bundles.

## Testing strategy

### Every meaningful change

- `.\gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2`
- inspect first relevant compiler/resource/manifest error only; stop adding features until resolved
- `rg` for duplicate resource/class/navigation names
- inspect manifest merge when permissions/activities/providers change

### Navigation/UI

- Activity/fragment launch tests for every route.
- Bottom-nav selected state, repeat selection, back/up, deep return from recognition.
- Rotation/configuration change and process recreation for non-camera screens.
- Permission denied/denied permanently/granted paths.
- Small screen, large font, landscape policy, keyboard/IME, TalkBack order/content descriptions.
- Light/night/system-bar/edge-to-edge visual checks.

### Recognition integration

- Existing `S4SkewTest`, `SigningHandGateTest`, `ConfirmationTopKTest`, and
  `SentenceBuilderTest` remain green.
- Controller lifecycle tests with fakes where possible.
- Physical-device F22 checklist on every runtime-affecting build.
- Explicit front/back camera, rotation, preview overlay alignment, handedness reset, navigation away/
  back, screen-off/on, and repeated open/close cycles.
- Record p50/p95 and processed FPS when UI changes could affect hot-path load.

### Backend/data features

- Guest/offline path works with no network/configuration.
- Supabase auth/session refresh/logout and ownership/RLS/storage tests before rollout.
- No secret/service-role value in source, resources, logs, or APK inspection.
- History retention/delete/export semantics tested if history is added.

## Rollback strategy

### Per-phase rollback

- Each phase is a small commit/patch with the previous green APK/build output retained.
- New shell/screens stay unreachable or flag-gated until verified.
- Revert the phase's new routes/resources/dependencies as one unit; do not patch the recognition
  pipeline to make a failed UI phase compile.

### Recognition rollback

- Keep the pre-migration recognition activity/layout until the new dedicated activity passes F22.
- `FeatureFlags.RECOGNITION_ENABLED=false` remains the camera/overlay kill-switch.
- Load failure continues to degrade without crashing.
- Model asset rollback continues to use the existing backup directories and documented model
  procedure; UI migration must not alter those files.

### Failure procedure

1. Stop feature work.
2. Capture the first relevant error/failing test.
3. Identify the last phase/screen change touching that surface.
4. Fix or revert only that change.
5. Re-run tests/build.
6. Record cause/resolution below.
7. If one corrective attempt fails and the same issue persists, run `/recover` per `AGENTS.md`.

## Known issues and unresolved gates

| ID | Issue | Impact | Required resolution | Status |
|---|---|---|---|---|
| UI-01 | Source-control root/branch unavailable from current root | rollback discipline | locate repo or establish recoverable backup before code | PARTIAL: source control still unavailable; Phase 2 rollback copy created at `C:/tmp/apphear3-android-backup-20260721-uidesign-phase2/` |
| UI-02 | AppHear2 `ConversationActivity` has no route | uncertain product scope | product decision; rebuild only after prerequisites | OPEN/DEFERRED |
| UI-03 | Supabase schema/RLS/storage policies absent | auth security/functionality unknown | backend contract + security tests | BLOCKS AUTH |
| UI-04 | Auth tokens are plaintext/no refresh/revocation | unsafe session handling | replace implementation | BLOCKS AUTH |
| UI-05 | GLB/mascot/font provenance not documented | licensing/release risk | confirm ownership/license | OPEN |
| UI-06 | Reference APK is ~321.7 MB | install/download/memory risk | asset inventory, compression, coverage, size budget | OPEN |
| UI-07 | Reference copy/resources heavily hardcoded | localization/theme/accessibility | tokenize during migration | OPEN |
| UI-08 | Current recognition screen has no ViewModel/controller boundary | UI-runtime coupling | Phase 6 adapter refactor with parity/lifecycle tests | OPEN |
| UI-09 | Session/history persistence contract absent | feature semantics unclear | product/data-retention decision | OPEN |
| UI-10 | AppHear3 performance remains below 15 FPS on baseline device | reliability UX | retain degraded behavior; redesign cannot claim to fix FPS | KNOWN LIMIT |

## Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-07-21 | Keep AppHear3 as runtime/build dependency source of truth | current pipeline is validated and parity-protected |
| 2026-07-21 | Use AppHear2 only for visual/flow/feature intent | old pipeline conflicts with schema/runtime contracts |
| 2026-07-21 | Use app-shell Navigation plus a dedicated recognition activity | isolates CameraX/MediaPipe lifecycle from general navigation |
| 2026-07-21 | MainActivity becomes homepage/shell; RecognitionActivity owns recognition | Matches intended AppHear2-like structure while keeping AppHear3 runtime protected |
| 2026-07-21 | Tokenize/recreate resources before screen migration | reference has extensive literals and name collisions |
| 2026-07-21 | Guest/offline first; defer Supabase and cloud TTS | backend/security/provider contracts are missing |
| 2026-07-21 | Defer combined conversation | currently unreachable and duplicates both pipelines |
| 2026-07-21 | Exclude batch tool, face model, old classifiers, and old runtime settings | obsolete/unsafe/incompatible with AppHear3 |

## Migration changelog

| Date | Phase/change | Files | Verification | Result |
|---|---|---|---|---|
| 2026-07-21 | Phase 0/1 assessment and context architecture | five `context/android-*.md` files plus context wiring | target unit tests + debug assemble | PASS; no app source change |
| 2026-07-21 | Phase 2 design-system token foundation | `colors.xml`, new `dimens.xml`, new `typography.xml`, new `styles.xml`, light/night `themes.xml`; docs/progress updated | `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` | PASS; no runtime, layout, manifest, asset, font, or dependency changes |
| 2026-07-21 | Phase 3 navigation shell placeholders | Navigation 2.9.8 catalog/dependencies; `AppShellActivity`; Home/Text-to-ASL/Profile/Settings placeholder fragments/layouts; nav graph and bottom nav menu; manifest non-launcher activity | `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2`; protected recognition file hash check | PASS; existing recognition launcher/runtime unchanged; shell is non-exported and not primary launcher |
| 2026-07-21 | Phase 4 shared component resources | shared component layouts/drawables and component strings | `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2`; protected recognition hash check | PASS; passive UI resources only |
| 2026-07-21 | Phase 5 Home/dashboard screen | `fragment_home.xml`, `HomeFragment.kt`, Home drawables/strings | `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2`; protected recognition file/model/MediaPipe asset hash check | PASS; Recognition card opens existing protected `MainActivity` |
| 2026-07-21 | Phase 5 guest Profile/settings screen group | `fragment_profile.xml`, `fragment_settings.xml`, `ProfileFragment.kt`, profile/settings row layouts, profile/settings drawables, strings; docs/progress updated | `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2`; protected recognition file/model/MediaPipe asset hash check | PASS; AppHear2 Supabase/auth/runtime toggles excluded; guest/local UI only |
| 2026-07-21 | Phase 5 Text-to-ASL shell refinement | `fragment_text_to_asl.xml`, `TextToAslFragment.kt`, translator drawables, strings; docs/progress updated | `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2`; protected recognition file/model/MediaPipe asset hash check | PASS; WebView/GLB/speech/TTS/recent-store behavior excluded and deferred |
| 2026-07-22 | Text-to-ASL UI space cleanup | `fragment_text_to_asl.xml`, `TextToAslFragment.kt`, `MainActivity.kt`, `strings.xml`; docs/progress updated | `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` | PASS; large Respond button removed, compact Reply route added under speaker, bottom nav hidden only on Text-to-ASL; recognition/runtime files unchanged |

| 2026-07-22 | Speech input + ElevenLabs/Android TTS | `ui/speech/*`, `TextToAslFragment.kt`, `RecognitionActivity.kt`, `build.gradle.kts`, `AndroidManifest.xml`, `strings.xml`; docs/progress updated | `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` | PASS; existing Text-to-ASL mic/speaker and Recognition Speak button wired; AppHear3 recognition pipeline unchanged |

| 2026-07-22 | Settings configuration status layer | `build.gradle.kts`, `ui/settings/AppConfiguration.kt`, `SettingsFragment.kt`, settings row layouts, docs/progress updated | `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2`; redacted generated `BuildConfig` check | PASS; Supabase/ElevenLabs configured status visible; no Supabase auth/database writes; recognition runtime unchanged |

| 2026-07-22 | Recognizer Speak-as-reply to Text-to-ASL | `RecognitionActivity.kt`, `MainActivity.kt`, `TextToAslFragment.kt`, `app_shell_nav.xml`, `strings.xml`; docs/progress updated | Checkpoint `testDebugUnitTest assembleDebug` after each affected surface; final `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` | PASS; speech-to-text reply routed through shell/nav arg; pending auto-submit is lifecycle-safe and one-shot; recognition runtime unchanged |

| 2026-07-22 | Recognizer Hear button TTS | `activity_recognition.xml`, `RecognitionActivity.kt`, `strings.xml`; docs/progress updated | UI checkpoint build + final `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` | PASS; Hear speaks recognized sentence via ElevenLabs/Android TTS fallback; Speak remains speech-to-text reply; recognition runtime unchanged |

| 2026-07-22 | Recognizer sentence card reposition | `activity_recognition.xml`; docs/progress updated | `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` | PASS; sentence display moved above collapsible panel and follows panel position; recognition runtime unchanged |

Every future entry records the exact screen/component, changed files, build/tests, device result when
applicable, rollback point, and remaining issue IDs.

## Assumptions requiring confirmation

- Navigation Component and dedicated recognition activity are accepted.
- Phase 2 can proceed before final auth/avatar/conversation scope decisions.
- Source control or a backup destination can be established before implementation.

## Decisions

This document's phase order and protected surfaces are the migration contract. Deviations require an
explicit decision-log entry before code changes.

## Known risks

- A large all-at-once resource import can hide collisions and inflate APK size.
- A launcher switch before recognition routing is proven can strand users away from the core feature.
- Lifecycle regressions may pass JVM tests and require repeated physical-device navigation tests.
- Backend/UI scaffolding can be mistaken for working features unless empty/unavailable states are
  explicit.

## Current status

Phases 0, 1, the no-asset portion of Phase 2, Phase 3 navigation placeholders, Phase 4 shared component resources, and the Phase 5 Home/dashboard, guest Profile/settings, and Text-to-ASL shell screens are complete. A rollback copy exists at `C:/tmp/apphear3-android-backup-20260721-uidesign-phase2/`. Fonts and visual assets remain blocked until provenance/license approval. The existing `MainActivity` remains the launcher and recognition baseline; `AppShellActivity` is non-exported until launcher switching is explicitly verified in a later phase. The next permitted implementation step is Phase 6 continuation: complete manual interaction/signing smoke for `RecognitionActivity`, then remove or retire the temporary `AppShellActivity` scaffold after confirming no route still depends on it. Do not add Text-to-ASL WebView/GLB/speech behavior until asset and data-contract gates are closed.


### 2026-07-21 UI correction gate inserted before later migration phases

Later migration work is paused until visible UI drift is corrected against `context/design/` screenshots and the actual AppHear2 XML/resources. The first corrected screen is Home/dashboard. Verification: `assembleDebug` PASS, `testDebugUnitTest` PASS, protected model/config/MediaPipe asset hash check PASS. Device visual smoke is pending because ADB listed no attached device.

New context file: [`android-ui-reference-correction.md`](android-ui-reference-correction.md).

Next permitted UI work: correct one remaining screenshot group at a time, preferably Recognition if addressing the highest-value visible surface, or Text-to-ASL if choosing the safer non-camera UI first. No later feature/data/backend migration resumes until this UI correction pass is complete or explicitly re-scoped.