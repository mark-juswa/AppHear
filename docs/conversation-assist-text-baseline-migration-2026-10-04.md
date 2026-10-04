# Context Assist migration to the working Text-to-ASL baseline

## Verified source history

- Preserved working Text-to-ASL branch: `codex/current-working-text-to-asl-baseline-2026-09-29`.
- Preserved annotated tag: `apphear-text-to-asl-working-alphabet-2026-09-29`.
- Both resolve to `cc1f3949114d0ed1dab38d4428191151b37df358`. The tested pilot's scope and limits remain in `context/current-working-baseline-2026-09-29.md`.
- Previous Context Assist branch: `feature/conversation-phrase-assist-mvp` at `75f5959c06b96c893bb1c8f266f7b3deb529ead6`. Its merge base with the preserved source is `76d93cecd85bf9f76064d320aa4a5791b5f0704a`.
- The preserved branch and tag were not moved or edited. The primary checkout's unrelated local fingerspelling work was left untouched.

## Reconciliation

The newer baseline includes the Text-to-ASL alphabet/character pilot, Profile/Settings dependencies, and debug continuous-transition instrumentation. The old Context Assist branch lacks those changes. A wholesale merge or copy of its Text-to-ASL fragment or Gradle file would remove baseline behavior.

This branch instead starts at `cc1f394` and adds the existing Context Assist sidecar and its historical tests/evidence. The sidecar Kotlin providers, validator, conservative matcher, policy JSON, read-only Top-5 evidence seam, and advisory recognition UI are unchanged from the old experiment. The shared Gradle file retains all seven Text-to-ASL pilot flags and adds separate Context Assist debug flags, with release hard-disabled. The newer Text-to-ASL fragment records a Hearing turn after a successful plan while retaining asynchronous catalog loading, New-character readiness, playback, character choice, unsupported-token reporting, and Replay. A deferred submission retains its original typed/speech source. Replay does not record a second turn.

Recognition Top-1, event guard, SentenceBuilder, the 378-feature path, S2-R2, materializer, Recognition V2, model, and vocabulary are not tuned. Context Assist remains downstream: raw recognized text stays visible and is what Hear speaks; the existing matcher can only show a separate advisory `Context-supported` line when visual evidence supports a cached prediction. The Gemini provider remains available only through the explicit private debug flag; no real provider call was required for this migration.

## Validation and limits

- Default debug JVM suite: 147 tests, 0 failures.
- Pilot flags plus fake Context Assist JVM suite: 147 tests, 0 failures.
- Pilot flags with Context Assist OFF JVM suite: 147 tests, 0 failures.
- Pilot-plus-Context-Assist debug APK, release APK, and Android test APK: built successfully.
- Pilot with Context Assist OFF debug APK: built successfully.
- The connected Android suite and physical F22 smoke remain pending until the representative phone appears in ADB. Build success and historical phone evidence do not establish a new device pass for this combined build.
- The current Gemini Free-tier setup is for synthetic development conversation text only. Credentials belong in ignored local configuration and must not be committed.
- Text-to-ASL pilot flags and Context Assist default to off, and release remains off. The existing deferred issue registry still applies, especially recognizer Top-5 absence, extra events, provider coverage, semantic grounding, and production credential transport.
