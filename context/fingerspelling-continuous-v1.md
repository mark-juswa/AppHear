# Fingerspell automatic held-letter runtime v1

Approved October5 baseline `b48594c4942d9e9ac0d94ff96396e80b9f049c0a`.
Authoritative app source:
`C:/Users/Gigabyte/.codex/worktrees/fingerspell-continuous-oct05/5. Apphear3`,
branch `codex/fingerspell-continuous-oct05`. Do not patch the preserved manual worktree.

Supervisor-approved automatic held letters, no Start/Done, persistent Settings selection,
exclusive WORD/FINGERSPELL owners. Use confirms the spelling draft. Not fluent-spelling accuracy.

Frozen V2.1 epoch034 geometry/Adapter.v1 `[T,405]` unchanged. Decoder:
`apphear.fingerspelling.single_letter_ctc.v1`; exact singleton CTC, blank27/.5 once, empty/SPACE
refusal. Beam10/greedy remain intact in manual rollback. No model or feature change.

`HeldLetterPolicy` consumes deep-copied CommonObservation raw, retains chronological genuine
observations and masks, and requests a bounded window. A fresh frozen Adapter v1 recomputes
dt/motion for every requested window. No generated landmarks or forward fill.

`ContinuousFingerspell` has exactly one inference worker, no backlog, generation/epoch result
guards; state returns to the camera executor. Transition to WORD joins actual in-flight invocation
via the inference lock. WORD consume remains synchronous and unchanged; no WORD frames enter
the fingerspell model. Shared Candidate01 remains the same perception producer.

Policy asset `fingerspelling/continuous_policy.json`,
`apphear.fingerspelling.held_letter_policy.v1`: window4000ms/max64; minspan1000ms/min4usable;
interval500ms;3same decodes/min1000ms; repeated-letter rearm800ms/min3missing observations.
Operational timing defaults, not correctness confidence or calibrated acceptance thresholds.
Tracking loss can resemble deliberate lowering. Wrong letters can stabilize; confirmation required.

Settings choice defaults WORD and is available only in opted-in fingerspell builds. Unsupported
saved modes fall back to WORD; a failed selected fingerspell model never silently routes to WORD.
Row present in both Profile and Settings. Flags `fingerspell=true`, `fingerspellContinuous=true`;
default/release false. Continuous=false restores manual flow in the same October5 shell.

Engineering gates:169 private/default unit checks;54 exact singleton parity fixtures;
14 model/1246Adapter raw device checks;2device Settings/automatic-owner tests;3local Context Assist
checks; protected sources/models/237priorAPK assets identical. Supervisor confirms automatic flow
and WORD restoration. No qualified signer/all26 accuracy or fluent evaluation. No retraining.

Gate report `docs/apphear-fingerspelling-continuous-gate-2026-10-08.md`; evidence
`artifacts/fingerspelling_continuous_01/summary.json` in the research workspace.


## Fingerspell presentation clarification — 2026-10-08

CURRENT SIGN = presentation-only latest valid singleton decode (`currentLetter`); RECOGNIZED =
confirmed + stabilized draft spelling. Tentative letter does not change accumulation. No new feature
schema, threshold or decoding policy. Missing/empty/reset clears current display; stale results
cannot overwrite it. This supersedes earlier hiding of CURRENT SIGN. Controls remain hidden.
Source: HeldLetterPolicy / FingerspellSnapshot / ContinuousFingerspell.emit / Activity renderer,
active October5 checkout.170host and5Xiaomi checks pass. WORD/model/camera contracts unchanged.
