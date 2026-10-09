# Fingerspell CURRENT SIGN / RECOGNIZED correction

Date: 2026-10-08. Active app: October5 `fingerspell-continuous-oct05` checkout,
base `b48594c4942d9e9ac0d94ff96396e80b9f049c0a`.

The supervisor clarified the intended UI. Hiding CURRENT SIGN was a misunderstanding.
This correction supersedes the earlier display-cleanup instruction/document to hide that column.

- CURRENT SIGN remains visible and shows the latest valid one-letter model decode.
- RECOGNIZED shows the accumulated spelling: confirmed text plus stabilized draft letters.
- A tentative changing letter updates CURRENT SIGN without being added prematurely to RECOGNIZED.
- Missing usable hand evidence, an empty decode or session reset clears the current letter to the
  existing idle placeholder. Stale results cannot update it. Accumulated spelling remains intact
  until the existing Clear/Retry/confirmation actions act on it.
- Experimental controls stay hidden. Existing Hear confirmation and Clear behavior remain.

Implementation adds a presentation-only `currentLetter` field in HeldLetterPolicy and
FingerspellSnapshot, passes it through ContinuousFingerspell.emit, and restores the Activity column.
The field never controls inference, stabilization, accumulation, repeated-letter rearm or decoding.
No new thresholds, model changes, WORD behavior or camera configuration changes.

Changed app files: RecognitionActivity.kt; fingerspelling/FingerspellRuntime.kt,
ContinuousFingerspell.kt, HeldLetterPolicy.kt; HeldLetterPolicyTest.kt and
ContinuousFingerspellInstrumentedTest.kt. Exact source hashes: artifacts/fingerspelling_current_sign_01.

Validation:

- 170 host tests pass, including separation of tentative/current and accumulated letters,
  stale-result rejection, missing/empty/reset behavior and existing held-letter tests.
- Five Xiaomi UI/owner/Settings/Context Assist tests pass. The device test asserts CURRENT SIGN
  `Y` alongside RECOGNIZED `AMY`, then tentative CURRENT SIGN `B` while RECOGNIZED stays `AMY`.
- Controls remain absent; normal WORD column restoration and sentence storage checks pass.
- 655 protected existing source/asset files match the before-change inventory. Candidate01,
  feature math, models, decoding, WORD/Context Assist and front/rear camera settings are unchanged.
- Updated private camera-enabled build installed on Xiaomi. Prior private APKs preserved.

Evidence: artifacts/fingerspelling_current_sign_01/validation.json, device_tests.log, build.log,
changes.json, before.json and private_apks. This is a display correction, not an accuracy improvement.
