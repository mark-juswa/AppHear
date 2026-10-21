# Perception throughput: pipelined Candidate01 pose (2026-10-20)

Scheduling-only experiment behind a new default-off debug flag. No model weights, thresholds, S2,
decoder, materializer, WORD or SentenceBuilder changed. Protected TEST, E6 and Tier 3 were not
opened. Nothing committed. Device: Xiaomi M2101K7AG (3ab64582), front camera, WORD owner, one
non-expert signer (engineering measurement, **no accuracy claim from the live runs**).

## Answer

| Question | Result |
|---|---|
| Does pipelining reach ~7.5 observations/s live? | **No: 6.52 obs/s** vs 5.60 and 5.12 for the serial runs before and after it (+16% / +27%; +22% vs their mean) |
| Are per-frame Candidate01 outputs unchanged? | **Yes, bit-identical** on recorded frames, for the shipped budget, on all four engines (device + host check) |
| Does the flag-off path behave exactly as before? | **Yes**: the refactored serial path equals a verbatim copy of the pre-change analyzer, bit-for-bit, on all four engines |
| Predicted end-to-end effect at the measured cadence | **+3.7 points correct words natural (44.6% → 48.3%), +3.3 continuous (25.3% → 28.6%)**, fewer extra events in natural signing |
| Cost | **+~260 ms capture→observation latency** (p50 305/328 → 578 ms), **+~100% of one CPU core** (≈195% → 305%), +~7 MB PSS |
| Recommendation | **Keep the flag off; do not enable it in a debug engine yet.** One bounded follow-up (below) addresses the latency and contention first |

## 1. What changed (all behind `-PrecognitionV3PipelinedPose=true`, debug only; release hard-off)

- `Candidate01FrameAnalyzer`: new `Candidate01PipelineBudget` and a pipelined path. On the camera
  thread, frame *t* is preprocessed into one of two alternating native slots, the CameraX image is
  released at once (the native kernel keeps its own pixel copy), and DWPose(*t*) is submitted to a
  dedicated `AppHearV3Pose` thread. The same thread then refines the hands of frame *t−1*, builds its
  observation, and calls the owner, `session.consume`, the overlay and the UI. Session, owner and UI
  work stays on the CameraX executor thread exactly as before. Observations are emitted in capture
  order with their own capture timestamps; frame *t*'s observation is emitted when frame *t+1*
  arrives (a frame still in flight at a reset is dropped, as if CameraX had replaced it).
- The serial path is the old code moved into a shared `emit()`. With the flag off, no new thread,
  slot or log line exists, and the timing trace is byte-for-byte the old one.
- Thread budgets are explicit: `DWPoseTRunner(intraOpThreads, allowSpinning)` and
  `HandRefinerRunner(threads)`, with defaults identical to before (2 / spinning / 2). Gradle accepts
  only parity-proven pipeline budgets (pose 2 threads; hands 1 or 2) and refuses the flag together
  with parallel hands.
- Owner safety: an owner that reads pixels keeps the serial path (`ownerReadsImage`). Only the
  manual, non-continuous fingerspell capture reads pixels; the live build is continuous, so its
  owner receives a `ReleasedImageProxy` that throws on any pixel or metadata access.
- `PhoneProductionSession.open` is `internal` instead of `private` (visibility only), so tests can
  pin an engine without touching user settings. `recognitionV3ProfileLimit` (default 240) bounds the
  opt-in trace.

## 2. Parity evidence

`PipelinedPoseParityInstrumentedTest` runs the **real analyzer** on recorded frames through a fake
CameraX `ImageProxy`, comparing every raw-v1 field (plus ROI and proposal flags) as raw IEEE bits;
wall-clock fields are excluded. Inputs:
(a) the 51 real phone RGBA frames of the Stage 1 test;
(b) a contiguous 174-frame signing stream: 12 held-out DEV clips (ASL Citizen P12), every 4th 30 fps
frame, JPEG decoded on the device, with the decoded input hashed in every arm.

Device run, 2026-10-20 (`perception_throughput/device/`):

| Comparison | Frames | Result |
|---|---:|---|
| Legacy (verbatim pre-change copy) vs new serial, all 4 engines, stream | 175 each | identical; identical recognition output (12 commits on the experimental engines) |
| Serial vs pipelined (2 pose threads, spin, 2 hand threads), all 4 engines, stream | 174 each | **identical**, including every committed word and sentence |
| Serial vs pipelined p2/spin/h2, p2/nospin/h2, p2/nospin/h1 — phone frames | 51 | identical |
| Serial vs pipelined **p1**/nospin/h1 — phone frames | 51 | **differs** at observation 0 (`hand_proposal_support`): one DWPose thread changes ORT output bits |
| Pixel-reading owner + flag → stays serial, owner reads pixels | 4 | pass |

The host re-check (`tools/recognition_v3/compare_pipeline_parity.py`) independently parsed every
dump and agrees (12 of 13 pairs identical; the one failure is p1).
Not run because that test aborted at p1: p2/nospin/* on the signing stream. The p1 arm is now removed
from the test and forbidden by Gradle. Host tests: 5 new tool tests + 18 existing trace tests pass.
Android unit tests: 274/275; the one failure is the pre-existing `OriginalWordBatchTest` manifest
mismatch seen in every checkout.

Recorded-input throughput, no camera or preview (the pipeline's ceiling): serial 8.3–8.7 frames/s
→ pipelined 11.5–11.9 (Stable/Experimental) and 7.0–7.1 → 9.9–10.2 (WORD-blend engines).

## 3. Live device measurement (front camera, WORD, A/B/A, 90 s after 10 s warm-up)

| Run | obs/s | Mean interval | 1/2/3/4-frame gaps | Capture→obs p50 / p95 | DWPose p50 | Hands p50 | CPU (1 core = 100%) | PSS |
|---|---:|---:|---|---|---:|---:|---:|---:|
| Serial A | 5.60 | 178 ms | 2 / 38 / 52 / 8 % | 305 / 372 ms | 80 ms | 55 ms | 206% | — |
| **Pipelined B** | **6.52** | **153 ms** | 14 / 49 / 32 / 6 % | **578 / 687 ms** | 128 ms | 115 ms | 305% | ~307 MB |
| Serial C | 5.12 | 195 ms | 0 / 21 / 66 / 12 % | 328 / 372 ms | 77 ms | 109 ms | 185% | ~300 MB |

- **Contention, not idle time, limits the gain.** Overlapped, DWPose slows from ~80 to 128 ms and
  hands to 115 ms. The `AppHearV3Pose` thread uses ~75% of a core on top of the existing work. The
  Snapdragon 678 has two big cores; the pipeline puts 4 inference threads on them plus camera,
  preview, S2 and UI.
- **Latency is the main cost.** The observation of frame *t* is emitted after the hands of *t*,
  which run only once frame *t+1* has arrived and DWPose(*t+1*) has been submitted. Under
  contention that adds ~260 ms. Words therefore commit ~¼ s later on screen, even though decoder
  decisions (timestamp-based) are unaffected.
- Thermal: status 0 throughout; battery 39.8–41.5 °C. The thermal HAL exposes no temperatures, and
  the runs were short (~100 s): **sustained thermal behaviour is NOT MEASURED**. Camera drops are
  NOT MEASURED (gaps are reported as gaps).
- Scenes differ between runs (hands present, two-hand frames: compare serial A vs C hands wall),
  so treat ±0.5 obs/s as run-to-run spread.

## 4. Predicted end-to-end effect (offline, unchanged models)

`docs/audit/probes/word_accuracy/e2e_camera_grid.py` reuses `heldout_dev_e2e.py`: the same
signer-disjoint DEV streams and seed, S2-R3 Arm A e10, CONFIRM_BOUNDARY_70, materializer and
WORD_BLEND_02. It only places each observation on the 15 fps camera grid, with k-frame gaps drawn
from the **measured** live distributions. The harness first reproduced the reported 133.333 ms
run exactly (415 / 246 correct words).

| Cadence (3 seeds) | NATURAL correct / detected / precision / extra per min | CONTINUOUS correct / detected / precision |
|---|---|---|
| Serial as measured (188 ms mean) | 44.6 / 75.2 / 54.2% / 1.61 | 25.3 / 52.2 / 47.8% |
| **Pipelined as measured (153 ms mean)** | **48.3** / 80.8 / 56.0% / 1.24 | **28.6** / 55.2 / 51.1% |
| Δ | **+3.7** (seed range 46.9–50.7) | **+3.3** |
| Reference: every 2nd frame (133 ms) | 51.0 / 84.6 / 57.1% / 1.02 | 30.4 / 56.4 / 53.2% |

The measured pipeline captures a bit over half of the gain a steady 133 ms cadence would give
(+6.8 / +3.9 vs 200 ms). Irregular gaps (14% 1-frame and 38% 3/4-frame) add seed-to-seed spread.
Live captures are engineering runs and contain no lexical ground truth, so these remain predictions.

## 5. S2 / decoder cadence check

- **Decoder timers are in ms but sit exactly on the camera grid**: 133.308, 266.616, 399.924 and
  533.232 ms are 2, 4, 6 and 8 × 66.654 ms. On the phone, 2-frame gaps fall **below** 133.308 ms in
  38% of pipelined gaps (5–12% serial), because the frame period alternates between 66.654 and
  ~66.76 ms. The PRE-gap bridge (`elapsed < preGapResetMs`), minimum-active and post-confirm
  comparisons therefore flip with microsecond jitter. Offline 30 fps timestamps always land on the
  ">=" side. Bound: with every gap just below the edge (`--time-scale 0.9998`), natural is
  unchanged (51.0%) and continuous drops 30.4% → 29.3%. The device behaviour lies between. This is
  pre-existing (it already affects serial runs) but matters more at 2-frame cadence. No threshold
  was changed.
- **S2 receptive field is 61 observations**, not a time span: 12 s at 5/s, 8 s at 7.5/s. Offline
  results at 133 and 100 ms show no harm.
- The materializer ring buffer (256 observations / 30 s) is age-bound below 8.5 obs/s. WORD uses
  the DENSE view (max 96 observations ≈ 12.8 s at 7.5/s). The S2 features use per-observation
  deltas and dt: cadence-dependent by construction, and covered by the offline runs.

## 6. Risks

1. **Latency +~260 ms** per observation in the current "emit on next frame" design: the largest
   UX risk ("responsiveness preserved").
2. CPU +~100% of a core: battery and sustained thermal not measured; the Stage 1 report still has an
   unexplained phone closure after live runs. This session saw several USB/ADB resets during
   captures (transport id 1 → 3), with no app crash observed.
3. Threshold-edge flips (§5) change event boundaries slightly at 2-frame cadence.
4. Thread counts are not free levers: 1 DWPose thread changes output bits. Any budget change needs
   the parity test (the build now rejects pose ≠ 2).
5. The last frame before a reset is dropped (one observation), and a manual (non-continuous)
   fingerspell build silently keeps the serial path.

## 7. Recommendation

**Do not enable the flag in a debug engine yet.** The throughput gain is real and output-safe
(+16–27% observations, predicted +3–4 points correct words), but it costs ~¼ s of extra latency
and a full extra core, while the target 7.5 obs/s is not reached.

One bounded follow-up before deciding, same parity test and A/B/A protocol:
1. Emit each observation as soon as its own hands finish: run the hand stage on a second worker and
   post the result to the camera thread, instead of waiting for frame *t+1*. That removes the deferral.
2. Lower contention: hands 1 thread + pose spinning off (`p2/nospin/h1`, already bit-identical on
   phone frames; still needs the signing-stream parity run).

Enable in a debug engine only if live ≥ ~7 obs/s, latency within +100 ms of serial, and a
≥10-minute run shows no thermal throttling or instability.

## 8. Still needs the device

- Parity of `p2/nospin/h1` and `p2/nospin/h2` on the 174-frame signing stream.
- Live A/B/A of any follow-up variant; rear camera (30 fps) not measured.
- Sustained (≥10 min) thermal, battery and stability run; camera drop counts (sensor-timestamp join).

## Reproduce

```bash
python tools/recognition_v3/build_pipeline_fixtures.py --data-root "<data root>" --stage1-fixtures "<recognition-v3-stage1 artifacts>/android_fixtures" --out artifacts/recognition_v3_pipeline/android_fixtures
```
Build with the live-baseline properties plus `-PrecognitionV3FixtureDir=...` (and
`-PrecognitionV3Profile=true -PrecognitionV3ProfileLimit=2000 [-PrecognitionV3PipelinedPose=true]`
for the live arms). Run `PipelinedPoseParityInstrumentedTest`, pull
`files/recognition_v3_pipeline_parity/`, then run `compare_pipeline_parity.py <dir>`. For live
captures, `tools/recognition_v3/run_pipeline_measurement.ps1` (the user opens ASL Recognition;
instrumented launches fail on MIUI). For predictions, `e2e_camera_grid.py --gap-mix` with the
measured `interval_camera_frames`.
Evidence: `docs/audit/probes/word_accuracy/perception_throughput/` (APK and fixture hashes in
`device/manifest.json`). Raw traces, dumps and APKs: `artifacts/recognition_v3_pipeline/` (ignored).
The user's original APK pair was restored with `adb install -r` and verified by hash, with
`firstInstallTime` unchanged and engine/mode preferences intact. The parity dumps (~1.7 MB) remain
in the app's `files/recognition_v3_pipeline_parity/`.
