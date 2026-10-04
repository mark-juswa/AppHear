# Conversation-aware phrase assistance MVP

**Current mode (2026-09-29): shadow-only.** The earlier output-changing behavior described by
this MVP has been removed. See `conversation-phrase-assist-shadow-report.md` for the active
data flow, tests, and safety boundary. The implementation below is retained as experiment history.

## Current experiment

This branch is based on protected commit `76d93cecd85bf9f76064d320aa4a5791b5f0704a`. The recognizer, vocabulary ordering, Candidate01, 378 features, S2-R2, event lifecycle, materializer, and Recognition V2 are unchanged. The sidecar copies the recognizer's existing Top-5 indices and scores only after a guarded committed event.

The Text-to-ASL Sign It action, speech result, or keyboard Done action records one completed hearing turn. A fake or remote provider predicts reply phrases once and caches them for that turn. The RecognitionActivity buffers committed sign evidence separately from S8. The existing Hear button is the Deaf turn boundary: it compares the signed sequence against the cached phrase candidates, displays and speaks the assisted English phrase when the match passes, and otherwise displays and speaks the raw S8 sentence. The raw event/gloss sequence and assisted sequence remain distinct in bounded process memory and debug logs. Hear begins a clean S8 sentence for the next response when this feature is on. Replay does not add a new hearing turn.

Predictions are consumed at that Hear action. A late reply to an older hearing message is discarded by turn ID, and a new Deaf response does not reuse the previous message's predictions. If prediction has not arrived by Hear, the raw result is used immediately.

There is no automatic sentence-end detector in the protected app. A Deaf response must be finalized with Hear for phrase-level interpretation. If the app is interrupted mid-turn, or more than eight events exceed the buffer, Hear uses raw recognition. The current sign display still shows the recognizer's Top-1; the sentence area shows the assisted phrase after finalization. No AI request runs on a CameraX frame or sign event.

## Exact vocabulary and conservative match

`I`, `ME`, `FINE`, `THANK-YOU`, `OKAY`, and `STORE` are not in the frozen 236-class list. The fake demonstration uses supported concepts: `GO HOME`, `GO SCHOOL`, `GO WORK`, `GOOD`, `TIRED`, and `SICK`. Natural English may add grammatical words, but each concept must name a real recognizer class and map one-to-one to a committed sign event. Unsupported provider concepts are rejected. The matcher permits at most one changed event and requires close Top-5 visual evidence; a strong contradictory Top-1 yields raw fallback. The score rule is provisional and is not calibrated confidence. See the audit note for the limited real-score sample.

## Build switches

The feature defaults **off** for all builds. Release builds always compile it off. Internal debug test build:

```powershell
cd android
.\gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon '-Pandroid.useAndroidX=true' '-PcontextPhraseAssist=true' '-PcontextPhraseAssistProvider=fake'
```

The fake provider returns known phrases for hearing messages containing “Where … go” or “How are you”. For optional remote testing, set `APPHEAR_CONTEXT_ASSIST_API_KEY` in the local environment and build debug with `'-PcontextPhraseAssistProvider=remote'`. The remote adapter uses the OpenAI Responses API with structured JSON output and `store=false`; it sends only recent conversation text and the exact allowed gloss list. It sends no audio, image, geometry, or recognition tensor. The debug credential is embedded in that debug APK: keep it private, rotate it after testing, and replace this transport with a backend/proxy before any public rollout. A missing credential, API error, timeout, malformed response, invalid concept, or unmatched phrase yields raw recognition.

The remote adapter follows the [official OpenAI Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs). The model identifier is isolated in `RemoteContextPredictionProvider.kt`; application state and matching are provider independent. No remote request has been validated without a configured development credential.

## Validation and rollback

The deterministic JVM tests cover Top-5 evidence extraction, exact vocabulary filtering, phrase agreement, strong contradiction, no-match fallback, event deduplication, long-turn overflow, stale prediction rejection, provider failure, timeout, and fake reply generation. Policy asset loading runs in the background prediction step; Hear only performs bounded in-memory matching. The final default-off JVM suite passed 105/105, the full connected Android suite passed 15/15, and debug-on, default-off, and release APKs built. Phone smoke is a runtime integration check, not a cross-signer accuracy claim.

Rollback: build without `-PcontextPhraseAssist=true`, or use the protected baseline commit/branch. Disabled debug and all release builds use the original S8 sentence and Hear behavior. The feature does not migrate persistent data, so there is no data rollback.

Open evaluation work: a held-out cross-signer conversation corpus and end-to-end phrase comparison are needed before calling the feature accurate or enabling it in release. The current fake scenario proves wiring and safety behavior only. Natural English from a remote provider still needs broader semantic evaluation because exact signed-concept validation alone cannot prove that every grammatical nuance in the phrase was signed.
