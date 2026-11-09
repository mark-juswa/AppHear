# EXP-P3-004 — Candidate recognizers: on-device-runtime parity and relative inference cost

| Field | Value |
|---|---|
| **ID** | EXP-P3-004 |
| **Hypothesis** | The blend candidates load through the production recognizer path, reproduce their Keras outputs within the Gate-2 tolerance (1e-4), keep the frozen class order, and cost a small, bounded amount more per event than the frozen model. |
| **Baseline** | Frozen `1ccf0afa…` (814,068 B) |
| **Dataset / split** | 20 pinned Gate-1 fixture views per candidate (parity only; no accuracy claim) |
| **Configuration** | existing `WordBlendParityInstrumentedTest` (unchanged) run on an arm64 emulator (`sdk_gphone16k_arm64`, 4 vCPU, software GL), 3 rounds × 20 views, first round discarded |
| **Training** | none |
| **Metrics** | max absolute probability difference vs Keras; invocation ms (median, p95); file size |

## Results
| Package | Size | Max abs vs Keras (MEASURED-EMU) | Invocation median / p95, emulator | Frozen, same run |
|---|---:|---:|---:|---:|
| WORD_BLEND_01 | 3,232,620 B (3.97×) | 2.4e-7 | 3.05 / 3.41 ms | 0.75 / 0.97 ms |
| WORD_BLEND_02 | 3,232,620 B (3.97×) | 4.2e-7 | 3.19 / 4.02 ms | 0.76 / 1.20 ms |

Relative cost ≈ **4.1× / 4.2×** the frozen model on this emulator, consistent with the repo's host measurement (5.0 vs 1.1 ms, ≈ 4.5×, REPO-REPORTED). Class order, identity and top-1 on all 20 views match.

### Cost in context (provenance matters)
- Frozen recognizer on the target phone: **≈ 2.7 ms per committed word** (REPO-REPORTED, measured on the Xiaomi).
- Blend on the target phone: **≈ 12 ms per committed word — an ESTIMATE by the repo; not measured.** The emulator number above is *not* a phone number and must not be scaled into one.
- The recognizer runs **once per event**, not per frame. The phone's analyzer spends 135–215 ms per frame (REPO-REPORTED); a ≈ 10 ms increase on the event frame is about 5–7 % of that one frame (ESTIMATE).
- Memory: +2.4 MB of model weights (file size), runtime working set not measured.

## Regression run on the same emulator
All `perceptionvnext` instrumented tests: **25 run, 22 pass, 3 fail for environment reasons** (`ParallelHandRefiner…` and `RecordedPerceptionBenchmark…` need `v3/manifest.json` fixtures supplied by a Gradle property; `LivePerceptionCapture…` needs a launch extra). Included passes: frozen and blend parity, WORD-v2 shadow parity, Recognition-v2 parity and end-to-end replay, S2 parity and the Phase 2 analyzer-recovery tests.

## Conclusion
Hypothesis supported for parity and for a bounded relative cost. Quality-vs-cost: a ≈ 4× larger, ≈ 4× slower-per-event model whose absolute cost is small next to the frame time. **Device latency of the blend remains to be measured.**
