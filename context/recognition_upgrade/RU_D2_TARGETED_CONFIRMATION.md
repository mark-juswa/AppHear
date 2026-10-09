# RU-D2 Targeted Failure Confirmation

**Status:** first paired device collection analyzed; result in
`artifacts/recognition_upgrade/ru_d2/RU_D2_TARGETED_CONFIRMATION_RESULT.md`.

RU-D2 reuses the default-off RU-D1 trace, rolling evidence, exact `[96,258]` reconstruction, and
actual-span/oracle-span analyzer. It does not change production recognition, S4, S5, S6, S7, the
model, datasets, or feature schema.

## Question

If obvious capture, hand-detection, positioning, and boundary problems are reduced while preserving
the AppHear target variant, does each unresolved sign still fail?

## Frozen paired queue

`ru_d2_targeted_confirmation_01.csv` contains 14 attempts: adjacent NATURAL and CONTROLLED
conditions for `HAVE`, `TODAY`, `KNOW`, `WHO`, `NOW`, `WE`, and `LEAVE`. Each row is one sign
performance only. `TABLE` is excluded because both RU-D1 attempts failed cross-runtime argmax
parity. `GOOD` and `HELLO` are omitted because RU-D1 already established them as repeated healthy
controls.

The controlled condition changes framing, hand visibility, clean rest boundaries, and execution
consistency only. It must not substitute, exaggerate, or invent a different sign variant.

## Collection

```powershell
.\eval\runtime_diagnostics\run_ru_d1_batch.ps1 `
  -SignerId signer_01 `
  -SessionId ru_d2_targeted_confirmation_01 `
  -QueuePath .\context\recognition_upgrade\ru_d2_targeted_confirmation_01.csv
```

Wait for the labeled READY screen. Follow its NATURAL or CONTROLLED instruction, long-press CLEAR,
perform the sign once, return fully to rest, wait about one second, and long-press CLEAR to save.
Queue advancement never begins recording.

The first run exposed an ADB argument-quoting defect: free-text READY instructions containing spaces
were split by the device shell, so numeric order extras after that argument were lost. The launcher
now transports instructions as Base64 and its Android display path decodes them; tests/build pass.
This correction is diagnostic-only and does not retroactively invent missing condition metadata.

## Analysis contract

Pull all 14 session bundles together. Reject structurally incomplete, visually invalid, variant-
mismatched, or replay-parity-failing attempts. Annotate tight visible sign spans and rerun actual
versus oracle replay. The consolidated report must compare each natural/controlled pair and state:

- whether controlled capture materially improved hand/pose coverage and S5 boundaries;
- whether oracle replay rescued the target;
- whether target rank is within Top-5;
- dominant confusion;
- practical outcome: perception/capture, S5, S6 ranking, likely data/variant/generalization,
  possible representation limit, mixed/insufficient, or healthy when clean;
- only the next justified repair action, without implementing it.

Classification beyond the RU-D1 stage labels is conservative: data/variant/generalization or
representation limitation requires consistent clean-condition evidence plus prior project evidence;
otherwise the result stays S6 or mixed/insufficient.
