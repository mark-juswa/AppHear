# Conversation Phrase Assist — Stage 1 provider evaluation

Date: 2026-09-29. Starting branch `feature/conversation-phrase-assist-mvp`, HEAD
`a951f5d86b491430e702e0da226b18c77dc06217`, clean before this stage.
Protected recognition baseline
`baseline/apphear-s2-r2-integration-complete-2026-09-26` resolves to
`76d93cecd85bf9f76064d320aa4a5791b5f0704a`.

## Result

**Live reply-quality validation is blocked by API credits.** Two bounded calls
with the configured local development key reached the OpenAI API and returned
HTTP 429. The structured error was
`type=insufficient_quota`, `code=credit_balance_exhausted` ("You have no
credits remaining"). The first call took about 9.6 s and the diagnostic
follow-up about 8.0 s. No candidate response was generated. The harness
stopped after the first case, rather than spending requests on the other
scenarios. No key was printed or written to the evaluation artifact.

There are consequently **no accepted or rejected live phrase candidates**,
no live vocabulary-validity rate, and no basis yet for judging conversational
relevance, phrase usefulness, semantic alignment, diversity, or stability.
Stage 2 visible prediction UI is not ready for a decision from this evidence.

## Existing provider contract inspected

Source: `android/app/src/main/java/com/example/apphear/contextassist/RemoteContextPredictionProvider.kt`.
The unchanged provider uses `HttpURLConnection` to POST
`https://api.openai.com/v1/responses` with model **`gpt-4o-mini`** and
`store=false`. Its system message is:

> You predict possible conversational replies for a constrained ASL recognizer.

The user message serializes the bounded recent turns as `SPEAKER: text` lines,
then supplies the sorted comma-delimited set of 236 exact
`class_index_to_gloss` labels from
`android/app/src/main/assets/phase4a_gate2_recognizer_parity/manifest.json`.
It asks for 3–5 plausible next Deaf replies, concept sequences drawn only
from the listed labels, natural English with permissible grammar, and no
claim that a prediction was signed. There is no developer message.

The Responses `text.format` is strict `json_schema` named
`apphear_reply_candidates`: root `candidates` array; each item has required
`naturalText` string and `concepts` string array; extra object properties
are forbidden. The schema does not enforce the 3–5 count or vocabulary.
The parser requires HTTP 2xx and response `status=completed`, finds the
first `output_text`, parses its `candidates`, and keeps at most five.
Malformed JSON or missing fields throws; non-2xx, incomplete status, or
missing output yields an empty list. There is no retry.

The application validator in
`android/app/src/main/java/com/example/apphear/contextassist/PhraseAssistCore.kt`
trims text/concepts and rejects blank or over-140-character natural text,
empty or over-eight-concept sequences, any concept not exactly in the
236-label set, and duplicate concept sequences. `predictValidated` turns
provider errors and its 10 s timeout into no predictions. A blank key
returns no predictions before opening a connection.

`ConversationPhraseAssist.recordHearingMessage` passes the current
`ConversationContext` snapshot (at most six turns) after a completed typed
or speech hearing message, calls the provider on `Dispatchers.IO`, and
uses the hearing turn ID to reject stale replies. Stage 0.5 records the
completed **raw SentenceBuilder sentence** as each Deaf turn; event Top-5
recognition evidence remains separate and is not sent to the LLM.
The development credential comes from Gradle
`APPHEAR_CONTEXT_ASSIST_API_KEY` (or the same environment variable),
is embedded only in a debug `BuildConfig`, and is empty in release.
This temporary credential transport requires the debug APK to remain private.

The [official model page](https://developers.openai.com/api/docs/models/gpt-4o-mini)
lists `gpt-4o-mini` for Responses and Structured Outputs, and the
[Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs)
documents `text.format` with `json_schema`. No concrete request-format
incompatibility was found in the code or documentation. The quota error
prevents confirming a successful live response.

## Bounded live set and observations

The checked-in evaluation harness
`eval/context_prediction_stage1_eval.py` mirrors the provider's current
request body and validation rules. It prepares eight single-turn situations:
"Hello, how are you?", "Where are you going?", "Are you tired?",
"Are you feeling okay?", "Do you want to go home?", "Did you go to
school?", "Where is your family?", and "What do you want to do?".
It also prepares three short multi-turn histories: greeting/GOOD/going,
going/GO HOME/tired, and school/YES/family. These use communicated text,
not event gloss reconstruction or visual evidence.

Only the first situation was sent. Its raw API result was an error, not a
structured candidate response:

```json
{"error":{"type":"insufficient_quota","code":"credit_balance_exhausted",
          "message":"You have no credits remaining."}}
```

This is a shortened excerpt of the diagnostic response; the local ignored
artifact `artifacts/context_phrase_stage1_live.json` has the complete
synthetic request case, error category, and timing. It contains no key.
The remaining ten situations were deliberately not sent after the quota
rejection. No candidate was accepted or rejected by vocabulary validation
in live output, and the semantic overclaim safeguard could not be evaluated.

## Failure and shadow safety checks

- A new connected test directly exercises the existing structured parser:
  `GO HOME` parses and validates; unsupported `MARKET` is filtered;
  empty candidates stay empty; a malformed item throws rather than becoming
  a phrase. No provider or prompt code changed.
- Existing JVM tests cover provider exception and timeout fallback, exact
  vocabulary rejection, stale hearing-turn rejection, matcher fallback,
  event deduplication, and raw/assisted separation.
- Existing Android tests verify shadow-only Hear speech and Sign-to-Text
  display remain raw even when a fake predicted phrase would differ.
  Context Assist OFF tests verify baseline Hear behavior.
- Missing key returns no predictions in provider code. The live quota
  rejection is HTTP non-2xx, which also returns no predictions. The initial
  sandboxed desktop attempt met a local connection refusal; the same request
  reached the API when run with network permission. The desktop probe does
  not constitute an Android remote-provider success test.
- No release or product output path was changed. No remote credential was
  embedded in the regression APKs: Gradle was invoked with an explicit empty
  key override. The phone's pre-test APK was restored after connected tests,
  and the restored APK matched the backup by SHA-256.

## Gates

| Gate | Result |
| --- | --- |
| `:app:testDebugUnitTest` | PASS, 106 tests, 0 failures/skips |
| `:app:assembleDebug` | PASS, Context Assist ON/fake, empty key override |
| `:app:compileDebugAndroidTestKotlin` | PASS |
| `:app:connectedDebugAndroidTest` ON/fake | PASS, one conditional OFF-mode skip |
| `:app:connectedDebugAndroidTest` OFF | PASS, 20 tests, 5 conditional ON-mode skips |
| `:app:assembleRelease` | PASS, Context Assist OFF, empty key |
| `:app:testReleaseUnitTest` | BLOCKED by pre-existing release test source-set errors: tests reference debug-only `P7dMath`, `P8bDecoder`, and phone debug helpers |
| Real remote Android success path | NOT RUN: API credit balance exhausted |

## Diff and recommendation

This stage adds one evaluation-only script, one focused Android parser test,
and this report. It changes no recognizer, phrase matcher, provider, prompt,
model, product UI, or shadow-mode code. The existing raw Sign-to-Text and
Hear/TTS output remained isolated in the connected tests.

Restore API credits and rerun the bounded set with the same provider/model
before deciding whether the provider is ready for Stage 2. Record each raw
structured response, exact-vocabulary acceptance/rejection, semantic
overclaims, diversity, and latency. The currently observed blocker calls
for **no provider code change**.
