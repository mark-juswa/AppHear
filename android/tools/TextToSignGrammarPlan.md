# Text-to-Sign vocabulary and reviewed grammar plan

Checkpoint `660b473` preserves the previous phrase/avatar implementation. Work continues in the existing AppHear-source clone and branch; no renamed directory or additional clone is needed.

The user's implementation instructions resolve the architecture choices: ASL only, preserve existing UI and recognition, reuse the offline GLB player, retain labeled unreviewed previews, and never invent assets or translations. Repository `/architect` guidance was consulted. Its normal pre-build confirmation is superseded by the user's explicit phased implementation authorization; no new consequential architecture choice requires confirmation. No recognition stages, feature vectors, model contracts or train/serve parity components change. Progress/contract notes live here and in Text-to-Sign documentation because the user prohibits unrelated shared-document modifications.

## Terms and scope

- Candidate: reference-only vocabulary or a proposed English intent, no signing support implied.
- Mapped: a compatible asset is linked and integrity/action checks pass; rendering not yet established.
- Playable: actual playback evidence is recorded for the asset/version/device. Structural GLB checks alone do not qualify.
- Linguistically validated: qualified ASL review covers the exact meaning, variant, animation and grammatical/non-manual context, alongside playback evidence.
- Unsupported: necessary data is missing/rejected. This is separate from candidates in the research inventory.

## Implementation

1. Audit selected catalogs, aliases, manifests and GLB action identity; save per-entry evidence outside the APK.
2. Inspect official dataset conditions and accessible metadata; save 50 source-linked everyday lexical candidates and 20 English phrase review targets separately from supported content. Do not package research videos or entire datasets.
3. Add lifecycle/semantic/gloss/non-manual metadata and review records. Tighten imports so validation assertions without playback/reviewer evidence cannot enable translations.
4. Add conservative English intent/negation/time analysis. Do not remove copulas/articles, infer universal ASL order, translate idioms literally, or fabricate glosses.
5. Add a data-driven exact-English reviewed phrase registry containing explicitly ordered sign IDs/gloss and scoped embedded non-manual requirements. Registry activation is configurable and contained by the existing pilot flag. Ship zero enabled validated phrases unless evidence exists. Exact reviewed whole phrases win; future sequence composition remains separately reviewable.
6. Integrate the planner into the existing fragment. Fallback retains supported individual signs in English order and clearly reports unvalidated sentences. Block incomplete negated expressions rather than sign an opposite affirmative meaning. Meaning analysis is routing metadata, not a general semantic model.
7. Reuse existing completion/cancellation/profile/neutral logic. Non-manual requirements must be embedded in reviewed clips: this player does not synthesize facial grammar.
8. Run unit tests, real-player lifecycle tests, integrity checks, APK and test-APK builds. Attempt available Android device tests, report unavailable hardware honestly. No ASL linguistic accuracy claim without qualified review.

## Intended files

Existing Text-to-Sign metadata, extension loader, plan and fragment need small edits. New Text-to-Sign-only files provide intent analysis, reviewed grammar types/planner/loader and an empty registry. Associated unit/device tests and tools/docs provide audit, validation checklist and build evidence. The animation engine, avatar assets and all unrelated code remain unchanged unless new evidence exposes a queue defect.

## Gates and remaining data work

Engineering gate: normalization/longest aliases, existing HELLO BEAUTIFUL ordering, exact grammar rule selection, review/profile/asset/NMM rejection, negation preservation, cancellation and unchanged-source checks. Runtime rendering and real loading/performance require a working device/emulator. Linguistic gate: qualified Deaf ASL review of meaning, handshape, movement, grammar, variants, facial/head/body features and comprehension. Zero validated records is an honest valid initial state; it is not a completed grammar corpus or a 50-word release.
