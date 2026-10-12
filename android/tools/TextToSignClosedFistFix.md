# ME and LOVE closed-hand preview correction — 12 October 2026

This correction is limited to Text-to-Sign. It is not qualified ASL validation.

## Latest LOVE follow-up: wrists, fist closure and crossed-arm placement

Checkpoint before this follow-up: `checkpoint/love-wrist-review-20261012`, commit `635cd57`. The preceding finger-only repair below is historical; its statement that wrists/arms are unchanged does not describe this follow-up.

The actual held LOVE pose had bind-relative wrist rotations of approximately 144° left and 160° right. Earlier torso-clearance IK retained the source world-hand orientation. Closing fingers alone therefore retained a twisted-looking wrist. The YES donor's index remained incompletely curled. An actual Android close-up confirmed this; playback completion was not sufficient evidence of a good handshape.

The follow-up changes only `SIGN_LOVE`: six arm/forearm/hand rotation tracks and 24 index/middle/ring/pinky joint tracks. Both wrists are straightened in the held pose, with axial roll assigned to the forearm, and the arms cross diagonally with fists at the opposite upper chest, guided by the supplied reference and ASLU's LOVE demonstration. Finger flexion uses each actual anatomical segment and palm normal, rather than a generic local-X clamp. The existing thumb tracks remain. This is authored, unvalidated preview data; the numerical joint angles are implementation choices, not an ASL standard.

The existing first/last 0.3 seconds of finger articulation are preserved, with 0.25-second transition envelopes in the signing area. A separately measured brief release-hand penetration already existed in the pinned baseline. LOVE-only two-bone IK reroutes the affected right-hand release forward by at most 22.3 mm, preserving its world orientation and bone lengths. No runtime collision system or global restriction was introduced.

Offline verification sampled 641 actual skinned poses: maximum front-torso hand penetration 0 mm and forearm penetration 1.892 mm. These are measurements against a front-surface proxy, not proof of all-mesh or arm-arm collision clearance. The low-poly mesh remains angular, and qualified ASL review is still required. All 231 other named actions, including YES, ME, HELP and all 26 alphabet clips, are byte-identical to the checkpoint. Hierarchy, bind matrices, skin weights, mesh, materials, textures and animation endpoints remain unchanged.

Bundle SHA256: `c04f873aa44d7c31fdf688d423d18100843535067acab0223418ea9340fa34b5`.

Files changed in this follow-up:

- `app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb`: only the 30 LOVE rotation channels described above.
- Adjacent `fingerspelling-avatar.json`: checksum and separate `loveWristFistCorrection` audit. Older repair metadata remains explicitly historical.
- `app/src/main/java/com/example/apphear/domain/texttoasl/AslFingerspellingBundle.kt`: checksum only.
- `tools/correct-text-to-sign-love-wrists.py`: guarded candidate-only generator, exact scope/neutral endpoint checks, dense surface gate and skinned comparison. It never overwrites production assets.
- `app/src/test/java/com/example/apphear/AslLoveContactTest.kt`: checks the actually referenced final arm tracks rather than obsolete append-only samplers; checks repair scope, surface gate and unvalidated status.
- `app/src/androidTest/java/com/example/apphear/AslFingerspellingPlaybackInstrumentedTest.kt`: explicitly opens normal Text mode and asserts that the displayed input equals the submitted request, avoiding stale replay passes.
- This report.

To reproduce the candidate, recover the bundle from checkpoint `635cd57` as binary without changing the checkout, then run the generator with `--source <checkpoint.glb> --output <candidate.glb> --report <audit.json>`. NumPy and Pillow are development-only requirements already used by the existing tools. Inspect the actual candidate on Android before applying it. The integrity check deliberately rejects other input hashes.

The predecessor APK `183938864c8db39afce5e4c9c4a8bef6a96f1f5f5466293bd5870a57cb43ec0d` was successfully installed after the user approved an AppHear-only keep-data reinstall. Its corrected normal-input test passed all 21 requested inputs and cancellation/replacement on one viewer. The first harness run failed at NICOLE with `Ready`; explicitly opening Text mode resolved that harness issue. This predecessor result must not be presented as the final corrected APK's test result.

Final verification:

- `testDebugUnitTest`, `assembleDebug`, `assembleDebugAndroidTest`: successful; 244 JVM tests, no failures/errors/skips. The first run exposed a test-filter error that counted translation/scale alongside rotation channels; it was corrected, then all tests rerun. No animation changes were needed for that test failure.
- Signed APK: `app/build/outputs/apk/debug/app-debug.apk`, SHA256 `809a9f43b7330db6d9219cbc91f501fb2d416e87bbe5d1ac1634ac798e427aed`. Signature verified; packaged bundle checksum and emulator-installed APK checksum both match.
- Actual Medium Phone API 36 / Android 16 emulator: all 21 normal-input cases and NICOLE→ANNA cancellation/replacement passed on the final APK in 124.941 seconds. Inputs: NICOLE, NAME, YOU, ANNA, JAZZ, ACTION, HELLO NICOLE, ME, YES, LOVE, HELP, COOK, BECOME, MONEY, NEW, SOME, DAY, HELLO LOVE, MY NAME, YOUR NAME, I LOVE YOU. One existing WebView was retained throughout. This is technical playback verification, not ASL sentence validation.
- The first emulator session ended during the build. The same existing AVD was restarted without wiping or creating another device. AppHear was absent in the restarted persistent session; the final APK was installed without another removal. The previously saved AppHear-only data archive was restored using ADB binary input, and the onboarding preference hash was verified against the original backup. No other apps were removed.
- Actual installed-APK LOVE body and both-hand screenshots were inspected at 0.866667 seconds. Closed fingers and straighter crossed wrists are visible. A paused bone audit matches the final bundle to approximately 0.00000171° with no interfering scheduled animation. This capture used the APK's local asset, not an injected candidate. The viewer was restored afterward.
- No AndroidRuntime/Chromium exception appeared in the collected startup/test log window. This does not prove absence of every possible crash.
- All 26 alphabet clips are unchanged, with normal NICOLE/ANNA/JAZZ/ACTION and mixed-input playback passing. A new individual visual review of all A–Z letters was not performed in this follow-up. No physical-phone test or qualified ASL validation occurred. Full frame-by-frame linguistic review, thumb/mesh refinement and complete arm-arm collision validation remain outstanding.
- Main/home and existing Text/Talk input were exercised. Sign-to-Text camera/recognition, database, live accounts, Gemini and voice services were not runtime regression-tested. Their source and UI are unchanged. The build reused the existing public `fake` service configuration; live-service connectivity is not established by these tests.

Evidence remains in the existing `outputs/AppHear-Word-Finger-Fix-Review` folder: `love-wrist-fist-correction.json`, `love-corrected-apk-input-tests-20261012.json`, `closed-fist-runtime-installed-love-corrected.json`, `love-installed-pose-comparison.json`, and `closed-fist-SIGN_LOVE-{Body,Right,Left}-installed-love-corrected.png`. Earlier unsuccessful/neutral diagnostic captures are not final-pose evidence.

No UI, navigation, recognition, camera, model, database, shared settings, Gradle or dependency changes are part of this follow-up. No new vocabulary, avatar, clone, exported APK copy, or GitHub push was added.

The user reported YES as visually acceptable and ME/LOVE as distorted, then provided a LOVE reference showing closed fists crossed over the upper chest. Reference pages: [ME](https://www.lifeprint.com/asl101/pages-signs/m/me.htm), [LOVE](https://www.lifeprint.com/asl101/pages-signs/l/love.htm), [YES](https://www.lifeprint.com/asl101/pages-signs/y/yes.htm). No external media or motion data was packaged.

## Finding and repair

ME's original three folded fingers bend backward. LOVE's previous local-X sign correction kept source lateral articulation and incomplete closure; it did not provide a consistent fist. Thumb articulation also contributes to deformation. These are clip-specific rotation problems. The shared hierarchy, bind matrices and skin weight sums pass the existing structural checks; those checks do not prove good mesh deformation. No global joint limits or runtime hand masks were introduced.

The existing same-rig SIGN_YES articulation at 40% of its timeline supplies the folded finger/thumb pose. SIGN_YES itself is unchanged. LOVE uses this articulation for both hands, with left-hand rotations mirrored through actual bind frames. ME uses it only for thumb/middle/ring/pinky; its pointing index remains original. Original motion timestamps/endpoints are preserved, with a 180ms entry/release envelope. The wrist, arm, shoulder and body motion are untouched by this repair. The result remains an unreviewed preview, not a verified lexical translation.

Final scope: 30 LOVE and 12 ME rotation channels. All 230 other named actions, including all 26 alphabet actions, are unchanged. Mesh, hierarchy, weights, materials, textures and rest pose are unchanged. No vocabulary was added.

## Files

- `app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb`: scoped finger/thumb tracks.
- Adjacent `fingerspelling-avatar.json`: explicit profile version, donor/source hashes, references, unreviewed status.
- `app/src/main/java/com/example/apphear/domain/texttoasl/AslFingerspellingBundle.kt`: bundle integrity checksum only.
- `tools/correct-closed-fist-text-to-sign-hands.py`: reproducible offline donor/mirror correction, explicit accepted baselines, candidate mode and apply mode.
- `tools/verify-closed-fist-text-to-sign-hands.py`: exact scope/endpoints/body-matrix checks and actual skinned before/after renders.
- `app/src/test/java/com/example/apphear/AslClosedFistCorrectionTest.kt`: exact affected-node sets and preserved YES/ME index/rig/timing.
- `AslFingerspellingFallbackTest.kt`: adds SIGN_I to the explicitly scope-tested repair list.
- `AslWordFingerRepairTest.kt`: checks retained HUSBAND/WIFE reflection separately from the replacement LOVE method.
- `AslLoveContactTest.kt`: includes explicitly corrected LOVE thumbs in the scope boundary; existing arm/contact tests remain.
- `app/src/androidTest/java/com/example/apphear/AslFingerspellingPlaybackInstrumentedTest.kt`: includes standalone ME and YES in normal-input regressions.
- This document.

Checkpoint: `checkpoint/closed-fists-20261012` / commit `3ffa7ca`, on the existing local development branch. No push. No UI, navigation, recognition, model, camera, database, shared settings, Gradle or dependency edits.

## Evidence and limitations

Final bundle SHA256: `907944cee4c3ea684d4eddc8b734db75a1c21e06e04d3092f9fbdab7cbdd7fd1`.

The verifier samples 61 poses per changed action and finds zero wrist/arm matrix change. Actual Android WebView diagnostic sampling of the exact corrected bundle at ME 0.920s, LOVE 0.867s and YES 0.760s reaches the intended finger rotations within 0.000003 degrees, with action weight 1 and no interfering actions. This is component rendering evidence, not an installed-APK or complete sequence test.

The emulator rejected APK replacement with `INSTALL_FAILED_INSUFFICIENT_STORAGE`. It still has the previous installed APK. The corrected bundle was supplied temporarily to its debug WebView as a Blob, then the original viewer source/camera were restored. A separate capture made while normal input interfered failed the rotation comparison and is explicitly not accepted as final evidence. Only `closed-fist-runtime-confirmed.json` and matching `*-confirmed.png` captures are accepted for the final bundle.

Review outputs remain in the existing `outputs/AppHear-Word-Finger-Fix-Review` folder: `closed-fist-verification.json`, `closed-fist-android-pose-comparison.json`, actual close-ups and LOVE upper-body capture. The hand mesh remains visibly angular. LOVE still needs a complete motion/contact/wrist/handshape review against the user's reference and a qualified signer; partial pose alignment and smooth playback do not prove correctness. No final-version installed-APK emulator pass or physical-device test is claimed.

Final build: `testDebugUnitTest`, `assembleDebug`, `assembleDebugAndroidTest` passed, 243 JVM tests with zero failures. APK v2 signature verifies. APK SHA256: `183938864c8db39afce5e4c9c4a8bef6a96f1f5f5466293bd5870a57cb43ec0d`. The existing resident-player mock passes 278 requests and completion/cancellation checks. Of 1556 packaged assets/resources/native-library/manifest entries compared by CRC and size with the previous tested APK, only the human avatar bundle and its adjacent metadata differ; this inventory is not a cryptographic proof or a full unrelated-feature device test.

The historical normal-input test belongs to the previous installed APK; do not attribute it to this correction. Newly built test cases for ME/YES cannot run against the final APK until storage permits an update. The attempted run against the old installed app was stopped deliberately, and its resulting process-stopped message is not a crash result for the new APK. Automated checks are not signing accuracy results. Keep previous exported builds until the new APK has passed a real installation/interaction review.

The final build is `app/build/outputs/apk/debug/app-debug.apk` under this Android project. No extra exported APK copy was made and no old version was deleted while the final installation remains unverified. Older repair-stage tools assert their own earlier preservation boundaries; use the current closed-fist verifier against the new checkpoint for this stage rather than interpreting a historical all-other-actions assertion as valid after additional deliberate repairs.

To repeat the offline scope verification, extract the checkpoint's original bundle into a developer temporary file and pass original/current/output paths to `verify-closed-fist-text-to-sign-hands.py`. The correction tool accepts either the original checkpoint hash or the intermediate finger-only hash and rejects unknown baselines. It is a no-op when profile version 2 is already present. Use the existing `tools/android/build_working_baseline.ps1 -Configuration fake -OriginalWords` build configuration; no private service credentials are introduced.
