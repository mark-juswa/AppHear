# ME and LOVE closed-hand preview correction — 12 October 2026

This correction is limited to Text-to-Sign. It is not qualified ASL validation.

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
