# Text-to-Sign vocabulary batch 2 — 2026-10-15

Scope: existing development clone and branch, Text-to-Sign only. Update-1 is
checkpointed at `4227c42` / `checkpoint/update-1-before-batch-2-20261015`.
No UI, navigation, camera, recognition, database, dependency or runtime player edit.
No source or exported APK deletion is part of this batch. No push.

## Vocabulary audit and selection

Update-1 contains 216 lexical dictionary entries, 215 unique lexical actions,
26 alphabet actions and one neutral action. NAME shares an existing NAME/CALL
variant; aliases and arbitrary fingerspelled words are not additional lexical actions.
Qualified ASL validations: zero. Existing entries are not newly certified here.

Six additional lexical entries are candidates for the same resident human rig:

| Input | Previously supported lexically | Meaning/reference | New action | ASL status |
|---|---|---|---|---|
| AGAIN / repeat / do over | No | [ASLU AGAIN](https://www.lifeprint.com/asl101/pages-signs/a/again.htm): bent dominant fingertips arc toward flat other palm | `SIGN_AGAIN_HUMAN_RETARGETED_PREVIEW` | Requires ASL validation |
| CLASS | No | [ASLU CLASS](https://www.lifeprint.com/asl101/pages-signs/c/class.htm): educational class, two C hands outline a group | `SIGN_CLASS_HUMAN_RETARGETED_PREVIEW` | Requires ASL validation |
| MUST | No | [ASLU NEED/MUST](https://www.lifeprint.com/asl101/pages-signs/n/need.htm): X hand/wrist motion, related to NEED, not all meanings of critical | `SIGN_MUST_HUMAN_RETARGETED_PREVIEW` | Requires ASL validation |
| FINGERSPELL / fingerspelling / spell | No | [ASLU FINGERSPELL](https://www.lifeprint.com/asl101/pages-signs/f/fingerspell.htm): lexical movement about spelling, independent finger flexion | `SIGN_FINGERSPELL_HUMAN_RETARGETED_PREVIEW` | Requires ASL validation |
| SO-SO | No | [ASLU SO-SO](https://www.lifeprint.com/asl101/pages-signs/s/so-so.htm): middling condition, hand rocks | `SIGN_SO_SO_HUMAN_RETARGETED_PREVIEW` | Requires ASL validation |
| GROW UP | No | [ASLU GROW UP](https://www.lifeprint.com/asl101/pages-signs/g/grow-up.htm): childhood to adulthood, not every meaning of raised | `SIGN_GROW_UP_HUMAN_RETARGETED_PREVIEW` | Requires ASL validation |

This is four single-word entries plus two short lexical expressions, six motion
actions. Alternative English forms are not counted as extra animations. No new
validated sentence/phrase translation or non-manual grammatical expression is claimed.
The resulting catalog has 222 lexical entries / 221 unique lexical actions;
including alphabet and neutral, 248 actions.
These are six new dictionary entries/motion actions, not a claim of six distinct
ASL lexemes: MUST is a related NEED variant. Imperative facial emphasis is not validated.

Rejected/deferred: `request.glb` actually names a PREFER/FAVORITE action; CHILDREN
names a longer CHILDREN_YOU expression. Do not relabel these to inflate coverage.
GIRL, MARRY, MINUS and emphatic DON'T candidates had substantial clipping and are
not enabled. DON'T also requires context-specific negation; no universal English
negation mapping is introduced. Their prior spelling behavior stays in place.
DAD/MOM, WE/THEY and broad synonym forms are not counted as distinct new signs.

## Implementation and corrections

Existing repository source motions use a different 54-node skeleton. Conversion
maps anatomical bone frames onto the 69-node resident human without altering its
geometry, skeleton, bind pose, skin weights, textures or any of the 242 old actions.
Original source GLBs remain untouched. Source hashes and actual action names are
recorded in the bundle metadata; unexpected source actions/duplicate IDs fail.

Direct conversion exposed finger-axis twist and unsuitable contact placement.
For these new actions only, corresponding native B/C/X hand articulation is reused;
AGAIN uses its bent dominant hand and flat other hand. Left-hand articulation is
reflected through the rig's actual rest/parent frames, not copied as raw right-hand
quaternions. FINGERSPELL preserves source-driven independent joint flexion, removing
the incompatible axial twist rather than locking all fingers or imposing joint limits.
MUST retains its lexical wrist motion. SO-SO/GROW UP retain source wrist/arm motion.
SO-SO uses the reference's open five-hand; GROW UP uses an extended flat hand.

Scoped placement correction moves both AGAIN hands 35 mm forward, retaining their
relative geometry. CLASS uses 30 mm forward placement and lowers only its elevated
signing area by up to 200 mm; neutral arms are not pushed beyond reach. Fixed-length
mesh-aware arm IK preserves chosen hand orientation. No generic collision rule is
applied to existing signs. The source timing/repetitions and exact contacts still
need qualified review. The existing completion-driven queue, cancellation, relaxed
fingerspelling posture, alphabet fallback and no-robot policy are reused unchanged.

## Verification and limitations

Independent audit samples 41 poses/action: existing action descriptions and binary
prefix preserved exactly; finite unit rotation tracks, unchanged geometry/skin.
Final bundle SHA256:
`c8e86f065acd1bb0fe39ee7524daad73324106a53fb8b455bf89744e4a1a778d`.
The final corrected candidate passes the sampled hand/forearm front-surface proxy
for all six actions. This is not full triangle collision or linguistic verification.
Actual rendered review, final Android build/input results and exported hash are
recorded below when complete; candidates must not be reported as installed prematurely.

The emulator initially exhibited System UI/AppHear ANRs under host memory pressure;
an Update-1 input test timed out before any new asset was installed. The test also
used page Ready before actual GLB readiness. Its cold-model readiness wait is now
explicit, without changing production playback. Failed runs are not counted as passes.
All six new actions were inspected in the actual Android 16 emulator WebView, first
as separate candidate models. No individual screenshot set is required; compact
review sheets are in the existing `outputs/AppHear-Word-Finger-Fix-Review` folder.
Phone-pose/source comparisons pass for six samples, then AGAIN's updated contact
sample separately, at a maximum finger quaternion error of 0.00000171 degrees,
full action weight and no interfering action. These are sampled technical checks,
not a statement that each ASL movement is linguistically correct.

The rendered AGAIN gap was corrected after the handshape review: at the source
motion's closest approach (2.433333s), a smooth local correction brings the dominant
middle fingertip to 10 mm above the other palm's bone plane. Only RightArm,
RightForeArm and RightHand samplers change; its finger channels and the other 247
actions remain unchanged. The modeled surface gap was 71 mm before correction;
the corrected rigid finger shift error is under 0.00000002 m. This geometric
contact does not certify skin contact, timing, repetition or signer comprehensibility.
FINGERSPELL retains independent source-driven excursions of all four fingers;
fingers do not share one locked or generic closed-hand pose. All 26 alphabet
actions, including J/Z trajectories, are byte-identical to Update-1.

Licensing: existing AppHear motion/rig rights remain unresolved, as in Update-1.
These are local unreviewed development previews, not a redistribution clearance.
Reference links were inspected; no external instructional media/dataset was packaged.
The established fake-service debug build does not provision private account/voice/
Gemini connectivity. Physical-device and qualified Deaf ASL signer tests have not occurred.

## Files in scope

- `app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb`: append accepted new actions only.
- Adjacent `fingerspelling-avatar.json`: additive dictionary/source metadata; old entries preserved.
- `app/src/main/java/com/example/apphear/domain/texttoasl/AslFingerspellingBundle.kt`: bundle hash only.
- `app/src/test/java/com/example/apphear/AslVocabularyExpansionTest.kt`: new lookup/alias/mixed-spelling/rejection tests.
- `app/src/test/java/com/example/apphear/AslFingerspellingFallbackTest.kt`: action count.
- `app/src/androidTest/java/com/example/apphear/AslFingerspellingPlaybackInstrumentedTest.kt`: six new inputs, aliases/sequences and actual initial-model readiness.
- `tools/test-text-to-sign-resident.cjs`: action count for all-action controller coverage.
- `tools/expand-text-to-sign-everyday.py`: reusable offline generation entry point; old batch defaults preserved.
- `tools/audit-text-to-sign-everyday.py`: reusable audit counts/key; old actions audited against supplied checkpoint.
- `tools/expand-text-to-sign-batch2.py`: scoped source conversion/handshape/placement corrections.
- This report.

## Reproduction / expansion

Recover the Update-1 bundle and adjacent JSON from the checkpoint into a separate
working filename. Run `expand-text-to-sign-batch2.py BASELINE.glb CANDIDATE.glb
CONVERSION.json`, then `audit-text-to-sign-everyday.py BASELINE.glb CANDIDATE.glb
AUDIT.json everydayExpansion2`. The offline scripts require the existing NumPy/Pillow
developer runtime; no mobile dependency is added. Review actual Android output before
replacing the bundle and checksum. Build with the existing OriginalWords baseline
wrapper and run unit/controller/instrumentation tests. Future additions must check
aliases, source action identity, meaning, rights, handshape, orientation, contact,
independent motion, timing/transitions and signer review. Do not set linguistic
validation status based on build/render success.

## Completed build and installed tests — 2026-10-16

- Final app build: `testDebugUnitTest assembleDebug assembleDebugAndroidTest`,
  successful in 9m12s using the unchanged SDK/Gradle configuration. Actual JUnit
  XML total: **252 tests, zero failures/errors**. The test-only readiness refinement
  subsequently built with `assembleDebugAndroidTest` in 2m34s; production APK unchanged.
- Controller tests: pass, one resident model and 294 word/letter clips/completion
  callbacks across all 248 action names, cancellation, stale completion and load errors.
  These are controller mocks, separate from the actual device evidence.
- Installed Android 16 Medium Phone test: **OK (1 test)**, 355.263 seconds,
  covering **75 normal-input cases plus cancellation**. All six additions, aliases,
  HELLO CLASS NICOLE, HELP AGAIN, existing lexical inputs, A–Z inputs and the
  requested name/letter sequences completed. Standalone I selects ME/I; letter I
  is exercised within NICOLE/ACTION. GIRL retains spelling, not an unsuitable lexical clip.
- Initial runs failed on readiness before signing under host/emulator memory
  pressure/System UI ANRs; another callback deadline was too short. They are not
  counted as passes. The successful run used the same AVD, 3 GB RAM, two cores,
  software graphics and temporarily **540×1200 at 210 dpi**, preserving logical
  layout size. **1080×2400 at 420 dpi was restored** afterward and the test emulator
  closed to free laptop memory. No wipe or new AVD. This is not a phone or original-
  resolution performance benchmark. Physical phone testing was not performed.
- Candidate hand renders were inspected at the original emulator resolution.
  AGAIN contact was inspected after correction. Final SO-SO was additionally
  captured from the installed APK at reduced resolution; source/renderer finger
  comparison passes at zero angular error. The five other inspected new action
  tracks are exactly unchanged by the final SO-SO edit. Other sampled comparisons
  pass at max 0.00000171 degrees, full action weight, no interfering action.
- Installed APK and exported APK hashes agree. Signature verifies against the
  existing debug certificate SHA256
  `5a315db9ca99c70f5f0c127dc8c6558e02d343e5b41d0bf4eee8bb256ce38a8c`.
  AppHear-only reinstall used the previously authorized keep-data option after a
  validated private backup. Preference files were byte-identical before app startup.
  No other application was removed. No crash-buffer exceptions were observed
  during the bounded checks; earlier ANRs remain a testing limitation.
- Compared against Update-1, every old resource/asset/native-library APK ZIP entry
  is unchanged except the two intended bundle files. All 242 original actions,
  geometry, skeleton and skin data are preserved. No unrelated source edits.
  Live camera/recognition/cloud-service functionality was not tested on the emulator;
  the existing JVM regression suite ran. Fake/private-service configuration is unchanged.

Export: `outputs/AppHear-Update-2.apk`, **843,100,553 bytes**.
SHA256: `65f8ea490d71525d1bd8566784ae78e88199fe2acf02b83dbe891ee065d0e35d`.
Android package/version remain `com.example.apphear`, versionName 1.0 / code 1.
Update-1 remains preserved separately. No Windows files were deleted.

Evidence in the existing review folder:
`batch2-normal-input-tests.json`, `batch2-installed-integrity.json`,
`batch2-final-skin-audit.json`, `batch2-final-conversion.json`,
`batch2-vocabulary-inventory.csv` (222 entries), `batch2-new-word-verification.csv`,
`batch2-six-pose-comparison.json`, `batch2-again-contact-pose-comparison.json`,
`batch2-installed-five-pose-comparison.json` and the single preferred overview
`batch2-review-overview.png`. Diagnostic drafts are not additional app versions.

**Six technically playable preview entries; zero new linguistically validated
signs or sentence translations.** Qualified ASL review must still check exact
handshape/thumb position, palm orientation, contact, repetition, timing, non-manual
features and comprehensibility. MUST is related to NEED and needs appropriate
imperative facial/body emphasis; no distinct-lexeme or complete-grammar claim is made.
