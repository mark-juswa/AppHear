# Recognition coordination v1

Authoritative app: `C:/Users/Gigabyte/.codex/worktrees/fingerspell-continuous-oct05/5. Apphear3`.
Approved base: October5 `b48594c4942d9e9ac0d94ff96396e80b9f049c0a`.
Contract: `apphear.recognition.coordination.v1`; config: `recognition_coordination_policy.json`.

## Inputs and ownership

The coordinator reads actual hearing text and active hearing-turn ID from the existing
ConversationPhraseAssist process owner. It does not read predicted reply text, confidence,
WORD probabilities, fingerspelling logits or transcript labels. The intent matcher recognizes
only the six full-match English rules in the asset (name/place/explicit spelling questions).
Unknown, negated and compound questions retain the current owner; Settings remains the manual fallback.

The existing Candidate01FrameAnalyzer `ownsObservation` seam is authoritative. The bridge runs
on the existing camera executor immediately before that seam, using WORD readiness and current
`handObserved && any valid joint` evidence. Exactly one downstream recognizer consumes each
observation. Candidate01 remains the common producer. No concurrent recognition or score fusion.

Automatic FINGERSPELL entry requires a fresh supported hearing turn, WORD idle, no usable hand
in the current observation, and no response activity already seen. Startup warm-up is not itself
a response; a WORD commitment always counts. Once response activity occurs, the same turn cannot
switch automatically later. Manual override vetoes that turn; asynchronous provider updates cannot
re-arm it. An unsupported/new hearing turn never interrupts active spelling.

## Completion and storage

Existing held-letter capture, singleton CTC and stabilization remain unchanged. CURRENT SIGN
shows the current tentative letter; RECOGNIZED shows stabilized spelling. No Start/Done buttons.
WORD and spelling buffers remain separate. Neither is injected into the other's SentenceBuilder.

The existing speaker/Hear icon while FINGERSPELL opens review of actual confirmed+draft characters.
The recognition screen has no WORD/Spell/Finish chooser buttons; it shows active mode status only.
The existing runtime confirms only if the draft is still identical; generation guards reject
stale actions. Confirm returns to WORD. Only actual A–Z/SPACE text is recorded in conversation
history, through a new stale-turn-checked additive method. A newer question cannot inherit the
old spelling. The last confirmed spelling stays visible in the coordination row; the WORD
recognized card restores its own stored sentence. WORD Hear and advisory matching are unchanged.

Empty spelling cannot finish. Manual preference remains in existing Settings.
There is no silence/missing-hand completion timeout: the same absence is already used to re-arm
legitimate repeated letters. Speaker/Hear review and explicit confirmation is the current end-of-spelling contract.

Activity stop invalidates queued context/confirmation and uses the existing runtime pause.
Settings remains the persisted preferred mode. Context switches are temporary and do not change
that preference; camera switching retains the actual active owner through the existing callback.

## Flag, tests and limits

`-PrecognitionCoordination=true` enables `RECOGNITION_COORDINATION_ENABLED` only in a debug build
with fingerspelling, continuous fingerspelling and Context Assist enabled. Default and release
are false. Existing manual Settings behavior is the rollback; prior APKs are preserved.

No feature math changed. Adapter.v1 remains `[T,405]`; no new train/serve skew test is necessary
for a routing-only component, and all existing feature/model identities were hash-checked.
180 private and 180 default host tests pass. Synthetic Xiaomi routing/confirmation, owner,
buffer, camera and readiness-aware WORD/Context tests pass. See
`docs/apphear-recognition-coordination-2026-10-08.md` and
`artifacts/recognition_coordination_01/validation.json` for exact results and initial failures.

This is bounded English routing, not arbitrary semantic intent understanding. Coordination
does not improve A–Z or WORD recognition accuracy. Names, letter identity, spelling completeness
and confidence are never supplied by context. Accurate all-26/fluent signing remains unproven.


## Automatic UI correction and acceptance evidence — 2026-10-08

Supervisor rejected the screen chooser. Text-to-ASL question -> Sign It -> Reply is the primary
context flow. Existing automatic routing rules remain unchanged. Top speaker/Hear reviews actual
spelling and returns to WORD on confirmation; bottom SPEAK is hearing input, not confirmation.
CURRENT SIGN remains tentative detection; RECOGNIZED remains stabilized construction.

No two-letter cap: current Xiaomi test displays all 104 characters without ellipsis. The original
AM screenshot's acceptance trace was not retained, so its plateau is not yet diagnosed. Additive
acceptance diagnostics expose epoch/hand/candidate/latch state and exact reject reasons without
changing thresholds or model semantics. Flush counter no longer stops when bounded event deque
reaches 64. See docs/apphear-recognition-automatic-ui-correction-2026-10-08.md and phase validation.


### Compact mode header — 2026-10-09
Existing coordination status is a top-row glass pill between Back and Camera, showing only
Fingerspell or Word from the actual exclusive owner. No context reason/last-spelling/instructions
in this indicator; recognition/confirmation/history unchanged. No feature contract change.
181 host +3 Xiaomi engineering checks pass; docs/apphear-recognition-mode-header-2026-10-09.md.
