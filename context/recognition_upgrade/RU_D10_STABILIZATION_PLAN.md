# RU-D10 Recognition Stabilization

## Scope

Exactly two independently compiled, debug-only candidates are evaluated against the unchanged
runtime: A (`-PruD10A=true`) and B (`-PruD10B=true`). Release builds and ordinary debug builds set
both false. No dataset, model, MediaPipe setting, threshold, S4 feature, S6, or S7 change is in
scope.

## Measured baseline and bottleneck

Existing Xiaomi profiling reports approximately 1.7 ms conversion, 14 ms rotation, 100 ms hand,
110 ms pose, 0.5 ms recognition, and 130 ms wall time. Hand and pose already execute in parallel;
pose cadence 2 and `KEEP_ONLY_LATEST` are already active. Later ordinary-device smoke observed
roughly 9.6-12.7 processed FPS, while the evidence-heavy RU-D7 attempts averaged about 4-5 FPS with
0.27-0.35 second tail gaps. MediaPipe inference is the dominant floor. VIDEO/LIVE_STREAM, rotation
offload, detector/model/confidence changes, cadence changes, and feature changes are explicitly
excluded because they do not meet the low-risk parity boundary.

The one concrete low-risk continuity defect is resource lifetime: converted and rotated Bitmaps
and their MPImage wrappers were not explicitly released after both landmarker calls and diagnostic
copying completed. Candidate A bounds those lifetimes. It may reduce GC/tail stalls but is not
expected to materially reduce the approximately 100 ms landmarker latency.

## Candidate B contract

Candidate B bridges `candidate → one interruption → candidate` only when S5 already has positive
onset accumulation, hand presence remains true, the raised gate remains true, and motion remains at
or above the unchanged `theta_off`. It never changes `theta_on`, `theta_off`, `k_on`, or release.

Frozen RU-D7 replay has exact baseline S5/window-source parity. B recovers KNOW R1 and WE R2 onset
and adds zero onsets outside all 26 annotated sign spans. It also changes KEEP R2, which is not
credited because that attempt is sign-form-uncertain. Crucially, the credited onset recoveries do
not produce target commits and the x86 diagnostic replay changes KNOW R1, SISTER R2, and WE R2 from
no commit to wrong commits. B therefore remains off and fails the current end-to-end keep gate.

## Four-way evaluation

| Mode | Frozen-trace status | Device timing status |
|---|---|---|
| Baseline | Complete | Required as reference |
| A only | Recognition/S5 identical by construction | Required |
| B only | Complete; not promotion-ready | Included as timing/control identity |
| A + B | Same bounded S5 result as B | Included; cannot be promoted while B fails |

The prepared device benchmark runs each mode for 45 seconds with no hands in view, records stage
mean/p50/p95 plus processed inter-frame gaps, and counts no-hand S5 onsets and commits. Candidate A
is kept only if it improves a general timing/tail metric without crashes or false activation. A
small signed phone confirmation is considered only after that timing gate passes.

## Manual command

From the repository root:

```powershell
& '.\model\config\recognition_upgrade\run_ru_d10_stabilization.ps1' -Command Benchmark
```

Expected outputs are under
`artifacts/recognition_upgrade/ru_d10/device_benchmark_01/`: four preserved APKs, four full Logcat
captures, `ru_d10_device_timing.csv`, and `ru_d10_device_benchmark_summary.json`. Successful
completion prints `RU-D10 DEVICE BENCHMARK COMPLETE`, reports all four modes, and has `passed=true`.

## Final result

The initial structural parser reported all four modes present, but consolidated Logcat review found
native `SIGSEGV` crashes in both A-enabled modes, ending in
`android::BitmapWrapper::freePixels()`. The parser now treats AppHear native tombstones as failures;
its corrected summary has `passed=false` with A-only and A+B crash errors. Candidate A is reverted.

Candidate B is also reverted: although it recovered KNOW R1 and WE R2 onset with zero off-span
onsets, it changed three evaluable attempts from no commit to wrong x86 diagnostic commits. A+B
inherits both failures. The saved Baseline APK was reinstalled on the connected phone. No signed
phone confirmation is justified, and no further stabilization branch follows from RU-D10.
