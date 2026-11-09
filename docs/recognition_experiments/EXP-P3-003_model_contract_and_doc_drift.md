# EXP-P3-003 — Model contract validation and documentation drift

| Field | Value |
|---|---|
| **ID** | EXP-P3-003 |
| **Hypothesis** | The audit documents (WORD_ACCURACY_236, WORD_PRIORITIES, Phases 1–2) still describe the implementation: model hashes, class list, engines, thresholds. (Falsifiable by any mismatch.) |
| **Baseline** | Frozen `ordinary_v2_tcn_fp32.tflite` `1ccf0afa…02880c`; candidates WORD_V2 `1de85b3c…`, WORD_BLEND_01 `bc8a6c91…`, WORD_BLEND_02 `40533bc3…` |
| **Dataset / split** | none: asset and source files only |
| **Configuration** | `python -m eval.recognition_experiments.model_contract_check` (and JVM `RecognitionAccuracyRegressionTest`) |
| **Training** | none |
| **Metrics** | pass/fail checks; documented-claim table |

## Results (COMPUTED; result file `results/model_contract_check.json`)
- **42 checks, 0 failed.** For every package (frozen, WORD v2, BLEND_01, BLEND_02): model file present; TFLite SHA-256 equals the manifest; 236 unique classes; class order identical across all four manifests; schema `apphear.perception_vnext.recognition.v2`; input `[1,96,350]`, mask `[1,96]`, output `[1,236]` softmax; protected TEST not accessed; vocabulary pin equals the Kotlin `VOCAB_SHA`. Frozen model hash equals the Kotlin `MODEL_SHA`; frozen manifest hash equals `GATE2_MANIFEST_SHA`.
- Legacy `assets/vocab.json` (gloss → index) has the **same 236 glosses in the same order** as Recognition-v2.
- Confidence floors in code (STABLE 0.55, EXPERIMENTAL 0.75) equal the calibration evidence file; BLEND engines carry no floor.
- All four documented hash prefixes hold. Engines in code: STABLE, EXPERIMENTAL, EXPERIMENTAL_WORD_BLEND, EXPERIMENTAL_WORD_BLEND_02.
- Sizes: frozen 814,068 B; WORD v2 814,068 B; BLEND_01 and BLEND_02 3,232,620 B each.

## Drift found (documents vs implementation)
1. `WORD_ACCURACY_236_2026-10-17.md` §5 says the blend is "not yet wired into the app". The code has both blend engines (`EXPERIMENTAL_WORD_BLEND`, `…_02`) and the Phase 1.2 APK packages them; `WORD_PRIORITIES_2026-10-18.md` (a day later) states they are installed. The earlier sentence is stale.
2. The Phase 1 shadow/gate documents describe BLEND engines as having no calibrated floor; this still holds in code.
3. `AGENTS.md` / `context/` still describe the MediaPipe-258 pipeline (reconnaissance F-007); unchanged.
4. One published count (per-class movement 52 "down") includes a float-boundary class (see EXP-P3-001).

## Limitation
The vocabulary pin is the SHA-256 of an external `VOCAB_MANIFEST` file, not of the class list; it cannot be recomputed from this repository, so it is enforced as a declared pin only.

## Conclusion
Hypothesis supported with the drift above. No model, vocabulary or contract change is needed.
