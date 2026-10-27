# Three-source Text-to-Sign integration — 23 October 2026

Engineering preview on `integration/text-to-sign-three-sources-20261023`. No GitHub push.

## Sources and actual union

| Source | Pinned identity | Lexical entries |
|---|---|---:|
| Primary architecture: mark-juswa/AppHear, claude/fingerspell-practical-integration | 1f9e571a8571e78eb06995d6d7f1f2990027608a | 232 |
| Latest verified working: AppHear-Update-6 | 378213fbd5c948d254cbeb43e344c251138fd91d | 258 |
| Johnmichael030/APPHEAR, main | ff506e8039d0da912d153ad7de46ea2e45bd73cc | 647 |
| Integrated union | 404 external additions to the 258-entry working union | **662** |

There are 661 distinct active lexical actions (NAME reuses CALL-SOMEONE'S-NAME),
26 alphabet actions and one neutral action. 52 inactive alternatives are also
retained: 36 prior-primary actions and 16 overlapping external actions. Total
packaged actions: 740. Neither inactive alternatives, letters, aliases nor arbitrary
fingerspelling inflate the 662-entry count. There are 794 explicit English forms.
The union adds 430 entries relative to the primary branch: 26 from the working
version, then 404 genuinely new external entries. Zero qualified ASL validations.

Working entries absent from the external 647 catalog, all retained:
bread, church, coffee, communicate, explain, fine, hotel, library, milk, nice, orange, pain, sign, together, with.

## Selective architecture and source choices

The new checkout is based on the primary branch; no whole-application merge was
performed. Its TextToAslFragment, TextToAslPlaybackController, resident JavaScript
player, screen layout, application resources, navigation, recognition and models
are unchanged. This retains the primary branch's renderer-crash recovery and its
matching lifecycle/conversation code. Existing experimental flags retain their
defaults; recognition features were not enabled or rewritten to deliver vocabulary.

The working version's first 284 referenced actions, including A–Z and relaxed
neutral, remain exact. Compatible external rotation actions were appended; the
external avatar mesh was not copied. All 420 external added/replacement actions
are preserved exactly. 404 are new active entries. Eleven overlap newer working
entries; five are replacement candidates. These sixteen remain inactive alternatives.
Both variants are available for future controlled review without silently overwriting
the current working motion. The 36 differing primary actions are also retained as
REVIEW_PRIMARY__ actions. Git history and all old APKs are preserved.

196 shared entries were identical in the prior comparison. For the 36 differing
entries, the latest working repair/retiming is retained as a baseline, not declared
a universal winner. FINISH/SCHOOL/DIVORCE have measured prior improvements; LOVE,
ME/I and other previously flagged signs remain subject to correction and ASL review.
Every active source choice is in integrated-vocabulary-inventory.csv.

Priority mapping choices:

| Entry | Active selection / limitation |
|---|---|
| LOVE | Working SIGN_LOVE; primary rollback retained. This integration does not fix its remaining wrist/handshape concerns. |
| YOU | Existing working pointing preview; external replacement retained inactive. |
| YOUR/YOURS | Existing working flat-palm preview preserved, as requested. |
| ME/I | Working pointing path retained; prior wrist-bend concern remains. |
| MY | Existing primary/working motion retained. |
| NAME | Existing CALL-SOMEONE'S-NAME noun/verb-form preview reuse, not a newly validated standalone sign. |
| WHAT | Existing motion and meaning limitations retained. |
| WHY | Existing preview retained; both old wrist concern and external torso-screen flag require review. |
| WHERE | Existing preview retained; external candidate preserved. |
| TODAY | Existing preview retained; external candidate has better axial screening but needs full variant review before substitution. |
| HELP, HELLO | Existing working motions retained. |

The five external candidates were compared across 31 skinned source poses each,
with actual bone-space wrist/axial and torso-depth screens. CPU hand views were
inspected; these are not Android replacement-acceptance results. Both sources have
limitations: the external WHY screen reaches about 27.6 mm projected hand/torso
depth; TODAY's external axial screen improves about 230 to 99 degrees. These
screens do not establish correct signing, and a smaller bend is not a linguistic
decision. The current candidate policies intentionally avoid automatic substitutions.

## Compatibility, integrity and licensing

Skeleton/node hierarchy, bind/skin, mesh declarations, geometry bytes, materials,
textures and scenes match. Imported tracks therefore retain their original local
bone targets; no Euler reinterpretation, global finger clamp, runtime retargeting,
new IK, alternate avatar or new animation controller was introduced. The portable
append-compatible-asl-motions.py reproduces the combined GLB hash independently.

External LFS payloads were retrieved as binaries, not pointer files, and verified:

- 647 bundle: 79,906,716 bytes, SHA256 7840f979713d878f273a71975c38e1d12dbf3856151af531cbed8daf70fd0024.
- Earlier web bundle: 54,902,340 bytes, SHA256 6b4dbc4fce99ff6d396e3bc8bf2c792adef4f1fe1deb7bfa709306096084e9cb.
- Five fixes: 55,421,552 bytes, SHA256 244ba8daf6371124dac2da6a985fff0dfaead8ee92e672fcfe93ebf5d5e24616.
- Combined: 87,606,644 bytes, SHA256 7975abceb4c75e09cab995600d6b852edbd608a44e4e4a07550746544f7e7aec.

All three provided verification scripts pass on the isolated original source
packages. The integrated verifier separately checks 662 mappings, 794 forms,
740 actions, all clocks/quaternions, source hashes, exact old-action preservation,
and exact copied external motion values. 3,479,153 quaternion keys were checked.

Imported motion: Ranum, Otterspeer, Andersen, Belleman and Roelofsen, 3D-LEX v1.0
ASL Animation Data, CC BY 4.0. The official release index identifies this license:
https://www.sign-lang.uni-hamburg.de/lrec/data/3dlexv10.html
Source: https://osf.io/mqzyk/ ; paper: https://aclanthology.org/2024.signlang-1.33/
Terms: https://creativecommons.org/licenses/by/4.0/
The packaged 3DLEX_ATTRIBUTION.md retains creator credits, links, earlier adaptation
notes and this append-only modification record. Source identities for all 420
imported actions are in three-source-external-motions.json. No source dataset
archive, source mesh or texture was imported. Existing avatar/motion provenance
remains separately unresolved; the new motion license does not clear older rights.

## Actual tests and limits

- JVM: **366 tests passed**, zero failures/errors/skips, including the union and all
  794 declared input-form mappings. Existing unrelated regression tests also ran.
- Controller harness: **794 requests passed**, exercising every packaged action,
  completion guards, repeat/letter sequences, one resident model, cancellation,
  missing-action rejection and neutral return. This uses deterministic viewer events.
- Android universal app and Android test APK build: passed using existing Gradle,
  JDK17 and SDK36. Emulator ABI packaging passed. No dependency/SDK upgrades.
- Existing Medium Phone API36 emulator: app data was backed up (165 files,
  17,381,376 bytes) before the previously approved AppHear-only keep-data reinstall.
  Both APKs installed. Existing exported SplashActivity launched; MainActivity is
  intentionally not exported and was launched from inside instrumentation.
- Real native pose audit: **20 words passed** in 66.04 seconds; ten rendered phases
  each were captured and inspected: adult, age, alcohol, and, apple, basement, bedroom, church, coffee, hospital, hotel, i_me, library, love, name, today, where, why, you, your_yours.
  Six of these are newly imported lexical entries; the other fourteen are preserved
  words. Full-body views reveal coarse positions but do not prove fine finger contact.
- Normal native input: **91 inputs passed** in 371.501 seconds, with exact
  native-to-player action lists checked against the real planner. 26
  alphabet action names were observed across the requests, including J/Z and repeated
  letters. NICOLE/NAME/ANNA/JAZZ/ACTION, mixed word/spelling input and rapid cancellation
  were exercised. Same WebView identity was asserted throughout.
- One live host-process memory sample: PSS 241,874 KB; RSS 371,212 KB. This excludes
  separate WebView renderer accounting and is not peak memory or phone acceptance.
- Recorded AndroidRuntime error log was empty during the successful test period.
  No physical phone, all-662 rendered motion audit, p50/p95 loading/FPS benchmark,
  live camera recognition or qualified Deaf/ASL evaluation was performed.

Initial development failures remain in local logs: an incorrect AIRPORT audit ID
(AIRPORT is absent and still spells), stale test UI wording after the primary
branch removed preview text, test observer null handling, UTF-8 test fixture text,
a test Java API mismatch, and a missing visual-test helper. Final tests use actual
actions rather than reintroducing UI notices. No production controller change was
made to satisfy the tests. The final successful logs are the evidence above.

All 662 entries have mapped existing lexical actions; **this does not mean all are
anatomically correct or linguistically validated**. Every uninspected entry is
explicitly marked in the CSV. Automatic spelling remains for names and missing
words (e.g. NICOLE, ANNA, AIRPORT and QZXUNKNOWN where no phrase matches). Context
name prefixes still force spelling instead of substituting a coincidentally named
lexical word. There are still no validated complete ASL sentence translations or
validated non-manual grammatical markers. Existing English preview behavior stays.

## Build and recovery

Open the integration checkout's android folder in Android Studio. Keep JDK17 and
the existing SDK provisioned. The portable command is:

```powershell
& .\android\tools\build-integrated-preview.ps1 -Configuration fake
python .\android\tools\verify-integrated-vocabulary.py
Push-Location .\android
node .\tools\test-text-to-sign-resident.cjs
Pop-Location
```

The build wrapper uses the same fake debug service configuration as the verified
working preview. Account/Gemini/voice services require the owner's existing private
configuration and were not live-tested. -Configuration private uses that existing
configuration; never commit its keys. Other primary experimental flags retain their
defaults, not blanket activation. Release defaults remain unchanged.

Actual build tasks: testDebugUnitTest assembleDebug assembleDebugAndroidTest,
--max-workers=2, -Dorg.gradle.jvmargs=-Xmx2048m,
-Pkotlin.compiler.execution.strategy=in-process, with the existing local ONNX
dependency and test-JIT init scripts. Emulator-only packaging used the existing
x86_64 ABI init script. These machine-local helpers are not checked in.

Recovery checkpoint: checkpoint/before-three-source-integration-20261023 preserves
the prior tracked draft; the five prior untracked files also have a verified local
ZIP checkpoint. The original feature/s2-r3-text-to-sign-vocabulary checkout and
AppHear-Improved/AppHear-source were not overwritten. No Windows files or older APKs
were deleted. No main branch, production credentials, models, recognition logic,
camera, navigation, login code, database or unrelated UI was changed. No GitHub push.

## Delivery

APK: AppHear-Update-7.apk in the user's existing outputs directory.
Package com.example.apphear, versionName 1.0 / versionCode 1, debug v2 signature verified.
APK bytes: 878828035; SHA256 8c8322e1bb8d2ab723cd1747d5ce599359d7e58674bad1dc1444fd5db5001f28.
The emulator APK contains the same shared code/assets, with only native ABI packaging
differences from the universal build. Exact modified files are listed below.

## Exact created/modified files (relative to the integration checkout)

- `android/app/src/androidTest/java/com/example/apphear/AslAllWordsHandAuditTest.kt`
- `android/app/src/androidTest/java/com/example/apphear/AslFingerspellingPlaybackInstrumentedTest.kt`
- `android/app/src/androidTest/java/com/example/apphear/AslVisualTestGuard.kt`
- `android/app/src/aslOriginalWords/assets/asl_animations/original_words_v1/3DLEX_ATTRIBUTION.md`
- `android/app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb`
- `android/app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.json`
- `android/app/src/aslOriginalWords/assets/asl_animations/original_words_v1/integration-manifest.json`
- `android/app/src/main/assets/asl_animations/existing_aliases_asl.json`
- `android/app/src/main/java/com/example/apphear/domain/texttoasl/AslAdverbPolicy.kt`
- `android/app/src/main/java/com/example/apphear/domain/texttoasl/AslFingerspellingBundle.kt`
- `android/app/src/main/java/com/example/apphear/domain/texttoasl/AslInputAnalysis.kt`
- `android/app/src/main/java/com/example/apphear/domain/texttoasl/AslIntegratedVocabulary.kt`
- `android/app/src/main/java/com/example/apphear/domain/texttoasl/AslLexicalContext.kt`
- `android/app/src/main/java/com/example/apphear/domain/texttoasl/AslPhrasePlanner.kt`
- `android/app/src/main/java/com/example/apphear/domain/texttoasl/AslTextNormalizer.kt`
- `android/app/src/main/java/com/example/apphear/domain/texttoasl/AslTranslationPlanner.kt`
- `android/app/src/main/java/com/example/apphear/domain/texttoasl/EverydayAslExpression.kt`
- `android/app/src/main/java/com/example/apphear/ui/texttoasl/AndroidAssetAslCatalogLoader.kt`
- `android/app/src/main/java/com/example/apphear/ui/texttoasl/AslIntegratedVocabularyLoader.kt`
- `android/app/src/test/java/com/example/apphear/AslConversationCorpusTest.kt`
- `android/app/src/test/java/com/example/apphear/AslFingerspellingFallbackTest.kt`
- `android/app/src/test/java/com/example/apphear/AslFlatBaseHandCorrectionTest.kt`
- `android/app/src/test/java/com/example/apphear/AslFourSignPlacementTest.kt`
- `android/app/src/test/java/com/example/apphear/AslGrammarPlannerTest.kt`
- `android/app/src/test/java/com/example/apphear/AslPointingCorrectionTest.kt`
- `android/app/src/test/java/com/example/apphear/AslThreeWristRepairTest.kt`
- `android/app/src/test/java/com/example/apphear/AslVersionIntegrationTest.kt`
- `android/app/src/test/java/com/example/apphear/AslVocabularyExpansionTest.kt`
- `android/app/src/test/java/com/example/apphear/AslWordFingerRepairTest.kt`
- `android/app/src/test/java/com/example/apphear/AslWristRollCorrectionTest.kt`
- `android/app/src/test/resources/texttoasl/conversation-mechanical-gates.json`
- `android/app/src/test/resources/texttoasl/four-placement-gates.json`
- `android/app/src/test/resources/texttoasl/hand-twist-baseline.json`
- `android/app/src/test/resources/texttoasl/three-wrist-gates.json`
- `android/tools/ThreeSourceIntegration.md`
- `android/tools/adverb-preview-cases.json`
- `android/tools/append-compatible-asl-motions.py`
- `android/tools/build-integrated-preview.ps1`
- `android/tools/conversation-100-asl.json`
- `android/tools/integrated-vocabulary-inventory.csv`
- `android/tools/test-text-to-sign-resident.cjs`
- `android/tools/three-source-external-motions.json`
- `android/tools/verify-integrated-vocabulary.py`
