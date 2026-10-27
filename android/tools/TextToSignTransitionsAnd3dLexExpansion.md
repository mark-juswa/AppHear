# Text-to-Sign transitions and direct 3D-LEX expansion — Update 8

Engineering preview dated 24 October 2026. Only Text-to-Sign source/assets and its development tools/tests changed. No GitHub push.

## Actual counts

- Added **49** real motion-backed lexical preview entries; **711 entries** total, **710 distinct active lexical actions**, **843 explicit English forms**.
- 789 packaged actions: 710 active lexical actions, 26 alphabet actions, one neutral, 52 inactive alternatives. NAME still shares the existing CALL-SOMEONE'S-NAME action; it is not counted as a new repair.
- Zero qualified ASL validations and zero validated complete sentence translations. Technically mapped/playable does not mean linguistically correct.
- Official archive: 938 GLB filenames. 343 were absent from current English forms/aliases. All 343 were audited; 49 passed the current conversion gates and 294 were not added. This archive cannot supply 400 genuinely new motions beyond the current app. The request remains short by 351 usable new entries; existing words, aliases and spelling were not counted as additions.

ALONE, ALWAYS, ANGRY, BEHIND, FULL, LATE, LONG, NEXT, WAY, AGAINST, APPEAR, AREA, ARGUE, ARMY, BAR, BEAR, BIRTH, BREAK, BUTTERFLY, DANGER, DEER, DORMITORY, DRUG, DRY, END, EXPECT, FIGHT, FISH, FOREST, FRIENDLY, GAMBLE, HURT, LAPTOP, MAD, MIRROR, MOUTH, NECKLACE, NOSE, OCEAN, PUNISH, RICH, SOAP, SOUR, STUBBORN, TEXT, UNDER, UP, WE, WONDER

Rejected candidates are individually recorded in `3dlex-expansion-audit.csv`:

- Abrupt rotation remains: 93.
- Duplicate source payload / sense review: 167.
- Invalid interior source bone lengths: 8.
- Missing animation data: 1.
- Retarget direction mismatch: 25.

## Confirmed causes and repairs

1. The imported converter adds 0.2-second neutral keys at BOTH boundaries of every clip. All 453 active imported entries were independently checked against their recorded source durations. The native queue now bypasses only that padding between different consecutive actions. Initial entry and final exit remain; repeated actions retain their boundaries. No linguistic sign boundary was guessed.
2. Lexical playback previously had no blend. A preliminary weight-1 pose overlay produced a halfway jump. Word boundaries now restore the held outgoing action after the mixer seek, then schedule a real 120-ms incoming/outgoing crossfade. There is no seek after scheduling the fade. Letter-to-letter timing/overlay behavior stays unchanged; word/letter boundaries share the resident human.
3. Completion uses the actual clip timeline/end window, not a fixed sequencing delay. The completion token is invalidated before endpoint seeking to prevent reentrant callbacks. Cancellation, repeated input and missing actions remain guarded.
4. 47 newly imported source files end with a near-180-degree global hip flip into the bind pose. Exclusion requires the final retained raw frame, a >90-degree global hip jump within 1/12 second, and at least 95% exact animated-rotation bind matches. That terminal export frame is excluded; interior source tracks are untouched. Existing bone-length, direction-error and per-frame rotation gates were NOT loosened. Source archives remain byte-identical.
5. No finger constraints, generic hand poses, mesh/skin-weight edits or shoulder locks were added. Original first 740 actions, alphabet, neutral, rig and geometry remain exact. New wrist screening found no >270-degree axial range or >100-degree local swing flags in the 49 source-motion cores; this is screening, not anatomical or ASL certification.

The source clips themselves still contain preparation/retraction and some rest movement. This fix removes verified converter padding; it does not claim natural linguistic coarticulation or automatically crop a signing stroke. Some isolated-clip arm lowering may remain. Previously unresolved LOVE/ME handshape/contact concerns are not declared fixed by this update.

## Evidence actually obtained

- JVM tests: 367, failures 0, errors 0, skipped 0.
- Four export-reset tests pass: targeted terminal corruption, natural rest return preserved, non-bind finger pose preserved, interior/slow movement untouched.
- Actual JavaScript player harness: all 789 named actions plus mixed/regression requests (843 requests), padding windows, callback ordering, reentrant seek, cancellation and missing-animation rejection pass.
- Independent GLB/catalog verifier passes; old working prefix and all 420 external actions remain exact. First 740 pre-expansion actions and binary data were independently preserved during append.
- All 49 new hand meshes were CPU-skinned at four phases for both hands and visually inspected. These untextured close-ups are not Android captures and do not establish lexical meaning.
- New Android audit: 49 / 49 entries have collected native selection, ten rendered phase samples and fresh continuous playback/completion evidence. Final combined two-test run: PASS.
- Final combined emulator run passed in 813.981 seconds: 49 fresh continuous lexical playbacks with 490 rendered pose samples, followed by all 91 normal inputs. Same resident avatar was asserted. Representative Android pose sheets inspected: ALWAYS, ANGRY, BEHIND, FULL, LONG and WE. All other new entries have collected captures; fine handshape/meaning review by ASL signers remains outstanding.
- The emulator-tested DEX code, player, dictionary and combined GLB exactly match the universal APK (22 files checked). Compared with Update 7, 1,664 non-code package entries match exactly, including app resources, manifest, models and native libraries; only the five intended Text-to-Sign asset files differ outside compiled code/signing metadata.
- Earlier 91-input emulator regression passed in 394.735 seconds. Refined before/after comparison passed in 102.734 seconds (APPLE TEA, ADULT BASEMENT, HELLO NICOLE, repeated APPLE). Final full normal-input regression is separately recorded with the expanded build.
- Frame gaps varied under capture/build load. Boundary-step measurements are diagnostic only; no smoother-motion percentage, production FPS, peak memory or ASL accuracy score is claimed.
- Physical phone testing, qualified ASL review and all-711 fine handshape validation were not performed. Existing non-manual/facial grammar limitations remain.

## Build and packaging

The existing SDK/Gradle/Kotlin/library versions and application versionName 1.0/versionCode 1 remain. The original debug preview flags and fake-service configuration remain the same as Update 7; no private credentials are included.

```powershell
$env:JAVA_HOME = "<existing JDK 17 directory>"
$env:ANDROID_HOME = "<existing Android SDK directory>"
$env:JAVA_TOOL_OPTIONS = "-XX:ActiveProcessorCount=2 -XX:TieredStopAtLevel=1"
& ./android/tools/build-integrated-preview.ps1 -Tasks @("testDebugUnitTest","assembleDebug","assembleDebugAndroidTest", "-Dorg.gradle.jvmargs=-Xmx2048m", "-Pkotlin.compiler.execution.strategy=in-process", "--init-script", "<existing verified-onnx.init.gradle>")
```

Desktop test heap is 1 GB, one fork, via `text-to-sign-test-memory.init.gradle`; Android runtime heap/settings are unchanged. One earlier run failed with a desktop heap OOM before this correction. The final rerun passed. The existing emulator-only x86_64 packaging init was used for device tests; the distributable APK retains original universal packaging. App data was backed up and retained during AppHear-only reinstall. Insufficient-storage and one failed manual install attempt are retained in local logs; no other apps were removed or device data wiped.

Read-only checks:
```powershell
python android/tools/verify-integrated-vocabulary.py
python android/tools/audit-imported-transition-padding.py
python android/tools/test-3dlex-export-reset.py
# Run the player harness from android/:
node tools/test-text-to-sign-resident.cjs
```

## Provenance, reproducibility and remaining work

Source: 3D-LEX v1.0 ASL Animation Data, https://osf.io/mqzyk/ . License record: https://www.sign-lang.uni-hamburg.de/lrec/data/3dlexv10.html . CC BY 4.0 attribution is bundled in 3DLEX_ATTRIBUTION.md. Only ASL motions are used; no NGT motion, source mesh or texture is imported. Rights to AppHear's older avatar/motions remain separately unresolved.

Official ASL_ANIM_GLB.zip SHA-256: `bac3e8ca0dbcc45eec0952a20dd04f28cc38131baddc8a354a72da673af0bdc7`.
Pinned reference converter SHA-256: `46f6b33f3b1ed76bd9de73618484e12932096c62350875c9e2d8a6d30f736384`. It is the prepare-web-asl-vocabulary.py source from Johnmichael030/APPHEAR at ff506e8039d0da912d153ad7de46ea2e45bd73cc. Its implementation is not packaged into the APK.
Final motion bundle SHA-256: `214bed7147ffa794be0a79de2a56cd74899d599a0207676d825063e2825c107c`; bytes: 94,824,008.
Dictionary manifest SHA-256: `a434fae72617738b98ba1b5f25ddbe0df6bb774afb645bfd07b7a15f34d31f58`.

Conversion tools stage candidates before touching runtime assets. `expand-3dlex-vocabulary.py` takes the official archive, pinned converter source and a staging output directory; `package-3dlex-expansion.py` accepts that reviewed staging directory. The baseline digest is deliberately pinned to the pre-expansion bundle; reproduce from the checkpoint rather than silently reapplying to a newer model. No downloaded dataset/cache/APK/private log is committed.

Next: obtain qualified ASL review of lexical senses, variants, handshape/contact and motion timing; repair rejected sources individually with evidence; add suitable new licensed ASL motions to address the remaining requested vocabulary. Source presence and valid rotations alone do not authorize a verified-ASL label.

## Files changed

- `android/app/src/androidTest/java/com/example/apphear/AslAllWordsHandAuditTest.kt`
- `android/app/src/androidTest/java/com/example/apphear/AslFingerspellingPlaybackInstrumentedTest.kt`
- `android/app/src/aslOriginalWords/assets/asl_animations/original_words_v1/3DLEX_ATTRIBUTION.md`
- `android/app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb`
- `android/app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.json`
- `android/app/src/aslOriginalWords/assets/asl_animations/original_words_v1/integration-manifest.json`
- `android/app/src/aslPilot/assets/pilot_player.js`
- `android/app/src/main/java/com/example/apphear/domain/texttoasl/AslAnimationAsset.kt`
- `android/app/src/main/java/com/example/apphear/domain/texttoasl/AslFingerspellingBundle.kt`
- `android/app/src/main/java/com/example/apphear/domain/texttoasl/AslIntegratedVocabulary.kt`
- `android/app/src/main/java/com/example/apphear/ui/texttoasl/TextToAslFragment.kt`
- `android/app/src/main/java/com/example/apphear/ui/texttoasl/TextToAslPlaybackController.kt`
- `android/app/src/test/java/com/example/apphear/AslVersionIntegrationTest.kt`
- `android/tools/3dlex-expansion-audit.csv`
- `android/tools/TextToSignTransitionsAnd3dLexExpansion.md`
- `android/tools/audit-imported-transition-padding.py`
- `android/tools/build-integrated-preview.ps1`
- `android/tools/expand-3dlex-vocabulary.py`
- `android/tools/integrated-vocabulary-inventory.csv`
- `android/tools/package-3dlex-expansion.py`
- `android/tools/test-3dlex-export-reset.py`
- `android/tools/test-text-to-sign-resident.cjs`
- `android/tools/text-to-sign-test-memory.init.gradle`
- `android/tools/verify-integrated-vocabulary.py`

## Development review

Plan/scope: pass for the bounded transition repair and available-data expansion. System integrity: pass for original actions/alphabet/rig preservation and scoped changes. Engineering gates: pass (unit/player/data/Android tests and package integrity). Important remaining items: the 400-addition target is not met; no qualified linguistic validation; source clips retain their own preparation/retraction; all-711 anatomical/contact review is incomplete. Recommendation: engineering preview for review, not a linguistically validated production release.

Protected: Sign-to-Text, camera/MediaPipe, recognition models, navigation, login/database, app resources/layout/theme, other checkouts and prior public APKs. Checkpoint: `checkpoint/before-transition-repair-20261024` (695e24f38fef686e65cdb062e4859ac214dc4289). Development branch: `integration/text-to-sign-three-sources-20261023`. No main/remote branch changes or GitHub push.
