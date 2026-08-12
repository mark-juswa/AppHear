# E4-AE Hard-Negative Weighted Signing Gate Result

Last updated: 2026-08-02

## Purpose

E4-AE tests whether upweighting train-split hard negatives found by E4-AD improves the E4-AC low-motion-aware signing gate without leaking test rows into training.

## Verified Project References

- Runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_ae_hard_negative_gate.py`
- Historical no-effect run: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_ae_hard_negative_gate_01`
- Corrected run: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_ae_hard_negative_gate_02`
- Metrics: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_ae_hard_negative_gate_02\metrics\hard_negative_gate_metrics.json`
- Source hard negatives: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_ad_false_commit_review_01`

## Result Summary

Corrected run: `e4_ae_hard_negative_gate_02`

- Structural check passed.
- Experiment gate failed.
- Train hard negatives upweighted: `12`
- Hard-negative weight: `6.0`
- Mean accepted precision: `0.9605`
- Minimum accepted precision: `0.9417`
- Mean positive coverage: `0.9746`
- Minimum positive coverage: `0.9661`
- Maximum no-sign false commit rate: `0.0882`
- Mean/min GOOD recall: `0.9667` / `0.9667`
- Mean/min SORRY recall: `0.9667` / `0.9667`

## Interpretation

E4-AE did not improve on E4-AC. It preserved `SORRY`, but seed `101` worsened on no-sign false commits, pushing minimum accepted precision down to `0.9417`. This means naive hard-negative sample weighting is not a sufficient fix.

## Decision

Do not continue tuning hard-negative weights as the main path. The best current gate remains E4-AC `01`, but it is still not runtime-approved. The next high-value step is likely either more diverse no-sign/P1 data or an architecture/policy change that separates `HELLO`-like ordinary hand movement from intentional signing more explicitly.

## Recommended Next Action

Prepare a focused E4-AF plan before more training: compare two options using the existing E4-AD evidence.

1. Add more P1/N0 capture diversity targeted around `HELLO`-like ordinary movement.
2. Add an uncertainty/abstain band or two-stage gate where suspicious no-sign/HELLO-like windows are rejected unless the recognizer has temporal confirmation over multiple consecutive windows.

No Android/export until this gate passes with margin.
