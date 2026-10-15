> **Connected-phone follow-up (October16):** Eleven Android gates and a finalized757-observation engineering capture now pass. Physical review is pending; see [device validation](recognition-v3-stage2-device-validation-2026-10-16.md). Earlier phone-absent/pending-device statements below are historical.

# Recognition V3 Stage2 — compact capture path

2026-10-15, Asia/Manila. **COMPACT_CAPTURE_BUILT_DEVICE_VALIDATION_PENDING**.

Continues commit1422cad on codex/recognition-v3-stage2, after completed Stage1 validation e196a8d.
The canonical integrated checkout4c99ac24, protected76d93cec, Stage1 candidate/evidence and the
rejected S2 history-reset experiment remain preserved. This implements the missing diagnostic
capture/review profile; it is **not a continuous WORD recognition fix**.

## Why this is the next step

The prior investigation reproduced the real1,364-observation A/B recording: six/seven confident
signs had no S2 ACTIVE, both TABLE spans lacked accepted hands, and some subsequent signs were
already READY. Unconditional S2-prefix reset after re-arm increased events10→20 and fully
contained reviewed non-sign events4→9. Shortening recovery or deploying that reset is unsupported.

That investigation explicitly identified missing adjacent-repeat and sign-then-hold evidence.
The existing seven-block recorder could not represent this smaller cohort without relabeling
the experiment. It now supports an explicitly selected, versioned compact profile.

## Implemented behavior

One canonical JSON asset, apphear.word_transition_protocol.v1 / V3_STAGE2_COMPACT_01,
defines five blocks and seven intended signs:

| Block | Physical task | Human review |
|---|---|---|
| A_HANDS_DOWN | HELLO → naturally lower hands → HOME | Two lexical intervals |
| B_HANDS_UP | HELLO → HOME, hands remain in signing space | Two lexical intervals |
| C_REPEAT_HANDS_UP | HELLO → HELLO, two distinct executions | Two separate lexical intervals |
| D_SIGN_THEN_HOLD | HELLO once, then hold final position about5s | One lexical interval plus a separate hold-negative interval |
| E_ORDINARY_MOVEMENT | Ordinary hand/body movement without signing | A bounded non-sign interval |

Use the same signer, framing, lighting and distance for A/B. Allow initialization and initial
IDLE before each whole positive block; do not wait for READY or tap between words. Return to
neutral only after the sequence, allow roughly3s of tail, then STOP. Do not adapt movements to
the displayed predictions. This is one bounded design capture, not repeated tuning.

- Explicit debug intent selects the compact profile; legacy seven-block defaults remain intact.
- The same CameraX/native/DWPose/refiner, exact recorder, S2-R2, decoder, Admission, materializer,
  frozen classifier and diagnostic UI delivery are reused. Markers do not reset inference.
- Compact opt-in refuses concurrent-hand builds and invalid scope/proficiency metadata.
  Frozen model/recovery guards already present remain enforced.
- Capture identity records protocol SHA, comparison baseline e196a8d, label schema and declared
  signer proficiency. UNKNOWN is allowed and does not imply ASL competence or accuracy validity.
- Blinded reviewer and evaluator now understand human_boundaries.v2 with profile/evidence hashes.
  The reviewer still displays only genuine source images/timestamps, without predictions.
- Review refuses changed sign order, protocol/schema mismatch, incomplete block review,
  overlapping lexical/non-sign labels, and a hold-negative interval before the physical sign ends.
- Results distinguish missing events, merged events, multiple-event overlaps, early/wrong episodes
  and lexical mismatches. Two separate repeated-sign events remain two evaluation results.
  Diagnostic delivery is **not** normal-app sentence delivery; that limitation stays explicit.

Raw-v1, 378 features/normalization, V2[96,350]+mask and all weights remain unchanged.
No recovery/admission timer, history-reset policy, sentence dedup, FINGERSPELL, coordination,
Context Assist, Hear, Text-to-ASL, normal UI or release-source behavior was changed.
The new debug flags enabling the preexisting diagnostic Activity have no consumers in main sources.
Stage1 concurrency and profiling are both false.

## Verification actually completed

- **141 host tests pass**, including compact/legacy source-linkage roundtrips, repeat/merge/
  classifier attribution, human-label integrity, earlier Stage2, lifecycle, materializer,
  trace and existing FINGERSPELL regressions. Synthetic cases test the tools, not signing accuracy.
- **200 Android JVM tests pass**, including six new protocol/scope checks and the existing
  actual Kotlin replay of all1,364 historical decoder observations.
- The real historical capture's integrity payload and human-boundary analysis reproduce exactly:
 1,364 observations, ten events, unchanged source and label hashes.
- **581 protected shared-state hashes pass**.
- Integrated debug APK and Android-test APK build successfully. Packaged-parser instrumentation
  test is compiled but **NOT RUN**. No phone was connected.
- Both APK ZIP integrity checks pass. All **465 original asset/native entries** match the saved
  serial baseline byte-for-byte; the only extra payload is the compact protocol JSON.
- Ruff/mypy and reviewer JavaScript / PowerShell syntax checks pass.
- The read-only device preflight utility's CheckOnly path passed; physical boot/exit/thermal
  inspection remains pending until the phone is connected.

The first APK build filled C: and produced an incomplete package; this is a host storage failure,
not a phone/runtime crash. Its log and completed200-test JVM receipts are retained. One bounded
recovery removed only this worktree's verified generated intermediates after archiving receipts,
then redirected generated build outputs to F: with a local init script. The full build succeeded.
No baseline APK, source model, dataset, recording or research result was removed. Build metadata
and the recovered-artifact location are in the delivery manifest.

## APK delivery

The valid, snapshotted APKs are on F: (do not use the failed C: build's partial output):

- App: F:/ASL DATASET/5. Apphear3/artifacts/recognition_v3_stage2_compact_build_20261015/delivery/app-debug-stage2-compact.apk
- Test: F:/ASL DATASET/5. Apphear3/artifacts/recognition_v3_stage2_compact_build_20261015/delivery/app-debug-stage2-compact-androidTest.apk

The build uses the repository's integrated fake-service preset with OriginalWords, automatic
FINGERSPELL, coordination, rear-camera support and Context Assist flags. It does not provision
live external service credentials. The diagnostic capture itself uses the existing front camera.

App SHA-256: 846ad345cdb061bef11858ef95151c0d35abdadbd67a5dbb1f9401abf7f6f6fc
Test SHA-256: 45d5faaad3ae5e87308d1d25e4ad0ba029bc9f4d19691deb5350eb5a0689fd15

## Stable-phone procedure

First run the **read-only** collector from this worktree:

```powershell
& tools/recognition_v3/inspect_stage2_phone.ps1 -Serial SERIAL
```

It saves uptime, boot reasons, AppHear exit-info, thermal/battery/memory and recent crash-buffer
records locally. It never installs/launches, clears logs/data or changes settings. Review the
evidence and the actual phone's stability before proceeding. The previous phone closure remains
unresolved; no preflight output is automatically a stability certification.

Then, on one stable authorized phone, update without uninstalling/clearing storage:

```powershell
$stage2Adb = 'D:/AndroidStudio/Android/Sdk/platform-tools/adb.exe'
$stage2Serial = 'SERIAL'
$stage2Apks = 'F:/ASL DATASET/5. Apphear3/artifacts/recognition_v3_stage2_compact_build_20261015/delivery'
& $stage2Adb -s $stage2Serial install -r "$stage2Apks/app-debug-stage2-compact.apk"
& $stage2Adb -s $stage2Serial install -r "$stage2Apks/app-debug-stage2-compact-androidTest.apk"
& $stage2Adb -s $stage2Serial shell am instrument -w -r -e class com.example.apphear.perceptionvnext.Stage2TransitionProtocolInstrumentedTest com.example.apphear.test/androidx.test.runner.AndroidJUnitRunner
```

Stop if install or instrumentation fails. The packaged parser test finishes its instrumentation
normally; a test Activity/process closing is not by itself an app crash. The older Stage1
run_device_gate.ps1 reinstalls the old paired APKs: do not use it to validate this new capture APK.
The test APK does not bundle the separate51-frame Stage1 pixel fixtures; that old pixel test is
not a fresh device result for this build.

Use a stable non-secret signer ID; set proficiency accurately. Prefer an ASL-proficient design
signer, but no held-out/generalization claim follows merely from this declaration:

```powershell
$stage2Signer = 'stage2_design_signer_01'
$stage2Proficiency = 'UNKNOWN' # ASL_PROFICIENT only with actual human attestation
& $stage2Adb -s $stage2Serial shell am start -n com.example.apphear/.perceptionvnext.PerceptionVNextLiveRecognitionActivity --ez perception_vnext_enabled true --ez phone_causal_enabled true --ez continuous_transition_diagnostics true --ez recognition_v3_stage2_diagnostics true --ez s2_exact_parity_capture true --es phone_s2_package S2_R2_CANDIDATE --es phone_rearm_policy PRE_OR_POST_EXPERIMENTAL --es validation_signer_id $stage2Signer --es validation_signer_proficiency $stage2Proficiency
```

Confirm Block1/5. Use START/STOP once per whole block. After block5, FINALIZE & SAVE EVIDENCE;
keep the app open until final visual-drain verification completes. Preserve any incomplete/failed
session instead of retrying silently. All capture and parser instructions above remain **NOT
DEVICE TESTED** in this continuation.

Pull into a new local directory, preserving prior sessions:

```powershell
$stage2PhoneRoot = '/sdcard/Android/data/com.example.apphear/files/phone_repeated_recognition_integration_01'
$stage2Session = (& $stage2Adb -s $stage2Serial shell cat "$stage2PhoneRoot/latest_session.txt").Trim()
if ($stage2Session -notmatch '^session_\d{8}T\d{6}Z$') { throw 'Invalid session pointer' }
$stage2PullRoot = 'F:/ASL DATASET/5. Apphear3/artifacts/recognition_v3_stage2_compact_device'
$stage2SessionRoot = Join-Path $stage2PullRoot $stage2Session
if (Test-Path -LiteralPath $stage2SessionRoot) { throw 'Preserve the existing session; do not overwrite' }
New-Item -ItemType Directory -Force -Path $stage2PullRoot | Out-Null
& $stage2Adb -s $stage2Serial pull "$stage2PhoneRoot/$stage2Session" $stage2SessionRoot
python -m eval.runtime_diagnostics.continuous_transition_diagnostics prepare --session "$stage2SessionRoot"
```

Stop on a failed/incomplete pull or audit. Serve only on localhost to review the source frames:

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory "$stage2SessionRoot"
```

Open localhost:8765/transition_review/index.html, review every whole block, retain uncertainty
where boundaries or sign execution are unclear, and save human_boundaries.json beside the
template. Then:

```powershell
python -m eval.runtime_diagnostics.continuous_transition_diagnostics analyze --session "$stage2SessionRoot"
```

Only after source integrity and human review should the event/state/window/lexical results guide
a new readiness or segmentation candidate. Do not treat counts, synthetic passes or this new APK
as an accuracy improvement. Normal-app consecutive-repeat sentence behavior still requires a
separate production-session check; the prior dedup limitation has not been changed.

## Review and rollback

Scope/plan alignment PASS; source/model-contract preservation PASS; offline diagnostic gates PASS.
Deployment/actual capture validity remains PENDING, not passed. No critical implementation finding;
two important open gates: stable-phone execution and qualified human-reviewed real signing evidence.
Retain the earlier rejected-context-reset result and keep Stage1 disabled.

Omitting recognition_v3_stage2_diagnostics uses the original seven-block diagnostic profile.
Normal app and release behavior remain unchanged. The canonical integrated checkout and original
serial APK remain the rollback reference; no data migration or app uninstall is required.
