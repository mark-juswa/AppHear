# AppHear Update 12 — existing avatar vocabulary update

Partial milestone: 785 catalog entries, 917 English input forms, 863 animation actions. One new lexical animation preview: ARRIVE. 215 entries remain before the 1,000-entry target. Aliases and fingerspelling are not new lexical signs. No new avatar/model was added.

## Implemented correction
ARRIVE uses the licensed 3D-LEX source timing/body motion with the existing avatar's B finger pose. The opposite hand is transferred through anatomical rest frames, not Euler sign flips. Original thumbs are retained. A sign-specific contact correction uses bounded arm IK; maximum wrist adjustment is 38.46 mm. No global finger limits or generic collision avoidance was introduced. All previous 862 actions and the human mesh/rig remain preserved; the fingerspelling controller is unchanged.

Reference: https://www.lifeprint.com/asl101/pages-signs/a/arrive.htm
Motion source: https://osf.io/mqzyk/ ; CC BY 4.0 data license record: https://www.sign-lang.uni-hamburg.de/lrec/data/3dlexv10.html . Qualified ASL validation has NOT occurred. Facial grammatical features are not provided by this asset.

## Actual verification
- 374 JVM tests: zero failures, errors or skips; 74 current XML outputs.
- Android debug APK and instrumentation APK build succeeded (8m53s).
- ARRIVE: 61 sampled CPU-skinned poses screened; 347 poses at 120 Hz checked for transverse hand-mesh crossings deeper than 1 mm: zero. Tangential contact is permitted. This does not prove absence of every possible collision.
- CPU-rendered hand geometry inspected. These are not Android screenshots or linguistic validation.
- Portable staging tool reproduced the corrected motion data. Protected source channels and all previous actions are pinned by tests.
- APK signature verified with the existing debug certificate.
- Compared with Update 11: 1,665 non-code APK entries unchanged; only four Text-to-Sign asset entries changed. Android manifest/resources unchanged. This is not a substitute for full application regression testing.
- Existing Medium Phone API 36 booted. APK installation failed. Android package manager explicitly reports: 'Requested internal only, but not enough space' (988 MB available). No applications/files removed, no wipe, no phone installation. New Android rendering, completion and device performance remain NOT TESTED.

## Rejected experiments, not enabled
PROOF, DIVIDE, BLOOD and ESCAPE exceeded the bounded contact displacement. BELIEVE retained body/hand intersections; EXPRESS retained hand intersection. GAME, CONFLICT, STAR, CANNOT and DISCUSS remain unresolved contact/retargeting candidates. These experiments were not copied into the app or counted as added words. Other remaining candidates are individually listed in remaining-target-words.csv/json; they were not all visually tested. Static combined exports and raw-capture-only entries still need usable, synchronized motions.

## Files changed in this batch
Text-to-Sign asset directory android/app/src/aslOriginalWords/assets/asl_animations/original_words_v1/: fingerspelling-avatar.glb, fingerspelling-avatar.json, integration-manifest.json, 3DLEX_ATTRIBUTION.md.
Runtime count/hash pins: AslFingerspellingBundle.kt, AslIntegratedVocabulary.kt under android/app/src/main/java/com/example/apphear/domain/texttoasl/.
Tests: AslFbxVocabularyExpansionTest.kt, AslVersionIntegrationTest.kt, new AslContactVocabularyExpansionTest.kt; resources/texttoasl/fbx-expansion-gates.json and new contact-vocabulary-gates.json.
Tool/documentation: android/tools/stage-arrive-contact-vocabulary.py; android/tools/ContactVocabularyExpansion.md.
Earlier uncommitted work is preserved; this list describes this batch, not the entire dirty working tree. Checkpoint tag: checkpoint/before-raw-vocabulary-recovery-20261026 at 9d6b8565567ba637b22887b307a9e183e7f27894; untracked checkpoint backup remains in ignored staging.

## Scope and limitations
No Sign-to-Text, camera, recognition model, navigation, layout, login, database, idle or fingerspelling-controller changes in this batch. No GitHub push, clone, new character, file cleanup, model replacement or prior APK deletion. Catalog previews are not linguistically verified ASL. Manual review by qualified ASL signers is required before claiming comprehensibility or accuracy. New motions beyond ARRIVE are not delivered in this APK.

## Build command
From the existing integration working tree, with the existing Java 17/SDK configuration:

    .\android\tools\build-integrated-preview.ps1 -Configuration private -Tasks @('testDebugUnitTest','assembleDebug','assembleDebugAndroidTest','--offline','-Pkotlin.compiler.execution.strategy=out-of-process','--init-script','C:\Users\nicole\Documents\Codex\2026-10-09\project-apphear-clone-and-redesign-the\work\verified-onnx.init.gradle')

APK: AppHear-Update-12.apk in the existing outputs directory. SHA256: c7578803e6b3cb9f17c801cb15b299f00826d3833c8d78514673e1ccfcde0228. Previous builds retained.
