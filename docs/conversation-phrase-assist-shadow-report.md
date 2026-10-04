# Conversation phrase assistance shadow safety stage — 2026-09-29

## Repository state

The clean feature worktree began on `feature/conversation-phrase-assist-mvp` at
`24f0684360332b25d34a70f445e245733982976a`. That commit belongs to the feature branch.
The protected `baseline/apphear-s2-r2-integration-complete-2026-09-26` ref still resolved to
`76d93cecd85bf9f76064d320aa4a5791b5f0704a`. The main checkout was separately on
`codex/current-working-text-to-asl-baseline-2026-09-29` at `cc1f394` with unrelated local
changes; it was not edited or reset.

## Code trace and couplings found

- `android/app/src/main/java/com/example/apphear/perceptionvnext/PhoneProductionSession.kt`
  owns the raw `SentenceBuilder`, applies the increasing event-ID guard, appends Top-1, and copies
  existing Top-5 scores into read-only `RecognitionEvidence`. The frozen recognizer invocation,
  Top-1 choice, and event guard are unchanged.
- `Candidate01FrameAnalyzer.kt` passes `PhoneProductionSession.Update.evidence` through
  `FrameResult` (`pipeline/FrameAnalyzer.kt`). `RecognitionActivity.kt` buffers it in a bounded
  `SigningTurnBuffer` separately from the raw sentence.
- `ui/texttoasl/TextToAslFragment.kt` records completed hearing text. The process-local
  `ConversationPhraseAssist.kt` owns bounded conversation turns, cached predictions, and the
  phrase matcher. `PhraseAssistCore.kt` owns evidence, predictions, and matching types.
- Before this safety stage, `RecognitionActivity.speakRecognizedSentence()` set an assisted
  sentence in the UI, passed it to TTS, and called `phoneSession.clearSentence()` at Hear.
  `renderRecognitionSnapshot()` could retain that assisted display on subsequent frames.
  `ConversationPhraseAssist.finalizeDeafTurn()` also added assisted natural text as the Deaf
  conversation turn. Thus a contextual match or even a fallback changed baseline Hear and raw
  sentence reset behavior when the flag was on.

## Shadow-only boundary

The existing Hear path now obtains the raw sentence, performs the normal empty-text check,
and sends exactly that raw text to `AppHearSpeechPlayer`. Only afterward does the sidecar snapshot
current Top-5 events, consume cached predictions, run the unchanged matcher, and append a bounded
`ShadowEvaluation`. The record stores raw sentence, event IDs/Top-5 labels and scores, predicted
phrases, hypothetical candidate if any, whether its gloss sequence differs, and a reason
(`MATCH`, missing/incomplete evidence, no predictions, no visual match/tie, or matcher unavailable).
  Debug logging exposes the same fields. No camera frames, landmarks, tensors, or audio are retained.

The sentence renderer uses `RecognitionUiSnapshot.sentenceText` directly. The assisted display
override and Hear-specific `phoneSession.clearSentence()` call are gone. Clear still clears the
raw sentence exactly as before and also drops sidecar evidence. Activity stop drops sidecar
  evidence; it does not write product sentence or speech state. The shared conversation context
  records the raw sentence communicated by Hear, never the hypothetical natural-language phrase.
  Full event glosses and scores remain in `ShadowEvaluation`. The existing
`contextPhraseAssist` debug flag now means **shadow evaluation only**; it defaults off and release
remains hard-disabled. The provider, prompt, model, vocabulary, matching policy, and all frozen
recognition components were left unchanged.

## Validation

- Shadow-on JVM suite: 106 tests, zero failures/errors. Shadow-on debug app and Android test
  APKs built. The connected Android suite discovered 16 tests, skipped the flag-off-only test,
  and had zero failures.
- Flag-off JVM suite: 106 tests, zero failures/errors. Default-off debug APK built. The connected
  suite discovered 16 tests, skipped two shadow-on-only tests, and had zero failures. Release
  packaging passed on a diagnostic retry after an initial generic incremental-packaging failure.
- The Android shadow test injects synthetic guarded events with raw `GO THINK` and a supported
  hypothetical `GO HOME`. It captures the actual Hear speech call and asserts spoken text and
  sentence UI remain `GO THINK`, including a repeated Hear and Activity stop. The sidecar record
  separately shows `GO HOME`, `wouldChangeRaw=true`, and `MATCH`. Core tests verify Top-1/Top-5,
  `SentenceBuilder` isolation, duplicate IDs, invalid concepts, stale predictions, provider
  exception, and timeout.
- Xiaomi M2101K7AG's pre-test APK was backed up and restored after connected tests. The pulled
  restored APK SHA-256 matched the backup exactly:
  `82c5298f218efb3c5184b3923672787f46843267e913aeb7c00d517a2829c5d5`.

## Remaining limits

The phone tests use synthetic recognition evidence; they do not establish live-signer or
cross-signer phrase accuracy. The remote provider was not activated. Shadow records are bounded,
  process-local, and not a persistent evaluation dataset. The completed raw sentence and full
  event sequence are kept separately, including when `SentenceBuilder` deduplicates or caps words.
  No contextual interpretation
is eligible for product output at this stage.

## Stage 0.5 representation correction — 2026-09-29

`ConversationPhraseAssist.evaluateShadowTurn()` previously constructed the Deaf
`ConversationTurn.text` by joining event Top-1 glosses, even though its `rawSentence` argument
was the exact text Hear spoke and `ShadowEvaluation` already stored both representations. The
Deaf context turn now uses that completed raw sentence. Event evidence still goes unchanged to
the matcher and bounded shadow history. A communicated raw sentence is recorded even when
the evidence buffer is incomplete, because Hear still spoke it; repeated Hear without new
evidence does not create another turn. Hearing-turn IDs and stale-reply rejection are unchanged.

Focused Android tests exercised `GO, GO, HOME` as events versus `GO HOME` as the spoken/context
sentence, a capped `GO, HOME, WORK` sequence versus `HOME WORK`, and an interrupted evidence
window. They verified that IDs and Top-K remain in the evaluation record. Shadow-on and
flag-off connected suites each discovered 19 tests with zero failures (one and five
flag-specific skips respectively). Both debug configurations and the release APK built;
release packaging required a 4 GB Gradle heap after a Java heap-space error in Android's APK
packager. No provider, prompt, matcher, threshold, recognizer, or product-output change occurred.
