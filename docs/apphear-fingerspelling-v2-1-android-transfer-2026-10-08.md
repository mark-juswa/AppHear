# AppHear V2.1 epoch034 Android engineering transfer

2026-10-08. Decision: **retain V2.1 epoch034 as the experimental geometry-only
FINGERSPELL candidate**. Export, numerical/text parity, bounded runtime, ownership
and preservation pass. **The supervisor's AMY retries remain inaccurate.** This is
an engineering transfer decision, not reliable spelling or production promotion.

## Scope and authoritative project

Research branch `codex/current-working-text-to-asl-baseline-2026-09-29`, HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358`. Application worktree:
`C:\Users\Gigabyte\.codex\worktrees\fingerspell-oct04-integration\5. Apphear3`,
HEAD `cee71d9f181695847936eb5f3605ea37eab82a95` (October4 application baseline).
Existing dirty/untracked work was preserved. The research checkout's older Android
sources were not used as the application authority.

A package-admission branch was added to isolated `FingerspellModels.kt`, a
separate `SequenceV21ParityInstrumentedTest.kt` was added, and the epoch038 test
received a candidate-applicability guard.
No session, analyzer, activity, Android UI, WORD lifecycle, sentence or Context
Assist code was changed. Existing async model loading, full-buffer Done-time
inference, manual ownership, preview and confirmation remain authoritative.

No training, acquisition, Candidate01 extraction, quantization, new auxiliary
inference, visual residual, decoder tuning or TEST access occurred.

## Exact checkpoint/package identities

| Artifact | Identity |
|---|---|
| Candidate ID | `SEQUENCE_V2_1_EPOCH034_GEOMETRY_ONLY` |
| Main-only checkpoint | `runs/fingerspelling_sequence_v2_1_01/best_candidates/epoch_034.keras` |
| Checkpoint SHA256 | `3f92287c5ee82b2e0de1d396c4d27fe3b0efaed8af23b79b878740a56f1af638` |
| FP32 TFLite SHA256 | `e78de274b967acf0ea9d30bd3f3ac4422a1ef8ebdd95c8676b57dd05fed75c4c` |
| TFLite size | 1,305,012 bytes |
| Manifest SHA256 | `8edc998728fa41883abacbc8382359d6d61621bc259da78ca7c2ab6f8126d01e` |
| Private installed app APK SHA256 | `068c744df22acefdc48f44246e2f533127c73d63a332d3e2617f9c52d3b24c4e` |
| Installed test companion SHA256 | `624077246a6f8c5771c702143aa8657293c6dfe131b071b73402d0ce27e72aa5` |
| Preserved epoch038 rollback APK SHA256 | `c3e075dde2f49edb4014eb705f4ded721d4b6f18f0a78b7446ba6b27d7b6de35` |

The checkpoint hash is checked before Keras loading. The model has exactly 292,956
inference parameters and no local auxiliary layer. FP32 builtin-only TFLite,
dynamic `[1,T,405]` and `[1,T,1]` inputs, one `[1,T,28]` output. Symmetric masked
TCN, eight64-channel blocks, stride1, receptive field1021. There is no appearance
model in this package. Frozen Adapter.v1 schema/config/implementation/column hashes
are enforced by the Android loader before loading; its feature math was not edited.

Blank27, SPACE26, penalty0.5 exactly once, prefix beam10 Top-1, greedy internal
diagnostic unchanged. No Top-N UI or language/spelling correction.

The installed APK hashes were read on Xiaomi and match the retained private
builds. Loader checks the exact manifest, adapter and model SHA on device.
APKs contain the previously authorized local service configuration: phone-only,
private, not distribution artifacts. No service credentials appear in this report.

## Export and parity

Six deterministic metadata-selected governed sequences × native/phone views, plus
two synthetic contract cases:14 model fixtures. Roles are TRAIN DAUN, TRAIN
MacKenzie and DEV-A; short/long, SPACE, repeat, J/Z and missing/partial/duplicate
hand evidence are represented. No DEV-B selection/inference or TEST access.

| Gate | Result |
|---|---|
| Keras→TFLite maximum absolute logit difference | 0.0000319481 |
| Keras→Xiaomi maximum absolute logit difference | 0.0000233650 |
| Host TFLite→Xiaomi maximum absolute logit difference | 0.0000123978 |
| Python→Android Adapter observations | 1,246; maximum difference0 |
| Main model greedy/beam strings | 14/14 exact at all three levels |
| Masked-padding model checks | 14; host maximum difference0, Xiaomi0.00000476837 |
| Existing prefix-beam reference fixtures | 523/523 exact strings; maximum score difference8.88e−15 |

Host tolerance: absolute/relative2e−4. Device absolute2e−4. No tolerance was
relaxed. Masked garbage padding17.0 cannot change valid observations. Test-only
masked outputs are excluded when decoding padding fixtures; production sessions
already contain only actual observations. Hand-missing actual observations are
retained, not treated as padding. Both chronological geometry slots remain intact.

V2.1 deliberately uses future context. The new exporter/test therefore checks
full-sequence parity and mask invariance, not causal prefix invariance. The
epoch038 exporter, fixtures and causal assertions remain unchanged; its test
now skips correctly when another package is loaded. Export ran
twice for the padding-fixture decoding correction; model and manifest hashes were
identical. This changed a diagnostic, not model or production decoder behavior.

Phone runs on the existing Android TFLite2.16.1 CPU interpreter,2threads; host
TensorFlow2.21.0. No Flex/custom operators, delegate, INT8 or GPU required. The
existing dynamic-output tensor-buffer handling works without modification.

## Xiaomi saved-fixture runtime

Model warm values use the last of three invocations per fixture; all-invocation
times are separately retained. Six cases per real view. Established empirical
percentile rule: sorted index floor((n−1)×p); small-N values are descriptive only.

| View | T range | Model p50/p95/max ms | Beam p50/p95/max ms | Model+both decoders p50/p95/max ms |
|---|---:|---:|---:|---:|
| Native | 91–331 | 18.68 /37.85 /45.00 | 105.59 /191.96 /254.66 | 146.85 /237.61 /274.96 |
| Phone-like | 19–67 | 7.46 /10.42 /11.85 | 16.25 /21.78 /38.86 | 22.29 /34.36 /49.44 |

Cold/earlier native invocation maximum108.59ms. Separate523 frozen-logit decoder
suite: native p50/p95171.33/378.48ms; phone31.88/53.48ms. It uses different logits
and lengths, so it is not a model-runtime comparison. Synthetic worst decoder
case2,503ms is a stress fixture, not observed live Done latency. Full retained
timings and timestep counts are in the JSON evidence.

Parity heap snapshots: Java3,428,776→20,932,776bytes;
native10,986,736→21,487,536bytes. They are neither peak memory nor isolated model
allocations. No runtime/memory failure observed. No latency optimization performed.

## Camera smoke — non-accuracy evidence

Supervisor confirmed attempts to spell AMY, controls work, and results are
inaccurate. Four completed new-candidate sessions were recorded; do not pretend
only one occurred or that signing was linguistically verified.

| Session suffix | Observations /observed-hand | Cadence/s | Greedy | Beam/preview | Model ms | Beam ms | Done processing ms |
|---|---:|---:|---|---|---:|---:|---:|
| 1791452659976 | 71 /21 | 6.24 | AMSEY | AMSEY |124.44|352.75|479.74|
| 1791452687577 | 50 /19 | 6.44 | ASEAY | ASEEAY |87.65|121.49|210.81|
| 1791452709363 | 42 /17 | 5.79 | AEAY | AEAY |74.51|90.42|166.68|
| 1791452721719 | 38 /16 | 5.83 | AMEMMEAYY | AMEMEAY |13.34|80.35|95.04|

All session manifests identify epoch034/405geometry/visualfalse. Preview diagnostics
equal beam Top-1. The supervisor confirmed functioning controls and returning to
WORD; exact displayed texts above come from runtime diagnostics, not a separate
human transcription of every preview. Retry/Clear/Use semantics also pass the
synthetic ownership test. No incorrect spelling was requested for confirmation.

Done time is model plus both decoders measured inside the worker; it excludes
button-queue delay and UI rendering. Live processing is slower than warm saved
fixtures, especially the first attempt. Report this rather than substituting the
warm numbers for actual sessions. Cadence5.79–6.44/s is a bounded descriptive
measurement, not controlled proof of a change from the historical6.23/s.

No proficient signer, verified letter boundaries, isolated A–Z test or controlled
phone accuracy benchmark exists. No training video/landmarks/logits were saved
or collected by this step. Sparse observed-hand evidence is confirmed; it does
not prove which missing frames caused which character error or that signer
execution was correct/incorrect. No signing blame or new accuracy claim follows.

## Validation, preservation and rollback

- 41 focused Python decoder/V2.1/input-review checks pass. Ruff and mypy pass for
  all four added transfer utilities. Console-only pyreadline destructor warning
  occurs after pytest completion; XML shows successful tests.
- 157 Android host unit tests pass,0failures/errors/skips; includes WORD raw/S2,
  RecognitionV2 parity, SentenceBuilder, ownership and18ContextAssist tests.
- Device runs:3tests (new numerical transfer, WORD decoder exclusion,523beam
  fixtures), then5tests (final mask/decode transfer, Use/Retry/Clear/WORD ownership,
 3 deterministic local ContextAssist regressions). No network inference test.
  New numerical test repeated after diagnostic padding correction; all passed.
- 1,599 inventoried existing files: two intended existing changes, the isolated
  loader and epoch038 test guard;1,597unchanged. A new test is additional.
  Candidate01, Adapter, models/checkpoints, WORD, ContextAssist, old exporters,
  session/owner/UI and both old package inventories remain unchanged.
- 235non-fingerspelling APK assets byte-identical to epoch038 rollback. No WORD
  model or UI asset substitution. Protected inventory is before/after hashes,
  including the separate authoritative worktree, not a clean-git claim.
- The cache-lock failure was tooling: abandoned Gradle process from a failed
  relative-path log pipeline; an absolute log path and scoped process cleanup
  restored the build. Mixed inherited {sha256,bytes} inventory records were
  normalized correctly; the initial audit assertion did not indicate file edits.

Old epoch038 and B2/residual packages/checkpoints/manifests are preserved and
remain separately admitted by the loader. Epoch038 rollback APK is unchanged:
`artifacts/fingerspelling_train4096_android_01/private_apks/app-debug.apk`.
Rollback is retained; its accuracy/parity is prior evidence, not a new device
rollback experiment in this phase. Old packages were not overwritten. The old test retains its numerical/causal
checks behind the applicability guard.

## Files added/changed and reproduction

Research additions:
- `tools/fingerspelling/android_sequence_v2_1_export.py`: pinned main-only FP32 export,
  deterministic governed fixtures; existing converter/fixture selector reused.
- `tools/fingerspelling/android_sequence_v2_1_port.py`: scoped isolated loader
  admission and separate non-causal device-test generation.
- `tools/fingerspelling/android_sequence_v2_1_evidence.py`: private APK identities,
  asset comparison, regression/preservation and JSON-only phone report collection.
- `tools/fingerspelling/android_sequence_v2_1_report.py`: saved-evidence summary.
- This report and append-only context/feature-schema, fingerspelling-android-v1,
  progress-tracker and memory state. No405schema change.

Authoritative application changes:
- `android/app/src/main/java/com/example/apphear/fingerspelling/FingerspellModels.kt`
- New `android/app/src/androidTest/java/com/example/apphear/fingerspelling/SequenceV21ParityInstrumentedTest.kt`
- `android/app/src/androidTest/java/com/example/apphear/fingerspelling/Train4096ParityInstrumentedTest.kt`: candidate guard only.

Evidence root: `artifacts/fingerspelling_sequence_v2_1_android_01/`.
Read `export_parity.json`, `model_manifest.json`, `xiaomi_fingerspell_sequence_v2_1_parity.json`,
`xiaomi_fingerspell_beam_parity.json`, `runtime_summary.json`, `session_*.json`,
`physical_smoke.json`, `live_session_inventory.json`, `preservation_before.json`,
`preservation.json`, `source_identity.json`, `unit_validation.json`, `python_tests.xml`,
`apk_identities.json`, `installed_apk_integrity.json`, instrumentation/build logs,
`engineering_decision.json`, and `private_apks/` (private phone-only).

From `F:\ASL DATASET\5. Apphear3`, inspect saved results without new inference:
`& .\.venv\Scripts\python.exe -m tools.fingerspelling.android_sequence_v2_1_report`.
Re-export, if explicitly needed:
`& .\.venv\Scripts\python.exe -u -m tools.fingerspelling.android_sequence_v2_1_export`.
The existing private build wrapper accepts this evidence directory via its
`-ArtifactDirectory` parameter; the old default remains the old residual package.

## Review and next action

Review: plan alignment PASS, protected system integrity PASS, experimental transfer
readiness PASS. Critical0, important1, minor0. Important product limitation:
AMY still incorrect and reliable A–Z/generalized phone accuracy unestablished.
No release promotion or automatic new model experiment is justified.

Retain the already-demonstrated offline letter improvement as experimental;
do not claim that transfer itself improves phone accuracy. The next separate
small roadmap task is exact no-usable-hand refusal, with independent feature
flag/tests. It would **not** refuse these four partly observable AMY captures,
and cannot fix their visible-letter confusion. Do not sell it as that fix.
Supervised handshape/appearance remains parked: zero trustworthy reviewed letter
labels and no qualified reviewer. No pseudo labels or additional geometry training.


Final candidate-applicability check: V2.1 parity passed again; epoch038 test skipped
by explicit candidate assumption as intended (one applicable pass/one skip, not
two parity passes). Old causal assertions remain intact for epoch038. The final
APK app hash is unchanged; companion SHA updated above. A subsequent ADB
collection transport failed after the final parity JSON had been pulled; previous
complete four-session inventory is retained. This is not a model/test failure.

FINGERSPELL_V2_1_ANDROID_PASS
