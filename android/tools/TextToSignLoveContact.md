# LOVE contact correction — 2026-10-10

Development branch: `apphear/text-to-sign-redesign`. Reversible pre-edit checkpoint:
`b8c302b`. Continued the existing `outputs/AppHear-source` clone; no new clone,
push, dependencies, recognition, navigation or screen-layout changes.

## Actual cause and correction

The native `SIGN_LOVE` animation places the right wrist behind the front chest
surface while the left hand stays far forward. At 0.58 seconds the original right
wrist z is approximately -0.014 m, versus +0.255 m on the left. True skinning of
the weighted mesh confirms the disappearing right hand. The bind matrices and
weights are internally consistent (identity error 7.20e-7, weight-sum error
1.19e-7). This specific failure is in the source arm/contact animation, rather
than evidence of a defective global rig or overlapping playback.

`correct-text-to-sign-love.py` applies a LOVE-specific offline correction using
the actual weighted torso front surface and two-bone arm IK. It preserves bone
lengths, source finger channels and wrist orientation. Only six arm/forearm/wrist
rotation channels change. Approach/release are rerouted over 0.30 seconds each;
the held crossed-arm XY positions remain unchanged. The corrective tracks are
sampled at 240 Hz because lower-rate joint interpolation produced between-key
forearm clipping. The original 2.1666667-second timeline is retained.

This is not generic collision avoidance: signs with intentional contact are not
automatically pushed away. The original individual LOVE file and native resident
bundle remain intact. All 202 other native word actions, all 26 previously
corrected alphabet actions, mesh, skin, hierarchy, bind pose and materials are
unchanged. Earlier distal-finger calibration is preserved; no generic finger
rotation clamps or new handshapes were introduced.

The viewer camera changes from orbit `0deg 75deg 3m`/target `0m 1.5m 0m` to
`0deg 85deg 2.6m`/`0m 1.3m 0m`. This frames the hands more directly within the
existing display. Both existing viewers use the same settings. Crossfade remains
zero to preserve handshape clarity. No normal UI/debug controls were added.

The existing completion/timeline checks, request cancellation and resident-avatar
reuse remain unchanged. Tests verify no simultaneous playback, stale/duplicate
completion rejection, neutral sampling, errors and repeated letters. No robot
fallback was introduced. Automatic lexical-sign/fingerspelling lookup remains.

## Exact files changed

Paths are relative to the existing Android directory:

| File | Reason |
|---|---|
| `app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb` | Six LOVE corrective rotation tracks |
| Same directory, `fingerspelling-avatar.json` | New checksum and unreviewed contact-correction provenance/measurements |
| `app/src/main/java/com/example/apphear/domain/texttoasl/AslFingerspellingBundle.kt` | Update expected bundle integrity hash |
| `app/src/aslPilot/assets/model_viewer_pilot.html` | Camera framing only |
| `app/src/test/java/com/example/apphear/AslFingerspellingFallbackTest.kt` | Permit only the separately tested LOVE change in native-action integrity assertion |
| `app/src/test/java/com/example/apphear/AslLoveContactTest.kt` | Six-channel scope, unchanged fingers/rig, strict times, unit quaternions and original endpoints |
| `tools/correct-text-to-sign-love.py` | Reproducible, checksum-guarded offline correction |
| `tools/audit-text-to-sign-contact.py` | Independent sampled skin/contact measurements and comparison renders |
| `tools/audit-text-to-sign-hands.py` | Explicit `--love-corrected` audit mode; add LOVE to development samples |
| `tools/hand_pose_inspector.html` | LOVE in development-only selector |
| `tools/test-text-to-sign-resident.cjs` | Actual player tested with combined bundle, LOVE, words and repeated letters |
| `tools/TextToSignLoveContact.md` | This documentation |

## Performed checks

- Android `testDebugUnitTest`, `assembleDebug`, `assembleDebugAndroidTest` succeeded:
  **233 tests, zero failures/errors/skips**. Existing Gradle/SDK configuration retained.
- APK signature verified with the existing debug certificate SHA-256
  `5a315db9ca99c70f5f0c127dc8c6558e02d343e5b41d0bf4eee8bb256ce38a8c`.
- Independent LOVE audit: 347 sampled poses including between corrective keys.
  Maximum projected hand depth changed from 0.26778 m to zero; forearm depth
  from 0.23153 m to 0.00177 m. These are front-surface technical measurements,
  not accuracy percentages. Between-key held XY error 0.000319 m; bone-length error 5.34e-8 m.
- A–Z, HELLO, BEAUTIFUL, HELP and THANKS: actual mesh sampled 25 times per action,
  with fixed-camera front/side comparison renders. A–Z/HELLO/BEAUTIFUL showed
  no projected torso penetration at these samples. J/Z motion remains unchanged.
- Existing `test-text-to-sign-player.cjs` passed cancellation, completion-driven
  sequencing, neutral sampling, retained avatar and error handling.
- New resident test passed eleven mixed/repeated word/letter clips including
  LOVE, with one loaded model. Existing NAME/NICOLE/ANNA/JAZZ/ACTION and HELLO
  NICOLE lookup/fingerspelling tests passed within the 233-test suite.
- Compared 1,534 packaged asset/resource/manifest paths against the previous
  Hand-Fix APK: only the combined GLB, its JSON manifest and viewer HTML changed.
  Unrelated layouts, recognition assets and packaged Android resources match.
- No attached phone. Pixel_3a emulator failed because Windows hardware
  acceleration is unavailable; API36 software-emulation attempt exited before
  boot. Android instrumented tests compiled but were not run. Browser WebGL
  could not connect to the local inspector in this session.

Visuals are CPU renders of the actual skinned mesh, not Android screenshots.
They omit textures and use colored geometry to reveal body intersections.
See workspace `outputs/AppHear-Love-Fix-Review/sign_love-comparison.png`,
`alphabet-review.png`, per-action comparisons and `contact-audit.json`.

## Remaining limitations and review

LOVE is still an **unreviewed preview**, not linguistically validated ASL. The
source left hand can remain about 15 cm forward; only excessive right-side body
penetration and the approach/release problem were corrected. The front-surface
proxy is not a closed-volume collision test and does not guarantee no arm-arm,
finger-finger or back-body intersections. Qualified review must assess contact,
crossing order, fist/thumb placement, palm orientation, timing and naturalness.

HELP and THANKS retain possible forearm intersections (projected maxima 0.08346 m
and 0.05623 m). Their source hand paths were not automatically rerouted. They
need sign-specific correction/review. No standalone NAME asset was created;
NAME still fingerspells. I LOVE YOU has no newly validated sentence animation;
any available individual-sign/fingerspelling preview must not be presented as a
validated ASL sentence. No new lexical sign or grammar claim was added.

Review on the phone: LOVE, HELLO, BEAUTIFUL, HELP, THANK YOU; all A–Z (J/Z in
motion); NAME, NICOLE, ANNA, JAZZ, ACTION; HELLO NICOLE; I LOVE YOU. Inspect both
hands from front and side, first/last frames, repeated letters, fast new requests,
pause/repeat, neutral return and all existing screens. Record device, reviewer,
variant, reference, timestamp, verdict and necessary corrections. Qualified ASL
review has not occurred; zero signs/phrases gain verified status from this fix.

Reference: [ASL University LOVE](https://www.lifeprint.com/asl101/pages-signs/l/love.htm).
It describes crossed hands at the chest; LOVE and the ILY acronym are distinct.
No reference videos or third-party animation assets were downloaded or bundled.

## Reproduce technical checks

From the Android project, with development NumPy/Pillow and Node installed:

```powershell
python tools/audit-text-to-sign-contact.py BEFORE.glb app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb REVIEW_DIR
node tools/test-text-to-sign-player.cjs
node tools/test-text-to-sign-resident.cjs
python tools/serve-hand-inspector.py --before BEFORE.glb
```

This session's BEFORE is the workspace `work/love-fix-before.glb`; preserve it.
The correction tool is idempotent on its corrected manifest and rejects unknown
baselines. To reproduce from scratch use the checkpoint bundle/manifest in an
isolated test copy, not the original repository. Build/export using workspace
`outputs/Build-AppHear-Love-Fix.ps1`; the `fake` configuration preserves the
existing test service settings, while `private` needs the existing private setup.
