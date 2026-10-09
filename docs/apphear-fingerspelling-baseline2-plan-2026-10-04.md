# Baseline 2 implementation plan — 2026-10-04

Scope is the user's cadence-aware/emission-robustness baseline request. All existing WORD,
Candidate01/raw/405 schemas, source lineage/splits/reflection and Baseline-1 evidence stay frozen.
This is a controlled continuation of the existing model and optimized execution components,
not an unrelated encoder/trainer design. New orchestration is necessary to retain Baseline-1
pinned source hashes and checkpoint resumability; encoder, Adam configuration, cached native/
phone data, compiled steps and text metrics are imported/reused unchanged.

Definitions: sparse view is actual frame selection, not simulated camera accuracy; emission
means argmax nonblank timesteps versus collapsed decoded characters; checkpoint contains
model/optimizer/epoch/patience state; calibration is one global blank logit subtraction with
no language priors. Normal CTC uses blanks, so blank fraction alone is not proof of failure.

Frozen config: `model/config/fingerspelling_ctc_baseline_02.json`, written before inference.

1. Diagnose saved epoch-30 Baseline-1 model on fixed metadata/identity-chosen 8 TRAIN and
   15-signers-plus-infeasible-cases DEV subset. Record IDs before inference. Inspect native/
   phone blank fractions and decoded/reference ratios. No training.
2. If sparse blank fraction >=0.8 and decoded/reference ratio <0.5, allow a bounded full-DEV
   blank penalty sweep over 0/0.5/1/1.5/2 on cached inference logits. No more inference per
   penalty. Record evidence, including no-improvement findings. These thresholds are a
   diagnostic eligibility rule, not a production recognition threshold.
3. Add TemporalViewLayer.v1: native /12Hz /6.231166Hz min-gap real indices, same as prior
   phone policy. Deterministic sample+seed offset cycles the requested view over epochs;
   every sample requests each regime once per three epochs. Feasible fallback proceeds to
   nearest denser view; record requested/actual view, frame/index hashes and CTC headroom.
   Derive intermediate views from selected raw observations through the original adapter.
   Never slice dense dt/motion columns or permanently duplicate the corpus.
4. Reuse the existing compiled causal TCN/CTC training primitives. Train once per source per
   epoch. DEV always uses original fixed native/phone views. Select on equal-weight mean
   **uncalibrated** CER, first tie, with both scores retained. Max 90 epochs, min 30 before
   early stop, patience 15, meaningful patience improvement 0.002. Exact best-score selection
   and patience improvement tracking are separate. Batch/LR/architecture remain unchanged.
5. Emission/headroom, length/signer/J/Z/repetition diagnostics accompany each checkpoint.
   Final best-checkpoint calibration uses the predetermined DEV range only, then freezes one
   global penalty in a report. Require combined CER improvement >=0.005, fewer deletions,
   native CER increase <=0.02, mean insertion-rate increase <=0.05; otherwise retain 0.
   Calibration never changes CTC fitting or checkpoint selection. Report raw and calibrated
   scores; DEV-tuned scores are not unseen TEST estimates. A Baseline-1 penalty need not be
   optimal after cadence training, so freeze the range/policy now, the model-specific value
   after final best-checkpoint evaluation. This avoids pretending a B1 bias is transferable.
6. Bounded engineering smoke: 8 TRAIN /8 DEV, three short epochs, actual updates permitted
   by user; pause after epoch 1, restore model/Adam/epoch/patience and continue. Verify view
   variation/fallback, masks/motion, finite loss/gradients and evaluation, no quality claim.
7. Hand off preflight/train/resume/status/final-evaluate commands; agent does not run full
   training. Preserve original completed models and provide rollback to original commands.

Native feature parity must be exact; recomputed phone features must match stored phone
features. Selected raw masks and frame identities remain unchanged. New temporal-view schema
does not change adapter schema/version. No installed Android parity claim or release gate.

Interpretation limit: sparse failure after B2 does not by itself prove information destruction;
first distinguish learning/discrimination/CTC conditions from cadence. No architecture search,
TEST inference, source download, new collection or production recognition change.
