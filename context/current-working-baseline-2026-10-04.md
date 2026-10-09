# Current working AppHear baseline — 2026-10-04

Historical preserved baseline. The current user-reviewed application baseline is now described in [the October 5 handoff](current-working-baseline-2026-10-05.md). This October 4 branch/tag remains fixed for rollback and for experiments already based on it.

## Identity

- Preservation branch: `baseline/apphear-text-to-asl-context-assist-ui-2026-10-04`.
- Annotated preservation tag: `apphear-text-to-asl-context-assist-ui-2026-10-04`.
- Last application change before this preservation note: `ffd32041dcf2a0f5e72a3904ca6129ce7c7b268c`.
- This source descends from the preserved Text-to-ASL alphabet baseline `cc1f3949114d0ed1dab38d4428191151b37df358` and the protected S2-R2 recognition baseline `76d93cecd85bf9f76064d320aa4a5791b5f0704a`. Neither older branch nor tag was moved.

This is the **current working source baseline for future AppHear experiments**. New work starts on a separate branch or worktree from the annotated tag. The preservation branch and tag are not development branches and must not be moved to accommodate later experiments.

## Included behavior

- The Text-to-ASL alphabet/character pilot and its existing feature flags from the 2026-09-29 baseline.
- Conversation-Aware Phrase Assistance as a downstream sidecar: completed Hearing turns can trigger asynchronous Gemini reply predictions; completed sign events retain read-only Top-5 evidence; the existing matcher can show a separate `Context-supported` interpretation only when visual evidence supports it.
- The compact Recognition UI with a content-fitting, multiword raw `RECOGNIZED` card and three visible, fully wrapped conversational predictions. The leading prediction is centered; a partial visual-anchor cue may briefly emphasize it. Predictions do not become recognized text.
- Raw Top-1, `SentenceBuilder`, Clear, and Hear/TTS remain authoritative. The recognizer, segmentation, materializer, vocabulary, matcher rules, and thresholds were not changed by the UI work.

## Reproducible build configurations

- The phone-reviewed private debug APK had the Text-to-ASL pilot, shared characters, more words, character selection, New idle, alphabet fallback, and Context Assist enabled. Its Context Assist provider was Gemini; Profile/Accounts and Stage 3 capture were off. The local development credential is **not** stored in Git. Use only synthetic conversation text with the present Gemini Free-tier setup.
- The explicit all-flags-off debug configuration also builds and passes tests. Release keeps Context Assist and the Text-to-ASL pilot flags hard-disabled in `android/app/build.gradle.kts`.
- Local, ignored rollback APKs are under `android/build/stable-context-assist-ui-20261004/` in this worktree. The phone-reviewed private debug APK is `app-debug-context-assist-ui.apk` (SHA-256 `1B8DBEDF5C494826A477510290D34825BCF1A0360D48B3C702462C7025A60E81`). The all-flags-off debug APK is `app-debug-all-flags-off.apk` (SHA-256 `CE434E8C33197526E21AFE9491F0D33E494E22F9D71096E04536B62D7C1A8080`). These APKs may embed local service configuration; keep them private and never commit them.

## Validation and limits

- On this source, the Context Assist/Gemini debug configuration passed 150/150 JVM tests and debug, release, and Android-test APK builds. An explicit all-flags-off debug configuration also passed 150/150 JVM tests and its debug APK build.
- The representative Xiaomi M2101K7AG phone showed three complete predictions in the compact strip without ellipsis; the user accepted that visual layout. Earlier checks confirmed the raw multiword card and that predictions stay visible during signing. These are interaction checks, not recognition-accuracy evidence.
- The latest Android test companion could not be installed on the phone (`INSTALL_FAILED_USER_RESTRICTED`), so its updated UI assertion was compiled but not executed. An earlier combined Context Assist instrumentation class also had an order-dependent Activity launch timeout, although focused tests passed individually before the latest UI polish.
- Broad F22 device smoke, controlled performance/thermal checks, continuous natural signing, cross-signer phrase accuracy, and contextual benefit remain unverified. The Stage 3 physical pilot found wrong Top-1 labels often absent from Top-5; context must not silently rewrite raw communication. Production cloud credential transport remains deferred.

## Restore and next-work rule

Use `git switch -c <new-experiment-branch> apphear-text-to-asl-context-assist-ui-2026-10-04` or create a worktree from that tag. If an experiment fails, return to the tag without resetting or rewriting the preserved branch. Restore the exact phone-reviewed private debug APK from the ignored local archive when it is available; verify the APK SHA-256 before installation. If that local archive is lost, rebuild from the tag with the same local development flags and credential, but treat the rebuild as a new binary requiring verification.

Do not interpret this working source baseline as a release promotion or a claim that recognition accuracy has improved. Future experiments must keep their own branch, validation record, and rollback artifact.
