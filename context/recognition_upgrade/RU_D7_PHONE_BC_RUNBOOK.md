# RU-D7 Bounded Fresh-Phone B-vs-C Confirmation

**Status:** workflow prepared; collection has not started.

## Frozen comparison

- B: RU-D6 `B_ru_d3_cleanup/seed_303/best.keras`.
- C: RU-D6 `C_ru_d5_semlex/seed_202/best.keras`.
- Capture: unchanged RU-D1 debug-only Android recognizer and schema 3.0 `[96,258]` diagnostics.
- Each phone attempt is captured once. B and C run offline on the same reconstructed windows.
- Phone attempts remain evaluation-only and must never enter training.

The panel contains KNOW, WHO, WE, COME, LEAVE and HELLO, SISTER, KEEP, MOVE, PUT, GOOD, NOW,
HAVE. Each receives two natural attempts, interleaved in a 26-attempt queue. A clearly invalid
capture may later be repeated under a new explicitly labeled session, but this launcher does not
silently add repetitions.

## Collection

With exactly one authorized phone connected, install the verified diagnostic APK:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& '.\eval\runtime_diagnostics\run_ru_d7_phone_bc.ps1' -Command Install
```

Then start the queue:

```powershell
& '.\eval\runtime_diagnostics\run_ru_d7_phone_bc.ps1' -Command Collect `
  -SignerId 'withheld_phone_01' -SessionId 'ru_d7_phone_bc_01'
```

For every READY screen: start at rest, long-press CLEAR, perform the displayed sign once at natural
speed, return fully to rest, wait about one second, and long-press CLEAR to save. Queue advancement
never starts recording. If collection stops, rerun with `-StartAt <current order>`; already saved
attempts are preserved.

Successful collection ends with: `All 26 diagnostic attempts are saved.`

## Pull and bounded review

```powershell
& '.\eval\runtime_diagnostics\run_ru_d7_phone_bc.ps1' -Command Pull
& '.\eval\runtime_diagnostics\run_ru_d7_phone_bc.ps1' -Command MakeAnnotations
```

The second command requires exactly 26 bundles from session `ru_d7_phone_bc_01` and creates
`artifacts/recognition_upgrade/ru_d7/phone_bc_01/annotations.csv`. Review each bounded evidence
folder, enter processed onset/release IDs, mark performance validity, and record whether a required
hand was visibly present during a MediaPipe miss. Invalid attempts are rejected rather than forced
into the B/C comparison.

## Replay after annotations are complete

```powershell
& '.\eval\runtime_diagnostics\run_ru_d7_phone_bc.ps1' -Command Replay
```

The replay first verifies the captured deployed-model window hashes, argmax parity, and S7 parity.
Only trusted attempts continue. It then runs the identical actual windows and independently
constructed oracle windows through B and C, applies the unchanged current S7 policy offline, and
writes:

- `reports/ru_d7_capture_diagnostics.csv`
- `reports/ru_d7_attempt_bc.csv`
- `reports/ru_d7_class_summary.csv`
- `reports/ru_d7_phone_bc_report.json`

The report deliberately leaves the promotion category for consolidated evidence review. It never
deploys C or authorizes training, calibration, threshold changes, or another data cycle.
