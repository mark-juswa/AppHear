# Text-to-ASL alphabet fallback pilot results

Status: flagged pilot installed; early-submit, cold-load leave/reopen, and all-26-letter handset checks passed on M2101K7AG. Default/release remain OFF.

The approved change restores whole-word fingerspelling for words without any sign GLB in the selected New catalog. Existing word/phrase matches still win: New still plays Original HELLO for `hello`. New spells an unknown `cat` as C-A-T using New-character letter clips; standalone `I` remains the existing I/Me sign, while I inside an unknown word is letter I. Original never borrows New letters. Since its installed 102-entry catalog contains only A/B, a word needing another Original letter is reported unsupported as a whole token in the flagged build.

## Asset and implementation

`tools/text_to_asl_assets/alphabet-fallback.mjs` verifies the 24 optimized C–Z source hashes, exact decoded rendering resources, matching skeleton/node layout, and each added animation channel. It appends them to the prior 27-sign-plus-idle bundle in a separate `aslAlphabet` asset source. The prior 28 animation records and compressed binary prefix remain exact. The result has 52 named animations, 61,791,300 bytes (58.93 MiB), SHA-256 `645da29f5e8a24dc7da2f4b6e23ca2e87fb91254958f5053ba0281080ec0a524`, and glTF validation with zero errors and the same 32 warning categories as the prior bundle. The 102 Original GLBs and previous pilot GLB remain untouched.

`aslAlphabetFallback` is a separate default-off debug flag requiring the New idle and character selector flags. The schema-3 manifest adds 24 guarded letter records. The loader exposes them only through a dedicated letter map, avoiding alias collision with pronoun I. The planner's token-atomic fallback is active only under this flag; the default-off planner keeps its existing behavior. The player still uses two viewers and pins the selected New shared source, with no new runtime library or recognition change.

## Verification

- Twelve player tests and 132 JVM tests pass in the flagged build. The ordinary default-off build also passes 132 JVM tests.
- APK inspection confirms one experimental shared GLB, all 102 Original GLBs byte-identical in pilot and default, and no pilot payload in default. The tested APK is 325.17 MiB; default rollback is 307.65 MiB.
- The pilot was installed with `adb install -r`, retaining app data. Two isolated on-device catalog/preference tests passed; the test companion was removed.
- The first manual run exposed a cold-load request race. The shared New idle took 11,223 ms. A phrase submitted before it was ready produced model `load` callbacks with empty animation lists and skipped clips. `/recover` classified this as an isolated player readiness bug. A focused correction now queues early Sign It input until idle starts and ignores empty-animation load callbacks. The corrected pilot builds and tests pass, is installed, and passed the user's immediate-submit retest. See `artifacts/text_to_asl_alphabet_20260928/recovery-note.md`.
- After reopening the first build, the user reported that the alphabet sequence, Replay and controls worked. The scoped log confirms two complete `hello cat zebra` runs: HELLO on Original, C-A-T and Z-E-B-R-A on New, and New idle after each. New warm transitions were 22–91 ms; no failures in those two runs. This is a one-phone diagnostic, not a latency guarantee.
- In the corrected build, the user tapped Sign It while New was still loading and confirmed the complete phrase and Replay worked. The scoped log independently confirms the first run in order, New idle returning, and zero failures. That run's New idle cold load was 12,015 ms; later sign switches took 32–70 ms. One uncontrolled paired memory sample while the app and renderer were resident was 292,653 + 455,644 KiB PSS (about 731 MiB combined).
- The latest lifecycle correction restarts New idle when Text-to-ASL is reopened after leaving during its cold load. The user confirmed reopening then spelling C-A-T. On the same installed build, the user visually accepted all 26 letters. The final scoped phone log confirms A–Z started and finished in order, then New idle started; no playback failure was logged. That particular cold idle took 7,342 ms and letter-switch loads were 24–163 ms. These are diagnostic observations from one phone.

## Remaining gates and rollback

The larger 58.93 MiB GLB has a visibly slow cold load on this phone. The readiness fix prevents early input loss but does not reduce that load time. Controlled cold-load p50/p95, frame pacing, paired app/WebView memory, low-RAM/thermal use, broad F22 smoke and live account tests remain open. Keep default/release OFF and do not claim production readiness.

The immediately prior phone-working idle pilot is saved as `artifacts/text_to_asl_alphabet_20260928/previous-working-pilot.apk`. The new pilot and ordinary default-off APK are saved separately. The final pilot SHA-256 is `82c5298f218efb3c5184b3923672787f46843267e913aeb7c00d517a2829c5d5`; the default rollback SHA-256 is `a61c09d0b254753d44d992739734467c5a7e8d1f0363f317ad96b9b5dc57a3b7`. Selecting Original is an in-app character fallback; installing the prior pilot with `adb install -r` is the exact code rollback.

## /review

Plan alignment: PASS for New A–Z fallback, known-sign precedence, Original isolation and flagging. System integrity: PASS; no recognition schema/version, S4/F math, model, account, camera or navigation change. Offline gate: PASS. Critical: 0. Important: 1 — cold-load and broader device performance/F22 gates. Recommendation: retain as a user-test pilot and keep default/release OFF.
