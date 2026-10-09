# A1 Independent-Clock Hands-First Perception

**Status:** EVALUATED / KEEP AS DEFAULT-OFF V2 FOUNDATION / NOT DEPLOYED  
**Frozen source baseline:** `7dd4fa05f2e7dffd3f06a2fdc88f90b1ea66836f`  
**Stable baseline APK SHA-256:** `208ECCFD06681F09100277AB0FF72BDE63E95CED7B86BC3ABE769FEBC04BCCF5`

## Isolated hypothesis

A1 tests only whether removing the lockstep hand→pose join and full-cycle `busy` barrier delivers
fresher/more frequent direct hand observations. It does not test pose cadence, MediaPipe mode,
landmark recovery, thresholds, models, feature math, or class-specific behavior.

## Runtime behavior

- CameraX remains `KEEP_ONLY_LATEST`, RGBA, `480x360`.
- Ingress converts/rotates each CameraX-delivered frame and offers the immutable upright bitmap to
  capacity-one latest-only hand and pose mailboxes.
- Hand runs on one long-lived worker and publishes immediately after `detectHands()`.
- Pose runs on one long-lived worker at the frozen current cadence (`pose_every_n=2`).
- A third capacity-one mailbox feeds one serialized recognition consumer.
- A hand timestamp `H` can use only the newest pose `P <= H`; future pose association is impossible.
- The maximum accepted pose age is supplied at launch and is frozen automatically as
  `ceil(BASELINE_1 pose-age p95 + BASELINE_1 inter-hand-publication-gap p95)` before A1 runs.
- Missing/expired causal poses produce `NO_CAUSAL_POSE`/`POSE_TOO_OLD`; no malformed 258-vector is
  sent downstream.

## Ownership and lifecycle

- `ImageProxy`: owned and always closed by analyzer ingress after conversion.
- Upright `Bitmap`: immutable shared read-only object retained by a reference-counted frame lease.
- Pending/in-flight hand or pose packet: owns exactly one lease reference.
- Published hand waiting for the consumer: transfers its lease reference to the hand observation.
- Supersession, rejection, inference completion, or shutdown releases the owned reference.
- `MPImage`: local inference-call wrapper; no explicit close. `Bitmap.recycle()` is never called.
- Pause/switch/destroy unbinds CameraX immediately. Worker join runs on the dedicated lifecycle
  shutdown executor, never the main thread. Landmarkers and recognizer close only after a successful
  join; on join failure they remain open rather than risking native use-after-free.

## Diagnostics and evaluator

`AppHearA1` records ingress, conversion, rotation, both mailbox lifecycles, inference intervals,
publication, causal join/rejection, consumer timing, and shutdown. The evaluator reports distinct
camera/accept/offer/inference/publication/pose/join/S4 rates; p50/p95/max gaps and latencies;
synchronizer yield/reasons; API-level hand/pose overlap; PSS; thermal status; ordering/future-pose
violations; and no-sign S5/commit/crash markers. Camera timestamp and app monotonic timestamp remain
separate; analyzer-arrival→S4 is the valid monotonic latency proxy.

## Frozen Stage-1 gates

A1 passes only when all safety/non-regression gates pass and:

- fresh hand publications/sec `>= 1.15 * Baseline`, **or** p95 inter-hand gap
  `<= 0.80 * Baseline`;
- p95 hand-inference-end→S4 `<= 0.75 * Baseline`;
- S4 observations/sec `>= 0.95 * Baseline`;
- synchronizer yield `>= max(0.90, Baseline - 0.05)`;
- valid pose-age p95 stays within the frozen Baseline-derived ceiling;
- no future, duplicate, or out-of-order hand consumption;
- no crash, ANR, native fault, no-sign onset/commit;
- peak PSS `<= 1.15 * Baseline`; and thermal decay is not over five percentage points worse.

Any failure produces `REJECT_A1_HARD_STOP`. No signing run or A2 implementation follows a failure.

## Manual device command

From the repository root:

```powershell
.\model\config\recognition_upgrade\run_a1_independent_clock.ps1 -Command Benchmark -SecondsPerMode 120 -WarmupSeconds 20
```

This builds one instrumented debug APK, runs `BASELINE_1 → A1_1 → A1_2 → BASELINE_2`, freezes the
pose-age ceiling after `BASELINE_1`, samples PSS/thermal state, and writes results under
`artifacts/recognition_upgrade/a1_independent_clock/device_benchmark_02/`. The earlier
`device_benchmark_01` is retained as invalid tooling evidence because post-run logcat collection
covered only 1-13 seconds of each intended 100-second measurement. It does not run a signed
sentinel.

## Stage-1 result

The corrected live-logcat run `device_benchmark_02` passed every preregistered gate. Baseline versus
A1 aggregate results were: fresh hands `5.300 → 7.077/s`, S4 `5.304 → 7.063/s`, p95 inter-hand gap
`258.3 → 169.3 ms`, and p95 hand-inference-end→S4 `63.3 → 3.9 ms`. A1 synchronizer yield was
`0.9980`; there were three `POSE_TOO_OLD` rejections, no ordering/future-pose violations, no crash
markers, and no no-sign onset or commit. Peak PSS increased `453,208 → 461,531 KiB` (`+1.84%`).

The expected tradeoff was older reused pose: p95 pose age increased `296.3 → 505.1 ms`, but stayed
under the preregistered `582 ms` ceiling. API-level hand/pose inference overlap increased from about
`65.7%` to `99.5%`; MediaPipe/GPU internal execution is not directly observable. The result supports
advancing A1 to the small signed sentinel, but is not yet `KEEP A1 AS V2 FOUNDATION` because signed
recognition non-regression remains untested. Canonical result:
`context/recognition_upgrade/A1_STAGE1_NO_SIGN_RESULT.md`.

## Authorized signing sentinel

The sentinel uses `GOOD`, `WE`, `NOW`, `KNOW`, `HAVE`, and `HELLO`, two natural attempts per mode,
with 12 Baseline and 12 A1 captures interleaved and order-balanced. It reuses the output-only RU-D1
bundle path and the frozen `582 ms` pose ceiling. It does not change S4-S7, models, thresholds, or
perception semantics.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "F:\ASL DATASET\5. Apphear3\model\config\recognition_upgrade\run_a1_signing_sentinel.ps1" -Command Install

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "F:\ASL DATASET\5. Apphear3\model\config\recognition_upgrade\run_a1_signing_sentinel.ps1" -Command Collect -SignerId signer_01
```

Do not begin A2 from this Stage-1 pass. First pull, annotate, and compare signed bundles.

## Signing sentinel decision

The 24-attempt sentinel completed and supports `KEEP A1 AS V2 FOUNDATION`. Baseline versus A1 had
the same aggregate S5 onset count (`11/12`), essentially equal hand coverage (`57.1%` vs `57.9%`)
and two-hand coverage (`20.6%` vs `20.0%`), and full pose coverage. Recorded on-phone correct
commits increased `2 → 5`, wrong commits decreased `5 → 4`, and no-commits decreased `5 → 3`.
`GOOD` and `HAVE` improved to two correct A1 commits each. One of two A1 `HELLO` attempts missed
onset despite both Baseline attempts committing correctly, so that isolated caveat remains for any
broader evaluation. `KNOW`, `NOW`, and `WE` remain unresolved.

The result keeps A1 experimental and default-off; it does not authorize production deployment.
Aggregate signed landmark coverage remaining flat also establishes that scheduling alone does not
solve MediaPipe detector/occlusion loss. Canonical signed result:
`context/recognition_upgrade/A1_SIGNING_SENTINEL_RESULT.md`.
