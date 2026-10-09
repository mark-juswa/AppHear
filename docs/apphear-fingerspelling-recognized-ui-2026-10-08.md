# Fingerspell RECOGNIZED presentation

Same October5-based `codex/fingerspell-continuous-oct05` worktree and frozen V2.1 model.
Requested change: hide experimental detection-screen controls, show letters in the existing
RECOGNIZED card instead of CURRENT SIGN. No model/runtime/ownership/Settings changes.

Only application implementation file changed: `RecognitionActivity.kt`.
Continuous flag skips the experimental panel entirely. In FINGERSPELL the CURRENT SIGN text
column is hidden; RECOGNIZED displays confirmed spelling plus the pending spelling draft.
An empty spelling hides the card using its existing placeholder behavior. Returning to WORD
restores the CURRENT SIGN column and uses unchanged WORD rendering.

The existing Clear button still clears spelling, mode selection stays in Settings. Because the
Use button is hidden, the existing Hear button opens a confirmation dialog for pending spelling.
Cancel does not confirm/speak. Confirm and hear confirms only if the draft/confirmed state still
matches the reviewed text and the owner is still FINGERSPELL; otherwise it asks the user to review
again. WORD Hear/TTS branch and Context Assist code remain unchanged.

Validation: private build/169 host tests pass. The updated device test checks letters appear in
sentenceText/RECOGNIZED, card visible, CURRENT SIGN hidden, experimental button collection empty,
WORD column restoration, unchanged WORD sentence and no spelling inference in WORD. Existing
Settings-host tests retained. No accuracy claim, training, feature/decoder/model change.

Evidence: `artifacts/fingerspelling_continuous_01/ui_polish_before.json`, `ui_polish_changes.json`,
`build_ui_polish.log`. All source files except RecognitionActivity and its isolated device test
match the immediate pre-change inventory. Preserved WORD/model hashes also pass.

Device installation/validation status is recorded separately after connecting the Xiaomi.
