# E4-K Checkpoint Policy Result

**Purpose:** Record the checkpoint-policy diagnostic after E4-J showed strong Conv1D latest checkpoints but unstable validation-best checkpoints.

**Scope:** Experiment result only. This does not authorize Android integration, model export, production recognizer replacement, source dataset mutation, or vocabulary expansion beyond a separately prepared offline diagnostic.

**Current status:** Completed. Structural check passed. Recommended policy is `conv1d_baseline_latest_fixed_epoch` for the next offline expansion diagnostic only.

**Last updated:** 2026-07-30.

## Verified Project References

- Runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_k_checkpoint_policy.py`
- Source run: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_j_reliable_core_3sign_pilot_01`
- E4-K run directory: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_k_checkpoint_policy_01`
- Policy report: `metrics\policy_report.json`
- Markdown summary: `metrics\policy_report.md`
- Check report: `check_report.json`

## Completion Evidence

Structural check passed:

```json
{
  "passed": true,
  "errors": []
}
```

## Main Result

| Branch | Checkpoint | Mean Test | Std Test | Min Seed Test | Min Class Test | Collapse Seeds | Stable >=0.90 |
|---|---|---:|---:|---:|---:|---:|---|
| `conv1d_baseline` | `best` | `0.8185` | `0.1134` | `0.7222` | `0.1667` | `1` | `false` |
| `conv1d_baseline` | `latest` | `0.9741` | `0.0052` | `0.9667` | `0.9333` | `0` | `true` |
| `tcn_masked_pool` | `best` | `0.7741` | `0.1362` | `0.6778` | `0.1000` | `2` | `false` |
| `tcn_masked_pool` | `latest` | `0.8815` | `0.1205` | `0.7111` | `0.2333` | `0` | `false` |

## Interpretation

E4-K confirms the E4-J interpretation:

- The E4-J script-level gate passed, but the stricter written gate did not.
- Validation accuracy is saturated and cannot safely choose checkpoints by itself.
- `conv1d_baseline` latest/fixed-epoch behavior is the only stable policy in this evidence set.
- `tcn_masked_pool` is not the recommended branch for the next local expansion diagnostic.

## Decision

Use `conv1d_baseline_latest_fixed_epoch` for the next offline diagnostic only.

This is not a production model-selection policy yet. It is an experiment policy for the next controlled expansion step.

Do not export E4-J/E4-K to Android.

Do not expand many signs at once.

## Recommended Next Experiment

Prepare E4-L as a one-sign expansion diagnostic:

- Base classes: `GOOD`, `HELLO`, `SORRY`
- Add exactly one candidate sign
- Use `conv1d_baseline` only
- Use latest/fixed-epoch checkpoint policy
- Keep signer-held-out test
- Require every class `>=0.90` test accuracy, no collapse, and stable behavior across seeds

The next candidate should be chosen from verified local signs with enough support and minimal known confusion, not from BYE/NO/THANKYOU/YES.

## Risks

- Repeated use of the same held-out signer can overfit experiment decisions.
- Fixed/latest checkpoint policy may fail once a harder sign is added.
- The 3-sign core proves separability only for a tiny local vocabulary.
- A production silent translator still requires broader vocabulary, boundary handling, false-positive rejection, and Android performance gates.

## Next Required Action

Prepare E4-L one-sign expansion package. Candidate selection must be explicit and evidence-based before training.