# Automatic held-letter Fingerspell — engineering gate

Implemented and installed as an **experimental automatic held-letter flow**. It is not validated
fluent continuous spelling and it is not a newly accurate A–Z classifier. The supervisor approved
this interaction, confirmed Settings/automatic operation works, then confirmed `WORD works`.

## Baseline and preservation

- Approved branch/tag: `baseline/apphear-text-to-asl-context-assist-ui-2026-10-05`.
- Base HEAD: `b48594c4942d9e9ac0d94ff96396e80b9f049c0a`.
- Development branch: `codex/fingerspell-continuous-oct05` (uncommitted development changes).
- Authoritative application worktree:
  `C:/Users/Gigabyte/.codex/worktrees/fingerspell-continuous-oct05/5. Apphear3`.
- Existing manual integration:
  `C:/Users/Gigabyte/.codex/worktrees/fingerspell-oct04-integration/5. Apphear3` remains intact.
- Research workspace remains `F:/ASL DATASET/5. Apphear3`; unrelated dirty work was preserved.

Verified 626 protected October 5 baseline files unchanged, 648 prior-manual source/files unchanged,
the frozen integration math/model/decoder files unchanged, and all 237 existing APK assets
byte-identical. Only the new continuous policy asset was added. All October 5 Text-to-ASL files
remain intact. The existing Candidate01FrameAnalyzer observation-owner seam was copied byte-for-byte
from the validated manual integration: no new perception math, thresholds, models or pixel changes.

WORD `PhoneProductionSession.consume` is synchronous and camera-executor confined. The shared
owner callback sends observations to either its unchanged consume method or fingerspelling.
FINGERSPELL inference has one separate worker and a lock: entry to WORD waits until any actual
fingerspell invocation completes. Pending/stale fingerspell results cannot update WORD UI.
Common Candidate01 perception remains active in both modes. Model loading remains async; retaining
both models in memory does not run both recognizers. WORD sentence storage is not used for spelling.

## Frozen inference identity

V2.1 geometry-only epoch034 checkpoint:
`3f92287c5ee82b2e0de1d396c4d27fe3b0efaed8af23b79b878740a56f1af638`.
TFLite:
`e78de274b967acf0ea9d30bd3f3ac4422a1ef8ebdd95c8676b57dd05fed75c4c`.
Manifest:
`8edc998728fa41883abacbc8382359d6d61621bc259da78ca7c2ab6f8126d01e`.
Adapter v1 `[T,405]`, masks, frozen visual/geometry rollback and model weights are unchanged.
Actual automatic decoder is the previously validated exact singleton CTC decoder, with blank27
penalty0.5 once. Frozen beam10/greedy remain in the manual diagnostic/rollback path. Automatic mode
does not run beam decoding on every window, introduce a dictionary, or use language priors.

## Behavior and policy

Settings → Recognition mode persists WORD/FINGERSPELL; default and unsupported-build fallback WORD.
The row exists in both Settings and the embedded Profile/Settings host.

FINGERSPELL has no Start/Done. Hold a letter until it appears, then change letters. Sustained missing
hand evidence rearms the same letter. New letters append only to an unconfirmed draft. Use confirms
the draft; Retry removes the draft while preserving confirmed spelling; Clear removes both.
Returning to WORD preserves the WORD sentence. Lifecycle pause cancels pending results and draft.

Policy `apphear.fingerspelling.held_letter_policy.v1`: 4-second/64-observation bounded raw window;
minimum one-second span and four usable observations; requests at least500ms apart; three same-letter
decodes over at least1second; same-letter rearm after at least800ms/three missing observations.
These are operational defaults, **not calibrated correctness thresholds**. Observations are real,
chronological, deep-copied; invalid data/masks remain unchanged. Adapter v1 rederives dt/motion from
each selected raw window. No interpolation, forward filling, fabricated frames or model retraining.

## Validation

| Gate | Result |
|---|---|
| Private Android unit suite |169 tests,0 failures/errors/skips;8 new policy/Settings tests|
| Default build unit gate |169 pass; default/release fingerspell flags false|
| Singleton Python↔Xiaomi fixtures |54 exact; maximum log-mass discrepancy4.547e-13|
| Frozen model/Adapter device fixtures |14 sequences/1246 raw observations; Adapter max0|
| Keras↔Android logits |maximum2.6226e-5|
| Host TFLite↔Android logits |maximum1.3351e-5|
| Greedy/beam decoded fixtures |0 mismatches; same unchanged model/decoders|
| Masked-padding check |14 cases; maximum5.722e-6|
| Local Context Assist regression |3 tests pass; no remote call required|
| Automatic ownership/confirmation/Settings hosts |2 Xiaomi tests pass; synthetic, not accuracy|
| Physical supervisor smoke |automatic interaction works; WORD controls/camera restored|
| Protected hashes/assets |pass; no WORD/Context/model/Adapter change|

The initial Settings rollout crashed because the shared renderer also runs inside Profile and
the new row was initially present only in Settings. Corrected by adding the same row to both
layouts and testing both hosts, including their choice dialogs. Earlier engineering failures
were Kotlin statement separators, synthetic body-array dimensions, and a test that asserted owner
readiness before asynchronous startup completed. No model/feature correction was needed.

## Runtime and recognition limits

In one captured active episode:19 automatic inference events, approximately4.79 delivered
observations/s; model p50/p95/max49.94/73.47/74.50ms; singleton decoder5.05/8.34/9.04ms.
Worker-start to camera-state-callback p50/p95/max210.50/221.17/226.15ms, including camera-executor
callback wait. It is not pure model inference, end-to-end letter latency, or Done latency.
Waiting for stability adds roughly seconds. No paired cadence experiment was performed, so this
does not prove that CPU sharing has zero cadence impact. Peak memory was not measured.

The supervisor did not supply exact preview text. Diagnostics contain stabilized raw emissions
including `SABSSC`, then `YZIE` after draft resets. They do **not** establish correct `AMY`, qualified
ASL execution, or all26 accuracy. Some identical letters were appended after rearm/reset. Without
complete raw/gesture annotation we cannot distinguish deliberate lowering/Retry from tracking loss.
Holding the same predicted letter suppresses duplication only while the latch remains armed.
Tracking loss can falsely rearm, and wrong predictions can stabilize. Confirmation remains essential.

The original cadence diagnostic retained observations across activity pauses and therefore could
produce a misleading final aggregate rate (0.666/s). Do not interpret that as throughput. The final
build resets cadence windows at mode/lifecycle transitions and stores a separate last-active record.
The reported4.79/s is the earlier bounded active sample; the correction did not change recognition.

## Changed files and reproduction

Application changes in the authoritative worktree:

- `android/app/build.gradle.kts` — separate debug continuous flag, default/release false.
- `RecognitionActivity.kt` — existing finger integration, saved mode/lifecycle, automatic controls.
- `fingerspelling/FingerspellRuntime.kt` — delegates automatic mode; preserves manual mode.
- `fingerspelling/HeldLetterPolicy.kt`, `ContinuousFingerspell.kt` — new controller/worker.
- `data/settings/RecognitionModeSettings.kt` — new preference/default resolver.
- `ui/settings/SettingsContent.kt`, `ui/profile/ProfileFragment.kt` — mode choice/availability.
- `fragment_settings.xml`, `fragment_profile.xml`, `row_setting_recognition_mode.xml`, `strings.xml`.
- `HeldLetterPolicyTest.kt`, `ContinuousFingerspellInstrumentedTest.kt`.

Previously validated fingerspelling classes/tests/fixtures were staged intact onto October5;
the current analyzer seam is identical to the manual source. No production WORD class was edited.
Research helpers: `tools/fingerspelling/continuous_{stage,port,preservation,report}.py`, Kotlin
templates under `tools/fingerspelling/continuous_android/`, `android_continuous_build.ps1`.

Build from research root:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\tools\fingerspelling\android_continuous_build.ps1 -Configuration private
```

Private final APK (phone-only; contains authorized local service configuration):
`artifacts/fingerspelling_continuous_01/private_apks/app-debug-private-continuous.apk`.
SHA `07a79ab54fd923cfacafe4de976548ca871673bcaef696d576b96dd80e500872`.

Rollback by installing the intact manual APK:

```powershell
& 'D:\AndroidStudio\Android\Sdk\platform-tools\adb.exe' -s 3ab64582 install -r 'F:\ASL DATASET\5. Apphear3\artifacts\fingerspelling_single_letter_01\private_apks\app-debug-private-single-letter.apk'
```

That rollback also restores the previous October4 app shell. Rebuilding this October5 worktree
with `fingerspell=true` and `fingerspellContinuous=false` instead keeps October5 and restores manual
Start/Done behavior. Release/default leave fingerspelling unavailable and WORD authoritative.
Staging scripts refuse repeat staging; use the build wrapper for subsequent builds.

Evidence directory: `artifacts/fingerspelling_continuous_01/`: `summary.json`, preservation before/after,
device numerical parity JSONs, initial/fixed/final flow test logs, camera smoke JSONs, build logs/APKs.

## Review decision

Plan alignment and protection/engineering gates pass. No critical unresolved integration defect
found. Important limitations: uncalibrated stability/rearm settings, no all-letter/held-out signer
accuracy gate, possible tracking-loss repetition, no controlled cadence comparison or peak memory.
These remain explicit experimental limitations; no production-recognition promotion is claimed.

Retain **experimental automatic held-letter Fingerspell with confirmation**. WORD and all frozen
recognition components remain protected. No training, new dataset, visual experiment or decoder
tuning follows this task automatically.
