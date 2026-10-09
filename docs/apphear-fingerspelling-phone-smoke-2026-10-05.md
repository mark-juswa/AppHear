# AppHear fingerspelling phone smoke — 2026-10-05

## Preserved installation and scope

F: research checkout remains `codex/current-working-text-to-asl-baseline-2026-09-29`,
HEAD `cc1f3949114d0ed1dab38d4428191151b37df358`, with prior dirty/untracked work preserved.
Installed integration comes from the isolated October 4 application worktree at
`cee71d9f181695847936eb5f3605ea37eab82a95`, not F:'s older Android source.
Saved/device APK SHA-256 is
`a70e4b4882c1da72513912381f75183d8ee8cd563086096be2839c6cc6573dc5`.
Frozen phone parity and ownership tests pass 2/2. The 640-file baseline check has
no unexpected changes; only the three documented integration seams differ.
No model, feature, crop, decoder, WORD/Context Assist semantics or release behavior changed.
Private APK remains local; no training, TEST access or training video capture.

## First completed physical session

The user was asked for exactly one AMY Start → spell → Done attempt and replied
"done". Preflight had zero reports; the next pull contained exactly one completed
report and zero failed reports. This establishes intended-prompt linkage, not signing correctness.
The user's self-reported imperfect signing limits interpretation. This is engineering
smoke, not a proficiency, CER, cross-signer or production-accuracy evaluation.

| Measurement | AMY attempt |
|---|---:|
| Raw prediction | `SAAME Y` |
| Observations | 47 |
| Capture wall duration | 8.293 s |
| Observation timestamp span | 8.134 s |
| Delivered observation cadence | 5.655/s |
| Gap median / p95 / maximum | 133.518 / 333.270 / 724.861 ms |
| Candidate01 median / p95 | 142.814 / 203.282 ms |
| Any accepted hand evidence | 18/47 observations (38.30%) |
| No retained crop | 29/47 observations (61.70%) |
| Retained visual slots / duplicate frames | 27 / 6 |
| Per-crop median / p95 | 34.777 / 35.154 ms |
| Appearance median / p95 | 9.370 / 9.938 ms |
| Added visual work per observation median / p95 / max | 1.928 / 90.977 / 498.901 ms |
| Sequence inference + greedy decode | 252.545 ms |
| Java / native heap snapshots | 25,663,040 / 183,027,344 bytes |

`finish_ms` excludes button-to-worker queueing, report writing and preview rendering;
it is not total user-visible finishing latency. Heap values are snapshots, not peak
memory. Source indices 97–143 cover 47 consecutive analyzer observations, but CameraX
frame drops are not directly counted. CPU two-thread inference is used.

The bounded session and model invocation succeeded; the raw spelling is incorrect
for the intended AMY prompt. Low hand/crop coverage merits further framing and
visibility checks. These aggregate diagnostics do not establish when letters were
performed or distinguish capture, signing, proposal/refiner or model failure causes.
The maximum crop/visual cost is retained as a measured outlier, without attributing
it to warm-up, scheduling or another cause. No performance optimization is inferred
from one attempt or from the unannotated prior WORD cadence window.

Original report: `artifacts/fingerspelling_android_01/oct04/phone/session_1791162234888.json`.
Its SHA-256 is `6b9f1905182473a55d9dc4e2b470e1607ea9d52516ee0e3f42349595f70544d0`.
Human linkage is stored separately in `human_session_linkage_2026-10-05.json`;
the pulled source JSON and automatic inventory are not relabeled.

## Remaining live checks

Retry and a separate BELLA attempt completed. The user explicitly reported the
preview `BELD DA`, matching the unique additional completed report
`session_1791162509867.json` (SHA-256
`0384afb00fb26996366d4f5137660125988f1fc26e379a1333b1328c2ff225bf`).
This links the intended BELLA prompt without asserting correct signing.

| Measurement | BELLA attempt |
|---|---:|
| Raw/confirmed-on-screen preview | `BELD DA` |
| Observations / capture wall duration | 68 / 10.903 s |
| Observation timestamp span / cadence | 10.731 s / 6.243/s |
| Gap median / p95 / maximum | 133.308 / 266.616 / 333.270 ms |
| Candidate01 median / p95 | 128.379 / 188.300 ms |
| Any accepted hand evidence | 29/68 observations (42.65%) |
| No retained crop | 40/68 observations (58.82%) |
| Retained visual slots / duplicate frames | 40 / 5 |
| Per-crop median / p95 | 34.815 / 35.000 ms |
| Appearance median / p95 | 9.317 / 9.548 ms |
| Added visual work median / p95 / maximum | 0.685 / 89.374 / 90.277 ms |
| Sequence inference + greedy decode | 72.649 ms |
| Java / native heap snapshots | 30,093,512 / 186,403,400 bytes |

Both bounded attempts completed without a failed-session report. BELLA's cadence
is close to the earlier 6.23/s phone estimate, but two uncontrolled attempts do not
establish a representative distribution or a causal WORD-versus-visual slowdown.
Crop processing is a measured additional cost (~35ms per retained slot); do not
optimize or change semantics from these data alone. Completed sequences do not
preserve the intended letters accurately. Sparse accepted-hand coverage and
unverified signing prevent a confident model/domain diagnosis. No CER benchmark.

Start/Done, preview and Retry have physical evidence. The user replied "works"
after the explicit Clear and return-to-WORD check: preview cleared, normal WORD
controls returned and camera continued. Use must remain deliberate;
neither incorrect preview was automatically committed. Confirmation/repeated-letter
buffer mechanics have automated test evidence, but these two predictions do not
prove correct repeated-letter recognition. A proficient/verified signing sample,
matched cadence profiling, peak memory/drop/thermal checks and broader phone-domain
recognition remain later gates. Numerical parity must not be conflated with accuracy.

## Decision and next bounded check

The manual session/preview/reset route operates on the target phone with verified
numerical parity. Recognition usefulness is not established: both intended prompts
are wrong. Preserve the installed experimental implementation and frozen models.
Next recognition evidence should use clearly visible, verified signing and distinguish
lead-in/release from signing content before diagnosing missing-hand coverage.
Do not expand data, train another model, tune thresholds or optimize the visual
path solely from these two imperfect-signing attempts. A deliberate physical Use
check and representative profiling remain open; no production promotion.

FINGERSPELL_ANDROID_LIVE_SMOKE_COMPLETED_WITH_RECOGNITION_LIMITS
