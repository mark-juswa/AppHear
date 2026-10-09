# A1 Stage-1 No-Sign Device Result

**Date:** 2026-08-16  
**Decision:** `PROCEED_TO_SMALL_SIGNING_SENTINEL`  
**Final A1 disposition:** pending signed non-regression evidence

## Evidence boundary

This is an order-balanced Xiaomi phone runtime result from
`BASELINE_1 → A1_1 → A1_2 → BASELINE_2`. Each run used a 20-second warm-up followed by roughly
100 measured seconds, stationary placement, no hands visible, the same camera/resolution/delegate,
and one APK (`SHA-256 374B75363192C1D8AF0ADE707589A2A11383AAA4E500E671FE31BF18ACC77C2E`).
Trace coverage was `1.0` in every run. `device_benchmark_01` remains invalid tooling evidence and is
not included because post-run logcat capture retained only 1-13 seconds.

## Aggregate result

| Metric | Baseline | A1 | Change / interpretation |
| --- | ---: | ---: | --- |
| Fresh hand publications/s | 5.300 | 7.077 | +33.5% |
| S4 observations/s | 5.304 | 7.063 | +33.1% |
| p95 inter-hand gap | 258.3 ms | 169.3 ms | -34.5% |
| p95 hand-end→S4 | 63.3 ms | 3.9 ms | -93.8% |
| p95 pose age | 296.3 ms | 505.1 ms | Older, but below frozen 582 ms ceiling |
| Synchronizer yield | boundary-affected 1.0009 | 0.9980 | Healthy; 3 `POSE_TOO_OLD` rejections |
| Peak PSS | 453,208 KiB | 461,531 KiB | +1.84% |
| Throughput half-decay | +1.16% | +0.79% | No additional thermal decay signal |
| Hand-interval inference overlap | about 65.7% | about 99.5% | API calls overlap; GPU internals unobservable |

The Baseline yield slightly above one is a warm-up boundary accounting artifact: a measured join
can correspond to a hand publication immediately before the cutoff. It is not evidence of an extra
observation and does not affect the A1 gate, whose own yield was below one and healthy.

No run contained a crash marker, ANR/native-fault marker, no-sign S5 onset, no-sign commit,
ordering violation, or future-pose association. Thermal service status was unavailable on this
device, so the preregistered within-run throughput half-decay check supplied the thermal stability
signal.

## Gate decision

All frozen gates passed: freshness/tail, hand-end→S4, S4 throughput, synchronizer yield, pose age,
ordering, stability, no-sign behavior, memory, thermal decay, and trace coverage. This demonstrates
that independent clocks materially improve usable hand delivery on this phone/backend without a
Stage-1 safety regression.

It does **not** yet show that older causal pose is harmless while signing. The bounded signed
sentinel must compare hand/two-hand coverage, S5 onset/release, S6 target rank, commits, and wrong
commits before A1 can be classified `KEEP A1 AS V2 FOUNDATION` or rejected. A2 remains forbidden.

Primary machine-readable evidence:
`artifacts/recognition_upgrade/a1_independent_clock/device_benchmark_02/a1_device_benchmark_summary.json`.
