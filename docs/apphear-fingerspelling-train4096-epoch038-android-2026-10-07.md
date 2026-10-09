# TRAIN4096 epoch038 Android transfer

Decision: retain the exact epoch038 checkpoint as the **experimental geometry-only FINGERSPELL candidate**. Keras/TFLite/Android transfer, fixed decoding, rollback, exclusive ownership and bounded phone engineering checks pass. This establishes faithful deployment, not reliable spelling accuracy or phone-domain generalization.

## Repository and preservation

Research checkout: `F:\ASL DATASET\5. Apphear3`, branch `codex/current-working-text-to-asl-baseline-2026-09-29`, HEAD `cc1f3949114d0ed1dab38d4428191151b37df358`.

Authoritative application worktree: `C:\Users\Gigabyte\.codex\worktrees\fingerspell-oct04-integration\5. Apphear3`, detached HEAD `cee71d9f181695847936eb5f3605ea37eab82a95`, corresponding to `baseline/apphear-text-to-asl-context-assist-ui-2026-10-04`. The older F: Android tree was not used for application integration or edited.

Pre-existing dirty/untracked research, dataset, model, Android integration and context work was preserved. No reset, branch switch, merge, discard or commit. Application activity/analyzer/build.gradle changes already present from the earlier integration remain byte-identical. No protected WORD changes are required by this phase.

Before editing, 1,199 protected source/config/model/old-package files were hashed. All remain identical. Six existing fingerspelling implementation/test files outside the eight intended changes also remain identical, including feature math, visual preprocessing and beam decoder. The 235 non-fingerspelling assets packaged in the new and rollback builds are byte-identical. See `preservation.json`, `android_source_identity.json`, `apk_identities.json` and the before-source copies under the evidence root.

## Exact checkpoint and package

| Item | Identity |
|---|---|
| Selected checkpoint | `runs/fingerspelling_train4096_01/best_candidates/epoch_038.keras` |
| Checkpoint SHA256 | `b037e32789f523c043b46c32cdc2ea11f2f600fd35f30ecd672604b6f6947886` |
| Package schema | `apphear.fingerspelling.android.geometry.v1` |
| Candidate | `TRAIN4096_EPOCH038_GEOMETRY_ONLY` |
| Exported model | `artifacts/fingerspelling_train4096_android_01/geometry_sequence.tflite` |
| Model SHA256 | `38d36c8be71a0217defc63b6614f05c6491fdba618d0fffb02aceea8df4f01ff` |
| Model bytes | 825,580 |
| Packaged manifest SHA256 | `11d4236c9d75f0b8c98a2637998764ec2819fec5c89e492fc0f1455f1c0b2b6d` |
| Installed private app APK SHA256 | `c3e075dde2f49edb4014eb705f4ded721d4b6f18f0a78b7446ba6b27d7b6de35` |
| Private test companion SHA256 | `249e035cb51772ded5d693312a5bfa9bf7172da6602d6c1cdf401415129c75d2` |

The exporter checks the selected checkpoint hash **before** loading it. The package contains only `geometry_sequence.tflite` and its manifest. No MobileNet, old residual, quantization, optimization/training update or learned-semantic change. FP32 builtin-only graph, inputs `[1,T,405]` plus `[1,T,1]` mask; output `[1,T,28]`. Adapter v1 configuration/implementation/column hashes are unchanged.

The installed app and companion APK hashes were also measured on the Xiaomi and match the retained private builds exactly (`installed_apk_integrity.json`). The actual session manifest/model loader additionally verifies the geometry graph/package hashes on-device.

Blank index27, penalty0.5 applied once by each existing decoder, prefix beam width10, Top-1 remain unchanged. Greedy remains diagnostic. No Top-N UI, LM, dictionary, insertion bonus, token pruning or decoder tuning.

## Minimal isolated integration

The existing debug `fingerspellArtifactDir` chooses the package internally. The loader accepts only the pinned old residual manifest or pinned new geometry manifest, checks schema/adapter/model hashes, and loads the corresponding graph. Geometry mode never loads appearance, computes quality/dedup/crops, reads RGB through the visual helper, or produces residual inputs.

The existing session takes the package input width (405 or original1559 default). Chronological, finite input and existing512-observation/60-second refusal guards are retained. Manual ownership, Start/Done, preview, Use/Retry/Clear, independent spelling buffer and WORD storage are reused unchanged. Model loading stays off-main; CPU2-thread inference/beam remains on the existing camera worker. Existing debug feature flag still gates integration; release/default flags remain unchanged and disabled. No user-facing model selector.

### Exact application files changed

All paths below are relative to the **C: application worktree**, not the F: Android tree:

1. `android/app/src/main/java/com/example/apphear/fingerspelling/FingerspellModels.kt` — dual pinned package loader; optional appearance; package width and explicit mask support for parity.
2. `android/app/src/main/java/com/example/apphear/fingerspelling/FingerspellRuntime.kt` — geometry-only capture branch and package-kind diagnostics.
3. `android/app/src/main/java/com/example/apphear/fingerspelling/FingerspellCore.kt` — validated package-specific buffer width with old default preserved.
4. `android/app/src/androidTest/java/com/example/apphear/fingerspelling/Train4096ParityInstrumentedTest.kt` — added numerical/mask/causal/text transfer and CPU timing test.
5. `android/app/src/androidTest/java/com/example/apphear/fingerspelling/FingerspellParityInstrumentedTest.kt` — old visual fixtures apply only to rollback package; existing observation parser reusable by geometry test.
6. `android/app/src/androidTest/java/com/example/apphear/fingerspelling/FingerspellOwnershipInstrumentedTest.kt` — synthetic observation uses actual session width.
7. `android/app/src/androidTest/java/com/example/apphear/fingerspelling/FingerspellBeamInstrumentedTest.kt` — WORD guard injection uses actual session width; decoder fixture test unchanged.
8. `android/app/src/test/java/com/example/apphear/fingerspelling/FingerspellSessionTest.kt` — added405-width/repeated-letter/wrong-width regression.

F: additions/changes: `tools/fingerspelling/android_train4096_export.py`; optional `ArtifactDirectory` argument in existing `android_oct04_build.ps1` (old default preserved); transfer plan/report/evidence; appended component/status entries in `context/feature-schema.md`, `context/fingerspelling-android-v1.md`, `context/progress-tracker.md`, `memory.md`. Corresponding application-worktree context/status/memory entries are appended for continuity. Original exporter/package/checkpoints/reports are preserved.

## Numerical and decoded parity

Six metadata-selected governed sequences × native/phone views plus two synthetic contract cases = **14 model cases**. Includes TRAIN DAUN/MacKenzie, DEV-A, short/long inputs, SPACE, J/Z and repeats. Synthetic raw cases cover one/both missing slots, duplicate slots, partial validity, absent full body, motion/gap/resolution changes. Padding is a masked, test-only contract fixture; never training or fabricated phone observations. No DEV-B selection/inference or TEST payload access in this phase.

| Comparison | Result |
|---|---|
| Keras→host TFLite max absolute logit error | 0.0000154972 |
| Host TFLite→Xiaomi max absolute logit error | 0.0000119209 |
| Keras→Xiaomi max absolute logit error | 0.0000145733 |
| Python→Android Adapter v1 | 1,246 observations; max error0 |
| New-model greedy strings | 14/14 exact; zero mismatches |
| New-model beam Top-1 strings | 14/14 exact; zero mismatches |
| Causal-prefix comparisons | 14/14 pass |
| Existing beam fixtures on Xiaomi | 523/523 exact; 416 differ from greedy as expected |
| Beam prefix-mass max score difference | 8.88×10⁻¹⁵ |

Host logits use atol/rtol2e-4; Android checks absolute2e-4. Adapter tolerance1e-6. Observed errors are far below tolerance. These checks compare the same inputs and strings, not correctness against transcripts. Existing repeated-character/blank/SPACE decoder tests pass unchanged.

## Xiaomi runtime and functional evidence

Xiaomi M2101K7AG, Android12, USB serial3ab64582. CPU2 threads, no GPU/NNAPI configuration changes. Six real transfer cases per view; table uses the stored lower empirical percentile convention, not a population latency estimate. Mask/synthetic cases excluded from this timing table.

| Fixed fixture view | T range | warm model p50/p95/max ms | beam p50/p95/max ms | warm model + both decoders p50/p95/max ms |
|---|---|---|---|---|
| Native | 91–331 | 15.73 /19.46 /41.04 | 112.34 /193.19 /268.43 | 135.18 /240.40 /284.32 |
| Phone-like | 19–67 | 5.57 /6.37 /8.29 | 22.35 /28.04 /49.49 | 29.46 /34.58 /57.91 |

Separate existing523-fixture decoder run: native p50/p95 92.04/156.84ms; phone-like17.46/30.67ms. These fixed-logit timings are distinct from live capture.

One supervisor/nonexpert **engineering-only** AMY attempt:

- 51 real Candidate01 observations, 8.073s capture wall time, 7.936s timestamp span.
- Delivered cadence **6.3007 observations/s** =50 gaps /span; gaps p50/p95/max133.52/200.28/200.28ms.
- Candidate01 processing p50/p95/max143.20/195.73/211.44ms. Per-observation geometry preparation p50/p95/max0.897/1.065/1.214ms (legacy JSON key `added_visual_ms`; visual branch explicitlyfalse).
- Model85.97ms; greedy1.88ms; beam314.88ms; model+both decoders **402.75ms**; worker-to-report403.23ms.
- Greedy `AESEYI`; beam and visible preview **`AAESEYI`**. Actual session manifest pins epoch038/hash above and model input405, visualfalse.
- Supervisor confirmed preview, Retry, Clear, return to WORD and camera operation: “yes, all work.” No incorrect spelling was confirmed into conversation text.
- 21/51 observations had at least one observed hand. This is capture evidence only; handshape correctness/boundaries were not evaluated. Do not infer a recognition cause from this count.

The live finish measurement is slower than warm fixture timings. Its cause was not isolated; neither timing is hidden. Approximately0.40s bounded Done processing is practical here. Finish scope excludes button queue and visible rendering; no true button-to-preview latency claim. No observation-drop counter was added; existing KEEP_ONLY_LATEST behavior remains, losses are not quantified.

Memory: parity Java heap snapshots3,399,344→9,968,184 bytes and native10,859,984→19,992,024 bytes. Active-session snapshots Java20,191,136/native179,284,560 bytes include the application/camera/perception. Neither is peak memory or an isolated model allocation measure. No memory-induced failure observed.

**No live accuracy claim.** AMY was an explicit prompt, not a verified linguistic performance. No proficient signer was required, no attempt became training data, and no video/logits/raw landmark recording was added. Phone-domain model improvement remains unmeasured.

## Tests, preservation and rollback

- Python focused adapter/temporal/schema/beam tests: **41 passed**.
- Android debug host suite: **157 passed**, zero failures/errors/skips. Includes Phone causal/raw/S2 recorder/finalizer, RecognitionV2 JVM parity, SentenceBuilder, recognition UI and18 Context Assist tests.
- New-package Xiaomi numerical/beam/ownership/WORD guard: **4 passed**.
- Preserved old-package Xiaomi visual parity, ownership, WORD guard and3 deterministic Context Assist/Hear tests: **6 passed**, zero assumption skips. Old visual parity: feature/crop0; quality5.96e-8; embedding1.60e-5; logits8.11e-6;6 causal prefixes and6 zero-visual B2 checks pass.
- WORD sentence storage survives independent spelling preview/confirmation/retry/clear; stale WORD UI output cannot overwrite spelling preview; neither spelling model nor decoder executes when owner is WORD.
- Raw Hear output, advisory visibility and leaving-recognition lifecycle regressions pass with the existing fake provider. The authorized private Gemini build is restored afterward; provider code/prompts/schema were not edited.
- 1,199 protected files and235 packaged non-fingerspelling assets unchanged; no unexpected fingerspelling file change. Candidate01, Adapter, WORD/Context Assist, old checkpoints/package and sealed TEST preserved.

Rollback remains usable: the old manifest `09680096117f4d34eb86e0b71fc8681bfe3d4101082c4e0db2c8f7e9b1a1e57b` loads the original residual/appearance models in the updated loader. Numerical rollback was measured, not assumed. Rebuild using the helper's original default:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\tools\fingerspelling\android_oct04_build.ps1 -Configuration private
```

New experimental geometry build:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\tools\fingerspelling\android_oct04_build.ps1 -Configuration private -ArtifactDirectory 'F:\ASL DATASET\5. Apphear3\artifacts\fingerspelling_train4096_android_01'
```

The installed new private APK and companion are retained under the new evidence root's `private_apks/`. They contain the previously authorized local service configuration and must remain private/phone-only. Original old private APK remains preserved under `artifacts/fingerspelling_android_beam_01/private_apks/`. Fake rollback build is test evidence, not the final phone configuration.

## Review and limitations

Plan alignment PASS; architecture boundaries PASS; offline/device experimental gate PASS. No critical/important review findings. No new accuracy experiment authorized by this result.

A legacy beam-fixture packaging path was corrected before the completed host gate. Transient ADB daemon loss during private restore was resolved by reconnecting and successful `install -r`; final session proves the intended package. Xiaomi denies direct shell permission grants and launching the non-exported recognition activity; existing camera permission and normal user navigation worked, so no permission/export/manifest changes were made.

Do not interpret geometry-only transfer as validation of old residual weights on the new B2 state. The residual is intentionally absent. Do not equate numerical transfer with signer-generalizable phone accuracy. Known weak complete-string recognition and research reflection limitation remain; no training, data expansion, decoder tuning, segmentation, quantization or production promotion occurred.

## Evidence

Root: `F:\ASL DATASET\5. Apphear3\artifacts\fingerspelling_train4096_android_01\`.

Key artifacts: `export_parity.json`, `model_manifest.json`, `android_assets/`, `parity_assets/`, `xiaomi_fingerspell_train4096_parity.json`, `xiaomi_fingerspell_beam_parity.json`, `xiaomi_rollback_visual_parity.json`, `runtime_summary.json`, `session_1791372125109.json`, `physical_smoke_records.json`, `unit_validation.json`, `python_tests.xml`, build/instrumentation logs, `preservation_before.json`, `preservation.json`, `android_changed_files.json`, `android_source_identity.json`, `apk_identities.json`, `installed_apk_integrity.json`, `android_source_before/`, `android_source_staged/`, `decision.json`.

TRAIN4096_EPOCH038_ANDROID_PASS
