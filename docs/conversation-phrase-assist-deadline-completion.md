# Conversation-Aware Phrase Assistance — deadline advisory completion

Date: 2026-09-30; presentation corrected 2026-10-01. Status: **IMPLEMENTED FOR INTERNAL DEBUG USE; RELEASE REMAINS OFF**.

## Starting state and decision

The worktree was clean on feature/conversation-phrase-assist-mvp at 240b674963bfd0a0125fd36bd5429c528bc10e3b. The protected baseline ref still resolved to 76d93cecd85bf9f76064d320aa4a5791b5f0704a. The Stage 3 pilot showed little first-pass Top-5 recovery opportunity, so this milestone exposes prediction and matcher-supported text separately while preserving raw recognition and Hear/TTS as authoritative. It does not claim an accuracy gain.

## Data flow and visible behavior

A completed typed or speech Hearing message still enters ConversationPhraseAssist.recordHearingMessage from TextToAslFragment. The existing asynchronous provider generates validated ReplyCandidates once for that turn and caches them silently for the signer's response. Text-to-ASL shows no predicted replies. A small immutable PhraseAssistUiState retains the current turn and accepted naturalText candidates internally; the existing turn-ID guard rejects late older responses. Failed, timed-out, missing-key, malformed, or empty provider results leave the contextual interpretation absent.

The existing recognizer continues to commit Top-1 to SentenceBuilder and render the raw sentence. At Hear, the existing call speaks that raw sentence and evaluates the read-only evidence snapshot. Only a ShadowEvaluation with reason MATCH and a naturalText/concept sequence that appears in its cached candidates can populate the separate “Context-supported · advisory” line. NO_EVIDENCE, INCOMPLETE_EVIDENCE, NO_PREDICTIONS, abstention, or an unverified candidate leave it hidden. The raw sentence is never overwritten or sent through the contextual speech path.

An accepted new sign, raw Clear, and screen stop hide the old advisory line. Text-to-ASL Clear invalidates the pending reply window, so a late provider completion cannot repopulate it. Once a completed reply screen is left, its presentation is discarded; the bounded conversation history and existing shadow evaluation records remain separate. The existing Stage 3 diagnostic logger stays under its debug-only capture flag and is not part of the UI.

The only user-facing contextual output is the supported interpretation beneath the raw recognized sentence on Sign Detection. Predictions remain internal candidates, never a list on either screen. With Context Assist OFF, the contextual line stays gone and the original SENTENCE label remains. No Top-K scores, event IDs, correction controls, or diagnostic labels appear in the normal UI.

## Changed files

| Path | Purpose |
|---|---|
| android/app/src/main/java/com/example/apphear/contextassist/PhraseAssistCore.kt | Immutable presentation projection and strict matcher-result-to-cached-candidate check |
| android/app/src/main/java/com/example/apphear/contextassist/ConversationPhraseAssist.kt | Publish turn-scoped presentation updates; clear stale views/window without writing raw state |
| android/app/src/main/java/com/example/apphear/RecognitionActivity.kt | Observe sidecar state, show advisory text, hide it on new sign/Clear/navigation; Hear stays raw |
| android/app/src/main/java/com/example/apphear/ui/texttoasl/TextToAslFragment.kt | Continue triggering predictions on completed Hearing input and invalidating the pending reply with Text-to-ASL Clear; no prediction display |
| android/app/src/main/res/layout/activity_recognition.xml, fragment_text_to_asl.xml, values/strings.xml | Minimal contextual result on Sign Detection; no visible prediction list |
| android/app/src/test/java/com/example/apphear/contextassist/PhraseAssistUiStateTest.kt | Turn lifecycle, accepted match, abstain/incomplete/unverified behavior |
| android/app/src/androidTest/java/com/example/apphear/contextassist/ConversationPhraseAssistInstrumentedTest.kt | Silent prediction cache, supported advisory, raw Hear, second-turn fallback, feature OFF |
| context/feature-schema.md | Imprint of presentation-only boundary; no recognition schema change |
| docs/context-assist-deferred-issues.md | Persistent known-issues registry |

Recognition inference, Top-1, Candidate01, S2-R2, materializer, SentenceBuilder, matcher algorithm/thresholds, Gemini model/prompt, and release behavior were not changed.

## Verification

- Feature-ON fake-provider debug: all 110 JVM tests passed (zero failures/errors); assembleDebug passed.
- Feature-OFF debug: all 110 JVM tests passed; assembleDebug and assembleRelease passed. Generated release BuildConfig has Context Assist OFF, capture OFF, and empty Context Assist keys.
- Original Xiaomi M2101K7AG Android 12 connected feature-ON suite: 25 test cases, 23 passed, 2 conditional skips, zero failures. Those assertions covered the original UI contract, which was corrected on 2026-10-01; current results are recorded below.
- Connected feature-OFF suite: 25 test cases, 18 passed, 7 conditional skips, zero failures. The raw Hear path and hidden contextual views were checked.
- The first connected attempt was blocked by the phone canceling the test-companion installation; the original APK was immediately restored. One expanded test then failed because it expected the first raw sentence after injecting a second one; the assertion was corrected to the second raw sentence and the full ON suite passed. No product code was changed for that test-only failure.
- After both suites, the original user APK was restored by non-streaming install. Installed SHA-256 matched the pre-test backup exactly: 82c5298f218efb3c5184b3923672787f46843267e913aeb7c00d517a2829c5d5. No instrumentation companion package remained listed.
- No UI screenshot was retained. Device test view assertions provide UI evidence without capturing camera imagery.

## Remaining limits and release position

The provider's natural text is a conversational hypothesis; even a matcher-supported phrase may have unsupported semantic detail. Stage 3 wrong first-pass concepts were often absent from Top-5, so this feature does not repair those errors. Gemini Free-tier development traffic was not expanded to real conversation data in this milestone. The previous Stage 1.1 synthetic Android run established the real Gemini cache path; this UI milestone used the fake provider for deterministic device verification. Public release remains hard-disabled pending secure credential transport, privacy review, and held-out signer validation. See context-assist-deferred-issues.md for the full issue list.

**Deadline definition:** the conservative advisory feature is implemented for internal debug use. The original milestone and the 2026-10-01 placement correction passed their software and connected UI gates. It is not validated as an accuracy improvement or enabled in public release.

## 2026-10-01 presentation correction

Conversation predictions are generated from the completed Hearing turn and cached silently. User-facing contextual assistance appears on the Sign-to-Text side only after recognition evidence supports a candidate. The prediction list was removed from Text-to-ASL and Sign Detection. The provider, cache ownership, turn-ID guard, matcher, raw recognized sentence, and Hear/TTS path were not changed. The corrected test/build results are recorded in the progress tracker and correction commit.

The feature-ON fake-provider JVM suite passed 110/110; debug and Android-test APK builds passed. The feature-OFF JVM suite passed 110/110; debug and release builds passed, with release assist/capture off and empty Context Assist keys. Both layout XML files parse and contain no prediction-list nodes. The updated connected feature-ON suite reported OK (25 tests); the corrected silent-cache Text-to-ASL test also passed independently. The feature-OFF connected suite reported 18 passes, 7 conditional skips, and no failures across 25 tests. No physical signing was performed. The original APK's installed SHA-256 matched its pre-test backup, and the test companion was removed. The 2026-09-30 real-Gemini synthetic smoke established the provider/cache path before this presentation-only change, so no new live request was made.
