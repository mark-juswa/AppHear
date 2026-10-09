# APPHEAR_FINGERSPELLING_RESIDUAL_VISUAL_RESULTS_REVIEW_01

**RESIDUAL_VISUAL_NOT_SUPPORTED_STOP_VISUAL_PATH.** The full residual experiment
provides a modest positive signal but fails its frozen support rule. Preserve it as
research evidence, keep B2 as the retained recognizer, and stop this visual direction.
No further training, architecture, data expansion or Android work was performed.
This is signer-disjoint DEV analysis, not deployed accuracy or proof all visual methods fail.

## Verified state and execution

Branch `codex/current-working-text-to-asl-baseline-2026-09-29`; HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358`. Existing dirty/untracked work preserved.
Only documentation/state updates were made during this results review.

- Governed1024TRAIN/256DEV; full visual package1280/1280validated, TEST sealed.
- Saved run identity matches current code/config/data/visual receipt identities.
- Actual B2 checkpoint SHA
  `64f425358ef30e21a4aca18795226854f7aa44a34c3bc3e54a8c06366cb61397`.
- Residual epoch35 checkpoint SHA
  `f87be3236196c8ab8321a3b6f7bb9d6398d048e257630a38546e8a8d00143251`.
  File hash, selection metadata and final evaluation agree.
-39epochs completed; earliest best score at35 verified from all epoch reports.
  Early stopping: meaningful-improvement anchor0.5386173,12non-improving epochs.
  Smaller later gains did not reset the frozen patience criterion.
- Every epoch retains1024TRAIN sources, minimum selected CTC headroom0,
  frozen B2 unchanged, no TEST access. Decoder0.5 unchanged/no retuning.
- Logged epoch times total≈36.8minutes, excluding startup/reference and final evaluation.
  No training/inference was rerun; saved final decision recomputed identically.

## Full256DEV, fixed B2 decoder0.5

Each view has3457reference characters. Counts use existing deterministic sequence
Levenshtein alignment, not invented letter boundaries.

| Metric | B2 native | Residual native | B2 phone-like | Residual phone-like |
|---|---:|---:|---:|---:|
| CER |55.05%|53.86%|54.47%|53.69%|
| Correct aligned characters |1656|1710|1760|1779|
| Substitutions |582|591|968|962|
| Deletions |1219|1156|729|716|
| Insertions |102|115|186|178|
| Predicted characters |2340|2416|2914|2919|
| Correct/predicted precision |70.77%|70.78%|60.40%|60.95%|
| Exact sequences |0|0|0|0|
| Empty predictions |3|3|0|0|

Balanced CER54.7585%→53.7749%:0.9835percentage-point improvement, approximately
1.80%relative error reduction. Correct native+54/sparse+19. Native deletion−63 is
partly offset by substitution+9/insertion+13. Sparse S−6/D−13/I−8 is a small cleaner gain.

Raw penalty0 CER also improves: native58.43%→57.48%, sparse54.82%→54.12%.
Raw native S386→400 and precision77.56%→77.18% worsen slightly; sparse S733→717
and precision66.63%→67.48% improve. Fixed0.5 remains the preselected comparison.

11/15DEV signers improve balanced CER;4worsen. Largest signer gain≈3.95points.
Aligned counts improve for18of27symbols native and17of27sparse;7native/8sparse
symbols worsen. These are diagnostics, not significance or independent confirmation.
DEV was used for checkpoint selection, and no uncertainty interval was established.

| Subgroup | Sequences | Native B2→residual CER | Sparse B2→residual CER |
|---|---:|---:|---:|
| J-containing |59|55.73%→54.80%|54.93%→53.20%|
| Z-containing |52|56.55%→54.48%|56.41%→54.07%|
| Repeated letters |109|54.11%→52.92%|53.51%→53.51%|

Sequence subgroup CER does not prove individual J/Z recall improvement: sparse Z
aligned count decreased despite lower Z-containing sequence CER.

## TRAIN diagnostic and decision

The existing metadata-selected TRAIN diagnostic contains only8sequences/143reference
characters. At epoch35 fixed-decoder native CER39.86%→39.16%, correct88→91;
sparse CER36.36%→34.97%, correct99→96. This is not whole1024TRAIN fit evidence.
Sparse TRAIN CER improves despite fewer matches, reinforcing why CER alone is insufficient.

Seven of eight frozen checks pass: both CERs lower, both correct counts higher,
sparse substitutions lower, mean precision stable and≥8signers improve (actual11).
**Only native substitutions fail:582→591.**

This differs from a pure more-emission/unchanged-correct-count failure: visual correction
has a small real signal. Do not describe it as no visual information or universally
signer-specific overfitting. Nevertheless it did not meet the agreed discrimination
pattern, no exact strings emerged, and the rule must not be relaxed after seeing results.

Keep B2; preserve residual artifacts; close this visual direction. Do not automatically
try another backbone/crop-size/attention/TCN/training/data-expansion/Android experiment.
The remaining fingerspelling bottleneck and next intervention are not proven by this run;
any next work needs a new bounded evidence-based scope.

Primary artifact: `runs/fingerspelling_residual_visual_01/final_evaluation.json`.

**RESIDUAL_VISUAL_NOT_SUPPORTED_STOP_VISUAL_PATH**
