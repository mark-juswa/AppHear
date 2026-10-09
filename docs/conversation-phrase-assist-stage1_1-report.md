# Stage 1.1 — reply hypotheses and expected semantic anchors

Date: 2026-09-29. Feature branch: `feature/conversation-phrase-assist-mvp`.
Verified clean starting HEAD: `e9240d2b3fed7973d31a0ad5e19b38a8c3e4b925`.
Protected `baseline/apphear-s2-r2-integration-complete-2026-09-26` remains
`76d93cecd85bf9f76064d320aa4a5791b5f0704a`.

## Finding and decision

The focused contract refinement substantially improved exact anchor validity and scenario
coverage. Natural English and diverse reply intentions remained. However, important semantic
mismatches persist, and desktop latency was much worse in this run. **Prompt/schema refinement
is insufficient to establish that naturalText is supported by signed anchors.** Do not promote
predictions into verified communication. Stage 2 is not approved by this evaluation; review a
grounding architecture that retains hypotheses separately from verified meaning before UI or
recovery work. No such architecture was implemented here, and no further prompt tuning was done.

## Current implementation and causes

- `android/app/src/main/java/com/example/apphear/contextassist/GeminiContextPredictionProvider.kt`
  uses Gemini Interactions, `POST https://generativelanguage.googleapis.com/v1beta/interactions`,
  unchanged model `gemini-3.5-flash-lite`, `store=false`, 5-second connect and 8-second read
  timeouts, no retry. Prediction runs on the existing IO dispatcher, under the coordinator's
  unchanged 10-second prediction deadline. HTTP/incomplete/parser/provider failures yield no
  usable predictions through the existing wrapper.
- `RemoteContextPredictionProvider.kt` remains byte-for-byte unchanged: OpenAI Responses,
  `gpt-4o-mini`, original `naturalText`/`concepts` schema and prompt. No OpenAI calls were made.
- `PhraseAssistCore.kt` supplies `ContextPredictionProvider.predict(PredictionRequest)` and
  `ReplyCandidate(naturalText, concepts)`. Inputs contain at most six communicated conversation
  turns and the frozen gloss set. Deaf context comes from the raw SentenceBuilder sentence
  communicated at Hear, not reconstructed event glosses. Top-K evidence stays separate.
- Before this change, Gemini's schema allowed unrestricted strings in `concepts`; the prompt
  supplied vocabulary but did not enforce it structurally. The existing application validator
  correctly rejected unsupported strings, but only after generation. Its text/shape/label checks
  do not verify semantic correspondence. The instruction permitting absent English grammar did
  not clearly distinguish grammatical filler from substantive meaning.
- `ReplyCandidateValidator` remains unchanged. It trims values, checks 140-character natural
  text and 1–8 anchors, exact vocabulary membership, at most five candidates, and duplicate
  anchor sequences. Label validity does not prove semantic validity or a signed utterance.

## Small change chosen

Gemini's wire fields are now `naturalText` and **`expectedConcepts`**. The parser adapts the
latter to the existing provider-independent `ReplyCandidate.concepts`; no global rename,
matcher edit, new semantic validator, or new provider layer was necessary. A comment documents
that both representations are hypotheses. `naturalText` has no vocabulary enum or English-word
filter. Grammatical words such as “I'm” remain valid in “I'm tired.” / `[TIRED]`.

The concise system instruction is:

> You predict conversational reply hypotheses and their observable semantic anchors.

The user prompt supplies the same recent conversation plus the complete sorted exact label list,
then asks for 3–5 meaningfully different replies. It defines expectedConcepts as ordered observable
semantic anchors rather than English tokenization, asks for exact labels and omission of unsupported
grammatical filler, permits natural grammar, and asks that substantive meaning be grounded in anchors
or explicitly established context. Two examples illustrate `GO HOME` and `TIRED`; no phrase-template
library or recognizer-class rule system was added. Schema descriptions reinforce the same separation.

An exact-label schema enum was investigated as defense in depth. Google returned generic HTTP 400
`invalid_request` for the full 236-label schema, both with and without optional array limits, and
again without descriptive fields. Diagnostic requests succeeded with a three-label enum and without
an enum. This isolates a problem with the full enum schema combination on the current path; the API
did not identify its precise size/complexity limit. Rather than narrowing supported vocabulary or
switching API/model, the final schema uses strings and keeps the full label list in the prompt plus
the existing deterministic application validator. This limitation is empirical even though
[Google's structured-output documentation](https://ai.google.dev/gemini-api/docs/structured-output)
describes enum support. No schema-level vocabulary-enforcement claim is made.

## Same-case comparison

The unchanged `CASES` in `eval/context_prediction_stage1_eval.py` supplies all eight single-turn
and three multi-turn cases. The Gemini harness retains `--contract stage1` for reproducing the old
body and defaults to `--contract stage1_1` for the revised body. It writes distinct artifacts so
the Stage 1 results are not overwritten. Model, scenarios, conversation representation, and
application rejection rules were held constant. No retries or benchmark-driven prompt refinements
were used. A live model is nondeterministic; one historical and one revised run do not isolate all
service-load or sampling effects.

| Measure | Stage 1 | Stage 1.1 |
| --- | ---: | ---: |
| Cases with structured HTTP 200 output | 11/11 | 11/11 |
| Raw candidates | 42 | 40 |
| Accepted by application rules | 32 | 38 |
| Rejected | 10 unsupported | 1 unsupported + 1 duplicate |
| Candidates with unsupported anchors | 10/42 (23.8%) | 1/40 (2.5%) |
| Cases with zero accepted candidates | 2/11 | 0/11 |
| Desktop median latency | 1.799 s | 7.926 s |
| Desktop mean latency | 1.930 s | 10.775 s |
| Desktop minimum / maximum | 1.424 / 2.837 s | 1.778 / 24.438 s |
| Requests above Android's 10 s coordinator deadline | 0 | 5 |

The unsupported-anchor rate counts candidates, not individual anchor tokens. “Accepted” only
means deterministic label/shape validity. Desktop request timeout remains 30 seconds for collecting
diagnostic outputs; it is not Android's 8-second read timeout or 10-second coordinator deadline.
No timeout was extended in the application. These results cannot establish that the contract
caused all of the latency increase, and they are not a phone-network latency guarantee.

| Case / conversation supplied | Before accepted/rejected | After raw; accepted/rejected | After latency | Qualitative review |
| --- | ---: | ---: | ---: | --- |
| HEARING: Hello, how are you? | 3/0 | 3; 2/1 | 24.438 s | “Thank you” still lacked an anchor, but this candidate was rejected as a duplicate. A reciprocal question remains plausible but not a direct condition answer. |
| HEARING: Where are you going? | 4/0 | 3; 3/0 | 7.926 s | Natural, distinct destinations. SHOP1 versus store destination remains a semantic caveat. |
| HEARING: Are you tired? | 3/1 | 4; 4/0 | 17.853 s | Yes/no, sleep need, and mild tiredness remain distinct; unsupported I is absent. |
| HEARING: Are you feeling okay? | 4/0 | 3; 3/0 | 2.189 s | Sick/good/tired hypotheses remain natural and reasonably anchored. |
| HEARING: Do you want to go home? | 3/1 | 3; 3/0 | 1.778 s | Go now/stay/sleep replies have matching substantive anchors; unsupported NOT is absent. |
| HEARING: Did you go to school? | 0/4 | 4; 4/0 | 2.474 s | Coverage recovered without I. “Went” with YESTERDAY SCHOOL leaves the action implicit; “at that school” adds specificity. |
| HEARING: Where is your family? | 4/0 | 4; 3/1 | 23.126 s | OUT rejected. “Another city,” “parents,” and “with me” still add details beyond the anchors/context. |
| HEARING: What do you want to do? | 4/0 | 4; 4/0 | 14.714 s | Movie, restaurant, home/sleep, and cleaning are diverse, natural intentions. |
| HEARING greeting; DEAF GOOD; HEARING That's good. Where are you going? | 4/0 | 4; 4/0 | 18.655 s | Latest question followed; home/store/work/hospital differ. Does not prove deep use of prior turns. |
| HEARING Where are you going?; DEAF GO HOME; HEARING Are you tired after the trip? | 0/4 | 4; 4/0 | 2.481 s | Coverage recovered, but “Yes, long trip” / YES TIRED is weakly aligned. No/ready-home also lacks a tiredness anchor. |
| HEARING Did you go to school?; DEAF YES; HEARING How is your family? | 3/0 | 4; 4/0 | 2.892 s | Family status replies follow the latest question; “parents and sister” omits parents anchors. |

The complete conversation input, raw structured output, raw counts, parsed/accepted/rejected
candidates and exact rejection reasons for every case are preserved in
[Stage 1.1 synthetic results](conversation-phrase-assist-stage1_1-results.json).
All text is synthetic. The original Stage 1 report and local artifact remain available separately.

### Improved and remaining examples

```json
{"naturalText":"Yes, I go to school.","expectedConcepts":["YES","GO","SCHOOL"]}
{"naturalText":"Yes, I need sleep.","expectedConcepts":["YES","NEED","SLEEP"]}
{"naturalText":"I'm going home.","expectedConcepts":["GO","HOME"]}
```

These preserve natural grammatical English while removing unsupported I. However:

```json
{"naturalText":"My parents are at home.","expectedConcepts":["FAMILY","HOUSE"]}
{"naturalText":"Yes, long trip.","expectedConcepts":["YES","TIRED"]}
{"naturalText":"My parents and sister are fine.","expectedConcepts":["FAMILY","SISTER","GOOD"]}
```

The model still sometimes selects a related broad concept rather than anchors for the actual
substantive claim. The long-trip question supplies a trip context, but does not establish a long
trip, and TIRED is not equivalent to that assertion. This is evidence against treating the natural
sentence as verified meaning. No semantic safety percentage is claimed: the review is qualitative,
with no blinded reproducible semantic labeling protocol. Most cases retain distinct communicative
intentions; the greeting duplicate is still an example of trivial wording variation.

## Safety and regression gates

- No recognition component, vocabulary asset/order, Top-1, event guard, SentenceBuilder, Hear/TTS,
  raw UI, lifecycle/re-arm, or matcher threshold/logic was edited. `PhraseAssistCore.kt` changed
  only a candidate documentation comment; `PhraseMatcher` and validator behavior are unchanged.
- No release configuration or flags changed. Context Assist remains default-off/debug-only,
  release hard-disabled. The Free-tier Gemini key was neither displayed nor committed; only
  synthetic conversations were sent.
- The new JVM test verifies natural grammar need not appear in the recognizer vocabulary, while
  unsupported anchors still fail. Existing tests cover matcher fallback, provider errors/timeouts,
  stale turns, event deduplication, raw SentenceBuilder preservation and raw/hypothetical separation.
- Updated Android parser test requires expectedConcepts, adapts it without altering matcher input,
  rejects malformed/legacy Gemini items, and retains the unsupported-candidate validation check.
  New request/schema test checks the full frozen 236-label prompt and unrestricted natural-English
  field. The live synthetic test now checks real cached hypotheses through RecognitionActivity,
  confirming that displayed text, intercepted Hear speech and communicated Deaf context remain
  GO THINK and the injected event IDs 101/102 remain intact. No physical sign correction was needed.
- JVM: PASS, **107 tests**, 0 failures/errors/skips.
- Default debug APK and Android instrumentation Kotlin compilation: PASS, empty keys.
- Release APK: PASS, Context Assist hard-disabled, empty keys, 4 GB Gradle heap.
- Android connected real Gemini synthetic test: PASS, 1 test on Xiaomi M2101K7AG / Android 12.
- Focused connected ON/fake suite: PASS, 8 passed, 2 conditional skips, 0 failures/errors.
- Focused connected OFF suite: PASS, 4 passed, 6 conditional skips, 0 failures/errors.
- The first OFF suite attempt ran no tests because the phone canceled test APK installation
  (`INSTALL_FAILED_USER_RESTRICTED`). Reusing a test package failed because Gradle had removed it.
  After the user agreed to approve install prompts, the normal OFF suite passed. No source change
  was made to address installation. Streamed restoration later failed with an empty error; the
  file-based `adb install --no-streaming -r` restored the saved APK successfully. Installed APK
  SHA-256 matched `82C5298F218EFB3C5184B3923672787F46843267E913AEB7C00D517A2829C5D5`.
  Restoration verification covers APK bytes, not application private data; connected test tooling
  installs/removes test app packages. The local debug BuildConfig was returned to empty keys.
- Pre-existing release-unit-test source-set failure involving debug-only helpers was not changed
  or rerun. No recognition accuracy claim follows from these synthetic provider tests.

## Diff and stopping boundary

Changes are limited to the Gemini provider contract/parser, one candidate comment, focused JVM
and Android tests, the Gemini comparison harness, synthetic evaluation evidence, and project
report/contract/handoff notes. OpenAI provider, old scenario set, matcher and product paths remain
unchanged. Keep the refined contract shadow-only and stop at Stage 1.1 for review. The remaining
grounding and latency concerns must be resolved before claiming readiness for visible predictions
or any later automatic communication output.

Final project review: scope and shadow isolation PASS; production/Stage 2 readiness is deferred.
No critical recognition-boundary violation was found. Important remaining findings are semantic
overclaims and variable latency. The unchanged matcher still requires a one-to-one evidence
sequence; calling concepts “anchors” does not add missing-sign recovery or alignment. The
accompanying feature commit is the resulting Stage 1.1 revision; its SHA is returned with this
report. No key was detected in the changed source or synthetic results, and Git whitespace checks
passed before commit.
