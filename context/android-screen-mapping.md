# Android Screen and Feature Mapping

## 2026-09-28 Profile/Auth mapping update (supersedes historical deferred entries)

User approved restoring the established account flow after reference inspection. ProfileFragment
owns the original card and preferences order; ProfileAccountContent owns the inline editor and
reference Login/Register overlay, without a new destination or Edit→Settings redirect. AccountRepository
owns Auth metadata/session IO; EncryptedAccountSessionStore owns remembered credentials. Debug-only
profileAccounts pilot implemented/installed, offline and synthetic physical gates pass; live account,
avatar policy and manual UI acceptance pending backend reactivation. Default/release remain guest.

Last updated: 2026-07-21  
Status: Home/dashboard, Recognition, and Text-to-ASL UI reference corrections BUILD GREEN; remaining screenshot UI corrections pending

## Purpose

Map every verified AppHear2 screen and user-facing feature to the production AppHear3 application.
Use this file to decide whether an item is rebuilt, adapted, merged, deferred, or excluded, and to
track migration status without guessing from filenames.

## Scope and sources of truth

- Reference UI: `D:/Programming/MOBILE APP/3.1 New Way/backup/AppHear2/app/src/main/`
- Production runtime/UI: `F:/ASL DATASET/5. Apphear3/android/app/src/main/`
- Verified project details: [`android-project-inventory.md`](android-project-inventory.md)
- Target destinations and boundaries: [`android-ui-architecture.md`](android-ui-architecture.md)
- Phase/status rules: [`android-migration-plan.md`](android-migration-plan.md)
- Design tokens/assets: [`android-design-system.md`](android-design-system.md); UI correction tracker: [`android-ui-reference-correction.md`](android-ui-reference-correction.md)

## Status vocabulary

`NOT STARTED` -> `SCAFFOLDED` -> `MIGRATING` -> `BUILD GREEN` -> `DEVICE VERIFIED` -> `DONE`.
`DEFERRED` and `EXCLUDED` require a decision-log entry before they can change.

## Screen mapping

| AppHear2 screen | Relevant reference files | Purpose and verified behavior | AppHear3 destination | Action | Dependencies/data | Navigation | Main risks | Status |
|---|---|---|---|---|---|---|---|---|
| First-run splash | `SplashActivity.java`; `activity_splash.xml`; `bg_splash_screen.xml`; `splash.png` | One-time Get Started gate stored in `apphear_onboarding` preferences | `OnboardingFragment` or equivalent first-run destination | Rebuild | first-run preference; approved mascot/art | launcher -> onboarding -> app shell | copying launcher manifest; inaccessible/oversized art; reset behavior | NOT STARTED |
| Loading/brand transition | `LoadingActivity.java`; `activity_loading.xml`; `applogo.png`; icon art | Animates logo, per-letter slogan, and three icons; forces navigation after 3150 ms | Startup transition inside launcher/shell | Adapt and merge | static assets only; no recognition preload in reference | onboarding/launch -> home | forced delay; handler leaks; confusing it with model loading | NOT STARTED |
| Home/dashboard | `MainActivity.java`; `activity_main.xml`; `FeatureCardAdapter.java`; two `item_feature_card_*.xml`; `nav_bottom.xml` | Greeting, auth name, recent-word chips, two-card pager, bottom navigation | Final `MainActivity` homepage/shell hosting `HomeFragment`; temporary `AppShellActivity` remains only as cleanup candidate | Rebuilt shell UI now hosted by `MainActivity` | local guest name; truthful empty local history; recognition route; Text-to-ASL route | home tab; current and final recognition card -> `RecognitionActivity` | manual signing/device interaction smoke still pending | BUILD GREEN after AppHear2 screenshot/XML correction; visual device smoke pending; temporary AppShellActivity cleanup pending |
| Sign detection | `SignDetectActivity.java`; `activity_sign_detect.xml`; old `ml/`, `mediapipe/`, model assets | Old camera recognition UI, TTS, candidate/confidence display, sentence, camera flip | Dedicated `RecognitionActivity` backed only by AppHear3 runtime | Parity scaffold created first; visual redesign later | current S0-S8 runtime; camera permission; Android TTS optional later | shell Home/Text-to-ASL -> `RecognitionActivity` -> back | catastrophic regression if old pipeline or assets are copied; camera lifecycle; device smoke still required | BUILD GREEN after AppHear2 visual correction; automated runtime device smoke passed; manual signing/visual QA pending |
| Text/speech to ASL | `texttoasl/TextToAslActivity.java`; `activity_text_to_asl.xml`; `avatar/*`; `texttoasl/*`; `assets/model_viewer.html`; `assets/asl_animations/*` | Plans known phrases/letters, plays local GLB files in WebView, accepts text/speech, supports replay and spoken output | `TextToAslFragment` shell; dedicated playback host only if later WebView lifecycle requires | Rebuilt shell UI; defer playback/speech/data behavior | local text preview only; WebKit/GLB/speech/TTS contracts later | ASL tab; Open recognition -> existing protected `MainActivity` | 300+ MB assets; incomplete vocabulary; WebView security/lifecycle; no-ASL-match behavior | BUILD GREEN after AppHear2 visual correction; PLAYBACK/SPEECH/ROUTE SCREENSHOT DEFERRED |
| Profile and auth | `ProfileActivity.java`; `activity_profile.xml`; `auth/SupabaseAuthManager.java`; profile/settings row drawables | Guest state, login/register, profile edit, avatar upload, settings list | `ProfileFragment` plus `SettingsFragment` in shell graph | Rebuilt guest/local UI; defer live auth | guest display state; passive AppHear2-style settings rows; backend contract later | profile tab; profile button -> settings; auth sub-route if approved | plaintext tokens; missing refresh; unknown RLS/storage policy; old runtime toggles must stay passive and non-persistent | BUILD GREEN after AppHear2 settings/profile visual correction; AUTH DEFERRED |
| Combined conversation | `conversation/ConversationActivity.java`; `activity_conversation.xml`; chat item layouts | Switches between signing camera and responding avatar/text/speech; duplicates both feature pipelines | `Conversation` feature composed from recognition and text-to-ASL interfaces | Rebuild after both parent features; do not port duplicated pipelines | recognition engine interface; avatar player; TTS; conversation-session state | no reference route was found; proposed from recognition/text-to-ASL | currently unreachable; 782-line god activity; duplicate camera/model ownership | DEFERRED |
| Batch processing developer tool | `batch/BatchProcessActivity.java`; `activity_batch_process.xml`; `VideoLandmarkProcessor.java`; batch/data writers | ADB-launched old in-app video-to-landmark regeneration | No production destination | Exclude | offline AppHear3 pipeline is authoritative | none | old feature/model schema, exported dev activity, storage/privacy | EXCLUDED |

## Shared component mapping

| Reference component | Source | Target component | Action | Risks/status |
|---|---|---|---|---|
| Bottom navigation | `nav_bottom.xml`, `NavTouchAnimator.java` | Material bottom navigation owned by `AppShellActivity` | Rebuild | Navigation shell scaffold uses one graph/menu; visual polish still pending; SCAFFOLDED |
| Feature cards | `item_feature_card_detect.xml`, `item_feature_card_project.xml`, `FeatureCardAdapter.java` | Reusable `FeatureCardView`/layout model | Adapt visual design | `component_feature_card.xml` scaffolded; screen data binding pending; SCAFFOLDED |
| Detection bottom sheet | `activity_sign_detect.xml`, shape drawables | Recognition controls panel | Rebuild | Must render `RecognitionUiState`, not own inference; NOT STARTED |
| Text-to-ASL bottom sheet | `activity_text_to_asl.xml` | Translator input/control panel | Adapt | IME, speech, and WebView lifecycle; NOT STARTED |
| Conversation bubbles | `item_chat_bubble_signing.xml`, `item_chat_bubble_response.xml`, adapter/models | Conversation message list | Defer with conversation | No durable store; DEFERRED |
| Profile/settings panel | `activity_profile.xml`, `row_setting_*.xml` | Settings sections and reusable rows | Adapted as passive UI rows | Guest/local profile and settings rows are BUILD GREEN after screenshot/XML correction; old toggles are non-interactive and non-persistent |
| Status/live badges | `bg_status_pill.xml`, `bg_live_badge*.xml`, dot drawables | Shared status chip | Adapt | `component_status_chip.xml` scaffolded with text plus dot; variants pending; SCAFFOLDED |
| Buttons/cards/shapes | `bg_btn_*`, `bg_*pill*`, cards, circles | Tokenized shared styles | Adapt/rename | Shared button/card styles plus panel/chip/circle drawables scaffolded; SCAFFOLDED |
| Inter font family | `res/font/inter_*.otf` | App typography resources | Verify license, then adapt | Six weights add size; NOT STARTED |
| Mascots/brand images | PNG assets in `res/drawable` | Branded illustrations | Verify/optimize/rename | Provenance, density, compression, content descriptions; NOT STARTED |

## Feature mapping

| AppHear2 feature | Verified source/data | AppHear3 equivalent | Decision | Destination/status |
|---|---|---|---|---|
| Camera preview | `SignDetectActivity`, `ConversationActivity` | current recognition-bearing `MainActivity` + new parity `RecognitionActivity` + `FrameAnalyzer` | Keep AppHear3 implementation; verify `RecognitionActivity` parity before shell conversion | RecognitionActivity / BUILD GREEN, DEVICE SMOKE PENDING |
| Front/back camera | old `flipCamera()` | current `cameraToggle`, `rebindCamera()`, session reset | Preserve current behavior, restyle only | RecognitionActivity / NOT STARTED |
| Landmark overlay | `LandmarkOverlayView` incl. optional face | `OverlayView`, hand+pose only | Preserve AppHear3 overlay; no face | RecognitionActivity / NOT STARTED |
| Recognition model/inference | old `ml/`, `sign_classifier*.tflite` | schema-3.0 `RecognitionPipeline`, `streaming.tflite` | Exclude old; keep current unchanged | Protected / current |
| Top candidates | old confidence/candidate tracker | current `RecognitionState` top-three list | Preserve current result; redesign presentation | RecognitionActivity / NOT STARTED |
| Sentence builder | old activity `StringBuilder`, max 5 | current S8 `SentenceBuilder`, max 20/dedup | Keep AppHear3 S8 source of truth | RecognitionActivity / NOT STARTED |
| Handedness | old hidden/automatic pipeline settings | current explicit Right/Left toggle | Preserve and make clearly discoverable | Recognition/settings / NOT STARTED |
| FPS/degraded mode | old debug FPS/status | current `RuntimeProfiler`, `LowFpsMonitor`, degraded banner | Keep current semantics; separate user vs developer diagnostics | RecognitionActivity / NOT STARTED |
| Start/stop detection | explicit old button | AppHear3 begins after permission/warmup | Product decision: add UI pause without destroying engine, or omit | UNRESOLVED |
| Speak detected sentence | TTS plus optional ElevenLabs | no current equivalent | Rebuild with Android TTS first; cloud voice deferred | RecognitionActivity / NOT STARTED |
| Recent signs | text-input `RecentSignsStore` | none | Replace with accurately named recent activity/history contract | Home / DEFERRED |
| Text-to-ASL avatar | local GLB + WebView | none | Adapt only after asset/performance verification | TextToAsl / NOT STARTED |
| Speech input | Android `RecognizerIntent` | none | Adapt with explicit availability/error states | TextToAsl / NOT STARTED |
| Account/profile | Supabase custom REST | none | Guest-first; backend separately approved | Profile / DEFERRED AUTH |
| Avatar upload | Supabase Storage public URL | none | Defer with auth/storage policy | Profile / DEFERRED |
| Settings: dominant hand | not a clean old setting | current preference in `MainActivity` | Promote to settings + keep quick recognition control | NOT STARTED |
| Settings: face landmarks | old `AppSettings` | forbidden in AppHear3 | Exclude | EXCLUDED |
| Settings: extended/core old models | old classifiers | obsolete | Exclude | EXCLUDED |
| Settings: low latency/smart detection/duplicate/hand gate | old v2 policy switches | current config/feature flags, offline-gated | Do not expose old controls; consider read-only diagnostics only | EXCLUDED initially |
| Settings: rotate offload/parallel/profiling | old developer experiments | current fixed/flagged runtime behavior | Developer-only build surface, not normal user settings | DEFERRED DEV |
| Cloud voice | ElevenLabs key in BuildConfig | none | Optional future feature; Android TTS fallback first | DEFERRED |
| LLM gloss translation | `LlmGlossTranslator`, Tasks GenAI dependency | S8 LM assist intentionally deferred | Exclude from UI migration | EXCLUDED initially |
| Batch landmark regeneration | exported dev activity | offline Python extraction pipeline | Exclude | EXCLUDED |

## AppHear3-only capabilities that must remain reachable

| Capability | Current source | Required target location | Protection |
|---|---|---|---|
| Schema/shape refusal | `ModelContract.validateOrThrow()` | Recognition engine startup | No UI bypass; human-readable fallback |
| Recognition kill-switch | `FeatureFlags.RECOGNITION_ENABLED` | Runtime only | Camera/overlay fallback must still launch |
| Load-failure fallback | `MainActivity.start()` `runCatching` | RecognitionActivity/controller | Preserve camera-only operation and error state |
| Pre-onset buffer and low-FPS policy | `RecognitionPipeline`, runtime config | Runtime only | UI observes state; never duplicates gates |
| One commit per signing bout | `awaitingRelease` | Runtime only | Navigation/UI must not replay commits |
| Top-three candidates | `Confirmation.topCandidates` -> state | Recognition controls | Preserve ordering |
| Dominant-hand override | `SessionNormalizer.handedness` | Recognition quick action + setting | Reset session after a change |
| Camera convention/session reset | `MainActivity.rebindCamera()` | Recognition controller | Preserve analysis/preview mirroring contract |
| Runtime measurements | `FrameResult`, profiler, low-FPS monitor | User status + developer diagnostics | Throttle UI updates; preserve p50/p95 logs |
| S8 sentence clear | `RecognitionPipeline.clearSentence()` | Recognition controls | Single source of truth |

## Navigation destination map

```text
Launcher
  -> first run: Onboarding
  -> returning: AppShell/Home

AppShell
  Home
    -> RecognitionActivity
    -> TextToAsl
  TextToAsl
  Profile/Settings

RecognitionActivity
  -> back to previous shell destination
  -> optional future Conversation (deferred)

Conversation (deferred)
  -> composes recognition + text-to-ASL interfaces; owns neither pipeline
```

## Assumptions requiring confirmation

- `ConversationActivity` is a desired future experience despite having no current route.
- Text-to-ASL and all bundled GLB animations are in release scope and licensed for reuse.
- A separate Learn page is not present in the inspected reference; the ASL tab is text-to-ASL,
  not a lesson/course feature.
- History means locally persisted recognition/translation activity, not cloud analytics.

## Missing/unresolved

- Whether detection requires a user-visible start/stop control in the new UX.
- Final first-release scope for auth, cloud speech, avatar, conversation, and history.
- Behavior when text cannot be mapped to a bundled ASL animation.
- Required retention/privacy rules for any future history.

## MainActivity homepage/shell decision

Final structure: MainActivity is the homepage/shell, and recognition lives in a dedicated RecognitionActivity. Current AppShellActivity and Home routes are temporary scaffolding from the safe migration phase. The next recognition phase must create/verify RecognitionActivity first, then fold the shell into MainActivity without changing AppHear3 recognition behavior.

## Decisions and risks

- Activity/layout names in this table are evidence, not a copy list.
- Recognition is a dedicated destination so camera and inference do not live in the general shell.
- The combined conversation experience is rebuilt from interfaces only after both parent features
  are stable; the old activity is never copied.
- Backend-dependent screens remain visually scaffoldable but cannot claim working sync without a
  verified backend contract.

## Current status

Home/dashboard, Recognition, Text-to-ASL, and Settings/Profile are build-green after AppHear2 screenshot/XML correction passes. Final architecture is now active: `MainActivity` is the homepage/shell and dedicated `RecognitionActivity` is the recognition screen. RecognitionActivity startup/runtime automated smoke partially passed; manual signing/interaction checks remain pending. Text-to-ASL playback, speech, TTS, and recent-store behavior remain deferred behind asset/provenance and data-contract gates.
