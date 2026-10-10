# Relaxed fingerspelling posture — 2026-10-10

Continued the existing development clone and branch `apphear/text-to-sign-redesign`.
Pre-edit reversible checkpoint: `a878a33`. No new clone, push or unrelated change.

## Cause

The fragment already advances directly from one queued letter to the next and
calls idle only after the queue. There was no concurrent breathing/idle layer.
The alphabet assets themselves contained added bind-pose endpoints and source
arm-raising/lowering movements in every letter. Consequently NICOLE performed
six separate arm-lowering/raising cycles. The shoulder bones were already steady;
the repeated whole-arm motion produced the apparent shrugging.

For example A's right wrist was about 0.998 m high at its added rest endpoint,
0.933 m at the source entry and 1.262 m while signing. Every letter repeated that
path. Fixing only the fragment's final idle call would not remove these resets.

## Changes

All 26 alphabet actions now use their audited central signing span: original
0.50 seconds through duration minus 0.50 seconds. This removes the added rest
endpoints and source approach/release. Finger and wrist poses within the retained
span are preserved using glTF spherical rotation interpolation. The final pose
holds for 180 ms as part of the animation timeline. Completion still uses the
actual animation timeline/event, not a fixed sequencing delay.

The selected human stays resident. Letter transitions use the existing
model-viewer public crossfade property with 120 ms blending; lexical signs use
zero crossfade and their complete existing timelines. A constant neutral action
copies the existing human's actual HELLO frame-zero pose. Returning from the final
letter uses a 220 ms crossfade to that pose. It does not overlay an idle or
breathing animation throughout signing. No shoulder locks, joint clamps, global
bone masks, synthetic lexical handshapes or new character were introduced.

The controller tells the viewer when an action is a LETTER. The fragment, word
lookup, automatic fingerspelling, dictionary semantics and normal UI are unchanged.
Repeated letters replay their complete revised action as separate queue entries;
no full-body neutral reset is inserted between them. Moving J/Z retain the source
trace within the signing span. Repeated-letter readability still needs qualified
review: no invented lateral repeat gesture was added.

The new constant neutral clip is an engineering pose, not a new sign or validated
breathing animation. The avatar retains source hand/arm motion while signing and
full lexical body motion. Idle breathing was not invented to disguise the issue.

## Exact changed files

Relative to the Android directory:

| File | Purpose |
|---|---|
| `app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb` | 26 revised letter timelines plus constant neutral action |
| Same directory, `fingerspelling-avatar.json` | Revised durations, checksum and signing-span audit |
| `app/src/aslPilot/assets/pilot_player.js` | Letter-only crossfade and final neutral-pose blending |
| `app/src/main/java/com/example/apphear/domain/texttoasl/AslFingerspellingBundle.kt` | Integrity checksum |
| `app/src/main/java/com/example/apphear/ui/texttoasl/TextToAslPlaybackController.kt` | Pass LETTER flag to viewer |
| `app/src/test/java/com/example/apphear/AslFingerspellingFallbackTest.kt` | Expect the additional neutral action |
| `app/src/test/java/com/example/apphear/AslFingerspellingPostureTest.kt` | Signing-span coverage/durations and preserved provenance |
| `tools/test-text-to-sign-resident.cjs` | Letter/word transition settings, neutral return and retained-avatar assertions |
| `tools/prepare-text-to-sign-posture.py` | Reproducible, checksum-guarded preparation |
| `tools/audit-text-to-sign-posture.py` | Source-pose, shoulder, J/Z and lexical-preservation checks; comparison renders |
| `tools/TextToSignRelaxedPosture.md` | Documentation |

Mesh, skin weights, skeleton, bind pose and all 203 lexical actions—including the
LOVE correction and HELP—are unchanged. Existing original individual assets stay
intact. No dependency/SDK/Gradle upgrades, UI layout, navigation, Sign-to-Text,
recognition model, camera, database or unrelated setting edits.

## Technical evidence and testing

- All 26 letters checked at 21 times in their retained signing span. Maximum
  source-to-revised world-matrix error 1.55e-7; maximum shoulder-matrix variation
  7.78e-16. This confirms preservation, not linguistic accuracy.
- J/Z wrist-motion spans exceed 1 cm; their movements were not replaced by stills.
- All 203 lexical action descriptions and the complete prior binary prefix match
  the pre-edit bundle. Geometry and skin data match too.
- Fixed-camera front/side actual mesh renders cover A, B, J, Z, NAME, NICOLE,
  ANNA and JAZZ. Comparisons sample late-letter poses (94% of each respective
  timeline), showing removal of the old per-letter full-body rest return.
- Existing player event/cancellation/neutral/error tests pass. The resident test
  covers LOVE, HELLO, BEAUTIFUL and repeated N/Z with one model load; it checks
  120 ms for letter transitions, zero for lexical signs and 220 ms for final idle.
- Existing lookup tests cover automatic NAME/NICOLE/ANNA/JAZZ fallback and HELLO
  NICOLE. They do not claim a validated ASL sentence translation.
- Android unit tests, application APK and instrumented test APK build succeeded:
  **235 tests, zero failures/errors/skips**, build time 5m 12s. Instrumented tests
  were compiled but not executed on a device.
- Signature verification passed with the same existing debug certificate.
  Compared 1,534 asset/resource/manifest paths against the LOVE-fix APK: only
  the combined avatar GLB/JSON and pilot player JS changed. Normal layouts,
  camera framing, recognition assets and Android resources remain identical.

Build/export counts and APK comparison results are recorded in the workspace
`outputs/AppHear-Relaxed-Posture-Review/build-verification.json` and
`outputs/AppHear-Relaxed-Posture-Report.md` after the build. Existing fake service
configuration is retained; private connected services need the existing private
setup. No keys or private configuration were changed.

## Device and linguistic limits

No physical phone is attached. Pixel_3a could not boot because Windows hardware
acceleration is unavailable. CPU renders are actual skinned geometry without
textures; they are not emulator screenshots. The player event tests use a mock
viewer while exercising the real player code. Native WebView GPU crossfade
appearance, speed, cancellation during a fade, final neutral return and double
letter legibility still require on-device review. Public API behavior was checked
against the locally bundled model-viewer 4.3.1 code; it was not replaced/upgraded.

The avatar retains its existing neutral stance; no qualified relaxed-posture or
ASL validation has occurred. Alphabet/lexical entries remain unreviewed previews.
Prior HELP/THANKS collision issues and missing standalone NAME are unchanged.
No additional linguistically verified signs/phrases are claimed.

Phone review: A, B, J, Z, NAME, NICOLE, ANNA, JAZZ, HELLO NICOLE, LOVE and HELP.
Check shoulders/elbows, finger contact/palm orientation, moving-letter paths,
repeated letters, stable signing height, transition blending, fast new input,
neutral return, same avatar, unchanged screens and qualified ASL comprehensibility.

## Reproduce

From the Android project, development NumPy/Pillow and Node are required only for
the tools; they are not Android dependencies:

```powershell
python tools/audit-text-to-sign-posture.py BEFORE.glb app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb REVIEW_DIR
node tools/test-text-to-sign-player.cjs
node tools/test-text-to-sign-resident.cjs
```

The preserved workspace baseline is `work/posture-before.glb`. Preparation is
idempotent and rejects unknown source checksums. Use checkpoint files in a test
copy for regeneration; do not overwrite original assets or rerun old retargeting
tools over this bundle. The workspace build/export entry is
`outputs/Build-AppHear-Relaxed-Posture.ps1`.
