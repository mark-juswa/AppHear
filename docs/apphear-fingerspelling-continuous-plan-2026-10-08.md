# Automatic held-letter Fingerspell implementation

Approved baseline: `baseline/apphear-text-to-asl-context-assist-ui-2026-10-05`,
`b48594c4942d9e9ac0d94ff96396e80b9f049c0a`.
Target worktree: `C:/Users/Gigabyte/.codex/worktrees/fingerspell-continuous-oct05/5. Apphear3`.
The October 4 manual integration worktree and private single-letter APK are rollback evidence.

The supervisor approved automatic **held-letter** capture and confirmation. This is not a fluent
continuous-spelling accuracy claim. The three prior A/M/Y captures are useful wiring evidence,
not proof of all-letter accuracy. Continuous CTC previously had weak letter discrimination and
uncontrolled transitions/repetition. The new flow constrains one rolling-window inference to
one letter using the exact existing single-letter CTC probability calculation.

## Contract

One common CameraX/Candidate01 producer; exactly one recognition owner. WORD receives its existing
observations unchanged when selected. FINGERSPELL consumes the existing seam instead of WORD.
Persistent Settings choice defaults to WORD, unsupported choices resolve to WORD. If a selected
fingerspell model cannot load, do not silently run WORD. Require the user to select WORD.

Automatic mode has no Start/Done buttons. Hold a letter until it appears in the unconfirmed preview;
change to a different held letter, or lower the hands until sustained missing evidence rearms a
repeated letter. Use confirms the complete preview. Retry clears the draft; Clear clears spelling.
The WORD SentenceBuilder and its stored sentence are untouched.

Timing policy is an explicit versioned configuration, **engineering defaults**, not calibrated
correctness confidence: at most four seconds/64 real observations; one second/four usable
observations before inference; at most one request per 500 ms; three same-letter decodes spanning
one second; missing evidence for at least 800 ms and three observations rearms repetition.
Missingness can also arise from tracking loss, so repetition boundaries are not linguistically proven.
J/Z remain motion letters; a held-letter sequence can include their movement, but performance is unproven.

Retain independent raw arrays, select chronological real observations only, and rederive Adapter v1
dt/motion from the selected window. No feature schema, geometry, model, decoder penalty, pixel math
or training change. The frozen V2.1 checkpoint remains the actual model. One inference worker,
no backlog; generation/epoch guards suppress stale results. Switching WORD waits for an in-flight
fingerspell invocation to finish before changing ownership. Lifecycle pause invalidates requests.

## Gates

1. Unit tests: bounds, chronology, raw-array lifetime, timing derivation, stability, no-input,
   same-letter latch/rearm, stale result rejection, Settings fallback.
2. Frozen singleton decoder/model parity stays unchanged. No recognition accuracy improvement claimed
   by synthetic replay or by a nonexpert supervisor.
3. Android instrumentation: Settings persistence, automatic preview, confirmation, Clear/Retry,
   no fingerspell inference in WORD, preserved WORD sentence, no Start/Done UI.
4. Xiaomi bounded CameraX smoke: automatic letters reach preview, timing/cadence measured, mode
   switching and Settings usable. Refuse any claim that all A–Z or fluent spelling is validated.
5. Hash inventory: protected WORD/Context/perception/model files and October 5 Text-to-ASL changes
   remain byte-identical. Existing Candidate01FrameAnalyzer seam is copied unchanged from the prior
   validated integration; no new perception modification.

Opt-in flags: `fingerspell=true`, `fingerspellContinuous=true`. Both are false for release;
continuous false restores the existing manual integration behavior. No S2-R2 reuse or modification.
