# ME/I and YOU pointing preview correction — 12 October 2026

Only Text-to-Sign is changed. Checkpoint: `checkpoint/me-you-review-20261012`, commit `b2c3163`. No new clone, avatar, vocabulary or dependency. This is an authored, technically tested preview, not qualified ASL validation.

## Observed problems

The actual dictionary uses `SIGN_I` for ME/I and `SIGN_YOU_HUMAN_RETARGETED_PREVIEW` for singular YOU. A diagnostic first requested the nonexistent name `SIGN_YOU`; that failed capture was discarded and the real dictionary name was used.

The installed predecessor's rendered ME points upward and ends in front of the chest. At 40% of its clip, the index direction is approximately `[0.745, 0.480, -0.463]`, and its tip is at `[-0.023, 1.378, 0.229]` meters. The earlier closed-fist repair deliberately retained this original index/arm data, so it did not fix the pointing target.

The YOU clip points diagonally across the avatar: approximately `[0.792, 0.105, 0.601]`, rather than along its forward axis. Its source/rest posture also places the unused left hand far out at its side. Exact bone-frame retargeting alone did not establish correct sign meaning or posture. These are clip-specific pose/target problems; no evidence requires replacing the shared hierarchy or skinning engine.

References: [ASLU ME/I](https://www.lifeprint.com/asl101/pages-signs/m/me.htm), [ASLU YOU](https://www.lifeprint.com/asl101/pages-signs/y/you.htm). The user's photographs are visual guides; the second appears AI-generated and is not linguistic validation. Neither image nor external motion data is bundled.

## Repair

- Both clips fully extend the index using its existing bind articulation. Middle/ring/pinky curl about their actual segment/palm-normal axes (80/95/50 degrees). Thumb articulation reuses the same rig's existing YES preview. These numerical angles are implementation choices, not ASL standards.
- ME points toward the center chest. Its fingertip target is computed against the avatar's real front torso surface with a 20mm bone-tip offset. The tested tip reaches approximately `[-0.010, 1.300, 0.175]` meters. This establishes pointing direction; it does not prove exact skin contact or linguistic validity.
- YOU points along the avatar's forward axis toward the person in front. Its wrist target is `[-0.12, 1.25, 0.38]` meters. The unused left shoulder/arm/forearm/hand use the existing relaxed-neutral articulation.
- Two-bone IK preserves arm lengths. Axial rotation is assigned to the forearm to reduce concentrated wrist twist, while retaining the intended world-hand direction. 350ms entry/release envelopes return ME to its source neutral and YOU to the same human's existing relaxed neutral. No global clamps, hand masks or new animation layer.
- Only 18 ME and 22 YOU rotation tracks change. Other translation/scale tracks, geometry, hierarchy, bind matrices, weights, materials and textures remain. All 230 other actions—including LOVE, YES, HELP and all 26 alphabet clips—are unchanged.

## Files

1. `app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb`: two scoped pointer clips.
2. Adjacent `fingerspelling-avatar.json`: checksum, explicit `pointingCorrection` provenance, measured direction/surface checks and preservation hashes. Older correction records remain historical.
3. `app/src/main/java/com/example/apphear/domain/texttoasl/AslFingerspellingBundle.kt`: checksum only.
4. `tools/correct-text-to-sign-pointing.py`: candidate-only generator with pinned input, exact scope and preservation checks; never overwrites production assets.
5. `app/src/test/java/com/example/apphear/AslPointingCorrectionTest.kt`: pointer scope/validation boundary, actual index extension/finger articulation, and preserved LOVE/YES/HELP/A–Z hashes.
6. `AslClosedFistCorrectionTest.kt`: retains older donor-provenance checks while recognizing the separate, explicitly tested ME index/arm correction.
7. `app/src/androidTest/java/com/example/apphear/AslFingerspellingPlaybackInstrumentedTest.kt`: adds I, ME YOU, YOU ME, YOU NICOLE and ME NICOLE to normal-input/queue/cancellation regressions.
8. This report.

## Technical evidence and limits

Candidate/final bundle SHA256: `82fab0b6693c5bdaef8433e25d4f417a51f0ede522ab9e9154e4f8cff7fddeb8`. Pinned predecessor: `c04f873aa44d7c31fdf688d423d18100843535067acab0223418ea9340fa34b5`.

Offline CPU skinning at 401 samples per clip found no hand/forearm penetration against the front-torso proxy. Index-direction cosine is approximately 1.0 for each intended target; this is a geometric measurement, not an accuracy percentage. The source binary prefix and all other actions match exactly.

Both candidate clips were rendered in the existing Android 16 Medium Phone WebView, then body and both-hand screenshots inspected. The recorded bone transforms match the candidate with maximum angular error approximately 0.00000296 degrees and no interfering scheduled clip. Candidate captures use an injected local Blob and are not proof that the installed predecessor contains these changes. Installed final-APK checks are recorded after building below.

Remaining limits: low-poly fingers remain angular; the thumb donor and contact/timing need qualified ASL review; the proxy does not prove all-mesh or arm-arm collision clearance. No new physical-phone test, qualified review, or individual visual A–Z audit is implied. Text-to-Sign grammar/validation notices and automatic fingerspelling remain intact. No Sign-to-Text, camera, recognition/model, home/navigation/UI, database, shared settings, Gradle or SDK changes.

To reproduce, recover the binary bundle from checkpoint `b2c3163` without changing the checkout, then run `correct-text-to-sign-pointing.py --source <checkpoint.glb> --output <candidate.glb> --report <audit.json>`. NumPy/Pillow are existing development-only tools. Inspect the candidate on Android before separately applying it. The generator rejects other baseline hashes.

Evidence is stored in the existing `outputs/AppHear-Word-Finger-Fix-Review` directory, including `me-you-candidate.json`, its CPU comparison PNGs, `closed-fist-runtime-me-you-candidate.json`, the corresponding Android screenshots and `me-you-candidate-android-comparison.json`.

## Final installed-APK verification

- `testDebugUnitTest`, `assembleDebug`, `assembleDebugAndroidTest`: successful. 247 unit tests, 0 failures/errors/skips. The initial run exposed two test-filter mistakes (unchanged translation tracks and lexical LETTER/mail counted as an alphabet letter); these were corrected and the full checks rerun. No animation changes were required for those test failures.
- Signed APK: `app/build/outputs/apk/debug/app-debug.apk`. SHA256 `08fc66b848d5f91afb9923c5eef407379deb890dba8bbad6e3640eaf0432c55b`. Signature verified, packaged bundle SHA matches the tested candidate, and emulator-installed APK hash matches the build.
- The emulator was restarted during this work using the same existing Medium Phone API 36 AVD, without wiping or creating another device. An in-place update failed for insufficient storage. Using the user's existing AppHear-only keep-data authorization, current AppHear data was backed up to a private local archive before replacing its code. The onboarding preference hash was unchanged afterward. No phone, other apps or laptop cleanup targets were modified.
- Final Android 16 emulator normal-input test: 26 inputs plus NICOLE→ANNA cancellation/replacement passed in 252.983 seconds on one existing WebView. Inputs: NICOLE, NAME, YOU, ANNA, JAZZ, ACTION, HELLO NICOLE, ME, YES, LOVE, HELP, COOK, BECOME, MONEY, NEW, SOME, DAY, HELLO LOVE, MY NAME, YOUR NAME, I LOVE YOU, I, ME YOU, YOU ME, YOU NICOLE, ME NICOLE. Technical queue completion is not ASL sentence validation.
- ME and YOU were submitted through the existing input/buttons and captured from the installed APK's own local asset, with no injected candidate. Both held poses and hand close-ups were inspected. Final bone comparisons pass: approximately 0.00000296° maximum error for ME, 0.00000171° for YOU, with no interfering scheduled clip. A manual capture that accidentally appended `ME` to a prefilled `me` field was discarded and recaptured with exactly ME; the normal-input automated test explicitly replaces text and checks the displayed request.
- The collected AndroidRuntime/Chromium log window contained no exceptions. This is not proof of every possible startup/device condition. Home/navigation and existing Text input were exercised; camera/Sign-to-Text, databases and live account/Gemini/voice connectivity were not runtime regression-tested. Their source remains unchanged. The build reused the existing public `fake` service configuration, not new private service settings.
- Individual A–Z visual and physical-phone testing were not repeated in this follow-up. All 26 alphabet actions are preserved exactly; NICOLE, ANNA, JAZZ, ACTION and mixed word/fingerspelling tests pass. Qualified ASL review, thumb/mesh refinement and full trajectory/linguistic evaluation remain outstanding.

Final evidence in the same existing review folder: `me-you-installed-input-tests.json`, `closed-fist-runtime-me-installed.json`, `closed-fist-runtime-you-installed.json`, `me-installed-pose-comparison.json`, `you-installed-pose-comparison.json`, and body/hand images named `closed-fist-SIGN_I-*-me-installed.png` and `closed-fist-SIGN_YOU_HUMAN_RETARGETED_PREVIEW-*-you-installed.png`. The viewer was restored to normal settings and the updated app left open. No push or additional exported APK copy.
