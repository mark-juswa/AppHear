# Fingerspelling reported three-letter limit — 2026-10-08

The reported display cap could not be reproduced. No recognition or display code was
changed, and the existing private app remains installed. Two focused regression tests
were added; only the test APK was installed on the Xiaomi.

## Measured result

- The unmodified HeldLetterPolicy accepted 104 letters, exceeding both three characters
  and the 64-observation inference-window bound (which does not bound spelling length).
- The existing RecognitionActivity rendered the same 104-character spelling on the
  Xiaomi: five lines, 770 px text width, 348 px text/layout height; final line ends at
  character 104, no ellipsis. CURRENT SIGN remained Z separately.
- 171 host tests passed, five phone tests passed, including owner/confirmation/clear and
  Context Assist regressions. All 660 other inventoried app source/assets/build files
  were unchanged. Candidate01, models, Adapter, camera and WORD were not edited.

## Actual session evidence and uncertainty

The pre-test diagnostic was preserved in `reported_session.json`: it contains additions
E, E, A, producing EEA. Subsequent events preserve EEA; most decode blank or latched A.
There are also three Y results spanning about 1.0496 seconds which did not append.
That means it would be incorrect to attribute every rejection solely to instability.
The existing diagnostic does not record callback policy epoch, current missing-hand
state or candidate state; stale/absence rejection versus stability rejection cannot
be distinguished from these saved records. No three-letter branch exists in the code.

The supervisor was asked whether CURRENT SIGN shows the fourth letter while RECOGNIZED
stays at three, or is blank/incorrect. This clarification is pending. Recognition
thresholds must not be loosened merely to produce a longer but incorrect spelling.

## Files and evidence

Active checkout: `C:/Users/Gigabyte/.codex/worktrees/fingerspell-continuous-oct05/5. Apphear3`.
Added long-spelling checks to `HeldLetterPolicyTest.kt` and
`ContinuousFingerspellInstrumentedTest.kt`. Research orchestration:
`tools/fingerspelling/long_spelling_check.py` and `long_spelling_record.py`.
Evidence: `artifacts/fingerspelling_long_spelling_01/validation.json`,
`device_layout.json`, `before.json`, `reported_session.json`, `build_checks.log`,
`original_device_checks.log`, `preservation_device_checks.log`.

This proves storage/rendering capacity, not real-signing recognition accuracy.
