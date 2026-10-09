# Conversation Phrase Assist — Gemini Stage 1 evaluation

Date: 2026-09-29. Starting branch `feature/conversation-phrase-assist-mvp`, HEAD
`253c6b6636cdbcb7f4d2a7da3ac6b7ead3c121d8`, clean before this extension.
Protected baseline ref still resolves to `76d93cecd85bf9f76064d320aa4a5791b5f0704a`.

## Result

**A real Gemini reply-prediction path works in shadow mode on Android using synthetic text.**
The existing OpenAI provider and its blocked-credit report remain unchanged. The new optional
debug provider uses Google's Interactions API at
`https://generativelanguage.googleapis.com/v1beta/interactions`. It sends the same bounded
conversation lines, sorted frozen 236-class gloss list, system instruction, and 3–5 phrase
request as the existing provider. `response_format` requests JSON with `candidates[]`,
`naturalText`, and `concepts[]`. `store=false`; no images, audio, Top-K scores, or recognition
tensors are sent. The existing application validator rejects unsupported concepts.

The initially selected `gemini-3.8-flash` returned HTTP 503 `service_unavailable` twice
(14.6 s and 20.1 s), explicitly citing model demand. A single `gemini-3.7-flash` probe
also returned HTTP 503 (13.4 s); `gemini-3.5-flash` timed out after 30.1 s. One
`gemini-3.5-flash-lite` probe succeeded in 2.7 s, so the debug provider now selects
**`gemini-3.5-flash-lite`**. This is an availability/latency choice for validation,
not a comparative intelligence or accuracy claim. Google lists Flash-Lite as a stable
model with structured output and a Free tier:
[model specification](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite),
[pricing and data use](https://ai.google.dev/gemini-api/docs/pricing).

The key's project is on Google's **Free** billing tier. Only the checked-in synthetic
conversation cases were sent. Real user conversations must not be sent under this
development setup because Google's Free tier says inputs and outputs may be used to
improve its products. The key stays in local Gradle configuration and was not logged or
committed. It is embedded only in a debug build explicitly configured with both
`contextPhraseAssist=true` and `contextPhraseAssistProvider=gemini`; release and ordinary
debug builds receive an empty Gemini key. A debug APK containing the key is temporary
private development infrastructure.

## Bounded live observations

`eval/gemini_prediction_stage1_eval.py` sent the eight single-turn and three multi-turn
synthetic histories defined by the prior Stage 1 harness. All 11 returned HTTP 200 and
`status=completed`. Every output parsed as the requested JSON shape. There were 42 raw
candidates: **32 passed** exact-vocabulary/application-shape checks and **10 were rejected**
for unsupported concepts. The provider sometimes used `I` although the frozen class list
does not contain that exact label; two cases had zero usable candidates. No candidate was
silently remapped. Request latency: minimum 1.42 s, median 1.80 s, mean 1.93 s, maximum
2.84 s on this desktop probe. These timings are not phone-network latency guarantees.

| Synthetic situation | Accepted / rejected | Observation |
| --- | ---: | --- |
| Hello, how are you? | 3 / 0 | One candidate repeated the question; another claimed “thank you” without a matching concept. |
| Where are you going? | 4 / 0 | `GO HOME`, `GO WORK`, `GO SHOP1`, `GO SCHOOL` gave distinct plausible destinations. |
| Are you tired? | 3 / 1 | `I` caused the rejection; supported yes/no tired alternatives remained. |
| Are you feeling okay? | 4 / 0 | Several meaningful condition replies. |
| Do you want to go home? | 3 / 1 | Unsupported `NOT` caused the rejection. |
| Did you go to school? | 0 / 4 | Every candidate used unsupported `I`. |
| Where is your family? | 4 / 0 | Several family-location phrases; wording needs semantic review. |
| What do you want to do? | 4 / 0 | Distinct eat, restaurant, movie, and stay-home replies. |
| Greeting / GOOD / where going | 4 / 0 | Responses followed the latest going question. |
| GO HOME / tired after trip | 0 / 4 | Three used unsupported `I`; one used unsupported `LONG` and `TRIP`. |
| School / YES / how family | 3 / 0 | Family-condition replies followed the latest question. |

Representative raw structured output, with no postprocessing:

```json
{"candidates":[
  {"naturalText":"I am going home.","concepts":["GO","HOME"]},
  {"naturalText":"I am going to work.","concepts":["GO","WORK"]},
  {"naturalText":"I am going to the store.","concepts":["GO","SHOP1"]},
  {"naturalText":"I am going to school.","concepts":["GO","SCHOOL"]}
]}
```

The full raw structured responses, parsed candidates, per-item rejection reasons, and
latencies are in the ignored local synthetic artifact
`artifacts/gemini_phrase_stage1_gemini_3_5_flash_lite.json`. The artifact contains no key.
Accepted means exact recognizer-label and shape validity, **not** semantic safety.
For example, “I am fine, thank you.” with `GOOD FEEL` claims thanks without a signed
concept, and “going to the store” with `GO SHOP1` may conflate shopping with a destination.
The current deterministic validator cannot detect those meaning gaps. The 3–4 replies
per successful case show useful phrase-level variety, but this tiny synthetic set does not
establish reliability or real conversation quality.

## Android and safety gates

- The Gemini parser test accepted `GO HOME`, filtered unsupported `MARKET`, rejected a
  malformed item, and confirmed that a missing key returns no predictions.
- The synthetic connected Android test completed a hearing turn, made a real Gemini request,
  cached validated candidates for that turn, and recorded a shadow result while keeping
  `rawSentence=GO THINK` and the Deaf conversation turn text unchanged. No physical sign
  correction or product-output mutation was tested or enabled.
- Existing JVM and connected tests cover timeout, provider exception, stale-turn rejection,
  event deduplication, raw sentence preservation, Context Assist OFF, and fake shadow matching
  with raw display and Hear/TTS unchanged. HTTP non-2xx and incomplete remote responses yield
  no predictions; no retry is configured.
- `:app:testDebugUnitTest`: PASS, 106 tests, 0 failures, 0 skips.
- `:app:assembleDebug` with Context Assist OFF and empty keys: PASS.
- `:app:assembleRelease` with release Context Assist hard-disabled and empty keys: PASS.
- Focused connected Android suite, OFF: PASS; conditional ON tests skipped.
- Focused connected Android suite, ON/fake: PASS; conditional OFF/live tests skipped.
- Targeted connected Android ON/Gemini synthetic remote test: PASS, 1 test.
- Phone's pre-test APK was restored after the live test; installed APK SHA-256 matched the
  backup. The two temporary backup copies were then removed. The local debug APK was rebuilt
  with empty keys, and its generated Gemini BuildConfig field was verified empty.

An initial Gradle invocation lacked the repository-required `android.useAndroidX` property;
the next PowerShell command split its unquoted dotted name. Quoting the property fixed the
command. No source change was needed. The pre-existing release-unit-test source-set issue
documented in the earlier Stage 1 report was not retested in this extension.

## Decision

Final project review: plan alignment and shadow system integrity PASS; product readiness
remains deferred. No critical boundary violation was found. Important findings are the
unsupported concepts and semantic overclaims above. The platform HTTP call is blocking on
the existing IO dispatcher; socket deadlines bound network waits, while coroutine timeout
alone cannot promptly interrupt every blocking socket operation. No wait enters the camera
or recognition path. No matcher, recognition, UI, speech, or SentenceBuilder file changed.

The real provider is usable for **synthetic shadow evaluation**, but Stage 2 visible
prediction UI is **not ready**. First make one focused provider-contract improvement so
unsupported labels such as `I` are avoided more consistently and natural English cannot
claim important content absent from the signed concepts; then repeat a bounded evaluation.
Do not change recognition, the matcher, product output, or release behavior based on these
results. This stage ends here.
