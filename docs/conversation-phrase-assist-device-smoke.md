# Conversation phrase assistance phone smoke — 2026-09-28

**Historical smoke:** this tested the earlier output-changing MVP. The 2026-09-29 build is
shadow-only; its results are in `conversation-phrase-assist-shadow-report.md`.

Device: Xiaomi M2101K7AG, Android 12. Internal debug APK used `contextPhraseAssist=true` and the fake provider; no remote credential or network request was used. The previously installed APK was saved before testing and restored afterward. Final installed SHA-256 equals the backup: `30bc5822a2bbf0581b085993aea9219bcb41c53cc9277b37c6446ba758f17b23`. No Android test package remains installed.

## Physical interaction

The hearing message “Where are you going?” reached the completed-message seam; logs showed three cached fake reply candidates. RecognitionActivity loaded the protected Candidate01/S2-R2 backend. One live attempt committed GO and HOME once each and returned to IDLE/READY after each. An earlier unintended RIGHT3 commit was already in that Deaf turn, so Hear correctly abstained: raw and displayed text were `RIGHT3 GO HOME`, with no contextual phrase forced. The user retried after Clear but reported that the recognizer kept producing wrong words. We stopped physical signing attempts and did not tune S2, admission, re-arm, materializer, or the recognizer.

The observed overlay/camera remained responsive and there was no reported crash. Logs showed roughly 4.8–7.9 processed fps during the first sequence; no paired baseline timing capture was performed, so this is not a slowdown or performance-pass claim. The first GO/HOME sequence demonstrates event delivery and re-arm, not contextual phrase accuracy. The raw fallback is the expected behavior when extra events contradict a predicted two-concept phrase.

## Synthetic Android integration

Two focused instrumentation tests passed on the same phone with the real Android vocabulary asset/configuration and fake provider (`2/2`, zero failures). One test fed `GO`, then `THINK 0.35 / HOME 0.33`: the sidecar preserved raw `GO THINK`, selected supported `GO HOME`, and produced “I'm going home.” The second invoked the real RecognitionActivity Hear action with equivalent synthetic committed events, verified that the sentence area showed the assisted English phrase, and verified that Activity teardown cleared the display override. These tests do not measure live-sign accuracy.

After moving policy loading off the Hear button's main thread, the full connected Android suite passed `15/15`. The default-off JVM suite passed `105/105`, and default-off debug and release APKs both built. The original phone APK was restored and pulled back for comparison; its SHA-256 again matched the saved pre-experiment APK.

## Remaining validation

- A live signed sequence that produces an exact supported phrase or a close Top-5 ambiguity without extra events has not been observed. The assisted result has been demonstrated on the phone with synthetic evidence, not with a physical signed phrase.
- Remote prediction was not exercised because no development credential was configured. Provider exceptions and timeouts pass JVM fallback tests; offline-network phone behavior remains untested.
- Flag-off and release builds pass software regressions, but a separate physical flag-off comparison was not repeated in this session. The prior installed APK was restored bit-for-bit.
- No held-out cross-signer end-to-end phrase evaluation exists. This branch remains an internal experiment and should not be promoted as an accuracy improvement.
