# Fingerspelling execution optimization 01

Approved scope, 2026-10-03: prepare a separate execution path while the original baseline
finishes unchanged. This is model/eval execution work, not a new encoder experiment or
Android change. The original trainer, metrics, model config and adapter stay byte-identical.

Execution optimization means identical data/targets/model/loss/optimizer hyperparameters,
not guaranteed identical floating-point trajectories or dropout draws. A checkpoint means
the model + optimizer + completed epoch, not just saved inference weights. Batched DEV
metrics must still decode every actual timestep and retain structurally infeasible phone
views in greedy metrics while excluding them only from CTC loss.

1. Add immutable, schema/hash-checked in-memory feature caching; no new features or data.
2. Add a dynamic-shape compiled loss/gradient/update step with the same Adam configuration.
3. Batch DEV in existing receipt order, trim padded logits by true lengths and preserve
   sequence-weighted eligible CTC loss. No length bucketing or altered TRAIN shuffle.
4. Short bounded tests: cache byte identity; scalar/batched native+phone metrics (including
   infeasible phone cases); eager/graph loss and gradient tolerance with dropout disabled;
   dropout-enabled finite gradients; model/optimizer checkpoint restore without updates.
5. Record stage timings, tracing costs and limits. No bulk run, full epoch or model sweep.
6. New user-run entry point must write an independent identity and run folder. The old
   baseline is read-only. Verify checkpoint compatibility by read-only restoration, but do
   not implement migration or import the running experiment. Future optimized training starts
   only in a separately authorized run; no hash-guard bypass or silent mixing.

Parity acceptance: unchanged cached values and padding; exact greedy text/metrics on the
bounded sample; loss/gradient tolerance rather than bit identity; same architecture and
checkpoint state. Measure speed, do not promise a multiplier. Training quality, convergence
and full-run speed require subsequent evidence. CPU threads, seed, batch size and evaluation
frequency remain unchanged. No GPU migration or TEST data.

Fallback: original `model.fingerspelling_ctc` command and untouched run. No feature-contract
version change. Imprint records only separate offline execution components.
