# Fingerspelling playback regression repair

## Root cause confirmed on a physical phone

The relaxed-posture commit `b3fef24` added built-in crossfading while resuming the outgoing action, followed by `viewer.currentTime = 0`. In the bundled model-viewer 4.3.1, this setter calls `AnimationMixer.setTime` on the entire mixer. Rewinding its clock after scheduling fades leaves the incoming animation at weight zero and the outgoing neutral/letter at weight one. Cached actions can accumulate competing weights. The displayed timeline advances although its finger transforms do not control the skeleton.

Live debugging on the authorized phone confirmed I at effective weight 0 and neutral at 1. Six baseline NICOLE samples failed the full-pose gate; maximum local finger rotation discrepancy from their actual glTF tracks was 99.55 degrees. This is playback interference, not a new finger clamp. The subsequent word-finger commit `8186fe9` did not change the alphabet assets. No rig/skin/handshape asset changes are necessary to fix this demonstrated regression.

## Scoped correction

Pause before changing animationName, clear cached actions, and seek before scheduling any transition. Disable built-in crossfade for this path. Start the incoming named action at full weight. Use public `appendAnimation` / `detachAnimation` to fade a bounded outgoing pose over 120ms for letters, 220ms for final neutral return. No subsequent mixer seek occurs while that fade is scheduled. Outgoing actions keep timeScale 1 and clamp at their endpoint; never freeze a cached letter's timeScale, which would prevent it playing later. Repeated identical names are explicitly reselected while paused so Lit's equal-value optimization cannot skip the reset.

These public APIs are described in [model-viewer documentation](https://modelviewer.dev/docs/). Production code does not access private mixer symbols. Debug-only inspection reads the pinned version's internals to measure actual action weights and bone transforms. Lexical signs use no outgoing overlay; their full body/finger data remain intact. One resident avatar, completion-driven queue, cropped signing posture, J/Z source trajectories and automatic fallback remain in place.

## Changed files

- `app/src/aslPilot/assets/pilot_player.js`: targeted replay ordering and bounded outgoing-pose fade.
- `tools/test-text-to-sign-player.cjs`: public append/detach mock support for existing completion/error/cancel tests.
- `tools/test-text-to-sign-resident.cjs`: tests seek-before-fade ordering, repeated names, nonfrozen cached actions, lexical isolation and final neutral transition.
- `app/src/androidTest/java/com/example/apphear/AslFingerspellingPlaybackInstrumentedTest.kt`: normal-screen requests for NICOLE, NAME, ANNA, JAZZ, HELLO NICOLE, LOVE, HELP and cancellation; launcher avoids the prior global-idle startup gate.
- `tools/inspect-text-to-sign-phone.cjs`: development-only actual WebView finger/weight snapshots and Android screenshots; temporary camera zoom restored afterward.
- `tools/audit-text-to-sign-phone-poses.py`: independent comparison against real glTF rotations and competing animation weights.
- `tools/TextToSignFingerspellingPlaybackFix.md`: this record.

No alphabet/word GLB, rig, skin weight, dictionary, Android UI, navigation, recognition, MediaPipe, model, database or dependency changed. Temporary close-up cameras are diagnostic only, not product UI changes.

## Actual results and limits

Android build succeeded for application and instrumentation APKs; 237 existing unit tests remained passing/up-to-date. Both updated Node player tests pass. The new focused instrumentation class compiles. The old normal-screen test timed out at activity startup; a focused attempt also encountered startup restrictions, then a USB disconnect. The revised foreground-launcher test has not completed and is not reported as passing.

Physical-phone prototype: 32 samples (NICOLE plus A–Z) reached effective weight 1 with no competing nonzero action at sample time. All measured right-hand local quaternions matched their actual source tracks within 0.000002 degrees. Six real Android close-up NICOLE screenshots demonstrate distinct rendered poses; unlike these screenshots, the initial CDP screenshot method missed the hardware WebGL surface and produced blank images, so those blank captures are not visual evidence.

The corrected APK was installed successfully with `adb install -r`, preserving data and signing identity. Its 1,534 packaged resource paths match the prior word-finger APK except `assets/pilot_player.js`; all avatar assets are identical. Full post-install A–Z screenshot replay and the revised normal-screen test still need completion after reconnecting the phone. Prototype inspection is explicitly distinguished from installed-APK testing.

This restores the source alphabet's articulation; it does not certify that every source handshape, thumb contact, doubled-letter cue or J/Z trajectory is linguistically accurate. All remain unreviewed pending qualified ASL review. Compare with [ASLU's alphabet](https://www.lifeprint.com/asl101/fingerspelling/abc.htm) and [fingerspelling guidance](https://www.lifeprint.com/asl101/pages-layout/fingerspelling.htm). No reference media was redistributed. LOVE/HELP assets are unchanged; their post-install rendered regression test remains pending. No new lexical sign was invented.

## Reproduce on a debug phone

Keep Text-to-Sign open without typing during diagnostic playback. Find its WebView debugger socket using `adb shell cat /proc/net/unix`, then forward it to port 9227. The diagnostic tool refuses other page URLs.

```powershell
adb forward tcp:9227 localabstract:webview_devtools_remote_<AppHearPID>
$env:APPHEAR_ADB = '<absolute-path-to-adb.exe>'
node tools/inspect-text-to-sign-phone.cjs <output-directory> <phone-serial> 9227 NICOLEABCDEFGHIJKLMNOPQRSTUVWXYZ
python tools/audit-text-to-sign-phone-poses.py app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb <output-directory>/runtime-poses.json <output-directory>/pose-audit.json --require-pass
node tools/test-text-to-sign-player.cjs
node tools/test-text-to-sign-resident.cjs
adb shell am instrument -w -r -e class com.example.apphear.AslFingerspellingPlaybackInstrumentedTest com.example.apphear.test/androidx.test.runner.AndroidJUnitRunner
```

The debug pose tool drives existing playback directly for measurement, not the normal input screen. The instrumentation class separately tests normal input/buttons. Neither establishes ASL linguistic correctness. Review all letters, J/Z motion, repeat boundaries, normal sequences and lexical signs with qualified ASL signers before changing validation status.

Checkpoint before changes: `d7cdb11` on existing branch `apphear/text-to-sign-redesign`. No push or merge.
