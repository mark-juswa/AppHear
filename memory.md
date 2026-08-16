# Memory — RU-D7 Phone B-vs-C Workflow Ready

Last updated: 2026-08-15 22:39 +08:00

## What was built

- RU-D6 completed successfully across A/B/C and seeds `101/202/303`; Candidate C is the strongest
  validation branch but is not approved for deployment.
- Prepared RU-D7 as a bounded 26-attempt fresh-phone confirmation: 13 signs with two natural
  attempts each, including the five repair targets and regression/confusion controls.
- Added the isolated queue, guarded PowerShell install/collection/pull/replay workflow, B/C offline
  evaluator, focused tests, and operator runbook.
- Frozen comparison checkpoints are B `RU-D3 cleanup seed 303` and C `RU-D5 Sem-Lex seed 202`.

## Decisions made

- Capture every phone attempt once with the unchanged default-off RU-D1 diagnostic APK. Never
  record separate attempts for B and C.
- Replay byte-identical reconstructed actual `[96,258]` windows and the same manually annotated
  oracle windows through both checkpoints offline.
- Keep the deployed recognizer's recorded window/argmax/S7 parity as the attempt trust gate.
- Phone attempts remain withheld evaluation evidence and must never enter training.
- No deployment, retraining, additional data, S5/S7/threshold/schema/architecture change is
  authorized during RU-D7.

## Problems solved

- Added explicit actual-window and oracle-window reporting for Top-1, target rank, Top-5,
  confidence/margin, and unchanged-policy S7 simulation for both B and C.
- Guarded the S5-no-inference case: an attempt such as WHO can have no actual S6 window without
  aborting the batch; oracle replay remains available.
- Model and queue hashes are frozen, both checkpoints pass `[1,96,258] -> [1,96,236]` smoke, and
  focused RU-D1/RU-D7 tests, Ruff, PowerShell parsing, and the isolated preflight pass.

## Current state

- RU-D7 is prepared at `artifacts/recognition_upgrade/ru_d7/phone_bc_01` with no protected-test
  access and no production behavior change.
- No APK has been built/installed for this session and no RU-D7 phone attempts have been collected.
- The queue has 26 attempts covering KNOW, WHO, WE, COME, LEAVE, HELLO, SISTER, KEEP, MOVE, PUT,
  GOOD, NOW, and HAVE.
- The operator runbook is `context/recognition_upgrade/RU_D7_PHONE_BC_RUNBOOK.md`.

## Next session starts with

Connect exactly one authorized phone, then run:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& '.\eval\runtime_diagnostics\run_ru_d7_phone_bc.ps1' -Command Install
```

After `INSTALL COMPLETE`, start the prepared queue:

```powershell
& '.\eval\runtime_diagnostics\run_ru_d7_phone_bc.ps1' -Command Collect `
  -SignerId 'withheld_phone_01' -SessionId 'ru_d7_phone_bc_01'
```

Stop after all 26 attempts are saved and report completion before pull/annotation/replay.

## Open questions

- Whether Candidate C improves phone-domain KNOW, WHO, and LEAVE while preserving WE.
- Whether C introduces false WHO attraction on SISTER or KEEP or harms healthy controls.
- Whether COME remains poor for both B and C under oracle spans; if so, close the Sem-Lex COME
  repair path under the current representation/model.
- Final outcome remains one of: promote C as research baseline, keep C experimental/mixed, or C
  fails phone transfer. C must not be deployed automatically under any outcome.
