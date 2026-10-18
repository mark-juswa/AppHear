# Reviewed ASL phrases and vocabulary workflow

Current avatar continuation: [single resident human avatar and vocabulary batches](TextToSignSingleAvatar.md). Alternate stored character choices are retained but no longer change active Text-to-Sign playback. The existing 203 motions now share one resident GLB; no new sign correctness is asserted.

The 2026-10-10 [everyday expression milestone](TextToSignEveryday.md) adds ten small offline English meaning records. These contain no executable gloss or motion sequences. Known incomplete everyday expressions now stop signing instead of using the generic individual-word preview; other dictionary sequences retain the behavior described below. The larger research inventories and datasets remain outside the APK.

The installed player remains the existing offline GLB/model-viewer engine. ASL is the target; FSL data is rejected. The current assets have no recorded qualified ASL review, so the shipped reviewed phrase registry is empty. This is a safe, data-driven grammar integration, not a general English-to-ASL translator or a completed new signing corpus.

## Pipeline and scope

Existing typed/speech text → shared Text-to-Sign normalization → conservative English intent/negation/time analysis → exact reviewed English meaning lookup → declared ASL gloss/asset order and scoped embedded non-manual requirements → compatible animation queue → existing completion callbacks and neutral pose.

The original longest word/phrase matcher remains the fallback. It recognizes existing HELLO/HI/HEY aliases and HELLO BEAUTIFUL without assuming that the sequence is a correct ASL sentence. Whole reviewed English phrases take priority over individual signs. Unreviewed English sentence previews retain supported tokens in English order and explicitly report missing words and unvalidated sentence status. No copulas/articles or time/negation words are silently deleted. Losing a negation token stops the preview rather than show an affirmative fragment. Known idioms listed in the registry are blocked from literal playback; this finite list is not general idiom detection.

Intent analysis covers greetings, expressions, simple statements, WH and yes/no questions, and common request patterns. It is a conservative routing heuristic, not full meaning understanding. Ambiguity, conditionals, spatial agreement, classifier constructions, inflection and arbitrary sentence translation remain unsupported. Reviewer-authored exact mappings can encode meaningful order, but they do not generalize automatically to other English inputs. No universal ASL grammar rules were invented.

The existing `ASL_ASSET_PILOT_ENABLED` flag contains this integration; flag-off uses the existing legacy planner. `grammar_asl.json.enabled` disables reviewed phrase selection while retaining preview notices and meaning guards. No BuildConfig, dependency, SDK or layout changes were needed. Catalog and grammar file loading remain off the main thread.

## Five statuses and evidence

| Status | Requirement and meaning |
| --- | --- |
| CANDIDATE | Reference discovery or English review target only; no motion/playback/validation implied |
| MAPPED | A compatible candidate asset is linked and structural/hash/action checks pass |
| PLAYABLE | Actual engine playback evidence records the exact asset/version/device |
| LINGUISTICALLY_VALIDATED | Qualified ASL review covers exact meaning/variant/motion/non-manual features, with playback and source/license records |
| UNSUPPORTED | Required motion/description is absent or rejected |

Built-in metadata defaults to MAPPED/UNREVIEWED. It is not automatically promoted after a file hash check. Current on-device playback has not been performed in this session. Historical build/user observations do not qualify every clip as playable or ASL-validated. The separate audit reports file-valid motions, playback evidence, and linguistic validation separately. Candidate word/phrase inventories and raw research metadata are outside the APK.

The extension manifest uses schema 2 (see `TextToSignDictionary.md`). New imports require a qualified review, real playback evidence, gloss and specific meaning alongside source/license records and verified GLB identity. Candidate/mapped/playable additions belong in the review inventory until approved. Software checks that records are complete; it cannot itself establish the reviewer's proficiency, ownership rights or truth of a declared review.

## Reviewed phrase registry

`app/src/main/assets/asl_animations/grammar_asl.json` contains `schemaVersion: 1`, `language: "ASL"`, `enabled`, `phrases` and `blockedLiteralExpressions`. The current `phrases` list is empty. Add entries only after the checklist below is completed; do not populate it with guessed glosses for the test sentences.

Each phrase has `id`, `language`, `english` (exact alternative English forms), `meaning`, `intent` (the routing intent), `gloss` (reviewed ordered labels), `signIds` (ordered existing dictionary IDs), `status: "LINGUISTICALLY_VALIDATED"`, `negated`, `timeWords`, `isQuestion`, `nonManualMarkers`, and `review`.

Each `review` record requires `reviewer`, `reviewedOn` (real calendar date), `sources`, `license`, `meaningEvidence`, `nonManualEvidence` and `playbackEvidence`. The runtime requires all referenced sign assets to be ASL-validated, non-pose and on one human avatar profile. Ordered gloss must equal the concatenated reviewed gloss of those assets; a complete phrase clip may carry multiple labels. Duplicate IDs or normalized English meanings disable the malformed registry rather than pick a random rule.

A `nonManualMarkers` item contains `marker`, `fromSign` and `throughSign` (zero-based inclusive queue indices). Every clip in that scope must declare that marker in its reviewed `embeddedNonManualMarkers`. Question translations require non-empty declared non-manual coverage and review. Invalid scopes, missing markers, incompatible/missing assets, mismatched time/negation/question/intent or incomplete reviews reject the phrase and retain clearly labeled dictionary preview behavior.

The player can display bone/morph tracks encoded in GLB, but does not synthesize eyebrows/head movements from grammar metadata. Current catalog audit found no morph-weight animation channels in the selected assets; bone tracks alone do not establish required facial grammar. None has reviewed non-manual markers. Do not claim WH or yes/no question signing is complete. Requiring metadata coverage is an evidence gate, not automated visual proof of facial/head/body motion.

## Review and import checklist

1. Identify the English sense/intent, context, negation, temporal reference, idiomatic meaning and acceptable alternatives. Record ambiguities rather than assign unrelated signs.
2. Link authoritative lexical/continuous references, exact IDs/variant/region, and source attribution. A dataset gloss or English subtitle is not a complete ASL translation.
3. Confirm asset and reference rights allow the intended distribution and derivatives; obtain extra permissions when needed. Preserve license, attribution and evidence. Do not bundle research datasets.
4. Have qualified ASL signers review the sign/phrase formulation, gloss order, grammatical scope and required non-manual features. Record qualifications, review date, evidence and requested corrections.
5. Obtain or create a legitimately licensed compatible motion asset from qualified signing reference, then inspect handshape, wrist/palm orientation, location, path, timing, body/head/face motion and sense/variant. Do not guess missing finger data or retarget rigs without validation.
6. Validate GLB identity, expected action, duration, secure path, selected rig/appearance, normalized aliases and ID uniqueness. Use an explicit new asset/version rather than silently overwrite a reviewed clip.
7. Play it through the actual target engine and Android screen. Record device/WebView version, asset hash, loading/response times, full completion, neutral return, Repeat and rapid cancellation. Test without networking and monitor memory/frame stability.
8. Ask qualified Deaf ASL reviewers to judge the rendered output without relying only on the English prompt. Record comprehensibility, semantic/grammar errors, regional variation, non-manual coverage and remediation; do not invent percentages.
9. Promote the record only to the evidence-backed status. Add exact phrase mappings only once all their assets and grammatical context are validated. Run import/grammar/queue tests and unrelated host regressions before a scoped APK build.
10. Preserve the previous APK/commit for rollback. Use local commits on the existing development branch; do not push or change unrelated app source.

## Resource research and limitations

- [WLASL official repository](https://github.com/dxli94/WLASL) supplies word-class/video-reference metadata and variants, not GLB/SiGML. Its [C-UDA](https://github.com/dxli94/WLASL/blob/master/start_kit/C-UDA-1.0.pdf) limits data to computational use and has attribution/downstream-agreement conditions; the repository also states academic/noncommercial use. These terms are not blanket rights to redistribute source-site videos as an app dictionary.
- [How2Sign](https://how2sign.github.io/) supplies continuous video and English alignment metadata under CC BY-NC 4.0/research-purpose conditions. English translations are not word-for-word ASL gloss. The accessible test annotations provide review locators; substring matches do not prove equivalent ASL expression. Original How2 data has separate redistribution restrictions.
- [ASL Signbank conditions](https://aslsignbank.com/about/conditions/) and [copyright](https://aslsignbank.com/about/copyright/) specify CC BY-NC-SA, attribution, direct video links and exclusion of draft media from disseminated work. The old Yale URL often fails; the site's [FAQ](https://aslsignbank.com/about/FAQs/) documents the current domain and ECV vocabulary. It documents variation and annotation ID glosses; it is not a translation authority. The public ECV was inspected without login or access-control bypass.
- [ASL-LEX download terms](https://asl-lex.org/download.html) distinguish CC BY-NC database/visualization from reference videos, which need explicit permission for other use. Its lexical/phonological metadata helps review; no avatar data is provided. The linked OSF data download was inaccessible (403), so no individual ASL-LEX entry cross-reference was invented.

No research video was downloaded, converted or bundled. WLASL metadata, How2Sign public test CSV and Signbank ECV were inspected as local research inputs, with hashes recorded in the separate inventory. The 50 word targets lack existing selected-avatar aliases/assets; the 20 phrase targets are English meaning briefs without ASL gloss or activated motion. Additional asset creation, legal clearance and qualified review remain real separate work.

## Testing and rebuild

Use the existing `tools/android/build_working_baseline.ps1 -Configuration fake -OriginalWords` flags with tasks `testDebugUnitTest`, `assembleDebug`, `assembleDebugAndroidTest`. The workspace export helper is `outputs/Build-AppHear-ASLGrammar.ps1`. The public fake build leaves private connected services unconfigured; an existing private configuration is needed for those services, unchanged by this work.

`AslGrammarPlannerTest` uses explicitly synthetic review records to test gates/order/scope; its fixtures are not animations and do not validate any real sign. `OriginalWordBatchTest` runs all 15 user expressions against actual selected dictionary data and checks asset presence without claiming sentence validity. `AslGrammarInstrumentedTest` checks packaged wiring, and the existing screen test exercises HELLO BEAUTIFUL, an unvalidated question and blocked negation. Run those on a working emulator/test phone with the same feature flags. Existing player completion/cancellation tests remain in `tools/test-text-to-sign-player.cjs`.

Run `python android/tools/audit-text-to-sign.py --output <audit-folder> --research-dir <metadata-folder>` from the repository; omit the research argument for a bundled-motion audit only. The research folder must contain explicitly obtained `WLASL_v0.3.json`, `how2sign_realigned_test.csv` and `asl.ecv`. The script never downloads data or activates entries. See the workspace final report for actual results rather than assuming these instructions were run on a physical device.
