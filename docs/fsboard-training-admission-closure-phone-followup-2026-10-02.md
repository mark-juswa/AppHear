# FSBOARD_TRAINING_ADMISSION_CLOSURE — connected-phone follow-up

This supplements the immutable [12-clip closure](fsboard-training-admission-closure-2026-10-02.md).
The previously unavailable phone was connected on 2026-10-02. No training, Android changes,
perception tuning, video download, offline extraction or custom dataset collection occurred.

## Repository and installed build — VERIFIED

- Checkout: `codex/current-working-text-to-asl-baseline-2026-09-29`,
  HEAD `cc1f3949114d0ed1dab38d4428191151b37df358`.
- Protected WORD baseline: `76d93cecd85bf9f76064d320aa4a5791b5f0704a`,
  `baseline/apphear-s2-r2-integration-complete-2026-09-26` and
  `codex/recognition-stable-ru-d10`. No branch/ref changes.
- Preserved dirty files: `APPHEAR_CONTINUOUS_TRANSITION_AND_READINESS_01_REPORT.md`,
  `context/feature-schema.md`, `context/progress-tracker.md`, `memory.md`; existing untracked
  AZ/FSboard tools, datasets, reports, tests, scratch files and phone pulls remain in place.
- The installed APK is **not** the checkout's saved APK. Its SHA-256 is
  `ca7e7e449a36c549f454fc621cc7ecc1181192e0c58129c31b0a21c0efcf128c`, identical to the existing
  APK in the separate `feature/conversation-phrase-assist-mvp` worktree. That worktree is clean
  at `75f5959c06b96c893bb1c8f266f7b3deb529ead6`, later than the closure's earlier `801fb1d`
  inventory. The later commits record phone/UI verification and the private phone build.
  APK identity does not prove that every byte was built from the subsequent documentation HEAD.
- Checkout APK SHA-256 remains
  `a61c09d0b254753d44d992739734467c5a7e8d1f0363f317ad96b9b5dc57a3b7`.
  No APK was built, installed, rolled back or reconfigured during this follow-up.
- All 24 compared Candidate01-model/native-library APK entries are byte-identical between
  installed and checkout APKs. Twelve preprocessing/pose/refiner/math/raw-observation classes
  have identical disassembly after removing file-address/table relocations. The analyzer/session
  differ through existing Context Assist evidence forwarding; this measurement includes that
  installed normal-app overhead. It is not an exact-checkout APK benchmark.
- All 883 protected workspace files remain hash-identical. The previous closure's 77 indexed
  files and report hash still validate. Fixed manifest SHA-256 remains
  `23f1bf347f016f3ffe208d4dc181038c1d814a00c4c340c0dc669b0db9bcd000`.

## Fresh normal-app cadence — VERIFIED, with stated measurement limits

The user opened the ordinary Sign-to-Text camera and confirmed readiness, then alternated rest
with hand movements/spelling. Foreground activity was `RecognitionActivity`; startup logged
`normal backend=Candidate01 package=S2_R2_CANDIDATE`. No debug capture activity, video/landmark
recording, debugger, method trace or additional inference pipeline was used. Existing normal
WORD processing and commits continued; their labels are not evaluation results.

Device: Xiaomi M2101K7AG, Android 12 / SDK 31, battery saver off, USB charging. Battery was
61%, 38.0°C at the start and 60%, 38.7°C at final inspection. This is one live period under
those conditions, not a cold/warm/content-stratified performance study.

The normal analyzer increments `sourceIndex` once when constructing each actual
`PhoneRawObservation`. After `PhoneProductionSession.consume`, it logs index/FPS only when
decoder state changes. Start/end log snapshots together retain the run's index-zero origin;
the later snapshot alone had lost early lines from the bounded Android log buffer.
Endpoints were selected by a reproducible rule: first retained state entry at least 10 seconds
after index zero, then last state entry in the snapshot taken before requesting the user stop.

| Metric | Result |
|---|---:|
| Start/end indices | 47 / 535 |
| Start/end log epoch seconds | 1790927303.404 / 1790927381.720 |
| Elapsed completion-log interval | 78.316 s |
| Actual observation intervals | 488 |
| Observations including both endpoints | 489 |
| Delivered completion cadence estimate | **6.231166 observations/s** |
| State-conditioned rolling FPS range | 4.3–6.4 |
| Median / p95 / max observation gap | Unavailable |
| Candidate01 processing p50 / p95 | Unavailable |
| Exact camera-drop count | Unavailable |

This counts actual delivered observations through indices; elapsed time uses sparse completion
logs rather than per-frame source timestamps. Sparse state-transition gaps must not be called
observation gaps, and their FPS distribution is not a full-frame distribution. Normal
`Candidate01FrameAnalyzer` retains processing times only in transient observations and does
not persist per-frame timestamps/timing. Legacy `AppHearPerf` instrumentation is not wired to
this analyzer. Those unavailable percentiles were not inferred or supplied from a debug
capture harness. Requested camera rate remains 15 FPS with `KEEP_ONLY_LATEST`; throughput
below that request supports a backpressure concern but does not quantify actual dropped frames.

Source references: `Candidate01FrameAnalyzer.analyze` (source index, consume, sparse state log),
`RecognitionActivity.start` / `bindPhoneCamera` (normal session, front camera, 480×360 target,
15-FPS request, one camera executor), `FpsTracker.tick` (1500-ms rolling completion-time FPS).

## CTC structural capacity at measured rate — CALCULATED approximation

Only the already-pinned v13 TRAIN/DEV metadata was read. No TEST metadata/payload was needed.
Subset policy remains uppercase ASCII letters/spaces with at least one letter, without trimming
or inventing character boundaries. Signer roles remain official and unchanged.

For each transcript:

`required = character count including spaces + adjacent repeated-character pairs`

`available ≈ floor(metadata duration × 6.231166) + 1`

This assumes one output step per actual observation, no encoder temporal stride, approximately
uniform cadence and an observation at time zero. No resampling, interpolation or manufactured
observations was performed. Results use the unrounded measured rate.

| Official role | Clips / signers | Full-clip failures | Publisher-window failures |
|---|---:|---:|---:|
| TRAIN | 64,410 / 117 | 1,734 (2.6921%) | 6,772 (10.5139%) |
| DEV | 2,352 / 15 | 17 (0.7228%) | 131 (5.5697%) |

Full clips include lead-in/release, making that bound optimistic for useful signing evidence.
Publisher annotation windows are a timing sensitivity check, not character boundaries or a
new crop policy. Actual output length must be checked on extracted sequences before any future
CTC loss. Missing-hand observations remain masked timesteps; deleting them changes capacity.

**Interpretation:** this phone rate does not make the majority of the selected alphabetic corpus
structurally impossible for unstrided CTC. It supports useful capacity for one controlled first
baseline, conditional on source admission. It does not prove J/Z trajectories survive sparse
sampling, sufficient CTC alignment slack, character accuracy or deployed spelling accuracy.
Source video cadence is mostly ~30 FPS; live ~6.23-Hz evidence still carries motion-loss risk.
Final encoder/adapter width, window, stride and phone decoder remain unimplemented/unfrozen.

## Remaining evidence and decision

The phone-disconnection blocker is closed for **current installed normal-app delivered cadence**,
with the build scope and unavailable metrics above. A benchmark of the checkout APK specifically
would require a separately agreed build switch; none was performed. Exact gap/timing percentiles
would require additional observability and are not silently treated as measured. They do not
invalidate this bounded delivered-rate calculation.

The independent reflection blocker remains: three fixed clips have exact visual unmirrored
evidence; nine retain `UNKNOWN` and `training_admitted=false`. Available public Record These
Hands history starts after the selected 2021–2022 captures, and the publication identifies a
precursor app without a session-to-build mapping or saved-pixel convention attestation. Current
source strongly supports unmirrored saving but cannot establish the historical precursor/v13
conversion convention for both strata. No source was flipped or admitted on handedness guesses.

The next bounded step is dated precursor code/APK plus collection mapping, **or a publisher/
custodian attestation covering saved front-camera reflection for both DAUN/MacKenzie and v13
clip conversion**. Readable clothing text in every clip is not required if that scope is established.
No publisher message has been sent; sending one requires explicit user authorization.

The twelve-clip diagnostics still support one first Candidate01→common phone evidence→sequence
encoder→character-CTC baseline once reflection admission closes. They do not justify training
now, changing perception, selecting easier clips or searching for another dataset.

Evidence: `datasets/fingerspelling/fsboard_candidate01_admission_20261002/phone_cadence_followup_01/`:
`cadence-assessment.json`, `ctc-measured-cadence-approximation.json`, `installed-build-attribution.json`,
`perception-class-parity.json`, source log snapshots, and `preservation-check.json`. Previous
receipts/indexes remain immutable. Local private build copies/disassembly are ignored from Git.

FSBOARD_TRAINING_ADMISSION_HOLD
