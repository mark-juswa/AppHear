# E4-J Reliable-Core 3-Sign Result

**Purpose:** Record the completed E4-J 3-sign reliable-core benchmark result and decision.

**Scope:** Experiment result only. This does not authorize Android integration, model export, production recognizer replacement, dataset mutation, or vocabulary expansion without a separate approved experiment.

**Current status:** Completed. Structural check passed. Automated gate field passed, but engineering interpretation is a limited pass because best-checkpoint selection remains unstable.

**Last updated:** 2026-07-30.

## Verified Project References

- Runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_j_reliable_core_3sign.py`
- Run directory: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_j_reliable_core_3sign_pilot_01`
- Metrics: `metrics\metrics.json`
- Metrics summary: `metrics\metrics.md`
- Check report: `check_report.json`
- Package plan: `E4_J_RELIABLE_CORE_PACKAGE.md`

## Completion Evidence

Final structural check passed:

```json
{
  "passed": true,
  "errors": []
}
```

This means the run outputs are complete. It does not by itself mean production readiness.

## Dataset

- Classes: `GOOD`, `HELLO`, `SORRY`
- Rows: `190`
- Input shape: `[96,258]`
- Train/validation/test rows: `75/25/90`
- Random baseline: `0.3333`

Class counts:

| Split | GOOD | HELLO | SORRY |
|---|---:|---:|---:|
| train | 15 | 45 | 15 |
| validation | 5 | 15 | 5 |
| test | 30 | 30 | 30 |

## Main Result

Automated summary:

| Branch | Checkpoint | Mean Test | Std Test | Min Seed Test | Min Class Test |
|---|---|---:|---:|---:|---:|
| `conv1d_baseline` | best | `0.8185` | `0.1134` | `0.7222` | `0.1667` |
| `conv1d_baseline` | latest | `0.9741` | `0.0052` | `0.9667` | `0.9333` |
| `tcn_masked_pool` | best | `0.7741` | `0.1362` | `0.6778` | `0.1000` |
| `tcn_masked_pool` | latest | `0.8815` | `0.1205` | `0.7111` | `0.2333` |

Validation-selected checkpoint reported by the script:

- Branch: `conv1d_baseline`
- Seed: `202`
- Checkpoint: `best`
- Validation accuracy: `1.0000`
- Test accuracy: `0.9778`
- Minimum class test accuracy: `0.9667`

## Per-Seed Interpretation

Conv1D latest checkpoints are strong and stable:

| Seed | Test | GOOD | HELLO | SORRY |
|---:|---:|---:|---:|---:|
| 101 | `0.9778` | `1.0000` | `0.9333` | `1.0000` |
| 202 | `0.9667` | `1.0000` | `0.9333` | `0.9667` |
| 303 | `0.9778` | `1.0000` | `0.9333` | `1.0000` |

Conv1D best checkpoints are not stable:

- Seed 101 best test: `0.7556`, with `SORRY` only `0.4000`.
- Seed 202 best test: `0.9778`, stable.
- Seed 303 best test: `0.7222`, with `SORRY` only `0.1667`.

Masked TCN is worse and unstable:

- Latest mean test: `0.8815`, but seed 303 latest test is only `0.7111` and `SORRY` is only `0.2333`.
- Best mean test: `0.7741`, with seed-level collapses on `SORRY`.

## Gate Interpretation

The script's `gate_passed` field is `true`, but this should be treated carefully.

Engineering interpretation:

- E4-J proves that `GOOD`, `HELLO`, and `SORRY` are separable in the current `[96,258]` landmark feature space when using the Conv1D latest checkpoint family.
- E4-J does not prove that the current validation-based best-checkpoint selection is reliable.
- E4-J does not support TCN as the next model choice.
- E4-J does not authorize Android integration or production export.

Strictly, the written E4-J gate required latest and best checkpoint families to be stable. The best-checkpoint family is not stable, so this is a **limited pass / checkpoint-policy no-go** rather than a full production go.

## Decision

Use E4-J as evidence that a small reliable local landmark core exists, specifically with `conv1d_baseline` latest checkpoints.

Do not use masked TCN for the next step.

Do not export a production model yet.

The next highest-value step is to fix the checkpoint-selection/evaluation policy before expanding vocabulary. The current validation set is too small and too easy: all branches/seeds can show `1.0000` validation while held-out test ranges from excellent to collapsed.

## Recommended Next Experiment

E4-K should be a checkpoint-policy diagnostic on the same 3-sign package, without rerunning extraction:

- Select checkpoints by a more robust rule than validation accuracy alone.
- Compare latest checkpoint, validation-loss checkpoint, validation-accuracy checkpoint, and possibly averaged last-N checkpoints.
- Report held-out test only after the rule is fixed.
- Keep classes fixed as `GOOD`, `HELLO`, `SORRY`.
- Prefer `conv1d_baseline`; keep masked TCN only as a control or drop it if the goal is speed.

If E4-K confirms Conv1D latest or another stable policy, then expand by adding one candidate sign at a time.

## Risks

- Repeated decisions on the same held-out signer can overfit experiment choices to this test set.
- Validation is not signer-independent enough for reliable checkpoint selection.
- The 3-sign core is too small to provide product value by itself.
- Future signs may still fail due label inconsistency, insufficient signers, or feature overlap.

## Next Required Action

Prepare E4-K checkpoint-policy diagnostic or directly patch E4-J reporting/check logic so the automated gate matches the written gate. Do not expand vocabulary until checkpoint selection is made reliable.