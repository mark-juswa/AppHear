# Recognition V3 Stage 1 — partial Android validation

Date: 2026-10-15 (Asia/Manila). **PARTIAL_ANDROID_EVIDENCE_MIXED_DO_NOT_PROMOTE**.
Branch: `codex/recognition-v3-stage1`. Runtime implementation: `5d73b412`.
No further phone operations after the user chose to finish with collected evidence.

## Decision

Retain concurrent hand refinement as a default-off experimental candidate. Identical-pixel
Android replay confirms lower two-hand wall time with unchanged hand outputs. Live front-camera
FINGERSPELL delivery improved in this small engineering sample; WORD delivery did not. Neither
ASL accuracy improvement nor sustained runtime stability is established. V3 rear-camera runs
are missing. Do not enable globally or describe Stage 1 as promotion-ready.

## Integrated baseline and preservation

`5d73b412c3f310d56346f1c4cc960f69246afc27` is a direct child of canonical integrated
`4c99ac24ebe7d1d1371a7268288df43df08f8d6b`. The canonical checkout remains clean at
that commit; protected `76d93cecd85bf9f76064d320aa4a5791b5f0704a` remains intact.
The other dirty research checkout was not used as the application baseline or modified.

The integrated app includes S2-R2, Recognition V2/frozen WORD classifier, automatic held-letter
FINGERSPELL with epoch034/Adapter405, exclusive output coordination, Hear, Context Assist,
Text-to-ASL, front/rear camera support, and Original273/New122 catalogs. The September28
continuous-transition diagnostics commit `befa94a5` is also an ancestor of the canonical app.
Its presence does not imply a continuous WORD transition fix was implemented.

This evaluation changes only androidTest sources, evaluation tooling/tests, and evidence/context.
No additional main/debug/release runtime, model, feature math, UI, resource, ownership policy,
S2-R2, Admission, materializer, Recognition V2 or SentenceBuilder change. The shared-state
checker passed all **581 hashes**. Saved app APK hashes match the original Stage1 manifest;
the original paired build comparison found all **465 assets/native libraries** identical.

## Actual phone tests

Device: Xiaomi M2101K7AG, Android12/SDK31, SM6150 CPU. Signer status explicitly
**NONEXPERT_ENGINEERING_SMOKE**. The live gestures have no qualified signer/lexical truth.

- Applicable Android software gate: **11 tests per arm passed**, including actual native
  rotation/stride and serial/concurrent model parity, S2 parity, Recognition V2 replay,
  sequence/single-letter parity, automatic FINGERSPELL UI and owner/WORD coordination.
- The first baseline gate also ran the obsolete manual Start/Done method
  `FingerspellSingleLetterInstrumentedTest#confirmationRefusalAndWordIsolation`, which
  **failed**: continuous mode deliberately makes manual `start()` a no-op, so the test's
  manual-session phase precondition is invalid. Its failure output is preserved.
  The driver now selects that class's exact parity method and runs the applicable automatic
  UI/coordination tests separately. This is an explicit test applicability correction,
  not a hidden passing rerun or a production bug fix.
- New on-device paired recorded compute benchmark passed: **51 real recorded RGBA frames**,
  fresh DWPose inference once per frame, current ROIs, alternating serial/concurrent arm order,
  one warmup plus three measured passes; **204 hand-output comparisons**, including warmup,
  matched coordinates, validity, presence and handedness exactly.
- **Six 20-second live captures passed**: both front-camera arms/owners, then serial rear WORD
  and FINGERSPELL. V3 rear WORD/FINGERSPELL: **NOT TESTED**.
- **71 host tests passed** (18 trace-integrity plus 53 existing fingerspelling regressions).
  These tests establish engineering integrity, not ASL accuracy.
- Both new instrumentation APK builds succeeded. The original app APKs were reused unchanged;
  the initial Stage1 191-JVM-test-per-arm results remain historical, not a fresh rerun.

Original gate receipts, test XML, bounded logcat traces, UI/PSS snapshots, thermal snapshots and
recorded benchmark rows are retained under `artifacts/recognition_v3_validation/`.
Compact committed results and SHA-256 provenance are under
`evidence/recognition_v3_validation_20261015/`.

## Identical-input compute result

Times in ms, p50 / p95; three measured passes after one full warmup.

| Current inferred hand proposals | Serial hand wall | V3 hand wall | Evidence |
|---|---:|---:|---|
| 0 | 0.003 / 0.011 | 0.008 / 0.011 | No useful inference saving expected |
| 1 | 30.728 / 31.279 | 30.705 / 31.226 | Same serial path |
| 2 | 61.782 / 64.147 | 38.901 / 43.168 | 37.0% p50, 32.7% p95 reduction |

For two proposals, shared fresh DWPose was 34.818 / 35.367 ms; preprocessing 1.058 / 1.168 ms,
decode 0.366 / 0.462 ms. Summed hand-inference durations increased from 58.000 / 60.728 to
63.151 / 67.073 ms even as wall time fell. That is consistent with contention; it is not a
CPU-utilization measurement. Benchmark process PSS before/after spans test initialization and
teardown, so it is explicitly **not** the incremental production memory cost.

Replay establishes a real phone compute benefit without changing these perception outputs.
It does not measure live camera FPS, new signs, lexical correctness, or end-to-end phrase accuracy.

## Live observation delivery

Primary exploratory comparison uses completion clock **[BEGIN+5s, BEGIN+19s)** for every
completed run: fixed five-second warmup and **14-second denominator**, counting genuine completed
observations. This avoids a variable-duration 20-observation warmup. Source IDs and capture/
completion clocks are validated before trimming; no reused observations are counted.
One run per condition, different live gestures; no significance or generalization claim.

| Camera / owner / arm | Observations / 14s | Delivered FPS | Analyzer p50 / p95 ms | Pose p50 / p95 ms | Hands wall p50 / p95 ms |
|---|---:|---:|---:|---:|---:|
| Front WORD serial | 65 | 4.64 | 214.7 / 248.1 | 86.8 / 115.0 | 109.8 / 112.8 |
| Front WORD V3 | 61 | 4.36 | 225.4 / 328.9 | 107.0 / 140.0 | 100.0 / 172.9 |
| Front FINGERSPELL serial | 69 | 4.93 | 195.9 / 217.5 | 82.6 / 102.3 | 109.6 / 113.3 |
| Front FINGERSPELL V3 | 85 | 6.07 | 160.4 / 185.2 | 80.9 / 96.5 | 73.8 / 94.0 |
| Rear WORD serial | 104 | 7.43 | 135.5 / 157.0 | 59.7 / 68.0 | 66.3 / 68.9 |
| Rear FINGERSPELL serial | 108 | 7.71 | 129.0 / 143.8 | 61.3 / 72.2 | 66.7 / 69.7 |
| Rear both owners V3 | — | NOT TESTED | — | — | — |

Observed front FINGERSPELL FPS: **+23.2%**; front WORD: **−6.2%**, with worse analyzer p95.
All used 480×640 source geometry; front rotation270/rear90; existing front15/rear30 AE retained.
The earlier `baseline_word_front_01` pilot preceded clarified automated/live instructions and
is preserved but excluded from this preannounced six-run batch.

Instrumented median PSS: WORD serial279412KB vs V3 301402KB (**+21.5MiB**);
FINGERSPELL serial274878KB vs V3 300521KB (**+25.0MiB**). Scene allocations and test overhead
are included; do not attribute the full delta precisely to an interpreter arena.
All 12 before/after live thermal snapshots report status0. CPU snapshots use stale sampling
intervals across runs; quantitative app CPU percentages are **excluded**. No long thermal,
leak or sustained contention/stability test was completed. Sensor timestamp join was unavailable:
camera frame drops are **NOT MEASURED**, and timing gaps are not drop counts.

## Output validity and recognition behavior

No synthetic/missing frames, forward-filled landmarks, or changed V2 representation were added.
Identical-input Android perception parity passed. Live validity was not identical between scenes:
front WORD accepted hands/frame 0.354 serial vs0.492 V3; front FINGERSPELL0.797 vs1.741.
Mean valid body fraction was approximately0.535 vs0.539 (WORD),0.431 vs0.462 (FINGERSPELL),
and only0.212/0.235 in the two serial rear runs. These are internal validity diagnostics,
not landmark truth. Sparse/weak body evidence and different hand visibility confound live
recognition comparisons.

Both front WORD runs displayed **HELLO** only during the requested HELLO→HOME→TABLE scene.
Serial rear showed HOME then HOME HELLO. Front FINGERSPELL drafts were **S→SA→SAE**
(serial) and **S→SM→SMY** (V3); rear serial **A→AE→AES**, for requested A–M–Y holds.
These are observed UI outputs, not scored sign labels. Correctness remains **UNVERIFIED**;
the different incorrect/different drafts cannot establish an improvement or a causal regression.

Exclusive WORD/FINGERSPELL ownership and existing coordination passed applicable gates; the
runtime and unrelated app functionality were preserved. This does not certify reliable fluent
fingerspelling, all-letter accuracy, or continuous WORD recognition.

## Phone closure and stability limitation

Early screen closures occurred at instrumentation completion. Available AppHear exit records
reported user-requested `finished inst` termination and the collected crash buffer had no
AppHear Java/native crash. Those closures alone did not establish an application crash.

A **separate later incident remains unresolved**: after the six live runs, both USB and wireless
ADB vanished before V3 rear installation; the user reported that the phone suddenly closed.
The last confirmed installed app was **serial baseline**. No postincident crash/reboot evidence
was available, so do not infer a V3 crash, a device reboot, or a clean stability pass.
The user requested completion using saved evidence; all further device operations stopped.

## Project Lead handoff — hands-down wait remains unresolved

User report during this evaluation: **“I have to wait and hold my hands down to sign again.”**
This recalls the earlier `APPHEAR_CONTINUOUS_TRANSITION_AND_READINESS_01` work,
whose report states **DIAGNOSTIC_TOOLING_READY_WAIT_FOR_AB_CAPTURE**. That work instrumented
the symptom; it did not implement a continuous WORD transition policy fix. It is integrated,
not accidentally omitted from the V3 branch.

Current `PhoneProductionSession` uses PRE_OR_POST recovery. After one event,
`PhoneCausalEventProducer` enters EVENT_EMITTED_WAIT_REARM, requires approximately399.924ms
stable PRE/POST, resets recovery on ACTIVE, and resets on gaps greater than533.232ms.
ACTIVE may also cancel pending POST completion. This supports possible mechanisms for the
symptom, **not an attribution from these captures**. The current FPS logs/UI snapshots lack
the complete human lexical boundaries and decoder lifecycle needed to distinguish:
(1) waiting/re-arm blocks the next sign; (2) consecutive signs merge without an S2 boundary;
(3) S2 fails to reacquire ACTIVE; (4) distinct events exist but recognition/window output fails.

When Stage2 is authorized, reuse the existing A/B hands-down versus natural hands-up cohort,
source observations, human boundaries and per-event lifecycle/window/UI linkage from
`APPHEAR_CONTINUOUS_TRANSITION_AND_READINESS_01_REPORT.md`. Evaluate transition success,
missed/merged/duplicate events and false activations before changing timers or retraining.
FINGERSPELL has a separate held-letter policy: same-letter repeats rearm through tracking loss;
this must not be conflated with WORD re-arm or removed to mask the WORD issue.
No policy fix or message to another task is implied by saving this handoff.

## Next priority and rollback

Shared neural inference remains the measured cost: live front pose roughly81–107ms p50 plus
hand wall74–110ms. Current delivery is still well below the historical15-FPS target.
Concurrency reduces paired hand wall time but does not remove the shared CPU/inference budget.
If further Stage1 performance work is authorized after the device incident is understood,
one bounded **thread-budget comparison** is justified (for example, one thread per concurrent
hand interpreter instead of two), with same-pixel parity and all owner/lens gates. Do not start
an open-ended tuning cycle, another architectural rewrite, Stage2 or Stage3 automatically.

Current evidence collection is closed as partial. Retain V3 off; prioritize diagnosing the
device incident and completing the missing matched rear/repeated conditions before promotion.
The project lead should consider the reported transition failure as the explicit Stage2
product issue; faster perception alone is insufficient to resolve it.

Rollback requires no merge/revert in the canonical checkout: it remains4c99ac24. Keep
`recognitionV3ParallelHands=false` (also the default/release setting) or update with the saved
serial APK using `adb -s SERIAL install -r artifacts/recognition_v3_stage1/app-debug-baseline.apk`
when a stable device is available. Preserve data; do not uninstall or clear storage.
The V3 source commit and all evidence remain available independently.

## Reproduction without a phone

From this worktree with the existing Python environment:

```powershell
python tools/recognition_v3/evaluate_collected_runs.py --data artifacts/recognition_v3_validation --out evidence/recognition_v3_validation_20261015/phone_results.json
python -m pytest tests/test_recognition_v3_trace.py tests/test_fingerspelling_prefix_beam.py tests/test_fingerspelling_single_letter.py
```

The saved paired APK identities and new instrumentation APK hashes are in
`evidence/recognition_v3_validation_20261015/validation_manifest.json`.
Device drivers are `tools/recognition_v3/run_device_gate.ps1` and
`tools/recognition_v3/run_live_capture.ps1`; the gate's `-CheckOnly` performs hash preflight
without accessing a phone. Private raw artifacts/APKs must be retained or provisioned separately
when cloning the compact Git evidence.

## Review disposition

Plan/scope alignment: PASS (evaluation only; no Stage2/3). System integrity: PASS for tested
same-input perception parity and ownership; no feature schema change. Promotion readiness:
**FAIL / incomplete evidence**. Important open findings: mixed live delivery/PSS cost; missing
V3 rear/repeated conditions and qualified recognition evidence; unresolved phone closure and
hands-down transition symptom. No claim of improved ASL accuracy.
