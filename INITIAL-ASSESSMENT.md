# AppHear — Initial Text-to-Sign Technical Assessment

Date: 2026-10-09 (Asia/Manila)
Upstream: https://github.com/mark-juswa/AppHear
Inspected revision: `1e215aebd69a173dd198aa5598a89600072d22fe`
Scope: repository discovery, source-level diagnosis, solution assessment. No application code changed.

## 1. Clone and preservation

The canonical development clone is this `AppHear-source/` folder. It is a shallow, filtered Git clone of upstream main with a sparse checkout. Android source/resources, root documentation, project context, and relevant tests are present. The complete upstream file tree is recorded in Git; omitted binary blobs can be fetched later. It is **not yet a complete offline build checkout**.

Full-history and full-snapshot download attempts stalled or progressed too slowly. Representative binary fetches also failed with "unable to read sha1 file". Those processes were stopped. Incomplete attempts are retained under the workspace's work folder; they are not development projects.

Original upstream content remains available at HEAD. No push, commit, application rewrite, recognition change, or secret configuration was performed. Git status was clean before adding this assessment. Do not confuse repository-reported historical builds or accuracy with verification in this session.

## 2. Actual project structure

- `android/`: production native Android Gradle project, Kotlin/XML, namespace and application ID `com.example.apphear`.
- `apphear-react/`: separate experimental React Native project; not the native APK implementation being redesigned.
- `asl recorder/ASLRecorder2/`: separate recorder Android project.
- `pipeline/`, `model/`, `eval/`, `deploy/`, `tests/`: Python recognition/data/training/evaluation tooling.
- `context/`, `docs/`, `artifacts/`: operational documentation and research artifacts.

The native launcher is SplashActivity; the shell routes through MainActivity. RecognitionActivity owns Sign-to-Text. TextToAslFragment owns the signing interface. The current public repository describes AppHear 3, not just the older AppHear2 implementation referenced by historical docs.

Protected surface: RecognitionActivity, `pipeline/**` Kotlin, S4 feature math, confirmation policy, TFLite model/manifests/vocabulary/configuration, and MediaPipe task assets. Text-to-Sign does not need modifications to any of those.

## 3. Text-to-Sign implementation and dependencies

Actual files, relative to this clone:

| File | Responsibility |
|---|---|
| android/app/src/main/java/com/example/apphear/ui/texttoasl/TextToAslFragment.kt | Text/speech input, submit/replay/clear, queue/progress, seven-second advancement timer |
| android/app/src/main/java/com/example/apphear/domain/texttoasl/AslTextNormalizer.kt | Lowercase, punctuation removal, whitespace normalization, standalone hi/hey mapping |
| android/app/src/main/java/com/example/apphear/domain/texttoasl/AslPhrasePlanner.kt | Greedy longest alias match, character-level fallback |
| android/app/src/main/java/com/example/apphear/domain/texttoasl/AslAnimationCatalog.kt | Catalog, alias lookup, duplicate ID/alias rejection |
| android/app/src/main/java/com/example/apphear/domain/texttoasl/AslAnimationAsset.kt | ID, display text, GLB path, type, aliases |
| android/app/src/main/java/com/example/apphear/domain/texttoasl/TextToAslPlan.kt | Queue, requested/normalized text, unsupported characters; any nonempty queue is playable |
| android/app/src/main/java/com/example/apphear/ui/texttoasl/AndroidAssetAslCatalogLoader.kt | Parse manifest and check referenced assets can open |
| android/app/src/main/java/com/example/apphear/ui/texttoasl/TextToAslPlaybackController.kt | Local WebView setup and Android/JavaScript callbacks |
| android/app/src/main/assets/model_viewer.html | Two model-viewer elements, model swapping/preloading, playback |
| android/app/src/main/assets/asl_animations/manifest.json | 102 catalog entries |
| android/app/src/main/assets/asl_animations/*.glb | 102 tracked prerecorded avatar assets |
| android/app/src/main/assets/vendor/model-viewer/model-viewer-4.3.1.min.js | Bundled model-viewer renderer |
| android/app/src/test/java/com/example/apphear/TextToAslPlannerTest.kt | Mapping/normalizer/catalog tests |
| android/app/src/test/java/com/example/apphear/TextToAslAssetManifestTest.kt | Manifest coverage, GLB header/animation presence, local renderer reference checks |

Checked-in dependencies: AndroidX WebKit 1.16.0, model-viewer 4.3.1, Android Gradle Plugin 8.11.2, Kotlin 2.0.21, Gradle wrapper 8.13. Android compile/target SDK 36; minimum SDK 26. These are inventory values, not a recommendation to upgrade other components.

Sign-to-Text uses CameraX, MediaPipe Tasks Vision 0.10.14 and TFLite 2.16.1. These do not generate avatar poses.

There is no SiGML engine in the current Text-to-Sign workflow, no text-conditioned pose generation, and no runtime landmark-to-avatar retargeting in the inspected module. It selects GLB files and plays their embedded animations. No tracked .blend, .fbx, .bvh, .sigml or .mp4 reference/source files were found by extension inventory. The export/retargeting process and source signer references remain unverified.

The binary download failure prevents direct verification of GLB skeleton names, skin joints, hand/finger channels, morph targets, clip duration and mesh deformation in this session. The filenames are not evidence of correct signs.

## 4. Complete input-to-output path

1. Typed input, system speech transcript, or navigation incoming_text enters TextToAslFragment.
2. Submit calls AslPhrasePlanner.plan().
3. AslTextNormalizer lowercases English text, removes apostrophes/question marks, replaces other non-alphanumeric punctuation, and compresses spaces.
4. Catalog registers IDs, display text and aliases. Planner chooses the longest matching alias at the beginning of the remaining string.
5. If no alias matches, it consumes one character and optionally adds an available letter clip. Unsupported letters are collected; numbers are silently consumed.
6. Fragment stores the queue and calls TextToAslPlaybackController.play(), then preloads the next clip.
7. WebView loads local HTTPS-style URLs at appassets.androidplatform.net through WebViewAssetLoader. File/content access is disabled, mixed content prohibited, network loading blocked.
8. playSign() swaps between two model-viewer elements. It selects the first embedded animation and calls play().
9. JavaScript finished events call Android.onAnimationFinished(); the fragment advances. Independently a seven-second timer advances the queue.
10. After the queue, the fragment plays the idle asset.

Replay and clear exist. Pause/resume, speed adjustment, explicit stop/cancellation tokens, and sign validation gating do not exist in the current module.

## 5. Confirmed defects and their implications

### A. Partial words and suffixes become misleading signs

Only A and B are letter-type catalog entries. The planner retries dictionary matching after every consumed character; matching therefore need not start at an original word boundary.

A read-only PowerShell transcription of the inspected planner, using the actual manifest, produced:

| Input | Clip IDs selected | Characters omitted |
|---|---|---|
| hello | hello | none |
| how are you | how_are_you | none |
| banana | b, a, a, a | n, n |
| hi there | hello, here | t |
| How many brothers do you have? | a, b, possessive_adjective, you, have | h,o,w,m,n,y,r,o,t,d,o |
| hello 123 | hello | digits silently ignored |
| rest | idle | none |
| good morning | good, morning | none |

This audit is a source-level reproduction, not execution of Kotlin unit tests or linguistic validation. It demonstrates why apparently unrelated clips can be selected without any random-number logic.

Internal IDs/display labels are also usable aliases, including idle/rest/stand. Maintenance poses should not become conversational output. Question-mark removal also erases a cue that a future phrase planner needs for non-manual features.

### B. Infinite looping defeats the completion workflow

model_viewer.html calls `viewer.play()` without repetitions and gives both viewers autoplay. Model-viewer 4.3.1 source defines default repetitions as Infinity. A normally looping sign does not finish after one rendition, so the Android safety timer can become the normal advancement mechanism.

A short sign can repeat for seven seconds. A slow load consumes some of that timer before playback begins; a long or stalled load can be skipped without completion. Setting a crossfade attribute does not blend skeletal motion between two different viewer elements: the current swap is a visual opacity transition.

Primary API evidence: https://raw.githubusercontent.com/google/model-viewer/v4.3.1/packages/model-viewer/src/features/animation.ts

### C. Failure, readiness and cancellation are incomplete

- Viewer readiness means the custom element is defined, not that a model is loaded/rendered.
- No GLB load-error callback or timeout/rejection exists in waitForModel().
- loadedUrls records historical URL loads, not whether a particular viewer's current model is ready. Reassigning a previously loaded URL can wrongly bypass waiting.
- Obsolete load listeners are not canceled when a newer request replaces the pending URL.
- Completion callbacks identify only URL/asset, not a unique playback request. Replay or repeated identical clips need a generation ID.
- Hidden viewers are not explicitly paused. Preloading starts autoplay and can use extra mobile resources.
- Clear switches toward idle but has no explicit stop/invalidation API.
- Unsupported-character warnings are overwritten immediately by playback progress and later Complete; signedText still displays the entire requested sentence.

These are confirmed source omissions and lifecycle risks. Their frequency and device impact have not been measured.

### D. No evidence-based linguistic acceptance gate

Manifest fields are only id/displayText/asset/type/aliases. There is no explicit language code, source/reference, sense/context, reviewer, validation date/status, license, signer consent, animation name/duration, non-manual specification or per-asset provenance.

Many phrase aliases use gloss-like order, such as "brother you how many". The code does not translate general English grammar into ASL, resolve meaning, establish discourse referents, or create question/negation facial expressions. Splitting a sentence into available English-word clips is not proof of an ASL sentence.

The intended language should remain ASL. Do not substitute UEA BSL examples or FSL data.

### E. Asset-specific rig defects remain hypotheses

Bad finger tracks, bone axes, skin weights, hand orientation, animation export or source mocap could explain distorted individual clips. None is established by filename or code inspection. Since each GLB is loaded as its own model, runtime cross-rig retargeting is not visible here; any retargeting damage may be baked into export.

Repository notes report 185.36 MiB of GLBs and a 193.45 MiB debug APK after expansion. These are historical reported measurements, not reproduced measurements. Per-clip embedded meshes/textures and two viewer instances warrant memory/load profiling.

## 6. CWASA assessment

CWASA is a plausible optional engine, not an automatic translation solution.

- UEA documents JavaScript/HTML5/WebGL rendering and client-side Animgen processing. It exposes init, playSiGMLText, playSiGMLURL, stopSiGML, readiness and event hooks.
- SiGML encodes HamNoSys manual features plus non-manual aspects. Reviewed ASL descriptions must be acquired/authored; arbitrary XML or BSL examples are not verified ASL.
- Documented controls include suspend/resume, frame stepping, speed and progress; integration must use the actual release's API.
- UEA reports operation on **some Android devices**, not universal Android WebView compatibility.
- A local package must include scripts/configuration, avatar definitions and sign files, use client-side generation, and point all paths to bundled resources. Existing Android WebViewAssetLoader is a suitable delivery mechanism, subject to actual package tests.
- The local-installation page mainly describes legacy JASigning ZIPs and server-fetched CWASA examples. It does not establish a complete offline Android CWASA package.
- UEA lists standard anna/marc/francoise avatars as freely usable; extended avatars are evaluation-only in the configuration documentation.
- Current conditions distinguish BY-SA example pages from underlying software that must remain unmodified on BY-ND-equivalent terms. Record exact distribution/license/attribution and permitted avatar/sign-data rights before APK redistribution. No licensing enquiry was sent.

A technical evaluation should prove local initialization, WebGL context creation/recovery, verified SiGML playback, offline behavior, loading failure handling and device performance. Configuration-ready is separate from avatarready. Use event-driven serialized playback, not the desktop Electron TCP protocol.

Sources:
- https://vh.cmp.uea.ac.uk/index.php/CWA_Signing_Avatars
- https://vh.cmp.uea.ac.uk/index.php/SiGML
- https://vh.cmp.uea.ac.uk/index.php/Configuring_CWASA_for_HTML5_web_pages
- https://vh.cmp.uea.ac.uk/index.php/Logging_and_Event_Hooks
- https://vh.cmp.uea.ac.uk/index.php/CWASA_Platform_Issues
- https://vh.cmp.uea.ac.uk/index.php/CWASA_Local_Installation
- https://vh.cmp.uea.ac.uk/index.php/CWASA_Conditions_of_Use
- https://developer.android.com/develop/ui/views/layout/webapps/load-local-content

## 7. Comparison and preliminary selection

| Approach | Accuracy potential | Android/performance | Effort and maintenance | Feasibility here |
|---|---|---|---|---|
| A: CWASA + reviewed SiGML | Depends on notation, generated motion and Deaf review; supports non-manual description | WebView/WebGL plausible; device/offline package unproved | Medium/high; specialist sign authoring and engine licensing | Optional evaluation backend |
| B: Verified GLB library | Good only after clip-by-clip linguistic and technical review | Already integrated; current asset size/loading costs substantial | Lowest integration effort, costly asset QC; export provenance needed | Retain for comparison; do not label current clips verified |
| C: Video/landmark mocap | Potentially good with qualified signer capture and correction; occlusion, depth, fingers and face are weaknesses | Authoring offline; optimized final clips on device | Highest effort: calibrated capture, rigging, cleanup and review | Later content-production workflow |
| D: Qualified-signer videos | Strongest direct preservation of reviewed hands, face and body for fixed phrases | Native local video playback practical; measure codec/load/storage | Moderate recording/licensing effort; easy per-item review | Preferred initial reliable baseline once assets exist |
| E: Video + verified avatar | Reliable validated fallback with optional 3D benefit | Native videos plus existing or CWASA WebView backend | Modular backend/validation registry; moderate integration work | Recommended product direction |

Choose **E, initially D**, with a phrase-first ASL registry. Keep current GLB playback as a quarantined evaluation backend and evaluate A independently. If five licensed reviewed ASL SiGML items become available first and the offline/device gates pass, A can serve the initial avatar proof of concept. This recommendation is preliminary because sign content, rights and device evidence are unresolved.

A renderer replacement alone will not fix unsafe mapping or unsupported text. Conversely, fixing the planner cannot repair an incorrect handshape baked into a clip.

## 8. Proposed architecture and dictionary contract — not implemented

Preserve the native screen/navigation and Sign-to-Text boundary.

Input -> meaning-preserving normalization -> exact approved phrase/word lookup -> plan with explicit unsupported spans -> selected validated media -> serialized playback controller.

Do not scan inside unknown words. Do not silently delete numbers or unsupported language. Default to a clear unsupported message; optionally offer separately labeled dictionary items without presenting them as a translated sentence. Fingerspelling requires a complete reviewed alphabet, J/Z movement, clear mode labeling and an explicit fallback policy.

Each registry item should include:
- stable ID, ASL language code, phrase text/aliases, sense/context and regional variant;
- media type/path, selected animation name, duration and permitted speed range;
- provenance/reference URL, source signer/author, license and attribution;
- validation state (unreviewed, technical-only, linguistically-approved, rejected), reviewer/date and evidence;
- non-manual features and review notes;
- checksum/content version and supported device/backend conditions.

Only linguistically-approved, licensed items enter user playback. Maintain separate ASL/FSL registries if FSL is later requested.

Controller states: initializing, ready, loading, playing, paused, completed, error, disposed. Every playback request has a generation token. Replacement/clear/navigation cancels prior loads/listeners/timers, stops active output and pauses the other viewer. Completion advances exactly once. Load failures do not report Complete. Provide repeat, pause/resume and supported speed controls; preserve review-approved timing ranges.

## 9. Incremental development gates

1. Finish complete clone and binary audit; parse all GLB JSON/BIN tracks and validate structure; review representative clips visually beside references. Obtain export/rig sources if possible.
2. Establish phrase registry and tests for token boundaries, unsupported words/numbers, identity/sense, approved-only selection and mixed input.
3. Repair existing playback under a rollback flag: single repetition, readiness/load errors, cancellation tokens, real completion, pause/speed controls.
4. Acquire five licensed ASL signs/phrases and documented qualified Deaf review. Candidate review list: hello, thank you, how are you, nice to meet you, I love you. Their presence in the current manifest does not make them verified.
5. Build parallel video and/or CWASA proof of concept without removing the old viewer. Document exactly which assets are approved.
6. Integrate only after build/tests and physical Android smoke pass.
7. Measure selection correctness, blinded comprehensibility review, manual/non-manual correctness, startup/load response, frame rate, memory, thermals, transitions, lifecycle stability and airplane-mode behavior. Do not invent acceptance percentages; agree thresholds before collection.
8. Expand only through repeatable content/licensing/review gates.

## 10. Checks performed and remaining limitations

Performed:
- Cloned and pinned source revision; inventoried the full Git file tree.
- Inspected native Android input/domain/controller/viewer/catalog/test/dependency files.
- Counted 102 manifest entries and 102 tracked GLB paths; zero missing tracked manifest paths.
- Confirmed only A/B letter entries and absence of validation/provenance fields.
- Reproduced planner behavior against actual aliases (PowerShell audit, not Kotlin execution).
- Verified infinite-loop default against model-viewer 4.3.1 primary source.
- Inspected UEA CWASA and Android primary documentation.
- Build preflight: gradlew --version failed because JAVA_HOME is unset and java is not on PATH.
- Android SDK directory exists; adb reported no connected devices.

Not performed:
- Complete binary clone, GLB skeleton/finger/morph-track inspection or visual validation.
- Android compilation, existing JVM/instrumentation tests, APK installation or device profiling.
- Working five-sign proof of concept, CWASA bundling or Android integration.
- Qualified Deaf linguistic review or rights clearance.

Build instructions for a later complete checkout:
1. Install/configure a compatible JDK (AGP 8.x requires JDK 17) and Android SDK platform 36; configure SDK location locally without checking it in.
2. Complete sparse checkout/downloads, including all Android assets and test resources. Use the canonical AppHear-source clone; avoid copying stale AppHear2 files.
3. From android/: `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2`.
4. Connect a device and run documented device-smoke checks, plus Text-to-Sign scenarios: exact phrase, unknown word, mixed input, numbers, repeated clip, clear during load, resubmit during load, offline startup, pause/resume/speed, navigation away/back.
5. Keep cloud configuration absent for baseline checks. Do not commit credentials, local.properties, keystores or secret Gradle properties.

Historical context contains drift: early paragraphs claim no WebKit/no playback while current code includes both, and the progress tracker is unusually large with malformed content noted in memory.md. Current source and direct evidence govern this assessment.

## 11. Session handoff

Completed: source-level Phase 1 assessment and preliminary Phase 2 comparison.
Changed files: this assessment only; application and recognition source untouched.
Next action: make the canonical clone complete, recover representative binary assets, and audit clip channels/rigs alongside a licensed ASL reference. In parallel, establish the source/permission/reviewer evidence for the five-sign proof of concept.

