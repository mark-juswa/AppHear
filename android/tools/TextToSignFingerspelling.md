# Single-human fingerspelling milestone

Only Text-to-Sign was changed. Continue from `apphear/text-to-sign-redesign`; checkpoint `ab2ae51` precedes these changes. No UI layouts, navigation, recognition, camera, models, service configuration, database, dependency versions or original source clips were changed. The existing pilot/alphabet/OriginalWords build flags gate this milestone.

## Actual assets and rendering contract

The existing alphabet is **26 named FemaleASL letter actions**, including moving J and Z, in `app/src/aslAlphabet/assets/asl_animations/vnext/shared-alphabet.glb`, SHA-256 `645da29f5e8a24dc7da2f4b6e23ca2e87fb91254958f5053ba0281080ec0a524`. It uses a different rig from the resident Wolf3D human; directly loading it would change characters. Source alphabet handshape accuracy and motion rights were not established by the previous import. All letters remain unreviewed.

The development tools decode those actions with the existing vendored MIT meshoptimizer decoder and retarget their arm/wrist/finger rotations through anatomical segment and palm frames. The source pelvis and ancestor transforms are included; omitting them produced sideways hands during the first visual check and was corrected. Target bone lengths, geometry, skinning, materials, textures and the 203 existing word actions are retained. No runtime motion synthesis, new Android dependency or legacy-character fallback was added.

`fingerspelling-avatar.glb` contains **229 actions: 203 original word actions plus 26 retargeted alphabet previews**, using the existing human mesh and skeleton. SHA-256 `6d74df5b6a0065a5f55e83d4b7863324f5c213852a9d649cd1b40fe7730ae600`; 24,564,576 bytes. The original 203-action bundle and all source clips remain for rollback. The loader verifies the pinned hash, schema, character, language, letter coverage, action names and durations before exposing the alphabet. Every active word, letter and neutral pose uses the same combined URL. Corrupt data causes a visible loading error rather than a different avatar.

Each letter has explicit neutral endpoints, with a 250 ms interpolation into/out of its existing recorded motion. This separates repeated letters through completed clip actions, not arbitrary queue timers. It is slow citation-style preview spelling, **not validated fluent coarticulation or native double-letter movement**. J and Z retain source motion and measurable retargeted wrist movement; their path, finger orientation and comprehensibility still need signer review.

## Planning and queue behavior

1. Fully reviewed ASL phrase records retain first priority, including their asset and embedded non-manual requirements. There are currently zero reviewed phrase records.
2. Existing complete dictionary entries and longest embedded expressions such as THANK YOU retain priority. Existing lexical clips remain labeled unreviewed previews.
3. Each unmatched A–Z word is atomically mapped through all of its letters. NAME becomes N-A-M-E; NICOLE becomes N-I-C-O-L-E. Names after declared name-introduction prefixes are spelled even if a name also matches a lexical word.
4. Missing letters, non-A–Z tokens, numbers or symbols report the whole unavailable token; a partial name is never silently emitted. Punctuation, case and whitespace normalize; symbols are retained for error reporting. Limit: 80 characters per spelled word and 256 actions per request. Oversized queues fail with a shorter-input message.
5. Existing output labels identify the word, current letter and letter position. `fingerspelledWords` records word boundaries separately from lexical/phrase metadata. Mixed output is explicitly an English word-sign/fingerspelling preview, never a validated ASL sentence.
6. Everyday unreviewed sentence candidates may use temporary literal word/fingerspelling output when the complete same-human alphabet is loaded. English words are retained; question facial grammar is not invented. Idioms already blocked by the grammar registry remain blocked. Negation is preserved by signing or spelling; unrenderable negation still stops incomplete output.
7. The existing fragment queue advances through the player's real animation timeline/completion callbacks. Token cancellation rejects stale/duplicate callbacks. Existing Sign It, Repeat, Clear and navigation behavior remains. The final neutral pose comes from HELLO's resting frame in the same combined model.

## Standalone NAME work

[ASL University NAME](https://www.lifeprint.com/asl101/pages-signs/n/name.htm) describes two H handshapes and commonly two contacts; question expression has additional non-manual grammar. This source is a reference, not a license to package its media. No reference video/images were copied.

The [Kozha NAME SiGML candidate](https://github.com/zhan-a/Kozha/blob/main/data/American_SL_ASL.sigml) describes handshape, orientation, neutral space, crossing and repeated movement. Its companion metadata reports CC BY-NC 4.0, heuristic orientation, review required and zero Deaf-native reviewers. It contains **no Wolf3D joint-space keyframes**. A direct format conversion cannot supply calibrated rig geometry/contact; a SiGML interpreter plus review or manual animation is necessary. It was inspected but not incorporated into the APK.

`author-text-to-sign-name-candidate.py` now creates a **quarantined human-rig review animation**, reusing retargeted H finger configuration, mirrored anatomical hand setup, two-bone arm IK and two dominant-hand lowering movements around crossed contact anchors. It is a development candidate, not a correct NAME claim. Output goes to a caller-selected review folder outside Android assets. Palm orientation, finger contact, thumb position, mirrored handshape, timing and movement need correction and qualified ASL review. It is not registered or included in the APK, and NAME uses fingerspelling until that work is complete. No old robot motion is used.

## Reproduce development assets and build

Use Node and Python with NumPy for offline development only; the app does not depend on Python/NumPy. From `android`:

```powershell
node tools/decode-text-to-sign-alphabet.cjs ../../../work/decoded-alphabet.json
python tools/retarget-text-to-sign-alphabet.py ../../../work/decoded-alphabet.json
python tools/author-text-to-sign-name-candidate.py ../../../outputs/ASL-Name-Review
```

Retargeting starts from the unchanged 203-action resident bundle and writes a different combined file. The pinned Kotlin hash must match the deterministic output. Do not change old source manifests or certify the resulting motions through hashes alone. Build with the existing `../tools/android/build_working_baseline.ps1 -Configuration fake -OriginalWords`, JDK 17 and the existing SDK configuration; no Gradle/SDK/Kotlin upgrade is necessary. Fake configuration retains public test service settings; private connected services need the existing private configuration.

## Actual validation and limitations

- Android debug and instrumentation APK builds succeeded; **231 JVM tests passed** with zero failures/errors/skips.
- Tests cover all supplied inputs, longest phrase priority, full-word fallback, unrenderable tokens, repeated letters, one asset URL, preserved original word actions/skeleton, hashes and named actions. Existing no-fallback mode remains tested separately.
- Simulated real-player JavaScript tests passed for mixed word/letter clips, repeat/cancellation, missing actions, stale/duplicate/early events and timeline completion. One viewer loaded the bundle once across ten mixed/repeated actions. These are mocked viewer events, not Android rendering.
- Host CPU skinning rendered all 26 hand snapshots for inspection. Retargeted J/Z wrist trajectories were checked from output keyframes. This catches structural pose problems, but does not prove linguistic correctness or Android WebGL performance.
- Instrumentation tests were updated and compiled, but **not executed**: the available emulator crashed before boot (`-1073741819`, access denied `0xc0000022`). No phone was attached. No physical-device or qualified ASL evaluation occurred.
- No new reviewed lexical signs or reviewed phrases were added. The alphabet derivative remains unreviewed; inherited motion license/provenance is unresolved. Do not publish these assets as newly licensed/validated data.
- Facial grammar/mouthing, smooth fluent spelling, double-letter conventions, device rendering and real memory/latency remain open. Do not infer accuracy from a smooth animation or a passing test.

## Review and vocabulary expansion

For each letter/sign, review video playback on the selected human: handedness, thumb and finger contact, palm orientation, location, movement, timing, mesh intersections and return to neutral. For J/Z review the complete path, not one still frame. For ANNA/JAZZ verify double letters are recognizable; for NICOLE/HELLO NICOLE verify boundaries and comprehensibility. Record qualified review identity/date, meaning/variant, source/license, device/playback evidence and correction notes before upgrading metadata.

Add real lexical assets only after their rig, motion, source/license and review records are established. Existing compatible signs are reused automatically; missing vocabulary continues spelling. A new lexical action must be added to the governed resident-bundle tooling/manifest and checksum, plus loader/domain tests, without replacing the shared avatar. NAME is explicitly excluded until its review candidate becomes a tested and validated lexical clip. Do not map CALL_SOMEONES_NAME or an old robot phrase to standalone NAME.
