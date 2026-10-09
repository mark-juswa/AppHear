# AppHear Text-to-Sign preview - implementation and handoff

Date: 2026-10-09. Branch: apphear/text-to-sign-redesign. Base: 1e215aebd69a173dd198aa5598a89600072d22fe.

This follow-up supersedes the download/build blockers in INITIAL-ASSESSMENT.md. The complete upstream Android application, renderer and all 102 GLB assets are now present. No source outside this development clone was changed. Nothing was pushed to GitHub.

## What is implemented

The existing Android interface accepts typed or speech-recognized input. A whole-input alias lookup selects one existing phrase or word clip. Unsupported text is rejected in full; no partial fingerspelling or English word concatenation occurs. Numbers, non-Latin characters and internal punctuation are retained so input cannot silently turn into an unrelated alias. Phrase playback uses its declared GLB animation name, plays once, and supports Repeat, Pause/Resume and speeds 0.5-1.5x. All resources load locally through WebViewAssetLoader; the viewer blocks network requests. One viewer limits overlapping playback and memory use. Generation tokens ignore stale callbacks, loads time out, renderer errors are visible, and leaving the screen pauses an active phrase.

This is explicitly an American Sign Language (ase) PREVIEW. The user approved labeled existing clips on 2026-10-09. Every manifest entry is unreviewed with empty reviewer/reference/evidence fields. No clip has been asserted to be linguistically correct. Five suggested samples: hello, thank you, how are you, nice to meet you, I love you. These are playback samples, not five verified signs.

The preview installs as com.example.apphear.redesign / AppHear Preview, alongside the original app. Recognition sources, MediaPipe, model binaries and navigation are preserved. This application is a debug build for development testing.

## Evidence and root causes

The original greedy planner consumed unknown input a character at a time and could switch into suffix word aliases. Missing letters were skipped: banana could yield BAAA; hi there could yield HELLO HERE. Numeric input was erased. This broke the relationship between input and output independently of rig quality. The original renderer used default looping playback and a seven-second advancement timeout rather than actual completion, plus two avatar viewers. The redesign removes this behavior from its enabled path.

All 102 upstream GLBs contain a single animation and animate hand/finger bones. Typical sign skeletons have 52 joints; the idle asset has two 67-joint skins. Importing differing skeletons can produce visual discontinuity, but there is no shared-rig retargeting step established in this implementation. Hand orientation and sign timing require visual review. Sign GLBs did not contain morph-weight animation channels; this does not establish adequate facial/non-manual signing. Assets alone do not establish linguistic validity.

Actual Android WebView testing found another problem: model-viewer 4.3.1 reached the final animation position without emitting its public finished event after model replacement. The page now observes currentTime/duration every 100ms as well as listening for finished; it never marks success based on elapsed wall time. A separate watchdog reports failure. See the pinned engine's animation.ts and ModelScene.ts: https://github.com/google/model-viewer/tree/v4.3.1/packages/model-viewer/src . The engine source was not modified.

## Architecture choice and remaining validation

| Approach | Accuracy potential | Android/offline/performance | Effort and maintenance | Decision |
|---|---|---|---|---|
| CWASA + SiGML | Depends on verified sign descriptions and non-manual features; no English translator | WebGL client exists; official site says some Android support; package/device/license assessment required | Requires licensed runtime/assets and reviewed descriptions | Further research, not integrated |
| Validated GLB clips | Good for a bounded reviewed dictionary, not arbitrary sentence translation | Existing bundled WebView renderer; mobile memory/device tests needed | Fits current code; each clip needs review and rights documentation | Existing clips allowed only as preview |
| Video-to-motion capture | Finger orientation, occlusion, depth and face are difficult | Offline generated clips possible; inference is extra work | Substantial cleaning, retargeting and signer review | Later asset-authoring route |
| Qualified-signer videos | Preserves real hands, face and posture for reviewed phrases | Android native video is straightforward offline; storage grows | Recording/consent/licensing and dictionary maintenance | Recommended reliable validated dictionary |
| Hybrid video + validated avatar | Reviewed video provides fallback; approved avatar where useful | Modular local playback; choose output per entry | Two formats and clear review gates | Recommended production direction |

CWASA research: https://vh.cmp.uea.ac.uk/ . Offline redistribution rights for the actual engine/avatar/sign resources must be established; an example/content license cannot be assumed to license everything. This preview reuses upstream assets and records their undocumented license status. Confirm rights before public distribution. No substitute FSL dictionary was added. Future FSL must use separate language IDs/data.

Next: engage qualified Deaf ASL reviewers, record evidence/reviewer/date and rights per phrase, approve at least five signs or licensed videos, then add a validated-only dictionary filter and reviewed video fallback. A validation flag is metadata, not proof. Sentence grammar, continuous coarticulation and non-manual semantics are not implemented. Do not use this preview as validated communication output.

## Changed files

- android/app/build.gradle.kts: redesign flag, separate debug app identity.
- domain/texttoasl/{AslPhrasePlanner,AslTextNormalizer,AslAnimationAsset}.kt: strict lookup and clip metadata.
- ui/texttoasl/{AndroidAssetAslCatalogLoader,TextToAslFragment,TextToAslPlaybackController}.kt: local initialization, UI controls, cancellation/error bridge.
- assets/model_viewer.html: single named-clip player and lifecycle/timeline checks.
- assets/model_viewer_legacy.html: untouched original page retained for rollback.
- assets/asl_animations/manifest.json: language, actual animation name, provenance and review fields.
- res/layout/fragment_text_to_asl.xml, res/values/text_to_asl_redesign.xml, src/debug/res/values/strings.xml: preview notice and playback controls.
- StrictAslPlannerTest.kt, TextToAslPlannerTest.kt, TextToAslAssetManifestTest.kt and tools/test-preview-playback.cjs: regression checks.
- .gitignore: exclude Kotlin local cache. No secret/local Gradle settings are part of the source change.

## Build and rollback

Use Android Studio with JDK 17 and Android SDK platform/build-tools 36. This clone uses Gradle 8.13. Copy android/gradle.properties.example to ignored android/gradle.properties for AndroidX settings; leave secret fields empty unless needed for your own deployment. Configure local SDK/JAVA_HOME. From android:

```powershell
./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2
node tools/test-preview-playback.cjs
```

APK: android/app/build/outputs/apk/debug/app-debug.apk. The exported phone installer is ../AppHear-TextToSign-Preview.apk. Rebuild with -PtextToAslRedesign=false to restore the legacy planner/viewer path. The preview package identity and catalog metadata remain; rollback is not a linguistically validated system either. The upstream base commit remains available in Git.

## Testing and review

41 JVM tests passed, including existing recognition skew tests and strict planner/asset tests. The JavaScript regression harness passes cancellation, duplicate completion, missing named animation, failed load, pause/speed/resume, looping idle and final timeline completion without an event. Built debug APK installed and launched on API 36 Medium_Phone emulator using software graphics. Native hello input reached Complete and Repeat at 0.5x completed. Five clips also passed debugger-driven actual WebGL playback and 250ms pause/resume: hello, thank_you, how_are_you, i_love_you, nice_to_meet_you. Observed single-sample load times were 137-809ms on this emulator; these are diagnostics, not device benchmarks. See ../EMULATOR-PLAYBACK-RESULTS.json. This is engineering verification only.

Physical-phone camera/recognition smoke, WebGL compatibility, offline air-plane-mode test, responsiveness p50/p95 and memory measurements remain device-run work. Follow context/device-smoke.md for preserved recognition behavior. No performance threshold, sign comprehension percentage or Deaf-user validation is claimed.

Review: plan alignment passes for the user-approved preview scope; original five VERIFIED-sign milestone remains open. System integrity passes source boundary and unit checks; recognition feature schema was not changed, so /imprint has no schema update. Production readiness is blocked by unreviewed signs, undocumented asset rights and pending physical-device testing. Recommendation: development preview only. No critical implementation finding remains from tested flow; important open items are linguistic validation, rights and physical device smoke; minor item is APK size (~197 MiB from bundled upstream assets).
