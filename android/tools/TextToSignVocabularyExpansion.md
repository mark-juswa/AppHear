# NAME / YOU vocabulary expansion — 2026-10-10

Only Text-to-Sign changes. Same resident human, same completion-driven player,
same automatic A–Z fallback, same UI/navigation/recognition configuration.
Checkpoint: `checkpoint/name-you-vocabulary-20261010` at `d996e61`.

## Enabled inputs and evidence

| Input | Implementation | Reference | Status |
|---|---|---|---|
| NAME | New dictionary entry sharing existing human `SIGN_CALL__TO_CALL_SOMEONE_S_NAME` action | [ASLU NAME](https://www.lifeprint.com/asl101/pages-signs/n/name.htm) documents NAME/NAMED movement variation | Unreviewed native-form preview; not a newly authored/validated standalone animation |
| YOU | Existing `you.glb` motion retargeted from the 54-node source to resident human anatomical frames | [ASLU YOU](https://www.lifeprint.com/asl101/pages-signs/y/you.htm) | Unreviewed retargeted preview |
| YOU ALL / ALL OF YOU | Existing plural pointing/sweep clip retargeted to same human | ASLU YOU plural reference above | Unreviewed retargeted preview; one plural-pronoun expression, not a validated sentence |
| MOM / MUM | Alternatives for existing MOTHER motion | [ASLU MOM](https://www.lifeprint.com/asl101/pages-signs/m/mom.htm) | Existing unreviewed motion |
| DAD | Alternative for existing FATHER motion | [ASLU DAD](https://www.lifeprint.com/asl101/pages-signs/d/dad.htm) | Existing unreviewed motion |
| OKAY | Alternative spelling for existing OK motion | [ASLU OKAY](https://www.lifeprint.com/asl101/pages-signs/o/okay.htm) | Existing unreviewed motion |

Three dictionary entries, **two added motion actions**, four English alternative
forms. Do not count these as seven newly created ASL animations. There are zero
qualified-signer validations and zero newly validated sentence translations.
NAME/NAMED contact repetitions, finger contact, thumb/palm orientation and meaning
need qualified review. NAME in a question does not supply facial question grammar.
Personal names after the existing introduction prefixes still fingerspell.

Source motions and rig already belong to the local AppHear checkout. Their existing
license/provenance remains unresolved; this task establishes no redistribution
rights. Reference links inform review; no reference images/videos, SiGML or third-party
dataset payloads were imported. The separate authored NAME candidate stays quarantined.
AGAIN was investigated but its two-hand contact remains unresolved; it is not registered
or packaged. It continues using the existing spelling fallback.

## Architecture and protection

`AslVocabularyExpansion` validates IDs, aliases, motion names, duration, provenance
fields, permitted avatar and dictionary collisions. The NAME variant must match
the existing accepted native motion. The loader exposes additions only in the
existing enabled human/alphabet preview path, after verifying the bundle hash.
Missing named animations still fail through the existing player; no legacy model
or network fallback is introduced. No reviewed-entry acceptance gate is weakened.

The offline conversion calibrates every arm/hand/finger segment against each rig's
bind axes and palm frame. Terminal source joints without tip bones use preceding
segment directions, matching the prior alphabet calibration technique. Bone-space
quaternions are reconstructed in hierarchy order with hemisphere continuity.
Target geometry, bone lengths, skin weights and the full original binary motion
data remain untouched. Neutral endpoints are added only to the new clips.

Existing 230 animations—including all alphabet poses, LOVE repairs and neutral
posture—are unchanged. The player JS is unchanged, preserving the mixer-clock
regression fix, controlled fades, cancellation and completion callbacks. Two
new actions are appended to the same GLB; total named actions: 232.

## Actual checks

- Android `testDebugUnitTest`, `assembleDebug`, `assembleDebugAndroidTest`: success.
- 241 unit tests passed, zero failures/errors/skips (four new vocabulary tests).
- Node player and resident tests passed. Resident test confirms real new action
  names in the bundle; its controller checks use a mock viewer, not Android rendering.
- Source/frame and CPU skinned-mesh inspection: YOU/YOU ALL and existing NAME form.
  61 poses per new dictionary entry checked for finite/normalized rotation data.
  CPU renders are not phone screenshots or qualified linguistic validation.
- APK comparison: 1,532 asset/resource paths match; only alias JSON, resident
  fingerspelling GLB and its JSON manifest differ. Existing animation descriptions
  and original binary payload prefix are identical.
- New APK signature verification passed. Same fake service configuration as the
  preceding test APK; no account/voice/Gemini credentials provisioned here.
- No device was connected (`adb devices` empty). Updated instrumentation compiles
  but was not run. No emulator or physical-phone playback claimed.

## Changed repository files

- `app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb`
- `app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.json`
- `app/src/main/assets/asl_animations/existing_aliases_asl.json`
- `app/src/main/java/com/example/apphear/domain/texttoasl/AslFingerspellingBundle.kt`
- `app/src/main/java/com/example/apphear/domain/texttoasl/AslVocabularyExpansion.kt`
- `app/src/main/java/com/example/apphear/ui/texttoasl/AndroidAssetAslCatalogLoader.kt`
- `app/src/test/java/com/example/apphear/AslFingerspellingFallbackTest.kt`
- `app/src/test/java/com/example/apphear/AslVocabularyExpansionTest.kt`
- `app/src/androidTest/java/com/example/apphear/AslFingerspellingPlaybackInstrumentedTest.kt`
- `tools/expand-text-to-sign-you.py`
- `tools/audit-text-to-sign-vocabulary.py`
- `tools/test-text-to-sign-resident.cjs`
- this document.

No application layout, theme, navigation, Sign-to-Text, camera, recognition model,
database, Gradle/SDK dependency or normal player behavior was modified.

## Reproduce and extend

From the Android directory, run the existing Node player/resident tests. From the
workspace, `outputs/Build-AppHear-Vocabulary-Expansion.ps1` builds the application
and tests and verifies its APK signature; it refuses to overwrite an exported APK.
`audit-text-to-sign-vocabulary.py <previous-APK> <new-APK> <report-json>` verifies
unchanged resources and original animations. The current unit tests read the bundled
manifest and source assets, so no research dataset or internet is needed.

For further signs: obtain legitimate source motion and license evidence, convert
to this rig offline, inspect full hands/body/contact, keep source animations intact,
append a uniquely named action and provenance entry, update the bundle hash, and
run lookup/collision/asset/playback checks. Never substitute unrelated gestures.
Only add linguistic validation after actual qualified review, including necessary
non-manual features and intended meaning. Reviewed phrases continue using their
separate gated grammar registry. English word sequences remain labeled previews.
