# Everyday ASL milestone — 2026-10-10

Scope: Text-to-Sign only, on `apphear/text-to-sign-redesign`. Checkpoint `ef79d58` preserves the previous grammar build. The existing clone is `outputs/AppHear-source`; no second clone or UI redesign is involved.

## Implemented behavior

`everyday_asl.json` contains ten **English meaning candidates** and explicit alternative English forms. Normalization handles case, punctuation, apostrophes and repeated whitespace. Contractions are accepted through declared alternatives, not a universal deletion rule. The four requested hot-today variants identify `everyday_hot_today`. Negated, hypothetical, past and different-time forms do not select that rule.

Existing reviewed whole-phrase rules retain priority and their existing evidence/asset/non-manual checks. There are currently zero such rules. The everyday inventory does not create an executable gloss sequence. HELLO and THANK YOU may use their existing complete clips as labeled unreviewed previews, following the user's earlier preview authorization. The other eight candidates stop output rather than signing isolated fragments of an incomplete sentence. Available constituent clips alone do not enable a phrase.

Missing-concept diagnostics inspect the **selected avatar catalog**, exclude letters and neutral poses, and never change avatars. `LETTER I` cannot stand in for personal-pronoun ME. The generic HELLO BEAUTIFUL individual-sign preview remains available on Original human, using the existing completion-event queue. Repeated input still uses the resident engine and existing cancellation tokens; this milestone makes no player changes.

The name introduction has a whole-word English prefix. It identifies the intent of `My name is Nicole`, but does not invent a name sign, mix rigs or automatically spell the name. A same-rig NAME clip, complete compatible alphabet, reviewed spelling transitions and licensed motion are required. The catalog's letters cannot be matched through a fictitious whole-name clip.

If either packaged meaning registry cannot be loaded, sentence playback fails closed; standalone dictionary word previews remain available. Invalid or ambiguous inventories are rejected before playback. All new behavior remains behind the existing ASL asset pilot flag.

## First-ten inventory

The following requirements describe concepts for acquisition/review, **not validated signing orders**. No phrase below has been reviewed by a qualified ASL signer. No motion assets were added, synthesized or retargeted.

| English meaning | Proposed expression / reference | Original human reusable clips | Missing data | Current output |
|---|---|---|---|---|
| Hello / Hi | HELLO lexical candidate; [lesson 2](https://www.lifeprint.com/asl101/lessons/lesson02.htm) | `hello` | AppHear motion and meaning review | Labeled complete-clip preview |
| How are you? | Social greeting versus concerned question require different facial interpretation; [lesson 2](https://www.lifeprint.com/asl101/lessons/lesson02.htm) | `how` | YOU; contextual facial motion/review | Unavailable |
| What is your name? | NAME question with appropriate indexing/facial grammar; [signing notes](https://www.lifeprint.com/asl101/topics/signingnotes.htm) | `your_yours` | NAME; reviewed question/non-manual sequence | Unavailable |
| My name is... | Possessive + name + actual fingerspelled name is a candidate for review; [signing notes](https://www.lifeprint.com/asl101/topics/signingnotes.htm) | `my_mine` | NAME; complete compatible spelling sequence/review | Unavailable |
| It is hot today | TODAY and weather-HOT are lexical candidates, full sentence order undetermined; [HOT](https://www.lifeprint.com/asl101/pages-signs/h/hot.htm) | `today`, `hot` | Full-meaning/order and facial review; lexical reference is not phrase validation | Unavailable despite both clips existing |
| It is raining | RAIN lexical candidate, full current-weather expression undetermined; [RAIN](https://www.lifeprint.com/asl101/pages-signs/r/rain.htm) | None | RAIN and phrase review | Unavailable |
| I am hungry | Speaker indexing + hunger is a candidate for review; [lesson 7](https://www.lifeprint.com/asl101/lessons/lesson07.htm) | `i_me` | HUNGRY; reviewed complete expression | Unavailable |
| I am tired | ME and TIRED lexical concepts, full phrase undetermined; [TIRED](https://www.lifeprint.com/asl101/pages-signs/t/tired.htm) | `i_me` | TIRED and phrase review | Unavailable |
| Thank you | THANK-YOU lexical candidate; [reference](https://www.lifeprint.com/asl101/pages-signs/t/thankyou.htm) | `thank_you` | AppHear motion and meaning review | Labeled complete-clip preview |
| Can you help me? | Directional help toward speaker requires question/request expression; [HELP](https://www.lifeprint.com/asl101/pages-signs/h/help.htm) | `help` only as an unreviewed lexical reference | Reviewed YOU-HELP-ME directional motion and facial grammar; generic HELP is insufficient | Unavailable |

All corresponding New-avatar expressions lack the required complete compatible clips. The system retains the user's selected avatar and reports unavailability. Original and New are different rigs and may not be mixed.

## Source and licensing boundary

Lifeprint is a reference link, not a licensed asset provider for this APK. Its [permission policy](https://www.lifeprint.com/asl101/pages-layout/permission.htm) requires specific permission for incorporating its materials into apps. No Lifeprint media, curriculum, SiGML or motion is copied, embedded or downloaded. English inputs and intent descriptions are independently structured from the user's requested vocabulary. Gloss and executable sign-ID fields remain empty in the candidate asset; reviewer-authored and legally usable signing data must enter the reviewed grammar registry separately.

The prior [vocabulary/grammar research](TextToSignGrammar.md) remains applicable: WLASL videos are not avatar motions and have computational-use restrictions; How2Sign is noncommercial reference data with English translations rather than automatic gloss; Signbank has noncommercial/share-alike and access/variant constraints; ASL-LEX reference-video reuse requires permission. None supplies a ready, licensed compatible avatar phrase in this milestone. Existing AppHear clips retain their prior unresolved source/linguistic provenance; technical availability does not settle that provenance.

## Changed source files and purpose

- `domain/texttoasl/EverydayAslExpression.kt`: meaning-candidate schema and ambiguity validation.
- `domain/texttoasl/ReviewedAslPhrase.kt`: attaches everyday inventory and registry-failure state to the existing grammar registry.
- `domain/texttoasl/AslTranslationPlanner.kt`: meaning lookup, complete-clip preview checks, missing-concept diagnostics and incomplete-phrase blocking.
- `ui/texttoasl/AndroidAslGrammarLoader.kt`: loads small offline candidate inventory alongside reviewed grammar.
- `assets/asl_animations/everyday_asl.json`: ten requested meanings and declared alternatives; no executable unverified glosses.
- JVM `EverydayAslExpressionTest.kt`, `OriginalWordBatchTest.kt`: normalization, actual assets, variant selection, missing data, avatar constraints and generic queue regression.
- Device `AslGrammarInstrumentedTest.kt`, `TextToAslSequenceInstrumentedTest.kt`: packaged-loader and unchanged-screen regression expectations.
- This document: limitations and review/import procedure.

No shared Android file, fragment/layout, navigation, setting, dependency, recognition component, database, model or existing avatar/animation payload is changed.

## Validation and expansion procedure

1. Obtain legally usable motion on the chosen rig, including the necessary directional and facial features. Record license, attribution and source. Reference videos alone are insufficient.
2. Have qualified Deaf ASL reviewers author/review the whole meaning, aliases, gloss, regional variant, signing order, question/negation/time and non-manual scopes. Resolve greeting-versus-concern ambiguity explicitly.
3. Check finger shape, wrist orientation, contact/location, motion path, timing, neutral transitions and facial/head/body behavior against that reviewed interpretation. Collect comprehensibility evidence; record reviewer/date and failures, not fabricated percentages.
4. Import reviewed clip metadata through `dictionary_extensions_asl.json` using the existing checksums, valid animation action, supported rig and review evidence checks. See [dictionary instructions](TextToSignDictionary.md).
5. Add a corresponding fully reviewed rule to `grammar_asl.json` with exact English forms, declared gloss/sign IDs and scoped embedded non-manual markers. Candidate records cannot bypass those gates. Add a separate entry for a different intent or meaning; do not universally strip English auxiliaries.
6. Run JVM tests, APK/test-APK build, real WebGL-device queue/cancellation tests and qualified-signer review. Update documented status only after each gate passes. Add the remaining requested expressions after this first milestone has actual reviewed playable assets.

Build using the existing `tools/android/build_working_baseline.ps1` with `-Configuration fake -OriginalWords` and tasks `testDebugUnitTest`, `assembleDebug`, `assembleDebugAndroidTest`, `-Pkotlin.compiler.execution.strategy=in-process`. No Gradle, Kotlin or SDK upgrade is required. The public fake configuration does not provision private account/Gemini/voice services. Actual build/device results are recorded in the generated output report, not inferred here.
