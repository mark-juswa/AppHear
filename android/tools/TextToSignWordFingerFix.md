# Native word finger-axis repair

## Finding and scope

The selected human's LOVE asset rotates the index, middle, ring and pinky joints backwards relative to its bind-pose flexion axes. Actual skinned-mesh inspection shows opening/hyperextension where inward curling is needed. The quaternions themselves are finite and normalized. This is an animation-data fault; the inspected native clips use the same rig as the resident avatar, without native-word retargeting. No Euler/quaternion conversion bug or concurrent idle conflict was demonstrated. Bind matrix identity error is approximately 7.2e-7 and weight-sum error 1.2e-7; these checks do not certify artistic skin weights or handshape accuracy.

LOVE's intended crossed arms are supported by [ASLU's LOVE reference](https://www.lifeprint.com/asl101/pages-signs/l/love.htm). The same reverse flexion appears in the supporting left hands of HUSBAND and WIFE. Their cupped/clasping variants are described by [HUSBAND](https://www.lifeprint.com/asl101/pages-signs/h/husband.htm), [WIFE](https://www.lifeprint.com/asl101/pages-signs/w/wife.htm) and [MARRIAGE](https://www.lifeprint.com/asl101/pages-signs/m/marriage.htm). References establish intended forms, not validation of these animations. No reference video was packaged or redistributed.

## Correction

An explicit profile list selects 24 LOVE finger rotation tracks and 12 each for HUSBAND and WIFE: joints 1–3 of Index/Middle/Ring/Pinky on the specified hands. For each selected quaternion, compute its bind-relative delta, reflect negative local-X flexion to inward flexion, preserve the other delta components, then normalize and restore bind orientation. Use shortest-path quaternion interpolation. A 180ms smooth entry/release envelope retains source neutral endpoints and the previous LOVE arm-clearance repair. This envelope changes curve values, not queue timing or completion handling.

Thumbs have different axes and remain unchanged; the tested thumb-reflection prototype was rejected. No global joint clamp, IK change, skeleton edit, weight edit, generic hand pose, or runtime collision avoidance was introduced. Original binary data remains intact as a prefix; corrected tracks are appended. Arm/wrist curves, targets, sign lengths, timestamps, source meshes, and all other actions are retained. Original per-word GLBs remain available.

The common profile-based tool repairs this demonstrated fault across three words. Other warnings require sign-specific inspection and references before adding a profile. Applying reflection indiscriminately could damage legitimate ASL forms.

## Exact files

All paths below are relative to this Android project:

- `app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb`: corrected 48 selected tracks.
- `app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.json`: digest and unreviewed correction provenance.
- `app/src/main/java/com/example/apphear/domain/texttoasl/AslFingerspellingBundle.kt`: integrity digest matching the repaired asset.
- `app/src/test/java/com/example/apphear/AslLoveContactTest.kt`: permits exactly the inspected LOVE arm/finger channels, retains contact checks.
- `app/src/test/java/com/example/apphear/AslFingerspellingFallbackTest.kt`: retains native-action identity checks except the three separately tested corrections.
- `app/src/test/java/com/example/apphear/AslWordFingerRepairTest.kt`: verifies repair scope, quaternion math, source times, endpoints and unchanged thumbs.
- `tools/native-word-hand-profiles.json`: allow-list, rationale and reference provenance.
- `tools/correct-text-to-sign-word-fingers.py`: reproducible offline asset correction, source checksum guard and idempotence.
- `tools/audit-text-to-sign-word-fingers.py`: independent mesh audit, remaining warning list and matched-camera hand images.
- `tools/TextToSignWordFingerFix.md`: this record and review procedure.

No viewer JavaScript, screen layout, navigation, Sign-to-Text, recognition model, MediaPipe, database, dependency or shared application behavior was edited. The existing relaxed alphabet posture and one-avatar queue remain intact.

## Actual verification

- Android `testDebugUnitTest`, `assembleDebug`, `assembleDebugAndroidTest`: BUILD SUCCESSFUL; 237 unit tests, zero failures/errors/skips. Instrumentation APK assembled, not executed.
- Existing player and resident-avatar Node tests passed, including completion, cancellation, mixed/repeated input and one resident avatar.
- All 203 native word clips checked for finite animation data and unit quaternions.
- 227 actions unchanged: 200 other native words, all 26 alphabet clips and neutral pose. This is data preservation, not a new visual validation of every sign or J/Z.
- LOVE: 347 sampled poses. Arm/shoulder/wrist matrix change exactly zero. Torso-front proxy maximum hand penetration 0mm; maximum forearm depth 1.77mm. A proxy/sample test does not establish continuous, full-mesh collision freedom.
- HUSBAND/WIFE: 41 sampled poses each; arm/wrist matrix change zero. Matched-time front/side mesh images inspect both hands. Right hands unchanged.
- Mesh maximum edge-stretch ratio improved in the repaired hands, but residual deformation remains. LOVE right-hand 99th-percentile stretch slightly increased (1.521 to 1.562); do not call all skin metrics improved. Thumb/contact, low-poly skinning and handshape details still need review.
- 15 other word actions / 18 hands flagged by the reverse-PIP warning signature. A warning is not proof that their intended handshape is incorrect; they were left unchanged.
- Pixel_3a emulator launch failed: x86 hardware acceleration unavailable, Windows Hypervisor Platform not enabled/usable. No Android GPU screenshot, physical-phone test, or instrumented runtime result is claimed.
- Qualified ASL linguistic validations for these repairs: **zero**. Dictionary status remains unreviewed.

## Reproduce and extend

Preserve a pre-repair GLB before running the correction. From this Android directory, with Python/NumPy/Pillow available:

```powershell
python tools/correct-text-to-sign-word-fingers.py
python tools/audit-text-to-sign-word-fingers.py <pre-repair-glb> app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb <review-output-directory>
node tools/test-text-to-sign-player.cjs
node tools/test-text-to-sign-resident.cjs
```

The correction's source checksum intentionally prevents applying it to an unrelated asset. In this workspace, the preserved pre-repair file is `work/word-finger-before.glb` relative to the workspace root. The exported build helper is `outputs/Build-AppHear-Word-Finger-Fix.ps1`; run it from a normal PowerShell/Android Studio terminal. Its default fake service configuration is unchanged; private account/voice/Gemini service credentials are not added by this repair.

Before extending profiles: compare actual mesh from multiple views against the intended variant; examine the bind-local axis; test thumbs separately; preserve sign-specific orientation/contact; verify neutral endpoints, torso clearance and untouched channels; update the checksum; run the audit and Android tests. Seek qualified ASL review of handshape, thumb placement, orientation, contact, timing and meaning. Do not upgrade entries to linguistically validated based on mechanical tests.

For device review, install the APK using the same debug signing key, then test LOVE, HUSBAND, WIFE; unchanged HELLO, BEAUTIFUL, HELP, THANK YOU; all A–Z; NAME/NICOLE/ANNA/JAZZ; HELLO NICOLE and I LOVE YOU. Confirm shoulders, repeated letters, J/Z movement, cancellation and neutral return. NAME remains fingerspelling where no compatible lexical asset exists. Record actual observations instead of claiming these device tests were performed here.
