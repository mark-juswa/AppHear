# Ten-word development preview batch — 2026-10-13

Scope: Text-to-Sign only, existing clone and `apphear/text-to-sign-redesign` branch.
Checkpoint `checkpoint/ten-word-expansion-20261012` at `8f353b4` preserves the tested
ME/YOU correction. No new clone, engine, avatar, dependency, UI or navigation change.

## Inventory and additions

The existing 203 word entries plus YOU, YOU ALL and the NAME variant are the baseline.
NAME shares the existing CALL/NAMED action; this is not another independently authored
motion. The baseline contains 205 lexical actions, 26 alphabet actions and one neutral
action. Existing aliases are alternative inputs, not extra sign motions. Unknown A–Z
words use fingerspelling, not lexical dictionary entries. Qualified ASL validations: 0.

Ten previously absent lexical entries are proposed in this batch:

| Word | Reference and intended form | Animation added | Review status |
|---|---|---|---|
| BEST | [ASLU BEST](https://www.lifeprint.com/asl101/pages-signs/b/best.htm), GOOD-derived emphasized upward comparison | `SIGN_BEST_HUMAN_RETARGETED_PREVIEW` | Requires ASL validation |
| BETTER | [ASLU BETTER](https://www.lifeprint.com/asl101/pages-signs/b/better.htm), smaller outward comparison | `SIGN_BETTER_HUMAN_RETARGETED_PREVIEW` | Requires ASL validation |
| DIVORCE | [ASLU DIVORCE](https://www.lifeprint.com/asl101/pages-signs/d/divorce.htm), D hands separate/rotate outward | `SIGN_DIVORCE_HUMAN_RETARGETED_PREVIEW` | Requires ASL validation |
| FROM | [ASLU FROM](https://www.lifeprint.com/asl101/pages-signs/f/from.htm), base index remains extended, dominant index hooks/pulls away | `SIGN_FROM_HUMAN_RETARGETED_PREVIEW` | Requires ASL validation |
| GRANDMA | [ASLU GRANDMA](https://www.lifeprint.com/asl101/pages-signs/g/grandma.htm), open five hand from chin forward | `SIGN_GRANDMA_HUMAN_RETARGETED_PREVIEW` | Requires ASL validation |
| GRANDPA | [ASLU GRANDPA](https://www.lifeprint.com/asl101/pages-signs/g/grandpa.htm), open five hand from forehead forward | `SIGN_GRANDPA_HUMAN_RETARGETED_PREVIEW` | Requires ASL validation |
| HERE | [ASLU HERE](https://www.lifeprint.com/asl101/pages-signs/h/here.htm), relaxed palms up, horizontal circles near waist | `SIGN_HERE_HUMAN_RETARGETED_PREVIEW` | Requires ASL validation |
| PARENTS | [ASLU PARENTS](https://www.lifeprint.com/asl101/pages-signs/p/parents.htm), successive mother/father locations | `SIGN_PARENTS_HUMAN_RETARGETED_PREVIEW` | Requires ASL validation |
| PREFER | [ASLU PREFER](https://www.lifeprint.com/asl101/pages-signs/p/prefer.htm), middle finger taps chin, not lips | `SIGN_PREFER_HUMAN_RETARGETED_PREVIEW` | Requires ASL validation |
| SINGLE | [ASLU SINGLE](https://www.lifeprint.com/asl101/pages-signs/s/single.htm), index-circle variant; meaning depends on context | `SIGN_SINGLE_HUMAN_RETARGETED_PREVIEW` | Requires ASL validation |

GRANDMOTHER, GRANDFATHER and FAVORITE are additional input alternatives; they are not
counted as three more lexical animations. No complete sentence translation or question
non-manual grammar is validated by these word additions. FINE was excluded: its source
contains changing letter-like handshapes; it must not be counted as a new lexical FINE.

## Conversion and corrections

Original source GLBs remain untouched in `app/src/main/assets/asl_animations`. Their
actual action names, hashes and reference links are recorded in the bundle manifest.
Existing AppHear motion/rig redistribution provenance remains unresolved. Local
development previews establish no new redistribution rights. No reference video,
image, dataset or third-party SiGML is copied into the APK.

`expand-text-to-sign-everyday.py` accepts only the pinned pre-expansion bundle and writes
a separate candidate. Anatomical segment/palm frames convert source arm, wrist and
finger rotations. Reference-guided corrective keyframes are authored on the resident
rig for the new clips: independent finger curl axes, appropriate open/index/hooked
forms, contact locations, comparison movement, horizontal HERE circles, PREFER taps
and neutral entry/exit. These are engineering previews, not signer-validated motion.
Specific thumbnail/handshape, contact, repetition and timing still require review.

The first raw conversion missed some contact locations and produced unsuitable poses.
Early face-contact candidates placed the hand heel behind its thumb contact. The
corrective five-hand palm faces across the signer, thumb toward chin/forehead, rather
than putting the wrist inside the face. Position-space entry/exit is solved with
fixed-length two-bone IK; axial rotation is distributed to the forearm to preserve the
world hand frame without excessive wrist twist. No generic collision rule or global
finger/shoulder lock is introduced. All 232 pre-existing actions, their binary data,
geometry, bind pose, skin weights and hierarchy must remain identical.

The existing catalog automatically loads new manifest entries. The existing single
avatar/completion-driven queue, automatic fingerspelling, cancellation, grammar
limitations and unreviewed-preview notices remain in place. No runtime player change.

## Build and verification

Final bundle SHA256: `11b50d333dae036132515c535bea9b9adbf0d42f43be901bb7c4b36b3bb1e43c`.
The calibrated chin/forehead markers are 1.51/1.70 metres on this rig. The final
PREFER refinement changes only three arm/wrist channels, preserves the finger
channels and hand orientation, and moves contact from the throat to the chin.
The MOTHER donor experiment was rejected and is not shipped.

The final Gradle build completed successfully (4m24s): `testDebugUnitTest`,
`assembleDebug`, `assembleDebugAndroidTest`. Actual JUnit XML totals: 250 tests,
zero failures/errors. The final APK signature verifies; versionName 1.0,
versionCode 1 (unchanged). APK SHA256:
`2b0aa9419e6233c7ec9d2d2979cd1ee1e4c573d732aea4e288993ca40db91cca`.
The emulator-installed base APK has the same hash. A private data backup was
validated before the previously authorized AppHear-only keep-data reinstall.
The preference file inventory was retained. No other application was removed.

Node controller tests pass: completion, cancellation, missing/ambiguous action
rejection and one resident model across 288 word/letter callbacks. These are mock
controller tests, not proof of rendered motion. All old resource, asset and native
library ZIP entries match the previous ME/YOU APK except the two intended bundle
files. All 232 original animation descriptions and binary data are preserved.
Unrelated recognition/UI unit tests ran in the full suite; live camera recognition,
account/Gemini/voice services and physical-phone behavior were not exercised.
The APK uses the existing public fake-service build configuration.

Candidate renders and sampled surface checks are development evidence. A paused pose
does not demonstrate a full sign's movement, timing or comprehensibility. Front torso/
face projection is not full closed-mesh collision detection. Qualified ASL review and
physical-phone testing are separate and have not occurred in this batch.

The installed Android 16 Medium Phone emulator passed the instrumentation test
(268.826s): 63 normal-input cases plus NICOLE-to-ANNA cancellation. This includes
all ten new words, mixed HELLO GRANDMA NICOLE, NAME/NICOLE/ANNA/JAZZ/ACTION, existing
LOVE/HELP/ME/YOU and single-letter inputs. Standalone I uses the pronoun entry;
the separate direct alphabet test explicitly selects the letter I action.

Actual installed-asset developer pose captures cover all ten words and all 26
letters. Source/renderer finger quaternion comparison passes for all 36 samples:
maximum error 0.00000171 degrees, action weight 1, no interfering action. These
are sampled-pose checks, not qualified recognition tests or full-motion accuracy
certification. J/Z motion channels are byte-identical to the previous working
bundle; their playback completed in the input tests. No AppHear crash-buffer
exceptions were observed during this test window. The emulator's System UI had an
ANR after boot; choosing Wait allowed the app to operate. This is not attributed
to AppHear without evidence.

Review evidence resides in the existing `outputs/AppHear-Word-Finger-Fix-Review`
folder: `everyday-ten-normal-input-tests.json`, `everyday-ten-installed-integrity.json`,
`everyday-ten-final-pose-comparison.json`, `everyday-alphabet-final-pose-comparison.json`,
`everyday-ten-chin-reviewed-skin-audit.json`, `everyday-ten-vocabulary-inventory.csv`,
and `everyday-ten-body-everyday-ten-final-overview.png`. Individual captures were
already created before the user requested fewer screenshots. No further individual
captures are required. A compact overview is the preferred deliverable.

Final export: `outputs/AppHear-Update-1.apk` (843,016,470 bytes), SHA256 above.
Previous distinct tested build retained: `outputs/AppHear-ME-YOU-Fix-Test.apk`
(842,884,815 bytes), SHA256
`08fc66b848d5f91afb9923c5eef407379deb890dba8bbad6e3640eaf0432c55b`.
Both retain Android version 1.0/code 1; their build contents/hashes distinguish
the development updates. Renaming the exported file does not change package identity.
No Windows files have been removed. Prior "ask first" cleanup instructions remain
in force; obsolete APKs require approval of an exact removal list.

No qualified linguistic validation has occurred. Body-surface projection is only a geometric proxy and may leave
small intersections outside the sampled surface; it is not full collision proof.

## Files changed in this batch

- `app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb`: append ten new corrected preview actions after visual checks.
- Adjacent `fingerspelling-avatar.json`: dictionary entries, provenance, references, meaning and expansion audit.
- `app/src/main/java/com/example/apphear/domain/texttoasl/AslFingerspellingBundle.kt`: checksum pin only.
- `app/src/test/java/com/example/apphear/AslVocabularyExpansionTest.kt`: actual new-word selection, mixed spelling and review boundaries.
- `app/src/test/java/com/example/apphear/AslFingerspellingFallbackTest.kt`: expected bundle action count.
- `app/src/androidTest/java/com/example/apphear/AslFingerspellingPlaybackInstrumentedTest.kt`: new-word, mixed-input and individual A–Z cases.
- `tools/test-text-to-sign-resident.cjs`: expected action count; existing all-action queue tests.
- `tools/expand-text-to-sign-everyday.py`: offline candidate conversion/correction, no runtime dependency.
- `tools/audit-text-to-sign-everyday.py`: independent scope, quaternion and sampled skin checks.
- `tools/correct-everyday-prefer-forearm.py`: PREFER-only mesh-aware elbow solve and chin calibration; no finger-channel changes.
- This report.

## Reproduce and future review

Recover the bundle and adjacent manifest from the checkpoint without checking out/resetting
the active branch. Run `expand-text-to-sign-everyday.py <checkpoint.glb> <candidate.glb>
<candidate-report.json>`, then `correct-everyday-prefer-forearm.py <candidate.glb>
<reviewed.glb> <refinement-report.json>`, then
`audit-text-to-sign-everyday.py <checkpoint.glb> <reviewed.glb> <skin-report.json>`.
Use existing NumPy/Pillow development runtime.
Inspect the Android render and actual motion before applying the candidate and checksum.
Build through the existing `build_working_baseline.ps1` OriginalWords configuration.

For ASL review, assess meaning/variant, dominance, all fingers and thumb contact,
palm orientation, face/body contact, direction/repetitions, timing, entry/exit and
comprehensibility with qualified Deaf ASL signers. Record reviewers, dates and observed
issues. Never change `MAPPED` to linguistically validated based on these software checks.
