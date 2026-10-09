# Single resident avatar and incremental vocabulary — 2026-10-10

Scope: Text-to-Sign and its avatar only. Existing development clone/branch retained; checkpoint `91b86fa` precedes this work. No new clone, push, navigation, layout, recognition, model, camera, dependency or database changes.

## What changed

The sole active character is the existing **Original human** (Wolf3D, 69 nodes), not the legacy 54-node robot. It has 203 existing sign motions, including HELLO and BEAUTIFUL. The alternate FemaleASL character has a different skeleton and less compatible vocabulary. Saved avatar preferences remain stored, and the existing settings screen remains unchanged; Text-to-Sign now deliberately ignores alternate character selection. Returning from settings no longer destroys/recreates its engine.

The fragment requires the existing OriginalWords/pilot build configuration. A configuration without those assets fails visibly; it cannot silently start the legacy engine. The controller refuses assets from any other profile for playback/preload, including legacy and FemaleASL. No old files are deleted.

All 203 source GLBs had identical skeleton/scene definitions and identical geometry, textures and bind-pose data. `bundle-text-to-sign-avatar.py` copies their original animation data into **one resident GLB**. It does not generate poses, retarget fingers, change signing order or declare the signs accurate. The output is 19,998,976 bytes, with 203 unique named animations. Every active sign and neutral pose points to that URL. The existing player keeps the model loaded and changes the named animation; one visible avatar remains throughout requests. Existing cancellation tokens, actual completion callbacks, repeat controls and neutral frame are retained.

The original individual clips and both older character systems remain packaged for review and rollback. Packaging adds approximately 20 MB; it does not reduce total APK size in this milestone. Memory and loading-time improvements require actual mobile measurement. Bundling keeps previously accepted motion/provenance status unchanged.

The safe new input mapping **GOODBYE → existing BYE** uses the existing clip and reference link; no duplicate/new motion is created. A separately governed alias manifest checks the existing source path and SHA256 and retains unreviewed status. It cannot add missing signs, upgrade validation, substitute letters/poses or overwrite conflicting meanings. Reviewed new motions still use the existing dictionary-extension review gates.

## NAME investigation

All 316 source GLBs, including shared animation bundles, were inspected. There is no standalone NAME action on either existing human rig. The four files containing name phrases (`hey-name-you`, `my-name`, `your-dad-name`, `your-mom-name-what`) use the 54-node legacy rig. They are complete phrase animations, not a reusable standalone human NAME clip. The human `call__to_call_someone_s_name` is a different lexical label and is not assigned to NAME. Typing NAME continues to report it unsupported and retains the resident human avatar.

[Lifeprint's NAME reference](https://www.lifeprint.com/asl101/pages-signs/n/name.htm) describes a two-handed H handshape and explains movement variation and question facial grammar. For a future motion review, check both hands' finger extension, thumb position, crossed hand orientation/contact location, dominance, contact repetitions, movement timing, neutral return and the distinction between lexical NAME and name-question non-manual features. A NAME lexical motion alone would not automatically validate “What is your name?”

An accessible [Kozha SiGML NAME candidate](https://github.com/zhan-a/Kozha/blob/main/data/American_SL_ASL.sigml) was inspected. Its [metadata](https://github.com/zhan-a/Kozha/blob/main/data/American_SL_ASL.sigml.meta.json) declares CC BY-NC 4.0, review required, and zero Deaf-native reviewers. This is an upstream rendering candidate, not AppHear-compatible or qualified-reviewed motion. It would require a CWASA engine/character, or verified retargeting onto the resident rig, and independent sign review. It was not imported or enabled. Upstream provider claims do not establish AppHear playback or sign accuracy.

[CWASA conditions](https://vh.cmp.uea.ac.uk/index.php/CWASA_Conditions_of_Use) permit developing pages with attribution/share-alike conditions but require the underlying engine to remain unmodified under terms equivalent to attribution/no-derivatives. CWASA renders SiGML, while the current player renders GLB. Introducing it as an automatic NAME fallback would switch characters and conflict with preserving current working clips. No CWASA fallback or external network dependency is introduced.

[SignAvatars](https://github.com/ZhengdiYu/SignAvatars) is another possible acquisition route: noncommercial research access is requested through its form, with separate source-video/model/licensing constraints and SMPL-X data requiring conversion/retargeting. No access request, contact message or restricted download was made. No readily usable, licensed, qualified-reviewed NAME GLB for the current rig was obtained. Acquisition/manual authoring plus qualified ASL review remains necessary; random procedural motion is not a substitute.

## Batch progress

`audit-text-to-sign-batches.py --output-dir <directory>` checks the frozen source manifest, payload hashes, named actions and aliases. It emits CSV/JSON for all 77 targets. These are existing unreviewed clip mappings, not linguistically validated or current-device-tested signing counts.

| Batch | Targets | Existing compatible preview mappings | Missing motions |
|---|---:|---:|---|
| Introductions | 16 | 11 | NAME, YOU, NICE, DEAF, HEARING |
| Essential communication | 16 | 13 | UNDERSTAND, REPEAT, STOP |
| Feelings | 14 | 10 | TIRED, HUNGRY, THIRSTY, OKAY |
| Activities | 15 | 11 | STUDY, LEARN, STAND, FOOD |
| Time/weather | 16 | 9 | NOW, LATER, NIGHT, WEATHER, RAIN, SUNNY, WIND |

Totals: **54 mapped targets, 23 missing compatible animations, one added alternative input, zero new sign motions, zero linguistically verified signs.** STAND's neutral-pose alias is deliberately excluded from vocabulary counts; letters do not satisfy words. LIKE currently labels affection, which must be distinguished from food preference during meaning review. A file/name/hash pass does not establish correct hands, facial expression or comprehensibility. Android-rendered playable counts for this run remain zero unless a device test actually completes.

No batch was falsely completed. Existing clips are retained rather than duplicated. Missing resources are recorded for all batches; the next acquisition batch is NAME, YOU, NICE, DEAF and HEARING, authored/licensed on the resident rig and reviewed in context. NICE TO MEET YOU and name questions also require whole-phrase/non-manual review. Generic HELLO BEAUTIFUL and HELLO BEAUTIFUL GOODBYE can use individual-sign sequence playback; existing reviewed-phrase and incomplete-everyday-expression rules remain unchanged.

## Add a future sign

1. Obtain explicit legally usable animation data or commission/reference-based original authoring. Record license, attribution, language, sense/variant and provenance. Do not reuse an unrelated clip.
2. Have qualified Deaf ASL reviewers evaluate fingers, orientation, contact/location, direction, timing, transitions and needed face/head/body behavior. Record reviewer/date and actual comprehension evidence.
3. Test the same-rig clip on Android. Import through the existing reviewed dictionary extension, not the preview-alias manifest. An extension on another rig is rejected by the active engine.
4. Extend the resident packer under a new version/hash when a compatible sign is approved; preserve existing motion bytes and validate the new bundle. The current bundle requires its exact 203-motion source contract. Reviewed future extensions must not be silently relabeled as one of these 203 motions.
5. Add reviewed whole-phrase records only after their meaning, gloss, order and scoped non-manual motion are validated. See [grammar workflow](TextToSignGrammar.md) and [dictionary workflow](TextToSignDictionary.md).

Existing source-motion redistribution provenance remains unresolved. This patch adds no externally sourced motion and no new linguistic certification. Reference links do not license reference media; no Lifeprint video/curriculum was bundled.

## Verification boundary

JVM tests verify source hashes, all 203 bundled motion target/timing/value bytes, catalog consistency, single profile, alias identity/conflicts and previous grammar/queue regressions. Instrumentation tests are updated to start with a saved New preference and require the Original human sequence, same WebView, GOODBYE completion and unsupported NAME retention. They require a real working Android WebGL device. The emitted final report records actual build/signature/package comparison, emulator attempts and tests run. It must not claim visual or linguistic validation from software tests.
