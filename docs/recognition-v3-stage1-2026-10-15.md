> **Later phone evaluation:** See [partial Android validation](recognition-v3-stage1-validation-2026-10-15.md). The implementation report below preserves its original pre-device state; measured live results are mixed and promotion remains blocked.

# Recognition V3 Stage 1 — concurrent current-frame hand refinement

Status: **IMPLEMENTED_HOST_PARITY_PASS_DEVICE_GATE_PENDING**, 2026-10-15 Asia/Manila.
Branch `codex/recognition-v3-stage1` starts from canonical integrated
`4c99ac24ebe7d1d1371a7268288df43df08f8d6b`. Managed worktree:
`C:/Users/Gigabyte/.codex/worktrees/recognition-v3-stage1/5. Apphear3`.
Protected baseline `76d93cecd85bf9f76064d320aa4a5791b5f0704a` is unchanged. Neither the
canonical integrated checkout nor the original dirty research checkout was edited.
No Stage 2/3, training, model replacement, cloud SONAR/Uni-Sign, Kaggle or UI work occurred.

## Bottleneck and selected change

Inspected `RecognitionActivity`, `Candidate01FrameAnalyzer`, `PerceptionVNextNativePreprocessor`,
`perception_vnext_preprocess.cpp`, `DWPoseTRunner` and `HandRefinerRunner`.
CameraX uses RGBA8888 and KEEP_ONLY_LATEST on a dedicated analysis executor. Each accepted
frame runs native preprocessing, full DWPose-t, then anatomical-left and anatomical-right
refinement serially, before producing one genuine raw observation and running its exclusive owner.

The strongest existing stage-separated phone evidence is
`artifacts/recognition_upgrade/perception_vnext/phone_01/NATIVE_RUNTIME_RESULT.md` in the research
checkout. Its native snapshot measured preprocessing 2.693 ms p50, DWPose 80.006 ms, crop
resampling 3.324 ms and each hand refiner 50.946 ms. Neural inference, particularly two serial
refinements, dominates that profile. These are historical measurements, not a fresh October15
matched profile. DWPose's reported 80 ms alone exceeds the 66.7 ms observation budget.

The separate historical October8 12-observation camera samples had front WORD 3.6674 delivered
observations/s and analyzer p50/p95 235.155625/456.061927 ms; rear WORD 8.7884 and
102.226302/163.083437 ms. They measure total cost, not stage attribution, and are startup samples
under different camera conditions. They cannot establish the V3 speedup or explain the front/rear
difference. Source: `artifacts/camera_input_01/summary.json` in the research checkout.

Implemented one optimization: overlap the two hand crop/refiner operations when both original
current-frame DWPose proposals exist. The existing interpreter handles anatomical left on one
bounded worker; a separately initialized interpreter handles anatomical right on the analyzer.
Both retain the existing CPU/XNNPACK two-thread options, identical weights and output restoration.
Zero/one-proposal frames retain serial execution. A briefly investigated output-marshalling route
was discarded; no such implementation remains in the final diff.

Expected benefit: less serial wall time for two-hand observations may allow CameraX to deliver
more genuine observations, preserving more short-sign evidence. This is a hypothesis about phone
behavior, not proof of greater ASL accuracy or the 15 FPS target.

## Correctness, ownership and resource boundaries

- `CurrentFrameHandPair` has one worker and a queue capacity of one, with serialized `run/close`.
  There is at most one submitted hand task. It drains that task even if the analyzer-side operation
  throws or the waiting thread is interrupted. Cancellation is not used as proof native work ended.
- Each operation owns its interpreter output arrays and input buffer. JNI cropping reads the
  immutable source-frame byte copy and writes distinct destinations; the native math is unchanged.
- No observation is emitted until both tasks finish. `ImageProxy` still closes in the analyzer's
  existing `finally`; no task retains it, and no frame or landmark is fabricated/carried forward.
- Capture timestamps and source indices, orientation/unmirrored coordinates, anatomical slots,
  joint validity, proposal support, presence and handedness semantics remain unchanged.
- The existing `ownsObservation` callback runs once after the join, before `session.consume`.
  WORD/FINGERSPELL remain mutually exclusive, with unchanged Context Assist, Hear and UI ownership.
- Raw-v1, S2 378, Recognition V2 350 and FS Adapter v1 405 schemas/models remain frozen. No new
  representation is passed to any recognizer. Existing version/hash checks remain in place.
- Incremental resources: one extra hand interpreter and its native tensor arena/thread pool,
  one 602,112-byte direct input buffer and one scheduling worker. The additional mapped model is
  the same 5,478,949-byte asset. Physical memory sharing/PSS, battery, thermal and CPU contention
  are **NOT TESTED** on a phone. This is a meaningful retention gate, especially on small heaps.

No S2-R2, Admission, materializer, Recognition V2, SentenceBuilder, fingerspelling decoder/policy,
model/config asset, native binary, app resource or unrelated feature changed.

## Actual comparison and validation

`tools/recognition_v3/compare_hand_scheduling.py` reads existing, hash-verified recorded phone
pixels and cached current-frame proposals. It selects up to two frames per condition/proposal
count, covering empty, hands-down, unilateral, separated, crossing, face, torso and articulation
conditions: **51 real frames**, five paired repetitions, **255 compared hand outputs**.
Protected test/train data was not opened or modified. Selection is an engineering condition
sample, not independent signer-held-out accuracy evidence.

Both arms consume identical precomputed crops/ROIs. Baseline uses one interpreter serially;
candidate uses separate interpreters concurrently for two-proposal frames. Host TensorFlow
2.21.0/NumPy2.4.6, Windows CPU/XNNPACK; Android stays on its original TFLite2.16.1. Thus this
validates the scheduling hypothesis and same-input host semantics, not the Android binary.

| Host refinement scope | Cases per arm | Serial p50/p95 ms | Concurrent p50/p95 ms |
|---|---:|---:|---:|
| Zero proposals | 85 | 0.0012 / 0.00298 | 0.0038 / 0.00658 |
| One proposal (same serial path) | 85 | 4.2079 / 5.08914 | 4.1682 / 5.10384 |
| Two proposals | 85 | 8.5389 / 9.6632 | 5.0619 / 6.47986 |

Two-hand host refinement p50 fell 40.7%, p95 32.9%. Single-hand p95 was slightly higher; its
code path is unchanged and the tiny difference is not evidence of a phone regression or gain.
All 255 comparisons were bitwise identical for image/crop XY, presence, handedness, validity,
diagnostic Z and world output. Therefore the same threshold decisions follow on those inputs.
This does not establish recognition-input parity on the Android binary or real-time classification.

Actually completed:

- Matched integrated baseline and V3 debug app/test APK builds, using the canonical frozen
  package/build preset with FINGERSPELL, continuous policy, coordination, front/rear camera,
  Context Assist fake provider, and full Original Text-to-ASL extension enabled.
- **191 JVM tests per arm**, zero failures/errors/skips, including five new concurrency/drain/
  interruption/order/close tests, Recognition V2 golden-feature parity, phone causal core,
  fingerspelling decoder/policy and coordination regressions.
- **53 existing host fingerspelling regression tests**, no failures.
- New Python Ruff, Black and mypy checks passed. `git diff --check` passed.
- **465 packaged assets/native libraries are SHA256-identical between the two app APKs**;
  protected source/assets have no diff from canonical. Frozen package inventory verified by builds.
- New Android recorded-pixel test compiled into both test APKs. It compares serial vs concurrent
  native crop bytes and real interpreter coordinates/confidence/validity on the same real frames.
  **NOT RUN**: no attached device was available (`adb devices -l` empty).

| Requested phone/product result | Baseline vs V3 result in this run |
|---|---|
| Genuine delivered observation FPS | NOT TESTED |
| Analyzer p50/p95 and perception stages | NOT TESTED; bounded tracing implemented |
| Camera drops | NOT MEASURED; never inferred from timestamp gaps |
| Android observation validity/parity | Compiled test; NOT RUN |
| Memory/PSS, thermal, battery, camera stability | NOT TESTED |
| Comparable WORD classification/events | UNVERIFIED; frozen downstream unit parity passes |
| Live FINGERSPELL regression/accuracy | NOT TESTED; host policy/decoder/ownership regressions pass |
| Held-out end-to-end signed-phrase accuracy | UNVERIFIED; no improvement claim |

The original sparse-vs-dense recognition evidence is motivation, not a new result. Do not label
synthetic scheduler tests, hash parity or this host speedup as ASL accuracy improvement.

## Deliverables and reproducible commands

Compact versioned evidence:
`evidence/recognition_v3_stage1_20261015/{host_comparison,delivery_manifest,source_sha256}.json`.
The source hash inventory itself has SHA256
`5448eb98e07f39742251bc1ab4345d2478e188313f0989f72ab9fbbebc38438a`.
Generated APKs, Android recorded-pixel fixtures, XML test results and logs stay separately under
`artifacts/recognition_v3_stage1/` in the isolated worktree.

| APK | SHA256 |
|---|---|
| `app-debug-baseline.apk` | `5aa262c6b21a1e0675b4f2fc69ad7b13102fb5011e12babcdc02d252e011990a` |
| `app-debug-v3.apk` | `24d403c2eca200338574d97e05bd398992fa410e51e4bdaea70996003d1be673` |
| `app-debug-baseline-androidTest.apk` | `e3d71b2a73f41cbb77d23e67db60b2a96d4cfbe0918d789c8075247e8c362a86` |
| `app-debug-v3-androidTest.apk` | `d979d665000881264c90c9d30a5431d9d02b65e1364336e1ae3ce5c62312b3c4` |

App sizes: baseline822,576,858 bytes, V3 822,576,866; identical model/assets, no duplicated model
file in the APK. Test APKs are about33.6MB and contain the generated recorded-pixel fixtures.
Fake services explicitly blank credentials; no private service keys were copied into either APK.

From the isolated worktree, with JDK17/installed Android SDK configured:

```powershell
& 'F:/ASL DATASET/5. Apphear3/.venv/Scripts/python.exe' tools/recognition_v3/compare_hand_scheduling.py --evidence-root 'F:/ASL DATASET/5. Apphear3' --out artifacts/recognition_v3_stage1
& ./tools/recognition_v3/build_stage1.ps1 -Arm baseline
& ./tools/recognition_v3/build_stage1.ps1 -Arm v3
```

## Bounded device gate and rollback

Before a performance capture, install the selected app and matching test APK on an authorized
test phone; run the recorded-input numerical gate first:

```powershell
adb shell am instrument -w -e class com.example.apphear.perceptionvnext.ParallelHandRefinerInstrumentedTest com.example.apphear.test/androidx.test.runner.AndroidJUnitRunner
```

Require exact crop/model output parity or investigate the specific Android discrepancy; do not
promote after a mismatch. Run existing CameraInput, camera-switch, S2/recognizer parity and
coordination/ContinuousFingerspell tests, then `context/device-smoke.md`. Preserve old app data;
the generic smoke checklist's destructive uninstall is unnecessary for this asset-identical pair.

Capture matched baseline/V3 scenes on each lens in both WORD and FINGERSPELL, equal lighting,
distance, signer, thermal state, exposure and camera settings. Use zero-, one-, two-hand and
crossing/contact cases. Restart RecognitionActivity per bounded capture. Save `AppHearV3` logcat
rows and existing camera sensor timing separately; profile records at most240 observations.
Both arms enable identical diagnostic overhead. The trace's analyzer measurement ends after
delivery to its owner/UI callback, before diagnostic logging and final ImageProxy close; CameraTimingProbe
measures the outer analyzer call including that overhead. Neither measures preview presentation.

```powershell
python tools/recognition_v3/summarize_trace.py matched-word-front-v3.log --skip-warmup 20
```

The summary separates real capture span from completion-clock delivered FPS, reports lower-empirical
p50/p95 stages, validity and heap snapshots, and rejects stale/nonchronological/mixed-owner traces.
Camera drops require a complete sensor-timestamp join over the same interval; the existing bounded
camera probe may saturate before240 observations. If coverage is incomplete, report drops unknown.
Measure PSS/thermal and sustained runs separately; the bounded trace is not a long-run leak test.
Human-reviewed sign/event outcomes and held-out phrase evidence are required for accuracy claims.

Rollback: install `app-debug-baseline.apk` (same package/signing key, retain app data), or rebuild
with `recognitionV3ParallelHands=false`. Omit both V3 properties to restore ordinary no-trace
defaults. Release hardcodes both false. Exact integrated rollback remains commit4c99ac24 and its
unchanged `tools/android/build_working_baseline.ps1`; protected76d93cec remains separately intact.
No model/data migration or git reset is needed.

Review (`/review`): plan alignment PASS; architecture/contract/ownership inspection PASS;
production readiness PENDING. Critical implementation findings0; important validation gaps2
(Android binary parity/performance/resources; real recognition/FS behavior); minor0.
Retain as independently evaluable experimental code, keep default off, do not promote or begin
Stage2 automatically. The next limitation is actual phone parity, net delivery and recognition
evidence; inference scheduling alone cannot solve continuous transitions or model generalization.

API reference used for interpreter ownership: [Google LiteRT Java Interpreter](https://developers.google.com/edge/api/tflite/java/org/tensorflow/lite/Interpreter).
Each interpreter owns resources and is not thread-safe; the implementation shares neither
interpreter instances nor mutable input/output storage between simultaneous operations.
