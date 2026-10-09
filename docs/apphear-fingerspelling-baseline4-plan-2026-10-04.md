# Baseline 4 — controlled capacity gate

Research-only recognition experiment authorized by the Baseline-4 request. It is separate from the protected WORD upgrade plan. Existing B1–B3 code, runs and artifacts remain read-only. Read the operational context and recognition-upgrade documents; use the architect → implementation → imprint/review workflow.

## Frozen decisions

- Fit means decoding the fixed 64 TRAIN diagnostic sequences, not generalization or phone accuracy. Use the exact IDs from `artifacts/fingerspelling_baseline3/diagnostic_manifest.json` (32 DAUN, 32 MacKenzie).
- Baseline-2 architecture: 64 channels, four residual blocks, two causal kernel-3 convolutions per block, dilations 1/2/4/8, LayerNorm/ReLU/dropout 0.1, first residual projection, 28-logit head. 193,116 parameters; receptive field 61 observations.
- One candidate: **128 channels**, otherwise identical architecture. 558,236 parameters (2.89×); receptive field stays 61. The first temporal convolution compresses 405 evidence columns to 64 channels in B2; doubling width tests that bottleneck and subsequent discrimination capacity without changing temporal extent. Additional dilation would confound width with history and is unnecessary for this first gate.
- FP32 weights about 2.23 MB, approximately 555,000 convolution/dense MACs per output observation. Phone latency, activation memory, streaming implementation and TFLite conversion remain unmeasured. This is deployment-plausible, not device-certified.
- Both arms start fresh, seed 20261002, identical batch order, 8 samples/batch, Adam 0.001/clipnorm 5, same B2 real-observation cadence schedule and nearest-denser CTC fallback. No loss/decoder/regularization change. Shape-dependent initialization differs; one seed cannot prove a universal capacity effect.
- **60 subset epochs / 480 updates per arm**, evaluate raw native and phone TRAIN views at epochs 0/15/30/45/60. No calibration or DEV selection in the gate. Persist checkpoint, optimizer and committed epoch for resume. A subset epoch is not a full-tranche epoch.
- Authorization rule, fixed before fitting: at BOTH epoch 45 and 60 the candidate must reduce balanced raw TRAIN CER by at least **0.05 absolute**, improve each view's CER, and increase aligned correct/reference character fraction in each view. This is a diagnostic effect threshold, not a production accuracy target. Loss, edit types, exact strings and all per-character recalls accompany it. Failure means the bounded test does not support the hypothesis; it does not establish information loss or prove that all larger models fail. Do not extend the budget or try another architecture after seeing results.

## Conditional continuation

If the gate passes, reuse B2 full training policy unchanged: same 1,024/256 tranche, adapter v1 `[T,405]`, raw-v1, temporal views, CTC28, balanced uncalibrated DEV selection, max90/min30/patience15/minimum-improvement0.002, existing bounded post-selection blank calibration. Add fixed TRAIN diagnostic reports and B2 comparisons. Validate finite gradients/loss, causality/padding, checkpoint and optimizer resume, native/sparse metrics and dataset identities in a short engineering smoke. Then hand full training to the user.

If it does not pass, stop before full B4 training preparation and report the negative/inconclusive fit evidence. Do not change features, perceive new videos, expand data or integrate Android.

No feature-contract or Python/Android feature parity change. Separate B4 config/run identities and CLI provide the opt-in flag; production has no call to this experiment. TEST remains sealed. Candidate01, WORD, Context Assist and all old checkpoints remain untouched.
